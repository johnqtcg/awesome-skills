---
name: security-review
description: Exploitability-first standalone security review of code changes, diffs, PRs, or services. Use when asked for a security review, security audit, vulnerability assessment, or pre-merge security check (安全审查/安全评审/漏洞排查) — covers auth, input, secrets, API, data, concurrency, container, third-party, and dependency risk across Go, Node.js/TypeScript, Java, and Python, with mandatory evidence, false-positive suppression, scope-based depth (Lite/Standard/Deep), and CWE/OWASP-mapped machine-readable output. NOT for general-purpose Go code review — use go-review-lead for that (it dispatches go-security-review as its security dimension); this skill is the deeper security-only process with mandatory gates and audit-grade output.
allowed-tools: Read, Grep, Glob, Bash(git diff*), Bash(go vet*), Bash(go build*), Bash(go test -race*), Bash(gosec*), Bash(govulncheck*), Bash(semgrep*), Bash(npm audit*), Bash(curl*), Bash(mvn dependency:tree*), Bash(mvn org.owasp:dependency-check-maven:check*), Bash(mvn spotbugs:check*), Bash(pip-audit*), Bash(safety check*), Bash(bandit*)
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
| Send any request / run a scanner against a live target | §Active Verification Authorization Gate (**default deny**) |

## Review Principles

- Prioritize exploitable risk over style issues.
- Ground every claim in code/config/runtime evidence.
- Distinguish confirmed vulnerabilities from hypotheses.
- Provide reproducible proof for high-risk findings.
- Map findings to standards for auditability.
- If evidence is missing, state `Not found in repo`.
- Fail closed: if a mandatory gate cannot be executed, state it explicitly and do not claim full coverage.
- **Authorization before action**: static review always; touching a running system only under
  §Active Verification Authorization Gate. Default deny.
- **Execution integrity**: never present a command you did not run as if you had. Label
  unexecuted reproducers explicitly.

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

If Lite triage finds **all** of: 10 Gate D domains `N/A`, 11 scenario checklists `N/A`, clean
secret sweep, and no constructor/acquisition calls in Gate A — output a condensed report
instead of the full Output Contract: review depth + rationale, the line
`Fast Pass: all domains N/A, all scenarios N/A, no findings.`, a JSON summary with
`pass: true` and zero counts, and the Gate F list (may be empty). All four are mandatory.

This avoids verbose N/A tables for benign changes while preserving audit traceability.

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

**Anti-pattern**: marking a domain `N/A` when imports or adjacent call paths contain trigger signals (e.g., `database/sql` imported → Domain 2 must be `Applicable`).

→ Worked `N/A` judgments with rationales: `references/authorization-and-policy.md` §6.

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

## Change Origin Classification

Classify each finding's origin relative to the current code change:

- **`introduced`**: defect resides in code added or modified by this change. **Must fix before merge.**
- **`pre-existing`**: defect found in unchanged code that came into scope via call paths.
  Default: **file a follow-up issue and do not block merge** — a change should not be held
  hostage to unrelated debt. This default is a *recommendation to the owning team*, not a
  security clearance, and it is **void** (recommend blocking + escalate) when the finding is
  `P0` or an actively-exploited `P1`, when this change widens the attack surface on it, when
  this merge is the release vehicle that ships it, or when the defect sits in the same
  file/function being modified. Never present "pre-existing" as a reason the risk is
  acceptable. → `references/authorization-and-policy.md` §5.
- **`uncertain`**: diff boundaries are ambiguous. Use `git blame` to resolve; treat as `introduced` if unresolvable.

Add `**Origin:**` to each finding's output. Use diff hunks as primary classification signal.

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

Classify all 11 as `Applicable` or `N/A`, then run the applicable ones:

1. Authentication / Authorization · 2. Input Validation / Injection / Uploads ·
3. Session / JWT / Cookie / CSRF · 4. New Endpoints and Error Surface ·
5. Secrets / Crypto / Key Management · 6. Payment / Financial Transitions ·
7. Sensitive Data Storage / Transmission · 8. Third-Party Integrations ·
9. Supply Chain / Dependency / Build Path · 10. Container / Deployment Security ·
11. Concurrency Safety as Security Risk

> **Reference**: `references/scenario-checklists.md` has the per-item details and the
> stack-specific subsections. Load it for every Standard/Deep review.

## Active Verification Authorization Gate (Mandatory Before Any Request)

This skill can issue network requests (`curl`) and run scanners. **A tool grant is not an
authorization.** Everything below is *static* analysis by default; sending a single request to
a target you were not authorized to test is unauthorized activity, regardless of intent.

Before any command that touches a running system, record this three-line block:

```
Active verification: permitted | NOT permitted
Target: <host/URL or "none">
Basis: <who authorized it, or which local/test environment it is>
```

**Default deny.** If you cannot fill in `Basis` from what the user actually told you,
`Active verification` is `NOT permitted`. Do not infer authorization from the presence of a
hostname in the code, a `.env` file, a README, or a CI config.

Always allowed: reading code/config/diffs, static scanners on local source, local test runs,
and requests to `127.0.0.1`/`localhost` or a container you started.

Never without explicit authorization: any request to a host you did not stand up (including
read-only `GET` to staging/production), authenticating with credentials found in the repo, or
scanning a third party. Ambiguous targets — `.test`/`.local` domains, a shared dev cluster, a
hostname in a compose file you did not launch — count as **not permitted**; ask first.

When authorized: non-destructive read-only probes only; production is static-only unless
explicitly authorized with a change window; demonstrate rather than enumerate; use only
test accounts the user provided; log every request in `Automation Evidence`; stop on any
unexpected impact.

A `confirmed` P0/P1 does **not** require executing anything — static proof of the path is
sufficient. Provide the reproducer as **unexecuted instructions** labelled
`Reproducer (NOT executed — no authorization to test)`, against a non-routable placeholder
target. Never describe a command you did not run as if you had.

→ Full rules (destructive payloads, credentials, rate limits, production policy):
`references/authorization-and-policy.md` §1.

## Focused Automation Gate

Run when tools are available; never claim results without running commands.
**Prerequisite: the Active Verification Authorization Gate above.** Everything in this
section except the local static commands requires `Active verification: permitted`.

Execution policy:

- Always run low-cost baseline sweep (`rg` secrets patterns).
- Run expensive scanners according to `Gate D` applicability:
  - If dependency/module graph changed or third-party risk is `Applicable`, run `govulncheck`.
  - If security-sensitive Go code changed, run `gosec` on affected scope (or full repo when scope is unclear).
- If a scanner is skipped because the domain is `N/A`, record that explicitly in `Automation Evidence`.

→ Exact commands (secret sweep regex, `go test -race`, `gosec`, `govulncheck` source and
binary mode): `references/authorization-and-policy.md` §7.

### Tool Interpretation Rules (Mandatory)

- `go test -race`: a detected race is always a **defect to fix**, but its *security* severity depends on what races. Races on auth/permission/balance/quota state are `P1` (CWE-367). Races on request-scoped state an attacker can drive concurrently are `P2`. A race confined to test scaffolding, metrics counters, or log buffers is `P3` or reliability-only — say which, and why. Report goroutine stacks from race output.
- `gosec`: report rule ID, location, and whether finding is exploitable on reachable paths.
- `govulncheck` source mode: call-trace reachable vulns are high confidence (`confirmed/likely`).
- `govulncheck -mode=binary <path-to-binary>`: exposure signal only; do not mark `confirmed` without source reachability or equivalent proof. Binary mode has no call-graph, so it over-reports. It also accepts only a built artifact — passing a package pattern is an error, not a scan.
- Any suppressed `nolint:gosec` requires rationale review. Judge the **suppressed rule**, not the missing comment: if the underlying gosec finding is exploitable, report it at its own severity. If it is a genuine false positive, an absent rationale is a process/hygiene note, not a security finding — record it under `Hardening suggestions`, not as `P3`. Only treat it as `P3` when the suppression hides a real defense gap you cannot fully assess.

## Language/Framework Extension Hooks

Gate D's **10 domains are stack-independent** — they are the review axes, not Go features.
Only the sink/idiom reference you load changes per stack. Detect the stack from manifests
(`go.mod`, `package.json`, `pom.xml`/`build.gradle`, `pyproject.toml`/`requirements.txt`), load
the matching reference plus `scenario-checklists.md`, evaluate the **same 10 domains**, and
record `stack` in the JSON and the coverage header.

A non-Go stack must not report `N/A` for all ten domains merely because the repo is not Go —
that is a coverage failure, not an exemption. Multi-stack repos emit one coverage section per
stack; a domain is `FAIL` for the repo if it fails in any stack.

→ Detection table, Domain 2 generalisation, and multi-stack JSON shape:
`references/authorization-and-policy.md` §2.

## Standards Mapping (Mandatory)

Map each finding to `CWE-xxx` and OWASP ASVS. Use `Mapping: TBD` if unclear.

**Pin the ASVS version in every mapping.** ASVS 5.0.0 reorganised and renumbered the chapters
4.x used, so a bare `V4` or `V4.1.2` does not identify a requirement — it does not say which
standard it belongs to. Write IDs fully qualified (`ASVS 4.0.3 V4.1.2`), declare
`"asvs_version"` once in the JSON block, and use exactly one version per report.

The lookup table in `references/security-review.md` is **4.0.3 chapter numbers**. If the
project audits against 5.0.0, resolve IDs from the 5.0.0 document — never renumber by guessing;
`Mapping: TBD` beats a plausible-but-wrong requirement ID.

→ Version-pinning rules: `references/authorization-and-policy.md` §3.

## Output Contract

Return outputs in this order. Fields are graded MUST / SHOULD / MAY per review depth:

| # | Section | Lite | Standard | Deep |
|---|---------|------|----------|------|
| 1 | **Findings** (P0 → P3) | MUST | MUST | MUST |
| 2 | **Security Domain Coverage** (10 domains, per detected stack) | MUST (triage only) | MUST (full) | MUST (full) |
| 3 | **Automation Evidence** | MUST (secret sweep only) | MUST | MUST |
| 4 | **Open questions / assumptions** | MAY | MUST | MUST |
| 5 | **Risk Acceptance Register** | MAY | MUST | MUST |
| 6 | **Remediation Plan** | MAY | MUST | MUST |
| 7 | **Machine-Readable Summary (JSON)** | MUST | MUST | MUST |
| 8 | **Hardening suggestions** | MAY | SHOULD | MUST |
| 9 | **Uncovered Risk List** | MUST | MUST | MUST |

### 1) Findings (P0 -> P3)

Each finding includes: Title · Severity · Confidence (`confirmed/likely/suspected`) ·
Mapping (`CWE` / version-pinned `ASVS`) · File/line · Exploit path · Impact ·
Minimal reproducer · Recommended fix · Suggested regression/negative test ·
Baseline status (`new/regressed/unchanged`) · Origin (`introduced | pre-existing | uncertain`).

The reproducer is required for confirmed P0/P1, but may be **unexecuted instructions** when
active verification is not authorized — label it as such; never fake execution.

→ Fully worked finding (IDOR, all fields populated, unexecuted reproducer, 404-not-403 fix):
`references/security-review.md` §One-Shot Finding Example.

#### Finding Volume Cap

- **P0/P1**: Always fully reported. Volume cap does not apply to P0/P1.
- **P2/P3 soft cap by depth**: Lite ≤ 3, Standard ≤ 5, Deep ≤ 8 detailed lower-severity findings.
- **Overflow goes to a `Condensed Findings` subsection of §1 — never to §9.** List each
  overflow item as one line (`ID — severity — title — file:line`), still inside Findings, and
  record `counts.overflow` in the JSON block.
- P0/P1 findings are never dropped by volume cap.

**§1 and §9 are disjoint.** §9 means *"scope I did not inspect"*; a confirmed P2 is the
opposite — inspected, understood, real. Filing findings there corrupts the section readers use
to judge review coverage. The cap limits **detail**, not disclosure: every finding stays
visible in §1. → `references/authorization-and-policy.md` §4.

### 2) Security Domain Coverage (Required for every stack)

Header must name the stack, e.g. `Security Domain Coverage — stack: nodejs`.

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
  "summary": { "pass": false, "score": "10/14", "baseline": "present" },
  "counts": { "p0": 0, "p1": 1, "p2": 2, "p3": 1, "overflow": 0 },
  "changes": { "new": 2, "regressed": 1, "unchanged": 1, "resolved": 0 },
  "stack": "go",
  "asvs_version": "4.0.3",
  "active_verification": "not_permitted",
  "security_domains": { "required": true, "total": 10, "pass": 7, "fail": 2, "na": 1 },
  "findings": [
    {
      "id": "SEC-001", "severity": "P1", "confidence": "confirmed", "status": "new",
      "origin": "introduced", "cwe": "CWE-639", "asvs": "ASVS 4.0.3 V4.1.2",
      "file": "internal/handler/account.go:88"
    }
  ]
}
```

`security_domains` uses the same key for every stack — a consumer must never branch on
language to read the result (there is no `go_domains` key). `stack` may be a comma-joined list;
`active_verification` mirrors the authorization gate so CI can tell whether findings were
established statically or dynamically.

→ Full field rules and the multi-stack `per_stack` shape:
`references/authorization-and-policy.md` §2.

### 8) Hardening suggestions

### 9) Uncovered Risk List (Mandatory)

## Load References Selectively / Bundled Assets
→ See `references/reference-index.md` for the loading guide by depth and stack, and the full
asset inventory.
