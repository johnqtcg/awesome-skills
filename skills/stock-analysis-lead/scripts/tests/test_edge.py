"""Tests for finlib P3 edge engines — cross-section (breadth) + verdict diff (monitoring)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from finlib import crosssection as X  # noqa: E402
from finlib import verdict_diff as D  # noqa: E402


def book():
    return [
        {"ticker": "TEAM", "weighted_return_36mo": 1.07, "bear_to_current_ratio": 0.90,
         "good_company_score": 9, "implied_growth": 0.20, "delivered_growth": 0.30},
        {"ticker": "NOW", "weighted_return_36mo": 0.73, "bear_to_current_ratio": 0.84, "good_company_score": 7},
        {"ticker": "AMZN", "weighted_return_36mo": 0.234, "bear_to_current_ratio": 0.63, "good_company_score": 8},
        {"ticker": "NVDA", "weighted_return_36mo": -0.11, "bear_to_current_ratio": 0.32,
         "good_company_score": 8, "implied_growth": 0.25, "delivered_growth": 0.55},
        {"ticker": "MRVL", "weighted_return_36mo": -0.22, "bear_to_current_ratio": 0.33,
         "good_company_score": 7, "implied_growth": 0.30, "delivered_growth": 0.20},
    ]


def test_crosssection_best_all_round_is_TEAM():
    res = X.analyze(book())
    assert res["best_all_round"] == "TEAM"
    team = next(r for r in res["ranked"] if r["ticker"] == "TEAM")
    assert team["rank_return"] == 1 and team["rank_downside"] == 1 and team["rank_quality"] == 1


def test_crosssection_flags_best_risk_reward_and_growth_gaps():
    res = X.analyze(book())
    flags = " ".join(res["dislocations"])
    assert "TEAM" in flags and "risk/reward" in flags
    # MRVL: implied 0.30 > delivered 0.20 -> priced for acceleration
    assert any("MRVL" in f and "acceleration" in f for f in res["dislocations"])
    # NVDA: implied 0.25 < delivered 0.55 -> "below delivered" value flag
    assert any("NVDA" in f and "BELOW delivered" in f for f in res["dislocations"])


def test_crosssection_ranks_losers_last():
    res = X.analyze(book())
    order = [r["ticker"] for r in res["ranked"]]
    assert order.index("TEAM") < order.index("AMZN") < order.index("MRVL")


def test_verdict_diff_detects_upgrade_trigger_and_new_assumption():
    prev = {"ticker": "AMZN", "verdict": "Watch", "current_price": 237.5,
            "target_base": 300, "key_bull_assumptions": ["AWS reaccel", "ads engine"]}
    new = {"ticker": "AMZN", "verdict": "Buy", "current_price": 195.0,
           "target_base": 300, "key_bull_assumptions": ["AWS reaccel", "ads engine", "FCF inflection 2027"],
           "invalidation_triggers": ["BUY-zone alert at <=$200 (clean entry)"]}
    out = D.diff(prev, new)
    assert out["material"]
    joined = " | ".join(out["changes"])
    assert "verdict: Watch -> Buy" in joined
    assert "current_price" in joined
    assert any("crossed buy-trigger" in c for c in out["changes"])   # 195 <= 200
    assert any("ADDED" in a and "FCF inflection" in a for a in out["assumption_breaks"])


def test_verdict_diff_no_change_is_immaterial():
    e = {"ticker": "X", "verdict": "Hold", "current_price": 100, "target_base": 110,
         "key_bull_assumptions": ["a"]}
    out = D.diff(dict(e), dict(e))
    assert out["material"] is False