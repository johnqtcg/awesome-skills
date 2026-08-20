"""Cross-skill contract tests for the stock-analysis multi-agent system.

The existing per-skill contract tests all passed while the orchestration matrix
was broken in three places at once:

  * the lead said Lite runs the Peer worker's General panel; the Peer skill said
    "Lite depth (orchestrator skips this worker to save tokens)";
  * the lead said "all 5 workers" in two places and "five-analyst report" in a
    third, having grown to six;
  * every agent definition demanded "the machine-readable Findings JSON block
    exactly as specified in the orchestrator's dispatch prompt", and the dispatch
    prompt did not define one.

Each of those is a statement about the *relationship between two files*, which is
exactly what a per-skill structural test cannot see. These tests assert the joins:
one authoritative source per fact, and every other file agreeing with it or not
restating it at all.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from finlib import runbundle as RB  # noqa: E402
from finlib import worker_contract as WC  # noqa: E402

LEAD_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = LEAD_ROOT.parents[1]
SKILLS_DIR = REPO_ROOT / "skills"
AGENTS_DIR = REPO_ROOT / "outputexample" / "stock-analysis-lead" / "agents"

LEAD_MD = LEAD_ROOT / "SKILL.md"
DISPATCH_MD = LEAD_ROOT / "references" / "dispatch-protocol.md"
CONTRACT_MD = LEAD_ROOT / "references" / "worker-contract.md"
VERDICT_LOG_MD = LEAD_ROOT / "references" / "verdict-log-protocol.md"

# Tier assignment is declared here and asserted against dispatch-protocol.md.
TIER0 = set(RB.TIER0)
TIER1 = {"stock-management-reviewer", "stock-peer-comparison-reviewer"}


@pytest.fixture(scope="module")
def lead() -> str:
    return LEAD_MD.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def dispatch() -> str:
    return DISPATCH_MD.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def worker_texts() -> dict[str, str]:
    return {
        skill: (SKILLS_DIR / skill / "SKILL.md").read_text(encoding="utf-8")
        for skill, _ in WC.WORKERS.values()
    }


@pytest.fixture(scope="module")
def agent_texts() -> dict[str, str]:
    return {
        agent: (AGENTS_DIR / f"{agent}.md").read_text(encoding="utf-8")
        for agent in WC.WORKERS
    }


def _frontmatter(text: str) -> str:
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    return match.group(1) if match else ""


# --------------------------------------------------------------------------- #
# the fan-out itself
# --------------------------------------------------------------------------- #

def test_worker_map_covers_every_worker_skill_on_disk():
    """A seventh worker added under skills/stock-*-review without registering in
    WORKERS would otherwise be silently absent from the whole system."""
    on_disk = {
        p.parent.name for p in SKILLS_DIR.glob("stock-*-review/SKILL.md")
    }
    registered = {skill for skill, _ in WC.WORKERS.values()}
    assert on_disk == registered, (
        f"unregistered worker skills: {sorted(on_disk - registered)}; "
        f"registered-but-missing: {sorted(registered - on_disk)}"
    )


def test_tier_partition_is_complete_and_disjoint():
    assert TIER0 | TIER1 == set(WC.WORKERS)
    assert not (TIER0 & TIER1)


def test_prefixes_are_unique():
    prefixes = [prefix for _, prefix in WC.WORKERS.values()]
    assert len(prefixes) == len(set(prefixes)), f"duplicate prefix: {prefixes}"


def test_no_prefix_is_a_prefix_of_another():
    """``P`` and a hypothetical ``PE`` would make ID ownership ambiguous even with
    whole-segment matching if either were ever used without a hyphen."""
    prefixes = sorted(p for _, p in WC.WORKERS.values())
    for a in prefixes:
        for b in prefixes:
            if a != b:
                assert not b.startswith(a) or "-" in b, f"{a!r} shadows {b!r}"


# --------------------------------------------------------------------------- #
# agent <-> skill <-> prefix joins
# --------------------------------------------------------------------------- #

def test_each_agent_declares_its_mapped_skill(agent_texts):
    for agent, (skill, _) in WC.WORKERS.items():
        fm = _frontmatter(agent_texts[agent])
        assert skill in fm, f"agent {agent} does not declare skill {skill} in frontmatter"


def test_each_worker_skill_declares_its_prefix(worker_texts):
    for skill, prefix in WC.WORKERS.values():
        text = worker_texts[skill]
        assert f'"prefix": "{prefix}"' in text, (
            f"{skill} must pin its prefix {prefix!r} in its findings-json block"
        )


def test_no_worker_skill_claims_another_workers_prefix(worker_texts):
    """The Business skill emitting ``"prefix": "EQ"`` would route its findings to
    the wrong dimension in consolidation."""
    for skill, prefix in WC.WORKERS.values():
        for other_skill, other_prefix in WC.WORKERS.values():
            if other_prefix == prefix:
                continue
            assert f'"prefix": "{other_prefix}"' not in worker_texts[skill], (
                f"{skill} declares foreign prefix {other_prefix!r}"
            )


def test_lead_dispatches_every_agent_by_exact_name(lead):
    for agent in WC.WORKERS:
        pattern = rf"(?<![A-Za-z0-9-]){re.escape(agent)}(?![A-Za-z0-9-])"
        assert re.search(pattern, lead), f"lead never names agent {agent}"


# --------------------------------------------------------------------------- #
# the message protocol closes — the headline defect
# --------------------------------------------------------------------------- #

def test_lead_dispatch_prompt_defines_the_findings_block(lead):
    """The agent definitions point at "the block specified in the dispatch
    prompt". That block must actually be in the dispatch prompt."""
    assert "findings-json" in lead
    for field in (
        "contract_version", "archetype_challenge", "checklist_coverage",
        "mandatory_checks_run", "status_reason", "fiscal_period", "confidence",
    ):
        assert field in lead, f"dispatch prompt omits contract field: {field}"


def test_every_worker_skill_carries_the_findings_block(worker_texts):
    for skill in worker_texts:
        assert "```findings-json" in worker_texts[skill], (
            f"{skill} Output Format has no findings-json block — a directly "
            f"invoked worker would emit nothing machine-readable"
        )


def test_every_agent_definition_points_at_the_contract_file(agent_texts):
    for agent, text in agent_texts.items():
        assert "worker-contract.md" in text, (
            f"agent {agent} does not reference the contract spec"
        )
        assert "findings-json" in text, f"agent {agent} does not name the block"


def test_no_agent_still_points_at_an_undefined_dispatch_prompt_block(agent_texts):
    """The exact broken phrasing must not come back."""
    dead = "exactly as specified in the orchestrator's dispatch prompt"
    for agent, text in agent_texts.items():
        assert dead not in text, f"agent {agent} still defers to an undefined block"


def test_contract_version_agrees_across_every_file(lead, worker_texts, agent_texts):
    # The lead names the version and delegates the field-by-field schema to the
    # worker skills and worker-contract.md — a third inline copy of the same JSON
    # is a third thing to drift. It must still name the required keys, so a worker
    # reading only the dispatch prompt knows what is mandatory.
    assert f"Contract v{WC.CONTRACT_VERSION}" in lead, "lead names a different contract version"
    assert "contract_version" in lead, "lead does not name the version field at all"
    assert "worker-contract.md" in lead, "lead does not point at the authoritative schema"

    expected = f'"contract_version": "{WC.CONTRACT_VERSION}"'
    for skill, text in worker_texts.items():
        assert expected in text, f"{skill} pins a different contract version"
    label = f"Contract v{WC.CONTRACT_VERSION}"
    for agent, text in agent_texts.items():
        assert label in text, f"agent {agent} does not state {label}"
    assert f'`CONTRACT_VERSION = "{WC.CONTRACT_VERSION}"`' in CONTRACT_MD.read_text(encoding="utf-8")


def test_worker_findings_blocks_are_valid_against_the_validator(worker_texts):
    """The schema each worker shows must be a payload the validator accepts once
    its placeholders are filled — otherwise every worker copies an example that
    fails the gate. Placeholders are substituted with legal values first."""
    for skill, prefix in WC.WORKERS.values():
        blocks = WC._FENCE.findall(worker_texts[skill])
        assert len(blocks) == 1, f"{skill} has {len(blocks)} findings-json blocks, expected 1"
        raw = (
            blocks[0]
            .replace("<echo the dispatched depth>", "Standard")
            .replace("<echo the dispatched archetype>", "Hyperscaler")
            .replace(f"{prefix}-NN", f"{prefix}-01")
            .replace("High|Medium|Low", "High")
            .replace("<= 80 chars", "a title")
            .replace("<item/page/note>", "Item 1A, page 3")
            .replace("direct quote <= 60 words, or a computed figure with its inputs", "quoted text")
            .replace("one sentence on what this means for the thesis", "it matters.")
            .replace("first-hand|second-hand", "first-hand")
        )
        payload = json.loads(raw)
        # The template ships items_checked=0; a real reply fills it in.
        payload["checklist_coverage"]["items_checked"] = payload["checklist_coverage"]["items_total"]
        errs = WC.validate(payload)
        assert errs == [], f"{skill} template fails validation: {[e.as_dict() for e in errs]}"


def test_worker_checklist_totals_match_their_actual_checklists(worker_texts):
    """``items_total`` in the template must equal the number of checklist rows the
    skill defines, or the coverage check compares against a fiction."""
    for skill, prefix in WC.WORKERS.values():
        text = worker_texts[skill]
        rows = set(re.findall(rf"^\|\s*({re.escape(prefix)}-\d+)\s*\|", text, re.M))
        block = WC._FENCE.findall(text)[0]
        declared = int(re.search(r'"items_total":\s*(\d+)', block).group(1))
        assert declared == len(rows), (
            f"{skill}: template says items_total={declared} but the checklist "
            f"defines {len(rows)} rows ({sorted(rows)})"
        )


# --------------------------------------------------------------------------- #
# depth x worker matrix — one authoritative source, no contradictions
# --------------------------------------------------------------------------- #

def test_dispatch_protocol_declares_every_worker_with_a_tier(dispatch):
    for agent in TIER0:
        assert f"`{agent}`" in dispatch, f"{agent} not named in dispatch-protocol.md"
    for agent in TIER1:
        assert f"`{agent}`" in dispatch, f"{agent} not named in dispatch-protocol.md"
    assert "Tier 0 — Core" in dispatch
    assert "Tier 1 — Conditional" in dispatch
    assert "Tier 2 — Conflict-triggered" in dispatch


def test_tier0_workers_are_listed_in_the_tier0_section(dispatch):
    """A Tier-0 worker named only in the Tier-1 table would silently become
    skippable."""
    start = dispatch.index("### Tier 0 — Core")
    end = dispatch.index("### Tier 1 — Conditional")
    section = dispatch[start:end]
    for agent in TIER0:
        assert f"`{agent}`" in section, f"{agent} missing from the Tier-0 section"
    for agent in TIER1:
        assert f"`{agent}`" not in section, f"{agent} is Tier-1 but appears in Tier-0"


def test_tier1_workers_are_listed_in_the_tier1_section(dispatch):
    start = dispatch.index("### Tier 1 — Conditional")
    end = dispatch.index("### Tier 2 — Conflict-triggered")
    section = dispatch[start:end]
    for agent in TIER1:
        assert f"`{agent}`" in section, f"{agent} missing from the Tier-1 section"


def test_peer_worker_does_not_claim_lite_skips_it(worker_texts):
    """The exact contradiction the 130-test suite missed: the lead ran the Peer
    worker at Lite while the Peer skill declared itself skipped there."""
    text = worker_texts["stock-peer-comparison-review"]
    assert "orchestrator skips this worker" not in text
    assert "Lite mode" in text or "Lite depth" in text


def test_industry_worker_still_declares_itself_always_on(worker_texts):
    """Industry owns 2 Good-Company items, so it must stay Tier-0 at every depth."""
    text = worker_texts["stock-industry-review"]
    assert "always-on" in text
    assert "Tier-0" in text


def test_tier1_workers_state_their_conditional_status(worker_texts):
    for agent in TIER1:
        skill = WC.WORKERS[agent][0]
        assert "Tier-1" in worker_texts[skill], (
            f"{skill} does not tell a directly-invoking reader it is conditional"
        )


def test_conditional_workers_point_at_the_authoritative_trigger_source(worker_texts):
    for agent in TIER1:
        skill = WC.WORKERS[agent][0]
        assert "dispatch-protocol.md" in worker_texts[skill], (
            f"{skill} restates triggers without citing the authoritative file"
        )


@pytest.mark.parametrize("stale", [
    "all 5 workers",
    "Dispatch all 5",
    "five-analyst",
    "all 6 workers",
    "skip all 6 workers",
    "Collect Findings from all 6 workers",
])
def test_lead_carries_no_stale_worker_count(lead, stale):
    """Hardcoded fan-out counts drifted every time the roster changed. The count
    is now depth- and trigger-dependent, so prose must not assert one."""
    assert stale not in lead, f"stale worker-count phrasing in lead: {stale!r}"


def test_no_worker_skill_hardcodes_the_fan_out_size(worker_texts):
    for skill, text in worker_texts.items():
        for stale in ("one of 5 parallel workers", "one of 6 parallel workers",
                      "one of five parallel", "one of six parallel"):
            assert stale not in text, f"{skill} hardcodes the fan-out size: {stale!r}"


# --------------------------------------------------------------------------- #
# failure-path wiring
# --------------------------------------------------------------------------- #

def test_lead_wires_the_validator_and_the_bundle_gate(lead):
    assert "worker_contract.py" in lead, "lead never runs the contract validator"
    assert "runbundle.py" in lead, "lead never runs the bundle gate"
    assert "verdictlog.py" in lead, "lead still hand-rolls the log append"


def test_lead_documents_every_failure_mode_the_review_found_missing(lead):
    for concept in ("TIMEOUT", "retry", "quorum", "REFUSED", "DEGRADED", "FAILED"):
        assert concept in lead, f"lead does not handle agent failure mode: {concept}"


def test_lead_states_the_retry_limit_and_forbids_model_fallback(lead):
    assert "one" in lead.lower() and "retry" in lead.lower()
    assert "No model fallback" in lead, (
        "silently substituting a different model makes the run unauditable"
    )


def test_lead_forbids_blocking_on_the_full_set(lead):
    assert "Do not wait for the full set" in lead
    assert "quorum" in lead


def test_quorum_rules_agree_between_lead_and_dispatch_protocol(lead, dispatch):
    """Both files state the quorum table; they must not disagree on the counts."""
    for text, label in ((lead, "SKILL.md"), (dispatch, "dispatch-protocol.md")):
        assert "4" in text and "degraded" in text.lower(), label
        assert "Watch" in text, f"{label} omits the balance-sheet Watch cap"
    assert "no verdict" in lead.lower()
    assert "No verdict" in dispatch


def test_run_bundle_layout_names_the_files_the_gate_requires(dispatch):
    for name in RB.PUBLICATION_FILES:
        assert name in dispatch, f"run-bundle layout omits {name}, which the gate requires"
    assert "workers/" in dispatch
    assert "attempt1.md" in dispatch, "the retry-artifact naming convention is undocumented"


def test_both_gate_stages_are_wired_into_the_lead(lead):
    """The ordering defect: a pre-verdict gate demanded a post-verdict artifact."""
    assert "--require-verdict" not in lead, "the flag that caused the ordering bug is back"
    for stage in RB.STAGES:
        assert f"--stage {stage}" in lead, f"the {stage} gate is never invoked"


def _bash_blocks(text: str) -> str:
    """Concatenate only the ```bash fences. A flag *mentioned* in prose (a Quick
    Reference row, a forward reference to a later step) is not an invocation, so a
    plain substring search cannot distinguish "runs here" from "talks about"."""
    return "\n".join(re.findall(r"```bash\n(.*?)```", text, re.S))


def test_bash_block_extractor_separates_invocation_from_mention():
    """Guard the guard: prose outside a fence must not be picked up."""
    sample = "Prose says --stage publication happens later.\n\n```bash\nrun --stage evidence\n```\n"
    blocks = _bash_blocks(sample)
    assert "--stage evidence" in blocks
    assert "--stage publication" not in blocks


def test_the_evidence_gate_is_invoked_before_the_verdict_step(lead):
    """Sections, and only their bash fences. Step 5d-ter legitimately *mentions*
    the publication stage as a forward reference; what it must not do is *run* it,
    because verdict.json does not exist yet."""
    gate_section = lead.index("#### 5d-ter.")
    verdict_section = lead.index("#### 5f. Verdict and Conditions")
    log_section = lead.index("#### 5g. Append Verdict to Log")
    assert gate_section < verdict_section < log_section, "workflow steps are out of order"

    gate_cmds = _bash_blocks(lead[gate_section:verdict_section])
    assert "--stage evidence" in gate_cmds, "5d-ter does not run the evidence gate"
    assert "--stage publication" not in gate_cmds, (
        "5d-ter invokes the publication gate, which demands artifacts Step 5f has not"
        " written yet — this is the exact ordering defect --require-verdict caused"
    )

    log_cmds = _bash_blocks(lead[log_section:])
    assert "--stage publication" in log_cmds, "5g does not run the publication gate"


def test_the_state_machine_is_wired_into_the_lead(lead, dispatch):
    """Point 3: the transitions must be enforced by a tool, not narrated."""
    assert "dispatch.py" in lead, "the lead never plans or records through the state machine"
    for command in ("plan", "record"):
        assert f"dispatch.py {command}" in lead or f"dispatch.py \\\n" in lead, command
    assert "dispatch.py" in dispatch
    assert "referee, not the runner" in dispatch, (
        "the doc must be honest that the orchestrator is still the executor"
    )


def test_retry_artifact_convention_is_stated_where_the_orchestrator_will_read_it(lead):
    assert "attempt<N>.md" in lead or "attempt1.md" in lead, (
        "the orchestrator is never told to persist a superseded reply"
    )


def test_archetype_challenge_is_wired_end_to_end(lead, worker_texts, agent_texts, dispatch):
    """The de-correlation channel is only real if the lead asks for it, the workers
    know how to file it, and the lead is told what to do on receipt."""
    assert "archetype_challenge" in lead
    assert "archetype_contested" in lead, "lead does not handle the >=2-challenge case"
    assert "Archetype challenge" in CONTRACT_MD.read_text(encoding="utf-8")
    assert "archetype_challenge" in dispatch
    for skill, text in worker_texts.items():
        assert "archetype_challenge" in text, f"{skill} cannot file a challenge"
    for agent, text in agent_texts.items():
        assert "archetype_challenge" in text, f"agent {agent} is not told to challenge"


def test_optionality_test_runs_after_data_acquisition(lead):
    """It divides visible-business value by market cap; neither input exists
    before Step 2, so placing it at classification time made it unanswerable."""
    step2 = lead.index("### Step 2: Data Acquisition")
    optionality = lead.index("### Step 2b: Optionality Test")
    triage = lead.index("### Step 3: Triage")
    assert step2 < optionality < triage


def test_prior_verdict_review_runs_after_the_provisional_verdict(lead):
    """Blind-first: reading the prior verdict before analyzing anchors the run and
    puts the workflow in tension with its own anchoring self-check."""
    verdict = lead.index("#### 5f. Verdict and Conditions")
    review = lead.index("#### 5f-bis. Prior Verdict Review")
    dispatch_step = lead.index("### Step 4: Dispatch")
    assert dispatch_step < verdict < review

    # Bound to structure, not prose. Both SKILL.md and verdict-log-protocol.md
    # legitimately *describe* the old ordering to explain why it changed, so a
    # text search for "Step 1.5b" fails on the correction. Headings, TOC links,
    # and `load during` directives are instruction-shaped and cannot be history.
    for revived in ("### Step 1.5b", "#### Step 1.5b", "[Step 1.5b]", "load during Step 1.5b"):
        assert revived not in lead, f"the anchoring-prone step came back as {revived!r}"

    # The positive half: the load directive must point at the late step.
    load_line = next(
        line for line in lead.splitlines() if "verdict-log-protocol.md` — load" in line
    )
    assert "5f-bis" in load_line, f"verdict-log load directive still early: {load_line}"


def test_verdict_log_schema_carries_the_calibration_inputs():
    text = VERDICT_LOG_MD.read_text(encoding="utf-8")
    for field in ("prob_bull", "prob_base", "prob_bear", "probability_anchors",
                  "wacc", "terminal_g", "reverse_dcf_implied_growth",
                  "peer_set", "workers_validated", "quorum", "schema_version"):
        assert field in text, f"verdict-log schema omits {field}"


def test_calibration_loop_is_executable_not_aspirational():
    text = VERDICT_LOG_MD.read_text(encoding="utf-8")
    assert "calibration.py" in text
    calib = LEAD_ROOT / "scripts" / "finlib" / "calibration.py"
    assert calib.exists()


def test_no_file_claims_empirically_calibrated_probabilities():
    """The priors are judgment priors until the tool says otherwise. Any file
    calling them calibrated overstates what the framework has earned."""
    banned = re.compile(r"calibrated probabilit|empirically calibrated|calibrated framework", re.I)
    for path in [LEAD_MD] + sorted((LEAD_ROOT / "references").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            if banned.search(line):
                # A line may discuss the *absence* of calibration.
                assert re.search(r"not yet|uncalibrated|is not|never|deprecated", line, re.I), (
                    f"{path.name}: unearned calibration claim: {line.strip()[:120]}"
                )


def test_persistence_is_opt_in_and_the_path_is_resolved(lead):
    assert "opt-in" in lead.lower()
    assert "STOCK_VERDICT_LOG" in lead, "lead does not document the portable override"
    assert ".claude/projects" not in lead, "lead still prints a personal Claude path"


def test_every_section_cross_reference_resolves():
    """`worker-contract.md` pointed at "`dispatch-protocol.md` § Re-dispatch" while
    no such heading existed. A dangling pointer sends the orchestrator looking for
    rules it will not find, so it silently proceeds without them.

    Whitespace is collapsed first because these references wrap across lines.
    """
    files = sorted((LEAD_ROOT / "references").glob("*.md")) + [LEAD_MD]
    headings = {
        f.name: {m.group(1).strip()
                 for m in re.finditer(r"^#{2,4}\s+(.+?)\s*$", f.read_text(encoding="utf-8"), re.M)}
        for f in files
    }
    unresolved = []
    for f in files:
        flat = re.sub(r"\s+", " ", f.read_text(encoding="utf-8"))
        for match in re.finditer(
            r"`([a-z0-9-]+\.md)`\s*(?:§|Part)\s*([A-Za-z0-9 \-]+?)(?=[.,;)]|\s—|\s`|$)", flat
        ):
            target, section = match.group(1), match.group(2).strip()
            if target not in headings:
                unresolved.append(f"{f.name} -> unknown file {target}")
                continue
            if not any(section.lower() in h.lower() or h.lower().startswith(section.lower())
                       for h in headings[target]):
                unresolved.append(f"{f.name} -> '{target} § {section}' has no such heading")
    assert not unresolved, "\n".join(unresolved)


def test_the_cross_reference_checker_can_fail():
    """Guard the guard: the regex must actually match this reference shape."""
    flat = "see `dispatch-protocol.md` § Nonexistent Section for details"
    found = re.findall(r"`([a-z0-9-]+\.md)`\s*(?:§|Part)\s*([A-Za-z0-9 \-]+?)(?=[.,;)]|\s—|\s`|$)", flat)
    assert found == [("dispatch-protocol.md", "Nonexistent Section for details")], found


def test_dispatch_prompt_names_every_required_contract_key(lead):
    """Compressing the inline schema must not drop a mandatory key: a worker that
    reads only the dispatch prompt has to know what the gate will demand."""
    start = lead.index("### Step 4: Dispatch")
    prompt = lead[start:lead.index("#### Validate every reply", start)]
    for key in (
        "contract_version", "worker", "prefix", "status", "status_reason", "depth_mode",
        "archetype_applied", "archetype_challenge", "findings", "positives", "data_gaps",
        "checklist_coverage", "mandatory_checks_run",
        "id", "severity", "title", "citation", "evidence", "implication", "confidence",
        "source", "locator", "fiscal_period",
    ):
        assert key in prompt, f"the dispatch prompt no longer names required key {key!r}"
