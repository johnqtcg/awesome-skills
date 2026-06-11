#!/usr/bin/env bash
# Run all regression tests for the go-benchmark skill.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEST_DIR="${SCRIPT_DIR}/tests"

echo "All test files (contract + golden + template compilation)"
# pytest discovers every test_*.py, so newly added test files can never be
# silently skipped (explicit per-file lists repeatedly caused exactly that
# across this repo's skills).
python3 -m pytest "${TEST_DIR}" -v

echo ""
echo "go-benchmark skill regression checks passed."
