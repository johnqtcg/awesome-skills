#!/usr/bin/env python3
"""Deterministic safety checker for MongoDB migration scripts.

Why this exists: before 2026-08 this skill had 97 passing tests and no executable
checker. The tests asserted that a fixture's hand-written ``expected_feedback`` string
contained certain words, so a backfill script that throws ``TypeError`` on its first
line and a rolling-index procedure the server rejects both passed review, and one of
them was recorded as "no violations".

Every rule below is grounded either in a MongoDB manual page or in a behaviour measured
on a live server, and the grounding is declared as data in ``RULES`` so the test suite
can assert that each rule has a source, a violating input, and a compliant input. A
docstring claiming coverage is unfalsifiable; a table is not.

Usage:
    lint_migration.py FILE [FILE ...] [--json] [--mongo-version N] [--docs N]
    lint_migration.py --list-rules
    lint_migration.py --limitations
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import pathlib
import re
import sys

SEV_CRITICAL = "critical"
SEV_STANDARD = "standard"
SEV_HYGIENE = "hygiene"

# Majors in support as of 2026-08. 4.4 / 5.0 / 6.0 are EOL.
SUPPORTED_MIN, SUPPORTED_MAX = 7, 8

# collMod can change expireAfterSeconds in place from 5.1; below that a TTL change
# needed dropIndex + createIndex. Measured working on live 7.0.31 and 8.0.28.
TTL_COLLMOD_MIN_MAJOR = 6   # 5.1 rounded to the next whole major this skill supports

LARGE_COLLECTION_DOCS = 1_000_000


@dataclasses.dataclass(frozen=True)
class Rule:
    code: str
    severity: str
    title: str
    source: str


RULES: tuple[Rule, ...] = (
    Rule("MG001", SEV_CRITICAL, "unbounded updateMany/deleteMany with no batching",
         "measured: a single updateMany holds a write ticket for its whole duration"),
    Rule("MG002", SEV_CRITICAL, "ObjectId range rebuilt from its own hex is an empty range",
         "measured on 7.0/8.0: ObjectId(id.toHexString()).equals(id) is true"),
    Rule("MG003", SEV_CRITICAL, "ObjectId.valueOf() treated as a string",
         "measured on 7.0/8.0: valueOf() returns an object; .substring is undefined"),
    Rule("MG004", SEV_CRITICAL, "createIndex issued against a replica-set secondary",
         "measured on a live 3-member set: NotWritablePrimary"),
    Rule("MG005", SEV_STANDARD, "write concern not stated on a migration write",
         "manual: w:majority is not the driver default for every deployment"),
    Rule("MG006", SEV_STANDARD, "backfill resumes from max(_id) of migrated documents",
         "skill rule - resume point; pre-migrated high keys hide unfinished work"),
    Rule("MG007", SEV_STANDARD, "validationLevel strict applied before a backfill",
         "manual: strict validates every write against existing legacy documents"),
    Rule("MG008", SEV_STANDARD, "unique index created without a duplicate pre-check",
         "manual: createIndex fails on existing duplicates"),
    Rule("MG009", SEV_STANDARD, "TTL change by dropIndex + createIndex",
         "manual: collMod changes expireAfterSeconds in place from 5.1"),
    Rule("MG010", SEV_STANDARD, "$unset described or used as reversible",
         "skill rule - the previous value is gone unless captured first"),
    Rule("MG011", SEV_STANDARD, "db.collection.validate() as a routine migration step",
         "manual: validate() takes an exclusive collection lock"),
    Rule("MG012", SEV_HYGIENE, "rs.printReplicationInfo() used to read replication lag",
         "measured: it prints the oplog window of the connected member"),
    Rule("MG013", SEV_HYGIENE, "ticket metric read from the version-wrong path",
         "measured: wiredTiger.concurrentTransactions on 7.0, queues.execution on 8.0"),
    Rule("MG014", SEV_HYGIENE, "no throttle between backfill batches",
         "skill rule - an unthrottled loop is an unbounded write"),
    Rule("MG015", SEV_STANDARD, "index build on a large collection with no lag monitoring",
         "skill rule - a replicated build runs on every member; lag is the signal"),
    Rule("MG016", SEV_CRITICAL, "$gt keyset cursor on _id without a single-type guarantee",
         "measured: $gt type-brackets, so an int cursor never reaches ObjectIds"),
)

RULES_BY_CODE = {r.code: r for r in RULES}

# Properties this checker CANNOT establish, declared as data so the limitation travels
# with every result instead of living in a docstring nobody reads. A clean run means no
# rule fired -- it is not a safety verdict.
UNPROVABLE: tuple[str, ...] = (
    "that a backfill loop terminates or covers every document (run it against a "
    "restored snapshot; the live matrix does exactly this for the documented loop)",
    "collection sizes, index selectivity, or how long any operation will take",
    "anything about the live deployment: replica-set topology, shard keys, existing "
    "indexes, installed validators, or the server version actually in use",
    "whether a filter is genuinely idempotent, only whether one is present",
    "application-side behaviour such as dual-writes or read-path cutover",
)


@dataclasses.dataclass
class Finding:
    code: str
    severity: str
    line: int
    message: str
    snippet: str

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


def _strip_comments(js: str) -> str:
    """Remove // and /* */ comments without touching string literals.

    Comments matter here: several rules key on API calls, and a line explaining why a
    call is wrong must not count as making that call.
    """
    out, i, n = [], 0, len(js)
    while i < n:
        c = js[i]
        if c in "'\"`":
            j = i + 1
            while j < n and js[j] != c:
                j += 2 if js[j] == "\\" else 1
            out.append(js[i:min(j + 1, n)])
            i = j + 1
            continue
        if js.startswith("//", i):
            j = js.find("\n", i)
            i = n if j == -1 else j
            continue
        if js.startswith("/*", i):
            j = js.find("*/", i + 2)
            i = n if j == -1 else j + 2
            continue
        out.append(c)
        i += 1
    return "".join(out)




# What counts as an unconditional termination. `assert` is deliberately absent: mongosh's
# assert(true) is a no-op, and a reviewer used exactly that to clear the rule.
_ABORT_HEAD = re.compile(
    r"^\s*(?:throw\b"
    r"|quit\s*\("
    r"|return\s+(?:new\s+)?[Ee]rror\b"
    r"|return\s+errors\.New\b"
    r"|return\s+fmt\.Errorf\b"
    r"|panic\s*\()")


def _first_statement_aborts(body: str) -> bool:
    """Does the guarded branch terminate IMMEDIATELY and unconditionally?

    The bar is the FIRST statement, not "an abort appears somewhere in the body". Two
    bypasses made that necessary, both with a genuine `throw` inside the right branch:

        if (types.length !== 1) { if (!config.ok) throw ...; print("mixed"); }
        if (types.length !== 1) { assert(true); print("mixed"); }

    Neither terminates when the types are mixed, so the keyset ran anyway. Requiring the
    first statement rules out nested conditions, no-op assertions, and anything the
    reader would have to trace to be sure of.

    This rule has now been bypassed four times, each time by a cleverer arrangement of
    the same tokens. That is the nature of proving a semantic property syntactically, so
    the shape accepted here is deliberately narrow and anything outside it is NOT
    inferred safe -- pass --id-type instead.
    """
    inner = body.strip()
    if inner.startswith("{"):
        inner = inner[1:]
        if inner.rstrip().endswith("}"):
            inner = inner.rstrip()[:-1]
    return bool(_ABORT_HEAD.match(inner))


def _braced_or_single_statement(text: str) -> str | None:
    """The body an `if` guards: the balanced `{...}` block, or the single statement up
    to the first `;` when there are no braces.

    Returning the BODY rather than a fixed-size lookahead is what ties the abort to the
    condition. A window would re-admit the bypass this replaced.
    """
    i = 0
    while i < len(text) and text[i] in " \t\n\r":
        i += 1
    if i >= len(text):
        return None
    if text[i] == "{":
        depth, j = 0, i
        while j < len(text):
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
                if depth == 0:
                    return text[i:j + 1]
            j += 1
        return text[i:]          # unbalanced: treat the remainder as the body
    j = text.find(";", i)
    return text[i:j + 1] if j != -1 else text[i:i + 200]


class Linter:
    def __init__(self, mongo_version: int = SUPPORTED_MIN, docs: int | None = None,
                 id_type: str | None = None):
        self.mongo_version = mongo_version
        self.docs = docs
        # A declared single _id BSON type is the precondition the $gt keyset needs. It
        # cannot be inferred from the script, so it is either passed in (--id-type) or
        # asserted in the script itself (see ID_TYPE_PROVEN_RE).
        self.id_type = id_type
        self.findings: list[Finding] = []

    def _add(self, code: str, line: int, snippet: str, message: str,
             severity: str | None = None) -> None:
        rule = RULES_BY_CODE[code]
        self.findings.append(Finding(code, severity or rule.severity, line, message,
                                     snippet.strip()[:160]))

    # -- helpers ------------------------------------------------------------
    @staticmethod
    def _script_proves_single_id_type(code: str) -> bool:
        """Does the script establish the MG016 precondition, in a shape a reader can
        follow?

        The bar is a specific control flow, not two independent facts about the file.
        The previous version asked only whether `$type: "$_id"` appeared ANYWHERE and
        whether a `throw`/`assert`/`quit` appeared ANYWHERE, with no relationship
        required -- so a script that probed the types, printed them, and then threw
        because an unrelated config key was missing cleared the rule.

        Required, and structurally connected:
          1. a `$type: "$_id"` grouping, whose result is bound to a name;
          2. an `if` comparing THAT name's length against 1;
          3. an abort inside the branch THAT `if` guards.

        (3) used to be "an abort somewhere nearby", which a reviewer bypassed with two
        adjacent but unrelated statements: `if (types.length !== 1) print("mixed");`
        then `if (!config.ok) throw ...`. Both facts were present, neither checked
        anything.

        Anything this cannot recognise is NOT inferred as safe -- pass `--id-type`
        instead. Erring toward the finding costs a reviewer one flag; erring the other
        way ships a migration that silently skips documents.
        """
        m = re.search(
            r"(?:const|let|var)\s+(\w+)\s*(?::[^=]+)?=\s*[^;\n]*"
            r"\$type[\"']?\s*:\s*[\"']\$_id", code)
        if not m:
            # Go: `types` populated via cursor.All after a $type pipeline.
            m = re.search(r"\$type[\"']?\s*:\s*[\"']\$_id[^;]*?"
                          r"(?:All\s*\(\s*\w+\s*,\s*&?(\w+)\)|INTO\s+(\w+))",
                          code, re.S)
            if not m:
                return False
        var = next(g for g in m.groups() if g)
        start = m.start()

        # The abort must be INSIDE the branch the comparison guards. Requiring only
        # that both appear nearby was bypassable by putting them in different
        # statements -- `if (types.length !== 1) print("mixed");` followed by
        # `if (!config.ok) throw ...` cleared the rule while checking nothing.
        #
        # Two accepted shapes, both anchored on the SAME `if`:
        #     if (<var>.length !== 1) { ... throw|quit|assert ... }
        #     if (<var>.length !== 1) throw ...            // single statement
        #     if len(<var>) != 1 { ... return ...Error... }   // Go
        #
        # Anything else is not inferred as safe. This is a syntactic reader without an
        # AST, so where it cannot see the shape it says so and the caller passes
        # --id-type. Erring toward the finding costs a reviewer one flag; erring the
        # other way ships a migration that silently skips documents.
        window = code[start:start + 900]
        v = re.escape(var)
        cond = (rf"(?:{v}\s*\.length|\blen\s*\(\s*{v}\s*\))\s*"
                rf"(?:!==?|<>|>|>=)\s*1\b")
        abort = (r"\bthrow\b|\bquit\s*\(|\bassert\b"
                 r"|\breturn\s+(?:new\s+)?[Ee]rror"
                 r"|\berrors\.New\b|\bfmt\.Errorf\b")

        for m2 in re.finditer(rf"\bif\s*\(?\s*{cond}\s*\)?", window):
            rest = window[m2.end():]
            body = _braced_or_single_statement(rest)
            if body is not None and _first_statement_aborts(body):
                return True
        return False

    @staticmethod
    def _lineno(text: str, pos: int) -> int:
        return text[:pos].count("\n") + 1

    def _size_note(self) -> str:
        if self.docs is None:
            return ""
        return f" Declared collection size {self.docs:,} documents."

    def _large(self) -> bool:
        return self.docs is not None and self.docs >= LARGE_COLLECTION_DOCS

    # -- main ---------------------------------------------------------------
    def lint(self, js: str) -> list[Finding]:
        self.findings = []
        code = _strip_comments(js)
        L = lambda m: self._lineno(code, m.start())        # noqa: E731

        # MG003 -- ObjectId.valueOf() used as a string.
        for m in re.finditer(r"\.valueOf\(\)\s*\.\s*(substring|substr|slice|charAt|padStart)",
                             code):
            self._add("MG003", L(m), m.group(0),
                      "ObjectId.prototype.valueOf() returns an object, not a hex string "
                      "-- measured on 7.0 and 8.0. This throws "
                      "`TypeError: ... .substring is not a function` on the first "
                      "iteration, so the loop never runs. Use .toHexString() if you "
                      "genuinely need the hex, but see MG002 first.")

        # MG002 -- a range whose two bounds are the same ObjectId.
        for m in re.finditer(
                r"\$gt\s*:\s*(\w+)\s*,\s*\$lte\s*:\s*ObjectId\s*\(\s*\1\b|"
                r"\$gte\s*:\s*(\w+)\s*,\s*\$lt\s*:\s*ObjectId\s*\(\s*\2\b", code):
            self._add("MG002", L(m), m.group(0),
                      "both bounds resolve to the SAME ObjectId, so this range matches "
                      "nothing: ObjectId(id.toHexString()).equals(id) is true (measured "
                      "on 7.0/8.0). A loop built on it advances its cursor and updates "
                      "zero documents while reporting success. Select the batch's keys "
                      "first and take the cursor from the documents you actually "
                      "processed.")

        # MG004 -- writing to a secondary. Keyed on actually TARGETING one, not on the
        # word appearing: rs.printSecondaryReplicationInfo() is the correct way to read
        # lag and must not be read as "this connects to a secondary".
        targets_secondary = re.search(
            r"""setReadPref\s*\(\s*["']secondary"""
            r"""|readPreference\s*[:=]\s*["']secondary"""
            r"""|directConnection\s*[:=]\s*true"""
            r"""|connect\s*\([^)]*secondary""", code, re.I)
        if targets_secondary and re.search(r"createIndex\s*\(", code):
            for m in re.finditer(r"createIndex\s*\(", code):
                self._add("MG004", L(m), "createIndex on a secondary",
                          "a replica-set secondary rejects writes with "
                          "NotWritablePrimary (measured on a live 3-member set), so a "
                          "'connect to the secondary and createIndex' procedure cannot "
                          "run. Issue the build on the PRIMARY and let it replicate; a "
                          "real rolling build first removes the member from the set.")
                break

        # MG006 -- resume point taken from the migrated maximum.
        for m in re.finditer(
                r"find\s*\(\s*\{[^}]*(_migrated|migrated|new_field)[^}]*\}\s*\)"
                r"\s*(\.\w+\([^)]*\)\s*)*\.sort\s*\(\s*\{\s*_id\s*:\s*-1", code):
            self._add("MG006", L(m), m.group(0),
                      "resuming from the highest already-migrated _id skips every "
                      "unprocessed document below a pre-migrated high key, and the loop "
                      "still exits cleanly. Re-run from the start: the batch predicate "
                      "({field: {$exists: false}}) is the resume point.")

        # MG009 -- TTL change by drop + recreate.
        if (self.mongo_version >= TTL_COLLMOD_MIN_MAJOR
                and re.search(r"dropIndex\s*\(", code)
                and re.search(r"expireAfterSeconds", code)):
            m = re.search(r"dropIndex\s*\(", code)
            self._add("MG009", L(m), m.group(0),
                      f"changing a TTL by dropIndex + createIndex on MongoDB "
                      f"{self.mongo_version} is an avoidable full index build: collMod "
                      "changes expireAfterSeconds in place from 5.1 (verified on live "
                      "7.0 and 8.0). Use "
                      "db.runCommand({collMod: <coll>, index: {keyPattern: ..., "
                      "expireAfterSeconds: N}}).")

        # MG007 -- strict validator with no prior moderate stage.
        if re.search(r"validationLevel\s*:\s*[\"']strict[\"']", code) \
                and not re.search(r"validationLevel\s*:\s*[\"']moderate[\"']", code):
            m = re.search(r"validationLevel\s*:\s*[\"']strict[\"']", code)
            self._add("MG007", L(m), m.group(0),
                      "applying a strict validator before the data complies rejects "
                      "writes to every legacy document. Stage it: moderate -> backfill "
                      "-> verify zero non-compliant -> strict. Note what moderate "
                      "actually exempts (measured): only updates to documents that "
                      "ALREADY fail validation; inserts and updates to compliant "
                      "documents are still validated.")

        # MG008 -- unique index with no duplicate pre-check.
        if re.search(r"createIndex\s*\([^)]*\)\s*,?\s*\{[^}]*unique\s*:\s*true", code) \
                or re.search(r"unique\s*:\s*true", code):
            if not re.search(r"\$group|aggregate\s*\(|countDocuments\s*\(", code):
                m = re.search(r"unique\s*:\s*true", code)
                self._add("MG008", L(m), m.group(0),
                          "creating a unique index fails outright if duplicates exist. "
                          "Pre-check with an aggregation grouping on the key and "
                          "matching count > 1, and resolve them first.")

        # MG011 -- validate() as a routine step.
        for m in re.finditer(r"\.validate\s*\(", code):
            self._add("MG011", L(m), m.group(0),
                      "db.collection.validate() takes an EXCLUSIVE lock on the "
                      "collection and can run for a long time on a large one. It checks "
                      "for storage corruption, not for whether a migration finished. To "
                      "confirm a backfill, count the documents still matching its "
                      "predicate; if you do need validate(), run it on a secondary.")

        # MG012 -- wrong command for replication lag.
        for m in re.finditer(r"rs\.printReplicationInfo\s*\(", code):
            self._add("MG012", L(m), m.group(0),
                      "rs.printReplicationInfo() prints the oplog window of the member "
                      "you are connected to -- how much history is retained, not how far "
                      "behind anyone is. Use rs.printSecondaryReplicationInfo(), or read "
                      "optimeDate per member from rs.status().")

        # MG013 -- ticket metric path that is wrong for the target version.
        wt = re.search(r"wiredTiger\s*\.\s*concurrentTransactions", code)
        qe = re.search(r"queues\s*\.\s*execution", code)
        if wt and self.mongo_version >= 8 and not qe:
            self._add("MG013", L(wt), wt.group(0),
                      "on MongoDB 8 the ticket metric lives at "
                      "serverStatus().queues.execution; wiredTiger.concurrentTransactions "
                      "is absent (measured), so this reads undefined -- which looks "
                      "exactly like 'no pressure'.")
        if qe and self.mongo_version < 8 and not wt:
            self._add("MG013", L(qe), qe.group(0),
                      "on MongoDB 7 the ticket metric lives at "
                      "serverStatus().wiredTiger.concurrentTransactions; "
                      "queues.execution is absent (measured), so this reads undefined.")

        # MG015 -- an index build on a large collection with nothing watching lag.
        # The build itself is correct (replicated is the default); what is missing is
        # the observation that tells you whether secondaries are keeping up.
        if self._large() and re.search(r"createIndex\s*\(", code) \
                and not re.search(r"printSecondaryReplicationInfo|currentOp\s*\(|"
                                  r"rs\.status\s*\(", code):
            m = re.search(r"createIndex\s*\(", code)
            self._add("MG015", self._lineno(code, m.start()), m.group(0),
                      "a replicated index build runs on every data-bearing member, so "
                      "secondaries can fall behind on a collection this size, with "
                      "nothing here watching for it." + self._size_note()
                      + " Add rs.printSecondaryReplicationInfo() (NOT "
                      "rs.printReplicationInfo(), which shows the connected member's "
                      "oplog window) and db.currentOp() for build progress.")

        # MG016 -- a keyset cursor over _id. Correct ONLY when every _id in the
        # collection is the same BSON type: comparison operators type-bracket, so once
        # the cursor holds an integer, {$gt: <int>} stops matching ObjectIds entirely.
        # Measured on 8.0: 30 ints + 30 ObjectIds, batch 25 -> 30 documents stranded.
        #
        # The rule is "no single-type guarantee", not "uses $gt", so a script that
        # establishes the guarantee must clear it. Two auditable ways, both requiring
        # something a reader can check -- never a bare comment:
        #   1. --id-type <bsonType> on the command line;
        #   2. the script itself proves it, by grouping on {$type: "$_id"} AND failing
        #      when more than one type comes back.
        if re.search(r"_id\s*[:=]\s*\{\s*\$gt\s*:", code) or \
                re.search(r"\{\s*\$gt\s*:\s*lastId", code):
            if not (self.id_type or self._script_proves_single_id_type(code)):
                m = re.search(r"\$gt", code)
                self._add("MG016", self._lineno(code, m.start()), m.group(0),
                          "a $gt cursor over _id silently strands every _id whose BSON "
                          "type differs from the cursor's: comparison operators "
                          "type-bracket, so $gt on an integer never reaches ObjectIds "
                          "even though they sort after every integer. Either drop the "
                          "cursor (re-query the predicate each batch -- correct for any "
                          "_id type), or establish the precondition: pass --id-type, or "
                          "have the script group on {$type: '$_id'} and abort when it "
                          "sees more than one.")

        self._check_bulk_writes(code)
        self.findings.sort(key=lambda f: (f.line, f.code))
        return self.findings

    def _check_bulk_writes(self, code: str) -> None:
        """MG001 / MG005 / MG014 -- properties of the write loop itself."""
        writes = list(re.finditer(r"\.(updateMany|deleteMany)\s*\(", code))
        if not writes:
            return

        batched = bool(re.search(r"\$in\s*:\s*\w+", code)
                       or re.search(r"\.limit\s*\(", code)
                       or re.search(r"bulkWrite\s*\(", code))
        looped = bool(re.search(r"\b(while|for)\s*\(", code))

        for m in writes:
            line = self._lineno(code, m.start())
            if not (batched and looped):
                self._add("MG001", line, m.group(0),
                          f"{m.group(1)}() with no batching loop runs as one operation: "
                          "it holds a write ticket for its whole duration and the "
                          "oplog entry set grows without bound. Select a bounded batch "
                          "of _ids, update those, and advance."
                          + self._size_note(),
                          severity=SEV_CRITICAL if self._large() else None)

            if not re.search(r"writeConcern\s*:", code):
                self._add("MG005", line, m.group(0),
                          "no writeConcern stated. A migration write should say what "
                          "durability it requires -- w:'majority' so the change survives "
                          "a primary failover, or w:1 with an explicit note that the "
                          "backfill is re-runnable.")

        if looped and not re.search(r"\bsleep\s*\(|setTimeout|time\.Sleep", code):
            self._add("MG014", self._lineno(code, writes[0].start()), "batch loop",
                      "no pause between batches. A tight loop is an unbounded write by "
                      "another name: it keeps the ticket pool saturated for the whole "
                      "run. Sleep between batches and tune from measured queue length.")


def render_text(path: str, findings: list[Finding]) -> str:
    if not findings:
        return (f"{path}: 0 findings — no rule in this checker fired.\n"
                f"  NOT a proof of safety: see `--limitations` for what it cannot decide.")
    lines = [f"{path}: {len(findings)} finding(s)"]
    for f in findings:
        lines.append(f"  [{f.severity.upper():8}] {f.code} line {f.line}: {f.message}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*", type=pathlib.Path)
    ap.add_argument("--json", action="store_true", help="emit findings as JSON")
    ap.add_argument("--mongo-version", type=int, default=SUPPORTED_MIN,
                    help=f"target major (default {SUPPORTED_MIN}, the oldest supported)")
    ap.add_argument("--docs", type=int, default=None,
                    help=f"known document count; escalates unbounded writes to critical "
                         f"at >= {LARGE_COLLECTION_DOCS:,}. Never de-escalates.")
    ap.add_argument("--id-type", metavar="TYPE",
                    help="declare that every _id in the target collection is this single "
                         "BSON type (objectId, int, string, ...). Clears MG016, because "
                         "the $gt keyset is correct once that holds. Verify it first: "
                         "db.c.aggregate([{$group: {_id: {$type: '$_id'}}}])")
    ap.add_argument("--list-rules", action="store_true")
    ap.add_argument("--limitations", action="store_true",
                    help="print what this checker cannot decide, and exit")
    args = ap.parse_args(argv)

    if args.limitations:
        print("This checker reads the JavaScript you hand it. It cannot establish:")
        for item in UNPROVABLE:
            print(f"  - {item}")
        print("\nA clean result means no rule fired, not that the migration is safe.")
        return 0

    if args.list_rules:
        for r in RULES:
            print(f"{r.code}\t{r.severity}\t{r.title}\t[{r.source}]")
        return 0

    if not args.files:
        ap.error("no input files (use --list-rules to inspect the registry)")

    if not SUPPORTED_MIN <= args.mongo_version <= SUPPORTED_MAX:
        print(f"warning: MongoDB {args.mongo_version} is outside the supported range "
              f"{SUPPORTED_MIN}-{SUPPORTED_MAX}; version-gated rules may be wrong",
              file=sys.stderr)

    results, worst = {}, 0
    for path in args.files:
        if not path.exists():
            print(f"{path}: ERROR file not found", file=sys.stderr)
            return 2
        findings = Linter(args.mongo_version, args.docs, args.id_type).lint(
            path.read_text(encoding="utf-8"))
        results[str(path)] = [f.to_dict() for f in findings]
        if findings:
            worst = 1
        if not args.json:
            print(render_text(str(path), findings))

    if args.json:
        print(json.dumps({"findings": results, "unprovable": list(UNPROVABLE)}, indent=2))
    return worst


if __name__ == "__main__":
    sys.exit(main())
