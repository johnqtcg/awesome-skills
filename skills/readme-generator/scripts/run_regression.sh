#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
VALIDATOR="${SKILL_CREATOR_VALIDATOR:-$HOME/.codex/skills/.system/skill-creator/scripts/quick_validate.py}"

echo "============================================"
echo "  readme-generator skill regression suite"
echo "============================================"

run_suite() {
  local label="$1" file="$2"
  echo ""
  echo "${label}"
  if python3 -c "import pytest" >/dev/null 2>&1; then
    python3 -m pytest "${SKILL_DIR}/scripts/tests/${file}" -v
  else
    echo "  pytest not installed; falling back to unittest"
    python3 "${SKILL_DIR}/scripts/tests/${file}"
  fi
}

echo ""
echo "[1/5] Validate skill frontmatter"
if [[ -f "${VALIDATOR}" ]]; then
  python3 "${VALIDATOR}" "${SKILL_DIR}"
else
  echo "  validator not found at ${VALIDATOR}; skip quick_validate"
fi

run_suite "[2/5] Contract tests"                    test_skill_contract.py
run_suite "[3/5] Golden scenario tests"             test_golden_scenarios.py
run_suite "[4/5] Discovery script behavioral tests" test_discovery_script.py
run_suite "[5/5] Forward evaluation"                test_forward_eval.py

echo ""
echo "============================================"
echo "  All regression checks passed"
echo "============================================"

# Coverage honesty. The forward-eval layer proves the GRADER separates a grounded
# README from a fabricated one. It does not prove a live model produces grounded
# READMEs — that requires README_GEN_EVAL_CMD. Say so out loud rather than letting a
# green suite imply coverage it does not have.
if [[ -z "${README_GEN_EVAL_CMD:-}" ]]; then
  echo ""
  echo "  GAP: live forward eval skipped (README_GEN_EVAL_CMD unset)."
  echo "       Verified: the rules exist, routing is correct, the grader discriminates,"
  echo "       and every golden example the skill ships survives that grader."
  echo "       NOT verified: that a live model reliably produces a passing README."
  echo ""
  echo "       Run it with:  bash scripts/run_live_eval.sh"
  echo "       It needs an AUTHENTICATED CLI. Unauthenticated it aborts with exit 2 and"
  echo "       grades nothing, so a setup failure can never be read as a skill result."
fi
