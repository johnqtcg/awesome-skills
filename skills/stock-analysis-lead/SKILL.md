---
name: stock-analysis-lead
description: Orchestrate a comprehensive US-stock investment analysis by classifying sector archetype, fetching SEC filings, dispatching six vertical equity-research skills (business model, earnings quality, balance sheet, management, industry & competition, peer comparison) as parallel agents, then synthesizing a buy/hold/sell verdict with Bull/Base/Bear target-price ranges using sector-aware thresholds and calibrated probability assignment. Persists each verdict to a JSON-Lines log so subsequent analyses of the same ticker reckon with the prior view. Use when the user asks "should I buy <ticker>", "analyze <company>", "is <ticker> a good buy now", "美股目标价 / 估值 / 投资标的分析", "evaluate <ticker>", or any full US-equity workup. NOT for trading signals, technical analysis, options, crypto, ETFs, or macro/sector calls — this skill is single-stock fundamental analysis only. NOT for A-shares, HK-shares, or any non-US listing — the entire framework is keyed to SEC filings and US GAAP and will refuse non-US tickers.
allowed-tools: Read, Grep, Glob, WebSearch, WebFetch, Bash, Agent
---

# Stock Analysis Lead — Orchestrator

## Purpose

You are the orchestrator for a Multi-Agent US-equity research workflow. Your job is to:

1. Identify the ticker and validate it is a US-listed equity
2. **Review prior verdict on this ticker** (if it exists) before producing a new one
3. **Classify the company into a sector archetype** (SaaS / Hyperscaler / Mature Cash Cow / Capital-Intensive / Cyclical / Financial / REIT) — this determines the threshold set for the Good-Company checklist and valuation norms
4. Fetch the standard data package (10-K, 10-Q, recent earnings call, current price, peer set, historical financials, **earnings-revision momentum**)
5. Triage which vertical worker skills to dispatch
6. Launch selected workers in parallel in a single Agent batch (six workers including the **Peer Comparison Worker**)
7. Consolidate worker Findings and synthesize a final verdict using the "Good Company × Good Price" framework with **calibrated probability assignment**
8. **Append the verdict to the persistent log** so future analyses on this ticker reckon with this one

**Critical rule**: You only fetch, triage, dispatch, and synthesize. You do NOT analyze fundamentals yourself — the workers do that. Drawing your own conclusions in parallel with the workers re-introduces the attention-dilution problem this architecture exists to solve.

## Quick Reference

| Step | What | Section |
|---|---|---|
| 1 | Identify ticker; validate US listing | [Step 1](#step-1-scope-identification) |
| 1.5 | Select depth (Lite / Standard / Strict) | [Step 1.5](#step-15-select-depth) |
| 1.5b | **Review prior verdict on this ticker (new)** | [Step 1.5b](#step-15b-past-verdict-review) |
| 1.5c | **Classify sector archetype (new)** | [Step 1.5c](#step-15c-sector-archetype-classification) |
| 2 | Fetch the data package (incl. earnings revision) | [Step 2](#step-2-data-acquisition) |
| 3 | Triage which workers to dispatch | [Step 3](#step-3-triage) |
| 4 | Dispatch 6 workers in parallel | [Step 4](#step-4-dispatch) |
| 5 | Synthesize verdict + **append to verdict log** | [Step 5](#step-5-synthesis) |
| — | Output format | [Output Format](#output-format) |
| — | Consolidation rules | [Consolidation Rules](#consolidation-rules) |

## When To Use

- User asks for full investment analysis of a US-listed equity ("analyze NVDA", "should I buy MSFT", "评估 AAPL", "is GOOG overvalued").
- User invokes the skill explicitly.
- The question is fundamental-analysis-oriented (business quality, financial health, valuation, recommendation).

## When NOT To Use

- **Technical analysis / chart patterns / trading signals** — different methodology; route to a future technical-analysis skill or decline.
- **Options analysis** — different instrument; this skill does not consider IV, Greeks, or strategies.
- **Crypto, FX, commodities** — completely different asset class.
- **Sector ETFs / mutual funds / index funds** — fundamental-analysis lens does not apply.
- **Macro / sector calls** — single-stock framework cannot answer "is tech a buy".
- **Non-US listings** — A-shares, HK-shares, foreign private issuers (20-F filers). Different disclosure standard; refuse explicitly.

## Workflow

### Step 1: Scope Identification

Extract the ticker from the user's prompt. Validate:

1. Is it a recognizable US listing (NYSE / Nasdaq / NYSE American symbol)?
2. Is it a domestic issuer (10-K filer) or a foreign private issuer (20-F filer)?
   - 20-F-only filers: out of scope. Reject with explanation.
3. Is it an ADR for a non-US company with primary listing elsewhere?
   - If the company files 10-K/10-Q as a US-domestic issuer (e.g., select dual-listed): in scope.
   - If filing 20-F only: out of scope.
4. Is it an A-share (3-digit / 6-digit Chinese symbol) or HK ticker (4-digit)?
   - Out of scope. Refuse with the standard message:
   ```
   This skill analyzes US-listed equities only (SEC 10-K/10-Q filers).
   A-shares, HK-shares, and 20-F-only foreign private issuers are out of scope.
   ```
5. Identify the question type:
   - **Full workup**: "analyze X", "should I buy X" → all 5 workers
   - **Valuation check**: "is X expensive", "what's a fair price for X" → 4 fundamentals workers + heavy valuation synthesis
   - **Specific concern**: "is X's balance sheet OK" → target the relevant worker; other workers still run for context but with lighter weighting

### Step 1.5: Select Depth

| Depth | When | Workers dispatched | Synthesis effort |
|---|---|---|---|
| **Lite** | Quick gut-check; user mentions a small position or hallway question | All 6 workers but Industry runs in **Lite-Industry mode** (moat name + share trend only, no full Porter); Peer Comparison runs **General panel only** | Minimal — Bull/Base/Bear ranges from multiples only |
| **Standard** | Default | All 6 workers, full mode | Full Good-Company score (sector-aware) + 4-method valuation + Bull/Base/Bear with calibrated probabilities |
| **Strict** | User explicitly asks for deep analysis OR position size > 5% of portfolio implied OR "long-term" / "core holding" mentioned | All 6 workers + extended cross-check between workers | Full + reverse-DCF stress test + cognitive-bias audit + 2nd-archetype check for multi-segment companies |

Default to Standard unless the prompt explicitly signals Lite or Strict.

**Important**: Even Lite mode runs all 6 workers (in lighter form). The previous behavior of completely skipping Industry in Lite was wrong — Industry determines 2 Good-Company checklist items (moat + TAM), and skipping it distorted the score. Lite now runs a focused Industry pass (moat type + share-trend one-liner) instead.

### Step 1.5b: Past Verdict Review

**Before proceeding to data acquisition**, check the verdict log for any prior analysis of this ticker:

```bash
LOG_FILE=~/.claude/projects/-Users-john-awesome-skills/memory/stock-analysis-verdicts.jsonl
test -f "$LOG_FILE" && grep "\"ticker\": \"<TICKER>\"" "$LOG_FILE" | tail -3 | jq
```

If a prior verdict exists:
- Read the most recent (and up to 3 prior) entries
- Compute time elapsed since prior verdict
- For each Bull/Bear assumption listed in the prior entry, mark whether it has been:
  - **VALIDATED** (assumption played out as expected)
  - **INVALIDATED** (assumption disproved by events)
  - **STILL OPEN** (insufficient time/data)
- Compute: current price vs the prior Bull/Base/Bear trajectory — which scenario is the current price closest to?
- Surface this as a **"Prior Verdict Tracking"** subsection in the final report

The new verdict must explicitly reckon with the prior one. If you arrive at a different verdict, state why — what new information, what assumption changes, what time elapsed.

If no prior verdict exists: skip this step.

See `references/verdict-log-protocol.md` for the full format and review procedure.

### Step 1.5c: Sector Archetype Classification

**Before applying the Good-Company checklist or valuation norms**, classify the company into exactly one archetype:

- **High-Growth SaaS / Software**
- **Mature Cash Cow / Consumer Staples**
- **Hyperscaler / Mega-Cap Tech Platform**
- **Capital-Intensive Industrial / Infrastructure / Utility**
- **Cyclical** (materials, auto, semiconductors, travel)
- **Bank / Insurance / Asset Manager (Financials)**
- **REIT**
- **Payment Network / Card Scheme / Transaction Processor** (MA, V, AXP-network, PYPL, processors)

Classification rules (see `references/sector-archetypes.md` for full taxonomy):
- Look at revenue mix, gross margin, capex intensity, and dominant business model.
- If a company is materially multi-archetype (e.g., AMZN = Hyperscaler + Retail), pick the dominant by revenue (>60%) but flag the secondary archetype and run a secondary score on that segment in Strict mode.

**Apply only the threshold set from the matching archetype** in the Good-Company checklist (Step 5b) and the valuation norms (Step 5c). **Also load the archetype's Analytical Addendum and pass its `mandatory_line_items` + `specialist_checks` into the worker dispatch (Step 4) as REQUIRED checks** — this turns generalist coverage into sector depth (e.g., payment network → BUS-11 client incentives + EQ-15 VAS mix-shift become mandatory, and the valuation model uses a `revenue_bridge`). The prior version's SaaS-default thresholds (rev growth ≥15%, NRR>115%, Net Debt/EBITDA <2) systematically under-rated mature cash cows, utilities, banks, REITs, and cyclicals — that bias is now fixed by sector-aware scoring.

Document the archetype choice in the final report's Execution Status section.

**Optionality test (run right after classification).** Compute the visible/established business's intrinsic value (a driver-model DCF on only the segments that earn revenue today) ÷ market cap. If it is below ~30–40%, the stock is **option-dominated**: attach the **Optionality Overlay** (`references/sector-archetypes.md`). The overlay does NOT change the base archetype — it changes the *valuation structure*: Step 5c builds a **sum-of-the-parts** instead of relying on a single-entity target, reverse-DCF is demoted to sizing the option premium (never a mechanical downgrade), Step 5d sets probabilities from the **venture tree**, and the **segment-materiality rule** forces every material engine (e.g. a high-margin, fast-growing energy/storage segment) to be modeled, not mentioned. Tesla is the canonical case (visible ≈ 9% of price).

### Step 2: Data Acquisition

Fetch the standard data package before dispatching workers. Workers receive paths to local copies, not URLs.

**FIRST-HAND DATA RULE (mandatory).** Before falling back to any aggregator (stockanalysis.com, macrotrends, etc.), pull structured financials directly from SEC EDGAR's XBRL `companyfacts` API with the bundled pipeline:

```bash
python3 scripts/finlib/edgar.py fetch --ticker <TICKER> --out $TMPDIR/stock-analysis-<ticker>/financials.json
# offline / cached companyfacts: python3 scripts/finlib/edgar.py parse --facts <companyfacts.json> --out financials.json
```

`financials.json` carries, for **every reported figure, its source XBRL tag + period + form** (revenue, operating income, OCF, capex, D&A, SBC, accounts receivable + allowance, deferred revenue, RPO, shares, debt, cash). Add it to the manifest as `financials`. Aggregator sites are **fallback only**; any reported financial number that came from a search snippet (not from `financials.json` or the filing) must be tagged `second-hand` in the manifest. Concepts EDGAR does not expose as a flat value — notably **segment operating income** (dimensional) — land in `financials.json["gaps"]`; workers must then read the relevant 10-K **footnote directly**, never infer them from consolidated totals.

| Artifact | Primary source | Tool | Required for | Fallback |
|---|---|---|---|---|
| Latest 10-K | SEC EDGAR | `firecrawl-download` or `WebFetch` | All workers | Company IR page |
| Latest 10-Q | SEC EDGAR | `firecrawl-download` or `WebFetch` | All workers | — |
| Most recent earnings call transcript | Seeking Alpha (free tier) | `firecrawl-search` → download | Management worker | Company IR webcast (less reliable) |
| Current price + basic multiples (TTM PE, P/S, EV/EBITDA, market cap) | stockanalysis.com | `WebFetch` | Synthesis | Yahoo Finance via scrape |
| 10-year financial history (revenue, OCF, FCF, gross margin, etc.) | stockanalysis.com | `WebFetch` | Earnings-quality + balance-sheet workers | Macrotrends |
| Peer list (2–4 closest comparables) | 10-K Item 1 "Competition" + `WebSearch` | inline + WebSearch | Industry worker | manual selection |
| Analyst consensus (revenue/EPS estimates) | Yahoo Finance "Analysis" tab | scrape | Synthesis (cognitive-bias check) | Seeking Alpha |
| **Earnings-revision momentum (30/60/90 day NTM EPS revision direction + magnitude)** | Yahoo Finance "Analysis" tab; sell-side aggregators | scrape | Synthesis Step 5d (probability adjustment) | Manual count of recent target-price revisions |
| 12-month insider Form 4 activity | SEC EDGAR | `WebFetch` | Management worker | — |
| DEF 14A (latest proxy) | SEC EDGAR | `firecrawl-download` | Management worker | — |

Write all fetched artifacts to a scratch directory (e.g., `$TMPDIR/stock-analysis-<ticker>/`). Emit a `data-manifest.json`:

```json
{
  "ticker": "MSFT",
  "fetched_at": "2026-05-15T03:00:00Z",
  "filings": {
    "10K": {"path": "...", "fiscal_year": 2024, "filing_date": "2025-07-30"},
    "10Q": {"path": "...", "quarter": "Q1 FY26", "filing_date": "2025-10-30"},
    "DEF14A": {"path": "...", "filing_date": "2025-10-15"}
  },
  "transcripts": [{"path": "...", "quarter": "Q1 FY26", "date": "2025-10-29"}],
  "price_data": {"current": 412.30, "ttm_pe": 32.5, "fwd_pe": 28.1, "ev_ebitda": 22.4, "market_cap_b": 3060},
  "historicals": {"path": "...", "years": 10},
  "peers": ["GOOGL", "AAPL", "AMZN"],
  "insider_activity": {"path": "..."},
  "missing": []
}
```

If any artifact is missing, list it in `missing` with reason. Workers receive the manifest; they self-skip when their required data is in `missing`.

### Step 3: Triage

Decide which workers to dispatch using a 4-phase pass.

#### Phase A: Always-on (all depths — Lite runs lighter mode but no full skip)

- `stock-business-reviewer`
- `stock-earnings-quality-reviewer`
- `stock-balance-sheet-reviewer`
- `stock-management-reviewer`
- `stock-industry-reviewer` (Lite mode: moat name + share-trend only; Standard/Strict: full Porter analysis)
- **`stock-peer-comparison-reviewer` (NEW)** — independent 12-item ratio benchmark vs 2-4 peers; provides cross-validation for moat and market-share claims (Lite mode: General panel only; Standard/Strict: General + archetype-specific panel)

#### Phase B: Data-availability gating

Cross-check the manifest. If a worker's required data is in `missing`:

- 10-K missing → skip all 6 workers; report data-unavailable failure
- DEF 14A missing → mark management worker as `DEGRADED (no proxy)` but still dispatch (transcripts still useful)
- 10-year history missing → mark earnings-quality worker as `DEGRADED (trend analysis impacted)` but dispatch
- Transcripts missing → mark management worker as `DEGRADED (no call transcript)`
- Peer list missing → mark **both industry AND peer-comparison workers** as `DEGRADED (no peers)` and use sector-archetype-only norms
- Earnings revision data missing → synthesis Step 5d proceeds without momentum adjustment; note degradation

#### Phase C: Question-driven priority

If the user's question targets a specific dimension (e.g., "is the balance sheet safe"):
- Dispatch all 5 as usual
- In Step 5 synthesis, weight the targeted dimension's Findings more heavily; show the user explicitly why other dimensions matter for the full picture

#### Phase D: Sanity check — fabricated tickers

If you cannot find the ticker in SEC EDGAR's company database, do not synthesize. Return:
```
Ticker not found in SEC EDGAR. Verify the symbol and re-run.
```

### Step 4: Dispatch

**Critical**: Launch all selected workers in a single Agent tool batch (multiple Agent invocations in one message). Sequential dispatch breaks the parallelism that justifies the architecture.

Each Agent invocation receives a prompt with:

```
You are <worker-name>. Load your skill via the skills: field.
Ticker: <TICKER>
Depth: <Lite|Standard|Strict>
Archetype: <archetype> — apply its sector-archetypes.md Analytical Addendum (mandatory_line_items + specialist_checks) as REQUIRED, not optional.
Manifest: <path to data-manifest.json>
Filings available at: <scratch-dir>

Return only structured Findings per your skill's Output Format.
Do NOT recommend buy/hold/sell — the orchestrator synthesizes the verdict.
```

Workers run in parallel. Wait for all to return before proceeding.

### Step 5: Synthesis

This is the orchestrator's most important step. Do not delegate it to a worker.

#### 5a. Consolidate Worker Findings

- Collect Findings from all 6 workers.
- Deduplicate by Finding meaning (not just by ID). Cross-worker overlap is fine and often correct.
- Assign unified IDs `INV-NNN` while preserving worker prefixes (BUS, EQ, BS, MGT, IND, **P** for peer-comparison).
- Sort by severity High → Medium → Low, then by worker order.
- Apply volume caps: Lite = 8 max Findings, Standard = 15 max, Strict = 25 max. Truncate by suppressing Low.
- **Cross-reference Peer Comparison panel against Industry's moat / share claims**: if peer-comparison P-01 (revenue growth) is mid-panel but Industry says "gaining share," surface the conflict in the synthesis section. The peer comparison is the independent referee.

#### 5b. Good-Company Score — sector-aware (from `references/good-company-checklist.md` + `references/sector-archetypes.md`)

**Apply the threshold set from the archetype chosen in Step 1.5c.** The 10-item checklist structure is the same, but the actual thresholds (numbers and direction) vary per archetype:

1. Revenue growth — threshold per archetype (SaaS ≥15%, Mature ≥4%, Utility ≥3%, REIT FFO/share ≥4%, etc.)
2. Gross margin level — threshold per archetype's sector norm
3. Operating leverage — direction acceptable per archetype (Mature: stable OK; SaaS: positive required)
4. **FCF or alternative cash metric** — per archetype (SaaS: FCF growth; Mature: FCF/Revenue + coverage; REIT: AFFO; Bank: ROTCE)
5. **Cohort/retention or coverage metric** — per archetype (SaaS: NRR; Mature: dividend coverage; Bank: loan-loss coverage; REIT: occupancy)
6. Market share — same direction (rising or stable), sector-specific norm
7. **Balance sheet leverage** — Net Debt/EBITDA threshold per archetype (SaaS ≤1.5×; Mature ≤3×; Utility ≤5×; REIT ≤6×; Bank: CET1 cushion instead)
8. Management quality — qualitative across archetypes
9. Identifiable moat — 7-type taxonomy applies to all archetypes
10. TAM — sector-specific growth threshold

Scoring: PASS = 7+, "good company"; PASS = 9+, "high quality". Same scoring rubric across archetypes — only the underlying thresholds change.

**Required output**: document the archetype + threshold-set used so the score is auditable. Without this, the score is uninterpretable.

#### 5c. Valuation (from `references/valuation-methods.md` + sector-archetype norms)

**Build a driver model, don't hand-pick three P/Es.** Author a `model.json` (drivers each tagged `source: data|assumption`; anchors — revenue_0, op_margin_start, da_pct, capex_pct — fed from `financials.json`) and run `python3 scripts/finlib/valuation.py run --model model.json`. It outputs DCF, **reverse-DCF (what growth the current price implies)**, the three scenarios as one model's parameter sets, a **derived** terminal multiple (Gordon `(1+g)/(WACC−g)`, never typed), and a sensitivity table. **The report MUST disclose WACC, terminal g, reverse-DCF implied growth, and the sensitivity table** (valuation-methods.md § Mandatory disclosure), and reconcile DCF intrinsic value against the scenario target when they diverge >10% — a point estimate without these is illustrative, not analytical. If any anchor is an assumption it prints `grounding: LOW`. See `references/valuation-methods.md`.

**Option-dominated stocks (Optionality Overlay attached) — build a sum-of-the-parts (PRIMARY lens).** A single-entity scenario target cannot value a company whose price is mostly unproven future businesses. Author a `sotp.json` and run `python3 scripts/finlib/sotp.py run --model sotp.json` (valuation-methods.md Method 5): established engines as `fixed`/`multiple` legs (a material energy/storage segment **modeled** GWh×$/kWh×margin, not a one-line positive — segment-materiality rule), each venture as an `option` leg (TAM→share→take-rate→margin→exit × P(success)/time) with **low/base/high ranges**. The engine refuses un-sourced drivers and refuses a point-estimate option leg; the output is a per-share **distribution** plus `option_share_of_value` (modeled) and `market_implied_option_share` (~the % of price the market calls option) — never a single target. The gap between those two is the priced-for-perfection signal. Here reverse-DCF on the visible business only *sizes* the option premium; it is tautological that the visible business cannot justify the price, so it MUST NOT trigger the "implied growth infeasible → downgrade" reconciliation row below.

Run four methods in order. **Use archetype-specific valuation norms** (P/E ranges, EV/FCF ranges, dividend yield benchmarks) from `references/sector-archetypes.md` — NOT generic SaaS norms:

1. **Multiples**: PE, PEG, P/S, EV/EBITDA, EV/FCF (or archetype-specific alternatives like P/TBV for banks, P/FFO for REITs). For each:
   - Compare to historical percentile (5-year and 10-year)
   - Compare to peer median (using Peer Comparison Worker output for this)
   - Compare to archetype-norm range (NOT generic SaaS norm)

2. **Reverse-DCF**: derive the growth-and-margin assumptions implied by the current price. Use archetype-appropriate WACC (utilities 7-8%; banks 9-11% cost of equity; SaaS 9-10%) and archetype-appropriate terminal multiple. Flag if implied assumptions exceed historical track record or sector feasibility.

3. **DCF**: only as a sanity check. Source doc warns DCF has too much manipulation surface. For Mature Cash Cow archetype, perpetuity DCF (Gordon model) can be primary; for SaaS, never primary.

4. **Scenarios**: Bull/Base/Bear (see 5d).

**Cross-Method Reconciliation — strict rules** (replaces the previous "lean toward scenarios" fudge):

When the four methods produce conflicting signals, apply the following priority order:

| Disagreement Pattern | Tiebreaker |
|---|---|
| Multiples say "cheap" but Scenarios say "Watch/Hold" | **Scenarios win** — multiples reflect past; scenarios reflect forward fundamentals |
| Multiples say "expensive" but Scenarios say "Buy" | **Scenarios win IF assumptions feasible**; otherwise multiples win (overpaying for growth that may not arrive) |
| Reverse-DCF says "market implies impossible growth" | **Treat as Bear-confirming**; reduce verdict tier by one — **EXCEPT** when the Optionality Overlay is attached: then this is tautological (visible business never justifies an option stock's price), so it only *sizes* the premium and must NOT cut the tier |
| Reverse-DCF says "market implies modest growth" + Scenarios say "Buy" | **Both agree** — verdict is well-supported |
| Peer Comparison says "expensive vs peers" + Multiples say "cheap vs history" | Investigate **why**: company-specific issue or sector-wide derating? |

If you cannot reconcile, the default is **Hold** until the conflict is resolved — explicit "I don't know" is more honest than fudging.

#### 5d. Build Bull/Base/Bear (from `references/scenario-framework.md` + `references/scenario-probability-calibration.md`)

For each scenario, specify:
- 5-year revenue (or FFO/PPNR/etc per archetype) CAGR
- Terminal operating margin
- Terminal multiple (archetype-appropriate)
- **Probability weight assigned via the calibrated framework** (NOT the old ad-hoc Good-Company → weight mapping)
- Computed target price

**Probability assignment must show the work** (see `references/scenario-probability-calibration.md`):
- Anchor 1: archetype base rate (e.g., Hyperscaler Bull base rate 25-35%)
- Anchor 2: independent-assumption adjustment (each independent positive assumption above 1 reduces Bull by ~5pp)
- Anchor 3: mandatory disconfirming-evidence citation (for Bull ≥25%, cite specific real-world bear thesis and explain weight)

**Option-dominated stocks** — derive Bull/Bear from the **venture tree**, not pp-subtraction (see `references/scenario-probability-calibration.md`): an independent `P(success)` per venture (the SAME number used in the SOTP option legs); Bear = `Π(1−Pᵢ)` (visible-only); Bull = the value-dominant venture(s) succeeding; Base = residual. This replaces the "base rate −5pp −2pp" arithmetic for these names.

**Earnings-revision momentum adjustment** (see `references/earnings-revision-momentum.md`):
- Strong Positive momentum → Bull +5pp, Bear -5pp
- Mild Positive → Bull +2pp, Bear -2pp
- Mild Negative → Bull -2pp, Bear +2pp
- Strong Negative → Bull -5pp, Bear +5pp

Compute:
- **Weighted expected price** = Σ (scenario_price × probability)
- **Weighted expected return** = (weighted expected price − current price) / current price
- **Bear-to-current ratio** = bear price / current price

**Decision rule** (unchanged):
- Weighted return ≥ 50% AND Bear/Current ≥ 0.75 → **Strong Buy** odds
- Weighted return ≥ 30% AND Bear/Current ≥ 0.70 → **Buy** odds
- Weighted return ≥ 15% AND Bear/Current ≥ 0.80 → **Watch** odds (set an alert price)
- Otherwise → **Hold** or **Trim/Sell** if currently held

Note: the hard thresholds (50%/0.75, 30%/0.70, 15%/0.80) are themselves uncalibrated. They are the framework's current best guess; the verdict log enables future recalibration based on observed outcome distribution.

#### 5d-bis. 口径 / Calculation Lint Gate (MANDATORY — deterministic)

Do not trust LLM arithmetic or labels. Emit every multiple/ratio/margin to `metrics.json` (per entry: `id`, `claimed_label`, `stated_value`, `inputs`, `tags{basis,period,period_count}`, `is_trend_claim`), then run `python3 scripts/finlib/lint.py --metrics $TMPDIR/stock-analysis-<ticker>/metrics.json`. It (via `scripts/finlib/ratios.py`) catches: **label vs formula** (an `ev_*` multiple without `total_debt`+`cash_and_sti` is the P/FCF-as-EV/FCF error; EV = mktcap+debt−cash) · **internal consistency** (stated vs recomputed-from-inputs >2% → catches "capex/rev 50%" when inputs give 67%) · **single-period** (`period_count<4` on a leverage/trend claim → FAIL; use ≥4Q or TTM) · **口径 tags** (mixing GAAP/non-GAAP/core, TTM/FY → WARN). **Any FAIL blocks the report** — fix it, or tag the value `second-hand/unverified` and lower the dependent conclusion's confidence. Feed `inputs` from `financials.json` so the recompute is meaningful.

#### 5e. Cognitive-Bias Self-Check (from `references/cognitive-bias-gates.md`)

Run 6 binary checks; document each as PASS or FLAG:

1. **Anchoring**: Am I anchoring on past prices rather than intrinsic value? FLAG if "cheap" justification rests on historical price decline.
2. **Story bias**: Have I quantified the narrative (revenue, time horizon, probability)? FLAG if "AI-beneficiary" or similar appears without numbers.
3. **Confirmation**: Did at least one worker raise a substantive counter-thesis? FLAG if all workers agree without dissent.
4. **Overconfidence**: Am I more bullish than current sell-side consensus by > 20%? If yes, FLAG and justify the divergence specifically.
5. **Information edge**: this is public-information-only synthesis — no channel checks, IR access, or expert network. Carry the mandatory `信息优势声明` disclosure and cap conviction accordingly (no "analyst-grade" certainty on a public-only thesis). See `references/information-edge.md`.
6. **Consensus clone**: is the verdict ≈ consensus (same direction AND weighted price within ±10% of median) with no falsifiable variant view? FLAG → add a 变量观点 / Variant Perception statement (what the market prices in · where I differ · what would prove me wrong), or explicitly declare the call consensus-aligned. See `references/information-edge.md` §1b.
7. **Inverted rigor** (option-dominated names only): is the segment that drives the *largest* share of value the *least*-modeled thing in the report? FLAG if the option/venture value is a single judgment number with no SOTP, no ranges, no P(success). Being rigorous on the visible 10% while hand-waving the decisive 90% is the signature failure for these names — the SOTP (Step 5c) is the fix.

Any FLAG must be addressed in the final report — not buried.

#### 5f. Verdict and Conditions

Commit to one of:
- **Strong Buy** — high conviction; expected return > 50% with bounded downside
- **Buy** — good odds per decision rule
- **Watch** — set an alert price; not yet compelling
- **Hold** — currently fairly valued for current holders; not adding
- **Trim** — currently held but starting to deteriorate; reduce position
- **Sell** — thesis invalidated OR severely overvalued

Specify **invalidation conditions** — quantitative triggers for when to sell. Examples:
- "Sell if FCF turns negative for 2 consecutive quarters"
- "Sell if NRR falls below 110%"
- "Sell if Net Debt/EBITDA crosses 3.0×"

This implements the source doc's Part 3 §4 "卖出三种情形" pattern —论点被证伪 / 估值严重过高 / 找到更好的标的.

#### 5g. Append Verdict to Log (from `references/verdict-log-protocol.md`)

After committing the verdict, append one JSON Lines entry to:

```
~/.claude/projects/-Users-john-awesome-skills/memory/stock-analysis-verdicts.jsonl
```

The entry must include: ticker, company_name, verdict_date, verdict, conviction, current_price, target_base/bull/bear, weighted_expected_price, weighted_return_36mo, bear_to_current_ratio, horizon_months, archetype, good_company_score, key_bull_assumptions (3-5), key_bear_assumptions (3-5), invalidation_triggers, data_gaps_noted, cognitive_bias_flags, depth_mode, skill_version.

Use atomic append (`>>` shell redirect or equivalent). Confirm the write succeeded; surface a warning if it failed.

This persistent log is the feedback mechanism — the next analysis on this ticker will read this entry in Step 1.5b and explicitly reckon with what assumptions played out.

## Output Format

Render in user's invocation language (Chinese labels if user spoke Chinese; English otherwise). Both versions of the labels are listed below.

```
# <Ticker> — Investment Analysis Report

## Verdict / 顶层结论
<Strong Buy/Buy/Watch/Hold/Trim/Sell — single line, no hedging>
- Target price range: $X – $Y (Base: $Z)
- Weighted expected return: __% over <horizon, default 36 months>
- Conviction: <High/Medium/Low>
- **Sector archetype**: <SaaS / Hyperscaler / Mature Cash Cow / Capital-Intensive / Cyclical / Financials / REIT / Payment Network>

## Variant Perception / 变量观点 (mandatory)
- Market prices in / 市场当前定价: <reverse-DCF implied growth __% · consensus rating __ / median target $__>
- Where I differ (falsifiable) / 我的差异化判断: <one specific thesis/number/probability claim — or "无: consensus-aligned, value is independent confirmation">
- What would prove me wrong vs the crowd / 证伪点: <specific datapoint>

## Prior Verdict Tracking / 历史 verdict 跟踪 (if log shows past entry)
- Prior verdict (<date>, <X months ago>): <verdict> at $<price>, target $<base>, Bull $<bull>, Bear $<bear>
- Bull/Bear assumptions validation summary
- Current price vs prior trajectory

## Good-Company Score / 好公司评分: X / 10 (archetype: <name>)
| # | Item | Threshold (archetype) | Score | One-line evidence |
| 1 | Revenue growth | ≥<threshold>% | PASS/WEAK/FAIL | <evidence> |
... (10 items, sector-aware thresholds)

## Bull / Base / Bear / 三档情景
| Scenario | Revenue CAGR | Op Margin | Multiple | Target | Probability | Probability Anchors |
| Bull | __% | __% | __× | $__ | __% | base rate <X%> + assumption adj <±pp> + momentum adj <±pp>; disconfirming evidence: <citation> |
| Base | __% | __% | __× | $__ | __% | residual |
| Bear | __% | __% | __× | $__ | __% | base rate <X%> + assumption adj <±pp> + momentum adj <±pp>; confirming-of-Bull citation: <citation> |
- DCF disclosure (mandatory): WACC __% · terminal g __% · reverse-DCF implied growth __% (vs track-record __%) · sensitivity(revenue_cagr ±3pp): $__–$__. Base prob = residual. Reconcile DCF intrinsic vs target if >10% apart. A target without these is illustrative, not analytical.

## Sum-of-the-Parts / 分部加总估值 (option-dominated stocks only)
| Segment | Method | Value low–base–high | % of base equity | P(success) | Grounding |
| <auto> | fixed (DCF EV) | $__–$__–$__ | __% | — | OK |
| <energy> | multiple (GWh×$/kWh×margin) | $__–$__–$__ | __% | — | OK |
| <robotaxi> | option (TAM→share→take×P) | $__–$__–$__ | __% | __% (range) | LOW |
- Per-share distribution: $__ (low) – $__ (base) – $__ (high). Modeled option share of value: __%. **Market-implied option share: __%** (the ~90%-is-option figure). Gap = priced-for-perfection signal. Each venture leg shows its assumption chain + P(success) as a range, never a point.

## Earnings Revision Momentum / 卖方修正动量
- Momentum bucket: <Strong Positive / Mild Positive / Mild Negative / Strong Negative>
- 30-day NTM EPS revision: +/- X%
- Analysts raising vs cutting (30d): <X> up / <Y> down
- Probability adjustment applied: Bull <±pp>, Bear <±pp>

## Peer Comparison Summary / 同业对比摘要
- Archetype peer set: <ticker list>
- Items where target is BEST in panel: <list>
- Items where target is WORST in panel: <list>
- Cross-validation of moat/share claims: <which Industry-worker claims are supported by peer data>

## Worker Findings / 各维度发现
(sorted by severity High → Medium → Low; dedup'd; capped per depth mode)

### [High|Medium|Low] Short Title
- **ID**: `INV-NNN` (preserve worker prefix: BUS / EQ / BS / MGT / IND)
- **Citation**: filing section
- **Evidence**: from worker
- **Implication**: from worker

## Risks I Accept / 我接受的风险 (≥ 3, mandatory)
1. <strongest counter-thesis>
2. <secondary risk>
3. <…>

## Invalidation Conditions / 卖出触发器 (mandatory, ≥ 1 quantitative)
- <e.g., "Sell if FCF negative for 2 consecutive quarters">

## Data Coverage / 数据覆盖度
- Fetched: <list from manifest>
- Missing: <list from manifest with confidence impact>
- Workers degraded: <e.g., "management — DEGRADED (no proxy available)">

## Cognitive-Bias Self-Check / 认知偏差自检
- Anchoring: <PASS|FLAG + rationale>
- Story bias: <PASS|FLAG + rationale>
- Confirmation: <PASS|FLAG + rationale>
- Overconfidence: <PASS|FLAG + rationale>
- Information edge: <PASS|FLAG + rationale>
- Consensus clone / variant view: <PASS|FLAG + rationale>

## Verdict Log / 决策日志
- Logged to: ~/.claude/projects/-Users-john-awesome-skills/memory/stock-analysis-verdicts.jsonl
- Entry timestamp: <ISO 8601>
- Confirm: this verdict will be reviewed when ticker is re-analyzed
```

## Consolidation Rules

- **Deduplicate across workers**: e.g., if Earnings-Quality flags "negative FCF" (EQ-02) and Balance-Sheet flags "cash runway < 12 months" (BS-03), keep both — they are related but distinct mechanisms. If two workers report the same exact mechanism (rare but possible), merge into one Finding citing both worker prefixes.
- **Promote severity**: when a Finding is dependency-critical (e.g., balance sheet drives the Bear scenario floor), promote it one severity tier in the synthesis output.
- **Suppress contradictions**: if Industry says "moat is strong" but Earnings-Quality shows margin compression, do not suppress either — both go in, and the synthesis explains the tension (this is the conflict the user is paying you to surface).
- **Volume caps**: Lite ≤ 8, Standard ≤ 15, Strict ≤ 25. Truncate Low severity first.

## No-Workers-Returned-Findings Case

If all 6 workers return zero Findings (a structurally clean company):
- Good-Company score likely 9–10
- Surface positive observations the workers noted
- Verdict still required — usually Watch (clean but priced for perfection) or Buy (clean and reasonably priced)
- Do not pretend to find issues to look thorough

## Toolchain Risk Acknowledgment

This skill depends on web-scraped data from stockanalysis.com, Yahoo Finance, Seeking Alpha, and SEC EDGAR. **Any of these can change layout or rate-limit at any time**. The fallback chains in `data-acquisition-playbook.md` are documented but not continuously tested. If Step 2 data acquisition produces sparse output:

1. Check whether scraped pages returned empty content (silent failure)
2. Try the documented fallback source
3. If both fail, mark the missing artifact in the manifest's `missing` field
4. Workers self-degrade based on what's missing
5. The orchestrator notes data-coverage limitations explicitly in the final report's "Data Coverage" section

A degraded analysis with explicit gaps is more honest than a complete-looking analysis built on stale or missing data.

## Load References Selectively

- `references/sector-archetypes.md` — load during Step 1.5c to classify the archetype and obtain threshold sets.
- `references/data-acquisition-playbook.md` — load during Step 2 to confirm the SEC EDGAR URL pattern and the fallback chain when primary sources fail.
- `references/earnings-revision-momentum.md` — load during Step 2 (data) and Step 5d (probability adjustment) for analyst-revision tracking.
- `references/verdict-log-protocol.md` — load during Step 1.5b (read past verdict) and Step 5g (append new verdict).
- `references/good-company-checklist.md` — load during Step 5b to score the 10 items.
- `references/valuation-methods.md` — load during Step 5c for the multi-method valuation procedure including reverse-DCF and **Method 5 Sum-of-the-Parts** (`scripts/finlib/sotp.py`) for option-dominated stocks.
- `references/scenario-framework.md` — load during Step 5d for the Bull/Base/Bear structure.
- `references/scenario-probability-calibration.md` — load during Step 5d for the calibrated probability assignment framework.
- `references/cognitive-bias-gates.md` — load during Step 5e to run the 5 self-check questions; `references/information-edge.md` — the public-info honesty doctrine + the AI-advantaged edges (cross-section `scripts/finlib/crosssection.py`, monitoring `scripts/finlib/verdict_diff.py`).

## Review Discipline

You are the editor of a five-analyst report. Your value is not in re-doing each analyst's work — it is in committing a verdict. The source doc's strongest message: leadership wants a recommendation backed by structure, not a literature review. Take a position. Name the risk you accept. Commit to invalidation conditions. The user will override your verdict, and that is fine — but they cannot override "it depends".