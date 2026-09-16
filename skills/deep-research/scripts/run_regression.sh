#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
TEST_DIR="$SCRIPT_DIR/tests"

echo "=== Deep Research Skill Regression Suite ==="
echo "Skill root: $SKILL_DIR"
echo ""

echo "--- 1/3: Declared test dependencies ---"
# ripgrep is a hard dependency of `search-codebase`, so its absence is not a
# reason to skip: without it the suite reported `OK (skipped=7)` and this
# script still exited 0, while three of COVERAGE.md's headline repository
# guarantees had not run. A missing dependency is a failed gate, not a pass.
missing=0
for tool in git rg; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "MISSING REQUIRED TOOL: $tool" >&2
    missing=1
  fi
done
if [ "$missing" -ne 0 ]; then
  echo "Install the tools above before running the regression suite." >&2
  exit 1
fi
echo "git, rg: OK"
echo ""

echo "--- 2/3: All test files (unit + smoke + contract + golden) ---"
# unittest discover picks up every test_*.py, so newly added test files can
# never be silently skipped (the smoke tests were once missing from an
# explicit per-file list while the script shipped broken).
#
# Discovery is driven from Python rather than `python3 -m unittest` so the
# skipped count can fail the run. `countTestCases()` counts *collected* tests,
# so the COVERAGE.md staleness guard cannot see a skip — only this can.
python3 - "$TEST_DIR" <<'PY'
import sys
import unittest

test_dir = sys.argv[1]
suite = unittest.defaultTestLoader.discover(test_dir, pattern="test_*.py")
result = unittest.TextTestRunner(verbosity=2).run(suite)

if result.skipped:
    print("")
    print(f"FAILED: {len(result.skipped)} test(s) were skipped; a skip is not a pass.")
    for case, reason in result.skipped:
        print(f"  - {case}: {reason}")
    sys.exit(1)

if not result.wasSuccessful():
    sys.exit(1)
PY
echo ""

echo "--- 3/3: Script help check ---"
python3 "$SCRIPT_DIR/deep_research.py" --help >/dev/null
echo "deep_research.py --help: OK"
echo ""

echo "=== All regression checks passed ==="
