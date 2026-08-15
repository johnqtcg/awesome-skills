#!/usr/bin/env bash
# Run all regression checks for the go-dependency-audit skill.
#
# Everything here is offline and deterministic. The behavioural evaluation
# (scripts/eval_forward.py --run) needs an authenticated `claude` CLI and is NOT
# part of this suite; step 5 runs only its self-test, which proves the grader can
# still tell a correct answer from a wrong one.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "${SCRIPT_DIR}")"
TEST_DIR="${SCRIPT_DIR}/tests"
rc=0

run() {
  echo
  echo "--- $1"
  shift
  "$@" || rc=1
}

run "[1/5] Fact linter (commands, flags, env vars, framing)" \
  python3 "${SCRIPT_DIR}/lint_dep_audit_docs.py" "${SKILL_DIR}"

run "[2/5] Linter mutation tests (every rule must kill its own defect)" \
  python3 -m pytest "${TEST_DIR}/test_doc_lint.py" -q

run "[3/5] govulncheck recipe tests (jq extracted from the docs, executed)" \
  python3 -m pytest "${TEST_DIR}/test_govulncheck_recipes.py" -q

run "[4/5] Structure + golden scenario tests" \
  python3 -m pytest "${TEST_DIR}/test_skill_contract.py" \
                    "${TEST_DIR}/test_golden_scenarios.py" -q

run "[5/5] Forward-eval harness (criteria self-test + grader failure modes)" \
  python3 -m pytest "${TEST_DIR}/test_forward_eval.py" -q

echo
if [ "$rc" -eq 0 ]; then
  echo "go-dependency-audit regression checks passed."
  echo "Behavioural eval (needs an authenticated CLI, not run here):"
  echo "  python3 ${SCRIPT_DIR}/eval_forward.py --run"
  echo "  python3 ${SCRIPT_DIR}/eval_forward.py --grade <dir>"
else
  echo "go-dependency-audit regression checks FAILED."
fi
exit "$rc"
