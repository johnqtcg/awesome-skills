# Security Review — Severity Calibration Guide

Use this reference when calibrating severity and confidence for findings. Load it when severity decisions feel ambiguous or when reviewing findings before publication.

---

## Governing Rule: Exploitability Outranks Any Severity Floor

Elsewhere in this skill some patterns carry a default floor ("at least `P2`"). Those defaults
are **starting points for a reachable finding**, not overrides of the exploitability-first
principle. When a floor and the four questions below disagree, the questions win — and you
must state which one moved the severity.

Apply to every finding before publishing:

1. **Can an attacker trigger it?** Reachable from an untrusted input at a trust boundary?
   If no path exists, it is not a security finding at any severity — suppress (Rule 2) or
   reclassify as reliability/quality.
2. **Does it protect a security asset?** Credentials, authz decisions, funds, PII, tenant
   isolation, integrity. If the affected value is cosmetic or operational, it is not `P1/P2`.
3. **Is it already bounded upstream?** Gateway body caps, WAF, network policy, pool limits,
   framework escaping. If yes, downgrade or suppress (Rule 1/3) and record residual risk —
   including what happens if that control is removed.
4. **Is it a security defect or a reliability defect?** Both are worth fixing; only the first
   belongs in this report as a finding. Route the second to `Hardening suggestions` and say so.

A finding that cannot answer (1) and (2) affirmatively must not be published as `P1` or `P2`,
regardless of any default floor. Conversely, a default floor never *caps* severity: a
"P2 by default" pattern on an unauthenticated payment path is `P1` or `P0`.

**Do not pad the report with floor-derived findings.** Systematically reporting every
missing-`MaxBytesReader` or unexplained-`nolint` as a finding is the over-reporting failure
mode this skill exists to prevent (see AE-3), and it trains readers to ignore the output.

### Deployment-dependent patterns

For patterns whose severity hinges on infrastructure you cannot see (`MaxBytesReader`,
rate limiting, `X-Frame-Options`, CSP), do not guess. Either verify the upstream control in
the repo (ingress config, gateway manifest, middleware chain) and calibrate accordingly, or
report at the lower severity with an explicit assumption line and list the check under
`Open questions / assumptions`.

---

## Confidence Downgrade Rules

### Attacker Must Control Environment Variable

If the exploit path requires the attacker to control an environment variable (e.g., `BASE_URL`, `API_KEY`), the confidence is at most `suspected` unless you can demonstrate a realistic control path (CI injection, shared hosting, supply-chain `.env` compromise).

**Example**: "SSRF via DNS rebinding on `ISSUE2MD_AI_BASE_URL`" → `P3 suspected` (env var is admin-controlled, not attacker-controlled in normal deployment).

### Attacker Must Control Server Configuration

If the finding depends on a misconfigured server setting that the attacker cannot influence, downgrade to `suspected` and note the configuration assumption.

**Example**: "Path traversal via `openAPISpecPath`" → Suppressed if the path is set at construction time from a compile-time constant or admin-only config.

### Architectural Mitigation Blocks the Path

If an upstream architectural control (allowlist, gateway, WAF, network policy) blocks the attack vector, consider suppression rather than a finding. If the mitigation is partial or could be removed, keep the finding but downgrade severity.

**Example**: "SSRF via user-supplied URL" → Suppressed when parser restricts to `github.com` host and handler does not make HTTP requests to the raw URL.

---

## Severity Calibration Table: Common Go Findings

| Finding Pattern | Typical Severity | Typical Confidence | Key Calibration Factor |
|----------------|-----------------|-------------------|----------------------|
| SQL injection via `fmt.Sprintf` into query | P1 High | confirmed (if reachable) | Is input attacker-controlled at trust boundary? |
| `math/rand` for security token | P1 High | confirmed | Is the output used for auth/session/nonce? If display-only → Suppressed |
| `text/template` with user input | P1 High | confirmed | Is output rendered as HTML to browser? If internal log only → P3 |
| Missing `rows.Close()` | P2 Medium | confirmed | Connection pool exhaustion over time |
| `defer` inside loop | P2 Medium | confirmed | Resource accumulation until function returns |
| No `MaxBytesReader` on POST endpoint | P2 Medium | likely | Depends on deployment (reverse proxy may limit) |
| Missing rate limiting | P2 Medium | confirmed | Depends on whether external rate limiter exists |
| No `io.LimitReader` on response body | P2 Medium | likely | OOM risk, depends on response source trust |
| HTTP redirect following leaks auth header | P2 Medium | likely | Go 1.23+ strips cross-host auth header by default; verify Go version |
| Prompt injection via user content | P2 Medium | likely | Output is rendered text, not code execution; blast radius is content quality |
| SSRF via DNS rebinding (IP-literal check only) | P3 Low | suspected | Requires attacker to control URL config + DNS infrastructure |
| API key as plain `string` | P3 Low | suspected | Only exploitable if struct is logged/serialized via `%+v` |
| Missing `X-Frame-Options` | P3 Low | confirmed | Clickjacking, depends on whether page has state-changing actions |
| Missing CSP header | P3 Low | confirmed | Defense-in-depth; no XSS needed if none exists |
| `InsecureSkipVerify: true` in test code | Suppressed | — | Not production code (Suppression Rule 4) |
| `math/rand` for display shuffle | Suppressed | — | Non-security use (Suppression Rule 2) |

---

## Root-Cause vs Delivery-Mechanism Separation

When a finding can be exploited through multiple delivery mechanisms, report the **root cause** as the finding and note the delivery mechanisms in the exploit path. Do not create separate findings for the same root cause.

| Root Cause | Delivery Mechanism | Correct Report |
|-----------|-------------------|----------------|
| Missing rate limiting | CSRF, direct scripting, botnets | Report rate limiting as P2; mention CSRF as amplifying delivery mechanism |
| Missing input validation | XSS, SQL injection, path traversal | Report the specific injection type; if multiple sinks share the same unvalidated input, group under one finding |
| Unbounded resource consumption | Large payload, deep recursion, pagination | Report the resource exhaustion as P2; list specific vectors in exploit path |

---

## Stateless Endpoint CSRF Assessment

For stateless endpoints (no session, no cookies, no server-side state mutation), CSRF is generally not applicable because:

1. The endpoint does not perform actions on behalf of an authenticated user session
2. No state is mutated that benefits the attacker
3. The browser's same-origin policy prevents the attacker from reading the response

If the concern is **cost/rate-limit exhaustion** via cross-origin requests, report it as a rate limiting issue (P2), not CSRF.

CSRF is applicable when the endpoint:
- Uses cookie-based or session-based authentication AND
- Performs a state-changing operation (write, delete, transfer)
