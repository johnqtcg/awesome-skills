"""Drift guards for PostgreSQL facts verified against the official documentation.

Each entry pins one behaviour that was WRONG in this skill before 2026-08 and was
corrected against the PostgreSQL 17 documentation source (``doc/src/sgml``). The
`source` field records where the claim comes from so a reviewer can re-verify
rather than trust this file.

Design notes:

* Checks are **per-subject**: each one names the specific document and the specific
  claim. "Does the word ShareRowExclusive appear anywhere" would be satisfied by an
  unrelated mention, so every check pins a distinguishing phrase.
* `forbid` patterns target the **previous wrong phrasing** specifically, never a
  substring that the correcting explanation would also contain -- otherwise the
  sentence explaining why something was wrong would trip the guard.
"""

from __future__ import annotations

import dataclasses
import pathlib
import re

import pytest

SKILL_DIR = pathlib.Path(__file__).resolve().parents[2]
SKILL_MD = SKILL_DIR / "SKILL.md"
MATRIX = SKILL_DIR / "references" / "pg-ddl-lock-matrix.md"
LARGE = SKILL_DIR / "references" / "large-table-migration.md"
ANTI = SKILL_DIR / "references" / "migration-anti-examples.md"
REPL = SKILL_DIR / "references" / "replication-rls-extensions.md"


@dataclasses.dataclass(frozen=True)
class Fact:
    fid: str
    doc: pathlib.Path
    require: str          # regex that MUST match (the corrected claim)
    forbid: str | None    # regex that must NOT match (the previous wrong claim)
    source: str
    why: str


FACTS: tuple[Fact, ...] = (
    Fact("F04-fk-lock", MATRIX,
         r"ADD FOREIGN KEY.*ShareRowExclusive",
         r"ADD CONSTRAINT \(FK/CHECK\)",
         "alter_table.sgml - ADD table_constraint",
         "FK takes only SHARE ROW EXCLUSIVE; merging FK and CHECK into one "
         "AccessExclusive row was the original factual error."),

    Fact("F04-fk-referenced-table", MATRIX,
         r"SHARE ROW EXCLUSIVE lock on the\s+\*{0,2}referenced\*{0,2} table",
         None,
         "alter_table.sgml - ADD table_constraint",
         "ADD FOREIGN KEY also locks the referenced table for writes."),

    Fact("F05-multi-subcommand-escalation", MATRIX,
         r"strictest one required by any subcommand",
         None,
         "alter_table.sgml - Description",
         "A multi-subcommand ALTER TABLE escalates to the strictest lock, which "
         "defeats the NOT VALID pattern when batched."),

    Fact("F05-escalation-in-skill", SKILL_MD,
         r"strictest",
         None,
         "alter_table.sgml - Description",
         "The escalation rule must appear in the skill body, not only the reference."),

    Fact("F06-validate-referenced-rowshare", MATRIX,
         r"VALIDATE CONSTRAINT \(FK\).*RowShare",
         None,
         "alter_table.sgml - Notes",
         "Validating an FK also needs ROW SHARE on the referenced table."),

    Fact("F07-reindex-table-lock", MATRIX,
         r"REINDEX.*ShareLock on table",
         r"\|\s*REINDEX\s*\|\s*AccessExclusiveLock",
         "reindex.sgml - Notes",
         "REINDEX takes ShareLock on the parent table, not AccessExclusive."),

    Fact("F07-reindex-planner-effect", MATRIX,
         # tolerate the blockquote line-wrap: "... REINDEX blocks\n> virtually any queries"
         r"blocks[\s>]*virtually any quer",
         None,
         "reindex.sgml - Notes",
         "The planner locks every index, so reads block in practice. Both halves "
         "of this fact are load-bearing; dropping either one is a regression."),

    Fact("F08-identity-overriding", LARGE,
         r"OVERRIDING SYSTEM VALUE",
         r"id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,\n  user_id",
         "insert.sgml - OVERRIDING SYSTEM VALUE",
         "Inserting an explicit value into a GENERATED ALWAYS identity column "
         "without OVERRIDING SYSTEM VALUE is an error."),

    Fact("F09-volatile-default", SKILL_MD,
         r"volatil",
         None,
         "alter_table.sgml - Notes",
         "The rewrite gate is the default's volatility, not the mere presence of "
         "a DEFAULT."),

    Fact("F10-int-to-bigint-rewrites", MATRIX,
         r"`int`\s*→\s*`bigint`.*REWRITES|REWRITES.*int.*bigint",
         r"int → bigint on some versions",
         "alter_table.sgml - Notes",
         "int4 is not binary coercible to int8, so the widening rewrites. The old "
         "text listed it as a no-rewrite case."),

    Fact("F11-fillfactor-lock", MATRIX,
         r"FILLFACTOR|fillfactor.*ShareUpdateExclusive",
         None,
         "alter_table.sgml - SET ( ... )",
         "Storage-parameter changes take ShareUpdateExclusive, not AccessExclusive."),

    Fact("F12-attach-partition-parent", MATRIX,
         r"ShareUpdateExclusive on parent",
         None,
         "alter_table.sgml - ATTACH PARTITION",
         "ATTACH PARTITION leaves the parent readable and writable."),

    # Measured on live 14.23 / 15.18 / 16.14 / 17.10 / 18.4: 14-17 raise "cannot add
    # NOT VALID foreign key on partitioned table"; 18 accepts it. The claim was
    # written as an absolute prohibition until a server was actually asked, so the
    # guard now pins the VERSION GATE, not the prohibition.
    Fact("F13-partitioned-fk-not-valid", MATRIX,
         r"PG 18 lifts this",
         # The superseded decision-tree wording, which stated the rule with no version
         # qualifier at all. Deliberately NOT the phrase "may not be declared NOT
         # VALID" -- that phrase still appears, correctly, inside the PG 14-17 clause,
         # so forbidding it would fire on the corrected text.
         r"\(unavailable on partitioned tables\)",
         "alter_table.sgml - ADD table_constraint; verified on live 14-18",
         "The two-step NOT VALID pattern is unavailable on partitioned tables only up "
         "to PG 17. Stating it unconditionally makes the skill reject valid PG 18 SQL."),

    Fact("F13b-partitioned-fk-gate-in-skill", SKILL_MD,
         r"PG 14.17.*may not be declared.*NOT VALID|version-gated",
         None,
         "verified on live 14.23/15.18/16.14/17.10/18.4",
         "The main document must carry the version gate too; a reader who never opens "
         "the lock matrix would otherwise apply the 14-17 rule to an 18 target."),


    # --- 2026-08-07 round 3: claims a review flagged, each re-verified on a server ---
    Fact("F22-pg-repack-has-no-cleanup-mode", LARGE,
         r"pg_repack has no cleanup mode",
         r"pg_repack has a cleanup mode",
         "reorg.github.io/pg_repack -- --dry-run only prints what would be processed",
         "The file told the reader to run `--dry-run` to clean up after a crashed "
         "repack. It removes nothing; the documented recovery is DROP/CREATE EXTENSION. "
         "Following the old text would leave the repack schema and its triggers behind."),

    Fact("F23-no-extension-destdir-guc", REPL,
         r"no `extension_destdir` setting on PostgreSQL 14.18",
         r"SHOW extension_destdir",
         "pg_settings -- verified absent on live 14.23 and 18.4",
         "The file told the reader to run `SHOW extension_destdir` to locate an "
         "extension's upgrade scripts. No such GUC exists on any supported major, so "
         "the instruction can only error. Use pg_config SHAREDIR."),

    Fact("F24-setval-empty-table-is-called", LARGE,
         # Pins the SQL, not the prose around it. A require of "is_called|three-argument
         # form" matched the explanatory sentence, so a mutation that hardcoded the third
         # argument to `true` -- reintroducing the exact bug -- left the guard green.
         r"setval\(\s*\n\s*pg_get_serial_sequence\('orders_new', 'id'\),\s*\n"
         r"\s*coalesce\(\(SELECT max\(id\) FROM orders_new\), 1\),\s*\n"
         r"\s*\(SELECT count\(\*\) > 0 FROM orders_new\)",
         r"\(SELECT coalesce\(max\(id\), 1\) FROM orders_new\)\n\);",
         "functions-sequence.sgml -- measured: two-arg setval implies is_called = true",
         "The two-argument setval on an EMPTY table makes the next value 2, so id 1 is "
         "never issued after a create-swap-rename. The three-argument form with "
         "is_called driven by whether any row exists is the only correct shape."),

    Fact("F25-if-not-exists-is-not-generally-safe", ANTI,
         r"\*\*not\*\* safe in general",
         r"`CREATE INDEX IF NOT EXISTS` is safe by\ncontrast",
         "measured: an existing idx_x ON t (amt) survives CREATE INDEX IF NOT EXISTS "
         "idx_x ON t (note)",
         "AE-16 called IF NOT EXISTS safe while AE-19 documents its name-only drift "
         "hole. The two contradicted each other in the same file."),

    Fact("F26-nullable-add-column-takes-access-exclusive", SKILL_MD,
         r"still takes\nAccessExclusiveLock",
         r"all non-blocking \(ADD nullable column",
         "pg_locks -- measured on live 14.23 and 18.4",
         "Calling a nullable ADD COLUMN 'non-blocking' reads as 'needs no lock_timeout'. "
         "It takes AccessExclusiveLock briefly, so it still queues behind open "
         "transactions and still blocks everything behind it while it waits."),

    Fact("F19-max-uuid-absent", LARGE,
         r"`max\(uuid\)`? does not exist|no `max\(uuid\)` aggregate|not available for `uuid`",
         None,
         "pg_aggregate - verified absent on live 14.23 and 18.4",
         "PostgreSQL ships no max(uuid) aggregate on any supported version, so a "
         "uuid-keyed backfill using Template A's max(id) fails at runtime. This was "
         "documented backwards until a live server was queried."),

    Fact("F14-do-commit-is-supported", LARGE,
         r"COMMIT` inside a `DO` block \*\*is\*\* supported|is\*\* supported on PostgreSQL 11\+",
         r"requires PostgreSQL 11\+ with procedures \(`CREATE PROCEDURE`\)",
         "plpgsql.sgml - Transaction Management",
         "COMMIT in a DO block is legal on PG 11+; the real constraint is that the "
         "DO must be invoked at top level."),

    Fact("F14-do-commit-toplevel-only", LARGE,
         r"top level",
         None,
         "plpgsql.sgml - Transaction Management",
         "A framework-wrapped transaction makes the inner COMMIT fail."),

    Fact("F15-statement-timeout-concurrent", SKILL_MD,
         r"statement_timeout.*0|never cap a concurrent build",
         None,
         "config.sgml - statement_timeout",
         "statement_timeout aborts any statement exceeding it, so a short value "
         "kills a long concurrent index build."),

    Fact("F16-supported-versions", SKILL_MD,
         r"14\s*[–-]\s*18",
         r"PostgreSQL 12[–-]17",
         "postgres repo branches/tags",
         "Supported majors are 14-18 as of 2026-08; 12 and 13 are EOL."),

    Fact("F16-no-assume-pg12", SKILL_MD,
         r"Assume PG 14",
         r"Assume PG 12 \(conservative\)",
         "postgres repo branches/tags",
         "The conservative default must be the oldest SUPPORTED major."),

    Fact("F01-set-local-noop", SKILL_MD,
         r"outside a transaction",
         None,
         "set.sgml - LOCAL",
         "SET LOCAL outside a transaction block only warns and has no effect -- the "
         "defect that made the Critical scorecard item unsatisfiable."),

    Fact("F17-conrelid-scoping", SKILL_MD,
         r"conrelid",
         None,
         "catalog-pg-constraint.sgml",
         "Constraint names are unique per table, so an unscoped conname guard can "
         "silently skip the migration."),

    Fact("F18-pg-repack-cannot-alter-type", LARGE,
         r"pg_repack cannot change a schema|pg_repack \*\*cannot",
         r"Use pg_repack's trigger-based replication to copy data",
         "reorg.github.io/pg_repack",
         "pg_repack has no schema-change workflow; the previous text described a "
         "capability it does not have."),

    Fact("F19-keyset-backfill", LARGE,
         r"keyset",
         None,
         "skill rule",
         "Fixed numeric-range stepping is wrong for sparse, negative, UUID and "
         "composite keys."),

    Fact("F20-resume-point", LARGE,
         r"skips (every )?unprocessed rows?|skips unprocessed",
         None,
         "skill rule",
         "max(id) WHERE col IS NOT NULL skips unprocessed rows below the maximum."),

    Fact("F21-reindex-anti-example", ANTI,
         r"ShareLock on the parent table",
         r"REINDEX blocks all reads and writes on the underlying table",
         "reindex.sgml - Notes",
         "The same REINDEX error also existed in the anti-example file; fixing only "
         "the matrix would have left it live."),

    Fact("F22-anti-example-conrelid", ANTI,
         r"conrelid",
         None,
         "catalog-pg-constraint.sgml",
         "AE-11's recommended DO block originally carried the unscoped-conname bug "
         "it was supposed to teach against."),

    Fact("F27-extension-pin-installed-state", REPL,
         r"SELECT extversion INTO have FROM pg_extension.*?IF have IS NULL.*?"
         r"CREATE EXTENSION pg_stat_statements VERSION.*?ELSIF have <> want.*?"
         r"RAISE EXCEPTION",
         r"CREATE EXTENSION IF NOT EXISTS pg_stat_statements VERSION",
         "sql-createextension.html - IF NOT EXISTS",
         "IF NOT EXISTS does not change an already-installed extension to the requested "
         "version. The pin must distinguish absent, matching, and mismatched states."),
)


@pytest.mark.parametrize("fact", FACTS, ids=[f.fid for f in FACTS])
class TestFactDrift:
    def test_required_claim_present(self, fact: Fact):
        text = fact.doc.read_text(encoding="utf-8")
        assert re.search(fact.require, text, re.I | re.S), (
            f"{fact.fid}: {fact.doc.name} no longer states the verified claim.\n"
            f"  expected pattern: {fact.require}\n"
            f"  source: {fact.source}\n  why it matters: {fact.why}"
        )

    def test_previous_wrong_claim_absent(self, fact: Fact):
        if fact.forbid is None:
            pytest.skip("no superseded phrasing pinned for this fact")
        text = fact.doc.read_text(encoding="utf-8")
        assert not re.search(fact.forbid, text, re.I), (
            f"{fact.fid}: {fact.doc.name} has regressed to the superseded claim.\n"
            f"  forbidden pattern: {fact.forbid}\n"
            f"  source: {fact.source}\n  why it matters: {fact.why}"
        )


class TestFactRegistryIntegrity:
    def test_ids_unique(self):
        ids = [f.fid for f in FACTS]
        assert len(ids) == len(set(ids))

    def test_all_docs_exist(self):
        for f in FACTS:
            assert f.doc.exists(), f"{f.fid} points at a missing file: {f.doc}"

    def test_every_fact_has_a_source_and_reason(self):
        for f in FACTS:
            assert f.source.strip(), f"{f.fid} has no source"
            assert f.why.strip(), f"{f.fid} has no rationale"

    def test_forbid_patterns_do_not_match_their_own_require(self):
        """A `forbid` pattern that also matches the corrected text would make the
        two halves of the guard mutually unsatisfiable."""
        for f in FACTS:
            if f.forbid is None:
                continue
            text = f.doc.read_text(encoding="utf-8")
            assert re.search(f.require, text, re.I | re.S), f"{f.fid}: require failed"
            assert not re.search(f.forbid, text, re.I), f"{f.fid}: forbid matched"

    def test_forbid_patterns_are_specific_enough_to_fire(self):
        """Positive control: each forbidden pattern must actually match its own
        superseded text. A typo'd regex that can never match would pass forever."""
        # Reconstructed snippets of the pre-2026-08 wording.
        superseded = {
            "F04-fk-lock": "| ADD CONSTRAINT (FK/CHECK) | AccessExclusiveLock |",
            "F07-reindex-table-lock": "| REINDEX | AccessExclusiveLock | Yes | Yes |",
            "F08-identity-overriding":
                "  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,\n  user_id bigint",
            "F10-int-to-bigint-rewrites":
                "e.g., varchar(50) -> varchar(100), int → bigint on some versions",
            "F14-do-commit-is-supported":
                "Note: `COMMIT` inside DO blocks requires PostgreSQL 11+ with "
                "procedures (`CREATE PROCEDURE`)",
            "F16-supported-versions": "schema migration safety for PostgreSQL 12–17",
            "F16-no-assume-pg12": "| Assume PG 12 (conservative) |",
            "F18-pg-repack-cannot-alter-type":
                "2. Use pg_repack's trigger-based replication to copy data",
            "F21-reindex-anti-example":
                "REINDEX blocks all reads and writes on the underlying table.",
            # The pre-2026-08 decision-tree line, which stated the partitioned-table
            # restriction with no version qualifier. PG 18 accepts the NOT VALID form,
            # so the unqualified wording makes the skill reject valid SQL.
            "F13-partitioned-fk-not-valid":
                "Use NOT VALID to shorten the scan (unavailable on partitioned tables).",
            "F22-pg-repack-has-no-cleanup-mode":
                "-- Clean up (pg_repack has a cleanup mode)",
            "F23-no-extension-destdir-guc":
                "transition (`SHOW extension_destdir` / the packaged",
            "F24-setval-empty-table-is-called":
                "SELECT setval(\n  pg_get_serial_sequence('orders_new', 'id'),\n"
                "  (SELECT coalesce(max(id), 1) FROM orders_new)\n);",
            "F25-if-not-exists-is-not-generally-safe":
                "`CREATE INDEX IF NOT EXISTS` is safe by\ncontrast "
                "-- it is scoped correctly by the server.",
                     "F26-nullable-add-column-takes-access-exclusive":
                         "| **Lite** | <=3 DDL statements, all non-blocking "
                         "(ADD nullable column, CONCURRENTLY index) | 1-4 | None |",
                    "F27-extension-pin-installed-state":
                        "CREATE EXTENSION IF NOT EXISTS pg_stat_statements VERSION '1.9';",
                }
        for f in FACTS:
            if f.forbid is None:
                continue
            assert f.fid in superseded, (
                f"{f.fid} pins a forbidden pattern but provides no superseded "
                "sample to prove the pattern can fire"
            )
            assert re.search(f.forbid, superseded[f.fid], re.I), (
                f"{f.fid}: forbid pattern {f.forbid!r} does not match the actual "
                "superseded text it is meant to catch -- the guard is inert"
            )
