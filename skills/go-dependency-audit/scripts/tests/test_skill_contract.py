"""Structural contract tests for go-dependency-audit SKILL.md.

Scope, stated honestly: these tests check that the skill's *structure* is
present and internally consistent — sections, gate classes, degradation modes,
output contract. They cannot check that the guidance is correct.

Correctness of the factual claims is checked elsewhere and deliberately not
duplicated here:
  - scripts/lint_dep_audit_docs.py + test_doc_lint.py   — command/flag/env facts
  - test_govulncheck_recipes.py                          — the jq recipes, executed

Where a check *can* be made falsifiable (parse the table, compare the halves)
it is, rather than asserting that a sentence exists.
"""

from __future__ import annotations

import pathlib
import re

import pytest

SKILL_DIR = pathlib.Path(__file__).resolve().parents[2]
SKILL_MD = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
SKILL_LOWER = SKILL_MD.lower()
REFS_DIR = SKILL_DIR / "references"

SKILL_LINE_BUDGET = 500


def _ref(name: str) -> str:
    return (REFS_DIR / name).read_text(encoding="utf-8")


def _section(text: str, start: str, end: str | None = None) -> str:
    i = text.index(start)
    if end is None:
        return text[i:]
    return text[i:text.index(end, i)]


# ──────────────────────────────────────────────────────────────────────
class TestFrontmatter:

    @pytest.fixture(autouse=True)
    def _front(self):
        m = re.search(r"^---\n(.*?)\n---", SKILL_MD, re.DOTALL)
        assert m, "YAML frontmatter block not found"
        self.front = m.group(1)

    def test_name(self):
        assert "name: go-dependency-audit" in self.front

    def test_description_covers_triggers(self):
        desc = self.front.lower()
        for kw in ("govulncheck", "license", "cve", "supply chain",
                   "upgrade", "go.mod"):
            assert kw in desc, f"description missing trigger keyword: {kw}"

    def test_description_declares_read_only(self):
        assert "read-only" in self.front.lower(), (
            "the read-only default is a behavioural contract and belongs in the "
            "description, where the routing model sees it"
        )

    def test_allowed_tools_present(self):
        assert "allowed-tools:" in self.front

    def test_allowed_tools_grants_go_env(self):
        """S9.6 requires reporting real GOPROXY/GOPRIVATE values."""
        assert "Bash(go env" in self.front


# ──────────────────────────────────────────────────────────────────────
class TestRemediationBoundary:
    """S1.3 is the skill's central safety property."""

    def test_section_exists(self):
        assert "### 1.3 Remediation Boundary" in SKILL_MD

    def test_declares_non_negotiable(self):
        sec = _section(SKILL_MD, "### 1.3 Remediation Boundary", "## 2 Gates")
        assert "NON-NEGOTIABLE" in sec

    def test_forbids_destructive_rollback(self):
        sec = _section(SKILL_MD, "### 1.3 Remediation Boundary", "## 2 Gates")
        assert "git checkout" in sec, "the specific destructive rollback must be named"
        assert "uncommitted" in sec.lower()

    def test_requires_readonly_proof(self):
        sec = _section(SKILL_MD, "### 1.3 Remediation Boundary", "## 2 Gates")
        assert "git status --porcelain" in sec, (
            "read-only-ness must be provable, not merely asserted"
        )


# ──────────────────────────────────────────────────────────────────────
GATE_ROW_RE = re.compile(
    r"^\|\s*(\d+)\s*\|([^|]+)\|([^|]*)\|\s*(BLOCK|DEGRADE|WARN)\s*\|",
    re.MULTILINE,
)


class TestGates:
    """Every gate must carry exactly one class; classes drive stop-vs-continue."""

    @pytest.fixture(autouse=True)
    def _rows(self):
        self.rows = GATE_ROW_RE.findall(SKILL_MD)

    def test_gate_classes_are_defined(self):
        sec = _section(SKILL_MD, "### 2.1 Gate classes", "### 2.2 Gate table")
        for cls in ("BLOCK", "DEGRADE", "WARN"):
            assert f"**{cls}**" in sec, f"gate class {cls} not defined"

    def test_no_gate_both_stops_and_degrades(self):
        sec = _section(SKILL_MD, "### 2.1 Gate classes", "### 2.2 Gate table")
        assert "exactly one class" in sec

    def test_gate_table_parses(self):
        assert len(self.rows) >= 8, (
            f"only {len(self.rows)} classified gate rows parsed; the table "
            f"shape changed or a gate lost its class"
        )

    def test_every_gate_number_is_unique(self):
        nums = [r[0] for r in self.rows]
        assert len(nums) == len(set(nums)), f"duplicate gate numbers: {nums}"

    def test_all_three_classes_are_used(self):
        used = {r[3] for r in self.rows}
        assert used == {"BLOCK", "DEGRADE", "WARN"}, (
            f"gate table uses only {sorted(used)}; a taxonomy with an unused "
            f"class is a taxonomy that has drifted"
        )

    def test_integrity_failure_does_not_stop_the_audit(self):
        """The checksum gate reports rather than blocks — the finding is the deliverable."""
        row = [r for r in self.rows if r[0] == "6"]
        assert row, "gate 6 (checksum verification) not found"
        assert row[0][3] == "WARN", (
            "a checksum mismatch must be reported as a finding, not swallowed "
            "by a STOP that suppresses it"
        )


# ──────────────────────────────────────────────────────────────────────
MODE_ROW_RE = re.compile(r"^\|\s*`([a-z0-9-]+)`\s*\|\s*([^|]*)\|\s*([^|]*)\|\s*([^|]*)\|",
                         re.MULTILINE)


class TestDegradationModes:

    @pytest.fixture(autouse=True)
    def _modes(self):
        sec = _section(SKILL_MD, "## 4 Degradation Modes", "## 5 Dependency Audit")
        self.rows = MODE_ROW_RE.findall(sec)

    def test_modes_parse(self):
        assert len(self.rows) >= 4, f"only {len(self.rows)} degradation modes parsed"

    def test_every_mode_states_what_it_cannot_claim(self):
        for name, _entered, _can, cannot in self.rows:
            assert cannot.strip(), f"mode {name!r} has an empty MUST NOT column"

    def test_no_cve_mode_forbids_all_cve_claims(self):
        row = [r for r in self.rows if r[0] == "no-cve"]
        assert row, "no-cve mode missing"
        cannot = row[0][3].lower()
        assert "cve" in cannot and ("any" in cannot or "absent" in cannot)

    def test_reachability_mode_exists(self):
        names = {r[0] for r in self.rows}
        assert "no-reachability" in names, (
            "binary mode and non-symbol scans produce findings whose "
            "reachability is unmeasured; that state needs a name"
        )

    def test_never_fabricate(self):
        assert "Never fabricate CVE findings" in SKILL_MD

    def test_failed_scan_is_not_a_clean_scan(self):
        sec = _section(SKILL_MD, "## 4 Degradation Modes", "## 5 Dependency Audit")
        assert "exit code of 1 is a *failed scan*" in sec

    def test_degraded_marker_names_the_mode(self):
        assert "# DEGRADED [<mode>]:" in SKILL_MD


# ──────────────────────────────────────────────────────────────────────
class TestTriageModel:
    """The evidence-tier model replaced a CVSS-keyed one that could not work."""

    def test_states_that_govulncheck_emits_no_cvss(self):
        sec = _section(SKILL_MD, "## 6 Triage & Priority Model", "## 7 Anti-Examples")
        assert "does **not** publish CVSS scores" in sec

    def test_forbids_cvss_sourced_from_govulncheck(self):
        sec = _section(SKILL_MD, "## 6 Triage & Priority Model", "## 7 Anti-Examples")
        assert "Never state a CVSS score sourced from govulncheck" in sec

    def test_cvss_requires_a_named_source(self):
        sec = _section(SKILL_MD, "## 6 Triage & Priority Model", "## 7 Anti-Examples")
        assert "named external" in sec and "not retrieved" in sec

    def test_no_cvss_keyed_priority_survives(self):
        """Regression: the old model gated P0 on a number the tool never emits."""
        for bad in ("CVSS >= 9.0 AND govulncheck confirms",
                    "CVSS >= 7.0 AND reachable"):
            assert bad not in SKILL_MD, f"CVSS-keyed severity rule survived: {bad!r}"

    def test_three_evidence_tiers(self):
        sec = _section(SKILL_MD, "### 6.2 Evidence tiers", "### 6.3 Priority")
        for tier in ("E1 Called", "E2 Imported", "E3 Required"):
            assert tier in sec, f"evidence tier missing: {tier}"

    def test_tiers_map_to_real_output_sections(self):
        sec = _section(SKILL_MD, "### 6.2 Evidence tiers", "### 6.3 Priority")
        for header in ("=== Symbol Results ===", "=== Package Results ===",
                       "=== Module Results ==="):
            assert header in sec, f"tier table lost real output section {header}"

    def test_priority_table_covers_p0_to_p3(self):
        sec = _section(SKILL_MD, "### 6.3 Priority", "## 7 Anti-Examples")
        for p in ("**P0**", "**P1**", "**P2**", "**P3**"):
            assert p in sec, f"priority {p} missing"

    def test_unreviewed_reports_do_not_prove_unreachability(self):
        sec = _section(SKILL_MD, "### 6.3 Priority", "## 7 Anti-Examples")
        assert "UNREVIEWED" in sec


# ──────────────────────────────────────────────────────────────────────
class TestLicenseFraming:

    def test_legal_determinations_are_out_of_scope(self):
        sec = _section(SKILL_MD, "### 1.2 Out of scope", "### 1.3 Remediation")
        assert "legal determinations" in sec.lower()

    def test_section_carries_a_disclaimer(self):
        sec = _section(SKILL_MD, "### 5.2 License Risk Triage", "### 5.3 Upgrade")
        assert "does not give legal advice" in sec

    def test_uses_the_scanners_vocabulary(self):
        sec = _section(SKILL_MD, "### 5.2 License Risk Triage", "### 5.3 Upgrade")
        for word in ("forbidden", "restricted", "reciprocal", "permissive", "unknown"):
            assert word in sec, f"go-licenses type {word!r} not referenced"

    def test_grades_the_shipping_evidence(self):
        """`go list -deps` proves a build dependency, not binary content."""
        sec = _section(SKILL_MD, "### 5.2 License Risk Triage", "### 5.3 Upgrade")
        assert "-deps" in sec, "build-dependency evidence not mentioned"
        assert "go version -m" in sec, "binary evidence not mentioned"
        # `./cmd/...` may appear only in the clause warning against assuming it.
        for line in sec.splitlines():
            if "./cmd/..." in line:
                assert re.search(r"never assume|do not assume|not all", line), (
                    f"main packages must be discovered, not assumed: {line.strip()}"
                )

    def test_reference_has_an_escalation_packet(self):
        text = _ref("license-compliance.md")
        assert "ESCALATE" in text
        assert "UNKNOWN to this audit" in text, (
            "the packet must have a legal value for 'we could not determine this'"
        )


# ──────────────────────────────────────────────────────────────────────
class TestUpgradeAndHygiene:

    def test_v0_has_no_compatibility_guarantee(self):
        sec = _section(SKILL_MD, "### 5.3 Upgrade Planning", "### 5.4 Supply Chain")
        assert "no compatibility promise" in sec

    def test_gosum_is_not_a_lockfile(self):
        sec = _section(SKILL_MD, "### 5.4 Supply Chain Security", "### 5.5 Module Hygiene")
        assert "not a lockfile" in sec

    def test_goproxy_does_not_control_verification(self):
        sec = _section(SKILL_MD, "### 5.4 Supply Chain Security", "### 5.5 Module Hygiene")
        assert "GOPROXY=direct` still verifies" in sec

    def test_module_cycles_are_not_a_defect(self):
        sec = _section(SKILL_MD, "### 5.5 Module Hygiene", "## 6 Triage")
        assert "legal in Go" in sec
        assert "never as a failed check" in sec

    def test_go_work_absolutism_removed(self):
        sec = _section(SKILL_MD, "### 5.5 Module Hygiene", "## 6 Triage")
        assert "Do not commit go.work" not in sec
        assert "exception" in sec.lower()

    def test_scorecard_has_no_cycle_gate(self):
        sec = _section(SKILL_MD, "## 8 Dependency Audit Scorecard", "## 9 Output Contract")
        assert "Circular dependencies absent" not in sec, (
            "module-graph cycles are legal; they cannot be a pass/fail item"
        )


# ──────────────────────────────────────────────────────────────────────
class TestScorecard:
    """The item list moved to references/scorecard.md; SKILL.md keeps the maths."""

    @pytest.fixture(autouse=True)
    def _sec(self):
        self.sec = _section(SKILL_MD, "## 8 Dependency Audit Scorecard",
                            "## 9 Output Contract")
        self.ref = _ref("scorecard.md")

    def test_skill_routes_to_the_reference(self):
        assert "references/scorecard.md" in self.sec

    def test_three_tiers_in_the_reference(self):
        for tier in ("## 1 Critical", "## 2 Standard", "## 3 Hygiene"):
            assert tier in self.ref, f"missing tier heading {tier}"

    def test_twelve_items_in_the_reference(self):
        items = re.findall(r"^\*\*([CSH]\d)\.", self.ref, re.MULTILINE)
        assert len(items) == 12, f"expected 12 scorecard items, found {len(items)}"
        assert len(set(items)) == 12, f"duplicate item ids: {items}"

    def test_na_items_leave_the_denominator(self):
        assert "N/A" in self.sec
        assert "never counts as a pass" in self.sec, (
            "an unrunnable check scored as a pass is how a degraded audit "
            "reports PASS"
        )

    def test_verdict_is_a_ratio_not_a_fixed_threshold(self):
        """A fixed `>= 4/5` is unreachable once an item goes N/A."""
        assert "passed / applicable" in self.sec
        for bad in ("Standard >= 4/5", "Hygiene >= 3/4"):
            assert bad not in self.sec, (
                f"fixed threshold {bad!r} contradicts the N/A rule above it"
            )

    def test_multi_module_verdict_is_the_worst_module(self):
        assert "worst" in self.sec and "average" in self.sec

    def test_reference_shows_the_na_arithmetic(self):
        """A worked example is what makes the N/A rule checkable by a reader."""
        assert "Scoring Worked Example" in self.ref
        assert "0.67" in self.ref, "the example lost its failing ratio"


# ──────────────────────────────────────────────────────────────────────
class TestOutputContract:

    @pytest.fixture(autouse=True)
    def _sec(self):
        self.sec = _section(SKILL_MD, "## 9 Output Contract",
                            "## 10 Reference Loading Guide")

    def test_nine_sections(self):
        for i in range(1, 10):
            assert f"### 9.{i}" in self.sec, f"output section 9.{i} missing"

    def test_quick_mode_has_a_reduced_contract(self):
        """The old contract demanded 9 sections from a single-concern scan."""
        assert "Quick mode emits" in self.sec
        quick_line = [l for l in self.sec.splitlines() if "Quick mode emits" in l][0]
        for part in ("9.1", "9.2", "9.3", "9.8", "9.9"):
            assert part in quick_line

    def test_quick_subset_agrees_with_depth_section(self):
        depth = _section(SKILL_MD, "### Quick", "### Standard (default)")
        assert "S9 subset" in depth
        assert "Do not emit empty" in depth

    def test_omitted_sections_must_be_declared(self):
        assert "never silently dropped" in self.sec

    def test_cve_results_require_a_cvss_source(self):
        s93 = _section(self.sec, "### 9.3", "### 9.4")
        assert "with its source" in s93 and "not retrieved" in s93

    def test_cve_results_require_evidence_tier(self):
        s93 = _section(self.sec, "### 9.3", "### 9.4")
        assert "evidence tier" in s93.lower()
        assert "exit code" in s93.lower()

    def test_remediation_is_emitted_not_run(self):
        s97 = _section(self.sec, "### 9.7", "### 9.8")
        assert "does not run them" in s97

    def test_uncovered_risks_never_empty(self):
        s98 = _section(self.sec, "### 9.8", "### 9.9")
        assert "never empty" in s98.lower()

    def test_machine_summary_reports_tiers_and_exit_code(self):
        s99 = _section(self.sec, "### 9.9", "**Scorecard appended**")
        for key in ("e1_called", "e2_imported", "e3_required", "exit_code",
                    "scan_level", "modes"):
            assert key in s99, f"machine-readable summary missing {key!r}"


# ──────────────────────────────────────────────────────────────────────
class TestReferenceFiles:

    REFS = ("govulncheck-patterns.md", "license-compliance.md",
            "upgrade-planning.md", "supply-chain-security.md",
            "anti-examples.md")

    @pytest.mark.parametrize("name", REFS)
    def test_exists_and_is_linked(self, name):
        assert (REFS_DIR / name).exists()
        assert name in SKILL_MD, f"SKILL.md does not reference {name}"

    @pytest.mark.parametrize("name", REFS)
    def test_has_a_table_of_contents(self, name):
        assert "## Table of Contents" in _ref(name)

    def test_govulncheck_ref_pins_its_verified_version(self):
        assert "v1.1.4" in _ref("govulncheck-patterns.md")

    def test_govulncheck_ref_lists_nonexistent_flags(self):
        text = _ref("govulncheck-patterns.md")
        assert "Flags that do not exist" in text
        for flag in ("-go=1.21", "-mode=query"):
            assert flag in text, f"{flag} should be documented as non-existent"

    def test_govulncheck_ref_documents_all_exit_codes(self):
        sec = _section(_ref("govulncheck-patterns.md"), "## 6 Exit Codes",
                       "## 7 CI Integration")
        for code in ("`0`", "`1`", "`2`", "`3`"):
            assert code in sec, f"exit code {code} undocumented"
        assert "always exit 0" in sec

    def test_govulncheck_ref_documents_reachability_limits(self):
        text = _ref("govulncheck-patterns.md")
        assert "reflect" in text and "Never write \"not affected\"" in text

    def test_supply_chain_ref_lists_phantom_vars(self):
        text = _ref("supply-chain-security.md")
        assert "GONOSUMCHECK" in text
        assert "Never shipped" in text

    def test_supply_chain_ref_covers_retractions(self):
        text = _ref("supply-chain-security.md")
        assert "-retracted" in text and "Deprecated" in text

    def test_upgrade_ref_forbids_destructive_rollback(self):
        text = _ref("upgrade-planning.md")
        assert "never emits a rollback that discards uncommitted work" in text

    def test_upgrade_ref_documents_pseudo_version_grammar(self):
        text = _ref("upgrade-planning.md")
        assert "12 lowercase" in text
        assert "yyyymmddhhmmss" in text


# ──────────────────────────────────────────────────────────────────────
class TestNoPhantomPaths:
    """Every local path SKILL.md cites must exist.

    A sibling skill shipped an index row pointing at `agents/openai.yaml`, a file
    that never existed anywhere in this repository. No skill here has an
    `agents/` directory, so a reference to one is always a broken link.
    """

    def test_no_agents_dir_reference(self):
        assert "agents/openai.yaml" not in SKILL_MD
        assert not (SKILL_DIR / "agents").exists(), (
            "this repo has no per-skill agents/ convention; adding one here "
            "would be a lone outlier"
        )

    def test_cited_reference_files_exist(self):
        cited = set(re.findall(r"`(references/[A-Za-z0-9._-]+\.md)`", SKILL_MD))
        assert cited, "SKILL.md cites no reference files"
        missing = [c for c in cited if not (SKILL_DIR / c).exists()]
        assert not missing, f"SKILL.md cites non-existent paths: {sorted(missing)}"

    def test_every_reference_file_is_cited(self):
        on_disk = {f"references/{p.name}" for p in REFS_DIR.glob("*.md")}
        cited = set(re.findall(r"`(references/[A-Za-z0-9._-]+\.md)`", SKILL_MD))
        orphans = on_disk - cited
        assert not orphans, f"reference files nothing routes to: {sorted(orphans)}"


# ──────────────────────────────────────────────────────────────────────
class TestLineBudget:

    def test_skill_md_within_budget(self):
        lines = SKILL_MD.count("\n") + 1
        assert lines <= SKILL_LINE_BUDGET, \
            f"SKILL.md is {lines} lines (budget: {SKILL_LINE_BUDGET})"

    def test_budget_has_headroom(self):
        """A budget already at the limit is not a budget."""
        lines = SKILL_MD.count("\n") + 1
        assert lines <= SKILL_LINE_BUDGET - 20, (
            f"SKILL.md is {lines}/{SKILL_LINE_BUDGET} lines — raise the budget "
            f"deliberately rather than discovering it mid-edit"
        )
