#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== E2E Test Skill — Regression Suite ==="
echo ""

# Test files are discovered, not listed. A hardcoded list silently skips any new
# file, which is how golden fixtures 011-014 stayed untested while COVERAGE.md
# claimed full coverage.
TEST_FILES=()
while IFS= read -r f; do
  TEST_FILES+=("${f}")
done < <(find "${SCRIPT_DIR}/tests" -maxdepth 1 -name 'test_*.py' | sort)

if [ "${#TEST_FILES[@]}" -eq 0 ]; then
  echo "FAIL: no test files discovered under ${SCRIPT_DIR}/tests" >&2
  exit 1
fi

for f in "${TEST_FILES[@]}"; do
  echo "--- $(basename "${f}") ---"
  python3 "${f}" 2>&1 | tail -3
  echo ""
done

# Run the pytest form too. This repo's pytest.ini sets --import-mode=importlib,
# which does not add the test directory to sys.path — a suite can pass standalone
# and still fail under `pytest skills/`. Both forms must be green.
echo "--- pytest form ---"
python3 -m pytest "${SCRIPT_DIR}/tests" -q
echo ""

CLEANUP_PATHS=()
cleanup() { [ "${#CLEANUP_PATHS[@]}" -gt 0 ] && rm -rf "${CLEANUP_PATHS[@]}"; }
trap cleanup EXIT

# Forward-eval self-check: the grader must fire on a known-bad spec. A linter
# nobody validates is a linter nobody should trust. (The complementary direction
# — the skill's own GOOD examples must stay clean — is asserted by
# TestSkillOwnExamplesPassTheGrader in the contract suite.)
echo "--- grader smoke test ---"
# Explicit template: macOS `mktemp -t <prefix>` ignores $TMPDIR and writes under
# /var/folders/..., which a sandboxed runner may not be permitted to touch.
BAD_SPEC="$(mktemp "${TMPDIR:-/tmp}/e2e_bad_spec.XXXXXX")"
CLEANUP_PATHS+=("${BAD_SPEC}")
cat > "${BAD_SPEC}" <<'SPEC'
test('t', async ({ page }) => {
  await page.goto('https://staging.example.com');
  await page.waitForTimeout(3000);
});
SPEC
if python3 "${SCRIPT_DIR}/lint_e2e_spec.py" "${BAD_SPEC}" >/dev/null 2>&1; then
  echo "FAIL: grader reported no CRITICAL findings on a known-bad spec" >&2
  exit 1
fi
echo "grader correctly rejects a known-bad spec"
echo ""

echo "--- discovery script smoke test ---"
PROBE="$(mktemp -d "${TMPDIR:-/tmp}/e2e_probe.XXXXXX")"
CLEANUP_PATHS+=("${PROBE}")
# An empty directory is the case most likely to abort a probe script.
if ! out=$(bash "${SCRIPT_DIR}/discover_e2e_needs.sh" "${PROBE}" 2>&1); then
  echo "FAIL: discovery script aborted on an empty directory" >&2
  echo "${out}" >&2
  exit 1
fi
if ! printf '%s' "${out}" | grep -q '=== End Report ==='; then
  echo "FAIL: discovery report truncated on an empty directory" >&2
  exit 1
fi
echo "discovery script completes on an empty directory"
echo ""

echo "=== All tests passed ==="
