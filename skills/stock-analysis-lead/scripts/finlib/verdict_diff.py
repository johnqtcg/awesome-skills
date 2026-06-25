"""finlib.verdict_diff — Edge B: event-driven monitoring off the verdict log.

On a new filing/transcript, re-run the analysis and diff the new verdict entry
against the prior one for the same ticker. Surfaces what changed — verdict,
targets, price vs buy-triggers, and which bull/bear assumptions were added or
dropped — faster and more consistently than a human re-reading an old note.

CLI:
    python3 verdict_diff.py --prev prior.json --new current.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys


def _num(x):
    return x if isinstance(x, (int, float)) else None


def diff(prev: dict, new: dict) -> dict:
    out: dict = {"ticker": new.get("ticker"), "changes": [], "assumption_breaks": []}

    # verdict
    if prev.get("verdict") != new.get("verdict"):
        out["changes"].append(f"verdict: {prev.get('verdict')} -> {new.get('verdict')}")

    # price + targets
    for k in ("current_price", "target_base", "target_bull", "target_bear",
              "weighted_return_36mo", "bear_to_current_ratio", "good_company_score"):
        a, b = _num(prev.get(k)), _num(new.get(k))
        if a is not None and b is not None and a != b:
            pct = f" ({(b - a) / abs(a):+.1%})" if a else ""
            out["changes"].append(f"{k}: {a} -> {b}{pct}")

    # did price cross a buy-trigger mentioned in invalidation_triggers?
    cur = _num(new.get("current_price"))
    for trig in new.get("invalidation_triggers", []):
        m = re.search(r"<?=?\s*\$?(\d[\d,]*)", str(trig))
        if cur is not None and m and ("BUY" in str(trig).upper() or "买入" in str(trig)):
            level = float(m.group(1).replace(",", ""))
            if cur <= level:
                out["changes"].append(f"PRICE {cur} crossed buy-trigger ~{level:g}: {trig}")

    # assumption set changes (added / dropped)
    for field in ("key_bull_assumptions", "key_bear_assumptions"):
        a = set(prev.get(field, []))
        b = set(new.get(field, []))
        for added in sorted(b - a):
            out["assumption_breaks"].append(f"[{field}] ADDED: {added}")
        for dropped in sorted(a - b):
            out["assumption_breaks"].append(f"[{field}] DROPPED: {dropped}")

    out["material"] = bool(out["changes"] or out["assumption_breaks"])
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="diff two verdict-log entries")
    ap.add_argument("--prev", required=True)
    ap.add_argument("--new", required=True)
    args = ap.parse_args(argv)
    with open(args.prev, encoding="utf-8") as f:
        prev = json.load(f)
    with open(args.new, encoding="utf-8") as f:
        new = json.load(f)
    print(json.dumps(diff(prev, new), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())