"""finlib.crosssection — Edge A: breadth / cross-section dislocation finder.

A human desk covers ~10-20 names and can't hold 30 live models at once. This runs
the same metrics across a whole book and surfaces RELATIVE dislocations a narrow
human view structurally misses. It does not black-box a single score — it ranks
per metric and flags the gaps, leaving judgment to the reader.

Input: a list of entries (or a verdicts.jsonl), each with at least:
    ticker, weighted_return_36mo, bear_to_current_ratio, good_company_score
  optional: implied_growth (reverse-DCF), delivered_growth (trailing)

CLI:
    python3 crosssection.py rank --book verdicts.jsonl
    python3 crosssection.py rank --entries entries.json
"""
from __future__ import annotations

import argparse
import json
import sys


def _rank_desc(entries: list, key: str) -> dict:
    """ticker -> 1-based rank by `key` descending (None sorts last)."""
    vals = [(e["ticker"], e.get(key)) for e in entries]
    ordered = sorted(vals, key=lambda kv: (kv[1] is None, -(kv[1] or 0)))
    return {tk: i + 1 for i, (tk, _) in enumerate(ordered)}


def analyze(entries: list) -> dict:
    n = len(entries)
    by_return = _rank_desc(entries, "weighted_return_36mo")
    by_downside = _rank_desc(entries, "bear_to_current_ratio")
    by_quality = _rank_desc(entries, "good_company_score")

    rows = []
    for e in entries:
        tk = e["ticker"]
        implied = e.get("implied_growth")
        delivered = e.get("delivered_growth")
        gap = (implied - delivered) if (implied is not None and delivered is not None) else None
        rows.append({
            "ticker": tk,
            "weighted_return_36mo": e.get("weighted_return_36mo"),
            "bear_to_current_ratio": e.get("bear_to_current_ratio"),
            "good_company_score": e.get("good_company_score"),
            "rank_return": by_return[tk],
            "rank_downside": by_downside[tk],
            "rank_quality": by_quality[tk],
            "rank_sum": by_return[tk] + by_downside[tk] + by_quality[tk],
            "implied_minus_delivered_growth": round(gap, 4) if gap is not None else None,
        })
    rows.sort(key=lambda r: r["rank_sum"])  # best all-round first

    flags = []
    for r in rows:
        # best risk/reward: top-tier return AND top-tier downside protection
        if r["rank_return"] <= max(1, n // 3) and r["rank_downside"] <= max(1, n // 3):
            flags.append(f"{r['ticker']}: best risk/reward (return rank {r['rank_return']}, "
                         f"downside rank {r['rank_downside']})")
        g = r["implied_minus_delivered_growth"]
        if g is not None and g >= 0.05:
            flags.append(f"{r['ticker']}: market implies +{g:.0%} growth ABOVE delivered — priced for "
                         f"acceleration not yet shown (caution)")
        if g is not None and g <= -0.05:
            flags.append(f"{r['ticker']}: market implies {g:.0%} growth BELOW delivered — possible "
                         f"value if thesis intact")
    return {"n": n, "ranked": rows, "dislocations": flags,
            "best_all_round": rows[0]["ticker"] if rows else None}


def _load_book(path: str) -> list:
    """Load the latest entry per ticker from a verdicts.jsonl book."""
    latest: dict = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            e = json.loads(line)
            latest[e["ticker"]] = e  # later line wins
    return list(latest.values())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="cross-section dislocation finder")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("rank")
    r.add_argument("--book", help="verdicts.jsonl")
    r.add_argument("--entries", help="json list of entries")
    args = ap.parse_args(argv)

    if args.book:
        entries = _load_book(args.book)
    elif args.entries:
        with open(args.entries, encoding="utf-8") as f:
            entries = json.load(f)
    else:
        print("need --book or --entries", file=sys.stderr)
        return 2
    print(json.dumps(analyze(entries), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())