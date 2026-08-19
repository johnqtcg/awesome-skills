#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEST_DIR="${SCRIPT_DIR}/tests"
echo "[1/4] Documentation linter (factual + structural rules over the real docs)"
python3 "${SCRIPT_DIR}/lint_api_doc.py" "${SCRIPT_DIR}/.."
echo "[2/4] Linter mutation tests (every rule must catch its own regression)"
python3 -m pytest "${TEST_DIR}/test_doc_lint.py" -v
echo "[3/4] Contract tests (SKILL.md structure + reference files)"
python3 -m pytest "${TEST_DIR}/test_skill_contract.py" -v
echo "[4/4] Golden scenario tests (fixture/doc consistency + false positives)"
python3 -m pytest "${TEST_DIR}/test_golden_scenarios.py" -v
echo ""
echo "api-design skill regression checks passed."
