# Report Output Format

Load at render time (after Step 5g). This is the full template for the rendered
report — moved out of `SKILL.md` so the main file carries the workflow and the
wire contracts while the render template loads only when it is needed.

**The Worker Findings section is machine-audited.** `scripts/finlib/report_audit.py`
parses it and diffs it against `consolidated.json` field by field: matching
severity, the worker's citation `locator` verbatim, and the worker's `evidence` and
`implication` verbatim. Surrounding prose is fine; substitution is not. The
publication gate blocks on any mismatch, so the shape below is a contract, not a
suggestion.

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
- **Read only after this run's provisional verdict was committed** (Step 5f-bis) — stated so the reader knows this analysis was not anchored on it
- Prior verdict (<date>, <X months ago>): <verdict> at $<price>, target $<base>, Bull $<bull>, Bear $<bear>
- Bull/Bear assumptions: VALIDATED / INVALIDATED / STILL OPEN, each with the datapoint
- Current price vs prior trajectory: <closest scenario>
- Provisional verdict this run: <verdict> → final: <verdict>. <"unchanged" | what in the prior entry changed it>

## Good-Company Score / 好公司评分: X / 10 (archetype: <name>)
| # | Item | Threshold (archetype) | Score | One-line evidence |
| 1 | Revenue growth | ≥<threshold>% | PASS/WEAK/FAIL | <evidence> |
... (10 items, sector-aware thresholds)

## Bull / Base / Bear / 三档情景
| Scenario | Revenue CAGR | Op Margin | Multiple | Target | Probability | Probability Anchors |
| Bull | __% | __% | __× | $__ | __% | archetype prior <X%> + assumption adj <±pp> + momentum adj <±pp>; disconfirming evidence: <citation> |
| Base | __% | __% | __× | $__ | __% | residual |
| Bear | __% | __% | __× | $__ | __% | archetype prior <X%> + assumption adj <±pp> + momentum adj <±pp>; confirming-of-Bull citation: <citation> |
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
(every finding in `consolidated.json` appears exactly once, and only those — `report_audit.py` diffs this section field by field)

### [High|Medium|Low] Short Title
- **ID**: `BUS-11` (the worker's own Finding ID from consolidated.json — BUS / EQ / BS / MGT / IND / P)
- **Citation**: must contain the worker's citation `locator` verbatim
- **Evidence**: the worker's `evidence` **verbatim** (surrounding prose allowed; substitution is not)
- **Implication**: the worker's `implication` **verbatim** (you may add to it, not replace it)

## Risks I Accept / 我接受的风险 (≥ 3, mandatory)
1. <strongest counter-thesis>
2. <secondary risk>
3. <…>

## Invalidation Conditions / 卖出触发器 (mandatory, ≥ 1 quantitative)
- <e.g., "Sell if FCF negative for 2 consecutive quarters">

## Data Coverage & Dispatch Log / 数据覆盖度与调度记录
- Fetched: <list from manifest>
- Missing: <list from manifest with confidence impact>
- Depth: <Lite|Standard|Strict> · Archetype: <name> <"(CONTESTED — re-dispatched)" if applicable>
- Worker states (from `run/dispatch-log.json` — every dispatched worker appears):

| Worker | Tier | Trigger | State | Status | Attempts | Notes |
|---|:--:|---|---|---|:--:|---|
| business | 0 | always-on | VALIDATED | OK | 1 | — |
| management | 1 | depth=Standard | VALIDATED | DEGRADED | 2 | no proxy; retry after MISSING_BLOCK |
| peer-comparison | 1 | <trigger, or "NOT DISPATCHED — no peer set"> | TIMEOUT | — | 2 | P-items UNSCORED |

- Tier-0 quorum: <N>/4 → verdict permitted: <full | degraded | none>
- Run bundle: <path> · `runbundle.py check` → <PASS|FAIL>

## Cognitive-Bias Self-Check / 认知偏差自检
- Anchoring: <PASS|FLAG + rationale>
- Story bias: <PASS|FLAG + rationale>
- Confirmation: <PASS|FLAG + rationale>
- Overconfidence: <PASS|FLAG + rationale>
- Information edge: <PASS|FLAG + rationale>
- Consensus clone / variant view: <PASS|FLAG + rationale>
- Inverted rigor: <N/A if not option-dominated | PASS|FLAG + rationale>

## Verdict Log / 决策日志
- Logged to: <resolved path from `verdictlog.py path`, or "NOT PERSISTED — persistence not opted into">
- Schema version: 3 · Entry timestamp: <ISO 8601>
- Probabilities recorded: Bull __% / Base __% / Bear __% (so this verdict is calibratable later)
- Confirm: this verdict will be reviewed when the ticker is re-analyzed
```
