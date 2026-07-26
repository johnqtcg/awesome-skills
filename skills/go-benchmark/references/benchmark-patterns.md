# Benchmark Patterns Reference

Deep-dive patterns for benchmark code. The sink pattern, basic templates, and benchstat workflow are documented in SKILL.md. Load this file when you need `b.*` API details, sub-benchmark shapes, per-iteration setup/teardown, or throughput reporting.

---

## b.* API Quick Reference

| Method | Purpose | Notes |
|--------|---------|-------|
| `b.N` | Loop iteration count | Use `for i := 0; i < b.N; i++` (all versions) or `for range b.N` (Go 1.24+) |
| `b.ResetTimer()` | Restart the clock | Call after one-time setup |
| `b.StopTimer()` | Pause timing | Use for per-iteration teardown |
| `b.StartTimer()` | Resume timing | Pair with StopTimer |
| `b.ReportAllocs()` | Enable alloc reporting | Same as `-benchmem` for this benchmark only |
| `b.SetBytes(n)` | Set bytes/op denominator | Enables MB/s reporting |
| `b.ReportMetric(v, unit)` | Add custom metric | e.g. `b.ReportMetric(float64(hits)/float64(total), "hit-rate")` |
| `b.Run(name, f)` | Sub-benchmark | Creates `BenchmarkXxx/name` in output |
| `b.RunParallel(f)` | Parallel benchmark | `f` receives `*testing.PB`; use `pb.Next()` as loop condition |
| `b.Cleanup(f)` | Register cleanup | Runs after benchmark, including sub-benchmarks |
| `b.Skip(...)` | Skip this benchmark | Useful for platform-specific benchmarks |
| `b.TempDir()` | Temp dir | Cleaned up automatically |

---

## Sub-Benchmarks

### Input size table (O(n) functions)
```go
func BenchmarkEncode(b *testing.B) {
    sizes := []struct {
        name string
        n    int
    }{
        {"64B", 64},
        {"1KB", 1024},
        {"64KB", 64 * 1024},
        {"1MB", 1024 * 1024},
    }
    for _, tc := range sizes {
        b.Run(tc.name, func(b *testing.B) {
            data := makeData(tc.n)
            b.SetBytes(int64(tc.n))
            b.ResetTimer()
            for i := 0; i < b.N; i++ {
                sinkBytes = Encode(data)
            }
        })
    }
}
```

### Comparing two implementations
```go
func BenchmarkConcat(b *testing.B) {
    input := strings.Repeat("x", 100)
    b.Run("plus-operator", func(b *testing.B) {
        b.ResetTimer()
        for i := 0; i < b.N; i++ {
            var s string
            for j := 0; j < 10; j++ { s += input }
            sinkString = s
        }
    })
    b.Run("strings-builder", func(b *testing.B) {
        b.ResetTimer()
        for i := 0; i < b.N; i++ {
            var sb strings.Builder
            sb.Grow(len(input) * 10)
            for j := 0; j < 10; j++ { sb.WriteString(input) }
            sinkString = sb.String()
        }
    })
}
```

---

## Choosing the Loop Form

On Go ≥ 1.24 `for b.Loop()` is the default: it starts the timer at the first call, stops it when
it returns false, and keeps the body from being optimised away — so neither `b.ResetTimer()` nor
a sink is needed. Two exceptions:

**1. Sub-nanosecond operations.** `b.Loop()` costs a real call per iteration. Measured on an
Apple M4, Go 1.26:

```
BenchmarkLoopEmpty-10       1.724 ns/op    ← empty for b.Loop() {}
BenchmarkClassicEmpty-10    0.2281 ns/op   ← empty for i := 0; i < b.N; i++ {}
```

Roughly 1.5 ns of harness per iteration. If the operation under test is in that range, the
harness dominates — use the classic loop and subtract a baseline:

```go
// Measure the harness itself, then subtract it from the real result.
func BenchmarkAddBaseline(b *testing.B) {
    for i := 0; i < b.N; i++ { // empty body, same loop shape
    }
}

var sinkInt int

func BenchmarkAdd(b *testing.B) {
    for i := 0; i < b.N; i++ {
        sinkInt = add(i, 3)
    }
}
```

Report `BenchmarkAdd − BenchmarkAddBaseline`. Why this matters concretely — the same cheap
function, three ways:

```
BenchmarkClassicEmpty-10      0.2281 ns/op   ← baseline
BenchmarkClassicDiscard-10    0.2258 ns/op   ← `_ = add(...)`: EQUAL to baseline, call eliminated
BenchmarkClassicSink-10       0.2882 ns/op   ← sink: above baseline, call survives
```

Without the baseline row, `0.2258` and `0.2882` look like the same measurement. The baseline is
what proves the discard version measured nothing.

**2. Inside `b.RunParallel`** — `b.Loop()` is not usable; `pb.Next()` is the loop condition.

---

## Multi-Return Sinks

A store to a package-level variable cannot be elided, so **one** sink is enough to keep a
multi-return call alive:

```go
var sinkBytes []byte

func BenchmarkMarshal(b *testing.B) {
    input := buildInput()
    for b.Loop() {
        sinkBytes, _ = json.Marshal(input) // sufficient: the store to sinkBytes is observable
    }
}
```

Sink the error too only when you want it inspected — e.g. to fail the benchmark on an
unexpected error, which is worth doing when a silent error path would make the benchmark
measure the cheap failure branch instead of the real work:

```go
func BenchmarkMarshal(b *testing.B) {
    input := buildInput()
    for b.Loop() {
        out, err := json.Marshal(input)
        if err != nil {
            b.Fatal(err) // otherwise you may be benchmarking the error return
        }
        sinkBytes = out
    }
}
```

Under `b.Loop()` no sink is required at all; keep one only if you also want the value inspected.

---

## Parallel Benchmarks

**The ordinary package-level sink becomes a data race here.** Inside `b.RunParallel`, the body
runs on N goroutines concurrently; `sinkAny, _ = cache.Get(...)` has every one of them writing
the same variable. `go test -race -bench=.` fails with `WARNING: DATA RACE`, so the benchmark
cannot be run under the race detector at all — and a racy benchmark is not a valid measurement.

Writing the shared variable *after* the loop does not fix it either: each goroutine still
performs that write.

```go
// BAD: shared sink written from every goroutine — fails under -race
func BenchmarkCacheGet(b *testing.B) {
    b.RunParallel(func(pb *testing.PB) {
        for pb.Next() {
            sinkAny, _ = cache.Get("key-42")
        }
    })
}

// GOOD: goroutine-local accumulation, single atomic publish per goroutine
var sinkTotal atomic.Int64

func BenchmarkCacheGet(b *testing.B) {
    cache := NewCache(1000)
    populateCache(cache)
    b.ResetTimer()
    b.RunParallel(func(pb *testing.PB) {
        var acc int // local: nothing shared while the timer runs
        for pb.Next() {
            v, _ := cache.Get("key-42")
            acc += len(v)
        }
        sinkTotal.Add(int64(acc))
    })
}

// GOOD (alternative): no accumulator, keep the last value alive
func BenchmarkCacheGetKeepAlive(b *testing.B) {
    cache := NewCache(1000)
    populateCache(cache)
    b.ResetTimer()
    b.RunParallel(func(pb *testing.PB) {
        var local any
        for pb.Next() {
            local, _ = cache.Get("key-42")
        }
        runtime.KeepAlive(local)
    })
}
```

Pick the accumulator when the result is cheap to reduce (length, sum, hash);
pick `runtime.KeepAlive` when the result is a struct or pointer you do not want to touch.

`b.Loop()` is **not** usable inside `RunParallel` — `pb.Next()` is the loop condition there.

Control goroutine count: `go test -bench=BenchmarkCacheGet -benchmem -cpu=1,2,4,8`

Always run parallel benchmarks under the race detector once:
`go test -race -bench=BenchmarkCacheGet -benchtime=100x -run='^$' .`
A benchmark that cannot survive `-race` is measuring undefined behaviour.

---

## Per-Iteration Setup/Teardown

Use `b.StopTimer` / `b.StartTimer` when you must reset state between iterations:

```go
func BenchmarkInsert(b *testing.B) {
    db := openTestDB(b)
    for i := 0; i < b.N; i++ {
        b.StopTimer()
        db.Exec("TRUNCATE t")
        b.StartTimer()
        sinkErr = db.Exec("INSERT INTO t VALUES (?)", generateRow())
    }
}
```

> `StopTimer/StartTimer` adds overhead itself. If per-iteration reset is cheap, prefer regenerating the value without stopping the timer.

---

## Throughput Benchmarks (b.SetBytes)

`b.SetBytes(n)` makes the framework report `MB/s`:

```go
func BenchmarkCompress(b *testing.B) {
    data := makePayload(64 * 1024)
    b.SetBytes(int64(len(data)))
    b.ResetTimer()
    for i := 0; i < b.N; i++ {
        sinkBytes, sinkErr = compress(data)
    }
}
```

Output: `BenchmarkCompress-8   2000   850000 ns/op   75.3 MB/s   65792 B/op   2 allocs/op`
