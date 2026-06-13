# Germany FAQ Agent — Eval-Driven Development Scaffold

RAG FAQ assistant for Kenyans exploring opportunities in Germany, built
**eval-first**: every component exists to make failures observable, measurable,
and regression-tested.

## Architecture

```
question -> [categorize] -> [BM25 retrieve over 9 SOPs] -> [generate] -> answer
                |                    |                          |
                └──────────── full JSON trace ──────────────────┘
                                     |
                  eval/run_eval.py -> reports/run_<sha>_<ts>.json
                                     |
                  src/triage.py ranks worst -> failure_modes.md -> new metric + test
```

## Quick start (offline — no API key needed)

```bash
make install
make test     # 13 tests, all offline via deterministic mock
make eval     # full 25-case eval suite -> reports/run_<sha>_<ts>.json
make traces   # triage: worst results first
make agent Q="How do I apply for the SGAO nursing programme?"
```

Set `ANTHROPIC_API_KEY` in `.env` to switch from the mock to real models:
- Agent model: `claude-sonnet-4-6` (swappable)
- Judge model: `claude-haiku-4-5-20251001` (**pinned** — never auto-upgrades,
  so scores stay comparable across agent changes)

## The eval-driven loop

1. `make eval` — every case produces metrics + a trace
2. `make traces` — triage ranks the worst traces (recall failures weighted highest)
3. Open the trace JSON, identify the failure mode
4. Document it in `failure_modes.md` (FM-07, FM-08, …)
5. Write the metric in `src/metrics.py` + a regression test in `tests/test_metrics.py`
6. Fix the agent (new prompt version in `prompts/`, retrieval change, etc.)
7. `make ci` — gate composite score with `--fail-under`

## Repository layout

| Path | Purpose |
|---|---|
| `prompts/` | Versioned prompt files (`generate_v1` → `v2` added staleness disclaimers) |
| `data/sops/` | 9 SOPs (~15.7k words) — the knowledge base |
| `data/test_cases.csv` | 25 grounded cases: expected SOPs, key facts, policy details |
| `failure_modes.md` | Living taxonomy — every metric maps to one FM-NN entry |
| `src/metrics.py` | 6 pure-function metrics, one per failure mode |
| `src/judge.py` | LLM-as-judge, pinned model + versioned rubric |
| `src/tracing.py` | Full JSON trace per run in `traces/` |
| `src/triage.py` | CLI ranking worst eval results |
| `eval/run_eval.py` | Suite runner, `--fail-under` gate, sha-stamped reports |
| `tests/` | 13 tests incl. one regression test per failure mode |
| `.github/workflows/ci.yml` | tests + gated eval on every PR |

## Metrics ↔ failure modes

| Metric | Failure mode | Question it answers |
|---|---|---|
| `sop_recall` | FM-01 retrieval miss | Did we fetch the SOPs the answer needs? |
| `category_accuracy` | FM-02 misroute | Did routing help or hurt retrieval? |
| `keyword_coverage` | FM-03 fact omission | Are the critical facts in the answer? |
| `grounding_rate` | FM-04 hallucination | Is every fact in the answer backed by retrieved text? |
| `staleness_disclaimer_rate` | FM-05 stale confidence | Are volatile facts flagged as verify-at-source? |
| `next_step_rate` | FM-06 missing next step | Does the answer end with an action? |

## Why a deterministic mock?

`src/llm_client.py:MockClient` makes the whole pipeline — agent, judge, eval,
CI — run offline with zero keys and byte-identical outputs. CI stays free and
flake-free; the same `--fail-under` gate applies to real models when the
secret is configured.

## Web interface (end users + AG personnel)

Two surfaces over one FastAPI backend that wraps the same `FAQAgent`:

```bash
make serve         # http://localhost:8000
```

| URL | Audience | Purpose |
|---|---|---|
| `/` | End users (Kenyans/diaspora) | Calm Q&A chat — ask, get a grounded answer with its source SOPs, rate it |
| `/admin` | AG-Career Hub personnel | Live ops console — stats, every question logged, flagged-for-review queue, in-place SOP editor with one-click reindex |

The admin console is gated by `ADMIN_TOKEN` (default `ag-admin-dev`, set your own
in `.env`). The server runs in demo/mock mode with no API key, or live answers
once `ANTHROPIC_API_KEY` is set — identical to the CLI.

### API endpoints
Public: `POST /api/ask`, `POST /api/feedback`
Admin (header `X-Admin-Token`): `/api/admin/stats`, `/questions`, `/flagged`,
`/trace/{id}`, `/sops`, `GET|PUT /sops/{id}`, `POST /reindex`

Every answered question is appended to `data/qa_log.jsonl` with its three
ground-truth-free metrics (grounding, staleness disclaimer, next-step) so
personnel can monitor live quality. Each question also writes a full trace to
`traces/`, viewable in the admin drawer.
