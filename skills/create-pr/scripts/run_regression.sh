#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
VALIDATOR="${SKILL_CREATOR_VALIDATOR:-$HOME/.codex/skills/.system/skill-creator/scripts/quick_validate.py}"

echo "[1/3] Validate skill frontmatter"
if [[ ! -f "${VALIDATOR}" ]]; then
  echo "validator not found at ${VALIDATOR}" >&2
  exit 1
fi
python3 "${VALIDATOR}" "${SKILL_DIR}"

echo "[2/3] Smoke-test bundled script help"
python3 "${SKILL_DIR}/scripts/create_pr.py" --help >/dev/null

echo "[3/3] Run regression tests"
python3 -m unittest discover -s "${SKILL_DIR}/scripts/tests" -p "test_*.py" -v

echo "create-pr skill regression checks passed"
