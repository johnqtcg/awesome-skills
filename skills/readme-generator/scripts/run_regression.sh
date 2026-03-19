#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
VALIDATOR="${SKILL_CREATOR_VALIDATOR:-$HOME/.codex/skills/.system/skill-creator/scripts/quick_validate.py}"

echo "============================================"
echo "  readme-generator skill regression suite"
echo "============================================"

echo ""
echo "[1/3] Validate skill frontmatter"
if [[ -f "${VALIDATOR}" ]]; then
  python3 "${VALIDATOR}" "${SKILL_DIR}"
else
  echo "  validator not found at ${VALIDATOR}; skip quick_validate"
fi

echo ""
echo "[2/3] Run contract tests"
if python3 -c "import pytest" >/dev/null 2>&1; then
  python3 -m pytest "${SKILL_DIR}/scripts/tests/test_skill_contract.py" -v
else
  echo "  pytest not installed; falling back to unittest"
  python3 "${SKILL_DIR}/scripts/tests/test_skill_contract.py"
fi

echo ""
echo "[3/3] Run golden scenario tests"
if python3 -c "import pytest" >/dev/null 2>&1; then
  python3 -m pytest "${SKILL_DIR}/scripts/tests/test_golden_scenarios.py" -v
else
  echo "  pytest not installed; falling back to unittest"
  python3 "${SKILL_DIR}/scripts/tests/test_golden_scenarios.py"
fi

echo ""
echo "============================================"
echo "  All regression checks passed"
echo "============================================"
