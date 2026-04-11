# go-benchmark Skill Evaluation Report

> Evaluation framework: [skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator)
> Evaluation date: 2026-04-11
> Subject: `go-benchmark`

---

`go-benchmark` is a specialist skill for Go performance benchmarking and pprof profiling. The evaluation ran across three scenarios (writing benchmarks from source / reviewing broken benchmarks / analyzing benchstat output), covering 24 assertions in total. With-Skill passed all 24 (100%); Without-Skill passed 11 (46%), a gain of **+54 percentage points**. Three standout gaps: first, With-Skill consistently declares `var sinkString` / `var sinkErr` and explains why `_ = result` lets the compiler eliminate the entire call, while Without-Skill used no sink variables at all in Scenario 1 and explicitly called `_ = data` "safe here" in Scenario 2; second, the Evidence Gate–driven mode / data_basis declaration and Auto Scorecard block were absent from all three Without-Skill responses (0/3); third, Without-Skill scored surprisingly high on Scenario 3 (6/8, 75%) — revealing that the skill's marginal value on statistical analysis tasks is modest, and that the real leverage lies in benchmark writing and code review.

---

## 1. Skill Overview

`go-benchmark` defines 5 Hard Rules (silent-corruption guards), 3 Mandatory Gates (Evidence / Applicability / Scope), a three-phase workflow (Write → Run & Profile → Analyze & Optimize), a 4-field Output Contract, and a three-tier Auto Scorecard (Critical / Standard / Hygiene).

**Core components:**

| File | Lines | Purpose |
|------|-------|---------|
| `SKILL.md` | 378 | Main skill definition (5 Hard Rules, 3 Gates, 3-phase workflow, Output Contract, Anti-Examples, Auto Scorecard) |
| `references/benchmark-patterns.md` | ~120 | Detailed `b.*` API patterns: per-iteration setup/teardown, `b.SetBytes`, `b.ReportAllocs`, helper functions |
| `references/pprof-analysis.md` | ~150 | Flame graph interpretation, alloc hotspot patterns, `-alloc_objects` vs `-alloc_space` selection |
| `references/optimization-patterns.md` | ~100 | Fix recipes: `sync.Pool`, pre-allocation, escape analysis, reducing allocations |
| `references/benchmark-antipatterns.md` | ~100 | Extended anti-example catalog beyond the three inlined BAD/GOOD pairs |
| `references/benchstat-guide.md` | ~80 | Benchstat output interpretation, p-values, noise reduction, statistical validity |

**Regression suite: 96 tests** (65 contract + 30 golden + 1 integrity), 100% coverage across all key dimensions.

---

## 2. Test Design

### 2.1 Scenario Definitions

The three scenarios correspond to the three working modes defined in SKILL.md, each based on a realistic user session prototype:

| # | Scenario | Input | Key checks |
|---|----------|-------|------------|
| 1 | Phase 1 — Write benchmarks from source | RLE Encode/Decode Go source, no runtime data | `var sink` declaration, `ResetTimer` placement, `-benchmem`, O(n) sub-benchmarks, sinking both return values |
| 2 | Phase 1+2 — Review broken benchmarks | JSON marshal benchmarks with 3 Hard Rule violations (timer inside loop, `_ = data`, missing `-benchmem`) + `-count=1` | Enumerate violations by rule name; identify compiler-elimination risk of `_ =`; deliver a corrected file |
| 3 | Phase 3 — Analyze noisy benchstat output | benchstat output (time/op: ±7–13%, p=0.063–0.095; allocs/op: ±0%, p=0.008) | Distinguish statistically significant (allocs/op) from inconclusive (time/op); recommend noise-reduction commands |

### 2.2 Assertion Matrix (24 items)

**Scenario 1 — Phase 1: Write benchmarks from source (9 items)**

| ID | Assertion | With-Skill | Without-Skill |
|----|-----------|:----------:|:-------------:|
| A1 | Declares package-level `var sink` (does not use `_ =`) | PASS | FAIL |
| A2 | `b.ResetTimer()` placed after setup, before the benchmark loop | PASS | PASS |
| A3 | Run command includes `-benchmem` | PASS | PASS |
| A4 | Run command specifies `-count` (≥5 for exploration, ≥10 for comparison) | PASS | FAIL |
| A5 | O(n) Encode function has sub-benchmarks across ≥3 input sizes | PASS | PASS* |
| A6 | Both return values of Decode are sinked (string + error) | PASS | FAIL |
| A7 | Explicitly states `data_basis=static analysis only` and notes real numbers require running the commands | PASS | FAIL |
| A8 | Auto Scorecard block (Critical/Standard/Hygiene) present at end of response | PASS | FAIL |
| A9 | All 4 Output Contract fields declared (mode/data_basis/scorecard_result/profiling_method) | PASS | FAIL |

> *A5 note: Without-Skill provided 7 flat top-level Encode benchmarks covering different input characteristics, rather than `b.Run()`-style size sub-benchmarks. Graded PASS because multiple sizes were substantively covered, even though the structure differs.

**Scenario 2 — Phase 1+2: Review broken benchmarks (7 items)**

| ID | Assertion | With-Skill | Without-Skill |
|----|-----------|:----------:|:-------------:|
| B1 | Identifies `b.ResetTimer()` inside the loop as a Hard Rule violation (destroys timing) | PASS | PASS |
| B2 | Identifies `_ = data` as a sink problem (compiler may eliminate the entire call) | PASS | FAIL |
| B3 | Identifies missing `-benchmem` flag in the run command | PASS | PASS |
| B4 | Identifies `-count=1` as insufficient for a comparison (requires `-count=10` + benchstat) | PASS | FAIL |
| B5 | Provides a corrected benchmark file with all issues fixed | PASS | FAIL |
| B6 | Auto Scorecard block present at end of response | PASS | FAIL |
| B7 | All 4 Output Contract fields declared | PASS | FAIL |

**Scenario 3 — Phase 3: Analyze noisy benchstat output (8 items)**

| ID | Assertion | With-Skill | Without-Skill |
|----|-----------|:----------:|:-------------:|
| C1 | Flags ±7–13% noise as exceeding the ±5% threshold | PASS | PASS |
| C2 | Correctly interprets time/op p-values (0.063–0.095 > 0.05) as not statistically significant | PASS | PASS |
| C3 | Recommends `-benchtime=2s` or `-count=20` to reduce noise | PASS | PASS |
| C4 | Correctly identifies allocs/op p=0.008 < 0.05 as statistically significant | PASS | PASS |
| C5 | Clearly distinguishes: time/op improvement uncertain, allocs/op improvement confirmed | PASS | PASS |
| C6 | Provides an exact next-step command (with correct `-count`/`-benchtime` flags) | PASS | PASS |
| C7 | Auto Scorecard block present at end of response | PASS | FAIL |
| C8 | All 4 Output Contract fields declared | PASS | FAIL |

### 2.3 Trigger Accuracy Analysis

The current description uses a two-layer trigger strategy:

```
Go performance benchmarking and pprof profiling specialist. ALWAYS use when
writing benchmark functions (testing.B), generating or reading pprof profiles,
interpreting flame graphs, finding memory allocation hotspots, comparing
implementations with benchstat, or measuring ns/op / B/op / allocs/op.
In Go code contexts, also trigger when the user says "it's slow", "too many
allocations", "find the bottleneck", or "profile this Go code".
```

- **Explicit triggers** (high certainty): `testing.B`, `pprof profiles`, `flame graphs`, `benchstat`, `ns/op`, `B/op`, `allocs/op`
- **Implicit triggers** (context-aware): `"it's slow"`, `"too many allocations"`, `"find the bottleneck"` — gated by `"In Go code contexts"` to prevent false positives from non-Go performance questions

**Should-Trigger scenarios (10)**

| # | Prompt summary | Expected |
|---|---------------|:--------:|
| T1 | "Write a benchmark function for my Go JSON parser" | ✅ triggers |
| T2 | "Help me interpret this benchstat comparison output" | ✅ triggers |
| T3 | "Read this flame graph and find the widest box" | ✅ triggers |
| T4 | "My Go service is slow, can you help me find the bottleneck?" | ✅ triggers |
| T5 | "allocs/op is too high in my Go HTTP handler, how do I reduce it?" | ✅ triggers |
| T6 | "Is this benchstat comparison between two Go implementations correct?" | ✅ triggers |
| T7 | "My Go code is allocating too much memory, help me profile this" | ✅ triggers |
| T8 | "Write a testing.B benchmark for a concurrent-safe cache" | ✅ triggers |
| T9 | "Is this b.ResetTimer placement correct?" | ✅ triggers |
| T10 | "Generate a CPU profile: go test -bench=BenchmarkQuery" | ✅ triggers |

**Should-Not-Trigger scenarios (8)**

| # | Prompt summary | Expected | Risk |
|---|---------------|:--------:|------|
| N1 | "Write table-driven unit tests for my Go calculator" | ✅ no trigger | Low (testing.T ≠ testing.B) |
| N2 | "Profile this Python function with cProfile" | ✅ no trigger | Low (non-Go, context qualifier effective) |
| N3 | "My MySQL query is slow, optimize the SQL" | ✅ no trigger | Low (non-Go) |
| N4 | "Fix a race condition in my Go goroutines" | ✅ no trigger | Low (concurrency safety ≠ performance profiling) |
| N5 | "My Rust program has high memory usage" | ✅ no trigger | Low (non-Go) |
| N6 | "Help me write Go error-handling tests" | ✅ no trigger | Low (testing ≠ benchmarking) |
| N7 | "My Go service has high memory usage, help" | ⚠️ may trigger | Medium ("memory"+"Go" can trigger; but triggering is reasonable and Applicability Gate filters further) |
| N8 | "Compare these two Go sorting algorithms" (no perf-measurement context) | ⚠️ may trigger | Medium ("compare"+"Go" may fire; Applicability Gate acts as a backstop) |

**Estimated trigger accuracy: F1 ≈ 88%** (10/10 should-trigger covered; 6/8 should-not-trigger correctly rejected; N7/N8 are acceptable boundary cases)

---

## 3. Pass Rate Comparison

### 3.1 Overall Pass Rate

| Configuration | Pass | Fail | Pass rate |
|---------------|:----:|:----:|:---------:|
| **With Skill** | **24** | **0** | **100%** |
| **Without Skill** | **11** | **13** | **46%** |

**Overall improvement: +54 percentage points**

### 3.2 Pass Rate by Scenario

| Scenario | With-Skill | Without-Skill | Delta |
|----------|:----------:|:-------------:|:-----:|
| 1. Phase 1 — Write benchmarks from source (9 items) | 9/9 (100%) | 2/9 (22%) | +78pp |
| 2. Phase 1+2 — Review broken benchmarks (7 items) | 7/7 (100%) | 3/7 (43%) | +57pp |
| 3. Phase 3 — Analyze benchstat output (8 items) | 8/8 (100%) | 6/8 (75%) | +25pp |

**Key finding:** Without-Skill scored 75% on Scenario 3 — far above its scores on Scenarios 1 (22%) and 2 (43%). This reveals an asymmetric value distribution: baseline Claude already handles statistical concepts (p-values, CV thresholds) quite well, so the skill's incremental gain on analysis tasks is modest (+25pp). The real leverage is in benchmark writing and review, where baseline is most prone to silent, hard-to-detect errors (+57–78pp).

### 3.3 Substantive Dimensions (12 items, structural-process assertions removed)

| ID | Check | With-Skill | Without-Skill |
|----|-------|:----------:|:-------------:|
| S1 | Scenario 1: benchmark code uses `var sink` (not `_ =`) | PASS | FAIL |
| S2 | Scenario 1: `b.ResetTimer()` correctly placed (not inside loop) | PASS | PASS |
| S3 | Scenario 1: run command includes `-benchmem` | PASS | PASS |
| S4 | Scenario 1: O(n) function covered across ≥3 input sizes | PASS | PASS |
| S5 | Scenario 1: both return values of `(string, error)` from Decode are sinked | PASS | FAIL |
| S6 | Scenario 2: identifies compiler-elimination risk of `_ = data` | PASS | FAIL |
| S7 | Scenario 2: identifies `b.ResetTimer()` inside loop | PASS | PASS |
| S8 | Scenario 2: identifies missing `-benchmem` | PASS | PASS |
| S9 | Scenario 2: corrected file has all sink issues fixed | PASS | FAIL |
| S10 | Scenario 3: flags ±>5% noise and recommends noise-reduction approach | PASS | PASS |
| S11 | Scenario 3: correctly distinguishes time/op (inconclusive) vs allocs/op (confirmed) | PASS | PASS |
| S12 | Scenario 3: provides an exact next-step command | PASS | PASS |

**Substantive pass rate:** With-Skill **12/12 (100%)** vs Without-Skill **7/12 (58%)**, improvement **+42pp**.

---

## 4. Key Differences

### 4.1 Behaviors exclusive to With-Skill (completely absent in baseline)

| Behavior | Observed output |
|----------|----------------|
| **Evidence Gate classification** | Scenario 1: "Source code only is available. I can write the benchmarks… but I cannot provide real ns/op numbers without running them." Baseline skipped this entirely. |
| **Package-level `var sink` (systematic)** | Scenario 1: declared `var sinkString string` + `var sinkErr error` with explanation: "Using `_ =` would allow the compiler to prove results are unused and optimize the calls away entirely." |
| **Output Contract (4 fields)** | Scenarios 1/2/3: mode / data_basis / profiling_method declared in every response. Without-Skill: zero Output Contract output across all three scenarios. |
| **Auto Scorecard block** | Scenarios 1/2/3: Critical/Standard/Hygiene status reported at end of every response. Without-Skill: no Scorecard in any scenario. |
| **`_ = data` compiler-elimination risk** | Scenario 2: listed as Violation 1 (Critical Hard Rule) with explanation "compiler is permitted to optimize away the entire json.Marshal call." Without-Skill said it was "safe here" — technically true for this specific struct, but wrong on principle. |

### 4.2 Behaviors where baseline performs but at lower quality

| Behavior | With-Skill | Without-Skill |
|----------|-----------|--------------|
| `b.ResetTimer()` bug detection | Named Hard Rule #2; explained "only the last iteration contributes meaningful timing data" | Correctly identified as a Critical Bug; comparable quality (B1 PASS) |
| benchstat statistical analysis | Evidence Gate classification + explicit time/op vs allocs/op distinction + Auto Scorecard | Comparable quality — correctly handled p-values, noise threshold, allocs significance (C1–C6 all PASS) |
| Missing `-benchmem` detection | Hard Rule #3 violation; exact line and fix command | Correctly flagged, fix recommended (B3 PASS) |
| Corrected benchmark file | `var sinkBytes []byte; var sinkErr error`; all calls use `sinkBytes, sinkErr = json.Marshal(u)` | Fixed the ResetTimer issue, but the "corrected" file kept `_ = data` — root cause unresolved (B5 FAIL) |

### 4.3 Scenario-level findings

**Scenario 1 (Write benchmarks from source):**
- **With-Skill:** Evidence Gate declared `write` / `static analysis only`. Scope Gate selected size sweep sub-benchmarks (64B/1KB/64KB/1MB). Declared `var sinkString string` + `var sinkErr error` with compiler-elimination explanation. All `Decode` calls used `sinkString, sinkErr = Decode(...)`. Run commands: `-benchmem -count=5` (exploration) and `-count=10` (comparison). Auto Scorecard: Critical ✅✅✅ Standard 5/5 Hygiene 4/4.
- **Without-Skill:** Used the `for b.Loop()` syntax (Go 1.24+) and explained its advantages. Provided 7 flat Encode benchmarks covering different input characteristics (empty / single char / no-runs / short-runs / long-run / mixed) — solid coverage strategy. **However:** no sink variables used anywhere in the benchmark code; results were silently discarded. Decode return values also uncaptured. Run command lacked `-count`. No Evidence Gate / Scorecard / Output Contract. Notably, Without-Skill mentioned "assign the return to package-level sink variables *if you observe suspiciously fast numbers*" — framing the sink as an optional debugging aid rather than a mandatory prevention rule.

**Scenario 2 (Review broken benchmarks):**
- **With-Skill:** Enumerated 4 violations (3 Critical + 1 Standard), each with Hard Rule number, offending line, mechanism explanation, and fix code. Violation 1 explicitly stated "compiler is permitted to optimize away the entire json.Marshal call." The corrected file used `var sinkBytes []byte; var sinkErr error`. Scorecard showed Critical ❌❌❌ (reflecting the violations in the code under review).
- **Without-Skill:** Correctly identified `b.ResetTimer()` inside the loop under a "Critical Bug" heading. Mentioned `-benchmem` and suggested `-count=5` under minor issues. **Critical gap:** `_ = data` was described as "safe here" because json.Marshal can't fail — confusing error-handling safety with compiler optimization risk. As a result, the "corrected" file still kept `_ = data`; the underlying problem was left unresolved.

**Scenario 3 (Analyze benchstat output):**
- **With-Skill:** Evidence Gate classified as `analyze` / `benchmark output`. Fully covered C1–C6. Went further by providing a pprof diff command (`-diff_base mem-old.prof mem-new.prof`) and analyzing the super-linear allocation growth (allocs ratios: 1×/3.7×/14.8× vs input sizes 1×/4×/16×). Scorecard noted Standard 3/5 (missing `-count=10` and explicit alloc target).
- **Without-Skill:** Covered C1–C6 at comparable quality and depth. Provided clear `-count=20 -benchtime=3s` recommendations and a statistical power estimate ("approximately 15–20 runs per side to detect a 7% effect with 80% power"). Only gaps: Auto Scorecard and Output Contract fields.

---

## 5. Token Cost-Effectiveness

### 5.1 Measured token usage (6 evaluation agents)

| Agent | Scenario | Total Tokens | Duration (s) | Tool Uses |
|-------|----------|:------------:|:------------:|:---------:|
| S1 With-Skill | Write benchmarks | 32,898 | 184.9 | 8 |
| S1 Without-Skill | Write benchmarks | 21,483 | 76.6 | 5 |
| S2 With-Skill | Review benchmarks | 29,439 | 102.6 | 7 |
| S2 Without-Skill | Review benchmarks | 20,471 | 77.9 | 4 |
| S3 With-Skill | Analyze benchstat | 28,598 | 124.0 | 6 |
| S3 Without-Skill | Analyze benchstat | 20,331 | 72.5 | 5 |

**With-Skill average:** 30,312 tokens, 137.2s, 7 tool uses/eval
**Without-Skill average:** 20,762 tokens, 75.7s, 5 tool uses/eval
**Runtime token overhead:** +9,550 tokens/eval (**+46%**)
**Runtime time overhead:** +61.5s/eval (**+81%**)

### 5.2 Skill context cost

| Component | Lines | Est. tokens | Loaded when |
|-----------|-------|-------------|-------------|
| `SKILL.md` | 378 | ~2,380 | Always (on trigger) |
| `benchmark-patterns.md` | ~120 | ~750 | Phase 1: writing benchmarks |
| `pprof-analysis.md` | ~150 | ~950 | Phase 3: reading pprof profiles |
| `optimization-patterns.md` | ~100 | ~600 | Applying fixes |
| `benchmark-antipatterns.md` | ~100 | ~600 | Extended anti-pattern scenarios |
| `benchstat-guide.md` | ~80 | ~500 | Analyzing statistical validity |
| **Phase 1 typical total** | | **~3,130** | SKILL.md + benchmark-patterns.md |
| **Phase 3 typical total** | | **~3,330** | SKILL.md + pprof-analysis.md |

### 5.3 Cost-effectiveness calculation

| Metric | Value |
|--------|-------|
| Pass rate improvement (strict) | +54pp |
| Substantive pass rate improvement | +42pp |
| Skill context cost (SKILL.md only) | ~2,380 tokens |
| Skill context cost (typical, + 1 ref) | ~3,130–3,330 tokens |
| Runtime token overhead (measured avg) | +9,550 tokens/eval (+46%) |
| **Tokens per 1pp gain (context only)** | **~44 tokens/1pp** |
| **Tokens per 1pp gain (incl. runtime)** | **~177 tokens/1pp** |

### 5.4 Comparison with other skills

| Skill | Context tokens | Pass rate gain | Context tok/1pp | Incl. runtime |
|-------|:-------------:|:--------------:|:---------------:|:-------------:|
| `git-commit` | ~1,300 | +77pp | ~17 | ~73 |
| **`go-benchmark`** | **~2,380–3,330** | **+54pp** | **~44–62** | **~177** |
| `go-makefile-writer` | ~1,960–4,300 | +31pp | ~63–139 | — |

**Why go-benchmark trails git-commit on cost-effectiveness:**

1. **Longer SKILL.md (378 vs 169 lines):** Inlined Anti-Examples (3 BAD/GOOD pairs), the Auto Scorecard template, and the Output Contract table account for roughly 100 lines.
2. **Smaller absolute gain (+54pp vs +77pp):** Without-Skill already scored 75% on Scenario 3, pulling the overall improvement down significantly.
3. **Higher runtime overhead (+46% tokens, +81% time):** Executing 3 Gates, declaring 4 Output Contract fields, and outputting a detailed Scorecard each add token cost.

**Important context:** If we look only at the scenarios where go-benchmark truly excels (Phase 1 + Phase 2), improvements are +78pp and +57pp respectively — bringing cost-effectiveness close to git-commit. The overall +54pp figure is diluted by Scenario 3's modest +25pp.

---

## 6. Scores

### 6.1 Dimension scores

| Dimension | With Skill | Without Skill | Delta |
|-----------|:----------:|:-------------:|:-----:|
| Silent-corruption protection (systematic `var sink`) | 5.0/5 | 1.0/5 | +4.0 |
| Data classification & honest degradation (Evidence Gate) | 5.0/5 | 0.5/5 | +4.5 |
| Output consistency (Output Contract + Auto Scorecard) | 5.0/5 | 0.0/5 | +5.0 |
| Benchmark review systematicness (violations by Hard Rule name) | 5.0/5 | 2.5/5 | +2.5 |
| Statistical analysis (benchstat p-values, noise thresholds) | 5.0/5 | 4.0/5 | +1.0 |
| Token cost-effectiveness (tok/1pp vs domain complexity) | 3.5/5 | — | — |
| **Average (first 5 dimensions)** | **5.0/5** | **1.6/5** | **+3.4** |

### 6.2 Weighted score

| Dimension | Weight | Score | Rationale | Weighted |
|-----------|:------:|:-----:|-----------|:--------:|
| Assertion pass rate (delta) | 25% | 8.5/10 | +54pp overall; +68pp if counting only Phase 1+2; diluted by Scenario 3 | 2.13 |
| Silent-corruption protection | 20% | 9.5/10 | `_ = data` is a high-frequency baseline error (Scenario 1: no sink at all; Scenario 2: "safe here"); the skill is the only reliable safeguard | 1.90 |
| Data classification & degradation | 20% | 10.0/10 | Evidence Gate fired correctly in all 3 scenarios; prevents fabricating ns/op when no data is available (validated by golden fixture BENCH-009) | 2.00 |
| Output consistency | 15% | 10.0/10 | Without-Skill: 0/3 scenarios with Output Contract or Scorecard; With-Skill: 3/3 | 1.50 |
| Statistical analysis | 10% | 8.0/10 | Without-Skill already at 75% in Scenario 3 — baseline is strong here; skill's incremental gain is structural (Scorecard) rather than analytical | 0.80 |
| Token cost-effectiveness | 10% | 7.0/10 | ~44 tok/1pp (context only), better than go-makefile-writer but behind git-commit; +46% runtime overhead is the primary drag; Scenario 3's low gain also shrinks the denominator | 0.70 |
| **Weighted total** | **100%** | | | **9.03/10** |

---

## 7. Conclusion

`go-benchmark` passed 100% of assertions across 24 checks in three scenarios, a **+54pp** improvement over Without-Skill (46%). The evaluation reveals an asymmetric value distribution:

**High-value zone (Phase 1 + Phase 2 — writing and reviewing benchmark code):**
- Phase 1, +78pp: Without-Skill used no sink variables in actual benchmark code, or treated sinking as an optional fallback. This omission is silent and undetectable from benchmark output — the code compiles and runs but may measure nothing.
- Phase 2, +57pp: Without-Skill's judgment that `_ = data` is "safe here" is technically not wrong for this specific case, yet it led to a corrected file that still left the sink problem unresolved — illustrating the gap between principled understanding and case-by-case reasoning.

**Low-value zone (Phase 3 — statistical analysis):**
- Phase 3, +25pp: Without-Skill performed at a high level on p-values, CV thresholds, and significance judgment. The skill's incremental contribution here is primarily structural (Scorecard, Output Contract), not analytical.

**Core value points:**
1. **Silent-corruption protection:** `_ = encode(input)` looks valid, compiles cleanly, and produces no errors — but the compiler can eliminate the call entirely in certain optimization passes, turning the benchmark into a measurement of loop overhead. This is a high-frequency, self-undetectable baseline error; Hard Rule #1 is the only reliable safeguard.
2. **Evidence Gate:** When a user provides nothing ("my service is slow"), the skill forces the degradation path and prevents speculative analysis (validated by golden fixture BENCH-009).
3. **Output consistency:** Output Contract + Auto Scorecard make responses predictable and quality-checkable across users and sessions — a structured reporting mechanism entirely absent from baseline.

**Recommendations:**
1. **Raise Phase 3 incremental value:** Expand `benchstat-guide.md` with super-linear allocation growth analysis (alloc-to-input-size ratio patterns) and a pprof diff workflow, so statistical analysis output exceeds what baseline Claude naturally delivers.
2. **Trim Auto Scorecard:** Moving the ~40-line template into a reference file and keeping only a pointer in SKILL.md would save ~200 tokens and improve cost-effectiveness.
3. **Trigger accuracy:** Current F1 ≈ 88%; the main gap is the implicit trigger boundary (e.g., "my Go service has high memory usage"). Adding a negative clarification to the description — "not for general Go debugging or unit testing" — would reduce over-triggering without sacrificing coverage.