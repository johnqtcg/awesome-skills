import re
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[2]
SKILL_MD = SKILL_DIR / "SKILL.md"
REFS_DIR = SKILL_DIR / "references"


def load_linter(alias: str):
    """Import scripts/lint_e2e_spec.py by path.

    The module must be registered in sys.modules *before* exec_module: it uses
    `from __future__ import annotations`, so @dataclass resolves its field types
    through sys.modules[cls.__module__] and raises AttributeError on None when
    the module is absent.
    """
    import importlib.util
    import sys

    path = SKILL_DIR / "scripts" / "lint_e2e_spec.py"
    spec = importlib.util.spec_from_file_location(alias, path)
    assert spec and spec.loader, f"cannot load {path}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[alias] = module
    spec.loader.exec_module(module)
    return module


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
        # These gates previously read "< 1.30" (toPass) and "< 1.35"
        # (toBeAttached / hasNot). Both were wrong against upstream release
        # notes: toPass landed in 1.29, and hasNot + toBeAttached both landed in
        # 1.33. The "< 1.32" form for hasNot was the dangerous one — it told a
        # project on exactly 1.32 that the API was available.
        self.assertIn("< 1.27", self.skill_text)
        self.assertIn("< 1.29", self.skill_text)
        self.assertIn("< 1.33", self.skill_text)

    def test_no_stale_version_gates(self) -> None:
        for stale in ["< 1.30", "< 1.32", "< 1.35"]:
            self.assertNotIn(
                stale,
                self.skill_text,
                f"stale version gate {stale!r} reintroduced in SKILL.md",
            )

    def test_node_gate_defers_to_compatibility_table(self) -> None:
        # The old table asserted "Playwright >= 1.30 not supported on Node < 16"
        # and "Playwright >= 1.40 not supported on Node < 18", neither of which
        # matches the published engines.node field. SKILL.md now points at the
        # verified table instead of restating numbers that can drift.
        self.assertIn("Node", self.skill_text)
        self.assertIn("references/playwright-patterns.md", self.skill_text)

    def test_networkidle_prohibited(self) -> None:
        self.assertIn("networkidle", self.skill_text)
        self.assertIn("DISCOURAGED", self.skill_text)

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


class TestProgressiveDisclosureBudget(unittest.TestCase):
    """SKILL.md is loaded on every invocation, so its size is a running cost.

    skill-creator's guidance is to stay under ~500 lines. It reached 478 by
    accretion — every review round adds a table — so the ceiling is asserted
    rather than left to notice.
    """

    LIMIT = 500

    def test_skill_md_within_budget(self) -> None:
        lines = len(SKILL_MD.read_text().split("\n"))
        self.assertLess(
            lines,
            self.LIMIT,
            f"SKILL.md is {lines} lines (limit {self.LIMIT}). Move detail into a "
            "reference rather than raising this number.",
        )

    def test_no_reference_is_loaded_unconditionally(self) -> None:
        """Every reference must state when to load it, so nothing is loaded 'just
        in case'. Two are marked every-task by design; the rest are conditional."""
        text = SKILL_MD.read_text()
        section = text[
            text.index("## Load References Selectively") : text.index("## Runner Strategy")
        ]
        for path in sorted(REFS_DIR.glob("*.md")):
            self.assertIn(
                path.name,
                section,
                f"{path.name} has no stated load condition",
            )

    def test_largest_reference_is_flagged_as_sectioned(self) -> None:
        """deep-patterns is ~1000 lines; the router must not imply reading it whole.

        Scoped to the Load References table — an unscoped search picks up the
        Quick Reference row, which appears earlier. Same shadowing trap as the
        version-table test.
        """
        text = SKILL_MD.read_text()
        section = text[
            text.index("## Load References Selectively") : text.index("## Runner Strategy")
        ]
        row = next(
            ln
            for ln in section.split("\n")
            if "playwright-deep-patterns.md" in ln and ln.startswith("|")
        )
        self.assertIn("section", row.lower())


class TestVersionFactsAreCorrect(unittest.TestCase):
    """Pin the Playwright API-introduction versions verified against upstream.

    Source of truth: microsoft/playwright docs/src/release-notes-js.md.
    Every number here was read out of that file, not recalled. A wrong number in
    this table makes the skill emit code that throws at runtime, so the values
    are asserted rather than left to prose review.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.patterns = (REFS_DIR / "playwright-patterns.md").read_text()

    def test_api_introduction_versions(self) -> None:
        expected = {
            "getByRole": "1.27",
            "toPass()": "1.29",
            "hasNot": "1.33",
            "toBeAttached()": "1.33",
            "frameLocator()": "1.17",
            "contentFrame()": "1.43",
            "webServer": "1.14",
        }
        # Scope to the API-availability table. Searching the whole file matches
        # the first row mentioning the API anywhere, which silently picked up an
        # unrelated "verify against" table once another section mentioned
        # `webServer.command`.
        start = self.patterns.index("### Playwright API Availability")
        end = self.patterns.index("### Node.js Compatibility")
        table = self.patterns[start:end]

        for api, version in expected.items():
            row = next(
                (ln for ln in table.split("\n") if api in ln and ln.startswith("|")),
                None,
            )
            self.assertIsNotNone(
                row, f"no API-availability row for {api} (searched only that table)"
            )
            self.assertIn(
                version,
                row,
                f"{api} should be documented as introduced in {version}; row was: {row}",
            )

    def test_node_engine_floors_match_the_manifest(self) -> None:
        # Verified from the published engines.node field per version.
        for pair in ["1.25 – 1.34", "1.35 – 1.44", "1.45 – 1.61", "1.62+"]:
            self.assertIn(pair, self.patterns, f"missing Node compatibility row: {pair}")
        for floor in [">=14", ">=16", ">=18", ">=20"]:
            self.assertIn(floor, self.patterns, f"missing engines floor: {floor}")

    def test_supported_runtime_kept_separate_from_engine_floor(self) -> None:
        """Two different Node constraints exist and they disagree.

        `engines.node` is `>=20` for Playwright 1.62; the documented System
        requirements say "latest 22.x, 24.x or 26.x". Quoting only the engine
        floor lets a project be called supported when it is merely installable.
        """
        self.assertIn("Package engine minimum", self.patterns)
        self.assertIn("Officially supported runtime", self.patterns)
        self.assertIn("latest 22.x, 24.x or 26.x", self.patterns)
        # The reconciliation must state the middle case explicitly.
        self.assertIn("runnable, unsupported", self.patterns)

    def test_skill_md_flags_the_unsupported_middle_case(self) -> None:
        skill = SKILL_MD.read_text()
        self.assertIn("engines.node", skill)
        self.assertIn("22.x", skill)


class TestNoDiscouragedApis(unittest.TestCase):
    """`networkidle` must not appear as recommended usage anywhere.

    Playwright marks it DISCOURAGED in its own API reference. Two instances were
    shipping inside GOOD examples; this test is what keeps them from returning.
    """

    def test_networkidle_only_in_prohibition_context(self) -> None:
        offenders = []
        for path in [SKILL_MD] + sorted(REFS_DIR.glob("*.md")):
            lines = path.read_text().split("\n")
            for i, line in enumerate(lines):
                if "networkidle" not in line:
                    continue
                stripped = line.strip()
                # Navigation, not usage: a heading or a TOC entry naming the
                # anti-pattern is how the reader finds the prohibition.
                if stripped.startswith("#") or stripped.startswith("- ["):
                    continue
                # Allowed only when the surrounding lines mark it as wrong.
                window = "\n".join(lines[max(0, i - 6) : i + 4]).lower()
                if any(
                    marker in window
                    for marker in [
                        "wrong",
                        "bad",
                        "discouraged",
                        "do not",
                        "never",
                        "avoid",
                        "mechanically checked",
                    ]
                ):
                    continue
                offenders.append(f"{path.name}:{i + 1}: {line.strip()}")
        self.assertEqual(
            [],
            offenders,
            "networkidle used without a prohibition marker:\n" + "\n".join(offenders),
        )


class TestTauriRoutedAwayFromPlaywright(unittest.TestCase):
    """Tauri renders in the OS webview; Playwright cannot attach to it.

    The platform matrix used to say "Playwright WebView debugging / Connect to
    WebView port", which is not an implementable path on any platform.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.deep = (REFS_DIR / "playwright-deep-patterns.md").read_text()

    def test_official_route_documented(self) -> None:
        for token in ["WebdriverIO", "@wdio/tauri-service", "tauri-driver"]:
            self.assertIn(token, self.deep, f"Tauri routing missing: {token}")

    def test_wrong_route_absent(self) -> None:
        for banned in ["Playwright WebView debugging", "Connect to WebView port"]:
            self.assertNotIn(banned, self.deep, f"wrong Tauri guidance present: {banned}")


class TestSelectorPriorityConsistent(unittest.TestCase):
    """SKILL.md described "data-testid priority" while the reference ranks
    getByRole first. Contradictory guidance across a load boundary is worse than
    either rule alone, because which one fires depends on load order."""

    def test_skill_md_does_not_claim_testid_priority(self) -> None:
        text = SKILL_MD.read_text()
        self.assertNotIn("data-testid priority", text)

    def test_reference_ranks_get_by_role_first(self) -> None:
        patterns = (REFS_DIR / "playwright-patterns.md").read_text()
        section = patterns[patterns.index("## Selector Strategy") :][:600]
        role_pos = section.index("getByRole")
        testid_pos = section.index("getByTestId")
        self.assertLess(
            role_pos, testid_pos, "getByRole must be ranked above getByTestId"
        )

    def test_skill_md_matches_reference_ordering(self) -> None:
        text = SKILL_MD.read_text()
        self.assertIn("getByRole", text)


class TestNoCredentialLeakInProbes(unittest.TestCase):
    """A presence check must never print the value.

    The env probe used to `echo "E2E_PASS=${E2E_PASS:-MISSING}"`, which writes
    the password into CI logs, screen recordings, and agent transcripts.
    """

    def test_no_echo_of_secret_values(self) -> None:
        offenders = []
        targets = [SKILL_MD] + sorted(REFS_DIR.glob("*.md")) + [
            SKILL_DIR / "scripts" / "discover_e2e_needs.sh"
        ]
        # Matches `echo "..._PASS=${..._PASS...}"` — printing a secret's value.
        leak = re.compile(
            r"echo\s+[\"'][^\"']*(PASS|PASSWORD|SECRET|TOKEN|API_KEY)\s*=\s*\$\{",
            re.IGNORECASE,
        )
        for path in targets:
            lines = path.read_text().split("\n")
            for i, line in enumerate(lines):
                if not leak.search(line):
                    continue
                # Allowed only when marked as a counter-example nearby, the same
                # way the networkidle guard works.
                window = "\n".join(lines[max(0, i - 3) : i + 2]).lower()
                if any(m in window for m in ["wrong", "never", "do not", "bad"]):
                    continue
                offenders.append(f"{path.name}:{i + 1}: {line.strip()}")
        self.assertEqual(
            [],
            offenders,
            "secret value printed by a presence check:\n" + "\n".join(offenders),
        )

    def test_presence_only_probe_documented(self) -> None:
        text = (REFS_DIR / "environment-and-dependency-gates.md").read_text()
        self.assertIn("Never echo a secret's value", text)


class TestAntiExampleCountClaimIsAccurate(unittest.TestCase):
    """SKILL.md claimed a "catalog of 12" while anti-examples.md held 7.

    Any restated count is a drift liability, so this test ties the claim to the
    file it describes.
    """

    def test_no_stale_count_claim(self) -> None:
        text = SKILL_MD.read_text()
        self.assertNotIn("catalog of 12 common Playwright mistakes", text)

    def test_skill_md_states_no_hard_count_for_the_reference(self) -> None:
        """Any restated count drifts the moment a case is added.

        "seven cases below plus seven more" went stale within the same session
        when a 15th case was added. The sentence now enumerates topics instead of
        counting them, so growth cannot invalidate it.
        """
        text = SKILL_MD.read_text()
        section = text[text.index("Load References Selectively") : text.index("## Runner Strategy")]
        line = next(ln for ln in section.split("\n") if "anti-examples.md" in ln)
        number_words = [
            "seven more",
            "eight more",
            "twelve",
            "14 ",
            "15 ",
            "catalog of",
        ]
        for phrase in number_words:
            self.assertNotIn(
                phrase,
                line,
                f"anti-examples pointer states a count ({phrase!r}); describe the "
                "topics instead so it cannot go stale",
            )

    def test_reference_does_not_duplicate_the_core_seven(self) -> None:
        """The reference is extended-only.

        It used to restate SKILL.md's seven cases with fuller code, so loading
        both meant reading the same seven twice — ~150 duplicated lines in the
        file that gets loaded *alongside* the always-loaded one.
        """
        anti = (REFS_DIR / "anti-examples.md").read_text()
        text = SKILL_MD.read_text()
        section = text[
            text.index("## Anti-Examples") : text.index("## Agent Browser Bridge")
        ]
        skill_cases = re.findall(r"^### \d+\) (.+)$", section, re.MULTILINE)
        self.assertEqual(
            7, len(skill_cases), "SKILL.md should carry exactly 7 inline anti-examples"
        )

        anti_headings = [
            h.lower() for h in re.findall(r"^## (.+)$", anti, re.MULTILINE)
        ]
        # The distinctive noun of each core case must not head a section here.
        for core in ["waitforTimeout in assertions", "fragile css selector chain"]:
            self.assertNotIn(
                core.lower(),
                anti_headings,
                f"core case {core!r} is duplicated in anti-examples.md",
            )
        self.assertIn("extended", anti.split("\n")[0].lower())

    def test_reference_has_a_table_of_contents(self) -> None:
        """It was the only reference file without one, at 311 lines."""
        anti = (REFS_DIR / "anti-examples.md").read_text()
        self.assertIn("## Table of Contents", anti)

    def test_toc_lists_every_case(self) -> None:
        """A TOC that drifts from the headings is worse than none."""
        anti = (REFS_DIR / "anti-examples.md").read_text()
        toc_block = anti[anti.index("## Table of Contents") :]
        toc_block = toc_block[: toc_block.index("\n## ", 5)]
        toc_entries = re.findall(r"^- \[(.+?)\]\(#", toc_block, re.MULTILINE)
        headings = [
            h
            for h in re.findall(r"^## (.+)$", anti, re.MULTILINE)
            if h != "Table of Contents"
        ]
        self.assertEqual(
            headings,
            toc_entries,
            "anti-examples.md TOC must list every case heading, in order",
        )

    def test_every_reference_file_has_a_toc(self) -> None:
        for path in sorted(REFS_DIR.glob("*.md")):
            self.assertIn(
                "Table of Contents",
                path.read_text(),
                f"{path.name} has no table of contents",
            )

    def test_extended_cases_are_unique_to_the_reference(self) -> None:
        anti = (REFS_DIR / "anti-examples.md").read_text()
        for topic in ["networkidle", "iframe boundary", "third-party widget"]:
            self.assertIn(
                topic.split()[0],
                anti,
                f"extended anti-example topic missing: {topic}",
            )


class TestIframeCoverage(unittest.TestCase):
    """Golden fixture 014 required frameLocator/contentFrame, but neither token
    existed anywhere in the skill. The fixture was decoration."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.deep = (REFS_DIR / "playwright-deep-patterns.md").read_text()

    def test_frame_apis_documented(self) -> None:
        self.assertIn("frameLocator", self.deep)
        self.assertIn("contentFrame", self.deep)

    def test_nested_frame_guidance(self) -> None:
        self.assertIn("Nested Frames", self.deep)

    def test_payment_sandbox_gate(self) -> None:
        self.assertIn("pk_test_", self.deep)
        self.assertIn("sandbox", self.deep.lower())


class TestAllowedToolsCoversDocumentedCommands(unittest.TestCase):
    """The skill instructed running `agent-browser` and the discovery script,
    neither of which the allowed-tools list permitted."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.fm = frontmatter(SKILL_MD.read_text())

    def test_agent_browser_permitted(self) -> None:
        self.assertIn("agent-browser", self.fm)

    def test_discovery_script_permitted(self) -> None:
        self.assertIn("bash scripts/", self.fm)

    def test_linter_permitted(self) -> None:
        self.assertIn("python3 scripts/", self.fm)


class TestGoldenExamplesLabelledSynthetic(unittest.TestCase):
    """Concrete pass counts in the examples invite copying fabricated evidence,
    which directly contradicts the Execution Integrity Gate."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.text = (REFS_DIR / "golden-examples.md").read_text()

    def test_synthetic_warning_present(self) -> None:
        self.assertIn("synthetic", self.text.lower())
        self.assertIn("Never Copy Them", self.text)

    def test_warning_precedes_first_result(self) -> None:
        warn = self.text.lower().index("synthetic")
        first_result = self.text.index("3/3 passed")
        self.assertLess(
            warn, first_result, "the synthetic-data warning must precede any result"
        )

    def test_execution_integrity_referenced(self) -> None:
        self.assertIn("Execution Integrity Gate", self.text)


class TestSpecLinter(unittest.TestCase):
    """The forward-eval grader must actually catch the defects it claims to.

    Contract tests verify the skill *says* the right things; these verify the
    grader *detects* the wrong things, on real source rather than prose.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.lint = load_linter("lint_e2e_spec")

    def rules(self, source: str) -> set:
        return {f.rule for f in self.lint.lint_source(source)}

    def test_clean_spec_passes(self) -> None:
        source = """
import { test, expect } from '@playwright/test';
const BASE = process.env.E2E_BASE_URL;
test.skip(!BASE, 'E2E_BASE_URL not set');
test('user sees the dashboard after signing in', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
});
"""
        self.assertEqual(set(), self.rules(source))

    def test_detects_wait_for_timeout(self) -> None:
        source = """
test.skip(!process.env.E2E_BASE_URL, 'x');
test('user sees confirmation after ordering', async ({ page }) => {
  await page.waitForTimeout(3000);
  await expect(page.getByText('Done')).toBeVisible();
});
"""
        self.assertIn("C1", self.rules(source))

    def test_detects_networkidle(self) -> None:
        source = """
test.skip(!process.env.E2E_BASE_URL, 'x');
test('user sees the dashboard totals', async ({ page }) => {
  await page.goto('/d');
  await page.waitForLoadState('networkidle');
  await expect(page.getByTestId('total')).toHaveText('42');
});
"""
        self.assertIn("C1", self.rules(source))

    def test_detects_hardcoded_url(self) -> None:
        source = """
test.skip(!process.env.E2E_USER, 'x');
test('user reaches the staging login page', async ({ page }) => {
  await page.goto('https://staging.myapp.com/login');
  await expect(page.getByRole('heading')).toBeVisible();
});
"""
        self.assertIn("C3", self.rules(source))

    def test_localhost_url_allowed(self) -> None:
        source = """
test.skip(!process.env.E2E_USER, 'x');
test('user reaches the local login page', async ({ page }) => {
  await page.goto('http://localhost:3000/login');
  await expect(page.getByRole('heading')).toBeVisible();
});
"""
        self.assertNotIn("C3", self.rules(source))

    def test_detects_credential_literal(self) -> None:
        source = """
test.skip(!process.env.E2E_USER, 'x');
test('user signs in with the seeded account', async ({ page }) => {
  await page.getByLabel('Password').fill('hunter2secret');
  await expect(page.getByText('Welcome')).toBeVisible();
});
"""
        self.assertIn("C3", self.rules(source))

    def test_negative_test_password_allowed(self) -> None:
        """A deliberately wrong password is the point of a negative test."""
        source = """
test.skip(!process.env.E2E_USER, 'x');
test('invalid password is rejected with an error', async ({ page }) => {
  await page.getByLabel('Password').fill('wrong-password');
  await expect(page.getByText('Invalid')).toBeVisible();
});
"""
        self.assertNotIn("C3", self.rules(source))

    def test_teaching_comments_do_not_trigger(self) -> None:
        """BAD examples live in comments throughout this skill."""
        source = """
test.skip(!process.env.E2E_BASE_URL, 'x');
// BAD: await page.waitForTimeout(3000);
// BAD: await page.waitForLoadState('networkidle');
/* BAD: await page.goto('https://staging.example.com'); */
test('user sees the dashboard heading', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading')).toBeVisible();
});
"""
        self.assertEqual(set(), self.rules(source))

    def test_detects_missing_skip_guard(self) -> None:
        source = """
test('user signs in with the seeded account', async ({ page }) => {
  await page.goto(process.env.E2E_BASE_URL!);
  await expect(page.getByRole('heading')).toBeVisible();
});
"""
        self.assertIn("C4", self.rules(source))

    def test_ci_flag_ternary_is_not_a_missing_guard(self) -> None:
        """`workers: process.env.CI ? 4 : undefined` needs no skip guard."""
        source = """
export default defineConfig({
  fullyParallel: true,
  workers: process.env.CI ? 4 : undefined,
});
"""
        self.assertNotIn("C4", self.rules(source))

    def test_scaffold_is_not_penalised_for_missing_assertions(self) -> None:
        """The Configuration Gate explicitly endorses guarded scaffolds."""
        source = """
const BASE = process.env.E2E_BASE_URL;
test.skip(!BASE, 'E2E_BASE_URL not set');
// TODO: wire the payment sandbox account before enabling this journey
test('user completes checkout end to end', async ({ page }) => {
  await page.goto(`${BASE}/checkout`);
  // ... scaffold continues
});
"""
        self.assertNotIn("S3", self.rules(source))

    def test_detects_shared_mutable_identity(self) -> None:
        source = """
test.skip(!process.env.E2E_BASE_URL, 'x');
const sharedEmail = 'e2e-user@example.com';
test('admin deletes the shared account', async ({ page }) => {
  await page.goto('/a');
  await expect(page.getByText(sharedEmail)).toBeVisible();
});
test('user updates the shared account', async ({ page }) => {
  await page.goto('/p');
  await expect(page.getByText(sharedEmail)).toBeVisible();
});
"""
        self.assertIn("C2", self.rules(source))

    def test_per_test_identity_allowed(self) -> None:
        source = """
test.skip(!process.env.E2E_BASE_URL, 'x');
const email = `e2e-${Date.now()}@example.com`;
test('admin deletes the generated account', async ({ page }) => {
  await page.goto('/a');
  await expect(page.getByText(email)).toBeVisible();
});
test('user updates the generated account', async ({ page }) => {
  await page.goto('/p');
  await expect(page.getByText(email)).toBeVisible();
});
"""
        self.assertNotIn("C2", self.rules(source))

    def test_detects_fragile_css_chain(self) -> None:
        source = """
test.skip(!process.env.E2E_BASE_URL, 'x');
test('user clicks the primary call to action', async ({ page }) => {
  await page.locator('.app > div:nth-child(2) .cta.primary').click();
  await expect(page.getByText('Done')).toBeVisible();
});
"""
        self.assertIn("S1", self.rules(source))

    def test_detects_unjustified_serial(self) -> None:
        source = """
test.skip(!process.env.E2E_BASE_URL, 'x');
test.describe('orders', () => {
  test.describe.configure({ mode: 'serial' });
  test('user views their order history', async ({ page }) => {
    await page.goto('/o');
    await expect(page.getByRole('heading')).toBeVisible();
  });
});
"""
        self.assertIn("S5", self.rules(source))

    def test_justified_serial_allowed(self) -> None:
        source = """
test.skip(!process.env.E2E_BASE_URL, 'x');
test.describe('checkout funnel — serial because steps share cart state', () => {
  test.describe.configure({ mode: 'serial' });
  test('user completes the funnel in order', async ({ page }) => {
    await page.goto('/c');
    await expect(page.getByRole('heading')).toBeVisible();
  });
});
"""
        self.assertNotIn("S5", self.rules(source))

    def test_detects_vague_test_name(self) -> None:
        source = """
test.skip(!process.env.E2E_BASE_URL, 'x');
test('test1', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading')).toBeVisible();
});
"""
        self.assertIn("H2", self.rules(source))

    def test_guard_is_matched_per_variable_not_per_file(self) -> None:
        """A skip on one variable must not launder every other variable.

        This exact snippet returned zero findings before the fix: the file-global
        "does any test.skip exist" check let an unguarded E2E_PASS through.
        """
        source = """
const U = process.env.E2E_USER;
const P = process.env.E2E_PASS;
test.skip(!U, 'user missing');
test('user signs in with the seeded account', async ({ page }) => {
  await page.getByLabel('Email').fill(U!);
  await page.getByLabel('Password').fill(P!);
  await expect(page.getByText('Welcome')).toBeVisible();
});
"""
        findings = self.lint.lint_source(source)
        c4 = [f for f in findings if f.rule == "C4"]
        self.assertTrue(c4, "unguarded E2E_PASS must be reported")
        self.assertTrue(
            any("E2E_PASS" in f.message for f in c4),
            f"the finding must name E2E_PASS, got: {[f.message for f in c4]}",
        )
        self.assertFalse(
            any("E2E_USER" in f.message for f in c4),
            "E2E_USER is guarded and must not be reported",
        )

    def test_guard_covering_all_variables_is_clean(self) -> None:
        source = """
const U = process.env.E2E_USER;
const P = process.env.E2E_PASS;
test.skip(!U || !P, 'credentials missing');
test('user signs in with the seeded account', async ({ page }) => {
  await page.getByLabel('Email').fill(U!);
  await page.getByLabel('Password').fill(P!);
  await expect(page.getByText('Welcome')).toBeVisible();
});
"""
        self.assertNotIn("C4", self.rules(source))

    def test_guard_by_env_name_covers_its_alias(self) -> None:
        """`test.skip(!process.env.E2E_PASS)` must cover a `P` alias of it."""
        source = """
const P = process.env.E2E_PASS;
test.skip(!process.env.E2E_PASS, 'password missing');
test('user signs in with the seeded account', async ({ page }) => {
  await page.getByLabel('Password').fill(P!);
  await expect(page.getByText('Welcome')).toBeVisible();
});
"""
        self.assertNotIn("C4", self.rules(source))

    def test_detects_network_wait_armed_after_trigger(self) -> None:
        """An inline-awaited waitForResponse hangs when the response is fast."""
        source = """
test.skip(!process.env.E2E_BASE_URL, 'x');
test('user continues to payment after saving an address', async ({ page }) => {
  await page.getByRole('button', { name: 'Save address' }).click();
  await page.waitForResponse(resp => resp.url().includes('/api/address'));
  await expect(page.getByText('Payment')).toBeVisible();
});
"""
        self.assertIn("W1", self.rules(source))

    def test_promise_armed_before_trigger_is_clean(self) -> None:
        source = """
test.skip(!process.env.E2E_BASE_URL, 'x');
test('user continues to payment after saving an address', async ({ page }) => {
  const saved = page.waitForResponse(resp => resp.url().includes('/api/address'));
  await page.getByRole('button', { name: 'Save address' }).click();
  await saved;
  await expect(page.getByText('Payment')).toBeVisible();
});
"""
        self.assertNotIn("W1", self.rules(source))

    def test_wait_for_event_has_the_same_ordering_rule(self) -> None:
        source = """
test.skip(!process.env.E2E_BASE_URL, 'x');
test('a new tab opens when the user follows the external link', async ({ page }) => {
  await page.getByRole('link', { name: 'Open' }).click();
  await page.context().waitForEvent('page');
  await expect(page.getByText('Opened')).toBeVisible();
});
"""
        self.assertIn("W1", self.rules(source))

    def test_guard_does_not_leak_across_tests(self) -> None:
        """A guard inside test A says nothing about test B.

        Matching per variable but file-wide still returned zero findings here:
        the guard in the first test laundered the unguarded use in the second.
        """
        source = """
const PASS = process.env.E2E_PASS;

test('first journey guards the credential', async ({ page }) => {
  test.skip(!PASS, 'password missing');
  await page.getByLabel('Password').fill(PASS!);
  await expect(page.getByText('Welcome')).toBeVisible();
});

test('second journey uses it with no guard at all', async ({ page }) => {
  await page.getByLabel('Password').fill(PASS!);
  await expect(page.getByText('Welcome')).toBeVisible();
});
"""
        findings = [f for f in self.lint.lint_source(source) if f.rule == "C4"]
        self.assertTrue(findings, "unguarded use in the second test must be reported")
        # Only the second test's use is a defect; the first is guarded.
        self.assertTrue(
            all(f.line >= 10 for f in findings),
            f"only the second test should be flagged, got lines {[f.line for f in findings]}",
        )

    def test_per_test_guards_in_every_test_are_clean(self) -> None:
        """The legitimate counterpart: a file-scope const plus a guard in each
        test. Reporting the bare declaration here would be a false alarm — an
        unread binding is harmless."""
        source = """
const PASS = process.env.E2E_PASS;

test('first journey guards the credential', async ({ page }) => {
  test.skip(!PASS, 'password missing');
  await page.getByLabel('Password').fill(PASS!);
  await expect(page.getByText('Welcome')).toBeVisible();
});

test('second journey guards it too', async ({ page }) => {
  test.skip(!PASS, 'password missing');
  await page.getByLabel('Password').fill(PASS!);
  await expect(page.getByText('Welcome')).toBeVisible();
});
"""
        self.assertNotIn("C4", self.rules(source))

    def test_describe_scoped_guard_covers_its_tests(self) -> None:
        source = """
const PASS = process.env.E2E_PASS;

test.describe('authenticated area', () => {
  test.skip(!PASS, 'password missing');

  test('user opens the dashboard', async ({ page }) => {
    await page.getByLabel('Password').fill(PASS!);
    await expect(page.getByRole('heading')).toBeVisible();
  });
});
"""
        self.assertNotIn("C4", self.rules(source))

    def test_before_each_guard_covers_the_scope(self) -> None:
        """`test.skip` in a beforeEach hook does skip every test in that scope."""
        source = """
const PASS = process.env.E2E_PASS;

test.beforeEach(async () => {
  test.skip(!PASS, 'password missing');
});

test('user opens the dashboard', async ({ page }) => {
  await page.getByLabel('Password').fill(PASS!);
  await expect(page.getByRole('heading')).toBeVisible();
});
"""
        self.assertNotIn("C4", self.rules(source))

    def test_alias_with_fallback_is_not_tracked(self) -> None:
        """`const T = process.env.X ?? ''` can never be undefined."""
        source = """
const TOKEN = process.env.E2E_TOKEN ?? '';
test('api returns the order list for the caller', async ({ request }) => {
  const r = await request.get('/api/orders', {
    headers: { Authorization: `Bearer ${TOKEN}` },
  });
  await expect(r).toBeOK();
});
"""
        self.assertNotIn("C4", self.rules(source))

    def test_promise_all_form_is_not_flagged(self) -> None:
        """`await Promise.all([waiter, action])` arms both before either runs —
        the canonical correct pattern for new-tab handling."""
        source = """
test.skip(!process.env.E2E_BASE_URL, 'x');
test('a new tab opens when the user follows the external link', async ({ page }) => {
  const [newPage] = await Promise.all([
    page.context().waitForEvent('page'),
    page.getByRole('link', { name: 'Open' }).click(),
  ]);
  await expect(newPage.getByRole('heading')).toBeVisible();
});
"""
        self.assertNotIn("W1", self.rules(source))

    def test_exit_code_reflects_critical_only(self) -> None:
        critical = "test('t1', async ({ page }) => { await page.waitForTimeout(1); });"
        hygiene_only = """
test.skip(!process.env.E2E_BASE_URL, 'x');
test('t1', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading')).toBeVisible();
});
"""
        self.assertTrue(
            any(f.severity == "CRITICAL" for f in self.lint.lint_source(critical))
        )
        self.assertFalse(
            any(f.severity == "CRITICAL" for f in self.lint.lint_source(hygiene_only))
        )


class TestSkillOwnExamplesPassTheGrader(unittest.TestCase):
    """Every GOOD example the skill ships must survive the skill's own grader.

    A skill that ships both exemplars and a checker has to run one against the
    other; otherwise it teaches by example what it forbids by rule. This test
    found four real defects on its first run, including the flagship "runnable"
    golden example reading process.env with no skip guard.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.lint = load_linter("lint_e2e_spec_selfcheck")

    @staticmethod
    def _good_blocks() -> list:
        """Yield (source_file, line, code) for every ts block NOT marked as a
        counter-example. A block counts as BAD if a marker appears in the text
        just before it or on any line inside it."""
        blocks = []
        bad_marker = re.compile(r"\bBAD\b|WRONG|AVOID|DO NOT|Do NOT|never found", re.I)
        for path in [SKILL_MD] + sorted(REFS_DIR.glob("*.md")):
            text = path.read_text()
            for m in re.finditer(r"```ts\n(.*?)```", text, re.DOTALL):
                preceding = text[max(0, m.start() - 200) : m.start()]
                body = m.group(1)
                if bad_marker.search(preceding) or bad_marker.search(body):
                    continue
                line = text.count("\n", 0, m.start()) + 1
                blocks.append((path.name, line, body))
        return blocks

    def test_good_examples_have_no_critical_findings(self) -> None:
        blocks = self._good_blocks()
        self.assertGreater(len(blocks), 10, "block extraction found too few examples")
        failures = []
        for name, line, body in blocks:
            for f in self.lint.lint_source(body):
                if f.severity == "CRITICAL":
                    failures.append(f"{name}:{line} [{f.rule}] {f.message}")
        self.assertEqual(
            [],
            failures,
            "GOOD examples failing the skill's own grader:\n" + "\n".join(failures),
        )


class TestLinterScopeIsHonest(unittest.TestCase):
    """The module docstring must not claim scorecard coverage it lacks.

    It previously said it reports "whether that code satisfies C1-C4 / S1-S6 /
    H1-H4" while implementing 8 of those 14 items. An overclaiming linter is
    worse than no linter, because a clean report gets read as a pass.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.text = (SKILL_DIR / "scripts" / "lint_e2e_spec.py").read_text()
        cls.doc = cls.text[: cls.text.index('"""', cls.text.index('"""') + 3)]

    def test_names_the_unchecked_items(self) -> None:
        for unchecked in ["S2", "S4", "S6", "H1", "H3", "H4"]:
            self.assertIn(
                unchecked,
                self.doc,
                f"docstring must state that {unchecked} is NOT checked",
            )
        self.assertIn("NOT checked", self.doc)

    def test_does_not_claim_full_coverage(self) -> None:
        self.assertNotIn("S1-S6", self.doc)
        self.assertNotIn("H1-H4", self.doc)

    def test_w1_marked_as_beyond_the_scorecard(self) -> None:
        self.assertIn("W1", self.doc)
        self.assertIn("not a scorecard", self.doc.lower())

    def test_skill_md_states_the_same_subset(self) -> None:
        skill = SKILL_MD.read_text()
        self.assertIn("S2, S4, S6, H1, H3, H4", skill)


class TestConfigBaselineDoesNotGuessEnvironment(unittest.TestCase):
    """The config template must not present guessed values as ready to use.

    The prior baseline hardcoded `npm run dev` and port 3000 with a silent
    localhost fallback. In CI with E2E_BASE_URL unset that boots a dev server and
    reports green for an environment nobody meant to test.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.patterns = (REFS_DIR / "playwright-patterns.md").read_text()

    def test_ci_fallback_fails_loudly(self) -> None:
        self.assertIn("refusing to fall back to localhost", self.patterns)
        self.assertIn("process.env.CI && !process.env.E2E_BASE_URL", self.patterns)

    def test_values_flagged_for_verification(self) -> None:
        self.assertIn("VERIFY these two against the repository", self.patterns)
        for fact in ["dev_command", "detected_port", "e2e_directory"]:
            self.assertIn(
                fact,
                self.patterns,
                f"config baseline should point at the discovery field {fact}",
            )

    def test_web_server_skipped_when_targeting_deployed_env(self) -> None:
        # Booting a local server while pointing at staging tests the wrong target.
        self.assertIn("webServer: process.env.E2E_BASE_URL", self.patterns)

    def test_documents_the_confusing_failure_mode(self) -> None:
        self.assertIn("Timed out waiting for the web server", self.patterns)


class TestWaitOrderingDocumented(unittest.TestCase):
    """`waitForResponse` after its trigger is a hang, and it shipped inside the
    flaky-triage golden example as the *fix*."""

    def test_golden_example_arms_promise_first(self) -> None:
        text = (REFS_DIR / "golden-examples.md").read_text()
        section = text[text.index("## 3) Flaky Triage") : text.index("## 4) CI Gate")]
        promise_pos = section.index("const addressSaved = page.waitForResponse")
        click_pos = section.index("Save address' }).click();", promise_pos)
        self.assertLess(
            promise_pos, click_pos, "the waiter must be created before the click"
        )

    def test_golden_example_prefers_visible_state(self) -> None:
        text = (REFS_DIR / "golden-examples.md").read_text()
        self.assertIn("Address confirmed", text)

    def test_wrong_form_shown_as_counter_example(self) -> None:
        text = (REFS_DIR / "golden-examples.md").read_text()
        idx = text.index("await page.waitForResponse(resp => resp.url().includes('/api/address'));")
        window = text[max(0, idx - 300) : idx]
        self.assertIn("WRONG", window)

    def test_anti_example_exists(self) -> None:
        anti = (REFS_DIR / "anti-examples.md").read_text()
        self.assertIn("Network wait armed after the action that triggers it", anti)

    def test_patterns_file_explains_the_ordering(self) -> None:
        patterns = (REFS_DIR / "playwright-patterns.md").read_text()
        self.assertIn("Order is load-bearing", patterns)


class TestEnvStateSemantics(unittest.TestCase):
    """`declared` must exist as a distinct state from `available`.

    An empty `.env.example` proves the variable is expected, not that a value
    exists. Reporting it as `available` cleared the `no_base_url` blocker and
    could make an unrunnable project report `ready`.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.script = (SKILL_DIR / "scripts" / "discover_e2e_needs.sh").read_text()

    def test_three_states_implemented(self) -> None:
        for state in ["available", "declared", "missing"]:
            self.assertIn(state, self.script)

    def test_legend_is_emitted(self) -> None:
        self.assertIn("env_state_legend", self.script)

    def test_env_example_capped_at_declared(self) -> None:
        self.assertIn("can never raise a variable above `declared`", self.script)

    def test_empty_value_distinguished_from_present_value(self) -> None:
        self.assertIn("env_state_in_file", self.script)

    def test_declared_base_url_is_unknown_not_blocker(self) -> None:
        self.assertIn("base_url_declared_but_unset", self.script)

    def test_partial_credentials_flagged(self) -> None:
        self.assertIn("test_account_password_not_available", self.script)


class TestDiscoverScriptRobustness(unittest.TestCase):
    """The script is a probe; a missing thing must never abort the scan.

    It previously ran under `set -e`, so a Makefile without an `e2e` target made
    `grep` exit 1 and killed the script mid-report — which reads as "nothing else
    found" rather than "the scan died".
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.script = SKILL_DIR / "scripts" / "discover_e2e_needs.sh"
        cls.text = cls.script.read_text()

    def test_does_not_use_set_e(self) -> None:
        first_lines = "\n".join(self.text.split("\n")[:6])
        self.assertNotIn("set -euo", first_lines)
        self.assertIn("set -uo pipefail", first_lines)

    def test_set_e_omission_is_explained(self) -> None:
        self.assertIn("deliberately NOT enabled", self.text)

    def test_makefile_grep_cannot_abort(self) -> None:
        makefile_section = self.text[self.text.index("Makefile") :][:600]
        self.assertIn("|| true", makefile_section)

    def test_separates_blockers_from_unknowns(self) -> None:
        # Collapsing "unknown" into "blocked" is what produced false
        # stop-the-world verdicts on public-page suites and Cypress repos.
        self.assertIn("unknowns", self.text)
        self.assertIn("needs_confirmation", self.text)

    def test_missing_account_is_not_a_blocker(self) -> None:
        self.assertIn("confirm_whether_journey_needs_auth", self.text)

    def test_recognises_non_js_projects(self) -> None:
        for token in ["python_web", "rust_web", "tauri_desktop"]:
            self.assertIn(token, self.text, f"project type not detected: {token}")

    def test_respects_existing_runner(self) -> None:
        self.assertIn("other_e2e_runner", self.text)
        self.assertIn("cypress", self.text)

    def test_base_url_in_config_counts(self) -> None:
        self.assertIn("base_url_in_playwright_config", self.text)

    def test_no_sed_shrapnel(self) -> None:
        # A repo-wide output->outputexample replacement once corrupted these
        # comments into "outputexample a structured report".
        self.assertNotIn("outputexample", self.text)

    def test_never_prints_secret_values(self) -> None:
        self.assertIn("never print a value", self.text.lower())


if __name__ == "__main__":
    unittest.main()
