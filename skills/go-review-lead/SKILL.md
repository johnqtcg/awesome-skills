---
name: go-review-lead
description: Orchestrate a comprehensive Go code review by triaging code changes, dispatching vertical review skills (security, concurrency, error, logic, performance, quality, test) as parallel agents, then consolidating results into a unified report. Use for full Go PR review or comprehensive code review. Replaces the monolithic go-code-reviewer with focused parallel analysis.
---

# Go Review Lead — Orchestrator

## Purpose

Triage Go code changes and dispatch vertical review skills as parallel agents, then consolidate their findings into a unified report. This skill is the entry point for comprehensive Go code review.

**Critical rule**: The Lead Agent only **triages and consolidates**. It never reviews code itself. All code review happens in vertical skill agents.

## When To Use
- Full Go PR review or comprehensive code review requested
- User asks for "Go code review" without specifying a specific dimension
- Need to cover multiple review dimensions in one pass

## When NOT To Use
- User explicitly asks for single-dimension review (e.g., "check security only") → dispatch the specific vertical skill directly
- Non-Go code review

## Workflow

### Step 1: Analyze Scope

Run the following commands to gather triage data:
```bash
git diff --name-only HEAD~1   # changed files
git diff HEAD~1               # full diff
```
Identify:
- Changed `.go` files (production) and `_test.go` files (separate tracking)
- New files added (stronger signals — more domains likely affected)
- Impact radius: exported interface changes → search implementors; exported signature changes → search callers

**Raw snippet fallback**: If no git context is available (user pasted a code snippet with no file path or diff):
1. Write the snippet to `$TMPDIR/review_snippet.go`
2. Run all grep-based triage (Phase 0 + Phases 1-4) against the temp file
3. Apply the same dispatch validation grep below
4. Clean up the temp file after review

### Step 1.5: Select Review Depth (Lite / Standard / Strict)

After analyzing scope, select the review depth **before** triage. State the selected depth and reasoning in the report's `Review Mode` section.

#### Selection Rules

| Depth | Trigger Condition | Agent Policy | Finding Soft Cap |
|-------|------------------|-------------|-----------------|
| **Lite** | Changed files ≤ 3 **AND** none of the high-risk signals below | Only always-dispatch: go-quality-reviewer + go-logic-reviewer (2 agents) | 5 |
| **Standard** | Does not qualify for Lite or Strict (default) | Normal 4-phase triage, dispatch as needed | 10 |
| **Strict** | Any high-risk signal present **OR** > 15 changed Go files **OR** user explicitly requests comprehensive/strict review | Full 4-phase triage + Dispatch Validation Grep safety net; Residual Risk section required non-empty | 15 |

**High-risk signals** (any one triggers Strict):
- Security/auth code changed (`auth/`, `middleware/`, `token/`, `session/`, `jwt/`, `oauth/`)
- Concurrency primitives added/modified (`go func`, `sync.`, `chan`, `errgroup`)
- HTTP/API contract changed (exported handler signature, route registration, response schema)
- Persistence/schema changed (`sql`, migration files, ORM model changes)
- Exported function/interface signature changed
- Broad refactor (> 15 production Go files)

**Lite safeguard**: Even in Lite mode, if the 2 always-dispatched agents collectively report ≥ 3 High findings, **escalate to Standard** and re-triage with the full 4-phase process. State the escalation in the report.

#### Depth-Specific Dispatch Behavior

**Lite**:
- Skip Steps 1.5b (Compile Pre-check) and 1.6 (Dispatch Validation Grep)
- Skip Step 2 (4-phase triage) — only dispatch go-quality-reviewer + go-logic-reviewer
- Sub-agent prompt appendix: `"Lite mode: focus on high-confidence defects only, soft cap 3 findings per agent"`

**Standard**:
- Execute all steps as documented (compile pre-check, 4-phase triage, dispatch validation grep)
- Apply conditional scope narrowing (Step 3) to reduce cross-agent duplication

**Strict**:
- Execute all steps; do NOT apply scope narrowing — cross-agent duplication serves as cross-validation safety net
- Sub-agent prompt appendix: `"Strict mode: full checklist, no item skipped, report all confirmed findings"`

### Step 1.5b: Compile Pre-check (Standard / Strict Only)

Before triage, run a quick compilation check to catch syntax and type errors that every agent would otherwise redundantly report:

```bash
# For file-based review:
cd <repo_root> && go build ./... 2>&1 | head -30

# For raw snippet:
cd $TMPDIR && go build review_snippet.go 2>&1
```

**If compile errors exist**:
1. Lead Agent reports compile errors directly as High findings (category: Compile) — these do not need domain expertise
2. Include them in the final report with IDs starting from REV-001
3. Proceed with triage and dispatch for **non-compile issues** — sub-agents still review logic, concurrency, performance, etc.
4. Add to each sub-agent's dispatch prompt: `"Note: compile errors (listed below) are already reported by Lead. Do NOT re-report them. Focus on runtime, logic, and domain-specific issues only."` followed by a brief list of the compile error locations

**If no compile errors**: proceed normally.

**Rationale**: In the getBatchUser benchmark case, 3 compile errors were independently reported by 4 agents (12 raw findings → 3 merged), consuming ~35% of the redundant token budget. Pre-checking eliminates this entire class of duplication.

### Step 1.6: Dispatch Validation Grep (Safety Net — Standard / Strict Only)

**Before finalizing which skills to skip**, run quick grep for each conditional skill's top trigger patterns against all changed files (or the temp snippet file). If ANY pattern hits, **override the skip decision** and dispatch that skill.

This catches triage logic gaps where manual Phase 1-4 analysis misses a pattern.

```bash
# Run these greps against all changed .go files:
# Performance triggers:
grep -l 'make\(\[\]\|append(' <files>
grep -l 'for.*range.*\.\(Query\|Exec\|Get\|Set\)' <files>
# Concurrency triggers:
grep -l 'go func\|go .*(' <files>
grep -l 'sync\.\|chan ' <files>
# Security triggers:
grep -l '"database/sql"\|"os/exec"\|Sprintf.*SELECT\|Sprintf.*INSERT' <files>
grep -l 'http\.Handle\|http\.ListenAndServe' <files>
# Error triggers:
grep -l '\.Close()\|tx\.\|resp\.Body\|sql\.Rows' <files>
# Test triggers:
grep -l '_test\.go' <file_list>
```

| Skill | Validation Patterns (ANY hit → dispatch) |
|-------|------------------------------------------|
| go-performance-reviewer | `make\(\[\]`, `append\(`, `for.*range.*\.\(Query\|Exec\)` |
| go-concurrency-reviewer | `go\s+func`, `sync\.`, `chan\s`, `make\(chan` |
| go-security-reviewer | `"database/sql"`, `"os/exec"`, `http\.Handle`, `Sprintf.*SELECT` |
| go-error-reviewer | `\.Close\(\)`, `tx\.`, `resp\.Body`, `sql\.Rows`, `panic\(` |
| go-test-reviewer | `_test\.go` in changed file list |

**Override rule**: If validation grep hits but Phases 1-4 did not trigger the skill, add it with rationale: `"Dispatch-validation grep override: {pattern} found in {file}"`.

### Step 2: Triage — Select Vertical Skills (Multi-Phase)

Execute the 4 triage phases in order. **Each phase independently contributes dispatch decisions — run all 4 even if earlier phases already trigger agents.**

Two agents are **Always** dispatched regardless of phases:
- **go-quality-reviewer** — baseline lint/style for any Go change
- **go-logic-reviewer** — baseline correctness check for any behavior change

For the remaining 5, use the phases below:

---

#### Phase 1: Import Analysis (Strongest Signal)

Scan `import` blocks across ALL changed files (not just diff lines):
```bash
grep -n '"database/sql"\|"os/exec"\|"net/http"\|"sync"\|"crypto/\|"math/rand"\|"text/template"\|"html/template"' <changed_files>
grep -n 'errgroup\|singleflight\|semaphore' <changed_files>
```

| Import present | → Dispatch |
|----------------|-----------|
| `"database/sql"` | security + error + performance |
| `"os/exec"` | security |
| `"net/http"` (as server — `http.Handler`, `http.HandleFunc`) | security |
| `"net/http"` (as client — `http.Get`, `http.NewRequest`, `http.Client`) | security + performance |
| `"crypto/md5"`, `"crypto/sha1"`, `"math/rand"` | security |
| `"sync"`, `"sync/atomic"` | concurrency |
| `"golang.org/x/sync/..."`, `errgroup`, `singleflight` | concurrency |
| `"html/template"`, `"text/template"` with user input context | security |

---

#### Phase 2: Diff Pattern Scan (Changed Lines Only)

Scan only lines added/modified in the diff (`^+` lines, excluding `^+++`):
```bash
git diff HEAD~1 | grep '^+[^+]'
```

| Pattern in added/modified lines | → Dispatch |
|---------------------------------|-----------|
| `go func`, `make(chan`, `<-chan`, `chan<-` | concurrency |
| `sync\.Mutex`, `sync\.RWMutex`, `sync\.WaitGroup`, `select {` | concurrency |
| `sql\.Rows`, `tx\.Begin`, `tx\.Commit`, `tx\.Rollback` | error |
| `resp\.Body`, `defer.*\.Close()`, `panic(` | error |
| `make\(\[\][^,)]+,[^,)]+\)` (2-arg slice, no capacity: `make([]T, n)`) | performance |
| `append\(` co-occurring with `make\(\[\]` in same function/file | performance |
| `make(map` (any map literal, with or without size hint) | performance |
| `strings\.Builder`, `bytes\.Buffer` replacing string concat | performance |
| loop body containing `.Query`, `.Exec`, `.Get`, `.Set` (DB/cache) | performance |
| hardcoded string matching `[A-Za-z0-9+/]{20,}=` or `sk-`, `pk-`, `secret` | security |
| `filepath\.Join.*r\.`, `os\.Open.*r\.`, user input flowing into file paths | security |
| `tls\.Config{`, `InsecureSkipVerify` | security |

---

#### Phase 3: File Path Heuristics

Check the paths of changed files — certain packages indicate domain risk regardless of diff patterns:

| File path contains | → Dispatch |
|-------------------|-----------|
| `auth/`, `middleware/`, `token/`, `session/`, `jwt/`, `oauth/`, `permission/` | security |
| `handler/`, `server/`, `api/`, `router/`, `endpoint/` | security |
| `worker/`, `pool/`, `queue/`, `scheduler/`, `job/`, `pipeline/` | concurrency |
| `repo/`, `store/`, `dao/`, `repository/`, `db/` | error + performance |
| `cache/`, `redis/`, `memcache/` | performance |

---

#### Phase 4: Change Scope Assessment

| Condition | → Action |
|-----------|---------|
| Any `_test.go` file in diff | dispatch go-test-reviewer |
| New `.go` file added (not test) | add error (new code has no established error patterns yet) |
| > 5 production Go files changed | verify error is already dispatched; add if not |
| Exported `interface` definition changed | ensure logic is dispatched (always is, but flag in rationale) |
| `go.mod` / `go.sum` changed (new dependency) | check new import domain → re-run Phase 1 for new package |

---

#### Triage Output — Explicit Reasoning Required

After all 4 phases, write out the dispatch decision with reasoning:

```
Triage result:
- Always: go-quality-reviewer, go-logic-reviewer
- Phase 1 (imports): go-security-reviewer (database/sql found), go-error-reviewer (database/sql → sql.Rows risk), go-performance-reviewer (database/sql → N+1 risk)
- Phase 2 (diff patterns): go-concurrency-reviewer (go func at worker.go:34)
- Phase 3 (file paths): [none additional]
- Phase 4 (scope): go-test-reviewer (_test.go files present)
- Skipped: [list skipped agents with explicit reason, e.g., "go-test-reviewer would be skipped but triggered by Phase 4"]
```

**No blanket fallback**: If an agent is not triggered by any phase, do NOT dispatch it. Absence of trigger signals = absence of domain risk in this change. Record the skip reason explicitly so the review consumer can judge whether the skip was correct.

### Step 3: Dispatch Parallel Agents

> **CRITICAL — TRUE PARALLEL EXECUTION REQUIRED**
> Issue **ALL** selected Agent tool calls in a **single response message** — do NOT call one agent, wait for it to finish, then call the next. Every selected agent must appear as a separate `Agent` tool call block within the same turn. The runtime executes them concurrently only when dispatched together. Serial dispatch defeats the entire architecture.

Launch selected skills as **parallel agents** using the Agent tool. Each agent receives:
1. The files/diff to review
2. Instruction to follow its SKILL.md and its **Grep-Gated Execution Protocol**
3. The review scope (files list or diff)
4. Depth-specific appendix (Lite/Standard/Strict — see Step 1.5)
5. **Conditional scope narrowing instructions** (Standard mode only — see below)

#### Conditional Scope Narrowing (Standard Mode Only)

In Standard mode, go-logic-reviewer's 10 semantic items overlap with specialized agents' checklists. When a specialized agent is already dispatched, tell go-logic-reviewer to **skip the overlapping items** to reduce redundant findings.

| If this agent is dispatched | go-logic-reviewer skips these items |
|----------------------------|-------------------------------------|
| go-concurrency-reviewer | Goroutine lifecycle / synchronization correctness |
| go-error-reviewer | Error propagation path completeness |
| go-performance-reviewer | Resource allocation efficiency |

Append to go-logic-reviewer's dispatch prompt:
```
Scope narrowing (Standard mode): The following dimensions are covered by
dedicated agents in this review — skip checklist items that fall under these
categories to avoid duplicate findings:
- [list dispatched specialized dimensions, e.g., "Concurrency (go-concurrency-reviewer dispatched)", "Error handling (go-error-reviewer dispatched)"]
Focus your analysis on: state machine transitions, boundary conditions,
return value contracts, nil/zero-value assumptions, algorithm correctness,
and any logic items NOT covered by the dispatched specialists.
```

**Important constraints**:
- **Strict mode**: Do NOT apply scope narrowing — all agents run full checklists for cross-validation
- **Lite mode**: Not applicable (only 2 agents, no specialized agents to overlap with)
- **Fallback**: If a specialized agent is NOT dispatched (e.g., go-concurrency-reviewer skipped), go-logic-reviewer MUST retain those items — they are its responsibility as the fallback

Example dispatch prompt for each agent:
```
Review the following Go code changes using the go-{domain}-review skill.
Files: [file list]
Diff context: [diff or "read the files directly"]
Follow your SKILL.md exactly — including the Grep-Gated Execution Protocol.
Run grep pre-scan on all grep-gated checklist items BEFORE semantic analysis.
Return your complete findings report with grep audit line in Execution Status.
[Depth appendix: "Lite mode: ..." or "Strict mode: ..." or omit for Standard]
[Compile pre-check note if applicable: "Compile errors already reported by Lead: ..."]
[Scope narrowing for go-logic-reviewer in Standard mode if applicable]
```

#### Sub-Agent Reporting Contract

- Sub-agents report only **FOUND** items (grep-confirmed + semantic-confirmed, or semantic-only confirmed)
- NOT FOUND items (grep MISS) are **silently excluded** from reports — do not list them
- Each sub-agent MUST include in Execution Status: `Grep pre-scan: X/Y items hit, Z confirmed as findings`
- Lead uses this audit line to verify coverage: if 0/Y hit on a dispatched agent, note in Residual Risk

### Step 4: Consolidate Results

After all agents return, collect each agent's full response. For each agent response:
- Extract all findings (FOUND items) for deduplication and merging
- Extract the `Execution Status` block — specifically the `Grep pre-scan: X/Y hit, Z confirmed` line — and record it for the Per-skill grep audit in the final Execution Status section

Then merge their reports:

1. **Deduplicate and merge**: When multiple agents flag the same location:
   - **Different issues at same location** → keep both (e.g., Security: "SQL injection at repo.go:67" + Error: "missing error check at repo.go:67" — distinct root causes)
   - **Same issue, different domains** → merge into the more specific finding (e.g., Error: "resp.Body not closed" + Logic: "resource not closed" → keep Error's finding)
   - **Same issue, different severities** → merge and **promote to the highest severity**. For example: Performance flags "N+1 query at repo.go:30" as Medium + Security flags "unbounded query at repo.go:30" as High → merge into High, combine evidence from both agents

2. **Sort by severity descending**: Final output MUST be ordered High → Medium → Low. Within the same severity level, sort by origin (`introduced` before `pre-existing`), then by category alphabetically.

3. **Apply volume cap** (severity-tiered, depth-dependent):
   - Phase 1: Report ALL High-severity findings (never capped regardless of depth)
   - Phase 2: Fill to soft target with Medium findings (Lite: ~5, Standard: ~10, Strict: ~15)
   - Phase 3: If slots remain, include Low findings
   - Overflow → move to Residual Risk section with one-line summary each

4. **Apply change origin classification** (when reviewing PR/diff):
   - `introduced`: finding on code added/modified in this PR
   - `pre-existing`: finding on unchanged code (discovered via impact radius)

5. **Assign unified IDs**: Renumber findings sequentially (REV-001, REV-002...) in severity-descending order, preserving the original skill prefix (SEC/CONC/ERR/LOGIC/PERF/QUAL/TEST) for traceability. REV-001 is always the highest-severity finding.

## Output Format

Output as plain text — do NOT use markdown headers (`#`, `##`, `###`) or bold (`**`). Use `---` as section dividers. This format renders correctly in terminal (Claude Code CLI) and IDE environments alike.

---
Review Mode

- Review depth: Lite | Standard | Strict (with selection rationale)
- Compile pre-check: PASS | FAIL (N compile errors reported as REV-001..REV-N) | Skipped (Lite mode)
- Dispatched skills: [list]
- Skipped skills: [list with reasons]
- Scope narrowing: [Applied to go-logic-reviewer: skipped {dimensions} | Not applied (Strict/Lite) | N/A]
- Triage rationale: 1-2 lines explaining why conditional skills were included or excluded

---
Findings

Merged from all agents, sorted descending by severity (High → Medium → Low), then by origin (introduced → pre-existing), then by category alphabetically.

[High|Medium|Low] Short Title

- ID: REV-NNN (original: SEC-001 / CONC-001 / etc.)
- Origin: introduced | pre-existing | uncertain
- Baseline: new | regressed | unchanged (compare against base branch; uncertain if diff unavailable)
- Principle: N/A (no constitution.md) | or cite specific clause
- Category: Security | Concurrency | Error | Logic | Performance | Quality | Test
- Location: path:line (or location list for merged findings)
- Impact: user/business/runtime impact
- Evidence: concrete code path or tool output showing the issue
- Recommendation: specific and minimal fix direction
- Action: must-fix | follow-up | needs-clarification

---
Suppressed Items

Merged from all agents. Only include items filtered by anti-example gates.

[Suppressed] Short Title
- Reason: which agent suppressed it + anti-example matched
- Location: path:line
- Residual risk: brief note on remaining exposure

---
Execution Status
- Go version: X.Y (from go.mod) or unknown
- Dispatch validation grep: X overrides applied (list patterns that triggered overrides, or "no overrides needed")
- Skills dispatched: [list]
- Per-skill grep audit:
  - go-security-reviewer: Grep pre-scan X/Y hit, Z confirmed | gosec PASS|FAIL|Not available
  - go-concurrency-reviewer: Grep pre-scan X/Y hit, Z confirmed | go test -race PASS|FAIL|Not run
  - go-error-reviewer: Grep pre-scan X/Y hit, Z confirmed
  - go-performance-reviewer: Grep pre-scan X/Y hit, Z confirmed
  - go-quality-reviewer: Grep pre-scan X/Y hit, Z confirmed | golangci-lint PASS|FAIL|Not available
  - go-test-reviewer: Grep pre-scan X/Y hit, Z confirmed
  - go-logic-reviewer: Semantic-only (no grep patterns)
  - [only list dispatched agents]
- Excluded (generated): list or None

---
Risk Acceptance / SLA
- SLA recommendation by severity: High = must-fix before merge; Medium = follow-up within 2 weeks; Low = discretionary
- Optional risk acceptance entries for deferred fixes:
  - Finding ID: REV-NNN
  - Owner: [name]
  - Compensating control: [description]
  - Expiry/review date: YYYY-MM-DD

---
Open Questions

Only include blockers that materially affect review confidence. Omit section if none.

---
Residual Risk / Testing Gaps

1. Verification gaps: tools not run and why
2. Volume-cap overflow: findings confirmed but displaced by cap — each as severity | origin | location | short description
3. Pre-existing issues (non-High): Low/Medium pre-existing defects found in impact-radius files (not in diff) — one-line summary each
4. Areas not covered: parts of the change whose risk could not be assessed

---
Summary

X introduced / Y pre-existing / Z uncertain. N High / M Medium / L Low.
If capped: "N additional lower-priority issues moved to Residual Risk."

## Example Output (End-to-End)

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

## Consolidation Rules

- **Lead never reviews code** — all findings come from vertical agents
- **Never drop High findings** — volume cap only affects Medium/Low
- **Preserve agent evidence** — copy findings verbatim, only renumber IDs
- **If an agent returns no findings**, note it in Review Mode section, not in Findings
- **If an agent fails to run**, note in Execution Status with reason

## No-Finding Case
If all agents return no findings: state `No actionable findings found across all review dimensions.` Still output Review Mode, Execution Status, and Residual Risk sections.