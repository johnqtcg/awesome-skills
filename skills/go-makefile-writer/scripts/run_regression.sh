#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TESTS_DIR="${SCRIPT_DIR}/tests"

echo "=== go-makefile-writer skill regression ==="
echo ""

echo "[1/2] Contract tests..."
python3 "${TESTS_DIR}/test_skill_contract.py" -v
echo ""

echo "[2/2] Golden review tests..."
python3 "${TESTS_DIR}/test_golden_reviews.py" -v
echo ""

echo "=== All tests passed ==="
