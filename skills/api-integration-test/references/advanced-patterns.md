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

Note: this **stub-server** pattern (a fake handler you write in the test) is an
*adapter/component test*, NOT an integration test — it exercises only your client's
parsing and transport, so it belongs alongside unit tests (no build tag). Wiring the
**real** handler + real dependencies through `httptest.Server` is a different thing:
that IS an in-process integration test (build tag required). See SKILL.md §Test Taxonomy.

## Test Data Lifecycle Pattern

Document data lifecycle explicitly for any test that creates resources:

```go
func TestCreateAndCleanup_Integration(t *testing.T) {
    env, baseURL := requireIntegrationEnv(t)
    tenant := strings.TrimSpace(os.Getenv("TEST_TENANT_ID"))
    // Creates AND deletes data → destructive. assertDestructiveSafe (SKILL.md
    // §Go Implementation Baseline) skips unless INTEGRATION_ALLOW_DESTRUCTIVE=1,
    // requires NONPROD_HOST_ALLOWLIST, fatals on a prod target even with
    // ALLOW_PROD=1, and validates the test tenant — destructive writes are never
    // allowed against production. Keep destructive tests in a CI job separate
    // from the base read-only gate.
    assertDestructiveSafe(t, env, baseURL, tenant)

    client := NewClient(baseURL)
    ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
    defer cancel()

    // Create
    created, err := client.CreateItem(ctx, &CreateItemRequest{
        Name: fmt.Sprintf("test-item-%d", time.Now().UnixNano()),
    })
    require.NoError(t, err)
    require.NotEmpty(t, created.ID)

    // Cleanup — register immediately after creation. Failure must be SURFACED,
    // not swallowed: a silent `_ = client.DeleteItem(...)` leaves polluted data
    // that eventually breaks the test environment.
    t.Cleanup(func() {
        cleanCtx, cleanCancel := context.WithTimeout(context.Background(), 5*time.Second)
        defer cleanCancel()
        if err := client.DeleteItem(cleanCtx, created.ID); err != nil {
            // t.Errorf marks the test failed so leaked data is visible in CI.
            // Downgrade to t.Logf only for exploratory local runs — never a release gate.
            t.Errorf("cleanup failed, data leaked (id=%s): %v", created.ID, err)
        }
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
        image: company/internal-api:1.24.0  # pin an exact version or @sha256 digest — never :latest (breaks reproducibility)
        ports: ["8080:8080"]
        options: >-
          --health-cmd "curl -f http://localhost:8080/health || exit 1"
          --health-interval 5s
          --health-timeout 3s
          --health-retries 10
    steps:
      - uses: actions/checkout@v7   # pin to a major tag (or a full commit SHA for strict reproducibility)
      - uses: actions/setup-go@v7
        with:
          go-version-file: go.mod
      - name: Run integration tests
        env:
          INTERNAL_API_INTEGRATION: "1"
          ENV: test
          API_BASE_URL: http://localhost:8080
          TEST_TENANT_ID: test-tenant-1
          TEST_TENANT_ALLOWLIST: test-tenant-1   # required — tenant validation is fail-closed
          # destructive jobs also set INTEGRATION_ALLOW_DESTRUCTIVE and NONPROD_HOST_ALLOWLIST
        run: go test -tags=integration -v -timeout=300s -count=1 ./...   # -count=1: never accept a (cached) result for an integration run
```

### Makefile Target

```makefile
.PHONY: integration-test
integration-test: ## Run integration tests (requires services running)
	INTERNAL_API_INTEGRATION=1 ENV=dev TEST_TENANT_ID=test-tenant-1 TEST_TENANT_ALLOWLIST=test-tenant-1 \
	  go test -tags=integration -v -timeout=300s -count=1 ./...
```

### Command Reference

```bash
# Smoke — quick connectivity check
INTERNAL_API_INTEGRATION=1 ENV=dev API_BASE_URL=http://localhost:8080 \
  TEST_TENANT_ID=test-tenant-1 TEST_TENANT_ALLOWLIST=test-tenant-1 \
  go test -tags=integration ./... -run Integration -v -timeout=30s -count=1

# Standard — default pre-merge gate
INTERNAL_API_INTEGRATION=1 ENV=dev API_BASE_URL=http://localhost:8080 \
  TEST_TENANT_ID=test-tenant-1 TEST_TENANT_ALLOWLIST=test-tenant-1 \
  go test -tags=integration ./... -run Integration -v -timeout=120s -count=1

# Comprehensive — release gate
INTERNAL_API_INTEGRATION=1 ENV=dev API_BASE_URL=http://localhost:8080 \
  TEST_TENANT_ID=test-tenant-1 TEST_TENANT_ALLOWLIST=test-tenant-1 \
  go test -tags=integration ./... -run Integration -v -timeout=300s -count=1
```
