#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TESTS_DIR="${SCRIPT_DIR}/tests"

echo "=== api-integration-test skill regression suite ==="
echo ""

if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 not found. Install Python 3.8+."
    exit 1
fi

echo "Running contract tests..."
python3 -m unittest "${TESTS_DIR}/test_skill_contract.py" -v
echo ""

echo "Running golden scenario tests..."
python3 -m unittest "${TESTS_DIR}/test_golden_scenarios.py" -v
echo ""

echo "=== All regression tests passed ==="
