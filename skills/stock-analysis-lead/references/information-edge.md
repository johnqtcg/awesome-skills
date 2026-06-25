# Information Edge — Honest Boundary + Where the AI Edge Actually Is

Load during Step 5e (cognitive-bias / honesty) and whenever framing conviction. This file fixes the framework's hardest limitation honestly: it has **no proprietary information advantage**, and pretending otherwise is the most dangerous form of false confidence.

---

## 1. The honest boundary (mandatory disclosure)

A top sell-side/buy-side senior's alpha comes substantially from **information the market doesn't have yet**: channel checks (calling an Azure mega-customer about real consumption), expert networks (Tegus/AlphaSense calls), direct IR/management access, and first-hand supply-chain datapoints (NVIDIA/TSMC/memory). **This framework has none of that.** It works only from public disclosure + sell-side consensus reprocessing.

Therefore every report MUST carry, prominently (in the Verdict block or Data Coverage):

> **信息优势声明 / Information-edge disclosure:** 本分析基于公开披露 + 卖方一致预期的再加工,**无渠道调研、专家网络、IR 直连或一手供应链 datapoint**。此处的价值在于流程、广度与校准,**不在于"知道别人不知道的事"**。

**Confidence cap:** because there is no information edge, conviction language is capped. Do NOT use "high conviction / analyst-grade" framing for a thesis whose only inputs are public. Reserve "High" conviction for cases where the edge is *process* (a clear valuation dislocation that the math makes unambiguous), never for cases that hinge on a forward judgment a better-informed human could out-call. When in doubt, one notch lower.

This is not self-deprecation — it is calibration. An honest "公开信息、靠流程" beats a false "资深分析师级判断".

---

## 1b. Variant perception — state where you differ from consensus (mandatory)

"No information edge" is not the same as "no view." The honesty disclosure above stops you from faking *private-information* certainty; it must NOT become an excuse to hide behind consensus. The opposite failure mode — a verdict that restates the sell-side ("Buy, alongside 35 other Buys, target near consensus") with no articulated difference — is a **consensus clone**: organized, well-cited, and adding nothing. A report's value is the gap between what it concludes and what the crowd already believes.

Therefore every report MUST carry a short **变量观点 / Variant Perception** statement, with three parts:

1. **What the market currently prices in** — anchored in the numbers, not vibes: the reverse-DCF implied growth at the current price, and the consensus rating/target. ("Market implies ~8% net-revenue CAGR; 35 Buy / 3 Hold; median target $645.")
2. **Where I differ, and why (falsifiable)** — one specific, checkable claim that is NOT just "I agree but I'm more careful." It can be on the **thesis** ("the market prices VAS as a cyclical services add-on; I think it is a structural re-rating item growing 2× the network — if VAS margin holds and mix keeps climbing, blended take expands, not compresses"), on **a number** ("consensus assumes incentives stay ~33% of gross; I model them rising to 36%, cutting net-revenue growth ~1.5pp"), or on **probability** ("market treats stablecoin disruption as a 1–3yr risk; I price it as 5–10yr, which is why my Bear is milder than the bears'").
3. **What would prove me wrong vs the crowd** — the specific datapoint that would collapse the variant view (ties to the invalidation triggers).

**If there is genuinely no variant view** — the analysis lands on the consensus call with no differentiated edge — that is allowed, but you MUST say so plainly: *"变量观点：无。本结论与卖方共识方向、目标价基本一致;价值在于独立验证了共识、而非提供差异化判断。"* Do not dress a consensus restatement as insight. This statement is what Gate 6 (`cognitive-bias-gates.md`) checks.

A variant view is not a license to be aggressive — it must still respect the §1 confidence cap. The point is to make the report's *difference from the crowd* explicit and falsifiable, whichever direction it points (more bullish, more bearish, or "same call, here's the independent confirmation").

---

## 2. Where the AI edge actually IS (lean into these)

The framework cannot win the human's game (depth + private info). It can win a *different* game. Three edges, all real and underexploited:

### Edge A — Breadth / cross-section (`scripts/finlib/crosssection.py`)
A human analyst covers ~10–20 names and cannot hold 30 live models at once. The AI can run the **same** rigorous driver model across an entire peer set / sector simultaneously and surface **relative dislocations** — e.g., which names have the best weighted-return-per-unit-downside, or the largest gap between the growth the market *implies* (reverse-DCF) and the growth the company has *delivered*. Run it after several single-name workups:

```bash
python3 scripts/finlib/crosssection.py rank --book verdicts.jsonl   # or --entries entries.json
```

The dislocation that pops out of a 30-name cross-section is genuine edge a 15-name human desk structurally cannot see.

### Edge B — Event-driven monitoring (`scripts/finlib/verdict_diff.py` + the verdict log)
The framework already logs every verdict with its assumptions and triggers. On a new 8-K/10-Q/transcript, re-run and **diff against the prior entry** — flag verdict changes, price crossing a buy trigger, and assumption additions/removals — faster and more consistently than a human re-reads their old note:

```bash
python3 scripts/finlib/verdict_diff.py --prev prior.json --new current.json
```

Tireless, consistent re-evaluation the instant data drops is an AI-advantaged mode.

### Edge C — Alternative data (the closest legal analog to a channel check) — opt-in
If given API access, an `alt-data` worker can pull the AI-accessible analogs of channel checks: app-download trends, job-postings (hiring as a demand/capex proxy), data-center build permits, import/shipping data, web-traffic, GitHub activity, Glassdoor. These are **not** insider info, but they are forward signals most retail and many desks don't systematically integrate. Specify providers as opt-in; **degrade gracefully (and say so) when no keys are present** — never fabricate an alt-data datapoint.

---

## 3. Positioning (state this once, plainly)

The goal is not to beat a top analyst at depth and private information. It is to be **excellent at the AI-advantaged game — breadth, discipline, calibration, tireless monitoring — while honestly bounded on the human-advantaged game (first-hand depth, proprietary edge).** A report that says so is more useful, and more honest, than one that imitates a senior analyst's certainty without the senior analyst's information.