"""Golden scenario tests for kafka-event-driven-design.

WHY THIS FILE LOOKS THE WAY IT DOES
-----------------------------------
The previous version of this suite asserted things like::

    assert "poison" in fixture["expected_feedback"].lower()

That is a tautology: the fixture supplies both the input and the oracle, so the
assertion only proves the fixture author typed a word into their own string. It
passed 91/91 with the skill's core rules rewritten to say the opposite of the
truth ("never use acks=all; prefer acks=1"), because inverted advice contains
the same keywords.

Every assertion here is anchored to something OUTSIDE the fixture:

* ``detector_rules``  — the exact set of linter rule IDs that must fire on the
  fixture's snippet. Bidirectional: a missing rule fails, and so does an extra
  one (that is the false-positive guard).
* ``checklist_anchor`` — text that must exist in SKILL.md. If the checklist item
  a fixture depends on is deleted or reworded, the fixture fails.
* ``expected_feedback`` is linted like any other prose. A fixture is a shipped
  exemplar of the skill's own output; it must pass the skill's own grader.
* A hand-written table of verified upstream facts (defaults, API shapes) that the
  documentation must state correctly. These values were transcribed from Apache
  Kafka source, not from the docs under test.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import re
import sys

import pytest

SKILL_DIR = pathlib.Path(__file__).resolve().parents[2]
SKILL_MD = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
REFS_DIR = SKILL_DIR / "references"
GOLDEN_DIR = pathlib.Path(__file__).resolve().parent / "golden"


def _load_linter():
    """Load by path: this repo runs pytest with --import-mode=importlib, which
    breaks bare sibling imports, and the linter lives in scripts/ not tests/."""
    path = SKILL_DIR / "scripts" / "lint_kafka_docs.py"
    spec = importlib.util.spec_from_file_location("lint_kafka_docs", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["lint_kafka_docs"] = module  # register before exec
    spec.loader.exec_module(module)
    return module


LINTER = _load_linter()


def _fixtures() -> list[dict]:
    return [json.loads(f.read_text(encoding="utf-8"))
            for f in sorted(GOLDEN_DIR.glob("*.json"))]


FIXTURES = _fixtures()
BY_ID = {f["id"]: f for f in FIXTURES}

VALID_TYPES = {"defect", "good_practice", "degradation_scenario", "workflow"}
VALID_SEVERITIES = {"critical", "standard", "hygiene", "none"}
REQUIRED_FIELDS = {
    "id", "title", "type", "severity", "code_snippet", "expected_feedback",
    "coverage_rules", "reference", "detector_rules", "checklist_anchor",
    "snippet_lang",
}


def lint(text: str, path: str = "fixture.md") -> set[str]:
    return {f.rule for f in LINTER.scan_text(text, path)}


def fenced(fix: dict) -> str:
    return f"```{fix['snippet_lang']}\n{fix['code_snippet']}\n```\n"


def ids(fixtures) -> list[str]:
    return [f["id"] for f in fixtures]


# ===========================================================================
# Fixture integrity
# ===========================================================================

class TestFixtureIntegrity:
    def test_minimum_fixture_count(self):
        assert len(FIXTURES) >= 18

    @pytest.mark.parametrize("fix", FIXTURES, ids=ids(FIXTURES))
    def test_required_fields(self, fix):
        missing = REQUIRED_FIELDS - set(fix.keys())
        assert not missing, f"{fix['id']}: missing fields {missing}"

    @pytest.mark.parametrize("fix", FIXTURES, ids=ids(FIXTURES))
    def test_valid_type_and_severity(self, fix):
        assert fix["type"] in VALID_TYPES
        assert fix["severity"] in VALID_SEVERITIES
        if fix["type"] == "defect":
            assert fix["severity"] != "none", f"{fix['id']}: defect with severity none"
        else:
            assert fix["severity"] == "none", f"{fix['id']}: non-defect with a severity"

    def test_unique_ids(self):
        assert len(BY_ID) == len(FIXTURES)

    @pytest.mark.parametrize("fix", FIXTURES, ids=ids(FIXTURES))
    def test_reference_target_exists(self, fix):
        ref = fix["reference"]
        if ref == "SKILL.md":
            return
        assert (SKILL_DIR / ref).exists(), f"{fix['id']}: dangling reference {ref}"


# ===========================================================================
# Anchors point OUTSIDE the fixture
# ===========================================================================

class TestChecklistAnchors:
    """Each fixture names a checklist/scorecard item in SKILL.md that makes its
    defect reviewable. Deleting or rewording that item fails the fixture, so the
    fixture set cannot drift away from the skill body."""

    @pytest.mark.parametrize("fix", FIXTURES, ids=ids(FIXTURES))
    def test_anchor_present_in_skill(self, fix):
        anchor = fix["checklist_anchor"]
        assert anchor in SKILL_MD, (
            f"{fix['id']}: checklist_anchor not found in SKILL.md: {anchor!r}"
        )

    def test_anchors_are_not_trivial(self):
        for fix in FIXTURES:
            assert len(fix["checklist_anchor"]) >= 20, (
                f"{fix['id']}: anchor too short to be a meaningful structural probe"
            )

    def test_anchors_cover_distinct_items(self):
        # A fixture set that all points at one checklist line is not coverage.
        assert len({f["checklist_anchor"] for f in FIXTURES}) >= 12


# ===========================================================================
# Severity ↔ scorecard invariant
# ===========================================================================

def _checklist_item_containing(anchor: str) -> int | None:
    """The §5 item number whose body contains `anchor`, or None if the anchor
    lives outside the checklist (a Gate or a §4 hard rule).

    Resolved by position, not by parsing prose: find the anchor's offset, then
    the nearest preceding `N. **` that is still inside §5.
    """
    if anchor not in SKILL_MD:
        return None
    start = SKILL_MD.index("## §5 Design Checklist")
    end = SKILL_MD.index("## §6 Partition Design")
    pos = SKILL_MD.index(anchor)
    if not (start < pos < end):
        return None
    heads = [(m.start(), int(m.group(1)))
             for m in re.finditer(r"^(\d+)\.\s+\*\*", SKILL_MD[start:end], re.M)]
    preceding = [n for off, n in heads if start + off < pos]
    return preceding[-1] if preceding else None


def _tier_of_item() -> dict[int, str]:
    return {int(n): t.strip().split()[0].lower()
            for n, t in re.findall(r"^(\d+)\.\s+\*\*.*?\*\*\s*\*\(([^)]+)\)\*",
                                   SKILL_MD, re.M)}


class TestSeverityIsActuallyScoreable:
    """A fixture graded critical/standard must map to an item the scorecard can
    fail on.

    This gate exists because it was violated: `atomicity mechanism` and
    `sensitive data` were reviewed-but-unscored §5 items while KAFKA-015 graded a
    Kafka-transaction-around-a-database-write as **critical** and KAFKA-018 graded
    PII-on-a-compacted-topic as **standard**. Both defects could be found,
    written into §9, and still leave the scorecard PASS. Severity that cannot
    reach the verdict is decoration.
    """

    SCOREABLE = {"critical", "standard", "hygiene"}
    GRADED = [f for f in FIXTURES if f["severity"] in {"critical", "standard"}]

    def test_there_are_graded_fixtures_to_check(self):
        """Guards the guard: an empty GRADED list would pass everything below."""
        assert len(self.GRADED) >= 10, \
            f"only {len(self.GRADED)} critical/standard fixtures — probe is near-vacuous"

    @pytest.mark.parametrize("fix", GRADED, ids=ids(GRADED))
    def test_anchor_resolves_to_a_checklist_item(self, fix):
        item = _checklist_item_containing(fix["checklist_anchor"])
        assert item is not None, (
            f"{fix['id']} is severity {fix['severity']} but its anchor "
            f"{fix['checklist_anchor']!r} is not inside a §5 checklist item, so "
            f"no scorecard item fails when this defect is present")

    @pytest.mark.parametrize("fix", GRADED, ids=ids(GRADED))
    def test_that_item_carries_a_tier(self, fix):
        item = _checklist_item_containing(fix["checklist_anchor"])
        tier = _tier_of_item().get(item)
        assert tier in self.SCOREABLE, (
            f"{fix['id']} ({fix['severity']}) anchors on §5 item {item}, whose "
            f"tier is {tier!r} — an unscored item cannot fail the scorecard")

    def test_every_checklist_item_is_scoreable(self):
        """The general form. Per-fixture checks only cover items a fixture
        happens to exercise; this one closes the rest."""
        tiers = _tier_of_item()
        assert tiers, "no §5 items carry a tier tag"
        unscored = sorted(n for n, t in tiers.items() if t not in self.SCOREABLE)
        assert not unscored, f"§5 items outside the scorecard: {unscored}"


class TestCoverageRulesGrounded:
    @pytest.mark.parametrize("fix", FIXTURES, ids=ids(FIXTURES))
    def test_coverage_rules_appear_in_docs(self, fix):
        # Whitespace-normalised: prose wraps, and a two-word term split across a
        # line break is still present in the docs. A raw substring check reports
        # a false absence and pushes the author to reflow the doc for the test.
        raw = "\n".join(
            [SKILL_MD] + [p.read_text(encoding="utf-8") for p in sorted(REFS_DIR.glob("*.md"))]
        )
        corpus = re.sub(r"\s+", " ", raw).lower()
        for rule in fix["coverage_rules"]:
            needle = re.sub(r"\s+", " ", rule).lower()
            assert needle in corpus, f"{fix['id']}: '{rule}' absent from docs"


# ===========================================================================
# Linter detection — bidirectional
# ===========================================================================

class TestDetectorExpectations:
    """The declared rule set must match the linter output EXACTLY.

    Missing rules mean the defect is undetected. Extra rules mean a false
    positive on realistic Kafka code, which is the failure mode that trains
    reviewers to ignore a tool.
    """

    @pytest.mark.parametrize("fix", FIXTURES, ids=ids(FIXTURES))
    def test_snippet_detection_exact(self, fix):
        expected = set(fix["detector_rules"])
        actual = lint(fenced(fix), f"{fix['id']}.md")
        assert actual == expected, (
            f"{fix['id']}: linter reported {sorted(actual) or 'nothing'}, "
            f"fixture declares {sorted(expected) or 'nothing'}"
        )

    @pytest.mark.parametrize(
        "fix", [f for f in FIXTURES if not f["detector_rules"]],
        ids=ids([f for f in FIXTURES if not f["detector_rules"]]),
    )
    def test_clean_snippets_stay_clean(self, fix):
        """Explicit false-positive guard over realistic Kafka code."""
        assert lint(fenced(fix), f"{fix['id']}.md") == set()

    def test_some_fixtures_are_actually_detected(self):
        """Guards the guard: if every fixture declared an empty rule set, the
        exact-match test above would pass while detecting nothing at all."""
        detected = [f["id"] for f in FIXTURES if f["detector_rules"]]
        assert len(detected) >= 5, f"only {detected} exercise the linter"

    def test_declared_rules_exist(self):
        known = {r.id for r in LINTER.RULES}
        for fix in FIXTURES:
            unknown = set(fix["detector_rules"]) - known
            assert not unknown, f"{fix['id']}: unknown rule id(s) {unknown}"


class TestExemplarsPassOwnGrader:
    """Fixture feedback is a shipped example of the skill's own output. If it
    contains a claim the linter rejects, the skill is teaching the error it
    documents elsewhere."""

    @pytest.mark.parametrize("fix", FIXTURES, ids=ids(FIXTURES))
    def test_expected_feedback_is_clean(self, fix):
        found = lint(fix["expected_feedback"], f"{fix['id']}-feedback.md")
        assert not found, f"{fix['id']}: feedback trips {sorted(found)}"

    @pytest.mark.parametrize("fix", FIXTURES, ids=ids(FIXTURES))
    def test_title_is_clean(self, fix):
        assert not lint(fix["title"], f"{fix['id']}-title.md")


# ===========================================================================
# Verified upstream facts — transcribed from Apache Kafka source, NOT from the
# documents under test. Mutating a doc value breaks these.
# ===========================================================================

# (description, file, must-contain). Values verified against
# apache/kafka ProducerConfig.java / ConsumerConfig.java on branches 2.8, 3.0,
# 4.3 and docs/operations/consumer-rebalance-protocol.md on 4.3.
VERIFIED_FACTS = [
    ("Java producer acks default flipped to all at 3.0",
     "references/version-client-matrix.md", "| `acks` | `1` | **`all`** |"),
    ("Java producer idempotence default flipped to true at 3.0",
     "references/version-client-matrix.md", "| `enable.idempotence` | `false` | **`true`** |"),
    ("idempotence permits in-flight up to 5, not 1",
     "references/version-client-matrix.md", "with message ordering\npreserved for any allowable value"),
    ("consumer auto-commit still defaults true",
     "references/version-client-matrix.md", "`enable.auto.commit` | **`true`**"),
    ("isolation.level defaults to read_uncommitted",
     "references/version-client-matrix.md", "`isolation.level` | **`read_uncommitted`**"),
    ("classic assignor default is Range-first (eager)",
     "references/version-client-matrix.md", "`[RangeAssignor, CooperativeStickyAssignor]`"),
    ("group.protocol still defaults to classic in 4.x",
     "references/version-client-matrix.md", "`group.protocol` | `classic`"),
    ("KIP-848 GA in 4.0",
     "references/version-client-matrix.md", "**4.0 GA**"),
    ("CooperativeSticky maps to the uniform server-side assignor",
     "references/version-client-matrix.md", "| `CooperativeStickyAssignor` | `uniform` |"),
    ("sarama requires MaxOpenRequests=1 under idempotence",
     "references/version-client-matrix.md", "must equal 1"),
    ("sarama acks default is WaitForLocal",
     "references/version-client-matrix.md", "**`WaitForLocal` (= acks=1)**"),
    ("librdkafka idempotence default is false",
     "references/version-client-matrix.md", "| idempotence default | **`true`** | `false` | `false` |"),
    ("surviving sendOffsetsToTransaction takes ConsumerGroupMetadata",
     "references/version-client-matrix.md", "sendOffsetsToTransaction(offsets, consumer.groupMetadata())"),
    ("BACKWARD permits deleting fields",
     "references/event-schema-patterns.md", "**Delete fields**; add optional fields"),
    ("FORWARD permits deleting optional fields",
     "references/event-schema-patterns.md", "Add fields; **delete optional fields**"),
    ("BACKWARD requires upgrading consumers first",
     "references/event-schema-patterns.md", "| Consumers |"),
    ("FORWARD requires upgrading producers first",
     "references/event-schema-patterns.md", "| Producers |"),
]


class TestVerifiedFacts:
    @pytest.mark.parametrize(
        "desc,rel,needle", VERIFIED_FACTS, ids=[f[0] for f in VERIFIED_FACTS]
    )
    def test_fact_stated(self, desc, rel, needle):
        text = (SKILL_DIR / rel).read_text(encoding="utf-8")
        assert needle in text, f"{rel} no longer states: {desc}"


# ===========================================================================
# Whole-corpus lint gate
# ===========================================================================

class TestCorpusLint:
    def test_all_shipped_docs_pass(self):
        offenders = []
        for path in [SKILL_DIR / "SKILL.md"] + sorted(REFS_DIR.glob("*.md")):
            found = LINTER.scan_text(path.read_text(encoding="utf-8"), path.name)
            offenders += [f"{f.path}:{f.line} [{f.rule}] {f.excerpt}" for f in found]
        assert not offenders, "linter findings in shipped docs:\n" + "\n".join(offenders)

    def test_linter_selftest_passes(self):
        assert LINTER.selftest() == 0

    def test_linter_has_meaningful_rule_count(self):
        assert len(LINTER.RULES) >= 20
        for rule in LINTER.RULES:
            assert rule.should_fire, f"{rule.id}: no positive selftest case"
            assert rule.should_pass, f"{rule.id}: no negative selftest case"
