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

## AE-5: Demonstrated Impact Asserted From an Unverified Condition

**Wrong**: `SEC-001: P0 confirmed — remote code execution via Java native deserialization`,
with `Impact: remote code execution as the service account — full host compromise`, while the
same report records "whether a known gadget library is on the classpath is unresolved". The
path is genuinely confirmed; the RCE *impact* was not established by this review, and the
report states it in the indicative anyway.

**Correct**: keep the severity (unfiltered native deserialization of network input is P0 by
class and reachability), and split the two claims:

- `Confirmed`: untrusted bytes reach `ObjectInputStream.readObject` with no filter — CWE-502.
  Independent of any gadget, this already permits instantiation of arbitrary `Serializable`
  types on the classpath and unbounded object-graph expansion.
- `Assessed (not demonstrated here)`: remote code execution, **if** a gadget chain is present.
  Unverified condition: the classpath inventory. Checks that would settle it:
  `mvn dependency:tree`, and whether a JEP 290 filter is configured.

The severity does not move for the unverified condition in either direction — but the reader
must be able to tell which sentence is evidence and which is inference.

## AE-6: Accepting P0 Without Escalation

**Wrong**: Adding a P0 finding to the Risk Acceptance Register with approver: "tech lead."
**Correct**: P0 findings MUST NOT be accepted without VP-level or equivalent sign-off. Record the approver name and role explicitly.

## AE-7: Ignoring Transitive Call Paths

**Wrong**: Reviewing only the changed function and concluding "no injection risk" while the function passes user input to a helper that calls `db.Query(fmt.Sprintf(...))`.
**Correct**: Trace user input through changed function into callers and callees (at least 1-2 levels). String `Applicable` domains must follow data flow, not just diff boundaries.
