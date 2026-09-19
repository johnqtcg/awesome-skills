# Benchmark Anti-Patterns

Extended catalog of benchmark mistakes. The three core patterns are in SKILL.md; these cover edge cases.

> **On Go ≥ 1.24, AP-1 and AP-2 both disappear if you use `for b.Loop()`** — it starts the
> timer itself and keeps the body alive, so there is no ResetTimer to misplace and no sink to
> forget. The classic-loop fixes below still apply on older toolchains and to sub-nanosecond
> benchmarks (see `benchmark-patterns.md` §Choosing the Loop Form).

## AP-1: Silently ignoring an error return

Note the real reason to handle the error — it is **not** about dead-code elimination. A store
to `sinkBytes` is observable, so the call already cannot be elided by sinking one value.

```go
// BAD: an error every iteration means you are benchmarking the cheap failure path,
// and the result looks impressively fast for the wrong reason.
var sinkBytes []byte
func BenchmarkMarshal(b *testing.B) {
    for b.Loop() {
        sinkBytes, _ = json.Marshal(input) // input may be unmarshalable; nobody checks
    }
}

// GOOD: fail loudly, so a broken benchmark cannot masquerade as a fast one
var sinkBytes []byte
func BenchmarkMarshal(b *testing.B) {
    for b.Loop() {
        out, err := json.Marshal(input)
        if err != nil {
            b.Fatal(err)
        }
        sinkBytes = out
    }
}
```

## AP-2: b.ResetTimer inside the loop

```go
// BAD: resets the timer on EVERY iteration; destroys the measurement
func BenchmarkWrong(b *testing.B) {
    for i := 0; i < b.N; i++ {
        b.ResetTimer() // inside loop!
        result = doWork()
    }
}

// GOOD (Go >= 1.24): b.Loop handles the timer; the mistake becomes unexpressible
func BenchmarkRight(b *testing.B) {
    setup()
    for b.Loop() {
        doWork()
    }
}

// GOOD (classic): ResetTimer once, before the loop
func BenchmarkRightClassic(b *testing.B) {
    setup()
    b.ResetTimer()
    for i := 0; i < b.N; i++ {
        result = doWork()
    }
}
```

## AP-3: Using b.N to index into a pre-generated data slice

**The modulo is not the problem.** This entry used to say the defect was "introduces modulo
operation in hot loop". Measured on go1.26.1 darwin/arm64 (Apple M4), 5 runs each, a
`//go:noinline` callee over a 1000-element slice:

| Loop | ns/op (5 runs) |
|---|---|
| `search(data[i%len(data)])` | 0.81, 0.81, 1.03, 1.18, 1.52 |
| `search(input)` — single input | 0.80, 1.16, 1.22, 1.32, 1.60 |

<!-- measured: go1.26.1 darwin/arm64, Apple M4, 2026-09-18 -->

The two ranges overlap almost completely; the difference is below the run-to-run noise this
document tells you to distrust in AP-7. Citing a cost you have not measured is the mistake
this skill exists to prevent, so the real reasons are below.

**What actually goes wrong**, and it is about *what you are measuring*, not arithmetic:

1. **The working set changes.** Sweeping 1000 inputs touches ~1000 cache lines; a single
   input stays in L1. Those are two different questions, and neither is "wrong" — but the
   numbers are not comparable, and a reader assumes they are.
2. **The result depends on `b.N`.** With a data-dependent cost (search depth, branch
   predictability), which elements get visited changes with the iteration count the harness
   picks, so `-benchtime` changes the answer. That breaks `benchstat` comparisons between
   runs that landed on different `b.N`.

```go
// AMBIGUOUS: measures "search over a 1000-element working set", but reads like
// "measures search". State which one you meant.
func BenchmarkSearch(b *testing.B) {
    data := generateData(1000)
    b.ResetTimer()
    for i := 0; i < b.N; i++ {
        sinkResult = search(data[i%len(data)])
    }
}

// GOOD: say it with sub-benchmarks, so both questions are answered and labelled.
func BenchmarkSearchByScenario(b *testing.B) {
    data := generateData(1000)
    b.Run("hot-single-input", func(b *testing.B) {
        in := data[0]
        for b.Loop() {
            sinkResult = search(in)
        }
    })
    b.Run("sweep-1000", func(b *testing.B) {
        i := 0
        for b.Loop() {
            sinkResult = search(data[i%len(data)])
            i++
        }
    })
}
```

Note the sweep keeps its own counter rather than reusing the loop index: `b.Loop()` exposes
none, and reaching for `b.N` inside a `b.Loop()` body is the bug this entry started as.

## AP-4: Benchmarking test helpers inside benchmarks

```go
// BAD: requireNoError and similar test helpers add overhead
func BenchmarkCreate(b *testing.B) {
    b.ResetTimer()
    for i := 0; i < b.N; i++ {
        obj, err := createObject()
        require.NoError(b, err) // test framework overhead in hot loop
        sinkObj = obj
    }
}

// GOOD: check error once outside, or use b.Fatal only on non-zero iterations
func BenchmarkCreate(b *testing.B) {
    b.ResetTimer()
    for i := 0; i < b.N; i++ {
        obj, err := createObject()
        if err != nil {
            b.Fatal(err)
        }
        sinkObj = obj
    }
}
```

## AP-5: Disabling GC to "stabilise" allocation counts

This entry used to recommend the pattern below. It is wrong three times over, and it is kept
here as an anti-example because the advice circulates widely.

```go
// BAD: does not compile, and would not help if it did
import "runtime/debug"

func BenchmarkAllocSensitive(b *testing.B) {
    defer debug.SetGCPercent(debug.SetGCPercent(-1))() // ← compile error
    for b.Loop() {
        sinkResult = allocHeavyFunc()
    }
}
```

**1. It does not compile.** `debug.SetGCPercent` returns `int`, so the trailing `()` tries to
call an integer:

```
invalid operation: cannot call debug.SetGCPercent(debug.SetGCPercent(-1))
    (value of type int): int is not a function
```

`defer` needs a function call; `defer debug.SetGCPercent(debug.SetGCPercent(-1))` (no trailing
parens) is the valid form — the inner call disables GC now and returns the previous value, the
outer call is deferred and restores it.

**2. The premise does not hold for the usual case.** `allocs/op` and `B/op` come from the
runtime's *allocation* counters (`Mallocs`/`TotalAlloc` deltas). GC frees memory; it does not
allocate. For ordinary code, disabling it cannot make those counters more stable — they were
already stable. Measured on Go 1.26 darwin/arm64, same function, five runs each
(`scripts/gc_claim_check.sh`, experiment 1):

| | `B/op` | `allocs/op` | `ns/op` |
|---|---|---|---|
| GC on | 1024 | 1 | 92.0 – 97.7 |
| GC off | 1024 | 1 | 39.2 – 230.0 |

<!-- measured: go1.26.1 darwin/arm64, Apple M4, 2026-07-29 -->

The allocation figures are byte-identical. There was nothing to stabilise.

**But "GC cannot change the allocation count" is false in general**, and it is worth knowing
where. Anything whose caching is tied to the collector changes behaviour when you switch it
off. `sync.Pool` is the common case: [its contract](https://pkg.go.dev/sync#Pool) says "any
item stored in the Pool may be removed automatically at any time without notification", and in
practice entries are dropped at GC. Disable GC and the pool stops being drained, so `New` runs
far less often — the code performs genuinely fewer allocations. Experiment 2 of the same
script, counting `New` calls over **2000 iterations** (the script's `POOL_ITERS`):

| | `Pool.New` calls |
|---|---|
| GC on | 36, 30, 29 |
| GC off | 1, 1, 1 |

So the honest rule is narrower than "it changes nothing": for code with no GC-coupled cache,
allocation counts are GC-independent and disabling it buys you nothing; for code with one, it
buys you *different behaviour from production*, which is worse than nothing.

**3. It distorts the timing — in whichever direction it happens to.** With the collector off
the heap only grows, so later iterations pay page-fault and fresh-span costs earlier ones did
not, while also skipping all collection work. Experiment 1 above shows GC-off runs landing at
both 39 ns/op (much faster than the 92–98 baseline) and 230 ns/op (much slower) in the same
five-run set. Do not read that as "disabling GC is slower"; read it as **the workload is no
longer the one you meant to measure**, and its results are not comparable to anything.

Every number above is from `scripts/gc_claim_check.sh` at its current constants
(`POOL_ITERS=2000`, `garbSize = 64 << 10`), measured on go1.26.1 darwin/arm64 (Apple M4) on
2026-07-29. Run it on your machine and Go version rather than trusting these figures — the
direction is the point, the magnitudes are local.

The iteration count quoted here is pinned to the script's constant by
`test_templates_compile.py::GCClaimScriptTests::test_doc_iteration_count_matches_the_script`.
An earlier revision retuned the script from 3000 to 2000 iterations and left the prose saying
3000 while still asserting "every number above is from the script" — evidence that drifts from
the thing that produced it is worse than no evidence, because it still reads as verified.

**What to do instead:** leave GC alone. If you suspect GC *is* distorting a comparison, say so
with evidence — `GODEBUG=gctrace=1` shows collection frequency — and reduce the allocation
rate rather than switching off the mechanism that reveals it. Tuning `GOGC` for a benchmark
measures your `GOGC` setting, not your function.

## AP-6: Benchmarking mutex-protected state with b.RunParallel without proper per-goroutine setup

```go
// BAD: all goroutines share the same key — measures lock contention, not the function
func BenchmarkCacheSet(b *testing.B) {
    cache := NewCache(100)
    b.RunParallel(func(pb *testing.PB) {
        for pb.Next() {
            cache.Set("same-key", value) // contended key
        }
    })
}

// GOOD: use distinct keys per goroutine to measure throughput without artificial contention
func BenchmarkCacheSet(b *testing.B) {
    cache := NewCache(100)
    var n atomic.Int64
    b.RunParallel(func(pb *testing.PB) {
        id := n.Add(1)
        key := fmt.Sprintf("key-%d", id)
        for pb.Next() {
            cache.Set(key, value)
        }
    })
}
```

## AP-7: Interpreting noisy benchmarks as meaningful

Signals that a benchmark is too noisy to trust:
- `± > 5%` in benchstat output for any run
- Wildly different results between consecutive `go test -bench=.` runs
- `p > 0.05` (not statistically significant) — conclusion is unreliable

Fixes:
- `go test -bench=. -benchtime=2s` — longer measurement window
- `go test -bench=. -count=20` — more samples for benchstat
- Ensure no background processes (compilation, Docker) during measurement
- Pin CPU frequency on Linux: `sudo cpupower frequency-set -g performance`

## AP-8: Using -benchmem flag but ignoring allocs/op

High `allocs/op` is often more actionable than high `ns/op`. A function may be fast in isolation but cause GC pressure under production load.

Rule of thumb:
- `0 allocs/op` for hot-path operations: ideal
- `1-2 allocs/op`: acceptable if objects are small and short-lived
- `> 5 allocs/op` in a tight loop: investigate with `-memprofile`