"""Behavioural tests for lint_migration.py, plus the fixtures→checker link.

These differ in kind from the pre-2026-08 suite. That suite asserted that a fixture's
own hand-written ``expected_feedback`` contained certain words, so it could only ever
prove that the document, the fixture and the test shared a wording. It preserved, green,
a backfill script that throws TypeError on its first line and a rolling-index procedure
the server rejects.

Here the real checker is fed real JavaScript and the emitted codes are asserted. Every
rule needs BOTH a violating input and a compliant one -- the compliant half is what
catches a rule that fires on everything, which a violation-only suite cannot see.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import sys

import pytest

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parents[1]
GOLDEN_DIR = pathlib.Path(__file__).resolve().parent / "golden"


def _load_linter():
    """Load by path: this repo runs pytest with --import-mode=importlib, which breaks
    bare sibling imports. Register in sys.modules before exec_module so dataclasses can
    resolve the module during class creation."""
    path = SCRIPTS_DIR / "lint_migration.py"
    spec = importlib.util.spec_from_file_location("mongo_lint_migration", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["mongo_lint_migration"] = mod
    spec.loader.exec_module(mod)
    return mod


LINT = _load_linter()


def codes(js: str, **kw) -> set[str]:
    return {f.code for f in LINT.Linter(**kw).lint(js)}


def findings(js: str, **kw):
    return LINT.Linter(**kw).lint(js)


# ---------------------------------------------------------------------------
# Coverage declared as data: (code, violating JS, compliant JS, kwargs)
# ---------------------------------------------------------------------------

# The loop this skill recommends. No $gt: comparison operators type-bracket, so a
# cursor over _id strands every _id whose BSON type differs from the cursor's. The
# predicate is the cursor, and it is also the resume point.
GOOD_LOOP = """
while (true) {
  const batch = db.orders.find({new_field: {$exists: false}}, {_id: 1})
                  .sort({_id: 1}).limit(5000).toArray();
  if (batch.length === 0) break;
  const ids = batch.map(d => d._id);
  db.orders.updateMany({_id: {$in: ids}, new_field: {$exists: false}},
                       {$set: {new_field: "v"}}, {writeConcern: {w: "majority"}});
  sleep(100);
}
"""

CASES: list[tuple[str, str, str, dict]] = [
    ("MG001",
     'db.orders.updateMany({}, {$set: {f: 1}}, {writeConcern: {w: "majority"}});',
     GOOD_LOOP, {}),
    ("MG002",
     'db.orders.updateMany({_id: {$gt: lastId, $lte: ObjectId(lastId)}},'
     ' {$set: {f: 1}}, {writeConcern: {w: "majority"}});',
     GOOD_LOOP, {}),
    ("MG003",
     'const hex = lastId.valueOf().substring(0, 24);',
     'const hex = lastId.toHexString();', {}),
    ("MG004",
     'db.getMongo().setReadPref("secondary");\ndb.orders.createIndex({a: 1});',
     'db.orders.createIndex({a: 1});\nrs.printSecondaryReplicationInfo();', {}),
    ("MG005",
     'while (true) { const ids = [1]; db.o.updateMany({_id: {$in: ids}},'
     ' {$set: {f: 1}}); sleep(10); break; }',
     GOOD_LOOP, {}),
    ("MG006",
     'const last = db.orders.find({_migrated: true}).sort({_id: -1}).limit(1).next();',
     'db.orders.countDocuments({new_field: {$exists: false}});', {}),
    ("MG007",
     'db.runCommand({collMod: "o", validator: {}, validationLevel: "strict"});',
     'db.runCommand({collMod: "o", validator: {}, validationLevel: "moderate"});\n'
     'db.runCommand({collMod: "o", validationLevel: "strict"});', {}),
    ("MG008",
     'db.orders.createIndex({email: 1}, {unique: true});',
     'db.orders.aggregate([{$group: {_id: "$email", n: {$sum: 1}}},'
     ' {$match: {n: {$gt: 1}}}]);\n'
     'db.orders.createIndex({email: 1}, {unique: true});', {}),
    ("MG009",
     'db.events.dropIndex("createdAt_1");\n'
     'db.events.createIndex({createdAt: 1}, {expireAfterSeconds: 7200});',
     'db.runCommand({collMod: "events",'
     ' index: {keyPattern: {createdAt: 1}, expireAfterSeconds: 7200}});', {}),
    ("MG011",
     'db.orders.validate();',
     'db.orders.countDocuments({new_field: {$exists: false}});', {}),
    ("MG012",
     'rs.printReplicationInfo();',
     'rs.printSecondaryReplicationInfo();', {}),
    ("MG013",
     'db.serverStatus().wiredTiger.concurrentTransactions;',
     'const q = (db.serverStatus().queues || {}).execution;', {"mongo_version": 8}),
    ("MG014",
     'while (true) { const ids = [1];'
     ' db.o.updateMany({_id: {$in: ids}}, {$set: {f: 1}},'
     ' {writeConcern: {w: "majority"}}); break; }',
     GOOD_LOOP, {}),
    ("MG016",
     'let lastId = null;\nwhile (true) {\n  const q = {f: {$exists: false}};\n'
     '  if (lastId !== null) q._id = {$gt: lastId};\n'
     '  const b = db.c.find(q, {_id: 1}).sort({_id: 1}).limit(5000).toArray();\n'
     '  if (b.length === 0) break;\n  const ids = b.map(d => d._id);\n'
     '  db.c.updateMany({_id: {$in: ids}}, {$set: {f: 1}},'
     ' {writeConcern: {w: "majority"}});\n  lastId = ids[ids.length - 1];\n'
     '  sleep(100);\n}',
     GOOD_LOOP, {}),
    ("MG015",
     'db.orders.createIndex({a: 1});',
     'db.orders.createIndex({a: 1});\nrs.printSecondaryReplicationInfo();',
     {"docs": 30_000_000}),
]

CASES_BY_CODE = {c[0]: c for c in CASES}

# Severity pinned INDEPENDENTLY of the checker's own registry. Deriving it from
# RULES_BY_CODE would make the assertion tautological -- a mutation that downgrades a
# rule would move both sides together and the test would still pass.
EXPECTED_SEVERITY: dict[str, str] = {
    "MG001": "critical",   # one unbounded write holds a ticket for its whole duration
    "MG002": "critical",   # migrates nothing while reporting success
    "MG003": "critical",   # throws on the first iteration
    "MG004": "critical",   # the procedure cannot execute
    "MG005": "standard",
    "MG006": "standard",
    "MG007": "standard",
    "MG008": "standard",
    "MG009": "standard",
    "MG010": "standard",
    "MG011": "standard",
    "MG015": "standard",
    "MG016": "critical",
    "MG012": "hygiene",
    "MG013": "hygiene",
    "MG014": "hygiene",
}


class TestRuleRegistry:
    def test_every_rule_has_a_source(self):
        for rule in LINT.RULES:
            assert rule.source.strip(), f"{rule.code} has no documentation source"

    def test_pinned_severities_cover_every_rule(self):
        assert {r.code for r in LINT.RULES} == set(EXPECTED_SEVERITY), (
            "EXPECTED_SEVERITY must pin exactly the registry's rules"
        )

    def test_every_rule_has_a_test_case(self):
        missing = sorted({r.code for r in LINT.RULES} - set(CASES_BY_CODE))
        # MG010 has no automatable violating input: it is about prose describing $unset
        # as reversible, which the drift guards cover instead. Declared, not silent.
        assert missing == ["MG010"], missing

    def test_registry_severity_matches_the_independent_pin(self):
        for code, sev in EXPECTED_SEVERITY.items():
            assert LINT.RULES_BY_CODE[code].severity == sev, code


@pytest.mark.parametrize("code,bad,good,kw", CASES, ids=[c[0] for c in CASES])
class TestEachRule:
    def test_fires_on_violation(self, code, bad, good, kw):
        assert code in codes(bad, **kw), f"{code} did not fire on its violating input"

    def test_silent_on_compliant(self, code, bad, good, kw):
        assert code not in codes(good, **kw), (
            f"{code} fired on its COMPLIANT input -- false positive"
        )

    def test_emitted_severity_matches_the_pinned_value(self, code, bad, good, kw):
        emitted = [f for f in findings(bad, **kw) if f.code == code]
        assert emitted
        assert emitted[0].severity == EXPECTED_SEVERITY[code], (
            f"{code} emitted {emitted[0].severity!r}, pinned as "
            f"{EXPECTED_SEVERITY[code]!r}"
        )


class TestTheScriptThisSkillUsedToShip:
    """The exact backfill loop that shipped until 2026-08, kept as a regression probe.

    It had two independent defects and 97 green tests preserved both. If the checker
    ever stops reporting them, the same class of error can ship again.
    """

    ORIGINAL = """
let lastId = ObjectId("000000000000000000000000");
while (true) {
  const result = db.orders.updateMany(
    {_id: {$gt: lastId, $lte: ObjectId(lastId.valueOf().substring(0,24))},
     new_field: {$exists: false}},
    {$set: {new_field: "default_value"}},
    {writeConcern: {w: "majority"}}
  );
  const nextDoc = db.orders.find({_id: {$gt: lastId}})
    .sort({_id: 1}).skip(4999).limit(1).next();
  if (!nextDoc) break;
  lastId = nextDoc._id;
  sleep(100);
}
"""

    def test_reports_the_typeerror_defect(self):
        assert "MG003" in codes(self.ORIGINAL)

    def test_reports_the_empty_range_defect(self):
        assert "MG002" in codes(self.ORIGINAL)

    def test_both_are_critical(self):
        got = {f.code: f.severity for f in findings(self.ORIGINAL)}
        assert got["MG002"] == "critical" and got["MG003"] == "critical", got

    def test_the_replacement_is_clean(self):
        """The corrected loop must pass the checker, or the skill recommends
        JavaScript its own tool rejects."""
        assert findings(GOOD_LOOP) == []


class TestDocumentSizeEscalation:
    """--docs may escalate a verdict but never de-escalate one: an unknown size has to
    keep the finding, or the flag becomes a way to silence the checker."""

    SQL = 'db.orders.updateMany({}, {$set: {f: 1}}, {writeConcern: {w: "majority"}});'

    def _sev(self, **kw):
        return {f.code: f.severity for f in findings(self.SQL, **kw)}

    def test_unknown_size_still_reports(self):
        assert "MG001" in self._sev()

    def test_large_collection_is_critical(self):
        assert self._sev(docs=20_000_000)["MG001"] == "critical"

    def test_docs_never_suppresses_a_finding(self):
        for n in (0, 1, 1000, 50_000_000):
            assert "MG001" in self._sev(docs=n), f"--docs {n} silenced the finding"


class TestGoldenFixturesDriveTheChecker:
    """The link the pre-2026-08 suite was missing.

    It asserted `"no violation" in fixture["expected_feedback"]` -- a string the fixture
    author wrote. Nothing ran. Here every fixture's snippet goes through the real
    checker and the emitted codes must match what the fixture declares.
    """

    FIXTURES = [json.loads(p.read_text(encoding="utf-8"))
                for p in sorted(GOLDEN_DIR.glob("*.json"))]

    def test_fixtures_were_loaded(self):
        assert len(self.FIXTURES) >= 13, len(self.FIXTURES)

    @pytest.mark.parametrize("fix", FIXTURES, ids=[f["id"] for f in FIXTURES])
    def test_declared_codes_match_the_checker(self, fix):
        ctx = fix["lint_context"]
        emitted = sorted({f.code for f in LINT.Linter(
            ctx["mongo_version"], ctx["docs"]).lint(fix["migration_snippet"])})
        assert emitted == fix["expected_lint_codes"], (
            f"{fix['id']}: checker emitted {emitted}, fixture declares "
            f"{fix['expected_lint_codes']}"
        )

    @pytest.mark.parametrize("fix", FIXTURES, ids=[f["id"] for f in FIXTURES])
    def test_good_practice_fixtures_are_actually_clean(self, fix):
        """MONGO-008 recorded a procedure the server rejects as 'No violations'. A
        good-practice fixture now has to survive the checker, not just say it does."""
        if fix["type"] != "good_practice":
            pytest.skip("not a good_practice fixture")
        assert fix["expected_lint_codes"] == [], (
            f"{fix['id']} is labelled good_practice but the checker reports "
            f"{fix['expected_lint_codes']}"
        )

    @pytest.mark.parametrize("fix", FIXTURES, ids=[f["id"] for f in FIXTURES])
    def test_defect_fixtures_actually_trip_a_rule(self, fix):
        """A defect fixture no rule covers is a coverage gap stated as data rather than
        discovered later."""
        if fix["type"] != "defect":
            pytest.skip("not a defect fixture")
        assert fix["expected_lint_codes"], (
            f"{fix['id']} is labelled a defect but no rule fires on it"
        )


class TestOutputContract:
    def test_clean_result_does_not_read_as_a_safety_verdict(self, tmp_path, capsys):
        p = tmp_path / "ok.js"
        p.write_text(GOOD_LOOP)
        assert LINT.main([str(p)]) == 0
        out = capsys.readouterr().out
        assert "0 findings" in out
        assert "NOT a proof of safety" in out, out

    def test_json_carries_the_limitations(self, tmp_path, capsys):
        p = tmp_path / "bad.js"
        p.write_text('db.o.updateMany({}, {$set: {a: 1}});')
        LINT.main([str(p), "--json"])
        payload = json.loads(capsys.readouterr().out)
        assert payload["findings"][str(p)]
        assert payload["unprovable"], "JSON output dropped the limitations"

    def test_limitations_flag_lists_them(self, capsys):
        assert LINT.main(["--limitations"]) == 0
        assert "cannot establish" in capsys.readouterr().out

    def test_missing_file_exits_two(self, tmp_path):
        assert LINT.main([str(tmp_path / "nope.js")]) == 2

    def test_comments_are_not_code(self):
        """A line explaining why a call is wrong must not count as making it."""
        assert "MG011" not in codes("// never call db.orders.validate() here\n")
        assert "MG012" not in codes("// rs.printReplicationInfo() is the wrong command\n")


class TestMG016PreconditionContract:
    """MG016's name is "no single-type guarantee", not "uses $gt". A script that
    establishes the guarantee must clear it, or the rule is unfalsifiable in practice
    and reviewers learn to ignore it."""

    KEYSET = """
let lastId = null;
while (true) {
  const q = {f: {$exists: false}};
  if (lastId !== null) q._id = {$gt: lastId};
  const b = db.c.find(q, {_id: 1}).sort({_id: 1}).limit(5000).toArray();
  if (b.length === 0) break;
  const ids = b.map(d => d._id);
  db.c.updateMany({_id: {$in: ids}}, {$set: {f: 1}},
                  {writeConcern: {w: "majority"}});
  lastId = ids[ids.length - 1];
  sleep(100);
}
"""
    PROOF = ('const t = db.c.aggregate([{$group: {_id: {$type: "$_id"}}}]).toArray();\n'
             'if (t.length !== 1) throw new Error("mixed _id types");\n')
    ASKS_ONLY = 'const t = db.c.aggregate([{$group: {_id: {$type: "$_id"}}}]).toArray();\n'

    def test_bare_keyset_is_reported(self):
        assert "MG016" in codes(self.KEYSET)

    def test_declared_id_type_clears_it(self):
        assert "MG016" not in codes(self.KEYSET, id_type="objectId")

    def test_in_script_proof_clears_it(self):
        assert "MG016" not in codes(self.PROOF + self.KEYSET)

    def test_an_unrelated_abort_does_not_clear_it(self):
        """The bypass a reviewer built: probe the _id types, print them, then throw
        because an unrelated config key is missing. The old check asked only whether
        `$type: "$_id"` appeared anywhere and whether a `throw` appeared anywhere, with
        no relationship required between them."""
        js = ('const t = db.c.aggregate([{$group: {_id: {$type: "$_id"}}}]).toArray();\n'
              'print("id types seen: " + t.length);\n'
              'if (!config.batchSize) throw new Error("missing batchSize in config");\n')
        assert "MG016" in codes(js + self.KEYSET)

    def test_comparing_without_aborting_does_not_clear_it(self):
        js = ('const t = db.c.aggregate([{$group: {_id: {$type: "$_id"}}}]).toArray();\n'
              'if (t.length !== 1) print("mixed!");\n')
        assert "MG016" in codes(js + self.KEYSET)

    def test_a_proof_far_from_its_subject_does_not_clear_it(self):
        """A check forty statements from the value it checks is not one a reviewer can
        follow, so it is not accepted as one."""
        filler = "".join(f"const pad{i} = db.other.countDocuments({{k: {i}}});\n"
                         for i in range(40))
        js = ('const t = db.c.aggregate([{$group: {_id: {$type: "$_id"}}}]).toArray();\n'
              + filler + 'if (t.length !== 1) throw new Error("mixed");\n')
        assert "MG016" in codes(js + self.KEYSET)

    def test_the_go_shape_of_the_proof_is_recognised(self):
        js = ('cur, _ := coll.Aggregate(ctx, mongo.Pipeline{{{Key: "$group", '
              'Value: bson.M{"_id": bson.M{"$type": "$_id"}}}}})\n'
              'var types []bson.M\n_ = cur.All(ctx, &types)\n'
              'if len(types) != 1 { return errors.New("mixed _id types") }\n')
        assert "MG016" not in codes(js + self.KEYSET)

    def test_asking_the_type_without_acting_does_not_clear_it(self):
        """The same shape of gap as fetching a definition and never comparing it:
        querying the types and ignoring the answer proves nothing."""
        assert "MG016" in codes(self.ASKS_ONLY + self.KEYSET)

    def test_a_comment_claiming_uniformity_does_not_clear_it(self):
        """Comments are stripped before analysis, so an assertion in prose cannot
        suppress a finding -- suppression has to be auditable."""
        claim = "// every _id in this collection is an ObjectId, promise\n"
        assert "MG016" in codes(claim + self.KEYSET)

    def test_a_literal_id_range_is_reported_too(self):
        """MG016's condition is two alternatives, and every other test here exercises
        the `{$gt: lastId}` spelling. A mutation that disabled the OTHER half --
        `_id: {$gt: ...}` written literally -- went unnoticed, so it is covered here."""
        js = ('while (true) {\n'
              '  const b = db.c.find({_id: {$gt: cutoff}}, {_id: 1})'
              '.sort({_id: 1}).limit(1000).toArray();\n'
              '  if (b.length === 0) break;\n  const ids = b.map(d => d._id);\n'
              '  db.c.updateMany({_id: {$in: ids}}, {$set: {f: 1}},'
              ' {writeConcern: {w: "majority"}});\n  sleep(50);\n}')
        assert "MG016" in codes(js)

    def test_a_conditional_abort_inside_the_branch_does_not_clear_it(self):
        """Bypass 3: a real `throw`, in the right branch, that only fires when an
        unrelated config check fails. The types being mixed still runs the keyset."""
        js = ('const types = db.c.aggregate([{$group: {_id: {$type: "$_id"}}}]).toArray();\n'
              'if (types.length !== 1) {\n'
              '  if (!config.ok) throw new Error("bad config");\n'
              '  print("mixed");\n}\n')
        assert "MG016" in codes(js + self.KEYSET)

    def test_a_no_op_assertion_does_not_clear_it(self):
        """Bypass 4: `assert(true)` terminates nothing. `assert` is no longer in the
        accepted set at all -- it cannot be distinguished from its no-op form here."""
        js = ('const types = db.c.aggregate([{$group: {_id: {$type: "$_id"}}}]).toArray();\n'
              'if (types.length !== 1) {\n  assert(true);\n  print("mixed");\n}\n')
        assert "MG016" in codes(js + self.KEYSET)

    def test_the_abort_must_be_the_FIRST_statement(self):
        """Anything before it is a statement the reader must check for control flow.
        The bar is an immediate, unconditional termination."""
        js = ('const types = db.c.aggregate([{$group: {_id: {$type: "$_id"}}}]).toArray();\n'
              'if (types.length !== 1) {\n  print("mixed");\n'
              '  throw new Error("mixed");\n}\n')
        assert "MG016" in codes(js + self.KEYSET)

    def test_the_cursorless_loop_needs_no_precondition(self):
        assert "MG016" not in codes(GOOD_LOOP)
