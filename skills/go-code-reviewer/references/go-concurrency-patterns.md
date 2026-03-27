# Go Concurrency Patterns

Deep-dive reference for the **Concurrency & Lifecycle (High)** category in SKILL.md step 5.

## Goroutine Leak

```go
// BAD: goroutine has no exit path
func startWorker() {
    go func() {
        for {
            doWork() // runs forever, no way to stop
        }
    }()
}

// GOOD: context-based cancellation
func startWorker(ctx context.Context) {
    go func() {
        for {
            select {
            case <-ctx.Done():
                return
            default:
                doWork()
            }
        }
    }()
}
```

Red flags:
- `go func()` without a cancellation signal (`ctx.Done()`, quit channel, `sync.WaitGroup`)
- Goroutine blocked on channel send/receive with no timeout or cancel
- No `WaitGroup.Wait()` or equivalent join before program/test exit

## Race Conditions on Shared State

```go
// BAD: concurrent map write (panic at runtime)
var cache = map[string]string{}
go func() { cache["a"] = "1" }()
go func() { cache["b"] = "2" }()

// GOOD: sync.Map for concurrent access
var cache sync.Map
go func() { cache.Store("a", "1") }()
go func() { cache.Store("b", "2") }()

// GOOD: mutex-protected map
var (
    mu    sync.RWMutex
    cache = map[string]string{}
)
func set(k, v string) {
    mu.Lock()
    defer mu.Unlock()
    cache[k] = v
}
```

Also check:
- Shared slice append without lock (slice header is 3 words, not atomic)
- Package-level `var` modified by multiple goroutines
- Struct fields accessed concurrently without synchronization

## Mutex Misuse

```go
// BAD: unlock not deferred (skipped on early return/panic)
mu.Lock()
if err := doWork(); err != nil {
    return err // mu never unlocked!
}
mu.Unlock()

// GOOD: defer unlock immediately
mu.Lock()
defer mu.Unlock()
if err := doWork(); err != nil {
    return err
}

// BAD: copying a mutex (silently creates independent lock)
type Cache struct {
    mu sync.Mutex
    m  map[string]string
}
c2 := c1 // c2.mu is a different lock — no protection!

// GOOD: use pointer receiver, never copy
func (c *Cache) Set(k, v string) {
    c.mu.Lock()
    defer c.mu.Unlock()
    c.m[k] = v
}
```

Additional checks:
- `RWMutex.RLock()` followed by write operation
- Lock ordering inconsistency (potential deadlock)
- Holding lock across I/O or network calls (blocks other goroutines)

## Channel Deadlock

```go
// BAD: unbuffered channel with no receiver
ch := make(chan int)
ch <- 1 // blocks forever

// BAD: range over channel never closed
ch := make(chan int, 10)
go func() {
    for i := 0; i < 10; i++ {
        ch <- i
    }
    // missing: close(ch)
}()
for v := range ch { // blocks forever after 10 items
    fmt.Println(v)
}

// GOOD: close channel when done sending
go func() {
    defer close(ch)
    for i := 0; i < 10; i++ {
        ch <- i
    }
}()
```

## Errgroup for Coordinated Goroutines

```go
// BAD: manual goroutine management, error lost
var wg sync.WaitGroup
for _, item := range items {
    wg.Add(1)
    go func(it Item) {
        defer wg.Done()
        if err := process(it); err != nil {
            log.Println(err) // error swallowed
        }
    }(item)
}
wg.Wait()

// GOOD: errgroup propagates first error and cancels remaining
g, ctx := errgroup.WithContext(ctx)
for _, item := range items {
    item := item // rebind for pre-Go 1.22 closure safety
    g.Go(func() error {
        return process(ctx, item)
    })
}
if err := g.Wait(); err != nil {
    return fmt.Errorf("processing failed: %w", err)
}
```

Note: `errgroup.SetLimit(n)` for bounded concurrency (Go 1.20+).

## Context Propagation

```go
// BAD: context not passed through
func handler(w http.ResponseWriter, r *http.Request) {
    result := fetchData() // no ctx — can't cancel, no timeout
}

// GOOD: propagate request context
func handler(w http.ResponseWriter, r *http.Request) {
    result, err := fetchData(r.Context())
}

// BAD: context.Value for control flow
ctx = context.WithValue(ctx, "userID", id)
// ...later...
id := ctx.Value("userID").(string) // type assertion panic risk

// GOOD: typed key, defensive extraction
type ctxKey struct{}
ctx = context.WithValue(ctx, ctxKey{}, id)

func userIDFromCtx(ctx context.Context) (string, bool) {
    id, ok := ctx.Value(ctxKey{}).(string)
    return id, ok
}
```

Guidelines:
- `context.Background()` only at program entry points (main, init, top-level test)
- `context.TODO()` as explicit marker for "needs proper context later"
- Never store `context.Context` in a struct field

## Channel Direction

```go
// GOOD: constrain channel direction in signatures
func producer(out chan<- int) { ... } // send-only
func consumer(in <-chan int) { ... }  // receive-only
```

## Select + Default Trap

```go
// BAD: busy-spin with default
for {
    select {
    case msg := <-ch:
        handle(msg)
    default:
        // burns CPU in tight loop
    }
}

// GOOD: block until message or done
for {
    select {
    case msg := <-ch:
        handle(msg)
    case <-ctx.Done():
        return
    }
}
```

## sync.Pool and sync.Once

```go
// sync.Pool: reuse temporary objects to reduce GC pressure
var bufPool = sync.Pool{
    New: func() any { return new(bytes.Buffer) },
}
buf := bufPool.Get().(*bytes.Buffer)
buf.Reset() // IMPORTANT: always reset before use
defer bufPool.Put(buf)

// sync.Once: safe lazy initialization
var (
    instance *DB
    once     sync.Once
)
func GetDB() *DB {
    once.Do(func() {
        instance = connectDB() // runs exactly once
    })
    return instance
}
```

Pitfalls:
- `sync.Pool` objects may be collected between GC cycles — don't rely on persistence
- `sync.Once` panic: if `Do` panics, subsequent calls return immediately (the func is considered done)

## Worker Pool Pattern

```go
// BAD: unbounded goroutine spawning — one goroutine per request
func handleRequests(requests []Request) {
    for _, req := range requests {
        go func(r Request) {
            process(r) // 10k requests = 10k goroutines = OOM risk
        }(req)
    }
}

// GOOD: fixed worker pool with buffered channel
func handleRequests(ctx context.Context, requests []Request) {
    jobs := make(chan Request, len(requests))
    const numWorkers = 10

    var wg sync.WaitGroup
    for i := 0; i < numWorkers; i++ {
        wg.Add(1)
        go func() {
            defer wg.Done()
            for req := range jobs {
                process(req)
            }
        }()
    }

    for _, req := range requests {
        jobs <- req
    }
    close(jobs)
    wg.Wait()
}

// GOOD: errgroup.SetLimit for bounded concurrency (Go 1.20+)
func handleRequests(ctx context.Context, requests []Request) error {
    g, ctx := errgroup.WithContext(ctx)
    g.SetLimit(10)

    for _, req := range requests {
        g.Go(func() error {
            return process(ctx, req)
        })
    }
    return g.Wait()
}
```

Red flags:
- `go func()` inside a request handler or loop with no concurrency bound
- Goroutine count proportional to input size rather than a fixed pool
- No back-pressure mechanism when producers outpace consumers

## Goroutine Panic Recovery

```go
// BAD: panic inside goroutine crashes the entire process
go func(u *UserKey) {
    defer wg.Done()
    user, err := redis.GetGuest(ctx, u.Id) // any panic here = process dead
    if err != nil {
        return
    }
    resultCh <- user
}(u)

// GOOD: every goroutine has its own recover guard
go func(u *UserKey) {
    defer wg.Done()
    defer func() {
        if r := recover(); r != nil {
            log.ErrorContextf(ctx, "panic in getBatchUser goroutine: %v\n%s",
                r, debug.Stack())
        }
    }()
    user, err := redis.GetGuest(ctx, u.Id)
    if err != nil {
        return
    }
    resultCh <- user
}(u)
```

Key rules:
- Go panics do **not** cross goroutine boundaries. The parent goroutine cannot catch a child goroutine's panic.
- An unrecovered panic in any goroutine — including library code it calls — terminates the whole process immediately.
- `recover()` is only effective inside a `defer` function. `defer recover()` alone does nothing useful; it must be `defer func() { recover() }()`.
- Place the recover defer **before** any other defers to ensure it runs even if another defer panics.
- Always log the stack trace (`debug.Stack()`) alongside the recovered value for diagnosis.

Red flags:
- `go func()` body with no `defer func() { recover() }()` when calling external libraries, type assertions, or map access that could panic
- `defer wg.Done()` as the only defer — if the goroutine body panics, `wg.Done()` runs but the panic still propagates and kills the process
- `defer recover()` without wrapping in `func()` — this form does not suppress the panic

## Graceful Shutdown

```go
// BAD: abrupt exit — in-flight requests dropped, resources leaked
func main() {
    srv := &http.Server{Addr: ":8080", Handler: mux}
    go srv.ListenAndServe()

    sigCh := make(chan os.Signal, 1)
    signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
    <-sigCh
    os.Exit(0) // connections dropped, defers skipped
}

// GOOD: 3-phase shutdown — stop accepting → drain in-flight → cleanup
func main() {
    var wg sync.WaitGroup
    srv := &http.Server{
        Addr:    ":8080",
        Handler: withWG(&wg, mux), // middleware increments wg for each background task
    }

    // Phase 1: start serving
    go func() {
        if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
            log.Fatalf("listen: %v", err)
        }
    }()

    // Wait for termination signal
    ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
    defer stop()
    <-ctx.Done()
    log.Println("shutting down...")

    // Phase 2: drain in-flight requests (with timeout)
    shutdownCtx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
    defer cancel()
    if err := srv.Shutdown(shutdownCtx); err != nil {
        log.Printf("HTTP server shutdown error: %v", err)
    }

    // Phase 3: wait for background goroutines spawned by handlers
    wg.Wait()

    log.Println("clean shutdown complete")
}
```

The 3-phase pattern:
1. **Stop accepting**: `srv.Shutdown()` stops new connections
2. **Drain in-flight**: existing requests complete up to the timeout
3. **Cleanup**: wait for background goroutines, flush buffers, close DB connections

Red flags:
- `os.Exit()` in production server code
- `signal.Notify` without a shutdown sequence
- No timeout on the shutdown context (can hang forever)
- Background goroutines not tracked with `WaitGroup` or similar

## Timer and Ticker Leaks

```go
// BAD: time.After allocates a new timer every iteration — leaks until fire
for {
    select {
    case msg := <-ch:
        handle(msg)
    case <-time.After(5 * time.Second): // new timer each loop — memory leak
        log.Println("timeout")
        return
    }
}

// GOOD: reuse a single timer with Reset
timer := time.NewTimer(5 * time.Second)
defer timer.Stop()
for {
    select {
    case msg := <-ch:
        handle(msg)
        if !timer.Stop() {
            <-timer.C
        }
        timer.Reset(5 * time.Second)
    case <-timer.C:
        log.Println("timeout")
        return
    }
}

// BAD: ticker not stopped — goroutine inside runtime keeps ticking
func pollStatus(ctx context.Context) {
    ticker := time.NewTicker(1 * time.Second)
    // missing: defer ticker.Stop()
    for {
        select {
        case <-ticker.C:
            checkStatus()
        case <-ctx.Done():
            return // ticker leaked!
        }
    }
}

// GOOD: always defer ticker.Stop()
func pollStatus(ctx context.Context) {
    ticker := time.NewTicker(1 * time.Second)
    defer ticker.Stop()
    for {
        select {
        case <-ticker.C:
            checkStatus()
        case <-ctx.Done():
            return
        }
    }
}
```

Red flags:
- `time.After` inside any `for`/`select` loop
- `time.NewTicker` without a corresponding `Stop()`
- `time.NewTimer` without `Stop()` on all exit paths

## WaitGroup.Add Placement

```go
// BAD: wg.Add(1) inside the goroutine — race with wg.Wait()
var wg sync.WaitGroup
for _, item := range items {
    go func(it Item) {
        wg.Add(1) // goroutine may not execute before wg.Wait() returns
        defer wg.Done()
        process(it)
    }(item)
}
wg.Wait() // may return immediately if no goroutine started yet

// GOOD: wg.Add(1) before launching the goroutine
var wg sync.WaitGroup
for _, item := range items {
    wg.Add(1)
    go func(it Item) {
        defer wg.Done()
        process(it)
    }(item)
}
wg.Wait()
```

The rule is simple: `wg.Add()` must happen-before the `go` statement that calls `wg.Done()`. Placing `Add` inside the goroutine body creates a race where `Wait` can observe zero before any goroutine increments the counter.

Red flags:
- `wg.Add(1)` anywhere inside a `go func()` body
- `wg.Add(n)` with `n` computed from a value that might be stale
- `wg.Done()` without a matching `wg.Add()` (causes panic: negative WaitGroup counter)

## Loop Variable Capture (pre-Go 1.22)

```go
// BAD: all goroutines capture the same loop variable (pre-Go 1.22)
for _, v := range items {
    go func() {
        use(v) // all goroutines see the LAST value of v
    }()
}

// GOOD (pre-Go 1.22): shadow the loop variable
for _, v := range items {
    v := v // create a new variable scoped to this iteration
    go func() {
        use(v)
    }()
}

// GOOD (pre-Go 1.22): pass as function parameter
for _, v := range items {
    go func(val Item) {
        use(val)
    }(v)
}
```

**Go 1.22+ note**: Starting with Go 1.22, each loop iteration creates a new variable, so the capture bug no longer occurs. However, if your module's `go` directive is below 1.22, or you maintain libraries targeting older versions, this pattern still applies.

Red flags:
- `go func()` or `defer func()` inside `for range` referencing the loop variable directly
- Closure captures of `i` or `v` in `for i, v := range` without re-binding
- Tests passing locally (Go 1.22+) but failing in CI with an older Go version

## singleflight for Deduplication

```go
// BAD: concurrent cache misses each hit the backend
func GetUser(ctx context.Context, id string) (*User, error) {
    if u, ok := cache.Get(id); ok {
        return u, nil
    }
    // 100 concurrent requests for the same id = 100 DB queries
    return db.QueryUser(ctx, id)
}

// GOOD: singleflight deduplicates concurrent calls for the same key
import "golang.org/x/sync/singleflight"

var userGroup singleflight.Group

func GetUser(ctx context.Context, id string) (*User, error) {
    if u, ok := cache.Get(id); ok {
        return u, nil
    }
    v, err, _ := userGroup.Do(id, func() (any, error) {
        // only ONE call executes; others wait for the result
        u, err := db.QueryUser(ctx, id)
        if err == nil {
            cache.Set(id, u)
        }
        return u, err
    })
    if err != nil {
        return nil, err
    }
    return v.(*User), nil
}
```

When to use `singleflight`:
- Cache stampede prevention (many goroutines miss cache simultaneously)
- Expensive backend/API calls that are safe to share across waiters
- DNS resolution, config reloads, or any idempotent fetch

Red flags:
- Cache lookup + backend call without dedup in high-concurrency code paths
- `sync.Mutex` around the entire cache-miss path (serializes all keys, not just duplicates)
- Forgetting the third return value `shared` if you need to distinguish leader vs. follower

## Nil Channel in Select

```go
// GOOD: use nil channel to dynamically disable a select case
func merge(ctx context.Context, ch1, ch2 <-chan int) <-chan int {
    out := make(chan int)
    go func() {
        defer close(out)
        for ch1 != nil || ch2 != nil {
            select {
            case v, ok := <-ch1:
                if !ok {
                    ch1 = nil // disable this case — channel is drained
                    continue
                }
                out <- v
            case v, ok := <-ch2:
                if !ok {
                    ch2 = nil // disable this case — channel is drained
                    continue
                }
                out <- v
            case <-ctx.Done():
                return
            }
        }
    }()
    return out
}
```

Key properties of nil channels:
- Sending to a nil channel blocks forever
- Receiving from a nil channel blocks forever
- A nil channel in a `select` case is **never selected** (effectively disabled)

This technique is useful for:
- Merging N channels and gracefully handling each closing independently
- Fan-in patterns where producers finish at different times
- Disabling slow or unhealthy upstream sources without restructuring the select

## See Also

- `go-modern-practices.md` (typed atomics, goroutine lifecycle patterns)
- `go-performance-patterns.md` (lock optimization, sharded locks)
- `go-database-patterns.md` (connection pool lifecycle)