---
name: go-code-reviewer
description: Review Go code with a defect-first approach using repository policy (constitution.md first, then AGENTS.md fallback). Use for code review, PR review, quality checks, risk analysis, and regression detection.
allowed-tools: Read, Grep, Glob, Bash(go build*), Bash(go vet*), Bash(staticcheck*), Bash(golangci-lint*)
---
# Go Code Reviewer

## Purpose
Use this skill to review Go code for real defects and risk, not just style.
The review must be evidence-based, policy-aligned, and actionable.

## Quick Reference

| When you need to… | Jump to |
|---|---|
| Select review depth (Lite / Standard / Strict) | §Execution Modes |
| Read repo policy before reviewing | §Review Policy Sources |
| Execute full review checklist | §Review Checklist |
| Determine finding severity | §Finding Severity |
| Decide what NOT to report | §Review Discipline |
| Format findings and report | §Output Format |
| See a complete formatted output example | Load `references/example-output.md` |

## When To Use
Trigger this skill when the user asks for:
- Go code review / PR review / diff review
- Code quality or best-practice checks
- Risk or regression analysis
- "Is this code compliant with project rules?"

## Review Policy Sources (in order)
1. `constitution.md` (highest repository policy for this skill)
2. `AGENTS.md` (repo workflow/testing/style constraints)
3. Local package conventions (tests, interfaces, dependency patterns)
4. Go language/runtime best practices
If `constitution.md` is missing, explicitly state that and continue with `AGENTS.md` + Go best practices.

## Execution Modes (Lite / Standard / Strict)
Choose a mode before starting review and state it in the report.
- Default mode: `Standard`
- Declare the selected mode in a dedicated `Review Mode` section.
Mode selection rules:
- Choose `Lite` only when scope is small (typically <=3 files), low-risk, and no security/auth/concurrency/public API changes are involved.
- Choose `Strict` when any high-risk signal exists: security/auth, concurrency/lifecycle, HTTP/API contract changes, persistence/schema changes, exported signature changes, or broad refactors (typically >15 files).
- Use `Standard` for everything else.
### Lite (fast triage)
- Review focus: confirmed defects with high confidence, avoid speculative architecture commentary.
- Minimum execution:
  - Run at least one static tool (`golangci-lint` preferred, else `staticcheck`/`go vet`).
  - Run `go test` for impacted package(s).
  - Run `go test -race` only if concurrency risk is present; if skipped, state reason.
- Baseline/Suppression/SLA gates still apply.
- Finding volume: soft target ≤ 5 findings (severity-tiered; see Workflow step 10).

### Standard (default balanced review)
- Full workflow in this skill applies as written.
- Expected execution when feasible:
  - `golangci-lint run` (config-aware fallback strategy),
  - impacted-package tests,
  - `go test -race` when concurrency/shared state risk exists.
- Finding volume: soft target ≤ 10 findings (severity-tiered; see Workflow step 10).

### Strict (release/security gate)
- Perform deep impact-radius expansion and compatibility checks.
- Minimum execution when feasible:
  - `golangci-lint run` + direct `staticcheck`/`go vet` when not explicitly covered by config.
  - `go test ./...`
  - `go test -race ./...`
- For unresolved findings, provide explicit SLA and, if deferred, complete risk acceptance entry.
- Finding volume: soft target ≤ 15 findings (severity-tiered; see Workflow step 10).

## Mandatory Review Gates
### 1) Execution Integrity Gate
Never claim verification was executed unless it actually ran.
- If `go test` or `go test -race` is not run, you must output:
  - `Not run in this environment`
  - reason
  - exact commands to run
- Do not imply pass/fail for commands you did not execute.

### 2) Baseline Comparison Gate
When prior review context exists (previous PR review comments, prior findings, or known issue list), classify each finding as:
- `new`
- `regressed`
- `unchanged`
- `resolved`
If no baseline is available, state: `Baseline not found`.

### 3) False-Positive Suppression Gate
Before reporting a finding, check whether the risk is already blocked by:
- upstream guard/middleware/policy
- non-user-controlled input path
- framework/runtime safe guarantees
If blocked, do not report as a finding. Put it in a short `Suppressed items` section with rationale.

### 4) Risk Acceptance and SLA Gate
For unresolved findings, include:
- recommended SLA by severity
- optional risk acceptance entry when immediate fix is not chosen
Default SLA guidance:
- `High`: fix or strong mitigation in <= 3 business days
- `Medium`: <= 14 calendar days
- `Low`: next planned iteration
Risk acceptance entry fields:
- finding ID
- owner
- justification
- compensating controls
- expiry/review date

### 5) Go Version Gate
Before recommending version-specific features, check the project's minimum Go version:
- Read `go.mod` for the `go` directive (e.g., `go 1.21`).
- Do NOT recommend features unavailable at the project's Go version as findings.
- If `go.mod` is not found or not readable, state `Go version: unknown` and annotate version-specific recommendations with their minimum required version.
Version-gated features (non-exhaustive):

| Feature | Minimum Go |
|---------|-----------|
| Generics | 1.18 |
| `atomic.Int64`, `atomic.Bool`, typed atomics | 1.19 |
| `context.WithCancelCause`, `strings.Clone`, `errors.Join` | 1.20 |
| `slog`, `context.WithoutCancel`, `context.AfterFunc`, `slices`, `maps`, `min`/`max` builtins | 1.21 |
| `sync.OnceValue`, `sync.OnceFunc` | 1.21 |
| Range-over-func, enhanced loop variable semantics, `math/rand/v2` | 1.22 |
| `iter.Seq`, `unique` package | 1.23 |

### 6) Generated Code Exclusion Gate
Exclude auto-generated files from review findings:
- Files matching: `*.pb.go`, `*_gen.go`, `wire_gen.go`, `*_string.go`, `*_enumer.go`
- Files matching generated mock patterns: `mock_*.go` (from mockgen), `*_mock.go`
- Files containing the standard header: `// Code generated .* DO NOT EDIT`
Rules:
- If a generated file is in the diff, note it in Execution Status as `Excluded (generated)` with the file name.
- Review the generator configuration or template only if the user specifically requests it.

### 7) Reference Loading Gate
When code under review matches trigger patterns (see Appendix), the corresponding reference file **MUST** be loaded before evaluating that category.
- If a trigger pattern fires but the reference was not loaded, pause evaluation and load it.
- This is mandatory, not advisory. Reviewing concurrency patterns without loading `go-concurrency-patterns.md` will miss nuanced patterns and produce lower-quality findings.
- Record which references were loaded in the Execution Status section.

### 8) Change Origin Classification Gate
When reviewing a PR or diff, classify each finding's origin relative to the current change:
- `introduced`: The defective code was added or modified in this PR/diff. The author owns this finding.
- `pre-existing`: The defect exists in code that was NOT changed in this PR/diff. This is historical technical debt, not the author's fault.
- `uncertain`: Origin cannot be determined (e.g., full-file review without diff context, or ambiguous refactoring).
Classification method:
- Check whether the finding's location falls within diff hunks (added or modified lines). If yes → `introduced`.
- If the finding is on an unchanged line within a diff file, or in a file not in the diff (reached via impact-radius expansion) → `pre-existing`.
- If no diff context is available (e.g., reviewing a file or package directly without a PR) → `uncertain`.
Actionability by origin:

| Origin | Merge-blocking? | Action |
|--------|----------------|--------|
| `introduced` | Yes | Must fix or explicitly accept before merge. Counts toward SLA. |
| `pre-existing` | No (unless High severity with immediate security/data-integrity/crash risk) | Report for awareness. Recommend filing as a follow-up issue with tracking link. Do NOT block the PR for historical debt. |
| `uncertain` | Treat as `introduced` | Author may reclassify with evidence (e.g., `git blame` showing the line predates the branch). |
This gate exists so that developers are never blocked by legacy issues they did not introduce, while still surfacing important pre-existing risks for visibility. Pre-existing issues that do not make it into Findings (due to severity or volume cap) MUST still appear in `Residual Risk / Testing Gaps` with a one-line summary — no validated issue should be silently dropped.

## Workflow
0. Select review mode (`Lite|Standard|Strict`) and record mode selection rationale.
   - Check `go.mod` for the project Go version. Record as `Go version: X.Y`.
   - If `go.mod` is not accessible, record `Go version: unknown`.

1. Define scope.
- Confirm files, package, or diff under review.
- If scope is unclear, state assumptions explicitly.
- Apply Generated Code Exclusion Gate: identify and exclude generated files from findings scope. List excluded files in Execution Status.

2. Diff analysis (when reviewing PR/diff).
- Extract changed file list and diff hunks.
- Identify impact radius:
  - Interface changes → search all implementors and callers
  - Exported function signature changes → search cross-package callers
  - Struct field changes → search all construction and usage sites
- Add impact-radius files to review scope (even if not in the diff).
- **Diff-boundary rule**: For impact-radius files NOT in the diff, review ONLY the specific functions and code paths affected by the change. Do not audit the entire file for unrelated pre-existing issues. Pre-existing defects that are High severity (security, data integrity, crash) SHOULD be reported as findings with `Origin: pre-existing` and `Action: follow-up issue`. Medium-severity pre-existing defects in unchanged code MUST be listed in `Residual Risk / Testing Gaps` with a one-line summary so they are not silently lost. Low-severity pre-existing issues may be omitted.
- For refactoring changes (large-scale moves/renames), focus on behavior preservation verification rather than line-by-line review.

3. Gather evidence.
- Read changed files and relevant tests first.
- Prefer reviewing real diff context when available.
- Apply Reference Loading Gate: load reference files matching trigger patterns before evaluating.

4. Run static analysis (when feasible).
- Discover project lint config: check `.golangci.yml` / `.golangci.yaml` first; respect project settings.
- Tool priority with fallback: `golangci-lint run` → `staticcheck ./...` → `go vet ./...`
  - If `golangci-lint` is available, inspect `.golangci*` config for enabled linters.
  - Only mark `go vet` / `staticcheck` as covered when they are explicitly enabled by config.
  - If coverage is unclear (or linter disabled), run the missing tool directly.
  - If `golangci-lint` is not available, try `staticcheck`, then fall back to `go vet`.
- Include tool output in Execution Status section.
- If no tools are installed, state `Not available` and continue.
- Dedup rule: same location + same issue = report once. Prefer tool output as Evidence when available.
- Mode-specific minimum:
  - Lite mode: one static tool minimum.
  - Standard mode: config-aware tool strategy.
  - Strict mode: `golangci-lint` plus direct `staticcheck`/`go vet` when not explicitly covered.

5. Run targeted verification when feasible.
- `go test` for impacted package(s)
- `go test -race` when concurrency/shared state risk exists
- If execution is not feasible, apply Execution Integrity Gate.
- Mode-specific minimum:
  - Lite mode: impacted-package `go test`; `-race` only for concurrency risk.
  - Standard mode: impacted-package `go test`; `-race` for concurrency risk.
  - Strict mode: run `go test ./...` and `go test -race ./...`.

6. Evaluate defect-first.
Use the checklist below. Skip categories that are not applicable to the change under review. For detailed patterns and code examples, see linked reference files.
**Security (High)** → `references/go-security-patterns.md`
- SQL/command/path injection in `database/sql`, `os/exec`, `filepath`
- Hardcoded secrets, insecure TLS (`InsecureSkipVerify`), weak crypto
- `unsafe` package usage without justification
- Sensitive data leaked in logs or error messages
- **AuthN/AuthZ**: JWT validation (algorithm pinning, claims verification), IDOR (ownership checks on resource access), middleware ordering (auth before handler), session management
- **SSRF**: user-controlled URL fetch without host allowlist or private-IP blocking
- **XSS**: `text/template` or `fmt.Fprintf` used for HTML output, `template.HTML()` on user input
- **Rate limiting**: missing on authentication/sensitive endpoints
- **CORS**: reflected `Origin`, wildcard with credentials
- **HTTP security headers**: missing `X-Content-Type-Options`, `X-Frame-Options`, `Strict-Transport-Security`, `Content-Security-Policy`
- **Timing attacks**: `==` comparison on secrets/tokens instead of `crypto/subtle.ConstantTimeCompare`
- **Input validation**: unbounded request body (missing `http.MaxBytesReader`), unchecked integer inputs used for allocation
**Error Handling (High)** → `references/go-error-and-quality.md`
- Ignored errors (`_` discard on error-returning calls)
- Missing error wrapping context (`%w`) — inspect every `return err` path
- `panic` used for recoverable errors
- Direct equality instead of `errors.Is` / `errors.As`
**Concurrency & Lifecycle (High)** → `references/go-concurrency-patterns.md`
- Goroutine leak (no cancellation path)
- Race conditions on shared state (maps, slices, vars)
- Mutex misuse (missing `defer Unlock`, lock copying)
- Unbuffered channel deadlock
- Missing `errgroup` for coordinated goroutine error handling
- `context.Context` not propagated; `context.Value` abuse
- `sync.Pool` / `sync.Once` misuse
- Goroutine missing `defer recover()` — unrecovered panic crashes entire process
- Goroutines created per loop element without concurrency limit (semaphore / `errgroup.SetLimit` / worker pool)
**Test Quality (High)** → `references/go-test-quality.md`
- Tests cover changed behavior and failure modes
- Table-driven test pattern with meaningful subtest names
- `t.Helper()` on test helpers
- Assertion completeness (not just "no error")
- Boundary/edge cases (`nil`, `0`, `1`, empty, max)
- Mock/stub scope minimized
**API & HTTP (High, when applicable)** → `references/go-api-http-checklist.md`
- For server handlers, avoid requiring explicit `r.Body.Close()`; focus on bounded reads and error handling.
- For outbound HTTP clients, require `resp.Body.Close()` on all paths.
- HTTP status codes semantically correct
- Response `Content-Type` set explicitly
- Middleware ordering (auth before handler)
- `http.Server` graceful shutdown
- API backward compatibility preserved
- **gin/echo/chi**: middleware registration order, route conflict detection, `c.Request.Context()` propagation
- **gRPC**: interceptor chain order, metadata propagation, deadline propagation, stream lifecycle
- **wire/fx**: dependency cycle detection, provider signature consistency
**Database & Persistence (High, when applicable)** → `references/go-database-patterns.md`
- `sql.Rows` not closed (resource leak)
- Transaction rollback pattern (`defer tx.Rollback()` + commit override)
- Connection pool misconfiguration (missing `SetMaxOpenConns`, `SetConnMaxLifetime`)
- N+1 queries (loop with individual queries instead of batch)
- Missing context propagation (`db.Query` instead of `db.QueryContext`)
- `sql.ErrNoRows` mishandled as server error
- Null handling without `sql.Null*` types
**Code Quality (Medium)** → `references/go-error-and-quality.md`
- Function >50 lines, nesting >4 levels
- Naked returns in long functions
- Mutable package-level variables
- Interface pollution (unused abstractions)
- Early return pattern (no `else` after error return)
- Nil interface trap (typed nil returned as interface)
- Inconsistent pointer vs value receivers
- Shadowed error variables
- Pointer slice `[]*T` elements not nil-guarded before field access or method call
**Performance (Medium)** → `references/go-performance-patterns.md`
- String concatenation in loops (use `strings.Builder`)
- Slice/map without pre-allocation when size known
- `sync.Pool` misuse or missed opportunity for hot-path allocations
- Unnecessary allocations in hot paths
- Struct field alignment (use `fieldalignment` tool)
- Substring memory retention (use `strings.Clone`)
- Lock scope too wide; mutex where atomic suffices
- Missing buffered I/O (`bufio`) for frequent small writes/reads
- `http.DefaultClient` without timeout or transport tuning
- `regexp.Compile` in hot path instead of package-level compile-once
**Modern Go & Best Practices (Medium)** → `references/go-modern-practices.md`
- Generics vs interface choice appropriateness
- `any` overuse where type constraint is possible
- `slog` for structured logging (Go 1.21+)
- Typed atomic operations (`atomic.Int64` etc., Go 1.19+)
- `context.WithCancelCause` / `context.WithoutCancel` (Go 1.20+/1.21+)
- Goroutine lifecycle: recover panics, leak prevention, concurrency control
- Channel buffer selection semantics
- Error message format (lowercase, no punctuation)
- `context.Background()` vs `context.TODO()` usage
- Package naming (short, lowercase, no underscore)
- Godoc on exported symbols
**Dependency & Module (Low)**
- `go.sum` synchronized
- Stale `replace` directives
- Unnecessary dependencies
- Deprecated standard library functions

7. Apply False-Positive Suppression Gate.

8. Apply Baseline Comparison Gate.

9. Apply Change Origin Classification Gate.
- For each finding, determine whether the defective code was introduced in this PR/diff or existed before.
- Use diff hunks as the primary signal: finding location inside a changed hunk → `introduced`; outside → `pre-existing`.
- When in doubt, use `git blame` or file history to confirm.
- Attach `Origin` and `Action` to each finding.

10. Consolidate, prioritize, and report findings.
- **Merge rule**: When the same conceptual issue (e.g., "missing error wrapping") appears at ≥ 3 locations, report ONE finding with a location list, not N separate findings. Merged findings share the same `Origin` only if all locations have the same origin; otherwise list origins per location.
- **Volume cap — severity-tiered strategy**:
  - Soft targets by mode: Lite ≤ 5, Standard ≤ 10, Strict ≤ 15.
  - **Phase 1 — High**: Report ALL High-severity findings regardless of the soft target. High findings are never dropped by volume cap.
  - **Phase 2 — Medium**: Fill remaining slots (soft target minus High count) with Medium-severity findings, prioritizing `introduced` over `pre-existing`.
  - **Phase 3 — Low**: If slots remain, include Low-severity findings.
  - **Overflow**: If total candidates exceed the soft target after Phase 1, move the lowest-severity candidates that did not make the cut to `Residual Risk / Testing Gaps` with a one-line summary each, and note `N additional lower-priority issues moved to Residual Risk` in Summary.
  - Example: Standard mode, 4 High + 8 Medium found → report 4 High + 6 Medium as findings, move 2 Medium to Residual Risk.
- **Sort order**: `introduced` before `pre-existing` within the same severity level. High → Medium → Low.
- Every finding must include policy mapping, file references, `Origin`, and `Action`.
- Apply Go Version Gate: remove or downgrade findings that recommend features above the project's Go version.

11. Add risk acceptance/SLA recommendations.

## Severity Rubric
### High
Likely functional breakage, data loss/corruption, security risk,
race/deadlock, or significant production instability.

### Medium
Meaningful maintainability or reliability risk that is not immediate critical failure.

### Low
Clarity/readability improvement or non-critical consistency gap.

## Evidence Rules
- Do not report speculative findings as confirmed defects.
- Every finding must include:
  - exact location (`path:line`)
  - concrete impact
  - why current behavior is risky/incorrect
  - actionable fix direction
- Clearly label inference vs directly observed behavior.

### Anti-examples (DO NOT report these)
Load `references/go-review-anti-examples.md` for the full list (this file is always loaded for any review — see Appendix trigger table). Before suppressing a finding using an anti-example, you **MUST** quote specific code evidence satisfying the anti-example's stated precondition. Category match alone is not sufficient — if you cannot cite evidence, the finding must be reported.
- "This function could panic if nil is passed" — when the caller is internal and always passes non-nil
- "Missing error handling on json.Marshal" — when marshaling a known-safe struct with no interface fields
- "Missing error wrapping with %w" — when the caller already wraps the error; adding another layer would produce redundant context like `"create user: insert user: insert row: ..."`
- "Potential race condition on this map" — when the map is only accessed within a single goroutine or is created and consumed within a single function scope
- "Should use errgroup instead of WaitGroup" — when no error propagation is needed and goroutine count is small and fixed
- "Should use sync.Pool" — when the object is small and allocated infrequently
- "Should pre-allocate slice" — when the slice is small (< 16 elements) or size is truly unknown
- "Struct fields should be reordered for alignment" — when the struct has < 4 fields or savings < 8 bytes
- "Should use strings.Clone for substring" — when both the substring and parent string are short-lived locals eligible for GC at the same scope
- "Should use slog instead of log" — when the project's `go.mod` targets Go < 1.21
- "Should use atomic.Int64 instead of atomic.AddInt64" — when the project's `go.mod` targets Go < 1.19
- "Missing context propagation" — when the function is synchronous, short-lived, performs no I/O, and has no cancellable work
- "Should use generics here" — when only one concrete type is used throughout the codebase
- "Exported function missing godoc" — when the symbol is in an `internal/` package not intended for external consumers
- "Function too long (>50 lines)" — when the body is a straightforward table-driven switch, a sequential pipeline with no nesting, or a single select/case block
Grey-area guidance:
- `errors.Is` vs `==`: direct `==` against a sentinel from the same package is acceptable; cross-package must use `errors.Is`
- `context.TODO()` vs `context.Background()`: in `main()` or top-level initialization, `context.Background()` is correct; `TODO()` is only appropriate when context propagation is planned but not yet implemented
- `interface{}` → `any`: pure alias rename is cosmetic; report only if part of a broader modernization effort, never as a standalone finding
- `defer f.Close()` ignoring error: acceptable for **read-only** file opens; flag only for **write** operations where close flushes buffered data

## Output Format (Required)
### Review Mode
- `Lite|Standard|Strict`
- mode selection rationale (1-2 lines)

### Findings
List findings first, ordered by severity.
#### [High|Medium|Low] Short Title
- **ID:** `REV-001`
- **Origin:** `introduced|pre-existing|uncertain`
- **Baseline:** `new|regressed|unchanged` (or `N/A` if baseline missing)
- **Principle:** `constitution.md` clause (or `N/A` with reason)
- **Location:** `path:line` (or location list for merged findings)
- **Impact:** user/business/runtime impact
- **Evidence:** concrete observed behavior
- **Recommendation:** specific and minimal fix direction
- **Action:** `must-fix` | `follow-up issue` (aligned with Origin actionability table)

### Suppressed Items
Only include items filtered by the suppression gate.
#### [Suppressed] Short Title
- **Reason:** upstream guard / non-user-controlled input / framework safety
- **Location:** `path:line`
- **Residual risk:** short note

### Execution Status
- `Go version`: `X.Y` (from `go.mod`) or `unknown`
- `Excluded (generated)`: list of generated files excluded, or `None`
- `References loaded`: list of reference files loaded for this review
- `go vet`: `PASS|FAIL|Not available|Covered by golangci-lint config`
- `staticcheck`: `PASS|FAIL|Not available|Covered by golangci-lint config`
- `golangci-lint`: `PASS|FAIL|Not available`
- `go test`: `PASS|FAIL|Not run in this environment`
- `go test -race`: `PASS|FAIL|Not run in this environment`
- If not run, include reason and exact commands.

### Risk Acceptance / SLA
- SLA recommendation by severity in this review
- Optional risk acceptance entries for deferred fixes:
  - finding ID
  - owner
  - compensating control
  - expiry/review date

### Open Questions
Only include blockers that materially affect confidence.

### Residual Risk / Testing Gaps
This section captures items that are valuable context but do not belong in Findings:
1. **Verification gaps**: tools or tests that were not run, and the reason.
2. **Volume-cap overflow**: findings that were evaluated and confirmed but displaced by the severity-tiered volume cap (see Workflow step 10). List each with a one-line summary (`severity | origin | location | short description`) so no validated issue is silently dropped.
3. **Pre-existing issues (non-High)**: Low/Medium-severity pre-existing defects found in impact-radius files (not in the diff) go here with a one-line summary each. High-severity pre-existing issues may be promoted to Findings with `Origin: pre-existing`.
4. **Areas not covered**: parts of the change whose risk could not be assessed (e.g., missing test fixtures, untraceable dynamic dispatch).

### Summary
1-3 lines only, after findings. Include origin breakdown: `X introduced / Y pre-existing / Z uncertain`.
If findings were capped by volume limit, note: `N additional lower-priority issues moved to Residual Risk`.

### Example Output Reference

When you need to verify report formatting or check what a complete review looks like:
→ Load `references/example-output.md` for a full example covering Review Mode, Findings with all required fields (ID, Origin, Baseline, Principle, Location, Impact, Evidence, Recommendation, Action), and Summary.

## No-Finding Case
If no issues are found:
- Explicitly say: `No actionable findings found.`
- Still provide:
  - `Review Mode`
  - `Execution Status`
  - baseline status (`resolved` list if available, otherwise `Baseline not found`)
  - residual risks/testing gaps

## Review Discipline
- Prefer small, precise, defensible findings over generic advice.
- Findings are the primary deliverable.
- Recommend tests whenever behavior changes are proposed.
- Execute ALL checklist categories regardless of how many High findings have already been identified; the presence of multiple High findings does not reduce the obligation to complete remaining categories; finish the full checklist scan before consolidating findings.

## Skill Maintenance
Run regression checks for this skill with:
```bash
bash "<path-to-skill>/scripts/run_regression.sh"
```

## Appendix: Reference Loading Triggers
**This is a mandatory gate** (see §7 Reference Loading Gate). Use the table below as a compact trigger map; detailed patterns live in the reference files themselves.

| Reference | Representative triggers |
|---|---|
| `references/go-review-anti-examples.md` | Any review (always loaded) |
| `references/pr-review-quick-checklist.md` | Any PR or diff review |
| `references/go-security-patterns.md` | auth/token flows, hardcoded string literals, SQL/command/path use, outbound fetches, TLS, HTML/template output, upload/body limits |
| `references/go-concurrency-patterns.md` | `go func`, channels, mutexes, wait groups, `errgroup`, lifecycle or cancellation code |
| `references/go-error-and-quality.md` | ignored errors, `panic(`, `errors.Is/As`, naked returns, receiver or shadowing issues |
| `references/go-test-quality.md` | `_test.go`, `httptest`, `testing.B/F`, `testdata/` |
| `references/go-api-http-checklist.md` | `net/http`, handlers, servers, `gin`/`echo`/`chi`, gRPC, `pb.` or `proto.` |
| `references/go-database-patterns.md` | `database/sql`, `pgx`, `sqlx`, `gorm`, `ent`, query/tx/rows code |
| `references/go-performance-patterns.md` | hot loops, builders, preallocation, `sync.Pool`, atomics, regex, client or JSON hot paths |
| `references/go-modern-practices.md` | generics, `any`, `slog`, typed atomics, modern context helpers, `slices`/`maps` |
