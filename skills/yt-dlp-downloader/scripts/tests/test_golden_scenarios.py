"""Golden scenario tests for keyword coverage in the yt-dlp-downloader skill."""

import json
import re
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent.parent
SKILL_MD = SKILL_ROOT / "SKILL.md"
GOLDEN_DIR = Path(__file__).resolve().parent / "golden"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _all_skill_text() -> str:
    parts = [_read(SKILL_MD)]
    ref_dir = SKILL_ROOT / "references"
    if ref_dir.is_dir():
        for f in ref_dir.iterdir():
            if f.suffix == ".md":
                parts.append(_read(f))
    return "\n".join(parts)


class TestGoldenFromFixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.all_text = _all_skill_text()
        cls.fixtures = {}
        if GOLDEN_DIR.is_dir():
            for f in sorted(GOLDEN_DIR.glob("*.json")):
                cls.fixtures[f.stem] = json.loads(f.read_text())

    def _check_fixture(self, name: str):
        fixture = self.fixtures.get(name)
        if not fixture:
            self.skipTest(f"golden/{name}.json not found")
        for kw in fixture.get("required_keywords", []):
            if kw.startswith("re:"):
                self.assertRegex(self.all_text, kw[3:], f"[{name}] regex not found: {kw[3:]}")
            else:
                self.assertIn(kw, self.all_text, f"[{name}] keyword not found: {kw}")


def _make_fixture_test(name):
    def test_method(self):
        self._check_fixture(name)
    test_method.__doc__ = f"Golden scenario: {name}"
    return test_method


_FIXTURES = [
    "single_video",
    "playlist_download",
    "audio_extraction",
    "subtitle_download",
    "authenticated_download",
    "live_stream",
    "sponsorblock",
    "format_selection",
]

for _name in _FIXTURES:
    setattr(TestGoldenFromFixtures, f"test_{_name}", _make_fixture_test(_name))


class TestCommonScenarios(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = _read(SKILL_MD)
        cls.all_text = _all_skill_text()

    def test_no_playlist_flag(self):
        self.assertIn("--no-playlist", self.skill)

    def test_yes_playlist_flag(self):
        self.assertIn("--yes-playlist", self.all_text)

    def test_download_archive(self):
        self.assertIn("--download-archive", self.skill)

    def test_merge_output_format(self):
        self.assertIn("--merge-outputexample-format", self.all_text)

    def test_cookies_from_browser(self):
        self.assertIn("--cookies-from-browser", self.all_text)

    def test_format_list_probe(self):
        self.assertIn("yt-dlp -F", self.skill)

    def test_list_subs_probe(self):
        self.assertIn("--list-subs", self.skill)

    def test_concurrent_fragments(self):
        self.assertIn("--concurrent-fragments", self.all_text)

    def test_restrict_filenames(self):
        self.assertIn("--restrict-filenames", self.all_text)

    def test_embed_subs(self):
        self.assertIn("--embed-subs", self.all_text)

    def test_embed_metadata(self):
        self.assertIn("--embed-metadata", self.all_text)

    def test_embed_thumbnail(self):
        self.assertIn("--embed-thumbnail", self.all_text)

    def test_audio_format_mp3(self):
        self.assertIn("--audio-format mp3", self.all_text)

    def test_impersonate_flag(self):
        self.assertIn("--impersonate", self.all_text)

    def test_live_from_start(self):
        self.assertIn("--live-from-start", self.all_text)

    def test_sponsorblock_remove(self):
        self.assertIn("--sponsorblock-remove", self.all_text)

    def test_format_sorting_flag(self):
        self.assertIn("-S", self.all_text)

    def test_preset_alias(self):
        self.assertIn("--preset-alias", self.all_text)

    def test_update_to_nightly(self):
        self.assertIn("--update-to nightly", self.all_text)

    def test_proxy_flag(self):
        self.assertIn("--proxy", self.all_text)

    def test_sleep_requests(self):
        self.assertIn("--sleep-requests", self.all_text)

    def test_output_template_truncation(self):
        self.assertIn("%(title).200s", self.all_text)

    def test_ffmpeg_dependency(self):
        self.assertIn("ffmpeg", self.skill)

    def test_yt_dlp_ejs_dependency(self):
        self.assertIn("yt-dlp-ejs", self.all_text)


if __name__ == "__main__":
    unittest.main()
