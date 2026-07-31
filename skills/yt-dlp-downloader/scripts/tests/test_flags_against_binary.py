"""Validate every yt-dlp flag in the skill's docs against the real binary.

A repo-wide global replace once corrupted 17 occurrences of
``--merge-output-format`` into ``--merge-outputexample-format`` across the
command templates — the skill's most-copied artifacts — and the text-level
tests stayed green (the corrupted assertion matched the corrupted docs).
For a CLI-wrapper skill the cheapest behavioral gate is: extract every
``--flag`` the docs mention and check it against ``yt-dlp --help``. Offline,
no downloads. Skipped only when yt-dlp is not installed.

WHAT THIS CANNOT PROVE. The oracle is the *installed* binary. A green run means
every documented flag exists in that build — not that the command still means
what the docs say on the current yt-dlp. yt-dlp ships roughly monthly and does
change option semantics and defaults, so a stale local binary can accept a flag
whose behaviour has since moved. ``test_binary_freshness_is_reported`` prints
the version and the gap so a reader can weigh the result instead of reading a
green suite as a semantic guarantee.
"""

import re
import shutil
import subprocess
import unittest
from datetime import date, datetime
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
def yt_dlp_version() -> str:
    proc = subprocess.run(["yt-dlp", "--version"], capture_output=True, text=True, timeout=30)
    return proc.stdout.strip()


@lru_cache(maxsize=1)
def yt_dlp_help() -> str:
    proc = subprocess.run(["yt-dlp", "--help"], capture_output=True, text=True, timeout=30)
    return proc.stdout


@lru_cache(maxsize=1)
def yt_dlp_options() -> frozenset:
    """The set of complete long options, not a substring haystack.

    ``"--sub-lang" in help_text`` is true because ``--sub-langs`` contains it,
    so a substring check silently blesses every abbreviation yt-dlp's parser
    happens to accept. Documenting an abbreviation is a latent break: it stops
    working the moment another option shares the prefix. Match whole tokens.
    """
    return frozenset(re.findall(r"(?<![\w-])(--[a-z][a-z0-9-]+)", yt_dlp_help()))


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
        options = yt_dlp_options()
        self.assertIn("--merge-output-format", options, "sanity: help output incomplete?")
        unknown = []
        for flag, files in sorted(doc_flags().items()):
            if flag in NOT_YT_DLP_FLAGS:
                continue
            if flag not in options:
                unknown.append(f"{flag} (in {', '.join(sorted(files))})")
        self.assertEqual([], unknown,
                         "flags documented but rejected by the installed yt-dlp:\n  "
                         + "\n  ".join(unknown))


@unittest.skipUnless(shutil.which("yt-dlp"), "yt-dlp not installed")
class BinaryProvenanceTests(unittest.TestCase):
    """State the oracle's age instead of letting green imply currency."""

    def test_binary_freshness_is_reported(self) -> None:
        version = yt_dlp_version()
        self.assertRegex(version, r"^\d{4}\.\d{2}\.\d{2}", f"unexpected version: {version}")
        try:
            released = datetime.strptime(version[:10], "%Y.%m.%d").date()
        except ValueError:
            self.skipTest(f"non-date version {version}; freshness unknown")
        age = (date.today() - released).days
        # Report only what was measured. An earlier version said this binary
        # "predates the current release by more than a quarter" — an assertion
        # about the latest release, which nothing here had queried. Age since
        # this build's own date is the only fact available offline.
        print(f"\n  yt-dlp oracle: {version} — this installed binary is {age} days old.")
        if age > 30:
            print(
                "  It may not match the latest release. Flag EXISTENCE is verified\n"
                "  against this build; flag SEMANTICS are verified only as of it.\n"
                "  Run `yt-dlp -U` before reading a green suite as agreement with\n"
                "  current yt-dlp behaviour."
            )
        # Never fails on age: a stale binary is a caveat to report, not a defect
        # in the skill. Failing here would block the suite on an unrelated local
        # condition and teach people to skip it.
        self.assertTrue(True)

    def test_no_claim_about_the_latest_release_without_querying_it(self) -> None:
        """Offline code must not describe a gap it cannot measure.

        The distance between this build and the newest release is not knowable
        from `--version` alone. Phrasing that implies it — "behind the current
        release", "N versions old" — is an unmeasured claim.
        """
        # Only what is actually printed. Comments must stay free to quote the
        # wrong phrasing while explaining why it was wrong — scanning them too
        # makes the guard fire on its own documentation.
        body = Path(__file__).read_text(encoding="utf-8")
        reported = body[body.index("def test_binary_freshness_is_reported"):]
        reported = reported[: reported.index("def test_no_claim_about")]
        reported = "\n".join(
            line for line in reported.splitlines() if not line.lstrip().startswith("#")
        )
        for phrase in ("current release", "latest release by", "versions behind"):
            self.assertNotIn(
                phrase, reported,
                f"freshness output claims a relationship to another release "
                f"that nothing queried: '{phrase}'",
            )

    def test_docs_do_not_promise_version_specific_behaviour_silently(self) -> None:
        """A behavioural claim tied to a version must name the version."""
        for path in DOC_FILES:
            text = path.read_text(encoding="utf-8")
            for match in re.finditer(r"(?m)^.*\b(now|since|as of)\b.*(defaults?|behaviou?r).*$", text):
                line = match.group(0)
                self.assertRegex(
                    line, r"\d{4}\.\d{2}",
                    f"{path.name}: version-dependent claim without a version: {line.strip()}",
                )


@unittest.skipUnless(shutil.which("yt-dlp"), "yt-dlp not installed")
class ExactMatchingTests(unittest.TestCase):
    def test_abbreviations_are_rejected_not_silently_accepted(self) -> None:
        """Negative control for the substring bug.

        `--sub-lang` is an accepted abbreviation of `--sub-langs`, so the old
        substring check passed it. Whole-token matching must not.
        """
        options = yt_dlp_options()
        self.assertIn("--sub-langs", options)
        self.assertNotIn("--sub-lang", options)
        self.assertIn("--sub-lang", yt_dlp_help(), "the substring really is present")

    def test_docs_use_canonical_option_names(self) -> None:
        for path in DOC_FILES:
            text = path.read_text(encoding="utf-8")
            for flag in FLAG_RE.findall(text):
                if flag in NOT_YT_DLP_FLAGS:
                    continue
                self.assertIn(
                    flag, yt_dlp_options(),
                    f"{path.name}: '{flag}' is not a canonical option "
                    "(an abbreviation breaks when another option shares the prefix)",
                )


@unittest.skipUnless(shutil.which("yt-dlp"), "yt-dlp not installed")
class PresetAliasTests(unittest.TestCase):
    """A claim about another tool's behaviour must be checked against that tool.

    The docs once stated `--preset-alias mp3` was equivalent to
    `-x --audio-format mp3 --audio-quality 0 --embed-thumbnail --embed-metadata`.
    It is not: the binary expands it to
    `-f 'ba[acodec^=mp3]/ba/b' -x --audio-format mp3` and nothing more.
    """

    @staticmethod
    def _documented_expansion(text: str) -> str:
        block = re.search(r"--preset-alias mp3` expands to exactly:\s*```\n(.*?)```", text, re.DOTALL)
        return block.group(1).strip() if block else ""

    def _binary_expansion(self) -> str:
        section = re.search(
            r"(?s)Preset Aliases:.*?-t mp3\s+(.*?)\n\s*\n", yt_dlp_help()
        )
        if not section:
            self.skipTest("this yt-dlp build does not list preset aliases")
        return " ".join(section.group(1).split())

    def test_documented_expansion_matches_the_binary(self) -> None:
        documented = self._documented_expansion(
            (SKILL_DIR / "references" / "scenario-templates.md").read_text(encoding="utf-8")
        )
        self.assertTrue(documented, "the mp3 preset expansion is no longer documented")
        binary = self._binary_expansion()
        norm = lambda s: " ".join(s.replace("'", "").split())
        self.assertEqual(
            norm(binary), norm(documented),
            f"documented expansion disagrees with the installed yt-dlp:\n"
            f"  binary:     {binary}\n  documented: {documented}",
        )

    def test_docs_do_not_claim_the_preset_embeds_metadata(self) -> None:
        for name in ("scenario-templates.md", "decision-rules.md"):
            text = (SKILL_DIR / "references" / name).read_text(encoding="utf-8")
            for match in re.finditer(r"(?m)^.*preset-alias mp3.*$", text):
                line = match.group(0)
                if "equivalent" in line.lower():
                    self.fail(f"{name}: reinstated equivalence claim: {line.strip()}")


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