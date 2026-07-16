import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[2]
SKILL_MD = SKILL_DIR / "SKILL.md"
REF_DIR = SKILL_DIR / "references"
CHECKLISTS = REF_DIR / "create-pr-checklists.md"
CONFIG_EXAMPLE = REF_DIR / "create-pr-config.example.yaml"
BUNDLED_SCRIPT_GUIDE = REF_DIR / "bundled-script-guide.md"
MERGE_STRATEGY = REF_DIR / "merge-strategy-guide.md"
PR_BODY_TEMPLATE = REF_DIR / "pr-body-template.md"
RUN_REGRESSION = SKILL_DIR / "scripts" / "run_regression.sh"
SCRIPT = SKILL_DIR / "scripts" / "create_pr.py"


def frontmatter(text: str) -> str:
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        raise AssertionError("missing yaml frontmatter")
    return match.group(1)


def normalize(text: str) -> str:
    text = text.lower()
    text = text.replace("→", " ")
    text = text.replace("–", " ")
    text = text.replace("—", " ")
    text = re.sub(r"[^\w\s]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


class CreatePRSkillContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skill_text = SKILL_MD.read_text()
        cls.skill_norm = normalize(cls.skill_text)
        cls.checklists_text = CHECKLISTS.read_text()
        cls.bundled_text = BUNDLED_SCRIPT_GUIDE.read_text()
        cls.merge_text = MERGE_STRATEGY.read_text()
        cls.template_text = PR_BODY_TEMPLATE.read_text()
        cls.config_text = CONFIG_EXAMPLE.read_text()
        cls.run_regression_text = RUN_REGRESSION.read_text()
        cls.script_text = SCRIPT.read_text()

    def assertContainsNormalized(self, needle: str, haystack: str, message: str = "") -> None:
        self.assertIn(normalize(needle), normalize(haystack), message or f"missing: {needle}")

    def test_frontmatter_name_and_description(self) -> None:
        fm = frontmatter(self.skill_text)
        self.assertIn("name: create-pr", fm)
        self.assertIn("evidence-backed pull requests", fm)
        keys = {
            line.split(":", 1)[0].strip()
            for line in fm.splitlines()
            if line and not line.startswith((" ", "\t")) and ":" in line
        }
        self.assertEqual({"name", "description"}, keys)

    def test_skill_references_all_supporting_files(self) -> None:
        for path in (
            CHECKLISTS,
            CONFIG_EXAMPLE,
            BUNDLED_SCRIPT_GUIDE,
            MERGE_STRATEGY,
            PR_BODY_TEMPLATE,
            RUN_REGRESSION,
            SCRIPT,
        ):
            self.assertTrue(path.exists(), f"missing {path.name}")

        for label in (
            "references/create-pr-checklists.md",
            "references/pr-body-template.md",
            "references/create-pr-config.example.yaml",
            "references/merge-strategy-guide.md",
            "references/bundled-script-guide.md",
        ):
            self.assertIn(label, self.skill_text)

    def test_quick_reference_covers_all_gates(self) -> None:
        for gate in ("Gate A", "Gate B", "Gate C", "Gate D", "Gate E", "Gate F", "Gate G", "Gate H"):
            self.assertIn(gate, self.skill_text)
        self.assertContainsNormalized("confirmed → ready", self.skill_text)
        self.assertContainsNormalized("likely → ready only for low-residual-risk suppressions", self.skill_text)
        self.assertContainsNormalized("suspected → draft", self.skill_text)

    def test_non_negotiables_capture_release_safety_rules(self) -> None:
        for phrase in (
            "Never open a PR from `main` as the head branch.",
            "Never push secrets, credentials, or local-only configuration.",
            "Never claim a gate passed without command or code evidence.",
            "Fail closed",
            "One PR = one problem.",
            "PR title must follow Conventional Commits format",
        ):
            self.assertContainsNormalized(phrase, self.skill_text)

    def test_readiness_confidence_and_suspected_rule(self) -> None:
        for level in ("confirmed", "likely", "suspected"):
            self.assertIn(f"`{level}`", self.skill_text)
        self.assertContainsNormalized("Do not mark a PR `ready` with `suspected` confidence.", self.skill_text)

    def test_suppression_rules_define_only_three_reasons(self) -> None:
        self.assertContainsNormalized("Suppress a gate only when: (1) gate is N/A for changed files, (2) tooling unavailable, or (3) equivalent upstream check proves the condition", self.skill_text)
        self.assertContainsNormalized("Any suppression must be recorded in `Uncovered Risk List`", self.skill_text)
        self.assertContainsNormalized("Keep PR as `draft` if the uncovered area can hide merge-blocking defects.", self.skill_text)

    def test_fixed_process_lists_all_steps_and_fast_path(self) -> None:
        for step in (
            "Scope the change.",
            "Run `Gate A`: authentication and repository preflight.",
            "Run `Gate B`: branch hygiene and sync with `origin/main`.",
            "Run `Gate C`: change-risk classification.",
            "Run `Gate D`: quality evidence",
            "Run `Gate E`: security and secret-leak checks.",
            "Run `Gate F`: documentation and compatibility checks.",
            "Run `Gate G`: commit hygiene and commit message quality.",
            "Prepare PR title/body with structured evidence.",
            "If no hard publication blocker exists, push branch and create PR to `main`; otherwise stop before push.",
            "Run `Gate H`: post-create verification.",
            "Decide `draft` vs `ready` from gate results.",
            "Report findings first, then PR link, then follow-up actions.",
        ):
            self.assertContainsNormalized(step, self.skill_text)
        self.assertContainsNormalized("Fast path (≤100 changed lines, no high-risk area)", self.skill_text)

    def test_gate_a_has_required_preflight_commands_and_suppression(self) -> None:
        for cmd in (
            "git rev-parse --is-inside-work-tree",
            "git remote -v",
            "git remote get-url origin",
            "gh auth status -h github.com",
            "gh repo view --json nameWithOwner,isPrivate,viewerPermission,defaultBranchRef",
            "git ls-remote --heads origin main",
            "gh api repos/{owner}/{repo}/branches/main/protection",
        ):
            self.assertIn(cmd, self.skill_text)
        self.assertContainsNormalized("If branch protection query fails (404/403), record in Uncovered Risk List and continue.", self.skill_text)
        self.assertContainsNormalized("origin repository identity must match", self.skill_text)

    def test_gate_b_covers_branch_hygiene_and_no_auto_rebase(self) -> None:
        for phrase in (
            "branch name matches `<type>/<short-description>`",
            "git status --porcelain",
            "grep -rnE '^(<<<<<<<|=======|>>>>>>>)' .",
            "git fetch origin main",
            "git merge-base --is-ancestor origin/main HEAD",
            "Do NOT auto-rebase",
        ):
            self.assertContainsNormalized(phrase, self.skill_text)

    def test_gate_c_covers_high_risk_areas_size_thresholds_and_monorepo(self) -> None:
        for phrase in (
            "auth/authz, payment, migration, concurrency, public API, infra config, secrets",
            "≤ 400 lines",
            "401–800 lines",
            "> 800 lines",
            "explicit risk and rollback notes in PR body",
            "If multiple `go.mod` exist, scope gates D/E to changed modules only",
        ):
            self.assertContainsNormalized(phrase, self.skill_text)

    def test_gate_d_requires_project_checks_then_language_defaults(self) -> None:
        for phrase in (
            "Run project-standard checks first; fallback to language defaults.",
            "repo-defined check target (`make test`, `make lint`, etc.)",
            "language checks (for Go: `go test ./...`, `golangci-lint run`)",
            "Record exact command and pass/fail result.",
            "If a command is unavailable, mark uncovered risk.",
        ):
            self.assertContainsNormalized(phrase, self.skill_text)

    def test_gate_e_covers_secret_scans_and_go_security_tools(self) -> None:
        for phrase in (
            "git diff --name-only --diff-filter=ACMR origin/main...HEAD",
            "git diff origin/main...HEAD",
            ".env",
            ".pem",
            ".key",
            ".p12",
            "comments",
            "gosec ./...",
            "govulncheck ./...",
            "Any surviving high-confidence filename or content match is a hard publication blocker",
        ):
            self.assertContainsNormalized(phrase, self.skill_text)

    def test_gate_f_requires_docs_and_compatibility_notes(self) -> None:
        for phrase in (
            "docs/changelog/readme updates",
            "Check backward compatibility and migration impact.",
            "include rollout/rollback notes",
        ):
            self.assertContainsNormalized(phrase, self.skill_text)

    def test_gate_g_requires_commit_hygiene_title_quality_and_self_review(self) -> None:
        for phrase in (
            "All commits should use Conventional Commit format",
            "PR title must also follow Conventional Commits format",
            "subject ≤ 50 characters",
            "body line must be ≤ 72 characters",
            "--confirm-self-review",
            "If no commit exists, create one before PR creation.",
            "Perform a self-review of the full diff",
        ):
            self.assertContainsNormalized(phrase, self.skill_text)

    def test_gate_h_requires_post_create_verification(self) -> None:
        for phrase in (
            "Confirm PR points to `base=main` and `head=<feature branch>`.",
            "Confirm title/body rendered correctly.",
            "Confirm draft/ready state matches gate outcomes.",
            "gh pr view --json number,url,state,isDraft,baseRefName,headRefName,title,body",
            "gh pr checks <pr-number>",
        ):
            self.assertContainsNormalized(phrase, self.skill_text)

    def test_draft_vs_ready_decision_rules_exist(self) -> None:
        for phrase in (
            "Mark `ready` only when all mandatory gates pass or are suppressed with low residual risk.",
            "Keep `draft` when:",
            "any mandatory gate failed",
            "important evidence is missing",
            "unresolved design/security/performance questions remain",
        ):
            self.assertContainsNormalized(phrase, self.skill_text)

    def test_required_pr_body_structure_has_8_sections(self) -> None:
        for section in (
            "1. Problem/Context",
            "2. What Changed",
            "3. Why This Approach",
            "4. Risk and Rollback Plan",
            "5. Test Evidence (commands + key outputs)",
            "6. Security Notes",
            "7. Breaking Changes / Migration Notes",
            "8. Reviewer Checklist",
        ):
            self.assertContainsNormalized(section, self.skill_text)

    def test_command_playbook_covers_push_create_edit_and_view(self) -> None:
        for phrase in (
            "git fetch origin main",
            "git merge-base --is-ancestor origin/main HEAD",
            "git push -u origin HEAD",
            "gh pr create --base main",
            "gh pr edit <pr-number> --add-reviewer <user1>,<user2> --add-label <label>",
            "gh pr view --json number,url,state,isDraft,baseRefName,headRefName",
        ):
            self.assertContainsNormalized(phrase, self.skill_text)

    def test_output_contract_order_is_defined(self) -> None:
        for phrase in (
            "Gate results (`PASS/FAIL/SUPPRESSED/N/A`) with one-line evidence.",
            "`Uncovered Risk List`",
            "PR metadata: number, URL, draft/ready, base/head.",
            "Next actions needed from user/reviewers.",
        ):
            self.assertContainsNormalized(phrase, self.skill_text)

    def test_pr_body_template_has_all_sections_and_tables(self) -> None:
        for section in (
            "# PR Title",
            "## 1) Problem / Context",
            "## 2) What Changed",
            "## 3) Why This Approach",
            "## 4) Risk and Rollback Plan",
            "## 5) Test Evidence",
            "## 6) Security Notes",
            "## 7) Breaking Changes / Migration Notes",
            "## 8) Reviewer Checklist",
        ):
            self.assertIn(section, self.template_text)
        self.assertIn("| Command | Result | Notes |", self.template_text)

    def test_checklists_cover_preflight_security_publication_and_maintenance(self) -> None:
        for heading in (
            "## Preflight Checklist",
            "## Scope and Risk Checklist",
            "## Quality Evidence Checklist",
            "## Security Checklist",
            "## PR Publication Checklist",
            "## Skill Maintenance Checklist",
            "## Uncovered Risk Entry Format",
        ):
            self.assertIn(heading, self.checklists_text)
        for phrase in (
            "bash skills/create-pr/scripts/run_regression.sh",
            "Contract tests cover gate ordering, readiness confidence, output contract, and reference links",
            "Golden scenarios execute the script decision functions for ready/draft, suppression, blocker, and publication outcomes",
        ):
            self.assertContainsNormalized(phrase, self.checklists_text)

    def test_bundled_script_guide_covers_behavior_examples_and_exit_codes(self) -> None:
        for phrase in (
            "updates title/body instead of creating a duplicate PR",
            "Draft/ready state is reconciled from gate results",
            "Hard publication blockers are checked before `git push`",
            "python \"<path-to-skill>/scripts/create_pr.py\"",
            "bash \"<path-to-skill>/scripts/run_regression.sh\"",
            "`0`: all required gates passed (ready).",
            "`1`: at least one gate is suppressed/uncovered",
            "`2`: at least one gate failed. Hard publication failures stop before push",
        ):
            self.assertContainsNormalized(phrase, self.bundled_text)

    def test_merge_strategy_guide_covers_three_strategies_and_squash_priority(self) -> None:
        for phrase in (
            "Squash and merge",
            "Create a merge commit",
            "Rebase and merge",
            "PR title = final commit message",
            "default to treating the PR title as if it were a squash commit message",
        ):
            self.assertContainsNormalized(phrase, self.merge_text)

    def test_config_example_covers_core_and_nested_settings(self) -> None:
        for phrase in (
            "base: main",
            "reviewers:",
            "labels:",
            "check_cmd:",
            "quality:",
            "security_tools:",
            "branch_protection:",
            "required_checks:",
            "secret_scan:",
            "allow_patterns:",
            "conflict_scan:",
            "scan_changed_files_only: true",
        ):
            self.assertIn(phrase, self.config_text)

    def test_run_regression_runs_validator_help_and_unittest_discovery(self) -> None:
        for phrase in (
            "[1/3] Validate skill frontmatter",
            "[2/3] Smoke-test bundled script help",
            "python3 \"${SKILL_DIR}/scripts/create_pr.py\" --help >/dev/null",
            "[3/3] Run regression tests",
            "python3 -m unittest discover -s \"${SKILL_DIR}/scripts/tests\" -p \"test_*.py\" -v",
        ):
            self.assertIn(phrase, self.run_regression_text)
        self.assertNotIn("continuing", self.run_regression_text.lower())
        self.assertIn('python3 "${VALIDATOR}" "${SKILL_DIR}"', self.run_regression_text)

    def test_run_regression_stops_when_validator_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            validator = Path(tmp) / "fail_validator.py"
            validator.write_text("raise SystemExit(7)\n")
            env = dict(os.environ)
            env["SKILL_CREATOR_VALIDATOR"] = str(validator)
            result = subprocess.run(
                ["bash", str(RUN_REGRESSION)],
                cwd=SKILL_DIR,
                env=env,
                capture_output=True,
                text=True,
            )
        self.assertEqual(7, result.returncode)
        self.assertNotIn("[2/3]", result.stdout)
        self.assertNotIn("regression checks passed", result.stdout)

    def test_bundled_script_exposes_exit_codes_and_main_returns_all_three(self) -> None:
        self.assertContainsNormalized("Exit Codes", self.bundled_text)
        for value in ("return 0", "return 1", "return 2"):
            self.assertIn(value, self.script_text)

    def test_gate_c_size_threshold_constants_match_skill(self) -> None:
        """Verify create_pr.py defines SIZE_THRESHOLD_WARN=400 and SIZE_THRESHOLD_STRONG=800
        so they stay in sync with the thresholds documented in SKILL.md."""
        self.assertIn(
            "SIZE_THRESHOLD_WARN = 400",
            self.script_text,
            "create_pr.py must define SIZE_THRESHOLD_WARN = 400",
        )
        self.assertIn(
            "SIZE_THRESHOLD_STRONG = 800",
            self.script_text,
            "create_pr.py must define SIZE_THRESHOLD_STRONG = 800",
        )

    def test_gate_b_conflict_marker_grep_regex_matches_all_three_markers(self) -> None:
        """Verify the grep command in Gate B actually matches all three conflict markers.

        Guards against BRE vs ERE translation bugs where ( ) and | are literal in BRE,
        causing <<<<<<< and >>>>>>> to be silently missed.
        """
        # Extract the grep command from SKILL.md
        m = re.search(r"`(grep\s+-\S*E\S*\s+\S+\s+\.)`", self.skill_text)
        self.assertIsNotNone(m, "SKILL.md must contain an ERE grep command for conflict markers")
        cmd = m.group(1)  # type: ignore[union-attr]
        for marker in ("<<<<<<< HEAD", "=======", ">>>>>>> branch"):
            result = subprocess.run(
                ["bash", "-c", f"echo '{marker}' | {cmd.replace(' .', '')}"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                result.returncode, 0,
                f"grep command failed to match conflict marker: {marker!r}\ncmd: {cmd}",
            )


class ProseScriptConsistencyTests(unittest.TestCase):
    """Bridge tests between the two implementations of the gates.

    SKILL.md's prose workflow is the specification and the no-Python
    fallback; scripts/create_pr.py is the canonical executable. Each test
    here fails when one side changes a shared constant or semantic without
    the other — closing the dual-brain drift hole.
    """

    @classmethod
    def setUpClass(cls) -> None:
        import importlib.util
        import sys

        spec = importlib.util.spec_from_file_location("create_pr_bridge", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        cls.mod = module
        cls.skill_text = SKILL_MD.read_text()
        cls.script_src = SCRIPT.read_text()

    def test_canonical_implementation_declared(self) -> None:
        self.assertIn("Canonical Implementation", self.skill_text)
        self.assertIn("create_pr.py", self.skill_text)
        self.assertIn("fallback", self.skill_text)

    def test_size_thresholds_match(self) -> None:
        warn = self.mod.SIZE_THRESHOLD_WARN
        strong = self.mod.SIZE_THRESHOLD_STRONG
        self.assertIn(f"{warn} lines", self.skill_text,
                      f"script warns at {warn} lines but SKILL.md does not mention it")
        self.assertIn(f"{warn + 1}–{strong}", self.skill_text,
                      "SKILL.md warn band must match script thresholds")
        self.assertIn(f"> {strong}", self.skill_text,
                      f"script strong-warns above {strong} lines but SKILL.md does not")

    def test_confidence_levels_match_behavior(self) -> None:
        mk = lambda status: [self.mod.GateResult("Gate B", status, "x")]
        derived = {
            self.mod.determine_confidence(mk(self.mod.FAIL)),
            self.mod.determine_confidence(mk(self.mod.SUPPRESSED)),
            self.mod.determine_confidence(mk(self.mod.PASS)),
        }
        self.assertEqual(derived, {"suspected", "likely", "confirmed"})
        for level in derived:
            self.assertIn(level, self.skill_text,
                          f"confidence level {level!r} missing from SKILL.md")

    def test_gate_statuses_match(self) -> None:
        for status in (self.mod.PASS, self.mod.FAIL, self.mod.SUPPRESSED, self.mod.NA):
            self.assertIn(status, self.skill_text,
                          f"gate status {status!r} missing from SKILL.md")

    def test_gate_letters_match(self) -> None:
        for letter in "ABCDEFGH":
            self.assertIn(f"Gate {letter}", self.skill_text)
            self.assertIn(f"Gate {letter}", self.script_src)

    def test_secret_scan_added_lines_semantics_match(self) -> None:
        # Script side: scans added lines only
        self.assertIn("parse_diff_added_lines", self.script_src)
        # Prose side: must declare the same semantics and filter the diff to + lines
        self.assertIn("ADDED LINES ONLY", self.skill_text)
        self.assertIn("grep '^+[^+]'", self.skill_text)

    def test_secret_exemptions_match(self) -> None:
        # Script exempts env/config references and allowlisted patterns;
        # the prose triage must teach the same exemptions.
        self.assertTrue(self.mod.SECRET_REFERENCE_RE.search('os.getenv("API_TOKEN")'.lower()))
        for token in ("os.Getenv", "allow_patterns", "placeholder"):
            self.assertIn(token, self.skill_text,
                          f"prose Gate E missing the script's {token!r} exemption")

    def test_frontmatter_has_only_portable_skill_fields(self) -> None:
        fm = frontmatter(self.skill_text)
        self.assertNotIn("disable-model-invocation", fm)
        self.assertNotIn("allowed-tools", fm)


if __name__ == "__main__":
    unittest.main()
