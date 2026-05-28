# Capital Allocation Patterns Reference

Load this when classifying a company's 5-year capital-allocation history, evaluating M&A track record, or judging buyback-timing quality.

---

## The Five Uses of Cash

Every dollar of operating cash a company generates ends up in exactly one of these places. The 5-year history of where the money went is a fingerprint of management quality.

1. **Capex** — reinvested in the business (maintenance + expansion)
2. **M&A** — acquired other businesses
3. **Buybacks** — repurchased own shares
4. **Dividends** — returned cash to shareholders
5. **Debt reduction** — paid down debt

A sixth implicit use: **idle cash on balance sheet** — when management generates cash but has no productive use for it.

The right mix depends on growth stage:

- Early growth (low cash, high reinvestment opportunity): heavy Capex + R&D
- Mature growth (high cash, moderate opportunity): mix of Capex + Buybacks
- Mature stable (high cash, low opportunity): heavy Buybacks + Dividends
- Cyclical industrial: Capex + dividend + occasional debt reduction

Mismatch = poor allocation. A late-stage company that keeps doing M&A signals empire-building. A high-growth company that pays a fat dividend signals depleted opportunity.

---

## Buyback Timing Quality

Most retail commentary treats buybacks as inherently good — they're not. Buybacks are good if executed below intrinsic value; they destroy value if executed at peaks.

### How to assess

1. Build a 5-year quarterly table: shares repurchased, average price paid, quarter-end price.
2. Compare each quarter's average buyback price to the trailing 4-quarter price range.
3. Score:
   - Buybacks concentrated near 52-week lows = excellent timing
   - Buybacks evenly distributed = neutral (mechanical)
   - Buybacks concentrated near 52-week highs = poor timing (often pre-recession excess)

### Exemplars

- **Apple**: textbook buyback discipline. Heavy buybacks during 2016, 2019, 2020 lows; lighter during 2021 peak. Result: per-share value compounding well above market.
- **Berkshire Hathaway**: opportunistic buybacks below intrinsic value, none during 2021 peak.
- **Counter-example**: many companies bought heavily in 2019–2021 at peak prices using debt — destroyed value in 2022 correction.

When evaluating MGT-02, look for the pattern over years, not a single quarter.

---

## M&A Track Record Methodology

Management ROI on M&A is the single most-revealing capital-allocation metric. Most large M&A creates negative value for the acquirer.

### Sample 2–3 named acquisitions

Pick acquisitions:
1. Announced 3+ years ago (enough time to evaluate)
2. Material (≥ 5% of acquirer market cap at time of deal)
3. Disclosed in the 10-K M&A footnote

### Estimate ROI

For each:

- Purchase price paid (cash + stock + assumed debt)
- Revenue contribution at time of acquisition
- Revenue contribution today (segment-level disclosure)
- Goodwill write-down history (any impairments mentioned in footnote)

Calculate implicit revenue growth of the acquired business under acquirer's ownership. Compare to industry growth.

Patterns:
- Acquired-segment revenue grew faster than industry: management is a good operator integrating the asset
- Acquired-segment revenue grew with industry but no faster: bought revenue at a premium for no synergy
- Acquired-segment revenue grew slower than industry: actively destroyed value
- Acquired-segment was written down: explicit acknowledgment of overpayment

Flag MGT-03 if 2 of 3 sampled acquisitions show slowing or write-down.

### Historical exemplars

- **Microsoft + LinkedIn (2016)**: $26B deal. LinkedIn revenue 2.5× in 5 years; clean integration. Good capital allocation.
- **AT&T + Time Warner (2018, divested 2022)**: $85B deal; $40B+ write-down. Reverse spin-off. Catastrophic capital allocation.
- **Google + YouTube (2006)**: $1.65B; turned into one of the great media franchises. Exceptional capital allocation.

---

## Guidance Track Record Methodology

Build a scorecard for the last 8–12 quarters: company guided to range $X–$Y, actuals came in $Z. Categorize each quarter:

- **Beat top of range**: management was conservative
- **In range**: management was accurate
- **Miss bottom of range**: management was overoptimistic OR business deteriorated
- **Significant beat (>5% above top)**: either deliberate sandbagging or unexpected upside

### Healthy patterns

- Consistent beats by small margins (1–3% above top of range): management is conservative, credibility-builder
- 6+ of last 8 quarters at or above midpoint: predictable execution

### Red flag patterns

- **Raise-then-miss**: management raised guidance early in the year then missed by year-end. Particularly damaging — signals overconfidence + denial.
- **Repeated downward revisions**: 2+ guidance cuts in trailing 4 quarters. Business is deteriorating faster than management can see.
- **Missing on the "fudge factor"**: missing the bottom of the range by 1% (i.e., they had a chance to set realistic guidance but were too proud) shows poor self-awareness.

Cite specific quarter dates in MGT-04 evidence.

---

## Comp Structure Reading

DEF 14A "Executive Compensation Discussion & Analysis" section. Look for:

### Healthy structure

- **Long-Term Incentive (LTI) tied to TSR (Total Shareholder Return)** vs peer group over 3-year period. Forces management to align with stockholders.
- **Significant performance-vesting** (not just time-vesting): 50%+ of LTI vests on hitting hurdles.
- **Multi-year metrics** (3-year average, not 1-year)
- **Cap on payouts** (so 200% performance doesn't pay 1000%)

### Misaligned structure

- LTI tied only to revenue or non-GAAP earnings (no TSR): can grow revenue with bad ROIC and still pay out
- All time-vesting (no performance hurdles): pure retention pay
- One-year performance window: short-term incentive at long-term cost
- Discretionary bonus dominant: board can pay anything regardless of results

### Founder-controlled / dual-class

Companies with dual-class share structures (Meta, Alphabet, Snap) preserve founder control. Read this neutrally:
- Argument for: founder long-term focus protects against quarterly-earnings myopia
- Argument against: removes accountability, can entrench bad management

Flag MGT-06 if comp ties to short-term metrics AND there is no TSR component.

---

## Insider Ownership and Trading

### Ownership level (proxy "Security Ownership" table)

- CEO ownership > 1% of shares: founder-grade alignment (good)
- 0.1–1%: normal
- < 0.1% and not the founder: low skin-in-the-game (yellow)

Total insider ownership (officers + directors + 10%+ holders): healthy is > 5%.

### Trading activity (Form 4 filings, last 12 months)

- **Cluster of buying**: highest-conviction insider signal. Multiple insiders buying with personal money is rare and bullish.
- **Cluster of selling**: requires nuance. Sales can be:
  - 10b5-1 plan automatic (mechanical, low signal) — disclosed in the Form 4
  - Tax-related (option exercise, RSU vest) — low signal
  - Diversification (CEO selling 5% of holdings spread over a year) — neutral
  - Open-market sales at price highs (the bad pattern) — high signal
- **Insider buying despite low price**: very bullish
- **No buying activity for years**: neutral (some insiders never buy)

Pull the Form 4 filings from SEC EDGAR for the trailing 12 months. Flag MGT-08 only when the pattern is clear (cluster of open-market sales near highs).

---

## Communication Style Audit

Read the most recent earnings call transcript (Q&A section is more informative than prepared remarks). Watch for:

### Honest patterns

- CEO names the specific reason a number missed without blaming external factors
- CEO acknowledges trade-offs (e.g., "We chose to invest in X at the cost of margin this quarter")
- Forward statements include specific magnitude (e.g., "20% revenue growth at 25% operating margin") rather than directional only

### Defensive patterns (flag)

- Misses blamed on "macro headwinds", "challenging environment", "FX" without specifics
- Vague forward statements ("optimistic about the trajectory")
- Combative or dismissive responses to analyst pushback
- Frequent changes in which metrics get highlighted (KPI cherry-picking)

Cite the call date in MGT-09. Quote ≤60 words of the offending passage.

---

## Strategic Thesis Stability

Pull annual letters from the last 3 years. Compare:

- Does the strategy in year 1 still appear in year 3? (Stable thesis is good)
- Does the strategy pivot wildly each year? (Pivot-prone — signal of weak conviction or fashion-chasing)
- Does the strategy persist despite repeated failure? (Stubbornness — opposite problem)

The right pattern: stable core thesis with tactical adjustments. Example: Costco — same strategy for 30 years (high-volume, low-margin, member loyalty), tactical adjustments at the margins.

Flag MGT-10 if you see "AI strategy" appearing as a top priority for the first time in the most recent letter — suggests fashion-chasing rather than coherent capital allocation. Or if the company has pivoted from "platform" to "vertical" to "AI" in successive letters — incoherent.