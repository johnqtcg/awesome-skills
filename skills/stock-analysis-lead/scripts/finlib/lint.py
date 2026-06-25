"""finlib.lint — 口径 / consistency / single-period linter.

Moves arithmetic and label discipline OUT of the LLM's head into deterministic
checks. Consumes a `metrics.json` produced by the orchestrator and returns a
list of findings; any FAIL blocks the report (or forces a correction).

metrics.json schema — a list of metric entries:
    {
      "id": "ev_fcf",                  # canonical ratio id (see ratios.RATIO_FUNCS)
      "claimed_label": "EV/FCF",       # how the report LABELS it
      "stated_value": 44.0,            # the number the report prints
      "inputs": {"mktcap": 3150, "total_debt": 50, "cash_and_sti": 110, "fcf": 71.6},
      "tags": {"basis": "gaap", "period": "ttm", "period_count": 1},
      "kind": "valuation_multiple",    # optional hint
      "is_trend_claim": false          # set true for "trend/leverage accelerating" style claims
    }

Run:
    python3 lint.py --metrics metrics.json            # exit 1 if any FAIL
    python3 lint.py --metrics metrics.json --json out.json
"""
from __future__ import annotations

import argparse
import inspect
import json
import sys

try:
    from . import ratios
except ImportError:  # allow running as a script
    import ratios  # type: ignore

REL_TOL = 0.02  # 2% tolerance between stated and recomputed value
# Labels that imply an enterprise-value numerator.
_EV_LABEL_TOKENS = ("ev/", "ev /", "enterprise value", "ev-to", "ev to")


def _finding(level: str, metric_id: str, msg: str) -> dict:
    return {"level": level, "metric": metric_id, "message": msg}


def _recompute(entry: dict):
    """Recompute the metric from its inputs using the canonical ratio function."""
    fn = ratios.RATIO_FUNCS.get(entry.get("id"))
    if fn is None:
        return None, "no canonical function for id"
    params = inspect.signature(fn).parameters
    inputs = entry.get("inputs", {})
    missing = [p for p in params if p not in inputs]
    if missing:
        return None, f"missing inputs {missing}"
    try:
        return fn(**{p: inputs[p] for p in params})["value"], None
    except Exception as e:  # noqa: BLE001
        return None, f"recompute error: {e}"


def check_recompute(entry: dict) -> list:
    """FAIL if stated value disagrees with the value recomputed from inputs."""
    out = []
    stated = entry.get("stated_value")
    canon, err = _recompute(entry)
    if err:
        out.append(_finding("WARN", entry.get("id", "?"),
                            f"cannot verify: {err} — number is unverified, not first-hand"))
        return out
    if stated is None or canon is None:
        return out
    denom = abs(canon) if canon else 1.0
    if abs(stated - canon) / denom > REL_TOL:
        out.append(_finding("FAIL", entry.get("id", "?"),
                            f"stated {stated:g} but recomputes to {canon:.4g} from its own inputs "
                            f"(>{REL_TOL:.0%} off) — internal inconsistency"))
    return out


def check_ev_label(entry: dict) -> list:
    """FAIL if a metric is LABELED as an EV multiple but was computed off market cap
    (i.e., no debt/cash supplied) — the EV/FCF-vs-P/FCF error."""
    out = []
    label = str(entry.get("claimed_label", "")).lower()
    looks_ev = any(tok in label for tok in _EV_LABEL_TOKENS)
    inputs = entry.get("inputs", {})
    has_ev_components = ("total_debt" in inputs and "cash_and_sti" in inputs)
    if looks_ev and not has_ev_components:
        out.append(_finding("FAIL", entry.get("id", "?"),
                            f"labeled '{entry.get('claimed_label')}' (an EV multiple) but inputs lack "
                            f"total_debt/cash_and_sti — this computes a PRICE multiple (e.g. P/FCF), not EV. "
                            f"EV = mktcap + debt - cash."))
    # also catch: id is a price multiple but label claims EV
    if looks_ev and entry.get("id") in ("pfcf", "ps", "pe"):
        out.append(_finding("FAIL", entry.get("id", "?"),
                            f"id '{entry.get('id')}' is a price multiple but labeled '{entry.get('claimed_label')}' (EV)."))
    return out


def check_single_period(entry: dict) -> list:
    """FAIL trend/operating-leverage claims that rest on a single period."""
    out = []
    if entry.get("is_trend_claim") or entry.get("kind") in ("trend", "operating_leverage"):
        pc = entry.get("tags", {}).get("period_count")
        if pc is not None and pc < 4:
            out.append(_finding("FAIL", entry.get("id", "?"),
                                f"trend/operating-leverage claim rests on {pc} period(s); require >=4 "
                                f"(or TTM) — single-quarter YoY is polluted by one-offs / SBC / depreciation timing"))
    return out


def check_unit_tags(entry: dict) -> list:
    """WARN if a derived multiple mixes incompatible bases (e.g. non-GAAP EPS over
    GAAP price, or a 'core' numerator with TTM denominator) without flagging it."""
    out = []
    tags = entry.get("tags", {})
    mixed = tags.get("mixed_basis")
    if mixed:
        out.append(_finding("WARN", entry.get("id", "?"),
                            f"mixes bases {mixed} — confirm口径 alignment (GAAP vs non-GAAP vs core; "
                            f"TTM vs FY; cash capex vs incl. finance leases)"))
    return out


# Labels/kinds that denote an operating-leverage or margin-bridge claim.
_OPLEV_LABEL_TOKENS = ("operating leverage", "operating-leverage", "op leverage", "经营杠杆", "杠杆")
# Headline margins whose GAAP/adjusted gap routinely moves cross-year comparisons.
_HEADLINE_MARGIN_IDS = {"operating_margin", "fcf_margin", "net_margin", "gross_margin"}


def _is_operating_leverage(entry: dict) -> bool:
    if entry.get("kind") == "operating_leverage":
        return True
    label = str(entry.get("claimed_label", "")).lower()
    return any(tok in label for tok in _OPLEV_LABEL_TOKENS)


def check_definition(entry: dict) -> list:
    """FAIL an operating-leverage / margin-bridge claim that cannot be recomputed
    from its inputs. 'Operating leverage +X pp' is ambiguous: margin expansion
    (margin_delta_pp), the revenue-minus-opex growth gap (operating_leverage_pp),
    or the %ΔOpInc/%ΔRev ratio (dol) are three different numbers. A bare figure
    with no declared, recomputable definition is unauditable."""
    out = []
    if not _is_operating_leverage(entry):
        return out
    _, err = _recompute(entry)
    if err:
        out.append(_finding("FAIL", entry.get("id", "?"),
                            f"operating-leverage claim '{entry.get('claimed_label')}' is not recomputable "
                            f"({err}) — declare the definition: operating_leverage_pp "
                            f"(revenue_growth_pp − opex_growth_pp), margin_delta_pp (margin_end − margin_start), "
                            f"or dol (%ΔOpInc/%ΔRev), and supply its inputs. A bare '+X pp' is unauditable."))
    return out


def check_basis_reconciliation(entry: dict) -> list:
    """Headline margins reported on ONE basis (GAAP or adjusted/non-GAAP/core)
    need an explicit reconciliation marker. GAAP and adjusted margins diverge via
    Special Items / SBC; a cross-year comparison on an unreconciled basis misleads.
    WARN for a single snapshot; FAIL when the claim is also a trend (cross-year)
    claim — that is where the unreconciled basis actually bites. Set
    tags.basis_reconciled, or supply both tags.gaap_value and tags.adjusted_value,
    to clear it."""
    out = []
    if entry.get("id") not in _HEADLINE_MARGIN_IDS:
        return out
    tags = entry.get("tags", {})
    basis = str(tags.get("basis", "")).lower()
    if basis not in ("gaap", "adjusted", "non-gaap", "core"):
        return out
    reconciled = bool(tags.get("basis_reconciled")) or (
        "gaap_value" in tags and "adjusted_value" in tags)
    if reconciled:
        return out
    level = "FAIL" if (entry.get("is_trend_claim") or entry.get("kind") == "trend") else "WARN"
    out.append(_finding(level, entry.get("id", "?"),
                        f"headline margin '{entry.get('claimed_label')}' stated on '{basis}' basis only — "
                        f"show the GAAP↔adjusted bridge (Special Items / SBC) or set tags.basis_reconciled. "
                        f"Cross-year comparison on a single basis can be distorted by one-offs."))
    return out


CHECKS = [check_recompute, check_ev_label, check_single_period, check_unit_tags,
          check_definition, check_basis_reconciliation]


def lint(metrics: list) -> list:
    findings = []
    for entry in metrics:
        for chk in CHECKS:
            findings.extend(chk(entry))
    return findings


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="finlib 口径/consistency linter")
    ap.add_argument("--metrics", required=True, help="path to metrics.json")
    ap.add_argument("--json", help="optional path to write findings json")
    args = ap.parse_args(argv)

    with open(args.metrics, encoding="utf-8") as f:
        metrics = json.load(f)
    if isinstance(metrics, dict):
        metrics = metrics.get("metrics", [])

    findings = lint(metrics)
    fails = [f for f in findings if f["level"] == "FAIL"]
    warns = [f for f in findings if f["level"] == "WARN"]

    for f in findings:
        print(f"[{f['level']}] {f['metric']}: {f['message']}")
    print(f"\n{len(fails)} FAIL, {len(warns)} WARN over {len(metrics)} metrics")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump({"findings": findings, "fail": len(fails), "warn": len(warns)}, f, indent=2)

    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())