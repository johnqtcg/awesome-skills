#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
TEST_DIR="$SCRIPT_DIR/tests"

echo "=== Deep Research Skill Regression Suite ==="
echo "Skill root: $SKILL_DIR"
echo ""

run_pytest() {
    if python3 -m pytest "$@" 2>/dev/null; then
        return 0
    elif command -v pipx &>/dev/null && pipx run pytest "$@" 2>/dev/null; then
        return 0
    else
        echo "ERROR: pytest not found. Install with: pip install pytest" >&2
        return 1
    fi
}

echo "--- 1/4: Script unit tests (test_deep_research.py) ---"
python3 -m unittest discover -s "$TEST_DIR" -p 'test_deep_research.py' -v
echo ""

echo "--- 2/4: SKILL.md contract tests (test_skill_contract.py) ---"
run_pytest "$TEST_DIR/test_skill_contract.py" -v
echo ""

echo "--- 3/4: Golden scenario tests (test_golden_scenarios.py) ---"
run_pytest "$TEST_DIR/test_golden_scenarios.py" -v
echo ""

echo "--- 4/4: Script help check ---"
python3 "$SCRIPT_DIR/deep_research.py" --help >/dev/null
echo "deep_research.py --help: OK"
echo ""

echo "=== All regression checks passed ==="
