"""End-to-end walk of the CLI sequence SKILL.md tells the orchestrator to run.

The regression this exists for: v3 wired ``runbundle.py check --require-verdict``
into Step 5d-ter while ``verdict.json`` is produced at Step 5f. Following the
documented order guaranteed a failure — and the unit suites missed it because each
tested a mode in isolation while nothing walked the sequence in order.

So this file walks it **in order**, from ``dispatch.py plan`` through
``verdictlog.py append``, asserting that each stage's real output is accepted by
the next stage's real input, and that the pre-verdict gate passes at the point the
workflow actually reaches it.

Tools are driven through ``main(argv)`` rather than their Python API, so a flag
renamed in a module but not in SKILL.md shows up here.
"""
import hashlib
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from finlib import calibration as CAL  # noqa: E402
from finlib import dispatch as D  # noqa: E402
from finlib import runbundle as RB  # noqa: E402
from finlib import verdictlog as VL  # noqa: E402
from finlib import worker_contract as WC  # noqa: E402

LEAD_ROOT = Path(__file__).resolve().parents[2]
SKILL_MD = LEAD_ROOT / "SKILL.md"
SKILLS_DIR = LEAD_ROOT.parents[1] / "skills"

DEPTH = "Standard"
ARCHETYPE = "Hyperscaler / Mega-Cap Tech Platform"
MANIFEST = {
    "ticker": "MSFT",
    "filings": {"10K": {"path": "10k.htm"}, "10Q": {"path": "10q.htm"}, "DEF14A": {"path": "p.htm"}},
    "transcripts": [{"path": "q1.txt"}],
    "peers": ["GOOGL", "AMZN"],
    "missing": [],
}


def _template_payload(agent: str) -> dict:
    """Start from the block the worker's own SKILL.md publishes, so this test
    breaks if a worker template drifts from what the pipeline accepts."""
    skill, prefix = WC.WORKERS[agent]
    raw = WC._FENCE.findall((SKILLS_DIR / skill / "SKILL.md").read_text(encoding="utf-8"))[0]
    for a, b in [
        ("<echo the dispatched depth>", DEPTH),
        ("<echo the dispatched archetype>", ARCHETYPE),
        (f"{prefix}-NN", f"{prefix}-01"),
        ("High|Medium|Low", "High"),
        ("<= 80 chars", f"{prefix} headline finding"),
        ("<item/page/note>", "Item 7, page 41"),
        ("direct quote <= 60 words, or a computed figure with its inputs", "quoted evidence"),
        ("one sentence on what this means for the thesis", "it moves the Base margin path."),
        ("first-hand|second-hand", "first-hand"),
    ]:
        raw = raw.replace(a, b)
    payload = json.loads(raw)
    payload["checklist_coverage"]["items_checked"] = payload["checklist_coverage"]["items_total"]
    return payload


def _reply(payload: dict) -> str:
    return (f"# {payload['worker']}\n\n## Findings\n\nHuman-readable analysis.\n\n"
            f"```findings-json\n{json.dumps(payload, indent=2)}\n```\n")


@pytest.fixture()
def run(tmp_path):
    """Walk Steps 3-4 for real: plan the fan-out, then record every event through
    the state machine. Nothing here hand-writes dispatch-log.json."""
    run_dir = tmp_path / "run"
    (run_dir / "workers").mkdir(parents=True)
    (run_dir / "data-manifest.json").write_text(json.dumps(MANIFEST), encoding="utf-8")
    (run_dir / "financials.json").write_text('{"revenue": {"value": 245122, "tag": "Revenues"}}',
                                             encoding="utf-8")
    (run_dir / "metrics.json").write_text('{"entries": []}', encoding="utf-8")
    (run_dir / "lint.json").write_text('{"fail": [], "warn": []}', encoding="utf-8")

    log = D.plan("MSFT", DEPTH, ARCHETYPE, MANIFEST, ["full"])
    dispatched = [w["worker"] for w in log["workers"] if w["state"] == "PENDING"]
    assert len(dispatched) == 6, dispatched

    payloads = []
    for agent in dispatched:
        payload = _template_payload(agent)
        (run_dir / "workers" / f"{agent}.md").write_text(_reply(payload), encoding="utf-8")
        (run_dir / "workers" / f"{agent}.json").write_text(json.dumps(payload, indent=2),
                                                           encoding="utf-8")
        payloads.append(payload)
        log = D.record(log, agent, "launched")
        log = D.record(log, agent, "returned")
        log = D.record(log, agent, "validated", status=payload["status"], duration=210)

    (run_dir / "dispatch-log.json").write_text(json.dumps(log, indent=2), encoding="utf-8")
    consolidated = WC.consolidate(payloads, cap=RB.FINDING_CAP[DEPTH])
    (run_dir / "consolidated.json").write_text(json.dumps(consolidated, indent=2), encoding="utf-8")
    return run_dir


def _verdict(run_dir: Path, **overrides) -> dict:
    v = {
        "schema_version": "3",
        "ticker": "MSFT", "company_name": "Microsoft Corporation",
        "verdict_date": "2026-08-20", "verdict": "Buy", "conviction": "Medium",
        "current_price": 500.0, "target_base": 600.0, "target_bull": 760.0, "target_bear": 430.0,
        "prob_bull": 0.25, "prob_base": 0.55, "prob_bear": 0.20,
        "weighted_expected_price": 606.0, "weighted_return_36mo": 0.212,
        "bear_to_current_ratio": 0.86, "horizon_months": 36,
        "archetype": ARCHETYPE, "good_company_score": 9, "depth_mode": DEPTH,
        "key_bull_assumptions": ["Azure growth holds above 25%"],
        "key_bear_assumptions": ["AI capex digestion cuts Azure growth to 12%"],
        "invalidation_triggers": ["Sell if Azure growth < 15% for 2 consecutive quarters"],
        "workers_validated": sorted(WC.WORKERS),
        "quorum": "full",
        "dcf": {"wacc": 0.09, "terminal_g": 0.03, "reverse_dcf_implied_growth": 0.14},
        "peer_set": MANIFEST["peers"],
    }
    v.update(overrides)
    return v


def _write_report(run_dir: Path) -> None:
    """Render the Findings section the way report_audit.py parses it. Emitting bare
    IDs was enough for the old substring gate and is no longer enough — which is the
    point of the change."""
    consolidated = json.loads((run_dir / "consolidated.json").read_text(encoding="utf-8"))
    blocks = []
    for f in consolidated["findings"]:
        cit = f.get("citation") or {}
        blocks.append(
            f"### [{f['severity']}] {f['title']}\n\n"
            f"- **ID**: `{f['id']}`\n"
            f"- **Citation**: {cit.get('source', '')} {cit.get('locator', '')}"
            f" ({cit.get('fiscal_period', '')})\n"
            f"- **Evidence**: {f.get('evidence', '')}\n"
            f"- **Implication**: {f.get('implication', '')}\n"
        )
    (run_dir / "report.md").write_text(
        "# MSFT — Investment Analysis\n\n## Worker Findings\n\n" + "\n".join(blocks),
        encoding="utf-8")


def _write_model(run_dir: Path) -> str:
    """Write model.json and return its digest. The digest is mandatory at
    publication, so every publishable fixture needs one."""
    model = json.dumps({"drivers": {"revenue_0": 245122, "op_margin_start": 0.44}}, indent=2)
    (run_dir / "model.json").write_text(model, encoding="utf-8")
    return hashlib.sha256((run_dir / "model.json").read_bytes()).hexdigest()


# --------------------------------------------------------------------------- #
# the documented order, walked in order
# --------------------------------------------------------------------------- #

def test_step3_plan_is_driven_by_the_state_machine(run, capsys):
    log = json.loads((run / "dispatch-log.json").read_text(encoding="utf-8"))
    assert log["depth_mode"] == DEPTH
    assert all(w["state"] == "VALIDATED" for w in log["workers"])
    assert log["quorum"]["verdict_permitted"] == "full"


def test_step4_validates_every_dispatched_reply(run, capsys):
    for agent in WC.WORKERS:
        rc = WC.main([
            "validate", "--reply", str(run / "workers" / f"{agent}.md"),
            "--expect-worker", agent, "--expect-depth", DEPTH, "--expect-archetype", ARCHETYPE,
        ])
        out = json.loads(capsys.readouterr().out)
        assert rc == 0, f"{agent}: {out['errors']}"


def test_step5a_consolidates_the_validated_replies(run, capsys):
    rc = WC.main(["consolidate", "--replies", str(run / "workers" / "*.md"), "--cap", "15"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0, out["invalid_replies"]
    assert len(out["workers_consumed"]) == 6
    assert len(out["findings"]) == 6
    assert {f["reported_by"] for f in out["findings"]} == {p for _, p in WC.WORKERS.values()}
    assert out["archetype_contested"] is False


def test_step5d_ter_evidence_gate_passes_before_any_verdict_exists(run, capsys):
    """The exact defect: this gate runs at 5d-ter, before Step 5f writes a verdict."""
    assert not (run / "verdict.json").exists()
    rc = RB.main(["check", "--run", str(run), "--stage", "evidence"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0, out["errors"]
    assert out["verdict_permitted"] == "full"
    assert out["payloads_consumed"] == 6


def test_publication_gate_rejects_the_pre_verdict_bundle(run, capsys):
    rc = RB.main(["check", "--run", str(run), "--stage", "publication"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert any("verdict.json" in e for e in out["errors"])


def test_step5g_publication_gate_then_log_append(run, tmp_path, capsys):
    digest = _write_model(run)
    (run / "verdict.json").write_text(json.dumps(_verdict(
        run, model={"engine": "finlib.valuation", "model_json_sha256": digest,
                    "grounding": "OK", "anchors_from_financials_json": True}), indent=2),
        encoding="utf-8")
    _write_report(run)

    rc = RB.main(["check", "--run", str(run), "--stage", "publication"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0, out["errors"]

    log = tmp_path / "state" / "verdicts.jsonl"
    assert VL.main(["--log", str(log), "validate", "--entry", str(run / "verdict.json")]) == 0
    capsys.readouterr()
    # Opt-in: the first append needs --init and refuses without it.
    assert VL.main(["--log", str(log), "append", "--entry", str(run / "verdict.json")]) == 1
    capsys.readouterr()
    assert VL.main(["--log", str(log), "append", "--entry", str(run / "verdict.json"), "--init"]) == 0
    capsys.readouterr()

    # Step 5f-bis reads it back on the next run for this ticker.
    prior = VL.read(log, ticker="MSFT", limit=3)
    assert len(prior) == 1 and prior[0]["verdict"] == "Buy"

    # And the entry is calibratable — the property v2's log lacked.
    report = CAL.report(prior, {"MSFT": 800.0}, date(2029, 8, 20))
    assert report["matured_and_scored"] == 1
    assert report["scored"][0]["realised"] == "bull"


def test_model_digest_closes_the_loop_from_model_to_verdict(run, capsys):
    digest = _write_model(run)
    model = (run / "model.json").read_text(encoding="utf-8")
    (run / "verdict.json").write_text(json.dumps(_verdict(
        run, model={"engine": "finlib.valuation", "model_json_sha256": digest,
                    "grounding": "OK", "anchors_from_financials_json": True})), encoding="utf-8")
    _write_report(run)
    rc = RB.main(["check", "--run", str(run), "--stage", "publication"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0, out["errors"]

    # Edit the model after the fact and the digest no longer vouches for the targets.
    (run / "model.json").write_text(model.replace("0.44", "0.55"), encoding="utf-8")
    assert RB.main(["check", "--run", str(run), "--stage", "publication"]) == 1
    assert any("model digest mismatch" in e
               for e in json.loads(capsys.readouterr().out)["errors"])


# --------------------------------------------------------------------------- #
# the failure paths, walked the same way
# --------------------------------------------------------------------------- #

def test_a_worker_that_drops_the_block_fails_loudly_and_is_retryable(run, capsys):
    """The v2 silent failure: this worker's dimension used to just vanish."""
    victim = run / "workers" / "stock-business-reviewer.md"
    victim.write_text("# report\n\nAll good, nothing to flag.\n", encoding="utf-8")

    rc = WC.main(["validate", "--reply", str(victim), "--expect-worker", "stock-business-reviewer"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 1 and out["retryable"] is True

    rc = WC.main(["consolidate", "--replies", str(run / "workers" / "*.md")])
    out = json.loads(capsys.readouterr().out)
    assert rc == 1, "consolidation must not exit 0 with a dimension missing"

    rc = RB.main(["check", "--run", str(run), "--stage", "evidence"])
    gate = json.loads(capsys.readouterr().out)
    assert rc == 1, "the gate must catch a VALIDATED worker whose reply is invalid"
    assert any("fails contract validation" in e for e in gate["errors"])


def test_the_retry_path_leaves_verifiable_evidence(run, capsys):
    """A retry must appear in the log AND leave the failed reply on disk."""
    log = json.loads((run / "dispatch-log.json").read_text(encoding="utf-8"))
    name = "stock-industry-reviewer"

    # Rebuild that worker's history through the machine: it failed once, then passed.
    fresh = D.plan("MSFT", DEPTH, ARCHETYPE, MANIFEST, ["full"])
    fresh = D.record(fresh, name, "launched")
    fresh = D.record(fresh, name, "returned")
    fresh = D.record(fresh, name, "invalid", error_code="MISSING_BLOCK")
    fresh = D.record(fresh, name, "retry", error_code="MISSING_BLOCK")
    fresh = D.record(fresh, name, "returned")
    fresh = D.record(fresh, name, "validated", status="OK", duration=402)
    replacement = next(e for e in fresh["workers"] if e["worker"] == name)
    for i, entry in enumerate(log["workers"]):
        if entry["worker"] == name:
            log["workers"][i] = replacement
    (run / "dispatch-log.json").write_text(json.dumps(log), encoding="utf-8")

    rc = RB.main(["check", "--run", str(run), "--stage", "evidence"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert any("attempt1.md is absent" in e for e in out["errors"])

    (run / "workers" / f"{name}.attempt1.md").write_text(
        "# industry\n\nI forgot the JSON block.\n", encoding="utf-8")
    rc = RB.main(["check", "--run", str(run), "--stage", "evidence"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0, out["errors"]


def test_two_lost_tier0_workers_block_the_verdict_end_to_end(run, capsys):
    log = D.plan("MSFT", DEPTH, ARCHETYPE, MANIFEST, ["full"])
    for name in WC.WORKERS:
        if name in ("stock-business-reviewer", "stock-industry-reviewer"):
            log = D.record(log, name, "launched")
            log = D.record(log, name, "timeout", duration=600)
            log = D.record(log, name, "retry")
            log = D.record(log, name, "timeout", duration=600)
            log = D.record(log, name, "failed")
            (run / "workers" / f"{name}.md").unlink()
            (run / "workers" / f"{name}.json").unlink()
            (run / "workers" / f"{name}.attempt1.md").write_text("x", encoding="utf-8")
        else:
            log = D.record(log, name, "launched")
            log = D.record(log, name, "returned")
            log = D.record(log, name, "validated", status="OK", duration=210)
    (run / "dispatch-log.json").write_text(json.dumps(log), encoding="utf-8")
    assert log["quorum"]["verdict_permitted"] == "none"

    payloads = [_template_payload(a) for a in WC.WORKERS
                if a not in ("stock-business-reviewer", "stock-industry-reviewer")]
    (run / "consolidated.json").write_text(
        json.dumps(WC.consolidate(payloads, cap=RB.FINDING_CAP[DEPTH])), encoding="utf-8")
    digest = _write_model(run)
    (run / "verdict.json").write_text(json.dumps(_verdict(
        run, conviction="Low", quorum="none",
        model={"engine": "finlib.valuation", "model_json_sha256": digest})), encoding="utf-8")
    _write_report(run)

    rc = RB.main(["check", "--run", str(run), "--stage", "publication"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert out["verdict_permitted"] == "none"
    assert any("quorum forbids a verdict" in e for e in out["errors"])


def test_a_contested_archetype_is_surfaced_by_consolidation(run, capsys):
    challenge = {
        "proposed": "Capital-Intensive Industrial / Infrastructure / Utility",
        "reason": "capex/revenue 31% TTM and 28% on a 3-yr average; gross margin 21%",
        "evidence": {"source": "financials.json", "locator": "capex, revenue",
                     "fiscal_period": "TTM 2026-06-30"},
    }
    for agent in ("stock-earnings-quality-reviewer", "stock-balance-sheet-reviewer"):
        payload = _template_payload(agent)
        payload["archetype_challenge"] = dict(challenge)
        (run / "workers" / f"{agent}.md").write_text(_reply(payload), encoding="utf-8")
        (run / "workers" / f"{agent}.json").write_text(json.dumps(payload, indent=2),
                                                       encoding="utf-8")

    rc = WC.main(["consolidate", "--replies", str(run / "workers" / "*.md")])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["archetype_contested"] is True
    assert len(out["archetype_challenges"]) == 2


def test_lite_run_is_a_smaller_fan_out_end_to_end(tmp_path):
    """Lite must cost less in practice, not just in the docs."""
    bare = {"ticker": "XYZ", "filings": {"10K": {"path": "x"}}, "peers": [], "missing": []}
    lite = D.plan("XYZ", "Lite", "Hyperscaler", bare, ["specific"])
    standard = D.plan("XYZ", "Standard", "Hyperscaler", bare, ["specific"])
    lite_n = sum(1 for w in lite["workers"] if w["state"] == "PENDING")
    std_n = sum(1 for w in standard["workers"] if w["state"] == "PENDING")
    assert lite_n == 4 and std_n == 6


# --------------------------------------------------------------------------- #
# the documented commands must be the real commands
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("module,argv", [
    (WC, ["validate", "--reply", "X", "--expect-worker", "Y", "--expect-depth", "Z",
          "--expect-archetype", "A", "--require-checks", "B"]),
    (WC, ["consolidate", "--replies", "X", "--cap", "15"]),
    (RB, ["check", "--run", "X", "--stage", "evidence"]),
    (RB, ["check", "--run", "X", "--stage", "publication"]),
    (D, ["plan", "--log", "X", "--ticker", "MSFT", "--depth", "Standard",
         "--archetype", "A", "--manifest", "X", "--question-shape", "valuation,moat"]),
    (D, ["record", "--log", "X", "--worker", "stock-business-reviewer", "--event", "launched"]),
    (D, ["record", "--log", "X", "--worker", "stock-business-reviewer", "--event", "validated",
         "--status", "OK", "--duration", "210"]),
    (D, ["record", "--log", "X", "--worker", "stock-industry-reviewer", "--event", "dispatched",
         "--wave", "2", "--reason", "conflict"]),
    (D, ["quorum", "--log", "X"]),
    (VL, ["path"]),
    (VL, ["init"]),
    (VL, ["read", "--ticker", "MSFT", "--limit", "3"]),
    (VL, ["validate", "--entry", "X"]),
    (VL, ["append", "--entry", "X", "--init"]),
    (VL, ["migrate", "--entry", "X"]),
    (CAL, ["report", "--prices", "X", "--as-of", "2026-08-20"]),
])
def test_every_documented_flag_is_accepted_by_its_parser(module, argv, tmp_path, capsys):
    """argparse exits 2 on an unknown flag or subcommand, so reaching any other
    outcome proves the argv was accepted. File args point at an absent path on
    purpose: getting as far as the I/O layer is itself the proof."""
    argv = [str(tmp_path / "absent") if a == "X" else a for a in argv]
    try:
        module.main(argv)
    except SystemExit as exc:
        assert exc.code != 2, f"{module.__name__} rejected documented argv: {argv}"
    except OSError:
        pass
    finally:
        capsys.readouterr()


def test_skill_md_commands_name_only_real_scripts():
    text = SKILL_MD.read_text(encoding="utf-8")
    referenced = set(re.findall(r"scripts/finlib/(\w+\.py)", text))
    assert referenced, "SKILL.md references no finlib scripts — wiring lost"
    for name in sorted(referenced):
        assert (LEAD_ROOT / "scripts" / "finlib" / name).exists(), (
            f"SKILL.md invokes scripts/finlib/{name}, which does not exist"
        )


def test_skill_md_subcommands_exist_in_their_tools():
    """Guard the pairing, not just the filename."""
    text = SKILL_MD.read_text(encoding="utf-8")
    known = {
        "worker_contract.py": {"validate", "consolidate"},
        "runbundle.py": {"check"},
        "dispatch.py": {"plan", "record", "quorum"},
        "verdictlog.py": {"path", "init", "append", "read", "validate", "migrate"},
        "calibration.py": {"report"},
        "verdict_diff.py": set(),
        "lint.py": set(),
        "edgar.py": {"fetch", "parse"},
        "valuation.py": {"run"},
        "sotp.py": {"run"},
        "crosssection.py": set(),
    }
    for script, sub in re.findall(r"scripts/finlib/(\w+\.py)\s+\\?\s*\n?\s*([a-z_]+)?", text):
        if not sub or script not in known or not known[script]:
            continue
        assert sub in known[script], f"SKILL.md calls `{script} {sub}`, which is not a subcommand"


def test_skill_md_never_uses_a_removed_flag():
    """``--require-verdict`` was the ordering bug: it forced a pre-verdict gate to
    demand an artifact that did not exist yet. It must not come back."""
    text = SKILL_MD.read_text(encoding="utf-8")
    assert "--require-verdict" not in text
    for stage in RB.STAGES:
        assert f"--stage {stage}" in text, f"SKILL.md never invokes the {stage} stage"


def test_skill_md_runs_the_evidence_gate_before_the_publication_gate():
    text = SKILL_MD.read_text(encoding="utf-8")
    assert text.index("--stage evidence") < text.index("--stage publication"), (
        "the pre-verdict gate must be documented before the publication gate"
    )
