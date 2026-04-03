# Go Test Quality

Deep-dive reference for the **Test Quality (High)** category in SKILL.md step 6.

## Table-Driven Tests

```go
func TestParseAmount(t *testing.T) {
    tests := []struct {
        name string; input string; want int64; wantErr bool
    }{
        {"valid integer", "100", 100, false},
        {"valid with cents", "10.50", 1050, false},
        {"zero", "0", 0, false},
        {"negative", "-5", -500, false},
        {"empty string", "", 0, true},
        {"non-numeric", "abc", 0, true},
        {"overflow", "99999999999999999999", 0, true},
    }
    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            got, err := ParseAmount(tt.input)
            if tt.wantErr {
                if err == nil { t.Fatal("expected error, got nil") }
                return
            }
            if err != nil { t.Fatalf("unexpected error: %v", err) }
            if got != tt.want {
                t.Errorf("ParseAmount(%q) = %d, want %d", tt.input, got, tt.want)
            }
        })
    }
}
```

Checklist: descriptive `name` per case, happy + edge + error coverage, `t.Run` for subtest isolation, error messages include input/got/want.

## Test Naming Convention

```
TestFuncName_scenario
TestFuncName_scenario_subcondition
```

Examples: `TestCreateUser_validInput`, `TestCreateUser_duplicateEmail_returnsConflict`, `TestParseConfig_emptyFile_returnsDefault`

## t.Helper()

```go
// BAD: error points to helper function, not the calling test
func assertNoError(t *testing.T, err error) {
    if err != nil {
        t.Fatalf("unexpected error: %v", err) // line reported here
    }
}

// GOOD: t.Helper() fixes line reporting
func assertNoError(t *testing.T, err error) {
    t.Helper()
    if err != nil {
        t.Fatalf("unexpected error: %v", err) // line reported at caller
    }
}
```

Rule: Every test helper function must call `t.Helper()` as its first statement.

## t.Cleanup()

```go
func TestWithTempDir(t *testing.T) {
    dir := t.TempDir() // auto-cleaned up
    db := setupTestDB(t)
    t.Cleanup(func() { db.Close() })
}
```

Prefer `t.Cleanup()` over `defer` in test helpers — cleanup runs even if the helper returns early.

## Assertion Completeness

```go
// BAD: only checks "no error" — doesn't verify behavior
func TestGetUser(t *testing.T) {
    user, err := GetUser("123")
    if err != nil { t.Fatal(err) }
    // missing: what about the user?
}

// GOOD: verify actual behavior
func TestGetUser(t *testing.T) {
    user, err := GetUser("123")
    if err != nil { t.Fatalf("GetUser: %v", err) }
    if user.ID != "123" { t.Errorf("ID = %q, want %q", user.ID, "123") }
    if user.Name == "" { t.Error("Name is empty") }
}
```

Checklist: verify return value fields (not just "no error"), verify error type/message (not just `err != nil`), verify side effects (DB state, files, messages).

## Boundary / Edge Cases

Always test these boundaries for the changed code:

| Type | Cases |
|------|-------|
| Nil/zero | `nil` pointer, `nil` slice, `nil` map, zero struct |
| Empty | Empty string `""`, empty slice `[]T{}`, empty map |
| One | Single element, length 1 |
| Boundary | `math.MaxInt`, `math.MinInt`, max slice capacity |
| Unicode | Multi-byte chars, emoji, RTL text |
| Concurrent | Parallel subtests with `t.Parallel()` for race detection |

## Mock / Stub Best Practices

```go
// GOOD: minimal interface at test site
type mockStore struct {
    findFn func(id string) (*User, error)
}
func (m *mockStore) FindByID(id string) (*User, error) { return m.findFn(id) }

func TestService_GetUser(t *testing.T) {
    store := &mockStore{
        findFn: func(id string) (*User, error) {
            if id == "123" {
                return &User{ID: "123", Name: "Alice"}, nil
            }
            return nil, ErrNotFound
        },
    }
    svc := NewService(store)
    // ... test ...
}
```

Guidelines: mock at interface boundaries (not internal functions), keep mock scope minimal, prefer hand-written mocks over heavy frameworks, test real implementations when feasible.

## Benchmark Tests (testing.B)

```go
// BAD: no ResetTimer after expensive setup, no alloc reporting
func BenchmarkProcess(b *testing.B) {
    data := loadLargeFixture() // expensive — counted in benchmark time
    for i := 0; i < b.N; i++ {
        Process(data)
    }
}

// GOOD: proper setup isolation and alloc tracking
func BenchmarkProcess(b *testing.B) {
    data := loadLargeFixture()
    b.ReportAllocs()
    b.ResetTimer()
    for i := 0; i < b.N; i++ {
        Process(data)
    }
}
```

Sub-benchmarks for comparing variants:

```go
// GOOD: sub-benchmarks with parallel variant
func BenchmarkEncode(b *testing.B) {
    payload := makePayload(1024)
    b.Run("json", func(b *testing.B) {
        b.ReportAllocs()
        for i := 0; i < b.N; i++ { json.Marshal(payload) }
    })
    b.Run("msgpack", func(b *testing.B) {
        b.ReportAllocs()
        for i := 0; i < b.N; i++ { msgpack.Marshal(payload) }
    })
    b.Run("json_parallel", func(b *testing.B) {
        b.ReportAllocs()
        b.RunParallel(func(pb *testing.PB) {
            for pb.Next() { json.Marshal(payload) }
        })
    })
}
```

Checklist: `b.ResetTimer()` after expensive setup, `b.ReportAllocs()` for alloc counts, `b.RunParallel()` for contention throughput. Run: `go test -run='^$' -bench=. -benchtime=3s -count=5 -benchmem`. Use `benchstat` for statistical comparison.

## Fuzz Tests (testing.F, Go 1.18+)

```go
// GOOD: fuzz test for a parser with seed corpus
func FuzzParseHeader(f *testing.F) {
    f.Add([]byte("Content-Type: text/html\r\n"))
    f.Add([]byte("X-Custom: value with spaces\r\n"))
    f.Add([]byte(""))
    f.Add([]byte("\r\n\r\n"))
    f.Add([]byte("MalformedNoColon\r\n"))

    f.Fuzz(func(t *testing.T, data []byte) {
        header, err := ParseHeader(data)
        if err != nil {
            return // invalid input is fine, just must not panic
        }
        raw := header.Bytes()
        header2, err := ParseHeader(raw)
        if err != nil {
            t.Fatalf("round-trip failed: %v", err)
        }
        if header.Key != header2.Key || header.Value != header2.Value {
            t.Errorf("round-trip mismatch: %+v vs %+v", header, header2)
        }
    })
}
```

Guidelines: seeds cover happy/boundary/empty/tricky inputs. Fuzz callback must never panic — that is the primary invariant. Prefer property-based checks (round-trip, idempotency) over exact assertions. Run: `go test -fuzz=FuzzParseHeader -fuzztime=30s`. Crashing inputs saved to `testdata/fuzz/` automatically.

## HTTP Handler Testing (httptest)

```go
// BAD: starting a real server to test a handler
func TestHandler_Bad(t *testing.T) {
    go http.ListenAndServe(":9999", myHandler())
    time.Sleep(100 * time.Millisecond) // race-prone, port may conflict
    resp, err := http.Get("http://localhost:9999/health")
    if err != nil {
        t.Fatal(err)
    }
    defer resp.Body.Close()
}

// GOOD: httptest.NewRecorder for unit-level handler tests
func TestHealthHandler(t *testing.T) {
    req := httptest.NewRequest(http.MethodGet, "/health", nil)
    rec := httptest.NewRecorder()
    HealthHandler(rec, req)

    if rec.Code != http.StatusOK {
        t.Errorf("status = %d, want %d", rec.Code, http.StatusOK)
    }
    if body := rec.Body.String(); body != `{"status":"ok"}` {
        t.Errorf("body = %q, want %q", body, `{"status":"ok"}`)
    }
}
```

```go
// GOOD: httptest.NewServer for integration testing with full HTTP stack
func TestAPI_CreateUser(t *testing.T) {
    srv := httptest.NewServer(newRouter())
    t.Cleanup(srv.Close)
    body := strings.NewReader(`{"name":"Alice","email":"a@b.com"}`)
    resp, err := srv.Client().Post(srv.URL+"/users", "application/json", body)
    if err != nil { t.Fatalf("POST /users: %v", err) }
    defer resp.Body.Close()
    if resp.StatusCode != http.StatusCreated {
        t.Errorf("status = %d, want %d", resp.StatusCode, http.StatusCreated)
    }
}
```

Checklist: prefer `httptest.NewRecorder` for isolated handler tests, `httptest.NewServer` for full router/middleware stack, always `t.Cleanup(srv.Close)`, never hardcode ports.

## t.Parallel() Deep Guide

```go
// GOOD: parallel subtests with properly captured loop variable
func TestSlugify(t *testing.T) {
    tests := []struct {
        name, input, want string
    }{
        {"spaces", "hello world", "hello-world"},
        {"upper", "GoLang", "golang"},
        {"special", "a@b#c", "a-b-c"},
    }
    for _, tt := range tests {
        tt := tt // capture for pre-Go 1.22 (unnecessary in Go 1.22+)
        t.Run(tt.name, func(t *testing.T) {
            t.Parallel()
            if got := Slugify(tt.input); got != tt.want {
                t.Errorf("Slugify(%q) = %q, want %q", tt.input, got, tt.want)
            }
        })
    }
}
```

```go
// BAD: shared mutable state without synchronization
func TestCounter_bad(t *testing.T) {
    counter := 0
    for i := 0; i < 10; i++ {
        t.Run(fmt.Sprintf("inc_%d", i), func(t *testing.T) {
            t.Parallel()
            counter++ // DATA RACE
        })
    }
}

// GOOD: atomic or per-subtest owned data
func TestCounter_good(t *testing.T) {
    var counter atomic.Int64
    for i := 0; i < 10; i++ {
        t.Run(fmt.Sprintf("inc_%d", i), func(t *testing.T) {
            t.Parallel()
            counter.Add(1)
        })
    }
}
```

When **NOT** to use `t.Parallel()`:
- Tests sharing a real database that depend on insertion/deletion order
- Tests that bind to a specific port or named resource
- Tests using `t.Setenv()` (panics if combined with `t.Parallel()`)
- Tests that mutate package-level state without synchronization

Rule: If a test calls `t.Parallel()`, it must be safe to run concurrently with every other parallel test in the same package. Validate with `go test -race -count=3`.

## TestMain for Setup/Teardown

```go
// GOOD: one-time expensive setup shared across all tests in a package
var testDB *sql.DB

func TestMain(m *testing.M) {
    var err error
    testDB, err = sql.Open("postgres", os.Getenv("TEST_DSN"))
    if err != nil { fmt.Fprintf(os.Stderr, "setup: %v\n", err); os.Exit(1) }
    code := m.Run()
    testDB.Close()
    os.Exit(code)
}
```

Guidelines: runs once per package, not per test. Always `os.Exit(m.Run())` — forgetting means exit 0 on failure. Use for expensive one-time resources (DB, containers, large fixtures). `t.Log`/`t.Fatal` are **not available** inside `TestMain` — use `fmt.Fprintf(os.Stderr, ...)` + `os.Exit(1)`.

## Integration Test Gating

```go
// BAD: integration test mixed with unit tests, always runs
func TestOrderFlow_integration(t *testing.T) {
    db := connectRealDB() // fails on every dev machine without DB
}

// GOOD: gated by build tag — only runs when explicitly requested
//go:build integration
package order_test

func TestOrderFlow_integration(t *testing.T) {
    dsn := os.Getenv("TEST_DSN")
    if dsn == "" { t.Fatal("TEST_DSN required") }
    db, err := sql.Open("postgres", dsn)
    if err != nil { t.Fatalf("connect: %v", err) }
    t.Cleanup(func() { db.Close() })
    // ...
}
```

Run with: `go test -tags=integration ./...`

Env-var gating (simpler, no build tags):

```go
// GOOD: skip when env not set
func TestExternalAPI(t *testing.T) {
    apiKey := os.Getenv("EXTERNAL_API_KEY")
    if apiKey == "" { t.Skip("EXTERNAL_API_KEY not set; skipping") }
    client := NewClient(apiKey)
    // ...
}
```

Guidelines: build tags keep integration tests out of `go test ./...`. Env-var gating is lighter but shows as "skipped". Integration tests must own setup/teardown — never rely on leftover state. In CI, run in a separate job with service containers.

## Golden File Testing

```go
var update = flag.Bool("update", false, "update golden files")

func TestRender_golden(t *testing.T) {
    tests := []struct{ name, input, golden string }{
        {"simple", "hello", "testdata/simple.golden"},
        {"complex", "<b>bold</b>", "testdata/complex.golden"},
    }
    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            got := Render(tt.input)
            if *update {
                os.MkdirAll("testdata", 0o755)
                os.WriteFile(tt.golden, []byte(got), 0o644)
                return
            }
            want, err := os.ReadFile(tt.golden)
            if err != nil { t.Fatalf("read golden: %v (run -update)", err) }
            if got != string(want) {
                t.Errorf("mismatch (-want +got):\n%s", diff(string(want), got))
            }
        })
    }
}
```

Guidelines: store in `testdata/` (ignored by `go build`). Regenerate: `go test -run=TestRender_golden -update`. Commit golden files to VCS — diffs show exactly what changed. Ideal for serialisation, templates, CLI output, codegen.

## t.Setenv() (Go 1.17+)

```go
// BAD: manual env manipulation — easy to forget cleanup
func TestConfig_bad(t *testing.T) {
    old := os.Getenv("APP_MODE")
    os.Setenv("APP_MODE", "debug")
    defer os.Setenv("APP_MODE", old)
    cfg := LoadConfig()
    if cfg.Mode != "debug" {
        t.Errorf("Mode = %q, want %q", cfg.Mode, "debug")
    }
}

// GOOD: t.Setenv handles save/restore automatically
func TestConfig_good(t *testing.T) {
    t.Setenv("APP_MODE", "debug")
    cfg := LoadConfig()
    if cfg.Mode != "debug" {
        t.Errorf("Mode = %q, want %q", cfg.Mode, "debug")
    }
}
```

Notes: auto-restores previous value on test finish. Panics if combined with `t.Parallel()` (env vars are process-global). Prefer injecting config structs; use `t.Setenv` only when code directly reads `os.Getenv`.

## Coverage Commands

```bash
go test -cover ./...                                 # quick summary
go test -coverprofile=coverage.out ./...             # generate profile
go tool cover -html=coverage.out                     # visual HTML report
go tool cover -func=coverage.out                     # per-function breakdown
go test -race ./...                                  # race detection
go test -race -cover -count=3 ./...                  # combined reliability
```

Target: 80%+ coverage for business logic packages.

## See Also

- `go-concurrency-patterns.md` — race detection strategies, `t.Parallel()` with mutexes, and concurrent test patterns
- `go-api-http-checklist.md` — HTTP handler design conventions and status code expectations relevant to `httptest` assertions
