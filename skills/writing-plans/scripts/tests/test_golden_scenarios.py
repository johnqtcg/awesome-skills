"""Golden fixture tests for writing-plans skill.

Validates that plan examples in golden/*.json match expected structural patterns.
All checks are pure text/regex — no network, no AI, no side effects.
"""

import glob
import json
import os
import re

import pytest

GOLDEN_DIR = os.path.join(os.path.dirname(__file__), "golden")


def load_golden_fixtures():
    """Load all golden fixture JSON files."""
    fixtures = []
    for path in sorted(glob.glob(os.path.join(GOLDEN_DIR, "*.json"))):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            data["_fixture_file"] = os.path.basename(path)
            fixtures.append(data)
    return fixtures


FIXTURES = load_golden_fixtures()
FIXTURE_IDS = [f["_fixture_file"] for f in FIXTURES]


@pytest.fixture(params=FIXTURES, ids=FIXTURE_IDS)
def golden_fixture(request):
    return request.param


class TestGoldenScenarios:
    """Validate structural patterns in golden plan examples."""

    def test_fixture_has_required_fields(self, golden_fixture):
        """Every fixture must declare scenario, mode, and plan_text."""
        required = ["scenario", "mode", "expected_result", "plan_text"]
        for field in required:
            assert field in golden_fixture, (
                f"Fixture {golden_fixture['_fixture_file']} missing required field: {field}"
            )

    def test_must_contain_patterns_present(self, golden_fixture):
        """Patterns in must_contain_patterns must appear in the plan text."""
        plan_text = golden_fixture["plan_text"]
        for pattern in golden_fixture.get("must_contain_patterns", []):
            assert re.search(pattern, plan_text), (
                f"Fixture {golden_fixture['_fixture_file']}: "
                f"expected pattern '{pattern}' not found in plan_text"
            )

    def test_must_not_contain_patterns_absent(self, golden_fixture):
        """Patterns in must_not_contain_patterns must NOT appear in the plan text."""
        plan_text = golden_fixture["plan_text"]
        for pattern in golden_fixture.get("must_not_contain_patterns", []):
            assert not re.search(pattern, plan_text), (
                f"Fixture {golden_fixture['_fixture_file']}: "
                f"forbidden pattern '{pattern}' found in plan_text"
            )


class TestGoodPlans:
    """Additional checks for plans expected to PASS."""

    @pytest.fixture(params=[f for f in FIXTURES if f["expected_result"] == "PASS"],
                    ids=[f["_fixture_file"] for f in FIXTURES if f["expected_result"] == "PASS"])
    def good_fixture(self, request):
        return request.param

    def test_file_path_labels_present(self, good_fixture):
        """Good plans (non-SKIP, non-Lite) should have file path labels."""
        if good_fixture["mode"] in ("SKIP", "Lite"):
            pytest.skip("SKIP/Lite mode plans have relaxed path label requirements")
        plan_text = good_fixture["plan_text"]
        assert re.search(r"\[(Existing|New|Speculative)\]", plan_text), (
            f"Good plan {good_fixture['_fixture_file']} should have [Existing]/[New]/[Speculative] labels"
        )

    def test_verification_commands_present(self, good_fixture):
        """Good plans should contain runnable verification commands."""
        if good_fixture["mode"] == "SKIP":
            pytest.skip("SKIP mode plans don't need verification commands")
        plan_text = good_fixture["plan_text"]
        has_run = re.search(r"Run:", plan_text)
        has_command = re.search(r"go test|pytest|npm test|make test", plan_text)
        has_command_label = re.search(r"\[command\]", plan_text)
        assert has_run or has_command or has_command_label, (
            f"Good plan {good_fixture['_fixture_file']} should have verification commands"
        )

    def test_no_complete_implementation_in_standard_deep(self, good_fixture):
        """Standard/Deep mode good plans should not contain complete function implementations."""
        if good_fixture["mode"] not in ("Standard", "Deep"):
            pytest.skip("Only Standard/Deep mode plans checked for implementation code")
        plan_text = good_fixture["plan_text"]
        # Check for Go function implementations (>3 lines)
        go_impl = re.search(r"func \w+\([^)]*\)\s*\{[^}]{100,}\}", plan_text, re.DOTALL)
        # Check for Python function implementations (>3 lines)
        py_impl = re.search(r"def \w+\([^)]*\):\s*\n(?:\s{4,}.*\n){4,}", plan_text)
        assert not go_impl and not py_impl, (
            f"Good plan {good_fixture['_fixture_file']} should not contain complete implementations"
        )


class TestBadPlans:
    """Verify that bad plans exhibit expected failures."""

    @pytest.fixture(params=[f for f in FIXTURES if f["expected_result"] == "FAIL"],
                    ids=[f["_fixture_file"] for f in FIXTURES if f["expected_result"] == "FAIL"])
    def bad_fixture(self, request):
        return request.param

    def test_has_expected_failures(self, bad_fixture):
        """Bad plans should declare what failures to expect."""
        assert "expected_failures" in bad_fixture or "failure_reasons" in bad_fixture, (
            f"Bad fixture {bad_fixture['_fixture_file']} should declare expected_failures or failure_reasons"
        )

    def test_bad_plan_violates_rules(self, bad_fixture):
        """Bad plans should actually violate at least one structural rule."""
        plan_text = bad_fixture["plan_text"]
        violations = []

        # Check B2: missing path labels
        has_file_refs = re.search(r"[`'][\w/]+\.\w+", plan_text)
        has_labels = re.search(r"\[(Existing|New|Speculative)\]", plan_text)
        if has_file_refs and not has_labels:
            violations.append("B2: missing file path labels")

        # Check B5: complete implementation code
        has_long_code = re.search(r"```\w*\n.{200,}```", plan_text, re.DOTALL)
        if has_long_code:
            violations.append("B5: contains complete implementation code")

        # Check B4: no verification commands
        has_verification = re.search(r"Run:|go test|pytest|npm test|\[command\]", plan_text)
        if not has_verification:
            violations.append("B4: no verification commands")

        assert len(violations) > 0, (
            f"Bad fixture {bad_fixture['_fixture_file']} should violate at least one rule "
            f"but no violations detected"
        )


class TestDegradedModePlans:
    """Verify degraded mode plans follow degraded rules."""

    @pytest.fixture(params=[f for f in FIXTURES if f.get("degraded", False)],
                    ids=[f["_fixture_file"] for f in FIXTURES if f.get("degraded", False)])
    def degraded_fixture(self, request):
        return request.param

    def test_declares_degraded_mode(self, degraded_fixture):
        plan_text = degraded_fixture["plan_text"]
        assert re.search(r"[Dd]egraded", plan_text), (
            "Degraded mode plan must declare degraded mode"
        )

    def test_uses_speculative_labels(self, degraded_fixture):
        plan_text = degraded_fixture["plan_text"]
        assert re.search(r"\[Speculative\]", plan_text), (
            "Degraded mode plan must use [Speculative] labels"
        )

    def test_no_existing_labels(self, degraded_fixture):
        plan_text = degraded_fixture["plan_text"]
        assert not re.search(r"\[Existing\]", plan_text), (
            "Degraded mode plan must not claim [Existing] (repo not verified)"
        )