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
        # `title` joined the required set: Phase 5 declares it mandatory, but nothing checked it.
        self.assertEqual(4, len(crit), "title, owner, status, last_updated all missing")
        self.assertEqual(
            {"title", "owner", "status", "last_updated"},
            {f.message.split("`")[1] for f in crit},
        )

    def test_all_blank_table_row_is_not_a_separator(self):
        """The separator test was `^\\s*\\|[\\s:|-]+\\|\\s*$`. That class admits spaces and pipes,
        so an entirely blank data row matched it and was SKIPPED — a parameter table with nothing
        filled in produced zero findings and passed the reference-doc Critical gate."""
        body = "| Field | Type |\n|-------|------|\n|       |      |\n"
        findings = lint_doc.check_tables(body, 0, lint_doc.CRITICAL)
        self.assertTrue(findings, "an all-blank data row must be reported, not skipped")
        self.assertTrue(all(f.check == "table-cells" for f in findings))
        self.assertEqual(lint_doc.CRITICAL, findings[0].severity)

    def test_separator_row_recognition(self):
        for line, want in (
            ("|-------|------|", True),
            ("|:------|-----:|", True),
            ("| :---: | ---- |", True),
            ("|       |      |", False),   # blank data row
            ("|   -   |      |", False),   # single dash is not an alignment cell
            ("| a | b |", False),
        ):
            with self.subTest(line=line):
                self.assertEqual(want, lint_doc.is_separator_row(line))

    def test_empty_reference_table_still_fails_for_a_real_doc(self):
        """End-to-end: the bypass mattered because it let an unfilled data dictionary through."""
        doc = GOOD_DOC + (
            "\n## Parameters\n\n| Field | Type | Required |\n|-------|------|----------|\n"
            "|       |      |          |\n")
        names = [f.check for f in lint_doc.lint(doc, "reference")
                 if f.severity == lint_doc.CRITICAL]
        self.assertIn("table-cells", names)

    def test_calendar_invalid_date_is_critical(self):
        """Shape-only validation let `2026-99-99` through, so any staleness audit built on
        last_updated was unsound."""
        doc = GOOD_DOC.replace("last_updated: 2026-06-11", "last_updated: 2026-99-99")
        hits = [f for f in lint_doc.lint(doc) if f.check == "date-format"]
        self.assertEqual(1, len(hits), "an impossible calendar date must be rejected")
        self.assertEqual(lint_doc.CRITICAL, hits[0].severity)
        self.assertIn("real calendar date", hits[0].message)

    def test_valid_leap_day_accepted(self):
        doc = GOOD_DOC.replace("last_updated: 2026-06-11", "last_updated: 2024-02-29")
        self.assertEqual([], [f for f in lint_doc.lint(doc) if f.check == "date-format"])

    def test_unclosed_code_fence_is_critical(self):
        """An unclosed fence makes every fence-skipping check blind to the rest of the file."""
        doc = GOOD_DOC + "\n```go\nfunc main() {}\n"
        hits = [f for f in lint_doc.lint(doc) if f.check == "fence-balance"]
        self.assertEqual(1, len(hits))
        self.assertEqual(lint_doc.CRITICAL, hits[0].severity)

    def test_balanced_fences_accepted(self):
        doc = GOOD_DOC + "\n```go\nfunc main() {}\n```\n"
        self.assertEqual([], [f for f in lint_doc.lint(doc) if f.check == "fence-balance"])

    def test_applicable_versions_warned_when_body_pins_a_version(self):
        # GOOD_DOC already declares the field, so remove it to exercise the check.
        doc = GOOD_DOC.replace("applicable_versions: Redis 7.2+\n", "")
        doc += "\nRequires Redis 7.2.1 or later.\n"
        self.assertIn("applicable-versions", checks(lint_doc.lint(doc)))

    def test_applicable_versions_satisfied_when_declared(self):
        doc = GOOD_DOC + "\nRequires Redis 7.2.1 or later.\n"
        self.assertNotIn("applicable-versions", checks(lint_doc.lint(doc)))

    def test_applicable_versions_not_demanded_without_a_version_mention(self):
        """No false positives on docs that pin nothing."""
        doc = GOOD_DOC.replace("applicable_versions: Redis 7.2+\n", "")
        self.assertNotIn("applicable-versions", checks(lint_doc.lint(doc)))

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

    def test_overweight_title_warned(self):
        doc = GOOD_DOC.replace(
            "# Deploy Redis Cluster",
            "# Deploying And Operating Redis Clusters Across Multiple Production Regions")
        hits = [f for f in lint_doc.lint(doc) if f.check == "title-weight"]
        self.assertTrue(hits, "an over-budget title must warn")
        self.assertEqual(lint_doc.WARNING, hits[0].severity)

    def test_filler_title_warned_at_any_length(self):
        doc = GOOD_DOC.replace("# Deploy Redis Cluster", "# A Guide To Redis")
        hits = [f for f in lint_doc.lint(doc) if f.check == "title-weight"]
        self.assertTrue(any("filler" in f.message for f in hits),
                        "SPA rejects filler regardless of length")

    def test_identifier_prefixed_title_is_not_penalised(self):
        """The skill's own recommended RFC title was 45 chars and tripped its own linter under
        the flat 20-char rule. The ID prefix aids search; it is not padding."""
        doc = GOOD_DOC.replace(
            "# Deploy Redis Cluster",
            "# RFC-042: Migrate to Event-Driven Architecture")
        self.assertEqual([], [f for f in lint_doc.lint(doc) if f.check == "title-weight"],
                         "the skill's own example title must pass its own linter")

    def test_cjk_title_budget_is_not_latin_char_count(self):
        """20 CJK characters carry far more than 20 Latin characters; a single character
        threshold is not comparable across scripts."""
        short_cjk = GOOD_DOC.replace("# Deploy Redis Cluster", "# 部署 Redis 集群")
        self.assertEqual([], [f for f in lint_doc.lint(short_cjk) if f.check == "title-weight"])
        long_cjk = GOOD_DOC.replace(
            "# Deploy Redis Cluster",
            "# 在多个生产区域部署并运维分布式缓存集群的完整操作流程说明")
        self.assertTrue([f for f in lint_doc.lint(long_cjk) if f.check == "title-weight"],
                        "an over-budget CJK title must still warn")

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

    def test_pangu_detected_on_line_with_cjk_slash(self):
        """Regression: URL_RE was \\w-based, and Python \\w matches CJK — prose
        like 读/写 was treated as a path, swallowing surrounding CJK text and
        masking the real violation (使用Redis) on the same line."""
        doc = GOOD_DOC + "\n支持读/写分离且使用Redis部署。\n"
        hits = [f for f in lint_doc.lint(doc) if f.check == "pangu-spacing"]
        self.assertEqual(1, len(hits), [str(f) for f in hits])
        self.assertIn("用R", hits[0].message)

    def test_pangu_still_exempts_real_paths_and_urls(self):
        doc = GOOD_DOC + (
            "\n配置文件位于config/app.yaml中。"
            "\n安装到/usr/local/bin目录,详见 https://example.com/docs 页面。\n"
        )
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