#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
VALIDATOR="${SKILL_CREATOR_VALIDATOR:-$HOME/.codex/skills/.system/skill-creator/scripts/quick_validate.py}"

echo "=== security-review regression suite ==="
echo ""

echo "[1/3] Validate skill frontmatter"
if [[ -f "${VALIDATOR}" ]]; then
  python3 "${VALIDATOR}" "${SKILL_DIR}" || echo "  quick_validate failed (non-blocking)"
else
  echo "  validator not found at ${VALIDATOR}; skip quick_validate"
fi
echo ""

echo "[2/3] Run contract tests (SKILL.md structure + references)"
python3 -m unittest discover -s "${SKILL_DIR}/scripts/tests" -p "test_skill_contract.py" -v
echo ""

echo "[3/3] Run golden review tests (rule coverage + false-positive suppression)"
python3 -m unittest discover -s "${SKILL_DIR}/scripts/tests" -p "test_golden_reviews.py" -v
echo ""

echo "security-review regression checks passed"
