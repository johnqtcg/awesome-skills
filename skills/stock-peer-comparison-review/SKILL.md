---
name: stock-peer-comparison-review
description: Independently benchmark a US-listed target equity against 2-4 closest peers on a fixed 12-item ratio panel — growth rates, profitability, capital intensity, balance sheet leverage, capital returns, and valuation multiples. Provides cross-validation for moat and market-share claims made by the business and industry reviewers. Trigger when running a Standard-or-deeper stock-analysis-lead workup, and at Lite depth when a peer set exists and the question is valuation- or moat-shaped; supplies the independent quantitative comparison that single-name analysis cannot. Dispatched by stock-analysis-lead as a Tier-1 conditional worker.
allowed-tools: Read, Grep, Glob, WebSearch, WebFetch, Bash
---

# Stock Peer Comparison Review

## Purpose

Most single-stock analyses fall into one of two failure modes:

1. **Tunnel vision**: declaring the target has a "wide moat" or "industry-leading margins" without ever showing what the peer set actually does.
2. **Peer-set selection bias**: comparing only against weaker peers to flatter the target.

This worker fixes both. It loads a fixed 12-item ratio panel, computes the target and each peer on the same definition, and surfaces the rank position. The Industry and Business workers can claim "Azure is gaining share" — this worker reports the ratios that either confirm or contradict the claim independent of narrative.

The output is a small, dense, rank-ordered comparison table. It is **not a recommendation**; it is the independent data the orchestrator uses to validate the moat and market-share claims of other workers.

## When To Use

- Orchestrator dispatches in Standard or Strict depth (Tier-1 always-on at those depths).
- Lite depth **and** a peer set of >=2 names exists **and** the question is valuation- or moat-shaped ("expensive", "cheap", "fair price", "moat", "vs peers", "losing share") -> dispatched in **Lite mode**: General 12-item panel only, no archetype-specific extension. See `stock-analysis-lead/references/dispatch-protocol.md` Part 1 Tier 1 for the authoritative trigger.
- User explicitly asks "how does X compare to peers".
- A specific competitive claim ("losing share", "best-in-class margins") needs independent verification.

## When NOT To Use

- Lite depth with no peer set, or a Lite question that is not valuation/moat-shaped — the Tier-1 trigger does not fire and the orchestrator scores the peer-dependent items `UNSCORED` rather than guessing.
- Companies with no comparable peers (rare, but e.g., single-issuer ADRs, novel asset classes).
- Sector ETFs or funds (compose peer index instead).

## Mandatory Gates

### 1) Peer Set Validation Gate
Must use 2–4 peers identified by the orchestrator (typically from the 10-K Item 1 Competition section + WebSearch). Reject peer-set selections that are obviously cherry-picked weaker:
- All peers materially smaller than target (>10× revenue gap)
- All peers in distressed states
- Peer set excludes the obvious #1 in the category

If the peer set looks rigged, surface this to the orchestrator and refuse to score until corrected.

### 2) Same-Definition Gate
Every ratio must be computed on a comparable basis (same fiscal year vintage, same GAAP/non-GAAP convention, same currency). If a peer doesn't disclose a needed line (e.g., NRR for non-SaaS comparison), mark NOT FOUND — do not estimate.

### 3) Archetype-Awareness Gate
Peer comparison must use the **same sector archetype** as the target (see `stock-analysis-lead/references/sector-archetypes.md`). Comparing a SaaS company against an industrial peer on SaaS metrics is invalid.

### 4) Recency Gate
Use trailing twelve months (TTM) data where available; fall back to most recent full fiscal year. Document the data vintage explicitly.

## Workflow

1. Receive from orchestrator: target ticker, peer list (2–4), archetype.
2. For each company (target + peers), assemble the 12-item panel from manifest data.
3. For each item, compute the rank (1 = best in panel) and the gap-to-leader.
4. Surface 3 specific places target is **best in panel** and 3 places it is **worst in panel**.
5. Cross-reference with claims from other workers if visible in manifest comments.

## The 12-Item Comparison Panel

Different sub-panels apply per archetype. Always run the General panel; run the Archetype-Specific panel additionally.

### General Panel (all archetypes)

| # | Item | Definition | Direction |
|---|------|------------|:---------:|
| P-01 | Revenue growth | TTM revenue YoY % | Higher better |
| P-02 | Gross margin | TTM GP / Revenue | Higher better |
| P-03 | Operating margin | TTM OpInc / Revenue | Higher better |
| P-04 | FCF margin | TTM FCF / Revenue | Higher better |
| P-05 | Revenue per employee | TTM revenue / FY-end headcount | Higher better |
| P-06 | Net Debt / EBITDA | Most recent quarter | Lower better |
| P-07 | Capex intensity | TTM Capex / Revenue | Archetype-dependent |
| P-08 | R&D intensity | TTM R&D / Revenue | Archetype-dependent |
| P-09 | Buyback + dividend yield | TTM (Repurchase + Div) / Market cap | Higher better |
| P-10 | Forward P/E | Consensus NTM EPS | Lower better (cheaper) |
| P-11 | EV/FCF (TTM) | (Market cap − net cash) / TTM FCF | Lower better |
| P-12 | EV/Sales (TTM) | (Market cap − net cash) / TTM Revenue | Lower better |

### Archetype-Specific Panel — SaaS

Add: NRR, GRR, Magic Number, ARR growth, customer count growth.

### Archetype-Specific Panel — Mature Cash Cow

Add: Dividend coverage ratio, dividend yield, organic vs M&A growth split, payout ratio.

### Archetype-Specific Panel — Capital-Intensive

Add: Maintenance capex vs expansion capex split, regulatory ROE allowed vs achieved (utilities), contracted backlog growth.

### Archetype-Specific Panel — Financials

Add: ROTCE, NIM (banks), CET1 (banks), combined ratio (insurance), P/TBV.

### Archetype-Specific Panel — REIT

Add: FFO/share growth, AFFO/share growth, occupancy, NOI growth same-store, payout ratio of AFFO.

## Filing-Pattern-Gated Execution Protocol

### Execution Order

1. Pull target manifest values for the 12 items.
2. For each peer in the peer-list, run a quick web search to populate the same 12 items (TTM basis where available).
3. Where peer data is unavailable, mark NOT FOUND and note in Execution Status — do NOT fabricate.
4. Build the ranking table; compute target's rank in each item.
5. Compute summary: count of items target is 1st in panel; count where target is last.
6. Surface the 3 most material relative strengths and 3 most material relative weaknesses.

### Output Discipline

- Do NOT recommend buy/hold/sell.
- Do NOT interpret causation ("they're winning because of...") — that's the Industry worker's job.
- Do NOT speculate beyond the data — if a ratio looks anomalous and you can't explain it from disclosures, flag it as "data anomaly, requires investigation" rather than guessing.

## Output Format

### Comparison Table

```
Archetype: <SaaS / Hyperscaler / Mature Cash Cow / etc.>
Peer set: <Target> + [Peer1, Peer2, Peer3, Peer4]
Data vintage: TTM as of <date>

| Item            | <Target>  | <P1>   | <P2>   | <P3>   | <P4>   | Target Rank |
| P-01 Rev growth | XX%       | YY%    | YY%    | YY%    | YY%    | N of 5      |
| P-02 GM         | XX%       | YY%    | ...                                | N of 5      |
| ...
```

### Summary Findings

Format: 3 Best-in-Panel + 3 Worst-in-Panel + Anomalies

#### Best in Panel
- **P-XX [Item]**: Target is #1 of 5 at XX% vs panel median YY%. **Cross-references**: Industry worker's claim of "leading position in X" is supported by P-XX.

#### Worst in Panel
- **P-XX [Item]**: Target is last of 5 at XX% vs panel median YY%. **Cross-references**: Business worker's flag of "narrative bucket without methodology" matches P-XX shortfall.

#### Anomalies / Data Gaps
- Peer X did not disclose ABC; rank in P-XX is incomplete.

### Execution Status

```
Filings reviewed: [Target] manifest + [peer ticker] 10-K/10-Q for each peer
Items computed: X / 12 General + Y / archetype-specific
Data NOT FOUND: <list>
Archetype applied: <name>
```

### No-Finding Case

If target is materially mid-panel (not 1st or last in any item), output:
```
Target is materially mid-panel: no item where it leads, no item where it lags by >25%.
Implication: target performs in line with peers; no quantitative edge or shortfall detected.
This is itself a finding — supports neither premium nor discount valuation.
```

### Machine-Readable Findings Block (mandatory)

End the reply with **exactly one** fenced block tagged `findings-json`, carrying
**Worker Findings Contract v1** (full schema and error codes:
`stock-analysis-lead/references/worker-contract.md`). The orchestrator synthesizes
the verdict **from this block only** — anything stated in the Markdown above but
omitted here does not reach the report. Everything above the fence is for the
human reader.

```findings-json
{
  "contract_version": "1",
  "worker": "stock-peer-comparison-reviewer",
  "prefix": "P",
  "status": "OK",
  "depth_mode": "<echo the dispatched depth>",
  "archetype_applied": "<echo the dispatched archetype>",
  "archetype_challenge": null,
  "findings": [
    {
      "id": "P-NN",
      "severity": "High|Medium|Low",
      "title": "<= 80 chars",
      "citation": {"source": "10-K", "locator": "<item/page/note>", "fiscal_period": "FY2025"},
      "evidence": "direct quote <= 60 words, or a computed figure with its inputs",
      "implication": "one sentence on what this means for the thesis",
      "confidence": "first-hand|second-hand"
    }
  ],
  "positives": [],
  "data_gaps": [],
  "checklist_coverage": {"items_total": 12, "items_checked": 0, "items_not_found": 0, "ids_not_checked": []},
  "mandatory_checks_run": []
}
```

Contract rules that fail validation if broken:

- `status` is one of `OK` / `DEGRADED` / `SKIPPED` / `REFUSED`; any value other
  than `OK` **requires** a `status_reason`. The gate returns `SKIPPED (...)` in
  prose *and* `"status": "SKIPPED"` here.
- Every finding ID must start with `P` — the prefix is the whole segment
  before the first hyphen.
- `citation` is an **object**, never a bare string; `locator` and `fiscal_period`
  must be non-empty. A finding with no real citation is suppressed, not emitted.
- `source: "aggregator"` forces `confidence: "second-hand"` — this is what makes
  the first-hand data rule checkable rather than aspirational.
- `checklist_coverage`: `items_checked + items_not_found` must reach
  `items_total` (12), so "the checklist ran to completion" is verifiable.
- `archetype_challenge`: `null` when the dispatched archetype fits. When the
  evidence says it does not, file `{"proposed", "reason", "evidence"}` instead of
  silently analyzing against thresholds you believe are wrong — this is the only
  sanctioned way to disagree with the orchestrator's classification.
- `mandatory_checks_run`: list the archetype-specific check IDs the dispatch
  marked REQUIRED. Omitting one that was required fails validation.

Self-check before replying:

```bash
python3 <path-to>/stock-analysis-lead/scripts/finlib/worker_contract.py \
  validate --reply <this-reply>.md --expect-worker stock-peer-comparison-reviewer
```

## Cross-Reference Rules

The peer-comparison worker's outputs explicitly feed back into other workers' claims:

- **Validates Industry's market-share claim**: if Industry says "gaining share", P-01 (revenue growth) should be > peer median. If not, Industry's claim is suspect.
- **Validates Business's moat claim**: a "switching cost moat" should show as P-02 (gross margin) and P-04 (FCF margin) above peer median through cycles.
- **Validates Earnings Quality's "operating leverage" claim**: P-03 (operating margin) growing faster than P-01 (revenue growth) confirms leverage.
- **Stress-tests Industry's "best-in-class" claim**: P-05 (revenue per employee) should be top-quartile in panel.
- **Reality-checks valuation cheap/expensive claim**: P-10 / P-11 / P-12 vs peer median tells you whether the target is cheap because it deserves to be (last in P-01/P-02/P-04) or anomalously.

## Load References Selectively

- `references/peer-comparison-methodology.md` — load when constructing the panel for an archetype not in the main checklist, or when peer-set composition is contested.

## Review Discipline

This worker's job is to be a quantitative referee. The other workers tell stories; this one provides receipts. When the stories don't match the receipts, surface the gap — that's the orchestrator's most actionable input.