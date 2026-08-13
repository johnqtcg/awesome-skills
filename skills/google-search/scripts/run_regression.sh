#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TESTS_DIR="${SCRIPT_DIR}/tests"

echo "=== Google Search Skill — Regression Tests ==="
echo ""

PYTHON="python3"
PYTEST="${PYTHON} -m pytest"
if ! $PYTEST --version &>/dev/null; then
    PYTEST="pipx run pytest"
fi

echo "--- Semantic Lint: skill docs ---"
"${PYTHON}" "${SCRIPT_DIR}/lint_search_report.py"
echo ""

echo "--- Semantic Lint: self-test (does each rule fire?) ---"
"${PYTHON}" "${SCRIPT_DIR}/lint_search_report.py" --self-test
echo ""

echo "--- Contract Tests ---"
$PYTEST "${TESTS_DIR}/test_skill_contract.py" -v --tb=short "$@"
echo ""

echo "--- Golden Scenario Tests ---"
$PYTEST "${TESTS_DIR}/test_golden_scenarios.py" -v --tb=short "$@"
echo ""

echo "--- Lint Mutation Tests (does the linter catch reintroduced defects?) ---"
$PYTEST "${TESTS_DIR}/test_lint_mutations.py" -v --tb=short "$@"
echo ""

echo "--- Forward Eval: grade the grader (no model needed) ---"
"${PYTHON}" "${SCRIPT_DIR}/eval_forward.py" --self-test
$PYTEST "${TESTS_DIR}/test_forward_eval.py" -v --tb=short "$@"
echo ""

echo "=== All offline tests complete ==="
echo ""
echo "The live behavioural eval is NOT part of this run: it needs an authenticated CLI and"
echo "an unsandboxed shell. To execute it (same model for both arms):"
echo ""
echo "    python3 scripts/eval_forward.py --run --model sonnet --out eval_out"
echo ""
echo "Everything above grades this skill's TEXT. Only that command grades its BEHAVIOUR."
