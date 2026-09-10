"""Behavioral tests for this skill's executable assets.

The 71 prior tests were all wording-level: none ever executed `make` against
the golden Makefiles or ran the discovery script. A broken tab, a typo'd
target reference, or the probe-script `set -e` bug (a repo without cmd/
killed the script before its own "no entrypoints" branch — see git history)
would keep every test green. These tests run the real binaries.

Requires `make` and `bash` on PATH (both are hard prerequisites of the
skill's domain, so no skip logic).
"""

import json
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

    def _run(self, *args: str, env_extra: dict | None = None) -> subprocess.CompletedProcess:
        # A private build cache: `go list` fails outright when the default
        # GOCACHE is unreadable, and the script then honestly degrades to the
        # glob — which would make these classification assertions measure the
        # fallback instead of the toolchain path.
        env = {**os.environ,
               "GOCACHE": str(self.repo / ".gocache"),
               "GOMODCACHE": str(self.repo / ".gomodcache")}
        if env_extra:
            env.update(env_extra)
        return subprocess.run(
            ["bash", str(DISCOVER), *args, str(self.repo)],
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
        )

    def test_a_directory_with_no_module_is_unknown_not_library_only(self) -> None:
        """Empty output with nothing queryable is NOT 'this repo has no programs'.

        Both cases used to exit 0 printing the same "no entrypoints" line, so a
        repo whose toolchain merely could not run looked exactly like a library.
        SKILL.md's project-shape table reads "no package main" as "emit no
        build targets", so an ordinary program lost every build target it
        should have had. Exit 4 is the difference.
        """
        proc = self._run()
        self.assertEqual(4, proc.returncode,
                         f"an unanswerable query must not report success: {proc.stderr}")
        self.assertEqual("", proc.stdout)
        self.assertIn("INCOMPLETE", proc.stderr)
        self.assertNotIn("has no programs", proc.stderr)

    def test_library_only_module_is_a_complete_answer(self) -> None:
        """The other half: a real module with no programs exits 0, and says so."""
        (self.repo / "go.mod").write_text("module example.com/lib\n\ngo 1.22\n")
        (self.repo / "lib.go").write_text("package lib\n\nfunc F() {}\n")
        (self.repo / "cmd").mkdir()
        proc = self._run()
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertEqual("", proc.stdout)
        self.assertIn("has no programs", proc.stderr)
        self.assertIn("# discovery: go-list\n", proc.stderr)

    def test_a_broken_toolchain_over_a_real_program_is_incomplete(self) -> None:
        """The reviewer's case: an ordinary program plus a toolchain that
        cannot answer. Silence here is not evidence of a library."""
        (self.repo / "go.mod").write_text("module example.com/app\n\ngo 1.22\n")
        (self.repo / "entry.go").write_text("package main\n\nfunc main() {}\n")
        ok = self._run()
        self.assertEqual(0, ok.returncode, ok.stderr)
        self.assertIn("confirmed", ok.stdout)
        broken = self._run(env_extra={"GOFLAGS": "-mod=bogus"})
        self.assertEqual(4, broken.returncode,
                         f"a failed query must not read as library-only: {broken.stderr}")
        self.assertEqual("", broken.stdout)
        self.assertIn("INCOMPLETE", broken.stderr)

    def test_entrypoints_classified_with_kind_and_target(self) -> None:
        (self.repo / "go.mod").write_text("module example.com/fixture\n\ngo 1.22\n")
        for d in ("cmd/api", "cmd/consumer/sync", "cmd/cron/cleanup", "cmd/mytool"):
            (self.repo / d).mkdir(parents=True)
            (self.repo / d / "main.go").write_text("package main\n\nfunc main() {}\n")
        proc = self._run()
        self.assertEqual(0, proc.returncode, proc.stderr)
        rows = [tuple(line.split("\t")) for line in proc.stdout.splitlines()]
        self.assertIn(("api", "api", "api", "cmd/api", "confirmed"), rows)
        self.assertIn(("consumer", "sync", "consumer-sync", "cmd/consumer/sync", "confirmed"), rows)
        self.assertIn(("cron", "cleanup", "cron-cleanup", "cmd/cron/cleanup", "confirmed"), rows)
        self.assertIn(("other", "mytool", "mytool", "cmd/mytool", "confirmed"), rows)
        for row in rows:
            self.assertEqual(5, len(row), f"row is not 5-field TSV: {row}")

    def test_json_mode_emits_parseable_objects(self) -> None:
        (self.repo / "go.mod").write_text("module example.com/fixture\n\ngo 1.22\n")
        (self.repo / "cmd" / "api").mkdir(parents=True)
        (self.repo / "cmd" / "api" / "main.go").write_text("package main\n\nfunc main() {}\n")
        proc = self._run("--json")
        self.assertEqual(0, proc.returncode, proc.stderr)
        objs = [json.loads(line) for line in proc.stdout.splitlines()]
        self.assertEqual(1, len(objs))
        self.assertEqual(
            {"kind": "api", "name": "api", "target": "api", "dir": "cmd/api",
             "confidence": "confirmed"}, objs[0]
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
        # Point GOCACHE at a writable dir — the default ~/Library/Caches/go-build is
        # outside a restricted sandbox's writable set, so a cold rebuild there is denied.
        self.build_env = {**os.environ, "GOCACHE": str(self.proj / ".gocache")}

    def _build(self, cwd: Path, extra_env: dict | None = None) -> subprocess.CompletedProcess:
        env = self.build_env if extra_env is None else {**self.build_env, **extra_env}
        return subprocess.run(["make", "build-api"], cwd=cwd, env=env,
                              capture_output=True, text=True, timeout=60)

    def test_build_injects_all_version_metadata(self) -> None:
        build = self._build(self.proj)
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
        def build_time() -> str:
            b = self._build(self.proj, {"SOURCE_DATE_EPOCH": "1700000000"})  # 2023-11-14
            self.assertEqual(0, b.returncode, b.stderr)  # both builds must actually succeed
            return run([str(self.proj / "bin" / "api"), "--version"], self.proj).stdout

        first, second = build_time(), build_time()
        self.assertEqual(first, second, "fixed SOURCE_DATE_EPOCH must give an identical buildTime")
        self.assertIn("buildTime=2023-11-14", first, first)

    def test_binary_reproducible_across_checkout_paths(self) -> None:
        """Identical source at two DIFFERENT paths + a fixed SOURCE_DATE_EPOCH must
        produce a byte-identical binary. This is exactly what -trimpath buys, and is the
        evidence behind the docs' (narrowed) reproducibility claim — without -trimpath the
        embedded build path differs and the hashes diverge."""
        import hashlib

        # Shared writable GOCACHE (sandbox) + fixed epoch; -trimpath makes the two
        # different build paths irrelevant to the output.
        env = {**self.build_env, "SOURCE_DATE_EPOCH": "1700000000"}
        main_go = (self.proj / "cmd" / "api" / "main.go").read_text()
        makefile = (self.proj / "Makefile").read_text()
        digests = []
        for _ in range(2):
            d = Path(tempfile.mkdtemp())
            self.addCleanup(shutil.rmtree, d, ignore_errors=True)
            (d / "cmd" / "api").mkdir(parents=True)
            (d / "cmd" / "api" / "main.go").write_text(main_go)
            (d / "go.mod").write_text("module fixture\n\ngo 1.22\n")
            (d / "Makefile").write_text(makefile)
            b = subprocess.run(["make", "build-api"], cwd=d, env=env,
                               capture_output=True, text=True, timeout=60)
            self.assertEqual(0, b.returncode, b.stderr)
            digests.append(hashlib.sha256((d / "bin" / "api").read_bytes()).hexdigest())
        self.assertEqual(digests[0], digests[1],
                         "identical source at different paths + fixed epoch + -trimpath "
                         "must be byte-identical")

    def test_clean_removes_build_artifacts(self) -> None:
        self.assertEqual(0, self._build(self.proj).returncode)
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

    def test_traditional_multimodule_without_gowork(self):
        # Tier 3: a plain multi-module repo with NO go.work must still list modules
        # (scoped go.mod search), excluding vendored / example modules.
        for m in ("svc-a", "svc-b", "examples/demo", "vendor/dep"):
            (self.repo / m).mkdir(parents=True)
            (self.repo / m / "go.mod").write_text("module m\n\ngo 1.22\n")
        out = subprocess.run(["bash", str(DISCOVER), "--modules", str(self.repo)],
                             capture_output=True, text=True, timeout=30)
        self.assertEqual(0, out.returncode, out.stderr)
        dirs = out.stdout.split()
        self.assertTrue(any(d.endswith("svc-a") for d in dirs),
                        f"traditional multi-module repo must list modules: {out.stdout!r}")
        self.assertTrue(any(d.endswith("svc-b") for d in dirs), out.stdout)
        self.assertFalse(any("examples" in d or "vendor" in d for d in dirs),
                         f"vendored/example modules must be excluded: {out.stdout!r}")

    def test_go_work_parser_handles_comments_and_quotes(self):
        # Force the toolchain-absent branch (tier 2 awk parser) via a minimal PATH,
        # exercising `//` comment stripping and quote removal directly.
        (self.repo / "go.work").write_text(
            'go 1.22\n\nuse (\n\t./svc-a  // primary service\n\t"./svc-b"\n)\n'
        )
        out = subprocess.run(["env", "PATH=/usr/bin:/bin", "bash", str(DISCOVER),
                              "--modules", str(self.repo)],
                             capture_output=True, text=True, timeout=30)
        self.assertEqual(0, out.returncode, out.stderr)
        lines = [ln.strip() for ln in out.stdout.splitlines() if ln.strip()]
        self.assertIn("./svc-a", lines, f"comment not stripped / path lost: {out.stdout!r}")
        self.assertIn("./svc-b", lines, f"surrounding quotes not removed: {out.stdout!r}")


@unittest.skipUnless(GIT, "git not installed")
# `GenerateCheckBeforeAfterTests` and `ErrorPropagationTests` used to live here.
# Both extracted a recipe out of ONE golden file with their own private
# extractor, so they proved the property for one copy of a recipe the skill
# ships two or three times — and a second extractor is a second thing that can
# silently match nothing. They have moved to `test_shipped_recipes.py`, which
# extracts every copy from every shipped asset and runs each one against both
# halves of the contract, under bash and again under a plain POSIX sh.


class GoToolchainDiscoveryTests(unittest.TestCase):
    """Entrypoint discovery must answer at PACKAGE level, not by filename.

    A `cmd/**/main.go` glob is wrong in both directions and a real repo hits
    both: it misses a program whose file is not called main.go, misses programs
    outside cmd/, and falsely reports a non-main package that merely contains a
    file with that name.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = Path(self._tmp.name)
        self.env = {**os.environ, "GOCACHE": str(self.repo / ".gocache"),
                    "GOMODCACHE": str(self.repo / ".gomodcache")}

    def _run(self, *args: str, env_extra: dict | None = None):
        env = dict(self.env)
        if env_extra:
            env.update(env_extra)
        return subprocess.run(["bash", str(DISCOVER), *args], cwd=self.repo, env=env,
                              capture_output=True, text=True, timeout=60)

    @unittest.skipUnless(GO, "requires the go toolchain")
    def test_finds_programs_the_filename_glob_misses_and_skips_its_false_positive(self):
        (self.repo / "go.mod").write_text("module example.com/root\n\ngo 1.22\n")
        (self.repo / "main.go").write_text("package main\n\nfunc main() {}\n")
        (self.repo / "cmd" / "app").mkdir(parents=True)
        # a real program whose file is NOT named main.go
        (self.repo / "cmd" / "app" / "entry.go").write_text("package main\n\nfunc main() {}\n")
        # a NON-main package that happens to contain a file called main.go
        (self.repo / "internal" / "helper").mkdir(parents=True)
        (self.repo / "internal" / "helper" / "main.go").write_text(
            "package helper\n\nfunc Help() {}\n")
        out = self._run()
        self.assertEqual(0, out.returncode, out.stderr)
        dirs = {line.split("\t")[3] for line in out.stdout.splitlines() if "\t" in line}
        self.assertIn(".", dirs, f"root-level program missed: {out.stdout!r}")
        self.assertIn("cmd/app", dirs, f"program in entry.go missed: {out.stdout!r}")
        self.assertNotIn("internal/helper", dirs,
                         f"non-main package falsely reported: {out.stdout!r}")

    @unittest.skipUnless(GO, "requires the go toolchain")
    def test_workspace_root_still_reports_its_programs(self):
        """Inside a workspace `go list ./...` refuses non-member directories.

        Left unhandled, a workspace root reports zero entrypoints even when
        programs sit right there.
        """
        (self.repo / "svc").mkdir()
        (self.repo / "svc" / "go.mod").write_text("module example.com/svc\n\ngo 1.22\n")
        (self.repo / "go.work").write_text("go 1.22\n\nuse ./svc\n")
        (self.repo / "go.mod").write_text("module example.com/root\n\ngo 1.22\n")
        (self.repo / "main.go").write_text("package main\n\nfunc main() {}\n")
        out = self._run()
        self.assertEqual(0, out.returncode, out.stderr)
        self.assertIn(".", {line.split("\t")[3] for line in out.stdout.splitlines()
                            if "\t" in line},
                      f"workspace root program missed: {out.stdout!r}{out.stderr!r}")

    @unittest.skipUnless(GO, "requires the go toolchain")
    def test_gowork_off_still_lists_every_module(self):
        """`go env GOWORK` prints the literal string "off" when disabled.

        "off" is non-empty, so a bare `-n` test treated it as a workspace path
        and asked `go list -m`, which then answered for one module or none —
        the workspace's real members vanished while the exit code stayed 0.
        """
        for m in ("svc-a", "svc-b"):
            (self.repo / m).mkdir()
            (self.repo / m / "go.mod").write_text(f"module example.com/{m}\n\ngo 1.22\n")
        (self.repo / "go.work").write_text("go 1.22\n\nuse (\n\t./svc-a\n\t./svc-b\n)\n")
        normal = self._run("--modules")
        self.assertEqual(0, normal.returncode, normal.stderr)
        self.assertEqual(2, len(normal.stdout.split()), normal.stdout)
        off = self._run("--modules", env_extra={"GOWORK": "off"})
        self.assertEqual(0, off.returncode,
                         f"GOWORK=off must still find the modules: {off.stdout!r}{off.stderr!r}")
        found = {Path(p).name for p in off.stdout.split()}
        self.assertEqual({"svc-a", "svc-b"}, found,
                         f"GOWORK=off lost the member modules: {off.stdout!r}")

    def test_zero_modules_is_an_error_not_a_silent_success(self):
        """An aggregate target looping over an empty module list must not pass.

        Exiting 0 with empty output is what let `for m in $(MODULES)` iterate
        over nothing and report success.
        """
        out = self._run("--modules")
        self.assertNotEqual(0, out.returncode,
                            f"no modules must be an error: {out.stdout!r}{out.stderr!r}")
        self.assertIn("no Go modules found", out.stderr)

    @unittest.skipUnless(GO, "requires the go toolchain")
    def test_a_successful_query_with_no_main_package_is_not_a_failed_query(self):
        """Library-only is an ANSWER, not an inability to answer.

        Measured: `go list -f '{{.Name}}' ./...` exits 0 for a library-only
        module, for a module whose source does not parse, and for one with an
        unresolvable import — it only needs the package clause. It exits
        non-zero for exactly one thing: no module to ask about. Collapsing
        "answered: none" into "could not answer" sent discovery to the filename
        glob, which then reported a `package helper` file called main.go as a
        program.
        """
        (self.repo / "go.mod").write_text("module example.com/lib\n\ngo 1.22\n")
        (self.repo / "lib.go").write_text("package lib\n\nfunc F() {}\n")
        (self.repo / "cmd" / "helper").mkdir(parents=True)
        (self.repo / "cmd" / "helper" / "main.go").write_text(
            "package helper\n\nfunc H() {}\n")
        out = self._run()
        self.assertEqual(0, out.returncode, out.stderr)
        self.assertEqual("", out.stdout.strip(),
                         f"a non-main package was reported as an entrypoint: {out.stdout!r}")
        # Match the script's stable token, not its prose. The first version of
        # this assertion looked for the word "fallback" while the script says
        # "falling back", so it passed no matter which path ran — the mutation
        # that restored the defect killed nothing.
        self.assertIn("# discovery: go-list\n", out.stderr,
                      f"an answerable query must not fall back: {out.stderr!r}")
        self.assertNotIn("glob", out.stderr, f"unexpected fallback: {out.stderr!r}")

    @unittest.skipUnless(GO, "requires the go toolchain")
    def test_nested_module_programs_are_found_alongside_the_root_module(self):
        """`go list ./...` never crosses a module boundary, so the root module's
        answer is complete only for the root module. Stopping as soon as one
        module answered hid every program in every nested module."""
        (self.repo / "go.mod").write_text("module example.com/root\n\ngo 1.22\n")
        (self.repo / "cmd" / "rootapp").mkdir(parents=True)
        (self.repo / "cmd" / "rootapp" / "main.go").write_text(
            "package main\n\nfunc main() {}\n")
        (self.repo / "sub" / "cmd" / "subapp").mkdir(parents=True)
        (self.repo / "sub" / "go.mod").write_text("module example.com/sub\n\ngo 1.22\n")
        (self.repo / "sub" / "cmd" / "subapp" / "main.go").write_text(
            "package main\n\nfunc main() {}\n")
        out = self._run()
        self.assertEqual(0, out.returncode, out.stderr)
        dirs = {line.split("\t")[3] for line in out.stdout.splitlines() if "\t" in line}
        self.assertIn("cmd/rootapp", dirs, out.stdout)
        self.assertIn("sub/cmd/subapp", dirs,
                      f"nested module's program missed: {out.stdout!r}")

    @unittest.skipUnless(GO, "requires the go toolchain")
    def test_confirmed_and_candidate_are_distinguishable(self):
        """A glob guess and a toolchain answer must not look alike downstream.

        Emitting both in the same shape is what let a caller turn a filename
        guess straight into a build target.
        """
        # No go.mod anywhere: the toolchain cannot be asked, so the glob runs.
        (self.repo / "cmd" / "x").mkdir(parents=True)
        (self.repo / "cmd" / "x" / "main.go").write_text("package main\n\nfunc main() {}\n")
        (self.repo / "cmd" / "decoy").mkdir(parents=True)
        (self.repo / "cmd" / "decoy" / "main.go").write_text("package decoy\n\nfunc X() {}\n")
        out = self._run()
        self.assertEqual(4, out.returncode,
                         f"glob rows mean the query was incomplete: {out.stderr}")
        self.assertIn("# discovery: glob\n", out.stderr, out.stderr)
        rows = [line.split("\t") for line in out.stdout.splitlines() if "\t" in line]
        self.assertTrue(rows, f"glob fallback found nothing: {out.stdout!r}{out.stderr!r}")
        for row in rows:
            self.assertEqual(5, len(row), f"confidence column missing: {row!r}")
            self.assertEqual("candidate", row[4],
                             f"a glob guess must not be labelled confirmed: {row!r}")
        self.assertNotIn("cmd/decoy", {r[3] for r in rows},
                         "even the fallback must read the package clause, not the filename")

    @unittest.skipUnless(GO, "requires the go toolchain")
    def test_toolchain_answers_are_labelled_confirmed(self):
        (self.repo / "go.mod").write_text("module example.com/root\n\ngo 1.22\n")
        (self.repo / "cmd" / "api").mkdir(parents=True)
        (self.repo / "cmd" / "api" / "main.go").write_text("package main\n\nfunc main() {}\n")
        out = self._run()
        self.assertIn("# discovery: go-list\n", out.stderr, out.stderr)
        rows = [line.split("\t") for line in out.stdout.splitlines() if "\t" in line]
        self.assertTrue(rows, out.stdout)
        for row in rows:
            self.assertEqual("confirmed", row[4], f"{row!r}")

    @unittest.skipUnless(GO, "requires the go toolchain")
    def test_json_mode_carries_the_confidence_too(self):
        (self.repo / "go.mod").write_text("module example.com/root\n\ngo 1.22\n")
        (self.repo / "cmd" / "api").mkdir(parents=True)
        (self.repo / "cmd" / "api" / "main.go").write_text("package main\n\nfunc main() {}\n")
        out = self._run("--json")
        rows = [json.loads(line) for line in out.stdout.splitlines() if line.startswith("{")]
        self.assertTrue(rows, out.stdout)
        for row in rows:
            self.assertEqual("confirmed", row.get("confidence"), f"{row!r}")



class LibraryOnlyProjectTests(unittest.TestCase):
    """A library-only repo must not be handed program-shaped requirements.

    The default target list assumes a binary: build-*, run-*, a version target,
    -ldflags injection, and a `--version` check on the artifact. A repo with no
    `package main` can satisfy none of those, so the skill has to detect the
    shape rather than apply the list unconditionally.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = Path(self._tmp.name)
        (self.repo / "go.mod").write_text("module example.com/lib\n\ngo 1.22\n")
        (self.repo / "stringx").mkdir()
        (self.repo / "stringx" / "stringx.go").write_text(
            "package stringx\n\nfunc Reverse(s string) string {\n"
            "\tr := []rune(s)\n"
            "\tfor i, j := 0, len(r)-1; i < j; i, j = i+1, j-1 {\n"
            "\t\tr[i], r[j] = r[j], r[i]\n\t}\n\treturn string(r)\n}\n")
        (self.repo / "stringx" / "stringx_test.go").write_text(
            "package stringx\n\nimport \"testing\"\n\n"
            "func TestReverse(t *testing.T) {\n"
            "\tif got := Reverse(\"ab\"); got != \"ba\" {\n"
            "\t\tt.Fatalf(\"got %q\", got)\n\t}\n}\n")
        self.env = {**os.environ, "GOCACHE": str(self.repo / ".gocache"),
                    "GOMODCACHE": str(self.repo / ".gomodcache")}

    @unittest.skipUnless(GO, "requires the go toolchain")
    def test_discovery_reports_no_entrypoints(self):
        proc = subprocess.run(["bash", str(DISCOVER)], cwd=self.repo, env=self.env,
                              capture_output=True, text=True, timeout=60)
        self.assertEqual(0, proc.returncode,
                         "a library-only repo is a normal outcome, not an error")
        self.assertEqual("", proc.stdout.strip(),
                         f"library-only repo must yield no entrypoints: {proc.stdout!r}")
        self.assertIn("No Go entrypoints (package main) found", proc.stderr)

    @unittest.skipUnless(GO, "requires the go toolchain")
    def test_discovery_still_reports_the_module(self):
        """--modules must find the library's own module; zero modules is an error."""
        proc = subprocess.run(["bash", str(DISCOVER), "--modules"], cwd=self.repo,
                              env=self.env, capture_output=True, text=True, timeout=60)
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertEqual(1, len(proc.stdout.split()), proc.stdout)

    @unittest.skipUnless(GO, "requires the go toolchain")
    def test_a_library_shaped_makefile_validates_without_a_binary(self):
        """The library validation path is `make test`, not a `--version` run."""
        (self.repo / "Makefile").write_text(
            ".DEFAULT_GOAL := help\n"
            "SHELL       := bash\n"
            ".SHELLFLAGS := -euo pipefail -c\n"
            "GO ?= go\n\n"
            ".PHONY: help fmt-check test ci\n\n"
            "help: ## Show targets\n"
            "\t@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | sort | "
            "awk 'BEGIN {FS = \":.*?## \"}; {printf \"  %-14s %s\\n\", $$1, $$2}'\n\n"
            "fmt-check: ## Check formatting\n"
            "\t@out=$$(gofmt -l . 2>&1); status=$$?; \\\n"
            "\tif [ $$status -ne 0 ]; then echo \"$$out\"; exit $$status; fi; \\\n"
            "\tif [ -n \"$$out\" ]; then echo \"$$out\"; exit 1; fi\n\n"
            "test: ## Run tests\n"
            "\t$(GO) test ./...\n\n"
            "ci: fmt-check test ## Mirror CI\n"
        )
        for target in ("help", "fmt-check", "test", "ci"):
            proc = subprocess.run(["make", target], cwd=self.repo, env=self.env,
                                  capture_output=True, text=True, timeout=90)
            self.assertEqual(0, proc.returncode,
                             f"library `make {target}` failed: {proc.stdout}{proc.stderr}")
        self.assertNotIn("build-", (self.repo / "Makefile").read_text(),
                         "a library Makefile must not carry build-* targets")

if __name__ == "__main__":
    unittest.main()
