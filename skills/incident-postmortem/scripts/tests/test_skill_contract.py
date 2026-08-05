"""Contract tests for incident-postmortem SKILL.md."""

import pathlib
import re

import pytest

SKILL_DIR = pathlib.Path(__file__).resolve().parents[2]
SKILL_MD = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
SKILL_LOWER = SKILL_MD.lower()
REFS_DIR = SKILL_DIR / "references"


def _ref(name: str) -> str:
    return (REFS_DIR / name).read_text(encoding="utf-8")


def _flat(text: str) -> str:
    """Collapse whitespace for prose assertions.

    Markdown wraps at ~88 chars, so a literal multi-word assertion breaks whenever a
    sentence re-wraps — which has forced three unrelated doc edits already. Assert on
    the flattened text and let the prose wrap where it likes.
    """
    return re.sub(r"\s+", " ", text).lower()


SKILL_FLAT = _flat(SKILL_MD)


# ──────────────────────────────────────────────────────────────────────
class TestFrontmatter:

    @pytest.fixture(autouse=True)
    def _front(self):
        m = re.search(r"^---\n(.*?)\n---", SKILL_MD, re.DOTALL)
        assert m, "YAML frontmatter block not found"
        self.front = m.group(1)

    def test_name(self):
        # The name field shipped as "incident-postmortem-postmortem" (a
        # creation-time replace accident) and this very test asserted the
        # corruption for two months. The registry identity must equal the
        # directory name — assert that invariant, not a literal.
        dirname = pathlib.Path(__file__).resolve().parents[2].name
        assert f"name: {dirname}" in self.front
        assert "postmortem-postmortem" not in self.front

    def test_description_triggers(self):
        desc = self.front.lower()
        for kw in ("post-mortem", "timeline", "root cause", "blameless",
                    "action item", "severity"):
            assert kw in desc, f"missing trigger: {kw}"

    def test_allowed_tools(self):
        assert "allowed-tools:" in self.front


# ──────────────────────────────────────────────────────────────────────
class TestMandatoryGates:

    def test_section_exists(self):
        assert "## 2 Mandatory Gates" in SKILL_MD

    def test_gate_1_context(self):
        assert "Gate 1: Incident Context Collection" in SKILL_MD
        assert "Incident identifier" in SKILL_MD

    def test_gate_2_blameless(self):
        assert "Gate 2: Blameless Framing" in SKILL_MD
        assert "STOP and reframe" in SKILL_MD

    def test_gate_3_scope(self):
        assert "Gate 3: Scope Classification" in SKILL_MD
        for mode in ("Draft", "Review", "Extract"):
            assert mode in SKILL_MD

    def test_gate_4_output(self):
        assert "Gate 4: Output Completeness" in SKILL_MD

    def test_stop_semantics(self):
        assert SKILL_MD.count("STOP") >= 3


# ──────────────────────────────────────────────────────────────────────
class TestDepthSelection:

    def test_three_depths(self):
        for d in ("### Quick", "### Standard", "### Deep"):
            assert d in SKILL_MD

    def test_standard_default(self):
        assert "Standard (default)" in SKILL_MD

    def test_force_standard(self):
        assert "Force Standard if" in SKILL_MD

    def test_force_deep(self):
        assert "Force Deep if" in SKILL_MD

    def test_references_by_depth(self):
        for r in ("postmortem-template.md", "rca-techniques.md",
                   "severity-framework.md"):
            assert r in SKILL_MD


# ──────────────────────────────────────────────────────────────────────
class TestDegradationModes:

    def test_five_modes(self):
        for m in ("Full", "Partial", "Sketch", "Review", "Planning"):
            assert m in SKILL_MD

    def test_can_cannot(self):
        assert "Can Deliver" in SKILL_MD
        assert "Cannot Claim" in SKILL_MD

    def test_never_fabricate_timeline(self):
        assert "Never fabricate timeline entries" in SKILL_MD

    def test_never_invent_root_cause(self):
        assert "Never invent root causes without evidence" in SKILL_MD

    def test_degraded_marker(self):
        assert "# DEGRADED:" in SKILL_MD


# ──────────────────────────────────────────────────────────────────────
class TestChecklist:

    def test_five_subsections(self):
        for sub in ("5.1 Timeline Construction", "5.2 Root Cause Analysis",
                     "5.3 Impact Assessment", "5.4 Action Items",
                     "5.5 Organizational Learning"):
            assert sub in SKILL_MD

    def test_timeline_items(self):
        assert "Timestamps are UTC and sequential" in SKILL_MD
        assert "Every entry has a source" in SKILL_MD

    def test_rca_items(self):
        # 5-Why is the default, not a universal mandate: the reference file's own
        # "Single Cause Fallacy" anti-pattern contradicted a blanket 5-Why rule.
        assert "Select the technique by causal shape" in SKILL_MD
        assert "Root cause must be systemic, not individual" in SKILL_MD

    def test_rca_technique_is_chosen_not_fixed(self):
        for technique in ("5-Why", "fishbone", "fault tree"):
            assert technique.lower() in SKILL_LOWER, f"missing technique: {technique}"

    def test_rca_allows_multiple_necessary_conditions(self):
        assert "jointly-necessary" in SKILL_LOWER
        assert "single sentence" in SKILL_LOWER

    def test_impact_items(self):
        assert "Quantify impact with metrics" in SKILL_MD

    def test_action_items(self):
        assert "Every action item has an owner and deadline" in SKILL_MD
        assert "Categorize actions: prevent, detect, mitigate" in SKILL_MD

    def test_learning_items(self):
        assert "Document what went well" in SKILL_MD
        assert "Link to previous related incidents" in SKILL_MD

    def test_total_count(self):
        numbered = re.findall(r"^\d+\.\s+\*\*", SKILL_MD, re.MULTILINE)
        assert len(numbered) >= 18


# ──────────────────────────────────────────────────────────────────────
class TestSeverityClassification:

    def test_four_levels(self):
        for level in ("### SEV-1 Critical", "### SEV-2 Major",
                       "### SEV-3 Minor", "### SEV-4 Informational"):
            assert level in SKILL_MD

    def test_sev1_criteria(self):
        assert "Complete service outage" in SKILL_MD or "data loss" in SKILL_LOWER

    def test_sev1_requires_deep(self):
        assert "Deep post-mortem" in SKILL_MD


# ──────────────────────────────────────────────────────────────────────
class TestAntiExamples:

    def test_six_exist(self):
        for i in range(1, 7):
            assert f"AE-{i}" in SKILL_MD

    def test_ae1_blame(self):
        assert "Blame-focused post-mortem" in SKILL_MD

    def test_ae2_timeline(self):
        assert "Timeline without sources" in SKILL_MD

    def test_ae3_vague_actions(self):
        assert "as an action item" in SKILL_LOWER

    def test_ae4_shallow_rca(self):
        assert "Shallow 5-Why" in SKILL_MD

    def test_ae5_what_went_well(self):
        assert 'Missing "what went well"' in SKILL_MD

    def test_ae6_no_tracking(self):
        assert "No follow-up tracking" in SKILL_MD

    def test_wrong_right_pairs(self):
        assert SKILL_MD.count("# WRONG") >= 6
        assert SKILL_MD.count("# RIGHT") >= 6


# ──────────────────────────────────────────────────────────────────────
class TestScorecard:

    def test_section_exists(self):
        assert "## 8 Post-mortem Scorecard" in SKILL_MD

    def test_critical_3(self):
        assert "Timeline present with UTC timestamps" in SKILL_MD
        assert "Root cause identified" in SKILL_MD
        assert "Action items have owners and deadlines" in SKILL_MD

    def test_standard_5(self):
        for item in ("Impact quantified with metrics",
                      "RCA depth >= 3, technique named",
                      "Contributing factors distinguished",
                      "Blameless language throughout"):
            assert item in SKILL_MD

    def test_scorecard_does_not_mandate_5why(self):
        """§5.2 picks the technique by causal shape; the scorecard must score them
        equally, or a correct fault-tree RCA loses a point for not being a 5-Why."""
        assert "5-Why analysis depth >= 3" not in SKILL_MD
        scorecard = SKILL_MD.split("## 8 Post-mortem Scorecard")[1].split("## 9 ")[0]
        assert "technique" in scorecard.lower()

    def test_hygiene_4(self):
        for item in ("What went well", "Action items categorized",
                      "Related incidents linked",
                      "Follow-up tracking mechanism defined"):
            assert item in SKILL_MD

    def test_verdict(self):
        assert "3/3" in SKILL_MD
        assert "4/5" in SKILL_MD
        assert "3/4" in SKILL_MD
        assert "PASS" in SKILL_MD


# ──────────────────────────────────────────────────────────────────────
class TestOutputContract:

    def test_nine_sections(self):
        for i in range(1, 10):
            assert f"9.{i}" in SKILL_MD

    def test_incident_summary(self):
        assert "Incident Summary" in SKILL_MD

    def test_mode_depth(self):
        assert "Draft | Review | Extract" in SKILL_MD

    def test_timeline(self):
        assert "DETECTION, RESPONSE, RECOVERY" in SKILL_MD

    def test_rca(self):
        assert "Root Cause Analysis" in SKILL_MD

    def test_impact(self):
        assert "Impact Assessment" in SKILL_MD

    def test_what_went_well(self):
        assert "What Went Well" in SKILL_MD

    def test_action_items(self):
        assert "prevent/detect/mitigate" in SKILL_LOWER

    def test_lessons(self):
        assert "Lessons Learned" in SKILL_MD

    def test_uncovered_risks(self):
        assert "Uncovered Risks" in SKILL_MD
        assert "never empty" in SKILL_LOWER

    def test_scorecard_appended(self):
        assert "Scorecard appended" in SKILL_MD


# ──────────────────────────────────────────────────────────────────────
class TestReferenceFiles:

    def test_template_exists(self):
        assert (REFS_DIR / "postmortem-template.md").exists()

    def test_rca_exists(self):
        assert (REFS_DIR / "rca-techniques.md").exists()

    def test_severity_exists(self):
        assert (REFS_DIR / "severity-framework.md").exists()

    def test_skill_references_all(self):
        for n in ("postmortem-template.md", "rca-techniques.md",
                   "severity-framework.md"):
            assert n in SKILL_MD

    def test_template_has_sections(self):
        t = _ref("postmortem-template.md").lower()
        for kw in ("timeline", "root cause", "action items"):
            assert kw in t

    def test_rca_has_5why(self):
        assert "5-why" in _ref("rca-techniques.md").lower()

    def test_rca_has_fishbone(self):
        assert "fishbone" in _ref("rca-techniques.md").lower()

    def test_severity_has_levels(self):
        s = _ref("severity-framework.md")
        for lev in ("SEV-1", "SEV-2", "SEV-3", "SEV-4"):
            assert lev in s

    def test_severity_has_slo_budget(self):
        assert "slo" in _ref("severity-framework.md").lower()


# ──────────────────────────────────────────────────────────────────────
class TestLineCount:

    def test_under_budget(self):
        # 420 -> 460 (2026-08-04) paid for Gate 5 and the §9.0 mode matrix;
        # 460 -> 500 (2026-08-05) paid for the user-format precedence rule in §9.0,
        # which resolves a conflict observed in a live run: the model dropped the
        # 9.2/9.9 spine to obey an explicit "only the RCA section" instruction.
        # 500 is this repo's established second tier (systematic-debugging, load-test,
        # unit-test, security-review all sit at 488-500), not a bespoke number.
        # Prose in §1/§3/§8/§9 was compacted first; the rest is runtime rules the
        # model needs, and §7's anti-examples stay whole.
        lines = SKILL_MD.count("\n") + 1
        assert lines <= 500, f"SKILL.md is {lines} lines (budget: 500)"


# ──────────────────────────────────────────────────────────────────────
class TestCrossFileConsistency:

    @pytest.fixture(autouse=True)
    def _refs(self):
        self.template = _ref("postmortem-template.md").lower()
        self.rca = _ref("rca-techniques.md").lower()
        self.severity = _ref("severity-framework.md").lower()

    def test_5why_in_both(self):
        assert "5-why" in SKILL_LOWER
        assert "5-why" in self.rca

    def test_blameless_in_both(self):
        assert "blameless" in SKILL_LOWER
        assert "blameless" in self.rca or "blameless" in self.template

    def test_sev1_in_both(self):
        assert "sev-1" in SKILL_LOWER
        assert "sev-1" in self.severity

    def test_timeline_in_skill_and_template(self):
        assert "timeline" in SKILL_LOWER
        assert "timeline" in self.template

    def test_action_items_in_skill_and_template(self):
        assert "action item" in SKILL_LOWER
        assert "action item" in self.template

    def test_template_min_lines(self):
        lines = _ref("postmortem-template.md").count("\n") + 1
        assert lines >= 150

    def test_rca_min_lines(self):
        lines = _ref("rca-techniques.md").count("\n") + 1
        assert lines >= 150

    def test_severity_min_lines(self):
        lines = _ref("severity-framework.md").count("\n") + 1
        assert lines >= 100

    # ── Numeric threshold cross-validation ──────────────────────────

    def test_5why_depth_threshold_consistent(self):
        """SKILL.md says 'depth >= 3'; rca-techniques.md depth table must include depth 3."""
        assert "depth >= 3" in SKILL_LOWER
        assert "| 3 |" in self.rca or "depth 3" in self.rca

    def test_detection_gap_target_consistent(self):
        """Detection gap < 5 min target must appear in both SKILL.md and template."""
        assert "5 min" in SKILL_LOWER
        assert "detection gap" in self.template
        assert "< 5 min" in self.template

    def test_response_gap_target_in_template(self):
        """Response gap target must be defined in template."""
        assert "response gap" in self.template
        assert "< 5 min" in self.template

    def test_sev1_duration_threshold_consistent(self):
        """SEV-1 '> 30 min' threshold must match between SKILL.md and severity framework."""
        assert "30 min" in SKILL_LOWER
        assert "30 min" in self.severity

    def test_sev2_duration_threshold_consistent(self):
        """SEV-2 '> 15 min' threshold must match between SKILL.md and severity framework."""
        assert "15 min" in SKILL_LOWER
        assert "15 min" in self.severity

    def test_sev1_action_item_deadline_consistent(self):
        """SEV-1 action items '48 hours' deadline must match across files."""
        assert "48 hours" in SKILL_LOWER
        assert "48 hours" in self.severity

    def test_action_categories_in_template(self):
        """Prevent/detect/mitigate categories must appear in template."""
        for cat in ("prevent", "detect", "mitigate"):
            assert cat in self.template, f"category '{cat}' not in template"

    def test_5why_stop_criterion_consistent(self):
        """5-Why stop criterion 'process or design' must appear in both SKILL.md and rca-techniques."""
        assert "process or design" in SKILL_LOWER
        assert "process" in self.rca and "design" in self.rca

# ──────────────────────────────────────────────────────────────────────
class TestLanguageContract:
    """The reviewer's fork: either declare English-only, or follow the user's language
    and make the mechanical layer follow too. This skill does the latter, so the
    support boundary has to be stated rather than discovered."""

    def test_language_rule_is_declared(self):
        assert "write the post-mortem in the language the user is using" in SKILL_FLAT

    def test_supported_languages_are_named(self):
        assert "english and chinese" in SKILL_FLAT

    def test_unsupported_languages_are_admitted(self):
        assert "other languages are not yet aliased" in SKILL_FLAT

    def test_linter_carries_the_aliases_it_claims(self):
        source = (SKILL_DIR / "scripts" / "lint_postmortem.py").read_text(encoding="utf-8")
        for alias in ("时间线", "行动项", "未覆盖风险", "负责人", "截止", "不适用",
                      "预防", "检测", "缓解", "北京时间"):
            assert alias in source, f"linter is missing the alias it claims: {alias}"

    def test_grader_carries_the_aliases_too(self):
        source = (SKILL_DIR / "scripts" / "grade_postmortem_eval.py").read_text(encoding="utf-8")
        for alias in ("时间线", "行动项", "未覆盖风险", "模式", "根因"):
            assert alias in source, f"grader is missing the alias it claims: {alias}"


# ──────────────────────────────────────────────────────────────────────
class TestGate5SensitiveData:
    """Gate 5 exists because incident evidence carries customer and credential data
    and a post-mortem circulates far wider than the logs it was built from."""

    def test_gate_exists(self):
        assert "Gate 5: Sensitive Data & Distribution" in SKILL_MD

    def test_covers_credential_classes(self):
        for kw in ("credential", "token", "connection uri"):
            assert kw in SKILL_LOWER, f"Gate 5 must name {kw}"

    def test_covers_customer_identifiers(self):
        for kw in ("customer identifier", "email", "payment data"):
            assert kw in SKILL_LOWER, f"Gate 5 must name {kw}"

    def test_employee_names_replaced_by_role(self):
        assert "the on-call engineer" in SKILL_LOWER

    def test_requires_distribution_marking(self):
        assert "**Distribution**" in SKILL_MD
        assert "**Redaction**" in SKILL_MD

    def test_security_disclosure_not_waivable(self):
        assert "disclosure process" in SKILL_LOWER
        assert "not yours" in SKILL_LOWER

    def test_stops_on_credential(self):
        assert "STOP if a credential appears" in SKILL_MD

    def test_linter_enforces_gate_5(self):
        assert "Gate 5 credential/PII scan" in SKILL_MD

    def test_template_carries_distribution_header(self):
        template = _ref("postmortem-template.md")
        assert "Distribution" in template and "Redaction" in template


# ──────────────────────────────────────────────────────────────────────
class TestOutputContractByMode:
    """§9.0 replaced 'every response MUST include these sections', which was
    unsatisfiable alongside the Quick / Review / Extract / Planning deliverables."""

    def test_matrix_exists(self):
        assert "### 9.0 Required Sections by Mode" in SKILL_MD

    def test_matrix_has_all_four_modes(self):
        header = [ln for ln in SKILL_MD.splitlines() if ln.startswith("| Section")]
        assert header, "§9.0 must have a mode matrix header row"
        for mode in ("Draft", "Review", "Extract", "Planning"):
            assert mode in header[0], f"§9.0 matrix missing column: {mode}"

    def test_no_blanket_every_response_rule(self):
        """The contradicting sentence must be gone, not merely qualified."""
        assert "Every response MUST include these sections" not in SKILL_MD

    def test_mandatory_spine_in_every_mode(self):
        """9.2 and 9.9 are the only sections required by all four modes."""
        rows = {ln.split("|")[1].strip(): ln for ln in SKILL_MD.splitlines()
                if ln.startswith("| 9.")}
        assert rows, "§9.0 matrix has no section rows"
        for key in ("9.2 Mode & Depth", "9.9 Uncovered Risks"):
            assert key in rows, f"§9.0 matrix missing row: {key}"
            cells = [c.strip() for c in rows[key].split("|")[2:6]]
            assert all(c == "Yes" for c in cells), \
                f"{key} must be required in all four modes, got {cells}"

    def test_out_of_contract_sections_are_marked(self):
        """A mode that does not require a section must show — , not blank."""
        rows = [ln for ln in SKILL_MD.splitlines() if ln.startswith("| 9.")]
        assert len(rows) == 9, f"expected 9 section rows, got {len(rows)}"
        for row in rows:
            for cell in [c.strip() for c in row.split("|")[2:6]]:
                assert cell in ("Yes", "—"), f"unexpected matrix cell {cell!r} in {row}"

    def test_padding_is_a_defect(self):
        assert "padding it with speculation is a defect" in SKILL_LOWER

    def test_planning_mode_is_gate_3_option(self):
        gate3 = SKILL_MD.split("Gate 3: Scope Classification")[1].split("### Gate 4")[0]
        assert "Planning" in gate3, "Planning must be a declared Gate 3 mode"

    def test_gate_1_routes_to_planning_instead_of_dead_stop(self):
        gate1 = SKILL_MD.split("Gate 1: Incident Context Collection")[1] \
                        .split("### Gate 2")[0]
        assert "Planning" in gate1
        assert "Never synthesize a Draft" in gate1

    def test_gate_4_is_mode_aware(self):
        gate4 = SKILL_MD.split("Gate 4: Output Completeness")[1].split("### Gate 5")[0]
        assert "your mode" in gate4
        assert "not gaps" in gate4

    def test_quick_depth_keeps_the_spine(self):
        assert "§9.0 spine" in SKILL_MD


# ──────────────────────────────────────────────────────────────────────
class TestOrgPolicyPrecedence:
    """Built-in dollar and minute thresholds are defaults, not universal rules."""

    def test_skill_defers_to_org_policy(self):
        assert "The organization's own incident policy wins" in SKILL_MD

    def test_skill_names_thresholds_as_defaults(self):
        assert "defaults for when no local" in SKILL_LOWER

    def test_skill_admits_calibration_limits(self):
        for kw in ("mid-size saas", "hospital", "bank"):
            assert kw in SKILL_LOWER, f"§6 must admit the calibration limit: {kw}"

    def test_severity_reference_defers_too(self):
        severity = _ref("severity-framework.md").lower()
        assert "organization" in severity
        assert "default" in severity


# ──────────────────────────────────────────────────────────────────────
class TestLinterContract:
    """§8 must describe what the linter actually does. The prose previously
    promised checks the implementation could not perform on its own template."""

    def test_mode_flag_documented(self):
        assert "--mode draft" in SKILL_MD

    def test_all_three_entry_formats_documented(self):
        for fmt in ("bare `14:23", "- 14:23", "| 14:23 |"):
            assert fmt in SKILL_MD, f"§8 must document entry format: {fmt}"

    def test_table_and_empty_cells_documented(self):
        assert "table form" in SKILL_LOWER
        assert "`TBD` cells" in SKILL_MD

    def test_checks_named_in_skill_exist_in_linter(self):
        """Every check name §8 advertises must be emittable by the script."""
        source = (SKILL_DIR / "scripts" / "lint_postmortem.py").read_text(encoding="utf-8")
        for claim, check in (
            ("chronological order", "timeline-order"),
            ("explicit UTC declaration", "timeline-timezone"),
            ("non-empty \"Uncovered Risks\"", "uncovered-risks"),
            ("Gate 5 credential/PII scan", "sensitive-data"),
        ):
            assert claim in SKILL_MD, f"§8 no longer claims: {claim}"
            assert f'"{check}"' in source, f"linter cannot emit advertised check {check}"


# ──────────────────────────────────────────────────────────────────────
class TestCoverageDocAccuracy:
    """COVERAGE.md drifted to 135 while the suite had grown to 144. Encode the
    count as data and verify it, so the claim can never silently rot again."""

    COVERAGE = pathlib.Path(__file__).resolve().parent / "COVERAGE.md"

    def _declared_total(self) -> int:
        m = re.search(r"\*\*Total tests:\s*(\d+)\*\*", self.COVERAGE.read_text(encoding="utf-8"))
        assert m, "COVERAGE.md must state '**Total tests: N**'"
        return int(m.group(1))

    def _actual_total(self) -> int:
        import ast
        total = 0
        for path in sorted(self.COVERAGE.parent.glob("test_*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                        and node.name.startswith("test_"):
                    total += 1
        return total

    def test_declared_total_matches_collected(self):
        declared, actual = self._declared_total(), self._actual_total()
        assert declared == actual, \
            f"COVERAGE.md declares {declared} tests, suite defines {actual}"

    def test_coverage_doc_lists_every_test_file(self):
        text = self.COVERAGE.read_text(encoding="utf-8")
        for path in sorted(self.COVERAGE.parent.glob("test_*.py")):
            assert path.name in text, f"COVERAGE.md does not mention {path.name}"


# ──────────────────────────────────────────────────────────────────────
class TestRcaConsistencyAcrossFiles:
    """§5.2 was changed to pick a technique by causal shape, but the scorecard, the
    template and the contributing-factor table still assumed 5-Why and a single root
    cause. A correct fault-tree analysis was simultaneously required and penalised."""

    def test_template_does_not_mandate_5why(self):
        template = _ref("postmortem-template.md")
        assert "[5-Why minimum" not in template
        rca_block = template.split("## Root Cause Analysis")[1].split("##")[0]
        assert "technique" in rca_block.lower()

    def test_template_5why_block_is_scoped_to_5why(self):
        """The 5-Why fill-in template must not read as the only allowed shape."""
        template = _ref("postmortem-template.md")
        block = _flat(template.split("### 5-Why Template")[1].split("###")[0])
        assert "only when" in block
        assert "scores every technique equally" in block

    def test_contributing_factor_table_allows_multiple_root_causes(self):
        rca = _ref("rca-techniques.md")
        assert "Usually 1 (rarely 2)" not in rca
        assert "one per failed defense" in rca

    def test_every_file_agrees_5why_is_a_default_not_a_mandate(self):
        """Sweep: no file may state 5-Why as an unconditional minimum."""
        offenders = []
        for name in ("SKILL.md", "references/postmortem-template.md",
                     "references/rca-techniques.md", "references/severity-framework.md"):
            text = (SKILL_DIR / name).read_text(encoding="utf-8")
            for i, line in enumerate(text.splitlines(), 1):
                low = line.lower()
                if "5-why" not in low:
                    continue
                # An unconditional demand: "5-Why" next to minimum/required/must/all.
                if re.search(r"5-why[^.\n]{0,40}\b(minimum|required|mandatory)\b", low) or \
                   re.search(r"\b(all|every)\b[^.\n]{0,30}5-why", low):
                    offenders.append(f"{name}:{i}: {line.strip()}")
        assert not offenders, "5-Why stated as a mandate:\n" + "\n".join(offenders)


# ──────────────────────────────────────────────────────────────────────
class TestActionCategoryPolicy:
    """Requiring all three categories unconditionally produced filler action items."""

    def test_na_with_reason_is_permitted(self):
        assert "n/a — <reason>" in SKILL_FLAT
        assert "rather than inventing a low-value item" in SKILL_FLAT

    def test_empty_category_still_a_finding(self):
        assert "an empty category is a finding; a justified n/a is an answer." in SKILL_FLAT

    def test_review_mode_exempt_from_categories(self):
        """Review-mode action items fix the document, not the system."""
        assert "review mode is exempt" in SKILL_FLAT


# ──────────────────────────────────────────────────────────────────────
class TestDepthIsLintable:
    """Quick depth delivers one section + the 9.2/9.9 spine. Without a matching linter
    flag, an output that perfectly obeys the Quick contract failed the mechanical gate."""

    def test_skill_documents_depth_flag(self):
        assert "--depth quick" in SKILL_FLAT

    def test_linter_exposes_depth(self):
        source = (SKILL_DIR / "scripts" / "lint_postmortem.py").read_text(encoding="utf-8")
        assert 'DEPTHS = ("standard", "quick", "deep")' in source
        assert '"--depth"' in source

    def test_skill_states_what_quick_still_enforces(self):
        assert "still lints everything present" in SKILL_FLAT
