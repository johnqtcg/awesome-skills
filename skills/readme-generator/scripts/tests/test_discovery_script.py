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
