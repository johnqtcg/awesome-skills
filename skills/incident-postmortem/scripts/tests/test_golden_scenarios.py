"""Golden scenario tests for incident-postmortem skill."""

import json
import re
import pathlib

import pytest

SKILL_DIR = pathlib.Path(__file__).resolve().parents[2]
GOLDEN_DIR = pathlib.Path(__file__).resolve().parent / "golden"
REFS_DIR = SKILL_DIR / "references"

VALID_TYPES = {"defect", "good_practice", "degradation_scenario", "workflow"}
VALID_SEVERITIES = {"critical", "standard", "hygiene", "none"}
REQUIRED_FIELDS = {
    "id", "title", "type", "severity", "code_snippet",
    "expected_feedback", "lint_expectation", "coverage_rules", "reference",
}


def _all_docs_lower() -> str:
    parts = [(SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")]
    for f in sorted(REFS_DIR.glob("*.md")):
        parts.append(f.read_text(encoding="utf-8"))
    return "\n".join(parts).lower()


def _load_fixtures() -> list[dict]:
    return [json.loads(f.read_text(encoding="utf-8"))
            for f in sorted(GOLDEN_DIR.glob("*.json"))]


def _load(fid: str) -> dict:
    for fx in _load_fixtures():
        if fx["id"] == fid:
            return fx
    raise ValueError(f"fixture {fid} not found")


ALL_DOCS = _all_docs_lower()


# ──────────────────────────────────────────────────────────────────────
class TestFixtureIntegrity:

    def test_minimum_count(self):
        assert len(_load_fixtures()) >= 14

    def test_required_fields(self):
        for fx in _load_fixtures():
            missing = REQUIRED_FIELDS - set(fx.keys())
            assert not missing, f"{fx['id']} missing: {missing}"

    def test_valid_types(self):
        for fx in _load_fixtures():
            assert fx["type"] in VALID_TYPES, f"{fx['id']} bad type"

    def test_valid_severities(self):
        for fx in _load_fixtures():
            assert fx["severity"] in VALID_SEVERITIES

    def test_defect_severity_not_none(self):
        for fx in _load_fixtures():
            if fx["type"] == "defect":
                assert fx["severity"] != "none", fx["id"]

    def test_non_defect_severity_none(self):
        for fx in _load_fixtures():
            if fx["type"] in ("good_practice", "degradation_scenario", "workflow"):
                assert fx["severity"] == "none", fx["id"]

    def test_unique_ids(self):
        ids = [fx["id"] for fx in _load_fixtures()]
        assert len(ids) == len(set(ids))

    def test_coverage_rules_findable(self):
        for fx in _load_fixtures():
            for rule in fx["coverage_rules"]:
                assert rule.lower() in ALL_DOCS, \
                    f"{fx['id']} rule not found: {rule!r}"


# ── Critical Defects ─────────────────────────────────────────────────
class TestPM001:
    """Blame language."""

    @pytest.fixture(autouse=True)
    def _fx(self):
        self.fx = _load("PM-001")

    def test_type_severity(self):
        assert self.fx["type"] == "defect"
        assert self.fx["severity"] == "critical"

    def test_violated_rule(self):
        assert "blameless" in self.fx["violated_rule"].lower() or \
               "systemic" in self.fx["violated_rule"].lower()

    def test_expected_mentions_reframe(self):
        assert "reframe" in self.fx["expected_feedback"].lower() or \
               "blameless" in self.fx["expected_feedback"].lower()


class TestPM002:
    """Unsourced timeline."""

    @pytest.fixture(autouse=True)
    def _fx(self):
        self.fx = _load("PM-002")

    def test_type_severity(self):
        assert self.fx["type"] == "defect"
        assert self.fx["severity"] == "critical"

    def test_violated_rule(self):
        assert "timeline" in self.fx["violated_rule"].lower()

    def test_expected_mentions_source(self):
        assert "source" in self.fx["expected_feedback"].lower()


class TestPM003:
    """Unowned action items."""

    @pytest.fixture(autouse=True)
    def _fx(self):
        self.fx = _load("PM-003")

    def test_type_severity(self):
        assert self.fx["type"] == "defect"
        assert self.fx["severity"] == "critical"

    def test_violated_rule(self):
        assert "owner" in self.fx["violated_rule"].lower() or \
               "deadline" in self.fx["violated_rule"].lower()

    def test_expected_mentions_owner(self):
        assert "owner" in self.fx["expected_feedback"].lower()


# ── Standard Defects ─────────────────────────────────────────────────
class TestPM004:
    """Shallow RCA."""

    @pytest.fixture(autouse=True)
    def _fx(self):
        self.fx = _load("PM-004")

    def test_type_severity(self):
        assert self.fx["type"] == "defect"
        assert self.fx["severity"] == "standard"

    def test_violated_rule(self):
        assert "5-why" in self.fx["violated_rule"].lower() or \
               "depth" in self.fx["violated_rule"].lower()

    def test_expected_mentions_depth(self):
        assert "depth" in self.fx["expected_feedback"].lower()


class TestPM005:
    """No impact metrics."""

    @pytest.fixture(autouse=True)
    def _fx(self):
        self.fx = _load("PM-005")

    def test_type_severity(self):
        assert self.fx["type"] == "defect"
        assert self.fx["severity"] == "standard"

    def test_violated_rule(self):
        assert "metric" in self.fx["violated_rule"].lower() or \
               "impact" in self.fx["violated_rule"].lower()

    def test_expected_mentions_quantify(self):
        assert "duration" in self.fx["expected_feedback"].lower()


class TestPM006:
    """Missing what went well."""

    @pytest.fixture(autouse=True)
    def _fx(self):
        self.fx = _load("PM-006")

    def test_type_severity(self):
        assert self.fx["type"] == "defect"
        assert self.fx["severity"] == "standard"

    def test_violated_rule(self):
        assert "went well" in self.fx["violated_rule"].lower()

    def test_expected_mentions_celebrate(self):
        fb = self.fx["expected_feedback"].lower()
        assert "blameless" in fb or "positive" in fb


class TestPM007:
    """No tracking tickets."""

    @pytest.fixture(autouse=True)
    def _fx(self):
        self.fx = _load("PM-007")

    def test_type_severity(self):
        assert self.fx["type"] == "defect"
        assert self.fx["severity"] == "standard"

    def test_violated_rule(self):
        assert "tracking" in self.fx["violated_rule"].lower() or \
               "follow-up" in self.fx["violated_rule"].lower()

    def test_expected_mentions_jira(self):
        fb = self.fx["expected_feedback"].lower()
        assert "jira" in fb or "ticket" in fb


# ── Good Practices ───────────────────────────────────────────────────
class TestPM008:
    """Well-formed post-mortem."""

    @pytest.fixture(autouse=True)
    def _fx(self):
        self.fx = _load("PM-008")

    def test_type_severity(self):
        assert self.fx["type"] == "good_practice"
        assert self.fx["severity"] == "none"

    def test_expected_positive(self):
        assert "no violation" in self.fx["expected_feedback"].lower()

    def test_expected_mentions_blameless(self):
        assert "blameless" in self.fx["expected_feedback"].lower()


class TestPM009:
    """Well-executed 5-Why RCA."""

    @pytest.fixture(autouse=True)
    def _fx(self):
        self.fx = _load("PM-009")

    def test_type_severity(self):
        assert self.fx["type"] == "good_practice"
        assert self.fx["severity"] == "none"

    def test_expected_positive(self):
        assert "no violation" in self.fx["expected_feedback"].lower()

    def test_expected_mentions_systemic(self):
        assert "systemic" in self.fx["expected_feedback"].lower()


# ── Degradation Scenarios ────────────────────────────────────────────
class TestPM010:
    """Verbal only — sketch mode."""

    @pytest.fixture(autouse=True)
    def _fx(self):
        self.fx = _load("PM-010")

    def test_type_severity(self):
        assert self.fx["type"] == "degradation_scenario"
        assert self.fx["severity"] == "none"

    def test_expected_mentions_degraded(self):
        assert "degraded" in self.fx["expected_feedback"].lower()

    def test_expected_forbids_fabrication(self):
        fb = self.fx["expected_feedback"].lower()
        assert "must not" in fb or "cannot" in fb


class TestPM011:
    """No incident-postmortem — planning mode."""

    @pytest.fixture(autouse=True)
    def _fx(self):
        self.fx = _load("PM-011")

    def test_type_severity(self):
        assert self.fx["type"] == "degradation_scenario"
        assert self.fx["severity"] == "none"

    def test_expected_mentions_template(self):
        assert "template" in self.fx["expected_feedback"].lower()

    def test_expected_mentions_gate_1(self):
        fb = self.fx["expected_feedback"].lower()
        assert "gate 1" in fb or "planning" in fb


# ── Workflow Scenarios ───────────────────────────────────────────────
class TestPM012:
    """Full draft workflow."""

    @pytest.fixture(autouse=True)
    def _fx(self):
        self.fx = _load("PM-012")

    def test_type_severity(self):
        assert self.fx["type"] == "workflow"
        assert self.fx["severity"] == "none"

    def test_expected_mentions_timeline(self):
        assert "timeline" in self.fx["expected_feedback"].lower()

    def test_expected_mentions_5why(self):
        assert "5-why" in self.fx["expected_feedback"].lower()


class TestPM013:
    """Review workflow."""

    @pytest.fixture(autouse=True)
    def _fx(self):
        self.fx = _load("PM-013")

    def test_type_severity(self):
        assert self.fx["type"] == "workflow"
        assert self.fx["severity"] == "none"

    def test_expected_mentions_scorecard(self):
        assert "scorecard" in self.fx["expected_feedback"].lower()

    def test_expected_mentions_what_went_well(self):
        fb = self.fx["expected_feedback"].lower()
        assert "went well" in fb or "missing" in fb


# ── Defect: Recurring Incident ──────────────────────────────────────
class TestPM014:
    """Recurring incident-postmortem — unlinked related incidents."""

    @pytest.fixture(autouse=True)
    def _fx(self):
        self.fx = _load("PM-014")

    def test_type_severity(self):
        assert self.fx["type"] == "defect"
        assert self.fx["severity"] == "standard"

    def test_violated_rule(self):
        vr = self.fx["violated_rule"].lower()
        assert "related" in vr or "linked" in vr

    def test_expected_mentions_prior_incidents(self):
        fb = self.fx["expected_feedback"].lower()
        assert "prior" in fb or "previous" in fb or "related" in fb


# ── Workflow: Cross-team SEV-1 ──────────────────────────────────────
class TestPM015:
    """Cross-team SEV-1 deep analysis."""

    @pytest.fixture(autouse=True)
    def _fx(self):
        self.fx = _load("PM-015")

    def test_type_severity(self):
        assert self.fx["type"] == "workflow"
        assert self.fx["severity"] == "none"

    def test_expected_mentions_deep(self):
        assert "deep" in self.fx["expected_feedback"].lower()

    def test_expected_mentions_multi_team(self):
        fb = self.fx["expected_feedback"].lower()
        assert "multi-team" in fb or "cross-team" in fb


# ── Workflow: Near-miss Analysis ────────────────────────────────────
class TestPM016:
    """Near-miss with real data — SEV-4 analysis."""

    @pytest.fixture(autouse=True)
    def _fx(self):
        self.fx = _load("PM-016")

    def test_type_severity(self):
        assert self.fx["type"] == "workflow"
        assert self.fx["severity"] == "none"

    def test_expected_mentions_near_miss(self):
        fb = self.fx["expected_feedback"].lower()
        assert "near-miss" in fb or "near miss" in fb

    def test_expected_mentions_sev4(self):
        assert "sev-4" in self.fx["expected_feedback"].lower()

# ── Corpus ↔ linter wiring ──────────────────────────────────────────
# Before this class existed, zero fixtures were ever fed to the bundled
# linter, and the flagship "good post-mortem" fixture failed it with a
# critical finding. Every fixture now declares what the linter must do
# with it, and the declaration is verified in both directions.

import importlib.util  # noqa: E402  (kept local to this block)
import sys  # noqa: E402

_LINT_PATH = SKILL_DIR / "scripts" / "lint_postmortem.py"
_spec = importlib.util.spec_from_file_location("lint_postmortem_golden", _LINT_PATH)
lint_postmortem = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
sys.modules[_spec.name] = lint_postmortem
_spec.loader.exec_module(lint_postmortem)

VALID_EXPECTATIONS_PREFIX = ("clean", "not_a_document", "flags:", "misses:")

# The linter's heading regexes are deliberately loose (`^#{1,4}\s+.*timeline`) so
# they match real-world headings like "## Timeline (UTC, all sourced)". That makes
# them wrong for *this* guard: the prompt fixtures use `# User says: ...` comment
# lines, and "# Document has timeline, root cause, action items" would read as both
# headings at once. A section heading names its section, so anchor on the start of
# the heading text.
SECTION_HEADING_RE = {
    "timeline": re.compile(r"(?mi)^#{1,4}\s+timeline\b"),
    "action items": re.compile(r"(?mi)^#{1,4}\s+action items?\b"),
}


class TestLintExpectations:
    """Each fixture's declared lint_expectation must hold against the real linter."""

    def test_expectation_vocabulary(self):
        for fx in _load_fixtures():
            exp = fx["lint_expectation"]
            assert exp.startswith(VALID_EXPECTATIONS_PREFIX), \
                f"{fx['id']} has unknown lint_expectation {exp!r}"

    def test_named_checks_exist(self):
        """A flags:/misses: expectation must name a check the linter can emit."""
        emitted = set()
        for fx in _load_fixtures():
            for f in lint_postmortem.lint(fx["code_snippet"]):
                emitted.add(f.check)
        # Every check the linter documents, so a typo'd name cannot pass silently.
        documented = {
            "timeline-utc", "timeline-source", "timeline-untimed", "timeline-order",
            "timeline-timezone", "action-owner", "action-deadline",
            "action-categories", "went-well", "uncovered-risks", "blame-language",
            "sensitive-data",
        }
        assert emitted <= documented, f"undocumented check emitted: {emitted - documented}"
        for fx in _load_fixtures():
            exp = fx["lint_expectation"]
            if ":" in exp:
                name = exp.split(":", 1)[1]
                assert name in documented, f"{fx['id']} names unknown check {name!r}"

    def test_clean_fixtures_are_actually_clean(self):
        for fx in _load_fixtures():
            if fx["lint_expectation"] != "clean":
                continue
            findings = lint_postmortem.lint(fx["code_snippet"])
            assert findings == [], \
                f"{fx['id']} is declared lint-clean but reports: " \
                + "; ".join(str(f) for f in findings)

    def test_flags_fixtures_trigger_their_check(self):
        for fx in _load_fixtures():
            exp = fx["lint_expectation"]
            if not exp.startswith("flags:"):
                continue
            want = exp.split(":", 1)[1]
            names = {f.check for f in lint_postmortem.lint(fx["code_snippet"])}
            assert want in names, \
                f"{fx['id']} declares flags:{want} but linter reported {sorted(names)}"

    def test_misses_fixtures_document_the_judgment_boundary(self):
        """SKILL.md §8 claims judgment items stay with the reviewer. Prove it.

        A `misses:` fixture asserts the mechanical layer genuinely cannot catch
        this defect — so the claim is tested, not just asserted in prose.
        """
        for fx in _load_fixtures():
            exp = fx["lint_expectation"]
            if not exp.startswith("misses:"):
                continue
            want = exp.split(":", 1)[1]
            names = {f.check for f in lint_postmortem.lint(fx["code_snippet"])}
            assert want not in names, \
                f"{fx['id']} declares misses:{want}, but the linter now catches it — " \
                f"promote the fixture to flags:{want}"

    def test_not_a_document_label_cannot_hide_a_broken_document(self):
        """Guard the guard: `not_a_document` must be an excerpt or a prompt.

        Without this, any full document that fails the linter could be silenced
        by relabelling it.
        """
        for fx in _load_fixtures():
            if fx["lint_expectation"] != "not_a_document":
                continue
            snippet = fx["code_snippet"]
            has_both = all(rx.search(snippet) for rx in SECTION_HEADING_RE.values())
            assert not has_both, \
                f"{fx['id']} has both Timeline and Action Items sections, so it is a " \
                f"whole document and must declare clean/flags:, not not_a_document"

    def test_the_not_a_document_guard_has_teeth(self):
        """Guard the guard: it must reject a full document and accept a prompt.

        Anchoring too loosely made `# Document has timeline, ... action items` (a
        prompt comment) read as two headings; anchoring at all is pointless if it
        stops recognising a real document.
        """
        real_doc = "# PM\n\n## Timeline (UTC)\n- 14:23 x (log)\n\n## Action Items\n- y\n"
        assert all(rx.search(real_doc) for rx in SECTION_HEADING_RE.values()), \
            "guard must recognise a genuine whole document"
        prompt = ("# User provides a post-mortem and says: 'Review this'\n"
                  "# Document has timeline, root cause, action items, but no tests\n")
        assert not all(rx.search(prompt) for rx in SECTION_HEADING_RE.values()), \
            "guard must not read prompt prose as section headings"

    def test_at_least_one_clean_and_one_flags_fixture(self):
        exps = [fx["lint_expectation"] for fx in _load_fixtures()]
        assert "clean" in exps, "corpus must contain a lint-clean reference document"
        assert any(e.startswith("flags:") for e in exps), \
            "corpus must contain a fixture that the linter actually rejects"


class TestTemplateWorkedExample:
    """The template's own worked example must pass the skill's own linter.

    This is the regression that shipped: a document written in the official
    template's format drew `[critical] timeline has no HH:MM-stamped entries`,
    because the linter only understood `-`-prefixed timeline entries.
    """

    def _example(self) -> str:
        text = (REFS_DIR / "postmortem-template.md").read_text(encoding="utf-8")
        m = re.search(
            r"<!-- WORKED-EXAMPLE-BEGIN -->\s*```markdown\n(.*?)\n```\s*"
            r"<!-- WORKED-EXAMPLE-END -->", text, re.S)
        assert m, "template must carry a delimited worked example"
        return m.group(1)

    def test_example_is_present_and_substantial(self):
        assert len(self._example().splitlines()) >= 50

    def test_example_lints_clean(self):
        findings = lint_postmortem.lint(self._example())
        assert findings == [], \
            "template worked example must pass the bundled linter: " \
            + "; ".join(str(f) for f in findings)

    def test_example_uses_bare_timeline_and_table_actions(self):
        """Pin the two formats the old linter could not read."""
        ex = self._example()
        assert re.search(r"(?m)^\d{2}:\d{2} \[[A-Z]+\]", ex), \
            "example must exercise bare `HH:MM [PHASE]` timeline entries"
        assert re.search(r"(?m)^\| AI-\d+ \|", ex), \
            "example must exercise the Markdown action-items table"

    def test_template_documents_mandatory_sections(self):
        text = (REFS_DIR / "postmortem-template.md").read_text(encoding="utf-8")
        required = text.split("## 2 Incident Summary Template")[0]
        for section in ("## Mode & Depth", "## Uncovered Risks"):
            assert section in required, \
                f"template Required Sections must list {section} (SKILL.md §9)"
