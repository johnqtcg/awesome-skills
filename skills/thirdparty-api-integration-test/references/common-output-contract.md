# Common Integration Output Contract

When executing integration-test skills, always report:

1. Integration target:
   - service/client/package/method under test
2. Gate variable and required runtime env vars
3. Exact command(s) used to run tests
4. Timeout setting and retry policy used by the test
5. **Degradation level applied**: `Full` | `Scaffold` | `Blocked` (mirror the configuration gate)
6. Result summary:
   - **counts**: `N passed, N failed, N skipped`
   - overall verdict (pass / fail / skip); first failing step (or first skip condition)
7. Failure classification (if failed):
   - config / auth / network / timeout / contract / business assertion / rate-limit
8. Missing prerequisites:
   - exact missing variables
   - actionable setup instructions

## CI-Integrity Rules

- If tests were not executed, state that explicitly and explain why.
- **Never report PASS when tests were actually skipped** — distinguish "passed" from "skipped".
- **A `(cached)` result is NOT evidence of a live vendor call.** `go test` prints `ok … (cached)`
  when it reuses a prior result without running the binary, so the vendor was never contacted.
  Every real run MUST use `-count=1`; treat a `(cached)` line as "did not run this time".
- Include the Go version and the `-tags`/`-count=1`/`-timeout` flags in the command output.
