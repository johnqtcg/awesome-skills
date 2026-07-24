# Common Integration Configuration Gate

Apply this gate before generating or updating runnable integration tests.

## Mandatory Steps

1. Scan repository code and configuration to identify required runtime variables.
2. List each variable with:
   - purpose
   - expected format/type
   - whether it is required or optional (with default)
3. Include gate variable(s) (for example `INTERNAL_API_INTEGRATION=1` or vendor-specific gate).
4. Enforce production safety gate — validate the **resolved host**, not just `ENV`:
   - refuse if `ENV` is `prod`/`production` **OR** the base-URL host matches a prod
     pattern. Fail **closed**: `url.Parse` accepts relative refs — `api.production.internal`
     parses with no error but empty scheme/host, and `prod-host:8080` gets scheme
     `prod-host` — so require an **absolute `http(s)` URL with a non-empty host** and
     treat anything else (or a parse error) as prod. Checking only the parse error is a bypass.
   - require a dedicated test tenant/account; refuse non-test tenants
   - allow override only with explicit `INTEGRATION_ALLOW_PROD=1`
   - when the run gate is enabled, this refusal is a hard failure (`t.Fatalf`), not a
     silent `t.Skip` (see SKILL.md §Skip vs Fail (CI Integrity))
5. Determine degradation level (see below) and proceed accordingly.
6. Never guess endpoints, credentials, or identifiers to make tests look runnable.
7. Never hardcode secrets, passwords, tokens, or private endpoints in test source.
8. Require build tag isolation for runnable tests:
   - `//go:build integration`
   - run with `go test -tags=integration ...`

## Degradation Levels

Determine the current level based on available information, and act accordingly:

| Level | Condition | Action |
|-------|-----------|--------|
| **Full** | All required env vars documented, service address known, gate var defined | Generate complete, runnable integration tests |
| **Scaffold** | Some env vars identified, some missing (e.g., unknown test user ID, partial config) | Generate test file with `t.Skip(...)` guards + `// TODO:` markers for each missing value. State explicitly which vars are missing and how to obtain them. **Scaffold skips are authoring-time-incomplete and MUST be excluded from the official CI integration gate** (separate build tag / not in the gated target) so they never false-green. |
| **Blocked** | Gate env var unknown, cannot determine service address, or scope is unclear | Do NOT generate runnable test code. Output only: (1) required variable checklist, (2) example `export` + `go test` command block, (3) setup instructions, (4) reason for blocking. |

### Decision Flow

```
1. Can you determine the gate env var name?  No → Blocked
2. Can you determine the service address/base URL?  No → Blocked
3. Are ALL required env vars documented?  No → Scaffold (mark missing vars with TODO)
4. All above?  → Full
```

### Scaffold Mode Example

```go
func TestOrderService_Integration(t *testing.T) {
    if os.Getenv("INTERNAL_API_INTEGRATION") != "1" {
        t.Skip("set INTERNAL_API_INTEGRATION=1 to run")
    }
    // TODO: replace with real endpoint once service is deployed
    baseURL := strings.TrimSpace(os.Getenv("ORDER_SERVICE_URL"))
    if baseURL == "" {
        t.Skip("set ORDER_SERVICE_URL to run (e.g., http://localhost:8081)")
    }
    // TODO: determine test order ID for your environment
    orderID := strings.TrimSpace(os.Getenv("TEST_ORDER_ID"))
    if orderID == "" {
        t.Skip("set TEST_ORDER_ID to run")
    }
}
```

> **Scaffold `t.Skip` is intentional and temporary.** These skips mark an
> authoring-time-incomplete test and must stay out of the official gate. Once the
> TODOs are filled and the test is promoted to **Full** mode, the run-gate check
> stays `t.Skip` (opt-in), but missing *required* config while the gate is enabled
> becomes `t.Fatalf` — otherwise a completed test that lost its config would
> false-green. See SKILL.md §Skip vs Fail (CI Integrity).

### Blocked Mode Example Output

```
## Blocked: Cannot Generate Integration Tests

**Reason**: Service address and authentication method are unknown.

**Required variables** (not yet determined):

| Variable | Purpose | How to obtain |
|----------|---------|---------------|
| `API_BASE_URL` | Service endpoint | Check deployment config or service registry |
| `API_TOKEN` | Auth bearer token | Generate via `make token-dev` or ask ops |
| `TEST_TENANT_ID` | Isolated test tenant | Create in admin console |
| `TEST_TENANT_ALLOWLIST` | Exact test tenant IDs permitted (fail-closed; required) | List your test tenant ID(s), comma-separated |

**Example run command** (fill in values first):
```bash
export INTERNAL_API_INTEGRATION=1
export ENV=dev
export API_BASE_URL=http://???
export API_TOKEN=???
export TEST_TENANT_ID=???
export TEST_TENANT_ALLOWLIST=???        # required — exact test tenant IDs (comma-separated)
# destructive runs also need: export INTEGRATION_ALLOW_DESTRUCTIVE=1 NONPROD_HOST_ALLOWLIST=<test hosts>
go test -tags=integration ./internal/client/order -run Integration -v -count=1
```
```

## Required Output In Every Run

Always include:
- required variable list
- example export/run command block
- currently missing variables (if any)
- degradation level applied (Full / Scaffold / Blocked)
- whether prod-safety gate blocked execution

## Skip / Fatal Message Quality

Both skip and fatal messages must be actionable and concrete. Use the right one
(see SKILL.md §Skip vs Fail): **skip** only when the run was not requested or for
an opt-in tier; **fatal** when the gate is set but misconfigured or the target is
production.

Skip examples (run not requested / opt-in tier):
- `set INTERNAL_API_INTEGRATION=1 to run`
- `destructive: set INTEGRATION_ALLOW_DESTRUCTIVE=1 to run`

Fatal examples (gate on but broken/dangerous — NOT a skip):
- `set ENV, CONFIG_DIR, TEST_USER_ID, TEST_TENANT_ID to run`
- `refuse production target: set INTEGRATION_ALLOW_PROD=1 to override, or use a non-prod endpoint`

BAD messages (do not use):
- `missing configuration` — too vague, user does not know which var
- `test skipped` — provides zero guidance
- `environment not set up` — does not tell user what to set up
