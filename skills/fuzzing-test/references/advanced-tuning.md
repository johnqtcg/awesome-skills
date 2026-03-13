# Advanced Fuzz Tuning

Load this file only when diagnosing ineffective fuzz runs, debugging OOM/leak/flaky failures, or tuning fuzz performance.

## Coverage Feedback

### Evaluating Fuzz Effectiveness

After a fuzz run, check whether coverage is actually growing:

```bash
# run fuzz with coverage profile
go test -run=^$ -fuzz=^FuzzXxx$ -fuzztime=30s -coverprofile=fuzz_cover.out .

# inspect coverage
go tool cover -func=fuzz_cover.out | grep -E "total:|<target_package>"

# visualize uncovered paths
go tool cover -html=fuzz_cover.out -o fuzz_cover.html
```

### Signs of Ineffective Fuzzing

| Symptom | Likely Cause | Action |
|---------|-------------|--------|
| Coverage plateaus quickly (<60%) | Harness `t.Skip` rate too high or input guards too restrictive | Relax guards, add more structurally valid seeds |
| Coverage plateaus at high % but no bugs | Target is well-tested already | Increase fuzz budget or accept current coverage |
| Fuzz runs but only hits error-return paths | All seeds fail early validation | Add valid seed inputs via `f.Add(...)` |
| Very slow iterations (<100/sec) | Target is expensive per call | Add tighter size bounds, profile the target, consider `High` cost class |

### Skip Rate Monitoring

If `t.Skip()` fires on >50% of iterations, the fuzzer is wasting effort:

```go
// anti-pattern: overly broad skip
f.Fuzz(func(t *testing.T, data []byte) {
    var req ComplexStruct
    if err := json.Unmarshal(data, &req); err != nil {
        t.Skip() // ~95% of random bytes fail unmarshal
    }
    // ...
})

// better: seed heavily + use smaller input space
f.Add(validJSON1)
f.Add(validJSON2)
f.Add(validJSON3) // many structurally distinct seeds
```

## Troubleshooting

### Fuzz process OOM / killed

```go
// problem: unbounded allocation inside fuzz target
func FuzzDecode(f *testing.F) {
    f.Fuzz(func(t *testing.T, data []byte) {
        Decode(data) // may allocate huge buffers from crafted headers
    })
}

// fix: bound input size AND add allocation guard in production code
f.Fuzz(func(t *testing.T, data []byte) {
    if len(data) > 1<<16 { // 64KB max
        t.Skip()
    }
    Decode(data)
})
```

If OOM persists even with size bounds, the target may have amplification (e.g., decompression bomb). Add `runtime.MemStats` checks or fix the production code.

### Coverage not growing after initial burst

1. Check skip rate (see above).
2. Inspect uncovered branches with `-coverprofile` — are they behind input constraints the fuzzer can't reach?
3. Add targeted seed inputs that exercise uncovered paths.
4. If target has complex state setup, consider splitting into smaller fuzz targets per sub-function.

### Goroutine / resource leak under fuzz

Fuzz harness runs thousands of iterations in one process. Leaks accumulate:

```go
// problem: target opens resources not cleaned per iteration
f.Fuzz(func(t *testing.T, data []byte) {
    r := NewReader(data) // opens internal goroutine
    r.Parse()
    // r.Close() missing — goroutine leak × 10000 iterations
})

// fix: always close, use t.Cleanup
f.Fuzz(func(t *testing.T, data []byte) {
    r := NewReader(data)
    t.Cleanup(func() { r.Close() })
    r.Parse()
})
```

### Flaky fuzz failures

- Non-deterministic target (time, random, global state) → mock or skip.
- Map iteration order → use `sort` before comparison.
- Floating-point comparison → use epsilon tolerance.
- If flakiness persists, the target is not suitable for fuzzing (gate 4 failure).

## Go Version Details

| Go Version | Fuzzing Capabilities |
|-----------|---------------------|
| < 1.18 | No native fuzzing — use `go-fuzz` (dvyukov) or skip |
| 1.18+ | `testing.F` available, supported types: `[]byte`, `string`, `bool`, `int`/`uint` variants, `float32`/`float64` |
| 1.20+ | Improved corpus minimization, better coverage instrumentation |
| 1.21+ | Enhanced fuzz worker stability, reduced memory overhead |
| 1.22+ | Range function support in tests; fuzz cache improvements |

## Race Detection + Fuzz

```bash
# run fuzz with race detector — catches concurrent bugs
go test -run=^$ -fuzz=^FuzzXxx$ -fuzztime=30s -race .
```

Caveats:
- `-race` increases per-iteration cost ~2-10x — reduce `-fuzztime` accordingly.
- Race detector + fuzz is most valuable for targets that use goroutines internally.
- If the target is a pure function with no concurrency, `-race` adds cost with no benefit.

## Fuzz Worker Parallelism

```bash
# control fuzz worker count (defaults to GOMAXPROCS)
GOMAXPROCS=4 go test -run=^$ -fuzz=^FuzzXxx$ -fuzztime=60s -parallel=4 .
```

Guidelines:
- For CPU-bound targets: `GOMAXPROCS = num_cores` (default).
- For memory-heavy targets: reduce `-parallel` to avoid OOM.
- CI runners: set explicit `-parallel=2` to avoid starving other jobs.

## Structured Input with `go-fuzz-headers`

When `json.Unmarshal`-based struct generation has too high a skip rate, use `go-fuzz-headers` for deterministic structured consumption:

```go
import fuzz "github.com/AdaLogics/go-fuzz-headers"

func FuzzProcessOrder(f *testing.F) {
	f.Add([]byte{0x01, 0x02, 0x03, 0x04})

	f.Fuzz(func(t *testing.T, data []byte) {
		if len(data) > 4096 {
			t.Skip()
		}
		fc := fuzz.NewConsumer(data)
		var order Order
		if err := fc.GenerateStruct(&order); err != nil {
			t.Skip()
		}
		result, err := ProcessOrder(order)
		if err != nil {
			return
		}
		if result.Total < 0 {
			t.Fatalf("negative total: %v", result.Total)
		}
	})
}
```

Advantages over JSON unmarshal:
- Lower skip rate (bytes consumed deterministically, not parsed as JSON).
- Coverage-guided mutations directly affect struct fields.
- Works for structs with non-JSON-friendly fields (func, chan excluded).

## Fuzz Performance Baseline

Before investing in long fuzz runs, establish a baseline:

```bash
# measure per-iteration cost
go test -run=^$ -fuzz=^FuzzXxx$ -fuzztime=5s . 2>&1 | tail -1
# outputexample: "fuzz: elapsed: 5s, execs: 48231 (9646/sec), new interesting: 12 (total: 18)"
```

| Metric | Healthy | Concern | Action |
|--------|---------|---------|--------|
| execs/sec | >1000 | <100 | Profile target, add size bounds |
| new interesting | Growing | Plateaued at 0 | Check seeds, relax guards |
| total interesting | >10 in 30s | <5 | Target may have low branch diversity |
