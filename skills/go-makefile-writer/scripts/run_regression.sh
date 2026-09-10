#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TESTS_DIR="${SCRIPT_DIR}/tests"

# The test files are DISCOVERED, not listed. This script used to name them one
# by one, which meant a new test file ran under `pytest skills/` and in CI but
# was silently skipped by the skill's own regression entrypoint — the place a
# contributor is most likely to trust. A hand-maintained list of things that
# must match the directory is a second copy of the directory.
total=$(ls "${TESTS_DIR}"/test_*.py 2>/dev/null | wc -l | tr -d ' ')
if [ "$total" -eq 0 ]; then
  echo "no test files found under ${TESTS_DIR}" >&2
  exit 1
fi

echo "=== go-makefile-writer skill regression (${total} test files) ==="
echo ""

i=0
for f in "${TESTS_DIR}"/test_*.py; do
  i=$((i + 1))
  echo "[${i}/${total}] $(basename "$f")..."
  python3 "$f" -v
  echo ""
done

echo "=== All tests passed ==="
