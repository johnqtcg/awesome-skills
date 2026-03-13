# Security Review — Extended Anti-Examples

These are additional structured examples of review mistakes. Each shows a wrong approach and the correct alternative.

For the core anti-examples (style findings, over-reporting false positives, missing gate coverage), see the main SKILL.md.

---

## AE-2: Marking Domain N/A Without Evidence

**Wrong**: `Domain 7 (Concurrency): N/A` — with no further explanation, while the diff adds a `go func()` in a handler.
**Correct**: `Domain 7 (Concurrency): Applicable` — diff introduces `go func()` at `handler.go:45`; verify bounded lifecycle, shared state synchronization, and run `go test -race`.

## AE-4: Confirmed Without Reproducer

**Wrong**: `SEC-003: P0 confirmed — SQL injection in search handler` with no reproducer, no exploit path, and no evidence beyond seeing string concatenation.
**Correct**: Either provide a reproducer (`curl` command + expected response) for `confirmed`, or downgrade to `likely`/`suspected` with a clear statement of what assumption remains unproven.

## AE-6: Accepting P0 Without Escalation

**Wrong**: Adding a P0 finding to the Risk Acceptance Register with approver: "tech lead."
**Correct**: P0 findings MUST NOT be accepted without VP-level or equivalent sign-off. Record the approver name and role explicitly.

## AE-7: Ignoring Transitive Call Paths

**Wrong**: Reviewing only the changed function and concluding "no injection risk" while the function passes user input to a helper that calls `db.Query(fmt.Sprintf(...))`.
**Correct**: Trace user input through changed function into callers and callees (at least 1-2 levels). String `Applicable` domains must follow data flow, not just diff boundaries.
