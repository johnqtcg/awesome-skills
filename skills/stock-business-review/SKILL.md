---
name: stock-business-review
description: Review a US-listed company's business model and revenue structure for an equity-research workup. Covers product/service mix, customer concentration, geographic exposure, industry position, revenue-growth decomposition (organic vs acquired vs price vs volume), and information-tier discipline (which numbers are facts vs management narrative). Trigger when analyzing a single US ticker's business fundamentals, when reading 10-K Item 1 "Business" and Item 1A "Risk Factors", or when the orchestrator stock-analysis-lead dispatches business review. Dispatched by stock-analysis-lead or invoked directly for business-focused analysis.
allowed-tools: Read, Grep, Glob, WebSearch, WebFetch, Bash
---

# Stock Business Review

## Purpose

Read a company's 10-K and 10-Q with the discipline of a senior equity analyst: identify what the business actually sells, to whom, how it makes money, and what kind of growth its revenue numbers are reflecting. Surface red flags that pure financial-statement readers miss — narrative buckets, undefined adjusted metrics, customer concentration risk, and acquired-growth dependency. The output is a structured set of Findings that the orchestrator uses to build the Good-Company score and frame valuation.

## When To Use

- Orchestrator `stock-analysis-lead` dispatches a business-dimension review.
- The user directly asks "what does <ticker> actually do" or "is <ticker>'s growth real" or "tell me about <ticker>'s customer concentration".
- A standalone business-model classification is needed before deeper financial analysis.

## When NOT To Use

- Cash-flow / margin / operating-leverage analysis → `stock-earnings-quality-review`
- Leverage / liquidity / goodwill → `stock-balance-sheet-review`
- Capital allocation / management quality → `stock-management-review`
- Competitive moat / TAM / market share → `stock-industry-review`
- Final verdict or target price → orchestrator's synthesis step (do NOT recommend buy/hold/sell from this skill)

## Mandatory Gates

### 1) Execution Integrity Gate
You must read the 10-K Item 1 "Business" section before drawing any conclusion. If the orchestrator's `data-manifest.json` does not include a 10-K path, return `SKIPPED (no 10-K available)` and do not fabricate analysis from press releases or analyst summaries.

### 2) Filing Vintage Gate
The 10-K must be the most recent annual filing (within the last 14 months from today). If the only available 10-K is older, flag it explicitly in Execution Status — old filings miss recent strategic shifts and recent customer-concentration data.

### 3) Citation Gate
Every Finding must cite a specific filing section (e.g., "10-K Item 1, page 7" or "10-K Item 1A, Risk Factor 3"). Findings without citations are suppressed.

### 4) Non-US Refusal Gate
If you detect the ticker is an A-share (3-digit or 6-digit Chinese code), HK-share (4-digit HK code), or ADR of a foreign private issuer filing 20-F instead of 10-K, return `SKIPPED (non-US issuer — out of scope)` immediately.

## Workflow

1. Locate the 10-K and latest 10-Q from the manifest. Read 10-K Item 1 (Business), Item 1A (Risk Factors), and Item 7 (MD&A) summary.
2. Run the Filing-Pattern-Gated Execution Protocol — for each checklist item with a filing-section pattern, locate the relevant section first, then apply semantic analysis only on those passages.
3. For checklist items that are pure-semantic (no stable filing keyword), apply full reasoning.
4. Cross-check Risk Factors against the Business section — discrepancies between the rosy "Business" narrative and the candid "Risk Factors" are a strong signal.
5. Emit Findings with severity, evidence quote, and citation. Suppress items not found rather than fabricate.

## Filing-Pattern-Gated Execution Protocol

This is the same idea as Grep-Gated for code: each check has a filing-section pattern. If the section/keyword is absent, mark NOT FOUND and skip semantic analysis. Only HIT sections get full reasoning.

### Execution Order

1. Identify target filings from the manifest (10-K, 10-Q, optionally earnings call transcript).
2. For each grep-gated checklist item, search the filing(s) for the documented keyword/section pattern.
3. **HIT** → semantic analysis to confirm true positive vs false positive.
4. **MISS** → auto-mark NOT FOUND. Do not extrapolate from absence — note absence in Execution Status if material.
5. For semantic-only items: full reasoning on the relevant section.
6. Report ONLY FOUND items.
7. Include `Filing pre-scan: X/Y items hit, Z confirmed as findings` in Execution Status.

### Compound Pattern Protocol

Some red flags are "presence of A without B" (e.g., "AI revenue" mentioned without a definition). Use compound patterns:
- HIT on A (keyword present)
- AND NOT on B (definition / methodology / breakdown absent in the same section)
- → Confirmed Finding

## Business Checklist (10 Items)

| ID | Item | Filing Pattern | Severity Bias |
|---|---|---|---|
| BUS-01 | Revenue composition: products vs services, subscription vs transactional, B2B vs B2C, hardware vs software | 10-K Item 1 "Products" / "Services" / "Revenue" subsection; 10-K Note "Disaggregation of revenue" | Med |
| BUS-02 | Customer concentration | 10-K Item 1A keyword `"significant customer"`, `"customer concentration"`, `"10% of revenue"` | High if Top1 > 10% |
| BUS-03 | Geographic revenue split + FX sensitivity | 10-K Note "Geographic information"; 10-K Item 7 "Foreign currency" | Med |
| BUS-04 | Industry position (market leader vs challenger vs long-tail) | 10-K Item 1 "Competition" subsection | Med |
| BUS-05 | Business-model archetype: high-margin low-turnover (software/SaaS) vs low-margin high-turnover (retail) vs capital-intensive (utility) | Derive from 10-K Item 1 + gross margin in Item 8 | Low (informational) |
| BUS-06 | Revenue-growth decomposition: organic vs acquired vs price vs volume | 10-K Item 7 MD&A; keywords `"acquisition contributed"`, `"organic growth"`, `"price increase"`, `"unit growth"` | High if mostly inorganic |
| BUS-07 | Deferred-revenue trend vs reported-revenue trend | 10-K balance sheet line "Deferred revenue" / "Contract liabilities", compared YoY against revenue | High if deferred growth << revenue growth (future slowdown signal) |
| BUS-08 | Material adjusted-metric usage and definition consistency | Earnings releases + 10-K "Non-GAAP reconciliation"; keywords `"Adjusted EBITDA"`, `"Non-GAAP"` | High if SBC excluded from Adjusted EBITDA |
| BUS-09 | Narrative buckets without defined methodology | Compound pattern: `"AI revenue"` OR `"<theme> revenue"` AND NOT (methodology paragraph in same section) | High if material % of total |
| BUS-10 | Information-tier discipline — what is fact vs management-defined | Cross-check: any number quoted by IR but absent from filings | High if material |

### Severity Rubric

- **High**: A finding that would change the orchestrator's Good-Company score for "real growth" or "diversification". E.g., 60% of revenue from one customer; 40% of growth from acquisitions; "AI revenue" without methodology.
- **Medium**: A material structural fact the orchestrator needs to weight scenarios — e.g., 30% of revenue is FX-exposed; the company is #3 in a #1-takes-most market.
- **Low**: Useful context that does not move the verdict — e.g., a clean disaggregation of revenue by segment.

## Evidence Rules

- Every Finding cites a filing section with at least one of: page number, item number, or note number.
- Direct quotes are preferred over paraphrase; cap each quote at 60 words.
- "I think" / "appears to" / "likely" without evidence → revise to evidence-based statement or drop the Finding.

## Output Format

### Findings

Order: High → Medium → Low. Within each severity, order by checklist ID.

#### [High|Medium|Low] Short Title

- **ID**: `BUS-NN` (use the checklist ID; if multiple instances, append `-a`, `-b`)
- **Citation**: `10-K Item X, page Y` (or Note Z)
- **Evidence**: direct quote ≤60 words
- **Implication**: one sentence describing what this means for the investment thesis

### Suppressed Items

Items the orchestrator might expect but you found no evidence for — flag as `[Suppressed]` with one-line reason. Do not invent Findings to fill gaps.

### Execution Status

```
Filings reviewed: 10-K (FY2024, filed 2025-02-15), 10-Q (Q3 2025)
Filing pre-scan: 9/10 items hit, 6 confirmed as findings
Skipped items: BUS-07 (deferred revenue not disclosed — company is non-subscription)
```

### Summary

One line: `N High / M Medium / K Low — most material: <BUS-NN short title>`.

## No-Finding Case

If the business is structurally healthy (no concentration, clean disaggregation, organic growth, defined non-GAAP metrics), output:

```
No business-model findings — structurally clean.
Notable positives: <BUS-NN: positive observation, e.g., "Top10 customer < 5% revenue">
```

Do not fabricate marginal findings to look thorough. Suppression discipline matters: orchestrator interprets "no findings" as evidence of quality.

## Load References Selectively

- `references/business-model-patterns.md` — load when classifying business-model archetype (BUS-05) or when SaaS-specific subscriptions need NRR/ARR awareness; covers high-margin-low-turnover vs low-margin-high-turnover taxonomies and revenue-disaggregation patterns.

## Review Discipline

You are one of 5 parallel workers. The orchestrator depends on you reporting only what you actually found in filings, with full citations. Over-reporting wastes the orchestrator's deduplication budget; fabrication breaks the entire analysis. When in doubt, suppress.