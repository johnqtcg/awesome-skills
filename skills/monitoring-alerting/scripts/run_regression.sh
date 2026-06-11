#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEST_DIR="${SCRIPT_DIR}/tests"
echo "All test files (contract + golden + yaml artifacts)"
# pytest discovers every test_*.py, so newly added test files can never be
# silently skipped (explicit per-file lists repeatedly caused exactly that
# across this repo's skills).
python3 -m pytest "${TEST_DIR}" -v
echo ""
echo "monitoring-alerting skill regression checks passed."
