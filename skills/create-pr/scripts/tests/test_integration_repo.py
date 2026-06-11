"""Integration tests: run the bundled script's gates against real git repos.

The golden fixtures describe decision scenarios (clean change, behind main,
planted secret, oversized PR); these tests build each scenario as an actual
git repository with a local bare ``origin`` and assert the gate verdicts the
script produces. No network, no GitHub — gates B/C/E and the confidence
mapping are pure git + filesystem, which is exactly what makes this cheap.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parent.parent / "create_pr.py"
spec = importlib.util.spec_from_file_location("create_pr_integration", SCRIPT_PATH)
create_pr = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = create_pr
spec.loader.exec_module(create_pr)

GIT_ID = ["-c", "user.name=itest", "-c", "user.email=itest@example.com"]


def git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *GIT_ID, *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout


def make_args(**overrides) -> Namespace:
    base = {
        "repo": ".",
        "config": "",
        "no_config": True,
        "base": "",
        "head": "",
        "title": None,
        "issue": None,
        "reviewers": None,
        "labels": None,
        "create_pr": False,
        "dry_run": True,
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


def build_repo(tmp: Path) -> Path:
    """Work repo on branch ``main`` with one commit, pushed to a local bare origin."""
    remote = tmp / "remote.git"
    work = tmp / "work"
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
    git(work, "add", "-A")
    git(work, "commit", "-m", "chore: initial commit")
    git(work, "remote", "add", "origin", str(remote))
    git(work, "push", "-u", "origin", "main")
    return work


def gate_env(repo: Path, branch: str):
    settings = create_pr.resolve_settings(make_args(), repo, branch)
    ctx = create_pr.Context(repo=repo, base=settings.base, branch=branch)
    return ctx, settings


class GateIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = build_repo(Path(self._tmp.name))

    def commit_on_feature(self, branch: str, filename: str, content: str, msg: str) -> None:
        git(self.repo, "checkout", "-b", branch)
        (self.repo / filename).write_text(content)
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-m", msg)

    # --- golden 001: clean small change → all gates pass, confidence confirmed ---

    def test_clean_small_change_is_confirmed(self) -> None:
        self.commit_on_feature(
            "feature/add-helper", "helper.go",
            'package main\n\nfunc Helper() string {\n\treturn "ok"\n}\n',
            "feat: add helper",
        )
        ctx, settings = gate_env(self.repo, "feature/add-helper")

        b = create_pr.gate_b_branch_sync(ctx, settings)
        self.assertEqual(create_pr.PASS, b.status, b.evidence)
        c = create_pr.gate_c_change_risk(ctx, settings)
        self.assertEqual(create_pr.PASS, c.status, c.evidence)
        self.assertFalse(any("size:" in d for d in c.details), "small change must not warn on size")
        e = create_pr.gate_e_security(ctx, settings)
        self.assertEqual(create_pr.PASS, e.status, e.evidence)

        self.assertEqual("confirmed", create_pr.determine_confidence([b, c, e]))

    # --- golden 003: branch behind main → Gate B blocker ---

    def test_behind_main_is_blocker(self) -> None:
        self.commit_on_feature(
            "feature/stale-branch", "feature.go",
            "package main\n\nfunc Feature() {}\n",
            "feat: add feature",
        )
        # Advance main past the branch point and publish it.
        git(self.repo, "checkout", "main")
        (self.repo / "hotfix.go").write_text("package main\n\nfunc Hotfix() {}\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-m", "fix: hotfix on main")
        git(self.repo, "push", "origin", "main")
        git(self.repo, "checkout", "feature/stale-branch")

        ctx, settings = gate_env(self.repo, "feature/stale-branch")
        b = create_pr.gate_b_branch_sync(ctx, settings)
        self.assertEqual(create_pr.FAIL, b.status)
        self.assertIn("behind", b.evidence)
        self.assertEqual("suspected", create_pr.determine_confidence([b]))

    # --- golden 009: planted secret in an added line → Gate E blocker ---

    def test_planted_secret_fails_gate_e(self) -> None:
        self.commit_on_feature(
            "feature/leaky-config", "config.go",
            'package main\n\nvar password = "prod-credential-9981-zzz"\n',
            "feat: add config",
        )
        ctx, settings = gate_env(self.repo, "feature/leaky-config")
        e = create_pr.gate_e_security(ctx, settings)
        self.assertEqual(create_pr.FAIL, e.status)
        self.assertIn("secret scan matched", e.evidence)
        self.assertTrue(any("config.go" in d for d in e.details))
        self.assertEqual("suspected", create_pr.determine_confidence([e]))

    def test_env_reference_is_not_flagged(self) -> None:
        self.commit_on_feature(
            "feature/env-config", "config.go",
            'package main\n\nimport "os"\n\nvar token = os.Getenv("API_TOKEN")\n',
            "feat: read token from env",
        )
        ctx, settings = gate_env(self.repo, "feature/env-config")
        e = create_pr.gate_e_security(ctx, settings)
        self.assertEqual(create_pr.PASS, e.status, e.evidence)

    # --- golden 005: oversized PR → Gate C size warning ---

    def test_oversized_change_warns(self) -> None:
        lines = "\n".join(f"// filler line {i}" for i in range(900))
        self.commit_on_feature(
            "feature/huge-drop", "generated.go",
            f"package main\n\n{lines}\n",
            "feat: add generated table",
        )
        ctx, settings = gate_env(self.repo, "feature/huge-drop")
        c = create_pr.gate_c_change_risk(ctx, settings)
        self.assertEqual(create_pr.PASS, c.status)
        self.assertTrue(
            any("very large" in d for d in c.details),
            f"expected strong size warning in details: {c.details}",
        )

    # --- conflict markers committed to the branch → Gate B blocker ---

    def test_conflict_marker_blocks(self) -> None:
        self.commit_on_feature(
            "fix/bad-merge", "merge.go",
            "package main\n\n<<<<<<< HEAD\nfunc A() {}\n=======\nfunc B() {}\n>>>>>>> other\n",
            "fix: resolve merge",
        )
        ctx, settings = gate_env(self.repo, "fix/bad-merge")
        b = create_pr.gate_b_branch_sync(ctx, settings)
        self.assertEqual(create_pr.FAIL, b.status)
        self.assertIn("conflict markers", b.evidence)


if __name__ == "__main__":
    unittest.main()