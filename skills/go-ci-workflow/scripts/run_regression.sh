#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
VALIDATOR="${SKILL_CREATOR_VALIDATOR:-$HOME/.codex/skills/.system/skill-creator/scripts/quick_validate.py}"

# A COLLAPSE DETECTOR, not the true test count. `unittest discover` exits 0
# after "Ran 0 tests" when the discovery pattern or path matches nothing, so a
# green run can mean no run at all. Deliberate slack: this number must never be
# hand-maintained as the exact total — that rots within two commits. Its only
# job is to catch discovery collapsing to a fraction of the suite.
MIN_TESTS=100

echo "[1/4] Check validation layers"
# Prerequisites are checked BEFORE the validator: quick_validate.py itself
# imports yaml, so a missing PyYAML otherwise surfaces as that script's
# traceback instead of the actionable message below.
#
# PyYAML is declared in requirements.txt and gates every structural YAML test —
# the layer that validates the copyable workflow blocks. The tests skip rather
# than crash collection (deliberate: a hard import kills the whole repo suite),
# but THIS script is a publish gate. A skipped YAML layer must fail it, not
# merely qualify the banner: without this check the suite reported
# "Ran 116 tests ... OK (skipped=18)" with rc=0 and every YAML block unchecked.
if ! python3 -c 'import yaml' >/dev/null 2>&1; then
  echo "ERROR: PyYAML is not importable — all structural YAML validation would" >&2
  echo "       be SKIPPED, leaving the reference workflow blocks unchecked." >&2
  echo "       Install: python3 -m pip install -r requirements.txt (repository root)" >&2
  exit 1
fi
echo "PyYAML present; structural YAML validation enabled"

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
  echo "         Install (release binary — works behind a proxy that breaks" >&2
  echo "         the Go module fetch): download actionlint_<ver>_<os>_<arch>.tar.gz" >&2
  echo "         from https://github.com/rhysd/actionlint/releases/latest" >&2
  echo "         or: go install github.com/rhysd/actionlint/cmd/actionlint@latest" >&2
fi

echo "[2/4] Validate skill frontmatter"
# Fail closed: a missing or failing validator is a regression failure, not a
# skip. (The previous version swallowed the validator's error and still
# reported success, which hid a real frontmatter defect.)
if [[ ! -f "${VALIDATOR}" ]]; then
  echo "validator not found at ${VALIDATOR}" >&2
  exit 1
fi
python3 "${VALIDATOR}" "${SKILL_DIR}"

echo "[3/4] Run regression tests"
test_log="$(mktemp 2>/dev/null || echo "${TMPDIR:-/tmp}/gociw_regression.$$.log")"
trap 'rm -f "${test_log}"' EXIT
python3 -m unittest discover -s "${SKILL_DIR}/scripts/tests" -p "test_*.py" -v 2>&1 | tee "${test_log}"

echo "[4/4] Verify the run was not silently degraded"
# Every permitted skip must be accounted for by a layer this script has already
# reported as absent. Any other skip means a test opted itself out without the
# runner knowing — the failure mode that let 18 silently-skipped YAML tests
# read as a pass. This ceiling is derived from the environment, never
# hand-maintained.
expected_skips=0
skip_reason="none"
if [[ "${actionlint_ran}" -eq 0 ]]; then
  expected_skips=1
  skip_reason="actionlint absent (1 test)"
fi

ran="$(grep -oE '^Ran [0-9]+ test' "${test_log}" | tail -1 | grep -oE '[0-9]+' || true)"
skipped="$(grep -oE 'skipped=[0-9]+' "${test_log}" | tail -1 | grep -oE '[0-9]+' || true)"
skipped="${skipped:-0}"

if [[ -z "${ran}" ]]; then
  echo "ERROR: could not parse a test count from the run — treating as a failure." >&2
  exit 1
fi
if (( ran < MIN_TESTS )); then
  echo "ERROR: only ${ran} tests ran (floor ${MIN_TESTS}). Test discovery collapsed;" >&2
  echo "       a partial run must never report success." >&2
  exit 1
fi
if (( skipped > expected_skips )); then
  echo "ERROR: ${skipped} tests skipped but only ${expected_skips} are accounted for" >&2
  echo "       (${skip_reason}). An unexplained skip is an unverified layer." >&2
  echo "       Re-run with -v and inspect the 'skipped' lines above." >&2
  exit 1
fi

echo "ran=${ran} skipped=${skipped} (accounted for: ${skip_reason})"
if [[ "${actionlint_ran}" -eq 1 ]]; then
  echo "go-ci-workflow skill regression checks passed (including actionlint)"
else
  echo "go-ci-workflow skill regression checks passed EXCEPT actionlint (see WARNING above)"
fi
