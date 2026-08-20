#!/usr/bin/env bash
# Capture a run bundle as a committable golden run.
#
# A golden run is the one piece of evidence this framework still lacks: proof that
# six real agents completed against real SEC data, including the timeout, bad-output
# and second-wave paths. The synthetic end-to-end test proves the *tools* compose;
# it cannot prove the *agents* do.
#
# This script does not create that evidence — only a real analysis can. What it does
# is make capturing one a single command that refuses to capture a bundle which is
# not actually publishable, and that strips the parts which should not be committed.
#
# Usage:
#   scripts/goldenrun.sh capture <run-dir> <ticker> [dest-root]
#   scripts/goldenrun.sh verify  <golden-dir>
#
# `capture` runs the publication gate first and aborts on FAIL, so a bundle that
# cannot be published can never become a baseline.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FINLIB="$HERE/finlib"
DEFAULT_DEST="$(cd "$HERE/../../.." && pwd)/outputexample/stock-analysis-lead/runs"

die() { printf 'goldenrun: %s\n' "$1" >&2; exit 1; }

cmd_capture() {
  local run="${1:-}" ticker="${2:-}" dest_root="${3:-$DEFAULT_DEST}"
  [ -n "$run" ] && [ -n "$ticker" ] || die "usage: goldenrun.sh capture <run-dir> <ticker> [dest-root]"
  [ -d "$run" ] || die "run dir not found: $run"

  echo "==> publication gate (a FAIL here means this bundle is not a baseline)"
  python3 "$FINLIB/runbundle.py" check --run "$run" --stage publication \
    || die "bundle failed the publication gate; fix the run, do not capture it"

  # Date comes from the verdict, not from `date`, so re-capturing the same run is
  # idempotent and the directory name states when the analysis was made.
  local vdate
  vdate="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["verdict_date"])' \
    "$run/verdict.json")" || die "cannot read verdict_date from verdict.json"

  local dest="$dest_root/${ticker}-${vdate}"
  [ -e "$dest" ] && die "destination already exists: $dest"
  mkdir -p "$dest"
  # -a would carry macOS extended attributes into the repo; -R is enough.
  cp -R "$run/." "$dest/"

  # Scratch artifacts that are large, machine-specific, or not evidence.
  find "$dest" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
  find "$dest" -name '*.pyc' -delete 2>/dev/null || true
  rm -f "$dest"/*.lock

  cat > "$dest/CAPTURE.md" <<EOF
# Golden run — ${ticker}, ${vdate}

Captured with \`scripts/goldenrun.sh capture\`, which ran
\`runbundle.py check --stage publication\` and refused to capture on FAIL.

Verify at any time:

\`\`\`bash
python3 skills/stock-analysis-lead/scripts/finlib/runbundle.py check \\
  --run outputexample/stock-analysis-lead/runs/${ticker}-${vdate} --stage publication
\`\`\`

## Review before committing

This bundle contains raw agent output and an investment view. Check each item:

- [ ] \`workers/*.md\` — raw replies may quote scraped third-party content. Confirm
      quotation is within fair use, or trim the quotes.
- [ ] \`verdict.json\` — records the author's investment view. Committing it makes
      that view public and permanent.
- [ ] \`data-manifest.json\` — paths may leak local usernames or directory layout.
- [ ] No API keys, cookies, or session tokens anywhere in the bundle.
- [ ] Prices and filings are as-of ${vdate}; the bundle is a snapshot, not current
      advice.

## What this bundle proves, and what it does not

Proves: the tool chain ran end to end and the artifacts agree with each other.

Does **not** prove correctness of the analysis. A golden run is a *regression*
baseline: a later code change that alters these artifacts should be explained. It
is not evidence that the verdict was right.
EOF

  echo "==> captured to $dest"
  echo "==> re-verifying the captured copy"
  python3 "$FINLIB/runbundle.py" check --run "$dest" --stage publication \
    || die "the captured copy does not verify — capture is unusable"
  echo "==> read $dest/CAPTURE.md and complete the review checklist before committing"
}

cmd_verify() {
  local golden="${1:-}"
  [ -n "$golden" ] || die "usage: goldenrun.sh verify <golden-dir>"
  [ -d "$golden" ] || die "not found: $golden"
  python3 "$FINLIB/runbundle.py" check --run "$golden" --stage publication
}

case "${1:-}" in
  capture) shift; cmd_capture "$@" ;;
  verify)  shift; cmd_verify  "$@" ;;
  *) die "usage: goldenrun.sh {capture|verify} ..." ;;
esac
