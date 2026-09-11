"""Integration tests: run the bundled script's gates against real git repos.

The golden fixtures describe decision scenarios (clean change, behind main,
planted secret, oversized PR); these tests build each scenario as an actual
git repository with a local bare ``origin`` and assert the gate verdicts the
script produces. No network, no GitHub — gates B/C/E and the confidence
mapping are pure git + filesystem, which is exactly what makes this cheap.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest import mock

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
        target = self.repo / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-m", msg)

    # --- golden 001: clean small change → all gates pass, confidence confirmed ---

    # --- Gate D coverage must track observed execution, not command spelling ---

    MARKER_MAKEFILE = """.PHONY: test lint build
test:
\t@echo ran > ran-test.marker
lint:
\t@echo ran > ran-lint.marker
build:
\t@echo ran > ran-build.marker
"""

    def _run_gate_d_with_make(self, command: str):
        """Run Gate D for real against a Makefile whose targets leave markers behind."""
        (self.repo / "Makefile").write_text(self.MARKER_MAKEFILE)
        (self.repo / "app.go").write_text("package main\n\nfunc App() {}\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-m", "feat: add app")
        settings = create_pr.resolve_settings(
            make_args(check_cmd=[command]), self.repo, "feature/make-modes"
        )
        ctx = create_pr.Context(
            repo=self.repo,
            base="main",
            branch="feature/make-modes",
            changed_files=[Path("app.go")],
        )
        result = create_pr.gate_d_quality(ctx, settings)
        markers = sorted(p.name for p in self.repo.glob("*.marker"))
        return result, ctx, markers

    def test_gate_d_credits_make_targets_that_really_run(self) -> None:
        git(self.repo, "checkout", "-b", "feature/make-modes")
        result, ctx, markers = self._run_gate_d_with_make("make test lint build")

        self.assertEqual(
            ["ran-build.marker", "ran-lint.marker", "ran-test.marker"],
            markers,
            "control case must actually execute all three targets",
        )
        self.assertEqual(create_pr.PASS, result.status, result.evidence)
        for dimension in create_pr.QUALITY_DIMENSIONS:
            self.assertTrue(ctx.quality_coverage[dimension].startswith("executed"))

    def test_gate_d_resolves_duplicate_assignments_like_the_shell(self) -> None:
        """Graded against real make, both directions, both assignment layers.

        Each row asserts the marker count first, so the verdict is checked against what
        actually ran rather than against my reading of the precedence rules.
        """
        rows = [
            ("MAKEFLAGS=s MAKEFLAGS=n make test lint build", 0, create_pr.SUPPRESSED),
            ("MAKEFLAGS=n MAKEFLAGS=s make test lint build", 3, create_pr.PASS),
            ("make MAKEFLAGS=s MAKEFLAGS=n test lint build", 0, create_pr.SUPPRESSED),
            ("make MAKEFLAGS=n MAKEFLAGS=s test lint build", 3, create_pr.PASS),
            ("MAKEFLAGS=n make MAKEFLAGS=s test lint build", 0, create_pr.SUPPRESSED),
            ("MAKEFLAGS=s make MAKEFLAGS=n test lint build", 0, create_pr.SUPPRESSED),
        ]
        for command, expected_markers, expected_status in rows:
            with self.subTest(command=command):
                self.setUp()
                git(self.repo, "checkout", "-b", "feature/make-modes")
                result, ctx, markers = self._run_gate_d_with_make(command)
                self.assertEqual(
                    expected_markers, len(markers), f"{command} executed {markers}"
                )
                self.assertEqual(expected_status, result.status, result.evidence)
                executed = [
                    d for d, v in ctx.quality_coverage.items() if v.startswith("executed")
                ]
                self.assertEqual(3 if expected_markers else 0, len(executed), ctx.quality_coverage)

    def test_gate_d_resolves_assignment_layers_against_the_environment(self) -> None:
        """A command-line assignment adds switches; a shell prefix replaces the value."""
        rows = [
            ("make MAKEFLAGS=s test lint build", "n", 0, create_pr.SUPPRESSED),
            ("make MAKEFLAGS=n test lint build", "s", 0, create_pr.SUPPRESSED),
            ("MAKEFLAGS=s make test lint build", "n", 3, create_pr.PASS),
            ("MAKEFLAGS= make test lint build", "n", 3, create_pr.PASS),
        ]
        for command, exported, expected_markers, expected_status in rows:
            with self.subTest(command=command, MAKEFLAGS=exported):
                self.setUp()
                git(self.repo, "checkout", "-b", "feature/make-modes")
                with mock.patch.dict(os.environ, {"MAKEFLAGS": exported}):
                    result, ctx, markers = self._run_gate_d_with_make(command)
                self.assertEqual(
                    expected_markers, len(markers),
                    f"{command} with MAKEFLAGS={exported} executed {markers}",
                )
                self.assertEqual(expected_status, result.status, result.evidence)

    def test_gate_d_does_not_credit_a_makeflags_assignment(self) -> None:
        """`MAKEFLAGS=n` is `make -n`, whether assigned on the command line or exported."""
        git(self.repo, "checkout", "-b", "feature/make-modes")
        result, ctx, markers = self._run_gate_d_with_make("make MAKEFLAGS=n test lint build")

        self.assertEqual([], markers, "precondition: MAKEFLAGS=n must execute nothing")
        self.assertEqual(create_pr.SUPPRESSED, result.status, result.evidence)
        for dimension in create_pr.QUALITY_DIMENSIONS:
            self.assertTrue(
                ctx.quality_coverage[dimension].startswith("uncovered"), ctx.quality_coverage
            )
        self.assertTrue(
            any("MAKEFLAGS=n" in d for d in result.details), result.details
        )

    def test_gate_d_does_not_credit_discovery_under_a_dry_run_environment(self) -> None:
        """The entry point with no command text at all: auto-discovery plus the env.

        `make test` / `make lint` / `make build` are discovered from the Makefile, and an
        exported MAKEFLAGS=n turns every one of them into a dry run.
        """
        git(self.repo, "checkout", "-b", "feature/make-modes")
        (self.repo / "Makefile").write_text(self.MARKER_MAKEFILE)
        (self.repo / "app.go").write_text("package main\n\nfunc App() {}\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-m", "feat: add app")

        with mock.patch.dict(os.environ, {"MAKEFLAGS": "n"}):
            settings = create_pr.resolve_settings(make_args(), self.repo, "feature/make-modes")
            ctx = create_pr.Context(
                repo=self.repo, base="main", branch="feature/make-modes",
                changed_files=[Path("app.go")],
            )
            result = create_pr.gate_d_quality(ctx, settings)

        self.assertEqual(
            [], sorted(p.name for p in self.repo.glob("*.marker")),
            "precondition: an exported MAKEFLAGS=n must execute nothing",
        )
        self.assertEqual(create_pr.SUPPRESSED, result.status, result.evidence)
        self.assertEqual("draft", create_pr.determine_pr_mode([result]))
        self.assertTrue(
            any("inherited MAKEFLAGS=n" in d for d in result.details), result.details
        )
        for dimension in ("test", "lint", "build"):
            self.assertTrue(
                ctx.quality_coverage[dimension].startswith("uncovered"), ctx.quality_coverage
            )

    def test_gate_d_credits_discovery_under_a_harmless_environment(self) -> None:
        """Control: MAKEFLAGS=s is silent, not a dry run — the targets really run."""
        git(self.repo, "checkout", "-b", "feature/make-modes")
        (self.repo / "Makefile").write_text(self.MARKER_MAKEFILE)
        (self.repo / "app.go").write_text("package main\n\nfunc App() {}\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-m", "feat: add app")

        with mock.patch.dict(os.environ, {"MAKEFLAGS": "s"}):
            settings = create_pr.resolve_settings(make_args(), self.repo, "feature/make-modes")
            ctx = create_pr.Context(
                repo=self.repo, base="main", branch="feature/make-modes",
                changed_files=[Path("app.go")],
            )
            result = create_pr.gate_d_quality(ctx, settings)

        self.assertEqual(
            ["ran-build.marker", "ran-lint.marker", "ran-test.marker"],
            sorted(p.name for p in self.repo.glob("*.marker")),
        )
        self.assertEqual(create_pr.PASS, result.status, result.evidence)
        self.assertEqual([], ctx.uncovered_risks)

    def test_gate_d_credits_a_command_that_clears_a_bad_environment(self) -> None:
        """`MAKEFLAGS= make …` deliberately clears the inherited value."""
        git(self.repo, "checkout", "-b", "feature/make-modes")
        with mock.patch.dict(os.environ, {"MAKEFLAGS": "n"}):
            result, ctx, markers = self._run_gate_d_with_make(
                "MAKEFLAGS= make test lint build"
            )

        self.assertEqual(3, len(markers), f"the cleared env must let make run: {markers}")
        self.assertEqual(create_pr.PASS, result.status, result.evidence)

    def test_gate_d_does_not_credit_a_bundled_dry_run_flag(self) -> None:
        """`make -sn test lint build` is `-s -n`: silent AND dry-run.

        Matching whole argument tokens misses the bundle, so coverage claimed three
        executed dimensions while no target ran.
        """
        git(self.repo, "checkout", "-b", "feature/make-modes")
        result, ctx, markers = self._run_gate_d_with_make("make -sn test lint build")

        self.assertEqual([], markers, "precondition: -sn must execute nothing")
        self.assertEqual(create_pr.SUPPRESSED, result.status, result.evidence)
        self.assertEqual("draft", create_pr.determine_pr_mode([result]))
        for dimension in create_pr.QUALITY_DIMENSIONS:
            self.assertTrue(
                ctx.quality_coverage[dimension].startswith("uncovered"),
                ctx.quality_coverage,
            )

    def test_gate_d_grades_value_bearing_bundles_by_execution(self) -> None:
        """Real make runs, graded by markers: `-sj2` executes, `-snj2` and `-nf…` do not.

        Every row is asserted against the marker files, so a verdict that disagrees with
        what actually ran fails regardless of how the flags are spelled.
        """
        rows = [
            ("make -sj2 test lint build", 3, create_pr.PASS),
            ("make -snj2 test lint build", 0, create_pr.SUPPRESSED),
            ("make -nf./Makefile test lint build", 0, create_pr.SUPPRESSED),
            ("make -nj2 test lint build", 0, create_pr.SUPPRESSED),
        ]
        for command, expected_markers, expected_status in rows:
            with self.subTest(command=command):
                self.setUp()  # fresh repo per row
                git(self.repo, "checkout", "-b", "feature/make-modes")
                result, ctx, markers = self._run_gate_d_with_make(command)
                self.assertEqual(
                    expected_markers, len(markers), f"{command} executed {markers}"
                )
                self.assertEqual(expected_status, result.status, result.evidence)
                executed_dimensions = [
                    d for d, v in ctx.quality_coverage.items() if v.startswith("executed")
                ]
                if expected_markers:
                    self.assertEqual(3, len(executed_dimensions), ctx.quality_coverage)
                else:
                    self.assertEqual([], executed_dimensions, ctx.quality_coverage)

    def test_gate_d_does_not_credit_a_declared_value_bearing_dry_run(self) -> None:
        """The same bundle through the explicit declaration entry point."""
        git(self.repo, "checkout", "-b", "feature/make-modes")
        (self.repo / "Makefile").write_text(self.MARKER_MAKEFILE)
        (self.repo / "app.go").write_text("package main\n\nfunc App() {}\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-m", "feat: add app")
        dry = "make -snj2 test lint build"
        settings = create_pr.resolve_settings(
            make_args(test_cmd=[dry], lint_cmd=[dry], build_cmd=[dry]),
            self.repo,
            "feature/make-modes",
        )
        ctx = create_pr.Context(
            repo=self.repo, base="main", branch="feature/make-modes",
            changed_files=[Path("app.go")],
        )
        result = create_pr.gate_d_quality(ctx, settings)

        self.assertEqual([], sorted(self.repo.glob("*.marker")))
        self.assertEqual(create_pr.SUPPRESSED, result.status, result.evidence)
        for dimension in create_pr.QUALITY_DIMENSIONS:
            self.assertIn("runs no check", ctx.quality_coverage[dimension])

    def test_gate_d_does_not_credit_a_declared_dry_run(self) -> None:
        """An explicit per-dimension declaration states intent, not execution.

        `quality.test_cmd` / `lint_cmd` / `build_cmd` pointing at `make -n …` must go
        through the same execution-mode check as a classified command.
        """
        git(self.repo, "checkout", "-b", "feature/make-modes")
        (self.repo / "Makefile").write_text(self.MARKER_MAKEFILE)
        (self.repo / "app.go").write_text("package main\n\nfunc App() {}\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-m", "feat: add app")
        dry = "make -n test lint build"
        settings = create_pr.resolve_settings(
            make_args(test_cmd=[dry], lint_cmd=[dry], build_cmd=[dry]),
            self.repo,
            "feature/make-modes",
        )
        ctx = create_pr.Context(
            repo=self.repo,
            base="main",
            branch="feature/make-modes",
            changed_files=[Path("app.go")],
        )
        result = create_pr.gate_d_quality(ctx, settings)

        self.assertEqual(
            [], sorted(p.name for p in self.repo.glob("*.marker")),
            "precondition: the declared command must execute nothing",
        )
        self.assertEqual(create_pr.SUPPRESSED, result.status, result.evidence)
        self.assertEqual("draft", create_pr.determine_pr_mode([result]))
        self.assertEqual(
            {"quality: test", "quality: lint", "quality: build"},
            {u["area"] for u in ctx.uncovered_risks},
        )
        for dimension in create_pr.QUALITY_DIMENSIONS:
            self.assertIn("declared via config", ctx.quality_coverage[dimension])
            self.assertIn("runs no check", ctx.quality_coverage[dimension])

    def test_gate_d_still_credits_a_declared_wrapper_that_runs(self) -> None:
        """A declaration is only refused when a run mode contradicts it."""
        git(self.repo, "checkout", "-b", "feature/make-modes")
        (self.repo / "Makefile").write_text(
            self.MARKER_MAKEFILE + "ci: test lint build\n"
        )
        (self.repo / "app.go").write_text("package main\n\nfunc App() {}\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-m", "feat: add app")
        settings = create_pr.resolve_settings(
            make_args(test_cmd=["make ci"], lint_cmd=["make ci"], build_cmd=["make ci"]),
            self.repo,
            "feature/make-modes",
        )
        ctx = create_pr.Context(
            repo=self.repo,
            base="main",
            branch="feature/make-modes",
            changed_files=[Path("app.go")],
        )
        result = create_pr.gate_d_quality(ctx, settings)

        self.assertEqual(
            ["ran-build.marker", "ran-lint.marker", "ran-test.marker"],
            sorted(p.name for p in self.repo.glob("*.marker")),
        )
        self.assertEqual(create_pr.PASS, result.status, result.evidence)
        self.assertEqual([], ctx.uncovered_risks)

    def test_gate_d_does_not_credit_a_make_dry_run(self) -> None:
        """`make -n test lint build` exits 0 having executed nothing."""
        git(self.repo, "checkout", "-b", "feature/make-modes")
        result, ctx, markers = self._run_gate_d_with_make("make -n test lint build")

        self.assertEqual([], markers, "precondition: a dry run must execute nothing")
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

    def test_requested_head_must_match_checked_out_branch(self) -> None:
        self.commit_on_feature(
            "feature/actual", "feature.go",
            "package main\n\nfunc Feature() {}\n",
            "feat: add feature",
        )
        ctx, settings = gate_env(self.repo, "feature/different")
        b = create_pr.gate_b_branch_sync(ctx, settings)
        self.assertEqual(create_pr.FAIL, b.status)
        self.assertTrue(b.blocks_publish)
        self.assertIn("does not match", b.evidence)

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

    # --- review finding 1: a secret that only exists inside the pushed history ---

    def test_secret_added_then_deleted_in_the_push_range_is_a_blocker(self) -> None:
        """The reviewer's scenario: commit 1 adds a token, commit 2 removes it.

        The net origin/main...HEAD diff is clean, but `git push` transmits both
        commits, so the token becomes reachable in the remote repository's history.
        """
        git(self.repo, "checkout", "-b", "feature/leak-then-remove")
        target = self.repo / "config.go"
        target.write_text(
            'package main\n\nvar token = "ghp_abcdefghijklmnopqrstuvwxyz0123456789"\n'
        )
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-m", "feat: add config")
        target.write_text('package main\n\nfunc Config() string { return "ok" }\n')
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-m", "fix: drop inline literal")

        # Precondition: HEAD is clean, so a net-diff-only scan sees nothing.
        self.assertNotIn("ghp_", (self.repo / "config.go").read_text())
        self.assertEqual(
            "2", git(self.repo, "rev-list", "--count", "origin/main..HEAD").strip()
        )

        ctx, settings = gate_env(self.repo, "feature/leak-then-remove")
        e = create_pr.gate_e_security(ctx, settings)
        self.assertEqual(create_pr.FAIL, e.status, e.evidence)
        self.assertTrue(e.blocks_publish)
        self.assertIn("secret scan matched", e.evidence)
        self.assertTrue(
            any("[github_pat]" in d and "(commit " in d for d in e.details),
            f"finding must name the commit that introduced it: {e.details}",
        )

    def test_binary_sensitive_file_in_the_push_range_is_a_blocker(self) -> None:
        """A binary patch carries no `+++` header, so paths must come from git, not the patch.

        commit 1 adds a NUL-containing client.p12, commit 2 deletes it: HEAD is clean
        and the patch text names no path, yet the keystore is still pushed.
        """
        git(self.repo, "checkout", "-b", "feature/binary-cert")
        certs = self.repo / "certs"
        certs.mkdir()
        keystore = certs / "client.p12"
        keystore.write_bytes(bytes([0x30, 0x82, 0x04, 0x00]) + b"\x00binary\x00payload" * 8)
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-m", "feat: add client keystore")
        keystore.unlink()
        (self.repo / "svc.go").write_text("package main\n\nfunc Svc() {}\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-m", "fix: load keystore from secret manager")

        ctx, settings = gate_env(self.repo, "feature/binary-cert")
        e = create_pr.gate_e_security(ctx, settings)
        self.assertEqual(create_pr.FAIL, e.status, e.evidence)
        self.assertTrue(e.blocks_publish)
        self.assertTrue(
            any("certs/client.p12" in d and "sensitive_filename" in d for d in e.details),
            f"binary keystore must be named in the findings: {e.details}",
        )

    def test_empty_sensitive_file_in_the_push_range_is_a_blocker(self) -> None:
        """An empty new file produces a patch with no hunk and no `+++` line either."""
        git(self.repo, "checkout", "-b", "feature/empty-key")
        (self.repo / "id_rsa").write_bytes(b"")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-m", "feat: add key placeholder")
        (self.repo / "id_rsa").unlink()
        (self.repo / "keys.go").write_text("package main\n\nfunc Keys() {}\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-m", "fix: drop key placeholder")

        ctx, settings = gate_env(self.repo, "feature/empty-key")
        e = create_pr.gate_e_security(ctx, settings)
        self.assertEqual(create_pr.FAIL, e.status, e.evidence)
        self.assertTrue(any("id_rsa" in d for d in e.details), e.details)

    def test_renamed_sensitive_file_in_the_push_range_is_a_blocker(self) -> None:
        """A pure rename has no `+++` header; here the risky name exists only mid-range."""
        git(self.repo, "checkout", "-b", "feature/rename-cert")
        (self.repo / "notes.txt").write_text("harmless\n" * 10)
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-m", "feat: add notes")
        git(self.repo, "mv", "notes.txt", "server.pem")
        git(self.repo, "commit", "-m", "refactor: rename notes file")
        git(self.repo, "mv", "server.pem", "notes.txt")
        git(self.repo, "commit", "-m", "refactor: restore notes file name")

        # Precondition: server.pem is gone from HEAD and from the net diff.
        self.assertFalse((self.repo / "server.pem").exists())
        net = git(self.repo, "diff", "--name-only", "origin/main...HEAD")
        self.assertNotIn("server.pem", net)

        ctx, settings = gate_env(self.repo, "feature/rename-cert")
        e = create_pr.gate_e_security(ctx, settings)
        self.assertEqual(create_pr.FAIL, e.status, e.evidence)
        self.assertTrue(any("server.pem" in d for d in e.details), e.details)

    def test_non_ascii_path_is_still_content_scanned(self) -> None:
        """git renders a non-ASCII path as an escaped display form by default.

        The escaped name never matches the path parsed from the patch, so the whole
        file silently drops out of the content scan.
        """
        self.commit_on_feature(
            "feature/cjk-config", "配置.go",
            'package main\n\nvar password = "prod-credential-9981-zzz"\n',
            "feat: add config",
        )
        ctx, settings = gate_env(self.repo, "feature/cjk-config")
        e = create_pr.gate_e_security(ctx, settings)
        self.assertEqual(create_pr.FAIL, e.status, e.evidence)
        self.assertTrue(
            any("配置.go" in d for d in e.details),
            f"finding must name the real path, not an escaped form: {e.details}",
        )
        self.assertFalse(
            any("\\351" in d for d in e.details), f"escaped display form leaked: {e.details}"
        )

    def test_sensitive_filename_added_then_deleted_in_the_push_range_is_a_blocker(self) -> None:
        git(self.repo, "checkout", "-b", "feature/transient-dotenv")
        env_file = self.repo / ".env"
        env_file.write_text("PASSWORD=supersecretpassword\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-m", "feat: add runtime config")
        env_file.unlink()
        (self.repo / "runtime.go").write_text("package main\n\nfunc Runtime() {}\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-m", "fix: read runtime config from env")

        ctx, settings = gate_env(self.repo, "feature/transient-dotenv")
        e = create_pr.gate_e_security(ctx, settings)
        self.assertEqual(create_pr.FAIL, e.status, e.evidence)
        self.assertTrue(e.blocks_publish)
        self.assertTrue(any("sensitive_filename" in d for d in e.details), e.details)

    def test_multi_commit_clean_branch_records_range_scan_evidence(self) -> None:
        git(self.repo, "checkout", "-b", "feature/two-clean-commits")
        (self.repo / "a.go").write_text("package main\n\nfunc A() {}\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-m", "feat: add a")
        (self.repo / "b.go").write_text("package main\n\nfunc B() {}\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-m", "feat: add b")

        ctx, settings = gate_env(self.repo, "feature/two-clean-commits")
        e = create_pr.gate_e_security(ctx, settings)
        self.assertEqual(create_pr.PASS, e.status, e.evidence)
        self.assertTrue(
            any("push range scan: 2 commit(s)" in d for d in e.details),
            f"gate must state how much history it actually read: {e.details}",
        )

    def test_list_changed_files_returns_real_paths_not_display_forms(self) -> None:
        """`ctx.changed_files` feeds module detection and the PR body, so it must be exact.

        Without `-z` git renders these names in its escaped/quoted display form, which
        then reaches the body and `detect_affected_go_modules` as a path that does not
        exist on disk.
        """
        git(self.repo, "checkout", "-b", "feature/odd-listing")
        names = ["配置.go", 'q"uote.go', "back\\slash.go", "we\nird.go", "a b.go"]
        for name in names:
            (self.repo / name).write_text("package main\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-m", "feat: add oddly named files")

        files, cmd = create_pr.list_changed_files(self.repo, "main", 60)
        self.assertEqual(0, cmd.rc, cmd.stderr)
        self.assertEqual(sorted(names), sorted(str(f) for f in files))
        for path in files:
            self.assertTrue((self.repo / path).exists(), f"path is not usable on disk: {path!r}")

    def test_oddly_named_sensitive_file_only_in_history_is_a_blocker(self) -> None:
        """Per-commit path enumeration must survive a filename containing a newline."""
        git(self.repo, "checkout", "-b", "feature/odd-history")
        risky = "we\nird.pem"
        (self.repo / risky).write_text("-----BEGIN CERTIFICATE-----\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-m", "feat: add certificate")
        (self.repo / risky).unlink()
        (self.repo / "tls.go").write_text("package main\n\nfunc TLS() {}\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-m", "fix: load certificate from secret manager")

        net = git(self.repo, "diff", "--name-only", "origin/main...HEAD")
        self.assertNotIn("ird.pem", net)

        ctx, settings = gate_env(self.repo, "feature/odd-history")
        e = create_pr.gate_e_security(ctx, settings)
        self.assertEqual(create_pr.FAIL, e.status, e.evidence)
        self.assertTrue(
            any("ird.pem" in d and "sensitive_filename" in d for d in e.details), e.details
        )

    def test_paths_needing_quoting_are_still_content_scanned(self) -> None:
        """git C-quotes a path containing a quote, a backslash, or a newline.

        The quoted form appears in the patch header too, so it must be decoded; the
        name list must be read NUL-separated, because a newline in a filename cannot
        be split on newlines.
        """
        git(self.repo, "checkout", "-b", "feature/odd-names")
        names = ['a b.go', 'q"uote.go', "back\\slash.go", "we\nird.go"]
        for name in names:
            (self.repo / name).write_text(
                'package main\n\nvar password = "prod-credential-9981-zzz"\n'
            )
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-m", "feat: add oddly named files")

        ctx, settings = gate_env(self.repo, "feature/odd-names")
        e = create_pr.gate_e_security(ctx, settings)
        self.assertEqual(create_pr.FAIL, e.status, e.evidence)
        findings = [d for d in e.details if "generic_secret" in d]
        self.assertEqual(
            len(names),
            len(findings),
            f"every oddly named file must be scanned, got: {findings}",
        )

    def test_env_reference_is_not_flagged(self) -> None:
        self.commit_on_feature(
            "feature/env-config", "config.go",
            'package main\n\nimport "os"\n\nvar token = os.Getenv("API_TOKEN")\n',
            "feat: read token from env",
        )
        ctx, settings = gate_env(self.repo, "feature/env-config")
        e = create_pr.gate_e_security(ctx, settings)
        self.assertEqual(create_pr.PASS, e.status, e.evidence)

    def test_dotenv_filename_is_a_secret_blocker(self) -> None:
        self.commit_on_feature(
            "feature/leaky-dotenv", ".env",
            "PASSWORD=supersecretpassword\n",
            "feat: add runtime config",
        )
        ctx, settings = gate_env(self.repo, "feature/leaky-dotenv")
        e = create_pr.gate_e_security(ctx, settings)
        self.assertEqual(create_pr.FAIL, e.status)
        self.assertTrue(e.blocks_publish)
        self.assertTrue(any("sensitive_filename" in detail for detail in e.details))

    def test_secret_in_docs_comment_is_a_blocker(self) -> None:
        self.commit_on_feature(
            "docs/leaky-runbook", "docs/runbook.md",
            "# Emergency credential\n# password = supersecretpassword\n",
            "docs: add recovery runbook",
        )
        ctx, settings = gate_env(self.repo, "docs/leaky-runbook")
        e = create_pr.gate_e_security(ctx, settings)
        self.assertEqual(create_pr.FAIL, e.status)
        self.assertTrue(any("docs/runbook.md" in detail for detail in e.details))

    def test_deleting_sensitive_file_is_not_a_new_secret_finding(self) -> None:
        (self.repo / ".env").write_text("PASSWORD=supersecretpassword\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-m", "chore: add legacy config")
        git(self.repo, "push", "origin", "main")
        git(self.repo, "checkout", "-b", "fix/remove-legacy-config")
        (self.repo / ".env").unlink()
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-m", "fix: remove legacy config")

        ctx, settings = gate_env(self.repo, "fix/remove-legacy-config")
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

    def test_gate_g_rejects_user_supplied_non_conventional_title(self) -> None:
        self.commit_on_feature(
            "feature/title-check", "title.go",
            "package main\n\nfunc Title() {}\n",
            "feat: add title check",
        )
        settings = create_pr.resolve_settings(
            make_args(title="random title", confirm_self_review=True),
            self.repo,
            "feature/title-check",
        )
        ctx = create_pr.Context(repo=self.repo, base=settings.base, branch=settings.branch)
        g = create_pr.gate_g_commit_hygiene(ctx, settings)
        self.assertEqual(create_pr.FAIL, g.status)
        self.assertTrue(g.blocks_publish)
        self.assertIn("PR title", g.evidence)

    def test_gate_g_requires_explicit_scope_and_self_review_confirmation(self) -> None:
        self.commit_on_feature(
            "feature/self-review", "review.go",
            "package main\n\nfunc Review() {}\n",
            "feat: add review helper",
        )
        settings = create_pr.resolve_settings(
            make_args(title="feat: add review helper"),
            self.repo,
            "feature/self-review",
        )
        ctx = create_pr.Context(repo=self.repo, base=settings.base, branch=settings.branch)
        g = create_pr.gate_g_commit_hygiene(ctx, settings)
        self.assertEqual(create_pr.SUPPRESSED, g.status)
        self.assertTrue(g.blocks_ready)
        self.assertIn("self-review", g.evidence)

    def test_gate_g_rejects_commit_body_lines_over_72_characters(self) -> None:
        git(self.repo, "checkout", "-b", "feature/long-body")
        (self.repo / "body.go").write_text("package main\n\nfunc Body() {}\n")
        git(self.repo, "add", "-A")
        git(
            self.repo,
            "commit",
            "-m",
            "feat: add body helper",
            "-m",
            "x" * 73,
        )
        settings = create_pr.resolve_settings(
            make_args(title="feat: add body helper", confirm_self_review=True),
            self.repo,
            "feature/long-body",
        )
        ctx = create_pr.Context(repo=self.repo, base=settings.base, branch=settings.branch)
        g = create_pr.gate_g_commit_hygiene(ctx, settings)
        self.assertEqual(create_pr.FAIL, g.status)
        self.assertIn("72", g.evidence)


if __name__ == "__main__":
    unittest.main()
