import json
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[2]
SKILL_MD = SKILL_DIR / "SKILL.md"
GOLDEN_DIR = SKILL_DIR / "scripts" / "tests" / "golden"
APP_REF = SKILL_DIR / "references" / "applicability-checklist.md"
TARGET_REF = SKILL_DIR / "references" / "target-priority.md"

ALL_REFS = [
    SKILL_MD,
    APP_REF,
    TARGET_REF,
    SKILL_DIR / "references" / "crash-handling.md",
    SKILL_DIR / "references" / "ci-strategy.md",
    SKILL_DIR / "references" / "anti-examples.md",
    SKILL_DIR / "references" / "advanced-tuning.md",
]


def load_fixture(name: str) -> dict:
    path = GOLDEN_DIR / name
    return json.loads(path.read_text())


def combined_text() -> str:
    return "\n".join(f.read_text() for f in ALL_REFS if f.exists())


class GoldenFixtureIntegrityTests(unittest.TestCase):
    def test_golden_directory_exists(self) -> None:
        self.assertTrue(GOLDEN_DIR.exists(), "golden directory missing")

    def test_expected_fixture_count(self) -> None:
        fixtures = list(GOLDEN_DIR.glob("*.json"))
        self.assertGreaterEqual(len(fixtures), 8, f"expected >=8 fixtures, got {len(fixtures)}")

    def test_all_fixtures_have_required_fields(self) -> None:
        required = {"id", "description", "code_snippet", "applicability_verdict", "skill_rules_that_must_fire"}
        for path in sorted(GOLDEN_DIR.glob("*.json")):
            data = json.loads(path.read_text())
            missing = required - set(data.keys())
            self.assertFalse(missing, f"{path.name} missing fields: {missing}")

    def test_suitable_fixtures_have_template(self) -> None:
        for path in sorted(GOLDEN_DIR.glob("*.json")):
            data = json.loads(path.read_text())
            if data["applicability_verdict"] == "suitable":
                self.assertIn("expected_template", data, f"{path.name} suitable but missing expected_template")
                self.assertIn("expected_fuzz_mode", data, f"{path.name} suitable but missing expected_fuzz_mode")

    def test_not_suitable_fixtures_have_alternative(self) -> None:
        for path in sorted(GOLDEN_DIR.glob("*.json")):
            data = json.loads(path.read_text())
            if data["applicability_verdict"] == "not_suitable":
                self.assertIn("expected_alternative", data, f"{path.name} not_suitable but missing expected_alternative")
                self.assertIn("failed_hard_stop", data, f"{path.name} not_suitable but missing failed_hard_stop")


class GoldenSuitableParserTests(unittest.TestCase):
    def test_001_parser_rules_coverage(self) -> None:
        data = load_fixture("001_parser_suitable.json")
        text = combined_text()
        for rule in data["skill_rules_that_must_fire"]:
            self.assertIn(rule, text, f"rule missing in skill text: {rule}")

    def test_001_template_a_referenced(self) -> None:
        data = load_fixture("001_parser_suitable.json")
        self.assertEqual(data["expected_template"], "Template A")
        self.assertIn("Template A: Parser", SKILL_MD.read_text())


class GoldenSuitableRoundtripTests(unittest.TestCase):
    def test_002_roundtrip_rules_coverage(self) -> None:
        data = load_fixture("002_roundtrip_suitable.json")
        text = combined_text()
        for rule in data["skill_rules_that_must_fire"]:
            self.assertIn(rule, text, f"rule missing in skill text: {rule}")

    def test_002_template_b_referenced(self) -> None:
        data = load_fixture("002_roundtrip_suitable.json")
        self.assertEqual(data["expected_template"], "Template B")
        self.assertIn("Template B: Round-Trip", SKILL_MD.read_text())


class GoldenSuitableDifferentialTests(unittest.TestCase):
    def test_003_differential_rules_coverage(self) -> None:
        data = load_fixture("003_differential_suitable.json")
        text = combined_text()
        for rule in data["skill_rules_that_must_fire"]:
            self.assertIn(rule, text, f"rule missing in skill text: {rule}")

    def test_003_template_c_referenced(self) -> None:
        data = load_fixture("003_differential_suitable.json")
        self.assertEqual(data["expected_template"], "Template C")


class GoldenSuitableStructAwareTests(unittest.TestCase):
    def test_004_struct_aware_rules_coverage(self) -> None:
        data = load_fixture("004_struct_aware_suitable.json")
        text = combined_text()
        for rule in data["skill_rules_that_must_fire"]:
            self.assertIn(rule, text, f"rule missing in skill text: {rule}")

    def test_004_template_d_referenced(self) -> None:
        data = load_fixture("004_struct_aware_suitable.json")
        self.assertEqual(data["expected_template"], "Template D")


class GoldenNotSuitableTrivialTests(unittest.TestCase):
    def test_005_trivial_hard_stop(self) -> None:
        data = load_fixture("005_trivial_not_suitable.json")
        self.assertEqual(data["applicability_verdict"], "not_suitable")
        self.assertEqual(data["failed_hard_stop"], "1")

    def test_005_alternative_suggested(self) -> None:
        data = load_fixture("005_trivial_not_suitable.json")
        self.assertIn("unit tests", data["expected_alternative"])


class GoldenNotSuitableNoOracleTests(unittest.TestCase):
    def test_006_no_oracle_hard_stop(self) -> None:
        data = load_fixture("006_no_oracle_not_suitable.json")
        self.assertEqual(data["applicability_verdict"], "not_suitable")
        self.assertEqual(data["failed_hard_stop"], "3")

    def test_006_rules_coverage(self) -> None:
        data = load_fixture("006_no_oracle_not_suitable.json")
        text = combined_text()
        for rule in data["skill_rules_that_must_fire"]:
            self.assertIn(rule, text, f"rule missing: {rule}")


class GoldenNotSuitableDbTests(unittest.TestCase):
    def test_007_db_dependent_hard_stop(self) -> None:
        data = load_fixture("007_db_dependent_not_suitable.json")
        self.assertEqual(data["applicability_verdict"], "not_suitable")
        self.assertEqual(data["failed_hard_stop"], "2")

    def test_007_rules_coverage(self) -> None:
        data = load_fixture("007_db_dependent_not_suitable.json")
        text = combined_text()
        for rule in data["skill_rules_that_must_fire"]:
            self.assertIn(rule, text, f"rule missing: {rule}")


class GoldenValidatorRaceTests(unittest.TestCase):
    def test_008_race_features(self) -> None:
        data = load_fixture("008_validator_with_race.json")
        self.assertEqual(data["applicability_verdict"], "suitable")
        self.assertIn("race detection", data.get("advanced_features", []))

    def test_008_rules_coverage(self) -> None:
        data = load_fixture("008_validator_with_race.json")
        text = combined_text()
        for rule in data["skill_rules_that_must_fire"]:
            self.assertIn(rule, text, f"rule missing: {rule}")


class GoldenCrashHandlingTests(unittest.TestCase):
    def test_009_crash_steps_documented(self) -> None:
        data = load_fixture("009_crash_handling_workflow.json")
        skill = SKILL_MD.read_text()
        crash = (SKILL_DIR / "references" / "crash-handling.md").read_text()
        self.assertEqual(data["workflow_type"], "crash_handling")
        # Every declared crash step must be reachable from the skill's own workflow.
        anchors = {
            "retain_corpus": "retain corpus under",
            "record_failure_type": "Record failure type",
            "fix_minimal": "Fix with minimal code change",
            "rerun_regression": "Re-run corpus regression",
            "report_root_cause": "Report root cause",
        }
        for step in data["expected_crash_steps"]:
            self.assertIn(step, anchors, f"fixture declares unknown crash step: {step}")
            self.assertIn(anchors[step], skill + crash,
                          f"crash step {step} has no anchor in SKILL.md/crash-handling.md")


class GoldenCiIntegrationTests(unittest.TestCase):
    def test_010_both_lanes_documented(self) -> None:
        data = load_fixture("010_ci_integration_workflow.json")
        ci = (SKILL_DIR / "references" / "ci-strategy.md").read_text()
        for lane in data["expected_ci_lanes"]:
            self.assertIn(lane, ci, f"CI lane missing from ci-strategy.md: {lane}")


class GoldenBorderlineTests(unittest.TestCase):
    def test_011_check4_is_warn_not_fail(self) -> None:
        data = load_fixture("011_borderline_soft_warning.json")
        self.assertEqual("Warn", data["expected_checks"]["deterministic_local"])
        self.assertEqual("suitable", data["applicability_verdict"])

    def test_011_check4_never_a_hard_stop(self) -> None:
        """Regression guard: checks 4 and 5 must stay soft warnings in BOTH documents."""
        skill = SKILL_MD.read_text()
        ref = APP_REF.read_text()
        self.assertIn("Soft Warnings (proceed with caution)", ref)
        self.assertIn("soft warnings", skill.lower(),
                      "SKILL.md must state that checks 4/5 are soft warnings, not hard stops")


class GoldenGoFuzzHeadersTests(unittest.TestCase):
    def test_012_high_skip_rate_routes_to_structured_bridge(self) -> None:
        data = load_fixture("012_go_fuzz_headers_suitable.json")
        skill = SKILL_MD.read_text()
        self.assertEqual("go-fuzz-headers", data["deserialization_method"])
        self.assertEqual("Template D", data["expected_template"])
        # The skill must document the bridge and the skip-rate threshold that triggers it.
        self.assertIn("GenerateStruct", skill)
        self.assertIn("skip rate", skill.lower())

    def test_012_skip_rate_threshold_is_stated(self) -> None:
        skill = SKILL_MD.read_text()
        self.assertIn("50%", skill,
                      "skill must state the skip-rate threshold that forces a seed rethink")


class GoldenHardStopConsistencyTests(unittest.TestCase):
    """The two documents disagreed on whether check 1 is blocking. Pin them together."""

    def test_hard_stop_items_agree_across_documents(self) -> None:
        skill = SKILL_MD.read_text()
        ref = APP_REF.read_text()
        for item in ("1", "2", "3"):
            self.assertRegex(
                skill, rf"\|\s*`?{item}`?\s",
                f"SKILL.md hard-stop table must list blocking item {item}",
            )
            self.assertIn(f"If `{item}` fails: **stop**", ref,
                          f"applicability-checklist.md must hard-stop on item {item}")

    def test_skill_md_no_longer_limits_hard_stop_to_2_or_3(self) -> None:
        skill = SKILL_MD.read_text()
        self.assertNotIn("If item `2` or `3` fails", skill,
                         "stale rule: check 1 must also be a hard stop")


class GoldenVersionGateTests(unittest.TestCase):
    def test_013_low_go_directive_is_not_a_hard_stop(self) -> None:
        data = load_fixture("013_go_directive_low_toolchain_modern.json")
        self.assertEqual("suitable", data["applicability_verdict"])
        self.assertTrue(data["version_gate"]["must_not_hard_stop"])
        self.assertEqual("proceed", data["version_gate"]["gate_decision"])

    def test_015_old_toolchain_is_a_hard_stop(self) -> None:
        data = load_fixture("015_toolchain_below_118_hard_stop.json")
        self.assertEqual("not_suitable", data["applicability_verdict"])
        self.assertEqual("hard_stop", data["version_gate"]["gate_decision"])
        self.assertEqual("Go Version Gate", data["failed_hard_stop"])

    def test_gate_keys_on_toolchain_not_go_directive(self) -> None:
        """Regression guard for the corrected gate: `testing.F` availability is decided by
        the toolchain. Verified empirically — a `go 1.16` module fuzzes under Go 1.25."""
        skill = SKILL_MD.read_text()
        self.assertIn("Gate on the toolchain that will actually run the tests", skill)
        self.assertIn("go version", skill)
        self.assertIn("GOTOOLCHAIN", skill)
        self.assertIn("note, not a stop", skill,
                      "a low `go` directive must be a note, not a hard stop")

    def test_two_version_fixtures_cover_both_outcomes(self) -> None:
        outcomes = set()
        for path in sorted(GOLDEN_DIR.glob("*.json")):
            data = json.loads(path.read_text())
            if "version_gate" in data:
                outcomes.add(data["version_gate"]["gate_decision"])
        self.assertEqual({"proceed", "hard_stop"}, outcomes,
                         "version gate needs one proceed fixture and one hard-stop fixture")


class GoldenCorpusLocationTests(unittest.TestCase):
    def test_014_interesting_corpus_is_in_gocache(self) -> None:
        data = load_fixture("014_corpus_management_degradation.json")
        loc = data["corpus_location"]
        self.assertEqual("$GOCACHE/fuzz", loc["interesting_inputs"])
        self.assertTrue(loc["must_correct_user_premise"])
        self.assertFalse(data["expected_corpus_actions"]["commit_all_auto_generated"])

    def test_skill_states_testdata_is_failure_only(self) -> None:
        """Regression guard: the skill must not imply coverage corpus accumulates in
        testdata/fuzz. Verified empirically — a clean run creates no testdata/ at all."""
        skill = SKILL_MD.read_text()
        self.assertIn("only on failure", skill)
        self.assertIn("$GOCACHE/fuzz", skill)

    def test_ci_caches_gocache_not_testdata(self) -> None:
        ci = (SKILL_DIR / "references" / "ci-strategy.md").read_text()
        self.assertIn("go env GOCACHE", ci)
        self.assertNotIn("path: testdata/fuzz\n", ci,
                         "caching testdata/fuzz cannot accumulate corpus — cache $GOCACHE/fuzz")

    def test_ci_schedule_is_top_level(self) -> None:
        """`schedule` is a workflow trigger, never a job key."""
        ci = (SKILL_DIR / "references" / "ci-strategy.md").read_text()
        self.assertIn("MUST be top-level `on:`", ci)
        self.assertRegex(ci, r"(?m)^on:\n(?:.*\n)*?  schedule:",
                         "ci-strategy.md must show schedule under a top-level `on:`")


class GoldenFixtureScenarioCoverageTests(unittest.TestCase):
    """Every fixture must have a scenario-specific test class, not just the generic
    integrity sweep. This is what was missing for 009-015."""

    def test_every_fixture_is_referenced_by_a_test(self) -> None:
        source = Path(__file__).read_text()
        missing = [
            path.name for path in sorted(GOLDEN_DIR.glob("*.json"))
            if path.name not in source
        ]
        self.assertFalse(missing, f"fixtures with no scenario-specific test: {missing}")


if __name__ == "__main__":
    unittest.main()
