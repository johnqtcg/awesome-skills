#!/usr/bin/env python3
"""Regenerate the count rows in scripts/tests/COVERAGE.md from disk.

`test_skill_contract.py::TestCoverageDocAccuracy` already fails when those numbers drift, which
is the important half. This closes the other half: the numbers were still typed by hand, so every
change to the suite meant a manual edit, and getting it wrong produced a red build that said
nothing about the skill. Counted, not remembered.

    python3 scripts/sync_coverage_counts.py [--check]

--check exits non-zero without writing, for CI.
"""

import json
import re
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
TESTS = SKILL_DIR / "scripts" / "tests"
COVERAGE = TESTS / "COVERAGE.md"
SKILL_MD = SKILL_DIR / "SKILL.md"

# Label in COVERAGE.md -> test module. Must stay in step with
# TestCoverageDocAccuracy.LAYER_LABELS, which test_every_test_module_is_accounted_for pins
# against the modules actually on disk.
LAYERS = {
    "Contract tests": "test_skill_contract.py",
    "Golden-fixture tests": "test_golden_reviews.py",
    "Executable-example tests": "test_examples_executable.py",
    "Forward-eval tests": "test_forward_eval.py",
    "Report-schema tests": "test_report_schema.py",
}
# Collected by pytest via its *_test.py pattern but driven as a subprocess by the layer above,
# so these are counted separately rather than folded into the layer totals. DISCOVERED, not
# listed: naming one file left the next one unaccounted for — `jinja_ssti_facts_test.py` was
# added with 6 tests that neither this script nor COVERAGE.md knew about, and the sync would
# have kept writing back the stale total.
def nested_matrices():
    return sorted((TESTS / "examples" / "python").glob("*_test.py"), key=lambda q: q.name)


def count_tests(path: Path) -> int:
    return len(re.findall(r"(?m)^\s+def test_\w+", path.read_text(encoding="utf-8")))


def main() -> int:
    check_only = "--check" in sys.argv
    text = COVERAGE.read_text(encoding="utf-8")
    original = text

    total = 0
    for label, module in LAYERS.items():
        n = count_tests(TESTS / module)
        total += n
        text = re.sub(rf"\|\s*{re.escape(label)}\s*\|\s*\d+\s*\|", f"| {label} | {n} |", text)

    text = re.sub(r"\|\s*\*\*Total tests\*\*\s*\|\s*\*\*\d+\*\*\s*\|",
                  f"| **Total tests** | **{total}** |", text)

    fixtures = sorted((TESTS / "golden").glob("*.json"))
    parsed = [json.loads(p.read_text(encoding="utf-8")) for p in fixtures]
    tp = sum(1 for f in parsed if f["expected_finding"])
    text = re.sub(r"\|\s*Total golden fixtures\s*\|\s*\d+\s*\|",
                  f"| Total golden fixtures | {len(parsed)} |", text)
    text = re.sub(r"\|\s*True positives\s*\|\s*\d+\s*\|", f"| True positives | {tp} |", text)
    text = re.sub(r"\|\s*False positives\s*\|\s*\d+\s*\|",
                  f"| False positives | {len(parsed) - tp} |", text)

    lines = len(SKILL_MD.read_text(encoding="utf-8").splitlines())
    # Unchanged from before the § Output Contract split. The headroom below came from moving
    # normative detail into references/output-contract.md, not from relaxing the cap — raising
    # the number to fit a change is how a budget stops being one.
    budget = 500
    text = re.sub(r"\|\s*SKILL\.md lines\s*\|[^|]*\|",
                  f"| SKILL.md lines | {lines} (budget: ≤ {budget}, "
                  f"{budget - lines} lines headroom) |", text)

    nested_count = 0
    for path in nested_matrices():
        n = count_tests(path)
        nested_count += n
        pattern = rf"{re.escape(path.name)}` adds \d+ more:"
        if not re.search(pattern, text):
            print(f"COVERAGE.md does not declare nested matrix {path.name} "
                  f"({n} tests) — add a row for it", file=sys.stderr)
            return 1
        text = re.sub(pattern, f"{path.name}` adds {n} more:", text)
    collected = total + nested_count
    text = re.sub(r"collects it directly and reports \d+\.",
                  f"collects it directly and reports {collected}.", text)

    if text == original:
        print("COVERAGE.md counts already accurate")
        return 0
    if check_only:
        print("COVERAGE.md counts are stale; run scripts/sync_coverage_counts.py", file=sys.stderr)
        return 1
    COVERAGE.write_text(text, encoding="utf-8")
    print(f"updated: {total} layer tests ({collected} collected by pytest), "
          f"{len(parsed)} fixtures, SKILL.md {lines} lines")
    return 0


if __name__ == "__main__":
    sys.exit(main())
