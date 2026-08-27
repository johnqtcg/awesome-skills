import re
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[2]
SKILL_MD = SKILL_DIR / "SKILL.md"
REFS_DIR = SKILL_DIR / "references"
RUNNER = SKILL_DIR / "scripts" / "run_regression.sh"
COVERAGE = SKILL_DIR / "scripts" / "tests" / "COVERAGE.md"


def frontmatter(text: str) -> str:
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        raise AssertionError("missing yaml frontmatter")
    return match.group(1)


class TestFrontmatter(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skill = SKILL_MD.read_text()
        cls.fm = frontmatter(cls.skill).lower()

    def test_name_is_correct(self) -> None:
        self.assertIn("name: systematic-debugging", self.fm)

    def test_description_has_debugging_triggers(self) -> None:
        for keyword in [
            "debugging",
            "diagnosing",
            "root cause",
            "flaky",
            "race condition",
            "performance regression",
            "build failure",
        ]:
            self.assertIn(keyword, self.fm)

    def test_skill_md_stays_within_progressive_disclosure_limit(self) -> None:
        lines = self.skill.count("\n")
        self.assertLessEqual(lines, 500, f"SKILL.md too long: {lines} lines")


class TestMandatoryGates(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skill = SKILL_MD.read_text()

    def test_gate_section_exists(self) -> None:
        self.assertIn("## Mandatory Gates", self.skill)

    def test_all_five_gates_exist(self) -> None:
        for gate in [
            "Root Cause Gate",
            "Evidence Gate",
            "Hypothesis Discipline Gate",
            "Fix Attempt Gate",
            "Reporting Integrity Gate",
        ]:
            self.assertIn(gate, self.skill)


class TestQualityScorecard(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skill = SKILL_MD.read_text()

    def test_scorecard_section_exists(self) -> None:
        self.assertIn("## Quality Scorecard", self.skill)

    def test_scorecard_tiers_exist(self) -> None:
        for tier in ["### Critical", "### Standard", "### Hygiene"]:
            self.assertIn(tier, self.skill)

    def test_scorecard_ids_exist(self) -> None:
        for item in ["C1", "C2", "C3", "C4", "S1", "S2", "S3", "S4", "S5", "S6", "H1", "H2", "H3", "H4"]:
            self.assertIn(item, self.skill)

    def test_scorecard_output_json_exists(self) -> None:
        self.assertIn('"scorecard"', self.skill)
        self.assertIn('"overall": "PASS|FAIL"', self.skill)


class TestAntiExamples(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skill = SKILL_MD.read_text()
        cls.ref = (REFS_DIR / "bad-good-debugging-reports.md").read_text()

    def test_skill_anti_example_section_exists(self) -> None:
        self.assertIn("## Anti-Examples - BAD / GOOD Debugging Reports", self.skill)

    def test_skill_lists_all_anti_example_categories(self) -> None:
        for item in [
            "symptom presented as root cause",
            "guessed fix without reproduction",
            "sleep/retry used to hide a race",
            "performance fix without profiling",
            "missing boundary evidence",
            "bundled fixes destroying attribution",
            "repeated failed fixes without questioning architecture",
        ]:
            self.assertIn(item, self.skill.lower())

    def test_reference_has_seven_bad_good_pairs(self) -> None:
        self.assertGreaterEqual(self.ref.count("BAD:"), 7)
        self.assertGreaterEqual(self.ref.count("GOOD:"), 7)


class TestSelectiveLoading(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skill = SKILL_MD.read_text()

    def test_selective_loading_section_exists(self) -> None:
        self.assertIn("## Load References Selectively", self.skill)

    def test_all_reference_conditions_exist(self) -> None:
        for ref in [
            "root-cause-tracing.md",
            "defense-in-depth.md",
            "condition-based-waiting.md",
            "bug-type-strategies.md",
            "scope-and-severity.md",
            "safety-and-authorization.md",
            "output-contract-template.md",
            "debugging-report-scorecard.md",
            "bad-good-debugging-reports.md",
        ]:
            self.assertIn(ref, self.skill)


class TestOutputContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skill = SKILL_MD.read_text()
        cls.contract = (REFS_DIR / "output-contract-template.md").read_text()

    def test_output_contract_section_exists(self) -> None:
        self.assertIn("## Output Contract (Required)", self.skill)

    def test_output_contract_has_nine_sections(self) -> None:
        for section in [
            "1. Triage",
            "2. Reproduction",
            "3. Evidence Collected",
            "4. Hypothesis Log",
            "5. Root Cause",
            "6. Fix Plan and Change",
            "7. Verification",
            "8. Residual Risk and Follow-ups",
            "9. Scorecard",
        ]:
            self.assertIn(section, self.contract)

    def test_output_contract_has_pass_fail_rules(self) -> None:
        self.assertIn("PASS/FAIL Rules", self.contract)
        self.assertIn("Critical tier has no FAIL", self.contract)


class TestReferenceFiles(unittest.TestCase):
    def test_reference_inventory_exists(self) -> None:
        expected = [
            "bad-good-debugging-reports.md",
            "bug-type-strategies.md",
            "condition-based-waiting.md",
            "debugging-report-scorecard.md",
            "defense-in-depth.md",
            "output-contract-template.md",
            "root-cause-tracing.md",
            "scope-and-severity.md",
            "safety-and-authorization.md",
        ]
        for fname in expected:
            self.assertTrue((REFS_DIR / fname).exists(), f"missing reference: {fname}")

    def test_reference_total_depth_is_at_least_1000_lines(self) -> None:
        total = 0
        for path in REFS_DIR.glob("*.md"):
            total += path.read_text().count("\n")
        self.assertGreaterEqual(total, 1000, f"reference depth too shallow: {total}")

    def test_all_references_have_toc(self) -> None:
        for fname in [
            "bad-good-debugging-reports.md",
            "bug-type-strategies.md",
            "condition-based-waiting.md",
            "debugging-report-scorecard.md",
            "defense-in-depth.md",
            "output-contract-template.md",
            "root-cause-tracing.md",
            "scope-and-severity.md",
            "safety-and-authorization.md",
        ]:
            text = (REFS_DIR / fname).read_text()
            self.assertIn("## Table of Contents", text)


class TestBugTypeCategoryCountConsistency(unittest.TestCase):
    """Regression test for the 8-claimed/6-actual bug-type category mismatch
    found in external review: SKILL.md must state the true category count of
    bug-type-strategies.md's numbered sections, not an aspirational one."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.skill = SKILL_MD.read_text()
        cls.bug_types = (REFS_DIR / "bug-type-strategies.md").read_text()

    def test_bug_type_strategies_numbered_category_count(self) -> None:
        # Numbered top-level categories look like "## 1. Logic Errors ...".
        categories = re.findall(r"^## \d+\. ", self.bug_types, re.MULTILINE)
        actual_count = len(categories)
        self.assertEqual(
            actual_count,
            6,
            f"bug-type-strategies.md has {actual_count} numbered categories, "
            "expected 6 — if this changed intentionally, update the count "
            "SKILL.md's 'Load References Selectively' section claims to match",
        )
        self.assertIn(f"{actual_count}-category", self.skill)

    def test_skill_does_not_overclaim_category_count(self) -> None:
        self.assertNotIn("8-type", self.skill)
        self.assertNotIn("8-category", self.skill)


class TestFindPolluterAlgorithmClaimConsistency(unittest.TestCase):
    """Regression test for the 'automated binary-search isolation' claim
    found false by external review: the script is a sequential linear scan."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.skill = SKILL_MD.read_text()
        cls.script = (SKILL_DIR / "scripts" / "find-polluter.sh").read_text()

    def test_skill_does_not_claim_binary_search(self) -> None:
        self.assertNotIn("binary-search", self.skill.lower())
        self.assertNotIn("binary search", self.skill.lower())

    def test_script_does_not_claim_binary_search(self) -> None:
        self.assertNotIn("binary-search", self.script.lower())
        self.assertNotIn("binary search", self.script.lower())

    def test_skill_describes_sequential_behavior(self) -> None:
        self.assertIn("sequentially", self.skill.lower())


class TestSeverityModeReconciliation(unittest.TestCase):
    """Regression test for the P2-shortcut vs. 'MUST complete each phase' vs.
    C1 contradiction found by external review. The P2 row, the Scope & Mode
    section, and gate C1 must all point at the same reconciled rule instead
    of drifting independently."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.skill = SKILL_MD.read_text()

    def test_scope_and_mode_section_exists(self) -> None:
        self.assertIn("## Scope & Mode", self.skill)

    def test_c1_references_declared_mode_severity(self) -> None:
        c1_match = re.search(r"\| C1 \|(.+?)\|\n", self.skill)
        self.assertIsNotNone(c1_match, "C1 row not found in Critical tier table")
        self.assertIn("mode/severity", c1_match.group(1))

    def test_diagnose_only_mode_is_a_valid_terminal_state(self) -> None:
        self.assertIn("Diagnose-only", self.skill)
        self.assertIn("not a skipped step", self.skill)


class TestFrontmatterExcludesDestructiveTools(unittest.TestCase):
    """Regression test for the review's safety-gate finding: git init and
    rm -rf must not be pre-approved (auto-executable) via allowed-tools."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.fm = frontmatter(SKILL_MD.read_text())

    def test_no_git_init_in_allowed_tools(self) -> None:
        self.assertNotIn("git init", self.fm)

    def test_no_rm_rf_in_allowed_tools(self) -> None:
        self.assertNotIn("rm -rf", self.fm)


class TestScorecardOutputContractSync(unittest.TestCase):
    """Regression tests for the second-round review finding: SKILL.md,
    debugging-report-scorecard.md, and output-contract-template.md drifted
    out of sync on Critical-tier IDs, H2's fields, and the PASS/FAIL math."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.skill = SKILL_MD.read_text()
        cls.scorecard = (REFS_DIR / "debugging-report-scorecard.md").read_text()
        cls.contract = (REFS_DIR / "output-contract-template.md").read_text()

    def test_scorecard_h2_includes_mode(self) -> None:
        h2_match = re.search(r"\| H2 \|(.+?)\|(.+?)\|\n", self.scorecard)
        self.assertIsNotNone(h2_match, "H2 row not found in debugging-report-scorecard.md")
        self.assertIn("mode", h2_match.group(1).lower())

    def test_scorecard_and_skill_agree_on_critical_ids(self) -> None:
        skill_ids = set(re.findall(r"\| (C\d) \|", self.skill))
        scorecard_ids = set(re.findall(r"\| (C\d) \|", self.scorecard))
        self.assertEqual(skill_ids, scorecard_ids)
        self.assertIn("C5", skill_ids, "Reporting Integrity Gate should have a Critical scorecard item")

    def test_pass_fail_rules_state_critical_is_not_offset(self) -> None:
        # The 2026-08-27 review found S2/S4 could both fail (2 of 6) while
        # Standard still hit 4/6, silently overall-PASSing a report with no
        # boundary evidence and no honest verification. The fix ties those
        # specific failure modes to Critical items (C3, C5) instead, and the
        # doc must say so explicitly so this doesn't quietly drift back.
        self.assertIn("offset by a good Standard/Hygiene score", self.contract)
        self.assertIn("fails C5", self.contract)
        self.assertIn("fails C3", self.contract)

    def test_verification_section_is_mode_aware(self) -> None:
        self.assertIn("diagnose-only", self.contract.lower())


class TestFindPolluterIncompleteExitCode(unittest.TestCase):
    """Regression test: a scan where every run failed to execute must not
    exit 0 (success) — that was the 2026-08-27 review's point #3."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.script = (SKILL_DIR / "scripts" / "find-polluter.sh").read_text()

    def test_incomplete_exit_code_is_documented_and_used(self) -> None:
        self.assertIn("exit 4", self.script)
        self.assertIn("INCOMPLETE", self.script)


class TestDefenseInDepthPathBoundaryFix(unittest.TestCase):
    """Regression test for the startsWith(tmpDir) prefix-match bug (e.g.
    '/tmp-evil' incorrectly passing a naive check against '/tmp')."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.ref = (REFS_DIR / "defense-in-depth.md").read_text()

    def test_boundary_safe_check_present(self) -> None:
        self.assertIn("tmpDir + sep", self.ref)

    def test_naive_unguarded_startswith_not_present(self) -> None:
        # The bug was a bare `startsWith(tmpDir)` used as the *entire*
        # condition. It's fine for that substring to appear as part of the
        # fixed `=== tmpDir || normalized.startsWith(tmpDir + sep)` check —
        # what must NOT appear is the naive check standing alone.
        self.assertNotIn("if (!normalized.startsWith(tmpDir))", self.ref)


class TestRegressionAssets(unittest.TestCase):
    def test_runner_exists(self) -> None:
        self.assertTrue(RUNNER.exists(), "run_regression.sh must exist")

    def test_runner_references_both_commands(self) -> None:
        text = RUNNER.read_text()
        self.assertIn("python3 -m unittest discover", text)
        self.assertIn("find-polluter.sh", text)

    def test_coverage_doc_exists(self) -> None:
        self.assertTrue(COVERAGE.exists(), "COVERAGE.md must exist")


class TestOutputContractHasModeField(unittest.TestCase):
    """Regression test for the third-round review finding: the Triage
    template must actually contain a Mode field, matching H2's requirement
    (in both SKILL.md and debugging-report-scorecard.md) that mode be
    classified alongside severity and bug type."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = (REFS_DIR / "output-contract-template.md").read_text()

    def test_triage_template_has_mode_field(self) -> None:
        triage_section = self.contract.split("## 2. Reproduction")[0]
        self.assertIn("Mode:", triage_section)
        self.assertIn("diagnose-only", triage_section)


class TestNAScopeIsRestrictedToC1AndC4(unittest.TestCase):
    """Regression test for the third-round review finding: a live subagent
    marked Standard-tier S2 as N/A, which scope-and-severity.md's own rule
    forbids (only C1/C4 may ever be N/A). The rule must say this explicitly
    enough that S2 specifically is called out, not just "no other criterion"."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.scope = (REFS_DIR / "scope-and-severity.md").read_text()

    def test_s2_explicitly_named_as_not_na_able(self) -> None:
        self.assertIn("this includes S2", self.scope)

    def test_only_c1_and_c4_may_be_na(self) -> None:
        self.assertIn("No other Critical, Standard, or Hygiene criterion may be marked N/A", self.scope)


class TestSensitiveCommandsExcludedFromAllowedTools(unittest.TestCase):
    """Regression test for the third-round review finding: env and tcpdump
    must not be pre-approved — the exposure happens at execution time, and
    report-time redaction can't undo it, so these need a per-run ask."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.fm = frontmatter(SKILL_MD.read_text()).lower()

    def test_no_bare_env_wildcard_in_allowed_tools(self) -> None:
        self.assertNotIn("bash(env*)", self.fm)

    def test_no_tcpdump_wildcard_in_allowed_tools(self) -> None:
        self.assertNotIn("bash(tcpdump*)", self.fm)


class TestLiveScenarioTranscriptsPreserved(unittest.TestCase):
    """Regression test for the third-round review finding: a live-scenario
    write-up with no preserved transcript isn't independently checkable."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.eval_dir = SKILL_DIR.parent.parent / "evaluate" / "systematic-debugging-live-scenarios-2026-08-27"

    def test_transcripts_directory_exists(self) -> None:
        self.assertTrue(self.eval_dir.exists(), f"missing {self.eval_dir}")

    def test_readme_exists(self) -> None:
        self.assertTrue((self.eval_dir / "README.md").exists())

    def test_at_least_five_transcripts_present(self) -> None:
        transcripts = list(self.eval_dir.glob("*.jsonl"))
        self.assertGreaterEqual(len(transcripts), 5, f"found {len(transcripts)} transcripts, expected >= 5")

    def test_coverage_doc_says_five_not_four(self) -> None:
        # Regression for the specific miscount the third-round review caught:
        # the prose said "four" while the table listed five scenario rows.
        coverage_text = COVERAGE.read_text()
        transcripts = list(self.eval_dir.glob("*.jsonl"))
        self.assertEqual(5, len(transcripts))
        self.assertIn("five fresh general-purpose subagents", coverage_text)
        self.assertNotIn("four fresh general-purpose subagents", coverage_text)


if __name__ == "__main__":
    unittest.main()
