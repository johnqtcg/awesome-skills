#!/usr/bin/env bash
# Find which test introduces an unwanted file/state artifact.
# Usage: ./scripts/find-polluter.sh <file_or_dir_to_check> <test_pattern> [runner]
# Example: ./scripts/find-polluter.sh '.git' './src/**/*.test.ts' 'npm test'

set -euo pipefail

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  echo "Usage: $0 <file_to_check> <test_pattern> [runner]"
  echo "Example: $0 '.git' './src/**/*.test.ts' 'npm test'"
  exit 0
fi

if [[ $# -lt 2 || $# -gt 3 ]]; then
  echo "Usage: $0 <file_to_check> <test_pattern> [runner]"
  echo "Example: $0 '.git' './src/**/*.test.ts' 'npm test'"
  exit 64
fi

POLLUTION_CHECK="$1"
TEST_PATTERN="$2"
RUNNER_STR="${3:-${TEST_RUNNER:-npm test}}"

if [[ -e "$POLLUTION_CHECK" ]]; then
  echo "Error: '$POLLUTION_CHECK' already exists before running tests."
  echo "Clean up the artifact first, then rerun the script."
  exit 2
fi

# Split runner string into argv array (simple space-delimited form).
# For complex quoting, pass a wrapper script path in TEST_RUNNER.
read -r -a RUNNER <<<"$RUNNER_STR"
if [[ ${#RUNNER[@]} -eq 0 ]]; then
  echo "Error: empty test runner command"
  exit 64
fi

echo "Searching for test that creates: $POLLUTION_CHECK"
echo "Pattern: $TEST_PATTERN"
echo "Runner: ${RUNNER[*]}"
echo ""

TEST_FILES=()
while IFS= read -r path; do
  [[ -n "$path" ]] || continue
  TEST_FILES+=("$path")
done < <(find . -type f -path "$TEST_PATTERN" | LC_ALL=C sort)

TOTAL=${#TEST_FILES[@]}
if [[ $TOTAL -eq 0 ]]; then
  echo "No test files matched pattern: $TEST_PATTERN"
  exit 3
fi

echo "Found $TOTAL test files"
echo ""

COUNT=0
for TEST_FILE in "${TEST_FILES[@]}"; do
  COUNT=$((COUNT + 1))

  if [[ -e "$POLLUTION_CHECK" ]]; then
    echo "Error: '$POLLUTION_CHECK' appeared before running $TEST_FILE"
    exit 2
  fi

  echo "[$COUNT/$TOTAL] Testing: $TEST_FILE"
  "${RUNNER[@]}" "$TEST_FILE" >/dev/null 2>&1 || true

  if [[ -e "$POLLUTION_CHECK" ]]; then
    echo ""
    echo "FOUND POLLUTER"
    echo "  Test: $TEST_FILE"
    echo "  Created: $POLLUTION_CHECK"
    echo ""
    echo "Pollution details:"
    ls -la "$POLLUTION_CHECK"
    echo ""
    echo "To investigate:"
    echo "  ${RUNNER[*]} '$TEST_FILE'"
    echo "  sed -n '1,200p' '$TEST_FILE'"
    exit 1
  fi
done

echo ""
echo "No polluter found: all matched tests left '$POLLUTION_CHECK' untouched."
exit 0
