"""Golden scenario tests for the mysql-migration skill.

Two layers, with different evidentiary weight:

1. **Fixture integrity + rule coverage** — schema, type/severity constraints,
   and that every `coverage_rule` phrase is findable in the docs. This proves
   the corpus is well-formed and the docs mention the concept. It does NOT
   prove any advice is correct: a fixture asserting a wrong practice would
   still pass, which is exactly how MIG-008 shipped a reversed gh-ost
   invocation as a "good practice" until the 2026-08-06 audit.

2. **Linter verdicts (`lint` block)** — each fixture's `migration_snippet` is
   run through scripts/lint_migration.py at the fixture's MySQL version, and
   the reported check IDs are asserted against `must_report` / `must_not_report`.
   This layer is falsifiable: it fails when the checker's judgement on real
   statements changes.

Neither layer invokes a model. Model-facing evaluation is a separate,
unimplemented track — see scripts/tests/COVERAGE.md.
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
LINTER_PATH = SKILL_DIR / "scripts" / "lint_migration.py"


def _load_linter():
    """Import lint_migration.py by path (pytest runs with --import-mode=importlib).

    Must be registered in sys.modules before exec_module: the module pairs
    `from __future__ import annotations` with @dataclass, whose field resolution
    looks the module up by name.
    """
    spec = importlib.util.spec_from_file_location("mysql_migration_linter_golden", LINTER_PATH)
    assert spec and spec.loader, f"cannot load {LINTER_PATH}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


LINT = _load_linter()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _all_docs_lower() -> str:
    """Concatenate SKILL.md + all references, lowercased and whitespace-normalized.

    Collapsing runs of whitespace to a single space means a coverage phrase still
    matches when the sentence containing it is re-wrapped. Without this, a purely
    cosmetic reflow of a paragraph fails the suite while nothing about the
    documented rule has changed.
    """
    parts = [SKILL_MD]
    for f in sorted(REFS_DIR.glob("*.md")):
        parts.append(f.read_text(encoding="utf-8"))
    return re.sub(r"\s+", " ", "\n".join(parts).lower())


def _load_fixtures() -> list[dict]:
    """Load all golden fixture JSON files, sorted by filename."""
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
    "expected_feedback", "coverage_rules", "reference", "lint",
}


# ===========================================================================
# Fixture Integrity Tests
# ===========================================================================

class TestFixtureIntegrity:
    """Meta-level validation on all fixtures."""

    def test_minimum_fixture_count(self):
        assert len(FIXTURES) >= 15, f"Expected ≥15 fixtures, found {len(FIXTURES)}"

    def test_required_fields(self):
        for fix in FIXTURES:
            missing = REQUIRED_FIELDS - set(fix.keys())
            assert not missing, f"{fix['id']}: missing fields {missing}"

    def test_valid_types(self):
        for fix in FIXTURES:
            assert fix["type"] in VALID_TYPES, \
                f"{fix['id']}: invalid type '{fix['type']}'"

    def test_valid_severities(self):
        for fix in FIXTURES:
            assert fix["severity"] in VALID_SEVERITIES, \
                f"{fix['id']}: invalid severity '{fix['severity']}'"

    def test_defect_severity_not_none(self):
        for fix in FIXTURES:
            if fix["type"] == "defect":
                assert fix["severity"] != "none", \
                    f"{fix['id']}: defect must have non-none severity"

    def test_non_defect_severity_none(self):
        for fix in FIXTURES:
            if fix["type"] in ("good_practice", "degradation_scenario", "workflow"):
                assert fix["severity"] == "none", \
                    f"{fix['id']}: {fix['type']} must have severity=none"

    def test_unique_ids(self):
        ids = [f["id"] for f in FIXTURES]
        assert len(ids) == len(set(ids)), f"duplicate IDs: {ids}"

    def test_coverage_rules_findable(self):
        """Every coverage_rule phrase must be findable in combined docs."""
        for fix in FIXTURES:
            for rule in fix["coverage_rules"]:
                needle = re.sub(r"\s+", " ", rule.lower())
                assert needle in ALL_DOCS_LOWER, \
                    f"{fix['id']}: coverage rule '{rule}' not found in docs"


# ===========================================================================
# Per-Fixture Behavioral Tests: Critical Defects
# ===========================================================================

class TestMIG001:
    """MIG-001: Missing session guards."""
    fix = next(f for f in FIXTURES if f["id"] == "MIG-001")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "critical"

    def test_violated_rule(self):
        assert "session guard" in self.fix["violated_rule"].lower() or \
               "session" in self.fix["violated_rule"].lower()

    def test_expected_mentions_guards(self):
        fb = self.fix["expected_feedback"].lower()
        assert "lock_wait_timeout" in fb


class TestMIG002:
    """MIG-002: Implicit algorithm."""
    fix = next(f for f in FIXTURES if f["id"] == "MIG-002")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "critical"

    def test_violated_rule(self):
        assert "algorithm" in self.fix["violated_rule"].lower()

    def test_expected_mentions_instant(self):
        fb = self.fix["expected_feedback"].lower()
        assert "instant" in fb or "algorithm" in fb


class TestMIG003:
    """MIG-003: NOT NULL without phased approach."""
    fix = next(f for f in FIXTURES if f["id"] == "MIG-003")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "critical"

    def test_expected_mentions_phased(self):
        fb = self.fix["expected_feedback"].lower()
        assert "phased" in fb or "phase" in fb


class TestMIG004:
    """MIG-004: Missing rollback plan."""
    fix = next(f for f in FIXTURES if f["id"] == "MIG-004")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "critical"

    def test_violated_rule(self):
        assert "rollback" in self.fix["violated_rule"].lower()

    def test_expected_mentions_irreversible(self):
        fb = self.fix["expected_feedback"].lower()
        assert "irreversible" in fb


# ===========================================================================
# Per-Fixture Behavioral Tests: Standard Defects
# ===========================================================================

class TestMIG005:
    """MIG-005: INSTANT on MySQL 5.7."""
    fix = next(f for f in FIXTURES if f["id"] == "MIG-005")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "standard"

    def test_expected_mentions_57(self):
        fb = self.fix["expected_feedback"].lower()
        assert "5.7" in fb

    def test_expected_suggests_inplace(self):
        fb = self.fix["expected_feedback"].lower()
        assert "inplace" in fb


class TestMIG006:
    """MIG-006: LIMIT/OFFSET backfill."""
    fix = next(f for f in FIXTURES if f["id"] == "MIG-006")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "standard"

    def test_expected_mentions_pk_range(self):
        fb = self.fix["expected_feedback"].lower()
        assert "pk" in fb or "primary key" in fb


class TestMIG011:
    """MIG-011: VARCHAR boundary cross."""
    fix = next(f for f in FIXTURES if f["id"] == "MIG-011")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "standard"

    def test_expected_mentions_boundary(self):
        fb = self.fix["expected_feedback"].lower()
        assert "255" in fb or "boundary" in fb

    def test_expected_mentions_utf8mb4(self):
        fb = self.fix["expected_feedback"].lower()
        assert "utf8mb4" in fb


# ===========================================================================
# Per-Fixture Behavioral Tests: Good Practices
# ===========================================================================

class TestMIG007:
    """MIG-007: Well-formed phased migration."""
    fix = next(f for f in FIXTURES if f["id"] == "MIG-007")

    def test_type_severity(self):
        assert self.fix["type"] == "good_practice"
        assert self.fix["severity"] == "none"

    def test_expected_positive(self):
        fb = self.fix["expected_feedback"].lower()
        assert "no violation" in fb


class TestMIG008:
    """MIG-008: Good gh-ost invocation."""
    fix = next(f for f in FIXTURES if f["id"] == "MIG-008")

    def test_type_severity(self):
        assert self.fix["type"] == "good_practice"
        assert self.fix["severity"] == "none"

    def test_expected_positive(self):
        fb = self.fix["expected_feedback"].lower()
        assert "no violation" in fb

    def test_expected_mentions_tool(self):
        fb = self.fix["expected_feedback"].lower()
        assert "gh-ost" in fb


# ===========================================================================
# Per-Fixture Behavioral Tests: Degradation & Workflow
# ===========================================================================

class TestMIG009:
    """MIG-009: Degraded mode — missing context."""
    fix = next(f for f in FIXTURES if f["id"] == "MIG-009")

    def test_type_severity(self):
        assert self.fix["type"] == "degradation_scenario"
        assert self.fix["severity"] == "none"

    def test_expected_forbids_claims(self):
        fb = self.fix["expected_feedback"].lower()
        assert "must not" in fb or "not claim" in fb

    def test_expected_mentions_degraded(self):
        fb = self.fix["expected_feedback"].lower()
        assert "degraded" in fb


class TestMIG010:
    """MIG-010: Multi-step column rename workflow."""
    fix = next(f for f in FIXTURES if f["id"] == "MIG-010")

    def test_type_severity(self):
        assert self.fix["type"] == "workflow"
        assert self.fix["severity"] == "none"

    def test_expected_mentions_phases(self):
        fb = self.fix["expected_feedback"].lower()
        assert "phase" in fb or "step" in fb

    def test_expected_mentions_dual_write(self):
        fb = self.fix["expected_feedback"].lower()
        assert "dual" in fb or "both column" in fb

# ===========================================================================
# Layer 2: Linter Verdicts — the falsifiable layer
# ===========================================================================

def _fixture_filename(fix: dict) -> str:
    """Give the linter a filename whose extension selects the right lexer."""
    snippet = fix["migration_snippet"]
    if "gh-ost" in snippet or "pt-online-schema-change" in snippet:
        return f"{fix['id']}.sh"
    return f"{fix['id']}.sql"


def _lint_ids(fix: dict) -> set:
    cfg = fix["lint"]
    findings = LINT.lint_text(
        _fixture_filename(fix),
        fix["migration_snippet"],
        LINT.parse_version(cfg["mysql_version"]),
        False,
    )
    return {f.check_id for f in findings}


class TestLintExpectationsAreWellFormed:
    """The lint block is a claim about behavior; keep it checkable."""

    def test_every_fixture_declares_lint_expectations(self):
        for fix in FIXTURES:
            cfg = fix.get("lint")
            assert isinstance(cfg, dict), f"{fix['id']}: missing lint block"
            assert "mysql_version" in cfg, f"{fix['id']}: lint block needs mysql_version"
            assert isinstance(cfg.get("must_report", []), list)
            assert isinstance(cfg.get("must_not_report", []), list)

    def test_lint_version_parses(self):
        for fix in FIXTURES:
            LINT.parse_version(fix["lint"]["mysql_version"])

    def test_referenced_check_ids_exist(self):
        for fix in FIXTURES:
            cfg = fix["lint"]
            for cid in list(cfg.get("must_report", [])) + list(cfg.get("must_not_report", [])):
                assert cid in LINT.CHECK_REGISTRY, f"{fix['id']}: unknown check id {cid}"

    def test_expectations_do_not_contradict(self):
        for fix in FIXTURES:
            cfg = fix["lint"]
            overlap = set(cfg.get("must_report", [])) & set(cfg.get("must_not_report", []))
            assert not overlap, f"{fix['id']}: {overlap} in both must_report and must_not_report"

    def test_lint_version_matches_scenario_context(self):
        """A fixture that lints at a different version than it describes is a trap."""
        for fix in FIXTURES:
            ctx_ver = (fix.get("context") or {}).get("mysql_version")
            if not ctx_ver or ctx_ver == "unknown":
                continue
            assert fix["lint"]["mysql_version"] == ctx_ver, (
                f"{fix['id']}: context says MySQL {ctx_ver} but lint block uses "
                f"{fix['lint']['mysql_version']}"
            )


class TestLintVerdicts:
    """Run the checker over each fixture's actual statements."""

    @pytest.mark.parametrize("fix", FIXTURES, ids=[f["id"] for f in FIXTURES])
    def test_must_report(self, fix):
        expected = set(fix["lint"].get("must_report", []))
        if not expected:
            pytest.skip("no must_report expectations")
        reported = _lint_ids(fix)
        missing = expected - reported
        assert not missing, (
            f"{fix['id']}: checker did not report {sorted(missing)} "
            f"(reported: {sorted(reported) or 'nothing'})"
        )

    @pytest.mark.parametrize("fix", FIXTURES, ids=[f["id"] for f in FIXTURES])
    def test_must_not_report(self, fix):
        forbidden = set(fix["lint"].get("must_not_report", []))
        if not forbidden:
            pytest.skip("no must_not_report expectations")
        reported = _lint_ids(fix)
        wrong = forbidden & reported
        assert not wrong, f"{fix['id']}: checker wrongly reported {sorted(wrong)} on this snippet"

    @pytest.mark.parametrize(
        "fix", [f for f in FIXTURES if f["type"] == "good_practice"],
        ids=[f["id"] for f in FIXTURES if f["type"] == "good_practice"])
    def test_good_practice_fixtures_are_clean(self, fix):
        """A fixture labelled 'good practice' must not contain a critical defect.

        This is the assertion that would have caught MIG-008's reversed
        --allow-on-master usage when it was introduced.
        """
        findings = LINT.lint_text(
            _fixture_filename(fix),
            fix["migration_snippet"],
            LINT.parse_version(fix["lint"]["mysql_version"]),
            False,
        )
        critical = [f for f in findings if f.severity == LINT.CRITICAL]
        assert not critical, (
            f"{fix['id']} is labelled good_practice but the checker found critical issues:\n"
            + "\n".join(f"  [{f.check_id}] {f.message}" for f in critical)
        )

    @pytest.mark.parametrize(
        "fix", [f for f in FIXTURES if f["type"] == "defect"],
        ids=[f["id"] for f in FIXTURES if f["type"] == "defect"])
    def test_defect_fixtures_declare_at_least_one_signal(self, fix):
        """A defect fixture must either trip a check or say why it cannot.

        MIG-014's defect is a wrong *review note* attached to correct SQL — no
        statement-level signal exists, so it declares an empty must_report and
        relies on must_not_report to pin the correct verdict.
        """
        cfg = fix["lint"]
        if cfg.get("must_report"):
            return
        assert cfg.get("must_not_report"), (
            f"{fix['id']}: a defect fixture with neither must_report nor must_not_report "
            "asserts nothing about behavior"
        )


# ===========================================================================
# Per-Fixture Behavioral Tests: audit regressions (2026-08-06)
# ===========================================================================

class TestMIG012:
    """MIG-012: gh-ost operation-mode confusion."""
    fix = next(f for f in FIXTURES if f["id"] == "MIG-012")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "critical"

    def test_snippet_pairs_replica_host_with_allow_on_master(self):
        snip = self.fix["migration_snippet"]
        assert "--allow-on-master" in snip and "replica" in snip

    def test_expected_states_the_correct_semantics(self):
        fb = self.fix["expected_feedback"].lower()
        assert "at the master" in fb
        assert "default mode" in fb


class TestMIG013:
    """MIG-013: partition clause algorithm rejection on 5.7."""
    fix = next(f for f in FIXTURES if f["id"] == "MIG-013")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "critical"

    def test_expected_mentions_default_only(self):
        fb = self.fix["expected_feedback"].lower()
        assert "algorithm=default" in fb and "lock=default" in fb


class TestMIG014:
    """MIG-014: DROP COLUMN is not COPY — regression guard for the audited error."""
    fix = next(f for f in FIXTURES if f["id"] == "MIG-014")

    def test_expected_corrects_the_reviewer_not_the_sql(self):
        fb = self.fix["expected_feedback"].lower()
        assert "the sql is correct" in fb
        assert "in place = yes" in fb or "inplace" in fb

    def test_expected_does_not_recommend_gh_ost_for_this(self):
        fb = self.fix["expected_feedback"].lower()
        assert "for nothing" in fb or "adds a ghost table" in fb

    def test_snippet_uses_inplace_lock_none(self):
        assert "ALGORITHM=INPLACE, LOCK=NONE" in self.fix["migration_snippet"]


class TestMIG015:
    """MIG-015: ADD FOREIGN KEY + INPLACE with checks enabled."""
    fix = next(f for f in FIXTURES if f["id"] == "MIG-015")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "critical"

    def test_expected_quotes_the_rule(self):
        fb = self.fix["expected_feedback"]
        assert "foreign_key_checks is disabled" in fb
        assert "only the COPY algorithm is supported" in fb

    def test_expected_states_no_online_and_validated_path(self):
        assert "no online-and-validated path" in self.fix["expected_feedback"].lower()
