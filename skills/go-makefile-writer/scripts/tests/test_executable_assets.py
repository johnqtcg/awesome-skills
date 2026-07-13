"""Behavioral tests for this skill's executable assets.

The 71 prior tests were all wording-level: none ever executed `make` against
the golden Makefiles or ran the discovery script. A broken tab, a typo'd
target reference, or the probe-script `set -e` bug (a repo without cmd/
killed the script before its own "no entrypoints" branch — see git history)
would keep every test green. These tests run the real binaries.

Requires `make` and `bash` on PATH (both are hard prerequisites of the
skill's domain, so no skip logic).
"""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[2]
GOLDEN_DIR = SKILL_DIR / "references" / "golden"
DISCOVER = SKILL_DIR / "scripts" / "discover_go_entrypoints.sh"
GO = shutil.which("go")
GIT = shutil.which("git")


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


@unittest.skipUnless(GO, "go toolchain not installed")
class RealBuildTests(unittest.TestCase):
    """Actually build a binary and run it — proves `-ldflags` injection reaches the
    artifact, which `make -n` (dry-run) can never verify."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.proj = Path(self._tmp.name)
        (self.proj / "cmd" / "api").mkdir(parents=True)
        (self.proj / "cmd" / "api" / "main.go").write_text(
            'package main\n\nimport (\n\t"fmt"\n\t"os"\n)\n\n'
            'var (\n\tversion   = "unset"\n\tcommit    = "unset"\n\tbuildTime = "unset"\n)\n\n'
            "func main() {\n"
            '\tif len(os.Args) > 1 && os.Args[1] == "--version" {\n'
            '\t\tfmt.Printf("version=%s commit=%s buildTime=%s\\n", version, commit, buildTime)\n'
            "\t\treturn\n\t}\n"
            '\tfmt.Println("running")\n}\n'
        )
        (self.proj / "go.mod").write_text("module fixture\n\ngo 1.22\n")
        (self.proj / "Makefile").write_text((GOLDEN_DIR / "simple-project.mk").read_text())

    def test_build_injects_all_version_metadata(self) -> None:
        build = run(["make", "build-api"], self.proj)
        self.assertEqual(0, build.returncode, build.stderr)
        binary = self.proj / "bin" / "api"
        self.assertTrue(binary.exists(), "make build-api did not produce bin/api")
        out = run([str(binary), "--version"], self.proj)
        # All THREE -X vars must reach the artifact (VERSION→"dev", COMMIT→"unknown"
        # outside a git repo; buildTime always set). None may remain at "unset".
        self.assertIn("version=dev", out.stdout, out.stdout)
        self.assertIn("commit=", out.stdout)
        self.assertIn("buildTime=", out.stdout)
        self.assertNotIn("unset", out.stdout,
                         "every -X var must be injected; none left at its 'unset' default")
        # A real --version CLI, not an unconditional print.
        self.assertEqual("running\n", run([str(binary)], self.proj).stdout)

    def test_build_time_reproducible_with_fixed_epoch(self) -> None:
        env = {**os.environ, "SOURCE_DATE_EPOCH": "1700000000"}  # 2023-11-14T22:13:20Z

        def build_time() -> str:
            subprocess.run(["make", "build-api"], cwd=self.proj, env=env,
                           capture_output=True, text=True, timeout=30)
            return run([str(self.proj / "bin" / "api"), "--version"], self.proj).stdout

        first, second = build_time(), build_time()
        self.assertEqual(first, second, "fixed SOURCE_DATE_EPOCH must give an identical buildTime")
        self.assertIn("buildTime=2023-11-14", first, first)

    def test_clean_removes_build_artifacts(self) -> None:
        self.assertEqual(0, run(["make", "build-api"], self.proj).returncode)
        self.assertTrue((self.proj / "bin" / "api").exists())
        clean = run(["make", "clean"], self.proj)
        self.assertEqual(0, clean.returncode, clean.stderr)
        self.assertFalse((self.proj / "bin").exists(), "clean must remove bin/")


class CleanSafetyTests(unittest.TestCase):
    """`clean` must delete generated artifacts only — never hand-written docs."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.proj = Path(self._tmp.name)
        (self.proj / "cmd" / "api").mkdir(parents=True)
        (self.proj / "cmd" / "api" / "main.go").write_text("package main\n\nfunc main() {}\n")
        (self.proj / "go.mod").write_text("module fixture\n\ngo 1.22\n")
        (self.proj / "Makefile").write_text((GOLDEN_DIR / "complex-project.mk").read_text())

    def test_clean_preserves_handwritten_docs(self) -> None:
        (self.proj / "bin").mkdir()
        (self.proj / "bin" / "api").write_text("stale")
        (self.proj / "docs").mkdir()
        handwritten = self.proj / "docs" / "architecture.md"
        handwritten.write_text("# hand-written, not generated\n")
        (self.proj / "docs" / "swagger.json").write_text("{}")  # generated artifact
        proc = run(["make", "clean"], self.proj)
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertTrue(handwritten.exists(),
                        "clean deleted a hand-written doc — must scope to generated files")
        self.assertFalse((self.proj / "docs" / "swagger.json").exists(),
                         "clean should still remove generated swagger artifacts")
        self.assertFalse((self.proj / "bin").exists(), "clean must still remove bin/")


class DiscoverModulesTests(unittest.TestCase):
    """`--modules` lists go.work `use` modules only — never examples/vendored ones
    (the misfire a bare `rg --files go.mod` produces)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = Path(self._tmp.name)

    def test_lists_use_modules_excludes_others(self):
        (self.repo / "go.work").write_text("go 1.22\n\nuse (\n\t./svc-a\n\t./svc-b\n)\n")
        for m in ("svc-a", "svc-b", "examples/demo"):
            (self.repo / m).mkdir(parents=True)
            (self.repo / m / "go.mod").write_text(f"module {m}\n\ngo 1.22\n")
        out = subprocess.run(["bash", str(DISCOVER), "--modules", str(self.repo)],
                             capture_output=True, text=True, timeout=30)
        self.assertEqual(0, out.returncode, out.stderr)
        dirs = out.stdout.split()
        self.assertTrue(any(d.endswith("svc-a") for d in dirs), out.stdout)
        self.assertTrue(any(d.endswith("svc-b") for d in dirs), out.stdout)
        self.assertFalse(any("examples" in d for d in dirs),
                         f"a module not in go.work `use` must not be listed: {out.stdout!r}")


@unittest.skipUnless(GIT, "git not installed")
class GenerateCheckBeforeAfterTests(unittest.TestCase):
    """generate-check compares before/after, so a PRE-EXISTING dirty tree unrelated
    to codegen is not misreported as 'generated code stale' (the porcelain-only bug)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = Path(self._tmp.name)
        self.env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull,
                    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
        self._git("init", "-q")
        (self.repo / "committed.txt").write_text("v1\n")
        self._git("add", "committed.txt")
        self._git("commit", "-qm", "init")
        (self.repo / "committed.txt").write_text("locally edited\n")  # pre-existing, unrelated dirt
        # No-op `generate` + the golden's before/after generate-check recipe.
        (self.repo / "Makefile").write_text(
            "generate:\n\t@true\n\n"
            "generate-check: ## check\n"
            "\t@before=\"$$(git status --porcelain)\"; \\\n"
            "\t$(MAKE) generate >/dev/null; \\\n"
            "\tafter=\"$$(git status --porcelain)\"; \\\n"
            "\tif [ \"$$before\" != \"$$after\" ]; then echo STALE; exit 1; fi\n"
        )

    def _git(self, *a):
        return subprocess.run(["git", *a], cwd=self.repo, env=self.env, capture_output=True, text=True)

    def test_preexisting_dirt_is_not_flagged(self):
        out = subprocess.run(["make", "generate-check"], cwd=self.repo, env=self.env,
                             capture_output=True, text=True, timeout=30)
        self.assertEqual(0, out.returncode,
                         f"pre-existing dirt must not be flagged stale: {out.stdout}{out.stderr}")


if __name__ == "__main__":
    unittest.main()