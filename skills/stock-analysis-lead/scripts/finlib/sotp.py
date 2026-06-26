"""finlib.sotp — sum-of-the-parts valuation for option-dominated / multi-engine companies.

A single-entity DCF cannot value a company whose price is dominated by unproven
future businesses (robotaxi, humanoid robots, an AI platform). Running a reverse-DCF
on the *visible* business of such a name only tells you the visible business cannot
justify the price — which is the DEFINITION of an option stock, not evidence of
anything. SOTP values each engine on its own terms and sums them.

Three leg methods:
  fixed    — a directly-supplied value (e.g. an enterprise value produced by the
             driver-model DCF in valuation.py for the established auto business).
             One number, one source. (Cash/debt go in top-level `net_cash`, NOT a leg.)
  multiple — value = metric x multiple (e.g. energy EBITDA x EV/EBITDA, or energy
             GWh x $/kWh x margin folded into a metric x exit multiple). For an
             established, modelable segment — the antidote to a one-line "positive".
  option   — a venture leg valued by an EXPLICIT chain, then probability- and
             time-discounted:
                conditional_ev = tam x share x take_rate x margin x exit_multiple
                pv_if_success  = conditional_ev / (1+discount)**years
                expected_value = pv_if_success x p_success
             Every driver carries a source; the genuinely-unknowable ones
             (tam, share, take_rate, p_success) MUST also carry low/high, so the
             leg is a RANGE, never a point. The SOTP equity value is therefore a
             DISTRIBUTION (low/base/high), not a single target.

Design intent (the whole point): for an option stock the SOTP's value is
AUDITABILITY, not precision. It converts one opaque "$650 judgment" into a chain
of individually-falsifiable, range-expressed, source-tagged assumptions, and it
surfaces `option_share_of_value` — how much of the price is unproven-venture
narrative. It must never be dressed up as a precise derived number; the guardrails
below enforce that (un-sourced driver rejected; option leg without ranges rejected;
grounding is LOW whenever any option leg is present).

The per-venture `p_success` here is the SAME number that feeds the venture
probability tree in `scenario-probability-calibration.md` — use it consistently so
the Bull/Bear scenario weights and the SOTP option legs cannot silently disagree.

$ figures in USD billions; shares in billions; rates/margins as fractions.

CLI:
    python3 sotp.py run --model sotp.json
"""
from __future__ import annotations

import argparse
import json
import sys

_KINDS = ("data", "assumption", "estimate")
# Required driver names per leg method.
_REQUIRED = {
    "fixed": ("amount",),
    "multiple": ("metric", "multiple"),
    "option": ("tam", "share", "take_rate", "margin", "exit_multiple", "years",
               "discount", "p_success"),
}
# Option-leg drivers that MUST carry low/high — an option value may not be a point.
_UNCERTAIN = ("tam", "share", "take_rate", "p_success")


def _src(driver: dict) -> dict:
    return driver.get("source") or {}


def _at(driver: dict, scenario: str) -> float:
    """Driver value at low/base/high. Falls back to the point value when a
    scenario bound is absent (legitimate for the non-uncertain drivers)."""
    if scenario == "low":
        return driver.get("low", driver["value"])
    if scenario == "high":
        return driver.get("high", driver["value"])
    return driver["value"]


def validate_sotp(model: dict) -> dict:
    """Return {ok, errors, warnings}. ok=False means do NOT value it."""
    errors: list = []
    warnings: list = []
    segs = model.get("segments")
    if not segs:
        errors.append("no segments — a SOTP needs at least one segment")
    if not model.get("shares_diluted"):
        errors.append("missing shares_diluted")

    for seg in segs or []:
        name = seg.get("name", "?")
        method = seg.get("method")
        if method not in _REQUIRED:
            errors.append(f"segment '{name}': method must be one of {tuple(_REQUIRED)}, got {method!r}")
            continue
        drivers = seg.get("drivers", {})
        for req in _REQUIRED[method]:
            if req not in drivers:
                errors.append(f"segment '{name}' ({method}): missing required driver '{req}'")
        for dname, d in drivers.items():
            if "value" not in d:
                errors.append(f"segment '{name}' driver '{dname}' has no value")
            if _src(d).get("kind") not in _KINDS:
                # GUARDRAIL: no un-sourced numbers in a valuation
                errors.append(f"segment '{name}' driver '{dname}' has no source "
                              f"(kind must be one of {_KINDS}) — un-sourced numbers may not enter a SOTP")
        if method == "option":
            for u in _UNCERTAIN:
                d = drivers.get(u)
                if not d:
                    continue
                if "low" not in d or "high" not in d:
                    # GUARDRAIL: an option value is a distribution, never a point
                    errors.append(f"segment '{name}' is an option leg; driver '{u}' must declare "
                                  f"low and high — a venture value may not be stated as a point")
                elif not (d["low"] <= d["value"] <= d["high"]):
                    errors.append(f"segment '{name}' driver '{u}': require low <= value <= high")
    return {"ok": not errors, "errors": errors, "warnings": warnings}


def _segment_ev(seg: dict, scenario: str) -> dict:
    """Enterprise-value contribution of one segment at low/base/high.

    Returns {ev, conditional_ev, p_success} — conditional_ev is the value IF a
    venture succeeds (None for non-option legs); ev is the risk-adjusted (option:
    probability-weighted) contribution that sums into equity."""
    d = seg["drivers"]
    method = seg["method"]
    if method == "fixed":
        ev = _at(d["amount"], scenario)
        return {"ev": ev, "conditional_ev": None, "p_success": None}
    if method == "multiple":
        ev = _at(d["metric"], scenario) * _at(d["multiple"], scenario)
        return {"ev": ev, "conditional_ev": None, "p_success": None}
    # option
    tam = _at(d["tam"], scenario)
    share = _at(d["share"], scenario)
    take = _at(d["take_rate"], scenario)
    margin = _at(d["margin"], scenario)
    exit_mult = _at(d["exit_multiple"], scenario)
    years = _at(d["years"], scenario)
    disc = _at(d["discount"], scenario)
    p = _at(d["p_success"], scenario)
    conditional_ev = tam * share * take * margin * exit_mult
    pv_if_success = conditional_ev / (1 + disc) ** years
    return {"ev": pv_if_success * p, "conditional_ev": conditional_ev, "p_success": p}


def run(model: dict) -> dict:
    v = validate_sotp(model)
    if not v["ok"]:
        return {"ok": False, "errors": v["errors"]}

    shares = model["shares_diluted"]
    net_cash = model.get("net_cash", 0.0)
    has_option = any(s["method"] == "option" for s in model["segments"])

    equity = {}
    for scen in ("low", "base", "high"):
        total_ev = sum(_segment_ev(s, scen)["ev"] for s in model["segments"])
        equity[scen] = total_ev + net_cash

    seg_rows = []
    option_ev_base = 0.0
    for s in model["segments"]:
        base = _segment_ev(s, "base")
        lo = _segment_ev(s, "low")["ev"]
        hi = _segment_ev(s, "high")["ev"]
        if s["method"] == "option":
            option_ev_base += base["ev"]
        row = {
            "name": s["name"], "method": s["method"],
            "ev_low": round(lo, 2), "ev_base": round(base["ev"], 2), "ev_high": round(hi, 2),
            "pct_of_base_equity": round(base["ev"] / equity["base"], 4) if equity["base"] else None,
            "grounding": "LOW" if s["method"] == "option" else "OK",
        }
        if base["conditional_ev"] is not None:
            row["conditional_ev_if_success"] = round(base["conditional_ev"], 2)
            row["p_success"] = base["p_success"]
        seg_rows.append(row)

    per_share = {k: (equity[k] / shares if shares else None) for k in equity}
    out = {
        "ok": True,
        "segments": seg_rows,
        "equity_low": round(equity["low"], 2),
        "equity_base": round(equity["base"], 2),
        "equity_high": round(equity["high"], 2),
        "per_share_low": round(per_share["low"], 2),
        "per_share_base": round(per_share["base"], 2),
        "per_share_high": round(per_share["high"], 2),
        "option_share_of_value": round(option_ev_base / equity["base"], 4) if equity["base"] else None,
        "grounding": ("LOW: contains option legs — the value is a distribution driven by "
                      "unproven-venture assumptions; report the low-base-high band and each "
                      "leg's P(success), never a point target"
                      if has_option else "OK: no option legs"),
    }
    cur = model.get("current_price")
    if cur:
        market_cap = cur * shares
        visible_equity = sum(r["ev_base"] for r in seg_rows if r["method"] != "option") + net_cash
        out["current_price"] = cur
        out["base_upside"] = round((per_share["base"] - cur) / cur, 4)
        # The critique's "~90% is option": how much of the PRICE the market assigns to
        # unproven ventures, vs how much a disciplined SOTP actually supports. The gap
        # between this and `option_share_of_value` is the priced-for-perfection signal.
        out["market_implied_option_share"] = (round((market_cap - visible_equity) / market_cap, 4)
                                               if market_cap else None)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="finlib sum-of-the-parts valuation")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--model", required=True)
    r.add_argument("--out")
    args = ap.parse_args(argv)

    with open(args.model, encoding="utf-8") as f:
        model = json.load(f)
    res = run(model)
    txt = json.dumps(res, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(txt)
    print(txt)
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())