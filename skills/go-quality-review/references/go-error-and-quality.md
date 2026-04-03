# Go Error Handling & Code Quality

Deep-dive reference for **Error Handling (High)** and **Code Quality (Medium)** categories in SKILL.md step 5.

---

## Error Handling

### Ignored Errors

```go
// BAD: error discarded with blank identifier
data, _ := json.Marshal(obj)
f.Close() // error ignored

// GOOD: handle or propagate
data, err := json.Marshal(obj)
if err != nil {
    return fmt.Errorf("marshal user: %w", err)
}
if err := f.Close(); err != nil {
    return fmt.Errorf("close file: %w", err)
}
```

Acceptable `_` discard cases (document why):
- `fmt.Fprintf` to known-good writers (e.g., `bytes.Buffer`)
- Hash `Write` (never returns error per `io.Writer` contract)

### Missing Error Wrapping

```go
// BAD: bare error return loses context
if err != nil {
    return err
}

// GOOD: wrap with %w for chain inspection
if err != nil {
    return fmt.Errorf("create user %q: %w", name, err)
}
```

Guidelines:
- **Inspect every `return err` path**: for each function under review, trace all `return ..., err` statements and verify each has a descriptive `fmt.Errorf("operationName: %w", err)` wrapper. Raw returns lose call-site context and may expose internal DB/system error details (table names, column names, SQL syntax) to callers, creating both debugging and security issues.
- Wrap at every abstraction boundary
- Error message: lowercase, no trailing punctuation, describe what failed
- Include key identifiers (user ID, file path) in wrap message

### Panic for Recoverable Errors

```go
// BAD: panic in library/handler code
func ParseConfig(data []byte) Config {
    var cfg Config
    if err := json.Unmarshal(data, &cfg); err != nil {
        panic(err) // kills caller
    }
    return cfg
}

// GOOD: return error
func ParseConfig(data []byte) (Config, error) {
    var cfg Config
    if err := json.Unmarshal(data, &cfg); err != nil {
        return Config{}, fmt.Errorf("parse config: %w", err)
    }
    return cfg, nil
}
```

Acceptable panic:
- Programmer error in `init()` (missing required env var at startup)
- Truly unrecoverable state (corrupted invariant that indicates a bug)

### errors.Is / errors.As

```go
// BAD: direct comparison breaks wrapping
if err == sql.ErrNoRows { ... }

// GOOD: traverses the error chain
if errors.Is(err, sql.ErrNoRows) { ... }

// BAD: type assertion on wrapped error
if e, ok := err.(*os.PathError); ok { ... }

// GOOD: unwraps through chain
var pathErr *os.PathError
if errors.As(err, &pathErr) { ... }
```

---

## Code Quality

### Pointer Slice Nil Guard

```go
// BAD: dereferencing pointer slice element without nil check
func getBatchUser(ctx context.Context, userKeys []*UserKey) ([]*User, error) {
    for i, u := range userKeys {
        user, err := redis.GetGuest(ctx, u.Id) // panic if u is nil
        // ...
    }
}

// GOOD: nil guard before field access
func getBatchUser(ctx context.Context, userKeys []*UserKey) ([]*User, error) {
    for i, u := range userKeys {
        if u == nil {
            continue
        }
        user, err := redis.GetGuest(ctx, u.Id)
        // ...
    }
}
```

When a parameter or variable is `[]*T` (pointer slice), each element may be nil. Accessing fields or calling methods on a nil element causes a nil pointer dereference panic. This applies to:
- Function parameters of type `[]*T` — the caller controls the content
- Slices populated by external sources (DB scan, JSON unmarshal, API response)
- Slices built via `append` where some entries may have been set to nil

### Function Length and Nesting

```go
// BAD: deeply nested logic
func process(items []Item) error {
    for _, item := range items {
        if item.Valid {
            if item.Type == "A" {
                if item.Count > 0 {
                    // actual logic buried 4 levels deep
                }
            }
        }
    }
}

// GOOD: early return / guard clause pattern
func process(items []Item) error {
    for _, item := range items {
        if !item.Valid {
            continue
        }
        if item.Type != "A" {
            continue
        }
        if item.Count <= 0 {
            continue
        }
        // actual logic at 2 levels
    }
}
```

Thresholds:
- Function >50 lines: consider splitting
- Nesting >4 levels: refactor with early returns or extract helper

### Naked Returns

```go
// BAD: naked return in long function (reader must scroll to see what's returned)
func fetchUser(id string) (user User, err error) {
    // ... 30 lines of logic ...
    return // what is returned?
}

// GOOD: explicit return values
func fetchUser(id string) (User, error) {
    // ... logic ...
    return user, nil
}
```

Naked returns are acceptable only in very short functions (<5 lines).

### Mutable Package-Level Variables

```go
// BAD: mutable global state
var DefaultTimeout = 30 * time.Second // can be changed by any goroutine

// GOOD: constant or unexported with getter
const defaultTimeout = 30 * time.Second

// GOOD: functional options for configurability
type Option func(*Client)
func WithTimeout(d time.Duration) Option { ... }
```

### Interface Pollution

```go
// BAD: large interface defined where implemented (Java-style)
type UserManager interface {
    Create(User) error
    Update(User) error
    Delete(string) error
    FindByID(string) (User, error)
    FindByEmail(string) (User, error)
    List(Filter) ([]User, error)
    Count(Filter) (int, error)
    // ... 10 more methods
}

// GOOD: small interface defined where consumed
type UserFinder interface {
    FindByID(string) (User, error)
}
```

Principles:
- Define interfaces at the call site, not the implementation site
- 1-3 methods per interface
- Accept interfaces, return structs

### Type Assertion Without ok Check

```go
// BAD: panics if assertion fails
val := ctx.Value(key).(string)

// GOOD: comma-ok pattern
val, ok := ctx.Value(key).(string)
if !ok {
    return fmt.Errorf("expected string for key %v", key)
}
```

### Defer in Loop

```go
// BAD: deferred calls accumulate until function returns
func processFiles(paths []string) error {
    for _, p := range paths {
        f, err := os.Open(p)
        if err != nil {
            return err
        }
        defer f.Close() // not closed until function returns!
    }
}

// GOOD: extract to function or close explicitly
func processFiles(paths []string) error {
    for _, p := range paths {
        if err := processFile(p); err != nil {
            return err
        }
    }
    return nil
}

func processFile(path string) error {
    f, err := os.Open(path)
    if err != nil {
        return err
    }
    defer f.Close()
    // ... process ...
    return nil
}
```

### Init Function Abuse

```go
// BAD: init with side effects that are hard to test
func init() {
    db = connectDatabase()        // fails at import time
    http.HandleFunc("/", handler) // hidden registration
}

// GOOD: explicit initialization
func NewApp(cfg Config) (*App, error) {
    db, err := connectDatabase(cfg.DSN)
    if err != nil {
        return nil, fmt.Errorf("connect db: %w", err)
    }
    return &App{db: db}, nil
}
```

Acceptable `init()`:
- Register `database/sql` drivers
- Register `encoding/gob` types
- Set `flag` defaults

---

## Generics vs Interface

| Use Generics When | Use Interface When |
|---|---|
| Type-safe containers (set, queue, tree) | Behavior abstraction (Reader, Handler) |
| Functions operating on multiple concrete types uniformly | Dependency injection / testing |
| Reducing boilerplate for type-specific logic | Runtime polymorphism needed |
| Compile-time type constraint is valuable | Interface is already idiomatic (io.Reader) |

```go
// Generics: type-safe, zero runtime overhead
func Map[T, U any](s []T, f func(T) U) []U { ... }

// Interface: behavior contract
type Storage interface {
    Save(ctx context.Context, key string, data []byte) error
}
```

Avoid `any` as a type constraint when a more specific constraint exists.

---

## Nil Interface Trap

Go's most common gotcha: an interface value is `nil` only when **both** its type and value are `nil`. Storing a typed nil pointer into an interface produces a non-nil interface.

```go
// BAD: returns non-nil error even though err is nil
type MyError struct{ Msg string }
func (e *MyError) Error() string { return e.Msg }

func getError() error {
    var err *MyError // nil pointer
    return err       // interface{type: *MyError, value: nil} ≠ nil
}

func main() {
    if err := getError(); err != nil {
        fmt.Println("unexpected:", err) // prints "unexpected: <nil>"
    }
}
```

```go
// GOOD: return nil explicitly, or use the interface type as the variable
func getError() error {
    var err *MyError
    if err == nil {
        return nil // explicit nil — interface has no type, no value
    }
    return err
}

// GOOD: declare the variable as the interface type
func getError2() error {
    var err error // interface type — zero value is true nil
    // ... conditionally assign ...
    return err
}
```

Rule: never return a typed nil pointer through an interface return. Either return `nil` literally, or declare the variable as the interface type.

---

## Custom Error Types

Bare `fmt.Errorf` strings make it impossible for callers to distinguish errors programmatically.

```go
// BAD: caller cannot match on error kind
func FindUser(id string) (User, error) {
    // ...
    return User{}, fmt.Errorf("not found") // no way to detect "not found" vs other failures
}
```

```go
// GOOD: sentinel errors for simple, fixed conditions
var ErrNotFound = errors.New("not found")
var ErrConflict = errors.New("conflict")

func FindUser(id string) (User, error) {
    // ...
    return User{}, fmt.Errorf("find user %q: %w", id, ErrNotFound)
}

// Caller:
if errors.Is(err, ErrNotFound) { /* 404 */ }
```

```go
// GOOD: struct errors when callers need extra context
type ValidationError struct {
    Field   string
    Message string
}

func (e *ValidationError) Error() string {
    return fmt.Sprintf("validation: %s — %s", e.Field, e.Message)
}

func (e *ValidationError) Unwrap() error { return nil }

// Caller:
var ve *ValidationError
if errors.As(err, &ve) {
    log.Printf("field %s: %s", ve.Field, ve.Message)
}
```

When to use which:

| Sentinel (`ErrXxx`)            | Struct (`XxxError`)                  |
|--------------------------------|--------------------------------------|
| Fixed condition, no extra data | Caller needs structured fields       |
| Comparable with `errors.Is`    | Inspectable with `errors.As`         |
| E.g., `ErrNotFound`, `ErrAuth` | E.g., `ValidationError`, `HTTPError` |

Naming conventions:
- Sentinel: `var ErrXxx = errors.New("...")`
- Struct: `type XxxError struct { ... }`

---

## Receiver Type Decision

Inconsistent receiver types on the same struct cause confusion and subtle interface-satisfaction bugs.

```go
// BAD: mixed receivers on the same type
type Cache struct {
    mu    sync.Mutex
    items map[string]Item
}

func (c Cache) Len() int       { return len(c.items) }  // value receiver — copies mutex!
func (c *Cache) Set(k string, v Item) { c.mu.Lock(); defer c.mu.Unlock(); c.items[k] = v }
```

```go
// GOOD: all pointer receivers — consistent, avoids copying sync primitives
func (c *Cache) Len() int              { return len(c.items) }
func (c *Cache) Set(k string, v Item)  { c.mu.Lock(); defer c.mu.Unlock(); c.items[k] = v }
```

Decision matrix:

| Use **pointer** receiver `*T` when:                          | Use **value** receiver `T` when:                      |
|--------------------------------------------------------------|-------------------------------------------------------|
| Method mutates state                                         | Type is small immutable value (e.g., `time.Time`)     |
| Struct is large (>~64 bytes)                                 | Method is a pure function on the value                 |
| Struct contains `sync.Mutex`, channel, or other non-copyable | Type is a basic/scalar alias (e.g., `type Celsius float64`) |
| Type will satisfy interfaces requiring pointer receiver      |                                                       |

**Rule**: if _any_ method on a type needs a pointer receiver, make _all_ methods use pointer receivers for consistency. A value of type `T` cannot satisfy an interface if the method set requires `*T`.

---

## Shadowed Error Variable

`:=` inside an inner scope creates a new variable, silently leaving the outer `err` unchanged.

```go
// BAD: outer err is never updated
func doWork() error {
    var err error

    if condition {
        result, err := riskyCall() // new err — shadows outer err
        if err != nil {
            return err
        }
        use(result)
    }

    return err // always nil — the inner err was a different variable
}
```

```go
// GOOD: use = for the existing variable, declare result separately
func doWork() error {
    var err error

    if condition {
        var result Result
        result, err = riskyCall() // assigns to outer err
        if err != nil {
            return err
        }
        use(result)
    }

    return err
}
```

```go
// GOOD: restructure to avoid the issue entirely
func doWork() error {
    if condition {
        result, err := riskyCall()
        if err != nil {
            return fmt.Errorf("risky call: %w", err)
        }
        use(result)
    }
    return nil
}
```

Subtle variant — `if` initializer scope:

```go
var err error
// ...
if result, err := fn(); err != nil { // this err is scoped to the if block
    return err
}
// outer err is still nil here — fn's error was never assigned to it
```

Tip: run `go vet -shadow` or enable the `shadow` analyzer in your linter to catch these automatically.

---

## Log Once, Return Errors

Logging an error **and** returning it causes the same failure to appear multiple times in logs, making debugging harder.

```go
// BAD: double reporting
func LoadConfig(path string) (Config, error) {
    data, err := os.ReadFile(path)
    if err != nil {
        log.Printf("failed to read config: %v", err) // logged here
        return Config{}, fmt.Errorf("read config: %w", err) // AND returned
    }
    // ...
}

func main() {
    cfg, err := LoadConfig("app.yaml")
    if err != nil {
        log.Fatalf("startup failed: %v", err) // logged AGAIN
    }
}
// Output:
// failed to read config: open app.yaml: no such file
// startup failed: read config: open app.yaml: no such file
```

```go
// GOOD: intermediate layers wrap and return — top-level handler logs once
func LoadConfig(path string) (Config, error) {
    data, err := os.ReadFile(path)
    if err != nil {
        return Config{}, fmt.Errorf("read config %q: %w", path, err) // wrap only
    }
    // ...
}

func main() {
    cfg, err := LoadConfig("app.yaml")
    if err != nil {
        log.Fatalf("startup failed: %v", err) // single log point
    }
}
```

Boundary rule:
- **Intermediate layers**: wrap with context (`fmt.Errorf("...: %w", err)`) and return — never log.
- **Top-level handlers** (HTTP handler, main, worker loop): log and/or translate to user-facing response.
- **Exception**: logging at intermediate layers is acceptable when the error is intentionally _swallowed_ (not returned), but this should be rare and documented.

---

## See Also

- `go-concurrency-patterns.md` — panic recovery, goroutine error handling
- `go-database-patterns.md` — `sql.ErrNoRows` handling
- `go-test-quality.md` — assertion completeness for error paths