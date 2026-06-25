# Valuation Methods

Load during Step 5c. The orchestrator runs four valuation methods in sequence: multiples, reverse-DCF, DCF sanity check, scenarios. This file specifies the formulae, sources, and how to interpret each.

---

## Method 0: Driver Model (build this FIRST — it powers Methods 2–4)

Do not narrate three plausible terminal P/Es. Build one **driver model** and let the engine compute DCF, reverse-DCF, the three scenarios, the (derived) terminal multiple, and a sensitivity table. Changing one assumption (e.g. Azure growth) recomputes the target automatically.

**Why a model, not three numbers:** the old failure mode was hand-picking a terminal P/E and three CAGRs — internally inconsistent and unauditable. A driver model makes Bull/Base/Bear three parameterizations of the *same* equations, and forces the terminal multiple to be an OUTPUT (Gordon: EV/FCF = (1+g)/(WACC−g)).

**False-precision guardrail:** every driver must carry a `source`. The **anchor** drivers (`revenue_0`, `op_margin_start`, `da_pct`, `capex_pct` — the starting point) MUST be `data` from `financials.json`; forward drivers (`revenue_cagr`, `op_margin_terminal`, `wacc`, `terminal_growth`) are legitimately `assumption`. If an anchor is only an assumption, the run prints `grounding: LOW` and the valuation must be labeled **illustrative, not analytical**. An un-sourced driver is rejected outright — you cannot slip a guessed number into a DCF.

### Procedure

```bash
# 1. anchors come from first-hand data (Step 2 produced financials.json)
# 2. author model.json (schema below)
python3 scripts/finlib/valuation.py run --model $TMPDIR/stock-analysis-<ticker>/model.json \
        --sensitivity revenue_cagr
```

Outputs: `base_target`, `scenarios{bull,base,bear,weighted,weighted_return,bear_to_current}`,
`reverse_dcf.implied` (the growth the **current price** implies — flag if it exceeds the company's track record), `derived_terminal_ev_fcf`, `sensitivity`, and `grounding`.

### model.json schema

```json
{
  "ticker": "MSFT", "current_price": 421.92,
  "shares_diluted": 7.43, "net_cash": 60.0, "horizon_years": 5,
  "drivers": {
    "revenue_0":          {"value": 282.0, "source": {"kind":"data","ref":"financials.json:revenue@FY2025"}},
    "op_margin_start":    {"value": 0.45,  "source": {"kind":"data","ref":"financials.json:op_income/revenue@FY2025"}},
    "da_pct":             {"value": 0.10,  "source": {"kind":"data","ref":"financials.json:dep_amort/revenue@FY2025"}},
    "capex_pct":          {"value": 0.20,  "source": {"kind":"data","ref":"financials.json:capex/revenue@FY2025"}},
    "revenue_cagr":       {"value": 0.12,  "source": {"kind":"assumption","note":"Azure-led ~12%"}},
    "op_margin_terminal": {"value": 0.43,  "source": {"kind":"assumption","note":"mild fade"}},
    "tax_rate":           {"value": 0.17,  "source": {"kind":"data","ref":"financials.json:effective_tax@FY2025"}},
    "wacc":               {"value": 0.09,  "source": {"kind":"assumption","note":"CAPM ~9%"}},
    "terminal_growth":    {"value": 0.04,  "source": {"kind":"assumption","note":"~GDP+"}}
  },
  "scenarios": {
    "bull": {"revenue_cagr": 0.15, "op_margin_terminal": 0.45, "terminal_growth": 0.045},
    "base": {},
    "bear": {"revenue_cagr": 0.07, "op_margin_terminal": 0.40, "terminal_growth": 0.03}
  },
  "probabilities": {"bull": 0.25, "base": 0.50, "bear": 0.25}
}
```

FCF each year = NOPAT + D&A − capex − ΔNWC, with operating margin fading linearly from `op_margin_start` to `op_margin_terminal` over the horizon; terminal value via Gordon. The report's scenario table and the decision-rule inputs (weighted return, bear/current) should be **read from this model's output**, and the report must state the `grounding` verdict and show the sensitivity row so a reader sees which numbers are data-grounded vs assumed.

### Mandatory disclosure (the report must SHOW, not just compute)

A DCF / reverse-DCF number is not analytical unless the reader can see its load-bearing assumptions. Whenever the report cites **any** DCF, reverse-DCF, or intrinsic-value figure, it MUST disclose, adjacent to that figure:

- **WACC** and **terminal growth `g`** — the two assumptions that move the answer most (a 1pp WACC change ≈ 10%+ on value; an undisclosed WACC makes any "implied CAGR" unfalsifiable);
- the **reverse-DCF implied growth** at the current price, printed next to the company's actual track-record CAGR;
- a **sensitivity table** — at minimum the 1-D `revenue_cagr ± 3pp` sweep the engine emits. For any verdict that leans on the DCF, run a **2-D grid** (`revenue_cagr × wacc`, or `revenue_cagr × terminal multiple`) — call `valuation.py` twice across a WACC range, or vary `terminal_growth`. The engine's single-driver sweep is a floor, not the ceiling.

A single-point intrinsic value with none of the above is **illustrative, not analytical** — label it so. Never call a bare point estimate "the strongest single piece of evidence": its precision is an artifact of undisclosed assumptions.

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

### DCF intrinsic value ↔ scenario / multiple target price

The DCF prints an intrinsic value **as of today**; the Bull/Base/Bear table prints a **36-month** target (often forward EPS × a multiple). These are two different numbers, and readers conflate them. When the DCF Base intrinsic value and the Base scenario target differ by more than ~10%, the report MUST reconcile them in one explicit sentence — is the gap the time horizon (36 months of compounding), an assumed multiple re-rating, a different FCF-conversion path, or a share-count change? An unreconciled "\$553 DCF vs \$600 target" pair reads as two methods that were never made to agree, and quietly hides which one the verdict actually rests on.

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