"""Tests for finlib (P0 计算/口径 layer + P1 EDGAR parsing).

The two headline regressions encode the real errors found in the MSFT report:
  1. P/FCF mislabeled as EV/FCF
  2. capex/revenue stated 50% but recomputes to ~67%
  3. operating-leverage concluded from a single quarter
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from finlib import ratios, lint  # noqa: E402


# --------------------------------------------------------------------------- #
# ratios — math correctness
# --------------------------------------------------------------------------- #

def test_ev_subtracts_net_cash():
    # net-cash company: EV must be BELOW market cap
    ev = ratios.enterprise_value(mktcap=3150, total_debt=50, cash_and_sti=110)["value"]
    assert ev == 3090
    assert ev < 3150


def test_ev_fcf_vs_pfcf_differ():
    pfcf = ratios.pfcf(mktcap=3150, fcf=71.6)["value"]
    evfcf = ratios.ev_fcf(mktcap=3150, total_debt=50, cash_and_sti=110, fcf=71.6)["value"]
    assert round(pfcf, 1) == 44.0           # the report's "44x"
    assert evfcf < pfcf                       # EV/FCF is lower for a net-cash co
    assert abs(evfcf - 43.16) < 0.1


def test_capex_intensity_math():
    assert abs(ratios.capex_intensity(190, 282)["value"] - 0.6738) < 0.001


# --------------------------------------------------------------------------- #
# lint — the three headline failures must be caught
# --------------------------------------------------------------------------- #

def test_pfcf_mislabeled_as_ev_fcf_FAILS():
    entry = {
        "id": "pfcf",
        "claimed_label": "EV/FCF",          # WRONG label
        "stated_value": 44.0,
        "inputs": {"mktcap": 3150, "fcf": 71.6},   # no debt/cash -> not EV
        "tags": {"basis": "gaap", "period": "ttm"},
    }
    findings = lint.lint([entry])
    fails = [f for f in findings if f["level"] == "FAIL"]
    assert fails, "should FAIL: P/FCF labeled EV/FCF"
    assert any("EV" in f["message"] for f in fails)


def test_capex_intensity_inconsistent_FAILS():
    entry = {
        "id": "capex_intensity",
        "claimed_label": "capex/revenue",
        "stated_value": 0.50,               # report said "50%+"
        "inputs": {"capex": 190, "revenue": 282},   # actually ~67%
        "tags": {"basis": "gaap", "period": "fy"},
    }
    findings = lint.lint([entry])
    fails = [f for f in findings if f["level"] == "FAIL"]
    assert fails, "should FAIL: stated 50% but recomputes to 67%"
    assert any("recomputes" in f["message"] for f in fails)


def test_single_period_operating_leverage_FAILS():
    entry = {
        "id": "operating_margin",
        "claimed_label": "operating leverage positive",
        "stated_value": 0.46,
        "inputs": {"operating_income": 0.46 * 70, "revenue": 70},
        "kind": "operating_leverage",
        "is_trend_claim": True,
        "tags": {"period_count": 1},        # single quarter
    }
    findings = lint.lint([entry])
    fails = [f for f in findings if f["level"] == "FAIL"]
    assert any("period" in f["message"] for f in fails), "single-quarter trend claim should FAIL"


def test_clean_metrics_PASS():
    metrics = [
        {  # correctly labeled & computed EV/FCF
            "id": "ev_fcf",
            "claimed_label": "EV/FCF",
            "stated_value": 43.16,
            "inputs": {"mktcap": 3150, "total_debt": 50, "cash_and_sti": 110, "fcf": 71.6},
            "tags": {"basis": "gaap", "period": "ttm"},
        },
        {  # correctly labeled P/FCF
            "id": "pfcf",
            "claimed_label": "P/FCF",
            "stated_value": 44.0,
            "inputs": {"mktcap": 3150, "fcf": 71.6},
            "tags": {"basis": "gaap", "period": "ttm"},
        },
        {  # operating leverage backed by 4 quarters
            "id": "operating_margin",
            "claimed_label": "op margin",
            "stated_value": 0.46,
            "inputs": {"operating_income": 32.2, "revenue": 70},
            "kind": "operating_leverage",
            "is_trend_claim": True,
            "tags": {"period_count": 4},
        },
    ]
    findings = lint.lint(metrics)
    fails = [f for f in findings if f["level"] == "FAIL"]
    assert not fails, f"clean metrics should pass, got {fails}"


# --------------------------------------------------------------------------- #
# lint — operating-leverage definition + GAAP/adjusted reconciliation (P0)
# --------------------------------------------------------------------------- #

def test_undefined_operating_leverage_pp_FAILS():
    # The MA report's "+4.9pp operating leverage" with no declared formula.
    entry = {
        "claimed_label": "operating leverage +4.9pp",
        "stated_value": 4.9,
        "inputs": {},                      # no inputs -> no recomputable definition
        "kind": "operating_leverage",
        "tags": {"period_count": 5},       # multi-period, so NOT the single-period FAIL
    }
    findings = lint.lint([entry])
    fails = [f for f in findings if f["level"] == "FAIL"]
    assert fails, "undefined '+X pp' operating leverage should FAIL"
    assert any("recomputable" in f["message"] for f in fails)


def test_defined_operating_leverage_pp_PASSES():
    # Same claim, but with a declared definition the linter can recompute.
    entry = {
        "id": "operating_leverage_pp",
        "claimed_label": "operating leverage (rev−opex growth) +6pp",
        "stated_value": 6.0,
        "inputs": {"revenue_growth_pp": 16.0, "opex_growth_pp": 10.0},
        "kind": "operating_leverage",
        "tags": {"period_count": 4},
    }
    findings = lint.lint([entry])
    fails = [f for f in findings if f["level"] == "FAIL"]
    assert not fails, f"a defined, recomputable operating-leverage claim should pass, got {fails}"


def test_headline_margin_single_basis_trend_FAILS():
    # GAAP operating margin used in a cross-year trend, no GAAP↔adjusted reconciliation.
    entry = {
        "id": "operating_margin",
        "claimed_label": "operating margin 57.6% (5y +4.8pp)",
        "stated_value": 0.576,
        "inputs": {"operating_income": 57.6, "revenue": 100.0},
        "is_trend_claim": True,
        "tags": {"basis": "gaap", "period_count": 5},
    }
    findings = lint.lint([entry])
    fails = [f for f in findings if f["level"] == "FAIL"]
    assert any("basis" in f["message"] for f in fails), "unreconciled GAAP trend margin should FAIL"


def test_headline_margin_reconciled_PASSES():
    entry = {
        "id": "operating_margin",
        "claimed_label": "operating margin 57.6% GAAP / 59.2% adj",
        "stated_value": 0.576,
        "inputs": {"operating_income": 57.6, "revenue": 100.0},
        "is_trend_claim": True,
        "tags": {"basis": "gaap", "period_count": 5, "basis_reconciled": True},
    }
    findings = lint.lint([entry])
    fails = [f for f in findings if f["level"] == "FAIL"]
    assert not fails, f"reconciled headline margin should pass, got {fails}"


# --------------------------------------------------------------------------- #
# edgar — XBRL parsing against a synthetic fixture (no network)
# --------------------------------------------------------------------------- #

def test_edgar_parses_companyfacts_fixture():
    from finlib import edgar
    facts = {
        "facts": {
            "us-gaap": {
                "Revenues": {"units": {"USD": [
                    {"end": "2025-06-30", "val": 282000000000, "fy": 2025, "fp": "FY", "form": "10-K"},
                ]}},
                "PaymentsToAcquirePropertyPlantAndEquipment": {"units": {"USD": [
                    {"end": "2025-06-30", "val": 64600000000, "fy": 2025, "fp": "FY", "form": "10-K"},
                ]}},
            }
        }
    }
    series = edgar.concept_series(facts, "us-gaap", "Revenues", "USD")
    assert series and series[-1]["val"] == 282000000000
    fin = edgar.extract_financials(facts)
    assert fin["revenue"]["value"] == 282000000000
    assert fin["capex"]["value"] == 64600000000
    # a concept that is absent must be reported as a gap, not fabricated
    assert "segment_operating_income" in fin["gaps"]