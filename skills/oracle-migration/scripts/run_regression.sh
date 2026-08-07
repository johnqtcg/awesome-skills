#!/usr/bin/env bash
# Run all regression checks for the oracle-migration skill.
#
# Stage 3 is the one that matters most: the golden fixtures are fed to the real checker
# and its output is compared against per-fixture expectations, so a fixture can no longer
# pass by restating its own conclusion.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEST_DIR="${SCRIPT_DIR}/tests"

echo "[1/6] Syntax check of the shipped scripts"
python3 -m py_compile "${SCRIPT_DIR}/lint_migration.py" "${SCRIPT_DIR}/mutation_sweep.py"

# Discovered, not enumerated. Naming the files individually meant a new test module
# (test_server_harness.py) sat in the directory without ever being run by the runner.
echo "[2/6] Test suite (contract, fact-drift guards, golden scenarios, server harness)"
python3 -m pytest "${TEST_DIR}" -q --no-header

echo "[3/6] Coverage document matches the live suite"
python3 "${TEST_DIR}/report_coverage.py" --check

echo "[4/6] Checker self-test: a known-bad script must exit 1, a clean one must exit 0"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/oracle-migration-regression.XXXXXX")"
trap 'rm -rf "${TMP}"' EXIT

cat >"${TMP}/bad.sql" <<'SQL'
ALTER TABLE orders ADD CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id);
SQL
cat >"${TMP}/good.sql" <<'SQL'
ALTER SESSION SET DDL_LOCK_TIMEOUT = 3;
ALTER TABLE orders ADD (tracking_id VARCHAR2(50));
SQL

if python3 "${SCRIPT_DIR}/lint_migration.py" "${TMP}/bad.sql" >/dev/null 2>&1; then
  echo "FAIL: checker exited 0 on a script with critical findings" >&2
  exit 1
fi
if ! python3 "${SCRIPT_DIR}/lint_migration.py" "${TMP}/good.sql" >/dev/null 2>&1; then
  echo "FAIL: checker exited non-zero on a clean script" >&2
  exit 1
fi

echo "[5/6] Mutation sweep (are the assertions load-bearing?)"
if [ "${SKIP_MUTATION_SWEEP:-0}" = "1" ]; then
  echo "      skipped via SKIP_MUTATION_SWEEP=1"
else
  python3 "${SCRIPT_DIR}/mutation_sweep.py"
fi

# Skips cleanly when ORACLE_TEST_DSN is unset, so CI stays green without an instance.
# When one is available it turns the documentation-derived claims into measured ones.
echo "[6/6] Server verification (skipped unless ORACLE_TEST_DSN is set)"
bash "${SCRIPT_DIR}/verify_against_server.sh"

echo ""
echo "oracle-migration skill regression checks passed."
