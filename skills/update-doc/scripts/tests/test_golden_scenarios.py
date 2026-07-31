"""Behavioral golden tests for `scripts/discover_doc_scope.sh`.

Each fixture under `golden/` describes a repository shape. The test materializes
that shape as a real git repository, runs the real discovery script against it,
and asserts the parsed report.

This is deliberately not a string-presence test of SKILL.md. A fixture failing
here means the skill would start from the wrong scope, pick the wrong command
source, or route to the wrong document structure on that repository shape.
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[2]
SCRIPT = SKILL_DIR / "scripts" / "discover_doc_scope.sh"
GOLDEN_DIR = Path(__file__).resolve().parent / "golden"

GIT = shutil.which("git")


def parse_report(text):
    """Parse the discovery report into {section: {key: value}, ...} plus lists.

    The report format is a fixed contract; parsing it here means a silent format
    change breaks the tests instead of being absorbed.
    """
    sections = {}
    listings = {}
    current = None
    for raw in text.splitlines():
        if raw.startswith("=== SECTION: "):
            current = raw[len("=== SECTION: "):].rstrip(" =").strip()
            sections[current] = {}
            listings[current] = []
            continue
        if raw.startswith("=== END ==="):
            current = None
            continue
        if current is None:
            continue
        if raw.startswith("  "):
            listings[current].append(raw.strip())
        elif ":" in raw:
            key, _, value = raw.partition(":")
            sections[current][key.strip()] = value.strip()
    return sections, listings


def write_files(root, mapping, append=False):
    for rel, content in (mapping or {}).items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if append else "w"
        with open(path, mode, encoding="utf-8") as handle:
            handle.write(content)


def git(root, *args):
    subprocess.run(
        [GIT, *args],
        cwd=root,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def build_repo(root, spec):
    """Materialize a fixture into a real directory (git repo when spec['git'])."""
    if not spec.get("git", True):
        write_files(root, spec.get("base_commit"))
        return None

    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "test@example.com")
    git(root, "config", "user.name", "test")
    git(root, "config", "commit.gpgsign", "false")

    write_files(root, spec.get("base_commit"))
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "base")

    if spec.get("branch_commit"):
        git(root, "checkout", "-q", "-b", "feature")
        write_files(root, spec["branch_commit"])
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", "branch")

    if spec.get("staged"):
        write_files(root, spec["staged"])
        for rel in spec["staged"]:
            git(root, "add", rel)

    # Worktree edits are appended after staging so they stay unstaged.
    write_files(root, spec.get("worktree_edit"), append=True)
    write_files(root, spec.get("untracked"))
    return "main"


def load_fixtures():
    return sorted(GOLDEN_DIR.glob("*.json"))


@unittest.skipIf(GIT is None, "git not available")
class GoldenScenarioTests(unittest.TestCase):
    maxDiff = None

    def run_fixture(self, path):
        spec = json.loads(path.read_text(encoding="utf-8"))
        expect = spec["expect"]

        with tempfile.TemporaryDirectory(
            dir=os.environ.get("TMPDIR") or None
        ) as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            base = build_repo(root, spec)

            cmd = ["bash", str(SCRIPT), "--repo", str(root)]
            if base:
                cmd += ["--base", base]
            proc = subprocess.run(cmd, capture_output=True, text=True)

        # A truncated report is the failure mode this sentinel exists to catch:
        # a non-zero exit alone would not distinguish "died midway" from
        # "reported an empty repository".
        self.assertEqual(
            proc.returncode, 0, f"{spec['id']}: exit {proc.returncode}\n{proc.stderr}"
        )
        self.assertTrue(
            proc.stdout.rstrip().endswith("=== END ==="),
            f"{spec['id']}: report truncated, no END sentinel",
        )

        sections, listings = parse_report(proc.stdout)
        ctx = spec["id"]

        self.assertEqual(sections["repo"]["STATUS"], expect["status"], f"{ctx}: STATUS")
        self.assertEqual(
            sections["language"]["DOMINANT"], expect["dominant"], f"{ctx}: DOMINANT"
        )
        self.assertEqual(
            sections["language"]["POLYGLOT"], expect["polyglot"], f"{ctx}: POLYGLOT"
        )
        self.assertEqual(
            sections["command_sources"]["PRIMARY"], expect["primary"], f"{ctx}: PRIMARY"
        )
        self.assertEqual(
            sections["project_type"]["LIKELY"], expect["likely"], f"{ctx}: LIKELY"
        )
        self.assertEqual(
            sections["docs"]["CODEMAPS"], expect["codemaps"], f"{ctx}: CODEMAPS"
        )
        self.assertEqual(sections["ci"]["DOC_CI"], expect["doc_ci"], f"{ctx}: DOC_CI")

        diff = sections["diff_scope"]
        for label, want in expect["sources"].items():
            self.assertEqual(
                int(diff[f"SOURCE {label}"]), want, f"{ctx}: SOURCE {label}"
            )
        self.assertEqual(
            int(diff["TOTAL_UNIQUE"]), expect["total_unique"], f"{ctx}: TOTAL_UNIQUE"
        )
        self.assertEqual(
            int(diff["NEW_SOURCE"]), expect["new_source"], f"{ctx}: NEW_SOURCE"
        )

        scope_lines = set(listings["diff_scope"])
        for wanted in expect["scope_contains"]:
            self.assertIn(wanted, scope_lines, f"{ctx}: {wanted} missing from scope")

        # `resolved` and `modules` are declared only by the fixtures that exist
        # to exercise them; TestCommandLevelResolutionIsCovered below keeps that
        # from silently becoming zero fixtures.
        for key, want in expect.get("resolved", {}).items():
            self.assertIn(
                f"{key}: {want}", listings["command_sources"],
                f"{ctx}: RESOLVED {key} should be '{want}', got "
                f"{[l for l in listings['command_sources'] if l.startswith(key + ':')]}",
            )
        # MODULES is per-module AND per-command: each module header is followed
        # by its own resolved kinds. A module reported as a single source would
        # repeat the repo-level PRIMARY mistake one level down.
        for module, wanted_lines in expect.get("modules", {}).items():
            self.assertIn(
                f"{module}:", listings["command_sources"], f"{ctx}: module {module} missing"
            )
            for line in wanted_lines:
                self.assertIn(
                    line, listings["command_sources"],
                    f"{ctx}: MODULES {module} should report '{line}'",
                )

    def test_all_fixtures(self):
        fixtures = load_fixtures()
        self.assertGreaterEqual(len(fixtures), 11, "golden corpus shrank")
        for path in fixtures:
            with self.subTest(fixture=path.name):
                self.run_fixture(path)

    def test_add_and_modify_twins_differ_only_in_new_source(self):
        """Guard the guard for NEW_SOURCE.

        010 and 011 must stay indistinguishable on every path-count field, so
        that NEW_SOURCE is the only thing that can separate them. If they drift
        apart on TOTAL_UNIQUE or the source counts, the pair stops proving that
        add-vs-modify discrimination works.
        """
        modify = json.loads(
            (GOLDEN_DIR / "010_base_range_modify_only.json").read_text(encoding="utf-8")
        )["expect"]
        add = json.loads(
            (GOLDEN_DIR / "011_base_range_adds_file.json").read_text(encoding="utf-8")
        )["expect"]

        self.assertEqual(modify["sources"], add["sources"], "twins must share source counts")
        self.assertEqual(
            modify["total_unique"], add["total_unique"], "twins must share TOTAL_UNIQUE"
        )
        self.assertEqual(modify["new_source"], 0)
        self.assertEqual(add["new_source"], 1)

    def test_command_level_resolution_is_covered(self):
        """`resolved`/`modules` are optional per fixture, so guard the coverage.

        Also asserts the mixed-source fixture really is mixed: if every kind
        resolved to the same source it would not distinguish command-level
        resolution from the old repo-level PRIMARY.
        """
        declaring = [
            p for p in load_fixtures()
            if json.loads(p.read_text(encoding="utf-8"))["expect"].get("resolved")
        ]
        self.assertGreaterEqual(len(declaring), 2, "command-level coverage shrank")

        mixed = json.loads(
            (GOLDEN_DIR / "012_mixed_command_sources.json").read_text(encoding="utf-8")
        )["expect"]
        self.assertEqual(mixed["primary"], "makefile")
        sources = {v.split(" ")[0] for v in mixed["resolved"].values()}
        self.assertGreaterEqual(
            len(sources), 2, "fixture must resolve kinds to different sources"
        )
        self.assertNotEqual(
            mixed["resolved"]["build"].split(" ")[0], mixed["primary"],
            "build must resolve away from PRIMARY or the fixture proves nothing",
        )

    def test_untracked_language_fixture_actually_flips_the_verdict(self):
        """009 only proves something if the tracked files are a *different*
        language from the untracked ones."""
        spec = json.loads(
            (GOLDEN_DIR / "009_untracked_new_language.json").read_text(encoding="utf-8")
        )
        tracked_ext = {p.rsplit(".", 1)[-1] for p in spec["base_commit"] if "." in p}
        untracked_ext = {p.rsplit(".", 1)[-1] for p in spec["untracked"] if "." in p}
        self.assertIn("go", tracked_ext)
        self.assertEqual(untracked_ext, {"py"})
        self.assertEqual(spec["expect"]["dominant"], "python")
        self.assertEqual(spec["expect"]["polyglot"], "yes")

    def test_bare_git_diff_would_miss_staged_and_untracked_fixtures(self):
        """The two regression fixtures must actually be invisible to `git diff`.

        Without this the fixtures could silently stop exercising the defect they
        were written for — for example if a future edit added a worktree change
        to them — and still pass.
        """
        for name in ("005_staged_only_change.json", "006_untracked_new_module.json"):
            spec = json.loads((GOLDEN_DIR / name).read_text(encoding="utf-8"))
            self.assertEqual(
                spec["expect"]["sources"]["worktree"],
                0,
                f"{name}: must have an empty working tree to prove the defect",
            )
            self.assertGreater(
                spec["expect"]["total_unique"],
                0,
                f"{name}: must still discover changes despite the empty working tree",
            )


if __name__ == "__main__":
    unittest.main()
