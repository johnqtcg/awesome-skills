"""Keep the rationale → skill → evaluate chain describing the same skill.

Why this layer exists: a skill whose headline feature is anti-staleness shipped companion docs
that had themselves gone stale. `rationale/design.md` still explained a "Level 2.5: Active
Retrieval" degradation step that had been replaced by the R1/R2/R3 Resolution Order, and both
evaluation reports still described the Quality Scorecard as "Gate 4" — a gate number that no
longer exists — alongside a SKILL.md line count and a weighted score from an older revision.
Every layer passed its own tests. Nothing compared them to each other.

The rule is not "never mention a retired construct": an honest rationale doc explains what
changed and why, and an evaluation report is a dated snapshot. The rule is that a mention must
be **marked** — as history, or as a snapshot with its date — rather than presented as current.

These tests are skipped when the companion layers are absent, so an installed copy of the skill
alone does not fail them.
"""

import re
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = SKILL_DIR.parents[1]
SKILL_NAME = SKILL_DIR.name

RATIONALE = REPO_ROOT / "rationale" / SKILL_NAME
EVALUATE = REPO_ROOT / "evaluate"
EVAL_REPORTS = [
    EVALUATE / f"{SKILL_NAME}-skill-eval-report.md",
    EVALUATE / f"{SKILL_NAME}-skill-eval-report.zh-CN.md",
]
RATIONALE_DOCS = [RATIONALE / "design.md", RATIONALE / "design.zh-CN.md"]

# Constructs that the skill no longer has. Each maps to the markers that make a mention
# legitimate — an explicit statement that it is historical, in either language.
RETIRED = {
    "Level 2.5": (
        r"(?i)earlier draft|had a|was replaced|retired|removed|no longer|used to|"
        r"previous(?:ly)?|早先|原先|旧版|已(?:被)?(?:移除|替换|废弃)|不再"),
    "2.5 级": (
        r"(?i)早先|原先|旧版|已(?:被)?(?:移除|替换|废弃)|不再|曾经"),
}

# Gate numbering changed. An eval report may still use the old numbers, but only if it carries
# a snapshot note that says so.
SNAPSHOT_MARKER = r"(?i)snapshot note|快照说明"


def _texts(paths):
    return [(p, p.read_text(encoding="utf-8")) for p in paths if p.is_file()]


class RetiredConstructTests(unittest.TestCase):
    @unittest.skipUnless(RATIONALE.is_dir(), "rationale layer not present")
    def test_rationale_does_not_present_retired_constructs_as_current(self):
        """Scoped to the paragraph, not the line.

        A line-scoped version of this check failed on its own subject matter: the sentence
        explaining that Level 2.5 was removed wraps across three lines, and only the first
        carries the marker. Prose does not respect line boundaries — the paragraph is the
        smallest unit in which "this is history" can be stated.
        """
        for path, text in _texts(RATIONALE_DOCS):
            for para in re.split(r"\n\s*\n", text):
                for construct, allowed in RETIRED.items():
                    if construct not in para:
                        continue
                    with self.subTest(doc=path.name, construct=construct):
                        self.assertRegex(
                            para, allowed,
                            f"{path.name} mentions the retired {construct!r} without marking it "
                            f"as historical — a reader cannot tell it is gone. Paragraph: "
                            f"{para[:160]!r}")

    @unittest.skipUnless(RATIONALE.is_dir(), "rationale layer not present")
    def test_rationale_describes_the_current_resolution_order(self):
        """The replacement has to be present, not merely the removal of the old text."""
        for path, text in _texts(RATIONALE_DOCS):
            with self.subTest(doc=path.name):
                for step in ("R1", "R2", "R3"):
                    self.assertIn(step, text,
                                  f"{path.name} must describe resolution step {step}")

    @unittest.skipUnless(RATIONALE.is_dir(), "rationale layer not present")
    def test_rationale_does_not_pin_a_skill_line_count(self):
        """A line count in prose is stale the moment the skill is edited, and unlike a gate name
        nothing makes the staleness visible. `run_regression.sh` reports the live number."""
        for path, text in _texts(RATIONALE_DOCS):
            hits = re.findall(r"(?i)SKILL\.md[^.\n]{0,40}?(\d{3,4})\s*(?:lines|行)", text)
            hits += re.findall(r"(?i)(\d{3,4})\s*(?:lines|行)[^.\n]{0,20}?SKILL\.md", text)
            with self.subTest(doc=path.name):
                self.assertEqual([], hits,
                                 f"{path.name} pins SKILL.md at {hits} lines; counts drift")


class EvalReportSnapshotTests(unittest.TestCase):
    @unittest.skipUnless(any(p.is_file() for p in EVAL_REPORTS), "evaluate layer not present")
    def test_reports_declare_they_are_snapshots(self):
        """The reports carry counts and a weighted score from a specific revision. Without a
        snapshot note a reader takes both as descriptions of the skill they just installed."""
        for path, text in _texts(EVAL_REPORTS):
            with self.subTest(doc=path.name):
                self.assertRegex(text, SNAPSHOT_MARKER,
                                 f"{path.name} needs a snapshot note naming the evaluated date")

    @unittest.skipUnless(any(p.is_file() for p in EVAL_REPORTS), "evaluate layer not present")
    def test_retired_gate_numbers_are_reconciled(self):
        """The evaluated snapshot called the scorecard "Gate 4"; the skill now has four gates,
        0–3. Keeping the old number is fine — leaving it unexplained is not."""
        skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        gates = set(re.findall(r"### Gate (\d)", skill))
        for path, text in _texts(EVAL_REPORTS):
            stale = {g for g in re.findall(r"Gate (\d)", text) if g not in gates}
            if not stale:
                continue
            with self.subTest(doc=path.name):
                note = re.search(SNAPSHOT_MARKER, text)
                self.assertIsNotNone(
                    note, f"{path.name} cites Gate {sorted(stale)} which no longer exists")
                self.assertRegex(
                    text[note.start():note.start() + 2500],
                    r"(?i)gate numbering|Gate 4[^.]{0,80}(now|对应)|门禁编号",
                    f"{path.name} cites Gate {sorted(stale)}; the snapshot note must map the "
                    f"old numbering onto the current gates")


class SkillSelfConsistencyTests(unittest.TestCase):
    """Cheap internal checks that catch the same class of drift inside SKILL.md itself."""

    def setUp(self):
        self.skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")

    def test_gate_numbers_are_contiguous_from_zero(self):
        gates = sorted(int(g) for g in re.findall(r"### Gate (\d)", self.skill))
        self.assertEqual(list(range(len(gates))), gates,
                         f"gate numbering has a hole or a duplicate: {gates}")

    def test_every_phase_referenced_in_prose_exists(self):
        defined = {int(n) for n in re.findall(r"### Phase (\d)", self.skill)}
        cited = {int(n) for n in re.findall(r"\bPhase (\d)\b", self.skill)}
        self.assertTrue(cited <= defined,
                        f"prose cites undefined phase(s): {sorted(cited - defined)}")

    def test_every_referenced_reference_file_exists(self):
        for name in set(re.findall(r"references/([\w.-]+\.md)", self.skill)):
            with self.subTest(reference=name):
                self.assertTrue((SKILL_DIR / "references" / name).is_file(),
                                f"SKILL.md points at references/{name}, which does not exist")

    def test_every_referenced_script_exists(self):
        for name in set(re.findall(r"scripts/([\w./-]+\.(?:py|sh))", self.skill)):
            with self.subTest(script=name):
                self.assertTrue((SKILL_DIR / "scripts" / name).is_file(),
                                f"SKILL.md points at scripts/{name}, which does not exist")

    def test_phase4_table_and_linter_checks_agree_both_ways(self):
        """Phase 4 tabulates the mechanical checks by name, so the table can drift in either
        direction: a renamed check leaves the table describing something the tool never emits,
        and a check added without a row is invisible to the reader who trusts the table."""
        source = (SKILL_DIR / "scripts" / "lint_doc.py").read_text(encoding="utf-8")
        emitted = set(re.findall(r'Finding\(\s*\n?\s*"([\w-]+)"', source))
        self.assertTrue(emitted, "no check names extracted — the extraction regex is broken")

        phase4 = self.skill.split("### Phase 4")[1].split("### Phase 5")[0]
        documented = {name for name in re.findall(r"`([a-z][a-z0-9-]{2,})`", phase4)
                      if "-" in name or name in emitted}

        self.assertEqual(
            set(), emitted - documented,
            f"linter emits check(s) with no row in the Phase 4 table: "
            f"{sorted(emitted - documented)}")
        self.assertEqual(
            set(), documented - emitted,
            f"Phase 4 documents check(s) the linter never emits: "
            f"{sorted(documented - emitted)}")


if __name__ == "__main__":
    unittest.main()
