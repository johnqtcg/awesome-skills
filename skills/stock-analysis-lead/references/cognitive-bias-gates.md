# Cognitive-Bias Gates

Load during Step 5e. Run 4 binary self-check questions. Document each as PASS or FLAG with rationale.

The source document's end section enumerates six common cognitive biases. The four most relevant to the verdict step are below — these are the failure modes that turn a sound analysis into a bad recommendation.

---

## Gate 1 — Anchoring

**Question**: Am I anchoring the verdict on the stock's recent price action rather than on intrinsic value?

### How anchoring manifests

- "It dropped 50% from highs — it must be cheap now"
- "It tripled in a year — it must be expensive"
- "It's near the 52-week low — value opportunity"
- "It's at all-time highs — overdue for a pullback"

### How to detect

- Did the verdict appear before you completed Bull/Base/Bear?
- Does your Base-scenario target price suspiciously hover close to the current price (anchoring bias)?
- Are you using past prices as the comparison rather than intrinsic value?

### PASS condition

The verdict flows from the Good-Company score and the Scenario weighted expected return. The historical price chart is not a load-bearing input.

### FLAG condition

Your justification language includes "down X% from highs" or "near recent lows" as a primary reason. **Antidote**: derive the verdict purely from the framework, then check whether the implied price target is reachable. If you find yourself making the framework fit a pre-formed conclusion based on the chart, re-run the synthesis with the chart hidden.

### What to write in the output

```
Anchoring: PASS — verdict derived from Bull/Base/Bear weighted return; no reliance on past price levels.
```

or

```
Anchoring: FLAG — my Bear price ($85) is suspiciously close to last year's low ($83). Re-checked: Bear scenario at $85 reflects 13× EV/EBITDA on year-5 EBITDA — that 13× came from the 2022 trough multiple, which is a legitimate stress test. Re-affirmed.
```

---

## Gate 2 — Story Bias

**Question**: Have I quantified the narrative — specific revenue numbers, time horizons, probabilities?

### How story bias manifests

- "AI-beneficiary" without naming the revenue stream
- "Mega-trend tailwind" without sizing the TAM and time-to-realize
- "First-mover advantage" without naming the moat type or the time-to-second-mover
- "Visionary CEO" without citing specific decisions that have paid off

### How to detect

- Read your verdict justification paragraph. Count the specific numbers (revenues, years, percentages). If fewer than 3 specifics, the verdict rests on narrative.
- Look for phrases the source doc explicitly flags: "万亿市场", "AI受益", "首屈一指", "巨大潜力" — and the English equivalents.

### PASS condition

Every claim in the verdict has a specific number, time horizon, or probability attached.

### FLAG condition

Any of the following appears without quantification:
- "Benefits from AI"
- "Captures the X opportunity"
- "Trillion-dollar TAM"
- "Best-in-class"
- "Strong tailwinds"

**Antidote**: replace each unquantified phrase with a specific claim ("captures 15% of the $40B enterprise AI inference market by 2030, growing at 35% CAGR per IDC"). If you cannot make it specific, drop the claim.

### What to write in the output

```
Story bias: PASS — TAM citation: $42B 2024 → $90B 2029 (IDC, Mar 2026); company captures 18% share growing to 25% (mgmt guidance, Q1 FY26 call); growth rate matches industry CAGR.
```

or

```
Story bias: FLAG — initial draft referenced "AI tailwinds" without sizing. Replaced with specific revenue: $8B current AI-attributable revenue + $4B incremental over 24 months (sum of 5 customer wins disclosed in earnings calls).
```

---

## Gate 3 — Confirmation

**Question**: Did at least one worker raise a substantive counter-thesis?

### How confirmation bias manifests

- All 6 workers report mostly positive Findings
- The Findings that surface skew toward confirming the prior view
- "Risks I Accept" reads like marketing copy ("currency headwinds", "competition") rather than substantive risks

### How to detect

- Count the Findings: are any of them adverse to the Tilt direction?
- Look at the dissent: did any worker fundamentally disagree with the others? (e.g., earnings-quality is positive but balance-sheet says high leverage)
- Are your "Risks I Accept" specific to the company (e.g., "TSMC concentration") or generic (e.g., "macroeconomic environment")?

### PASS condition

At least one worker raised a Finding adverse to the Tilt direction, OR the workers' Findings reveal substantive disagreement that the synthesis paragraph explicitly resolves.

### FLAG condition

All workers report the same direction (all positive or all negative) without dissent. **Antidote**: spawn a red-team thought — "what's the bear case that an experienced short-seller would write?" Make sure it's reflected in Risks I Accept.

### What to write in the output

```
Confirmation: PASS — earnings-quality and industry workers reported positive; management worker flagged buyback timing (MGT-02) as concern; balance-sheet flagged rising DSO (BS-06). Substantive disagreement integrated into the Watch verdict.
```

or

```
Confirmation: FLAG — all workers reported positive. Red-team adversarial: "what if AI capex doesn't translate to revenue?" — material risk not surfaced. Added to Risks I Accept as #1.
```

---

## Gate 4 — Overconfidence vs Sell-side Consensus

**Question**: Am I more bullish than sell-side consensus median by > 20%? If yes, can I justify the divergence specifically?

### How overconfidence manifests

- "Everyone else is wrong; I see what they're missing"
- Weighted-expected price > Wall Street median target × 1.2
- The justification for being above consensus relies on a single narrative without supporting evidence

### How to detect

- Pull analyst consensus median target from the manifest (`price_target_median`).
- Compute: (Your Weighted Expected Price − Consensus Target) / Consensus Target.
- > 20%: FLAG — must justify specifically.
- 0 to 20%: PASS — you're modestly above consensus, normal range.
- < 0 (you're below consensus): PASS — being more conservative is not a bias, it's a defensible position.

### PASS condition

Your weighted expected price is within 20% of consensus median, OR if outside, you cite specific evidence that explains the divergence:
- "Consensus assumes 12% revenue CAGR; I assume 18% because [specific recent customer wins / product launch / new market opening]"
- "Consensus uses 25× EV/EBITDA; I use 20× because [margin compression evident in last 3 quarters]"

### FLAG condition

Your weighted expected price > 1.2× consensus median AND your justification is narrative-based rather than specific.

### What to write in the output

```
Overconfidence: PASS — my Weighted Expected Price is $215 vs consensus median $200, a +7.5% premium. Within normal range; reflects same growth assumptions as consensus but tighter Bear scenario.
```

or

```
Overconfidence: FLAG — my Weighted Expected Price is $260 vs consensus median $185, +40% premium. Justification: I assume 25% revenue CAGR vs consensus 14%. Difference attributed to disclosed customer wins ($XX revenue runrate) and accelerating TAM (industry forecast revised up by Y). Risk acknowledged: if win rate doesn't sustain, my CAGR is too aggressive — pre-listed in Risks I Accept.
```

---

## Bonus — Reverse Sanity Check

If all 4 gates pass without flags, ask one more question: **Am I being too confident about the gates themselves?**

A clean run that says "PASS, PASS, PASS, PASS" without any flagged adjustments is suspicious. Re-examine each — the gates are designed to catch real biases; if your analysis caught zero biases, you're either unusually disciplined or you're rubber-stamping the checks.

Most quality analyses surface at least one flag. The flag is not a sign of bad work — it's a sign you found a bias before publishing.

---

## How Gates Affect Verdict Conviction

Each FLAG reduces conviction. Mapping:

| Flags | Conviction adjustment |
|---|---|
| 0 flags | Conviction unchanged (likely High) |
| 1 flag | Conviction adjusted from High → Medium |
| 2 flags | Conviction adjusted to Medium or Low |
| 3+ flags | Conviction = Low; consider downgrading verdict from Buy → Watch |

A "Buy" with Low conviction is fine — it tells the user the position size should be modest. The output should not bury the conviction tag; surface it next to the verdict.

---

## Anti-Pattern: Performative Self-Checking

Avoid running the gates as a checkbox exercise where every gate passes without genuine examination. Signs of performative checking:

- Each gate's rationale is generic ("verdict is data-driven", "narrative is quantified")
- No examples of specific things you considered and rejected
- All gates pass for every analysis you produce

A real analysis surfaces real flags. If your gates always pass, the gates aren't catching anything.