#!/usr/bin/env bash
# Run all of this skill's static checks in one command (V1 layer, no database needed).
#
# Scope: all-green proves only "the rules are written correctly, are mutually
# consistent, and have not been reverted." It does **not** prove "the generated
# DDL executes on the target version and produces the expected execution plan."
# The latter requires tests/integration/ to be run on a real instance and its
# results filled in.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$SKILL_DIR"

echo "=== oceanbase-table-design regression check ==="
echo "Skill directory: $SKILL_DIR"
echo ""

FAIL=0

run() {
    local label="$1"; shift
    echo "--- $label ---"
    if "$@"; then
        echo "  OK"
    else
        echo "  FAIL: $label"
        FAIL=1
    fi
    echo ""
}

run "Cross-file rule consistency (BNF grounding / controlled wording / paired assertions / constants / links / index)" \
    python3 scripts/check_consistency.py

run "NOCACHE-scoping rule graded against the defects it was written for" \
    python3 scripts/check_consistency.py --self-test

run "Output grader calibrated against known-verdict fixtures" \
    python3 scripts/run_cases.py --self-test

run "Case-spec validation (rule list / cases.json / cases.md all consistent)" \
    python3 scripts/run_cases.py --validate

run "Tablet estimation model self-test" \
    python3 scripts/estimate_tablets.py --self-test

run "Per-case negative-log verdict self-test" \
    python3 scripts/check_negative_log.py --self-test

run "Integration-suite version comparison and tiered-gating self-test" \
    bash scripts/run_integration.sh --self-test

run "TOC generator self-test" \
    python3 scripts/gen_toc.py --self-test

run "Reference TOCs up to date (headings vs. anchors)" \
    python3 scripts/gen_toc.py

# Contract tests + golden-scenario tests. Prefer pytest (matches the repo root's
# pytest.ini); fall back to unittest when pytest is not installed -- both run the
# same set of cases, so a missing dependency must never silently skip them.
echo "--- Contract tests + golden-scenario tests ---"
if python3 -c "import pytest" 2>/dev/null; then
    if python3 -m pytest scripts/tests -q; then
        echo "  OK (pytest)"
    else
        echo "  FAIL: scripts/tests"
        FAIL=1
    fi
else
    echo "  (pytest not installed, falling back to unittest)"
    if python3 -m unittest discover -s scripts/tests -p 'test_*.py'; then
        echo "  OK (unittest)"
    else
        echo "  FAIL: scripts/tests"
        FAIL=1
    fi
fi
echo ""

# Two budgets, because they catch different things. Lines catch a file growing new
# sections; words catch existing sections getting verbose without adding lines. The
# word ceiling is the skill-creator guideline -- a main file that costs more context
# than this on every trigger starts diluting its own instructions.
echo "--- SKILL.md size budget ---"
LINES=$(wc -l < SKILL.md)
WORDS=$(wc -w < SKILL.md | tr -d ' ')
echo "  SKILL.md: ${LINES} lines (limit 500), ${WORDS} words (limit 5000)"
if [ "$LINES" -gt 500 ]; then
    echo "  FAIL: exceeds 500 lines, move verbatim blocks to references/"
    FAIL=1
elif [ "$WORDS" -gt 5000 ]; then
    echo "  FAIL: exceeds 5000 words, push detail down into references/"
    FAIL=1
else
    echo "  OK"
fi
echo ""

echo "=== Conclusion ==="
if [ "$FAIL" -ne 0 ]; then
    echo "FAIL -- some checks did not pass"
    exit 1
fi
echo "PASS -- all static checks passed (V1 layer; V2-V5 still pending on a real instance)"
exit 0
