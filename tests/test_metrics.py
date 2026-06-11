"""One regression test per failure mode in failure_modes.md.
Each test encodes a REAL observed failure (the bad case) and its fix."""
from src import metrics as M


# FM-01 — retrieval miss
def test_fm01_retrieval_miss():
    # Observed: nursing+language question needed SOP_002 AND SOP_009;
    # top_k=3 retrieved only SOP_002 -> recall 0.5
    assert M.sop_recall(["SOP_002", "SOP_009"], ["SOP_002", "SOP_004", "SOP_003"]) == 0.5
    # Fixed (top_k=5 retrieves both)
    assert M.sop_recall(["SOP_002", "SOP_009"],
                        ["SOP_002", "SOP_009", "SOP_004"]) == 1.0
    # Name variants must normalise
    assert M.sop_recall(["sop-2"], ["SOP_002"]) == 1.0


# FM-02 — category misroute
def test_fm02_category_misroute():
    assert M.category_accuracy("STUDY", "SCHOLARSHIP") == 0.0
    assert M.category_accuracy("study", " STUDY ") == 1.0


# FM-03 — fact omission
def test_fm03_fact_omission():
    facts = "Block account €11,904 required. KCSE C+ minimum."
    bad = "You need a blocked account and good grades."        # omits both tokens
    good = "You need €11,904 in a block account and KCSE C+ grades."
    assert M.keyword_coverage(bad, facts) < 0.5
    assert M.keyword_coverage(good, facts) >= 0.5


# FM-04 — ungrounded fact (hallucination)
def test_fm04_ungrounded_fact():
    ctx = "DAAD stipend is €992 per month for STEM scholars."
    hallucinated = "The DAAD stipend is €1,500 per month."     # invented amount
    grounded = "The DAAD stipend is €992 per month."
    assert M.grounding_rate(hallucinated, ctx) < 1.0
    assert M.grounding_rate(grounded, ctx) == 1.0


# FM-05 — stale-data confidence
def test_fm05_stale_confidence():
    confident = "The deadline is 15 July and the amount is €11,904."
    disclaimed = ("The deadline is 15 July and the amount is €11,904 "
                  "(verify current status at the official source).")
    no_volatile = "Germany has many universities."
    assert M.staleness_disclaimer_rate(confident) == 0.0
    assert M.staleness_disclaimer_rate(disclaimed) == 1.0
    assert M.staleness_disclaimer_rate(no_volatile) == 1.0


# FM-06 — missing next step
def test_fm06_missing_next_step():
    assert M.next_step_rate("Good luck with your application.") == 0.0
    assert M.next_step_rate("Next step: apply at https://www2.daad.de") == 1.0


def test_metric_failure_map_is_complete():
    """Every failure mode FM-01..FM-06 has exactly one metric."""
    assert sorted(M.METRIC_FAILURE_MAP.values()) == [
        "FM-01", "FM-02", "FM-03", "FM-04", "FM-05", "FM-06"]
