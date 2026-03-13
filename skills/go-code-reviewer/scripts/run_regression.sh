#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
VALIDATOR="${SKILL_CREATOR_VALIDATOR:-$HOME/.codex/skills/.system/skill-creator/scripts/quick_validate.py}"

echo "[1/2] Validate skill frontmatter"
if [[ -f "${VALIDATOR}" ]]; then
  python3 "${VALIDATOR}" "${SKILL_DIR}"
else
  echo "validator not found at ${VALIDATOR}; skip quick_validate"
fi

echo "[2/2] Run regression tests"
python3 -m unittest discover -s "${SKILL_DIR}/scripts/tests" -p "test_*.py" -v

echo "go-code-reviewer regression checks passed"
