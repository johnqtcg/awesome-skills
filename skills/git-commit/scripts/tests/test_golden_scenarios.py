import json
import re
import unittest
from pathlib import Path, PurePosixPath


SKILL_DIR = Path(__file__).resolve().parents[2]
SKILL_MD = SKILL_DIR / "SKILL.md"
GOLDEN_DIR = Path(__file__).resolve().parent / "golden"

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
    "skill_rules_that_must_fire",
    "reference_files",
}

CC_SCOPE_RE = re.compile(r"^[0-9a-f]+\s+[a-z]+(?:\(([a-z0-9_-]+)\))?!?:\s+\S")
CC_ANY_RE = re.compile(r"^[0-9a-f]+\s+[a-z]+(?:\([a-z0-9_-]+\))?!?:\s+\S")
GENERIC_DIRS = {
    "src",
    "lib",
    "pkg",
    "cmd",
    "internal",
    "app",
    "apps",
    "service",
    "services",
    "module",
    "modules",
    "package",
    "packages",
    "component",
    "components",
    "test",
    "tests",
    "testdata",
}


def load_fixture(name: str) -> dict:
    return json.loads((GOLDEN_DIR / name).read_text())


def normalize(text: str) -> str:
    text = text.lower()
    text = text.replace("→", " ")
    text = re.sub(r"[^\w\s><=.-]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def combined_text() -> str:
    return normalize(SKILL_MD.read_text())


def scoped_counts(history: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for line in history:
        match = CC_SCOPE_RE.match(line)
        if match:
            scope = match.group(1)
            counts[scope] = counts.get(scope, 0) + 1
    return counts


def conventional_commit_count(history: list[str]) -> int:
    return sum(1 for line in history if CC_ANY_RE.match(line))


def _common_prefix(paths: list[list[str]]) -> list[str]:
    if not paths:
        return []
    prefix = paths[0][:]
    for parts in paths[1:]:
        shared = []
        for left, right in zip(prefix, parts):
            if left != right:
                break
            shared.append(left)
        prefix = shared
        if not prefix:
            break
    return prefix


def infer_bootstrap_scope(staged_paths: list[str]) -> str | None:
    filtered_paths = []
    for path in staged_paths:
        dirs = [
            segment
            for segment in PurePosixPath(path).parts[:-1]
            if segment.lower() not in GENERIC_DIRS
        ]
        if dirs:
            filtered_paths.append(dirs)
    if not filtered_paths:
        return None
    prefix = _common_prefix(filtered_paths)
    if prefix:
        return prefix[-1]
    leafs = {parts[-1] for parts in filtered_paths}
    return next(iter(leafs)) if len(leafs) == 1 else None


def resolve_scope(history: list[str], staged_paths: list[str]) -> tuple[str | None, str]:
    counts = scoped_counts(history)
    canonical = sorted(
        (
            scope
            for scope, count in counts.items()
            if count >= 3
            and any(f"/{scope}/" in f"/{path}/" or path.startswith(f"{scope}/") for path in staged_paths)
        ),
        key=lambda scope: (-counts[scope], scope),
    )
    if canonical:
        return canonical[0], "canonical"
    if conventional_commit_count(history) < 10:
        scope = infer_bootstrap_scope(staged_paths)
        if scope:
            return scope, "bootstrap"
    return None, "omitted"


def render_subject(commit_type: str, scope: str | None, proposed_subject: str) -> str:
    prefix = f"{commit_type}({scope}): " if scope else f"{commit_type}: "
    return prefix + proposed_subject


def subject_is_valid(subject_line: str) -> bool:
    return len(subject_line) <= 50 and not subject_line.endswith(".")


def resolve_timeout_seconds(env: dict[str, str], makefile_timeout: str | None) -> int:
    if makefile_timeout:
        return int(makefile_timeout)
    if env.get("QUALITY_GATE_TIMEOUT_SECONDS"):
        return int(env["QUALITY_GATE_TIMEOUT_SECONDS"])
    if env.get("SKILL_QUALITY_GATE_TIMEOUT_SECONDS"):
        return int(env["SKILL_QUALITY_GATE_TIMEOUT_SECONDS"])
    if env.get("COMMIT_TEST_TIMEOUT"):
        return int(env["COMMIT_TEST_TIMEOUT"])
    return 120


class GoldenFixtureIntegrityTests(unittest.TestCase):
    def test_golden_directory_exists(self) -> None:
        self.assertTrue(GOLDEN_DIR.exists(), "golden directory missing")

    def test_expected_fixture_count(self) -> None:
        fixtures = list(GOLDEN_DIR.glob("*.json"))
        self.assertGreaterEqual(len(fixtures), 7, f"expected >=7 fixtures, got {len(fixtures)}")

    def test_required_fields(self) -> None:
        for path in sorted(GOLDEN_DIR.glob("*.json")):
            fixture = json.loads(path.read_text())
            missing = REQUIRED_FIELDS - set(fixture)
            self.assertFalse(missing, f"{path.name} missing fields: {missing}")

    def test_unique_ids(self) -> None:
        ids = [json.loads(path.read_text())["id"] for path in sorted(GOLDEN_DIR.glob("*.json"))]
        self.assertEqual(len(ids), len(set(ids)), "fixture ids must be unique")

    def test_reference_files_exist(self) -> None:
        for path in sorted(GOLDEN_DIR.glob("*.json")):
            fixture = json.loads(path.read_text())
            for ref in fixture["reference_files"]:
                self.assertTrue((SKILL_DIR / ref).exists(), f"{path.name}: missing reference {ref}")


class GoldenScenarioBehaviorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skill_text = combined_text()

    def assert_rules_covered(self, fixture: dict) -> None:
        for rule in fixture["skill_rules_that_must_fire"]:
            self.assertIn(normalize(rule), self.skill_text, f"{fixture['id']}: missing rule {rule}")

    def assert_fixture_behavior(self, fixture_name: str) -> None:
        fixture = load_fixture(fixture_name)
        scope, source = resolve_scope(fixture["history"], fixture["staged_paths"])
        self.assertEqual(fixture["expected_scope"], scope, fixture["id"])
        self.assertEqual(fixture["expected_scope_source"], source, fixture["id"])
        subject_line = render_subject(fixture["commit_type"], scope, fixture["proposed_subject"])
        self.assertEqual(fixture["expected_subject_valid"], subject_is_valid(subject_line), fixture["id"])
        timeout_seconds = resolve_timeout_seconds(
            fixture.get("env", {}),
            fixture.get("makefile_timeout"),
        )
        self.assertEqual(fixture["expected_timeout_seconds"], timeout_seconds, fixture["id"])
        self.assert_rules_covered(fixture)

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


if __name__ == "__main__":
    unittest.main()
