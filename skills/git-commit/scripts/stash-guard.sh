#!/usr/bin/env bash
# stash-guard.sh — run a quality gate against the STAGED-ONLY working tree with
# the user's unstaged + untracked changes stashed and GUARANTEED restored
# exactly once on EVERY exit path (gate success, gate failure, timeout,
# SIGINT/SIGTERM).
#
#   Usage: bash stash-guard.sh <gate command...>
#          bash stash-guard.sh bash run-gate.sh make test
#
# Exit code = the gate command's exit code (restore happens first). An
# interrupt exits 130 (SIGINT) / 143 (SIGTERM) — never 0. A gate "pass" whose
# restore failed exits 1. Exit 2 = the gate NEVER RAN because the staged
# snapshot could not be fully isolated (e.g. dirty submodule content, which
# stash cannot carry) — fail-closed, never a gate against a mixed tree.
# On a restore conflict or a stash-OID mismatch it aborts loudly and PRESERVES
# the exact stash — the data is never lost, but `git stash pop` can leave a
# PARTIAL application in the worktree, so the printed recovery instructions
# must be followed rather than assuming a clean tree. If tracked files change
# while the gate runs, restore refuses the destructive reset and keeps the
# stash instead of silently discarding the concurrent edits.
#
# No `set -e`: it must not short-circuit the traps. `set -u` only.
set -u

CHANGED=0
if ! git diff --quiet || [ -n "$(git ls-files --others --exclude-standard)" ]; then
  CHANGED=1
fi
STASH=""
SNAPSHOT_TREE=""

restore() {
  [ "$CHANGED" = 1 ] && [ -n "$STASH" ] || return 0
  # Only ever touch OUR stash.
  if [ "$(git rev-parse -q --verify 'stash@{0}' 2>/dev/null)" != "$STASH" ]; then
    echo "stash-guard: our stash is no longer on top; your changes are safe in $STASH" >&2
    echo "stash-guard: restore manually: git stash apply --index $STASH" >&2
    return 1
  fi
  # Drift check BEFORE the reset: if tracked files or the index changed while
  # the gate ran (concurrent user/IDE edits, gate side-effects like formatters
  # or `go mod tidy`), those edits are NOT in the stash and a blind
  # `reset --hard` would destroy them silently. Submodule content dirt is
  # excluded: `reset --hard` cannot destroy it (pointer changes still count).
  if ! git diff --quiet --ignore-submodules=dirty \
     || [ "$(git write-tree 2>/dev/null)" != "$SNAPSHOT_TREE" ]; then
    echo "stash-guard: the tree changed while the gate ran (concurrent edits or gate side-effects)" >&2
    echo "stash-guard: refusing to reset; your pre-gate changes are safe in stash $STASH" >&2
    echo "stash-guard: inspect 'git status', then restore with: git stash apply --index $STASH" >&2
    return 1
  fi
  # Reset is safe: the entire change set lives in the stash. Applying onto a clean
  # HEAD (the stash's base) avoids the classic --keep-index + pop double-apply.
  git reset -q --hard
  if ! git stash pop --index -q 2>/dev/null; then
    echo "stash-guard: CONFLICT restoring your changes — they are safe in stash $STASH" >&2
    echo "stash-guard: the working tree may hold a PARTIAL restore; do not assume it is clean" >&2
    echo "stash-guard: resolve, then finish with: git stash apply --index $STASH" >&2
    return 1
  fi
  STASH=""   # restore is done — a second call (signal race) must be a no-op
}

# finish() is the ONLY exit path. All traps are cleared first so the `exit`
# below cannot re-enter restore via the EXIT trap: the old single-handler
# `trap ... EXIT INT TERM` ran restore twice on Ctrl-C and, because $? is
# unreliable inside a signal handler, could report an interrupt as exit 0.
finish() {
  trap - EXIT INT TERM
  rc=$1
  if ! restore && [ "$rc" -eq 0 ]; then
    rc=1   # a gate "pass" with a failed restore is NOT a pass
  fi
  exit "$rc"
}
trap 'finish $?' EXIT
trap 'finish 130' INT
trap 'finish 143' TERM

if [ "$CHANGED" = 1 ]; then
  # Record the pre-push top: `git stash push` can exit 0 WITHOUT creating an
  # entry (e.g. the only dirt is inside a submodule, which stash cannot carry).
  # Blindly claiming stash@{0} would then pop a PRE-EXISTING user stash.
  BEFORE=$(git rev-parse -q --verify 'stash@{0}' 2>/dev/null)
  if ! git stash push --keep-index --include-untracked -q -m "pre-commit gate $$"; then
    echo "stash-guard: git stash failed; aborting before running the gate" >&2
    CHANGED=0   # nothing was stashed → restore() is a no-op
    exit 1
  fi
  STASH=$(git rev-parse -q --verify 'stash@{0}' 2>/dev/null)
  if [ -z "$STASH" ] || [ "$STASH" = "$BEFORE" ]; then
    STASH=""   # push created no entry — NEVER adopt a pre-existing stash
  fi
  SNAPSHOT_TREE=$(git write-tree 2>/dev/null)
  # Isolation must be COMPLETE. `git stash` cannot carry submodule content
  # changes, so dirt can survive a successful push — running the gate then
  # would break the staged-snapshot promise (fail-open). Fail closed instead;
  # the EXIT trap restores whatever WAS stashed.
  if ! git diff --quiet || [ -n "$(git ls-files --others --exclude-standard)" ]; then
    echo "stash-guard: cannot isolate the staged snapshot — unstashable changes remain (dirty submodule content?)" >&2
    echo "stash-guard: refusing to run the gate against a mixed tree; commit or clean that state first" >&2
    exit 2
  fi
fi

"$@"