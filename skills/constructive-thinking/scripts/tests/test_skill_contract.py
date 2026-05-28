"""Zero-LLM contract tests for the constructive-thinking skill.

These checks are deterministic and do not invoke a language model.
They verify the structural contract of SKILL.md and references/ so
that future edits cannot silently break the skill's shape.
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
    "frameworks-library.md",
    "audience-and-compression.md",
    "anti-patterns.md",
]
REQUIRED_SECTION_HEADERS = [
    "When to Use",
    "When NOT to Use",
    "Core Method",
    "Mandatory Gates",
    "Output Contract",
    "Anti-Patterns",
]
REQUIRED_GATES = [
    "Gate 1",
    "Gate 2",
    "Gate 3",
    "Gate 4",
]
REQUIRED_CONTRACT_LABELS_EN = [
    "BLUF",
    "Frame",
    "Crux",
    "Key Nodes",
    "Tilt",
    "Reasoning",
]
REQUIRED_CONTRACT_LABELS_CN = [
    "顶层结论",
    "框架",
    "核心矛盾",
    "关键节点",
    "倾向方案",
    "理由",
]


@pytest.fixture(scope="module")
def skill_text() -> str:
    assert SKILL_MD.exists(), f"SKILL.md not found at {SKILL_MD}"
    return SKILL_MD.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def frontmatter(skill_text: str) -> dict[str, str]:
    """Parse the YAML-style frontmatter without depending on PyYAML."""
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", skill_text, re.DOTALL)
    assert match, "SKILL.md must start with a YAML frontmatter block"
    fm = {}
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
    assert SKILL_MD.exists(), "SKILL.md is missing"


def test_skill_md_under_line_limit(skill_text: str) -> None:
    line_count = len(skill_text.splitlines())
    assert line_count <= MAX_SKILL_LINES, (
        f"SKILL.md is {line_count} lines, exceeds {MAX_SKILL_LINES}. "
        "Move overflow content to references/."
    )


def test_frontmatter_required_fields(frontmatter: dict[str, str]) -> None:
    for field in ("name", "description", "allowed-tools"):
        assert field in frontmatter, f"frontmatter missing required field: {field}"
        assert frontmatter[field], f"frontmatter field {field} is empty"


def test_skill_name_matches_directory(frontmatter: dict[str, str]) -> None:
    assert frontmatter["name"] == "constructive-thinking", (
        f"frontmatter name is {frontmatter['name']!r}, expected 'constructive-thinking'"
    )


def test_description_mentions_method_signature(frontmatter: dict[str, str]) -> None:
    desc = frontmatter["description"]
    assert "Frame" in desc and "Crux" in desc, (
        "description must surface the method signature so the trigger is discoverable"
    )


def test_description_lists_negative_routes(frontmatter: dict[str, str]) -> None:
    desc = frontmatter["description"]
    for negative in ("tech-doc-writer", "writing-plans", "incident-postmortem"):
        assert negative in desc, (
            f"description must route away from overlapping skill: {negative}"
        )


def test_required_sections_present(skill_text: str) -> None:
    for header in REQUIRED_SECTION_HEADERS:
        pattern = rf"(?m)^#{{1,6}}\s+.*{re.escape(header)}"
        assert re.search(pattern, skill_text), (
            f"required section header missing: {header}"
        )


def test_four_mandatory_gates_declared(skill_text: str) -> None:
    for gate in REQUIRED_GATES:
        assert gate in skill_text, f"missing mandatory gate declaration: {gate}"


def test_output_contract_has_both_language_labels(skill_text: str) -> None:
    for label in REQUIRED_CONTRACT_LABELS_EN:
        assert label in skill_text, f"missing EN output-contract label: {label}"
    for label in REQUIRED_CONTRACT_LABELS_CN:
        assert label in skill_text, f"missing CN output-contract label: {label}"


def test_anti_patterns_section_has_examples(skill_text: str) -> None:
    bad_count = len(re.findall(r"\*\*BAD\*\*", skill_text))
    good_count = len(re.findall(r"\*\*GOOD\*\*", skill_text))
    assert bad_count >= 5, f"need ≥5 BAD examples in SKILL.md, found {bad_count}"
    assert good_count >= 5, f"need ≥5 GOOD examples in SKILL.md, found {good_count}"


def test_all_required_reference_files_exist() -> None:
    for ref in REQUIRED_REFERENCES:
        path = REFERENCES_DIR / ref
        assert path.exists(), f"missing reference: {path}"
        assert path.stat().st_size > 1000, (
            f"reference {ref} is suspiciously small (<1KB); likely a stub"
        )


def test_references_are_loaded_by_skill(skill_text: str) -> None:
    """Every reference file must be mentioned in SKILL.md with a load trigger."""
    for ref in REQUIRED_REFERENCES:
        assert ref in skill_text, (
            f"reference {ref} is never referenced from SKILL.md — "
            "progressive disclosure broken"
        )


def test_hedge_words_blocklisted_in_contract(skill_text: str) -> None:
    """SKILL.md must explicitly forbid hedge words in the Tilt."""
    for hedge in ("perhaps", "maybe", "可能", "也许"):
        assert hedge in skill_text, (
            f"hedge word {hedge!r} must be named in the forbidden list "
            "so the model learns to avoid it"
        )