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
10. **Quality scorecard verdict** (whenever test code was authored or reviewed):
    - the tier counts from `checklists.md` §Test Quality Checklist —
      `Critical: n/4, Standard: n/5, Hygiene: n/4`
    - the overall verdict under that file's rule: **any single Critical FAIL → overall
      FAIL**, regardless of the other tiers
    - each FAIL named with the item ID (`C2`, `S3`, …) and what would fix it

    Scoring without reporting is the same as not scoring: the rubric exists so a reviewer
    can see *which* check failed, not just that something did. Omit this field only when
    no test code was produced or reviewed (Blocked level, or a scope redirect).

## Rules

- If tests were not executed, state that explicitly with the reason and the degradation level.
- If execution was partial (some tests skipped due to missing config), report which tests ran and which were skipped.
- Never report a PASS when tests were actually skipped — distinguish between "passed" and "skipped".
- Include the Go version used and the `-tags` flag in the command output.
