"""Contract tests for go-dependency-audit SKILL.md.

Validates that required sections, rules, gates, scorecard tiers, and
output contract fields exist in SKILL.md and reference files.
NOT testing LLM behavior — only verifies rule surface is present.
"""

import pathlib
import re

import pytest

SKILL_DIR = pathlib.Path(__file__).resolve().parents[2]
SKILL_MD = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
SKILL_LOWER = SKILL_MD.lower()
REFS_DIR = SKILL_DIR / "references"


def _ref(name: str) -> str:
    return (REFS_DIR / name).read_text(encoding="utf-8")


def _all_text() -> str:
    parts = [SKILL_MD]
    for f in sorted(REFS_DIR.glob("*.md")):
        parts.append(f.read_text(encoding="utf-8"))
    return "\n".join(parts)


# ──────────────────────────────────────────────────────────────────────
class TestFrontmatter:
    """Validate YAML frontmatter fields."""

    @pytest.fixture(autouse=True)
    def _front(self):
        m = re.search(r"^---\n(.*?)\n---", SKILL_MD, re.DOTALL)
        assert m, "YAML frontmatter block not found"
        self.front = m.group(1)

    def test_name_is_go_dependency_audit(self):
        assert "name: go-dependency-audit" in self.front

    def test_description_covers_triggers(self):
        desc = self.front.lower()
        for kw in ("govulncheck", "license", "cve", "supply chain",
                    "upgrade", "go.mod"):
            assert kw in desc, f"description missing trigger keyword: {kw}"

    def test_allowed_tools_present(self):
        assert "allowed-tools:" in self.front

    def test_allowed_tools_includes_govulncheck(self):
        assert "govulncheck" in self.front

    def test_allowed_tools_includes_go_mod(self):
        assert "go mod" in self.front


# ──────────────────────────────────────────────────────────────────────
class TestMandatoryGates:
    """Validate S2 Mandatory Gates."""

    def test_gates_section_exists(self):
        assert "## 2 Mandatory Gates" in SKILL_MD

    def test_gate_1_module_discovery(self):
        assert "Gate 1: Module Discovery" in SKILL_MD
        assert "go.mod" in SKILL_MD

    def test_gate_2_tool_availability(self):
        assert "Gate 2: Tool Availability" in SKILL_MD
        assert "govulncheck" in SKILL_MD

    def test_gate_3_dependency_graph(self):
        assert "Gate 3: Dependency Graph Completeness" in SKILL_MD
        assert "go mod verify" in SKILL_MD

    def test_gate_4_scope_classification(self):
        assert "Gate 4: Scope Classification" in SKILL_MD
        for mode in ("Quick", "Standard", "Deep"):
            assert mode in SKILL_MD, f"mode {mode} missing from Gate 4"

    def test_gate_5_output_completeness(self):
        assert "Gate 5: Output Completeness" in SKILL_MD

    def test_stop_semantics(self):
        count = SKILL_MD.count("STOP")
        assert count >= 4, f"STOP appears {count} times, expected >= 4"


# ──────────────────────────────────────────────────────────────────────
class TestDepthSelection:
    """Validate S3 Depth Selection."""

    def test_three_depths(self):
        for depth in ("### Quick", "### Standard", "### Deep"):
            assert depth in SKILL_MD, f"depth heading missing: {depth}"

    def test_standard_is_default(self):
        assert "Standard (default)" in SKILL_MD

    def test_force_standard_conditions(self):
        assert "Force Standard if" in SKILL_MD

    def test_force_deep_conditions(self):
        assert "Force Deep if" in SKILL_MD

    def test_reference_loading_by_depth(self):
        for ref in ("govulncheck-patterns.md", "license-compliance.md",
                     "upgrade-planning.md", "supply-chain-security.md"):
            assert ref in SKILL_MD, f"reference {ref} not mentioned"


# ──────────────────────────────────────────────────────────────────────
class TestDegradationModes:
    """Validate S4 Degradation Modes."""

    def test_five_modes_defined(self):
        for mode in ("Full", "Manual", "Degraded", "Planning", "Partial"):
            assert mode in SKILL_MD, f"degradation mode {mode} not found"

    def test_table_has_can_cannot(self):
        assert "Can Deliver" in SKILL_MD
        assert "Cannot Claim" in SKILL_MD

    def test_never_fabricate_cve(self):
        assert "Never fabricate CVE findings" in SKILL_MD

    def test_never_claim_without_scanning(self):
        assert 'Never claim "no vulnerabilities" without scanning' in SKILL_MD

    def test_degraded_output_marker(self):
        assert "# DEGRADED:" in SKILL_MD


# ──────────────────────────────────────────────────────────────────────
class TestAuditChecklist:
    """Validate S5 Dependency Audit Checklist."""

    def test_five_subsections(self):
        for sub in ("5.1 CVE Scanning", "5.2 License Compliance",
                     "5.3 Upgrade Planning", "5.4 Supply Chain Security",
                     "5.5 Module Hygiene"):
            assert sub in SKILL_MD, f"subsection {sub} missing"

    def test_cve_scanning_items(self):
        assert "govulncheck in source mode is primary" in SKILL_MD
        assert "Source mode confirms reachability" in SKILL_MD
        assert "Transitive CVEs need triage" in SKILL_MD

    def test_license_items(self):
        assert "Categorize licenses by risk" in SKILL_MD
        assert "Transitive licenses propagate" in SKILL_MD

    def test_upgrade_items(self):
        assert "Semantic versioning drives risk assessment" in SKILL_MD
        assert "+incompatible" in SKILL_MD

    def test_supply_chain_items(self):
        assert "go.sum is your integrity anchor" in SKILL_MD
        assert "GOPROXY configuration matters" in SKILL_MD
        assert "GOPRIVATE for internal modules" in SKILL_MD

    def test_hygiene_items(self):
        assert "go mod tidy" in SKILL_LOWER
        assert "replace" in SKILL_LOWER
        assert "circular dependencies" in SKILL_LOWER

    def test_total_checklist_count(self):
        numbered = re.findall(r"^\d+\.\s+\*\*", SKILL_MD, re.MULTILINE)
        assert len(numbered) >= 20, f"found {len(numbered)} items, expected >= 20"


# ──────────────────────────────────────────────────────────────────────
class TestSeverityModel:
    """Validate S6 Severity Model."""

    def test_four_severity_levels(self):
        for level in ("### P0 Critical", "### P1 High",
                       "### P2 Medium", "### P3 Low"):
            assert level in SKILL_MD, f"severity level missing: {level}"

    def test_p0_includes_cvss(self):
        # P0 section should mention CVSS >= 9.0
        assert "CVSS >= 9.0" in SKILL_MD or "CVSS >= 9" in SKILL_MD

    def test_p0_requires_reachability(self):
        assert "reachable" in SKILL_LOWER

    def test_p1_includes_license(self):
        # P1 should mention license violations
        p1_section = SKILL_MD[SKILL_MD.index("### P1 High"):]
        p1_end = p1_section.index("### P2 Medium")
        p1_text = p1_section[:p1_end].lower()
        assert "license" in p1_text or "gpl" in p1_text


# ──────────────────────────────────────────────────────────────────────
class TestAntiExamples:
    """Validate S7 Anti-Examples."""

    def test_six_anti_examples(self):
        for i in range(1, 7):
            assert f"AE-{i}" in SKILL_MD, f"AE-{i} not found"

    def test_ae1_reachability(self):
        assert "Reporting every CVE without checking reachability" in SKILL_MD

    def test_ae2_transitive_licenses(self):
        assert "Ignoring transitive dependency licenses" in SKILL_MD

    def test_ae3_go_get_u(self):
        assert "go get -u" in SKILL_MD

    def test_ae4_replace_committed(self):
        assert "replace" in SKILL_LOWER

    def test_ae5_no_scan(self):
        assert 'Claiming "no vulnerabilities" without running govulncheck' in SKILL_MD

    def test_ae6_incompatible(self):
        assert "+incompatible" in SKILL_MD

    def test_wrong_right_pairs(self):
        wrong_count = SKILL_MD.count("# WRONG")
        right_count = SKILL_MD.count("# RIGHT")
        assert wrong_count >= 6, f"found {wrong_count} # WRONG, expected >= 6"
        assert right_count >= 6, f"found {right_count} # RIGHT, expected >= 6"


# ──────────────────────────────────────────────────────────────────────
class TestScorecard:
    """Validate S8 Dependency Audit Scorecard."""

    def test_scorecard_section_exists(self):
        assert "## 8 Dependency Audit Scorecard" in SKILL_MD

    def test_critical_tier_3_items(self):
        assert "govulncheck executed" in SKILL_MD
        assert "No reachable P0 CVEs" in SKILL_MD
        assert "go.mod/go.sum integrity verified" in SKILL_MD

    def test_standard_tier_5_items(self):
        for item in ("No reachable P1 CVEs", "License compliance checked",
                      "No +incompatible direct dependencies",
                      "GOPROXY and GOPRIVATE configured"):
            assert item in SKILL_MD, f"standard item missing: {item}"

    def test_hygiene_tier_4_items(self):
        for item in ("go.mod is tidy", "No unnecessary replace directives",
                      "Circular dependencies absent", "go.work not committed"):
            assert item in SKILL_MD, f"hygiene item missing: {item}"

    def test_passing_criteria(self):
        assert "3/3" in SKILL_MD
        assert "4/5" in SKILL_MD
        assert "3/4" in SKILL_MD

    def test_verdict_format(self):
        assert "PASS" in SKILL_MD
        assert "FAIL" in SKILL_MD


# ──────────────────────────────────────────────────────────────────────
class TestOutputContract:
    """Validate S9 Output Contract."""

    def test_nine_sections(self):
        for i in range(1, 10):
            assert f"9.{i}" in SKILL_MD, f"output section 9.{i} missing"

    def test_audit_context(self):
        assert "Audit Context" in SKILL_MD

    def test_mode_and_depth(self):
        assert "Mode & Depth" in SKILL_MD
        assert "Quick | Standard | Deep" in SKILL_MD

    def test_cve_scan_results(self):
        assert "CVE Scan Results" in SKILL_MD

    def test_license_summary(self):
        assert "License Summary" in SKILL_MD

    def test_outdated_dependencies(self):
        assert "Outdated Dependencies" in SKILL_MD

    def test_supply_chain_posture(self):
        assert "Supply Chain Posture" in SKILL_MD

    def test_upgrade_recommendations(self):
        assert "Upgrade Recommendations" in SKILL_MD

    def test_uncovered_risks(self):
        assert "Uncovered Risks" in SKILL_MD
        assert "never empty" in SKILL_LOWER

    def test_machine_readable_summary(self):
        assert "Machine-Readable Summary" in SKILL_MD
        assert "json" in SKILL_LOWER

    def test_scorecard_appended(self):
        assert "Scorecard appended" in SKILL_MD


# ──────────────────────────────────────────────────────────────────────
class TestReferenceFiles:
    """Validate reference file existence and content."""

    def test_govulncheck_patterns_exists(self):
        assert (REFS_DIR / "govulncheck-patterns.md").exists()

    def test_license_compliance_exists(self):
        assert (REFS_DIR / "license-compliance.md").exists()

    def test_upgrade_planning_exists(self):
        assert (REFS_DIR / "upgrade-planning.md").exists()

    def test_supply_chain_security_exists(self):
        assert (REFS_DIR / "supply-chain-security.md").exists()

    def test_skill_references_all_files(self):
        for name in ("govulncheck-patterns.md", "license-compliance.md",
                      "upgrade-planning.md", "supply-chain-security.md"):
            assert name in SKILL_MD, f"SKILL.md does not reference {name}"

    def test_govulncheck_has_source_mode(self):
        text = _ref("govulncheck-patterns.md").lower()
        assert "source mode" in text

    def test_govulncheck_has_triage_tree(self):
        text = _ref("govulncheck-patterns.md").lower()
        assert "triage" in text

    def test_license_has_categories(self):
        text = _ref("license-compliance.md").lower()
        for cat in ("permissive", "copyleft", "gpl"):
            assert cat in text, f"license-compliance missing: {cat}"

    def test_upgrade_has_semver(self):
        text = _ref("upgrade-planning.md").lower()
        assert "semantic versioning" in text or "semver" in text

    def test_supply_chain_has_gosum(self):
        text = _ref("supply-chain-security.md").lower()
        assert "go.sum" in text


# ──────────────────────────────────────────────────────────────────────
class TestLineCount:
    """SKILL.md must stay within the line budget."""

    def test_skill_md_under_line_budget(self):
        lines = SKILL_MD.count("\n") + 1
        assert lines <= 420, f"SKILL.md is {lines} lines (budget: 420)"


# ──────────────────────────────────────────────────────────────────────
class TestCrossFileConsistency:
    """Key terms must appear in both SKILL.md and relevant references."""

    @pytest.fixture(autouse=True)
    def _load_refs(self):
        self.govulncheck = _ref("govulncheck-patterns.md").lower()
        self.license = _ref("license-compliance.md").lower()
        self.upgrade = _ref("upgrade-planning.md").lower()
        self.supply_chain = _ref("supply-chain-security.md").lower()

    def test_govulncheck_in_skill_and_ref(self):
        assert "govulncheck" in SKILL_LOWER
        assert "govulncheck" in self.govulncheck

    def test_cvss_in_skill_and_govulncheck(self):
        assert "cvss" in SKILL_LOWER
        assert "cvss" in self.govulncheck

    def test_gpl_in_skill_and_license(self):
        assert "gpl" in SKILL_LOWER
        assert "gpl" in self.license

    def test_goprivate_in_skill_and_supply_chain(self):
        assert "goprivate" in SKILL_LOWER
        assert "goprivate" in self.supply_chain

    def test_incompatible_in_skill_and_upgrade(self):
        assert "+incompatible" in SKILL_LOWER
        assert "+incompatible" in self.upgrade

    def test_replace_in_skill_and_upgrade(self):
        assert "replace" in SKILL_LOWER
        assert "replace" in self.upgrade

    # --- Minimum substantive content ---

    def test_govulncheck_patterns_min_lines(self):
        lines = _ref("govulncheck-patterns.md").count("\n") + 1
        assert lines >= 200, f"govulncheck-patterns has {lines} lines, need >= 200"

    def test_license_compliance_min_lines(self):
        lines = _ref("license-compliance.md").count("\n") + 1
        assert lines >= 150, f"license-compliance has {lines} lines, need >= 150"

    def test_upgrade_planning_min_lines(self):
        lines = _ref("upgrade-planning.md").count("\n") + 1
        assert lines >= 200, f"upgrade-planning has {lines} lines, need >= 200"

    def test_supply_chain_min_lines(self):
        lines = _ref("supply-chain-security.md").count("\n") + 1
        assert lines >= 200, f"supply-chain-security has {lines} lines, need >= 200"