"""Regressions for the second review pass (2026-08-06).

Each class pins one defect the review found, so reintroducing it fails the suite
rather than merely being re-noticed by the next reviewer.
"""

from __future__ import annotations

import importlib.util
import pathlib
import re
import sys

import pytest

SKILL_DIR = pathlib.Path(__file__).resolve().parents[2]
LINTER_PATH = SKILL_DIR / "scripts" / "lint_migration.py"


def _load_linter():
    spec = importlib.util.spec_from_file_location("mysql_migration_linter_r2", LINTER_PATH)
    assert spec and spec.loader, f"cannot load {LINTER_PATH}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


lint = _load_linter()

GUARD = "SET SESSION lock_wait_timeout = 3;\nSET SESSION innodb_lock_wait_timeout = 3;\n"


def run(sql: str, version: str = "8.0.32", name: str = "m.sql") -> set[str]:
    return {f.check_id for f in lint.lint_text(name, sql, lint.parse_version(version), False)}


def run_findings(sql: str, version: str = "8.0.32", name: str = "m.sql") -> list:
    return lint.lint_text(name, sql, lint.parse_version(version), False)


class TestInstantClauseIntroductionVersion:
    """The ALGORITHM=INSTANT clause arrives whole in 8.0.12, not just for ADD COLUMN.

    Manual (8.0 Nutshell): "As of MySQL 8.0.12, ALGORITHM=INSTANT is supported for
    the following ALTER TABLE operations: adding a column; adding or dropping a
    virtual column; adding or dropping a column default value; modifying the
    definition of an ENUM or SET column; changing the index type; renaming a
    table." The earlier threshold of 8.0.0 let every non-ADD-COLUMN INSTANT pass
    on 8.0.0-8.0.11, which the server rejects.
    """

    NON_ADD_COLUMN_INSTANT = [
        "ALTER TABLE t ALTER COLUMN age SET DEFAULT 0, ALGORITHM=INSTANT;",
        "ALTER TABLE t ALTER COLUMN age DROP DEFAULT, ALGORITHM=INSTANT;",
        "ALTER TABLE t MODIFY COLUMN c ENUM('a','b','c'), ALGORITHM=INSTANT;",
        "ALTER TABLE t RENAME TO t2, ALGORITHM=INSTANT;",
    ]

    @pytest.mark.parametrize("stmt", NON_ADD_COLUMN_INSTANT)
    def test_8011_rejects_every_instant_operation(self, stmt):
        assert "MM001" in run(GUARD + stmt, "8.0.11"), (
            "8.0.11 has no ALGORITHM=INSTANT clause at all"
        )

    @pytest.mark.parametrize("version", ["8.0.0", "8.0.5", "8.0.11"])
    def test_every_pre_8012_release_rejects_instant(self, version):
        assert "MM001" in run(
            GUARD + "ALTER TABLE t ALTER COLUMN age SET DEFAULT 0, ALGORITHM=INSTANT;", version)

    @pytest.mark.parametrize("version", ["8.0.12", "8.0.29", "8.4.0"])
    def test_8012_and_later_accept_the_supported_set(self, version):
        assert "MM001" not in run(
            GUARD + "ALTER TABLE t ALTER COLUMN age SET DEFAULT 0, ALGORITHM=INSTANT;", version)

    def test_57_still_reported(self):
        assert "MM001" in run(
            GUARD + "ALTER TABLE t ADD COLUMN c INT, ALGORITHM=INSTANT;", "5.7.40")

    def test_mm002_is_not_resurrected(self):
        """MM002 was withdrawn as a strict subset of the corrected MM001."""
        assert "MM002" not in lint.CHECK_REGISTRY, (
            "MM002 could never fire independently once MM001's threshold became 8.0.12; "
            "a check that cannot fire inflates the coverage count without adding coverage"
        )


class TestIfExistsIsNotMySQLAlterSyntax:
    """MySQL ALTER TABLE has no IF [NOT] EXISTS for columns or indexes.

    The clause exists in MariaDB. `IF EXISTS` / `IF NOT EXISTS` appears zero
    times on the MySQL 8.0 ALTER TABLE reference page.
    """

    @pytest.mark.parametrize("stmt", [
        "ALTER TABLE t ADD COLUMN IF NOT EXISTS c INT;",
        "ALTER TABLE t DROP COLUMN IF EXISTS c;",
        "ALTER TABLE t ADD INDEX IF NOT EXISTS idx_c (c);",
        "ALTER TABLE t DROP INDEX IF EXISTS idx_c;",
    ])
    def test_alter_clause_variants_are_flagged(self, stmt):
        assert "MM026" in run(GUARD + stmt, "8.0.32")

    def test_statement_level_if_exists_remains_valid(self):
        """CREATE TABLE / DROP TABLE genuinely support it — do not flag those."""
        sql = ("CREATE TABLE IF NOT EXISTS t (id INT PRIMARY KEY);\n"
               "-- mysqldump retained\n"
               "DROP TABLE IF EXISTS scratch_table;")
        assert "MM026" not in run(sql, "8.0.32")


class TestBackupClaimNegation:
    """A backup mention inside a negation is not a backup."""

    @pytest.mark.parametrize("note", [
        "-- no backup exists",
        "-- backup not taken yet",
        "-- TODO: backup",
        "-- without a snapshot",
        "-- missing backup",
        "-- we never took a mysqldump",
        "-- restore is unavailable for this table",
    ])
    def test_negated_claims_do_not_satisfy_mm025(self, note):
        assert "MM025" in run(
            GUARD + f"{note}\nALTER TABLE t DROP COLUMN legacy, ALGORITHM=INPLACE, LOCK=NONE;",
            "8.0.32")

    @pytest.mark.parametrize("note", [
        "-- mysqldump of t taken 2026-08-01, 30-day retention",
        "-- snapshot captured before this release",
        "-- PITR window covers this change",
    ])
    def test_positive_claims_satisfy_mm025(self, note):
        assert "MM025" not in run(
            GUARD + f"{note}\nALTER TABLE t DROP COLUMN legacy, ALGORITHM=INPLACE, LOCK=NONE;",
            "8.0.32")

    def test_negation_elsewhere_does_not_void_a_real_backup_claim(self):
        """The negation must attach to the mention it governs, not to the file."""
        assert "MM025" not in run(
            GUARD + "-- no maintenance window is available this week\n"
                    "-- mysqldump taken, 30-day retention\n"
                    "ALTER TABLE t DROP COLUMN legacy, ALGORITHM=INPLACE, LOCK=NONE;", "8.0.32")


class TestSessionGuardOrdering:
    """A guard set after the DDL protects nothing."""

    def test_guard_after_ddl_is_reported(self):
        assert "MM015" in run(
            "ALTER TABLE t ADD INDEX idx_x (x), ALGORITHM=INPLACE, LOCK=NONE;\n"
            "SET SESSION lock_wait_timeout = 3;", "8.0.32")

    def test_guard_after_ddl_message_names_the_ordering(self):
        f = [x for x in run_findings(
            "ALTER TABLE t ADD INDEX idx_x (x), ALGORITHM=INPLACE, LOCK=NONE;\n"
            "SET SESSION lock_wait_timeout = 3;", "8.0.32") if x.check_id == "MM015"]
        assert f and "AFTER the first DDL" in f[0].message

    def test_guard_before_ddl_is_clean(self):
        assert "MM015" not in run(
            "SET SESSION lock_wait_timeout = 3;\n"
            "ALTER TABLE t ADD INDEX idx_x (x), ALGORITHM=INPLACE, LOCK=NONE;", "8.0.32")

    def test_guard_between_two_ddls_still_reports_the_first(self):
        assert "MM015" in run(
            "ALTER TABLE t ADD INDEX i1 (a), ALGORITHM=INPLACE, LOCK=NONE;\n"
            "SET SESSION lock_wait_timeout = 3;\n"
            "ALTER TABLE t ADD INDEX i2 (b), ALGORITHM=INPLACE, LOCK=NONE;", "8.0.32"), \
            "the first DDL ran unguarded regardless of what follows"

    def test_ptosc_set_vars_counts_as_a_guard(self):
        assert "MM015" not in run(
            "pt-online-schema-change --alter='ADD COLUMN c INT'"
            " --set-vars='lock_wait_timeout=3' --execute D=d,t=t", "8.0.32", "run.sh")


class TestVarcharBandNeedsCurrentDefinition:
    """The band is decided by the pair of widths, and only one is in the statement."""

    def test_finding_is_a_warning_not_critical(self):
        findings = [f for f in run_findings(
            GUARD + "ALTER TABLE t MODIFY name VARCHAR(300) CHARACTER SET latin1,"
                    " ALGORITHM=INPLACE;", "8.0.32") if f.check_id == "MM010"]
        assert findings, "the possible band crossing must still be surfaced"
        assert all(f.severity == lint.WARNING for f in findings), (
            "VARCHAR(260)->VARCHAR(300) latin1 stays in the 2-byte band and is a legal "
            "in-place change; a critical finding would block a correct migration"
        )

    def test_message_names_the_evidence_that_would_settle_it(self):
        f = [x for x in run_findings(
            GUARD + "ALTER TABLE t MODIFY name VARCHAR(300) CHARACTER SET latin1,"
                    " ALGORITHM=INPLACE;", "8.0.32") if x.check_id == "MM010"]
        assert "SHOW CREATE TABLE" in f[0].message

    def test_registry_severity_matches(self):
        assert lint.CHECK_REGISTRY["MM010"]["severity"] == lint.WARNING

    def test_uncertainty_is_declared_as_a_known_limit(self):
        assert any("varchar" in k for k in lint.UNCHECKED_BY_DESIGN)


class TestPtOscPreserveTriggers:
    """Upstream: --preserve-triggers cannot combine with flags that keep the old objects."""

    @pytest.mark.parametrize("clash", [
        "--no-drop-triggers", "--no-drop-old-table", "--no-swap-tables",
    ])
    def test_conflicts_are_flagged(self, clash):
        assert "MM027" in run(
            f"pt-online-schema-change --alter='ADD COLUMN c INT' --preserve-triggers {clash}"
            " --execute D=d,t=t", "8.0.32", "run.sh")

    def test_preserve_triggers_alone_is_clean(self):
        assert "MM027" not in run(
            "pt-online-schema-change --alter='ADD COLUMN c INT' --preserve-triggers"
            " --execute D=d,t=t", "8.0.32", "run.sh")

    def test_no_drop_old_table_alone_is_clean(self):
        assert "MM027" not in run(
            "pt-online-schema-change --alter='ADD COLUMN c INT' --no-drop-old-table"
            " --execute D=d,t=t", "8.0.32", "run.sh")

    def test_message_names_the_tradeoff(self):
        f = [x for x in run_findings(
            "pt-online-schema-change --alter='ADD COLUMN c INT' --preserve-triggers"
            " --no-drop-old-table --execute D=d,t=t", "8.0.32", "run.sh")
            if x.check_id == "MM027"]
        assert f and "mutually exclusive" in f[0].message


class TestBaselineAllowlist:
    """The self-lint runs at --fail-on warning; the baseline is what keeps that honest."""

    BASELINE = SKILL_DIR / "scripts" / "tests" / "lint_baseline.txt"

    def test_baseline_file_exists_and_parses(self):
        entries = lint.load_baseline(self.BASELINE)
        assert entries, "an empty baseline should be deleted, not shipped"

    def test_every_entry_carries_a_written_justification(self):
        """An exemption without a reason is indistinguishable from a mistake."""
        text = self.BASELINE.read_text(encoding="utf-8")
        comment_lines = [ln for ln in text.split("\n") if ln.strip().startswith("#")]
        assert len(comment_lines) >= 5, "the baseline must explain why each entry exists"

    def test_entries_are_not_keyed_on_line_numbers(self):
        """Line keys silently stop matching after any edit above the block."""
        for entry in lint.load_baseline(self.BASELINE):
            assert not entry.path_suffix.split("/")[-1].count(":"), (
                "baseline entries match on evidence text, not path:line"
            )

    def test_baseline_suppresses_only_its_own_finding(self):
        entries = lint.load_baseline(self.BASELINE)
        other = lint.Finding(check_id="MM014", severity=lint.WARNING,
                             path="references/migration-anti-examples.md", line=1,
                             message="x", evidence="ALTER TABLE unrelated ADD COLUMN c INT;")
        assert not any(e.matches(other) for e in entries), (
            "a baseline entry must not blanket-suppress its check for the whole file"
        )

    def test_baseline_entry_matches_its_target(self):
        target = lint.Finding(
            check_id="MM014", severity=lint.WARNING,
            path="skills/mysql-migration/references/migration-anti-examples.md", line=250,
            message="x",
            evidence="ALTER TABLE events ADD PARTITION (PARTITION p2026_09 "
                     "VALUES LESS THAN (20260901));")
        assert any(e.matches(target) for e in lint.load_baseline(self.BASELINE))

    def test_malformed_entry_is_rejected(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
            fh.write("MM014 references/x.md\n")
            name = fh.name
        with pytest.raises(ValueError):
            lint.load_baseline(pathlib.Path(name))

    def test_self_lint_is_clean_at_fail_on_warning(self, capsys):
        """The gate the runner actually uses, exercised end to end."""
        rc = lint.main([
            "--mysql-version", "8.0.35", "--skip-negative-examples",
            "--fail-on", "warning", "--baseline", str(self.BASELINE),
            str(SKILL_DIR / "SKILL.md"), str(SKILL_DIR / "references"),
        ])
        out = capsys.readouterr().out
        assert rc == 0, out

    def test_stale_baseline_entry_fails_the_run(self, tmp_path, capsys):
        """An exemption whose target is gone must not linger."""
        stale = tmp_path / "stale.txt"
        stale.write_text("MM014 | references/nope.md | SELECT 1;\n")
        clean = tmp_path / "ok.sql"
        clean.write_text("SET SESSION lock_wait_timeout = 3;\n"
                         "ALTER TABLE t ADD COLUMN c INT DEFAULT NULL, ALGORITHM=INSTANT;\n")
        rc = lint.main(["--mysql-version", "8.0.32", "--baseline", str(stale), str(clean)])
        capsys.readouterr()
        assert rc == 1, "a baseline entry matching nothing is an error, not a no-op"

    def test_unlisted_warning_still_fails_at_fail_on_warning(self, tmp_path, capsys):
        f = tmp_path / "w.sql"
        f.write_text("SET SESSION lock_wait_timeout = 3;\n"
                     "ALTER TABLE t ADD COLUMN c INT DEFAULT NULL;\n")
        empty = tmp_path / "b.txt"
        empty.write_text("# nothing exempted\n")
        rc = lint.main(["--mysql-version", "8.0.32", "--fail-on", "warning",
                        "--baseline", str(empty), str(f)])
        capsys.readouterr()
        assert rc == 1, "warnings outside the baseline must still fail the gate"


class TestDocumentedCountsMatchTheCode:
    """Numbers stated in prose drift; make each one an assertion.

    SKILL.md and COVERAGE.md both quote a check count. A stale count is exactly
    the kind of claim that looks authoritative and is quietly wrong — the same
    failure mode as the DDL matrix rows this skill was audited for.
    """

    SKILL_MD = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    COVERAGE = (SKILL_DIR / "scripts" / "tests" / "COVERAGE.md").read_text(encoding="utf-8")

    def test_skill_md_check_count_matches_registry(self):
        m = re.search(r"(\d+) checks:", self.SKILL_MD)
        assert m, "SKILL.md section 11 must state how many checks the linter has"
        assert int(m.group(1)) == len(lint.CHECK_REGISTRY), (
            f"SKILL.md says {m.group(1)} checks; CHECK_REGISTRY has "
            f"{len(lint.CHECK_REGISTRY)}"
        )

    def test_coverage_check_count_matches_registry(self):
        m = re.search(r"`CHECK_REGISTRY` declares (\d+)\s*\n?checks", self.COVERAGE)
        assert m, "COVERAGE.md section 3 must state the declared check count"
        assert int(m.group(1)) == len(lint.CHECK_REGISTRY), (
            f"COVERAGE.md says {m.group(1)} checks; CHECK_REGISTRY has "
            f"{len(lint.CHECK_REGISTRY)}"
        )

    @staticmethod
    def _load_sweep():
        """Import the runner and read its actual MUTATIONS list.

        Counting by string-matching the file-constant names was itself brittle:
        adding VERIFY/EVAL/COMPOSE targets silently undercounted, which is the
        same class of drift this test exists to prevent.
        """
        spec = importlib.util.spec_from_file_location(
            "mysql_migration_mutation_sweep", SKILL_DIR / "scripts" / "mutation_sweep.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module

    def test_coverage_mutation_count_matches_the_runner(self):
        actual = len(self._load_sweep().MUTATIONS)
        m = re.search(r"holds \*\*(\d+)\*\* mutations", self.COVERAGE)
        assert m, "COVERAGE.md section 6 must state the mutation count"
        assert int(m.group(1)) == actual, (
            f"COVERAGE.md claims {m.group(1)} mutations; mutation_sweep.py defines {actual}"
        )

    def test_every_mutation_targets_a_file_that_exists(self):
        for name, rel, _old, _new in self._load_sweep().MUTATIONS:
            assert (SKILL_DIR / rel).exists(), f"mutation {name!r} targets missing file {rel}"

    def test_mutation_names_are_unique(self):
        names = [m[0] for m in self._load_sweep().MUTATIONS]
        assert len(names) == len(set(names)), "duplicate mutation names hide sweep results"

    @staticmethod
    def _ids_covered(text: str) -> set:
        """Collect IDs named in the doc, expanding `MM003-MM005` style ranges."""
        covered = set(re.findall(r"\bMM\d{3}\b", text))
        for lo, hi in re.findall(r"\bMM(\d{3})\s*[-–—]\s*MM(\d{3})\b", text):
            covered.update(f"MM{n:03d}" for n in range(int(lo), int(hi) + 1))
        return covered

    def test_every_registry_id_is_documented_in_coverage(self):
        covered = self._ids_covered(self.COVERAGE)
        missing = sorted(set(lint.CHECK_REGISTRY) - covered)
        assert not missing, (
            f"registered but absent from COVERAGE.md's check table: {missing}"
        )

    def test_coverage_does_not_claim_ids_that_do_not_exist(self):
        claimed = self._ids_covered(self.COVERAGE)
        # MM002 may appear only in the withdrawal note, never as a covered check.
        rows = [ln for ln in self.COVERAGE.split("\n") if ln.startswith("|")]
        claimed_in_rows = self._ids_covered("\n".join(rows))
        phantom = sorted(claimed_in_rows - set(lint.CHECK_REGISTRY))
        assert not phantom, (
            f"COVERAGE.md's check table claims IDs that are not registered: {phantom}"
        )
        assert claimed, "no check IDs found in COVERAGE.md at all"

    def test_range_expansion_helper_is_not_vacuous(self):
        """Guard the guard: the helper must actually expand ranges."""
        assert self._ids_covered("MM003–MM005") == {"MM003", "MM004", "MM005"}
        assert self._ids_covered("MM021") == {"MM021"}

    def test_withdrawn_id_is_not_claimed_as_covered(self):
        assert "MM002" not in lint.CHECK_REGISTRY
