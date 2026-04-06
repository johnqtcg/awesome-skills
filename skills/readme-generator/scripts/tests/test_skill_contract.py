import re
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[2]
SKILL_MD = SKILL_DIR / "SKILL.md"
TEMPLATES_REF = SKILL_DIR / "references" / "templates.md"
CHECKLIST_REF = SKILL_DIR / "references" / "checklist.md"
COMMAND_REF = SKILL_DIR / "references" / "command-priority.md"
GOLDEN_REF = SKILL_DIR / "references" / "golden-examples.md"
ANTI_EXAMPLES_REF = SKILL_DIR / "references" / "anti-examples.md"
DISCOVER_SCRIPT = SKILL_DIR / "scripts" / "discover_readme_needs.sh"


def frontmatter(text: str) -> str:
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        raise AssertionError("missing yaml frontmatter")
    return match.group(1)


def skill_text() -> str:
    return SKILL_MD.read_text()


def anti_examples_text() -> str:
    """Anti-examples live in references/anti-examples.md (progressive disclosure)."""
    return ANTI_EXAMPLES_REF.read_text()


# ── 1. Frontmatter ──────────────────────────────────────────────

class TestFrontmatter(unittest.TestCase):
    def test_name(self):
        self.assertIn("name: readme-generator", frontmatter(skill_text()))

    def test_description_keywords(self):
        fm = frontmatter(skill_text())
        for kw in ["README", "generate", "refactor", "service", "library", "CLI", "monorepo"]:
            self.assertIn(kw.lower(), fm.lower(), f"missing keyword: {kw}")

    def test_description_length(self):
        fm = frontmatter(skill_text())
        desc_line = [l for l in fm.splitlines() if l.startswith("description:")][0]
        self.assertGreater(len(desc_line), 80, "description too short")


# ── 2. Pre-Generation Gates ─────────────────────────────────────

class TestGates(unittest.TestCase):
    def test_audience_gate(self):
        self.assertIn("Audience and Language Gate", skill_text())

    def test_project_type_gate(self):
        self.assertIn("Project Type Routing", skill_text())

    def test_command_verifiability_gate(self):
        self.assertIn("Command Verifiability Gate", skill_text())

    def test_evidence_completeness_gate(self):
        self.assertIn("Evidence Completeness Gate", skill_text())

    def test_gate_count(self):
        data = skill_text()
        gates = re.findall(r"###\s+\d+\)\s+.+(?:Gate|Routing)", data)
        self.assertGreaterEqual(len(gates), 4, f"only {len(gates)} gates found")

    def test_project_types_listed(self):
        data = skill_text()
        for pt in ["Service", "Library", "CLI", "Monorepo"]:
            self.assertIn(pt, data, f"project type missing: {pt}")


# ── 3. Anti-Examples ────────────────────────────────────────────

class TestAntiExamples(unittest.TestCase):
    def test_section_exists(self):
        self.assertIn("Anti-Examples (BAD / GOOD Markdown Pairs)", skill_text())

    def test_bad_good_count(self):
        # High-frequency top example stays inline; full catalog in references/anti-examples.md
        inline = skill_text()
        ref = anti_examples_text()
        combined = inline + "\n" + ref
        bad_count = len(re.findall(r"^BAD:", combined, re.MULTILINE))
        good_count = len(re.findall(r"^GOOD:", combined, re.MULTILINE))
        self.assertGreaterEqual(bad_count, 7, f"only {bad_count} BAD examples")
        self.assertGreaterEqual(good_count, 7, f"only {good_count} GOOD examples")

    def test_anti_example_topics(self):
        # Topics are split: top failure inline in SKILL.md, full catalog in references/anti-examples.md
        combined = skill_text() + "\n" + anti_examples_text()
        topics = [
            "process labels",
            "Maintainer workflow",
            "badge",
            "configuration",
            "monorepo",
            "Double-language",
            "Output snippet",
        ]
        for t in topics:
            self.assertIn(t.lower(), combined.lower(), f"anti-example topic missing: {t}")

    def test_anti_examples_have_markdown_code(self):
        data = skill_text() + "\n" + anti_examples_text()
        anti_section_start = data.index("Anti-Examples")
        anti_section = data[anti_section_start:]
        code_blocks = re.findall(r"```markdown", anti_section)
        self.assertGreaterEqual(len(code_blocks), 7, "anti-examples lack markdown code blocks")


# ── 4. Three-Tier Scorecard ─────────────────────────────────────

class TestScorecard(unittest.TestCase):
    def test_section_exists(self):
        self.assertIn("README Quality Scorecard (3-Tier)", skill_text())

    def test_critical_tier(self):
        data = skill_text()
        self.assertIn("Critical Tier", data)
        self.assertTrue("any FAIL" in data or "any fail" in data.lower(),
                        "critical tier missing one-vote-veto rule")

    def test_standard_tier(self):
        data = skill_text()
        self.assertIn("Standard Tier", data)
        self.assertIn("4/6", data)

    def test_hygiene_tier(self):
        data = skill_text()
        self.assertIn("Hygiene Tier", data)
        self.assertIn("3/4", data)

    def test_critical_items(self):
        data = skill_text()
        for item in ["Evidence-backed", "No fabricated", "Quick Start", "project type routing"]:
            self.assertIn(item.lower(), data.lower(), f"critical item missing: {item}")

    def test_standard_items(self):
        data = skill_text()
        for item in ["Command source", "Structure section", "Config", "Testing", "Badges", "Audience"]:
            self.assertIn(item, data, f"standard item missing: {item}")

    def test_hygiene_items(self):
        data = skill_text()
        for item in ["Maintenance trigger", "internal process labels", "Navigation", "Optional sections"]:
            self.assertIn(item.lower(), data.lower(), f"hygiene item missing: {item}")

    def test_output_format(self):
        self.assertIn("Critical:", skill_text())
        self.assertIn("Standard:", skill_text())
        self.assertIn("Hygiene:", skill_text())


# ── 5. Selective Loading ────────────────────────────────────────

class TestSelectiveLoading(unittest.TestCase):
    def test_section_exists(self):
        self.assertIn("Load References Selectively", skill_text())

    def test_all_refs_listed(self):
        data = skill_text()
        for ref in ["templates.md", "golden-examples.md", "command-priority.md", "checklist.md"]:
            self.assertIn(ref, data, f"reference not listed: {ref}")

    def test_conditions_present(self):
        data = skill_text()
        loading_section = data[data.index("Load References Selectively"):]
        for condition in ["from scratch", "calibrating", "command conflicts", "final review"]:
            self.assertIn(condition.lower(), loading_section.lower(),
                          f"loading condition missing: {condition}")


# ── 6. Badge Strategy ───────────────────────────────────────────

class TestBadgeStrategy(unittest.TestCase):
    def test_section_exists(self):
        self.assertIn("Badge Strategy", skill_text())

    def test_detection_order(self):
        data = skill_text()
        for badge_type in ["CI status", "Coverage", "Language version", "License", "Release"]:
            self.assertIn(badge_type, data, f"badge type missing: {badge_type}")

    def test_private_repo_fallback(self):
        self.assertIn("private", skill_text().lower())
        self.assertIn("Badge note: repository is private", skill_text())


# ── 7. Evidence Mapping ────────────────────────────────────────

class TestEvidenceMapping(unittest.TestCase):
    def test_section_exists(self):
        self.assertIn("Evidence Mapping Output (Required)", skill_text())

    def test_table_format(self):
        data = skill_text()
        self.assertIn("README Section", data)
        self.assertIn("Evidence File(s)", data)
        self.assertIn("Evidence Snippet/Reason", data)

    def test_not_found_rule(self):
        self.assertIn("Not found in repo", skill_text())


# ── 8. Lightweight Mode ────────────────────────────────────────

class TestLightweightMode(unittest.TestCase):
    def test_section_exists(self):
        self.assertIn("Lightweight Template Mode", skill_text())

    def test_trigger_conditions(self):
        data = skill_text()
        self.assertIn("fewer than 5", data)
        self.assertIn("no deployment", data.lower())

    def test_lightweight_sections(self):
        data = skill_text()
        for s in ["Project overview", "Quick start", "Common commands"]:
            self.assertIn(s, data)


# ── 9. Chinese / Bilingual ──────────────────────────────────────

class TestChineseBilingual(unittest.TestCase):
    def test_section_exists(self):
        self.assertIn("Chinese / Bilingual README Guidelines", skill_text())

    def test_keep_english_rule(self):
        self.assertIn("Keep English for", skill_text())

    def test_heading_style(self):
        self.assertIn("快速开始", skill_text())


# ── 10. Update Triggers ────────────────────────────────────────

class TestUpdateTriggers(unittest.TestCase):
    def test_section_exists(self):
        self.assertIn("README Update Triggers", skill_text())

    def test_key_triggers(self):
        data = skill_text()
        for trigger in ["Makefile target", "CI workflow", "Environment variable",
                         "LICENSE", "Go version"]:
            self.assertIn(trigger, data, f"trigger missing: {trigger}")


# ── 11. Templates Reference ────────────────────────────────────

class TestTemplatesRef(unittest.TestCase):
    def test_file_exists(self):
        self.assertTrue(TEMPLATES_REF.exists())

    def test_all_templates(self):
        data = TEMPLATES_REF.read_text()
        for tmpl in ["Template A: Service", "Template B: Library", "Template C: CLI",
                      "Template D: Monorepo", "Template E: Lightweight"]:
            self.assertIn(tmpl, data, f"template missing: {tmpl}")

    def test_templates_depth(self):
        lines = len(TEMPLATES_REF.read_text().splitlines())
        self.assertGreaterEqual(lines, 200, f"templates.md too thin: {lines} lines")

    def test_no_verification_status_in_templates(self):
        data = TEMPLATES_REF.read_text()
        self.assertNotIn("Status: `{Verified | Not verified in this environment}`", data)


# ── 12. Golden Examples Reference ───────────────────────────────

class TestGoldenExamplesRef(unittest.TestCase):
    def test_file_exists(self):
        self.assertTrue(GOLDEN_REF.exists())

    def test_toc_present(self):
        data = GOLDEN_REF.read_text()
        self.assertIn("Table of Contents", data)

    def test_example_count(self):
        data = GOLDEN_REF.read_text()
        examples = re.findall(r"^## Example \d+:", data, re.MULTILINE)
        self.assertGreaterEqual(len(examples), 5, f"only {len(examples)} golden examples")

    def test_project_types_covered(self):
        data = GOLDEN_REF.read_text()
        for pt in ["Service", "Library", "CLI", "Monorepo", "Lightweight"]:
            self.assertIn(pt, data, f"golden example missing for: {pt}")

    def test_evidence_mappings_present(self):
        data = GOLDEN_REF.read_text()
        mappings = re.findall(r"Evidence mapping", data, re.IGNORECASE)
        self.assertGreaterEqual(len(mappings), 3, "golden examples lack evidence mapping tables")

    def test_repo_signals_documented(self):
        data = GOLDEN_REF.read_text()
        signals = re.findall(r"\*\*Repo signals\*\*:", data)
        self.assertGreaterEqual(len(signals), 4, "golden examples lack repo signal descriptions")

    def test_depth(self):
        lines = len(GOLDEN_REF.read_text().splitlines())
        self.assertGreaterEqual(lines, 200, f"golden-examples.md too thin: {lines} lines")


# ── 13. Command Priority Reference ─────────────────────────────

class TestCommandPriorityRef(unittest.TestCase):
    def test_file_exists(self):
        self.assertTrue(COMMAND_REF.exists())

    def test_priority_ladder(self):
        data = COMMAND_REF.read_text()
        self.assertIn("Priority Ladder", data)
        self.assertIn("Makefile", data)

    def test_language_patterns(self):
        data = COMMAND_REF.read_text()
        for lang in ["Go", "Node.js", "Python", "Rust"]:
            self.assertIn(lang, data, f"language pattern missing: {lang}")

    def test_conflict_resolution(self):
        data = COMMAND_REF.read_text()
        self.assertIn("Conflict Resolution", data)

    def test_makefile_extraction(self):
        data = COMMAND_REF.read_text()
        self.assertIn("Makefile Target Extraction", data)

    def test_depth(self):
        lines = len(COMMAND_REF.read_text().splitlines())
        self.assertGreaterEqual(lines, 100, f"command-priority.md too thin: {lines} lines")


# ── 14. Checklist Reference ────────────────────────────────────

class TestChecklistRef(unittest.TestCase):
    def test_file_exists(self):
        self.assertTrue(CHECKLIST_REF.exists())

    def test_three_phases(self):
        data = CHECKLIST_REF.read_text()
        for phase in ["Phase 1: Before Drafting", "Phase 2: During Drafting", "Phase 3: Final Review"]:
            self.assertIn(phase, data, f"phase missing: {phase}")

    def test_common_mistakes_by_type(self):
        data = CHECKLIST_REF.read_text()
        self.assertIn("Common Mistakes by Project Type", data)
        for pt in ["Service", "Library", "CLI", "Monorepo", "Lightweight"]:
            self.assertIn(pt, data, f"project type mistakes missing: {pt}")

    def test_refactoring_checklist(self):
        data = CHECKLIST_REF.read_text()
        self.assertIn("Refactoring Existing README", data)

    def test_update_trigger_matrix(self):
        data = CHECKLIST_REF.read_text()
        self.assertIn("Update Trigger Matrix", data)

    def test_depth(self):
        lines = len(CHECKLIST_REF.read_text().splitlines())
        self.assertGreaterEqual(lines, 80, f"checklist.md too thin: {lines} lines")


# ── 15. Structural Integrity ───────────────────────────────────

class TestStructuralIntegrity(unittest.TestCase):
    def test_generation_workflow_steps(self):
        data = skill_text()
        self.assertIn("Generation Workflow", data)
        steps = re.findall(r"^\d+\.\s", data[data.index("Generation Workflow"):], re.MULTILINE)
        self.assertGreaterEqual(len(steps), 10, f"workflow has only {len(steps)} steps")

    def test_key_evidence_targets(self):
        data = skill_text()
        self.assertIn("Key Evidence Targets", data)
        for target in ["main.go", "Makefile", "go.mod", ".github/workflows"]:
            self.assertIn(target, data, f"evidence target missing: {target}")

    def test_monorepo_rules(self):
        self.assertIn("Monorepo Rules", skill_text())

    def test_navigation_rule(self):
        self.assertIn("README Navigation Rule", skill_text())

    def test_end_to_end_example_rule(self):
        self.assertIn("End-to-End Example Rule", skill_text())

    def test_output_style(self):
        self.assertIn("Output Style", skill_text())

    def test_community_files(self):
        data = skill_text()
        self.assertIn("Community and Governance Files", data)
        for f in ["LICENSE", "CONTRIBUTING.md", "SECURITY.md", "CHANGELOG.md"]:
            self.assertIn(f, data, f"community file missing: {f}")


# ── 17. Output Contract ─────────────────────────────────────────

class TestOutputContract(unittest.TestCase):
    def test_section_exists(self):
        self.assertIn("Output Contract (Mandatory Fields)", skill_text())

    def test_mandatory_fields(self):
        data = skill_text()
        for field in ["project_type", "language", "template_used", "evidence_mapping",
                       "scorecard", "degraded", "missing_evidence", "badges_added",
                       "sections_omitted"]:
            self.assertIn(field, data, f"output field missing: {field}")

    def test_json_format(self):
        data = skill_text()
        self.assertIn("Machine-Readable Summary (JSON)", data)
        self.assertIn('"project_type"', data)
        self.assertIn('"scorecard"', data)
        self.assertIn('"result": "PASS"', data)

    def test_field_count(self):
        data = skill_text()
        contract_start = data.index("Output Contract")
        contract_section = data[contract_start:data.index("## README Quality Scorecard")]
        field_rows = re.findall(r"\|\s+\d+\s+\|", contract_section)
        self.assertGreaterEqual(len(field_rows), 9, f"only {len(field_rows)} output fields")


# ── 18. Discover Script ─────────────────────────────────────────

class TestDiscoverScript(unittest.TestCase):
    def test_script_exists(self):
        self.assertTrue(DISCOVER_SCRIPT.exists(), "discover_readme_needs.sh not found")

    def test_script_executable(self):
        import os
        self.assertTrue(os.access(str(DISCOVER_SCRIPT), os.X_OK),
                        "discover script not executable")

    def test_script_referenced_in_skill(self):
        data = skill_text()
        self.assertIn("discover_readme_needs.sh", data)

    def test_script_in_selective_loading(self):
        data = skill_text()
        loading = data[data.index("Load References Selectively"):]
        self.assertIn("discover_readme_needs", loading)

    def test_script_in_workflow(self):
        data = skill_text()
        workflow = data[data.index("Generation Workflow"):]
        self.assertIn("discover_readme_needs", workflow)

    def test_script_dimensions(self):
        script = DISCOVER_SCRIPT.read_text()
        for dim in ["project_type", "language_version", "build_system", "ci_platform",
                     "configuration", "community_files", "quality_tools",
                     "existing_readme", "visibility", "verdict"]:
            self.assertIn(dim, script, f"discovery dimension missing: {dim}")

    def test_script_outputs_tsv(self):
        script = DISCOVER_SCRIPT.read_text()
        self.assertIn("printf", script)
        self.assertIn("\\t", script)


# ── 19. Version-Specific Rules ──────────────────────────────────

class TestVersionRules(unittest.TestCase):
    def test_section_exists(self):
        data = COMMAND_REF.read_text()
        self.assertIn("Version-Specific Command Rules", data)

    def test_go_version_rules(self):
        data = COMMAND_REF.read_text()
        self.assertIn("Go Version Rules", data)
        for ver in ["1.17", "1.18", "1.21", "1.22"]:
            self.assertIn(ver, data, f"Go version {ver} rule missing")

    def test_node_version_rules(self):
        data = COMMAND_REF.read_text()
        self.assertIn("Node.js Version Rules", data)

    def test_python_version_rules(self):
        data = COMMAND_REF.read_text()
        self.assertIn("Python Version Rules", data)

    def test_rust_version_rules(self):
        data = COMMAND_REF.read_text()
        self.assertIn("Rust Version Rules", data)

    def test_how_to_apply(self):
        data = COMMAND_REF.read_text()
        self.assertIn("How to Apply", data)

    def test_command_priority_depth(self):
        lines = len(COMMAND_REF.read_text().splitlines())
        self.assertGreaterEqual(lines, 200, f"command-priority.md: {lines} lines (need ≥200)")


# ── 20. Degradation Patterns ───────────────────────────────────

class TestDegradationPatterns(unittest.TestCase):
    def test_section_exists(self):
        data = CHECKLIST_REF.read_text()
        self.assertIn("Degradation Patterns", data)

    def test_degradation_levels(self):
        data = CHECKLIST_REF.read_text()
        self.assertIn("Degradation Levels", data)
        for level in ["Full evidence", "Partial evidence", "Minimal evidence", "No evidence"]:
            self.assertIn(level, data, f"degradation level missing: {level}")

    def test_evidence_gate_in_skill(self):
        data = skill_text()
        self.assertIn("degraded", data)
        self.assertIn("minimum evidence", data.lower())

    def test_checklist_depth(self):
        lines = len(CHECKLIST_REF.read_text().splitlines())
        self.assertGreaterEqual(lines, 150, f"checklist.md: {lines} lines (need ≥150)")

    def test_common_mistakes_have_evidence_column(self):
        data = CHECKLIST_REF.read_text()
        self.assertIn("Evidence to Check", data)


# ── 21. Cross-Cutting Integrity ─────────────────────────────────

class TestCrossCuttingIntegrity(unittest.TestCase):
    def test_skill_md_under_600_lines(self):
        lines = len(skill_text().splitlines())
        self.assertLessEqual(lines, 600, f"SKILL.md is {lines} lines (max 600)")

    def test_all_reference_files_exist(self):
        for ref in [TEMPLATES_REF, GOLDEN_REF, COMMAND_REF, CHECKLIST_REF]:
            self.assertTrue(ref.exists(), f"reference missing: {ref.name}")

    def test_total_content_depth(self):
        total = 0
        for f in [SKILL_MD, TEMPLATES_REF, GOLDEN_REF, COMMAND_REF, CHECKLIST_REF]:
            total += len(f.read_text().splitlines())
        self.assertGreaterEqual(total, 1500, f"total content: {total} lines (need ≥1500)")


if __name__ == "__main__":
    unittest.main()
