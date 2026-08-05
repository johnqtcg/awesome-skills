#!/usr/bin/env python3
"""Aggregate live-eval results at CHECK level and emit a machine-readable summary.

Scenario counts are too coarse to show whether the skill helps: two arms can fail the
same two scenarios while one fails 3 checks and the other 15. This reads the per-scenario
JSON that `grade_postmortem_eval.py --json` writes, prints both levels, and stores
`summary.json` so two arms can be diffed without re-reading transcripts.

Usage:
  summarize_eval.py <result_dir> --arm ARM --measured N --failed N
  summarize_eval.py --diff <baseline_summary.json> <candidate_summary.json>

Exit codes: 0 = summary written (or diff printed), 2 = nothing to summarize.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BAR = "=" * 52


def load_rows(result_dir: Path) -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8"))
            for p in sorted(result_dir.glob("*.json")) if p.name != "summary.json"]


def summarize(result_dir: Path, arm: str, measured: int, failed: int) -> int:
    rows = load_rows(result_dir)
    if not rows:
        print(f"nothing to summarize in {result_dir}", file=sys.stderr)
        return 2
    total = sum(r["checks_total"] for r in rows)
    passed = sum(r["checks_passed"] for r in rows)
    summary = {
        "arm": arm,
        "scenarios_measured": measured,
        "scenarios_passed": measured - failed,
        "scenarios_failed": failed,
        "checks_total": total,
        "checks_passed": passed,
        "checks_failed": total - passed,
        "per_scenario": [
            {"scenario": r["scenario"], "checks_total": r["checks_total"],
             "checks_passed": r["checks_passed"], "checks_failed": r["checks_failed"],
             "failed_checks": [c["check"] for c in r["failed_checks"]]}
            for r in rows
        ],
    }
    out = result_dir / "summary.json"
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")

    print(BAR)
    print(f"  arm:                {arm}")
    print(f"  scenarios measured: {measured}")
    print(f"  scenarios passed:   {measured - failed}")
    print(f"  scenarios failed:   {failed}")
    print(f"  checks passed:      {passed}/{total}")
    print(f"  checks failed:      {total - passed}")
    print(BAR)
    for r in summary["per_scenario"]:
        mark = "ok  " if r["checks_failed"] == 0 else "FAIL"
        print(f"  [{mark}] {r['scenario']:32} {r['checks_passed']}/{r['checks_total']}")
        for c in r["failed_checks"]:
            print(f"           - {c}")
    print()
    print(f"  machine-readable summary: {out}")
    return 0


def diff(baseline: Path, candidate: Path) -> int:
    """Per-scenario check delta between two arms — the comparison the runner asks for."""
    a = json.loads(baseline.read_text(encoding="utf-8"))
    b = json.loads(candidate.read_text(encoding="utf-8"))
    by_a = {r["scenario"]: r for r in a["per_scenario"]}
    by_b = {r["scenario"]: r for r in b["per_scenario"]}

    print(BAR)
    print(f"  baseline:  {a['arm']}  ({a['checks_failed']} checks failed)")
    print(f"  candidate: {b['arm']}  ({b['checks_failed']} checks failed)")
    print(BAR)
    for name in sorted(set(by_a) | set(by_b)):
        fa = by_a.get(name, {}).get("checks_failed")
        fb = by_b.get(name, {}).get("checks_failed")
        if fa is None or fb is None:
            print(f"  {name:32} only in one arm — not comparable")
            continue
        delta = fb - fa
        sign = "better" if delta < 0 else ("worse" if delta > 0 else "same  ")
        print(f"  {name:32} {fa:>3} -> {fb:>3}  ({sign} {delta:+d})")
    print(BAR)
    net = b["checks_failed"] - a["checks_failed"]
    verdict = ("candidate fails fewer checks — the skill helped" if net < 0 else
               "no improvement in failed checks" if net == 0 else
               "candidate fails MORE checks — the skill hurt")
    print(f"  net check delta: {net:+d} — {verdict}")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result_dir", nargs="?")
    parser.add_argument("--arm", default="unknown")
    parser.add_argument("--measured", type=int, default=0)
    parser.add_argument("--failed", type=int, default=0)
    parser.add_argument("--diff", nargs=2, metavar=("BASELINE", "CANDIDATE"))
    args = parser.parse_args(argv)
    if args.diff:
        return diff(Path(args.diff[0]), Path(args.diff[1]))
    if not args.result_dir:
        parser.error("result_dir is required unless --diff is given")
    return summarize(Path(args.result_dir), args.arm, args.measured, args.failed)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
