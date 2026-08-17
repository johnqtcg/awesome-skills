#!/usr/bin/env bash
# Run all regression tests for the log-analyzer skill.
#
# This discovers test files rather than listing them: an earlier version named
# two files explicitly, so test suites added later were never executed here even
# though they passed under `pytest skills/`.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEST_DIR="${SCRIPT_DIR}/tests"

shopt -s nullglob
TESTS=("${TEST_DIR}"/test_*.py)
shopt -u nullglob

if [ ${#TESTS[@]} -eq 0 ]; then
  echo "FAIL: no test files found under ${TEST_DIR}" >&2
  exit 1
fi

echo "Running ${#TESTS[@]} test suites:"
for t in "${TESTS[@]}"; do echo "  - $(basename "$t")"; done
echo

python3 -m pytest "${TESTS[@]}" -q

echo
echo "log-analyzer skill regression checks passed (${#TESTS[@]} suites)."
