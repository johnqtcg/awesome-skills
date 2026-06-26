"""Tests for finlib.sotp — sum-of-the-parts for option-dominated names.

The fixture is the TSLA case the critique exposed: ~90% of value is the
robotaxi/Optimus/FSD option, which the original report handled as a single
"$650 判断值". SOTP forces each engine into an explicit, range-expressed,
source-tagged leg and surfaces option_share_of_value.
"""
import copy
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from finlib import sotp as S  # noqa: E402


def _data(ref):
    return {"kind": "data", "ref": ref}


def _est(note):
    return {"kind": "estimate", "note": note}


def _assume(note):
    return {"kind": "assumption", "note": note}


def tsla_sotp():
    """Tesla as base archetype Cyclical-auto + Optionality Overlay.
    EV contributions in $B; net cash held at the top level."""
    return {
        "ticker": "TSLA", "current_price": 374.84,
        "shares_diluted": 3.35, "net_cash": 28.9,    # the $289亿 bear-floor cash leg
        "segments": [
            {
                "name": "auto", "method": "fixed",
                "drivers": {
                    # enterprise value of the visible auto business from valuation.py DCF
                    "amount": {"value": 90.0, "low": 60.0, "high": 130.0,
                               "source": _data("valuation.py run base EV @auto")},
                },
            },
            {
                "name": "energy", "method": "multiple",
                "drivers": {
                    # MODELED, not a one-line positive: ~steady-state EBITDA x EV/EBITDA
                    "metric": {"value": 4.0, "low": 2.5, "high": 6.5,
                               "source": _data("10-K:energy GWh x $/kWh x 39.5% margin")},
                    "multiple": {"value": 8.0, "low": 6.0, "high": 11.0,
                                 "source": _assume("high-growth hardware EV/EBITDA")},
                },
            },
            {
                "name": "robotaxi", "method": "option",
                "drivers": {
                    "tam": {"value": 300.0, "low": 100.0, "high": 600.0, "source": _est("ride TAM 2032")},
                    "share": {"value": 0.15, "low": 0.05, "high": 0.30, "source": _est("vs Waymo")},
                    "take_rate": {"value": 0.50, "low": 0.30, "high": 0.70, "source": _assume("network take")},
                    "margin": {"value": 0.30, "source": _assume("steady-state op margin")},
                    "exit_multiple": {"value": 13.0, "source": _assume("EV/EBIT at maturity")},
                    "years": {"value": 7.0, "source": _assume("time to scale")},
                    "discount": {"value": 0.15, "source": _assume("venture discount")},
                    "p_success": {"value": 0.16, "low": 0.08, "high": 0.35, "source": _est("4+ independent successes")},
                },
            },
        ],
    }


# --- guardrails --------------------------------------------------------------

def test_clean_model_validates_and_values():
    m = tsla_sotp()
    v = S.validate_sotp(m)
    assert v["ok"], v["errors"]
    res = S.run(m)
    assert res["ok"]
    assert res["per_share_low"] < res["per_share_base"] < res["per_share_high"]


def test_unsourced_driver_is_REJECTED():
    m = tsla_sotp()
    del m["segments"][1]["drivers"]["multiple"]["source"]
    v = S.validate_sotp(m)
    assert not v["ok"]
    assert any("no source" in e for e in v["errors"])


def test_option_leg_without_range_is_REJECTED():
    """The core false-precision guard: a venture value may not be a point."""
    m = tsla_sotp()
    del m["segments"][2]["drivers"]["p_success"]["low"]
    v = S.validate_sotp(m)
    assert not v["ok"]
    assert any("p_success" in e and "low" in e for e in v["errors"])


def test_option_range_must_bracket_value():
    m = tsla_sotp()
    m["segments"][2]["drivers"]["share"]["high"] = 0.10   # value 0.15 now outside [0.05, 0.10]
    v = S.validate_sotp(m)
    assert not v["ok"]
    assert any("low <= value <= high" in e for e in v["errors"])


def test_missing_required_option_driver_REJECTED():
    m = tsla_sotp()
    del m["segments"][2]["drivers"]["take_rate"]
    v = S.validate_sotp(m)
    assert not v["ok"]
    assert any("take_rate" in e for e in v["errors"])


# --- valuation behaviour -----------------------------------------------------

def test_grounding_is_LOW_when_option_legs_present():
    res = S.run(tsla_sotp())
    assert res["grounding"].startswith("LOW")


def test_grounding_OK_without_option_legs():
    m = tsla_sotp()
    m["segments"] = [s for s in m["segments"] if s["method"] != "option"]
    res = S.run(m)
    assert res["grounding"].startswith("OK")


def test_market_implied_vs_modeled_option_share_is_the_bear_signal():
    """The critique's core insight, made quantitative: the MARKET assigns ~90% of
    the price to the option, but a disciplined SOTP — even being generous on the
    venture — supports far less. The gap IS the priced-for-perfection verdict."""
    res = S.run(tsla_sotp())
    assert res["market_implied_option_share"] > 0.80, "market prices ~90% as option"
    # a disciplined, probability-weighted SOTP supports a much smaller option share
    assert res["option_share_of_value"] < res["market_implied_option_share"]
    # and the base SOTP per-share sits far below the current price (the bear signal)
    assert res["base_upside"] < -0.4, "disciplined SOTP << market price → overvalued"


def test_option_leg_reports_conditional_value_and_psuccess():
    res = S.run(tsla_sotp())
    robo = next(s for s in res["segments"] if s["name"] == "robotaxi")
    assert robo["grounding"] == "LOW"
    assert robo["conditional_ev_if_success"] > robo["ev_base"], (
        "expected (probability-weighted) value must be below the if-success value"
    )
    assert robo["p_success"] == 0.16


def test_probability_weighting_scales_option_contribution():
    """Halving P(success) roughly halves the option leg's expected contribution."""
    m = tsla_sotp()
    base = S.run(m)
    robo_base = next(s for s in base["segments"] if s["name"] == "robotaxi")["ev_base"]
    m2 = copy.deepcopy(m)
    m2["segments"][2]["drivers"]["p_success"]["value"] = 0.08
    halved = S.run(m2)
    robo_half = next(s for s in halved["segments"] if s["name"] == "robotaxi")["ev_base"]
    assert abs(robo_half - robo_base / 2) < 1e-6


def test_per_share_distribution_not_a_point():
    """The band must be materially wide for an option-dominated name — a tight
    band would mean the framework collapsed the genuine uncertainty."""
    res = S.run(tsla_sotp())
    assert res["per_share_high"] > res["per_share_low"] * 2, "option uncertainty must produce a wide band"


def test_base_upside_computed_against_current_price():
    res = S.run(tsla_sotp())
    assert "base_upside" in res and res["current_price"] == 374.84