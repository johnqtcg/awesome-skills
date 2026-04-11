# Benchmark Anti-Patterns

Extended catalog of benchmark mistakes. The three core patterns are in SKILL.md; these cover edge cases.

## AP-1: Forgetting to sink error values

```go
// BAD: only sinks first return; compiler may still elide the call
var sinkBytes []byte
func BenchmarkMarshal(b *testing.B) {
    b.ResetTimer()
    for i := 0; i < b.N; i++ {
        sinkBytes, _ = json.Marshal(input)
    }
}

// GOOD: sink both return values
var sinkBytes []byte
var sinkErr   error
func BenchmarkMarshal(b *testing.B) {
    b.ResetTimer()
    for i := 0; i < b.N; i++ {
        sinkBytes, sinkErr = json.Marshal(input)
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

// GOOD: ResetTimer once, before the loop
func BenchmarkRight(b *testing.B) {
    setup()
    b.ResetTimer()
    for i := 0; i < b.N; i++ {
        result = doWork()
    }
}
```

## AP-3: Using b.N to index into a pre-generated data slice

```go
// BAD: accesses data[i % len(data)]; introduces modulo operation in hot loop
func BenchmarkSearch(b *testing.B) {
    data := generateData(1000)
    b.ResetTimer()
    for i := 0; i < b.N; i++ {
        sinkResult = search(data[i%len(data)])
    }
}

// BETTER: use a single representative input or accept the small modulo overhead
// and note it in the benchmark comment
func BenchmarkSearch(b *testing.B) {
    input := generateData(1)[0] // single representative input
    b.ResetTimer()
    for i := 0; i < b.N; i++ {
        sinkResult = search(input)
    }
}
```

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

## AP-5: Not disabling GC for alloc-sensitive benchmarks

```go
// PATTERN: disable GC to get stable alloc counts when measuring allocations
import "runtime/debug"

func BenchmarkAllocSensitive(b *testing.B) {
    defer debug.SetGCPercent(debug.SetGCPercent(-1))() // disable GC; restore on exit
    b.ResetTimer()
    for i := 0; i < b.N; i++ {
        sinkResult = allocHeavyFunc()
    }
}
```

Only use when you need exact `allocs/op` counts. For throughput measurements, leave GC enabled.

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