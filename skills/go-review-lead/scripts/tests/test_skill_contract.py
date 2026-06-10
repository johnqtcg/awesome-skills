"""Zero-LLM contract tests for go-review-lead (orchestrator).

Verifies the structural shape of the orchestrator skill and locks down the
real dispatch contract — the orchestrator → agent → skill mapping. The
orchestrator dispatches sub-agents named ``*-reviewer`` (defined under
``outputexample/go-review-lead/agents/``); each agent's ``skills:``
frontmatter field loads the matching ``*-review`` methodology skill under
``skills/``. Token matching is hyphen-boundary so the ``-review`` skill name
can never satisfy a check for the ``-reviewer`` agent name by substring
coincidence.

Also locks the fixes for defects found in architecture review:
- 7-vs-8 worker drift (observability agent existed but README installed 7)
- ``remaining 5`` / ``Phase 0`` stale references in SKILL.md
- diff base hardcoded to HEAD~1 (multi-commit branches were under-reviewed)
- prose-only findings hand-off (now a JSON contract)
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
AGENTS_DIR = REPO_ROOT / "outputexample" / "go-review-lead" / "agents"
README_MD = REPO_ROOT / "outputexample" / "go-review-lead" / "README.md"

MAX_SKILL_LINES = 500

REQUIRED_REFERENCES = [
    "example-output.md",
    "findings-schema.md",
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
    "go-security-review",
    "go-concurrency-review",
    "go-error-review",
    "go-logic-review",
    "go-performance-review",
    "go-quality-review",
    "go-test-review",
    "go-observability-review",
]

EXPECTED_AGENTS = [
    "go-security-reviewer",
    "go-concurrency-reviewer",
    "go-error-reviewer",
    "go-logic-reviewer",
    "go-performance-reviewer",
    "go-quality-reviewer",
    "go-test-reviewer",
    "go-observability-reviewer",
]

AGENT_PREFIX = {
    "go-security-reviewer": "SEC",
    "go-concurrency-reviewer": "CONC",
    "go-error-reviewer": "ERR",
    "go-logic-reviewer": "LOGIC",
    "go-performance-reviewer": "PERF",
    "go-quality-reviewer": "QUAL",
    "go-test-reviewer": "TEST",
    "go-observability-reviewer": "OBS",
}


def _mentions_token(text: str, token: str) -> bool:
    """Hyphen-boundary token match: ``go-security-review`` does NOT match
    inside ``go-security-reviewer`` and vice versa."""
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
                break
    return skills


@pytest.fixture(scope="module")
def skill_text() -> str:
    assert SKILL_MD.exists(), f"SKILL.md not found at {SKILL_MD}"
    return SKILL_MD.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def readme_text() -> str:
    assert README_MD.exists(), f"README not found at {README_MD}"
    return README_MD.read_text(encoding="utf-8")


def test_skill_md_under_line_limit(skill_text: str) -> None:
    line_count = len(skill_text.splitlines())
    assert line_count <= MAX_SKILL_LINES, f"{line_count} lines > {MAX_SKILL_LINES}"


def test_frontmatter_fields(skill_text: str) -> None:
    fm = _frontmatter_block(skill_text)
    assert _frontmatter_name(skill_text) == "go-review-lead"
    assert "description" in fm
    assert "Agent" in fm, "allowed-tools must include the Agent tool for dispatch"


def test_required_sections_present(skill_text: str) -> None:
    for header in REQUIRED_SECTIONS:
        pattern = rf"(?mi)^#{{1,6}}\s+.*{re.escape(header)}"
        assert re.search(pattern, skill_text), f"missing section: {header}"


def test_required_references_exist(skill_text: str) -> None:
    for ref in REQUIRED_REFERENCES:
        path = REFERENCES_DIR / ref
        assert path.exists(), f"missing reference: {path}"
        assert ref in skill_text, f"reference {ref} never mentioned in SKILL.md"


# --- Dispatch contract: orchestrator → agent → skill ---


def test_token_matcher_rejects_substring_collision() -> None:
    assert _mentions_token("dispatch go-security-reviewer now", "go-security-reviewer")
    assert not _mentions_token("dispatch go-security-reviewer now", "go-security-review")
    assert _mentions_token("load `go-security-review`", "go-security-review")


def test_orchestrator_dispatches_all_eight_agents(skill_text: str) -> None:
    for agent in EXPECTED_AGENTS:
        assert _mentions_token(skill_text, agent), (
            f"orchestrator must reference agent by exact name: {agent}"
        )


def test_agent_definitions_exist() -> None:
    assert AGENTS_DIR.is_dir(), f"agent definitions dir missing: {AGENTS_DIR}"
    found = sorted(p.stem for p in AGENTS_DIR.glob("*.md"))
    assert found == sorted(EXPECTED_AGENTS), (
        f"agents on disk {found} != expected {sorted(EXPECTED_AGENTS)}"
    )
    for agent in EXPECTED_AGENTS:
        text = (AGENTS_DIR / f"{agent}.md").read_text(encoding="utf-8")
        assert _frontmatter_name(text) == agent, (
            f"agent {agent}.md frontmatter name must equal its filename"
        )


def test_agent_to_skill_mapping_closes() -> None:
    """Each agent declares exactly one ``skills:`` entry, that skill exists
    on disk, its frontmatter name equals its directory name, and the mapped
    set is exactly the eight vertical worker skills."""
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
    assert set(mapped) == set(REQUIRED_WORKER_SKILLS), (
        f"agent→skill map {sorted(set(mapped))} != required workers "
        f"{sorted(REQUIRED_WORKER_SKILLS)}"
    )


def test_agent_prefixes_consistent() -> None:
    for agent, prefix in AGENT_PREFIX.items():
        text = (AGENTS_DIR / f"{agent}.md").read_text(encoding="utf-8")
        assert f"{prefix}-" in text, f"agent {agent} must use the {prefix}- prefix"


# --- Drift locks: 7-vs-8 workers, stale references ---


def test_no_stale_seven_agent_counts(skill_text: str, readme_text: str) -> None:
    stale = re.compile(
        r"\b7-Agent\b|\b7 Worker\b|\b7 vertical\b|only the 7\b|\(7 workers",
        re.IGNORECASE,
    )
    for name, text in (("SKILL.md", skill_text), ("README.md", readme_text)):
        match = stale.search(text)
        assert match is None, f"stale 7-agent count {match.group(0)!r} in {name}"


def test_no_stale_remaining_five_or_phase_zero(skill_text: str) -> None:
    assert "remaining 5" not in skill_text, (
        "SKILL.md still says 'remaining 5' — 2 always-on + 6 conditional = 8 workers"
    )
    assert "Phase 0" not in skill_text, "SKILL.md references undefined 'Phase 0'"


def test_readme_installs_all_eight_workers(readme_text: str) -> None:
    """A user following the README must end up with a complete system —
    this is the exact gap that shipped a 7/8 install."""
    for agent in EXPECTED_AGENTS:
        assert _mentions_token(readme_text, agent), (
            f"README install/verify instructions missing agent: {agent}"
        )
    for skill in REQUIRED_WORKER_SKILLS:
        assert _mentions_token(readme_text, skill), (
            f"README skill install loop missing skill: {skill}"
        )


# --- Diff base: merge-base, not HEAD~1 ---


def test_diff_base_uses_merge_base(skill_text: str) -> None:
    assert "merge-base" in skill_text, (
        "Step 1 must diff against the merge-base of main, not bare HEAD~1"
    )
    assert not re.search(r"git diff (--name-only )?HEAD~1", skill_text), (
        "bare 'git diff HEAD~1' reviews only the last commit of a multi-commit branch"
    )


# --- Findings JSON contract wired end-to-end ---


def test_findings_json_contract_wired(skill_text: str) -> None:
    assert (REFERENCES_DIR / "findings-schema.md").exists()
    assert '"prefix"' in skill_text, "dispatch prompt must embed the compact schema"
    assert '"grep_audit"' in skill_text, "schema must carry the grep audit"
    for agent in EXPECTED_AGENTS:
        text = (AGENTS_DIR / f"{agent}.md").read_text(encoding="utf-8")
        assert "Findings JSON block" in text, (
            f"agent {agent} does not commit to the Findings JSON block"
        )


# --- Behavioral eval assets ---


def test_golden_eval_assets_exist() -> None:
    evals_dir = SKILL_ROOT / "evals"
    assert (evals_dir / "run_smoke.sh").exists()
    assert (evals_dir / "README.md").exists()
    golden = evals_dir / "golden"
    assert golden.is_dir(), "golden defect package missing"
    combined = "\n".join(
        p.read_text(encoding="utf-8") for p in golden.rglob("*.go")
    )
    planted_patterns = {
        "SQL injection": r"Sprintf\(.*SELECT",
        "data race": r"go func",
        "unclosed resp.Body": r"resp\.Body",
    }
    for defect, pattern in planted_patterns.items():
        assert re.search(pattern, combined), (
            f"golden package must contain the planted defect: {defect}"
        )