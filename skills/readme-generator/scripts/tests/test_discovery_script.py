"""Behavioral tests for scripts/discover_readme_needs.sh.

Probe-script contract: most probes finding nothing is a NORMAL outcome, not an
error. The script must always run to completion, print a verdict section, and
exit 0 — regardless of how sparse the repository is.

Regression origin (2026-07-08 audit): the script shipped with `set -euo
pipefail` and unguarded `var=$(grep … | pipe)` assignments, which killed it
silently (exit 1, empty stderr, truncated TSV, no verdict section) on three
common repo shapes: a Makefile with no plain targets, a comment-only
`.env.example`, and a workflows dir containing only `.yaml` files. Same defect
class previously fixed in go-ci-workflow and go-makefile-writer discovery
scripts. These tests exercise the script against real fixture directories so
the crash class cannot silently return.

Uses stdlib only (subprocess/tempfile/unittest) — no new test dependencies.
"""

import re
import subprocess
import tempfile
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[2]
SKILL_MD = SKILL_DIR / "SKILL.md"
SCRIPT = SKILL_DIR / "scripts" / "discover_readme_needs.sh"


def run_script(cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=60,
    )


class DiscoveryScriptBehavior(unittest.TestCase):
    """Run the script against fixture repos; it must never die mid-probe."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def assert_completes(self, proc: subprocess.CompletedProcess) -> None:
        self.assertEqual(
            proc.returncode, 0,
            f"script must exit 0 on sparse evidence; stderr={proc.stderr!r}",
        )
        self.assertIn(
            "=== discovery complete ===", proc.stdout,
            "completion marker missing — script died mid-probe (truncated TSV)",
        )
        self.assertRegex(
            proc.stdout, r"verdict\tstatus\t(READY|DEGRADED)",
            "verdict section missing — consumers cannot trust partial output",
        )

    def test_empty_dir_degrades_gracefully(self) -> None:
        proc = run_script(self.repo)
        self.assert_completes(proc)
        self.assertIn("verdict\tstatus\tDEGRADED", proc.stdout)
        self.assertIn("no build system detected", proc.stdout)

    def test_makefile_without_targets(self) -> None:
        """Empty Makefile: grep finds no targets — must not kill the script."""
        (self.repo / "Makefile").write_text("")
        (self.repo / "go.mod").write_text("module example.com/x\n\ngo 1.22\n")
        proc = run_script(self.repo)
        self.assert_completes(proc)
        self.assertIn("build\tmakefile\ttrue", proc.stdout)
        self.assertIn("build\tmake_targets\tnone", proc.stdout)

    def test_env_example_with_only_comments(self) -> None:
        """Comment-only .env.example: zero variable matches — must not crash."""
        (self.repo / ".env.example").write_text("# no vars here yet\n")
        (self.repo / "go.mod").write_text("module example.com/x\n\ngo 1.22\n")
        proc = run_script(self.repo)
        self.assert_completes(proc)
        self.assertIn("config\tenv_example\ttrue", proc.stdout)
        self.assertIn("config\tenv_vars\tnone", proc.stdout)

    def test_workflows_with_only_yaml_extension(self) -> None:
        """.yaml-only workflows dir: the old ls-glob probe crashed; find must list them."""
        wf = self.repo / ".github" / "workflows"
        wf.mkdir(parents=True)
        (wf / "ci.yaml").write_text("name: ci\n")
        (self.repo / "go.mod").write_text("module example.com/x\n\ngo 1.22\n")
        proc = run_script(self.repo)
        self.assert_completes(proc)
        self.assertIn("ci\tgithub_actions\ttrue", proc.stdout)
        self.assertIn("ci\tworkflow_file\t.github/workflows/ci.yaml", proc.stdout)

    def test_go_service_detected_ready(self) -> None:
        (self.repo / "cmd" / "app").mkdir(parents=True)
        (self.repo / "cmd" / "app" / "main.go").write_text("package main\n")
        (self.repo / "internal").mkdir()
        (self.repo / "go.mod").write_text("module example.com/x\n\ngo 1.22\n")
        (self.repo / "Makefile").write_text("build:\n\tgo build ./...\n\ntest:\n\tgo test ./...\n")
        proc = run_script(self.repo)
        self.assert_completes(proc)
        self.assertIn("project_type\tdetected\tservice", proc.stdout)
        self.assertIn("verdict\tstatus\tREADY", proc.stdout)
        self.assertIn("language\tgo\t1.22", proc.stdout)
        self.assertIn("build\tmake_targets\tbuild,test", proc.stdout)

    def test_gpl_license_detected(self) -> None:
        """First line of GPL has no contiguous 'GPL' substring — spelled-out form must match."""
        (self.repo / "LICENSE").write_text("GNU GENERAL PUBLIC LICENSE\nVersion 3, 29 June 2007\n")
        (self.repo / "go.mod").write_text("module example.com/x\n\ngo 1.22\n")
        proc = run_script(self.repo)
        self.assert_completes(proc)
        self.assertIn("community\tlicense_type\tGPL", proc.stdout)

    def test_tsv_key_spelling(self) -> None:
        """The codecov key was once misspelled 'codeov' in the true-branch only."""
        (self.repo / ".codecov.yml").write_text("coverage: {}\n")
        (self.repo / "go.mod").write_text("module example.com/x\n\ngo 1.22\n")
        proc = run_script(self.repo)
        self.assert_completes(proc)
        self.assertIn("quality\tcodecov\ttrue", proc.stdout)
        self.assertNotIn("codeov\t", proc.stdout)


class RoutingRegressions(unittest.TestCase):
    """Repo shapes the router got wrong before the 2026-07-28 audit.

    Every case here was reproduced against the old script first: Rust and Python
    repos fell through to `unknown`/DEGRADED because only Go and Node signals were
    consulted; `has_packages` was computed and never read; a root-level `main.go`
    routed to `library`; a `cmd/` directory with no `main.go` asserted `service`;
    and `package.json` was classified by grepping raw text for `"bin"`.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def write(self, rel: str, body: str = "") -> Path:
        p = self.repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)
        return p

    def detected(self) -> str:
        proc = run_script(self.repo)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        m = re.search(r"project_type\tdetected\t(\S+)", proc.stdout)
        self.assertIsNotNone(m, f"no project_type line in output:\n{proc.stdout}")
        return m.group(1)

    def entrypoint_count(self) -> int:
        proc = run_script(self.repo)
        m = re.search(r"entrypoint\tcount\t(\d+)", proc.stdout)
        self.assertIsNotNone(m, f"no entrypoint count in output:\n{proc.stdout}")
        return int(m.group(1))

    # ── Rust ────────────────────────────────────────────────────
    def test_rust_binary_is_cli(self) -> None:
        self.write("Cargo.toml", '[package]\nname = "tool"\nversion = "0.1.0"\n')
        self.write("src/main.rs", "fn main() {}\n")
        self.assertEqual(self.detected(), "cli")

    def test_rust_library_is_library(self) -> None:
        self.write("Cargo.toml", '[package]\nname = "lib"\nversion = "0.1.0"\n')
        self.write("src/lib.rs", "pub fn f() {}\n")
        self.assertEqual(self.detected(), "library")

    def test_rust_workspace_is_monorepo(self) -> None:
        self.write("Cargo.toml", '[workspace]\nmembers = ["crates/a"]\n')
        self.write("crates/a/Cargo.toml", '[package]\nname = "a"\n')
        self.assertEqual(self.detected(), "monorepo")

    # ── Python ──────────────────────────────────────────────────
    def test_python_package_is_library(self) -> None:
        self.write("pyproject.toml", '[project]\nname = "pkg"\nrequires-python = ">=3.11"\n')
        self.assertEqual(self.detected(), "library")

    def test_python_console_script_is_cli(self) -> None:
        self.write("pyproject.toml",
                   '[project]\nname = "pkg"\n\n[project.scripts]\npkg = "pkg.__main__:main"\n')
        self.assertEqual(self.detected(), "cli")

    def test_django_style_is_service(self) -> None:
        self.write("pyproject.toml", '[project]\nname = "site"\n')
        self.write("manage.py", "#!/usr/bin/env python\n")
        self.assertEqual(self.detected(), "service")

    # ── Monorepo via packages/ only ─────────────────────────────
    def test_packages_only_monorepo(self) -> None:
        """`has_packages` was assigned and never read — packages/-only repos
        fell through to the single-module heuristics."""
        self.write("package.json", '{"name": "root", "private": true}')
        self.write("packages/core/package.json", '{"name": "core", "main": "index.js"}')
        self.write("packages/cli/package.json", '{"name": "cli", "bin": {"cli": "./b.js"}}')
        self.assertEqual(self.detected(), "monorepo")
        self.assertGreaterEqual(self.entrypoint_count(), 2,
                                "monorepo entrypoints live in the modules, not the root")

    def test_npm_workspaces_is_monorepo(self) -> None:
        self.write("package.json", '{"name": "root", "workspaces": ["libs/*"]}')
        self.write("libs/a/package.json", '{"name": "a", "main": "i.js"}')
        self.assertEqual(self.detected(), "monorepo")

    def test_single_packages_subdir_is_not_monorepo(self) -> None:
        """One directory under packages/ is a layout choice, not a workspace."""
        self.write("go.mod", "module example.com/x\n\ngo 1.22\n")
        self.write("main.go", "package main\n")
        self.write("packages/only/thing.go", "package only\n")
        self.assertNotEqual(self.detected(), "monorepo")

    # ── Go entrypoint shapes ────────────────────────────────────
    def test_root_main_go_is_binary_not_library(self) -> None:
        self.write("go.mod", "module example.com/tool\n\ngo 1.22\n")
        self.write("main.go", "package main\n\nfunc main() {}\n")
        self.assertEqual(self.detected(), "cli")

    def test_root_main_go_with_internal_is_service(self) -> None:
        self.write("go.mod", "module example.com/svc\n\ngo 1.22\n")
        self.write("main.go", "package main\n\nfunc main() {}\n")
        self.write("internal/handler/h.go", "package handler\n")
        self.assertEqual(self.detected(), "service")

    def test_cmd_dir_without_main_go_is_not_service(self) -> None:
        """An empty/placeholder cmd/ used to assert `service` with no entrypoint."""
        self.write("go.mod", "module example.com/x\n\ngo 1.22\n")
        (self.repo / "cmd").mkdir()
        self.assertNotEqual(self.detected(), "service")
        self.assertEqual(self.entrypoint_count(), 0)

    def test_go_library_has_package_entrypoint(self) -> None:
        self.write("go.mod", "module example.com/lib\n\ngo 1.22\n")
        self.write("pkg/validate/v.go", "package validate\n")
        self.assertEqual(self.detected(), "library")
        self.assertGreaterEqual(self.entrypoint_count(), 1)

    # ── package.json parsed, not grepped ────────────────────────
    def test_package_json_bin_object_is_cli(self) -> None:
        self.write("package.json", '{"name": "t", "bin": {"t": "./cli.js"}}')
        self.assertEqual(self.detected(), "cli")

    def test_package_json_dependency_named_bin_is_not_cli(self) -> None:
        """grep '\"bin\"' matched dependency names and nested config blocks."""
        self.write("package.json",
                   '{"name": "t", "main": "index.js", "dependencies": {"bin-links": "^1.0.0"}}')
        self.assertEqual(self.detected(), "library")

    def test_package_json_directories_bin_is_not_cli(self) -> None:
        self.write("package.json",
                   '{"name": "t", "exports": "./i.js", "directories": {"bin": "./scripts"}}')
        self.assertEqual(self.detected(), "library")

    def test_malformed_package_json_does_not_crash(self) -> None:
        self.write("package.json", "{ not json ")
        proc = run_script(self.repo)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("=== discovery complete ===", proc.stdout)

    # ── CI / license probes ─────────────────────────────────────
    def test_empty_workflows_dir_is_not_github_actions(self) -> None:
        """A CI badge needs a workflow file, not just the directory."""
        (self.repo / ".github" / "workflows").mkdir(parents=True)
        self.write("go.mod", "module example.com/x\n\ngo 1.22\n")
        self.write("main.go", "package main\n")
        proc = run_script(self.repo)
        self.assertIn("ci\tgithub_actions\tfalse", proc.stdout)
        self.assertIn("workflows dir exists but contains no workflow file", proc.stdout)

    def test_license_md_gets_a_license_type(self) -> None:
        """LICENSE.md was reported present but never classified."""
        self.write("LICENSE.md", "MIT License\n\nCopyright (c) 2026\n")
        self.write("go.mod", "module example.com/x\n\ngo 1.22\n")
        self.write("main.go", "package main\n")
        proc = run_script(self.repo)
        self.assertIn("community\tlicense_file\tLICENSE.md", proc.stdout)
        self.assertIn("community\tlicense_type\tMIT", proc.stdout)

    # ── Entrypoint gate ─────────────────────────────────────────
    def test_no_entrypoint_blocks_the_verdict(self) -> None:
        """SKILL.md §Evidence Completeness Gate requires an entrypoint; the
        verdict only checked project type and build system, so the gate could
        never actually fire."""
        self.write("Makefile", "build:\n\techo hi\n")
        proc = run_script(self.repo)
        self.assertIn("entrypoint\tcount\t0", proc.stdout)
        self.assertIn("verdict\tstatus\tDEGRADED", proc.stdout)
        self.assertIn("no entrypoint identified", proc.stdout)

    def test_unknown_type_is_never_promoted_to_lightweight(self) -> None:
        """Lightweight is a presentation mode for a project we classified. Promoting an
        unclassifiable repo would hand the linter a required-section list for a type
        nobody established — and it made the "unknown" branch untestable."""
        self.write("notes.txt", "nothing a manifest can classify\n")
        proc = run_script(self.repo)
        self.assertIn("project_type\tdetected\tunknown", proc.stdout)
        self.assertIn("project_type\teffective\tunknown", proc.stdout)

    def test_public_go_library_is_never_auto_promoted(self) -> None:
        """The reported failure: `go.mod` + `pkg/`, no CI, few directories — a public Go
        SDK — was silently downgraded to lightweight and lost Installation and API.
        Absence of CI is not evidence of absence of users."""
        self.write("go.mod", "module github.com/acme/sdk\n\ngo 1.22\n")
        self.write("pkg/client.go", "package pkg\n\nfunc New() {}\n")
        proc = run_script(self.repo)
        self.assertIn("project_type\tdetected\tlibrary", proc.stdout)
        self.assertIn("project_type\teffective\tlibrary", proc.stdout)
        self.assertIn("project_type\tlightweight_eligible\tfalse", proc.stdout)
        self.assertIn("public distribution surface", proc.stdout)

    def test_discovery_never_promotes_on_its_own(self) -> None:
        """Three of the four lightweight triggers are mechanical; the fourth — audience
        is internal — is a judgement no probe can make. The script reports eligibility;
        the Audience Gate decides and records it with `--type=lightweight`."""
        self.write("go.mod", "module example.com/x\n\ngo 1.22\n")
        self.write("main.go", "package main\n")
        proc = run_script(self.repo)
        self.assertIn("project_type\tlightweight_eligible\ttrue", proc.stdout)
        self.assertIn("project_type\teffective\tcli", proc.stdout,
                      "eligible is not the same as promoted")

    def test_blockers_are_named_individually(self) -> None:
        self.write("go.mod", "module example.com/x\n\ngo 1.22\n")
        self.write("main.go", "package main\n")
        self.write(".github/workflows/ci.yml", "name: ci\n")
        self.write("Dockerfile", "FROM scratch\n")
        proc = run_script(self.repo)
        self.assertIn("CI present", proc.stdout)
        self.assertIn("deployment surface", proc.stdout)

    def test_small_repo_with_ci_is_not_eligible(self) -> None:
        self.write("go.mod", "module example.com/x\n\ngo 1.22\n")
        self.write("main.go", "package main\n")
        self.write(".github/workflows/ci.yml", "name: ci\n")
        proc = run_script(self.repo)
        self.assertIn("project_type\tlightweight_eligible\tfalse", proc.stdout)

    def test_small_repo_with_deploy_surface_is_not_eligible(self) -> None:
        self.write("go.mod", "module example.com/x\n\ngo 1.22\n")
        self.write("main.go", "package main\n")
        self.write("Dockerfile", "FROM scratch\n")
        proc = run_script(self.repo)
        self.assertIn("project_type\tlightweight_eligible\tfalse", proc.stdout)

    def test_published_package_is_not_eligible(self) -> None:
        """A package declaring `bin` has external consumers; its README is a homepage."""
        self.write("package.json", '{"name": "t", "bin": {"t": "./cli.js"}}')
        self.write("cli.js", "#!/usr/bin/env node\n")
        proc = run_script(self.repo)
        self.assertIn("project_type\thas_public_surface\ttrue", proc.stdout)
        self.assertIn("project_type\tlightweight_eligible\tfalse", proc.stdout)

    def test_verdict_reports_the_effective_type(self) -> None:
        """The verdict line is what consumers read, so it carries `effective`. Since the
        script no longer promotes, effective equals detected — the field still exists
        because `--type=` writes into it, keeping one value everything downstream reads."""
        self.write("go.mod", "module example.com/x\n\ngo 1.22\n")
        self.write("main.go", "package main\n")
        proc = run_script(self.repo)
        self.assertIn("verdict\tproject_type\tcli", proc.stdout)
        self.assertIn("verdict\tbase_type\tcli", proc.stdout)

    def test_cargo_workspace_with_crates_reaches_ready(self) -> None:
        """Routing said monorepo; the entrypoint scan walked only apps/, packages/,
        services/, so a crates/* workspace degraded on its own correct classification."""
        self.write("Cargo.toml", '[workspace]\nmembers = ["crates/*"]\n')
        self.write("crates/core/Cargo.toml", '[package]\nname = "core"\n')
        self.write("crates/core/src/lib.rs", "pub fn f() {}\n")
        self.write("crates/cli/Cargo.toml", '[package]\nname = "cli"\n')
        self.write("crates/cli/src/main.rs", "fn main() {}\n")
        proc = run_script(self.repo)
        self.assertIn("project_type\tdetected\tmonorepo", proc.stdout)
        self.assertIn("entrypoint\tmodule\tcrates/core", proc.stdout)
        self.assertIn("entrypoint\tmodule\tcrates/cli", proc.stdout)
        self.assertIn("verdict\tstatus\tREADY", proc.stdout)

    def test_go_workspace_root_counts_as_build_system(self) -> None:
        self.write("go.work", "go 1.22\n\nuse ./apps/svc\n")
        self.write("apps/svc/go.mod", "module svc\n\ngo 1.22\n")
        self.write("apps/svc/main.go", "package main\n")
        proc = run_script(self.repo)
        self.assertIn("verdict\tstatus\tREADY", proc.stdout)


class DiscoveryScriptContract(unittest.TestCase):
    """Static guards: keep the probe-script robustness rules from regressing."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.script_text = SCRIPT.read_text()

    def test_no_errexit_or_pipefail(self) -> None:
        """Probe scripts must not use errexit/pipefail: empty probe results are
        normal outcomes. Checks executable `set` lines only, so comments
        discussing the rule do not trip the assertion."""
        set_lines = [
            line.strip()
            for line in self.script_text.splitlines()
            if line.strip().startswith("set ")
        ]
        self.assertTrue(set_lines, "expected at least `set -u`")
        for line in set_lines:
            code = line.split("#", 1)[0]
            self.assertNotRegex(
                code, r"-\w*e|errexit|pipefail",
                f"errexit/pipefail found in probe script: {line!r} — "
                "empty probes would kill the script mid-TSV",
            )

    def test_set_u_present(self) -> None:
        self.assertRegex(self.script_text, r"(?m)^set -u\s*$")

    def test_explicit_exit_zero(self) -> None:
        last_line = self.script_text.rstrip().splitlines()[-1].strip()
        self.assertEqual(
            "exit 0", last_line,
            "probe script must end with explicit `exit 0` so a trailing failed "
            "probe cannot set a non-zero exit status",
        )


class TestRoutingSync(unittest.TestCase):
    """Project-type routing exists in two places (SKILL.md prose + bash logic).
    Guard against one-sided edits — the drift twin of the security-review
    suppression-rules incident."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.script_text = SCRIPT.read_text()
        cls.skill_text = SKILL_MD.read_text()

    def test_script_emits_every_documented_project_type(self) -> None:
        emitted = set(re.findall(r'project_type="(\w+)"', self.script_text))
        for doc_type in ("service", "library", "cli", "monorepo"):
            self.assertIn(
                doc_type, emitted,
                f"SKILL.md §Project Type Routing documents {doc_type!r} but the "
                "discovery script never emits it",
            )
        self.assertIn(
            "lightweight_candidate", self.script_text,
            "SKILL.md documents lightweight mode but script has no lightweight probe",
        )

    def test_documented_types_cover_script_emissions(self) -> None:
        emitted = set(re.findall(r'project_type="(\w+)"', self.script_text))
        emitted.discard("unknown")  # unknown maps to the degraded path, not a template
        # Anchor on the section heading, not the Quick Reference table mention
        routing_start = self.skill_text.index("### 2) Project Type Routing")
        routing_section = self.skill_text[routing_start : routing_start + 600]
        for script_type in emitted:
            self.assertIn(
                script_type.lower(),
                routing_section.lower(),
                f"script emits project_type={script_type!r} but SKILL.md "
                "§Project Type Routing does not document it",
            )


if __name__ == "__main__":
    unittest.main()
