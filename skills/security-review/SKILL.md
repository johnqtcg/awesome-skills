---
name: security-review
description: Perform exploitability-first security reviews for code changes (auth, input, secrets, API, data, concurrency, container, third-party, and dependency risk), with mandatory evidence, suppression discipline, scope-based review depth, and Go-specific secure-coding gates.
allowed-tools: Read, Grep, Glob, Bash(go vet*), Bash(go build*), Bash(gosec*), Bash(govulncheck*), Bash(semgrep*), Bash(npm audit*)
---

# Security Review

Find exploitable risks early, provide concrete fixes, and keep recommendations practical for engineering delivery.

## Quick Reference

| If you need to… | Go to |
|---|---|
| Choose review depth (Lite / Standard / Deep) | §Review Depth Selection |
| Run a fast Go security scan (skip Gate B/C/E) | Lite depth → Load `references/scenario-checklists.md` only |
| Run a full Go security review with all gates | Standard/Deep → Load `references/go-secure-coding.md` + `references/scenario-checklists.md` |
| Review Node.js / TypeScript code | Load `references/lang-nodejs.md` + `references/scenario-checklists.md` |
| Review Java / Spring code | Load `references/lang-java.md` + `references/scenario-checklists.md` |
| Review Python / FastAPI / Django code | Load `references/lang-python.md` + `references/scenario-checklists.md` |
| Calibrate severity (P0–P3) or confidence | Load `references/severity-calibration.md` |
| Suppress a false positive correctly | §False-Positive Suppression Rules |

## Review Principles

- Prioritize exploitable risk over style issues.
- Ground every claim in code/config/runtime evidence.
- Distinguish confirmed vulnerabilities from hypotheses.
- Provide reproducible proof for high-risk findings.
- Map findings to standards for auditability.
- If evidence is missing, state `Not found in repo`.
- Fail closed: if a mandatory gate cannot be executed, state it explicitly and do not claim full coverage.

## Evidence Confidence (Mandatory)

Each finding must include one confidence label:

- `confirmed`: vulnerable path proven by code and/or reproducible execution.
- `likely`: strong evidence with one missing runtime assumption.
- `suspected`: weak evidence requiring additional data.

Do not report `P0/P1` without `confirmed` or explicit justification.

## False-Positive Suppression Rules

Before publishing a finding, check suppression conditions:

1. Existing upstream guard already blocks the path.
2. Input is not attacker-controlled at trust boundary.
3. Sink is parameterized/safely encoded by framework guarantees.
4. Environment-only theoretical risk without reachable path.

If suppressed:

- keep a short note under `Open questions / assumptions`
- mark as `suppressed` (not a finding)
- explain blocking control and residual risk

## Severity Model

- `P0 Critical`: immediate compromise (RCE, auth bypass, key exfiltration, payment tampering).
- `P1 High`: strong exploit path (injection, IDOR, sensitive data leak, broken authz).
- `P2 Medium`: meaningful defense gap likely to become exploitable.
- `P3 Low`: hardening improvement.

## Remediation SLA (Default)

Use this unless the team provides stricter policy:

- `P0`: mitigation immediately, full fix within 24h.
- `P1`: fix within 3 business days.
- `P2`: fix within 14 calendar days.
- `P3`: backlog with planned milestone.

If SLA differs, state the project policy explicitly.

## Baseline Diff Mode (Mandatory When Baseline Exists)

When previous review artifacts exist, compare current findings with baseline and output:

- `new`: not present in baseline
- `regressed`: existed before and severity/confidence worsened
- `unchanged`: still present without material change
- `resolved`: removed since baseline

If no baseline exists, state `Baseline not found`.

## Review Depth Selection (Mandatory First Step)

Before starting, classify review depth based on change scope:

| Signal | Depth | Process |
|--------|-------|---------|
| Changed files ≤ 3 AND no trust-boundary / auth / crypto / payment paths touched | **Lite** | Steps 1-4, Gate A, Gate D (triage only), suppression filter, findings, Gate F |
| Changed files 4-15 OR any security-sensitive path touched | **Standard** | Full 15-step process |
| Changed files > 15 OR new service / new external integration / auth redesign | **Deep** | Full 15-step process + extended call-graph tracing beyond immediate callers |

Trigger signals that **force Standard or Deep** regardless of file count:

- Auth/authz middleware or handler changes
- Crypto, TLS, or secret-management code changes
- Payment/financial transaction paths
- New HTTP/gRPC endpoints exposed
- Dockerfile, K8s manifest, or CI pipeline security config changes
- `go.mod` / `go.sum` dependency changes
- Any file under `internal/auth/`, `internal/crypto/`, `pkg/security/`, or equivalent

When Lite is selected, record: `Review depth: Lite (N files changed, no security-sensitive paths). Gates B/C/E skipped per scope policy.`

### Fast Pass (Lite Only)

If ALL conditions are met during Lite triage:

1. All 10 Gate D domains classify as N/A
2. All 11 scenario checklists classify as N/A
3. Secret pattern sweep is clean
4. No constructor/acquisition calls found in Gate A

Then output a condensed report instead of the full Output Contract:

- Review depth + rationale (mandatory)
- `Fast Pass: all domains N/A, all scenarios N/A, no findings.`
- JSON summary with `pass: true` and zero counts (mandatory)
- Gate F uncovered risk list (mandatory, may be empty)

This avoids verbose N/A tables for truly benign changes while preserving audit traceability.

## Fixed Process + Mandatory Gates

The following process is mandatory for Standard and Deep reviews. Lite reviews follow the subset noted above.

1. Scope the change and select review depth.
2. Map trust boundaries.
3. Run scenario checks.
4. Run focused automation checks.
5. Run `Gate A`: constructor-release pairing audit.
6. Run `Gate B`: Go resource inventory scan.
7. Run `Gate C`: third-party lifecycle contract verification.
8. Run `Gate D`: Go secure-coding 10-domain coverage (for Go repos).
9. Verify exploitability.
10. Run `Gate E`: second-pass falsification review.
11. Apply suppression filter.
12. Compare with baseline (if available).
13. Report findings first.
14. Provide remediation plan and risk acceptance entries.
15. Provide `Gate F`: uncovered risk list.

If any mandatory gate cannot be executed, record it under `Uncovered Risk List` and downgrade confidence where applicable.

### Applicability-First Execution (Mandatory)

To control review cost and avoid unnecessary depth, execute in two phases:

- `Phase 1 (triage)`: classify each Go domain as `Applicable` or `N/A` from changed files + adjacent call paths.
- `Phase 2 (deep review)`: run detailed checks and domain-specific tooling only for `Applicable` domains.

Rules:

- `N/A` is allowed only with a one-line reason tied to code evidence.
- Do not mark `N/A` if there is any trigger signal (relevant imports, touched config, related middleware, DB/crypto/TLS paths, dependency changes).
- Domain-specific reproducer/tests are required only for `Applicable` domains with findings.

#### N/A Judgment Examples

| Domain | Scenario | Verdict | Rationale |
|--------|----------|---------|-----------|
| Randomness safety | Change adds a new CLI `--dry-run` flag; no token/session/nonce code touched | `N/A` | No import of `math/rand` or `crypto/rand` in changed files or callers |
| Injection + SQL | Change updates a Markdown documentation file only | `N/A` | No `.go` files changed; no SQL/exec/template paths reachable |
| TLS safety | Change modifies HTTP handler logic but no TLS config, `http.Client`, or dial code touched | `N/A` | No `tls.Config`, `InsecureSkipVerify`, or custom transport in changed scope |
| Concurrency safety | Change adds a pure function with no shared state, goroutines, or channels | `N/A` | Function is stateless; no `go` keyword, `sync.*`, or channel ops in diff |
| Container security | No Dockerfile, K8s manifests, or CI pipeline files in changed scope | `N/A` | `git diff --name-only` shows no infra/deploy files |

**Anti-pattern**: marking a domain `N/A` when imports or adjacent call paths contain trigger signals (e.g., `database/sql` imported → Domain 2 must be `Applicable`).

## Mandatory Gate Definitions

### Gate A: Constructor-Release Pairing (Mandatory)

For changed code and immediately related call paths, enumerate and verify pairings for every constructor/acquisition call:

- Constructors/acquisition: `New*`, `Open*`, `Acquire*`, `Begin*`, `Dial*`, `Listen*`, `Create*`, `WithCancel/WithTimeout/WithDeadline`.
- Required pairings: `Close`, `Release`, `Rollback/Commit`, `Stop`, `Cancel`, or explicit ownership transfer documented in code.

Output requirement:

- Include a short pairing table in analysis notes.
- Any missing or ambiguous pairing is at least `P2` unless proven harmless.

### Gate B: Go Resource Inventory (Mandatory for Go)

Scan all changed code for resource acquisition without matching release. Covers: `rows`, `stmt`, `tx`, `conn`, `file`, `http.Response.Body`, `net.Listener`, driver objects, `goroutine`, `context cancel`, `io.Pipe`.

Key checks: closed on both success and error paths; no `defer` inside loops; goroutines have bounded lifecycle; `WithTimeout` paired with `defer cancel()`.

> **Reference**: See `references/go-secure-coding.md` § Gate B for the full resource inventory table and anti-patterns.

### Gate C: Third-Party Lifecycle Contract Verification (Mandatory)

When code uses driver/framework objects with non-obvious lifecycle rules (for example `godror`, `sql` extensions, SDK clients):

- Verify lifecycle requirements from primary sources (library source code and/or official docs).
- Cite exactly what contract was used for the decision.
- If no contract can be verified, mark confidence at most `suspected` and list under `Uncovered Risk List`.

### Gate D: Go Secure-Coding 10-Domain Coverage (Mandatory for Go)

For Go repositories, score coverage for these 10 domains:

1. **Randomness safety** — `crypto/rand` for secrets; `math/rand` OK for non-security use.
2. **Injection + SQL lifecycle** — parameterized SQL, `ORDER BY` allowlist, `rows.Close`/`Err`, `Commit`/`Rollback`.
3. **Sensitive data handling** — mask logs, opaque error messages, response DTO minimization.
4. **Secret/config management** — no hardcoded secrets, env fail-fast, `nolint:gosec` with rationale.
5. **TLS safety** — `MinVersion >= TLS1.2`, no `InsecureSkipVerify` in production.
6. **Crypto primitives** — bcrypt/argon2id for passwords, AEAD for encryption, `subtle.ConstantTimeCompare`.
7. **Concurrency safety** — `go test -race` clean, no TOCTOU in auth/balance, no unsynchronized map access.
8. **Go injection sinks** — `html/template` not `text/template`, `exec.Command` arg separation, `filepath.Join` traversal.
9. **Static scanner posture** — `gosec` triaged, suppressed `nolint` has rationale.
10. **Dependency posture** — `govulncheck` source-mode reachability.

Execution: D1 triage (`Applicable/N/A`) → D2 deep review on applicable domains only.

Output: each domain `PASS/FAIL/N/A` with one-line evidence. Any `FAIL` with exploitable path becomes a finding.

> **Reference**: See `references/go-secure-coding.md` § Gate D for detailed checks, code examples, and decision tables per domain.

### Gate E: Second-Pass Falsification Review (Mandatory)

After first-pass findings, run a dedicated second pass to disprove your own conclusion:

- Ask: "What critical issue would I have missed if first pass over-focused on exploitability class X?"
- Focus on availability, consistency, lifecycle, and partial-failure paths.
- Specifically re-check: transaction boundaries, rollback guarantees, cleanup on error/panic, idempotency race windows.

Output requirement:

- Add a one-line summary in report: `Second-pass falsification completed: yes/no`.

### Gate F: Uncovered Risk List (Mandatory)

Always output unresolved coverage gaps to avoid false completeness.

Each item must include:

- Area not covered
- Why not covered (tool/env/access/time)
- Security impact if the gap hides a defect
- Recommended follow-up action and owner suggestion

## Anti-Examples (Common Review Mistakes)

These are structured examples of review mistakes this skill is designed to prevent. Each shows a wrong approach and the correct alternative.

### AE-1: Style Finding Reported as Security Issue

**Wrong**: Reporting `P3 — function has 200 lines, hard to review for security` as a security finding.
**Correct**: Code complexity is a code quality issue. Only report security findings when there is an exploitable or defense-gap path. If complexity obscures a real vulnerability, report the vulnerability itself with evidence.

### AE-3: Over-Reporting False Positives

**Wrong**: `P1 — math/rand used in pkg/display/shuffle.go:12 for randomizing quiz question order` without checking if the output is security-relevant.
**Correct**: Suppressed — `math/rand` usage is for display ordering of quiz questions; output is not attacker-exploitable and does not protect a security boundary (Suppression Rule 2).

### AE-5: Missing Gate Reported as Full Coverage

**Wrong**: Report says "all gates passed" but `go test -race` was not run because test suite was unavailable.
**Correct**: Record under `Uncovered Risk List`: "Gate D7 (Concurrency safety) — `go test -race` not executed because test suite has build errors. Impact: data races may exist undetected in changed packages. Recommended: fix test build and re-run."

> For additional anti-examples (N/A without evidence, confirmed without reproducer, P0 acceptance without escalation, ignoring transitive call paths), see `references/anti-examples.md`.

## Scenario Checklists

Run applicable scenarios from the full 11-scenario checklist:

1. **Authentication / Authorization** — auth on routes, authz before ops, IDOR, token lifecycle.
2. **Input Validation / Injection / Uploads** — schema rules, parameterized SQL, path traversal, upload controls, Go injection sinks.
3. **Session / JWT / Cookie / CSRF** — JWT validation, `alg=none` rejection, cookie flags, CSRF.
4. **New Endpoints and Error Surface** — authn/authz strategy, error leakage, CORS, idempotency, Go-specific (`MaxBytesReader`, timeouts).
5. **Secrets / Crypto / Key Management** — no hardcoded secrets, env-only loading, bcrypt/argon2id, constant-time compare.
6. **Payment / Financial Transitions** — server-side validation, replay protection, transaction boundaries, balance concurrency.
7. **Sensitive Data Storage / Transmission** — TLS, field masking, encryption-at-rest, response minimization.
8. **Third-Party Integrations** — timeout/retry bounds, signature verification, SSRF-safe URL, fail-safe behavior.
9. **Supply Chain / Dependency / Build Path** — `govulncheck`, `gosec`, dependency pinning.
10. **Container / Deployment Security** — Dockerfile non-root, image pinning, K8s securityContext, NetworkPolicy, CI secret store.
11. **Concurrency Safety as Security Risk** — TOCTOU, double-spend race, concurrent map crash, `go test -race`.

> **Reference**: See `references/scenario-checklists.md` for the full checklist with per-item details and Go-specific subsections.

## Focused Automation Gate

Run when tools are available; never claim results without running commands.

Execution policy:

- Always run low-cost baseline sweep (`rg` secrets patterns).
- Run expensive scanners according to `Gate D` applicability:
  - If dependency/module graph changed or third-party risk is `Applicable`, run `govulncheck`.
  - If security-sensitive Go code changed, run `gosec` on affected scope (or full repo when scope is unclear).
- If a scanner is skipped because the domain is `N/A`, record that explicitly in `Automation Evidence`.

```bash
# secret pattern sweep
rg -n "(AKIA[0-9A-Z]{16}|-----BEGIN (RSA|EC|OPENSSH|PRIVATE) KEY-----|ghp_[A-Za-z0-9]{36}|xox[baprs]-|AIza[0-9A-Za-z\-_]{35}|password\s*=|secret\s*=|token\s*=)" .

# Go race detector on changed packages (mandatory for Standard/Deep if tests exist)
go test -race -count=1 ./path/to/changed/...

# Go security scanners
gosec ./...
govulncheck ./...

# Optional cross-check: module exposure view (may include unreachable vulns)
govulncheck -mode=binary ./...
```

### Tool Interpretation Rules (Mandatory)

- `go test -race`: any race detected is at least `P2`; races on auth/balance/permission state are `P1` (CWE-367). Report goroutine stacks from race output.
- `gosec`: report rule ID, location, and whether finding is exploitable on reachable paths.
- `govulncheck` source mode: call-trace reachable vulns are high confidence (`confirmed/likely`).
- `govulncheck -mode=binary`: treat as exposure signal only; do not mark `confirmed` without source reachability or equivalent proof.
- Any suppressed `nolint:gosec` requires explicit rationale review; missing rationale is at least `P3` hardening gap.

## Language/Framework Extension Hooks

Default checklist targets Go services. For non-Go stacks, replace Go-specific Gate D domains with the stack-specific reference. All other gates, scenario checklists, severity model, and output contract remain unchanged. If mixed stack, split findings by module.

| Stack | Reference | Key Domains |
|-------|-----------|-------------|
| Node.js / TypeScript | `references/lang-nodejs.md` | injection, prototype pollution, ReDoS, SSRF, middleware order |
| Java / Spring | `references/lang-java.md` | deserialization, SpEL/SQL injection, auth annotations, config secrets |
| Python / FastAPI / Django | `references/lang-python.md` | eval/pickle, SSTI, ORM safety, async blocking, dependency audit |

## Standards Mapping (Mandatory)

Include mapping for each finding when applicable:

- `CWE-xxx`
- `OWASP ASVS <section>`

If unclear, use `Mapping: TBD` with reason.

## Output Contract

Return outputs in this order. Fields are graded MUST / SHOULD / MAY per review depth:

| # | Section | Lite | Standard | Deep |
|---|---------|------|----------|------|
| 1 | **Findings** (P0 → P3) | MUST | MUST | MUST |
| 2 | **Go 10-Domain Coverage** | MUST (triage only) | MUST (full) | MUST (full) |
| 3 | **Automation Evidence** | MUST (secret sweep only) | MUST | MUST |
| 4 | **Open questions / assumptions** | MAY | MUST | MUST |
| 5 | **Risk Acceptance Register** | MAY | MUST | MUST |
| 6 | **Remediation Plan** | MAY | MUST | MUST |
| 7 | **Machine-Readable Summary (JSON)** | MUST | MUST | MUST |
| 8 | **Hardening suggestions** | MAY | SHOULD | MUST |
| 9 | **Uncovered Risk List** | MUST | MUST | MUST |

### 1) Findings (P0 -> P3)

Each finding includes:

- Title
- Severity
- Confidence (`confirmed/likely/suspected`)
- Mapping (`CWE` / `OWASP ASVS`)
- File/line
- Exploit path
- Impact
- Minimal reproducer (required for confirmed P0/P1)
- Recommended fix
- Suggested regression/negative test
- Baseline status (`new/regressed/unchanged`)

#### One-Shot Finding Example

> **SEC-001: IDOR — Any authenticated user can access other users' orders**
>
> - **Severity**: P1 High
> - **Confidence**: confirmed
> - **Mapping**: CWE-639 (Authorization Bypass Through User-Controlled Key) / OWASP ASVS V4.1.2
> - **File/line**: `internal/handler/order.go:47`
> - **Exploit path**: `GET /api/orders/:id` extracts `id` from URL path and passes it directly to `repo.GetOrder(id)` without verifying `order.UserID == ctx.UserID()`. Any authenticated user can read any order by iterating IDs.
> - **Impact**: Full horizontal privilege escalation on order data (PII, payment amounts, addresses).
> - **Reproducer**:
>   ```bash
>   # User A's token, requesting User B's order
>   curl -H "Authorization: Bearer <tokenA>" https://api.example.com/api/orders/ORDER-9999
>   # Returns 200 with User B's order details
>   ```
> - **Recommended fix**:
>   ```go
>   order, err := h.repo.GetOrder(ctx, orderID)
>   if err != nil { ... }
>   if order.UserID != auth.UserIDFrom(ctx) {
>       return echo.NewHTTPError(http.StatusNotFound, "order not found")
>   }
>   ```
>   Return 404 (not 403) to avoid confirming the order exists.
> - **Regression test**: Add `TestGetOrder_CrossUser_Returns404` — create order as User A, request as User B, assert 404.
> - **Baseline status**: new

### 2) Go 10-Domain Coverage (Required for Go repos)

- Domains 1..10 with `PASS/FAIL/N/A`
- Applicability per domain (`Applicable` or `N/A` with reason)
- One-line evidence per domain (deep evidence required only for `Applicable` domains)
- Total `PASS` count and key failed domains

### 3) Automation Evidence

- Command list actually executed
- Key outputs (short)
- Tools skipped/unavailable and reason (including `N/A` applicability skips)

### 4) Open questions / assumptions

### 5) Risk Acceptance Register

P0 findings MUST NOT be accepted without VP-level or equivalent sign-off; record the approver explicitly. P1 findings require tech-lead-level sign-off.

For each accepted risk entry:

- Finding ID
- Reason for acceptance
- Compensating controls
- Approver (name and role)
- Owner
- Expiry/review date

### 6) Remediation Plan

- Immediate
- Short-term
- Backlog

### 7) Machine-Readable Summary (JSON)

Also output a compact JSON block for CI/inbox ingestion:

```json
{
  "summary": {
    "pass": false,
    "score": "10/14",
    "baseline": "present"
  },
  "counts": {
    "p0": 0,
    "p1": 1,
    "p2": 2,
    "p3": 1
  },
  "changes": {
    "new": 2,
    "regressed": 1,
    "unchanged": 1,
    "resolved": 0
  },
  "go_domains": {
    "required": true,
    "total": 10,
    "pass": 7,
    "fail": 2,
    "na": 1
  },
  "findings": [
    {
      "id": "SEC-001",
      "severity": "P1",
      "confidence": "confirmed",
      "status": "new",
      "cwe": "CWE-639",
      "asvs": "V4",
      "file": "internal/handler/account.go:88"
    }
  ]
}
```

### 8) Hardening suggestions

### 9) Uncovered Risk List (Mandatory)

## Load References Selectively

Read only the references needed for the current review. The review depth and language determine what to load.

For Go code at Standard or Deep depth:
→ Load `references/go-secure-coding.md` for Gate B resource inventory table (HTTP handlers, DB queries, file ops, goroutines, crypto) and Gate D 10-domain deep-dive (injection, auth, crypto, SSRF, race conditions, secrets, input validation, error handling, logging, dependencies).
→ Load `references/scenario-checklists.md` for the full 11-scenario checklist (web API, CLI, background worker, gRPC service, etc.) with per-item PASS/FAIL/N/A fields and Go-specific subsections.

For Go code at Lite depth (**do not load `go-secure-coding.md`** — Gate B/C/E are skipped):
→ Load `references/scenario-checklists.md` only, for scenario-scoped checklist items applicable to Lite gate coverage.

For Node.js / TypeScript code:
→ Load `references/lang-nodejs.md` for injection patterns, prototype pollution, ReDoS, SSRF, middleware order issues, and TypeScript-specific type-safety bypass risks.
→ Load `references/scenario-checklists.md` for the cross-language scenario checklist.

For Java / Spring code:
→ Load `references/lang-java.md` for deserialization vulnerabilities, SpEL/SQL injection, `@PreAuthorize` annotation gaps, config secrets exposure, and Spring Security misconfiguration patterns.
→ Load `references/scenario-checklists.md` for the cross-language scenario checklist.

For Python / FastAPI / Django code:
→ Load `references/lang-python.md` for `eval`/`pickle` misuse, SSTI, ORM safety gaps, async blocking risks, and dependency audit patterns.
→ Load `references/scenario-checklists.md` for the cross-language scenario checklist.

For general or multi-language reviews:
→ Load `references/scenario-checklists.md` only for the language-agnostic scenario checklist (~1,200 tokens).

When severity or confidence decisions feel ambiguous, or before publishing findings:
→ Load `references/severity-calibration.md` for confidence downgrade rules, severity scoring matrix, common finding patterns with calibrated severity levels, and CVSS estimation guidance.

When the report needs additional anti-examples for quality validation or reviewer training:
→ Load `references/anti-examples.md` for extended anti-examples (AE-2 through AE-7) covering N/A abuse, confirmed-without-reproducer, P0-acceptance-without-escalation, and transitive call path omissions.

## Bundled Assets

| File | Purpose |
|------|---------|
| `references/go-secure-coding.md` | Gate B resource inventory + Gate D 10-domain deep reference (Go only, Standard/Deep) |
| `references/scenario-checklists.md` | Full 11-scenario checklist with per-item details |
| `references/severity-calibration.md` | Severity + confidence calibration rules and common finding patterns |
| `references/anti-examples.md` | Extended anti-examples (AE-2, AE-4, AE-6, AE-7) |
| `references/security-review.md` | General security review methodology |
| `references/lang-nodejs.md` | Node.js/TypeScript domain-specific gates |
| `references/lang-java.md` | Java/Spring domain-specific gates |
| `references/lang-python.md` | Python/FastAPI/Django domain-specific gates |
