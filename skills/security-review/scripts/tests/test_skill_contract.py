"""Contract tests for security-review SKILL.md.

Validates that required sections, gates, labels, and structural elements
exist in the skill document and its references. Does NOT test LLM behavior —
only verifies that the rule surface is present and well-formed.
"""

import re
import json
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[2]
SKILL_MD = SKILL_DIR / "SKILL.md"
REFERENCES_DIR = SKILL_DIR / "references"


def frontmatter(text: str) -> str:
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        raise AssertionError("missing yaml frontmatter")
    return match.group(1)


class SecurityReviewContractTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.skill_text = SKILL_MD.read_text()
        cls.reference_texts: dict[str, str] = {}
        for ref_file in REFERENCES_DIR.glob("*.md"):
            cls.reference_texts[ref_file.name] = ref_file.read_text()
        cls.all_text = cls.skill_text + "\n".join(cls.reference_texts.values())

    # ------------------------------------------------------------------
    # Frontmatter
    # ------------------------------------------------------------------

    def test_frontmatter_name(self) -> None:
        fm = frontmatter(self.skill_text)
        name_match = re.search(r"^name:\s*(.+)$", fm, re.MULTILINE)
        self.assertIsNotNone(name_match, "missing name in frontmatter")
        self.assertEqual("security-review", name_match.group(1).strip())

    def test_frontmatter_description_not_empty(self) -> None:
        fm = frontmatter(self.skill_text)
        desc_match = re.search(r"^description:\s*(.+)$", fm, re.MULTILINE)
        self.assertIsNotNone(desc_match, "missing description in frontmatter")
        self.assertGreater(len(desc_match.group(1).strip()), 20)

    # ------------------------------------------------------------------
    # Core principles and labels
    # ------------------------------------------------------------------

    def test_evidence_confidence_labels(self) -> None:
        for label in ("confirmed", "likely", "suspected"):
            self.assertIn(
                f"`{label}`",
                self.skill_text,
                f"confidence label {label!r} missing",
            )

    def test_severity_levels(self) -> None:
        for level in ("P0 Critical", "P1 High", "P2 Medium", "P3 Low"):
            self.assertIn(level, self.skill_text)

    def test_suppression_rules_count(self) -> None:
        section_start = self.skill_text.index("## False-Positive Suppression Rules")
        section_end = self.skill_text.index("\n## ", section_start + 1)
        section = self.skill_text[section_start:section_end]
        numbered = re.findall(r"^\d+\.", section, re.MULTILINE)
        self.assertGreaterEqual(len(numbered), 4, "need at least 4 suppression rules")

    def test_remediation_sla_all_levels(self) -> None:
        for level in ("P0", "P1", "P2", "P3"):
            self.assertIn(f"`{level}`:", self.skill_text)

    # ------------------------------------------------------------------
    # Review depth selection
    # ------------------------------------------------------------------

    def test_review_depth_section_exists(self) -> None:
        self.assertIn("## Review Depth Selection", self.skill_text)

    def test_review_depth_has_three_levels(self) -> None:
        for depth in ("**Lite**", "**Standard**", "**Deep**"):
            self.assertIn(depth, self.skill_text)

    def test_review_depth_trigger_signals(self) -> None:
        self.assertIn("Auth/authz middleware", self.skill_text)
        self.assertIn("Dockerfile", self.skill_text)
        self.assertIn("go.mod", self.skill_text)

    # ------------------------------------------------------------------
    # Mandatory gates A-F
    # ------------------------------------------------------------------

    def test_all_gates_exist(self) -> None:
        for gate in ("Gate A", "Gate B", "Gate C", "Gate D", "Gate E", "Gate F"):
            self.assertIn(gate, self.skill_text, f"{gate} missing from SKILL.md")

    def test_gate_a_constructor_release(self) -> None:
        self.assertIn("Constructor-Release Pairing", self.skill_text)

    def test_gate_b_resource_inventory(self) -> None:
        self.assertIn("Go Resource Inventory", self.skill_text)

    def test_gate_b_references_detail(self) -> None:
        self.assertIn("references/go-secure-coding.md", self.skill_text)

    def test_gate_d_10_domains(self) -> None:
        self.assertIn("10-Domain Coverage", self.skill_text)
        for i in range(1, 11):
            self.assertIn(f"{i}.", self.skill_text)

    def test_gate_e_falsification(self) -> None:
        self.assertIn("Second-Pass Falsification", self.skill_text)

    def test_gate_f_uncovered_risk(self) -> None:
        self.assertIn("Uncovered Risk List", self.skill_text)

    # ------------------------------------------------------------------
    # Process steps
    # ------------------------------------------------------------------

    def test_process_has_15_steps(self) -> None:
        section_start = self.skill_text.index("## Fixed Process + Mandatory Gates")
        section_end = self.skill_text.index("\n### ", section_start + 1)
        section = self.skill_text[section_start:section_end]
        steps = re.findall(r"^\d+\.", section, re.MULTILINE)
        self.assertEqual(len(steps), 15, f"expected 15 steps, found {len(steps)}")

    # ------------------------------------------------------------------
    # Scenario checklists (reference)
    # ------------------------------------------------------------------

    def test_scenario_checklist_reference_exists(self) -> None:
        self.assertIn("references/scenario-checklists.md", self.skill_text)
        self.assertIn("scenario-checklists.md", self.reference_texts)

    def test_scenario_checklist_has_11_scenarios(self) -> None:
        checklist = self.reference_texts["scenario-checklists.md"]
        headings = re.findall(r"^## \d+\)", checklist, re.MULTILINE)
        self.assertEqual(
            len(headings), 11, f"expected 11 scenarios, found {len(headings)}"
        )

    def test_go_specific_sinks_in_checklist(self) -> None:
        checklist = self.reference_texts["scenario-checklists.md"]
        for sink in (
            "text/template",
            "os/exec.Command",
            "net/http.Redirect",
            "filepath.Join",
        ):
            self.assertIn(sink, checklist, f"Go sink {sink!r} missing from checklist")

    def test_container_security_in_checklist(self) -> None:
        checklist = self.reference_texts["scenario-checklists.md"]
        for item in ("runAsNonRoot", "NetworkPolicy", "HEALTHCHECK"):
            self.assertIn(item, checklist, f"container item {item!r} missing")

    def test_concurrency_security_in_checklist(self) -> None:
        checklist = self.reference_texts["scenario-checklists.md"]
        for item in ("TOCTOU", "Double-spend", "go test -race"):
            self.assertIn(item, checklist, f"concurrency item {item!r} missing")

    # ------------------------------------------------------------------
    # Go secure-coding reference
    # ------------------------------------------------------------------

    def test_go_secure_coding_reference_exists(self) -> None:
        self.assertIn("go-secure-coding.md", self.reference_texts)

    def test_go_secure_coding_has_all_domains(self) -> None:
        ref = self.reference_texts["go-secure-coding.md"]
        for domain in (
            "Randomness Safety",
            "Injection + SQL",
            "Sensitive Data",
            "Secret/Config",
            "TLS Safety",
            "Crypto Primitive",
            "Concurrency Safety",
            "Go-Specific Injection Sinks",
            "Static Scanner",
            "Dependency Vulnerability",
        ):
            self.assertIn(domain, ref, f"domain {domain!r} missing from go-secure-coding")

    def test_go_resource_inventory_table(self) -> None:
        ref = self.reference_texts["go-secure-coding.md"]
        for resource in ("rows", "stmt", "tx", "resp.Body", "goroutine", "cancel"):
            self.assertIn(resource, ref, f"resource {resource!r} missing from inventory")

    # ------------------------------------------------------------------
    # Language extension references
    # ------------------------------------------------------------------

    def test_lang_references_exist(self) -> None:
        for lang_file in ("lang-nodejs.md", "lang-java.md", "lang-python.md"):
            self.assertIn(
                lang_file,
                self.reference_texts,
                f"language reference {lang_file!r} missing",
            )

    def test_lang_references_have_domain_table(self) -> None:
        for lang_file in ("lang-nodejs.md", "lang-java.md", "lang-python.md"):
            text = self.reference_texts[lang_file]
            self.assertIn("| Domain |", text, f"{lang_file} missing domain table")

    def test_lang_references_have_automation_commands(self) -> None:
        for lang_file in ("lang-nodejs.md", "lang-java.md", "lang-python.md"):
            text = self.reference_texts[lang_file]
            self.assertIn("Automation Commands", text, f"{lang_file} missing automation")

    def test_lang_references_have_false_positives(self) -> None:
        for lang_file in ("lang-nodejs.md", "lang-java.md", "lang-python.md"):
            text = self.reference_texts[lang_file]
            self.assertIn("False Positives", text, f"{lang_file} missing FP section")

    # ------------------------------------------------------------------
    # Output contract
    # ------------------------------------------------------------------

    def test_output_contract_sections(self) -> None:
        for section in (
            "### 1) Findings",
            "### 2) Go 10-Domain Coverage",
            "### 3) Automation Evidence",
            "### 4) Open questions",
            "### 5) Risk Acceptance Register",
            "### 6) Remediation Plan",
            "### 7) Machine-Readable Summary",
            "### 8) Hardening suggestions",
            "### 9) Uncovered Risk List",
        ):
            self.assertIn(section, self.skill_text, f"output section {section!r} missing")

    def test_finding_example_exists(self) -> None:
        self.assertIn("One-Shot Finding Example", self.skill_text)
        self.assertIn("SEC-001", self.skill_text)
        self.assertIn("Reproducer", self.skill_text)
        self.assertIn("Regression test", self.skill_text)

    def test_json_summary_schema(self) -> None:
        json_match = re.search(r"```json\n(\{.*?\})\n```", self.skill_text, re.DOTALL)
        self.assertIsNotNone(json_match, "JSON summary block not found")
        data = json.loads(json_match.group(1))
        self.assertIn("summary", data)
        self.assertIn("counts", data)
        self.assertIn("go_domains", data)
        self.assertIn("findings", data)
        self.assertEqual(data["go_domains"]["total"], 10)

    def test_risk_acceptance_requires_approval(self) -> None:
        self.assertIn("VP-level", self.skill_text)
        self.assertIn("tech-lead-level", self.skill_text)

    # ------------------------------------------------------------------
    # Automation gate
    # ------------------------------------------------------------------

    def test_automation_commands_present(self) -> None:
        for cmd in ("rg -n", "go test -race", "gosec", "govulncheck"):
            self.assertIn(cmd, self.skill_text, f"automation command {cmd!r} missing")

    def test_tool_interpretation_rules(self) -> None:
        self.assertIn("Tool Interpretation Rules", self.skill_text)
        for tool in ("go test -race", "gosec", "govulncheck"):
            self.assertIn(tool, self.skill_text)

    # ------------------------------------------------------------------
    # Standards mapping
    # ------------------------------------------------------------------

    def test_standards_mapping_present(self) -> None:
        self.assertIn("CWE-xxx", self.skill_text)
        self.assertIn("OWASP ASVS", self.skill_text)

    # ------------------------------------------------------------------
    # Baseline diff mode
    # ------------------------------------------------------------------

    def test_baseline_diff_mode_documented(self) -> None:
        self.assertIn("Baseline Diff Mode", self.skill_text)
        for status in ("`new`", "`regressed`", "`unchanged`", "`resolved`"):
            self.assertIn(status, self.skill_text, f"baseline status {status!r} missing")
        self.assertIn("Baseline not found", self.skill_text)

    # ------------------------------------------------------------------
    # Issue 1: SKILL.md line budget (≤ 600 lines)
    # ------------------------------------------------------------------

    def test_skill_md_stays_within_line_budget(self) -> None:
        lines = len(self.skill_text.splitlines())
        self.assertLessEqual(lines, 500, f"SKILL.md too long: {lines} lines (budget: 500)")

    # ------------------------------------------------------------------
    # Issue 4: Anti-examples and N/A judgment — contract coverage
    # ------------------------------------------------------------------

    def test_anti_examples_inline_stubs_exist(self) -> None:
        """SKILL.md must contain the three inline anti-example stubs (AE-1, AE-3, AE-5)."""
        for ae in ("AE-1", "AE-3", "AE-5"):
            self.assertIn(ae, self.skill_text, f"{ae} missing from SKILL.md inline stubs")

    def test_anti_examples_reference_has_extended_rules(self) -> None:
        """anti-examples.md must contain all four extended anti-examples."""
        anti = self.reference_texts.get("anti-examples.md", "")
        self.assertNotEqual(anti, "", "anti-examples.md reference missing")
        for ae in ("AE-2", "AE-4", "AE-6", "AE-7"):
            self.assertIn(ae, anti, f"{ae} missing from anti-examples.md")
        self.assertIn("transitive", anti.lower(), "AE-7 transitive call path rule missing")

    def test_na_judgment_examples_section_exists(self) -> None:
        """N/A Judgment Examples section must be present with a verdict table."""
        self.assertIn("N/A Judgment Examples", self.skill_text)
        na_start = self.skill_text.index("N/A Judgment Examples")
        na_section = self.skill_text[na_start : na_start + 1000]
        self.assertIn("N/A", na_section)
        self.assertIn("Rationale", na_section)
        # At least one row showing a valid N/A domain
        self.assertIn("Randomness safety", na_section)

    # ------------------------------------------------------------------
    # Issue 5: Finding Volume Cap
    # ------------------------------------------------------------------

    def test_finding_volume_cap_documented(self) -> None:
        self.assertIn("Finding Volume Cap", self.skill_text)
        self.assertIn("P0/P1", self.skill_text)
        self.assertIn("P0/P1 findings are never dropped by volume cap", self.skill_text)
        for depth_cap in ("Lite ≤ 3", "Standard ≤ 5", "Deep ≤ 8"):
            self.assertIn(depth_cap, self.skill_text, f"Volume cap for {depth_cap!r} missing")

    # ------------------------------------------------------------------
    # Issue 6: Change Origin Classification
    # ------------------------------------------------------------------

    def test_change_origin_classification_documented(self) -> None:
        self.assertIn("Change Origin Classification", self.skill_text)
        for label in ("`introduced`", "`pre-existing`", "`uncertain`"):
            self.assertIn(label, self.skill_text, f"Origin label {label!r} missing")
        self.assertIn("Must fix before merge", self.skill_text)
        self.assertIn("do NOT block merge", self.skill_text)

    # ------------------------------------------------------------------
    # Issue 7: Gate C — independent contract test
    # ------------------------------------------------------------------

    def test_gate_c_lifecycle_contract_rules(self) -> None:
        """Gate C must document its own specific verification requirements independently."""
        gate_c_start = self.skill_text.index("Gate C: Third-Party Lifecycle")
        gate_c_section = self.skill_text[gate_c_start : gate_c_start + 600]
        self.assertIn("Cite exactly what contract was used", gate_c_section)
        self.assertIn("suspected", gate_c_section)
        self.assertIn("Uncovered Risk List", gate_c_section)


if __name__ == "__main__":
    unittest.main()
