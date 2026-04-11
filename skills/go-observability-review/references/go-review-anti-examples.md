# Observability Review — Anti-Examples (False-Positive Suppression)

Apply these rules in the Anti-Example Suppression Gate BEFORE reporting any finding.
Each rule describes a pattern that looks like a violation but is NOT.

---

## AE-1: fmt.Println in test files or main.go — do not report

```go
// NOT a finding — test output / startup diagnostics are expected
// _test.go file:
fmt.Println("=== integration test starting ===")

// main.go:
fmt.Printf("server starting on :%s\n", port)
```

**Rule**: Item 1 (`fmt.Print*`) applies only to non-test, non-main application code.
If the offending `fmt.Print` is in `*_test.go` or `main.go`, suppress and note:
`Suppressed: fmt.Println in main.go/test file — startup/test output, not application logging.`

---

## AE-2: context.Background() at service entry points — correct usage

```go
// NOT a finding — HTTP handler is a legitimate trace chain origin
func (h *Handler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
    ctx := r.Context()  // this IS the trace root; r.Context() already has the propagated parent
    // ...
}

// NOT a finding — background job starter
func main() {
    ctx, cancel := context.WithCancel(context.Background())  // ✓ correct origin
    defer cancel()
    go runWorker(ctx)
}

// NOT a finding — test setup
func TestFoo(t *testing.T) {
    ctx := context.Background()  // ✓ correct for test isolation
}
```

**Rule**: `context.Background()` in `main()`, `TestXxx()`, `init()`, `http.Handler` entry
(where `r.Context()` is used immediately after), or background job starter functions is CORRECT.
Only report Item 4 when `context.Background()` is created mid-call-chain in a function that
ALREADY has an incoming `ctx` parameter that should have been passed instead.

---

## AE-3: log.Fatal in package main — acceptable

```go
// NOT a finding — main is the correct place for fatal errors
func main() {
    cfg, err := config.Load()
    if err != nil {
        log.Fatalf("load config: %v", err)  // ✓ no deferred work yet
    }
}
```

**Rule**: Item 9 (`log.Fatal outside main`) applies only to non-main packages.
`log.Fatal*` in `package main` before any deferred resources are established is acceptable.
If in `package main` after significant setup (e.g., after `defer db.Close()`), downgrade to Medium
with note: "deferred cleanup will not run."

---

## AE-4: Prometheus constant labels — not a cardinality risk

```go
// NOT a finding — all label values are compile-time constants
counter.WithLabelValues("GET", "200").Inc()
counter.WithLabelValues("POST", "404").Inc()

// NOT a finding — bounded enum from a small constant set
func statusClass(code int) string {
    switch { case code < 400: return "2xx"; case code < 500: return "4xx"; default: return "5xx" }
}
counter.WithLabelValues(statusClass(resp.StatusCode)).Inc()
```

**Rule**: Item 7 (`WithLabelValues with variable`) requires that the variable is
unbounded (user-supplied, request-derived, or error text). A function that maps
an input to a finite constant set is NOT a cardinality risk. Only report when
the label value is directly from user input, URL path parameters, error messages,
request/user IDs, or other unbounded sources.

---

## AE-5: Logger field key contains "token" as a substring in a non-sensitive context

```go
// NOT a finding — "token_count" is not a sensitive credential field
logger.Info("tokenizer result", slog.Int("token_count", count))

// NOT a finding — "next_page_token" is a pagination cursor
logger.Info("list response", slog.String("next_page_token", resp.NextPageToken))
```

**Rule**: Item 8 (sensitive field in log) requires the field KEY to be one of the exact
sensitive identifiers (`password`, `token`, `secret`, `credential`, `api_key`, `apikey`).
Field keys that merely contain these words as substrings in a non-credential context
(e.g., `token_count`, `csrf_token_valid`, `next_page_token`) should be evaluated
semantically. Only report when the VALUE being logged is an actual credential or secret.

---

## AE-6: zap.Error(err) in simple, leaf-level functions with no request context

```go
// Borderline — a utility function with no request context available
func validateConfig(cfg Config) error {
    if cfg.Port == 0 {
        zap.L().Error("invalid config", zap.Error(err))  // no ctx available here
        return errors.New("port required")
    }
}
```

**Rule**: Item 11 (`zap.Error alone, missing correlation fields`) is Medium severity.
If the function is a pure utility/validation function with no incoming `ctx` parameter
and no request lifecycle, the absence of correlation fields is a design limitation,
not a defect. Downgrade from Medium to a non-finding with note in Suppressed Items:
`Function has no request context in scope — correlation fields not applicable here.`
Only report when a `ctx` parameter EXISTS in the function signature but is not used
to derive correlation fields.
