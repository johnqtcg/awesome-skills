# Data Acquisition Playbook

Load this during Step 2 to fetch the standard data package. This document specifies primary sources, tool choices, URL patterns, and fallback chains.

---

## Standard Data Package

For a Standard-depth analysis, fetch:

1. Latest 10-K (annual report)
2. Latest 10-Q (interim report)
3. Latest DEF 14A (proxy)
4. Last 4 earnings call transcripts (or the most recent if only one is fetchable)
5. Current price + basic multiples
6. 10-year historical financials
7. Peer list (2–4 close comparables)
8. Analyst consensus estimates
9. Insider Form 4 activity (last 12 months)

---

## SEC EDGAR — Primary Source for Filings

The SEC's EDGAR system is the canonical source for all US-listed company filings. It is free, public, and authoritative.

### URL patterns

Find company CIK (Central Index Key):
```
https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company=<NAME>&type=10-K&dateb=&owner=include&count=40
```

Once CIK known, list all 10-K filings:
```
https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=<CIK>&type=10-K&dateb=&owner=include&count=40
```

Ticker → CIK direct lookup:
```
https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=<TICKER>&type=10-K
```
(EDGAR accepts ticker in the CIK parameter for most US-listed equities.)

### Fetching strategy

1. Use `WebFetch` on the index page to extract the most recent filing's link.
2. Follow the link to the filing's "primary document" (usually `*.htm`).
3. Use `WebFetch` with the appropriate prompt to extract specific sections (e.g., "Extract Item 1 Business and Item 1A Risk Factors").

### EDGAR-specific gotchas

- EDGAR may rate-limit; if requests fail with 403, wait and retry, or fall back to company IR page.
- The "primary document" URL changes per filing; never hard-code a URL.
- 10-K and 10-Q filings can be > 1MB; consider using `firecrawl-download` to extract clean text rather than `WebFetch` which has length limits.
- For PDFs of older filings, EDGAR provides text-extracted HTML — prefer the HTML version.

---

## Filing-Section Strategy

The full 10-K is 100k+ words. Don't ask the model to read the whole thing. Extract the sections workers need:

| Section | Where in 10-K | Worker(s) that need it |
|---|---|---|
| Item 1 — Business | usually pages 4–25 | `stock-business-review` |
| Item 1A — Risk Factors | pages 25–60 | All workers — read for relevant subsections |
| Item 7 — MD&A | varies — typically the largest section | `stock-business-review`, `stock-earnings-quality-review` |
| Item 8 — Financial Statements & Notes | starts ~ pp. 80; runs to end | `stock-earnings-quality-review`, `stock-balance-sheet-review` |
| Item 9A — Controls and Procedures | brief | Skip unless material weakness disclosed |
| Schedule II — Valuation reserves | end | Skip unless investigating |

For the proxy (DEF 14A):
| Section | Contents | Worker |
|---|---|---|
| Compensation Discussion & Analysis | exec comp structure | `stock-management-review` MGT-06 |
| Summary Compensation Table | total comp by executive | MGT-06 |
| Security Ownership | insider holdings table | MGT-07 |

---

## Earnings Call Transcripts

Primary source: **Seeking Alpha** (free tier provides recent transcripts).

URL pattern:
```
https://seekingalpha.com/symbol/<TICKER>/earnings/transcripts
```

Use `firecrawl-search` with query `<ticker> earnings call transcript Q<n> 20XX site:seekingalpha.com` to find a specific quarter. Then `firecrawl-download` or `WebFetch` on the result.

Fallback: company IR page typically has webcast replay + sometimes a transcript. If neither is available, mark the management worker as DEGRADED.

---

## Current Price and Multiples

Primary: **stockanalysis.com** (free, no auth, reliable, machine-readable).

URL: `https://stockanalysis.com/stocks/<ticker>/`

Extract via `WebFetch` with a prompt like:
```
From this page, extract:
- Current price
- TTM P/E
- Forward P/E
- P/S ratio
- EV/EBITDA
- Market cap
- 52-week range
```

Fallback: Yahoo Finance (`finance.yahoo.com/quote/<ticker>`) via firecrawl-scrape — JS-rendered, so plain WebFetch may not work.

---

## 10-Year Historical Financials

Primary: stockanalysis.com financial pages
- Income: `https://stockanalysis.com/stocks/<ticker>/financials/`
- Balance Sheet: `https://stockanalysis.com/stocks/<ticker>/financials/balance-sheet/`
- Cash Flow: `https://stockanalysis.com/stocks/<ticker>/financials/cash-flow-statement/`

These pages show 10 years of annual data by default; quarterly available via toggle (use `?p=quarterly` query param).

Fallback: **Macrotrends** (`macrotrends.net/stocks/charts/<ticker>/<company-slug>/<metric>`) — provides individual metric pages with longer history. Useful when stockanalysis.com is missing data.

---

## Peer List Identification

Three-step approach:

1. **Primary**: read the 10-K Item 1 "Competition" subsection. Most companies name 2–5 competitors explicitly.
2. **Augment**: WebSearch query `<ticker> competitors closest peers` and cross-reference with the 10-K list.
3. **Validate**: peers should have similar revenue scale (within 5× either direction) and similar business model. Don't pair $5B SaaS with $500B mega-cap tech.

Typical peer count for analysis: 3 (one larger, one similar, one smaller is ideal).

---

## Analyst Consensus

Primary: Yahoo Finance "Analysis" tab
```
https://finance.yahoo.com/quote/<TICKER>/analysis
```

Fetch via firecrawl-scrape (JS-rendered). Extract:
- Number of analysts covering
- Mean revenue estimate (current FY, next FY)
- Mean EPS estimate (current FY, next FY)
- Mean price target (high / low / median)

Use this for the Overconfidence cognitive-bias check (Step 5e #4): if your weighted-expected price differs from analyst median target by > 20%, flag and justify.

---

## Insider Form 4 Activity

Primary: SEC EDGAR Form 4 filings for the company.

URL pattern:
```
https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=<TICKER>&type=4&dateb=&owner=include&count=40
```

Pull the most recent 12 months. Categorize each by:
- Insider name + role
- Open-market vs 10b5-1 plan vs option-related
- Net shares acquired / disposed
- Price executed (for open-market)

This feeds MGT-08 (insider net buying/selling pattern).

---

## Manifest Format

Write a single JSON manifest after Step 2 completes:

```json
{
  "ticker": "AAPL",
  "fetched_at": "2026-05-15T03:00:00Z",
  "company_name": "Apple Inc.",
  "sec_cik": "0000320193",
  "fiscal_year_end": "September",
  "filings": {
    "10K": {
      "path": "$TMPDIR/stock-analysis-AAPL/10K.txt",
      "fiscal_year": 2024,
      "filing_date": "2024-11-01",
      "url": "https://www.sec.gov/Archives/edgar/data/..."
    },
    "10Q": { ... },
    "DEF14A": { ... }
  },
  "transcripts": [
    {"path": "...", "quarter": "Q1 FY25", "date": "2025-01-30"}
  ],
  "price_data": {
    "current": 187.45,
    "as_of": "2026-05-15",
    "ttm_pe": 28.7,
    "fwd_pe": 26.2,
    "ps": 7.1,
    "ev_ebitda": 22.3,
    "market_cap_b": 2900,
    "52w_high": 199.62,
    "52w_low": 164.08
  },
  "historicals": {
    "path": "...",
    "years": 10,
    "source": "stockanalysis.com"
  },
  "peers": ["MSFT", "GOOGL", "META"],
  "analyst_consensus": {
    "n_analysts": 42,
    "fy1_rev_est_b": 410.0,
    "fy1_eps_est": 7.20,
    "price_target_median": 210,
    "price_target_high": 250,
    "price_target_low": 180
  },
  "insider_activity": {
    "path": "...",
    "window_months": 12
  },
  "missing": []
}
```

If any artifact is missing or partially fetched, add an entry to `missing` with:
```json
{"artifact": "DEF14A", "reason": "EDGAR rate-limited; retry suggested", "impact": "MGT worker DEGRADED — comp data unavailable"}
```

Workers read the manifest from a path in their dispatch prompt. They self-skip checks dependent on missing artifacts and report the skip in their Execution Status.

---

## Data Freshness Policy

A scratch directory from a prior run may still exist. Reuse is allowed **only within these windows**, judged against the manifest's `fetched_at` (and per-artifact dates). When stale, re-fetch; if re-fetch fails, treat as `missing` — never silently analyze on stale data.

| Artifact | Reuse window | Rationale |
|---|---|---|
| 10-K / 10-Q / DEF 14A | Until superseded by a newer filing (check EDGAR for filings after `fetched_at`) | Filings are immutable; only supersession matters |
| Earnings call transcript | Until the next earnings date | Same — immutable once published |
| 10-year financial history | 90 days, unless an earnings report landed since `fetched_at` | Changes only on new reports |
| Current price + multiples | **Never reuse across sessions** — re-fetch every run | Verdict math anchors on current price |
| Analyst consensus / earnings-revision momentum | 7 days | Revisions move weekly; momentum is the point |
| Peer list | 180 days | Competitive set changes slowly |
| Insider Form 4 activity | 30 days | New filings arrive continuously |

Record in the manifest which artifacts were reused vs freshly fetched (`"reused_from": "<prior fetched_at>"`); the final report's Data Coverage section must disclose any reuse.

---

## Failure Modes and Mitigations

| Failure | Mitigation |
|---|---|
| EDGAR returns 403 / rate-limited | Wait 60s, retry once. Then fall back to company IR page. |
| SEC viewer (new in 2024) renders JavaScript-heavy | Use `firecrawl-download` (which renders JS) instead of plain `WebFetch` |
| Earnings transcript paywall | Try multiple sources (Seeking Alpha → company IR → Bamsec). If none, mark DEGRADED. |
| stockanalysis.com missing a metric | Fall back to Macrotrends for that specific metric |
| Ticker is recently IPO'd (no 10-K yet) | Mark all workers DEGRADED — can run 10-Q/S-1 reading but with reduced confidence |
| Ticker delisted / acquired | Refuse — there is no actionable thesis on a delisted name |
| Foreign private issuer (20-F filer only) | Refuse per orchestrator's non-US gate |