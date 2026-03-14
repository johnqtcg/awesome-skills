import re
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[2]
SKILL_MD = SKILL_DIR / "SKILL.md"
API_REF = SKILL_DIR / "references" / "go-api-http-checklist.md"


def frontmatter(text: str) -> str:
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        raise AssertionError("missing yaml frontmatter")
    return match.group(1)


class GoCodeReviewerSkillContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skill_text = SKILL_MD.read_text()
        cls.api_ref_text = API_REF.read_text()

    # ------------------------------------------------------------------
    # Frontmatter
    # ------------------------------------------------------------------

    def test_frontmatter_name_is_hyphen_case(self) -> None:
        fm = frontmatter(self.skill_text)
        name_match = re.search(r"^name:\s*(.+)$", fm, re.MULTILINE)
        self.assertIsNotNone(name_match, "missing name in frontmatter")
        name = name_match.group(1).strip()
        self.assertEqual("go-code-reviewer", name)
        self.assertRegex(name, r"^[a-z0-9-]+$")

    # HTTP body rules (server vs client)
    # ------------------------------------------------------------------

    def test_http_body_rule_is_server_client_aware(self) -> None:
        self.assertIn("avoid requiring explicit `r.Body.Close()`", self.skill_text)
        self.assertIn("require `resp.Body.Close()`", self.skill_text)
        self.assertIn(
            "Do not treat missing `r.Body.Close()` in server handlers as an automatic defect.",
            self.api_ref_text,
        )
        self.assertIn("`resp.Body.Close()` is called on all success/error paths", self.api_ref_text)

    # ------------------------------------------------------------------
    # Tool coverage strategy
    # ------------------------------------------------------------------

    def test_tool_coverage_strategy_is_config_aware(self) -> None:
        self.assertIn(
            "Only mark `go vet` / `staticcheck` as covered when they are explicitly enabled by config.",
            self.skill_text,
        )
        self.assertIn("If coverage is unclear (or linter disabled), run the missing tool directly.", self.skill_text)

    # ------------------------------------------------------------------
    # Execution modes
    # ------------------------------------------------------------------

    def test_execution_modes_are_defined(self) -> None:
        self.assertIn("## Execution Modes (Lite / Standard / Strict)", self.skill_text)
        self.assertIn("Default mode: `Standard`", self.skill_text)
        self.assertIn("### Lite (fast triage)", self.skill_text)
        self.assertIn("### Standard (default balanced review)", self.skill_text)
        self.assertIn("### Strict (release/security gate)", self.skill_text)

    def test_skill_md_stays_within_line_budget(self) -> None:
        lines = len(self.skill_text.splitlines())
        self.assertLessEqual(lines, 500, f"SKILL.md too long: {lines} lines")

    def test_mode_selection_rules_are_present(self) -> None:
        self.assertIn("Choose `Lite` only when scope is small", self.skill_text)
        self.assertIn("Choose `Strict` when any high-risk signal exists", self.skill_text)
        self.assertIn("Use `Standard` for everything else.", self.skill_text)
        self.assertIn("Select review mode (`Lite|Standard|Strict`)", self.skill_text)

    def test_mode_specific_execution_requirements_exist(self) -> None:
        self.assertIn("Lite mode: one static tool minimum.", self.skill_text)
        self.assertIn("Standard mode: config-aware tool strategy.", self.skill_text)
        self.assertIn(
            "Strict mode: `golangci-lint` plus direct `staticcheck`/`go vet` when not explicitly covered.",
            self.skill_text,
        )
        self.assertIn("Strict mode: run `go test ./...` and `go test -race ./...`.", self.skill_text)

    # ------------------------------------------------------------------
    # Original 4 gates
    # ------------------------------------------------------------------

    def test_key_gates_exist(self) -> None:
        for gate in (
            "Execution Integrity Gate",
            "Baseline Comparison Gate",
            "False-Positive Suppression Gate",
            "Risk Acceptance and SLA Gate",
        ):
            self.assertIn(gate, self.skill_text)

    # ------------------------------------------------------------------
    # NEW: Gates 5, 6, 7
    # ------------------------------------------------------------------

    def test_go_version_gate_exists(self) -> None:
        self.assertIn("### 5) Go Version Gate", self.skill_text)
        self.assertIn("Read `go.mod` for the `go` directive", self.skill_text)
        self.assertIn(
            "Do NOT recommend features unavailable at the project's Go version as findings.",
            self.skill_text,
        )

    def test_go_version_gate_has_version_table(self) -> None:
        for feature_keyword in ("Generics", "slog", "atomic.Int64", "iter.Seq"):
            self.assertIn(feature_keyword, self.skill_text)

    def test_generated_code_exclusion_gate_exists(self) -> None:
        self.assertIn("### 6) Generated Code Exclusion Gate", self.skill_text)
        self.assertIn("*.pb.go", self.skill_text)
        self.assertIn("wire_gen.go", self.skill_text)
        self.assertIn("Code generated .* DO NOT EDIT", self.skill_text)

    def test_reference_loading_gate_exists(self) -> None:
        self.assertIn("### 7) Reference Loading Gate", self.skill_text)
        self.assertIn("MUST", self.skill_text)
        self.assertIn("This is mandatory, not advisory.", self.skill_text)

    # ------------------------------------------------------------------
    # NEW: Gate 8 — Change Origin Classification
    # ------------------------------------------------------------------

    def test_change_origin_classification_gate_exists(self) -> None:
        self.assertIn("### 8) Change Origin Classification Gate", self.skill_text)
        for label in ("introduced", "pre-existing", "uncertain"):
            self.assertIn(f"`{label}`", self.skill_text)

    def test_change_origin_actionability_table_exists(self) -> None:
        self.assertIn("Merge-blocking?", self.skill_text)
        self.assertIn("must-fix", self.skill_text)
        self.assertIn("follow-up issue", self.skill_text)

    def test_origin_field_in_output_format(self) -> None:
        self.assertIn("**Origin:** `introduced|pre-existing|uncertain`", self.skill_text)
        self.assertIn("**Action:** `must-fix` | `follow-up issue`", self.skill_text)

    def test_summary_includes_origin_breakdown(self) -> None:
        self.assertIn("origin breakdown", self.skill_text)
        self.assertIn("introduced", self.skill_text)

    def test_workflow_step9_applies_origin_classification(self) -> None:
        self.assertIn("Apply Change Origin Classification Gate", self.skill_text)
        self.assertIn("git blame", self.skill_text)

    # ------------------------------------------------------------------
    # NEW: Database reference trigger
    # ------------------------------------------------------------------

    def test_database_reference_trigger_exists(self) -> None:
        self.assertIn("go-database-patterns.md", self.skill_text)
        self.assertIn("sql.Rows", self.skill_text)

    def test_database_checklist_category_exists(self) -> None:
        self.assertIn("Database & Persistence (High", self.skill_text)

    # ------------------------------------------------------------------
    # NEW: Output example
    # ------------------------------------------------------------------

    def test_output_example_exists(self) -> None:
        self.assertIn("### Example Output (End-to-End)", self.skill_text)
        self.assertIn("REV-001", self.skill_text)
        self.assertIn("Origin:** introduced", self.skill_text)
        self.assertIn("Origin:** pre-existing", self.skill_text)
        self.assertIn("Action:** must-fix", self.skill_text)
        self.assertIn("Action:** follow-up issue", self.skill_text)

    # ------------------------------------------------------------------
    # NEW: Grey-area anti-examples
    # ------------------------------------------------------------------

    def test_grey_area_guidance_exists(self) -> None:
        self.assertIn("Grey-area guidance", self.skill_text)
        self.assertIn("errors.Is` vs `==`", self.skill_text)
        self.assertIn("context.TODO()", self.skill_text)
        self.assertIn("interface{}", self.skill_text)
        self.assertIn("defer f.Close()", self.skill_text)

    # ------------------------------------------------------------------
    # NEW: Workflow enhancements
    # ------------------------------------------------------------------

    def test_workflow_step0_checks_go_version(self) -> None:
        self.assertIn("Check `go.mod` for the project Go version", self.skill_text)
        self.assertIn("Go version: X.Y", self.skill_text)

    def test_workflow_step1_excludes_generated_code(self) -> None:
        self.assertIn("Apply Generated Code Exclusion Gate", self.skill_text)

    def test_workflow_step2_has_diff_boundary_rule(self) -> None:
        self.assertIn("Diff-boundary rule", self.skill_text)
        self.assertIn(
            "Do not audit the entire file for unrelated pre-existing issues.",
            self.skill_text,
        )

    def test_workflow_step3_applies_reference_loading_gate(self) -> None:
        self.assertIn(
            "Apply Reference Loading Gate: load reference files matching trigger patterns",
            self.skill_text,
        )

    def test_workflow_step9_has_merge_rule(self) -> None:
        self.assertIn("Merge rule", self.skill_text)
        self.assertIn("report ONE finding with a location list", self.skill_text)

    def test_workflow_step9_has_volume_cap(self) -> None:
        self.assertIn("Volume cap", self.skill_text)
        for cap in ("5 findings", "10 findings", "15 findings"):
            self.assertIn(cap, self.skill_text)
        self.assertIn("additional lower-priority issues moved to Residual Risk", self.skill_text)

    def test_volume_cap_is_severity_tiered(self) -> None:
        self.assertIn("severity-tiered strategy", self.skill_text)
        self.assertIn("Phase 1 — High", self.skill_text)
        self.assertIn("Phase 2 — Medium", self.skill_text)
        self.assertIn("Phase 3 — Low", self.skill_text)
        self.assertIn("High findings are never dropped by volume cap", self.skill_text)

    def test_residual_risk_captures_volume_overflow(self) -> None:
        self.assertIn("Volume-cap overflow", self.skill_text)
        self.assertIn("no validated issue is silently dropped", self.skill_text)

    # ------------------------------------------------------------------
    # NEW: Expanded anti-examples (15 total)
    # ------------------------------------------------------------------

    def test_anti_examples_count_at_least_15(self) -> None:
        marker = "### Anti-examples (DO NOT report these)"
        start = self.skill_text.index(marker)
        next_heading = self.skill_text.index("\n## ", start + len(marker))
        section = self.skill_text[start:next_heading]
        items = [line for line in section.split("\n") if line.startswith("- \"")]
        self.assertGreaterEqual(
            len(items), 15, f"Expected >= 15 anti-examples, found {len(items)}"
        )

    def test_version_specific_anti_examples_exist(self) -> None:
        self.assertIn("when the project's `go.mod` targets Go < 1.21", self.skill_text)
        self.assertIn("when the project's `go.mod` targets Go < 1.19", self.skill_text)

    def test_errgroup_false_positive_anti_example_exists(self) -> None:
        self.assertIn(
            "when no error propagation is needed and goroutine count is small and fixed",
            self.skill_text,
        )

    def test_context_propagation_anti_example_exists(self) -> None:
        self.assertIn(
            "when the function is synchronous, short-lived, performs no I/O, and has no cancellable work",
            self.skill_text,
        )

    def test_function_too_long_anti_example_exists(self) -> None:
        self.assertIn("table-driven switch", self.skill_text)

    def test_generics_false_positive_anti_example_exists(self) -> None:
        self.assertIn(
            "when only one concrete type is used throughout the codebase",
            self.skill_text,
        )

    # ------------------------------------------------------------------
    # NEW: Output format enhancements
    # ------------------------------------------------------------------

    def test_execution_status_includes_go_version(self) -> None:
        self.assertIn("`Go version`", self.skill_text)

    def test_execution_status_includes_generated_exclusion(self) -> None:
        self.assertIn("`Excluded (generated)`", self.skill_text)

    def test_execution_status_includes_references_loaded(self) -> None:
        self.assertIn("`References loaded`", self.skill_text)

    def test_finding_location_supports_list(self) -> None:
        self.assertIn("or location list for merged findings", self.skill_text)

    def test_residual_risk_includes_preexisting_note(self) -> None:
        self.assertIn(
            "Pre-existing issues (non-High)",
            self.skill_text,
        )
        self.assertIn(
            "pre-existing defects found in impact-radius files (not in the diff)",
            self.skill_text,
        )

    # ------------------------------------------------------------------
    # Original outputexample / no-finding / execution integrity checks
    # ------------------------------------------------------------------

    def test_required_output_sections_exist(self) -> None:
        for section in (
            "### Review Mode",
            "### Findings",
            "### Suppressed Items",
            "### Execution Status",
            "### Risk Acceptance / SLA",
            "### Open Questions",
            "### Residual Risk / Testing Gaps",
            "### Summary",
        ):
            self.assertIn(section, self.skill_text)

    def test_no_finding_contract_mentions_mode_and_execution(self) -> None:
        self.assertIn("No actionable findings found.", self.skill_text)
        self.assertIn("`Review Mode`", self.skill_text)
        self.assertIn("`Execution Status`", self.skill_text)
        self.assertIn("Baseline not found", self.skill_text)

    def test_execution_integrity_requires_not_run_language(self) -> None:
        self.assertIn("Not run in this environment", self.skill_text)
        self.assertIn("exact commands to run", self.skill_text)

    # ------------------------------------------------------------------
    # Appendix is mandatory gate
    # ------------------------------------------------------------------

    def test_appendix_is_mandatory_gate(self) -> None:
        self.assertIn(
            "**This is a mandatory gate**",
            self.skill_text,
        )


if __name__ == "__main__":
    unittest.main()
