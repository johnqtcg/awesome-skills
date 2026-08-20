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

### About the two PDFs in this directory

`MSFT-投资分析报告.pdf` and `META投资分析报告.pdf` are **illustrative report samples, not golden runs.** Read them for output shape and tone only. Specifically:

| | MSFT PDF | META PDF |
|---|---|---|
| Produced under | pre-v2 (5 workers) | v2 (6 workers) |
| DCF disclosure (WACC · terminal g · sensitivity) | absent — added in v2 | partial |
| Filing page/note-level citations in the body | partial | mostly absent |
| Cognitive-bias gate set | earlier, smaller set | 6-gate set |
| Worker Findings Contract | did not exist | did not exist |

Neither carries a run bundle, so **neither can be audited**: there is no way to check whether the synthesis faithfully carried the workers' evidence, which is exactly the gap `runbundle.py` now closes. They are also not regression baselines — a current run would legitimately differ from both, so a diff against them proves nothing.

**To create a real golden run**, use the capture harness — it runs the publication gate first and aborts on FAIL, so an unpublishable bundle can never become a baseline:

```bash
skills/stock-analysis-lead/scripts/goldenrun.sh capture "$TMPDIR/stock-analysis-msft/run" MSFT
skills/stock-analysis-lead/scripts/goldenrun.sh verify outputexample/stock-analysis-lead/runs/MSFT-2026-08-20
```

It writes `runs/<TICKER>-<verdict_date>/` plus a `CAPTURE.md` review checklist. Read that checklist before committing: raw worker replies can quote scraped third-party content, `verdict.json` records a personal investment view, and manifest paths can leak local directory layout. Nothing leaves `$TMPDIR` automatically.

**`runs/` is currently empty, and that is the framework's largest remaining gap.** See [`runs/README.md`](runs/README.md) for exactly which properties are verified by tests and which still need a live run. A test keeps that status line honest in both directions — it fails if the README claims no runs exist while some are present, and fails if it stops saying so while the directory is empty.

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
5. **Anchored Probability Procedure** (`references/scenario-probability-calibration.md`): replaces the ad-hoc "Good-Company score → Bull weight" mapping with an explicit 3-anchor procedure (archetype prior + assumption-independence adjustment + mandatory disconfirming-evidence citation). Auditable, **not yet calibrated** — see v3 item 7.
6. **Strict Cross-Method Reconciliation**: replaces "lean toward scenarios" fudge with explicit tiebreaker rules when multiples, reverse-DCF, and scenarios disagree.
7. **Lite Mode Fix**: Lite no longer skips the Industry worker entirely (the prior behavior distorted the Good-Company score by dropping 2 of 10 items); Lite runs a lighter Industry pass. (Superseded by v3 item 3, which made Lite a real reduction on the *other* two workers.)
8. **Toolchain Risk Acknowledgment**: explicit documentation of which data sources can silently fail and what degraded analysis looks like.

## v3 Improvements — orchestration hardening (August 2026)

v2 was a strong analytical framework with an incomplete runtime. Its message protocol was undefined, its failure model covered only missing data, and its triage always fanned out to all six workers. v3 addresses that:

1. **Worker Findings Contract v1** (`references/worker-contract.md`): a versioned JSON schema on the wire, validated deterministically by `scripts/finlib/worker_contract.py` with stable error codes. Previously the agent definitions demanded "the JSON block specified in the dispatch prompt" and the dispatch prompt defined none — so the orchestrator parsed free-form Markdown, and a worker that dropped a field failed **silently**.
2. **Dispatch state machine** (`references/dispatch-protocol.md`): explicit states (`VALIDATED` / `INVALID_OUTPUT` / `TIMEOUT` / `CRASHED` / `SKIPPED` / `REFUSED` / `FAILED`), one bounded retry with the validator's errors attached, per-worker time budgets, no model fallback, and a **quorum** rule stating which verdicts a partial fan-out may publish. v2 said only "wait for all workers to return" — one stalled agent held the whole analysis.
3. **Real triage tiers**: 4 Tier-0 core workers always; Management and Peer Comparison became Tier-1, dispatched on explicit triggers; a Tier-2 second wave fires only on a named cross-worker contradiction. Lite is now a 4-worker run rather than six in costume.
4. **Run bundle + gate** (`scripts/finlib/runbundle.py`): every run persists the manifest, dispatch log, **raw worker replies and extracted payloads**, model inputs/outputs, lint result, and verdict. The gate cross-checks the log against the files, recomputes the quorum rather than trusting the recorded summary, and blocks publication on mismatch.
5. **Archetype de-correlation**: the lead's classification is provisional; every worker can file an `archetype_challenge`, and two workers naming the same alternative force re-classification and re-dispatch. The optionality test also moved after data acquisition — it divides visible-business value by market cap, and neither input existed at its old position.
6. **Blind-first prior-verdict review**: moved from Step 1.5b to Step 5f-bis, *after* the provisional verdict. Reading the prior verdict first anchored the analysis and put the workflow in tension with its own anchoring self-check.
7. **Verdict log schema v3 + executable calibration** (`scripts/finlib/verdictlog.py`, `scripts/finlib/calibration.py`): the log now stores the assigned probabilities, WACC, terminal g, reverse-DCF implied growth, model digest, peer set, and quorum. v2's Calibration Loop asked for "average Bull probability assigned" — a number its own log did not store. `calibration.py` computes it and refuses to conclude on fewer than 10 matured verdicts.
8. **Portable, opt-in persistence**: the log path resolves via `$STOCK_VERDICT_LOG` → `$XDG_STATE_HOME` → `./.stock-analysis/` → `~/.local/state/`, replacing a hardcoded personal Claude project path. Appends take an exclusive lock, and no directory is created without the user opting in.
9. **Cross-skill contract tests** (`scripts/tests/test_orchestration_matrix.py`): tests over the *joins* between files — depth × worker matrix, agent ↔ skill ↔ prefix, contract-version agreement, failure-path wiring, step ordering. v2's per-skill suite all passed while three cross-file contradictions were live, because a per-skill structural test cannot see a relationship between two files.

## v3.1 — fail-closed pass (August 2026)

v3 defined the right rules; three of them were not actually binding.

1. **The bundle gate was fail-open and mis-ordered.** Absent `lint.json`, `financials.json`, `metrics.json` and `report.md` produced warnings and a PASS — so "the 口径 gate left no evidence it ran" was indistinguishable from "it ran and passed". Worse, Step 5d-ter invoked `--require-verdict` while `verdict.json` is written at Step 5f, so following the documented order could only fail. The gate is now two stages (`--stage evidence` pre-verdict, `--stage publication` after 5g) with every requirement fail-closed, and it additionally verifies that the artifacts *agree*: each extracted payload equals the payload in its raw reply, `consolidated.json` is reproducible by re-running consolidation, `report.md` carries every consolidated finding ID, the `verdict.json` model digest matches `model.json`, and every claimed retry left its superseded reply on disk.
2. **The state machine was prose.** Transitions, retry caps and tier triggers were documented and then written into a log the orchestrator authored freely, so an illegal history was recordable and nothing objected. `scripts/finlib/dispatch.py` now owns `dispatch-log.json`: `plan` computes the fan-out from depth + manifest + question shape (triage is a function, not a judgment call), and `record` refuses a second retry, a retry after a non-retryable code, a `failed` before the granted retry is used, a second wave past the depth cap, and events against a worker whose trigger never fired. Honest scope: the orchestrator is still the executor — `dispatch.py` is the referee.
3. **Official skill validation was not in the regression.** Two of the seven skills failed `skill-creator/scripts/quick_validate.py` while the repo's own suite was green: the lead's description carried angle brackets, and `stock-earnings-quality-review` had a bare `": "` inside its unquoted description scalar, which made the **entire frontmatter invalid YAML**. `scripts/tests/test_skill_frontmatter.py` now validates all seven skills and six agent definitions against the spec with a real YAML parser, and cross-checks against the official script when a copy is present. (One tolerated disagreement: that script's field allowlist is stale and rejects `disable-model-invocation`, a real product field.)
4. **Cross-file count drift.** The lead said "Run 6 binary checks" above a list of 7; `cognitive-bias-gates.md` documented only 6 gates and still said "All 5 workers"; the Peer and Management agent descriptions implied they always run. Gate 7 (Inverted Rigor) is now documented, the counts are derived from the files rather than restated, and the agent descriptions state their tier.
5. **No golden run — now falsifiably so.** `scripts/goldenrun.sh` captures a bundle as a baseline, gating before copying. `runs/README.md` enumerates what is verified by tests versus what still needs a live run, and `test_goldenrun.py` fails if that status line and the directory ever disagree.

## v3.2 — closing the evidence chain (August 2026)

v3.1 made the gate fail-closed on *presence*. Three ways to pass it while distorting the evidence remained.

1. **The report could distort a finding, not just drop it.** The gate checked only that each finding's ID appeared as a substring of `report.md`, and the consolidation re-check compared only id/severity/reported_by. Keeping the ID while rewriting the evidence, softening the implication, swapping the citation or downgrading the severity all passed. `scripts/finlib/report_audit.py` now parses the Worker Findings section and diffs it field by field: matching severity, the worker's citation `locator`, and the worker's `evidence` and `implication` **verbatim** (surrounding prose allowed, substitution not). A report block claiming a finding consolidation never produced is caught as fabrication. The consolidation projection widened to every field the contract defines.
2. **The second wave was a gap in the audit.** It got a name/reason/cap check and nothing else — no terminal-state check, no attempts or duration, no reply or payload required on disk, no contract validation, and its findings never entered consolidation. It is now audited identically to the first wave under the `<worker>.wave2.md` naming, and `dispatch.py` refuses a second wave-2 entry for the same worker (two made its history ambiguous and hid one of its replies).
3. **The publication gate trusted the caller to validate the verdict.** It checked quorum and conviction but never called `verdictlog.validate_entry()`, so a verdict missing its probabilities could pass as long as nobody skipped a separate command. The gate now validates the full v3 schema in-process, and the `model.model_json_sha256` digest is **required** at publication rather than checked-if-present.
4. **Prose counts and the persistence claim.** `cognitive-bias-gates.md` said "Run 6 binary self-check questions" and the navigation said "5 self-check questions" while the files carried 7 gates — the earlier count test compared *headings* and was blind to a number written in prose. A new scanner reads spoken counts (digits and words) and requires them to match the files or be absent. The frontmatter's "Each verdict persists" softened to "can persist to an opt-in log", matching the body.
5. **SKILL.md trimmed 666 → 500 lines.** The render template moved to `references/output-format.md`, the artifact table and manifest shape to `data-acquisition-playbook.md` (which already owned them), the inline dispatch JSON to a required-key list, and sections 5c/5d compressed to the decisions the orchestrator makes rather than a restatement of their references. The enforced ceiling is 510 — ten lines of headroom, so the next addition has to justify itself or move detail out. A test pins the fifteen control-plane anchors a reader of SKILL.md alone must still find.

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
3. Select depth: Lite (4 Tier-0 workers, Industry in light mode) / Standard (Tier-0 + both Tier-1 = 6) / Strict (6 + up to 3 conflict-triggered re-dispatches).
4. Triage by tier and dispatch the wave in a single Agent batch.
5. Validate every reply against Worker Findings Contract v1; retry a formatting failure once; mark timeouts; check the Tier-0 quorum before synthesizing anything.
6. Consolidate deterministically (`worker_contract.py consolidate`); handle any `archetype_challenge`; run the second wave on a named contradiction.
7. Score the 10-item Good-Company checklist against archetype thresholds.
8. Run 4-method valuation (multiples, reverse-DCF, DCF sanity check, scenarios) — or a sum-of-the-parts for option-dominated names.
9. Build Bull/Base/Bear with anchored probabilities; compute weighted expected return and Bear/Current ratio.
10. Pass the 口径 lint gate and the run-bundle gate — either FAIL blocks the report.
11. Run the 6 cognitive-bias self-checks; commit a **provisional** verdict with invalidation conditions.
12. **Only then** read the prior verdict on this ticker and reconcile; report any revision it caused.
13. Validate and append the verdict-log entry (if persistence was opted into); render the report in the user's invocation language.

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
- **The probabilities are anchored, not calibrated.** The archetype priors are judgment priors, and the buy thresholds (50%/0.75, 30%/0.70, 15%/0.80) have never been validated against outcomes. `calibration.py` is the path to fixing that, and it refuses to conclude until ≥10 matured verdicts exist in the log.
- **This is a Claude Code implementation, not a runtime-agnostic framework.** The orchestrator relies on Claude Code's Agent batch dispatch and `~/.claude/agents/` discovery. The *analytical* layer (`references/`) and the *deterministic* layer (`scripts/finlib/`, plain Python + stdlib) port cleanly; the dispatch layer would need reimplementing on another runtime. The Worker Findings Contract exists partly to make that port possible — it is plain JSON over any transport.
- **Time and token budgets are advisory.** The orchestrator cannot read its own token meter, so the per-depth figures in `dispatch-protocol.md` are planning guidance, not enforced limits.
