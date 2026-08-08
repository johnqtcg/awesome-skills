#!/usr/bin/env python3
"""Rewrite the derived counts in COVERAGE.md from the code they describe.

Only the *derived* numbers are touched — per-suite collected counts, the offline total,
and every mutation-count mention. The rule table and fixture table stay hand-curated on
purpose: those carry judgement (what a rule is for, which defect a fixture is about) and
are asserted against the code by
``test_golden_scenarios.py::TestCoverageDocMatchesReality``.

Run after adding or removing tests:

    python3 scripts/tests/update_coverage_counts.py

Exits 1 when it changed something, so a CI step can treat "the doc was stale" as a
failure rather than silently rewriting it.
"""

from __future__ import annotations

import importlib.util
import pathlib
import re
import subprocess
import sys

TESTS_DIR = pathlib.Path(__file__).resolve().parent
SKILL_DIR = TESTS_DIR.parents[1]
COVERAGE = TESTS_DIR / "COVERAGE.md"
LIVE_MATRIX = "test_mongo_server_matrix.py"


def collected(suite: pathlib.Path) -> int:
    out = subprocess.run(
        [sys.executable, "-m", "pytest", str(suite), "--collect-only", "-q",
         "-p", "no:cacheprovider"],
        capture_output=True, text=True, cwd=str(SKILL_DIR))
    return sum(1 for ln in out.stdout.splitlines() if "::" in ln)


def _full_matrix_reachable() -> bool:
    """True when every supported major answers. Anything less and the live count would
    understate the coverage the document describes."""
    probe = subprocess.run([sys.executable, str(TESTS_DIR / "mongo_server.py")],
                           capture_output=True, text=True)
    if probe.returncode != 0:
        return False
    rows = [ln for ln in probe.stdout.splitlines()
            if ln.strip() and "UNREACHABLE" not in ln and "MISLABELLED" not in ln]
    import importlib.util
    spec = importlib.util.spec_from_file_location("ms_probe", TESTS_DIR / "mongo_server.py")
    ms = importlib.util.module_from_spec(spec)
    sys.modules["ms_probe"] = ms
    spec.loader.exec_module(ms)
    return len(rows) == len(ms.SUPPORTED)


def mutation_count() -> int:
    path = SKILL_DIR / "scripts" / "mutation_sweep.py"
    spec = importlib.util.spec_from_file_location("pg_mutation_sweep", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["pg_mutation_sweep"] = mod
    spec.loader.exec_module(mod)
    return len(mod.MUTATIONS)


def main() -> int:
    text = before = COVERAGE.read_text(encoding="utf-8")
    offline_total = 0

    for suite in sorted(TESTS_DIR.glob("test_*.py")):
        if suite.name == LIVE_MATRIX:
            # Environment-dependent: the count scales with how many servers are
            # reachable. Skipping it entirely was wrong in the other direction -- the
            # figure then never updated at all and drifted (104 stated, 108 collected)
            # every time a parametrised test was added. So: update it, but ONLY when a
            # full set of servers is up, and say plainly when it was left alone.
            n = collected(suite)
            full = _full_matrix_reachable()
            if not full:
                print(f"  {suite.name:32} {n} (NOT written: not every major reachable)")
                continue
            print(f"  {suite.name:32} {n} (full matrix)")
            text = re.sub(rf"(\| `{re.escape(suite.name)}` \| )\d+( \|)",
                          rf"\g<1>{n}\g<2>", text)
            text = re.sub(r"(servers are reachable: )\d+( across)", rf"\g<1>{n}\g<2>",
                          text)
            continue
        n = collected(suite)
        offline_total += n
        text = re.sub(rf"(\| `{re.escape(suite.name)}` \| )\d+( \|)",
                      rf"\g<1>{n}\g<2>", text)
        print(f"  {suite.name:32} {n}")

    text = re.sub(r"\*\*\d+ offline tests\*\*", f"**{offline_total} offline tests**", text)

    n_mut = mutation_count()
    text = re.sub(r"\b\d+(\s*)mutations\b", rf"{n_mut}\g<1>mutations", text)
    text = re.sub(r"\b\d+\s*/\s*\d+(\s+mutations\s+killed)",
                  rf"{n_mut}/{n_mut}\g<1>", text)

    print(f"  offline total                    {offline_total}")
    print(f"  mutations                        {n_mut}")

    if text == before:
        print("COVERAGE.md already current.")
        return 0
    COVERAGE.write_text(text, encoding="utf-8")
    print("COVERAGE.md updated — review the diff before committing.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
