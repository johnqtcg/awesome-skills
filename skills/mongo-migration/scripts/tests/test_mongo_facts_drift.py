"""Drift guards for MongoDB facts, each verified against a live server.

Every entry pins one claim that was WRONG in this skill before 2026-08. The `source`
field records how it was established so a reviewer can re-check rather than trust this
file, and `forbid` pins the superseded wording so the old sentence cannot come back.

Design notes, learned the hard way on the sibling pg-migration skill:

* Checks are **per-subject**. "Does the word `moderate` appear anywhere" is satisfied by
  an unrelated mention, so each check pins a distinguishing phrase.
* `forbid` patterns target the **previous wrong phrasing** specifically, never a
  substring the correcting explanation also contains -- otherwise the sentence saying
  why something was wrong trips the guard.
* Every `forbid` needs a superseded sample proving the pattern can actually fire. A
  typo'd regex that can never match would pass forever.
"""

from __future__ import annotations

import dataclasses
import pathlib
import re

import pytest

SKILL_DIR = pathlib.Path(__file__).resolve().parents[2]
SKILL_MD = SKILL_DIR / "SKILL.md"
LARGE = SKILL_DIR / "references" / "large-collection-migration.md"
MATRIX = SKILL_DIR / "references" / "mongo-ddl-lock-matrix.md"
ANTI = SKILL_DIR / "references" / "migration-anti-examples.md"



# A document that CORRECTS an error usually quotes the error. Those quotations must not
# trip the guard against the error -- the "guard must allow its own correction" trap.
# So `forbid` is applied to the document with its WRONG-marked regions removed: any
# fenced block containing a WRONG marker, and any block under a "what was here before"
# heading. `require` still sees the whole file.
_FENCE_RE = re.compile(r"```[a-z]*\n.*?```", re.S)
_WRONG_IN_BLOCK = re.compile(r"^\s*(?://|--)?\s*WRONG\b", re.I | re.M)
_SUPERSEDED_HEADING = re.compile(
    r"^#+ .*(what was here before|superseded|used to ship).*$", re.I | re.M)


_RIGHT_MARKER = re.compile(r"^\s*(?://|--)?\s*RIGHT\b", re.I)


def forbid_scope(text: str) -> str:
    """The text a `forbid` pattern is allowed to see."""
    def blank(m):
        body = m.group(0)
        if not _WRONG_IN_BLOCK.search(body):
            return body
        # Blank only the WRONG REGION -- from each WRONG marker to the next RIGHT one --
        # not the whole block. Blanking the block hid the RIGHT half too, so a bad
        # recommendation sitting next to the error it corrects was invisible to the
        # scan. (Found exactly that way: AE-2's RIGHT half said "batch by _id range".)
        # Sentinel, not "": preserves length, and stops neighbouring lines fusing into
        # a match that exists in neither.
        out_lines = []
        skipping = False
        for ln in body.splitlines(keepends=True):
            if _WRONG_IN_BLOCK.match(ln):
                skipping = True
            elif _RIGHT_MARKER.match(ln):
                skipping = False
            out_lines.append("\x00" * len(ln) if skipping else ln)
        return "".join(out_lines)
    out = _FENCE_RE.sub(blank, text)

    # Drop each "what was here before" section up to the next heading of any level.
    for m in reversed(list(_SUPERSEDED_HEADING.finditer(out))):
        nxt = re.search(r"^#+ ", out[m.end():], re.M)
        end = m.end() + (nxt.start() if nxt else len(out) - m.end())
        out = out[:m.start()] + "\x00" * (end - m.start()) + out[end:]
    return out


@dataclasses.dataclass(frozen=True)
class Fact:
    fid: str
    doc: pathlib.Path
    require: str
    forbid: str | None
    source: str
    why: str


FACTS: tuple[Fact, ...] = (
    Fact("M01-objectid-valueof-not-a-string", LARGE,
         r"valueOf\(\)`? returns an \*{0,2}object\*{0,2}",
         r"\$lte: ObjectId\(lastId\.valueOf\(\)\.substring\(0,24\)\)\}",
         "measured on live 7.0.31 and 8.0.28",
         "The shipped loop called .substring on the result of valueOf(), which is an "
         "object. It threw TypeError on the first iteration -- the script could not "
         "run at all. Reintroducing that line ships a migration that does nothing."),

    Fact("M02-empty-objectid-range", LARGE,
         r"reconstructs \*{0,2}the same ObjectId\*{0,2}|always empty",
         None,
         "measured: ObjectId(id.toHexString()).equals(id) is true on 7.0 and 8.0",
         "Even with the TypeError fixed, both bounds resolve to the same id, so the "
         "range selects nothing and the loop reports success having migrated zero."),

    # Was pinned to "the cursor comes from the batch you just processed" -- correct
    # while a cursor was mandatory, and the WRONG default once the cursorless loop
    # replaced it. A guard that pins superseded wording keeps that wording alive.
    Fact("M03-no-cursor-by-default", LARGE,
         r"There is no cursor by default",
         None,
         "skill rule, proven by test_mongo_server_matrix.py",
         "The default loop carries no cursor at all, which is what makes it correct for "
         "any _id BSON type. A cursor is only introduced by the $gt optimisation, and "
         "then it must come from the batch just processed."),

    Fact("M03b-keyset-cursor-from-the-batch", LARGE,
         r"must come from the batch just processed",
         None,
         "skill rule - the arithmetic and max() forms are the original defects",
         "When the keyset optimisation IS taken, its cursor still may not come from "
         "arithmetic on the key or from a collection-wide max."),

    Fact("M04-resume-is-the-predicate", LARGE,
         r"predicate is the resume point",
         r"// Resume from lastMigrated\._id",
         "skill rule - a pre-migrated high key hides unfinished work below it",
         "Resuming from max(_id) of the migrated set skips every unprocessed document "
         "beneath a document that already carried the field."),

    Fact("M05-secondary-rejects-writes", LARGE,
         r"NotWritablePrimary",
         r"a\. Connect directly to the secondary",
         "measured on a live 3-member replica set (MongoDB 8.0)",
         "The old rolling procedure's first action is rejected by the server, so the "
         "procedure could not be executed as written -- and a fixture called it "
         "'no violations'."),

    Fact("M06-replicated-is-not-rolling", LARGE,
         r"\*{0,2}\"Replicated build\" and \"rolling build\" are different things\*{0,2}",
         r"MongoDB 4\.2\+ uses rolling/optimized builds by default",
         "manual: the 4.2 change made the DEFAULT build cheaper, not rolling",
         "Conflating them sends readers to a manual, resilience-reducing procedure "
         "instead of the default that already does what they want."),

    Fact("M07-real-rolling-needs-standalone", LARGE,
         r"Restart it as a \*{0,2}standalone\*{0,2}.*different\s*\n?\s*\*{0,2}port\*{0,2}",
         None,
         "manual: build-indexes-on-replica-sets",
         "Taking the member OUT of the set is the step that makes a rolling build a "
         "rolling build; without it the remaining steps are meaningless."),

    Fact("M08-ttl-collmod-in-place", SKILL_MD,
         r"`collMod` changes `expireAfterSeconds` in place from MongoDB 5\.1",
         r"Changing TTL value requires dropIndex \+ createIndex",
         "measured on live 7.0.31 and 8.0.28",
         "Every version this skill covers can change a TTL in place. Telling the "
         "reader to drop and recreate forces an avoidable full index build."),

    Fact("M09-moderate-semantics", SKILL_MD,
         r"only an update to a document that \*{0,2}already failed\*{0,2} validation is exempt",
         r"validates only inserts and updates, not existing docs",
         "measured on 8.0: insert REJECTED, update-of-compliant REJECTED, "
         "update-of-already-invalid ACCEPTED",
         "'only validates new writes' is wrong in the direction that matters: a reader "
         "would expect updates to existing documents to be exempt, and they are not "
         "unless the document already failed validation."),

    Fact("M10-transactional-ddl-nuance", SKILL_MD,
         r"createCollection` and `createIndex` \*are\* permitted inside a multi-document transaction",
         r"MongoDB has no transactional DDL\. Index drops are instant",
         "measured on 7.0 and 8.0: both commit inside a transaction",
         "'No transactional DDL' stated absolutely is false, and it discourages a "
         "rollback mechanism that genuinely exists for a narrow set of operations."),

    Fact("M11-unset-not-reversible", SKILL_MD,
         r"`\$unset` is not reversible by an \"inverse operation\"",
         r"\$set/\$unset can be reversed with inverse operation",
         "skill rule - the previous value is gone unless captured first",
         "Calling $unset 'script-rollback' invites a rollback plan that cannot work."),

    Fact("M12-replication-lag-command", SKILL_MD,
         r"rs\.printSecondaryReplicationInfo\(\)",
         r"Monitor `rs\.printReplicationInfo\(\)` for lag",
         "measured: printReplicationInfo prints the connected member's oplog window",
         "Pointing at the wrong command means the reader watches oplog retention and "
         "believes they are watching lag."),

    Fact("M13-tickets-not-a-fixed-128", MATRIX,
         r"The pool is not a fixed 128",
         r"\(default: 128 each\)",
         "measured: totalTickets was 10 on both 7.0 and 8.0; 7.0+ sizes it dynamically",
         "Planning batch sizes against a constant that the server no longer uses."),

    Fact("M14-ticket-path-moved", MATRIX,
         r"queues\.execution.*\n?.*\|\s*present",
         None,
         "measured: wiredTiger.concurrentTransactions absent on 8.0, "
         "queues.execution absent on 7.0",
         "Reading the wrong path returns undefined, which looks exactly like "
         "'no ticket pressure'."),

    Fact("M15-validate-is-not-a-migration-check", LARGE,
         r"exclusive lock on the collection",
         r"Run `db\.collection\.validate\(\)` and check `collStats`",
         "manual: validate() takes an exclusive collection lock",
         "Recommending validate() as a routine post-migration step schedules a long "
         "exclusive lock to answer a question it does not answer."),

    Fact("M17-gate1-asks-id-type", SKILL_MD,
         r"`_id` BSON type uniformity",
         None,
         "measured: $gt type-brackets, so a keyset over _id needs a single type",
         "The keyset optimisation is offered on the condition that Gate 1 established a "
         "single _id BSON type. If Gate 1 stops asking, the condition is unenforceable "
         "and the optimisation becomes the data-losing default again."),

    Fact("M18-gate1-defaults-to-mixed", SKILL_MD,
         r"If unknown, assume mixed",
         None,
         "skill rule - degrade toward the safe form, never the fast one",
         "An unknown _id type must route to the cursorless loop. Defaulting the other "
         "way would strand documents on exactly the collections nobody has inspected."),

    Fact("M16-supported-majors", SKILL_MD,
         r"MongoDB \*{0,2}7\.0 and 8\.0\*{0,2}",
         r"schema migration safety for MongoDB 4\.4 / 5\.0 / 6\.0 / 7\.0\+",
         "MongoDB lifecycle: 4.4, 5.0, 6.0 are EOL as of 2026-08",
         "A default assumption of 4.4 makes every version-gated rule in the skill "
         "reason about a release nobody should be running."),
)


@pytest.mark.parametrize("fact", FACTS, ids=[f.fid for f in FACTS])
class TestFactDrift:
    def test_required_claim_present(self, fact):
        text = fact.doc.read_text(encoding="utf-8")
        assert re.search(fact.require, text, re.I | re.S), (
            f"{fact.fid}: the corrected claim is missing from {fact.doc.name}.\n"
            f"  Source: {fact.source}\n  Why it matters: {fact.why}"
        )

    def test_superseded_claim_absent(self, fact):
        if fact.forbid is None:
            pytest.skip("no superseded phrasing pinned for this fact")
        text = forbid_scope(fact.doc.read_text(encoding="utf-8"))
        assert not re.search(fact.forbid, text, re.I), (
            f"{fact.fid}: the superseded wording is back in {fact.doc.name}.\n"
            f"  Why it was wrong: {fact.why}"
        )


class TestFactRegistryIntegrity:
    def test_every_fact_points_at_a_real_file(self):
        for f in FACTS:
            assert f.doc.exists(), f"{f.fid} points at a missing file: {f.doc}"

    def test_every_fact_has_a_source_and_reason(self):
        for f in FACTS:
            assert f.source.strip(), f"{f.fid} has no source"
            assert f.why.strip(), f"{f.fid} has no rationale"

    def test_forbid_patterns_do_not_match_their_own_require(self):
        """A forbid that also matches the corrected text makes the two halves of the
        guard mutually unsatisfiable."""
        for f in FACTS:
            if f.forbid is None:
                continue
            raw = f.doc.read_text(encoding="utf-8")
            assert re.search(f.require, raw, re.I | re.S), f"{f.fid}: require failed"
            assert not re.search(f.forbid, forbid_scope(raw), re.I), (
                f"{f.fid}: forbid matched outside a WRONG-marked region")

    def test_forbid_patterns_are_specific_enough_to_fire(self):
        """Positive control: each forbidden pattern must match its own superseded text.
        A regex that can never match would pass forever as an inert guard."""
        superseded = {
            "M01-objectid-valueof-not-a-string":
                "      _id: {$gt: lastId, $lte: ObjectId(lastId.valueOf().substring(0,24))},",
            "M04-resume-is-the-predicate":
                "// Resume from lastMigrated._id",
            "M05-secondary-rejects-writes":
                "   a. Connect directly to the secondary",
            "M06-replicated-is-not-rolling":
                "**When NOT needed**: MongoDB 4.2+ uses rolling/optimized builds by "
                "default for collections <50M documents.",
            "M08-ttl-collmod-in-place":
                "Changing TTL value requires dropIndex + createIndex (no in-place "
                "modification).",
            "M09-moderate-semantics":
                'validationLevel: "moderate" first (validates only inserts and updates, '
                "not existing docs)",
            "M10-transactional-ddl-nuance":
                "MongoDB has no transactional DDL. Index drops are instant but data "
                "changes are permanent.",
            "M11-unset-not-reversible":
                "- **Script-rollback**: $set/$unset can be reversed with inverse operation",
            "M12-replication-lag-command":
                "Monitor `rs.printReplicationInfo()` for lag.",
            "M13-tickets-not-a-fixed-128":
                "MongoDB limits concurrent operations via WiredTiger read/write tickets "
                "(default: 128 each).",
            "M15-validate-is-not-a-migration-check":
                "| Post-migration | Run `db.collection.validate()` and check `collStats` |",
            "M16-supported-majors":
                "**In scope** — schema migration safety for MongoDB 4.4 / 5.0 / 6.0 / 7.0+:",
        }
        for f in FACTS:
            if f.forbid is None:
                continue
            sample = superseded.get(f.fid)
            assert sample is not None, (
                f"{f.fid} pins a forbidden pattern but provides no superseded sample "
                "to prove the pattern can fire"
            )
            assert re.search(f.forbid, sample, re.I), (
                f"{f.fid}: the forbid pattern does not match its own superseded text, "
                "so it is inert"
            )


# The fixtures are corpus too. Scanning only the four Markdown files let superseded
# instructions survive in `violated_rule` and `coverage_rules` -- the very strings a
# reader of the test corpus would take as the rule.
_GOLDEN = sorted((SKILL_DIR / "scripts" / "tests" / "golden").glob("*.json"))
ALL_DOCS = [SKILL_MD, LARGE, MATRIX, ANTI] + _GOLDEN


class TestCrossFileConsistency:
    """Per-file `forbid` patterns cannot catch a claim corrected in one file and left
    standing in another. That is exactly what happened: the checklist required a
    replicated build while the SAFE row, Phase 1, AE-1, the lock matrix and an
    anti-example all still recommended a rolling one. An agent may read either.

    These scan EVERY document for phrasings that contradict a corrected rule, outside
    the WRONG-marked regions where quoting the old form is the point.
    """

    # A ban on a phrase must always exempt the sentence that REFUTES the phrase --
    # otherwise correcting an error trips the guard against that error. This kept
    # recurring, so it is one shared pattern rather than a hand-tuned exception per ban.
    REFUTATION = re.compile(
        r"does\s+(?:\*\*)?not(?:\*\*)?\s+mean|is not|are different things|conflates|"
        r"too strong|misleading|never|NOT\b|superseded|previously|used to|"
        r"could not (?:run|work)|cannot (?:run|work)|would (?:be )?wrong|is wrong|"
        r"\bWRONG\b|rather than|instead of|only .*exception|deliberate exception",
        re.I)

    BANNED = [
        # "rolling index" as well as "rolling build": the SAFE row said the former, and
        # a ban keyed only to the latter let it through.
        (r"rolling (?:build|index)",
         r"rolling build (?:is not|takes the member|removes each|is a different|"
         r"pattern\)|and is not|is NOT)|"
         r"not (?:a |what )?(?:this is a )?rolling|"
         r"real rolling build|Rolling Index Build|a rolling build|"
         r"replicated vs rolling|the rolling exception|rolling builds, TTL",
         "recommends a rolling index build without marking it the exception it is"),
        (r"only validates new writes|only new writes (?:are )?validated",
         None,
         "describes validationLevel moderate as validating only new writes"),
        # No hand-written allowance here. The earlier one, `has no transactional DDL\b`,
        # matched the bare claim it was meant to ban -- an exemption that swallowed its
        # own rule. Qualified phrasings are covered by REFUTATION above.
        (r"(?:MongoDB )?has no transactional DDL",
         None,
         "states flatly that MongoDB has no transactional DDL"),
        # Keyed to the CONCEPT, not to one spelling. The previous version banned the
        # exact string "_id-range batch" while the documents said "batch by `_id`
        # range", "_id range batched", "Batch by _id range" -- four phrasings of the
        # same instruction, none of which it matched. Same failure as banning "rolling
        # build" while the offending line said "rolling index".
        (r"(?:batch(?:ed|ing)?\s+by\s+[`\s]*_id[`\s]*\s*range"
         r"|_id[-\s]range\s+batch\w*"
         r"|batch\s+by\s+[`\s]*_id"
         r"|_id[-\s]range\s*\)"
         r"|with\s+[`\s]*_id[`\s]*[-\s]range)",
         None,
         "instructs the reader to batch by _id range; that is an optimisation "
         "conditional on a single _id BSON type, not the rule"),
    ]

    @pytest.mark.parametrize("doc", ALL_DOCS, ids=[d.name for d in ALL_DOCS])
    @pytest.mark.parametrize("pattern,allowed,why", BANNED,
                             ids=[b[2][:34] for b in BANNED])
    def test_no_document_contradicts_a_corrected_rule(self, doc, pattern, allowed, why):
        text = forbid_scope(doc.read_text(encoding="utf-8"))
        offenders = []
        for m in re.finditer(pattern, text, re.I):
            line_start = text.rfind("\n", 0, m.start()) + 1
            line_end = text.find("\n", m.end())
            line = text[line_start:line_end if line_end != -1 else len(text)]
            if self.REFUTATION.search(line):
                continue          # a sentence correcting the claim, not making it
            if allowed and re.search(allowed, line, re.I):
                continue          # the corrected, qualified phrasing
            offenders.append(line.strip()[:120])
        assert not offenders, (
            f"{doc.name} {why}:\n  " + "\n  ".join(offenders[:4])
        )
