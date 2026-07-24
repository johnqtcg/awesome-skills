#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TESTS_DIR="${SCRIPT_DIR}/tests"

echo "=== thirdparty-api-integration-test skill regression suite ==="
echo ""

if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 not found. Install Python 3.8+."
    exit 1
fi

# Discover ALL test_*.py — never hardcode a per-file list (a hardcoded list once
# silently excluded a whole behavioral suite in a sibling skill).
python3 -m unittest discover -s "${TESTS_DIR}" -p "test_*.py" -v

echo ""
echo "=== All regression tests passed ==="