#!/usr/bin/env bash
# Regression harness for kafka-event-driven-design.
#
# Gate order is deliberate: the linter must be able to prove itself (selftest)
# before its verdict on the docs means anything, and the mutation sweep must
# prove the whole thing can go red before a green run counts as evidence.
#
# Gate 7 grades the grader, not the model: it proves model_eval.py's deterministic
# scorer can separate a correct review from a confident wrong one, offline. The
# A/B run itself needs a model and stays opt-in (scripts/model_eval.py), as does
# trigger_eval.py — a gate that cannot run offline is a gate everyone skips.
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEST_DIR="${SCRIPT_DIR}/tests"
FAILED=0

run_gate() {
  local label="$1"; shift
  echo ""
  echo "=== ${label} ==="
  if "$@"; then
    echo "--- PASS: ${label}"
  else
    echo "--- FAIL: ${label}"
    FAILED=1
  fi
}

run_gate "[1/8] Linter self-test (every rule fires and stays quiet)" \
  python3 "${SCRIPT_DIR}/lint_kafka_docs.py" --selftest

run_gate "[2/8] Semantic lint of shipped documentation" \
  python3 "${SCRIPT_DIR}/lint_kafka_docs.py"

run_gate "[3/8] Mutation sweep (inverted claims must be caught)" \
  python3 "${SCRIPT_DIR}/mutation_sweep.py"

run_gate "[4/8] Paraphrase corpus (restatements the docs never use)" \
  python3 "${SCRIPT_DIR}/paraphrase_corpus.py"

run_gate "[5/8] Contract tests (structure + checkable claims)" \
  python3 -m pytest "${TEST_DIR}/test_skill_contract.py" -q

run_gate "[6/8] Golden scenarios (detector expectations + verified facts)" \
  python3 -m pytest "${TEST_DIR}/test_golden_scenarios.py" -q

run_gate "[7/8] Model-eval grader calibration (offline, no model needed)" \
  python3 "${SCRIPT_DIR}/model_eval.py" --calibrate

run_gate "[8/8] Coverage doc freshness (generated, never hand-maintained)" \
  python3 "${SCRIPT_DIR}/gen_coverage.py" --check

echo ""
if [ "${FAILED}" -eq 0 ]; then
  echo "kafka-event-driven-design: all 8 gates passed."
  exit 0
fi
echo "kafka-event-driven-design: one or more gates FAILED (see above)."
exit 1
