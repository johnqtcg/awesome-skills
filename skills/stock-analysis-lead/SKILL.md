---
name: stock-analysis-lead
description: Orchestrate a US-stock investment analysis — classify sector archetype, fetch SEC filings, dispatch a tiered fan-out of six vertical equity-research agents (business model, earnings quality, balance sheet, management, industry, peer comparison) over a validated JSON findings contract, then synthesize a buy/hold/sell verdict with Bull/Base/Bear target ranges using sector-aware thresholds and an auditable probability-assignment procedure. Each verdict can persist to an opt-in JSON-Lines log so later analyses reckon with the prior view. Use when the user asks "should I buy AAPL", "analyze Microsoft", "is NVDA a good buy now", "美股目标价 / 估值 / 投资标的分析", "evaluate GOOGL", or wants any full US-equity workup on a named ticker. NOT for trading signals, technical analysis, options, crypto, ETFs, or macro/sector calls — single-stock fundamental analysis only. NOT for A-shares, HK-shares, or non-US listings — the framework is keyed to SEC filings and US GAAP and refuses them.
allowed-tools: Read, Grep, Glob, WebSearch, WebFetch, Bash, Agent
---

# Stock Analysis Lead — Orchestrator

## Purpose

You are the orchestrator for a Multi-Agent US-equity research workflow. Your job is to:

1. Identify the ticker and validate it is a US-listed equity
2. **Classify the company into a sector archetype** (SaaS / Hyperscaler / Mature Cash Cow / Capital-Intensive / Cyclical / Financial / REIT / Payment Network) — this determines the threshold set for the Good-Company checklist and valuation norms, and is **provisional** until the workers can challenge it
3. Fetch the standard data package (10-K, 10-Q, recent earnings call, current price, peer set, historical financials, **earnings-revision momentum**)
4. Run the optionality test — it needs market cap, so it cannot run before step 3
5. Triage: dispatch the **Tier-0 core** always, **Tier-1 conditional** workers only when their trigger fires
6. Launch the wave in a single Agent batch; run the **dispatch state machine** (validate → retry once → timeout → quorum) over the replies
7. Consolidate validated Findings and synthesize a **provisional** verdict using the "Good Company × Good Price" framework with an **auditable probability-assignment procedure**
8. **Only then** read the prior verdict on this ticker and reconcile — reading it earlier anchors the whole analysis
9. Append the verdict to the log (opt-in, portable path) so future analyses reckon with this one

**Critical rule**: You only fetch, triage, dispatch, and synthesize. You do NOT analyze fundamentals yourself — the workers do that. Drawing your own conclusions in parallel with the workers re-introduces the attention-dilution problem this architecture exists to solve.

**Two things are never done by judgment**: worker replies are accepted or rejected by `scripts/finlib/worker_contract.py`, and the run is publishable or not by `scripts/finlib/runbundle.py`. An orchestrator that eyeballs a worker's Markdown is the failure mode this version exists to remove.

## Quick Reference

| Step | What | Section |
|---|---|---|
| 1 | Identify ticker; validate US listing | [Step 1](#step-1-scope-identification) |
| 1.5 | Select depth (Lite / Standard / Strict) | [Step 1.5](#step-15-select-depth) |
| 1.5c | Classify sector archetype | [Step 1.5c](#step-15c-sector-archetype-classification) |
| 2 | Fetch the data package (incl. earnings revision) | [Step 2](#step-2-data-acquisition) |
| 2b | **Optionality test — needs market cap, so it runs after data** | [Step 2b](#step-2b-optionality-test) |
| 3 | Triage: Tier-0 core + Tier-1 conditional | [Step 3](#step-3-triage) |
| 4 | Dispatch in parallel; run the state machine | [Step 4](#step-4-dispatch) |
| 5 | Synthesize provisional verdict | [Step 5](#step-5-synthesis) |
| 5d-ter | **Evidence gate — pre-verdict; blocks synthesis** | [Step 5d-ter](#step-5d-ter-run-bundle-gate-mandatory--deterministic) |
| 5f-bis | **Prior verdict review — deliberately AFTER the provisional verdict** | [Step 5f-bis](#step-5f-bis-prior-verdict-review-blind-first) |
| 5g | **Publication gate — blocks the report** + log append | [Step 5g](#5g-append-verdict-to-log-from-referencesverdict-log-protocolmd) |
| — | Output format | [Output Format](#output-format) |
| — | Consolidation rules | [Consolidation Rules](#consolidation-rules) |

Step numbering is stable across releases (there is no `1.5b`; the past-verdict review that held that slot moved to 5f-bis). Other reference files cite these labels — do not renumber.

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
5. Identify the question **shape** — it feeds the Tier-1 triage triggers in Step 3:
   - **Full workup**: "analyze X", "should I buy X" → every Tier-1 trigger fires
   - **Valuation-shaped**: "is X expensive", "fair price", "cheap", "vs peers" → fires the peer-comparison trigger
   - **Moat-shaped**: "what's the moat", "losing share" → fires the peer-comparison trigger
   - **Stewardship-shaped**: capital allocation, M&A, buybacks, insiders, guidance credibility → fires the management trigger
   - **Specific concern**: "is X's balance sheet OK" → Tier-0 still runs in full; the targeted dimension is weighted more heavily in Step 5, and the report states why the others still matter

### Step 1.5: Select Depth

| Depth | When | Fan-out | Synthesis effort |
|---|---|---|---|
| **Lite** | Quick gut-check; small position or hallway question | **4 Tier-0 workers** with Industry in **Lite-Industry mode** (moat name + share trend, no Porter). Tier-1 workers only if their trigger fires | Minimal — Bull/Base/Bear ranges from multiples only |
| **Standard** | Default | Tier-0 (full mode) + both Tier-1 workers = **6** | Full Good-Company score (sector-aware) + 4-method valuation + Bull/Base/Bear with anchored probabilities |
| **Strict** | User asks for deep analysis OR position > 5% of portfolio implied OR "long-term" / "core holding" | Tier-0 + both Tier-1 = **6**, plus up to **3** conflict-triggered second-wave re-dispatches | Full + reverse-DCF stress test + cognitive-bias audit + 2nd-archetype check for multi-segment companies |

Default to Standard unless the prompt explicitly signals Lite or Strict. Tier membership and triggers are defined in `references/dispatch-protocol.md` Part 1 — that file is authoritative; this table is the summary.

**Lite is a real reduction, not a lighter costume.** The previous version dispatched all six workers at every depth, which made "Lite" cost nearly as much as Standard while still paying the compounded failure risk of six agents. Industry stays Tier-0 at every depth (it owns 2 Good-Company items — moat + TAM — so skipping it distorts the score); Management and Peer Comparison became Tier-1. When a Tier-1 worker does not run, the items it would have informed are scored `UNSCORED`, never guessed, and the report names the trigger that did not fire.

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

**The archetype is provisional until the workers report back.** You are choosing it from thin evidence, before any worker has read a filing, and every worker then analyzes against the thresholds you picked — so a misclassification here is a *correlated* error across all six, exactly what the parallel architecture is supposed to prevent. Every worker therefore carries an `archetype_challenge` channel (`references/worker-contract.md` § Archetype challenge). Handling is mandatory in Step 5a: one challenge → re-check and re-dispatch the affected workers if it holds; **two or more challenges naming the same alternative → your classification is presumed wrong**, re-classify and re-dispatch all Tier-0 workers. Never publish a verdict on a contested archetype.

For a materially multi-segment company, prefer **routing by segment** (run the archetype's thresholds against the segment they fit) over forcing one label onto the consolidated entity. Strict mode requires this; Standard flags it.

### Step 2: Data Acquisition

Fetch the standard data package before dispatching workers. Workers receive paths to local copies, not URLs.

**FIRST-HAND DATA RULE (mandatory).** Before falling back to any aggregator (stockanalysis.com, macrotrends, etc.), pull structured financials directly from SEC EDGAR's XBRL `companyfacts` API with the bundled pipeline:

```bash
python3 scripts/finlib/edgar.py fetch --ticker <TICKER> --out $TMPDIR/stock-analysis-<ticker>/financials.json
# offline / cached companyfacts: python3 scripts/finlib/edgar.py parse --facts <companyfacts.json> --out financials.json
```

`financials.json` carries, for **every reported figure, its source XBRL tag + period + form** (revenue, operating income, OCF, capex, D&A, SBC, accounts receivable + allowance, deferred revenue, RPO, shares, debt, cash). Add it to the manifest as `financials`. Aggregator sites are **fallback only**; any reported financial number that came from a search snippet (not from `financials.json` or the filing) must be tagged `second-hand` in the manifest. Concepts EDGAR does not expose as a flat value — notably **segment operating income** (dimensional) — land in `financials.json["gaps"]`; workers must then read the relevant 10-K **footnote directly**, never infer them from consolidated totals.

**Artifact list, per-source fetch strategy, fallback chains and the full `data-manifest.json` shape: `references/data-acquisition-playbook.md`** (§ Standard Data Package, § Manifest Format). Load it here rather than restating the table — a second copy of the source list is a second thing to drift.

Minimum manifest for the fan-out to proceed: `ticker` · `filings.10K` · `financials` (from `edgar.py`) · `price_data` · `peers` (2–4, or empty) · `missing[]` with a reason per gap. Write everything to `$TMPDIR/stock-analysis-<ticker>/run/`.

If any artifact is missing, list it in `missing` with reason. Workers receive the manifest; they self-skip when their required data is in `missing`.

### Step 2b: Optionality Test

**Runs here, not at classification time** — it divides the visible business's intrinsic value by market cap, and neither input exists before Step 2. The previous version placed it right after archetype classification, where the market cap and segment values it needs had not been fetched yet, so it could only be answered by impression.

Compute the visible/established business's intrinsic value (a driver-model DCF on only the segments that earn revenue today, anchored on `financials.json`) ÷ market cap. If it is below ~30–40%, the stock is **option-dominated**: attach the **Optionality Overlay** (`references/sector-archetypes.md`). The overlay does NOT change the base archetype — it changes the *valuation structure*: Step 5c builds a **sum-of-the-parts** instead of relying on a single-entity target, reverse-DCF is demoted to sizing the option premium (never a mechanical downgrade), Step 5d sets probabilities from the **venture tree**, and the **segment-materiality rule** forces every material engine (e.g. a high-margin, fast-growing energy/storage segment) to be modeled, not mentioned. Tesla is the canonical case (visible ≈ 9% of price).

If segment operating income is in `financials.json["gaps"]` (EDGAR does not expose dimensional concepts as flat values), read the 10-K segment footnote directly before running this test. Do not infer segment economics from consolidated totals — that turns the whole overlay decision into a guess.

### Step 3: Triage

**Triage is computed, not judged.** `dispatch.py plan` derives the fan-out from depth + manifest + question shape and writes the initial `dispatch-log.json`:

```bash
python3 scripts/finlib/dispatch.py plan --log run/dispatch-log.json --ticker <TICKER> \
  --depth <Lite|Standard|Strict> --archetype "<archetype>" \
  --manifest run/data-manifest.json --question-shape <full|valuation|moat|stewardship|specific>
```

It refuses to plan when the manifest has no 10-K, and records every Tier-1 worker it did **not** dispatch together with the trigger that failed to fire. `references/dispatch-protocol.md` Part 1 documents the rules; `plan` decides them. Summary:

#### Phase A: Tier-0 core — always dispatched, every depth

`stock-business-reviewer` · `stock-earnings-quality-reviewer` · `stock-balance-sheet-reviewer` · `stock-industry-reviewer` (Lite: moat name + share trend only; Standard/Strict: full Porter). These four own every Good-Company item no other worker can supply, so dropping one makes the score uninterpretable rather than merely thinner.

#### Phase B: Tier-1 conditional — dispatched only when a trigger fires

| Worker | Trigger |
|---|---|
| `stock-management-reviewer` | Standard/Strict · OR DEF 14A + transcript both present · OR stewardship-shaped question · OR archetype ∈ {Mature Cash Cow, Capital-Intensive, Financials, REIT} |
| `stock-peer-comparison-reviewer` | Standard/Strict · OR (≥2 peers in manifest AND valuation- or moat-shaped question) |

Record the trigger that fired — or the one that did not — in `dispatch-log.json`. A skipped Tier-1 worker means its Good-Company items are `UNSCORED`, never guessed.

#### Phase C: Data-availability gating

Cross-check the manifest. If a worker's required data is in `missing`:

- 10-K missing → dispatch nothing; report data-unavailable failure
- DEF 14A missing → management worker `DEGRADED (no proxy)`, still dispatched (transcripts still useful)
- 10-year history missing → earnings-quality worker `DEGRADED (trend analysis impacted)`, still dispatched
- Transcripts missing → management worker `DEGRADED (no call transcript)`
- Peer list missing → industry worker `DEGRADED (no peers)`; the peer-comparison **trigger cannot fire** — do not dispatch it into a comparison it has no data for
- Earnings-revision data missing → Step 5d proceeds without the momentum adjustment; note the degradation

#### Phase D: Sanity check — fabricated tickers

If you cannot find the ticker in SEC EDGAR's company database, do not synthesize. Return:
```
Ticker not found in SEC EDGAR. Verify the symbol and re-run.
```

### Step 4: Dispatch

**Critical**: launch the whole first wave in a single Agent tool batch (multiple Agent invocations in one message). Sequential dispatch forfeits the parallelism that justifies the architecture.

Each Agent invocation receives:

```
You are <worker-name>. Load your skill via the skills: field.
Ticker: <TICKER>
Depth: <Lite|Standard|Strict>
Archetype: <archetype> — apply its sector-archetypes.md Analytical Addendum
  (mandatory_line_items + specialist_checks) as REQUIRED, not optional.
  Required checks for this run: <comma-separated IDs, or "none">
  If the evidence contradicts this archetype, file an archetype_challenge
  rather than analyzing against thresholds you believe are wrong.
Manifest: <path to data-manifest.json>
Filings available at: <scratch-dir>

Write your Markdown report, then end with EXACTLY ONE fenced block tagged
findings-json carrying Worker Findings Contract v1. The schema is in your skill's
Output Format section, pre-filled with your worker name, prefix and checklist
total; the full spec and error codes are in
stock-analysis-lead/references/worker-contract.md. Required keys:
  contract_version worker prefix status [status_reason unless OK] depth_mode
  archetype_applied archetype_challenge findings positives data_gaps
  checklist_coverage mandatory_checks_run
Each finding: id severity title citation{source,locator,fiscal_period}
  evidence implication confidence.

I synthesize the verdict FROM THIS BLOCK ONLY — anything you state in prose but
omit here does not reach the report. A citation must be the object form; a bare
string fails validation. source "aggregator" forces confidence "second-hand".
Echo depth_mode and archetype_applied back exactly as given above.
Do NOT recommend buy/hold/sell — I synthesize the verdict.
```

#### Validate every reply before consuming it

```bash
python3 scripts/finlib/worker_contract.py validate \
  --reply run/workers/<worker>.md --expect-worker <worker> \
  --expect-depth <depth> --expect-archetype "<archetype>" --require-checks <IDs>
```

A FAIL is never silently absorbed. Branch on the error class (`references/dispatch-protocol.md` Part 2):

- **Retryable** (formatting: `MISSING_BLOCK`, `BAD_JSON`, `BAD_CITATION`, `COVERAGE_INCOMPLETE`, …) → **one** re-dispatch with the validator's error list appended and the instruction *"re-emit a compliant block; do not re-run the research."*
- **Non-retryable** (`WORKER_MISMATCH`, `DEPTH_MISMATCH`, `ARCHETYPE_MISMATCH`) → the dispatch was wrong, not the reply. Fix the dispatch and launch a fresh attempt.
- Retries exhausted → `FAILED`. No model fallback: a different model is a different analyst, and swapping one in silently makes the run unauditable.

#### Do not wait for the full set

Per-worker budget: **Lite 5 min · Standard 10 min · Strict 15 min**. Consolidate as soon as the **quorum** is met; a worker still running past its budget is `TIMEOUT` and the report proceeds without it. One stalled agent must never hold the whole analysis.

| Tier-0 workers validated | What may be published |
|---|---|
| 4 of 4 | full verdict |
| 3 of 4 | **degraded verdict** — conviction capped **Low**, missing items `UNSCORED`, and the gap stated in the Verdict line itself, e.g. `Buy (DEGRADED — industry dimension uncovered, conviction capped Low)` |
| ≤2 of 4 | **no verdict.** Report what was gathered and name the uncovered dimensions |
| balance-sheet worker not validated | Bear floor unsupported → cap at `Watch`; no Buy / Strong Buy |
| any worker `REFUSED` | stop; surface to the user before synthesizing |

#### Record every event through the state machine

`run/dispatch-log.json` is owned by `dispatch.py`, not hand-written. Record each event as it happens; illegal ones are refused with a non-zero exit and an explanation:

```bash
python3 scripts/finlib/dispatch.py record --log run/dispatch-log.json \
  --worker <worker> --event launched
python3 scripts/finlib/dispatch.py record --log run/dispatch-log.json \
  --worker <worker> --event validated --status OK --duration 214
python3 scripts/finlib/dispatch.py record --log run/dispatch-log.json \
  --worker <worker> --event invalid --error-code MISSING_BLOCK
python3 scripts/finlib/dispatch.py record --log run/dispatch-log.json \
  --worker <worker> --event retry --error-code MISSING_BLOCK
```

Events: `launched` · `returned` · `validated` (with `--status`) · `invalid` · `timeout` · `crashed` · `retry` · `failed` · `dispatched` (second wave, needs `--reason`). The machine refuses a second retry, a retry after a non-retryable code, a `failed` before the granted retry is used, and events against a worker whose trigger never fired.

**Write the superseded reply to `run/workers/<worker>.attempt<N>.md`.** The gate requires it for every attempt beyond the first — otherwise "we retried after a MISSING_BLOCK" is an assertion nobody can check.

The Data Coverage section renders from this log, and the bundle gate cross-checks it against the files on disk. `dispatch.py` is the referee, not the runner: you are still the executor, but the log can no longer describe a history the protocol forbids.

### Step 5: Synthesis

This is the orchestrator's most important step. Do not delegate it to a worker.

#### 5a. Consolidate Worker Findings

Consolidation is **deterministic** — do not merge, sort, or cap by hand:

```bash
python3 scripts/finlib/worker_contract.py consolidate \
  --replies run/workers/*.md --cap <8 Lite | 15 Standard | 25 Strict>
```

It merges identical mechanisms across workers (keeping both prefixes), sorts High → Medium → Low then by worker order, truncates Low first and **never drops a High to fit the cap**, and exits non-zero if any reply failed validation — so a dropped dimension cannot pass for a complete fan-out. Preserve worker prefixes (BUS, EQ, BS, MGT, IND, **P**) in the rendered IDs.

Then apply the two judgment steps the tool cannot:

- **Handle `archetype_challenges`.** If `archetype_contested` is true (≥2 workers naming the same alternative), re-classify and re-dispatch all Tier-0 workers before going further. A single challenge: re-check it against `sector-archetypes.md`; if it holds, the thresholds change, so re-dispatch the affected workers rather than keeping thresholds you now believe are wrong.
- **Run the second wave** where consolidation surfaces a specific contradiction (`references/dispatch-protocol.md` Part 1 Tier 2) — e.g. Industry claims share gains while `P-01` revenue growth is at or below peer median. Cap: 2 re-dispatches (Strict: 3). Beyond that the conflict is not resolvable by more agents: record it as an unresolved tension and let the Step 5c tiebreaker default the verdict to **Hold**.

The peer comparison is the independent referee — where the stories and the receipts disagree, both go in the report.

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

**Build a driver model; do not hand-pick three P/Es.** Author `model.json` (every driver tagged `source: data|assumption`; anchors — revenue_0, op_margin_start, da_pct, capex_pct — fed from `financials.json`) and run `python3 scripts/finlib/valuation.py run --model model.json`. It emits DCF, reverse-DCF, the three scenarios as one model's parameter sets, a **derived** terminal multiple (Gordon `(1+g)/(WACC−g)`, never typed), and a sensitivity table. The report MUST disclose WACC, terminal g, reverse-DCF implied growth and the sensitivity table, and reconcile DCF intrinsic value against the scenario target when they diverge >10%. An unsourced anchor prints `grounding: LOW`.

**Record the model digest in `verdict.json`** (`model.model_json_sha256` = sha256 of `model.json`). The publication gate requires it: a target with no digest cannot be tied to the numbers that produced it.

**Option-dominated names (Optionality Overlay attached) — sum-of-the-parts is the PRIMARY lens.** Author `sotp.json`, run `python3 scripts/finlib/sotp.py run --model sotp.json` (valuation-methods.md Method 5): established engines as `fixed`/`multiple` legs (a material energy/storage segment **modeled** GWh×$/kWh×margin, never a one-line positive — segment-materiality rule), each venture as an `option` leg (TAM→share→take-rate→margin→exit × P(success)/time) with low/base/high ranges. The engine refuses un-sourced drivers and point-estimate option legs. Output is a per-share **distribution** plus `option_share_of_value` (modeled) and `market_implied_option_share`; the gap between them is the priced-for-perfection signal. Reverse-DCF on the visible business only *sizes* the premium here — it is tautological that the visible business cannot justify the price, so it MUST NOT trigger the downgrade row below.

Run the four methods in order, using **archetype-specific norms** from `references/sector-archetypes.md` — never generic SaaS norms: **(1) Multiples** (PE, PEG, P/S, EV/EBITDA, EV/FCF, or P/TBV for banks, P/FFO for REITs) each compared to 5- and 10-year historical percentile, peer median (from the Peer worker), and the archetype range. **(2) Reverse-DCF** with archetype-appropriate WACC (utilities 7–8%; banks 9–11% cost of equity; SaaS 9–10%); flag implied assumptions that exceed the track record or sector feasibility. **(3) DCF** as a sanity check only — perpetuity DCF may be primary for Mature Cash Cow, never for SaaS. **(4) Scenarios** (5d).

**Cross-Method Reconciliation — strict tiebreakers:**

| Disagreement | Tiebreaker |
|---|---|
| Multiples "cheap", Scenarios "Watch/Hold" | **Scenarios win** — multiples reflect the past |
| Multiples "expensive", Scenarios "Buy" | **Scenarios win IF assumptions feasible**; otherwise multiples win |
| Reverse-DCF: "market implies impossible growth" | **Bear-confirming**; cut the verdict one tier — **EXCEPT** under the Optionality Overlay, where it is tautological and must not cut |
| Reverse-DCF "modest growth" + Scenarios "Buy" | **Both agree** — well-supported |
| Peer says "expensive vs peers", Multiples say "cheap vs history" | Investigate: company-specific or sector-wide derating? |

If you cannot reconcile, the verdict is **Hold** — an explicit "I don't know" beats a fudge.

#### 5d. Build Bull/Base/Bear (from `references/scenario-framework.md` + `references/scenario-probability-calibration.md`)

Per scenario: 5-year revenue (or FFO/PPNR/etc per archetype) CAGR · terminal operating margin · archetype-appropriate terminal multiple · probability from the anchored procedure · computed target price.

**Naming discipline.** This is an **auditable probability-assignment procedure**, not an empirically calibrated one. The archetype figures are *judgment priors*, not measured frequencies, and the buy thresholds below have never been validated against outcomes. Say "archetype prior" in the report; never present a number built on one as empirically derived. `scripts/finlib/calibration.py` turns priors into calibrated numbers once ≥10 matured verdicts accumulate — until then, nothing here is calibrated.

**Show the work** — three anchors (detail: `scenario-probability-calibration.md`): archetype prior · independent-assumption adjustment (each independent positive assumption beyond the first cuts Bull ~5pp) · mandatory disconfirming-evidence citation for Bull ≥25%. **Option-dominated names** use the **venture tree** instead of pp-subtraction: an independent `P(success)` per venture (the same number as its SOTP option leg), Bear = `Π(1−Pᵢ)` (visible-only), Bull = the value-dominant venture(s) succeeding, Base = residual. **Earnings-revision momentum** then shifts Bull/Bear by ±5pp (Strong) or ±2pp (Mild), per `earnings-revision-momentum.md`.

Compute weighted expected price `Σ(price × prob)`, weighted expected return, and bear-to-current ratio. **These must reconcile**: `verdictlog.py validate` rejects an entry whose `weighted_expected_price` is not reproducible from its own probabilities, so record the numbers you actually used.

**Decision rule:** weighted return ≥50% and Bear/Current ≥0.75 → **Strong Buy** odds · ≥30% and ≥0.70 → **Buy** · ≥15% and ≥0.80 → **Watch** (set an alert price) · otherwise **Hold**, or **Trim/Sell** if held. Apply the Step 4 quorum ceilings on top.

These thresholds (50/0.75, 30/0.70, 15/0.80) are themselves uncalibrated — the framework's current best guess. Recalibration is executable, not aspirational: `python3 scripts/finlib/calibration.py report --prices prices.json` compares assigned probabilities against realised scenarios and refuses to conclude on fewer than 10 matured verdicts.

#### 5d-bis. 口径 / Calculation Lint Gate (MANDATORY — deterministic)

Do not trust LLM arithmetic or labels. Emit every multiple/ratio/margin to `metrics.json` (per entry: `id`, `claimed_label`, `stated_value`, `inputs`, `tags{basis,period,period_count}`, `is_trend_claim`), then run `python3 scripts/finlib/lint.py --metrics $TMPDIR/stock-analysis-<ticker>/metrics.json`. It (via `scripts/finlib/ratios.py`) catches: **label vs formula** (an `ev_*` multiple without `total_debt`+`cash_and_sti` is the P/FCF-as-EV/FCF error; EV = mktcap+debt−cash) · **internal consistency** (stated vs recomputed-from-inputs >2% → catches "capex/rev 50%" when inputs give 67%) · **single-period** (`period_count<4` on a leverage/trend claim → FAIL; use ≥4Q or TTM) · **口径 tags** (mixing GAAP/non-GAAP/core, TTM/FY → WARN). **Any FAIL blocks the report** — fix it, or tag the value `second-hand/unverified` and lower the dependent conclusion's confidence. Feed `inputs` from `financials.json` so the recompute is meaningful. Write the linter's output to `run/lint.json` — the bundle gate below treats a recorded FAIL as blocking, and an absent `lint.json` as no evidence the gate ran.

#### 5d-ter. Run-Bundle Gate (MANDATORY — deterministic)

The report claims to rest on the workers' evidence. Without that evidence on disk, the claim is unfalsifiable — a reader cannot distinguish a faithful synthesis from an invented one, and no run can be replayed as a regression. Every run therefore writes a bundle (layout: `references/dispatch-protocol.md` Part 3) to `$TMPDIR/stock-analysis-<ticker>/run/`, containing the manifest, `financials.json`, `dispatch-log.json`, **every worker's raw reply verbatim plus its extracted payload**, `consolidated.json`, the model/SOTP inputs and outputs, `metrics.json` + `lint.json`, `verdict.json`, and `report.md`.

**The gate runs in two stages, because the artifacts do not all exist yet at this point.** The previous version demanded `verdict.json` here, which Step 5f has not written — following the documented order could only fail.

```bash
# here, at 5d-ter: may I synthesize a verdict from this evidence?
python3 scripts/finlib/runbundle.py check --run $TMPDIR/stock-analysis-<ticker>/run --stage evidence
```

`--stage evidence` requires the manifest, `financials.json`, `dispatch-log.json`, `consolidated.json`, and every dispatched worker's raw reply **plus** its extracted payload. The `--stage publication` run happens after Step 5g (below) and adds `metrics.json`, `lint.json`, `verdict.json` and `report.md`.

Every requirement is fail-closed — nothing that changes whether the report is trustworthy is a warning. Beyond presence the gate checks that the artifacts **agree**: each `<worker>.json` equals the payload actually in `<worker>.md`; `consolidated.json` is reproducible by re-running consolidation; the log's states, attempt counts, tiers, triggers and second-wave cap are legal; no worker is left mid-flight; and the quorum is **recomputed** from states rather than read from the log's own summary, which would otherwise be self-certifying.

#### 5e. Cognitive-Bias Self-Check (from `references/cognitive-bias-gates.md`)

Run the binary checks below; document each as PASS or FLAG. Checks 1-6 apply to every run; check 7 applies only to option-dominated names:

1. **Anchoring**: Am I anchoring on past prices rather than intrinsic value? FLAG if the "cheap" justification rests on a historical price decline. Note that the structural anchor — reading the prior verdict before analyzing — is removed by design in this version: 5f-bis runs *after* the provisional verdict, so this check no longer has to detect an anchor the workflow itself installed. If the prior verdict did move your verdict, that belongs in Prior Verdict Tracking, not here.
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

This verdict is **provisional** until 5f-bis. Apply the quorum caps from Step 4: a degraded quorum carries the qualifier in the Verdict line, and a missing balance-sheet worker caps the verdict at `Watch`.

Specify **invalidation conditions** — quantitative triggers for when to sell. Examples:
- "Sell if FCF turns negative for 2 consecutive quarters"
- "Sell if NRR falls below 110%"
- "Sell if Net Debt/EBITDA crosses 3.0×"

This implements the source doc's Part 3 §4 "卖出三种情形" pattern —论点被证伪 / 估值严重过高 / 找到更好的标的.

#### 5f-bis. Prior Verdict Review — blind first (from `references/verdict-log-protocol.md`)

**Read the prior verdict only now, after 5f has committed a provisional verdict.** The previous version read it at Step 1.5b, before data acquisition — which handed the whole analysis an anchor and then asked the Step 5e anchoring self-check to detect it. Those two instructions were in direct tension, and the earlier one wins in practice. Blind-first resolves it: this run's judgment is formed independently, *then* compared.

```bash
python3 scripts/finlib/verdictlog.py read --ticker <TICKER> --limit 3
```

If a prior verdict exists:

- State its date, verdict, price, targets, and conviction.
- Mark each prior Bull/Bear assumption **VALIDATED** / **INVALIDATED** / **STILL OPEN**.
- Locate the current price against the prior Bull/Base/Bear trajectory.
- Diff the two entries mechanically: `python3 scripts/finlib/verdict_diff.py --prev prior.json --new verdict.json`.
- **If the provisional verdict differs from the prior one, say why** — what new information, what assumption changed, how much time elapsed. If it is the same, say what would have changed it.
- **If reading the prior verdict changes your provisional verdict, that revision is itself reportable.** Record the before/after in Prior Verdict Tracking. A silent revision is indistinguishable from anchoring.

If no prior verdict exists, or persistence was never opted into, say so and skip.

#### 5g. Append Verdict to Log (from `references/verdict-log-protocol.md`)

Persistence is **opt-in** and the path is resolved, never hardcoded — the previous version wrote to one developer's personal Claude project directory on every run:

```bash
python3 scripts/finlib/verdictlog.py path                      # show where it would go
python3 scripts/finlib/verdictlog.py init                      # opt in (once)
python3 scripts/finlib/verdictlog.py validate --entry run/verdict.json
python3 scripts/finlib/verdictlog.py append  --entry run/verdict.json
```

Resolution order: `$STOCK_VERDICT_LOG` → `$XDG_STATE_HOME/stock-analysis/` → `./.stock-analysis/` (if present) → `~/.local/state/stock-analysis/`. If the directory does not exist, `append` **refuses** rather than creating one: nothing writes the user's investment views to disk without them asking. Report that the verdict was not persisted and move on. Appends take an exclusive lock, so a concurrent run fails loudly instead of interleaving a torn line.

**Run the publication gate before showing anything to the user:**

```bash
python3 scripts/finlib/runbundle.py check --run $TMPDIR/stock-analysis-<ticker>/run --stage publication
```

This is the second half of the 5d-ter gate. On top of the evidence checks it requires `metrics.json`, `lint.json`, `verdict.json` and `report.md`, and it additionally verifies that `report.md` carries **every** consolidated finding ID (a synthesis that dropped surviving evidence fails), that a recorded model digest matches `model.json` on disk (so the targets provably came from that model), that a degraded quorum carries conviction `Low`, and that the verdict is one the quorum permits. FAIL blocks publication.

Schema **v3** (`references/verdict-log-protocol.md`) adds the fields v2 omitted: `prob_bull` / `prob_base` / `prob_bear`, the `probability_anchors` breakdown, `dcf{wacc, terminal_g, reverse_dcf_implied_growth}`, `model` (engine + input digest), `peer_set`, `momentum{bucket, adjustment_pp}`, `sotp`, `workers_validated`, and `quorum`. Without these the Calibration Loop asked for an average Bull probability its own log did not store. `validate` enforces that the three probabilities sum to 1 and that `weighted_expected_price` is reproducible from them — a log recording probabilities that never produced the target would make calibration audit numbers no analysis used.

## Output Format

Full template: **`references/output-format.md`** — load it before rendering. Render in the user's invocation language (Chinese labels if they spoke Chinese; English otherwise); the reference carries both label sets.

Mandatory blocks, in order: Verdict / 顶层结论 · Variant Perception / 变量观点 · Prior Verdict Tracking / 历史 verdict 跟踪 (if a prior entry exists) · Good-Company Score / 好公司评分 · Bull / Base / Bear / 三档情景 (with the DCF disclosure row) · Sum-of-the-Parts / 分部加总估值 (option-dominated only) · Earnings Revision Momentum / 卖方修正动量 · Peer Comparison Summary / 同业对比摘要 · Worker Findings / 各维度发现 · Risks I Accept / 我接受的风险 (≥3) · Invalidation Conditions / 卖出触发器 (≥1 quantitative) · Data Coverage & Dispatch Log / 数据覆盖度与调度记录 · Cognitive-Bias Self-Check / 认知偏差自检 · Verdict Log / 决策日志.

**The Worker Findings section is machine-audited.** `report_audit.py` diffs it against `consolidated.json` field by field — each finding's severity, its citation `locator`, and the worker's `evidence` and `implication` **verbatim**. You may add prose around them; you may not substitute them. Every consolidated finding appears exactly once, and no finding appears that consolidation did not produce.

## Consolidation Rules

- **Deduplicate across workers**: e.g., if Earnings-Quality flags "negative FCF" (EQ-02) and Balance-Sheet flags "cash runway < 12 months" (BS-03), keep both — they are related but distinct mechanisms. If two workers report the same exact mechanism (rare but possible), merge into one Finding citing both worker prefixes.
- **Promote severity**: when a Finding is dependency-critical (e.g., balance sheet drives the Bear scenario floor), promote it one severity tier in the synthesis output.
- **Suppress contradictions**: if Industry says "moat is strong" but Earnings-Quality shows margin compression, do not suppress either — both go in, and the synthesis explains the tension (this is the conflict the user is paying you to surface).
- **Volume caps**: Lite ≤ 8, Standard ≤ 15, Strict ≤ 25 — enforced by `worker_contract.py consolidate --cap`, which truncates Low first and never drops a High to fit.

## No-Workers-Returned-Findings Case

If every dispatched worker returns zero Findings (a structurally clean company):
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

- `references/sector-archetypes.md` — load during Step 1.5c to classify the archetype and obtain threshold sets, and during Step 2b for the Optionality Overlay.
- `references/data-acquisition-playbook.md` — load during Step 2 to confirm the SEC EDGAR URL pattern and the fallback chain when primary sources fail.
- `references/earnings-revision-momentum.md` — load during Step 2 (data) and Step 5d (probability adjustment) for analyst-revision tracking.
- `references/output-format.md` — load before rendering the report; the Worker Findings section it specifies is machine-audited field-by-field by `scripts/finlib/report_audit.py`, so the shape is a contract.
- `references/worker-contract.md` — load during Step 4 (dispatch: the exact `findings-json` schema) and Step 5a (consolidation + archetype-challenge handling).
- `references/dispatch-protocol.md` — load during Step 3 (triage tiers) and Step 4 (state machine, retry, timeout, quorum, budgets, run-bundle layout).
- `references/verdict-log-protocol.md` — load during Step 5f-bis (read prior verdict) and Step 5g (append new verdict).
- `references/good-company-checklist.md` — load during Step 5b to score the 10 items.
- `references/valuation-methods.md` — load during Step 5c for the multi-method valuation procedure including reverse-DCF and **Method 5 Sum-of-the-Parts** (`scripts/finlib/sotp.py`) for option-dominated stocks.
- `references/scenario-framework.md` — load during Step 5d for the Bull/Base/Bear structure.
- `references/scenario-probability-calibration.md` — load during Step 5d for the anchored probability-assignment procedure (archetype priors, assumption adjustment, mandatory disconfirming citation) and the executable Calibration Loop.
- `references/cognitive-bias-gates.md` — load during Step 5e to run the self-check gates it documents (Gates 1-6 always, Gate 7 for option-dominated names); `references/information-edge.md` — the public-info honesty doctrine + the AI-advantaged edges (cross-section `scripts/finlib/crosssection.py`, monitoring `scripts/finlib/verdict_diff.py`).

## Review Discipline

You are the editor of a multi-analyst report (four to six workers, depending on depth and triggers). Your value is not in re-doing each analyst's work — it is in committing a verdict. The source doc's strongest message: leadership wants a recommendation backed by structure, not a literature review. Take a position. Name the risk you accept. Commit to invalidation conditions. The user will override your verdict, and that is fine — but they cannot override "it depends".