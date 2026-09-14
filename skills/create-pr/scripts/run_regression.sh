#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Frontmatter validation lives in the suite below
# (`CreatePRSkillContractTests.test_frontmatter_*`), not in an external tool.
#
# This step used to hard-fail on a validator at
# `$HOME/.codex/skills/.system/skill-creator/scripts/quick_validate.py` — a path
# outside this repository and untracked by it, so `bash scripts/run_regression.sh`
# exited 1 on any other machine before a single test ran. Its allowlist is also
# five fields against the seventeen Claude Code documents, and it rejects
# `disable-model-invocation`, which this skill must set. `skills/update-doc`
# reached the same conclusion and ships its own validator rather than stripping
# the field to satisfy the tool — validating a file nobody ships proves nothing.
#
# Set SKILL_CREATOR_VALIDATOR to run one anyway; it is opt-in and advisory.
if [[ -n "${SKILL_CREATOR_VALIDATOR:-}" ]]; then
  echo "[opt-in] External validator: ${SKILL_CREATOR_VALIDATOR}"
  if [[ ! -f "${SKILL_CREATOR_VALIDATOR}" ]]; then
    echo "  requested validator not found — set the path or unset the variable" >&2
    exit 1
  fi
  # `|| rc=$?` keeps the validator's own exit code: `if ! cmd; then rc=$?` would
  # capture the negation's status (0) instead, and `set -e` would abort first.
  rc=0
  python3 "${SKILL_CREATOR_VALIDATOR}" "${SKILL_DIR}" || rc=$?
  if [[ "${rc}" -ne 0 ]]; then
    echo "  NOTE: a stale allowlist rejects documented fields; the suite's own" >&2
    echo "        frontmatter tests are authoritative." >&2
    exit "${rc}"
  fi
fi

echo "[1/2] Smoke-test bundled script help"
python3 "${SKILL_DIR}/scripts/create_pr.py" --help >/dev/null

echo "[2/2] Run regression tests"
python3 -m unittest discover -s "${SKILL_DIR}/scripts/tests" -p "test_*.py" -v

echo "create-pr skill regression checks passed"
