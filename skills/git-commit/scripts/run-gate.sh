#!/usr/bin/env bash
# run-gate.sh — run one quality-gate command with the skill's timeout ENFORCED,
# not just documented.
#
#   Usage: bash run-gate.sh [-t <seconds>] <gate command...>
#
# Timeout resolution (first match wins):
#   1. -t <seconds> — a timeout the repo wrapper itself declares
#      (§4 "Makefile wrappers take precedence")
#   2. $QUALITY_GATE_TIMEOUT_SECONDS
#   3. $SKILL_QUALITY_GATE_TIMEOUT_SECONDS
#   4. $COMMIT_TEST_TIMEOUT
#   5. default 120 seconds
#
# Prints `GATE_TIMEOUT: <n>s` on stderr before running (§4 "report the chosen
# timeout"). The timeout bounds ONE gate command (this invocation). Exit code
# is the gate's own; 124 means it ran out of time — the gate's whole process
# group is killed, in every branch (GNU timeout signals the group by default;
# the perl watcher does the same explicitly). With no timeout tool at all this
# exits 2 instead of running unbounded — the timeout is enforced, not advisory.
set -u

SECS=""
if [ "${1:-}" = "-t" ]; then
  SECS=${2:?run-gate: -t needs a seconds value}
  shift 2
fi
[ -n "$SECS" ] || SECS=${QUALITY_GATE_TIMEOUT_SECONDS:-${SKILL_QUALITY_GATE_TIMEOUT_SECONDS:-${COMMIT_TEST_TIMEOUT:-120}}}
case $SECS in
  ''|*[!0-9]*) echo "run-gate: invalid timeout '$SECS' (must be a positive integer)" >&2; exit 2 ;;
esac
if [ "$SECS" -eq 0 ]; then
  # timeout(1) and alarm() both treat 0 as "no timeout" — that silently
  # disables enforcement, so reject it.
  echo "run-gate: invalid timeout '0' (0 would disable the timeout)" >&2
  exit 2
fi
[ $# -gt 0 ] || { echo "run-gate: no gate command given" >&2; exit 2; }

echo "GATE_TIMEOUT: ${SECS}s" >&2

if command -v timeout >/dev/null 2>&1; then
  exec timeout "$SECS" "$@"
fi
if command -v gtimeout >/dev/null 2>&1; then
  exec gtimeout "$SECS" "$@"
fi
if command -v perl >/dev/null 2>&1; then
  # Watcher: the gate runs in its OWN process group so expiry kills the whole
  # tree (a bare `alarm; exec` would kill only the direct child and leak
  # grandchildren). INT/TERM are forwarded; timeout exits 124 like timeout(1).
  exec perl -e '
    my $secs = shift @ARGV;
    defined(my $pid = fork) or die "run-gate: fork: $!\n";
    if ($pid == 0) { setpgrp(0, 0); exec @ARGV or die "run-gate: exec failed: $!\n" }
    $SIG{INT}  = sub { kill "INT",  -$pid };
    $SIG{TERM} = sub { kill "TERM", -$pid };
    $SIG{ALRM} = sub { kill "TERM", -$pid; sleep 2; kill "KILL", -$pid; exit 124 };
    alarm $secs;
    my $r;
    do { $r = waitpid($pid, 0) } while ($r == -1 && $!{EINTR});
    exit(($? & 127) ? 128 + ($? & 127) : $? >> 8);
  ' "$SECS" "$@"
fi
echo "run-gate: no timeout tool (timeout/gtimeout/perl) — refusing to run unbounded" >&2
exit 2