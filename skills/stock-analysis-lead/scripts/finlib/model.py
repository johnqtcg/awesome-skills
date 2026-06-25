"""finlib.model — driver-based financial model schema + the false-precision guardrail.

A model is a set of *drivers*, each carrying a `source` that is either:
    {"kind": "data",       "ref":  "financials.json:revenue@FY2025"}   # first-hand
    {"kind": "assumption", "note": "Azure-led; consensus ~12%"}        # a forward guess

The guardrail has two teeth:
  1. Hard refusal — `validate_model` rejects any model with a driver that has no
     source at all. You may not slip an un-sourced number into a DCF.
  2. Anchor grounding — the *base/anchor* drivers (the starting point: current
     revenue, starting margin, D&A%, capex%, shares, net cash) SHOULD be data
     from financials.json. Forward drivers (growth, terminal margin, WACC,
     terminal growth) are legitimately assumptions. If an ANCHOR is only an
     assumption, that is the "DCF on guesses" trap — `anchor_grounding` flags it
     and valuation prints a prominent LOW-GROUNDING warning.

Pure Python, no dependencies. $ figures in USD billions; margins/rates as fractions.
"""
from __future__ import annotations

# Drivers that MUST exist for a valuation.
REQUIRED_DRIVERS = [
    "revenue_0", "revenue_cagr", "op_margin_start", "op_margin_terminal",
    "tax_rate", "da_pct", "capex_pct", "wacc", "terminal_growth",
]
# Anchors that SHOULD be data-grounded (the starting point, not the forecast).
ANCHOR_DRIVERS = {"revenue_0", "op_margin_start", "da_pct", "capex_pct"}
# Forward drivers for which "assumption" is the expected, honest source kind.
FORWARD_DRIVERS = {"revenue_cagr", "op_margin_terminal", "wacc", "terminal_growth"}

# ---------------------------------------------------------------------------
# Bottom-up revenue bridge (optional). When `model["revenue_bridge"]` is present
# the top line is built from segments (each grown by its own CAGR, or by a
# volume_growth × yield_growth pair) minus a contra-revenue line (client
# incentives / rebates), instead of a single typed revenue_cagr. This lets a
# Bear case be DERIVED ("cross-border volume −20% while VAS +20%") rather than a
# hand-filled blended CAGR. Segment/contra leaves live as flat drivers under
# `drivers` with dotted names, so the source guardrail and scenario overrides
# (override "seg.cross_border.volume_growth" in the bear scenario) work unchanged.
# ---------------------------------------------------------------------------

CONTRA_PCT = "contra.pct_of_gross"
CONTRA_PCT_TERMINAL = "contra.pct_of_gross_terminal"


def has_bridge(model: dict) -> bool:
    return bool(model.get("revenue_bridge", {}).get("segments"))


def seg_key(name: str, field: str) -> str:
    return f"seg.{name}.{field}"


def bridge_required_drivers(model: dict) -> list:
    """Flat driver names the bridge needs to exist (with sources)."""
    req: list = []
    br = model.get("revenue_bridge", {})
    for seg in br.get("segments", []):
        name = seg["name"]
        req.append(seg_key(name, "revenue_0"))
        if seg.get("mode") == "volume_yield":
            req += [seg_key(name, "volume_growth"), seg_key(name, "yield_growth")]
        else:
            req.append(seg_key(name, "cagr"))
    if br.get("contra"):
        req.append(CONTRA_PCT)   # terminal is optional (defaults to constant)
    return req


def _required_drivers(model: dict) -> list:
    if not has_bridge(model):
        return REQUIRED_DRIVERS
    # revenue_0 / revenue_cagr become DERIVED from the bridge; the rest stand.
    keep = [d for d in REQUIRED_DRIVERS if d not in ("revenue_0", "revenue_cagr")]
    return keep + bridge_required_drivers(model)


def _anchor_drivers(model: dict) -> set:
    if not has_bridge(model):
        return ANCHOR_DRIVERS
    # the segments' starting revenues are the data anchors in bridge mode
    seg_anchors = {seg_key(s["name"], "revenue_0") for s in model["revenue_bridge"]["segments"]}
    return (ANCHOR_DRIVERS - {"revenue_0"}) | seg_anchors


def dv(model: dict, name: str):
    """Driver value."""
    return model["drivers"][name]["value"]


def _source(driver: dict) -> dict:
    return driver.get("source") or {}


def validate_model(model: dict) -> dict:
    """Return {ok, errors, warnings, provenance}. ok=False means do NOT value it."""
    errors: list = []
    warnings: list = []
    drivers = model.get("drivers", {})
    anchors = _anchor_drivers(model)

    for req in _required_drivers(model):
        if req not in drivers:
            errors.append(f"missing required driver: {req}")

    data_grounded, assumptions, unsourced = [], [], []
    for name, d in drivers.items():
        if "value" not in d:
            errors.append(f"driver '{name}' has no value")
        src = _source(d)
        kind = src.get("kind")
        if kind not in ("data", "assumption"):
            # GUARDRAIL TOOTH 1: no un-sourced numbers allowed
            unsourced.append(name)
            errors.append(f"driver '{name}' has no source (kind must be 'data' or 'assumption') "
                          f"— un-sourced numbers may not enter a DCF")
        elif kind == "data":
            data_grounded.append(name)
        else:
            assumptions.append(name)

    # GUARDRAIL TOOTH 2: anchors that are only assumptions
    anchor_assumed = [n for n in anchors if n in drivers
                      and _source(drivers[n]).get("kind") == "assumption"]
    for n in anchor_assumed:
        warnings.append(f"ANCHOR driver '{n}' is an assumption, not data — the model's starting "
                        f"point is guessed; ground it in financials.json or treat the valuation as "
                        f"illustrative, not analytical")

    # economic sanity
    if "wacc" in drivers and "terminal_growth" in drivers:
        if dv(model, "wacc") <= dv(model, "terminal_growth"):
            errors.append("wacc <= terminal_growth — Gordon terminal value diverges/negative")

    provenance = {
        "data_grounded": data_grounded,
        "assumptions": assumptions,
        "unsourced": unsourced,
        "anchor_assumed": anchor_assumed,
        "anchors_total": len([n for n in anchors if n in drivers]),
        "anchors_data": len([n for n in anchors if n in drivers
                             and _source(drivers[n]).get("kind") == "data"]),
    }
    return {"ok": not errors, "errors": errors, "warnings": warnings, "provenance": provenance}


def apply_scenario(model: dict, scenario: str) -> dict:
    """Return a driver dict with the named scenario's overrides applied (values only)."""
    base = {k: v["value"] for k, v in model["drivers"].items()}
    overrides = model.get("scenarios", {}).get(scenario, {})
    base.update(overrides)
    return base