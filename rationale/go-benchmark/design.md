---
title: go-benchmark skill design rationale
owner: awesome-skills maintainers
status: active
last_updated: 2026-04-11
applicable_versions: current repository version
---

# go-benchmark Skill Design Rationale

`go-benchmark` is a skill for Go performance benchmarking and pprof profiling. Its core design idea is: **benchmark correctness must be enforced before measurement begins, because a corrupted benchmark produces numbers that look real but mean nothing.** That is why the skill leads with Hard Rules and Mandatory Gates rather than jumping straight to code generation.

## 1. Definition

`go-benchmark` is a structured Go performance engineering skill. Given source code, existing benchmark output, or a pprof profile, it classifies what the user actually has, determines whether the target is benchmarkable, selects the right benchmark shape, writes or reviews benchmark code against five hard correctness rules, interprets statistical output, and delivers a consistent quality report in every response.

## 2. Background and Problems

The skill is not solving "developers don't know what a benchmark is." It is solving "benchmark code that looks correct but silently measures the wrong thing."

Without systematic guidance, benchmark failures cluster into two broad categories:

**Silent corruption** — the benchmark compiles and runs, but the measurement is invalid:

| Problem | Mechanism | Why it is hard to detect |
|---------|-----------|--------------------------|
| `_ = result` discards the return | The compiler proves the result is unused and eliminates the call entirely | Output still shows ns/op; it is just measuring loop overhead |
| `b.ResetTimer()` inside the loop | Accumulated time is discarded on every iteration; only the last iteration contributes | Results look plausible but are highly variable and artificially compressed |
| Setup code runs inside the loop | Expensive one-time work (DB connect, fixture load) is measured on every iteration | ns/op is inflated; the benchmark measures setup, not the hot path |
| Missing `-benchmem` | `B/op` and `allocs/op` columns are absent | Allocation regressions are invisible; a function appears fast while silently growing GC pressure |

**Statistical invalidity** — the benchmark runs correctly, but the conclusions drawn from it are wrong:

| Problem | Consequence |
|---------|-------------|
| `-count=1` for a comparison | Single-run variance can be ±30%; any delta observed could be noise |
| ± > 5% CV in benchstat | The signal-to-noise ratio is too low to detect typical improvements (5–10%) |
| p > 0.05 treated as significant | False claims of improvement that will not reproduce in production |
| Comparing across environments | Results from different machines, Go versions, or CPU settings are not comparable |

A third failure mode matters especially for an AI-driven skill: **fabrication under uncertainty.** Without explicit rules, a model asked to "analyze performance" with no data will produce plausible-sounding ns/op estimates or invent flame graph hotspots. These outputs look authoritative but are purely speculative. The skill's design explicitly prevents this.

## 3. Comparison with Common Alternatives

| Dimension | `go-benchmark` skill | Ad-hoc benchmarking | pprof alone |
|-----------|---------------------|---------------------|-------------|
| Sink correctness | Hard Rule (mandatory) | Depends on developer knowledge | N/A |
| Timer placement | Hard Rule (mandatory) | Frequently wrong | N/A |
| `-benchmem` enforcement | Hard Rule (mandatory) | Often skipped | N/A |
| Statistical validity guidance | Built-in | Rarely applied | N/A |
| Honest degradation when data is missing | Explicit table | Model fabricates or guesses | N/A |
| Benchmark shape selection | Scope Gate (5 shapes) | One-size-fits-all | N/A |
| Output consistency | Output Contract + Auto Scorecard | None | None |
| Reference depth (patterns, antipatterns, optimization) | 5 reference files on demand | None | Limited |

The skill is not trying to replace `go test` or `go tool pprof`. It fills the layer between "I know these tools exist" and "I am using them correctly and drawing valid conclusions."

## 4. Core Design Rationale

### 4.1 Hard Rules Come First

Before any benchmark is written or reviewed, five rules are checked. They are called Hard Rules because a single violation silently invalidates everything else:

| Rule | Problem it prevents |
|------|---------------------|
| Sink every result — assign to a package-level `var sink T` | Compiler dead-code elimination of the benchmarked call |
| Timer discipline — setup before `b.ResetTimer()`, teardown with `b.StopTimer()`/`b.StartTimer()` | Setup time counted in the measurement |
| Always `-benchmem` | Invisible allocation regressions |
| `-count=10` for comparisons, `-count=5` for exploration | Statistically meaningless single-run deltas |
| Never compare across environments | Machine-specific, non-transferable conclusions |

The sink rule deserves extra explanation because it is the least intuitive. Consider:

```go
// Looks correct — assigns to blank identifier
func BenchmarkWrong(b *testing.B) {
    for i := 0; i < b.N; i++ {
        _ = expensiveFunc(input)
    }
}
```

The Go compiler is permitted to prove that if a result is assigned only to `_`, the assignment and the call producing it are both dead code. In some optimization passes, the entire `expensiveFunc` call is eliminated. The benchmark then measures an empty loop. The output still shows ns/op — it just shows the wrong number.

The fix is to assign to a package-level variable:

```go
var sink Result  // package-level, exported or unexported

func BenchmarkRight(b *testing.B) {
    for i := 0; i < b.N; i++ {
        sink = expensiveFunc(input)
    }
}
```

A package-level variable forces the result to escape, keeping the call real. This is why the skill treats it as Hard Rule #1 rather than a stylistic preference.

**Why not just catch violations during review?** Because the error is invisible at runtime. A corrupted benchmark compiles cleanly, runs silently, and produces output that looks exactly like valid output. The only reliable defence is to enforce the rule before the benchmark is written, not after the numbers have been trusted.

### 4.2 Three Mandatory Gates Run Before Any Work

Three gates run in sequence before the skill produces any benchmark code, analysis, or advice:

```
Evidence Gate → Applicability Gate → Scope Gate
```

**Evidence Gate — classify what you actually have:**

| Available | Mode | Data-basis label |
|-----------|------|-----------------|
| Source code only | `write` | `static analysis only` |
| Benchmark output (text) | `review` | `benchmark output` |
| pprof profile | `analyze` | `pprof profile` |
| Nothing meaningful | — | Ask the user what they have |

The gate does two things. First, it forces a realistic assessment of capability: with source code only, the skill can write benchmarks and reason about likely escape points, but it cannot provide real ns/op or allocs/op numbers. Second, it supplies the `data_basis` label that appears in the Output Contract, making the response's epistemic foundation explicit to the reader.

**Applicability Gate — confirm the target is benchmarkable:**

Not every function is worth benchmarking. The gate stops the workflow for:
- Trivial wrappers with no meaningful computation (a single field access, a constant return).
- Functions whose output is non-deterministic with no stable hot path to isolate.

The gate's stop message is explicit: "No meaningful benchmark target found. [Reason]. Describe what you want to optimize and I will help identify the right approach." This is intentionally more useful than generating a benchmark that will produce noisy, uninterpretable results.

**Scope Gate — select the right benchmark shape:**

| Scenario | Shape |
|----------|-------|
| One function, one scenario | `BenchmarkFuncName` |
| Comparing two implementations | `b.Run("old", ...)` / `b.Run("new", ...)` + `-count=10` + benchstat |
| O(n) function where input size matters | Sub-benchmarks across ≥3 input sizes |
| Goroutine-safe or cache-contested code | `b.RunParallel` |
| No baseline yet and the production profile shows a hotspot | Run pprof first, identify top-3 hotspots, then target benchmarks |

The gate eliminates the common failure of applying the wrong shape — for example, writing a single `BenchmarkFuncName` when the function is O(n) and the performance characteristic changes radically between small and large inputs. The sub-benchmark pattern exposes this scaling behavior; a flat benchmark hides it.

### 4.3 Honest Degradation Is an Explicit Table

A model skill without explicit degradation rules will fill gaps with plausible-sounding content. For performance benchmarking, the consequences are particularly harmful: an invented ns/op number or a fabricated pprof hotspot creates false confidence, which is worse than admitting uncertainty.

`go-benchmark` solves this with an explicit Honest Degradation table that maps each availability level to what can and cannot be done:

| Available | What you can do | What to say if it's missing |
|-----------|----------------|----------------------------|
| Source code only | Write benchmarks + static alloc hints via `-gcflags="-m"` | "I can write the benchmarks and show likely escape points, but I can't give real ns/op or allocs/op numbers without running them." |
| Benchmark output (text) | Interpret ns/op, flag high allocs | "I can interpret these numbers, but without a pprof profile I can only point at likely hotspots — not confirm them." |
| pprof profile | Full Phase 3 analysis | — |
| Neither code nor data | Explain the workflow; ask what they have | — |

The final row is the most important. When a user says "my service is slow" with nothing else attached, the correct response is to describe the three-phase workflow and ask what they can share — not to speculate about likely bottlenecks.

**Why not rely on the model's judgment?** Because judgment is inconsistent under pressure to be helpful. Explicit rules produce consistent output: the same input always produces the same degradation path, regardless of how confident the user sounds.

### 4.4 Three-Phase Workflow Maps to Data Availability

The three-phase structure (Write → Run & Profile → Analyze & Optimize) is not a linear mandatory sequence. It is a map from what the user has to what work is possible:

- **Phase 1 (Write):** source code available, no runtime data. Output: benchmark file + run command. Cannot produce real numbers.
- **Phase 2 (Run & Profile):** provides exact commands for running benchmarks and generating pprof profiles. Primarily instructional — the model gives commands, the user runs them.
- **Phase 3 (Analyze):** benchmark output or pprof profile available. Output: annotated interpretation, hotspot identification, per-hotspot fix with before/after code, next-step command.

This structure prevents two common mismatches:
- Skipping to analysis when no data exists.
- Staying in Phase 1 when the user has already provided pprof and wants optimization guidance.

The Evidence Gate determines which phase the response begins in. The phases are not re-executed in sequence on every request — they are entry points.

### 4.5 Reference Files Are Split by Concern and Loaded on Demand

`go-benchmark` has five reference files:

| File | Content | Loaded when |
|------|---------|-------------|
| `benchmark-patterns.md` | `b.*` API details: per-iteration setup/teardown, `b.SetBytes`, `b.ReportAllocs`, helper functions | Phase 1: writing or reviewing benchmark code |
| `pprof-analysis.md` | Flame graph reading, alloc hotspot patterns, `-alloc_objects` vs `-alloc_space` | Phase 3: reading pprof or flame graphs |
| `optimization-patterns.md` | Fix recipes: `sync.Pool`, pre-allocation, escape analysis, reducing allocs | Phase 3: applying fixes after profiling |
| `benchmark-antipatterns.md` | Extended anti-example catalog beyond the three inlined pairs | Extended review scenarios |
| `benchstat-guide.md` | Benchstat output, p-values, noise reduction, statistical validity | Analyzing benchstat with statistical rigor |

This split serves two goals. First, it keeps SKILL.md at 378 lines — long enough to cover the full workflow with precision, short enough to stay focused. Second, it means a Phase 1 request (writing benchmarks) never loads pprof analysis content, and a Phase 3 request (reading a flame graph) never loads benchmark writing patterns. Each request pays only for what it needs.

The decision of which file to load is made by explicit rules in SKILL.md, not by the model's judgment about what might be relevant. This is the same principle as the Evidence Gate: determinism over improvisation.

### 4.6 Output Contract Makes Every Response Verifiable

Every `go-benchmark` response must declare four fields:

| Field | Allowed values |
|-------|---------------|
| `mode` | `write` \| `review` \| `analyze` |
| `data_basis` | `static analysis only` \| `benchmark output` \| `pprof profile` |
| `scorecard_result` | The full Auto Scorecard block |
| `profiling_method` | `none` \| `cpu` \| `memory` \| `mutex` \| `block` |

Omitting any field is treated as a contract violation.

The purpose of the contract is not formality — it is verifiability. A user reading the response can immediately check: "Did this claim to produce real numbers when only source code was provided?" (Answered by `data_basis`.) "Did all three Critical rules pass?" (Answered by `scorecard_result`.) "Did the analysis use CPU profiling or memory profiling?" (Answered by `profiling_method`.)

Without the contract, quality checking relies on reading the full response carefully. With it, quality signals are surfaced to a consistent, scannable location in every response.

### 4.7 Auto Scorecard Produces a Quality Report at the End of Every Response

The Auto Scorecard checks every response against three tiers of criteria:

**Critical (all three must pass — any failure means redo):**
- Every benchmark assigns its result to a package-level sink.
- `-benchmem` is included in all run commands.
- `b.ResetTimer()` is placed correctly when setup exists.

**Standard (4 of 5 must pass):**
- `-count=10` (or higher) for comparative benchmarks; `-count=5` is acceptable for exploratory runs.
- O(n) functions have sub-benchmarks across ≥3 input sizes.
- `benchstat` is used when comparing two implementations.
- Explicit alloc target stated (e.g., "goal: ≤1 allocs/op").
- Profile files named descriptively, not left as default.

**Hygiene (3 of 4 must pass):**
- Parallel benchmark added if function is goroutine-safe.
- Sub-benchmark names are human-readable.
- pprof analysis calls out top-3 hotspot functions by name.
- Environment noted when sharing results (Go version, CPU, OS).

The tiering is intentional. Critical rules protect against invalid measurements — a single violation makes all numbers untrustworthy. Standard rules protect against insufficient rigor — violating one is acceptable if it does not apply to the current task. Hygiene rules reflect good practice but have legitimate exceptions.

The evaluation data confirms this works: across 24 assertions in 3 test scenarios, With-Skill passed 100%; Without-Skill passed 46%. The widest gap was in output structure and sink correctness — exactly what the Scorecard and Hard Rules are designed to enforce.

### 4.8 Anti-Examples Are Inlined, Not Just Referenced

SKILL.md contains three BAD/GOOD code pairs directly in the body:

1. `_ = expensiveFunc(input)` vs `sink = expensiveFunc(input)` — compiler dead-code elimination.
2. Setup inside the loop vs setup before `b.ResetTimer()` — measuring setup instead of the hot path.
3. `-count=1` vs `-count=10` + benchstat — statistically invalid delta.

These are the three most common silent benchmark errors. They are inlined (not in a reference file) because they serve as detection anchors: the skill checks incoming benchmark code directly against these patterns before reading anything else. Putting them in a reference file that is only loaded on demand would introduce latency into the most critical part of the review.

The test suite's 11 golden fixtures (BENCH-001 through BENCH-011) formalize these patterns as machine-verifiable regression cases.

## 5. Problems This Design Addresses

Cross-referencing `SKILL.md` and the evaluation report, the skill targets these concrete engineering problems:

| Problem | Corresponding design | Practical effect |
|---------|---------------------|-----------------|
| Silent benchmark corruption via `_ =` | Hard Rule #1 (sink) + inlined anti-example | Caught before the benchmark is written; not detectable from benchmark output alone |
| Timer corrupted by setup in loop | Hard Rule #2 (timer discipline) + inlined anti-example | Identified with specific line reference and one-line fix |
| Missing `-benchmem` | Hard Rule #3 | Allocation regressions stay visible on every run |
| Statistically invalid comparisons | Hard Rule #4 (`-count=10`) | Prevents claims from noisy single-run deltas |
| Cross-environment comparison | Hard Rule #5 | Prevents non-transferable conclusions |
| Benchmarking untargetable functions | Applicability Gate | Stops before generating useless code |
| Wrong benchmark shape for the scenario | Scope Gate (5 shapes) | O(n) functions get size sweeps; concurrent code gets RunParallel |
| Fabricated analysis when no data exists | Honest Degradation table | Every degradation path is explicit, not model-discretion |
| Inconsistent output quality | Output Contract + Auto Scorecard | Every response declares its data basis and quality status |
| Benchmark patterns not recalled in full | 5 reference files loaded on demand | API depth available without bloating the main file |

## 6. Key Highlights

### 6.1 Preventing Silent Corruption Before It Happens

The most important contribution of this skill is that it catches the class of errors that are invisible at runtime. A benchmark producing wrong numbers looks identical to one producing correct numbers. Hard Rules convert this invisible risk into a mandatory pre-flight check.

### 6.2 Making the Evidence Explicit

Every response declares its `data_basis`. This forces honest accounting: if only source code was available, the response cannot claim to provide real ns/op values. The Evidence Gate and the Honest Degradation table together make this accounting automatic rather than a matter of individual discipline.

### 6.3 Consistent Output Makes Quality Auditable

The Output Contract ensures that every `go-benchmark` response contains the same four fields in a consistent location. The Auto Scorecard ensures that every response ends with a machine-readable quality summary. This makes it possible to audit a batch of benchmark reviews without reading each response in full.

### 6.4 Reference Depth Without Context Bloat

Five reference files covering benchmark patterns, pprof analysis, optimization fixes, antipatterns, and benchstat interpretation give the skill genuine depth for complex tasks — without burdening simple requests with content they do not need. The skill loads only what the current request requires.

## 7. When to Use It — and When Not To

| Scenario | Suitable | Reason |
|----------|----------|--------|
| Writing benchmark functions from scratch | Yes | All Hard Rules enforced at generation time |
| Reviewing existing benchmarks for correctness | Yes | Systematic Hard Rule audit vs. pattern matching |
| Interpreting benchstat output | Yes | p-value, CV threshold, and statistical validity guidance |
| Reading a pprof flame graph | Yes | Hotspot identification, alloc vs. time profiling selection |
| Comparing two implementations | Yes | Scope Gate selects the right shape; Hard Rule #4 enforces `-count=10` |
| Profiling a trivial wrapper | No | Applicability Gate stops this explicitly |
| Getting real ns/op without running the code | No | Evidence Gate declares `static analysis only`; no fabrication |
| Benchmarking across two machines to compare | No | Hard Rule #5 prevents this conclusion |

## 8. Conclusion

The skill's real strength is not that it generates syntactically correct benchmark code. It is that it enforces the correctness properties that make benchmark results trustworthy. Through Hard Rules, three Mandatory Gates, the Honest Degradation table, and a consistent Output Contract, it converts a domain where errors are invisible and conclusions are frequently wrong into a domain where quality is checkable and claims are grounded in declared evidence.

From a design standpoint, this skill is a clear example of one core principle: **the output of a benchmark is not a number — it is a claim about the performance of code. Claims require evidence, and evidence requires honesty about what was actually measured.** Every design decision in `go-benchmark` follows from this principle.

## 9. Document Maintenance

This document should be updated when:

- The Hard Rules, Mandatory Gates, or workflow in `skills/go-benchmark/SKILL.md` change.
- Any reference file in `skills/go-benchmark/references/` changes substantially.
- Key data in `evaluate/go-benchmark-skill-eval-report.md` that supports conclusions in this document changes.
- The golden fixture set in `skills/go-benchmark/scripts/tests/golden/` is expanded or revised.

Review quarterly; review immediately if the `go-benchmark` skill undergoes significant refactoring.

## 10. Further Reading

- `skills/go-benchmark/SKILL.md`
- `skills/go-benchmark/references/benchmark-patterns.md`
- `skills/go-benchmark/references/pprof-analysis.md`
- `skills/go-benchmark/references/optimization-patterns.md`
- `skills/go-benchmark/references/benchmark-antipatterns.md`
- `skills/go-benchmark/references/benchstat-guide.md`
- `evaluate/go-benchmark-skill-eval-report.md`