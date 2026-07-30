"""Behavioral tests for scripts/lint_doc.py — the mechanical scorecard layer.

Each test feeds a real markdown document through the linter (imported as a
module for finding-level assertions, plus one subprocess test for the CLI
exit-code contract).
"""

import copy
import datetime
import importlib.util
import json
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


# The staleness check needs a reference date. Pinning it keeps these assertions deterministic:
# with the system date, every "no findings" test would start failing on its own a year after
# GOOD_DOC was written, and the failure would look like a code regression.
TODAY = datetime.date(2026, 6, 15)

GOOD_DOC = """---
title: Deploy Redis Cluster
owner: alice
status: active
last_updated: 2026-06-11
applicable_versions: Redis 7.2+
review_cadence: monthly
---

# Deploy Redis Cluster

**Conclusion first**: run `make deploy-redis` and verify with the steps below.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| port | int | yes | 6379 | listener port |

```bash
make deploy-redis
```

使用 Redis 集群部署 3 个节点。

## Maintenance

Update when the deploy script or the Redis major version changes.
"""


def checks(findings):
    return {f.check for f in findings}


def lint(doc, doc_type=None, config=None, today=TODAY):
    """Every test lints against a pinned date — see TODAY."""
    return lint_doc.lint(doc, doc_type, config, today)


class LintDocTests(unittest.TestCase):
    def test_good_doc_has_no_findings(self):
        findings = lint(GOOD_DOC, "task")
        self.assertEqual([], findings, [str(f) for f in findings])

    def test_missing_metadata_is_critical(self):
        doc = "# Title\n\nbody\n"
        findings = lint(doc)
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
        names = [f.check for f in lint(doc, "reference")
                 if f.severity == lint_doc.CRITICAL]
        self.assertIn("table-cells", names)

    def test_calendar_invalid_date_is_critical(self):
        """Shape-only validation let `2026-99-99` through, so any staleness audit built on
        last_updated was unsound."""
        doc = GOOD_DOC.replace("last_updated: 2026-06-11", "last_updated: 2026-99-99")
        hits = [f for f in lint(doc) if f.check == "date-format"]
        self.assertEqual(1, len(hits), "an impossible calendar date must be rejected")
        self.assertEqual(lint_doc.CRITICAL, hits[0].severity)
        self.assertIn("real calendar date", hits[0].message)

    def test_valid_leap_day_accepted(self):
        doc = GOOD_DOC.replace("last_updated: 2026-06-11", "last_updated: 2024-02-29")
        self.assertEqual([], [f for f in lint(doc) if f.check == "date-format"])

    def test_unclosed_code_fence_is_critical(self):
        """An unclosed fence makes every fence-skipping check blind to the rest of the file."""
        doc = GOOD_DOC + "\n```go\nfunc main() {}\n"
        hits = [f for f in lint(doc) if f.check == "fence-balance"]
        self.assertEqual(1, len(hits))
        self.assertEqual(lint_doc.CRITICAL, hits[0].severity)

    def test_balanced_fences_accepted(self):
        doc = GOOD_DOC + "\n```go\nfunc main() {}\n```\n"
        self.assertEqual([], [f for f in lint(doc) if f.check == "fence-balance"])

    def test_applicable_versions_warned_when_body_pins_a_version(self):
        # GOOD_DOC already declares the field, so remove it to exercise the check.
        doc = GOOD_DOC.replace("applicable_versions: Redis 7.2+\n", "")
        doc += "\nRequires Redis 7.2.1 or later.\n"
        self.assertIn("applicable-versions", checks(lint(doc)))

    def test_applicable_versions_satisfied_when_declared(self):
        doc = GOOD_DOC + "\nRequires Redis 7.2.1 or later.\n"
        self.assertNotIn("applicable-versions", checks(lint(doc)))

    def test_applicable_versions_not_demanded_without_a_version_mention(self):
        """No false positives on docs that pin nothing."""
        doc = GOOD_DOC.replace("applicable_versions: Redis 7.2+\n", "")
        self.assertNotIn("applicable-versions", checks(lint(doc)))

    def test_bad_status_and_date_are_critical(self):
        doc = GOOD_DOC.replace("status: active", "status: WIP").replace(
            "last_updated: 2026-06-11", "last_updated: June 2026")
        names = checks(lint(doc))
        self.assertIn("status-value", names)
        self.assertIn("date-format", names)

    def test_tbd_table_cell_critical_for_reference(self):
        doc = GOOD_DOC.replace("| yes |", "| TBD |")
        findings = lint(doc, "reference")
        hits = [f for f in findings if f.check == "table-cells"]
        self.assertEqual(1, len(hits))
        self.assertEqual(lint_doc.CRITICAL, hits[0].severity)

    def test_tbd_table_cell_warning_for_task(self):
        doc = GOOD_DOC.replace("| yes |", "| TBD |")
        findings = lint(doc, "task")
        hits = [f for f in findings if f.check == "table-cells"]
        self.assertEqual(1, len(hits))
        self.assertEqual(lint_doc.WARNING, hits[0].severity)

    def test_empty_table_cell_detected(self):
        doc = GOOD_DOC.replace("| yes |", "|  |")
        self.assertIn("table-cells", checks(lint(doc, "reference")))

    def test_overweight_title_warned(self):
        doc = GOOD_DOC.replace(
            "# Deploy Redis Cluster",
            "# Deploying And Operating Redis Clusters Across Multiple Production Regions")
        hits = [f for f in lint(doc) if f.check == "title-weight"]
        self.assertTrue(hits, "an over-budget title must warn")
        self.assertEqual(lint_doc.WARNING, hits[0].severity)

    def test_filler_title_warned_at_any_length(self):
        doc = GOOD_DOC.replace("# Deploy Redis Cluster", "# A Guide To Redis")
        hits = [f for f in lint(doc) if f.check == "title-weight"]
        self.assertTrue(any("filler" in f.message for f in hits),
                        "SPA rejects filler regardless of length")

    def test_identifier_prefixed_title_is_not_penalised(self):
        """The skill's own recommended RFC title was 45 chars and tripped its own linter under
        the flat 20-char rule. The ID prefix aids search; it is not padding."""
        doc = GOOD_DOC.replace(
            "# Deploy Redis Cluster",
            "# RFC-042: Migrate to Event-Driven Architecture")
        self.assertEqual([], [f for f in lint(doc) if f.check == "title-weight"],
                         "the skill's own example title must pass its own linter")

    def test_cjk_title_budget_is_not_latin_char_count(self):
        """20 CJK characters carry far more than 20 Latin characters; a single character
        threshold is not comparable across scripts."""
        short_cjk = GOOD_DOC.replace("# Deploy Redis Cluster", "# 部署 Redis 集群")
        self.assertEqual([], [f for f in lint(short_cjk) if f.check == "title-weight"])
        long_cjk = GOOD_DOC.replace(
            "# Deploy Redis Cluster",
            "# 在多个生产区域部署并运维分布式缓存集群的完整操作流程说明")
        self.assertTrue([f for f in lint(long_cjk) if f.check == "title-weight"],
                        "an over-budget CJK title must still warn")

    def test_multiple_h1_warned(self):
        doc = GOOD_DOC + "\n# Second Title\n"
        self.assertIn("single-h1", checks(lint(doc)))

    def test_untagged_code_fence_warned(self):
        doc = GOOD_DOC.replace("```bash", "```")
        self.assertIn("code-fence-lang", checks(lint(doc)))

    def test_pangu_violation_detected_with_line(self):
        doc = GOOD_DOC.replace("使用 Redis 集群部署 3 个节点。", "使用Redis集群部署3个节点。")
        hits = [f for f in lint(doc) if f.check == "pangu-spacing"]
        self.assertEqual(1, len(hits), "one line, one finding")
        self.assertIn("用R", hits[0].message)

    def test_pangu_ignores_inline_code_and_fences(self):
        doc = GOOD_DOC + "\n运行 `make部署target` 命令。\n\n```text\n中文mixed内容\n```\n"
        hits = [f for f in lint(doc) if f.check == "pangu-spacing"]
        self.assertEqual([], [str(f) for f in hits])

    def test_pangu_detected_on_line_with_cjk_slash(self):
        """Regression: URL_RE was \\w-based, and Python \\w matches CJK — prose
        like 读/写 was treated as a path, swallowing surrounding CJK text and
        masking the real violation (使用Redis) on the same line."""
        doc = GOOD_DOC + "\n支持读/写分离且使用Redis部署。\n"
        hits = [f for f in lint(doc) if f.check == "pangu-spacing"]
        self.assertEqual(1, len(hits), [str(f) for f in hits])
        self.assertIn("用R", hits[0].message)

    def test_pangu_still_exempts_real_paths_and_urls(self):
        doc = GOOD_DOC + (
            "\n配置文件位于config/app.yaml中。"
            "\n安装到/usr/local/bin目录,详见 https://example.com/docs 页面。\n"
        )
        hits = [f for f in lint(doc) if f.check == "pangu-spacing"]
        self.assertEqual([], [str(f) for f in hits])

    def test_h1_inside_code_fence_not_counted(self):
        doc = GOOD_DOC + "\n```markdown\n# Not A Real Title\n```\n"
        self.assertNotIn("single-h1", checks(lint(doc)))

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


class StalenessTests(unittest.TestCase):
    """`last_updated` used to be checked for *shape* only.

    `2000-01-01` produced `0 critical, 0 warning` — so the skill's headline anti-staleness
    claim rested on a field nothing ever compared against a clock.
    """

    def test_a_26_year_old_document_is_reported(self):
        doc = GOOD_DOC.replace("last_updated: 2026-06-11", "last_updated: 2000-01-01")
        hits = [f for f in lint(doc, "task") if f.check == "staleness"]
        self.assertEqual(1, len(hits), "an ancient last_updated must be reported")
        self.assertIn("days old", hits[0].message)

    def test_active_status_on_a_stale_doc_names_the_remedy(self):
        """`active` asserts the content is correct, so the fix is the status, not just the date."""
        doc = GOOD_DOC.replace("last_updated: 2026-06-11", "last_updated: 2000-01-01")
        hits = [f for f in lint(doc, "task") if f.check == "staleness"]
        self.assertIn("needs-update", hits[0].message)

    def test_fresh_document_is_silent(self):
        self.assertEqual([], [f for f in lint(GOOD_DOC, "task") if f.check == "staleness"])

    def test_future_date_is_reported(self):
        """A post-dated document cannot be audited; it also defeats every age comparison."""
        doc = GOOD_DOC.replace("last_updated: 2026-06-11", "last_updated: 2030-01-01")
        hits = [f for f in lint(doc, "task") if f.check == "staleness"]
        self.assertEqual(1, len(hits))
        self.assertIn("future", hits[0].message)

    def test_declared_cadence_tightens_the_window(self):
        """A monthly-cadence runbook is stale long before the 365-day default fires."""
        doc = GOOD_DOC.replace("last_updated: 2026-06-11", "last_updated: 2026-01-05")
        monthly = [f for f in lint(doc, "task") if f.check == "staleness"]
        self.assertEqual(1, len(monthly), "161 days > monthly(30) + grace(30)")
        self.assertIn("review_cadence=monthly", monthly[0].message)

        annual = doc.replace("review_cadence: monthly\n", "")
        self.assertEqual(
            [], [f for f in lint(annual, "task") if f.check == "staleness"],
            "without a cadence the same document is inside the 365-day default")

    def test_cadence_window_is_configurable(self):
        cfg = copy.deepcopy(lint_doc.DEFAULT_CONFIG)
        cfg["staleness"]["max_age_days"] = 1
        doc = GOOD_DOC.replace("review_cadence: monthly\n", "")
        self.assertTrue([f for f in lint(doc, "task", cfg) if f.check == "staleness"])

    def test_staleness_can_be_switched_off(self):
        cfg = copy.deepcopy(lint_doc.DEFAULT_CONFIG)
        cfg["staleness"]["enabled"] = False
        doc = GOOD_DOC.replace("last_updated: 2026-06-11", "last_updated: 2000-01-01")
        self.assertEqual([], [f for f in lint(doc, "task", cfg) if f.check == "staleness"])

    def test_unparseable_date_is_left_to_the_date_format_check(self):
        """Two findings for one defect is noise; date-format already owns this case."""
        doc = GOOD_DOC.replace("last_updated: 2026-06-11", "last_updated: 2026-99-99")
        self.assertEqual([], [f for f in lint(doc, "task") if f.check == "staleness"])


class MaintenanceTriggerTests(unittest.TestCase):
    def test_task_doc_without_a_trigger_is_reported(self):
        doc = (GOOD_DOC.replace("review_cadence: monthly\n", "")
                       .split("## Maintenance")[0])
        hits = [f for f in lint(doc, "task") if f.check == "maintenance"]
        self.assertEqual(1, len(hits))

    def test_a_maintenance_heading_satisfies_it(self):
        doc = GOOD_DOC.replace("review_cadence: monthly\n", "")
        self.assertEqual([], [f for f in lint(doc, "task") if f.check == "maintenance"])

    def test_a_declared_cadence_satisfies_it(self):
        doc = GOOD_DOC.split("## Maintenance")[0]
        self.assertEqual([], [f for f in lint(doc, "task") if f.check == "maintenance"])

    def test_chinese_heading_satisfies_it(self):
        doc = (GOOD_DOC.replace("review_cadence: monthly\n", "")
                       .replace("## Maintenance", "## 维护与更新触发条件"))
        self.assertEqual([], [f for f in lint(doc, "task") if f.check == "maintenance"])

    def test_concept_docs_are_not_asked_for_one(self):
        doc = (GOOD_DOC.replace("review_cadence: monthly\n", "")
                       .split("## Maintenance")[0])
        self.assertEqual([], [f for f in lint(doc, "concept") if f.check == "maintenance"])

    def test_a_maintenance_word_in_prose_does_not_count(self):
        """Only a heading counts — otherwise the word `maintenance` anywhere disables the check."""
        doc = ((GOOD_DOC.replace("review_cadence: monthly\n", "").split("## Maintenance")[0])
               + "\nThis runbook needs maintenance eventually.\n")
        self.assertTrue([f for f in lint(doc, "task") if f.check == "maintenance"])


class ReferenceTableColumnTests(unittest.TestCase):
    """A table reduced to `Field | Description` used to score a perfect pass: every cell
    non-empty, three quarters of the parameter contract absent."""

    HEADER = "\n## Request Parameters\n\n"

    def table(self, header_row, sep, *rows):
        return GOOD_DOC + self.HEADER + "\n".join([header_row, sep, *rows]) + "\n"

    def test_field_and_description_only_is_critical(self):
        doc = self.table("| Field | Description |", "|---|---|", "| user_id | the user |")
        hits = [f for f in lint(doc, "reference") if f.check == "table-columns"]
        self.assertEqual(1, len(hits))
        self.assertEqual(lint_doc.CRITICAL, hits[0].severity)
        for want in ("type", "required", "default"):
            self.assertIn(want, hits[0].message)

    def test_complete_table_passes(self):
        doc = self.table(
            "| Field | Type | Required | Default | Description |", "|---|---|---|---|---|",
            "| user_id | string | yes | none | the user |")
        self.assertEqual([], [f for f in lint(doc, "reference") if f.check == "table-columns"])

    def test_chinese_columns_are_accepted(self):
        doc = self.table(
            "| 字段 | 类型 | 是否必填 | 默认值 | 说明 |", "|---|---|---|---|---|",
            "| user_id | string | 是 | 无 | 用户标识 |")
        self.assertEqual([], [f for f in lint(doc, "reference") if f.check == "table-columns"])

    def test_error_code_table_is_not_a_parameter_table(self):
        """Error-code, changelog and compatibility tables share a reference doc legitimately."""
        doc = GOOD_DOC + (
            "\n## Error Codes\n\n| Code | HTTP Status | Trigger | Action |\n"
            "|---|---|---|---|\n| E1 | 404 | missing | retry |\n")
        self.assertEqual([], [f for f in lint(doc, "reference") if f.check == "table-columns"])

    def test_non_reference_types_are_untouched(self):
        """The scorecard tags this Critical item `[reference]` only."""
        doc = self.table("| Field | Description |", "|---|---|", "| user_id | the user |")
        for doc_type in ("task", "concept", "troubleshooting", "design", None):
            with self.subTest(doc_type=doc_type):
                self.assertEqual(
                    [], [f for f in lint(doc, doc_type) if f.check == "table-columns"])

    def test_an_unrelated_section_needs_two_columns_before_it_fires(self):
        """Corroboration rule. `Field | Value` under a neutral heading is an explanatory table,
        not an API dictionary — forcing this repository's 987 markdown files through
        `--type reference` produced 39 findings on exactly that shape, and a CRITICAL false
        positive blocks delivery of a correct document."""
        neutral = GOOD_DOC + (
            "\n## How It Works\n\n| Field | Value |\n|---|---|\n| port | 6379 |\n")
        self.assertEqual([], [f for f in lint(neutral, "reference")
                              if f.check == "table-columns"])

        # Two of the four present is itself evidence the author intended a parameter table.
        partial = GOOD_DOC + (
            "\n## How It Works\n\n| Field | Type | Required |\n|---|---|---|\n"
            "| port | int | yes |\n")
        self.assertTrue([f for f in lint(partial, "reference") if f.check == "table-columns"])

    def test_required_column_set_is_configurable(self):
        cfg = copy.deepcopy(lint_doc.DEFAULT_CONFIG)
        cfg["tables"]["reference_required_columns"] = ["type"]
        doc = self.table("| Field | Type |", "|---|---|", "| port | int |")
        self.assertEqual([], [f for f in lint(doc, "reference", cfg)
                              if f.check == "table-columns"])


class CommonMarkFenceTests(unittest.TestCase):
    """Five checks each re-derived fence state from `line.startswith("```")`.

    That missed `~~~` entirely, so a `~~~yaml` block was linted as prose — the CJK inside it
    was reported as a pangu violation. It also mis-tracked four-backtick wrappers, so H1s and
    untagged fences *inside* a fenced example counted as real ones.
    """

    def test_pangu_inside_a_tilde_fence_is_not_reported(self):
        doc = GOOD_DOC + "\n~~~yaml\ncache:\n  addr: 使用Redis集群\n~~~\n"
        self.assertEqual([], [f for f in lint(doc) if f.check == "pangu-spacing"])

    def test_untagged_tilde_fence_is_reported(self):
        doc = GOOD_DOC + "\n~~~\nplain text\n~~~\n"
        self.assertIn("code-fence-lang", checks(lint(doc)))

    def test_unclosed_tilde_fence_is_critical(self):
        doc = GOOD_DOC + "\n~~~yaml\nkey: value\n"
        hits = [f for f in lint(doc) if f.check == "fence-balance"]
        self.assertEqual(1, len(hits))
        self.assertEqual(lint_doc.CRITICAL, hits[0].severity)

    def test_a_backtick_fence_is_not_closed_by_a_tilde_fence(self):
        doc = GOOD_DOC + "\n```yaml\nkey: value\n~~~\n"
        self.assertTrue([f for f in lint(doc) if f.check == "fence-balance"])

    def test_inner_triple_backticks_nest_inside_a_four_backtick_fence(self):
        """CommonMark: a closer needs at least as many backticks as the opener."""
        doc = GOOD_DOC + "\n````markdown\n# Inner H1\n\n```\nuntagged\n```\n````\n"
        names = checks(lint(doc))
        self.assertNotIn("single-h1", names, "an H1 inside a fenced example is not a real H1")
        self.assertNotIn("code-fence-lang", names, "nor is the inner fence a real fence")
        self.assertNotIn("fence-balance", names)

    def test_an_info_string_never_closes_a_fence(self):
        """```go cannot close ``` — so this document has one block, not two."""
        doc = GOOD_DOC + "\n```\nouter\n```go\nstill inside\n```\n"
        self.assertEqual([], [f for f in lint(doc) if f.check == "fence-balance"])

    def test_scan_reports_fence_state_for_delimiters_and_contents(self):
        rows = list(lint_doc.scan("a\n~~~py\nb\n~~~\nc\n"))
        self.assertEqual([False, True, True, True, False], [r[2] for r in rows])


class TitleH1MatchTests(unittest.TestCase):
    def test_divergent_title_and_h1_are_reported(self):
        doc = GOOD_DOC.replace("# Deploy Redis Cluster", "# Configure Kafka Consumer Groups")
        hits = [f for f in lint(doc, "task") if f.check == "title-h1-match"]
        self.assertEqual(1, len(hits))
        self.assertEqual(lint_doc.WARNING, hits[0].severity)

    def test_matching_title_and_h1_are_silent(self):
        self.assertEqual([], [f for f in lint(GOOD_DOC, "task") if f.check == "title-h1-match"])

    def test_identifier_prefix_difference_is_tolerated(self):
        """`RFC-042: Migrate to X` and `Migrate to X` are the same document."""
        doc = GOOD_DOC.replace(
            "title: Deploy Redis Cluster", "title: 'RFC-042: Deploy Redis Cluster'")
        self.assertEqual([], [f for f in lint(doc, "design") if f.check == "title-h1-match"])

    def test_case_and_trailing_punctuation_are_ignored(self):
        doc = GOOD_DOC.replace("# Deploy Redis Cluster", "# deploy redis cluster.")
        self.assertEqual([], [f for f in lint(doc, "task") if f.check == "title-h1-match"])

    def test_check_is_configurable_for_repos_with_a_long_nav_title(self):
        """A deliberate long-sidebar-title convention turns this off rather than losing."""
        cfg = copy.deepcopy(lint_doc.DEFAULT_CONFIG)
        cfg["title"]["require_h1_match"] = False
        doc = GOOD_DOC.replace("# Deploy Redis Cluster", "# Something Else Entirely")
        self.assertEqual([], [f for f in lint(doc, "task", cfg)
                              if f.check == "title-h1-match"])


class PanguSpacingTests(unittest.TestCase):
    """The rule is "exactly one space", but only the zero-space case was detected."""

    def wrap(self, line):
        return GOOD_DOC + "\n" + line + "\n"

    def test_two_spaces_are_reported(self):
        hits = [f for f in lint(self.wrap("官方建议 SKILL 控制在  500 行以内。"))
                if f.check == "pangu-spacing"]
        self.assertEqual(1, len(hits))
        self.assertIn("exactly one", hits[0].message)

    def test_inline_code_does_not_fabricate_a_double_space(self):
        """The regression that mattered: exempt spans were deleted rather than replaced, which
        merged the spaces around them. `中 `git-commit` skill` became `中  skill`, and the rule
        reported a double space the author never wrote — 78 findings across this repository,
        every one of them false."""
        for line in (
            "这次 CI 正是由 §8.1 中 `git-commit` skill 的提交触发的。",
            "以下代码交给 `go-code-reviewer` Skill 处理：",
            "### 4.2 `铁律` 要写得这么绝对",
            "见 docs/api/reference.md 的说明。",
        ):
            with self.subTest(line=line):
                self.assertEqual(
                    [], [f for f in lint(self.wrap(line)) if f.check == "pangu-spacing"],
                    "an exempt span must not manufacture a spacing violation")

    def test_four_or_more_spaces_are_left_alone(self):
        """In Markdown that is indentation or column alignment, not prose spacing."""
        self.assertEqual([], [f for f in lint(self.wrap("字段    Redis    值"))
                              if f.check == "pangu-spacing"])

    def test_table_padding_is_not_prose_spacing(self):
        doc = GOOD_DOC + "\n| 名称   | Type |\n|---|---|\n| 端口   | int |\n"
        self.assertEqual([], [f for f in lint(doc) if f.check == "pangu-spacing"])

    def test_multi_space_rule_is_configurable(self):
        cfg = copy.deepcopy(lint_doc.DEFAULT_CONFIG)
        cfg["pangu"]["flag_multiple_spaces"] = False
        self.assertEqual([], [f for f in lint(self.wrap("控制在  500 行"), None, cfg)
                              if f.check == "pangu-spacing"])

    def test_pangu_can_be_switched_off_entirely(self):
        cfg = copy.deepcopy(lint_doc.DEFAULT_CONFIG)
        cfg["pangu"]["enabled"] = False
        self.assertEqual([], [f for f in lint(self.wrap("使用Redis集群"), None, cfg)
                              if f.check == "pangu-spacing"])


class ConfigTests(unittest.TestCase):
    """Gate 1 says the repository's convention outranks this skill's defaults. Before
    `.techdocrc.json` the linter could not honour that: frontmatter location, the four field
    names and the status vocabulary were all hard-coded, so a repo using footer metadata or a
    `maintainer:` field was told its own standard was a Critical lint failure."""

    def test_defaults_are_unchanged_without_a_config(self):
        cfg, path = lint_doc.load_config(None, Path(tempfile.gettempdir()) / "nowhere.md")
        self.assertIsNone(path)
        self.assertEqual(lint_doc.DEFAULT_CONFIG, cfg)

    def test_alias_lets_a_repo_keep_its_own_field_name(self):
        doc = GOOD_DOC.replace("owner: alice", "maintainer: alice")
        self.assertIn("metadata", checks(lint(doc, "task")))

        cfg = copy.deepcopy(lint_doc.DEFAULT_CONFIG)
        cfg["metadata"]["aliases"] = {"owner": ["maintainer"]}
        self.assertEqual([], [f for f in lint(doc, "task", cfg) if f.check == "metadata"])

    def test_status_vocabulary_is_configurable(self):
        doc = GOOD_DOC.replace("status: active", "status: published")
        self.assertIn("status-value", checks(lint(doc, "task")))

        cfg = copy.deepcopy(lint_doc.DEFAULT_CONFIG)
        cfg["metadata"]["status_values"] = ["published", "wip"]
        self.assertEqual([], [f for f in lint(doc, "task", cfg) if f.check == "status-value"])

    def test_required_field_set_is_configurable(self):
        doc = GOOD_DOC.replace("owner: alice\n", "")
        cfg = copy.deepcopy(lint_doc.DEFAULT_CONFIG)
        cfg["metadata"]["required"] = ["title", "status", "last_updated"]
        self.assertEqual([], [f for f in lint(doc, "task", cfg) if f.check == "metadata"])

    def test_footer_metadata_location(self):
        body = ("# Deploy Redis Cluster\n\nBody paragraph.\n\n## Maintenance\n\nOn change.\n"
                "\n---\ntitle: Deploy Redis Cluster\nowner: alice\nstatus: active\n"
                "last_updated: 2026-06-11\n---\n")
        self.assertTrue([f for f in lint(body, "task") if f.check == "metadata"],
                        "with the default frontmatter setting the block is invisible")

        cfg = copy.deepcopy(lint_doc.DEFAULT_CONFIG)
        cfg["metadata"]["location"] = "footer"
        self.assertEqual([], [f for f in lint(body, "task", cfg) if f.check == "metadata"])

    def test_location_none_skips_metadata_and_staleness(self):
        cfg = copy.deepcopy(lint_doc.DEFAULT_CONFIG)
        cfg["metadata"]["location"] = "none"
        doc = "# Deploy Redis Cluster\n\nBody.\n\n## Maintenance\n\nOn change.\n"
        names = checks(lint(doc, "task", cfg))
        self.assertNotIn("metadata", names)
        self.assertNotIn("staleness", names)

    def test_title_budget_is_configurable(self):
        doc = GOOD_DOC.replace("# Deploy Redis Cluster", "# Deploy Redis Cluster Everywhere Now")
        cfg = copy.deepcopy(lint_doc.DEFAULT_CONFIG)
        cfg["title"]["budget"] = 4.0
        hits = [f for f in lint(doc, "task", cfg) if f.check == "title-weight"]
        self.assertTrue(hits)
        self.assertIn("> 4", hits[0].message)

    def test_deep_merge_keeps_unmentioned_defaults(self):
        merged = lint_doc.deep_merge(
            lint_doc.DEFAULT_CONFIG, {"metadata": {"required": ["title"]}})
        self.assertEqual(["title"], merged["metadata"]["required"])
        self.assertEqual("status", merged["metadata"]["status_field"],
                         "a partial override must not wipe its siblings")
        self.assertEqual(365, merged["staleness"]["max_age_days"])

    def test_config_is_discovered_by_walking_up(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".techdocrc.json").write_text(
                json.dumps({"metadata": {"status_values": ["published"]}}), encoding="utf-8")
            nested = root / "docs" / "guides"
            nested.mkdir(parents=True)
            doc = nested / "page.md"
            doc.write_text(GOOD_DOC.replace("status: active", "status: published"),
                           encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), str(doc), "--type", "task",
                 "--today", "2026-06-15"],
                capture_output=True, text=True)
            self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
            self.assertIn(".techdocrc.json", proc.stdout, "the config in use must be named")

    def test_nearest_config_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".techdocrc.json").write_text(
                json.dumps({"metadata": {"status_values": ["root-only"]}}), encoding="utf-8")
            nested = root / "docs"
            nested.mkdir()
            (nested / ".techdocrc.json").write_text(
                json.dumps({"metadata": {"status_values": ["published"]}}), encoding="utf-8")
            doc = nested / "page.md"
            doc.write_text(GOOD_DOC.replace("status: active", "status: published"),
                           encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), str(doc), "--type", "task",
                 "--today", "2026-06-15"],
                capture_output=True, text=True)
            self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)

    def test_unknown_top_level_key_is_rejected(self):
        """A typo'd section would otherwise be silently ignored, and the author would believe
        the repository's convention had been applied."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "rc.json"
            cfg.write_text(json.dumps({"metadta": {}}), encoding="utf-8")
            doc = Path(tmp) / "d.md"
            doc.write_text(GOOD_DOC, encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), str(doc), "--config", str(cfg)],
                capture_output=True, text=True)
            self.assertEqual(3, proc.returncode)
            self.assertIn("unknown top-level key", proc.stderr)

    def test_malformed_config_exits_three(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "rc.json"
            cfg.write_text("{not json", encoding="utf-8")
            doc = Path(tmp) / "d.md"
            doc.write_text(GOOD_DOC, encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), str(doc), "--config", str(cfg)],
                capture_output=True, text=True)
            self.assertEqual(3, proc.returncode)

    def test_bad_today_exits_three(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc = Path(tmp) / "d.md"
            doc.write_text(GOOD_DOC, encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), str(doc), "--today", "yesterday"],
                capture_output=True, text=True)
            self.assertEqual(3, proc.returncode)

    def test_default_config_passes_its_own_validation(self):
        """A shipped default that its own validator rejects would fail every run."""
        lint_doc.validate_config(copy.deepcopy(lint_doc.DEFAULT_CONFIG), "DEFAULT_CONFIG")

    def test_misshapen_config_fails_loudly(self):
        """Rejecting an unknown *section* is not enough; a wrong *shape* inside a known section
        used to misbehave silently. `{"aliases": {"owner": "maintainer"}}` — a string where a
        list belongs — made resolve_field unpack the string one character at a time, look up
        `m`, `a`, `i`, … and report `metadata missing owner`: a complaint about the very field
        the author had just aliased, with nothing pointing at the config."""
        cases = {
            "aliases as a bare string": {"metadata": {"aliases": {"owner": "maintainer"}}},
            "unknown location": {"metadata": {"location": "sidebar"}},
            "required as a string": {"metadata": {"required": "title"}},
            "numeric field as a string": {"staleness": {"max_age_days": "365"}},
            "cadence_days not an object": {"staleness": {"cadence_days": []}},
            "budget as a string": {"title": {"budget": "20"}},
            "unknown required column": {"tables": {"reference_required_columns": ["colour"]}},
        }
        with tempfile.TemporaryDirectory() as tmp:
            doc = Path(tmp) / "d.md"
            doc.write_text(GOOD_DOC, encoding="utf-8")
            for label, payload in cases.items():
                with self.subTest(case=label):
                    cfg = Path(tmp) / "rc.json"
                    cfg.write_text(json.dumps(payload), encoding="utf-8")
                    proc = subprocess.run(
                        [sys.executable, str(SCRIPT), str(doc), "--config", str(cfg)],
                        capture_output=True, text=True)
                    self.assertEqual(3, proc.returncode,
                                     f"{label} must be rejected, not silently tolerated")
                    self.assertIn("config error", proc.stderr)

    def test_print_config_documents_the_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc = Path(tmp) / "d.md"
            doc.write_text(GOOD_DOC, encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), str(doc), "--print-config"],
                capture_output=True, text=True)
            self.assertEqual(0, proc.returncode)
            for key in ("metadata", "staleness", "location", "aliases",
                        "reference_required_columns"):
                self.assertIn(key, proc.stdout)


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