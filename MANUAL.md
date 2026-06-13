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

================================================================================
PART 9 — RUNNING WITH A REAL API KEY
================================================================================

Everything up to this point used the mock client — free, offline, deterministic.
This part covers switching to real Claude, what changes, what doesn't, and how to
watch the system perform on questions that have never been tested before.

────────────────────────────────────────────────────────────────────────────────
9.1  GET AND SET THE API KEY (do once, takes 3 minutes)
────────────────────────────────────────────────────────────────────────────────

STEP 1 — GET A KEY
  Go to: https://console.anthropic.com
  Sign in (or create a free account) → API Keys → Create Key
  Copy the key. It looks like: sk-ant-api03-...

STEP 2 — CREATE YOUR .env FILE
```bash
cp .env.example .env
```
  Open `.env` in any text editor. It looks like this:
  ```
  ANTHROPIC_API_KEY=
  AGENT_MODEL=claude-sonnet-4-20250514
  JUDGE_MODEL=claude-haiku-4-5-20251001
  ```
  Paste your key after `ANTHROPIC_API_KEY=` on the same line:
  ```
  ANTHROPIC_API_KEY=sk-ant-api03-your-key-here
  ```
  Save and close.

  NOTE: `.env` is in `.gitignore`. It will never be committed. Your key stays
  on your machine only.

STEP 3 — VERIFY THE KEY IS LIVE (costs ~1 API call)
```bash
python -c "
from src.llm_client import get_client
client, is_mock = get_client()
print('MOCK MODE' if is_mock else 'LIVE MODE — real API key found')
"
```
WHAT YOU SHOULD SEE:
  ```
  LIVE MODE — real API key found
  ```
  If you see `MOCK MODE`: the key is missing or has a leading/trailing space.
  Open `.env`, check the key is on the `ANTHROPIC_API_KEY=` line with no spaces.

  If you see `anthropic.AuthenticationError`: the key is invalid or expired.
  Go back to console.anthropic.com, create a new key, paste it in.

────────────────────────────────────────────────────────────────────────────────
9.2  ASK YOUR FIRST REAL QUESTION (2 API calls, ~3 seconds)
────────────────────────────────────────────────────────────────────────────────

```bash
make ask Q="How do I apply for the DAAD scholarship as a Kenyan?"
```

WHAT HAPPENS:
  Call 1 — categorize: Claude classifies the question → SCHOLARSHIP
  Call 2 — generate:   Claude reads the retrieved SOPs and writes a real answer

WHAT YOU SHOULD SEE:
```
  ✓  LIVE MODE — agent=claude-sonnet-4-20250514
                judge=claude-haiku-4-5-20251001 (pinned)

  → running...  done in 4.2s

  ════════════════════════════════════════════════════════════
  QUESTION
  How do I apply for the DAAD scholarship as a Kenyan?
  ════════════════════════════════════════════════════════════

  STEP 1 — CATEGORY DETECTED
  SCHOLARSHIP

  STEP 2 — SOPs RETRIEVED  (top_k=3)
  [ 5.12]  SOP_001  SOP-001: SCHOLARSHIP GUIDANCE & APPLICATIONS
  [ 3.24]  SOP_009  SOP-009: GERMAN LANGUAGE REQUIREMENTS & PATHWAYS
  [ 2.87]  SOP_003  SOP-003: UNDERGRADUATE & POSTGRADUATE STUDY ENROLLMENT

  STEP 3 — ANSWER
  ────────────────────────────────────────────────────────────
  DAAD offers several scholarships for Kenyan graduates...
  [prose answer, 150-300 words, grounded in SOP_001 content]
  ...Next step: apply via https://www2.daad.de
  ────────────────────────────────────────────────────────────

  AUTOMATIC METRICS  (no ground truth needed)
  grounding_rate              100%  ✓  every cited fact is in the retrieved SOPs
  staleness_disclaimer_rate   100%  ✓  volatile facts carry verify-at-source note
  next_step_rate              100%  ✓  answer ends with actionable link/contact

  LLM-AS-JUDGE  (model: claude-haiku-4-5-20251001)
  verdict: ✓ GOOD
  reason:  Answer directly addresses DAAD eligibility and cites €992 stipend.

  mode: LIVE  model=claude-sonnet-4-20250514
  trace: traces/trace_a1b2c3d4.json
```

HOW REAL ANSWERS DIFFER FROM MOCK ANSWERS:
  Mock: echoes fact tokens from retrieved text in a list (`- Key facts: DAAD, €992…`)
  Real: prose paragraphs that explain, connect ideas, include context and caveats

  The metrics and trace structure are IDENTICAL. Real mode doesn't change the
  plumbing — only what Claude returns as the answer.

────────────────────────────────────────────────────────────────────────────────
9.3  INTERACTIVE SESSION — MULTIPLE REAL QUESTIONS IN ONE GO
────────────────────────────────────────────────────────────────────────────────

This is the main way to explore real performance: ask several questions in a row
and see where the system shines and where it struggles.

```bash
make live
```

WHAT YOU SEE ON STARTUP:
```
  ✓  LIVE MODE — agent=claude-sonnet-4-20250514
                judge=claude-haiku-4-5-20251001 (pinned)

  Germany FAQ — live session  (type 'quit' or Ctrl+C to exit)
  Every answer + metrics printed here, full trace saved to traces/

  Question:
```

TYPE ANY QUESTION AND PRESS ENTER. Each question prints the full panel (category,
SOPs, answer, 3 automatic metrics, judge verdict). Then the prompt returns.

TO SAVE THE SESSION FOR LATER ANALYSIS:
```bash
make live -- --session user_pilot_june
```
This creates `data/sessions/user_pilot_june.csv` with one row per question:
timestamp, question, category, retrieved SOPs, grounding/staleness/next_step
scores, judge verdict and reason, and first 300 chars of the answer.

TO EXIT: type `quit`, or press Ctrl+C.

GOOD OPENING QUESTIONS TO TEST DIFFERENT CATEGORIES:
```
What scholarships can I get to study in Germany?             → SCHOLARSHIP
How do I apply for the nursing apprenticeship via SGAO?      → APPRENTICESHIP
What are the requirements to study in Germany?               → STUDY
What do I do first when I arrive in Germany?                 → SETTLEMENT
What is WIDU.africa and how does it work?                    → BUSINESS
Are there jobs in Germany I can apply for right now?         → JOB
What events does AG-Career Hub organise this year?           → EVENT
My KCSE grade is C+, I am 23 and my German is B1 —
what are my fastest options?                                 → complex, multi-SOP
```
The last question is deliberately hard (needs SOP_002 + SOP_009 + SOP_004). It
reliably shows the recall problem at top_k=3 — the answer will be thinner than
it should be. Raise top_k to fix it:
```bash
python -m src.live "My KCSE is C+, age 23, German B1 — fastest path to Germany?" \
  --top-k 5
```
Compare the two answers side by side. That is FM-01 made visible.

────────────────────────────────────────────────────────────────────────────────
9.4  RUNNING THE FULL EVAL SUITE WITH REAL MODELS
────────────────────────────────────────────────────────────────────────────────

The full 25-case eval suite with all three models (agent + judge):

```bash
make eval
```

WHAT HAPPENS:
  For each of the 25 test cases:
    Call 1 — categorize (agent model)
    Call 2 — generate   (agent model)
    Call 3 — judge      (judge model, pinned to claude-haiku-4-5-20251001)
  Total: 75 API calls, ~4-6 minutes, cost roughly $0.05-0.15.

WATCHING IT RUN (live in the terminal):
```
[ 1/25] recall=100% ground=100% What scholarships are available for studying i...
[ 2/25] recall=50%  ground=98%  How do I apply for the nursing apprenticeship ...
[ 3/25] recall=100% ground=100% What are the requirements to study in Germany ...
...
[25/25] recall=100% ground=100% I want to support a small chicken farm in Keny...
```
Watch for: recall < 100% is a retrieval miss (FM-01). Those rows deserve a
trace read after the run.

FINAL OUTPUT:
```
  sop_recall                   87.3%  FM-01
  category_accuracy            94.0%  FM-02
  keyword_coverage             78.4%  FM-03   ← real models score higher here
  grounding_rate               97.1%  FM-04
  staleness_disclaimer_rate    100.0%  FM-05
  next_step_rate               100.0%  FM-06
  judge_good_rate              80.0%
  COMPOSITE                    92.8%          ← will be higher than mock's 90.2%

Report -> reports/run_504a974_20260611T094532.json
```
Real keyword coverage will be higher than mock (real Claude elaborates; the mock
just echoes tokens). Judge good rate shows how often a real judge finds the real
answers satisfactory — the target is 80%+.

SKIPPING THE JUDGE TO SAVE COST:
```bash
python eval/run_eval.py --no-judge
```
Drops to 50 API calls. Use this during iteration; add the judge for a proper
before/after comparison.

────────────────────────────────────────────────────────────────────────────────
9.5  READING THE TRACES OF REAL RUNS
────────────────────────────────────────────────────────────────────────────────

Every real run saves a full trace to `traces/`. After a session or eval run:

```bash
ls -t traces/ | head -5              # most recent first
cat traces/trace_<id>.json | python -m json.tool | head -80
```

WHAT TO LOOK FOR IN A REAL TRACE:
```json
{
  "trace_id": "a1b2c3d4e5f6",
  "ts": "2026-06-11T09:45:32",
  "question": "How do I apply for the DAAD scholarship?",
  "config": {
    "model": "claude-sonnet-4-20250514",
    "top_k": 3,
    "prompts": { "generate": "generate_v2.txt" },  ← which prompt version
    "mock": false                                    ← confirms real mode
  },
  "steps": [
    { "step": "categorize", "category": "SCHOLARSHIP" },
    { "step": "retrieve",   "retrieved": [
        { "sop_id": "SOP_001", "score": 5.12 },
        { "sop_id": "SOP_009", "score": 3.24 }
      ]
    },
    { "step": "generate",   "answer": "DAAD offers several scholarships..." }
  ],
  "result": {
    "retrieved_context": "...full SOP text that was passed to Claude..."
  }
}
```

THREE THINGS TO CHECK IN EVERY SUSPICIOUS TRACE:
  1. Did the right SOP appear in `steps[1].retrieved`?
     If the answer is thin on scholarship details, check if SOP_001 scored
     highest. If it didn't, the BM25 query missed — FM-01.

  2. Is the answer consistent with `result.retrieved_context`?
     Read both side by side. Any fact in the answer that isn't in the context
     is a grounded_rate failure — FM-04.

  3. Does the prompt version in `config.prompts.generate` match what you expect?
     If you were testing generate_v2.txt but the trace shows v1, you forgot to
     pass the flag. The trace is ground truth on what actually ran.

────────────────────────────────────────────────────────────────────────────────
9.6  COST REFERENCE (so nothing surprises you)
────────────────────────────────────────────────────────────────────────────────

All figures are rough estimates at typical Anthropic pricing. Check
https://www.anthropic.com/pricing for current rates.

| Command | Agent calls | Judge calls | Total calls | Approx. cost |
|---|---|---|---|---|
| `make ask Q="..."` | 2 | 1 | 3 | <$0.01 |
| `make live` (5 questions) | 10 | 5 | 15 | <$0.05 |
| `make live` (20 questions) | 40 | 20 | 60 | ~$0.05–0.15 |
| `make eval` (25 cases, with judge) | 50 | 25 | 75 | ~$0.05–0.20 |
| `make eval --no-judge` | 50 | 0 | 50 | ~$0.03–0.10 |
| `python eval/run_eval.py --limit 5` | 10 | 5 | 15 | <$0.05 |

THE CHEAPEST REAL-MODE INNER LOOP:
```bash
python eval/run_eval.py --limit 5 --no-judge     # 10 calls, <$0.02
```
Use this when iterating on prompts. Run the full `make eval` only for a
proper before/after comparison.

TO SWITCH BACK TO FREE MOCK MODE AT ANY TIME:
```bash
# Option A — remove the key from .env
# Just delete the line or leave it blank: ANTHROPIC_API_KEY=

# Option B — unset for the current shell only
unset ANTHROPIC_API_KEY
make eval    # runs in mock mode immediately, no .env change
```
The system checks for the key at runtime. No other change is needed.

────────────────────────────────────────────────────────────────────────────────
9.7  TURNING REAL QUESTIONS INTO NEW TEST CASES
────────────────────────────────────────────────────────────────────────────────

The 25 test cases in `data/test_cases.csv` are the eval benchmark. Real
questions that reveal failures should graduate into that file so the failure
is regression-tested forever. Here is how.

STEP 1 — RUN A LIVE SESSION AND SPOT A WEAK ANSWER
```bash
make live -- --session pilot_1
```
Ask questions until the agent gives an answer that is incomplete, wrong, or
misses an important fact. Note the trace_id from the output.

STEP 2 — READ THAT TRACE
```bash
cat traces/trace_<id>.json | python -m json.tool
```
Identify: which SOPs were retrieved, which should have been retrieved, what
fact was missing from the answer.

STEP 3 — REVIEW THE SESSION LOG
```bash
cat data/sessions/pilot_1.csv
```
The CSV shows all questions with their automatic metric scores. Sort mentally
by `grounding_rate` < 1.0 (FM-04), `next_step_rate` = 0 (FM-06), or a judge
verdict of "partial" or "bad" — those are the candidates to promote.

STEP 4 — ADD THE QUESTION TO data/test_cases.csv
Open `data/test_cases.csv` and add one row. You need to fill in:

| Column | Where to get it | Example |
|---|---|---|
| `message` | The question you asked | "How long does it take to reach B2 German from B1?" |
| `complexity` | Your judgement | simple / medium / complex |
| `expected_category` | What the correct category is | APPRENTICESHIP |
| `expected_sops` | Which SOPs the answer NEEDS (from the SOP list) | SOP_002,SOP_009 |
| `expected_steps` | Key steps a good answer must cover | "1. B1→B2 takes 4-6 months…" |
| `key_facts` | Specific facts that must appear | "B2 certificate ≤1 year old. 4-6 months from B1." |
| `policy_details` | Important nuances/caveats | "Goethe-Institut Nairobi — book 2-3 months in advance." |

For `expected_sops`: open the SOPs in `data/sops/` and find which ones contain
the facts the question needs. SOP_009 covers all language timelines; SOP_002
covers nursing; SOP_001 covers scholarships, etc.

STEP 5 — VERIFY THE NEW CASE IMMEDIATELY
```bash
python eval/run_eval.py --limit 1     # will only run if your row is the last one
# or target it specifically:
python -c "
import pandas as pd
from src.agent import FAQAgent
from src import metrics as M
df = pd.read_csv('data/test_cases.csv')
row = df[df.message.str.contains('B2 German from B1')].iloc[0]
agent = FAQAgent()
trace = agent.answer(row['message'])
res = trace['result']
print('recalled:', M.sop_recall(row['expected_sops'].split(','), res['retrieved_sops']))
print('covered:', M.keyword_coverage(res['answer'], row['key_facts']))
"
```

STEP 6 — COMMIT THE NEW CASE
```bash
git add data/test_cases.csv
git commit -m "test: add real-user question — B1→B2 timeline (FM-01 regression)"
make eval    # the new case now runs in every future eval
```
The next eval report will contain this case, and its SHA will be in the
filename — so you can always trace which test cases existed when a given score
was produced.

────────────────────────────────────────────────────────────────────────────────
9.8  WHAT GOOD REAL-WORLD PERFORMANCE LOOKS LIKE
────────────────────────────────────────────────────────────────────────────────

These are the thresholds worth targeting, based on the failure mode taxonomy:

| Metric | Mock baseline | Real target | Danger zone |
|---|---|---|---|
| sop_recall | 85.7% | ≥ 90% | < 75% → top_k is too low |
| category_accuracy | 92.0% | ≥ 90% | < 80% → categorize prompt needs tuning |
| keyword_coverage | 64.2% | ≥ 80% | < 60% → retrieval or prompt gap |
| grounding_rate | 99.3% | ≥ 95% | < 90% → hallucination risk, check FM-04 |
| staleness_disclaimer_rate | 100% | 100% | < 90% → swap back to generate_v2.txt |
| next_step_rate | 100% | 100% | < 90% → prompt regression, check generate version |
| judge_good_rate | 72% (mock) | ≥ 75% | < 60% → answers are incomplete or wrong |
| COMPOSITE | 90.2% | ≥ 90% | < 75% → CI gate blocks merge |

IF A METRIC IS IN THE DANGER ZONE:
  sop_recall low         → increase top_k (try 5); check if category augmentation helps
  category_accuracy low  → read the wrong-category traces; edit categorize_v1.txt
  keyword_coverage low   → the answer exists but facts aren't in it; check retrieved_context
  grounding_rate low     → Claude invented something; add "never invent" to generate prompt
  staleness low          → check which generate_prompt version is in config.prompts.generate
  next_step low          → add a stronger "MUST include a link" instruction to the prompt
  judge_good low         → open the "bad" judge traces; find the pattern; document as new FM

The cycle is always: metric drops → read the traces → find the pattern →
document the failure mode → fix the cause → verify with `make eval` → commit.
