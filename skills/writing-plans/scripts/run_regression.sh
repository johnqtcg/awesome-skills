#!/usr/bin/env bash
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== writing-plans skill regression ==="
echo "Skill directory: $SKILL_DIR"
echo ""

echo "--- Contract tests ---"
python3 -m pytest "$SKILL_DIR/scripts/tests/test_skill_contract.py" -v

echo ""
echo "--- Golden scenario tests ---"
python3 -m pytest "$SKILL_DIR/scripts/tests/test_golden_scenarios.py" -v

echo ""
echo "=== All tests passed ==="