---
name: go-observability-review
description: >
  Review Go code for observability gaps: missing structured logging, broken trace
  context propagation, Prometheus cardinality explosions, span lifecycle errors,
  and sensitive fields in logs. Dispatched by go-review-lead as a vertical reviewer.
  Also trigger directly when the user says "review my logging", "check my tracing",
  "observability review", or "are my metrics correct".
allowed-tools: Read, Grep, Glob
---

# Go Observability Review

## Purpose

Find observability defects in Go code: logging anti-patterns, trace context breaks,
metrics cardinality risks, and span lifecycle errors. This skill covers one dimension only —
do not report security, concurrency, or error-handling issues outside observability scope.

## When To Use
- Any Go change that imports `go.uber.org/zap`, `log/slog`, `go.opentelemetry.io/`, `github.com/prometheus/client_golang`, `github.com/rs/zerolog`
- Diffs adding span creation, metric registration, or logging calls
- Files under `observability/`, `telemetry/`, `instrumentation/`, `metrics/`, `tracing/`

## When NOT To Use
- Non-Go code
- Changes with no logging/tracing/metrics imports or patterns
- Security review of authentication logic → go-security-reviewer

## Mandatory Gates

### 1) Execution Integrity Gate
Run all 12 grep-gated checklist items BEFORE any semantic analysis. Report the audit line:
`Grep pre-scan: X/12 items hit, Z confirmed as findings (2 semantic-only)`

### 2) Anti-Example Suppression Gate
BEFORE reporting any finding, check against the false-positive rules in
`references/go-review-anti-examples.md`. Apply all matching suppression rules.
Suppressed items must appear in the Suppressed Items section with reason.

### 3) Generated Code Exclusion Gate
Skip these files entirely — do not grep or analyze:
`*.pb.go`, `*_gen.go`, `mock_*.go`, `wire_gen.go`, `*_string.go`, any file starting with `// Code generated`

## Grep-Gated Execution Protocol

For each grep-gated item: run the grep, record HIT or MISS.
- **HIT** → proceed to semantic confirmation before reporting
- **MISS** → mark NOT FOUND, move to next item (no semantic analysis needed)

Never skip a grep step because an earlier item already found issues.

```bash
# Item 1: fmt.Print* as logging (exclude test files)
grep -rn 'fmt\.Print' --include='*.go' --exclude='*_test.go' <files>

# Item 2: stdlib log (unstructured, no levels)
grep -rn 'log\.Print\|log\.Println\|log\.Printf\|log\.Fatalf\|log\.Fatalln\|log\.Fatal\b' <files>

# Item 3: logger without context propagation
grep -rn 'zap\.L()\|zap\.S()\|slog\.Info(\|slog\.Warn(\|slog\.Error(\|slog\.Debug(' <files>

# Item 4: context.Background()/TODO() in function bodies (potential chain break)
grep -rn 'context\.Background()\|context\.TODO()' <files>

# Item 5: tracer.Start without nearby defer span.End()
grep -rn '\.Start(ctx,' <files>

# Item 6: span.End() without RecordError or SetStatus
grep -rn 'span\.End()' <files>

# Item 7: Prometheus WithLabelValues (check for variable args)
grep -rn 'WithLabelValues(' <files>

# Item 8: sensitive field names in log calls
grep -rn '"password"\|"passwd"\|"token"\|"secret"\|"credential"\|"api_key"\|"apikey"' <files>

# Item 9: log.Fatal outside main package
grep -rn 'log\.Fatal\b\|log\.Fatalln\|log\.Fatalf' --include='*.go' <files>

# Item 10: HTTP handler logging without request context
grep -rn 'func.*http\.ResponseWriter.*\*http\.Request' <files>

# Item 11: zap.Error(err) as sole field (missing correlation)
grep -rn 'zap\.Error(err)' <files>

# Item 12: Prometheus metric registered against default registry
grep -rn 'prometheus\.MustRegister\|prometheus\.Register(' <files>
```

## Observability Checklist

**Items 1-12 are grep-gated. Items 13-14 are semantic-only.**

**[1] fmt.Print\* used for logging** (Medium)
Signal: `fmt.Print` in non-test Go files.
Confirm: the output is application logging (not debug output, not deliberate stdout).
Fix: replace with structured logger (`slog.InfoContext(ctx, ...)` or `logger.Info(...)`).

**[2] stdlib `log` package (no levels, no structure)** (Medium)
Signal: `log.Print*` in any file.
Confirm: not in a test helper or `main()` startup message.
Fix: replace with `slog` (Go 1.21+) or `zap`/`zerolog`.

**[3] Logger called without context — loses trace_id correlation** (High)
Signal: `zap.L()`, `zap.S()`, or `slog.Info(`/`slog.Error(`/`slog.Warn(` with no `ctx` argument.
Confirm: a request context exists in scope; this is not an init or background task.
Fix: use `logger.InfoContext(ctx, ...)` or pass ctx to `zap.L().With(zap.String("trace_id", traceID))`.

**[4] context.Background()/TODO() breaks trace propagation chain** (High)
Signal: `context.Background()` or `context.TODO()` inside a function body.
Confirm via suppression gate: NOT at service entry point (HTTP handler root, `main`, job starter).
If confirmed mid-chain: parent context is discarded; downstream spans become orphaned.
Fix: pass the incoming `ctx` parameter through; use `context.Background()` only at chain origins.

**[5] tracer.Start() without defer span.End() — span leak** (High)
Signal: `\.Start(ctx,` in a function body.
Confirm: `defer span.End()` does NOT appear in the same function scope.
Fix: add `defer span.End()` immediately after `ctx, span := tracer.Start(...)`.

**[6] Error not recorded on span — span shows no error signal** (Medium)
Signal: `span.End()` present in function.
Confirm: neither `span.RecordError(err)` nor `span.SetStatus(codes.Error, ...)` appears before the End call in an error return path.
Fix: call `span.RecordError(err); span.SetStatus(codes.Error, err.Error())` before returning the error.

**[7] Prometheus label value from variable — cardinality explosion risk** (High)
Signal: `WithLabelValues(` call.
Confirm: at least one argument is a variable (not a compile-time constant string literal).
Assess: if the variable is user-supplied (e.g., URL path, user ID, error message), it is High; if bounded enum, downgrade to Medium.
Fix: normalize dynamic values to a bounded set before using as labels; never use user input directly.

**[8] Sensitive field name in log call** (High)
Signal: `"password"`, `"token"`, `"secret"`, `"credential"`, `"api_key"` as a string literal (log field key).
Confirm: the literal is used as a key in a structured log call, not in a comment or test assertion.
Fix: redact or omit the field; log only non-sensitive identifiers (e.g., user ID, not password).

**[9] log.Fatal / log.Fatalln / log.Fatalf outside main package** (Medium)
Signal: `log.Fatal` in non-main-package files.
Confirm: package declaration is NOT `package main`.
Impact: calls `os.Exit(1)` immediately, bypassing deferred cleanup, graceful shutdown hooks, and test teardown.
Fix: return an error; let the caller (ultimately main) decide on exit.

**[10] HTTP handler logging without request context** (Medium)
Signal: handler function with `http.ResponseWriter, *http.Request` signature.
Confirm: a logger call exists in the handler body but does NOT use `r.Context()` to extract the context or trace ID.
Fix: extract logger from `r.Context()` or call `logger.InfoContext(r.Context(), ...)`.

**[11] Error logged with no correlation fields** (Medium)
Signal: `zap.Error(err)` as the sole field in a zap log call.
Confirm: no other fields (request ID, trace ID, user ID) accompany the error.
Fix: add at least one correlation field: `zap.String("trace_id", span.SpanContext().TraceID().String())`.

**[12] Prometheus metric registered against default registry** (Medium)
Signal: `prometheus.MustRegister(...)` or `prometheus.Register(...)` (default registry).
Confirm: metric is a package-level `var`, registered at init time.
Risk: if tests import this package more than once across test binaries, duplicate registration panics.
Fix: use a custom `prometheus.NewRegistry()` injected via constructor; or wrap with `prometheus.AlreadyRegisteredError` check.

**[13] Critical code path lacks span coverage** *(semantic-only)* (Medium)
Assess: does the function make outbound DB calls, HTTP calls, or queue publishes without wrapping in an OTel span?
Signal of concern: function calls `db.QueryContext`, `http.Do`, or MQ publish with no `tracer.Start` in the same scope.

**[14] SLO-relevant operation lacks request metrics** *(semantic-only)* (Medium)
Assess: does the function handle a user-facing request path without incrementing a request counter and observing latency?
Signal of concern: HTTP handler or RPC handler with no `Counter.Inc()` or `Histogram.Observe()`.

## Severity Rubric

**High**: data exposure (sensitive field logged), production metric system corruption (cardinality explosion), silent trace orphaning (context break), span leak.
**Medium**: degraded debuggability (missing correlation, stdlib log), test reliability risk (default registry), graceful-shutdown bypass (log.Fatal).

## Evidence Rules

- Cite the exact file path and line number.
- Quote the offending line verbatim.
- For High findings, describe the attacker/operator impact (e.g., "trace_id absent from all downstream logs for this request").
- Do NOT speculate about intent. Report only what the code demonstrates.

## Output Format

```
[High|Medium] Short Title

  ID:             OBS-NNN
  Location:       path/to/file.go:line
  Impact:         production / debuggability / security impact
  Evidence:       verbatim offending line
  Recommendation: concrete fix with example
  Action:         must-fix | follow-up
```

Sections:
- **Findings** — confirmed items, sorted High → Medium
- **Suppressed Items** — items matched by anti-example gate (include matched rule + residual risk)
- **Execution Status** — `Grep pre-scan: X/12 items hit, Z confirmed as findings (2 semantic-only)` + references loaded

## Load References Selectively

| File | Load when |
|------|-----------|
| `references/go-observability-patterns.md` | Writing fix recommendations; need correct slog/OTel/Prometheus patterns |
| `references/go-review-anti-examples.md` | Evaluating any finding for suppression; always load before reporting |

## Review Discipline

- Report observability dimension only. Do not cross into security (injection), error-handling (unwrapped errors), or performance (N+1) — those belong to their respective vertical skills.
- Execute ALL 14 checklist items regardless of how many High findings have already been identified.
- Prefer precision over recall: a suppressed finding with documented residual risk is better than a speculative High finding.
