"""Consistency tests for references/example-output.md.

The worked example is what the model imitates, so an internal contradiction there
propagates into every report the skill produces. These tests check the example
against the rules SKILL.md states, rather than checking that prose exists.

Tables are parsed as data. Assertions anchored to particular sentences pass on an
inverted claim and fail on a harmless rewording, so they are avoided here.
"""

from __future__ import annotations

import pathlib
import re

import pytest

SKILL_DIR = pathlib.Path(__file__).resolve().parents[2]
EXAMPLE = (SKILL_DIR / "references" / "example-output.md").read_text(encoding="utf-8")
SKILL_MD = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")

OUT_OF_SCOPE = re.compile(r"out of scope", re.IGNORECASE)


def _section(title: str) -> str:
    """Body of a `### <title>` section, up to the next heading of the same level."""
    m = re.search(rf"^### {re.escape(title)}\s*$(.*?)(?=^#{{1,3}} |\Z)",
                  EXAMPLE, re.MULTILINE | re.DOTALL)
    assert m, f"section not found in example: {title}"
    return m.group(1)


def _rows(section_body: str) -> list[list[str]]:
    """Data rows of the first markdown table in a section."""
    rows = []
    for line in section_body.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if all(set(c) <= set("-: ") for c in cells):  # separator row
            continue
        rows.append(cells)
    assert rows, "no table rows found"
    return rows[1:]  # drop the header


def _scanned_services() -> set[str]:
    """Services named in the `Source:` line of Window & Source."""
    body = _section("Window & Source")
    m = re.search(r"`Source:`?(.*?)(?=\n- `Coverage)", body, re.DOTALL)
    assert m, "Source: line not found"
    return set(re.findall(r"app=([a-z0-9-]+)", m.group(1)))


SCANNED = _scanned_services()


# ──────────────────────────────────────────────────────────────────────
class TestScopeClosure:
    """SKILL.md Evidence Rules: every component is scanned or marked out of scope."""

    def test_source_line_names_services(self):
        assert SCANNED, "could not parse any scanned service from Source:"

    @pytest.mark.parametrize("section", ["Timeline", "Correlation Map"])
    def test_every_row_is_scanned_or_marked(self, section):
        unmarked = []
        for cells in _rows(_section(section)):
            service = cells[1]
            row = " | ".join(cells)
            if service in SCANNED:
                continue
            if OUT_OF_SCOPE.search(row):
                continue
            if service in {"window end", "n/a", "—", "-"}:
                continue
            unmarked.append(service)
        assert not unmarked, (
            f"{section} cites un-scanned components without an out-of-scope marker: "
            f"{sorted(set(unmarked))}. Scanned: {sorted(SCANNED)}"
        )

    @pytest.mark.parametrize("section", ["Timeline", "Correlation Map"])
    def test_marker_is_on_the_row_not_only_in_residual_risk(self, section):
        """A note at the bottom does not discharge the rule -- the reader meets the
        row first. This is the specific defect the rule was written for."""
        body = _section(section)
        offenders = [c[1] for c in _rows(body) if c[1] not in SCANNED
                     and c[1] not in {"window end", "n/a", "—", "-"}]
        assert offenders, "fixture drift: expected the example to contain out-of-scope rows"
        for cells in _rows(body):
            if cells[1] in offenders:
                assert OUT_OF_SCOPE.search(" | ".join(cells)), \
                    f"row for {cells[1]!r} in {section} lacks an inline marker"

    def test_out_of_scope_components_are_not_in_the_source_line(self):
        """Guards the opposite fix: silencing the test by widening Source: without
        actually scanning those logs."""
        assert "gateway" not in SCANNED, \
            "gateway was added to Source: -- either scan it or keep it marked"

    def test_coverage_is_partial_when_rows_are_out_of_scope(self):
        """Coverage is judged against the incident, not against the sources you
        happened to pick. If the request path leaves the scanned set, the window
        is partial however completely those services were read."""
        body = _section("Window & Source")
        m = re.search(r"`Coverage:\s*(\w+)", body)
        assert m, "Coverage: field not found"
        has_out_of_scope = any(
            OUT_OF_SCOPE.search(" | ".join(cells))
            for s in ("Timeline", "Correlation Map") for cells in _rows(_section(s))
        )
        if has_out_of_scope:
            assert m.group(1).lower() == "partial", (
                "the report marks rows out of scope yet claims Coverage: "
                f"{m.group(1)} -- those two statements contradict each other"
            )


# ──────────────────────────────────────────────────────────────────────
class TestEvidenceCompleteness:
    """SKILL.md Evidence Rules: every finding carries a redacted 1-5 line sample
    and a location that is where the evidence was READ."""

    def _finding_blocks(self) -> list[tuple[str, str]]:
        parts = re.split(r"^#### \[(?:High|Medium|Low)\] ", EXAMPLE, flags=re.MULTILINE)[1:]
        out = []
        for p in parts:
            body = re.split(r"^### ", p, flags=re.MULTILINE)[0]
            fid = re.search(r"\*\*ID:\*\* `(LOG-\d+)`", body)
            out.append((fid.group(1) if fid else p.splitlines()[0], body))
        return out

    @pytest.mark.parametrize("idx", range(2))
    def test_every_finding_has_a_fenced_evidence_sample(self, idx):
        blocks = self._finding_blocks()
        assert idx < len(blocks), f"expected at least {idx + 1} findings"
        fid, body = blocks[idx]
        fenced = re.findall(r"```\n(.*?)```", body, re.DOTALL)
        assert fenced, f"{fid} has no fenced evidence block"
        lines = [l for b in fenced for l in b.strip().splitlines()]
        assert 1 <= len(lines) <= 5, f"{fid} evidence is {len(lines)} lines, rule is 1-5"

    @pytest.mark.parametrize("idx", range(2))
    def test_location_is_a_log_source_not_a_code_path(self, idx):
        """`server.go` names where the bug probably lives, not where the evidence
        was read. Conflating them makes a finding unverifiable."""
        fid, body = self._finding_blocks()[idx]
        m = re.search(r"\*\*Location:\*\* (.+)", body)
        assert m, f"{fid} has no Location"
        loc = m.group(1)
        head = loc.split("*(")[0]  # text before any parenthetical aside
        assert re.search(r"kubectl logs|journalctl|\.log|\.jsonl|aggregator|pods?,|slog field", head), (
            f"{fid} Location does not name a log source: {head!r}"
        )


# ──────────────────────────────────────────────────────────────────────
class TestHandoffHonesty:
    """The hand-off block is consumed verbatim by incident-postmortem, so an
    unverified mechanism stated as fact propagates into the published RCA."""

    def _handoff(self) -> str:
        m = re.search(r"### Hand-off Protocol\n```\n(.*?)```", EXAMPLE, re.DOTALL)
        assert m, "hand-off block not found"
        return m.group(1)

    def test_blameless_framing_does_not_assert_the_unverified_mechanism(self):
        framing = re.search(r"blameless_framing:(.*?)(?=\n\w+:|\Z)",
                            self._handoff(), re.DOTALL).group(1)
        asserts_cause = re.search(
            r"\b(reduced|caused|introduced|set|lowered)\b", framing, re.IGNORECASE)
        hedged = re.search(r"not established|suspected|NOT\b|unverified|do not write",
                           framing, re.IGNORECASE)
        assert hedged or not asserts_cause, (
            "blameless_framing states the concurrency mechanism as fact while the "
            "report labels it a hypothesis: " + framing.strip()[:160]
        )

    def test_a_measured_observation_is_not_labelled_hypothesis(self):
        """A directly counted fact keeps Confirmed even when its explanation is a
        hypothesis. Downgrading the whole finding invites the reader to discount
        the measurement along with the guess."""
        blocks = re.split(r"^#### \[(?:High|Medium|Low)\] ", EXAMPLE, flags=re.MULTILINE)[1:]
        obs = [b for b in blocks if "lack `trace_id`" in b or "empty `trace_id`" in b]
        assert obs, "expected the observability finding in the example"
        conf = re.search(r"\*\*Confidence:\*\* `?([^`\n]+)`?", obs[0]).group(1)
        assert "Confirmed" in conf, (
            "the 14% figure is counted directly from the scanned logs, so the "
            f"finding is Confirmed; got {conf!r}"
        )
        assert re.search(r"hypothesis", obs[0], re.IGNORECASE), \
            "the proposed cause must still be labelled a hypothesis"

    def test_rollback_is_framed_as_a_test_not_a_cure(self):
        """While causation is unconfirmed, a recommendation promising recovery
        asserts the causal claim the report explicitly withheld."""
        body = _section("Recommendations")
        first = body.strip().splitlines()[0]
        assert re.search(r"roll ?back", first, re.IGNORECASE), \
            "expected rollback as the first recommendation"
        assert re.search(r"test of|hypothesis|if the deploy is|refut", first, re.IGNORECASE), (
            "the rollback must be framed as testing the deploy hypothesis: " + first[:140]
        )
        assert not re.search(r"error rate to 0 within", first), \
            "promises recovery from an unconfirmed cause"

    def test_leading_hypothesis_flags_the_unscanned_source(self):
        lh = re.search(r"leading_hypothesis:(.*?)(?=\n\w+:|\Z)",
                       self._handoff(), re.DOTALL).group(1)
        assert re.search(r"unverified|not scanned|needs corroboration", lh, re.IGNORECASE), \
            "leading_hypothesis must carry its own uncertainty into the post-mortem"


# ──────────────────────────────────────────────────────────────────────
class TestCascadeOneFindingRule:
    """log-cascade-analysis.md: report ONE finding for the cause; symptoms fold in."""

    def _findings(self) -> list[tuple[str, str]]:
        return re.findall(r"^#### \[(High|Medium|Low)\] (.+)$", EXAMPLE, re.MULTILINE)

    def test_single_high_availability_finding(self):
        highs = [t for sev, t in self._findings() if sev == "High"]
        assert len(highs) == 1, (
            f"expected one High cause finding for a single cascade, found {len(highs)}: "
            f"{highs}. A symptom cluster reported as its own High finding double-counts "
            f"the incident."
        )

    def test_symptom_cluster_is_suppressed_not_dropped(self):
        suppressed = _section("Suppressed Items")
        assert re.search(r"symptom cluster", suppressed, re.IGNORECASE), \
            "the symptom cluster must appear in Suppressed Items with its reason"
        assert re.search(r"re-?open", suppressed, re.IGNORECASE), \
            "suppression must state the condition that re-opens it as a finding"

    def test_finding_ids_are_contiguous_and_match_handoff(self):
        defined = re.findall(r"\*\*ID:\*\* `(LOG-\d+)`", EXAMPLE)
        assert defined == sorted(defined), "finding IDs are out of order"
        assert defined == [f"LOG-{i:03d}" for i in range(1, len(defined) + 1)], \
            f"finding IDs must be contiguous from LOG-001, got {defined}"
        m = re.search(r"top_findings: \[(.*?)\]", EXAMPLE)
        assert m, "hand-off block missing top_findings"
        listed = [x.strip() for x in m.group(1).split(",") if x.strip()]
        assert listed == defined, (
            f"hand-off top_findings {listed} does not match the findings actually "
            f"defined {defined} -- a dangling ID breaks the incident-postmortem hand-off"
        )


# ──────────────────────────────────────────────────────────────────────
class TestConfidenceDiscipline:
    """Gate 6: a link sourced outside the scanned logs is never Confirmed."""

    def test_deploy_attribution_is_not_confirmed(self):
        summary = _section("Summary") + _section("Executive Summary")
        assert not re.search(r"confirmed cause:.*deploy", summary, re.IGNORECASE), \
            ("the Summary claims the deploy as a Confirmed cause, but the deploy "
             "timestamp comes from an un-scanned source")

    def test_deploy_link_labelled_needs_corroboration(self):
        assert re.search(r"needs corroboration", EXAMPLE, re.IGNORECASE), \
            "the out-of-scope deploy link must carry a needs-corroboration label"

    def test_origin_breakdown_totals_match_findings(self):
        m = re.search(r"(\d+) confirmed / (\d+) hypothesis / (\d+) needs-corroboration",
                      EXAMPLE)
        assert m, "Executive Summary must carry an origin breakdown"
        assert sum(int(g) for g in m.groups()) > 0


# ──────────────────────────────────────────────────────────────────────
class TestExampleFollowsCurrentContract:

    def test_execution_status_records_gate_outcomes(self):
        body = _section("Execution Status")
        assert "Gate outcomes" in body, \
            "Execution Status must record which gates fired and in which class"
        assert re.search(r"\b(BLOCK|DEGRADE|WARN|CAP)\b", body), \
            "gate outcomes must name the gate class"

    def test_redaction_reports_the_tool_actually_used(self):
        body = _section("Execution Status")
        assert "redact_log.py" in body, \
            "the example must demonstrate the shipped redactor, not hand-waved redaction"

    def test_no_forbidden_command_demonstrated(self):
        """The example must not teach a form the Command Safety Contract forbids."""
        for bad in ("sed -i", "sort -o ", "gzip app.log", "--vacuum-", "rg --pre"):
            assert bad not in EXAMPLE, f"example demonstrates a forbidden form: {bad}"

    def test_quoted_evidence_is_redacted(self):
        for block in re.findall(r"```\n(.*?)```", EXAMPLE, re.DOTALL):
            assert not re.search(r"Bearer\s+(?!\*\*\*)[A-Za-z0-9._-]{8,}", block), \
                "an evidence block quotes an unredacted bearer token"
