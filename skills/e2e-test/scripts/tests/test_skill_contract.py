import re
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[2]
SKILL_MD = SKILL_DIR / "SKILL.md"
REFS_DIR = SKILL_DIR / "references"


def frontmatter(text: str) -> str:
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        raise AssertionError("missing yaml frontmatter")
    return match.group(1)


class TestFrontmatter(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skill_text = SKILL_MD.read_text()
        cls.fm = frontmatter(cls.skill_text)

    def test_name_is_hyphen_case(self) -> None:
        name_match = re.search(r"^name:\s*(.+)$", self.fm, re.MULTILINE)
        self.assertIsNotNone(name_match, "missing name in frontmatter")
        self.assertEqual("e2e-test", name_match.group(1).strip())

    def test_description_contains_trigger_keywords(self) -> None:
        desc = self.fm.lower()
        for keyword in ["e2e", "playwright", "agent browser", "flaky", "ci"]:
            self.assertIn(keyword, desc, f"description missing trigger keyword: {keyword}")

    def test_description_length(self) -> None:
        desc_match = re.search(r"description:\s*[\"'](.+?)[\"']", self.fm, re.DOTALL)
        self.assertIsNotNone(desc_match, "missing description")
        self.assertGreater(len(desc_match.group(1)), 50, "description too short")


class TestMandatoryGates(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skill_text = SKILL_MD.read_text()

    def test_configuration_gate(self) -> None:
        self.assertIn("Configuration Gate", self.skill_text)
        self.assertIn("do not invent them", self.skill_text)

    def test_environment_gate(self) -> None:
        self.assertIn("Environment Gate", self.skill_text)
        self.assertIn("target environment", self.skill_text)

    def test_execution_integrity_gate(self) -> None:
        self.assertIn("Execution Integrity Gate", self.skill_text)
        self.assertIn("Not run in this environment", self.skill_text)

    def test_stability_gate(self) -> None:
        self.assertIn("Stability Gate", self.skill_text)
        self.assertIn("repeat runs", self.skill_text)

    def test_side_effect_gate(self) -> None:
        self.assertIn("Side-Effect Gate", self.skill_text)
        self.assertIn("production data mutation", self.skill_text)

    def test_gates_are_serial(self) -> None:
        text = self.skill_text
        config_pos = text.index("Configuration Gate")
        env_pos = text.index("Environment Gate")
        exec_pos = text.index("Execution Integrity Gate")
        self.assertLess(config_pos, env_pos)
        self.assertLess(env_pos, exec_pos)


class TestAntiExamples(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skill_text = SKILL_MD.read_text()

    def test_anti_examples_section_exists(self) -> None:
        self.assertIn("Anti-Examples", self.skill_text)

    def test_anti_example_count(self) -> None:
        count = self.skill_text.count("### ")
        sections_with_bad_good = len(re.findall(r"BAD:\n```", self.skill_text))
        self.assertGreaterEqual(sections_with_bad_good, 7, "need at least 7 BAD/GOOD anti-examples")

    def test_sleep_anti_example(self) -> None:
        self.assertIn("waitForTimeout", self.skill_text)

    def test_css_chain_anti_example(self) -> None:
        self.assertIn("Fragile CSS selector", self.skill_text)

    def test_shared_data_anti_example(self) -> None:
        self.assertIn("Shared mutable data", self.skill_text)

    def test_storage_state_anti_example(self) -> None:
        self.assertIn("storageState", self.skill_text)

    def test_serial_anti_example(self) -> None:
        self.assertIn("Silently serializing", self.skill_text)

    def test_guessing_secrets_anti_example(self) -> None:
        self.assertIn("Guessing env values", self.skill_text)


class TestQualityScorecard(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skill_text = SKILL_MD.read_text()

    def test_scorecard_section_exists(self) -> None:
        self.assertIn("## Quality Scorecard", self.skill_text)

    def test_critical_tier(self) -> None:
        self.assertIn("### Critical", self.skill_text)
        self.assertTrue(
            "any FAIL" in self.skill_text or "any fail" in self.skill_text.lower(),
            "Critical tier must mention 'any FAIL' rule",
        )

    def test_standard_tier(self) -> None:
        self.assertIn("### Standard", self.skill_text)

    def test_hygiene_tier(self) -> None:
        self.assertIn("### Hygiene", self.skill_text)

    def test_critical_items(self) -> None:
        for item in ["C1", "C2", "C3", "C4"]:
            self.assertIn(item, self.skill_text)

    def test_standard_items(self) -> None:
        for item in ["S1", "S2", "S3", "S4", "S5", "S6"]:
            self.assertIn(item, self.skill_text)

    def test_hygiene_items(self) -> None:
        for item in ["H1", "H2", "H3", "H4"]:
            self.assertIn(item, self.skill_text)


class TestVersionGate(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skill_text = SKILL_MD.read_text()

    def test_version_gate_section(self) -> None:
        self.assertIn("Version and Platform Gate", self.skill_text)

    def test_playwright_version_rules(self) -> None:
        self.assertIn("< 1.27", self.skill_text)
        self.assertIn("< 1.30", self.skill_text)
        self.assertIn("< 1.35", self.skill_text)

    def test_node_version_rules(self) -> None:
        self.assertIn("< 16", self.skill_text)
        self.assertIn("< 18", self.skill_text)

    def test_framework_adaptation(self) -> None:
        for fw in ["Next.js", "SPA", "SSR", "Monorepo"]:
            self.assertIn(fw, self.skill_text)


class TestOutputContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skill_text = SKILL_MD.read_text()

    def test_all_output_fields(self) -> None:
        for field in [
            "`Task type`",
            "`Runner choice`",
            "`Environment gate`",
            "`Config/dependency status`",
            "`Executed commands`",
            "`Execution status`",
            "`Artifacts`",
            "`Next actions`",
        ]:
            self.assertIn(field, self.skill_text)

    def test_conditional_code_output(self) -> None:
        self.assertIn("files created or updated", self.skill_text)
        self.assertIn("skip conditions", self.skill_text)


class TestRunnerStrategy(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skill_text = SKILL_MD.read_text()

    def test_dual_tool_strategy(self) -> None:
        self.assertIn("Agent Browser first", self.skill_text)
        self.assertIn("Playwright preferred for code", self.skill_text)

    def test_bridge_workflow(self) -> None:
        self.assertIn("Agent Browser Bridge", self.skill_text)
        self.assertIn("translate the validated flow into Playwright", self.skill_text)


class TestPlaywrightRules(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skill_text = SKILL_MD.read_text()

    def test_playwright_first_section(self) -> None:
        self.assertIn("Playwright-First Engineering Rules", self.skill_text)

    def test_key_concepts(self) -> None:
        for concept in ["storageState", "serial vs parallel", "data per test"]:
            self.assertIn(concept, self.skill_text)


class TestFlakyPolicy(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skill_text = SKILL_MD.read_text()

    def test_flaky_section(self) -> None:
        self.assertIn("Flaky Test Policy", self.skill_text)

    def test_triage_sequence(self) -> None:
        self.assertIn("classify root cause", self.skill_text)
        self.assertIn("quarantine only with owner", self.skill_text)

    def test_root_cause_categories(self) -> None:
        for cat in ["selector instability", "async race", "test-data coupling", "environment drift"]:
            self.assertIn(cat, self.skill_text)


class TestReferenceFiles(unittest.TestCase):
    def test_all_reference_files_exist(self) -> None:
        expected = [
            "checklists.md",
            "playwright-patterns.md",
            "playwright-deep-patterns.md",
            "environment-and-dependency-gates.md",
            "agent-browser-workflows.md",
            "golden-examples.md",
        ]
        for fname in expected:
            self.assertTrue((REFS_DIR / fname).exists(), f"missing reference: {fname}")

    def test_reference_minimum_depth(self) -> None:
        for fname in REFS_DIR.glob("*.md"):
            lines = fname.read_text().count("\n")
            self.assertGreater(lines, 30, f"{fname.name} too shallow ({lines} lines)")

    def test_playwright_patterns_has_code(self) -> None:
        text = (REFS_DIR / "playwright-patterns.md").read_text()
        self.assertIn("```ts", text, "playwright-patterns.md must have TypeScript examples")
        self.assertIn("getByRole", text)
        self.assertIn("defineConfig", text)

    def test_playwright_deep_has_auth_example(self) -> None:
        text = (REFS_DIR / "playwright-deep-patterns.md").read_text()
        self.assertIn("storageState", text)
        self.assertIn("globalSetup", text)

    def test_playwright_deep_has_fixture_example(self) -> None:
        text = (REFS_DIR / "playwright-deep-patterns.md").read_text()
        self.assertIn("base.extend", text)

    def test_playwright_deep_has_mock_example(self) -> None:
        text = (REFS_DIR / "playwright-deep-patterns.md").read_text()
        self.assertIn("page.route", text)

    def test_playwright_deep_has_ci_strategy(self) -> None:
        text = (REFS_DIR / "playwright-deep-patterns.md").read_text()
        self.assertIn("shard", text)
        self.assertIn("upload-artifact", text)

    def test_golden_examples_has_code(self) -> None:
        text = (REFS_DIR / "golden-examples.md").read_text()
        self.assertIn("```ts", text)
        self.assertGreaterEqual(text.count("```ts"), 3, "golden-examples needs ≥ 3 code blocks")

    def test_golden_examples_covers_all_types(self) -> None:
        text = (REFS_DIR / "golden-examples.md").read_text()
        for t in ["Runnable Playwright", "Honest Scaffold", "Flaky Triage", "CI Gate", "Agent Browser"]:
            self.assertIn(t, text)

    def test_env_gates_has_flowchart(self) -> None:
        text = (REFS_DIR / "environment-and-dependency-gates.md").read_text()
        self.assertIn("Flowchart", text)

    def test_env_gates_has_stop_conditions(self) -> None:
        text = (REFS_DIR / "environment-and-dependency-gates.md").read_text()
        self.assertIn("Stop Conditions", text)
        self.assertIn("No base URL", text)

    def test_checklists_has_all_sections(self) -> None:
        text = (REFS_DIR / "checklists.md").read_text()
        for section in ["Pre-Run", "Critical Journey", "Code Review", "Flaky Triage", "Quarantine", "CI Gate"]:
            self.assertIn(section, text)

    def test_agent_browser_has_bridge(self) -> None:
        text = (REFS_DIR / "agent-browser-workflows.md").read_text()
        self.assertIn("Bridge To Playwright", text)

    def test_agent_browser_has_command_reference(self) -> None:
        text = (REFS_DIR / "agent-browser-workflows.md").read_text()
        self.assertIn("Command Reference", text)
        self.assertIn("agent-browser open", text)
        self.assertIn("agent-browser snapshot", text)


class TestSelectiveLoading(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skill_text = SKILL_MD.read_text()

    def test_load_references_section(self) -> None:
        self.assertIn("Load References Selectively", self.skill_text)

    def test_each_reference_has_loading_condition(self) -> None:
        section_start = self.skill_text.index("Load References Selectively")
        section_end = self.skill_text.index("## Runner Strategy")
        section = self.skill_text[section_start:section_end]
        for fname in [
            "checklists.md",
            "playwright-patterns.md",
            "playwright-deep-patterns.md",
            "environment-and-dependency-gates.md",
            "agent-browser-workflows.md",
            "golden-examples.md",
        ]:
            self.assertIn(fname, section)


class TestAccessibilityContent(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.deep = (REFS_DIR / "playwright-deep-patterns.md").read_text()

    def test_a11y_section_exists(self) -> None:
        self.assertIn("Accessibility Testing", self.deep)

    def test_axe_core_integration(self) -> None:
        self.assertIn("@axe-core/playwright", self.deep)
        self.assertIn("AxeBuilder", self.deep)

    def test_wcag_tags(self) -> None:
        self.assertIn("wcag2a", self.deep)
        self.assertIn("wcag2aa", self.deep)

    def test_scoped_analysis(self) -> None:
        self.assertIn(".include(", self.deep)
        self.assertIn(".exclude(", self.deep)

    def test_journey_integrated_a11y(self) -> None:
        self.assertIn("milestone", self.deep.lower())

    def test_common_violations_table(self) -> None:
        self.assertIn("Missing form labels", self.deep)
        self.assertIn("color contrast", self.deep)


class TestVisualRegressionContent(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.deep = (REFS_DIR / "playwright-deep-patterns.md").read_text()

    def test_visual_section_exists(self) -> None:
        self.assertIn("Visual Regression", self.deep)

    def test_screenshot_comparison(self) -> None:
        self.assertIn("toHaveScreenshot", self.deep)
        self.assertIn("maxDiffPixelRatio", self.deep)

    def test_dynamic_content_masking(self) -> None:
        self.assertIn("mask:", self.deep)

    def test_baseline_workflow(self) -> None:
        self.assertIn("--update-snapshots", self.deep)

    def test_threshold_strategy(self) -> None:
        self.assertIn("Threshold Strategy", self.deep)

    def test_external_services(self) -> None:
        self.assertIn("Percy", self.deep)
        self.assertIn("Chromatic", self.deep)


class TestMobileDesktopContent(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.deep = (REFS_DIR / "playwright-deep-patterns.md").read_text()

    def test_mobile_section_exists(self) -> None:
        self.assertIn("Mobile and Desktop E2E", self.deep)

    def test_device_emulation(self) -> None:
        self.assertIn("devices['Pixel", self.deep)
        self.assertIn("devices['iPhone", self.deep)

    def test_responsive_breakpoints(self) -> None:
        self.assertIn("BREAKPOINTS", self.deep)
        self.assertIn("viewport", self.deep)

    def test_electron_support(self) -> None:
        self.assertIn("_electron", self.deep)
        self.assertIn("electron.launch", self.deep)

    def test_react_native_web(self) -> None:
        self.assertIn("React Native Web", self.deep)

    def test_geolocation(self) -> None:
        self.assertIn("geolocation", self.deep)

    def test_platform_decision_matrix(self) -> None:
        self.assertIn("Platform Decision Matrix", self.deep)
        self.assertIn("Detox", self.deep)


class TestDiscoverScript(unittest.TestCase):
    def test_script_exists(self) -> None:
        script = SKILL_DIR / "scripts" / "discover_e2e_needs.sh"
        self.assertTrue(script.exists())

    def test_script_is_executable(self) -> None:
        import os
        script = SKILL_DIR / "scripts" / "discover_e2e_needs.sh"
        self.assertTrue(os.access(script, os.X_OK))

    def test_script_referenced_in_skill(self) -> None:
        skill_text = SKILL_MD.read_text()
        self.assertIn("discover_e2e_needs.sh", skill_text)

    def test_script_covers_key_checks(self) -> None:
        text = (SKILL_DIR / "scripts" / "discover_e2e_needs.sh").read_text()
        for check in ["playwright", "node", "framework", "existing_tests", "environment", "ci"]:
            self.assertIn(check, text)


class TestJsonOutput(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skill_text = SKILL_MD.read_text()

    def test_json_output_section(self) -> None:
        self.assertIn("Machine-Readable Summary", self.skill_text)

    def test_json_has_key_fields(self) -> None:
        for field in ["task_type", "runner", "execution_status", "scorecard", "blockers"]:
            self.assertIn(field, self.skill_text)


class TestGoldenExamplesTOC(unittest.TestCase):
    def test_toc_exists(self) -> None:
        text = (REFS_DIR / "golden-examples.md").read_text()
        self.assertIn("Table of Contents", text)


if __name__ == "__main__":
    unittest.main()
