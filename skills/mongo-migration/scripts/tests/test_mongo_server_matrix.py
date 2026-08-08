"""Live-MongoDB verification of the claims this skill makes.

Every other suite asserts against our own description of MongoDB. This one asserts
against MongoDB. It skips when no server is reachable -- see mongo_server.py for the
discovery order and why a skip is not treated as a pass.

Bring servers up with::

    bash scripts/mongo_server_harness.sh          # start 7.0 + 8.0 and run this matrix
    bash scripts/mongo_server_harness.sh --keep   # leave the containers running

Each test names the documented claim it checks, so a failure points at the sentence in
the skill that has gone stale rather than only at the JavaScript that broke.
"""

from __future__ import annotations

import importlib.util
import pathlib
import re
import sys

import pytest

TESTS_DIR = pathlib.Path(__file__).resolve().parent
SCRIPTS_DIR = TESTS_DIR.parent
SKILL_DIR = SCRIPTS_DIR.parent


def _load(name: str, path: pathlib.Path):
    """Load by path: this repo runs pytest with --import-mode=importlib, which breaks
    bare sibling imports. Register in sys.modules before exec_module so dataclasses can
    resolve the module during class creation."""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


MS = _load("mongo_migration_server", TESTS_DIR / "mongo_server.py")
SERVERS = MS.discover_all()

pytestmark = pytest.mark.skipif(
    not SERVERS,
    reason="no live MongoDB reachable; run scripts/mongo_server_harness.sh",
)

MAJORS = sorted(SERVERS)


@pytest.fixture(params=MAJORS, ids=[f"mongo{m}" for m in MAJORS])
def srv(request):
    return SERVERS[request.param]


# ---------------------------------------------------------------------------
# Harness integrity -- these must fail loudly, never skip quietly.
# ---------------------------------------------------------------------------

class TestHarnessIntegrity:
    def test_container_version_matches_its_label(self, srv):
        actual = MS.server_major(srv)
        assert actual == srv.major, (
            f"{srv.origin} is labelled MongoDB {srv.major} but reports {actual}"
        )

    def test_server_actually_evaluates_javascript(self, srv):
        """Guards against a 'connection' that returns empty output for everything,
        which would make every assertion below vacuously true."""
        assert srv.value("40 + 2") == 42

    def test_writes_go_to_whichever_member_is_primary(self, srv):
        """The harness must not assume which member holds the primary.

        Pinning n1 made this matrix pass on one run and fail 13 tests with
        NotWritablePrimary on the next, after an ordinary re-election. The connection is
        a replica-set seed list, so a write must succeed regardless of who is primary --
        and that is checked here rather than left to luck about election timing."""
        ok = srv.value(
            "(function(){ db.primary_probe.drop();"
            " db.primary_probe.insertOne({_id: 1}, {writeConcern: {w: 'majority'}});"
            " return db.primary_probe.countDocuments({_id: 1}); })()")
        assert ok == 1

    def test_the_secondary_handle_is_resolved_not_cached(self, srv):
        """`secondary()` re-resolves on every call. A handle cached at discovery time
        would aim at a member that an election has since promoted."""
        if not srv.members:
            pytest.skip("single-node deployment: no members to resolve between")
        sec = srv.secondary()
        assert sec is not None, "no member is currently a secondary"
        assert sec.value("db.hello().secondary") is True
        prim = srv.primary_name()
        assert prim is not None, "no member reports itself primary"
        assert prim not in sec.origin, (
            f"the 'secondary' handle resolved to {prim}, which is the primary"
        )

    def test_supported_majors_match_the_skill(self, srv):
        text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        assert "7.0 and 8.0" in text, (
            "SKILL.md must state the supported majors this matrix runs against"
        )


# ---------------------------------------------------------------------------
# P0 #1 -- the backfill script. Both defects reproduced, then the fix proven.
# ---------------------------------------------------------------------------

class TestBackfillCursor:
    def test_objectid_valueof_is_not_a_string(self, srv):
        """The shipped script called `lastId.valueOf().substring(0,24)`. valueOf()
        returns an object, so that threw TypeError on the first iteration -- the script
        could not run at all, let alone migrate anything."""
        assert srv.value("typeof db.oid_probe.find().toArray()") is not None  # warm-up
        kind = srv.value(
            "(function(){ db.oid_probe.drop(); db.oid_probe.insertOne({a:1});"
            " return typeof db.oid_probe.findOne()._id.valueOf(); })()")
        assert kind != "string", (
            "ObjectId.valueOf() now returns a string; the TypeError this skill "
            "documents would no longer occur and §1's explanation needs revisiting"
        )
        has_substring = srv.value(
            "(function(){ return typeof db.oid_probe.findOne()._id.valueOf().substring;"
            " })()")
        assert has_substring == "undefined", has_substring

    def test_reconstructing_an_objectid_from_its_hex_yields_the_same_id(self, srv):
        """The second defect, one layer down: even given a hex string, ObjectId(hex)
        rebuilds the SAME id, so `{$gt: id, $lte: id}` selects nothing."""
        same = srv.value(
            "(function(){ db.oid_probe.drop(); db.oid_probe.insertOne({a:1});"
            " const id = db.oid_probe.findOne()._id;"
            " return ObjectId(id.toHexString()).equals(id); })()")
        assert same is True

    def test_the_superseded_range_really_selects_nothing(self, srv):
        """Direct proof of the failure mode, independent of the TypeError."""
        matched = srv.value(
            "(function(){ db.rangeprobe.drop();"
            " for (let i=0;i<10;i++) db.rangeprobe.insertOne({i:i});"
            " const id = db.rangeprobe.find().sort({_id:1}).limit(1).next()._id;"
            " return db.rangeprobe.countDocuments({_id:{$gt:id,$lte:ObjectId(id.toHexString())}});"
            " })()")
        assert matched == 0, (
            "the $gt/$lte-same-id range now matches documents; the documented "
            "explanation of why the old script migrated nothing is no longer true"
        )

    def test_documented_loop_migrates_every_document(self, srv):
        """The replacement, run against the shapes §1 claims it handles: sparse
        ObjectIds, integer _ids in the same collection, and documents already carrying
        the target field at the TOP of the key range (what breaks a max()-based resume).
        """
        result = srv.value(BACKFILL_PROBE)
        assert result["distinctIdTypes"] >= 3, (
            "the probe no longer spans several _id BSON types, so it cannot detect the "
            "type-bracketing failure it exists for", result)
        assert result["missing"] == 0, f"{result['missing']} documents were skipped"
        assert result["updated"] == result["needed"], result
        assert result["preMigratedUntouched"] == 2, (
            "the loop rewrote documents that were already migrated", result)

    def test_the_gt_keyset_optimisation_strands_a_whole_bson_type(self, srv):
        """§1 restricts the `$gt` cursor to a single-BSON-type `_id`. That restriction
        is only worth stating if the unrestricted form really fails -- and it does:
        comparison operators type-bracket, so `$gt: <int>` never reaches ObjectIds that
        sort after every integer.

        The earlier version of this suite ran the `$gt` loop on 20 integers with batch
        size 25, so the first batch crossed into the ObjectIds before the boundary
        mattered and the bug passed unnoticed."""
        r = srv.value(TYPE_BRACKET_PROBE)
        assert r["gtIntReachesObjectIds"] == 0, (
            "$gt on an integer now matches ObjectIds; type bracketing has changed and "
            "§1's restriction needs revisiting", r)
        assert r["missed"] > 0, (
            "the $gt keyset loop migrated everything across a type boundary; if that is "
            "now true, the cursorless form is no longer required", r)
        assert r["missed"] == r["total"] - r["updated"], r

    def test_loop_is_resumable_without_stored_state(self, srv):
        """§1 claims a restart needs no cursor because the predicate is the resume
        point. Interrupt the loop, restart it from scratch, and nothing may be missed."""
        result = srv.value(RESUME_PROBE)
        assert result["missingAfterResume"] == 0, result
        assert result["firstPass"] > 0 and result["secondPass"] > 0, (
            "the probe did not actually interrupt and resume", result)


BACKFILL_PROBE = """
(function () {
  db.orders_probe.drop();
  const docs = [];
  for (let i = 0; i < 200; i++) docs.push({_id: new ObjectId(), seq: i});
  db.orders_probe.insertMany(docs);
  db.orders_probe.insertOne({_id: new ObjectId(), new_field: "already"});
  db.orders_probe.insertOne({_id: new ObjectId(), new_field: "already"});
  // Enough integers to fill whole batches on their own -- this is the alignment the
  // earlier probe got wrong. With 20 ints and batchSize 25 the first batch swallowed
  // them plus 5 ObjectIds, so the cursor was already an ObjectId and the type boundary
  // was never crossed. 60 ints and batchSize 25 makes the boundary unavoidable.
  for (let i = 0; i < 60; i++) db.orders_probe.insertOne({_id: i, seq: 1000 + i});
  db.orders_probe.insertOne({_id: "str-key", seq: 9999});

  const needed = db.orders_probe.countDocuments({new_field: {$exists: false}});
  const batchSize = 25;
  let updated = 0, rounds = 0;

  while (true) {
    if (++rounds > 200) break;
    // No $gt anywhere: the predicate is the cursor, so BSON type bracketing cannot
    // strand a whole type class.
    const batch = db.orders_probe.find({new_field: {$exists: false}}, {_id: 1})
                    .sort({_id: 1}).limit(batchSize).toArray();
    if (batch.length === 0) break;
    const ids = batch.map(d => d._id);
    updated += db.orders_probe.updateMany(
      {_id: {$in: ids}, new_field: {$exists: false}},
      {$set: {new_field: "default_value"}},
      {writeConcern: {w: "majority"}}).modifiedCount;
  }
  return {
    needed: needed,
    updated: updated,
    missing: db.orders_probe.countDocuments({new_field: {$exists: false}}),
    preMigratedUntouched: db.orders_probe.countDocuments({new_field: "already"}),
    distinctIdTypes: db.orders_probe.aggregate(
      [{$group: {_id: {$type: "$_id"}}}]).toArray().length,
    rounds: rounds
  };
})()
"""

TYPE_BRACKET_PROBE = """
(function () {
  db.tb_probe.drop();
  for (let i = 0; i < 30; i++) db.tb_probe.insertOne({_id: i});
  for (let i = 0; i < 30; i++) db.tb_probe.insertOne({_id: new ObjectId()});

  let lastId = null, updated = 0, rounds = 0;
  while (true) {
    if (++rounds > 100) break;
    const q = {done: {$exists: false}};
    if (lastId !== null) q._id = {$gt: lastId};        // the keyset optimisation
    const b = db.tb_probe.find(q, {_id: 1}).sort({_id: 1}).limit(25).toArray();
    if (b.length === 0) break;
    const ids = b.map(d => d._id);
    updated += db.tb_probe.updateMany({_id: {$in: ids}, done: {$exists: false}},
                                      {$set: {done: 1}}).modifiedCount;
    lastId = ids[ids.length - 1];
  }
  return {
    total: db.tb_probe.countDocuments(),
    updated: updated,
    missed: db.tb_probe.countDocuments({done: {$exists: false}}),
    gtIntReachesObjectIds: db.tb_probe.countDocuments({_id: {$gt: 29}})
  };
})()
"""

RESUME_PROBE = """
(function () {
  db.resume_probe.drop();
  for (let i = 0; i < 120; i++) db.resume_probe.insertOne({_id: new ObjectId(), seq: i});
  // A document at the TOP of the range that is already done: a max()-based resume
  // point would jump past everything below it.
  db.resume_probe.insertOne({_id: new ObjectId(), new_field: "already"});

  function run(maxRounds) {
    let updated = 0, rounds = 0;
    while (rounds < maxRounds) {
      rounds++;
      const batch = db.resume_probe.find({new_field: {$exists: false}}, {_id: 1})
                      .sort({_id: 1}).limit(20).toArray();
      if (batch.length === 0) break;
      const ids = batch.map(d => d._id);
      updated += db.resume_probe.updateMany(
        {_id: {$in: ids}, new_field: {$exists: false}},
        {$set: {new_field: "default_value"}}).modifiedCount;
    }
    return updated;
  }

  const firstPass = run(2);              // interrupted part-way
  const secondPass = run(100);           // restarted from lastId = null
  return {
    firstPass: firstPass,
    secondPass: secondPass,
    missingAfterResume: db.resume_probe.countDocuments({new_field: {$exists: false}})
  };
})()
"""


# ---------------------------------------------------------------------------
# P0 #2 -- index builds on a replica set.
# ---------------------------------------------------------------------------

class TestIndexBuildOnReplicaSet:
    """These are the claims a single-node set cannot check.

    The earlier harness started one container per version, so `test_createindex_on_a
    _secondary_is_rejected` SKIPPED (that member was the primary) and "the default build
    replicates" only re-read the primary's own index list. Both now require a real
    secondary, and FAIL rather than skip when one is missing -- a skip here is the exact
    silence that let the broken rolling procedure ship.
    """

    @staticmethod
    def _secondary(srv):
        sec = srv.secondary()
        assert sec is not None, (
            f"MongoDB {srv.major} has no reachable secondary. The replica-set claims in "
            "this skill cannot be verified against a single-node set -- start a real "
            "3-member set with scripts/mongo_server_harness.sh"
        )
        return sec

    def test_the_harness_provides_a_real_secondary(self, srv):
        sec = self._secondary(srv)
        assert sec.value("db.hello().secondary") is True, (
            "the 'secondary' handle reached a member that is not a secondary; a "
            "directConnection is required or the driver follows the set to the primary"
        )

    def test_createindex_on_a_secondary_is_rejected(self, srv):
        """Step (b) of the superseded rolling procedure, aimed at a genuine secondary."""
        sec = self._secondary(srv)
        err = sec.value(
            "(function(){ try { db.rs_probe.createIndex({a:1}); return 'ACCEPTED'; }"
            " catch(e) { return e.codeName || e.name; } })()")
        assert err == "NotWritablePrimary", err

    def test_default_build_actually_reaches_the_secondaries(self, srv):
        """The replicated default, checked where it matters: on another member.

        The previous version of this test asked the primary whether the primary had the
        index, which is true by construction and proves nothing about replication.
        """
        name = "idx_repl_probe"
        srv.value(
            "(function(){ db.repl_idx_probe.drop();"
            " db.repl_idx_probe.insertMany([{a:1},{a:2}]);"
            f" db.repl_idx_probe.createIndex({{a:1}}, {{name:'{name}'}});"
            " return 1; })()")
        sec = self._secondary(srv)
        # The build is acknowledged by a majority before createIndex returns, but the
        # secondary's catalog read is its own operation -- poll briefly rather than
        # assume, so a slow member is a wait and not a false failure.
        seen = sec.value(
            "(function(){ for (let i = 0; i < 40; i++) {"
            f"   const names = db.repl_idx_probe.getIndexes().map(x => x.name);"
            f"   if (names.indexOf('{name}') !== -1) return true;"
            "   sleep(250); } return false; })()")
        assert seen is True, (
            f"MongoDB {srv.major}: {name} never appeared on the secondary, so the "
            "'issue it on the primary and stop there' recommendation is unproven"
        )

    def test_a_write_on_the_primary_reaches_the_secondary(self, srv):
        """Sanity control for the test above: if replication itself were broken, the
        index assertion would fail for a reason that has nothing to do with builds."""
        srv.value("(function(){ db.repl_data_probe.drop();"
                  " db.repl_data_probe.insertOne({_id: 1, v: 'x'},"
                  " {writeConcern: {w: 'majority'}}); return 1; })()")
        sec = self._secondary(srv)
        got = sec.value(
            "(function(){ for (let i = 0; i < 40; i++) {"
            "   const d = db.repl_data_probe.findOne({_id: 1});"
            "   if (d) return d.v; sleep(250); } return null; })()")
        assert got == "x", got


# ---------------------------------------------------------------------------
# P1 -- facts the documents state. Each was wrong before 2026-08.
# ---------------------------------------------------------------------------

class TestDocumentedFacts:
    def test_collmod_changes_ttl_in_place(self, srv):
        """SKILL.md §5.1 item 4 used to say a TTL change requires dropIndex +
        createIndex. collMod does it in place from 5.1, i.e. on every supported major."""
        res = srv.value(
            "(function(){ db.ttl_probe.drop(); db.ttl_probe.insertOne({at:new Date()});"
            " db.ttl_probe.createIndex({at:1},{expireAfterSeconds:3600});"
            " try { const r = db.runCommand({collMod:'ttl_probe',"
            "   index:{keyPattern:{at:1}, expireAfterSeconds:7200}});"
            "   return {ok: r.ok, now: db.ttl_probe.getIndexes()"
            "     .filter(i=>i.expireAfterSeconds!==undefined)[0].expireAfterSeconds}; }"
            " catch(e) { return {ok:0, err:(e.codeName||e.name)}; } })()")
        assert res.get("ok") == 1, res
        assert int(res["now"]) == 7200, res

    def test_moderate_rejects_a_noncompliant_insert(self, srv):
        r = srv.value(MODERATE_PROBE)
        assert r["insertNonCompliant"] == "REJECTED", (
            "'moderate only validates new writes' was the old wording; an insert is "
            "validated, so that phrasing does not distinguish moderate from strict", r)

    def test_moderate_rejects_breaking_a_currently_compliant_document(self, srv):
        r = srv.value(MODERATE_PROBE)
        assert r["updateCompliant"] == "REJECTED", (
            "'validates inserts and updates, not existing docs' was the old wording; "
            "updates to existing COMPLIANT documents are validated", r)

    def test_moderate_exempts_an_already_invalid_document(self, srv):
        """The actual carve-out, and the reason the moderate->backfill->strict sequence
        works at all."""
        r = srv.value(MODERATE_PROBE)
        assert r["updateNonCompliant"] == "ACCEPTED", r

    def test_create_collection_and_index_are_allowed_in_a_transaction(self, srv):
        """'MongoDB has no transactional DDL' was stated absolutely. Both of these
        commit inside a multi-document transaction."""
        r = srv.value(
            "(function(){ const s = db.getMongo().startSession(); const out = {};"
            " try { s.startTransaction();"
            "   const d = s.getDatabase('test'); const n = 'txnprobe_' + ObjectId().toHexString();"
            "   d.createCollection(n); d.getCollection(n).createIndex({a:1});"
            "   s.commitTransaction(); out.result = 'ALLOWED'; }"
            " catch(e) { try{s.abortTransaction()}catch(_){} out.result = (e.codeName||e.name); }"
            " return out; })()")
        assert r["result"] == "ALLOWED", r

    @pytest.mark.parametrize("path,expect_on", [
        ("db.serverStatus().wiredTiger && db.serverStatus().wiredTiger.concurrentTransactions", 7),
        ("db.serverStatus().queues && db.serverStatus().queues.execution", 8),
    ])
    def test_ticket_metric_path_is_version_dependent(self, srv, path, expect_on):
        """The lock matrix documents both paths. Reading the wrong one returns
        undefined, which is easy to mistake for 'no pressure'."""
        present = srv.value(f"(({path}) ? true : false)")
        assert present is (srv.major == expect_on), (
            f"MongoDB {srv.major}: `{path}` present={present}; the matrix says it is "
            f"the {expect_on}.x path"
        )

    def test_total_tickets_is_not_the_documented_constant_128(self, srv):
        """The lock matrix used to state a fixed default of 128 each. 7.0+ sizes the
        pool dynamically."""
        total = srv.value(
            "(function(){ const ss = db.serverStatus();"
            " const q = (ss.queues && ss.queues.execution) || ss.wiredTiger.concurrentTransactions;"
            " return q.write.totalTickets; })()")
        assert isinstance(total, int) and total > 0, total
        assert total != 128, (
            "totalTickets is exactly 128 here; that is a coincidence of this host, not "
            "a default -- but if it has become fixed again the matrix text needs review"
        )

    def test_printReplicationInfo_reports_the_oplog_window_not_lag(self, srv):
        """SKILL.md pointed at rs.printReplicationInfo() to 'monitor lag'. It prints the
        oplog window of the member you are connected to."""
        out = srv.eval("rs.printReplicationInfo()")
        assert out.returncode == 0, out.stderr
        assert "oplog" in out.stdout.lower(), out.stdout[:200]
        assert "lag" not in out.stdout.lower(), (
            "rs.printReplicationInfo() now reports lag; SKILL.md's correction needs "
            "revisiting", out.stdout[:200])


MODERATE_PROBE = """
(function () {
  db.mod_probe.drop();
  db.mod_probe.insertOne({_id: 1, name: "ok", age: 30});
  db.mod_probe.insertOne({_id: 2, age: "not-a-number"});
  db.runCommand({collMod: "mod_probe",
    validator: {$jsonSchema: {required: ["name"], properties: {age: {bsonType: "int"}}}},
    validationLevel: "moderate"});
  function t(fn) { try { fn(); return "ACCEPTED"; } catch (e) { return "REJECTED"; } }
  return {
    insertNonCompliant: t(() => db.mod_probe.insertOne({_id: 3, age: "bad"})),
    updateCompliant:    t(() => db.mod_probe.updateOne({_id: 1}, {$set: {age: "bad"}})),
    updateNonCompliant: t(() => db.mod_probe.updateOne({_id: 2}, {$set: {age: "worse"}}))
  };
})()
"""


# ---------------------------------------------------------------------------
# Every JavaScript block the skill ships must at least parse.
# ---------------------------------------------------------------------------

DOCS = [SKILL_DIR / "SKILL.md"] + sorted((SKILL_DIR / "references").glob("*.md"))
FENCE_RE = re.compile(r"```javascript\n(.*?)```", re.S)
_WRONG_MARKER = re.compile(r"^\s*(?://\s*)?(WRONG|// WRONG|-- WRONG)\b", re.I)
_EXCERPT_MARKER = re.compile(r"^\s*//\s*excerpt\b", re.I)
MAX_EXCERPTS = 3
EXCERPTS: list[str] = []


def _js_blocks() -> list[tuple[str, int, str]]:
    """Blocks the docs present as correct. Anything after a `// WRONG` marker up to the
    next `// RIGHT` is skipped -- those are anti-examples and several are invalid on
    purpose."""
    out = []
    for doc in DOCS:
        text = doc.read_text(encoding="utf-8")
        for m in FENCE_RE.finditer(text):
            block = m.group(1)
            first = next((ln for ln in block.splitlines() if ln.strip()), "")
            if _EXCERPT_MARKER.match(first):
                EXCERPTS.append(doc.name)
                continue
            base = text[:m.start()].count("\n") + 2
            skipping, kept = False, []
            for i, ln in enumerate(block.splitlines()):
                if _WRONG_MARKER.match(ln):
                    skipping = True
                elif re.match(r"^\s*//\s*RIGHT\b", ln, re.I):
                    skipping = False
                if not skipping:
                    kept.append(ln)
            if any(k.strip() for k in kept):
                out.append((doc.name, base, "\n".join(kept)))
    return out


JS_BLOCKS = _js_blocks()


class TestShippedJavaScriptParses:
    """A snippet nobody can run is worse than no snippet. The old backfill script threw
    TypeError on line one and shipped for months under 97 green tests."""

    def test_blocks_were_extracted(self):
        assert len(JS_BLOCKS) >= 10, (
            f"only {len(JS_BLOCKS)} javascript blocks extracted -- extraction is "
            "broken, so a green result here would prove nothing"
        )

    def test_excerpt_escape_hatch_stays_rare(self):
        assert len(EXCERPTS) <= MAX_EXCERPTS, (
            f"{len(EXCERPTS)} blocks are marked `// excerpt:` ({EXCERPTS}); cap is "
            f"{MAX_EXCERPTS}. Make the block runnable instead of exempting it."
        )

    @pytest.mark.parametrize("doc,line,js", JS_BLOCKS,
                             ids=[f"{d}:{ln}" for d, ln, _ in JS_BLOCKS])
    def test_block_is_syntactically_valid(self, srv, doc, line, js):
        """Parse-only: wrap the block in a Function constructor so mongosh compiles it
        without executing. Executing every block would drop collections and reconfigure
        the server; compiling catches the class of defect that actually shipped."""
        probe = ("(function(){ try { new Function(%s); return 'OK'; }"
                 " catch (e) { return 'SYNTAX: ' + e.message; } })()"
                 % _js_string_literal(js))
        verdict = srv.value(probe)
        assert verdict == "OK", f"{doc}:{line} on MongoDB {srv.major}: {verdict}"


def _js_string_literal(s: str) -> str:
    """Encode Python text as a JS string literal safe to embed in --eval."""
    import json as _json
    return _json.dumps(s)
