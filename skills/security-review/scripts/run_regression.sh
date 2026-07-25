#!/usr/bin/env bash
# Fail closed. A security skill whose own runner prints "passed" after a validation
# failure is worse than no runner: it manufactures false assurance.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
VALIDATOR="${SKILL_CREATOR_VALIDATOR:-$HOME/.codex/skills/.system/skill-creator/scripts/quick_validate.py}"

echo "=== security-review regression suite ==="
echo ""

echo "[1/3] Validate skill frontmatter"
if [[ -f "${VALIDATOR}" ]]; then
  # No `|| echo` here — a validation failure must abort the run via set -e.
  python3 "${VALIDATOR}" "${SKILL_DIR}"
else
  echo "  validator not found at ${VALIDATOR}; skipping"
  echo "  (set SKILL_CREATOR_VALIDATOR to enforce frontmatter validation)"
fi
echo ""

echo "[2/3] Run contract tests (SKILL.md structure + references)"
python3 -m unittest discover -s "${SKILL_DIR}/scripts/tests" -p "test_skill_contract.py" -v
echo ""

echo "[3/3] Run golden + executable-example tests"
python3 -m unittest discover -s "${SKILL_DIR}/scripts/tests" -p "test_golden_reviews.py" -v
python3 -m unittest discover -s "${SKILL_DIR}/scripts/tests" -p "test_examples_executable.py" -v
echo ""

echo "security-review regression checks passed"
