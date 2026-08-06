#!/usr/bin/env bash
# Run verify_against_server.sh against every version the matrix claims to cover.
#
# This is the check that can actually falsify references/ddl-algorithm-matrix.md.
# Everything else in this skill's test suite only proves the documentation agrees
# with itself.
#
#   docker compose -f scripts/verify-matrix.docker-compose.yml up -d --wait
#   bash scripts/verify_matrix.sh
#   docker compose -f scripts/verify-matrix.docker-compose.yml down
#
# Exit codes:
#   0  every reachable instance matched the matrix (or none were reachable and
#      none were required — reported as SKIPPED, never as success)
#   1  an instance contradicted the matrix
#   3  --require-all was passed and an instance was unreachable

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQUIRE_ALL=0
[[ "${1:-}" == "--require-all" ]] && REQUIRE_ALL=1

# label:port — must match verify-matrix.docker-compose.yml
TARGETS="5.7:33057 8.0.11:33011 8.0:33080 8.4:33084 9.x:33090"

PASSED=""; FAILED=""; SKIPPED=""

for entry in ${TARGETS}; do
  label="${entry%%:*}"
  port="${entry##*:}"

  if ! MYSQL_PWD=verify mysql --host=127.0.0.1 --port="${port}" --user=root \
        --batch --skip-column-names --execute="SELECT 1" >/dev/null 2>&1; then
    SKIPPED="${SKIPPED} ${label}"
    echo "--- ${label} (port ${port}): UNREACHABLE, skipped"
    continue
  fi

  echo "--- ${label} (port ${port}): probing"
  if MYSQL_MIGRATION_VERIFY=1 \
     MYSQL_MIGRATION_VERIFY_DISPOSABLE=yes \
     MYSQL_HOST=127.0.0.1 MYSQL_PORT="${port}" \
     MYSQL_USER=root MYSQL_PASSWORD=verify \
     MYSQL_MIGRATION_VERIFY_SCHEMA="matrix_probe_$(echo "${label}" | tr -cd '0-9')" \
     bash "${SCRIPT_DIR}/verify_against_server.sh"; then
    PASSED="${PASSED} ${label}"
  else
    FAILED="${FAILED} ${label}"
  fi
done

echo
echo "matched:  ${PASSED:-none}"
echo "skipped:  ${SKIPPED:-none}"
echo "MISMATCH: ${FAILED:-none}"

if [[ -n "${FAILED}" ]]; then
  echo >&2
  echo "The matrix in references/ddl-algorithm-matrix.md disagrees with a real server." >&2
  echo "Re-read the manual for the reported rows before editing the matrix — a probe can" >&2
  echo "also fail because its setup table does not match the row's preconditions." >&2
  exit 1
fi

if [[ -n "${SKIPPED}" ]]; then
  echo
  echo "NOTE: the versions above were not reachable and were NOT verified."
  echo "      Start them with:"
  echo "        docker compose -f ${SCRIPT_DIR}/verify-matrix.docker-compose.yml up -d --wait"
  if [[ "${REQUIRE_ALL}" == "1" ]]; then
    echo "ERROR: --require-all was passed and some instances were unreachable." >&2
    exit 3
  fi
fi

if [[ -z "${PASSED}" ]]; then
  echo
  echo "SKIPPED: no instance was reachable, so nothing was verified."
  echo "         This is not a pass. See COVERAGE.md section 5."
fi
