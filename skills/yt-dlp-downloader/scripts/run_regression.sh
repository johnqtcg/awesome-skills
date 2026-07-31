#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TEST_DIR="$SCRIPT_DIR/tests"

echo "=== yt-dlp-downloader Skill Regression Suite ==="
echo ""

echo "--- Documented commands parsed by the real yt-dlp (offline) ---"
# Every command in the docs is run through yt-dlp's option parser with the URL
# removed. This validates flags, flag arguments, argument values and the -f
# expression — the layer a text search cannot reach.
# No `|| true`: swallowing this made a missing yt-dlp look like a pass — the
# pre-check error was discarded, the binary-dependent tests skipped, and the
# script still printed "All regression checks passed".
if command -v yt-dlp >/dev/null 2>&1; then
  python3 "$SCRIPT_DIR/extract_commands.py" check
  BINARY_VERIFIED=yes
else
  echo "  yt-dlp not installed: no command was parsed by the real binary."
  BINARY_VERIFIED=no
fi
echo ""

echo "--- All test files (contract + golden + flags-against-binary) ---"
# unittest discover picks up every test_*.py so newly added test files can
# never be silently skipped (an explicit per-file list once missed the
# binary-validation tests while 17 corrupted flags shipped green).
python3 -m unittest discover -s "$TEST_DIR" -p 'test_*.py' -v
echo ""

if [ "$BINARY_VERIFIED" = yes ]; then
  echo "=== All regression checks passed ==="
  echo ""
  echo "  Verified: every documented command parses cleanly through the installed"
  echo "  yt-dlp, each scenario template carries its required flags and none of its"
  echo "  forbidden ones, and the anti-example catalog is numbered 1..9 across both"
  echo "  files with the totals in SKILL.md agreeing."
  echo ""
  echo "  NOT verified: that any command succeeds against a live site, or that its"
  echo "  semantics match the CURRENT yt-dlp — the oracle is whichever build is"
  echo "  installed here. See test_flags_against_binary.py for the reported age."
else
  echo "=== Text-level checks passed; command verification did NOT run ==="
  echo ""
  echo "  yt-dlp is not installed, so no flag, flag argument, argument value or"
  echo "  -f expression was validated against the real parser, and the"
  echo "  binary-dependent tests were skipped rather than run."
  echo ""
  echo "  Do not read this as a full pass. Install yt-dlp and re-run."
  exit 3
fi
