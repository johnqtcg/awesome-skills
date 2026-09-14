import fnmatch
import os
import re
import sys
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
        self.assertEqual(
            {"name", "description", "disable-model-invocation", "allowed-tools"}, keys
        )

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
            "default to treating the PR title as if it were a squash commit message",
        ):
            self.assertContainsNormalized(phrase, self.merge_text)

    def test_merge_strategy_guide_states_github_squash_message_rules(self) -> None:
        """The squash commit message depends on commit count and repo setting.

        GitHub pre-fills the single commit's own title and message for a 1-commit PR,
        and the PR title plus commit list for 2+ commits; only the "title and
        description" format carries body text, and it carries the whole description.
        A guide that promises "PR title becomes the commit message" or maps one body
        section onto the commit body teaches a rule GitHub does not implement.
        """
        for phrase in (
            "1 commit in the PR",
            "that commit's title and message",
            "2+ commits",
            "the PR title plus the list of commits",
            "Pull request title and description",
            "the entire",
            "docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/configuring-commit-squashing-for-pull-requests",
        ):
            self.assertContainsNormalized(phrase, self.merge_text)

        forbidden = (
            "pr title final commit message",
            "pr body s what changed section becomes the squash commit body",
            "what changed section becomes the squash commit body",
        )
        normalized = normalize(self.merge_text + "\n" + self.skill_text)
        for phrase in forbidden:
            self.assertNotIn(
                phrase,
                normalized,
                f"squash commit message over-claim reintroduced: {phrase!r}",
            )

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

    def test_coverage_doc_matches_the_real_test_counts(self) -> None:
        """COVERAGE.md is a second copy of the suite; derive it instead of trusting it."""
        import importlib.util

        coverage_text = (Path(__file__).resolve().parent / "COVERAGE.md").read_text()
        declared = {
            m.group(1): int(m.group(2))
            for m in re.finditer(r"`scripts/tests/(test_\w+\.py)`\s*\|\s*(\d+)", coverage_text)
        }
        modules = sorted(p.name for p in Path(__file__).resolve().parent.glob("test_*.py"))
        self.assertEqual(set(modules), set(declared), "COVERAGE.md must list every test module")

        actual = {}
        for name in modules:
            path = Path(__file__).resolve().parent / name
            spec = importlib.util.spec_from_file_location(f"coverage_probe_{name[:-3]}", path)
            module = importlib.util.module_from_spec(spec)
            assert spec and spec.loader
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            actual[name] = unittest.defaultTestLoader.loadTestsFromModule(module).countTestCases()

        self.assertEqual(declared, actual, "COVERAGE.md per-module counts are stale")

        total = re.search(r"\*\*Total\*\*\s*\|\s*\*\*(\d+)\*\*", coverage_text)
        self.assertIsNotNone(total, "COVERAGE.md must state a total")
        self.assertEqual(
            sum(actual.values()),
            int(total.group(1)),  # type: ignore[union-attr]
            "COVERAGE.md total is stale",
        )

    def test_run_regression_runs_help_and_unittest_discovery(self) -> None:
        for phrase in (
            "[1/2] Smoke-test bundled script help",
            "python3 \"${SKILL_DIR}/scripts/create_pr.py\" --help >/dev/null",
            "[2/2] Run regression tests",
            "python3 -m unittest discover -s \"${SKILL_DIR}/scripts/tests\" -p \"test_*.py\" -v",
        ):
            self.assertIn(phrase, self.run_regression_text)
        self.assertNotIn("continuing", self.run_regression_text.lower())

    def test_run_regression_needs_nothing_outside_this_repository(self) -> None:
        """The documented entrypoint must run on a fresh clone.

        It used to hard-fail on a validator under `$HOME/.codex/`, a path this
        repository does not ship, so the suite was red on every other machine
        before a single test ran. Any absolute path into a user's home is the
        same defect wearing a different filename.
        """
        # Scan the EXECUTABLE lines only. Matching the whole file would fire on
        # the comment that documents the removed path — a guard wider than its
        # subject, reporting the explanation as the defect.
        code = "\n".join(
            line
            for line in self.run_regression_text.splitlines()
            if not line.lstrip().startswith("#")
        )
        for absolute in ("$HOME/", "${HOME}/", "~/"):
            self.assertNotIn(
                absolute,
                code,
                f"run_regression.sh reaches outside the repo via {absolute!r}",
            )
        # The opt-in hook may name the variable, but never default it to a path.
        self.assertNotRegex(code, r"SKILL_CREATOR_VALIDATOR:-[^}]")

    # No "the entrypoint exits 0 with the validator unset" test here on purpose:
    # it would invoke the runner, which invokes this suite, which invokes the
    # runner. `test_run_regression_stops_when_validator_fails` can shell out only
    # because its stub validator aborts the run before the discovery step.

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
        self.assertNotIn("[1/2]", result.stdout)
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
        cls.bundled_text = BUNDLED_SCRIPT_GUIDE.read_text()

    def assertContainsNormalized(self, needle: str, haystack: str, message: str = "") -> None:
        self.assertIn(normalize(needle), normalize(haystack), message or f"missing: {needle}")

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

    def test_secret_scan_push_range_semantics_match(self) -> None:
        """Both implementations must read the pushed commits, not only the net diff."""
        self.assertIn("commits_to_push", self.script_src)
        self.assertIn("collect_pushed_range_evidence", self.script_src)
        self.assertIn('"git", "rev-list", "--reverse", f"origin/{base}..HEAD"', self.script_src)
        self.assertIn("git rev-list origin/main..HEAD", self.skill_text)
        self.assertIn("git show --format= --unified=0", self.skill_text)
        self.assertContainsNormalized(
            "Scan scope is the push range, not the net diff", self.skill_text
        )

    def test_secret_scan_range_failure_is_fail_closed_on_both_sides(self) -> None:
        self.assertIn("SECRET_SCAN_COMMIT_LIMIT", self.script_src)
        self.assertContainsNormalized(
            "If the commit range cannot be enumerated or exceeds the script's commit cap",
            self.skill_text,
        )
        self.assertContainsNormalized("fail closed as a hard publication blocker", self.skill_text)

    def test_allow_pattern_scope_matches(self) -> None:
        """Allow patterns are matched against the credential, never the whole line."""
        entries = [
            self.mod.AddedLine(
                path="a.go",
                line_no=1,
                text='k = "ghp_abcdefghijklmnopqrstuvwxyz0123456789" # example',
            )
        ]
        allow = self.mod.compile_regexes(self.mod.DEFAULT_SECRET_ALLOW_PATTERNS)
        self.assertEqual(1, len(self.mod.scan_secrets_in_added_lines(entries, allow)))
        self.assertContainsNormalized(
            "apply to the matched credential itself", self.skill_text
        )
        self.assertContainsNormalized("never to the whole line", self.skill_text)

    def test_push_url_verification_matches(self) -> None:
        """Both sides must read the whole push set: --push alone returns only the first URL."""
        self.assertIn(
            '"git", "remote", "get-url", "--push", "--all", "origin"', self.script_src
        )
        self.assertIn("git remote get-url --push --all origin", self.skill_text)
        # Every executable line of the prose fallback must read the full push set.
        # (The single-URL form may still appear inside prose that explains why it is
        # insufficient, so anchor the check to command lines.)
        command_lines = re.findall(r"(?m)^git remote get-url --push.*$", self.skill_text)
        self.assertTrue(command_lines, "Gate A prose must run the push-URL command")
        for line in command_lines:
            self.assertIn("--all", line, f"incomplete push-URL command in SKILL.md: {line}")

    def test_path_enumeration_is_machine_readable_on_both_sides(self) -> None:
        """Binary, empty, and renamed files carry no `+++` header in the patch."""
        self.assertIn("list_commit_paths", self.script_src)
        self.assertIn('"--name-only", "--format=", "-z", "--diff-filter=ACMR"', self.script_src)
        self.assertIn("core.quotePath=false", self.script_src)
        self.assertNotIn("parse_diff_target_paths", self.script_src)
        self.assertIn("--name-only", self.skill_text)
        self.assertIn("-z", self.skill_text)
        self.assertIn("core.quotePath=false", self.skill_text)

    def test_quality_dimensions_match(self) -> None:
        for dimension in self.mod.QUALITY_DIMENSIONS:
            self.assertIn(dimension, self.skill_text.lower())
        self.assertContainsNormalized(
            "Grade test, lint, and build as three independent dimensions", self.skill_text
        )
        self.assertContainsNormalized(
            "A dimension with no executed evidence keeps Gate D at `SUPPRESSED`", self.skill_text
        )
        for flag in ("--test-cmd", "--lint-cmd", "--build-cmd", "--quality-na"):
            self.assertIn(flag, self.skill_text + self.bundled_text)
            self.assertIn(flag.lstrip("-"), self.script_src)

    def test_non_executing_run_modes_match(self) -> None:
        """Every flag SKILL.md promises to reject must really be rejected.

        The prose is the specification; a documented rejection the script does not
        implement is a promise the gate cannot keep.
        """
        self.assertIn("runs_the_check", self.script_src)
        self.assertIn("QUALITY_NON_EXECUTING_ARGS", self.script_src)
        self.assertContainsNormalized(
            "a recognised tool in a mode that executes no check", self.skill_text
        )

        span = re.search(
            r"Reject per tool:(.*?)The sets are", self.skill_text, re.DOTALL
        )
        self.assertIsNotNone(span, "SKILL.md must list the rejected run modes")
        cited = set()
        for chunk in re.findall(r"`([^`]+)`", span.group(1)):  # type: ignore[union-attr]
            for token in re.split(r"[\s|]+", chunk):
                if token.startswith("-"):
                    cited.add(token.rstrip(",.…"))
        self.assertGreaterEqual(len(cited), 10, f"expected a real list, got {cited}")

        known = set(self.mod.QUALITY_UNIVERSAL_NON_EXECUTING)
        for flags in self.mod.QUALITY_NON_EXECUTING_ARGS.values():
            known |= set(flags)
        prefixes = tuple(
            prefix
            for group in self.mod.QUALITY_NON_EXECUTING_PREFIXES.values()
            for prefix in group
        )
        for flag in sorted(cited):
            self.assertTrue(
                flag in known or flag.startswith(prefixes),
                f"SKILL.md promises to reject {flag!r} but no script rule does",
            )

    def test_one_execution_mode_gate_for_every_command_source(self) -> None:
        """Prose and script must agree that a declaration is not an exemption."""
        self.assertIn("reject_non_executing_checks", self.script_src)
        self.assertIn("find_non_executing_segment", self.script_src)
        # The reject pass runs inside command resolution, so no source can skip it.
        self.assertIn(
            "return reject_non_executing_checks(checks, env=env, env_error=env_error)",
            self.script_src,
        )
        self.assertContainsNormalized(
            "applied to every source, including explicit per-dimension declarations",
            self.skill_text,
        )
        self.assertContainsNormalized(
            "A declaration states intent; it is never a substitute for execution",
            self.skill_text,
        )
        checks = self.mod.reject_non_executing_checks(
            [self.mod.QualityCheck("make -n test", ["test"], "config:test_cmd")]
        )
        self.assertEqual([], checks[0].dimensions)

    def test_environment_run_modes_match(self) -> None:
        """Prose and script must agree that MAKEFLAGS-style variables are run modes."""
        self.assertIn("QUALITY_FLAG_ENV_VARS", self.script_src)
        self.assertIn("probe_flag_environment", self.script_src)
        for var in ("MAKEFLAGS", "GNUMAKEFLAGS", "GOFLAGS", "PYTEST_ADDOPTS", "MAVEN_ARGS"):
            self.assertIn(var, self.skill_text, f"{var} missing from SKILL.md")
            self.assertIn(var, self.script_src)
        self.assertContainsNormalized(
            "The run mode can arrive through the environment, not only the argument list",
            self.skill_text,
        )
        self.assertContainsNormalized(
            "the value actually inherited by the shell that will run the checks",
            self.skill_text,
        )
        self.assertContainsNormalized(
            "If the execution mode cannot be determined, the dimension stays uncovered",
            self.skill_text,
        )
        self.assertTrue(self.mod.find_non_executing_segment("make MAKEFLAGS=n test"))
        self.assertTrue(self.mod.find_non_executing_segment("make test", {"MAKEFLAGS": "n"}))
        self.assertEqual("", self.mod.find_non_executing_segment("make test", {"MAKEFLAGS": "s"}))

    def test_assignment_precedence_rules_match(self) -> None:
        """The prose must state the measured precedence, and the script must implement it."""
        self.assertIn("flag_variable_sources", self.script_src)
        self.assertIn("QUALITY_ARG_ASSIGNMENT_TOOLS", self.script_src)
        # setdefault keeps the FIRST duplicate — the defect this rule replaced.
        self.assertNotIn("assignments.setdefault", self.script_src)
        for phrase in (
            "Duplicates: the last one wins",
            "A shell prefix replaces the inherited value",
            "cumulative with the environment, not an override",
            "refuse if either blocks",
        ):
            self.assertContainsNormalized(phrase, self.skill_text)
        self.assertTrue(
            self.mod.find_non_executing_segment("MAKEFLAGS=s MAKEFLAGS=n make test")
        )
        self.assertEqual(
            "", self.mod.find_non_executing_segment("MAKEFLAGS=n MAKEFLAGS=s make test")
        )
        self.assertTrue(
            self.mod.find_non_executing_segment("MAKEFLAGS=s make MAKEFLAGS=n test")
        )
        self.assertTrue(
            self.mod.find_non_executing_segment("MAKEFLAGS=n make MAKEFLAGS=s test")
        )

    def test_bundled_short_option_rule_matches(self) -> None:
        self.assertIn("QUALITY_NON_EXECUTING_SHORTS", self.script_src)
        self.assertIn("QUALITY_VALUE_SHORTS", self.script_src)
        self.assertContainsNormalized("Bundled short options count", self.skill_text)
        self.assertContainsNormalized(
            "parse a single-dash token left to right, letter by letter, over the raw token",
            self.skill_text,
        )
        self.assertContainsNormalized(
            "Do not require the token to be all letters", self.skill_text
        )
        # go must stay out of bundle expansion, or `-run` reads as `-r -u -n`.
        self.assertNotIn("go", self.mod.QUALITY_NON_EXECUTING_SHORTS)
        self.assertContainsNormalized("go is excluded from bundle expansion", self.skill_text)
        for cmd in ("make -sn test", "make -snj2 test", "make -nf./Makefile test"):
            self.assertEqual([], self.mod.classify_quality_dimensions(cmd), cmd)
        for cmd in ("make -sj2 test", "go test -run TestNoop ./...", "mvn -Vq test"):
            self.assertEqual(["test"], self.mod.classify_quality_dimensions(cmd), cmd)
        # An all-letters precondition is exactly what missed the value-bearing bundles.
        self.assertNotIn('re.fullmatch(r"-[A-Za-z]{2,}", name)', self.script_src)

    def test_documented_run_mode_traps_stay_credited(self) -> None:
        """The prose names three spellings that only LOOK like dry runs."""
        self.assertContainsNormalized("pytest -n 4", self.skill_text)
        self.assertContainsNormalized("mvn -q", self.skill_text)
        self.assertContainsNormalized("ctest -V", self.skill_text)
        self.assertEqual(["test"], self.mod.classify_quality_dimensions("pytest -n 4"))
        self.assertEqual(["test"], self.mod.classify_quality_dimensions("mvn -q test"))
        self.assertEqual(["test"], self.mod.classify_quality_dimensions("ctest -V"))
        self.assertEqual([], self.mod.classify_quality_dimensions("make -n test"))

    def test_compat_unknown_labels_match(self) -> None:
        unknown_label = self.mod.COMPAT_BODY_LABELS["unknown"]
        self.assertIn(unknown_label, self.skill_text)
        self.assertIn(self.mod.COMPAT_BREAKING_LABELS["unknown"], self.skill_text)
        self.assertContainsNormalized(
            "Never render an unassessed change as `non-breaking`", self.skill_text
        )

    def test_prose_fallback_range_scan_actually_finds_a_transient_secret(self) -> None:
        """Execute the SKILL.md fallback loop; a documented recipe is untested code.

        Environments without Python run the prose commands, so the loop must really
        detect a credential that exists only in an intermediate commit.
        """
        m = re.search(
            r"^(for sha in \$\(git rev-list origin/main\.\.HEAD\); do\n.*?^done)$",
            self.skill_text,
            re.DOTALL | re.MULTILINE,
        )
        self.assertIsNotNone(m, "SKILL.md must contain the push-range scan loop")
        snippet = m.group(1)  # type: ignore[union-attr]

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            remote = root / "remote.git"
            work = root / "work"
            ident = ["-c", "user.name=contract", "-c", "user.email=contract@example.com"]

            def git(*args: str, cwd: Path) -> None:
                subprocess.run(
                    ["git", "-C", str(cwd), *ident, *args],
                    check=True,
                    capture_output=True,
                    text=True,
                )

            subprocess.run(
                ["git", "init", "--bare", "--initial-branch=main", str(remote)],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "init", "--initial-branch=main", str(work)],
                check=True,
                capture_output=True,
            )
            (work / "main.go").write_text("package main\n\nfunc main() {}\n")
            git("add", "-A", cwd=work)
            git("commit", "-m", "chore: init", cwd=work)
            git("remote", "add", "origin", str(remote), cwd=work)
            git("push", "-u", "origin", "main", cwd=work)

            git("checkout", "-b", "feature/leak", cwd=work)
            (work / "cfg.go").write_text(
                'package main\n\nvar token = "ghp_abcdefghijklmnopqrstuvwxyz0123456789"\n'
            )
            (work / ".env").write_text("PASSWORD=supersecretpassword\n")
            git("add", "-A", cwd=work)
            git("commit", "-m", "feat: add cfg", cwd=work)
            (work / "cfg.go").write_text('package main\n\nfunc Cfg() string { return "ok" }\n')
            (work / ".env").unlink()
            git("add", "-A", cwd=work)
            git("commit", "-m", "fix: drop literal", cwd=work)

            net = subprocess.run(
                ["bash", "-c", "git diff origin/main...HEAD | grep -c 'ghp_' || true"],
                cwd=work,
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                "0",
                net.stdout.strip(),
                "precondition: the net diff must be clean, otherwise this proves nothing",
            )

            result = subprocess.run(
                ["bash", "-c", snippet], cwd=work, capture_output=True, text=True
            )
            self.assertIn("ghp_abcdefghijklmnopqrstuvwxyz0123456789", result.stdout)
            self.assertIn("found in commit", result.stdout)
            self.assertIn(".env", result.stdout)

    # --- frontmatter -----------------------------------------------------
    #
    # These replace an earlier `test_frontmatter_has_only_portable_skill_fields`,
    # which pinned the ABSENCE of `disable-model-invocation` and `allowed-tools`.
    # That shape came from skill-creator's `quick_validate.py`, whose allowlist is
    # five fields against the seventeen Claude Code documents. Two things were
    # wrong with deferring to it. It rejects `disable-model-invocation`, a real
    # field — so the one skill here whose terminal action is `git push` +
    # `gh pr create` was also the only one a model could invoke on its own. And it
    # explicitly ALLOWS `allowed-tools`, so pinning that field's absence was not
    # even required by the tool being accommodated. The schema check the external
    # validator used to provide now lives in
    # `test_frontmatter_fields_are_documented_claude_code_fields` below.

    #: Documented Claude Code frontmatter fields + Agent Skills packaging fields.
    #: Mirrors `skills/update-doc/scripts/validate_frontmatter.py`.
    CLAUDE_CODE_FIELDS = frozenset(
        {
            "name", "description", "when_to_use", "argument-hint", "arguments",
            "disable-model-invocation", "user-invocable", "allowed-tools",
            "disallowed-tools", "model", "effort", "context", "agent",
            "background", "hooks", "paths", "shell", "license", "metadata",
        }
    )

    #: Commands that must always reach the user as a permission prompt. The
    #: bundled script is on this list because `--create-pr` makes it run
    #: `git push` and `gh pr edit` itself: excluding the two commands while
    #: auto-approving the program that issues them would be a guard narrower
    #: than its subject.
    NEVER_AUTO_APPROVED = (
        "git push",
        "git push -u origin HEAD",
        "gh pr create",
        "gh pr edit",
        "gh api",
        "gh api -X DELETE repos/o/r",
        "python3 scripts/create_pr.py --create-pr",
        "python3 /abs/path/skills/create-pr/scripts/create_pr.py --create-pr",
    )

    def _frontmatter_fields(self) -> dict:
        """Parse the top-level `key: value` pairs. No PyYAML dependency."""
        fields = {}
        for line in frontmatter(self.skill_text).splitlines():
            if not line or line.startswith((" ", "\t", "#")):
                continue
            key, sep, value = line.partition(":")
            if sep:
                fields[key.strip()] = value.strip()
        return fields

    def _allowed_bash_patterns(self) -> list:
        """The inner patterns of every `Bash(...)` entry in allowed-tools."""
        return re.findall(r"Bash\(([^)]*)\)", self._frontmatter_fields().get("allowed-tools", ""))

    def test_frontmatter_fields_are_documented_claude_code_fields(self) -> None:
        unexpected = set(self._frontmatter_fields()) - self.CLAUDE_CODE_FIELDS
        self.assertFalse(
            unexpected, f"frontmatter carries undocumented field(s): {sorted(unexpected)}"
        )

    def test_model_invocation_is_disabled(self) -> None:
        """A skill whose terminal action is `git push` is user-invoked only."""
        self.assertEqual(
            "true",
            self._frontmatter_fields().get("disable-model-invocation", "").lower(),
            "create-pr publishes to a remote; it must not be model-invocable "
            "from its description alone",
        )

    def test_allowed_tools_declared_and_covers_evidence_gathering(self) -> None:
        patterns = self._allowed_bash_patterns()
        self.assertTrue(patterns, "allowed-tools declares no Bash commands")
        # A sample of the read-only evidence the gates actually run.
        for cmd in ("git diff --stat origin/main...HEAD", "gh repo view", "go test ./..."):
            self.assertTrue(
                any(fnmatch.fnmatch(cmd, pat) for pat in patterns),
                f"allowed-tools does not cover evidence command {cmd!r}",
            )

    def test_publishing_commands_are_never_auto_approved(self) -> None:
        """Matched as globs, not substrings.

        A substring check passes a frontmatter that wrote `Bash(git*)` or
        `Bash(gh*)` — patterns that carry no literal "git push" yet approve it.
        Match each forbidden command against every pattern the way the
        permission layer does.
        """
        patterns = self._allowed_bash_patterns()
        for cmd in self.NEVER_AUTO_APPROVED:
            covering = [pat for pat in patterns if fnmatch.fnmatch(cmd, pat)]
            self.assertFalse(
                covering,
                f"allowed-tools auto-approves {cmd!r} via {covering!r}; the "
                f"publishing step must stay behind a permission prompt",
            )


if __name__ == "__main__":
    unittest.main()
