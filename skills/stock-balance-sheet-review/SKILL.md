---
name: stock-balance-sheet-review
description: Review a US-listed company's balance sheet health for an equity-research workup. Covers net-debt/EBITDA leverage, current ratio, cash runway, goodwill concentration and impairment history, DSO trend, inventory days, off-balance-sheet items (operating leases, contingent liabilities), and pension underfunding. Trigger when analyzing financial-statement risk at L4 of the seven-layer X-ray framework, or when assessing whether the company can survive a downturn. Dispatched by stock-analysis-lead.
allowed-tools: Read, Grep, Glob, WebSearch, WebFetch, Bash
---

# Stock Balance Sheet Review

## Purpose

Read the balance sheet for survivability. Most retail investors ignore the balance sheet until a recession exposes the leverage they didn't price in. Surface leverage and liquidity risks, goodwill bombs from past M&A, working-capital deterioration that signals customer-credit pressure, and off-balance-sheet hooks that compound in stress. Output a structured Findings set with quantitative thresholds.

## When To Use

- Orchestrator dispatches balance-sheet review (always-on in Standard / Strict depth).
- User asks "is <ticker> financially safe", "what's the debt situation", "can <ticker> survive a recession".

## When NOT To Use

- Earnings quality / cash flow → `stock-earnings-quality-review`
- Business model → `stock-business-review`
- Capital allocation history → `stock-management-review`
- Competitive position → `stock-industry-review`

## Mandatory Gates

### 1) Execution Integrity Gate
Read the balance sheet from the most recent 10-Q (more recent than 10-K). If only 10-K is available, note the date staleness in Execution Status.

### 2) Industry-Norm Gate
Leverage tolerable for a utility is catastrophic for SaaS. Identify sector before applying thresholds. Default thresholds below are general; flag if your sector materially shifts them.

### 3) Off-Balance-Sheet Gate
Read the "Commitments and Contingencies" footnote in every review. Operating leases were brought on-balance-sheet by ASC 842 (2019), but contingent liabilities, guarantees, and purchase obligations are still footnote-only.

### 4) Goodwill-History Gate
A single goodwill impairment is a yellow flag; multiple is a red flag indicating chronic overpayment in M&A. Check 5-year impairment history, not just current year.

## Workflow

1. Load 10-Q balance sheet and 10-K notes (Commitments, Goodwill, Pension).
2. Run filing-pattern-gated scan.
3. Compute ratios: Net Debt / EBITDA (using TTM EBITDA from financial-history), Current Ratio, Goodwill / Total Assets, DSO, Inventory Days.
4. Compare to industry norms and to the company's 5-year history.
5. Emit Findings.

## Filing-Pattern-Gated Execution Protocol

### Execution Order

1. Locate balance sheet (10-Q latest), Goodwill note, Commitments note, Long-term debt note.
2. For each checklist item, locate the specific line/note.
3. **HIT** → compute ratio, compare to threshold, semantic-confirm.
4. **MISS** → mark NOT FOUND.
5. Report only Findings that breach thresholds OR show adverse trend.
6. Include `Filing pre-scan: X/Y items hit, Z confirmed`.

## Balance Sheet Checklist (9 Items)

| ID | Item | Filing Section | Threshold |
|---|---|---|---|
| BS-01 | Net Debt / EBITDA | Long-term debt + Current portion − Cash; TTM EBITDA | Flag > 2× general; sector-aware (utility OK at 4×, SaaS bad at 2×) |
| BS-02 | Current Ratio | Current Assets / Current Liabilities | Flag < 1.0 (liquidity strain); < 1.5 in cyclical industries |
| BS-03 | Cash runway (unprofitable cos) | Cash / annual opex (or annual FCF burn) | Flag < 12 months — must refinance or issue equity |
| BS-04 | Goodwill / Total Assets | Balance sheet Goodwill / Total Assets | Flag > 30% — acquisition-driven; vulnerable to impairment |
| BS-05 | Goodwill impairment history | 5-year notes "Goodwill impairment" | Flag > 0 impairments in 5y as yellow; > 1 = red |
| BS-06 | DSO (Days Sales Outstanding) trend | AR / (Annual revenue / 365), 3-year trend | Flag rising > 10 days YoY without explanation in MD&A |
| BS-07 | Inventory days trend (non-tech) | Inventory / (Annual COGS / 365) | Flag rising > 15% YoY (slowing sell-through / obsolete inventory risk) |
| BS-08 | Off-balance-sheet items | "Commitments and Contingencies" note | Flag material guarantees, purchase obligations, or contingent liabilities |
| BS-09 | Pension underfunding | Pension footnote (defined-benefit only) | Flag underfunded amount > 5% of market cap |

### Severity Rubric

- **High**: Survivability-threatening. Net Debt/EBITDA > 4× in cyclical sector; cash runway < 6 months; goodwill > 50% of assets; multiple recent impairments.
- **Medium**: Adverse but manageable. Leverage rising; DSO trending up; contingent guarantee material but defined.
- **Low**: Watch-list. Inventory days slightly elevated; pension modestly underfunded.

## Evidence Rules

- Compute the ratio yourself; cite the source lines.
- Include the threshold you're comparing against (general or sector-specific).
- Trends: cite at least 3 years of values, not a single snapshot.

## Output Format

### Findings

#### [High|Medium|Low] Short Title

- **ID**: `BS-NN`
- **Citation**: balance sheet line / note, with periods
- **Evidence**: computed ratio + threshold + trend
- **Implication**: what this means under stress

### Suppressed Items

### Execution Status

```
Filings reviewed: 10-Q (Q3 2025), 10-K (FY2024) for footnotes
Filing pre-scan: 9/9 items hit, 2 confirmed as findings
Industry norm applied: <sector>
```

### Summary

One line: `N High / M Medium / K Low — most material: <BS-NN short title>`.

## No-Finding Case

```
No balance-sheet findings — leverage moderate, liquidity ample, no goodwill concentration.
Notable positives: Net Debt / EBITDA = 0.4×; Cash > Total Debt.
```

## Load References Selectively

- `references/balance-sheet-red-flags.md` — load when assessing goodwill concentration, off-balance-sheet items, or pension liabilities; contains the sector-norm leverage table, historical examples of goodwill bombs, and the Commitments-and-Contingencies decoding guide.

## Review Discipline

Balance sheet failures are slow until they're sudden. A leveraged company looks fine in a bull market and dies in a recession. Be unforgiving on High thresholds; the orchestrator will weight these heavily in the Bear scenario.