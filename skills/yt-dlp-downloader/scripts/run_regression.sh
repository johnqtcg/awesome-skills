#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TEST_DIR="$SCRIPT_DIR/tests"

echo "=== yt-dlp-downloader Skill Regression Suite ==="
echo ""

echo "--- All test files (contract + golden + flags-against-binary) ---"
# unittest discover picks up every test_*.py so newly added test files can
# never be silently skipped (an explicit per-file list once missed the
# binary-validation tests while 17 corrupted flags shipped green).
python3 -m unittest discover -s "$TEST_DIR" -p 'test_*.py' -v
echo ""

echo "=== All regression checks passed ==="
