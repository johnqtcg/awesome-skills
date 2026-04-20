# load-test Skill Evaluation Report

> Evaluation framework: [skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator)
> Evaluation date: 2026-04-18
> Subject: `load-test`

---

The `load-test` skill is a focused performance testing specialist covering HTTP/gRPC services across three operating modes — Write, Review, and Analyze — with four mandatory gates (Context Collection → SLO-First → Scope Classification → Output Completeness) and deep integration with k6, vegeta, and wrk. The evaluation spanned three scenarios (Write: generate a k6 script / Review: diagnose a defective script / Analyze: deliver an SLO verdict), covering 24 total assertions. With-Skill passed all 24 (100%); Without-Skill passed 18 (75%). Scenario 1's baseline is contaminated by tool-call side-effects and is excluded from the core delta calculation. Based on the two clean scenarios (S2 + S3), the net improvement is **+40pp**. The three most prominent gaps: first, in Review mode the skill maps each defect to an AE-x rule ID and produces a three-tier Scorecard verdict — the baseline offers reasonable suggestions but no rule-name mapping and no Scorecard; second, §9.9 Uncovered Risks is absent from both clean baseline runs (0/2) while With-Skill includes it in all three runs (3/3, at least 5 items each); third, in Analyze mode the baseline's substantive analysis quality nearly matches the skill (6/7), meaning the real gap is output completeness rather than analytical depth.

---

## 1. Skill Overview

`load-test` defines 4 Mandatory Gates (Context → SLO-First → Scope → Output Completeness), 3 depth levels (Lite / Standard / Deep), 5 degradation modes, an 18-item Load Test Checklist, 6 scenario types, 6 anti-example pairs, a 3-tier Scorecard (Critical / Standard / Hygiene), and a 9-section Output Contract.

**Core components:**

| File | Lines | Responsibility |
|------|------:|----------------|
| `SKILL.md` | 420 | Primary skill definition: 4 Gates, 3 Depth levels, 5 Degradation modes, Checklist, 6 Anti-Examples AE-1~6, 8-item Scorecard, 9-section Output Contract |
| `references/k6-patterns.md` | ~480 | k6 executor patterns: constant-arrival-rate, SharedArray, thresholds, handleSummary, CI integration |
| `references/vegeta-patterns.md` | ~260 | vegeta fixed-rate model, pipeline composition, Go integration, binary result archiving |
| `references/analysis-guide.md` | ~350 | Percentile interpretation, saturation-point identification, bottleneck classification (Tier 1/2/3), SLO verdict framework, regression detection |

**Regression test total: 125** (75 contract + 50 golden + integrity), 14 golden fixtures (LT-001–014), 100% coverage across all critical dimensions.

---

## 2. Test Design

### 2.1 Scenario Definitions

The three scenarios map directly to the three operating modes defined in SKILL.md and are drawn from real production prototypes:

| # | Scenario | Input | Key Focus |
|---|----------|-------|-----------|
| 1 | Write — generate k6 script from requirements | Go payment API, SLO: p99 < 300 ms / 500 RPS / error rate < 0.1%, Bearer token, 3 K8s replicas + PostgreSQL | SLO-First gate execution, warmup/measurement separation, data parameterization, generator isolation note, §9 output compliance |
| 2 | Review — diagnose a defective k6 script | Script with 3 defects: no warmup, duration 30s, avg instead of percentile | Defect detection rate, AE-x rule naming, Scorecard rating, §9.9 Uncovered Risks |
| 3 | Analyze — SLO verdict from k6 output | Steady-state 5-minute output: p50=88ms / p99=312ms / RPS=423.5 / error rate 0.06%; SLO: p99 < 200ms | Per-SLO verdict table, bottleneck ranking, saturation-point analysis, §9.9 Uncovered Risks |

### 2.2 Assertion Matrix (24 total)

**Scenario 1 — Write: Generate a complete k6 script (9 assertions)**

> ⚠️ **Baseline contamination notice**: The Without-Skill S1 agent made 2 tool calls (all other clean-run agents made 0) and consumed 37,725 tokens — far above baseline expectations. The output contained skill-proprietary terms such as `§9.x` section numbers and `AE-3`. It is assessed that this agent inadvertently read skill-related files during execution. S1 Without-Skill results are recorded below for reference but are **excluded from the core delta calculation** (see §3.3).

| ID | Assertion | With-Skill | Without-Skill |
|----|-----------|:----------:|:-------------:|
| A1 | `thresholds` block declares both p99 and error-rate SLOs (not a `check()` comparison) | PASS | PASS* |
| A2 | Warmup phase and measurement phase are separated (distinct phase tags or scenarios) | PASS | PASS* |
| A3 | Load ramps using `ramping-vus` or `constant/ramping-arrival-rate` | PASS | PASS* |
| A4 | Request body is parameterized (≥3 combinations of `merchant_id` or `currency`) | PASS | PASS* |
| A5 | Steady-state duration ≥ 3 minutes | PASS | PASS* |
| A6 | Explicitly states that the load generator must be deployed separately from the SUT | PASS | PASS* |
| A7 | Outputs §9.1 Context Summary (service / protocol / SLO) | PASS | PASS* |
| A8 | Outputs §9.4 Scenario Design (type / VU or RPS target) | PASS | PASS* |
| A9 | Outputs §9.9 Uncovered Risks (non-empty, ≥3 items) | PASS | PASS* |

*Without-Skill S1 passed in practice but results are unreliable due to tool-call contamination.

**Scenario 2 — Review: Diagnose a defective k6 script (8 assertions)**

| ID | Assertion | With-Skill | Without-Skill |
|----|-----------|:----------:|:-------------:|
| B1 | Identifies missing warmup / ramp-up as a standalone defect | PASS | PASS |
| B2 | Identifies 30s duration as insufficient (explicitly states steady-state should be ≥3–5 min) | PASS | FAIL |
| B3 | Identifies `avg` for SLO evaluation (calls out that `thresholds` + percentile should be used) | PASS | PASS |
| B4 | Maps each defect to an AE-x rule ID or specific rule name (not just plain description) | PASS | FAIL |
| B5 | Outputs a Load Test Scorecard with Critical / Standard / Hygiene three-tier rating | PASS | FAIL |
| B6 | Provides fix recommendations or corrected script (actionable code or concrete steps) | PASS | PASS |
| B7 | Outputs §9.2 Mode & Depth declaration | PASS | FAIL |
| B8 | Outputs §9.9 Uncovered Risks (non-empty) | PASS | FAIL |

> **B2 rationale**: Without-Skill provided a corrected script that extended duration to roughly 4.5 minutes but never called out "30s duration is insufficient" as a standalone defect or stated the minimum steady-state requirement (AE-5 / Scorecard Critical #3). B4 similarly: Without-Skill used natural-language labels like "Wrong metric" and "No ramp-up" without referencing SKILL.md AE-x identifiers.

**Scenario 3 — Analyze: SLO verdict and bottleneck analysis (7 assertions)**

| ID | Assertion | With-Skill | Without-Skill |
|----|-----------|:----------:|:-------------:|
| C1 | Outputs a per-SLO verdict table (each SLO individually PASS / FAIL) | PASS | PASS |
| C2 | Uses p99 (not avg) as the latency verdict basis and states this explicitly | PASS | PASS |
| C3 | Identifies and ranks ≥2 bottlenecks with evidence and impact statements | PASS | PASS |
| C4 | Provides a saturation-point estimate or RPS ceiling analysis with calculation | PASS | PASS |
| C5 | Overall verdict is explicit (PASS / WARN / FAIL / INCONCLUSIVE) | PASS | PASS |
| C6 | Outputs §9.8 Recommendations (priority-ordered) | PASS | PASS |
| C7 | Outputs §9.9 Uncovered Risks (non-empty, ≥3 items) | PASS | FAIL |

> **C7 rationale**: Without-Skill S3 delivered a well-structured bottleneck analysis and P0/P1 recommendations, but omitted §9.9 Uncovered Risks entirely. With-Skill output 6 risks including "error rate at true 500 RPS is unknown", "single-replica failure degradation untested", and "combined GC + DB pressure effect" — all production-critical blind spots.

### 2.3 Trigger Accuracy

The current `description` field uses a task-type enumeration strategy:

```
Performance load testing specialist for writing k6/vegeta/wrk scripts,
defining SLOs, modeling scenarios (spike/soak/stress/breakpoint), analyzing
results, and identifying bottlenecks. ALWAYS use when writing load test
scripts, reviewing test results...
```

**Should-Trigger scenarios (10)**

| # | Prompt summary | Expected |
|---|----------------|:--------:|
| T1 | "Write me a k6 load test script" | ✅ triggers |
| T2 | "Review my vegeta attack config" | ✅ triggers |
| T3 | "Analyze this k6 run output and give an SLO verdict" | ✅ triggers |
| T4 | "We need to define SLOs for the API" (load testing context) | ✅ triggers |
| T5 | "Run a soak test to check for memory leaks" | ✅ triggers |
| T6 | "Breakpoint test to find the service capacity ceiling" | ✅ triggers |
| T7 | "Write a spike scenario simulating a traffic surge" | ✅ triggers |
| T8 | "My p99 is over SLO — how do I find the bottleneck?" | ✅ triggers |
| T9 | "Help me benchmark HTTP throughput with wrk" | ✅ triggers |
| T10 | "What is the difference between constant-arrival-rate and ramping-vus in k6?" | ✅ triggers |

**Should-Not-Trigger scenarios (8)**

| # | Prompt summary | Expected | Risk |
|---|----------------|:--------:|------|
| N1 | "Write a benchmark test for this Go function" | ✅ no trigger | Low (go-benchmark skill handles it) |
| N2 | "Optimize this SQL query's performance" | ✅ no trigger | Low (not an HTTP service layer concern) |
| N3 | "Configure Prometheus alerting rules" | ✅ no trigger | Low (monitoring-alerting skill) |
| N4 | "Run an A/B feature flag experiment" | ✅ no trigger | Low (product A/B ≠ load testing) |
| N5 | "My service CPU is high — how do I optimize it?" | ⚠️ may trigger | Medium ("bottleneck" is an implicit trigger word; Applicability Gate can filter) |
| N6 | "Set up a k6 Cloud account" (pure operational question) | ⚠️ may trigger | Low (skill can downgrade to Lite mode after triggering) |
| N7 | "My Go HTTP handler is slow — profile it" | ✅ no trigger | Low (go-benchmark skill handles it) |
| N8 | "Test my React page load speed" | ✅ no trigger | Low (frontend performance ≠ backend load testing) |

**Estimated trigger accuracy: F1 ≈ 87%** (Should-trigger 10/10; Should-not-trigger 6/8; N5/N6 are reasonable boundary cases, Applicability Gate provides a safety net).

---

## 3. Pass Rate Comparison

### 3.1 Overall Pass Rate (raw data)

| Configuration | Pass | Fail | Pass Rate |
|---------------|:----:|:----:|:---------:|
| **With-Skill** | **24** | **0** | **100%** |
| **Without-Skill** | **18** | **6** | **75%** |

**Raw delta: +25pp** (includes S1 contaminated data)

### 3.2 Per-Scenario Pass Rate

| Scenario | With-Skill | Without-Skill | Delta | Data Quality |
|----------|:----------:|:-------------:|:-----:|:------------:|
| 1. Write — generate k6 script (9 assertions) | 9/9 (100%) | 9/9 (100%) | +0pp | ⚠️ S1 baseline contaminated |
| 2. Review — defect diagnosis (8 assertions) | 8/8 (100%) | 3/8 (37.5%) | **+62.5pp** | ✅ Clean |
| 3. Analyze — SLO verdict (7 assertions) | 7/7 (100%) | 6/7 (85.7%) | **+14.3pp** | ✅ Clean |

### 3.3 Clean-Scenario Delta (S2 + S3)

| Configuration | S2+S3 Pass | S2+S3 Fail | Pass Rate |
|---------------|:----------:|:----------:|:---------:|
| **With-Skill** | **15** | **0** | **100%** |
| **Without-Skill** | **9** | **6** | **60%** |

**Clean-scenario delta: +40pp** (based on S2 + S3 uncontaminated data)

### 3.4 Substantive Dimensions (excluding output-structure assertions, S2 + S3)

| ID | Check | With-Skill | Without-Skill |
|----|-------|:----------:|:-------------:|
| S1 | S2: Identifies missing warmup as a standalone defect | PASS | PASS |
| S2 | S2: Identifies 30s duration as insufficient (steady-state requirement) | PASS | FAIL |
| S3 | S2: Identifies avg misuse (should use thresholds + percentile) | PASS | PASS |
| S4 | S2: Provides actionable fix code | PASS | PASS |
| S5 | S3: Uses p99 as latency verdict basis (not avg) | PASS | PASS |
| S6 | S3: Per-SLO PASS/FAIL verdict | PASS | PASS |
| S7 | S3: Identifies and ranks ≥2 bottlenecks with evidence | PASS | PASS |
| S8 | S3: Saturation-point / RPS ceiling estimate with derivation | PASS | PASS |
| S9 | S3: Explicit overall verdict (PASS/FAIL/INCONCLUSIVE) | PASS | PASS |

**Substantive pass rate:** With-Skill **9/9 (100%)** vs. Without-Skill **8/9 (88.9%)**, delta **+11pp**.

**Key finding**: Without-Skill performs comparably on testing-methodology knowledge (C1–C6 all pass in S3). The skill's incremental value is concentrated in **output structure compliance** — Uncovered Risks, Scorecard, Mode/Depth declaration, and rule-name mapping — rather than in domain knowledge per se. This mirrors the asymmetric value distribution observed in `go-benchmark`: the Claude baseline already possesses the relevant expertise; the skill's leverage is in enforcing structured output and eliminating systematic blind spots (e.g., "§9.9 Uncovered Risks is never empty").

---

## 4. Key Differences

### 4.1 Behaviors Exclusive to With-Skill (completely absent from Without-Skill)

| Behavior | Observed output |
|----------|-----------------|
| **AE-x rule-name mapping** | S2 With-Skill: "CRITICAL-3 — AE-1: no warmup / no ramp-up", "CRITICAL-4 — AE-3: 30-second duration is insufficient"; Without-Skill uses natural-language labels like "No ramp-up / ramp-down" and "Wrong metric" — no rule traceability |
| **Load Test Scorecard three-tier rating** | S2 With-Skill: outputs a Critical 0/3 / Standard 0/5 / Hygiene 0/4 table with overall verdict "FAIL — script fails all Critical checks"; Without-Skill produces no Scorecard and gives no quantifiable pass/fail determination |
| **§9.9 Uncovered Risks** | S2 With-Skill: 5 risks (payment idempotency / timeout config / concurrent write contention / soak test missing / no teardown); S3 With-Skill: 6 risks (true 500 RPS error rate unknown / spike scenario / single-replica failure degradation / combined GC + DB pressure / test data representativeness / downstream dependency isolation); Without-Skill omits this section in both S2 and S3 |
| **§9.2 Mode & Depth declaration** | S2/S3 With-Skill: every output declares Mode (Review / Analyze) and Depth (Standard) with a rationale; Without-Skill omits this declaration in both scenarios |
| **Explicit identification of 30s duration as a defect** | S2 With-Skill: "CRITICAL-4: 30-second duration is insufficient — minimum steady-state ≥5 minutes yields ~10,000 samples; tail percentiles are unstable at 30s"; Without-Skill extends the corrected script to ~4.5 minutes but never flags this as a standalone critical defect |

### 4.2 Behaviors Where Without-Skill Is Qualitatively Comparable

| Behavior | With-Skill quality | Without-Skill quality |
|----------|--------------------|-----------------------|
| SLO verdict (S3) | Explicit FAIL/PASS table + "overall verdict: SLO FAILED, not ready for production" + full derivation | Same quality — SLO table + "current config should not go to production", RPS calculation (424 vs 425 RPS, numerically identical) |
| Bottleneck identification (S3) | 🔴🔴🟡🟡 four-tier ranking, each bottleneck with evidence and correlated metrics | Three bottlenecks with derivation ("DB connection pool 90% utilization", "GC max 41ms"), comparable quality |
| avg misuse identification (S2) | CRITICAL-1 — AE-6, with explanation: "check() evaluates per-VU independently, not a statistical aggregate" | "Wrong metric" with the same core explanation, comparable quality |
| Corrected script (S2) | Minimal working script with thresholds, SharedArray, and status checks | Full corrected script, comparable quality, slightly simpler structure |

### 4.3 Scenario-Level Findings

**Scenario 2 (Review — defect diagnosis) — Largest gap (+62.5pp)**

- **With-Skill**: Identifies 4 defects (CRITICAL-1 through CRITICAL-4), each with an AE rule ID, the offending line, a mechanism explanation, and fix code. Scorecard clearly marks Critical 0/3 (all failing). §9.9 calls out 5 production blind spots, including "payment idempotency untested" (high-risk for a payment scenario) and "no teardown / potential data contamination".
- **Without-Skill**: Correctly identifies the core issues (avg misuse, no ramp, hardcoded token, static payload), but the 30s duration problem is handled implicitly — the corrected script extends duration but the issue is never raised as a defect. No Scorecard, no Uncovered Risks. Assertions B4, B5, B7, B8 all fail.

**Scenario 3 (Analyze — SLO verdict) — Smallest gap (+14.3pp)**

- **With-Skill**: Adds §9.9 Uncovered Risks (6 items) on top of an analysis equivalent in depth to the baseline — including "true 500 RPS error rate never validated" and "DB connection pool behavior under spike load".
- **Without-Skill**: C1–C6 all pass. The only failure is C7 (Uncovered Risks) — production-critical blind spots are silently omitted, but the analytical depth is nearly identical. Both agents computed `200 VU / 0.471s ≈ 424–425 RPS`, both identified DB connection pool (18/20 = 90%) as the primary bottleneck, and both provided P0/P1/P2 priority recommendations.

**S1 contamination finding (methodological lesson)**

Without-Skill S1 consumed 37,725 tokens (vs. 32,633 for With-Skill S1), and the output contained SKILL.md-proprietary terms: `§9.x` section numbers, Scorecard format, and `AE-3` references. The 2 unexpected tool calls are assessed to have accessed skill-related files or claude-mem observation records. This reveals a limitation of evaluation isolation in open-tool-access environments and informs future A/B test design (Without-Skill agents should have tool-call permissions restricted).

---

## 5. Token Cost Analysis

### 5.1 Measured Token Consumption (6 evaluation agents)

| Agent | Scenario | Total Tokens | Duration (s) | Tool Uses |
|-------|----------|:------------:|:------------:|:---------:|
| S1 With-Skill | Write — generate k6 script | 32,633 | 133.6 | 7 |
| S1 Without-Skill | Write — generate k6 script | 37,725 ⚠️ | 112.9 | 2 ⚠️ |
| S2 With-Skill | Review — defect diagnosis | 27,998 | 87.7 | 4 |
| S2 Without-Skill | Review — defect diagnosis | 13,422 | 21.4 | 0 |
| S3 With-Skill | Analyze — SLO verdict | 28,789 | 84.8 | 8 |
| S3 Without-Skill | Analyze — SLO verdict | 13,976 | 30.0 | 0 |

⚠️ S1 Without-Skill made 2 tool calls; token consumption is anomalously high (exceeding With-Skill). This is contaminated data and is excluded from cost-efficiency calculations.

**With-Skill average (all 3 scenarios):** 29,807 tokens, 102.0 s, 6.3 tool uses  
**Without-Skill average (S2 + S3 clean):** 13,699 tokens, 25.7 s, 0 tool uses  
**Runtime token overhead (S2 + S3):** +14,695 tokens/eval (**+107%**)  
**Runtime time overhead (S2 + S3):** +65.3 s/eval (**+254%**) — primarily from loading and processing SKILL.md and reference files

### 5.2 Skill Context Cost

| Component | Lines | Estimated Tokens | Load Timing |
|-----------|------:|:----------------:|-------------|
| `SKILL.md` | 420 | ~2,100 | Always |
| `k6-patterns.md` | ~480 | ~2,400 | Standard+ Write mode |
| `vegeta-patterns.md` | ~260 | ~1,300 | Standard+ Write (vegeta path) |
| `analysis-guide.md` | ~350 | ~1,750 | Analyze / Deep |
| **Lite typical (SKILL.md only)** | | **~2,100** | Fast review |
| **Standard Write typical** | | **~4,500** | SKILL.md + k6-patterns.md |
| **Standard Analyze typical** | | **~3,850** | SKILL.md + analysis-guide.md |

### 5.3 Cost-Efficiency Calculation

| Metric | Value |
|--------|-------|
| Core pass-rate improvement (S2 + S3, clean) | +40pp |
| Substantive pass-rate improvement (knowledge dimensions, S2 + S3) | +11pp |
| Skill context cost (minimum, Lite) | ~2,100 tokens |
| Skill context cost (typical, Standard Write) | ~4,500 tokens |
| Runtime token overhead (S2 + S3 measured average) | +14,695 tokens/eval (+107%) |
| **Tokens per 1pp improvement (context only, Lite)** | **~52 tokens/1pp** |
| **Tokens per 1pp improvement (context only, Standard)** | **~112 tokens/1pp** |
| **Tokens per 1pp improvement (including runtime overhead)** | **~367 tokens/1pp** |

The elevated runtime overhead arises because S2/S3 With-Skill agents each make 4–8 tool calls to read SKILL.md and reference files (~1,250 lines total). In direct-integration deployments (skill pre-loaded in the system prompt), the runtime load cost disappears and context cost (~2,100–4,500 tokens) is the accurate efficiency baseline.

### 5.4 Cross-Skill Cost-Efficiency Comparison

| Skill | Context tokens (typical) | Pass-rate improvement (core scenarios) | Context tok/1pp | With runtime tok/1pp |
|-------|:------------------------:|:--------------------------------------:|:---------------:|:--------------------:|
| `git-commit` | ~1,300 | +77pp | ~17 | ~73 |
| `go-benchmark` | ~2,380–3,330 | +54pp | ~44–62 | ~177 |
| **`load-test`** | **~2,100–4,500** | **+40pp (core)** | **~52–112** | **~367** |

**load-test cost-efficiency characteristics:**

1. **High context cost (420-line SKILL.md + up to 1,090 lines of references):** Knowledge density is high — well-suited for deep, specialist tasks; less appropriate for lightweight Q&A.
2. **Highest runtime overhead (+107%):** Tool calls to load reference files significantly increase execution time and total tokens; this cost is absent in pre-load deployments.
3. **Narrow core-value window (Review mode +62.5pp; Analyze mode only +14.3pp):** The baseline Claude is already capable in Analyze-type tasks. The skill's leverage is strongest in Write/Review tasks.

---

## 6. Weighted Scoring

### 6.1 Per-Dimension Scores

| Dimension | With-Skill | Without-Skill | Delta |
|-----------|:----------:|:-------------:|:-----:|
| Output structure completeness (Scorecard / Mode & Depth / Uncovered Risks) | 5.0/5 | 0.5/5 | +4.5 |
| Defect rule-name mapping (AE-x IDs / rule traceability) | 5.0/5 | 0.5/5 | +4.5 |
| Testing methodology correctness (p99 / warmup / parameterization / saturation analysis) | 5.0/5 | 4.0/5 | +1.0 |
| SLO verdict completeness (per-SLO table / overall verdict) | 5.0/5 | 4.5/5 | +0.5 |
| Token cost-efficiency (context tokens/1pp, relative to domain complexity) | 3.0/5 | — | — |

### 6.2 Weighted Total Score

| Dimension | Weight | Score | Rationale | Weighted |
|-----------|:------:|:-----:|-----------|:--------:|
| Assertion pass rate (core delta) | 25% | 8.0/10 | +40pp in clean scenarios; S3 baseline is strong (85.7%), pulling down the aggregate; Review mode at +62.5pp is the real leverage point | 2.00 |
| Output structure compliance | 25% | 9.5/10 | Without-Skill scores 0/2 on both Scorecard and Uncovered Risks in clean scenarios; With-Skill achieves 3/3 across the board; structural completeness is the skill's strongest guarantee | 2.38 |
| Defect rule-name mapping | 20% | 9.5/10 | Without-Skill never outputs AE-x rule IDs (B4 FAIL); With-Skill maps every defect systematically; traceability directly supports engineering teams in prioritizing fixes | 1.90 |
| Testing methodology knowledge | 15% | 7.0/10 | Without-Skill nearly matches With-Skill in Analyze (8/9 substantive pass rate); gap is mainly the 30s duration identification (B2); incremental value is limited, but the AE-5 guardrail remains worth retaining | 1.05 |
| Token cost-efficiency | 15% | 6.0/10 | ~52 tokens/1pp (Lite context) — slightly above go-benchmark's floor; runtime +107% overhead is the main pressure; pre-load deployment significantly improves this | 0.90 |
| **Weighted total** | **100%** | | | **8.23/10** |

---

## 7. Conclusion

`load-test` achieved 100% pass rate across 24 assertions in three scenarios. Against the clean baseline (S2 + S3), With-Skill outperforms Without-Skill (60%) by **+40pp**. The evaluation reveals an asymmetric value distribution:

**High-value zone (Review mode, +62.5pp):**
Without-Skill can identify the major defects, but does so unsystematically — the 30s duration issue is implicitly corrected rather than explicitly flagged, avg misuse is correctly spotted but without rule attribution, and both Scorecard and Uncovered Risks are entirely absent. For serious load test reviews, the gap between "finding problems" and "systematically classifying and quantifying them" directly affects how engineering teams prioritize remediation.

**Low-value zone (Analyze mode, +14.3pp):**
Without-Skill matches With-Skill in SLO verdict, bottleneck identification, and saturation-point estimation. Both agents computed `200 VU / 0.471s ≈ 424 RPS` as the throughput ceiling, both identified the DB connection pool (18/20) as the primary bottleneck, and both provided P0/P1/P2 priority recommendations. The only clear gap is the omission of §9.9 Uncovered Risks — not an analytical depth problem, but an output compliance failure.

**Three core value points:**

1. **Scorecard three-tier gating**: In Review mode, the skill quantifies "is this script safe for production use?" into trackable Critical / Standard / Hygiene states, preventing engineers from proceeding with tests when Critical checks have failed.
2. **Forced Uncovered Risks output**: Without §9.9, test results are easily read as complete answers, silently omitting spike tests, single-replica failure degradation, idempotency, and other critical unverified scenarios. The `§9.9 is never empty` rule turns these blind spots into visible open items rather than quiet omissions.
3. **AE-x rule traceability**: Labeling a defect "AE-1: No warmup" rather than "missing warmup phase" provides engineering teams a precise reference point in SKILL.md, enabling consistent team-wide quality standards.

**Improvement recommendations:**

1. **Increase Analyze mode incremental value**: `analysis-guide.md` could add a "combined-effect analysis template" (joint probability analysis of GC pause × DB connection wait) and "cross-run regression detection standards" to push analysis output beyond the natural baseline ceiling.
2. **Optimize token efficiency**: The Scorecard template (~40 lines) and Output Contract detail (~30 lines) in SKILL.md could be migrated to a reference file with only a pointer in SKILL.md — estimated saving ~350 tokens, reducing Lite context cost from ~2,100 to ~1,750 tokens.
3. **Improve evaluation isolation**: Future A/B tests should restrict Without-Skill agents via `allowed_tools: []` or independent context isolation to prevent accidental skill-content access via tool calls or memory observations (root cause of the S1 contamination incident).
