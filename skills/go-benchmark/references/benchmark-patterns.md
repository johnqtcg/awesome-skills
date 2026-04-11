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

## Parallel Benchmarks

```go
func BenchmarkCacheGet(b *testing.B) {
    cache := NewCache(1000)
    populateCache(cache)
    b.ResetTimer()
    b.RunParallel(func(pb *testing.PB) {
        for pb.Next() {
            sinkAny, _ = cache.Get("key-42")
        }
    })
}
```

Control goroutine count: `go test -bench=BenchmarkCacheGet -benchmem -cpu=1,2,4,8`

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
