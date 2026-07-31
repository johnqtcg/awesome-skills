"""Golden scenario tests: validate real commands, not keyword presence.

The previous version concatenated every markdown file in the skill and asserted
that each fixture's keywords appeared *somewhere* in that blob. That passes as
long as the words exist — it cannot tell a complete, correct, runnable command
from a plausible-looking fragment, and a keyword satisfied by an unrelated
reference file counted for the scenario under test.

This version binds each fixture to the actual template section for its scenario
and checks three things about the command found there:

1. it parses cleanly through the installed yt-dlp (offline: every flag, flag
   argument, argument value and `-f` expression is validated by the binary),
2. it contains the flags the scenario requires,
3. it contains none of the flags the scenario forbids, and it satisfies the
   skill's pairing invariants (`--embed-subs` needs `--write-subs`, …).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[2]
GOLDEN_DIR = Path(__file__).resolve().parent / "golden"
TEMPLATES = SKILL_ROOT / "references" / "scenario-templates.md"

sys.path.insert(0, str(SKILL_ROOT / "scripts"))
import extract_commands as ec  # noqa: E402


def template_sections():
    """Map each `## N) Title` heading to the commands inside it."""
    text = TEMPLATES.read_text(encoding="utf-8")
    sections = {}
    parts = re.split(r"(?m)^## (.+)$", text)
    for title, body in zip(parts[1::2], parts[2::2]):
        commands = []
        for block in ec.iter_command_blocks(body):
            commands.extend(ec.split_commands(block))
        sections[title.strip()] = commands
    return sections


def load_fixtures():
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(GOLDEN_DIR.glob("*.json"))}


class TestScenarioCommands(unittest.TestCase):
    """Each fixture names a template section and asserts its command's shape."""

    @classmethod
    def setUpClass(cls):
        cls.sections = template_sections()
        cls.fixtures = load_fixtures()

    def scenario_commands(self, fixture):
        title = fixture["template_section"]
        self.assertIn(
            title, self.sections,
            f"template section '{title}' not found; sections are {sorted(self.sections)}",
        )
        commands = self.sections[title]
        self.assertTrue(commands, f"section '{title}' contains no yt-dlp command")
        return commands

    def test_every_fixture_binds_to_a_real_template_section(self):
        for name, fixture in self.fixtures.items():
            with self.subTest(fixture=name):
                self.scenario_commands(fixture)

    def test_required_flags_present_in_the_scenario_command(self):
        for name, fixture in self.fixtures.items():
            with self.subTest(fixture=name):
                commands = self.scenario_commands(fixture)
                joined = "\n".join(commands)
                for flag in fixture["required_flags"]:
                    self.assertIn(
                        flag, joined,
                        f"[{name}] '{flag}' missing from its own template section",
                    )

    def test_forbidden_flags_absent_from_the_scenario_command(self):
        for name, fixture in self.fixtures.items():
            with self.subTest(fixture=name):
                joined = "\n".join(self.scenario_commands(fixture))
                for flag in fixture.get("forbidden_flags", []):
                    self.assertNotIn(
                        flag, joined, f"[{name}] '{flag}' must not appear in this scenario"
                    )

    def test_format_selector_matches_the_scenario(self):
        for name, fixture in self.fixtures.items():
            pattern = fixture.get("format_selector_pattern")
            if not pattern:
                continue
            with self.subTest(fixture=name):
                joined = "\n".join(self.scenario_commands(fixture))
                self.assertRegex(joined, pattern, f"[{name}] format selector mismatch")

    def test_pairing_invariants(self):
        """Skill safety rule 8: `--embed-subs` alone downloads nothing."""
        for name, fixture in self.fixtures.items():
            with self.subTest(fixture=name):
                joined = "\n".join(self.scenario_commands(fixture))
                if "--embed-subs" in joined:
                    self.assertTrue(
                        "--write-subs" in joined or "--write-auto-subs" in joined,
                        f"[{name}] --embed-subs without --write-subs downloads no subtitles",
                    )
                if "--merge-output-format" in joined:
                    self.assertRegex(
                        joined, r"-f\s", f"[{name}] --merge-output-format without -f has no merge to format"
                    )


@unittest.skipUnless(shutil.which("yt-dlp"), "yt-dlp not installed")
class TestCommandsAreWellFormed(unittest.TestCase):
    """Run every documented command through yt-dlp's own parser.

    Offline. The URL is stripped, so a well-formed command stops at the
    missing-URL error having already validated flags, arguments and the format
    expression. A malformed one reports a parser error instead.
    """

    @classmethod
    def setUpClass(cls):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
            fh.write("# Netscape HTTP Cookie File\n")
            cls.cookies_stub = fh.name

    @classmethod
    def tearDownClass(cls):
        os.unlink(cls.cookies_stub)

    def test_documented_commands_parse(self):
        commands = ec.extract_commands()
        self.assertGreaterEqual(len(commands), 20, "command corpus shrank unexpectedly")
        malformed = []
        for source, command in commands:
            verdict, detail = ec.validate(command, self.cookies_stub)
            if verdict == ec.DOC_BUG:
                malformed.append(f"{source}: {command}\n    {detail}")
        self.assertEqual([], malformed, "malformed commands:\n" + "\n".join(malformed))

    def test_the_validator_actually_rejects_a_broken_command(self):
        """Grade the grader: a check that cannot fail proves nothing."""
        for broken in (
            'yt-dlp --no-playlst -f "bv*+ba/b" "<url>"',       # typo'd flag
            'yt-dlp -f "bv*[height<=1080" "<url>"',            # unbalanced selector
            'yt-dlp --merge-output-format bogus "<url>"',      # invalid value
        ):
            with self.subTest(command=broken):
                verdict, _ = ec.validate(broken, self.cookies_stub)
                self.assertEqual(ec.DOC_BUG, verdict)

    def test_a_valid_command_is_accepted(self):
        verdict, detail = ec.validate(
            'yt-dlp --no-playlist -f "bv*+ba/b" --merge-output-format mp4 "<url>"',
            self.cookies_stub,
        )
        self.assertEqual(ec.CLEAN, verdict, detail)

    def test_environment_limits_are_not_reported_as_defects(self):
        """A missing optional dependency is not a documentation bug.

        Collapsing the two would either fail the suite on an unrelated local
        gap or hide a real malformed command behind an 'environment' excuse.
        """
        verdict, _ = ec.validate('yt-dlp --impersonate chrome "<url>"', self.cookies_stub)
        self.assertIn(verdict, (ec.CLEAN, ec.ENV_LIMIT))


if __name__ == "__main__":
    unittest.main()
