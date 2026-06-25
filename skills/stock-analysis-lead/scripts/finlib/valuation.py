"""finlib.valuation — driver-based DCF / reverse-DCF / scenarios / sensitivity.

Turns "hand-pick three terminal P/Es" into "change one driver, target recomputes".
The terminal multiple is an OUTPUT (Gordon: EV/FCF = (1+g)/(WACC-g)), never typed.
Bull/Base/Bear are three parameterizations of the SAME model, so they are
internally consistent and auditable. Refuses to run an un-validated model.

CLI:
    python3 valuation.py run --model model.json
    python3 valuation.py run --model model.json --sensitivity revenue_cagr
"""
from __future__ import annotations

import argparse
import json
import sys

try:
    from . import model as M
except ImportError:  # script mode
    import model as M  # type: ignore


def _bridge_net_revenue(model: dict, d: dict, t: int) -> float:
    """Net revenue at year t (t=0 is the base year) = Σ segment revenue − contra
    revenue, reading values (with scenario overrides) from the flat dict `d`."""
    horizon = model.get("horizon_years", 5)
    br = model["revenue_bridge"]
    gross = 0.0
    for seg in br["segments"]:
        name = seg["name"]
        r0 = d[M.seg_key(name, "revenue_0")]
        if seg.get("mode") == "volume_yield":
            vg = d[M.seg_key(name, "volume_growth")]
            yg = d[M.seg_key(name, "yield_growth")]
            factor = ((1 + vg) * (1 + yg)) ** t
        else:
            factor = (1 + d[M.seg_key(name, "cagr")]) ** t
        gross += r0 * factor
    if not br.get("contra"):
        return gross
    p0 = d[M.CONTRA_PCT]
    pT = d.get(M.CONTRA_PCT_TERMINAL, p0)
    pct = p0 + (pT - p0) * (t / horizon) if horizon else p0   # incentive ratio fades linearly
    return gross - gross * pct


def _project(d: dict, horizon: int, model: dict = None) -> dict:
    """Project FCF from a flat driver dict (values only). FCF = NOPAT + D&A - capex - ΔNWC.
    If `model` carries a revenue_bridge, the top line is built bottom-up (segments
    − contra); otherwise it is the simple revenue_0 * (1+revenue_cagr)**t line."""
    m0, mT = d["op_margin_start"], d["op_margin_terminal"]
    tax, da_pct, capex_pct = d["tax_rate"], d["da_pct"], d["capex_pct"]
    nwc_pct = d.get("nwc_pct", 0.0)
    wacc, g = d["wacc"], d["terminal_growth"]
    bridge = model is not None and M.has_bridge(model)

    def rev_at(t: int) -> float:
        if bridge:
            return _bridge_net_revenue(model, d, t)
        return d["revenue_0"] * (1 + d["revenue_cagr"]) ** t

    rev0 = rev_at(0)
    pv_explicit = 0.0
    fcf_path = []
    rev_prev = rev0
    fcf_last = 0.0
    rev_last = rev0
    for t in range(1, horizon + 1):
        rev = rev_at(t)
        # linear margin fade from start to terminal across the horizon
        margin = m0 + (mT - m0) * (t / horizon)
        op_inc = rev * margin
        nopat = op_inc * (1 - tax)
        da = rev * da_pct
        capex = rev * capex_pct
        d_nwc = (rev - rev_prev) * nwc_pct
        fcf = nopat + da - capex - d_nwc
        pv_explicit += fcf / (1 + wacc) ** t
        fcf_path.append({"year": t, "revenue": round(rev, 2), "op_margin": round(margin, 4),
                         "fcf": round(fcf, 2)})
        rev_prev = rev
        fcf_last = fcf
        rev_last = rev

    terminal_ev_fcf = (1 + g) / (wacc - g)          # derived terminal multiple
    tv = fcf_last * terminal_ev_fcf                 # = fcf_last*(1+g)/(wacc-g)
    pv_tv = tv / (1 + wacc) ** horizon
    ev = pv_explicit + pv_tv
    derived_cagr = (rev_last / rev0) ** (1 / horizon) - 1 if rev0 and horizon else None
    return {"ev": ev, "pv_explicit": pv_explicit, "pv_tv": pv_tv, "tv": tv,
            "terminal_ev_fcf": terminal_ev_fcf, "fcf_path": fcf_path, "fcf_last": fcf_last,
            "revenue_0": rev0, "derived_revenue_cagr": derived_cagr}


def value_per_share(model: dict, driver_values: dict) -> dict:
    horizon = model.get("horizon_years", 5)
    proj = _project(driver_values, horizon, model=model)
    equity = proj["ev"] + model.get("net_cash", 0.0)   # net_cash negative if net debt
    shares = model["shares_diluted"]
    per_share = equity / shares if shares else None
    return {"per_share": per_share, "equity_value": equity, **proj}


def reverse_dcf(model: dict, current_price: float, solve_driver: str = "revenue_cagr",
                lo: float = -0.30, hi: float = 0.80) -> dict:
    """Solve the value of `solve_driver` (default revenue CAGR) that makes the DCF
    equal the current price — i.e. what the market is implying. In bridge mode the
    segmented top line is collapsed to its base-year net revenue and a single
    uniform net-revenue CAGR is solved, so the output stays the familiar 'market
    implies X% growth' figure."""
    base = M.apply_scenario(model, "base")
    rev_model = model
    if M.has_bridge(model):
        net0 = _bridge_net_revenue(model, base, 0)
        base = dict(base, revenue_0=net0)                       # add simple anchor
        rev_model = {k: v for k, v in model.items() if k != "revenue_bridge"}

    def price_at(x):
        dd = dict(base)
        dd[solve_driver] = x
        return value_per_share(rev_model, dd)["per_share"]

    p_lo, p_hi = price_at(lo), price_at(hi)
    if p_lo is None or p_hi is None or (p_lo - current_price) * (p_hi - current_price) > 0:
        return {"driver": solve_driver, "implied": None,
                "note": f"no root in [{lo},{hi}] (price not bracketed)"}
    for _ in range(60):
        mid = (lo + hi) / 2
        pm = price_at(mid)
        if (p_lo - current_price) * (pm - current_price) <= 0:
            hi = mid
        else:
            lo, p_lo = mid, pm
    return {"driver": solve_driver, "implied": round((lo + hi) / 2, 4)}


def run_scenarios(model: dict) -> dict:
    out = {}
    derived = {}
    for s in ("bull", "base", "bear"):
        dvals = M.apply_scenario(model, s)
        v = value_per_share(model, dvals)
        out[s] = round(v["per_share"], 2)
        if v.get("derived_revenue_cagr") is not None:
            derived[s] = round(v["derived_revenue_cagr"], 4)
    probs = model.get("probabilities")
    if probs:
        weighted = sum(out[s] * probs.get(s, 0) for s in ("bull", "base", "bear"))
        out["weighted"] = round(weighted, 2)
        cur = model.get("current_price")
        if cur:
            out["weighted_return"] = round((weighted - cur) / cur, 4)
            out["bear_to_current"] = round(out["bear"] / cur, 4)
    if M.has_bridge(model):
        # surface the DERIVED blended CAGR per scenario — the Bear CAGR is now an
        # output of the segment assumptions, not a hand-filled number.
        out["derived_cagr"] = derived
    return out


def _default_sensitivity_driver(model: dict, requested: str) -> str:
    """In bridge mode 'revenue_cagr' does not exist; fall back to the first
    segment's growth driver so a 1-D sweep is still meaningful."""
    base = M.apply_scenario(model, "base")
    if requested in base:
        return requested
    if M.has_bridge(model):
        seg = model["revenue_bridge"]["segments"][0]
        name = seg["name"]
        return M.seg_key(name, "volume_growth" if seg.get("mode") == "volume_yield" else "cagr")
    return requested


def sensitivity(model: dict, driver: str, span: float = 0.03, steps: int = 5) -> list:
    """Sweep a base-case driver ± span and report per-share — the 'living model' view."""
    base = M.apply_scenario(model, "base")
    driver = _default_sensitivity_driver(model, driver)
    center = base[driver]
    out = []
    for i in range(steps):
        x = center - span + (2 * span) * i / (steps - 1)
        dd = dict(base)
        dd[driver] = x
        out.append({driver: round(x, 4), "per_share": round(value_per_share(model, dd)["per_share"], 2)})
    return out


def sensitivity_2d(model: dict, driver_x: str, driver_y: str,
                   span_x: float = 0.03, span_y: float = 0.01, steps: int = 5) -> dict:
    """2-D sensitivity grid of per-share over driver_x × driver_y (e.g.
    revenue_cagr × wacc, or revenue_cagr × terminal_growth — the latter is how
    'growth × terminal multiple' is varied, since the multiple is derived from g).
    A single-point DCF hides this surface; the grid shows how fragile the target is."""
    base = M.apply_scenario(model, "base")
    dx = _default_sensitivity_driver(model, driver_x)
    dy = driver_y
    cx, cy = base[dx], base[dy]
    xs = [round(cx - span_x + (2 * span_x) * i / (steps - 1), 4) for i in range(steps)]
    ys = [round(cy - span_y + (2 * span_y) * j / (steps - 1), 4) for j in range(steps)]
    grid = []
    for yv in ys:
        row = []
        for xv in xs:
            dd = dict(base)
            dd[dx] = xv
            dd[dy] = yv
            row.append(round(value_per_share(model, dd)["per_share"], 2))
        grid.append(row)
    return {"driver_x": dx, "driver_y": dy, "x_values": xs, "y_values": ys, "grid": grid}


def run(model: dict, sensitivity_driver: str = "revenue_cagr", sensitivity2d: tuple = None) -> dict:
    v = M.validate_model(model)
    if not v["ok"]:
        return {"ok": False, "errors": v["errors"]}
    horizon = model.get("horizon_years", 5)
    result = {
        "ok": True,
        "provenance": v["provenance"],
        "warnings": v["warnings"],
        "base_target": round(value_per_share(model, M.apply_scenario(model, "base"))["per_share"], 2),
        "scenarios": run_scenarios(model),
        "derived_terminal_ev_fcf": round(_project(M.apply_scenario(model, "base"), horizon,
                                                   model=model)["terminal_ev_fcf"], 2),
        "sensitivity": sensitivity(model, sensitivity_driver),
    }
    if sensitivity2d:
        result["sensitivity_2d"] = sensitivity_2d(model, sensitivity2d[0], sensitivity2d[1])
    if model.get("current_price"):
        result["reverse_dcf"] = reverse_dcf(model, model["current_price"])
    # false-precision verdict
    prov = v["provenance"]
    if prov["anchor_assumed"]:
        result["grounding"] = (f"LOW: {len(prov['anchor_assumed'])}/{prov['anchors_total']} anchor "
                               f"drivers are assumptions ({prov['anchor_assumed']}) — treat as "
                               f"illustrative, not analytical")
    else:
        result["grounding"] = f"OK: all {prov['anchors_total']} anchor drivers data-grounded"
    return result


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="finlib driver-based valuation")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--model", required=True)
    r.add_argument("--sensitivity", default="revenue_cagr")
    r.add_argument("--sensitivity2d", help="two driver names 'x,y' for a 2-D grid, e.g. revenue_cagr,wacc")
    r.add_argument("--out")
    args = ap.parse_args(argv)

    with open(args.model, encoding="utf-8") as f:
        model = json.load(f)
    s2d = tuple(p.strip() for p in args.sensitivity2d.split(",")) if args.sensitivity2d else None
    res = run(model, args.sensitivity, sensitivity2d=s2d)
    txt = json.dumps(res, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(txt)
    print(txt)
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())