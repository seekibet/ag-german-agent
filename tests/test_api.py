"""Serving-layer tests — fully offline via the mock client."""
import os
os.environ.pop("ANTHROPIC_API_KEY", None)   # force mock before import

from fastapi.testclient import TestClient
from api.server import app

c = TestClient(app)
ADMIN = {"X-Admin-Token": "ag-admin-dev"}


def test_health():
    d = c.get("/health").json()
    assert d["status"] == "ok" and d["sops"] == 9


def test_ask_returns_answer_and_sources():
    r = c.post("/api/ask", json={"question": "nursing apprenticeship SGAO?"})
    assert r.status_code == 200
    d = r.json()
    assert d["category"] == "APPRENTICESHIP"
    assert any(s["sop_id"] == "SOP_002" for s in d["sources"])
    assert d["trace_id"]


def test_ask_empty_question_rejected():
    assert c.post("/api/ask", json={"question": "  "}).status_code == 400


def test_feedback_roundtrip():
    tid = c.post("/api/ask", json={"question": "WIDU africa grant?"}).json()["trace_id"]
    assert c.post("/api/feedback",
                  json={"trace_id": tid, "helpful": True}).status_code == 200
    assert c.post("/api/feedback",
                  json={"trace_id": "nope", "helpful": True}).status_code == 404


def test_admin_requires_token():
    assert c.get("/api/admin/stats").status_code == 401
    assert c.get("/api/admin/stats", headers=ADMIN).status_code == 200


def test_admin_lists_nine_sops():
    d = c.get("/api/admin/sops", headers=ADMIN).json()
    assert len(d["sops"]) == 9


def test_pages_serve():
    assert c.get("/").status_code == 200
    assert c.get("/admin").status_code == 200
