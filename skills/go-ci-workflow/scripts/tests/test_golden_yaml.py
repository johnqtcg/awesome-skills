"""Validate the workflow YAML embedded in the golden example references.

The golden examples are this skill's most-copied artifacts; a typo in them
propagates into real repositories. Every fenced ``yaml`` block must parse,
and every complete workflow (a block with a ``jobs`` key) must comply with
the rules SKILL.md itself mandates: timeout on every job, no ``@latest``
tool installs, no hardcoded Go versions, explicit permissions.

If ``actionlint`` is on PATH the workflows are additionally linted with it;
otherwise that layer is skipped (PyYAML structural checks still run).
"""

import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

# Optional dependency: a hard module-level import crashes pytest COLLECTION
# in environments without PyYAML, killing the entire repo suite instead of
# skipping these tests (this happened in CI). Declared in requirements.txt;
# degrade gracefully anyway.
try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

SKILL_DIR = Path(__file__).resolve().parents[2]
REF_DIR = SKILL_DIR / "references"

GOLDEN_FILES = [
    REF_DIR / "golden-examples.md",
    REF_DIR / "golden-example-monorepo.md",
    REF_DIR / "golden-example-service-containers.md",
]

YAML_BLOCK_RE = re.compile(r"```yaml\n(.*?)```", re.DOTALL)

# PyYAML (YAML 1.1) parses the bare key `on` as boolean True.
TRIGGER_KEYS = ("on", True)

HARDCODED_GO_VERSION_RE = re.compile(r"go-version:\s*['\"]?1\.\d")


def yaml_blocks() -> list[tuple[str, str]]:
    blocks: list[tuple[str, str]] = []
    for path in GOLDEN_FILES:
        for i, match in enumerate(YAML_BLOCK_RE.finditer(path.read_text()), 1):
            blocks.append((f"{path.name}#block{i}", match.group(1)))
    return blocks


def complete_workflows() -> list[tuple[str, dict]]:
    flows = []
    for name, text in yaml_blocks():
        doc = yaml.safe_load(text)
        if isinstance(doc, dict) and "jobs" in doc:
            flows.append((name, doc))
    return flows


@unittest.skipUnless(yaml is not None, "PyYAML not installed (pip install -r requirements.txt)")
class GoldenYamlTests(unittest.TestCase):
    def test_golden_files_exist_and_contain_yaml(self) -> None:
        for path in GOLDEN_FILES:
            self.assertTrue(path.exists(), f"missing golden file: {path}")
        self.assertGreaterEqual(len(yaml_blocks()), 3, "expected at least 3 yaml blocks")

    def test_every_yaml_block_parses(self) -> None:
        for name, text in yaml_blocks():
            try:
                yaml.safe_load(text)
            except yaml.YAMLError as exc:
                self.fail(f"{name}: yaml does not parse: {exc}")

    def test_complete_workflows_found(self) -> None:
        self.assertGreaterEqual(len(complete_workflows()), 3,
                                "expected at least 3 complete workflows in golden examples")

    def test_workflow_top_level_shape(self) -> None:
        for name, doc in complete_workflows():
            self.assertIn("name", doc, f"{name}: workflow missing name")
            self.assertTrue(any(k in doc for k in TRIGGER_KEYS), f"{name}: workflow missing trigger")
            self.assertTrue(doc["jobs"], f"{name}: workflow has no jobs")

    def test_every_job_has_timeout_and_runner(self) -> None:
        """SKILL.md: 'Set timeout-minutes on every job.'"""
        for name, doc in complete_workflows():
            for job_id, job in doc["jobs"].items():
                if "uses" in job:  # reusable-workflow caller jobs cannot set these
                    continue
                self.assertIn("runs-on", job, f"{name}:{job_id} missing runs-on")
                self.assertIn("timeout-minutes", job, f"{name}:{job_id} missing timeout-minutes")

    def test_permissions_declared(self) -> None:
        """Minimal-permissions rule: workflow-level or every-job permissions."""
        for name, doc in complete_workflows():
            if "permissions" in doc:
                continue
            for job_id, job in doc["jobs"].items():
                self.assertIn("permissions", job,
                              f"{name}: no workflow-level permissions and job {job_id} has none")

    def test_no_latest_tool_installs(self) -> None:
        """SKILL.md: pin go install tool versions exactly, never @latest."""
        for name, text in yaml_blocks():
            self.assertNotIn("@latest", text, f"{name}: tool installed @latest")

    def test_no_hardcoded_go_version(self) -> None:
        """SKILL.md: use go-version-file: go.mod — never hardcode Go version."""
        for name, text in yaml_blocks():
            match = HARDCODED_GO_VERSION_RE.search(text)
            self.assertIsNone(match, f"{name}: hardcoded Go version: {match.group(0) if match else ''}")
            if "actions/setup-go" in text:
                self.assertIn("go-version-file", text,
                              f"{name}: setup-go without go-version-file")

    def test_actionlint_when_available(self) -> None:
        if not shutil.which("actionlint"):
            self.skipTest("actionlint not installed")
        for name, doc_text in yaml_blocks():
            doc = yaml.safe_load(doc_text)
            if not (isinstance(doc, dict) and "jobs" in doc):
                continue
            with tempfile.TemporaryDirectory() as tmp:
                wf_dir = Path(tmp) / ".github" / "workflows"
                wf_dir.mkdir(parents=True)
                (wf_dir / "golden.yml").write_text(doc_text)
                proc = subprocess.run(
                    ["actionlint", "-no-color"],
                    cwd=tmp,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(0, proc.returncode, f"{name}: actionlint:\n{proc.stdout}")


if __name__ == "__main__":
    unittest.main()