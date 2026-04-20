"""Contract tests for incident-postmortem-postmortem SKILL.md."""

import pathlib
import re

import pytest

SKILL_DIR = pathlib.Path(__file__).resolve().parents[2]
SKILL_MD = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
SKILL_LOWER = SKILL_MD.lower()
REFS_DIR = SKILL_DIR / "references"


def _ref(name: str) -> str:
    return (REFS_DIR / name).read_text(encoding="utf-8")


# ──────────────────────────────────────────────────────────────────────
class TestFrontmatter:

    @pytest.fixture(autouse=True)
    def _front(self):
        m = re.search(r"^---\n(.*?)\n---", SKILL_MD, re.DOTALL)
        assert m, "YAML frontmatter block not found"
        self.front = m.group(1)

    def test_name(self):
        assert "name: incident-postmortem-postmortem" in self.front

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
        assert "Use 5-Why analysis as minimum" in SKILL_MD
        assert "Root cause must be systemic, not individual" in SKILL_MD

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
                      "5-Why analysis depth >= 3",
                      "Contributing factors distinguished",
                      "Blameless language throughout"):
            assert item in SKILL_MD

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
        lines = SKILL_MD.count("\n") + 1
        assert lines <= 420, f"SKILL.md is {lines} lines (budget: 420)"


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