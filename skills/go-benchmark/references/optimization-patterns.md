# Optimization Patterns

Apply these patterns after profiling confirms the hotspot. Never pre-optimize without data.

## 1. sync.Pool for Short-Lived Allocations

Use when: `runtime.mallocgc` or `runtime.newobject` appears in CPU profile, object lifetime is bounded by a single request or call.

```go
var bufPool = sync.Pool{
    New: func() any { return &bytes.Buffer{} },
}

func process(data []byte) []byte {
    buf := bufPool.Get().(*bytes.Buffer)
    buf.Reset()        // always reset before use
    defer bufPool.Put(buf)

    buf.Write(data)
    // ... processing ...
    result := make([]byte, buf.Len())
    copy(result, buf.Bytes())
    return result
}
```

**Benchmark check:** `-alloc_objects` should drop dramatically. If it doesn't, the pool isn't being hit (check Reset and Put paths).

**Caution:** pool objects may be collected by GC at any time; never store state that must survive across calls. Only effective when `New` is expensive.

---

## 2. Pre-Allocation (Slice and Map)

Use when: `runtime.growslice` or `runtime.mapassign` appears in the profile.

```go
// BAD: grows repeatedly
func collect(items []Item) []string {
    var result []string
    for _, item := range items {
        result = append(result, item.Name)
    }
    return result
}

// GOOD: single allocation
func collect(items []Item) []string {
    result := make([]string, 0, len(items))
    for _, item := range items {
        result = append(result, item.Name)
    }
    return result
}
```

For maps: `make(map[K]V, expectedSize)` avoids bucket growth. Useful when the map will hold many entries.

---

## 3. Avoid Interface Boxing in Hot Paths

Use when: `runtime.convT` / `runtime.convTslice` / `runtime.convTstring` in profile.

```go
// BAD: boxes string into any on every call
func log(msg any) { /* ... */ }
log(item.Name) // allocates

// GOOD: use concrete type or a dedicated overload
func logString(msg string) { /* ... */ }
logString(item.Name) // no alloc
```

Similarly: `fmt.Sprintf` in hot paths boxes every argument. Replace with `strconv`:

```go
// BAD: fmt.Sprintf boxes n into any
s := fmt.Sprintf("count=%d", n)

// GOOD: no allocation
var buf [32]byte
s := string(strconv.AppendInt(buf[:0], int64(n), 10))
// or for simple appends:
b = strconv.AppendInt(b, int64(n), 10)
```

---

## 4. String ↔ []byte Conversion

Use when: `runtime.slicebytetostring` or `runtime.stringtoslicebyte` in profile.

```go
// BAD: allocates on every call
func process(b []byte) string {
    return string(b) // allocates new string
}

// GOOD (safe): unsafe.String avoids allocation; b must not be modified after
import "unsafe"
func process(b []byte) string {
    return unsafe.String(unsafe.SliceData(b), len(b))
}
```

Only use `unsafe.String` when the `[]byte` will not be mutated while the string is live.

---

## 5. Escape Analysis Fixes

Run: `go build -gcflags="-m" ./pkg/... 2>&1 | grep "escapes to heap"`

| Escape reason | Fix |
|--------------|-----|
| Assigned to `any`/interface | Pass concrete type; add typed overloads |
| Returned pointer (small struct) | Return value copy instead of pointer |
| Closure captures loop variable | Pass variable as parameter to closure |
| `fmt.Sprintf` arg | `strconv.Itoa`, `strconv.AppendInt`, `[]byte` builder |
| Slice appended to interface slice | Use typed slice |

---

## 6. Reducing Lock Contention

Use when: `sync.(*Mutex).Lock` prominent in CPU or mutex profile.

- **Narrow lock scope**: move expensive work outside the locked section
- **Read-heavy workloads**: upgrade `sync.Mutex` to `sync.RWMutex`
- **Hot counter**: use `sync/atomic.Int64` instead of mutex-guarded `int64`
- **Per-key sharding**: split a global map into N shards, each with its own lock

```go
// Shard example for high-contention cache
const numShards = 64

type ShardedCache struct {
    shards [numShards]struct {
        sync.RWMutex
        data map[string]any
    }
}

func (c *ShardedCache) shard(key string) int {
    h := fnv.New32a()
    h.Write([]byte(key))
    return int(h.Sum32()) % numShards
}
```