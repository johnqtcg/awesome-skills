# Go Observability Patterns

Reference patterns for writing correct, production-grade observability code in Go.
Load this file when writing fix recommendations in go-observability-review findings.

---

## 1. Structured Logging

### Library Selection

| Library | Go version | Best for |
|---------|-----------|---------|
| `log/slog` | 1.21+ | new services, stdlib alignment, zero dependencies |
| `go.uber.org/zap` | any | high-throughput, existing zap codebases |
| `github.com/rs/zerolog` | any | lowest allocation, zero-alloc hot paths |

**Rule**: choose one library per service. Never mix stdlib `log` with a structured logger.

### Correct slog usage (Go 1.21+)

```go
// Setup — create once at service entry, pass via context or dependency injection
logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{
    Level: slog.LevelInfo,
}))
slog.SetDefault(logger)

// In handlers — always use context variant
func (h *Handler) CreateOrder(ctx context.Context, req *CreateOrderRequest) error {
    slog.InfoContext(ctx, "creating order",
        slog.String("user_id", req.UserID),
        slog.Int("item_count", len(req.Items)),
    )
    // ...
}
```

**Anti-pattern (do not use)**:
```go
slog.Info("creating order", "user_id", req.UserID)  // BAD: loses context/trace_id
fmt.Printf("creating order for %s\n", req.UserID)    // BAD: unstructured
```

### Correct zap usage

```go
// Setup — build once, inject via constructor
logger, _ := zap.NewProduction()
defer logger.Sync()

// In handlers — extract from context or inject
func (h *Handler) CreateOrder(ctx context.Context, req *CreateOrderRequest) error {
    // Option A: inject logger as field
    h.logger.InfoContext(ctx, "creating order",
        zap.String("user_id", req.UserID),
        zap.String("trace_id", traceIDFromCtx(ctx)),
    )
    // Option B: use zap with context logger (zapctx or otelslog bridge)
}
```

**Anti-pattern**: `zap.L().Info(...)` — uses the global logger, loses request context.

---

## 2. OpenTelemetry Tracing

### Tracer initialisation (once at startup)

```go
func initTracer(ctx context.Context, serviceName string) (*sdktrace.TracerProvider, error) {
    exporter, err := otlptracehttp.New(ctx,
        otlptracehttp.WithEndpoint(os.Getenv("OTEL_EXPORTER_OTLP_ENDPOINT")),
    )
    if err != nil {
        return nil, fmt.Errorf("create exporter: %w", err)
    }
    tp := sdktrace.NewTracerProvider(
        sdktrace.WithBatcher(exporter),
        sdktrace.WithResource(resource.NewWithAttributes(
            semconv.SchemaURL,
            semconv.ServiceName(serviceName),
        )),
    )
    otel.SetTracerProvider(tp)
    otel.SetTextMapPropagator(propagation.NewCompositeTextMapPropagator(
        propagation.TraceContext{},
        propagation.Baggage{},
    ))
    return tp, nil
}
```

### Correct span pattern

```go
var tracer = otel.Tracer("github.com/myorg/myservice")

func (r *OrderRepo) GetByID(ctx context.Context, id string) (*Order, error) {
    ctx, span := tracer.Start(ctx, "OrderRepo.GetByID",
        trace.WithAttributes(attribute.String("order.id", id)),
    )
    defer span.End()  // ALWAYS defer End immediately after Start

    order, err := r.db.QueryContext(ctx, "SELECT * FROM orders WHERE id = $1", id)
    if err != nil {
        span.RecordError(err)
        span.SetStatus(codes.Error, err.Error())
        return nil, fmt.Errorf("query order: %w", err)
    }
    return order, nil
}
```

**Anti-patterns**:
```go
// BAD: span leak — End never called on error path
ctx, span := tracer.Start(ctx, "op")
if err != nil { return nil, err }  // span leaked
defer span.End()                   // unreachable

// BAD: error not recorded — span appears successful in traces
ctx, span := tracer.Start(ctx, "op")
defer span.End()
if err != nil { return nil, err }  // span has no error signal

// BAD: new background context — trace chain broken
ctx, span := tracer.Start(context.Background(), "op")  // orphaned span
```

### Context propagation rules

| Location | Correct context | Reason |
|----------|----------------|--------|
| HTTP handler entry | `r.Context()` | carries incoming trace parent |
| gRPC handler entry | the `ctx` parameter | propagated by gRPC interceptor |
| Background job startup | `context.Background()` ✓ | genuine chain origin |
| `main()` startup | `context.Background()` ✓ | genuine chain origin |
| Any other function | pass the incoming `ctx` | never create new Background mid-chain |

---

## 3. Prometheus Metrics

### Safe registration pattern (test-friendly)

```go
// BAD: default registry causes panic on duplicate registration in tests
var requestsTotal = prometheus.NewCounterVec(
    prometheus.CounterOpts{Name: "http_requests_total"},
    []string{"method", "status"},
)
func init() { prometheus.MustRegister(requestsTotal) }

// GOOD: custom registry, injected via constructor
type Metrics struct {
    RequestsTotal *prometheus.CounterVec
    LatencyHist   *prometheus.HistogramVec
}

func NewMetrics(reg prometheus.Registerer) *Metrics {
    m := &Metrics{
        RequestsTotal: prometheus.NewCounterVec(
            prometheus.CounterOpts{Name: "http_requests_total"},
            []string{"method", "status"},
        ),
        LatencyHist: prometheus.NewHistogramVec(
            prometheus.HistogramOpts{
                Name:    "http_request_duration_seconds",
                Buckets: prometheus.DefBuckets,
            },
            []string{"method"},
        ),
    }
    reg.MustRegister(m.RequestsTotal, m.LatencyHist)
    return m
}

// In tests: use prometheus.NewRegistry() → no global state pollution
```

### Cardinality safety rules

| Label value source | Risk | Rule |
|-------------------|------|------|
| Compile-time constant (`"GET"`, `"200"`) | None ✓ | safe to use directly |
| Bounded enum (status codes, HTTP methods) | Low ✓ | normalize to string constant |
| User-supplied string (name, email, URL path) | **High** ✗ | never use; map to `"unknown"` or omit |
| Error message string | **High** ✗ | use error type/code, not `.Error()` text |
| Request ID / trace ID | **High** ✗ | log it, do not use as label |

```go
// BAD: user_id as label → one time-series per user
counter.WithLabelValues(userID).Inc()

// GOOD: use bounded classification
status := classifyUser(userID)  // "premium" | "standard" | "trial"
counter.WithLabelValues(status).Inc()
```

### Histogram bucket selection

```go
// For HTTP latency (seconds):
Buckets: []float64{0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5}

// For DB query latency (milliseconds via seconds):
Buckets: []float64{0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1}
```

---

## 4. Sensitive Field Redaction

Fields that must NEVER appear as log values:

```go
// BAD
logger.Info("login attempt", slog.String("password", req.Password))
logger.Info("auth", zap.String("token", bearerToken))

// GOOD — log only non-sensitive identifiers
logger.InfoContext(ctx, "login attempt",
    slog.String("user_id", req.UserID),
    slog.String("ip", req.RemoteAddr),
)
// If you must log that a field was present:
logger.InfoContext(ctx, "auth", slog.Bool("token_present", bearerToken != ""))
```

Redaction list: `password`, `passwd`, `secret`, `token`, `api_key`, `apikey`,
`credential`, `private_key`, `access_key`, `refresh_token`, `session_id`.
