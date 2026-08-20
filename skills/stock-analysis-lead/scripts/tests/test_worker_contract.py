"""Tests for the Worker Findings Contract v1 validator.

The regression these encode: before the contract existed, a worker that dropped a
field, emitted malformed JSON, cited nothing, or answered for the wrong dispatch
failed *silently* — its dimension simply vanished from the report while the
verdict was still published as if six workers had been consumed. Every test below
asserts a specific way that silence is now a loud, coded failure.
"""
import copy
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from finlib import worker_contract as WC  # noqa: E402

GOOD_PAYLOAD = {
    "contract_version": "1",
    "worker": "stock-business-reviewer",
    "prefix": "BUS",
    "status": "OK",
    "depth_mode": "Standard",
    "archetype_applied": "Hyperscaler / Mega-Cap Tech Platform",
    "archetype_challenge": None,
    "findings": [
        {
            "id": "BUS-02",
            "severity": "High",
            "title": "Top customer at 22% of revenue",
            "citation": {"source": "10-K", "locator": "Item 1A, page 23", "fiscal_period": "FY2025"},
            "evidence": "One customer accounted for 22% of consolidated revenue in FY2025",
            "implication": "Revenue is hostage to a single renewal decision.",
            "confidence": "first-hand",
        }
    ],
    "positives": [],
    "data_gaps": [],
    "checklist_coverage": {"items_total": 11, "items_checked": 9, "items_not_found": 2, "ids_not_checked": []},
    "mandatory_checks_run": ["BUS-11"],
}


def wrap(payload) -> str:
    """Render a payload the way a worker reply carries it."""
    body = payload if isinstance(payload, str) else json.dumps(payload, indent=2)
    return f"# Report\n\nSome prose.\n\n```findings-json\n{body}\n```\n"


def codes(errs) -> set[str]:
    return {e.code for e in errs}


# --------------------------------------------------------------------------- #
# transport
# --------------------------------------------------------------------------- #

def test_happy_path_passes():
    payload, errs = WC.validate_reply(wrap(GOOD_PAYLOAD))
    assert errs == [], [e.as_dict() for e in errs]
    assert payload["worker"] == "stock-business-reviewer"


def test_missing_block_is_caught():
    _, errs = WC.validate_reply("no fence at all, just prose about the business")
    assert codes(errs) == {"MISSING_BLOCK"}


def test_multiple_blocks_refuses_to_guess():
    reply = wrap(GOOD_PAYLOAD) + wrap(GOOD_PAYLOAD)
    _, errs = WC.validate_reply(reply)
    assert codes(errs) == {"MULTIPLE_BLOCKS"}


def test_malformed_json_is_caught():
    _, errs = WC.validate_reply(wrap('{"contract_version": "1", oops}'))
    assert codes(errs) == {"BAD_JSON"}


def test_prose_inside_the_fence_is_caught():
    """A worker that appends a closing sentence inside the fence must fail —
    silently ignoring trailing text is how partial payloads got consumed."""
    _, errs = WC.validate_reply(wrap(json.dumps(GOOD_PAYLOAD) + "\nThat concludes my review."))
    assert codes(errs) == {"BAD_JSON"}


def test_non_object_payload_is_caught():
    _, errs = WC.validate_reply(wrap("[1, 2, 3]"))
    assert codes(errs) == {"BAD_TYPE"}


def test_fence_extraction_tolerates_indentation():
    reply = "text\n\n  ```findings-json\n" + json.dumps(GOOD_PAYLOAD) + "\n  ```\n"
    payload, errs = WC.validate_reply(reply)
    assert errs == []
    assert payload["prefix"] == "BUS"


# --------------------------------------------------------------------------- #
# version gating
# --------------------------------------------------------------------------- #

def test_unknown_version_refuses_rather_than_best_effort():
    p = copy.deepcopy(GOOD_PAYLOAD)
    p["contract_version"] = "99"
    errs = WC.validate(p)
    # Only the version error: the field layout of a foreign version is not
    # guaranteed, so field-level complaints would be noise.
    assert codes(errs) == {"BAD_VERSION"}
    assert len(errs) == 1


def test_absent_version_is_caught():
    p = copy.deepcopy(GOOD_PAYLOAD)
    del p["contract_version"]
    assert codes(WC.validate(p)) == {"BAD_VERSION"}


# --------------------------------------------------------------------------- #
# required fields
# --------------------------------------------------------------------------- #

def test_every_required_field_is_individually_enforced():
    """Guard against a validator that only checks the fields a sample happens to
    omit. Each required key, dropped alone, must produce MISSING_FIELD."""
    required = (
        "worker", "prefix", "status", "depth_mode", "archetype_applied",
        "archetype_challenge", "findings", "positives", "data_gaps",
        "checklist_coverage", "mandatory_checks_run",
    )
    for field in required:
        p = copy.deepcopy(GOOD_PAYLOAD)
        del p[field]
        assert "MISSING_FIELD" in codes(WC.validate(p)), f"dropping {field} was not caught"


def test_empty_findings_is_a_valid_result():
    """A structurally clean company is a real answer, not a failure — the skill
    explicitly forbids fabricating findings to look thorough."""
    p = copy.deepcopy(GOOD_PAYLOAD)
    p["findings"] = []
    assert WC.validate(p) == []


def test_non_ok_status_requires_a_reason():
    for status in ("DEGRADED", "SKIPPED", "REFUSED"):
        p = copy.deepcopy(GOOD_PAYLOAD)
        p["status"] = status
        assert "MISSING_FIELD" in codes(WC.validate(p)), f"{status} without reason passed"
        p["status_reason"] = "10-Q absent from manifest"
        assert WC.validate(p) == [], f"{status} with reason failed"


def test_blank_status_reason_does_not_satisfy_the_requirement():
    p = copy.deepcopy(GOOD_PAYLOAD)
    p["status"] = "DEGRADED"
    p["status_reason"] = "   "
    assert "MISSING_FIELD" in codes(WC.validate(p))


def test_bad_status_is_caught():
    p = copy.deepcopy(GOOD_PAYLOAD)
    p["status"] = "PARTIAL"
    assert "BAD_STATUS" in codes(WC.validate(p))


def test_array_fields_reject_scalars():
    for field in ("findings", "positives", "data_gaps", "mandatory_checks_run"):
        p = copy.deepcopy(GOOD_PAYLOAD)
        p[field] = "not an array"
        assert "BAD_TYPE" in codes(WC.validate(p)), f"{field} accepted a string"


# --------------------------------------------------------------------------- #
# findings
# --------------------------------------------------------------------------- #

def test_each_finding_field_is_required():
    for field in ("id", "severity", "title", "citation", "evidence", "implication", "confidence"):
        p = copy.deepcopy(GOOD_PAYLOAD)
        del p["findings"][0][field]
        assert "MISSING_FIELD" in codes(WC.validate(p)), f"finding without {field} passed"


def test_bad_severity_is_caught():
    p = copy.deepcopy(GOOD_PAYLOAD)
    p["findings"][0]["severity"] = "Critical"
    assert "BAD_SEVERITY" in codes(WC.validate(p))


def test_finding_id_prefix_must_match_the_payload_prefix():
    p = copy.deepcopy(GOOD_PAYLOAD)
    p["findings"][0]["id"] = "EQ-02"
    assert "BAD_PREFIX" in codes(WC.validate(p))


def test_prefix_match_is_whole_segment_not_substring():
    """``P`` must not absorb ``P-01``-lookalikes from other workers, and ``BUS``
    must not be satisfied by ``BUSX``."""
    p = copy.deepcopy(GOOD_PAYLOAD)
    p["prefix"] = "P"
    p["worker"] = "stock-peer-comparison-reviewer"
    p["findings"][0]["id"] = "P-01"
    assert WC.validate(p) == []
    p["findings"][0]["id"] = "PX-01"
    assert "BAD_PREFIX" in codes(WC.validate(p))


def test_unknown_payload_prefix_is_caught():
    p = copy.deepcopy(GOOD_PAYLOAD)
    p["prefix"] = "ZZZ"
    assert "BAD_PREFIX" in codes(WC.validate(p))


def test_blank_evidence_does_not_pass_as_present():
    p = copy.deepcopy(GOOD_PAYLOAD)
    p["findings"][0]["evidence"] = ""
    assert "BAD_TYPE" in codes(WC.validate(p))


# --------------------------------------------------------------------------- #
# citations — the mechanism that makes the first-hand rule checkable
# --------------------------------------------------------------------------- #

def test_bare_string_citation_is_rejected():
    """v2 accepted "10-K Item 1, page 7" as a citation, which cannot be checked
    for period or source tier. The object form is mandatory."""
    p = copy.deepcopy(GOOD_PAYLOAD)
    p["findings"][0]["citation"] = "10-K Item 1, page 7"
    assert "BAD_CITATION" in codes(WC.validate(p))


def test_empty_locator_is_rejected():
    p = copy.deepcopy(GOOD_PAYLOAD)
    p["findings"][0]["citation"]["locator"] = "  "
    assert "BAD_CITATION" in codes(WC.validate(p))


def test_missing_fiscal_period_is_rejected():
    p = copy.deepcopy(GOOD_PAYLOAD)
    del p["findings"][0]["citation"]["fiscal_period"]
    assert "BAD_CITATION" in codes(WC.validate(p))


def test_unknown_citation_source_is_rejected():
    p = copy.deepcopy(GOOD_PAYLOAD)
    p["findings"][0]["citation"]["source"] = "seeking-alpha-comment"
    assert "BAD_CITATION" in codes(WC.validate(p))


def test_aggregator_source_cannot_claim_first_hand():
    """The first-hand data rule is only real if the pair is enforced."""
    p = copy.deepcopy(GOOD_PAYLOAD)
    p["findings"][0]["citation"]["source"] = "aggregator"
    assert "CONFIDENCE_MISMATCH" in codes(WC.validate(p))
    p["findings"][0]["confidence"] = "second-hand"
    assert WC.validate(p) == []


def test_positives_citations_are_validated_too():
    p = copy.deepcopy(GOOD_PAYLOAD)
    p["positives"] = [{"id": "BUS-02", "statement": "no concentration", "citation": "Item 1A"}]
    assert "BAD_CITATION" in codes(WC.validate(p))


# --------------------------------------------------------------------------- #
# coverage — "the checklist ran to completion" must be checkable
# --------------------------------------------------------------------------- #

def test_incomplete_coverage_is_caught():
    p = copy.deepcopy(GOOD_PAYLOAD)
    p["checklist_coverage"] = {"items_total": 11, "items_checked": 3, "items_not_found": 1, "ids_not_checked": []}
    assert "COVERAGE_INCOMPLETE" in codes(WC.validate(p))


def test_coverage_counts_must_be_integers():
    p = copy.deepcopy(GOOD_PAYLOAD)
    p["checklist_coverage"]["items_checked"] = "nine"
    assert "BAD_TYPE" in codes(WC.validate(p))


def test_boolean_is_not_an_integer_coverage_count():
    p = copy.deepcopy(GOOD_PAYLOAD)
    p["checklist_coverage"]["items_checked"] = True
    assert "BAD_TYPE" in codes(WC.validate(p))


# --------------------------------------------------------------------------- #
# dispatch identity — non-retryable class
# --------------------------------------------------------------------------- #

def test_wrong_worker_answering_is_non_retryable():
    errs = WC.validate(GOOD_PAYLOAD, expect_worker="stock-industry-reviewer")
    assert "WORKER_MISMATCH" in codes(errs)
    assert any(not e.as_dict()["retryable"] for e in errs if e.code == "WORKER_MISMATCH")


def test_expected_worker_pins_the_prefix():
    p = copy.deepcopy(GOOD_PAYLOAD)
    p["worker"] = "stock-industry-reviewer"
    p["prefix"] = "BUS"
    p["findings"][0]["id"] = "BUS-02"
    assert "BAD_PREFIX" in codes(WC.validate(p, expect_worker="stock-industry-reviewer"))


def test_depth_mismatch_is_caught():
    assert "DEPTH_MISMATCH" in codes(WC.validate(GOOD_PAYLOAD, expect_depth="Lite"))


def test_archetype_mismatch_without_a_challenge_is_caught():
    assert "ARCHETYPE_MISMATCH" in codes(WC.validate(GOOD_PAYLOAD, expect_archetype="REIT"))


def test_archetype_mismatch_with_a_challenge_is_allowed():
    """The challenge channel is the de-correlation mechanism — disagreeing
    *through it* must not be reported as a protocol violation."""
    p = copy.deepcopy(GOOD_PAYLOAD)
    p["archetype_applied"] = "Capital-Intensive Industrial"
    p["archetype_challenge"] = {
        "proposed": "Capital-Intensive Industrial",
        "reason": "capex/revenue 31% TTM; gross margin 21%",
    }
    assert WC.validate(p, expect_archetype="High-Growth SaaS / Software") == []


def test_challenge_requires_proposed_and_reason():
    p = copy.deepcopy(GOOD_PAYLOAD)
    p["archetype_challenge"] = {"proposed": "REIT"}
    assert "MISSING_FIELD" in codes(WC.validate(p))


def test_mandatory_archetype_checks_are_enforced():
    p = copy.deepcopy(GOOD_PAYLOAD)
    p["mandatory_checks_run"] = []
    assert "MANDATORY_CHECK_MISSING" in codes(WC.validate(p, require_checks=["BUS-11"]))
    p["mandatory_checks_run"] = ["BUS-11"]
    assert WC.validate(p, require_checks=["BUS-11"]) == []


def test_skipped_worker_is_not_faulted_for_unreached_checks():
    """A worker that never got a 10-K cannot be blamed for not running BUS-11."""
    p = copy.deepcopy(GOOD_PAYLOAD)
    p["status"] = "SKIPPED"
    p["status_reason"] = "no 10-K in manifest"
    p["mandatory_checks_run"] = []
    assert "MANDATORY_CHECK_MISSING" not in codes(WC.validate(p, require_checks=["BUS-11"]))


# --------------------------------------------------------------------------- #
# retryable partition — the state machine branches on this
# --------------------------------------------------------------------------- #

def test_retryable_partition_is_exhaustive_and_disjoint():
    """Every code the validator can emit must be classified. An unclassified
    code would make the retry decision undefined at runtime."""
    emitted = {
        "MISSING_BLOCK", "MULTIPLE_BLOCKS", "BAD_JSON", "BAD_VERSION",
        "MISSING_FIELD", "BAD_TYPE", "BAD_STATUS", "BAD_SEVERITY", "BAD_PREFIX",
        "BAD_CITATION", "CONFIDENCE_MISMATCH", "COVERAGE_INCOMPLETE",
        "MANDATORY_CHECK_MISSING", "WORKER_MISMATCH", "DEPTH_MISMATCH",
        "ARCHETYPE_MISMATCH",
    }
    non_retryable = {"WORKER_MISMATCH", "DEPTH_MISMATCH", "ARCHETYPE_MISMATCH"}
    assert WC.RETRYABLE == emitted - non_retryable
    assert not (WC.RETRYABLE & non_retryable)


def test_error_codes_documented_in_the_contract_reference():
    """The reference table and the implementation must not drift apart."""
    ref = os.path.join(os.path.dirname(__file__), "..", "..", "references", "worker-contract.md")
    with open(ref, encoding="utf-8") as f:
        text = f.read()
    for code in WC.RETRYABLE | {"WORKER_MISMATCH", "DEPTH_MISMATCH", "ARCHETYPE_MISMATCH"}:
        assert f"`{code}`" in text, f"error code {code} not documented in worker-contract.md"


# --------------------------------------------------------------------------- #
# consolidation
# --------------------------------------------------------------------------- #

def _payload(worker, prefix, findings, status="OK", **extra):
    p = copy.deepcopy(GOOD_PAYLOAD)
    p.update(worker=worker, prefix=prefix, findings=findings, status=status, **extra)
    if status != "OK":
        p["status_reason"] = "test"
    return p


def _finding(fid, severity="Medium", title=None):
    return {
        "id": fid,
        "severity": severity,
        "title": title or f"finding {fid}",
        "citation": {"source": "10-K", "locator": "Item 7", "fiscal_period": "FY2025"},
        "evidence": "x",
        "implication": "y",
        "confidence": "first-hand",
    }


def test_consolidate_sorts_high_before_low():
    out = WC.consolidate([
        _payload("stock-business-reviewer", "BUS", [_finding("BUS-01", "Low"), _finding("BUS-02", "High")]),
    ])
    assert [f["id"] for f in out["findings"]] == ["BUS-02", "BUS-01"]
    assert out["by_severity"] == {"High": 1, "Medium": 0, "Low": 1}


def test_consolidate_merges_the_same_mechanism_across_workers():
    same = "Margin compression from client incentives"
    out = WC.consolidate([
        _payload("stock-business-reviewer", "BUS", [_finding("BUS-11", "High", same)]),
        _payload("stock-earnings-quality-reviewer", "EQ", [_finding("EQ-04", "High", same)]),
    ])
    assert len(out["findings"]) == 1
    assert out["findings"][0]["reported_by"] == "BUS"
    assert out["findings"][0]["also_reported_by"] == ["EQ"]


def test_consolidate_keeps_distinct_mechanisms_separate():
    out = WC.consolidate([
        _payload("stock-earnings-quality-reviewer", "EQ", [_finding("EQ-02", "High", "Negative FCF")]),
        _payload("stock-balance-sheet-reviewer", "BS", [_finding("BS-03", "High", "Cash runway under 12 months")]),
    ])
    assert len(out["findings"]) == 2


def test_consolidate_excludes_skipped_and_refused_workers():
    out = WC.consolidate([
        _payload("stock-business-reviewer", "BUS", [_finding("BUS-01")]),
        _payload("stock-industry-reviewer", "IND", [_finding("IND-01")], status="SKIPPED"),
        _payload("stock-management-reviewer", "MGT", [_finding("MGT-01")], status="REFUSED"),
    ])
    assert [f["id"] for f in out["findings"]] == ["BUS-01"]
    assert set(out["workers_excluded"]) == {"stock-industry-reviewer", "stock-management-reviewer"}


def test_consolidate_cap_never_drops_a_high_to_keep_a_low():
    findings = [_finding(f"BUS-{i:02d}", "Low", f"low {i}") for i in range(1, 6)]
    findings.append(_finding("BUS-09", "High", "the high one"))
    out = WC.consolidate([_payload("stock-business-reviewer", "BUS", findings)], cap=2)
    kept = [f["id"] for f in out["findings"]]
    assert "BUS-09" in kept
    assert len(kept) == 2
    assert out["suppressed_count"] == 4


def test_consolidate_reports_degradation_reasons():
    out = WC.consolidate([
        _payload("stock-management-reviewer", "MGT", [], status="DEGRADED"),
    ])
    assert out["degraded"] == [{"worker": "stock-management-reviewer", "reason": "test"}]


def test_two_matching_challenges_mark_the_archetype_contested():
    challenge = {"proposed": "Capital-Intensive Industrial", "reason": "capex 31%"}
    out = WC.consolidate([
        _payload("stock-business-reviewer", "BUS", [], archetype_challenge=challenge),
        _payload("stock-earnings-quality-reviewer", "EQ", [], archetype_challenge=dict(challenge)),
    ])
    assert out["archetype_contested"] is True
    assert len(out["archetype_challenges"]) == 2


def test_one_challenge_does_not_mark_contested():
    out = WC.consolidate([
        _payload("stock-business-reviewer", "BUS", [],
                 archetype_challenge={"proposed": "REIT", "reason": "rent revenue"}),
    ])
    assert out["archetype_contested"] is False
    assert len(out["archetype_challenges"]) == 1


def test_two_challenges_proposing_different_archetypes_are_not_contested():
    """Disagreement among challengers is not a consensus against the lead."""
    out = WC.consolidate([
        _payload("stock-business-reviewer", "BUS", [],
                 archetype_challenge={"proposed": "REIT", "reason": "a"}),
        _payload("stock-earnings-quality-reviewer", "EQ", [],
                 archetype_challenge={"proposed": "Cyclical", "reason": "b"}),
    ])
    assert out["archetype_contested"] is False


def test_consolidate_ordering_is_reproducible_across_worker_input_order():
    a = _payload("stock-industry-reviewer", "IND", [_finding("IND-01", "High", "moat")])
    b = _payload("stock-business-reviewer", "BUS", [_finding("BUS-01", "High", "mix")])
    forward = [f["id"] for f in WC.consolidate([a, b])["findings"]]
    reverse = [f["id"] for f in WC.consolidate([b, a])["findings"]]
    assert forward == reverse == ["BUS-01", "IND-01"]


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def test_cli_validate_exit_codes(tmp_path, capsys):
    good = tmp_path / "good.md"
    good.write_text(wrap(GOOD_PAYLOAD), encoding="utf-8")
    assert WC.main(["validate", "--reply", str(good)]) == 0
    assert json.loads(capsys.readouterr().out)["verdict"] == "PASS"

    bad = tmp_path / "bad.md"
    bad.write_text("nothing here", encoding="utf-8")
    assert WC.main(["validate", "--reply", str(bad)]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["verdict"] == "FAIL"
    assert result["retryable"] is True


def test_cli_consolidate_fails_when_a_reply_is_invalid(tmp_path, capsys):
    (tmp_path / "a.md").write_text(wrap(GOOD_PAYLOAD), encoding="utf-8")
    (tmp_path / "b.md").write_text("broken", encoding="utf-8")
    rc = WC.main(["consolidate", "--replies", str(tmp_path / "a.md"), str(tmp_path / "b.md")])
    out = json.loads(capsys.readouterr().out)
    # A dropped dimension must not exit 0 — that is how a half-evidenced verdict
    # got published while looking complete.
    assert rc == 1
    assert len(out["invalid_replies"]) == 1
