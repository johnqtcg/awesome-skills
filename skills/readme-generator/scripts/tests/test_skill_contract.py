import importlib.util
import re
import sys
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
LINT_SCRIPT = SKILL_DIR / "scripts" / "lint_readme.py"
COVERAGE_DOC = Path(__file__).resolve().parent / "COVERAGE.md"
TEST_MODULES = ("test_skill_contract.py", "test_golden_scenarios.py",
                "test_discovery_script.py", "test_forward_eval.py")


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


def _load_linter():
    """Load lint_readme.py so the contract tests check templates against the SAME
    required-section table the grader enforces, instead of a second copy that can drift.

    Registered in sys.modules before exec: @dataclass resolves field types through
    sys.modules[cls.__module__], which is None for an unregistered spec-built module.
    """
    spec = importlib.util.spec_from_file_location("lint_readme", LINT_SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def templates() -> dict:
    """{'service': body, 'library': …} extracted from references/templates.md."""
    text = TEMPLATES_REF.read_text()
    out = {}
    pattern = re.compile(
        r"^## Template ([A-E]): ([^\n]+)\n(.*?)^````\s*(?:markdown)?\s*\n(.*?)^````",
        re.MULTILINE | re.DOTALL,
    )
    letter_to_type = {"A": "service", "B": "library", "C": "cli",
                      "D": "monorepo", "E": "lightweight"}
    for m in pattern.finditer(text):
        out[letter_to_type[m.group(1)]] = m.group(4)
    return out


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
    """The staleness matrix lives in references/checklist.md (it is refactor-mode
    detail, loaded on demand). SKILL.md must still route to it, and the matrix must
    still carry every trigger — a pointer to an empty page is worse than no pointer."""

    def test_skill_routes_to_the_matrix(self):
        data = skill_text()
        self.assertIn("Refactor Mode", data)
        refactor = data[data.index("## Refactor Mode"):]
        self.assertIn("checklist.md", refactor)
        self.assertIn("update-trigger matrix", refactor.lower())

    def test_key_triggers_present_in_checklist(self):
        data = CHECKLIST_REF.read_text()
        self.assertIn("Update Trigger Matrix", data)
        for trigger in ["Makefile target", "CI workflow", "Env variable",
                         "LICENSE", "Go/Node version"]:
            self.assertIn(trigger, data, f"trigger missing: {trigger}")

    def test_matrix_row_count(self):
        data = CHECKLIST_REF.read_text()
        start = data.index("## Update Trigger Matrix")
        section = data[start:data.index("##", start + 5)]
        rows = [l for l in section.splitlines() if l.startswith("|") and "---" not in l]
        self.assertGreaterEqual(len(rows), 10, f"only {len(rows)} matrix rows")


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

    def test_no_orphaned_reference_files(self):
        """Every file in references/ must be reachable from SKILL.md.

        Progressive disclosure only works if the always-loaded file says when to load
        each reference. A reference nothing points at is dead weight that still has to
        be maintained — and both files added during the 2026-07-28 hardening
        (badges-and-governance, language-snippets) could have landed that way."""
        skill = skill_text()
        # SKILL.md points at the golden set by pattern (`golden-<type>.md`) rather than
        # naming five files; expand it so the pattern counts as a mention.
        if "golden-<type>.md" in skill:
            skill += "\n" + "\n".join(
                f"golden-{k}.md" for k in
                ("service", "library", "cli", "monorepo", "lightweight")
            )
        orphans = [
            f.name for f in sorted((SKILL_DIR / "references").glob("*.md"))
            if f.name not in skill and f.stem not in skill
        ]
        self.assertEqual([], orphans,
                         f"references never mentioned in SKILL.md: {orphans}")

    def test_total_content_depth(self):
        """Counts every reference, not a hand-picked five: SKILL.md shrank when detail
        moved into new reference files, and a fixed five-file list would have read that
        as content loss."""
        total = len(SKILL_MD.read_text().splitlines())
        refs = sorted((SKILL_DIR / "references").glob("*.md"))
        self.assertGreaterEqual(len(refs), 8, "reference set unexpectedly small")
        for f in refs:
            total += len(f.read_text().splitlines())
        self.assertGreaterEqual(total, 1500, f"total content: {total} lines (need ≥1500)")

    def test_skill_md_stays_lean(self):
        """SKILL.md is always in context; references are loaded on demand. 400 lines is
        the working budget this skill was refactored down to (was 492)."""
        lines = len(skill_text().splitlines())
        self.assertLessEqual(lines, 400, f"SKILL.md is {lines} lines (budget 400)")


# ── 22. Templates satisfy their own required-section matrix ─────

class TestTemplateRequiredSections(unittest.TestCase):
    """SKILL.md §Structure Policy lists required sections per project type; the
    templates are what an author actually fills in. Before this test the two
    disagreed: Templates B, C, and D omitted sections the (then flat) required list
    demanded, so following the skill exactly produced a README the skill would fail.
    """

    @classmethod
    def setUpClass(cls):
        cls.lint = _load_linter()
        cls.templates = templates()

    def test_all_five_templates_extracted(self):
        self.assertEqual(
            {"service", "library", "cli", "monorepo", "lightweight"},
            set(self.templates),
            "template extraction broke — the rest of this class would vacuously pass",
        )

    def test_each_template_carries_its_required_sections(self):
        for ptype, body in self.templates.items():
            with self.subTest(template=ptype):
                missing = self.lint.missing_sections(body, ptype)
                self.assertEqual(
                    [], missing,
                    f"Template for {ptype!r} omits required section(s): {missing}",
                )

    def test_templates_do_not_carry_foreign_required_sections(self):
        """A Library template with a Configuration section teaches service habits."""
        self.assertNotIn("configuration", self.lint.REQUIRED_SECTIONS["library"])
        library = self.templates["library"].lower()
        self.assertNotIn("## configuration", library)

    def test_license_placeholder_carries_the_missing_note(self):
        """License is the documented exception to §Evidence Precedence: the section
        never simply disappears. Two of the five templates offered no fallback text,
        which is how "optional section, omit when missing" leaked back in."""
        data = TEMPLATES_REF.read_text()
        bare = data.count("{License type from LICENSE file.}")
        self.assertEqual(0, bare,
                         "a License placeholder with no missing-note fallback")
        self.assertGreaterEqual(
            data.count("Not found in repo — consider adding a LICENSE file"), 4,
            "every template that has a License section needs the fallback wording",
        )

    def test_no_verification_language_in_any_template(self):
        for ptype, body in self.templates.items():
            with self.subTest(template=ptype):
                for banned in ("Not verified", "not executed in this environment",
                               "| Verified |"):
                    self.assertNotIn(banned, body)


# ── 23. Repo-aware linter contract ──────────────────────────────

class TestLintReadmeScript(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lint = _load_linter()

    def test_script_exists_and_is_referenced(self):
        self.assertTrue(LINT_SCRIPT.exists())
        data = skill_text()
        self.assertIn("lint_readme.py", data)
        workflow = data[data.index("Generation Workflow"):]
        self.assertIn("lint_readme.py", workflow,
                      "the self-check step must be part of the workflow, not a footnote")

    def test_every_finding_code_is_documented_in_the_module(self):
        source = LINT_SCRIPT.read_text()
        codes = sorted(set(re.findall(r'Finding\("(R\d{3})"', source)))
        self.assertGreaterEqual(len(codes), 10, f"only {len(codes)} checks: {codes}")
        for code in codes:
            self.assertRegex(source, rf'{code}", (CRITICAL|STANDARD)',
                             f"{code} has no severity")

    def test_required_sections_cover_every_routed_type(self):
        for ptype in ("service", "library", "cli", "monorepo", "lightweight"):
            self.assertIn(ptype, self.lint.REQUIRED_SECTIONS)


# ── 24. Coverage doc cannot go stale ────────────────────────────

class TestCoverageDocIsCurrent(unittest.TestCase):
    """COVERAGE.md previously claimed 151 tests and listed a TestAgentsConfig class
    with an agents/openai.yaml that never existed anywhere in this repository. A
    coverage document that overstates the suite is worse than none, because it is
    read as evidence. These three checks make the numbers and the class names
    machine-verifiable.

    Counting is done by AST, not by running pytest: the suite must not depend on
    being able to re-enter its own runner.
    """

    @classmethod
    def setUpClass(cls):
        import ast
        cls.doc = COVERAGE_DOC.read_text()
        cls.per_module = {}
        cls.class_names = set()
        for name in TEST_MODULES:
            tree = ast.parse((Path(__file__).resolve().parent / name).read_text())
            count = 0
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    cls.class_names.add(node.name)
                    count += sum(
                        1 for b in node.body
                        if isinstance(b, (ast.FunctionDef, ast.AsyncFunctionDef))
                        and b.name.startswith("test_")
                    )
            cls.per_module[name] = count

    def test_total_matches_the_live_suite(self):
        total = sum(self.per_module.values())
        claimed = re.search(r"\*\*Total:\s*(\d+)\s*tests?\*\*", self.doc)
        self.assertIsNotNone(claimed, "COVERAGE.md has no '**Total: N tests**' line")
        self.assertEqual(
            total, int(claimed.group(1)),
            f"COVERAGE.md claims {claimed.group(1)}; the suite defines {total} "
            f"({self.per_module})",
        )

    def test_per_module_counts_match(self):
        headline = {
            "test_skill_contract.py": r"(\d+) contract",
            "test_golden_scenarios.py": r"(\d+) golden-scenario",
            "test_discovery_script.py": r"(\d+) discovery-behavioral",
            "test_forward_eval.py": r"(\d+) forward-eval",
        }
        for module, pattern in headline.items():
            with self.subTest(module=module):
                m = re.search(pattern, self.doc)
                self.assertIsNotNone(m, f"no count for {module} in COVERAGE.md")
                self.assertEqual(self.per_module[module], int(m.group(1)))

    def test_no_phantom_test_classes(self):
        """Every class named in a COVERAGE.md table row must exist in the suite.

        Table rows only, deliberately: the stale `TestAgentsConfig` entry lived in a
        row, and the prose above must stay free to explain that such a class was
        removed without the explanation itself tripping the check."""
        rows = [l for l in self.doc.splitlines() if l.lstrip().startswith("|")]
        named = set(re.findall(r"\b(Test[A-Z]\w+|[A-Z]\w*Test)\b", "\n".join(rows)))
        named -= {"TestCase"}
        phantom = sorted(named - self.class_names)
        self.assertEqual([], phantom,
                         f"COVERAGE.md names classes that do not exist: {phantom}")


# ── 25. Golden section orders satisfy the same matrix ───────────

class TestGoldenSectionOrders(unittest.TestCase):
    """The matrix is asserted in four places: SKILL.md prose, lint_readme's table,
    the templates, and the "Golden section order" lists in golden-examples.md. The
    fourth was the last one still disagreeing — three of its five lists omitted
    Documentation Maintenance while the skill required it."""

    @classmethod
    def setUpClass(cls):
        cls.lint = _load_linter()
        text = GOLDEN_REF.read_text()
        cls.orders = {}
        blocks = re.split(r"^## Example \d+: ", text, flags=re.MULTILINE)[1:]
        name_to_type = {"go service": "service", "go library": "library",
                        "cli tool": "cli", "monorepo": "monorepo",
                        "lightweight internal tool": "lightweight"}
        for block in blocks:
            title = block.splitlines()[0].strip().lower()
            ptype = name_to_type.get(title)
            m = re.search(r"### Golden section order\n\n((?:\d+\. .+\n)+)", block)
            if ptype and m:
                cls.orders[ptype] = [
                    re.sub(r"^\d+\.\s*", "", line).strip()
                    for line in m.group(1).strip().splitlines()
                ]

    def test_all_five_orders_parsed(self):
        self.assertEqual(
            {"service", "library", "cli", "monorepo", "lightweight"},
            set(self.orders),
            "section-order extraction broke — the next test would vacuously pass",
        )

    def test_each_order_satisfies_its_matrix_row(self):
        for ptype, items in self.orders.items():
            with self.subTest(example=ptype):
                synthetic = "\n".join(f"## {i}" for i in items)
                missing = self.lint.missing_sections(synthetic, ptype)
                self.assertEqual(
                    [], missing,
                    f"golden section order for {ptype!r} omits: {missing}",
                )


if __name__ == "__main__":
    unittest.main()
