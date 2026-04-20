#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEST_DIR="${SCRIPT_DIR}/tests"
echo "[1/2] Contract tests (SKILL.md structure + reference files)"
python3 -m pytest "${TEST_DIR}/test_skill_contract.py" -v
echo "[2/2] Golden scenario tests (API design defect detection)"
python3 -m pytest "${TEST_DIR}/test_golden_scenarios.py" -v
echo ""
echo "api-design skill regression checks passed."