"""Golden scenario tests for the api-design skill.

Scope, stated honestly: these are **consistency** tests, not behavioural
evidence. They do not run a model against the fixtures, so they cannot show
that the skill makes an agent review an API correctly. What they do enforce:

1. every defect fixture's severity equals the tier SKILL.md's scorecard
   actually assigns to the item it cites — expectations are *derived from the
   skill*, so a tier change in the doc breaks the fixtures instead of drifting
   past them;
2. every false-positive fixture cites a license anchor that exists in the docs,
   so deleting the clause that legalises a design breaks the fixture;
3. fixture prose obeys the same factual rules as the documentation — an
   exemplar that fails its own linter is worthless.

Behavioural claims belong to a live evaluation harness, not to this file.
"""

import ast
import collections
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


def _load_linter():
    spec = importlib.util.spec_from_file_location(
        "lint_api_doc", SKILL_DIR / "scripts" / "lint_api_doc.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["lint_api_doc"] = module
    spec.loader.exec_module(module)
    return module


LINT = _load_linter()


def _all_docs_lower() -> str:
    parts = [SKILL_MD]
    for f in sorted(REFS_DIR.glob("*.md")):
        parts.append(f.read_text(encoding="utf-8"))
    return "\n".join(parts).lower()


def _load_fixtures() -> list:
    return [json.loads(f.read_text(encoding="utf-8"))
            for f in sorted(GOLDEN_DIR.glob("*.json"))]


ALL_DOCS_LOWER = _all_docs_lower()
FIXTURES = _load_fixtures()
BY_ID = {f["id"]: f for f in FIXTURES}

# Derived from the skill, never hand-copied.
SCORECARD_TIERS = LINT._scorecard_tiers(SKILL_MD)
ITEM_TIER = {item: tier.lower()
             for tier, items in SCORECARD_TIERS.items() for item in items}
CHECKLIST, CHECKLIST_BODY = LINT._checklist_items(SKILL_MD)
DOC_ANCHORS = {
    m for path in [SKILL_DIR / "SKILL.md", *sorted(REFS_DIR.glob("*.md"))]
    for m in LINT.ANCHOR.findall(path.read_text(encoding="utf-8"))
}

VALID_TYPES = {"defect", "good_practice", "degradation_scenario", "workflow",
               "false_positive"}
NON_DEFECT_TYPES = VALID_TYPES - {"defect"}
VALID_SEVERITIES = {"critical", "standard", "hygiene", "none"}
REQUIRED_FIELDS = {
    "id", "title", "type", "severity", "code_snippet",
    "expected_feedback", "coverage_rules", "reference", "scorecard_item",
}

# Scorecard items no fixture exercises yet. Declared as data so the gap is
# falsifiable: adding or removing a fixture forces this set to be updated
# rather than letting "all fixtures pass" read as full coverage.
UNCOVERED_SCORECARD_ITEMS = {"H2", "H3"}


class TestFixtureIntegrity:
    def test_minimum_fixture_count(self):
        assert len(FIXTURES) >= 20

    def test_required_fields(self):
        for fix in FIXTURES:
            missing = REQUIRED_FIELDS - set(fix.keys())
            assert not missing, f"{fix['id']}: missing fields {missing}"

    def test_valid_types(self):
        for fix in FIXTURES:
            assert fix["type"] in VALID_TYPES, f"{fix['id']}: {fix['type']}"

    def test_valid_severities(self):
        for fix in FIXTURES:
            assert fix["severity"] in VALID_SEVERITIES

    def test_defect_severity_not_none(self):
        for fix in FIXTURES:
            if fix["type"] == "defect":
                assert fix["severity"] != "none"

    def test_non_defect_severity_none(self):
        for fix in FIXTURES:
            if fix["type"] in NON_DEFECT_TYPES:
                assert fix["severity"] == "none", \
                    f"{fix['id']} is {fix['type']} but severity={fix['severity']}"

    def test_non_defect_has_no_scorecard_item(self):
        for fix in FIXTURES:
            if fix["type"] in NON_DEFECT_TYPES:
                assert fix["scorecard_item"] is None

    def test_unique_ids(self):
        ids = [f["id"] for f in FIXTURES]
        assert len(ids) == len(set(ids))

    def test_coverage_rules_findable(self):
        for fix in FIXTURES:
            for rule in fix["coverage_rules"]:
                assert rule.lower() in ALL_DOCS_LOWER, \
                    f"{fix['id']}: coverage rule '{rule}' not found in docs"


class TestSeverityDerivedFromSkill:
    """The one check that catches tier drift: expectations come from SKILL.md."""

    def test_scorecard_parse_is_populated(self):
        assert len(ITEM_TIER) == 12, f"parsed {len(ITEM_TIER)} scorecard items"
        assert set(SCORECARD_TIERS) == {"Critical", "Standard", "Hygiene"}

    @pytest.mark.parametrize(
        "fixture_id", sorted(f["id"] for f in FIXTURES if f["type"] == "defect"))
    def test_defect_severity_matches_doc_tier(self, fixture_id):
        fix = BY_ID[fixture_id]
        item = fix["scorecard_item"]
        assert item in ITEM_TIER, \
            f"{fixture_id} cites scorecard item {item!r}, absent from SKILL.md §8"
        assert fix["severity"] == ITEM_TIER[item], (
            f"{fixture_id} declares severity {fix['severity']!r} but SKILL.md puts "
            f"{item} in the {ITEM_TIER[item]} tier")

    def test_cited_items_are_produced_by_a_checklist_rule(self):
        targets = {t for _, _, _, t in CHECKLIST}
        for fix in FIXTURES:
            if fix["scorecard_item"]:
                assert fix["scorecard_item"] in targets, (
                    f"{fix['id']} cites {fix['scorecard_item']}, which no §6 "
                    "checklist rule feeds")

    def test_uncovered_items_declared_accurately(self):
        covered = {f["scorecard_item"] for f in FIXTURES if f["scorecard_item"]}
        derived = set(ITEM_TIER) - covered
        assert derived == UNCOVERED_SCORECARD_ITEMS, (
            "fixture coverage changed; update UNCOVERED_SCORECARD_ITEMS. "
            f"derived={sorted(derived)} declared={sorted(UNCOVERED_SCORECARD_ITEMS)}")


class TestFalsePositiveFixtures:
    """Legal-but-unusual designs a reviewer must not report as defects."""

    FP = [f for f in FIXTURES if f["type"] == "false_positive"]

    def test_at_least_four_exist(self):
        assert len(self.FP) >= 5, "need FP coverage for the over-strict rules"

    def test_each_declares_what_must_not_be_flagged(self):
        for fix in self.FP:
            assert fix.get("must_not_flag"), f"{fix['id']}: empty must_not_flag"

    def test_each_cites_an_existing_license_anchor(self):
        for fix in self.FP:
            anchors = fix.get("licensed_by") or []
            assert anchors, f"{fix['id']}: no licensed_by anchor"
            for anchor in anchors:
                assert anchor in DOC_ANCHORS, (
                    f"{fix['id']} cites license anchor {anchor!r}, which no doc "
                    "declares — the clause legalising this design is gone")

    def test_expected_feedback_states_no_violation(self):
        for fix in self.FP:
            assert "no violation" in fix["expected_feedback"].lower()

    def test_expected_feedback_names_the_false_positive(self):
        for fix in self.FP:
            assert "false positive" in fix["expected_feedback"].lower(), \
                f"{fix['id']}: must say plainly which report would be wrong"

    def test_anchors_are_covered_by_a_fixture(self):
        cited = {a for fix in self.FP for a in fix.get("licensed_by", [])}
        assert LINT.REQUIRED_ANCHORS <= cited, (
            "license anchors with no fixture defending them: "
            f"{sorted(LINT.REQUIRED_ANCHORS - cited)}")


class TestFixturesObeyDocRules:
    """Exemplars are linted by the same instrument as the documentation."""

    @pytest.mark.parametrize("fixture_id", sorted(BY_ID))
    def test_no_refuted_claims_in_fixture_prose(self, fixture_id):
        fix = BY_ID[fixture_id]
        text = "\n".join([fix["title"], fix["expected_feedback"],
                          *(fix.get("must_not_flag") or [])])
        findings = LINT.check_claims(text, fixture_id)
        assert not findings, "\n".join(f"{f.rule}: {f.message}" for f in findings)


class TestCoverageDocIsAccurate:
    """COVERAGE.md numbers are derived, never hand-maintained."""

    COVERAGE = (pathlib.Path(__file__).resolve().parent / "COVERAGE.md").read_text(
        encoding="utf-8")

    def _declared(self) -> dict:
        block = re.search(r"<!-- coverage-counts\n(.*?)\n-->", self.COVERAGE, re.DOTALL)
        assert block, "COVERAGE.md has no machine-readable coverage-counts block"
        return {k.strip(): int(v) for k, v in
                (line.split(":") for line in block.group(1).strip().splitlines())}

    @staticmethod
    def _test_function_count(path: pathlib.Path) -> int:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        return sum(1 for n in ast.walk(tree)
                   if isinstance(n, ast.FunctionDef) and n.name.startswith("test_"))

    def test_declared_counts_match_reality(self):
        declared = self._declared()
        here = pathlib.Path(__file__).resolve().parent
        actual = {"linter_rules": len(LINT.RULES), "fixtures": len(FIXTURES)}
        for name in ("test_doc_lint.py", "test_golden_scenarios.py",
                     "test_skill_contract.py"):
            actual[name] = self._test_function_count(here / name)
        assert declared == actual, (
            f"COVERAGE.md is stale.\ndeclared={declared}\nactual={actual}")

    def test_force_class_counts_match_the_checklist(self):
        counts = collections.Counter(tag for _, tag, _, _ in CHECKLIST)
        table = {}
        for tag, listed in re.findall(
                r"^\|\s*`\[([PSDC])\]`[^|]*\|\s*(\d+)\s*\|", self.COVERAGE, re.MULTILINE):
            table[tag] = int(listed)
        assert table, "COVERAGE.md force-class table not parsed"
        assert table == dict(counts), (
            f"COVERAGE.md force-class counts {table} != checklist {dict(counts)}")

    def test_fixture_inventory_rows_match_the_fixtures(self):
        listed = set(re.findall(r"^\|\s*(API-\d+)\s*\|", self.COVERAGE, re.MULTILINE))
        assert listed == set(BY_ID), (
            f"COVERAGE.md inventory drift: only in doc={sorted(listed - set(BY_ID))}, "
            f"only in fixtures={sorted(set(BY_ID) - listed)}")

    def test_behavioural_limitation_is_stated(self):
        """The honest scope note is itself load-bearing; do not let it be dropped."""
        lower = self.COVERAGE.lower()
        assert "not behavioural evidence" in lower or \
               "none of these tests are behavioural evidence" in lower
        assert "no model is run" in lower


class TestDefectFixtureContent:
    """Per-fixture spot checks. These catch a gutted fixture, nothing more."""

    def test_api001_naming_is_hygiene_and_names_the_protocol_defect(self):
        fix = BY_ID["API-001"]
        fb = fix["expected_feedback"].lower()
        assert fix["severity"] == "hygiene"
        assert "noun" in fb or "verb" in fb
        assert "201" in fix["expected_feedback"], \
            "the [P] finding in this snippet is the missing 201/Location"

    @pytest.mark.parametrize(
        "fixture_id", sorted(f["id"] for f in FIXTURES if f["type"] == "defect"))
    def test_defect_states_a_verdict(self, fixture_id):
        """§8.1 turns (nature x condition x trigger) into a verdict. A fixture that
        never names the verdict cannot show the table was applied."""
        fb = BY_ID[fixture_id]["expected_feedback"]
        assert "FAIL" in fb or "WARN" in fb, \
            f"{fixture_id} reports a defect without saying whether it fails its item"

    def test_api001_convention_deviation_does_not_fail_its_item(self):
        """The regression this pins: a naming deviation with no live trigger is a
        WARN under §8.1, so H1 must still pass. Reporting it as a failure is the
        over-strict behaviour the nature/severity split exists to prevent."""
        fb = BY_ID["API-001"]["expected_feedback"]
        assert "WARN" in fb
        assert "H1 still passes" in fb, \
            "the fixture must state that the Hygiene item survives a bare convention miss"
        assert "FAIL" in fb, "the same snippet's [P] status-code defect does fail S1"

    def test_api002_error_transport(self):
        fix = BY_ID["API-002"]
        assert fix["scorecard_item"] == "C2"
        assert "200" in fix["expected_feedback"]

    def test_api003_machine_readable_code(self):
        fb = BY_ID["API-003"]["expected_feedback"].lower()
        assert "code" in fb and "machine" in fb

    def test_api004_names_its_risk_trigger(self):
        fix = BY_ID["API-004"]
        assert "T1" in fix["expected_feedback"], \
            "a trigger-dependent finding must name the trigger that makes it a FAIL"
        assert "retry" in fix["expected_feedback"].lower()

    def test_api017_covers_all_three_leak_channels(self):
        fb = BY_ID["API-017"]["expected_feedback"]
        for probe in ("metric", "audit", "T6"):
            assert probe in fb, f"C3 fixture must cover {probe}"

    def test_api018_does_not_demand_location(self):
        """201 without Location is [D]; the fixture must say so explicitly."""
        fb = BY_ID["API-018"]["expected_feedback"]
        assert "15.3.2" in fb and "[D]" in fb

    def test_api020_ties_severity_to_a_trigger(self):
        fb = BY_ID["API-020"]["expected_feedback"]
        assert "T5" in fb and "tie-breaker" in fb

    def test_api005_idor_is_critical(self):
        fix = BY_ID["API-005"]
        assert fix["scorecard_item"] == "C1"
        assert fix["severity"] == "critical"
        assert "idor" in fix["expected_feedback"].lower()

    def test_api006_uses_the_current_deprecation_syntax(self):
        fb = BY_ID["API-006"]["expected_feedback"]
        assert "RFC 9745" in fb
        assert "@1688169599" in fb, "must show the Structured Field Date form"
        assert "deprecation" in fb.lower()

    def test_api011_rate_limit_is_hygiene_and_trigger_gated(self):
        fix = BY_ID["API-011"]
        assert fix["severity"] == "hygiene"
        assert "T5" in fix["expected_feedback"]
        assert "429" in fix["expected_feedback"]


class TestNonDefectFixtureContent:
    def test_api007_good_practice(self):
        fb = BY_ID["API-007"]["expected_feedback"].lower()
        assert "no violation" in fb
        assert "etag" in fb or "idempotency" in fb or "concurrency" in fb

    def test_api008_pagination(self):
        fb = BY_ID["API-008"]["expected_feedback"].lower()
        assert "no violation" in fb
        assert "cursor" in fb

    def test_api009_degrades_instead_of_stopping(self):
        fb = BY_ID["API-009"]["expected_feedback"]
        lower = fb.lower()
        assert "minimal" in lower
        assert "must not" in lower or "not claim" in lower
        assert "n/a" in lower and "fail" in lower, \
            "unassessable items are N/A, never FAIL"
        assert "review" in lower, "Gate 1 mode is what licenses the degradation"

    def test_api010_workflow(self):
        fb = BY_ID["API-010"]["expected_feedback"].lower()
        assert "/orders" in fb or "resource" in fb
        assert "idempotency" in fb or "idempotent" in fb
