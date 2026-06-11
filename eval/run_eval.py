"""Eval runner. Produces reports/run_<git-sha>_<timestamp>.json so every
result is tied to a commit. Exits non-zero if --fail-under gate not met.

Usage:
  python eval/run_eval.py                          # full suite, mock or real
  python eval/run_eval.py --fail-under 0.80        # CI gate on composite score
  python eval/run_eval.py --top-k 5 --no-judge
"""
import argparse
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402

from src.agent import FAQAgent  # noqa: E402
from src.judge import Judge  # noqa: E402
from src import metrics as M  # noqa: E402


def git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "nogit"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default="data/test_cases.csv")
    ap.add_argument("--top-k", type=int, default=3)
    ap.add_argument("--generate-prompt", default="generate_v2.txt")
    ap.add_argument("--fail-under", type=float, default=None,
                    help="exit 1 if composite score below this")
    ap.add_argument("--no-judge", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    cases = pd.read_csv(args.cases)
    if args.limit:
        cases = cases.head(args.limit)

    agent = FAQAgent(top_k=args.top_k, generate_prompt=args.generate_prompt)
    judge = None if args.no_judge else Judge()

    results = []
    for i, row in cases.iterrows():
        q = row["message"]
        expected_sops = [s.strip() for s in str(row["expected_sops"]).split(",")]
        trace = agent.answer(q)
        res = trace["result"]

        rec = M.sop_recall(expected_sops, res["retrieved_sops"])
        ret_norm = {M.normalize_sop_name(s) for s in res["retrieved_sops"]}
        missing = sorted({M.normalize_sop_name(s) for s in expected_sops} - ret_norm)

        out = {
            "question": q,
            "complexity": row["complexity"],
            "expected_category": row["expected_category"],
            "got_category": res["category"],
            "expected_sops": ",".join(expected_sops),
            "retrieved_sops": ",".join(res["retrieved_sops"]),
            "missing_sops": ",".join(missing),
            "sop_recall": rec,
            "category_accuracy": M.category_accuracy(
                row["expected_category"], res["category"]),
            "keyword_coverage": M.keyword_coverage(
                res["answer"], row.get("key_facts", "")),
            "grounding_rate": M.grounding_rate(
                res["answer"], res["retrieved_context"]),
            "staleness_disclaimer_rate": M.staleness_disclaimer_rate(res["answer"]),
            "next_step_rate": M.next_step_rate(res["answer"]),
            "trace_path": trace.get("trace_path", ""),
        }
        if judge:
            v = judge.judge(q, res["answer"],
                            str(row.get("key_facts", "")),
                            str(row.get("policy_details", "")))
            out["judge_verdict"] = v["verdict"]
            out["judge_reason"] = v["reason"]
        results.append(out)
        print(f"[{i+1:2}/{len(cases)}] recall={rec:.0%} "
              f"ground={out['grounding_rate']:.0%} {q[:55]}")

    df = pd.DataFrame(results)
    agg = {m: round(float(df[m].mean()), 4) for m in M.METRIC_FAILURE_MAP}
    if judge:
        agg["judge_good_rate"] = round(
            float((df["judge_verdict"] == "good").mean()), 4)
    composite = round(sum(agg[m] for m in M.METRIC_FAILURE_MAP)
                      / len(M.METRIC_FAILURE_MAP), 4)

    report = {
        "git_sha": git_sha(),
        "timestamp": time.strftime("%Y%m%dT%H%M%S"),
        "config": {"top_k": args.top_k,
                   "generate_prompt": args.generate_prompt,
                   "agent_model": agent.model,
                   "judge_model": judge.model if judge else None,
                   "mock_mode": agent.is_mock,
                   "n_cases": len(cases)},
        "aggregate": agg,
        "composite_score": composite,
        "results": results,
    }
    os.makedirs("reports", exist_ok=True)
    out_path = f"reports/run_{report['git_sha']}_{report['timestamp']}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    for k, v in agg.items():
        fm = M.METRIC_FAILURE_MAP.get(k, "")
        print(f"  {k:<28} {v:.1%}  {fm}")
    print(f"  {'COMPOSITE':<28} {composite:.1%}")
    print(f"\nReport -> {out_path}")

    if args.fail_under is not None and composite < args.fail_under:
        print(f"\nFAIL: composite {composite:.3f} < gate {args.fail_under}")
        sys.exit(1)


if __name__ == "__main__":
    main()
