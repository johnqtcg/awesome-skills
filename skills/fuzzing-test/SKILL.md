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

Hard stop — items `1`, `2`, and `3` are each independently blocking: without a meaningful
input space fuzzing finds nothing a table test would not; without fuzz-supported types the
fuzzer cannot drive the target; without an oracle a bug cannot be recognised when the input
triggers it. On any of those:
- output `Applicability Verdict: Not suitable for fuzzing`
- list concrete failed checks with specific code references
- suggest alternative strategy (unit/integration/property tests)
- stop (do not write fuzz tests)

Items `4` and `5` are **soft warnings**, never hard stops: proceed, flag the risk, and adjust
the cost class. Full decision tree in `references/applicability-checklist.md`.

**Soft warning ≠ fuzz the live dependency.** Item `4` grades *determinism*; the Guardrails
rule ("do not fuzz targets requiring live DB/network") grades *what the harness body does*.
They resolve in one order, and this is the binding statement — a reference file that reads
otherwise is stale:

| Situation | Verdict |
|---|---|
| Harness body would touch a live DB/network/clock | **Not a gate failure — a scope decision.** Stub or extract the pure layer, then fuzz that. If neither is possible, stop and say so |
| Dependency is stubbed/injected, results still vary | Soft warning: proceed, flag non-determinism, raise the cost class |
| Target merely *reads* injected config/state deterministically | No warning |

## Additional Gates

### Target Priority Gate

With multiple candidates, fuzz in yield order: parsers/decoders/protocol handlers →
serialization round-trip paths → state transitions with strict invariants → differential
candidates. If only low-yield targets exist, say so before writing broad fuzz suites.
Tiers, examples, and tie-breaks: `references/target-priority.md`.

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
3. Seed with `f.Add(...)` — mine real data, do NOT invent fake seeds. Run all four before
   writing any `f.Add`:

   | Source | How |
   |---|---|
   | Existing unit tests | Grep `*_test.go` for calls to the target; lift the literal arguments |
   | `testdata/` | Glob `testdata/**/*` and `testdata/fuzz/**/*`; file contents become `[]byte` seeds |
   | Repo fixtures | `fixtures/`, `examples/`, `samples/`, `*.golden` — domain-representative inputs |
   | Production-like data | `.json`/`.yaml`/`.proto`/`.csv` matching the target's input type |

   **Seed categories (cover ≥3 of these across the `f.Add` set):**
   - valid inputs (mined above)
   - boundary values (empty, max-length, single-element)
   - malformed/known-bad inputs (truncated, corrupted headers)
   - structurally distinct cases (different branches/variants)

   **If there is nothing to mine** — a new package, no tests, no testdata — do not skip the
   step and do not invent plausible-looking payloads. Construct seeds from the **declared
   contract**: the struct definition, the format spec, the switch arms of the parser. Label
   them `constructed (no corpus available)` in the report, keep them minimal, and verify
   every one with `go test -run='^Fuzz' .` before shipping. "Do not invent seeds" bans
   fabricating *data you claim is real*; deriving a seed from the type you are about to
   parse is the legitimate fallback.
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

When fuzz finds a failure: capture the minimal reproducer → keep the crashing input in
`<pkg>/testdata/fuzz/FuzzXxx/` → record the failure type (panic / invariant violation /
timeout-resource blowup) → fix with a minimal change → re-run corpus replay **and** a short
fuzz → report root cause and the guard that prevents recurrence.

A round-trip or differential failure can come from either side. Decide which **from the
contract**, not from confidence in the code (§Template B): the harness is wrong only when
the contract says the input is outside what the target must preserve. Keep the reproducer
either way, and never relax an assertion to restore green.

→ Report format in `references/crash-handling.md`.

## CI Strategy

Use two-lane strategy (see `references/ci-strategy.md`):

- PR lane:
  - run corpus replay (`go test -run=^Fuzz`)
  - optional short fuzz only for low-cost targets
- Scheduled lane (nightly/periodic):
  - run bounded fuzz time per package
  - upload artifacts/crash corpus

## Minimal Templates

Every template ships **placeholder seeds**, marked as such: three structurally distinct
cases including a valid one, so the template satisfies `S1`'s shape. They are still
placeholders — they say nothing about *your* target's breaking region, which is the half of
`S1` that finds bugs. Replace them per §Seed mining strategy, keep ≥3 structurally distinct
cases, and make sure one of them reaches the behaviour your oracle asserts.

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

A round-trip harness fails on **correct** code unless the *whole mutated input domain* —
not just the seeds — stays inside what the codec is contractually required to preserve.
Seeds are the easy half; the fuzzer generates the other half.

```go
func FuzzRoundTripXxx(f *testing.F) {
	// PLACEHOLDER SEEDS — replace with mined inputs (§Seed mining strategy).
	f.Add("", int32(0))                            // boundary: zero values
	f.Add("seed", int32(1))                        // valid: typical
	f.Add("nul\x00 combining é \U0001F30D", int32(-1)) // valid but tricky: NUL, combining mark, astral rune

	f.Fuzz(func(t *testing.T, a string, b int32) {
		if len(a) > 1<<16 {
			t.Skip()
		}
		// DOMAIN GUARD — mandatory, and specific to the codec under test.
		// Anything the codec may legitimately rewrite is NOT a counter-example, so it
		// must leave the assertion's domain. For encoding/json that is invalid UTF-8:
		// Marshal replaces it with U+FFFD, so without this guard the fuzzer reports a
		// round-trip mismatch within a second against a perfectly correct codec.
		if !utf8.ValidString(a) {
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

**Write the domain guard from the codec's contract, before the assertion.** Common ones:

| Codec behaviour | Guard that keeps the oracle honest |
|---|---|
| `encoding/json`: invalid UTF-8 → U+FFFD | `if !utf8.ValidString(s) { t.Skip() }` |
| Timestamp truncated to ms/s | round the input to the stored precision first |
| Integer clamped by the wire format | bound the input to the representable range |
| Unicode normalised (NFC), key order canonicalised | no guard expresses it — use the variant below |

**Variant — codec normalizes inside its representable domain.** When the rewrite cannot be
guarded away, drop strict equality and assert **value-level idempotence**: one normalization
pass is legitimate, drift after it is not.

```go
	got, err := Decode(enc) // pass 1
	if err != nil {
		t.Fatalf("decode(encode(x)) failed: %v", err)
	}
	enc2, err := Encode(got)
	if err != nil {
		t.Fatalf("re-encode failed: %v", err)
	}
	got2, err := Decode(enc2) // pass 2
	if err != nil {
		t.Fatalf("second decode failed: %v", err)
	}
	if got2 != got {
		t.Fatalf("round-trip not idempotent: %+v vs %+v", got2, got)
	}
```

Two caveats, both measured on Go 1.26.1 against an `encoding/json` codec:

- **Compare decoded values, never encoded bytes.** `bytes.Equal(enc, enc2)` fails on correct
  code — `Marshal` writes invalid input as the escape `\ufffd` but a genuine U+FFFD rune as
  its literal bytes, so the encodings differ while the values agree.
- **Idempotence is strictly weaker than guarded equality.** It forbids drift, not a one-shot
  wrong transform. Against a codec mutated to flip the sign of large integers, with the same
  seeds in both harnesses: guarded equality **caught** it, the idempotent variant **missed**
  it (the corrupted value re-encodes to itself, so pass 2 agrees with pass 1). Prefer the
  domain guard; fall back to idempotence only when no guard can express the contract.

**Verify the oracle before trusting it.** A round-trip harness is wrong in two directions,
and only the second command catches the first one:

```bash
go test -run='^FuzzRoundTripXxx$' -v .                        # seeds must pass, and RUN
go test -run='^$' -fuzz='^FuzzRoundTripXxx$' -fuzztime=10s .  # must stay clean
```

Use `-v` on the first one: a seed the domain guard skips prints `--- SKIP: FuzzXxx/seed#2`
and the package still reports `ok`. Such a seed is **dead weight** — it satisfies `S1`'s
count while exercising nothing. Replace it with one the guard admits.

When the second command fails, **triage against the contract — do not assume either side**.
"I believe the implementation is correct" is not evidence; finding bugs in code its author
believed correct is the entire point of fuzzing.

1. **Keep the reproducer first.** The failing input is in `<pkg>/testdata/fuzz/FuzzXxx/`.
   Do not delete it, and do not widen a guard or weaken an assertion to get back to green —
   that silences the finding instead of resolving it.
2. **Ask what the codec's documented contract says about this input.** Not what the code
   does — what it promises. (`encoding/json` documents the U+FFFD rewrite; a JSON number
   documents its precision limits.)
3. **Then classify, and say which rule decided it:**
   - contract says the input is outside what the codec must preserve → the **harness** is
     wrong: add the domain guard (or the canonical comparison) and note the contract clause;
   - contract says the value must survive → the **implementation** is wrong: report it, keep
     the input as a regression corpus entry;
   - contract is silent or ambiguous → **neither is settled**. Report it as an open
     question with the reproducer attached, and do not change the assertion to hide it.

Record the verdict and its basis in the crash report (`references/crash-handling.md`). A
harness fix with no cited contract clause is indistinguishable from suppressing a bug.

Converse: a harness that finds nothing against a target you know is broken may have a fine
oracle and **seeds that never reach the breaking region** — the sign-flip mutant above is
caught instantly by a seed of `int32(-1<<30)` and survives 25s from seeds of `0`, `1`, `-1`.
That is `S1` doing real work, not a formality.

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

| Method | Measured cost | When to use |
|--------|--------------|-------------|
| `encoding/binary.Read` | **57 ns/op**, 64 B, 2 allocs | Fixed-layout structs; highest `execs/sec` |
| `json.Unmarshal` | **441 ns/op**, 232 B, 5 allocs | Readable seeds, nested/optional fields |
| `encoding/gob` (`NewDecoder` per input) | **5 293 ns/op**, 7 216 B, 163 allocs | Rarely worth it in a harness — see below |
| `go-fuzz-headers` `GenerateStruct` | not measured here | Complex nested structs; see [go-fuzz-headers bridge](#go-fuzz-headers-bridge) |

Conditions: Go 1.26.1, darwin/arm64 (Apple M4), one 4-field struct (`uint8,int32,uint32,uint16`),
`-benchmem -count=3`. **These are one machine's numbers — the ordering is the transferable
part, and even that depends on your struct.** Re-measure before optimising:

```bash
go test -run='^$' -bench=. -benchmem -count=5 . | tee bench.txt && benchstat bench.txt
```

Why `gob` loses here: a harness gets a fresh `[]byte` per iteration, so it builds a new
`gob.Decoder` and re-reads the type descriptor every time — 163 allocations against JSON's 5.
`gob` is fast on a long-lived stream, which a harness never has.

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
(`find "$(go env GOCACHE)/fuzz" -type f | wc -l`). `<pkg>` is the tested package's own
directory, not the repo root. Clean with `go clean -fuzzcache`.

→ `references/ci-strategy.md` (§Corpus Sharing Between Lanes) owns the cache keys, the
artifact glob, and who commits a crasher.

## Go Version Gate

**Gate on the toolchain that will actually run the tests — not on the `go` directive in `go.mod`.**
Run `go version` (and `go env GOTOOLCHAIN`); `testing.F` is a stdlib symbol, so the toolchain
decides whether it exists. A `go 1.16` module fuzzes fine under a modern toolchain.

- **`go version` < 1.18 → hard stop.** No `testing.F`. Recommend property tests, or legacy
  `go-fuzz` with explicit justification.
- **≥ 1.18 → proceed.** Everything after 1.18 is a tuning detail, not a gate.
- A low `go` directive is a **note, not a stop**: it caps *language* features inside the
  harness, nothing more.

→ `references/applicability-checklist.md` (§Go Version Gate) for the three-source check and
the `GOTOOLCHAIN` cases; `references/advanced-tuning.md` (§Go Version Details) for
per-release behaviour worth knowing when tuning.

### Tuning: race, parallelism, structured input, baseline

Four knobs share one home — `references/advanced-tuning.md` — so the numbers stay in one
place: `-race` with fuzz (cost multiplier, when it is worth it, when to say you skipped it),
worker parallelism (`GOMAXPROCS`/`-parallel` for memory-heavy targets and CI runners),
`go-fuzz-headers` `GenerateStruct` for structs that native fuzz types cannot express, and the
`execs/sec` baseline table that decides whether a longer fuzz window is worth buying.

Record a baseline (`execs/sec`, skip rate, measurement window) before scaling up any budget.

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
| S1 | Seed quality | ≥3 structurally distinct `f.Add(...)` seeds, **at least one valid**, all passing on the correct implementation, and at least one reaching the region the oracle protects |
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
