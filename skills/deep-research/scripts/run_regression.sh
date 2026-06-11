#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
TEST_DIR="$SCRIPT_DIR/tests"

echo "=== Deep Research Skill Regression Suite ==="
echo "Skill root: $SKILL_DIR"
echo ""

echo "--- 1/2: All test files (unit + smoke + contract + golden) ---"
# unittest discover picks up every test_*.py, so newly added test files can
# never be silently skipped (the smoke tests were once missing from an
# explicit per-file list while the script shipped broken).
python3 -m unittest discover -s "$TEST_DIR" -p 'test_*.py' -v
echo ""

echo "--- 2/2: Script help check ---"
python3 "$SCRIPT_DIR/deep_research.py" --help >/dev/null
echo "deep_research.py --help: OK"
echo ""

echo "=== All regression checks passed ==="
