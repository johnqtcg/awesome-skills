#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TEST_DIR="$SCRIPT_DIR/tests"

echo "=== yt-dlp-downloader Skill Regression Suite ==="
echo ""

echo "--- 1/2: Contract tests (test_skill_contract.py) ---"
python3 -m unittest "$TEST_DIR/test_skill_contract.py" -v
echo ""

echo "--- 2/2: Golden scenario tests (test_golden_scenarios.py) ---"
python3 -m unittest "$TEST_DIR/test_golden_scenarios.py" -v
echo ""

echo "=== All regression checks passed ==="
