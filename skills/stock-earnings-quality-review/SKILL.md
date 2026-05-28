---
name: stock-earnings-quality-review
description: Review a US-listed company's earnings quality, cash-flow integrity, and operating leverage for an equity-research workup. Covers operating cash flow vs net income drift, free cash flow trajectory, capex character (maintenance vs expansion), equity issuance / shareholder-return yield, revenue-quality signals (receivables vs revenue growth, channel stuffing), gross-margin level and trend, operating leverage, and three-cost-rate hygiene (S&M, R&D, G&A). SaaS-specific: ARR/NRR/GRR/CAC payback/Magic Number. Trigger when analyzing financial statements at L1+L2+L3 of the seven-layer X-ray framework. Dispatched by stock-analysis-lead.
allowed-tools: Read, Grep, Glob, WebSearch, WebFetch, Bash
---

# Stock Earnings Quality Review

## Purpose

Read the income statement, cash-flow statement, and selected MD&A passages with the eye of an analyst who trusts cash over accruals. Surface the most common quality red flags: net income that doesn't convert to cash, capex understated as "maintenance" while it's really expansion, receivables ballooning faster than revenue, gross margins eroding under cover of revenue growth, operating leverage that runs in reverse. Output a structured Findings set; do NOT draw the verdict — orchestrator does that.

## When To Use

- Orchestrator dispatches earnings-quality review (always-on in Standard / Strict depth).
- User asks about "earnings quality", "is the profit real", "cash conversion", "operating leverage", "margin trend".
- A pre-cursor to valuation — you cannot trust forward earnings until you've tested the quality of trailing earnings.

## When NOT To Use

- Balance sheet leverage / liquidity / goodwill → `stock-balance-sheet-review`
- Business model / customer concentration → `stock-business-review`
- Management capital allocation → `stock-management-review`
- Competitive moat / market share → `stock-industry-review`
- DCF, multiples, target price → orchestrator's synthesis step

## Mandatory Gates

### 1) Execution Integrity Gate
You must read the cash flow statement from the most recent 10-K and the latest 10-Q. If neither is in the manifest, return `SKIPPED (no cash flow data)`.

### 2) Multi-Period Gate
A single quarter or single year is noise. Compare ≥3 years of annual data (10-K plus historicals from manifest's `financial-history.json` if present). Trend matters more than level.

### 3) Sector-Aware Gate
A 20% gross margin is normal for retail and catastrophic for software. Identify the sector from the business-review's classification (or from 10-K SIC code in the manifest) before scoring margin levels.

### 4) Non-GAAP Discipline Gate
Where the company reports both GAAP and non-GAAP, always check the reconciliation. If SBC, restructuring, or amortization is excluded from "Adjusted EBITDA", surface it — these are real costs.

## Workflow

1. Load cash flow statement (10-K Item 8), income statement, and segment notes.
2. Run filing-pattern-gated scan over the checklist; semantic-confirm hits.
3. Pull 10-year financial-history from manifest if present; compute trends for OCF/Net Income ratio, FCF, gross margin, opex rates.
4. If business model = SaaS / subscription, run the SaaS sub-checklist (items EQ-06 + EQ-07).
5. Emit Findings with severity + numerical evidence (don't say "margin declining" without a number).

## Filing-Pattern-Gated Execution Protocol

### Execution Order

1. Identify the target sections in the manifest: cash flow statement, income statement, Note "Disaggregation of revenue", Item 7 MD&A.
2. For each checklist item with a documented filing-section pattern, locate the section and extract the numerical series.
3. **HIT** → quantitative analysis (compute ratio, trend, YoY change) + semantic check.
4. **MISS** → mark NOT FOUND; do not infer from analyst summaries.
5. For semantic items (e.g., management's explanation in MD&A): full reasoning on the passage.
6. Report only items where the numbers actually violate the rubric.
7. Include `Filing pre-scan: X/Y items hit, Z confirmed as findings`.

## Earnings Quality Checklist (14 Items)

| ID | Item | Filing Section | Threshold / Trigger |
|---|---|---|---|
| EQ-01 | OCF vs Net Income drift | Cash flow statement vs Income statement | Flag if OCF / Net Income < 0.7 for 2+ years |
| EQ-02 | FCF trajectory (FCF = OCF − Capex) | Cash flow statement | Flag if FCF negative AND not improving YoY |
| EQ-03 | Capex character (maintenance ≈ depreciation, expansion >> depreciation) | Cash flow "Capex" vs Income "D&A" | Flag if Capex / D&A > 2× without explicit expansion narrative |
| EQ-04 | Equity issuance pattern (dilution) | Cash flow "Issuance of common stock" + share-count history | Flag if shares outstanding grew > 5% YoY without M&A |
| EQ-05 | Shareholder return yield = (buybacks + dividends) / market cap | Cash flow "Repurchase of common stock" + "Dividends paid" | Informational — context for capital allocation worker |
| EQ-06 | SaaS metric: NRR (Net Revenue Retention) | Earnings releases, investor presentations | Flag if NRR < 110% for a "growth" SaaS; < 100% = customer flight |
| EQ-07 | SaaS metric: CAC payback / Magic Number | Investor presentations | Flag if Magic Number < 0.75 (deteriorating unit economics) |
| EQ-08 | Deferred-revenue growth vs revenue growth | Balance sheet "Contract liabilities" YoY | Flag if deferred growth < revenue growth by > 5pp (future slowdown signal) |
| EQ-09 | Receivables growth vs revenue growth (channel stuffing) | Balance sheet "AR" YoY vs Income revenue YoY | Flag if AR growth > revenue growth by > 10pp |
| EQ-10 | Gross-margin level vs sector + trend | Income statement; sector benchmark | Sector-aware threshold; flag declining margin > 2pp YoY |
| EQ-11 | Operating leverage check | OpInc growth vs Revenue growth | Flag if OpInc growth < Revenue growth in 2+ recent quarters (negative leverage) |
| EQ-12 | Sales & Marketing rate trend | Income segment | Flag if S&M / Revenue rising while revenue growth slowing (CAC inflation) |
| EQ-13 | R&D rate + SBC treatment in non-GAAP | Income + non-GAAP reconciliation | Flag if SBC > 15% of revenue AND excluded from Adjusted EBITDA |
| EQ-14 | One-time-item frequency (restructuring, write-downs) | Income statement "Special items" 5-year count | Flag if "one-time" items appear in 3+ of last 5 years (i.e., they're recurring) |

### Severity Rubric

- **High**: A Finding that would flip a Good-Company score item to FAIL — e.g., OCF / NI persistently below 0.7; FCF negative and worsening; NRR < 100%.
- **Medium**: A Finding that warrants reducing Bull-scenario probability — e.g., gross margin trending down 2pp/yr; S&M rate rising while growth slowing.
- **Low**: Useful context — e.g., shareholder return yield is 4%, providing a floor.

## Evidence Rules

- Findings must include the numerical value AND the direction/trend. "Margin declining" without numbers is rejected.
- Cite the filing line ("Cash flow statement line 'Purchases of property and equipment'") plus the year(s) compared.
- For SaaS metrics not in the 10-K, cite the earnings release or investor presentation explicitly.

## Output Format

### Findings

#### [High|Medium|Low] Short Title

- **ID**: `EQ-NN`
- **Citation**: filing section + period
- **Evidence**: numerical value(s) + trend
- **Implication**: what this changes about the investment thesis

### Suppressed Items

Items checked but not confirmed — list with one-line reason.

### Execution Status

```
Filings reviewed: 10-K (FY2024), 10-Q (Q3 2025), 10-year history (stockanalysis.com)
Filing pre-scan: 13/14 items hit, 5 confirmed as findings
Skipped items: EQ-06, EQ-07 (non-SaaS business model — SaaS metrics N/A)
Sector: <e.g., enterprise software>
```

### Summary

One line: `N High / M Medium / K Low — most material: <EQ-NN short title>`.

## No-Finding Case

```
No earnings-quality findings — cash conversion clean, margins stable, leverage positive.
Notable positives: OCF/NI = 1.05 (3-year avg); FCF margin 28% and stable.
```

## Load References Selectively

- `references/earnings-quality-patterns.md` — load when interpreting OCF/NI gaps, capex classification, or SaaS-specific metrics; contains worked examples, sector-specific margin benchmarks, and the Magic Number / CAC-payback formulae.

## Review Discipline

You are the most-loaded worker (14 checks). Discipline: numbers in every Finding; suppress items you cannot quantify. Orchestrator weights High-severity items heavily — false High findings damage the verdict more than missed Medium findings.