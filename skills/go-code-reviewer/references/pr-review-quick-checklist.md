# PR Review Quick Checklist

Use this checklist for fast, high-signal PR reviews.
This is a supplement to `SKILL.md`, not a replacement.

## 1) Scope & Intent
- PR scope is clear (what changed and why).
- Risky files identified (concurrency, persistence, auth, shared libs).
- Public/API behavior changes are explicit.

## 2) Correctness
- Main code path works as intended.
- Edge cases handled (empty, nil, boundary, last-element logic).
- No obvious off-by-one/map-slice misuse/stale-state bug.
- Error paths return correct failures (no silent partial success).

## 3) Concurrency & Lifecycle
- No data races on shared vars/maps/slices.
- Goroutine lifecycle controlled (cancel/shutdown path).
- Worker/background tasks have deterministic stop behavior.
- Lock/channel usage cannot deadlock under normal/error paths.

## 4) Error Handling
- No ignored critical errors.
- Wrapped errors keep context (`fmt.Errorf("...: %w", err)`) when appropriate.
- Logging is useful and not noisy.
- Panic recovery (if used) does not hide broken state.

## 5) Data & Contracts
- Persistence updates atomic/consistent where required.
- Ordering semantics preserved.
- API response shape/backward compatibility preserved.
- Migration/query/index impacts considered for DB changes.

## 6) Security & Safety
- Input validation is sufficient.
- Sensitive data is not logged.
- Auth/authz checks are not bypassed.
- External calls/timeouts/retries are bounded.

## 7) Performance
- No unbounded loops/work queues/memory growth.
- Expensive ops justified and scoped.
- N+1 patterns avoided.

## 8) Tests
- Tests cover changed behavior and key failure modes.
- Boundary cases covered (`n=0`, `n=1`, `n=2/3`, first/middle/last).
- Regression test exists for bug fixes.
- `go test` / `-race` evidence provided or explicitly marked:
  - `Not run in this environment`

## 9) Observability & Configuration
- New code paths have adequate logging (structured, with request context).
- Metrics or health signals added for new failure modes.
- Config changes (env vars, feature flags, defaults) are documented and bounded.
- No secrets or credentials in config defaults or logs.

## 10) Rollback Safety
- Can this change be safely rolled back without data migration?
- Database migrations are additive and backward-compatible where possible.
- Feature flags used for risky behavior changes.

## 11) Change Origin
- Each finding labeled `introduced` / `pre-existing` / `uncertain`.
- Pre-existing findings do NOT block merge unless High severity with immediate risk.
- Pre-existing findings recommend follow-up issue rather than inline fix.

## 12) Baseline Continuity
- Each finding labeled `new/regressed/unchanged`.
- If prior findings no longer reproduce, mark `resolved`.
- If no prior review context, state `Baseline not found`.

## 13) False-Positive Suppression
- Do not file findings already blocked by upstream guards.
- Do not file findings on non-user-controlled input paths.
- Move suppressed concerns to `Suppressed items` with rationale.

## 14) Review Output Quality
- Findings ordered High -> Medium -> Low.
- Each finding includes `location + impact + evidence + recommendation`.
- Include `Execution Status` and `Risk Acceptance / SLA` blocks.
- If no findings: state `No actionable findings found` and list residual risks.

## See Also

- `go-security-patterns.md` — detailed security review patterns
- `go-concurrency-patterns.md` — concurrency and lifecycle patterns
- `go-error-and-quality.md` — error handling and code quality patterns
- `go-test-quality.md` — test quality patterns
- `go-api-http-checklist.md` — HTTP and gRPC review patterns
- `go-database-patterns.md` — database review patterns
- `go-performance-patterns.md` — performance review patterns
- `go-modern-practices.md` — modern Go best practices
