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
        entries = [create_pr.AddedLine(path="cfg.go", line_no=12, text='token := os.Getenv("API_TOKEN")')]
        findings = create_pr.scan_secrets_in_added_lines(entries, [])
        self.assertEqual([], findings)

    def test_scan_secrets_catches_high_signal_token(self):
        entries = [create_pr.AddedLine(path="cfg.go", line_no=7, text='github = "ghp_abcdefghijklmnopqrstuvwxyz123456"')]
        findings = create_pr.scan_secrets_in_added_lines(entries, [])
        self.assertEqual(1, len(findings))
        self.assertIn("[github_pat]", findings[0])

    def test_filter_files_extension_and_exclude(self):
        files = [Path("cmd/main.go"), Path("docs/readme.md"), Path("vendor/a.go")]
        filtered = create_pr.filter_files(
            files,
            [".go", ".md"],
            [create_pr.re.compile(r"^vendor/")],
        )
        self.assertEqual([Path("cmd/main.go"), Path("docs/readme.md")], filtered)

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
                        "isDraft": True,
                        "baseRefName": "main",
                        "headRefName": "feature/x",
                    }
                    return create_pr.CommandResult("gh pr view", 0, json.dumps(meta), "")
                return create_pr.CommandResult("unknown", 1, "", "unexpected command")

            with patch.object(create_pr, "run_cmd", side_effect=fake_run):
                result = create_pr.gate_h_create_or_update_pr(settings, ctx, Path("/tmp/body.md"), confidence="likely")

            self.assertEqual(create_pr.PASS, result.status)
            self.assertIn("updated", result.evidence)


if __name__ == "__main__":
    unittest.main()
