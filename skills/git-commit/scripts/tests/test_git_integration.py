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


def _awk_supports_intervals() -> bool:
    """Twelve credential patterns are length-anchored ({16}, {20,}). An awk
    without interval support matches none of them, so secret-scan.sh refuses to
    run at all — correctly. Tests that need a SUCCESSFUL scan cannot apply there
    and must skip with a reason, or a user on such a host sees a wall of red and
    cannot tell an unsupported awk from a broken skill."""
    try:
        r = subprocess.run(
            ["awk", 'BEGIN { exit !((match("aaaaaaaaaaaaaaaaaaaaaaaaa", /[a-z]{20,}/) == 1) '
                    '&& (match("aaaaaaaaaaaaaaaaaaaaaaaaa", ENVIRON["P"]) == 1)) }'],
            env={**os.environ, "P": "[a-z]{20,}"}, capture_output=True, timeout=30)
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


AWK_INTERVALS = _awk_supports_intervals()
INTERVAL_SKIP = (
    "this host's awk has no regex interval support (Debian 12's default mawk "
    "1.3.4 20200120 is such an awk); secret-scan.sh REFUSES to run there rather "
    "than report a false clean, so scan-success assertions do not apply. The "
    "refusal itself is asserted by AwkCapabilityTests. Install gawk, or a mawk "
    ">= 1.3.4 20240123, to exercise these."
)
needs_intervals = unittest.skipUnless(AWK_INTERVALS, INTERVAL_SKIP)


def _bash_blocks() -> list[str]:
    return re.findall(r"```bash\n(.*?)```", SKILL_MD.read_text(encoding="utf-8"), re.DOTALL)


def _block_with(*needles: str) -> str | None:
    for block in _bash_blocks():
        if all(n in block for n in needles):
            return block
    return None


PREFLIGHT = _block_with("is-inside-work-tree", "IN_PROGRESS")
REPORT_BLOCK = _block_with("rev-parse --short HEAD", "--name-status")
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
@needs_intervals
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
        self.assertEqual(0, self.script("detect-ecosystems.sh").returncode,
                         "'none detected' is a successful answer")

    def test_unreadable_index_is_unknown_not_none(self):
        # Empty stdout is this script's "no ecosystem" signal, so a dead git
        # used to read as "nothing to gate" and skip the quality gate entirely.
        shim_dir = self.repo / ".shim"
        shim_dir.mkdir(exist_ok=True)
        shim = shim_dir / "git"
        shim.write_text("#!/usr/bin/env bash\n"
                        'if [ "$1" = "diff" ]; then exit 128; fi\n'
                        f'exec {GIT} "$@"\n')
        shim.chmod(0o755)
        self._stage("main.go")
        out = self.script("detect-ecosystems.sh",
                          extra_env={"PATH": f"{shim_dir}:{os.environ['PATH']}"})
        self.assertEqual(2, out.returncode, "a failed read must not look like 'none'")
        self.assertEqual("", out.stdout.strip())


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

    def test_kills_overrunning_gate_with_exit_124(self):
        # ONE code on every host. Three implementations disagree natively — GNU
        # gives 124 (or 137 if KILL was needed) and BusyBox gives 143 (or 137),
        # because BusyBox does not implement the 124 convention at all. run-gate
        # normalises, so a caller has one rule to remember.
        start = time.monotonic()
        out = self.script("run-gate.sh", "-t", "1", "sleep", "30", extra_env=self.CLEAR)
        self.assertEqual(124, out.returncode,
                         f"a timeout must surface as 124 on every host; got "
                         f"{out.returncode}\n{out.stderr}")
        self.assertIn("GATE_TIMED_OUT", out.stderr)
        self.assertLess(time.monotonic() - start, 25, "enforcement must actually kill the gate")

    def test_gate_failure_before_the_deadline_is_not_relabelled(self):
        # Normalisation keys on elapsed time, so a gate that dies of a signal
        # early keeps its own code and is not misreported as a timeout.
        out = self.script("run-gate.sh", "-t", "60", "sh", "-c",
                          "kill -TERM $$", extra_env=self.CLEAR)
        self.assertEqual(143, out.returncode,
                         "a signal death well before the deadline is the gate's own")
        self.assertNotIn("GATE_TIMED_OUT", out.stderr)

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


# ---------------------------------------------------------------------------
# Failure paths. Every test below reproduces a defect found in review; each one
# fails against the pre-fix script, so it pins the fix rather than decorating it.
# ---------------------------------------------------------------------------


@unittest.skipUnless(GIT, "git not installed")
class NonAsciiPathTests(_RepoTestCase):
    """`--name-only` is DISPLAY output: with the default core.quotePath a
    non-ASCII path arrives as "\346\272\220…", so the extension parsed as `py"`,
    `*.pem` stopped matching, and a CJK-named source file silently selected no
    gate at all. Every script must read paths raw."""

    def _stage_cjk(self):
        (self.repo / "源码" / "模块").mkdir(parents=True)
        (self.repo / "源码" / "模块" / "配置.py").write_text(
            'k = "AKIAIOSFODNN7EXAMPLE"\nname = "readable"\n')
        (self.repo / "源码" / "私钥.pem").write_text("-----BEGIN RSA PRIVATE KEY-----\n")
        self.git("add", "-A")

    def test_cjk_source_file_selects_its_gate(self):
        self._stage_cjk()
        self.assertEqual(["python"], self.script("detect-ecosystems.sh").stdout.split())

    @needs_intervals
    def test_cjk_sensitive_filename_is_flagged(self):
        self._stage_cjk()
        out = self.script("secret-scan.sh")
        self.assertEqual(0, out.returncode, out.stdout)
        self.assertIn("SENSITIVE_FILE: 源码/私钥.pem", out.stdout,
                      "an escaped path defeats the *.pem suffix match")

    @needs_intervals
    def test_cjk_finding_carries_a_usable_path_and_context(self):
        self._stage_cjk()
        out = self.script("secret-scan.sh").stdout
        self.assertIn("SECRET_CANDIDATE: 源码/模块/配置.py:1", out)
        # Context proves the reported path is one `git show ":<path>"` can open;
        # an escaped path would render "(unavailable)".
        self.assertIn("CONTEXT: 源码/模块/配置.py:2", out)
        self.assertNotIn("unavailable", out)

    def test_cjk_directory_can_bootstrap_a_scope(self):
        self._stage_cjk()
        out = self.script("resolve-scope.sh")
        self.assertEqual(0, out.returncode)
        self.assertIn("SCOPE: 源码", out.stdout)


@unittest.skipUnless(GIT, "git not installed")
class StageFailurePropagationTests(_RepoTestCase):
    """Checking only the git reads was not enough: a broken `awk` still let the
    scan exit 0 having printed nothing, which is the exact shape of a clean
    result. No stage may fail while the run claims to have completed."""

    def _broken_awk(self):
        shim_dir = self.repo / ".awkshim"
        shim_dir.mkdir(exist_ok=True)
        shim = shim_dir / "awk"
        shim.write_text("#!/usr/bin/env bash\necho 'awk: broken' >&2\nexit 2\n")
        shim.chmod(0o755)
        return {"PATH": f"{shim_dir}:{os.environ['PATH']}"}

    def _stage_a_leak(self):
        (self.repo / "leak.py").write_text('AWS_KEY = "AKIAIOSFODNN7EXAMPLE"\n')
        (self.repo / "id.pem").write_text("-----BEGIN RSA PRIVATE KEY-----\n")
        self.git("add", "-A")

    @needs_intervals
    def test_secret_scan_reports_a_broken_classifier(self):
        self._stage_a_leak()
        out = self.script("secret-scan.sh", extra_env=self._broken_awk())
        self.assertEqual(2, out.returncode,
                         "a failed scan stage must not exit 0 with no findings")
        self.assertIn("SCANNER_ERROR", out.stdout)
        self.assertNotIn("SECRET_CANDIDATE", out.stdout)

    def test_detect_ecosystems_reports_a_broken_classifier(self):
        (self.repo / "main.go").write_text("package main\n")
        self.git("add", "-A")
        out = self.script("detect-ecosystems.sh", extra_env=self._broken_awk())
        self.assertEqual(2, out.returncode)
        self.assertEqual("", out.stdout.strip())

    def test_resolve_scope_unreadable_index_is_not_an_omitted_scope(self):
        # `git ... | tr` reports tr's success without pipefail, so a dead git
        # yielded an empty path list — which resolve-scope reads as "nothing
        # staged" and answers `omitted`. That is a confident wrong answer, not
        # a failure. Only a structural check covered this before.
        shim_dir = self.repo / ".gshim"
        shim_dir.mkdir(exist_ok=True)
        shim = shim_dir / "git"
        shim.write_text("#!/usr/bin/env bash\n"
                        'for a in "$@"; do\n'
                        '  if [ "$a" = "diff" ]; then echo "fatal: broken" >&2; exit 128; fi\n'
                        "done\n"
                        f'exec {GIT} "$@"\n')
        shim.chmod(0o755)
        (self.repo / "svc").mkdir()
        (self.repo / "svc" / "a.go").write_text("package svc\n")
        self.git("add", "-A")
        out = self.script("resolve-scope.sh",
                          extra_env={"PATH": f"{shim_dir}:{os.environ['PATH']}"})
        self.assertEqual(2, out.returncode)
        self.assertNotIn("SCOPE_SOURCE: omitted", out.stdout,
                         "an unreadable index must not answer 'omitted'")

    def test_resolve_scope_reports_a_broken_classifier(self):
        (self.repo / "svc").mkdir()
        (self.repo / "svc" / "a.go").write_text("package svc\n")
        self.git("add", "-A")
        out = self.script("resolve-scope.sh", extra_env=self._broken_awk())
        self.assertEqual(2, out.returncode)
        self.assertNotIn("SCOPE:", out.stdout)


@unittest.skipUnless(GIT, "git not installed")
@needs_intervals
class LargeFileEarlyExitTests(_RepoTestCase):
    """INTERACTION test, not a single-point one. Three individually-correct
    choices combined into a false block: the context extractor exits early
    (`NR > n + 2`), the writer was a pipe, and pipefail was added to catch
    stage failures. On a small blob the writer finishes first and nothing
    happens; past the pipe buffer it is still writing when the reader leaves,
    takes SIGPIPE, exits 141, and a COMPLETED context render is reported as a
    scanner failure. Size-dependent, so every small fixture missed it."""

    LINES = 20000

    def _stage_big(self, name="big.py", secret_first=True):
        pad = "".join(f"padding line {i} aaaaaaaaaaaaaaaaaaaa\n"
                      for i in range(1, self.LINES + 1))
        body = ('KEY = "AKIAIOSFODNN7EXAMPLE"\n' + pad) if secret_first else (pad + 'KEY = "AKIAIOSFODNN7EXAMPLE"\n')
        (self.repo / name).write_text(body)
        self.git("add", name)
        return len(body)

    def test_small_and_large_blobs_agree(self):
        # The bug was invisible at small sizes: assert both, in one test, so a
        # regression cannot hide behind a passing small case.
        (self.repo / "small.py").write_text('KEY = "AKIAIOSFODNN7EXAMPLE"\na\nb\n')
        self.git("add", "small.py")
        small = self.script("secret-scan.sh")
        self.assertEqual(0, small.returncode, small.stdout)
        self.git("reset", "-q")

        size = self._stage_big()
        self.assertGreater(size, 65536, "fixture must exceed the pipe buffer to be meaningful")
        big = self.script("secret-scan.sh")
        self.assertEqual(0, big.returncode,
                         f"a completed context render must not read as a failure:\n{big.stdout}")
        self.assertNotIn("SCANNER_ERROR", big.stdout)

    def test_large_blob_still_renders_its_context(self):
        # The fix must not be "stop rendering context"; the window must survive.
        self._stage_big()
        out = self.script("secret-scan.sh")
        self.assertEqual(0, out.returncode)
        self.assertIn("SECRET_CANDIDATE: big.py:1", out.stdout)
        self.assertIn("CONTEXT: big.py:2", out.stdout)
        self.assertIn("CONTEXT: big.py:3", out.stdout)

    def test_secret_at_the_end_of_a_large_blob(self):
        # Reader reaches EOF, so no early exit fires — the other side of the
        # branch, and it must be clean too.
        self._stage_big(secret_first=False)
        out = self.script("secret-scan.sh")
        self.assertEqual(0, out.returncode, out.stdout)
        self.assertIn(f"SECRET_CANDIDATE: big.py:{self.LINES + 1}", out.stdout)

    def test_allowlisted_large_file_is_not_a_scanner_error(self):
        # An allowlisted path still goes through context rendering, so the false
        # block fired even for a finding the repo had already signed off.
        (self.repo / ".commit-secret-allowlist").write_text("big.py\n")
        self.git("add", ".commit-secret-allowlist")
        self.git("commit", "-qm", "chore: add allowlist")
        self._stage_big()
        out = self.script("secret-scan.sh")
        self.assertEqual(0, out.returncode, out.stdout)
        self.assertIn("ALLOWLISTED: big.py:1", out.stdout)
        self.assertNotIn("SCANNER_ERROR", out.stdout)

    def _awk_failing_only_at(self, marker):
        """An `awk` that fails ONLY the invocation carrying `marker`, passing
        every other stage through to the real one.

        A shim that breaks every awk cannot prove the context stage is checked:
        the earlier stages fail first and supply the exit 2 on their own. That
        is how a mutation removing the context check survived — the test could
        not tell which stage produced the error.
        """
        real = shutil.which("awk")
        shim_dir = self.repo / f".awkshim{abs(hash(marker)) % 1000}"
        shim_dir.mkdir(exist_ok=True)
        shim = shim_dir / "awk"
        shim.write_text("#!/usr/bin/env bash\n"
                        'for a in "$@"; do\n'
                        f'  case "$a" in {marker}) echo "awk: broken" >&2; exit 2 ;; esac\n'
                        "done\n"
                        f'exec {real} "$@"\n')
        shim.chmod(0o755)
        return {"PATH": f"{shim_dir}:{os.environ['PATH']}"}

    def test_broken_extractor_still_detected_on_a_large_blob(self):
        # The fix must not buy its clean exit by weakening detection: a real
        # extractor failure must still surface at the size that used to break.
        self._stage_big()
        out = self.script("secret-scan.sh",
                          extra_env=self._awk_failing_only_at("pfile=*"))
        self.assertEqual(2, out.returncode,
                         f"a context-stage failure must fail closed:\n{out.stdout}")
        self.assertIn("context rendering failed", out.stdout,
                      "the failing stage must name itself, not lean on another "
                      "stage's error")

    def test_context_stage_failure_is_attributed_to_the_context_stage(self):
        # Same isolation on a small blob: the check must exist independently of
        # the SIGPIPE fix, at any size.
        (self.repo / "s.py").write_text('KEY = "AKIAIOSFODNN7EXAMPLE"\na\nb\n')
        self.git("add", "s.py")
        out = self.script("secret-scan.sh",
                          extra_env=self._awk_failing_only_at("pfile=*"))
        self.assertEqual(2, out.returncode)
        self.assertIn("context rendering failed", out.stdout)
        # The finding itself still came from a working stage, so it must stand.
        self.assertIn("SECRET_CANDIDATE: s.py:1", out.stdout)

    def test_many_findings_in_a_large_blob_stay_bounded(self):
        # Context is rendered once per finding. Dropping the early exit instead
        # of the pipe would make this O(findings x lines); assert it completes.
        rows = "".join(f'key_{i} = "AKIAIOSFODNN7EXAMP{i:02d}"\n' for i in range(60))
        pad = "".join(f"pad {i}\n" for i in range(self.LINES))
        (self.repo / "many.py").write_text(rows + pad)
        self.git("add", "many.py")
        started = time.monotonic()
        out = self.script("secret-scan.sh")
        self.assertEqual(0, out.returncode, out.stdout)
        self.assertGreaterEqual(out.stdout.count("SECRET_CANDIDATE"), 60)
        self.assertLess(time.monotonic() - started, 45,
                        "per-finding context rendering must not blow up on size")


GITLEAKS = shutil.which("gitleaks")




@unittest.skipUnless(GIT and GITLEAKS,
                     "gitleaks not installed — the exit-code contract is "
                     "exercised only against a shim on this host, which is a "
                     "gap in the evidence, not a pass")
class RealGitleaksContractTests(_RepoTestCase):
    """The other gitleaks tests drive a SHIM, which proves the script reacts
    correctly to exit codes 0/1/10 but not that the real binary produces them.
    This class closes that loop where the binary exists. Its skip is surfaced by
    run_regression.sh (`-rs`) so the gap stays visible instead of silent."""

    # NOT the AWS documentation key. Verified against gitleaks v8.24.3: it
    # allowlists AKIAIOSFODNN7EXAMPLE and reports "no leaks found", so a test
    # built on that fixture proves nothing about the real scanner. The regex
    # fallback still flags it — that is the fallback's job — but gitleaks does not.
    UNALLOWLISTED_KEY = 'AWS_ACCESS_KEY_ID = "AKIA4T7YQ2XNZP9WLKD3"\n'

    def test_real_gitleaks_findings_use_the_pinned_exit_code(self):
        # The script pins findings to 10 because gitleaks' default 1 is
        # ambiguous between findings and execution errors. Verified against the
        # real binary: default exit is 1, --exit-code 10 yields 10.
        (self.repo / "leak.py").write_text(self.UNALLOWLISTED_KEY)
        self.git("add", "leak.py")
        out = subprocess.run(
            [GITLEAKS, "git", "--pre-commit", "--redact", "--staged",
             "--no-banner", "--exit-code", "10"],
            cwd=self.repo, env=_env(), capture_output=True, text=True, timeout=120)
        self.assertEqual(10, out.returncode,
                         f"real gitleaks did not honour --exit-code 10; the "
                         f"script's contract assumes it does:\n{out.stdout}{out.stderr}")

    def test_real_gitleaks_clean_stage_exits_zero(self):
        (self.repo / "ok.py").write_text("x = 1\n")
        self.git("add", "ok.py")
        out = subprocess.run(
            [GITLEAKS, "git", "--pre-commit", "--redact", "--staged",
             "--no-banner", "--exit-code", "10"],
            cwd=self.repo, env=_env(), capture_output=True, text=True, timeout=120)
        self.assertEqual(0, out.returncode, out.stdout + out.stderr)

    def test_real_gitleaks_has_the_git_subcommand(self):
        # Verified: gitleaks v8.18.4 has NO `git` subcommand and exits 1 for
        # every invocation — which the script correctly treats as a scanner
        # failure (1 is not in {0,10}) and fails closed on. If this assertion
        # fires, the installed gitleaks predates the documented invocation and
        # the version hint in the script's SCANNER_ERROR is the fix to read.
        out = subprocess.run([GITLEAKS, "git", "--help"],
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(0, out.returncode,
                         "installed gitleaks has no `git` subcommand (needs >= 8.19)")

    def test_secret_scan_composes_with_the_real_scanner(self):
        (self.repo / "leak.py").write_text(self.UNALLOWLISTED_KEY)
        self.git("add", "leak.py")
        out = self.script("secret-scan.sh")
        self.assertEqual(0, out.returncode,
                         f"real findings are a completed scan, not a scanner "
                         f"failure:\n{out.stdout}")
        self.assertNotIn("SCANNER_ERROR", out.stdout)


@unittest.skipUnless(GIT, "git not installed")
class AwkCapabilityTests(_RepoTestCase):
    """Twelve credential patterns are length-anchored by regex intervals. An awk
    without interval support treats `{16}` as literal braces, so AKIA…, ghp_…
    and the 20+ blob rule all match nothing and the scan prints a clean result.
    Silent, and invisible in the output — so it must fail closed."""

    def test_capability_probe_agrees_with_the_script(self):
        """Guard the guard, in whichever direction this host lies. The suite's
        gating and the script's refusal must agree, or one of them is wrong."""
        (self.repo / "leak.py").write_text('K = "AKIA4T7YQ2XNZP9WLKD3"\n')
        self.git("add", "leak.py")
        out = self.script("secret-scan.sh")
        if AWK_INTERVALS:
            self.assertNotEqual(2, out.returncode,
                                f"probe says intervals work, script refused:\n{out.stdout}")
        else:
            self.assertEqual(2, out.returncode,
                             "probe says intervals are missing, so the script "
                             "must refuse rather than report a false clean")
            self.assertIn("regex intervals", out.stdout)

    @unittest.skipIf(AWK_INTERVALS,
                     "host awk supports intervals; the native refusal path is "
                     "covered by the shim test below")
    def test_native_interval_less_awk_refuses(self):
        # Runs for real on Debian 12: no shim, the host's own mawk.
        (self.repo / "leak.py").write_text('K = "AKIA4T7YQ2XNZP9WLKD3"\n')
        self.git("add", "leak.py")
        out = self.script("secret-scan.sh")
        self.assertEqual(2, out.returncode)
        self.assertNotIn("SECRET_CANDIDATE", out.stdout,
                         "no findings may be claimed by a matcher that cannot match")

    def test_awk_without_interval_support_refuses_to_scan(self):
        real = shutil.which("awk")
        shim_dir = self.repo / ".awkcap"
        shim_dir.mkdir(exist_ok=True)
        shim = shim_dir / "awk"
        # Fail only the capability probe, so this proves the probe is what
        # blocks — not some later stage failing for its own reasons.
        shim.write_text("#!/usr/bin/env bash\n"
                        'for a in "$@"; do\n'
                        '  case "$a" in *AWK_PROBE*) exit 1 ;; esac\n'
                        "done\n"
                        f'exec {real} "$@"\n')
        shim.chmod(0o755)
        (self.repo / "leak.py").write_text('K = "AKIAIOSFODNN7EXAMPLE"\n')
        self.git("add", "leak.py")
        out = self.script("secret-scan.sh",
                          extra_env={"PATH": f"{shim_dir}:{os.environ['PATH']}"})
        self.assertEqual(2, out.returncode,
                         "an awk that cannot match the patterns must not report clean")
        self.assertIn("regex intervals", out.stdout)
        self.assertNotIn("SECRET_CANDIDATE", out.stdout,
                         "no findings may be claimed when the matcher is unusable")


@unittest.skipUnless(GIT, "git not installed")
@needs_intervals
class RedactionPriorityTests(_RepoTestCase):
    """Detection and the cut point are different decisions. The 20+ char blob
    rule must never decide detection (every long identifier would become a
    finding) but must always constrain the cut. It used to apply only when
    nothing else matched, so a long token BEFORE a sensitive key printed in
    full — on the finding line itself, not merely in context."""

    TOKEN = "Zm9vYmFyYmF6cXV4MTIzNDU2Nzg5MDEyMzQ1Njc4OQ"

    def _scan(self, body):
        (self.repo / "conf.env").write_text(body)
        self.git("add", "conf.env")
        out = self.script("secret-scan.sh")
        self.assertEqual(0, out.returncode, out.stdout)
        return out.stdout

    def test_blob_before_a_sensitive_key_is_not_printed(self):
        got = self._scan(f"SESSION={self.TOKEN} password = hunter2\n")
        self.assertIn("SECRET_CANDIDATE", got, "the keyed secret is still detected")
        self.assertNotIn(self.TOKEN, got, "the earlier blob must set the cut point")
        self.assertNotIn("hunter2", got)

    def test_blob_before_a_key_is_masked_in_context_too(self):
        got = self._scan(f"SESSION={self.TOKEN} password = hunter2\n"
                         'api_key = AKIAIOSFODNN7EXAMPLE\n')
        self.assertIn("CONTEXT: conf.env:1", got)
        self.assertNotIn(self.TOKEN, got)

    def test_a_long_identifier_alone_is_not_a_finding(self):
        # The blob rule constrains the cut; it must not manufacture findings.
        got = self._scan("const AuthenticationProviderFactoryRegistry = 1\n")
        self.assertNotIn("SECRET_CANDIDATE", got)


@unittest.skipUnless(GIT, "git not installed")
class DeletionAwarenessTests(_RepoTestCase):
    """A deletion is the change most likely to break its ecosystem's build."""

    def _detected(self):
        return self.script("detect-ecosystems.sh").stdout.split()

    def test_deleted_source_file_still_selects_its_gate(self):
        # Was: --diff-filter=d hid deletions, so removing a helper that other
        # modules import selected no Python gate and the break shipped.
        (self.repo / "helper.py").write_text("def add(a, b):\n    return a + b\n")
        (self.repo / "web.js").write_text("console.log(1);\n")
        self.git("add", "-A")
        self.git("commit", "-qm", "chore: add sources")
        self.git("rm", "-q", "helper.py")
        (self.repo / "web.js").write_text("console.log(2);\n")
        self.git("add", "-A")
        self.assertEqual({"python", "node"}, set(self._detected()),
                         "a deleted .py must still select the python gate")

    def test_deletion_only_stage_selects_its_gate(self):
        (self.repo / "mod.rs").write_text("fn a() {}\n")
        self.git("add", "-A")
        self.git("commit", "-qm", "chore: add rust")
        self.git("rm", "-q", "mod.rs")
        self.assertEqual(["rust"], self._detected())

    def test_rename_across_extensions_selects_both_gates(self):
        # --no-renames makes both sides visible: foo.py -> foo.txt removes a
        # Python file even though the "new" path has no ecosystem.
        (self.repo / "foo.py").write_text("x = 1\n")
        self.git("add", "-A")
        self.git("commit", "-qm", "chore: add py")
        self.git("mv", "foo.py", "foo.txt")
        self.assertEqual(["python"], self._detected())


@unittest.skipUnless(GIT, "git not installed")
@needs_intervals
class SecretScanFailClosedTests(_RepoTestCase):
    """A scan that cannot read the index must never look like a clean scan."""

    def _git_shim(self, failing_subcommand):
        """A `git` on PATH that fails one subcommand and passes the rest."""
        shim_dir = self.repo / ".shim"
        shim_dir.mkdir(exist_ok=True)
        shim = shim_dir / "git"
        # Match the subcommand ANYWHERE in argv: the scanner invokes
        # `git -c core.quotePath=false diff ...`, so a shim testing only $1
        # would pass that call straight through to the real git and quietly
        # stop simulating the failure it exists to simulate.
        shim.write_text(
            "#!/usr/bin/env bash\n"
            'for a in "$@"; do\n'
            f'  if [ "$a" = "{failing_subcommand}" ]; then\n'
            '    echo "fatal: unable to read files to diff" >&2\n'
            "    exit 128\n"
            "  fi\n"
            "done\n"
            f'exec {GIT} "$@"\n'
        )
        shim.chmod(0o755)
        return {"PATH": f"{shim_dir}:{os.environ['PATH']}"}

    def _stage_a_real_leak(self):
        (self.repo / "leak.py").write_text('AWS_KEY = "AKIAIOSFODNN7EXAMPLE"\n')
        (self.repo / "server.pem").write_text("-----BEGIN RSA PRIVATE KEY-----\n")
        self.git("add", "leak.py", "server.pem")

    def test_baseline_leak_is_reported(self):
        self._stage_a_real_leak()
        out = self.script("secret-scan.sh")
        self.assertEqual(0, out.returncode)
        self.assertIn("SECRET_CANDIDATE", out.stdout)
        self.assertIn("SENSITIVE_FILE: server.pem", out.stdout)

    def test_failing_diff_exits_2_instead_of_reporting_clean(self):
        # Was: `git diff | awk` reported awk's exit 0, so a dead git produced an
        # empty stdout and exit 0 — indistinguishable from "no secrets found".
        self._stage_a_real_leak()
        out = self.script("secret-scan.sh", extra_env=self._git_shim("diff"))
        self.assertEqual(2, out.returncode,
                         "a git failure must fail closed, not read as clean")
        self.assertNotIn("SECRET_CANDIDATE", out.stdout,
                         "no findings are claimed when the read failed")
        # EVERY stage that could not run must report itself. Asserting only
        # "some SCANNER_ERROR appeared" was too loose: the content-read error
        # alone satisfied it while the filename stage failed SILENTLY, because
        # `git ... | tr` reports tr's success unless pipefail is set. Counting
        # the markers encodes the property without pinning the wording.
        self.assertGreaterEqual(
            out.stdout.count("SCANNER_ERROR"), 2,
            f"both the filename and content stages failed here; each must say "
            f"so, else one silently reports nothing:\n{out.stdout}")

    def test_outside_a_work_tree_exits_2(self):
        out = subprocess.run(["bash", str(SCRIPTS / "secret-scan.sh")],
                             cwd=tempfile.gettempdir(), env=_env(),
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(2, out.returncode)
        self.assertIn("SCANNER_ERROR", out.stdout)


@unittest.skipUnless(GIT, "git not installed")
@needs_intervals
class SecretScanKeyedSecretTests(_RepoTestCase):
    """`password = x` was the only shape recognised: not `:`, not uppercase."""

    def _scan(self, name, body):
        (self.repo / name).write_text(body)
        self.git("add", name)
        out = self.script("secret-scan.sh")
        self.assertEqual(0, out.returncode, out.stdout)
        return out.stdout

    def test_json_password_is_detected(self):
        got = self._scan("config.json",
                         '{\n  "db_password": "Tr0ub4dor",\n  "db_user": "svc"\n}\n')
        self.assertIn("SECRET_CANDIDATE: config.json:2", got)
        self.assertNotIn("Tr0ub4dor", got)

    def test_uppercase_and_yaml_keys_are_detected(self):
        got = self._scan("conf.yaml", "PASSWORD = hunter2\nApi_Key: abc123xyz\n")
        self.assertNotIn("hunter2", got)
        self.assertNotIn("abc123xyz", got)
        self.assertEqual(2, got.count("SECRET_CANDIDATE"))

    def test_context_masks_a_neighbouring_keyed_secret(self):
        # The reported defect: a short JSON password two lines from a token
        # match printed verbatim in CONTEXT, so triage output leaked the secret.
        got = self._scan(
            "app.json",
            '{\n  "db_password": "Tr0ub4dor",\n'
            '  "api_key": "AKIAIOSFODNN7EXAMPLE",\n  "db_user": "svc"\n}\n',
        )
        self.assertIn("CONTEXT: app.json", got)
        self.assertNotIn("Tr0ub4dor", got,
                         "a keyed secret must be masked in CONTEXT lines too")

    def test_non_sensitive_keys_are_left_readable(self):
        # Masking everything would make CONTEXT useless for triage.
        got = self._scan("app.json",
                         '{\n  "api_key": "AKIAIOSFODNN7EXAMPLE",\n  "region": "us-east-1"\n}\n')
        self.assertIn('"region": "us-east-1"', got)

    def test_ordinary_code_produces_no_findings(self):
        got = self._scan("main.go",
                         'func main() {\n\tfmt.Println("hello")\n\tx := total(a, b)\n}\n')
        self.assertNotIn("SECRET_CANDIDATE", got)

    def test_non_ascii_prefix_does_not_corrupt_redaction(self):
        # tolower() is locale-sensitive; if it changed byte length the cut point
        # would slide and expose part of the value.
        got = self._scan("doc.md", "配置说明\n数据库口令 password = hunter2\n结束\n")
        self.assertNotIn("hunter2", got)
        self.assertIn("数据库口令", got, "the readable prefix must survive intact")


@unittest.skipUnless(GIT, "git not installed")
class RunGateKillEscalationTests(_RepoTestCase):
    CLEAR = {
        "QUALITY_GATE_TIMEOUT_SECONDS": "",
        "SKILL_QUALITY_GATE_TIMEOUT_SECONDS": "",
        "COMMIT_TEST_TIMEOUT": "",
    }

    def _timeout_shim(self, supports_k):
        """A fake `timeout` that logs its argv; optionally rejects -k."""
        shim_dir = self.repo / ".tshim"
        shim_dir.mkdir(exist_ok=True)
        log = shim_dir / "argv"
        reject = ('if [ "$1" = "-k" ]; then echo "unrecognized option -k" >&2; exit 125; fi\n'
                  if not supports_k else "")
        body = (
            "#!/usr/bin/env bash\n"
            + reject
            + f'echo "$*" >> "{log}"\n'
            'if [ "$1" = "-k" ]; then shift 2; fi\n'
            "shift\n"
            'exec "$@"\n'
        )
        for name in ("timeout", "gtimeout"):
            f = shim_dir / name
            f.write_text(body)
            f.chmod(0o755)
        return {"PATH": f"{shim_dir}:{os.environ['PATH']}"}, log

    def test_kill_after_is_passed_when_supported(self):
        # Was: `exec timeout "$SECS" "$@"` sent TERM only. The GNU manual's own
        # example shows timeout returning 124 while a TERM-ignoring command
        # keeps running — so the "process tree is dead" promise was unbacked.
        env, log = self._timeout_shim(supports_k=True)
        out = self.script("run-gate.sh", "-t", "7", "true",
                          extra_env={**self.CLEAR, **env})
        self.assertEqual(0, out.returncode)
        argv = [l for l in log.read_text().splitlines() if l.endswith("true")]
        self.assertTrue(any(l.startswith("-k ") for l in argv),
                        f"run-gate must pass --kill-after; argv was {argv}")

    def test_tool_without_kill_after_is_skipped_not_used(self):
        # The invariant is "never USE a tool that cannot force-kill". What
        # happens next depends on the host: with a qualifying alternative the
        # gate runs, without one the script refuses. Alpine has no perl, so
        # hardcoding rc==0 failed there for the right reason — derive it.
        env, log = self._timeout_shim(supports_k=False)
        out = self.script("run-gate.sh", "-t", "7", "true",
                          extra_env={**self.CLEAR, **env})
        self.assertFalse(log.exists(),
                         f"the weak tool must not be used at all; it ran: "
                         f"{log.read_text() if log.exists() else ''}")
        self.assertIn("trying the next tool", out.stderr)
        if shutil.which("perl"):
            self.assertEqual(0, out.returncode,
                             "with perl available the gate must still run")
        else:
            self.assertEqual(2, out.returncode,
                             "with no qualifying tool the script must refuse")
            self.assertIn("refusing to run", out.stderr)

    def test_refuses_when_nothing_can_force_kill(self):
        # No eligible tool anywhere: refusing is the only honest outcome, because
        # a run here would carry weaker timeout semantics than on every other host.
        env, log = self._timeout_shim(supports_k=False)
        shim_dir = env["PATH"].split(":")[0]
        out = subprocess.run([shutil.which("bash"), str(SCRIPTS / "run-gate.sh"),
                              "-t", "7", "true"],
                             cwd=self.repo,
                             env={**_env(self.CLEAR), "PATH": shim_dir},
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(2, out.returncode)
        self.assertIn("refusing to run", out.stderr)
        self.assertFalse(log.exists(), "the gate must not run through a weak tool")

    def test_term_ignoring_gate_is_actually_killed(self):
        # End-to-end on whichever branch this host uses.
        marker = self.repo / "child.pid"
        gate = self.repo / "stubborn.sh"
        gate.write_text("#!/usr/bin/env bash\ntrap '' TERM\necho $$ > \"%s\"\nsleep 45\n" % marker)
        gate.chmod(0o755)
        out = self.script("run-gate.sh", "-t", "1", str(gate), extra_env=self.CLEAR)
        self.assertEqual(124, out.returncode,
                         f"a TERM-ignoring gate must still time out as 124; "
                         f"got {out.returncode}\n{out.stderr}")
        pid = int(marker.read_text().strip())
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return
            time.sleep(0.1)
        os.kill(pid, signal.SIGKILL)
        self.fail("a TERM-ignoring gate survived its timeout")


@unittest.skipUnless(GIT, "git not installed")
class ResolveScopeTests(_RepoTestCase):
    def test_outside_a_work_tree_exits_2(self):
        out = subprocess.run(["bash", str(SCRIPTS / "resolve-scope.sh")],
                             cwd=tempfile.gettempdir(), env=_env(),
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(2, out.returncode, "a scope must never be guessed from a failed read")

    def test_unborn_head_bootstraps_from_staged_paths(self):
        empty = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, empty, True)
        subprocess.run([GIT, "init", "-q"], cwd=empty, env=_env(), check=True)
        (empty / "pkg" / "reporting").mkdir(parents=True)
        (empty / "pkg" / "reporting" / "r.go").write_text("package reporting\n")
        subprocess.run([GIT, "add", "-A"], cwd=empty, env=_env(), check=True)
        out = subprocess.run(["bash", str(SCRIPTS / "resolve-scope.sh")], cwd=empty,
                             env=_env(), capture_output=True, text=True, timeout=60)
        self.assertEqual(0, out.returncode, out.stderr)
        self.assertIn("SCOPE: reporting", out.stdout)
        self.assertIn("SCOPE_SOURCE: bootstrap", out.stdout)

    def test_nothing_staged_omits_without_failing(self):
        out = self.script("resolve-scope.sh")
        self.assertEqual(0, out.returncode)
        self.assertIn("SCOPE: (none)", out.stdout)


@unittest.skipUnless(GIT, "git not installed")
class RunGateCancellationTests(_RepoTestCase):
    """Cancelling the executor must cancel the gate.

    While run-gate `exec`ed the timeout tool, a signal to the executor hit the
    tool directly. Normalising the exit code introduced a supervisor that only
    `wait`ed — so SIGTERM returned 143 at once while the gate ran on and wrote
    its side effect two seconds later. Regression, caught by fault injection.
    """

    CLEAR = {"QUALITY_GATE_TIMEOUT_SECONDS": "", "SKILL_QUALITY_GATE_TIMEOUT_SECONDS": "",
             "COMMIT_TEST_TIMEOUT": ""}

    def _launch_slow_gate(self):
        """A gate that records its pid, then leaves a marker 2s later."""
        pidfile = self.repo / "child.pid"
        marker = self.repo / "side_effect"
        gate = self.repo / "gate.sh"
        gate.write_text(
            "#!/usr/bin/env bash\n"
            f'echo $$ > "{pidfile}"\n'
            "sleep 2\n"
            f'echo landed > "{marker}"\n'
            "sleep 30\n")
        gate.chmod(0o755)
        proc = subprocess.Popen(
            ["bash", str(SCRIPTS / "run-gate.sh"), "-t", "60", str(gate)],
            cwd=self.repo, env=_env(self.CLEAR),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and not pidfile.exists():
            time.sleep(0.05)
        self.assertTrue(pidfile.exists(), "gate never started")
        return proc, int(pidfile.read_text().strip()), marker

    def _assert_cancelled(self, proc, child, marker, sig, want_rc):
        """Assert the guarantee, not more than it.

        GUARANTEED: the gate is dead before the executor exits, and nothing new
        appears afterwards. NOT guaranteed, and deliberately not asserted: that
        a gate does zero work during the graceful window. Cancellation forwards
        TERM first precisely so a gate may clean up; a shell gate can finish the
        statement it was on. Asserting "no side effect at all" made this a race
        on how far the gate got before TERM landed — it passed, by luck.
        """
        proc.send_signal(sig)
        try:
            proc.wait(timeout=40)
        except subprocess.TimeoutExpired:
            proc.kill()
            self.fail("the executor did not exit after being signalled")
        self.assertEqual(want_rc, proc.returncode,
                         f"expected {want_rc} after {sig!r}, got {proc.returncode}")
        # The gate must be gone BEFORE the executor exits, not eventually.
        try:
            os.kill(child, 0)
            os.kill(child, signal.SIGKILL)
            self.fail(f"gate {child} outlived the cancelled executor")
        except ProcessLookupError:
            pass
        # And it must not act again: snapshot, wait past the gate's own next
        # step, and require no change.
        before = marker.exists()
        time.sleep(3)
        self.assertEqual(before, marker.exists(),
                         "the gate produced a NEW side effect after the "
                         "executor had already exited")

    def test_sigterm_cancels_the_gate_before_exiting(self):
        proc, child, marker = self._launch_slow_gate()
        self._assert_cancelled(proc, child, marker, signal.SIGTERM, 143)

    def test_sigint_cancels_the_gate_before_exiting(self):
        proc, child, marker = self._launch_slow_gate()
        self._assert_cancelled(proc, child, marker, signal.SIGINT, 130)

    def _launch(self, gate_body, extra_env=None, secs="300"):
        """Launch run-gate over a gate that records its pid, via the REAL path."""
        pidfile = self.repo / "child.pid"
        marker = self.repo / "side_effect"
        gate = self.repo / "gate.sh"
        gate.write_text("#!/usr/bin/env bash\n" + gate_body.replace(
            "@PID@", str(pidfile)).replace("@MARKER@", str(marker)))
        gate.chmod(0o755)
        env = dict(self.CLEAR)
        if extra_env:
            env.update(extra_env)
        proc = subprocess.Popen(
            ["bash", str(SCRIPTS / "run-gate.sh"), "-t", secs, str(gate)],
            cwd=self.repo, env=_env(env),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if pidfile.exists() and pidfile.read_text().strip():
                break
            time.sleep(0.05)
        else:
            proc.kill()
            self.fail("gate never started")
        return proc, int(pidfile.read_text().strip()), marker

    def _cancel_and_require_gate_stopped(self, proc, child, sig, want_rc, note):
        proc.send_signal(sig)
        try:
            _, err = proc.communicate(timeout=60)
        except subprocess.TimeoutExpired:
            proc.kill()
            os.kill(child, signal.SIGKILL)
            self.fail("the executor did not exit after being signalled")
        self.assertEqual(want_rc, proc.returncode, f"{note}: exit code")
        try:
            os.kill(child, 0)
            os.kill(child, signal.SIGKILL)
            self.fail(f"{note}: gate {child} is STILL RUNNING after the "
                      f"executor returned — the contract is that the executor "
                      f"returns only once the gate has stopped")
        except ProcessLookupError:
            pass
        return err

    def test_sighup_stops_the_gate_via_the_real_watcher(self):
        """SIGHUP, through the real path, on an ordinary gate.

        Reproduced before the fix: exit 129 in 0 seconds with the gate still
        running. The watcher set no `$SIG{HUP}` at all, so it died instantly,
        and it had moved the gate into a process group of its own — measured
        perl pgid 60922 vs gate pgid 60923 — so the supervisor's group signal
        and its KILL escalation both landed on a group holding only perl.
        The earlier shim-based test could not see this: its shim left the child
        in the same group, so it never reproduced the topology that broke.
        """
        proc, child, _ = self._launch('echo $$ > "@PID@"\nsleep 40\n')
        self._cancel_and_require_gate_stopped(proc, child, signal.SIGHUP, 129, "SIGHUP")

    def test_term_ignoring_gate_is_stopped_when_the_executor_is_cancelled(self):
        """A gate that ignores TERM, cancelled from outside, through the real path.

        Reproduced before the fix: exit 143 after ~12s with the gate still
        running. The watcher forwarded TERM but never escalated, and the
        supervisor's escalation could not reach the gate's separate group.
        """
        proc, child, _ = self._launch(
            'trap "" TERM\necho $$ > "@PID@"\nsleep 60\n')
        self._cancel_and_require_gate_stopped(
            proc, child, signal.SIGTERM, 143, "TERM-ignoring gate")

    def test_the_gate_shares_the_supervisors_process_group(self):
        """The invariant the two tests above depend on.

        Stated separately so a regression names the cause rather than the
        symptom: if a tool re-groups the gate, cancellation cannot reach it.
        """
        proc, child, _ = self._launch('echo $$ > "@PID@"\nsleep 40\n')
        try:
            gate_pgid = os.getpgid(child)
            # 1. The gate's group must be ADDRESSABLE — that is the group the
            #    supervisor signals and escalates on. (`proc.pid` is the
            #    supervisor itself, not the group-leading job, so it is not the
            #    thing to compare against.)
            os.kill(-gate_pgid, 0)
            # 2. It must not be the supervisor's own group, nor ours: a group
            #    signal must never travel up to the caller.
            self.assertNotEqual(os.getpgid(proc.pid), gate_pgid,
                                "gate shares the supervisor's group; a group "
                                "signal would escape upward")
            self.assertNotEqual(os.getpgid(0), gate_pgid,
                                "gate shares OUR group; a group signal would "
                                "hit the test runner itself")
        finally:
            proc.send_signal(signal.SIGTERM)
            proc.communicate(timeout=60)
            try:
                os.kill(child, signal.SIGKILL)
            except ProcessLookupError:
                pass

    def test_cancellation_reaches_a_gate_whose_tool_does_not_forward(self):
        """This is what the GROUP kill buys over signalling the tool's pid.

        Reverting to a pid-only forward survived mutation testing, because on
        this host the perl watcher forwards signals itself. A tool that does not
        forward — plenty exist — leaves the gate running when only the tool's
        pid is signalled. Simulated with a `timeout` shim that ignores signals.
        """
        pidfile = self.repo / "child.pid"
        marker = self.repo / "side_effect"
        shim_dir = self.repo / "nofwd"
        shim_dir.mkdir(exist_ok=True)
        shim = shim_dir / "timeout"
        # Accepts -k (so run-gate deems it eligible), ignores TERM/INT, and does
        # not pass signals to its child.
        shim.write_text(
            "#!/usr/bin/env bash\n"
            "trap '' TERM INT\n"
            'if [ "$1" = "-k" ]; then shift 2; fi\n'
            "shift\n"
            '"$@" &\n'
            "wait $!\n")
        shim.chmod(0o755)
        (shim_dir / "gtimeout").write_text(shim.read_text())
        (shim_dir / "gtimeout").chmod(0o755)
        gate = self.repo / "gate.sh"
        gate.write_text("#!/usr/bin/env bash\n"
                        f'echo $$ > "{pidfile}"\n'
                        "sleep 2\n"
                        f'echo landed > "{marker}"\n'
                        "sleep 30\n")
        gate.chmod(0o755)
        proc = subprocess.Popen(
            ["bash", str(SCRIPTS / "run-gate.sh"), "-t", "60", str(gate)],
            cwd=self.repo,
            env=_env({**self.CLEAR, "PATH": f"{shim_dir}:{os.environ['PATH']}"}),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and not pidfile.exists():
            time.sleep(0.05)
        self.assertTrue(pidfile.exists(), "gate never started")
        child = int(pidfile.read_text().strip())
        started = time.monotonic()
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=40)
        except subprocess.TimeoutExpired:
            proc.kill()
            self.fail("executor did not exit")
        elapsed = time.monotonic() - started
        try:
            os.kill(child, 0)
            os.kill(child, signal.SIGKILL)
            self.fail(f"gate {child} survived: a non-forwarding tool needs the "
                      f"cancellation to go to the process GROUP, not its pid")
        except ProcessLookupError:
            pass
        # NOT asserting promptness. It is tempting — but measured: with a tool
        # that ignores TERM and a shell gate that survives it, forwarding to the
        # group is no faster than forwarding to the pid; both wait for the grace
        # window and are then resolved by the group KILL. Asserting a time bound
        # here failed on correct code, i.e. it demanded a guarantee the design
        # does not make. What the group form buys is that the ESCALATION reaches
        # the whole tree at all: a pid-only escalation leaves this gate running
        # forever, which is the mutation this test is here to kill.
        self.assertLess(elapsed, 35.0, "cancellation must terminate, bounded")
        # Same bounded claim as above: no NEW work once the executor is gone.
        before = marker.exists()
        time.sleep(3)
        self.assertEqual(before, marker.exists(),
                         "gate acted again after the executor exited")

    def test_cancellation_report_is_conditional_not_asserted(self):
        """Structural, and labelled as such.

        The report used to claim "then KILLed" unconditionally, so a run that
        left the gate alive still read as cleaned up. It now checks the group
        before saying so. The FAILING branch cannot be reached from a test —
        it needs a process that survives SIGKILL — so this pins the presence of
        the check rather than its behaviour. A mutation deleting the check
        survives on purpose; recording that is more useful than pretending the
        branch is covered.
        """
        script = (SCRIPTS / "run-gate.sh").read_text()
        cancel = script.split("forward_and_exit()", 1)[1].split("run_normalised()", 1)[0]
        self.assertIn("REMAIN", cancel,
                      "the report must be able to say cleanup did NOT complete")
        # The claim must come after a re-check, not before it.
        kill_at = cancel.index("kill -KILL")
        self.assertGreater(cancel.index("REMAIN"), kill_at,
                           "the verification must follow the KILL it verifies")

    def test_cancellation_is_reported(self):
        proc, child, marker = self._launch_slow_gate()
        proc.send_signal(signal.SIGTERM)
        _, err = proc.communicate(timeout=40)
        self.assertIn("GATE_CANCELLED", err,
                      "a cancelled run must say so, not look like a gate failure")


@unittest.skipUnless(GIT, "git not installed")
class PortabilityMatrixFaultTests(_RepoTestCase):
    """The matrix summarises evidence, so a failure it swallows is worse than no
    matrix at all. `if docker run ... | sed` tested SED's status: a container
    exiting 42 was reported as "all exercised implementations pass", exit 0.
    Driven with a `docker` shim, so no daemon is needed."""

    def _matrix_with_docker_stub(self, stub_body, extra_env=None):
        stub_dir = self.repo / "dstub"
        stub_dir.mkdir(exist_ok=True)
        stub = stub_dir / "docker"
        stub.write_text("#!/usr/bin/env bash\n" + stub_body)
        stub.chmod(0o755)
        # MATRIX_LOCAL=0: the local rows run the pytest suite, which contains
        # this very test. Without it the call recurses until killed.
        env = {"PATH": f"{stub_dir}:{os.environ['PATH']}",
               "MATRIX_DOCKER": "1", "MATRIX_IMAGES": "fake:img",
               "MATRIX_LOCAL": "0"}
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            ["bash", str(SCRIPTS / "run_portability_matrix.sh")],
            cwd=SKILL_DIR, env=_env(env), capture_output=True, text=True, timeout=600)

    def test_failing_container_is_not_summarised_as_pass(self):
        out = self._matrix_with_docker_stub(
            'if [ "$1" = "info" ]; then exit 0; fi\necho "some output"\nexit 42\n')
        self.assertNotEqual(0, out.returncode,
                            f"a failing container must fail the matrix:\n{out.stdout}")
        self.assertIn("FAILED", out.stdout)
        self.assertNotIn("exercised implementation(s) pass", out.stdout)

    def test_passing_container_still_passes(self):
        # Guard the guard: if a healthy container cannot pass, the test above
        # proves nothing about failure detection.
        out = self._matrix_with_docker_stub(
            'if [ "$1" = "info" ]; then exit 0; fi\necho "RESULT: PASS"\nexit 0\n')
        self.assertEqual(0, out.returncode, out.stdout)
        self.assertNotIn("FAILED", out.stdout)

    def test_unreachable_daemon_is_reported_not_counted(self):
        out = self._matrix_with_docker_stub('exit 1\n')
        self.assertIn("UNAVAILABLE", out.stdout)
        self.assertIn("docker", out.stdout.split("UNVERIFIED:")[1])

    def test_in_container_suite_status_is_not_masked_by_tail(self):
        script = (SCRIPTS / "run_portability_matrix.sh").read_text()
        assert_msg = ("`pytest ... | tail` reports tail's status; the suite's "
                      "exit code must be captured before the tail")
        self.assertNotIn("pytest scripts/tests/ -q -p no:cacheprovider -rs 2>&1 | tail",
                         script, assert_msg)
        self.assertIn("prc=$?", script, assert_msg)


@unittest.skipUnless(GIT, "git not installed")
class EvalHarnessGateTests(_RepoTestCase):
    """The eval runner grades an agent, so IT needs grading too.

    Driven with a stub `claude`, so this costs no model calls: an answer with no
    decision token must come back INCOMPLETE and non-zero (a missing answer is
    not a pass), and a wrong token must FAIL. A harness that cannot fail is not
    a check.
    """

    def setUp(self):
        super().setUp()
        runner_src = SKILL_DIR / "scripts" / "eval" / "run_eval.sh"
        if not runner_src.is_file():
            self.skipTest("scripts/eval/run_eval.sh not present")
        self.scen = self.repo / "scen"
        self.scen.mkdir()
        (self.scen / "01_probe.sh").write_text(
            'printf "package x\\n" > a.go\nPROMPT="Commit my changes."\nEXPECT="ASK"\n')
        # EVAL_SCEN_DIR, not a sed-rewritten copy. Copying the runner is exactly
        # what moved $0 and voided the skill arm; the env override exists so
        # nobody needs to.
        self.runner = runner_src

    def _run_with_stub(self, stub_body, extra_env=None):
        stub_dir = self.repo / "cstub"
        stub_dir.mkdir(exist_ok=True)
        stub = stub_dir / "claude"
        stub.write_text("#!/usr/bin/env bash\n" + stub_body)
        stub.chmod(0o755)
        env = {"PATH": f"{stub_dir}:{os.environ['PATH']}",
               "EVAL_WORK": str(self.repo / "evalwork"),
               "EVAL_SCEN_DIR": str(self.scen)}
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            ["bash", str(self.runner), "1"], cwd=self.repo,
            env=_env(env), capture_output=True, text=True, timeout=120)

    def test_missing_decision_token_is_incomplete_not_a_pass(self):
        out = self._run_with_stub('echo "a prose answer with no token"\n')
        self.assertIn("INCOMPLETE", out.stdout)
        self.assertNotEqual(0, out.returncode, "a run with no answer must not exit 0")
        self.assertIn("do not read this as a score", out.stdout)

    def test_wrong_decision_token_fails(self):
        out = self._run_with_stub('echo "DECISION: COMMIT"\n')
        self.assertIn("FAIL", out.stdout)
        self.assertNotEqual(0, out.returncode)

    def test_correct_decision_token_passes(self):
        # Guard the guard: if this cannot pass, the two gates above prove nothing.
        out = self._run_with_stub('echo "DECISION: ASK"\n')
        self.assertEqual(0, out.returncode, out.stdout)
        self.assertIn("PASS", out.stdout)

    def test_missing_skill_refuses_instead_of_running_a_void_skill_arm(self):
        """The worst outcome an eval can have: silently grading nothing.

        The runner derived SKILL_DIR from `$0`, so copying it elsewhere (to
        point it at a different scenario set) moved that path — `SKILL.md` did
        not exist, the prompt referenced a nonexistent file, and the SKILL ARM
        RAN WITH NO SKILL while still being labelled `skill`. Four recorded
        cells were void and read as wins. It must refuse.
        """
        stray = self.repo / "stray.sh"
        stray.write_text(self.runner.read_text())
        out = subprocess.run(
            ["bash", str(stray), "1"], cwd=self.repo,
            env=_env({"EVAL_WORK": str(self.repo / "w2"),
                      "EVAL_SCEN_DIR": str(self.scen)}),
            capture_output=True, text=True, timeout=120)
        self.assertEqual(2, out.returncode,
                         f"a missing SKILL.md must abort, not degrade:\n{out.stdout}{out.stderr}")
        self.assertIn("no SKILL.md", out.stderr)
        self.assertNotIn("PASS", out.stdout)

    def test_every_required_answer_pattern_is_checked(self):
        """EXPECT_ANSWER holds one pattern per line, ALL required.

        Grading only the first survived mutation testing because no scenario in
        the harness tests exercised two patterns — which is the same shape as
        the real defect it was written for: scenario 10 graded a subject's
        length but not its format, so a non-Conventional-Commits answer passed.
        """
        (self.scen / "01_probe.sh").write_text(
            'printf "package x\\n" > a.go\n'
            'PROMPT="Commit my changes."\n'
            'EXPECT="ANY"\n'
            'ANSWER_PROMPT="the subject line."\n'
            "EXPECT_ANSWER='^.{1,50}$\n^[a-z]+: [^ ]'\n")
        # Satisfies the length pattern, violates the format one.
        out = self._run_with_stub(
            'echo "DECISION: COMMIT"\necho "ANSWER: Add a reconciliation stub"\n')
        self.assertIn("FAIL", out.stdout,
                      f"an answer matching only the first pattern must fail:\n{out.stdout}")
        self.assertNotEqual(0, out.returncode)
        # And one satisfying both must pass, or the check above is vacuous.
        ok = self._run_with_stub(
            'echo "DECISION: COMMIT"\necho "ANSWER: feat: add reconciliation stub"\n')
        self.assertEqual(0, ok.returncode, ok.stdout)
        self.assertIn("PASS", ok.stdout)

    def test_transcripts_carry_provenance(self):
        """Each transcript must state which skill file produced it, so validity
        is auditable per cell rather than inferred from the reply's prose."""
        out = self._run_with_stub('echo "DECISION: ASK"\n')
        self.assertEqual(0, out.returncode, out.stdout)
        logs = list((self.repo / "evalwork").rglob("transcripts/*.txt"))
        self.assertTrue(logs, f"no transcript written:\n{out.stdout}")
        head = logs[0].read_text().splitlines()[:2]
        self.assertTrue(head[0].startswith("#EVAL_CELL"), head)
        self.assertTrue(head[1].startswith("#EVAL_SKILL"), head)
        self.assertIn("SKILL.md", head[1])

    def test_run_logs_which_skill_file_it_loaded(self):
        # A void arm has to be visible in the log after the fact, not only
        # preventable in advance.
        out = self._run_with_stub('echo "DECISION: ASK"\n')
        self.assertIn("SKILL.md", out.stdout)
        self.assertRegex(out.stdout, r"skill\s*:.*SKILL\.md \(\d+ lines\)")


@unittest.skipUnless(GIT and PREFLIGHT and COMMIT_BLOCK, "git or SKILL.md blocks unavailable")
@needs_intervals
class WholeWorkflowTests(_RepoTestCase):
    """Run §1 -> §7 in order, as one sequence, against one repo.

    SCOPE, STATED HONESTLY: this executes the commands SKILL.md tells the agent
    to run and asserts a real commit lands. It does NOT prove the agent *decides*
    correctly — no agent is in the loop. What it does prove is that the documented
    sequence is executable and internally coherent end to end: the part that rots
    when a script's interface changes and only its own unit test is updated.
    Per-step behaviour, including failure paths, is covered by the classes above.
    """

    def test_full_sequence_lands_a_commit(self):
        # A change with every wrinkle the workflow claims to handle at once:
        # a CJK deletion, a large file, unstaged dirt, and an established scope.
        for msg in ("feat(auth): add login",
                    "fix(auth): expire tokens",
                    "test(auth): cover refresh"):
            (self.repo / f"{abs(hash(msg)) % 99999}.go").write_text("package auth\n")
            self.git("add", "-A")
            self.git("commit", "-qm", msg)
        (self.repo / "源码").mkdir()
        (self.repo / "源码" / "旧模块.py").write_text("x = 1\n")
        self.git("add", "-A")
        self.git("commit", "-qm", "chore: legacy module")
        head_before = self.git("rev-parse", "HEAD").stdout.strip()

        (self.repo / "auth").mkdir()
        (self.repo / "auth" / "session.go").write_text(
            "package auth\n" + "".join(f"// line {i}\n" for i in range(20000)))
        self.git("rm", "-q", "源码/旧模块.py")
        self.git("add", "-A")
        (self.repo / "scratch.txt").write_text("work in progress\n")   # untracked dirt

        # --- §1 Preflight: must report no blocker ---
        pre = self.bash(PREFLIGHT)
        self.assertEqual(0, pre.returncode, pre.stderr)
        self.assertNotIn("IN_PROGRESS", pre.stdout)

        # --- §3 Secret gate: clean scan on a large + CJK-deleting stage ---
        scan = self.script("secret-scan.sh")
        self.assertEqual(0, scan.returncode, f"secret gate: {scan.stdout}")
        self.assertNotIn("SECRET_CANDIDATE", scan.stdout)

        # --- §4 Ecosystems: the CJK deletion must surface python ---
        eco = self.script("detect-ecosystems.sh")
        self.assertEqual(0, eco.returncode)
        self.assertEqual({"python", "go"}, set(eco.stdout.split()),
                         "a deleted CJK-named .py must still select the python gate")

        # --- §4 Gate under isolation + enforced timeout ---
        gate = self.script(
            "stash-guard.sh", "bash", str(SCRIPTS / "run-gate.sh"), "-t", "30",
            "sh", "-c", 'test ! -f scratch.txt && echo STAGED_ONLY',
            extra_env={"QUALITY_GATE_TIMEOUT_SECONDS": "",
                       "SKILL_QUALITY_GATE_TIMEOUT_SECONDS": "",
                       "COMMIT_TEST_TIMEOUT": ""})
        self.assertEqual(0, gate.returncode, gate.stdout + gate.stderr)
        self.assertIn("STAGED_ONLY", gate.stdout, "the gate must see the staged snapshot")
        self.assertEqual("work in progress\n", (self.repo / "scratch.txt").read_text(),
                         "unstaged dirt must be restored")
        self.assertEqual("", self.git("stash", "list").stdout, "no stash may be left behind")

        # --- §5 Scope ---
        scope = self.script("resolve-scope.sh")
        self.assertEqual(0, scope.returncode)
        self.assertIn("SCOPE: auth", scope.stdout)
        self.assertIn("SCOPE_SOURCE: canonical", scope.stdout)

        # --- §6 Commit, through the real guard block ---
        subject = "feat(auth): move session into its own file"
        self.assertLessEqual(len(subject), 50, "fixture subject must satisfy the guard")
        block = re.sub(r"^SUBJECT='.*'$", f"SUBJECT='{subject}'",
                       COMMIT_BLOCK, count=1, flags=re.MULTILINE)
        commit = self.bash(block)
        self.assertEqual(0, commit.returncode, commit.stdout + commit.stderr)

        # --- §7 Post-commit report: run the DOCUMENTED block ---
        # Executing SKILL.md's own commands rather than an equivalent is the
        # point: this is how the test caught that the documented report command
        # printed the deleted CJK path as "\346\272\220…", unreadable to the user
        # and not a path `git add --` would accept.
        self.assertNotEqual(head_before, self.git("rev-parse", "HEAD").stdout.strip())
        self.assertEqual(subject, self.git("log", "-1", "--format=%s").stdout.strip())
        self.assertIsNotNone(REPORT_BLOCK, "§7 report block not found in SKILL.md")
        report = self.bash(REPORT_BLOCK)
        self.assertEqual(0, report.returncode, report.stderr)
        self.assertIn(subject, report.stdout)
        self.assertIn("auth/session.go", report.stdout)
        self.assertIn("源码/旧模块.py", report.stdout,
                      "the report must show the deleted CJK path readably, not escaped")
        self.assertNotIn("\\346", report.stdout, "no octal-escaped paths in the report")
        self.assertNotIn("scratch.txt", report.stdout,
                         "untracked dirt must NOT be committed")


if __name__ == "__main__":
    unittest.main()