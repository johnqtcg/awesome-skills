"""Contract tests for mongo-migration skill.

Validates structural integrity of SKILL.md and reference files without
requiring an LLM.
"""

import pathlib
import pytest

SKILL_DIR = pathlib.Path(__file__).resolve().parents[2]
SKILL_MD = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
REFS_DIR = SKILL_DIR / "references"


def _ref(name: str) -> str:
    return (REFS_DIR / name).read_text(encoding="utf-8")


# ===========================================================================
# 1. Frontmatter
# ===========================================================================

class TestFrontmatter:
    def test_name(self):
        assert "name: mongo-migration" in SKILL_MD

    def test_description_keywords(self):
        desc = SKILL_MD[:800].lower()
        for kw in ["index", "schema", "bulk", "shard key", "collmod",
                    "write concern", "batched backfill"]:
            assert kw in desc, f"description missing keyword: {kw}"

    def test_description_does_not_advertise_the_retracted_pattern(self):
        """`_id`-range batching was the headline until a live server showed it skips
        documents whenever _id spans more than one BSON type ($gt type-brackets). It is
        now a conditional optimisation, so the trigger description must not sell it as
        the method."""
        desc = SKILL_MD[:800].lower()
        assert "_id-range" not in desc, (
            "the description advertises _id-range batching again; it is only valid for "
            "a single-BSON-type _id (see large-collection-migration.md §1)"
        )


# ===========================================================================
# 2. Mandatory Gates
# ===========================================================================

class TestMandatoryGates:
    def test_gate_1_context(self):
        assert "Gate 1" in SKILL_MD
        lower = SKILL_MD.lower()
        assert "mongodb version" in lower
        assert "replica" in lower or "deployment" in lower

    def test_gate_1_stop_proceed(self):
        assert "**STOP**" in SKILL_MD
        assert "**PROCEED**" in SKILL_MD

    def test_gate_2_scope(self):
        assert "Gate 2" in SKILL_MD

    def test_gate_3_risk(self):
        assert "Gate 3" in SKILL_MD
        for risk in ["SAFE", "WARN", "UNSAFE"]:
            assert risk in SKILL_MD

    def test_gate_4_completeness(self):
        assert "Gate 4" in SKILL_MD

    def test_all_gates_have_stop(self):
        assert SKILL_MD.count("**STOP**") >= 3


# ===========================================================================
# 3. Depth Selection
# ===========================================================================

class TestDepthSelection:
    def test_three_depths(self):
        for depth in ["Lite", "Standard", "Deep"]:
            assert depth in SKILL_MD

    def test_force_standard_signals(self):
        lower = SKILL_MD.lower()
        for signal in ["field type change", "shard key", "validator"]:
            assert signal in lower, f"missing signal: {signal}"

    def test_reference_loading_by_depth(self):
        assert "mongo-ddl-lock-matrix.md" in SKILL_MD
        assert "large-collection-migration.md" in SKILL_MD


# ===========================================================================
# 4. Degradation Modes
# ===========================================================================

class TestDegradationModes:
    def test_four_modes_defined(self):
        for mode in ["Full", "Degraded", "Minimal", "Planning"]:
            assert mode in SKILL_MD

    def test_never_fabricate(self):
        lower = SKILL_MD.lower()
        assert "never" in lower and ("fabricate" in lower or "claim" in lower or "safe" in lower and "without" in lower)

    def test_assumptions_documented(self):
        assert "9.9" in SKILL_MD


# ===========================================================================
# 5. Migration Safety Checklist
# ===========================================================================

class TestChecklist:
    def test_subsection_count(self):
        for sub in ["5.1", "5.2", "5.3", "5.4"]:
            assert sub in SKILL_MD

    def test_index_build(self):
        lower = SKILL_MD.lower()
        assert "rolling" in lower or "background" in lower

    def test_write_concern(self):
        lower = SKILL_MD.lower()
        assert "write concern" in lower or "writeconcern" in lower

    def test_validator_progression(self):
        lower = SKILL_MD.lower()
        assert "moderate" in lower
        assert "strict" in lower

    def test_id_range_batching(self):
        assert "_id" in SKILL_MD
        assert "range" in SKILL_MD.lower()

    def test_backward_compatibility(self):
        lower = SKILL_MD.lower()
        assert "deployment order" in lower or "backward" in lower

    def test_rollback_feasibility(self):
        assert "irreversible" in SKILL_MD.lower()


# ===========================================================================
# 6. Execution Plan
# ===========================================================================

class TestExecutionPlan:
    def test_all_phases_present(self):
        lower = SKILL_MD.lower()
        for kw in ["additive", "compatible deploy", "rollout barrier", "backfill",
                   "verify", "validator", "cleanup"]:
            assert kw in lower, f"missing phase: {kw}"

    def test_compatible_deploy_precedes_the_backfill(self):
        """The ordering IS the correctness property, so it is asserted rather than
        left to the phase names.

        The plan used to run the backfill at Phase 2 and deploy the dual-writing
        application at Phase 3. That leaves a window between "backfill finished" and
        "new code live" in which old instances keep creating documents in the old shape:
        the verified count is stale the moment it is read, and the validator enabled
        later then rejects writes to documents the backfill never saw.
        """
        import re
        plan = SKILL_MD[SKILL_MD.index("## §6 Execution Plan"):]
        plan = plan[:plan.index("\n## ")] if "\n## " in plan else plan

        def phase_of(pattern):
            m = re.search(rf"(\d+)\. \*\*Phase \1 — [^*]*{pattern}", plan, re.I)
            assert m, f"no phase matches {pattern!r} in the execution plan"
            return int(m.group(1))

        deploy = phase_of("Compatible deploy")
        barrier = phase_of("Rollout barrier")
        backfill = phase_of("Backfill")
        verify = phase_of("Verify")
        cleanup = phase_of("Cleanup")

        assert deploy < backfill, (
            f"the compatible deploy is Phase {deploy} but the backfill is Phase "
            f"{backfill}; deploying after the backfill reopens the write race"
        )
        assert deploy < barrier < backfill, (
            "the rollout barrier must sit between the deploy and the backfill -- it is "
            "what makes the post-backfill count a property rather than an instant"
        )
        assert backfill < verify < cleanup, (
            "verification must follow the backfill and precede the irreversible cleanup"
        )

    def test_cleanup_is_a_separate_release(self):
        """$unset cannot be reversed, so it never rides along with the cutover."""
        assert "separate release" in SKILL_MD.lower()

    def test_references_large_collection(self):
        assert "large-collection-migration.md" in SKILL_MD


# ===========================================================================
# 7. Anti-Examples
# ===========================================================================

class TestAntiExamples:
    def test_min_count(self):
        ae_count = sum(1 for l in SKILL_MD.split("\n") if l.strip().startswith("### AE-"))
        assert ae_count >= 6

    def test_wrong_right_pairs(self):
        assert SKILL_MD.count("// WRONG") >= 5
        assert SKILL_MD.count("// RIGHT") >= 5

    def test_unbounded_update_anti_example(self):
        assert "updateMany" in SKILL_MD or "unbounded" in SKILL_MD.lower()

    def test_extended_ref(self):
        assert "migration-anti-examples.md" in SKILL_MD


# ===========================================================================
# 8. Scorecard
# ===========================================================================

class TestScorecard:
    def test_critical_tier(self):
        lower = SKILL_MD.lower()
        assert "critical" in lower
        assert "any fail" in lower

    def test_standard_tier(self):
        assert "4 of 5" in SKILL_MD or "4/5" in SKILL_MD

    def test_hygiene_tier(self):
        assert "3 of 4" in SKILL_MD or "3/4" in SKILL_MD

    def test_critical_items(self):
        lower = SKILL_MD.lower()
        assert "_id" in lower
        assert "write concern" in lower or "writeconcern" in lower

    def test_verdict_format(self):
        # The fixed 12-item denominator is gone on purpose: an N/A item has to leave
        # both sides of the ratio, which a constant cannot express. Assert the dynamic
        # form and that the old constant has NOT come back.
        assert "PASS/FAIL" in SKILL_MD
        assert "(Na+Nb+Nc)" in SKILL_MD, "the scorecard must state a moving denominator"
        assert "X/12" not in SKILL_MD, (
            "the fixed X/12 total is back; an N/A item cannot be scored against it"
        )


# ===========================================================================
# 9. Output Contract
# ===========================================================================

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


# ===========================================================================
# 10. Reference Files
# ===========================================================================

class TestReferenceFiles:
    def test_ddl_matrix_exists(self):
        content = _ref("mongo-ddl-lock-matrix.md")
        assert len(content.splitlines()) >= 80

    def test_ddl_matrix_keywords(self):
        content = _ref("mongo-ddl-lock-matrix.md")
        for kw in ["Exclusive", "createIndex", "WiredTiger"]:
            assert kw in content

    def test_large_collection_exists(self):
        content = _ref("large-collection-migration.md")
        assert len(content.splitlines()) >= 100

    def test_large_collection_keywords(self):
        content = _ref("large-collection-migration.md")
        for kw in ["_id", "batch", "BulkWrite", "reshardCollection"]:
            assert kw in content

    def test_anti_examples_exists(self):
        content = _ref("migration-anti-examples.md")
        assert len(content.splitlines()) >= 80

    def test_anti_examples_numbering(self):
        content = _ref("migration-anti-examples.md")
        assert "AE-7" in content
        ae_count = sum(1 for l in content.split("\n") if "## AE-" in l)
        assert ae_count >= 5

    def test_all_refs_mentioned_in_skill(self):
        for f in REFS_DIR.glob("*.md"):
            assert f.name in SKILL_MD, f"{f.name} not in SKILL.md"


# ===========================================================================
# 11. Line Count Budget
# ===========================================================================

class TestLineCount:
    def test_max_lines(self):
        lines = len(SKILL_MD.splitlines())
        assert lines <= 420, f"SKILL.md is {lines} lines (budget: 420)"


# ===========================================================================
# 12. Cross-File Consistency
# ===========================================================================

class TestCrossFileConsistency:
    def test_wiredtiger_in_matrix(self):
        assert "WiredTiger" in _ref("mongo-ddl-lock-matrix.md")

    def test_reshard_in_large_collection(self):
        assert "reshardCollection" in _ref("large-collection-migration.md")

    def test_id_range_in_large_collection(self):
        assert "_id" in _ref("large-collection-migration.md")

    def test_write_concern_in_skill(self):
        assert "write concern" in SKILL_MD.lower() or "writeConcern" in SKILL_MD

    def test_validator_in_anti_examples(self):
        content = _ref("migration-anti-examples.md")
        assert "validationLevel" in content or "validator" in content.lower()

    def test_replication_lag_in_matrix(self):
        assert "replication" in _ref("mongo-ddl-lock-matrix.md").lower()


class TestRegressionOrchestration:
    """Every test suite must be reachable from the release entry point.

    `test_go_examples_compile.py` was written, passed, and demonstrably caught the
    defect it was built for -- and then sat unreferenced by `run_regression.sh` for a
    release. The regression stayed green while COVERAGE.md advertised the coverage, so
    a broken Go example would have shipped exactly as before. A suite nobody runs is
    documentation, not a gate.
    """

    import pathlib as _p
    TESTS_DIR = _p.Path(__file__).resolve().parent
    RUNNER = TESTS_DIR.parents[0] / "run_regression.sh"

    def test_runner_exists(self):
        assert self.RUNNER.exists(), self.RUNNER

    def test_every_suite_is_referenced_by_the_runner(self):
        runner = self.RUNNER.read_text(encoding="utf-8")
        suites = sorted(p.name for p in self.TESTS_DIR.glob("test_*.py"))
        assert suites, "no test suites found -- the discovery is broken"
        missing = [n for n in suites if n not in runner]
        assert not missing, (
            "these suites exist but the release regression never runs them, so a "
            f"failure in them cannot fail a release: {missing}"
        )

    def test_stage_numbering_matches_the_stage_count(self):
        """`note "3/8 ..."` lines are the runner's own account of what it does. A stale
        denominator is how a newly added stage goes unnoticed."""
        import re
        runner = self.RUNNER.read_text(encoding="utf-8")
        stages = re.findall(r'note "(\d+)/(\d+) ', runner)
        assert stages, "the runner prints no numbered stages"
        denominators = {int(d) for _, d in stages}
        assert len(denominators) == 1, (
            f"stages disagree on the total: {sorted(denominators)}"
        )
        total = denominators.pop()
        numbers = sorted(int(n) for n, _ in stages)
        assert numbers == list(range(1, total + 1)), (
            f"stage numbers {numbers} are not 1..{total}"
        )

    def test_a_skipped_gate_is_not_a_passed_gate(self):
        """Both environment-dependent gates -- the Go toolchain and the live servers --
        must drive the INCOMPLETE exit, or 'everything I ran passed' gets reported as
        'everything passed'."""
        runner = self.RUNNER.read_text(encoding="utf-8")
        assert "go_ran" in runner and "live_ran" in runner
        assert 'exit 3' in runner
        assert '"${live_ran}" -eq 0 ] || [ "${go_ran}" -eq 0 ]' in runner, (
            "the INCOMPLETE condition must cover BOTH optional gates"
        )
