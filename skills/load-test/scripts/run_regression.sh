#!/usr/bin/env bash
# Run all regression tests for the load-test skill.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEST_DIR="${SCRIPT_DIR}/tests"

echo "All test files (contract + golden + k6-script validation)"
# pytest discovers every test_*.py, so newly added test files can never be
# silently skipped (an explicit per-file list once excluded the k6 script
# validation tests that caught 4 missing-import bugs in the references).
python3 -m pytest "${TEST_DIR}" -v

echo ""
echo "load-test skill regression checks passed."
