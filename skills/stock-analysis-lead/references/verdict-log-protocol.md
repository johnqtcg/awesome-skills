# Verdict Log Protocol — Feedback Loop

Load this during Step 1 (after ticker validation) and Step 5f (verdict commitment).

**Why this exists**: A single-shot equity analysis without a feedback loop is not investor's-process — it's literature review. Without tracking which past verdicts came true, the framework cannot learn from misses. This protocol creates a persistent, queryable log of every verdict the orchestrator produces, plus the assumptions it rested on, so that:

1. When the same ticker is re-analyzed later, the orchestrator MUST review the prior verdict before producing a new one.
2. The log accumulates calibration data — over many verdicts, the framework can be audited for systematic Bull/Bear bias, sector blind spots, and base-rate errors.
3. The user can manually review verdicts at any time and see which Bull scenarios played out vs which didn't.

This is a minimal feedback mechanism — not a full portfolio system. But it converts the skill from a one-shot tool into a process with memory.

---

## File Location and Format

The log lives at a project-independent location so the feedback loop survives machine moves, repo renames, and use from any project:

```
~/.claude/stock-analysis/verdicts.jsonl
```

Create the directory on first use: `mkdir -p ~/.claude/stock-analysis`.

**Format**: JSON Lines (one verdict per line). Each line is independently parseable; appends are atomic.

**Validation**: after every append, run this skill's `scripts/validate_verdict_log.py --last 1`. It checks required fields, enum values, assumption-count bounds, and target-price ordering (bear ≤ base ≤ bull). A warning, not a hard stop — but surface validation failures in the final report.

**Migration from pre-v2.1 path**: earlier versions wrote to the project memory directory (`~/.claude/projects/<project-slug>/memory/stock-analysis-verdicts.jsonl`). If that file exists and the new one does not, move it once:

```bash
mkdir -p ~/.claude/stock-analysis
mv ~/.claude/projects/*/memory/stock-analysis-verdicts.jsonl ~/.claude/stock-analysis/verdicts.jsonl
```

---

## Per-Verdict Schema

```json
{
  "ticker": "AAPL",
  "company_name": "Apple Inc.",
  "verdict_date": "2026-05-20",
  "verdict": "Buy",
  "conviction": "High",
  "current_price": 213.45,
  "target_base": 260.00,
  "target_bull": 320.00,
  "target_bear": 180.00,
  "weighted_expected_price": 250.00,
  "weighted_return_36mo": 0.171,
  "bear_to_current_ratio": 0.84,
  "horizon_months": 36,
  "archetype": "Hyperscaler",
  "good_company_score": 9,
  "key_bull_assumptions": [
    "Services revenue grows 15%/yr through 2028",
    "iPhone unit volume stable +2%/yr",
    "Vision Pro / AR achieves $5B+ run-rate by 2028"
  ],
  "key_bear_assumptions": [
    "China revenue declines 15%/yr on geopolitical pressure",
    "Services antitrust outcome adverse",
    "Apple Intelligence fails to drive iPhone upgrade cycle"
  ],
  "invalidation_triggers": [
    "Sell if Services revenue growth <8% for 2 consecutive quarters",
    "Sell if China revenue declines >25% YoY"
  ],
  "data_gaps_noted": ["DEF 14A details not retrieved"],
  "cognitive_bias_flags": [],
  "depth_mode": "Standard",
  "skill_version": "v2"
}
```

All fields are required except `data_gaps_noted` and `cognitive_bias_flags` (which may be empty arrays).

---

## Workflow Integration

### Step 1.5b — Past Verdict Review (NEW)

After ticker validation but before depth selection, the orchestrator MUST:

1. Read the verdict log file (if it exists).
2. Filter for past entries on the same ticker.
3. If found, the most recent past verdict becomes mandatory reading:
   - State the past verdict date, verdict, target, conviction
   - Compare past Bull/Base/Bear targets to today's current price
   - Identify which Bull/Bear assumptions have been validated, invalidated, or remain open
   - Note the time-elapsed vs original horizon

If past verdict is older than 12 months, summary review is sufficient; if more recent, full assumption check is required.

If no past verdict exists, skip and proceed.

### Step 5f — Verdict Commit and Log Append (UPDATED)

After committing the verdict, the orchestrator MUST:

1. Construct the JSON object per the schema above.
2. Append one line to the log file (JSON Lines format — newline-terminated).
3. Include the new line's `verdict_date` in the final report under "Tracking" so the user can audit.

The append must be atomic — use `>>` shell redirect or equivalent file-append semantics. Do NOT rewrite the entire file.

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

### Periodic Calibration Review

The user can ask: "What did the verdict log say 12 months ago for tickers I'm still analyzing?" The orchestrator should be able to:

1. Read the log
2. Filter for verdicts ≥12 months ago
3. Compute: weighted_expected_price vs current actual price
4. Report calibration: was the framework systematically too bullish, too bearish, sector-biased?

This is not automated — it's a manual audit the orchestrator can run on request.

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

The log lives in the user's home directory (`~/.claude/stock-analysis/`) and is never committed to git. It contains the user's investment views. If the user wishes to share or back up, they may copy the file; it should never be auto-committed.

---

## Initial Log Bootstrap

If the log doesn't exist yet, create it on the first verdict with one line. Subsequent verdicts append. The file is human-readable JSON-Lines; the user can review it directly with `cat`, `tail`, or `jq`:

```bash
# View latest 10 verdicts
tail -10 ~/.claude/stock-analysis/verdicts.jsonl | jq

# Get verdicts on a specific ticker
grep '"ticker": "AAPL"' ~/.claude/stock-analysis/verdicts.jsonl | jq

# Count Buy vs Watch vs Sell verdicts
grep -oE '"verdict": "[^"]*"' ~/.claude/stock-analysis/verdicts.jsonl | sort | uniq -c
```

This deliberately uses JSON-Lines rather than a single JSON array so the file can be appended without rewriting, which prevents corruption and enables atomic writes.