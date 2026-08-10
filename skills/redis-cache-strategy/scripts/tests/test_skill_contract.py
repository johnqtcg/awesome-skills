"""Contract tests for redis-cache-strategy skill."""

import importlib.util
import pathlib
import re
import sys

import pytest

SKILL_DIR = pathlib.Path(__file__).resolve().parents[2]
SKILL_MD = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
REFS_DIR = SKILL_DIR / "references"


def _ref(name: str) -> str:
    return (REFS_DIR / name).read_text(encoding="utf-8")


def _load_linter():
    """See the identical helper in test_golden_scenarios.py for why by-path."""
    path = SKILL_DIR / "scripts" / "lint_cache_docs.py"
    spec = importlib.util.spec_from_file_location("rcs_lint_contract", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["rcs_lint_contract"] = mod
    spec.loader.exec_module(mod)
    return mod


LINT = _load_linter()
ITEMS = LINT.skill_items(SKILL_MD)


def _slug(heading: str) -> str:
    """GitHub's heading-anchor algorithm.

    Lowercase, drop everything that is not a word character, space, or hyphen,
    then map EACH remaining space to a hyphen. Runs are deliberately *not*
    collapsed: dropping the em dash from "3. Acquire — with a fencing token"
    leaves two adjacent spaces, so the real anchor is `...acquire--with...`.
    Collapsing here would make this test bless TOC links that 404 on GitHub.
    """
    s = re.sub(r"[^\w\s-]", "", heading.lower())
    return s.strip().replace(" ", "-")


class TestFrontmatter:
    def test_name(self):
        assert "name: redis-cache-strategy" in SKILL_MD

    def test_description_keywords(self):
        desc_area = SKILL_MD[:800].lower()
        for kw in ["cache-aside", "write-through", "ttl", "stampede", "penetration",
                    "avalanche", "hot key", "consistency"]:
            assert kw in desc_area, f"description missing keyword: {kw}"


class TestMandatoryGates:
    def test_gate_1_context(self):
        assert "Gate 1" in SKILL_MD
        lower = SKILL_MD.lower()
        assert "redis version" in lower
        assert "maxmemory" in lower
        assert "eviction" in lower

    def test_gate_1_stop_proceed(self):
        assert "**STOP**" in SKILL_MD
        assert "**PROCEED**" in SKILL_MD

    def test_gate_2_scope(self):
        assert "Gate 2" in SKILL_MD
        for mode in ["review", "design", "troubleshoot"]:
            assert mode in SKILL_MD.lower()

    def test_gate_3_risk(self):
        assert "Gate 3" in SKILL_MD
        for risk in ["SAFE", "WARN", "UNSAFE"]:
            assert risk in SKILL_MD

    def test_gate_4_completeness(self):
        assert "Gate 4" in SKILL_MD

    def test_all_gates_have_stop(self):
        stop_count = SKILL_MD.count("**STOP**")
        assert stop_count >= 3


class TestDepthSelection:
    def test_three_depths(self):
        for depth in ["Lite", "Standard", "Deep"]:
            assert depth in SKILL_MD

    def test_force_standard_signals(self):
        lower = SKILL_MD.lower()
        for signal in ["write-behind", "distributed lock", "hot key"]:
            assert signal in lower, f"missing signal: {signal}"

    def test_reference_loading_by_depth(self):
        assert "cache-patterns.md" in SKILL_MD
        assert "cache-failure-modes.md" in SKILL_MD


class TestDegradationModes:
    def test_four_modes_defined(self):
        for mode in ["Full", "Degraded", "Minimal", "Planning"]:
            assert mode in SKILL_MD

    def test_never_fabricate(self):
        lower = SKILL_MD.lower()
        assert "never" in lower and ("fabricate" in lower or "claim" in lower)

    def test_consistency_sla_warning(self):
        lower = SKILL_MD.lower()
        assert "staleness" in lower or "consistency" in lower


class TestCacheStrategyChecklist:
    def test_subsection_count(self):
        for sub in ["5.1", "5.2", "5.3", "5.4"]:
            assert sub in SKILL_MD

    def test_pattern_keywords(self):
        for kw in ["cache-aside", "write-through", "write-behind"]:
            assert kw in SKILL_MD.lower()

    def test_ttl_jitter(self):
        lower = SKILL_MD.lower()
        assert "ttl" in lower and "jitter" in lower

    def test_stampede(self):
        lower = SKILL_MD.lower()
        assert "stampede" in lower and "singleflight" in lower

    def test_penetration(self):
        lower = SKILL_MD.lower()
        assert "penetration" in lower and ("bloom" in lower or "null" in lower)

    def test_distributed_lock(self):
        lower = SKILL_MD.lower()
        assert "setnx" in lower or "distributed lock" in lower

    def test_degradation(self):
        lower = SKILL_MD.lower()
        assert "cache-down" in lower or "degradation" in lower


class TestPatternSelection:
    def test_selection_table(self):
        lower = SKILL_MD.lower()
        assert "cache-aside" in lower and "write-through" in lower and "write-behind" in lower

    def test_warmup(self):
        lower = SKILL_MD.lower()
        assert "warmup" in lower or "warm" in lower


class TestAntiExamples:
    """AE-1..AE-13 live in the reference; SKILL.md keeps only a recognition index."""

    def _ae_ids(self, text: str, prefix: str) -> list[str]:
        return re.findall(rf"^{prefix}(AE-\d+)", text, re.M)

    def test_reference_holds_every_anti_example(self):
        ids = self._ae_ids(_ref("cache-anti-examples.md"), r"## ")
        assert ids == [f"AE-{i}" for i in range(1, 14)], \
            f"anti-examples are not AE-1..AE-13 in order: {ids}"

    def test_reference_keeps_wrong_right_pairs(self):
        content = _ref("cache-anti-examples.md")
        assert content.count("WRONG") >= 6, "the wrong half of the pairs went missing"
        assert content.count("RIGHT") >= 5

    def test_skill_index_covers_every_anti_example(self):
        """The index is what a review reads before deciding to load the file."""
        indexed = set(re.findall(r"\|\s*(AE-\d+)\s*\|", SKILL_MD))
        assert indexed == {f"AE-{i}" for i in range(1, 14)}, \
            f"§7 index does not cover every anti-example: missing " \
            f"{sorted({f'AE-{i}' for i in range(1, 14)} - indexed)}"

    def test_skill_index_maps_each_to_a_real_item(self):
        """An anti-example that maps to no §5 item cannot change any score."""
        all_ids = {f"{p}{n}" for p, nums in ITEMS.items() for n in nums}
        rows = re.findall(r"\|\s*AE-\d+\s*\|[^|\n]*\|[^|\n]*\|\s*([CSH]\d+)\s*\|", SKILL_MD)
        assert len(rows) == 13, f"§7 index has {len(rows)} rows with an item column, want 13"
        unknown = set(rows) - all_ids
        assert not unknown, f"§7 index references §5 items that do not exist: {sorted(unknown)}"

    def test_ttl_anti_example(self):
        assert "immortal" in _ref("cache-anti-examples.md").lower()

    def test_extended_ref(self):
        assert "cache-anti-examples.md" in SKILL_MD


class TestScorecard:
    """§8 scores §5's items and nothing else.

    The old version of this class asserted `"4 of 5" in SKILL_MD` and
    `"X/12" in SKILL_MD or "PASS/FAIL" in SKILL_MD`. Both were satisfied by
    text that had nothing to do with the scoring rule — the second passed on
    `PASS/FAIL` appearing anywhere, so the `X/12` half had been stale through
    two renumberings without a single red test. Every assertion below reads a
    structure and checks a value.
    """

    def _section(self, num: str) -> str:
        m = re.search(rf"^## §{num}\b.*?(?=^## §{int(num) + 1}\b|\Z)", SKILL_MD, re.S | re.M)
        assert m, f"§{num} section not found"
        return m.group(0)

    def test_tiers_have_item_ranges_matching_section_5(self):
        body = self._section("8")
        for tier, prefix in (("Critical", "C"), ("Standard", "S"), ("Hygiene", "H")):
            m = re.search(rf"\|\s*\*\*{tier}\*\*\s*\|[^|\n]*?{prefix}1\s*[–—-]\s*{prefix}?(\d+)",
                          body)
            assert m, f"§8 has no {prefix}1–{prefix}n range for the {tier} tier"
            assert int(m.group(1)) == max(ITEMS[prefix]), (
                f"§8 {tier} covers {prefix}1–{prefix}{m.group(1)} but §5 defines "
                f"{prefix}1–{prefix}{max(ITEMS[prefix])}")

    def test_critical_tier_tolerates_nothing(self):
        body = self._section("8")
        row = re.search(r"\|\s*\*\*Critical\*\*\s*\|[^|\n]*\|([^|\n]*)\|", body)
        assert row, "§8 Critical row not found"
        rule = row.group(1).lower()
        assert "every" in rule and "pass" in rule, \
            f"§8 Critical tier must require every item to PASS, got {rule.strip()!r}"
        assert "warn" in rule, "§8 must say explicitly that WARN also fails the Critical tier"

    def test_lower_tiers_declare_a_numeric_threshold(self):
        body = self._section("8")
        for tier in ("Standard", "Hygiene"):
            row = re.search(rf"\|\s*\*\*{tier}\*\*\s*\|[^|\n]*\|([^|\n]*)\|", body)
            assert row, f"§8 {tier} row not found"
            assert re.search(r"\d+\s*%", row.group(1)), \
                f"§8 {tier} tier has no percentage threshold: {row.group(1).strip()!r}"

    def test_denominator_is_dynamic(self):
        body = self._section("8")
        assert "N/A" in body and "NOT SCOREABLE" in body
        assert re.search(r"leave \*both\* sides|removed from both|dynamic denominator",
                         body, re.I), "§8 never states that N/A and NOT SCOREABLE leave the fraction"

    def test_unscoreable_critical_cannot_pass(self):
        """The one rule that stops `we could not check it` from reading as `it is fine`."""
        body = self._section("8")
        m = re.search(r"\*\*INCOMPLETE\*\*\s*—([^\n]*(?:\n(?!\s*-\s\*\*)[^\n]*)*)", body)
        assert m, "§8 does not define an INCOMPLETE verdict"
        clause = m.group(1)
        assert "NOT" in clause and "SCOREABLE" in clause and "Critical" in clause, \
            f"INCOMPLETE is not tied to a NOT SCOREABLE Critical item: {clause.strip()!r}"
        pass_rule = re.search(r"\*\*PASS\*\*\s*—([^\n]*)", body)
        assert pass_rule and "NOT SCOREABLE" in pass_rule.group(1), \
            "§8 PASS does not exclude a NOT SCOREABLE Critical item"

    def test_every_item_must_be_written_down(self):
        body = self._section("8")
        assert re.search(r"[Ee]very item gets a row", body), \
            "§8 does not require a per-item verdict row — an unrecorded item is an invisible FAIL"

    def test_section_8_declares_no_items_of_its_own(self):
        assert not re.search(r"^- \[ \]", self._section("8"), re.M), \
            "§8 reintroduced its own checklist — that duplication is the bug being fixed"


class TestOutputContract:
    def test_nine_sections(self):
        for section in ["9.1", "9.2", "9.3", "9.4", "9.5", "9.6", "9.7", "9.8", "9.9"]:
            assert section in SKILL_MD

    def test_uncovered_risks_mandatory(self):
        lower = SKILL_MD.lower()
        assert "never empty" in lower or "mandatory" in lower

    def test_volume_rules(self):
        assert "volume" in SKILL_MD.lower()

    def test_scorecard_in_output(self):
        lower = SKILL_MD.lower()
        assert "scorecard" in lower and "data basis" in lower


class TestReferenceFiles:
    def test_cache_patterns_exists(self):
        content = _ref("cache-patterns.md")
        assert len(content.splitlines()) >= 80

    def test_cache_patterns_keywords(self):
        content = _ref("cache-patterns.md").lower()
        for kw in ["cache-aside", "write-through", "write-behind", "dual-write"]:
            assert kw in content

    def test_failure_modes_exists(self):
        content = _ref("cache-failure-modes.md")
        assert len(content.splitlines()) >= 80

    def test_failure_modes_keywords(self):
        content = _ref("cache-failure-modes.md").lower()
        for kw in ["stampede", "penetration", "avalanche", "hot key"]:
            assert kw in content

    def test_anti_examples_exists(self):
        content = _ref("cache-anti-examples.md")
        assert len(content.splitlines()) >= 80

    def test_anti_examples_numbering(self):
        content = _ref("cache-anti-examples.md")
        assert "AE-7" in content
        ae_count = sum(1 for line in content.split("\n") if "## AE-" in line)
        assert ae_count >= 5

    def test_all_refs_mentioned_in_skill(self):
        for f in REFS_DIR.glob("*.md"):
            assert f.name in SKILL_MD, f"{f.name} not in SKILL.md"


class TestLineCount:
    def test_max_lines(self):
        """SKILL.md is loaded on every invocation, so its size is a real cost.

        Budget raised 420 → 440 on 2026-08-10, when §5 went from 14 loose items
        to 21 tiered ones with explicit scoring semantics. It was paid for, not
        waived: AE-1..AE-6 (≈62 lines of Go) moved to
        `references/cache-anti-examples.md`, and §8's duplicate checklist was
        deleted outright. If this needs raising again, move content out first.
        """
        lines = len(SKILL_MD.splitlines())
        assert lines <= 440, f"SKILL.md is {lines} lines (budget: 440)"


class TestEvalResultsAreNotClaimedWithoutData:
    """An A/B claim in the eval report must be backed by a run artifact.

    The harnesses exist and are calibrated, but the runs themselves have not
    executed (the nested CLI is unauthenticated in this environment) and both
    exit 3 INCOMPLETE. That gap is currently held by a sentence in the report,
    and a sentence is not a mechanism: the next person to edit §9.5 can delete
    the caveat, or paste in a number, and nothing objects.

    These tests make the claim and the evidence rise and fall together. They
    also pass in the opposite direction: once a real run writes the JSON, the
    report is *required* to cite it.
    """

    REPORTS = (
        SKILL_DIR.parents[1] / "evaluate" / "redis-cache-strategy-skill-eval-report.md",
        SKILL_DIR.parents[1] / "evaluate" / "redis-cache-strategy-skill-eval-report.zh-CN.md",
    )
    ARTIFACTS = {
        "model_eval": SKILL_DIR / "scripts" / "tests" / "model_eval_last_run.json",
        "trigger_eval": SKILL_DIR / "scripts" / "tests" / "trigger_eval_last_run.json",
    }
    # Shapes that assert a measured outcome, as opposed to describing the tool.
    RESULT_CLAIM = re.compile(
        r"arm\s*B\s*(?:scored|reached|beat)|delta\s*[+-]?\d|"
        r"recall\s*[:=]?\s*0?\.\d|precision\s*[:=]?\s*0?\.\d|"
        r"召回率?\s*[:=]?\s*0?\.\d|精确率?\s*[:=]?\s*0?\.\d",
        re.I,
    )

    @pytest.mark.parametrize("report", REPORTS, ids=lambda p: p.name)
    def test_report_claims_no_result_without_an_artifact(self, report):
        if not report.exists():
            pytest.skip(f"{report.name} not present")
        have = {n for n, p in self.ARTIFACTS.items() if p.exists()}
        claims = self.RESULT_CLAIM.findall(report.read_text(encoding="utf-8"))
        if not have:
            assert not claims, (
                f"{report.name} states an eval result ({claims[:3]}) but neither "
                f"{[p.name for p in self.ARTIFACTS.values()]} exists. Run the eval, "
                f"or remove the claim — an unbacked number is the one thing an "
                f"evaluation report must never contain.")

    @pytest.mark.parametrize("name", sorted(ARTIFACTS))
    def test_artifact_is_cited_once_it_exists(self, name):
        if not self.ARTIFACTS[name].exists():
            pytest.skip(f"{name} has not been run yet — the gap is declared in §9.5")
        for report in self.REPORTS:
            if report.exists():
                assert self.RESULT_CLAIM.search(report.read_text(encoding="utf-8")), (
                    f"{name} produced a result but {report.name} reports no numbers "
                    f"— the report is now behind the evidence")

    def test_the_open_gap_is_stated_in_both_reports(self):
        """While the artifacts are absent, both languages must say so."""
        if any(p.exists() for p in self.ARTIFACTS.values()):
            pytest.skip("an eval has run; the caveat no longer applies")
        for report in self.REPORTS:
            if not report.exists():
                continue
            text = report.read_text(encoding="utf-8")
            assert "INCOMPLETE" in text and re.search(r"not (?:run|measured|execute)|未|没有",
                                                      text), \
                f"{report.name} does not state that the A/B run has not happened"


class TestReferenceTOCs:
    """Every reference over 100 lines needs a table of contents.

    Asserted against the file's real `## ` headings rather than against the
    presence of the words "table of contents" — a TOC that has drifted from the
    headings is worse than none, because it sends a reader to an anchor that
    does not exist.
    """

    LONG_REF_MIN_LINES = 100

    @pytest.mark.parametrize("name", sorted(p.name for p in REFS_DIR.glob("*.md")))
    def test_long_reference_has_accurate_toc(self, name):
        content = _ref(name)
        headings = re.findall(r"^## (.+)$", content, re.M)
        if len(content.splitlines()) < self.LONG_REF_MIN_LINES:
            pytest.skip(f"{name} is short enough to read without a TOC")
        assert headings, f"{name} has no `## ` headings to index"

        # The TOC is the run of list links before the first `## ` heading.
        head = content.split("\n## ", 1)[0]
        links = re.findall(r"^- \[(.+?)\]\(#([\w-]+)\)$", head, re.M)
        assert links, f"{name} is {len(content.splitlines())} lines and has no TOC"

        assert [t for t, _ in links] == headings, (
            f"{name} TOC does not match its headings.\n"
            f"  TOC:      {[t for t, _ in links]}\n"
            f"  headings: {headings}")
        for title, anchor in links:
            assert anchor == _slug(title), \
                f"{name}: TOC anchor #{anchor} does not match heading {title!r} (#{_slug(title)})"


class TestCrossFileConsistency:
    def test_cache_aside_in_patterns(self):
        assert "cache-aside" in _ref("cache-patterns.md").lower()

    def test_singleflight_in_failure_modes(self):
        assert "singleflight" in _ref("cache-failure-modes.md").lower()

    def test_bloom_in_failure_modes(self):
        assert "bloom" in _ref("cache-failure-modes.md").lower()

    def test_ttl_jitter_in_failure_modes(self):
        content = _ref("cache-failure-modes.md").lower()
        assert "jitter" in content

    def test_keys_command_in_anti_examples(self):
        content = _ref("cache-anti-examples.md").lower()
        assert "keys" in content or "scan" in content

    def test_degradation_in_skill(self):
        assert "degradation" in SKILL_MD.lower()