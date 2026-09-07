"""Golden scenarios for the git-commit skill, checked against REAL artifacts.

Every expectation here is produced by running a shipped script against a real
git repository built from the fixture — never by a Python re-implementation of
the same rules. An earlier version computed the expected scope with its own
copy of the §5 algorithm, so the test only ever proved that Python agreed with
Python; the rules have since moved into scripts/resolve-scope.sh, and this file
drives that script. Subject validity likewise runs the real §6 guard block
extracted from SKILL.md.
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[2]
SKILL_MD = SKILL_DIR / "SKILL.md"
SCRIPTS = SKILL_DIR / "scripts"
GOLDEN_DIR = Path(__file__).resolve().parent / "golden"
GIT = shutil.which("git")

REQUIRED_FIELDS = {
    "id",
    "description",
    "scenario_type",
    "history",
    "staged_paths",
    "commit_type",
    "proposed_subject",
    "expected_scope",
    "expected_scope_source",
    "expected_subject_valid",
    "expected_timeout_seconds",
    "reference_files",
}

_ISOLATED_ENV = {
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@t",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@t",
    # Empty counts as unset for ${VAR:-...}: shield from ambient env.
    "QUALITY_GATE_TIMEOUT_SECONDS": "",
    "SKILL_QUALITY_GATE_TIMEOUT_SECONDS": "",
    "COMMIT_TEST_TIMEOUT": "",
}


def _env(extra=None):
    env = {**os.environ, **_ISOLATED_ENV}
    if extra:
        env.update(extra)
    return env


def _commit_block() -> str | None:
    """The real §6 single-line commit block, minus its `git commit` line."""
    for block in re.findall(r"```bash\n(.*?)```", SKILL_MD.read_text(encoding="utf-8"), re.DOTALL):
        if "SUBJECT_MAX" in block and "git commit -m" in block:
            return "\n".join(l for l in block.splitlines() if not l.startswith("git commit"))
    return None


COMMIT_GUARD = _commit_block()


def load_fixture(name: str) -> dict:
    return json.loads((GOLDEN_DIR / name).read_text())


class _GoldenRepo:
    """A throwaway git repo materialising a fixture's history and staged set."""

    def __init__(self, fixture: dict):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name)
        self.git("init", "-q")
        # `git log` is newest-first, so replay the fixture list in reverse to
        # reproduce the order (and therefore the 50-commit window) it describes.
        # Subjects are used verbatim: no extra seed commit, or the fixture's own
        # conventional-commit count would be off by one at the `< 10` boundary.
        for i, line in enumerate(reversed(fixture["history"])):
            subject = line.split(" ", 1)[1]
            (self.path / f"h{i}.txt").write_text(f"{i}\n")
            self.git("add", f"h{i}.txt")
            self.git("commit", "-qm", subject)
        for rel in fixture["staged_paths"]:
            target = self.path / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("staged\n")
            self.git("add", "--", rel)

    def cleanup(self):
        self._tmp.cleanup()

    def git(self, *args):
        return subprocess.run([GIT, *args], cwd=self.path, env=_env(),
                              capture_output=True, text=True)

    def script(self, name, *args, extra_env=None):
        return subprocess.run(["bash", str(SCRIPTS / name), *args], cwd=self.path,
                              env=_env(extra_env), capture_output=True, text=True, timeout=60)

    def bash(self, snippet, extra_env=None):
        return subprocess.run(["bash", "-c", snippet], cwd=self.path,
                              env=_env(extra_env), capture_output=True, text=True, timeout=60)


class GoldenFixtureIntegrityTests(unittest.TestCase):
    def test_golden_directory_exists(self) -> None:
        self.assertTrue(GOLDEN_DIR.exists(), "golden directory missing")

    def test_expected_fixture_count(self) -> None:
        fixtures = list(GOLDEN_DIR.glob("*.json"))
        self.assertGreaterEqual(len(fixtures), 8, f"expected >=8 fixtures, got {len(fixtures)}")

    def test_required_fields(self) -> None:
        for path in sorted(GOLDEN_DIR.glob("*.json")):
            fixture = json.loads(path.read_text())
            missing = REQUIRED_FIELDS - set(fixture)
            self.assertFalse(missing, f"{path.name} missing fields: {missing}")

    def test_unique_ids(self) -> None:
        ids = [json.loads(p.read_text())["id"] for p in sorted(GOLDEN_DIR.glob("*.json"))]
        self.assertEqual(len(ids), len(set(ids)), "fixture ids must be unique")

    def test_reference_files_exist(self) -> None:
        for path in sorted(GOLDEN_DIR.glob("*.json")):
            fixture = json.loads(path.read_text())
            for ref in fixture["reference_files"]:
                self.assertTrue((SKILL_DIR / ref).exists(), f"{path.name}: missing reference {ref}")

    def test_fixtures_discriminate_scope_outcomes(self) -> None:
        """A fixture set that only ever expects one outcome cannot detect a
        regression that collapses every case to that outcome."""
        sources = {json.loads(p.read_text())["expected_scope_source"]
                   for p in GOLDEN_DIR.glob("*.json")}
        self.assertEqual({"canonical", "bootstrap", "omitted"}, sources,
                         "fixtures must cover every SCOPE_SOURCE the script can emit")

    def test_documented_scope_sources_match_the_script(self) -> None:
        """Derive the vocabulary from the script instead of hand-listing it, so
        a new SCOPE_SOURCE cannot ship undocumented."""
        script = (SCRIPTS / "resolve-scope.sh").read_text()
        emitted = set(re.findall(r'emit\([^,]+,\s*"(\w+)"\)', script))
        self.assertTrue(emitted, "could not extract SCOPE_SOURCE values from resolve-scope.sh")
        skill = SKILL_MD.read_text()
        for source in emitted:
            self.assertIn(f"`{source}`", skill,
                          f"resolve-scope.sh can emit {source!r} but SKILL.md never explains it")


@unittest.skipUnless(GIT and COMMIT_GUARD, "git or the §6 guard block unavailable")
class GoldenScenarioBehaviorTests(unittest.TestCase):
    def assert_fixture_behavior(self, fixture_name: str) -> None:
        fixture = load_fixture(fixture_name)
        repo = _GoldenRepo(fixture)
        self.addCleanup(repo.cleanup)
        fid = fixture["id"]

        # --- scope: the real resolver against a real repo ---
        out = repo.script("resolve-scope.sh")
        self.assertEqual(0, out.returncode, f"{fid}: resolve-scope failed: {out.stderr}")
        scope = re.search(r"^SCOPE: (.+)$", out.stdout, re.MULTILINE).group(1)
        source = re.search(r"^SCOPE_SOURCE: (.+)$", out.stdout, re.MULTILINE).group(1)
        expected_scope = fixture["expected_scope"] or "(none)"
        self.assertEqual(expected_scope, scope, f"{fid}: scope")
        self.assertEqual(fixture["expected_scope_source"], source, f"{fid}: scope source")

        # --- subject: the real §6 guard, not a Python len() check ---
        prefix = (f"{fixture['commit_type']}({scope}): " if source != "omitted"
                  else f"{fixture['commit_type']}: ")
        subject = prefix + fixture["proposed_subject"]
        guard = re.sub(r"^SUBJECT='.*'$", f"SUBJECT='{subject}'",
                       COMMIT_GUARD, count=1, flags=re.MULTILINE)
        guard_run = repo.bash(guard)
        self.assertEqual(fixture["expected_subject_valid"], guard_run.returncode == 0,
                         f"{fid}: guard verdict for {subject!r}: {guard_run.stdout}")

        # --- timeout: the real enforcer reports the timeout it would apply ---
        args = ["-t", str(fixture["makefile_timeout"])] if fixture.get("makefile_timeout") else []
        gate = repo.script("run-gate.sh", *args, "true", extra_env=fixture.get("env", {}))
        reported = re.search(r"GATE_TIMEOUT: (\d+)s", gate.stderr)
        self.assertIsNotNone(reported, f"{fid}: run-gate.sh reported no timeout: {gate.stderr!r}")
        self.assertEqual(fixture["expected_timeout_seconds"], int(reported.group(1)), f"{fid}: timeout")

    def test_001_canonical_scope_from_history(self) -> None:
        self.assert_fixture_behavior("001_canonical_scope_from_history.json")

    def test_002_bootstrap_scope_for_new_repo(self) -> None:
        self.assert_fixture_behavior("002_bootstrap_scope_for_new_repo.json")

    def test_003_mixed_roots_omit_scope(self) -> None:
        self.assert_fixture_behavior("003_mixed_roots_omit_scope.json")

    def test_004_subject_guard_blocks_long_line(self) -> None:
        self.assert_fixture_behavior("004_subject_guard_blocks_long_line.json")

    def test_005_env_timeout_override(self) -> None:
        self.assert_fixture_behavior("005_env_timeout_override.json")

    def test_006_makefile_timeout_override(self) -> None:
        self.assert_fixture_behavior("006_makefile_timeout_override.json")

    def test_007_mature_repo_without_match_omits_scope(self) -> None:
        self.assert_fixture_behavior("007_mature_repo_without_match_omits_scope.json")

    def test_008_two_canonical_scopes_omit_rather_than_mislabel(self) -> None:
        self.assert_fixture_behavior("008_two_canonical_scopes_omit_scope.json")


if __name__ == "__main__":
    unittest.main()
