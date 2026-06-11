"""Behavioral tests for scripts/lint_postmortem.py — the mechanical scorecard layer."""

import importlib.util
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

## Timeline
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


if __name__ == "__main__":
    unittest.main()