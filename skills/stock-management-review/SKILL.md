---
name: stock-management-review
description: Review a US-listed company's management quality and capital-allocation track record for an equity-research workup. Covers 5-year capital-allocation history (buybacks vs dividends vs M&A vs capex vs debt), buyback timing, M&A return-on-investment, guidance-vs-actuals track record, comp-structure alignment, insider ownership and trading activity, earnings-call communication style, and strategic-thesis stability. Trigger when analyzing the human-judgment layer (L5 of the seven-layer X-ray) — the most under-rated and longest-impact dimension. Dispatched by stock-analysis-lead.
allowed-tools: Read, Grep, Glob, WebSearch, WebFetch, Bash
---

# Stock Management Review

## Purpose

Read DEF 14A (proxy), Letter to Shareholders, last 4 earnings-call transcripts, and 5-year capital-allocation history with a single question in mind: would I trust this CEO with my money for the next decade? Identify capital allocation skill (buyback timing, M&A discipline), credibility (guidance-vs-actuals), incentive alignment (comp structure), skin-in-the-game (insider ownership and trading), and communication honesty (call transcript style). Output structured Findings on management quality — orchestrator weights this heavily in long-horizon scenarios.

## When To Use

- Orchestrator dispatches management review (always-on in Standard / Strict).
- User asks "is the management good", "what's the CEO's track record", "are they good capital allocators".

## When NOT To Use

- Financial statement analysis → `stock-earnings-quality-review` or `stock-balance-sheet-review`
- Business strategy details → `stock-business-review`
- Industry positioning → `stock-industry-review`

## Mandatory Gates

### 1) Execution Integrity Gate
You must read at least 2 of: latest proxy (DEF 14A), latest annual letter to shareholders, last 4 earnings call transcripts. If fewer than 2 available, return `SKIPPED (insufficient management-disclosure data)`.

### 2) 5-Year-Window Gate
Capital allocation is a multi-year discipline. Look at 5 years of cash-flow allocation choices (buybacks, dividends, M&A, capex, debt). A single year is noise.

### 3) Insider-Activity Recency Gate
Insider transactions older than 12 months are weak signals. Pull the most recent 12 months of Form 4 filings.

### 4) Communication Bias Gate
Earnings call transcripts have an inherent positivity bias (CEOs sell). Look for absence of defense, willingness to name failures, and specific (not vague) forward statements.

## Workflow

1. Locate proxy, annual letter, recent earnings call transcripts.
2. Build the 5-year capital-allocation table from cash flow statements.
3. Sample 1–2 named acquisitions; estimate ROI (revenue contribution vs purchase price + integration cost).
4. Build the 8–12 quarter guidance-vs-actuals scorecard.
5. Read the most recent earnings call for tone; flag defensive patterns or vague guidance.
6. Emit Findings.

## Filing-Pattern-Gated Execution Protocol

### Execution Order

1. Identify filings: DEF 14A (comp + ownership), annual letter, transcripts.
2. For each checklist item, locate the specific section/keyword.
3. **HIT** → semantic + quantitative analysis.
4. **MISS** → mark NOT FOUND.
5. Report only confirmed Findings.
6. Include `Filing pre-scan: X/Y items hit, Z confirmed`.

## Management Checklist (10 Items)

| ID | Item | Filing Section | Trigger |
|---|---|---|---|
| MGT-01 | 5-year capital-allocation pattern | Cash flow statements ×5 | Profile: where did cash go (buybacks / div / M&A / capex / debt). Flag if M&A-heavy + low ROI. |
| MGT-02 | Buyback timing quality | Share repurchase history vs price history | Flag if buybacks concentrated at price-peak quarters (poor timing) |
| MGT-03 | M&A ROI (sample 2–3 named deals) | 10-K M&A footnote + segment results | Flag if acquired-segment revenue growth < industry growth, or write-down occurred |
| MGT-04 | Guidance-vs-actuals (8–12 quarters) | Earnings releases + actuals | Flag if missed > 2 of last 8 quarters; flag if "raise-then-miss" pattern |
| MGT-05 | Frequency of guidance revisions (down) | Earnings releases | Flag if guidance lowered > 2× in trailing 4 quarters |
| MGT-06 | Comp structure: LTI alignment | DEF 14A "Executive Compensation" section | Flag if LTI tied to revenue-growth or non-GAAP earnings without TSR component |
| MGT-07 | Insider ownership level | DEF 14A "Security Ownership" table | Flag if CEO/CFO ownership < 0.1% AND founder no longer with company (low skin-in-the-game) |
| MGT-08 | Insider net buying/selling (12 months) | Form 4 filings | Flag if cluster of selling at price highs OR no buying despite low price |
| MGT-09 | Earnings call communication style | Last earnings call transcript | Flag defensive patterns: blames macro for misses; vague forward statements; refuses analyst pushback |
| MGT-10 | Strategic-thesis stability | Annual letters (3 years) | Flag if strategy pivots every year (no compounding) OR same strategy persists despite repeated failure (stubborn) |

### Severity Rubric

- **High**: A Finding that should cap Bull-scenario probability. E.g., 3 consecutive guidance misses; M&A returns < 5%; insider selling cluster at highs.
- **Medium**: A Finding warranting watch. E.g., comp not tied to TSR; one missed guidance; modest founder dilution.
- **Low**: Context. E.g., capital allocation tilted to buybacks (informational unless timing is bad).

## Evidence Rules

- Cite proxy section, earnings release date, or Form 4 filing.
- For capital allocation, show the 5-year table summarized.
- For guidance vs actuals, show the scorecard or quote specific quarters.
- Direct quotes from earnings calls capped at 60 words.

## Output Format

### Findings

#### [High|Medium|Low] Short Title

- **ID**: `MGT-NN`
- **Citation**: proxy section / earnings release date / transcript date
- **Evidence**: data series or direct quote
- **Implication**: what this means for long-horizon trust

### Suppressed Items

### Execution Status

```
Filings reviewed: DEF 14A (FY2024), Annual Letter (FY2024), Q3/Q4 FY24 + Q1/Q2 FY25 earnings transcripts
Filing pre-scan: 9/10 items hit, 3 confirmed as findings
Skipped items: MGT-07 (founder still major holder — alignment evident, no flag)
```

### Summary

One line: `N High / M Medium / K Low — most material: <MGT-NN short title>`.

## No-Finding Case

```
No management-quality findings — track record clean, capital allocation thoughtful, communication direct.
Notable positives: Guidance beat 7/8 last quarters; CEO ownership 4%; buybacks well-timed (avg buyback 18% below current).
```

## Load References Selectively

- `references/capital-allocation-patterns.md` — load when classifying capital allocation history or evaluating M&A track record; contains buyback-timing analysis methodology, M&A-ROI estimation framework, and worked examples (e.g., Apple's playbook vs AT&T's historical disasters).

## Review Discipline

Management quality is the highest-impact / longest-horizon dimension. A great business with bad management compounds bad capital allocation; a mediocre business with great management often outperforms. Be selective with High severity — reserve it for clear pattern evidence over multiple years.