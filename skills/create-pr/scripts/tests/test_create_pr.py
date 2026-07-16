import json
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
