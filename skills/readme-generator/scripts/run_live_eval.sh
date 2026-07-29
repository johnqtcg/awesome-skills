#!/usr/bin/env bash
# Run the live forward evaluation: drive a real model through SKILL.md against each
# fixture repository and grade what it produces with scripts/lint_readme.py.
#
# This is the one layer the default suite cannot cover. Everything else proves the rules
# exist, routing is correct, the grader discriminates, and the shipped golden examples
# clear that grader. Only this shows a live model complies.
#
# Exit codes are deliberately distinct:
#   0  every fixture produced a README with zero findings
#   1  the model ran and its output was rejected — a real skill result
#   2  Harness Setup Failure: nothing was graded, do not read this as a skill result
#
# Usage:
#   bash scripts/run_live_eval.sh                       # uses `claude -p --model sonnet`
#   READMEer_MODEL=opus bash scripts/run_live_eval.sh   # different model
#   README_GEN_EVAL_CMD='<your cmd>' bash scripts/run_live_eval.sh
#
# Requirements: an AUTHENTICATED CLI. A sandboxed subprocess without credentials exits
# `Not logged in`, which the suite reports as a HARNESS FAULT failure rather than a skip —
# a broken harness must never read as green.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
MODEL="${READMEer_MODEL:-sonnet}"
PROBE_TIMEOUT="${READMEer_PROBE_TIMEOUT:-180}"
: "${README_GEN_EVAL_CMD:=claude -p --model ${MODEL} --permission-mode bypassPermissions}"
export README_GEN_EVAL_CMD

echo "============================================"
echo "  readme-generator live forward eval"
echo "  model command: ${README_GEN_EVAL_CMD}"
echo "============================================"

# The probe is ALLOW-list, not deny-list. Matching known auth-error strings let a missing
# binary, a timeout, or any other init failure print "probe OK" and then fail later as an
# ordinary test failure — the exact harness-vs-skill confusion this layer exists to
# prevent. Pass requires BOTH: exit 0, AND the sentinel on a line of its own.
#
# Run it through Python rather than `timeout(1)`: that binary is GNU coreutils and is
# absent from stock macOS, so the shell version either exited 127 (blaming the eval
# command for the shim's own absence) or, with the fallback, waited forever.
# `shell=True` matches how the test layer invokes the same command, so the probe vouches
# for the path that actually runs.
probe_out="$(READMEer_PROBE_TIMEOUT="${PROBE_TIMEOUT}" python3 - <<'PROBE' 2>&1
import os, subprocess, sys

cmd = os.environ["README_GEN_EVAL_CMD"]
try:
    proc = subprocess.run(
        cmd, shell=True, input="Reply with exactly one word: READY",
        capture_output=True, text=True,
        timeout=float(os.environ.get("READMEer_PROBE_TIMEOUT", "180")),
    )
except subprocess.TimeoutExpired:
    print("probe timed out", file=sys.stderr)
    sys.exit(124)
sys.stdout.write(proc.stdout)
sys.stderr.write(proc.stderr)
sys.exit(proc.returncode)
PROBE
)"
probe_rc=$?

abort_setup() {
  echo ""
  echo "  ABORT — Harness Setup Failure (nothing was graded)."
  echo "  reason: $1"
  echo "  probe exit: ${probe_rc}"
  echo "  probe output (first 3 lines):"
  printf '%s\n' "${probe_out}" | head -3 | sed 's/^/    /'
  echo ""
  echo "  This is NOT a skill result. Fix the runner, then re-run."
  echo "  Most common cause: the CLI is not authenticated — log in interactively"
  echo "  (/login) or export an API key."
  exit 2
}

if [[ ${probe_rc} -eq 124 ]]; then
  abort_setup "probe timed out after ${PROBE_TIMEOUT}s"
elif [[ ${probe_rc} -eq 127 ]]; then
  abort_setup "eval command not found on PATH"
elif [[ ${probe_rc} -ne 0 ]]; then
  abort_setup "probe exited non-zero"
# Whole-line match. `grep -q READY` also accepted NOT_READY, UNREADY and READY-ish, so
# the "exact sentinel" the comment promised was really a substring search.
elif ! printf '%s\n' "${probe_out}" | grep -Eq '^[[:space:]]*READY[[:space:]]*$'; then
  abort_setup "probe exited 0 but never produced a line containing only READY"
fi

echo ""
echo "auth probe OK (exit 0 + READY on its own line)"
echo ""

python3 -m pytest "${SKILL_DIR}/scripts/tests/test_forward_eval.py" \
  -k LiveForwardEval -v
rc=$?

echo ""
if [[ ${rc} -eq 0 ]]; then
  echo "  Live forward eval PASSED for all fixture project types."
  echo "  Record the model + date in scripts/tests/COVERAGE.md § Known Gaps."
else
  echo "  Live forward eval FAILED. Read the findings above: each one names the"
  echo "  README claim and the repository fact that contradicts it."
fi
exit ${rc}
