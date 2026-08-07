#!/usr/bin/env bash
# Bring up PostgreSQL 14-18 and run the live verification matrix against all of them.
#
# Why this exists: every other suite in this skill asserts against our own description
# of PostgreSQL. Only this one asserts against PostgreSQL. Two documented facts that
# survived a fully green offline suite -- `max(uuid)` (does not exist) and the
# partitioned-table NOT VALID FK rule (version-gated, not absolute) -- were both found
# the first time a server was actually asked.
#
# Usage:
#   bash scripts/pg_server_harness.sh              # start, test, stop
#   bash scripts/pg_server_harness.sh --keep       # leave containers up afterwards
#   bash scripts/pg_server_harness.sh --stop       # tear down and exit
#   bash scripts/pg_server_harness.sh 16 18        # only these majors
#
# Exit codes:
#   0  matrix ran and passed
#   1  matrix ran and failed
#   2  no server could be started -- the matrix did NOT run at all
#   3  INCOMPLETE: it ran, but not on every major it claims to cover. Coverage of
#      "14-18" is a claim about all five; four out of five is a different claim, and
#      a green exit here would let it pass as the stronger one.
#
# 2 and 3 are distinct from 0 on purpose: a skip is not a pass, and a partial run is
# not a full one.
#
# No `set -e`: a failure in one stage must not abort before the later stages report.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

ALL_MAJORS="14 15 16 17 18"
# Overridable so a private registry -- or a deliberately bad tag, when testing the
# failure path -- can be substituted without editing this script.
IMAGE_TMPL="${PGMIG_IMAGE_TMPL:-postgres:%s-alpine}"
KEEP=0
STOP_ONLY=0
MAJORS=""
EXPLICIT_SUBSET=0

for arg in "$@"; do
  case "${arg}" in
    --keep) KEEP=1 ;;
    --stop) STOP_ONLY=1 ;;
    1[4-8]) MAJORS="${MAJORS} ${arg}"; EXPLICIT_SUBSET=1 ;;
    -h|--help) sed -n '2,26p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "unknown argument: ${arg}" >&2; exit 2 ;;
  esac
done
# bash 3.2 (the macOS system bash) treats "${arr[@]}" on an empty array as unbound
# under `set -u`, so majors are carried as a plain string rather than an array.
[ -z "${MAJORS}" ] && MAJORS="${ALL_MAJORS}"
# Naming every supported major by hand is the same claim as naming none, so it must
# not be downgraded to "partial".
[ "$(echo ${MAJORS})" = "${ALL_MAJORS}" ] && EXPLICIT_SUBSET=0

note() { printf '\n=== %s ===\n' "$1"; }

if ! command -v docker >/dev/null 2>&1; then
  echo "docker not found." >&2
  echo "Point PG_MIGRATION_TEST_PSQL_<major> or PG_MIGRATION_TEST_DSN_<major> at" >&2
  echo "an existing server instead, then run pytest on the matrix directly." >&2
  exit 2
fi

if ! docker info >/dev/null 2>&1; then
  echo "the docker daemon is not reachable; cannot start any server." >&2
  exit 2
fi

teardown() {
  for v in ${MAJORS}; do
    docker rm -f "pgmig${v}" >/dev/null 2>&1
  done
}

if [ "${STOP_ONLY}" -eq 1 ]; then
  teardown
  echo "containers removed."
  exit 0
fi

note "Starting PostgreSQL ${MAJORS}"
started=""
for v in ${MAJORS}; do
  # Remove any pre-existing container FIRST, before anything can fail and skip ahead.
  # Doing it after the pull meant a failed pull left an earlier run's container alive,
  # and discovery then reported that major as verified while this run never started or
  # checked it -- the exact "coverage that was not established" this gate exists to stop.
  docker rm -f "pgmig${v}" >/dev/null 2>&1
  img="$(printf "${IMAGE_TMPL}" "${v}")"
  if ! docker image inspect "${img}" >/dev/null 2>&1; then
    echo "  pulling ${img}"
    docker pull "${img}" >/dev/null 2>&1 || {
      echo "  cannot pull ${img}; skipping PG${v}" >&2
      continue
    }
  fi
  if docker run -d --name "pgmig${v}" \
       -e POSTGRES_PASSWORD=pgmig -e POSTGRES_DB=pgmig \
       "${img}" >/dev/null 2>&1; then
    started="${started} ${v}"
  else
    echo "  failed to start PG${v}" >&2
  fi
done

if [ -z "${started}" ]; then
  echo "no server started; the matrix did not run." >&2
  exit 2
fi

note "Waiting for readiness"
ready=""
for v in ${started}; do
  # Poll rather than sleep: `timeout(1)` is not present on macOS, and a fixed sleep
  # is either too short on a cold start or wasted time on a warm one.
  i=0
  while [ "${i}" -lt 60 ]; do
    if docker exec "pgmig${v}" pg_isready -U postgres -d pgmig >/dev/null 2>&1; then
      ready="${ready} ${v}"
      echo "  PG${v} ready: $(docker exec "pgmig${v}" psql -U postgres -d pgmig -tAc \
            'SHOW server_version' 2>/dev/null)"
      break
    fi
    i=$((i + 1))
    sleep 1
  done
  case " ${ready} " in
    *" ${v} "*) ;;
    *) echo "  PG${v} never became ready" >&2 ;;
  esac
done

if [ -z "${ready}" ]; then
  echo "no server became ready; the matrix did not run." >&2
  [ "${KEEP}" -eq 0 ] && teardown
  exit 2
fi

# Completeness gate. Skipping a version that failed to start and still exiting 0 would
# report "verified on 14-18" on the strength of however many happened to come up.
missing=""
for v in ${MAJORS}; do
  case " ${ready} " in
    *" ${v} "*) ;;
    *) missing="${missing} ${v}" ;;
  esac
done
n_ready=$(echo ${ready} | wc -w | tr -d " ")

# Report what the matrix will actually use, not what this script started: discovery
# also picks up servers from PG_MIGRATION_TEST_* and containers left by an earlier
# --keep run. Claiming a narrower set than was tested would misreport the evidence.
note "Servers the matrix resolved"
discovered="$(python3 "${SKILL_DIR}/scripts/tests/pg_server.py")"
echo "${discovered}"
if echo "${discovered}" | grep -q MISLABELLED; then
  echo "a container reports a different major than its name claims; refusing to run." >&2
  [ "${KEEP}" -eq 0 ] && teardown
  exit 2
fi

note "Running the live matrix"
python3 -m pytest "${SKILL_DIR}/scripts/tests/test_pg_server_matrix.py" -q
status=$?

# A run in which every test was skipped exits 0 from pytest but verifies nothing.
# Require a positive marker that tests actually executed.
collected="$(python3 -m pytest "${SKILL_DIR}/scripts/tests/test_pg_server_matrix.py" \
             -q --collect-only 2>/dev/null | grep -c '::')"
if [ "${collected}" -lt 50 ]; then
  echo "only ${collected} matrix tests collected -- discovery is broken, so a green" >&2
  echo "result would prove nothing." >&2
  status=1
fi

[ "${KEEP}" -eq 0 ] && teardown
[ "${KEEP}" -eq 1 ] && echo "containers left running (--keep); remove with --stop"

echo ""
covered="$(echo "${discovered}" | cut -f1 | tr '\n' ' ')"

if [ "${status}" -ne 0 ]; then
  echo "live matrix FAILED" >&2
  exit 1
fi

if [ -n "${missing}" ]; then
  echo "INCOMPLETE VERIFICATION: requested${MAJORS}, but${missing} never became ready." >&2
  echo "  The matrix passed on:${covered}" >&2
  echo "  That is NOT coverage of 14-18. Re-run once every major starts." >&2
  exit 3
fi

if [ "${EXPLICIT_SUBSET}" -eq 1 ]; then
  echo "PARTIAL COVERAGE (${n_ready} of 5 majors, explicitly requested): ${covered}"
  echo "  Every requested major passed. Run without arguments for the full 14-18 claim."
  exit 0
fi

echo "live matrix passed on all ${n_ready} supported majors: ${covered}"
exit 0
