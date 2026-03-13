# Internal API Integration Patterns

## Table of Contents

1. [HTTP Pattern](#http-pattern)
2. [gRPC Pattern](#grpc-pattern)
3. [Expected Failure Path Pattern](#expected-failure-path-pattern)
4. [Retry/Timeout Policy Pattern](#retrytimeout-policy-pattern)
5. [Retry — Transient Error Classification](#retry--transient-error-classification)
6. [Env Parsing Pattern](#env-parsing-pattern)
7. [Concurrent Request Safety Pattern](#concurrent-request-safety-pattern)

For httptest adapter tests, test data lifecycle, and CI execution patterns, see `advanced-patterns.md`.

---

## HTTP Pattern

Use `httptest` only when validating adapter behavior; use real internal endpoint for true integration.

```go
ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
defer cancel()

resp, err := client.GetUser(ctx, userID)
require.NoError(t, err)
require.Equal(t, http.StatusOK, resp.StatusCode)
require.NotEmpty(t, resp.Body.ID)
require.Equal(t, userID, resp.Body.ID, "identity mapping: returned user must match request")
```

Recommended assertions:

1. HTTP status code (protocol-level).
2. Response schema — required fields are present and non-zero.
3. Key business invariant (e.g., returned account matches request account).

## gRPC Pattern

```go
ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
defer cancel()

out, err := grpcClient.GetResource(ctx, &pb.GetResourceRequest{Id: id})
require.NoError(t, err)
require.Equal(t, id, out.Id)
require.NotNil(t, out.Meta)
```

For expected gRPC errors:

```go
_, err := grpcClient.GetResource(ctx, &pb.GetResourceRequest{Id: "nonexistent"})
require.Error(t, err)
st, ok := status.FromError(err)
require.True(t, ok)
require.Equal(t, codes.NotFound, st.Code())
```

## Expected Failure Path Pattern

Always test at least one expected-failure scenario per endpoint.

```go
func TestGetUser_NotFound_Integration(t *testing.T) {
    env, baseURL := requireIntegrationEnv(t)
    _ = env

    client := NewClient(baseURL)
    ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
    defer cancel()

    resp, err := client.GetUser(ctx, "nonexistent-id-000")
    require.NoError(t, err, "HTTP call itself should succeed")
    require.Equal(t, http.StatusNotFound, resp.StatusCode)
}

func TestCreateUser_InvalidPayload_Integration(t *testing.T) {
    env, baseURL := requireIntegrationEnv(t)
    _ = env

    client := NewClient(baseURL)
    ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
    defer cancel()

    resp, err := client.CreateUser(ctx, &CreateUserRequest{Name: ""})
    require.NoError(t, err)
    require.Equal(t, http.StatusBadRequest, resp.StatusCode)
    require.Contains(t, resp.Body.Error, "name")
}
```

## Retry/Timeout Policy Pattern

Default is no retry. Add retry only for proven transient failures.

```go
ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
defer cancel()

const maxRetries = 1
backoff := 200 * time.Millisecond

var (
    resp *Response
    lastErr error
)

for attempt := 0; attempt <= maxRetries; attempt++ {
    resp, lastErr = client.DoSomething(ctx, req)
    if lastErr == nil {
        break
    }

    if !isTransient(lastErr) {
        break // non-retryable error, stop immediately
    }

    if attempt == maxRetries {
        break
    }

    select {
    case <-ctx.Done():
        t.Fatalf("context done before retry: %v", ctx.Err())
    case <-time.After(backoff):
    }
    backoff *= 2 // exponential backoff
}

require.NoError(t, lastErr)
require.NotNil(t, resp)
require.Equal(t, http.StatusOK, resp.StatusCode)
```

## Retry — Transient Error Classification

Only retry errors in the retryable set:

```go
func isTransient(err error) bool {
    if errors.Is(err, context.DeadlineExceeded) {
        return false // context expired, retrying is pointless
    }
    if errors.Is(err, context.Canceled) {
        return false
    }

    var netErr net.Error
    if errors.As(err, &netErr) && netErr.Timeout() {
        return true // individual call timeout, can retry
    }

    // HTTP 429, 502, 503, 504 are retryable
    var httpErr *HTTPError
    if errors.As(err, &httpErr) {
        switch httpErr.StatusCode {
        case http.StatusTooManyRequests,
            http.StatusBadGateway,
            http.StatusServiceUnavailable,
            http.StatusGatewayTimeout:
            return true
        }
    }

    return false
}
```

Never retry:
- 400 Bad Request (client bug)
- 401 Unauthorized (auth issue, not transient)
- 403 Forbidden (permission, not transient)
- 404 Not Found (resource absent, not transient)
- 409 Conflict (state conflict, needs different resolution)

## Env Parsing Pattern

```go
rawPort := strings.TrimSpace(os.Getenv("TARGET_PORT"))
port, err := strconv.Atoi(rawPort)
require.NoError(t, err, "TARGET_PORT must be a valid integer")
require.Greater(t, port, 0, "TARGET_PORT must be positive")

rawTimeout := strings.TrimSpace(os.Getenv("TEST_TIMEOUT"))
if rawTimeout == "" {
    rawTimeout = "15s"
}
timeout, err := time.ParseDuration(rawTimeout)
require.NoError(t, err, "TEST_TIMEOUT must be a valid duration (e.g., 15s, 1m)")
```

For list-type env vars:

```go
rawEndpoints := strings.TrimSpace(os.Getenv("SERVICE_ENDPOINTS"))
if rawEndpoints == "" {
    t.Skip("set SERVICE_ENDPOINTS (comma-separated) to run")
}
endpoints := strings.Split(rawEndpoints, ",")
for i := range endpoints {
    endpoints[i] = strings.TrimSpace(endpoints[i])
}
```

## Concurrent Request Safety Pattern

For Comprehensive mode — verify the service handles concurrent calls correctly:

```go
func TestConcurrentGetUser_Integration(t *testing.T) {
    env, baseURL := requireIntegrationEnv(t)
    _ = env

    client := NewClient(baseURL)
    const concurrency = 10

    ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
    defer cancel()

    errs := make(chan error, concurrency)
    for i := 0; i < concurrency; i++ {
        go func() {
            resp, err := client.GetUser(ctx, testUserID)
            if err != nil {
                errs <- err
                return
            }
            if resp.StatusCode != http.StatusOK {
                errs <- fmt.Errorf("unexpected status: %d", resp.StatusCode)
                return
            }
            errs <- nil
        }()
    }

    for i := 0; i < concurrency; i++ {
        require.NoError(t, <-errs, "concurrent request %d failed", i)
    }
}
```
