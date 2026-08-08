#!/usr/bin/env bash
# Run all regression checks for the mongo-migration skill.
#
# Note: no `set -e`. A non-zero exit from one stage must not abort the run before the
# later stages report -- a partial run that looks green is worse than a red one.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEST_DIR="${SCRIPT_DIR}/tests"

status=0
note() { printf '\n=== %s ===\n' "$1"; }

note "1/8 Contract tests (SKILL.md structure + reference files)"
python3 -m pytest "${TEST_DIR}/test_skill_contract.py" -q || status=1

note "2/8 Golden scenario tests (fixture shape)"
python3 -m pytest "${TEST_DIR}/test_golden_scenarios.py" -q || status=1

note "3/8 Checker behaviour + fixtures driven through the real checker"
python3 -m pytest "${TEST_DIR}/test_lint_migration.py" -q || status=1

note "4/8 Documentation fact-drift guards"
python3 -m pytest "${TEST_DIR}/test_mongo_facts_drift.py" -q || status=1

note "5/8 Checker self-check on the documented-correct form"
# The loop this skill recommends must pass its own checker, and the loop it used to ship
# must still be reported. A checker silent on a known-bad input is worse than useless.
tmp="$(mktemp -d "${TMPDIR:-/tmp}/mongomig.XXXXXX")" || {
  echo "  stage 5 failed: cannot create a writable temp dir" >&2; status=1; tmp=""; }
if [ -n "${tmp}" ]; then
  cat > "${tmp}/good.js" <<'JS'
// No $gt cursor: comparison operators type-bracket, so a keyset over _id strands every
// _id whose BSON type differs from the cursor's. The predicate selects each batch.
while (true) {
  const batch = db.orders.find({new_field: {$exists: false}}, {_id: 1})
                  .sort({_id: 1}).limit(5000).toArray();
  if (batch.length === 0) break;
  const ids = batch.map(d => d._id);
  db.orders.updateMany({_id: {$in: ids}, new_field: {$exists: false}},
                       {$set: {new_field: "v"}}, {writeConcern: {w: "majority"}});
  sleep(100);
}
JS
  cat > "${tmp}/known_bad.js" <<'JS'
let lastId = ObjectId("000000000000000000000000");
db.orders.updateMany(
  {_id: {$gt: lastId, $lte: ObjectId(lastId.valueOf().substring(0,24))}},
  {$set: {new_field: "v"}}, {writeConcern: {w: "majority"}});
JS
  # Exit status is the machine contract; the clean text is human-facing.
  if out="$(python3 "${SCRIPT_DIR}/lint_migration.py" "${tmp}/good.js" 2>&1)"; then
    echo "  good.js: clean"
  else
    echo "  good.js: UNEXPECTED FINDINGS" >&2; echo "${out}" >&2; status=1
  fi
  if out="$(python3 "${SCRIPT_DIR}/lint_migration.py" "${tmp}/known_bad.js" 2>&1)"; then
    echo "  known_bad.js: checker FAILED to flag the script this skill used to ship" >&2
    echo "${out}" >&2; status=1
  else
    case "${out}" in
      *MG002*MG003*|*MG003*MG002*) echo "  known_bad.js: correctly flagged MG002 + MG003" ;;
      *) echo "  known_bad.js: flagged, but not with both defects" >&2
         echo "${out}" >&2; status=1 ;;
    esac
  fi
  rm -rf "${tmp}"
fi

note "6/8 Go example compile gate"
# The JavaScript blocks are parsed by a real mongosh in stage 7. The Go blocks had no
# equivalent, which is how a `wcColl` handle that could not compile shipped -- and then
# the gate that catches it sat unwired for a release, so the regression stayed green
# while claiming the coverage. Absent or broken toolchain is INCOMPLETE, not a pass.
go_ran=0
if command -v go >/dev/null 2>&1 && command -v gofmt >/dev/null 2>&1; then
  if go version >/dev/null 2>&1; then
    python3 -m pytest "${TEST_DIR}/test_go_examples_compile.py" -q || status=1
    go_ran=1
  else
    echo "  NOT RUN — the Go toolchain is present but not working:" >&2
    go version 2>&1 | sed 's/^/    /' >&2
    echo "  (a GOROOT pointing at a different release does this)" >&2
  fi
else
  echo "  NOT RUN — no Go toolchain; the shipped Go blocks were not compiled." >&2
fi

note "7/8 Live MongoDB matrix (7.0 + 8.0)"
# The only stage that asserts against MongoDB rather than against our own description of
# it. Reported explicitly as NOT RUN when no server is reachable: every other stage can
# be green while a documented fact is simply false, which is how a backfill script that
# cannot execute survived 97 passing tests.
live_ran=0
if python3 "${TEST_DIR}/mongo_server.py" >/dev/null 2>&1; then
  echo "  servers found:"
  python3 "${TEST_DIR}/mongo_server.py" | sed 's/^/    /'
  n_found="$(python3 "${TEST_DIR}/mongo_server.py" \
             | grep -cv 'UNREACHABLE\|MISLABELLED' || true)"
  if python3 "${TEST_DIR}/mongo_server.py" | grep -q MISLABELLED; then
    echo "  a container reports a different major than its name claims." >&2; status=1
  fi
  python3 -m pytest "${TEST_DIR}/test_mongo_server_matrix.py" -q || status=1
  if [ "${n_found}" -eq 2 ]; then
    live_ran=1
  else
    echo "  PARTIAL: ${n_found} of 2 majors reachable. The 7.0+8.0 claim is unverified." >&2
  fi
else
  echo "  NOT RUN — no live MongoDB reachable." >&2
  echo "  The offline stages above cannot verify any MongoDB behaviour claim." >&2
  echo "  Run: bash scripts/mongo_server_harness.sh" >&2
fi

note "8/8 Mutation sweep (anchors)"
# Anchors only here -- the full sweep re-runs the suite once per mutation and belongs in
# a deliberate `python3 scripts/mutation_sweep.py` run. But a STALE anchor makes a
# mutation a silent no-op, which turns the whole sweep into theatre, so the cheap check
# runs every time. It was missing entirely: the 22/22 result had to be produced by hand.
python3 "${SCRIPT_DIR}/mutation_sweep.py" --verify || status=1

echo ""
if [ "${status}" -ne 0 ]; then
  echo "mongo-migration skill regression checks FAILED." >&2
  exit 1
fi

# "Everything I ran passed" is not "everything passed". The offline stages cannot check a
# single claim about MongoDB's actual behaviour, so calling the run green without the
# live matrix would report exactly the confidence this skill was wrong about twice.
if [ "${live_ran}" -eq 0 ] || [ "${go_ran}" -eq 0 ]; then
  echo "mongo-migration skill regression checks INCOMPLETE (exit 3)." >&2
  [ "${go_ran}" -eq 0 ] && \
    echo "  Stage 6 did not compile the Go examples (no working toolchain)." >&2
  [ "${live_ran}" -eq 0 ] && \
    echo "  Stage 7 did not verify MongoDB on both majors, so no behaviour claim in" >&2 && \
    echo "  this skill was checked against a server this run." >&2
  echo "  A skipped gate is not a passed gate." >&2
  exit 3
fi

echo "mongo-migration skill regression checks passed (offline + live 7.0/8.0)."
exit 0
