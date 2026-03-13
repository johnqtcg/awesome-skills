# Common Integration Output Contract

When executing integration-test skills, always report:

1. Integration target:
   - service/client/package/method under test
2. Gate variable and required runtime env vars
3. Exact command(s) used to run tests
4. Timeout setting and retry policy used by the test
5. Result summary:
   - pass/fail/skip
   - first failing step (or first skip condition)
6. Failure classification (if failed):
   - config / auth / network / timeout / contract / business assertion
7. Missing prerequisites:
   - exact missing variables
   - actionable setup instructions

If tests were not executed, state that explicitly and explain why.
