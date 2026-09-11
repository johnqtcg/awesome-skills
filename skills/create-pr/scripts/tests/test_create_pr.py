import json
import os
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch
import importlib.util
import sys

SCRIPT_PATH = Path(__file__).resolve().parent.parent / "create_pr.py"
spec = importlib.util.spec_from_file_location("create_pr", SCRIPT_PATH)
create_pr = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = create_pr
spec.loader.exec_module(create_pr)


class CreatePRSkillTests(unittest.TestCase):
    def make_args(self, **overrides):
        base = {
            "repo": ".",
            "config": "",
            "no_config": False,
            "base": "",
            "head": "",
            "title": None,
            "issue": None,
            "reviewers": None,
            "labels": None,
            "create_pr": False,
            "dry_run": False,
            "pr_body_out": "",
            "json_out": "",
            "docs_status": None,
            "compat_status": None,
            "check_cmd": [],
            "test_cmd": [],
            "lint_cmd": [],
            "build_cmd": [],
            "quality_na": [],
            "timeout": None,
            "quality": None,
            "security_tools": None,
            "branch_protection": None,
            "secret_scan": None,
            "conflict_scan": None,
            "update_existing_pr": None,
            "problem": None,
            "approach": None,
            "risk": None,
            "rollback": None,
            "monitoring": None,
            "migration_notes": None,
            "confirm_self_review": False,
        }
        base.update(overrides)
        return Namespace(**base)

    def test_parse_diff_added_lines(self):
        diff_text = """
diff --git a/a.go b/a.go
index 111..222 100644
--- a/a.go
+++ b/a.go
@@ -10,2 +10,3 @@
- old
+new1
+new2
 context
"""
        entries = create_pr.parse_diff_added_lines(diff_text)
        self.assertEqual(2, len(entries))
        self.assertEqual("a.go", entries[0].path)
        self.assertEqual(10, entries[0].line_no)
        self.assertEqual("new1", entries[0].text)
        self.assertEqual(11, entries[1].line_no)

    def test_unquote_git_path_decodes_c_style_quoting(self):
        self.assertEqual("plain.go", create_pr.unquote_git_path("plain.go"))
        self.assertEqual('q"uote.go', create_pr.unquote_git_path('"q\\"uote.go"'))
        self.assertEqual("back\\slash.go", create_pr.unquote_git_path('"back\\\\slash.go"'))
        self.assertEqual("we\nird.go", create_pr.unquote_git_path('"we\\nird.go"'))
        self.assertEqual("配置.go", create_pr.unquote_git_path('"\\351\\205\\215\\347\\275\\256.go"'))
        self.assertEqual("b/配置.go", create_pr.unquote_git_path('"b/\\351\\205\\215\\347\\275\\256.go"'))

    def test_parse_diff_added_lines_decodes_quoted_patch_headers(self):
        """A quoted `+++` header must resolve to the real path, or the file is skipped."""
        diff_text = (
            'diff --git "a/q\\"uote.go" "b/q\\"uote.go"\n'
            '--- "a/q\\"uote.go"\n'
            '+++ "b/q\\"uote.go"\n'
            "@@ -0,0 +1 @@\n"
            '+password = "prod-credential-9981"\n'
        )
        entries = create_pr.parse_diff_added_lines(diff_text)
        self.assertEqual(1, len(entries))
        self.assertEqual('q"uote.go', entries[0].path)

    def test_scan_secrets_respects_allowlist(self):
        entries = [
            create_pr.AddedLine(path="a.go", line_no=1, text='token = "dummy-token-value"'),
            create_pr.AddedLine(path="a.go", line_no=2, text='token = "prod-secret-123456"'),
        ]
        findings = create_pr.scan_secrets_in_added_lines(
            entries,
            [create_pr.re.compile(r"(?i)dummy")],
        )
        self.assertEqual(1, len(findings))
        self.assertIn("a.go:2", findings[0])

    def test_scan_secrets_ignores_env_reference_assignment(self):
        entries = [create_pr.AddedLine(path="cfg.go", line_no=12, text='token = os.Getenv("API_TOKEN")')]
        findings = create_pr.scan_secrets_in_added_lines(entries, [])
        self.assertEqual([], findings)

    def test_scan_secrets_catches_high_signal_token(self):
        entries = [create_pr.AddedLine(path="cfg.go", line_no=7, text='github = "ghp_abcdefghijklmnopqrstuvwxyz123456"')]
        findings = create_pr.scan_secrets_in_added_lines(entries, [])
        self.assertEqual(1, len(findings))
        self.assertIn("[github_pat]", findings[0])

    def test_scan_secrets_checks_comments_and_alpha_only_passwords(self):
        entries = [
            create_pr.AddedLine(
                path="docs/runbook.md",
                line_no=4,
                text="# password = supersecretpassword",
            )
        ]
        findings = create_pr.scan_secrets_in_added_lines(entries, [])
        self.assertEqual(1, len(findings))
        self.assertIn("docs/runbook.md:4", findings[0])

    def test_sensitive_filename_scan_covers_dotenv_and_key_material(self):
        findings = create_pr.scan_sensitive_filenames(
            [
                Path(".env"),
                Path("config/.env.production"),
                Path("certs/client.pem"),
                Path("certs/client.key"),
                Path("certs/client.p12"),
                Path("README.md"),
            ],
            [],
        )
        self.assertEqual(5, len(findings))
        self.assertFalse(any("README.md" in finding for finding in findings))

    def test_filter_files_extension_and_exclude(self):
        files = [Path("cmd/main.go"), Path("docs/readme.md"), Path("vendor/a.go")]
        filtered = create_pr.filter_files(
            files,
            [".go", ".md"],
            [create_pr.re.compile(r"^vendor/")],
        )
        self.assertEqual([Path("cmd/main.go"), Path("docs/readme.md")], filtered)

    def test_filter_files_treats_dotenv_variants_as_env_files(self):
        files = [Path(".env"), Path("config/.env.local"), Path("notes.txt")]
        filtered = create_pr.filter_files(files, [".env"], [])
        self.assertEqual([Path(".env"), Path("config/.env.local")], filtered)

    def test_parse_github_slug_supports_ssh_and_https(self):
        self.assertEqual("acme/service", create_pr.parse_github_slug("git@github.com:acme/service.git"))
        self.assertEqual("acme/service", create_pr.parse_github_slug("https://github.com/acme/service.git"))
        self.assertEqual("", create_pr.parse_github_slug("/tmp/remote.git"))

    def test_conventional_title_rules_cover_length_period_and_imperative_mood(self):
        self.assertTrue(create_pr.conventional_title_errors("feat: " + "a" * 51))
        self.assertIn("subject has a trailing period", create_pr.conventional_title_errors("fix: correct leak."))
        self.assertIn("subject appears non-imperative", create_pr.conventional_title_errors("docs: added runbook"))
        self.assertEqual([], create_pr.conventional_title_errors("docs: add runbook"))

    def test_resolve_settings_reads_repo_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            cfg = {
                "base": "develop",
                "check_cmd": ["make test", "make lint"],
                "quality": {"enabled": True},
                "security_tools": {"enabled": False},
                "update_existing_pr": True,
                "secret_scan": {"allow_patterns": [r"(?i)placeholder"]},
            }
            (repo / ".create-pr.json").write_text(json.dumps(cfg))
            settings = create_pr.resolve_settings(self.make_args(), repo, "feature/x")
            self.assertEqual("develop", settings.base)
            self.assertEqual(["make test", "make lint"], settings.check_cmd)
            self.assertFalse(settings.security_tools_enabled)
            self.assertTrue(settings.update_existing_pr)
            self.assertIn(".create-pr.json", settings.config_source)

    def test_parse_required_status_checks(self):
        payload = {
            "required_status_checks": {
                "contexts": ["build", "lint"],
                "checks": [{"context": "build"}, {"context": "unit"}],
            }
        }
        checks = create_pr.parse_required_status_checks(payload)
        self.assertEqual(["build", "lint", "unit"], checks)

    def test_classify_repo_slug(self):
        owner, name = create_pr.classify_repo_slug({"nameWithOwner": "acme/service"})
        self.assertEqual("acme", owner)
        self.assertEqual("service", name)

    def test_gate_a_blocks_when_origin_and_gh_repository_do_not_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            ctx = create_pr.Context(repo=repo, base="main", branch="feature/x")
            settings = create_pr.resolve_settings(self.make_args(), repo, "feature/x")

            def fake_run(cmd, cwd, timeout=1200):
                key = tuple(cmd)
                if key[:3] == ("git", "rev-parse", "--is-inside-work-tree"):
                    return create_pr.CommandResult("git rev-parse", 0, "true", "")
                if key[:3] == ("git", "remote", "-v"):
                    return create_pr.CommandResult("git remote -v", 0, "origin git@github.com:other/repo.git", "")
                if key[:3] == ("git", "remote", "get-url"):
                    return create_pr.CommandResult("git remote get-url origin", 0, "git@github.com:other/repo.git", "")
                if key[:4] == ("gh", "auth", "status", "-h"):
                    return create_pr.CommandResult("gh auth status", 0, "ok", "")
                if key[:3] == ("gh", "repo", "view"):
                    meta = {"nameWithOwner": "acme/service", "viewerPermission": "WRITE"}
                    return create_pr.CommandResult("gh repo view", 0, json.dumps(meta), "")
                if key[:4] == ("git", "ls-remote", "--heads", "origin"):
                    return create_pr.CommandResult("git ls-remote", 0, "sha\trefs/heads/main", "")
                return create_pr.CommandResult("unexpected", 1, "", "unexpected command")

            with patch.object(create_pr, "run_cmd", side_effect=fake_run):
                result = create_pr.gate_a_preflight(ctx, settings)

            self.assertEqual(create_pr.FAIL, result.status)
            self.assertTrue(result.blocks_publish)
            self.assertIn("identity", result.evidence)

    def test_gate_a_branch_protection_missing_becomes_suppressed(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            ctx = create_pr.Context(repo=repo, base="main", branch="feature/x")
            settings = create_pr.resolve_settings(self.make_args(), repo, "feature/x")

            def fake_run(cmd, cwd, timeout=1200):
                key = tuple(cmd)
                if key[:4] == ("git", "rev-parse", "--is-inside-work-tree",):
                    return create_pr.CommandResult("git rev-parse --is-inside-work-tree", 0, "true", "")
                if key[:3] == ("git", "remote", "-v"):
                    return create_pr.CommandResult("git remote -v", 0, "origin git@github.com:acme/x.git (fetch)", "")
                if key[:3] == ("git", "remote", "get-url"):
                    return create_pr.CommandResult("git remote get-url origin", 0, "git@github.com:acme/service.git", "")
                if key[:4] == ("gh", "auth", "status", "-h"):
                    return create_pr.CommandResult("gh auth status -h github.com", 0, "ok", "")
                if key[:3] == ("gh", "repo", "view"):
                    meta = {"nameWithOwner": "acme/service", "viewerPermission": "WRITE"}
                    return create_pr.CommandResult("gh repo view", 0, json.dumps(meta), "")
                if key[:4] == ("git", "ls-remote", "--heads", "origin"):
                    return create_pr.CommandResult("git ls-remote --heads origin main", 0, "sha\trefs/heads/main", "")
                if key[:2] == ("gh", "api"):
                    return create_pr.CommandResult("gh api .../protection", 1, "", "HTTP 404 Not Found")
                return create_pr.CommandResult("unknown", 1, "", "unexpected command")

            with patch.object(create_pr, "run_cmd", side_effect=fake_run):
                result = create_pr.gate_a_preflight(ctx, settings)

            self.assertEqual(create_pr.SUPPRESSED, result.status)
            self.assertTrue(any("branch protection" in u["area"] for u in ctx.uncovered_risks))

    def test_scan_conflict_markers_requires_complete_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            f = repo / "a.go"
            f.write_text("<<<<<<< ours\nx:=1\n=======\nx:=2\n>>>>>>> theirs\n")
            findings = create_pr.scan_conflict_markers_in_files(repo, [Path("a.go")])
            self.assertEqual(1, len(findings))

    def test_scan_conflict_markers_ignores_partial_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            f = repo / "README.zh-CN.md"
            f.write_text("Example text with <<<<<<< marker only\n")
            findings = create_pr.scan_conflict_markers_in_files(repo, [Path("README.zh-CN.md")])
            self.assertEqual([], findings)

    def test_gate_a_branch_protection_missing_required_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            ctx = create_pr.Context(repo=repo, base="main", branch="feature/x")
            settings = create_pr.resolve_settings(self.make_args(), repo, "feature/x")

            def fake_run(cmd, cwd, timeout=1200):
                key = tuple(cmd)
                if key[:3] == ("git", "rev-parse", "--is-inside-work-tree"):
                    return create_pr.CommandResult("git rev-parse --is-inside-work-tree", 0, "true", "")
                if key[:3] == ("git", "remote", "-v"):
                    return create_pr.CommandResult("git remote -v", 0, "origin x", "")
                if key[:3] == ("git", "remote", "get-url"):
                    return create_pr.CommandResult("git remote get-url origin", 0, "git@github.com:acme/service.git", "")
                if key[:4] == ("gh", "auth", "status", "-h"):
                    return create_pr.CommandResult("gh auth status -h github.com", 0, "ok", "")
                if key[:3] == ("gh", "repo", "view"):
                    meta = {"nameWithOwner": "acme/service", "viewerPermission": "WRITE"}
                    return create_pr.CommandResult("gh repo view", 0, json.dumps(meta), "")
                if key[:4] == ("git", "ls-remote", "--heads", "origin"):
                    return create_pr.CommandResult("git ls-remote --heads origin main", 0, "sha\trefs/heads/main", "")
                if key[:2] == ("gh", "api"):
                    payload = {"required_status_checks": {"contexts": []}, "required_pull_request_reviews": None}
                    return create_pr.CommandResult("gh api .../protection", 0, json.dumps(payload), "")
                return create_pr.CommandResult("unknown", 1, "", "unexpected command")

            with patch.object(create_pr, "run_cmd", side_effect=fake_run):
                result = create_pr.gate_a_preflight(ctx, settings)

            self.assertEqual(create_pr.SUPPRESSED, result.status)
            self.assertTrue(any("status checks" in u["area"] or "PR reviews" in u["area"] for u in ctx.uncovered_risks))

    # --- review finding 1b: allow patterns must not be line-scoped -------------

    def test_allowlist_does_not_suppress_a_token_from_an_unrelated_comment(self):
        """A real GitHub PAT with an `example` comment on the same line is still a leak.

        Matching allow patterns against the whole added line lets any nearby word
        ("example", "sample", "test-only") exempt the credential next to it.
        """
        entries = [
            create_pr.AddedLine(
                path="cfg.go",
                line_no=3,
                text='var t = "ghp_abcdefghijklmnopqrstuvwxyz0123456789" // example usage',
            )
        ]
        findings = create_pr.scan_secrets_in_added_lines(
            entries, create_pr.compile_regexes(create_pr.DEFAULT_SECRET_ALLOW_PATTERNS)
        )
        self.assertEqual(1, len(findings), findings)
        self.assertIn("[github_pat]", findings[0])

    def test_allowlist_still_exempts_a_placeholder_value(self):
        entries = [
            create_pr.AddedLine(path="cfg.go", line_no=4, text='token = "redacted-by-policy"')
        ]
        findings = create_pr.scan_secrets_in_added_lines(
            entries, create_pr.compile_regexes([r"(?i)redacted"])
        )
        self.assertEqual([], findings)

    def test_allowlist_exempts_a_high_signal_token_only_by_matching_the_token(self):
        entries = [
            create_pr.AddedLine(
                path="testdata/fixture.go",
                line_no=1,
                text='var fake = "ghp_example00000000000000000000000000"',
            )
        ]
        self.assertEqual(
            [],
            create_pr.scan_secrets_in_added_lines(
                entries, create_pr.compile_regexes([r"(?i)ghp_example"])
            ),
        )

    def test_findings_carry_commit_attribution_when_only_in_history(self):
        entries = [
            create_pr.AddedLine(
                path="cfg.go", line_no=2, text='password = "prod-credential-9981"', commit="abc123def456"
            )
        ]
        findings = create_pr.scan_secrets_in_added_lines(entries, [])
        self.assertEqual(1, len(findings))
        self.assertIn("(commit abc123def456)", findings[0])

    # --- review finding 1: range enumeration must fail closed ------------------

    def test_range_scan_fails_closed_when_rev_list_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)

            def fake_run(cmd, cwd, timeout=1200):
                return create_pr.CommandResult(" ".join(cmd), 128, "", "fatal: bad revision")

            with patch.object(create_pr, "run_cmd", side_effect=fake_run):
                entries, paths, details, errors = create_pr.collect_pushed_range_evidence(
                    repo, "main", 30
                )
            self.assertEqual([], entries)
            self.assertEqual([], paths)
            self.assertTrue(errors, "an unreadable push range must not be reported as clean")
            self.assertIn("push range", errors[0])

    def test_range_scan_fails_closed_above_the_commit_cap(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            shas = "\n".join(f"{i:040x}" for i in range(3))

            def fake_run(cmd, cwd, timeout=1200):
                if cmd[:2] == ["git", "rev-list"]:
                    return create_pr.CommandResult(" ".join(cmd), 0, shas, "")
                raise AssertionError(f"no commit may be read past the cap: {cmd}")

            with patch.object(create_pr, "SECRET_SCAN_COMMIT_LIMIT", 2), patch.object(
                create_pr, "run_cmd", side_effect=fake_run
            ):
                entries, _paths, _details, errors = create_pr.collect_pushed_range_evidence(
                    repo, "main", 30
                )
            self.assertEqual([], entries)
            self.assertTrue(errors)
            self.assertIn("cannot prove", errors[0])

    def test_gate_e_turns_incomplete_range_evidence_into_a_publication_blocker(self):
        """An unreadable push range must block publication, not land in details only."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            ctx = create_pr.Context(repo=repo, base="main", branch="feature/x")
            settings = create_pr.resolve_settings(self.make_args(no_config=True), repo, "feature/x")

            def fake_run(cmd, cwd, timeout=1200):
                if cmd[:2] == ["git", "rev-list"]:
                    return create_pr.CommandResult(" ".join(cmd), 128, "", "fatal: bad revision")
                if cmd[:3] == ["git", "diff", "--name-only"]:
                    return create_pr.CommandResult(" ".join(cmd), 0, "a.go", "")
                return create_pr.CommandResult(" ".join(cmd), 0, "", "")

            with patch.object(create_pr, "run_cmd", side_effect=fake_run):
                result = create_pr.gate_e_security(ctx, settings)

            self.assertEqual(create_pr.FAIL, result.status, result.evidence)
            self.assertTrue(result.blocks_publish)
            self.assertIn("push range", result.evidence)

    def test_gate_a_identity_details_list_every_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            ctx = create_pr.Context(repo=repo, base="main", branch="feature/x")
            settings = create_pr.resolve_settings(self.make_args(no_config=True), repo, "feature/x")
            fake = self._gate_a_fakes(
                "git@github.com:acme/service.git", "git@github.com:acme/service.git"
            )
            with patch.object(create_pr, "run_cmd", side_effect=fake):
                result = create_pr.gate_a_preflight(ctx, settings)
            identity_lines = [d for d in result.details if d.startswith("repository identity:")]
            self.assertEqual(1, len(identity_lines), result.details)
            for label in ("fetch=acme/service", "push[0]=acme/service", "gh=acme/service"):
                self.assertIn(label, identity_lines[0])

    def test_dedupe_added_lines_prefers_the_net_diff_entry(self):
        net = create_pr.AddedLine(path="a.go", line_no=9, text="secret = x")
        historical = create_pr.AddedLine(path="a.go", line_no=3, text="secret = x", commit="deadbeef")
        other = create_pr.AddedLine(path="b.go", line_no=1, text="secret = x", commit="deadbeef")
        result = create_pr.dedupe_added_lines([net, historical, other])
        self.assertEqual(2, len(result))
        self.assertEqual("", result[0].commit)
        self.assertEqual(9, result[0].line_no)
        self.assertEqual("b.go", result[1].path)

    # --- review finding 2: the push URL is the write target -------------------

    def _gate_a_fakes(self, fetch_url, push_url, gh_slug="acme/service"):
        push_urls = push_url if isinstance(push_url, (list, tuple)) else [push_url]

        def fake_run(cmd, cwd, timeout=1200):
            key = tuple(cmd)
            if key[:3] == ("git", "rev-parse", "--is-inside-work-tree"):
                return create_pr.CommandResult("git rev-parse", 0, "true", "")
            if key[:3] == ("git", "remote", "-v"):
                return create_pr.CommandResult("git remote -v", 0, f"origin {fetch_url}", "")
            if key[:4] == ("git", "remote", "get-url", "--push"):
                self.assertIn("--all", key, "Gate A must read every push URL, not just the first")
                return create_pr.CommandResult(
                    "git remote get-url --push --all origin", 0, "\n".join(push_urls), ""
                )
            if key[:3] == ("git", "remote", "get-url"):
                return create_pr.CommandResult("git remote get-url origin", 0, fetch_url, "")
            if key[:4] == ("gh", "auth", "status", "-h"):
                return create_pr.CommandResult("gh auth status", 0, "ok", "")
            if key[:3] == ("gh", "repo", "view"):
                meta = {"nameWithOwner": gh_slug, "viewerPermission": "WRITE"}
                return create_pr.CommandResult("gh repo view", 0, json.dumps(meta), "")
            if key[:4] == ("git", "ls-remote", "--heads", "origin"):
                return create_pr.CommandResult("git ls-remote", 0, "sha\trefs/heads/main", "")
            if key[:2] == ("gh", "api"):
                return create_pr.CommandResult("gh api", 0, json.dumps({
                    "required_pull_request_reviews": {},
                    "required_status_checks": {"contexts": ["unit-test"]},
                }), "")
            return create_pr.CommandResult("unexpected", 1, "", "unexpected command")

        return fake_run

    def test_gate_a_blocks_when_push_url_targets_another_repository(self):
        """A verified fetch/gh identity must not vouch for an unverified push target.

        `git push origin HEAD` writes to remote.origin.pushurl when it is set, and git
        keeps that URL independent of the fetch URL.
        """
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            ctx = create_pr.Context(repo=repo, base="main", branch="feature/x")
            settings = create_pr.resolve_settings(self.make_args(no_config=True), repo, "feature/x")
            fake = self._gate_a_fakes(
                "git@github.com:acme/service.git",
                "git@github.com:attacker/exfil.git",
                gh_slug="acme/service",
            )
            with patch.object(create_pr, "run_cmd", side_effect=fake):
                result = create_pr.gate_a_preflight(ctx, settings)

            self.assertEqual(create_pr.FAIL, result.status)
            self.assertTrue(result.blocks_publish)
            self.assertIn("push", result.evidence)

    def test_gate_a_blocks_when_push_url_is_not_a_github_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            ctx = create_pr.Context(repo=repo, base="main", branch="feature/x")
            settings = create_pr.resolve_settings(self.make_args(no_config=True), repo, "feature/x")
            fake = self._gate_a_fakes(
                "git@github.com:acme/service.git", "/srv/mirrors/service.git"
            )
            with patch.object(create_pr, "run_cmd", side_effect=fake):
                result = create_pr.gate_a_preflight(ctx, settings)

            self.assertEqual(create_pr.FAIL, result.status)
            self.assertTrue(result.blocks_publish)
            self.assertIn("push target", result.evidence)

    def test_gate_a_blocks_when_a_second_push_url_targets_another_repository(self):
        """One `git push` writes to EVERY configured push URL.

        `git remote get-url --push origin` returns only the first URL, so checking it
        alone leaves the remaining write targets unverified.
        """
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            ctx = create_pr.Context(repo=repo, base="main", branch="feature/x")
            settings = create_pr.resolve_settings(self.make_args(no_config=True), repo, "feature/x")
            fake = self._gate_a_fakes(
                "git@github.com:acme/service.git",
                [
                    "git@github.com:acme/service.git",
                    "git@github.com:attacker/exfil.git",
                ],
                gh_slug="acme/service",
            )
            with patch.object(create_pr, "run_cmd", side_effect=fake):
                result = create_pr.gate_a_preflight(ctx, settings)

            self.assertEqual(create_pr.FAIL, result.status, result.evidence)
            self.assertTrue(result.blocks_publish)
            self.assertIn("attacker/exfil", result.evidence)
            identity_line = next(
                d for d in result.details if d.startswith("repository identity:")
            )
            self.assertIn("push[1]=attacker/exfil", identity_line)

    def test_gate_a_blocks_when_a_second_push_url_is_not_a_github_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            ctx = create_pr.Context(repo=repo, base="main", branch="feature/x")
            settings = create_pr.resolve_settings(self.make_args(no_config=True), repo, "feature/x")
            fake = self._gate_a_fakes(
                "git@github.com:acme/service.git",
                ["git@github.com:acme/service.git", "/srv/mirrors/service.git"],
            )
            with patch.object(create_pr, "run_cmd", side_effect=fake):
                result = create_pr.gate_a_preflight(ctx, settings)

            self.assertEqual(create_pr.FAIL, result.status)
            self.assertTrue(result.blocks_publish)
            self.assertIn("push target #1", result.evidence)

    def test_gate_a_passes_when_push_url_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            ctx = create_pr.Context(repo=repo, base="main", branch="feature/x")
            settings = create_pr.resolve_settings(self.make_args(no_config=True), repo, "feature/x")
            fake = self._gate_a_fakes(
                "https://github.com/acme/service.git", "https://github.com/acme/service.git"
            )
            with patch.object(create_pr, "run_cmd", side_effect=fake):
                result = create_pr.gate_a_preflight(ctx, settings)

            self.assertEqual(create_pr.PASS, result.status, result.evidence)

    # --- review finding 3: per-dimension quality coverage ---------------------

    def _quality_ctx(self, repo, **overrides):
        settings = create_pr.resolve_settings(
            self.make_args(no_config=True, **overrides), repo, "feature/x"
        )
        ctx = create_pr.Context(
            repo=repo, base="main", branch="feature/x", changed_files=[Path("x.go")]
        )
        return ctx, settings

    def test_gate_d_records_lint_gap_when_linter_is_not_installed(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "go.mod").write_text("module example.com/x\n\ngo 1.22\n")
            ctx, settings = self._quality_ctx(repo)

            real_which = create_pr.shutil.which
            with patch.object(
                create_pr.shutil,
                "which",
                side_effect=lambda name: None if name == "golangci-lint" else real_which(name),
            ), patch.object(
                create_pr,
                "run_shell",
                side_effect=lambda cmd, cwd, timeout=0: create_pr.CommandResult(cmd, 0, "ok", ""),
            ):
                result = create_pr.gate_d_quality(ctx, settings)

            self.assertEqual(create_pr.SUPPRESSED, result.status, result.evidence)
            self.assertTrue(result.blocks_ready)
            self.assertIn("lint", result.evidence)
            self.assertEqual("draft", create_pr.determine_pr_mode([result]))
            self.assertTrue(
                any(u["area"] == "quality: lint" for u in ctx.uncovered_risks),
                ctx.uncovered_risks,
            )
            self.assertTrue(ctx.quality_coverage["lint"].startswith("uncovered"))
            self.assertTrue(ctx.quality_coverage["test"].startswith("executed"))
            self.assertTrue(ctx.quality_coverage["build"].startswith("executed"))

    def test_gate_d_passes_only_when_every_dimension_has_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "go.mod").write_text("module example.com/x\n\ngo 1.22\n")
            ctx, settings = self._quality_ctx(repo)

            real_which = create_pr.shutil.which
            with patch.object(
                create_pr.shutil,
                "which",
                side_effect=lambda name: "/usr/bin/golangci-lint"
                if name == "golangci-lint"
                else real_which(name),
            ), patch.object(
                create_pr,
                "run_shell",
                side_effect=lambda cmd, cwd, timeout=0: create_pr.CommandResult(cmd, 0, "ok", ""),
            ):
                result = create_pr.gate_d_quality(ctx, settings)

            self.assertEqual(create_pr.PASS, result.status, result.evidence)
            self.assertEqual([], ctx.uncovered_risks)

    def test_gate_d_does_not_credit_an_unclassifiable_command(self):
        """`make ci` may run everything or nothing; the script must not assume."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            ctx, settings = self._quality_ctx(repo, check_cmd=["make ci"])
            with patch.object(
                create_pr,
                "run_shell",
                side_effect=lambda cmd, cwd, timeout=0: create_pr.CommandResult(cmd, 0, "ok", ""),
            ):
                result = create_pr.gate_d_quality(ctx, settings)

            self.assertEqual(create_pr.SUPPRESSED, result.status, result.evidence)
            self.assertEqual(
                {"quality: test", "quality: lint", "quality: build"},
                {u["area"] for u in ctx.uncovered_risks},
            )
            self.assertTrue(any("make ci" in u["why"] for u in ctx.uncovered_risks))

    def test_gate_d_accepts_explicit_per_dimension_declarations(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            ctx, settings = self._quality_ctx(
                repo, test_cmd=["make ci"], lint_cmd=["make ci"], build_cmd=["make ci"]
            )
            calls = []

            def fake_shell(cmd, cwd, timeout=0):
                calls.append(cmd)
                return create_pr.CommandResult(cmd, 0, "ok", "")

            with patch.object(create_pr, "run_shell", side_effect=fake_shell):
                result = create_pr.gate_d_quality(ctx, settings)

            self.assertEqual(create_pr.PASS, result.status, result.evidence)
            self.assertEqual(["make ci"], calls, "a declared command must run once, not per dimension")

    def test_gate_d_honours_declared_not_applicable_dimensions(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            ctx, settings = self._quality_ctx(
                repo, check_cmd=["pytest -q"], quality_na=["lint", "build"]
            )
            with patch.object(
                create_pr,
                "run_shell",
                side_effect=lambda cmd, cwd, timeout=0: create_pr.CommandResult(cmd, 0, "ok", ""),
            ):
                result = create_pr.gate_d_quality(ctx, settings)

            self.assertEqual(create_pr.PASS, result.status, result.evidence)
            self.assertEqual([], ctx.uncovered_risks)
            self.assertIn("N/A (declared", ctx.quality_coverage["lint"])

    def test_gate_d_reports_a_failing_dimension_as_failed_not_uncovered(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            ctx, settings = self._quality_ctx(
                repo, check_cmd=["go test ./...", "golangci-lint run", "go build ./..."]
            )
            with patch.object(
                create_pr,
                "run_shell",
                side_effect=lambda cmd, cwd, timeout=0: create_pr.CommandResult(
                    cmd, 0 if "test" in cmd else 1, "", "boom"
                ),
            ):
                result = create_pr.gate_d_quality(ctx, settings)

            self.assertEqual(create_pr.FAIL, result.status)
            self.assertIn("golangci-lint run", result.evidence)
            self.assertIn("FAILED", ctx.quality_coverage["lint"])
            self.assertFalse(any("quality: lint" == u["area"] for u in ctx.uncovered_risks))

    def test_quality_classifier_reads_argv_not_command_text(self):
        """A command that merely PRINTS tool names must earn no dimension.

        `printf '%s' 'go test ./...; golangci-lint run; go build ./...'` exits 0 and
        runs no check; a regex over the command text credited all three dimensions.
        """
        harmless = "printf '%s\\n' 'go test ./...; golangci-lint run; go build ./...'"
        self.assertEqual([], create_pr.classify_quality_dimensions(harmless))
        self.assertEqual([], create_pr.classify_quality_dimensions("echo go test ./..."))
        self.assertEqual([], create_pr.classify_quality_dimensions("sh -c 'go test ./...'"))
        self.assertEqual([], create_pr.classify_quality_dimensions("bash ci.sh # go build"))

    def test_quality_classifier_leaves_shell_expressions_unclassified(self):
        for cmd in (
            "go test ./... && golangci-lint run",
            "go test ./... ; go build ./...",
            "go test ./... | tee out.txt",
            "$CMD test",
        ):
            self.assertEqual([], create_pr.classify_quality_dimensions(cmd), cmd)

    def test_quality_classifier_keeps_quoted_arguments_classifiable(self):
        """Quoting must not disqualify a simple command: `-run 'A;B'` is one argument."""
        self.assertEqual(
            ["test"], create_pr.classify_quality_dimensions("go test -run 'TestBuild;lint' ./...")
        )
        self.assertEqual(
            ["test"], create_pr.classify_quality_dimensions("go test -run '^TestX$' ./...")
        )

    def test_gate_d_does_not_credit_a_command_that_only_prints_tool_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            harmless = "printf '%s\\n' 'go test ./...; golangci-lint run; go build ./...'"
            ctx, settings = self._quality_ctx(repo, check_cmd=[harmless])
            with patch.object(
                create_pr,
                "run_shell",
                side_effect=lambda cmd, cwd, timeout=0: create_pr.CommandResult(cmd, 0, "", ""),
            ):
                result = create_pr.gate_d_quality(ctx, settings)

            self.assertEqual(create_pr.SUPPRESSED, result.status, result.evidence)
            self.assertEqual("draft", create_pr.determine_pr_mode([result]))
            self.assertEqual(
                {"quality: test", "quality: lint", "quality: build"},
                {u["area"] for u in ctx.uncovered_risks},
            )
            for dimension in create_pr.QUALITY_DIMENSIONS:
                self.assertTrue(
                    ctx.quality_coverage[dimension].startswith("uncovered"),
                    ctx.quality_coverage,
                )

    def test_quality_classifier_rejects_non_executing_run_modes(self):
        """A correct command name in a dry-run/help/list mode executes no check.

        `make -n test lint build` prints the recipes and runs none of them, so it must
        earn no coverage at all.
        """
        for cmd in (
            "make -n test lint build",
            "make --dry-run test",
            "make -q test",
            "make test --just-print",
            "make --version",
            "go test -n ./...",
            "go test -c ./...",
            "go test -list '.*' ./...",
            "go test -list=.* ./...",
            "golangci-lint run --help",
            "golangci-lint version",
            "pytest --collect-only",
            "pytest --co -q",
            "cargo test --no-run",
            "mvn package -DskipTests",
            "mvn test -Dmaven.test.skip=true",
            "gradle test --dry-run",
            "gradle build -x test",
            "npm run lint --if-present",
            "tsc --showConfig",
            "ctest -N",
            "ruff --version",
        ):
            self.assertEqual([], create_pr.classify_quality_dimensions(cmd), cmd)

    def test_quality_classifier_keeps_executing_forms_credited(self):
        """The same spellings mean different things per tool; only run modes are rejected.

        `pytest -n 4` runs tests in parallel, `mvn -q test` is merely quiet, and
        `ctest -V` is verbose — none of them is a dry run.
        """
        for cmd, expected in (
            ("make test lint build", ["test", "lint", "build"]),
            ("go test -race -count=1 ./...", ["test"]),
            ("golangci-lint run --timeout 5m", ["lint"]),
            ("pytest -n 4", ["test"]),
            ("pytest -q -k smoke", ["test"]),
            ("mvn -q test", ["test"]),
            ("ctest -V", ["test"]),
            ("cargo clippy -- -D warnings", ["lint"]),
            ("ruff check .", ["lint"]),
            ("tsc --noEmit", ["build"]),
            ("gofmt -l .", ["lint"]),
        ):
            self.assertEqual(expected, create_pr.classify_quality_dimensions(cmd), cmd)

    def test_python_module_form_is_judged_by_the_module_run_modes(self):
        """`python -m pytest --collect-only` must be judged as pytest, not as python."""
        self.assertEqual([], create_pr.classify_quality_dimensions("python3 -m pytest --collect-only"))
        self.assertEqual([], create_pr.classify_quality_dimensions("python -m pytest --co"))
        self.assertEqual(["test"], create_pr.classify_quality_dimensions("python3 -m pytest -q"))
        self.assertEqual(["build"], create_pr.classify_quality_dimensions("python3 -m build"))
        self.assertEqual([], create_pr.classify_quality_dimensions("python3 -m build --help"))

    def test_bundled_short_options_are_expanded_per_tool(self):
        """`-sn` is `-s -n`; whole-token matching misses the dry run inside a bundle."""
        for cmd in (
            "make -sn test lint build",
            "make -ns test",
            "make -kn test",
            "make -tk test",
            "make -qs test",
            "make -hs",
            "gradle -qm build",
            "gradle -xtest build",
            "just -qn test",
            "ctest -NV",
            "cargo test -qV",
            "npm test -sv",
        ):
            self.assertEqual([], create_pr.classify_quality_dimensions(cmd), cmd)

    def test_flag_carrying_environment_variables_are_parsed(self):
        """`MAKEFLAGS=n` is `make -n` — assigned in the command or exported."""
        for cmd in (
            "make MAKEFLAGS=n test lint build",
            "MAKEFLAGS=n make test",
            "MAKEFLAGS=sn make test",
            "MAKEFLAGS=-n make test",
            "make GNUMAKEFLAGS=n test",
            "cd api && MAKEFLAGS=n make test",
            "GOFLAGS=-n go test ./...",
            "PYTEST_ADDOPTS=--collect-only pytest",
            "MAVEN_ARGS=-DskipTests mvn test",
        ):
            self.assertTrue(create_pr.find_non_executing_segment(cmd), cmd)

        for cmd in (
            "make MAKEFLAGS=s test",
            "MAKEFLAGS=s make test",
            "MAKEFLAGS= make test",
            "MAKEFLAGS=j2 make test",
            "make TESTS=1 build",
            "CGO_ENABLED=0 go test ./...",
            "GOFLAGS=-mod=vendor go test ./...",
            "PYTEST_ADDOPTS=-n 4 pytest",
            "MAVEN_ARGS=-B mvn test",
            "FOO=n make test",
        ):
            self.assertEqual("", create_pr.find_non_executing_segment(cmd), cmd)

    def test_duplicate_assignments_resolve_last_wins(self):
        """The shell and make both keep the LAST duplicate assignment, not the first.

        Verified against real make: `MAKEFLAGS=s MAKEFLAGS=n make …` runs nothing,
        `MAKEFLAGS=n MAKEFLAGS=s make …` runs everything. Both directions are asserted,
        so neither a missed dry run nor a false refusal can pass.
        """
        for cmd in (
            "MAKEFLAGS=s MAKEFLAGS=n make test lint build",
            "make MAKEFLAGS=s MAKEFLAGS=n test lint build",
            "MAKEFLAGS=j2 MAKEFLAGS=n make test",
            "make MAKEFLAGS=s MAKEFLAGS=sn test",
        ):
            self.assertTrue(create_pr.find_non_executing_segment(cmd), cmd)
        for cmd in (
            "MAKEFLAGS=n MAKEFLAGS=s make test lint build",
            "make MAKEFLAGS=n MAKEFLAGS=s test lint build",
            "MAKEFLAGS=n MAKEFLAGS= make test",
            "make MAKEFLAGS=n MAKEFLAGS=j2 test",
        ):
            self.assertEqual("", create_pr.find_non_executing_segment(cmd), cmd)

    def test_command_line_assignment_is_cumulative_with_the_environment(self):
        """Measured: neither layer cancels the other's switches for MAKEFLAGS.

        `MAKEFLAGS=n make MAKEFLAGS=s test` and `MAKEFLAGS=s make MAKEFLAGS=n test`
        both execute nothing, so a refusal must come from *either* layer.
        """
        self.assertTrue(create_pr.find_non_executing_segment("MAKEFLAGS=n make MAKEFLAGS=s test"))
        self.assertTrue(create_pr.find_non_executing_segment("MAKEFLAGS=s make MAKEFLAGS=n test"))
        self.assertTrue(
            create_pr.find_non_executing_segment("make MAKEFLAGS=s test", {"MAKEFLAGS": "n"})
        )
        self.assertTrue(
            create_pr.find_non_executing_segment("make MAKEFLAGS=n test", {"MAKEFLAGS": "s"})
        )
        # A shell prefix REPLACES the inherited value, so this one really does run.
        self.assertEqual(
            "", create_pr.find_non_executing_segment("MAKEFLAGS=s make test", {"MAKEFLAGS": "n"})
        )
        self.assertEqual(
            "", create_pr.find_non_executing_segment("MAKEFLAGS= make test", {"MAKEFLAGS": "n"})
        )

    def test_flag_variable_sources_reports_both_layers(self):
        self.assertEqual(
            [("in the command", "s"), ("in the command", "n")],
            create_pr.flag_variable_sources("MAKEFLAGS", {"MAKEFLAGS": "s"}, {"MAKEFLAGS": "n"}, None),
        )
        self.assertEqual(
            [("inherited", "n"), ("in the command", "s")],
            create_pr.flag_variable_sources("MAKEFLAGS", {}, {"MAKEFLAGS": "s"}, {"MAKEFLAGS": "n"}),
        )
        # The prefix replaces the inherited value instead of adding to it.
        self.assertEqual(
            [("in the command", "s")],
            create_pr.flag_variable_sources("MAKEFLAGS", {"MAKEFLAGS": "s"}, {}, {"MAKEFLAGS": "n"}),
        )
        self.assertEqual(
            [], create_pr.flag_variable_sources("MAKEFLAGS", {}, {}, {"GOFLAGS": "-n"})
        )

    def test_argument_assignments_only_count_for_tools_that_accept_them(self):
        """`pytest PYTEST_ADDOPTS=--collect-only` is a path argument, not an assignment."""
        self.assertEqual(
            "", create_pr.find_non_executing_segment("pytest PYTEST_ADDOPTS=--collect-only")
        )
        self.assertEqual("", create_pr.find_non_executing_segment("go test GOFLAGS=-n ./..."))
        self.assertTrue(create_pr.find_non_executing_segment("make MAKEFLAGS=n test"))
        self.assertIn("make", create_pr.QUALITY_ARG_ASSIGNMENT_TOOLS)
        self.assertNotIn("pytest", create_pr.QUALITY_ARG_ASSIGNMENT_TOOLS)
        self.assertNotIn("go", create_pr.QUALITY_ARG_ASSIGNMENT_TOOLS)

    def test_inherited_environment_applies_to_the_right_tool_only(self):
        env = {"MAKEFLAGS": "n"}
        self.assertIn("inherited MAKEFLAGS=n", create_pr.find_non_executing_segment("make test", env))
        self.assertEqual("", create_pr.find_non_executing_segment("go test ./...", env))
        self.assertEqual("", create_pr.find_non_executing_segment("pytest", env))
        # A command-line assignment overrides the inherited value, including clearing it.
        self.assertEqual("", create_pr.find_non_executing_segment("MAKEFLAGS= make test", env))
        self.assertEqual("", create_pr.find_non_executing_segment("MAKEFLAGS=s make test", env))

    def test_env_flag_arguments_follows_make_bare_letter_semantics(self):
        self.assertEqual(["-n"], create_pr.env_flag_arguments("MAKEFLAGS", "n"))
        self.assertEqual(["-sn"], create_pr.env_flag_arguments("MAKEFLAGS", "sn"))
        self.assertEqual(["-n"], create_pr.env_flag_arguments("MAKEFLAGS", "-n"))
        self.assertEqual(["-sn", "-j2"], create_pr.env_flag_arguments("MAKEFLAGS", "sn -j2"))
        self.assertEqual([], create_pr.env_flag_arguments("MAKEFLAGS", ""))
        # A bare word is only a switch bundle for MAKEFLAGS-style variables.
        self.assertEqual([], create_pr.env_flag_arguments("GOFLAGS", "n"))
        self.assertEqual(["-n"], create_pr.env_flag_arguments("GOFLAGS", "-n"))
        # MAKEFLAGS may also carry variable assignments; those are not switches.
        self.assertEqual(["-n"], create_pr.env_flag_arguments("MAKEFLAGS", "n FOO=bar"))

    def test_undetermined_environment_keeps_the_dimension_uncovered(self):
        """If the execution environment cannot be read, nothing may be credited."""
        checks = create_pr.reject_non_executing_checks(
            [create_pr.QualityCheck("make test", ["test"], "makefile")],
            env={},
            env_error="cannot read the execution environment: boom",
        )
        self.assertEqual([], checks[0].dimensions)
        self.assertEqual(["test"], checks[0].rejected_dimensions)
        self.assertIn("cannot read the execution environment", checks[0].rejected)

        # A command that reads no flags from the environment is unaffected.
        unaffected = create_pr.reject_non_executing_checks(
            [create_pr.QualityCheck("golangci-lint run", ["lint"], "language-default")],
            env={},
            env_error="cannot read the execution environment: boom",
        )
        self.assertEqual(["lint"], unaffected[0].dimensions)

    def test_uses_flag_environment_detects_the_tools_that_read_flags(self):
        for cmd in ("make test", "MAKEFLAGS=s make test", "go test ./...", "pytest -q",
                    "mvn test", "python3 -m pytest -q"):
            self.assertTrue(create_pr.uses_flag_environment(cmd), cmd)
        for cmd in ("golangci-lint run", "./verify.sh", "npm run lint", "cargo test"):
            self.assertFalse(create_pr.uses_flag_environment(cmd), cmd)

    def test_probe_flag_environment_reads_the_execution_shell(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            with patch.dict(os.environ, {"MAKEFLAGS": "n"}):
                values, error = create_pr.probe_flag_environment(repo, 60, ("MAKEFLAGS",))
            self.assertEqual("", error)
            self.assertEqual({"MAKEFLAGS": "n"}, values)

    def test_probe_flag_environment_reports_failure_instead_of_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            with patch.object(
                create_pr, "run_cmd",
                side_effect=lambda cmd, cwd, timeout=1200: create_pr.CommandResult(
                    " ".join(cmd), 127, "", "zsh: not found"
                ),
            ):
                values, error = create_pr.probe_flag_environment(repo, 60, ("MAKEFLAGS",))
            self.assertEqual({}, values)
            self.assertIn("cannot read the execution environment", error)

    def test_bundled_short_options_with_values_are_still_expanded(self):
        """A bundle carrying a value must not switch the parser off.

        `make -snj2` is `-s -n -j2` and `make -nf./Makefile` is `-n -f ./Makefile`:
        both execute nothing. Requiring the token to be all letters skipped them.
        """
        for cmd in (
            "make -snj2 test lint build",
            "make -nf./Makefile test lint build",
            "make -nj2 test",
            "make -n2 test",
            "make -njobs test",
            "make -sqB test",
            "make -f./mk -n test",
            "gradle -qmi build",
            "ctest -Nj4",
        ):
            self.assertEqual([], create_pr.classify_quality_dimensions(cmd), cmd)

    def test_value_bearing_bundles_that_do_run_stay_credited(self):
        """The stop rule must keep digits and paths in an option value harmless."""
        for cmd, expected in (
            ("make -sj2 test", ["test"]),
            ("make -C./sub test", ["test"]),
            ("make -I./inc test", ["test"]),
            ("make -W./f test", ["test"]),
            ("make -l2.5 test", ["test"]),
            ("make -Onone test", ["test"]),
            ("mvn -T4 test", ["test"]),
            ("mvn -Dtest=Foo test", ["test"]),
            ("mvn -Vq test", ["test"]),
            ("gradle -Pver=1 test", ["test"]),
            ("gradle -b./b.gradle test", ["test"]),
            ("ctest -R^smoke$", ["test"]),
            ("ctest -MNightly", ["test"]),
            ("npm -C./sub test", ["test"]),
            ("cargo test -Zunstable-options", ["test"]),
            ("just -f./justfile test", ["test"]),
        ):
            self.assertEqual(expected, create_pr.classify_quality_dimensions(cmd), cmd)

    def test_long_options_are_not_read_as_a_letter_bundle(self):
        """`make --no-print-directory` contains n and t but is not `-n -t`.

        The stop-at-a-non-letter rule is what keeps long options out of the bundle
        scan; without it these credited commands would be refused.
        """
        for cmd, expected in (
            ("make --no-print-directory test", ["test"]),
            ("make --output-sync=target test", ["test"]),
            ("make --always-make test", ["test"]),
            ("gradle --continue build", ["build"]),
        ):
            self.assertEqual(expected, create_pr.classify_quality_dimensions(cmd), cmd)
        # Long options that really are non-executing are matched exactly, not by letter.
        for cmd in ("make --dry-run test", "make --just-print test", "gradle --dry-run build"):
            self.assertEqual([], create_pr.classify_quality_dimensions(cmd), cmd)

    def test_bundle_scan_stops_interpreting_after_a_non_letter(self):
        """After a non-letter the token is an option's value, not more flags.

        `make -s2n` is malformed (make rejects `-2`), so the scan stops rather than
        reading an `-n` out of the remainder.
        """
        self.assertEqual("", create_pr.non_executing_argument("make", ["-s2n"]))
        self.assertEqual("", create_pr.non_executing_argument("make", ["--no-print-directory"]))
        self.assertEqual("-sn", create_pr.non_executing_argument("make", ["-sn"]))
        self.assertEqual("-snj2", create_pr.non_executing_argument("make", ["-snj2"]))
        self.assertEqual("-nf./Makefile", create_pr.non_executing_argument("make", ["-nf./Makefile"]))

    def test_value_shorts_only_list_options_that_take_a_value(self):
        """A letter listed as value-taking ends the scan, so a wrong entry hides a dry run.

        `mvn -o` is offline and consumes nothing; listing it would make `mvn -ov`
        look executable.
        """
        self.assertNotIn("o", create_pr.QUALITY_VALUE_SHORTS["mvn"])
        self.assertIn("T", create_pr.QUALITY_VALUE_SHORTS["mvn"])
        self.assertIn("O", create_pr.QUALITY_VALUE_SHORTS["make"])
        for tool, shorts in create_pr.QUALITY_NON_EXECUTING_SHORTS.items():
            overlap = shorts & create_pr.QUALITY_VALUE_SHORTS.get(tool, frozenset())
            self.assertEqual(
                set(),
                overlap - set("x"),  # gradle -x is both, and is checked as blocked first
                f"{tool}: a blocked letter must not also end the scan: {overlap}",
            )

    def test_bundle_scan_stops_at_a_value_taking_short_option(self):
        """Letter-level scanning is only sound if a value-consuming letter ends it.

        Otherwise `make -fMakefile.test` "contains -t", `mvn -Pdev` "contains -v", and
        `go test -run X` would read as `-r -u -n`.
        """
        for cmd, expected in (
            ("make -fMakefile.test test", ["test"]),
            ("make -fmytest test", ["test"]),
            ("make -j4 test", ["test"]),
            ("make -rR test", ["test"]),
            ("make -si test", ["test"]),
            ("mvn -Pdev test", ["test"]),
            ("gradle -Pmax=1 test", ["test"]),
            ("go test -run TestNoop ./...", ["test"]),
            ("go test -count=1 -v ./...", ["test"]),
            ("cargo test -j4", ["test"]),
            ("ctest -R smoke", ["test"]),
            ("just -f justfile test", ["test"]),
            ("npm -w pkg test", ["test"]),
            ("pytest -qs", ["test"]),
        ):
            self.assertEqual(expected, create_pr.classify_quality_dimensions(cmd), cmd)

    def test_find_non_executing_segment_scans_every_segment(self):
        self.assertIn("make -n", create_pr.find_non_executing_segment("make -n test"))
        self.assertIn("make -sn", create_pr.find_non_executing_segment("make -sn test"))
        self.assertIn(
            "make -n", create_pr.find_non_executing_segment("make lint && make -n test")
        )
        self.assertIn(
            "pytest --collect-only",
            create_pr.find_non_executing_segment("cd api && python3 -m pytest --collect-only"),
        )
        # Nothing recognisable to contradict a declaration: the declaration stands.
        self.assertEqual("", create_pr.find_non_executing_segment("make ci"))
        self.assertEqual("", create_pr.find_non_executing_segment("bash ci.sh"))
        self.assertEqual("", create_pr.find_non_executing_segment("make ci && ./verify.sh"))
        self.assertEqual(
            "", create_pr.find_non_executing_segment("go test ./... && golangci-lint run")
        )

    def test_declared_dimension_still_goes_through_execution_mode_check(self):
        """Declaring a dimension says what a command is for, not that it ran."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            ctx, settings = self._quality_ctx(
                repo,
                test_cmd=["make -n test"],
                lint_cmd=["make -n lint"],
                build_cmd=["make -n build"],
            )
            with patch.object(
                create_pr,
                "run_shell",
                side_effect=lambda cmd, cwd, timeout=0: create_pr.CommandResult(cmd, 0, "", ""),
            ):
                result = create_pr.gate_d_quality(ctx, settings)

            self.assertEqual(create_pr.SUPPRESSED, result.status, result.evidence)
            self.assertEqual(
                {"quality: test", "quality: lint", "quality: build"},
                {u["area"] for u in ctx.uncovered_risks},
            )
            for dimension in create_pr.QUALITY_DIMENSIONS:
                self.assertIn("declared via config", ctx.quality_coverage[dimension])
            self.assertTrue(
                any(d.startswith("rejected non-executing commands:") for d in result.details),
                result.details,
            )

    def test_reject_non_executing_checks_moves_dimensions_aside(self):
        checks = create_pr.reject_non_executing_checks([
            create_pr.QualityCheck("make -n test", ["test"], "config:test_cmd"),
            create_pr.QualityCheck("make lint", ["lint"], "makefile"),
        ])
        self.assertEqual([], checks[0].dimensions)
        self.assertEqual(["test"], checks[0].rejected_dimensions)
        self.assertIn("executes no check", checks[0].rejected)
        self.assertEqual(["lint"], checks[1].dimensions)
        self.assertEqual("", checks[1].rejected)

    def test_runs_the_check_is_per_tool(self):
        self.assertFalse(create_pr.runs_the_check("make", ["-n", "test"]))
        self.assertTrue(create_pr.runs_the_check("pytest", ["-n", "4"]))
        self.assertFalse(create_pr.runs_the_check("make", ["-q"]))
        self.assertTrue(create_pr.runs_the_check("mvn", ["-q", "test"]))
        self.assertFalse(create_pr.runs_the_check("cargo", ["-V"]))
        self.assertTrue(create_pr.runs_the_check("ctest", ["-V"]))
        for tool in ("make", "go", "pytest", "npm"):
            self.assertFalse(create_pr.runs_the_check(tool, ["--help"]), tool)
            self.assertFalse(create_pr.runs_the_check(tool, ["--version"]), tool)

    def test_quality_dimension_classification(self):
        self.assertEqual(["test"], create_pr.classify_quality_dimensions("go test ./..."))
        self.assertEqual(["lint"], create_pr.classify_quality_dimensions("golangci-lint run"))
        self.assertEqual(["build"], create_pr.classify_quality_dimensions("cd svc && go build ./..."))
        self.assertEqual(["test"], create_pr.classify_quality_dimensions("make unit-test"))
        self.assertEqual([], create_pr.classify_quality_dimensions("make ci"))
        self.assertEqual([], create_pr.classify_quality_dimensions("./scripts/verify.sh"))

    def test_makefile_targets_are_read_without_executing_make(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "Makefile").write_text(
                ".PHONY: test lint\n"
                "GOFLAGS := -mod=readonly\n"
                "test:\n\tgo test ./...\n"
                "lint:\n\tgolangci-lint run\n"
            )
            targets = create_pr.makefile_targets(repo)
            self.assertIn("test", targets)
            self.assertIn("lint", targets)
            self.assertNotIn("GOFLAGS", targets)
            checks = {c.cmd: c.dimensions for c in create_pr.discover_quality_checks(repo, [])}
            self.assertEqual(["test"], checks["make test"])
            self.assertEqual(["lint"], checks["make lint"])
            self.assertNotIn("make build", checks, "an undeclared target must not be invented")

    # --- review finding 4: the body must not assert an unassessed verdict -----

    def test_body_reports_unknown_compatibility_honestly(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            settings = create_pr.resolve_settings(
                self.make_args(
                    no_config=True,
                    compat_status="unknown",
                    problem="p",
                    approach="a",
                ),
                repo,
                "feature/x",
            )
            ctx = create_pr.Context(repo=repo, base="main", branch="feature/x")
            body = create_pr.build_body(settings, ctx, [], confidence="likely")

            self.assertIn("Breaking change: unknown — not assessed", body)
            self.assertIn("Compatibility: `unknown (not assessed)`", body)
            self.assertIn("Unconfirmed", body)
            self.assertNotIn("non-breaking", body)
            self.assertNotIn("No migration required", body)

    def test_body_reports_assessed_compatibility_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            settings = create_pr.resolve_settings(
                self.make_args(no_config=True, compat_status="compatible"), repo, "feature/x"
            )
            ctx = create_pr.Context(repo=repo, base="main", branch="feature/x")
            body = create_pr.build_body(settings, ctx, [], confidence="confirmed")
            self.assertIn("Breaking change: no", body)
            self.assertIn("Compatibility: `non-breaking`", body)

    def test_body_renders_quality_coverage_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            settings = create_pr.resolve_settings(
                self.make_args(no_config=True, compat_status="compatible"), repo, "feature/x"
            )
            ctx = create_pr.Context(repo=repo, base="main", branch="feature/x")
            ctx.quality_coverage = {
                "test": "executed: go test ./...",
                "lint": "uncovered: no lint command discovered (golangci-lint not installed)",
                "build": "N/A (declared by quality.not_applicable)",
            }
            body = create_pr.build_body(settings, ctx, [], confidence="likely")
            self.assertIn("| lint | uncovered: no lint command discovered", body)
            self.assertIn("| test | executed: go test ./... |", body)
            self.assertIn("| build | N/A (declared by quality.not_applicable) |", body)

    def test_gate_h_updates_existing_pr(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            ctx = create_pr.Context(repo=repo, base="main", branch="feature/x")
            settings = create_pr.Settings(
                repo=repo,
                base="main",
                branch="feature/x",
                title="feat(test): demo",
                issue="",
                reviewers="",
                labels="",
                create_pr=True,
                dry_run=False,
                timeout=30,
                pr_body_out=None,
                json_out=None,
                docs_status="yes",
                compat_status="compatible",
                check_cmd=[],
                quality_enabled=True,
                quality_dimension_cmds={dim: [] for dim in create_pr.QUALITY_DIMENSIONS},
                quality_not_applicable=[],
                security_tools_enabled=True,
                branch_protection_enabled=True,
                branch_protection_require_pr_reviews=True,
                branch_protection_require_status_checks=True,
                branch_protection_required_checks=[],
                update_existing_pr=True,
                secret_scan_enabled=True,
                secret_include_extensions=[".go"],
                secret_exclude_regex=[],
                secret_allow_regex=[],
                conflict_scan_enabled=True,
                conflict_include_extensions=[".go"],
                conflict_exclude_regex=[],
                conflict_scan_changed_files_only=True,
                config_source="test",
            )

            def fake_run(cmd, cwd, timeout=1200):
                key = tuple(cmd)
                if key[:3] == ("git", "push", "-u"):
                    return create_pr.CommandResult("git push", 0, "", "")
                if key[:3] == ("gh", "pr", "list"):
                    payload = [{"number": 12, "url": "https://example/pr/12", "isDraft": False, "title": "old"}]
                    return create_pr.CommandResult("gh pr list", 0, json.dumps(payload), "")
                if key[:3] == ("gh", "pr", "edit"):
                    return create_pr.CommandResult("gh pr edit", 0, "", "")
                if key[:4] == ("gh", "pr", "ready", "--undo"):
                    return create_pr.CommandResult("gh pr ready --undo", 0, "", "")
                if key[:3] == ("gh", "pr", "view"):
                    meta = {
                        "number": 12,
                        "url": "https://example/pr/12",
                        "state": "OPEN",
                        "isDraft": False,
                        "baseRefName": "main",
                        "headRefName": "feature/x",
                        "title": "feat(test): demo",
                        "body": "body\n",
                    }
                    return create_pr.CommandResult("gh pr view", 0, json.dumps(meta), "")
                return create_pr.CommandResult("unknown", 1, "", "unexpected command")

            with patch.object(create_pr, "run_cmd", side_effect=fake_run):
                body_path = repo / "body.md"
                body_path.write_text("body\n")
                result = create_pr.gate_h_create_or_update_pr(
                    settings,
                    ctx,
                    body_path,
                    pr_mode="ready",
                    pre_publish_gates=[create_pr.GateResult("Gate A", create_pr.SUPPRESSED, "low risk")],
                )

            self.assertEqual(create_pr.PASS, result.status)
            self.assertIn("updated", result.evidence)

    def test_gate_h_does_not_push_when_a_hard_blocker_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            ctx = create_pr.Context(repo=repo, base="main", branch="feature/x")
            settings = create_pr.resolve_settings(self.make_args(create_pr=True), repo, "feature/x")
            body_path = repo / "body.md"
            body_path.write_text("body\n")
            blocker = create_pr.GateResult(
                "Gate E",
                create_pr.FAIL,
                "secret matched",
                blocks_ready=True,
                blocks_publish=True,
            )

            with patch.object(create_pr, "run_cmd") as mocked_run:
                result = create_pr.gate_h_create_or_update_pr(
                    settings,
                    ctx,
                    body_path,
                    pr_mode="draft",
                    pre_publish_gates=[blocker],
                )

            mocked_run.assert_not_called()
            self.assertEqual(create_pr.NA, result.status)
            self.assertIn("blocked", result.evidence)

    def test_gate_h_does_not_push_when_existing_pr_query_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            ctx = create_pr.Context(
                repo=repo,
                base="main",
                branch="feature/x",
                pr_title="feat: demo",
            )
            settings = create_pr.resolve_settings(
                self.make_args(create_pr=True, title="feat: demo"),
                repo,
                "feature/x",
            )
            body_path = repo / "body.md"
            body_path.write_text("body\n")
            calls = []

            def fake_run(cmd, cwd, timeout=1200):
                calls.append(tuple(cmd))
                if tuple(cmd)[:3] == ("gh", "pr", "list"):
                    return create_pr.CommandResult("gh pr list", 1, "", "API unavailable")
                return create_pr.CommandResult("unexpected", 1, "", "unexpected command")

            with patch.object(create_pr, "run_cmd", side_effect=fake_run):
                result = create_pr.gate_h_create_or_update_pr(
                    settings,
                    ctx,
                    body_path,
                    pr_mode="ready",
                    pre_publish_gates=[create_pr.GateResult("Gate A", create_pr.PASS, "ok")],
                )

            self.assertEqual(create_pr.FAIL, result.status)
            self.assertFalse(any(call[:3] == ("git", "push", "-u") for call in calls))

    def test_gate_h_fails_when_verified_metadata_does_not_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            ctx = create_pr.Context(repo=repo, base="main", branch="feature/x", pr_title="feat: demo")
            settings = create_pr.resolve_settings(
                self.make_args(create_pr=True, title="feat: demo", update_existing_pr=False),
                repo,
                "feature/x",
            )
            body_path = repo / "body.md"
            body_path.write_text("expected body\n")

            def fake_run(cmd, cwd, timeout=1200):
                key = tuple(cmd)
                if key[:3] == ("git", "push", "-u"):
                    return create_pr.CommandResult("git push", 0, "", "")
                if key[:3] == ("gh", "pr", "create"):
                    return create_pr.CommandResult("gh pr create", 0, "https://example/pr/7", "")
                if key[:3] == ("gh", "pr", "view"):
                    payload = {
                        "number": 7,
                        "url": "https://example/pr/7",
                        "state": "OPEN",
                        "isDraft": False,
                        "baseRefName": "develop",
                        "headRefName": "feature/x",
                        "title": "feat: demo",
                        "body": "wrong body",
                    }
                    return create_pr.CommandResult("gh pr view", 0, json.dumps(payload), "")
                return create_pr.CommandResult("unexpected", 1, "", "unexpected command")

            with patch.object(create_pr, "run_cmd", side_effect=fake_run):
                result = create_pr.gate_h_create_or_update_pr(
                    settings,
                    ctx,
                    body_path,
                    pr_mode="ready",
                    pre_publish_gates=[create_pr.GateResult("Gate A", create_pr.PASS, "ok")],
                )

            self.assertEqual(create_pr.FAIL, result.status)
            self.assertIn("base", result.evidence)
            self.assertTrue(any("body" in detail for detail in result.details))

    def test_determine_confidence_maps_gate_statuses(self):
        confirmed = create_pr.determine_confidence(
            [create_pr.GateResult("Gate A", create_pr.PASS, "ok")]
        )
        likely = create_pr.determine_confidence(
            [create_pr.GateResult("Gate A", create_pr.SUPPRESSED, "gap")]
        )
        suspected = create_pr.determine_confidence(
            [create_pr.GateResult("Gate A", create_pr.FAIL, "bad")]
        )

        self.assertEqual("confirmed", confirmed)
        self.assertEqual("likely", likely)
        self.assertEqual("suspected", suspected)

    def test_determine_pr_mode_distinguishes_low_and_high_residual_risk(self):
        low_risk_suppression = [
            create_pr.GateResult("Gate A", create_pr.SUPPRESSED, "protection unavailable")
        ]
        ready_blocking_suppression = [
            create_pr.GateResult(
                "Gate D",
                create_pr.SUPPRESSED,
                "quality unavailable",
                blocks_ready=True,
            )
        ]
        self.assertEqual("ready", create_pr.determine_pr_mode(low_risk_suppression))
        self.assertEqual("draft", create_pr.determine_pr_mode(ready_blocking_suppression))

    def test_gate_f_requires_real_narrative_and_breaking_migration_notes(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            settings = create_pr.resolve_settings(
                self.make_args(docs_status="yes", compat_status="breaking"),
                repo,
                "feature/x",
            )
            ctx = create_pr.Context(repo=repo, base="main", branch="feature/x")
            result = create_pr.gate_f_docs_compat(ctx, settings)
            self.assertEqual(create_pr.FAIL, result.status)
            self.assertTrue(result.blocks_ready)
            self.assertIn("migration", result.evidence)

    def test_build_body_includes_changed_files_and_uncovered_risk(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            settings = create_pr.resolve_settings(
                self.make_args(
                    problem="Quota spikes can exhaust the shared worker pool.",
                    approach="Reject excess work at the API boundary to protect downstream capacity.",
                    risk="Valid burst traffic may be throttled.",
                    rollback="Disable the quota guard flag; no data rollback is required.",
                    monitoring="Watch rejection rate and worker saturation.",
                    migration_notes="No migration is required.",
                ),
                repo,
                "feature/x",
            )
            ctx = create_pr.Context(
                repo=repo,
                base="main",
                branch="feature/x",
                changed_files=[Path("cmd/app/main.go"), Path("README.md")],
                test_results=[create_pr.CommandResult("go test ./...", 0, "ok", "")],
                high_risk_areas=["public_api"],
            )
            create_pr.add_uncovered(
                ctx,
                "branch protection",
                "API unavailable",
                "required checks may be unknown",
                "verify settings manually",
                "repo admin",
            )
            gates = [create_pr.GateResult("Gate A", create_pr.SUPPRESSED, "branch protection unavailable")]

            body = create_pr.build_body(settings, ctx, gates, confidence="likely")

            self.assertIn("cmd/app/main.go", body)
            self.assertIn("README.md", body)
            self.assertIn("public_api", body)
            self.assertIn("Area: branch protection", body)
            self.assertIn("go test ./...", body)
            self.assertIn("Reject excess work at the API boundary", body)
            self.assertIn("Disable the quota guard flag", body)
            self.assertNotIn("Uses the `create-pr` gated workflow", body)
            self.assertNotIn("revert PR commit set and redeploy", body)


if __name__ == "__main__":
    unittest.main()
