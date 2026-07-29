#!/usr/bin/env bash
# Run two prebuilt benchmark binaries alternately and emit two files for benchstat.
#
#   scripts/run_interleaved_bench.sh <old.bench> <new.bench> <out-dir> [count] [bench-regex]
#
# Why a script rather than a loop pasted into a README: the pasted loop kept getting the
# operational details wrong. It clobbered existing result files, hardcoded branch names,
# switched the worktree 20 times mid-measurement (failing outright on a dirty tree and
# stranding the caller on the wrong branch if interrupted), and folded compilation into the
# timing window. Everything here is fixed and testable, and the skill's allowed-tools needs
# to approve exactly one command instead of a shell loop.
#
# Build the two binaries yourself first — that step is yours because only you know which
# commits you are comparing. Use worktrees, not branch switching: they never touch your
# checkout, so a dirty tree is irrelevant and there is nothing to restore afterwards.
#
#   git worktree add /tmp/wt-old <base-ref>
#   git worktree add /tmp/wt-new <changed-ref>
#   (cd /tmp/wt-old && go test -c -o /tmp/old.bench ./pkg/mypkg)
#   (cd /tmp/wt-new && go test -c -o /tmp/new.bench ./pkg/mypkg)
#   git worktree remove /tmp/wt-old && git worktree remove /tmp/wt-new
#
# `git switch -` is NOT a way back: it means @{-1}, the PREVIOUS branch, not the one you
# started on. From `topic`, doing main -> feature -> `-` leaves you on main. If you must
# switch branches, capture the start point and restore it with a trap:
#
#   START=$(git symbolic-ref --quiet --short HEAD || git rev-parse HEAD)
#   trap 'git switch --quiet "$START"' EXIT
#
# `go test -c` compiles ONE package. `-o file` with a multi-package pattern such as
# `./pkg/...` fails with "with multiple packages, -o must refer to a directory or
# /dev/null" — name the single package you are benchmarking.
set -euo pipefail

die() { echo "error: $*" >&2; exit 2; }

[[ $# -ge 3 ]] || die "usage: $0 <old.bench> <new.bench> <out-dir> [count] [bench-regex]"

OLD_BIN=$1
NEW_BIN=$2
OUT_DIR=$3
COUNT=${4:-10}
BENCH=${5:-.}

[[ -x "$OLD_BIN" ]] || die "not an executable benchmark binary: $OLD_BIN"
[[ -x "$NEW_BIN" ]] || die "not an executable benchmark binary: $NEW_BIN"
[[ "$COUNT" =~ ^[1-9][0-9]*$ ]] || die "count must be a positive integer, got: $COUNT"

mkdir -p "$OUT_DIR"
OLD_TXT="$OUT_DIR/old.txt"
NEW_TXT="$OUT_DIR/new.txt"

# Refuse rather than append. Appending new samples onto a previous run's file is the
# quiet failure here: benchstat groups by benchmark name, so it will happily average
# yesterday's machine state into today's comparison and report a confident number.
for f in "$OLD_TXT" "$NEW_TXT"; do
  [[ -e "$f" ]] && die "$f already exists — move it aside or pick another out-dir"
done
: > "$OLD_TXT"
: > "$NEW_TXT"

echo "interleaving $COUNT samples per side (ABBA order — lead side alternates)"
echo "  old: $OLD_BIN"
echo "  new: $NEW_BIN"
echo "  out: $OUT_DIR"

# ABBA, not AB-AB. Alternating old->new every round still runs `old` first every time, so
# anything with a short period — a turbo-boost window that decays within a round, a cache
# left warm by the previous binary — lands on the same side each round and survives
# averaging as a systematic offset. Swapping which side leads on alternate rounds cancels
# the first-position advantage instead of merely spreading long-term drift.
run_one() {
  # A compiled test binary takes -test.-prefixed flags; the bare forms only work
  # through `go test`.
  "$1" -test.bench="$BENCH" -test.benchmem -test.count=1 -test.run='^$' >> "$2"
}

for ((i = 1; i <= COUNT; i++)); do
  printf '\r  sample %d/%d' "$i" "$COUNT"
  if (( i % 2 == 1 )); then
    run_one "$OLD_BIN" "$OLD_TXT"   # odd rounds: old leads
    run_one "$NEW_BIN" "$NEW_TXT"
  else
    run_one "$NEW_BIN" "$NEW_TXT"   # even rounds: new leads
    run_one "$OLD_BIN" "$OLD_TXT"
  fi
done
printf '\n'
if (( COUNT % 2 == 1 )); then
  echo "note: an odd count leaves one extra old-first round; use an even count for a" \
       "fully balanced ABBA order"
fi

if command -v benchstat >/dev/null; then
  benchstat "$OLD_TXT" "$NEW_TXT"
else
  echo "benchstat not installed; compare with:"
  echo "  go install golang.org/x/perf/cmd/benchstat@latest"
  echo "  benchstat $OLD_TXT $NEW_TXT"
fi
