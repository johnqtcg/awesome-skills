"""Behavioral tests for scripts/lint_postmortem.py — the mechanical scorecard layer."""

import importlib.util
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "lint_postmortem.py"
spec = importlib.util.spec_from_file_location("lint_postmortem", SCRIPT)
lint_postmortem = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = lint_postmortem
spec.loader.exec_module(lint_postmortem)


GOOD_DOC = """# INC-2024-0142 — Payment API Outage

## Timeline (UTC)
- 14:23 payment-api error rate spiked to 15% (Grafana: payment-slo)
- 14:26 PagerDuty alert fired: p99 > 500ms (PD incident #4821)
- 14:35 Scaled to 10 replicas, no improvement (Slack #incident-0142)
- 15:10 Service restored after config rollback (deploy log)

## Root Cause Analysis
Why did payment fail? Connection string was empty in config.
Why was it accepted? No schema validation in the deploy pipeline.

## What Went Well
- Alert fired within 3 minutes of first error

## Action Items
- [Prevent] Add config schema validation to CI (owner: @platform, deadline: 2024-04-01)
- [Detect] Add p99 latency alert at 500ms (owner: @sre, deadline: Mar 22)
- [Mitigate] Add circuit breaker order-svc -> payment-api (owner: @backend, deadline: Apr 15)

## Uncovered Risks
- Downstream cascade effects not traced
"""


def checks(findings):
    return {f.check for f in findings}


class LintPostmortemTests(unittest.TestCase):
    def test_good_doc_is_clean(self):
        findings = lint_postmortem.lint(GOOD_DOC)
        self.assertEqual([], [str(f) for f in findings])

    def test_unsourced_timeline_entry_is_critical(self):
        doc = GOOD_DOC.replace(
            "- 14:26 PagerDuty alert fired: p99 > 500ms (PD incident #4821)",
            "- 14:26 someone noticed something was wrong")
        hits = [f for f in lint_postmortem.lint(doc) if f.check == "timeline-source"]
        self.assertEqual(1, len(hits))
        self.assertEqual(lint_postmortem.CRITICAL, hits[0].severity)

    def test_missing_timeline_section_is_critical(self):
        doc = GOOD_DOC.replace("## Timeline", "## Sequence of Stuff")
        self.assertIn("timeline-utc", checks(lint_postmortem.lint(doc)))

    def test_action_without_owner_is_critical(self):
        doc = GOOD_DOC.replace(
            "- [Detect] Add p99 latency alert at 500ms (owner: @sre, deadline: Mar 22)",
            "- [Detect] Improve monitoring")
        names = checks(lint_postmortem.lint(doc))
        self.assertIn("action-owner", names)
        self.assertIn("action-deadline", names)

    def test_missing_category_warned(self):
        doc = GOOD_DOC.replace(
            "- [Mitigate] Add circuit breaker order-svc -> payment-api (owner: @backend, deadline: Apr 15)\n", "")
        hits = [f for f in lint_postmortem.lint(doc) if f.check == "action-categories"]
        self.assertEqual(1, len(hits))
        self.assertIn("mitigate", hits[0].message)

    def test_missing_went_well_and_risks_warned(self):
        doc = GOOD_DOC.replace("## What Went Well", "## Other").replace(
            "## Uncovered Risks", "## Misc")
        names = checks(lint_postmortem.lint(doc))
        self.assertIn("went-well", names)
        self.assertIn("uncovered-risks", names)

    def test_blame_phrase_detected_with_line(self):
        doc = GOOD_DOC + "\nRoot cause was operator error during deploy.\n"
        hits = [f for f in lint_postmortem.lint(doc) if f.check == "blame-language"]
        self.assertEqual(1, len(hits))
        self.assertIn("operator error", hits[0].message)

    def test_cli_exit_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            good = Path(tmp) / "good.md"
            good.write_text(GOOD_DOC, encoding="utf-8")
            self.assertEqual(0, subprocess.run(
                [sys.executable, str(SCRIPT), str(good)],
                capture_output=True).returncode)

            bad = Path(tmp) / "bad.md"
            bad.write_text("# Incident\n\nIt broke. We fixed it.\n", encoding="utf-8")
            self.assertEqual(1, subprocess.run(
                [sys.executable, str(SCRIPT), str(bad)],
                capture_output=True).returncode)

            warn_only = Path(tmp) / "warn.md"
            warn_only.write_text(
                GOOD_DOC.replace("## What Went Well", "## Other"), encoding="utf-8")
            self.assertEqual(1, subprocess.run(
                [sys.executable, str(SCRIPT), str(warn_only), "--strict"],
                capture_output=True).returncode, "--strict must fail on warnings")

            self.assertEqual(2, subprocess.run(
                [sys.executable, str(SCRIPT), str(Path(tmp) / "missing.md")],
                capture_output=True).returncode)


class SkillWiringGuards(unittest.TestCase):
    def test_lint_wired_into_skill(self):
        skill = (Path(__file__).resolve().parents[2] / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("lint_postmortem.py", skill, "§8 must wire in the mechanical linter")
        frontmatter = skill.split("---")[2 - 1]
        self.assertIn("Bash(*lint_postmortem.py*)", frontmatter)



# The document below is written in the *official template's* formats: bare
# `HH:MM [PHASE] ... (source)` timeline entries and a Markdown action-items
# table. The previous linter reported `[critical] timeline has no HH:MM-stamped
# entries` on exactly this shape, i.e. it rejected its own template, and it read
# no table cells at all — so an action-items table with empty Owner and Deadline
# cells passed with exit 0.
TEMPLATE_FORMAT_DOC = """# Post-mortem: Payment API Outage

## Timeline (UTC)
14:18 [TRIGGER]    Config deploy merged via CI (GitHub PR #4521)
14:23 [DETECTION]  Error rate spike to 15% (Grafana: payment-slo)
14:45 [MITIGATION] Rolled back config (ArgoCD audit log)
14:48 [RECOVERY]   Error rate at baseline (Grafana: payment-slo)

## What Went Well
- Alert fired within 3 minutes.

## Action Items
| ID | Category | Description | Owner | Deadline | Ticket | Status |
|----|----------|-------------|-------|----------|--------|--------|
| AI-1 | Prevent | Add config schema validation | @platform | 2024-04-01 | JIRA-4521 | Open |
| AI-2 | Detect | Add Redis health check | @sre | Mar 22 | JIRA-4522 | Open |
| AI-3 | Mitigate | Add auto-rollback | @platform | Apr 15 | JIRA-4523 | Open |

## Uncovered Risks
- Downstream cascade not traced.
"""


def severities(findings, check):
    return [f.severity for f in findings if f.check == check]


class TemplateFormatTests(unittest.TestCase):
    """The linter must accept every format the skill's own template emits."""

    def test_template_format_doc_is_clean(self):
        findings = lint_postmortem.lint(TEMPLATE_FORMAT_DOC)
        self.assertEqual([], [str(f) for f in findings])

    def test_bare_timeline_entries_are_recognised(self):
        findings = lint_postmortem.lint(TEMPLATE_FORMAT_DOC)
        self.assertEqual([], [f for f in findings if f.check == "timeline-utc"])

    def test_table_row_timeline_is_recognised(self):
        doc = TEMPLATE_FORMAT_DOC.replace(
            "14:18 [TRIGGER]    Config deploy merged via CI (GitHub PR #4521)",
            "| 14:18 | TRIGGER | Config deploy merged via CI (GitHub PR #4521) |")
        self.assertEqual([], [f for f in lint_postmortem.lint(doc)
                              if f.check.startswith("timeline-")])


class ActionTableTests(unittest.TestCase):
    """Table-form action items are linted, not skipped."""

    def test_empty_owner_and_deadline_cells_are_critical(self):
        doc = TEMPLATE_FORMAT_DOC.replace(
            "| AI-1 | Prevent | Add config schema validation | @platform | 2024-04-01 | JIRA-4521 | Open |",
            "| AI-1 | Prevent | Add config schema validation |  |  |  |  |")
        findings = lint_postmortem.lint(doc)
        self.assertIn(lint_postmortem.CRITICAL, severities(findings, "action-owner"))
        self.assertIn(lint_postmortem.CRITICAL, severities(findings, "action-deadline"))

    def test_tbd_cells_are_critical(self):
        doc = TEMPLATE_FORMAT_DOC.replace("| @sre | Mar 22 |", "| TBD | TBD |")
        findings = lint_postmortem.lint(doc)
        self.assertIn(lint_postmortem.CRITICAL, severities(findings, "action-owner"))
        self.assertIn(lint_postmortem.CRITICAL, severities(findings, "action-deadline"))

    def test_freeform_non_date_deadline_in_table_is_critical(self):
        """A deadline must be date-shaped, not merely non-empty.

        Mutation testing found this gap: every other deadline test used a value that
        was also on the placeholder list, so the date-shape branch was never exercised
        and could be deleted with the suite still green.
        """
        doc = TEMPLATE_FORMAT_DOC.replace("| @sre | Mar 22 |", "| @sre | when the sprint ends |")
        self.assertIn(lint_postmortem.CRITICAL,
                      severities(lint_postmortem.lint(doc), "action-deadline"))

    def test_freeform_non_date_deadline_in_list_is_critical(self):
        doc = GOOD_DOC.replace("deadline: Mar 22", "deadline: after the migration")
        self.assertIn(lint_postmortem.CRITICAL,
                      severities(lint_postmortem.lint(doc), "action-deadline"))

    def test_missing_owner_column_is_critical(self):
        doc = TEMPLATE_FORMAT_DOC.replace(" Owner |", " Assignee-ish |")
        self.assertIn("action-owner", checks(lint_postmortem.lint(doc)))

    def test_generic_team_handle_is_not_an_owner(self):
        doc = TEMPLATE_FORMAT_DOC.replace("| @platform | 2024-04-01 |", "| @team | 2024-04-01 |")
        self.assertIn("action-owner", checks(lint_postmortem.lint(doc)))

    def test_named_team_handle_is_an_owner(self):
        doc = TEMPLATE_FORMAT_DOC.replace("| @platform | 2024-04-01 |", "| @payments-team | 2024-04-01 |")
        self.assertNotIn("action-owner", checks(lint_postmortem.lint(doc)))

    def test_empty_action_section_is_critical(self):
        doc = re.sub(r"(?s)## Action Items\n.*?\n\n## Uncovered",
                     "## Action Items\n\n## Uncovered", TEMPLATE_FORMAT_DOC)
        findings = lint_postmortem.lint(doc)
        self.assertIn("action-owner", checks(findings))

    def test_placeholder_deadline_in_list_form_is_critical(self):
        doc = GOOD_DOC.replace("deadline: Mar 22", "deadline: TBD")
        self.assertIn("action-deadline", checks(lint_postmortem.lint(doc)))

    def test_vague_deadline_in_list_form_is_critical(self):
        doc = GOOD_DOC.replace("deadline: Mar 22", "deadline: next quarter")
        self.assertIn("action-deadline", checks(lint_postmortem.lint(doc)))

    def test_checklist_boxes_are_not_action_items(self):
        doc = TEMPLATE_FORMAT_DOC.replace(
            "## Uncovered Risks", "- [ ] reviewed by owners\n\n## Uncovered Risks")
        self.assertEqual([], [str(f) for f in lint_postmortem.lint(doc)])


class TimelineQualityTests(unittest.TestCase):

    def test_impossible_clock_time_is_critical(self):
        doc = GOOD_DOC.replace("- 14:23 ", "- 99:99 ")
        hits = [f for f in lint_postmortem.lint(doc) if f.check == "timeline-utc"]
        self.assertTrue(hits)
        self.assertEqual(lint_postmortem.CRITICAL, hits[0].severity)
        self.assertIn("impossible", hits[0].message)

    def test_out_of_order_entry_is_warned(self):
        doc = GOOD_DOC.replace("- 15:10 Service restored after config rollback (deploy log)",
                               "- 09:10 Service restored after config rollback (deploy log)\n"
                               "- 08:00 Follow-up note (Slack)")
        self.assertIn("timeline-order", checks(lint_postmortem.lint(doc)))

    def test_single_midnight_wrap_is_not_flagged(self):
        doc = GOOD_DOC.replace("- 15:10 Service restored after config rollback (deploy log)",
                               "- 00:20 Service restored after config rollback (deploy log)")
        self.assertNotIn("timeline-order", checks(lint_postmortem.lint(doc)))

    def test_untimed_entry_is_not_silently_ignored(self):
        doc = GOOD_DOC.replace("- 14:35 Scaled to 10 replicas, no improvement (Slack #incident-0142)",
                               "- Scaled to 10 replicas, no improvement (Slack #incident-0142)")
        hits = [f for f in lint_postmortem.lint(doc) if f.check == "timeline-untimed"]
        self.assertEqual(1, len(hits))

    def test_prose_in_timeline_is_allowed(self):
        doc = GOOD_DOC.replace("## Timeline (UTC)",
                               "## Timeline (UTC)\nAll timestamps normalised from PagerDuty.")
        self.assertNotIn("timeline-untimed", checks(lint_postmortem.lint(doc)))

    def test_missing_utc_declaration_is_warned(self):
        doc = GOOD_DOC.replace("## Timeline (UTC)", "## Timeline")
        hits = [f for f in lint_postmortem.lint(doc) if f.check == "timeline-timezone"]
        self.assertEqual(1, len(hits))
        self.assertIn("does not declare UTC", hits[0].message)

    def test_non_utc_zone_is_warned(self):
        doc = GOOD_DOC.replace("- 14:23 payment-api error rate spiked to 15% (Grafana: payment-slo)",
                               "- 14:23 PST payment-api error rate spiked (Grafana: payment-slo)")
        hits = [f for f in lint_postmortem.lint(doc) if f.check == "timeline-timezone"]
        self.assertEqual(1, len(hits))
        self.assertIn("PST", hits[0].message)

    def test_midline_parenthetical_is_not_a_source(self):
        """The source must end the entry.

        Supporting `| 14:18 | ... (src) |` table rows required relaxing the old
        end-of-line anchor; relaxing it to "parens anywhere" would silently accept an
        aside as evidence, which is the exact defect AE-2 exists to prevent.
        """
        doc = GOOD_DOC.replace(
            "- 14:26 PagerDuty alert fired: p99 > 500ms (PD incident #4821)",
            "- 14:26 PagerDuty alert (briefly) fired and nobody recorded where")
        hits = [f for f in lint_postmortem.lint(doc) if f.check == "timeline-source"]
        self.assertEqual(1, len(hits))

    def test_utc_offset_zero_is_not_reported_as_non_utc(self):
        """`+00:00` is UTC. An earlier lookbehind flagged it as a foreign zone."""
        doc = GOOD_DOC.replace("- 14:23 ", "- 2024-03-15T14:23+00:00 ")
        self.assertEqual([], [f for f in lint_postmortem.lint(doc)
                              if f.check == "timeline-timezone"])

    def test_duration_range_is_not_reported_as_a_timezone(self):
        """`14:23-15:10` is a range, not an offset — it must not be flagged."""
        doc = GOOD_DOC.replace("## Uncovered Risks",
                               "## Impact\nDuration 47 min (14:23-15:10 UTC).\n\n"
                               "## Uncovered Risks")
        self.assertEqual([], [f for f in lint_postmortem.lint(doc)
                              if f.check == "timeline-timezone"])

    def test_table_separator_row_is_not_an_entry(self):
        doc = GOOD_DOC.replace(
            "- 14:23 payment-api error rate spiked to 15% (Grafana: payment-slo)",
            "| Time | Event |\n|------|-------|\n| 14:23 | error rate spiked (Grafana) |")
        self.assertNotIn("timeline-untimed", checks(lint_postmortem.lint(doc)))


class UncoveredRisksTests(unittest.TestCase):
    """§9.9 says 'Mandatory — never empty'. The linter now enforces both halves."""

    def test_missing_section_is_critical(self):
        doc = GOOD_DOC.replace("## Uncovered Risks", "## Misc")
        hits = [f for f in lint_postmortem.lint(doc) if f.check == "uncovered-risks"]
        self.assertEqual(1, len(hits))
        self.assertEqual(lint_postmortem.CRITICAL, hits[0].severity)

    def test_empty_section_is_critical(self):
        doc = GOOD_DOC.replace("- Downstream cascade effects not traced", "")
        hits = [f for f in lint_postmortem.lint(doc) if f.check == "uncovered-risks"]
        self.assertEqual(1, len(hits))
        self.assertIn("never empty", hits[0].message)

    def test_placeholder_only_section_is_critical(self):
        doc = GOOD_DOC.replace("- Downstream cascade effects not traced", "- N/A")
        self.assertIn("uncovered-risks", checks(lint_postmortem.lint(doc)))


class SensitiveDataTests(unittest.TestCase):
    """Gate 5. A post-mortem circulates far wider than the logs it came from."""

    def test_aws_key_is_critical(self):
        doc = GOOD_DOC + "\nDebug: used AKIAIOSFODNN7EXAMPLE to reach the bucket.\n"
        hits = [f for f in lint_postmortem.lint(doc) if f.check == "sensitive-data"]
        self.assertEqual(1, len(hits))
        self.assertEqual(lint_postmortem.CRITICAL, hits[0].severity)

    def test_private_key_block_is_critical(self):
        doc = GOOD_DOC + "\n-----BEGIN RSA PRIVATE KEY-----\n"
        self.assertIn(lint_postmortem.CRITICAL,
                      severities(lint_postmortem.lint(doc), "sensitive-data"))

    def test_inline_password_is_critical(self):
        doc = GOOD_DOC + "\nThe config read password: hunter2hunter2\n"
        self.assertIn(lint_postmortem.CRITICAL,
                      severities(lint_postmortem.lint(doc), "sensitive-data"))

    def test_jwt_is_critical(self):
        doc = GOOD_DOC + ("\nHeader was eyJhbGciOiJIUzI1NiJ9."
                          "eyJzdWIiOiIxMjM0NTY3ODkwIn0.dBjftJeZ4CVPmB92K27uhbUJU1p1r_wW1g\n")
        self.assertIn(lint_postmortem.CRITICAL,
                      severities(lint_postmortem.lint(doc), "sensitive-data"))

    def test_email_is_warning_not_critical(self):
        doc = GOOD_DOC + "\nReported by customer alice@example.com.\n"
        sev = severities(lint_postmortem.lint(doc), "sensitive-data")
        self.assertEqual([lint_postmortem.WARNING], sev)

    def test_ipv4_is_warning(self):
        doc = GOOD_DOC + "\nRequests originated from 203.0.113.42.\n"
        self.assertEqual([lint_postmortem.WARNING],
                         severities(lint_postmortem.lint(doc), "sensitive-data"))

    def test_luhn_valid_card_is_critical(self):
        doc = GOOD_DOC + "\nFailed charge on card 4242424242424242.\n"
        self.assertIn(lint_postmortem.CRITICAL,
                      severities(lint_postmortem.lint(doc), "sensitive-data"))

    def test_non_luhn_long_number_is_not_a_card(self):
        """Guard against flagging request counts and IDs as payment data."""
        doc = GOOD_DOC + "\nProcessed 1234567890123456 events during the window.\n"
        self.assertEqual([], [f for f in lint_postmortem.lint(doc)
                              if f.check == "sensitive-data"])

    def test_redacted_marker_suppresses_the_finding(self):
        doc = GOOD_DOC + "\nThe config read password: ***REDACTED***\n"
        self.assertEqual([], [f for f in lint_postmortem.lint(doc)
                              if f.check == "sensitive-data"])

    def test_at_handles_are_not_emails(self):
        """`owner: @sre` must never be mistaken for PII."""
        self.assertEqual([], [f for f in lint_postmortem.lint(GOOD_DOC)
                              if f.check == "sensitive-data"])


class ModeGatingTests(unittest.TestCase):
    """§9.0 — each mode is linted only against the sections its contract requires."""

    def test_all_modes_accepted(self):
        for mode in lint_postmortem.MODES:
            lint_postmortem.lint(GOOD_DOC, mode)  # must not raise

    def test_unknown_mode_raises(self):
        with self.assertRaises(ValueError):
            lint_postmortem.lint(GOOD_DOC, "sideways")

    def test_extract_mode_ignores_action_items(self):
        doc = GOOD_DOC.replace("## Action Items", "## Notes")
        self.assertIn("action-owner", checks(lint_postmortem.lint(doc, "draft")))
        self.assertNotIn("action-owner", checks(lint_postmortem.lint(doc, "extract")))

    def test_review_mode_ignores_timeline(self):
        doc = ("# Review findings\n\n## Action Items\n"
               "- Add sources to the timeline (owner: @alice, deadline: Mar 22)\n\n"
               "## Uncovered Risks\n- did not re-verify the root cause\n")
        self.assertNotIn("timeline-utc", checks(lint_postmortem.lint(doc, "review")))

    def test_review_improvement_items_need_owner_and_deadline(self):
        """§9.7 items in Review fix the document, but they are still commitments.
        A review report whose whole plan is `- improve it` was lint-clean."""
        doc = ("# Review findings\n\n## Action Items\n- improve it\n\n"
               "## Uncovered Risks\n- did not re-verify the root cause\n")
        names = checks(lint_postmortem.lint(doc, "review"))
        self.assertIn("action-owner", names)
        self.assertIn("action-deadline", names)

    def test_review_mode_exempt_from_incident_categories(self):
        """prevent/detect/mitigate classify system fixes, not document fixes."""
        doc = ("# Review findings\n\n## Action Items\n"
               "- Add sources to the timeline (owner: @alice, deadline: Mar 22)\n\n"
               "## Uncovered Risks\n- did not re-verify the root cause\n")
        self.assertNotIn("action-categories", checks(lint_postmortem.lint(doc, "review")))

    def test_planning_mode_checks_only_risks_and_secrets(self):
        """§9.0 requires 9.9 in Planning too — "what this guide does not cover"."""
        doc = ("# Post-mortem process guide\n\nUse the template.\n\n"
               "## Uncovered Risks\n- does not cover regulated incidents\n")
        self.assertEqual(set(), checks(lint_postmortem.lint(doc, "planning")))

    def test_planning_mode_still_requires_uncovered_risks(self):
        doc = "# Post-mortem process guide\n\nUse the template.\n"
        self.assertIn("uncovered-risks", checks(lint_postmortem.lint(doc, "planning")))

    def test_planning_mode_still_blocks_credentials(self):
        doc = "# Process guide\n\nExample: AKIAIOSFODNN7EXAMPLE\n"
        self.assertIn("sensitive-data", checks(lint_postmortem.lint(doc, "planning")))

    def test_uncovered_risks_required_in_every_incident_mode(self):
        doc = "# Timeline only\n\n## Timeline (UTC)\n- 14:23 spike (Grafana)\n"
        for mode in ("draft", "extract", "review"):
            self.assertIn("uncovered-risks", checks(lint_postmortem.lint(doc, mode)),
                          f"{mode} must require §9.9")

    def test_cli_mode_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc = Path(tmp) / "extract.md"
            doc.write_text("# Extract\n\n## Timeline (UTC)\n- 14:23 spike (Grafana)\n"
                           "\n## Uncovered Risks\n- no logs after 15:00\n", encoding="utf-8")
            self.assertEqual(0, subprocess.run(
                [sys.executable, str(SCRIPT), str(doc), "--mode", "extract"],
                capture_output=True).returncode)
            # Same file in draft mode is incomplete: no Action Items section.
            self.assertEqual(1, subprocess.run(
                [sys.executable, str(SCRIPT), str(doc), "--mode", "draft"],
                capture_output=True).returncode)

    def test_cli_rejects_unknown_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc = Path(tmp) / "d.md"
            doc.write_text(GOOD_DOC, encoding="utf-8")
            self.assertEqual(2, subprocess.run(
                [sys.executable, str(SCRIPT), str(doc), "--mode", "sideways"],
                capture_output=True).returncode)

class SectionResolutionTests(unittest.TestCase):
    """`section()` took the first heading that merely *contained* the word, so a title
    like `# Timeline extract — INC-0142` shadowed the real `## Timeline (UTC)` and the
    document was reported as having no timestamped entries."""

    DOC = ("# Timeline extract — INC-2024-0142\n\n"
           "## Timeline (UTC)\n"
           "14:23 [DETECTION] Error rate spike (Grafana)\n\n"
           "## Uncovered Risks\n- root cause not analyzed\n")

    def test_h1_title_does_not_shadow_the_h2_section(self):
        self.assertNotIn("timeline-utc", checks(
            lint_postmortem.lint(self.DOC, "extract", "quick")))

    def test_h1_still_used_when_no_h2_exists(self):
        """Preferring H2 must not mean ignoring H1 — fall back, don't skip."""
        doc = self.DOC.replace("## Timeline (UTC)\n", "")
        self.assertNotIn("timeline-utc", checks(
            lint_postmortem.lint(doc, "extract", "quick")))

    def test_h1_fallback_still_lints_its_content(self):
        """Prove the fallback really parsed the H1 body rather than finding nothing."""
        doc = self.DOC.replace("## Timeline (UTC)\n", "").replace(" (Grafana)", "")
        self.assertIn("timeline-source", checks(
            lint_postmortem.lint(doc, "extract", "quick")))

    def test_action_items_title_shadowing(self):
        doc = ("# Action Items follow-up review\n\n## Timeline (UTC)\n"
               "14:23 [DETECTION] spike (Grafana)\n\n"
               "## Action Items\n"
               "- [Prevent] fix (owner: @sre, deadline: Mar 22)\n"
               "- [Detect] watch (owner: @sre, deadline: Mar 23)\n"
               "- [Mitigate] cap (owner: @sre, deadline: Mar 24)\n\n"
               "## What Went Well\n- ok\n\n## Uncovered Risks\n- x\n")
        self.assertEqual([], [str(f) for f in lint_postmortem.lint(doc)])


class EmptyActionTableTests(unittest.TestCase):
    """A table with headers and no data rows counted as "has items", so an empty
    Action Items table exited 0 in non-strict mode."""

    HEADER_ONLY = ("# PM\n\n## Timeline (UTC)\n14:23 [DETECTION] spike (Grafana)\n\n"
                   "## Action Items\n"
                   "| ID | Category | Description | Owner | Deadline |\n"
                   "|----|----------|-------------|-------|----------|\n\n"
                   "## What Went Well\n- prevent detect mitigate\n\n"
                   "## Uncovered Risks\n- x\n")

    def test_header_only_table_is_critical(self):
        hits = [f for f in lint_postmortem.lint(self.HEADER_ONLY)
                if f.check == "action-owner"]
        self.assertEqual(1, len(hits))
        self.assertEqual(lint_postmortem.CRITICAL, hits[0].severity)
        self.assertIn("no items", hits[0].message)

    def test_header_only_table_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "d.md"
            f.write_text(self.HEADER_ONLY, encoding="utf-8")
            self.assertEqual(1, subprocess.run(
                [sys.executable, str(SCRIPT), str(f)], capture_output=True).returncode)

    def test_table_with_a_data_row_is_not_empty(self):
        doc = self.HEADER_ONLY.replace(
            "|----|----------|-------------|-------|----------|\n",
            "|----|----------|-------------|-------|----------|\n"
            "| AI-1 | Prevent | Add validation | @sre | Mar 22 |\n")
        self.assertNotIn("no items", " ".join(str(f) for f in lint_postmortem.lint(doc)))


class RedactionScopeTests(unittest.TestCase):
    """A redaction marker exempts the span it replaces, never the whole line."""

    def test_live_key_beside_a_redacted_value_is_still_caught(self):
        doc = GOOD_DOC + "\nEnv: DB_PASS=***REDACTED*** AWS_KEY=AKIAIOSFODNN7EXAMPLE\n"
        hits = [f for f in lint_postmortem.lint(doc) if f.check == "sensitive-data"]
        self.assertEqual(1, len(hits))
        self.assertEqual(lint_postmortem.CRITICAL, hits[0].severity)
        self.assertIn("AWS", hits[0].message)

    def test_properly_redacted_line_stays_clean(self):
        doc = GOOD_DOC + "\nEnv: DB_PASS=***REDACTED*** AWS_KEY=<redacted>\n"
        self.assertEqual([], [f for f in lint_postmortem.lint(doc)
                              if f.check == "sensitive-data"])

    def test_redaction_does_not_merge_neighbours_into_a_false_match(self):
        """Substituting NUL rather than deleting keeps tokens apart."""
        doc = GOOD_DOC + "\npassword: ***REDACTED*** hunter2hunter2trailing\n"
        hits = [f for f in lint_postmortem.lint(doc) if f.check == "sensitive-data"]
        self.assertEqual([], hits, "redacted assignment must not re-pair with the next token")


class CategoryWaiverTests(unittest.TestCase):
    """Demanding all three categories unconditionally produced filler action items."""

    BASE = ("# PM\n\n## Timeline (UTC)\n14:23 [DETECTION] spike (Grafana)\n\n"
            "## Action Items\n"
            "| ID | Category | Description | Owner | Deadline |\n"
            "|----|----------|-------------|-------|----------|\n"
            "| AI-1 | Prevent | Add validation | @sre | Mar 22 |\n"
            "| AI-2 | Detect | Add alert | @sre | Mar 23 |\n\n"
            "{waiver}"
            "## What Went Well\n- ok\n\n## Uncovered Risks\n- x\n")

    def test_missing_category_without_waiver_warns(self):
        doc = self.BASE.format(waiver="")
        hits = [f for f in lint_postmortem.lint(doc) if f.check == "action-categories"]
        self.assertEqual(1, len(hits))
        self.assertIn("mitigate", hits[0].message)

    def test_explicit_na_waiver_satisfies_the_category(self):
        doc = self.BASE.format(
            waiver="Mitigate: N/A — failure is instantaneous, no window to reduce impact.\n\n")
        self.assertEqual([], [f for f in lint_postmortem.lint(doc)
                              if f.check == "action-categories"])

    def test_waiver_is_not_owner_checked(self):
        """A waiver commits to no work, so it must not be flagged for a missing owner."""
        doc = self.BASE.format(
            waiver="- Mitigate: N/A — failure is instantaneous, nothing to cap.\n\n")
        self.assertEqual([], [f for f in lint_postmortem.lint(doc)
                              if f.check.startswith("action-")])

    def test_all_categories_waived_still_means_no_action_items(self):
        doc = ("# PM\n\n## Timeline (UTC)\n14:23 [DETECTION] spike (Grafana)\n\n"
               "## Action Items\nPrevent: N/A. Detect: N/A. Mitigate: N/A.\n\n"
               "## What Went Well\n- ok\n\n## Uncovered Risks\n- x\n")
        self.assertIn("action-owner", checks(lint_postmortem.lint(doc)))

    def test_bare_category_word_no_longer_satisfies_the_check(self):
        """The old check passed on the word appearing anywhere in the section."""
        doc = self.BASE.format(waiver="We should mitigate this class of failure someday.\n\n")
        hits = [f for f in lint_postmortem.lint(doc) if f.check == "action-categories"]
        self.assertEqual(1, len(hits), "prose mentioning a category is not an action item")


class QuickDepthTests(unittest.TestCase):
    """Quick delivers one section + the 9.2/9.9 spine (SKILL.md §3). Without a depth
    flag, an output that perfectly obeyed the Quick contract failed the gate."""

    QUICK = ("# INC-2024-0142 timeline\n\n## Mode & Depth\nDraft + Quick.\n\n"
             "## Timeline (UTC)\n"
             "14:23 [DETECTION] Error rate spike (Grafana: payment-slo)\n"
             "14:45 [MITIGATION] Config rolled back (ArgoCD)\n\n"
             "## Uncovered Risks\n- Root cause not analyzed; timeline only.\n")

    def test_standard_depth_rejects_the_quick_deliverable(self):
        self.assertTrue([f for f in lint_postmortem.lint(self.QUICK, "draft", "standard")
                         if f.severity == lint_postmortem.CRITICAL])

    def test_quick_depth_accepts_it(self):
        self.assertEqual([], [str(f) for f in lint_postmortem.lint(self.QUICK, "draft", "quick")])

    def test_quick_still_lints_present_sections(self):
        doc = self.QUICK.replace(" (Grafana: payment-slo)", "")
        self.assertIn("timeline-source", checks(lint_postmortem.lint(doc, "draft", "quick")))

    def test_quick_still_requires_uncovered_risks(self):
        doc = self.QUICK.replace("## Uncovered Risks", "## Notes")
        hits = [f for f in lint_postmortem.lint(doc, "draft", "quick")
                if f.check == "uncovered-risks"]
        self.assertEqual(lint_postmortem.CRITICAL, hits[0].severity)

    def test_quick_still_catches_credentials(self):
        doc = self.QUICK + "\nAKIAIOSFODNN7EXAMPLE\n"
        self.assertIn("sensitive-data", checks(lint_postmortem.lint(doc, "draft", "quick")))

    def test_unknown_depth_raises(self):
        with self.assertRaises(ValueError):
            lint_postmortem.lint(GOOD_DOC, "draft", "exhaustive")

    def test_cli_depth_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "q.md"
            f.write_text(self.QUICK, encoding="utf-8")
            self.assertEqual(1, subprocess.run(
                [sys.executable, str(SCRIPT), str(f)], capture_output=True).returncode)
            self.assertEqual(0, subprocess.run(
                [sys.executable, str(SCRIPT), str(f), "--depth", "quick"],
                capture_output=True).returncode)

    def test_cli_rejects_unknown_depth(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "q.md"
            f.write_text(self.QUICK, encoding="utf-8")
            self.assertEqual(2, subprocess.run(
                [sys.executable, str(SCRIPT), str(f), "--depth", "exhaustive"],
                capture_output=True).returncode)


class UserPinnedFormatTests(unittest.TestCase):
    """§9.0: an explicit user format instruction outranks the output contract.

    Observed in a live run: asked for "only the RCA section", the model correctly chose
    a non-linear technique but dropped the 9.2/9.9 spine to obey the user. The spine has
    to move out of the artifact rather than force the model to disobey.
    """

    RCA_ONLY = ("## Root Cause Analysis\n"
                "Technique: fishbone — four parallel conditions, no single chain.\n"
                "- Process: migration held a long lock\n"
                "- Environment: marketing email drove 4x traffic\n"
                "- Technology: connection pool ceiling never raised\n")

    def test_pinned_artifact_is_not_penalised_for_a_missing_spine(self):
        self.assertEqual([], [str(f) for f in lint_postmortem.lint(
            self.RCA_ONLY, "draft", "quick", user_pinned_format=True)])

    def test_unpinned_artifact_still_requires_uncovered_risks(self):
        self.assertIn("uncovered-risks", checks(
            lint_postmortem.lint(self.RCA_ONLY, "draft", "quick")))

    def test_pinned_does_not_waive_content_checks(self):
        """Waiving §9.9 must not become a blanket amnesty."""
        doc = self.RCA_ONLY + "\n## Timeline (UTC)\n- 14:23 spike with no source\n"
        names = checks(lint_postmortem.lint(doc, "draft", "quick",
                                            user_pinned_format=True))
        self.assertIn("timeline-source", names)

    def test_pinned_does_not_waive_credentials(self):
        doc = self.RCA_ONLY + "\nkey AKIAIOSFODNN7EXAMPLE\n"
        self.assertIn("sensitive-data", checks(lint_postmortem.lint(
            doc, "draft", "quick", user_pinned_format=True)))

    def test_cli_pinned_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "rca.md"
            f.write_text(self.RCA_ONLY, encoding="utf-8")
            self.assertEqual(1, subprocess.run(
                [sys.executable, str(SCRIPT), str(f), "--depth", "quick"],
                capture_output=True).returncode)
            self.assertEqual(0, subprocess.run(
                [sys.executable, str(SCRIPT), str(f), "--depth", "quick",
                 "--user-pinned-format"], capture_output=True).returncode)

    def test_skill_documents_the_precedence_rule(self):
        skill = (Path(__file__).resolve().parents[2] / "SKILL.md").read_text(encoding="utf-8")
        flat = re.sub(r"\s+", " ", skill)
        self.assertIn("An explicit user format instruction outranks this contract", flat)
        self.assertIn("Never drop 9.9 *silently*", flat)
        self.assertIn("--user-pinned-format", flat)


class DeepDepthTests(unittest.TestCase):
    """`deep` must be accepted, not a usage error — §3 forces it for SEV-1."""

    def test_deep_is_a_valid_depth(self):
        self.assertIn("deep", lint_postmortem.DEPTHS)
        lint_postmortem.lint(GOOD_DOC, "draft", "deep")  # must not raise

    def test_deep_lints_like_standard_not_like_quick(self):
        doc = GOOD_DOC.replace("## Action Items", "## Notes")
        self.assertIn("action-owner", checks(lint_postmortem.lint(doc, "draft", "deep")))
        self.assertNotIn("action-owner", checks(lint_postmortem.lint(doc, "draft", "quick")))

    def test_cli_accepts_deep(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "d.md"
            f.write_text(GOOD_DOC, encoding="utf-8")
            self.assertEqual(0, subprocess.run(
                [sys.executable, str(SCRIPT), str(f), "--depth", "deep"],
                capture_output=True).returncode)


class CategoryWaiverReasonTests(unittest.TestCase):
    """A waiver must justify itself; `Mitigate: N/A` alone is a tick-box."""

    BASE = ("# PM\n\n## Timeline (UTC)\n14:23 [DETECTION] spike (Grafana)\n\n"
            "## Action Items\n"
            "| ID | Category | Description | Owner | Deadline |\n"
            "|----|----------|-------------|-------|----------|\n"
            "| AI-1 | Prevent | Add validation | @sre | Mar 22 |\n"
            "| AI-2 | Detect | Add alert | @sre | Mar 23 |\n\n"
            "{waiver}"
            "## What Went Well\n- ok\n\n## Uncovered Risks\n- x\n")

    def _cat_findings(self, waiver):
        return [f for f in lint_postmortem.lint(self.BASE.format(waiver=waiver))
                if f.check == "action-categories"]

    def test_bare_na_is_rejected(self):
        hits = self._cat_findings("Mitigate: N/A\n\n")
        self.assertEqual(1, len(hits))
        self.assertIn("without a reason", hits[0].message)

    def test_na_with_reason_is_accepted(self):
        self.assertEqual([], self._cat_findings(
            "Mitigate: N/A — the failure is instantaneous, no window exists.\n\n"))

    def test_two_word_reason_is_too_thin(self):
        self.assertEqual(1, len(self._cat_findings("Mitigate: N/A — no window\n\n")))

    def test_table_cell_waiver_with_reason_is_accepted(self):
        self.assertEqual([], self._cat_findings(
            "| AI-3 | Mitigate | N/A — no window exists to reduce impact | — | — |\n\n"))

    def test_item_merely_containing_na_is_not_a_waiver(self):
        """An ordinary item mentioning n/a must stay owner-checked."""
        doc = self.BASE.format(waiver="") .replace(
            "| AI-2 | Detect | Add alert | @sre | Mar 23 |",
            "| AI-2 | Detect | Alert when the field is n/a | | |")
        names = checks(lint_postmortem.lint(doc))
        self.assertIn("action-owner", names)
        self.assertIn("action-deadline", names)

    def test_min_reason_words_is_declared(self):
        self.assertEqual(3, lint_postmortem.MIN_REASON_WORDS)


ZH_DOC = """# 事故复盘：支付接口错误率升高（INC-2024-0142）

## 摘要
2024-03-15，payment-api 错误率达到 15.2%，持续 47 分钟。

## 时间线（UTC）
14:18 [TRIGGER] 配置变更上线（GitHub PR #4521）
14:23 [DETECTION] 错误率突增至 15.2%（Grafana：payment-slo）
14:45 [MITIGATION] 回滚配置（ArgoCD 审计日志）
14:48 [RECOVERY] 错误率回到基线（Grafana：payment-slo）

## 根因分析
方法：5-Why（线性因果链）。深度 5。

## 做得好的地方
- 首次报错后 3 分钟内告警触发。

## 行动项
| ID | 类别 | 描述 | 负责人 | 截止日期 | 工单 |
|----|------|------|--------|----------|------|
| AI-1 | 预防 | 在 CI 增加配置结构校验 | @platform | 2024-04-01 | JIRA-1 |
| AI-2 | 检测 | 增加 Redis 连接失败告警 | @sre | 2024-03-22 | JIRA-2 |
| AI-3 | 缓解 | 错误率突增自动回滚 | @platform | 2024-04-15 | JIRA-3 |

## 未覆盖风险
- 未量化收入影响，缺少交易金额数据。
"""


class ChineseDocumentTests(unittest.TestCase):
    """The skill follows the user's language, so the mechanical layer must too.

    Before the bilingual aliases, this document drew three criticals: no Timeline,
    no Action Items and no Uncovered Risks section.
    """

    def test_chinese_document_is_clean(self):
        self.assertEqual([], [str(f) for f in lint_postmortem.lint(ZH_DOC)])

    def test_chinese_headings_are_found(self):
        for rx, label in ((lint_postmortem.TIMELINE_HEADING_RE, "时间线"),
                          (lint_postmortem.ACTION_HEADING_RE, "行动项"),
                          (lint_postmortem.WENT_WELL_HEADING_RE, "做得好的地方"),
                          (lint_postmortem.RISKS_HEADING_RE, "未覆盖风险")):
            self.assertTrue(rx.search(ZH_DOC), f"heading not matched: {label}")

    def test_fullwidth_parentheses_count_as_a_source(self):
        doc = ZH_DOC.replace("（Grafana：payment-slo）", "")
        self.assertIn("timeline-source", checks(lint_postmortem.lint(doc)))

    def test_chinese_owner_column_is_read(self):
        doc = ZH_DOC.replace("| @platform | 2024-04-01 |", "|  |  |")
        names = checks(lint_postmortem.lint(doc))
        self.assertIn("action-owner", names)
        self.assertIn("action-deadline", names)

    def test_chinese_category_names_count(self):
        """预防/检测/缓解 satisfy prevent/detect/mitigate."""
        self.assertNotIn("action-categories", checks(lint_postmortem.lint(ZH_DOC)))

    def test_chinese_date_format_is_a_deadline(self):
        doc = ZH_DOC.replace("2024-04-01", "2024年4月1日")
        self.assertNotIn("action-deadline", checks(lint_postmortem.lint(doc)))

    def test_chinese_placeholder_owner_is_rejected(self):
        doc = ZH_DOC.replace("| @platform | 2024-04-01 |", "| 待定 | 2024-04-01 |")
        self.assertIn("action-owner", checks(lint_postmortem.lint(doc)))

    MITIGATE_ROW = "| AI-3 | 缓解 | 错误率突增自动回滚 | @platform | 2024-04-15 | JIRA-3 |\n"

    def _waive(self, text: str) -> str:
        """Replace the 缓解 row with a waiver, in place — a waiver placed after the
        document's last section is outside the Action Items body and is never read."""
        return ZH_DOC.replace(self.MITIGATE_ROW, text)

    def test_chinese_waiver_with_reason_is_accepted(self):
        doc = self._waive("\n缓解：不适用 —— 故障瞬间发生，没有可以降低影响的窗口。\n")
        self.assertNotIn("action-categories", checks(lint_postmortem.lint(doc)))

    def test_chinese_waiver_without_reason_is_rejected(self):
        doc = self._waive("\n缓解：不适用\n")
        hits = [f for f in lint_postmortem.lint(doc) if f.check == "action-categories"]
        self.assertEqual(1, len(hits))
        self.assertIn("without a reason", hits[0].message)

    def test_cjk_reason_weighting(self):
        """CJK carries no spaces, so a Latin word count reads a Chinese reason as empty."""
        self.assertEqual(0, lint_postmortem._reason_weight(""))
        self.assertGreaterEqual(lint_postmortem._reason_weight("没有可以降低影响的窗口"), 3)
        self.assertLess(lint_postmortem._reason_weight("无窗口"), 3)

    def test_chinese_blame_phrase_is_flagged(self):
        doc = ZH_DOC + "\n根因是人为失误。\n"
        self.assertIn("blame-language", checks(lint_postmortem.lint(doc)))

    def test_beijing_time_is_a_non_utc_zone(self):
        doc = ZH_DOC.replace("## 时间线（UTC）", "## 时间线（北京时间）")
        hits = [f for f in lint_postmortem.lint(doc) if f.check == "timeline-timezone"]
        self.assertTrue(hits)
        self.assertIn("北京时间", hits[0].message)

    def test_english_document_still_clean(self):
        """Adding aliases must not break the Latin path."""
        self.assertEqual([], [str(f) for f in lint_postmortem.lint(GOOD_DOC)])


if __name__ == "__main__":
    unittest.main()
