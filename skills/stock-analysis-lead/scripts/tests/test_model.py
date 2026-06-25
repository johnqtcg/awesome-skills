"""Tests for finlib P2 — driver model + valuation + the false-precision guardrail."""
import copy
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from finlib import model as M  # noqa: E402
from finlib import valuation as V  # noqa: E402


def _data(ref):
    return {"kind": "data", "ref": ref}


def _assume(note):
    return {"kind": "assumption", "note": note}


def msft_model():
    return {
        "ticker": "MSFT", "current_price": 421.92,
        "shares_diluted": 7.43, "net_cash": 60.0, "horizon_years": 5,
        "drivers": {
            "revenue_0":         {"value": 282.0, "source": _data("financials.json:revenue@FY2025")},
            "op_margin_start":   {"value": 0.45,  "source": _data("financials.json:op_income/revenue@FY2025")},
            "da_pct":            {"value": 0.10,  "source": _data("financials.json:dep_amort/revenue@FY2025")},
            "capex_pct":         {"value": 0.20,  "source": _data("financials.json:capex/revenue@FY2025")},
            "revenue_cagr":      {"value": 0.12,  "source": _assume("Azure-led; consensus ~12%")},
            "op_margin_terminal":{"value": 0.43,  "source": _assume("mild fade")},
            "tax_rate":          {"value": 0.17,  "source": _data("financials.json:effective_tax@FY2025")},
            "wacc":              {"value": 0.09,  "source": _assume("CAPM ~9%")},
            "terminal_growth":   {"value": 0.04,  "source": _assume("~GDP+")},
        },
        "scenarios": {
            "bull": {"revenue_cagr": 0.15, "op_margin_terminal": 0.45, "terminal_growth": 0.045},
            "base": {},
            "bear": {"revenue_cagr": 0.07, "op_margin_terminal": 0.40, "terminal_growth": 0.03},
        },
        "probabilities": {"bull": 0.25, "base": 0.50, "bear": 0.25},
    }


# --- guardrail ---------------------------------------------------------------

def test_unsourced_driver_is_REJECTED():
    m = msft_model()
    del m["drivers"]["revenue_cagr"]["source"]      # strip the source
    v = M.validate_model(m)
    assert not v["ok"]
    assert any("no source" in e for e in v["errors"])


def test_anchor_as_assumption_is_FLAGGED():
    m = msft_model()
    m["drivers"]["revenue_0"]["source"] = _assume("eyeballed")   # anchor guessed
    v = M.validate_model(m)
    assert v["ok"]                                  # not fatal, but flagged
    assert "revenue_0" in v["provenance"]["anchor_assumed"]
    res = V.run(m)
    assert res["grounding"].startswith("LOW")


def test_clean_model_is_OK_and_grounded():
    v = M.validate_model(msft_model())
    assert v["ok"] and not v["warnings"]
    res = V.run(msft_model())
    assert res["grounding"].startswith("OK")


def test_wacc_below_growth_REJECTED():
    m = msft_model()
    m["drivers"]["terminal_growth"]["value"] = 0.10   # > wacc 0.09
    assert not M.validate_model(m)["ok"]


# --- valuation behaviour -----------------------------------------------------

def test_terminal_multiple_is_DERIVED_not_typed():
    res = V.run(msft_model())
    # Gordon: EV/FCF = (1+g)/(wacc-g) = 1.04/0.05 = 20.8
    assert abs(res["derived_terminal_ev_fcf"] - 20.8) < 0.05


def test_living_model_changing_cagr_moves_target():
    base = V.value_per_share(msft_model(), M.apply_scenario(msft_model(), "base"))["per_share"]
    m = msft_model()
    m["scenarios"]["base"] = {"revenue_cagr": 0.16}   # bump Azure growth +4pp
    higher = V.value_per_share(m, M.apply_scenario(m, "base"))["per_share"]
    assert higher > base * 1.10, "raising growth must raise the target materially"


def test_scenarios_ordered_bull_gt_base_gt_bear():
    s = V.run_scenarios(msft_model())
    assert s["bull"] > s["base"] > s["bear"]
    assert "weighted" in s and "bear_to_current" in s


def test_reverse_dcf_finds_implied_growth():
    rev = V.reverse_dcf(msft_model(), 421.92)
    assert rev["implied"] is not None
    # to justify $422 (above our ~$300 base) the market implies HIGHER growth than base 12%
    assert rev["implied"] > 0.12


def test_sensitivity_is_monotonic_in_growth():
    rows = V.sensitivity(msft_model(), "revenue_cagr", span=0.03, steps=5)
    ps = [r["per_share"] for r in rows]
    assert ps == sorted(ps), "per-share should rise with growth"


def test_sensitivity_2d_grid_shape_and_direction():
    res = V.sensitivity_2d(msft_model(), "revenue_cagr", "wacc", span_x=0.03, span_y=0.01, steps=5)
    assert len(res["grid"]) == 5 and all(len(r) == 5 for r in res["grid"])
    # within a fixed-wacc row, per-share rises with growth (x ascending)
    for row in res["grid"]:
        assert row == sorted(row), "per-share should rise with growth along x"
    # holding growth fixed, per-share falls as WACC rises (y ascending => higher discount)
    col0 = [res["grid"][j][0] for j in range(5)]
    assert col0 == sorted(col0, reverse=True), "per-share should fall as WACC rises"


# --- bottom-up revenue bridge (segments / volume×yield / contra-revenue) -----

def network_bridge_model():
    """Payment-network-style model: domestic CAGR + cross-border volume×yield +
    VAS CAGR, minus a client-incentives contra-revenue line."""
    return {
        "ticker": "MA", "current_price": 493.0,
        "shares_diluted": 0.906, "net_cash": -15.0, "horizon_years": 5,
        "revenue_bridge": {
            "segments": [
                {"name": "domestic", "mode": "cagr"},
                {"name": "cross_border", "mode": "volume_yield"},
                {"name": "vas", "mode": "cagr"},
            ],
            "contra": True,
        },
        "drivers": {
            "seg.domestic.revenue_0":         {"value": 12.0, "source": _data("10-K:domestic@FY25")},
            "seg.domestic.cagr":              {"value": 0.10, "source": _assume("steady")},
            "seg.cross_border.revenue_0":     {"value": 12.0, "source": _data("10-K:xborder@FY25")},
            "seg.cross_border.volume_growth": {"value": 0.12, "source": _assume("travel")},
            "seg.cross_border.yield_growth":  {"value": 0.01, "source": _assume("mix")},
            "seg.vas.revenue_0":              {"value": 13.3, "source": _data("10-K:vas@FY25")},
            "seg.vas.cagr":                   {"value": 0.20, "source": _assume("VAS fast")},
            "contra.pct_of_gross":            {"value": 0.30, "source": _data("10-K:incentives/gross@FY25")},
            "op_margin_start":                {"value": 0.576, "source": _data("financials.json")},
            "op_margin_terminal":             {"value": 0.59, "source": _assume("mild lift")},
            "da_pct":                         {"value": 0.03, "source": _data("financials.json")},
            "capex_pct":                      {"value": 0.015, "source": _data("financials.json")},
            "tax_rate":                       {"value": 0.17, "source": _data("financials.json")},
            "wacc":                           {"value": 0.09, "source": _assume("CAPM ~9%")},
            "terminal_growth":                {"value": 0.04, "source": _assume("~GDP+")},
        },
        "scenarios": {
            "bull": {"seg.cross_border.volume_growth": 0.18, "seg.vas.cagr": 0.24},
            "base": {},
            # Bear is DERIVED from segment shocks, not a hand-filled blended CAGR:
            "bear": {"seg.cross_border.volume_growth": -0.05,
                     "seg.vas.cagr": 0.12, "seg.domestic.cagr": 0.04},
        },
        "probabilities": {"bull": 0.30, "base": 0.52, "bear": 0.18},
    }


def test_bridge_model_validates_and_values():
    m = network_bridge_model()
    v = M.validate_model(m)
    assert v["ok"], v["errors"]
    res = V.run(m)
    assert res["ok"] and res["base_target"] > 0
    assert res["grounding"].startswith("OK"), res["grounding"]
    # net revenue starts below gross because of the contra line
    base = M.apply_scenario(m, "base")
    net0 = V._bridge_net_revenue(m, base, 0)
    assert abs(net0 - (12 + 12 + 13.3) * (1 - 0.30)) < 1e-6


def test_bridge_bear_cagr_is_DERIVED_not_typed():
    m = network_bridge_model()
    s = V.run_scenarios(m)
    assert s["bull"] > s["base"] > s["bear"]
    # the blended CAGR is an OUTPUT of the segment assumptions
    assert "derived_cagr" in s
    assert s["derived_cagr"]["bear"] < s["derived_cagr"]["base"] < s["derived_cagr"]["bull"]


def test_bridge_missing_segment_driver_REJECTED():
    m = network_bridge_model()
    del m["drivers"]["seg.cross_border.yield_growth"]
    v = M.validate_model(m)
    assert not v["ok"]
    assert any("seg.cross_border.yield_growth" in e for e in v["errors"])


def test_bridge_reverse_dcf_runs():
    m = network_bridge_model()
    rev = V.reverse_dcf(m, m["current_price"])
    assert rev["driver"] == "revenue_cagr" and "implied" in rev