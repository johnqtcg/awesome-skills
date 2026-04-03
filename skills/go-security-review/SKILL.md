---
name: go-security-review
description: Review Go code for security vulnerabilities including OWASP Top 10, injection, auth/authz, crypto, secrets, SSRF, XSS, and input validation. Trigger when code involves SQL, user input, authentication, HTTP handlers, TLS, crypto, secrets, or file path operations. Use for security-focused code review of Go projects.
allowed-tools: Read, Grep, Glob, Bash
---

# Go Security Review

## Purpose

Identify exploitable security vulnerabilities in Go code. Scope is strictly security: injection, authentication/authorization, cryptography, secrets management, input validation, transport security, and HTTP hardening.

This skill does NOT cover: performance, concurrency (race conditions), code quality/style, test quality, error handling patterns, or business logic correctness — those belong to sibling vertical skills.

## When To Use
- Code touches SQL queries, command execution, or file path operations
- Code handles user input, authentication, authorization, or session management
- Code involves HTTP handlers, TLS configuration, or cryptographic operations
- Code contains hardcoded string literals that may be secrets
- Security-focused PR review requested

## When NOT To Use
- Performance optimization → `go-performance-review`
- Concurrency/race conditions → `go-concurrency-review`
- Error handling correctness → `go-error-review`
- Code style/lint → `go-quality-review`
- Test quality → `go-test-review`
- Business logic correctness → `go-logic-review`

## Mandatory Gates

### 1) Execution Integrity Gate
Never claim `gosec` or any security tool ran unless it actually produced output. If not run: state reason + exact command.

### 2) Go Version Gate
Read `go.mod` for the `go` directive. Do NOT recommend version-specific features above project version. If inaccessible, record `Go version: unknown`.

### 3) Anti-Example Suppression Gate
Before reporting, verify finding is not a false positive. MUST quote specific code evidence satisfying the precondition. Category match alone is insufficient.

Embedded anti-examples for security domain:
- **Speculative injection when input is internal/constant**: Do NOT flag `fmt.Sprintf` in SQL when the interpolated value is a compile-time constant, config value, or internal enum. Trace data flow from input source to dangerous function — confirm user input actually reaches it.
- **Over-cautious crypto on non-password use**: Do NOT flag MD5/SHA1 for cache key derivation, content hashing, or checksums where collision resistance is not a security requirement. Flag ONLY for password hashing, auth tokens, or integrity verification of untrusted data.
- **Context over-propagation**: Do NOT flag "missing context.Context" when function is synchronous, short-lived, no I/O, no cancellable work.
- **Rate limiting on internal-only endpoints**: Do NOT flag rate limiting absence on endpoints not exposed to public traffic (internal mesh, admin behind VPN). Verify endpoint exposure before reporting.
- **Insufficient evidence rule**: Every finding must quote concrete code evidence. "This endpoint handles user input" is not sufficient — show the path from input to dangerous function.

### 4) Generated Code Exclusion Gate
Exclude: `*.pb.go`, `*_gen.go`, `mock_*.go`, `wire_gen.go`, `*_string.go`, files with `// Code generated .* DO NOT EDIT`. Note excluded files in Execution Status.

## Workflow

1. **Define scope** — confirm files/diff under review. Apply Generated Code Exclusion Gate.
2. **Gather evidence** — read changed files, identify security-relevant patterns: SQL strings, `os/exec`, `filepath`, HTTP handlers, TLS config, crypto, hardcoded literals, auth middleware, URL fetching, template rendering.
3. **Load references** — always load `go-security-patterns.md`; load `go-api-http-checklist.md` when HTTP/API code present.
4. **Evaluate checklist** — execute ALL 16 items. For injection findings, trace data flow from input source to dangerous function.
5. **Apply suppression** — run candidates through anti-example gate → format output.

## Grep-Gated Execution Protocol

This skill uses mechanical grep pre-scanning to guarantee zero missed checklist items. 14 of 16 items are grep-gated; 2 are semantic-only.

### Execution Order
1. Identify target files (from dispatch prompt, or write raw snippet to `$TMPDIR/review_snippet.go`)
2. Run grep for all grep-gated checklist items against target files
3. **HIT** → run semantic analysis to confirm or reject (trace data flow for injection findings)
4. **MISS** → auto-mark NOT FOUND, skip semantic analysis
5. For compound patterns: run primary grep, then secondary pattern, apply AND/AND NOT logic
6. For semantic-only items (items 9, 12): full model reasoning
7. Report only FOUND items

### Grep Audit Line
Include in Execution Status: `Grep pre-scan: X/14 items hit, Z confirmed as findings (2 semantic-only)`

### Compound Pattern Protocol
- Item 3 (Path traversal): `filepath\.Join\|os\.Open` HIT → trace whether input comes from user request
- Item 8 (Sensitive data in logs): `log\.\|slog\.` HIT → check if logged value includes password/token/PII
- Item 10 (SSRF): `http\.Get\|client\.Do` HIT → trace whether URL comes from user input
- Item 15 (Timing attack): secret comparison HIT AND `subtle.ConstantTimeCompare` NOT found
- Item 16 (Input validation): `Atoi\|ParseInt` HIT → check if result used for allocation/slice sizing without bounds check

## Security Checklist (16 Items)

All High severity unless marked (Medium).

| # | Item | Code Pattern Triggers | Grep Pattern |
|---|------|-----------------------|--------------|
| 1 | **SQL injection** | `fmt.Sprintf` + SQL keywords, string concat in `db.Query`/`db.Exec`, `gorm.Raw()` | `Sprintf.*SELECT\|Sprintf.*INSERT\|Sprintf.*UPDATE\|Sprintf.*DELETE\|db\.Query\|db\.Exec\|gorm\.Raw` |
| 2 | **Command injection** | `os/exec` with variables from request/config, `sh -c` with interpolation | `os/exec\|exec\.Command` |
| 3 | **Path traversal** | `filepath.Join` with unsanitized request input, no `filepath.Rel` base-dir check | `filepath\.Join\|os\.Open\|os\.ReadFile` (compound: AND user input flows in — semantic required) |
| 4 | **Insecure TLS** | `InsecureSkipVerify: true`, `MinVersion` below TLS 1.2 | `InsecureSkipVerify\|MinVersion\|tls\.Config` |
| 5 | **Weak crypto** | `md5.Sum`/`sha1.Sum` for passwords or auth tokens, RSA < 2048, `math/rand` for secrets | `md5\.Sum\|sha1\.Sum\|math/rand` |
| 6 | **Hardcoded secrets** | String literals matching `sk-`, `ghp_`, `AKIA`, `password=`, `-----BEGIN` | `sk-\|ghp_\|AKIA\|password\s*=\s*"\|BEGIN.*PRIVATE` |
| 7 | **unsafe package** | `import "unsafe"` without documented justification comment | `"unsafe"` |
| 8 | **Sensitive data in logs** | Passwords, tokens, PII in `log.*`, `slog.*`, `fmt.Errorf`, full request body logged | `log\.\|slog\.\|Errorf\|Fprintf` (compound: AND sensitive data keyword in same statement — semantic required) |
| 9 | **AuthN/AuthZ flaws** | JWT without algorithm pinning, IDOR (no ownership check), auth middleware after handler | Semantic-Only (auth/authz patterns require understanding middleware flow) |
| 10 | **SSRF** | `http.Get`/`client.Do` with user-controlled URL, no host allowlist or private-IP blocking | `http\.Get\|http\.Post\|client\.Do\|http\.NewRequest` (compound: AND user-controlled URL — semantic required) |
| 11 | **XSS** | `text/template` for HTML, `template.HTML()` on user input, `fmt.Fprintf` to ResponseWriter with HTML | `text/template\|template\.HTML\|Fprintf.*ResponseWriter` |
| 12 | **Rate limiting missing** (Medium) | Auth/login/password-reset endpoints without rate limit middleware | Semantic-Only (rate limiting detection requires understanding endpoint exposure) |
| 13 | **CORS misconfiguration** | Reflected Origin header, `Access-Control-Allow-Origin: *` with credentials | `Access-Control\|AllowOrigin\|CORS\|Origin` |
| 14 | **HTTP security headers missing** (Medium) | No `X-Content-Type-Options`, `X-Frame-Options`, HSTS, CSP | `X-Content-Type\|X-Frame\|Strict-Transport\|Content-Security-Policy` |
| 15 | **Timing attack** | `==` on secrets/tokens instead of `crypto/subtle.ConstantTimeCompare` | `==.*secret\|==.*token\|==.*key\|==.*password` (compound: AND NOT `subtle\.ConstantTimeCompare`) |
| 16 | **Input validation missing** | No `http.MaxBytesReader` on body, unchecked `strconv.Atoi` used for allocation size | `MaxBytesReader\|LimitReader\|Atoi\|ParseInt\|ParseUint` |

## Severity Rubric

**High** — Exploitable vulnerability: injection, auth bypass, data exposure, SSRF, hardcoded secrets, insecure TLS.

**Medium** — Requires specific conditions or defense-in-depth gap: missing headers, rate limiting, weak config defaults.

## Evidence Rules
- Every finding: exact location (`path:line`), concrete impact, actionable fix with code example
- For injection: trace data flow — name the source (e.g., `r.URL.Query().Get("q")` at handler.go:23) and the sink (e.g., `fmt.Sprintf` at repo.go:67)
- No speculative findings — require evidence of user-controlled input reaching the vulnerable path
- **Merge rule**: same issue at ≥3 locations → one finding with location list

## Output Format

### Findings
#### [High|Medium] Short Title
- **ID:** SEC-NNN
- **Location:** `path:line` (or location list)
- **Impact:** What an attacker could achieve
- **Evidence:** Concrete code path showing the vulnerability
- **Recommendation:** Specific fix with code example
- **Action:** `must-fix` | `follow-up`

### Suppressed Items
#### [Suppressed] Short Title
- **Reason:** Anti-example matched + specific evidence cited
- **Residual risk:** Brief note

### Execution Status
- `Go version`: X.Y or unknown
- `gosec`: PASS | FAIL | Not available (reason + command)
- `Grep pre-scan`: X/14 items hit, Z confirmed as findings (2 semantic-only)
- `Excluded (generated)`: list or None
- `References loaded`: list

### Summary
1-2 lines. Count by severity.

## Example Output

```
### Findings

#### [High] SQL Injection in User Search
- **ID:** SEC-001
- **Location:** `internal/repo/user.go:67`
- **Impact:** Attacker can execute arbitrary SQL via search parameter
- **Evidence:** `fmt.Sprintf("SELECT * FROM users WHERE name LIKE '%%%s%%'", name)` — `name` flows from `r.URL.Query().Get("q")` at handler.go:23 through SearchUsers() without sanitization
- **Recommendation:** Use parameterized query: `db.QueryContext(ctx, "SELECT * FROM users WHERE name LIKE ?", "%"+name+"%")`
- **Action:** must-fix

### Suppressed Items
#### [Suppressed] MD5 Usage in Cache Key Generation
- **Reason:** MD5 at cache.go:15 is used for cache key derivation from internal struct, not password hashing. Anti-example: "over-cautious crypto on non-password use"
- **Residual risk:** None — cache key collision is acceptable

### Execution Status
- Go version: 1.21
- gosec: Not available (command: `gosec ./...`)
- Grep pre-scan: 3/14 items hit, 1 confirmed as findings (2 semantic-only)
- Excluded (generated): None
- References loaded: go-security-patterns.md, go-api-http-checklist.md

### Summary
1 High finding (SQL injection). No Medium findings.
```

## No-Finding Case
If no issues found: state `No security findings identified.` Still output Execution Status, Suppressed Items (if any), Summary.

## Load References Selectively

| Reference | Load When |
|-----------|-----------|
| `references/go-security-patterns.md` | Always |
| `references/go-api-http-checklist.md` | Code involves net/http, handlers, gin/echo/chi, gRPC, middleware |
| `references/go-review-anti-examples.md` | Always |

## Review Discipline
- **Security only** — never comment on performance, concurrency, style, tests, error handling, or logic
- **Execute ALL 16 checklist items** — do not skip because others produced High findings
- **Trace data flow** for every injection finding — name source and sink
- **Prefer precision over volume** — one well-evidenced finding beats five speculative warnings