#!/usr/bin/env bash
# Run all regression checks for the pg-migration skill.
#
# Note: no `set -e`. A non-zero exit from one stage must not abort the run before
# the later stages report -- a partial run that looks green is worse than a red one.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEST_DIR="${SCRIPT_DIR}/tests"
SKILL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

status=0
note() { printf '\n=== %s ===\n' "$1"; }

run_linter_self_check() {
  local check_status=0 tmp out lint_status f

  note "6/7 Linter self-check on the documented-correct forms"
  # The two canonical guard forms must lint clean. If either regresses, the skill is
  # recommending SQL its own checker rejects.
  # macOS: a bare `mktemp -d` ignores $TMPDIR and targets a path that may not be
  # writable under a sandbox. Always pass an explicit template rooted at $TMPDIR.
  tmp="$(mktemp -d "${TMPDIR:-/tmp}/pgmig.XXXXXX")" || {
    echo "  stage 6 failed: cannot create a writable temp dir" >&2
    return 1
  }

  cat > "${tmp}/txn.sql" <<'SQL'
BEGIN;
SET LOCAL lock_timeout = '3s';
SET LOCAL statement_timeout = '30s';
ALTER TABLE users ADD COLUMN bio text;
COMMIT;
SQL

  cat > "${tmp}/concurrent.sql" <<'SQL'
SET lock_timeout = '3s';
SET statement_timeout = 0;
CREATE INDEX CONCURRENTLY idx_orders_date ON orders (created_at);
RESET statement_timeout;
RESET lock_timeout;
SQL

  # Exit status is the machine contract. The clean text is intentionally not parsed:
  # it is human-facing and may change without changing linter semantics.
  for f in txn concurrent; do
    if out="$(python3 "${SCRIPT_DIR}/lint_migration.py" "${tmp}/${f}.sql" 2>&1)"; then
      echo "  ${f}.sql: clean"
    else
      echo "  ${f}.sql: UNEXPECTED FINDINGS" >&2
      echo "${out}" >&2
      check_status=1
    fi
  done

  # A checker that reports nothing on a known-bad input is worse than useless.
  cat > "${tmp}/known_bad.sql" <<'SQL'
SET LOCAL lock_timeout = '3s';
CREATE INDEX CONCURRENTLY idx_a ON t (c);
SQL
  if out="$(python3 "${SCRIPT_DIR}/lint_migration.py" "${tmp}/known_bad.sql" 2>&1)"; then
    lint_status=0
  else
    lint_status=$?
  fi
  case "${lint_status}:${out}" in
    1:*PG001*) echo "  known_bad.sql: correctly flagged PG001" ;;
    *) echo "  known_bad.sql: linter FAILED to flag PG001 with findings exit 1" >&2
       echo "${out}" >&2
       check_status=1 ;;
  esac

  rm -rf "${tmp}"
  return "${check_status}"
}

case "${1:-}" in
  "") ;;
  --stage6-only)
    run_linter_self_check
    exit $?
    ;;
  *)
    echo "usage: $0 [--stage6-only]" >&2
    exit 2
    ;;
esac

note "1/7 Contract tests (SKILL.md structure + reference files)"
python3 -m pytest "${TEST_DIR}/test_skill_contract.py" -q || status=1

note "2/7 Golden scenario tests (fixtures + linter agreement)"
python3 -m pytest "${TEST_DIR}/test_golden_scenarios.py" -q || status=1

note "3/7 Linter behavioral tests (every rule: fires + stays silent)"
python3 -m pytest "${TEST_DIR}/test_lint_migration.py" -q || status=1

note "4/7 Documentation fact-drift guards"
python3 -m pytest "${TEST_DIR}/test_pg_facts_drift.py" -q || status=1

note "5/7 Skill exemplars linted by the skill's own checker"
python3 -m pytest "${TEST_DIR}/test_skill_exemplars.py" -q || status=1

run_linter_self_check || status=1

note "7/7 Live PostgreSQL matrix (14-18)"
# The only stage that asserts against PostgreSQL rather than against our own
# description of it. Reported explicitly as NOT RUN when no server is reachable:
# every other stage can be green while a documented fact is simply false, which is
# how `max(uuid)` and the partitioned-FK rule survived a full green suite.
live_ran=0
if python3 "${TEST_DIR}/pg_server.py" >/dev/null 2>&1; then
  echo "  servers found:"
  python3 "${TEST_DIR}/pg_server.py" | sed 's/^/    /'
  # Count only usable servers. pg_server.py also prints a row for one it could not
  # reach or one whose version contradicts its container name; counting those as
  # "found" would let a broken server stand in for a verified one.
  n_found="$(python3 "${TEST_DIR}/pg_server.py" \
             | grep -cv 'UNREACHABLE\|MISLABELLED' || true)"
  if python3 "${TEST_DIR}/pg_server.py" | grep -q MISLABELLED; then
    echo "  a container reports a different major than its name claims." >&2
    status=1
  fi
  python3 -m pytest "${TEST_DIR}/test_pg_server_matrix.py" -q || status=1
  if [ "${n_found}" -eq 5 ]; then
    live_ran=1
  else
    echo "  PARTIAL: ${n_found} of 5 majors reachable. The 14-18 claim is unverified." >&2
  fi
else
  echo "  NOT RUN — no live PostgreSQL reachable." >&2
  echo "  The offline stages above cannot verify any PostgreSQL behaviour claim." >&2
  echo "  Run: bash scripts/pg_server_harness.sh" >&2
fi

note "Mutation sweep (anchors only; run scripts/mutation_sweep.py for the full sweep)"
python3 "${SCRIPT_DIR}/mutation_sweep.py" --verify || status=1

echo ""
if [ "${status}" -ne 0 ]; then
  echo "pg-migration skill regression checks FAILED." >&2
  exit 1
fi

# "Everything I ran passed" is not "everything passed". The offline stages cannot check
# a single claim about PostgreSQL's actual behaviour, so calling the run green without
# the live matrix would report exactly the confidence this skill was wrong about twice.
if [ "${live_ran}" -eq 0 ]; then
  echo "pg-migration skill regression checks INCOMPLETE (exit 3)." >&2
  echo "  Offline stages passed. Stage 7 did not verify PostgreSQL on all five majors," >&2
  echo "  so no behaviour claim in this skill was checked against a server this run." >&2
  echo "  Run: bash scripts/pg_server_harness.sh" >&2
  exit 3
fi

echo "pg-migration skill regression checks passed (offline + live 14-18)."
exit 0
