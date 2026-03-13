#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

echo "=== tdd-workflow skill regression ==="

echo "--- Contract tests ---"
python3 -m unittest tests/test_skill_contract.py -v

echo "--- Golden scenario tests ---"
python3 -m unittest tests/test_golden_scenarios.py -v

echo "=== All tests passed ==="
