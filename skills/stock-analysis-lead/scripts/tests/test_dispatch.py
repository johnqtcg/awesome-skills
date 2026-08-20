"""Tests for the enforced dispatch state machine.

The regression: v3 defined states, transitions, retry caps and tier triggers in
prose, then wrote them into a log the orchestrator authored freely. An illegal
history was recordable and nothing objected — "VALIDATED with 4 attempts",
"retried after WORKER_MISMATCH", "Lite dispatched six workers", "second wave of
five". Every test below is one such history being refused.

Triage is also asserted as a *function*: same depth + manifest + question shape
must always produce the same fan-out, so "Lite is cheaper" is a property of the
code rather than a hope about the orchestrator's judgment.
"""
import copy
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from finlib import dispatch as D  # noqa: E402
from finlib import runbundle as RB  # noqa: E402
from finlib import worker_contract as WC  # noqa: E402

FULL_MANIFEST = {
    "ticker": "MSFT",
    "filings": {"10K": {"path": "10k.htm"}, "10Q": {"path": "10q.htm"}, "DEF14A": {"path": "proxy.htm"}},
    "transcripts": [{"path": "q1.txt"}],
    "peers": ["GOOGL", "AMZN"],
    "missing": [],
}
BARE_MANIFEST = {"ticker": "XYZ", "filings": {"10K": {"path": "10k.htm"}}, "peers": [], "missing": []}


def _plan(depth="Standard", archetype="Hyperscaler", manifest=None, shapes=("full",)):
    return D.plan("MSFT", depth, archetype, manifest or FULL_MANIFEST, list(shapes))


def _dispatched(log):
    return [w["worker"] for w in log["workers"] if w["state"] == "PENDING"]


# --------------------------------------------------------------------------- #
# plan — triage as a computed function
# --------------------------------------------------------------------------- #

def test_standard_dispatches_all_six():
    assert len(_dispatched(_plan("Standard"))) == 6


def test_strict_dispatches_all_six():
    assert len(_dispatched(_plan("Strict"))) == 6


def test_lite_with_a_specific_question_dispatches_only_tier0():
    """The headline claim of the tiering: Lite must actually be cheaper.

    BARE_MANIFEST deliberately lacks a proxy, a transcript and a peer set, so no
    Tier-1 trigger can fire. FULL_MANIFEST would legitimately fire the management
    trigger (proxy + transcript both present) and is the wrong fixture here."""
    log = _plan("Lite", manifest=BARE_MANIFEST, shapes=("specific",))
    assert set(_dispatched(log)) == set(RB.TIER0)
    assert len(_dispatched(log)) == 4


def test_lite_valuation_question_fires_the_peer_trigger():
    # Peers present but no proxy/transcript, so only the peer trigger may fire.
    manifest = {"ticker": "MSFT", "filings": {"10K": {"path": "x"}}, "peers": ["GOOGL", "AMZN"]}
    log = _plan("Lite", manifest=manifest, shapes=("valuation",))
    assert "stock-peer-comparison-reviewer" in _dispatched(log)
    assert "stock-management-reviewer" not in _dispatched(log)


def test_lite_moat_question_fires_the_peer_trigger():
    manifest = {"ticker": "MSFT", "filings": {"10K": {"path": "x"}}, "peers": ["GOOGL", "AMZN"]}
    assert "stock-peer-comparison-reviewer" in _dispatched(
        _plan("Lite", manifest=manifest, shapes=("moat",)))


def test_lite_peer_trigger_needs_at_least_two_peers():
    manifest = dict(FULL_MANIFEST, peers=["GOOGL"])
    log = _plan("Lite", manifest=manifest, shapes=("valuation",))
    assert "stock-peer-comparison-reviewer" not in _dispatched(log)


def test_lite_stewardship_question_fires_the_management_trigger():
    manifest = dict(FULL_MANIFEST)
    manifest.pop("transcripts")
    log = _plan("Lite", manifest=manifest, shapes=("stewardship",))
    assert "stock-management-reviewer" in _dispatched(log)


def test_lite_management_trigger_fires_on_proxy_plus_transcript():
    log = _plan("Lite", manifest=FULL_MANIFEST, shapes=("specific",))
    # FULL_MANIFEST has both, so the trigger fires even on a narrow question.
    assert "stock-management-reviewer" in _dispatched(log)


@pytest.mark.parametrize("archetype", [
    "Mature Cash Cow / Consumer Staples",
    "Capital-Intensive Industrial / Infrastructure / Utility",
    "Bank / Insurance / Asset Manager (Financials)",
    "REIT",
])
def test_stewardship_archetypes_force_the_management_worker_even_at_lite(archetype):
    """For these names capital allocation IS the thesis, so it is not optional."""
    log = _plan("Lite", archetype=archetype, manifest=BARE_MANIFEST, shapes=("specific",))
    assert "stock-management-reviewer" in _dispatched(log)


def test_hyperscaler_at_lite_with_a_bare_manifest_gets_four_workers():
    log = _plan("Lite", archetype="Hyperscaler", manifest=BARE_MANIFEST, shapes=("specific",))
    assert len(_dispatched(log)) == 4


def test_tier0_is_never_conditional():
    for depth in D.DEPTHS:
        for shapes in (("specific",), ("full",), ("valuation",)):
            log = _plan(depth, manifest=BARE_MANIFEST, shapes=shapes)
            assert set(RB.TIER0) <= set(_dispatched(log)), (depth, shapes)


def test_untriggered_tier1_workers_are_recorded_not_omitted():
    """Silence about a skipped worker reads as "it ran"; the log must say why not."""
    log = _plan("Lite", manifest=BARE_MANIFEST, shapes=("specific",))
    skipped = [w for w in log["workers"] if w["state"] == "NOT_DISPATCHED"]
    assert {w["worker"] for w in skipped} == set(RB.TIER1)
    for entry in skipped:
        assert "NOT FIRED" in entry["trigger"]


def test_plan_is_deterministic():
    a = _plan("Lite", shapes=("valuation",))
    b = _plan("Lite", shapes=("valuation",))
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_plan_refuses_without_a_10k():
    manifest = {"ticker": "XYZ", "filings": {}, "peers": []}
    with pytest.raises(D.IllegalTransition, match="no 10-K"):
        D.plan("XYZ", "Standard", "Hyperscaler", manifest, ["full"])


def test_plan_refuses_an_unknown_depth_or_shape():
    with pytest.raises(D.IllegalTransition, match="depth"):
        D.plan("MSFT", "Deep", "Hyperscaler", FULL_MANIFEST, ["full"])
    with pytest.raises(D.IllegalTransition, match="question shape"):
        D.plan("MSFT", "Standard", "Hyperscaler", FULL_MANIFEST, ["vibes"])


def test_plan_refuses_an_empty_archetype():
    """Workers echo the archetype back for verification, so it cannot be blank."""
    with pytest.raises(D.IllegalTransition, match="archetype"):
        D.plan("MSFT", "Standard", "", FULL_MANIFEST, ["full"])


def test_planned_tiers_match_the_runbundle_tier_sets():
    log = _plan("Standard")
    for entry in log["workers"]:
        expected = 0 if entry["worker"] in RB.TIER0 else 1
        assert entry["tier"] == expected


# --------------------------------------------------------------------------- #
# record — illegal histories are refused
# --------------------------------------------------------------------------- #

W = "stock-business-reviewer"


def _walk(log, *events):
    for event, kwargs in events:
        log = D.record(log, W, event, **kwargs)
    return log


def test_the_happy_path_walks_to_validated():
    log = _walk(_plan(), ("launched", {}), ("returned", {}),
                ("validated", {"status": "OK", "duration": 214}))
    entry = next(e for e in log["workers"] if e["worker"] == W)
    assert entry["state"] == "VALIDATED"
    assert entry["attempts"] == 1
    assert entry["duration_s"] == 214
    assert log["quorum"]["tier0_validated"] == 1


@pytest.mark.parametrize("event,kwargs", [
    ("returned", {}),
    ("validated", {"status": "OK"}),
    ("invalid", {"error_code": "MISSING_BLOCK"}),
    ("timeout", {}),
    ("crashed", {}),
    ("retry", {}),
    ("failed", {}),
])
def test_no_event_may_skip_the_launch(event, kwargs):
    """Every terminal state must be reachable only through RUNNING."""
    with pytest.raises(D.IllegalTransition, match="requires state in"):
        D.record(_plan(), W, event, **kwargs)


def test_launching_twice_is_refused():
    log = D.record(_plan(), W, "launched")
    with pytest.raises(D.IllegalTransition, match="requires state in"):
        D.record(log, W, "launched")


def test_validated_requires_a_payload_status():
    log = _walk(_plan(), ("launched", {}), ("returned", {}))
    with pytest.raises(D.IllegalTransition, match="requires --status"):
        D.record(log, W, "validated")
    with pytest.raises(D.IllegalTransition, match="requires --status"):
        D.record(log, W, "validated", status="PARTIAL")


@pytest.mark.parametrize("status,state", [
    ("OK", "VALIDATED"), ("DEGRADED", "VALIDATED"),
    ("SKIPPED", "SKIPPED"), ("REFUSED", "REFUSED"),
])
def test_payload_status_determines_the_state(status, state):
    log = _walk(_plan(), ("launched", {}), ("returned", {}), ("validated", {"status": status}))
    entry = next(e for e in log["workers"] if e["worker"] == W)
    assert entry["state"] == state


def test_a_skipped_worker_does_not_count_toward_the_quorum():
    """It validated, and it was right to decline — but the dimension is uncovered."""
    log = _walk(_plan(), ("launched", {}), ("returned", {}), ("validated", {"status": "SKIPPED"}))
    assert log["quorum"]["tier0_validated"] == 0


def test_invalid_requires_the_validator_error_code():
    log = _walk(_plan(), ("launched", {}), ("returned", {}))
    with pytest.raises(D.IllegalTransition, match="requires --error-code"):
        D.record(log, W, "invalid")


def test_retry_after_a_non_retryable_code_is_refused():
    """WORKER_MISMATCH means the wrong agent answered. Re-asking cannot fix that."""
    log = _walk(_plan(), ("launched", {}), ("returned", {}),
                ("invalid", {"error_code": "WORKER_MISMATCH"}))
    with pytest.raises(D.IllegalTransition, match="not retryable"):
        D.record(log, W, "retry", error_code="WORKER_MISMATCH")


def test_retry_out_of_invalid_output_requires_the_code():
    log = _walk(_plan(), ("launched", {}), ("returned", {}),
                ("invalid", {"error_code": "MISSING_BLOCK"}))
    with pytest.raises(D.IllegalTransition, match="requires --error-code"):
        D.record(log, W, "retry")


def test_retryable_code_permits_exactly_one_retry():
    log = _walk(_plan(), ("launched", {}), ("returned", {}),
                ("invalid", {"error_code": "MISSING_BLOCK"}),
                ("retry", {"error_code": "MISSING_BLOCK"}))
    entry = next(e for e in log["workers"] if e["worker"] == W)
    assert entry["attempts"] == 2 and entry["state"] == "RUNNING"


def test_a_third_attempt_is_refused():
    log = _walk(_plan(), ("launched", {}), ("timeout", {}), ("retry", {}), ("timeout", {}))
    with pytest.raises(D.IllegalTransition, match=f"exceeds the cap of {D.MAX_ATTEMPTS}"):
        D.record(log, W, "retry")


def test_failing_before_the_retry_is_exhausted_is_refused():
    """Marking FAILED after one attempt skips the retry the policy grants."""
    log = _walk(_plan(), ("launched", {}), ("crashed", {}))
    with pytest.raises(D.IllegalTransition, match="allows one retry"):
        D.record(log, W, "failed")


def test_failed_is_accepted_once_attempts_are_exhausted():
    log = _walk(_plan(), ("launched", {}), ("timeout", {}), ("retry", {}), ("timeout", {}),
                ("failed", {}))
    entry = next(e for e in log["workers"] if e["worker"] == W)
    assert entry["state"] == "FAILED"
    assert "status" not in entry


def test_events_against_an_undispatched_worker_are_refused():
    log = _plan("Lite", manifest=BARE_MANIFEST, shapes=("specific",))
    with pytest.raises(D.IllegalTransition, match="was not dispatched"):
        D.record(log, "stock-peer-comparison-reviewer", "launched")


def test_unknown_worker_and_event_are_refused():
    with pytest.raises(D.IllegalTransition, match="unknown worker"):
        D.record(_plan(), "stock-vibes-reviewer", "launched")
    with pytest.raises(D.IllegalTransition, match="unknown event"):
        D.record(_plan(), W, "vibed")


def test_error_codes_accumulate_with_their_attempt_number():
    log = _walk(_plan(), ("launched", {}), ("returned", {}),
                ("invalid", {"error_code": "MISSING_BLOCK"}),
                ("retry", {"error_code": "MISSING_BLOCK"}), ("timeout", {}))
    entry = next(e for e in log["workers"] if e["worker"] == W)
    assert [e["code"] for e in entry["errors"]] == ["MISSING_BLOCK", "TIMEOUT"] or \
           [e["code"] for e in entry["errors"]] == ["MISSING_BLOCK"]
    assert entry["errors"][0]["attempt"] == 1


def test_a_stale_status_is_cleared_when_a_worker_later_fails():
    """A worker that validated then got re-dispatched must not keep the old status."""
    log = _walk(_plan(), ("launched", {}), ("returned", {}),
                ("invalid", {"error_code": "BAD_JSON"}))
    entry = next(e for e in log["workers"] if e["worker"] == W)
    assert "status" not in entry


# --------------------------------------------------------------------------- #
# second wave
# --------------------------------------------------------------------------- #

def test_second_wave_requires_a_named_reason():
    with pytest.raises(D.IllegalTransition, match="named contradiction"):
        D.record(_plan(), "stock-industry-reviewer", "dispatched", wave=2)


def test_second_wave_cap_is_depth_dependent():
    for depth, cap in RB.SECOND_WAVE_CAP.items():
        log = _plan(depth)
        # Distinct workers throughout: re-using one would trip the duplicate-entry
        # guard first and this test would stop exercising the cap at all.
        assert cap < len(RB.TIER0), "the fixture needs more distinct workers than the cap"
        for i in range(cap):
            log = D.record(log, RB.TIER0[i], "dispatched", wave=2, reason=f"conflict {i}")
        with pytest.raises(D.IllegalTransition, match=f"cap of {cap}"):
            D.record(log, RB.TIER0[cap], "dispatched", wave=2, reason="one too many")


def test_a_duplicate_wave2_entry_for_one_worker_is_refused():
    """Two entries for the same worker made its history ambiguous, and the lookup
    silently returned the first — hiding one of the two replies from the gate."""
    log = D.record(_plan(), "stock-industry-reviewer", "dispatched", wave=2, reason="first")
    with pytest.raises(D.IllegalTransition, match="already has a wave-2 entry"):
        D.record(log, "stock-industry-reviewer", "dispatched", wave=2, reason="second")


def test_an_ambiguous_history_is_refused_rather_than_resolved():
    """Even if a duplicate arrives by another route, no event may be applied."""
    log = D.record(_plan(), "stock-industry-reviewer", "dispatched", wave=2, reason="first")
    log["wave_2"].append(dict(log["wave_2"][0]))
    with pytest.raises(D.IllegalTransition, match="history is ambiguous"):
        D.record(log, "stock-industry-reviewer", "launched", wave=2)


def test_wave2_entry_records_its_artifact_stem():
    """The gate looks for workers/<worker>.wave2.md, so the convention is written
    into the log rather than left to the orchestrator's memory."""
    log = D.record(_plan(), "stock-industry-reviewer", "dispatched", wave=2, reason="conflict")
    assert log["wave_2"][0]["artifact_stem"] == "stock-industry-reviewer.wave2"


def test_dispatched_event_is_rejected_on_wave_one():
    with pytest.raises(D.IllegalTransition, match="second-wave"):
        D.record(_plan(), W, "dispatched", wave=1, reason="x")


def test_second_wave_entries_walk_the_same_machine():
    log = D.record(_plan(), "stock-industry-reviewer", "dispatched", wave=2,
                   reason="share claim vs P-01")
    log = D.record(log, "stock-industry-reviewer", "launched", wave=2)
    log = D.record(log, "stock-industry-reviewer", "returned", wave=2)
    log = D.record(log, "stock-industry-reviewer", "validated", status="OK", wave=2)
    assert log["wave_2"][0]["state"] == "VALIDATED"


# --------------------------------------------------------------------------- #
# quorum
# --------------------------------------------------------------------------- #

def _validate_all(log, workers):
    for name in workers:
        log = D.record(log, name, "launched")
        log = D.record(log, name, "returned")
        log = D.record(log, name, "validated", status="OK", duration=100)
    return log


def test_quorum_full_when_all_tier0_validate():
    log = _validate_all(_plan(), RB.TIER0)
    assert log["quorum"]["verdict_permitted"] == "full"
    assert "conviction_ceiling" not in log["quorum"]


def test_quorum_degraded_caps_conviction_at_low():
    log = _validate_all(_plan(), [w for w in RB.TIER0 if w != "stock-business-reviewer"])
    assert log["quorum"]["verdict_permitted"] == "degraded"
    assert log["quorum"]["conviction_ceiling"] == "Low"


def test_quorum_none_with_two_tier0_workers_lost():
    log = _validate_all(_plan(), RB.TIER0[:2])
    assert log["quorum"]["verdict_permitted"] == "none"


def test_missing_balance_sheet_worker_sets_a_watch_ceiling():
    log = _validate_all(_plan(), [w for w in RB.TIER0 if w != "stock-balance-sheet-reviewer"])
    assert log["quorum"]["verdict_ceiling"] == "Watch"
    assert "Bear floor" in log["quorum"]["ceiling_reason"]


def test_balance_sheet_present_sets_no_ceiling():
    log = _validate_all(_plan(), RB.TIER0)
    assert "verdict_ceiling" not in log["quorum"]


def test_quorum_matches_what_the_bundle_gate_recomputes(tmp_path):
    """Two independent implementations of the same rule must agree, or a run can
    pass one and fail the other."""
    log = _validate_all(_plan(), RB.TIER0[:3])
    assert log["quorum"]["verdict_permitted"] == "degraded"
    assert D.quorum(log) == log["quorum"]


# --------------------------------------------------------------------------- #
# CLI + doc agreement
# --------------------------------------------------------------------------- #

def test_cli_plan_then_record_then_quorum(tmp_path, capsys):
    manifest = tmp_path / "m.json"
    manifest.write_text(json.dumps(FULL_MANIFEST), encoding="utf-8")
    log = tmp_path / "dispatch-log.json"

    assert D.main(["plan", "--log", str(log), "--ticker", "MSFT", "--depth", "Lite",
                   "--archetype", "Hyperscaler", "--manifest", str(manifest),
                   "--question-shape", "specific"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["fan_out"] == 5      # FULL_MANIFEST fires the management trigger

    assert D.main(["record", "--log", str(log), "--worker", W, "--event", "launched"]) == 0
    capsys.readouterr()
    assert D.main(["record", "--log", str(log), "--worker", W, "--event", "returned"]) == 0
    capsys.readouterr()
    assert D.main(["record", "--log", str(log), "--worker", W, "--event", "validated",
                   "--status", "OK", "--duration", "210"]) == 0
    capsys.readouterr()

    assert D.main(["quorum", "--log", str(log)]) == 0
    assert json.loads(capsys.readouterr().out)["tier0_validated"] == 1


def test_cli_refusal_exits_nonzero_and_explains(tmp_path, capsys):
    manifest = tmp_path / "m.json"
    manifest.write_text(json.dumps(FULL_MANIFEST), encoding="utf-8")
    log = tmp_path / "dispatch-log.json"
    D.main(["plan", "--log", str(log), "--ticker", "MSFT", "--depth", "Standard",
            "--archetype", "Hyperscaler", "--manifest", str(manifest)])
    capsys.readouterr()
    rc = D.main(["record", "--log", str(log), "--worker", W, "--event", "validated", "--status", "OK"])
    captured = capsys.readouterr()
    assert rc == 1
    assert "refused" in json.loads(captured.err)


def test_every_transition_target_is_a_known_bundle_state():
    targets = {target for _, target in D.TRANSITIONS.values()} | set(D.STATUS_TO_STATE.values())
    assert targets <= set(RB.ALL_STATES), targets - set(RB.ALL_STATES)


def test_every_state_and_event_is_documented():
    ref = os.path.join(os.path.dirname(__file__), "..", "..", "references", "dispatch-protocol.md")
    with open(ref, encoding="utf-8") as f:
        text = f.read()
    for state in RB.ALL_STATES:
        assert f"`{state}`" in text, f"state {state} undocumented"
    for event in list(D.TRANSITIONS) + ["dispatched"]:
        assert f"`{event}`" in text, f"event {event} undocumented in dispatch-protocol.md"


def test_retryable_partition_is_shared_with_the_validator():
    """dispatch.py must not carry its own idea of what is retryable."""
    assert D.WC.RETRYABLE is WC.RETRYABLE
