"""Behavioral integration tests for the git-commit skill.

Unlike the contract/golden tests (which check structure and re-implement
algorithms), these tests EXTRACT the actual bash blocks from SKILL.md and run
them against real temporary git repositories, proving the preflight, secret-scan
and stash logic behave correctly in the states the skill claims to handle.

Skipped when git is not installed.
"""

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SKILL_MD = Path(__file__).resolve().parents[2] / "SKILL.md"
GIT = shutil.which("git")


def _bash_blocks() -> list[str]:
    return re.findall(r"```bash\n(.*?)```", SKILL_MD.read_text(encoding="utf-8"), re.DOTALL)


def _block_with(*needles: str) -> str | None:
    for block in _bash_blocks():
        if all(n in block for n in needles):
            return block
    return None


PREFLIGHT = _block_with("is-inside-work-tree", "IN_PROGRESS")
SECRET_SCAN = _block_with("SECRET_PATTERNS")
# The fallback regex scan only (independent of whether gitleaks is installed).
SECRET_FALLBACK = (
    SECRET_SCAN[SECRET_SCAN.index("if command -v rg"):] if SECRET_SCAN else None
)
STASH = _block_with("git stash push --keep-index")

_ISOLATED_ENV = {
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@t",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@t",
}


def _env(extra=None):
    env = {**os.environ, **_ISOLATED_ENV}
    if extra:
        env.update(extra)
    return env


def _git(cwd, *args):
    return subprocess.run([GIT, *args], cwd=cwd, env=_env(), capture_output=True, text=True)


def _bash(script, cwd, extra_env=None):
    return subprocess.run(
        ["bash", "-c", script], cwd=cwd, env=_env(extra_env),
        capture_output=True, text=True, timeout=60,
    )


@unittest.skipUnless(GIT, "git not installed")
@unittest.skipUnless(PREFLIGHT and SECRET_FALLBACK and STASH,
                     "expected bash blocks not found in SKILL.md")
class GitCommitIntegrationTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        _git(self.repo, "init", "-q")
        (self.repo / "file.txt").write_text("base\n")
        _git(self.repo, "add", "file.txt")
        _git(self.repo, "commit", "-qm", "chore: init")
        self.default_branch = _git(self.repo, "symbolic-ref", "--short", "HEAD").stdout.strip()

    def tearDown(self):
        self._tmp.cleanup()

    # ---- Preflight ----

    def test_preflight_clean_repo_reports_no_blocker(self):
        out = _bash(PREFLIGHT, self.repo)
        self.assertIn("true", out.stdout)          # is-inside-work-tree
        self.assertNotIn("IN_PROGRESS", out.stdout)  # no rebase/merge/etc in progress
        self.assertNotIn("file.txt", out.stdout)     # no conflicted paths

    def test_preflight_detects_merge_in_progress_and_conflict(self):
        _git(self.repo, "checkout", "-qb", "feature")
        (self.repo / "file.txt").write_text("feature\n")
        _git(self.repo, "commit", "-qam", "feat: feature side")
        _git(self.repo, "checkout", "-q", self.default_branch)
        (self.repo / "file.txt").write_text("mainline\n")
        _git(self.repo, "commit", "-qam", "fix: main side")
        merge = _git(self.repo, "merge", "feature")
        self.assertNotEqual(0, merge.returncode, "merge should conflict")
        out = _bash(PREFLIGHT, self.repo)
        self.assertIn("IN_PROGRESS MERGE_HEAD", out.stdout)
        self.assertIn("file.txt", out.stdout)  # conflict diff surfaced the path

    def test_preflight_detects_rebase_in_progress_worktree_safe(self):
        # Simulate a rebase state dir; the skill must find it via --git-path.
        (self.repo / ".git" / "rebase-merge").mkdir()
        out = _bash(PREFLIGHT, self.repo)
        self.assertIn("IN_PROGRESS rebase-merge", out.stdout)

    def test_preflight_allows_detached_head(self):
        head = _git(self.repo, "rev-parse", "HEAD").stdout.strip()
        _git(self.repo, "checkout", "-q", head)  # detached
        out = _bash(PREFLIGHT, self.repo)
        self.assertNotIn("IN_PROGRESS", out.stdout)  # detached HEAD is not a blocker

    # ---- Secret scan (fallback regex layer) ----

    def test_secret_scan_flags_added_sk_proj_key(self):
        (self.repo / "config.py").write_text(
            'API_KEY = "sk-proj-abcdEFGH1234ijklMNOP5678qrstUVWX"\n'
        )
        _git(self.repo, "add", "config.py")
        out = _bash(SECRET_FALLBACK, self.repo)
        self.assertIn("sk-proj-", out.stdout,
                      "modern sk-proj- key must be flagged (regex allows internal hyphens)")

    def test_secret_scan_ignores_removed_secret(self):
        (self.repo / "secrets.txt").write_text("KEY = AKIAIOSFODNN7EXAMPLE\n")
        _git(self.repo, "add", "secrets.txt")
        _git(self.repo, "commit", "-qm", "chore: add (pre-existing) secret")
        (self.repo / "secrets.txt").write_text("KEY = removed\n")
        _git(self.repo, "add", "secrets.txt")
        out = _bash(SECRET_FALLBACK, self.repo)
        self.assertNotIn("AKIA", out.stdout,
                         "removing a leaked secret must not be blocked (added-lines-only scan)")

    # ---- Stash isolation + round-trip ----

    def test_stash_isolates_gate_and_restores_worktree(self):
        # staged modification + unstaged modification (same file) + untracked file
        (self.repo / "file.txt").write_text("staged\n")
        _git(self.repo, "add", "file.txt")
        (self.repo / "file.txt").write_text("unstaged\n")
        (self.repo / "untracked.txt").write_text("untracked\n")

        snap = self.repo / "snapshot.out"
        probed = STASH.replace(
            "# ... run quality gate against the staged-only tree ...",
            'cat file.txt > "$SNAP"; '
            '(ls untracked.txt >/dev/null 2>&1 && echo UNTRACKED_PRESENT || echo UNTRACKED_ABSENT) >> "$SNAP"',
        )
        self.assertIn("$SNAP", probed, "probe injection point must exist in the stash block")
        result = _bash(probed, self.repo, extra_env={"SNAP": str(snap)})
        self.assertEqual(0, result.returncode, result.stderr)

        gate_view = snap.read_text()
        self.assertIn("staged", gate_view, "gate must see the STAGED content")
        self.assertNotIn("unstaged", gate_view, "gate must not see the unstaged change")
        self.assertIn("UNTRACKED_ABSENT", gate_view, "gate must not see untracked files")

        # after restore: unstaged change and untracked file are back (no data loss)
        self.assertEqual("unstaged\n", (self.repo / "file.txt").read_text())
        self.assertTrue((self.repo / "untracked.txt").exists())


if __name__ == "__main__":
    unittest.main()