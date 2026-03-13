"""Structural and content contract tests for the deep-research SKILL.md."""

import re
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent.parent
SKILL_MD = SKILL_ROOT / "SKILL.md"
OUTPUT_CONTRACT = SKILL_ROOT / "references" / "output-contract-template.md"
HALLUCINATION_REF = SKILL_ROOT / "references" / "hallucination-and-verification.md"
RESEARCH_PATTERNS = SKILL_ROOT / "references" / "research-patterns.md"
SCRIPT = SKILL_ROOT / "scripts" / "deep_research.py"
UNIT_TESTS = SKILL_ROOT / "scripts" / "tests" / "test_deep_research.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class TestFrontmatter(unittest.TestCase):
    def setUp(self):
        self.text = _read(SKILL_MD)

    def test_has_yaml_frontmatter(self):
        self.assertTrue(self.text.startswith("---"), "SKILL.md must start with YAML frontmatter")

    def test_has_name_field(self):
        self.assertRegex(self.text, r"(?m)^name:\s*deep-research")

    def test_has_description_field(self):
        self.assertRegex(self.text, r"(?m)^description:\s*\|")

    def test_description_mentions_research(self):
        m = re.search(r"description:\s*\|\n((?:\s+.*\n)+)", self.text)
        self.assertIsNotNone(m, "description block not found")
        desc = m.group(1).lower()
        self.assertIn("research", desc)

    def test_has_allowed_tools(self):
        self.assertRegex(self.text, r"(?m)^allowed-tools:")

    def test_allowed_tools_include_essentials(self):
        m = re.search(r"allowed-tools:\s*(.+)", self.text)
        self.assertIsNotNone(m)
        tools = m.group(1).lower()
        for tool in ["read", "bash", "webfetch"]:
            self.assertIn(tool, tools, f"allowed-tools should include {tool}")


class TestMandatoryGates(unittest.TestCase):
    def setUp(self):
        self.text = _read(SKILL_MD)

    def test_has_mandatory_gates_section(self):
        self.assertIn("## Mandatory Gates", self.text)

    def test_has_8_numbered_gates(self):
        for i in range(1, 9):
            self.assertRegex(
                self.text, rf"### {i}\)",
                f"Gate {i} not found as explicitly numbered ### {i})",
            )

    def test_gate_serial_order(self):
        positions = []
        for i in range(1, 9):
            m = re.search(rf"### {i}\)", self.text)
            self.assertIsNotNone(m, f"Gate {i} position not found")
            positions.append(m.start())
        for j in range(len(positions) - 1):
            self.assertLess(positions[j], positions[j + 1], f"Gate {j+1} must come before Gate {j+2}")

    def test_gate_names(self):
        expected = [
            "Scope Classification",
            "Ambiguity Resolution",
            "Evidence Requirements",
            "Research Mode",
            "Hallucination Awareness",
            "Budget Control",
            "Content Extraction",
            "Execution Integrity",
        ]
        for i, name in enumerate(expected, 1):
            pattern = rf"### {i}\)\s+{re.escape(name)}"
            self.assertRegex(self.text, pattern, f"Gate {i} should be named '{name}'")

    def test_ascii_flow_diagram(self):
        self.assertIn("1) Scope", self.text)
        self.assertIn("8) Execution", self.text)

    def test_evidence_requirements_table(self):
        self.assertIn("Conclusion Type", self.text)
        self.assertIn("Minimum Evidence Chain", self.text)
        self.assertIn("Target Confidence", self.text)

    def test_hallucination_awareness_table(self):
        self.assertIn("Risk Level", self.text)
        self.assertIn("Verification Method", self.text)


class TestExecutionModes(unittest.TestCase):
    def setUp(self):
        self.text = _read(SKILL_MD)

    def test_three_modes_defined(self):
        for mode in ["Quick", "Standard", "Deep"]:
            self.assertIn(mode, self.text)

    def test_mode_auto_selection_table(self):
        self.assertIn("Signal", self.text)
        self.assertIn("→ Mode", self.text)

    def test_user_override(self):
        self.assertRegex(
            self.text,
            r"(?i)user\s+explicitly\s+requests",
            "Should allow user to override auto-selected mode",
        )

    def test_budget_per_mode(self):
        self.assertIn("5–10", self.text)
        self.assertIn("15–25", self.text)
        self.assertIn("30–50", self.text)

    def test_hard_ceiling(self):
        self.assertRegex(self.text, r"(?i)hard\s+ceiling.*50")


class TestAntiExamples(unittest.TestCase):
    def setUp(self):
        self.text = _read(SKILL_MD)

    def test_has_anti_examples_section(self):
        self.assertIn("## Anti-Examples", self.text)

    def test_minimum_anti_examples(self):
        items = re.findall(r"(?m)^\d+\.\s+\*\*", self.text)
        self.assertGreaterEqual(len(items), 8, f"Need at least 8 anti-examples, found {len(items)}")

    def test_has_bad_good_code_pair(self):
        self.assertIn("BAD:", self.text)
        self.assertIn("GOOD:", self.text)


class TestHonestDegradation(unittest.TestCase):
    def setUp(self):
        self.text = _read(SKILL_MD)

    def test_has_degradation_section(self):
        self.assertIn("## Honest Degradation", self.text)

    def test_three_levels(self):
        for level in ["Full", "Partial", "Blocked"]:
            self.assertIn(f"**{level}**", self.text)


class TestOutputContract(unittest.TestCase):
    def setUp(self):
        self.skill = _read(SKILL_MD)
        self.contract = _read(OUTPUT_CONTRACT)

    def test_9_output_sections(self):
        self.assertIn("9 sections", self.skill)

    def test_contract_has_all_sections(self):
        for i in range(1, 10):
            self.assertRegex(self.contract, rf"## {i}\)")

    def test_contract_has_quality_gates(self):
        self.assertIn("## Quality Gates", self.contract)

    def test_contract_mentions_evidence_chain(self):
        self.assertIn("Evidence chain", self.contract)

    def test_contract_mentions_degradation(self):
        self.assertIn("Degradation", self.contract)

    def test_contract_has_source_tier(self):
        self.assertIn("tier", self.contract.lower())


class TestSafetyRules(unittest.TestCase):
    def setUp(self):
        self.text = _read(SKILL_MD)

    def test_has_safety_section(self):
        self.assertIn("## Safety Rules", self.text)

    def test_no_fabrication_rule(self):
        self.assertRegex(self.text, r"(?i)never\s+fabricate")

    def test_contradiction_surfacing_rule(self):
        self.assertRegex(self.text, r"(?i)contradict.*surfaced")


class TestReferenceFiles(unittest.TestCase):
    def test_output_contract_exists(self):
        self.assertTrue(OUTPUT_CONTRACT.exists())

    def test_hallucination_ref_exists(self):
        self.assertTrue(HALLUCINATION_REF.exists())

    def test_research_patterns_exists(self):
        self.assertTrue(RESEARCH_PATTERNS.exists())

    def test_script_exists(self):
        self.assertTrue(SCRIPT.exists())

    def test_unit_tests_exist(self):
        self.assertTrue(UNIT_TESTS.exists())


class TestHallucinationReference(unittest.TestCase):
    def setUp(self):
        self.text = _read(HALLUCINATION_REF)

    def test_has_hallucination_types(self):
        for htype in ["Fabricated Citation", "Stale Information", "Confidence Inflation", "Phantom Feature"]:
            self.assertIn(htype, self.text)

    def test_has_cross_validation_protocol(self):
        self.assertIn("Cross-Validation Protocol", self.text)

    def test_has_source_tier_ranking(self):
        self.assertIn("Source Tier Ranking", self.text)
        for tier in ["T1", "T2", "T3", "T4", "T5"]:
            self.assertIn(tier, self.text)

    def test_has_numeric_claim_labels(self):
        self.assertIn("Numeric Claim Labels", self.text)

    def test_has_tool_recommendation_table(self):
        self.assertIn("Recommended Tool", self.text)


class TestResearchPatterns(unittest.TestCase):
    def setUp(self):
        self.text = _read(RESEARCH_PATTERNS)

    def test_has_error_debugging_section(self):
        self.assertIn("Error Debugging", self.text)

    def test_has_official_docs_section(self):
        self.assertIn("Official Documentation", self.text)

    def test_has_github_search_section(self):
        self.assertIn("GitHub Code Search", self.text)

    def test_has_tech_comparison_section(self):
        self.assertIn("Technology Comparison", self.text)

    def test_has_benchmark_section(self):
        self.assertIn("Performance Benchmark", self.text)

    def test_has_security_section(self):
        self.assertIn("Security Research", self.text)

    def test_has_codebase_section(self):
        self.assertIn("Codebase Research", self.text)

    def test_has_ai_tool_selection(self):
        self.assertIn("AI Tool Selection", self.text)

    def test_has_query_syntax_reference(self):
        self.assertIn("Query Syntax", self.text)
        for op in ['""', "site:", "filetype:", "intitle:", "after:"]:
            self.assertIn(op, self.text)


class TestSubcommandTable(unittest.TestCase):
    def setUp(self):
        self.text = _read(SKILL_MD)

    def test_has_subcommands_section(self):
        self.assertIn("## Subcommands Reference", self.text)

    def test_all_subcommands_listed(self):
        for cmd in ["retrieve", "fetch-content", "search-codebase", "validate", "report"]:
            self.assertIn(f"`{cmd}`", self.text)


class TestLineCount(unittest.TestCase):
    def test_skill_md_under_500_lines(self):
        lines = _read(SKILL_MD).count("\n") + 1
        self.assertLessEqual(lines, 500, f"SKILL.md is {lines} lines (max 500)")


class TestProgressiveDisclosure(unittest.TestCase):
    def setUp(self):
        self.text = _read(SKILL_MD)

    def test_has_load_references_table(self):
        self.assertIn("## Load References Selectively", self.text)

    def test_references_triggered_by_context(self):
        self.assertIn("Trigger", self.text)
        self.assertIn("Reference", self.text)
        self.assertIn("Timing", self.text)


if __name__ == "__main__":
    unittest.main()
