# Failure Mode Taxonomy (living document)

Every metric in `src/metrics.py` maps to exactly one failure mode here.
Every failure mode has a regression test in `tests/test_metrics.py`.
When a new failure is observed in triage (`make traces` → `python -m src.triage`),
add it here FIRST, then write the metric, then the regression test.

| ID | Failure mode | Observed example | Metric | Regression test |
|----|--------------|------------------|--------|-----------------|
| FM-01 | **Retrieval miss** — a required SOP is not in the retrieved set, so the answer cannot contain its facts | "B1 to B2 nursing path" missed SOP_009 at top_k=3 | `sop_recall` | `test_fm01_retrieval_miss` |
| FM-02 | **Category misroute** — question routed to wrong category, degrading BM25 query augmentation | "degree recognition" routed STUDY vs SCHOLARSHIP | `category_accuracy` | `test_fm02_category_misroute` |
| FM-03 | **Fact omission** — relevant SOP retrieved but key fact (€ amount, deadline, acronym) absent from answer | answer omitted "€11,904" block account figure | `keyword_coverage` | `test_fm03_fact_omission` |
| FM-04 | **Ungrounded fact** — answer contains a € amount / year not present in any retrieved SOP (hallucination) | invented "€1,500 stipend" | `grounding_rate` | `test_fm04_ungrounded_fact` |
| FM-05 | **Stale-data confidence** — answer states a volatile fact (deadline, amount) without a verify-at-source disclaimer | quoted 2025 deadline as if permanent | `staleness_disclaimer_rate` | `test_fm05_stale_confidence` |
| FM-06 | **Missing next step** — answer ends without an actionable link/contact, violating the FAQ contract | no URL or contact in WIDU answer | `next_step_rate` | `test_fm06_missing_next_step` |

## Adding a new failure mode
1. Paste the offending trace ID + excerpt under "Observed example".
2. Implement the metric in `src/metrics.py` (pure function, no API calls).
3. Add a regression test that FAILS on the bad trace and PASSES on a fixed one.
4. Wire the metric into `eval/run_eval.py` aggregation.
