import re
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[2]
SKILL_MD = SKILL_DIR / "SKILL.md"
WORKFLOW_GUIDE = SKILL_DIR / "references" / "workflow-quality-guide.md"
PR_CHECKLIST = SKILL_DIR / "references" / "pr-checklist.md"
REPO_SHAPES = SKILL_DIR / "references" / "repository-shapes.md"
ADVANCED = SKILL_DIR / "references" / "github-actions-advanced-patterns.md"
FALLBACK = SKILL_DIR / "references" / "fallback-and-scaffolding.md"
GOLDEN_EXAMPLES = SKILL_DIR / "references" / "golden-examples.md"
GOLDEN_MONOREPO = SKILL_DIR / "references" / "golden-example-monorepo.md"
GOLDEN_SERVICE_CONTAINERS = SKILL_DIR / "references" / "golden-example-service-containers.md"
DISCOVER_SCRIPT = SKILL_DIR / "scripts" / "discover_ci_needs.sh"


def frontmatter(text: str) -> str:
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        raise AssertionError("missing yaml frontmatter")
    return match.group(1)


class GoCIWorkflowSkillContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skill_text = SKILL_MD.read_text()
        cls.wqg_text = WORKFLOW_GUIDE.read_text()
        cls.pr_text = PR_CHECKLIST.read_text()
        cls.rs_text = REPO_SHAPES.read_text()
        cls.gap_text = ADVANCED.read_text()
        cls.fb_text = FALLBACK.read_text()
        cls.ge_text = GOLDEN_EXAMPLES.read_text()
        cls.ge_monorepo_text = GOLDEN_MONOREPO.read_text()
        cls.ge_service_containers_text = GOLDEN_SERVICE_CONTAINERS.read_text()

    @staticmethod
    def count_heading(text: str, title: str) -> int:
        pattern = r"^#{2,3}\s+" + re.escape(title) + r"\s*$"
        return len(re.findall(pattern, text, re.MULTILINE))

    # ------------------------------------------------------------------
    # Frontmatter
    # ------------------------------------------------------------------

    def test_frontmatter_name_and_description(self) -> None:
        fm = frontmatter(self.skill_text)
        self.assertIn("name: go-ci-workflow", fm)
        self.assertIn("GitHub Actions", fm)

    # SKILL.md structure
    # ------------------------------------------------------------------

    def test_priority_and_fallback_exist(self) -> None:
        self.assertIn("## Execution Priority", self.skill_text)
        self.assertIn("controlled inline workflow commands only", self.skill_text)
        self.assertIn("## Mandatory Gates", self.skill_text)
        self.assertIn("Degraded Output Gate", self.skill_text)

    def test_skill_has_5_mandatory_gates(self) -> None:
        for gate in (
            "### 1) Repository Shape Gate",
            "### 2) Local Parity Gate",
            "### 3) Security and Permissions Gate",
            "### 4) Execution Integrity Gate",
            "### 5) Degraded Output Gate",
        ):
            self.assertIn(gate, self.skill_text)

    def test_repository_shape_gate_lists_all_shapes(self) -> None:
        self.assertIn("Repository Shape Gate", self.skill_text)
        for shape in (
            "single-module application",
            "single-module library",
            "multi-module repository",
            "monorepo with multiple apps/packages",
            "Docker-heavy repository",
            "reusable-workflow candidate",
        ):
            self.assertIn(shape, self.skill_text)

    def test_local_parity_gate_has_3_execution_paths(self) -> None:
        for path in ("make target", "repo task", "inline fallback"):
            self.assertIn(f"`{path}`", self.skill_text)

    def test_security_gate_covers_events_and_permissions(self) -> None:
        self.assertIn("pull_request", self.skill_text)
        self.assertIn("push", self.skill_text)
        self.assertIn("workflow_call", self.skill_text)
        self.assertIn("fork PRs can reach secrets", self.skill_text)
        self.assertIn("minimum required `permissions`", self.skill_text)

    def test_execution_integrity_gate_requires_not_run_language(self) -> None:
        self.assertIn("Not run in this environment", self.skill_text)
        self.assertIn("exact commands to run next", self.skill_text)

    def test_output_contract_has_9_fields(self) -> None:
        for field in (
            "changed files",
            "repository shape classification",
            "execution path for each job",
            "trigger configuration",
            "permissions and secret assumptions",
            "tool versions used",
            "missing targets",
            "validation performed",
            "recommended follow-up work",
        ):
            self.assertIn(field, self.skill_text)

    def test_advanced_rules_reference_new_patterns(self) -> None:
        self.assertIn("composite actions", self.skill_text)
        self.assertIn("service containers", self.skill_text)
        self.assertIn("path filters", self.skill_text)

    def test_operating_model_has_5_steps(self) -> None:
        for step in (
            "Inspect repository shape",
            "Decide the honest workflow architecture",
            "Compose workflow YAML",
            "Validate syntax",
            "Report assumptions",
        ):
            self.assertIn(step, self.skill_text)

    def test_skill_references_discover_script(self) -> None:
        self.assertIn("scripts/discover_ci_needs.sh", self.skill_text)

    def test_skill_cross_references_go_makefile_writer(self) -> None:
        self.assertIn("$go-makefile-writer", self.skill_text)

    # ------------------------------------------------------------------
    # Reference files exist
    # ------------------------------------------------------------------

    def test_all_references_and_scripts_exist(self) -> None:
        for path in (
            WORKFLOW_GUIDE, PR_CHECKLIST, REPO_SHAPES,
            ADVANCED, FALLBACK, GOLDEN_EXAMPLES,
            GOLDEN_MONOREPO, GOLDEN_SERVICE_CONTAINERS,
            DISCOVER_SCRIPT,
        ):
            self.assertTrue(path.exists(), f"missing {path.name}")

    # ------------------------------------------------------------------
    # workflow-quality-guide.md (15 sections)
    # ------------------------------------------------------------------

    def test_wqg_has_toc(self) -> None:
        self.assertIn("## Table of Contents", self.wqg_text)

    def test_wqg_has_all_15_sections(self) -> None:
        for section in (
            "## 1. Job Set",
            "## 2. Trigger Strategy",
            "## 3. Go Setup Pattern",
            "## 4. Core Gate Job",
            "## 5. Docker Build Job",
            "## 6. Integration Test Job",
            "## 7. E2E Test Job",
            "## 8. Vulnerability Scanning Job",
            "## 9. Static Analysis Extras",
            "## 10. Caching Strategy",
            "## 11. Tool Installation",
            "## 12. Secret Management",
            "## 13. Matrix Strategy",
            "## 14. Robustness and Anti-Pattern Rules",
            "## 15. Validation Checklist",
        ):
            self.assertIn(section, self.wqg_text, f"missing section: {section}")

    def test_wqg_core_gate_delegates_to_make(self) -> None:
        self.assertIn("make ci COVER_MIN=80", self.wqg_text)
        self.assertIn("Delegate to `make ci`", self.wqg_text)

    def test_wqg_robustness_and_anti_patterns_have_substantive_rules(self) -> None:
        self.assertIn("Robustness:", self.wqg_text)
        self.assertIn("Anti-patterns to avoid:", self.wqg_text)
        for rule in (
            "timeout-minutes",
            "continue-on-error: true",
            "Inline `go test`, `go build` commands instead of `make` targets.",
            "Tool installation with `@latest` in CI.",
            "Missing `concurrency` control",
            "CI behavior that cannot be reproduced locally.",
        ):
            self.assertIn(rule, self.wqg_text)

    def test_wqg_tool_version_currency_note(self) -> None:
        self.assertIn(
            "Versions in this guide are examples current at time of writing",
            self.wqg_text,
        )

    def test_wqg_mentions_monorepo(self) -> None:
        self.assertIn("monorepo", self.wqg_text.lower())

    # ------------------------------------------------------------------
    # github-actions-advanced-patterns.md (9 sections)
    # ------------------------------------------------------------------

    def test_gap_has_all_9_sections(self) -> None:
        for section in (
            "## 1) Permissions",
            "## 2) Fork PR Safety",
            "## 3) Reusable Workflows",
            "## 4) Composite Actions",
            "## 5) Matrix Strategy",
            "## 6) Self-Hosted Runners",
            "## 7) Artifacts and Reports",
            "## 8) Concurrency and Timeouts",
            "## 9) Service Containers",
        ):
            self.assertIn(section, self.gap_text, f"missing section: {section}")

    def test_gap_fork_pr_has_if_condition_yaml(self) -> None:
        self.assertIn(
            "github.event.pull_request.head.repo.full_name == github.repository",
            self.gap_text,
        )

    def test_gap_fork_pr_warns_about_pull_request_target(self) -> None:
        self.assertIn("pull_request_target", self.gap_text)
        self.assertIn("dangerous", self.gap_text.lower())

    def test_gap_permissions_has_github_token_section(self) -> None:
        self.assertIn("GITHUB_TOKEN", self.gap_text)
        self.assertIn("custom PAT or GitHub App token", self.gap_text)

    def test_gap_permissions_has_escalation_table(self) -> None:
        for perm in ("contents: write", "packages: write", "pull-requests: write"):
            self.assertIn(perm, self.gap_text)

    def test_gap_composite_actions_has_comparison_table(self) -> None:
        self.assertIn("Composite Action", self.gap_text)
        self.assertIn("Reusable Workflow", self.gap_text)
        self.assertIn("Step-level sharing", self.gap_text)

    def test_gap_service_containers_has_health_checks(self) -> None:
        self.assertIn("health-cmd", self.gap_text)
        self.assertIn("pg_isready", self.gap_text)
        self.assertIn("redis-cli ping", self.gap_text)

    def test_gap_service_containers_has_common_images_table(self) -> None:
        for db in ("PostgreSQL", "MySQL", "Redis", "Kafka", "MongoDB"):
            self.assertIn(db, self.gap_text, f"missing database: {db}")

    def test_gap_timeout_table_exists(self) -> None:
        self.assertIn("15 min", self.gap_text)
        self.assertIn("20 min", self.gap_text)
        self.assertIn("30 min", self.gap_text)

    # ------------------------------------------------------------------
    # golden examples (2 inline + 2 specialized reference files)
    # ------------------------------------------------------------------

    def test_ge_has_toc(self) -> None:
        self.assertIn("## Table of Contents", self.ge_text)

    def test_ge_has_all_examples_across_split_references(self) -> None:
        for heading in (
            "## 1) Standard Service Repository",
            "## 2) No Makefile Fallback",
        ):
            self.assertIn(heading, self.ge_text, f"missing example: {heading}")
        self.assertIn("golden-example-monorepo.md", self.ge_text)
        self.assertIn("golden-example-service-containers.md", self.ge_text)
        self.assertIn("Golden Example — Monorepo With Multiple Modules", self.ge_monorepo_text)
        self.assertIn(
            "Golden Example — Service With Integration Tests and Service Containers",
            self.ge_service_containers_text,
        )

    def test_ge_each_has_complete_workflow_and_output_summary(self) -> None:
        workflow_count = sum(
            self.count_heading(text, "Complete Workflow")
            for text in (self.ge_text, self.ge_monorepo_text, self.ge_service_containers_text)
        )
        summary_count = sum(
            self.count_heading(text, "Output Summary")
            for text in (self.ge_text, self.ge_monorepo_text, self.ge_service_containers_text)
        )
        self.assertEqual(workflow_count, 4, f"expected 4 Complete Workflow sections, got {workflow_count}")
        self.assertEqual(summary_count, 4, f"expected 4 Output Summary sections, got {summary_count}")

    def test_ge_fallback_has_inline_markers(self) -> None:
        self.assertIn("# INLINE FALLBACK", self.ge_text)
        self.assertIn("Local parity: PARTIAL", self.ge_text)

    def test_ge_service_container_example_has_services_block(self) -> None:
        self.assertIn("services:", self.ge_service_containers_text)
        self.assertIn("mysql:", self.ge_service_containers_text)
        self.assertIn("redis:", self.ge_service_containers_text)

    # ------------------------------------------------------------------
    # repository-shapes.md (6 shapes)
    # ------------------------------------------------------------------

    def test_rs_has_all_6_shapes(self) -> None:
        for heading in (
            "## 1) Single-Module Service",
            "## 2) Single-Module Library",
            "## 3) Multi-Module Repository",
            "## 4) Monorepo",
            "## 5) Docker-Heavy Repository",
            "## 6) No Makefile or Partial Tasking",
        ):
            self.assertIn(heading, self.rs_text, f"missing shape: {heading}")

    def test_rs_monorepo_has_path_filter_patterns(self) -> None:
        self.assertIn("### Path Filter Pattern", self.rs_text)
        self.assertIn("dorny/paths-filter", self.rs_text)
        self.assertIn("paths:", self.rs_text)

    def test_rs_multi_module_has_matrix_yaml(self) -> None:
        self.assertIn("fail-fast: false", self.rs_text)
        self.assertIn("go-version-file: ${{ matrix.module }}/go.mod", self.rs_text)

    def test_rs_docker_heavy_has_matrix_include(self) -> None:
        self.assertIn("matrix:", self.rs_text)
        self.assertIn("dockerfile:", self.rs_text)

    def test_rs_no_makefile_has_fallback_marking(self) -> None:
        self.assertIn("# INLINE FALLBACK", self.rs_text)

    # ------------------------------------------------------------------
    # pr-checklist.md
    # ------------------------------------------------------------------

    def test_pr_checklist_has_10_sections(self) -> None:
        for n in range(1, 11):
            self.assertIn(f"## {n})", self.pr_text, f"missing checklist section {n}")

    def test_pr_checklist_mentions_permissions_and_fallback(self) -> None:
        content = self.pr_text.lower()
        self.assertIn("permissions", content)
        self.assertIn("fallback", content)

    # ------------------------------------------------------------------
    # fallback-and-scaffolding.md
    # ------------------------------------------------------------------

    def test_fb_has_3_fallback_levels(self) -> None:
        for level in ("Level A: Full parity", "Level B: Partial parity", "Level C: Scaffold only"):
            self.assertIn(level, self.fb_text, f"missing fallback level: {level}")

    # ------------------------------------------------------------------
    # discover_ci_needs.sh
    # ------------------------------------------------------------------

    def test_discover_script_has_8_categories(self) -> None:
        content = DISCOVER_SCRIPT.read_text()
        for category in ("makefile-target", "repo-task", "container", "test-type",
                         "config", "shape", "workflow", "tool"):
            self.assertIn(category, content, f"missing category: {category}")

    def test_discover_script_handles_shapes(self) -> None:
        content = DISCOVER_SCRIPT.read_text()
        self.assertIn("find . -name go.mod", content)
        self.assertIn("single-root-module", content)
        self.assertIn("multi-module", content)


if __name__ == "__main__":
    unittest.main()
