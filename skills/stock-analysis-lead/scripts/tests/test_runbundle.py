"""Tests for the fail-closed, two-stage run-bundle gate.

Two regressions are encoded:

1. **The gate could pass on an incomplete bundle.** Absent `lint.json`,
   `financials.json`, `metrics.json` and `report.md` produced warnings and a PASS,
   which made "the 口径 gate left no evidence it ran" indistinguishable from "it
   ran and passed". Every requirement is now fail-closed, split across the stage
   where the artifact actually exists.
2. **The documented order could not be followed.** Step 5d-ter ran
   `--require-verdict` while `verdict.json` is produced at Step 5f, so obeying
   SKILL.md guaranteed a failure. The stages now match the workflow.

Beyond presence, the gate must catch artifacts that disagree with each other — a
hand-edited payload, a non-reproducible consolidation, a report that dropped a
surviving finding, a model digest that does not match the model on disk.
"""
import hashlib
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from finlib import runbundle as RB  # noqa: E402
from finlib import worker_contract as WC  # noqa: E402

TIER0 = list(RB.TIER0)
TIER1 = list(RB.TIER1)
PREFIX = {name: WC.WORKERS[name][1] for name in WC.WORKERS}
ARCHETYPE = "Hyperscaler / Mega-Cap Tech Platform"
DEPTH = "Standard"


def payload_for(worker: str, status: str = "OK", depth: str = DEPTH, findings=None) -> dict:
    p = {
        "contract_version": "1",
        "worker": worker,
        "prefix": PREFIX[worker],
        "status": status,
        "depth_mode": depth,
        "archetype_applied": ARCHETYPE,
        "archetype_challenge": None,
        "findings": findings or [],
        "positives": [],
        "data_gaps": [],
        "checklist_coverage": {"items_total": 5, "items_checked": 5, "items_not_found": 0,
                               "ids_not_checked": []},
        "mandatory_checks_run": [],
    }
    if status != "OK":
        p["status_reason"] = "test fixture"
    return p


def finding(worker: str, n: int = 1, severity: str = "High") -> dict:
    prefix = PREFIX[worker]
    return {
        "id": f"{prefix}-{n:02d}",
        "severity": severity,
        "title": f"{prefix} finding {n}",
        "citation": {"source": "10-K", "locator": "Item 7", "fiscal_period": "FY2025"},
        "evidence": "quoted evidence",
        "implication": "it matters.",
        "confidence": "first-hand",
    }


def reply(payload: dict) -> str:
    return (f"# {payload['worker']}\n\nprose\n\n```findings-json\n"
            f"{json.dumps(payload, indent=2)}\n```\n")


def full_verdict(**overrides) -> dict:
    """A schema-v3 verdict. The publication gate now validates the whole entry
    in-process, so a three-field stub is no longer a usable fixture."""
    v = {
        "schema_version": "3",
        "ticker": "MSFT", "company_name": "Microsoft Corporation",
        "verdict_date": "2026-08-20", "verdict": "Buy", "conviction": "Medium",
        "current_price": 500.0, "target_base": 600.0, "target_bull": 760.0,
        "target_bear": 430.0,
        "prob_bull": 0.25, "prob_base": 0.55, "prob_bear": 0.20,
        "weighted_expected_price": 606.0, "weighted_return_36mo": 0.212,
        "bear_to_current_ratio": 0.86, "horizon_months": 36,
        "archetype": ARCHETYPE, "good_company_score": 9, "depth_mode": DEPTH,
        "key_bull_assumptions": ["Azure growth holds above 25%"],
        "key_bear_assumptions": ["AI capex digestion cuts Azure growth to 12%"],
        "invalidation_triggers": ["Sell if Azure growth < 15% for two quarters"],
        "workers_validated": list(TIER0), "quorum": "full",
        "dcf": {"wacc": 0.09, "terminal_g": 0.03},
    }
    v.update(overrides)
    return v


def render_report(consolidated: dict) -> str:
    """Render the Findings section the way report_audit.py parses it."""
    blocks = []
    for f in consolidated.get("findings", []):
        cit = f.get("citation") or {}
        blocks.append(
            f"### [{f['severity']}] {f['title']}\n\n"
            f"- **ID**: `{f['id']}`\n"
            f"- **Citation**: {cit.get('source', '')} {cit.get('locator', '')}"
            f" ({cit.get('fiscal_period', '')})\n"
            f"- **Evidence**: {f.get('evidence', '')}\n"
            f"- **Implication**: {f.get('implication', '')}\n"
        )
    return "# MSFT — Investment Analysis Report\n\n## Worker Findings\n\n" + "\n".join(blocks)


def build(tmp_path: Path, workers=None, stage="evidence", verdict=None,
          lint=None, quorum=None, depth=DEPTH, findings_per_worker=False,
          write_payloads=True, write_replies=True, report=None, model=None,
          wave2=None) -> Path:
    """Write a bundle complete for `stage`. ``workers`` is (name, state, status);
    ``wave2`` is (name, state, status, reason)."""
    workers = workers if workers is not None else (
        [(w, "VALIDATED", "OK") for w in TIER0] + [(w, "VALIDATED", "OK") for w in TIER1]
    )
    run = tmp_path / "run"
    (run / "workers").mkdir(parents=True, exist_ok=True)
    (run / "data-manifest.json").write_text('{"ticker": "MSFT", "missing": []}', encoding="utf-8")
    (run / "financials.json").write_text('{"revenue": {"value": 1}}', encoding="utf-8")

    entries, payloads = [], []
    for name, state, status in workers:
        entry = {
            "worker": name,
            "tier": 0 if name in TIER0 else 1,
            "trigger": "always-on" if name in TIER0 else f"depth={depth}",
            "state": state,
            "attempts": 0 if state == "NOT_DISPATCHED" else 1,
            "errors": [],
            "duration_s": 200,
        }
        if status is not None:
            entry["status"] = status
        entries.append(entry)

        if state in RB.STATES_WITH_PAYLOAD or state in RB.STATES_WITH_RAW_ONLY:
            found = [finding(name)] if findings_per_worker else []
            p = payload_for(name, status or "OK", depth, found)
            if write_replies:
                (run / "workers" / f"{name}.md").write_text(reply(p), encoding="utf-8")
            if state in RB.STATES_WITH_PAYLOAD:
                if write_payloads:
                    (run / "workers" / f"{name}.json").write_text(
                        json.dumps(p, indent=2), encoding="utf-8")
                payloads.append(p)

    tier0_ok = sum(1 for n, s, st in workers
                   if n in TIER0 and s in RB.COUNTS_FOR_QUORUM and st in ("OK", "DEGRADED"))
    missing = len(TIER0) - tier0_ok
    permitted = "full" if missing == 0 else ("degraded" if missing == 1 else "none")
    wave2_entries = []
    for name, state, status, reason in (wave2 or []):
        entry = {"worker": name, "reason": reason, "state": state,
                 "attempts": 1, "errors": [], "duration_s": 180,
                 "artifact_stem": f"{name}.wave2"}
        if status is not None:
            entry["status"] = status
        wave2_entries.append(entry)
        if state in RB.STATES_WITH_PAYLOAD or state in RB.STATES_WITH_RAW_ONLY:
            found = [finding(name, n=9)] if findings_per_worker else []
            p = payload_for(name, status or "OK", depth, found)
            (run / "workers" / f"{name}.wave2.md").write_text(reply(p), encoding="utf-8")
            if state in RB.STATES_WITH_PAYLOAD:
                (run / "workers" / f"{name}.wave2.json").write_text(
                    json.dumps(p, indent=2), encoding="utf-8")
                payloads.append(p)

    (run / "dispatch-log.json").write_text(json.dumps({
        "ticker": "MSFT", "depth_mode": depth, "archetype": ARCHETYPE,
        "workers": entries, "wave_2": wave2_entries,
        "quorum": quorum or {"tier0_validated": tier0_ok, "tier0_required": len(TIER0),
                             "verdict_permitted": permitted},
    }, indent=2), encoding="utf-8")

    consolidated = WC.consolidate(payloads, cap=RB.FINDING_CAP[depth])
    (run / "consolidated.json").write_text(json.dumps(consolidated, indent=2), encoding="utf-8")

    if stage == "publication":
        (run / "metrics.json").write_text('{"entries": []}', encoding="utf-8")
        (run / "lint.json").write_text(json.dumps(lint if lint is not None else {"fail": []}),
                                       encoding="utf-8")
        (run / "report.md").write_text(
            report if report is not None else render_report(consolidated), encoding="utf-8")
        # The model digest is mandatory at publication, so every fixture carries one.
        model_text = model if model is not None else '{"drivers": {"revenue_0": 245122}}'
        (run / "model.json").write_text(model_text, encoding="utf-8")
        digest = hashlib.sha256((run / "model.json").read_bytes()).hexdigest()
        v = verdict if verdict is not None else full_verdict(
            conviction="Low" if permitted == "degraded" else "Medium",
            quorum=permitted,
        )
        if isinstance(v, dict) and "model" not in v:
            v = dict(v, model={"engine": "finlib.valuation", "model_json_sha256": digest})
        (run / "verdict.json").write_text(json.dumps(v), encoding="utf-8")
    elif lint is not None:
        (run / "lint.json").write_text(json.dumps(lint), encoding="utf-8")
    return run


# --------------------------------------------------------------------------- #
# stage separation — the ordering contradiction
# --------------------------------------------------------------------------- #

def test_evidence_stage_passes_before_a_verdict_exists(tmp_path):
    """Step 5d-ter runs before Step 5f. The gate must not require a verdict there."""
    run = build(tmp_path, stage="evidence")
    assert not (run / "verdict.json").exists()
    result = RB.check(run, stage="evidence")
    assert result["verdict"] == "PASS", result["errors"]


def test_publication_stage_fails_on_the_same_bundle(tmp_path):
    """The evidence-stage bundle is deliberately not publishable."""
    run = build(tmp_path, stage="evidence")
    result = RB.check(run, stage="publication")
    assert result["verdict"] == "FAIL"
    for name in ("metrics.json", "lint.json", "verdict.json", "report.md"):
        assert any(name in e for e in result["errors"]), name


def test_publication_stage_passes_on_a_complete_bundle(tmp_path):
    result = RB.check(build(tmp_path, stage="publication"), stage="publication")
    assert result["verdict"] == "PASS", result["errors"]


def test_unknown_stage_is_refused(tmp_path):
    result = RB.check(build(tmp_path), stage="final")
    assert result["verdict"] == "FAIL"
    assert any("unknown stage" in e for e in result["errors"])


def test_stage_file_sets_are_nested():
    """Publication must require everything evidence does, or a run could pass the
    later gate while failing the earlier one."""
    assert set(RB.EVIDENCE_FILES) < set(RB.PUBLICATION_FILES)


# --------------------------------------------------------------------------- #
# fail-closed: what used to be a warning
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("name", RB.EVIDENCE_FILES)
def test_every_evidence_file_is_required_not_warned(tmp_path, name):
    run = build(tmp_path, stage="evidence")
    (run / name).unlink()
    result = RB.check(run, stage="evidence")
    assert result["verdict"] == "FAIL", f"{name} absent still passed"
    assert any(name in e for e in result["errors"])


@pytest.mark.parametrize("name", ("metrics.json", "lint.json", "verdict.json", "report.md"))
def test_every_publication_file_is_required_not_warned(tmp_path, name):
    run = build(tmp_path, stage="publication")
    (run / name).unlink()
    result = RB.check(run, stage="publication")
    assert result["verdict"] == "FAIL", f"{name} absent still passed"
    assert any(name in e for e in result["errors"])


def test_absent_lint_json_no_longer_passes_with_a_note(tmp_path):
    """The headline fail-open: no lint evidence used to read as a clean lint."""
    run = build(tmp_path, stage="publication")
    (run / "lint.json").unlink()
    assert RB.check(run, stage="publication")["verdict"] == "FAIL"


def test_recorded_lint_failure_blocks_publication(tmp_path):
    run = build(tmp_path, stage="publication", lint={"fail": [{"id": "ev_fcf"}]})
    result = RB.check(run, stage="publication")
    assert result["verdict"] == "FAIL"
    assert any("口径 gate" in e for e in result["errors"])


def test_an_empty_required_file_is_not_presence(tmp_path):
    run = build(tmp_path, stage="evidence")
    (run / "financials.json").write_text("", encoding="utf-8")
    result = RB.check(run, stage="evidence")
    assert result["verdict"] == "FAIL"
    assert any("empty" in e for e in result["errors"])


def test_the_gate_returns_no_warnings_field(tmp_path):
    """A warnings channel is where fail-open hides. There is no longer one."""
    result = RB.check(build(tmp_path, stage="publication"), stage="publication")
    assert "warnings" not in result


# --------------------------------------------------------------------------- #
# artifacts must agree with each other
# --------------------------------------------------------------------------- #

def test_hand_edited_payload_is_caught(tmp_path):
    """A doctored workers/<w>.json would let the report cite findings the worker
    never returned."""
    run = build(tmp_path, stage="evidence", findings_per_worker=True)
    victim = run / "workers" / f"{TIER0[0]}.json"
    doctored = json.loads(victim.read_text(encoding="utf-8"))
    doctored["findings"][0]["severity"] = "Low"
    victim.write_text(json.dumps(doctored, indent=2), encoding="utf-8")
    result = RB.check(run, stage="evidence")
    assert result["verdict"] == "FAIL"
    assert any("does not match the payload extracted" in e for e in result["errors"])


def test_non_reproducible_consolidation_is_caught(tmp_path):
    """A dropped finding or a raised cap must not survive re-consolidation."""
    run = build(tmp_path, stage="evidence", findings_per_worker=True)
    consolidated = json.loads((run / "consolidated.json").read_text(encoding="utf-8"))
    consolidated["findings"] = consolidated["findings"][:-1]
    (run / "consolidated.json").write_text(json.dumps(consolidated), encoding="utf-8")
    result = RB.check(run, stage="evidence")
    assert result["verdict"] == "FAIL"
    assert any("not reproducible" in e for e in result["errors"])


def test_a_severity_promoted_only_in_consolidated_is_caught(tmp_path):
    run = build(tmp_path, stage="evidence", findings_per_worker=True)
    consolidated = json.loads((run / "consolidated.json").read_text(encoding="utf-8"))
    consolidated["findings"][0]["severity"] = "Low"
    (run / "consolidated.json").write_text(json.dumps(consolidated), encoding="utf-8")
    assert RB.check(run, stage="evidence")["verdict"] == "FAIL"


def test_report_omitting_a_consolidated_finding_is_caught(tmp_path):
    run = build(tmp_path, stage="publication", findings_per_worker=True,
                report="# MSFT\n\nNothing to report.\n")
    result = RB.check(run, stage="publication")
    assert result["verdict"] == "FAIL"
    assert any("omits finding" in e for e in result["errors"]), result["errors"]


def test_report_containing_every_finding_id_passes(tmp_path):
    run = build(tmp_path, stage="publication", findings_per_worker=True)
    assert RB.check(run, stage="publication")["verdict"] == "PASS", \
        RB.check(run, stage="publication")["errors"]


def test_model_digest_mismatch_is_caught(tmp_path):
    """The digest ties the recorded targets to the model that produced them."""
    run = build(tmp_path, stage="publication", model='{"drivers": {"revenue_0": 100}}')
    verdict = json.loads((run / "verdict.json").read_text(encoding="utf-8"))
    verdict["model"] = {"engine": "finlib.valuation", "model_json_sha256": "0" * 64}
    (run / "verdict.json").write_text(json.dumps(verdict), encoding="utf-8")
    result = RB.check(run, stage="publication")
    assert result["verdict"] == "FAIL"
    assert any("model digest mismatch" in e for e in result["errors"])


def test_matching_model_digest_passes(tmp_path):
    model = '{"drivers": {"revenue_0": 100}}'
    run = build(tmp_path, stage="publication", model=model)
    digest = hashlib.sha256((run / "model.json").read_bytes()).hexdigest()
    verdict = json.loads((run / "verdict.json").read_text(encoding="utf-8"))
    verdict["model"] = {"engine": "finlib.valuation", "model_json_sha256": digest}
    (run / "verdict.json").write_text(json.dumps(verdict), encoding="utf-8")
    result = RB.check(run, stage="publication")
    assert result["verdict"] == "PASS", result["errors"]


def test_digest_recorded_without_a_model_on_disk_is_caught(tmp_path):
    run = build(tmp_path, stage="publication")
    (run / "model.json").unlink()      # the builder writes one by default now
    result = RB.check(run, stage="publication")
    assert result["verdict"] == "FAIL"
    assert any("model.json is absent" in e for e in result["errors"]), result["errors"]


def test_a_publication_verdict_without_a_model_digest_is_refused(tmp_path):
    """The digest is mandatory at publication: a target with no recorded model
    cannot be tied to the numbers that produced it."""
    run = build(tmp_path, stage="publication")
    verdict = json.loads((run / "verdict.json").read_text(encoding="utf-8"))
    del verdict["model"]
    (run / "verdict.json").write_text(json.dumps(verdict), encoding="utf-8")
    result = RB.check(run, stage="publication")
    assert result["verdict"] == "FAIL"
    assert any("no model.model_json_sha256" in e for e in result["errors"]), result["errors"]


# --------------------------------------------------------------------------- #
# the verdict schema is validated inside the gate
# --------------------------------------------------------------------------- #

def test_an_incomplete_verdict_is_caught_without_a_separate_command(tmp_path):
    """A final publication gate must not depend on the caller having remembered to
    run `verdictlog.py validate` first."""
    run = build(tmp_path, stage="publication")
    verdict = json.loads((run / "verdict.json").read_text(encoding="utf-8"))
    for field in ("prob_bull", "prob_base", "prob_bear", "key_bull_assumptions"):
        verdict.pop(field, None)
    (run / "verdict.json").write_text(json.dumps(verdict), encoding="utf-8")
    result = RB.check(run, stage="publication")
    assert result["verdict"] == "FAIL"
    assert sum("verdict.json:" in e for e in result["errors"]) >= 4, result["errors"]


def test_probabilities_that_do_not_sum_to_one_are_caught_by_the_gate(tmp_path):
    run = build(tmp_path, stage="publication")
    verdict = json.loads((run / "verdict.json").read_text(encoding="utf-8"))
    verdict["prob_bull"] = 0.45
    (run / "verdict.json").write_text(json.dumps(verdict), encoding="utf-8")
    result = RB.check(run, stage="publication")
    assert result["verdict"] == "FAIL"
    assert any("must sum to 1.00" in e for e in result["errors"]), result["errors"]


def test_a_target_not_reproducible_from_the_probabilities_is_caught(tmp_path):
    run = build(tmp_path, stage="publication")
    verdict = json.loads((run / "verdict.json").read_text(encoding="utf-8"))
    verdict["weighted_expected_price"] = 720.0
    (run / "verdict.json").write_text(json.dumps(verdict), encoding="utf-8")
    result = RB.check(run, stage="publication")
    assert result["verdict"] == "FAIL"
    assert any("prob×target" in e for e in result["errors"]), result["errors"]


def test_terminal_growth_above_wacc_is_caught_by_the_gate(tmp_path):
    run = build(tmp_path, stage="publication")
    verdict = json.loads((run / "verdict.json").read_text(encoding="utf-8"))
    verdict["dcf"] = {"wacc": 0.07, "terminal_g": 0.09}
    (run / "verdict.json").write_text(json.dumps(verdict), encoding="utf-8")
    result = RB.check(run, stage="publication")
    assert result["verdict"] == "FAIL"
    assert any("Gordon terminal value" in e for e in result["errors"]), result["errors"]


# --------------------------------------------------------------------------- #
# report fidelity — distortion, not just omission
# --------------------------------------------------------------------------- #

def test_a_rewritten_evidence_line_is_caught(tmp_path):
    """The whole point of widening the check: keeping the ID while replacing the
    worker's quote used to pass."""
    run = build(tmp_path, stage="publication", findings_per_worker=True)
    report = (run / "report.md").read_text(encoding="utf-8")
    (run / "report.md").write_text(
        report.replace("quoted evidence", "management characterises this as immaterial"),
        encoding="utf-8")
    result = RB.check(run, stage="publication")
    assert result["verdict"] == "FAIL"
    assert any("evidence does not carry the worker" in e for e in result["errors"]), result["errors"]


def test_a_downgraded_severity_in_the_report_is_caught(tmp_path):
    run = build(tmp_path, stage="publication", findings_per_worker=True)
    report = (run / "report.md").read_text(encoding="utf-8")
    (run / "report.md").write_text(report.replace("### [High]", "### [Low]", 1), encoding="utf-8")
    result = RB.check(run, stage="publication")
    assert result["verdict"] == "FAIL"


def test_a_fabricated_finding_in_the_report_is_caught(tmp_path):
    run = build(tmp_path, stage="publication", findings_per_worker=True)
    with open(run / "report.md", "a", encoding="utf-8") as f:
        f.write("\n### [High] Undisclosed related-party transactions\n\n"
                "- **ID**: `BUS-99`\n- **Citation**: 10-K Item 13\n"
                "- **Evidence**: invented\n- **Implication**: invented\n")
    result = RB.check(run, stage="publication")
    assert result["verdict"] == "FAIL"
    assert any("not in consolidated.json" in e for e in result["errors"]), result["errors"]


# --------------------------------------------------------------------------- #
# consolidation is compared on every field, not just the IDs
# --------------------------------------------------------------------------- #

def test_a_rewritten_evidence_in_consolidated_is_caught(tmp_path):
    """The projection used to compare only id/severity/reported_by, so rewriting
    the evidence while keeping the ID survived re-consolidation."""
    run = build(tmp_path, stage="evidence", findings_per_worker=True)
    consolidated = json.loads((run / "consolidated.json").read_text(encoding="utf-8"))
    consolidated["findings"][0]["evidence"] = "softened summary"
    (run / "consolidated.json").write_text(json.dumps(consolidated), encoding="utf-8")
    result = RB.check(run, stage="evidence")
    assert result["verdict"] == "FAIL"
    assert any("not reproducible" in e for e in result["errors"]), result["errors"]


@pytest.mark.parametrize("field,value", [
    ("title", "a friendlier title"),
    ("implication", "nothing to worry about"),
    ("confidence", "second-hand"),
    ("citation", {"source": "aggregator", "locator": "blog", "fiscal_period": "FY2025"}),
])
def test_every_finding_field_is_compared(tmp_path, field, value):
    run = build(tmp_path, stage="evidence", findings_per_worker=True)
    consolidated = json.loads((run / "consolidated.json").read_text(encoding="utf-8"))
    consolidated["findings"][0][field] = value
    (run / "consolidated.json").write_text(json.dumps(consolidated), encoding="utf-8")
    assert RB.check(run, stage="evidence")["verdict"] == "FAIL", f"{field} not compared"


def test_the_projection_covers_every_finding_field_the_contract_defines():
    """Guard against the projection silently narrowing again: every field a worker
    may put in a finding must be in FINDING_FIELDS."""
    contract_fields = {"id", "severity", "title", "citation", "evidence",
                       "implication", "confidence"}
    assert contract_fields <= set(RB.FINDING_FIELDS), contract_fields - set(RB.FINDING_FIELDS)


# --------------------------------------------------------------------------- #
# wave 2 is audited like wave 1
# --------------------------------------------------------------------------- #

def test_a_validated_wave2_worker_passes(tmp_path):
    run = build(tmp_path, stage="evidence", findings_per_worker=True,
                wave2=[("stock-industry-reviewer", "VALIDATED", "OK", "share claim vs P-01")])
    result = RB.check(run, stage="evidence")
    assert result["verdict"] == "PASS", result["errors"]
    assert result["wave2_dispatched"] == ["stock-industry-reviewer"]
    assert result["wave2_payloads_consumed"] == 1


def test_a_wave2_worker_without_its_reply_is_caught(tmp_path):
    run = build(tmp_path, stage="evidence",
                wave2=[("stock-industry-reviewer", "VALIDATED", "OK", "conflict")])
    (run / "workers" / "stock-industry-reviewer.wave2.md").unlink()
    result = RB.check(run, stage="evidence")
    assert result["verdict"] == "FAIL"
    assert any("wave2.md is absent" in e for e in result["errors"]), result["errors"]


def test_a_wave2_worker_without_its_payload_is_caught(tmp_path):
    run = build(tmp_path, stage="evidence",
                wave2=[("stock-industry-reviewer", "VALIDATED", "OK", "conflict")])
    (run / "workers" / "stock-industry-reviewer.wave2.json").unlink()
    result = RB.check(run, stage="evidence")
    assert result["verdict"] == "FAIL"
    assert any("wave2.json is absent" in e for e in result["errors"]), result["errors"]


def test_a_wave2_reply_that_fails_the_contract_is_caught(tmp_path):
    run = build(tmp_path, stage="evidence",
                wave2=[("stock-industry-reviewer", "VALIDATED", "OK", "conflict")])
    (run / "workers" / "stock-industry-reviewer.wave2.md").write_text(
        "# no fence\n", encoding="utf-8")
    result = RB.check(run, stage="evidence")
    assert result["verdict"] == "FAIL"
    assert any("fails contract validation" in e for e in result["errors"]), result["errors"]


def test_a_hand_edited_wave2_payload_is_caught(tmp_path):
    run = build(tmp_path, stage="evidence", findings_per_worker=True,
                wave2=[("stock-industry-reviewer", "VALIDATED", "OK", "conflict")])
    path = run / "workers" / "stock-industry-reviewer.wave2.json"
    doctored = json.loads(path.read_text(encoding="utf-8"))
    doctored["findings"][0]["severity"] = "Low"
    path.write_text(json.dumps(doctored, indent=2), encoding="utf-8")
    result = RB.check(run, stage="evidence")
    assert result["verdict"] == "FAIL"
    assert any("does not match the payload extracted" in e for e in result["errors"]), result["errors"]


def test_a_non_terminal_wave2_state_is_caught(tmp_path):
    """Wave 2 previously got no state-quality check at all."""
    run = build(tmp_path, stage="evidence",
                wave2=[("stock-industry-reviewer", "RUNNING", None, "conflict")])
    result = RB.check(run, stage="evidence")
    assert result["verdict"] == "FAIL"
    assert any("non-terminal" in e for e in result["errors"]), result["errors"]


def test_wave2_attempts_above_the_cap_are_caught(tmp_path):
    run = build(tmp_path, stage="evidence",
                wave2=[("stock-industry-reviewer", "VALIDATED", "OK", "conflict")])
    log = json.loads((run / "dispatch-log.json").read_text(encoding="utf-8"))
    log["wave_2"][0]["attempts"] = 5
    (run / "dispatch-log.json").write_text(json.dumps(log), encoding="utf-8")
    result = RB.check(run, stage="evidence")
    assert result["verdict"] == "FAIL"
    assert any("wave 2" in e and "outside 1.." in e for e in result["errors"]), result["errors"]


def test_a_wave2_entry_without_a_duration_is_caught(tmp_path):
    run = build(tmp_path, stage="evidence",
                wave2=[("stock-industry-reviewer", "VALIDATED", "OK", "conflict")])
    log = json.loads((run / "dispatch-log.json").read_text(encoding="utf-8"))
    del log["wave_2"][0]["duration_s"]
    (run / "dispatch-log.json").write_text(json.dumps(log), encoding="utf-8")
    result = RB.check(run, stage="evidence")
    assert result["verdict"] == "FAIL"
    assert any("wave 2" in e and "duration_s" in e for e in result["errors"]), result["errors"]


def test_two_wave2_entries_for_one_worker_are_caught(tmp_path):
    run = build(tmp_path, stage="evidence",
                wave2=[("stock-industry-reviewer", "VALIDATED", "OK", "conflict")])
    log = json.loads((run / "dispatch-log.json").read_text(encoding="utf-8"))
    log["wave_2"].append(dict(log["wave_2"][0]))
    (run / "dispatch-log.json").write_text(json.dumps(log), encoding="utf-8")
    result = RB.check(run, stage="evidence")
    assert result["verdict"] == "FAIL"
    assert any("two wave-2 entries" in e for e in result["errors"]), result["errors"]


def test_an_unrecorded_wave2_reply_on_disk_is_caught(tmp_path):
    """The mirror-image leak: a second-wave reply nobody logged."""
    run = build(tmp_path, stage="evidence")
    (run / "workers" / "stock-industry-reviewer.wave2.md").write_text(
        reply(payload_for("stock-industry-reviewer")), encoding="utf-8")
    result = RB.check(run, stage="evidence")
    assert result["verdict"] == "FAIL"
    assert any("no wave_2 entry claims it" in e for e in result["errors"]), result["errors"]


def test_wave2_findings_must_reach_consolidation(tmp_path):
    """A second wave answers a scoped question whose findings belong in the report;
    excluding them from consolidation would silently discard them."""
    run = build(tmp_path, stage="evidence", findings_per_worker=True,
                wave2=[("stock-industry-reviewer", "VALIDATED", "OK", "conflict")])
    consolidated = json.loads((run / "consolidated.json").read_text(encoding="utf-8"))
    ids = {f["id"] for f in consolidated["findings"]}
    assert "IND-09" in ids, f"the wave-2 finding is missing from consolidation: {sorted(ids)}"
    assert RB.check(run, stage="evidence")["verdict"] == "PASS"


def test_dropping_the_wave2_finding_from_consolidated_is_caught(tmp_path):
    run = build(tmp_path, stage="evidence", findings_per_worker=True,
                wave2=[("stock-industry-reviewer", "VALIDATED", "OK", "conflict")])
    consolidated = json.loads((run / "consolidated.json").read_text(encoding="utf-8"))
    consolidated["findings"] = [f for f in consolidated["findings"] if f["id"] != "IND-09"]
    (run / "consolidated.json").write_text(json.dumps(consolidated), encoding="utf-8")
    assert RB.check(run, stage="evidence")["verdict"] == "FAIL"


# --------------------------------------------------------------------------- #
# retry and second-wave evidence
# --------------------------------------------------------------------------- #

def test_a_claimed_retry_without_its_failed_reply_is_caught(tmp_path):
    """"We retried after a MISSING_BLOCK" must be verifiable, not asserted."""
    run = build(tmp_path, stage="evidence")
    log = json.loads((run / "dispatch-log.json").read_text(encoding="utf-8"))
    log["workers"][0]["attempts"] = 2
    log["workers"][0]["errors"] = [{"attempt": 1, "code": "MISSING_BLOCK"}]
    (run / "dispatch-log.json").write_text(json.dumps(log), encoding="utf-8")
    result = RB.check(run, stage="evidence")
    assert result["verdict"] == "FAIL"
    assert any("attempt1.md is absent" in e for e in result["errors"])


def test_a_retry_with_its_failed_reply_on_disk_passes(tmp_path):
    run = build(tmp_path, stage="evidence")
    log = json.loads((run / "dispatch-log.json").read_text(encoding="utf-8"))
    name = log["workers"][0]["worker"]
    log["workers"][0]["attempts"] = 2
    log["workers"][0]["errors"] = [{"attempt": 1, "code": "MISSING_BLOCK"}]
    (run / "dispatch-log.json").write_text(json.dumps(log), encoding="utf-8")
    (run / "workers" / f"{name}.attempt1.md").write_text("# no fence here\n", encoding="utf-8")
    result = RB.check(run, stage="evidence")
    assert result["verdict"] == "PASS", result["errors"]


def test_a_retry_with_no_recorded_error_is_caught(tmp_path):
    run = build(tmp_path, stage="evidence")
    log = json.loads((run / "dispatch-log.json").read_text(encoding="utf-8"))
    name = log["workers"][0]["worker"]
    log["workers"][0]["attempts"] = 2
    (run / "dispatch-log.json").write_text(json.dumps(log), encoding="utf-8")
    (run / "workers" / f"{name}.attempt1.md").write_text("x", encoding="utf-8")
    result = RB.check(run, stage="evidence")
    assert result["verdict"] == "FAIL"
    assert any("errors[] is empty" in e for e in result["errors"])


def test_a_retry_after_a_non_retryable_code_is_caught(tmp_path):
    run = build(tmp_path, stage="evidence")
    log = json.loads((run / "dispatch-log.json").read_text(encoding="utf-8"))
    name = log["workers"][0]["worker"]
    log["workers"][0]["attempts"] = 2
    log["workers"][0]["errors"] = [{"attempt": 1, "code": "WORKER_MISMATCH"}]
    (run / "dispatch-log.json").write_text(json.dumps(log), encoding="utf-8")
    (run / "workers" / f"{name}.attempt1.md").write_text("x", encoding="utf-8")
    result = RB.check(run, stage="evidence")
    assert result["verdict"] == "FAIL"
    assert any("non-retryable" in e for e in result["errors"])


def test_attempts_above_the_cap_are_caught(tmp_path):
    run = build(tmp_path, stage="evidence")
    log = json.loads((run / "dispatch-log.json").read_text(encoding="utf-8"))
    log["workers"][0]["attempts"] = 4
    (run / "dispatch-log.json").write_text(json.dumps(log), encoding="utf-8")
    result = RB.check(run, stage="evidence")
    assert result["verdict"] == "FAIL"
    assert any(f"outside 1..{RB.MAX_ATTEMPTS}" in e for e in result["errors"])


def test_second_wave_beyond_the_depth_cap_is_caught(tmp_path):
    run = build(tmp_path, stage="evidence", depth="Standard")
    log = json.loads((run / "dispatch-log.json").read_text(encoding="utf-8"))
    log["wave_2"] = [
        {"worker": w, "reason": "conflict", "state": "VALIDATED", "attempts": 1, "errors": []}
        for w in TIER0[:3]
    ]
    (run / "dispatch-log.json").write_text(json.dumps(log), encoding="utf-8")
    result = RB.check(run, stage="evidence")
    assert result["verdict"] == "FAIL"
    assert any("exceeds the Standard cap" in e for e in result["errors"])


def test_second_wave_without_a_reason_is_caught(tmp_path):
    run = build(tmp_path, stage="evidence")
    log = json.loads((run / "dispatch-log.json").read_text(encoding="utf-8"))
    log["wave_2"] = [{"worker": TIER0[0], "state": "VALIDATED", "attempts": 1, "errors": []}]
    (run / "dispatch-log.json").write_text(json.dumps(log), encoding="utf-8")
    result = RB.check(run, stage="evidence")
    assert result["verdict"] == "FAIL"
    assert any("no reason" in e for e in result["errors"])


def test_retry_and_wave2_artifacts_are_not_reported_as_orphans(tmp_path):
    run = build(tmp_path, stage="evidence")
    name = TIER0[0]
    log = json.loads((run / "dispatch-log.json").read_text(encoding="utf-8"))
    log["workers"][0]["attempts"] = 2
    log["workers"][0]["errors"] = [{"attempt": 1, "code": "BAD_JSON"}]
    (run / "dispatch-log.json").write_text(json.dumps(log), encoding="utf-8")
    (run / "workers" / f"{name}.attempt1.md").write_text("x", encoding="utf-8")
    (run / "workers" / f"{name}.wave2.md").write_text("x", encoding="utf-8")
    result = RB.check(run, stage="evidence")
    assert not any("orphan" in e or "absent from dispatch-log" in e for e in result["errors"]), \
        result["errors"]


# --------------------------------------------------------------------------- #
# dispatch-log legality
# --------------------------------------------------------------------------- #

def test_a_missing_tier1_entry_is_caught(tmp_path):
    """Omitting a skipped worker reads as "it ran"; it must be NOT_DISPATCHED."""
    run = build(tmp_path, stage="evidence",
                workers=[(w, "VALIDATED", "OK") for w in TIER0])
    result = RB.check(run, stage="evidence")
    assert result["verdict"] == "FAIL"
    assert any("record it as NOT_DISPATCHED" in e for e in result["errors"])


def test_not_dispatched_without_a_trigger_is_caught(tmp_path):
    run = build(tmp_path, stage="evidence",
                workers=[(w, "VALIDATED", "OK") for w in TIER0]
                        + [(w, "NOT_DISPATCHED", None) for w in TIER1])
    log = json.loads((run / "dispatch-log.json").read_text(encoding="utf-8"))
    for entry in log["workers"]:
        if entry["state"] == "NOT_DISPATCHED":
            entry.pop("trigger", None)
    (run / "dispatch-log.json").write_text(json.dumps(log), encoding="utf-8")
    result = RB.check(run, stage="evidence")
    assert result["verdict"] == "FAIL"
    assert any("trigger that did not fire" in e for e in result["errors"])


def test_not_dispatched_tier1_workers_pass_when_recorded(tmp_path):
    run = build(tmp_path, stage="evidence",
                workers=[(w, "VALIDATED", "OK") for w in TIER0]
                        + [(w, "NOT_DISPATCHED", None) for w in TIER1])
    result = RB.check(run, stage="evidence")
    assert result["verdict"] == "PASS", result["errors"]


def test_a_missing_tier0_entry_is_caught(tmp_path):
    run = build(tmp_path, stage="evidence",
                workers=[(w, "VALIDATED", "OK") for w in TIER0[1:]]
                        + [(w, "NOT_DISPATCHED", None) for w in TIER1])
    result = RB.check(run, stage="evidence")
    assert result["verdict"] == "FAIL"
    assert any("always dispatched" in e for e in result["errors"])


def test_a_wrong_tier_label_is_caught(tmp_path):
    run = build(tmp_path, stage="evidence")
    log = json.loads((run / "dispatch-log.json").read_text(encoding="utf-8"))
    log["workers"][0]["tier"] = 1
    (run / "dispatch-log.json").write_text(json.dumps(log), encoding="utf-8")
    result = RB.check(run, stage="evidence")
    assert result["verdict"] == "FAIL"
    assert any("Tier-0 worker" in e for e in result["errors"])


def test_a_tier1_worker_without_a_trigger_is_caught(tmp_path):
    run = build(tmp_path, stage="evidence")
    log = json.loads((run / "dispatch-log.json").read_text(encoding="utf-8"))
    for entry in log["workers"]:
        if entry["worker"] in TIER1:
            entry.pop("trigger", None)
    (run / "dispatch-log.json").write_text(json.dumps(log), encoding="utf-8")
    result = RB.check(run, stage="evidence")
    assert result["verdict"] == "FAIL"
    assert any("without recording its trigger" in e for e in result["errors"])


@pytest.mark.parametrize("state", RB.NON_TERMINAL_STATES)
def test_a_mid_flight_bundle_is_caught(tmp_path, state):
    """A worker still PENDING/RUNNING means the run is not finished."""
    run = build(tmp_path, stage="evidence")
    log = json.loads((run / "dispatch-log.json").read_text(encoding="utf-8"))
    log["workers"][0]["state"] = state
    log["workers"][0].pop("status", None)
    (run / "dispatch-log.json").write_text(json.dumps(log), encoding="utf-8")
    result = RB.check(run, stage="evidence")
    assert result["verdict"] == "FAIL"
    assert any("non-terminal" in e for e in result["errors"])


def test_a_missing_duration_is_caught(tmp_path):
    run = build(tmp_path, stage="evidence")
    log = json.loads((run / "dispatch-log.json").read_text(encoding="utf-8"))
    log["workers"][0].pop("duration_s")
    (run / "dispatch-log.json").write_text(json.dumps(log), encoding="utf-8")
    result = RB.check(run, stage="evidence")
    assert result["verdict"] == "FAIL"
    assert any("duration_s" in e for e in result["errors"])


def test_a_bad_depth_or_absent_archetype_is_caught(tmp_path):
    run = build(tmp_path, stage="evidence")
    log = json.loads((run / "dispatch-log.json").read_text(encoding="utf-8"))
    log["depth_mode"] = "Deep"
    log.pop("archetype")
    (run / "dispatch-log.json").write_text(json.dumps(log), encoding="utf-8")
    result = RB.check(run, stage="evidence")
    assert result["verdict"] == "FAIL"
    assert any("depth_mode" in e for e in result["errors"])
    assert any("archetype is required" in e for e in result["errors"])


def test_a_duplicate_worker_entry_is_caught(tmp_path):
    run = build(tmp_path, stage="evidence")
    log = json.loads((run / "dispatch-log.json").read_text(encoding="utf-8"))
    log["workers"].append(dict(log["workers"][0]))
    (run / "dispatch-log.json").write_text(json.dumps(log), encoding="utf-8")
    result = RB.check(run, stage="evidence")
    assert result["verdict"] == "FAIL"
    assert any("twice in wave 1" in e for e in result["errors"])


def test_unknown_state_and_worker_are_caught(tmp_path):
    run = build(tmp_path, stage="evidence")
    log = json.loads((run / "dispatch-log.json").read_text(encoding="utf-8"))
    log["workers"][0]["state"] = "PROBABLY_FINE"
    log["workers"].append({"worker": "stock-vibes-reviewer", "tier": 1, "state": "VALIDATED"})
    (run / "dispatch-log.json").write_text(json.dumps(log), encoding="utf-8")
    result = RB.check(run, stage="evidence")
    assert result["verdict"] == "FAIL"
    assert any("not a known dispatch state" in e for e in result["errors"])
    assert any("unknown worker" in e for e in result["errors"])


def test_corrupt_dispatch_log_fails(tmp_path):
    run = build(tmp_path, stage="evidence")
    (run / "dispatch-log.json").write_text("{not json", encoding="utf-8")
    result = RB.check(run, stage="evidence")
    assert result["verdict"] == "FAIL"
    assert any("invalid JSON" in e for e in result["errors"])


def test_missing_run_dir_fails(tmp_path):
    result = RB.check(tmp_path / "nope")
    assert result["verdict"] == "FAIL"
    assert any("not found" in e for e in result["errors"])


# --------------------------------------------------------------------------- #
# disk footprint must match state
# --------------------------------------------------------------------------- #

def test_validated_worker_without_a_raw_reply_fails(tmp_path):
    run = build(tmp_path, stage="evidence", write_replies=False)
    result = RB.check(run, stage="evidence")
    assert result["verdict"] == "FAIL"
    assert any(".md is absent" in e for e in result["errors"])


def test_validated_worker_without_an_extracted_payload_fails(tmp_path):
    run = build(tmp_path, stage="evidence", write_payloads=False)
    result = RB.check(run, stage="evidence")
    assert result["verdict"] == "FAIL"
    assert any(".json is absent" in e for e in result["errors"])


def test_a_state_claiming_no_reply_while_a_reply_exists_fails(tmp_path):
    """A TIMEOUT with a reply on disk means one of the two is a lie."""
    run = build(tmp_path, stage="evidence")
    log = json.loads((run / "dispatch-log.json").read_text(encoding="utf-8"))
    log["workers"][0]["state"] = "TIMEOUT"
    log["workers"][0]["attempts"] = 2
    log["workers"][0]["errors"] = [{"attempt": 1, "code": "TIMEOUT"}]
    log["quorum"] = {"tier0_validated": 3, "tier0_required": 4, "verdict_permitted": "degraded"}
    (run / "dispatch-log.json").write_text(json.dumps(log), encoding="utf-8")
    name = log["workers"][0]["worker"]
    (run / "workers" / f"{name}.attempt1.md").write_text("x", encoding="utf-8")
    result = RB.check(run, stage="evidence")
    assert result["verdict"] == "FAIL"
    assert any("claims no reply arrived, yet" in e for e in result["errors"])


def test_orphan_reply_not_in_the_log_fails(tmp_path):
    run = build(tmp_path, stage="evidence")
    (run / "workers" / "stock-management-reviewer.md").unlink()
    (run / "workers" / "stock-management-reviewer.json").unlink()
    log = json.loads((run / "dispatch-log.json").read_text(encoding="utf-8"))
    log["workers"] = [w for w in log["workers"] if w["worker"] != "stock-management-reviewer"]
    (run / "dispatch-log.json").write_text(json.dumps(log), encoding="utf-8")
    (run / "workers" / "stock-management-reviewer.md").write_text(
        reply(payload_for("stock-management-reviewer")), encoding="utf-8")
    result = RB.check(run, stage="evidence")
    assert result["verdict"] == "FAIL"
    assert any("absent from dispatch-log" in e for e in result["errors"])


def test_empty_reply_file_fails_rather_than_counting_as_present(tmp_path):
    run = build(tmp_path, stage="evidence")
    (run / "workers" / f"{TIER0[0]}.md").write_text("", encoding="utf-8")
    result = RB.check(run, stage="evidence")
    assert result["verdict"] == "FAIL"
    assert any("fails contract validation" in e for e in result["errors"])


def test_reply_status_must_match_the_logged_status(tmp_path):
    run = build(tmp_path, stage="evidence")
    (run / "workers" / f"{TIER0[0]}.md").write_text(
        reply(payload_for(TIER0[0], status="DEGRADED")), encoding="utf-8")
    result = RB.check(run, stage="evidence")
    assert result["verdict"] == "FAIL"
    assert any("dispatch-log records status" in e for e in result["errors"])


def test_a_skipped_payload_logged_as_validated_is_caught(tmp_path):
    """SKIPPED must not be laundered into VALIDATED — the dimension is uncovered."""
    run = build(tmp_path, stage="evidence")
    name = TIER0[0]
    p = payload_for(name, status="SKIPPED")
    (run / "workers" / f"{name}.md").write_text(reply(p), encoding="utf-8")
    (run / "workers" / f"{name}.json").write_text(json.dumps(p, indent=2), encoding="utf-8")
    result = RB.check(run, stage="evidence")
    assert result["verdict"] == "FAIL"
    assert any("implies state SKIPPED" in e or "records status" in e for e in result["errors"])


def test_reply_from_the_wrong_worker_or_depth_fails(tmp_path):
    run = build(tmp_path, stage="evidence")
    (run / "workers" / f"{TIER0[0]}.md").write_text(
        reply(payload_for("stock-management-reviewer")), encoding="utf-8")
    assert RB.check(run, stage="evidence")["verdict"] == "FAIL"

    run2 = build(tmp_path / "b", stage="evidence")
    (run2 / "workers" / f"{TIER0[0]}.md").write_text(
        reply(payload_for(TIER0[0], depth="Lite")), encoding="utf-8")
    assert RB.check(run2, stage="evidence")["verdict"] == "FAIL"


# --------------------------------------------------------------------------- #
# quorum, recomputed
# --------------------------------------------------------------------------- #

def test_quorum_is_recomputed_from_states(tmp_path):
    workers = ([(TIER0[0], "TIMEOUT", None)] + [(w, "VALIDATED", "OK") for w in TIER0[1:]]
               + [(w, "NOT_DISPATCHED", None) for w in TIER1])
    run = build(tmp_path, stage="evidence", workers=workers,
                quorum={"tier0_validated": 4, "tier0_required": 4, "verdict_permitted": "full"})
    result = RB.check(run, stage="evidence")
    assert result["verdict"] == "FAIL"
    assert result["tier0_validated"] == 3
    assert result["verdict_permitted"] == "degraded"
    assert any("quorum mismatch" in e for e in result["errors"])


def test_verdict_present_while_quorum_forbids_it_fails(tmp_path):
    workers = ([(TIER0[0], "FAILED", None), (TIER0[1], "FAILED", None)]
               + [(w, "VALIDATED", "OK") for w in TIER0[2:]]
               + [(w, "NOT_DISPATCHED", None) for w in TIER1])
    run = build(tmp_path, stage="publication", workers=workers,
                verdict=full_verdict(conviction="Low", quorum="none"))
    log = json.loads((run / "dispatch-log.json").read_text(encoding="utf-8"))
    for entry in log["workers"]:
        if entry["state"] == "FAILED":
            entry["attempts"] = 2
            entry["errors"] = [{"attempt": 1, "code": "TIMEOUT"}]
    (run / "dispatch-log.json").write_text(json.dumps(log), encoding="utf-8")
    for name in (TIER0[0], TIER0[1]):
        (run / "workers" / f"{name}.attempt1.md").write_text("x", encoding="utf-8")
    result = RB.check(run, stage="publication")
    assert result["verdict"] == "FAIL"
    assert any("quorum forbids a verdict" in e for e in result["errors"])


def test_degraded_quorum_forces_low_conviction(tmp_path):
    workers = ([(TIER0[0], "SKIPPED", "SKIPPED")] + [(w, "VALIDATED", "OK") for w in TIER0[1:]]
               + [(w, "NOT_DISPATCHED", None) for w in TIER1])
    run = build(tmp_path, stage="publication", workers=workers,
                verdict=full_verdict(conviction="High", quorum="degraded"))
    result = RB.check(run, stage="publication")
    assert result["verdict"] == "FAIL"
    assert any("caps conviction at Low" in e for e in result["errors"])


def test_verdict_recording_a_different_quorum_is_caught(tmp_path):
    workers = ([(TIER0[0], "SKIPPED", "SKIPPED")] + [(w, "VALIDATED", "OK") for w in TIER0[1:]]
               + [(w, "NOT_DISPATCHED", None) for w in TIER1])
    run = build(tmp_path, stage="publication", workers=workers,
                verdict=full_verdict(conviction="Low", quorum="full"))
    result = RB.check(run, stage="publication")
    assert result["verdict"] == "FAIL"
    assert any("verdict.json records quorum" in e for e in result["errors"])


def test_missing_balance_sheet_worker_caps_the_verdict_at_watch(tmp_path):
    bs = "stock-balance-sheet-reviewer"
    workers = ([(bs, "SKIPPED", "SKIPPED")] + [(w, "VALIDATED", "OK") for w in TIER0 if w != bs]
               + [(w, "NOT_DISPATCHED", None) for w in TIER1])
    run = build(tmp_path, stage="publication", workers=workers,
                verdict=full_verdict(conviction="Low", quorum="degraded"))
    result = RB.check(run, stage="publication")
    assert result["verdict"] == "FAIL"
    assert any("cap at Watch" in e for e in result["errors"])

    run2 = build(tmp_path / "b", stage="publication", workers=workers,
                 verdict=full_verdict(verdict="Watch", conviction="Low", quorum="degraded"))
    result2 = RB.check(run2, stage="publication")
    assert result2["verdict"] == "PASS", result2["errors"]


def test_missing_quorum_block_is_caught(tmp_path):
    run = build(tmp_path, stage="evidence")
    log = json.loads((run / "dispatch-log.json").read_text(encoding="utf-8"))
    del log["quorum"]
    (run / "dispatch-log.json").write_text(json.dumps(log), encoding="utf-8")
    result = RB.check(run, stage="evidence")
    assert result["verdict"] == "FAIL"
    assert any("missing quorum block" in e for e in result["errors"])


# --------------------------------------------------------------------------- #
# CLI + doc agreement
# --------------------------------------------------------------------------- #

def test_cli_stage_flag_and_exit_codes(tmp_path, capsys):
    run = build(tmp_path, stage="publication")
    assert RB.main(["check", "--run", str(run), "--stage", "publication"]) == 0
    assert json.loads(capsys.readouterr().out)["verdict"] == "PASS"
    assert RB.main(["check", "--run", str(run), "--stage", "evidence"]) == 0
    capsys.readouterr()
    (run / "consolidated.json").unlink()
    assert RB.main(["check", "--run", str(run), "--stage", "evidence"]) == 1
    assert json.loads(capsys.readouterr().out)["verdict"] == "FAIL"


def test_cli_defaults_to_the_evidence_stage(tmp_path, capsys):
    """The default must be the stage that runs first, so a bare invocation cannot
    fail for an artifact that does not exist yet."""
    run = build(tmp_path, stage="evidence")
    assert RB.main(["check", "--run", str(run)]) == 0
    assert json.loads(capsys.readouterr().out)["stage"] == "evidence"


def test_state_partition_is_exhaustive_and_documented():
    buckets = (RB.STATES_WITH_PAYLOAD, RB.STATES_WITH_RAW_ONLY, RB.STATES_WITHOUT_REPLY)
    flat = [s for bucket in buckets for s in bucket]
    assert len(flat) == len(set(flat)), "a state appears in two buckets"
    assert set(RB.ALL_STATES) == set(flat)
    assert set(RB.NON_TERMINAL_STATES) <= set(RB.ALL_STATES)
    assert set(RB.COUNTS_FOR_QUORUM) <= set(RB.STATES_WITH_PAYLOAD)

    ref = Path(__file__).resolve().parents[2] / "references" / "dispatch-protocol.md"
    text = ref.read_text(encoding="utf-8")
    for state in RB.ALL_STATES:
        assert f"`{state}`" in text, f"state {state} not documented"


def test_both_stages_are_documented():
    ref = Path(__file__).resolve().parents[2] / "references" / "dispatch-protocol.md"
    text = ref.read_text(encoding="utf-8")
    for stage in RB.STAGES:
        assert f"`{stage}`" in text, f"stage {stage} not documented"
    for name in RB.PUBLICATION_FILES:
        assert name in text, f"required file {name} not documented in the bundle layout"
