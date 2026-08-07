#!/usr/bin/env bash
# Execute the disputed DDL against a real Oracle instance and report whether the server
# agrees with what this skill documents.
#
# Every lock/version claim here is otherwise documentation-derived. This script is the
# mechanism for turning the checkable subset into measured facts. It is SKIP-by-default:
# without a reachable instance it exits 0 with a clear "not requested" message so CI
# stays green, and exits non-zero only when a probe genuinely contradicts the docs.
#
#   ORACLE_TEST_DSN     e.g. system/pw@//localhost:1521/FREEPDB1   (required to run)
#   ORACLE_ALLOW_DDL=1  required acknowledgement — this script CREATEs and DROPs tables
#
# Usage:
#   ORACLE_TEST_DSN=... ORACLE_ALLOW_DDL=1 bash scripts/verify_against_server.sh
#   bash scripts/verify_against_server.sh --list      # show probes without connecting
#
# Exit codes: 0 all probes passed or skipped · 1 a probe contradicted the docs
#             2 setup/usage error (distinct from a finding — never conflate them)
#
# TWO DESIGN RULES, both learned from getting them wrong:
#
#  1. Every probe runs against a FRESHLY REBUILT table. An earlier revision shared one
#     scratch table across probes, so P01's RENAME COLUMN removed the column P05 and P09
#     depended on: P05 then "failed" with ORA-00904 instead of the ORA-01439 it was
#     testing and passed anyway, and P09 failed permanently. Probe order must never be
#     load-bearing.
#  2. A "must fail" probe asserts the SPECIFIC ORA code. "It errored" is not evidence
#     that it errored for the documented reason — a typo, a missing table or a privilege
#     error all produce a non-zero result and would score as a confirmed rejection.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# id | claim | must-succeed SQL | must-fail SQL | required ORA code on failure
# Use @T@ for the scratch table name; it is substituted literally, never eval'd.
PROBES=$(cat <<'PROBE_EOF'
P01|RENAME COLUMN is supported (9.2+) and metadata-only|ALTER TABLE @T@ RENAME COLUMN c_num TO c_num2|-|-
P02|Widening NUMBER precision AND scale together is allowed on a populated table|ALTER TABLE @T@ MODIFY (c_amt NUMBER(12,4))|-|-
P03|Widening VARCHAR2 length is allowed on a populated table|ALTER TABLE @T@ MODIFY (c_txt VARCHAR2(320))|-|-
P04|Narrowing a char column whose data fits is allowed|ALTER TABLE @T@ MODIFY (c_txt VARCHAR2(10))|-|-
P05|Decreasing NUMBER scale on a populated column is REJECTED|-|ALTER TABLE @T@ MODIFY (c_amt NUMBER(8,1))|ORA-01440
P06|Changing datatype class on a populated column is REJECTED|-|ALTER TABLE @T@ MODIFY (c_num VARCHAR2(40))|ORA-01439
P07|NOT NULL over existing NULLs is REJECTED|-|ALTER TABLE @T@ MODIFY (c_null NUMBER NOT NULL)|ORA-02296
P08|Narrowing a char column whose data does NOT fit is REJECTED|-|ALTER TABLE @T@ MODIFY (c_txt VARCHAR2(2))|ORA-01441
P09|DBA_EXTENTS has no DATA_OBJECT_ID column|-|SELECT data_object_id FROM dba_extents WHERE ROWNUM = 1|ORA-00904
P10|DBA_EXTENTS does expose RELATIVE_FNO and BLOCK_ID|SELECT relative_fno, block_id FROM dba_extents WHERE ROWNUM = 1|-|-
P11|ADD CONSTRAINT ... ENABLE NOVALIDATE is accepted syntax|ALTER TABLE @T@ ADD CONSTRAINT ck_probe CHECK (c_num > -1) ENABLE NOVALIDATE|-|-
P12|DDL_LOCK_TIMEOUT accepts 0 (legal value, meaning NOWAIT)|ALTER SESSION SET DDL_LOCK_TIMEOUT = 0|-|-
P13|DDL_LOCK_TIMEOUT rejects a value above the 1000000 ceiling|-|ALTER SESSION SET DDL_LOCK_TIMEOUT = 1000001|ORA-00068
P14|DDL_LOCK_TIMEOUT rejects a negative value|-|ALTER SESSION SET DDL_LOCK_TIMEOUT = -1|ORA-00068
PROBE_EOF
)

probe_count() { printf '%s\n' "$PROBES" | grep -c '^P'; }

if [ "${1:-}" = "--list" ]; then
  printf '%s\n' "$PROBES" | while IFS='|' read -r id claim ok bad code; do
    [ -z "$id" ] && continue
    if [ "$code" != "-" ]; then
      printf '%-5s [expects %s] %s\n' "$id" "$code" "$claim"
    else
      printf '%-5s [expects success] %s\n' "$id" "$claim"
    fi
  done
  printf '\n%s probe(s). Set ORACLE_TEST_DSN and ORACLE_ALLOW_DDL=1 to run them.\n' "$(probe_count)"
  exit 0
fi

# --- gating ---------------------------------------------------------------------------
# "Not requested" and "broken" must be distinguishable. No DSN is the former.
if [ -z "${ORACLE_TEST_DSN:-}" ]; then
  echo "SKIP: ORACLE_TEST_DSN is not set — server verification not requested."
  echo "      Every lock/version claim in this skill therefore remains"
  echo "      documentation-derived. See scripts/tests/COVERAGE.md section 7."
  exit 0
fi

if [ "${ORACLE_ALLOW_DDL:-0}" != "1" ]; then
  echo "ERROR: ORACLE_TEST_DSN is set but ORACLE_ALLOW_DDL is not 1." >&2
  echo "       This script CREATEs and DROPs a scratch table. Refusing to run DDL" >&2
  echo "       against an instance without an explicit acknowledgement." >&2
  exit 2
fi

if ! command -v sqlplus >/dev/null 2>&1; then
  echo "ERROR: sqlplus not found on PATH; cannot run server verification." >&2
  exit 2
fi

T="ORAMIG_PROBE_$$"
RESULTS="$(mktemp "${TMPDIR:-/tmp}/oramig_results.XXXXXX")"
SETUP_FAILURES="$(mktemp "${TMPDIR:-/tmp}/oramig_setup.XXXXXX")"

# The DSN carries a password: keep it out of argv and out of the transcript.
run_sql() {
  sqlplus -S -L /nolog <<SQLPLUS_EOF 2>&1
WHENEVER SQLERROR CONTINUE NONE
CONNECT ${ORACLE_TEST_DSN}
SET HEADING OFF FEEDBACK OFF PAGESIZE 0 VERIFY OFF ECHO OFF
${1}
EXIT SUCCESS
SQLPLUS_EOF
}

drop_scratch() { run_sql "DROP TABLE ${T} PURGE;" >/dev/null 2>&1 || true; }
cleanup() { drop_scratch; rm -f "${RESULTS}" "${SETUP_FAILURES}"; }
trap cleanup EXIT

# sqlplus exits 0 even after an ORA- error here, because the probe loop needs to inspect
# the error text rather than die on it (WHENEVER SQLERROR CONTINUE NONE + EXIT SUCCESS).
# So EVERY caller must judge by the OUTPUT, never by the exit code. An earlier revision
# checked only `if ! run_sql ...` in rebuild_scratch, which meant a privilege, quota or
# tablespace failure creating the scratch table went unnoticed — and the run then
# reported a dozen probe failures as "the server contradicts the documentation" (exit 1)
# when the truth was "the harness never got set up" (exit 2). Those must never be
# conflated: one demands a doc change, the other a DBA.
sql_errored() { printf '%s' "$1" | grep -qE '(^|[^A-Z0-9])(ORA|SP2|PLS)-[0-9]+'; }

# Rebuilt before EVERY probe so no probe can observe another's side effects.
rebuild_scratch() {
  local out
  drop_scratch
  out="$(run_sql "
CREATE TABLE ${T} (
  id     NUMBER PRIMARY KEY,
  c_num  NUMBER(10),
  c_amt  NUMBER(10,2),
  c_txt  VARCHAR2(100),
  c_null NUMBER
);
INSERT INTO ${T} VALUES (1, 42, 12.34, 'probe-row', NULL);
COMMIT;
" 2>&1)" || true
  if sql_errored "$out"; then
    SETUP_ERROR="$(printf '%s' "$out" | grep -oE '(ORA|SP2|PLS)-[0-9]+.*' | head -1)"
    return 1
  fi

  # Creating without error is not the same as the row being there. Confirm the fixture
  # actually exists, or a silently empty table turns every data-dependent rejection
  # probe into a false "the server accepted it".
  out="$(run_sql "SELECT COUNT(*) FROM ${T};" 2>&1)" || true
  if sql_errored "$out" || ! printf '%s' "$out" | grep -qE '(^|[^0-9])1([^0-9]|$)'; then
    SETUP_ERROR="scratch table verification returned: $(printf '%s' "$out" | tr '\n' ' ')"
    return 1
  fi
  return 0
}

SETUP_ERROR=""

echo "Verifying against the configured instance (scratch table ${T}) ..."
if ! rebuild_scratch; then
  echo "ERROR: could not create the scratch table — check the DSN and privileges." >&2
  echo "       ${SETUP_ERROR}" >&2
  echo "       This is a setup failure, not a finding about Oracle's behaviour." >&2
  exit 2
fi

printf '\n%-5s %-26s %s\n' "ID" "VERDICT" "CLAIM"

while IFS='|' read -r id claim ok bad code; do
  [ -z "$id" ] && continue
  # A mid-run setup failure is not a finding about Oracle — record it separately so it
  # cannot be summed into "N probes contradicted the documentation".
  if ! rebuild_scratch; then
    printf '%-5s %-26s %s\n' "$id" "SETUP-FAILED" "$claim"
    echo "$id|${SETUP_ERROR}" >>"$SETUP_FAILURES"
    continue
  fi

  verdict="pass"

  if [ "$ok" != "-" ]; then
    sql="${ok//@T@/$T}"
    if ! out="$(run_sql "${sql};")" || printf '%s' "$out" | grep -qE '^(ORA|SP2|PLS)-[0-9]+'; then
      verdict="FAIL(should-succeed)"
    fi
  fi

  if [ "$bad" != "-" ] && [ "$verdict" = "pass" ]; then
    sql="${bad//@T@/$T}"
    out="$(run_sql "${sql};" || true)"
    if ! printf '%s' "$out" | grep -qE '^(ORA|SP2|PLS)-[0-9]+'; then
      verdict="FAIL(was-accepted)"
    elif [ "$code" != "-" ] && ! printf '%s' "$out" | grep -q "$code"; then
      # Errored, but not for the documented reason. Reporting this as a pass is how a
      # broken probe masquerades as a confirmed fact.
      got="$(printf '%s' "$out" | grep -oE '(ORA|SP2|PLS)-[0-9]+' | head -1)"
      verdict="FAIL(want ${code}, got ${got:-?})"
    fi
  fi

  printf '%-5s %-26s %s\n' "$id" "$verdict" "$claim"
  [ "$verdict" = "pass" ] || echo "$id|$verdict" >>"$RESULTS"
done <<PROBE_INPUT
${PROBES}
PROBE_INPUT

# Setup failures are checked FIRST and exit 2: if the fixture never existed, the probe
# verdicts are meaningless and reporting them as documentation contradictions would send
# someone to rewrite correct docs.
if [ -s "$SETUP_FAILURES" ]; then
  n=$(wc -l <"$SETUP_FAILURES" | tr -d ' ')
  echo ""
  echo "ERROR: the scratch fixture could not be built for ${n} probe(s):" >&2
  sed 's/^/  /' "$SETUP_FAILURES" >&2
  echo "This is a setup failure (privileges, quota, tablespace), not a finding." >&2
  exit 2
fi

if [ -s "$RESULTS" ]; then
  n=$(wc -l <"$RESULTS" | tr -d ' ')
  echo ""
  echo "${n} probe(s) did not match the documentation:"
  sed 's/^/  /' "$RESULTS"
  echo ""
  echo "Either the skill's claim is wrong for this release, or the probe is."
  echo "Investigate before shipping — do not silence."
  exit 1
fi

echo ""
echo "All $(probe_count) probes agree with the documented behaviour on this instance."
