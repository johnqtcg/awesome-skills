"""Behavioral integration tests for the git-commit skill.

Runs the skill's real artifacts against temporary git repositories:
  - the §1 Preflight bash block (still inline in SKILL.md), extracted and executed;
  - scripts/secret-scan.sh — redaction, real file:line, context, committed
    allowlist, and gitleaks-failure surfacing;
  - scripts/stash-guard.sh — including the failure paths a commit skill must
    survive: gate failure, SIGINT/SIGTERM, restore conflict, foreign stash on top;
  - scripts/detect-ecosystems.sh — multi-ecosystem and marker-only stages;
  - scripts/run-gate.sh — timeout resolution, reporting, and enforcement;
  - the §6 commit block end-to-end (subject guard really blocks, commit really lands).

Skipped when git is not installed.
"""

import os
import re
import shutil
import signal
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[2]
SKILL_MD = SKILL_DIR / "SKILL.md"
SCRIPTS = SKILL_DIR / "scripts"
GIT = shutil.which("git")

FAKE_KEY = "sk-proj-abcdEFGH1234ijklMNOP5678qrstUVWX"


def _bash_blocks() -> list[str]:
    return re.findall(r"```bash\n(.*?)```", SKILL_MD.read_text(encoding="utf-8"), re.DOTALL)


def _block_with(*needles: str) -> str | None:
    for block in _bash_blocks():
        if all(n in block for n in needles):
            return block
    return None


PREFLIGHT = _block_with("is-inside-work-tree", "IN_PROGRESS")
COMMIT_BLOCK = _block_with("SUBJECT_MAX", "git commit -m")
MULTILINE_BLOCK = _block_with("SUBJECT_MAX", "git commit -F -")

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

    def test_redacts_secret_with_real_file_line_and_context(self):
        (self.repo / "config.py").write_text(
            "a = 1\nb = 2\nc = 3\n"
            f'API_KEY = "{FAKE_KEY}"\n'
            "d = 5\n"
        )
        self.git("add", "config.py")
        out = self.script("secret-scan.sh")
        self.assertEqual(0, out.returncode)
        # Real source line number, not the filtered diff stream's line number.
        self.assertIn("SECRET_CANDIDATE: config.py:4:", out.stdout)
        self.assertIn("[REDACTED]", out.stdout)
        self.assertNotIn(FAKE_KEY, out.stdout + out.stderr,
                         "the secret value must never be printed")
        for n in (2, 3, 5):
            self.assertIn(f"CONTEXT: config.py:{n}:", out.stdout)
        self.assertNotIn("CONTEXT: config.py:4:", out.stdout)

    def test_context_masks_key_body_lines(self):
        # The PEM body next to a BEGIN header must not leak through CONTEXT lines.
        body = "MIIEpAIBAAKCAQEAxyzxyzxyzxyzxyzxyzxyzxyzxyzxyz"
        (self.repo / "deploy.txt").write_text(
            "-----BEGIN RSA PRIVATE KEY-----\n" + body + "\nsafe trailing line\n"
        )
        self.git("add", "deploy.txt")
        out = self.script("secret-scan.sh")
        self.assertIn("SECRET_CANDIDATE: deploy.txt:1:", out.stdout)
        self.assertNotIn(body, out.stdout, "key body must be masked in context output")

    def test_ignores_removed_secret(self):
        (self.repo / "secrets.txt").write_text("KEY = AKIAIOSFODNN7EXAMPLE\n")
        self.git("add", "secrets.txt")
        self.git("commit", "-qm", "chore: pre-existing secret")
        (self.repo / "secrets.txt").write_text("KEY = removed\n")
        self.git("add", "secrets.txt")
        out = self.script("secret-scan.sh")
        self.assertEqual(0, out.returncode)
        self.assertNotIn("AKIA", out.stdout, "removing a secret must not be flagged")

    def _with_gitleaks_shim(self, body):
        """Install a fake gitleaks on PATH; returns the extra_env to use."""
        shim = self.repo / "shim"
        shim.mkdir(exist_ok=True)
        fake = shim / "gitleaks"
        fake.write_text(f"#!/bin/sh\n{body}\n")
        fake.chmod(0o755)
        return {"PATH": f"{shim}{os.pathsep}{os.environ.get('PATH', '')}"}

    def test_gitleaks_failure_surfaces_scanner_error_and_exits_2(self):
        env = self._with_gitleaks_shim("echo 'FTL failed to load config' >&2\nexit 3")
        (self.repo / "config.py").write_text(f'API_KEY = "{FAKE_KEY}"\n')
        self.git("add", "config.py")
        out = self.script("secret-scan.sh", extra_env=env)
        self.assertEqual(2, out.returncode,
                         "a broken scanner must fail closed in the exit code")
        self.assertIn("SCANNER_ERROR", out.stdout, "gitleaks stderr must not be swallowed")
        self.assertIn("failed to load config", out.stdout)
        self.assertIn("SECRET_CANDIDATE", out.stdout,
                      "regex fallback must still run when gitleaks breaks")

    def test_gitleaks_exit_1_is_error_not_findings(self):
        # With findings pinned to --exit-code 10, exit 1 is unambiguously an
        # execution error — even without FTL/ERR markers in stderr. This was
        # the old fail-open path: error text without those markers passed as clean.
        env = self._with_gitleaks_shim("echo 'something went wrong' >&2\nexit 1")
        (self.repo / "clean.txt").write_text("nothing here\n")
        self.git("add", "clean.txt")
        out = self.script("secret-scan.sh", extra_env=env)
        self.assertEqual(2, out.returncode)
        self.assertIn("SCANNER_ERROR: gitleaks exited 1", out.stdout)
        self.assertIn("something went wrong", out.stdout)

    def test_gitleaks_exit_10_is_findings_not_error(self):
        env = self._with_gitleaks_shim("echo 'Finding: REDACTED'\nexit 10")
        (self.repo / "clean.txt").write_text("nothing here\n")
        self.git("add", "clean.txt")
        out = self.script("secret-scan.sh", extra_env=env)
        self.assertEqual(0, out.returncode, "findings are a completed scan, not a failure")
        self.assertIn("Finding: REDACTED", out.stdout)
        self.assertNotIn("SCANNER_ERROR", out.stdout)

    def test_committed_allowlist_marks_findings(self):
        (self.repo / ".commit-secret-allowlist").write_text("tests/*\n")
        self.git("add", ".commit-secret-allowlist")
        self.git("commit", "-qm", "chore: add allowlist")
        (self.repo / "tests").mkdir()
        (self.repo / "tests" / "fixture.py").write_text(f'KEY = "{FAKE_KEY}"\n')
        self.git("add", "tests/fixture.py")
        out = self.script("secret-scan.sh")
        self.assertIn("ALLOWLISTED: tests/fixture.py:1:", out.stdout)
        self.assertNotIn("SECRET_CANDIDATE", out.stdout)
        self.assertNotIn(FAKE_KEY, out.stdout, "allowlisted findings stay redacted")

    def test_staged_uncommitted_allowlist_is_ignored(self):
        # An allowlist introduced by the very commit under scan must not
        # self-authorize it — only the HEAD version counts.
        (self.repo / ".commit-secret-allowlist").write_text("*\n")
        self.git("add", ".commit-secret-allowlist")
        (self.repo / "config.py").write_text(f'KEY = "{FAKE_KEY}"\n')
        self.git("add", "config.py")
        out = self.script("secret-scan.sh")
        self.assertIn("SECRET_CANDIDATE: config.py:1:", out.stdout)
        self.assertNotIn("ALLOWLISTED", out.stdout)


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

    def _signal_test(self, sig, expected_rc):
        self._dirty()
        marker = self.repo / "gate-started"
        proc = subprocess.Popen(
            ["bash", str(SCRIPTS / "stash-guard.sh"), "sh", "-c",
             f'touch "{marker}" && sleep 30'],
            cwd=self.repo, env=_env(), stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, start_new_session=True,
        )
        try:
            deadline = time.monotonic() + 20
            while not marker.exists():
                if time.monotonic() > deadline:
                    self.fail("gate never started")
                time.sleep(0.05)
            os.killpg(os.getpgid(proc.pid), sig)
            rc = proc.wait(timeout=30)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=10)
        self.assertEqual(expected_rc, rc, "an interrupt must never be reported as success")
        self._assert_restored()
        self.assertEqual("", self.git("stash", "list").stdout,
                         "restore must run exactly once and leave no stash behind")

    def test_sigint_restores_and_exits_130(self):
        self._signal_test(signal.SIGINT, 130)

    def test_sigterm_restores_and_exits_143(self):
        self._signal_test(signal.SIGTERM, 143)

    def test_restore_conflict_preserves_stash_and_fails(self):
        # The gate recreates a file that was stashed as untracked → pop conflicts.
        self._dirty()
        out = self.script("stash-guard.sh", "sh", "-c", "echo gate-made > untracked.txt")
        self.assertNotEqual(0, out.returncode,
                            "a gate 'pass' with a failed restore must not exit 0")
        self.assertIn("CONFLICT", out.stderr)
        self.assertIn("git stash apply --index", out.stderr)
        self.assertIn("pre-commit gate", self.git("stash", "list").stdout,
                      "the user's changes must be preserved in the stash")

    def test_foreign_stash_on_top_aborts_safely(self):
        # Someone (here: the gate itself) pushes another stash while the gate runs.
        self._dirty()
        gate = "echo x > extra.txt && git stash push -q --include-untracked -m interloper -- extra.txt"
        out = self.script("stash-guard.sh", "sh", "-c", gate)
        self.assertNotEqual(0, out.returncode)
        self.assertIn("no longer on top", out.stderr)
        stashes = self.git("stash", "list").stdout
        self.assertIn("interloper", stashes)
        self.assertIn("pre-commit gate", stashes, "our stash must be preserved, not popped blindly")

    def _add_dirty_submodule(self):
        """Commit a submodule, then dirty its content — unstashable state."""
        sub_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(sub_tmp.cleanup)
        subsrc = Path(sub_tmp.name)
        for args in (("init", "-q"), ("add", "s.txt"), ("commit", "-qm", "sub")):
            if args[0] == "add":
                (subsrc / "s.txt").write_text("x\n")
            subprocess.run([GIT, *args], cwd=subsrc, env=_env(),
                           capture_output=True, text=True)
        self.git("-c", "protocol.file.allow=always", "submodule", "add", str(subsrc), "sub")
        self.git("commit", "-qm", "chore: add submodule")
        (self.repo / "sub" / "s.txt").write_text("dirt\n")

    def test_preexisting_stash_never_adopted_and_gate_refused(self):
        # P0 regression: `git stash push` exits 0 WITHOUT creating an entry when
        # the only dirt lives inside a submodule. Adopting stash@{0} blindly
        # popped the user's own pre-existing stash; and because that state is
        # unstashable, the gate must NOT run either (fail-closed, exit 2) —
        # it would see a tree that is not the staged snapshot.
        (self.repo / "file.txt").write_text("stashme\n")
        self.git("stash", "push", "-qm", "PREEXISTING")
        self._add_dirty_submodule()
        self.assertNotEqual(0, self.git("diff", "--quiet").returncode,
                            "precondition: the tree must look dirty (CHANGED=1)")
        marker = self.repo / "gate-ran"
        out = self.script("stash-guard.sh", "sh", "-c", f'touch "{marker}"')
        self.assertEqual(2, out.returncode, out.stderr)
        self.assertIn("cannot isolate", out.stderr)
        self.assertFalse(marker.exists(), "the gate must not run against a mixed tree")
        stashes = self.git("stash", "list").stdout
        self.assertIn("PREEXISTING", stashes, "the user's stash must never be adopted or popped")
        self.assertNotIn("pre-commit gate", stashes)
        self.assertEqual("base\n", (self.repo / "file.txt").read_text(),
                         "the pre-existing stash content must not be applied to the worktree")

    def test_partial_isolation_restores_stash_and_refuses_gate(self):
        # Stashable dirt AND submodule dirt: the push creates an entry but
        # residue survives — the guard must put the stashed part back, refuse
        # the gate, and exit 2.
        self._add_dirty_submodule()
        self._dirty()
        marker = self.repo / "gate-ran"
        out = self.script("stash-guard.sh", "sh", "-c", f'touch "{marker}"')
        self.assertEqual(2, out.returncode, out.stderr)
        self.assertIn("cannot isolate", out.stderr)
        self.assertFalse(marker.exists(), "the gate must not run against a mixed tree")
        self._assert_restored()
        self.assertEqual("", self.git("stash", "list").stdout)
        self.assertEqual("dirt\n", (self.repo / "sub" / "s.txt").read_text())

    def test_gate_side_effects_refuse_destructive_reset(self):
        # A tracked file changed while the gate ran (formatter, `go mod tidy`,
        # or a concurrent IDE edit). Those edits are NOT in the stash — a blind
        # `reset --hard` would destroy them silently.
        self._dirty()
        out = self.script("stash-guard.sh", "sh", "-c", "echo gatedrift > file.txt")
        self.assertNotEqual(0, out.returncode,
                            "a gate pass with an unrestorable tree must not exit 0")
        self.assertIn("changed while the gate ran", out.stderr)
        self.assertIn("git stash apply --index", out.stderr)
        self.assertEqual("gatedrift\n", (self.repo / "file.txt").read_text(),
                         "the mid-gate edit must not be destroyed by reset --hard")
        self.assertIn("pre-commit gate", self.git("stash", "list").stdout,
                      "the pre-gate changes stay safe in the stash")


@unittest.skipUnless(GIT, "git not installed")
class DetectEcosystemsTests(_RepoTestCase):
    def _stage(self, *names):
        for name in names:
            path = self.repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("x\n")
            self.git("add", name)

    def _detected(self):
        out = self.script("detect-ecosystems.sh")
        self.assertEqual(0, out.returncode, out.stderr)
        return out.stdout.split()

    def test_minority_ecosystem_is_never_dropped(self):
        self._stage("a.go", "b.go", "c.go", "d.go", "e.go", "web/app.ts")
        self.assertEqual(["go", "node"], self._detected(),
                         "5 Go + 1 TS must yield BOTH gates, majority first")

    def test_marker_only_go_mod(self):
        self._stage("go.mod")
        self.assertEqual(["go"], self._detected())

    def test_marker_only_package_json(self):
        self._stage("package.json")
        self.assertEqual(["node"], self._detected())

    def test_marker_only_cargo_pyproject_pom(self):
        self._stage("Cargo.toml", "pyproject.toml", "backend/pom.xml")
        self.assertEqual({"rust", "python", "java"}, set(self._detected()))

    def test_extended_markers_go_work_uv_bun_gradle(self):
        self._stage("go.work", "uv.lock", "bun.lockb", "gradle.properties")
        self.assertEqual({"go", "python", "node", "java"}, set(self._detected()))

    def test_frontend_component_extensions(self):
        self._stage("App.vue", "Widget.svelte", "util.mts")
        self.assertEqual(["node"], self._detected())

    def test_no_ecosystem_detected_outputs_nothing(self):
        self._stage("README.md")
        self.assertEqual([], self._detected())


@unittest.skipUnless(GIT, "git not installed")
class RunGateTests(_RepoTestCase):
    # Empty string counts as unset for ${VAR:-...}, shielding from ambient env.
    CLEAR = {
        "QUALITY_GATE_TIMEOUT_SECONDS": "",
        "SKILL_QUALITY_GATE_TIMEOUT_SECONDS": "",
        "COMMIT_TEST_TIMEOUT": "",
    }

    def test_reports_default_timeout_and_passes_exit_code_through(self):
        out = self.script("run-gate.sh", "sh", "-c", "exit 3", extra_env=self.CLEAR)
        self.assertEqual(3, out.returncode, "gate exit code must propagate")
        self.assertIn("GATE_TIMEOUT: 120s", out.stderr)

    def test_env_override_wins_over_lower_priority_env(self):
        out = self.script(
            "run-gate.sh", "true",
            extra_env={**self.CLEAR,
                       "QUALITY_GATE_TIMEOUT_SECONDS": "600",
                       "COMMIT_TEST_TIMEOUT": "50"},
        )
        self.assertEqual(0, out.returncode)
        self.assertIn("GATE_TIMEOUT: 600s", out.stderr)

    def test_repo_wrapper_flag_beats_env(self):
        out = self.script(
            "run-gate.sh", "-t", "900", "true",
            extra_env={**self.CLEAR, "QUALITY_GATE_TIMEOUT_SECONDS": "600"},
        )
        self.assertEqual(0, out.returncode)
        self.assertIn("GATE_TIMEOUT: 900s", out.stderr)

    def test_invalid_timeout_is_rejected(self):
        out = self.script("run-gate.sh", "-t", "12x", "true", extra_env=self.CLEAR)
        self.assertEqual(2, out.returncode)
        self.assertIn("invalid timeout", out.stderr)

    def test_zero_timeout_is_rejected(self):
        # timeout(1) and alarm() treat 0 as "no timeout" — accepting it would
        # silently disable enforcement.
        out = self.script("run-gate.sh", "-t", "0", "true", extra_env=self.CLEAR)
        self.assertEqual(2, out.returncode)
        self.assertIn("invalid timeout", out.stderr)

    def test_kills_overrunning_gate_with_124(self):
        # All branches (timeout/gtimeout/perl watcher) report 124 on expiry.
        start = time.monotonic()
        out = self.script("run-gate.sh", "-t", "1", "sleep", "30", extra_env=self.CLEAR)
        self.assertEqual(124, out.returncode,
                         "timeout must kill the gate and surface uniformly as 124")
        self.assertLess(time.monotonic() - start, 15, "enforcement must actually kill the gate")

    def test_timeout_kills_whole_process_tree(self):
        # A gate that backgrounds work (test runners, daemonized helpers) must
        # not leak grandchildren past the timeout.
        pidfile = self.repo / "child.pid"
        out = self.script("run-gate.sh", "-t", "1", "sh", "-c",
                          f'sleep 30 & echo $! > "{pidfile}"; wait',
                          extra_env=self.CLEAR)
        self.assertEqual(124, out.returncode)
        pid = int(pidfile.read_text().strip())
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
            time.sleep(0.1)
        else:
            os.kill(pid, signal.SIGKILL)
            self.fail("backgrounded grandchild survived the timeout")

    def test_composes_with_stash_guard(self):
        # Timeout inside the guard: changes still restored, timeout code propagates.
        (self.repo / "file.txt").write_text("unstaged\n")
        out = self.script("stash-guard.sh", "bash", str(SCRIPTS / "run-gate.sh"),
                          "-t", "1", "sleep", "30", extra_env=self.CLEAR)
        self.assertEqual(124, out.returncode)
        self.assertEqual("unstaged\n", (self.repo / "file.txt").read_text())
        self.assertEqual("", self.git("stash", "list").stdout)


@unittest.skipUnless(GIT and COMMIT_BLOCK, "git or §6 commit block unavailable")
class CommitGuardEndToEndTests(_RepoTestCase):
    """Execute the real §6 block with only the SUBJECT placeholder substituted."""

    def _run_commit_block(self, subject):
        block = re.sub(r"^SUBJECT='.*'$", f"SUBJECT='{subject}'",
                       COMMIT_BLOCK, count=1, flags=re.MULTILINE)
        return self.bash(block)

    def _stage_change(self):
        (self.repo / "a.txt").write_text("x\n")
        self.git("add", "a.txt")

    def test_valid_subject_commits_end_to_end(self):
        self._stage_change()
        out = self._run_commit_block("feat(core): add a")
        self.assertEqual(0, out.returncode, out.stdout + out.stderr)
        self.assertEqual("feat(core): add a",
                         self.git("log", "-1", "--format=%s").stdout.strip())

    def test_long_subject_is_blocked_and_nothing_commits(self):
        self._stage_change()
        out = self._run_commit_block("feat: " + "x" * 60)
        self.assertNotEqual(0, out.returncode)
        self.assertIn("subject too long", out.stdout + out.stderr)
        self.assertEqual("chore: init",
                         self.git("log", "-1", "--format=%s").stdout.strip())

    def test_trailing_period_is_blocked(self):
        self._stage_change()
        out = self._run_commit_block("feat(core): add a.")
        self.assertNotEqual(0, out.returncode)
        self.assertIn("must not end with", out.stdout + out.stderr)
        self.assertEqual("chore: init",
                         self.git("log", "-1", "--format=%s").stdout.strip())

    def test_repo_convention_subject_max_is_honored(self):
        # §5 carries the discovered limit into the guard via SUBJECT_MAX.
        self._stage_change()
        subject = "feat: " + "x" * 60  # 66 chars: over 50, under 72
        block = re.sub(r"^SUBJECT='.*'$", f"SUBJECT='{subject}'",
                       COMMIT_BLOCK, count=1, flags=re.MULTILINE)
        out = self.bash(block, extra_env={"SUBJECT_MAX": "72"})
        self.assertEqual(0, out.returncode, out.stdout + out.stderr)
        self.assertEqual(subject, self.git("log", "-1", "--format=%s").stdout.strip())


@unittest.skipUnless(GIT and MULTILINE_BLOCK, "git or §6 multi-line block unavailable")
class MultilineCommitEndToEndTests(_RepoTestCase):
    """The heredoc is the single message source; the guard checks its first line."""

    def _run_multiline_block(self, subject, body="Body line explaining why.",
                             footer="Closes #1"):
        block = (MULTILINE_BLOCK
                 .replace("<type>(<scope>): <subject>", subject)
                 .replace("<body — explain why, wrap at 72 chars>", body)
                 .replace("<footer>", footer))
        return self.bash(block)

    def _stage_change(self):
        (self.repo / "a.txt").write_text("x\n")
        self.git("add", "a.txt")

    def test_valid_multiline_commit_lands_with_body(self):
        self._stage_change()
        out = self._run_multiline_block("fix(auth): serialize token refresh")
        self.assertEqual(0, out.returncode, out.stdout + out.stderr)
        self.assertEqual("fix(auth): serialize token refresh",
                         self.git("log", "-1", "--format=%s").stdout.strip())
        body = self.git("log", "-1", "--format=%b").stdout
        self.assertIn("Body line explaining why.", body)
        self.assertIn("Closes #1", body)

    def test_long_subject_in_heredoc_is_blocked(self):
        # The guard validates the EXACT first line of the heredoc — the agent
        # can no longer validate one subject and commit another.
        self._stage_change()
        out = self._run_multiline_block("feat: " + "x" * 60)
        self.assertNotEqual(0, out.returncode)
        self.assertIn("subject too long", out.stdout + out.stderr)
        self.assertEqual("chore: init",
                         self.git("log", "-1", "--format=%s").stdout.strip())


if __name__ == "__main__":
    unittest.main()