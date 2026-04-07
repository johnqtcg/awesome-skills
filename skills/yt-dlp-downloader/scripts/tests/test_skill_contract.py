"""Structural and content contract tests for the yt-dlp-downloader SKILL.md."""

import re
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[2]
SKILL_MD = SKILL_DIR / "SKILL.md"
DECISION_RULES = SKILL_DIR / "references" / "decision-rules.md"
SCENARIO_TEMPLATES = SKILL_DIR / "references" / "scenario-templates.md"
SAFETY_RECOVERY = SKILL_DIR / "references" / "safety-and-recovery.md"
GOLDEN_EXAMPLES = SKILL_DIR / "references" / "golden-examples.md"
FORMAT_GUIDE = SKILL_DIR / "references" / "format-selection-guide.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class TestFrontmatter(unittest.TestCase):
    def setUp(self):
        self.text = _read(SKILL_MD)

    def test_has_yaml_frontmatter(self):
        self.assertTrue(self.text.startswith("---"), "SKILL.md must start with YAML frontmatter")

    def test_has_name_field(self):
        self.assertRegex(self.text, r"(?m)^name:\s*yt-dlp-downloader")

    def test_has_description_field(self):
        self.assertRegex(self.text, r"(?m)^description:\s*\|")

    def test_description_mentions_download(self):
        m = re.search(r"description:\s*\|\n((?:\s+.*\n)+)", self.text)
        self.assertIsNotNone(m)
        desc = m.group(1).lower()
        self.assertIn("download", desc)

    def test_has_allowed_tools(self):
        self.assertRegex(self.text, r"(?m)^allowed-tools:")

    def test_allowed_tools_include_bash(self):
        m = re.search(r"allowed-tools:\s*(.+)", self.text)
        self.assertIsNotNone(m)
        self.assertIn("Bash", m.group(1))


class TestMandatoryGates(unittest.TestCase):
    def setUp(self):
        self.text = _read(SKILL_MD)

    def test_has_mandatory_gates_section(self):
        self.assertIn("## Mandatory Gates", self.text)

    def test_has_7_numbered_gates(self):
        for i in range(1, 8):
            self.assertRegex(
                self.text, rf"### {i}\)",
                f"Gate {i} not found as explicitly numbered ### {i})",
            )

    def test_gate_serial_order(self):
        positions = []
        for i in range(1, 8):
            m = re.search(rf"### {i}\)", self.text)
            self.assertIsNotNone(m, f"Gate {i} position not found")
            positions.append(m.start())
        for j in range(len(positions) - 1):
            self.assertLess(positions[j], positions[j + 1])

    def test_gate_names(self):
        expected = [
            "Scope Classification",
            "Dependency",
            "Ambiguity Resolution",
            "Probe",
            "Auth Safety",
            "Execution Mode",
            "Execution Integrity",
        ]
        for i, name in enumerate(expected, 1):
            pattern = rf"### {i}\)\s+{re.escape(name)}"
            self.assertRegex(self.text, pattern, f"Gate {i} should be named '{name}'")

    def test_ascii_flow_diagram(self):
        self.assertIn("1) Scope", self.text)
        self.assertIn("7) Execution", self.text)

    def test_scope_scenario_table(self):
        for scenario in ["Single video", "Playlist", "Audio extraction", "Live stream", "SponsorBlock"]:
            self.assertIn(scenario, self.text)

    def test_dependency_check_commands(self):
        self.assertIn("yt-dlp --version", self.text)
        self.assertIn("ffmpeg -version", self.text)

    def test_yt_dlp_ejs_mentioned(self):
        self.assertIn("yt-dlp-ejs", self.text)

    def test_probe_commands_listed(self):
        for cmd in ['yt-dlp -F', 'yt-dlp --list-subs', 'yt-dlp --simulate']:
            self.assertIn(cmd, self.text)

    def test_auth_safety_rules(self):
        self.assertIn("Never", self.text)
        self.assertRegex(self.text, r"(?i)paste cookie")
        self.assertRegex(self.text, r"(?i)bypass.*DRM|DRM.*bypass")


class TestAntiExamples(unittest.TestCase):
    def setUp(self):
        self.text = _read(SKILL_MD)

    def test_has_anti_examples_section(self):
        self.assertIn("## Anti-Examples", self.text)

    def test_minimum_anti_examples(self):
        items = re.findall(r"(?m)^\d+\.\s+\*\*", self.text)
        self.assertGreaterEqual(len(items), 8, f"Need at least 8 anti-examples, found {len(items)}")

    def test_has_bad_good_code_pairs(self):
        self.assertIn("BAD:", self.text)
        self.assertIn("GOOD:", self.text)

    def test_format_guessing_anti_example(self):
        self.assertRegex(self.text, r"(?i)guess.*format|format.*guess")

    def test_no_playlist_anti_example(self):
        self.assertIn("--no-playlist", self.text)


class TestHonestDegradation(unittest.TestCase):
    def setUp(self):
        self.text = _read(SKILL_MD)

    def test_has_degradation_section(self):
        self.assertIn("## Honest Degradation", self.text)

    def test_three_levels(self):
        for level in ["Full", "Degraded", "Blocked"]:
            self.assertIn(f"**{level}**", self.text)


class TestSafetyRules(unittest.TestCase):
    def setUp(self):
        self.text = _read(SKILL_MD)

    def test_has_safety_section(self):
        self.assertIn("## Safety Rules", self.text)

    def test_no_unauthorized_access_rule(self):
        self.assertRegex(self.text, r"(?i)never.*not authorized|never.*unauthorized|authorized.*never")

    def test_no_drm_bypass_rule(self):
        self.assertRegex(self.text, r"(?i)DRM")

    def test_execution_integrity_rule(self):
        self.assertRegex(self.text, r"(?i)never.*claim.*download.*ran|never.*claim.*ran")


class TestOutputContract(unittest.TestCase):
    def setUp(self):
        self.text = _read(SKILL_MD)

    def test_has_output_contract_section(self):
        self.assertIn("## Output Contract", self.text)

    def test_7_output_fields(self):
        for field in ["Scenario", "Inputs", "Probe", "Final command",
                       "Execution status", "Output location", "Next step"]:
            self.assertIn(f"**{field}**", self.text)


class TestDefaults(unittest.TestCase):
    def setUp(self):
        self.text = _read(SKILL_MD)

    def test_archive_default(self):
        self.assertIn("--download-archive", self.text)

    def test_continue_default(self):
        self.assertIn("--continue", self.text)

    def test_no_overwrites_default(self):
        self.assertIn("--no-overwrites", self.text)

    def test_retries_default(self):
        self.assertIn("--retries 10", self.text)


class TestReferenceFiles(unittest.TestCase):
    def test_scenario_templates_exists(self):
        self.assertTrue(SCENARIO_TEMPLATES.exists())

    def test_decision_rules_exists(self):
        self.assertTrue(DECISION_RULES.exists())

    def test_safety_recovery_exists(self):
        self.assertTrue(SAFETY_RECOVERY.exists())

    def test_golden_examples_exists(self):
        self.assertTrue(GOLDEN_EXAMPLES.exists())

    def test_format_guide_exists(self):
        self.assertTrue(FORMAT_GUIDE.exists())


class TestScenarioTemplates(unittest.TestCase):
    def setUp(self):
        self.text = _read(SCENARIO_TEMPLATES)

    def test_has_single_video_template(self):
        self.assertIn("Single Video", self.text)

    def test_has_playlist_template(self):
        self.assertIn("Playlist", self.text)

    def test_has_audio_template(self):
        self.assertIn("Audio Extraction", self.text)

    def test_has_subtitle_template(self):
        self.assertIn("Subtitles", self.text)

    def test_has_auth_template(self):
        self.assertIn("Authenticated", self.text)

    def test_has_live_stream_template(self):
        self.assertIn("Live Stream", self.text)

    def test_has_sponsorblock_template(self):
        self.assertIn("SponsorBlock", self.text)

    def test_has_preset_alias_mention(self):
        self.assertIn("--preset-alias", self.text)

    def test_has_format_sorting_example(self):
        self.assertIn("-S", self.text)


class TestDecisionRules(unittest.TestCase):
    def setUp(self):
        self.text = _read(DECISION_RULES)

    def test_format_sorting_section(self):
        self.assertIn("Format Sorting", self.text)
        self.assertIn("-S", self.text)

    def test_sponsorblock_section(self):
        self.assertIn("SponsorBlock", self.text)

    def test_live_stream_section(self):
        self.assertIn("Live Stream", self.text)

    def test_impersonation_section(self):
        self.assertIn("Impersonation", self.text)
        self.assertIn("--impersonate", self.text)


class TestSafetyRecovery(unittest.TestCase):
    def setUp(self):
        self.text = _read(SAFETY_RECOVERY)

    def test_has_403_recovery(self):
        self.assertIn("403", self.text)

    def test_has_429_recovery(self):
        self.assertIn("429", self.text)

    def test_has_format_not_available_recovery(self):
        self.assertIn("Requested format is not available", self.text)

    def test_has_ffmpeg_recovery(self):
        self.assertIn("ffmpeg not found", self.text)

    def test_has_youtube_extraction_error_recovery(self):
        self.assertIn("yt-dlp-ejs", self.text)

    def test_has_version_management(self):
        self.assertIn("Version Management", self.text)
        self.assertIn("--update-to nightly", self.text)

    def test_has_impersonation_recovery(self):
        self.assertIn("--impersonate", self.text)


class TestFormatGuide(unittest.TestCase):
    def setUp(self):
        self.text = _read(FORMAT_GUIDE)

    def test_has_format_sorting(self):
        self.assertIn("-S", self.text)
        self.assertIn("Format Sorting", self.text)

    def test_has_container_considerations(self):
        self.assertIn("Container", self.text)
        for container in ["mp4", "mkv", "webm"]:
            self.assertIn(container, self.text)

    def test_has_output_template_variables(self):
        self.assertIn("Output Template Variables", self.text)
        for var in ["%(title)s", "%(id)s", "%(ext)s", "%(playlist_title)s"]:
            self.assertIn(var, self.text)


class TestGoldenExamples(unittest.TestCase):
    def setUp(self):
        self.text = _read(GOLDEN_EXAMPLES)

    def test_has_at_least_5_examples(self):
        count = len(re.findall(r"(?m)^## \d+\)", self.text))
        self.assertGreaterEqual(count, 5)

    def test_examples_have_7_fields(self):
        for field in ["Scenario", "Inputs", "Probe", "Final command",
                       "Execution status", "Output location", "Next step"]:
            self.assertIn(field, self.text)

    def test_has_sponsorblock_example(self):
        self.assertIn("SponsorBlock", self.text)


class TestProgressiveDisclosure(unittest.TestCase):
    def setUp(self):
        self.text = _read(SKILL_MD)

    def test_has_load_references_table(self):
        self.assertIn("## Load References Selectively", self.text)

    def test_references_have_triggers(self):
        self.assertIn("## Load References Selectively", self.text)
        self.assertIn("→ Load", self.text)
        self.assertIn("references/", self.text)


class TestLineCount(unittest.TestCase):
    def test_skill_md_under_500_lines(self):
        lines = _read(SKILL_MD).count("\n") + 1
        self.assertLessEqual(lines, 500, f"SKILL.md is {lines} lines (max 500)")


if __name__ == "__main__":
    unittest.main()
