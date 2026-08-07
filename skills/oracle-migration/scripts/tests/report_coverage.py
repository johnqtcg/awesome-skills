#!/usr/bin/env python3
"""Report — and verify — the counts cited in COVERAGE.md.

Hand-maintained totals in a coverage document drift within a couple of changes and then
misrepresent the suite, which is worse than having no number at all. This script derives
every count from the code and fixtures, and `--check` fails when COVERAGE.md disagrees.

Usage:
    python3 scripts/tests/report_coverage.py            # print live counts
    python3 scripts/tests/report_coverage.py --check    # exit 1 if COVERAGE.md drifted
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import re
import sys

TESTS_DIR = pathlib.Path(__file__).resolve().parent
SKILL_DIR = TESTS_DIR.parents[1]
GOLDEN_DIR = TESTS_DIR / "golden"
COVERAGE_MD = TESTS_DIR / "COVERAGE.md"


def _load(name: str, path: pathlib.Path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def lint_check_count(lint) -> int:
    return len(lint.CHECKS)


def collect() -> dict:
    lint = _load("oracle_lint_migration", SKILL_DIR / "scripts" / "lint_migration.py")
    sweep = _load("oracle_mutation_sweep", SKILL_DIR / "scripts" / "mutation_sweep.py")

    fixtures = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(GOLDEN_DIR.glob("*.json"))]
    contract_src = (TESTS_DIR / "test_skill_contract.py").read_text(encoding="utf-8")

    guards_block = re.search(r"FACT_GUARDS = \[(.*?)\n\]", contract_src, re.S)
    guard_count = guards_block.group(1).count("\n    (") if guards_block else 0

    # Server probes. COVERAGE.md quotes this number in prose, and prose is exactly where
    # a count rots unnoticed — it drifted 12 -> 14 while --check still reported clean,
    # because nothing derived it.
    harness_src = (SKILL_DIR / "scripts" / "verify_against_server.sh").read_text(
        encoding="utf-8"
    )
    probe_block = re.search(r"PROBE_EOF'\n(.*?)\nPROBE_EOF", harness_src, re.S)
    probe_count = (
        len([ln for ln in probe_block.group(1).splitlines() if ln.strip()])
        if probe_block
        else 0
    )

    groups: dict = {}
    for m in sweep.M:
        groups[m.mid[0]] = groups.get(m.mid[0], 0) + 1

    # The L group has two halves: L01–L25 disable one check each, everything above is
    # gating/calibration. Deriving the split from the ids keeps it correct as the group
    # grows; a hard-coded offset silently mislabels both rows after the first addition.
    l_nums = sorted(int(m.mid[1:]) for m in sweep.M if m.mid.startswith("L"))
    n_checks = lint_check_count(lint)
    per_check_nums = [n for n in l_nums if n <= n_checks]
    calib_nums = [n for n in l_nums if n > n_checks]
    per_check = len(per_check_nums)
    calibration = len(calib_nums)

    return {
        "checks": len(lint.CHECKS),
        "fixtures": len(fixtures),
        "by_type": {
            t: sum(1 for f in fixtures if f["type"] == t)
            for t in ("defect", "good_practice", "degradation_scenario", "workflow")
        },
        "fact_guards": guard_count,
        "server_probes": probe_count,
        "mutations": len(sweep.M),
        "mutation_groups": groups,
        "mutation_L_per_check": per_check,
        "mutation_L_calibration": calibration,
        # Real endpoints, not checks+1: the calibration block is numbered from a gap so
        # the per-check ids stay aligned with the ORA<nn> codes.
        "mutation_L_per_check_range": (per_check_nums[0], per_check_nums[-1]) if per_check_nums else (0, 0),
        "mutation_L_calib_range": (calib_nums[0], calib_nums[-1]) if calib_nums else (0, 0),
        "fixtures_with_detail_assertions": sum(
            1 for f in fixtures if f.get("lint_detail_must_contain")
        ),
    }


def expectations(stats: dict) -> list:
    """(label, literal that must appear in COVERAGE.md) derived from live counts."""
    g = stats["mutation_groups"]
    t = stats["by_type"]
    return [
        ("check count", f"{stats['checks']} checks, declared as data"),
        (
            "fixture census",
            f"{stats['fixtures']} fixtures — {t['defect']} defect, "
            f"{t['good_practice']} good_practice, {t['degradation_scenario']} "
            f"degradation_scenario, {t['workflow']} workflow",
        ),
        ("fact guards", f"{stats['fact_guards']} parametrised guards"),
        ("server probe count (cli hint)", f"# {stats['server_probes']} server probes"),
        ("server probe count (gap row)", f"runs {stats['server_probes']} probes"),
        ("mutation total", f"{stats['mutations']} mutations"),
        (
            "mutation group L (per-check)",
            "| `L{:02d}`–`L{:02d}` | {} |".format(
                *stats["mutation_L_per_check_range"], stats["mutation_L_per_check"]
            ),
        ),
        (
            "mutation group L (calibration)",
            "| `L{:02d}`–`L{:02d}` | {} |".format(
                *stats["mutation_L_calib_range"], stats["mutation_L_calibration"]
            ),
        ),
        ("mutation group F", f"| {g['F']} | fixture facts"),
        ("mutation group D", f"| {g['D']} | corrected facts"),
        (
            "detail assertions",
            f"{_word(stats['fixtures_with_detail_assertions'])} fixtures also assert",
        ),
    ]


_WORDS = {1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six"}


def _word(n: int) -> str:
    return _WORDS.get(n, str(n))


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)

    stats = collect()

    if not args.check:
        print(json.dumps(stats, indent=2))
        print("\nCOVERAGE.md must contain:")
        for label, literal in expectations(stats):
            print(f"  {label:<20} {literal!r}")
        return 0

    md = COVERAGE_MD.read_text(encoding="utf-8")
    drifted = [
        (label, literal) for label, literal in expectations(stats) if literal not in md
    ]

    # Every fixture must have a row in the inventory table.
    for path in sorted(GOLDEN_DIR.glob("*.json")):
        fid = json.loads(path.read_text(encoding="utf-8"))["id"]
        if f"| {fid} |" not in md:
            drifted.append(("fixture row", f"| {fid} |"))

    # Every check code must appear in the registry table.
    lint = sys.modules["oracle_lint_migration"]
    for code in lint.CHECKS:
        if f"| {code} |" not in md:
            drifted.append(("check row", f"| {code} |"))

    if drifted:
        print("COVERAGE.md has drifted from the live suite:", file=sys.stderr)
        for label, literal in drifted:
            print(f"  missing {label}: {literal!r}", file=sys.stderr)
        return 1

    print("COVERAGE.md matches the live suite.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
