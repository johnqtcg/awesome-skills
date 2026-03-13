# Go Performance Patterns

Deep-dive reference for the **Performance (Medium)** category in SKILL.md step 5.

## Slice Pre-allocation

```go
// BAD: append grows backing array repeatedly (O(n) allocations)
var results []Item
for _, v := range input {
    results = append(results, transform(v))
}

// GOOD: pre-allocate with make + cap, use index assignment
results := make([]Item, len(input))
for i, v := range input {
    results[i] = transform(v)
}

// GOOD (alternative): pre-allocate cap, use append
results := make([]Item, 0, len(input))
for _, v := range input {
    results = append(results, transform(v))
}
```

Key points:
- Index assignment avoids append overhead and enables BCE (Bounds Check Elimination) by the compiler
- When final length is known, `make([]T, n)` + index is fastest
- When length is estimated, `make([]T, 0, cap)` + append is safer

## String Concatenation

```go
// BAD: += in loop — O(n²) allocations, ~1000x slower for large n
var s string
for _, item := range items {
    s += item.Name + ","
}

// GOOD: strings.Builder with Grow pre-allocation
var b strings.Builder
b.Grow(len(items) * avgLen) // pre-allocate buffer
for i, item := range items {
    if i > 0 {
        b.WriteByte(',')
    }
    b.WriteString(item.Name)
}
result := b.String()
```

Comparison:
- `strings.Builder`: best for building strings, zero-copy `String()` method
- `bytes.Buffer`: use when you need `io.Writer` interface or mixed byte/string ops
- `fmt.Sprintf`: fine for small, one-shot formatting; avoid in loops

## Map Performance Traps

### Pre-allocation

```go
// BAD: map grows and rehashes repeatedly
m := make(map[string]int)
for _, item := range largeSlice {
    m[item.Key] = item.Value
}

// GOOD: pre-allocate with size hint
m := make(map[string]int, len(largeSlice))
for _, item := range largeSlice {
    m[item.Key] = item.Value
}
```

### Map Memory Leak (delete does not shrink)

`delete(m, key)` removes the entry but does NOT release the underlying bucket memory.
A map that grew to 1M entries and was deleted down to 10 still holds memory for 1M.

```go
// BAD: long-lived map used as cache with unbounded growth
var cache = make(map[string]Result)
func Add(k string, v Result) { cache[k] = v }
func Remove(k string)        { delete(cache, k) } // buckets never freed

// GOOD: periodic re-creation to release memory
func compactCache() {
    newCache := make(map[string]Result, len(cache))
    for k, v := range cache {
        newCache[k] = v
    }
    cache = newCache // old map becomes GC-eligible
}
```

### Large Map GC Optimization

The Go GC scans map entries that contain pointers. For maps with >128-byte keys or values, the runtime stores them as pointers, increasing GC pressure.

```go
// BAD: map[string]*LargeStruct — GC scans every pointer
var m map[string]*LargeStruct

// BETTER: map[int]LargeStruct — if key is non-pointer and value < 128B
// Or use index-based approach:
type Store struct {
    items []LargeStruct
    index map[string]int // index stores int offsets, not pointers
}
```

## Struct Memory Alignment

Field ordering affects struct size due to padding:

```go
// BAD: 24 bytes (padding between fields)
type Bad struct {
    a bool   // 1 byte + 7 padding
    b int64  // 8 bytes
    c bool   // 1 byte + 7 padding
}

// GOOD: 16 bytes (fields sorted by descending alignment)
type Good struct {
    b int64  // 8 bytes
    a bool   // 1 byte
    c bool   // 1 byte + 6 padding
}
```

Tools:
- `fieldalignment` (from `golang.org/x/tools`): detects and auto-fixes suboptimal field ordering
- Run: `go vet -vettool=$(which fieldalignment) ./...`

### Empty Struct (`struct{}`) Uses

```go
// Set implementation (zero memory per element)
seen := make(map[string]struct{})
seen["key"] = struct{}{}

// Signal-only channel (zero-size element)
done := make(chan struct{})
close(done) // broadcast signal
```

## False Sharing

When goroutines frequently write to adjacent struct fields, they may share the same CPU cache line (64 bytes), causing performance degradation.

```go
// BAD: counters on same cache line
type Counters struct {
    reads  atomic.Int64
    writes atomic.Int64
}

// GOOD: pad to separate cache lines (only when profiling confirms contention)
type Counters struct {
    reads  atomic.Int64
    _      [56]byte // pad to 64-byte cache line
    writes atomic.Int64
}
```

When to care: only when profiling shows cache contention in high-throughput concurrent code. Do NOT add padding speculatively.

## Escape Analysis

Variables that "escape" to the heap incur allocation and GC cost. Common escape causes:

```go
// Escapes: returning pointer to local variable
func newUser(name string) *User {
    u := User{Name: name} // escapes to heap
    return &u
}

// Escapes: assigning to interface
func process(v interface{}) { ... }
func caller() {
    x := 42
    process(x) // x escapes (boxed into interface)
}

// Escapes: closure captures
func maker() func() int {
    x := 0
    return func() int { x++; return x } // x escapes
}
```

Reducing escapes:
- Pass structs by value when they are small (<= ~64 bytes)
- Accept interfaces, return concrete types (not pointers to interfaces)
- Use `go build -gcflags="-m"` to inspect escape decisions

## For-Range Performance

```go
type LargeStruct struct {
    Data [1024]byte
    // ...
}

// BAD: range copies entire struct on each iteration
for _, item := range largeItems {
    process(item) // item is a copy of LargeStruct
}

// GOOD: use index to avoid copy
for i := range largeItems {
    process(&largeItems[i])
}
```

Note: As of Go 1.22+, the compiler optimizes some range-value copies. Still prefer index access for very large structs (>256 bytes).

## Lock Optimization

### Shrink Critical Section

```go
// BAD: holding lock during I/O
mu.Lock()
data := cache[key]
result := fetchFromDB(data) // slow I/O under lock!
cache[key] = result
mu.Unlock()

// GOOD: minimize lock scope
mu.Lock()
data := cache[key]
mu.Unlock()

result := fetchFromDB(data) // I/O outside lock

mu.Lock()
cache[key] = result
mu.Unlock()
```

### Read-Write Separation

```go
// Use sync.RWMutex when reads >> writes
var mu sync.RWMutex

func Get(key string) Value {
    mu.RLock()         // multiple readers allowed
    defer mu.RUnlock()
    return cache[key]
}

func Set(key string, val Value) {
    mu.Lock()          // exclusive writer
    defer mu.Unlock()
    cache[key] = val
}
```

### Atomic vs Mutex

```go
// BAD: mutex for simple counter (high contention overhead)
var mu sync.Mutex
var count int64
mu.Lock()
count++
mu.Unlock()

// GOOD: atomic for simple numeric operations (~3x faster)
var count atomic.Int64
count.Add(1)
```

Use atomic for: counters, flags, simple load/store of single values.
Use mutex for: complex invariants spanning multiple fields.

### Sharded Locks

When a single mutex becomes a bottleneck:

```go
const shardCount = 16

type ShardedMap struct {
    shards [shardCount]struct {
        sync.RWMutex
        data map[string]Value
    }
}

func (m *ShardedMap) shard(key string) *struct {
    sync.RWMutex
    data map[string]Value
} {
    h := fnv32(key)
    return &m.shards[h%shardCount]
}
```

## Substring Memory Retention

A substring of a large string retains the entire original string in memory:

```go
// BAD: s holds reference to entire largeString (possibly MB)
s := largeString[:10]

// GOOD (Go 1.20+): strings.Clone creates independent copy
s := strings.Clone(largeString[:10])

// GOOD (pre-1.20): manual copy
s := string([]byte(largeString[:10]))
```

Watch for this pattern when:
- Extracting small parts from large strings (file contents, HTTP bodies)
- Storing substrings in long-lived caches or maps

## sync.Pool for Object Reuse

```go
// BAD: allocating a new bytes.Buffer on every request
func HandleRequest(w http.ResponseWriter, r *http.Request) {
    buf := new(bytes.Buffer) // allocation on every call
    buf.ReadFrom(r.Body)
    process(buf.Bytes())
}

// GOOD: reuse buffers via sync.Pool
var bufPool = sync.Pool{
    New: func() any {
        return new(bytes.Buffer)
    },
}

func HandleRequest(w http.ResponseWriter, r *http.Request) {
    buf := bufPool.Get().(*bytes.Buffer) // type assertion required
    defer func() {
        buf.Reset() // clear contents before returning to pool
        bufPool.Put(buf)
    }()
    buf.ReadFrom(r.Body)
    process(buf.Bytes())
}
```

Critical caveats:
- `sync.Pool` is only beneficial for **frequently allocated, short-lived objects** that are expensive to create or cause GC pressure
- Do NOT use for small or infrequently allocated objects — the pool bookkeeping overhead outweighs the savings
- Pooled objects may be collected by the GC at any time (no size guarantee); always handle the `New` path
- Always `Reset()` or zero the object before `Put()` to avoid leaking data between callers

## Buffered I/O

```go
// BAD: writing small chunks directly to file/conn — each Write is a syscall
func WriteLogs(f *os.File, entries []string) {
    for _, entry := range entries {
        f.WriteString(entry + "\n") // syscall per entry
    }
}

// GOOD: wrap with bufio.NewWriter — batches writes into fewer syscalls
func WriteLogs(f *os.File, entries []string) {
    bw := bufio.NewWriter(f)
    defer bw.Flush() // flush remaining buffered data on exit
    for _, entry := range entries {
        bw.WriteString(entry)
        bw.WriteByte('\n')
    }
}

// For custom buffer size (default is 4096):
bw := bufio.NewWriterSize(f, 64*1024) // 64KB buffer
```

Read-heavy path:

```go
// BAD: reading small chunks directly from conn
func ReadAll(conn net.Conn) ([]byte, error) {
    return io.ReadAll(conn) // many small reads
}

// GOOD: wrap with bufio.NewReader to reduce syscalls
func ReadAll(conn net.Conn) ([]byte, error) {
    br := bufio.NewReader(conn)
    return io.ReadAll(br)
}
```

Why it matters:
- Each unbuffered `Write`/`Read` on a file or socket triggers a syscall
- `bufio` coalesces many small operations into fewer, larger syscalls
- Typical improvement: 5–50x for workloads with many small writes

## JSON Encoding Performance

```go
// BAD: json.Marshal allocates intermediate []byte, then you write it
func HandleGet(w http.ResponseWriter, r *http.Request) {
    data, err := json.Marshal(response) // allocates []byte
    if err != nil {
        http.Error(w, err.Error(), 500)
        return
    }
    w.Header().Set("Content-Type", "application/json")
    w.Write(data) // second copy into ResponseWriter
}

// GOOD: stream directly to writer — avoids intermediate buffer
func HandleGet(w http.ResponseWriter, r *http.Request) {
    w.Header().Set("Content-Type", "application/json")
    if err := json.NewEncoder(w).Encode(response); err != nil {
        // NOTE: headers already sent; log the error
        log.Printf("json encode: %v", err)
    }
}
```

Decoding with strict validation:

```go
// GOOD: streaming decode with unknown-field rejection
func decodeBody(r *http.Request, dst any) error {
    dec := json.NewDecoder(r.Body)
    dec.DisallowUnknownFields() // reject unexpected keys
    return dec.Decode(dst)
}
```

Notes:
- `json.NewEncoder`/`json.NewDecoder` avoid the intermediate `[]byte` allocation of `Marshal`/`Unmarshal`
- `Encoder.Encode` appends a trailing newline — acceptable for HTTP, but be aware when writing to files
- For extreme performance needs, consider `encoding/json/v2` (experimental, Go team) or third-party encoders like `github.com/json-iterator/go`, `github.com/goccy/go-json`, or `github.com/bytedance/sonic`

## HTTP Transport Tuning

```go
// BAD: http.DefaultClient — no timeout, small connection pool, shared globally
resp, err := http.Get("https://api.internal/resource") // uses DefaultClient

// GOOD: purpose-built client with tuned transport
var internalClient = &http.Client{
    Timeout: 10 * time.Second, // overall request timeout (includes dial, TLS, body read)
    Transport: &http.Transport{
        MaxIdleConns:          100,              // total idle connections across all hosts
        MaxIdleConnsPerHost:   20,               // idle connections per host (default is only 2!)
        IdleConnTimeout:       90 * time.Second, // how long idle connections stay in pool
        TLSHandshakeTimeout:   5 * time.Second,
        ResponseHeaderTimeout: 5 * time.Second,  // time to wait for response headers
        ExpectContinueTimeout: 1 * time.Second,
    },
}

func callInternal(ctx context.Context, url string) (*http.Response, error) {
    req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
    if err != nil {
        return nil, err
    }
    return internalClient.Do(req)
}
```

Key points:
- `http.DefaultClient` has zero timeout — a hung server blocks the goroutine forever
- Default `MaxIdleConnsPerHost` is **2** — far too low for service-to-service communication, causing frequent connection re-establishment
- Always pass a `context.Context` to requests for cancellation and deadline propagation
- Create **one client per target service class** (internal API, external vendor, etc.) — do NOT create a new `http.Client` per request
- The `Transport` is safe for concurrent use and should be shared

## Regexp Compile-Once

```go
// BAD: compiling regexp on every call — compilation is expensive
func ValidateEmail(email string) bool {
    re := regexp.MustCompile(`^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$`)
    return re.MatchString(email)
}

// GOOD: compile once at package level, reuse everywhere
var emailRegexp = regexp.MustCompile(`^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$`)

func ValidateEmail(email string) bool {
    return emailRegexp.MatchString(email)
}
```

Why this matters:
- `regexp.Compile` / `regexp.MustCompile` parses the pattern and builds an internal state machine — this is **orders of magnitude** more expensive than matching
- The compiled `*regexp.Regexp` is safe for concurrent use by multiple goroutines
- `MustCompile` at package level panics at init time if the pattern is invalid — fail-fast on startup rather than at runtime
- If you find `regexp.Compile` inside a loop or a frequently-called function, hoist it to a package-level `var` — this is almost always a free performance win

## See Also

- `go-concurrency-patterns.md` — mutex vs atomic, lock correctness
- `go-api-http-checklist.md` — HTTP client lifecycle
- `go-database-patterns.md` — connection pool performance