"""Behavioral tests for scripts/discover_ci_needs.sh against real fixture repos.

The script is a probe: most probes are EXPECTED to find nothing. These tests
exist because the original version used `set -euo pipefail` and died mid-run
on any repo whose Makefile lacked ci targets or that had no scripts/
directory — emitting truncated TSV that a caller could mistake for a
complete discovery. Every scenario asserts exit code 0 AND output content.
"""

import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "discover_ci_needs.sh"


def run_discovery(repo: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(SCRIPT), str(repo)],
        capture_output=True,
        text=True,
        timeout=30,
    )


def tsv_rows(proc: subprocess.CompletedProcess) -> list[tuple[str, ...]]:
    return [tuple(line.split("\t")) for line in proc.stdout.splitlines() if line]


class DiscoverScriptTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = Path(self._tmp.name)

    # --- regression: the three repo shapes that killed the set -e version ---

    def test_makefile_without_ci_targets_survives(self) -> None:
        (self.repo / "Makefile").write_text("build:\n\techo hi\n")
        proc = run_discovery(self.repo)
        self.assertEqual(0, proc.returncode, proc.stderr)
        rows = tsv_rows(proc)
        self.assertFalse(
            any(r[0] == "makefile-target" for r in rows),
            "a Makefile without ci targets must yield no makefile-target rows",
        )

    def test_repo_without_scripts_dir_runs_all_probes(self) -> None:
        (self.repo / "Makefile").write_text("ci:\n\techo ok\ndocker-build:\n\techo d\n")
        (self.repo / "go.mod").write_text("module x\n\ngo 1.22\n")
        proc = run_discovery(self.repo)
        self.assertEqual(0, proc.returncode, proc.stderr)
        rows = tsv_rows(proc)
        categories = {r[0] for r in rows}
        # Probes AFTER the scripts/ probe must still have run (the original
        # bug truncated output here).
        self.assertIn(("makefile-target", "ci", "Makefile"), rows)
        self.assertIn(("shape", "single-root-module", "go.mod"), rows)
        self.assertIn("config", categories, "go-version probe must run")

    def test_gomod_only_repo_reports_shape(self) -> None:
        (self.repo / "go.mod").write_text("module y\n\ngo 1.22\n")
        proc = run_discovery(self.repo)
        self.assertEqual(0, proc.returncode, proc.stderr)
        rows = tsv_rows(proc)
        self.assertIn(("shape", "single-root-module", "go.mod"), rows)
        self.assertIn(("config", "go-version", "go.mod (1.22)"), rows)

    def test_empty_repo_emits_only_the_completion_marker(self) -> None:
        """An empty repo must be distinguishable from a crash on line 1.

        The old contract was `stdout == ""`, which is exactly the fail-silent
        shape: "nothing found" and "died before producing anything" were
        byte-identical, and a caller had no positive signal that the probe ran
        at all. The script now always terminates with
        `meta<TAB>probe-complete<TAB>ok`, so absence of that line means a
        partial run."""
        proc = run_discovery(self.repo)
        self.assertEqual(0, proc.returncode, proc.stderr)
        rows = tsv_rows(proc)
        self.assertEqual([("meta", "probe-complete", "ok")], rows)

    def test_every_successful_run_ends_with_the_completion_marker(self) -> None:
        (self.repo / "go.mod").write_text("module x\n\ngo 1.23\n")
        (self.repo / "Makefile").write_text("ci:\n\techo ok\n")
        proc = run_discovery(self.repo)
        self.assertEqual(0, proc.returncode, proc.stderr)
        lines = [line for line in proc.stdout.splitlines() if line]
        self.assertEqual("meta\tprobe-complete\tok", lines[-1],
                         "completion marker must be the LAST line, or a truncated "
                         "run cannot be told from a complete one")

    # --- shape-detection accuracy (probe must not over-classify) ---

    def test_git_internals_are_never_cited_as_the_entrypoint(self) -> None:
        """`.git/` is in the prune list; the package-main probe once had its own
        hand-written copy that omitted it, so a blob checked out under `.git/`
        was reported as the application entrypoint."""
        (self.repo / "go.mod").write_text("module lib\n\ngo 1.23\n")
        stray = self.repo / ".git" / "x"
        stray.mkdir(parents=True)
        (stray / "leftover.go").write_text("package main\n\nfunc main() {}\n")
        proc = run_discovery(self.repo)
        self.assertEqual(0, proc.returncode, proc.stderr)
        rows = tsv_rows(proc)
        self.assertIn(("shape", "likely-library-or-unknown", "no package main found"), rows)
        for row in rows:
            self.assertNotIn(".git", row[2], f"pruned tree cited as evidence: {row}")

    def test_apostrophe_in_a_path_does_not_zero_the_tool_probe(self) -> None:
        """BSD xargs treats `'` as a quote character. One such directory
        ANYWHERE aborted the whole tool probe with "unterminated quote" — the
        clean root Makefile's tools were lost too, with exit 0 and (stderr
        being discarded) no diagnostic at all."""
        (self.repo / "go.mod").write_text("module x\n\ngo 1.23\n")
        (self.repo / "Makefile").write_text("ci:\n\tfieldalignment ./...\n")
        odd = self.repo / "john's dir"
        odd.mkdir()
        (odd / "Makefile").write_text("ci:\n\tnilaway ./...\n")
        proc = run_discovery(self.repo)
        self.assertEqual(0, proc.returncode, proc.stderr)
        rows = tsv_rows(proc)
        self.assertIn(("tool", "fieldalignment", "repo-scan"), rows)
        self.assertIn(("tool", "nilaway", "repo-scan"), rows)

    def test_unreadable_directory_does_not_produce_a_confident_verdict(self) -> None:
        """A permission-denied path is not evidence of absence.

        Every probe discarded stderr, so unreadable and absent were
        indistinguishable: an unreadable `cmd/` flipped the shape from
        `likely-application` to `likely-library-or-unknown` — a confidently
        WRONG answer feeding Gate 1, not an under-report."""
        (self.repo / "go.mod").write_text("module app\n\ngo 1.23\n")
        cmd = self.repo / "cmd" / "app"
        cmd.mkdir(parents=True)
        (cmd / "main.go").write_text("package main\n\nfunc main() {}\n")

        rows = tsv_rows(run_discovery(self.repo))
        self.assertIn(("shape", "likely-application", "cmd/app/main.go"), rows)

        (self.repo / "cmd").chmod(0o000)
        self.addCleanup(lambda: (self.repo / "cmd").chmod(0o755))
        proc = run_discovery(self.repo)
        self.assertEqual(0, proc.returncode, proc.stderr)
        rows = tsv_rows(proc)
        shapes = {r[1] for r in rows if r[0] == "shape"}
        self.assertNotIn("likely-library-or-unknown", shapes,
                         "an unreadable tree must not yield a confident library verdict")
        self.assertIn("undetermined", shapes)
        self.assertTrue(any(r[:2] == ("meta", "partial-scan") for r in rows),
                        "a degraded scan must say so")

    def test_empty_and_dash_arguments_are_rejected(self) -> None:
        """`${1:-.}` treated "" as unset and scanned the CWD, producing a full,
        plausible report of the wrong repository. `-` reached bash's `cd -`
        (which `--` does not prevent) and scanned $OLDPWD."""
        for bad in ("", "-"):
            proc = subprocess.run(["bash", str(SCRIPT), bad],
                                  capture_output=True, text=True, timeout=30)
            self.assertEqual(2, proc.returncode, f"{bad!r} was accepted as a root")
            self.assertEqual("", proc.stdout, f"{bad!r} produced a report")

    def test_gnumakefile_targets_are_found(self) -> None:
        """GNU make prefers GNUmakefile over Makefile; `-name Makefile` is an
        exact match and does not case-fold even on a case-insensitive volume,
        so such a repo reported zero targets."""
        (self.repo / "go.mod").write_text("module x\n\ngo 1.23\n")
        (self.repo / "GNUmakefile").write_text("ci:\n\tgosec ./...\n")
        rows = tsv_rows(run_discovery(self.repo))
        self.assertIn(("makefile-target", "ci", "GNUmakefile"), rows)
        self.assertIn(("tool", "gosec", "repo-scan"), rows)

    def test_vendored_go_mod_does_not_trigger_multi_module(self) -> None:
        """A vendored dependency's go.mod must not read as a nested module."""
        (self.repo / "go.mod").write_text("module app\n\ngo 1.23\n")
        vendor = self.repo / "vendor" / "github.com" / "x" / "y"
        vendor.mkdir(parents=True)
        (vendor / "go.mod").write_text("module y\n\ngo 1.20\n")
        proc = run_discovery(self.repo)
        self.assertEqual(0, proc.returncode, proc.stderr)
        rows = tsv_rows(proc)
        self.assertIn(("shape", "single-root-module", "go.mod"), rows)
        self.assertNotIn(("shape", "multi-module", "find go.mod"), rows)
        # the vendored go.mod must not appear as a discovered module version
        self.assertFalse(
            any(r[0] == "config" and r[1] == "go-version" and "vendor/" in r[2] for r in rows),
            "vendored go.mod leaked into go-version discovery",
        )

    def test_dependency_trees_leak_into_no_probe(self) -> None:
        """Pruning must apply to EVERY probe, not just the go.mod one.

        Regression: pruning was added to the module probe only, so a repo with
        `vendor/` reported its dependencies' `ci:` targets and their
        `test/integration` directories as first-party CI needs — feeding the
        Local Parity Gate targets the repo cannot actually run.
        """
        (self.repo / "go.mod").write_text("module app\n\ngo 1.23\n")
        (self.repo / "Makefile").write_text("ci:\n\techo real\n")

        dep = self.repo / "vendor" / "github.com" / "dep"
        (dep / "test" / "integration").mkdir(parents=True)
        (dep / "Makefile").write_text("ci:\n\techo VENDORED\nci-deploy:\n\techo x\n")
        nm = self.repo / "node_modules" / "pkg"
        nm.mkdir(parents=True)
        (nm / "Makefile").write_text("docker-build:\n\techo NODEMODULES\n")
        (nm / "Dockerfile").write_text("FROM scratch\n")

        proc = run_discovery(self.repo)
        self.assertEqual(0, proc.returncode, proc.stderr)
        rows = tsv_rows(proc)

        self.assertIn(("makefile-target", "ci", "Makefile"), rows)
        for row in rows:
            for field in row:
                self.assertNotIn("vendor/", field, f"vendored tree leaked: {row}")
                self.assertNotIn("node_modules/", field, f"dependency tree leaked: {row}")
        self.assertFalse(
            any(r[0] == "makefile-target" and r[1] == "ci-deploy" for r in rows),
            "a vendored Makefile target was reported as a first-party CI target",
        )

    def test_monorepo_dockerfiles_below_depth_two_are_found(self) -> None:
        """`services/<app>/Dockerfile` and `cmd/<app>/Dockerfile` are the
        canonical monorepo layout this skill documents. A -maxdepth 2 probe
        reported ZERO containers for them, so the docker-build job was silently
        dropped for exactly the shape the skill emphasises.
        """
        (self.repo / "go.mod").write_text("module app\n\ngo 1.23\n")
        for sub in ("services/api", "cmd/gateway", "deployments/docker/worker"):
            (self.repo / sub).mkdir(parents=True)
            (self.repo / sub / "Dockerfile").write_text("FROM scratch\n")

        proc = run_discovery(self.repo)
        self.assertEqual(0, proc.returncode, proc.stderr)
        found = {r[1] for r in tsv_rows(proc) if r[0] == "container"}
        self.assertEqual(
            {
                "services/api/Dockerfile",
                "cmd/gateway/Dockerfile",
                "deployments/docker/worker/Dockerfile",
            },
            found,
        )

    def test_go_workspace_detected(self) -> None:
        (self.repo / "go.work").write_text("go 1.23\n\nuse (\n  .\n  ./svc/api\n)\n")
        (self.repo / "go.mod").write_text("module root\n\ngo 1.23\n")
        api = self.repo / "svc" / "api"
        api.mkdir(parents=True)
        (api / "go.mod").write_text("module root/api\n\ngo 1.23\n")
        proc = run_discovery(self.repo)
        self.assertEqual(0, proc.returncode, proc.stderr)
        rows = tsv_rows(proc)
        self.assertIn(("shape", "go-workspace", "go.work"), rows)
        self.assertIn(("shape", "multi-module", "find go.mod"), rows)

    def test_toolchain_directive_detected(self) -> None:
        (self.repo / "go.mod").write_text("module app\n\ngo 1.23\n\ntoolchain go1.23.4\n")
        proc = run_discovery(self.repo)
        self.assertEqual(0, proc.returncode, proc.stderr)
        rows = tsv_rows(proc)
        self.assertIn(("config", "toolchain", "go.mod (go1.23.4)"), rows)

    def test_application_heuristic_flags_package_main(self) -> None:
        (self.repo / "go.mod").write_text("module app\n\ngo 1.23\n")
        (self.repo / "main.go").write_text("package main\n\nfunc main() {}\n")
        proc = run_discovery(self.repo)
        rows = tsv_rows(proc)
        self.assertIn(("shape", "likely-application", "main.go"), rows)

    def test_library_heuristic_when_no_package_main(self) -> None:
        (self.repo / "go.mod").write_text("module lib\n\ngo 1.23\n")
        (self.repo / "lib.go").write_text("package lib\n\nfunc F() {}\n")
        proc = run_discovery(self.repo)
        rows = tsv_rows(proc)
        self.assertIn(("shape", "likely-library-or-unknown", "no package main found"), rows)

    # --- full-featured repo: every probe category fires ---

    def test_rich_repo_fires_all_categories(self) -> None:
        (self.repo / "scripts").mkdir()
        (self.repo / ".github" / "workflows").mkdir(parents=True)
        (self.repo / "tests" / "integration").mkdir(parents=True)
        (self.repo / "tests" / "e2e").mkdir(parents=True)
        (self.repo / "svc" / "api").mkdir(parents=True)
        (self.repo / "Makefile").write_text(
            "ci:\n\techo ok\nci-e2e:\n\techo e\ndocker-build:\n\techo d\nlint:\n\tgolangci-lint run\n"
        )
        (self.repo / "go.mod").write_text("module rich\n\ngo 1.22\n")
        (self.repo / "svc" / "api" / "go.mod").write_text("module rich/api\n\ngo 1.23\n")
        (self.repo / "scripts" / "sec.sh").write_text("gosec ./...\n")
        (self.repo / "Dockerfile").write_text("FROM scratch\n")
        (self.repo / ".golangci.yml").write_text("run: {}\n")
        (self.repo / ".github" / "workflows" / "old.yml").write_text("name: old\n")

        proc = run_discovery(self.repo)
        self.assertEqual(0, proc.returncode, proc.stderr)
        rows = tsv_rows(proc)
        categories = {r[0] for r in rows}
        self.assertEqual(
            {"makefile-target", "repo-task", "container", "test-type", "config",
             "shape", "workflow", "tool", "meta"},
            categories,
        )
        self.assertIn(("makefile-target", "ci-e2e", "Makefile"), rows)
        self.assertIn(("repo-task", "script", "scripts/sec.sh"), rows)
        self.assertIn(("test-type", "e2e", "tests/e2e"), rows)
        self.assertIn(("shape", "multi-module", "find go.mod"), rows)
        self.assertIn(("config", "go-version", "svc/api/go.mod (1.23)"), rows)
        self.assertIn(("tool", "gosec", "repo-scan"), rows)
        self.assertIn(("tool", "golangci-lint", "repo-scan"), rows)
        self.assertIn(("workflow", "old.yml", ".github/workflows/old.yml"), rows)

    # --- output contract ---

    def test_every_output_row_has_three_tsv_fields(self) -> None:
        (self.repo / "Makefile").write_text("ci:\n\techo ok\n")
        (self.repo / "go.mod").write_text("module x\n\ngo 1.22\n")
        proc = run_discovery(self.repo)
        self.assertEqual(0, proc.returncode)
        for row in tsv_rows(proc):
            self.assertEqual(3, len(row), f"row is not 3-field TSV: {row}")

    def test_bad_root_exits_two(self) -> None:
        proc = run_discovery(self.repo / "does-not-exist")
        self.assertEqual(2, proc.returncode)
        self.assertEqual("", proc.stdout)


if __name__ == "__main__":
    unittest.main()