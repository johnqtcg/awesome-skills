# Common Integration Output Contract

When executing integration-test skills, always report these mandatory fields:

## Mandatory Fields

1. **Execution mode**: Smoke | Standard | Comprehensive
2. **Integration target**: service/client/package/method under test
3. **Degradation level**: Full | Scaffold | Blocked
4. **Gate variables and required runtime env vars**: list with current status (set / missing)
5. **Exact command(s)** used (or recommended) to run tests
6. **Timeout and retry policy**: timeout value + max retries + backoff strategy
7. **Result summary**:
   - pass / fail / skip / scaffold-only
   - total tests: N passed, N failed, N skipped
   - first failing test name and error (if any)
8. **Failure classification** (if failed):
   - config / auth / network / timeout / contract / business assertion / test pollution
   - evidence: exact error message or response snippet
   - suggested fix: concrete command or code change
9. **Missing prerequisites** (if any):
   - exact missing variables with purpose
   - actionable setup instructions (example commands)

## Rules

- If tests were not executed, state that explicitly with the reason and the degradation level.
- If execution was partial (some tests skipped due to missing config), report which tests ran and which were skipped.
- Never report a PASS when tests were actually skipped — distinguish between "passed" and "skipped".
- Include the Go version used and the `-tags` flag in the command output.
