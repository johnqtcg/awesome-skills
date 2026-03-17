"""
Golden scenario tests for tech-doc-writer skill.

Each fixture in golden/ defines a user scenario and the keywords that
SKILL.md + references must contain to handle it. Tests are zero-LLM:
they verify the skill text covers the required rules, not that an LLM
produces a correct document.

Run: python3 -m unittest scripts/tests/test_golden_scenarios.py -v
"""

import json
import os
import unittest

SKILL_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
SKILL_MD = os.path.join(SKILL_DIR, "SKILL.md")
REFS_DIR = os.path.join(SKILL_DIR, "references")
GOLDEN_DIR = os.path.join(os.path.dirname(__file__), "golden")


def _read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _load_fixtures():
    fixtures = []
    if not os.path.isdir(GOLDEN_DIR):
        return fixtures
    for name in sorted(os.listdir(GOLDEN_DIR)):
        if name.endswith(".json"):
            path = os.path.join(GOLDEN_DIR, name)
            with open(path, "r", encoding="utf-8") as f:
                fixtures.append((name, json.load(f)))
    return fixtures


_SKILL_CONTENT = _read(SKILL_MD)
_REF_CONTENTS = {}
for fname in os.listdir(REFS_DIR):
    if fname.endswith(".md"):
        _REF_CONTENTS[fname] = _read(os.path.join(REFS_DIR, fname))
_ALL_TEXT = _SKILL_CONTENT + "\n".join(_REF_CONTENTS.values())


class TestGoldenFixtureIntegrity(unittest.TestCase):
    """Verify the golden fixtures themselves are well-formed."""

    def test_minimum_fixture_count(self):
        fixtures = _load_fixtures()
        self.assertGreaterEqual(
            len(fixtures), 6,
            f"Need ≥6 golden fixtures, found {len(fixtures)}"
        )

    def test_fixtures_have_required_fields(self):
        required = {"id", "title", "user_request", "expected_mode", "skill_must_contain"}
        for name, fixture in _load_fixtures():
            for field in required:
                self.assertIn(
                    field, fixture,
                    f"{name} missing required field: {field}"
                )

    def test_fixture_ids_unique(self):
        ids = [f["id"] for _, f in _load_fixtures()]
        self.assertEqual(len(ids), len(set(ids)), "Duplicate fixture IDs")


class TestGoldenScenarioCoverage(unittest.TestCase):
    """For each fixture, verify SKILL.md + references contain all required keywords."""

    pass


def _make_keyword_test(fixture_name, fixture_data):
    def test_method(self):
        missing = []
        for keyword in fixture_data["skill_must_contain"]:
            if keyword not in _ALL_TEXT:
                missing.append(keyword)
        self.assertEqual(
            missing, [],
            f"Fixture {fixture_data['id']} ({fixture_data['title']}): "
            f"keywords not found in skill text: {missing}"
        )
    test_method.__doc__ = f"{fixture_data['id']}: {fixture_data['title']}"
    return test_method


def _make_gate_test(fixture_name, fixture_data):
    def test_method(self):
        if "gates_required" not in fixture_data:
            return
        missing = []
        for gate in fixture_data["gates_required"]:
            if gate not in _SKILL_CONTENT:
                missing.append(gate)
        self.assertEqual(
            missing, [],
            f"Fixture {fixture_data['id']}: gates not found in SKILL.md: {missing}"
        )
    test_method.__doc__ = f"{fixture_data['id']}: gates present"
    return test_method


def _make_reference_test(fixture_name, fixture_data):
    def test_method(self):
        ref = fixture_data.get("reference_to_load")
        if not ref:
            return
        self.assertIn(
            ref, _SKILL_CONTENT,
            f"Fixture {fixture_data['id']}: reference '{ref}' not mentioned in SKILL.md"
        )
        self.assertIn(
            ref, _REF_CONTENTS,
            f"Fixture {fixture_data['id']}: reference file '{ref}' does not exist"
        )
        section = fixture_data.get("reference_section")
        if section:
            self.assertIn(
                section, _REF_CONTENTS[ref],
                f"Fixture {fixture_data['id']}: section '{section}' not found in {ref}"
            )
    test_method.__doc__ = f"{fixture_data['id']}: reference loadable"
    return test_method


def _make_mode_test(fixture_name, fixture_data):
    def test_method(self):
        mode = fixture_data.get("expected_mode")
        if not mode:
            return
        self.assertIn(
            mode, _SKILL_CONTENT,
            f"Fixture {fixture_data['id']}: mode '{mode}' not found in SKILL.md"
        )
    test_method.__doc__ = f"{fixture_data['id']}: mode exists"
    return test_method


for _fname, _fdata in _load_fixtures():
    _base = _fname.replace(".json", "")
    setattr(
        TestGoldenScenarioCoverage,
        f"test_{_base}_keywords",
        _make_keyword_test(_fname, _fdata),
    )
    setattr(
        TestGoldenScenarioCoverage,
        f"test_{_base}_gates",
        _make_gate_test(_fname, _fdata),
    )
    setattr(
        TestGoldenScenarioCoverage,
        f"test_{_base}_reference",
        _make_reference_test(_fname, _fdata),
    )
    setattr(
        TestGoldenScenarioCoverage,
        f"test_{_base}_mode",
        _make_mode_test(_fname, _fdata),
    )


if __name__ == "__main__":
    unittest.main()
