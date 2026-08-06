"""Regressions for the third review pass (2026-08-06).

Covers file discovery, unparseable-format reporting, and version-range coverage —
the three places where the checker could previously report "clean" about input it
had never actually read.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import sys

import pytest

SKILL_DIR = pathlib.Path(__file__).resolve().parents[2]
LINTER_PATH = SKILL_DIR / "scripts" / "lint_migration.py"


def _load_linter():
    spec = importlib.util.spec_from_file_location("mysql_migration_linter_r3", LINTER_PATH)
    assert spec and spec.loader, f"cannot load {LINTER_PATH}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


lint = _load_linter()

DANGEROUS = ("SET SESSION lock_wait_timeout = 3;\n"
             "ALTER TABLE users ADD COLUMN c INT, ALGORITHM=INSTANT;\n")


class TestDirectoryDiscovery:
    """A migration the scanner never opened must not be reported as clean."""

    @pytest.mark.parametrize("name", [
        "V1__x.sql",            # Flyway
        "000001_init.up.sql",   # golang-migrate
        "schema.ddl",           # hand-rolled / Oracle-influenced
        "patch.mysql",
    ])
    def test_sql_carrying_extensions_are_scanned(self, tmp_path, name):
        (tmp_path / name).write_text(DANGEROUS, encoding="utf-8")
        files, _ = lint.iter_files([str(tmp_path)])
        assert [f.name for f in files] == [name], (
            f"{name} was not picked up in directory mode, so its DDL was never checked"
        )

    def test_ddl_extension_produces_the_same_findings_as_sql(self, tmp_path):
        (tmp_path / "a.sql").write_text(DANGEROUS, encoding="utf-8")
        (tmp_path / "b.ddl").write_text(DANGEROUS, encoding="utf-8")
        version = lint.parse_version("5.7.40")
        a = {f.check_id for f in lint.lint_text("a.sql", DANGEROUS, version)}
        b = {f.check_id for f in lint.lint_text("b.ddl", DANGEROUS, version)}
        assert a == b and "MM001" in a, (
            "extension must not change the verdict on identical content"
        )

    def test_explicitly_named_file_is_read_whatever_its_extension(self, tmp_path):
        odd = tmp_path / "migration.weird"
        odd.write_text(DANGEROUS, encoding="utf-8")
        files, skipped = lint.iter_files([str(odd)])
        assert files == [odd], "naming a file explicitly is the caller asserting it is a migration"
        assert not skipped

    def test_unrelated_files_are_not_scanned(self, tmp_path):
        (tmp_path / "notes.txt").write_text(DANGEROUS, encoding="utf-8")
        (tmp_path / "image.png").write_bytes(b"\x89PNG")
        files, skipped = lint.iter_files([str(tmp_path)])
        assert files == [] and skipped == {}

    def test_nested_directories_are_walked(self, tmp_path):
        nested = tmp_path / "migrations" / "v2"
        nested.mkdir(parents=True)
        (nested / "deep.sql").write_text(DANGEROUS, encoding="utf-8")
        files, _ = lint.iter_files([str(tmp_path)])
        assert [f.name for f in files] == ["deep.sql"]


class TestUnparseableFormatsAreReportedNotIgnored:
    """Liquibase XML/YAML and programmatic migrations carry DDL this cannot read."""

    @pytest.mark.parametrize("name,desc_fragment", [
        ("changelog.xml", "Liquibase XML"),
        ("changelog.yaml", "Liquibase YAML"),
        ("changelog.yml", "Liquibase YAML"),
        ("changelog.json", "Liquibase JSON"),
        ("migrate.go", "Go source"),
        ("Migration.java", "Java source"),
        ("env.py", "Python source"),
    ])
    def test_each_format_is_counted_and_named(self, tmp_path, name, desc_fragment):
        (tmp_path / name).write_text("<changeSet/>", encoding="utf-8")
        files, skipped = lint.iter_files([str(tmp_path)])
        assert files == []
        assert skipped, f"{name} was skipped silently"
        assert any(desc_fragment in d for d in skipped), (
            f"{name} must be reported by name; got {sorted(skipped)}"
        )

    def test_counts_accumulate(self, tmp_path):
        for i in range(3):
            (tmp_path / f"c{i}.xml").write_text("<changeSet/>", encoding="utf-8")
        _, skipped = lint.iter_files([str(tmp_path)])
        assert sum(skipped.values()) == 3

    def test_cli_prints_the_skipped_formats(self, tmp_path, capsys):
        (tmp_path / "changelog.xml").write_text("<changeSet/>", encoding="utf-8")
        (tmp_path / "ok.sql").write_text(DANGEROUS, encoding="utf-8")
        lint.main(["--mysql-version", "8.0.32", "--fail-on", "never", str(tmp_path)])
        out = capsys.readouterr().out
        assert "Not scanned" in out and "Liquibase XML" in out, (
            "a clean run over a Liquibase directory must not look like a clean migration set"
        )
        assert "updateSQL" in out, "tell the reader how to make the content lintable"

    def test_json_output_reports_skipped_formats(self, tmp_path, capsys):
        (tmp_path / "changelog.xml").write_text("<changeSet/>", encoding="utf-8")
        lint.main(["--mysql-version", "8.0.32", "--fail-on", "never",
                   "--format", "json", str(tmp_path)])
        payload = json.loads(capsys.readouterr().out)
        assert payload["unparseable_files_skipped"], (
            "machine consumers must be able to see that files went unread"
        )

    def test_zero_scanned_files_is_called_out(self, tmp_path, capsys):
        (tmp_path / "changelog.xml").write_text("<changeSet/>", encoding="utf-8")
        lint.main(["--mysql-version", "8.0.32", "--fail-on", "never", str(tmp_path)])
        assert "no files were scanned" in capsys.readouterr().out


class TestVersionCoverage:
    """dev.mysql.com redirects an unknown version to the current release, so the
    docs loading is not evidence that the rules apply."""

    @pytest.mark.parametrize("version", ["5.7.0", "5.7.44", "8.0.0", "8.0.42",
                                         "8.4.0", "8.4.5"])
    def test_transcribed_versions_are_verified(self, version):
        """Only the three versions whose matrix was transcribed from the manual."""
        coverage, _ = lint.version_coverage(lint.parse_version(version))
        assert coverage == "verified", f"{version} is inside the claimed range"

    @pytest.mark.parametrize("version", ["8.1.0", "8.2.0", "8.3.0", "9.0.0", "9.7.0"])
    def test_assumed_releases_are_not_claimed_as_verified(self, version):
        """9.x was downgraded from verified in the 2026-08-06 pass-4 review.

        Its online-DDL matrix is byte-identical to 8.4, which pass 3 treated as
        sufficient. It is not: 9.1.0 raised the INSTANT row-version ceiling from
        64 to 255 without touching that matrix. See test_lint_round4_audit.py.
        """
        coverage, why = lint.version_coverage(lint.parse_version(version))
        assert coverage == "assumed"
        assert "8.4" in why

    @pytest.mark.parametrize("version", ["5.6.51", "5.5.62", "10.0.0", "10.2.0", "11.0.0"])
    def test_out_of_range_versions_are_unverified(self, version):
        coverage, _ = lint.version_coverage(lint.parse_version(version))
        assert coverage == "unverified", f"{version} must not be silently accepted"

    def test_unverified_version_produces_mm028(self):
        f = lint.version_finding(lint.parse_version("10.2.0"))
        assert f is not None and f.check_id == "MM028"
        assert "on faith" in f.message

    def test_verified_version_produces_nothing(self):
        assert lint.version_finding(lint.parse_version("8.0.35")) is None

    def test_boundaries_are_exact(self):
        """Off-by-one at a range edge is how 9.x got silently analysed as 8.x."""
        assert lint.version_coverage(lint.parse_version("9.99.99"))[0] == "assumed"
        assert lint.version_coverage(lint.parse_version("10.0.0"))[0] == "unverified"
        assert lint.version_coverage(lint.parse_version("5.6.99"))[0] == "unverified"
        assert lint.version_coverage(lint.parse_version("5.7.0"))[0] == "verified"
        assert lint.version_coverage(lint.parse_version("5.8.0"))[0] == "unverified"
        assert lint.version_coverage(lint.parse_version("8.0.99"))[0] == "verified"
        assert lint.version_coverage(lint.parse_version("8.1.0"))[0] == "assumed"
        assert lint.version_coverage(lint.parse_version("8.4.99"))[0] == "verified"
        assert lint.version_coverage(lint.parse_version("8.5.0"))[0] == "unverified"

    def test_cli_reports_coverage_in_the_summary(self, tmp_path, capsys):
        f = tmp_path / "m.sql"
        f.write_text("SET SESSION lock_wait_timeout = 3;\n"
                     "ALTER TABLE t ADD COLUMN c INT, ALGORITHM=INPLACE, LOCK=NONE;\n",
                     encoding="utf-8")
        lint.main(["--mysql-version", "10.2.0", "--fail-on", "never", str(f)])
        out = capsys.readouterr().out
        assert "[unverified]" in out

    def test_fail_on_warning_makes_an_unverified_version_a_hard_stop(self, tmp_path, capsys):
        f = tmp_path / "m.sql"
        f.write_text("SET SESSION lock_wait_timeout = 3;\n"
                     "ALTER TABLE t ADD COLUMN c INT, ALGORITHM=INPLACE, LOCK=NONE;\n",
                     encoding="utf-8")
        rc = lint.main(["--mysql-version", "10.2.0", "--fail-on", "warning", str(f)])
        capsys.readouterr()
        assert rc == 1

    def test_mm028_fires_once_per_run_not_once_per_file(self, tmp_path, capsys):
        for i in range(4):
            (tmp_path / f"m{i}.sql").write_text(
                "SET SESSION lock_wait_timeout = 3;\n"
                "ALTER TABLE t ADD COLUMN c INT, ALGORITHM=INPLACE, LOCK=NONE;\n",
                encoding="utf-8")
        lint.main(["--mysql-version", "10.2.0", "--fail-on", "never",
                   "--format", "json", str(tmp_path)])
        payload = json.loads(capsys.readouterr().out)
        n = sum(1 for f in payload["findings"] if f["check_id"] == "MM028")
        assert n == 1, f"MM028 is a run-level check; got {n} copies"


class TestScopeStatementMatchesTheCode:
    """SKILL.md section 1 is a promise; keep it tied to what the checker does."""

    SKILL_MD = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")

    def test_declared_versions_match_the_verified_ranges(self):
        head = self.SKILL_MD.split("**In scope**")[0]
        for token in ("5.7", "8.0", "8.4", "9.x"):
            assert token in head, f"section 1 must mention {token}"
        assert "assumed" in head.lower(), (
            "section 1 must distinguish verified from assumed coverage"
        )

    def test_scope_names_the_unverified_bands(self):
        head = self.SKILL_MD.split("**In scope**")[0]
        assert "8.1" in head and "8.3" in head, "the EOL innovation gap must be stated"
        assert "MM028" in head, "point the reader at the check that enforces this"

    def test_scope_is_honest_about_liquibase(self):
        assert "Liquibase" in self.SKILL_MD
        scope = self.SKILL_MD.split("**Out of scope**")[0]
        assert "not parsed" in scope or "updateSQL" in scope, (
            "claiming Liquibase coverage without saying XML/YAML is unparsed overstates it"
        )

    def test_extension_list_in_skill_matches_the_checker(self):
        for ext in lint.SCANNED_EXTENSIONS:
            if ext in (".markdown",):
                continue
            assert f"`{ext}`" in self.SKILL_MD, (
                f"section 11 lists the scanned extensions; {ext} is missing"
            )
