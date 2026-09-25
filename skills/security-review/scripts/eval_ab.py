#!/usr/bin/env python3
"""Live A/B: the same reviewer with and without this skill, on the eight forward-eval fixtures.

    SECURITY_REVIEW_EVAL_CMD="$PWD/scripts/eval_live.sh" \\
      python3 scripts/eval_ab.py --out /path/to/run-dir [--workers 4] [--arms skill,control]

Why this exists: every live run before it graded the with-skill arm alone, so "the skill finds
more" had no baseline — the same gap the unit-test skill's A/B exposed, where both arms caught
the same bugs. Both arms are graded on one axis they can share without the skill's vocabulary,
`detection_outcome()` (true positive: the expected CWE is reported; false positive: the tested
class is not). The skill arm is additionally graded by the full `grade()`, which the control
cannot be — it was never shown the contract.

Outputs are written before grading, so a grader fix can be re-applied with `--grade-only`.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

TESTS = Path(__file__).resolve().parent / "tests"


def _load_harness():
    sys.path.insert(0, str(TESTS))
    spec = importlib.util.spec_from_file_location("sr_forward_eval", TESTS / "test_forward_eval.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def run_one(cmd: str, prompt: str, timeout: int) -> tuple[str, float, str]:
    started = time.monotonic()
    try:
        proc = subprocess.run(cmd, shell=True, input=prompt, capture_output=True, text=True,
                              timeout=timeout, errors="replace")
    except subprocess.TimeoutExpired:
        return "", time.monotonic() - started, "timeout"
    error = "" if proc.returncode == 0 else f"exit {proc.returncode}: {proc.stderr[-300:]}"
    if "Not logged in" in proc.stdout + proc.stderr:
        error = "not logged in (run outside the sandbox)"
    return proc.stdout, time.monotonic() - started, error


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--arms", default="skill,control")
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--grade-only", action="store_true")
    args = ap.parse_args()

    h = _load_harness()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    arms = [a for a in args.arms.split(",") if a]
    builders = {"skill": h.skill_prompt, "control": h.control_prompt}

    if not args.grade_only:
        cmd = os.environ.get("SECURITY_REVIEW_EVAL_CMD")
        if not cmd:
            print("set SECURITY_REVIEW_EVAL_CMD (e.g. scripts/eval_live.sh)", file=sys.stderr)
            return 2
        jobs = [(s, a) for s in h.SCENARIOS for a in arms]
        print(f"{len(jobs)} calls, arms={arms}, workers={args.workers}", flush=True)

        def job(pair):
            scenario, arm = pair
            fixture = h.load_fixture(h.SCENARIOS[scenario])
            text, secs, error = run_one(cmd, builders[arm](fixture), args.timeout)
            (out / f"{scenario}.{arm}.md").write_text(text, encoding="utf-8")
            (out / f"{scenario}.{arm}.meta.json").write_text(
                json.dumps({"seconds": round(secs, 1), "error": error, "chars": len(text)}),
                encoding="utf-8")
            return scenario, arm, secs, error

        with concurrent.futures.ThreadPoolExecutor(args.workers) as pool:
            for scenario, arm, secs, error in pool.map(job, jobs):
                print(f"  {scenario:44} {arm:8} {secs:6.0f}s {error}", flush=True)

    rows, incomplete = [], []
    for scenario, fixture_file in h.SCENARIOS.items():
        fixture = h.load_fixture(fixture_file)
        row = {"scenario": scenario,
               "polarity": "TP" if fixture.get("expected_finding", True) else "FP"}
        for arm in arms:
            path = out / f"{scenario}.{arm}.md"
            meta = out / f"{scenario}.{arm}.meta.json"
            error = json.loads(meta.read_text())["error"] if meta.exists() else "missing"
            if not path.exists() or error or not path.read_text(encoding="utf-8").strip():
                incomplete.append(f"{scenario}/{arm}: {error or 'empty output'}")
                continue
            text = path.read_text(encoding="utf-8")
            ok, detail = h.detection_outcome(text, fixture)
            row[f"{arm}_detection"] = ok
            row[f"{arm}_detail"] = detail
            if arm == "skill":
                passed, reasons = h.grade(text, fixture)
                row["skill_contract"] = passed
                row["skill_reasons"] = reasons
        rows.append(row)
    (out / "results.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")

    print(f"\n{'scenario':44} pol  " + "  ".join(f"{a}_det" for a in arms)
          + ("  skill_full" if "skill" in arms else ""))
    for r in rows:
        cells = "  ".join(f"{str(r.get(f'{a}_detection', '-')):>9}" for a in arms)
        full = f"  {str(r.get('skill_contract', '-')):>10}" if "skill" in arms else ""
        print(f"{r['scenario']:44} {r['polarity']}   {cells}{full}")
    for a in arms:
        graded = [r for r in rows if f"{a}_detection" in r]
        print(f"{a}: detection/suppression {sum(r[f'{a}_detection'] for r in graded)}"
              f"/{len(graded)}")
    if "skill" in arms:
        graded = [r for r in rows if "skill_contract" in r]
        print(f"skill: full grade (contract + calibration) {sum(r['skill_contract'] for r in graded)}"
              f"/{len(graded)}")
    if incomplete:
        print("INCOMPLETE — not graded:\n  " + "\n  ".join(incomplete))
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
