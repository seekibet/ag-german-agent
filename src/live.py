"""Interactive live runner — type real questions, see real answers + metrics.

Usage:
    python -m src.live                                          # interactive REPL
    python -m src.live "How do I apply for the DAAD scholarship?"  # one-shot
    python -m src.live --session my_session                    # logs to data/sessions/my_session.csv
"""
import argparse
import csv
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agent import FAQAgent   # noqa: E402
from src.judge import Judge       # noqa: E402
from src import metrics as M      # noqa: E402
from src.llm_client import get_client  # noqa: E402


DIVIDER  = "─" * 72
DIVIDER2 = "═" * 72


def render_result(trace: dict, judge_result: dict | None = None):
    res = trace["result"]
    cfg = trace["config"]

    print("\n" + DIVIDER2)
    print(f"  QUESTION")
    print(f"  {trace['question']}")
    print(DIVIDER2)

    print(f"\n  STEP 1 — CATEGORY DETECTED")
    print(f"  {res['category']}")

    print(f"\n  STEP 2 — SOPs RETRIEVED  (top_k={cfg['top_k']})")
    for s in res["retrieved_sops"]:
        step = next(st for st in trace["steps"] if st["step"] == "retrieve")
        match = next((r for r in step["retrieved"] if r["sop_id"] == s), {})
        score = match.get("score", 0)
        title = match.get("title", "")[:60]
        print(f"  [{score:5.2f}]  {s}  {title}")

    print(f"\n  STEP 3 — ANSWER")
    print(DIVIDER)
    for line in res["answer"].split("\n"):
        print(f"  {line}")
    print(DIVIDER)

    # Metrics that work without ground truth
    gr  = M.grounding_rate(res["answer"], res["retrieved_context"])
    sr  = M.staleness_disclaimer_rate(res["answer"])
    nsr = M.next_step_rate(res["answer"])

    print(f"\n  AUTOMATIC METRICS  (no ground truth needed)")
    print(f"  grounding_rate              {gr:.0%}   {'✓' if gr >= 0.90 else '⚠'}"
          f"   {'every cited fact is in the retrieved SOPs' if gr >= 0.90 else 'some facts may not be in retrieved SOPs — FM-04'}")
    print(f"  staleness_disclaimer_rate   {sr:.0%}   {'✓' if sr == 1.0 else '⚠'}"
          f"   {'volatile facts carry verify-at-source note' if sr == 1.0 else 'answer cites deadlines/amounts without disclaimer — FM-05'}")
    print(f"  next_step_rate              {nsr:.0%}   {'✓' if nsr == 1.0 else '⚠'}"
          f"   {'answer ends with actionable link/contact' if nsr == 1.0 else 'no next step found — FM-06'}")

    if judge_result:
        v = judge_result["verdict"]
        icon = {"good": "✓", "partial": "~", "bad": "✗"}.get(v, "?")
        print(f"\n  LLM-AS-JUDGE  (model: {judge_result['judge_model']})")
        print(f"  verdict: {icon} {v.upper()}")
        print(f"  reason:  {judge_result['reason']}")

    mode = "MOCK — install an API key for real answers" if cfg.get("mock") else f"LIVE  model={cfg['model']}"
    print(f"\n  mode: {mode}")
    print(f"  trace: {trace.get('trace_path','')}")
    print(DIVIDER2 + "\n")


def append_to_session(path: str, trace: dict, judge_result: dict | None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    exists = os.path.exists(path)
    res = trace["result"]
    gr  = M.grounding_rate(res["answer"], res["retrieved_context"])
    sr  = M.staleness_disclaimer_rate(res["answer"])
    nsr = M.next_step_rate(res["answer"])
    row = {
        "ts":            trace["ts"],
        "question":      trace["question"],
        "category":      res["category"],
        "retrieved_sops": ",".join(res["retrieved_sops"]),
        "grounding_rate": round(gr, 3),
        "staleness_disclaimer_rate": round(sr, 3),
        "next_step_rate": round(nsr, 3),
        "judge_verdict": judge_result["verdict"] if judge_result else "",
        "judge_reason":  judge_result["reason"]  if judge_result else "",
        "answer":        res["answer"][:300],
        "trace_path":    trace.get("trace_path", ""),
    }
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=row.keys())
        if not exists:
            w.writeheader()
        w.writerow(row)


def run_once(question: str, agent: FAQAgent, judge: Judge | None,
             session_path: str | None) -> dict:
    print(f"\n  → running...  ", end="", flush=True)
    t0 = time.time()
    trace = agent.answer(question)
    print(f"done in {time.time()-t0:.1f}s")
    j = judge.judge(question, trace["result"]["answer"]) if judge else None
    render_result(trace, j)
    if session_path:
        append_to_session(session_path, trace, j)
        print(f"  saved to session log: {session_path}")
    return trace


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question", nargs="*", help="question to ask (omit for REPL)")
    ap.add_argument("--top-k", type=int, default=3)
    ap.add_argument("--session", default=None,
                    help="session name; logs to data/sessions/<name>.csv")
    ap.add_argument("--no-judge", action="store_true")
    args = ap.parse_args()

    client, is_mock = get_client()
    agent = FAQAgent(top_k=args.top_k, client=client)
    judge = None if args.no_judge else Judge(client=client)

    session_path = (f"data/sessions/{args.session}.csv"
                    if args.session else None)

    if is_mock:
        print("\n  ⚠  MOCK MODE — answers are deterministic stand-ins.")
        print("     Add ANTHROPIC_API_KEY to .env for real Claude answers.\n")
    else:
        print(f"\n  ✓  LIVE MODE — agent={agent.model}")
        if judge:
            print(f"                judge={judge.model} (pinned)\n")

    if args.question:
        # one-shot
        run_once(" ".join(args.question), agent, judge, session_path)
        return

    # REPL
    print("  Germany FAQ — live session  (type 'quit' or Ctrl+C to exit)")
    print("  Every answer + metrics printed here, full trace saved to traces/\n")
    while True:
        try:
            q = input("  Question: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  Exiting.")
            break
        if not q or q.lower() in ("quit", "exit", "q"):
            break
        run_once(q, agent, judge, session_path)


if __name__ == "__main__":
    main()
