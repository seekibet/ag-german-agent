"""FastAPI serving layer for the Germany FAQ Agent.

Endpoints
  Public (end users)
    POST /api/ask          ask a question -> grounded answer + sources + metrics
    POST /api/feedback     mark an answer helpful / not helpful
  Admin (AG-Career Hub personnel, gated by X-Admin-Token header)
    GET  /api/admin/stats          live aggregate dashboard data
    GET  /api/admin/questions      recent answered questions (filter by category)
    GET  /api/admin/flagged        questions needing review
    GET  /api/admin/trace/{id}     full JSON trace for one question
    GET  /api/admin/sops           list SOPs in the knowledge base
    GET  /api/admin/sops/{id}      one SOP's full text
    PUT  /api/admin/sops/{id}      edit a SOP, then rebuild the BM25 index
    POST /api/admin/reindex        rebuild the index without editing

Static UI
    /            end-user chat        (web/index.html)
    /admin       personnel dashboard  (web/admin.html)

Run:  make serve   (or  uvicorn api.server:app --reload)
The agent runs in MOCK mode unless ANTHROPIC_API_KEY is set — the server
works fully offline for development.
"""
import json
import os
import time
import uuid

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from api import admin_store
from src.agent import FAQAgent
from src import metrics as M

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "ag-admin-dev")  # override in production
SOPS_DIR = "data/sops"

app = FastAPI(title="Germany FAQ Agent", version="1.0")

# One agent instance, reused across requests. Rebuilt on SOP edits.
_agent = FAQAgent(top_k=int(os.getenv("TOP_K", "5")), sops_dir=SOPS_DIR)


def rebuild_agent():
    global _agent
    _agent = FAQAgent(top_k=_agent.top_k, sops_dir=SOPS_DIR)


# ── schemas ──────────────────────────────────────────────────────────────────
class AskRequest(BaseModel):
    question: str


class FeedbackRequest(BaseModel):
    trace_id: str
    helpful: bool
    comment: str = ""


class SopUpdate(BaseModel):
    content: str


# ── auth ─────────────────────────────────────────────────────────────────────
def require_admin(token: str | None):
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Admin token required.")


# ── public endpoints ─────────────────────────────────────────────────────────
@app.post("/api/ask")
def ask(req: AskRequest):
    q = (req.question or "").strip()
    if not q:
        raise HTTPException(status_code=400, detail="Question is empty.")

    trace = _agent.answer(q)
    res = trace["result"]

    grounding = M.grounding_rate(res["answer"], res["retrieved_context"])
    staleness = M.staleness_disclaimer_rate(res["answer"])
    next_step = M.next_step_rate(res["answer"])

    retrieve_step = next(s for s in trace["steps"] if s["step"] == "retrieve")
    sources = [
        {"sop_id": r["sop_id"], "title": r["title"].split(":", 1)[-1].strip()}
        for r in retrieve_step["retrieved"]
    ]

    admin_store.log_question({
        "trace_id": trace["trace_id"],
        "ts": trace["ts"],
        "question": q,
        "category": res["category"],
        "answer": res["answer"],
        "retrieved_sops": res["retrieved_sops"],
        "grounding_rate": grounding,
        "staleness_disclaimer_rate": staleness,
        "next_step_rate": next_step,
        "mock": trace["config"].get("mock", False),
        "feedback": None,
    })

    return {
        "trace_id": trace["trace_id"],
        "category": res["category"],
        "answer": res["answer"],
        "sources": sources,
        "mock": trace["config"].get("mock", False),
    }


@app.post("/api/feedback")
def feedback(req: FeedbackRequest):
    ok = admin_store.add_feedback(req.trace_id, req.helpful, req.comment)
    if not ok:
        raise HTTPException(status_code=404, detail="Unknown trace_id.")
    return {"status": "recorded"}


# ── admin endpoints ──────────────────────────────────────────────────────────
@app.get("/api/admin/stats")
def admin_stats(x_admin_token: str | None = Header(default=None)):
    require_admin(x_admin_token)
    s = admin_store.stats()
    s["agent"] = {"top_k": _agent.top_k, "model": _agent.model,
                  "mock": _agent.is_mock,
                  "prompts": _agent.prompt_versions}
    return s


@app.get("/api/admin/questions")
def admin_questions(category: str | None = None, limit: int = 100,
                    x_admin_token: str | None = Header(default=None)):
    require_admin(x_admin_token)
    return {"questions": admin_store.recent(limit=limit, category=category)}


@app.get("/api/admin/flagged")
def admin_flagged(x_admin_token: str | None = Header(default=None)):
    require_admin(x_admin_token)
    return {"flagged": admin_store.flagged()}


@app.get("/api/admin/trace/{trace_id}")
def admin_trace(trace_id: str, x_admin_token: str | None = Header(default=None)):
    require_admin(x_admin_token)
    traces_dir = os.getenv("TRACES_DIR", "traces")
    path = os.path.join(traces_dir, f"trace_{trace_id}.json")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Trace not found.")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@app.get("/api/admin/sops")
def admin_sops(x_admin_token: str | None = Header(default=None)):
    require_admin(x_admin_token)
    out = []
    for sid, sop in _agent.sops_db.items():
        out.append({"sop_id": sid, "title": sop["title"],
                    "words": len(sop["content"].split())})
    return {"sops": out}


@app.get("/api/admin/sops/{sop_id}")
def admin_get_sop(sop_id: str, x_admin_token: str | None = Header(default=None)):
    require_admin(x_admin_token)
    sop_id = sop_id.upper()
    if sop_id not in _agent.sops_db:
        raise HTTPException(status_code=404, detail="SOP not found.")
    return {"sop_id": sop_id, "content": _agent.sops_db[sop_id]["content"]}


@app.put("/api/admin/sops/{sop_id}")
def admin_put_sop(sop_id: str, body: SopUpdate,
                  x_admin_token: str | None = Header(default=None)):
    require_admin(x_admin_token)
    sop_id = sop_id.upper()
    if sop_id not in _agent.sops_db:
        raise HTTPException(status_code=404, detail="SOP not found.")
    # find the file on disk for this SOP id
    num = sop_id.split("_")[1]
    import glob
    matches = glob.glob(os.path.join(SOPS_DIR, f"sop_{num}_*.txt"))
    if not matches:
        raise HTTPException(status_code=404, detail="SOP file not found on disk.")
    with open(matches[0], "w", encoding="utf-8") as f:
        f.write(body.content)
    rebuild_agent()
    return {"status": "saved", "sop_id": sop_id, "reindexed": True}


@app.post("/api/admin/reindex")
def admin_reindex(x_admin_token: str | None = Header(default=None)):
    require_admin(x_admin_token)
    rebuild_agent()
    return {"status": "reindexed", "sops": len(_agent.sops_db)}


# ── static UI ────────────────────────────────────────────────────────────────
@app.get("/")
def index():
    return FileResponse("web/index.html")


@app.get("/admin")
def admin_page():
    return FileResponse("web/admin.html")


@app.get("/health")
def health():
    return {"status": "ok", "mock": _agent.is_mock, "sops": len(_agent.sops_db)}


# serve any other static assets (favicon etc.) if present
if os.path.isdir("web"):
    app.mount("/static", StaticFiles(directory="web"), name="static")
