import re
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[2]
SKILL_MD = SKILL_DIR / "SKILL.md"
UPDATE_DOC_REF = SKILL_DIR / "references" / "update-doc.md"
CI_DRIFT_REF = SKILL_DIR / "references" / "ci-drift.md"


def frontmatter(text: str) -> str:
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        raise AssertionError("missing yaml frontmatter")
    return match.group(1)


class UpdateDocSkillContractTests(unittest.TestCase):
    def test_frontmatter_name_and_description(self) -> None:
        data = SKILL_MD.read_text()
        fm = frontmatter(data)
        self.assertIn("name: update-doc", fm)
        self.assertIn("Keep repository documentation synchronized", fm)

    def test_lightweight_sections_present(self) -> None:
        data = SKILL_MD.read_text()
        self.assertIn("Lightweight Output Mode", data)
        self.assertIn("Full Output Mode", data)
        self.assertIn("Compact output", data)

    def test_self_validation_section_present(self) -> None:
        data = SKILL_MD.read_text()
        self.assertIn("Self-Validation", data)
        self.assertIn("scripts/run_regression.sh", data)

    def test_reference_docs_cover_lightweight_mode(self) -> None:
        data = UPDATE_DOC_REF.read_text()
        self.assertIn("Lightweight output", data)
        self.assertIn("Full output", data)

    def test_ci_reference_mentions_contract_checks(self) -> None:
        data = CI_DRIFT_REF.read_text()
        self.assertIn("contract test", data)
        self.assertIn("run_regression.sh", data)

    # --- Evidence Commands: multi-language coverage ---

    def test_evidence_commands_has_language_detection(self) -> None:
        data = SKILL_MD.read_text()
        self.assertIn("Detect Language", data)
        self.assertIn("detect dominant language", data)

    def test_evidence_commands_covers_python(self) -> None:
        data = SKILL_MD.read_text()
        self.assertIn("### Python", data)
        # urlpatterns and BaseSettings are stable, backslash-free identifiers in this section
        self.assertIn("urlpatterns", data)
        self.assertIn("BaseSettings", data)

    def test_evidence_commands_covers_node(self) -> None:
        data = SKILL_MD.read_text()
        self.assertIn("Node.js / TypeScript", data)
        # package.json is a stable, backslash-free identifier in this section
        self.assertIn("package.json", data)

    def test_evidence_commands_covers_java(self) -> None:
        data = SKILL_MD.read_text()
        self.assertIn("### Java", data)
        self.assertIn("@SpringBootApplication", data)

    def test_evidence_commands_has_generic_fallback(self) -> None:
        data = SKILL_MD.read_text()
        self.assertIn("Generic", data)
        self.assertIn("language-agnostic", data)

    # --- Output Examples ---

    def test_output_examples_section_present(self) -> None:
        data = SKILL_MD.read_text()
        self.assertIn("## Output Examples", data)

    def test_output_examples_has_lightweight_example(self) -> None:
        data = SKILL_MD.read_text()
        self.assertIn("Lightweight Output Example", data)
        self.assertIn("Evidence map", data)
        self.assertIn("Command verification", data)

    def test_output_examples_has_full_output_example(self) -> None:
        data = SKILL_MD.read_text()
        self.assertIn("Full Output Example", data)
        self.assertIn("Scorecard", data)
        self.assertIn("Open gaps", data)
        self.assertIn("Not found in repo", data)


if __name__ == "__main__":
    unittest.main()
