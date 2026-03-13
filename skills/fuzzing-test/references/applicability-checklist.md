# Applicability Checklist

Use before writing any fuzz test. Mark each item `Pass` / `Fail`.

## Mandatory Checks

| # | Check | Pass Criteria | Fail Example |
|---|-------|--------------|--------------|
| 1 | Meaningful input space | Target behavior varies significantly with input | Config loader that reads one fixed file |
| 2 | Fuzz-compatible types | Can be driven by `[]byte`, `string`, `int`, `float`, `bool`, or struct-via-`[]byte` deserialize | Requires `chan`, `func`, or live connection as input |
| 3 | Clear oracle/invariant | At least one: no-panic, round-trip, differential, domain constraint | "It should work correctly" with no testable assertion |
| 4 | Deterministic/local | Same input → same output (or bounded non-determinism) | Result depends on DB state, wall clock, or random seed |
| 5 | Fast per-call | <1ms per call for high-iteration fuzzing | Each call makes HTTP request or heavy disk I/O |

## Hard Stop Rules

- If `2` fails: **stop** — Go fuzz cannot drive this target effectively.
- If `3` fails: **stop** — no oracle means no way to detect bugs.
- If `1` fails: **stop** — fuzzing adds no value over simple unit tests.

## Soft Warnings (proceed with caution)

- If `4` fails: can sometimes work with mocks/stubs, but flag as higher risk.
- If `5` fails: classify as `High` cost, restrict to nightly runs with strict `-fuzztime`.

## Concrete Judgment Examples

### Suitable for Fuzzing (Verdict: PASS)

#### Example A: JSON Parser

```go
// ✅ Pass all 5 checks
func ParseConfig(data []byte) (*Config, error) {
    var cfg Config
    if err := json.Unmarshal(data, &cfg); err != nil {
        return nil, err
    }
    if cfg.Port < 1 || cfg.Port > 65535 {
        return nil, fmt.Errorf("invalid port: %d", cfg.Port)
    }
    return &cfg, nil
}
// Check 1: ✅ Rich input space (arbitrary JSON bytes)
// Check 2: ✅ []byte input — native fuzz type
// Check 3: ✅ Oracle: no panic + domain constraint (port range)
// Check 4: ✅ Pure function, deterministic
// Check 5: ✅ Fast, no I/O
```

#### Example B: Custom Wire Protocol Decoder

```go
// ✅ Tier 1 fuzz target — complex grammar, crash-prone
func DecodeFrame(data []byte) (*Frame, error) {
    if len(data) < 4 {
        return nil, ErrTooShort
    }
    length := binary.BigEndian.Uint32(data[:4])
    if int(length) > len(data)-4 {
        return nil, ErrTruncated
    }
    return parsePayload(data[4 : 4+length])
}
// Check 1: ✅ Binary protocol — huge input space with length/offset/type fields
// Check 2: ✅ []byte
// Check 3: ✅ Oracle: no panic + valid frame structure
// Check 4: ✅ Pure, no external state
// Check 5: ✅ Fast per call
```

#### Example C: Round-Trip Codec

```go
// ✅ Strong invariant: decode(encode(x)) == x
func MarshalEvent(e Event) ([]byte, error)  { ... }
func UnmarshalEvent(data []byte) (Event, error) { ... }
// Check 1: ✅ Struct fields + encoding → rich input
// Check 2: ✅ Use struct-via-[]byte (json.Marshal seeds)
// Check 3: ✅ Oracle: round-trip equality
// Check 4: ✅ Deterministic
// Check 5: ✅ Fast
```

### NOT Suitable for Fuzzing (Verdict: FAIL)

#### Example D: Trivial Arithmetic

```go
// ❌ Check 1 FAIL — trivial input space
func Add(a, b int) int {
    return a + b
}
// Input space is vast but behavior is trivially correct.
// Fuzz will never find a bug that a simple unit test wouldn't.
// → Use table-driven unit tests instead.
```

#### Example E: Database-Dependent Business Logic

```go
// ❌ Check 4 FAIL — depends on live DB state
func CreateOrder(ctx context.Context, db *sql.DB, req OrderRequest) (*Order, error) {
    user, err := db.QueryRow("SELECT ...").Scan(...)
    if err != nil {
        return nil, err
    }
    // ... business logic depends on DB row values
}
// Result varies with DB state — non-deterministic, can't reproduce.
// → Fuzz the pure validation/parsing layer: ValidateOrderRequest(req)
// → Use integration tests for the DB-dependent logic.
```

#### Example F: No Testable Oracle

```go
// ❌ Check 3 FAIL — no way to assert correctness
func LogRequest(r *http.Request) {
    log.Printf("method=%s path=%s", r.Method, r.URL.Path)
}
// No return value, no side effect to check, no invariant.
// Even if it panics, that's a trivial nil-check fix, not a fuzz-worthy target.
// → Skip fuzzing. Code review + unit test for nil input is sufficient.
```

#### Example G: Slow External Call

```go
// ❌ Check 5 FAIL — HTTP call per iteration
func FetchAndParse(url string) (*Result, error) {
    resp, err := http.Get(url) // 50-200ms per call
    if err != nil {
        return nil, err
    }
    defer resp.Body.Close()
    return Parse(resp.Body)
}
// At 100ms/call, fuzzer gets only 10 execs/sec — useless.
// → Fuzz Parse(io.Reader) directly with in-memory readers.
// → Use integration tests for the full FetchAndParse path.
```

### Borderline Cases (Soft Warning → Conditional Pass)

#### Example H: Non-Deterministic but Stubbable

```go
// ⚠️ Check 4 soft fail — depends on time.Now()
func GenerateToken(userID string) Token {
    return Token{
        UserID:    userID,
        ExpiresAt: time.Now().Add(24 * time.Hour),
        Random:    rand.Int63(),
    }
}
// Can fuzz if you inject a clock + deterministic random source.
// Without injection: flaky, skip.
// → Refactor to accept a clock interface, then fuzz the pure logic.
```

## Alternative Strategies When Fuzzing is Not Suitable

| Failed Check | Alternative |
|-------------|-------------|
| No fuzz-compatible types | Property-based testing with `rapid`/`gopter` (custom generators) |
| No clear oracle | Manual code review + integration tests with known edge cases |
| Non-deterministic | Integration tests with controlled test fixtures |
| Too slow | Table-driven unit tests with hand-picked boundary values |
| Trivial input space | Exhaustive unit tests covering all cases |
