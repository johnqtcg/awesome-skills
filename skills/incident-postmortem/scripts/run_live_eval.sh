#!/usr/bin/env bash
#
# Live forward evaluation: given this skill, does a model actually select the right
# mode, degrade honestly, pick an RCA technique that fits the incident, redact
# secrets, and refuse to invent evidence?
#
# Everything else in this skill's suite is deterministic and model-free. That proves
# the rules exist, that the linter behaves on real documents, and that every golden
# fixture matches its declared lint expectation. It does NOT prove the above, which
# is the skill's actual job. This script measures it.
#
# Grading is still deterministic: scripts/grade_postmortem_eval.py uses regexes,
# section lookups and the bundled linter. There is no model judging a model.
#
# Requires an authenticated CLI supplied via INCIDENT_PM_EVAL_CMD. The command must
# read a prompt on stdin and write the response to stdout, with the working directory
# holding the scenario's evidence files:
#
#   export INCIDENT_PM_EVAL_CMD='claude -p --strict-mcp-config --permission-mode dontAsk'
#   bash scripts/run_live_eval.sh
#
# Isolation notes (same constraints the update-doc harness documents):
#   - A nested `claude -p` does NOT inherit the parent session's credentials. Run it
#     from an authenticated terminal or it prints "Not logged in" and returns empty.
#   - It DOES inherit user-level plugin hooks; a failing hook can abort the run after
#     the model already answered.
#   - `--bare` skips hooks but also skips the credential path — fix the hook instead.
#   - `--strict-mcp-config` keeps interactively-authenticated MCP servers out.
#   - The parent's project CLAUDE.md does not apply (the run happens in a temp dir),
#     but user-level ~/.claude/CLAUDE.md still does and is a confound worth naming
#     whenever you report numbers.
#   - The with-skill arm INSTALLS the skill at <dir>/.claude/skills/incident-postmortem
#     and invokes `/incident-postmortem`. Pasting SKILL.md into the prompt would
#     measure a different artifact: no allowed-tools, no on-demand references.
#
# Exit codes:
#   0  every scenario passed grading
#   1  at least one scenario failed grading — a real result about the skill
#   2  setup failure (no command configured, CLI missing, empty response).
#      Never report 2 as a skill result: nothing was measured.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
EVAL_DIR="${SKILL_DIR}/scripts/tests/eval"
GRADER="${SKILL_DIR}/scripts/grade_postmortem_eval.py"
ARM="${INCIDENT_PM_EVAL_ARM:-with-skill}"

if [[ -z "${INCIDENT_PM_EVAL_CMD:-}" ]]; then
  cat >&2 <<'MSG'
setup: INCIDENT_PM_EVAL_CMD is not set, so no live evaluation ran.

  This is a setup failure (exit 2), not a skill result. Nothing was measured; do not
  record it as either a pass or a failure.

  export INCIDENT_PM_EVAL_CMD='claude -p --strict-mcp-config --permission-mode dontAsk'

  A nested `claude -p` needs its own login; it does not inherit the parent session's
  credentials. Run this from an authenticated terminal.
MSG
  exit 2
fi

scenarios=()
while IFS= read -r f; do
  [[ -n "$f" ]] && scenarios+=("$f")
done < <(find "${EVAL_DIR}" -maxdepth 1 -name 'scenario_*.json' | sort)

if [[ ${#scenarios[@]} -eq 0 ]]; then
  echo "setup: no scenarios under ${EVAL_DIR}" >&2
  exit 2
fi

failures=0
measured=0
# Per-scenario JSON lands here so two arms can be diffed mechanically.
RESULT_DIR="${INCIDENT_PM_EVAL_OUT:-$(mktemp -d "${TMPDIR:-/tmp}/incident-pm-results.XXXXXX")}"
mkdir -p "${RESULT_DIR}"

for scenario in "${scenarios[@]}"; do
  name="$(basename "${scenario}" .json)"
  workdir="$(mktemp -d "${TMPDIR:-/tmp}/incident-pm-eval.XXXXXX")"
  workspace="${workdir}/incident"
  mkdir -p "${workspace}"

  python3 - "$scenario" "$workspace" <<'PY'
import json, pathlib, sys
scenario = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
root = pathlib.Path(sys.argv[2])
for rel, content in scenario.get("materials", {}).items():
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
PY

  prompt="$(python3 -c "
import json,sys
print(json.load(open(sys.argv[1], encoding='utf-8'))['prompt'])" "$scenario")"

  if [[ "${ARM}" == "with-skill" ]]; then
    # Copy an ALLOW-LIST, not the whole directory minus a blocklist. `cp -R` followed by
    # `rm -rf scripts/tests` left the grader, this runner and even a compiled
    # __pycache__/grade_postmortem_eval.pyc inside the skill the model can read — so the
    # model could have read the checks it was being scored against. An allow-list cannot
    # silently regain a leak when a new file is added to the skill.
    install="${workspace}/.claude/skills/incident-postmortem"
    mkdir -p "${install}/references" "${install}/scripts"
    cp "${SKILL_DIR}/SKILL.md" "${install}/SKILL.md"
    cp "${SKILL_DIR}"/references/*.md "${install}/references/"
    # lint_postmortem.py is the only script a user-facing run needs: SKILL.md §8 tells
    # the model to run it, and the frontmatter grants Bash(*lint_postmortem.py*).
    cp "${SKILL_DIR}/scripts/lint_postmortem.py" "${install}/scripts/lint_postmortem.py"
    prompt="/incident-postmortem ${prompt}"

    # Fail loudly rather than measure a contaminated run.
    leaked="$(find "${install}" -type f \
      ! -name 'SKILL.md' \
      ! -path "${install}/references/*.md" \
      ! -name 'lint_postmortem.py' -print)"
    if [[ -n "${leaked}" ]]; then
      echo "setup: harness files leaked into the installed skill:" >&2
      echo "${leaked}" >&2
      exit 2
    fi
  fi

  echo "=== ${name} (${ARM}) ==="
  response="${workdir}/response.md"
  if ! (cd "${workspace}" && printf '%s' "${prompt}" | eval "${INCIDENT_PM_EVAL_CMD}") \
       > "${response}" 2>"${workdir}/stderr.log"; then
    echo "setup: eval command failed for ${name}; see ${workdir}/stderr.log" >&2
    tail -5 "${workdir}/stderr.log" >&2
    exit 2
  fi
  if [[ ! -s "${response}" ]]; then
    echo "setup: eval command produced an empty response for ${name}" >&2
    exit 2
  fi

  measured=$((measured + 1))
  python3 "${GRADER}" "${scenario}" "${response}" \
    --json "${RESULT_DIR}/${name}.json" || failures=$((failures + 1))
  echo "  artifacts: ${workdir}"
  echo
done

# Scenario counts alone cannot show improvement: two arms can fail the same two
# scenarios while one fails 3 checks and the other 15. Aggregate at CHECK level and
# write JSON so two runs can be diffed mechanically.
python3 "${SCRIPT_DIR}/summarize_eval.py" "${RESULT_DIR}" \
  --arm "${ARM}" --measured "${measured}" --failed "${failures}"

echo
echo "Compare arms by re-running with INCIDENT_PM_EVAL_ARM=without-skill, then diffing"
echo "the two summary.json files. A skill that helps must fail strictly fewer CHECKS —"
echo "scenario counts are too coarse to show it, and one arm scored against nothing"
echo "tells you nothing about the skill's contribution."

[[ ${failures} -eq 0 ]] || exit 1
