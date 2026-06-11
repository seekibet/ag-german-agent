"""Triage CLI: rank the worst eval results so failures are reviewed first.

Usage:
  python -m src.triage                      # latest report in reports/
  python -m src.triage reports/run_X.json   # specific report
  python -m src.triage --top 5
"""
import argparse
import glob
import json
import os
import sys


def severity(row: dict) -> float:
    """Lower = worse. Weighted: recall failures dominate (they cap everything
    downstream), then grounding (hallucination), then coverage."""
    return (3.0 * row.get("sop_recall", 0)
            + 2.0 * row.get("grounding_rate", 0)
            + 1.5 * row.get("keyword_coverage", 0)
            + 1.0 * row.get("category_accuracy", 0)
            + 0.5 * row.get("staleness_disclaimer_rate", 0)
            + 0.5 * row.get("next_step_rate", 0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("report", nargs="?", default=None)
    ap.add_argument("--top", type=int, default=10)
    args = ap.parse_args()

    path = args.report
    if path is None:
        reports = sorted(glob.glob("reports/run_*.json"))
        if not reports:
            sys.exit("No reports found. Run: make eval")
        path = reports[-1]

    with open(path, encoding="utf-8") as f:
        report = json.load(f)

    rows = sorted(report["results"], key=severity)[: args.top]

    print(f"\nTRIAGE — worst {len(rows)} of {len(report['results'])} "
          f"({os.path.basename(path)})")
    print("=" * 100)
    for i, r in enumerate(rows, 1):
        print(f"\n#{i}  severity={severity(r):.2f}  "
              f"recall={r['sop_recall']:.0%} ground={r['grounding_rate']:.0%} "
              f"kw={r['keyword_coverage']:.0%} cat={'OK' if r['category_accuracy'] else 'MISS'} "
              f"judge={r.get('judge_verdict','-')}")
        print(f"    Q: {r['question'][:85]}")
        if r.get("missing_sops"):
            print(f"    missing SOPs: {r['missing_sops']}  -> FM-01")
        if r["grounding_rate"] < 1.0:
            print(f"    ungrounded facts present -> FM-04")
        print(f"    trace: {r.get('trace_path','-')}")
    print("\nNext: open the trace JSON, identify the failure mode, "
          "update failure_modes.md, add a regression test.")


if __name__ == "__main__":
    main()
