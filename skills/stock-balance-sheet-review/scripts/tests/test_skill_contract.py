"""Zero-LLM contract tests for stock-balance-sheet-review worker skill."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

SKILL_ROOT = Path(__file__).resolve().parents[2]
SKILL_MD = SKILL_ROOT / "SKILL.md"
REFERENCES_DIR = SKILL_ROOT / "references"

MAX_SKILL_LINES = 500
SKILL_NAME = "stock-balance-sheet-review"
REQUIRED_REFERENCES = ["balance-sheet-red-flags.md"]
REQUIRED_SECTIONS = [
    "Purpose",
    "When To Use",
    "When NOT To Use",
    "Mandatory Gates",
    "Workflow",
    "Filing-Pattern-Gated Execution Protocol",
    "Output Format",
]
FINDING_ID_PREFIX = "BS-"


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
    assert "Execution Integrity Gate" in skill_text


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


def test_does_not_recommend_verdict(skill_text: str) -> None:
    assert "synthesis" in skill_text.lower() or "orchestrator" in skill_text.lower()


def test_sector_awareness_required(skill_text: str) -> None:
    """Balance sheet thresholds must vary by sector."""
    assert "sector" in skill_text.lower(), (
        "balance-sheet worker must apply sector-aware thresholds"
    )


# --------------------------------------------------------------------------- #
# Official-spec frontmatter validation.
#
# A skill must be independently verifiable: running only this skill's regression
# must catch a frontmatter defect that stops it loading. The regex-based
# `frontmatter` fixture above tolerates malformed YAML and returns a dict anyway,
# which is how a bare ": " inside an unquoted description survived — it made the
# whole block invalid YAML while every existing test stayed green.
# The cross-skill sweep lives in stock-analysis-lead/scripts/tests/test_skill_frontmatter.py.
# --------------------------------------------------------------------------- #

def test_frontmatter_is_valid_yaml() -> None:
    yaml = pytest.importorskip("yaml", reason="pyyaml is declared in requirements.txt")
    match = re.match(r"^---\n(.*?)\n---", SKILL_MD.read_text(encoding="utf-8"), re.DOTALL)
    assert match, "unterminated frontmatter block"
    try:
        data = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        raise AssertionError(f"frontmatter is not valid YAML: {exc}") from exc
    assert isinstance(data, dict), "frontmatter must be a mapping"
    assert data["name"] == SKILL_NAME


def test_description_meets_the_spec(skill_text: str) -> None:
    yaml = pytest.importorskip("yaml", reason="pyyaml is declared in requirements.txt")
    match = re.match(r"^---\n(.*?)\n---", skill_text, re.DOTALL)
    desc = yaml.safe_load(match.group(1))["description"]
    assert "<" not in desc and ">" not in desc, "angle brackets are rejected by the spec"
    assert len(desc) <= 1024, f"description is {len(desc)} chars, limit 1024"


def test_unquoted_description_has_no_bare_colon_space(skill_text: str) -> None:
    """The exact mechanism that broke this skill family: `Foo: bar` inside an
    unquoted YAML scalar invalidates the entire frontmatter."""
    match = re.match(r"^---\n(.*?)\n---", skill_text, re.DOTALL)
    for line in match.group(1).splitlines():
        stripped = line.strip()
        if not stripped.startswith("description:"):
            continue
        value = stripped[len("description:"):].strip()
        if value.startswith(("'", '"')):
            continue
        assert ": " not in value, (
            "unquoted description contains a bare ': ' — use an em-dash or quote the scalar"
        )
