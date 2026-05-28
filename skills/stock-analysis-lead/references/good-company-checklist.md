# Good Company Checklist

Load during Step 5b. Score 10 items as PASS / WEAK / FAIL using aggregate Findings from the workers + sector-archetype-specific thresholds. The checklist follows source-document Part 3 §1 in spirit but **must be applied with sector-aware thresholds** from `sector-archetypes.md`, not generic SaaS defaults.

A company scoring 7+ PASS = "good company"; 9+ PASS = "high quality / 卓越公司". Score 5 or below = quality concerns; orchestrator should weight Bear scenario heavily.

**Critical**: The thresholds below are SaaS/Hyperscaler defaults. For Mature Cash Cow / Capital-Intensive / Cyclical / Financials / REIT archetypes, the threshold for each item differs — see `sector-archetypes.md` for the full per-archetype parameter sets. The PASS/WEAK/FAIL determination must use the archetype-specific threshold, NOT the defaults below.

Example: a KO (Mature Cash Cow) growing revenue 4% should score PASS on Item 1 (threshold ≥4% for that archetype), NOT WEAK or FAIL as the SaaS default ≥15% would suggest. Applying the SaaS default to mature cash cows is exactly the systematic bias the archetype framework exists to fix.

---

## The 10 Items

### 1. Revenue Growth — sustained ≥ 15%

| Source worker | Earnings-Quality |
|---|---|
| Evidence sought | 3+ year revenue CAGR ≥ 15%, AND most recent 4-quarter trend not collapsing |

- **PASS**: 3-year CAGR ≥ 15% and recent quarter ≥ 12%
- **WEAK**: 3-year CAGR 8–15%, OR strong trailing but recent quarter < 5%
- **FAIL**: 3-year CAGR < 8%, OR recent revenue declining

Note: a slowing growth trend even within "good" levels is a yellow flag. A 30% → 20% → 12% trajectory is decelerating; PASS the level test but flag in synthesis.

### 2. Gross Margin — high and stable / rising

| Source worker | Earnings-Quality |
|---|---|
| Evidence sought | Sector-aware gross margin level (see business-model archetype) and 3-year trend |

- **PASS**: sector-leading or top-quartile + stable or rising
- **WEAK**: sector-median + stable, OR slight compression
- **FAIL**: persistent compression > 2pp/year, OR materially below sector

### 3. Operating Leverage — OpInc growth ≥ Revenue growth

| Source worker | Earnings-Quality |
|---|---|
| Evidence sought | TTM OpInc growth vs TTM revenue growth |

- **PASS**: OpInc growing ≥ 1.2× revenue growth (positive leverage)
- **WEAK**: OpInc growing roughly with revenue (1.0×)
- **FAIL**: OpInc growing < revenue (negative leverage) — margins eroding

### 4. FCF — positive and growing

| Source worker | Earnings-Quality |
|---|---|
| Evidence sought | 3-year FCF trajectory (FCF = OCF − Capex) |

- **PASS**: FCF positive each of the last 3 years AND growing in trend
- **WEAK**: FCF positive but uneven, OR negative in 1 year due to one-time capex
- **FAIL**: FCF negative in 2+ recent years OR positive but declining

### 5. SaaS Specific — NRR > 115% (skip if not SaaS)

| Source worker | Earnings-Quality EQ-06 |
|---|---|
| Evidence sought | Reported NRR in earnings release / investor day deck |

- **PASS**: NRR > 115%
- **WEAK**: NRR 105–115%
- **FAIL**: NRR < 105% or declining toward 100%
- **N/A**: skip if business is not subscription/SaaS

If skipped, the Good-Company total is out of 9 instead of 10. Adjust threshold for the 7+ rule accordingly (7/10 ≈ 6/9, 9/10 ≈ 8/9).

### 6. Market Share — rising (or holding in mature market)

| Source worker | Industry |
|---|---|
| Evidence sought | Company revenue growth vs industry growth |

- **PASS**: company growth > industry growth (gaining share)
- **WEAK**: company growth = industry growth (holding share in growth market) OR holding share in stable market
- **FAIL**: company growth < industry growth (losing share)

### 7. Balance Sheet Health

| Source worker | Balance-Sheet |
|---|---|
| Evidence sought | Net Debt/EBITDA, liquidity, goodwill, off-balance-sheet items |

- **PASS**: Net Debt/EBITDA ≤ 2× (sector-adjusted), no liquidity concerns, goodwill < 30% of assets, no recent impairments
- **WEAK**: leverage near the upper sector bound, one concern (e.g., DSO trending up) but otherwise sound
- **FAIL**: leverage > sector red-flag threshold, OR liquidity strain, OR multiple goodwill impairments

### 8. Management Quality

| Source worker | Management |
|---|---|
| Evidence sought | Guidance track record + capital allocation + insider activity |

- **PASS**: 6+ of last 8 quarters in/above guidance, sensible capital allocation, no concerning insider activity
- **WEAK**: mixed guidance record, mixed capital allocation
- **FAIL**: 3+ guidance misses, or M&A track record poor, or insider selling cluster at highs

### 9. Identifiable Moat — any of 7 named types

| Source worker | Industry IND-05 |
|---|---|
| Evidence sought | Named moat: network / brand / scale-cost / switching / patent / regulatory / proprietary-data |

- **PASS**: named moat with quantified evidence (NRR, margin stability, market share, etc.)
- **WEAK**: named moat but evidence narrow or weakening
- **FAIL**: no identifiable moat OR moat eroding (e.g., NRR falling, switching cost reduced by new tech)

### 10. TAM — large and growing

| Source worker | Industry |
|---|---|
| Evidence sought | TAM size and 5-year TAM growth rate |

- **PASS**: TAM growing > 8%/year AND large headroom (current revenue < 30% of TAM)
- **WEAK**: TAM growing 4–8%/year, OR company already dominant (> 50% of TAM)
- **FAIL**: TAM growing < 4%/year (mature market), OR shrinking

---

## Scoring Procedure

For each item, examine the aggregate Findings from the corresponding worker. Translate severity into score:

- High severity Finding on the relevant dimension → contributes to FAIL
- Medium severity Finding → contributes to WEAK
- No relevant Finding + positive observation in worker's "No-Finding Case" → PASS

Tally: count PASS items.
- 9–10 PASS: high-quality company
- 7–8 PASS: good company
- 5–6 PASS: average — quality bar uncertain
- ≤ 4 PASS: quality concerns dominate

This score is one input to the verdict; it is NOT the verdict itself. A high-quality company at a poor price is a Watch, not a Buy. A mediocre company at a fire-sale price might be a Buy.

---

## Anti-Pattern: Score Inflation

Beware grading on a curve. The bar for PASS is high — the source doc deliberately calls a 7+ score "good company" implying that scoring 7 is not trivial.

Common inflation traps:
- Awarding PASS on item 2 (gross margin) because "the trend is improving" when the level is still mediocre
- Awarding PASS on item 6 (market share) because the company is "stable" when industry is actually growing faster
- Awarding PASS on item 9 (moat) when the company's own language describes "competitive advantages" but no named moat type fits

When in doubt, score WEAK. The orchestrator's verdict is more accurate when the inputs are honest.