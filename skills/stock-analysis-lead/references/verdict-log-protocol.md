# Verdict Log Protocol — Feedback Loop

Load this during Step 1 (after ticker validation) and Step 5f (verdict commitment).

**Why this exists**: A single-shot equity analysis without a feedback loop is not investor's-process — it's literature review. Without tracking which past verdicts came true, the framework cannot learn from misses. This protocol creates a persistent, queryable log of every verdict the orchestrator produces, plus the assumptions it rested on, so that:

1. When the same ticker is re-analyzed later, the orchestrator MUST review the prior verdict before producing a new one.
2. The log accumulates calibration data — over many verdicts, the framework can be audited for systematic Bull/Bear bias, sector blind spots, and base-rate errors.
3. The user can manually review verdicts at any time and see which Bull scenarios played out vs which didn't.

This is a minimal feedback mechanism — not a full portfolio system. But it converts the skill from a one-shot tool into a process with memory.

---

## File Location and Format

**The path is resolved, never hardcoded.** v2 baked one developer's personal Claude project directory into the skill, which broke on any other machine, project, or agent runtime. `scripts/finlib/verdictlog.py` is now the only sanctioned reader/writer and resolves in this order (first hit wins):

1. `--log <path>` argument
2. `$STOCK_VERDICT_LOG`
3. `$XDG_STATE_HOME/stock-analysis/verdicts.jsonl` (when `XDG_STATE_HOME` is set)
4. `./.stock-analysis/verdicts.jsonl` (when that directory exists — per-project logs)
5. `~/.local/state/stock-analysis/verdicts.jsonl`

```bash
python3 scripts/finlib/verdictlog.py path      # where would it go?
python3 scripts/finlib/verdictlog.py init      # opt in, once
```

**Persistence is opt-in.** If the resolved directory does not exist, `append` refuses and reports why rather than creating it. The log holds the user's investment views; nothing writes them to disk on the user's behalf without them asking. A refused append is reported in the Verdict Log section as `NOT PERSISTED` — it never silently succeeds or silently fails.

**Concurrency.** `append` takes an `O_EXCL` lock file for the duration of the write and `fsync`s. Two analyses running at once cannot interleave a torn line; the second fails loudly with the lock path.

**Format**: JSON Lines (one verdict per line), so appends never rewrite the file. Each line is independently parseable, and a corrupt line is skipped on read rather than killing the reader.

**Schema versioning.** Every line carries `schema_version`. Current: **`"3"`**. `verdictlog.py migrate --entry <old>.json` brings an older line forward; it **marks** absent fields in `fields_unavailable_at_write_time` rather than back-filling them, because a guessed probability would be read by the Calibration Loop as one the analysis actually assigned.

---

## Per-Verdict Schema — v3

v2 stored no probabilities, no discount rate, no model inputs, and no peer set. That made its own Calibration Loop uncomputable: the loop asks for "average Bull probability assigned", and the log did not contain it. v3 adds exactly the fields needed to close that loop, plus the fields needed to reproduce the target.

```json
{
  "schema_version": "3",
  "ticker": "AAPL",
  "company_name": "Apple Inc.",
  "verdict_date": "2026-05-20",
  "verdict": "Buy",
  "conviction": "High",
  "current_price": 213.45,
  "target_base": 260.00,
  "target_bull": 320.00,
  "target_bear": 180.00,
  "prob_bull": 0.25,
  "prob_base": 0.55,
  "prob_bear": 0.20,
  "weighted_expected_price": 259.00,
  "weighted_return_36mo": 0.213,
  "bear_to_current_ratio": 0.84,
  "horizon_months": 36,
  "archetype": "Hyperscaler / Mega-Cap Tech Platform",
  "good_company_score": 9,
  "depth_mode": "Standard",

  "probability_anchors": {
    "archetype_prior_bull": 0.30,
    "independent_assumptions": 3,
    "assumption_adjustment_pp": -5,
    "momentum_adjustment_pp": 2,
    "disconfirming_evidence_cited": "Short interest at 18-month high; SPV operating-lease thesis"
  },
  "dcf": {
    "wacc": 0.09,
    "terminal_g": 0.03,
    "terminal_multiple_derived": 14.7,
    "reverse_dcf_implied_growth": 0.14,
    "sensitivity_revenue_cagr_3pp": [232.0, 291.0]
  },
  "model": {
    "engine": "finlib.valuation",
    "model_json_sha256": "9f2c…",
    "grounding": "OK",
    "anchors_from_financials_json": true
  },
  "peer_set": ["GOOGL", "MSFT", "AMZN"],
  "momentum": {"bucket": "Mild Positive", "adjustment_pp": 2},
  "sotp": null,

  "workers_validated": ["stock-business-reviewer", "stock-earnings-quality-reviewer",
                        "stock-balance-sheet-reviewer", "stock-industry-reviewer",
                        "stock-management-reviewer"],
  "workers_failed": [{"worker": "stock-peer-comparison-reviewer", "state": "TIMEOUT"}],
  "quorum": "full",

  "key_bull_assumptions": ["Services revenue grows 15%/yr through 2028"],
  "key_bear_assumptions": ["China revenue declines 15%/yr on geopolitical pressure"],
  "invalidation_triggers": ["Sell if Services revenue growth <8% for 2 consecutive quarters"],
  "data_gaps_noted": ["DEF 14A details not retrieved"],
  "cognitive_bias_flags": [],
  "prior_verdict_changed_provisional": false
}
```

### Validation (enforced by `verdictlog.py validate`)

Required: `schema_version`, `ticker`, `company_name`, `verdict_date`, `verdict`, `conviction`, `current_price`, the three `target_*`, the three `prob_*`, `weighted_expected_price`, `weighted_return_36mo`, `bear_to_current_ratio`, `horizon_months`, `archetype`, `good_company_score`, `depth_mode`, `key_bull_assumptions`, `key_bear_assumptions`, `invalidation_triggers`, `workers_validated`, `quorum`.

Optional: `probability_anchors`, `dcf`, `model`, `peer_set`, `momentum`, `sotp`, `workers_failed`, `data_gaps_noted`, `cognitive_bias_flags`, `prior_verdict_changed_provisional`.

Arithmetic and enum rules that FAIL the append:

| Rule | Why |
|---|---|
| `prob_bull + prob_base + prob_bear = 1.00` (±0.01) | a probability set that does not sum to one is not a probability set |
| each `prob_*` in `[0, 1]` | store fractions, not percentages — `25` silently breaks every average |
| `weighted_expected_price ≈ Σ(prob × target)` within 2% | the recorded probabilities must be the ones that produced the target, or calibration audits numbers no analysis used |
| `verdict` ∈ the six verdict labels; `conviction` ∈ High/Medium/Low | free-text labels cannot be aggregated |
| `quorum` ∈ `full` / `degraded` | a `none` quorum forbids a verdict, so no entry should exist to log |
| `good_company_score` an integer 0–10 | a fractional score means the checklist was not scored |
| assumption and trigger arrays non-empty | an unfalsifiable verdict cannot be reviewed later, which defeats the log's purpose |
| `dcf.terminal_g < dcf.wacc` | otherwise the Gordon terminal value is undefined |

## Workflow Integration

### Step 5f-bis — Prior Verdict Review (blind-first)

**This moved.** v2 read the prior verdict at Step 1.5b — before data acquisition, before any worker ran. That handed the entire analysis an anchor and then asked the Step 5e anchoring self-check to detect it; the two instructions were in direct tension and the earlier one wins in practice. The review now runs *after* Step 5f has committed a provisional verdict, so this run's judgment is formed independently and then compared.

```bash
python3 scripts/finlib/verdictlog.py read --ticker <TICKER> --limit 3
```

1. Only after a provisional verdict exists, read up to 3 prior entries for the ticker.
2. If found, the most recent becomes mandatory reading:
   - State the past verdict date, verdict, target, conviction
   - Compare past Bull/Base/Bear targets to today's current price
   - Identify which Bull/Bear assumptions have been validated, invalidated, or remain open
   - Note the time-elapsed vs original horizon

If past verdict is older than 12 months, summary review is sufficient; if more recent, full assumption check is required.

If no past verdict exists, skip and proceed.

### Step 5g — Verdict Commit and Log Append

```bash
python3 scripts/finlib/verdictlog.py validate --entry run/verdict.json   # fails closed
python3 scripts/finlib/verdictlog.py append   --entry run/verdict.json
```

1. Construct the JSON object per the v3 schema above and write it to `run/verdict.json` — the run bundle carries it whether or not persistence is opted into.
2. `validate` first. An invalid entry is **never** written: a malformed line would corrupt every later calibration read.
3. `append` under the lock. Report the resolved path, or `NOT PERSISTED` plus the reason, in the report's Verdict Log section.

Never hand-roll the append with `>>`. The shell redirect skips validation and the lock, which is how a torn line and an unsummable probability set both become possible.

---

## How to Use the Log

### When Re-analyzing the Same Ticker

The orchestrator's report must include a **"Prior Verdict Tracking"** subsection that says:

```
Prior verdict (2025-12-15, 5 months ago): Buy at $190.20, target $250, Bull $310, Bear $165
- Time elapsed: 5 months of 36-month horizon
- Current price $213.45 — within Base trajectory
- Bull assumption #1 (Services 15% growth) — VALIDATED (Q1 +14.5%)
- Bull assumption #2 (iPhone units stable) — STILL OPEN
- Bull assumption #3 (Vision Pro) — TRACKING BELOW (still small revenue)
- Bear assumption (China decline -15%) — PARTIALLY VALIDATED (Q1 -8%)
- Net: Bull track 1/3 validated; Bear track 1/1 partially. Re-anchor scenarios.
```

This forces the new verdict to reckon with the old one rather than starting fresh.

### Periodic Calibration Review — executable

```bash
# prices.json: {"AAPL": 231.4, "MSFT": 502.1}
python3 scripts/finlib/calibration.py report --prices prices.json
```

`calibration.py` reads the log, keeps only verdicts whose horizon is ≥⅓ elapsed, classifies each against its own recorded Bull/Bear targets, and compares realised frequency to mean assigned probability — overall and per archetype. Three honesty properties matter more than the numbers:

- **Pre-v3 lines are reported `unscorable` with a reason**, not dropped. Dropping them would silently shrink the denominator and make a thin sample look thick.
- **Unmatured and unpriced verdicts are listed separately**, so the reader can see the sample the conclusion rests on.
- **Fewer than 10 matured verdicts → it refuses to conclude.** It prints the gap but explicitly declines to authorise revising the archetype priors. A 3-verdict sample is not calibration.

Only once it reports a ≥10-verdict sample with a gap beyond ±10pp should the archetype priors in `scenario-probability-calibration.md` be revised.

---

## What This Does NOT Do

To set honest expectations:

- This is not a portfolio tracker (positions, P&L, sizing).
- This is not a screen for ideas (passive monitoring).
- This is not auto-rebalancing or trading.
- This is not automated learning — the SKILL.md still has to be revised by humans based on what the log reveals.

The log is the minimum mechanism to convert one-shot analyses into a process with memory. Beyond that requires real portfolio infrastructure.

---

## Privacy and Storage Note

The log holds the user's investment views — sensitive personal data. Consequences of that:

- **Opt-in only.** No directory is created on the user's behalf; `append` refuses instead (see File Location above).
- **Never auto-committed.** The default locations are outside any repository. If a user opts into the project-local `./.stock-analysis/` form, that directory must be git-ignored — say so when creating it.
- **The user controls the copy.** Backing up, sharing, or deleting the log is theirs to do; the skill never copies it elsewhere.
- **Portable by construction.** Because the path is resolved rather than hardcoded, the same skill works on another machine or under another agent runtime by setting one environment variable.

---

## Initial Log Bootstrap

If the log doesn't exist yet, create it on the first verdict with one line. Subsequent verdicts append. The file is human-readable JSON-Lines; the user can review it directly with `cat`, `tail`, or `jq`:

```bash
LOG=$(python3 scripts/finlib/verdictlog.py path | python3 -c 'import json,sys; print(json.load(sys.stdin)["path"])')

python3 scripts/finlib/verdictlog.py read --limit 10 | jq          # latest 10, any ticker
python3 scripts/finlib/verdictlog.py read --ticker AAPL | jq       # one ticker, chronological
jq -r .verdict "$LOG" | sort | uniq -c                             # verdict distribution
```

Prefer `verdictlog.py read` over `grep` on the raw file: it filters on the parsed `ticker` field (case-insensitively) and skips corrupt lines, where `grep '"ticker": "AAPL"'` depends on key order and whitespace that `json.dumps` is free to change.

This deliberately uses JSON-Lines rather than a single JSON array so the file can be appended without rewriting, which prevents corruption and enables atomic writes.