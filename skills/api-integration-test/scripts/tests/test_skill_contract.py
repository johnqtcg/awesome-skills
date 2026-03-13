#!/usr/bin/env python3
"""Contract tests for api-integration-test skill."""

import json
import os
import re
import unittest

SKILL_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
SKILL_MD = os.path.join(SKILL_ROOT, "SKILL.md")
REFS_DIR = os.path.join(SKILL_ROOT, "references")


def read(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()
SKILL_TEXT = read(SKILL_MD)
SKILL_LINES = SKILL_TEXT.splitlines()


def assert_re(testcase: unittest.TestCase, pattern: str, text: str, msg: str | None = None) -> None:
    testcase.assertIsNotNone(re.search(pattern, text, re.MULTILINE), msg or f"regex not found: {pattern}")


# ── Frontmatter ──────────────────────────────────────────────


class TestFrontmatter(unittest.TestCase):
    def test_has_yaml_frontmatter(self):
        self.assertTrue(SKILL_TEXT.startswith("---"), "SKILL.md must start with YAML frontmatter")
        second = SKILL_TEXT.index("---", 3)
        self.assertGreater(second, 3, "Frontmatter must have closing ---")

    def test_has_name(self):
        assert_re(self, r"^name:\s*api-integration-test", SKILL_TEXT)

    def test_has_description(self):
        assert_re(self, r"^description:", SKILL_TEXT)

    def test_description_has_trigger_keywords(self):
        fm = SKILL_TEXT.split("---")[1]
        keywords = ["integration", "API", "Go"]
        for kw in keywords:
            self.assertIn(kw.lower(), fm.lower(), f"description missing keyword: {kw}")

    def test_has_allowed_tools(self):
        assert_re(self, r"^allowed-tools:", SKILL_TEXT)

    def test_allowed_tools_whitelist(self):
        fm = SKILL_TEXT.split("---")[1]
        match = re.search(r"allowed-tools:\s*(.+)", fm)
        self.assertIsNotNone(match, "allowed-tools line not found")
        tools = match.group(1)
        for tool in ["Read", "Grep", "Glob", "Bash"]:
            self.assertIn(tool, tools, f"allowed-tools missing {tool}")


# ── Mandatory Sections (H2 level) ───────────────────────────


class TestMandatorySections(unittest.TestCase):
    REQUIRED_HEADINGS = [
        "Goal",
        "When To Use",
        "Scope",
        "Mandatory Gates",
        "Execution Modes",
        "Required Test Pattern",
        "Anti-Examples",
        "Go Implementation Baseline",
        "Safety Rules",
        "Execution Commands",
        "Output Contract",
        "CI Integration",
    ]

    def test_has_required_heading(self):
        for heading in self.REQUIRED_HEADINGS:
            with self.subTest(heading=heading):
                assert_re(self, rf"^##\s+.*{re.escape(heading)}", SKILL_TEXT, f"Missing required heading: {heading}")


# ── Mandatory Gates ──────────────────────────────────────────


class TestMandatoryGates(unittest.TestCase):
    GATES = [
        "Scope Validation Gate",
        "Go Version Gate",
        "Configuration Completeness Gate",
        "Execution Mode Gate",
        "Production Safety Gate",
        "Execution Integrity Gate",
        "Load References Selectively",
    ]

    def test_gate_defined(self):
        for gate in self.GATES:
            with self.subTest(gate=gate):
                assert_re(self, rf"^###\s+\d+\)\s+{re.escape(gate)}", SKILL_TEXT, f"Mandatory gate not defined: {gate}")

    def test_gates_numbered_1_through_7(self):
        numbers = re.findall(r"^###\s+(\d+)\)", SKILL_TEXT, re.MULTILINE)
        expected = [str(i) for i in range(1, 8)]
        self.assertEqual(numbers, expected, f"Gates must be numbered 1-7 sequentially, got: {numbers}")

    def test_serial_dependency_stated(self):
        section = SKILL_TEXT.split("## Mandatory Gates")[1].split("\n## ")[0]
        self.assertTrue("serial" in section.lower() or "order" in section.lower())

    def test_gate_failure_blocks(self):
        section = SKILL_TEXT.split("## Mandatory Gates")[1].split("\n## ")[0]
        self.assertTrue("block" in section.lower() or "stop" in section.lower())


# ── Execution Mode Auto-Selection ────────────────────────────


class TestExecutionModes(unittest.TestCase):
    MODES = ["Smoke", "Standard", "Comprehensive"]

    def test_mode_defined(self):
        for mode in self.MODES:
            with self.subTest(mode=mode):
                assert_re(self, rf"^###\s+{mode}", SKILL_TEXT, f"Execution mode not defined: {mode}")

    def test_standard_is_default(self):
        self.assertIn("default", SKILL_TEXT.lower().split("### standard")[1].split("###")[0])

    def test_auto_selection_table_exists(self):
        gate_section = SKILL_TEXT.split("Execution Mode Gate")[1].split("###")[0]
        self.assertIn("Signal", gate_section)
        self.assertIn("Mode", gate_section)

    def test_smoke_triggers(self):
        gate_section = SKILL_TEXT.split("Execution Mode Gate")[1].split("###")[0]
        self.assertTrue("smoke" in gate_section.lower() or "connectivity" in gate_section.lower())

    def test_comprehensive_triggers(self):
        gate_section = SKILL_TEXT.split("Execution Mode Gate")[1].split("###")[0]
        self.assertTrue("comprehensive" in gate_section.lower() or "release" in gate_section.lower())

    def test_user_override(self):
        gate_section = SKILL_TEXT.split("Execution Mode Gate")[1].split("###")[0]
        self.assertTrue("user explicitly" in gate_section.lower() or "regardless" in gate_section.lower())


# ── Gates Content ────────────────────────────────────────────


class TestGateContent(unittest.TestCase):
    def test_production_gate_env(self):
        self.assertIn("INTEGRATION_ALLOW_PROD", SKILL_TEXT)

    def test_build_tag(self):
        self.assertIn("//go:build integration", SKILL_TEXT)

    def test_run_gate_env(self):
        self.assertIn("INTERNAL_API_INTEGRATION", SKILL_TEXT)

    def test_context_timeout_required(self):
        self.assertIn("context.WithTimeout", SKILL_TEXT)

    def test_execution_integrity_no_false_pass(self):
        section = SKILL_TEXT.split("Execution Integrity Gate")[1].split("###")[0]
        self.assertTrue("never" in section.lower() and ("claim" in section.lower() or "report" in section.lower()))

    def test_scope_redirect_to_unit_test(self):
        section = SKILL_TEXT.split("Scope Validation Gate")[1].split("###")[0]
        self.assertIn("$unit-test", section)

    def test_version_gate_go_mod(self):
        section = SKILL_TEXT.split("Go Version Gate")[1].split("###")[0]
        self.assertIn("go.mod", section)

    def test_version_gate_versions(self):
        section = SKILL_TEXT.split("Go Version Gate")[1].split("###")[0]
        self.assertIn("1.17", section)
        self.assertIn("1.22", section)


# ── Degradation (now in Gate 3) ──────────────────────────────


class TestDegradation(unittest.TestCase):
    LEVELS = ["Full", "Scaffold", "Blocked"]

    def test_level_defined(self):
        for level in self.LEVELS:
            with self.subTest(level=level):
                self.assertIn(level, SKILL_TEXT)

    def test_blocked_stops_execution(self):
        section = SKILL_TEXT.split("Configuration Completeness Gate")[1].split("###")[0]
        self.assertTrue("stop" in section.lower() or "STOP" in section)


# ── Anti-Examples ────────────────────────────────────────────


class TestAntiExamples(unittest.TestCase):
    def test_has_anti_examples_section(self):
        self.assertIn("Anti-Examples", SKILL_TEXT)

    def test_minimum_anti_examples(self):
        section = SKILL_TEXT.split("Anti-Examples")[1].split("## ")[0]
        numbered = re.findall(r"^\d+\.\s+\*\*", section, re.MULTILINE)
        self.assertGreaterEqual(len(numbered), 5, f"Expected ≥5 anti-examples, found {len(numbered)}")


# ── Output Contract ──────────────────────────────────────────


class TestOutputContract(unittest.TestCase):
    def test_references_output_contract(self):
        self.assertIn("common-output-contract.md", SKILL_TEXT)


# ── Reference Files ──────────────────────────────────────────


class TestReferenceFiles(unittest.TestCase):
    EXPECTED_FILES = [
        "common-integration-gate.md",
        "common-output-contract.md",
        "checklists.md",
        "internal-api-patterns.md",
    ]

    def test_reference_exists(self):
        for filename in self.EXPECTED_FILES:
            with self.subTest(filename=filename):
                path = os.path.join(REFS_DIR, filename)
                self.assertTrue(os.path.isfile(path), f"Reference file missing: {filename}")

    def test_reference_not_empty(self):
        for filename in self.EXPECTED_FILES:
            with self.subTest(filename=filename):
                path = os.path.join(REFS_DIR, filename)
                content = read(path)
                self.assertGreater(len(content.strip()), 50, f"Reference file too short: {filename}")

    def test_reference_mentioned_in_skill(self):
        for filename in self.EXPECTED_FILES:
            with self.subTest(filename=filename):
                self.assertIn(filename, SKILL_TEXT, f"Reference {filename} not mentioned in SKILL.md")


# ── Reference Loading (now in Gate 7) ───────────────────────


class TestReferenceLoading(unittest.TestCase):
    def test_gate_file_always_loads(self):
        section = SKILL_TEXT.split("Load References Selectively")[1].split("## ")[0]
        self.assertTrue("always" in section.lower() and "common-integration-gate.md" in section)

    def test_patterns_has_trigger(self):
        section = SKILL_TEXT.split("Load References Selectively")[1].split("## ")[0]
        self.assertTrue(
            "trigger" in section.lower()
            or "only when" in section.lower()
            or "http/gRPC" in section
        )


# ── Safety Rules ─────────────────────────────────────────────


class TestSafetyRules(unittest.TestCase):
    def test_no_hardcode_secrets(self):
        section = SKILL_TEXT.split("Safety Rules")[1].split("## ")[0]
        self.assertTrue("hardcode" in section.lower() or "secret" in section.lower())

    def test_timeout_bounded(self):
        section = SKILL_TEXT.split("Safety Rules")[1].split("## ")[0]
        self.assertTrue("timeout" in section.lower() and "bounded" in section.lower())


# ── SKILL.md Size ────────────────────────────────────────────


class TestSize(unittest.TestCase):
    def test_under_500_lines(self):
        self.assertLessEqual(
            len(SKILL_LINES),
            500,
            f"SKILL.md is {len(SKILL_LINES)} lines (max 500). Move content to references/.",
        )


if __name__ == "__main__":
    unittest.main()
