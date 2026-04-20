#!/usr/bin/env bash
# Run all regression tests for the load-test skill.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEST_DIR="${SCRIPT_DIR}/tests"

echo "[1/2] Contract tests (SKILL.md structure + reference files)"
python3 -m pytest "${TEST_DIR}/test_skill_contract.py" -v

echo "[2/2] Golden scenario tests (load test defect detection)"
python3 -m pytest "${TEST_DIR}/test_golden_scenarios.py" -v

echo ""
echo "load-test skill regression checks passed."