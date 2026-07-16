#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
VALIDATOR="${SKILL_CREATOR_VALIDATOR:-$HOME/.codex/skills/.system/skill-creator/scripts/quick_validate.py}"

echo "[1/3] Validate skill frontmatter"
# Fail closed: a missing or failing validator is a regression failure, not a
# skip. (The previous version swallowed the validator's error and still
# reported success, which hid a real frontmatter defect.)
if [[ ! -f "${VALIDATOR}" ]]; then
  echo "validator not found at ${VALIDATOR}" >&2
  exit 1
fi
python3 "${VALIDATOR}" "${SKILL_DIR}"

echo "[2/3] GitHub Actions semantic lint (actionlint)"
# actionlint is the only layer that checks Actions expressions/contexts/shell.
# PyYAML proves the YAML parses; it does NOT prove GitHub will accept the
# workflow. Say so loudly when actionlint is absent so a green run is not
# mistaken for full validation.
actionlint_ran=0
if command -v actionlint >/dev/null 2>&1; then
  echo "actionlint found ($(actionlint --version 2>/dev/null | head -1)); golden workflows are linted by test_golden_yaml.py"
  actionlint_ran=1
else
  echo "WARNING: actionlint is NOT installed — GitHub Actions expression/semantic" >&2
  echo "         validation is SKIPPED. YAML parses, but trigger and \${{ }}" >&2
  echo "         expression correctness are NOT verified this run." >&2
  echo "         Install: go install github.com/rhysd/actionlint/cmd/actionlint@latest" >&2
fi

echo "[3/3] Run regression tests"
python3 -m unittest discover -s "${SKILL_DIR}/scripts/tests" -p "test_*.py" -v

if [[ "${actionlint_ran}" -eq 1 ]]; then
  echo "go-ci-workflow skill regression checks passed (including actionlint)"
else
  echo "go-ci-workflow skill regression checks passed EXCEPT actionlint (see WARNING above)"
fi