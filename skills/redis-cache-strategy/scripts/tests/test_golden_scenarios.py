"""Golden scenario tests for redis-cache-strategy.

What changed and why
--------------------
The previous version of this file asserted things like

    assert "jitter" in fixture["expected_feedback"]

which reads a string out of the fixture and asserts something about that same
string. It tests whoever wrote the fixture, not the skill, and it cannot fail
for any defect in the documentation. That is how a hot-key example that spread
no load at all sat at "100% passing" for months.

These tests instead run the skill's own code rules over each fixture's snippet
and compare against a hand-written declaration on the fixture:

  * `detectors`                 -- the exact set of rules that must fire.
  * `primary_defect_gated_by`   -- the rule that catches the HEADLINE defect,
                                   or null when only a model review can.

Both directions are enforced. A declared rule that stops firing fails; a rule
that starts firing where nothing was declared also fails, which is what makes
an over-broad rule visible instead of merely quiet.
"""

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
    """Load lint_cache_docs.py by path.

    Registered in sys.modules *before* exec_module: the module combines
    `from __future__ import annotations` with @dataclass, and without the
    registration the dataclass decorator resolves its own module to None and
    raises "'NoneType' object has no attribute '__dict__'". The repo also runs
    pytest with --import-mode=importlib, so a bare sibling import is not an
    option here.
    """
    path = SKILL_DIR / "scripts" / "lint_cache_docs.py"
    spec = importlib.util.spec_from_file_location("rcs_lint", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["rcs_lint"] = mod
    spec.loader.exec_module(mod)
    return mod


LINT = _load_linter()
CODE_RULES = [r for r in LINT.RULES if r.scope == "code"]
KNOWN_RULE_IDS = {r.id for r in LINT.RULES}

# §5's items, parsed from SKILL.md itself so this file cannot hold a stale copy.
SKILL_ITEMS = LINT.skill_items(SKILL_MD)
ALL_ITEM_IDS = {f"{p}{n}" for p, nums in SKILL_ITEMS.items() for n in nums}
TIER_RANK = {"H": 1, "S": 2, "C": 3}
SEVERITY_RANK = {"hygiene": 1, "standard": 2, "critical": 3}


def _all_docs_lower() -> str:
    """Joined docs, lowercased, with runs of whitespace collapsed.

    The collapse matters: without it a two-word concept that happens to straddle
    a line wrap ("… with Redis\\nunavailable …") reads as absent, so the test
    fails for a formatting reason and gets "fixed" by re-wrapping prose around
    an assertion. Normalise here instead.
    """
    parts = [SKILL_MD] + [f.read_text(encoding="utf-8") for f in sorted(REFS_DIR.glob("*.md"))]
    return re.sub(r"\s+", " ", "\n".join(parts).lower())


def _load_fixtures() -> list[dict]:
    return [json.loads(f.read_text(encoding="utf-8"))
            for f in sorted(GOLDEN_DIR.glob("*.json"))]


ALL_DOCS_LOWER = _all_docs_lower()
FIXTURES = _load_fixtures()
BY_ID = {f["id"]: f for f in FIXTURES}

VALID_TYPES = {"defect", "good_practice", "degradation_scenario", "workflow"}
VALID_SEVERITIES = {"critical", "standard", "hygiene", "none"}
REQUIRED_FIELDS = {
    "id", "title", "type", "severity", "code_snippet", "expected_feedback",
    "coverage_rules", "reference", "detectors", "primary_defect_gated_by",
    "detector_note", "scorecard_items",
}

# §5 items that no fixture exercises yet. Derived-minus-declared is asserted
# below, so adding an item without a fixture is a deliberate edit here rather
# than a silent hole: "17/17 fixtures pass" says nothing about an item that has
# no fixture at all, because the denominator is the fixture list.
ITEMS_WITHOUT_A_FIXTURE = {
    "C1",  # source of truth — a design statement, not a code shape
    "S1", "S5", "S6",  # jitter, hot key, staleness window
    "H1", "H2", "H3", "H4", "H5",  # every hygiene item
}

# Declared coverage. Fixtures whose HEADLINE defect no code rule can gate --
# these are the cases that rely on the model actually reading SKILL.md. The
# number is asserted below so that "we added a rule" and "we added an ungated
# fixture" both have to be a deliberate edit here, not a silent drift.
# Only `defect` fixtures appear here; a non-defect fixture has no primary
# defect to gate and is checked separately.
UNGATED_PRIMARY_DEFECTS = {
    "CACHE-001", "CACHE-003", "CACHE-004", "CACHE-011", "CACHE-012",
    "CACHE-013", "CACHE-014", "CACHE-015", "CACHE-016", "CACHE-017",
}


def fired_rules(snippet: str) -> set[str]:
    """Rule IDs that fire on a snippet, comment tails masked as in the linter."""
    body = LINT.strip_comments(snippet)
    return {r.id for r in CODE_RULES for _ in r._fn(body)}


def ids(fixtures) -> list[str]:
    return [f["id"] for f in fixtures]


# ---------------------------------------------------------------------------
# fixture integrity
# ---------------------------------------------------------------------------

class TestFixtureIntegrity:
    def test_minimum_fixture_count(self):
        assert len(FIXTURES) >= 17

    @pytest.mark.parametrize("fix", FIXTURES, ids=ids(FIXTURES))
    def test_required_fields(self, fix):
        assert not REQUIRED_FIELDS - set(fix.keys()), \
            f"{fix['id']}: missing {REQUIRED_FIELDS - set(fix.keys())}"

    @pytest.mark.parametrize("fix", FIXTURES, ids=ids(FIXTURES))
    def test_valid_type_and_severity(self, fix):
        assert fix["type"] in VALID_TYPES
        assert fix["severity"] in VALID_SEVERITIES

    @pytest.mark.parametrize("fix", FIXTURES, ids=ids(FIXTURES))
    def test_severity_matches_type(self, fix):
        if fix["type"] == "defect":
            assert fix["severity"] != "none"
        else:
            assert fix["severity"] == "none"

    def test_unique_ids(self):
        assert len(ids(FIXTURES)) == len(set(ids(FIXTURES)))

    @pytest.mark.parametrize("fix", FIXTURES, ids=ids(FIXTURES))
    def test_coverage_rules_findable(self, fix):
        for rule in fix["coverage_rules"]:
            assert rule.lower() in ALL_DOCS_LOWER, f"{fix['id']}: '{rule}' not in docs"

    @pytest.mark.parametrize("fix", FIXTURES, ids=ids(FIXTURES))
    def test_reference_file_exists(self, fix):
        assert (SKILL_DIR / fix["reference"]).exists(), \
            f"{fix['id']}: reference {fix['reference']} does not exist"


# ---------------------------------------------------------------------------
# behaviour: the fixtures drive the real checker
# ---------------------------------------------------------------------------

class TestDetectorBehaviour:
    @pytest.mark.parametrize("fix", FIXTURES, ids=ids(FIXTURES))
    def test_declared_detectors_are_real_rules(self, fix):
        unknown = set(fix["detectors"]) - KNOWN_RULE_IDS
        assert not unknown, f"{fix['id']}: declares non-existent rule(s) {unknown}"

    @pytest.mark.parametrize("fix", FIXTURES, ids=ids(FIXTURES))
    def test_declared_detectors_all_fire(self, fix):
        """Positive direction: every declared rule must actually fire."""
        missing = set(fix["detectors"]) - fired_rules(fix["code_snippet"])
        assert not missing, (
            f"{fix['id']}: declared detector(s) {sorted(missing)} did not fire. "
            "Either the rule is dead or the snippet no longer contains the defect."
        )

    @pytest.mark.parametrize("fix", FIXTURES, ids=ids(FIXTURES))
    def test_no_undeclared_rule_fires(self, fix):
        """Negative direction: an over-broad rule must not pass unnoticed."""
        extra = fired_rules(fix["code_snippet"]) - set(fix["detectors"])
        assert not extra, (
            f"{fix['id']}: undeclared rule(s) {sorted(extra)} fired. "
            "Either the rule is over-broad, or the fixture gained a defect "
            "that must be declared."
        )

    @pytest.mark.parametrize(
        "fix", [f for f in FIXTURES if f["type"] == "good_practice"],
        ids=ids([f for f in FIXTURES if f["type"] == "good_practice"]))
    def test_exemplars_are_clean(self, fix):
        """The shipped models of correct code must pass the skill's own grader.

        Both exemplars failed this when it was first written -- CACHE-007 had an
        unchecked type assertion, `== sql.ErrNoRows`, and two discarded cache
        writes while its expected_feedback said "No violations".
        """
        assert fired_rules(fix["code_snippet"]) == set(), \
            f"{fix['id']} is shipped as an exemplar but trips its own linter"
        assert fix["detectors"] == []

    @pytest.mark.parametrize("fix", FIXTURES, ids=ids(FIXTURES))
    def test_primary_defect_declaration_consistent(self, fix):
        prim = fix["primary_defect_gated_by"]
        if fix["type"] != "defect":
            assert prim is None, f"{fix['id']}: non-defect fixture declares a primary detector"
            assert fix["id"] not in UNGATED_PRIMARY_DEFECTS
            return
        if prim is None:
            assert fix["id"] in UNGATED_PRIMARY_DEFECTS, \
                f"{fix['id']}: primary defect ungated but not in the declared set"
        else:
            assert prim in fix["detectors"], \
                f"{fix['id']}: primary detector {prim} is not in its own detectors list"
            assert fix["id"] not in UNGATED_PRIMARY_DEFECTS

    def test_ungated_set_has_no_stale_entries(self):
        assert UNGATED_PRIMARY_DEFECTS <= set(BY_ID), \
            f"stale ids in UNGATED_PRIMARY_DEFECTS: {UNGATED_PRIMARY_DEFECTS - set(BY_ID)}"
        non_defect = {i for i in UNGATED_PRIMARY_DEFECTS if BY_ID[i]["type"] != "defect"}
        assert not non_defect, f"non-defect ids in UNGATED_PRIMARY_DEFECTS: {non_defect}"

    def test_gated_coverage_is_not_zero(self):
        """At least the mechanically-checkable defects must be mechanically checked."""
        gated = [f for f in FIXTURES if f["primary_defect_gated_by"]]
        assert len(gated) >= 3, "no fixture's headline defect is gated by a rule"

    @pytest.mark.parametrize("fix", FIXTURES, ids=ids(FIXTURES))
    def test_detector_note_explains_gaps(self, fix):
        if fix["primary_defect_gated_by"] is None:
            assert len(fix["detector_note"].strip()) >= 40, \
                f"{fix['id']}: ungated primary defect needs a stated reason"


# ---------------------------------------------------------------------------
# the scorecard must be able to act on what the fixtures find
# ---------------------------------------------------------------------------

class TestScorecardReachability:
    """The defect this class exists to prevent.

    Before 2026-08-10, §5 listed 14 checklist items and §8 scored a *different*
    14. Three fixtures marked `critical` — write-behind for money (CACHE-012),
    a cross-tenant key (CACHE-014), an unfenced correctness lock (CACHE-017) —
    mapped only to §8 entries in the Standard tier, and Standard tolerated one
    failure. A review could therefore find all three, report them as Critical
    in prose, and still print PASS.

    These tests make that unrepresentable: a fixture names the §5 IDs it
    violates, those IDs must exist, and the tier of at least one of them must be
    at least as severe as the fixture claims to be.
    """

    def test_skill_defines_items(self):
        assert SKILL_ITEMS, "SKILL.md §5 defines no C/S/H items — parser or doc broke"
        assert set(SKILL_ITEMS) == {"C", "S", "H"}, f"unexpected tiers: {sorted(SKILL_ITEMS)}"

    @pytest.mark.parametrize("fix", FIXTURES, ids=ids(FIXTURES))
    def test_scorecard_items_exist(self, fix):
        unknown = set(fix["scorecard_items"]) - ALL_ITEM_IDS
        assert not unknown, (
            f"{fix['id']}: names §5 item(s) {sorted(unknown)} that SKILL.md does not define. "
            f"Defined: {sorted(ALL_ITEM_IDS)}"
        )

    @pytest.mark.parametrize("fix", [f for f in FIXTURES if f["type"] == "defect"],
                             ids=ids([f for f in FIXTURES if f["type"] == "defect"]))
    def test_defect_names_at_least_one_item(self, fix):
        assert fix["scorecard_items"], \
            f"{fix['id']} is a defect that violates no §5 item — it cannot affect any score"

    @pytest.mark.parametrize("fix", [f for f in FIXTURES if f["type"] == "defect"],
                             ids=ids([f for f in FIXTURES if f["type"] == "defect"]))
    def test_severity_can_actually_block(self, fix):
        """A `critical` fixture must map to a Critical item, or its severity is decorative."""
        want = SEVERITY_RANK[fix["severity"]]
        best = max(TIER_RANK[i[0]] for i in fix["scorecard_items"])
        assert best >= want, (
            f"{fix['id']} is severity={fix['severity']} but its worst §5 item is tier "
            f"{[k for k, v in TIER_RANK.items() if v == best][0]}*. A Critical finding that "
            f"lands only in Standard cannot force a FAIL — Standard tolerates a miss."
        )

    @pytest.mark.parametrize("fix", [f for f in FIXTURES if f["type"] != "defect"],
                             ids=ids([f for f in FIXTURES if f["type"] != "defect"]))
    def test_non_defect_names_no_items(self, fix):
        assert fix["scorecard_items"] == [], \
            f"{fix['id']} is {fix['type']} but claims to violate {fix['scorecard_items']}"

    def test_uncovered_items_are_declared(self):
        """Coverage is `items - exercised`, not `fixtures that passed`.

        A new §5 item with no fixture is invisible to a suite whose denominator
        is the fixture list; deriving the complement makes it visible.
        """
        exercised = {i for f in FIXTURES for i in f["scorecard_items"]}
        uncovered = ALL_ITEM_IDS - exercised
        assert uncovered == ITEMS_WITHOUT_A_FIXTURE, (
            f"§5 item coverage drifted.\n"
            f"  newly uncovered (add a fixture, or declare it): "
            f"{sorted(uncovered - ITEMS_WITHOUT_A_FIXTURE)}\n"
            f"  now covered (remove from the declaration): "
            f"{sorted(ITEMS_WITHOUT_A_FIXTURE - uncovered)}"
        )

    def test_every_critical_item_that_has_a_fixture_is_reachable(self):
        """Each Critical item with a fixture must have a *critical* fixture.

        Otherwise the item is scored as Critical but only ever demonstrated by a
        case the suite calls Standard, and nothing proves the tier is load-bearing.
        """
        crit_items = {f"C{n}" for n in SKILL_ITEMS.get("C", [])}
        by_item: dict[str, set[str]] = {}
        for f in FIXTURES:
            for i in f["scorecard_items"]:
                by_item.setdefault(i, set()).add(f["severity"])
        for item in sorted(crit_items & set(by_item)):
            assert "critical" in by_item[item], (
                f"{item} is a Critical item but every fixture naming it is "
                f"{sorted(by_item[item])} — nothing proves it can force a FAIL"
            )


# ---------------------------------------------------------------------------
# adversarial cases must stay adversarial
# ---------------------------------------------------------------------------

class TestAdversarialCases:
    def test_outage_fixture_separates_outage_from_miss(self):
        fb = BY_ID["CACHE-015"]["expected_feedback"].lower()
        assert "redis.nil" in fb and "errors.is" in fb
        assert "degradation" in fb
        # The snippet must actually contain the conflation, or the case is moot.
        assert "if err != nil {" in BY_ID["CACHE-015"]["code_snippet"]
        assert "redis.Nil" not in BY_ID["CACHE-015"]["code_snippet"]

    def test_race_fixture_has_both_sides_of_the_interleaving(self):
        snippet = BY_ID["CACHE-016"]["code_snippet"]
        # A race needs a reader AND a writer; one function cannot show it.
        assert "rdb.Set(" in snippet and "rdb.Del(" in snippet
        fb = BY_ID["CACHE-016"]["expected_feedback"].lower()
        assert "double-delete" in fb or "double delete" in fb

    def test_lock_fixture_is_well_formed_but_unsafe(self):
        """This case exists precisely because no code rule can catch it."""
        fix = BY_ID["CACHE-017"]
        assert fired_rules(fix["code_snippet"]) == set(), \
            "CACHE-017 must remain clean under the linter — that is its point"
        snippet = fix["code_snippet"]
        # It must show the WELL-FORMED baseline (TTL + token + CAS release)...
        assert "SetNX" in snippet and "token" in snippet and "releaseCAS" in snippet
        # ...while the feedback insists the baseline is not sufficient.
        fb = fix["expected_feedback"].lower()
        assert "fencing" in fb
        assert "renewal" in fb or "renew" in fb
        assert "failover" in fb

    @pytest.mark.parametrize("fid", ["CACHE-015", "CACHE-016", "CACHE-017"])
    def test_adversarial_cases_are_critical(self, fid):
        assert BY_ID[fid]["severity"] == "critical"
