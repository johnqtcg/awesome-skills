# Scenario Framework — Bull / Base / Bear

Load during Step 5d. Build three scenarios with explicit numerical assumptions and probability weights.

The source document Part 3 §5 prescribes this as the most honest valuation approach: **不追求"精确估值"，追求"理解赔率"** — don't aim for a single point estimate; aim to understand the odds.

---

## Required Assumptions per Scenario

Each scenario must specify, explicitly:

| Field | Bull | Base | Bear |
|---|---|---|---|
| 5-year revenue CAGR | % | % | % |
| Terminal operating margin | % | % | % |
| Terminal multiple (EV/EBITDA or P/E) | × | × | × |
| Probability weight | __% | __% | __% |
| Computed target price | $ | $ | $ |

Probability weights must sum to 100%.

---

## How to Set Each Scenario

### Bull

Assume:
- All Good-Company items maintain PASS
- Growth thesis plays out at the high end of management's guidance trajectory
- Multiple expansion if currently below historical peak
- Probability: typically 20–35% (rare for an obvious bull case to be > 35% — if it's > 50%, you're not being honest about uncertainty)

Common Bull driver: TAM expansion realizes, NRR stays > 130%, gross margin holds, share gain accelerates.

### Base

Assume:
- Most Good-Company items stay where they are
- Growth at the analyst consensus midpoint
- Multiple stays at current level or normalizes to 5-year median
- Probability: typically 45–55% — this is your weighted-average future expectation

Common Base driver: business continues current trajectory; multiple compresses modestly from peak.

### Bear

Assume:
- The biggest risk in the Worker Findings actually materializes
- Growth decelerates more than guidance suggests
- Multiple compresses to historical 25th percentile (or peer worst)
- Probability: typically 20–30% — if you can articulate a credible bear case, weight it accordingly

Common Bear drivers (per worker prefix):
- **EQ Bear**: gross margin compresses 5pp; OCF/NI gap widens
- **BS Bear**: leverage rising into a downturn; cash runway shortens
- **MGT Bear**: capital-allocation mistake (overpriced M&A); guidance misses cluster
- **IND Bear**: share loss accelerates; moat erodes (e.g., AI substitution risk)
- **BUS Bear**: customer concentration realizes (top customer cuts spend)

---

## Computing Target Price

For each scenario:

### EV/EBITDA approach

1. Project Year-5 revenue = R₀ × (1 + CAGR)^5
2. Project Year-5 EBITDA = Year-5 revenue × (terminal op margin + D&A margin)
3. Target enterprise value = Year-5 EBITDA × terminal multiple
4. Target equity value = Target EV − Year-5 net debt
5. Target price = Target equity value / shares outstanding (Year 5)

### P/E approach (for mature profitable companies)

1. Project Year-5 EPS using consensus + scenario-specific delta
2. Target price = Year-5 EPS × scenario terminal P/E

### P/S approach (for unprofitable growth companies)

1. Project Year-5 revenue
2. Target market cap = Year-5 revenue × scenario terminal P/S
3. Target price = Target market cap / shares outstanding (Year 5, including reasonable SBC dilution)

Discount Year-5 target back to present value at WACC if you want a today's-equivalent target. Often skipped — buyers think in terms of multi-year return horizons, not PV.

---

## Decision Rule

After computing all three targets and assigning probabilities:

```
Weighted Expected Price = Σ (scenario_price × probability)
Weighted Expected Return = (Weighted Expected Price − Current Price) / Current Price
Bear-to-Current Ratio = Bear Price / Current Price
```

Verdict ladder:

| Condition | Verdict |
|---|---|
| Weighted return ≥ 50% AND Bear/Current ≥ 0.75 | **Strong Buy** |
| Weighted return ≥ 30% AND Bear/Current ≥ 0.70 | **Buy** |
| Weighted return ≥ 15% AND Bear/Current ≥ 0.80 | **Watch** (set alert price) |
| Weighted return 0–15% | **Hold** if already held; not adding |
| Weighted return < 0 | **Trim** if held, **Sell** if conviction in Bear is high |
| Weighted return ≥ 30% but Bear/Current < 0.55 | **Watch** — upside is real but downside too severe; wait for better price |

The Bear/Current floor is critical. A 50% expected return is not attractive if Bear means losing 50% — risk-adjusted, that's a 0% game. Source doc: "期望回报/最大下行 > 2 = 好赔率" — expected upside divided by max downside > 2 is good odds.

---

## Probability-Weight Discipline

**Use the calibrated framework in `scenario-probability-calibration.md`** for probability assignment. The previous "Good-Company score → Bull weight" mapping is **deprecated** — it was uncalibrated and circular.

Summary of the calibrated framework:

1. **Anchor 1**: Start with the archetype base rate (see sector-archetypes.md and calibration file).
2. **Anchor 2**: Adjust downward for each independent positive assumption above 1 (Bull) or independent failure condition (Bear).
3. **Anchor 3 (mandatory)**: Cite specific real-world disconfirming evidence and explain why you weighted past it.

Probability assignments must show the work. A probability without traceable anchors is uncalibrated guess.

Probability sum constraint: Bull + Base + Bear = 100%.

Sanity range: Bull > 40% is almost certainly overconfident; Bear > 45% should produce a Sell verdict; Base < 40% requires explicit justification for the bimodal outcome distribution.

---

## Example Scenarios — Worked Example (Hypothetical)

Company XYZ, currently $100, generates $20B revenue, op margin 25%, $1B FCF, 0 net debt.

| Field | Bull | Base | Bear |
|---|---|---|---|
| 5-year revenue CAGR | 22% | 14% | 6% |
| Terminal op margin | 32% | 27% | 22% |
| Terminal EV/EBITDA | 25× | 20× | 13× |
| Probability | 25% | 50% | 25% |
| Year-5 revenue | $54B | $39B | $27B |
| Year-5 EBITDA (= rev × (op margin + 4% D&A)) | $19.4B | $12.1B | $7.0B |
| Target EV | $485B | $242B | $91B |
| Target price (assume 200M shares) | $2,425 | $1,210 | $455 |

(Numbers fabricated to illustrate the framework; do not use as a real reference.)

- Weighted price = $2,425×0.25 + $1,210×0.5 + $455×0.25 = $606+$605+$114 = $1,325
- Weighted return = ($1,325 − $1,000) / $1,000 = 32.5% (over 5 years; ~5.8% annualized)
- Bear/Current = $455 / $1,000 = 0.45 — too severe a downside even with attractive Bull

Verdict (per decision rule): **Watch** — wait for better entry. Bear scenario losing > 50% of capital makes the odds inadequate at this price.

---

## When Scenarios Disagree With Multiples

If your scenarios produce a Weighted Expected Price 50% above current AND multiples view says "expensive vs history" — investigate the disconnect. Common explanations:

- Your Bull/Base CAGRs are too optimistic — re-anchor against management guidance + analyst consensus
- Your Bear multiple compression is too modest — recheck what the company's multiple was at the last cyclical low
- Multiples view is anchored on trailing — your scenarios are properly forward; this disagreement may be legitimate

When in doubt, lean toward the scenarios — they are explicit about the future; multiples implicitly bake in the past.

---

## Cognitive-Bias Trap in Scenarios

The biggest failure mode: **anchoring Bull/Base/Bear too close together**. If your Bull is $130 and your Bear is $90 on a $100 stock, you've collapsed the framework. A real Bear/Bull spread for a typical growth company is 3–5× from end to end (Bear $40, Bull $200 on $100).

If your scenarios are too tight, your framework isn't doing its job. Force yourself to consider the genuine tail outcomes — that's the whole point.