"""Integration tests for scripts/discover_e2e_needs.sh.

COVERAGE.md previously listed "discover_e2e_needs.sh not integration-tested" as a
known gap: the script was only checked for existence and for containing certain
strings. That is how it shipped with a `set -e` abort that truncated the report,
and with verdict logic that declared a public documentation site "blocked".

These tests build throwaway repositories and run the real script against them.
"""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[2]
SCRIPT = SKILL_DIR / "scripts" / "discover_e2e_needs.sh"


def run_script(root: Path) -> subprocess.CompletedProcess:
    # Scrub inherited E2E_* so a developer's own shell cannot flip a verdict and
    # make these tests pass or fail for reasons unrelated to the fixture.
    env = {k: v for k, v in os.environ.items() if not k.startswith("E2E_")}
    return subprocess.run(
        ["bash", str(SCRIPT), str(root)],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )


def parse_report(stdout: str) -> dict:
    fields = {}
    for line in stdout.split("\n"):
        if "\t" in line:
            key, _, value = line.partition("\t")
            fields[key.strip()] = value.strip()
    return fields


class DiscoverScriptTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="e2e-discover-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def write(self, rel: str, content: str) -> None:
        path = self.tmp / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def report(self) -> dict:
        proc = run_script(self.tmp)
        self.assertEqual(
            0, proc.returncode, f"scan aborted (rc={proc.returncode}): {proc.stderr}"
        )
        self.assertIn("=== End Report ===", proc.stdout, "report was truncated")
        return parse_report(proc.stdout)


class TestScanNeverAborts(DiscoverScriptTestCase):
    """A probe must always produce a complete report."""

    def test_empty_directory(self) -> None:
        fields = self.report()
        self.assertEqual("unknown", fields["project_type"])

    def test_makefile_without_e2e_target(self) -> None:
        """The regression that motivated dropping `set -e`.

        `grep -oE '...e2e...:' Makefile` exits 1 when no target matches. Under
        `set -e` that killed the script mid-report, right after the go section
        header — indistinguishable from "found nothing else".
        """
        self.write("go.mod", "module x\ngo 1.22\n")
        self.write("Makefile", "build:\n\tgo build ./...\n")
        fields = self.report()
        self.assertEqual("none", fields["go_makefile_e2e_targets"])
        self.assertIn("readiness", fields)

    def test_makefile_with_e2e_target(self) -> None:
        self.write("go.mod", "module x\ngo 1.22\n")
        self.write("Makefile", "e2e-test:\n\tgo test ./tests/e2e\n")
        fields = self.report()
        self.assertIn("e2e-test", fields["go_makefile_e2e_targets"])

    def test_nonexistent_root_exits_2(self) -> None:
        proc = run_script(self.tmp / "does-not-exist")
        self.assertEqual(2, proc.returncode)

    def test_report_is_complete_for_every_fixture_shape(self) -> None:
        required = [
            "playwright_version",
            "node_version",
            "framework",
            "workspace",
            "go_mod",
            "e2e_directory",
            "E2E_BASE_URL",
            "dev_command",
            "ci_platform",
            "axe_core",
            "project_type",
            "suggested_runner",
            "blockers",
            "unknowns",
            "readiness",
        ]
        fields = self.report()
        for key in required:
            self.assertIn(key, fields, f"empty repo report missing {key}")


class TestNoFalseBlockers(DiscoverScriptTestCase):
    """`blocked` must mean "cannot produce a runnable test", nothing weaker.

    Every case here previously reported `readiness blocked`.
    """

    def test_public_site_with_base_url_in_config(self) -> None:
        """A docs site needs no login, and baseURL lives in the config."""
        self.write(
            "package.json",
            '{"devDependencies":{"@playwright/test":"1.55.0"},"scripts":{"dev":"vite"}}',
        )
        self.write(
            "playwright.config.ts",
            'export default { use: { baseURL: "https://docs.example.com" } };\n',
        )
        fields = self.report()
        self.assertEqual("true", fields["base_url_in_playwright_config"])
        self.assertEqual("none", fields["blockers"])
        self.assertNotEqual("blocked", fields["readiness"])

    def test_missing_account_is_an_unknown_not_a_blocker(self) -> None:
        self.write(
            "package.json", '{"devDependencies":{"@playwright/test":"1.55.0"}}'
        )
        self.write(
            "playwright.config.ts",
            'export default { use: { baseURL: "http://localhost:3000" } };\n',
        )
        fields = self.report()
        self.assertEqual("none", fields["blockers"])
        self.assertIn("no_test_account", fields["unknowns"])

    def test_web_server_config_satisfies_base_url(self) -> None:
        self.write(
            "package.json", '{"devDependencies":{"@playwright/test":"1.55.0"}}'
        )
        self.write(
            "playwright.config.ts",
            'export default { webServer: { command: "npm run dev", '
            'url: "http://localhost:3000" } };\n',
        )
        fields = self.report()
        self.assertEqual("true", fields["web_server_in_config"])
        self.assertNotIn("no_base_url", fields["blockers"])

    def test_fully_configured_project_is_ready(self) -> None:
        self.write(
            "package.json",
            '{"devDependencies":{"@playwright/test":"1.55.0"},"scripts":{"dev":"vite"}}',
        )
        self.write(
            "playwright.config.ts",
            'export default { use: { baseURL: "http://localhost:3000" }, '
            'webServer: { command: "npm run dev", url: "http://localhost:3000" } };\n',
        )
        self.write(".env", "E2E_BASE_URL=http://localhost:3000\nE2E_USER=u\nE2E_PASS=p\n")
        fields = self.report()
        self.assertEqual("ready", fields["readiness"])
        self.assertEqual("none", fields["blockers"])
        self.assertEqual("none", fields["unknowns"])


class TestProjectClassification(DiscoverScriptTestCase):
    def test_go_module_without_cmd_entrypoint(self) -> None:
        """Previously reported `unknown_project_type` despite a go.mod."""
        self.write("go.mod", "module x\ngo 1.22\n")
        fields = self.report()
        self.assertEqual("go", fields["project_type"])
        self.assertEqual("go_net_http", fields["suggested_runner"])

    def test_go_web_service_detected(self) -> None:
        self.write("go.mod", "module x\ngo 1.22\n")
        self.write(
            "cmd/server/main.go",
            'package main\n\nimport "net/http"\n\nfunc main() { http.ListenAndServe(":8080", nil) }\n',
        )
        fields = self.report()
        self.assertEqual("go_web", fields["project_type"])
        self.assertEqual("server", fields["go_web_cmd"])

    def test_go_root_main_detected(self) -> None:
        self.write("go.mod", "module x\ngo 1.22\n")
        self.write(
            "main.go",
            'package main\n\nimport "net/http"\n\nfunc main() { http.ListenAndServe(":8080", nil) }\n',
        )
        fields = self.report()
        self.assertEqual("root_main.go", fields["go_web_cmd"])

    def test_python_web_project(self) -> None:
        self.write("requirements.txt", "fastapi\nuvicorn\n")
        fields = self.report()
        self.assertEqual("python_web", fields["project_type"])
        self.assertEqual("pytest+httpx", fields["suggested_runner"])

    def test_rust_web_project(self) -> None:
        self.write("Cargo.toml", '[dependencies]\naxum = "0.7"\n')
        fields = self.report()
        self.assertEqual("rust_web", fields["project_type"])

    def test_tauri_routed_away_from_playwright(self) -> None:
        self.write(
            "package.json",
            '{"dependencies":{"react":"18.0.0","@tauri-apps/api":"2.0.0"}}',
        )
        fields = self.report()
        self.assertEqual("tauri", fields["framework"])
        self.assertEqual("tauri_desktop", fields["project_type"])
        self.assertIn("wdio", fields["suggested_runner"])

    def test_existing_cypress_runner_respected(self) -> None:
        """Recommending Playwright alongside an in-use runner is wrong."""
        self.write("package.json", '{"devDependencies":{"cypress":"13.0.0"}}')
        fields = self.report()
        self.assertEqual("cypress", fields["other_e2e_runner"])
        self.assertEqual("cypress", fields["suggested_runner"])
        self.assertIn("existing_runner_cypress", fields["unknowns"])

    def test_dependency_match_is_exact_not_substring(self) -> None:
        """`next-auth` must not register as Next.js, nor `react-native` as react."""
        self.write("package.json", '{"dependencies":{"next-auth":"4.0.0"}}')
        fields = self.report()
        self.assertNotIn("nextjs", fields["framework"])

    def test_nextjs_app_router_detected(self) -> None:
        self.write("package.json", '{"dependencies":{"next":"14.0.0"}}')
        (self.tmp / "app").mkdir()
        fields = self.report()
        self.assertEqual("nextjs-app-router", fields["framework"])

    def test_monorepo_flagged(self) -> None:
        self.write("package.json", '{"workspaces":["packages/*"]}')
        fields = self.report()
        self.assertEqual("npm-workspaces", fields["workspace"])


class TestSecretHandling(DiscoverScriptTestCase):
    def test_report_never_contains_a_secret_value(self) -> None:
        self.write(
            ".env",
            "E2E_BASE_URL=http://localhost:3000\n"
            "E2E_USER=real-user@example.com\n"
            "E2E_PASS=SuperSecret123\n",
        )
        proc = run_script(self.tmp)
        self.assertEqual(0, proc.returncode)
        self.assertNotIn("SuperSecret123", proc.stdout)
        self.assertNotIn("SuperSecret123", proc.stderr)
        self.assertNotIn("real-user@example.com", proc.stdout)
        fields = parse_report(proc.stdout)
        self.assertEqual("available", fields["E2E_PASS"])

    def test_env_example_is_declared_not_available(self) -> None:
        """A template proves the variable is expected, not that a value exists.

        This test previously asserted `available` for an empty `.env.example`,
        pinning the wrong behaviour: the verdict logic reads `available` to clear
        the `no_base_url` blocker, so a template with no values could make a
        project report `ready` when nothing could actually run.
        """
        self.write(".env.example", "E2E_BASE_URL=\nE2E_USER=\nE2E_PASS=\n")
        fields = self.report()
        self.assertEqual("declared", fields["E2E_BASE_URL"])
        self.assertEqual("declared", fields["E2E_USER"])
        self.assertEqual("declared", fields["E2E_PASS"])

    def test_filled_env_example_still_only_declared(self) -> None:
        """Even a filled-in template is documentation, not configuration."""
        self.write(".env.example", "E2E_BASE_URL=http://example.test\n")
        fields = self.report()
        self.assertEqual("declared", fields["E2E_BASE_URL"])

    def test_empty_value_in_real_env_is_declared(self) -> None:
        self.write(".env", "E2E_BASE_URL=http://localhost:3000\nE2E_PASS=\n")
        fields = self.report()
        self.assertEqual("available", fields["E2E_BASE_URL"])
        self.assertEqual("declared", fields["E2E_PASS"])

    def test_real_value_is_available(self) -> None:
        self.write(".env", "E2E_BASE_URL=http://localhost:3000\nE2E_PASS=s3cret\n")
        fields = self.report()
        self.assertEqual("available", fields["E2E_PASS"])

    def test_quoted_value_is_available(self) -> None:
        self.write(".env", 'E2E_PASS="s3cret"\n')
        self.assertEqual("available", self.report()["E2E_PASS"])

    def test_absent_variable_is_missing(self) -> None:
        self.write(".env", "UNRELATED=1\n")
        self.assertEqual("missing", self.report()["E2E_PASS"])

    def test_export_prefix_recognised(self) -> None:
        self.write(".env", "export E2E_PASS=s3cret\n")
        self.assertEqual("available", self.report()["E2E_PASS"])

    def test_inline_comment_after_empty_value_is_declared(self) -> None:
        """`E2E_PASS= # TODO: inject from vault` supplies no value.

        Stripping only whitespace and quotes left "#TODO:injectfromvault", which
        is non-empty, so this was reported `available` — the strongest state, for
        a line that explicitly says the value is missing.
        """
        self.write(".env", "E2E_PASS= # TODO: inject from vault\n")
        self.assertEqual("declared", self.report()["E2E_PASS"])

    def test_value_that_is_only_a_comment_is_declared(self) -> None:
        self.write(".env", "E2E_PASS=#see vault\n")
        self.assertEqual("declared", self.report()["E2E_PASS"])

    def test_inline_comment_after_real_value_keeps_available(self) -> None:
        self.write(".env", "E2E_PASS=s3cret # rotated monthly\n")
        self.assertEqual("available", self.report()["E2E_PASS"])

    def test_hash_inside_unquoted_value_is_not_a_comment(self) -> None:
        """A '#' with no preceding whitespace is part of the value."""
        self.write(".env", "E2E_PASS=p#ss\n")
        self.assertEqual("available", self.report()["E2E_PASS"])

    def test_hash_inside_quoted_value_is_not_a_comment(self) -> None:
        self.write(".env", 'E2E_PASS="p#ss"\n')
        self.assertEqual("available", self.report()["E2E_PASS"])

    def test_quoted_value_with_trailing_comment(self) -> None:
        self.write(".env", "E2E_PASS='s3cret'  # rotated\n")
        self.assertEqual("available", self.report()["E2E_PASS"])

    def test_whitespace_only_value_is_declared(self) -> None:
        self.write(".env", "E2E_PASS=   \n")
        self.assertEqual("declared", self.report()["E2E_PASS"])

    def test_legend_emitted(self) -> None:
        """The three states are meaningless to a reader without the legend."""
        fields = self.report()
        self.assertIn("env_state_legend", fields)
        for state in ["available", "declared", "missing"]:
            self.assertIn(state, fields["env_state_legend"])


class TestEnvStateDrivesVerdict(DiscoverScriptTestCase):
    """`declared` must land between `available` and `missing`, not collapse into
    either. Collapsing toward available produces a false `ready`; collapsing
    toward missing produces a false `blocked`."""

    PKG = '{"devDependencies":{"@playwright/test":"1.55.0"}}'

    def test_declared_only_is_needs_confirmation(self) -> None:
        self.write("package.json", self.PKG)
        self.write(".env.example", "E2E_BASE_URL=\nE2E_USER=\n")
        fields = self.report()
        self.assertEqual("none", fields["blockers"])
        self.assertIn("base_url_declared_but_unset", fields["unknowns"])
        self.assertEqual("needs_confirmation", fields["readiness"])

    def test_no_evidence_at_all_is_blocked(self) -> None:
        self.write("package.json", self.PKG)
        fields = self.report()
        self.assertIn("no_base_url", fields["blockers"])
        self.assertEqual("blocked", fields["readiness"])

    def test_config_base_url_needs_target_verification(self) -> None:
        self.write("package.json", self.PKG)
        self.write(
            "playwright.config.ts",
            'export default { use: { baseURL: "http://localhost:3000" } };\n',
        )
        fields = self.report()
        self.assertEqual("none", fields["blockers"])
        self.assertIn("base_url_resolved_from_config", fields["unknowns"])

    def test_user_without_password_is_flagged(self) -> None:
        """A half-configured account fails at login with a misleading error."""
        self.write("package.json", self.PKG)
        self.write(
            "playwright.config.ts",
            'export default { use: { baseURL: "http://localhost:3000" } };\n',
        )
        self.write(".env", "E2E_USER=u@example.com\nE2E_PASS=\n")
        fields = self.report()
        self.assertIn("test_account_password_not_available", fields["unknowns"])

    def test_fully_available_env_is_ready(self) -> None:
        self.write("package.json", self.PKG)
        self.write(
            "playwright.config.ts",
            'export default { use: { baseURL: "http://localhost:3000" } };\n',
        )
        self.write(".env", "E2E_BASE_URL=http://localhost:3000\nE2E_USER=u\nE2E_PASS=p\n")
        fields = self.report()
        self.assertEqual("ready", fields["readiness"])
        self.assertEqual("none", fields["unknowns"])


class TestExistingTestDiscovery(DiscoverScriptTestCase):
    def test_counts_playwright_specs(self) -> None:
        self.write("package.json", '{"devDependencies":{"@playwright/test":"1.55.0"}}')
        self.write("tests/e2e/login.spec.ts", "// spec\n")
        self.write("tests/e2e/checkout.spec.ts", "// spec\n")
        fields = self.report()
        self.assertEqual("tests/e2e", fields["e2e_directory"])
        self.assertEqual("2", fields["e2e_test_files"])

    def test_counts_go_e2e_tests(self) -> None:
        self.write("go.mod", "module x\ngo 1.22\n")
        self.write("tests/e2e/web_test.go", "package e2e\n")
        fields = self.report()
        self.assertEqual("1", fields["go_e2e_test_files"])

    def test_detects_playwright_visual_regression_usage(self) -> None:
        self.write("package.json", '{"devDependencies":{"@playwright/test":"1.55.0"}}')
        self.write(
            "tests/e2e/visual.spec.ts",
            "await expect(page).toHaveScreenshot('home.png');\n",
        )
        fields = self.report()
        self.assertEqual("playwright-built-in", fields["visual_regression"])

    def test_detects_ci_e2e_lane(self) -> None:
        self.write(".github/workflows/e2e.yml", "jobs:\n  e2e:\n    steps:\n      - run: npx playwright test\n")
        fields = self.report()
        self.assertEqual("github-actions", fields["ci_platform"])
        self.assertEqual("true", fields["ci_has_e2e"])


if __name__ == "__main__":
    unittest.main()
