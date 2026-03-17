"""
Contract tests for tech-doc-writer skill.

Verifies structural integrity against the 10-item quality checklist
from skill最佳实践.md Appendix C, plus domain-specific requirements
for a technical writing skill.

Run: python3 -m unittest scripts/tests/test_skill_contract.py -v
"""

import os
import re
import unittest

SKILL_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
SKILL_MD = os.path.join(SKILL_DIR, "SKILL.md")
REFS_DIR = os.path.join(SKILL_DIR, "references")


def _read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _read_skill():
    return _read(SKILL_MD)


# ─── Checklist #1: description contains trigger keywords ───


class TestDescription(unittest.TestCase):
    def setUp(self):
        self.content = _read_skill()
        m = re.search(r"^---\n(.*?)\n---", self.content, re.DOTALL)
        self.frontmatter = m.group(1) if m else ""

    def test_has_frontmatter(self):
        self.assertIn("---", self.content[:10])

    def test_name_field(self):
        self.assertIn("name: tech-doc-writer", self.frontmatter)

    def test_description_field(self):
        self.assertIn("description:", self.frontmatter)

    def test_description_has_chinese_keywords(self):
        chinese_kw = ["技术文档", "设计文档", "操作手册", "故障报告", "API文档"]
        found = sum(1 for kw in chinese_kw if kw in self.frontmatter)
        self.assertGreaterEqual(found, 3, f"Need ≥3 Chinese keywords, found {found}")

    def test_description_has_english_keywords(self):
        english_kw = ["RFC", "ADR", "runbook", "review", "troubleshoot"]
        found = sum(1 for kw in english_kw if kw.lower() in self.frontmatter.lower())
        self.assertGreaterEqual(found, 3, f"Need ≥3 English keywords, found {found}")

    def test_allowed_tools(self):
        self.assertIn("allowed-tools:", self.frontmatter)


# ─── Checklist #2: SKILL.md ≤ 500 lines ───


class TestSkillSize(unittest.TestCase):
    def test_under_500_lines(self):
        lines = _read_skill().count("\n")
        self.assertLessEqual(lines, 500, f"SKILL.md is {lines} lines, max 500")


# ─── Checklist #3: Mandatory gates ───


class TestMandatoryGates(unittest.TestCase):
    def setUp(self):
        self.content = _read_skill()

    def test_has_mandatory_gates_section(self):
        self.assertIn("## Mandatory Gates", self.content)

    def test_gate_0_execution_integrity(self):
        self.assertIn("Gate 0", self.content)
        self.assertIn("Execution Integrity", self.content)

    def test_gate_1_repo_context(self):
        self.assertIn("Gate 1", self.content)

    def test_gate_2_document_type(self):
        self.assertIn("Gate 2", self.content)

    def test_gate_3_quality_scorecard(self):
        self.assertIn("Gate 3", self.content)
        self.assertIn("Quality Scorecard", self.content)

    def test_stop_and_ask_gates(self):
        count = self.content.count("STOP and ASK")
        self.assertGreaterEqual(count, 2, "Need ≥2 STOP and ASK checkpoints")


# ─── Checklist #4: Anti-examples ───


class TestAntiExamples(unittest.TestCase):
    def setUp(self):
        self.skill_content = _read_skill()
        self.guide_content = _read(os.path.join(REFS_DIR, "writing-quality-guide.md"))

    def test_skill_references_anti_examples(self):
        """SKILL.md must reference Anti-Examples (pointer to writing-quality-guide.md)."""
        self.assertIn("Anti-Examples", self.skill_content)

    def test_anti_examples_in_quality_guide(self):
        """Full anti-examples list lives in writing-quality-guide.md §Anti-Examples."""
        self.assertIn("§Anti-Examples", self.guide_content)
        section = self.guide_content.split("§Anti-Examples")[1]
        numbered = re.findall(r"^\d+\.", section, re.MULTILINE)
        self.assertGreaterEqual(len(numbered), 8, f"Need ≥8 anti-examples in guide, found {len(numbered)}")


# ─── Checklist #5: Reference loading conditions ───


class TestReferenceLoading(unittest.TestCase):
    def setUp(self):
        self.content = _read_skill()

    def test_has_selective_loading_section(self):
        self.assertIn("Load References Selectively", self.content)

    def test_templates_loading_condition(self):
        self.assertIn("templates.md", self.content)

    def test_quality_guide_loading_condition(self):
        self.assertIn("writing-quality-guide.md", self.content)

    def test_docs_as_code_loading_condition(self):
        self.assertIn("docs-as-code.md", self.content)

    def test_review_patterns_loading_condition(self):
        self.assertIn("§Review Patterns", self.content)


# ─── Checklist #6: Output contract ───


class TestOutputContract(unittest.TestCase):
    def setUp(self):
        self.content = _read_skill()

    def test_has_output_contract_section(self):
        self.assertIn("## Output Contract", self.content)

    def test_structured_field_names(self):
        fields = ["mode:", "degradation:", "doc_type:", "audience:",
                   "scorecard:", "files:", "maintenance:", "assumptions:"]
        for field in fields:
            self.assertIn(field, self.content, f"Missing structured field: {field}")

    def test_scorecard_format_specified(self):
        self.assertIn("Critical: <n>/<total>", self.content)

    def test_has_example_block(self):
        self.assertIn("tech-doc-writer output", self.content)


# ─── Checklist #7: Version/platform awareness ───


class TestVersionAwareness(unittest.TestCase):
    def setUp(self):
        self.content = _read_skill()

    def test_applicable_versions_mentioned(self):
        self.assertIn("applicable_versions", self.content)

    def test_metadata_template(self):
        self.assertIn("last_updated", self.content)
        self.assertIn("status:", self.content)


# ─── Checklist #8: Degradation strategy ───


class TestDegradation(unittest.TestCase):
    def setUp(self):
        self.content = _read_skill()

    def test_has_degradation_section(self):
        self.assertIn("## Degradation Strategy", self.content)

    def test_three_levels(self):
        for level in ["Level 1", "Level 2", "Level 3"]:
            self.assertIn(level, self.content, f"Missing degradation {level}")

    def test_full_partial_scaffold(self):
        for label in ["Full", "Partial", "Scaffold"]:
            self.assertIn(label, self.content, f"Missing degradation label: {label}")


# ─── Checklist #9: allowed-tools ───


class TestAllowedTools(unittest.TestCase):
    def test_allowed_tools_in_frontmatter(self):
        content = _read_skill()
        m = re.search(r"^---\n(.*?)\n---", content, re.DOTALL)
        self.assertIsNotNone(m)
        self.assertIn("allowed-tools:", m.group(1))


# ─── Checklist #10: Contract tests exist (self-referential) ───


class TestSelfValidation(unittest.TestCase):
    def test_skill_references_regression_script(self):
        self.assertIn("run_regression.sh", _read_skill())

    def test_regression_script_exists(self):
        self.assertTrue(
            os.path.exists(os.path.join(SKILL_DIR, "scripts", "run_regression.sh"))
        )


# ─── Reference file existence ───


class TestReferenceFiles(unittest.TestCase):
    def test_templates_exists(self):
        self.assertTrue(os.path.exists(os.path.join(REFS_DIR, "templates.md")))

    def test_quality_guide_exists(self):
        self.assertTrue(os.path.exists(os.path.join(REFS_DIR, "writing-quality-guide.md")))

    def test_docs_as_code_exists(self):
        self.assertTrue(os.path.exists(os.path.join(REFS_DIR, "docs-as-code.md")))

    def test_templates_has_toc(self):
        content = _read(os.path.join(REFS_DIR, "templates.md"))
        self.assertIn("## Table of Contents", content)

    def test_quality_guide_has_toc(self):
        content = _read(os.path.join(REFS_DIR, "writing-quality-guide.md"))
        self.assertIn("## Table of Contents", content)


# ─── Golden scenario tests exist ───


class TestGoldenInfrastructure(unittest.TestCase):
    def test_golden_test_file_exists(self):
        self.assertTrue(
            os.path.exists(os.path.join(SKILL_DIR, "scripts", "tests", "test_golden_scenarios.py"))
        )

    def test_golden_dir_exists(self):
        golden_dir = os.path.join(SKILL_DIR, "scripts", "tests", "golden")
        self.assertTrue(os.path.isdir(golden_dir))

    def test_minimum_golden_fixtures(self):
        golden_dir = os.path.join(SKILL_DIR, "scripts", "tests", "golden")
        fixtures = [f for f in os.listdir(golden_dir) if f.endswith(".json")]
        self.assertGreaterEqual(len(fixtures), 6, f"Need ≥6 golden fixtures, found {len(fixtures)}")


# ─── Templates coverage ───


class TestTemplatesCoverage(unittest.TestCase):
    def setUp(self):
        self.content = _read(os.path.join(REFS_DIR, "templates.md"))

    def test_task_template(self):
        self.assertIn("Task Document", self.content)

    def test_concept_template(self):
        self.assertIn("Concept Document", self.content)

    def test_reference_template(self):
        self.assertIn("Reference Document", self.content)

    def test_troubleshooting_template(self):
        self.assertIn("Troubleshooting Document", self.content)

    def test_design_template(self):
        self.assertIn("Design Document", self.content)


# ─── Quality guide sections ───


class TestQualityGuideSections(unittest.TestCase):
    def setUp(self):
        self.content = _read(os.path.join(REFS_DIR, "writing-quality-guide.md"))

    def test_funnel_structure_section(self):
        self.assertIn("§Funnel Structure", self.content)

    def test_bad_good_examples_section(self):
        self.assertIn("§BAD/GOOD Examples", self.content)

    def test_code_examples_section(self):
        self.assertIn("§Code Examples", self.content)

    def test_visual_expression_section(self):
        self.assertIn("§Visual Expression", self.content)

    def test_review_patterns_section(self):
        self.assertIn("§Review Patterns", self.content)

    def test_has_bad_examples(self):
        self.assertGreaterEqual(self.content.count("**BAD**"), 3)

    def test_has_good_examples(self):
        self.assertGreaterEqual(self.content.count("**GOOD**"), 3)


# ─── Quality scorecard tiers ───


class TestQualityScorecard(unittest.TestCase):
    def setUp(self):
        self.content = _read_skill()

    def test_three_tiers(self):
        for tier in ["Critical", "Standard", "Hygiene"]:
            self.assertIn(f"**{tier}", self.content, f"Missing scorecard tier: {tier}")

    def test_critical_has_checkboxes(self):
        scorecard = self.content.split("Gate 3: Quality Scorecard")[1].split("\n## ")[0]
        critical_section = scorecard.split("**Standard")[0]
        checks = critical_section.count("- [ ]")
        self.assertGreaterEqual(checks, 3, f"Need ≥3 Critical checks, found {checks}")

    def test_standard_has_checkboxes(self):
        scorecard = self.content.split("Gate 3: Quality Scorecard")[1].split("\n## ")[0]
        standard_section = scorecard.split("**Standard")[1].split("**Hygiene")[0]
        checks = standard_section.count("- [ ]")
        self.assertGreaterEqual(checks, 4, f"Need ≥4 Standard checks, found {checks}")


# ─── Execution modes ───


class TestExecutionModes(unittest.TestCase):
    def setUp(self):
        self.content = _read_skill()

    def test_write_mode(self):
        self.assertIn("### Write", self.content)

    def test_review_mode(self):
        self.assertIn("### Review", self.content)

    def test_improve_mode(self):
        self.assertIn("### Improve", self.content)


# ─── Hard rules ───


class TestHardRules(unittest.TestCase):
    def setUp(self):
        self.content = _read_skill()

    def test_has_hard_rules(self):
        self.assertIn("## Hard Rules", self.content)

    def test_reader_first_rule(self):
        self.assertIn("Reader-first", self.content)

    def test_one_doc_one_job(self):
        self.assertIn("One doc, one job", self.content)

    def test_evidence_over_opinion(self):
        self.assertIn("Evidence over opinion", self.content)


# ─── Document type classification ───


class TestDocTypeClassification(unittest.TestCase):
    def setUp(self):
        self.content = _read_skill()

    def test_five_doc_types(self):
        types = ["Concept doc", "Task doc", "Reference doc",
                 "Troubleshooting doc", "Design doc"]
        for t in types:
            self.assertIn(t, self.content, f"Missing doc type: {t}")


# ─── Maintenance section ───


class TestMaintenanceSection(unittest.TestCase):
    def setUp(self):
        self.content = _read_skill()

    def test_has_maintenance_section(self):
        self.assertIn("Document Maintenance", self.content)

    def test_update_triggers(self):
        self.assertIn("update trigger", self.content.lower())

    def test_status_lifecycle(self):
        for status in ["active", "needs-update", "deprecated"]:
            self.assertIn(status, self.content)

    def test_review_cadence(self):
        self.assertIn("review cadence", self.content.lower())


if __name__ == "__main__":
    unittest.main()
