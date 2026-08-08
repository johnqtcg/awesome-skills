"""Golden scenario tests for mongo-migration skill.

Validates behavioral coverage: each golden fixture exercises specific
rules in SKILL.md and reference files.
"""

import json
import pathlib
import pytest

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
    "id", "title", "type", "severity", "migration_snippet",
    "expected_feedback", "coverage_rules", "reference",
}


# ===========================================================================
# Fixture Integrity Tests
# ===========================================================================

class TestFixtureIntegrity:
    def test_minimum_fixture_count(self):
        assert len(FIXTURES) >= 11

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
# Critical Defects
# ===========================================================================

class TestMONGO001:
    """MONGO-001: Unbounded updateMany."""
    fix = next(f for f in FIXTURES if f["id"] == "MONGO-001")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "critical"

    def test_violated_rule(self):
        vr = self.fix["violated_rule"].lower()
        assert "batch" in vr or "_id" in vr

    def test_expected_mentions_wiredtiger(self):
        assert "wiredtiger" in self.fix["expected_feedback"].lower()


class TestMONGO002:
    """MONGO-002: No explicit write concern."""
    fix = next(f for f in FIXTURES if f["id"] == "MONGO-002")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "critical"

    def test_violated_rule(self):
        assert "write concern" in self.fix["violated_rule"].lower()

    def test_expected_mentions_majority(self):
        assert "majority" in self.fix["expected_feedback"].lower()


class TestMONGO003:
    """MONGO-003: No rollback — in-place type overwrite."""
    fix = next(f for f in FIXTURES if f["id"] == "MONGO-003")

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

class TestMONGO004:
    """MONGO-004: Validator strict before backfill."""
    fix = next(f for f in FIXTURES if f["id"] == "MONGO-004")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "standard"

    def test_violated_rule(self):
        vr = self.fix["violated_rule"].lower()
        assert "validator" in vr or "moderate" in vr

    def test_expected_mentions_moderate(self):
        assert "moderate" in self.fix["expected_feedback"].lower()


class TestMONGO005:
    """MONGO-005: Unique index without duplicate check."""
    fix = next(f for f in FIXTURES if f["id"] == "MONGO-005")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "standard"

    def test_violated_rule(self):
        vr = self.fix["violated_rule"].lower()
        assert "unique" in vr or "duplicate" in vr

    def test_expected_mentions_duplicate(self):
        assert "duplicate" in self.fix["expected_feedback"].lower()


class TestMONGO006:
    """MONGO-006: In-place field type change."""
    fix = next(f for f in FIXTURES if f["id"] == "MONGO-006")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "standard"

    def test_violated_rule(self):
        vr = self.fix["violated_rule"].lower()
        assert "type" in vr or "dual" in vr

    def test_expected_mentions_dual(self):
        fb = self.fix["expected_feedback"].lower()
        assert "dual" in fb or "new-field" in fb


class TestMONGO011:
    """MONGO-011: Index build without lag monitoring."""
    fix = next(f for f in FIXTURES if f["id"] == "MONGO-011")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "standard"

    def test_violated_rule(self):
        vr = self.fix["violated_rule"].lower()
        assert "index" in vr or "replication" in vr or "monitor" in vr

    def test_expected_mentions_lag(self):
        fb = self.fix["expected_feedback"].lower()
        assert "replication" in fb or "lag" in fb


class TestMONGO013:
    """MONGO-013: Sharded bulk write without batching or balancer awareness."""
    fix = next(f for f in FIXTURES if f["id"] == "MONGO-013")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "standard"

    def test_violated_rule(self):
        vr = self.fix["violated_rule"].lower()
        assert "batch" in vr or "_id" in vr

    def test_expected_mentions_shard(self):
        assert "shard" in self.fix["expected_feedback"].lower()

    def test_expected_mentions_balancer(self):
        assert "balancer" in self.fix["expected_feedback"].lower()


# ===========================================================================
# Good Practices
# ===========================================================================

class TestMONGO007:
    """MONGO-007: Well-formed phased migration."""
    fix = next(f for f in FIXTURES if f["id"] == "MONGO-007")

    def test_type_severity(self):
        assert self.fix["type"] == "good_practice"
        assert self.fix["severity"] == "none"

    def test_expected_positive(self):
        assert "no violation" in self.fix["expected_feedback"].lower()


class TestMONGO008:
    """MONGO-008: Good rolling index build."""
    fix = next(f for f in FIXTURES if f["id"] == "MONGO-008")

    def test_type_severity(self):
        assert self.fix["type"] == "good_practice"
        assert self.fix["severity"] == "none"

    def test_expected_positive(self):
        assert "no violation" in self.fix["expected_feedback"].lower()

    def test_expected_mentions_rolling(self):
        assert "rolling" in self.fix["expected_feedback"].lower()


# ===========================================================================
# Degradation & Workflow
# ===========================================================================

class TestMONGO009:
    """MONGO-009: Degraded mode."""
    fix = next(f for f in FIXTURES if f["id"] == "MONGO-009")

    def test_type_severity(self):
        assert self.fix["type"] == "degradation_scenario"
        assert self.fix["severity"] == "none"

    def test_expected_forbids_claims(self):
        fb = self.fix["expected_feedback"].lower()
        assert "must not" in fb or "not claim" in fb

    def test_expected_mentions_degraded(self):
        assert "degraded" in self.fix["expected_feedback"].lower()


class TestMONGO010:
    """MONGO-010: Field type migration workflow."""
    fix = next(f for f in FIXTURES if f["id"] == "MONGO-010")

    def test_type_severity(self):
        assert self.fix["type"] == "workflow"
        assert self.fix["severity"] == "none"

    def test_expected_mentions_new_field(self):
        fb = self.fix["expected_feedback"]
        assert "amount_v2" in fb or "new-field" in fb.lower()

    def test_expected_mentions_phases(self):
        fb = self.fix["expected_feedback"].lower()
        assert "phase" in fb or "step" in fb or "(1)" in fb


class TestMONGO012:
    """MONGO-012: reshardCollection workflow."""
    fix = next(f for f in FIXTURES if f["id"] == "MONGO-012")

    def test_type_severity(self):
        assert self.fix["type"] == "workflow"
        assert self.fix["severity"] == "none"

    def test_expected_mentions_reshard(self):
        fb = self.fix["expected_feedback"].lower()
        assert "reshardcollection" in fb or "reshard" in fb

    def test_expected_mentions_cutover(self):
        fb = self.fix["expected_feedback"].lower()
        assert "cutover" in fb or "lock" in fb


class TestCoverageDocMatchesReality:
    """COVERAGE.md is prose about machine-checkable facts, which is exactly the shape
    that drifts: it still claimed 97 tests, two suites, and a TTL rule that was false,
    long after the checker, the fact guards, the live matrix and the mutation sweep
    existed. Everything derivable is derived."""

    import pathlib as _p
    COVERAGE = _p.Path(__file__).resolve().parent / "COVERAGE.md"

    def _text(self):
        return self.COVERAGE.read_text(encoding="utf-8")

    def _mod(self, name, rel):
        import importlib.util, sys, pathlib
        path = pathlib.Path(__file__).resolve().parents[1] / rel
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
        return mod

    def test_every_stated_mutation_count_agrees_with_the_sweep(self):
        """Checks EVERY count in the file, not that the right one appears somewhere: a
        correct figure elsewhere in the document hides a contradictory one."""
        import re
        n = len(self._mod("mongo_sweep_probe", "mutation_sweep.py").MUTATIONS)
        text = self._text()
        stated = {int(m.group(1)) for m in re.finditer(r"\b(\d+)\s*mutations\b", text)}
        for m in re.finditer(r"\b(\d+)\s*/\s*(\d+)\s+mutations\s+killed", text):
            stated.update({int(m.group(1)), int(m.group(2))})
        assert stated == {n}, f"sweep defines {n}; COVERAGE.md states {sorted(stated)}"

    def test_rule_table_matches_the_checker_registry(self):
        text = self._text()
        documented = {}
        for ln in text.splitlines():
            if ln.startswith("| MG") and ln.count("|") >= 4:
                parts = [c.strip() for c in ln.split("|")]
                documented[parts[1]] = parts[2]
        actual = {r.code: r.severity
                  for r in self._mod("mongo_lint_probe", "lint_migration.py").RULES}
        assert documented == actual, (
            "COVERAGE.md's rule table has drifted from the registry.\n"
            f"  only in doc:      {sorted(set(documented) - set(actual))}\n"
            f"  only in registry: {sorted(set(actual) - set(documented))}"
        )

    def test_stated_per_suite_and_total_offline_counts_are_current(self):
        """The gap a reviewer found: the table said 47 golden tests and 251 offline
        while pytest collected 51 and 255, and nothing asserted either number, so the
        wrong figures rode along with a fully green suite. The live matrix is excluded --
        its count scales with how many servers happen to be reachable."""
        import subprocess, sys, pathlib as _pl
        tests_dir = _pl.Path(__file__).resolve().parent
        text = self._text()
        total = 0
        for suite in sorted(tests_dir.glob("test_*.py")):
            if suite.name == "test_mongo_server_matrix.py":
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

    def test_stated_live_count_is_current_when_the_matrix_is_full(self):
        """The live figure drifted twice (104 stated, 108 collected) because the updater
        deliberately skipped it and nothing asserted it. Asserted now — but only when
        every supported major is reachable, since the count is a function of that."""
        import importlib.util, subprocess, sys, pathlib as _pl
        tests_dir = _pl.Path(__file__).resolve().parent
        spec = importlib.util.spec_from_file_location("ms_cov", tests_dir / "mongo_server.py")
        ms = importlib.util.module_from_spec(spec)
        sys.modules["ms_cov"] = ms
        spec.loader.exec_module(ms)
        found = ms.discover_all()
        if len(found) != len(ms.SUPPORTED):
            pytest.skip(f"{len(found)}/{len(ms.SUPPORTED)} majors reachable; the live "
                        "count is environment-dependent")
        out = subprocess.run(
            [sys.executable, "-m", "pytest", str(tests_dir / "test_mongo_server_matrix.py"),
             "--collect-only", "-q", "-p", "no:cacheprovider"],
            capture_output=True, text=True, cwd=tests_dir.parents[1])
        n = sum(1 for ln in out.stdout.splitlines() if "::" in ln)
        text = self._text()
        row = next((ln for ln in text.splitlines()
                    if ln.startswith("| `test_mongo_server_matrix.py` |")), None)
        assert row is not None
        assert int(row.split("|")[2].strip()) == n, (
            f"COVERAGE.md states {row.split('|')[2].strip()} live tests; "
            f"pytest collects {n}. Run update_coverage_counts.py with the full matrix up."
        )
        assert f"{n} across MongoDB" in text, f"the prose must also state {n}"

    def test_every_checker_rule_has_a_mutation(self):
        """"22/22 killed" does not mean every rule was mutation-verified. MG016 was
        added without one, so the sweep could not have detected its removal."""
        import re
        sweep = self._mod("mongo_sweep_probe2", "mutation_sweep.py")
        blob = " ".join(m.anchor + " " + m.replacement + " " + m.breaks
                        for m in sweep.MUTATIONS)
        rules = {r.code for r in self._mod("mongo_lint_probe2", "lint_migration.py").RULES}
        # MG010 is prose-only (see TestRuleRegistry); the drift guards cover it.
        uncovered = sorted(r for r in rules - {"MG010"} if r not in blob)
        assert not uncovered, (
            f"checker rules with no mutation, so their removal would go unnoticed: "
            f"{uncovered}"
        )

    def test_fixture_and_fact_counts_are_current(self):
        import glob, pathlib as _pl
        text = self._text()
        n_fix = len(glob.glob(str(_pl.Path(__file__).resolve().parent / "golden" / "*.json")))
        assert f"{n_fix} golden fixtures" in text, f"must state '{n_fix} golden fixtures'"
        n_facts = len(self._mod("mongo_facts_probe", "tests/test_mongo_facts_drift.py").FACTS)
        assert f"{n_facts} pinned facts" in text, f"must state '{n_facts} pinned facts'"

    def test_it_no_longer_claims_the_superseded_shape(self):
        """The stale version described two suites and 97 tests."""
        text = self._text()
        assert "97 tests" not in text or "Before 2026-08" in text
        for gone in ["TTL modification requires drop", "rolling fixture is good practice"]:
            assert gone not in text
