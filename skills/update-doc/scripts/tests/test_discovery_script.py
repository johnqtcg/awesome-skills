"""Edge-case behavior tests for `scripts/discover_doc_scope.sh`.

The golden corpus covers whole repository shapes. This file covers the boundary
conditions a fixture cannot express: argument handling, unresolvable base refs,
degraded modes, and the report contract itself.
"""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[2]
SCRIPT = SKILL_DIR / "scripts" / "discover_doc_scope.sh"

GIT = shutil.which("git")

SECTION_ORDER = [
    "=== SECTION: repo ===",
    "=== SECTION: diff_scope ===",
    "=== SECTION: language ===",
    "=== SECTION: command_sources ===",
    "=== SECTION: project_type ===",
    "=== SECTION: docs ===",
    "=== SECTION: ci ===",
    "=== END ===",
]


def run(*args):
    return subprocess.run(
        ["bash", str(SCRIPT), *args], capture_output=True, text=True
    )


def field(stdout, key):
    for line in stdout.splitlines():
        if line.startswith(f"{key}:"):
            return line.split(":", 1)[1].strip()
    raise AssertionError(f"field {key} not found in report")


class TempRepo:
    def __init__(self, git_init=True):
        self.git_init = git_init

    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR") or None)
        self.path = Path(self._tmp.name) / "repo"
        self.path.mkdir()
        if self.git_init:
            self.git("init", "-q", "-b", "main")
            self.git("config", "user.email", "t@example.com")
            self.git("config", "user.name", "t")
            self.git("config", "commit.gpgsign", "false")
        return self

    def __exit__(self, *exc):
        self._tmp.cleanup()

    def git(self, *args):
        subprocess.run(
            [GIT, *args], cwd=self.path, check=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )

    def write(self, rel, content):
        p = self.path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

    def commit(self, message="c"):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)


class TestArgumentHandling(unittest.TestCase):
    def test_help_exits_zero(self):
        proc = run("--help")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("Usage:", proc.stdout)

    def test_unknown_argument_is_a_usage_error(self):
        proc = run("--nope")
        self.assertEqual(proc.returncode, 3)
        self.assertNotIn("=== END ===", proc.stdout)

    def test_base_without_value_is_a_usage_error(self):
        proc = run("--base")
        self.assertEqual(proc.returncode, 3)

    def test_repo_without_value_is_a_usage_error(self):
        proc = run("--repo")
        self.assertEqual(proc.returncode, 3)

    def test_missing_repo_path_is_a_usage_error(self):
        proc = run("--repo", "/definitely/not/a/real/path/xyz")
        self.assertEqual(proc.returncode, 3)
        self.assertNotIn("=== END ===", proc.stdout)


class TestReportContract(unittest.TestCase):
    def test_sections_appear_in_fixed_order(self):
        with TempRepo(git_init=False) as repo:
            proc = run("--repo", str(repo.path))
        self.assertEqual(proc.returncode, 0)
        positions = []
        for marker in SECTION_ORDER:
            self.assertIn(marker, proc.stdout, f"missing {marker}")
            positions.append(proc.stdout.index(marker))
        self.assertEqual(positions, sorted(positions), "sections out of order")

    def test_sentinel_is_the_final_line(self):
        with TempRepo(git_init=False) as repo:
            proc = run("--repo", str(repo.path))
        self.assertEqual(proc.stdout.rstrip().splitlines()[-1], "=== END ===")

    def test_empty_directory_still_produces_a_full_report(self):
        """Every probe is empty here. A `set -e` runner would abort on the first
        one and emit a partial report that looks like a crash."""
        with TempRepo(git_init=False) as repo:
            proc = run("--repo", str(repo.path))
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(field(proc.stdout, "STATUS"), "DEGRADED_NO_GIT")
        self.assertEqual(field(proc.stdout, "DOMINANT"), "GENERIC")
        self.assertEqual(field(proc.stdout, "PRIMARY"), "NONE")
        self.assertEqual(field(proc.stdout, "LIKELY"), "UNKNOWN")
        self.assertEqual(field(proc.stdout, "TOTAL_UNIQUE"), "0")


@unittest.skipIf(GIT is None, "git not available")
class TestBaseRefResolution(unittest.TestCase):
    def test_unresolvable_base_degrades_without_losing_other_sources(self):
        with TempRepo() as repo:
            repo.write("main.go", "package main\n")
            repo.write("go.mod", "module x\n\ngo 1.22\n")
            repo.commit()
            repo.write("new.go", "package main\n")
            proc = run("--repo", str(repo.path), "--base", "origin/does-not-exist")

        self.assertEqual(proc.returncode, 0)
        self.assertEqual(field(proc.stdout, "BASE_REF"), "NOT_RESOLVED")
        self.assertEqual(field(proc.stdout, "SOURCE base_range"), "0")
        # The untracked file must still be discovered.
        self.assertEqual(field(proc.stdout, "SOURCE untracked"), "1")
        self.assertEqual(field(proc.stdout, "TOTAL_UNIQUE"), "1")

    def test_base_is_auto_resolved_when_not_supplied(self):
        with TempRepo() as repo:
            repo.write("main.go", "package main\n")
            repo.commit()
            proc = run("--repo", str(repo.path))
        self.assertEqual(field(proc.stdout, "BASE_REF"), "main")

    def test_repo_with_no_commits_does_not_crash(self):
        with TempRepo() as repo:
            repo.write("README.md", "# x\n")
            proc = run("--repo", str(repo.path))
        self.assertEqual(proc.returncode, 0)
        self.assertTrue(proc.stdout.rstrip().endswith("=== END ==="))
        self.assertEqual(field(proc.stdout, "SOURCE untracked"), "1")

    def test_sources_do_not_double_count_a_file_in_two_states(self):
        """A file both committed on the branch and edited in the worktree appears
        in two sources but must count once in TOTAL_UNIQUE."""
        with TempRepo() as repo:
            repo.write("main.go", "package main\n")
            repo.commit()
            repo.git("checkout", "-q", "-b", "feature")
            repo.write("main.go", "package main // v2\n")
            repo.commit("branch")
            with open(repo.path / "main.go", "a", encoding="utf-8") as fh:
                fh.write("// worktree\n")
            proc = run("--repo", str(repo.path), "--base", "main")

        self.assertEqual(field(proc.stdout, "SOURCE worktree"), "1")
        self.assertEqual(field(proc.stdout, "SOURCE base_range"), "1")
        self.assertEqual(field(proc.stdout, "TOTAL_UNIQUE"), "1")


@unittest.skipIf(GIT is None, "git not available")
class TestRoutingSignals(unittest.TestCase):
    def test_bin_manifest_routes_to_cli_not_library(self):
        with TempRepo() as repo:
            repo.write("package.json", '{"main":"i.js","bin":{"t":"./i.js"}}\n')
            repo.write("i.js", "1;\n")
            repo.commit()
            proc = run("--repo", str(repo.path))
        self.assertEqual(field(proc.stdout, "LIKELY"), "cli")

    def test_main_only_manifest_routes_to_library(self):
        with TempRepo() as repo:
            repo.write("package.json", '{"main":"index.js"}\n')
            repo.write("index.js", "1;\n")
            repo.commit()
            proc = run("--repo", str(repo.path))
        self.assertEqual(field(proc.stdout, "LIKELY"), "library")

    def test_container_manifest_outranks_library_shape(self):
        with TempRepo() as repo:
            repo.write("go.mod", "module x\n\ngo 1.22\n")
            repo.write("Dockerfile", "FROM golang:1.22\n")
            repo.write("cmd/api/main.go", "package main\n")
            repo.commit()
            proc = run("--repo", str(repo.path))
        self.assertEqual(field(proc.stdout, "LIKELY"), "service")

    def test_makefile_outranks_native_toolchain(self):
        with TempRepo() as repo:
            repo.write("go.mod", "module x\n\ngo 1.22\n")
            repo.write("Makefile", "test:\n\tgo test ./...\n")
            repo.commit()
            proc = run("--repo", str(repo.path))
        self.assertEqual(field(proc.stdout, "PRIMARY"), "makefile")

    def test_native_used_when_no_wrapper_exists(self):
        with TempRepo() as repo:
            repo.write("go.mod", "module x\n\ngo 1.22\n")
            repo.write("main.go", "package main\n")
            repo.commit()
            proc = run("--repo", str(repo.path))
        self.assertEqual(field(proc.stdout, "PRIMARY"), "native")

    def test_single_language_repo_is_not_polyglot(self):
        with TempRepo() as repo:
            for i in range(5):
                repo.write(f"a{i}.go", "package main\n")
            repo.commit()
            proc = run("--repo", str(repo.path))
        self.assertEqual(field(proc.stdout, "POLYGLOT"), "no")

    def test_second_language_over_threshold_marks_polyglot(self):
        with TempRepo() as repo:
            for i in range(5):
                repo.write(f"a{i}.go", "package main\n")
            for i in range(3):
                repo.write(f"b{i}.py", "x = 1\n")
            repo.commit()
            proc = run("--repo", str(repo.path))
        self.assertEqual(field(proc.stdout, "POLYGLOT"), "yes")

    def test_pyproject_project_table_routes_to_library(self):
        """Exercises the `^[[:space:]]*\\[project\\]` probe.

        Written with a POSIX class rather than `\\s`, which is a GNU extension
        that BSD grep is not required to support.
        """
        with TempRepo() as repo:
            repo.write("pyproject.toml", "[project]\nname = \"pkg\"\n")
            repo.write("src/pkg/__init__.py", "")
            repo.write("src/pkg/core.py", "def f():\n    pass\n")
            repo.commit()
            proc = run("--repo", str(repo.path))
        self.assertEqual(field(proc.stdout, "DOMINANT"), "python")
        self.assertEqual(field(proc.stdout, "LIKELY"), "library")

    def test_cargo_workspace_routes_to_monorepo(self):
        with TempRepo() as repo:
            repo.write("Cargo.toml", "[workspace]\nmembers = [\"a\"]\n")
            repo.write("a/src/main.rs", "fn main() {}\n")
            repo.commit()
            proc = run("--repo", str(repo.path))
        self.assertEqual(field(proc.stdout, "LIKELY"), "monorepo")

    def test_cargo_lib_routes_to_library(self):
        with TempRepo() as repo:
            repo.write("Cargo.toml", "[package]\nname = \"c\"\n\n[lib]\npath = \"src/lib.rs\"\n")
            repo.write("src/lib.rs", "pub fn f() {}\n")
            repo.commit()
            proc = run("--repo", str(repo.path))
        self.assertEqual(field(proc.stdout, "DOMINANT"), "rust")
        self.assertEqual(field(proc.stdout, "LIKELY"), "library")

    def test_command_kinds_resolve_independently_of_primary(self):
        with TempRepo() as repo:
            repo.write("Makefile", "lint:\n\teslint .\n")
            repo.write(
                "package.json",
                '{\n  "name": "a",\n  "scripts": {\n    "build": "tsc",\n'
                '    "test": "vitest"\n  }\n}\n',
            )
            repo.write("index.ts", "export const x = 1;\n")
            repo.commit()
            out = run("--repo", str(repo.path)).stdout

        self.assertIn("PRIMARY: makefile", out)
        self.assertIn("  lint: makefile (make lint)", out)
        self.assertIn("  build: package-scripts (npm run build)", out)
        self.assertIn("  test: package-scripts (npm run test)", out)

    def test_unresolvable_kind_is_reported_not_guessed(self):
        with TempRepo() as repo:
            repo.write("README.md", "# x\n")
            repo.write("notes.txt", "hi\n")
            repo.commit()
            out = run("--repo", str(repo.path)).stdout
        for kind in ("build", "test", "lint", "run", "install"):
            self.assertIn(f"  {kind}: NOT_FOUND", out, f"{kind} must not be invented")

    def test_makefile_target_that_does_not_exist_is_not_claimed(self):
        """A Makefile defining only `lint` must not produce `make build`."""
        with TempRepo() as repo:
            repo.write("Makefile", "lint:\n\tgo vet ./...\n")
            repo.write("go.mod", "module x\n\ngo 1.22\n")
            repo.write("main.go", "package main\n")
            repo.commit()
            out = run("--repo", str(repo.path)).stdout
        self.assertNotIn("build: makefile", out)
        self.assertIn("  build: native (go build ./...)", out)

    def test_modules_report_their_own_source(self):
        with TempRepo() as repo:
            repo.write("Makefile", "test:\n\techo root\n")
            repo.write("services/api/go.mod", "module api\n")
            repo.write("services/api/main.go", "package main\n")
            repo.write("services/api/Makefile", "build:\n\tgo build ./...\n")
            repo.write("packages/ui/package.json", '{\n  "scripts": {\n    "build": "vite build"\n  }\n}\n')
            repo.write("packages/ui/package-lock.json", '{}\n')
            repo.write("packages/ui/i.ts", "export const a = 1;\n")
            repo.commit()
            out = run("--repo", str(repo.path)).stdout
        # Per-module AND per-command. `services/api` has a Makefile, but only
        # for `build` — its other kinds must still resolve on their own merits
        # rather than the whole module being labelled "makefile".
        self.assertIn("  services/api:", out)
        self.assertIn("    build: makefile (make build)", out)
        self.assertIn("    test: native (go test ./...)", out)
        self.assertIn("  packages/ui:", out)
        self.assertIn("    build: package-scripts (npm run build)", out)

    def test_ci_run_prefix_does_not_self_match(self):
        """Regression: every GitHub Actions step literally contains `run:`.

        Matching the raw line meant the `run` kind resolved to whatever the
        first CI step happened to be — a system-dependency install was reported
        as the project's start command.
        """
        with TempRepo() as repo:
            repo.write("README.md", "# x\n")
            repo.write(
                ".github/workflows/ci.yml",
                "jobs:\n  b:\n    steps:\n"
                "      - run: sudo apt-get install -y libpq-dev\n"
                "      - run: echo done\n",
            )
            repo.commit()
            out = run("--repo", str(repo.path)).stdout
        self.assertIn("  run: NOT_FOUND", out)
        self.assertNotIn("apt-get", out)

    def test_ci_matches_the_command_text_when_it_genuinely_matches(self):
        with TempRepo() as repo:
            repo.write("README.md", "# x\n")
            repo.write(
                ".github/workflows/ci.yml",
                "jobs:\n  b:\n    steps:\n      - run: ./scripts/build.sh --release\n",
            )
            repo.commit()
            out = run("--repo", str(repo.path)).stdout
        self.assertIn("  build: ci (./scripts/build.sh --release)", out)

    def test_library_go_module_gets_no_run_command(self):
        """`go run .` needs a main package; a library module has none."""
        with TempRepo() as repo:
            repo.write("go.mod", "module lib\n\ngo 1.22\n")
            repo.write("lib.go", "package lib\n\nfunc F() {}\n")
            repo.commit()
            out = run("--repo", str(repo.path)).stdout
        self.assertIn("  run: NOT_FOUND", out)
        # Toolchain-guaranteed kinds still resolve.
        self.assertIn("  build: native (go build ./...)", out)
        self.assertIn("  test: native (go test ./...)", out)

    def test_go_main_package_gets_a_run_command(self):
        with TempRepo() as repo:
            repo.write("go.mod", "module app\n\ngo 1.22\n")
            repo.write("main.go", "package main\n\nfunc main() {}\n")
            repo.commit()
            out = run("--repo", str(repo.path)).stdout
        self.assertIn("  run: native (go run .)", out)

    def test_pytest_requires_evidence(self):
        """A Python project may use unittest. `pytest` is not a safe default."""
        with TempRepo() as repo:
            repo.write("pyproject.toml", "[project]\nname = \"x\"\n")
            repo.write("a.py", "x = 1\n")
            repo.commit()
            self.assertIn("  test: NOT_FOUND", run("--repo", str(repo.path)).stdout)

            repo.write("requirements.txt", "pytest>=8\n")
            repo.commit("add pytest")
            self.assertIn("  test: native (pytest)", run("--repo", str(repo.path)).stdout)

    def test_package_manager_follows_the_lockfile(self):
        for lockfile, install, runner in (
            ("pnpm-lock.yaml", "pnpm install", "pnpm run build"),
            ("yarn.lock", "yarn install", "yarn build"),
            ("package-lock.json", "npm install", "npm run build"),
        ):
            with self.subTest(lockfile=lockfile):
                with TempRepo() as repo:
                    repo.write(
                        "package.json",
                        '{\n  "scripts": {\n    "build": "tsc"\n  }\n}\n',
                    )
                    repo.write(lockfile, "\n")
                    repo.write("i.ts", "export const x = 1;\n")
                    repo.commit()
                    out = run("--repo", str(repo.path)).stdout
                self.assertIn(f"  install: native ({install})", out)
                self.assertIn(f"  build: package-scripts ({runner})", out)

    def test_no_lockfile_means_the_package_manager_is_unknown(self):
        with TempRepo() as repo:
            repo.write("package.json", '{\n  "scripts": {\n    "build": "tsc"\n  }\n}\n')
            repo.write("i.ts", "export const x = 1;\n")
            repo.commit()
            out = run("--repo", str(repo.path)).stdout
        self.assertIn("  install: NOT_FOUND", out)

    def test_module_resolution_follows_the_documented_priority(self):
        """A module with both a justfile (priority 2) and package scripts
        (priority 3) must resolve the overlapping kind to the justfile."""
        with TempRepo() as repo:
            repo.write("packages/ui/justfile", "test:\n\tvitest\n")
            repo.write(
                "packages/ui/package.json",
                '{\n  "scripts": {\n    "test": "vitest",\n    "build": "vite build"\n  }\n}\n',
            )
            repo.write("packages/ui/i.ts", "export const a = 1;\n")
            repo.commit()
            out = run("--repo", str(repo.path)).stdout
        self.assertIn("    test: justfile (just test)", out)
        self.assertIn("    build: package-scripts (npm run build)", out)

    def test_package_manager_run_subcommand_is_not_run_semantics(self):
        """Regression: `npm run build` was reported as BOTH build and run.

        The wrapper's own verb is not the project's run command — `npm run build`
        builds. Match the script name, not the raw text.
        """
        with TempRepo() as repo:
            repo.write("README.md", "# x\n")
            repo.write(
                ".github/workflows/ci.yml",
                "jobs:\n  b:\n    steps:\n"
                "      - run: npm run build\n"
                "      - run: pnpm run test\n"
                "      - run: yarn lint\n",
            )
            repo.commit()
            out = run("--repo", str(repo.path)).stdout
        self.assertIn("  build: ci (npm run build)", out)
        self.assertIn("  test: ci (pnpm run test)", out)
        self.assertIn("  lint: ci (yarn lint)", out)
        self.assertIn("  run: NOT_FOUND", out)

    def test_go_run_keeps_run_semantics_in_ci(self):
        """The stripping must not go too far: in `go run ./cmd/x` the verb IS
        the semantics, unlike a package manager's `run` subcommand."""
        with TempRepo() as repo:
            repo.write("README.md", "# x\n")
            repo.write(
                ".github/workflows/ci.yml",
                "jobs:\n  b:\n    steps:\n      - run: go run ./cmd/server\n",
            )
            repo.commit()
            out = run("--repo", str(repo.path)).stdout
        self.assertIn("  run: ci (go run ./cmd/server)", out)

    def test_workspace_members_outside_conventional_dirs(self):
        """go.work `use ./api` and Cargo `members` put modules outside
        packages/apps/services, where the directory scan cannot see them."""
        with TempRepo() as repo:
            repo.write("go.work", "go 1.22\n\nuse ./api\n")
            repo.write("api/go.mod", "module api\n")
            repo.write("api/main.go", "package main\n\nfunc main() {}\n")
            repo.write("Cargo.toml", '[workspace]\nmembers = ["crates/foo"]\n')
            repo.write("crates/foo/Cargo.toml", '[package]\nname = "foo"\n')
            repo.write("crates/foo/src/lib.rs", "pub fn f() {}\n")
            repo.commit()
            out = run("--repo", str(repo.path)).stdout
        self.assertIn("  api:", out)
        self.assertIn("  crates/foo:", out)
        # And still resolved per command, not labelled wholesale.
        self.assertIn("    run: native (go run .)", out)
        self.assertIn("    build: native (cargo build)", out)

    def test_pnpm_workspace_members_are_discovered(self):
        with TempRepo() as repo:
            repo.write("pnpm-workspace.yaml", "packages:\n  - lib/ui\n")
            repo.write("lib/ui/package.json", '{\n  "scripts": {\n    "build": "tsc"\n  }\n}\n')
            repo.write("lib/ui/i.ts", "export const a = 1;\n")
            repo.commit()
            out = run("--repo", str(repo.path)).stdout
        self.assertIn("  lib/ui:", out)
        self.assertIn("    build: package-scripts (npm run build)", out)

    def test_ci_command_chains_are_split_before_matching(self):
        """Regression: `cd frontend && npm run build` matched `run` again.

        Stripping only at the start of the string left the package manager's
        `run` in the middle of the chain. Split on shell separators, drop
        navigation-only and env-assignment segments, reduce each on its own.
        """
        with TempRepo() as repo:
            repo.write("README.md", "# x\n")
            repo.write(
                ".github/workflows/ci.yml",
                "jobs:\n  b:\n    steps:\n"
                "      - run: cd frontend && npm run build\n"
                "      - run: CI=true npm run test\n",
            )
            repo.commit()
            out = run("--repo", str(repo.path)).stdout
        self.assertIn("  build: ci (cd frontend && npm run build)", out)
        self.assertIn("  test: ci (CI=true npm run test)", out)
        self.assertIn("  run: NOT_FOUND", out)

    def test_go_run_inside_a_chain_keeps_run_semantics(self):
        with TempRepo() as repo:
            repo.write("README.md", "# x\n")
            repo.write(
                ".github/workflows/ci.yml",
                "jobs:\n  b:\n    steps:\n      - run: cd api && go run ./cmd/server\n",
            )
            repo.commit()
            out = run("--repo", str(repo.path)).stdout
        self.assertIn("  run: ci (cd api && go run ./cmd/server)", out)

    def test_cargo_workspace_exclude_is_honoured(self):
        """An excluded crate still has a Cargo.toml, so nothing downstream
        would filter it out on its own."""
        with TempRepo() as repo:
            repo.write("Cargo.toml", '[workspace]\nmembers = ["crates/*"]\nexclude = ["crates/old"]\n')
            for name in ("live", "old"):
                repo.write(f"crates/{name}/Cargo.toml", f'[package]\nname = "{name}"\n')
                repo.write(f"crates/{name}/src/lib.rs", "pub fn f() {}\n")
            repo.commit()
            out = run("--repo", str(repo.path)).stdout
        self.assertIn("  crates/live:", out)
        self.assertNotIn("  crates/old:", out)

    def test_pnpm_workspace_negation_is_honoured(self):
        with TempRepo() as repo:
            repo.write("pnpm-workspace.yaml", 'packages:\n  - packages/*\n  - "!packages/legacy"\n')
            for name in ("live", "legacy"):
                repo.write(f"packages/{name}/package.json", '{\n  "scripts": {\n    "build": "x"\n  }\n}\n')
                repo.write(f"packages/{name}/i.ts", "export const a = 1;\n")
            repo.commit()
            out = run("--repo", str(repo.path)).stdout
        self.assertIn("  packages/live:", out)
        self.assertNotIn("  packages/legacy:", out)

    def test_multiline_yaml_run_blocks_are_extracted(self):
        """Regression: `run: |` bodies were invisible.

        Reading only the same line as the key missed every multi-line step,
        which is the common shape for anything beyond a single command.
        """
        with TempRepo() as repo:
            repo.write("README.md", "# x\n")
            repo.write(
                ".github/workflows/ci.yml",
                "jobs:\n  b:\n    steps:\n"
                "      - run: |\n"
                "          npm run build\n"
                "          npm run test\n"
                "      - run: yarn lint\n",
            )
            repo.commit()
            out = run("--repo", str(repo.path)).stdout
        self.assertIn("  build: ci (npm run build)", out)
        self.assertIn("  test: ci (npm run test)", out)
        self.assertIn("  lint: ci (yarn lint)", out)
        self.assertIn("  run: NOT_FOUND", out)

    def test_gitlab_script_lists_are_extracted(self):
        """The script lists .gitlab-ci.yml as CI, so it must read its syntax
        rather than only GitHub Actions' `run:`."""
        with TempRepo() as repo:
            repo.write("README.md", "# x\n")
            repo.write(
                ".gitlab-ci.yml",
                "build-job:\n  script:\n    - npm run build\n    - npm run test\n",
            )
            repo.commit()
            out = run("--repo", str(repo.path)).stdout
        self.assertIn("  build: ci (npm run build)", out)
        self.assertIn("  test: ci (npm run test)", out)

    def test_workspaces_parsing_does_not_depend_on_formatting(self):
        for label, manifest in (
            ("single-line", '{"workspaces":["libs/a"]}\n'),
            ("multi-line", '{\n  "workspaces": [\n    "libs/a"\n  ]\n}\n'),
            ("object-form", '{\n  "workspaces": {\n    "packages": ["libs/a"]\n  }\n}\n'),
        ):
            with self.subTest(form=label):
                with TempRepo() as repo:
                    repo.write("package.json", manifest)
                    repo.write("libs/a/package.json", '{"scripts":{"build":"tsc"}}\n')
                    repo.write("libs/a/i.ts", "export const a = 1;\n")
                    repo.commit()
                    out = run("--repo", str(repo.path)).stdout
                self.assertIn("  libs/a:", out)

    def test_scripts_parsing_does_not_depend_on_formatting(self):
        for label, manifest in (
            ("minified", '{"name":"a","scripts":{"build":"tsc","test":"vitest"}}\n'),
            ("expanded", '{\n  "scripts": {\n    "build": "tsc",\n    "test": "vitest"\n  }\n}\n'),
        ):
            with self.subTest(form=label):
                with TempRepo() as repo:
                    repo.write("package.json", manifest)
                    repo.write("package-lock.json", "{}\n")
                    repo.write("i.ts", "export const x = 1;\n")
                    repo.commit()
                    out = run("--repo", str(repo.path)).stdout
                self.assertIn("  build: package-scripts (npm run build)", out)
                self.assertIn("  test: package-scripts (npm run test)", out)

    def test_doc_ci_detected_only_when_a_doc_check_runs(self):
        with TempRepo() as repo:
            repo.write("README.md", "# x\n")
            repo.write(".github/workflows/ci.yml", "jobs:\n  t:\n    steps:\n      - run: go test ./...\n")
            repo.commit()
            proc = run("--repo", str(repo.path))
        self.assertEqual(field(proc.stdout, "DOC_CI"), "absent")

        with TempRepo() as repo:
            repo.write("README.md", "# x\n")
            repo.write(".github/workflows/ci.yml", "jobs:\n  t:\n    steps:\n      - run: lychee README.md\n")
            repo.commit()
            proc = run("--repo", str(repo.path))
        self.assertEqual(field(proc.stdout, "DOC_CI"), "present")


if __name__ == "__main__":
    unittest.main()
