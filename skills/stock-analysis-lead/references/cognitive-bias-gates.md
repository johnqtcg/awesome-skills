# Cognitive-Bias Gates

Load during Step 5e. Run every gate documented below — Gates 1-6 on every run, Gate 7 only for option-dominated names. Document each as PASS, FLAG, or (Gate 7 when it does not apply) N/A, with a rationale.

> The count is deliberately not restated as a number here. It drifted twice — the
> main skill said "Run 6 binary checks" above a list of 7 while this file
> documented 6 gates. `test_skill_frontmatter.py` now derives both from the files.

Gates 1–4 are the four cognitive biases from the source document most relevant to the verdict step — the failure modes that turn a sound analysis into a bad recommendation. Gate 5 adds information-edge honesty (no faked private-information certainty); Gate 6 adds the mirror check — no hiding behind consensus with zero articulated edge.

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

- Every dispatched worker reports mostly positive Findings (the fan-out is 4-6 depending on depth and Tier-1 triggers — see `dispatch-protocol.md`)
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

## Gate 5 — Information-Edge Honesty

Full doctrine in `references/information-edge.md`. The single most dangerous form of false confidence is implying analyst-grade conviction on a thesis whose only inputs are public.

### How it manifests
- Conviction language ("high conviction", "strong buy with confidence") on a thesis built entirely from public filings + sell-side consensus.
- Implying a depth/edge the framework structurally lacks: no channel checks, no expert-network calls, no IR/management access, no first-hand supply-chain datapoints.

### PASS condition
- The report carries the mandatory disclosure: *本分析基于公开披露 + 卖方一致预期,无渠道调研/专家网络/IR 直连/一手供应链 datapoint;价值在流程、广度与校准,不在信息优势。*
- Conviction is capped: "High" is reserved for unambiguous *valuation/process* dislocations (the math is clear), never for forward judgments a better-informed human could out-call. When in doubt, one notch lower.

### FLAG condition
- Any "analyst-grade" / "high-conviction" framing whose edge would actually require private information. Downgrade conviction and state why.

### What to write in the output
```
Information edge: PASS — public-info-only synthesis; disclosure carried; conviction Medium (edge is the valuation dislocation + cross-sectional rank, not private datapoints).
```

---

## Gate 6 — Consensus Clone (no edge)

**Question**: Is my verdict just the consensus, with no articulated variant view? (The mirror of Gate 4: Gate 4 catches being *too far above* consensus on a narrative; Gate 6 catches being *indistinguishable from* consensus while implying the report adds insight.)

Full doctrine in `references/information-edge.md` §1b. A report whose verdict direction matches the sell-side majority and whose target sits on top of the consensus median, with no falsifiable differentiated claim anywhere, is a **consensus clone** — well-organized, well-cited, and adding nothing the reader didn't already have.

### How to detect
- Same verdict DIRECTION as the sell-side majority (e.g., Buy among mostly Buys), AND
- `|weighted expected price − consensus median| / consensus median ≤ 10%`, AND
- the report contains **no explicit, falsifiable 变量观点 / Variant Perception** statement (thesis, number, or probability where you specifically differ).

### PASS condition
The report carries an explicit, falsifiable Variant Perception (per information-edge.md §1b) — a specific way it differs from consensus on thesis, a number, or probability — OR it plainly declares *"变量观点：无 — consensus-aligned; the value here is independent confirmation, not a differentiated call."* Either is acceptable; honesty is the bar.

### FLAG condition
Verdict ≈ consensus AND no variant statement (or only a generic one like "we're more disciplined"). **Antidote**: add one specific, checkable claim where your view diverges from the crowd, or explicitly label the report a consensus restatement. A consensus-confirming call can be correct — but it must be **declared**, not disguised as insight.

### What to write in the output
```
Consensus clone: PASS — variant view stated: market prices VAS as cyclical services (reverse-DCF implies ~8% blended CAGR); I treat VAS as a structural re-rating item growing ~2× the network — falsified if VAS organic growth drops below the network's for 2 quarters.
```
or
```
Consensus clone: FLAG → resolved — initial verdict was Buy at ~consensus target with no differentiation. Added explicit variant view on incentive-ratio trajectory (I model incentives rising to 36% of gross vs consensus ~33%), which is what makes my Base net-revenue CAGR ~1.5pp below the Street.
```
or
```
Consensus clone: PASS — 变量观点：无. Verdict is consensus-aligned (Buy, target within 6% of median); value is the independent, first-hand-data confirmation of the bull case, not a differentiated call. Stated plainly, not dressed as edge.
```

---

## Gate 7 — Inverted Rigor (option-dominated names only)

**Applies only when the Optionality Overlay is attached** (Step 2b: the visible business is worth < ~30-40% of market cap). For every other name this gate is `N/A`, not `PASS` — recording a pass on a gate that never ran overstates the audit.

**Question**: Is the segment driving the *largest* share of value the *least*-modeled thing in the report?

### How inverted rigor manifests

- A four-method valuation on the visible ~10% of value, and one judgment sentence for the decisive ~90%
- The option/venture value appears as a single number with no range and no `P(success)`
- Reverse-DCF on the visible business is read as "priced for impossible growth" and used to cut the tier — which is tautological for an option stock and says nothing
- A material engine (e.g. a fast-growing energy/storage segment) is mentioned in prose but never modeled

### How to detect

- Rank the report's sections by modeling depth; rank the SOTP legs by share of value. If the two orderings are inverted, FLAG.
- Check every `option` leg in `sotp.json` carries low/base/high **and** a `P(success)` range. A point estimate is an automatic FLAG.
- Check `option_share_of_value` (modeled) against `market_implied_option_share`. If the modeled share is near zero while the market-implied share is most of the price, the SOTP was not actually built.

### PASS condition

The SOTP (Step 5c, `scripts/finlib/sotp.py`) exists, every material engine is a modeled leg, every venture leg carries ranges plus `P(success)`, and Bull/Bear come from the venture tree rather than pp-subtraction.

### FLAG condition

Any material driver of value is a bare judgment number. Resolution is to build the missing leg, not to add a caveat — this is the signature failure for these names and a disclosure does not fix it.

### What to write in the output

```
- Inverted rigor: N/A (not option-dominated — visible business is 78% of market cap)
- Inverted rigor: FLAG — robotaxi leg was a single $X judgment; rebuilt as an option leg
  (TAM -> share -> take-rate x P(success) 15-35%), which widened the Bear target to $__
```

---

## Bonus — Reverse Sanity Check

If every applicable gate passes without flags, ask one more question: **Am I being too confident about the gates themselves?**

A clean run that returns nothing but PASS is suspicious. Re-examine each — the gates are designed to catch real biases; if your analysis caught zero biases, you're either unusually disciplined or you're rubber-stamping the checks.

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

The mapping above counts **Gates 1–4** (the bias gates). **Gates 5 and 6 are honesty/edge gates**: a FLAG there is resolved by *adding the missing disclosure* (the information-edge statement, or the variant-perception statement), not by cutting a conviction notch. They do not, by themselves, move conviction — they ensure the report is honest about what kind of call it is.

**Gate 7 is a rework gate**, and it is stricter than either class: a FLAG means the valuation itself is incomplete, so it is resolved by **building the missing SOTP leg and re-deriving the targets**, not by adjusting conviction or adding a caveat. A report may not publish with Gate 7 flagged. Where the gate does not apply, record `N/A` — never `PASS`.

---

## Anti-Pattern: Performative Self-Checking

Avoid running the gates as a checkbox exercise where every gate passes without genuine examination. Signs of performative checking:

- Each gate's rationale is generic ("verdict is data-driven", "narrative is quantified")
- No examples of specific things you considered and rejected
- All gates pass for every analysis you produce

A real analysis surfaces real flags. If your gates always pass, the gates aren't catching anything.