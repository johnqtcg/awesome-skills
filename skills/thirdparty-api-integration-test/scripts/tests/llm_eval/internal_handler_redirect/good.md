## Scope verdict

`Scope: OUT OF SCOPE for $thirdparty-api-integration-test`

## Recommended skill

**`$api-integration-test`** — internal HTTP API integration tests.

## Reason

`HealthHandler` is **this service's own `http.HandlerFunc`**, served by the binary under
test. There is no third-party vendor anywhere in this path: no vendor client, no external
account, no sandbox host, no billable call. Everything this skill exists to control —
`VENDOR_SANDBOX_HOSTS`, `VENDOR_TEST_ACCOUNTS`, the call budget, idempotency keys,
`Retry-After` handling — has nothing to bind to.

Routing it here would also be actively harmful, not merely wrong: the vendor gates would
refuse a first-party target as "not on the sandbox allowlist", so the test could only ever
skip or fatal. `$api-integration-test` has the right gates for a first-party endpoint
(resolved host, test tenant, in-process vs system integration taxonomy).

**Hard stop.** Per the Scope Validation Gate, the remaining gates are skipped and no test
code is generated.
