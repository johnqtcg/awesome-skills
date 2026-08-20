"""Tests for the report-fidelity audit.

The regression: the publication gate checked only that each finding's **ID appeared
as a substring** of `report.md`. That catches a *dropped* finding and nothing else.
Keep the ID and rewrite the evidence, soften the implication, or swap the citation,
and the bundle still passed — so "faithful synthesis" was checkable in exactly one
direction, and not the one that matters. A report distorts far more easily than it
loses.

Every test below is one way of distorting a finding while keeping its ID.
"""
import copy
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from finlib import report_audit as RA  # noqa: E402

FINDING = {
    "id": "BUS-11",
    "severity": "High",
    "title": "Client incentives at 38% of gross revenue",
    "citation": {"source": "10-K", "locator": "Note 1 Revenue recognition",
                 "fiscal_period": "FY2025"},
    "evidence": "Gross revenue $38.2B less client incentives $14.5B = net revenue $23.7B; "
                "incentives/gross 38.0% vs 34.1% FY2022",
    "implication": "Reported net-revenue growth understates volume growth and overstates "
                   "pricing power.",
    "confidence": "first-hand",
    "reported_by": "BUS",
}

CONSOLIDATED = {"findings": [FINDING]}


def render(finding: dict, **override) -> str:
    """Render a finding the way the Output Format specifies."""
    f = {**finding, **override}
    citation = override.get(
        "citation_line",
        f"{f['citation']['source']} {f['citation']['locator']} ({f['citation']['fiscal_period']})",
    )
    return (
        "# MSFT — Investment Analysis Report\n\n"
        "## Worker Findings / 各维度发现\n\n"
        f"### [{f['severity']}] {f['title']}\n\n"
        f"- **ID**: `{f['id']}`\n"
        f"- **Citation**: {citation}\n"
        f"- **Evidence**: {f['evidence']}\n"
        f"- **Implication**: {f['implication']}\n\n"
        "## Risks I Accept\n\n1. Something else.\n"
    )


# --------------------------------------------------------------------------- #
# the faithful case
# --------------------------------------------------------------------------- #

def test_a_faithful_report_passes():
    assert RA.audit(CONSOLIDATED, render(FINDING)) == []


def test_surrounding_prose_and_emphasis_are_allowed():
    """The report may bold a number, wrap a long quote, or add context. None of
    that changes what it asserts."""
    report = (
        "# MSFT\n\n## Worker Findings\n\n"
        "### [High] Client incentives at 38% of gross revenue\n\n"
        "- **ID**: `BUS-11` (business worker)\n"
        "- **Citation**: 10-K **Note 1 Revenue recognition**, FY2025, page 71\n"
        "- **Evidence**: Per the filing — Gross revenue $38.2B less client incentives\n"
        "  $14.5B = net revenue $23.7B; incentives/gross 38.0% vs 34.1% FY2022\n"
        "- **Implication**: Reported net-revenue growth understates volume growth and\n"
        "  overstates pricing power. This caps the Bull multiple.\n"
    )
    assert RA.audit(CONSOLIDATED, report) == []


def test_empty_consolidation_and_empty_report_agree():
    assert RA.audit({"findings": []}, "# MSFT\n\nNo findings.\n") == []


# --------------------------------------------------------------------------- #
# distortion — the class the old ID check could not see
# --------------------------------------------------------------------------- #

def test_rewritten_evidence_is_caught():
    report = render(FINDING, evidence="Client incentives are a modest headwind.")
    errors = RA.audit(CONSOLIDATED, report)
    assert any("evidence does not carry the worker's text" in e for e in errors), errors


def test_softened_implication_is_caught():
    report = render(FINDING, implication="Management is managing this well.")
    errors = RA.audit(CONSOLIDATED, report)
    assert any("implication does not carry the worker's text" in e for e in errors), errors


def test_swapped_citation_is_caught():
    report = render(FINDING, citation_line="Q3 earnings call, CFO remarks")
    errors = RA.audit(CONSOLIDATED, report)
    assert any("does not contain the worker's locator" in e for e in errors), errors


def test_downgraded_severity_is_caught():
    report = render(FINDING, severity="Low")
    errors = RA.audit(CONSOLIDATED, report)
    assert any("severity" in e for e in errors), errors


def test_a_truncated_quote_is_caught():
    """Dropping the second half of a computed figure removes the comparison that
    made it a finding."""
    report = render(FINDING, evidence="Gross revenue $38.2B less client incentives $14.5B")
    assert any("evidence" in e for e in RA.audit(CONSOLIDATED, report))


def test_a_changed_number_inside_the_quote_is_caught():
    report = render(FINDING, evidence=FINDING["evidence"].replace("38.0%", "18.0%"))
    assert any("evidence" in e for e in RA.audit(CONSOLIDATED, report))


# --------------------------------------------------------------------------- #
# omission and fabrication
# --------------------------------------------------------------------------- #

def test_an_omitted_finding_is_caught():
    errors = RA.audit(CONSOLIDATED, "# MSFT\n\n## Worker Findings\n\nNothing material.\n")
    assert any("omits finding BUS-11" in e for e in errors), errors


def test_a_fabricated_finding_is_caught():
    """A finding no worker returned is the mirror image of a dropped one."""
    report = render(FINDING) + (
        "\n### [High] Undisclosed related-party transactions\n\n"
        "- **ID**: `BUS-99`\n- **Citation**: 10-K Item 13\n"
        "- **Evidence**: invented\n- **Implication**: invented\n"
    )
    errors = RA.audit(CONSOLIDATED, report)
    assert any("BUS-99, which is not in consolidated.json" in e for e in errors), errors


def test_a_duplicated_finding_is_caught():
    report = render(FINDING) + render(FINDING).split("## Worker Findings / 各维度发现\n\n")[1]
    errors = RA.audit(CONSOLIDATED, report)
    assert any("2 times" in e for e in errors), errors


def test_a_block_without_an_id_is_caught():
    report = (
        "# MSFT\n\n## Worker Findings\n\n"
        "### [High] Client incentives at 38% of gross revenue\n\n"
        "- **Citation**: 10-K Note 1 Revenue recognition\n"
        "- **Evidence**: something\n- **Implication**: something\n"
    )
    errors = RA.audit(CONSOLIDATED, report)
    assert any("has no **ID** line" in e for e in errors), errors


@pytest.mark.parametrize("field", ["Citation", "Evidence", "Implication"])
def test_a_missing_required_line_is_caught(field):
    report = render(FINDING)
    report = "\n".join(l for l in report.splitlines() if f"**{field}**" not in l)
    errors = RA.audit(CONSOLIDATED, report)
    assert any(f"no **{field}** line" in e for e in errors), errors


# --------------------------------------------------------------------------- #
# parsing
# --------------------------------------------------------------------------- #

def test_parser_finds_every_block():
    two = {"findings": [FINDING, {**FINDING, "id": "EQ-04", "title": "Margin compression",
                                  "reported_by": "EQ"}]}
    report = render(FINDING) + render(two["findings"][1]).split("## Worker Findings / 各维度发现\n\n")[1]
    assert len(RA.parse_findings(report)) == 2
    assert RA.audit(two, report) == []


def test_parser_stops_at_the_next_h2_section():
    """A `- **Evidence**:` bullet in a later section must not be absorbed into the
    last finding block."""
    report = render(FINDING) + (
        "\n## Data Coverage\n\n- **Evidence**: unrelated bullet that must not be absorbed\n"
    )
    blocks = RA.parse_findings(report)
    assert len(blocks) == 1
    assert "unrelated bullet" not in blocks[0]["Evidence"]
    assert RA.audit(CONSOLIDATED, report) == []


def test_parser_ignores_non_finding_h3_headings():
    report = render(FINDING).replace(
        "## Risks I Accept", "### Some other subsection\n\nprose\n\n## Risks I Accept")
    assert len(RA.parse_findings(report)) == 1


def test_normalize_collapses_wrapping_and_emphasis():
    assert RA.normalize("a  **b**\n  c `d`") == "a b c d"


def test_normalize_handles_non_breaking_space():
    """A pasted quote can carry U+00A0, which would fail a naive comparison."""
    assert RA.normalize("a b") == "a b"


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def test_cli_exit_codes(tmp_path, capsys):
    consolidated = tmp_path / "consolidated.json"
    consolidated.write_text(json.dumps(CONSOLIDATED), encoding="utf-8")
    report = tmp_path / "report.md"

    report.write_text(render(FINDING), encoding="utf-8")
    assert RA.main(["check", "--report", str(report), "--consolidated", str(consolidated)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["verdict"] == "PASS" and out["blocks_parsed"] == 1

    report.write_text(render(FINDING, evidence="paraphrased away"), encoding="utf-8")
    assert RA.main(["check", "--report", str(report), "--consolidated", str(consolidated)]) == 1
    assert json.loads(capsys.readouterr().out)["verdict"] == "FAIL"


def test_output_format_reference_matches_what_the_parser_expects():
    """The audit is only possible because the Output Format promises this shape.
    If the two drift, every real report fails the gate for the wrong reason.

    The template lives in `references/output-format.md`; SKILL.md carries the
    pointer plus the fidelity rule."""
    root = os.path.join(os.path.dirname(__file__), "..", "..")
    with open(os.path.join(root, "references", "output-format.md"), encoding="utf-8") as f:
        template = f.read()
    for line in ("- **ID**:", "- **Citation**:", "- **Evidence**:", "- **Implication**:"):
        assert line in template, f"the Output Format no longer specifies {line!r}"
    assert "### [High|Medium|Low]" in template, (
        "the Output Format no longer specifies the bracketed-severity heading the"
        " parser keys on"
    )
    with open(os.path.join(root, "SKILL.md"), encoding="utf-8") as f:
        lead = f.read()
    assert "references/output-format.md" in lead, "SKILL.md no longer points at the template"
    assert "report_audit.py" in lead, "SKILL.md no longer states the fidelity rule"


def test_a_report_rendered_from_the_reference_template_parses():
    """Mutation-proofing the pairing: the shape in the reference must actually
    survive the parser, not merely contain the right substrings."""
    root = os.path.join(os.path.dirname(__file__), "..", "..")
    with open(os.path.join(root, "references", "output-format.md"), encoding="utf-8") as f:
        template = f.read()
    filled = (
        template[template.index("### [High|Medium|Low] Short Title"):]
        .split("\n\n## ")[0]
        .replace("[High|Medium|Low]", "[High]")
        .replace("Short Title", FINDING["title"])
        .replace("`BUS-11` (the worker's own Finding ID from consolidated.json — BUS / EQ / BS / MGT / IND / P)",
                 f"`{FINDING['id']}`")
        .replace("must contain the worker's citation `locator` verbatim",
                 FINDING["citation"]["locator"])
        .replace("the worker's `evidence` **verbatim** (surrounding prose allowed; substitution is not)",
                 FINDING["evidence"])
        .replace("the worker's `implication` **verbatim** (you may add to it, not replace it)",
                 FINDING["implication"])
    )
    blocks = RA.parse_findings("## Worker Findings\n\n" + filled)
    assert len(blocks) == 1, blocks
    assert RA.audit(CONSOLIDATED, "## Worker Findings\n\n" + filled) == []
