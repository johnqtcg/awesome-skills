# Vendor Integration Test Template

Generic template for third-party API integration tests. Replace `<VENDOR>` placeholders with your vendor name (e.g., `MCS`, `USS`, `GITHUB`, `OPENAI`).

## Go Template

```go
//go:build integration
// +build integration

func Test<VENDOR>Integration(t *testing.T) {
    if os.Getenv("<VENDOR>_INTEGRATION") != "1" {
        t.Skip("set <VENDOR>_INTEGRATION=1 to run")
    }

    env := strings.ToLower(strings.TrimSpace(os.Getenv("ENV")))
    if (env == "prod" || env == "production") && os.Getenv("INTEGRATION_ALLOW_PROD") != "1" {
        t.Skip("refuse prod by default: set INTEGRATION_ALLOW_PROD=1 to override")
    }

    configDir := strings.TrimSpace(os.Getenv("CONFIG_DIR"))
    rawID := strings.TrimSpace(os.Getenv("<VENDOR>_TARGET_ID"))
    if env == "" || configDir == "" || rawID == "" {
        t.Skip("set ENV, CONFIG_DIR, <VENDOR>_TARGET_ID to run")
    }

    targetID, err := strconv.ParseInt(rawID, 10, 64)
    require.NoError(t, err)
    t.Logf("<VENDOR> target ID: %d", targetID)

    // Data lifecycle: use dedicated IDs and idempotency keys, avoid shared mutable fixtures.

    cfg := config.MustLoad()
    client, err := NewClient(cfg.<VENDOR>Service, zap.NewNop())
    require.NoError(t, err)

    ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
    defer cancel()

    // Default no retry; if vendor is transient, allow max 1 retry with bounded backoff.

    // Call <VENDOR> API and assert protocol + business invariants:
    //   protocol: status code, required response fields
    //   business: identifier consistency, semantic constraints
    _ = client
}
```

## Run Command

```bash
<VENDOR>_INTEGRATION=1 ENV=dev CONFIG_DIR=/path/to/config \
<VENDOR>_TARGET_ID=123 \
go test -tags=integration ./internal/pkg/thirdparty/<vendor> -run Integration -v
```

## Adapting the Template

1. Replace `<VENDOR>` / `<vendor>` with the actual vendor name (uppercase for env vars, lowercase for package path).
2. Add vendor-specific env vars as needed (API keys, tenant IDs, region).
3. If the vendor uses API key auth instead of config loader, replace `config.MustLoad()` with direct key retrieval from env.
4. For paid APIs (e.g., OpenAI), keep tests read-only and use the cheapest model/tier available.
