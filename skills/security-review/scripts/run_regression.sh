#!/usr/bin/env bash
# Fail closed, and never overstate coverage.
#
# Two failure modes this guards against:
#   1. Reporting "passed" after a validation failure  -> false assurance.
#   2. Reporting a bare "passed" when checks were SKIPPED (no validator, no Go, no Node)
#      -> also false assurance, just quieter. The final verdict distinguishes
#      PASS / PASS WITH SKIPS / FAIL, and STRICT=1 turns any skip into a failure
#      so CI can demand full coverage.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
VALIDATOR="${SKILL_CREATOR_VALIDATOR:-$HOME/.codex/skills/.system/skill-creator/scripts/quick_validate.py}"
STRICT="${STRICT:-0}"

SKIPS=()
note_skip() { SKIPS+=("$1"); echo "  SKIPPED: $1"; }

echo "=== security-review regression suite ==="
[[ "${STRICT}" == "1" ]] && echo "(STRICT=1: any skip is a failure)"
echo ""

echo "[1/3] Validate skill frontmatter"
if [[ -f "${VALIDATOR}" ]]; then
  # No `|| echo` here — a validation failure must abort the run via set -e.
  python3 "${VALIDATOR}" "${SKILL_DIR}"
else
  note_skip "frontmatter validation (validator not found at ${VALIDATOR}; set SKILL_CREATOR_VALIDATOR)"
fi
echo ""

echo "[2/3] Run contract tests (SKILL.md structure + references)"
python3 -m unittest discover -s "${SKILL_DIR}/scripts/tests" -p "test_skill_contract.py" -v
echo ""

echo "[3/3] Run golden, forward-eval, and executable-example tests"

# Explicit template under TMPDIR: a bare `mktemp` resolves to /var/folders/... on macOS and
# fails with "Operation not permitted" under a sandboxed run.
LOGDIR="$(mktemp -d "${TMPDIR:-/tmp}/security-review-logs.XXXXXX")"
trap 'rm -rf "${LOGDIR}"' EXIT

# Read unittest's STRUCTURED summary, not a grep of the whole log. Grepping for
# "skipped|SKIP" matched this suite's own docstrings (which discuss skipped checks) and
# invented a phantom skip on a fully green run.
run_suite() {
  local pattern="$1" label="$2" log="${LOGDIR}/${2//[^A-Za-z0-9]/_}.log"
  python3 -m unittest discover -s "${SKILL_DIR}/scripts/tests" -p "${pattern}" -v 2>&1 | tee "${log}"
  # unittest's final line is "OK", "OK (skipped=N)", or "FAILED (...)".
  local n
  n="$(sed -nE 's/^OK \(.*skipped=([0-9]+).*\)$/\1/p' "${log}" | tail -1)"
  if [[ -n "${n}" && "${n}" -gt 0 ]]; then
    # Attribute the known cause instead of emitting a second, vaguer line for the same gap.
    if [[ "${label}" == "forward eval" && -z "${SECURITY_REVIEW_EVAL_CMD:-}" ]]; then
      note_skip "live model forward-eval not configured (${n} test; set SECURITY_REVIEW_EVAL_CMD)"
    else
      note_skip "${label}: ${n} test(s) skipped (see [3/3] output)"
    fi
  fi
}

run_suite "test_golden_reviews.py"       "golden fixtures"
run_suite "test_forward_eval.py"         "forward eval"
run_suite "test_examples_executable.py"  "executable examples"
echo ""

# Toolchain absence is reported separately: without these, whole verification layers vanish
# and the per-suite skip count above is what surfaces it.
command -v go   >/dev/null 2>&1 || note_skip "Go example verification (go not installed)"
command -v node >/dev/null 2>&1 || note_skip "Node example verification (node not installed)"

echo "=== verdict ==="
if [[ ${#SKIPS[@]} -eq 0 ]]; then
  echo "PASS — all checks executed"
  exit 0
fi

echo "PASS WITH SKIPS — ${#SKIPS[@]} check(s) did not run:"
for s in "${SKIPS[@]}"; do echo "  - ${s}"; done
echo ""
echo "These are gaps in verification, not evidence of correctness."

if [[ "${STRICT}" == "1" ]]; then
  echo "FAIL — STRICT=1 requires every check to run"
  exit 1
fi
exit 0
