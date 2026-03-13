"""
Structural and content contract tests for the google-search skill.
Validates that SKILL.md and reference files maintain required sections,
gates, modes, patterns, and quality criteria.
"""

import os
import re
import pytest

SKILL_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
SKILL_MD = os.path.join(SKILL_ROOT, "SKILL.md")
REFS_DIR = os.path.join(SKILL_ROOT, "references")


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


SKILL_TEXT = _read(SKILL_MD)


# ── Frontmatter ──────────────────────────────────────────────────────────

class TestFrontmatter:
    def test_has_yaml_frontmatter(self):
        assert SKILL_TEXT.startswith("---"), "SKILL.md must start with YAML frontmatter"

    def test_has_name(self):
        assert re.search(r"^name:\s*google-search", SKILL_TEXT, re.MULTILINE)

    def test_has_description(self):
        m = re.search(r"^description:\s*(.+)", SKILL_TEXT, re.MULTILINE)
        assert m and len(m.group(1)) >= 50, "description must be >= 50 chars"

    def test_has_allowed_tools(self):
        assert re.search(r"^allowed-tools:", SKILL_TEXT, re.MULTILINE)


# ── Mandatory H2 Sections ────────────────────────────────────────────────

class TestMandatorySections:
    REQUIRED_HEADINGS = [
        "Overview",
        "Mandatory Gates",
        "Workflow",
        "Anti-Examples",
        "Honest Degradation",
        "Safety Rules",
        "Output Contract",
        "Load References Selectively",
        "Worked Examples",
    ]

    @pytest.mark.parametrize("heading", REQUIRED_HEADINGS)
    def test_h2_present(self, heading):
        pattern = rf"^## {re.escape(heading)}"
        assert re.search(pattern, SKILL_TEXT, re.MULTILINE), f"Missing H2: {heading}"


# ── Mandatory Gates ──────────────────────────────────────────────────────

class TestMandatoryGates:
    GATES = [
        ("1", "Scope Classification Gate"),
        ("2", "Ambiguity Resolution Gate"),
        ("3", "Evidence Requirements Gate"),
        ("4", "Language Detection Gate"),
        ("5", "Source Path Gate"),
        ("6", "Execution Mode Gate"),
        ("7", "Budget Control Gate"),
        ("8", "Execution Integrity Gate"),
    ]

    @pytest.mark.parametrize("number,name", GATES)
    def test_gate_numbered(self, number, name):
        pattern = rf"###\s*{number}\)\s*{re.escape(name)}"
        assert re.search(pattern, SKILL_TEXT), f"Gate {number}) {name} not found with correct numbering"

    def test_gates_serial_order(self):
        positions = []
        for num, name in self.GATES:
            m = re.search(rf"###\s*{num}\)", SKILL_TEXT)
            assert m, f"Gate {num} not found"
            positions.append(m.start())
        assert positions == sorted(positions), "Gates must appear in serial order 1-8"

    def test_ascii_flow_diagram(self):
        assert "1) Scope" in SKILL_TEXT and "8) Execution" in SKILL_TEXT, \
            "ASCII flow diagram must reference first and last gate"

    def test_stop_and_ask(self):
        assert "STOP and ASK" in SKILL_TEXT, "Ambiguity gate must include STOP and ASK directive"

    def test_serial_blocking_statement(self):
        assert re.search(r"strict serial order", SKILL_TEXT, re.IGNORECASE), \
            "Gates must state serial execution"
        assert re.search(r"blocks all subsequent", SKILL_TEXT, re.IGNORECASE), \
            "Gates must state blocking behavior"

    def test_evidence_chain_table(self):
        assert "Conclusion Type" in SKILL_TEXT, "Evidence Requirements gate must have conclusion type table"
        assert "Minimum Evidence Chain" in SKILL_TEXT, "Evidence Requirements gate must define evidence chains"
        assert "Target Confidence" in SKILL_TEXT, "Evidence Requirements gate must set target confidence"

    def test_evidence_chain_types(self):
        for ctype in ["Single factual claim", "Best practice", "Numeric claim",
                       "Technology comparison", "Person or entity", "Disputed"]:
            assert ctype in SKILL_TEXT, f"Evidence chain missing conclusion type: {ctype}"


# ── Execution Modes ──────────────────────────────────────────────────────

class TestExecutionModes:
    def test_three_modes_defined(self):
        for mode in ["Quick", "Standard", "Deep"]:
            assert mode in SKILL_TEXT, f"Mode '{mode}' must be defined"

    def test_mode_auto_selection_table(self):
        assert "Signal" in SKILL_TEXT and "→ Mode" in SKILL_TEXT, \
            "Must have signal-to-mode auto-selection table"

    def test_mode_budget_limits(self):
        assert "max 2 queries" in SKILL_TEXT, "Quick mode must specify max 2 queries"
        assert "max 5 queries" in SKILL_TEXT, "Standard mode must specify max 5 queries"
        assert "max 8 queries" in SKILL_TEXT, "Deep mode must specify max 8 queries"

    def test_user_override(self):
        assert re.search(r"user explicitly requests.*mode", SKILL_TEXT, re.IGNORECASE), \
            "User override for execution mode must be mentioned"

    def test_evidence_chain_in_examples(self):
        examples_section = SKILL_TEXT.split("## Worked Examples")[-1]
        assert "Evidence chain" in examples_section, \
            "Worked examples must show evidence chain step"


# ── Anti-Examples ────────────────────────────────────────────────────────

class TestAntiExamples:
    def test_minimum_anti_examples(self):
        count = len(re.findall(r"^\d+\.\s+\*\*", SKILL_TEXT, re.MULTILINE))
        assert count >= 6, f"Need >= 6 anti-examples, found {count}"

    def test_has_bad_good_pairs(self):
        bad_count = SKILL_TEXT.count("BAD:")
        good_count = SKILL_TEXT.count("GOOD:")
        assert bad_count >= 2, f"Need >= 2 BAD examples, found {bad_count}"
        assert good_count >= 2, f"Need >= 2 GOOD examples, found {good_count}"


# ── Honest Degradation ──────────────────────────────────────────────────

class TestDegradation:
    def test_three_levels(self):
        for level in ["Full", "Partial", "Blocked"]:
            assert f"**{level}**" in SKILL_TEXT, f"Degradation level '{level}' must be defined"


# ── Output Contract ──────────────────────────────────────────────────────

class TestOutputContract:
    REQUIRED_FIELDS = [
        "Execution mode",
        "Degradation level",
        "Conclusion summary",
        "Evidence chain status",
        "Key evidence",
        "Source assessment",
        "Key numbers",
        "Reusable queries",
    ]

    @pytest.mark.parametrize("field", REQUIRED_FIELDS)
    def test_output_field_present(self, field):
        assert field in SKILL_TEXT, f"Output contract missing field: {field}"


# ── Worked Examples ──────────────────────────────────────────────────────

class TestWorkedExamples:
    def test_minimum_examples(self):
        count = len(re.findall(r"^### Example \d+:", SKILL_TEXT, re.MULTILINE))
        assert count >= 2, f"Need >= 2 worked examples, found {count}"

    def test_examples_follow_gate_structure(self):
        assert "Gates" in SKILL_TEXT.split("## Worked Examples")[-1], \
            "Worked examples must reference gate classification"


# ── Reference Files ──────────────────────────────────────────────────────

class TestReferenceFiles:
    REQUIRED_REFS = [
        "query-patterns.md",
        "source-evaluation.md",
        "chinese-search-ecosystem.md",
        "high-conflict-topics.md",
        "ai-search-and-termination.md",
        "programmer-search-patterns.md",
    ]

    @pytest.mark.parametrize("ref", REQUIRED_REFS)
    def test_reference_exists(self, ref):
        assert os.path.isfile(os.path.join(REFS_DIR, ref)), f"Missing reference: {ref}"

    @pytest.mark.parametrize("ref", REQUIRED_REFS)
    def test_reference_not_empty(self, ref):
        path = os.path.join(REFS_DIR, ref)
        content = _read(path)
        assert len(content.strip()) > 100, f"Reference {ref} is too short"

    @pytest.mark.parametrize("ref", REQUIRED_REFS)
    def test_reference_linked_from_skill(self, ref):
        assert ref in SKILL_TEXT, f"Reference {ref} not linked from SKILL.md"


# ── Programmer Search Patterns ───────────────────────────────────────────

class TestProgrammerSearchPatterns:
    @pytest.fixture
    def content(self):
        return _read(os.path.join(REFS_DIR, "programmer-search-patterns.md"))

    REQUIRED_SECTIONS = [
        "Error Debugging",
        "Official Documentation",
        "GitHub Code Search",
        "Stack Overflow",
        "RFC and Technical Standards",
        "Performance Benchmarks",
        "Quick-Reference: Google Search Syntax",
    ]

    @pytest.mark.parametrize("section", REQUIRED_SECTIONS)
    def test_section_present(self, content, section):
        assert section in content, f"Missing section: {section}"

    def test_syntax_table(self, content):
        for syntax in ['`"phrase"`', '`site:`', '`filetype:`', '`intitle:`', '`after:`']:
            assert syntax in content, f"Syntax table missing: {syntax}"


# ── Source Evaluation Scorecard ──────────────────────────────────────────

class TestSourceEvaluationScorecard:
    @pytest.fixture
    def content(self):
        return _read(os.path.join(REFS_DIR, "source-evaluation.md"))

    def test_three_tier_scorecard(self, content):
        for tier in ["Critical", "Standard", "Hygiene"]:
            assert f"### {tier}" in content, f"Scorecard missing tier: {tier}"

    def test_scorecard_has_checkboxes(self, content):
        checkbox_count = content.count("- [ ]")
        assert checkbox_count >= 10, f"Scorecard needs >= 10 items, found {checkbox_count}"


# ── AI Search and Termination ────────────────────────────────────────────

class TestAISearchTermination:
    @pytest.fixture
    def content(self):
        return _read(os.path.join(REFS_DIR, "ai-search-and-termination.md"))

    def test_degradation_protocol(self, content):
        for level in ["Full Mode", "Partial Mode", "Blocked Mode"]:
            assert level in content, f"Missing degradation level: {level}"

    def test_search_budget(self, content):
        assert "8 queries" in content, "Must specify max query budget"


# ── Line Count Guard ─────────────────────────────────────────────────────

class TestLineLimits:
    def test_skill_md_under_500_lines(self):
        lines = SKILL_TEXT.count("\n") + 1
        assert lines <= 500, f"SKILL.md has {lines} lines, must be <= 500"

    def test_skill_md_over_100_lines(self):
        lines = SKILL_TEXT.count("\n") + 1
        assert lines >= 100, f"SKILL.md has {lines} lines, seems too short"
