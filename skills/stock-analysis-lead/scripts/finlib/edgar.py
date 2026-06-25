"""finlib.edgar — SEC EDGAR first-hand data pipeline.

Replaces second-hand aggregator scraping (stockanalysis.com mirrors) with the
canonical XBRL `companyfacts` API, so workers read primary, structured,
filing-sourced numbers — including the figures search snippets never surface
(segment operating income, AR + allowance, deferred revenue, RPO).

Network note: live fetch hits data.sec.gov (requires network + a descriptive
User-Agent per SEC fair-access policy). In a sandboxed run without network,
use --facts <cached.json> to parse an already-downloaded companyfacts file.
The *parsing* layer (concept_series / extract_financials) is pure and fully
unit-tested offline.

CLI:
    python3 edgar.py fetch --ticker MSFT --out financials.json
    python3 edgar.py fetch --cik 0000789019 --out financials.json
    python3 edgar.py parse --facts companyfacts.json --out financials.json
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Optional
from urllib.request import Request, urlopen

SEC_UA = "stock-analysis-lead research (contact: set-your-email@example.com)"
TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10}.json"

# Canonical concept → list of candidate XBRL tags (filers differ). First hit wins.
CONCEPT_MAP = {
    "revenue": [("us-gaap", "RevenueFromContractWithCustomerExcludingAssessedTax"),
                ("us-gaap", "Revenues"),
                ("us-gaap", "SalesRevenueNet")],
    "operating_income": [("us-gaap", "OperatingIncomeLoss")],
    "net_income": [("us-gaap", "NetIncomeLoss")],
    "ocf": [("us-gaap", "NetCashProvidedByUsedInOperatingActivities")],
    "capex": [("us-gaap", "PaymentsToAcquirePropertyPlantAndEquipment"),
              ("us-gaap", "PaymentsToAcquireProductiveAssets")],
    "dep_amort": [("us-gaap", "DepreciationDepletionAndAmortization"),
                  ("us-gaap", "DepreciationAmortizationAndAccretionNet")],
    "sbc": [("us-gaap", "ShareBasedCompensation")],
    "accounts_receivable": [("us-gaap", "AccountsReceivableNetCurrent")],
    "allowance_doubtful": [("us-gaap", "AllowanceForDoubtfulAccountsReceivableCurrent")],
    "deferred_revenue": [("us-gaap", "ContractWithCustomerLiabilityCurrent"),
                         ("us-gaap", "DeferredRevenueCurrent")],
    "rpo": [("us-gaap", "RevenueRemainingPerformanceObligation")],
    "shares_diluted": [("us-gaap", "WeightedAverageNumberOfDilutedSharesOutstanding")],
    "total_debt": [("us-gaap", "LongTermDebtNoncurrent"), ("us-gaap", "LongTermDebt")],
    "cash_and_sti": [("us-gaap", "CashCashEquivalentsAndShortTermInvestments"),
                     ("us-gaap", "CashAndCashEquivalentsAtCarryingValue")],
    # Segment operating income is dimensional (per-segment members) and not a
    # single top-level concept; we surface it as a gap unless a filer tags a flat
    # concept, prompting the worker to read the segment FOOTNOTE directly.
    "segment_operating_income": [("us-gaap", "__segment_dimensional__")],
}


def _get(url: str) -> bytes:
    req = Request(url, headers={"User-Agent": SEC_UA, "Accept-Encoding": "gzip, deflate"})
    with urlopen(req, timeout=30) as r:  # noqa: S310 (trusted SEC host)
        data = r.read()
    if data[:2] == b"\x1f\x8b":  # gzip
        import gzip
        data = gzip.decompress(data)
    return data


def ticker_to_cik(ticker: str) -> Optional[str]:
    """Resolve ticker -> 10-digit zero-padded CIK via SEC's mapping file (network)."""
    data = json.loads(_get(TICKERS_URL))
    t = ticker.upper()
    for row in data.values():
        if row.get("ticker", "").upper() == t:
            return str(row["cik_str"]).zfill(10)
    return None


def fetch_companyfacts(cik10: str) -> dict:
    """Fetch the full XBRL companyfacts document for a CIK (network)."""
    return json.loads(_get(FACTS_URL.format(cik10=cik10)))


# --- pure parsing layer (offline-testable) ----------------------------------

def concept_series(facts: dict, taxonomy: str, tag: str, unit: str = "USD") -> list:
    """Return the time series (list of period dicts) for one XBRL concept, or []."""
    try:
        node = facts["facts"][taxonomy][tag]["units"][unit]
    except (KeyError, TypeError):
        return []
    # sort by period end for determinism
    return sorted(node, key=lambda d: d.get("end", ""))


def _latest(facts: dict, candidates: list) -> Optional[dict]:
    for taxonomy, tag in candidates:
        if tag.startswith("__"):
            continue  # sentinel (dimensional / not a flat concept)
        for unit in ("USD", "shares", "USD/shares"):
            s = concept_series(facts, taxonomy, tag, unit)
            if s:
                last = s[-1]
                return {"value": last["val"], "tag": tag, "unit": unit,
                        "end": last.get("end"), "fy": last.get("fy"),
                        "fp": last.get("fp"), "form": last.get("form")}
    return None


def extract_financials(facts: dict) -> dict:
    """Map raw companyfacts -> a structured, first-hand financials dict.

    Every value carries its source tag + period + form, so downstream code can
    cite it. Concepts that are genuinely absent go into `gaps` — never fabricated.
    """
    out: dict = {"entity": facts.get("entityName"), "cik": facts.get("cik"),
                 "values": {}, "gaps": []}
    for canon, candidates in CONCEPT_MAP.items():
        hit = _latest(facts, candidates)
        if hit is None:
            out["gaps"].append(canon)
        else:
            out["values"][canon] = hit
    # convenience flat accessors used by tests / callers
    for k, v in out["values"].items():
        out[k] = v
    return out


def _cli_fetch(args) -> int:
    cik = args.cik
    if cik is None:
        if not args.ticker:
            print("need --ticker or --cik", file=sys.stderr)
            return 2
        cik = ticker_to_cik(args.ticker)
        if cik is None:
            print(f"ticker {args.ticker} not found in EDGAR", file=sys.stderr)
            return 2
    cik = str(cik).zfill(10)
    facts = fetch_companyfacts(cik)
    fin = extract_financials(facts)
    _write(fin, args.out)
    return 0


def _cli_parse(args) -> int:
    with open(args.facts, encoding="utf-8") as f:
        facts = json.load(f)
    fin = extract_financials(facts)
    _write(fin, args.out)
    return 0


def _write(fin: dict, out: Optional[str]) -> None:
    txt = json.dumps(fin, indent=2, default=str)
    if out:
        with open(out, "w", encoding="utf-8") as f:
            f.write(txt)
        print(f"wrote {out}: {len(fin['values'])} concepts, {len(fin['gaps'])} gaps "
              f"({', '.join(fin['gaps']) or 'none'})")
    else:
        print(txt)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="EDGAR XBRL first-hand financials")
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch", help="fetch from data.sec.gov (network)")
    f.add_argument("--ticker")
    f.add_argument("--cik")
    f.add_argument("--out")
    f.set_defaults(func=_cli_fetch)
    p = sub.add_parser("parse", help="parse a cached companyfacts.json (offline)")
    p.add_argument("--facts", required=True)
    p.add_argument("--out")
    p.set_defaults(func=_cli_parse)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())