# Earnings Revision Momentum

Load this during Step 2 (data acquisition) and Step 5c (valuation).

**Why this exists**: Academic finance research (Stickel 1991, Womack 1996, plus more recent work) consistently identifies **analyst earnings-revision direction** as one of the strongest single empirical predictors of next-12-month equity returns. The previous version of this framework collected consensus *targets* but ignored the *velocity* of those targets — i.e., whether analysts were raising or lowering estimates in the trailing 30/60/90 days. This file fixes the omission.

Earnings-revision momentum is **complementary** to fundamental analysis, not a substitute for it. A great company with rising estimates is more compelling than a great company with falling estimates, even if both have the same target price.

---

## What to Track

For the target and each peer in the comparison panel, capture:

| Metric | Source | Window | Direction |
|---|---|---|---|
| EPS NTM revision direction | Yahoo Finance "Analysis" tab; Bloomberg if available | 30, 60, 90 days | +/- |
| EPS NTM revision magnitude | Same | 30-day % change | absolute |
| Revenue NTM revision direction | Same | 30, 60, 90 days | +/- |
| Number of analysts raising vs cutting estimates | Same | 30 days | count |
| Price target revision velocity | Aggregate sell-side targets | 30, 60, 90 days | weighted |
| Sentiment from earnings call language | Recent call transcripts (qualitative — sample) | Most recent quarter | bullish/cautious/defensive |

Only the first four are strictly quantitative; targets and tone are softer.

---

## Classification

After capturing the data, classify the target into one of four buckets:

### Strong Positive Momentum

- ≥ 70% of analysts raised EPS NTM estimates in trailing 30 days
- Aggregate NTM EPS revised up > 3% in 30 days
- Recent quarter beat + management raised forward guidance
- Earnings call language is confident and specific

### Mild Positive Momentum

- 50–70% of analysts raised estimates
- Aggregate NTM EPS revised up 0–3%
- Mixed beat (slight beat or in-line)
- Earnings call language stable

### Mild Negative Momentum

- 30–50% raised (50–70% cut)
- Aggregate NTM EPS revised down 0–3%
- Mild miss or guidance reset
- Earnings call language defensive on macro

### Strong Negative Momentum

- ≥ 70% of analysts cut EPS NTM estimates
- Aggregate NTM EPS revised down > 3%
- Material miss + guidance cut
- Earnings call language acknowledges trajectory change

---

## How This Affects the Synthesis

### Scenario Probability Adjustments

Earnings-revision momentum should explicitly nudge the Bull/Base/Bear probability weights:

| Momentum Bucket | Bull | Base | Bear |
|---|---|---|---|
| Strong Positive | +5pp | +0pp | −5pp |
| Mild Positive | +2pp | +0pp | −2pp |
| Mild Negative | −2pp | +0pp | +2pp |
| Strong Negative | −5pp | +0pp | +5pp |

This nudge is bounded — momentum is one input among many. Do NOT swing weights by more than 5pp on momentum alone.

### Verdict Conviction Adjustment

Strong Positive momentum can support upgrading conviction one tier (Medium → High). Strong Negative can downgrade Buy to Watch even when scenario math passes Buy.

### Bear Trigger Watch

Strong Negative momentum is itself a partial Bear-case validation. Surface it in the "Risks I Accept" section explicitly: "Sell-side revising estimates down — Bear scenario probability higher than fundamental analysis alone would suggest."

---

## Use With the Peer Comparison Worker

Earnings revision momentum should be one of the items in the peer comparison panel. If the target has positive momentum but peers have negative momentum, that's relative strength. If everyone in the panel has negative momentum, that's industry-wide rather than firm-specific — interpret differently.

---

## Edge Cases

- **Recently IPO'd companies**: insufficient analyst coverage; momentum is noisy. Note in Execution Status and weight lighter.
- **Post-earnings-blackout periods**: revisions are clustered right after quarterly reports. Within 1-2 weeks of a report, the revision pattern is most informative. Stale revisions (60+ days old in a fast-moving narrative) are less informative.
- **Special situations**: M&A, spin-offs, restatements distort revision pattern. Document and either exclude or note caveat.

---

## Output Discipline

The orchestrator's report must include an **"Earnings Revision Momentum"** subsection in the synthesis (Step 5e or in a dedicated section). Format:

```
Momentum bucket: <Strong Positive / Mild Positive / Mild Negative / Strong Negative>
30-day EPS NTM revision: +X.X% / -X.X%
Analysts raising vs cutting (30d): X up / Y down
Probability weight adjustment applied: Bull +/- Xpp, Bear +/- Ypp
Conviction adjustment: <maintained / upgraded / downgraded> based on momentum
```

This puts the momentum signal in plain sight where it can be cross-checked.

---

## Anti-Pattern: Momentum Chasing

The point of including momentum is to **stress-test** fundamental conclusions, not to invert them. A high-quality company at attractive valuation with mild negative momentum is still a Buy candidate — momentum reduces conviction, not the verdict. Conversely, a low-quality company at high valuation with positive momentum should NOT be upgraded to Buy by momentum alone; that's the chase pattern that ends badly in cycles.

Use momentum as a **finishing check**, not a primary input.