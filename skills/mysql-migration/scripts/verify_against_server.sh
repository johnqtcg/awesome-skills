#!/usr/bin/env bash
# Execute the DDL algorithm/lock claims in references/ddl-algorithm-matrix.md
# against a real MySQL server and report any the server contradicts.
#
# This is the only check in this skill that can falsify the matrix itself. The
# Python tests verify that the documentation and the linter agree with each
# other; they cannot detect a claim that is internally consistent and wrong.
#
# Opt-in. With no server configured it SKIPS (exit 0) rather than passing
# silently — "not requested" and "verified" must never look alike.
#
#   MYSQL_MIGRATION_VERIFY=1 \
#   MYSQL_HOST=127.0.0.1 MYSQL_PORT=3306 MYSQL_USER=root MYSQL_PASSWORD=secret \
#   bash scripts/verify_against_server.sh
#
# Exit codes:
#   0  skipped (not requested), or every probe matched the matrix
#   1  the server contradicted a documented claim
#   3  requested, but prerequisites are missing (no client, cannot connect)
#
# The script creates and drops a scratch schema. It never touches an existing
# one: it refuses to run if the schema name already exists.

set -euo pipefail

SCHEMA="${MYSQL_MIGRATION_VERIFY_SCHEMA:-mysql_migration_matrix_probe}"

if [[ "${MYSQL_MIGRATION_VERIFY:-0}" != "1" ]]; then
  echo "SKIP: server verification not requested."
  echo "      Set MYSQL_MIGRATION_VERIFY=1 plus MYSQL_HOST/PORT/USER/PASSWORD to run it."
  echo "      The matrix in references/ddl-algorithm-matrix.md is transcribed from the"
  echo "      manual and guarded by tests, but has NOT been executed against a server."
  exit 0
fi

# This script creates and drops a schema. Require the operator to say out loud
# that the target is disposable, so a copy-pasted command cannot reach a
# production host just because the credentials happened to work.
if [[ "${MYSQL_MIGRATION_VERIFY_DISPOSABLE:-}" != "yes" ]]; then
  echo "ERROR: this script CREATEs and DROPs a schema on the target server." >&2
  echo "       Point it only at a disposable, non-production instance, then set:" >&2
  echo "         MYSQL_MIGRATION_VERIFY_DISPOSABLE=yes" >&2
  exit 3
fi

# The schema name is interpolated into DDL. Constrain it to a plain identifier so
# it cannot carry a backtick, a semicolon, or anything else that would change the
# shape of a CREATE/DROP statement.
if [[ ! "${SCHEMA}" =~ ^[A-Za-z][A-Za-z0-9_]{0,62}$ ]]; then
  echo "ERROR: unsafe schema name: ${SCHEMA}" >&2
  echo "       MYSQL_MIGRATION_VERIFY_SCHEMA must match ^[A-Za-z][A-Za-z0-9_]{0,62}$" >&2
  echo "       (letters, digits and underscore; starts with a letter; max 63 chars)." >&2
  exit 3
fi

if ! command -v mysql >/dev/null 2>&1; then
  echo "ERROR: verification requested but the 'mysql' client is not on PATH." >&2
  exit 3
fi

# Credentials go through a 0600 option file, never on the command line: argv is
# world-readable via ps/procfs for the lifetime of every mysql invocation.
DEFAULTS_FILE="$(mktemp "${TMPDIR:-/tmp}/mysql-migration-verify.XXXXXX")"
chmod 600 "${DEFAULTS_FILE}"
SCHEMA_CREATED=0
# Installed before the file is populated: every exit path from here on, including
# a failed connection, must remove the credentials.
cleanup() {
  if [[ "${SCHEMA_CREATED}" == "1" ]]; then
    mysql --defaults-file="${DEFAULTS_FILE}" --batch --skip-column-names \
      --execute="DROP DATABASE IF EXISTS \`${SCHEMA}\`" >/dev/null 2>&1 || true
  fi
  rm -f "${DEFAULTS_FILE}"
}
trap cleanup EXIT
{
  echo "[client]"
  echo "host=${MYSQL_HOST:-127.0.0.1}"
  echo "port=${MYSQL_PORT:-3306}"
  echo "user=${MYSQL_USER:-root}"
  if [[ -n "${MYSQL_PASSWORD:-}" ]]; then
    echo "password=${MYSQL_PASSWORD}"
  fi
} > "${DEFAULTS_FILE}"

# --defaults-file must be the first argument mysql sees.
mysql_exec() { mysql --defaults-file="${DEFAULTS_FILE}" --batch --skip-column-names "$@"; }

if ! SERVER_VERSION="$(mysql_exec --execute="SELECT VERSION()" 2>/dev/null)"; then
  echo "ERROR: verification requested but the server is unreachable." >&2
  echo "       host=${MYSQL_HOST:-127.0.0.1} port=${MYSQL_PORT:-3306} user=${MYSQL_USER:-root}" >&2
  exit 3
fi
echo "Server: ${SERVER_VERSION}"

if [[ -n "$(mysql_exec --execute="SHOW DATABASES LIKE '${SCHEMA}'")" ]]; then
  echo "ERROR: schema '${SCHEMA}' already exists; refusing to reuse it." >&2
  echo "       Drop it, or set MYSQL_MIGRATION_VERIFY_SCHEMA to an unused name." >&2
  exit 3
fi

mysql_exec --execute="CREATE DATABASE \`${SCHEMA}\`"
SCHEMA_CREATED=1

PASS=0
FAIL=0
FAILURES=()

# probe <label> <accept|reject> <setup SQL> <statement under test>
#
# "accept" means the matrix claims the server permits this algorithm/lock
# combination; "reject" means the matrix claims it does not. A probe fails when
# the server disagrees in either direction — including a claimed rejection that
# actually succeeds, which is how an over-conservative row (COPY where INPLACE
# works) escalates safe migrations to gh-ost for nothing.
probe() {
  local label="$1" expectation="$2" setup="$3" stmt="$4"
  local out rc

  mysql_exec --database="${SCHEMA}" --execute="DROP TABLE IF EXISTS probe_t; ${setup}"

  set +e
  out="$(mysql_exec --database="${SCHEMA}" --execute="${stmt}" 2>&1)"
  rc=$?
  set -e

  if [[ "${expectation}" == "accept" ]]; then
    if [[ ${rc} -eq 0 ]]; then
      PASS=$((PASS + 1)); printf '  ok       %s\n' "${label}"
    else
      FAIL=$((FAIL + 1))
      FAILURES+=("${label}: matrix says ACCEPTED, server rejected -> ${out}")
      printf '  MISMATCH %s (expected accept)\n' "${label}"
    fi
  else
    if [[ ${rc} -ne 0 ]]; then
      PASS=$((PASS + 1)); printf '  ok       %s (rejected as documented)\n' "${label}"
    else
      FAIL=$((FAIL + 1))
      FAILURES+=("${label}: matrix says REJECTED, server accepted it")
      printf '  MISMATCH %s (expected reject)\n' "${label}"
    fi
  fi
}

BASE="CREATE TABLE probe_t (
        id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
        legacy VARCHAR(50) DEFAULT NULL,
        body TEXT,
        nick VARCHAR(63) CHARACTER SET utf8mb4 DEFAULT NULL
      ) ENGINE=InnoDB"

# version_lt <a> <b> -> true when a < b, comparing major.minor.patch numerically.
# Avoids `sort -V`, which is not portable to the BSD sort on macOS.
version_lt() {
  awk -v a="$1" -v b="$2" '
    BEGIN {
      na = split(a, x, /[.-]/); nb = split(b, y, /[.-]/)
      for (i = 1; i <= 3; i++) {
        xi = (i <= na && x[i] ~ /^[0-9]+$/) ? x[i] + 0 : 0
        yi = (i <= nb && y[i] ~ /^[0-9]+$/) ? y[i] + 0 : 0
        if (xi < yi) exit 0
        if (xi > yi) exit 1
      }
      exit 1
    }'
}

echo
echo "Probing the claims this skill previously stated incorrectly:"

# The ALGORITHM=INSTANT clause arrives whole in 8.0.12. A server below that must
# reject it for operations that have nothing to do with ADD COLUMN — this probe
# is the one that would have caught the original 8.0.0 threshold.
if version_lt "${SERVER_VERSION}" "8.0.12"; then
  probe "ALGORITHM=INSTANT on SET DEFAULT (pre-8.0.12)" reject "${BASE}" \
    "ALTER TABLE probe_t ALTER COLUMN legacy SET DEFAULT 'x', ALGORITHM=INSTANT"
  probe "ALGORITHM=INSTANT on ADD COLUMN (pre-8.0.12)" reject "${BASE}" \
    "ALTER TABLE probe_t ADD COLUMN extra INT, ALGORITHM=INSTANT"
else
  probe "ALGORITHM=INSTANT on SET DEFAULT (8.0.12+)" accept "${BASE}" \
    "ALTER TABLE probe_t ALTER COLUMN legacy SET DEFAULT 'x', ALGORITHM=INSTANT"
fi

# ALTER TABLE has no IF [NOT] EXISTS in MySQL; the clause is MariaDB's.
probe "ADD COLUMN IF NOT EXISTS" reject "${BASE}" \
  "ALTER TABLE probe_t ADD COLUMN IF NOT EXISTS extra INT"
probe "DROP COLUMN IF EXISTS" reject "${BASE}" \
  "ALTER TABLE probe_t DROP COLUMN IF EXISTS legacy"

# The audit's headline error: DROP COLUMN was documented as COPY-only.
probe "DROP COLUMN, ALGORITHM=INPLACE, LOCK=NONE" accept "${BASE}" \
  "ALTER TABLE probe_t DROP COLUMN legacy, ALGORITHM=INPLACE, LOCK=NONE"

# Extending VARCHAR is In Place = Yes but Instant = No on every release.
probe "extend VARCHAR in-band, ALGORITHM=INPLACE" accept "${BASE}" \
  "ALTER TABLE probe_t MODIFY COLUMN legacy VARCHAR(200), ALGORITHM=INPLACE, LOCK=NONE"
probe "extend VARCHAR, ALGORITHM=INSTANT" reject "${BASE}" \
  "ALTER TABLE probe_t MODIFY COLUMN legacy VARCHAR(200), ALGORITHM=INSTANT"

# utf8mb4 VARCHAR(63)->(64) crosses 255 bytes: 252 -> 256.
probe "VARCHAR(63)->(64) utf8mb4 crosses 255 bytes, INPLACE" reject "${BASE}" \
  "ALTER TABLE probe_t MODIFY COLUMN nick VARCHAR(64) CHARACTER SET utf8mb4,
     ALGORITHM=INPLACE, LOCK=NONE"

# FULLTEXT never permits concurrent DML.
probe "ADD FULLTEXT INDEX, LOCK=NONE" reject "${BASE}" \
  "ALTER TABLE probe_t ADD FULLTEXT INDEX ft_body (body), ALGORITHM=INPLACE, LOCK=NONE"
probe "ADD FULLTEXT INDEX, LOCK=SHARED" accept "${BASE}" \
  "ALTER TABLE probe_t ADD FULLTEXT INDEX ft_body (body), ALGORITHM=INPLACE, LOCK=SHARED"

# ADD PRIMARY KEY permits concurrent DML.
probe "ADD PRIMARY KEY, LOCK=NONE" accept \
  "CREATE TABLE probe_t (a BIGINT NOT NULL, b BIGINT NOT NULL) ENGINE=InnoDB" \
  "ALTER TABLE probe_t ADD PRIMARY KEY (a), ALGORITHM=INPLACE, LOCK=NONE"

# ADD FOREIGN KEY: INPLACE only while foreign_key_checks is off.
mysql_exec --database="${SCHEMA}" --execute="
  DROP TABLE IF EXISTS probe_child; DROP TABLE IF EXISTS probe_parent;
  CREATE TABLE probe_parent (id BIGINT NOT NULL PRIMARY KEY) ENGINE=InnoDB;
  CREATE TABLE probe_child (id BIGINT NOT NULL PRIMARY KEY, p_id BIGINT,
                            KEY k_p (p_id)) ENGINE=InnoDB;"
probe "ADD FOREIGN KEY, INPLACE, foreign_key_checks=1" reject "SELECT 1" \
  "SET SESSION foreign_key_checks = 1;
   ALTER TABLE probe_child ADD CONSTRAINT fk_p FOREIGN KEY (p_id)
     REFERENCES probe_parent(id), ALGORITHM=INPLACE, LOCK=NONE"
probe "ADD FOREIGN KEY, INPLACE, foreign_key_checks=0" accept "SELECT 1" \
  "SET SESSION foreign_key_checks = 0;
   ALTER TABLE probe_child ADD CONSTRAINT fk_p FOREIGN KEY (p_id)
     REFERENCES probe_parent(id), ALGORITHM=INPLACE, LOCK=NONE"

# Partition clauses: 5.7 accepts only DEFAULT; 8.0 accepts INPLACE.
PART="CREATE TABLE probe_t (id BIGINT NOT NULL, PRIMARY KEY (id)) ENGINE=InnoDB
      PARTITION BY RANGE (id) (PARTITION p0 VALUES LESS THAN (100))"
if [[ "${SERVER_VERSION}" == 5.7* ]]; then
  probe "5.7 ADD PARTITION, ALGORITHM=INPLACE" reject "${PART}" \
    "ALTER TABLE probe_t ADD PARTITION (PARTITION p1 VALUES LESS THAN (200)),
       ALGORITHM=INPLACE, LOCK=NONE"
  probe "5.7 ADD PARTITION, no algorithm clause" accept "${PART}" \
    "ALTER TABLE probe_t ADD PARTITION (PARTITION p1 VALUES LESS THAN (200))"
  probe "5.7 ALGORITHM=INSTANT is not a valid algorithm" reject "${BASE}" \
    "ALTER TABLE probe_t ADD COLUMN extra INT, ALGORITHM=INSTANT"
else
  probe "8.0 ADD PARTITION (RANGE), ALGORITHM=INPLACE, LOCK=NONE" accept "${PART}" \
    "ALTER TABLE probe_t ADD PARTITION (PARTITION p1 VALUES LESS THAN (200)),
       ALGORITHM=INPLACE, LOCK=NONE"
  probe "8.0 REORGANIZE PARTITION, LOCK=NONE" reject "${PART}" \
    "ALTER TABLE probe_t REORGANIZE PARTITION p0 INTO
       (PARTITION p0a VALUES LESS THAN (50), PARTITION p0b VALUES LESS THAN (100)),
       ALGORITHM=INPLACE, LOCK=NONE"
fi

echo
echo "matched ${PASS}, mismatched ${FAIL}"
if [[ ${FAIL} -gt 0 ]]; then
  echo
  echo "The server contradicted references/ddl-algorithm-matrix.md:" >&2
  for f in ${FAILURES[@]+"${FAILURES[@]}"}; do
    echo "  - ${f}" >&2
  done
  echo >&2
  echo "Re-read the manual for these rows before changing the matrix — a probe can also" >&2
  echo "fail because this script's setup table does not match the row's preconditions." >&2
  exit 1
fi

echo "All probed matrix claims hold on ${SERVER_VERSION}."
