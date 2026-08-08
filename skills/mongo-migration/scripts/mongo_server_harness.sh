#!/usr/bin/env bash
# Bring up MongoDB 7.0 and 8.0 as REAL 3-member replica sets and run the live
# verification matrix against both.
#
# Three members, not one. A single-node set still answers rs.* helpers and satisfies
# w:"majority", which is enough for the ObjectId / TTL / validator / transaction facts --
# but it has no secondary, so "a secondary rejects createIndex" skipped and "the default
# build replicates" only ever re-read the primary's own index list. Those are exactly the
# replica-set claims this skill makes, so the harness has to provide a real set.
#
# Why this exists: every other suite in this skill asserts against our own description of
# MongoDB. Only this one asserts against MongoDB. Two defects survived 97 green tests --
# a backfill loop that throws TypeError on its first line, and a rolling-index procedure
# the server rejects with NotWritablePrimary. Both were found the first time a server was
# actually asked; one of them was recorded by a fixture as "no violations".
#
# Usage:
#   bash scripts/mongo_server_harness.sh            # start, test, stop
#   bash scripts/mongo_server_harness.sh --keep     # leave containers up afterwards
#   bash scripts/mongo_server_harness.sh --stop     # tear down and exit
#   bash scripts/mongo_server_harness.sh 8          # only this major
#
# Exit codes:
#   0  matrix ran and passed on every requested major
#   1  matrix ran and failed
#   2  no server could be started -- the matrix did NOT run at all
#   3  INCOMPLETE: it ran, but not on every major it claims to cover
#
# 2 and 3 are distinct from 0 on purpose: a skip is not a pass, and a partial run is not
# a full one.
#
# No `set -e`: a failure in one stage must not abort before the later stages report.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

ALL_MAJORS="7 8"
IMAGE_TMPL="${MONGOMIG_IMAGE_TMPL:-mongo:%s.0}"
KEEP=0
STOP_ONLY=0
MAJORS=""
EXPLICIT_SUBSET=0

for arg in "$@"; do
  case "${arg}" in
    --keep) KEEP=1 ;;
    --stop) STOP_ONLY=1 ;;
    [78]) MAJORS="${MAJORS} ${arg}"; EXPLICIT_SUBSET=1 ;;
    -h|--help) sed -n '2,24p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "unknown argument: ${arg}" >&2; exit 2 ;;
  esac
done
# bash 3.2 (the macOS system bash) treats "${arr[@]}" on an empty array as unbound under
# `set -u`, so majors are carried as a plain string rather than an array.
[ -z "${MAJORS}" ] && MAJORS="${ALL_MAJORS}"
[ "$(echo ${MAJORS})" = "${ALL_MAJORS}" ] && EXPLICIT_SUBSET=0

note() { printf '\n=== %s ===\n' "$1"; }

if ! command -v docker >/dev/null 2>&1; then
  echo "docker not found." >&2
  echo "Point MONGO_MIGRATION_TEST_MONGOSH_<major> or _URI_<major> at an existing" >&2
  echo "server instead, then run pytest on the matrix directly." >&2
  exit 2
fi
if ! docker info >/dev/null 2>&1; then
  echo "the docker daemon is not reachable; cannot start any server." >&2
  exit 2
fi

NODES="1 2 3"
teardown() {
  for v in ${MAJORS}; do
    for i in ${NODES}; do docker rm -f "mongomig${v}n${i}" >/dev/null 2>&1; done
    docker rm -f "mongomig${v}" >/dev/null 2>&1      # pre-3-node layout
  done
  docker network rm mongomignet >/dev/null 2>&1
}

if [ "${STOP_ONLY}" -eq 1 ]; then
  teardown; echo "containers removed."; exit 0
fi

note "Starting MongoDB ${MAJORS} (3 members each)"
docker network create mongomignet >/dev/null 2>&1
started=""
for v in ${MAJORS}; do
  img="$(printf "${IMAGE_TMPL}" "${v}")"
  if ! docker image inspect "${img}" >/dev/null 2>&1; then
    echo "  pulling ${img}"
    docker pull "${img}" >/dev/null 2>&1 || {
      echo "  cannot pull ${img}; skipping MongoDB ${v}" >&2; continue; }
  fi
  # Remove any pre-existing container FIRST, before anything can fail and skip ahead: a
  # survivor from an earlier run would be discovered and reported as verified by a run
  # that never started or checked it.
  for i in ${NODES}; do docker rm -f "mongomig${v}n${i}" >/dev/null 2>&1; done

  ok=1
  for i in ${NODES}; do
    docker run -d --name "mongomig${v}n${i}" --network mongomignet "${img}" \
      --replSet "rsmig${v}" --bind_ip_all >/dev/null 2>&1 || ok=0
  done
  if [ "${ok}" -eq 1 ]; then
    started="${started} ${v}"
  else
    echo "  failed to start all 3 members for MongoDB ${v}" >&2
    for i in ${NODES}; do docker rm -f "mongomig${v}n${i}" >/dev/null 2>&1; done
  fi
done

if [ -z "${started}" ]; then
  echo "no server started; the matrix did not run." >&2; exit 2
fi

note "Waiting for readiness and initiating the replica sets"
ready=""
for v in ${started}; do
  # Poll rather than sleep: `timeout(1)` is absent on macOS, and a fixed sleep is either
  # too short on a cold start or wasted time on a warm one.
  i=0
  while [ "${i}" -lt 90 ]; do
    docker exec "mongomig${v}n1" mongosh --quiet --eval 'db.runCommand({ping:1}).ok' \
      >/dev/null 2>&1 && break
    i=$((i + 1)); sleep 1
  done

  docker exec "mongomig${v}n1" mongosh --quiet --eval "
    try { rs.initiate({_id:'rsmig${v}', members:[
      {_id:0, host:'mongomig${v}n1:27017'},
      {_id:1, host:'mongomig${v}n2:27017'},
      {_id:2, host:'mongomig${v}n3:27017'}]}) } catch (e) {}" >/dev/null 2>&1

  # Require a PRIMARY *and* at least one SECONDARY. A single-node set would satisfy the
  # first alone, and that is the state this harness exists to stop reporting as verified.
  j=0
  while [ "${j}" -lt 90 ]; do
    if docker exec "mongomig${v}n1" mongosh --quiet --eval '
          const m = rs.status().members || [];
          quit((m.some(x => x.stateStr === "PRIMARY") &&
                m.filter(x => x.stateStr === "SECONDARY").length >= 1) ? 0 : 1)' \
         >/dev/null 2>&1; then
      ready="${ready} ${v}"
      echo "  MongoDB ${v} ready: $(docker exec "mongomig${v}n1" mongosh --quiet \
            --eval 'print(db.version() + " [" + rs.status().members
                      .map(m => m.stateStr).join(",") + "]")' 2>/dev/null | tail -1)"
      break
    fi
    j=$((j + 1)); sleep 1
  done
  case " ${ready} " in
    *" ${v} "*) ;;
    *) echo "  MongoDB ${v} never reached PRIMARY + SECONDARY" >&2 ;;
  esac
done

if [ -z "${ready}" ]; then
  echo "no server became ready; the matrix did not run." >&2
  [ "${KEEP}" -eq 0 ] && teardown
  exit 2
fi

# Completeness gate. Skipping a version that failed to start and still exiting 0 would
# report "verified on 7.0 and 8.0" on the strength of however many happened to come up.
missing=""
for v in ${MAJORS}; do
  case " ${ready} " in *" ${v} "*) ;; *) missing="${missing} ${v}" ;; esac
done
n_ready=$(echo ${ready} | wc -w | tr -d " ")

note "Servers the matrix resolved"
discovered="$(python3 "${SKILL_DIR}/scripts/tests/mongo_server.py")"
echo "${discovered}"
if echo "${discovered}" | grep -q MISLABELLED; then
  echo "a container reports a different major than its name claims; refusing to run." >&2
  [ "${KEEP}" -eq 0 ] && teardown
  exit 2
fi

note "Running the live matrix"
python3 -m pytest "${SKILL_DIR}/scripts/tests/test_mongo_server_matrix.py" -q
status=$?

# A run in which every test was skipped exits 0 from pytest but verifies nothing.
collected="$(python3 -m pytest "${SKILL_DIR}/scripts/tests/test_mongo_server_matrix.py" \
             -q --collect-only 2>/dev/null | grep -c '::')"
if [ "${collected}" -lt 30 ]; then
  echo "only ${collected} matrix tests collected -- discovery is broken, so a green" >&2
  echo "result would prove nothing." >&2
  status=1
fi

[ "${KEEP}" -eq 0 ] && teardown
[ "${KEEP}" -eq 1 ] && echo "containers left running (--keep); remove with --stop"

echo ""
covered="$(echo "${discovered}" | cut -f1 | tr '\n' ' ')"

if [ "${status}" -ne 0 ]; then
  echo "live matrix FAILED" >&2; exit 1
fi
if [ -n "${missing}" ]; then
  echo "INCOMPLETE VERIFICATION: requested${MAJORS}, but${missing} never became ready." >&2
  echo "  The matrix passed on:${covered}" >&2
  echo "  That is NOT coverage of 7.0 and 8.0. Re-run once every major starts." >&2
  exit 3
fi
if [ "${EXPLICIT_SUBSET}" -eq 1 ]; then
  echo "PARTIAL COVERAGE (${n_ready} of 2 majors, explicitly requested): ${covered}"
  exit 0
fi
echo "live matrix passed on all ${n_ready} supported majors: ${covered}"
exit 0
