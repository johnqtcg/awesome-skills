# Valuation Methods

Load during Step 5c. The orchestrator runs four valuation methods in sequence: multiples, reverse-DCF, DCF sanity check, scenarios. This file specifies the formulae, sources, and how to interpret each.

**Branch for option-dominated stocks.** When the **Optionality Overlay** is attached (Step 1.5c: the visible/established business is worth less than ~30–40% of market cap — Tesla, pre-profit narrative names), the structure changes: **Method 5 (Sum-of-the-Parts)** becomes the primary lens, reverse-DCF is demoted to *sizing the option premium* (not a downgrade trigger — see Method 2), and probabilities come from the venture tree (`scenario-probability-calibration.md`). A single-entity scenario target cannot value a company whose price is mostly unproven future businesses; do not force one.

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

## Method 2: Reverse-DCF — Sizing What the Market Implies

For a company whose value lives in its **visible, modelable** business (a compounder, a cash cow, a single-engine grower), this is the most useful single framing tool: take the current price as given and back-solve for the growth-and-margin assumptions the market is implying. Then ask: are those assumptions realistic? It is most powerful precisely where a forward DCF is weakest — it needs no terminal-value guess to be informative.

**It is a framing device, not a verdict.** Do not call a bare reverse-DCF figure "the strongest single piece of evidence." What it produces — an implied CAGR — is only as falsifiable as the WACC and horizon behind it (disclose both), and for some companies it is the *wrong primary lens* entirely (next).

### When reverse-DCF is the WRONG primary lens (option-dominated stocks)

For an option-dominated name (Optionality Overlay attached), reverse-DCF on the **visible** business answers a tautology, not a question. If ~90% of the price is the robotaxi/AI/biotech option, then of course the visible 10% cannot justify the price — that is the *definition* of an option stock, not new bearish information. Two rules follow:

- **Use it to SIZE the option premium, not to condemn the stock.** "The visible business is worth ~$35; the price is $375; therefore the market assigns ~$340 (≈90%) to the option" is the correct, useful inference — and it is exactly the input the SOTP (Method 5) needs.
- **Do NOT mechanically downgrade for an infeasible implied visible-growth.** Converting "the visible business can't carry the price" into a one-notch verdict cut double-counts the premise — you already declared 90% of value to be option. The orchestrator's Cross-Method Reconciliation rule that treats "market implies impossible growth → Bear-confirming, reduce one tier" is **suspended** when the Optionality Overlay is attached.

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

Reverse-DCF answers: **what does the market believe?** For a single-engine business, if the implied assumptions exceed historical track record or industry-feasible bounds, the stock is overvalued; if below what management is delivering, undervalued. For an option-dominated business, the implied visible-growth will *always* look infeasible — read it as the size of the option premium (above), and hand that premium to Method 5 to value explicitly.

This is a strong input to the Cognitive-Bias overconfidence check — but for option-dominated names the load-bearing evidence is the SOTP (Method 5), not this figure.

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

## Method 5: Sum-of-the-Parts (SOTP) — for option-dominated / multi-engine companies

**Run this (as the PRIMARY lens) when the Optionality Overlay is attached.** A single-entity DCF or one blended CAGR cannot value a company that is really several different businesses — an established cash engine + a fast-growing modelable segment + one or more unproven *ventures*. SOTP values each engine on its own terms and sums them. It is the difference between a defensible framework for the option and a single opaque "$650 判断值."

> **Why this matters more than precision.** For an unproven venture the inputs (2032 TAM, addressable share, take-rate, P(success)) are themselves near-guesses — a SOTP does **not** make the answer *precise*. Its value is **auditability and updatability**: it converts one opaque number into a chain of individually-falsifiable, range-expressed, source-tagged assumptions you can debate and revise leg-by-leg as evidence arrives. A SOTP dressed up as a precise point target is *worse* than the judgment number it replaced — it is the same pseudo-precision in a new costume. The engine enforces this (below).

### Procedure

Author a `sotp.json` and run the engine — it refuses un-sourced drivers and refuses a point-estimate option leg:

```bash
python3 scripts/finlib/sotp.py run --model $TMPDIR/stock-analysis-<ticker>/sotp.json
```

Each segment is one of three leg types:

- **`fixed`** — a directly-supplied enterprise value (e.g. the visible auto business's EV from a `valuation.py` driver-model run). One `amount`, one source. (Cash/net debt go in top-level `net_cash`, never a leg.)
- **`multiple`** — `value = metric × multiple` (e.g. energy steady-state EBITDA × EV/EBITDA). **This is the antidote to the "one-line positive" disease**: a material high-margin/high-growth segment (Tesla Energy: GWh × $/kWh × 39.5% margin) gets a modeled leg, not a sentence (see the Segment-Materiality rule in `sector-archetypes.md`).
- **`option`** — a venture valued by an explicit chain, then probability- and time-discounted:
  - `conditional_ev = tam × share × take_rate × margin × exit_multiple`  (EV if it succeeds)
  - `pv_if_success = conditional_ev / (1+discount)^years`
  - `expected_value = pv_if_success × p_success`  (the risk-adjusted contribution that sums into equity)
  - The genuinely-unknowable drivers (`tam`, `share`, `take_rate`, `p_success`) **must** carry `low`/`high`, so the leg — and the whole SOTP — is a **distribution (low/base/high)**, never a point.

`equity = Σ segment EV (probability-weighted for option legs) + net_cash`; per-share = equity / shares.

### Outputs to put in the report

- The **per-share distribution**: low – base – high (not a point target).
- **`option_share_of_value`** — how much of *your modeled* equity is the (probability-weighted) ventures.
- **`market_implied_option_share`** — `(market_cap − visible_equity) / market_cap`: how much of the *price* the market assigns to the ventures (this is the "~90% is option" number). **The gap between these two is the priced-for-perfection signal** — when the market pays for 90% option and a generous SOTP supports far less, the base per-share sits far below price and the verdict writes itself.
- Each option leg's **assumption chain + P(success) as a range** — so a reader can disagree with any single leg.

### `sotp.json` schema

```json
{
  "ticker": "TSLA", "current_price": 374.84, "shares_diluted": 3.35, "net_cash": 28.9,
  "segments": [
    {"name": "auto",   "method": "fixed",
     "drivers": {"amount": {"value": 90, "low": 60, "high": 130, "source": {"kind":"data","ref":"valuation.py auto EV"}}}},
    {"name": "energy", "method": "multiple",
     "drivers": {"metric": {"value": 4.0, "low": 2.5, "high": 6.5, "source": {"kind":"data","ref":"10-K energy GWh×$/kWh×39.5%"}},
                 "multiple": {"value": 8, "low": 6, "high": 11, "source": {"kind":"assumption","note":"hardware EV/EBITDA"}}}},
    {"name": "robotaxi", "method": "option",
     "drivers": {"tam": {"value": 300, "low": 100, "high": 600, "source": {"kind":"estimate","note":"ride TAM 2032"}},
                 "share": {"value": 0.15, "low": 0.05, "high": 0.30, "source": {"kind":"estimate","note":"vs Waymo"}},
                 "take_rate": {"value": 0.5, "low": 0.3, "high": 0.7, "source": {"kind":"assumption","note":"network take"}},
                 "margin": {"value": 0.30, "source": {"kind":"assumption","note":"steady-state"}},
                 "exit_multiple": {"value": 13, "source": {"kind":"assumption","note":"EV/EBIT at maturity"}},
                 "years": {"value": 7, "source": {"kind":"assumption","note":"time to scale"}},
                 "discount": {"value": 0.15, "source": {"kind":"assumption","note":"venture discount"}},
                 "p_success": {"value": 0.16, "low": 0.08, "high": 0.35, "source": {"kind":"estimate","note":"4+ independent successes"}}}}
  ]
}
```

The per-venture `p_success` is the **same number** that feeds the venture probability tree in `scenario-probability-calibration.md` — use one value in both places so the SOTP and the Bull/Bear weights cannot silently disagree.

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