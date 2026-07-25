---
name: fuzzing-test
description: Generate Go fuzz tests (Go 1.18+ testing.F) for specified code when users ask for fuzzing/模糊测试/fuzz test generation, parser robustness, round-trip, or differential fuzzing. Always run an applicability gate first; if the target is not suitable, explain concrete reasons and stop without writing fuzz test code.
allowed-tools: Read, Write, Grep, Glob, Bash(go test*), Bash(go build*), Bash(go clean*), Bash(go tool cover*), Bash(gh issue*)
---

# Fuzzing Test Skill (Go)

Generate high-signal Go fuzz tests only when targets are suitable.

## Quick Reference — Load References Selectively

Read the section named below first; load the reference only when its trigger applies.

| When you need to… | Section | Load on demand |
|---|---|---|
| Decide if a target is suitable | §Applicability Gate (**run first, always**) | `applicability-checklist.md` — full decision tree, oracle forms, version gate, borderline cases |
| Choose among 3+ candidate targets | §Target Priority Gate | `target-priority.md` — bug-yield ranking and tie-breaks |
| Write the harness | §Minimal Templates | — |
| Handle a discovered crash | §Crash Handling | `crash-handling.md` — triage steps, corpus policy, report template |
| Set up CI | §CI Strategy | `ci-strategy.md` — Actions config, corpus caching, budgets |
| Diagnose a slow/ineffective run, OOM, leak, or flake | §Fuzz Performance Baseline | `advanced-tuning.md` — seed quality, skip-rate, allocation profiling |
| Avoid or check for common mistakes | §Quality Scorecard | `anti-examples.md` — 9 BAD/GOOD harness patterns |

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

Hard stop — items `1`, `2`, and `3` are each independently blocking:

| Failed item | Why it stops the workflow |
|---|---|
| `1` meaningful input space | Fuzzing adds nothing a table-driven unit test would not find |
| `2` fuzz-supported types | Go's fuzzer cannot drive the target at all |
| `3` clear oracle | No way to recognise a bug even when the input triggers it |

On any of those:
- output `Applicability Verdict: Not suitable for fuzzing`
- list concrete failed checks with specific code references
- suggest alternative strategy (unit/integration/property tests)
- stop (do not write fuzz tests)

Items `4` and `5` are **soft warnings**, never hard stops: proceed, flag the risk, and adjust
the cost class. Full decision tree in `references/applicability-checklist.md`.

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

Every template ships **placeholder seeds**, marked as such. They are structurally distinct
so each template already satisfies scorecard `S1` as written — but placeholders are not
real seeds. Replace them with inputs mined per §Seed mining strategy before shipping; keep
at least three structurally distinct cases when you do.

### Template A: Parser (`[]byte`)

```go
func FuzzParseXxx(f *testing.F) {
	// PLACEHOLDER SEEDS — replace with mined inputs (§Seed mining strategy).
	f.Add([]byte{})                             // boundary: empty
	f.Add([]byte{0x01, 0x00})                   // valid: minimal header
	f.Add([]byte{0x01, 0xff, 0xff, 0xff, 0xff}) // malformed: oversized length field

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
	// PLACEHOLDER SEEDS — replace with mined inputs (§Seed mining strategy).
	// Seeds must round-trip under the CORRECT implementation, so they stay inside
	// what the codec can represent. Invalid UTF-8 does NOT belong here: encoding/json
	// rewrites it to U+FFFD, so the seed fails on correct code (see the note below).
	f.Add("", int32(0))                            // boundary: zero values
	f.Add("seed", int32(1))                        // valid: typical
	f.Add("nul\x00 combining é \U0001F30D", int32(-1)) // valid but tricky: NUL, combining mark, astral rune

	f.Fuzz(func(t *testing.T, a string, b int32) {
		if len(a) > 1<<16 {
			t.Skip()
		}
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

Two round-trip traps that fail on **correct** code — both cost a debugging cycle:

- **Every seed must be representable by the codec.** Invalid UTF-8 under `encoding/json`
  becomes U+FFFD, so the seed fails before testing anything. Same for dropped sub-second
  precision or clamped integer width. Verify with `go test -run='^Fuzz' .`
- **If the codec normalizes, `got != orig` is the wrong oracle** — compare canonical forms,
  or assert idempotence on a second pass.

→ Load `references/anti-examples.md` (Mistakes 8-9) for both patterns with BAD/GOOD code.

### Template C: Differential

```go
func FuzzDiffXxx(f *testing.F) {
	// PLACEHOLDER SEEDS — replace with mined inputs (§Seed mining strategy).
	f.Add("hello,world", ",") // valid: typical
	f.Add("", ",")            // boundary: empty subject
	f.Add("a,,b", ",,")       // structurally distinct: empty field + multi-char separator

	f.Fuzz(func(t *testing.T, s, sep string) {
		if sep == "" || len(s) > 1<<16 {
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
	// PLACEHOLDER SEEDS — replace with mined inputs (§Seed mining strategy).
	seed1, _ := json.Marshal(Request{Method: "GET", Path: "/api/v1/users", Body: ""})
	seed2, _ := json.Marshal(Request{Method: "POST", Path: "/api/v1/users", Body: `{"name":"x"}`})
	seed3, _ := json.Marshal(Request{Method: "", Path: "", Body: ""}) // boundary: all-empty
	f.Add(seed1)
	f.Add(seed2)
	f.Add(seed3)

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

Go writes fuzz inputs to **two** locations. Conflating them is the most common
fuzz-workflow error:

| Input kind | Written to | Fate |
|---|---|---|
| Failing input | `<pkg>/testdata/fuzz/FuzzXxx/` — **only on failure** | Commit it; it becomes a regression test |
| Coverage-growing "interesting" input | `$GOCACHE/fuzz/<module>/<pkg>/FuzzXxx/` | Never committed; cache it in CI |

So a clean 30-minute run reporting `new interesting: 2000` adds **nothing** to
`testdata/fuzz` — those entries are in the build cache
(`find "$(go env GOCACHE)/fuzz" -type f | wc -l`). Note `<pkg>` is the tested package's own
directory, not the repo root.

- **Always commit** crashing inputs under `<pkg>/testdata/fuzz/FuzzXxx/` — these are regression tests.
- **Do not commit** the Go fuzz cache (`$GOCACHE/fuzz/`) — large and machine-specific.
- **Selectively commit** high-value seeds covering distinct code paths; not hundreds of auto-generated entries.
- Clean cache: `go clean -fuzzcache`

## Go Version Gate

**Gate on the toolchain that will actually run the tests — not on the `go` directive in `go.mod`.**
Run `go version` (and `go env GOTOOLCHAIN`); `testing.F` is a stdlib symbol, so the toolchain
decides whether it exists. A `go 1.16` module fuzzes fine under a modern toolchain.

| Effective toolchain (`go version`) | Guidance |
|---------------------|----------|
| `< 1.18` | **Hard stop.** No `testing.F`. Recommend property tests, or legacy `go-fuzz` with explicit justification. |
| `1.18` | Native `testing.F` available. Baseline for this skill. |
| `1.20` | Prefer current corpus layout and CI patterns. |
| `1.21` | Re-check package performance and memory budgets before extending fuzz time. |
| `1.22` | Per-iteration loop variables; be explicit about loop semantics when adapting older examples. |

A low `go` directive is a **note, not a stop**: it caps *language* features inside the
harness, nothing more.

→ Load `references/applicability-checklist.md` (§Go Version Gate) for the three-source check
and the `GOTOOLCHAIN` cases.

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
| C2 | Observable oracle present | Every `f.Fuzz` body has an oracle that can actually fail. See the two accepted forms below — do not grade this by searching for an API token |
| C3 | Size guard present | `len(data) > N` or equivalent bound in every `[]byte`/`string` harness |

**C2 is graded against the oracle declared at the gate, not the presence of a `t.Fatal` call.**
A **no-panic / robustness** harness needs no assertion — the runtime already fails on panic;
just say so in a comment. A harness declaring **round-trip / differential / domain
constraint** must assert it explicitly. What C2 rejects is the *mismatch*: declaring an
invariant and then dropping the result.

→ Load `references/applicability-checklist.md` (§Oracle Forms) for the full pass/fail table.

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

- One target fuzz: `go test -run='^$' -fuzz='^FuzzXxx$' -fuzztime=30s .`
- Replay committed corpus for **all** targets: `go test -run='^Fuzz' ./...`
- Replay one target's corpus: `go test -run='^FuzzXxx$' .`
- Where interesting corpus accumulates: `find "$(go env GOCACHE)/fuzz" -type f`
- Clean fuzz cache: `go clean -fuzzcache`

`-fuzz` must match **exactly one** target — `-fuzz='^Fuzz'` fails with
`will not fuzz, -fuzz matches more than one fuzz test` in any package with two or more
targets. Anchor it per target and loop in the shell to cover a package. `-run='^Fuzz'`
has no such restriction and is the correct way to replay every target's corpus at once.

## Skill Maintenance

Run regression checks for this skill with:

```bash
bash "<path-to-skill>/scripts/run_regression.sh"
```
