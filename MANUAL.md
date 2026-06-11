# OPERATING MANUAL — Germany FAQ Agent
Version: 1.0
Audience: You, running this for the first time
Promise: **Nothing in this manual can break anything.** Every command is reversible,
every failure mode is documented below with its fix, and the entire system runs
offline by default — no API key, no cost, no risk.

================================================================================
PART 0 — WHY YOU CANNOT BREAK THIS
================================================================================

Read this first. It removes 90% of the fear.

| Fear | Reality |
|---|---|
| "I'll burn API credits" | Default mode is the **mock client** — zero API calls until you deliberately put a key in `.env`. You can run everything 1,000 times for free. |
| "I'll corrupt the data" | The SOPs and test cases are committed in git. `git checkout -- data/` restores them in one command. |
| "I'll break the code" | Same: `git checkout -- .` resets every tracked file to the last commit. The tag `v0.1.0-baseline` is a permanent snapshot — `git checkout v0.1.0-baseline` returns to the known-good state forever. |
| "A command will hang or loop" | Every command here finishes in under 60 seconds in mock mode. If anything seems stuck, `Ctrl+C` stops it cleanly — traces and reports are written atomically per file. |
| "I'll get a wall of errors" | The 5 errors you can realistically hit are listed in PART 6, each with its one-line fix. There are no others in normal operation. |
| "Deleting traces/reports loses something" | They are regenerable artifacts, gitignored on purpose. Delete them all (`rm traces/*.json reports/*.json`) any time — the next run recreates them. |

The worst case across this entire manual: you delete the folder and unzip it again.

================================================================================
PART 1 — FIRST-TIME SETUP (5 minutes, do once)
================================================================================

STEP 1 — UNZIP AND ENTER
```bash
unzip germany-faq-agent.zip
cd germany-faq-agent
```
WHAT YOU SHOULD SEE: a folder with `Makefile`, `src/`, `data/`, `prompts/`,
`tests/`, `eval/`, `failure_modes.md`. The `.git` history is included — run
`git log --oneline` and you'll see 11 commits ending at the README.

STEP 2 — INSTALL DEPENDENCIES
```bash
pip install -r requirements.txt
```
On some Linux systems pip refuses with "externally-managed-environment".
That is not an error in this project — it's your OS protecting system Python.
Fix (pick one):
```bash
pip install -r requirements.txt --break-system-packages     # quick
# or, cleaner:
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
```
WHAT YOU SHOULD SEE: pip finishing silently or with "Successfully installed…".
Five packages: anthropic, pandas, rank-bm25, python-dotenv, pytest.

STEP 3 — VERIFY THE INSTALL (your first safe command)
```bash
make test
```
WHAT YOU SHOULD SEE:
```
................                                                  [100%]
16 passed in 0.34s
```
16 dots = 16 tests = everything imports, the SOPs load, BM25 works, the mock
client is deterministic, the metrics behave. **If you see this, the system is
healthy.** This command is your health check forever — run it whenever in doubt.

STEP 4 — (OPTIONAL, SKIP ON DAY 1) ADD AN API KEY
Do NOT do this yet. Everything in Parts 2–5 works without it.
When you eventually want real Claude answers:
```bash
cp .env.example .env
# open .env in any editor, paste your key after ANTHROPIC_API_KEY=
```
To go back to free mode: delete the key from `.env` (or delete `.env`).
The code checks the key's presence at runtime — no other change needed.

================================================================================
PART 2 — YOUR FIRST RUN (2 minutes)
================================================================================

STEP 1 — ASK THE AGENT ONE QUESTION
```bash
make agent
```
WHAT HAPPENS INTERNALLY (visible in the output):
1. The question is categorized → `SCHOLARSHIP`
2. BM25 retrieves the 3 most relevant SOPs → `['SOP_001', ...]`
3. An answer is generated (mock mode: it deterministically echoes the facts
   found in the retrieved SOPs — that's why it looks list-like, not prose)
4. A full trace is saved → `traces/trace_<id>.json`

WHAT YOU SHOULD SEE (mock mode):
```
[SCHOLARSHIP] SOPs=['SOP_001', 'SOP_003', 'SOP_006']
Here is a direct answer based on the retrieved SOPs.
- Key facts: DAAD, KAS, IPS, €992, ...
...
trace -> traces/trace_a1b2c3d4e5f6.json
```

STEP 2 — ASK YOUR OWN QUESTION
```bash
make agent Q="How do I apply for the nursing apprenticeship via SGAO?"
```
Try a few. Watch the category and retrieved SOPs change. This is the fastest
way to build intuition for what the retriever does well and badly.

STEP 3 — OPEN A TRACE (this is the heart of the whole system)
```bash
cat traces/trace_*.json | head -50        # or open in any editor
```
WHAT YOU'RE LOOKING AT: the complete record of one run —
- `config`: model, top_k, **which prompt versions were used**, mock yes/no
- `steps[0]` categorize: what category was chosen
- `steps[1]` retrieve: which SOPs, with BM25 scores
- `steps[2]` generate: the full answer
Nothing about a run is hidden. When something goes wrong later, the trace is
where you look — never guess, always read the trace.

================================================================================
PART 3 — RUNNING THE EVAL (the main loop, 3 minutes)
================================================================================

STEP 1 — RUN THE FULL SUITE
```bash
make eval
```
WHAT HAPPENS: all 25 test cases from `data/test_cases.csv` run through the
agent. Each gets scored on 6 metrics + an LLM-judge verdict. A report is
written to `reports/run_<git-sha>_<timestamp>.json`.

WHAT YOU SHOULD SEE (last lines):
```
  sop_recall                   85.7%  FM-01
  category_accuracy            92.0%  FM-02
  keyword_coverage             64.2%  FM-03
  grounding_rate               99.3%  FM-04
  staleness_disclaimer_rate    100.0%  FM-05
  next_step_rate               100.0%  FM-06
  judge_good_rate              72.0%
  COMPOSITE                    90.2%
Report -> reports/run_504a974_20260611T232746.json
```

HOW TO READ EACH LINE (each metric = one documented failure mode):
| Line | Plain-English question it answers | Where it's documented |
|---|---|---|
| sop_recall | Did retrieval fetch the SOPs this answer needs? | failure_modes.md FM-01 |
| category_accuracy | Did the router pick the right category? | FM-02 |
| keyword_coverage | Are the critical facts (€ amounts, acronyms) in the answer? | FM-03 |
| grounding_rate | Is every fact in the answer backed by retrieved text (no hallucination)? | FM-04 |
| staleness_disclaimer_rate | Are volatile facts (deadlines, amounts) flagged "verify at source"? | FM-05 |
| next_step_rate | Does every answer end with an actionable link/contact? | FM-06 |

The report filename contains the git SHA — six months from now you can match
any report to the exact code that produced it.

STEP 2 — TRIAGE THE WORST RESULTS
```bash
make traces
```
WHAT YOU SHOULD SEE: the 10 worst cases, worst first, each with:
- which metrics failed and by how much
- which SOPs were missing (→ FM-01)
- the path to the full trace JSON

This is intentionally opinionated: recall failures are weighted 3×, because a
retrieval miss caps everything downstream — the generator cannot cite a fact
it never saw. Fix retrieval problems first, always.

STEP 3 — THE FULL IMPROVEMENT LOOP (what to do with a bad trace)
This is the workflow the entire repo is built around:
```
1. make eval                      → see aggregate scores
2. make traces                    → find the worst case
3. cat traces/trace_<id>.json     → read what actually happened
4. Diagnose: which failure mode?  → check the table in failure_modes.md
5a. Known mode (FM-01..06)?       → fix the agent (see Part 4)
5b. NEW kind of failure?          → add FM-07 to failure_modes.md FIRST,
                                    then a metric in src/metrics.py,
                                    then a regression test in tests/test_metrics.py
6. make ci                        → confirm composite still clears the gate
7. git commit                     → the next report's filename carries your new SHA
```
The taxonomy-first rule (5b) is the discipline that keeps this honest:
no fix without a documented failure mode, no failure mode without a test.

================================================================================
PART 4 — SAFE EXPERIMENTS (each takes <2 minutes, all reversible)
================================================================================

EXPERIMENT 1 — SEE top_k FIX RECALL (the FM-01 demo)
```bash
python eval/run_eval.py --top-k 3 --no-judge     # baseline
python eval/run_eval.py --top-k 5 --no-judge     # wider retrieval
```
WHAT TO LOOK FOR: `sop_recall` rises at top_k=5. The complex multi-SOP cases
(the lawyer question, the B1-nursing question) are the ones that improve —
they need 3–4 SOPs and top_k=3 physically cannot fetch them all.
LESSON: retrieval breadth is the cheapest quality lever in the system.

EXPERIMENT 2 — WATCH A PROMPT REGRESSION GET CAUGHT (the FM-05 demo)
```bash
python eval/run_eval.py --generate-prompt generate_v1.txt --no-judge
```
WHAT TO LOOK FOR: `staleness_disclaimer_rate` drops (v1 lacks the
"verify at source" rule that v2 added). This is the prompt-versioning payoff:
an old prompt version produces a measurably worse score on the exact metric
its successor was written to fix. Roll forward:
```bash
python eval/run_eval.py --generate-prompt generate_v2.txt --no-judge
```
and the metric recovers. You just watched the eval suite catch a regression.

EXPERIMENT 3 — RUN A FAST PARTIAL SUITE WHILE ITERATING
```bash
python eval/run_eval.py --limit 5 --no-judge
```
Five cases, no judge calls — sub-second in mock mode. Use this as your inner
loop; run the full `make eval` only before committing.

EXPERIMENT 4 — DELIBERATELY FAIL THE CI GATE (so it never surprises you)
```bash
python eval/run_eval.py --fail-under 0.99
```
WHAT YOU SHOULD SEE: the suite runs normally, prints scores, then:
```
FAIL: composite 0.902 < gate 0.99
```
and exits with code 1. That exit code is exactly what fails a PR in CI.
Nothing is damaged — the report was still written. Reset nothing; just rerun
with the real gate (0.75) or none.

EXPERIMENT 5 — EDIT A PROMPT AND MEASURE THE EFFECT
```bash
cp prompts/generate_v2.txt prompts/generate_v3.txt
# edit generate_v3.txt — e.g. demand a "Requirements:" section
python eval/run_eval.py --generate-prompt generate_v3.txt --no-judge
```
Worse scores? `rm prompts/generate_v3.txt` — v2 was never touched. Better?
Commit v3. **Never edit v1/v2 in place** — append-only versions are what make
old eval reports interpretable.

================================================================================
PART 5 — GOING LIVE WITH REAL MODELS (when you're ready)
================================================================================

STEP 1 — Put your key in `.env` (Part 1, Step 4). That's the only change.

STEP 2 — Budget before you run (so cost is never a surprise):
| Command | API calls (approx) | Notes |
|---|---|---|
| `make agent` | 2 | categorize + generate |
| `make eval` | 75 | 25 × (categorize + generate + judge) |
| `make eval` with `--no-judge` | 50 | drops the judge calls |
| `--limit 5 --no-judge` | 10 | recommended first real run |

STEP 3 — First real run, small:
```bash
python eval/run_eval.py --limit 5
```
Real answers will be prose (unlike the mock's fact-echo) and `keyword_coverage`
typically rises. The judge runs on the **pinned** model
(`claude-haiku-4-5-20251001`) regardless of what agent model you use — that
pinning is why scores from today remain comparable after you upgrade the agent
next quarter.

STEP 4 — CI with real models: add `ANTHROPIC_API_KEY` as a GitHub repo secret.
The same workflow file silently upgrades from mock to real. Without the secret,
CI runs in mock mode — free and deterministic.

================================================================================
PART 6 — EVERY ERROR YOU CAN REALISTICALLY HIT (and its one-line fix)
================================================================================

E-1: `ModuleNotFoundError: No module named 'rank_bm25'` (or pandas/anthropic)
  → Dependencies not installed in the Python you're running.
  → FIX: `pip install -r requirements.txt --break-system-packages`
    (or activate your venv: `source .venv/bin/activate`)

E-2: `error: externally-managed-environment` during pip install
  → OS-protected system Python; cosmetic, not project-related.
  → FIX: add `--break-system-packages`, or use a venv (Part 1, Step 2).

E-3: `FileNotFoundError: No SOPs found in data/sops/`
  → You're running from the wrong directory.
  → FIX: `cd germany-faq-agent` (all commands assume the repo root).

E-4: `No reports found. Run: make eval` (from `make traces`)
  → Triage needs at least one report to rank.
  → FIX: literally what it says — `make eval` first.

E-5: `anthropic.AuthenticationError` / 401
  → A key is present in `.env` but invalid or expired.
  → FIX: correct the key, or delete it to fall back to free mock mode.
    The system never half-works: valid key = real, no key = mock.

If you hit anything not on this list: `make test`. If the 16 tests pass, the
code is fine and the issue is environmental (directory, venv, key). If a test
fails, `git status` will show what changed — `git checkout -- <file>` reverts it.

================================================================================
PART 7 — PANIC BUTTONS (total reset, in escalating order)
================================================================================

LEVEL 1 — "My run artifacts are messy"
```bash
rm -f traces/*.json reports/*.json
```
Always safe. These are regenerable outputs, never inputs.

LEVEL 2 — "I edited code/prompts/data and regret it"
```bash
git status                 # see what you changed
git checkout -- <file>     # revert one file
git checkout -- .          # revert everything tracked
```

LEVEL 3 — "I want the exact known-good starting point"
```bash
git stash                          # shelve your changes (recoverable!)
git checkout v0.1.0-baseline       # the tagged baseline snapshot
make test                          # 16 passed → you're home
git checkout main                  # ...and back to the latest when ready
```

LEVEL 4 — "Burn it down"
Delete the folder. Unzip again. Sixty seconds, including `make test`.

================================================================================
PART 8 — DAILY DRIVER REFERENCE CARD
================================================================================

```bash
make test       # health check — 16 tests, <1s, run whenever unsure
make agent      # one question (Q="..." to override)
make eval       # full 25-case suite → sha-stamped report
make traces     # triage: worst results first, with trace paths
make ci         # what CI runs: tests + eval gated at --fail-under 0.75

python eval/run_eval.py --limit 5 --no-judge          # fast inner loop
python eval/run_eval.py --top-k 5                     # retrieval experiment
python eval/run_eval.py --generate-prompt generate_v1.txt   # prompt A/B
python -m src.triage reports/run_<sha>_<ts>.json --top 5    # triage old report
```

THE ONE-PARAGRAPH MENTAL MODEL:
The agent answers questions in three traced steps (categorize → retrieve →
generate). The eval scores every answer against ground truth on six metrics,
each mapping to one documented failure mode with its own regression test.
Triage shows you the worst traces; the taxonomy tells you what kind of failure
you're looking at; prompts are versioned so fixes are measurable and
reversible; reports are SHA-stamped so results are tied to commits; and the
mock client means every part of this loop is free until you decide otherwise.

You cannot break it. Run it.
