# US-Stock Multi-Agent Investment Analysis — Deployment Guide

This directory contains ready-to-deploy agent definition files for the 6-Agent US-stock fundamental-analysis system. The architecture mirrors `go-review-lead` and is described in [`bestpractice/架构篇.md`](../../bestpractice/架构篇.md) §17–18.

> **Platform constraint**: Claude Code does not allow subagents to spawn other subagents. The `stock-analysis-lead` orchestrator therefore runs as a **Skill in the main conversation**, not as an agent definition in `.claude/agents/`. The 6 Worker Agents in `agents/` are dispatched by the main conversation, not by a Lead Agent.

## What's in This Directory

```
agents/                                  # 6 vertical Worker Agents only
├── stock-business-reviewer.md           # Worker: business model, customer concentration, narrative buckets
├── stock-earnings-quality-reviewer.md   # Worker: OCF/NI, FCF, capex, margins, operating leverage, SaaS metrics
├── stock-balance-sheet-reviewer.md      # Worker: leverage, liquidity, goodwill, working capital, off-BS items
├── stock-management-reviewer.md         # Worker: capital allocation, M&A, guidance record, insider activity
├── stock-industry-reviewer.md           # Worker: market share, TAM, moat classification, pricing power
└── stock-peer-comparison-reviewer.md    # Worker: independent 12-item ratio benchmark vs 2-4 peers (NEW v2)
```

Each file is a Claude Code agent definition (YAML frontmatter + system prompt). Each loads its domain knowledge at runtime via the `skills:` field, keeping the definitions short.

The `stock-analysis-lead` orchestrator is **not in this directory**. It lives in `skills/stock-analysis-lead/SKILL.md` and is loaded by the main conversation.

## Prerequisites

Each Worker Agent loads a corresponding vertical skill at runtime. These skills must be installed before the agents will work:

| Agent file | Required skill |
|-----------|----------------|
| `stock-business-reviewer.md` | `stock-business-review` |
| `stock-earnings-quality-reviewer.md` | `stock-earnings-quality-review` |
| `stock-balance-sheet-reviewer.md` | `stock-balance-sheet-review` |
| `stock-management-reviewer.md` | `stock-management-review` |
| `stock-industry-reviewer.md` | `stock-industry-review` |
| `stock-peer-comparison-reviewer.md` | `stock-peer-comparison-review` (NEW v2) |

The `stock-analysis-lead` skill is loaded by the main conversation — it is the orchestrator, not a worker.

The source files for all 7 skills are in the `skills/` directory of this repository.

## Installation

### Step 1 — Install the skills

Copy the skill directories to your Claude Code user-level skills location. The default path is `~/.claude/skills/`; adjust if your setup differs.

```bash
# Run from the repository root
for skill in stock-analysis-lead \
             stock-business-review \
             stock-earnings-quality-review \
             stock-balance-sheet-review \
             stock-management-review \
             stock-industry-review \
             stock-peer-comparison-review; do
  cp -r "skills/$skill" ~/.claude/skills/
done
```

### Step 2 — Install the Worker Agent definitions

Copy **only the 6 Worker Agent** definition files to `~/.claude/agents/`. Do **not** copy any orchestrator agent — `stock-analysis-lead` is a Skill, not an Agent.

```bash
mkdir -p ~/.claude/agents
for agent in stock-business-reviewer \
             stock-earnings-quality-reviewer \
             stock-balance-sheet-reviewer \
             stock-management-reviewer \
             stock-industry-reviewer \
             stock-peer-comparison-reviewer; do
  cp "outputexample/stock-analysis-lead/agents/${agent}.md" ~/.claude/agents/
done
```

Claude Code discovers agents in `~/.claude/agents/` automatically — no further configuration is needed.

### Verify

```bash
ls ~/.claude/agents/ | grep stock-
# Expected output (6 workers):
# stock-balance-sheet-reviewer.md
# stock-business-reviewer.md
# stock-earnings-quality-reviewer.md
# stock-industry-reviewer.md
# stock-management-reviewer.md
# stock-peer-comparison-reviewer.md
```

## v2 Improvements (May 2026)

This is v2 of the skill, with the following improvements over v1:

1. **Sector-aware thresholds** (`references/sector-archetypes.md`): the Good-Company checklist now applies threshold sets per archetype (SaaS / Mature Cash Cow / Hyperscaler / Capital-Intensive / Cyclical / Financials / REIT) rather than universal SaaS defaults. Fixes systematic under-rating of mature staples, banks, REITs, utilities, and cyclicals.
2. **New Peer Comparison Worker** (`stock-peer-comparison-review`): independent 12-item ratio benchmark vs 2-4 peers; cross-validates moat and market-share claims from the Industry and Business workers.
3. **Earnings Revision Momentum** (`references/earnings-revision-momentum.md`): NTM EPS revision direction and magnitude over 30/60/90 days adjusts scenario probabilities ±5pp.
4. **Verdict Log** (`references/verdict-log-protocol.md`): every verdict persists to JSON Lines log; subsequent re-analyses of the same ticker mandatorily review the prior verdict and check assumption validation.
5. **Calibrated Probability Framework** (`references/scenario-probability-calibration.md`): replaces ad-hoc "Good-Company score → Bull weight" mapping with explicit 3-anchor framework (archetype base rate + assumption-independence adjustment + mandatory disconfirming-evidence citation).
6. **Strict Cross-Method Reconciliation**: replaces "lean toward scenarios" fudge with explicit tiebreaker rules when multiples, reverse-DCF, and scenarios disagree.
7. **Lite Mode Fix**: Lite no longer skips the Industry worker entirely (the prior behavior distorted the Good-Company score by dropping 2 of 10 items); Lite now runs a lighter Industry pass.
8. **Toolchain Risk Acknowledgment**: explicit documentation of which data sources can silently fail and what degraded analysis looks like.

## Usage

Invoke the orchestrator from the main conversation:

**English:**
```
Use stock-analysis-lead to analyze NVDA
```
```
Analyze MSFT — is it a good buy at current levels?
```

**Chinese:**
```
用 stock-analysis-lead 分析 AAPL
```
```
现在适合买入 GOOGL 吗？给我一个完整的投资分析
```

The main conversation (running the `stock-analysis-lead` Skill) will:

1. Identify the ticker and validate it as a US listing (rejects A-shares, HK-shares, 20-F filers).
2. Fetch the standard data package: latest 10-K, 10-Q, DEF 14A, recent earnings call transcripts, current price + multiples, 10-year historicals, peer list, analyst consensus, insider Form 4 activity.
3. Select depth: Lite (all 6 workers in lighter form) / Standard (all 6, full mode) / Strict (all 6 + extended cross-check).
4. Triage and dispatch Worker Agents in parallel.
5. Consolidate Findings; score the 10-item Good-Company checklist.
6. Run 4-method valuation (multiples, reverse-DCF, DCF sanity check, scenarios).
7. Build Bull/Base/Bear with probability weights; compute weighted expected return and Bear/Current ratio.
8. Run 4 cognitive-bias self-checks (anchoring, story bias, confirmation, overconfidence).
9. Commit a verdict (Strong Buy / Buy / Watch / Hold / Trim / Sell) with invalidation conditions.
10. Render the final report in the user's invocation language.

You can also invoke any Worker Agent directly for a focused single-dimension analysis:

```
@stock-management-reviewer audit MSFT's capital allocation track record
```

## Scope

**In scope:**
- US-listed equities (NYSE / Nasdaq / NYSE American) filing 10-K and 10-Q with the SEC
- Single-stock fundamental analysis
- Long-term investment thesis (multi-quarter to multi-year horizons)

**Out of scope (will be refused):**
- A-shares and HK-shares
- Foreign private issuers filing only 20-F
- ETFs and mutual funds
- Options analysis
- Technical analysis / chart-based trading signals
- Cryptocurrency and FX
- Sector / macro calls

## Model Configuration

All Worker Agents default to `sonnet`. Per the architecture documented in `bestpractice/架构篇.md` §17.3.3, mid-tier models with focused attention on a single dimension outperform top-tier models splitting attention across dimensions. The orchestrator's synthesis step benefits from Sonnet or Opus depending on the depth mode.

To override the model for a worker:

```bash
sed -i '' 's/model: sonnet/model: haiku/' ~/.claude/agents/stock-balance-sheet-reviewer.md
```

## Architecture Overview

For the complete design rationale — attention dilution problem, triage logic, parallel dispatch in a single Agent batch, consolidation rules, and model-cost trade-off — see:

- Chinese: [`bestpractice/架构篇.md`](../../bestpractice/架构篇.md) §17–18

The stock-analysis case mirrors the go-code-reviewer case at the architectural level. The key adaptation is **Step 2 (data acquisition)** — unlike code review where the diff is in front of the model, stock analysis requires external data, so the orchestrator centrally fetches SEC filings and market data before dispatching the workers.

## Source Methodology

The skill's analytical framework follows the six-part methodology in [`如何找到好的投资标的.md`](../../如何找到好的投资标的.md) at the repository root:

- **Part 1** (business understanding) → `stock-business-review`
- **Part 2 layers L1–L3** (cash flow, revenue quality, margins) → `stock-earnings-quality-review`
- **Part 2 layer L4** (balance sheet) → `stock-balance-sheet-review`
- **Part 2 layer L5** (management) → `stock-management-review`
- **Part 2 layer L6** (industry) → `stock-industry-review`
- **Part 2 layer L7** (valuation) + **Part 3** (synthesis) → orchestrator's Step 5
- **Part 4** (heuristics) + cognitive-bias section → orchestrator's cognitive-bias gates

## Limitations

- The framework assumes US GAAP and SEC filing structure. Non-US disclosures (中报/年报 in IFRS / CAS) require different checklists; out of scope.
- Real-time price data depends on the freshness of stockanalysis.com / Yahoo Finance — typically intraday-delayed by 15 minutes. For execution-grade pricing, use a brokerage data feed.
- Earnings-call transcript access depends on Seeking Alpha free tier availability; degraded mode runs without transcripts.
- The skill does not consider options market signals or short-interest data.
- The skill does not execute trades; it produces analysis only.