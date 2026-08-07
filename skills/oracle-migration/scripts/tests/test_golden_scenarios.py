"""Golden scenario tests for the oracle-migration skill.

These tests are *behavioural*: every fixture's migration_snippet is fed to the real
checker in scripts/lint_migration.py and the emitted findings are compared against the
fixture's declared expectations. An earlier revision asserted only that certain words
appeared somewhere in the fixture's own expected_feedback string, which a fixture could
satisfy by restating its own conclusion — including a wrong one.
"""

import dataclasses
import importlib.util
import json
import pathlib
import re
import sys

import pytest

SKILL_DIR = pathlib.Path(__file__).resolve().parents[2]
SKILL_MD = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
REFS_DIR = SKILL_DIR / "references"
GOLDEN_DIR = pathlib.Path(__file__).resolve().parent / "golden"
LINTER_PATH = SKILL_DIR / "scripts" / "lint_migration.py"


def _load_linter():
    """Load lint_migration.py by path.

    Registered in sys.modules before exec_module because the module uses
    `from __future__ import annotations` together with @dataclass; without the
    registration the dataclass machinery cannot resolve the module and raises
    AttributeError: 'NoneType' object has no attribute '__dict__'.
    """
    name = "oracle_lint_migration"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, LINTER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


LINT = _load_linter()


def _all_docs_lower() -> str:
    parts = [SKILL_MD]
    for f in sorted(REFS_DIR.glob("*.md")):
        parts.append(f.read_text(encoding="utf-8"))
    return "\n".join(parts).lower()


def _load_fixtures() -> list[dict]:
    out = []
    for f in sorted(GOLDEN_DIR.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        d["_stem"] = f.stem
        out.append(d)
    return out


ALL_DOCS_LOWER = _all_docs_lower()
FIXTURES = _load_fixtures()
FIXTURES_BY_ID = {f["id"]: f for f in FIXTURES}

VALID_TYPES = {"defect", "good_practice", "degradation_scenario", "workflow"}
VALID_SEVERITIES = {"critical", "standard", "hygiene", "none"}
REQUIRED_FIELDS = {
    "id", "title", "type", "severity", "migration_snippet",
    "expected_feedback", "coverage_rules", "reference",
    "expect_findings", "forbid_findings", "lint_context",
}


CONTEXT_FIELDS = {f.name for f in dataclasses.fields(LINT.Context)}


def run_linter(fix: dict):
    ctx_raw = fix.get("lint_context") or {}
    unknown = set(ctx_raw) - CONTEXT_FIELDS
    assert not unknown, (
        f"{fix['id']}: lint_context has field(s) {sorted(unknown)} that Context does not "
        "accept — they would be silently dropped and the fixture would test the default"
    )
    return LINT.Linter(LINT.Context(**ctx_raw)).lint_text(
        fix["migration_snippet"], fix["_stem"] + ".sql"
    )


def codes(findings) -> set:
    return {f.code for f in findings}


def idfn(fix):
    return fix["id"]


def _sentences(text: str) -> list:
    """Split prose into sentences without breaking on `...`.

    Ellipses are masked first: SQL prose is full of `FLASHBACK TABLE ... TO SCN`, and a
    plain split on ". " cuts that in half, so a correctly-worded sentence loses the
    clause that qualifies it and the guard fires on text that is fine.
    """
    masked = text.replace("...", "\x00")
    parts = re.split(r"(?<=[.!?])\s+", masked)
    return [p.replace("\x00", "...").strip().lower() for p in parts if p.strip()]


# ======================================================================================
# Fixture schema integrity
# ======================================================================================


class TestFixtureIntegrity:
    def test_minimum_fixture_count(self):
        assert len(FIXTURES) >= 20

    @pytest.mark.parametrize("fix", FIXTURES, ids=idfn)
    def test_required_fields(self, fix):
        missing = REQUIRED_FIELDS - set(fix.keys())
        assert not missing, f"{fix['id']}: missing {missing}"

    @pytest.mark.parametrize("fix", FIXTURES, ids=idfn)
    def test_valid_type(self, fix):
        assert fix["type"] in VALID_TYPES

    @pytest.mark.parametrize("fix", FIXTURES, ids=idfn)
    def test_valid_severity(self, fix):
        assert fix["severity"] in VALID_SEVERITIES

    @pytest.mark.parametrize("fix", FIXTURES, ids=idfn)
    def test_defect_severity_not_none(self, fix):
        if fix["type"] == "defect":
            assert fix["severity"] != "none"

    @pytest.mark.parametrize("fix", FIXTURES, ids=idfn)
    def test_non_defect_severity_none(self, fix):
        if fix["type"] in ("good_practice", "degradation_scenario", "workflow"):
            assert fix["severity"] == "none"

    def test_unique_ids(self):
        ids = [f["id"] for f in FIXTURES]
        assert len(ids) == len(set(ids))

    @pytest.mark.parametrize("fix", FIXTURES, ids=idfn)
    def test_coverage_rules_findable(self, fix):
        for rule in fix["coverage_rules"]:
            assert rule.lower() in ALL_DOCS_LOWER, f"{fix['id']}: '{rule}' not in docs"

    @pytest.mark.parametrize("fix", FIXTURES, ids=idfn)
    def test_declared_codes_exist(self, fix):
        """A fixture cannot expect or forbid a check the linter does not implement."""
        declared = (
            fix["expect_findings"] + fix["forbid_findings"] + fix.get("lint_ignore", [])
        )
        for code in declared:
            assert code in LINT.CHECKS, f"{fix['id']}: unknown check code {code}"

    @pytest.mark.parametrize("fix", FIXTURES, ids=idfn)
    def test_expect_and_forbid_disjoint(self, fix):
        overlap = set(fix["expect_findings"]) & set(fix["forbid_findings"])
        assert not overlap, f"{fix['id']}: {overlap} both expected and forbidden"

    @pytest.mark.parametrize("fix", FIXTURES, ids=idfn)
    def test_defect_fixtures_expect_at_least_one_finding(self, fix):
        """A defect fixture the checker cannot detect is not a regression test."""
        if fix["type"] == "defect":
            assert fix["expect_findings"], (
                f"{fix['id']} is type=defect but declares no expect_findings — it would "
                "pass even if the checker stopped working entirely"
            )


# ======================================================================================
# Behavioural: the checker's real output vs the fixture's declared expectations
# ======================================================================================


class TestLinterBehaviour:
    @pytest.mark.parametrize("fix", FIXTURES, ids=idfn)
    def test_expected_findings_are_emitted(self, fix):
        got = codes(run_linter(fix))
        missing = set(fix["expect_findings"]) - got
        assert not missing, (
            f"{fix['id']}: checker did not emit {sorted(missing)}; emitted {sorted(got)}"
        )

    @pytest.mark.parametrize("fix", FIXTURES, ids=idfn)
    def test_forbidden_findings_are_absent(self, fix):
        got = codes(run_linter(fix))
        present = set(fix["forbid_findings"]) & got
        assert not present, (
            f"{fix['id']}: checker emitted forbidden {sorted(present)} (false positive)"
        )

    @pytest.mark.parametrize("fix", FIXTURES, ids=idfn)
    def test_no_undeclared_findings(self, fix):
        """Every emitted finding must be accounted for.

        Without this, a fixture could silently start producing extra findings — including
        false positives on the good_practice fixtures — and still pass.
        """
        got = codes(run_linter(fix))
        allowed = set(fix["expect_findings"]) | set(fix.get("lint_ignore", []))
        extra = got - allowed
        assert not extra, (
            f"{fix['id']}: undeclared findings {sorted(extra)}. Add them to "
            "expect_findings if correct, or to lint_ignore if incidental."
        )

    @pytest.mark.parametrize(
        "fix", [f for f in FIXTURES if f.get("expect_severity")], ids=idfn
    )
    def test_emitted_severity(self, fix):
        """Severity is a decision, not decoration, and needs its own assertion.

        Several checks downgrade or upgrade based on context (a prepared reverse rename,
        a pre-DDL snapshot, a row count below the scorecard threshold). Asserting only
        the finding's code or its wording lets the severity logic be deleted silently.
        """
        got = {f.code: f.severity for f in run_linter(fix)}
        for code, want in fix["expect_severity"].items():
            assert code in got, f"{fix['id']}: {code} not emitted at all"
            assert got[code] == want, (
                f"{fix['id']}: {code} emitted as {got[code]}, expected {want}"
            )

    @pytest.mark.parametrize(
        "fix", [f for f in FIXTURES if f.get("lint_detail_must_contain")], ids=idfn
    )
    def test_context_sensitive_wording(self, fix):
        """Edition/version context must actually change the advice, not just the header."""
        found = {f.code: f.detail for f in run_linter(fix)}
        for code, needle in fix["lint_detail_must_contain"].items():
            assert code in found, f"{fix['id']}: {code} not emitted"
            assert needle.lower() in found[code].lower(), (
                f"{fix['id']}: {code} detail missing {needle!r}\ngot: {found[code]}"
            )

    @pytest.mark.parametrize(
        "fix", [f for f in FIXTURES if f["type"] == "good_practice"], ids=idfn
    )
    def test_good_practice_has_no_critical_findings(self, fix):
        crit = [f.code for f in run_linter(fix) if f.severity == LINT.CRITICAL]
        assert not crit, f"{fix['id']} is good_practice but raises critical {crit}"

    @pytest.mark.parametrize(
        "fix", [f for f in FIXTURES if f["severity"] == "critical"], ids=idfn
    )
    def test_critical_fixture_yields_critical_finding(self, fix):
        sevs = {f.severity for f in run_linter(fix)}
        assert LINT.CRITICAL in sevs, (
            f"{fix['id']} is severity=critical but the checker's worst finding is {sevs}"
        )


# ======================================================================================
# Prose guards — the fixture's own narrative must not contradict the corrected facts
# ======================================================================================


class TestFeedbackContent:
    @pytest.mark.parametrize(
        "fix", [f for f in FIXTURES if f.get("expected_feedback_must_not_contain")], ids=idfn
    )
    def test_banned_phrases_absent(self, fix):
        fb = fix["expected_feedback"].lower()
        for phrase in fix["expected_feedback_must_not_contain"]:
            assert phrase.lower() not in fb, (
                f"{fix['id']}: expected_feedback still contains banned phrase {phrase!r}"
            )

    @pytest.mark.parametrize(
        "fix", [f for f in FIXTURES if f["type"] == "good_practice"], ids=idfn
    )
    def test_good_practice_states_no_violations(self, fix):
        assert "no violation" in fix["expected_feedback"].lower()

    def test_ora001_names_the_error_code(self):
        assert "ora-00054" in FIXTURES_BY_ID["ORA-001"]["expected_feedback"].lower()

    def test_ora002_prescribes_two_step(self):
        fb = FIXTURES_BY_ID["ORA-002"]["expected_feedback"].lower()
        assert "novalidate" in fb and "validate" in fb

    def test_ora003_rejects_fake_compensating_ddl(self):
        """The rollback fixture must reject structure-only 'rollback', not merely note it."""
        fb = FIXTURES_BY_ID["ORA-003"]["expected_feedback"].lower()
        assert "restore/pitr" in fb or "restore / pitr" in fb
        assert "compensating-ddl" in fb

    def test_ora003_does_not_recommend_flashback_table_as_undo(self):
        """Mentioning Flashback is fine; recommending it is not.

        Scoped to the sentence containing the mention so the guard cannot be satisfied
        by an unrelated negation elsewhere in the paragraph. Ellipses are masked before
        splitting — a naive split on ". " tears `FLASHBACK TABLE ... TO SCN` in half and
        fails on correct text.
        """
        fb = FIXTURES_BY_ID["ORA-003"]["expected_feedback"].lower().replace("\n", " ")
        mentions = [s for s in _sentences(fb) if "flashback table" in s]
        assert mentions, "ORA-003 should address Flashback explicitly"
        for sentence in mentions:
            assert "unavailable" in sentence or "cannot" in sentence, (
                f"ORA-003 mentions Flashback Table without ruling it out: {sentence!r}"
            )

    def test_flashback_sentence_guard_rejects_a_recommendation(self):
        """Guard the guard: the splitter must still catch a genuine violation."""
        bad = (
            "Drop the column. As a safety net, FLASHBACK TABLE ... TO TIMESTAMP will "
            "restore it. Nothing else is needed."
        )
        mentions = [s for s in _sentences(bad) if "flashback table" in s]
        assert len(mentions) == 1, f"splitter produced {mentions}"
        assert not ("unavailable" in mentions[0] or "cannot" in mentions[0])

    def test_ora011_rejects_the_rewrite_misclassification(self):
        fb = FIXTURES_BY_ID["ORA-011"]["expected_feedback"].lower()
        assert "ora-01440" in fb and "ora-01439" in fb
        assert "dictionary" in fb or "stored row bytes" in fb

    def test_ora012_names_the_missing_column(self):
        fb = FIXTURES_BY_ID["ORA-012"]["expected_feedback"].lower()
        assert "ora-00904" in fb
        assert "dba_objects" in fb

    def test_ora013_denies_atomicity(self):
        fb = FIXTURES_BY_ID["ORA-013"]["expected_feedback"].lower()
        assert "implicit commit" in fb
        assert "ora-00942" in fb

    def test_ora014_states_flashback_restriction(self):
        fb = FIXTURES_BY_ID["ORA-014"]["expected_feedback"].lower()
        assert "structure" in fb
        assert "to before drop" in fb

    def test_ora015_requires_halting_on_errors(self):
        fb = FIXTURES_BY_ID["ORA-015"]["expected_feedback"].lower()
        assert "dba_redefinition_errors" in fb
        assert "dml_lock_timeout" in fb

    def test_ora016_states_nologging_is_not_a_hint(self):
        fb = FIXTURES_BY_ID["ORA-016"]["expected_feedback"].lower()
        assert "not a hint" in fb
        assert "force logging" in fb

    def test_ora009_refuses_unevidenced_claims(self):
        fb = FIXTURES_BY_ID["ORA-009"]["expected_feedback"].lower()
        assert "must not" in fb or "not claim" in fb
        assert "degraded" in fb

    def test_ora019_and_020_name_their_gate(self):
        assert "se2" in FIXTURES_BY_ID["ORA-019"]["expected_feedback"].lower()
        assert "12.2" in FIXTURES_BY_ID["ORA-020"]["expected_feedback"]


# ======================================================================================
# Coverage of the declared check registry
# ======================================================================================


class TestCheckRegistryCoverage:
    def test_every_check_has_a_triggering_fixture(self):
        """CHECKS is declared as data; each entry needs a fixture that provokes it.

        Prevents the registry from listing checks that no longer fire.
        """
        triggered = set()
        for fix in FIXTURES:
            triggered |= codes(run_linter(fix))
        untriggered = set(LINT.CHECKS) - triggered
        assert not untriggered, (
            "checks with no triggering golden fixture: " + ", ".join(sorted(untriggered))
        )

    def test_every_check_has_a_non_triggering_fixture(self):
        """Each check must also stay silent on at least one fixture.

        A check that fires on every input carries no information.
        """
        always = set(LINT.CHECKS)
        for fix in FIXTURES:
            always &= codes(run_linter(fix))
        assert not always, (
            "checks that fire on every fixture (no discrimination): "
            + ", ".join(sorted(always))
        )
