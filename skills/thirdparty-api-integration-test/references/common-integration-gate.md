# Common Integration Configuration Gate

Apply this gate before generating or updating runnable integration tests.

## Mandatory Steps

1. Scan repository code and configuration to identify required runtime variables.
2. List each variable with:
   - purpose
   - expected format/type
   - whether it is required
3. Include gate variable(s) (for example `THIRDPARTY_INTEGRATION=1` or vendor-specific gate).
4. Enforce production safety gate:
   - if `ENV` is `prod`/`production`, refuse by default
   - allow override only with explicit `INTEGRATION_ALLOW_PROD=1`
5. If required values are missing:
   - ask the user for missing values before generating runnable tests, or
   - generate placeholder-only scaffolding with explicit TODO markers and `t.Skip(...)` guards
6. Never guess endpoints, credentials, or identifiers to make tests look runnable.
7. Never hardcode secrets, passwords, tokens, or private endpoints in test source.
8. Require build tag isolation for runnable tests:
   - `//go:build integration`
   - run with `go test -tags=integration ...`

## Required Output In Every Run

Always include:
- required variable list
- example export/run command block
- currently missing variables (if any)
- whether prod-safety gate blocked execution

## Skip Message Quality

Skip messages must be actionable and concrete, for example:
- `set THIRDPARTY_INTEGRATION=1 to run`
- `set ENV, CONFIG_DIR, MCS_CUSTOMER_IDS, MCS_LABEL_ID to run`
- `refuse prod by default: set INTEGRATION_ALLOW_PROD=1 to override`
