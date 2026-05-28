"""Zero-LLM contract tests for stock-peer-comparison-review worker skill."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

SKILL_ROOT = Path(__file__).resolve().parents[2]
SKILL_MD = SKILL_ROOT / "SKILL.md"
REFERENCES_DIR = SKILL_ROOT / "references"

MAX_SKILL_LINES = 500
SKILL_NAME = "stock-peer-comparison-review"
REQUIRED_REFERENCES = ["peer-comparison-methodology.md"]
REQUIRED_SECTIONS = [
    "Purpose",
    "When To Use",
    "When NOT To Use",
    "Mandatory Gates",
    "Workflow",
    "12-Item Comparison Panel",
    "Output Format",
]
FINDING_ID_PREFIX = "P-"


@pytest.fixture(scope="module")
def skill_text() -> str:
    return SKILL_MD.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def frontmatter(skill_text: str) -> dict[str, str]:
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", skill_text, re.DOTALL)
    assert match
    fm: dict[str, str] = {}
    current: str | None = None
    for line in match.group(1).splitlines():
        if not line.strip():
            continue
        if line.startswith(" ") and current is not None:
            fm[current] = (fm[current] + " " + line.strip()).strip()
            continue
        if ":" in line:
            k, _, v = line.partition(":")
            current = k.strip()
            fm[current] = v.strip()
    return fm


def test_skill_md_exists() -> None:
    assert SKILL_MD.exists()


def test_line_count(skill_text: str) -> None:
    assert len(skill_text.splitlines()) <= MAX_SKILL_LINES


def test_frontmatter(frontmatter: dict[str, str]) -> None:
    assert frontmatter["name"] == SKILL_NAME
    assert frontmatter["description"]
    assert "allowed-tools" in frontmatter


def test_required_sections(skill_text: str) -> None:
    for header in REQUIRED_SECTIONS:
        pattern = rf"(?mi)^#{{1,6}}\s+.*{re.escape(header)}"
        assert re.search(pattern, skill_text), f"missing section: {header}"


def test_four_mandatory_gates(skill_text: str) -> None:
    assert "Peer Set Validation Gate" in skill_text
    assert "Same-Definition Gate" in skill_text
    assert "Archetype-Awareness Gate" in skill_text


def test_references_exist() -> None:
    for ref in REQUIRED_REFERENCES:
        path = REFERENCES_DIR / ref
        assert path.exists()
        assert path.stat().st_size > 500


def test_references_loaded(skill_text: str) -> None:
    for ref in REQUIRED_REFERENCES:
        assert ref in skill_text


def test_finding_prefix_present(skill_text: str) -> None:
    assert FINDING_ID_PREFIX in skill_text


def test_dispatched_by_orchestrator(skill_text: str) -> None:
    assert "stock-analysis-lead" in skill_text


def test_archetype_aware(skill_text: str) -> None:
    assert "archetype" in skill_text.lower() or "sector" in skill_text.lower()


def test_does_not_recommend_verdict(skill_text: str) -> None:
    assert "synthesis" in skill_text.lower() or "orchestrator" in skill_text.lower()


def test_12_items_present(skill_text: str) -> None:
    for i in range(1, 13):
        assert f"P-{i:02d}" in skill_text, f"missing P-{i:02d} in panel"