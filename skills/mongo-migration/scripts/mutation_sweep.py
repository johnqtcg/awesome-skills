#!/usr/bin/env python3
"""Mutation sweep for the mongo-migration skill.

Each mutation breaks one behaviour on purpose. The test suite must then FAIL --
that is a KILL. A mutation the suite still passes is a SURVIVOR, meaning no
assertion actually depends on the behaviour it broke.

Two failure modes this script is built to avoid:

1. **Stale anchors.** If a mutation's anchor text no longer exists in the file,
   the substitution is a silent no-op and the mutation "survives" for a reason
   that has nothing to do with test coverage. Every anchor is verified to exist
   (and its occurrence count recorded) before the sweep runs; a missing anchor is
   a hard error, not a survivor.
2. **Partial replacement.** Substitutions replace ALL occurrences. Replacing only
   the first can leave a working copy of the mutated logic behind, which makes a
   genuine assertion look vacuous.

Usage:
    mutation_sweep.py            # run the sweep
    mutation_sweep.py --verify   # only check anchors resolve, do not run tests
    mutation_sweep.py --list     # print the mutation registry
"""

from __future__ import annotations

import argparse
import atexit
import dataclasses
import os
import pathlib
import shutil
import stat
import subprocess
import sys
import tempfile

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent
SKILL_DIR = SCRIPTS_DIR.parent
TESTS_DIR = SCRIPTS_DIR / "tests"

LINTER = SCRIPTS_DIR / "lint_migration.py"
RUNNER = SCRIPTS_DIR / "run_regression.sh"
MATRIX = SKILL_DIR / "references" / "mongo-ddl-lock-matrix.md"
LARGE = SKILL_DIR / "references" / "large-collection-migration.md"
ANTI = SKILL_DIR / "references" / "migration-anti-examples.md"
SKILL_MD = SKILL_DIR / "SKILL.md"
COVERAGE = TESTS_DIR / "COVERAGE.md"



@dataclasses.dataclass(frozen=True)
class Mutation:
    mid: str
    target: pathlib.Path
    anchor: str
    replacement: str
    breaks: str  # what behaviour this destroys


MUTATIONS: tuple[Mutation, ...] = (
    # ---- the two defects that survived 97 green tests ------------------------
    Mutation("M01", LINTER,
             '(substring|substr|slice|charAt|padStart)",',
             '(NEVERMATCHESZZZ)",',
             "MG003 stops reporting .valueOf().substring -- the TypeError that made the "
             "shipped backfill loop unrunnable"),
    Mutation("M02", LINTER,
             '                r"\\$gt\\s*:\\s*(\\w+)\\s*,\\s*\\$lte\\s*:\\s*ObjectId\\s*\\(\\s*\\1\\b|"',
             '                r"NEVERMATCHESZZZ|"',
             "MG002 stops reporting the self-referential ObjectId range that migrates "
             "zero documents while reporting success"),

    # ---- write-loop shape ----------------------------------------------------
    Mutation("M03", LINTER,
             "            if not (batched and looped):",
             "            if False:",
             "MG001 never reports an unbounded updateMany"),
    Mutation("M04", LINTER,
             '            if not re.search(r"writeConcern\\s*:", code):',
             "            if False:",
             "MG005 never reports a migration write with no stated write concern"),
    Mutation("M05", LINTER,
             '        if looped and not re.search(r"\\bsleep\\s*\\(|setTimeout|time\\.Sleep", code):',
             "        if False:",
             "MG014 never reports an unthrottled batch loop"),

    # ---- replica-set and version-gated rules ---------------------------------
    Mutation("M06", LINTER,
             "        if targets_secondary and re.search(r\"createIndex\\s*\\(\", code):",
             "        if False:",
             "MG004 never reports createIndex aimed at a secondary, which the server "
             "rejects with NotWritablePrimary"),
    Mutation("M07", LINTER,
             "        if wt and self.mongo_version >= 8 and not qe:",
             "        if False:",
             "MG013 never reports the 7.0 ticket path used against an 8.0 target"),
    Mutation("M08", LINTER,
             "TTL_COLLMOD_MIN_MAJOR = 6",
             "TTL_COLLMOD_MIN_MAJOR = 99",
             "MG009 never fires, so drop-and-recreate for a TTL change looks correct on "
             "every supported version"),
    Mutation("M09", LINTER,
             "        if self._large() and re.search(r\"createIndex\\s*\\(\", code) \\",
             "        if False and re.search(r\"createIndex\\s*\\(\", code) \\",
             "MG015 never reports an index build on a large collection with no lag "
             "monitoring"),

    # ---- resume point and validator ------------------------------------------
    Mutation("M10", LINTER,
             '                r"\\s*(\\.\\w+\\([^)]*\\)\\s*)*\\.sort\\s*\\(\\s*\\{\\s*_id\\s*:\\s*-1", code):',
             '                r"NEVERMATCHESZZZ", code):',
             "MG006 never reports a resume point taken from max(_id) of the migrated set"),
    Mutation("M11", LINTER,
             '            self._add("MG007", L(m), m.group(0),',
             '            self._add("MG001", L(m), m.group(0),',
             "MG007 never reports a strict validator applied before the data complies"),
    Mutation("M12", LINTER,
             '            if not re.search(r"\\$group|aggregate\\s*\\(|countDocuments\\s*\\(", code):',
             "            if False:",
             "MG008 never reports a unique index built with no duplicate pre-check"),

    # ---- honesty of the output ------------------------------------------------
    Mutation("M13", LINTER,
             'f"  NOT a proof of safety: see `--limitations` for what it cannot decide.")',
             'f"  All clear.")',
             "a clean result reads as a safety verdict again"),
    Mutation("M14", LINTER,
             'print(json.dumps({"findings": results, "unprovable": list(UNPROVABLE)}, indent=2))',
             "print(json.dumps(results, indent=2))",
             "the JSON output drops the limitations, so a CI gate consuming it never "
             "sees them"),
    Mutation("M15", LINTER,
             '    Rule("MG002", SEV_CRITICAL,',
             '    Rule("MG002", SEV_HYGIENE,',
             "the empty-range defect is downgraded from critical to hygiene"),

    # ---- comment handling -----------------------------------------------------
    Mutation("M16", LINTER,
             '        if js.startswith("//", i):',
             "        if False:",
             "comments count as code, so a line explaining why a call is wrong is read "
             "as making that call"),

    # ---- MG016: the type-bracketing trap and its precondition ------------------
    Mutation("M23", LINTER,
             '        if re.search(r"_id\\s*[:=]\\s*\\{\\s*\\$gt\\s*:", code) or \\',
             "        if False or \\",
             "MG016 never reports a $gt keyset over _id, so a loop that strands whole "
             "BSON type classes reads as clean"),
    Mutation("M24", LINTER,
             "            if not (self.id_type or self._script_proves_single_id_type(code)):",
             "            if False:",
             "MG016 is suppressed for every input, precondition or not"),
    # M25 targeted the original two-fact MG016 proof (`asks and acts`), which a reviewer
    # bypassed with an unrelated throw. That implementation is gone; M29-M31 mutate the
    # control-flow shape that replaced it.
    Mutation("M26", SKILL_MD,
             "**`_id` BSON type uniformity**",
             "**_id sampling**",
             "Gate 1 stops asking whether _id has a single BSON type, the precondition "
             "the keyset optimisation depends on"),

    # ---- rules a coverage assertion found had no mutation at all ---------------
    Mutation("M27", LINTER,
             '        for m in re.finditer(r"\\.validate\\s*\\(", code):',
             '        for m in re.finditer(r"NEVERMATCHESZZZ", code):',
             "MG011 never reports db.collection.validate(), which takes an exclusive "
             "collection lock, as a routine migration step"),
    Mutation("M28", LINTER,
             '        for m in re.finditer(r"rs\\.printReplicationInfo\\s*\\(", code):',
             '        for m in re.finditer(r"NEVERMATCHESZZZ", code):',
             "MG012 never reports rs.printReplicationInfo() used to read lag"),

    # M29 targeted `re.search(abort, body)` -- the "an abort appears somewhere in
    # the branch" test, which reviewers bypassed with a nested conditional throw
    # and with assert(true). M32-M34 mutate the first-statement rule that replaced it.
    # Anchored on a backslash-free line on purpose: the `if` regex above it is dense
    # with escapes, and every attempt to quote it through a generator produced a
    # different string than the source held. Mutating the slice that ties the body to
    # its guard tests the same property -- that the abort must sit inside the branch the
    # comparison opened, not merely somewhere in the window.
    Mutation("M30", LINTER,
             "            rest = window[m2.end():]",
             "            rest = window",
             "MG016 stops tying the abort to the branch its comparison guards, so an "
             "abort on an unrelated condition elsewhere in the window clears the rule"),
    Mutation("M31", LINTER,
             "        window = code[start:start + 900]",
             "        window = code",
             "MG016 accepts a proof anywhere in the file, so an unrelated abort far from "
             "the type probe clears the rule"),

    Mutation("M32", LINTER,
             "            if body is not None and _first_statement_aborts(body):",
             "            if body is not None:",
             "MG016 stops requiring the guarded branch to terminate at all"),
    Mutation("M33", LINTER,
             '    r"^\\s*(?:throw\\b"',
             '    r"(?:throw\\b"',
             "the abort no longer has to be the FIRST statement -- dropping the "
             "anchor lets a nested conditional throw or a log-then-throw clear MG016"),
    Mutation("M34", LINTER,
             "    r\"^\\s*(?:throw\\b\"",
             "    r\"^\\s*(?:assert\\b|throw\\b\"",
             "assert re-enters the accepted set, so assert(true) clears MG016"),

    # ---- documentation drift ---------------------------------------------------
    # M17 used to pin "cursor comes from the batch you just processed" -- which was the
    # right rule when a cursor was mandatory, and became the WRONG default once the
    # cursorless loop replaced it. A mutation that pins superseded wording keeps that
    # wording alive. It now pins the rule that actually holds.
    Mutation("M17", LARGE,
             "**There is no cursor by default.**",
             "**The cursor comes from the batch you just processed.**",
             "the default reverts to a cursor-carrying loop, which type-brackets and "
             "strands whole BSON type classes"),
    Mutation("M18", LARGE,
             '"Replicated build" and "rolling build" are different things',
             "A replicated build is a rolling build",
             "the conflation that sent readers to a procedure they do not need returns"),
    Mutation("M19", LARGE,
             "NotWritablePrimary",
             "NotAProblem",
             "the measured reason the old rolling procedure cannot run is lost"),
    Mutation("M20", SKILL_MD,
             "`collMod` changes `expireAfterSeconds` in place from MongoDB 5.1",
             "Changing a TTL always requires dropIndex + createIndex",
             "the TTL correction reverts to the claim that is false on every supported "
             "version"),
    Mutation("M21", SKILL_MD,
             "only an update to a document that **already failed** validation is exempt",
             "only new writes are validated",
             "the moderate-validation semantics revert to the wrong summary"),
    Mutation("M22", MATRIX,
             "The pool is not a fixed 128",
             "The pool is a fixed 128",
             "the ticket-pool claim reverts to a constant the server no longer uses"),
)


# The sweep mutates source files. Doing that in the real worktree makes every other
# reader of the tree -- a concurrent regression run, an editor, a second sweep -- observe
# deliberately broken code, and two sweeps overlapping corrupt each other's restore. So
# the whole sweep runs against a private copy and the real tree is never written to.
_SANDBOX: pathlib.Path | None = None


def sandbox_root() -> pathlib.Path:
    """Return (creating on first use) a private copy of the skill directory.

    Do not run the sweep while anything else writes to the tree. copytree takes a
    non-atomic snapshot, so a concurrent edit lands as a half-copied state and a
    mutation can then report SURVIVED for a reason unrelated to test coverage -- which
    happened once here, alongside a `update_coverage_counts.py` run.
    """
    global _SANDBOX
    if _SANDBOX is None:
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="pgmig-sweep-",
                                            dir=os.environ.get("TMPDIR") or None))
        dest = tmp / SKILL_DIR.name
        shutil.copytree(SKILL_DIR, dest, ignore=shutil.ignore_patterns(
            "__pycache__", ".pytest_cache", ".git", "*.pyc"))
        # copytree preserves mode, so a read-only source file would make the sandbox
        # unwritable and the sweep would fail on the copy for a reason that has nothing
        # to do with the mutation. The sandbox is meant to be mutable; the original is
        # the thing being protected.
        for f in dest.rglob("*"):
            if f.is_file():
                f.chmod(f.stat().st_mode | stat.S_IWUSR)
        atexit.register(shutil.rmtree, tmp, True)
        _SANDBOX = dest
    return _SANDBOX


def sandboxed(target: pathlib.Path) -> pathlib.Path:
    """Map a real path to its counterpart inside the sandbox copy."""
    return sandbox_root() / target.relative_to(SKILL_DIR)


def run_tests(timeout: int = 300) -> bool:
    """Return True if the suite PASSES, run inside the sandbox copy.

    The live-server matrix is excluded: no mutation here targets MongoDB's own
    behaviour, it needs containers the sweep must not depend on, and at ~60s per run it
    would dominate the wall-clock of the whole sweep. Its job -- checking our claims
    against a real server -- is not something a mutation can test.
    """
    root = sandbox_root()
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", str(root / "scripts" / "tests"),
         "-q", "-x", "--no-header", "-p", "no:cacheprovider",
         "--ignore", str(root / "scripts" / "tests" / "test_mongo_server_matrix.py")],
        cwd=str(root), capture_output=True, text=True, timeout=timeout,
    )
    return proc.returncode == 0


def verify_anchors() -> list[str]:
    """Every anchor must exist. A stale anchor is an error, never a survivor."""
    problems = []
    for m in MUTATIONS:
        if not m.target.exists():
            problems.append(f"{m.mid}: target missing: {m.target}")
            continue
        text = m.target.read_text(encoding="utf-8")
        count = text.count(m.anchor)
        if count == 0:
            problems.append(
                f"{m.mid}: anchor not found in {m.target.name} -- the mutation would "
                f"be a silent no-op. Anchor: {m.anchor[:80]!r}"
            )
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--verify", action="store_true",
                    help="only check that anchors resolve; do not run the sweep")
    ap.add_argument("--list", action="store_true", help="print the mutation registry")
    args = ap.parse_args(argv)

    if args.list:
        for m in MUTATIONS:
            print(f"{m.mid}\t{m.target.name}\t{m.breaks}")
        return 0

    problems = verify_anchors()
    if problems:
        print("ANCHOR VERIFICATION FAILED — refusing to run the sweep:", file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        print("\nFix the anchors (the source has changed) and re-run.", file=sys.stderr)
        return 2
    print(f"anchors OK ({len(MUTATIONS)} mutations)")
    if args.verify:
        return 0

    print("baseline: running suite unmutated...")
    if not run_tests():
        print("BASELINE FAILS — fix the suite before sweeping.", file=sys.stderr)
        return 2
    print("baseline PASSES\n")

    print(f"sweeping in a private copy at {sandbox_root()}\n")
    killed, survived = [], []
    for m in MUTATIONS:
        target = sandboxed(m.target)
        original = target.read_text(encoding="utf-8")
        # Replace ALL occurrences: a partial replacement can leave working logic behind.
        mutated = original.replace(m.anchor, m.replacement)
        assert mutated != original, f"{m.mid}: replacement produced no change"
        try:
            target.write_text(mutated, encoding="utf-8")
            passed = run_tests()
        finally:
            target.write_text(original, encoding="utf-8")

        if passed:
            survived.append(m)
            print(f"  SURVIVED  {m.mid}  {m.breaks}")
        else:
            killed.append(m)
            print(f"  killed    {m.mid}  {m.breaks}")

    total = len(MUTATIONS)
    print(f"\n{len(killed)}/{total} killed, {len(survived)} survived")
    if survived:
        print("\nSurvivors — no assertion depends on these behaviours:")
        for m in survived:
            print(f"  {m.mid} ({m.target.name}): {m.breaks}")
        return 1
    print("All mutations killed: every mutated behaviour is covered by an assertion.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
