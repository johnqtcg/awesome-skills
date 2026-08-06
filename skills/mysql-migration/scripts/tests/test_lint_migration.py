"""Behavioral tests for scripts/lint_migration.py.

These assert what the checker *decides* about real statements, not whether a
phrase appears somewhere in the documentation. Every check declared in
CHECK_REGISTRY must have a violating input that triggers it and, where a
corrected form exists, a clean input that does not.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys

import pytest

SKILL_DIR = pathlib.Path(__file__).resolve().parents[2]
LINTER_PATH = SKILL_DIR / "scripts" / "lint_migration.py"


def _load_linter():
    """Import lint_migration.py by path.

    The repo runs pytest with --import-mode=importlib, which does not put the
    test directory on sys.path, so a bare `import lint_migration` fails under
    `pytest skills/` while passing under run_regression.sh. Registering the
    module in sys.modules *before* exec_module is also required: the module
    combines `from __future__ import annotations` with @dataclass, and
    dataclass field resolution looks the module up by __name__.
    """
    spec = importlib.util.spec_from_file_location("mysql_migration_linter", LINTER_PATH)
    assert spec and spec.loader, f"cannot load {LINTER_PATH}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


lint = _load_linter()


def run(sql: str, version: str = "8.0.32", name: str = "m.sql",
        skip_negative: bool = False) -> set[str]:
    """Lint a snippet and return the set of check IDs reported."""
    findings = lint.lint_text(name, sql, lint.parse_version(version), skip_negative)
    return {f.check_id for f in findings}


def run_findings(sql: str, version: str = "8.0.32", name: str = "m.sql") -> list:
    return lint.lint_text(name, sql, lint.parse_version(version), False)


GUARD = "SET SESSION lock_wait_timeout = 3;\nSET SESSION innodb_lock_wait_timeout = 3;\n"


# ===========================================================================
# Declared-coverage contract: one violating input per registered check
# ===========================================================================

# check_id -> (source text, filename, mysql version)
VIOLATING_INPUTS: dict[str, tuple[str, str, str]] = {
    "MM001": (GUARD + "ALTER TABLE t ADD COLUMN c INT, ALGORITHM=INSTANT;", "m.sql", "5.7.40"),
    "MM003": (GUARD + "ALTER TABLE t ADD COLUMN c INT AFTER id, ALGORITHM=INSTANT;",
              "m.sql", "8.0.20"),
    "MM004": (GUARD + "ALTER TABLE t DROP COLUMN c, ALGORITHM=INSTANT;", "m.sql", "8.0.20"),
    "MM005": (GUARD + "ALTER TABLE t RENAME COLUMN a TO b, ALGORITHM=INSTANT;",
              "m.sql", "8.0.20"),
    "MM006": (GUARD + "ALTER TABLE t ADD INDEX idx_a (a), ALGORITHM=INSTANT;", "m.sql", "8.0.32"),
    "MM007": (GUARD + "ALTER TABLE t ADD PARTITION (PARTITION p1 VALUES LESS THAN (5)),"
                      " ALGORITHM=INPLACE;", "m.sql", "5.7.40"),
    "MM008": (GUARD + "ALTER TABLE t ADD FULLTEXT INDEX ft (body),"
                      " ALGORITHM=INPLACE, LOCK=NONE;", "m.sql", "8.0.32"),
    "MM009": (GUARD + "ALTER TABLE c ADD CONSTRAINT fk FOREIGN KEY (p_id) REFERENCES p(id),"
                      " ALGORITHM=INPLACE, LOCK=NONE;", "m.sql", "8.0.32"),
    "MM010": (GUARD + "ALTER TABLE t MODIFY COLUMN nick VARCHAR(64) CHARACTER SET utf8mb4,"
                      " ALGORITHM=INPLACE, LOCK=NONE;", "m.sql", "8.0.32"),
    "MM011": ("WHILE @i < @m DO\n  UPDATE t SET c = 1 WHERE id > @i;\nEND WHILE;",
              "m.sql", "8.0.32"),
    "MM012": ("UPDATE t SET c = 1 WHERE c IS NULL LIMIT 100 OFFSET 200;", "m.sql", "8.0.32"),
    "MM013": ("SET SESSION sql_log_bin = 0;\nUPDATE t SET c = 1 WHERE id = 1;",
              "m.sql", "8.0.32"),
    "MM014": (GUARD + "ALTER TABLE t ADD COLUMN c INT DEFAULT NULL;", "m.sql", "8.0.32"),
    "MM015": ("ALTER TABLE t ADD COLUMN c INT DEFAULT NULL, ALGORITHM=INSTANT;\n"
              "SET SESSION lock_wait_timeout = 3;", "m.sql", "8.0.32"),
    "MM016": ("UPDATE t SET c = 1 WHERE c IS NULL LIMIT 1000 OFFSET 5000;", "m.sql", "8.0.32"),
    "MM017": ("gh-ost --host=replica1.internal --allow-on-master --database=d --table=t"
              " --alter='ADD COLUMN c INT' --execute", "run.sh", "8.0.32"),
    "MM018": ("gh-ost --host=master.internal --allow-on-master --initially-drop-old-table"
              " --database=d --table=t --alter='ADD COLUMN c INT' --execute", "run.sh", "8.0.32"),
    "MM019": ("pt-online-schema-change --alter='MODIFY c INT NOT NULL' --null-to-not-null"
              " --execute D=d,t=t", "run.sh", "8.0.32"),
    "MM020": ("pt-online-schema-change --alter='ADD COLUMN c INT' D=d,t=t", "run.sh", "8.0.32"),
    "MM021": ("SHOW REPLICA STATUS;", "m.sql", "8.0.21"),
    "MM022": ("SHOW SLAVE STATUS;", "m.sql", "8.4.0"),
    "MM023": ("SELECT * FROM performance_schema.data_locks;", "m.sql", "5.7.40"),
    "MM024": ("SELECT Seconds_Behind_Source FROM x;", "m.sql", "8.0.21"),
    "MM025": (GUARD + "-- no backup exists\n"
                      "ALTER TABLE t DROP COLUMN legacy, ALGORITHM=INPLACE, LOCK=NONE;",
              "m.sql", "8.0.32"),
    "MM026": (GUARD + "ALTER TABLE t ADD COLUMN IF NOT EXISTS c INT, ALGORITHM=INSTANT;",
              "m.sql", "8.0.32"),
    "MM027": ("pt-online-schema-change --alter='ADD COLUMN c INT' --preserve-triggers"
              " --no-drop-old-table --execute D=d,t=t", "run.sh", "8.0.32"),
    "MM029": (GUARD + "ALTER TABLE t ADD COLUMN c INT, ALGORITHM=INSTANT, LOCK=NONE;",
              "m.sql", "8.0.32"),
}


# Checks that describe the whole run rather than one statement, so they have no
# per-file violating input. Each maps to a version that must trigger it.
RUN_LEVEL_INPUTS: dict[str, str] = {
    "MM028": "10.2.0",
}

# Run-level checks driven by the directory contents rather than the version.
# key -> (filename to create, mysql version)
CORPUS_LEVEL_INPUTS: dict[str, tuple[str, str]] = {
    "MM030": ("changelog.xml", "8.0.32"),
}


class TestDeclaredCoverage:
    """CHECK_REGISTRY is the coverage claim; these tests make it falsifiable."""

    def test_every_registered_check_has_a_violating_input(self):
        covered = set(VIOLATING_INPUTS) | set(RUN_LEVEL_INPUTS) | set(CORPUS_LEVEL_INPUTS)
        missing = set(lint.CHECK_REGISTRY) - covered
        assert not missing, (
            f"checks declared in CHECK_REGISTRY with no failing input: {sorted(missing)}. "
            "A declared check with no failing input is an unverified claim."
        )

    def test_no_orphan_fixtures(self):
        covered = set(VIOLATING_INPUTS) | set(RUN_LEVEL_INPUTS) | set(CORPUS_LEVEL_INPUTS)
        orphan = covered - set(lint.CHECK_REGISTRY)
        assert not orphan, f"fixtures for unregistered checks: {sorted(orphan)}"

    def test_a_check_is_not_declared_at_more_than_one_level(self):
        levels = [set(VIOLATING_INPUTS), set(RUN_LEVEL_INPUTS), set(CORPUS_LEVEL_INPUTS)]
        for i, a in enumerate(levels):
            for b in levels[i + 1:]:
                assert not (a & b), f"declared at more than one level: {sorted(a & b)}"

    @pytest.mark.parametrize("check_id", sorted(CORPUS_LEVEL_INPUTS))
    def test_corpus_level_check_fires(self, check_id, tmp_path, capsys):
        import json as _json
        filename, version = CORPUS_LEVEL_INPUTS[check_id]
        (tmp_path / filename).write_text("{}", encoding="utf-8")
        lint.main(["--mysql-version", version, "--fail-on", "never", "--format", "json",
                   str(tmp_path)])
        payload = _json.loads(capsys.readouterr().out)
        ids = {f["check_id"] for f in payload["findings"]}
        assert check_id in ids, f"{check_id} did not fire on {filename}; got {sorted(ids)}"

    @pytest.mark.parametrize("check_id", sorted(RUN_LEVEL_INPUTS))
    def test_run_level_check_fires(self, check_id):
        version = RUN_LEVEL_INPUTS[check_id]
        finding = lint.version_finding(lint.parse_version(version))
        assert finding is not None and finding.check_id == check_id, (
            f"{check_id} did not fire for --mysql-version {version}"
        )

    @pytest.mark.parametrize("check_id", sorted(VIOLATING_INPUTS))
    def test_violating_input_triggers_its_check(self, check_id):
        text, name, version = VIOLATING_INPUTS[check_id]
        reported = run(text, version, name)
        assert check_id in reported, (
            f"{check_id} did not fire on its own violating input "
            f"(reported: {sorted(reported) or 'nothing'})"
        )

    @pytest.mark.parametrize("check_id", sorted(lint.CHECK_REGISTRY))
    def test_registry_entry_is_well_formed(self, check_id):
        meta = lint.CHECK_REGISTRY[check_id]
        assert meta["severity"] in lint.SEVERITIES
        assert meta["title"] and len(meta["title"]) > 10


# ===========================================================================
# Corrected forms must be clean — the fix must actually satisfy the checker
# ===========================================================================

class TestCorrectedFormsAreClean:
    """Each pair mirrors a violating input above with the documented fix applied."""

    def test_instant_on_57_fixed_by_inplace(self):
        assert "MM001" not in run(
            GUARD + "ALTER TABLE t ADD COLUMN c INT DEFAULT NULL, ALGORITHM=INPLACE, LOCK=NONE;",
            "5.7.40")

    def test_instant_add_column_allowed_from_8012(self):
        assert "MM001" not in run(
            GUARD + "ALTER TABLE t ADD COLUMN c INT DEFAULT NULL, ALGORITHM=INSTANT;", "8.0.12")

    def test_instant_positional_add_allowed_from_8029(self):
        assert "MM003" not in run(
            GUARD + "ALTER TABLE t ADD COLUMN c INT AFTER id, ALGORITHM=INSTANT;", "8.0.29")

    def test_instant_drop_column_allowed_from_8029(self):
        assert "MM004" not in run(
            GUARD + "ALTER TABLE t DROP COLUMN c, ALGORITHM=INSTANT;\n-- backup retained",
            "8.0.29")

    def test_instant_rename_allowed_from_8028(self):
        assert "MM005" not in run(
            GUARD + "ALTER TABLE t RENAME COLUMN a TO b, ALGORITHM=INSTANT;", "8.0.28")

    def test_partition_without_algorithm_clean_on_57(self):
        out = run(GUARD + "ALTER TABLE t ADD PARTITION "
                          "(PARTITION p1 VALUES LESS THAN (5));", "5.7.40")
        assert "MM007" not in out
        # And the "always state an algorithm" warning must not fire here either:
        # on 5.7 the server accepts only DEFAULT for this clause.
        assert "MM014" not in out

    def test_partition_inplace_allowed_on_80(self):
        assert "MM007" not in run(
            GUARD + "ALTER TABLE t ADD PARTITION (PARTITION p1 VALUES LESS THAN (5)),"
                    " ALGORITHM=INPLACE, LOCK=NONE;", "8.0.32")

    def test_fulltext_with_shared_lock_is_clean(self):
        assert "MM008" not in run(
            GUARD + "ALTER TABLE t ADD FULLTEXT INDEX ft (body),"
                    " ALGORITHM=INPLACE, LOCK=SHARED;", "8.0.32")

    def test_fk_inplace_clean_when_checks_disabled_first(self):
        assert "MM009" not in run(
            GUARD
            + "SET SESSION foreign_key_checks = 0;\n"
            + "ALTER TABLE c ADD CONSTRAINT fk FOREIGN KEY (p_id) REFERENCES p(id),"
              " ALGORITHM=INPLACE, LOCK=NONE;\n"
            + "SET SESSION foreign_key_checks = 1;", "8.0.32")

    def test_fk_copy_is_clean(self):
        assert "MM009" not in run(
            GUARD + "ALTER TABLE c ADD CONSTRAINT fk FOREIGN KEY (p_id) REFERENCES p(id),"
                    " ALGORITHM=COPY;", "8.0.32")

    def test_varchar_within_band_is_clean(self):
        # VARCHAR(63) utf8mb4 = 252 bytes, still a 1-byte length prefix.
        assert "MM010" not in run(
            GUARD + "ALTER TABLE t MODIFY COLUMN nick VARCHAR(63) CHARACTER SET utf8mb4,"
                    " ALGORITHM=INPLACE, LOCK=NONE;", "8.0.32")

    def test_loop_inside_stored_program_is_clean(self):
        assert "MM011" not in run(
            "DELIMITER $$\n"
            "CREATE PROCEDURE p()\nBEGIN\n"
            "  DECLARE v BIGINT DEFAULT 0;\n"
            "  WHILE v < 10 DO\n    SET v = v + 1;\n  END WHILE;\n"
            "END$$\nDELIMITER ;", "8.0.32")

    def test_pk_range_backfill_is_clean(self):
        out = run("UPDATE t SET c = 1 WHERE id > 0 AND id <= 1000 AND c IS NULL;", "8.0.32")
        assert "MM012" not in out
        assert "MM016" not in out

    def test_ghost_replica_mode_without_flag_is_clean(self):
        assert "MM017" not in run(
            "gh-ost --host=replica1.internal --database=d --table=t"
            " --alter='ADD COLUMN c INT' --execute", "8.0.32", "run.sh")

    def test_ghost_master_mode_with_flag_is_clean(self):
        assert "MM017" not in run(
            "gh-ost --host=master.internal --allow-on-master --database=d --table=t"
            " --alter='ADD COLUMN c INT' --execute", "8.0.32", "run.sh")

    def test_ptosc_with_dry_run_is_clean(self):
        assert "MM020" not in run(
            "pt-online-schema-change --alter='ADD COLUMN c INT' --dry-run D=d,t=t",
            "8.0.32", "run.sh")

    def test_replica_statements_match_version(self):
        assert "MM021" not in run("SHOW REPLICA STATUS;", "8.0.22")
        assert "MM022" not in run("SHOW SLAVE STATUS;", "8.0.21")
        assert "MM023" not in run("SELECT * FROM performance_schema.data_locks;", "8.0.32")
        assert "MM024" not in run("SELECT Seconds_Behind_Master FROM x;", "5.7.40")
        assert "MM024" not in run("SELECT Seconds_Behind_Source FROM x;", "8.0.22")

    def test_drop_column_with_backup_is_clean(self):
        assert "MM025" not in run(
            GUARD + "-- mysqldump of t taken 2026-08-01, 30-day retention\n"
                    "ALTER TABLE t DROP COLUMN legacy, ALGORITHM=INPLACE, LOCK=NONE;", "8.0.32")


# ===========================================================================
# Regressions on the specific facts this skill previously stated incorrectly
# ===========================================================================

class TestPreviouslyWrongFacts:
    """Guards against reintroducing the errors found in the 2026-08-06 audit."""

    def test_drop_column_inplace_lock_none_is_accepted_on_57(self):
        """5.7 matrix: In Place = Yes, Permits Concurrent DML = Yes."""
        out = run(GUARD + "-- backup retained\n"
                          "ALTER TABLE t DROP COLUMN c, ALGORITHM=INPLACE, LOCK=NONE;", "5.7.40")
        assert out == set(), f"DROP COLUMN INPLACE/LOCK=NONE is valid on 5.7; got {sorted(out)}"

    def test_drop_column_inplace_lock_none_is_accepted_on_80_pre_8029(self):
        out = run(GUARD + "-- backup retained\n"
                          "ALTER TABLE t DROP COLUMN c, ALGORITHM=INPLACE, LOCK=NONE;", "8.0.20")
        assert out == set(), f"DROP COLUMN is INPLACE before 8.0.29; got {sorted(out)}"

    def test_varchar_extension_is_never_instant(self):
        assert "MM006" in run(
            GUARD + "ALTER TABLE t MODIFY COLUMN bio VARCHAR(500), ALGORITHM=INSTANT;", "8.0.35")

    def test_varchar_extension_inplace_is_fine(self):
        assert "MM006" not in run(
            GUARD + "ALTER TABLE t MODIFY COLUMN bio VARCHAR(200) CHARACTER SET latin1,"
                    " ALGORITHM=INPLACE, LOCK=NONE;", "8.0.35")

    def test_add_primary_key_permits_lock_none(self):
        """Manual's own example is ADD PRIMARY KEY (c), ALGORITHM=INPLACE, LOCK=NONE."""
        out = run(GUARD + "ALTER TABLE t ADD PRIMARY KEY (id), ALGORITHM=INPLACE, LOCK=NONE;",
                  "8.0.32")
        assert "MM008" not in out, f"ADD PRIMARY KEY permits concurrent DML; got {sorted(out)}"

    def test_rename_index_is_not_instant(self):
        assert "MM006" in run(
            GUARD + "ALTER TABLE t RENAME INDEX old_idx TO new_idx, ALGORITHM=INSTANT;", "8.0.35")

    def test_fulltext_blocks_dml_on_every_index_not_just_the_first(self):
        sql = (GUARD
               + "ALTER TABLE t ADD FULLTEXT INDEX ft1 (a), ALGORITHM=INPLACE, LOCK=NONE;\n"
               + "ALTER TABLE t ADD FULLTEXT INDEX ft2 (b), ALGORITHM=INPLACE, LOCK=NONE;")
        ids = [f.check_id for f in run_findings(sql, "8.0.35")]
        assert ids.count("MM008") == 2, (
            "every ADD FULLTEXT INDEX blocks writes, not only the first one on the table"
        )


# ===========================================================================
# Lexer behaviour
# ===========================================================================

class TestMasking:
    def test_comment_masking_preserves_length_and_lines(self):
        src = "SELECT 1; -- ALGORITHM=INSTANT\nSELECT 2;"
        masked = lint.mask_sql_noise(src)
        assert len(masked) == len(src)
        assert masked.count("\n") == src.count("\n")
        assert "INSTANT" not in masked

    def test_masking_does_not_merge_adjacent_tokens(self):
        """Blanking a span to '' would fuse the neighbours; NUL keeps them apart."""
        src = "ALTER /* x */ TABLE t;"
        masked = lint.mask_sql_noise(src)
        assert "ALTERTABLE" not in masked.replace("\x00", "")
        assert "ALTER" in masked and "TABLE" in masked

    def test_commented_out_violation_is_not_reported(self):
        assert run(GUARD + "-- ALTER TABLE t ADD COLUMN c INT, ALGORITHM=INSTANT;",
                   "5.7.40") == set()

    def test_shell_double_dash_flags_are_not_treated_as_sql_comments(self):
        out = run("gh-ost --host=replica1.internal --allow-on-master --database=d --table=t"
                  " --alter='ADD COLUMN c INT' --execute", "8.0.32", "run.sh")
        assert "MM017" in out


class TestMarkdownSegmentation:
    def test_negative_blocks_are_skippable(self):
        md = (
            "# Doc\n\n"
            "```sql\n-- WRONG: this is the anti-example\n"
            "ALTER TABLE t ADD COLUMN c INT, ALGORITHM=INSTANT;\n```\n"
        )
        assert "MM001" in run(md, "5.7.40", "doc.md", skip_negative=False)
        assert "MM001" not in run(md, "5.7.40", "doc.md", skip_negative=True)

    def test_non_sql_fences_are_ignored(self):
        md = "```text\nALTER TABLE t ADD COLUMN c INT, ALGORITHM=INSTANT;\n```\n"
        assert run(md, "5.7.40", "doc.md") == set()

    def test_bash_fence_is_linted_as_shell(self):
        md = ("```bash\ngh-ost --host=replica1.internal --allow-on-master"
              " --database=d --table=t --alter='ADD COLUMN c INT' --execute\n```\n")
        assert "MM017" in run(md, "8.0.32", "doc.md")


class TestVersionParsing:
    @pytest.mark.parametrize("raw,expected", [
        ("5.7", (5, 7, 0)),
        ("5.7.40", (5, 7, 40)),
        ("8.0.29", (8, 0, 29)),
        ("8.4.0-log", (8, 4, 0)),
        ("  8.0.35  ", (8, 0, 35)),
    ])
    def test_parse(self, raw, expected):
        assert lint.parse_version(raw) == expected

    def test_reject_garbage(self):
        with pytest.raises(ValueError):
            lint.parse_version("mysql-latest")


class TestCLI:
    def test_list_checks_needs_no_other_arguments(self, capsys):
        assert lint.main(["--list-checks"]) == 0
        assert "MM001" in capsys.readouterr().out

    def test_missing_version_is_usage_error_not_a_finding(self):
        with pytest.raises(SystemExit) as exc:
            lint.main(["some.sql"])
        assert exc.value.code == 2

    def test_unreadable_path_exits_2_not_1(self, capsys):
        assert lint.main(["--mysql-version", "8.0.32", "/nonexistent/nope.sql"]) == 2
        capsys.readouterr()

    def test_clean_file_exits_0(self, tmp_path, capsys):
        f = tmp_path / "ok.sql"
        f.write_text(GUARD + "ALTER TABLE t ADD COLUMN c INT DEFAULT NULL, ALGORITHM=INSTANT;")
        assert lint.main(["--mysql-version", "8.0.32", str(f)]) == 0
        capsys.readouterr()

    def test_critical_finding_exits_1(self, tmp_path, capsys):
        f = tmp_path / "bad.sql"
        f.write_text(GUARD + "ALTER TABLE t ADD COLUMN c INT, ALGORITHM=INSTANT;")
        assert lint.main(["--mysql-version", "5.7.40", str(f)]) == 1
        capsys.readouterr()

    def test_fail_on_warning_escalates(self, tmp_path, capsys):
        f = tmp_path / "warn.sql"
        f.write_text(GUARD + "ALTER TABLE t ADD COLUMN c INT DEFAULT NULL;")
        assert lint.main(["--mysql-version", "8.0.32", str(f)]) == 0
        assert lint.main(["--mysql-version", "8.0.32", "--fail-on", "warning", str(f)]) == 1
        capsys.readouterr()

    def test_json_output_is_parseable(self, tmp_path, capsys):
        import json
        f = tmp_path / "bad.sql"
        f.write_text(GUARD + "ALTER TABLE t ADD COLUMN c INT, ALGORITHM=INSTANT;")
        lint.main(["--mysql-version", "5.7.40", "--format", "json", str(f)])
        payload = json.loads(capsys.readouterr().out)
        assert payload["mysql_version"] == "5.7.40"
        assert payload["files_scanned"] == 1
        assert any(x["check_id"] == "MM001" for x in payload["findings"])


class TestSelfConsistency:
    """The skill's own shipped documentation must pass its own checker."""

    DOCS = ["SKILL.md", "references/ddl-algorithm-matrix.md",
            "references/large-table-migration.md",
            "references/migration-anti-examples.md"]

    @pytest.mark.parametrize("rel", DOCS)
    def test_shipped_docs_have_no_critical_findings(self, rel):
        path = SKILL_DIR / rel
        text = path.read_text(encoding="utf-8")
        # 8.0.35 is the version the positive examples target; anti-example blocks
        # (labelled WRONG/INVALID) are deliberately excluded.
        findings = lint.lint_text(rel, text, lint.parse_version("8.0.35"), True)
        critical = [f for f in findings if f.severity == lint.CRITICAL]
        assert not critical, "\n".join(
            f"{f.path}:{f.line} [{f.check_id}] {f.message}" for f in critical)


class TestLexerRegressions:
    """Defects found on 2026-08-06 when the fixture layer first ran the checker."""

    def test_statement_preceded_by_a_comment_is_still_analysed(self):
        """Masking uses NUL, which `re` does not treat as whitespace.

        A leading comment left the statement starting with NUL characters and
        every `^\\s*ALTER` anchor silently failed, so a migration file with a
        header comment — i.e. every real migration file — was not checked.
        """
        with_comment = GUARD + "-- V5__add_column.sql\nALTER TABLE t ADD COLUMN c VARCHAR(100);"
        without = GUARD + "ALTER TABLE t ADD COLUMN c VARCHAR(100);"
        assert "MM014" in run(without), "baseline: bare ALTER must be flagged"
        assert "MM014" in run(with_comment), (
            "a header comment must not hide the statement from the checker"
        )

    def test_block_comment_before_statement_does_not_hide_it(self):
        assert "MM014" in run(GUARD + "/* migration 5 */ ALTER TABLE t ADD COLUMN c INT;")

    def test_has_ddl_detection_survives_leading_comments(self):
        """MM015 is a whole-file check keyed off 'does this file contain DDL'.

        The line-anchored form must be exercised with a comment on the SAME line
        as the statement: a comment on its own preceding line leaves the next
        line's `^` clean, so it does not test the anchor at all.
        """
        assert "MM015" in run(
            "/* migration header */ ALTER TABLE t ADD COLUMN c INT, ALGORITHM=INSTANT;")
        assert "MM015" in run(
            "-- header\nALTER TABLE t ADD COLUMN c INT, ALGORITHM=INSTANT;")


class TestNoFalsePositiveOnNullabilityChange:
    """MODIFY naming a type is not necessarily a type change."""

    def test_not_null_enforcement_after_backfill_is_clean(self):
        """The standard phased pattern: add nullable, backfill, then enforce.

        'Making a column NOT NULL' is In Place = Yes, Permits Concurrent DML =
        Yes, so LOCK=NONE is correct. Flagging it critical broke golden fixture
        MIG-007, which is exactly the migration shape this skill recommends.
        """
        out = run(GUARD + "ALTER TABLE orders MODIFY COLUMN total_usd DECIMAL(12,2) "
                          "NOT NULL DEFAULT 0.00, ALGORITHM=INPLACE, LOCK=NONE;", "8.0.32")
        assert "MM008" not in out, f"nullability change permits LOCK=NONE; got {sorted(out)}"

    def test_limits_are_declared_as_data(self):
        """What the checker cannot decide must be written down, not implied."""
        assert hasattr(lint, "UNCHECKED_BY_DESIGN")
        assert "type-change-vs-nullability-change" in lint.UNCHECKED_BY_DESIGN
        for key, reason in lint.UNCHECKED_BY_DESIGN.items():
            assert reason and len(reason) > 10, f"{key} has no stated reason"


class TestPrimaryKeyLockRules:
    def test_drop_primary_key_alone_cannot_use_lock_none(self):
        assert "MM008" in run(
            GUARD + "ALTER TABLE t DROP PRIMARY KEY, ALGORITHM=COPY, LOCK=NONE;", "8.0.32")

    def test_drop_and_add_primary_key_together_permits_lock_none(self):
        out = run(GUARD + "ALTER TABLE t DROP PRIMARY KEY, ADD PRIMARY KEY (a, b), "
                          "ALGORITHM=INPLACE, LOCK=NONE;", "8.0.32")
        assert "MM008" not in out, (
            "dropping and adding a primary key in one statement permits concurrent DML"
        )
