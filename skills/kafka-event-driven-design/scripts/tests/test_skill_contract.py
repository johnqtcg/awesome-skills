"""Contract tests for kafka-event-driven-design.

Structure tests only prove sections exist; they cannot tell correct advice from
its inverse. They are kept here because deleting a section IS a regression worth
catching — but the semantic load is carried by test_golden_scenarios.py (linter
+ verified-fact table) and scripts/mutation_sweep.py.

Where a claim is checkable, this file asserts the claim rather than a keyword.
"""

from __future__ import annotations

import importlib.util
import json
import math
import pathlib
import re
import subprocess
import sys

import pytest

SKILL_DIR = pathlib.Path(__file__).resolve().parents[2]
SKILL_MD = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
REFS_DIR = SKILL_DIR / "references"
SCRIPTS_DIR = SKILL_DIR / "scripts"

# skill-creator guidance caps an always-loaded SKILL.md at "under 500 lines"; a
# gate set at `<= 500` was reading the cap as a target and the file sat at exactly
# 500. The budget only ever ratchets down: raising it to accommodate new prose is
# the regression this gate exists to catch. Move detail into references/ instead —
# the anti-example bodies and the duplicated tier checklists went that way.
LINE_BUDGET = 435


def _ref(name: str) -> str:
    return (REFS_DIR / name).read_text(encoding="utf-8")


def _frontmatter() -> str:
    """The YAML frontmatter block, whitespace-normalised.

    Scoped to the real block rather than the first N characters: a fixed slice
    silently starts checking body prose the moment the description grows.
    """
    parts = SKILL_MD.split("---", 2)
    assert len(parts) >= 3, "SKILL.md has no frontmatter block"
    return re.sub(r"\s+", " ", parts[1])


def _client_defaults_table():
    """(header cells, {row label: cells}) for the client-defaults table in
    version-client-matrix.md §3.

    Parsed as data so per-client assertions can target one cell. Substring checks
    over the whole file cannot distinguish "franz-go has a documented default"
    from "franz-go is mentioned in a footnote".
    """
    lines = _ref("version-client-matrix.md").splitlines()
    for i, line in enumerate(lines):
        if line.startswith("|") and "**Java**" in line and "franz-go" in line:
            header = [c.strip() for c in line.strip().strip("|").split("|")]
            rows = {}
            for follow in lines[i + 2:]:          # +2 skips the |---| separator
                if not follow.startswith("|"):
                    break
                cells = [c.strip() for c in follow.strip().strip("|").split("|")]
                rows[cells[0]] = cells
            return header, rows
    return None, {}


def _min_context_rows() -> dict[str, str]:
    """{scored-item cell: minimum-context cell} from Gate 1's minimum-context
    table. Parsed as data so a test can ask what gates *one* item rather than
    grepping the file for a sentence."""
    block = re.search(
        r"^\|\s*Scored item\s*\|\s*Minimum context\s*\|.*?(?:\n\n|\Z)",
        SKILL_MD, re.S | re.M)
    if not block:
        return {}
    rows = {}
    for line in block.group(0).splitlines()[2:]:      # skip header + |---|
        if not line.startswith("|"):
            break
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 2:
            rows[cells[0]] = cells[1]
    return rows


def _tier_of_checklist_items() -> dict[int, str]:
    """{§5 item number: tier} from the *(Tier)* tag on each checklist item."""
    return {int(n): t.strip().split()[0].lower()
            for n, t in re.findall(r"^(\d+)\.\s+\*\*.*?\*\*\s*\*\(([^)]+)\)\*",
                                   SKILL_MD, re.M)}


def _tier_table_items() -> dict[str, set[int]]:
    """{tier: {§5 item numbers}} from §8's tier table."""
    block = re.search(r"^\|\s*Tier\s*\|\s*§5 items\s*\|.*?(?:\n\n|\Z)",
                      SKILL_MD, re.S | re.M)
    assert block, "§8 tier table not found"
    out: dict[str, set[int]] = {}
    for line in block.group(0).splitlines()[2:]:
        if not line.startswith("|"):
            break
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        tier = cells[0].strip("*_ ").lower()
        out[tier] = {int(n) for n in re.findall(r"\b(\d+)\s+\w", cells[1])}
    return out


def _span(start: str, end: str) -> str:
    """The SKILL.md text between two literal markers, for scoping a guard to one
    passage. A whole-file search is satisfiable by any unrelated match."""
    i = SKILL_MD.index(start)
    j = SKILL_MD.index(end, i)
    return SKILL_MD[i:j]


def _load_by_path(name: str):
    """Sibling scripts are loaded by path, not imported.

    This repo runs pytest with `--import-mode=importlib`, under which a bare
    `import lint_kafka_docs` from a test file does not resolve. Registering in
    sys.modules before exec_module is also required — a dataclass defined in a
    module that is not yet registered fails to resolve its own annotations.
    """
    path = SCRIPTS_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_linter():
    return _load_by_path("lint_kafka_docs")


def _load_model_eval():
    return _load_by_path("model_eval")


LINTER = _load_linter()
REF_FILES = ["event-schema-patterns.md", "consumer-failure-modes.md",
             "consumer-anti-examples.md", "version-client-matrix.md"]

# Backticked link to a sibling reference file, with or without the
# "references/" prefix. Upstream provenance paths (docs/operations/foo.md) carry
# a different directory prefix and so do not match.
SIBLING_LINK = re.compile(r"`(?:references/)?([a-z0-9-]+\.md)`")


class TestFrontmatter:
    def test_name(self):
        assert "name: kafka-event-driven-design" in SKILL_MD

    def test_description_keywords(self):
        desc = _frontmatter().lower()
        for kw in ["kafka", "partition", "consumer group", "schema", "idempotent",
                   "dead letter", "exactly-once"]:
            assert kw in desc, f"description missing keyword: {kw}"

    def test_description_excludes_cluster_ops(self):
        """Trigger precision: an unqualified 'ALWAYS use' pulls in broker/ops
        questions this skill deliberately does not answer."""
        desc = _frontmatter().lower()
        assert "not for" in desc, "description states no negative scope"
        for kw in ["broker", "kraft", "connect"]:
            assert kw in desc, f"description does not exclude: {kw}"

    def test_scope_section_matches_description(self):
        """The out-of-scope table must not contradict the frontmatter."""
        for kw in ["Broker sizing", "KRaft", "Kafka Streams / Kafka Connect",
                   "MirrorMaker"]:
            assert kw in SKILL_MD, f"§1 out-of-scope table missing: {kw}"


class TestMandatoryGates:
    def test_gate_1_context(self):
        assert "Gate 1" in SKILL_MD
        lower = SKILL_MD.lower()
        for item in ["kafka version", "client library", "group.protocol",
                     "ordering", "delivery", "data sensitivity"]:
            assert item in lower, f"Gate 1 missing context item: {item}"

    def test_gate_1_offers_4x(self):
        """The version list itself must reach 4.x — not merely mention 4.0 in
        prose elsewhere on the row."""
        m = re.search(r"\*\*Kafka version\*\*\s*\(([^)]*)\)", SKILL_MD)
        assert m, "Gate 1 has no parenthesised Kafka version list"
        assert "4." in m.group(1), f"version list stops early: {m.group(1)!r}"

    def test_gates_have_stop_and_proceed(self):
        assert SKILL_MD.count("**STOP**") >= 3
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

    def test_version_unknown_blocks_config_verdicts(self):
        """The reviewer must refuse to score durability blind, not guess."""
        assert "not scoreable" in SKILL_MD.lower()
        assert _min_context_rows(), "Gate 1 has no minimum-context table"


class TestMinimumContextGating:
    """Gate 1, §4's hard rule and §8's NOT SCOREABLE row must express *one*
    gating policy.

    They previously did not: §2 said stop when broker version **and** client are
    both unknown, §4 said a verdict needs both, and §8's row repeated the "both
    unknown" form — three different rules for the same decision, and all three
    conflated four independent facts into one global gate. These tests read the
    table as data and hold each site to it.
    """

    # Hand-written, NOT read out of SKILL.md: which fact must gate which item.
    # Keyed by a distinctive substring of the row label so rewording the prose
    # around it does not break the test, but re-pointing a row does.
    EXPECTED_GATE = {
        "Producer durability": ("client library", ("broker version",)),
        "Consumer-protocol keys": ("group.protocol", ()),
        "Feature availability": ("broker version", ("client library",)),
    }

    def test_table_gates_each_item_on_its_own_fact(self):
        rows = _min_context_rows()
        assert rows, "Gate 1 has no 'Minimum context per scored item' table"
        for needle, (required, forbidden) in self.EXPECTED_GATE.items():
            row = next((v for k, v in rows.items() if needle in k), None)
            assert row, f"no minimum-context row for {needle!r}: {list(rows)}"
            assert required.lower() in row.lower(), \
                f"{needle} must be gated on {required!r}; table says {row!r}"
            for bad in forbidden:
                assert bad.lower() not in row.lower(), \
                    f"{needle} must NOT require {bad!r} as well; table says {row!r}"

    def test_table_has_an_ungated_row(self):
        """The row that stops a global version gate creeping back: most items
        need no version at all, and must still be scored when one is missing."""
        rows = _min_context_rows()
        ungated = [k for k, v in rows.items()
                   if re.fullmatch(r"\*\*none\*\*|none", v.strip(), re.I)]
        assert ungated, \
            f"no 'minimum context: none' row — every item now looks version-gated: {rows}"

    @pytest.mark.parametrize("label,start,end", [
        ("Gate 1 STOP", "**STOP**: Asked to score an item", "**PROCEED**: At least event type"),
        ("§4 hard rule", "**Hard rule**: Never give a config verdict", "---\n\n## §5"),
        ("§8 NOT SCOREABLE row", "| **NOT SCOREABLE** |", "\n\nThe PASS/WARN split"),
    ])
    def test_no_site_reinstates_the_global_and_gate(self, label, start, end):
        """Scoped per site. A whole-file search would pass on any one site being
        correct, which is exactly how the three drifted apart."""
        text = _span(start, end).lower()
        for bad in (r"\bneither\b.*\bnor\b",
                    r"broker version\s*\*?\*?and\*?\*?\s*client",
                    r"version\s+and\s+client\s+(?:are\s+)?unknown",
                    r"\bboth\b[^.]{0,40}\bunknown\b"):
            assert not re.search(bad, text), \
                f"{label} reinstates the global both-unknown gate ({bad!r}): {text[:200]!r}"

    def test_each_site_defers_to_the_table(self):
        for label, start, end in (
            ("§4 hard rule", "**Hard rule**: Never give a config verdict", "---\n\n## §5"),
            ("§8 NOT SCOREABLE row", "| **NOT SCOREABLE** |", "\n\nThe PASS/WARN split"),
        ):
            text = _span(start, end).lower()
            assert "minimum context" in text, \
                f"{label} does not point at the minimum-context table: {text[:200]!r}"

    def test_not_scoreable_is_scoped_to_the_item(self):
        """An unscoreable item must not black out the rest of the review."""
        row = _span("| **NOT SCOREABLE** |", "\n\nThe PASS/WARN split").lower()
        assert "only that item" in row or "and only that item" in row, \
            f"§8 NOT SCOREABLE row does not scope the block to one item: {row!r}"


class TestDepthSelection:
    def test_three_depths(self):
        for depth in ["Lite", "Standard", "Deep"]:
            assert depth in SKILL_MD

    def test_force_standard_signals(self):
        lower = SKILL_MD.lower()
        for signal in ["schema evolution", "exactly-once", "compacted",
                       "group.protocol=consumer", "pii"]:
            assert signal in lower, f"missing force-Standard signal: {signal}"

    def test_version_matrix_always_loadable(self):
        assert "version-client-matrix.md" in SKILL_MD
        assert "**Before scoring a version-sensitive configuration item" in SKILL_MD

    def test_quick_reference_does_not_globalise_the_version_gate(self):
        """The header used to close with "a verdict given without knowing the
        broker version and client library is a guess" — true of producer
        durability, false of most of the checklist, and a direct contradiction of
        §2's per-item table sitting forty lines below it."""
        header = _span("## Quick Reference", "\n---\n\n## §1 Scope").lower()
        for bad in (r"a verdict given without", r"\bany\s+verdict\b",
                    r"broker version and client library is a guess"):
            assert not re.search(bad, header), \
                f"Quick Reference reinstates a global version gate ({bad!r})"
        assert "version-sensitive" in header, \
            "Quick Reference must scope the matrix load to version-sensitive items"


class TestDegradationModes:
    def test_four_modes_defined(self):
        for mode in ["Full", "Degraded", "Minimal", "Planning"]:
            assert mode in SKILL_MD

    def test_hard_rules_present(self):
        assert SKILL_MD.count("**Hard rule**") >= 3

    def test_no_fabricated_numbers_rule(self):
        assert "Never state a numeric threshold you did not derive" in SKILL_MD

    def test_eos_requires_consumer_side_settings(self):
        assert "read_committed" in SKILL_MD
        assert "enable.auto.commit=false" in SKILL_MD


class TestDesignChecklist:
    def test_subsection_count(self):
        for sub in ["5.1", "5.2", "5.3", "5.4", "5.5"]:
            assert sub in SKILL_MD

    def test_numbered_items_are_sequential(self):
        nums = [int(m) for m in re.findall(r"^(\d+)\.\s+\*\*", SKILL_MD, re.MULTILINE)]
        assert nums, "no numbered checklist items found"
        assert nums == list(range(1, len(nums) + 1)), f"checklist numbering broken: {nums}"

    def test_governance_items_present(self):
        assert "Sensitive data in events is classified and controlled" in SKILL_MD
        assert "Topic ownership and consumer inventory recorded" in SKILL_MD

    @pytest.mark.parametrize("needle", [
        "partition key", "Schema Registry", "consumer lag", "min.insync.replicas",
    ])
    def test_core_topics_covered(self, needle):
        assert needle.lower() in SKILL_MD.lower()


class TestPartitionDesign:
    def test_hot_partition_section(self):
        lower = SKILL_MD.lower()
        assert "hot partition" in lower or "skewed" in lower

    def test_ordering_tradeoff_stated(self):
        assert "You cannot have per-entity Kafka-native ordering" in SKILL_MD

    def test_global_ordering_has_no_fixed_threshold(self):
        assert "no fixed events/sec threshold" in SKILL_MD
        assert "p99_processing_time" in SKILL_MD


class TestAntiExamples:
    """The WRONG/RIGHT pairs live in the reference file; SKILL.md keeps only the
    index. These check the index is complete and the pairs really are there —
    "moved to references" must not become "quietly deleted"."""

    @staticmethod
    def _catalogue() -> list[int]:
        return [int(n) for n in re.findall(r"^## AE-(\d+)",
                                           _ref("consumer-anti-examples.md"), re.M)]

    def test_extended_ref(self):
        assert "consumer-anti-examples.md" in SKILL_MD

    def test_numbering_contiguous_from_one(self):
        nums = self._catalogue()
        assert nums, "no anti-examples found in the reference file"
        assert nums == list(range(1, len(nums) + 1)), f"AE numbering broken: {nums}"
        assert max(nums) >= 17, "Kafka 4.x / fencing / PII anti-examples missing"

    # Two writing styles coexist in the catalogue: `// WRONG` … `// RIGHT` inside
    # one fence, and a fenced problem followed by a `**Right approach:**` block.
    # Declared as data so the test states what it accepts instead of implying it.
    PROBLEM_MARKERS = ("WRONG", "SUSPECT", "BAD:")
    REMEDY_MARKERS = ("RIGHT", "Right approach", "Fix:")

    def test_every_anti_example_has_both_arms(self):
        """Per section, not per file. A whole-file count of "WRONG" is satisfied
        by six loud entries while eleven others quietly lose their remedy."""
        content = _ref("consumer-anti-examples.md")
        parts = re.split(r"(?m)^## (AE-\d+[^\n]*)$", content)
        sections = dict(zip(parts[1::2], parts[2::2]))
        assert len(sections) >= 17, f"only {len(sections)} anti-examples parsed"
        for title, body in sections.items():
            assert any(m in body for m in self.PROBLEM_MARKERS), \
                f"{title[:40]}: no problem arm ({self.PROBLEM_MARKERS})"
            assert any(m in body for m in self.REMEDY_MARKERS), \
                f"{title[:40]}: no remedy arm ({self.REMEDY_MARKERS})"

    def test_skill_index_covers_every_catalogue_entry(self):
        """Every AE number in the reference must be reachable from SKILL.md's
        index — as its own row or inside a `AE-7 … AE-11` range."""
        section = _span("## §7 Anti-Examples", "\n---\n\n## §8")
        singles = {int(n) for n in re.findall(r"\bAE-(\d+)\b", section)}
        covered = set(singles)
        for lo, hi in re.findall(r"AE-(\d+)\s*(?:…|\.\.\.)\s*AE-(\d+)", section):
            covered |= set(range(int(lo), int(hi) + 1))
        missing = set(self._catalogue()) - covered
        assert not missing, f"§7 index does not reach AE numbers: {sorted(missing)}"

    def test_skill_index_does_not_overreach(self):
        """The mirror of the above: an index entry with no catalogue entry
        behind it sends the reader to a section that does not exist."""
        section = _span("## §7 Anti-Examples", "\n---\n\n## §8")
        cited = {int(n) for n in re.findall(r"\bAE-(\d+)\b", section)}
        assert cited <= set(self._catalogue()), \
            f"§7 cites anti-examples that do not exist: {sorted(cited - set(self._catalogue()))}"


class TestScorecard:
    """Anchored on the §8 tables, not on their prose.

    The previous version asserted exact sentences ("**N/A** requires a stated
    reason") and broke the moment §8 was reworded — a guard that fires on
    rephrasing but would happily pass an *inverted* rule is worse than no guard.
    These read the verdict table and the worked-example table as data, and compare
    against expectations written out by hand below.
    """

    # Hand-written, NOT derived from SKILL.md: what each verdict must do to the
    # numerator/denominator. Reword the doc freely; invert it and this fires.
    VERDICT_CREDIT = {
        "PASS": "credit",
        "WARN": "credit",
        "FAIL": "no credit",
        "N/A": "removed",
        "NOT SCOREABLE": "removed",
    }
    # ceil(0.8 × A) computed by hand, so the test does not merely agree with
    # whatever the doc happens to tabulate.
    STANDARD_EXAMPLES = {7: 6, 5: 4, 4: 4, 3: 3, 0: 0}

    @staticmethod
    def _verdict_rows():
        """{verdict: 'Counts as' cell} from the §8 verdict table."""
        pattern = re.compile(
            r"^\|\s*\*\*(PASS|WARN|FAIL|N/A|NOT SCOREABLE)\*\*\s*\|[^|]*\|(.*?)\|\s*$")
        return {m.group(1): m.group(2).strip()
                for line in SKILL_MD.splitlines()
                if (m := pattern.match(line))}

    def test_tiers(self):
        lower = SKILL_MD.lower()
        assert "critical" in lower and "standard" in lower and "hygiene" in lower

    def test_all_five_verdicts_defined(self):
        rows = self._verdict_rows()
        assert set(rows) == set(self.VERDICT_CREDIT), \
            f"§8 verdict table defines {sorted(rows)}, expected {sorted(self.VERDICT_CREDIT)}"

    def test_verdict_credit_semantics_not_inverted(self):
        rows = self._verdict_rows()
        for verdict, expected in self.VERDICT_CREDIT.items():
            cell = rows[verdict].lower()
            if expected == "credit":
                assert "credit" in cell and "no credit" not in cell, \
                    f"{verdict} must count as credit; table says {rows[verdict]!r}"
            elif expected == "no credit":
                assert "no credit" in cell, \
                    f"{verdict} must NOT count as credit; table says {rows[verdict]!r}"
            else:
                assert "removed" in cell, \
                    f"{verdict} must leave the denominator; table says {rows[verdict]!r}"

    def test_not_scoreable_forces_overall_not_scoreable(self):
        """Bound to the NOT SCOREABLE row itself, so an unrelated mention of
        'not scoreable' elsewhere in §8 cannot satisfy it."""
        cell = self._verdict_rows()["NOT SCOREABLE"].lower()
        assert "forces" in cell and "not scoreable" in cell, \
            f"NOT SCOREABLE row must force the overall verdict; says {cell!r}"

    def test_worked_examples_match_the_stated_formula(self):
        """The worked-example table, the tier table's ratio, and hand-computed
        ceil() must all agree. Catches a doc that drifts its examples while
        keeping the formula, or vice versa."""
        ratio = re.search(
            r"\|\s*Standard\s*\|[^|]*\|\s*7\s*\|\s*`C ≥ ceil\(([\d.]+) × A\)`", SKILL_MD)
        assert ratio, "§8 tier table no longer states Standard's ceil ratio"
        r = float(ratio.group(1))
        assert r == 0.8, f"Standard ratio is now {r}; STANDARD_EXAMPLES needs recomputing"

        block = re.search(r"^\|\s*Applicable `A`\s*\|.*?(?:\n\n|\Z)",
                          SKILL_MD, re.S | re.M)
        assert block, "§8 worked-example table not found"
        examples = {int(a): int(c) for a, c in
                    re.findall(r"^\|\s*(\d+)\s*\|\s*(\d+)\s*\|", block.group(0), re.M)}
        assert examples == self.STANDARD_EXAMPLES, \
            f"worked examples are {examples}, expected {self.STANDARD_EXAMPLES}"
        for a, c in examples.items():
            assert c == math.ceil(r * a), \
                f"A={a}: doc says C={c}, ceil({r}×{a})={math.ceil(r * a)}"

    def test_output_contract_uses_C_over_A_not_fixed_denominators(self):
        """§9's summary template must not reintroduce `/3` `/5` `/4` — the fixed
        denominators are exactly the ambiguity §8's arithmetic removes, since A
        shrinks with every N/A and NOT SCOREABLE."""
        summary = re.search(r"\*\*Scorecard summary\*\*.*?```(.*?)```", SKILL_MD, re.S)
        assert summary, "§9 scorecard summary template not found"
        body = summary.group(1)
        assert "C/A" in body, "§9 summary must report each tier as C/A"
        for bad in ("/3", "/5", "/4"):
            assert bad not in body, \
                f"§9 summary reintroduces fixed denominator {bad!r}: {body!r}"

    # Hand-written: which §5 items carry which weight. Derived from neither
    # table, so the two drifting apart — or either drifting from intent — fires.
    EXPECTED_TIERS = {
        "critical": {5, 8, 9, 11},
        "standard": {6, 7, 10, 12, 13, 14, 16},
        "hygiene": {1, 2, 3, 4, 15, 17},
    }
    N_ITEMS = 17

    def test_tier_table_matches_intent(self):
        assert _tier_table_items() == self.EXPECTED_TIERS, \
            f"§8 tier table now reads {_tier_table_items()}"

    def test_no_item_is_left_unscored(self):
        """An item outside the scorecard is a hole, not a simplification: the
        finding lands in §9 and the verdict still comes out PASS. Atomicity
        (item 8) sat there while KAFKA-015 graded the same defect Critical."""
        tiers = _tier_table_items()
        assert "unscored" not in tiers, \
            f"§8 reintroduced an unscored tier: {tiers.get('unscored')}"
        tags = set(_tier_of_checklist_items().values())
        assert "unscored" not in tags, "a §5 item is tagged *(unscored)*"

    def test_checklist_tags_match_the_tier_table(self):
        """§5's per-item *(Tier)* tag and §8's tier table are two statements of
        the same fact in two places. The §8 tier lists used to be a full second
        copy of the checklist, and the copies disagreed (item 11 read PASS in §5
        and WARN in §8). Tag + table is the smallest form that can still drift,
        so it is checked rather than trusted."""
        tags = _tier_of_checklist_items()
        assert len(tags) == self.N_ITEMS, \
            f"expected {self.N_ITEMS} tagged checklist items, got {sorted(tags)}"
        from_tags: dict[str, set[int]] = {}
        for item, tier in tags.items():
            from_tags.setdefault(tier, set()).add(item)
        assert from_tags == self.EXPECTED_TIERS, \
            f"§5 tier tags say {from_tags}"

    def test_every_checklist_item_is_placed_exactly_once(self):
        placed = [n for items in _tier_table_items().values() for n in items]
        assert sorted(placed) == list(range(1, self.N_ITEMS + 1)), \
            f"§8 tiers do not partition §5's {self.N_ITEMS} items: {sorted(placed)}"

    def test_critical_items_are_conditional_not_absolute(self):
        """Critical rows must carry their exemption path, otherwise the
        scorecard reproduces the false positives it was rewritten to remove."""
        assert "PASS when kafka-clients ≥3.0 defaults already satisfy it" in SKILL_MD
        assert "WARN for a documented non-DLQ policy with an owner" in SKILL_MD


class TestOutputContract:
    def test_nine_sections(self):
        for section in [f"9.{i}" for i in range(1, 10)]:
            assert section in SKILL_MD

    def test_uncovered_risks_mandatory(self):
        assert "MANDATORY — never empty" in SKILL_MD

    def test_version_basis_reported(self):
        assert "Version basis:" in SKILL_MD


class TestReferenceFiles:
    @pytest.mark.parametrize("name", REF_FILES)
    def test_exists_and_substantial(self, name):
        assert len(_ref(name).splitlines()) >= 80

    @pytest.mark.parametrize("name", REF_FILES)
    def test_mentioned_in_skill(self, name):
        assert name in SKILL_MD

    def test_no_orphan_reference_files(self):
        for f in REFS_DIR.glob("*.md"):
            assert f.name in SKILL_MD, f"{f.name} not referenced from SKILL.md"

    def test_schema_patterns_keywords(self):
        content = _ref("event-schema-patterns.md").lower()
        for kw in ["avro", "protobuf", "backward", "event_id", "outbox",
                   "content model", "upgrade first"]:
            assert kw in content, f"missing: {kw}"

    def test_failure_modes_keywords(self):
        content = _ref("consumer-failure-modes.md").lower()
        for kw in ["rebalance", "poison", "lag", "duplicate", "ordering",
                   "read_committed", "producerfencedexception"]:
            assert kw in content, f"missing: {kw}"

    def test_version_matrix_covers_four_clients(self):
        content = _ref("version-client-matrix.md").lower()
        for client in ["kafka-clients", "librdkafka", "sarama", "franz-go"]:
            assert client in content, f"missing client: {client}"

    def test_franz_go_has_its_own_matrix_column(self):
        header, _ = _client_defaults_table()
        assert header, "client-defaults table header not found"
        assert any("franz-go" in h for h in header), \
            f"franz-go has no column in the client-defaults table: {header}"

    def test_franz_go_idempotence_default_is_true_with_named_optout(self):
        """Three independent anchors, so deleting the franz-go column cannot pass
        by leaving the word 'franz-go' in a prose paragraph: the column exists,
        its idempotence default reads true, and the opt-out call is named in that
        same cell. `franz-go in content` alone was satisfiable without any of it."""
        header, rows = _client_defaults_table()
        col = next(i for i, h in enumerate(header) if "franz-go" in h)
        idem = next((cells for label, cells in rows.items()
                     if "idempotence default" in label), None)
        assert idem, f"no 'idempotence default' row in the matrix: {list(rows)}"
        cell = idem[col]
        flat = cell.lower().replace("`", "")
        assert "true" in flat, \
            f"franz-go idempotence default reads {cell!r}, expected true"
        assert "false" not in flat, \
            f"franz-go idempotence default contradicts itself: {cell!r}"
        assert "disableidempotentwrite" in flat, \
            f"franz-go opt-out call DisableIdempotentWrite() not named in {cell!r}"

    @staticmethod
    def _slug(heading: str) -> str:
        """GitHub's heading-anchor algorithm: lowercase, drop everything that is
        not alphanumeric / space / hyphen / underscore, then spaces to hyphens."""
        s = re.sub(r"[^\w\- ]", "", heading.strip().lower())
        return s.replace(" ", "-")

    def test_every_reference_has_a_contents_table(self):
        """All four references exceed 100 lines. Without a map at the top, an
        agent loading one pays for the whole file to find one section."""
        for name in REF_FILES:
            content = _ref(name)
            assert len(content.splitlines()) > 100, \
                f"{name} shrank below 100 lines — is the TOC still warranted?"
            assert "**Contents**" in content, f"{name} has no Contents table"

    def test_reference_toc_anchors_resolve(self):
        """Every in-page link in a Contents table must hit a real `## ` heading.
        Hand-derived slugs silently rot: em dashes, `&`, backticked identifiers
        and version dots all collapse differently."""
        checked = 0
        for name in REF_FILES:
            content = _ref(name)
            headings = {self._slug(h) for h in
                        re.findall(r"^## (.+)$", content, re.M)}
            assert headings, f"{name} has no level-2 headings"
            for anchor in re.findall(r"\]\(#([^)]+)\)", content):
                assert anchor in headings, (
                    f"{name}: TOC anchor #{anchor} matches no heading. "
                    f"Available: {sorted(headings)}")
                checked += 1
        assert checked >= 25, \
            f"anchor probe only checked {checked} links — TOCs missing or unlinked"

    def test_prose_client_and_reference_counts_match_reality(self):
        """Adding franz-go left three "three major client libraries" / "all three
        reference files" claims behind, in two different files. Counts written as
        English words go stale silently, so derive them and compare."""
        words = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}
        header, _ = _client_defaults_table()
        n_clients = len([h for h in header if h])          # col 0 is the row-label column
        n_refs = len(REF_FILES)

        for label, actual, patterns in (
            ("client libraries", n_clients,
             [r"(\w+) major\s+client libraries", r"wrong on all (\w+)"]),
            ("reference files", n_refs, [r"All (\w+) reference files"]),
        ):
            expected = words[actual]
            for pattern in patterns:
                hits = [m for f in (SKILL_MD, *(_ref(n) for n in REF_FILES))
                        for m in re.findall(pattern, f)]
                assert hits, f"count-claim probe {pattern!r} matched nothing — is it still in the docs?"
                for got in hits:
                    assert got.lower() == expected, (
                        f"{label}: docs say {got!r} but there are {actual} "
                        f"({expected}) — pattern {pattern!r}")

    def test_cross_references_resolve(self):
        """Every sibling reference file cited from a reference file exists.

        Only bare backticked filenames count. Upstream provenance paths such as
        `docs/operations/consumer-rebalance-protocol.md` name files in the
        Apache Kafka repo, not here — the negative lookbehind excludes them.
        """
        for name in REF_FILES:
            for target in SIBLING_LINK.findall(_ref(name)):
                if target == "SKILL.md":
                    continue
                assert (REFS_DIR / target).exists(), \
                    f"{name} references missing sibling file {target}"

    def test_cross_reference_check_is_not_vacuous(self):
        """Guards the guard: the regex above must actually find sibling links."""
        found = {t for name in REF_FILES
                 for t in SIBLING_LINK.findall(_ref(name))}
        siblings = found & {f.name for f in REFS_DIR.glob("*.md")}
        assert len(siblings) >= 2, f"cross-reference probe found nothing to check: {found}"


class TestLineCount:
    def test_skill_within_budget(self):
        lines = len(SKILL_MD.splitlines())
        assert lines <= LINE_BUDGET, f"SKILL.md is {lines} lines (budget: {LINE_BUDGET})"


class TestToolingPresent:
    def test_linter_exists_and_selftests(self):
        assert (SCRIPTS_DIR / "lint_kafka_docs.py").exists()
        assert LINTER.selftest() == 0

    def test_mutation_sweep_exists(self):
        assert (SCRIPTS_DIR / "mutation_sweep.py").exists()

    def test_regression_runner_invokes_every_gate(self):
        runner = (SCRIPTS_DIR / "run_regression.sh").read_text(encoding="utf-8")
        for gate in ["lint_kafka_docs.py", "mutation_sweep.py", "gen_coverage.py",
                     "paraphrase_corpus.py", "model_eval.py",
                     "test_skill_contract.py", "test_golden_scenarios.py"]:
            assert gate in runner, f"run_regression.sh never runs {gate}"

    def test_coverage_doc_is_generated_not_handwritten(self):
        cov = (SCRIPTS_DIR / "tests" / "COVERAGE.md").read_text(encoding="utf-8")
        assert cov.startswith("<!-- GENERATED"), \
            "COVERAGE.md must be generated; hand-maintained totals go stale silently"


class TestCoverageDocTracksTheRunner:
    """The generator once hard-coded five gate rows while the runner ran seven.

    "Auto-generated" only means "agrees with the generator's model of the world";
    it says nothing about that model being complete. These tests bind the table
    to the file that actually decides what runs.
    """

    @staticmethod
    def _gen():
        path = SCRIPTS_DIR / "gen_coverage.py"
        spec = importlib.util.spec_from_file_location("gen_coverage", path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["gen_coverage"] = mod
        spec.loader.exec_module(mod)
        return mod

    @staticmethod
    def _table_rows() -> list[str]:
        cov = (SCRIPTS_DIR / "tests" / "COVERAGE.md").read_text(encoding="utf-8")
        block = re.search(r"^\| Gate \| What it proves \| Size \|.*?(?:\n\n|\Z)",
                          cov, re.S | re.M)
        assert block, "COVERAGE.md has no Gate Summary table"
        return [l for l in block.group(0).splitlines()[2:] if l.startswith("|")]

    def test_row_count_matches_the_runner(self):
        gates = self._gen().parse_gates()
        rows = self._table_rows()
        assert len(rows) == len(gates), (
            f"run_regression.sh runs {len(gates)} gates but COVERAGE.md lists "
            f"{len(rows)} — regenerate with scripts/gen_coverage.py")

    def test_every_runner_gate_appears_by_label(self):
        rows = "\n".join(self._table_rows())
        for label, _, _ in self._gen().parse_gates():
            pretty = re.sub(r"^\[\d+/\d+\]\s*", "", label)
            assert pretty in rows, f"gate {pretty!r} missing from COVERAGE.md"

    def test_no_gate_renders_as_an_unknown(self):
        """An unrecognised gate must fail the generator, not fill the row with
        em-dashes — a table that looks complete while saying nothing is exactly
        the failure mode being fixed."""
        for row in self._table_rows():
            cells = [c.strip() for c in row.strip().strip("|").split("|")]
            assert all(c and c != "—" for c in cells), f"blank gate row: {row!r}"

    def test_generator_rejects_a_gate_it_cannot_describe(self):
        """Guards the guard: prove the assertion above actually fires."""
        gen = self._gen()
        original = dict(gen.GATE_PROVES)
        try:
            gen.GATE_PROVES.pop(("model_eval.py", False))
            with pytest.raises(AssertionError, match="GATE_PROVES"):
                gen.build()
        finally:
            gen.GATE_PROVES.clear()
            gen.GATE_PROVES.update(original)

    def test_runner_gate_numbering_is_self_consistent(self):
        """`[3/7]` left behind on a runner that now has eight gates is the same
        silent drift one level down."""
        gates = self._gen().parse_gates()          # raises if numbering is off
        assert len(gates) >= 8, f"only {len(gates)} gates parsed from the runner"


class TestModelEvalHarness:
    """The harness is executed, not just imported.

    Unit-testing `grade()` while never running `main()` is how a harness ships
    with a wrong flag or an inverted exit code: every leaf passes and the thing
    has never once run end to end. These drive the real entry point with a stub
    runner, so no model and no credentials are involved.
    """

    EVAL = SCRIPTS_DIR / "model_eval.py"

    @staticmethod
    def _stub(tmp_path, body: str, exit_code: int = 0):
        stub = tmp_path / "stub_runner"
        stub.write_text(f"#!/bin/sh\ncat <<'EOF'\n{body}\nEOF\nexit {exit_code}\n",
                        encoding="utf-8")
        stub.chmod(0o755)
        return stub

    def _run(self, *args, cwd=None):
        return subprocess.run([sys.executable, str(self.EVAL), *args],
                              capture_output=True, text=True, cwd=cwd or SKILL_DIR)

    def test_calibration_gate_passes(self):
        proc = self._run("--calibrate")
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert "0 problem(s)" in proc.stdout

    def test_dry_run_calls_nothing_and_reports_the_plan(self):
        proc = self._run("--dry-run")
        assert proc.returncode == 0, proc.stdout + proc.stderr
        loaded = _load_model_eval()
        n = len(loaded.eval_corpus())
        assert f"{n * 2} calls" in proc.stdout, \
            f"dry-run must state the real call count (2 arms × {n}): {proc.stdout!r}"
        assert "no model" in proc.stdout, "dry-run must state the grader is not a model"
        assert "good-practice" in proc.stdout, \
            "dry-run must show the false-alarm half of the corpus"
        assert "refs=" in proc.stdout, \
            "dry-run must state which references ride along in the skilled arm"

    def test_corpus_carries_both_fixture_classes(self):
        """Defects alone measure pessimism: a model that condemns everything
        scores perfectly. The good_practice half is what makes the number mean
        judgement rather than alarm."""
        loaded = _load_model_eval()
        kinds = {f["type"] for f in loaded.eval_corpus()}
        assert kinds == {"defect", "good_practice"}, \
            f"eval corpus is {kinds}; the false-alarm half is missing"
        for fix in loaded.eval_corpus():
            if fix["type"] == "good_practice":
                assert fix["id"] in loaded.FALSE_ALARM, \
                    f"{fix['id']} has no over-flag markers — unmeasured failure mode"

    def test_full_ab_run_against_a_stub(self, tmp_path):
        """The end-to-end path: build prompts, call the runner twice per fixture,
        grade both arms, print the comparison."""
        good = ("The DLQ publish error is discarded and the offset is committed "
                "regardless, which is silent data loss; check the publish result "
                "before advancing. Retry, then route the unprocessable message.")
        stub = self._stub(tmp_path, good)
        proc = self._run("--runner", str(stub), "--limit", "2", "-v")
        assert "recall, all fixtures" in proc.stdout, proc.stdout + proc.stderr
        assert "recall, defects only" in proc.stdout
        assert "false alarms on correct code" in proc.stdout
        # Both arms saw the same canned answer, so the delta must be exactly 0 —
        # anything else means the arms are not graded identically.
        assert re.search(r"\(\+0\.000;", proc.stdout), proc.stdout

    def test_nonzero_exit_with_output_is_infra_not_a_low_score(self, tmp_path):
        """A CLI that prints a usage banner or a partial answer and exits 1 is
        not a review. Grading whatever it emitted makes a broken run look like a
        bad model — and low scores are the ones that get investigated."""
        stub = self._stub(tmp_path, "usage: my-llm [options] PROMPT", exit_code=1)
        proc = self._run("--runner", str(stub), "--limit", "1")
        assert proc.returncode == 2, \
            f"nonzero exit was graded as an answer: rc={proc.returncode}\n{proc.stdout}"
        assert "NOT a pass" in proc.stderr

    def test_json_keeps_the_raw_responses(self, tmp_path):
        """A score with no response behind it cannot be re-graded when the
        grader changes, and cannot be argued with."""
        stub = self._stub(tmp_path, "A review mentioning acks and idempotence.")
        out = tmp_path / "ab.json"
        self._run("--runner", str(stub), "--limit", "2", "--json", str(out))
        payload = json.loads(out.read_text(encoding="utf-8"))
        assert payload["transcripts"], "no transcripts recorded"
        assert all(t["response"] for t in payload["transcripts"])
        assert {t["arm"] for t in payload["transcripts"]} == {"baseline", "skilled"}
        assert payload["refs"] in ("none", "matrix", "all")

    def test_skilled_arm_carries_the_references_the_skill_mandates(self):
        """§3 loads version-client-matrix.md for ANY config verdict, so an arm
        holding only SKILL.md is not the workflow being evaluated."""
        loaded = _load_model_eval()
        assert loaded.REF_SETS["matrix"] == ["version-client-matrix.md"]
        fix = loaded.eval_corpus()[0]
        bare = loaded.build_prompt(fix, True, "none")
        withref = loaded.build_prompt(fix, True, "matrix")
        assert len(withref) > len(bare) + 1000, \
            "the matrix reference is not actually reaching the prompt"
        assert "version-client-matrix.md" in withref
        assert loaded.build_prompt(fix, False, "matrix") == \
            loaded.build_prompt(fix, False, "none"), \
            "the baseline arm must be identical regardless of --refs"

    def test_empty_runner_output_is_infra_not_a_zero_score(self, tmp_path):
        """A runner that prints nothing must exit 2. Grading it as an empty
        review scores both arms at zero and reads as "the skill made no
        difference" — a broken harness reporting a finding."""
        stub = self._stub(tmp_path, "")
        proc = self._run("--runner", str(stub), "--limit", "1")
        assert proc.returncode == 2, \
            f"empty output scored instead of skipping: {proc.returncode}\n{proc.stdout}"
        assert "NOT a pass" in proc.stderr

    def test_missing_runner_binary_is_infra(self):
        proc = self._run("--runner", "definitely-not-a-real-binary-xyz", "--limit", "1")
        assert proc.returncode == 2
        assert "NOT a pass" in proc.stderr

    def test_wrong_claims_fail_even_with_perfect_recall(self, tmp_path):
        """The linter penalty must be able to fail a response that names every
        required concept while asserting something known to be false."""
        loaded = _load_model_eval()
        fixture = next(f for f in loaded.fixtures() if f["id"] == "KAFKA-011")
        response = ("Add consumer lag monitoring with an alert. "
                    "Page when consumer lag reaches ten thousand records.")
        score = loaded.grade(response, fixture)
        assert score.recall == 1.0, f"expected full recall, got {score.missed}"
        assert not score.clean, "a known-wrong claim scored clean at full recall"
        assert "KL024" in score.wrong_claims
