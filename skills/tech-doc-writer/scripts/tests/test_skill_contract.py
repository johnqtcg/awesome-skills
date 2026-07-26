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

    def _contract_blocks(self):
        """Return the field-name sets of the contract template and its worked example.

        Fields are read out of the block itself rather than hardcoded. The hardcoded list drifted:
        `resolution:` was added to the contract and this test kept passing, because it also
        searched the whole file — any field name appearing in prose counted as present."""
        blocks = []
        current = None
        for line in self.content.splitlines():
            if "── tech-doc-writer output ──" in line:
                current = set()
                blocks.append(current)
                continue
            if current is not None:
                if line.startswith("```"):
                    current = None
                    continue
                m = re.match(r"^([a-z_]+):", line)
                if m:
                    current.add(m.group(1))
        return blocks

    def test_structured_field_names(self):
        blocks = self._contract_blocks()
        self.assertGreaterEqual(len(blocks), 2,
                                "expected a contract template and a worked example")
        template = blocks[0]
        # Floor, so a broken extraction cannot pass by finding nothing.
        self.assertGreaterEqual(len(template), 8,
                                f"contract declares only {len(template)} fields: {template}")
        for field in ("mode", "resolution", "degradation", "doc_type", "audience",
                      "scorecard", "files", "maintenance", "assumptions"):
            self.assertIn(field, template, f"contract template omits `{field}:`")

    def test_worked_example_instantiates_every_field(self):
        """A reader copies the example, not the template — an example missing a field teaches an
        incomplete contract."""
        blocks = self._contract_blocks()
        missing = blocks[0] - blocks[1]
        self.assertFalse(missing,
                         f"worked example omits contract field(s): {sorted(missing)}")

    def test_scorecard_format_specified(self):
        """`<total>` was wrong: the denominator is the APPLICABLE count for the doc type, not a
        fixed total. The contract must say so, or the ⅔-of-applicable rule has no output shape."""
        self.assertIn("Critical: <n>/<applicable>", self.content)
        self.assertRegex(
            self.content, r"(?i)denominators are the APPLICABLE counts",
            "the output contract must state that denominators vary by doc_type",
        )
        self.assertIn("--scorecard", self.content,
                      "the contract should point at the tool that computes the denominators")

    def test_output_contract_requires_the_resolution_field(self):
        """The Resolution Order state machine is unverifiable if the output never records which
        step applied."""
        block = self.content.split("── tech-doc-writer output ──")[1]
        self.assertRegex(block, r"(?m)^resolution:",
                         "output contract must carry a `resolution:` field")
        for step in ("R1", "R2", "R3"):
            self.assertIn(step, block, f"resolution field must enumerate {step}")

    def test_output_contract_has_no_retired_level(self):
        """Level 2.5 was removed from the Degradation Strategy but survived in the contract, so
        the model saw two versions of the level vocabulary."""
        self.assertNotIn("Level 2.5", self.content,
                         "Level 2.5 was retired from the degradation strategy")

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
    """`allowed-tools` is optional in the skill format but conventional here (43 of 51 skills
    declare it), so presence is asserted as a repo convention rather than a format requirement.
    The value is what actually needed checking: the list used to grant `StrReplace`, which is not
    a tool name at all — no other skill in the repo names it, and `Edit` was already granted, so
    it read as a real permission while granting nothing."""

    # Names that exist as tools. A typo here is a silent no-op grant, not an error.
    KNOWN_TOOLS = {
        "Read", "Write", "Edit", "Grep", "Glob", "Bash", "Agent", "Task",
        "WebFetch", "WebSearch", "NotebookEdit", "TodoWrite",
    }

    def setUp(self):
        content = _read_skill()
        m = re.search(r"^---\n(.*?)\n---", content, re.DOTALL)
        self.assertIsNotNone(m, "SKILL.md has no YAML frontmatter")
        self.frontmatter = m.group(1)

    def test_allowed_tools_in_frontmatter(self):
        self.assertIn("allowed-tools:", self.frontmatter,
                      "repo convention: skills declare an explicit least-privilege tool list")

    def test_every_granted_tool_name_is_real(self):
        m = re.search(r"^allowed-tools:\s*(.+)$", self.frontmatter, re.M)
        self.assertIsNotNone(m)
        # `Bash(git log*)` -> `Bash`; scope patterns are not validated here, only the tool name.
        names = {t.split("(")[0].strip() for t in m.group(1).split(",")}
        names.discard("")
        unknown = names - self.KNOWN_TOOLS
        self.assertFalse(unknown,
                         f"allowed-tools grants unrecognised tool name(s) {sorted(unknown)} — a "
                         f"name that is not a tool grants nothing while looking like a permission")

    def test_no_duplicate_tool_grants(self):
        m = re.search(r"^allowed-tools:\s*(.+)$", self.frontmatter, re.M)
        entries = [t.strip() for t in m.group(1).split(",") if t.strip()]
        dupes = {e for e in entries if entries.count(e) > 1}
        self.assertFalse(dupes, f"allowed-tools repeats {sorted(dupes)}")


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

    def test_tier_thresholds_are_ratios_of_applicable_items(self):
        """A fixed `≥ n/total` label was the bug, not the guard: with items tagged by doc type,
        a Concept doc had only 2 applicable Standard items, so `≥ 4/6` was unpassable — the tier
        could never be satisfied no matter how good the document was. Thresholds are now ratios
        of the applicable subset, so the header must say so rather than name a fixed count."""
        import re as _re
        scorecard = self.content.split("Gate 3: Quality Scorecard")[1].split("\n## ")[0]
        for tier in ("Standard", "Hygiene"):
            section = scorecard.split(f"**{tier}")[1]
            if tier == "Standard":
                section = section.split("**Hygiene")[0]
            header = section.split("**")[0]
            self.assertRegex(
                header, r"(⅔|2/3).{0,30}applicable",
                f"{tier} header must state the ⅔-of-applicable rule, not a fixed count",
            )
            self.assertIsNone(
                _re.search(r"≥\s*\d+/\d+\s*pass", header),
                f"{tier} header still declares a fixed count; that made the tier unpassable "
                f"for concept/reference/design docs",
            )

    def test_resolution_order_is_deterministic(self):
        """Gate 2 said "unclear audience → STOP and ASK" while Level 2 said "audience uncertain →
        assume broadest and continue". With no ordering, two runs could legitimately do opposite
        things. The sequence must be explicit and the two must be sequential states."""
        content = self.content
        self.assertIn("Resolution Order", content)
        for step in ("R1", "R2", "R3"):
            self.assertIn(step, content, f"resolution step {step} missing")
        self.assertRegex(
            content, r"(?i)Retrieve\s*(→|->)\s*Ask\s*(→|->)\s*Assume",
            "the ordering Retrieve → Ask → Assume must be stated explicitly",
        )
        self.assertRegex(
            content, r"(?i)sequential states, never alternatives|sequential states, not alternatives",
            "must state that STOP-and-ASK and Level 2 are sequential, not alternatives",
        )
        # "Cannot ask" must be bounded, or R3 becomes a licence to skip asking.
        self.assertRegex(
            content, r'(?i)"?[Cc]annot ask"? means',
            "must define what counts as being unable to ask",
        )
        self.assertRegex(
            content, r"(?i)not\s+.?cannot ask.?|Absence of a reply.{0,60}not",
            "must forbid treating a same-turn non-answer as permission to assume",
        )

    def test_resolution_path_must_be_reported(self):
        self.assertRegex(
            self.content, r"(?i)must state the resolution path|Resolution:\s*R1",
            "the response must record which resolution step applied",
        )

    def test_scoring_rule_defines_na_handling(self):
        scorecard = self.content.split("Gate 3: Quality Scorecard")[1].split("\n## ")[0]
        self.assertIn("N/A", scorecard, "the scoring rule must define N/A handling")
        self.assertRegex(
            scorecard, r"(?i)N/A items? leave the denominator|leave the denominator",
            "must state explicitly that N/A items leave the denominator",
        )
        self.assertRegex(
            scorecard, r"(?i)0 applicable",
            "must define the empty-tier case (0 applicable items)",
        )
        self.assertRegex(
            scorecard, r"(?i)report the arithmetic|N/M applicable|\d+/\d+ applicable",
            "must require the arithmetic to be reported, not just a verdict",
        )

    def test_title_rule_is_language_aware_and_matches_the_linter(self):
        """The flat "≤ 20 characters" rule flagged the skill's own recommended RFC title (45
        chars) and treated 20 CJK characters as equivalent to 20 Latin ones."""
        content = self.content
        self.assertNotRegex(
            content, r"(?i)\*\*S\*\*imple:\s*≤\s*20 characters",
            "the flat character threshold is retired; use the weight budget",
        )
        self.assertRegex(content, r"(?i)language-aware weight budget|weight budget")
        for token in ("CJK character", "Leading identifier", "exempt"):
            self.assertIn(token, content, f"title budget must define {token!r}")
        self.assertRegex(
            content, r"(?i)filler is judged separately|Filler is judged",
            "filler must be a separate rule from length",
        )
        # And the rule must point at the checker so they cannot drift.
        self.assertRegex(content, r"lint_doc\.py.{0,80}title-weight|title-weight")

    def test_phase5_metadata_template_includes_needs_update(self):
        """`needs-update` is accepted by the linter and required by the maintenance flow, but the
        template offered only draft|active|deprecated — forcing a false choice between "this is
        correct" and "do not read this"."""
        m = re.search(r"### Phase 5: Metadata.*?```yaml\n(.*?)```", self.content, re.S)
        self.assertIsNotNone(m, "Phase 5 metadata template not found")
        template = m.group(1)
        for value in ("draft", "active", "needs-update", "deprecated"):
            self.assertIn(value, template,
                          f"status template must offer {value!r}")
        self.assertIn("applicable_versions", template)
        self.assertIn("title", template)

    def test_ci_example_does_not_ship_unverified_pins(self):
        """A skill that preaches anti-staleness must not ship rotting action pins. The example
        carried `checkout@v4`, `markdownlint-cli2-action@v18`, and an action its author has since
        archived — presented as current."""
        path = os.path.join(SKILL_DIR, "references", "docs-as-code.md")
        with open(path, encoding="utf-8") as fh:
            docs_as_code = fh.read()

        # Concrete majors must not be presented as current inside the workflow example.
        offenders = re.findall(r"uses:\s*[\w.-]+/[\w.-]+@v\d+", docs_as_code)
        self.assertFalse(
            offenders,
            "workflow example pins concrete action majors that will rot; use @vN with a "
            f"verify-before-use note: {offenders}",
        )
        # The archived action must not be recommended.
        self.assertNotRegex(
            docs_as_code, r"uses:\s*gaurav-nelson/github-action-markdown-link-check",
            "that link-check action is archived; recommend a maintained checker",
        )
        # And the systemic fix must be present, not just a warning.
        self.assertIn("dependabot.yml", docs_as_code,
                      "action staleness needs an automated fix, not only a caution")
        self.assertIn("package-ecosystem: github-actions", docs_as_code)
        self.assertRegex(
            docs_as_code,
            r"(?is)(verify|resolve|confirm)[^.]{0,80}(before|against)[^.]{0,80}"
            r"(adopt|current|release)"
            r"|[Bb]efore adopting[^.]{0,80}(resolve|verify|confirm)",
            "must tell the reader to resolve each pin against its current release before use",
        )
        self.assertRegex(
            docs_as_code, r"(?m)^permissions:",
            "the example workflow should declare least-privilege permissions",
        )

    def test_linter_scorecard_table_matches_skill_items(self):
        """Cross-file drift guard: lint_doc.py computes the denominator, so its SCORECARD table
        must carry the same number of items per tier as SKILL.md lists. If they drift, the tool
        and the rule disagree about what counts."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "lint_doc", os.path.join(SKILL_DIR, "scripts", "lint_doc.py"))
        lint_doc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(lint_doc)

        scorecard = self.content.split("Gate 3: Quality Scorecard")[1].split("\n## ")[0]
        # Split on the header form `**Tier (` — the bare `**Tier` token also appears in the
        # scoring-rule prose above, which silently truncated the section to nothing.
        for tier in ("Critical", "Standard", "Hygiene"):
            section = scorecard.split(f"**{tier} (")[1]
            for later in ("**Standard (", "**Hygiene ("):
                if later != f"**{tier} (" and later in section:
                    section = section.split(later)[0]
            doc_items = section.count("- [ ]")
            tool_items = len(lint_doc.SCORECARD[tier])
            self.assertEqual(
                doc_items, tool_items,
                f"{tier}: SKILL.md lists {doc_items} items but lint_doc.SCORECARD has "
                f"{tool_items} — the computed denominator would be wrong",
            )


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
