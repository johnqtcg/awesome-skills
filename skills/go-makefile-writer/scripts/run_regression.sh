#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TESTS_DIR="${SCRIPT_DIR}/tests"

echo "=== go-makefile-writer skill regression ==="
echo ""

echo "[1/3] Contract tests..."
python3 "${TESTS_DIR}/test_skill_contract.py" -v
echo ""

echo "[2/3] Golden review tests..."
python3 "${TESTS_DIR}/test_golden_reviews.py" -v
echo ""

echo "[3/3] Executable-asset tests (real make / build)..."
python3 "${TESTS_DIR}/test_executable_assets.py" -v
echo ""

echo "=== All tests passed ==="
