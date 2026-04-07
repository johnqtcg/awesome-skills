---
name: fuzzing-test
description: Generate Go fuzz tests (Go 1.18+ testing.F) for specified code when users ask for fuzzing/模糊测试/fuzz test generation, parser robustness, round-trip, or differential fuzzing. Always run an applicability gate first; if the target is not suitable, explain concrete reasons and stop without writing fuzz test code.
allowed-tools: Read, Write, Grep, Glob, Bash(go test*), Bash(go build*), Bash(go clean*), Bash(go tool cover*), Bash(gh issue*)
---

# Fuzzing Test Skill (Go)

Generate high-signal Go fuzz tests only when targets are suitable.

## Quick Reference

| When you need to… | Jump to |
|---|---|
| Determine if a target is suitable for fuzzing | §Applicability Gate (run first, always) |
| Choose among multiple candidate targets | §Target Priority Gate + load `references/target-priority.md` |
| Write the fuzz harness | §Harness Templates |
| Handle a discovered crash | §Crash Documentation + load `references/crash-handling.md` |
| Set up CI integration | Load `references/ci-strategy.md` |
| Diagnose a slow / ineffective fuzz run | Load `references/advanced-tuning.md` |
| Avoid common fuzzing mistakes | Load `references/anti-examples.md` |

## Load References Selectively

When target suitability is ambiguous (borderline cases):
→ Load `references/applicability-checklist.md` for the full suitability decision tree with edge-case guidance.

When 3+ candidate targets need prioritization:
→ Load `references/target-priority.md` for the bug-finding-yield ranking criteria and tie-breaking rules.

When a fuzz run discovers a crash that needs documentation:
→ Load `references/crash-handling.md` for crash triage steps, corpus commit policy, and regression test patterns.

When the user requests CI integration for fuzz tests:
→ Load `references/ci-strategy.md` for GitHub Actions configuration, corpus caching, and time-budget settings.

When diagnosing an ineffective fuzz run, OOM, leaks, flaky failures, or performance issues:
→ Load `references/advanced-tuning.md` for seed quality analysis, skip-rate diagnosis, allocation profiling, and harness simplification patterns.

When you need to avoid or check for common fuzzing mistakes (trivial targets, missing oracle, bad seeds, OOM, global state, time-based assertions, dropped corpus):
→ Load `references/anti-examples.md` for 7 BAD/GOOD code patterns covering the most frequent harness mistakes.

## Applicability Gate (Must Run First)

Before writing any fuzz code, evaluate suitability. If the target fails this gate, the entire remaining workflow is skipped — output the verdict, suggest alternatives, and stop.

Mark each item `Pass` / `Fail`:

1. Target has meaningful input space (not trivial fixed-path logic).
2. Target can be driven by Go fuzz-supported parameter types.
3. Target has clear oracle/invariant:
   - no panic for any input
   - round-trip (`decode(encode(x)) == x`)
   - differential consistency
   - domain constraints/properties
4. Target is mostly deterministic/local (not dominated by DB/network/clock/global mutable state).
5. Target is fast enough for high-iteration fuzzing.

Hard stop:

- If item `2` or `3` fails:
  - output `Applicability Verdict: Not suitable for fuzzing`
  - list concrete failed checks with specific code references
  - suggest alternative strategy (unit/integration/property tests)
  - stop (do not write fuzz tests)

## Additional Gates

### Target Priority Gate

When multiple candidates exist, prioritize by bug-finding yield:

1. Parsers/decoders/protocol handlers
2. Serialization/deserialization round-trip paths
3. State transitions with strict invariants
4. Differential comparison candidates (new vs ref implementation)

If only low-yield targets exist, state that explicitly before writing broad fuzz suites.

### Risk and Cost Gate

Classify fuzz effort:

- `Low`: pure function, fast, local
- `Medium`: moderate CPU/memory, bounded guards needed
- `High`: expensive path, heavy allocations, strict budget required

Set budget policy per class:

- `Low`: local fuzz 30-60s
- `Medium`: local fuzz 15-45s + stricter input guards
- `High`: corpus-only in PR, fuzz run in scheduled/nightly jobs

### Execution Integrity Gate

Never claim fuzz commands ran unless actually executed.

If not run, output:
- `Not run in this environment`
- reason
- exact commands to run

## Output Contract

Always start with:

1. `Applicability Verdict`
2. `Why` (2-6 concrete bullets)
3. `Action`

Then:

- If unsuitable: stop.
- If suitable: implement fuzz tests and report execution status.

## Implementation Workflow (Only If Suitable)

1. Identify target and `Oracle/invariant`.
2. Select fuzz mode:
- parser robustness
- round-trip
- differential
- multi-parameter
3. Seed with `f.Add(...)` — mine real data, do NOT invent fake seeds:

   **Seed mining strategy (run these before writing f.Add calls):**
   ```
   a. Grep existing unit tests for real inputs:
      Grep for function calls to the fuzz target in *_test.go files
      → extract literal arguments as seeds

   b. Scan testdata/ directories:
      Glob for testdata/**/* and testdata/fuzz/**/*
      → use file contents as []byte seeds

   c. Scan fixtures/examples in the repo:
      Glob for fixtures/, examples/, samples/, *.golden
      → use as domain-representative seeds

   d. Extract from production-like config/data files:
      Read any .json, .yaml, .proto, .csv files that match the target's input type
      → use real payloads, not hallucinated ones
   ```

   **Seed categories (each f.Add should cover ≥3 of these):**
   - valid inputs (mined from tests/testdata above)
   - boundary values (empty, max-length, single-element)
   - malformed/known-bad inputs (truncated, corrupted headers)
   - structurally distinct cases (different branches/variants)
4. Implement `FuzzXxx` in `*_test.go`.
5. Add harness guards:
- add a **Size guard**
- bound max length/size
- skip impossible combos with `t.Skip`
- avoid external side effects
6. Run checks:
- corpus/regression: `go test -run=^FuzzXxx$ .`
- short fuzz: `go test -run=^$ -fuzz=^FuzzXxx$ -fuzztime=30s .`
7. If crash found and fixed:
- retain corpus under `testdata/fuzz/FuzzXxx/`
- add deterministic regression assertion if applicable

## Crash Handling (Mandatory)

When fuzz finds a failure:

1. Capture minimal reproducible command.
2. Keep crashing input in corpus path.
3. Record failure type:
- panic
- invariant violation
- timeout/resource blowup
4. Fix with minimal code change.
5. Re-run corpus regression and short fuzz run.
6. Report root cause + prevention guard.

Use format in `references/crash-handling.md`.

## CI Strategy

Use two-lane strategy (see `references/ci-strategy.md`):

- PR lane:
  - run corpus replay (`go test -run=^Fuzz`)
  - optional short fuzz only for low-cost targets
- Scheduled lane (nightly/periodic):
  - run bounded fuzz time per package
  - upload artifacts/crash corpus

## Minimal Templates

### Template A: Parser (`[]byte`)

```go
func FuzzParseXxx(f *testing.F) {
	f.Add([]byte{})
	f.Add([]byte{0x01, 0x00})

	f.Fuzz(func(t *testing.T, data []byte) {
		if len(data) > 1<<20 {
			t.Skip()
		}
		out, err := ParseXxx(data)
		if err != nil {
			return
		}
		if !isValid(out) {
			t.Fatalf("invalid parsed result: %+v", out)
		}
	})
}
```

### Template B: Round-Trip

```go
func FuzzRoundTripXxx(f *testing.F) {
	f.Add("seed", int32(1))

	f.Fuzz(func(t *testing.T, a string, b int32) {
		orig := Obj{A: a, B: b}
		enc, err := Encode(orig)
		if err != nil {
			t.Skip()
		}
		got, err := Decode(enc)
		if err != nil {
			t.Fatalf("decode(encode(x)) failed: %v", err)
		}
		if got != orig {
			t.Fatalf("round-trip mismatch: got=%+v want=%+v", got, orig)
		}
	})
}
```

### Template C: Differential

```go
func FuzzDiffXxx(f *testing.F) {
	f.Add("hello,world", ",")

	f.Fuzz(func(t *testing.T, s, sep string) {
		if sep == "" {
			t.Skip()
		}
		got := ImplNew(s, sep)
		want := ImplRef(s, sep)
		if !equal(got, want) {
			t.Fatalf("diff mismatch: got=%v want=%v", got, want)
		}
	})
}
```

### Template D: Struct-Aware (Multi-Parameter with `[]byte` Deserialize)

Use when the target needs a complex struct that exceeds Go's native fuzz parameter types. Feed `[]byte` and deserialize into the struct inside the harness:

```go
func FuzzProcessRequest(f *testing.F) {
	// seed with known-good serialized inputs
	seed1, _ := json.Marshal(Request{Method: "GET", Path: "/api/v1/users", Body: ""})
	seed2, _ := json.Marshal(Request{Method: "POST", Path: "/api/v1/users", Body: `{"name":"x"}`})
	f.Add(seed1)
	f.Add(seed2)

	f.Fuzz(func(t *testing.T, data []byte) {
		if len(data) > 4096 {
			t.Skip()
		}
		var req Request
		if err := json.Unmarshal(data, &req); err != nil {
			t.Skip() // invalid structure, not interesting
		}
		// now fuzz with a well-typed struct
		resp, err := ProcessRequest(req)
		if err != nil {
			return // expected error path
		}
		if resp.StatusCode < 100 || resp.StatusCode > 599 {
			t.Fatalf("invalid status code: %d", resp.StatusCode)
		}
	})
}
```

Key points:
- `t.Skip()` on unmarshal failure to let the fuzzer focus on structurally valid inputs.
- Seed with multiple structurally distinct valid inputs to help coverage-guided exploration.
- Bound `len(data)` to avoid spending time on enormous payloads.

**Deserialization strategy (choose by performance need):**

| Method | Speed | When to use |
|--------|-------|-------------|
| `json.Unmarshal` | Slow (~10-50 μs/op) | Quick prototyping, human-readable seeds, low-iteration targets |
| `encoding/gob` | Medium (~2-10 μs/op) | Better throughput when seed readability is not needed |
| `encoding/binary.Read` | Fast (~0.1-1 μs/op) | Performance-sensitive targets needing max `execs/sec` |
| `go-fuzz-headers` `GenerateStruct` | Fast + structured | Complex structs with nested fields; see [go-fuzz-headers bridge](#go-fuzz-headers-bridge) below |

For high-iteration fuzzing (targets <1 μs/call), prefer `encoding/binary` or `go-fuzz-headers` over JSON — the deserialization overhead can dominate total execution time and reduce bug-finding yield.

## Fuzz vs Property-Based Testing

- **Use fuzz** when: inputs are byte/string-like, you want crash discovery, or target is a parser/decoder.
- **Use property-based** (`rapid`/`gopter`) when: inputs need complex generators with domain constraints, or `t.Skip`-based filtering would waste >80% of iterations.
- **Use both** when: fuzz for crash discovery + property-based for domain invariants on the same target.

## Corpus Management

- **Always commit** crashing inputs under `testdata/fuzz/FuzzXxx/` — these are regression tests.
- **Do not commit** the Go fuzz cache (`$GOCACHE/fuzz/`) — it's large and machine-specific.
- **Selectively commit** high-value seed inputs that cover distinct code paths. Avoid committing hundreds of auto-generated entries.
- Clean cache: `go clean -fuzzcache`

## Go Version Gate

Check `go.mod` before generating native fuzz code:

| Go version | Guidance |
|------------|----------|
| `1.18` | Native `testing.F` is available. Baseline for this skill. |
| `1.20` | Prefer current corpus layout and CI patterns. |
| `1.21` | Re-check package performance and memory budgets before extending fuzz time. |
| `1.22` | Be explicit about loop variable semantics when adapting older code examples. |

If Go < 1.18, native fuzzing is unavailable — stop and recommend property tests or legacy `go-fuzz` only with explicit justification.

### Race Detection + Fuzz

When the target touches goroutines, shared caches, or normalization pipelines with internal concurrency:

- run corpus replay with `go test -race -run=^FuzzXxx$ .`
- if runtime is acceptable, run a short fuzz burst with `-race`
- document when `-race` is skipped because the package is too slow for a bounded fuzz window

### Fuzz Worker Parallelism

Tune concurrency deliberately:

- cap `GOMAXPROCS` when CPU saturation hides determinism issues
- use `-parallel` carefully; higher worker counts can reduce `execs/sec` on allocation-heavy targets
- if a target is memory-heavy, lower worker count before increasing fuzz time

### go-fuzz-headers bridge

For complex binary or protocol-heavy inputs, `go-fuzz-headers` can bootstrap structured data from bytes:

```go
consumer := fuzz.NewConsumer(data)
var req Request
if err := consumer.GenerateStruct(&req); err != nil {
	t.Skip()
}
```

Use `GenerateStruct` only when native fuzz parameter types are too limiting and the target still has a strong oracle.

### Fuzz Performance Baseline

Record a baseline before scaling up:

- approximate `execs/sec`
- average allocation profile if known
- skip rate estimate
- time budget used for the measurement

If `execs/sec` is too low for meaningful exploration, simplify the harness before asking for longer fuzz windows.

## Quality Scorecard

After generating fuzz tests, evaluate quality. Mark each item `Pass` / `Fail`.

### Critical (all must pass for overall PASS)

| # | Check | Criteria |
|---|-------|----------|
| C1 | Applicability gate ran | Verdict documented before any code |
| C2 | Oracle/invariant present | Every `f.Fuzz` body has at least one `t.Fatal`/`t.Errorf` asserting a property |
| C3 | Size guard present | `len(data) > N` or equivalent bound in every `[]byte`/`string` harness |

### Standard (≥4/5 must pass)

| # | Check | Criteria |
|---|-------|----------|
| S1 | Seed quality | `f.Add(...)` includes ≥3 structurally distinct valid inputs |
| S2 | Fuzz mode matches target | Parser → robustness, codec → round-trip, migration → differential |
| S3 | Skip rate bounded | `t.Skip()` usage justified; estimated skip rate <50% |
| S4 | Harness isolation | No network/DB/clock/global-state dependency in harness body |
| S5 | Corpus policy stated | Where to commit, what to exclude, cache strategy |

### Hygiene (≥3/4 must pass)

| # | Check | Criteria |
|---|-------|----------|
| H1 | Naming convention | `FuzzXxx` matches target name, file is `*_test.go` |
| H2 | Cost class assigned | Low/Medium/High with matching `-fuzztime` budget |
| H3 | t.Cleanup for resources | Fuzz target that opens resources uses `t.Cleanup` |
| H4 | Quick commands provided | Exact `go test` commands for corpus replay + short fuzz |

Scoring:
- **PASS**: All Critical pass AND ≥4/5 Standard AND ≥3/4 Hygiene
- **FAIL**: Any Critical fails → overall FAIL regardless of other scores

## Guardrails

- Do not fuzz targets requiring live DB/network unless fully stubbed.
- Do not use flaky assertions tied to time/random/global state.
- Do not generate fuzz code when applicability gate fails.
- Keep memory/time bounded in harness.
- Do not commit fuzz cache (`$GOCACHE/fuzz/`) to git — only commit `testdata/fuzz/`.
- If skip rate exceeds 50%, re-evaluate seed strategy before continuing.

## Quick Commands

- One target fuzz: `go test -run=^$ -fuzz=^FuzzXxx$ -fuzztime=30s .`
- All fuzz targets in package: `go test -run=^$ -fuzz=^Fuzz -fuzztime=1m .`
- Corpus replay only: `go test -run=^FuzzXxx$ .`
- Clean fuzz cache: `go clean -fuzzcache`

## Skill Maintenance

Run regression checks for this skill with:

```bash
bash "<path-to-skill>/scripts/run_regression.sh"
```
