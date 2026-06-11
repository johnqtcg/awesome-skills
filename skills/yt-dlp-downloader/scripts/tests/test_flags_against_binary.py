"""Validate every yt-dlp flag in the skill's docs against the real binary.

A repo-wide global replace once corrupted 17 occurrences of
``--merge-output-format`` into ``--merge-outputexample-format`` across the
command templates — the skill's most-copied artifacts — and the text-level
tests stayed green (the corrupted assertion matched the corrupted docs).
For a CLI-wrapper skill the cheapest behavioral gate is: extract every
``--flag`` the docs mention and check it against ``yt-dlp --help``. Offline,
no downloads. Skipped only when yt-dlp is not installed.
"""

import re
import shutil
import subprocess
import unittest
from functools import lru_cache
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[2]
DOC_FILES = [SKILL_DIR / "SKILL.md", *sorted((SKILL_DIR / "references").glob("*.md"))]

FLAG_RE = re.compile(r"(?<![\w-])--[a-z][a-z0-9-]+")

# Flags documented for other tools or as deliberate placeholders, not yt-dlp
# options. Keep this list short and justified. Currently empty: every flag
# the docs mention is a real yt-dlp option.
NOT_YT_DLP_FLAGS: set[str] = set()


@lru_cache(maxsize=1)
def yt_dlp_help() -> str:
    proc = subprocess.run(["yt-dlp", "--help"], capture_output=True, text=True, timeout=30)
    return proc.stdout


def doc_flags() -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for path in DOC_FILES:
        text = path.read_text(encoding="utf-8")
        # Strip diagram/prose lines that are not command examples? No — flags
        # only appear in command contexts in this skill; scan everything.
        for flag in FLAG_RE.findall(text):
            found.setdefault(flag, set()).add(path.name)
    return found


@unittest.skipUnless(shutil.which("yt-dlp"), "yt-dlp not installed")
class FlagsAgainstBinaryTests(unittest.TestCase):
    def test_every_documented_flag_is_accepted_by_yt_dlp(self) -> None:
        help_text = yt_dlp_help()
        self.assertIn("--merge-output-format", help_text, "sanity: help output incomplete?")
        unknown = []
        for flag, files in sorted(doc_flags().items()):
            if flag in NOT_YT_DLP_FLAGS:
                continue
            if flag not in help_text:
                unknown.append(f"{flag} (in {', '.join(sorted(files))})")
        self.assertEqual([], unknown,
                         "flags documented but rejected by the installed yt-dlp:\n  "
                         + "\n  ".join(unknown))


class CorruptionGuardTests(unittest.TestCase):
    def test_global_replace_artifact_absent(self) -> None:
        """Lock the output→outputexample sed accident out of this skill."""
        for path in DOC_FILES:
            self.assertNotIn("outputexample", path.read_text(encoding="utf-8"),
                             f"{path.name}: global-replace artifact present")

    def test_merge_output_format_present_in_templates(self) -> None:
        templates = (SKILL_DIR / "references" / "scenario-templates.md").read_text(encoding="utf-8")
        self.assertIn("--merge-output-format mp4", templates)


if __name__ == "__main__":
    unittest.main()