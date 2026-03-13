#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TESTS_DIR="${SCRIPT_DIR}/tests"

echo "=== Google Search Skill — Regression Tests ==="
echo ""

PYTEST="python3 -m pytest"
if ! $PYTEST --version &>/dev/null; then
    PYTEST="pipx run pytest"
fi

echo "--- Contract Tests ---"
$PYTEST "${TESTS_DIR}/test_skill_contract.py" -v --tb=short "$@"
echo ""

echo "--- Golden Scenario Tests ---"
$PYTEST "${TESTS_DIR}/test_golden_scenarios.py" -v --tb=short "$@"
echo ""

echo "=== All tests complete ==="
