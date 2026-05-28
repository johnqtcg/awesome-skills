"""Zero-LLM contract tests for stock-analysis-lead (orchestrator).

Verifies the structural shape of the orchestrator skill: frontmatter,
required sections, dispatch references to all 5 worker skills, references
files present, and length below the repo's 500-line limit.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

SKILL_ROOT = Path(__file__).resolve().parents[2]
SKILL_MD = SKILL_ROOT / "SKILL.md"
REFERENCES_DIR = SKILL_ROOT / "references"

MAX_SKILL_LINES = 500

REQUIRED_REFERENCES = [
    "data-acquisition-playbook.md",
    "good-company-checklist.md",
    "valuation-methods.md",
    "scenario-framework.md",
    "cognitive-bias-gates.md",
    "sector-archetypes.md",
    "earnings-revision-momentum.md",
    "verdict-log-protocol.md",
    "scenario-probability-calibration.md",
]

REQUIRED_SECTIONS = [
    "Purpose",
    "Quick Reference",
    "When To Use",
    "When NOT To Use",
    "Workflow",
    "Output Format",
    "Consolidation Rules",
]

REQUIRED_WORKER_SKILLS = [
    "stock-business-review",
    "stock-earnings-quality-review",
    "stock-balance-sheet-review",
    "stock-management-review",
    "stock-industry-review",
    "stock-peer-comparison-review",
]


@pytest.fixture(scope="module")
def skill_text() -> str:
    assert SKILL_MD.exists(), f"SKILL.md not found at {SKILL_MD}"
    return SKILL_MD.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def frontmatter(skill_text: str) -> dict[str, str]:
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", skill_text, re.DOTALL)
    assert match, "SKILL.md must start with a YAML frontmatter block"
    fm: dict[str, str] = {}
    current_key: str | None = None
    for raw_line in match.group(1).splitlines():
        if not raw_line.strip():
            continue
        if raw_line.startswith(" ") and current_key is not None:
            fm[current_key] = (fm[current_key] + " " + raw_line.strip()).strip()
            continue
        if ":" in raw_line:
            key, _, value = raw_line.partition(":")
            current_key = key.strip()
            fm[current_key] = value.strip()
    return fm


def test_skill_md_exists() -> None:
    assert SKILL_MD.exists()


def test_skill_md_under_line_limit(skill_text: str) -> None:
    line_count = len(skill_text.splitlines())
    assert line_count <= MAX_SKILL_LINES, f"{line_count} lines > {MAX_SKILL_LINES}"


def test_frontmatter_required_fields(frontmatter: dict[str, str]) -> None:
    for field in ("name", "description", "allowed-tools"):
        assert field in frontmatter, f"missing frontmatter field: {field}"
        assert frontmatter[field], f"empty frontmatter field: {field}"


def test_skill_name(frontmatter: dict[str, str]) -> None:
    assert frontmatter["name"] == "stock-analysis-lead"


def test_description_rejects_non_us(frontmatter: dict[str, str]) -> None:
    desc = frontmatter["description"]
    assert "A-shares" in desc and "HK" in desc, (
        "description must explicitly state non-US scope rejection"
    )
    assert "10-K" in desc or "SEC" in desc, (
        "description must mention SEC/10-K to anchor on US filings"
    )


def test_description_lists_negative_routes(frontmatter: dict[str, str]) -> None:
    desc = frontmatter["description"]
    for negative in ("technical analysis", "options", "crypto", "ETFs"):
        assert negative in desc, f"description must list out-of-scope: {negative}"


def test_required_sections_present(skill_text: str) -> None:
    for header in REQUIRED_SECTIONS:
        pattern = rf"(?mi)^#{{1,6}}\s+.*{re.escape(header)}"
        assert re.search(pattern, skill_text), f"missing section: {header}"


def test_dispatches_all_workers(skill_text: str) -> None:
    for worker_skill in REQUIRED_WORKER_SKILLS:
        assert worker_skill in skill_text, (
            f"orchestrator must reference worker skill: {worker_skill}"
        )


def test_synthesis_step_has_required_subcomponents(skill_text: str) -> None:
    for component in (
        "Good-Company",
        "Bull",
        "Base",
        "Bear",
        "Cognitive-Bias",
        "Reverse-DCF",
    ):
        assert component in skill_text, f"synthesis missing component: {component}"


def test_output_contract_has_required_sections(skill_text: str) -> None:
    for output_section in (
        "Verdict",
        "Good-Company Score",
        "Bull / Base / Bear",
        "Risks I Accept",
        "Invalidation Conditions",
        "Data Coverage",
        "Cognitive-Bias Self-Check",
    ):
        assert output_section in skill_text, (
            f"output format missing: {output_section}"
        )


def test_chinese_labels_present(skill_text: str) -> None:
    """The output contract must include CN labels so the skill renders
    correctly when invoked in Chinese."""
    for cn_label in (
        "顶层结论",
        "好公司评分",
        "三档情景",
        "我接受的风险",
        "卖出触发器",
        "认知偏差自检",
    ):
        assert cn_label in skill_text, f"missing Chinese label: {cn_label}"


def test_required_references_exist() -> None:
    for ref in REQUIRED_REFERENCES:
        path = REFERENCES_DIR / ref
        assert path.exists(), f"missing reference: {path}"
        assert path.stat().st_size > 1000, f"reference {ref} suspiciously small"


def test_references_loaded_by_skill(skill_text: str) -> None:
    for ref in REQUIRED_REFERENCES:
        assert ref in skill_text, (
            f"reference {ref} never mentioned in SKILL.md — broken disclosure"
        )


def test_non_us_refusal_message_present(skill_text: str) -> None:
    assert "SEC 10-K/10-Q filers" in skill_text or "non-US" in skill_text.lower(), (
        "SKILL.md must include the non-US refusal logic"
    )


def test_verdict_options_present(skill_text: str) -> None:
    for verdict in ("Strong Buy", "Buy", "Watch", "Hold", "Trim", "Sell"):
        assert verdict in skill_text, f"verdict option missing: {verdict}"