# Scenario Probability Calibration

Load this during Step 5d (scenarios). Replaces the ad-hoc "Bull weight scales with Good-Company score" mapping in `scenario-framework.md` with an explicit, assumption-based, base-rate framework.

**Why this exists**: The previous version mapped Good-Company score → Bull probability (9+ → 25–30%, 7–8 → 15–25%, ≤6 → 10–15%). This was uncalibrated and circular — the same LLM that produced the score then chose the weight from a mapping that the LLM itself self-evaluated as "reasonable." The adversarial test ("a hedge fund analyst would sign these?") was performative because the LLM evaluating its own work almost always passes.

This file fixes that by:
1. Anchoring probability assignment to **explicit assumptions** rather than a derived score
2. Providing **base-rate guidance** from observable financial history
3. Adding an **adversarial check** that requires citing a specific source of disconfirming evidence

---

## The Three Probability Anchors

Each scenario must have its probability anchored to one of these reference points, NOT to the Good-Company score.

### Anchor 1: Base Rate from Sector History

What is the historical frequency that a company in this archetype, at this growth stage, achieved the Bull-scenario trajectory?

Approximate base rates by archetype. **These are uncalibrated judgment priors, not measured frequencies** — a directional starting point informed by industry/academic studies, to be revised by the Calibration Loop (below) as the verdict log accumulates real outcomes. Do not present a probability built on them as if it were empirically derived; cite them as "archetype prior," not "base rate observed in data":

| Archetype | Bull Achievement Base Rate | Bear Realization Base Rate |
|---|---|---|
| High-Growth SaaS | 15–25% (tail outcomes; most SaaS slows) | 20–30% |
| Mature Cash Cow | 5–15% (growth surprises are rare in mature) | 10–20% |
| Hyperscaler | 25–35% (these dominate; share gains compound) | 10–20% |
| Capital-Intensive | 10–20% (cyclical asymmetry) | 25–35% (cycles down hard) |
| Cyclical | 15–25% at trough; 5–15% at peak (cycle-stage dependent) | 30–45% at peak; 10–20% at trough |
| Financials | 15–25% | 15–25% |
| REIT | 10–20% | 15–25% |

**Use these as starting probabilities**, adjusted by company-specific factors (next anchors).

### Anchor 2: Assumption Independence Check

For each Bull scenario assumption, ask: would it require multiple independent positive surprises to be true?

- 1 independent assumption needed → relatively high Bull probability (close to base rate)
- 2 independent assumptions → reduce probability by ~5pp from base
- 3+ independent assumptions → further reduce by ~5pp per additional assumption

Example: NVDA Bull case needs (a) AI capex stays high, (b) AI capex actually monetizes, (c) competitive entrants stay behind. Three independent assumptions → Bull probability is meaningfully below the hyperscaler-archetype base rate of 25–35%.

Mirror logic for Bear: more independent failure conditions required → lower Bear probability.

### Anchor 3: Adversarial Disconfirmation Citation (Mandatory)

For Bull probability ≥ 25%: you must cite ONE specific source of disconfirming evidence that exists in the real world and explain why you weighted past it.

Example (not generic):
> "Bull probability 28% — citing disconfirming evidence: short interest at 18-month high (4.2% of float per Yahoo); short thesis is that Net Debt/EBITDA at 1.6× peaks higher than disclosed because of $30B SPV operating leases. Weighted past because: even if short thesis is correct on SPV, FCF coverage of obligations is 2.4× — survival not at stake."

For Bear probability ≥ 25%: you must cite ONE specific source of confirming-of-Bull evidence and explain why you weighted past it.

This is what the previous version's "adversarial test" should have done — require **specific external evidence** rather than LLM self-evaluation.

---

## How to Assign Probabilities

### Procedural Rules

1. Start with the archetype prior (Anchor 1) as the default Bull probability.
2. Adjust downward for each independent assumption above 1 (Anchor 2).
3. Cite disconfirming evidence and explain weight (Anchor 3).
4. Base case is **the residual**: Base = 100% − Bull − Bear. **Label it `(residual)` in the output** — it is a balancing figure, never an independently estimated probability. Presenting the residual as if it were derived from its own base rate is the "tell" of a probability dressed up as quantitative.
5. Bear is set similarly: archetype prior, adjusted for independent failure conditions, with confirming-of-Bull evidence cited.
6. **Earnings-revision momentum tilt** (from `earnings-revision-momentum.md`, applied in Step 5d) is the ONLY post-anchor adjustment: Mild ±2pp / Strong ±5pp on Bull and Bear. It is a judgmental tilt and MUST cite the revision evidence behind the bucket (e.g. "6 of 8 analysts raised NTM EPS; +3% 30-day revision"). Do not stack other ad-hoc ±pp nudges on top — base-rate prior + assumption-independence + one evidenced momentum tilt is auditable; a pile of unexplained ±pp is not.

### Probability Sum Constraints

Bull + Base + Bear = 100% exactly. No rounding adjustments.

### Probability Range Sanity

If your computed probabilities produce:
- Bull > 40% → almost certainly overconfident; re-examine assumptions
- Bear > 45% → close to "Sell"; verdict math should reflect
- Base < 40% → unusual; bimodal outcome distribution requires explicit justification

---

## How This Affects Decision Rule

The decision rule (Strong Buy / Buy / Watch / Hold thresholds) stays the same. What changes is the quality of the inputs feeding into the weighted expected price.

If probabilities are well-calibrated, the framework's verdict accuracy improves. If probabilities are biased (e.g., LLM systematic Bull bias), the verdicts will be systematically too bullish. This is exactly the calibration problem the verdict-log feedback mechanism is designed to surface over time.

---

## Anti-Patterns to Avoid

### "Round Numbers" Bias

Probabilities like 30/50/20 or 25/50/25 are suspicious because they're suspiciously round. Real probability assignments often look like 22/53/25 — non-round numbers reflect actual reasoning. If you find yourself defaulting to round numbers, you probably haven't reasoned through Anchors 1–3.

### "I Have No View on Probabilities"

Some analysts dodge by leaving probabilities equal-weighted (33/33/33). This is a non-decision. Either you have a view on which scenarios are more likely, or you should not be making a recommendation.

### "Bull Always Wins"

Systematic bias toward Bull (visible in verdict log over time as Bull > Base in many high-quality cases) is the LLM's natural narrative bias. Watch for this in calibration review.

---

## Worked Example

Target: Hyperscaler at trough valuation (e.g., Adobe 2026).

**Step 1**: Archetype base rate Bull = 25% (Hyperscaler 25-35% range, but Adobe is mature-leaning, mid-range).

**Step 2**: Bull assumptions:
1. AI monetization in Creative Cloud + Document Cloud realizes (one assumption)
2. New CEO does not pursue defensive M&A ($5B+ Figma-style deal) (one assumption)
3. Capex stays disciplined while AI capability grows (one assumption)
= 3 independent assumptions → Bull probability adjusted down to 25% − 10pp = 15–20%.

But wait, we set Bull at 30% in the actual Adobe analysis. Why?

**Step 3 (Disconfirming evidence cited)**: We must cite specific bear evidence and explain weight. In the Adobe report we should have said:
> "Bull 30% — citing disconfirming evidence: OpenAI image generation revenue $3B+ and growing >100% YoY; Canva 150M MAU. Weighted past because: Document Cloud is structurally less AI-disrupted (PDF / e-signature legacy); IP-indemnification moat for enterprise is real and growing."

The fact that we got to 30% Bull with three independent assumptions and a clearly-articulated disconfirming-evidence rebuttal means the probability should perhaps have been 22–25%, not 30%.

**Lesson**: This framework would have lowered the Adobe Bull weight from 30% to ~23%, which would have moved the weighted expected price from $411 to maybe $385. Still a Buy, but more conservative — and more honest about the AI uncertainty.

---

## Calibration Loop

Every 10 verdicts, the user (or orchestrator on request) should review the verdict log and compute:

- Average Bull probability assigned: __%
- Frequency of Bull-scenario validation 12 months later: __%
- Gap (= over-confidence or under-confidence)

If the gap exceeds ±10pp, recalibrate the archetype base rates in this file. This is the explicit feedback loop the framework needs.

---

## Documentation in Output

The orchestrator's report must include in the Scenario section:

```
Bull probability assignment: 22%
- Archetype base rate (Hyperscaler): 25%
- Independent assumptions required: 3 → adjustment -5pp → 20%
- Disconfirming evidence cited: <specific>
- Net assigned: 22% (rounded slightly above the assumption-adjustment floor)
```

This makes the probability traceable. The reader can disagree with any step.