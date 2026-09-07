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
# timeout"). The timeout bounds ONE gate command (this invocation).
#
# EXIT CODE: the gate's own, except that **a timeout is always 124** — on every
# host, whichever tool is used. With no tool that can force-kill, this exits 2
# rather than run unbounded: the timeout is enforced, not advisory. An interrupt
# is forwarded to the gate and reported as 130 (INT) / 143 (TERM) / 129 (HUP)
# only after the gate has actually stopped.
#
# Getting to one code took three facts, each measured rather than assumed:
#  1. Expiry sends TERM, and a gate that ignores it survives. GNU timeout then
#     still returns 124 while the command KEEPS RUNNING — the coreutils manual
#     shows exactly this: `timeout -s INT 5s env --ignore-signal=INT sleep 20`
#     -> "'sleep' terminates regularly after the full 20 seconds, still
#     'timeout' returns with exit status 124". So TERM alone cannot back the
#     "process tree is dead" promise; `--kill-after` is required, and a tool
#     that lacks it is SKIPPED rather than used behind a warning.
#  2. GNU reports 137 (128+9) when the KILL was needed, not 124.
#  3. BusyBox timeout (Alpine) does not implement the 124 convention AT ALL: it
#     reports the child's signal death, so a plain expiry is 143 and a
#     TERM-ignoring one is 137. Verified on BusyBox v1.37.0.
# Three implementations, four possible codes, and 137/143 also occur when
# something else kills the gate. So the tool is run as a CHILD (not exec'd) and
# a signal death at or past the deadline is normalised to 124. Elapsed time is
# the implementation-independent evidence that the deadline is what fired.
# Every branch signals the whole process GROUP: GNU uses its own program group
# unless `--foreground`, BusyBox kills the child tree, the watcher calls setpgrp.
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

# Run the timeout tool as a child and normalise its verdict to a single code.
# `exec` cannot do this: the tool's own status becomes ours unfiltered, which is
# how BusyBox's 143 reached callers that were told to expect 124 or 137.
# Cancellation must reach the gate. While this was `exec`, a signal to the
# executor hit the timeout tool directly; introducing a supervisor that only
# `wait`ed broke that — SIGTERM to the executor returned 143 immediately while
# the gate ran on and wrote its side effect two seconds later. So the supervisor
# forwards the signal, then WAITS for the gate to actually die before exiting:
# leaving first is precisely what let the gate outlive its own cancellation.
# Signalling the TOOL's pid is not enough. Measured: a forwarded INT killed the
# gate's `sleep`, after which the gate's shell carried on to its next line and
# produced its side effect anyway, while the tool stayed alive — so the
# supervisor saw "tool still running", then "tool gone", and never noticed the
# gate had done work after cancellation. Cancellation therefore goes to the
# whole PROCESS GROUP, and liveness is checked on the group too.
forward_and_exit() {   # forward_and_exit <signal-name> <exit-code>
  trap - INT TERM HUP                      # no re-entry from a second signal
  kill -"$1" -"$gate_pid" 2>/dev/null || kill -"$1" "$gate_pid" 2>/dev/null
  # Give the tool room to tear its own tree down (GNU/BusyBox -k is 10s; the
  # perl watcher uses TERM+2s+KILL) before escalating. `kill -0` on the negative
  # pid asks "is ANY process left in that group?". Integer sleep only: POSIX
  # sleep takes whole seconds.
  i=0
  while kill -0 -"$gate_pid" 2>/dev/null && [ "$i" -lt 12 ]; do
    sleep 1; i=$((i + 1))
  done
  if kill -0 -"$gate_pid" 2>/dev/null; then
    kill -KILL -"$gate_pid" 2>/dev/null
    wait "$gate_pid" 2>/dev/null
    # Verify, then report what is true. The old message asserted cleanup
    # unconditionally, so a run that left the gate alive still read as clean.
    sleep 1
    if kill -0 -"$gate_pid" 2>/dev/null; then
      echo "GATE_CANCELLED: SIG$1 and KILL sent, but processes REMAIN in the gate's group — clean up manually" >&2
    else
      echo "GATE_CANCELLED: SIG$1 forwarded to the gate's group, then KILLed after ${i}s" >&2
    fi
  else
    wait "$gate_pid" 2>/dev/null
    echo "GATE_CANCELLED: SIG$1 forwarded to the gate's group; it exited" >&2
  fi
  exit "$2"
}

run_normalised() {
  start=$(date +%s)
  # Job control gives the background job its OWN process group, which is what
  # makes the group-wide cancellation above addressable. Turned straight back
  # off so bash does not print job notifications into the gate's output.
  set -m
  "$@" &
  gate_pid=$!
  set +m
  trap 'forward_and_exit TERM 143' TERM
  trap 'forward_and_exit INT  130' INT
  trap 'forward_and_exit HUP  129' HUP
  wait "$gate_pid"
  rc=$?
  trap - INT TERM HUP
  elapsed=$(( $(date +%s) - start ))
  # 128+15 TERM / 128+9 KILL at or past the deadline: the expiry did this.
  # Before the deadline they are the gate's own death and must pass through.
  case $rc in
    137|143) [ "$elapsed" -ge "$SECS" ] && rc=124 ;;
  esac
  [ "$rc" -eq 124 ] && echo "GATE_TIMED_OUT: after ${SECS}s (process group killed)" >&2
  exit "$rc"
}

# KILL_AFTER must be non-zero: the manual notes -k "has no effect if either the
# main duration ... or the duration specified to this option, is 0".
KILL_AFTER=10
# A tool is ELIGIBLE only if it can force-kill. Escalation is the guarantee this
# script exists to provide, so a `timeout` that cannot do it is skipped, not used
# with a warning: degrading to TERM-only while still reporting a timeout would
# tell the caller the gate is dead when it may still be running and holding
# locks, ports, or a database. Keep looking for a tool that qualifies.
for tool in timeout gtimeout; do
  command -v "$tool" >/dev/null 2>&1 || continue
  # Feature-probe rather than assume GNU: busybox/toybox `timeout` may reject -k.
  if "$tool" -k "$KILL_AFTER" 5 true >/dev/null 2>&1; then
    run_normalised "$tool" -k "$KILL_AFTER" "$SECS" "$@"
  fi
  echo "run-gate: $tool does not accept --kill-after and cannot force-kill; trying the next tool" >&2
done
if command -v perl >/dev/null 2>&1; then
  # Watcher. It must NOT move the gate into a process group of its own.
  #
  # It used to: the child called `setpgrp(0, 0)`, which made expiry able to kill
  # the whole tree — but it also put the gate in a group the CALLER cannot
  # address. Measured: perl pgid 60922, gate pgid 60923. So the supervisor's
  # group signals and its KILL escalation both landed on a group containing only
  # perl, and the gate survived cancellation outright:
  #   SIGHUP  -> executor exited 129 in 0s, gate still running (no $SIG{HUP} at
  #              all, so perl died instantly and nothing forwarded)
  #   SIGTERM with a TERM-ignoring gate -> 143 after 12s, gate still running
  #              (perl forwarded TERM but never escalated; the supervisor's KILL
  #              hit perl's group, not the gate's)
  # run_normalised already gives this whole invocation its own group via `set -m`,
  # so isolation is provided one level up and the child simply stays put. Then
  # one group covers perl + gate + grandchildren, and the supervisor can both
  # signal and escalate on it. INT/TERM/HUP are left at their default
  # disposition on purpose: a group signal should take perl and the gate down
  # together, and escalation is the supervisor's job, in one place.
  run_normalised perl -e '
    my $secs = shift @ARGV;
    defined(my $pid = fork) or die "run-gate: fork: $!\n";
    if ($pid == 0) { exec @ARGV or die "run-gate: exec failed: $!\n" }
    # Address the group only when we are its leader. Without that check, a
    # caller that did not create a group for us would have its OWN group
    # signalled — far worse than a leaked gate.
    my $target = (getpgrp(0) == $$) ? -$$ : $pid;
    $SIG{ALRM} = sub {
      local $SIG{TERM} = "IGNORE";      # do not TERM ourselves out of the handler
      kill "TERM", $target;
      sleep 2;
      kill "KILL", $target;             # when $target is our group this ends us
      exit 124;                         # reached only in the pid-fallback case;
    };                                  # otherwise the supervisor maps 137 -> 124
    alarm $secs;
    my $r;
    do { $r = waitpid($pid, 0) } while ($r == -1 && $!{EINTR});
    exit(($? & 127) ? 128 + ($? & 127) : $? >> 8);
  ' "$SECS" "$@"
fi
# Nothing here can force-kill, so no run can honour the contract. Refusing is the
# only honest outcome: running anyway would produce a gate result whose timeout
# semantics are weaker than every other host's.
echo "run-gate: no timeout tool that can force-kill the gate (need GNU timeout/gtimeout with --kill-after, or perl) — refusing to run" >&2
exit 2