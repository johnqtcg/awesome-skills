"""finlib.calibration — make the Calibration Loop executable instead of aspirational.

``scenario-probability-calibration.md`` asks for "average Bull probability
assigned" vs "frequency of Bull validation 12 months later". Under schema v2 that
was uncomputable: the log stored no probabilities at all. Schema v3 stores them,
and this module does the arithmetic — so the framework's probabilities can be
audited against outcomes rather than merely described as calibratable.

Honest framing: this computes a **realised-outcome comparison against assigned
probabilities**. Until enough matured verdicts accumulate, the archetype priors in
``scenario-probability-calibration.md`` remain judgment priors. This tool reports
how many matured verdicts exist so a reader can see whether any conclusion is yet
supportable, rather than presenting a 3-verdict sample as calibration.

Scenario realisation for a matured verdict, from the price on the review date:
  price >= target_bull            -> bull
  price <= target_bear            -> bear
  otherwise                       -> base

CLI:
    python3 calibration.py report --prices prices.json [--log <path>] [--as-of 2026-08-19]
    # prices.json: {"AAPL": 231.4, "MSFT": 502.1}   -- current price per ticker
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date

try:
    from . import verdictlog as VL
except ImportError:  # direct CLI invocation
    import verdictlog as VL  # type: ignore

read = VL.read
resolve_path = VL.resolve_path

# A verdict is "matured" once this much of its horizon has elapsed. Below it,
# the scenario has not had time to play out and scoring it is noise.
MATURITY_FRACTION = 0.33
MIN_MATURED_FOR_CONCLUSION = 10


def _parse_date(value: str) -> date | None:
    try:
        parts = [int(p) for p in str(value).split("-")[:3]]
        return date(*parts) if len(parts) == 3 else None
    except (ValueError, TypeError):
        return None


def _realised(price: float, entry: dict) -> str | None:
    bull, bear = entry.get("target_bull"), entry.get("target_bear")
    if not isinstance(bull, (int, float)) or not isinstance(bear, (int, float)):
        return None
    if price >= bull:
        return "bull"
    if price <= bear:
        return "bear"
    return "base"


def report(entries: list[dict], prices: dict[str, float], as_of: date) -> dict:
    scored: list[dict] = []
    unmatured, unpriced, unscorable = [], [], []

    for entry in entries:
        ticker = str(entry.get("ticker", "")).upper()
        verdict_date = _parse_date(entry.get("verdict_date", ""))
        horizon = entry.get("horizon_months")
        if verdict_date is None or not isinstance(horizon, (int, float)):
            unscorable.append({"ticker": ticker, "reason": "unparseable verdict_date or horizon_months"})
            continue
        elapsed_months = (as_of - verdict_date).days / 30.44
        if elapsed_months < horizon * MATURITY_FRACTION:
            unmatured.append({
                "ticker": ticker, "verdict_date": entry.get("verdict_date"),
                "elapsed_months": round(elapsed_months, 1), "horizon_months": horizon,
            })
            continue
        if ticker not in prices:
            unpriced.append({"ticker": ticker, "verdict_date": entry.get("verdict_date")})
            continue
        probs = {k: entry.get(f"prob_{k}") for k in ("bull", "base", "bear")}
        if any(not isinstance(v, (int, float)) or isinstance(v, bool) for v in probs.values()):
            unscorable.append({
                "ticker": ticker, "verdict_date": entry.get("verdict_date"),
                "reason": "no assigned probabilities on this entry"
                          f" (schema_version {entry.get('schema_version')})",
            })
            continue
        outcome = _realised(prices[ticker], entry)
        if outcome is None:
            unscorable.append({"ticker": ticker, "reason": "missing target_bull/target_bear"})
            continue
        scored.append({
            "ticker": ticker,
            "verdict_date": entry.get("verdict_date"),
            "archetype": entry.get("archetype"),
            "verdict": entry.get("verdict"),
            "elapsed_months": round(elapsed_months, 1),
            "price_at_review": prices[ticker],
            "assigned": probs,
            "realised": outcome,
        })

    n = len(scored)
    out: dict = {
        "as_of": as_of.isoformat(),
        "entries_in_log": len(entries),
        "matured_and_scored": n,
        "min_matured_for_conclusion": MIN_MATURED_FOR_CONCLUSION,
        "unmatured": unmatured,
        "unpriced": unpriced,
        "unscorable": unscorable,
        "scored": scored,
    }

    if not n:
        out["conclusion"] = (
            "No matured, priced, probability-bearing verdicts. Nothing is calibrated yet;"
            " the archetype figures remain judgment priors."
        )
        return out

    for scenario in ("bull", "base", "bear"):
        assigned = sum(s["assigned"][scenario] for s in scored) / n
        realised = sum(1 for s in scored if s["realised"] == scenario) / n
        out[scenario] = {
            "mean_assigned": round(assigned, 4),
            "realised_frequency": round(realised, 4),
            "gap_pp": round((realised - assigned) * 100, 1),
        }

    by_archetype: dict[str, dict] = {}
    for s in scored:
        bucket = by_archetype.setdefault(str(s.get("archetype")), {"n": 0, "assigned_bull": 0.0, "realised_bull": 0})
        bucket["n"] += 1
        bucket["assigned_bull"] += s["assigned"]["bull"]
        bucket["realised_bull"] += 1 if s["realised"] == "bull" else 0
    for name, bucket in by_archetype.items():
        count = bucket["n"]
        bucket["mean_assigned_bull"] = round(bucket.pop("assigned_bull") / count, 4)
        bucket["realised_bull_frequency"] = round(bucket.pop("realised_bull") / count, 4)
        bucket["gap_pp"] = round(
            (bucket["realised_bull_frequency"] - bucket["mean_assigned_bull"]) * 100, 1
        )
    out["by_archetype"] = by_archetype

    bull_gap = out["bull"]["gap_pp"]
    if n < MIN_MATURED_FOR_CONCLUSION:
        out["conclusion"] = (
            f"Only {n} matured verdict(s) — below the {MIN_MATURED_FOR_CONCLUSION}-verdict floor."
            " Report the numbers, but do NOT revise the archetype priors on this sample."
        )
    elif bull_gap <= -10:
        out["conclusion"] = (
            f"Bull realised {bull_gap:+.1f}pp vs assigned: systematic over-optimism."
            " Lower the archetype Bull priors in scenario-probability-calibration.md."
        )
    elif bull_gap >= 10:
        out["conclusion"] = (
            f"Bull realised {bull_gap:+.1f}pp vs assigned: systematic under-optimism."
            " Raise the archetype Bull priors."
        )
    else:
        out["conclusion"] = (
            f"Bull gap {bull_gap:+.1f}pp, within ±10pp on {n} verdicts. No revision indicated."
        )
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="calibration report over the verdict log")
    ap.add_argument("--log")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("report")
    r.add_argument("--prices", required=True, help="JSON map of ticker -> current price")
    r.add_argument("--as-of", help="ISO date; defaults to today")
    args = ap.parse_args(argv)

    with open(args.prices, encoding="utf-8") as f:
        prices = {str(k).upper(): float(v) for k, v in json.load(f).items()}
    as_of = _parse_date(args.as_of) if args.as_of else date.today()
    if as_of is None:
        print(json.dumps({"error": f"unparseable --as-of {args.as_of!r}"}), file=sys.stderr)
        return 2

    entries = read(resolve_path(args.log))
    print(json.dumps(report(entries, prices, as_of), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
