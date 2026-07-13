#!/usr/bin/env bash
# stash-guard.sh — run a quality gate against the STAGED-ONLY working tree with
# the user's unstaged + untracked changes stashed and GUARANTEED restored on
# EVERY exit path (gate success, gate failure, or interrupt) via a trap.
#
#   Usage: bash scripts/stash-guard.sh <gate command...>
#          bash scripts/stash-guard.sh make ci
#
# Exit code = the gate command's exit code (restore happens first, in the trap).
# On a restore conflict or a stash-OID mismatch it exits non-zero and PRESERVES
# the exact stash so nothing is ever lost — never a half-restored tree.
#
# No `set -e`: it must not short-circuit the trap. `set -u` only.
set -u

CHANGED=0
if ! git diff --quiet || [ -n "$(git ls-files --others --exclude-standard)" ]; then
  CHANGED=1
fi
STASH=""

restore() {
  [ "$CHANGED" = 1 ] && [ -n "$STASH" ] || return 0
  # Only ever touch OUR stash.
  if [ "$(git rev-parse -q --verify 'stash@{0}' 2>/dev/null)" != "$STASH" ]; then
    echo "stash-guard: our stash is no longer on top; your changes are safe in $STASH" >&2
    echo "stash-guard: restore manually: git stash apply --index $STASH" >&2
    return 1
  fi
  # Reset is safe: the entire change set lives in the stash. Applying onto a clean
  # HEAD (the stash's base) avoids the classic --keep-index + pop double-apply.
  git reset -q --hard
  if ! git stash pop --index -q 2>/dev/null; then
    echo "stash-guard: CONFLICT restoring your changes — they are safe in stash $STASH" >&2
    echo "stash-guard: resolve, then finish with: git stash apply --index $STASH" >&2
    return 1
  fi
}
trap 'rc=$?; restore || rc=1; exit $rc' EXIT INT TERM

if [ "$CHANGED" = 1 ]; then
  if ! git stash push --keep-index --include-untracked -q -m "pre-commit gate $$"; then
    echo "stash-guard: git stash failed; aborting before running the gate" >&2
    CHANGED=0   # nothing was stashed → restore() is a no-op
    exit 1
  fi
  STASH=$(git rev-parse -q --verify 'stash@{0}')
fi

"$@"