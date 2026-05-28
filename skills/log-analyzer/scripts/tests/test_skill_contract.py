"""Contract tests for log-analyzer SKILL.md and references."""

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

    def test_name_is_log_analyzer(self):
        assert re.search(r"^name:\s*log-analyzer\s*$", self.front, re.MULTILINE), \
            "frontmatter name must be 'log-analyzer'"

    def test_description_includes_trigger_phrases(self):
        desc = self.front.lower()
        for kw in (
            "log analysis",
            "incident",
            "trace_id",
            "request_id",
            "slog",
            "syslog",
            "kubernetes",
            "incident-postmortem",
        ):
            assert kw in desc, f"description missing trigger keyword: {kw}"

    def test_allowed_tools_includes_safe_log_inspection(self):
        assert "allowed-tools:" in self.front
        for tool in ("Read", "Grep", "Glob", "jq", "kubectl logs", "journalctl"):
            assert tool in self.front, f"allowed-tools missing: {tool}"

    def test_no_unrestricted_bash(self):
        # We must not grant a bare Bash() — log analysis is read-only.
        assert "Bash(*)" not in self.front, "bare Bash(*) is too broad for log-analyzer"


# ──────────────────────────────────────────────────────────────────────
class TestStructure:

    def test_within_line_budget(self):
        n = len(SKILL_MD.splitlines())
        assert n <= 500, f"SKILL.md too long: {n} lines (budget 500)"

    def test_quick_reference_present(self):
        assert "## Quick Reference" in SKILL_MD

    def test_purpose_present(self):
        assert "## Purpose" in SKILL_MD

    def test_when_to_use_present(self):
        assert "## When To Use" in SKILL_MD


# ──────────────────────────────────────────────────────────────────────
class TestModes:

    def test_three_modes_defined(self):
        assert "## Analysis Modes (Lite / Standard / Strict)" in SKILL_MD
        for d in ("### Lite (fast triage)", "### Standard (default balanced analysis)",
                  "### Strict (incident / post-mortem grade)"):
            assert d in SKILL_MD, f"missing mode header: {d}"

    def test_default_is_standard(self):
        assert "Default: `Standard`" in SKILL_MD

    def test_mode_selection_rules_present(self):
        assert "Choose `Lite` only when scope is small" in SKILL_MD
        assert "Choose `Strict`" in SKILL_MD
        assert "Use `Standard` for everything else." in SKILL_MD

    def test_mode_volume_caps_present(self):
        for cap in ("≤ 5 findings", "≤ 10 findings", "≤ 15 findings"):
            assert cap in SKILL_MD, f"missing cap: {cap}"


# ──────────────────────────────────────────────────────────────────────
class TestMandatoryGates:

    def test_section_present(self):
        assert "## Mandatory Gates" in SKILL_MD

    @pytest.mark.parametrize("gate,heading", [
        ("format", "### 1) Format Detection Gate"),
        ("pii", "### 2) PII / Secret Redaction Gate"),
        ("time", "### 3) Time Window Boundary Gate"),
        ("stats", "### 4) Statistical Significance Gate"),
        ("correlation", "### 5) Correlation Gate"),
        ("causation", "### 6) Causation Discipline Gate (First-Error vs Root-Cause)"),
        ("volume", "### 7) Volume Cap & Severity-Tiered Reporting Gate"),
    ])
    def test_each_gate_present(self, gate, heading):
        assert heading in SKILL_MD, f"gate missing: {gate} → {heading}"

    def test_pii_gate_lists_classes(self):
        for cls in ("Bearer tokens", "API keys", "Email addresses",
                    "Credit card", "Cookies"):
            assert cls in SKILL_MD, f"PII class missing in Gate 2: {cls}"

    def test_time_window_gate_required_fields(self):
        for field in ("Window:", "Source:", "Coverage:"):
            assert field in SKILL_MD, f"time-window field missing: {field}"

    def test_statistical_gate_distinguishes_rate_from_count(self):
        assert "rate" in SKILL_MD.lower()
        assert "base rate" in SKILL_MD.lower()
        assert "baseline" in SKILL_MD.lower()

    def test_correlation_gate_names_ids(self):
        for field in ("trace_id", "request_id", "span_id"):
            assert field in SKILL_MD

    def test_causation_chain_has_four_links(self):
        for link in ("Symptom", "Proximate trigger", "Underlying cause", "Contributing factors"):
            assert link in SKILL_MD, f"causation chain missing link: {link}"

    def test_volume_cap_phases(self):
        for phase in ("Phase 1 — High", "Phase 2 — Medium", "Phase 3 — Low"):
            assert phase in SKILL_MD


# ──────────────────────────────────────────────────────────────────────
class TestWorkflow:

    def test_workflow_section_present(self):
        assert "## Workflow" in SKILL_MD

    def test_workflow_step0_records_mode(self):
        assert "0. **Select mode**" in SKILL_MD

    def test_workflow_includes_first_occurrence_pivot(self):
        assert "First-occurrence pivot" in SKILL_MD

    def test_workflow_includes_handoff_step(self):
        assert "Hand-off." in SKILL_MD or "Hand-off Protocol" in SKILL_MD


# ──────────────────────────────────────────────────────────────────────
class TestOutputFormat:

    def test_required_sections_listed(self):
        for section in (
            "### Analysis Mode",
            "### Window & Source",
            "### Executive Summary",
            "### Findings",
            "### Timeline",
            "### Correlation Map",
            "### Root Cause Hypotheses",
            "### Recommendations",
            "### Suppressed Items",
            "### Execution Status",
            "### Open Questions",
            "### Residual Risk / Investigation Gaps",
            "### Hand-off Protocol",
            "### Summary",
        ):
            assert section in SKILL_MD, f"output section missing: {section}"

    def test_finding_required_fields(self):
        for field in ("**ID:**", "**Confidence:**", "**Category:**",
                      "**Location:**", "**Evidence:**", "**Inference:**",
                      "**Refuter:**", "**Recommendation:**"):
            assert field in SKILL_MD, f"finding field missing: {field}"

    def test_confidence_levels_defined(self):
        for level in ("Confirmed", "Hypothesis", "Hypothesis — needs corroboration"):
            assert level in SKILL_MD, f"confidence level missing: {level}"

    def test_no_finding_case_documented(self):
        assert "## No-Finding Case" in SKILL_MD
        assert "No actionable findings in window." in SKILL_MD

    def test_handoff_block_structured(self):
        for k in ("incident_id", "impact_summary", "window_utc",
                  "affected_services", "top_findings", "blameless_framing"):
            assert k in SKILL_MD, f"hand-off field missing: {k}"


# ──────────────────────────────────────────────────────────────────────
class TestReferenceLoadingTriggers:

    REQUIRED_REFS = [
        "log-format-cheatsheet.md",
        "log-correlation.md",
        "log-aggregator-queries.md",
        "log-statistical-methods.md",
        "log-pii-redaction.md",
        "log-cascade-analysis.md",
        "log-tooling-commands.md",
        "log-anti-patterns.md",
        "log-analysis-quick-checklist.md",
        "example-output.md",
    ]

    def test_appendix_present(self):
        assert "## Appendix: Reference Loading Triggers" in SKILL_MD

    @pytest.mark.parametrize("ref", REQUIRED_REFS)
    def test_each_reference_referenced_from_skill_md(self, ref):
        assert ref in SKILL_MD, f"SKILL.md does not reference: {ref}"

    @pytest.mark.parametrize("ref", REQUIRED_REFS)
    def test_each_reference_file_exists_and_nonempty(self, ref):
        p = REFS_DIR / ref
        assert p.exists(), f"missing file: {ref}"
        text = p.read_text(encoding="utf-8")
        assert len(text.splitlines()) >= 30, f"{ref} too short (<30 lines)"


# ──────────────────────────────────────────────────────────────────────
class TestAntiPatternsReference:

    @pytest.fixture(autouse=True)
    def _load(self):
        self.text = _ref("log-anti-patterns.md")

    def test_minimum_anti_pattern_count(self):
        items = re.findall(r"^## A\d+\b", self.text, re.MULTILINE)
        assert len(items) >= 12, f"need ≥12 anti-patterns, found {len(items)}"

    def test_first_error_trap_documented(self):
        assert "First ERROR" in self.text or "First-error" in self.text or "first ERROR" in self.text

    def test_secret_leak_anti_pattern(self):
        assert "Bearer" in self.text

    def test_symptom_vs_cause_anti_pattern(self):
        assert "Symptom cluster" in self.text or "symptom cluster" in self.text


# ──────────────────────────────────────────────────────────────────────
class TestPiiRedactionReference:

    @pytest.fixture(autouse=True)
    def _load(self):
        self.text = _ref("log-pii-redaction.md")

    def test_hard_list_present(self):
        assert "Always Redact" in self.text

    def test_examples_before_after(self):
        assert "Before:" in self.text and "After:" in self.text

    def test_trace_id_explicitly_kept(self):
        assert "trace_id" in self.text
        assert "not redact" in self.text.lower() or "not a secret" in self.text.lower()


# ──────────────────────────────────────────────────────────────────────
class TestStatisticalReference:

    @pytest.fixture(autouse=True)
    def _load(self):
        self.text = _ref("log-statistical-methods.md")

    def test_rate_vs_count_section(self):
        assert "Rate" in self.text or "rate" in self.text
        assert "denominator" in self.text.lower()

    def test_baseline_section(self):
        assert "Baseline" in self.text or "baseline" in self.text


# ──────────────────────────────────────────────────────────────────────
class TestQuickChecklist:

    @pytest.fixture(autouse=True)
    def _load(self):
        self.text = _ref("log-analysis-quick-checklist.md")

    def test_three_phases(self):
        for h in ("Pre-Flight", "During Analysis", "Pre-Publish"):
            assert h in self.text, f"checklist phase missing: {h}"

    def test_checklist_items_minimum(self):
        items = re.findall(r"^\s*- \[ \]", self.text, re.MULTILINE)
        assert len(items) >= 20, f"≥20 checklist items expected, found {len(items)}"


# ──────────────────────────────────────────────────────────────────────
class TestExampleOutput:

    @pytest.fixture(autouse=True)
    def _load(self):
        self.text = _ref("example-output.md")

    def test_finding_with_required_fields(self):
        for field in ("**ID:**", "**Confidence:**", "**Category:**",
                      "**Location:**", "**Evidence:**", "**Inference:**",
                      "**Refuter:**", "**Recommendation:**"):
            assert field in self.text, f"example missing field: {field}"

    def test_redaction_demonstrated(self):
        assert "REDACTED" in self.text or "***" in self.text

    def test_handoff_block_demonstrated(self):
        for k in ("incident_id", "impact_summary", "window_utc",
                  "blameless_framing"):
            assert k in self.text, f"example hand-off missing: {k}"

    def test_correlation_table_demonstrated(self):
        assert "Operation" in self.text
        assert "Latency" in self.text
