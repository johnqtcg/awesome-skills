#!/usr/bin/env bash
# Run all regression tests for the load-test skill.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEST_DIR="${SCRIPT_DIR}/tests"

echo "All test files (contract + golden + k6-script validation)"
# pytest discovers every test_*.py, so newly added test files can never be
# silently skipped (an explicit per-file list once excluded the k6 script
# validation tests that caught 4 missing-import bugs in the references).
# Captured rather than written to a temp file: `mktemp` needs a writable
# system temp dir, which is not guaranteed (it is denied under Claude Code's
# default sandbox). The suite runs in seconds, so buffering costs nothing.
set +e
OUT="$(python3 -m pytest "${TEST_DIR}" -v -rs 2>&1)"
STATUS=$?
set -e
printf '%s\n' "${OUT}"
if [[ "${STATUS}" -ne 0 ]]; then
  echo "" >&2
  echo "load-test skill regression FAILED (pytest exit ${STATUS})." >&2
  exit "${STATUS}"
fi

# A skip is not a pass. The real-`k6 run` layer — the only layer that executes
# default() and handleSummary() — disappears entirely when k6 is missing or a
# sandbox refuses a loopback bind(), and the summary line still reads OK. Say
# so loudly, and qualify the success message, so nobody reads a green run as
# "the runtime layer verified this".
echo ""
DEGRADED=0
if grep -q "did NOT execute" <<< "${OUT}"; then
  echo "WARNING: the real k6-run layer did NOT execute (loopback bind denied)." >&2
  echo "         default()/handleSummary() were never called. Static checks and" >&2
  echo "         k6 inspect ran; runtime behaviour is UNVERIFIED this run." >&2
  echo "         Re-run outside the sandbox, or set LOADTEST_REQUIRE_RUNTIME=1" >&2
  echo "         to make this a hard failure in CI." >&2
  DEGRADED=1
fi
if grep -q "k6 not installed" <<< "${OUT}"; then
  echo "WARNING: k6 is not installed — k6 inspect AND the real-run layer were" >&2
  echo "         both skipped. Install k6 for meaningful validation." >&2
  DEGRADED=1
fi
if grep -q "not found beside this skill" <<< "${OUT}"; then
  echo "NOTE: outputexample/load-test/ is absent (skill installed standalone);" >&2
  echo "      its 14 cross-file checks were skipped, not run." >&2
  DEGRADED=1
fi

if [[ "${DEGRADED}" -eq 1 ]]; then
  echo "load-test skill regression checks passed EXCEPT the layers noted above."
else
  echo "load-test skill regression checks passed (including the real k6-run layer)."
fi
