#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=== tech-doc-writer skill regression tests ==="
echo "Skill directory: $SKILL_DIR"
echo ""

cd "$SKILL_DIR"

FAIL=0
STRICT="${STRICT:-0}"
SKIPS=()
note_skip() { SKIPS+=("$1"); }

[ "$STRICT" = "1" ] && echo "(STRICT=1: any skipped check fails the run)"

echo "--- Contract tests ---"
# Read unittest's structured summary rather than grepping the log body: this suite's own
# docstrings discuss skipped checks, so a text grep invents phantom skips.
TEST_LOG="$(mktemp "${TMPDIR:-/tmp}/tdw-tests.XXXXXX")"
trap 'rm -f "$TEST_LOG"' EXIT
python3 -m unittest discover -s scripts/tests -p 'test_*.py' -v 2>&1 | tee "$TEST_LOG" || FAIL=1
if grep -q "^FAILED" "$TEST_LOG"; then FAIL=1; fi
# A stub is not a model. Setting TECH_DOC_EVAL_CMD to stub_writer.py un-skips LiveForwardEval,
# which would otherwise be reported as "all checks executed" — a stub replaying a stored
# exemplar would then masquerade as live-model coverage.
case "${TECH_DOC_EVAL_CMD:-}" in
    *stub_writer.py*)
        note_skip "TECH_DOC_EVAL_CMD points at stub_writer.py, not a model. The live path ran, \
but it replayed stored exemplars; model behaviour is still unmeasured."
        ;;
esac

SKIPPED_N="$(sed -nE 's/^OK \(.*skipped=([0-9]+).*\)$/\1/p' "$TEST_LOG" | tail -1)"
if [ -n "${SKIPPED_N:-}" ] && [ "$SKIPPED_N" -gt 0 ]; then
    if [ -z "${TECH_DOC_EVAL_CMD:-}" ]; then
        # Be exact about the size of the gap. The harness plumbing IS exercised on every run,
        # by LiveHarnessPlumbingTest driving it through scripts/tests/stub_writer.py; what is
        # missing is a real model writing the document rather than a stub replaying one.
        note_skip "no live model configured (${SKIPPED_N} test; set TECH_DOC_EVAL_CMD). \
Harness plumbing and grader discrimination ARE covered via stub_writer.py; unmeasured here is \
whether a model following this skill produces a passing document."
    else
        note_skip "${SKIPPED_N} test(s) skipped (see the -v output above)"
    fi
fi

echo ""
echo "--- Line count check ---"
LINES=$(wc -l < SKILL.md)
echo "SKILL.md: ${LINES} lines (limit: 500)"
if [ "$LINES" -gt 500 ]; then
    echo "FAIL: SKILL.md exceeds 500 lines"
    FAIL=1
fi

echo ""
echo "--- Reference files ---"
for f in references/templates.md references/writing-quality-guide.md references/docs-as-code.md; do
    if [ -f "$f" ]; then
        echo "  OK: $f ($(wc -l < "$f") lines)"
    else
        echo "  FAIL: $f missing"
        FAIL=1
    fi
done

echo ""
echo "--- Output Contract format check ---"
if grep -q "── tech-doc-writer output ──" SKILL.md; then
    # Fields are DERIVED from the contract block, not hardcoded here. A hardcoded list drifted
    # once already: `resolution:` was added to the contract and the runner kept reporting all
    # fields OK. The old check also grepped the whole file, so a field named anywhere in the
    # prose counted as present.
    contract_fields() {   # $1 = which block (1 = template, 2 = worked example)
        awk -v want="$1" '
            /── tech-doc-writer output ──/ { n++; inblk = (n == want); next }
            inblk && /^```/               { inblk = 0 }
            inblk && /^[a-z_]+:/          { sub(/:.*/, "", $1); print $1 }
        ' SKILL.md | sort -u
    }
    TEMPLATE_FIELDS=$(contract_fields 1)
    EXAMPLE_FIELDS=$(contract_fields 2)
    FIELD_COUNT=$(printf '%s\n' "$TEMPLATE_FIELDS" | grep -c .)

    # Floor: proves the extraction found a real block rather than silently matching nothing.
    if [ "$FIELD_COUNT" -lt 8 ]; then
        echo "  FAIL: Output Contract has only $FIELD_COUNT fields — extraction likely broken"
        FAIL=1
    else
        echo "  OK: Output Contract declares $FIELD_COUNT fields: $(echo $TEMPLATE_FIELDS | tr '\n' ' ')"
    fi

    # The worked example must instantiate every field the template declares, or readers copy an
    # example that silently omits part of the contract.
    MISSING=$(comm -23 <(printf '%s\n' "$TEMPLATE_FIELDS") <(printf '%s\n' "$EXAMPLE_FIELDS"))
    if [ -n "$MISSING" ]; then
        echo "  FAIL: worked example omits contract field(s): $(echo $MISSING | tr '\n' ' ')"
        FAIL=1
    else
        echo "  OK: worked example instantiates every declared field"
    fi
else
    echo "  FAIL: Output Contract block not found in SKILL.md"
    FAIL=1
fi

echo ""
echo "--- Template coverage check ---"
# Verify all doc types referenced in Gate 2 have templates in templates.md
DOC_TYPES=("Concept" "Task" "Reference" "Troubleshooting" "Design")
for dtype in "${DOC_TYPES[@]}"; do
    if grep -qi "$dtype" references/templates.md; then
        echo "  OK: Template for '$dtype' doc found"
    else
        echo "  FAIL: No template for '$dtype' doc in templates.md"
        FAIL=1
    fi
done

echo ""
echo "--- Anti-Examples migration check ---"
# Verify Anti-Examples are in writing-quality-guide.md (not duplicated in SKILL.md)
if grep -q "§Anti-Examples" references/writing-quality-guide.md; then
    echo "  OK: §Anti-Examples section exists in writing-quality-guide.md"
else
    echo "  FAIL: §Anti-Examples section missing from writing-quality-guide.md"
    FAIL=1
fi

echo ""
echo "--- Scorecard doc-type annotation check ---"
if grep -q '\[all\]' SKILL.md && grep -q '\[task' SKILL.md && grep -q '\[troubleshooting\]' SKILL.md; then
    echo "  OK: Scorecard items have doc-type annotations"
else
    echo "  WARN: Some scorecard items may lack doc-type annotations"
fi

echo ""
echo "=== verdict ==="
if [ "$FAIL" -ne 0 ]; then
    echo "FAIL — one or more checks failed"
    exit 1
fi

if [ "${#SKIPS[@]}" -eq 0 ]; then
    echo "PASS — all checks executed"
    exit 0
fi

# A bare "All checks passed" while the live eval never ran overstated what was verified: the
# exemplar self-tests show the GRADER discriminates, not that a real model follows the skill.
echo "PASS WITH SKIPS — ${#SKIPS[@]} check(s) did not run:"
for s in "${SKIPS[@]}"; do echo "  - $s"; done
echo ""
echo "These are gaps in verification, not evidence of correctness."
if [ "$STRICT" = "1" ]; then
    echo "FAIL — STRICT=1 requires every check to run"
    exit 1
fi
exit 0
