#!/usr/bin/env bash
#
# Live forward A/B evaluation: given this skill, does a model actually classify
# the repository shape, classify every job's execution path, honour the Output
# Contract, and refuse to claim validation that did not run?
#
# Everything else in this skill's suite is deterministic and model-free. That
# proves the rules exist in SKILL.md, that the discovery probe reports what it
# claims, and that every reference YAML block parses and lints. It does NOT
# prove that a model reading the skill complies with it. This script measures
# that, and only that.
#
# Grading is still deterministic. There is no model judging a model: every axis
# is extracted as DATA from the response and compared against the golden
# fixture's own `expected_shape` / `expected_execution_paths` /
# `expected_output_fields`.
#
# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------
#
#   bash scripts/run_live_eval.sh --dry-run     # no model; grader self-check
#
#   export GO_CI_WORKFLOW_EVAL_CMD='claude -p --strict-mcp-config --permission-mode dontAsk'
#   bash scripts/run_live_eval.sh                                  # with-skill arm
#   GO_CI_WORKFLOW_EVAL_ARM=without-skill bash scripts/run_live_eval.sh   # control arm
#
# The command must read a prompt on stdin and write the assistant response to
# stdout, with the working directory as the repository under test.
#
# Environment:
#   GO_CI_WORKFLOW_EVAL_CMD   required for a live run; the model command
#   GO_CI_WORKFLOW_EVAL_ARM   with-skill (default) | without-skill
#   GO_CI_WORKFLOW_EVAL_OUT   directory for the per-scenario result JSON, so
#                             two arms can be diffed mechanically
#
# ---------------------------------------------------------------------------
# Isolation notes, measured on Claude Code 2.1.220
# ---------------------------------------------------------------------------
#   - A nested `claude -p` does NOT inherit the parent session's credentials.
#     It needs its own authenticated login, or it prints "Not logged in" and
#     the response is empty. Run this from an authenticated terminal.
#   - It DOES inherit user-level plugin hooks. A failing SessionEnd hook aborts
#     the run AFTER the model has already answered, so the work is lost and the
#     scenario looks like a command failure. Fix the hook; do not work around
#     it with --bare (see below).
#   - It inherits the working directory and the CLAUDE.md files that apply to
#     it. The run happens in a temp repository, so the parent project's
#     CLAUDE.md does not apply, but the user-level ~/.claude/CLAUDE.md still
#     does and is a confound worth naming whenever you report numbers.
#   - `--strict-mcp-config` keeps interactively-authenticated MCP servers out.
#
#   - NEVER use `--bare`. It skips the skill directory walk, which disables the
#     exact thing under test: the with-skill arm would silently become a second
#     control arm and the A/B would produce a bogus null result. It also skips
#     the credential path, so it trades a hook problem for an auth problem.
#     Both measured on Claude Code 2.1.220.
#
#   - Because a silently-unloaded skill is indistinguishable from a skill that
#     did not help, the with-skill arm ASSERTS ITS TREATMENT: after each run the
#     response must show the closed vocabulary that only SKILL.md defines (at
#     least two Mandatory Gate names and at least one execution-path label). If
#     it does not, this script exits as a SETUP failure and grades nothing.
#
#   - The with-skill arm INSTALLS the skill at
#     <repo>/.claude/skills/go-ci-workflow and invokes `/go-ci-workflow`.
#     Pasting SKILL.md into the prompt would measure a different artifact: no
#     ${CLAUDE_SKILL_DIR} resolution, no allowed-tools, no on-demand references,
#     and no runnable discovery script. Note that a project-level skill requires
#     accepting the workspace trust dialog, so a non-interactive run may need
#     that pre-accepted.
#     The install is an ALLOW-LIST, not "copy everything then delete tests":
#     a blocklist silently regains a leak the next time a file is added, and
#     this skill's scripts/tests/ holds the very fixtures the model is scored
#     against.
#
# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------
# Derived from scripts/tests/golden/*.json — the same fixtures the offline
# suite uses. There is no second, hand-written scenario list to drift out of
# sync. Each prompt is built from the fixture's `context` plus the SITUATION
# half of its `description`; the half after the em dash states what the skill
# should do and is withheld, because fixture 006 literally names a Mandatory
# Gate there. A tripwire in the harness refuses to run if that half ever leaks
# behavioural vocabulary into a prompt.
#
# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------
#   0  everything graded passed
#   1  something graded failed — a real result about the skill (or, under
#      --dry-run, about the grader)
#   3  SETUP failure: nothing was graded. Never report 3 as a skill result;
#      a setup failure is not a score of 0, and a score of 0 is not a setup
#      failure.
#
#   Why 3 and not the 2 used by the sibling harnesses (update-doc,
#   incident-postmortem): bash itself exits 2 for a syntax error or a misused
#   builtin, so a future `set -u` unbound-variable abort in this script would be
#   indistinguishable from a deliberate setup abort. 3 is unambiguous.
#
# ---------------------------------------------------------------------------
# Portability: macOS/BSD stock tooling only. No GNU `timeout`, no `xargs -d`,
# no in-place `sed`. Anything that needs real logic is done in Python.
# ---------------------------------------------------------------------------

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
SKILL_MD="${SKILL_DIR}/SKILL.md"
GOLDEN_DIR="${SKILL_DIR}/scripts/tests/golden"
DISCOVER="${SKILL_DIR}/scripts/discover_ci_needs.sh"
ARM="${GO_CI_WORKFLOW_EVAL_ARM:-with-skill}"
SETUP_RC=3

DRY_RUN=0
for arg in "$@"; do
  case "${arg}" in
    --dry-run) DRY_RUN=1 ;;
    -h|--help)
      # Only the leading comment block. `grep -E '^#'` also printed every
      # column-0 comment inside the embedded python, turning --help into 164
      # lines of grader internals. No interval expressions: BSD awk on stock
      # macOS does not support them.
      awk 'NR==1 && /^#!/ {next} /^#/ {sub(/^# ?/, ""); print; next} {exit}' \
        "${BASH_SOURCE[0]}"
      exit 0
      ;;
    *)
      echo "unknown argument: ${arg} (try --help)" >&2
      exit "${SETUP_RC}"
      ;;
  esac
done

WORK="$(mktemp -d "${TMPDIR:-/tmp}/go-ci-workflow-eval.XXXXXX")" || {
  echo "setup: could not create a working directory" >&2; exit "${SETUP_RC}"; }
HARNESS="${WORK}/harness.py"

setup_fail() {
  echo "" >&2
  echo "  ABORT — SETUP FAILURE (nothing was graded)" >&2
  echo "  reason: $*" >&2
  echo "" >&2
  echo "  This is NOT a skill result. A setup failure reported as a score of 0" >&2
  echo "  is indistinguishable from a model that answered badly. Fix the" >&2
  echo "  runner, then re-run." >&2
  echo "  artifacts: ${WORK}" >&2
  exit "${SETUP_RC}"
}

# Checked BEFORE any setup work: a missing command must abort immediately and
# unmistakably, never after a page of output that could be mistaken for a run.
if [[ "${DRY_RUN}" -eq 0 && -z "${GO_CI_WORKFLOW_EVAL_CMD:-}" ]]; then
  cat >&2 <<'MSG'

  ABORT — SETUP FAILURE (nothing was graded)
  reason: GO_CI_WORKFLOW_EVAL_CMD is not set, so no model was invoked.

  This is exit 3, a setup failure — not a skill result, and NOT a score of 0.
  Nothing was measured; do not record it as either a pass or a failure.

    export GO_CI_WORKFLOW_EVAL_CMD='claude -p --strict-mcp-config --permission-mode dontAsk'
    bash scripts/run_live_eval.sh

  A nested `claude -p` needs its own login; it does not inherit the parent
  session's credentials. Run this from an authenticated terminal.

  To verify the harness and the grader without a model:

    bash scripts/run_live_eval.sh --dry-run
MSG
  exit "${SETUP_RC}"
fi

if [[ "${DRY_RUN}" -eq 0 ]]; then
  case "${ARM}" in
    with-skill|without-skill) ;;
    *) setup_fail "GO_CI_WORKFLOW_EVAL_ARM must be with-skill or without-skill, got '${ARM}'. A typo would otherwise run the control arm under a treatment label." ;;
  esac
fi

# The grader and the scenario builder live in one embedded program: the runner
# and the grader must never drift apart, and the skill ships one new executable
# rather than three.
# The grader is a real file, not a heredoc: a 960-line Python program living
# inside a bash string cannot be linted or imported, and the tests had to
# extract it to a temp file before they could exercise it. It is copied into
# the work dir so the run is hermetic and the rest of this script is unchanged.
cp "${SCRIPT_DIR}/live_eval_grader.py" "${HARNESS}"

h() { python3 "${HARNESS}" --skill-md "${SKILL_MD}" "$@"; }

# ---------------------------------------------------------------------------
# Step 1 — derive the scenarios (both modes). This also validates that SKILL.md
# still defines the four closed vocabularies the grader parses out of it, and
# that no fixture leaks its expected behaviour into a prompt.
# ---------------------------------------------------------------------------
SCEN_DIR="${WORK}/scenarios"
echo "============================================================"
echo "  go-ci-workflow live forward eval"
if [[ "${DRY_RUN}" -eq 1 ]]; then
  echo "  mode: --dry-run (recorded responses; no model is invoked)"
else
  echo "  mode: live   arm: ${ARM}"
fi
echo "============================================================"
echo ""
h derive --golden "${GOLDEN_DIR}" --out "${SCEN_DIR}" \
  || setup_fail "scenario derivation refused (see above)"

scenarios=()
while IFS= read -r f; do
  [[ -n "${f}" ]] && scenarios+=("${f}")
done < <(find "${SCEN_DIR}" -maxdepth 1 -name '*.json' | sort)
[[ ${#scenarios[@]} -gt 0 ]] || setup_fail "no scenarios derived from ${GOLDEN_DIR}"
echo ""

# ---------------------------------------------------------------------------
# Step 2 — materialise every scenario's repository and prove the skill's own
# discovery probe can read it (both modes). A prompt that describes a repo the
# model cannot inspect measures reading comprehension, not the skill.
# ---------------------------------------------------------------------------
echo "materialising ${#scenarios[@]} fixture repositories"
for scenario in "${scenarios[@]}"; do
  name="$(basename "${scenario}" .json)"
  repo="${WORK}/repos/${name}"
  mkdir -p "${repo}"
  h materialize --scenario "${scenario}" --repo "${repo}" \
    || setup_fail "could not materialise ${name}"
  last="$(bash "${DISCOVER}" "${repo}" 2>/dev/null | tail -1)"
  case "${last}" in
    *probe-complete*) ;;
    *) setup_fail "discover_ci_needs.sh did not complete on ${name}; its last line was: ${last}" ;;
  esac
done
echo "  all repositories readable by discover_ci_needs.sh (probe-complete)"
echo ""

scenario_for() {
  # $1 = fixture id -> derived scenario path
  local p="${SCEN_DIR}/$1.json"
  [[ -f "${p}" ]] || setup_fail "recording targets fixture '$1', which is not among the derived scenarios"
  printf '%s' "${p}"
}

# ===========================================================================
# DRY RUN — exercise the entire harness and grader with recorded responses.
# This is the layer that can be verified without credentials, and it is the
# layer that proves the grader can FAIL. A grader that cannot fail is worthless.
# ===========================================================================
if [[ "${DRY_RUN}" -eq 1 ]]; then
  recordings=()
  while IFS= read -r f; do
    [[ -n "${f}" ]] && recordings+=("${f}")
  done < <(find "${GOLDEN_DIR}" -maxdepth 1 -name 'live_eval_*.md' | sort)
  [[ ${#recordings[@]} -gt 0 ]] \
    || setup_fail "no recorded responses (${GOLDEN_DIR}/live_eval_*.md) to replay"

  RES_GOOD="${WORK}/results/replay-good"
  RES_BAD="${WORK}/results/replay-bad"
  mkdir -p "${RES_GOOD}" "${RES_BAD}"
  good_json=""
  bad_json=""
  selfcheck_failures=0
  graded=0

  for rec in "${recordings[@]}"; do
    rec_name="$(basename "${rec}" .md)"
    fixture="$(h meta --response "${rec}" --key fixture)" \
      || setup_fail "recording ${rec_name} has no usable header"
    rec_arm="$(h meta --response "${rec}" --key arm)"
    expect="$(h meta --response "${rec}" --key expect)"
    scen="$(scenario_for "${fixture}")"

    echo "=== ${rec_name} (fixture ${fixture}, arm ${rec_arm}, expect ${expect}) ==="

    out=""
    case "${rec_arm}" in
      replay-good) out="${RES_GOOD}/${fixture}.json"; good_json="${out}" ;;
      replay-bad)  out="${RES_BAD}/${fixture}.json";  bad_json="${out}" ;;
      *)           out="${WORK}/results/${rec_name}.json"; mkdir -p "${WORK}/results" ;;
    esac

    h grade --scenario "${scen}" --response "${rec}" --arm "${rec_arm}" --json "${out}"
    grade_rc=$?
    graded=$((graded + 1))

    # The treatment assertion is replayed through the SAME code path the live
    # with-skill arm uses, so --dry-run proves the guard actually fires rather
    # than merely existing.
    h treatment --response "${rec}" >/dev/null 2>&1
    treat_rc=$?

    case "${expect}" in
      pass)
        if [[ ${grade_rc} -ne 0 ]]; then
          echo "  SELF-CHECK FAILED: the reference response must pass every axis." >&2
          selfcheck_failures=$((selfcheck_failures + 1))
        fi
        if [[ ${treat_rc} -ne 0 ]]; then
          echo "  SELF-CHECK FAILED: the reference response must satisfy the treatment assertion." >&2
          selfcheck_failures=$((selfcheck_failures + 1))
        fi
        ;;
      fail)
        if [[ ${grade_rc} -eq 0 ]]; then
          echo "  SELF-CHECK FAILED: the defective response was graded as a pass." >&2
          selfcheck_failures=$((selfcheck_failures + 1))
        fi
        ;;
      setup-abort)
        if [[ ${treat_rc} -ne ${SETUP_RC} ]]; then
          echo "  SELF-CHECK FAILED: an untreated response must abort the with-skill arm" >&2
          echo "    as a SETUP failure (exit ${SETUP_RC}); the assertion returned ${treat_rc}." >&2
          selfcheck_failures=$((selfcheck_failures + 1))
        else
          echo "  treatment  correctly refused this arm (exit ${SETUP_RC}, nothing graded)"
        fi
        ;;
      *)
        setup_fail "recording ${rec_name} declares an unknown expect: ${expect}"
        ;;
    esac
    echo ""
  done

  # The two arms differ ONLY in the planted defect, so a grader that moves a
  # control axis is reacting to length or tone, not to the defect.
  [[ -n "${good_json}" && -n "${bad_json}" ]] \
    || setup_fail "the replay corpus needs one replay-good and one replay-bad recording"
  h compare --good "${good_json}" --bad "${bad_json}" \
    --axes parity,integrity --margin 0.5 \
    || selfcheck_failures=$((selfcheck_failures + 1))
  echo ""

  h summarize --results "${RES_GOOD}" --arm replay-good
  echo ""
  h summarize --results "${RES_BAD}" --arm replay-bad
  echo ""
  echo "  artifacts: ${WORK}"
  echo ""
  if [[ ${selfcheck_failures} -ne 0 ]]; then
    echo "DRY-RUN SELF-CHECK FAILED (${selfcheck_failures} problem(s))."
    echo "Do not run a live arm until the grader discriminates again: its numbers"
    echo "would not mean anything."
    echo "LIVE-EVAL-COMPLETE arms=2 scenarios=${#scenarios[@]} graded=${graded} mode=dry-run result=selfcheck-failed"
    exit 1
  fi
  echo "Dry run complete. The grader passes the reference response, fails the"
  echo "defective twin on exactly the planted axes, and refuses an untreated arm."
  echo "Set GO_CI_WORKFLOW_EVAL_CMD and re-run without --dry-run to measure a model."
  echo "LIVE-EVAL-COMPLETE arms=2 scenarios=${#scenarios[@]} graded=${graded} mode=dry-run result=ok"
  exit 0
fi

# ===========================================================================
# LIVE RUN
# ===========================================================================
RESULT_DIR="${GO_CI_WORKFLOW_EVAL_OUT:-${WORK}/results/${ARM}}"
mkdir -p "${RESULT_DIR}"

failures=0
measured=0

for scenario in "${scenarios[@]}"; do
  name="$(basename "${scenario}" .json)"
  repo="${WORK}/repos/${name}"
  prompt="$(h prompt --scenario "${scenario}")" \
    || setup_fail "could not build the prompt for ${name}"

  if [[ "${ARM}" == "with-skill" ]]; then
    install="${repo}/.claude/skills/go-ci-workflow"
    mkdir -p "${install}/references" "${install}/scripts"
    cp "${SKILL_MD}" "${install}/SKILL.md" || setup_fail "install failed for ${name}"
    cp "${SKILL_DIR}"/references/*.md "${install}/references/" \
      || setup_fail "install failed for ${name}"
    # discover_ci_needs.sh is the only script a user-facing run needs: SKILL.md
    # § Mandatory Gates tells the model to run it and the frontmatter grants
    # Bash(bash ${CLAUDE_SKILL_DIR}/scripts/discover_ci_needs.sh*).
    cp "${DISCOVER}" "${install}/scripts/discover_ci_needs.sh" \
      || setup_fail "install failed for ${name}"
    prompt="/go-ci-workflow ${prompt}"

    leaked="$(find "${install}" -type f \
      ! -name 'SKILL.md' \
      ! -path "${install}/references/*.md" \
      ! -name 'discover_ci_needs.sh' -print)"
    if [[ -n "${leaked}" ]]; then
      setup_fail "harness files leaked into the installed skill (the model could read the checks it is scored against):
${leaked}"
    fi

    # Contamination probe: the installed skill must be invisible to the
    # scenario's own discovery, or the shape and task-entrypoint rows would
    # describe the measuring instrument instead of the repository under test.
    contaminated="$(bash "${DISCOVER}" "${repo}" 2>/dev/null | grep -c '\.claude/')"
    if [[ "${contaminated:-0}" -ne 0 ]]; then
      setup_fail "installed skill is visible to discover_ci_needs.sh on ${name} (${contaminated} rows mention .claude/)"
    fi
  fi

  echo "=== ${name} (${ARM}) ==="
  response="${WORK}/response-${name}.md"
  if ! (cd "${repo}" && printf '%s' "${prompt}" | eval "${GO_CI_WORKFLOW_EVAL_CMD}") \
       > "${response}" 2>"${WORK}/stderr-${name}.log"; then
    echo "  last stderr lines:" >&2
    tail -5 "${WORK}/stderr-${name}.log" >&2
    setup_fail "the eval command failed on ${name}"
  fi
  if [[ ! -s "${response}" ]]; then
    echo "  last stderr lines:" >&2
    tail -5 "${WORK}/stderr-${name}.log" >&2
    setup_fail "the eval command produced an EMPTY response for ${name} (most often: the nested CLI is not logged in)"
  fi

  # Assert the treatment BEFORE grading. A with-skill arm that did not load the
  # skill is a second control arm; grading it would publish a bogus null result
  # as a fact about the skill.
  if [[ "${ARM}" == "with-skill" ]]; then
    h treatment --response "${response}"
    if [[ $? -ne 0 ]]; then
      echo "       scenario: ${name}" >&2
      echo "       response: ${response}" >&2
      setup_fail "the with-skill arm was not treated on ${name} (see above)"
    fi
  fi

  measured=$((measured + 1))
  h grade --scenario "${scenario}" --response "${response}" --arm "${ARM}" \
    --json "${RESULT_DIR}/${name}.json" || failures=$((failures + 1))
  echo ""
done

h summarize --results "${RESULT_DIR}" --arm "${ARM}"
echo ""
echo "  results:   ${RESULT_DIR}"
echo "  artifacts: ${WORK}"
echo ""
echo "Compare arms axis by axis: re-run with GO_CI_WORKFLOW_EVAL_ARM=without-skill"
echo "and diff the two result directories. One arm scored against nothing says"
echo "nothing about the skill's contribution, and a single blended number hides"
echo "which axis actually moved."
echo "LIVE-EVAL-COMPLETE arms=1 scenarios=${#scenarios[@]} graded=${measured} mode=live arm=${ARM}"

[[ ${failures} -eq 0 ]] || exit 1
