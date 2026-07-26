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
        """Gate B is stack-independent — it was "Go Resource Inventory" while Gate D had already
        become all-stack, which left the 15-step prose contradicting the domain table."""
        self.assertIn("Gate B: Resource Inventory (Mandatory, every stack)", self.skill_text)
        self.assertNotIn("Go Resource Inventory", self.skill_text)

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
        """Domain names are the stack-independent canonical set (see
        authorization-and-policy.md §2). The Go reference is one instantiation of it, not the
        definition — it previously used its own names ("TLS Safety", "Go-Specific ..."), which is
        what made "Domain 7" ambiguous across stacks."""
        ref = self.reference_texts["go-secure-coding.md"]
        for num, domain in enumerate((
            "Randomness Safety",
            "Injection & Data-Access Safety",
            "Sensitive Data Handling",
            "Secret / Config Management",
            "Transport Security",
            "Crypto Primitive Correctness",
            "Concurrency & Shared-State Safety",
            "Language-Specific Injection Sinks",
            "Static Scanner Posture",
            "Dependency Vulnerability Posture",
        ), start=1):
            self.assertIn(f"### Domain {num} — {domain}", ref,
                          f"go-secure-coding.md must head Domain {num} with the canonical name "
                          f"{domain!r}")

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
            "### 2) Security Domain Coverage",
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
        """The worked example lives in references (progressive disclosure); SKILL.md must
        still point at it, and the example must model the safe-reproducer rules."""
        ref = (SKILL_DIR / "references" / "security-review.md").read_text()
        self.assertIn("One-Shot Finding Example", ref)
        self.assertIn("SEC-001", ref)
        self.assertIn("Regression test", ref)
        self.assertIn("NOT executed", ref, "the example reproducer must be labelled unexecuted")
        self.assertIn("127.0.0.1", ref, "the example must target loopback, not a real host")
        self.assertIn("One-Shot Finding Example", self.skill_text,
                      "SKILL.md must still route the reader to the worked example")

    def test_json_summary_schema(self) -> None:
        json_match = re.search(r"```json\n(\{.*?\})\n```", self.skill_text, re.DOTALL)
        self.assertIsNotNone(json_match, "JSON summary block not found")
        data = json.loads(json_match.group(1))
        self.assertIn("summary", data)
        self.assertIn("counts", data)
        # Stack-neutral key: a CI consumer must not branch on language to read the result.
        self.assertIn("security_domains", data)
        self.assertNotIn("go_domains", data, "go_domains is retired; use security_domains")
        self.assertIn("findings", data)
        self.assertEqual(data["security_domains"]["total"], 10)
        # Multi-language and audit context must be machine-readable too.
        self.assertIn("stack", data)
        self.assertIn("asvs_version", data)
        self.assertIn("active_verification", data)
        self.assertIn(data["active_verification"], ("permitted", "not_permitted"))

    def test_asvs_mappings_are_version_pinned(self) -> None:
        """A bare `V4` does not identify a requirement: ASVS 5.0.0 renumbered 4.x chapters."""
        json_match = re.search(r"```json\n(\{.*?\})\n```", self.skill_text, re.DOTALL)
        data = json.loads(json_match.group(1))
        for finding in data["findings"]:
            self.assertRegex(
                finding["asvs"], r"ASVS \d+\.\d+\.\d+ V\d",
                "ASVS mappings must be version-pinned (e.g. 'ASVS 4.0.3 V4.1.2')",
            )

    def test_risk_acceptance_requires_approval(self) -> None:
        self.assertIn("VP-level", self.skill_text)
        self.assertIn("tech-lead-level", self.skill_text)

    # ------------------------------------------------------------------
    # Automation gate
    # ------------------------------------------------------------------

    def test_automation_commands_present(self) -> None:
        """Commands live in the policy reference; SKILL.md keeps the execution policy."""
        policy = (SKILL_DIR / "references" / "authorization-and-policy.md").read_text()
        for cmd in ("rg -n", "go test -race", "gosec", "govulncheck"):
            self.assertIn(cmd, policy, f"automation command {cmd!r} missing from policy ref")
        self.assertIn("authorization-and-policy.md", self.skill_text,
                      "SKILL.md must route to the command reference")

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
        """N/A judgment table lives in the policy reference; the anti-pattern rule stays inline."""
        policy = (SKILL_DIR / "references" / "authorization-and-policy.md").read_text()
        self.assertIn("N/A` Judgment Examples", policy)
        start = policy.index("N/A` Judgment Examples")
        section = policy[start : start + 1500]
        self.assertIn("Rationale", section)
        self.assertIn("Randomness safety", section)
        self.assertRegex(self.skill_text, r"`?N/A`? judgments",
                         "SKILL.md must route to the N/A examples")
        self.assertRegex(self.skill_text, r"(?i)anti-pattern.*`N/A`|`N/A`.*trigger signals",
                         "the N/A anti-pattern rule must stay inline in SKILL.md")

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
        self.assertIn("do not block merge", self.skill_text)

    def test_pre_existing_default_has_documented_overrides(self) -> None:
        """"pre-existing → don't block" is an org policy call, not a security clearance. The
        skill must name the cases where it is void, or it reads as blanket permission to ship
        a known P0."""
        self.assertRegex(
            self.skill_text, r"(?i)void",
            "the pre-existing merge default must state when it does not apply",
        )
        for override in ("release vehicle", "widens the attack surface", "same\n  file/function|same file/function"):
            self.assertRegex(
                self.skill_text, override,
                f"missing pre-existing block override: {override}",
            )
        self.assertRegex(
            self.skill_text, r"(?i)never present .pre-existing. as a reason",
            "must forbid using 'pre-existing' as a risk-acceptance argument",
        )

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

    # ------------------------------------------------------------------
    # Drift guard: normative rules live only in SKILL.md
    # ------------------------------------------------------------------

    def test_aids_reference_does_not_duplicate_normative_rules(self) -> None:
        """references/security-review.md once restated severity/SLA/suppression rules
        and drifted (4 suppression rules in SKILL.md vs 3 in the copy). It is now a
        supplementary-aids file; normative rule text must never reappear there."""
        aids_text = (REFERENCES_DIR / "security-review.md").read_text()
        self.assertIn("only in `SKILL.md`", aids_text, "single-source-of-truth note missing")
        forbidden = [
            "Suppress only when",          # suppression rules copy
            "SLA Defaults",                # remediation SLA copy
            "Evidence Levels",             # confidence labels copy
            "Baseline Diff Labels",        # baseline status copy
            "Risk Acceptance Entry",       # risk acceptance template copy
            "Tool Interpretation",         # tool interpretation copy
            "Tooling Quick Commands",      # automation commands copy
            "Go 10-Domain Quick Matrix",   # Gate D domain list copy
        ]
        for marker in forbidden:
            self.assertNotIn(
                marker,
                aids_text,
                f"normative section {marker!r} duplicated in references/security-review.md; "
                "SKILL.md is the single source of truth",
            )

    def test_frontmatter_description_has_trigger_and_boundary(self) -> None:
        """Description must state when to use the skill and how it differs from
        go-review-lead / go-security-review to prevent trigger collisions."""
        fm = frontmatter(self.skill_text)
        desc = re.search(r"^description:\s*(.+)$", fm, re.MULTILINE).group(1)
        self.assertIn("Use when", desc, "description missing 'Use when' trigger phrase")
        self.assertIn("go-review-lead", desc, "description missing boundary vs go-review-lead")
        self.assertIn("go-security-review", desc, "description missing boundary vs go-security-review")


class TestCoverageDocAccuracy(unittest.TestCase):
    """COVERAGE.md drifted to 46 tests / 494 lines while reality was 48 / 500. Hand-maintained
    counts always drift; recompute them from disk instead."""

    COVERAGE = SKILL_DIR / "scripts" / "tests" / "COVERAGE.md"
    TESTS = SKILL_DIR / "scripts" / "tests"

    @staticmethod
    def _declared(text: str, label: str):
        m = re.search(rf"\|\s*\*{{0,2}}{re.escape(label)}\*{{0,2}}\s*\|\s*\*{{0,2}}(\d+)", text)
        return int(m.group(1)) if m else None

    @staticmethod
    def _count_tests(path) -> int:
        """Count `def test_*` across a test module."""
        return len(re.findall(r"(?m)^\s+def test_\w+", path.read_text(encoding="utf-8")))

    def test_skill_md_line_count_is_accurate(self) -> None:
        actual = len(SKILL_MD.read_text(encoding="utf-8").splitlines())
        text = self.COVERAGE.read_text(encoding="utf-8")
        m = re.search(r"\|\s*SKILL\.md lines\s*\|\s*(\d+)", text)
        self.assertIsNotNone(m, "COVERAGE.md must declare the SKILL.md line count")
        self.assertEqual(actual, int(m.group(1)),
                         f"COVERAGE.md says {m.group(1)} lines; SKILL.md has {actual}")

    def test_fixture_count_is_accurate(self) -> None:
        actual = len(list((self.TESTS / "golden").glob("*.json")))
        declared = self._declared(self.COVERAGE.read_text(encoding="utf-8"),
                                  "Total golden fixtures")
        self.assertEqual(actual, declared,
                         f"COVERAGE.md says {declared} fixtures; disk has {actual}")

    def test_declared_test_counts_match_disk(self) -> None:
        text = self.COVERAGE.read_text(encoding="utf-8")
        for label, module in (
            ("Contract tests", "test_skill_contract.py"),
            ("Golden-fixture tests", "test_golden_reviews.py"),
            ("Executable-example tests", "test_examples_executable.py"),
            ("Forward-eval tests", "test_forward_eval.py"),
        ):
            with self.subTest(module=module):
                declared = self._declared(text, label)
                self.assertIsNotNone(declared, f"COVERAGE.md must declare '{label}'")
                actual = self._count_tests(self.TESTS / module)
                self.assertEqual(actual, declared,
                                 f"{label}: COVERAGE.md says {declared}, {module} defines {actual}")

    def test_total_is_the_sum(self) -> None:
        text = self.COVERAGE.read_text(encoding="utf-8")
        parts = sum(self._count_tests(self.TESTS / m) for m in (
            "test_skill_contract.py", "test_golden_reviews.py",
            "test_examples_executable.py", "test_forward_eval.py"))
        self.assertEqual(parts, self._declared(text, "Total tests"),
                         "COVERAGE.md 'Total tests' must equal the sum of the layers")

    def test_forward_eval_layer_is_documented(self) -> None:
        text = self.COVERAGE.read_text(encoding="utf-8")
        self.assertIn("test_forward_eval.py", text)
        self.assertIn("forward_eval/README.md", text)


class TestLanguageReferenceNavigation(unittest.TestCase):
    """The language references passed 100 lines with no way to navigate them."""

    def test_language_refs_have_contents(self) -> None:
        for name in ("lang-nodejs.md", "lang-java.md", "lang-python.md"):
            text = (SKILL_DIR / "references" / name).read_text(encoding="utf-8")
            if len(text.splitlines()) < 100:
                continue
            self.assertIn("## Contents", text,
                          f"{name} exceeds 100 lines and needs a Contents block")

    def test_go_reference_has_contents(self) -> None:
        text = (SKILL_DIR / "references" / "go-secure-coding.md").read_text(encoding="utf-8")
        self.assertIn("## Contents", text)


if __name__ == "__main__":
    unittest.main()
