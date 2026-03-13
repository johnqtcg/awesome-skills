#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== E2E Best Practise Skill — Regression Suite ==="
echo ""

echo "--- Contract Tests ---"
python3 "${SCRIPT_DIR}/tests/test_skill_contract.py" -v
echo ""

echo "--- Golden Scenario Tests ---"
python3 "${SCRIPT_DIR}/tests/test_golden_scenarios.py" -v
echo ""

echo "=== All tests passed ==="
