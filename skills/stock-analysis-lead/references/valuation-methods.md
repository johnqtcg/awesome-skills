# Valuation Methods

Load during Step 5c. The orchestrator runs four valuation methods in sequence: multiples, reverse-DCF, DCF sanity check, scenarios. This file specifies the formulae, sources, and how to interpret each.

---

## Method 1: Multiples — Multi-Dimensional Cross-Check

Apply each multiple along three dimensions:
- Historical percentile (5-year and 10-year of the company's own range)
- Peer median
- Industry composite (where available)

### P/E (Trailing and Forward)

- **Trailing P/E**: useful for sanity but reflects past
- **Forward P/E**: more relevant; uses NTM EPS estimate from analyst consensus
- **5y percentile**: < 30% = below historical average; 70%+ = above

Limitations: P/E meaningless for unprofitable companies; distorted by one-time items in EPS.

### PEG = P/E ÷ Growth Rate

Growth rate = NTM EPS growth rate or 3-year forward growth estimate.

- **< 1**: cheap relative to growth
- **1–2**: reasonable
- **> 2**: expensive
- **> 3**: priced for perfection

PEG is most useful for sustainable growth companies. Avoid PEG for:
- Cyclicals (growth rate volatile)
- Hyper-growth pre-profit (use P/S instead)
- Mature (growth rate near zero — PEG distorts)

### P/S (Price / Sales)

Most useful for unprofitable growth companies where P/E is meaningless.

- SaaS typical range: 5–15× depending on growth + retention
- Consumer typical: 1–4×
- Mature industrial: 0.5–2×

A 20× P/S requires roughly 30%+ revenue growth at 80%+ gross margins to justify. Anything below is overpriced.

### EV/EBITDA

Removes capital structure noise. Compare against peers more reliably than P/E.

- Software: 15–30×
- Consumer brand: 12–20×
- Industrial: 8–14×
- Utility: 8–12×

### EV/FCF

The orchestrator's favorite single multiple. FCF cannot be manipulated like EBITDA (which can hide capex needs).

- **EV/FCF < 20**: reasonable
- **EV/FCF 20–30**: priced for growth — growth must materialize
- **EV/FCF > 40**: priced for perfection — minimal margin for error

Compute EV = Market Cap + Debt − Cash. Use TTM FCF.

### Multi-Dimension Output Format

For each multiple, output:

```
P/E (Fwd):       28.1×    5y %ile: 65%     Peer median: 24×    Composite: 22×
P/S:              7.1×    5y %ile: 70%     Peer median: 6.2×   Composite: 5.5×
EV/EBITDA:       22.4×    5y %ile: 50%     Peer median: 19×    Composite: 17×
EV/FCF:          28.3×    5y %ile: 40%     Peer median: 25×    Composite: 22×
```

Read the table holistically. If all multiples are in the 70%+ historical percentile AND > peer median, the stock is meaningfully more expensive than its norm.

---

## Method 2: Reverse-DCF — The Most Useful Single Valuation Tool

Most analysts use DCF to derive a target price. The smarter use is the opposite: take the current price as given and back-solve for the growth-and-margin assumptions the market is implying. Then ask: are those assumptions realistic?

### Setup

- Current market cap = M
- Current TTM revenue = R₀
- Current operating margin = OM₀
- WACC = w (typically 8–10% for US large-caps)
- Terminal growth rate = g (typically 2.5–3% — slightly above long-run inflation)

### Calculation

Assume the company grows revenue at rate r for 10 years and operating margin expands to OM_t at year 10. Then enters perpetuity growth at g. Compute the present value of free cash flows.

Solve for (r, OM_t) pairs that produce PV = M.

### Interpretation

Examples (illustrative):
- Apple 2026: current price implies 5-year revenue CAGR of 7%, terminal op margin of 32% — both within historical track record. Pricing seems reasonable.
- Hypothetical AI darling at $200B mcap with $1B revenue: current price implies 70%+ growth for 5 years AND terminal op margin > 40%. Not impossible but historically rare; flag as priced-for-perfection.
- Mature value name: current price implies 0% growth and stable margins — easy to beat.

### Use in synthesis

Reverse-DCF answers: **what does the market believe?** If the implied assumptions exceed historical track record or industry-feasible bounds, the stock is overvalued. If implied assumptions are below what management is delivering, the stock is undervalued.

This becomes the strongest single input to the Cognitive-Bias overconfidence check.

---

## Method 3: DCF Forward — Sanity Check Only

Build a 10-year explicit forecast + terminal value. Discount at WACC.

### When to use

- As a triangulation point for the Base scenario in the Bull/Base/Bear framework
- To articulate the impact of specific assumption changes (sensitivity analysis)

### When NOT to lean on it

Per the source doc: DCF has too much manipulation surface. Specifically:
- Terminal value typically > 70% of total DCF — entirely dependent on terminal multiple/growth assumption
- WACC sensitivity: 1pp change → 10%+ change in valuation
- 10-year forecasts are noise

Use DCF as one input, never the anchor. The orchestrator's primary valuation lens is Bull/Base/Bear scenarios with explicit multiples, not DCF.

---

## Method 4: Scenarios

See `scenario-framework.md` for the full Bull/Base/Bear procedure. The decision rule lives there.

---

## Cross-Method Reconciliation

After running all methods, the orchestrator should arrive at three views:

- **Multiples view**: is the stock expensive vs its history, peers, and industry?
- **Reverse-DCF view**: is the market pricing in feasible assumptions?
- **Scenarios view**: across Bull/Base/Bear, is the weighted expected return attractive?

Reconcile any disagreements. Examples:

- Multiples cheap but Reverse-DCF implies declining business → market believes terminal value is impaired (value trap risk). Verdict skews Hold or Sell.
- Multiples expensive but Reverse-DCF implies modest assumptions because growth is accelerating → market is paying for inflection. Could be Buy if growth thesis is intact.
- Scenarios show 60% upside but Bear shows 40% downside → odds attractive only if you can size the position correctly.

The reconciliation paragraph in the final report should explicitly call out which method was load-bearing for the verdict and why.

---

## Numerical Hygiene

- Round multiples to 1 decimal (28.4×, not 28.42×).
- Round percentile to integers (65%, not 64.7%).
- Round target prices to nearest dollar above $20, nearest dime below.
- Never present 3+ significant figures of precision in a forecast — it implies false accuracy.

---

## Common Errors to Avoid

1. **Anchoring on trailing P/E for growth companies**: trailing earnings reflect past investments; forward earnings reflect monetization. For SaaS, use Forward P/E or P/S.
2. **Comparing across business models**: comparing a software company's P/E to a manufacturer's P/E is meaningless. Stay within the peer set.
3. **Treating one period's multiple as steady-state**: cyclicals can show 5× P/E at peak and 50× at trough (because earnings collapsed). For cyclicals, use mid-cycle EPS estimates.
4. **Ignoring stock-based compensation in FCF**: SBC is a real cost. Either subtract SBC from FCF before computing EV/FCF, or note that you didn't. Source doc specifically warns about this.
5. **Treating DCF target price as a forecast**: DCF derives a single point under specific assumptions. Scenarios with probability weights are more honest about uncertainty.