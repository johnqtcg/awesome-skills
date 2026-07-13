"""Behavioral integration tests for the git-commit skill.

Runs the skill's real artifacts against temporary git repositories:
  - the §1 Preflight bash block (still inline in SKILL.md), extracted and executed;
  - scripts/secret-scan.sh;
  - scripts/stash-guard.sh, including the failure paths a commit skill must survive
    (gate FAILS, interrupt) — the changes must still be restored.

Skipped when git is not installed.
"""

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[2]
SKILL_MD = SKILL_DIR / "SKILL.md"
SCRIPTS = SKILL_DIR / "scripts"
GIT = shutil.which("git")


def _bash_blocks() -> list[str]:
    return re.findall(r"```bash\n(.*?)```", SKILL_MD.read_text(encoding="utf-8"), re.DOTALL)


def _block_with(*needles: str) -> str | None:
    for block in _bash_blocks():
        if all(n in block for n in needles):
            return block
    return None


PREFLIGHT = _block_with("is-inside-work-tree", "IN_PROGRESS")

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


class _RepoTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = Path(self._tmp.name)
        self.git("init", "-q")
        (self.repo / "file.txt").write_text("base\n")
        self.git("add", "file.txt")
        self.git("commit", "-qm", "chore: init")
        self.default_branch = self.git("symbolic-ref", "--short", "HEAD").stdout.strip()

    def git(self, *args):
        return subprocess.run([GIT, *args], cwd=self.repo, env=_env(),
                              capture_output=True, text=True)

    def bash(self, script, extra_env=None):
        return subprocess.run(["bash", "-c", script], cwd=self.repo, env=_env(extra_env),
                              capture_output=True, text=True, timeout=60)

    def script(self, name, *args, extra_env=None):
        return subprocess.run(["bash", str(SCRIPTS / name), *args], cwd=self.repo,
                              env=_env(extra_env), capture_output=True, text=True, timeout=60)


@unittest.skipUnless(GIT and PREFLIGHT, "git or preflight block unavailable")
class PreflightTests(_RepoTestCase):
    def test_clean_repo_reports_no_blocker(self):
        out = self.bash(PREFLIGHT)
        self.assertIn("true", out.stdout)
        self.assertNotIn("IN_PROGRESS", out.stdout)
        self.assertNotIn("file.txt", out.stdout)

    def test_detects_merge_in_progress_and_conflict(self):
        self.git("checkout", "-qb", "feature")
        (self.repo / "file.txt").write_text("feature\n")
        self.git("commit", "-qam", "feat: feature side")
        self.git("checkout", "-q", self.default_branch)
        (self.repo / "file.txt").write_text("mainline\n")
        self.git("commit", "-qam", "fix: main side")
        self.assertNotEqual(0, self.git("merge", "feature").returncode)
        out = self.bash(PREFLIGHT)
        self.assertIn("IN_PROGRESS MERGE_HEAD", out.stdout)
        self.assertIn("file.txt", out.stdout)

    def test_detects_rebase_in_progress_worktree_safe(self):
        (self.repo / ".git" / "rebase-merge").mkdir()
        self.assertIn("IN_PROGRESS rebase-merge", self.bash(PREFLIGHT).stdout)

    def test_allows_detached_head(self):
        head = self.git("rev-parse", "HEAD").stdout.strip()
        self.git("checkout", "-q", head)
        self.assertNotIn("IN_PROGRESS", self.bash(PREFLIGHT).stdout)


@unittest.skipUnless(GIT, "git not installed")
class SecretScanScriptTests(_RepoTestCase):
    def test_clean_stage_exits_zero_no_findings(self):
        (self.repo / "hello.txt").write_text("nothing secret here\n")
        self.git("add", "hello.txt")
        out = self.script("secret-scan.sh")
        self.assertEqual(0, out.returncode, "clean scan must exit 0, not the grep no-match 1")
        self.assertNotIn("SECRET_CANDIDATE", out.stdout)

    def test_flags_added_sk_proj_key(self):
        (self.repo / "config.py").write_text('API_KEY = "sk-proj-abcdEFGH1234ijklMNOP5678qrstUVWX"\n')
        self.git("add", "config.py")
        out = self.script("secret-scan.sh")
        self.assertEqual(0, out.returncode)
        self.assertIn("SECRET_CANDIDATE", out.stdout)
        self.assertIn("sk-proj-", out.stdout)

    def test_ignores_removed_secret(self):
        (self.repo / "secrets.txt").write_text("KEY = AKIAIOSFODNN7EXAMPLE\n")
        self.git("add", "secrets.txt")
        self.git("commit", "-qm", "chore: pre-existing secret")
        (self.repo / "secrets.txt").write_text("KEY = removed\n")
        self.git("add", "secrets.txt")
        out = self.script("secret-scan.sh")
        self.assertEqual(0, out.returncode)
        self.assertNotIn("AKIA", out.stdout, "removing a secret must not be flagged")


@unittest.skipUnless(GIT, "git not installed")
class StashGuardTests(_RepoTestCase):
    def _dirty(self):
        """staged + unstaged edit of the same file, plus an untracked file."""
        (self.repo / "file.txt").write_text("staged\n")
        self.git("add", "file.txt")
        (self.repo / "file.txt").write_text("unstaged\n")
        (self.repo / "untracked.txt").write_text("untracked\n")

    def _assert_restored(self):
        self.assertEqual("unstaged\n", (self.repo / "file.txt").read_text())
        self.assertTrue((self.repo / "untracked.txt").exists())
        self.assertEqual("staged\n", self.git("show", ":file.txt").stdout)  # index preserved

    def test_restores_after_successful_gate(self):
        self._dirty()
        out = self.script("stash-guard.sh", "true")
        self.assertEqual(0, out.returncode, out.stderr)
        self._assert_restored()

    def test_restores_even_when_gate_fails(self):
        # THE key transactional guarantee: gate failure must NOT strand changes in the stash.
        self._dirty()
        out = self.script("stash-guard.sh", "sh", "-c", "exit 3")
        self.assertEqual(3, out.returncode, "gate's exit code must propagate")
        self._assert_restored()

    def test_gate_sees_staged_only_snapshot(self):
        self._dirty()
        snap = self.repo / "snap.out"
        out = self.script(
            "stash-guard.sh", "sh", "-c",
            'cat file.txt > "$SNAP"; '
            '{ ls untracked.txt >/dev/null 2>&1 && echo PRESENT || echo ABSENT; } >> "$SNAP"',
            extra_env={"SNAP": str(snap)},
        )
        self.assertEqual(0, out.returncode, out.stderr)
        view = snap.read_text()
        self.assertIn("staged", view)          # gate saw staged content
        self.assertNotIn("unstaged", view)     # not the unstaged edit
        self.assertIn("ABSENT", view)          # untracked hidden during gate
        self._assert_restored()

    def test_no_dirty_state_runs_gate_without_stashing(self):
        out = self.script("stash-guard.sh", "true")
        self.assertEqual(0, out.returncode, out.stderr)
        self.assertEqual("", self.git("stash", "list").stdout, "must not leave a stray stash")


if __name__ == "__main__":
    unittest.main()