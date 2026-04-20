#!/usr/bin/env bash
# Run all regression tests for the incident-postmortem-postmortem skill.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEST_DIR="${SCRIPT_DIR}/tests"

echo "[1/2] Contract tests (SKILL.md structure + reference files)"
python3 -m pytest "${TEST_DIR}/test_skill_contract.py" -v

echo "[2/2] Golden scenario tests (post-mortem quality detection)"
python3 -m pytest "${TEST_DIR}/test_golden_scenarios.py" -v

echo ""
echo "incident-postmortem skill regression checks passed."