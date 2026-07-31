#!/usr/bin/env bash
#
# Live forward evaluation: does a model, given this skill, actually produce a
# grounded documentation update?
#
# Everything else in this skill's test suite is deterministic and model-free.
# That proves the rules exist, the discovery script reports the right scope, and
# the grader can tell a grounded update from a fabricated one. It does NOT prove
# the third thing, which is what this script measures.
#
# Requires an authenticated CLI, supplied via UPDATE_DOC_EVAL_CMD. The command
# must accept a prompt on stdin and write the assistant response to stdout, with
# the working directory as the repository under test. Example:
#
#   export UPDATE_DOC_EVAL_CMD='claude -p --strict-mcp-config --permission-mode dontAsk'
#   bash scripts/run_live_eval.sh
#
# Isolation notes, measured on Claude Code 2.1.220:
#   - A nested `claude -p` does NOT inherit the parent session's credentials. It
#     needs its own authenticated login, or it prints "Not logged in" and the
#     response is empty. Run this from an authenticated terminal.
#   - It DOES inherit user-level plugin hooks. A failing SessionEnd hook aborts
#     the run after the model has already answered.
#   - `--bare` skips hooks, LSP and plugins, but also skips the credential path,
#     so it trades the hook problem for an auth problem. Fix the hook instead.
#   - `--strict-mcp-config` keeps interactively-authenticated MCP servers out.
#   - The parent's project CLAUDE.md is not inherited because the run happens in
#     a temp repo, but the user-level ~/.claude/CLAUDE.md still applies and is a
#     confound worth naming when reporting numbers.
#   - The with-skill arm INSTALLS the skill at <repo>/.claude/skills/update-doc
#     and invokes it as `/update-doc`. Pasting SKILL.md into the prompt instead
#     would measure a different artifact — no ${CLAUDE_SKILL_DIR} resolution, no
#     allowed-tools, no on-demand references, no runnable discovery script.
#     Note that a project-level skill requires accepting the workspace trust
#     dialog, so a non-interactive run may need that pre-accepted.
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
GRADER="${SKILL_DIR}/scripts/grade_doc_update.py"
ARM="${UPDATE_DOC_EVAL_ARM:-with-skill}"

if [[ -z "${UPDATE_DOC_EVAL_CMD:-}" ]]; then
  cat >&2 <<'MSG'
setup: UPDATE_DOC_EVAL_CMD is not set, so no live evaluation ran.

  This is a setup failure (exit 2), not a skill result. Nothing was measured;
  do not record it as either a pass or a failure.

  export UPDATE_DOC_EVAL_CMD='claude -p --strict-mcp-config --permission-mode dontAsk'

  A nested `claude -p` needs its own login; it does not inherit the parent
  session's credentials. Run this from an authenticated terminal.
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

for scenario in "${scenarios[@]}"; do
  name="$(basename "${scenario}" .json)"
  workdir="$(mktemp -d "${TMPDIR:-/tmp}/update-doc-eval.XXXXXX")"
  repo="${workdir}/repo"
  mkdir -p "${repo}"

  # Materialize the fixture, committing only the tracked half so the untracked
  # files stay untracked — the whole point of several scenarios.
  python3 - "$scenario" "$repo" <<'PY'
import json, pathlib, sys
scenario = json.loads(pathlib.Path(sys.argv[1]).read_text())
root = pathlib.Path(sys.argv[2])
for group in ("repo",):
    for rel, content in scenario[group].items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
PY

  git -C "${repo}" init -q -b main
  git -C "${repo}" config user.email eval@example.com
  git -C "${repo}" config user.name eval
  # The skill is installed under .claude/ AFTER this commit, so without an
  # exclude its own files land in the untracked set and the language counts:
  # the scenario's scope, NEW_SOURCE, DOMINANT and POLYGLOT would all describe
  # the measuring instrument instead of the repository under test.
  echo '.claude/' >> "${repo}/.git/info/exclude"
  git -C "${repo}" add -A
  git -C "${repo}" commit -qm base

  python3 - "$scenario" "$repo" <<'PY'
import json, pathlib, sys
scenario = json.loads(pathlib.Path(sys.argv[1]).read_text())
root = pathlib.Path(sys.argv[2])
for rel, content in scenario.get("untracked", {}).items():
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
PY

  prompt="$(python3 -c "
import json,sys
s=json.load(open(sys.argv[1]))
print(s['prompt'])" "$scenario")"

  # Install the skill the way a user would, rather than pasting SKILL.md into
  # the prompt. Concatenation measures a different artifact: ${CLAUDE_SKILL_DIR}
  # never resolves, `allowed-tools` never applies, references are not loaded on
  # demand, and the mandatory discovery script cannot run — so the numbers would
  # not describe an installed skill.
  if [[ "${ARM}" == "with-skill" ]]; then
    mkdir -p "${repo}/.claude/skills"
    cp -R "${SKILL_DIR}" "${repo}/.claude/skills/update-doc"
    rm -rf "${repo}/.claude/skills/update-doc/scripts/tests"
    prompt="/update-doc ${prompt}"
  fi

  # Contamination probe: the scenario's own discovery must not see the harness.
  probe="$(bash "${SKILL_DIR}/scripts/discover_doc_scope.sh" --repo "${repo}" 2>/dev/null \
    | grep -c '\.claude/' || true)"
  if [ "${probe:-0}" -ne 0 ]; then
    echo "setup: installed skill is visible to the scenario's own discovery" >&2
    echo "       (${probe} references to .claude/); numbers would be polluted" >&2
    exit 2
  fi

  echo "=== ${name} (${ARM}) ==="
  response="${workdir}/response.md"
  if ! (cd "${repo}" && printf '%s' "${prompt}" | eval "${UPDATE_DOC_EVAL_CMD}") \
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
  python3 "${GRADER}" "${scenario}" "${repo}" "${response}" || failures=$((failures + 1))
  echo "  artifacts: ${workdir}"
  echo
done

echo "======================================"
echo "  scenarios measured: ${measured}"
echo "  scenarios failing:  ${failures}"
echo "  arm:                ${ARM}"
echo "======================================"
echo
echo "Compare arms by re-running with UPDATE_DOC_EVAL_ARM=without-skill. A skill"
echo "that helps should fail strictly fewer checks than the bare model; comparing"
echo "a single arm against zero tells you nothing about the skill's contribution."

[[ ${failures} -eq 0 ]] || exit 1
