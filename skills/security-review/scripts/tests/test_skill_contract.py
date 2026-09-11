"""Contract tests for security-review SKILL.md.

Validates that required sections, gates, labels, and structural elements
exist in the skill document and its references. Does NOT test LLM behavior —
only verifies that the rule surface is present and well-formed.
"""

import re
import sys
import subprocess
import importlib.util
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
        # The normative report contract spans two files since § Output Contract's field detail
        # was split into references/output-contract.md: SKILL.md keeps the depth matrix (which
        # drives execution) and the reference carries §1-§9. Tests about the contract must read
        # both, or an extraction looks like a deletion.
        cls.contract_text = cls.skill_text + "\n" + cls.reference_texts["output-contract.md"]

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
        become all-stack, which left the 15-step prose contradicting the domain table.

        Asserted semantically rather than as an exact heading string: the earlier version pinned
        the literal `(Mandatory, every stack)` parenthetical, so clarifying *which depths* Gate B
        is mandatory at broke the test without anything being wrong."""
        self.assertRegex(
            self.skill_text,
            r"(?m)^#{2,4}\s*Gate B: Resource Inventory\s*\(([^)]*)\)",
            "Gate B must keep its heading and a mandatory/scope parenthetical",
        )
        heading = re.search(r"(?m)^#{2,4}\s*Gate B: Resource Inventory\s*\(([^)]*)\)",
                            self.skill_text).group(1)
        self.assertIn("Mandatory", heading, "Gate B must be marked mandatory")
        self.assertIn("every stack", heading, "Gate B must stay stack-independent")
        self.assertNotIn("Go Resource Inventory", self.skill_text)

    def test_gate_b_depth_scope_agrees_with_depth_selection(self) -> None:
        """Gate B's heading now names the depths it applies at. That claim must not contradict
        the depth table or the Quick Reference, which is how the A/B overlap became invisible in
        the first place: two sections describing the same scan with no stated relationship."""
        heading = re.search(r"(?m)^#{2,4}\s*Gate B: Resource Inventory\s*\(([^)]*)\)",
                            self.skill_text).group(1)
        if "Standard" in heading or "Deep" in heading:
            self.assertRegex(self.skill_text, r"skip Gate B",
                             "the heading says Gate B is Standard/Deep-only, so the fast-scan "
                             "path must say Gate B is skipped")
            lite_row = [l for l in self.skill_text.splitlines()
                        if "**Lite**" in l and "Gate A" in l]
            self.assertTrue(lite_row, "the depth table must have a Lite row listing its gates")
            self.assertNotIn("Gate B", lite_row[0],
                             "Lite must not list Gate B while the heading excludes it")
        # And the relationship between A and B must be stated, not left implicit.
        self.assertRegex(self.skill_text, r"(?i)Gates A and B are",
                         "state how Gate A and Gate B relate; otherwise they read as two "
                         "copies of the same acquire/release scan")

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
        """Spans SKILL.md + references/output-contract.md — see setUpClass.contract_text."""
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
            self.assertIn(section, self.contract_text, f"output section {section!r} missing")

    def test_finding_example_exists(self) -> None:
        """The worked example lives in references (progressive disclosure); SKILL.md must
        still point at it, and the example must model the safe-reproducer rules."""
        ref = (SKILL_DIR / "references" / "security-review.md").read_text()
        self.assertIn("One-Shot Finding Example", ref)
        self.assertIn("SEC-001", ref)
        self.assertIn("Regression test", ref)
        self.assertIn("NOT executed", ref, "the example reproducer must be labelled unexecuted")
        self.assertIn("127.0.0.1", ref, "the example must target loopback, not a real host")
        self.assertIn("One-Shot Finding Example", self.contract_text,
                      "the report contract must still route the reader to the worked example; "
                      "the pointer moved to output-contract.md with § 1 Findings")

    def test_json_summary_schema(self) -> None:
        json_match = re.search(r"```json\n(\{.*?\})\n```", self.contract_text, re.DOTALL)
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
        json_match = re.search(r"```json\n(\{.*?\})\n```", self.contract_text, re.DOTALL)
        data = json.loads(json_match.group(1))
        for finding in data["findings"]:
            self.assertRegex(
                finding["asvs"], r"ASVS \d+\.\d+\.\d+ V\d",
                "ASVS mappings must be version-pinned (e.g. 'ASVS 4.0.3 V4.1.2')",
            )

    def test_risk_acceptance_requires_approval(self) -> None:
        self.assertIn("VP-level", self.contract_text)
        self.assertIn("tech-lead-level", self.contract_text)

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

    def test_suppressed_array_field_names_are_stated_not_paraphrased(self) -> None:
        """Reported hole, found by a live eval run: every other row of the JSON field-semantics
        table backticks the exact field name, but the `suppressed[]` row described its three
        sub-fields only in prose ("the vulnerability class", "the residual risk") — a live
        model consistently wrote `suppressed[].class` and `suppressed[].residual`, neither of
        which the schema defines, and every occurrence failed schema validation. The docs must
        name `candidate` and `residual_risk` explicitly, not just describe what they mean."""
        policy = self.reference_texts["authorization-and-policy.md"]
        self.assertIn("`candidate`", policy)
        self.assertIn("`residual_risk`", policy)
        self.assertIn("not** `class`", policy)
        self.assertIn("not** `residual`", policy)

    def test_scanner_egress_is_distinguished_from_target_probing(self) -> None:
        """Reported hole: the authorization table lists `govulncheck`/`npm audit`/`pip-audit`
        as always-allowed local static scanners while also forbidding 'any request to a host
        you did not stand up' — but those scanners reach vuln.go.dev / the npm registry / PyPI
        by default. Without a clarification, a literal reading of the two rules contradicts
        itself."""
        policy = self.reference_texts["authorization-and-policy.md"]
        self.assertIn("different authorization question", policy)
        for tool_egress in ("npm audit", "vuln.go.dev", "PyPI"):
            self.assertIn(tool_egress, policy)
        self.assertIn("air-gapped", policy.lower())

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
        self.assertIn("Finding Volume Cap", self.contract_text)
        self.assertIn("P0/P1", self.contract_text)
        self.assertIn("P0/P1 findings are never dropped by volume cap", self.contract_text)
        for depth_cap in ("Lite ≤ 3", "Standard ≤ 5", "Deep ≤ 8"):
            self.assertIn(depth_cap, self.contract_text, f"Volume cap for {depth_cap!r} missing")

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

    # COVERAGE.md label -> test module. Kept in one place because two copies of this mapping
    # (one per assertion below) drifted apart the moment a fifth module was added.
    LAYER_LABELS = {
        "Contract tests": "test_skill_contract.py",
        "Golden-fixture tests": "test_golden_reviews.py",
        "Executable-example tests": "test_examples_executable.py",
        "Forward-eval tests": "test_forward_eval.py",
        "Report-schema tests": "test_report_schema.py",
    }

    def test_every_test_module_is_accounted_for(self) -> None:
        """Derived from disk: a new test module must be declared in COVERAGE.md, or the totals
        below would silently exclude it and still agree with each other."""
        on_disk = {p.name for p in self.TESTS.glob("test_*.py")}
        self.assertEqual(on_disk, set(self.LAYER_LABELS.values()),
                         f"unaccounted test modules: {on_disk - set(self.LAYER_LABELS.values())}")

    def test_declared_test_counts_match_disk(self) -> None:
        text = self.COVERAGE.read_text(encoding="utf-8")
        for label, module in self.LAYER_LABELS.items():
            with self.subTest(module=module):
                declared = self._declared(text, label)
                self.assertIsNotNone(declared, f"COVERAGE.md must declare '{label}'")
                actual = self._count_tests(self.TESTS / module)
                self.assertEqual(actual, declared,
                                 f"{label}: COVERAGE.md says {declared}, {module} defines {actual}")

    def test_total_is_the_sum(self) -> None:
        text = self.COVERAGE.read_text(encoding="utf-8")
        parts = sum(self._count_tests(self.TESTS / m) for m in self.LAYER_LABELS.values())
        self.assertEqual(parts, self._declared(text, "Total tests"),
                         "COVERAGE.md 'Total tests' must equal the sum of the layers")

    def test_forward_eval_layer_is_documented(self) -> None:
        text = self.COVERAGE.read_text(encoding="utf-8")
        self.assertIn("test_forward_eval.py", text)
        self.assertIn("forward_eval/README.md", text)

    def test_every_nested_example_matrix_declares_its_count(self) -> None:
        """Reported hole: the prose said `xml_facts_test.py` adds 11 more tests while five had
        been added to that file — a hand-typed count with no test behind it.

        Generalised from that one filename to EVERY nested matrix on disk. Naming a single file
        left the next one undeclared and unnoticed: `jinja_ssti_facts_test.py` was added with 6
        tests that no number in this document accounted for. Discovered from disk, so a new
        matrix cannot be added without declaring it here."""
        text = self.COVERAGE.read_text(encoding="utf-8")
        nested_files = sorted(
            (self.TESTS / "examples").rglob("*_test.py"),
            key=lambda p: p.name)
        nested_files = [p for p in nested_files if p.suffix == ".py"
                        and p.name.endswith("_test.py")
                        and "python" in p.parts]  # only pytest-collectable Python matrices
        self.assertTrue(nested_files, "expected at least one nested Python matrix")
        declared_total = 0
        for path in nested_files:
            actual = self._count_tests(path)
            declared_total += actual
            m = re.search(rf"{re.escape(path.name)}` adds (\d+) more:", text)
            self.assertIsNotNone(
                m, f"COVERAGE.md must state how many tests {path.name} adds "
                   f"(it defines {actual})")
            self.assertEqual(actual, int(m.group(1)),
                             f"COVERAGE.md says {m.group(1)} for {path.name}, the file defines "
                             f"{actual}")
        total = sum(self._count_tests(self.TESTS / mod) for mod in self.LAYER_LABELS.values())
        m2 = re.search(r"collects it directly and reports (\d+)\.", text)
        self.assertIsNotNone(m2, "COVERAGE.md must state pytest's direct collection count")
        self.assertEqual(total + declared_total, int(m2.group(1)),
                         "COVERAGE.md's pytest-collection number disagrees with layer total + "
                         "every nested matrix's count")


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


class TestCoverageSyncScript(unittest.TestCase):
    """The sync script regenerates COVERAGE.md's counts, and had no test that could fire.

    A mutation reverting it from *discovering* nested matrices to *listing* one filename
    survived: the accuracy guard reads COVERAGE.md against disk, and COVERAGE.md was already
    correct, so nothing exercised the generator. An `assert` with no test that trips it is not
    a check — so the script's own contract is asserted here."""

    SYNC = SKILL_DIR / "scripts" / "sync_coverage_counts.py"
    TESTS = SKILL_DIR / "scripts" / "tests"

    def _module(self):
        spec = importlib.util.spec_from_file_location("security_review_sync_counts", self.SYNC)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
        return mod

    def test_check_mode_reports_the_document_as_current(self) -> None:
        """`--check` is the CI half. If it is red, COVERAGE.md is stale on disk."""
        proc = subprocess.run([sys.executable, str(self.SYNC), "--check"],
                              capture_output=True, text=True, timeout=120)
        self.assertEqual(0, proc.returncode,
                         f"COVERAGE.md counts are stale; run the sync script:\n"
                         f"{proc.stdout}{proc.stderr}")

    def test_nested_matrices_are_discovered_from_disk(self) -> None:
        found = {p.name for p in self._module().nested_matrices()}
        on_disk = {p.name for p in (self.TESTS / "examples" / "python").glob("*_test.py")}
        self.assertTrue(on_disk, "expected nested Python matrices on disk")
        self.assertEqual(on_disk, found,
                         "the sync script must discover every nested matrix, not list one — "
                         "a hardcoded filename left the next matrix unaccounted for")

    def test_an_undeclared_nested_matrix_is_refused(self) -> None:
        """The generator must fail loudly rather than silently write a total that omits a
        matrix COVERAGE.md never declared."""
        extra = self.TESTS / "examples" / "python" / "zz_probe_facts_test.py"
        extra.write_text("import unittest\n\n\nclass T(unittest.TestCase):\n"
                         "    def test_probe(self):\n        pass\n", encoding="utf-8")
        self.addCleanup(extra.unlink)
        proc = subprocess.run([sys.executable, str(self.SYNC), "--check"],
                              capture_output=True, text=True, timeout=120)
        self.assertNotEqual(0, proc.returncode,
                            "an undeclared nested matrix must be refused")
        self.assertIn("does not declare nested matrix", proc.stdout + proc.stderr)


class TestImpactEvidenceSeparation(unittest.TestCase):
    """A review found the Java deserialization golden answer rating the finding P0 /
    `confirmed` while the same report recorded "whether a known gadget library is on the
    classpath is unresolved".

    The `confirmed` label was defensible — SKILL.md defines it as the vulnerable PATH proven
    from code, and § Active Verification says static proof suffices. What was missing was a
    rule separating that from the maximum IMPACT: the title and Impact line asserted achieved
    RCE in the indicative, which this review did not establish. Severity does not move for an
    unverified aggravating condition in either direction; the impact wording must."""

    SKILL = SKILL_MD
    ANTI = SKILL_DIR / "references" / "anti-examples.md"
    JAVA_REF = SKILL_DIR / "references" / "lang-java.md"
    GOLDEN = (SKILL_DIR / "scripts" / "tests" / "forward_eval" /
              "java_deserialization_true_positive" / "good.md")

    def _confidence_section(self) -> str:
        text = self.SKILL.read_text(encoding="utf-8")
        start = text.index("## Evidence Confidence")
        return text[start:text.index("## False-Positive Suppression Rules", start)]

    def test_confidence_covers_the_path_not_the_maximum_impact(self) -> None:
        section = self._confidence_section()
        self.assertIn("covers the vulnerable path, not the maximum impact", section)
        self.assertIn("assessed", section)

    def test_the_rule_names_what_must_accompany_an_assessed_impact(self) -> None:
        section = self._confidence_section()
        self.assertIn("name the unverified", section)
        self.assertRegex(section, r"(?i)list the check that would settle it")

    def test_the_three_axes_are_stated_separately(self) -> None:
        """A review found the rule ("an unverified aggravating condition does not lower the
        severity") contradicting the grader (which accepted a downgrade for exactly that
        condition). The rule now separates the axes so both can be right."""
        section = self._confidence_section()
        for axis in ("**Severity**", "**Evidence**", "**Impact basis**"):
            self.assertIn(axis, section, f"§ Evidence Confidence must name the {axis} axis")
        self.assertIn("demonstrated`/`assessed", section)

    def test_uncertainty_routes_to_the_axis_it_belongs_to(self) -> None:
        """The distinction that resolves the contradiction: uncertain REACHABILITY may lower
        severity; an uncertain AGGRAVATING condition may not."""
        section = self._confidence_section()
        self.assertRegex(section, r"(?s)Uncertain \*\*reachability.*?may lower\s*\n?\s*the "
                                  r"\*\*severity\*\*")
        self.assertRegex(section, r"(?s)Uncertain \*\*aggravating\*\* condition.*?severity "
                                  r"does \*\*not\*\* move")
        self.assertIn("Absence of a known", section)

    def test_confirmed_may_not_be_reinterpreted_to_keep_a_conclusion(self) -> None:
        section = self._confidence_section()
        self.assertIn("Do not reinterpret `confirmed` to keep a conclusion", section)
        self.assertIn("`confirmed` + `assessed`", section)

    def test_anti_example_five_exists_and_shows_the_split(self) -> None:
        anti = self.ANTI.read_text(encoding="utf-8")
        self.assertIn("AE-5: Demonstrated Impact Asserted From an Unverified Condition", anti)
        self.assertIn("`Confirmed`", anti)
        self.assertIn("Assessed (not demonstrated here)", anti)
        self.assertIn("mvn dependency:tree", anti)

    def test_the_golden_answer_separates_established_from_assessed(self) -> None:
        """The exemplar has to demonstrate the rule; it was the report that broke it."""
        good = self.GOLDEN.read_text(encoding="utf-8")
        self.assertIn("Impact — established here", good)
        self.assertIn("Impact — assessed, not demonstrated by this review", good)
        self.assertIn("What would move the RCE impact from assessed to demonstrated", good)
        # And the severity is still P0 with its basis stated, not hedged away.
        self.assertRegex(good, r"(?m)^> - \*\*Severity\*\*: P0 Critical")

    def test_the_golden_answer_title_does_not_assert_achieved_rce(self) -> None:
        """Round 1 split the Impact lines and left the TITLE saying "Remote code execution
        via ...". The headline is the part most readers keep, and it was still asserting the
        consequence the review could not establish."""
        good = self.GOLDEN.read_text(encoding="utf-8")
        title = next(l for l in good.splitlines() if l.startswith("> **SEC-001:"))
        self.assertNotRegex(
            title, r"(?i)remote code execution",
            f"the finding title asserts the assessed consequence as the headline: {title}")
        self.assertRegex(title, r"(?i)deserializ", f"the title must still name the class: {title}")

    def test_the_golden_answer_scopes_the_unfiltered_claim(self) -> None:
        """The report listed JEP 290 filter configuration as unresolved in § 4 while the
        Confidence line said the path reaches `readObject()` "with no filter" — a claim about
        the JVM, from evidence about one class."""
        good = self.GOLDEN.read_text(encoding="utf-8")
        flat = re.sub(r"\s*\n>?\s*", " ", good)
        self.assertIn("No per-stream filter is set *in the code under review*", flat)
        self.assertIn('"unfiltered" is asserted of this class, not of the JVM', flat)

    def test_the_schema_declares_the_impact_basis_axis(self) -> None:
        """The third axis has to be machine-readable, or a CI consumer cannot tell a
        demonstrated impact from an assessed one."""
        schema = json.loads(
            (SKILL_DIR / "references" / "report-schema.json").read_text(encoding="utf-8"))
        props = schema["properties"]["findings"]["items"]["properties"]
        self.assertIn("impact_basis", props)
        self.assertEqual(["demonstrated", "assessed"], props["impact_basis"]["enum"])
        self.assertIn("impact_condition", props)
        for field in ("impact_basis", "impact_condition"):
            self.assertGreater(len(props[field].get("description", "")), 80,
                               f"{field} needs a definition, not just a name")

    def test_the_golden_answer_states_impact_that_needs_no_gadget(self) -> None:
        """The reason P0 survives the unverified condition: arbitrary Serializable
        instantiation and unbounded graph expansion are established from the code alone. Without
        this the rating would rest on the very assumption the review could not check."""
        good = self.GOLDEN.read_text(encoding="utf-8")
        self.assertIn("Independent of any known gadget", good,
                      "the golden answer must state the impact that needs no gadget")
        # Wrap-tolerant: the exemplar is a blockquote, so a wrapped phrase is split by a
        # newline AND a `>` continuation marker. Collapsing whitespace alone leaves the `>`
        # inside the phrase — the first version of this assertion failed on exactly that.
        flat = re.sub(r"\s*\n>?\s*", " ", good)
        self.assertRegex(flat, r"(?i)unbounded graph expansion",
                         "the no-gadget impact must name unbounded graph expansion")

    def test_the_java_reference_tables_what_the_code_does_and_does_not_establish(self) -> None:
        ref = self.JAVA_REF.read_text(encoding="utf-8")
        self.assertIn("What is established from the code, and what is not", ref)
        self.assertIn("not** established by the code", ref)

    def test_the_jep290_filter_api_is_version_gated(self) -> None:
        """Verified by execution on this repo's toolchain (JDK 1.8.0_461): `javac` rejects
        `java.io.ObjectInputFilter` outright. Recommending the Java 9 call to a Java 8 service
        is advice that does not build."""
        ref = self.JAVA_REF.read_text(encoding="utf-8")
        self.assertIn("does not exist", ref)
        self.assertIn("jdk.serialFilter", ref)
        self.assertIn("sun.misc.ObjectInputFilter", ref)
        self.assertIn("1.8.0_461", ref)
        good = self.GOLDEN.read_text(encoding="utf-8")
        self.assertIn("Java 9+", good)
        self.assertIn("jdk.serialFilter", good)

    def test_the_filter_is_labelled_a_mitigation_not_a_fix(self) -> None:
        for path in (self.JAVA_REF, self.GOLDEN):
            with self.subTest(path=path.name):
                self.assertIn("mitigation", path.read_text(encoding="utf-8"))


class TestSSTIAutoescapeIsNotASandbox(unittest.TestCase):
    """A review found the § SSTI "GOOD" example labelled `sandboxed environment with
    autoescape` while constructing a plain `Environment(autoescape=...)` — and with no
    `loader`, so `get_template()` could not have worked either. Autoescape escapes output; it
    does not restrict attribute traversal. Jinja's sandbox is `SandboxedEnvironment`."""

    PY_REF = SKILL_DIR / "references" / "lang-python.md"

    def _ssti_section(self) -> str:
        text = self.PY_REF.read_text(encoding="utf-8")
        start = text.index("### SSTI")
        return text[start:text.index("### TLS Configuration", start)]

    def test_the_section_states_autoescape_is_not_a_sandbox(self) -> None:
        section = self._ssti_section()
        self.assertIn("`autoescape` is not a sandbox", section)

    @staticmethod
    def _code_blocks(section: str):
        """Yield each fenced code block's body. The unit of analysis has to be the block, not
        the line: the original defect put `# GOOD: sandboxed environment with autoescape` on
        the comment line ABOVE `env = Environment(autoescape=...)`, so a same-line scan — the
        first version of this guard — reproduced the defect and missed it. A mutation run
        caught that."""
        inside, buf = False, []
        for line in section.splitlines():
            if line.lstrip().startswith("```"):
                if inside:
                    yield "\n".join(buf)
                    buf = []
                inside = not inside
                continue
            if inside:
                buf.append(line)
        if buf:
            yield "\n".join(buf)

    def test_no_code_block_calls_a_plain_environment_sandboxed(self) -> None:
        """A block that advertises a sandbox must construct `SandboxedEnvironment`.

        The anti-vacuity assertion is that the scan REACHED the sandbox-labelled blocks — not
        that one of them constructs a plain Environment, which is the defect itself. Getting
        that backwards made the first version of this guard fail on correct content."""
        sandbox_blocks = [b for b in self._code_blocks(self._ssti_section())
                          if re.search(r"(?i)sandbox", b)]
        self.assertTrue(sandbox_blocks,
                        "anti-vacuity: the scan found no § SSTI block mentioning a sandbox")
        for block in sandbox_blocks:
            if not re.search(r"(?<![.\w])Environment\(", block):
                continue  # names the sandbox but constructs nothing — nothing to mislabel
            self.assertIn(
                "SandboxedEnvironment(", block,
                "a § SSTI code block advertises a sandbox while constructing a plain "
                f"Environment:\n{block}")

    def test_the_untrusted_template_path_uses_the_real_sandbox(self) -> None:
        section = self._ssti_section()
        self.assertIn("from jinja2.sandbox import SandboxedEnvironment", section)

    def test_every_get_template_block_configures_a_loader(self) -> None:
        """`Environment()` with no loader cannot serve `get_template()`, so a snippet without
        one is not a working control.

        Scoped to the block that makes the call. Asserting `"FileSystemLoader" in section` was
        satisfied by the IMPORT line alone: a mutation deleting the actual
        `loader=FileSystemLoader(...)` argument left the guard green."""
        checked = 0
        for block in self._code_blocks(self._ssti_section()):
            if "get_template(" not in block:
                continue
            checked += 1
            self.assertRegex(
                block, r"loader\s*=",
                f"a § SSTI block calls get_template() with no loader configured:\n{block}")
        self.assertGreater(checked, 0,
                           "anti-vacuity: no § SSTI block calls get_template at all")

    def test_the_sandbox_resource_table_is_specific_and_correct(self) -> None:
        """The first version claimed `range(10**9)` "still runs" in the sandbox. It does not:
        `range` is replaced by `safe_range`, capped at `MAX_RANGE = 100_000`. The conclusion
        was right and the example was wrong — so the section must now name the bound that
        DOES exist alongside the ones that do not, and must not deny resource limits wholesale."""
        section = self._ssti_section()
        self.assertIn("safe_range", section)
        self.assertIn("MAX_RANGE", section)
        self.assertIn("intercepted_binops", section)
        self.assertRegex(section, r"(?i)nested loops")
        self.assertIn("Do **not** write that the sandbox has no resource limits at all",
                      section)
        # And the retired claim must not come back.
        self.assertNotRegex(section, r"range\(10\*\*9\)[^|]*still runs")

    def test_the_section_gives_a_review_verdict_per_case(self) -> None:
        """A reviewer needs the decision, not just the fixed code: which of the two cases
        applies decides whether "autoescape is on" answers the finding."""
        section = self._ssti_section()
        self.assertIn("Review rule", section)
        self.assertIn("Not SSTI", section)
        self.assertRegex(section, r"(?i)do not call it closed")


class TestRunNumbersAreNotReadAsDetectionRates(unittest.TestCase):
    """A review warned that `1 / 8` must not be read as a 12.5% detection rate: most of those
    failures were report-format defects on scenarios that had detected their vulnerability."""

    LIVE = (SKILL_DIR / "scripts" / "tests" / "forward_eval" / "LIVE_RESULTS.md")
    EVAL = SKILL_DIR / "scripts" / "tests" / "test_forward_eval.py"

    def test_the_record_states_what_the_number_is_not(self) -> None:
        text = self.LIVE.read_text(encoding="utf-8")
        self.assertIn("fully-compliant-report rate, not a detection rate", text)

    def test_the_record_documents_every_grader_category(self) -> None:
        text = self.LIVE.read_text(encoding="utf-8")
        source = self.EVAL.read_text(encoding="utf-8")
        m = re.search(r"CATEGORIES = \(([^)]*)\)", source)
        self.assertIsNotNone(m, "test_forward_eval.py must declare CATEGORIES")
        names = re.findall(r"\b(DETECTION|SUPPRESSION|CALIBRATION|INTEGRITY|CONTRACT)\b",
                           m.group(1))
        self.assertEqual(5, len(names), names)
        for name in names:
            # A table ROW, not any backticked mention: the first version of this guard was
            # satisfied by the prose sentence "the `asvs: TBD` cases are `calibration`, not
            # detection" — so deleting the row that explains the category left it green. A
            # mutation run caught that.
            row = re.search(rf"(?m)^\|\s*`{name.lower()}`\s*\|\s*(.+?)\s*\|\s*$", text)
            self.assertIsNotNone(
                row, f"LIVE_RESULTS.md must carry a table row explaining the "
                     f"{name.lower()} category")
            self.assertGreater(len(row.group(1)), 15,
                               f"the {name.lower()} row must say what it measures")

    def test_the_record_requires_future_runs_to_report_the_breakdown(self) -> None:
        text = self.LIVE.read_text(encoding="utf-8")
        self.assertIn("rather than a bare", text)
        self.assertIn("summarize()", text)

    def test_the_record_states_the_grader_changes_since_run_4(self) -> None:
        """A run's numbers are only comparable if what changed between runs is recorded."""
        text = self.LIVE.read_text(encoding="utf-8")
        self.assertIn("impact_basis", text)
        self.assertIn("scoped to the claim", text)
        self.assertIn("Severity is exact again", text)
        self.assertIn("Validation precedes grading", text)

    def test_the_record_refuses_to_infer_outcomes_from_the_instrument(self) -> None:
        """Three consecutive rounds fixed the instrument. The record must say that this
        licenses no claim about the thing being measured."""
        text = self.LIVE.read_text(encoding="utf-8")
        self.assertIn("A grader that stops crashing is not a reviewer that stops erring",
                      text)
        self.assertRegex(text, r"(?i)unsupported until Run 5 exists")

    def test_the_record_separates_instrument_change_from_outcome_change(self) -> None:
        """A bigger green offline suite is not a better reviewer. The record must say which
        column each claim belongs in, and that the right-hand one needs a live run."""
        text = self.LIVE.read_text(encoding="utf-8")
        self.assertIn("What the offline work does and does not establish", text)
        self.assertIn("| Established | Not established |", text)
        self.assertIn("the measuring instrument\nchanged", text)
        self.assertRegex(text, r"(?i)categories explain results; they do not improve")


if __name__ == "__main__":
    unittest.main()
