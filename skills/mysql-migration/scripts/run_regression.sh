#!/usr/bin/env bash
# Run all regression checks for the mysql-migration skill.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
TEST_DIR="${SCRIPT_DIR}/tests"

# Named phases exist for readable output. The coverage guard below is what makes
# them safe: a new test file that nobody wires into a phase would otherwise be
# collected by `pytest skills/` in CI and silently skipped here, which is how a
# 52-test file went unrun by this script until 2026-08-06.
declare -a PHASE_LABEL=(
  "Contract tests (SKILL.md structure + reference files)"
  "Golden scenario tests (fixture integrity + checker verdicts)"
  "Migration checker tests (declared coverage, corrected forms, audit regressions)"
  "Drift guards + harness guards (matrix, tools, docs, eval rubric, server-script safety)"
)
declare -a PHASE_FILES=(
  "test_skill_contract.py"
  "test_golden_scenarios.py"
  "test_lint_migration.py test_lint_round2_audit.py test_lint_round3_audit.py test_lint_round4_audit.py"
  "test_ddl_matrix_drift.py test_tool_facts_drift.py test_model_eval_harness.py test_verify_server_guards.py"
)

echo "[0/5] Test-file coverage guard"
# bash 3.2 compatible (macOS default): no mapfile, no associative arrays.
ON_DISK="$(cd "${TEST_DIR}" && ls test_*.py 2>/dev/null | sort)"
WIRED="$(printf '%s\n' ${PHASE_FILES[@]+"${PHASE_FILES[@]}"} | tr ' ' '\n' | grep -v '^$' | sort -u)"
if [[ -z "${ON_DISK}" ]]; then
  echo "ERROR: no test files found in ${TEST_DIR}" >&2
  exit 1
fi
MISSING="$(comm -23 <(printf '%s\n' "${ON_DISK}") <(printf '%s\n' "${WIRED}"))"
STALE="$(comm -13 <(printf '%s\n' "${ON_DISK}") <(printf '%s\n' "${WIRED}"))"
if [[ -n "${MISSING}" ]]; then
  echo "ERROR: test files on disk but not wired into any phase:" >&2
  printf '%s\n' "${MISSING}" | sed 's/^/  /' >&2
  exit 1
fi
if [[ -n "${STALE}" ]]; then
  echo "ERROR: phases reference test files that no longer exist:" >&2
  printf '%s\n' "${STALE}" | sed 's/^/  /' >&2
  exit 1
fi
echo "  $(printf '%s\n' "${ON_DISK}" | wc -l | tr -d ' ') test file(s), all wired"

for i in "${!PHASE_LABEL[@]}"; do
  echo "[$((i + 1))/5] ${PHASE_LABEL[$i]}"
  # shellcheck disable=SC2086 -- word splitting is the point: one phase, several files
  ( cd "${TEST_DIR}" && python3 -m pytest ${PHASE_FILES[$i]} -q )
done

echo "[5/5] Self-lint: the shipped documentation must pass its own checker"
# --fail-on warning, not critical: a warning nobody has to act on accumulates until
# the self-lint means nothing. Findings that are genuinely correct for a MySQL
# version other than the one this run assumes are listed, with written justification,
# in tests/lint_baseline.txt — and a baseline entry that stops matching is itself an
# error, so exemptions cannot outlive their reason. Blocks labelled WRONG/INVALID
# are excluded as deliberate anti-examples.
python3 "${SCRIPT_DIR}/lint_migration.py" \
  --mysql-version 8.0.35 \
  --skip-negative-examples \
  --fail-on warning \
  --baseline "${TEST_DIR}/lint_baseline.txt" \
  "${SKILL_DIR}/SKILL.md" "${SKILL_DIR}/references"

echo
echo "mysql-migration skill regression checks passed."
echo
echo "NOT covered by the above — run these deliberately:"
echo "  * Mutation sweep (are the assertions load-bearing? ~1 min):"
echo "      python3 ${SCRIPT_DIR}/mutation_sweep.py"
echo "  * Server verification (the only check that can falsify the DDL matrix itself;"
echo "    needs a real MySQL):"
echo "      MYSQL_MIGRATION_VERIFY=1 MYSQL_HOST=... MYSQL_USER=... \\"
echo "        bash ${SCRIPT_DIR}/verify_against_server.sh"
echo "  * Model-facing evaluation — the grader's own tests ran above, but the"
echo "    with-skill / without-skill question is UNANSWERED until this runs"
echo "    against a real model:"
echo "      python3 ${SCRIPT_DIR}/run_model_eval.py \\"
echo "        --model-cmd '<cmd reading a prompt on stdin>' --out results/"
