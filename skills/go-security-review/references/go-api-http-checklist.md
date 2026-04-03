# Go API & HTTP Checklist

Deep-dive reference for the **API & HTTP (High)** category in SKILL.md step 5.

## Request/Response Body Handling

### Server Handlers (`http.Request.Body`)

```go
// BAD: unbounded read and ignored error
func handler(w http.ResponseWriter, r *http.Request) {
    data, _ := io.ReadAll(r.Body)
    _ = data
}

// GOOD: bounded read and explicit error handling
// NOTE: in net/http server handlers, request body lifecycle is managed by server internals.
func handler(w http.ResponseWriter, r *http.Request) {
    data, err := io.ReadAll(io.LimitReader(r.Body, 1<<20)) // 1MB limit
    if err != nil {
        http.Error(w, "bad request", http.StatusBadRequest)
        return
    }
    _ = data
}
```

Checks:
- Use `io.LimitReader` (or equivalent) to prevent unbounded memory use.
- Handle body read errors explicitly.
- Do not treat missing `r.Body.Close()` in server handlers as an automatic defect.

### Outbound Clients (`http.Response.Body`)

```go
// BAD: response body not closed
resp, err := http.DefaultClient.Do(req)
if err != nil {
    return err
}
data, err := io.ReadAll(resp.Body) // leak if not closed

// GOOD: close response body on all paths
resp, err := http.DefaultClient.Do(req)
if err != nil {
    return err
}
defer resp.Body.Close()
data, err := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
if err != nil {
    return fmt.Errorf("read response body: %w", err)
}
_ = data
```

Checks:
- `resp.Body.Close()` is called on all success/error paths after `Do`.
- Read size is bounded when payload can be large or untrusted.

## HTTP Status Codes

| Situation | Code | Common Mistake |
|-----------|------|----------------|
| Created a resource | `201 Created` | Using `200 OK` |
| Accepted async work | `202 Accepted` | Using `200 OK` |
| No content to return | `204 No Content` | Using `200 OK` with empty body |
| Bad input | `400 Bad Request` | Using `500` |
| Not authenticated | `401 Unauthorized` | Confusing with `403` |
| Not authorized | `403 Forbidden` | Using `401` |
| Resource not found | `404 Not Found` | Using `400` or `500` |
| Conflict (duplicate) | `409 Conflict` | Using `400` |
| Rate limited | `429 Too Many Requests` | Using `503` |

## Response Content-Type

```go
// BAD: Content-Type not set (browser may sniff)
func handler(w http.ResponseWriter, r *http.Request) {
    json.NewEncoder(w).Encode(resp)
}

// GOOD: set Content-Type before writing body
func handler(w http.ResponseWriter, r *http.Request) {
    w.Header().Set("Content-Type", "application/json")
    w.WriteHeader(http.StatusOK)
    json.NewEncoder(w).Encode(resp)
}
```

Important: `w.Header().Set()` must be called before `w.WriteHeader()` or first `w.Write()`.

## Middleware Ordering

Correct order (outermost to innermost):

```
1. Recovery (panic handler)
2. Request ID / correlation
3. Logging / metrics
4. Rate limiting
5. CORS
6. Authentication
7. Authorization
8. Request validation
9. Business handler
```

Review checks:
- Auth middleware runs before business handlers (not after)
- Recovery middleware is outermost (catches panics from all layers)
- CORS runs before auth (preflight requests don't carry credentials)
- Rate limiting runs before expensive operations

## Graceful Shutdown

```go
// BAD: abrupt shutdown loses in-flight requests
log.Fatal(http.ListenAndServe(":8080", handler))

// GOOD: graceful shutdown with context
srv := &http.Server{
    Addr:         ":8080",
    Handler:      handler,
    ReadTimeout:  10 * time.Second,
    WriteTimeout: 30 * time.Second,
    IdleTimeout:  60 * time.Second,
}

go func() {
    if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
        log.Fatalf("listen: %v", err)
    }
}()

quit := make(chan os.Signal, 1)
signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
<-quit

ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
defer cancel()
if err := srv.Shutdown(ctx); err != nil {
    log.Fatalf("shutdown: %v", err)
}
```

Checks:
- `ReadTimeout` / `WriteTimeout` / `IdleTimeout` set (prevent slowloris)
- `Shutdown()` used instead of `Close()`
- Shutdown timeout is bounded
- Background workers also respect shutdown signal

## API Backward Compatibility

Breaking changes to watch for:
- Removing or renaming a JSON field (clients break on deserialization)
- Changing field type (e.g., `string` to `int`)
- Removing an endpoint or changing its path
- Changing HTTP method (`GET` to `POST`)
- Adding required request fields without default
- Changing error response shape

Non-breaking (safe):
- Adding optional request fields with defaults
- Adding new response fields
- Adding new endpoints
- Adding new enum values (if clients handle unknown values)

Review pattern:
```go
// Check struct tags for removed/renamed fields
type UserResponse struct {
    ID    string `json:"id"`
    Name  string `json:"name"`
    // Email string `json:"email"` // REMOVED — breaking change!
}
```

## Timeout and Cancellation

```go
// BAD: no timeout on outgoing HTTP call
resp, err := http.Get(url)

// GOOD: context with timeout
ctx, cancel := context.WithTimeout(r.Context(), 5*time.Second)
defer cancel()

req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
if err != nil {
    return err
}
resp, err := client.Do(req)
```

Checks:
- All outgoing HTTP/gRPC calls have context with timeout
- Database queries use context
- Long-running operations check `ctx.Done()`

## Response Body Leak

```go
// BAD: response body not drained/closed (connection not reused)
resp, err := client.Do(req)
if err != nil {
    return err
}
if resp.StatusCode != 200 {
    return fmt.Errorf("bad status: %d", resp.StatusCode)
    // resp.Body not closed!
}

// GOOD: always close, drain for connection reuse
resp, err := client.Do(req)
if err != nil {
    return err
}
defer resp.Body.Close()

if resp.StatusCode != 200 {
    io.Copy(io.Discard, resp.Body) // drain for connection reuse
    return fmt.Errorf("bad status: %d", resp.StatusCode)
}
```

---

## gRPC Interceptor Chain Order

```go
// BAD: auth interceptor runs after logging — unauthenticated requests
// are logged with potentially sensitive metadata before rejection.
srv := grpc.NewServer(
    grpc.ChainUnaryInterceptor(
        loggingInterceptor,   // logs request including auth headers
        authInterceptor,      // rejects unauthenticated — too late, already logged
        rateLimitInterceptor,
    ),
)

// GOOD: recovery outermost, auth before logging sees business data
srv := grpc.NewServer(
    grpc.ChainUnaryInterceptor(
        recoveryInterceptor,   // 1. catch panics from any layer
        loggingInterceptor,    // 2. structured request/response log
        authInterceptor,       // 3. reject unauthenticated early
        rateLimitInterceptor,  // 4. shed load before heavy work
        // business handler is the final UnaryHandler
    ),
)
```

Checks:
- `recoveryInterceptor` is first (outermost) so panics in any interceptor are caught.
- `authInterceptor` runs before business logic; unauthenticated requests never reach handlers.
- Sensitive request payloads are not logged before auth validates the caller.
- Use `grpc.ChainUnaryInterceptor()` (and `grpc.ChainStreamInterceptor()` for streams) instead of nesting manually.

## gRPC Metadata Propagation

```go
// BAD: interceptor creates a fresh context, dropping incoming metadata
func badInterceptor(
    ctx context.Context,
    req any,
    info *grpc.UnaryServerInfo,
    handler grpc.UnaryHandler,
) (any, error) {
    newCtx := context.Background() // incoming metadata lost
    return handler(newCtx, req)
}

// GOOD: extract metadata from incoming context and propagate
func goodInterceptor(
    ctx context.Context,
    req any,
    info *grpc.UnaryServerInfo,
    handler grpc.UnaryHandler,
) (any, error) {
    md, ok := metadata.FromIncomingContext(ctx)
    if ok {
        // Forward selected headers to outbound calls
        ctx = metadata.NewOutgoingContext(ctx, md)
    }
    return handler(ctx, req)
}
```

Checks:
- Interceptors never replace ctx with `context.Background()` or `context.TODO()`.
- `metadata.FromIncomingContext` is used to read client-supplied metadata.
- When calling downstream gRPC services, relevant metadata is forwarded via `metadata.NewOutgoingContext` or `metadata.AppendToOutgoingContext`.
- Trace/correlation IDs survive the full call chain.

## gRPC Deadline Propagation

```go
// BAD: outbound call without deadline — can hang forever if downstream is stuck
func (s *Server) GetOrder(ctx context.Context, req *pb.GetOrderReq) (*pb.Order, error) {
    // ctx may already carry a deadline from the client, but if not, this blocks indefinitely.
    resp, err := s.inventoryClient.CheckStock(ctx, &pb.StockReq{ItemID: req.ItemId})
    if err != nil {
        return nil, err
    }
    return buildOrder(resp), nil
}

// GOOD: derive deadline from incoming context or set an explicit timeout;
// use WaitForReady(false) so the call fails fast when the backend is unavailable.
func (s *Server) GetOrder(ctx context.Context, req *pb.GetOrderReq) (*pb.Order, error) {
    callCtx := ctx // prefer incoming deadline when present
    if _, ok := ctx.Deadline(); !ok {
        var cancel context.CancelFunc
        callCtx, cancel = context.WithTimeout(ctx, 3*time.Second)
        defer cancel()
    }

    resp, err := s.inventoryClient.CheckStock(
        callCtx,
        &pb.StockReq{ItemID: req.ItemId},
        grpc.WaitForReady(false), // fail fast if backend not ready
    )
    if err != nil {
        return nil, status.Errorf(codes.Internal, "check stock: %v", err)
    }
    return buildOrder(resp), nil
}
```

Checks:
- Every outbound gRPC call has a deadline (either inherited from context or explicitly set).
- `context.WithTimeout` / `context.WithDeadline` is used, and the `cancel` func is deferred.
- `grpc.WaitForReady(false)` is used when fail-fast behavior is desired (avoid queuing when backend is down).
- Cascading timeouts are shorter than the parent deadline to leave room for local processing.

## gRPC Stream Lifecycle

```go
// BAD: Recv() error not checked for io.EOF — loop exits on any error
// and may treat normal stream completion as a failure.
func (s *Server) StreamOrders(req *pb.StreamReq, stream pb.OrderService_StreamOrdersServer) error {
    for {
        msg, err := someSource.Recv()
        if err != nil {
            return err // io.EOF here means success, not failure
        }
        if err := stream.Send(msg); err != nil {
            return err
        }
    }
}

// GOOD: check for io.EOF to detect normal end-of-stream;
// also check context cancellation for client-initiated teardown.
func (s *Server) ProcessStream(stream pb.OrderService_ProcessStreamServer) error {
    for {
        msg, err := stream.Recv()
        if errors.Is(err, io.EOF) {
            return stream.SendAndClose(&pb.Summary{Count: count})
        }
        if err != nil {
            if st, ok := status.FromError(err); ok && st.Code() == codes.Canceled {
                return nil // client cancelled — not an error
            }
            return status.Errorf(codes.Internal, "recv: %v", err)
        }

        if err := stream.Context().Err(); err != nil {
            return status.FromContextError(err).Err()
        }

        // process msg …
        count++
    }
}
```

Checks:
- `io.EOF` from `Recv()` is handled as normal stream completion, not an error.
- Client-side cancellation (`codes.Canceled`) is distinguished from real failures.
- `stream.Context().Err()` is checked in long-running loops.
- `SendAndClose` is used for client-streaming RPCs; `Send` for server-streaming.

## gRPC Error Handling

```go
// BAD: returning raw Go error — client receives codes.Unknown with opaque message
func (s *Server) GetUser(ctx context.Context, req *pb.GetUserReq) (*pb.User, error) {
    u, err := s.repo.Find(req.Id)
    if err != nil {
        return nil, fmt.Errorf("find user: %w", err) // codes.Unknown on the wire
    }
    return toProto(u), nil
}

// GOOD: use status.Errorf with appropriate gRPC status codes
func (s *Server) GetUser(ctx context.Context, req *pb.GetUserReq) (*pb.User, error) {
    if req.GetId() == "" {
        return nil, status.Errorf(codes.InvalidArgument, "user id is required")
    }

    u, err := s.repo.Find(req.Id)
    if err != nil {
        if errors.Is(err, ErrNotFound) {
            return nil, status.Errorf(codes.NotFound, "user %q not found", req.Id)
        }
        return nil, status.Errorf(codes.Internal, "find user: %v", err)
    }
    return toProto(u), nil
}

// Client-side: inspect gRPC status from returned error
resp, err := client.GetUser(ctx, req)
if err != nil {
    st, ok := status.FromError(err)
    if ok {
        switch st.Code() {
        case codes.NotFound:
            // handle not found
        case codes.InvalidArgument:
            // handle bad input
        default:
            // unexpected error
        }
    }
}
```

| Situation | gRPC Code | Common Mistake |
|-----------|-----------|----------------|
| Missing/invalid argument | `codes.InvalidArgument` | Using `codes.Internal` |
| Resource not found | `codes.NotFound` | Returning raw `nil, err` |
| Caller not authenticated | `codes.Unauthenticated` | Using `codes.PermissionDenied` |
| Caller lacks permission | `codes.PermissionDenied` | Using `codes.Unauthenticated` |
| Duplicate / conflict | `codes.AlreadyExists` | Using `codes.Internal` |
| Deadline exceeded | `codes.DeadlineExceeded` | Using `codes.Unavailable` |
| Backend unavailable | `codes.Unavailable` | Using `codes.Internal` |
| Unimplemented RPC | `codes.Unimplemented` | Returning `codes.Unknown` |

Checks:
- All server RPC methods return `status.Errorf()` errors, never raw `fmt.Errorf()`.
- `codes.Internal` is reserved for truly unexpected errors; domain errors use specific codes.
- Client code uses `status.FromError()` to inspect codes, not string matching.
- Sensitive internal details are not leaked in status messages sent to clients.

## See Also

- `go-security-patterns.md` — TLS, auth patterns
- `go-concurrency-patterns.md` — stream lifecycle, goroutine management
- `go-database-patterns.md` — connection pool for backend calls
