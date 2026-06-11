"""Behavioral tests for this skill's executable assets.

The 71 prior tests were all wording-level: none ever executed `make` against
the golden Makefiles or ran the discovery script. A broken tab, a typo'd
target reference, or the probe-script `set -e` bug (a repo without cmd/
killed the script before its own "no entrypoints" branch — see git history)
would keep every test green. These tests run the real binaries.

Requires `make` and `bash` on PATH (both are hard prerequisites of the
skill's domain, so no skip logic).
"""

import subprocess
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[2]
GOLDEN_DIR = SKILL_DIR / "references" / "golden"
DISCOVER = SKILL_DIR / "scripts" / "discover_go_entrypoints.sh"


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=30)


class GoldenMakefileExecutionTests(unittest.TestCase):
    """Golden Makefiles must execute with real make, not just read well."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.proj = Path(self._tmp.name)
        (self.proj / "cmd" / "api").mkdir(parents=True)
        (self.proj / "cmd" / "api" / "main.go").write_text("package main\n\nfunc main() {}\n")
        (self.proj / "go.mod").write_text("module fixture\n\ngo 1.22\n")

    def _install(self, golden_name: str) -> None:
        makefile = (GOLDEN_DIR / golden_name).read_text()
        (self.proj / "Makefile").write_text(makefile)

    def test_simple_help_renders_documented_targets(self) -> None:
        self._install("simple-project.mk")
        proc = run(["make", "help"], self.proj)
        self.assertEqual(0, proc.returncode, proc.stderr)
        for target in ("build-api", "test", "lint", "ci", "cover-check", "clean"):
            self.assertIn(target, proc.stdout, f"help missing target: {target}")

    def test_simple_build_api_dry_run_has_ldflags_and_bin_path(self) -> None:
        self._install("simple-project.mk")
        proc = run(["make", "-n", "build-api"], self.proj)
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertIn("-X main.version=", proc.stdout, "ldflags version injection missing")
        self.assertIn("-X main.commit=", proc.stdout)
        self.assertIn("-o bin/api", proc.stdout, "artifact must land in bin/")
        self.assertIn("./cmd/api", proc.stdout)

    def test_simple_test_target_uses_race(self) -> None:
        self._install("simple-project.mk")
        proc = run(["make", "-n", "test"], self.proj)
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertIn("-race", proc.stdout)

    def test_complex_help_renders_multi_binary_targets(self) -> None:
        self._install("complex-project.mk")
        proc = run(["make", "help"], self.proj)
        self.assertEqual(0, proc.returncode, proc.stderr)
        for target in (
            "build-api",
            "build-consumer-sync",
            "build-cron-cleanup",
            "build-migrate",
            "docker-build",
        ):
            self.assertIn(target, proc.stdout, f"help missing target: {target}")

    def test_complex_cross_compile_sets_cgo_disabled(self) -> None:
        self._install("complex-project.mk")
        proc = run(["make", "-n", "build-linux"], self.proj)
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertIn("CGO_ENABLED=0", proc.stdout,
                      "cross-compilation without CGO_ENABLED=0 is a listed anti-pattern")

    def test_complex_consumer_target_maps_cmd_path_semantics(self) -> None:
        self._install("complex-project.mk")
        proc = run(["make", "-n", "build-consumer-sync"], self.proj)
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertIn("./cmd/consumer/sync", proc.stdout)


class DiscoverScriptTests(unittest.TestCase):
    """The probe script must treat 'nothing found' as success, not death."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = Path(self._tmp.name)

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", str(DISCOVER), *args, str(self.repo)],
            capture_output=True,
            text=True,
            timeout=30,
        )

    def test_repo_without_cmd_dir_exits_zero_with_message(self) -> None:
        proc = self._run()
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertEqual("", proc.stdout)
        self.assertIn("No cmd/**/main.go entrypoints found", proc.stderr)

    def test_empty_cmd_dir_exits_zero_with_message(self) -> None:
        (self.repo / "cmd").mkdir()
        proc = self._run()
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertIn("No cmd/**/main.go entrypoints found", proc.stderr)

    def test_entrypoints_classified_with_kind_and_target(self) -> None:
        for d in ("cmd/api", "cmd/consumer/sync", "cmd/cron/cleanup", "cmd/mytool"):
            (self.repo / d).mkdir(parents=True)
            (self.repo / d / "main.go").write_text("package main\n")
        proc = self._run()
        self.assertEqual(0, proc.returncode, proc.stderr)
        rows = [tuple(line.split("\t")) for line in proc.stdout.splitlines()]
        self.assertIn(("api", "api", "api", "cmd/api"), rows)
        self.assertIn(("consumer", "sync", "consumer-sync", "cmd/consumer/sync"), rows)
        self.assertIn(("cron", "cleanup", "cron-cleanup", "cmd/cron/cleanup"), rows)
        self.assertIn(("other", "mytool", "mytool", "cmd/mytool"), rows)
        for row in rows:
            self.assertEqual(4, len(row), f"row is not 4-field TSV: {row}")

    def test_json_mode_emits_parseable_objects(self) -> None:
        import json

        (self.repo / "cmd" / "api").mkdir(parents=True)
        (self.repo / "cmd" / "api" / "main.go").write_text("package main\n")
        proc = self._run("--json")
        self.assertEqual(0, proc.returncode, proc.stderr)
        objs = [json.loads(line) for line in proc.stdout.splitlines()]
        self.assertEqual(1, len(objs))
        self.assertEqual(
            {"kind": "api", "name": "api", "target": "api", "dir": "cmd/api"}, objs[0]
        )

    def test_bad_root_exits_two(self) -> None:
        proc = subprocess.run(
            ["bash", str(DISCOVER), str(self.repo / "missing")],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(2, proc.returncode)
        self.assertEqual("", proc.stdout)


if __name__ == "__main__":
    unittest.main()