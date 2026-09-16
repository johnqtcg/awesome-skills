"""Golden scenarios: each fixture asserts something about the SKILL, not itself.

What this file used to be, and why it changed. Half of its tests looked like:

    def test_001_expects_full_parity(self):
        data = load_fixture("001_single_module_service.json")
        self.assertEqual(data["expected_parity_level"], "full")

That reads the fixture and asserts the fixture's own value. It touches no skill
artifact and cannot fail unless someone edits the fixture — a tautology that
inflated the test count without adding a single bit of discrimination. The
other half searched for each rule in the concatenation of SKILL.md plus EVERY
reference, so `"30 min"` was satisfied by one unrelated cell in a timeout table.

Every assertion here now binds a fixture field to the skill text that must
honour it:

* declared shapes, gates, execution paths and output fields must exist in the
  SKILL.md section that owns them (not merely somewhere in the file);
* `skill_rules_that_must_fire` is searched only in SKILL.md plus the references
  that SKILL.md's "Load References Selectively" rules would actually open for
  that scenario (`load_references`). A rule that only exists in a file the
  skill would not read for this scenario is not covered — it is a gap, and the
  scoping is what makes that visible.
"""

import json
import re
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[2]
SKILL_MD = SKILL_DIR / "SKILL.md"
REF_DIR = SKILL_DIR / "references"
GOLDEN_DIR = SKILL_DIR / "scripts" / "tests" / "golden"

ALWAYS_LOADED = ("workflow-quality-guide.md", "golden-examples.md")

REQUIRED_FIELDS = {
    "id", "description", "scenario_type", "expected_gates",
    "skill_rules_that_must_fire", "load_references",
}
EXECUTION_PATHS = {"make target", "repo task", "inline fallback"}


def fixtures() -> list[tuple[str, dict]]:
    return [(p.name, json.loads(p.read_text()))
            for p in sorted(GOLDEN_DIR.glob("*.json"))]


def section(text: str, heading_re: str) -> str:
    """The body of the first heading matching `heading_re`, up to the next
    heading of the same or higher level. Assertions scoped to a section cannot
    be satisfied by an unrelated paragraph elsewhere in the file."""
    m = re.search(heading_re, text, re.MULTILINE)
    if not m:
        return ""
    level = len(re.match(r"#+", m.group(0)).group(0))
    rest = text[m.end():]
    nxt = re.search(r"^#{1," + str(level) + r"}\s", rest, re.MULTILINE)
    return rest[:nxt.start()] if nxt else rest


def scoped_corpus(data: dict) -> str:
    """SKILL.md + exactly the references this scenario would cause to load."""
    parts = [SKILL_MD.read_text()]
    for name in list(ALWAYS_LOADED) + list(data["load_references"]):
        parts.append((REF_DIR / name).read_text())
    return "\n".join(parts)


class FixtureIntegrityTests(unittest.TestCase):
    def test_expected_fixture_count(self) -> None:
        self.assertGreaterEqual(len(fixtures()), 12,
                                f"expected >=12 fixtures, got {len(fixtures())}")

    def test_all_fixtures_have_required_fields(self) -> None:
        for name, data in fixtures():
            missing = REQUIRED_FIELDS - set(data)
            self.assertFalse(missing, f"{name} missing fields: {missing}")

    def test_scenario_types_cover_all_shapes(self) -> None:
        types = {d["scenario_type"] for _, d in fixtures()}
        expected = {
            "single_module_service", "single_module_library", "multi_module",
            "monorepo", "docker_heavy", "no_makefile", "fork_pr_security",
            "service_containers",
        }
        self.assertTrue(expected.issubset(types), f"missing scenario types: {expected - types}")

    def test_load_references_name_real_files(self) -> None:
        """A fixture cannot scope itself to a reference that does not exist, or
        to one SKILL.md never tells the agent to load."""
        skill_text = SKILL_MD.read_text()
        for name, data in fixtures():
            for ref in data["load_references"]:
                self.assertTrue((REF_DIR / ref).exists(), f"{name}: no such reference {ref}")
                self.assertIn(ref, skill_text,
                              f"{name}: SKILL.md never instructs loading {ref}")


class FixtureBindsToSkillTests(unittest.TestCase):
    """Each fixture field must be grounded in the SKILL.md section that owns it."""

    @classmethod
    def setUpClass(cls) -> None:
        text = SKILL_MD.read_text()
        cls.shape_gate = section(text, r"^#{2,4}.*Repository Shape Gate\s*$")
        cls.parity_gate = section(text, r"^#{2,4}.*Local Parity Gate\s*$")
        cls.output_contract = section(text, r"^#{2,3}\s*Output Contract\s*$")
        cls.gate_headings = set(
            re.findall(r"^#{2,4}(?:\s*\d+\))?\s*(.*?Gate)\s*$", text, re.MULTILINE)
        )
        cls.skill_text = text

    def test_expected_shapes_are_declared_by_the_shape_gate(self) -> None:
        self.assertTrue(self.shape_gate, "Repository Shape Gate section not found")
        for name, data in fixtures():
            shape = data.get("expected_shape")
            if shape is None:
                continue
            self.assertIn(shape, self.shape_gate,
                          f"{name}: expected_shape {shape!r} is not one the "
                          "Repository Shape Gate can produce")

    def test_expected_gates_are_real_gates(self) -> None:
        self.assertEqual(5, len(self.gate_headings), f"gates parsed: {self.gate_headings}")
        for name, data in fixtures():
            for gate in data["expected_gates"]:
                self.assertIn(gate, self.gate_headings,
                              f"{name}: {gate!r} is not a mandatory gate in SKILL.md")

    def test_execution_paths_are_the_three_declared_ones(self) -> None:
        for path in EXECUTION_PATHS:
            self.assertIn(f"`{path}`", self.parity_gate,
                          f"Local Parity Gate no longer declares {path!r}")
        for name, data in fixtures():
            for job, path in (data.get("expected_execution_paths") or {}).items():
                self.assertIn(path, EXECUTION_PATHS,
                              f"{name}: job {job} uses undeclared execution path {path!r}")

    def test_expected_output_fields_are_in_the_output_contract(self) -> None:
        self.assertTrue(self.output_contract, "Output Contract section not found")
        for name, data in fixtures():
            for field in data.get("expected_output_fields") or []:
                self.assertIn(field, self.output_contract,
                              f"{name}: {field!r} is not promised by the Output Contract")

    def test_parity_levels_are_grounded_in_the_fallback_ladder(self) -> None:
        """`full` / `partial` / `scaffold` are the Level A/B/C ladder in
        fallback-and-scaffolding.md — not free-text fixture labels."""
        ladder = (REF_DIR / "fallback-and-scaffolding.md").read_text()
        wanted = {"full": "Level A", "partial": "Level B", "scaffold": "Level C"}
        for label, level in wanted.items():
            self.assertIn(level, ladder, f"fallback ladder no longer defines {level}")
        for name, data in fixtures():
            level = data.get("expected_parity_level")
            if level is not None:
                self.assertIn(level, wanted,
                              f"{name}: parity level {level!r} is not on the A/B/C ladder")


class ScopedRuleCoverageTests(unittest.TestCase):
    """Each rule must be reachable from what the skill would actually load."""

    def test_every_rule_is_in_the_scenario_scoped_corpus(self) -> None:
        for name, data in fixtures():
            corpus = scoped_corpus(data)
            for rule in data["skill_rules_that_must_fire"]:
                self.assertIn(
                    rule, corpus,
                    f"{name}: rule {rule!r} is not in SKILL.md or any reference "
                    f"this scenario loads ({data['load_references']})",
                )

    def test_conditional_rules_are_not_all_satisfied_by_skill_md_alone(self) -> None:
        """A scenario that declares conditional references must depend on them.
        If every rule is already in SKILL.md, the fixture is testing nothing
        about the reference it claims to need."""
        skill_only = SKILL_MD.read_text()
        for name, data in fixtures():
            if not data["load_references"]:
                continue
            needs_ref = [r for r in data["skill_rules_that_must_fire"]
                         if r not in skill_only]
            self.assertTrue(
                needs_ref,
                f"{name}: declares {data['load_references']} but every rule is "
                "already satisfied by SKILL.md — the reference is untested here",
            )

    def test_rules_are_specific_enough_to_discriminate(self) -> None:
        """Guard against a future fixture 'passing' on a two-letter token."""
        for name, data in fixtures():
            for rule in data["skill_rules_that_must_fire"]:
                self.assertGreaterEqual(
                    len(rule), 4, f"{name}: rule {rule!r} is too short to be evidence")


if __name__ == "__main__":
    unittest.main()
