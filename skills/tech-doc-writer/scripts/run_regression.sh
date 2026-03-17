#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=== tech-doc-writer skill regression tests ==="
echo "Skill directory: $SKILL_DIR"
echo ""

cd "$SKILL_DIR"

FAIL=0

echo "--- Contract tests ---"
python3 -m unittest discover -s scripts/tests -p 'test_*.py' -v 2>&1 || FAIL=1

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
    # Verify all required fields exist in the Output Contract block
    REQUIRED_FIELDS=("mode:" "degradation:" "doc_type:" "audience:" "scorecard:" "files:" "maintenance:" "assumptions:")
    for field in "${REQUIRED_FIELDS[@]}"; do
        if grep -q "$field" SKILL.md; then
            echo "  OK: Output Contract field '$field' present"
        else
            echo "  FAIL: Output Contract missing field '$field'"
            FAIL=1
        fi
    done
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
ANTI_COUNT_GUIDE=$(grep -c "^\*\*" references/writing-quality-guide.md 2>/dev/null | tail -1)
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
if [ "$FAIL" -eq 0 ]; then
    echo "=== All checks passed ==="
else
    echo "=== Some checks FAILED ==="
    exit 1
fi
