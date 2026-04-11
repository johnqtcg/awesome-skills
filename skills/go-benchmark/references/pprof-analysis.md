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
    -cpuprofile cpu.prof -run=^$ ./pkg/...

# Memory only
go test -bench=BenchmarkEncode -benchmem -count=1 \
    -memprofile mem.prof -run=^$ ./pkg/...

# Both at once
go test -bench=BenchmarkEncode -benchmem -count=1 \
    -cpuprofile cpu.prof -memprofile mem.prof -run=^$ ./pkg/...

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
go tool pprof -http=:6060 cpu.prof
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
go tool pprof mem.prof
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

## Mutex & Block Profiling

Enable in code first:
```go
func init() {
    runtime.SetMutexProfileFraction(1) // capture all contention
    runtime.SetBlockProfileRate(1)      // capture all goroutine blocks
}
```

```bash
go test -bench=BenchmarkCacheGet -count=1 \
    -mutexprofile mutex.prof -blockprofile block.prof -run=^$ ./...

go tool pprof -http=:6060 mutex.prof   # where time is spent waiting for locks
go tool pprof -http=:6060 block.prof   # where goroutines block
```

- High `flat` on a specific `Lock` call → that lock is contended → reduce scope, use `sync.RWMutex`, or shard data
- `runtime.chanrecv` / `runtime.chansend` in block profile → channel is a bottleneck
- `time.Sleep` → expected; filter out
