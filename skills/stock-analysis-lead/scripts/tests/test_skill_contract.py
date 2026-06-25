"""Zero-LLM contract tests for stock-analysis-lead (orchestrator).

Verifies the structural shape of the orchestrator skill: frontmatter,
required sections, references files present, and length below the repo's
500-line limit.

It also locks down the real dispatch contract — the orchestrator → agent →
skill mapping. The orchestrator dispatches sub-agents named ``*-reviewer``
(defined under ``outputexample/stock-analysis-lead/agents/``); each agent's
``skills:`` frontmatter field loads the matching ``*-review`` methodology
skill under ``skills/``. These tests assert that chain closes with exact,
hyphen-boundary token matching so the ``-review`` skill name can never
satisfy a check for the ``-reviewer`` agent name (or vice versa) by
substring coincidence.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

SKILL_ROOT = Path(__file__).resolve().parents[2]
SKILL_MD = SKILL_ROOT / "SKILL.md"
REFERENCES_DIR = SKILL_ROOT / "references"

REPO_ROOT = SKILL_ROOT.parents[1]
SKILLS_DIR = REPO_ROOT / "skills"
AGENTS_DIR = REPO_ROOT / "outputexample" / "stock-analysis-lead" / "agents"

# Raised 500 -> 540 for the P2/P3 additions (archetype Analytical-Addendum dispatch
# wiring + the mandatory Variant Perception output block). Detail lives in the
# reference files; SKILL.md only carries the minimal pointers and output contract.
MAX_SKILL_LINES = 540

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

# The orchestrator dispatches AGENTS (``-reviewer``), not skills directly.
# Each agent's ``skills:`` frontmatter field loads its ``-review`` skill.
EXPECTED_AGENTS = [
    "stock-business-reviewer",
    "stock-earnings-quality-reviewer",
    "stock-balance-sheet-reviewer",
    "stock-management-reviewer",
    "stock-industry-reviewer",
    "stock-peer-comparison-reviewer",
]


def _mentions_token(text: str, token: str) -> bool:
    """True if ``token`` appears in ``text`` not surrounded by other
    identifier characters (``[A-Za-z0-9-]``).

    Hyphen is treated as part of the identifier, so a search for
    ``stock-business-review`` does NOT match inside
    ``stock-business-reviewer`` — closing the substring-collision hole
    that let the previous test pass on a broken reference.
    """
    pattern = rf"(?<![A-Za-z0-9-]){re.escape(token)}(?![A-Za-z0-9-])"
    return re.search(pattern, text) is not None


def _frontmatter_block(text: str) -> str:
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    return match.group(1) if match else ""


def _frontmatter_name(text: str) -> str | None:
    for line in _frontmatter_block(text).splitlines():
        match = re.match(r"^name\s*:\s*(.+?)\s*$", line)
        if match:
            return match.group(1).strip()
    return None


def _agent_declared_skills(text: str) -> list[str]:
    """Parse the ``skills:`` frontmatter field (YAML list or inline form)."""
    block = _frontmatter_block(text)
    skills: list[str] = []
    in_skills = False
    for line in block.splitlines():
        if re.match(r"^skills\s*:", line):
            inline = line.split(":", 1)[1].strip()
            if inline.startswith("["):
                items = inline.strip("[]").split(",")
                return [i.strip().strip("\"'") for i in items if i.strip()]
            in_skills = True
            continue
        if in_skills:
            item = re.match(r"^\s+-\s*(.+?)\s*$", line)
            if item:
                skills.append(item.group(1).strip().strip("\"'"))
            elif line.strip() and not line.startswith(" "):
                break  # reached the next top-level frontmatter key
    return skills


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


def test_token_matcher_rejects_substring_collision() -> None:
    """Guard the matcher itself: the ``-review`` skill name must never
    satisfy a check for the ``-reviewer`` agent name by substring."""
    assert _mentions_token("dispatch stock-business-reviewer now", "stock-business-reviewer")
    assert not _mentions_token("dispatch stock-business-reviewer now", "stock-business-review")
    assert _mentions_token("load `stock-business-review`", "stock-business-review")


def test_orchestrator_dispatches_all_agents(skill_text: str) -> None:
    """Orchestrator must dispatch every worker AGENT by its exact name."""
    for agent in EXPECTED_AGENTS:
        assert _mentions_token(skill_text, agent), (
            f"orchestrator must dispatch agent by exact name: {agent}"
        )


def test_agent_definitions_exist() -> None:
    assert AGENTS_DIR.is_dir(), f"agent definitions dir missing: {AGENTS_DIR}"
    for agent in EXPECTED_AGENTS:
        path = AGENTS_DIR / f"{agent}.md"
        assert path.exists(), f"missing agent definition: {path}"
        assert _frontmatter_name(path.read_text(encoding="utf-8")) == agent, (
            f"agent {agent}.md frontmatter name must equal its filename"
        )


def test_agent_to_skill_mapping_closes() -> None:
    """The real dispatch contract: each dispatched agent declares exactly
    one ``skills:`` entry, that skill exists on disk, and its frontmatter
    name equals its directory name. The mapped set must be the six distinct
    required worker skills — no drift in either direction."""
    mapped: list[str] = []
    for agent in EXPECTED_AGENTS:
        agent_text = (AGENTS_DIR / f"{agent}.md").read_text(encoding="utf-8")
        declared = _agent_declared_skills(agent_text)
        assert len(declared) == 1, (
            f"agent {agent} must declare exactly one skill, got: {declared}"
        )
        skill = declared[0]
        skill_md = SKILLS_DIR / skill / "SKILL.md"
        assert skill_md.exists(), (
            f"agent {agent} maps to skill '{skill}' but {skill_md} does not exist"
        )
        assert _frontmatter_name(skill_md.read_text(encoding="utf-8")) == skill, (
            f"skill '{skill}' frontmatter name must equal its directory name"
        )
        mapped.append(skill)
    assert len(set(mapped)) == len(EXPECTED_AGENTS), (
        f"agents must map to distinct skills, got: {mapped}"
    )
    assert set(mapped) == set(REQUIRED_WORKER_SKILLS), (
        f"agent→skill map {sorted(set(mapped))} != required workers "
        f"{sorted(set(REQUIRED_WORKER_SKILLS))}"
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
        "Variant Perception",
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
        "变量观点",
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