"""Official-spec frontmatter validation for all seven stock skills and six agents.

The regression: the repo's own 315-test suite was green while two of the seven
skills failed the official `skill-creator/scripts/quick_validate.py`:

  * `stock-analysis-lead` — `description` contained `<ticker>` / `<company>`;
    angle brackets are rejected by the spec.
  * `stock-earnings-quality-review` — a bare `": "` inside the unquoted
    `description` scalar (`SaaS-specific: ARR/NRR/...`) made the **entire
    frontmatter invalid YAML**, so the skill could fail to load at all.

Neither was visible to the existing tests because they hand-parsed frontmatter
with a regex that tolerates malformed YAML, and never checked the spec's content
rules. The checks below are implemented independently of the official script (so
they run in CI with no external file), and are then **cross-checked against the
official script** when a copy is discoverable, so the two cannot silently drift.

One deliberate difference from `quick_validate.py`: its `allowed_properties` set
is **stale**. It rejects `disable-model-invocation`, which is a real Claude Code
frontmatter field. Encoding the validator's allowlist here would demand deleting
a legitimate field, so the allowlist below is the product's, and the cross-check
tolerates exactly that one class of disagreement.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml", reason="pyyaml is declared in requirements.txt")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from finlib import worker_contract as WC  # noqa: E402

LEAD_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = LEAD_ROOT.parents[1]
SKILLS_DIR = REPO_ROOT / "skills"
AGENTS_DIR = REPO_ROOT / "outputexample" / "stock-analysis-lead" / "agents"

STOCK_SKILLS = ["stock-analysis-lead"] + sorted(skill for skill, _ in WC.WORKERS.values())

# The product's field set (Claude Code frontmatter reference + the Agent Skills
# packaging spec), NOT quick_validate.py's stale six.
PRODUCT_FIELDS = {
    "name", "description", "when_to_use", "argument-hint", "arguments",
    "disable-model-invocation", "user-invocable", "allowed-tools", "disallowed-tools",
    "model", "effort", "context", "agent", "background", "hooks", "paths", "shell",
    "license", "metadata", "compatibility",
}

MAX_NAME = 64
MAX_DESCRIPTION = 1024

# Where a checked-out skill-creator may live. Absent in CI, so the cross-check skips.
OFFICIAL_VALIDATOR_CANDIDATES = (
    Path.home() / "skills" / "skills" / "skill-creator" / "scripts" / "quick_validate.py",
    Path.home() / "skill-creator" / "scripts" / "quick_validate.py",
    Path.home() / "Downloads" / "skills" / ".system" / "skill-creator" / "scripts" / "quick_validate.py",
)


def _official_validator() -> Path | None:
    return next((p for p in OFFICIAL_VALIDATOR_CANDIDATES if p.exists()), None)


def _frontmatter_text(path: Path) -> str:
    content = path.read_text(encoding="utf-8")
    assert content.startswith("---"), f"{path}: no YAML frontmatter"
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    assert match, f"{path}: unterminated frontmatter block"
    return match.group(1)


def _parse(path: Path) -> dict:
    """Parse with a real YAML parser. The repo's other tests hand-roll a regex
    that happily returns a dict for input PyYAML rejects — which is how a broken
    scalar survived."""
    text = _frontmatter_text(path)
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        pytest.fail(f"{path.parent.name}: frontmatter is not valid YAML — {exc}")
    assert isinstance(data, dict), f"{path.parent.name}: frontmatter must be a mapping"
    return data


def _check(data: dict, label: str, *, require_tools: bool) -> list[str]:
    errors: list[str] = []

    unexpected = set(data) - PRODUCT_FIELDS
    if unexpected:
        errors.append(f"unexpected frontmatter key(s): {sorted(unexpected)}")

    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        errors.append("name is required and must be a non-empty string")
    else:
        if not re.match(r"^[a-z0-9-]+$", name):
            errors.append(f"name {name!r} must be kebab-case (lowercase, digits, hyphens)")
        if name.startswith("-") or name.endswith("-") or "--" in name:
            errors.append(f"name {name!r} may not start/end with a hyphen or contain '--'")
        if len(name) > MAX_NAME:
            errors.append(f"name is {len(name)} chars, limit {MAX_NAME}")

    desc = data.get("description")
    if not isinstance(desc, str) or not desc.strip():
        errors.append("description is required and must be a non-empty string")
    else:
        if "<" in desc or ">" in desc:
            found = re.findall(r"<[^>]{0,40}>", desc) or ["<", ">"]
            errors.append(f"description contains angle brackets: {found}")
        if len(desc) > MAX_DESCRIPTION:
            errors.append(f"description is {len(desc)} chars, limit {MAX_DESCRIPTION}")

    if require_tools and "allowed-tools" not in data:
        errors.append("allowed-tools is the repo convention and is absent")

    return [f"{label}: {e}" for e in errors]


# --------------------------------------------------------------------------- #
# the seven skills
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("skill", STOCK_SKILLS)
def test_skill_frontmatter_is_valid_yaml(skill):
    """The defect that could stop a skill loading entirely."""
    _parse(SKILLS_DIR / skill / "SKILL.md")


@pytest.mark.parametrize("skill", STOCK_SKILLS)
def test_skill_frontmatter_meets_the_spec(skill):
    path = SKILLS_DIR / skill / "SKILL.md"
    errors = _check(_parse(path), skill, require_tools=True)
    assert not errors, "\n".join(errors)


@pytest.mark.parametrize("skill", STOCK_SKILLS)
def test_skill_name_matches_its_directory(skill):
    assert _parse(SKILLS_DIR / skill / "SKILL.md")["name"] == skill


@pytest.mark.parametrize("skill", STOCK_SKILLS)
def test_description_has_no_bare_colon_space(skill):
    """The specific mechanism that broke `stock-earnings-quality-review`: a bare
    ``": "`` inside an unquoted YAML scalar. Guarded directly, because YAML
    validity alone would silently pass a *quoted* scalar and then break again the
    next time someone edits it unquoted."""
    text = _frontmatter_text(SKILLS_DIR / skill / "SKILL.md")
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("description:"):
            continue
        value = stripped[len("description:"):].strip()
        if value.startswith(("'", '"')):
            continue          # a quoted scalar may legally contain ": "
        assert ": " not in value, (
            f"{skill}: unquoted description contains a bare ': ' — this makes the whole"
            f" frontmatter invalid YAML. Use an em-dash, or quote the scalar."
        )


# --------------------------------------------------------------------------- #
# the six agent definitions
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("agent", sorted(WC.WORKERS))
def test_agent_frontmatter_is_valid_yaml(agent):
    _parse(AGENTS_DIR / f"{agent}.md")


@pytest.mark.parametrize("agent", sorted(WC.WORKERS))
def test_agent_name_matches_its_filename(agent):
    assert _parse(AGENTS_DIR / f"{agent}.md")["name"] == agent


@pytest.mark.parametrize("agent", sorted(WC.WORKERS))
def test_agent_description_has_no_angle_brackets_and_fits(agent):
    data = _parse(AGENTS_DIR / f"{agent}.md")
    desc = data["description"]
    assert "<" not in desc and ">" not in desc, re.findall(r"<[^>]{0,40}>", desc)
    assert len(desc) <= MAX_DESCRIPTION, f"{len(desc)} chars"


@pytest.mark.parametrize("agent", sorted(WC.WORKERS))
def test_agent_declares_exactly_its_mapped_skill(agent):
    data = _parse(AGENTS_DIR / f"{agent}.md")
    assert data.get("skills") == [WC.WORKERS[agent][0]], data.get("skills")


def test_agent_descriptions_do_not_contradict_their_tier():
    """The drift found in review: the Peer agent's description said it "runs in
    Lite mode in Lite depth", while the rule is that it runs at Lite only when its
    trigger fires. An agent description is what the dispatcher reads, so a wrong
    claim there is a routing bug, not a typo."""
    tier1 = {"stock-management-reviewer", "stock-peer-comparison-reviewer"}
    for agent in sorted(WC.WORKERS):
        desc = _parse(AGENTS_DIR / f"{agent}.md")["description"]
        if agent in tier1:
            assert "Tier-1" in desc or "conditional" in desc, (
                f"{agent} is Tier-1 but its description does not say so"
            )
            if "Lite" in desc:
                assert "trigger" in desc, (
                    f"{agent} mentions Lite depth without the trigger condition —"
                    f" this reads as 'always runs at Lite', which is wrong"
                )
        else:
            assert "Tier-1" not in desc, f"{agent} is Tier-0 but claims Tier-1"


# --------------------------------------------------------------------------- #
# cross-file counts that drifted
# --------------------------------------------------------------------------- #

def test_lead_gate_count_matches_the_reference():
    """"Run 6 binary checks" sat above a list of 7, and the reference documented
    only 6 gates. Derive both from the files instead of restating a number."""
    lead = (LEAD_ROOT / "SKILL.md").read_text(encoding="utf-8")
    ref = (LEAD_ROOT / "references" / "cognitive-bias-gates.md").read_text(encoding="utf-8")

    start = lead.index("#### 5e. Cognitive-Bias Self-Check")
    end = lead.index("#### 5f. Verdict and Conditions")
    listed = re.findall(r"^(\d+)\. \*\*", lead[start:end], re.M)
    documented = re.findall(r"^## Gate (\d+) — ", ref, re.M)

    assert listed, "the lead lists no numbered self-checks"
    assert [int(n) for n in listed] == list(range(1, len(listed) + 1)), listed
    assert len(documented) == len(listed), (
        f"the lead runs {len(listed)} checks but cognitive-bias-gates.md documents"
        f" {len(documented)} gates — one file was updated without the other"
    )

    # No hardcoded count may contradict the list.
    stale = re.search(r"Run (\d+) binary checks", lead)
    if stale:
        assert int(stale.group(1)) == len(listed), (
            f"the lead says 'Run {stale.group(1)} binary checks' above a list of {len(listed)}"
        )


def test_output_block_reports_every_gate():
    """A self-check the report never renders is a check nobody sees.

    The render template lives in `references/output-format.md`; the checks that
    populate it are listed in SKILL.md Step 5e. The two must agree in count.
    """
    lead = (LEAD_ROOT / "SKILL.md").read_text(encoding="utf-8")
    template = (LEAD_ROOT / "references" / "output-format.md").read_text(encoding="utf-8")
    start = template.index("## Cognitive-Bias Self-Check / 认知偏差自检")
    block = template[start:template.index("\n## ", start + 10)]
    rendered = re.findall(r"^- ([^:]+):", block, re.M)
    listed = re.findall(r"^\d+\. \*\*(.+?)\*\*",
                        lead[lead.index("#### 5e."):lead.index("#### 5f.")], re.M)
    assert rendered, "the template renders no self-check lines"
    assert len(rendered) == len(listed), (
        f"the template renders {len(rendered)} gates but Step 5e runs {len(listed)}"
    )


def test_no_stock_reference_file_hardcodes_a_worker_count():
    """The fan-out is 4-6 depending on depth and triggers, so a live claim naming
    a fixed count is drift waiting to happen. Historical statements about what a
    previous version did are allowed and are exempted by the 'previous'/'v2' cue."""
    pattern = re.compile(r"\ball (?:5|6|five|six) workers\b", re.I)
    history = re.compile(r"previous version|v2 |v2's|used to|no longer|before this", re.I)
    for path in sorted((LEAD_ROOT / "references").glob("*.md")) + [LEAD_ROOT / "SKILL.md"]:
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line) and not history.search(line):
                pytest.fail(f"{path.name}:{i} states a fixed worker count: {line.strip()[:110]}")


# --------------------------------------------------------------------------- #
# cross-check against the official validator, when available
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("skill", STOCK_SKILLS)
def test_official_validator_agrees(skill):
    """Our independent implementation and the shipped validator must not drift.

    Skipped when no checked-out skill-creator is present (CI), so the suite never
    depends on a file outside the repo — but when one IS present, disagreement is
    a failure, not a note.
    """
    validator = _official_validator()
    if validator is None:
        pytest.skip("no skill-creator/scripts/quick_validate.py found on this machine")

    proc = subprocess.run(
        [sys.executable, str(validator), str(SKILLS_DIR / skill)],
        capture_output=True, text=True, timeout=60,
    )
    official_ok = proc.returncode == 0
    ours_ok = not _check(_parse(SKILLS_DIR / skill / "SKILL.md"), skill, require_tools=False)

    if official_ok == ours_ok:
        return

    # The one tolerated disagreement: the shipped allowlist is stale and rejects
    # `disable-model-invocation`, a real product field. Any other split is a bug
    # in one of the two implementations.
    message = (proc.stdout + proc.stderr).strip()
    assert not official_ok and ours_ok and "disable-model-invocation" in message, (
        f"{skill}: official validator says {'valid' if official_ok else 'invalid'}"
        f" ({message}) but our check says {'valid' if ours_ok else 'invalid'}"
    )


def test_official_validator_is_actually_exercised_somewhere():
    """Guard against the cross-check silently skipping forever: if a validator is
    present, at least one parametrised case must have run it."""
    validator = _official_validator()
    if validator is None:
        pytest.skip("no validator on this machine")
    proc = subprocess.run(
        [sys.executable, str(validator), str(SKILLS_DIR / STOCK_SKILLS[0])],
        capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, (
        f"{STOCK_SKILLS[0]} fails the official validator: {(proc.stdout + proc.stderr).strip()}"
    )


NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}


def _spoken_counts(text: str, noun_pattern: str) -> list[tuple[int, str, str]]:
    """Find natural-language counts like "6 binary checks" or "five gates".

    The previous cross-file test counted *headings* and so was blind to a number
    written in prose — which is exactly where both drifts lived.
    """
    hits = []
    rx = re.compile(rf"\b(\d+|{'|'.join(NUMBER_WORDS)})\s+(?:\w+\s+){{0,2}}?({noun_pattern})\b", re.I)
    for i, line in enumerate(text.splitlines(), 1):
        for m in rx.finditer(line):
            raw = m.group(1).lower()
            hits.append((NUMBER_WORDS.get(raw, int(raw) if raw.isdigit() else 0), m.group(0), f"{i}: {line.strip()[:100]}"))
    return hits


def test_the_spoken_count_scanner_works():
    """Guard the guard: it must catch both digit and word forms."""
    found = _spoken_counts("Run 6 binary checks. Also five gates apply.", r"checks?|gates?")
    assert {n for n, _, _ in found} == {6, 5}, found


def test_no_prose_count_of_the_self_check_gates_contradicts_the_files():
    """The drift the heading-count test missed: "Run 6 binary self-check questions"
    in the reference and "the 5 self-check questions" in the navigation, while the
    files carried 7 gates. Any prose count must equal the real one or be absent."""
    ref_path = LEAD_ROOT / "references" / "cognitive-bias-gates.md"
    lead_path = LEAD_ROOT / "SKILL.md"
    documented = len(re.findall(r"^## Gate (\d+) — ", ref_path.read_text(encoding="utf-8"), re.M))
    assert documented, "no gates documented"

    offenders = []
    for path in (ref_path, lead_path):
        text = path.read_text(encoding="utf-8")
        exempt = _history_lines(text)
        for count, _phrase, where in _spoken_counts(
            text, r"gates?|self-check questions?|binary checks?|binary self-check questions?"
        ):
            lineno = int(where.split(":", 1)[0])
            if lineno in exempt:
                continue
            if count != documented:
                offenders.append(f"{path.name}:{where}  (says {count}, files have {documented})")
    assert not offenders, "\n".join(offenders)


def _history_lines(text: str) -> set[int]:
    """Line numbers inside a paragraph that explains a past drift.

    Scoped to the whole paragraph, not the single line: an explanation of "it said
    6 above a list of 7" naturally wraps, and only one of its lines carries the cue
    word. A line-scoped exemption failed on the sentence describing the fix — the
    same over-narrow-scope mistake this suite exists to catch elsewhere.
    """
    cue = re.compile(r"drift|previous|used to|no longer|deliberately not|earlier version", re.I)
    exempt: set[int] = set()
    lineno = 1
    for para in re.split(r"\n\s*\n", text):
        span = para.count("\n") + 1
        if cue.search(para):
            exempt.update(range(lineno, lineno + span))
        lineno += span + 1
    return exempt


def test_the_history_exemption_is_paragraph_scoped():
    """Guard the guard, both ways: it must exempt a wrapped explanation and must
    NOT exempt an ordinary paragraph that happens to sit nearby."""
    text = (
        "Run 6 gates today.\n"          # line 1 — must NOT be exempt
        "\n"
        "> It drifted once — the skill\n"   # line 3 — cue
        "> said 6 gates above a list of 7.\n"  # line 4 — same paragraph, exempt too
    )
    exempt = _history_lines(text)
    assert 1 not in exempt
    assert {3, 4} <= exempt


def test_frontmatter_does_not_overstate_persistence():
    """The body makes the verdict log explicitly opt-in; the description used to
    say "Each verdict persists", which promises a side effect the skill will not
    perform without the user opting in."""
    desc = _parse(SKILLS_DIR / "stock-analysis-lead" / "SKILL.md")["description"]
    if "persist" in desc.lower():
        assert re.search(r"opt-in|can persist|optional", desc, re.I), (
            f"description claims unconditional persistence: {desc[desc.lower().index('persist')-40:][:120]!r}"
        )
