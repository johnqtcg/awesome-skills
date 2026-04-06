# Example Output (End-to-End)

A complete review report produced by the go-review-lead orchestrator. Use this as a formatting and completeness reference.

```
---
Review Mode

- Review depth: Standard (4 production files, concurrency primitives present but no auth/schema changes)
- Compile pre-check: PASS
- Dispatched skills: go-security-reviewer, go-concurrency-reviewer, go-quality-reviewer, go-logic-reviewer
- Skipped skills: go-test-reviewer (no _test.go in diff), go-performance-reviewer (no hot-path patterns), go-error-reviewer (no sql.Rows/resp.Body patterns)
- Scope narrowing: Applied to go-logic-reviewer: skipped Concurrency (go-concurrency-reviewer dispatched), Security (go-security-reviewer dispatched)
- Triage rationale: diff includes database/sql and go func patterns; no test files or performance-sensitive loops

---
Findings

[High] Race Condition on Shared Cache Map

- ID: REV-001 (original: CONC-001)
- Origin: introduced
- Baseline: new
- Principle: N/A (no constitution.md)
- Category: Concurrency
- Location: internal/cache/store.go:42
- Impact: Concurrent HTTP handlers write to unprotected map; will panic under load
- Evidence: go func at store.go:38 writes to s.items without lock; concurrent read at store.go:57 has no synchronization. go test -race confirms.
- Recommendation: Replace s.items with sync.Map or wrap all accesses with sync.RWMutex
- Action: must-fix

[High] SQL Injection in Search Handler

- ID: REV-002 (original: SEC-001)
- Origin: introduced
- Baseline: new
- Principle: N/A (no constitution.md)
- Category: Security
- Location: internal/repo/user.go:67
- Impact: Attacker can execute arbitrary SQL via search parameter
- Evidence: fmt.Sprintf("SELECT * FROM users WHERE name LIKE '%%%s%%'", name) — name flows from r.URL.Query().Get("q") without sanitization
- Recommendation: db.QueryContext(ctx, "SELECT * FROM users WHERE name LIKE ?", "%"+name+"%")
- Action: must-fix

[Medium] Function Exceeds 50-Line Limit

- ID: REV-003 (original: QUAL-001)
- Origin: introduced
- Baseline: new
- Principle: N/A (no constitution.md)
- Category: Quality
- Location: internal/service/order.go:120
- Impact: Reduced readability and testability; harder to review logic correctness
- Evidence: ProcessOrder() is 78 lines; golangci-lint cyclop reports complexity 12
- Recommendation: Extract payment validation and inventory check into separate functions
- Action: follow-up

---
Suppressed Items

[Suppressed] MD5 Usage in Cache Key
- Reason: go-security-reviewer suppressed: MD5 at cache.go:15 used for non-cryptographic cache key derivation (anti-example: over-cautious crypto on non-password use)
- Location: internal/cache/store.go:15
- Residual risk: None — cache key collision is acceptable

---
Execution Status
- Go version: 1.22
- Skills dispatched: go-security-reviewer, go-concurrency-reviewer, go-quality-reviewer, go-logic-reviewer
- Per-skill tool runs:
  - go-security-reviewer: gosec Not available (command: gosec ./...)
  - go-concurrency-reviewer: go test -race PASS
  - go-quality-reviewer: golangci-lint PASS
- Excluded (generated): internal/proto/user.pb.go

---
Risk Acceptance / SLA
- High findings: must-fix before merge
- Medium findings: follow-up within 2 weeks
- Low findings: discretionary

---
Residual Risk / Testing Gaps
1. Verification gaps: gosec not installed — manual review covered SQL/command injection patterns
2. Volume-cap overflow: None
3. Pre-existing issues: None found in impact-radius files
4. Areas not covered: Dynamic dispatch in plugin loader not traceable

---
Summary

2 introduced / 0 pre-existing / 0 uncertain. 2 High / 1 Medium / 0 Low.
```
