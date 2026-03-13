# Target Priority

Prioritize fuzz targets by expected bug-finding yield.

## Priority Tiers

### Tier 1: High Yield (fuzz first)

| Target Type | Why High Yield | Example |
|------------|---------------|---------|
| Parsers/decoders | Complex input grammar, many edge cases | JSON/XML/CSV parser, protocol decoder |
| Protocol handlers | State machine with untrusted input | HTTP request parser, gRPC frame handler |
| Compression/encoding | Amplification + round-trip invariants | gzip, base64, custom wire format |

### Tier 2: Medium Yield

| Target Type | Why Medium Yield | Example |
|------------|-----------------|---------|
| Round-trip encode/decode | Strong invariant (`decode(encode(x)) == x`) | Serializer, marshaler, codec |
| Validators/sanitizers | Must reject bad input without panic | Email validator, HTML sanitizer, path normalizer |
| State transitions | Strict invariants on valid states | Order state machine, workflow engine |

### Tier 3: Lower Yield (fuzz if time permits)

| Target Type | Why Lower Yield | Example |
|------------|----------------|---------|
| Differential (new vs ref) | Only useful during rewrites/migrations | Replacing a library, optimizing an algorithm |
| Formatters/renderers | Usually less crash-prone | Template renderer, log formatter |
| Configuration loaders | Limited input variety | YAML/TOML config parser (unless custom format) |

## De-Prioritize (usually not worth fuzzing)

- Thin wrappers with tiny input space (e.g., `func Add(a, b int) int`)
- DB/network-dominated paths (fuzz can't meaningfully explore)
- Heavily non-deterministic logic (random, time-dependent)
- Functions with no observable side effect or return value to assert on

## Concrete Go Examples — Tier Assignment

### Tier 1 Example: Custom Binary Decoder

```go
// Tier 1 — complex grammar, index/length calculations, crash-prone
func DecodeTLV(data []byte) ([]TLV, error) {
    var result []TLV
    offset := 0
    for offset < len(data) {
        if offset+3 > len(data) {
            return nil, ErrTruncated
        }
        tag := data[offset]
        length := int(binary.BigEndian.Uint16(data[offset+1 : offset+3]))
        offset += 3
        if offset+length > len(data) {
            return nil, ErrTruncated
        }
        result = append(result, TLV{Tag: tag, Value: data[offset : offset+length]})
        offset += length
    }
    return result, nil
}
// Fuzz mode: Parser robustness (Template A)
// Oracle: no panic + valid TLV structure
// Priority: HIGH — offset arithmetic is classic off-by-one territory
```

### Tier 1 Example: HTTP Header Parser

```go
// Tier 1 — untrusted input, complex grammar with edge cases
func ParseHeaders(raw []byte) (map[string][]string, error) {
    headers := make(map[string][]string)
    for _, line := range bytes.Split(raw, []byte("\r\n")) {
        idx := bytes.IndexByte(line, ':')
        if idx < 0 {
            continue
        }
        key := string(bytes.TrimSpace(line[:idx]))
        val := string(bytes.TrimSpace(line[idx+1:]))
        headers[key] = append(headers[key], val)
    }
    return headers, nil
}
// Fuzz mode: Parser robustness
// Oracle: no panic + keys are non-empty strings
// Priority: HIGH — split/index operations on untrusted bytes
```

### Tier 2 Example: JSON Codec Round-Trip

```go
// Tier 2 — strong invariant, moderate complexity
type Event struct {
    Type    string    `json:"type"`
    Payload string    `json:"payload"`
    SeqNo   int64     `json:"seq_no"`
}

func MarshalEvent(e Event) ([]byte, error) { return json.Marshal(e) }
func UnmarshalEvent(data []byte) (Event, error) {
    var e Event
    err := json.Unmarshal(data, &e)
    return e, err
}
// Fuzz mode: Round-trip (Template B)
// Oracle: UnmarshalEvent(MarshalEvent(e)) == e
// Priority: MEDIUM — json.Marshal is well-tested, but custom fields may have edge cases
```

### Tier 2 Example: Input Validator

```go
// Tier 2 — must never panic on any input
func ValidateEmail(email string) error {
    if len(email) > 254 {
        return ErrTooLong
    }
    parts := strings.SplitN(email, "@", 2)
    if len(parts) != 2 || parts[0] == "" || parts[1] == "" {
        return ErrInvalidFormat
    }
    if !strings.Contains(parts[1], ".") {
        return ErrNoDomain
    }
    return nil
}
// Fuzz mode: Parser robustness (no-panic + domain constraint)
// Oracle: no panic + valid emails pass, malformed ones return error
// Priority: MEDIUM — string operations on untrusted input
```

### De-Prioritize Example: Simple Wrapper

```go
// NOT worth fuzzing — trivial delegation with no logic
func GetUserName(u *User) string {
    if u == nil {
        return ""
    }
    return u.Name
}
// No meaningful input space, one nil check.
// → Unit test the nil case and move on.
```

### De-Prioritize Example: DB-Dependent Path

```go
// NOT worth fuzzing — result depends entirely on DB state
func GetOrderTotal(ctx context.Context, db *sql.DB, orderID string) (float64, error) {
    var total float64
    err := db.QueryRowContext(ctx, "SELECT total FROM orders WHERE id = ?", orderID).Scan(&total)
    return total, err
}
// Fuzz cannot explore meaningful paths without a live DB.
// → Fuzz the SQL builder or validation layer instead.
```

## Multi-Target Selection

When a package has multiple fuzz candidates:
1. Start with Tier 1 targets.
2. After initial fuzz run, check coverage report for uncovered paths.
3. Add Tier 2 targets only if they cover significantly new code paths.
4. Skip Tier 3 unless specifically requested or during dedicated fuzz sprints.

## Quick Decision Flowchart

```
Is the function a parser/decoder/protocol handler?
  → YES: Tier 1 — fuzz immediately
  → NO: Does it have a round-trip or strict invariant?
    → YES: Tier 2 — fuzz after Tier 1 targets
    → NO: Is it a rewrite with a reference implementation?
      → YES: Tier 3 — differential fuzz if time permits
      → NO: Is it a thin wrapper / DB-dependent / trivial?
        → YES: De-prioritize — don't fuzz
        → NO: Evaluate on a case-by-case basis
```
