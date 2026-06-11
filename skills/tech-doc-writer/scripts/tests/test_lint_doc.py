"""Behavioral tests for scripts/lint_doc.py — the mechanical scorecard layer.

Each test feeds a real markdown document through the linter (imported as a
module for finding-level assertions, plus one subprocess test for the CLI
exit-code contract).
"""

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "lint_doc.py"
spec = importlib.util.spec_from_file_location("lint_doc", SCRIPT)
lint_doc = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = lint_doc
spec.loader.exec_module(lint_doc)


GOOD_DOC = """---
title: Deploy Redis Cluster
owner: alice
status: active
last_updated: 2026-06-11
applicable_versions: Redis 7.2+
---

# Deploy Redis Cluster

**Conclusion first**: run `make deploy-redis` and verify with the steps below.

| Field | Type | Required | Default |
|-------|------|----------|---------|
| port | int | yes | 6379 |

```bash
make deploy-redis
```

使用 Redis 集群部署 3 个节点。
"""


def checks(findings):
    return {f.check for f in findings}


class LintDocTests(unittest.TestCase):
    def test_good_doc_has_no_findings(self):
        findings = lint_doc.lint(GOOD_DOC, "task")
        self.assertEqual([], findings, [str(f) for f in findings])

    def test_missing_metadata_is_critical(self):
        doc = "# Title\n\nbody\n"
        findings = lint_doc.lint(doc)
        crit = [f for f in findings if f.severity == lint_doc.CRITICAL]
        self.assertEqual({"metadata"}, {f.check for f in crit})
        self.assertEqual(3, len(crit), "owner, status, last_updated all missing")

    def test_bad_status_and_date_are_critical(self):
        doc = GOOD_DOC.replace("status: active", "status: WIP").replace(
            "last_updated: 2026-06-11", "last_updated: June 2026")
        names = checks(lint_doc.lint(doc))
        self.assertIn("status-value", names)
        self.assertIn("date-format", names)

    def test_tbd_table_cell_critical_for_reference(self):
        doc = GOOD_DOC.replace("| port | int | yes | 6379 |", "| port | int | TBD | 6379 |")
        findings = lint_doc.lint(doc, "reference")
        hits = [f for f in findings if f.check == "table-cells"]
        self.assertEqual(1, len(hits))
        self.assertEqual(lint_doc.CRITICAL, hits[0].severity)

    def test_tbd_table_cell_warning_for_task(self):
        doc = GOOD_DOC.replace("| port | int | yes | 6379 |", "| port | int | TBD | 6379 |")
        findings = lint_doc.lint(doc, "task")
        hits = [f for f in findings if f.check == "table-cells"]
        self.assertEqual(1, len(hits))
        self.assertEqual(lint_doc.WARNING, hits[0].severity)

    def test_empty_table_cell_detected(self):
        doc = GOOD_DOC.replace("| port | int | yes | 6379 |", "| port | int |  | 6379 |")
        self.assertIn("table-cells", checks(lint_doc.lint(doc, "reference")))

    def test_long_title_warned(self):
        doc = GOOD_DOC.replace(
            "# Deploy Redis Cluster",
            "# A Comprehensive Guide To Deploying Redis Clusters In Production")
        hits = [f for f in lint_doc.lint(doc) if f.check == "title-length"]
        self.assertEqual(1, len(hits))
        self.assertEqual(lint_doc.WARNING, hits[0].severity)

    def test_multiple_h1_warned(self):
        doc = GOOD_DOC + "\n# Second Title\n"
        self.assertIn("single-h1", checks(lint_doc.lint(doc)))

    def test_untagged_code_fence_warned(self):
        doc = GOOD_DOC.replace("```bash", "```")
        self.assertIn("code-fence-lang", checks(lint_doc.lint(doc)))

    def test_pangu_violation_detected_with_line(self):
        doc = GOOD_DOC.replace("使用 Redis 集群部署 3 个节点。", "使用Redis集群部署3个节点。")
        hits = [f for f in lint_doc.lint(doc) if f.check == "pangu-spacing"]
        self.assertEqual(1, len(hits), "one line, one finding")
        self.assertIn("用R", hits[0].message)

    def test_pangu_ignores_inline_code_and_fences(self):
        doc = GOOD_DOC + "\n运行 `make部署target` 命令。\n\n```text\n中文mixed内容\n```\n"
        hits = [f for f in lint_doc.lint(doc) if f.check == "pangu-spacing"]
        self.assertEqual([], [str(f) for f in hits])

    def test_h1_inside_code_fence_not_counted(self):
        doc = GOOD_DOC + "\n```markdown\n# Not A Real Title\n```\n"
        self.assertNotIn("single-h1", checks(lint_doc.lint(doc)))

    def test_cli_exit_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            good = Path(tmp) / "good.md"
            good.write_text(GOOD_DOC, encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), str(good), "--type", "task"],
                capture_output=True, text=True)
            self.assertEqual(0, proc.returncode, proc.stdout)

            bad = Path(tmp) / "bad.md"
            bad.write_text("# No Metadata At All\n", encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), str(bad)],
                capture_output=True, text=True)
            self.assertEqual(1, proc.returncode)

            warn_only = Path(tmp) / "warn.md"
            warn_only.write_text(GOOD_DOC.replace("```bash", "```"), encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), str(warn_only), "--strict"],
                capture_output=True, text=True)
            self.assertEqual(1, proc.returncode, "--strict must fail on warnings")

            proc = subprocess.run(
                [sys.executable, str(SCRIPT), str(Path(tmp) / "missing.md")],
                capture_output=True, text=True)
            self.assertEqual(2, proc.returncode)


class ContractGuardTests(unittest.TestCase):
    def test_allowed_tools_include_edit_for_improve_mode(self):
        """Improve mode promises minimal-diff edits; Claude Code's edit tool
        is `Edit` (StrReplace is the Codex name — kept for dual-harness use)."""
        skill = (Path(__file__).resolve().parents[2] / "SKILL.md").read_text(encoding="utf-8")
        frontmatter = skill.split("---")[1]
        self.assertRegex(frontmatter, r"allowed-tools:.*\bEdit\b")
        self.assertIn("lint_doc.py", skill, "Phase 4 must wire in the mechanical linter")


if __name__ == "__main__":
    unittest.main()