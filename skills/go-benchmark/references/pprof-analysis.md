# pprof Analysis Reference

Deep-dive for generating and interpreting pprof profiles. The `-alloc_objects` vs `-alloc_space` distinction and `sync.Pool` pattern are documented in SKILL.md. Load this file when interpreting flame graphs, using CLI commands, or diagnosing mutex/block contention.

---

## Profile Types

| Profile | Flag | Measures | Use When |
|---------|------|----------|----------|
| CPU | `-cpuprofile` | Where goroutines spend CPU time (~100 Hz sampling) | High `ns/op`, CPU-bound code |
| Memory | `-memprofile` | Heap allocations (cumulative) | High `allocs/op` or `B/op` |
| Mutex | `-mutexprofile` | Mutex contention wait time | Parallelism doesn't scale |
| Block | `-blockprofile` | Goroutine blocking (channels, mutexes, syscalls) | Goroutine stalls |

---

## Generating Profiles

```bash
# CPU only (use -run=^$ to skip unit tests)
go test -bench=BenchmarkEncode -benchmem -count=1 \
    -cpuprofile cpu-encode-before.prof -run=^$ ./pkg/...

# Memory only
go test -bench=BenchmarkEncode -benchmem -count=1 \
    -memprofile mem-encode-before.prof -run=^$ ./pkg/...

# Both at once
go test -bench=BenchmarkEncode -benchmem -count=1 \
    -cpuprofile cpu-encode-before.prof -memprofile mem-encode-before.prof -run=^$ ./pkg/...

# Differential: capture before and after separately
go test -bench=. -count=1 -memprofile mem-before-pool.prof -run=^$ ./...
# ... apply optimization ...
go test -bench=. -count=1 -memprofile mem-after-pool.prof -run=^$ ./...
go tool pprof -http=:6060 -alloc_objects -diff_base mem-before-pool.prof mem-after-pool.prof
```

In the diff view: **red** = regression, **green** = improvement, **gray** = unchanged.

---

## Web UI Tabs

```bash
go tool pprof -http=:6060 cpu-encode-before.prof
```

| Tab | Best for |
|-----|----------|
| **Top** | Quick overview; sort by `flat` for self-cost, `cum` for call chains |
| **Flame Graph** | Call stack visualization; find wide boxes |
| **Graph** | Directed call graph with edge weights |
| **Source** | Per-line sample counts (`list FuncName`) |

---

## CLI Commands

```bash
go tool pprof mem-encode-before.prof
(pprof) top          # Top 10 by self (flat) cost
(pprof) top -cum     # Top 10 by cumulative cost (includes callees)
(pprof) top20
(pprof) list FuncName   # Per-line annotation (regex)
(pprof) weblist FuncName
(pprof) disasm FuncName # Assembly with sample annotations
```

**Reading `top` output:**
- `flat` = samples where this function was on top of the stack (self-cost)
- `cum` = samples where this function was anywhere in the stack
- High `cum`, low `flat` → bottleneck is in callees, not this function itself

---

## Reading Flame Graphs

- **X-axis** = sample count proportion. Wider = more time. Not wall-clock order.
- **Y-axis** = call depth. Bottom = entry point. Top = leaf functions.
- **Wide plateau** (wide box, narrow children) = this function itself is the hotspot.
- **Tall tower** = deep call chain; look for the widest box in the tower.

**Signals to look for:**
- `runtime.mallocgc` prominent in CPU profile → allocation pressure causing CPU overhead
- `runtime.gcBgMarkWorker` consuming samples → reduce allocations
- `runtime.chanrecv` / `runtime.chansend` → channel contention
- `sync.(*Mutex).Lock` → lock contention (also check mutex profile)

---

## Alloc Hotspot Patterns

Open with `-alloc_objects` (see SKILL.md), then in **Source** tab use `list FuncName`.

| Signature in pprof | Fix |
|-------------------|-----|
| `runtime.makeslice` inside loop | Pre-allocate outside loop or use `sync.Pool` (see SKILL.md) |
| `runtime.slicebytetostring` | Avoid `string([]byte)`; use `unsafe.String` if safe |
| `runtime.convT` / `runtime.convTslice` | Avoid `any` boxing in hot path |
| `fmt.(*pp).doPrintf` | Replace `fmt.Sprintf` with `strconv` or pre-formatted strings |
| `runtime.growslice` | Pre-size: `make([]T, 0, expectedCap)` |

---

## Escape Analysis

Predict which allocations will appear before profiling:

```bash
go build -gcflags="-m" ./pkg/... 2>&1 | grep "escapes to heap"
go build -gcflags="-m=2" ./pkg/... 2>&1   # verbose: shows reasoning
```

| Escape reason | Fix |
|--------------|-----|
| Assigned to interface | Pass concrete type directly |
| Returned pointer (small struct) | Return value, not pointer |
| Closure captures variable | Pass as parameter instead |
| `fmt.Sprintf` args | `strconv.Itoa(n)` or `strconv.AppendInt` |

---

## Heap Profile: the Four Views

A Go heap profile carries four sample types. `runtime/pprof` documents `-inuse_space` as the
default.

| Flag | Measures | Use for |
|---|---|---|
| `-alloc_objects` | allocation **count** since process start, including everything already freed | GC pressure — the churn rate |
| `-alloc_space` | allocated **bytes** since process start, including everything already freed | which call sites move the most bytes |
| `-inuse_objects` | objects **live** at the sample | retention: how many objects are still held |
| `-inuse_space` | bytes **live** at the sample | closest available answer to "how big is the heap" |

**`alloc_*` is a lifetime total, not a footprint.** Code that allocates and immediately discards
1 KB a million times reports roughly 1 GB of `alloc_space` while the live heap never exceeds a
few KB. Reading `alloc_space` as "memory used" is the single most common misreading of a Go heap
profile, and it sends you optimising churn when the complaint was residency (or vice versa).

**None of the four is RSS.** Resident set size also includes the runtime's own structures,
goroutine and OS thread stacks, spans that are free but not yet returned to the OS, and anything
allocated through cgo. A heap profile showing 300 MB live against 4 GB RSS is not a
contradiction and not necessarily a leak — see the OS for RSS (`ps`, `/proc/<pid>/status`).

Pick by the question being asked:

| Complaint | Flag |
|---|---|
| "GC runs constantly" / "it's slow" | `-alloc_objects` |
| "one call site allocates enormous buffers" | `-alloc_space` |
| "the process is too big" / "memory grows" | `-inuse_space` |

---

## Mutex & Block Profiling

**Under `go test` you do not enable these in code.** The testing package does it for you:
`-blockprofile` applies `-test.blockprofilerate` (default 1) via `runtime.SetBlockProfileRate`,
and `-mutexprofile` applies `-test.mutexprofilefraction` (default 1) via
`runtime.SetMutexProfileFraction` — see `src/testing/testing.go`, where both are set before the
run starts. Adding an `init()` duplicates that and hides the rate you are actually sampling at.

```bash
go test -bench=BenchmarkCacheGet -benchmem -count=1 -run=^$ \
    -mutexprofile mutex-cacheget-before.prof \
    -blockprofile block-cacheget-before.prof ./...

go tool pprof -http=:6060 mutex-cacheget-before.prof   # time spent waiting for locks
go tool pprof -http=:6060 block-cacheget-before.prof   # where goroutines block
```

Change the rate with the flags, not with code:

```bash
# sample 1 blocking event in 100 — cheaper on a very hot path
go test -bench=. -benchmem -run=^$ -blockprofile block-cacheget-sampled.prof -blockprofilerate=100 ./...
```

**An `init()` *is* the right tool for a long-running service**, which has no `go test` flags to
set the rate for it:

```go
// in a service binary, not a test
func init() {
    runtime.SetMutexProfileFraction(1) // 1 = capture every contention event
    runtime.SetBlockProfileRate(1)     // 1 = capture every blocking event, in ns
}
```

Both carry runtime cost at rate 1; in production sample far more sparsely.

- High `flat` on a specific `Lock` call → that lock is contended → reduce scope, use `sync.RWMutex`, or shard data
- `runtime.chanrecv` / `runtime.chansend` in block profile → channel is a bottleneck
- `time.Sleep` → expected; filter out
