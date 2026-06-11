"""Metrics module. Each metric maps 1:1 to a failure mode in failure_modes.md.

All metrics are pure functions (no API calls) so they are fast, deterministic,
and unit-testable. Token extraction is shared via fact_tokens().
"""
import re
from typing import List

from src.retrieval import normalize_sop_name

# Generic uppercase words that are not "facts" (avoid false fact tokens)
_STOPWORDS = {"THE", "AND", "FOR", "WITH", "ONLY", "ALL", "MUST", "NOT",
              "VIA", "PER", "NEW", "ARE", "HAS", "CAN", "MAY", "ONE"}


def fact_tokens(text: str) -> List[str]:
    """Distinctive fact tokens: euro amounts, acronyms (2-6 caps), 4-digit years."""
    raw = re.findall(r"€[\d,.]+|\b[A-Z]{2,6}\b|\b\d{4}\b", str(text))
    return sorted({t for t in raw if t not in _STOPWORDS})


# FM-01 — retrieval miss ------------------------------------------------------
def sop_recall(expected_sops: List[str], retrieved_sops: List[str]) -> float:
    exp = {normalize_sop_name(s) for s in expected_sops if str(s).strip()}
    if not exp:
        return 1.0
    ret = {normalize_sop_name(s) for s in retrieved_sops}
    return len(exp & ret) / len(exp)


# FM-02 — category misroute ---------------------------------------------------
def category_accuracy(expected: str, got: str) -> float:
    return float(str(expected).strip().upper() == str(got).strip().upper())


# FM-03 — fact omission -------------------------------------------------------
def keyword_coverage(answer: str, key_facts: str) -> float:
    tokens = fact_tokens(key_facts)
    if not tokens:
        return 1.0
    low = answer.lower()
    return sum(1 for t in tokens if t.lower() in low) / len(tokens)


# FM-04 — ungrounded fact (hallucination) -------------------------------------
def grounding_rate(answer: str, retrieved_context: str) -> float:
    """Fraction of fact tokens in the ANSWER that also appear in the
    retrieved context. 1.0 = fully grounded; <1.0 = invented facts."""
    ans_tokens = fact_tokens(answer)
    if not ans_tokens:
        return 1.0
    ctx = retrieved_context.lower()
    return sum(1 for t in ans_tokens if t.lower() in ctx) / len(ans_tokens)


# FM-05 — stale-data confidence ----------------------------------------------
_VOLATILE = re.compile(r"€[\d,.]+|\bdeadline\b|\b20\d{2}\b", re.I)
_DISCLAIM = re.compile(
    r"verify|check (the )?(current|official)|subject to change|"
    r"updated annually|official source", re.I)


def staleness_disclaimer_rate(answer: str) -> float:
    """If the answer cites volatile facts (amounts/deadlines/years), it must
    carry a verify-at-source disclaimer. 1.0 = compliant."""
    if not _VOLATILE.search(answer):
        return 1.0
    return 1.0 if _DISCLAIM.search(answer) else 0.0


# FM-06 — missing next step ---------------------------------------------------
_NEXT_STEP = re.compile(
    r"https?://|www\.|contact|apply at|next step|@|\.com|\.de|\.org", re.I)


def next_step_rate(answer: str) -> float:
    return 1.0 if _NEXT_STEP.search(answer) else 0.0


METRIC_FAILURE_MAP = {
    "sop_recall": "FM-01",
    "category_accuracy": "FM-02",
    "keyword_coverage": "FM-03",
    "grounding_rate": "FM-04",
    "staleness_disclaimer_rate": "FM-05",
    "next_step_rate": "FM-06",
}
