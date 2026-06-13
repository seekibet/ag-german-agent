.PHONY: agent traces eval test ci install

install:
	pip install -q -r requirements.txt

# Run the agent once with an example question (Q="..." to override)
Q ?= What scholarships are available for studying in Germany?
agent:
	python -m src.agent $(Q)

# Triage: rank the worst results from the latest eval report
traces:
	python -m src.triage --top 10

# Full eval suite -> reports/run_<git-sha>_<timestamp>.json
eval:
	python eval/run_eval.py --top-k 3

# Unit + regression tests (offline, mock client)
test:
	python -m pytest tests/ -q

# What CI runs: tests + gated eval (mock mode unless ANTHROPIC_API_KEY set)
ci: test
	python eval/run_eval.py --top-k 3 --fail-under 0.75

# Interactive live session (real questions, full trace + metrics per answer)
live:
	python -m src.live

# One-shot question: make ask Q="your question here"
ask:
	python -m src.live "$(Q)"
