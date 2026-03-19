import json
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[2]
SKILL_MD = SKILL_DIR / "SKILL.md"
GOLDEN_DIR = Path(__file__).resolve().parent / "golden"
TEMPLATES_REF = SKILL_DIR / "references" / "templates.md"
GOLDEN_REF = SKILL_DIR / "references" / "golden-examples.md"
CHECKLIST_REF = SKILL_DIR / "references" / "checklist.md"


def load_fixture(name: str) -> dict:
    with open(GOLDEN_DIR / name) as f:
        return json.load(f)


def skill_text() -> str:
    return SKILL_MD.read_text()


# ── Infrastructure ──────────────────────────────────────────────

class TestGoldenInfrastructure(unittest.TestCase):
    def test_golden_dir_exists(self):
        self.assertTrue(GOLDEN_DIR.exists())

    def test_minimum_fixture_count(self):
        fixtures = list(GOLDEN_DIR.glob("*.json"))
        self.assertGreaterEqual(len(fixtures), 9, f"only {len(fixtures)} golden fixtures")

    def test_all_fixtures_valid_json(self):
        for f in GOLDEN_DIR.glob("*.json"):
            with open(f) as fh:
                data = json.load(fh)
            self.assertIn("id", data, f"{f.name} missing 'id'")
            self.assertIn("description", data, f"{f.name} missing 'description'")
            self.assertIn("repo_signals", data, f"{f.name} missing 'repo_signals'")
            self.assertIn("skill_rules_that_must_fire", data, f"{f.name} missing 'skill_rules_that_must_fire'")

    def test_all_fixtures_have_project_type(self):
        for f in GOLDEN_DIR.glob("*.json"):
            with open(f) as fh:
                data = json.load(fh)
            self.assertIn("project_type", data["repo_signals"],
                          f"{f.name} missing project_type in repo_signals")


# ── 001: Go Service Full ───────────────────────────────────────

class TestGoServiceFull(unittest.TestCase):
    def setUp(self):
        self.fix = load_fixture("001_go_service_full.json")

    def test_template_is_service(self):
        self.assertEqual(self.fix["expected_template"], "Template A: Service")
        self.assertIn("Template A: Service", TEMPLATES_REF.read_text())

    def test_all_expected_sections(self):
        self.assertGreaterEqual(len(self.fix["expected_sections"]), 8)

    def test_badge_types(self):
        self.assertEqual(len(self.fix["expected_badge_types"]), 4)
        for bt in self.fix["expected_badge_types"]:
            self.assertIn(bt.lower(), skill_text().lower())

    def test_rules_fire(self):
        data = skill_text().lower()
        for rule in self.fix["skill_rules_that_must_fire"]:
            key = rule.split("→")[0].strip().lower()
            self.assertIn(key, data, f"rule concept missing: {key}")

    def test_golden_example_exists(self):
        golden = GOLDEN_REF.read_text()
        self.assertIn("Go Service", golden)


# ── 002: Go Library ────────────────────────────────────────────

class TestGoLibrary(unittest.TestCase):
    def setUp(self):
        self.fix = load_fixture("002_go_library.json")

    def test_template_is_library(self):
        self.assertEqual(self.fix["expected_template"], "Template B: Library")
        self.assertIn("Template B: Library", TEMPLATES_REF.read_text())

    def test_has_installation_section(self):
        self.assertIn("Installation", self.fix["expected_sections"])

    def test_has_api_overview(self):
        self.assertIn("API Overview", self.fix["expected_sections"])

    def test_no_makefile_command_priority(self):
        rules = " ".join(self.fix["skill_rules_that_must_fire"])
        self.assertIn("no Makefile", rules)


# ── 003: CLI Tool ──────────────────────────────────────────────

class TestCLITool(unittest.TestCase):
    def setUp(self):
        self.fix = load_fixture("003_cli_tool.json")

    def test_template_is_cli(self):
        self.assertEqual(self.fix["expected_template"], "Template C: CLI Tool")

    def test_e2e_rule_fires(self):
        rules = " ".join(self.fix["skill_rules_that_must_fire"])
        self.assertIn("End-to-End Example Rule", rules)
        self.assertIn("End-to-End Example Rule", skill_text())

    def test_has_flags_section(self):
        self.assertIn("Flags", self.fix["expected_sections"])

    def test_has_commands_section(self):
        self.assertIn("Commands", self.fix["expected_sections"])


# ── 004: Monorepo ──────────────────────────────────────────────

class TestMonorepo(unittest.TestCase):
    def setUp(self):
        self.fix = load_fixture("004_monorepo.json")

    def test_template_is_monorepo(self):
        self.assertEqual(self.fix["expected_template"], "Template D: Monorepo")

    def test_monorepo_rules_fire(self):
        rules = " ".join(self.fix["skill_rules_that_must_fire"])
        self.assertIn("Monorepo Rules", rules)
        self.assertIn("Monorepo Rules", skill_text())

    def test_license_missing_note(self):
        rules = " ".join(self.fix["skill_rules_that_must_fire"])
        self.assertIn("LICENSE missing note", rules)
        self.assertIn("Not found in repo", skill_text())

    def test_has_overview_table(self):
        self.assertIn("Repository Overview", self.fix["expected_sections"])


# ── 005: Lightweight Internal ──────────────────────────────────

class TestLightweightInternal(unittest.TestCase):
    def setUp(self):
        self.fix = load_fixture("005_lightweight_internal.json")

    def test_template_is_lightweight(self):
        self.assertEqual(self.fix["expected_template"], "Template E: Lightweight")

    def test_lightweight_mode_triggers(self):
        rules = " ".join(self.fix["skill_rules_that_must_fire"])
        self.assertIn("Lightweight Template Mode", rules)
        self.assertIn("Lightweight Template Mode", skill_text())

    def test_no_badges(self):
        self.assertEqual(self.fix["expected_badge_types"], [])

    def test_absent_sections(self):
        self.assertIn("sections_that_must_be_absent", self.fix)
        absent = self.fix["sections_that_must_be_absent"]
        self.assertGreaterEqual(len(absent), 4)

    def test_golden_example_exists(self):
        golden = GOLDEN_REF.read_text()
        self.assertIn("Lightweight", golden)


# ── 006: Private Service ───────────────────────────────────────

class TestPrivateService(unittest.TestCase):
    def setUp(self):
        self.fix = load_fixture("006_private_service.json")

    def test_badge_fallback_required(self):
        self.assertTrue(self.fix["badge_fallback_required"])

    def test_no_external_badges(self):
        self.assertEqual(self.fix["expected_badge_types"], [])

    def test_private_repo_rule(self):
        rules = " ".join(self.fix["skill_rules_that_must_fire"])
        self.assertIn("private-repo fallback", rules)
        self.assertIn("Badge note: repository is private", skill_text())


# ── 007: Chinese README ───────────────────────────────────────

class TestChineseReadme(unittest.TestCase):
    def setUp(self):
        self.fix = load_fixture("007_chinese_readme.json")

    def test_language_is_chinese(self):
        self.assertEqual(self.fix["expected_language"], "Chinese")

    def test_chinese_rules_present(self):
        self.assertGreaterEqual(len(self.fix["chinese_rules"]), 4)

    def test_chinese_guidelines_in_skill(self):
        self.assertIn("Chinese / Bilingual README Guidelines", skill_text())

    def test_no_double_headings_rule(self):
        rules = self.fix["chinese_rules"]
        has_double = any("double" in r.lower() for r in rules)
        self.assertTrue(has_double, "missing no-double-heading rule")


# ── 008: Refactor Stale README ─────────────────────────────────

class TestRefactorStale(unittest.TestCase):
    def setUp(self):
        self.fix = load_fixture("008_refactor_stale_readme.json")

    def test_has_existing_issues(self):
        issues = self.fix["repo_signals"]["existing_readme_issues"]
        self.assertGreaterEqual(len(issues), 3)

    def test_expected_actions(self):
        actions = self.fix["expected_actions"]
        self.assertGreaterEqual(len(actions), 4)
        action_text = " ".join(actions).lower()
        self.assertIn("preserve", action_text)
        self.assertIn("fix", action_text)

    def test_refactoring_checklist_exists(self):
        self.assertIn("Refactoring Existing README", CHECKLIST_REF.read_text())

    def test_rules_fire(self):
        rules = " ".join(self.fix["skill_rules_that_must_fire"])
        self.assertIn("Refactoring Existing README", rules)
        self.assertIn("3-Tier Scorecard", rules)


# ── 009: Degraded No Build ─────────────────────────────────────

class TestDegradedNoBuild(unittest.TestCase):
    def setUp(self):
        self.fix = load_fixture("009_degraded_no_build.json")

    def test_project_type_unknown(self):
        self.assertEqual(self.fix["repo_signals"]["project_type"], "unknown")

    def test_degraded_output(self):
        self.assertTrue(self.fix["expected_output_fields"]["degraded"])

    def test_missing_evidence_listed(self):
        missing = self.fix["expected_output_fields"]["missing_evidence"]
        self.assertGreaterEqual(len(missing), 2)

    def test_evidence_gate_fires(self):
        rules = " ".join(self.fix["skill_rules_that_must_fire"])
        self.assertIn("Evidence Completeness Gate", rules)

    def test_output_contract_degraded(self):
        rules = " ".join(self.fix["skill_rules_that_must_fire"])
        self.assertIn("Output Contract", rules)
        self.assertIn("degraded", rules)

    def test_skill_has_degraded_rule(self):
        data = skill_text()
        self.assertIn("degraded", data.lower())
        self.assertIn("Evidence Completeness Gate", data)


if __name__ == "__main__":
    unittest.main()

