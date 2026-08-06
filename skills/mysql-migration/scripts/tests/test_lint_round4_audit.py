"""Regressions for the fourth review pass (2026-08-06).

The headline item is a correction to a correction: pass 3 rewrote SKILL.md to say
INSTANT takes no metadata lock, on the strength of the *What Is New* page. The
ALTER TABLE **reference** is more precise and says the opposite, and also that
INSTANT accepts no LOCK clause at all. Both are pinned here.
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
    spec = importlib.util.spec_from_file_location("mysql_migration_linter_r4", LINTER_PATH)
    assert spec and spec.loader, f"cannot load {LINTER_PATH}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


lint = _load_linter()
GUARD = "SET SESSION lock_wait_timeout = 3;\n"

SKILL_MD = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
MATRIX = (SKILL_DIR / "references" / "ddl-algorithm-matrix.md").read_text(encoding="utf-8")
ANTI = (SKILL_DIR / "references" / "migration-anti-examples.md").read_text(encoding="utf-8")


def run(sql: str, version: str = "8.0.32", name: str = "m.sql") -> set[str]:
    return {f.check_id for f in lint.lint_text(name, sql, lint.parse_version(version), False)}


class TestInstantAcceptsOnlyLockDefault:
    """Manual: "Only LOCK = DEFAULT is permitted for operations that use
    ALGORITHM=INSTANT. The other LOCK clause parameters are not applicable."
    """

    @pytest.mark.parametrize("lock", ["NONE", "SHARED", "EXCLUSIVE"])
    def test_non_default_lock_with_instant_is_critical(self, lock):
        out = run(GUARD + f"ALTER TABLE t ADD COLUMN c INT, ALGORITHM=INSTANT, LOCK={lock};",
                  "8.0.32")
        assert "MM029" in out, (
            f"ALGORITHM=INSTANT, LOCK={lock} is rejected by the server; got {sorted(out)}"
        )

    def test_lock_default_with_instant_is_accepted(self):
        assert "MM029" not in run(
            GUARD + "ALTER TABLE t ADD COLUMN c INT, ALGORITHM=INSTANT, LOCK=DEFAULT;", "8.0.32")

    def test_instant_without_a_lock_clause_is_clean(self):
        assert run(GUARD + "ALTER TABLE t ADD COLUMN c INT DEFAULT NULL, ALGORITHM=INSTANT;",
                   "8.0.32") == set()

    def test_inplace_with_lock_none_is_still_fine(self):
        assert "MM029" not in run(
            GUARD + "ALTER TABLE t ADD INDEX i (c), ALGORITHM=INPLACE, LOCK=NONE;", "8.0.32")

    def test_severity_is_critical_not_warning(self):
        assert lint.CHECK_REGISTRY["MM029"]["severity"] == lint.CRITICAL, (
            "the statement does not run; that is not a style warning"
        )

    def test_message_says_to_drop_the_clause_not_change_it(self):
        f = [x for x in lint.lint_text(
            "m.sql", GUARD + "ALTER TABLE t ADD COLUMN c INT, ALGORITHM=INSTANT, LOCK=NONE;",
            lint.parse_version("8.0.32")) if x.check_id == "MM029"]
        assert f and "Drop the LOCK clause" in f[0].message


class TestInstantIsNotLockFree:
    """Pass 3 introduced the claim that INSTANT takes no metadata lock. It does."""

    def test_skill_states_instant_can_take_an_exclusive_mdl(self):
        assert "exclusive metadata lock" in SKILL_MD
        assert "INSTANT is **not** exempt" in SKILL_MD or "INSTANT included" in SKILL_MD

    def test_skill_does_not_claim_instant_takes_no_lock(self):
        """Scoped per SENTENCE, not per line.

        SKILL.md items are paragraph-length single lines, so a line-scoped
        exclusion for the sentence that debunks the myth also excused the myth
        itself when both sat on the same line.
        """
        offenders = []
        for sentence in re.split(r"(?<=[.!?])\s+", SKILL_MD):
            if not re.search(r"take[s]?\s+\*{0,2}no\*{0,2}\s+metadata lock", sentence, re.I):
                continue
            # A sentence may quote the claim in order to reject it.
            if re.search(r"looser|not licence|do not treat|is a looser summary", sentence, re.I):
                continue
            offenders.append(sentence.strip()[:140])
        assert not offenders, (
            "INSTANT may take a brief exclusive metadata lock; claiming otherwise tells readers "
            f"to skip the guard. Offending sentences: {offenders}"
        )

    def test_the_myth_guard_is_not_vacuous(self):
        """Guard the guard: the detector must fire on the claim it exists to catch."""
        claim = "INSTANT operations take no metadata lock on the table."
        hits = [x for x in re.split(r"(?<=[.!?])\s+", claim)
                if re.search(r"take[s]?\s+\*{0,2}no\*{0,2}\s+metadata lock", x, re.I)
                and not re.search(r"looser|not licence|do not treat", x, re.I)]
        assert hits, "the detector would not catch the claim it was written for"

    def test_matrix_does_not_say_nothing_to_lock(self):
        assert "nothing to lock" not in MATRIX, (
            "'nothing to lock' is both wrong and the reason someone would omit the guard"
        )

    def test_matrix_flowchart_forbids_a_lock_clause_on_instant(self):
        chart = re.search(r"1\. Does §1–§4 list INSTANT.*?\n\n", MATRIX, re.S)
        assert chart, "the INSTANT step of the flowchart is missing"
        body = chart.group(0)
        assert re.search(r"omit LOCK|omit `LOCK`", body, re.I), (
            f"the INSTANT branch must say to omit the clause; got: {body!r}"
        )
        assert "LOCK=DEFAULT" in body or "LOCK = DEFAULT" in body
        assert re.search(r"NONE.*rejected|rejected.*NONE", body, re.S), (
            "it must also say which values are rejected"
        )

    def test_matrix_lock_table_is_algorithm_aware(self):
        """The old table mapped 'concurrent DML = yes' straight to LOCK=NONE.

        Scoped to the LOCK derivation table: `| **INSTANT** |` also appears as an
        ordinary cell in the per-operation tables, so a document-wide substring
        check is satisfied even when this row is deleted.
        """
        table = re.search(r"\*\*LOCK=NONE\?\*\*.*?(?=\*\*Rebuilds\?\*\*)", MATRIX, re.S)
        assert table, "the LOCK derivation table is missing"
        rows = [ln for ln in table.group(0).split("\n") if ln.startswith("|")]
        instant_rows = [ln for ln in rows if re.match(r"^\|\s*\*\*INSTANT\*\*\s*\|", ln)]
        assert instant_rows, (
            f"the LOCK derivation table must carve out INSTANT as its own row, or the general "
            f"concurrent-DML rule gets applied to it. Rows present: {rows}"
        )
        assert re.search(r"omit `LOCK`", instant_rows[0]), instant_rows[0]
        assert "LOCK=DEFAULT" in instant_rows[0] or "LOCK = DEFAULT" in instant_rows[0]

    def test_guard_is_still_required_before_instant(self):
        assert "MM015" in run(
            "ALTER TABLE t ADD COLUMN c INT DEFAULT NULL, ALGORITHM=INSTANT;", "8.0.32"), (
            "INSTANT can still queue behind a long transaction; the guard is not optional"
        )


class TestNineXIsAssumedNotVerified:
    """A matrix-identical release is not a rules-identical release."""

    @pytest.mark.parametrize("version", ["9.0.0", "9.1.0", "9.2.0", "9.7.0", "9.99.0"])
    def test_9x_is_assumed(self, version):
        coverage, why = lint.version_coverage(lint.parse_version(version))
        assert coverage == "assumed", f"{version} was never confirmed beyond the DDL matrix"
        assert "TOTAL_ROW_VERSIONS" in why, (
            "the explanation must name the concrete thing that changed, or it reads as caution "
            "for its own sake"
        )

    def test_9x_produces_mm028(self):
        f = lint.version_finding(lint.parse_version("9.7.0"))
        assert f is not None and f.check_id == "MM028"

    @pytest.mark.parametrize("version", ["5.7.44", "8.0.42", "8.4.5"])
    def test_the_three_transcribed_versions_stay_verified(self, version):
        assert lint.version_coverage(lint.parse_version(version))[0] == "verified"

    def test_skill_scope_does_not_call_9x_verified(self):
        head = SKILL_MD.split("**In scope**")[0]
        m = re.search(r"\*\*Verified\s*—\s*([^*]*)\*\*", head)
        assert m, "section 1 must state the verified set as **Verified — ...**"
        verified = m.group(1)
        assert "9" not in verified, f"9.x is assumed, not verified: {verified!r}"
        assert "5.7" in verified and "8.0" in verified and "8.4" in verified
        m2 = re.search(r"\*\*Assumed\s*—\s*([^*]*)\*\*", head)
        assert m2 and "9.x" in m2.group(1), "9.x must appear in the assumed set"


class TestRowVersionCeilingIsVersioned:
    def test_ae17_gives_both_ceilings_in_a_version_keyed_table(self):
        """Assert on the table rows.

        The surrounding prose quotes the manual, which contains both numbers and
        "9.1.0" — so a section-wide substring check passes even after the table
        is collapsed back to a single flat limit.
        """
        section = re.search(r"## AE-17:.*?(?=\n## |\Z)", ANTI, re.S)
        assert section, "AE-17 is missing"
        rows = [ln for ln in section.group(0).split("\n")
                if ln.startswith("|") and "TOTAL_ROW_VERSIONS" not in ln and "---" not in ln]
        assert len(rows) >= 2, f"the ceiling must be keyed by version band; rows: {rows}"
        assert any("255" in r and "9.1" in r for r in rows), (
            f"no row states the 9.1.0+ ceiling of 255; rows: {rows}"
        )
        assert any("64" in r and "8.4" in r for r in rows), (
            f"no row states the pre-9.1 ceiling of 64; rows: {rows}"
        )

    def test_ae17_does_not_assert_a_single_flat_limit(self):
        section = re.search(r"## AE-17:.*?(?=\n## |\Z)", ANTI, re.S).group(0)
        assert "read the ceiling off the server" in section or "not off this page" in section, (
            "a bare number invites quoting it at the wrong version"
        )


class TestUnparsedCarriersAreFindings:
    """Printing a note while returning 0 let a Liquibase directory pass CI."""

    def _dir_with(self, tmp_path, names):
        for n in names:
            (tmp_path / n).write_text("{}", encoding="utf-8")
        return str(tmp_path)

    def test_liquibase_only_directory_fails_at_fail_on_warning(self, tmp_path, capsys):
        target = self._dir_with(tmp_path, ["a.json", "b.xml", "c.yaml"])
        rc = lint.main(["--mysql-version", "8.0.32", "--fail-on", "warning", target])
        capsys.readouterr()
        assert rc == 1, "a directory of unread migration carriers must not pass a strict gate"

    def test_finding_is_emitted_per_format(self, tmp_path, capsys):
        import json as _json
        target = self._dir_with(tmp_path, ["a.json", "b.xml"])
        lint.main(["--mysql-version", "8.0.32", "--fail-on", "never", "--format", "json", target])
        payload = _json.loads(capsys.readouterr().out)
        ids = [f["check_id"] for f in payload["findings"]]
        assert ids.count("MM030") == 2, f"one finding per unread format; got {ids}"

    def test_count_is_reported_in_the_message(self, tmp_path, capsys):
        target = self._dir_with(tmp_path, ["a.json", "b.json", "c.json"])
        lint.main(["--mysql-version", "8.0.32", "--fail-on", "never", target])
        out = capsys.readouterr().out
        assert "3 file(s) of type" in out

    def test_a_directory_of_sql_produces_no_mm030(self, tmp_path, capsys):
        (tmp_path / "ok.sql").write_text(
            GUARD + "ALTER TABLE t ADD COLUMN c INT DEFAULT NULL, ALGORITHM=INSTANT;\n",
            encoding="utf-8")
        rc = lint.main(["--mysql-version", "8.0.32", "--fail-on", "warning", str(tmp_path)])
        capsys.readouterr()
        assert rc == 0

    def test_mm030_is_registered_and_documented(self):
        assert "MM030" in lint.CHECK_REGISTRY
        cov = (SKILL_DIR / "scripts" / "tests" / "COVERAGE.md").read_text(encoding="utf-8")
        assert "MM030" in cov


class TestExplicitUnparseableFilesAreNotScannedAsSql:
    """Naming a changelog explicitly does not make it parseable.

    Scanning a JSON/XML changelog as SQL reports "clean" about DDL that sits
    inside string values, masked by the quoting — a silent green on a file nobody
    checked. Only an *unknown* extension gets the "the caller says it is a
    migration" treatment.
    """

    BAD_DDL = "ALTER TABLE t ADD COLUMN c INT, ALGORITHM=INSTANT, LOCK=NONE;"

    @pytest.mark.parametrize("name,desc", [
        ("changelog.json", "Liquibase JSON"),
        ("changelog.xml", "Liquibase XML"),
        ("changelog.yaml", "Liquibase YAML"),
        ("changelog.yml", "Liquibase YAML"),
        ("migrate.go", "Go source"),
        ("Migration.java", "Java source"),
        ("env.py", "Python source"),
    ])
    def test_explicit_known_carrier_is_reported_not_scanned(self, tmp_path, name, desc):
        f = tmp_path / name
        f.write_text('{"sql": "%s"}' % self.BAD_DDL, encoding="utf-8")
        files, skipped = lint.iter_files([str(f)])
        assert files == [], f"{name} must not be scanned as SQL when named explicitly"
        assert any(desc in d for d in skipped), f"{name} must be reported; got {sorted(skipped)}"

    def test_explicit_carrier_fails_a_strict_run(self, tmp_path, capsys):
        f = tmp_path / "changelog.json"
        f.write_text('{"sql": "%s"}' % self.BAD_DDL, encoding="utf-8")
        rc = lint.main(["--mysql-version", "8.0.32", "--fail-on", "warning", str(f)])
        out = capsys.readouterr().out
        assert rc == 1, out
        assert "MM030" in out

    def test_explicit_unknown_extension_is_still_scanned(self, tmp_path, capsys):
        """The escape hatch stays open for genuinely unknown names."""
        f = tmp_path / "migration.weird"
        f.write_text("SET SESSION lock_wait_timeout = 3;\n" + self.BAD_DDL + "\n",
                     encoding="utf-8")
        files, skipped = lint.iter_files([str(f)])
        assert files == [f] and not skipped
        rc = lint.main(["--mysql-version", "8.0.32", str(f)])
        out = capsys.readouterr().out
        assert rc == 1 and "MM029" in out, out

    def test_extensionless_file_is_still_scanned(self, tmp_path):
        f = tmp_path / "migration"
        f.write_text("SET SESSION lock_wait_timeout = 3;\n", encoding="utf-8")
        files, skipped = lint.iter_files([str(f)])
        assert files == [f] and not skipped

    def test_zero_scan_message_no_longer_promises_explicit_override(self, tmp_path, capsys):
        f = tmp_path / "changelog.json"
        f.write_text("{}", encoding="utf-8")
        lint.main(["--mysql-version", "8.0.32", "--fail-on", "never", str(f)])
        out = capsys.readouterr().out
        assert "UNLESS the extension is a known-unparseable carrier" in out, (
            "the help text must not still claim explicit naming always wins"
        )


class TestRowVersionFailureNumberIsVersioned:
    """AE-17's table was versioned but its prose still said 'number 65'."""

    def test_prose_does_not_hardcode_the_65th_migration(self):
        section = re.search(r"## AE-17:.*?(?=\n## |\Z)", ANTI, re.S).group(0)
        prose = "\n".join(ln for ln in section.split("\n") if not ln.startswith("|"))
        assert "number 65" not in prose, (
            "the failing migration number is the server's ceiling + 1, which is 256 from 9.1.0"
        )

    def test_prose_names_both_thresholds(self):
        section = re.search(r"## AE-17:.*?(?=\n## |\Z)", ANTI, re.S).group(0)
        assert "65th" in section and "256th" in section, (
            "state both, keyed to the release, rather than one bare number"
        )

    def test_code_comment_is_not_hardcoded_either(self):
        section = re.search(r"## AE-17:.*?(?=\n## |\Z)", ANTI, re.S).group(0)
        assert "Release 1..64" not in section, (
            "the snippet comment carried the same stale ceiling"
        )


class TestInstantLockWordingIsPrecise:
    """"Accepts no LOCK clause" contradicted the quote beside it."""

    def test_skill_states_the_accepted_forms(self):
        line = [ln for ln in SKILL_MD.split("\n") if "Lock level" in ln]
        assert line, "section 5.1 item 2 is missing"
        body = line[0]
        assert re.search(r"omit the `LOCK` clause or write `LOCK=DEFAULT`", body), (
            f"say what IS accepted, not only what is not: {body[:160]}"
        )
        for rejected in ("NONE", "SHARED", "EXCLUSIVE"):
            assert rejected in body, f"{rejected} must be named as rejected"

    def test_skill_does_not_say_instant_accepts_no_lock_clause(self):
        assert "accepts **no `LOCK` clause**" not in SKILL_MD, (
            "that phrasing contradicts the LOCK=DEFAULT quote printed beside it"
        )

    def test_matrix_agrees_with_skill(self):
        table = re.search(r"\*\*LOCK=NONE\?\*\*.*?(?=\*\*Rebuilds\?\*\*)", MATRIX, re.S)
        row = [ln for ln in table.group(0).split("\n")
               if re.match(r"^\|\s*\*\*INSTANT\*\*\s*\|", ln)][0]
        assert "omit `LOCK`" in row and "LOCK=DEFAULT" in row


class TestCoverageDocHasNoUnassertedTotals:
    """Test totals drifted at every review pass; they are no longer stated."""

    COVERAGE = (SKILL_DIR / "scripts" / "tests" / "COVERAGE.md").read_text(encoding="utf-8")

    def test_no_grand_total_row(self):
        assert "**Total automated**" not in self.COVERAGE, (
            "a hand-maintained test total drifts and nothing catches it; the runner prints "
            "the authoritative numbers"
        )

    def test_points_at_the_runner_instead(self):
        assert "run_regression.sh" in self.COVERAGE

    def test_the_numbers_that_remain_are_asserted_ones(self):
        """Only counts with an enforcing test may appear as bold totals."""
        bolded = re.findall(r"\*\*(\d+)\s+(?:registered checks|mutations)\*\*", self.COVERAGE)
        bolded += re.findall(r"holds \*\*(\d+)\*\* mutations", self.COVERAGE)
        assert bolded, "the asserted counts should still be stated"
