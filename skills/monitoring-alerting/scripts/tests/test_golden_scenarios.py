"""Golden scenario tests for monitoring-alerting skill."""

import importlib.util
import json
import re
import pathlib
import sys
import pytest


def _load_linter():
    path = pathlib.Path(__file__).resolve().parents[1] / "lint_monitoring_docs.py"
    spec = importlib.util.spec_from_file_location("mon_lint", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod      # register first: by-path exec + dataclasses/
    spec.loader.exec_module(mod)      # __future__ annotations otherwise breaks
    return mod


LINTER = _load_linter()

SKILL_DIR = pathlib.Path(__file__).resolve().parents[2]
SKILL_MD = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
REFS_DIR = SKILL_DIR / "references"
GOLDEN_DIR = pathlib.Path(__file__).resolve().parent / "golden"


def _all_docs_lower() -> str:
    parts = [SKILL_MD]
    for f in sorted(REFS_DIR.glob("*.md")):
        parts.append(f.read_text(encoding="utf-8"))
    return "\n".join(parts).lower()


def _load_fixtures() -> list[dict]:
    return [json.loads(f.read_text(encoding="utf-8"))
            for f in sorted(GOLDEN_DIR.glob("*.json"))]


ALL_DOCS_LOWER = _all_docs_lower()
FIXTURES = _load_fixtures()

VALID_TYPES = {"defect", "good_practice", "degradation_scenario", "workflow"}
VALID_SEVERITIES = {"critical", "standard", "hygiene", "none"}
REQUIRED_FIELDS = {
    "id", "title", "type", "severity", "code_snippet",
    "expected_feedback", "coverage_rules", "reference",
}


class TestFixtureIntegrity:
    def test_minimum_fixture_count(self):
        assert len(FIXTURES) >= 13

    def test_required_fields(self):
        for fix in FIXTURES:
            missing = REQUIRED_FIELDS - set(fix.keys())
            assert not missing, f"{fix['id']}: missing fields {missing}"

    def test_valid_types(self):
        for fix in FIXTURES:
            assert fix["type"] in VALID_TYPES

    def test_valid_severities(self):
        for fix in FIXTURES:
            assert fix["severity"] in VALID_SEVERITIES

    def test_defect_severity_not_none(self):
        for fix in FIXTURES:
            if fix["type"] == "defect":
                assert fix["severity"] != "none"

    def test_non_defect_severity_none(self):
        for fix in FIXTURES:
            if fix["type"] in ("good_practice", "degradation_scenario", "workflow"):
                assert fix["severity"] == "none"

    def test_unique_ids(self):
        ids = [f["id"] for f in FIXTURES]
        assert len(ids) == len(set(ids))

    def test_coverage_rules_findable(self):
        for fix in FIXTURES:
            for rule in fix["coverage_rules"]:
                assert rule.lower() in ALL_DOCS_LOWER, \
                    f"{fix['id']}: coverage rule '{rule}' not found in docs"


# Critical Defects

class TestMON001:
    fix = next(f for f in FIXTURES if f["id"] == "MON-001")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "critical"

    def test_violated_rule(self):
        assert "sli" in self.fix["violated_rule"].lower()

    def test_expected_mentions_sli(self):
        fb = self.fix["expected_feedback"].lower()
        assert "sli" in fb and ("availability" in fb or "latency" in fb)


class TestMON002:
    fix = next(f for f in FIXTURES if f["id"] == "MON-002")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "critical"

    def test_violated_rule(self):
        assert "actionable" in self.fix["violated_rule"].lower()

    def test_expected_mentions_runbook(self):
        fb = self.fix["expected_feedback"].lower()
        assert "runbook" in fb or "action" in fb


class TestMON003:
    fix = next(f for f in FIXTURES if f["id"] == "MON-003")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "critical"

    def test_violated_rule(self):
        vr = self.fix["violated_rule"].lower()
        assert "severity" in vr or "routing" in vr

    def test_expected_mentions_pagerduty(self):
        fb = self.fix["expected_feedback"].lower()
        assert "pagerduty" in fb or "page" in fb


# Standard Defects

class TestMON004:
    fix = next(f for f in FIXTURES if f["id"] == "MON-004")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "standard"

    def test_violated_rule(self):
        vr = self.fix["violated_rule"].lower()
        assert "for" in vr or "flapping" in vr or "duration" in vr

    def test_expected_mentions_for(self):
        assert "for:" in self.fix["expected_feedback"] or "for'" in self.fix["expected_feedback"]


class TestMON005:
    fix = next(f for f in FIXTURES if f["id"] == "MON-005")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "standard"

    def test_violated_rule(self):
        assert "runbook" in self.fix["violated_rule"].lower()

    def test_expected_mentions_runbook_url(self):
        fb = self.fix["expected_feedback"].lower()
        assert "runbook" in fb


class TestMON006:
    fix = next(f for f in FIXTURES if f["id"] == "MON-006")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "standard"

    def test_violated_rule(self):
        assert "cardinality" in self.fix["violated_rule"].lower()

    def test_expected_mentions_user_id(self):
        assert "user_id" in self.fix["expected_feedback"]


class TestMON011:
    fix = next(f for f in FIXTURES if f["id"] == "MON-011")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "standard"

    def test_violated_rule(self):
        vr = self.fix["violated_rule"].lower()
        assert "grouping" in vr or "deduplication" in vr

    def test_expected_mentions_group_by(self):
        fb = self.fix["expected_feedback"].lower()
        assert "group" in fb


class TestMON014:
    """Single-replica `up == 0` labelled critical.

    Added 2026-08-13 with the fixture. It exists because the forward eval caught an agent
    stating the principle ("`up` is telemetry, not customer impact") and violating it in the
    same answer, so the assertions below pin the *reasoning* the feedback must contain, not
    just that the fixture parses.
    """
    fix = next(f for f in FIXTURES if f["id"] == "MON-014")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "standard"

    def test_violated_rule_is_about_page_worthiness(self):
        vr = self.fix["violated_rule"].lower()
        assert "page" in vr and ("redundanc" in vr or "impact" in vr)

    def test_feedback_downgrades_single_replica(self):
        """One of six replicas down is a redundancy event, not user impact."""
        fb = self.fix["expected_feedback"].lower()
        assert "warning" in fb or "ticket" in fb, \
            "must say the single-replica case is not page-worthy"
        assert "redundanc" in fb or "load balancer" in fb, \
            "must give the reason: the remaining replicas absorb it"

    def test_feedback_keeps_a_real_page_path(self):
        """Downgrading must not remove coverage -- it must relocate the page."""
        fb = self.fix["expected_feedback"]
        assert re.search(r"all replicas|count\(up", fb, re.I), \
            "must add a separate critical alert for the all-replicas-gone case"
        assert re.search(r"synthetic|probe", fb, re.I), \
            "must mention an external probe as the user-impact signal"
        assert "burn" in fb.lower(), \
            "the actual user-impact page belongs on the burn-rate alert"

    def test_feedback_requires_for_on_up_zero(self):
        """`up == 0` is true after a single failed scrape."""
        fb = self.fix["expected_feedback"]
        assert re.search(r"for:\s*5m|single failed scrape", fb, re.I)


class TestMON015:
    """`up == 0` with the topology deliberately withheld.

    The discriminating counterpart to MON-014: because the replica count is NOT in the context,
    a correct answer has to ask for it or answer conditionally. A fixture that states the
    deciding fact measures reading comprehension instead of judgement.
    """
    fix = next(f for f in FIXTURES if f["id"] == "MON-015")

    def test_context_withholds_the_replica_count(self):
        ctx = json.dumps(self.fix["context"]).lower()
        assert "replica" not in ctx and "instance" not in ctx, \
            "the whole point of this fixture is that the topology is unstated; putting it in " \
            "context turns the criterion into reading comprehension"

    def test_feedback_requires_asking_or_conditioning(self):
        fb = self.fix["expected_feedback"]
        assert re.search(r"\bASK\b|ask for", fb), "must allow/expect asking"
        assert re.search(r"conditional", fb, re.I), "must allow the conditional answer"
        assert "do not default to critical" in fb.lower()

    def test_feedback_keeps_the_for_and_absent_lessons(self):
        fb = self.fix["expected_feedback"]
        assert "for: 5m" in fb, "`up == 0` is true after a single failed scrape"
        assert "absent(" in fb and "sum(up" in fb, \
            "the all-down alert needs both halves"
        assert "empty vector" in fb, "must explain WHY count(up==1)==0 is silent"


class TestMON016:
    """Latency SLO request — the base model reliably reaches for a percentile."""
    fix = next(f for f in FIXTURES if f["id"] == "MON-016")

    def test_feedback_demands_a_proportion_not_a_percentile(self):
        fb = self.fix["expected_feedback"]
        assert re.search(r"PROPORTION OF REQUESTS FASTER|proportion of", fb, re.I)
        assert "histogram_quantile" in fb, "must explain what is wrong with the percentile"
        assert re.search(r"no countable bad event|no error budget", fb, re.I)

    def test_feedback_requires_one_instrument_and_valid_events(self):
        fb = self.fix["expected_feedback"]
        assert re.search(r"SAME histogram", fb, re.I), \
            "numerator and denominator must come from one instrument"
        assert re.search(r"\bVALID\b", fb), "must require the valid-event definition"
        assert re.search(r"instrumentation prerequisite", fb, re.I), \
            "must state the no-status-label case rather than papering over it"


class TestEveryFixtureHasAssertions:
    """Derived, not listed: a new fixture with no assertion class is untested coverage.

    MON-014 shipped covered only by the generic shape checks (parses, has the required
    fields) until a review pointed out it had no `TestMON014`. Those generic checks pass for
    any well-formed JSON, so "the fixture exists" was being read as "the fixture is tested".
    """

    def test_every_fixture_id_has_a_test_class(self):
        source = pathlib.Path(__file__).read_text(encoding="utf-8")
        missing = []
        for fx in FIXTURES:
            cls = "TestMON" + fx["id"].split("-")[1]
            if f"class {cls}" not in source:
                missing.append(f"{fx['id']} -> {cls}")
        assert not missing, (
            "fixtures with no per-fixture assertion class (generic shape checks pass for any "
            f"well-formed JSON, so this is untested coverage): {missing}")


# Good Practices

class TestMON007:
    fix = next(f for f in FIXTURES if f["id"] == "MON-007")

    def test_type_severity(self):
        assert self.fix["type"] == "good_practice"
        assert self.fix["severity"] == "none"

    def test_expected_positive(self):
        assert "no violation" in self.fix["expected_feedback"].lower()

    def test_expected_mentions_burn_rate(self):
        fb = self.fix["expected_feedback"].lower()
        assert "burn" in fb and "rate" in fb

    def test_burn_rate_arithmetic_is_correct(self):
        """Replaces a keyword check that could not fail on a wrong number.

        This fixture is a *good_practice* case: its expected_feedback is "No violations",
        so whatever it contains becomes the model answer. It previously shipped
        "budget exhausted in 2 hours" for a 14.4x burn -- off by more than an order of
        magnitude (the real figure is ~50h) -- and the assertion guarding it only checked
        that the words "burn" and "rate" appeared. A keyword test cannot catch a wrong
        number, because the keyword is still there.

        Every rate/duration pair in the fixture is now recomputed from the definitions:
            budget_consumed = burn_rate x window / slo_window
            time_to_exhaust = slo_window / burn_rate
        """
        blob = self.fix["code_snippet"] + "\n" + self.fix["expected_feedback"]
        slo_h = 30 * 24

        # the multiplier used in the expr must be a canonical Google SRE tier
        multipliers = {float(x) for x in re.findall(r"(\d+(?:\.\d+)?)\s*\*\s*0\.001", blob)}
        assert multipliers, "no burn-rate multiplier found in the expr"
        assert multipliers <= {14.4, 6.0, 3.0, 1.0}, (
            f"non-canonical burn-rate multiplier {multipliers}; the SRE tiers are "
            f"14.4/6/3/1 (see references/sli-slo-patterns.md)")

        # Every "exhausts in T" claim must equal slo_window / burn_rate.
        # Refutation detection is delegated to the linter rather than reimplemented here:
        # the fixture legitimately QUOTES the wrong figure in order to reject it, and two
        # independent implementations of "is this claim being refuted" would drift. The
        # first version of this loop got it wrong by using `blob.find(t_s)`, which returns
        # the first occurrence of the digit anywhere in the document, not the match
        # position -- so the exemption never applied where it was meant to.
        for m in re.finditer(
                r"(\d+(?:\.\d+)?)\s*x[^.\n]{0,80}?exhaust\w*[^.\n]{0,30}?"
                r"in\s*~?\s*(\d+(?:\.\d+)?)\s*(h|hours?|d|days?)", blob, re.I):
            if LINTER.claim_is_refuted(blob, m.span()):
                continue
            rate = float(m.group(1))
            unit = m.group(3)
            hours = float(m.group(2)) * (24 if unit.lower().startswith("d") else 1)
            want = slo_h / rate
            assert abs(hours - want) < 0.15 * want, (
                f"{rate}x exhausts a 30-day budget in {want:.0f}h, fixture says "
                f"{m.group(2)}{unit}")

        # every "N% of budget in W" claim must equal burn_rate x W / slo_window
        for rate_s, pct_s, win_s, unit in re.findall(
                r"(\d+(?:\.\d+)?)\s*x[^.\n]{0,60}?(\d+(?:\.\d+)?)\s*%[^.\n]{0,40}?"
                r"budget[^.\n]{0,30}?in\s*(\d+(?:\.\d+)?)\s*(h|hours?|d|days?)",
                blob, re.I):
            rate, pct = float(rate_s), float(pct_s)
            win_h = float(win_s) * (24 if unit.lower().startswith("d") else 1)
            want = rate * win_h / slo_h * 100
            assert abs(pct - want) < max(0.15 * want, 0.05), (
                f"{rate}x over {win_s}{unit} spends {want:.2f}% of budget, fixture "
                f"says {pct}%")

    def test_arithmetic_check_is_not_vacuous(self):
        """Negative control: the regexes above must actually match this fixture.

        Without this, a rewording that stops the patterns matching leaves
        test_burn_rate_arithmetic_is_correct passing over zero claims -- green, and
        measuring nothing.
        """
        blob = self.fix["code_snippet"] + "\n" + self.fix["expected_feedback"]
        assert re.search(r"(\d+(?:\.\d+)?)\s*\*\s*0\.001", blob), \
            "no burn-rate multiplier matched; the arithmetic test is inert"
        claims = re.findall(r"(\d+(?:\.\d+)?)\s*x[^.\n]{0,80}?exhaust", blob, re.I)
        assert claims, "no exhaustion claim matched; the arithmetic test is inert"

    def test_routing_is_not_stated_as_a_universal_rule(self):
        """The fixture is a model answer, so a vendor mapping phrased as a requirement
        there teaches it as one."""
        fb = self.fix["expected_feedback"]
        assert not re.search(r"critical must (?:go to|route to|page via) pagerduty", fb, re.I)


class TestMON008:
    fix = next(f for f in FIXTURES if f["id"] == "MON-008")

    def test_type_severity(self):
        assert self.fix["type"] == "good_practice"
        assert self.fix["severity"] == "none"

    def test_expected_positive(self):
        assert "no violation" in self.fix["expected_feedback"].lower()

    def test_expected_mentions_red(self):
        assert "RED" in self.fix["expected_feedback"] or "red" in self.fix["expected_feedback"].lower()


# Degradation & Workflow

class TestMON009:
    fix = next(f for f in FIXTURES if f["id"] == "MON-009")

    def test_type_severity(self):
        assert self.fix["type"] == "degradation_scenario"
        assert self.fix["severity"] == "none"

    def test_expected_forbids_claims(self):
        fb = self.fix["expected_feedback"].lower()
        assert "must not" in fb or "not claim" in fb

    def test_expected_mentions_degraded(self):
        assert "degraded" in self.fix["expected_feedback"].lower()


class TestMON010:
    fix = next(f for f in FIXTURES if f["id"] == "MON-010")

    def test_type_severity(self):
        assert self.fix["type"] == "workflow"
        assert self.fix["severity"] == "none"

    def test_expected_mentions_slo(self):
        fb = self.fix["expected_feedback"].lower()
        assert "slo" in fb or "sli" in fb

    def test_expected_mentions_routing(self):
        fb = self.fix["expected_feedback"].lower()
        assert "pagerduty" in fb or "routing" in fb


class TestMON012:
    fix = next(f for f in FIXTURES if f["id"] == "MON-012")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "standard"

    def test_violated_rule(self):
        vr = self.fix["violated_rule"].lower()
        assert "inhibition" in vr or "cascade" in vr

    def test_expected_feedback(self):
        fb = self.fix["expected_feedback"].lower()
        assert "inhibit_rules" in fb or "inhibition" in fb


class TestMON013:
    fix = next(f for f in FIXTURES if f["id"] == "MON-013")

    def test_type_severity(self):
        assert self.fix["type"] == "workflow"
        assert self.fix["severity"] == "none"

    def test_expected_mentions_budget(self):
        fb = self.fix["expected_feedback"].lower()
        assert "error budget" in fb or "budget" in fb

    def test_expected_mentions_decision(self):
        fb = self.fix["expected_feedback"].lower()
        assert "deploy" in fb or "incident-postmortem" in fb or "freeze" in fb or "renegotiate" in fb