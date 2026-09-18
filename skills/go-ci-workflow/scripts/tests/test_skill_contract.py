# PEP 563: annotations are never evaluated at runtime, so PEP 604 unions
# (`dict | None`) work on Python 3.9. macOS ships 3.9.6 as /usr/bin/python3, and
# without this the module fails to IMPORT there — unittest reports one
# `_FailedTest` and silently runs 46 of 124 tests. Caught only by running the
# runner on a stripped PATH; the version floor is not otherwise declared.
from __future__ import annotations

import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[2]
SKILL_MD = SKILL_DIR / "SKILL.md"
REF_DIR = SKILL_DIR / "references"
WORKFLOW_GUIDE = REF_DIR / "workflow-quality-guide.md"
PR_CHECKLIST = REF_DIR / "pr-checklist.md"
REPO_SHAPES = REF_DIR / "repository-shapes.md"
ADVANCED = REF_DIR / "github-actions-advanced-patterns.md"
FALLBACK = REF_DIR / "fallback-and-scaffolding.md"
GOLDEN_EXAMPLES = REF_DIR / "golden-examples.md"
GOLDEN_MONOREPO = REF_DIR / "golden-example-monorepo.md"
GOLDEN_SERVICE_CONTAINERS = REF_DIR / "golden-example-service-containers.md"
DISCOVER_SCRIPT = SKILL_DIR / "scripts" / "discover_ci_needs.sh"
RUN_REGRESSION = SKILL_DIR / "scripts" / "run_regression.sh"

# §16 pinning-policy table rows: | `actions/checkout` | `v7` | 2026-07-16 |
POLICY_ROW_RE = re.compile(
    r"^\|\s*`(?P<action>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)`\s*\|\s*`(?P<major>v\d+)`\s*\|",
    re.MULTILINE,
)
# `uses: owner/repo@ref` occurrences in the reference YAML examples.
USES_RE = re.compile(
    r"uses:\s*(?P<action>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)@(?P<ref>[A-Za-z0-9_.-]+)"
)
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
# §13 Go support table row: | `go` | `1.26`, `1.27` | 2026-09-17 |
GO_POLICY_ROW_RE = re.compile(
    r"^\|\s*`go`\s*\|\s*(?P<majors>[^|]+?)\s*\|\s*(?P<verified>\d{4}-\d{2}-\d{2})\s*\|",
    re.MULTILINE,
)
# A literal Go version list in a matrix: go-version: ['1.26', '1.27']
GO_MATRIX_RE = re.compile(r"go-version:\s*\[(?P<list>[^\]]*)\]")
GO_VERSION_RE = re.compile(r"1\.\d+")
# Majors already out of Go's two-most-recent support window on 2026-09-17.
# Bump this floor deliberately when the §13 policy row moves, exactly as
# TestActionVersionCurrency.test_no_known_stale_majors_remain is bumped.
KNOWN_EOL_GO_MINORS = frozenset(range(11, 26))
# §8 recommended-timeout table rows: | Core gate (fmt + test + lint + build) | 15 min |
TIMEOUT_ROW_RE = re.compile(
    r"^\|\s*(?P<job>[A-Za-z][^|]*?)\s*\|\s*(?P<minutes>\d+)\s*min\s*\|",
    re.MULTILINE,
)


def frontmatter(text: str) -> str:
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        raise AssertionError("missing yaml frontmatter")
    return match.group(1)


def _count_heading(text: str, title: str) -> int:
    pattern = r"^#{2,3}\s+" + re.escape(title) + r"\s*$"
    return len(re.findall(pattern, text, re.MULTILINE))


def shape_gate_shapes(text: str) -> list:
    """The closed vocabulary Gate 1 requires the model to classify into.

    Derived from SKILL.md so the reference doc can be checked against it
    instead of maintaining a second hardcoded copy of the same list.
    """
    section = gate_sections(text)["Repository Shape Gate"]
    body = section.split("Inspect:")[0]   # the second bullet list is files to read
    return [m.group(1).strip() for m in re.finditer(r"^-\s+(.+)$", body, re.MULTILINE)]


def numbered_sections(text: str) -> dict:
    """`## 3. Title` / `## 6) Title` -> that section's own body, lowercased key.

    Section-scoped on purpose. A whole-file assertion is satisfied by a match
    anywhere, which is how a gutted §6 stayed green: the sentence its fixture
    searched for lived *below* the deleted paragraph.
    """
    heads = list(re.finditer(r"^##\s*\d+[.)]\s*(?P<name>.+?)\s*$", text, re.MULTILINE))
    out = {}
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        out[m.group("name").strip().lower()] = text[m.end():end]
    return out


def gate_sections(text: str) -> dict:
    """SKILL.md gate name -> the text of that gate's own section."""
    heads = list(re.finditer(r"^#{2,4}\s*(?:\d+\)\s*)?(?P<name>[A-Z][^\n]*?Gate)\s*$",
                             text, re.MULTILINE))
    out = {}
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        nxt = re.search(r"^## ", text[m.end():end], re.MULTILINE)
        stop = m.end() + nxt.start() if nxt else end
        out[m.group("name")] = text[m.end():stop]
    return out

# ------------------------------------------------------------------
# TestFrontmatter
# ------------------------------------------------------------------

class TestFrontmatter(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skill_text = SKILL_MD.read_text()

    def test_frontmatter_name_and_description(self) -> None:
        fm = frontmatter(self.skill_text)
        self.assertIn("name: go-ci-workflow", fm)
        self.assertIn("GitHub Actions", fm)

    def test_frontmatter_has_no_unsupported_fields(self) -> None:
        """Only validator-recognised keys may appear (name/description/license/
        allowed-tools/metadata/compatibility). `disable-model-invocation` is
        rejected by quick_validate and previously made the runner fail."""
        fm = frontmatter(self.skill_text)
        self.assertNotIn("disable-model-invocation", fm)


# ------------------------------------------------------------------
# TestSkillMdStructure
# ------------------------------------------------------------------

class TestSkillMdStructure(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skill_text = SKILL_MD.read_text()

    def test_skill_md_under_line_budget(self) -> None:
        """SKILL.md must stay within the 350-line maintenance budget."""
        lines = len(self.skill_text.splitlines())
        self.assertLessEqual(lines, 350, f"SKILL.md too long: {lines} lines (budget: 350)")

    def test_priority_and_fallback_exist(self) -> None:
        self.assertIn("## Execution Priority", self.skill_text)
        self.assertIn("controlled inline workflow commands only", self.skill_text)
        self.assertIn("## Mandatory Gates", self.skill_text)
        self.assertIn("Degraded Output Gate", self.skill_text)

    def test_skill_has_5_mandatory_gates(self) -> None:
        """Gate NAMES are a real contract — the golden fixtures key
        `expected_gates` on them. Match the name, not the `### N)` prefix, so
        renumbering or restyling headings is not a test failure."""
        for gate in (
            "Repository Shape Gate",
            "Local Parity Gate",
            "Security and Permissions Gate",
            "Execution Integrity Gate",
            "Degraded Output Gate",
        ):
            self.assertRegex(
                self.skill_text,
                re.compile(r"^#{2,4}[^\n]*" + re.escape(gate) + r"\s*$", re.MULTILINE),
                f"mandatory gate heading missing: {gate}",
            )

    def test_every_gate_has_a_substantive_body(self) -> None:
        """Slice SKILL.md between gate headings and assert INSIDE the slice.

        A mutation audit deleted the entire body of the Local Parity Gate and of
        the Degraded Output Gate and the suite stayed green: their assertions
        were whole-file substring checks that other sections happened to
        satisfy. A gate reduced to a heading is a gate that does not run.
        """
        gates = gate_sections(self.skill_text)
        self.assertEqual(5, len(gates), f"expected 5 gate sections, got {sorted(gates)}")
        # Each gate must carry its own operative content, found in its own slice.
        required = {
            "Repository Shape Gate": ["go.mod", "Makefile", "classify"],
            "Local Parity Gate": ["make target", "repo task", "inline fallback",
                                  "missing"],
            "Security and Permissions Gate": ["fork PRs can reach secrets",
                                              "minimum required `permissions`",
                                              "workflow_call"],
            "Execution Integrity Gate": ["Not run in this environment",
                                         "exact commands to run next"],
            "Degraded Output Gate": ["do not fabricate complete parity",
                                     "scaffold", "missing targets"],
        }
        for gate, needles in required.items():
            body = gates[gate]
            self.assertGreaterEqual(
                len(body.split()), 25,
                f"{gate}: body is {len(body.split())} words — heading without content",
            )
            for needle in needles:
                self.assertIn(needle, body,
                              f"{gate}: operative content missing from its own section: {needle!r}")

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
# TestReferenceFiles
# ------------------------------------------------------------------

class TestReferenceFiles(unittest.TestCase):
    def test_all_references_and_scripts_exist(self) -> None:
        for path in (
            WORKFLOW_GUIDE, PR_CHECKLIST, REPO_SHAPES,
            ADVANCED, FALLBACK, GOLDEN_EXAMPLES,
            GOLDEN_MONOREPO, GOLDEN_SERVICE_CONTAINERS,
            DISCOVER_SCRIPT,
        ):
            self.assertTrue(path.exists(), f"missing {path.name}")


# ------------------------------------------------------------------
# TestWorkflowQualityGuide
# ------------------------------------------------------------------

class TestWorkflowQualityGuide(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.wqg_text = WORKFLOW_GUIDE.read_text()

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
        # §11 must carry a machine-checked pin table AND an explicit
        # re-verify instruction — a prose "these may be stale" note alone is
        # what let five tool pins rot unnoticed.
        self.assertIn("Re-verify before generating", self.wqg_text)
        self.assertIn("single source of truth", self.wqg_text)
        self.assertRegex(self.wqg_text, r"gh api repos/[\w./-]+/releases/latest")

    def test_wqg_mentions_monorepo(self) -> None:
        self.assertIn("monorepo", self.wqg_text.lower())

    def test_wqg_cache_section_matches_verified_setup_go_behaviour(self) -> None:
        """§3 taught the wrong cache mechanism for the very version §16 pins.

        It said `setup-go` "derives its key by hashing `go.sum`" and finds it
        "in the working directory". Verified against `actions/setup-go@v7.0.0`
        source: the default `dependencyFilePattern` is `go.mod` (changed in
        v6.3.0), `findDependencyFile` reads a non-recursive listing of
        `GITHUB_WORKSPACE`, and a missing file THROWS rather than missing the
        cache. Version currency was automated for actions and tools; the
        *behavioural* claim had nothing behind it, and a mutation reverting the
        correction survived the whole suite.

        Scoped to §3, and asserted as a known-bad absence plus required-topic
        coverage — the same shape as `test_no_known_stale_majors_remain`."""
        body = numbered_sections(self.wqg_text)["go setup pattern"]
        # Allow-list the decisive claim; do not deny-list wordings of the wrong
        # one. The space of wrong phrasings is unbounded — a first version of
        # this guard listed literal strings and missed the **bolded** variant,
        # so the reverting mutation survived the sweep.
        if not re.search(r"hashes\s+\*{0,2}`go\.mod`", body):
            self.fail("§3 no longer states that setup-go's default cache key hashes "
                      "`go.mod`. Verified against actions/setup-go@v7.0.0: the default "
                      "dependencyFilePattern is go.mod (since v6.3.0).")
        if re.search(r"hash(es|ing)\s+\*{0,2}`?go\.sum`?", body):
            self.fail("§3 regressed to the pre-2026-09-17 claim that the default cache "
                      "key hashes `go.sum`. It hashes go.mod; go.sum is only used when "
                      "cache-dependency-path names it explicitly.")
        if "github_workspace" not in body.lower():
            self.fail("§3 no longer states WHERE setup-go looks (a non-recursive "
                      "GITHUB_WORKSPACE listing, not the working directory) — the half "
                      "of the mechanism that decides whether the step fails outright.")

    def test_wqg_secret_section_states_the_platform_rule_correctly(self) -> None:
        """§12 taught a wrong causal model and the corpus never stated the real
        rule anywhere.

        It said to gate secret jobs with `if: github.event_name != 'pull_request'`
        "to prevent exposure on fork PRs". GitHub already withholds every secret
        from a fork `pull_request` run and downgrades `GITHUB_TOKEN` to
        read-only — the `if:` prevents a confusing empty-secret failure, not a
        leak, and it over-fires on same-repo PRs where the job would work. The
        actual exposure is `pull_request_target`."""
        body = numbered_sections(self.wqg_text)["secret management"]
        lowered = body.lower()
        if "to prevent exposure on fork prs" in lowered:
            self.fail("§12 has regressed to the false causal model: the event check "
                      "does not prevent a leak; GitHub already withholds secrets from "
                      "fork pull_request runs.")
        for topic, why in (
            ("no secrets at all", "the platform rule must be stated plainly"),
            ("head.repo.full_name", "the precise fork guard, not the blunt event check"),
            ("pull_request_target", "the actual exposure this section must name"),
        ):
            if topic.lower() not in lowered:
                self.fail(f"§12 no longer states {topic!r} — {why}")

    def test_wqg_has_pinning_and_supply_chain_section(self) -> None:
        self.assertIn("## 16. Action Version & Supply-Chain Pinning", self.wqg_text)
        # both pinning tiers documented
        self.assertIn("major tag", self.wqg_text)
        self.assertIn("commit SHA", self.wqg_text)
        # automated bumping
        self.assertIn("dependabot", self.wqg_text.lower())
        # re-verify guidance, not a frozen number
        self.assertIn("releases/latest", self.wqg_text)

    def test_wqg_documents_cache_dependency_path(self) -> None:
        self.assertIn("cache-dependency-path", self.wqg_text)


# ------------------------------------------------------------------
# TestAdvancedPatterns
# ------------------------------------------------------------------

class TestAdvancedPatterns(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.gap_text = ADVANCED.read_text()

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

    def test_gap_self_hosted_carries_the_trust_boundary_facts(self) -> None:
        """§6 is a NAMED load trigger of Gate 3 (Security and Permissions), so
        it must carry the trust-boundary facts, not just a heading.

        It shipped as nine content-free bullets — no mention that a self-hosted
        runner must almost never serve a public repository, which is the one
        fact that matters. `test_gap_has_all_9_sections` passed on the heading
        alone, and golden fixture 012 asserted that section's own heading and
        its own last sentence, so a mutation deleting the entire body survived.

        Required-topic coverage, scoped to §6, not phrase matching: any honest
        rewrite of this section keeps these terms; a gutted one loses them."""
        body = numbered_sections(self.gap_text)["self-hosted runners"]
        for topic, why in (
            ("public repositor", "the public-repo prohibition is the load-bearing fact"),
            ("ephemeral", "'destroy the runner per job' is not a guaranteed boundary"),
            ("runner group", "labels are not a security boundary; groups are"),
            ("GITHUB_TOKEN", "a compromised runner reaches the token, not just secrets"),
        ):
            if topic.lower() not in body.lower():
                self.fail(f"advanced-patterns §6 no longer covers {topic!r} — {why}")
        self.assertGreaterEqual(
            len(body.split()), 200,
            "§6 collapsed back toward a content-free stub; it is a Gate 3 load "
            "target and must carry real trust-boundary content")

    def test_gap_permissions_replacement_rule_is_not_inverted(self) -> None:
        """§1's replacement semantics decide whether a reader writes a working
        `permissions:` block or a 403.

        Inverting it to "adds, does not replace" / "leaves them at default"
        keeps every keyword and survived the audit's mutation set. Scoped to
        §1, asserted as the known-bad claim's absence plus the decisive term —
        the shape used for §3 and §6."""
        body = numbered_sections(self.gap_text)["permissions"]
        lowered = body.lower()
        for wrong in ("adds, does not replace", "leaves them at default",
                      "merges with", "adds to it"):
            if wrong in lowered:
                self.fail(f"§1 inverts the permissions replacement rule: {wrong!r}. "
                          "A declared block sets every unlisted scope to `none`.")
        if "does not add" not in lowered or "none" not in lowered:
            self.fail("§1 no longer states that a `permissions:` block REPLACES the "
                      "default grant and sets unlisted scopes to `none` — the single "
                      "most common permissions failure.")

    def test_gap_pull_request_target_is_never_endorsed(self) -> None:
        """§2 must warn about `pull_request_target`, not recommend it.

        A mutation rewriting it to "prefer `pull_request_target` whenever a PR
        job needs secrets … it is safe" endorsed the most dangerous Actions
        anti-pattern and survived every assertion."""
        body = numbered_sections(self.gap_text)["fork pr safety"]
        lowered = body.lower()
        for wrong in ("prefer `pull_request_target`", "prefer pull_request_target",
                      "it is safe to run pr code", "safe to run pr code with access"):
            if wrong in lowered:
                self.fail(f"§2 endorses pull_request_target: {wrong!r}. It runs in the "
                          "base context with full secrets and a writable token.")
        for topic in ("pull_request_target", "secret"):
            if topic not in lowered:
                self.fail(f"§2 no longer covers {topic!r} — it is the fork trust boundary")

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
# TestGoldenExamples
# ------------------------------------------------------------------

class TestGoldenExamples(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ge_text = GOLDEN_EXAMPLES.read_text()
        cls.ge_monorepo_text = GOLDEN_MONOREPO.read_text()
        cls.ge_service_containers_text = GOLDEN_SERVICE_CONTAINERS.read_text()

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
            _count_heading(text, "Complete Workflow")
            for text in (self.ge_text, self.ge_monorepo_text, self.ge_service_containers_text)
        )
        summary_count = sum(
            _count_heading(text, "Output Summary")
            for text in (self.ge_text, self.ge_monorepo_text, self.ge_service_containers_text)
        )
        self.assertEqual(workflow_count, 5, f"expected 5 Complete Workflow sections, got {workflow_count}")
        self.assertEqual(summary_count, 5, f"expected 5 Output Summary sections, got {summary_count}")

    def test_ge_fallback_has_inline_markers(self) -> None:
        self.assertIn("# INLINE FALLBACK", self.ge_text)
        self.assertIn("Local parity: PARTIAL", self.ge_text)

    def test_ge_service_container_example_has_services_block(self) -> None:
        self.assertIn("services:", self.ge_service_containers_text)
        self.assertIn("mysql:", self.ge_service_containers_text)
        self.assertIn("redis:", self.ge_service_containers_text)

    def test_ge_fork_pr_security_example_exists(self) -> None:
        """Fork PR Security section must be present with the correct if: guard YAML."""
        self.assertIn("## 3) Fork PR Security", self.ge_text)
        self.assertIn(
            "github.event.pull_request.head.repo.full_name == github.repository",
            self.ge_text,
        )


# ------------------------------------------------------------------
# TestRepositoryShapes
# ------------------------------------------------------------------

class TestRepositoryShapes(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rs_text = REPO_SHAPES.read_text()

    def test_rs_covers_every_shape_the_gate_declares(self) -> None:
        """The two taxonomies must agree — derived from SKILL.md, not a second
        hardcoded list.

        They had drifted: SKILL.md said `single-module application` and
        `reusable-workflow candidate`; this file said `Single-Module Service`,
        had no reusable-workflow section at all, and offered `No Makefile or
        Partial Tasking` as a seventh shape the gate never names. Each side was
        pinned by its own assertion, so nothing checked that they matched — a
        mutation making either side agree with the other went red from the
        *other* direction.
        """
        shapes = shape_gate_shapes(SKILL_MD.read_text())
        self.assertEqual(6, len(shapes),
                         f"Repository Shape Gate no longer lists 6 shapes: {shapes}")
        headings = {m.group(1).strip().lower()
                    for m in re.finditer(r"^## \d+\)\s*(.+)$", self.rs_text, re.MULTILINE)}
        missing = [s for s in shapes if s.lower() not in headings]
        self.assertFalse(
            missing,
            f"repository-shapes.md has no section for these Gate 1 shapes: {missing}. "
            f"Sections present: {sorted(headings)}")

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

    def test_rs_multi_module_sets_cache_dependency_path(self) -> None:
        self.assertIn("cache-dependency-path: ${{ matrix.module }}/go.sum", self.rs_text)

    def test_rs_documents_go_work_workspace(self) -> None:
        self.assertIn("go.work", self.rs_text)
        self.assertIn("go-workspace", self.rs_text)

    def test_rs_path_filter_job_has_pull_requests_read(self) -> None:
        self.assertIn("pull-requests: read", self.rs_text)

    def test_rs_documents_required_status_check_interaction(self) -> None:
        self.assertIn("Required Status Checks", self.rs_text)
        self.assertIn("ci-required", self.rs_text)
        self.assertIn("if: always()", self.rs_text)


# ------------------------------------------------------------------
# TestChecklist
# ------------------------------------------------------------------

class TestChecklist(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pr_text = PR_CHECKLIST.read_text()

    def test_pr_checklist_has_10_sections(self) -> None:
        for n in range(1, 11):
            self.assertIn(f"## {n})", self.pr_text, f"missing checklist section {n}")

    def test_pr_checklist_mentions_permissions_and_fallback(self) -> None:
        content = self.pr_text.lower()
        self.assertIn("permissions", content)
        self.assertIn("fallback", content)


# ------------------------------------------------------------------
# TestFallback
# ------------------------------------------------------------------

class TestFallback(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fb_text = FALLBACK.read_text()

    def test_fb_has_3_fallback_levels(self) -> None:
        for level in ("Level A: Full parity", "Level B: Partial parity", "Level C: Scaffold only"):
            self.assertIn(level, self.fb_text, f"missing fallback level: {level}")


# ------------------------------------------------------------------
# TestDiscoveryScript
# ------------------------------------------------------------------

class TestDiscoveryScript(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.content = DISCOVER_SCRIPT.read_text()

    def test_discover_script_has_8_categories(self) -> None:
        for category in ("makefile-target", "repo-task", "container", "test-type",
                         "config", "shape", "workflow", "tool"):
            self.assertIn(category, self.content, f"missing category: {category}")

    def test_discover_script_handles_shapes(self) -> None:
        self.assertIn("find . -type f -name go.mod", self.content)
        self.assertIn("single-root-module", self.content)
        self.assertIn("multi-module", self.content)

    def test_prune_list_has_exactly_one_definition(self) -> None:
        """The prune list must exist once and be derived everywhere else.

        It did not: the `find` predicates came from `PRUNE`, but the
        package-main probe carried a hand-written regex copy that had already
        drifted — it omitted `.git`, so a stray `.git/**/leftover.go` was
        reported as the application entrypoint, while a comment three lines
        above claimed the list applied to every probe. Both forms are now
        generated from `PRUNE_DIRS`.

        Comments are stripped first, so the narrative above (which names the
        directories) cannot satisfy or break this check. Behaviour is covered
        separately by `test_discover_script.py`."""
        code = "\n".join(line for line in self.content.splitlines()
                         if not line.lstrip().startswith("#"))
        self.assertIn("PRUNE_DIRS=(", code, "prune list is no longer declared in one place")
        for name in ("vendor", "node_modules", "testdata", "third_party"):
            self.assertEqual(
                1, code.count(name),
                f"{name!r} appears {code.count(name)}× in code — the prune list has a "
                "second copy that can drift. Derive it from PRUNE_DIRS.")

    def test_discover_script_detects_workspace_toolchain_and_app_signal(self) -> None:
        for token in ("go-workspace", "toolchain", "likely-application",
                      "likely-library-or-unknown"):
            self.assertIn(token, self.content, f"discover script missing: {token}")


# ------------------------------------------------------------------
# TestActionVersionCurrency — points 1 & 2: examples must match the §16 policy
# ------------------------------------------------------------------

class TestActionVersionCurrency(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = {
            m.group("action"): m.group("major")
            for m in POLICY_ROW_RE.finditer(WORKFLOW_GUIDE.read_text())
        }
        cls.ref_files = sorted(REF_DIR.glob("*.md"))

    def test_policy_table_lists_core_actions(self) -> None:
        for action in ("actions/checkout", "actions/setup-go",
                       "dorny/paths-filter", "actions/upload-artifact"):
            self.assertIn(action, self.policy, f"{action} missing from §16 pinning table")

    def test_every_example_pin_matches_policy_major(self) -> None:
        """Every `uses: <action>@vN` in the references must use the major the
        §16 table declares. SHA-pinned examples (40 hex) are exempt. This is the
        tripwire that turns a stale golden template into a red test."""
        mismatches = []
        for path in self.ref_files:
            for m in USES_RE.finditer(path.read_text()):
                action, ref = m.group("action"), m.group("ref")
                if action not in self.policy or SHA_RE.match(ref):
                    continue
                if ref != self.policy[action]:
                    mismatches.append(f"{path.name}: {action}@{ref} != policy {self.policy[action]}")
        self.assertFalse(mismatches, "action pins drifted from §16 policy:\n" + "\n".join(mismatches))

    def test_no_known_stale_majors_remain(self) -> None:
        """Guard against regressing to the versions the review flagged."""
        stale = {"actions/checkout": {"v4", "v5", "v6"},
                 "actions/setup-go": {"v4", "v5", "v6"},
                 "dorny/paths-filter": {"v3"},
                 "actions/upload-artifact": {"v4", "v5", "v6"}}
        found = []
        for path in self.ref_files:
            for m in USES_RE.finditer(path.read_text()):
                action, ref = m.group("action"), m.group("ref")
                if ref in stale.get(action, set()):
                    found.append(f"{path.name}: {action}@{ref}")
        self.assertFalse(found, "stale action majors still present:\n" + "\n".join(found))


class TestGoVersionCurrency(unittest.TestCase):
    """The §13 Go support table is the single source of truth for matrix
    versions — the mirror of §16 for actions and §11 for tools.

    Go ships a major roughly every six months and supports only the two most
    recent, so a matrix literal rots faster than any action or tool pin. The
    skill had a re-verify discipline for actions and tools but none for Go, and
    the only value check was a `16 <= minor <= 40` plausibility band in
    test_golden_yaml.py — under which an end-of-life `['1.16', '1.17']` passed.
    The 2026-09-17 review found `['1.22', '1.23']` shipped while upstream was
    on 1.27/1.26.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.guide = WORKFLOW_GUIDE.read_text()
        cls.ref_files = sorted(REF_DIR.glob("*.md"))

    def policy_majors(self) -> set:
        match = GO_POLICY_ROW_RE.search(self.guide)
        self.assertIsNotNone(match, "§13 Go support table row `| `go` | ... |` is missing")
        return set(GO_VERSION_RE.findall(match.group("majors")))

    def test_policy_table_declares_the_supported_majors(self) -> None:
        majors = self.policy_majors()
        self.assertEqual(2, len(majors),
                         f"§13 must declare exactly the two supported majors, got {sorted(majors)}")

    def test_every_matrix_go_version_matches_policy(self) -> None:
        """Every `go-version: [...]` literal in the references must equal the
        §13 row. This is the tripwire that turns a stale matrix into a red
        test — the same mechanism as TestActionVersionCurrency."""
        policy = self.policy_majors()
        seen = 0
        mismatches = []
        for path in self.ref_files:
            for m in GO_MATRIX_RE.finditer(path.read_text()):
                declared = set(GO_VERSION_RE.findall(m.group("list")))
                if not declared:          # `${{ matrix.go-version }}` indirection
                    continue
                seen += 1
                if declared != policy:
                    mismatches.append(
                        f"{path.name}: {sorted(declared)} != §13 policy {sorted(policy)}")
        self.assertFalse(mismatches, "Go matrix versions drifted from §13:\n" + "\n".join(mismatches))
        self.assertGreaterEqual(seen, 2,
                                "Go matrix examples vanished — rule no longer bites")

    def test_policy_majors_are_not_end_of_life(self) -> None:
        """Guard against regressing to a major outside Go's support window."""
        stale = sorted(v for v in self.policy_majors()
                       if int(v.split(".")[1]) in KNOWN_EOL_GO_MINORS)
        self.assertFalse(stale,
                         f"§13 declares end-of-life Go majors {stale}; Go supports only "
                         "the two most recent. Re-verify against go.dev/dl and bump "
                         "KNOWN_EOL_GO_MINORS with the policy row.")


class TestTimeoutConsistency(unittest.TestCase):
    """The §8 recommended-timeout table is the single source of truth, and the
    always-loaded prose must not contradict it.

    It did: SKILL.md and `workflow-quality-guide.md` §15 both said "20 for
    e2e/integration" while the §8 table said E2E 30 and the §7 example used 30
    — and golden fixture 009 pinned the 30. Four copies, two values, and every
    existing assertion checked only that the numbers appeared *somewhere*, so a
    mutation that permuted the whole table stayed green.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.table = {m.group("job").lower(): int(m.group("minutes"))
                     for m in TIMEOUT_ROW_RE.finditer(ADVANCED.read_text())}

    def test_timeout_table_parses(self) -> None:
        self.assertGreaterEqual(len(self.table), 4,
                                "§8 recommended-timeout table did not parse")
        for key in ("integration tests", "e2e tests"):
            self.assertIn(key, self.table, f"§8 table missing row: {key}")

    def test_prose_timeouts_match_the_table(self) -> None:
        """Derived from the table, not a second hardcoded copy: editing a table
        row makes this fail until the prose is edited too."""
        pairs = {"integration": self.table["integration tests"],
                 "e2e": self.table["e2e tests"]}
        for path in (SKILL_MD, WORKFLOW_GUIDE):
            text = path.read_text()
            for word, minutes in pairs.items():
                # Not assertIn: it dumps the whole file into the failure output.
                if f"{minutes} {word}" not in text:
                    self.fail(f"{path.name}: timeout prose disagrees with the §8 "
                              f"table — expected '{minutes} {word}'. Bump both together.")


# ------------------------------------------------------------------
# TestRunRegression — point 6: the runner must fail closed
# ------------------------------------------------------------------

class TestRunRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = RUN_REGRESSION.read_text()

    def test_runner_is_fail_closed(self) -> None:
        self.assertIn("set -euo pipefail", self.text)
        # the old error-swallowing path must be gone
        self.assertNotIn("continuing", self.text.lower())

    def test_runner_surfaces_actionlint_skip(self) -> None:
        self.assertIn("actionlint", self.text)
        self.assertIn("WARNING", self.text)

    def test_runner_stops_when_validator_fails(self) -> None:
        """A failing validator must abort with its exit code, not print
        'regression checks passed'."""
        with tempfile.TemporaryDirectory() as tmp:
            validator = Path(tmp) / "fail_validator.py"
            validator.write_text("raise SystemExit(7)\n")
            env = dict(os.environ)
            env["SKILL_CREATOR_VALIDATOR"] = str(validator)
            result = subprocess.run(
                ["bash", str(RUN_REGRESSION)],
                cwd=str(SKILL_DIR),
                env=env,
                capture_output=True,
                text=True,
            )
        self.assertEqual(7, result.returncode)
        self.assertNotIn("[3/4]", result.stdout)
        self.assertNotIn("regression checks passed", result.stdout)

    # --- the runner's SUCCESS path ---
    #
    # Everything above aborts at the validator step, so until these tests the
    # runner's success path had never been executed by any test: a backdoor
    # that skipped the whole test step (`[ -n "${SKIP_TESTS:-}" ] || python3 -m
    # unittest ...`) was undetectable. Running the real suite from within the
    # suite would also recurse — it terminates today only because the injected
    # validator aborts first. These build a standalone skill directory with a
    # generated stub suite instead: the real script, no recursion.

    def _min_tests(self) -> int:
        match = re.search(r"^MIN_TESTS=(\d+)", self.text, re.MULTILINE)
        self.assertIsNotNone(match, "runner no longer declares MIN_TESTS")
        return int(match.group(1))

    def _run_with_stub_suite(self, n_pass: int, n_skip: int = 0, extra_env: dict | None = None):
        """Run the real runner against a generated stub suite."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scripts" / "tests").mkdir(parents=True)
            (root / "scripts" / "run_regression.sh").write_text(self.text)
            body = ["import unittest", "", "class StubTests(unittest.TestCase):"]
            body += [f"    def test_pass_{i}(self): pass" for i in range(n_pass)]
            body += [f"    def test_skip_{i}(self): self.skipTest('stub')"
                     for i in range(n_skip)]
            (root / "scripts" / "tests" / "test_stub.py").write_text("\n".join(body) + "\n")
            validator = root / "ok_validator.py"
            validator.write_text("raise SystemExit(0)\n")
            env = dict(os.environ)
            env["SKILL_CREATOR_VALIDATOR"] = str(validator)
            env.update(extra_env or {})
            return subprocess.run(
                ["bash", str(root / "scripts" / "run_regression.sh")],
                cwd=str(root), env=env, capture_output=True, text=True,
            )

    def test_runner_success_path_reports_pass(self) -> None:
        result = self._run_with_stub_suite(self._min_tests() + 5)
        self.assertEqual(0, result.returncode,
                         f"runner failed on a clean suite:\n{result.stdout}\n{result.stderr}")
        self.assertIn("regression checks passed", result.stdout)
        self.assertIn("[4/4]", result.stdout)
        # Assert the tests RAN, not merely that the banner printed. A step that
        # is skipped (by a backdoor, a bad path, or a silenced command) can
        # still reach the banner; only named test output proves execution.
        self.assertIn("test_pass_0", result.stdout)
        self.assertRegex(result.stdout, r"ran=\d+ skipped=\d+")

    def test_runner_fails_when_discovery_collapses(self) -> None:
        """`unittest discover` exits 0 after "NO TESTS RAN", so a pattern that
        matches nothing reads as success without this floor."""
        result = self._run_with_stub_suite(5)
        self.assertNotEqual(0, result.returncode, "a partial run reported success")
        self.assertNotIn("regression checks passed", result.stdout)
        self.assertIn("discovery collapsed", result.stderr)

    def test_runner_ignores_hostile_skip_environment_variables(self) -> None:
        """Behavioural guard against a *dormant* test-step backdoor.

        A mutation prefixing the unittest line with `[ -n "${SKIP_TESTS:-}" ] ||`
        changes nothing while the variable is unset, so the tree stays green and
        no source-only mutation can reveal it — it survived the committed sweep
        for exactly that reason. Supplying the trigger does reveal it: an
        unmutated runner ignores these variables and still executes the suite,
        a backdoored one produces no test output and fails to report a count.

        Text-matching the script for backdoor shapes would be self-deceiving
        (the space of wordings is unbounded); this asserts the behaviour."""
        result = self._run_with_stub_suite(
            self._min_tests() + 5,
            extra_env={"SKIP_TESTS": "1", "SKIP": "1", "NO_TESTS": "1"},
        )
        self.assertEqual(0, result.returncode,
                         f"runner changed behaviour under a skip-flavoured env var:\n"
                         f"{result.stdout}\n{result.stderr}")
        self.assertIn("test_pass_0", result.stdout,
                      "the test step did not execute — the runner honoured an "
                      "environment variable that must have no effect")

    def test_runner_fails_on_unaccounted_skips(self) -> None:
        """The live regression: PyYAML absent silently skipped 18 structural
        YAML tests and the runner still printed a success banner."""
        result = self._run_with_stub_suite(self._min_tests() + 5, n_skip=3)
        self.assertNotEqual(0, result.returncode, "unexplained skips reported success")
        self.assertNotIn("regression checks passed", result.stdout)
        self.assertIn("skipped", result.stderr)


if __name__ == "__main__":
    unittest.main()

# ------------------------------------------------------------------
# TestToolVersionCurrency — §11 pin table is the single source of truth
# ------------------------------------------------------------------

# §11 rows: | golangci-lint | `path/to/cmd` | `v2.13.2` | 2026-09-16 |
TOOL_ROW_RE = re.compile(
    r"^\|\s*(?P<tool>[a-z0-9-]+)\s*\|\s*`(?P<path>[^`]+)`\s*\|\s*`(?P<version>v[0-9][^`]*)`\s*\|",
    re.MULTILINE,
)
GO_INSTALL_RE = re.compile(r"go install (?P<path>[^\s@]+)@(?P<version>[^\s`\"']+)")
# A bare major tag in a code span. Tool pins always carry dots (`v2.13.2`), so
# anything matching this is an ACTION major — and must come from §16, not from
# a hand-written example. `pr-checklist.md` recommended `@v4`/`@v5` long after
# §16 moved to v7, and the old guard never saw it because it only read `uses:`
# lines.
BARE_MAJOR_RE = re.compile(r"`@v(?P<major>\d+)`")


class TestToolVersionCurrency(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.table = {
            m.group("path"): m.group("version")
            for m in TOOL_ROW_RE.finditer(WORKFLOW_GUIDE.read_text())
        }
        cls.ref_files = sorted(REF_DIR.glob("*.md"))

    def test_pin_table_lists_the_tools_the_examples_install(self) -> None:
        self.assertGreaterEqual(len(self.table), 5,
                                f"§11 pin table did not parse: {self.table}")
        installed = {
            m.group("path")
            for path in self.ref_files
            for m in GO_INSTALL_RE.finditer(path.read_text())
        }
        missing = installed - set(self.table)
        self.assertFalse(missing, f"tools installed in examples but absent from §11: {missing}")

    def test_every_go_install_matches_the_pin_table(self) -> None:
        """Eleven copies of five tool pins were scattered over five files with
        no cross-check; all five had rotted by several minor versions."""
        drift = []
        for path in self.ref_files:
            for m in GO_INSTALL_RE.finditer(path.read_text()):
                want = self.table.get(m.group("path"))
                if want and m.group("version") != want:
                    drift.append(f"{path.name}: {m.group('path')}@{m.group('version')} != §11 {want}")
        self.assertFalse(drift, "tool pins drifted from §11:\n" + "\n".join(drift))

    def test_no_go_install_at_latest(self) -> None:
        for path in self.ref_files:
            for m in GO_INSTALL_RE.finditer(path.read_text()):
                self.assertNotEqual("latest", m.group("version").lstrip("@"),
                                    f"{path.name}: {m.group('path')} installed @latest")

    def test_prose_tool_versions_match_the_pin_table(self) -> None:
        """Output-summary tables quoted `golangci-lint v2.6.2` in prose. Prose
        is a second copy and rots the same way — bind it to §11 too."""
        by_tool = {
            m.group("tool"): m.group("version")
            for m in TOOL_ROW_RE.finditer(WORKFLOW_GUIDE.read_text())
        }
        drift = []
        for path in self.ref_files:
            text = path.read_text()
            for tool, want in by_tool.items():
                for m in re.finditer(re.escape(tool) + r"\s+(v\d+\.\d+\.\d+)", text):
                    if m.group(1) != want:
                        drift.append(f"{path.name}: {tool} {m.group(1)} != §11 {want}")
        self.assertFalse(drift, "prose tool versions drifted from §11:\n" + "\n".join(drift))

    def test_no_bare_stale_action_major_anywhere(self) -> None:
        """Catches version guidance written as prose rather than as a `uses:`
        line — the hole that let pr-checklist.md keep recommending `@v4`."""
        policy_majors = {
            m.group("major")
            for m in re.finditer(r"\|\s*`[A-Za-z0-9_./-]+`\s*\|\s*`v(?P<major>\d+)`\s*\|",
                                 WORKFLOW_GUIDE.read_text())
        }
        self.assertTrue(policy_majors, "§16 policy table did not parse")
        # A bare `@vN` names no action, so it cannot be checked against §16 and
        # cannot be acted on by a reader — `@v4` is current for
        # dorny/paths-filter and four majors stale for actions/checkout at the
        # same time. Version examples must carry their action.
        offenders = []
        for path in self.ref_files + [SKILL_MD]:
            for m in BARE_MAJOR_RE.finditer(path.read_text()):
                offenders.append(f"{path.name}: `@v{m.group('major')}` names no action")
        self.assertFalse(offenders,
                         "unattributed action version example:\n" + "\n".join(offenders))


# ------------------------------------------------------------------
# TestCrossReferences — every `*.md` pointer must resolve
# ------------------------------------------------------------------

MD_REF_RE = re.compile(r"`(?P<name>[A-Za-z0-9._/-]+\.md)`")


class TestCrossReferences(unittest.TestCase):
    def test_every_referenced_md_file_exists(self) -> None:
        """`golden-examples.md` pointed readers at `advanced-patterns.md` — a
        file that does not exist (the real name is
        `github-actions-advanced-patterns.md`). It sat in an always-loaded file,
        on the fork-PR safety pointer, and no test looked at links at all."""
        broken = []
        for path in sorted(REF_DIR.glob("*.md")) + [SKILL_MD]:
            for m in MD_REF_RE.finditer(path.read_text()):
                target = m.group("name")
                if any((base / target).exists() for base in (REF_DIR, SKILL_DIR)):
                    continue
                broken.append(f"{path.name} -> {target}")
        self.assertFalse(broken, "dangling cross-references:\n" + "\n".join(broken))

    def test_skill_md_names_every_reference_file(self) -> None:
        """A reference nothing points to is dead weight in the skill bundle."""
        # SKILL.md writes them as `references/<name>.md`; compare basenames.
        named = {Path(n).name for n in MD_REF_RE.findall(SKILL_MD.read_text())}
        shipped = {p.name for p in REF_DIR.glob("*.md")}
        self.assertFalse(shipped - named,
                         f"reference files never named by SKILL.md: {shipped - named}")
