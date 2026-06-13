"""Persistence for the serving layer.

Every end-user question is appended to data/qa_log.jsonl with the answer,
retrieved SOPs, and the three ground-truth-free metrics (grounding, staleness,
next-step) so AG personnel can monitor live quality. Feedback is matched back
to a row by trace_id. This is deliberately a flat JSONL file — no database —
so it is trivially inspectable, greppable, and resettable.
"""
import json
import os
import threading
from typing import Dict, List, Optional

_LOCK = threading.Lock()
QA_LOG = os.path.join("data", "qa_log.jsonl")


def _ensure():
    os.makedirs("data", exist_ok=True)
    if not os.path.exists(QA_LOG):
        open(QA_LOG, "a", encoding="utf-8").close()


def log_question(record: Dict) -> None:
    """Append one answered question. Caller supplies trace_id + metrics."""
    _ensure()
    with _LOCK:
        with open(QA_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def add_feedback(trace_id: str, helpful: bool, comment: str = "") -> bool:
    """Attach feedback to an existing row by rewriting the file in place.
    Returns True if a matching row was found."""
    _ensure()
    found = False
    with _LOCK:
        rows = _read_all_unlocked()
        for r in rows:
            if r.get("trace_id") == trace_id:
                r["feedback"] = {"helpful": helpful, "comment": comment}
                found = True
        if found:
            with open(QA_LOG, "w", encoding="utf-8") as f:
                for r in rows:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return found


def _read_all_unlocked() -> List[Dict]:
    if not os.path.exists(QA_LOG):
        return []
    out = []
    with open(QA_LOG, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return out


def read_all() -> List[Dict]:
    with _LOCK:
        return _read_all_unlocked()


def recent(limit: int = 100, category: Optional[str] = None) -> List[Dict]:
    rows = read_all()
    if category:
        rows = [r for r in rows if r.get("category") == category.upper()]
    return list(reversed(rows))[:limit]


def flagged() -> List[Dict]:
    """Rows that need a human eye: imperfect grounding, missing next step,
    or explicit negative feedback."""
    out = []
    for r in read_all():
        fb = r.get("feedback") or {}
        if (r.get("grounding_rate", 1.0) < 1.0
                or r.get("next_step_rate", 1.0) < 1.0
                or r.get("staleness_disclaimer_rate", 1.0) < 1.0
                or fb.get("helpful") is False):
            out.append(r)
    return list(reversed(out))


def stats() -> Dict:
    rows = read_all()
    n = len(rows)
    if n == 0:
        return {"total": 0, "by_category": {}, "avg_grounding": None,
                "avg_staleness": None, "avg_next_step": None,
                "feedback": {"helpful": 0, "not_helpful": 0, "none": 0},
                "flagged": 0}

    def avg(key):
        vals = [r.get(key) for r in rows if isinstance(r.get(key), (int, float))]
        return round(sum(vals) / len(vals), 3) if vals else None

    by_cat: Dict[str, int] = {}
    helpful = not_helpful = none = 0
    for r in rows:
        by_cat[r.get("category", "GENERAL")] = by_cat.get(r.get("category", "GENERAL"), 0) + 1
        fb = r.get("feedback")
        if fb is None:
            none += 1
        elif fb.get("helpful"):
            helpful += 1
        else:
            not_helpful += 1

    return {
        "total": n,
        "by_category": dict(sorted(by_cat.items(), key=lambda kv: -kv[1])),
        "avg_grounding": avg("grounding_rate"),
        "avg_staleness": avg("staleness_disclaimer_rate"),
        "avg_next_step": avg("next_step_rate"),
        "feedback": {"helpful": helpful, "not_helpful": not_helpful, "none": none},
        "flagged": len(flagged()),
    }
