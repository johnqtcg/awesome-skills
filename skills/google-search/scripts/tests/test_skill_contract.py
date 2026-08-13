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

    def test_allowed_tools_preapproves_the_search_action(self):
        """`allowed-tools` lists the tools this skill may use without a permission prompt.
        A search skill that does not pre-approve searching leaves its own core action to a
        prompt; WebFetch alone only covers reading a URL you already have."""
        m = re.search(r"^allowed-tools:\s*(.+)$", SKILL_TEXT, re.MULTILINE)
        assert m, "allowed-tools missing"
        granted = {t.strip() for t in m.group(1).replace(",", " ").split()}
        for tool in ("WebSearch", "WebFetch"):
            assert tool in granted, f"{tool} not pre-approved; granted={sorted(granted)}"


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

    def test_anti_examples_do_not_restate_a_query_count(self):
        """Query counts live in the mode-definitions table and nowhere else.

        An anti-example demanding "at least two queries in every mode" contradicts the
        table's `Quick | 1–2`, and a Quick factual question answered by one Precision query
        against an official source should not be forced to spend a second. State the
        *condition* instead of a count so there is no second number to keep in sync.
        """
        section = SKILL_TEXT.split("## Anti-Examples")[1].split("\n## ")[0]
        assert not re.search(
            r"at least (?:two|three|2|3)\b[^.]{0,60}quer", section, re.IGNORECASE
        ), "anti-examples restate a query minimum; the mode table owns those numbers"

    def test_mode_table_is_the_single_source_of_query_counts(self):
        row = next(
            (l for l in SKILL_TEXT.split("\n") if re.match(r"^\|\s*Quick\s*\|", l)), ""
        )
        assert row, "Quick row missing from the mode-definitions table"
        assert re.search(r"\|\s*1[–-]2\s*\|", row), f"Quick query range changed: {row!r}"


# ── Honest Degradation ──────────────────────────────────────────────────

class TestDegradation:
    def test_three_levels(self):
        for level in ["Full", "Partial", "Blocked"]:
            assert f"**{level}**" in SKILL_TEXT, f"Degradation level '{level}' must be defined"

    def test_full_requires_the_whole_evidence_chain(self):
        """Gate 3 defines chains of two or three links for Standard and Deep. Judging the
        strongest source alone cannot establish that the chain is complete, which is how a
        Partial gets labeled Full: the official page found answers an adjacent question."""
        row = next((l for l in SKILL_TEXT.split("\n") if l.startswith("| **Full**")), "")
        assert row, "Full row not found in the degradation table"
        assert "evidence chain" in row.lower(), (
            "the Full condition must reference the evidence chain, not only the strongest source"
        )

    @staticmethod
    def _decision_tree():
        return SKILL_TEXT.split("**Decision tree**")[1].split("```")[1]

    def test_every_degradation_level_is_reachable(self):
        """Blocked must be decided before the chain question.

        Every Blocked case also has an unsatisfied evidence chain, so asking about the chain
        first routes "budget exhausted, nothing found" to Partial and leaves Blocked
        unreachable — while Partial promises a qualified answer that does not exist.
        """
        tree = self._decision_tree()
        for level in ("Full", "Partial", "Blocked"):
            assert level in tree, f"{level} is not an outcome in the decision tree"
        assert tree.index("Blocked") < tree.index("evidence chain"), (
            "Blocked is nested below the evidence-chain question, so it can never be reached"
        )

    def test_decision_tree_asks_about_total_failure_first(self):
        tree = self._decision_tree()
        first = next(l.strip() for l in tree.split("\n") if l.strip())
        assert re.search(r"budget|paywall|walled garden", first, re.IGNORECASE), (
            f"first decision-tree question is {first!r}, not the total-failure check"
        )

    def test_decision_tree_still_checks_the_chain_before_the_source(self):
        tree = self._decision_tree()
        assert tree.index("evidence chain") < tree.index("target confidence"), (
            "the chain must be tested before judging whether the sources answer the question"
        )


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

    def test_key_numbers_row_defers_to_the_canonical_label_lists(self):
        """One list, not two. SKILL.md used to restate the source-tier values, and the copy
        drifted: it said Official/Primary/Third-party/OSINT/Adversary while
        source-evaluation.md said something else and the worked example used a third form
        ("Mixed official + practitioner") that appeared on neither list."""
        row = next(
            (l for l in SKILL_TEXT.split("\n") if "**Key numbers**" in l), ""
        )
        assert row, "Key numbers row not found"
        assert "source-evaluation.md" in row, "row must point at the canonical list"
        assert "OSINT" not in row and "Adversary" not in row, (
            "row restates the tier enum instead of deferring to it"
        )

    def test_quick_mode_output_shape_is_constrained(self):
        """Quick mode must be compact, and compactness must not be readable as permission to
        drop MUST fields.

        The first version of this guidance said "if the metadata is longer than the answer, cut
        the metadata". In the 2026-08-13 live eval the with-skill arm then produced a correct
        answer with no labels, no cited URL and no reusable queries — every MUST field for Quick
        gone. Brevity guidance has to name what is not cuttable.
        """
        assert re.search(r"Quick mode output shape", SKILL_TEXT), \
            "no Quick-mode output shape rule"
        block = SKILL_TEXT.split("Quick mode output shape")[1][:1400]
        assert "No tables" in block or "no tables" in block
        assert re.search(r"never dropped|not to delete fields", block), (
            "the shape rule must state that MUST fields survive compression"
        )
        for field in ("1", "2", "3", "7", "8"):
            assert field in block.split("MUST in Quick")[0][-120:], (
                f"field {field} is not listed as MUST in the Quick shape rule"
            )

    def test_reusable_queries_row_requires_marking_unrun_queries(self):
        row = next((l for l in SKILL_TEXT.split("\n") if "**Reusable queries**" in l), "")
        assert "not run" in row, (
            "listing a query you never executed without marking it violates the Execution "
            "Integrity gate"
        )


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

    REQUIRED_GITHUB_SUBSECTIONS = [
        "Code search qualifiers",
        "Qualifiers that do NOT work in code search",
        "Repository search qualifiers",
    ]

    @pytest.mark.parametrize("sub", REQUIRED_GITHUB_SUBSECTIONS)
    def test_github_engines_are_separated(self, content, sub):
        """GitHub's code search and repository search take different qualifiers. Presenting
        one merged list is what put `filename:` and `stars:>100` in the code-search
        examples, neither of which exists in that engine."""
        assert re.search(rf"^#+\s+{re.escape(sub)}\s*$", content, re.MULTILINE), \
            f"missing subsection: {sub}"


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

class TestLocalLinksResolve:
    """Every skill-local path cited anywhere in the package must exist.

    A path that resolves in this repository but not in an installed copy is a broken evidence
    link for every user who installs the skill. `evaluate/` and `rationale/` live one level
    above the package, so citing them bare reads as a local file that is not there — they must
    be introduced as repository references instead.
    """

    PACKAGE_FILES = [SKILL_MD] + sorted(
        [os.path.join(REFS_DIR, f) for f in os.listdir(REFS_DIR) if f.endswith(".md")]
    ) + [
        os.path.join(SKILL_ROOT, "scripts", f)
        for f in sorted(os.listdir(os.path.join(SKILL_ROOT, "scripts")))
        if f.endswith((".py", ".sh", ".md"))
    ] + [
        os.path.join(SKILL_ROOT, "scripts", "tests", f)
        for f in sorted(os.listdir(os.path.join(SKILL_ROOT, "scripts", "tests")))
        if f.endswith((".py", ".md"))
    ]

    # paths that intentionally point outside the package
    EXTERNAL_PREFIXES = ("evaluate/", "rationale/", "outputexample/", "bestpractice/",
                         "skills/", "docs/", ".claude/")

    @pytest.mark.parametrize("path", PACKAGE_FILES)
    def test_cited_local_paths_exist(self, path):
        text = _read(path)
        # a filename cannot begin with a dot: "`.meta.json`" names a suffix pattern, not a file
        cited = set(re.findall(r"`([A-Za-z0-9][A-Za-z0-9_./-]*\.(?:md|py|sh|json))`", text))
        cited |= set(re.findall(r"\]\(([A-Za-z0-9][A-Za-z0-9_./-]*\.md)[^)]*\)", text))
        missing = []
        for ref in cited:
            if ref.startswith(self.EXTERNAL_PREFIXES) or ref.startswith("http"):
                continue
            candidates = [
                os.path.join(SKILL_ROOT, ref),
                os.path.join(os.path.dirname(path), ref),
                os.path.join(REFS_DIR, os.path.basename(ref)),
                os.path.join(SKILL_ROOT, "scripts", os.path.basename(ref)),
                os.path.join(SKILL_ROOT, "scripts", "tests", os.path.basename(ref)),
            ]
            if not any(os.path.exists(c) for c in candidates):
                missing.append(ref)
        assert not missing, f"{os.path.basename(path)} cites missing local files: {missing}"

    def test_the_resolver_is_not_vacuous(self):
        """Negative control: if the extractor found nothing, the test above would pass on any
        broken link."""
        text = _read(SKILL_MD)
        cited = set(re.findall(r"`([A-Za-z0-9][A-Za-z0-9_./-]*\.(?:md|py|sh|json))`", text))
        assert len(cited) >= 6, f"extractor found only {cited}"

    @pytest.mark.parametrize("external", ["evaluate/"])
    def test_out_of_package_references_are_introduced_as_such(self, external):
        for path in self.PACKAGE_FILES:
            text = _read(path)
            if external not in text:
                continue
            assert re.search(
                r"repositor|not (?:be )?ship|not part of|one level above|repo-level",
                text,
                re.IGNORECASE,
            ), (
                f"{os.path.basename(path)} cites {external} without saying it lives outside "
                f"the installed package"
            )


class TestLineLimits:
    def test_skill_md_under_500_lines(self):
        lines = SKILL_TEXT.count("\n") + 1
        assert lines <= 500, f"SKILL.md has {lines} lines, must be <= 500"

    def test_skill_md_over_100_lines(self):
        lines = SKILL_TEXT.count("\n") + 1
        assert lines >= 100, f"SKILL.md has {lines} lines, seems too short"
