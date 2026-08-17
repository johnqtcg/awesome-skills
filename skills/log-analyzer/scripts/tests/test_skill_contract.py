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

    def test_allowed_tools_grants_the_read_only_core(self):
        # Presence-only checks cannot tell a safe grant from a destructive one:
        # the previous version of this test asserted `awk *`/`sed *`/`gzip *`/
        # `journalctl *` were present and called them "safe log inspection", while
        # every one of them auto-approved a destructive invocation. The security
        # properties are asserted in test_allowed_tools.py against an attack
        # corpus; this test only pins the minimum read surface.
        assert "allowed-tools:" in self.front
        for tool in ("Read", "Grep", "Glob", "jq", "kubectl logs", "redact_log.py"):
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

    def _mode_rows(self) -> dict[str, list[str]]:
        """Parse the mode table as data. Asserting on exact prose passes on an
        inverted claim and fails on a harmless rewording."""
        sec = re.search(r"## Analysis Modes.*?(?=^## )", SKILL_MD, re.DOTALL | re.MULTILINE)
        assert sec, "Analysis Modes section not found"
        rows = {}
        for line in sec.group(0).splitlines():
            m = re.match(r"\|\s*\*\*(Lite|Standard|Strict)\*\*", line.strip())
            if m:
                rows[m.group(1)] = [c.strip() for c in line.strip().strip("|").split("|")]
        return rows

    def test_three_modes_defined(self):
        assert "## Analysis Modes (Lite / Standard / Strict)" in SKILL_MD
        rows = self._mode_rows()
        assert set(rows) == {"Lite", "Standard", "Strict"}, \
            f"expected exactly three modes, found {sorted(rows)}"

    def test_default_is_standard(self):
        assert "Default: `Standard`" in SKILL_MD

    def test_mode_selection_rules_present(self):
        assert "Choose `Lite` only when scope is small" in SKILL_MD
        assert "Choose `Strict`" in SKILL_MD
        assert "Use `Standard` for everything else." in SKILL_MD

    def test_mode_volume_caps_present_and_ordered(self):
        rows = self._mode_rows()
        caps = {}
        for mode, cells in rows.items():
            m = re.search(r"≤\s*(\d+)", cells[-1])
            assert m, f"{mode} row has no finding cap: {cells[-1]!r}"
            caps[mode] = int(m.group(1))
        assert caps["Lite"] < caps["Standard"] < caps["Strict"], \
            f"caps must widen with depth, got {caps}"

    def test_high_severity_is_exempt_from_the_cap(self):
        sec = re.search(r"## Analysis Modes.*?(?=^## )", SKILL_MD, re.DOTALL | re.MULTILINE)
        assert re.search(r"High[- ]severity is never dropped|High severity is never dropped",
                         sec.group(0)), \
            "the mode table must say a cap never drops a High finding"


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

    def test_base_rate_suppression_has_a_severity_carve_out(self):
        """Frequency must not be the sole severity input: a single security or
        data-integrity line is a finding, not noise."""
        gate = re.search(r"### 4\).*?(?=^### 5\))", SKILL_MD, re.DOTALL | re.MULTILINE)
        assert gate, "Gate 4 section not found"
        body = gate.group(0).lower()
        assert "exempt" in body, "Gate 4 must name an exemption from base-rate suppression"
        for cls in ("security", "data integrity", "financial", "compliance", "invariant"):
            assert cls in body, f"base-rate exemption does not cover: {cls}"
        assert "n=1" in body or "regardless of rate" in body or "at n=1" in body, \
            "the exemption must say these are reported at a single occurrence"


# ──────────────────────────────────────────────────────────────────────
class TestGateTaxonomy:
    """Gate failures are not uniform. Claiming they are is a contradiction the
    body of the document then refutes gate by gate."""

    CLASSES = {"BLOCK", "DEGRADE", "WARN", "CAP"}
    TABLE_CLASSES = {"BLOCK-EVIDENCE", "BLOCK-WORKFLOW", "DEGRADE", "WARN", "CAP"}

    def _gate_headings(self) -> list[tuple[str, str]]:
        return re.findall(r"^### (\d)\) (.+)$", SKILL_MD, re.MULTILINE)

    def test_no_blanket_hard_blocker_claim(self):
        assert "Gates are serial hard blockers" not in SKILL_MD, (
            "this claim is contradicted by 6 of the 7 gates, which degrade, warn, "
            "or cap rather than stop the workflow"
        )

    def test_taxonomy_table_defines_all_classes(self):
        for cls in self.TABLE_CLASSES:
            assert f"**{cls}**" in SKILL_MD, f"gate-class table missing {cls}"

    def test_block_is_split_by_scope(self):
        """The table originally said BLOCK stops the workflow while the gate body
        said to describe the line and continue. Those are different actions and
        need different names."""
        gate = re.search(r"### 2\).*?(?=^### 3\))", SKILL_MD, re.DOTALL | re.MULTILINE)
        assert gate, "Gate 2 section not found"
        body = gate.group(0)
        assert "BLOCK-EVIDENCE" in body and "BLOCK-WORKFLOW" in body, \
            "Gate 2 must distinguish withholding one line from stopping the report"
        evidence, workflow = body.index("BLOCK-EVIDENCE"), body.index("BLOCK-WORKFLOW")
        assert re.search(r"continue the analysis", body[evidence:workflow], re.IGNORECASE), \
            "BLOCK-EVIDENCE must say the analysis continues"

    def test_every_gate_declares_its_class(self):
        headings = self._gate_headings()
        assert len(headings) == 7, f"expected 7 gates, found {len(headings)}"
        for num, title in headings:
            cls = title.rsplit("—", 1)[-1].strip()
            assert cls in self.CLASSES, (
                f"Gate {num} heading does not end in a class from {sorted(self.CLASSES)}: {title!r}"
            )

    def test_exactly_one_block_gate(self):
        blocks = [t for _, t in self._gate_headings() if t.endswith("BLOCK")]
        assert len(blocks) == 1, f"expected exactly one BLOCK gate, found {blocks}"
        assert "PII" in blocks[0] or "Redaction" in blocks[0], \
            "the BLOCK gate must be the PII/secret gate — a leak is unrecoverable"

    def test_every_gate_states_its_on_failure_behaviour(self):
        sections = re.split(r"^### \d\) ", SKILL_MD, flags=re.MULTILINE)[1:]
        missing = [s.splitlines()[0] for s in sections if "On failure" not in s]
        assert not missing, f"gates with no stated failure behaviour: {missing}"

    def test_execution_status_reports_gate_outcomes(self):
        assert "`Gate outcomes`" in SKILL_MD, \
            "Execution Status must record which gates fired and in which class"

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
class TestReferenceNavigation:
    """Long references carry a Contents list so a reader can jump instead of
    scrolling. A TOC whose anchors do not resolve is worse than none -- it sends
    the reader somewhere that is not there -- so the links are checked, not just
    counted."""

    LONG_THRESHOLD = 100

    @staticmethod
    def _slug(heading: str) -> str:
        """GitHub's anchor rule: strip markdown formatting, lowercase, drop
        punctuation, replace EACH space with a hyphen. No collapsing -- an em dash
        between words leaves two spaces and therefore two hyphens."""
        s = re.sub(r"[`*_]", "", heading).lower()
        s = re.sub(r"[^\w\s-]", "", s)
        return s.strip().replace(" ", "-")

    def _refs(self):
        return sorted(p for p in REFS_DIR.glob("*.md"))

    def _long_refs(self):
        out = []
        for p in self._refs():
            lines = p.read_text(encoding="utf-8").splitlines()
            heads = [l for l in lines if l.startswith("## ") and l != "## Contents"]
            if len(lines) >= self.LONG_THRESHOLD and len(heads) >= 5:
                out.append(p)
        return out

    def test_there_are_long_references_to_check(self):
        assert self._long_refs(), "fixture drift: no long references found"

    def test_long_references_have_a_contents_list(self):
        missing = [p.name for p in self._long_refs()
                   if "## Contents" not in p.read_text(encoding="utf-8")]
        assert not missing, f"long references with no Contents list: {missing}"

    def test_every_toc_link_resolves_to_a_heading(self):
        broken = []
        for p in self._refs():
            text = p.read_text(encoding="utf-8")
            if "## Contents" not in text:
                continue
            anchors = {self._slug(l[3:].strip())
                       for l in text.splitlines() if l.startswith("## ")}
            anchors |= {self._slug(l[4:].strip())
                        for l in text.splitlines() if l.startswith("### ")}
            for label, target in re.findall(r"^- \[(.+?)\]\(#(.+?)\)$", text, re.MULTILINE):
                if target not in anchors:
                    broken.append(f"{p.name}: [{label}](#{target})")
        assert not broken, f"TOC links pointing at no heading: {broken}"

    def test_every_top_level_section_is_listed(self):
        missing = []
        for p in self._refs():
            text = p.read_text(encoding="utf-8")
            if "## Contents" not in text:
                continue
            listed = set(re.findall(r"^- \[(.+?)\]\(#", text, re.MULTILINE))
            for l in text.splitlines():
                if l.startswith("## ") and l != "## Contents":
                    if l[3:].strip() not in listed:
                        missing.append(f"{p.name}: {l[3:].strip()}")
        assert not missing, f"sections absent from their Contents list: {missing}"


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
