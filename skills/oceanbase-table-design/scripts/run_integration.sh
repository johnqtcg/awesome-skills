#!/usr/bin/env bash
# V2-V4 integration verification driver. Requires a reachable OceanBase instance and obclient.
#
# Usage:
#   ./run_integration.sh --dsn "obclient -h127.0.0.1 -P2881 -uroot@mysql#c1 -pXXX" \
#                        --mode mysql --version 4.5.0 --out tests/integration/results
#   ./run_integration.sh ... --version 4.4.2-bp1
#   ./run_integration.sh ... --dry-run          # only print which scripts would run, do not connect to the DB
#
# Three script kinds, three assertion styles (**none of them may be papered
# over with `|| true`**):
#   positive  positive example: any statement erroring fails the whole script
#   negative  negative example: judged case by case (scripts/check_negative_log.py) --
#             every case must error **individually**; an extra unrelated error must not
#             mask one case that unexpectedly succeeded
#   probe     version probing / unverified capability: both success and failure are
#             valid observations, only requires non-empty output that gets archived;
#             this is the only class with no exit-code assertion, and it is already
#             physically isolated from positive/negative
#
# **Layered by the minimum version per capability**: every script declares
# min_version. Below that version it is skipped, not treated as a failure --
# otherwise "this version doesn't support some capability" would be
# misreported as the whole positive suite failing.
# Capabilities whose minimum version has not been verified (C2/C3) always go
# into probe, and are only promoted to positive for a specific version after verification.
set -uo pipefail

if [ "${1:-}" = "--self-test" ]; then SELFTEST_ONLY=1; else SELFTEST_ONLY=0; fi

# OUT stays empty until ROOT is known, then defaults to a path INSIDE the skill.
# It used to default to the relative "tests/integration/results", which is resolved
# against the caller's cwd -- so a --dry-run launched from the repo root wrote a
# results tree next to the repo's own directories instead of into this skill. An
# explicit --out is still honoured verbatim, relative to wherever the caller is.
DSN=""; MODE="mysql"; VERSION=""; OUT=""; DRYRUN=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dsn)     DSN="$2"; shift 2 ;;
    --mode)    MODE="$2"; shift 2 ;;
    --version) VERSION="$2"; shift 2 ;;
    --out)     OUT="$2"; shift 2 ;;
    --dry-run) DRYRUN=1; shift ;;
    --self-test) shift ;;
    -h|--help) sed -n '1,25p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

[[ $SELFTEST_ONLY -eq 1 || -n "$VERSION" ]] || {
  echo "must provide --version (determines which scripts run, layered by capability)" >&2; exit 2; }
[[ $SELFTEST_ONLY -eq 1 || $DRYRUN -eq 1 || -n "$DSN" ]] || {
  echo "must provide --dsn" >&2; exit 2; }
[[ "$MODE" == "mysql" || "$MODE" == "oracle" ]] || {
  echo "--mode can only be mysql|oracle" >&2; exit 2; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
SQLDIR="$ROOT/tests/integration"
: "${OUT:=$ROOT/tests/integration/results}"
DEST="$OUT/$VERSION-$MODE"
[[ $SELFTEST_ONLY -eq 1 ]] || mkdir -p "$DEST"

# ---- Version comparison: normalize 4.4.2-bp1 into a comparable four-segment number ----
# BP is treated as the fourth segment; no BP is recorded as 0. 4.3.5 < 4.3.5-bp1 < 4.4.2
#
# Compatibility note: **do not use ${v,,} or ${v//x/y}** -- that's bash 4+
# syntax; macOS's bundled bash 3.2 raises "bad substitution", the function
# returns an empty string, and then [ "" -ge "" ] evaluates true -> the
# version gate silently fails open and every script gets executed.
# This is why tr/sed are used instead, with a fail-closed check inside ver_ge.
ver_key() {
  v="$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')"
  bp="$(printf '%s' "$v" | sed -n 's/.*bp\([0-9][0-9]*\).*/\1/p')"
  [ -n "$bp" ] || bp=0
  core="${v%%-*}"; core="${core%%bp*}"
  core="$(printf '%s' "$core" | tr '_' '.')"
  a="$(printf '%s' "$core" | cut -d. -f1)"
  b="$(printf '%s' "$core" | cut -d. -f2)"
  c="$(printf '%s' "$core" | cut -d. -f3)"
  printf "%d%03d%03d%03d" "${a:-0}" "${b:-0}" "${c:-0}" "$bp"
}
ver_ge() {
  k1="$(ver_key "$1")"; k2="$(ver_key "$2")"
  # fail-closed: exit immediately if pure digits can't be parsed, never treat it as "satisfied" and keep going
  case "$k1" in ''|*[!0-9]*) echo "cannot parse version: '$1' -> '$k1'" >&2; exit 3 ;; esac
  case "$k2" in ''|*[!0-9]*) echo "cannot parse version: '$2' -> '$k2'" >&2; exit 3 ;; esac
  [ "$k1" -ge "$k2" ]
}

# ---- Version comparison self-test (no DB needed, runs on --self-test or every startup) ----
ver_self_test() {
  fails=0
  chk() {  # chk <a> <op ge|lt> <b>
    if [ "$2" = "ge" ]; then
      ver_ge "$1" "$3" || { echo "  FAIL: expected $1 >= $3"; fails=$((fails+1)); }
    else
      ver_ge "$1" "$3" && { echo "  FAIL: expected $1 < $3"; fails=$((fails+1)); }
    fi
    return 0
  }
  chk 4.5.0     ge 4.3.5
  chk 4.3.0     lt 4.3.5
  chk 4.3.0     lt 4.3.5-bp1
  chk 4.3.5     lt 4.3.5-bp1
  chk 4.3.5-bp1 ge 4.3.5
  chk 4.3.5-bp1 lt 4.4.2
  chk 4.4.2     lt 4.4.2-bp1
  chk 4.4.2-bp1 ge 4.4.2
  chk 4.4.2-BP1 ge 4.4.2          # case-insensitive
  chk 4.2.0     ge 4.0.0
  chk 4.5.0     ge 4.0.0
  chk 4.10.0    ge 4.9.0          # numeric comparison, not lexicographic
  if [ "$fails" -eq 0 ]; then
    echo "ver_self_test: OK (all 12 version comparisons correct)"; return 0
  fi
  echo "ver_self_test: FAILED ($fails item(s))"; return 1
}

if [ "$SELFTEST_ONLY" -eq 1 ]; then ver_self_test; exit $?; fi

# self-test on startup: once the version gate fails it fails open, so this must block before any SQL runs
ver_self_test >/dev/null || {
  echo "version comparison self-test failed, refusing to continue (otherwise the version gate would silently fail open)" >&2; exit 3; }

TARGET_KEY="$(ver_key "$VERSION")"

# ---- Script list: file|kind|min_version|description ----
# min_version = "4.0.0" means applicable across the whole 4.x line
MYSQL_PLAN=(
  "mysql_base.sql|positive|4.0.0|basic table creation (HASH/KEY/RANGE/LIST/subpartitions/no primary key/duplicate table/queue table/global unique index)"
  "mysql_negative.sql|negative|4.0.0|14 L0 negative cases (per-case assertion)"
  "mysql_v430.sql|positive|4.3.0|columnstore and row-column redundant table creation"
  "mysql_v435.sql|positive|4.3.5|automatic partition split by SIZE"
  "mysql_v435bp1.sql|positive|4.3.5-bp1|heap table ORGANIZATION = HEAP"
  "tablegroup.sql|positive|4.2.0|tablegroup SHARDING three-state positive cases"
  "tablegroup_negative.sql|negative|4.2.0|3 tablegroup constraint negative cases"
  "tablegroup_probe.sql|probe|4.2.0|SCOPE syntax availability + Leader distribution for NONE (version-dependent)"
  "explain.sql|positive|4.0.0|partition pruning / index selection / join localization"
  "explain_v430.sql|positive|4.3.0|columnstore scan path"
  "tablet.sql|positive|4.0.0|reconcile actual tablet count + the real per-node ceiling"
  "storage_v430.sql|positive|4.3.0|actual differences across the three Column Group forms"
  "storage_base.sql|positive|4.0.0|queue-table pattern queries"
  "storage_negative.sql|negative|4.3.5|automatic partitioning + columnstore mutual exclusion (depends on mysql_v435.sql)"
  "mysql_probe.sql|probe|4.0.0|C2/C3 capabilities: SKIP_INDEX / DYNAMIC_PARTITION_POLICY / AUTO_INCREMENT_MODE"
  "storage_probe.sql|probe|4.0.0|actual dynamic-partition behavior + DROP PARTITION interaction with global indexes"
)
ORACLE_PLAN=(
  "oracle_mode.sql|positive|4.0.0|Oracle-mode table creation (HASH/RANGE/LIST column lists + INTERVAL)"
  "oracle_negative.sql|negative|4.0.0|7 Oracle forbidden-combination negative cases"
)

if [[ "$MODE" == "mysql" ]]; then PLAN=("${MYSQL_PLAN[@]}"); else PLAN=("${ORACLE_PLAN[@]}"); fi

echo "== OceanBase Table Design Skill Integration Verification =="
echo "   version: $VERSION (key=$TARGET_KEY)   mode: $MODE   output: $DEST"
echo

FAIL=0
declare -a REPORT=()
note() { REPORT+=("$1"); }

run_positive() {  # positive: any statement failing fails the whole script, exit code is never exempted
  local f="$1" log="$2"
  if $DSN < "$SQLDIR/$f" > "$DEST/$log" 2>&1; then
    echo "   PASS"; note "positive  $f  PASS"
  else
    echo "   FAIL (a positive case should not error, see ${log})"; note "positive  $f  FAIL"; FAIL=1
  fi
}

run_negative() { # negative: judged case by case, the expected set is auto-extracted from @@CASE markers in the SQL
  local f="$1" log="$2"
  $DSN --force < "$SQLDIR/$f" > "$DEST/$log" 2>&1
  if python3 "$SCRIPT_DIR/check_negative_log.py" "$DEST/$log" \
        --expect-from "$SQLDIR/$f" > "$DEST/${log%.log}.verdict.txt" 2>&1; then
    echo "   PASS (every case errored individually)"; note "negative  $f  PASS"
  else
    echo "   FAIL (see ${log%.log}.verdict.txt)"; note "negative  $f  FAIL"; FAIL=1
    sed -n '/\[error\]/,$p' "$DEST/${log%.log}.verdict.txt" | head -6
  fi
}

run_probe() {    # probe: does not assert exit code, but requires non-empty output
  local f="$1" log="$2"
  $DSN --force < "$SQLDIR/$f" > "$DEST/$log" 2>&1
  if [[ -s "$DEST/$log" ]]; then
    echo "   RECORDED (pending manual backfill into references/)"; note "probe     $f  RECORDED"
  else
    echo "   FAIL (probe produced no output at all)"; note "probe     $f  FAIL"; FAIL=1
  fi
}

for entry in "${PLAN[@]}"; do
  # split field by field with parameter expansion, avoiding the bash 3.2
  # compatibility trap of `IFS= read <<<`
  f="${entry%%|*}";            rest="${entry#*|}"
  kind="${rest%%|*}";          rest="${rest#*|}"
  minv="${rest%%|*}";          desc="${rest#*|}"
  if ! ver_ge "$VERSION" "$minv"; then
    echo "-- [skip] $f  (requires >= ${minv}, current ${VERSION})"
    note "skipped   $f  SKIP (min_version=${minv})"
    continue
  fi
  echo "-- [$kind] $f  — $desc"
  if [[ $DRYRUN -eq 1 ]]; then
    echo "   (dry-run)"; note "$kind  $f  DRY-RUN"; continue
  fi
  log="${f%.sql}.log"
  case "$kind" in
    positive) run_positive "$f" "$log" ;;
    negative) run_negative "$f" "$log" ;;
    probe)    run_probe    "$f" "$log" ;;
  esac
done

{
  echo "version: $VERSION"
  echo "mode: $MODE"
  echo "date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "dry_run: $DRYRUN"
  echo "overall: $([[ $FAIL -eq 0 ]] && echo PASS || echo FAIL)"
  echo
  echo "== Per-script results =="
  for line in "${REPORT[@]}"; do echo "  $line"; done
  echo
  echo "== Conclusions pending backfill =="
  echo "1. mysql_probe.log      -> whether SKIP_INDEX / DYNAMIC_PARTITION_POLICY /"
  echo "   AUTO_INCREMENT_MODE are available on this version; if so, backfill capability-matrix.md sections 5-3 and 4,"
  echo "   and promote the corresponding statements from mysql_probe.sql to a positive script for that version"
  echo "2. tablegroup_probe.log -> leader_hosts for SHARDING=NONE; SCOPE syntax availability"
  echo "   -> backfill tablegroup.md section 2.1 and capability-matrix.md section 3"
  echo "3. storage_probe.log    -> observed behavior of DROP PARTITION and global index rebuild"
  echo "   -> backfill capability-matrix.md section 5-2"
  echo "4. tablet.log           -> whether LIMIT_VALUE matches estimate_tablets.py's per_node_limit"
  echo "5. explain*.log         -> actual partitions hit per statement -> checks.partition_pruning.evidence"
  echo
  echo "Note: overall=PASS only means all positives passed, negatives were rejected"
  echo "      case by case as expected, and probes produced output."
  echo "      Until probe items are backfilled, the open items in capability-matrix.md section 5 must"
  echo "      not be claimed as resolved."
  echo "      A skipped item means the capability does not apply to this version, it is **not** a pass."
} > "$DEST/summary.txt"

echo
cat "$DEST/summary.txt"
exit $FAIL
