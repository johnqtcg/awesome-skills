# Go Modern Practices

Deep-dive reference for the **Modern Go & Best Practices (Medium)** category in SKILL.md step 5.

## Generics vs Interface Decision Matrix

### Core Distinction

| Aspect | Interface | Generics |
|--------|-----------|----------|
| Abstraction | Behavior (what it does) | Type (what it is) |
| Dispatch | Runtime (vtable) | Compile-time (monomorphization) |
| Use case | Polymorphism, dependency injection | Type-safe collections, algorithms |

### Quick Decision Flow

1. Need runtime polymorphism (different implementations at runtime)? → **Interface**
2. Need type-safe operations across multiple concrete types? → **Generics**
3. Writing a data structure or algorithm? → **Generics** (usually)
4. Defining a service boundary or plugin point? → **Interface**
5. Only one concrete type exists? → **Neither** (use the concrete type)

### When to Use Generics

```go
// GOOD: type-safe utility functions
func Map[T, U any](s []T, f func(T) U) []U {
    result := make([]U, len(s))
    for i, v := range s {
        result[i] = f(v)
    }
    return result
}

// GOOD: type-safe data structures
type Set[T comparable] struct {
    m map[T]struct{}
}

// GOOD: reducing boilerplate across similar types
func Contains[T comparable](slice []T, item T) bool {
    for _, v := range slice {
        if v == item {
            return true
        }
    }
    return false
}
```

### When NOT to Use Generics

```go
// BAD: generic for the sake of it — only one type used
func ProcessUser[T User](u T) error { ... } // just use User directly

// BAD: replacing interface polymorphism
func Handle[T HTTPHandler](h T) { ... } // use http.Handler interface

// BAD: over-constrained — simpler with interface
type Processor[T Readable & Writable & Closable] struct { ... }
// Better: define a small interface
```

### Constraint Design Principles

```go
// Use ~T for underlying type support
type Number interface {
    ~int | ~int32 | ~int64 | ~float32 | ~float64
}

// Prefer small, composable constraints
type Ordered interface {
    ~int | ~float64 | ~string
}

// Use standard library constraints (Go 1.21+)
import (
    "cmp"
    "slices"
    "maps"
)

// slices.Sort, slices.Contains, maps.Keys, etc.
slices.Sort(items) // sorts in place; use slices.SortFunc for custom ordering
```

## Typed Atomic Operations (Go 1.19+)

```go
// BAD: untyped atomic (error-prone, requires correct int64 alignment)
var counter int64
atomic.AddInt64(&counter, 1)
val := atomic.LoadInt64(&counter)

// GOOD: typed atomic (Go 1.19+)
var counter atomic.Int64
counter.Add(1)
val := counter.Load()

// GOOD: atomic.Bool for flags
var ready atomic.Bool
ready.Store(true)
if ready.Load() { ... }

// GOOD: atomic.Pointer for lock-free config reload
var config atomic.Pointer[Config]
config.Store(&Config{...})
cfg := config.Load()
```

Available typed atomics: `atomic.Bool`, `atomic.Int32`, `atomic.Int64`, `atomic.Uint32`, `atomic.Uint64`, `atomic.Pointer[T]`.

## Structured Logging with slog (Go 1.21+)

```go
// BAD: unstructured logging
log.Printf("user %s logged in from %s", userID, ip)

// GOOD: structured logging with slog
slog.Info("user logged in",
    "user_id", userID,
    "ip", ip,
    "method", "oauth",
)

// GOOD: typed attributes for performance-sensitive paths
slog.LogAttrs(ctx, slog.LevelInfo, "user logged in",
    slog.String("user_id", userID),
    slog.String("ip", ip),
)
```

### Logger Configuration

```go
// JSON handler for production
logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{
    Level: slog.LevelInfo,
}))
slog.SetDefault(logger)

// Text handler for development
logger := slog.New(slog.NewTextHandler(os.Stderr, &slog.HandlerOptions{
    Level: slog.LevelDebug,
}))

// Child logger with persistent attributes
userLogger := slog.With("user_id", userID)
userLogger.Info("action performed", "action", "update")
```

### Custom Handler

```go
// Wrap handler to add request-scoped fields
type contextHandler struct {
    slog.Handler
}

func (h *contextHandler) Handle(ctx context.Context, r slog.Record) error {
    if reqID, ok := ctx.Value(requestIDKey).(string); ok {
        r.AddAttrs(slog.String("request_id", reqID))
    }
    return h.Handler.Handle(ctx, r)
}
```

## Context Best Practices

### Six Core Principles

1. **Pass context as first parameter** — `func Foo(ctx context.Context, ...) error`
2. **Never store context in a struct** — pass it through call chains
3. **Derive child contexts** — use `context.With*` functions
4. **Respect cancellation** — check `ctx.Done()` in long operations
5. **Set timeouts at entry points** — HTTP handlers, CLI commands, job runners
6. **Avoid context.Value for required data** — use it for cross-cutting concerns only (tracing, auth)

### WithCancelCause (Go 1.20+)

```go
// BAD: cancel gives no reason
ctx, cancel := context.WithCancel(parent)
cancel() // why was it cancelled?

// GOOD: cancel with cause
ctx, cancel := context.WithCancelCause(parent)
cancel(fmt.Errorf("upstream service unavailable"))

// Later: retrieve the cause
if err := context.Cause(ctx); err != nil {
    slog.Error("context cancelled", "cause", err)
}
```

### WithoutCancel (Go 1.21+)

```go
// Use when you need context values but not cancellation
// e.g., background cleanup after request handler returns
func cleanup(ctx context.Context) {
    // Detach from parent cancellation, keep values (tracing, auth)
    bgCtx := context.WithoutCancel(ctx)
    go performCleanup(bgCtx)
}
```

### AfterFunc (Go 1.21+)

```go
// Execute a function when context is done
stop := context.AfterFunc(ctx, func() {
    conn.Close() // cleanup when context expires
})
// stop() returns true if the function was prevented from running
defer stop()
```

## Goroutine Lifecycle Management

### Always Recover Panics in Background Goroutines

```go
// BAD: unrecovered panic crashes the entire process
go func() {
    processItem(item) // if this panics, process dies
}()

// GOOD: recover + log
go func() {
    defer func() {
        if r := recover(); r != nil {
            slog.Error("goroutine panicked",
                "recover", r,
                "stack", string(debug.Stack()),
            )
        }
    }()
    processItem(item)
}()
```

### Goroutine Leak Prevention

```go
// BAD: goroutine blocks forever if no one reads
go func() {
    ch <- result // blocks if receiver is gone
}()

// GOOD: select with context cancellation
go func() {
    select {
    case ch <- result:
    case <-ctx.Done():
        return
    }
}()
```

### Concurrency Control

```go
// Worker pool pattern
func processAll(ctx context.Context, items []Item) error {
    g, ctx := errgroup.WithContext(ctx)
    g.SetLimit(10) // max 10 concurrent goroutines

    for _, item := range items {
        g.Go(func() error {
            return process(ctx, item)
        })
    }
    return g.Wait()
}

// Semaphore pattern
sem := make(chan struct{}, maxConcurrency)
for _, item := range items {
    sem <- struct{}{} // acquire
    go func() {
        defer func() { <-sem }() // release
        process(item)
    }()
}
```

### Fire-and-Forget Anti-Pattern

```go
// BAD: fire-and-forget — no error handling, no lifecycle control
go sendEmail(user, msg) // what if it fails? what if server is shutting down?

// GOOD: track goroutine lifecycle
type EmailSender struct {
    wg sync.WaitGroup
}

func (s *EmailSender) Send(ctx context.Context, user, msg string) {
    s.wg.Add(1)
    go func() {
        defer s.wg.Done()
        if err := sendEmail(ctx, user, msg); err != nil {
            slog.Error("email send failed", "user", user, "err", err)
        }
    }()
}

func (s *EmailSender) Shutdown() {
    s.wg.Wait() // wait for all in-flight sends
}
```

## Channel Buffer Selection

| Buffer Size | Semantics | Use When |
|-------------|-----------|----------|
| 0 (unbuffered) | Synchronization — sender blocks until receiver ready | Handoff/rendezvous, signal coordination |
| 1 | Decoupling — at most one pending item | Latest-value updates, done signals |
| N (small, fixed) | Bounded queue — absorb bursts | Known producer/consumer rate mismatch |
| N (large) | Throughput buffer | Pipeline stages with measured throughput |

Selection principles:
- **Default to unbuffered** unless you have a specific reason for buffering
- **Never use buffered channels to "hide" concurrency bugs** — if unbuffered deadlocks, the design may be wrong
- **Size buffers based on measured needs**, not guesses
- **Buffered channels are NOT queues** — for persistent work queues, use a proper queue

## strings.Clone (Go 1.20+)

Prevents large parent string from being retained in memory by a small substring:

```go
// BAD: substring retains entire parent string
func extractHost(rawURL string) string {
    // rawURL might be a large HTTP request line
    host := rawURL[7:21] // still references entire rawURL
    return host
}

// GOOD: Clone creates independent copy
func extractHost(rawURL string) string {
    host := rawURL[7:21]
    return strings.Clone(host) // independent memory
}
```

Use `strings.Clone` when:
- Extracting small parts from large strings (HTTP bodies, file contents, log lines)
- Storing substrings in long-lived data structures (caches, indexes)
- The source string will be garbage collected but the substring lives on

## errors.Join (Go 1.20+)

```go
// BAD: manual multi-error concatenation
func validateConfig(cfg Config) error {
    var msgs []string
    if cfg.Host == "" {
        msgs = append(msgs, "host is required")
    }
    if cfg.Port == 0 {
        msgs = append(msgs, "port is required")
    }
    if len(msgs) > 0 {
        return fmt.Errorf("validation failed: %s", strings.Join(msgs, "; "))
    }
    return nil
}

// GOOD: errors.Join preserves individual error identity
var ErrMissingHost = errors.New("host is required")
var ErrMissingPort = errors.New("port is required")

func validateConfig(cfg Config) error {
    var errs []error
    if cfg.Host == "" {
        errs = append(errs, ErrMissingHost)
    }
    if cfg.Port == 0 {
        errs = append(errs, ErrMissingPort)
    }
    return errors.Join(errs...) // returns nil if errs is empty
}

// Each wrapped error remains individually testable:
//   err := validateConfig(cfg)
//   errors.Is(err, ErrMissingHost) // true
//   errors.Is(err, ErrMissingPort) // true
```

### Cleanup Pattern: Collecting Deferred Close Errors

```go
func processFile(path string) (retErr error) {
    f, err := os.Open(path)
    if err != nil {
        return err
    }
    defer func() {
        retErr = errors.Join(retErr, f.Close())
    }()

    // ... work with f ...
    return nil
}
```

## sync.OnceValue / sync.OnceFunc (Go 1.21+)

```go
// BAD: manual sync.Once + package-level variable
var (
    dbOnce sync.Once
    dbConn *sql.DB
)

func GetDB() *sql.DB {
    dbOnce.Do(func() {
        dbConn, _ = sql.Open("postgres", os.Getenv("DSN"))
    })
    return dbConn
}

// GOOD: sync.OnceValue — cleaner, no separate variable
var GetDB = sync.OnceValue(func() *sql.DB {
    db, err := sql.Open("postgres", os.Getenv("DSN"))
    if err != nil {
        panic("open db: " + err.Error())
    }
    return db
})

// Call site: db := GetDB()
```

`sync.OnceFunc(func())` is the zero-return variant — useful for one-time side-effect init (e.g., registering metrics). Both are concurrency-safe and guarantee at-most-once execution.

Caveat: if the function panics, the panic is cached and replayed on every subsequent call. Use `sync.OnceValue` only for initialization that is truly fatal on failure; for transient errors (e.g., connecting to an external service that may be temporarily down), use a manual retry pattern instead.

## Loop Variable Fix (Go 1.22+)

Go 1.22 changed loop variable semantics: each iteration now gets its **own copy** of the loop variable, eliminating a long-standing footgun.

```go
// BAD (pre-1.22): all goroutines capture the same variable
for _, v := range items {
    go func() {
        use(v) // every goroutine sees the last value of v
    }()
}

// Pre-1.22 workaround: shadow the variable
for _, v := range items {
    v := v // create per-iteration copy
    go func() {
        use(v)
    }()
}
```

In Go 1.22+, the first form is correct automatically — each iteration has its own `v`.

**Reviewer note:** when the project targets Go 1.22+, flag leftover `v := v` shadows during review. They are unnecessary noise and can confuse readers into thinking there is still a capture bug.

## Range Over Integers (Go 1.22+)

```go
// BAD: classic three-clause loop
for i := 0; i < n; i++ {
    process(i)
}

// GOOD: range over integer (Go 1.22+)
for i := range n {
    process(i)
}
```

`range n` iterates `i` from `0` to `n-1`. Cleaner for simple counted loops.

## slices and maps Packages (Go 1.21+)

Replace hand-rolled helpers with standard library functions.

```go
// BAD: hand-rolled Contains
func contains(ss []string, target string) bool {
    for _, s := range ss {
        if s == target {
            return true
        }
    }
    return false
}

// GOOD
found := slices.Contains(ss, "target")
```

```go
// BAD: sort.Slice with less func
sort.Slice(users, func(i, j int) bool {
    return users[i].Name < users[j].Name
})

// GOOD: slices.SortFunc — type-safe, no index juggling
slices.SortFunc(users, func(a, b User) int {
    return cmp.Compare(a.Name, b.Name)
})
```

```go
// BAD: manual slice/map copy
dst := make([]int, len(src))
copy(dst, src)

// GOOD
dst := slices.Clone(src)
mcopy := maps.Clone(original)
keys := slices.Collect(maps.Keys(m))
```

## min/max Builtins (Go 1.21+)

```go
// BAD: float64 conversion just to use math.Min on integers
lo := int(math.Min(float64(a), float64(b)))
hi := int(math.Max(float64(a), float64(b)))

// GOOD: type-safe builtins for any ordered type
lo := min(a, b)
hi := max(a, b)

// Also works with strings and floats — no import needed
shortest := min(len(s1), len(s2))
latest   := max(t1, t2) // time.Time does not work — only ordered types
```

`min` and `max` accept any `cmp.Ordered` type (`int`, `float64`, `string`, etc.) and are variadic: `min(a, b, c)` is valid.

## See Also

- `go-concurrency-patterns.md` — goroutine lifecycle, singleflight
- `go-error-and-quality.md` — custom error types, wrapping
- `go-test-quality.md` — fuzz testing for modern Go features