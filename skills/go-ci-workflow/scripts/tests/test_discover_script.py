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

    def test_empty_repo_exits_zero_with_no_output(self) -> None:
        proc = run_discovery(self.repo)
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertEqual("", proc.stdout)

    # --- shape-detection accuracy (probe must not over-classify) ---

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
            {"makefile-target", "repo-task", "container", "test-type", "config", "shape", "workflow", "tool"},
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