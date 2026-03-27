"""Contract tests for writing-plans skill.

Validates SKILL.md structure, reference content quality, reviewer prompt
constraints, and cross-document terminology consistency — all without
invoking any LLM. Pure text/regex checks.
"""

import os
import re

import pytest

SKILL_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SKILL_MD = os.path.join(SKILL_DIR, "SKILL.md")
REFS_DIR = os.path.join(SKILL_DIR, "references")
TEMPLATES_DIR = os.path.join(REFS_DIR, "plan-templates")
REVIEWER_PROMPT = os.path.join(SKILL_DIR, "plan-document-reviewer-prompt.md")


def _read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture(scope="module")
def skill_content():
    return _read(SKILL_MD)


@pytest.fixture(scope="module")
def skill_lines(skill_content):
    return skill_content.splitlines()


@pytest.fixture(scope="module")
def frontmatter(skill_content):
    match = re.match(r"^---\n(.*?)\n---", skill_content, re.DOTALL)
    return match.group(1) if match else ""


# ─── Frontmatter Tests ───


class TestFrontmatter:
    def test_has_name_field(self, frontmatter):
        assert re.search(r"^name:\s*\S", frontmatter, re.MULTILINE), (
            "frontmatter must have 'name' field"
        )

    def test_has_description_field(self, frontmatter):
        assert re.search(r"^description:", frontmatter, re.MULTILINE), (
            "frontmatter must have 'description' field"
        )

    def test_description_under_1024_chars(self, frontmatter):
        desc_match = re.search(
            r"^description:\s*>?\s*\n?(.*?)(?=\n\w|\n---|\Z)",
            frontmatter,
            re.MULTILINE | re.DOTALL,
        )
        if desc_match:
            desc = desc_match.group(1).strip()
            assert len(desc) <= 1024, (
                f"description is {len(desc)} chars, must be ≤1024"
            )

    def test_description_has_trigger_keywords(self, frontmatter):
        trigger_words = ["plan", "spec", "requirement", "feature", "decomposition", "multi-step"]
        desc_lower = frontmatter.lower()
        found = [w for w in trigger_words if w in desc_lower]
        assert len(found) >= 2, (
            f"description should contain trigger keywords, found: {found}"
        )

    def test_description_has_exclusion_keywords(self, frontmatter):
        exclusion_words = ["not for", "not", "single-file", "trivial"]
        desc_lower = frontmatter.lower()
        found = [w for w in exclusion_words if w in desc_lower]
        assert len(found) >= 1, (
            "description should contain exclusion keywords (e.g., 'NOT for')"
        )


# ─── Required Sections Tests ───


class TestRequiredSections:
    REQUIRED_HEADINGS = [
        ("Requirements Clarity", r"#+\s.*[Rr]equirements\s*[Cc]larity"),
        ("Applicability Gate", r"#+\s.*[Aa]pplicability\s*[Gg]ate"),
        ("Execution Modes", r"#+\s.*[Ee]xecution\s*[Mm]odes"),
        ("Repo Discovery", r"#+\s.*[Rr]epo\s*[Dd]iscovery"),
        ("Scope & Risk", r"#+\s.*[Ss]cope.*[Rr]isk"),
        ("Plan Content Rules", r"#+\s.*[Pp]lan\s*[Cc]ontent\s*[Rr]ules"),
        ("Anti-Examples", r"#+\s.*[Aa]nti.?[Ee]xamples"),
        ("Output Contract", r"#+\s.*[Oo]utput\s*[Cc]ontract|[Pp]lan\s*[Dd]ocument\s*[Ss]tructure"),
        ("Scorecard", r"#+\s.*[Ss]corecard"),
        ("Degraded Mode", r"#+\s.*[Dd]egraded\s*[Mm]ode"),
        ("Plan Update Protocol", r"#+\s.*[Pp]lan\s*[Uu]pdate\s*[Pp]rotocol"),
    ]

    @pytest.mark.parametrize("name,pattern", REQUIRED_HEADINGS, ids=[h[0] for h in REQUIRED_HEADINGS])
    def test_has_required_section(self, skill_content, name, pattern):
        assert re.search(pattern, skill_content), (
            f"SKILL.md must contain a '{name}' section"
        )


# ─── Scorecard Structure Tests ───


class TestScorecard:
    def test_has_critical_tier(self, skill_content):
        assert re.search(r"[Cc]ritical.*(?:ALL|all)\s*must\s*pass", skill_content), (
            "scorecard must have Critical tier with 'ALL must pass' rule"
        )

    def test_has_standard_tier(self, skill_content):
        assert re.search(r"[Ss]tandard.*\d+/\d+\s*must\s*pass", skill_content), (
            "scorecard must have Standard tier with pass threshold"
        )

    def test_has_hygiene_tier(self, skill_content):
        assert re.search(r"[Hh]ygiene.*\d+/\d+\s*must\s*pass", skill_content), (
            "scorecard must have Hygiene tier with pass threshold"
        )

    def test_critical_items_exist(self, skill_content):
        critical_items = re.findall(r"\|\s*C\d\s*\|", skill_content)
        assert len(critical_items) >= 5, (
            f"scorecard must have ≥5 Critical items, found {len(critical_items)}"
        )

    def test_standard_items_exist(self, skill_content):
        standard_items = re.findall(r"\|\s*S\d\s*\|", skill_content)
        assert len(standard_items) >= 6, (
            f"scorecard must have ≥6 Standard items, found {len(standard_items)}"
        )

    def test_hygiene_items_exist(self, skill_content):
        hygiene_items = re.findall(r"\|\s*H\d\s*\|", skill_content)
        assert len(hygiene_items) >= 4, (
            f"scorecard must have ≥4 Hygiene items, found {len(hygiene_items)}"
        )


# ─── Execution Modes Tests ───


class TestExecutionModes:
    MODES = ["Lite", "Standard", "Deep"]

    @pytest.mark.parametrize("mode", MODES)
    def test_mode_defined(self, skill_content, mode):
        assert re.search(rf"###?\s*{mode}", skill_content), (
            f"SKILL.md must define '{mode}' execution mode"
        )


# ─── Progressive Disclosure Tests ───


class TestProgressiveDisclosure:
    def test_skill_md_under_500_lines(self, skill_lines):
        assert len(skill_lines) <= 500, (
            f"SKILL.md is {len(skill_lines)} lines, must be ≤500 for L2 progressive disclosure"
        )

    def test_references_have_loading_conditions(self, skill_content):
        ref_mentions = re.findall(r"references/\S+\.md", skill_content)
        assert len(ref_mentions) >= 3, (
            f"SKILL.md should reference ≥3 files in references/, found {len(ref_mentions)}"
        )

    def test_has_reference_loading_guide(self, skill_content):
        assert re.search(r"[Rr]eference\s*[Ll]oading", skill_content), (
            "SKILL.md should have a Reference Loading Guide/table"
        )


# ─── Code Block Labels Tests ───


class TestCodeBlockLabels:
    REQUIRED_LABELS = ["interface", "test-assertion", "command", "speculative"]

    @pytest.mark.parametrize("label", REQUIRED_LABELS)
    def test_label_defined(self, skill_content, label):
        assert re.search(rf"\[{label}\]", skill_content), (
            f"SKILL.md must define code block label '[{label}]'"
        )


# ─── Reference Files Existence Tests ───


class TestReferenceFiles:
    REQUIRED_REFS = [
        "applicability-gate.md",
        "repo-discovery-protocol.md",
        "anti-examples.md",
        "reviewer-checklist.md",
        "plan-update-protocol.md",
        "golden-scenarios.md",
        "requirements-clarity-gate.md",
    ]

    @pytest.mark.parametrize("filename", REQUIRED_REFS)
    def test_reference_file_exists(self, filename):
        path = os.path.join(REFS_DIR, filename)
        assert os.path.isfile(path), (
            f"references/{filename} must exist"
        )

    REQUIRED_TEMPLATES = [
        "bugfix.md",
        "feature.md",
        "refactor.md",
        "migration.md",
        "docs-only.md",
        "api-change.md",
    ]

    @pytest.mark.parametrize("filename", REQUIRED_TEMPLATES)
    def test_plan_template_exists(self, filename):
        path = os.path.join(TEMPLATES_DIR, filename)
        assert os.path.isfile(path), (
            f"references/plan-templates/{filename} must exist"
        )

    def test_reviewer_prompt_exists(self):
        assert os.path.isfile(REVIEWER_PROMPT), (
            "plan-document-reviewer-prompt.md must exist"
        )


# ═══════════════════════════════════════════════════════════════
# NEW: Reference Content Quality Tests
# ═══════════════════════════════════════════════════════════════


class TestAntiExamplesContent:
    """Verify anti-examples.md has substantive BAD/GOOD pairs."""

    @pytest.fixture(scope="class")
    def content(self):
        return _read(os.path.join(REFS_DIR, "anti-examples.md"))

    def test_has_at_least_10_numbered_examples(self, content):
        numbered = re.findall(r"^## \d+\.", content, re.MULTILINE)
        assert len(numbered) >= 10, (
            f"anti-examples.md must have ≥10 numbered examples, found {len(numbered)}"
        )

    def test_every_example_has_bad_and_good(self, content):
        bads = len(re.findall(r"BAD:", content))
        goods = len(re.findall(r"GOOD:", content))
        assert bads >= 10, f"anti-examples.md must have ≥10 BAD patterns, found {bads}"
        assert goods >= 10, f"anti-examples.md must have ≥10 GOOD patterns, found {goods}"

    def test_every_example_has_why(self, content):
        whys = len(re.findall(r"^Why:", content, re.MULTILINE))
        assert whys >= 10, (
            f"anti-examples.md must explain why for each example, found {whys} 'Why:' lines"
        )


class TestReviewerChecklistContent:
    """Verify reviewer-checklist.md has sufficient blocking and non-blocking items."""

    @pytest.fixture(scope="class")
    def content(self):
        return _read(os.path.join(REFS_DIR, "reviewer-checklist.md"))

    def test_has_at_least_6_blocking_items(self, content):
        blocking = re.findall(r"\|\s*B\d\s*\|", content)
        assert len(blocking) >= 6, (
            f"reviewer-checklist.md must have ≥6 blocking items, found {len(blocking)}"
        )

    def test_has_at_least_5_nonblocking_items(self, content):
        nonblocking = re.findall(r"\|\s*N\d\s*\|", content)
        assert len(nonblocking) >= 5, (
            f"reviewer-checklist.md must have ≥5 non-blocking items, found {len(nonblocking)}"
        )

    def test_has_output_format(self, content):
        assert re.search(r"[Oo]utput\s*[Ff]ormat", content), (
            "reviewer-checklist.md must define an output format"
        )

    def test_has_scorecard_in_output(self, content):
        assert re.search(r"Scorecard", content), (
            "reviewer-checklist.md output must include scorecard"
        )


class TestGoldenScenariosContent:
    """Verify golden-scenarios.md has sufficient scenario pairs."""

    @pytest.fixture(scope="class")
    def content(self):
        return _read(os.path.join(REFS_DIR, "golden-scenarios.md"))

    def test_has_at_least_6_scenarios(self, content):
        scenarios = re.findall(r"^## \d+\.", content, re.MULTILINE)
        assert len(scenarios) >= 6, (
            f"golden-scenarios.md must have ≥6 scenarios, found {len(scenarios)}"
        )

    def test_has_good_and_bad_per_scenario(self, content):
        goods = len(re.findall(r"### GOOD", content))
        bads = len(re.findall(r"### BAD", content))
        assert goods >= 6, f"golden-scenarios.md must have ≥6 GOOD examples, found {goods}"
        assert bads >= 6, f"golden-scenarios.md must have ≥6 BAD examples, found {bads}"


class TestApplicabilityGateContent:
    """Verify applicability-gate.md has decision tree and complexity signals."""

    @pytest.fixture(scope="class")
    def content(self):
        return _read(os.path.join(REFS_DIR, "applicability-gate.md"))

    def test_has_decision_tree(self, content):
        assert re.search(r"[Dd]ecision\s*[Tt]ree", content), (
            "applicability-gate.md must have a decision tree"
        )

    def test_has_complexity_signals(self, content):
        assert re.search(r"[Cc]omplexity\s*[Ss]ignal", content), (
            "applicability-gate.md must have complexity signals section"
        )

    def test_covers_skip_decision(self, content):
        assert re.search(r"SKIP", content), (
            "applicability-gate.md must cover SKIP decision"
        )

    def test_has_upgrade_protocol(self, content):
        assert re.search(r"[Uu]pgrade", content), (
            "applicability-gate.md must have upgrade protocol (Lite→Standard→Deep)"
        )


class TestRepoDiscoveryContent:
    """Verify repo-discovery-protocol.md has all 5 steps and path rules."""

    @pytest.fixture(scope="class")
    def content(self):
        return _read(os.path.join(REFS_DIR, "repo-discovery-protocol.md"))

    def test_has_5_discovery_steps(self, content):
        steps = re.findall(r"## Step \d", content)
        assert len(steps) >= 5, (
            f"repo-discovery-protocol.md must have ≥5 discovery steps, found {len(steps)}"
        )

    def test_has_path_verification_rules(self, content):
        assert re.search(r"[Pp]ath\s*[Vv]erification", content), (
            "repo-discovery-protocol.md must have path verification rules"
        )

    def test_defines_all_four_path_labels(self, content):
        for label in ["Existing", "New", "Inferred", "Speculative"]:
            assert re.search(rf"\[{label}\]", content), (
                f"repo-discovery-protocol.md must define [{label}] label"
            )

    def test_has_hard_rule(self, content):
        assert re.search(r"[Hh]ard\s*rule|NEVER\s*present", content), (
            "repo-discovery-protocol.md must have hard rule about Speculative vs Existing"
        )


class TestRequirementsClarityGateContent:
    """Verify requirements-clarity-gate.md has dimensions, depth table, examples, and anti-patterns."""

    @pytest.fixture(scope="class")
    def content(self):
        return _read(os.path.join(REFS_DIR, "requirements-clarity-gate.md"))

    def test_has_clarity_dimensions(self, content):
        for dim in ["D1", "D2", "D3", "D4", "D5"]:
            assert re.search(dim, content), (
                f"requirements-clarity-gate.md must define clarity dimension {dim}"
            )

    def test_has_mode_appropriate_depth(self, content):
        assert re.search(r"[Mm]ode.*[Aa]ppropriate\s*[Dd]epth", content), (
            "requirements-clarity-gate.md must have mode-appropriate depth section"
        )

    def test_has_clarification_examples(self, content):
        examples = re.findall(r"### Example \d", content)
        assert len(examples) >= 4, (
            f"requirements-clarity-gate.md must have ≥4 clarification examples, found {len(examples)}"
        )

    def test_has_anti_patterns(self, content):
        assert re.search(r"[Aa]nti.?[Pp]atterns", content), (
            "requirements-clarity-gate.md must have anti-patterns section"
        )


class TestPlanUpdateProtocolContent:
    """Verify plan-update-protocol.md has deviation classification and escalation."""

    @pytest.fixture(scope="class")
    def content(self):
        return _read(os.path.join(REFS_DIR, "plan-update-protocol.md"))

    def test_has_deviation_classification(self, content):
        for level in ["Trivial", "Significant", "Breaking"]:
            assert re.search(level, content), (
                f"plan-update-protocol.md must define '{level}' deviation level"
            )

    def test_has_escalation_thresholds(self, content):
        assert re.search(r"[Ee]scalation", content), (
            "plan-update-protocol.md must have escalation thresholds"
        )

    def test_has_recording_format(self, content):
        assert re.search(r"\[Deviation\]|[Rr]ecording\s*[Ff]ormat", content), (
            "plan-update-protocol.md must define deviation recording format"
        )


class TestPlanTemplateContent:
    """Verify each plan template has trigger signals, default mode, and sections."""

    TEMPLATES = ["bugfix.md", "feature.md", "refactor.md", "migration.md", "docs-only.md", "api-change.md"]

    @pytest.mark.parametrize("filename", TEMPLATES)
    def test_template_has_trigger_signals(self, filename):
        content = _read(os.path.join(TEMPLATES_DIR, filename))
        assert re.search(r"[Tt]rigger", content), (
            f"plan-templates/{filename} must have trigger signals"
        )

    @pytest.mark.parametrize("filename", TEMPLATES)
    def test_template_has_default_mode(self, filename):
        content = _read(os.path.join(TEMPLATES_DIR, filename))
        assert re.search(r"[Dd]efault\s*mode|Mode:", content), (
            f"plan-templates/{filename} must declare default mode"
        )

    @pytest.mark.parametrize("filename", TEMPLATES)
    def test_template_has_required_sections(self, filename):
        content = _read(os.path.join(TEMPLATES_DIR, filename))
        assert re.search(r"[Rr]equired\s*[Ss]ections?", content), (
            f"plan-templates/{filename} must list required sections"
        )

    @pytest.mark.parametrize("filename", TEMPLATES)
    def test_template_has_skeleton(self, filename):
        content = _read(os.path.join(TEMPLATES_DIR, filename))
        assert re.search(r"[Ss]keleton|[Ee]xample|```", content), (
            f"plan-templates/{filename} must include a skeleton example"
        )


# ═══════════════════════════════════════════════════════════════
# NEW: Reviewer Prompt Contract Tests
# ═══════════════════════════════════════════════════════════════


class TestReviewerPromptContract:
    """Verify plan-document-reviewer-prompt.md enforces checklist-based review."""

    @pytest.fixture(scope="class")
    def content(self):
        return _read(REVIEWER_PROMPT)

    def test_has_all_blocking_items(self, content):
        for b in ["B1", "B2", "B3", "B4", "B5", "B6"]:
            assert re.search(rf"\b{b}\b", content), (
                f"reviewer prompt must reference blocking item {b}"
            )

    def test_has_all_nonblocking_items(self, content):
        for n in ["N1", "N2", "N3", "N4", "N5", "N6", "N7"]:
            assert re.search(rf"\b{n}\b", content), (
                f"reviewer prompt must reference non-blocking item {n}"
            )

    def test_has_calibration_section(self, content):
        assert re.search(r"[Cc]alibration", content), (
            "reviewer prompt must have calibration section to prevent false positives"
        )

    def test_has_output_format(self, content):
        assert re.search(r"[Oo]utput\s*[Ff]ormat", content), (
            "reviewer prompt must define output format"
        )

    def test_has_scorecard_output(self, content):
        assert re.search(r"Scorecard.*C:.*S:.*H:", content), (
            "reviewer prompt output must include scorecard tally (C: _/4 | S: _/6 | H: _/4)"
        )

    def test_specifies_pass_fail_status(self, content):
        assert re.search(r"Approved.*Issues Found|PASS.*FAIL", content), (
            "reviewer prompt must specify Approved/Issues Found status output"
        )

    def test_specifies_max_iterations(self, content):
        assert re.search(r"[Mm]ax\s*\d+\s*iteration|3\s*iteration", content), (
            "reviewer prompt must specify max review iterations"
        )


# ═══════════════════════════════════════════════════════════════
# NEW: Cross-Document Terminology Consistency Tests
# ═══════════════════════════════════════════════════════════════


class TestTerminologyConsistency:
    """Verify path label terminology is consistent across all documents."""

    ALL_FOUR_LABELS = ["Existing", "New", "Inferred", "Speculative"]

    DOCS_THAT_MUST_LIST_ALL_LABELS = [
        ("SKILL.md Gate 3 Repo Discovery", SKILL_MD, r"Gate 3.*?(?=## )", re.DOTALL),
        ("SKILL.md Scorecard C2", SKILL_MD, r"C2\s*\|[^|]+\|", 0),
        ("repo-discovery-protocol.md Path Verification",
         os.path.join(REFS_DIR, "repo-discovery-protocol.md"),
         r"Path Verification.*", re.DOTALL),
    ]

    @pytest.mark.parametrize(
        "name,path,pattern,flags",
        DOCS_THAT_MUST_LIST_ALL_LABELS,
        ids=[d[0] for d in DOCS_THAT_MUST_LIST_ALL_LABELS],
    )
    def test_section_lists_all_four_labels(self, name, path, pattern, flags):
        content = _read(path)
        section_match = re.search(pattern, content, flags)
        assert section_match, f"Could not find section '{name}' in {os.path.basename(path)}"
        section = section_match.group(0)
        for label in self.ALL_FOUR_LABELS:
            assert re.search(rf"\[{label}\]", section), (
                f"'{name}' must list [{label}] — found in section: {section[:200]}..."
            )

    def test_reviewer_checklist_b2_lists_all_labels(self):
        content = _read(os.path.join(REFS_DIR, "reviewer-checklist.md"))
        b2_match = re.search(r"B2\s*\|[^|]+\|", content)
        assert b2_match, "reviewer-checklist.md must have B2 item"
        b2 = b2_match.group(0)
        for label in self.ALL_FOUR_LABELS:
            assert re.search(rf"\[{label}\]", b2), (
                f"reviewer-checklist.md B2 must list [{label}]"
            )

    def test_reviewer_prompt_b2_lists_all_labels(self):
        content = _read(REVIEWER_PROMPT)
        b2_match = re.search(r"B2\s*\|[^|]+\|", content)
        assert b2_match, "reviewer prompt must have B2 item"
        b2 = b2_match.group(0)
        for label in self.ALL_FOUR_LABELS:
            assert re.search(rf"\[{label}\]", b2), (
                f"reviewer prompt B2 must list [{label}]"
            )

    def test_skill_md_tasks_section_lists_all_labels(self):
        content = _read(SKILL_MD)
        tasks_match = re.search(
            r"### Tasks \(mandatory\).*?(?=###|\Z)", content, re.DOTALL
        )
        assert tasks_match, "SKILL.md must have '### Tasks (mandatory)' section"
        tasks = tasks_match.group(0)
        for label in self.ALL_FOUR_LABELS:
            assert re.search(rf"\[{label}\]", tasks), (
                f"SKILL.md Tasks section must list [{label}]"
            )


# ═══════════════════════════════════════════════════════════════
# NEW: Lightweight Plan Linter (validates plan text against rules)
# ═══════════════════════════════════════════════════════════════


class TestPlanLinter:
    """Reusable plan text validation — can be imported by golden tests too."""

    @staticmethod
    def lint_plan(plan_text, mode):
        """Return list of (rule_id, message) violations found in plan_text."""
        violations = []

        # B1: Mode declared
        if mode != "SKIP" and not re.search(r"Mode:", plan_text):
            violations.append(("B1", "Mode not declared in plan"))

        # B2: File paths have labels
        file_refs = re.findall(r"`[\w/.-]+\.\w+`", plan_text)
        if file_refs and not re.search(r"\[(Existing|New|Inferred|Speculative)", plan_text):
            violations.append(("B2", "File paths present but no labels found"))

        # B3: No unfilled placeholders
        for placeholder in ["TODO", "TBD", "FIXME"]:
            if re.search(rf"\b{placeholder}\b", plan_text):
                violations.append(("B3", f"Unfilled placeholder: {placeholder}"))

        # B4: Verification commands
        if mode != "SKIP":
            has_verification = re.search(
                r"Run:|go test|pytest|npm test|make test|\[command\]", plan_text
            )
            if not has_verification:
                violations.append(("B4", "No verification command found"))

        # B5: No complete implementation code in Standard/Deep
        if mode in ("Standard", "Deep"):
            # Go functions >100 chars
            if re.search(r"func \w+\([^)]*\)\s*\{[^}]{100,}\}", plan_text, re.DOTALL):
                violations.append(("B5", "Complete Go function implementation found"))
            # Python functions >4 lines
            if re.search(r"def \w+\([^)]*\):\s*\n(?:\s{4,}.*\n){4,}", plan_text):
                violations.append(("B5", "Complete Python function implementation found"))

        return violations

    def test_linter_catches_missing_mode(self):
        violations = self.lint_plan("Some plan without mode", "Standard")
        assert any(v[0] == "B1" for v in violations)

    def test_linter_catches_missing_labels(self):
        violations = self.lint_plan(
            "Modify `src/foo.go` — no labels here\nRun: go test",
            "Standard",
        )
        assert any(v[0] == "B2" for v in violations)

    def test_linter_catches_todo(self):
        violations = self.lint_plan("Mode: Standard\nTODO: fill in later", "Standard")
        assert any(v[0] == "B3" for v in violations)

    def test_linter_catches_missing_verification(self):
        violations = self.lint_plan("Mode: Standard\n[Existing] `foo.go`", "Standard")
        assert any(v[0] == "B4" for v in violations)

    def test_linter_passes_clean_plan(self):
        clean = (
            "Mode: Standard\n"
            "Modify `foo.go` [Existing]\n"
            "Run: go test ./...\n"
            "[test-assertion] assert result == expected\n"
        )
        violations = self.lint_plan(clean, "Standard")
        assert len(violations) == 0, f"Clean plan should have no violations: {violations}"

    def test_linter_skip_mode_relaxed(self):
        skip = "SKIP — proceeding directly"
        violations = self.lint_plan(skip, "SKIP")
        assert len(violations) == 0, f"SKIP mode should have no violations: {violations}"