"""Golden scenario tests for pg-migration skill.

Validates behavioral coverage: each golden fixture exercises specific
rules in SKILL.md and reference files.
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
    path = SKILL_DIR / "scripts" / "lint_migration.py"
    spec = importlib.util.spec_from_file_location("pg_lint_golden", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["pg_lint_golden"] = mod
    spec.loader.exec_module(mod)
    return mod


LINT = _load_linter()


def _all_docs_lower() -> str:
    parts = [SKILL_MD]
    for f in sorted(REFS_DIR.glob("*.md")):
        parts.append(f.read_text(encoding="utf-8"))
    return "\n".join(parts).lower()


def _load_fixtures() -> list[dict]:
    fixtures = []
    for f in sorted(GOLDEN_DIR.glob("*.json")):
        fixtures.append(json.loads(f.read_text(encoding="utf-8")))
    return fixtures


ALL_DOCS_LOWER = _all_docs_lower()
FIXTURES = _load_fixtures()

VALID_TYPES = {"defect", "good_practice", "degradation_scenario", "workflow"}
VALID_SEVERITIES = {"critical", "standard", "hygiene", "none"}
REQUIRED_FIELDS = {
    "id", "title", "type", "severity", "migration_snippet",
    "expected_feedback", "coverage_rules", "reference", "expected_lint_codes", "primary_lint_code",
}


# ===========================================================================
# Fixture Integrity Tests
# ===========================================================================

class TestFixtureIntegrity:
    def test_minimum_fixture_count(self):
        assert len(FIXTURES) >= 9

    def test_required_fields(self):
        for fix in FIXTURES:
            missing = REQUIRED_FIELDS - set(fix.keys())
            assert not missing, f"{fix['id']}: missing fields {missing}"

    def test_valid_types(self):
        for fix in FIXTURES:
            assert fix["type"] in VALID_TYPES, f"{fix['id']}: invalid type"

    def test_valid_severities(self):
        for fix in FIXTURES:
            assert fix["severity"] in VALID_SEVERITIES, f"{fix['id']}: invalid severity"

    def test_defect_severity_not_none(self):
        for fix in FIXTURES:
            if fix["type"] == "defect":
                assert fix["severity"] != "none", f"{fix['id']}: defect must have severity"

    def test_non_defect_severity_none(self):
        for fix in FIXTURES:
            if fix["type"] in ("good_practice", "degradation_scenario", "workflow"):
                assert fix["severity"] == "none", f"{fix['id']}: non-defect must be none"

    def test_unique_ids(self):
        ids = [f["id"] for f in FIXTURES]
        assert len(ids) == len(set(ids))

    def test_coverage_rules_findable(self):
        for fix in FIXTURES:
            for rule in fix["coverage_rules"]:
                assert rule.lower() in ALL_DOCS_LOWER, \
                    f"{fix['id']}: coverage rule '{rule}' not found in docs"


# ===========================================================================
# Behavioral: run the real checker on each snippet.
#
# Everything above validates fixture shape and prose. These tests are the ones
# that can actually be wrong about PostgreSQL: expected_lint_codes is written by
# hand from reading the snippet, and the linter must agree. When they disagree,
# one of the two is wrong and the disagreement has to be resolved rather than
# absorbed -- which is exactly what a suite asserting a fixture's own
# expected_feedback text can never surface.
# ===========================================================================

def _emitted_codes(fix: dict) -> set[str]:
    return {f.code for f in LINT.Linter().lint(fix["migration_snippet"])}


@pytest.mark.parametrize("fix", FIXTURES, ids=[f["id"] for f in FIXTURES])
class TestLinterAgreesWithFixtures:
    def test_expected_codes_are_declared_as_a_list(self, fix):
        assert isinstance(fix["expected_lint_codes"], list)

    def test_expected_codes_are_known_rules(self, fix):
        for code in fix["expected_lint_codes"]:
            assert code in LINT.RULES_BY_CODE, \
                f"{fix['id']}: unknown rule code {code}"

    def test_linter_emits_exactly_the_expected_codes(self, fix):
        emitted = _emitted_codes(fix)
        expected = set(fix["expected_lint_codes"])
        assert emitted == expected, (
            f"{fix['id']}: linter and fixture disagree.\n"
            f"  expected: {sorted(expected)}\n"
            f"  emitted:  {sorted(emitted)}\n"
            f"  missing:  {sorted(expected - emitted)}\n"
            f"  extra:    {sorted(emitted - expected)}"
        )

    def test_defect_fixtures_actually_trip_a_rule(self, fix):
        """A fixture labelled 'defect' whose snippet lints clean is not testing
        anything -- either the snippet is fine or no rule covers it."""
        if fix["type"] != "defect":
            pytest.skip("not a defect fixture")
        assert fix["expected_lint_codes"], (
            f"{fix['id']} is a defect fixture with no expected findings"
        )

    def test_good_practice_fixtures_lint_clean(self, fix):
        """The positive exemplars must survive the skill's own checker. Fixture 007
        previously claimed 'no violations' while containing a SET LOCAL no-op and an
        unscoped conname guard."""
        if fix["type"] != "good_practice":
            pytest.skip("not a good_practice fixture")
        assert _emitted_codes(fix) == set(), (
            f"{fix['id']} is labelled good_practice but the linter reports "
            f"{sorted(_emitted_codes(fix))}"
        )

    def test_primary_code_is_declared_for_defects(self, fix):
        if fix["type"] != "defect":
            assert fix["primary_lint_code"] is None
            return
        assert fix["primary_lint_code"] in fix["expected_lint_codes"], (
            f"{fix['id']}: primary_lint_code must be one of the expected codes"
        )

    def test_severity_matches_the_primary_rule(self, fix):
        """The fixture's `severity` labels the defect the fixture is ABOUT, not the
        worst thing anywhere in the snippet. A realistic snippet often also lacks a
        lock_timeout (critical) while demonstrating a standard-severity defect --
        those are different questions and must not be collapsed."""
        if fix["type"] != "defect":
            pytest.skip("not a defect fixture")
        primary = fix["primary_lint_code"]
        assert LINT.RULES_BY_CODE[primary].severity == fix["severity"], (
            f"{fix['id']}: declared severity {fix['severity']!r} but its primary "
            f"rule {primary} is {LINT.RULES_BY_CODE[primary].severity!r}"
        )

    def test_primary_rule_actually_fires(self, fix):
        if fix["type"] != "defect":
            pytest.skip("not a defect fixture")
        assert fix["primary_lint_code"] in _emitted_codes(fix), (
            f"{fix['id']}: primary rule {fix['primary_lint_code']} did not fire"
        )


# ===========================================================================
# Critical Defects
# ===========================================================================

class TestPG001:
    """PG-001: Missing lock_timeout."""
    fix = next(f for f in FIXTURES if f["id"] == "PG-001")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "critical"

    def test_violated_rule(self):
        assert "lock_timeout" in self.fix["violated_rule"].lower()

    def test_expected_mentions_timeout(self):
        assert "lock_timeout" in self.fix["expected_feedback"].lower()


class TestPG002:
    """PG-002: Index without CONCURRENTLY."""
    fix = next(f for f in FIXTURES if f["id"] == "PG-002")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "critical"

    def test_violated_rule(self):
        assert "concurrently" in self.fix["violated_rule"].lower()

    def test_expected_mentions_concurrently(self):
        assert "concurrently" in self.fix["expected_feedback"].lower()


class TestPG003:
    """PG-003: Constraint without NOT VALID."""
    fix = next(f for f in FIXTURES if f["id"] == "PG-003")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        # Standard, not critical: SKILL.md §8 places the NOT VALID two-step in the
        # Standard tier. The fixture previously claimed critical, contradicting the
        # scorecard it was meant to exercise.
        assert self.fix["severity"] == "standard"

    def test_expected_mentions_not_valid(self):
        fb = self.fix["expected_feedback"].lower()
        assert "not valid" in fb

    def test_does_not_claim_fk_takes_access_exclusive(self):
        """ADD FOREIGN KEY is ShareRowExclusive on both tables. The original fixture
        asserted AccessExclusiveLock here, which is the error this hardening fixed."""
        fb = self.fix["expected_feedback"].lower()
        assert "sharerowexclusive" in fb.replace(" ", "")
        assert "accessexclusivelock while scanning" not in fb

    def test_expected_mentions_two_step(self):
        fb = self.fix["expected_feedback"].lower()
        assert "two-step" in fb or "validate" in fb


class TestPG004:
    """PG-004: Missing rollback plan."""
    fix = next(f for f in FIXTURES if f["id"] == "PG-004")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "critical"

    def test_violated_rule(self):
        assert "rollback" in self.fix["violated_rule"].lower()

    def test_expected_mentions_irreversible(self):
        assert "irreversible" in self.fix["expected_feedback"].lower()


# ===========================================================================
# Standard Defects
# ===========================================================================

class TestPG005:
    """PG-005: ALTER COLUMN TYPE on large table."""
    fix = next(f for f in FIXTURES if f["id"] == "PG-005")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "standard"

    def test_expected_mentions_rewrite(self):
        fb = self.fix["expected_feedback"].lower()
        assert "rewrite" in fb

    def test_expected_mentions_pg_repack(self):
        fb = self.fix["expected_feedback"].lower()
        assert "pg_repack" in fb or "create-swap" in fb


class TestPG006:
    """PG-006: ADD CONSTRAINT IF NOT EXISTS syntax."""
    fix = next(f for f in FIXTURES if f["id"] == "PG-006")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "standard"

    def test_expected_mentions_syntax_error(self):
        fb = self.fix["expected_feedback"].lower()
        assert "syntax" in fb or "not support" in fb

    def test_expected_suggests_do_block(self):
        fb = self.fix["expected_feedback"].lower()
        assert "do block" in fb or "pg_constraint" in fb


class TestPG011:
    """PG-011: NOT NULL without CHECK shortcut."""
    fix = next(f for f in FIXTURES if f["id"] == "PG-011")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "standard"

    def test_expected_mentions_check(self):
        fb = self.fix["expected_feedback"].lower()
        assert "check" in fb

    def test_expected_mentions_not_valid(self):
        fb = self.fix["expected_feedback"].lower()
        assert "not valid" in fb


# ===========================================================================
# Good Practices
# ===========================================================================

class TestPG007:
    """PG-007: Well-formed phased migration."""
    fix = next(f for f in FIXTURES if f["id"] == "PG-007")

    def test_type_severity(self):
        assert self.fix["type"] == "good_practice"
        assert self.fix["severity"] == "none"

    def test_expected_positive(self):
        assert "no violation" in self.fix["expected_feedback"].lower()


class TestPG008:
    """PG-008: Good CONCURRENTLY usage."""
    fix = next(f for f in FIXTURES if f["id"] == "PG-008")

    def test_type_severity(self):
        assert self.fix["type"] == "good_practice"
        assert self.fix["severity"] == "none"

    def test_expected_positive(self):
        assert "no violation" in self.fix["expected_feedback"].lower()

    def test_expected_mentions_concurrently(self):
        assert "concurrently" in self.fix["expected_feedback"].lower()


# ===========================================================================
# Degradation & Workflow
# ===========================================================================

class TestPG009:
    """PG-009: Degraded mode."""
    fix = next(f for f in FIXTURES if f["id"] == "PG-009")

    def test_type_severity(self):
        assert self.fix["type"] == "degradation_scenario"
        assert self.fix["severity"] == "none"

    def test_expected_forbids_claims(self):
        fb = self.fix["expected_feedback"].lower()
        assert "must not" in fb or "not claim" in fb

    def test_expected_mentions_degraded(self):
        assert "degraded" in self.fix["expected_feedback"].lower()


class TestPG010:
    """PG-010: Multi-step workflow."""
    fix = next(f for f in FIXTURES if f["id"] == "PG-010")

    def test_type_severity(self):
        assert self.fix["type"] == "workflow"
        assert self.fix["severity"] == "none"

    def test_expected_mentions_phases(self):
        fb = self.fix["expected_feedback"].lower()
        assert "phase" in fb or "step" in fb

    def test_expected_mentions_backfill(self):
        fb = self.fix["expected_feedback"].lower()
        assert "backfill" in fb


class TestCoverageDocMatchesReality:
    """COVERAGE.md is hand-written prose about machine-checkable facts, which is
    exactly the shape that drifts: a review found it claiming 441 tests when 439 were
    collected. Counts that legitimately vary (test totals scale with how many servers
    are reachable) stay as a documented regenerate recipe; everything deterministic is
    asserted here instead of trusted."""

    COVERAGE = pathlib.Path(__file__).resolve().parent / "COVERAGE.md"

    def _text(self):
        return self.COVERAGE.read_text(encoding="utf-8")

    def test_fixture_table_matches_the_fixtures_on_disk(self):
        text = self._text()
        for path in sorted(GOLDEN_DIR.glob("*.json")):
            fix = json.loads(path.read_text(encoding="utf-8"))
            row = next((ln for ln in text.splitlines()
                        if ln.startswith(f"| {fix['id']} |")), None)
            assert row is not None, f"{fix['id']} has no row in COVERAGE.md"
            declared = row.rsplit("|", 2)[-2].strip()
            expected = ", ".join(fix.get("expected_lint_codes") or []) or "*(none)*"
            assert declared == expected, (
                f"{fix['id']}: COVERAGE.md says {declared!r}, the fixture says "
                f"{expected!r}"
            )

    def test_every_fixture_has_a_row(self):
        text = self._text()
        n = sum(1 for ln in text.splitlines() if ln.startswith("| PG-0"))
        assert n == len(list(GOLDEN_DIR.glob("*.json"))), (
            "COVERAGE.md's fixture table and scripts/tests/golden/ disagree on count"
        )

    def test_rule_table_matches_the_linter_registry(self):
        text = self._text()
        documented = {}
        for ln in text.splitlines():
            if ln.startswith("| PG0") and ln.count("|") >= 4:
                parts = [c.strip() for c in ln.split("|")]
                documented[parts[1]] = parts[2]
        actual = {r.code: r.severity for r in LINT.RULES}
        assert documented == actual, (
            "COVERAGE.md's rule table has drifted from the registry.\n"
            f"  only in doc:      {sorted(set(documented) - set(actual))}\n"
            f"  only in registry: {sorted(set(actual) - set(documented))}\n"
            f"  severity differs: "
            f"{sorted(c for c in set(documented) & set(actual) if documented[c] != actual[c])}"
        )


    def test_stated_fact_and_forbid_counts_are_current(self):
        """COVERAGE.md's prose about test_pg_facts_drift.py is a claim about another
        file's contents. It said "24 facts pinned" when 32 existed."""
        import importlib.util
        path = pathlib.Path(__file__).resolve().parent / "test_pg_facts_drift.py"
        spec = importlib.util.spec_from_file_location("pg_facts_drift_probe", path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["pg_facts_drift_probe"] = mod
        spec.loader.exec_module(mod)
        n_facts = len(mod.FACTS)
        n_forbid = sum(1 for f in mod.FACTS if f.forbid)
        text = self._text()
        assert f"{n_facts} facts pinned" in text, (
            f"COVERAGE.md must state '{n_facts} facts pinned'"
        )
        words = {1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six",
                 7: "Seven", 8: "Eight", 9: "Nine", 10: "Ten", 11: "Eleven",
                 12: "Twelve", 13: "Thirteen", 14: "Fourteen", 15: "Fifteen"}
        spelled = words.get(n_forbid, str(n_forbid))
        assert f"{spelled} carry a `forbid` pattern" in text, (
            f"COVERAGE.md must say '{spelled} carry a `forbid` pattern' "
            f"({n_forbid} facts do)"
        )

    def test_every_mutation_id_appears_in_the_coverage_map(self):
        """The 'Coverage by area' line enumerates mutation IDs. It stopped at M28 while
        M29-M51 existed, so a reader auditing coverage saw a map of half the sweep."""
        import re as _re
        text = self._text()
        m = _re.search(r"Coverage by area:(.+?)\.\n", text, _re.S)
        assert m, "COVERAGE.md no longer has a 'Coverage by area' map"
        listed = set()
        for lo, hi in _re.findall(r"M(\d+)[–-]M(\d+)", m.group(1)):
            listed.update(f"M{n:02d}" for n in range(int(lo), int(hi) + 1))
        listed.update(_re.findall(r"M\d{2}", m.group(1)))
        actual = {mm.mid for mm in self._mutations()}
        missing = sorted(actual - listed)
        assert not missing, f"mutations absent from the coverage map: {missing}"

    def _mutations(self):
        import importlib.util
        path = pathlib.Path(__file__).resolve().parents[1] / "mutation_sweep.py"
        spec = importlib.util.spec_from_file_location("pg_mutation_sweep2", path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["pg_mutation_sweep2"] = mod
        spec.loader.exec_module(mod)
        return mod.MUTATIONS

    def _mutation_count(self):
        import importlib.util
        path = pathlib.Path(__file__).resolve().parents[1] / "mutation_sweep.py"
        spec = importlib.util.spec_from_file_location("pg_mutation_sweep", path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["pg_mutation_sweep"] = mod
        spec.loader.exec_module(mod)
        return len(mod.MUTATIONS)

    def test_every_stated_mutation_count_agrees_with_the_sweep(self):
        """Checks EVERY count in the file, not that the right one appears somewhere.

        The weaker form ("is '45 mutations' present?") passed while the file also said
        "42/45 mutations killed" three lines away -- an assertion satisfied by a
        correct mention elsewhere cannot see a contradictory one.
        """
        n = self._mutation_count()
        text = self._text()
        stated = set()
        for m in re.finditer(r"\b(\d+)\s*mutations\b", text):
            stated.add(int(m.group(1)))
        for m in re.finditer(r"\b(\d+)\s*/\s*(\d+)\s+mutations\s+killed", text):
            stated.add(int(m.group(1)))
            stated.add(int(m.group(2)))
        assert stated, "COVERAGE.md states no mutation count at all"
        assert stated == {n}, (
            f"the sweep defines {n} mutations; COVERAGE.md states {sorted(stated)}. "
            "Every mention must agree -- a single stale or mangled figure is the drift."
        )

    def test_stated_per_suite_and_total_offline_counts_are_current(self):
        """Collected counts are derivable, so they are derived. The live matrix is
        excluded: its count scales with how many servers happen to be reachable."""
        import subprocess
        tests_dir = pathlib.Path(__file__).resolve().parent
        text = self._text()
        total = 0
        for suite in sorted(tests_dir.glob("test_*.py")):
            if suite.name == "test_pg_server_matrix.py":
                continue
            out = subprocess.run(
                [sys.executable, "-m", "pytest", str(suite), "--collect-only", "-q",
                 "-p", "no:cacheprovider"],
                capture_output=True, text=True, cwd=tests_dir.parents[1])
            n = sum(1 for ln in out.stdout.splitlines() if "::" in ln)
            total += n
            row = next((ln for ln in text.splitlines()
                        if ln.startswith(f"| `{suite.name}` |")), None)
            assert row is not None, f"{suite.name} has no row in COVERAGE.md"
            declared = int(row.split("|")[2].strip())
            assert declared == n, (
                f"{suite.name}: COVERAGE.md says {declared}, pytest collects {n}"
            )
        assert f"**{total} offline tests**" in text, (
            f"COVERAGE.md must state '**{total} offline tests**'"
        )
