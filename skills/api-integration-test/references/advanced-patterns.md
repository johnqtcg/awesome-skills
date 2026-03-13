# Advanced Integration Test Patterns

Load this file only when needed: Comprehensive mode, CI integration, httptest adapter tests, or test data lifecycle management.

## Table of Contents

1. [httptest Pattern (Adapter Tests)](#httptest-pattern-adapter-tests)
2. [Test Data Lifecycle Pattern](#test-data-lifecycle-pattern)
3. [CI Execution Pattern](#ci-execution-pattern)

---

## httptest Pattern (Adapter Tests)

When testing an adapter/client library without a real service:

```go
func TestClientAdapter_ParsesResponse(t *testing.T) {
    srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        require.Equal(t, "/api/v1/users/42", r.URL.Path)
        require.Equal(t, "Bearer test-token", r.Header.Get("Authorization"))
        w.Header().Set("Content-Type", "application/json")
        w.WriteHeader(http.StatusOK)
        fmt.Fprintf(w, `{"id":"42","name":"Test User"}`)
    }))
    defer srv.Close()

    client := NewClient(srv.URL, WithToken("test-token"))
    ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
    defer cancel()

    user, err := client.GetUser(ctx, "42")
    require.NoError(t, err)
    require.Equal(t, "42", user.ID)
    require.Equal(t, "Test User", user.Name)
}
```

Note: httptest tests are NOT integration tests. They belong alongside unit tests (no build tag needed). Include this pattern only for adapter-layer validation.

## Test Data Lifecycle Pattern

Document data lifecycle explicitly for any test that creates resources:

```go
func TestCreateAndCleanup_Integration(t *testing.T) {
    env, baseURL := requireIntegrationEnv(t)
    _ = env

    client := NewClient(baseURL)
    ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
    defer cancel()

    // Create
    created, err := client.CreateItem(ctx, &CreateItemRequest{
        Name: fmt.Sprintf("test-item-%d", time.Now().UnixNano()),
    })
    require.NoError(t, err)
    require.NotEmpty(t, created.ID)

    // Cleanup — register immediately after creation
    t.Cleanup(func() {
        cleanCtx, cleanCancel := context.WithTimeout(context.Background(), 5*time.Second)
        defer cleanCancel()
        _ = client.DeleteItem(cleanCtx, created.ID)
    })

    // Verify
    fetched, err := client.GetItem(ctx, created.ID)
    require.NoError(t, err)
    require.Equal(t, created.ID, fetched.ID)
}
```

## CI Execution Pattern

### GitHub Actions

```yaml
jobs:
  integration:
    runs-on: ubuntu-latest
    services:
      internal-api:
        image: company/internal-api:latest
        ports: ["8080:8080"]
        options: >-
          --health-cmd "curl -f http://localhost:8080/health || exit 1"
          --health-interval 5s
          --health-timeout 3s
          --health-retries 10
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-go@v5
        with:
          go-version-file: go.mod
      - name: Run integration tests
        env:
          INTERNAL_API_INTEGRATION: "1"
          ENV: test
          API_BASE_URL: http://localhost:8080
        run: go test -tags=integration -v -timeout=300s ./...
```

### Makefile Target

```makefile
.PHONY: integration-test
integration-test: ## Run integration tests (requires services running)
	INTERNAL_API_INTEGRATION=1 ENV=dev \
	  go test -tags=integration -v -timeout=300s ./...
```

### Command Reference

```bash
# Smoke — quick connectivity check
INTERNAL_API_INTEGRATION=1 ENV=dev API_BASE_URL=http://localhost:8080 \
  go test -tags=integration ./... -run Integration -v -timeout=30s

# Standard — default pre-merge gate
INTERNAL_API_INTEGRATION=1 ENV=dev API_BASE_URL=http://localhost:8080 \
  go test -tags=integration ./... -run Integration -v -timeout=120s

# Comprehensive — release gate
INTERNAL_API_INTEGRATION=1 ENV=dev API_BASE_URL=http://localhost:8080 \
  go test -tags=integration ./... -run Integration -v -timeout=300s -count=1
```
