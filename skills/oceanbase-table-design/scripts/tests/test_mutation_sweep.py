"""Mutation sweep: does the static suite actually go red when a rule is broken?

The contract and golden tests assert that phrases are *present*. That is one-directional
evidence -- a suite full of assertions can be green because the corpus is right, or green
because the assertions are vacuous, and reading it cannot tell you which. This file
settles the question: for each pinned rule it deletes or inverts the qualifier that rule
depends on, re-runs the suite against the mutated copy, and requires the **specific**
test that owns that rule to fail.

Three properties, each of which was a real failure mode in sibling skills:

  * **Every mutation replaces ALL occurrences.** Mutating only the first copy leaves the
    other copies satisfying the assertion, the test survives, and the report reads as
    "assertion is vacuous" when the truth is "mutation was incomplete".
  * **A named test must fail, not merely "pytest exited non-zero".** A non-zero exit can
    come from a collection error, a missing file, or an unrelated test -- crediting that
    to the mutation would certify coverage that does not exist.
  * **Coverage is derived, not declared.** `MUTATIONS` is checked against the rule list it
    claims to cover, so adding a rule without a mutation fails this file rather than
    silently reading as covered.

Runs the real suite in a subprocess against a real temp copy -- no monkeypatching, so
what passes here is what `run_regression.sh` sees.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
#: the copy must keep this name: a contract test asserts frontmatter `name:`
#: equals the directory basename, so copying into "skill/" fails the baseline
SKILL_DIRNAME = os.path.basename(SKILL_ROOT)

#: The two suites a mutation is allowed to break. Named explicitly rather than passing
#: the directory, because this file lives in that directory and would otherwise recurse
#: into itself once per mutation.
TARGET_SUITES = ("test_skill_contract.py", "test_golden_scenarios.py")

# (rule_id, path, find, replace, test that must fail, why this mutation is meaningful)
#
# `find` must be an exact substring of the current file. If it stops matching, the
# corpus was reworded and the mutation is no longer testing anything -- that is itself
# reported as a failure rather than silently skipped.
MUTATIONS = [
    (
        "R-NDV-GT-PARTITIONS",
        "SKILL.md",
        "### L1-B Design Blocker Checklist",
        "### L0 Extra Hard Constraints",
        "test_ndv_rule_is_in_the_blocker_block",
        "renaming the blocker block is how the 2026-08-12 tier fix would get reverted",
    ),
    (
        "R-NDV-GT-PARTITIONS",
        "SKILL.md",
        "Never grounds for calling a design infeasible",
        "Grounds for calling a design infeasible",
        "test_blocker_tier_still_emits_ddl",
        "inverting this sentence turns the blocker back into a refusal trigger",
    ),
    (
        "R-NDV-GT-PARTITIONS",
        "references/partitioning.md",
        "accepted_reason",
        "note",
        "test_blocker_tier_has_an_override_path",
        "with no override field, 'default fail' becomes 'always fail'",
    ),
    (
        "R-PKEY-TYPE",
        "references/partitioning.md",
        "Only criterion 3 is enforced",
        "All four criteria are enforced",
        "test_four_criteria_are_tier_annotated",
        "this is the sentence that keeps the four criteria from re-fusing into one hard gate",
    ),
    (
        "R-AUTOINC-MODE-GATE",
        "references/capability-matrix.md",
        "AUTO_INCREMENT_CACHE_SIZE",
        "AUTOINC_CACHE",
        "test_cache_size_explains_gap_magnitude",
        "without the real option name, 'use BIGINT' has no mechanism behind it",
    ),
    (
        "R-AUTOINC-MODE-GATE",
        "SKILL.md",
        "Write `AUTO_INCREMENT` / `AUTO_INCREMENT_MODE` / `auto_increment_cache_size` in Oracle-mode DDL",
        "Use auto-increment carefully in Oracle mode",
        "test_prohibition_listed",
        "softening the prohibition is exactly how illegal Oracle DDL got generated before",
    ),
    (
        "R-AUTOINC-MODE-GATE",
        "references/doc-gaps.md",
        "auto_increment_cache_size [=] INT_VALUE",
        "auto_increment_cache_size accepts NOCACHE",
        "test_nocache_scoped_to_oracle_sequences",
        "the integer-only production is the entire factual basis for rejecting NOCACHE in MySQL mode",
    ),
    (
        "R-AUTOINC-MODE-GATE",
        "references/doc-gaps.md",
        "disables caching entirely is `unverified`",
        "disables caching entirely is confirmed",
        "test_nocache_disable_value_stays_unverified",
        "promising a business gapless numbering on an unverified value is exactly the "
        "over-claim this skill exists to prevent",
    ),
    (
        "R-TENANT-DEFAULT-FORMAT",
        "references/storage-format.md",
        "no longer applies",
        "is still relevant",
        "test_explicit_write_is_the_recommended_workaround",
        "the explicit-clause recommendation loses its official basis without this",
    ),
    (
        "R-TABLEMODE-COMPACTION",
        "references/storage-format.md",
        "except `NORMAL`",
        "besides QUEUING",
        "test_all_but_normal_are_queuing_tables",
        "'which values count as queuing' is the whole point of the TABLE_MODE section",
    ),
    (
        "R-HOTSPOT-READ-DIRECTION",
        "references/hotspots.md",
        "do not add partitions",
        "consider adding partitions",
        "test_read_hotspot_does_not_get_bucket_advice",
        "bucketing a read hotspot multiplies reads instead of fixing them",
    ),
    (
        "R-SPECIAL-INDEX",
        "references/special-indexes.md",
        "must not use `SPACE`",
        "may use `SPACE`",
        "test_chinese_corpus_cannot_use_space_parser",
        "the SPACE tokenizer silently produces a full-text index that never matches Chinese",
    ),
    (
        "R-TABLET-SUM",
        "references/tablet-capacity.md",
        "_max_tablet_cnt_per_gb",
        "_tablet_cnt_cap",
        "test_tablet_formula_documented",
        "the Tablet ceiling parameter name is the anchor for the whole min(A,B) formula",
    ),
    (
        "R-CS-REPLICA-TOPOLOGY",
        "references/storage-format.md",
        "eventually consistent",
        "strongly consistent",
        "test_columnstore_replica_consistency_model_stated",
        "a strong-consistency AP query silently cannot use the replica",
    ),
    # ---- added 2026-08-12: the 28 rules the set-closure assertion exposed as unmutated ----
    (
        "R-TG-NONE-VERSION", "references/tablegroup.md",
        "has been removed", "still applies",
        "test_tablegroup_none_semantics_is_version_forked",
        "asserting the pre-BP1 single-node semantics on a new version is as wrong as the reverse",
    ),
    (
        "R-TG-SCOPE-VERSION", "references/tablegroup.md",
        "4.4.2", "4.0.0",
        "test_tablegroup_scope_has_a_minimum_version",
        "without the minimum version, SCOPE gets emitted for versions that reject it",
    ),
    (
        "R-MAXPART", "references/capability-matrix.md",
        "applies only to MySQL mode", "applies to both modes",
        "test_partition_ceiling_is_mode_dependent",
        "an 8192 gate applied to Oracle mode rejects a legal 10000-partition table",
    ),
    (
        "R-VERSION-GATE", "references/capability-matrix.md",
        "required_version", "suggested_version",
        "test_version_gate_names_a_required_version_field",
        "a suggestion cannot gate generation; the field name is the gate",
    ),
    (
        "R-L2-NO-REJECT", "references/anti-patterns.md",
        "Treating an L2 empirical threshold as grounds for rejecting a design",
        "Treating an L2 empirical threshold as a firm limit",
        "test_l2_threshold_may_not_reject_a_design",
        "turning an empirical number into a rejection is the single most common over-strictness",
    ),
    (
        "R-CONFIRMED-DDL-ONLY", "SKILL.md",
        "the primary DDL may only use C1", "the primary DDL prefers C1",
        "test_primary_ddl_is_c1_only",
        "'prefers' lets unconfirmed syntax into the statement the user actually runs",
    ),
    (
        "R-EVIDENCE", "references/output-contract.md",
        "without evidence", "with reasonable confidence",
        "test_evidence_gate_forbids_pass_without_evidence",
        "the no-pass-without-evidence gate is what keeps reasoning from replacing EXPLAIN",
    ),
    (
        "R-STORAGE-AXES", "SKILL.md",
        "Decide axis 2 first", "Decide axis 1 first",
        "test_storage_decision_is_two_axes_with_isolation_first",
        "isolation last in the chain means a workload that needs it never reaches the branch",
    ),
    (
        "R-SKIPINDEX", "SKILL.md",
        "SKIP_INDEX(MIN_MAX, SUM)", "a columnstore table",
        "test_skip_index_is_the_answer_for_narrow_aggregation",
        "without Skip Index this scenario has no answer but 'add columnstore', which is wrong",
    ),
    (
        "R-QUEUING", "references/storage-format.md",
        "steady_row_count", "row_count_guess",
        "test_queuing_table_identification_needs_measured_inputs",
        "queuing-table identification without measured inputs is a guess dressed as a verdict",
    ),
    (
        "R-LIST-ENUM-SYNTAX", "references/doc-gaps.md",
        "MySQL mode uses `VALUES IN (...)`, Oracle mode uses",
        "Both modes use `VALUES IN (...)`, and Oracle also accepts",
        "test_list_enumeration_syntax_differs_by_mode",
        "the two enumeration forms are not interchangeable; either substitution is a syntax error",
    ),
    (
        "R-LIST-DEFAULT", "references/verification.md",
        "list_default_partition", "list_partition_shape",
        "test_list_default_partition_recommended",
        "no catch-all partition means an unenumerated value fails the insert at runtime",
    ),
    (
        "R-AUTOSPLIT-LIMITS", "references/partitioning.md",
        "columnstore tables", "wide tables",
        "test_autosplit_restrictions_enumerated",
        "the columnstore restriction is one of the ten that make auto-split silently inapplicable",
    ),
    (
        "R-AUTOSPLIT-TRIGGER", "references/partitioning.md",
        "enable_auto_split", "auto_split_enabled",
        "test_autosplit_threshold_needs_the_tenant_switch",
        "writing SIZE without the tenant switch does not enable splitting -- the switch name is the fact",
    ),
    (
        "R-GI-COST", "SKILL.md",
        "global indexes are banned because they slow writes",
        "global indexes should be avoided",
        "test_global_index_is_a_cost_decision_not_a_ban",
        "losing the corrective phrasing lets the myth be restated as a rule",
    ),
    (
        "R-GI-DROPPART", "references/indexes.md",
        "global index rebuild", "index refresh",
        "test_global_index_on_archival_table_flags_rebuild",
        "the rebuild cost on every DROP PARTITION is the whole reason archival tables stay local-only",
    ),
    (
        "R-AUTOINC-PKEY", "references/indexes.md",
        "cross-node transactions", "some overhead",
        "test_autoinc_partition_key_costs_cross_node_txn",
        "'some overhead' does not tell the reader the cost is a distributed transaction per insert",
    ),
    (
        "R-MULTI-DIM", "SKILL.md",
        "Conflicting dimensions are normal, not a design failure",
        "Conflicting dimensions mean the design has failed",
        "test_conflicting_dimensions_is_not_a_failure",
        "this is the sentence that stops a normal multi-dimension workload being refused",
    ),
    (
        "R-INPUT-QUANT", "references/input-collection.md",
        "frequency_share", "access_weight",
        "test_quantified_inputs_required_and_collectable",
        "renaming the quantified input breaks the link between the gate and its collection SQL",
    ),
    (
        "R-INPUT-COLLECTION", "SKILL.md",
        "SQL to obtain", "list of required inputs",
        "test_quantified_inputs_required_and_collectable",
        "a requirement with no path to satisfy it leaves the user stuck or inventing numbers",
    ),
    (
        "R-DOC-CONFLICT-SPLIT", "references/doc-gaps.md",
        "official documents contradict each other", "official documents are consistent",
        "test_official_conflicts_route_by_scenario",
        "denying the conflict forces the agent to pick a side and write it up as a hard rule",
    ),
    (
        "R-DUPLICATE-TABLE", "references/tablegroup.md",
        "DUPLICATE_SCOPE", "REPLICA_SCOPE",
        "test_duplicate_table_is_the_dictionary_join_answer",
        "the clause name is the deliverable; a wrong name is unrunnable DDL",
    ),
    (
        "R-HOTSPOT-TYPES", "references/hotspots.md",
        "leader_skew", "node_imbalance",
        "test_hotspot_five_types_present",
        "a missing type means that hotspot shape gets no remedy at all",
    ),
    (
        "R-TABLET-MIN-PERNODE", "references/tablet-capacity.md",
        "Formula B", "Formula X",
        "test_ceiling_takes_the_smaller_of_two_formulas",
        "one formula alone over-reports headroom whenever the other binds",
    ),
    (
        "R-TABLET-WORST-NODE", "references/tablet-capacity.md",
        "worst", "average",
        "test_tablet_worst_node_drives_capacity",
        "averaging heterogeneous Units passes a design that will not fit on the smallest node",
    ),
    (
        "R-CG-SEMANTICS", "references/storage-format.md",
        "all columns, each column", "all columns",
        "test_column_group_redundancy_cost_stated",
        "collapsing the redundancy clause hides an approximately 2x storage cost",
    ),
    (
        "R-HTAP-FOUR-TIERS", "references/storage-format.md",
        "30%", "5%",
        "test_htap_index_tier_overhead_stated",
        "understating the columnstore-index overhead makes the wrong tier look free",
    ),
    (
        "R-NOORDER", "references/doc-gaps.md",
        "Do not set a TPS threshold", "Set a TPS threshold",
        "test_noorder_has_no_tps_threshold",
        "a fabricated TPS gate blocks NOORDER for workloads that officially qualify",
    ),
]


def _run_suite(root):
    """Run the two target suites against `root`; return (returncode, combined output).

    The copied test modules derive their own SKILL_ROOT from `__file__`, so pointing
    pytest at the copy is enough -- no env var or import hook involved.
    """
    paths = [os.path.join(root, "scripts", "tests", name) for name in TARGET_SUITES]
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--no-header",
         "-p", "no:cacheprovider", "--import-mode=importlib", *paths],
        cwd=root, capture_output=True, text=True,
    )
    return proc.returncode, proc.stdout + proc.stderr


def _copy_skill(dest):
    shutil.copytree(
        SKILL_ROOT, dest,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"))


class MutationSweepTests(unittest.TestCase):
    """One subtest per mutation, so a survivor names itself."""

    @classmethod
    def setUpClass(cls):
        """Baseline: the unmutated copy must be green.

        Without this, a mutation that "kills" a test proves nothing -- the test could
        have been failing in the copy for an unrelated reason (a path that does not
        survive copying, a missing fixture) and every mutation would look successful.
        """
        cls.tmp = tempfile.mkdtemp(prefix="ob-mutation-baseline-")
        root = os.path.join(cls.tmp, SKILL_DIRNAME)
        _copy_skill(root)
        cls.baseline_rc, cls.baseline_out = _run_suite(root)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_baseline_copy_is_green(self):
        self.assertEqual(
            self.baseline_rc, 0,
            "the unmutated copy already fails, so no mutation result below can be "
            f"trusted:\n{self.baseline_out[-3000:]}")

    def test_each_mutation_is_caught(self):
        if self.baseline_rc != 0:
            self.skipTest("baseline copy is not green; see test_baseline_copy_is_green")

        for rule, rel, find, replace, expect_test, why in MUTATIONS:
            with self.subTest(rule=rule, mutation=f"{rel}: {find[:40]!r}"):
                tmp = tempfile.mkdtemp(prefix="ob-mutation-")
                try:
                    root = os.path.join(tmp, SKILL_DIRNAME)
                    _copy_skill(root)
                    target = os.path.join(root, rel)
                    with open(target, encoding="utf-8") as f:
                        original = f.read()

                    self.assertIn(
                        find, original,
                        f"the mutation for {rule} no longer matches {rel} -- the text was "
                        f"reworded, so this mutation is testing nothing. Update MUTATIONS.")

                    # replace EVERY occurrence: a partial mutation leaves another copy
                    # satisfying the assertion and the survivor gets misread as a
                    # vacuous test rather than an incomplete mutation
                    mutated = original.replace(find, replace)
                    self.assertNotIn(find, mutated)
                    with open(target, "w", encoding="utf-8") as f:
                        f.write(mutated)

                    rc, out = _run_suite(root)
                    self.assertNotEqual(
                        rc, 0,
                        f"MUTATION SURVIVED for {rule}: replacing {find!r} with "
                        f"{replace!r} in {rel} broke nothing.\nWhy it matters: {why}")
                    self.assertIn(
                        expect_test, out,
                        f"the suite went red for {rule}, but {expect_test} was not the "
                        f"test that failed -- the mutation is being caught by accident, "
                        f"which means {expect_test} is not actually guarding it.\n"
                        f"{out[-2000:]}")
                finally:
                    shutil.rmtree(tmp, ignore_errors=True)


class MutationCoverageTests(unittest.TestCase):
    """Coverage as derived data, not as a claim in a docstring.

    "12/12 mutations killed" says nothing about the rules that have no mutation at all --
    the denominator is the mutation list itself, so an unmutated rule reads as covered.
    The set difference below is the only number that means anything.
    """

    #: Rules deliberately left without a mutation, each with the reason. An entry here is
    #: a recorded gap; an omission is a test failure.
    ACCEPTED_GAPS = {
        "R-EDITION-ORACLE": "single-sentence gate, no qualifier to delete",
        "R-KEY-3BRANCH": "covered by check_consistency.py's [B] branch-token rule",
        "R-KEY-AUTOSPLIT-PREFIX": "covered by the [B] branch-token rule",
        "R-UK-GLOBAL": "covered by the [B] branch-token rule",
        "R-ORACLE-NO-KEY": "covered by a BNF_FACTS absent-assertion",
        "R-ORACLE-NO-COLUMNS": "covered by a BNF_FACTS absent-assertion",
        "R-MYSQL-NO-INTERVAL": "covered by a BNF_FACTS absent-assertion",
    }

    def test_every_mutated_rule_exists_in_cases_json(self):
        with open(os.path.join(SKILL_ROOT, "tests", "cases.json"), encoding="utf-8") as f:
            known = set(json.load(f)["rules"])
        for rule, *_ in MUTATIONS:
            self.assertIn(
                rule, known,
                f"{rule} is mutated here but not registered in cases.json -- the two rule "
                f"lists have drifted")

    def test_accepted_gaps_are_real_rules(self):
        """A stale exemption is worse than no exemption: it silently excuses nothing
        while looking like it covers something."""
        with open(os.path.join(SKILL_ROOT, "tests", "cases.json"), encoding="utf-8") as f:
            known = set(json.load(f)["rules"])
        for rule in self.ACCEPTED_GAPS:
            self.assertIn(rule, known, f"exempted rule {rule} no longer exists in cases.json")

    def test_every_registered_rule_is_mutated_or_explicitly_exempt(self):
        """The set-closure assertion this file's docstring always claimed to make.

        It did not. Until 2026-08-12 the checks ran only in the forward direction --
        "every mutated rule exists in cases.json" and "every exemption exists in
        cases.json" -- neither of which says anything about a rule that appears in
        NEITHER list. The real numbers at that point were 44 registered rules, 14
        mutations covering 9 unique rules, 7 exemptions, and **28 rules in neither**.
        So "14/14 mutations killed" was true and "all rules are mutation-protected"
        was false, and only the second one sounded like coverage.

        This is the same failure as counting kills against the mutation list instead of
        against the rule list: the denominator was chosen from what had been done rather
        than from what needed doing. The set difference below cannot be gamed that way --
        a new rule in cases.json fails here until it is either mutated or exempted with
        a reason.
        """
        with open(os.path.join(SKILL_ROOT, "tests", "cases.json"), encoding="utf-8") as f:
            registered = set(json.load(f)["rules"])
        mutated = {m[0] for m in MUTATIONS}
        exempt = set(MutationCoverageTests.ACCEPTED_GAPS)
        uncovered = sorted(registered - mutated - exempt)
        self.assertEqual(
            uncovered, [],
            f"{len(uncovered)} rule(s) are registered in cases.json but are neither "
            f"mutated nor listed in ACCEPTED_GAPS, so nothing proves their contract "
            f"tests would notice if the rule were broken: {uncovered}\n"
            f"Add a mutation (preferred) or an ACCEPTED_GAPS entry naming the mechanism "
            f"that covers it. Do not bulk-exempt.")

    def test_exemptions_stay_a_small_minority(self):
        """Guard against closing the set above by exempting everything.

        The closure assertion is satisfiable two ways, and only one of them is coverage.
        A hard cap makes the cheap way fail.
        """
        with open(os.path.join(SKILL_ROOT, "tests", "cases.json"), encoding="utf-8") as f:
            registered = set(json.load(f)["rules"])
        exempt = set(MutationCoverageTests.ACCEPTED_GAPS)
        self.assertLessEqual(
            len(exempt), len(registered) // 4,
            f"{len(exempt)} of {len(registered)} rules are exempted from mutation "
            f"coverage; that is over a quarter. Exemptions are for rules genuinely "
            f"covered by another mechanism, not a way to satisfy the closure check.")

    def test_review_findings_have_a_mutation(self):
        """The rules the 2026-08-12 review touched must be mutation-covered, not merely
        asserted. These are the two findings that static presence-tests missed."""
        mutated = {m[0] for m in MUTATIONS}
        for rule in ("R-NDV-GT-PARTITIONS", "R-AUTOINC-MODE-GATE"):
            self.assertIn(rule, mutated,
                          f"{rule} was a review finding and must carry a mutation")

    def test_mutation_targets_are_distinct(self):
        seen = {(m[1], m[2]) for m in MUTATIONS}
        self.assertEqual(len(seen), len(MUTATIONS),
                         "two mutations target the same text; one of them is redundant")


if __name__ == "__main__":
    unittest.main()
