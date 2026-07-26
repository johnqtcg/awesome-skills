# Security Review — Go Secure-Coding Reference

Deep details for Gate B (resource inventory) and Gate D (10-domain coverage) in Go code.
This file is long — jump to the section you need rather than reading top to bottom.

## Contents

**Gate B — Resource Inventory** ([§](#gate-b-go-resource-inventory--extended-details))
- Key Invariant (severity depends on attacker reachability, not on the leak existing)
- Deferred Cleanup Anti-Patterns

**Gate D — 10 Domains** ([§](#gate-d-10-domain-deep-reference))

| # | Domain | Look for |
|---|--------|----------|
| 1 | Randomness Safety | `math/rand` in tokens/session/nonce |
| 2 | Injection & Data-Access Safety | concatenated SQL, `rows.Close()` |
| 3 | Sensitive Data Handling | logging/serialising PII and credentials |
| 4 | Secret / Config Management | hardcoded secrets, env loading |
| 5 | Transport Security | `MinVersion`, `InsecureSkipVerify` |
| 6 | Crypto Primitive Correctness | password hashing, constant-time compare |
| 7 | Concurrency & Shared-State Safety | TOCTOU, races on auth/balance state |
| 8 | Language-Specific Injection Sinks | `text/template`, `exec`, redirect, path, **Go XML facts** |
| 9 | Static Scanner Posture | `gosec` triage, `nolint` rationale |
| 10 | Dependency Vulnerability Posture | `govulncheck` source vs binary mode |

**Extended BAD/GOOD Patterns** ([§](#extended-security-patterns--badgood-code-reference))
AuthN/AuthZ · SSRF · XSS · CORS · Rate Limiting · HTTP Security Headers ·
Timing Attacks · Input Validation & Deserialization · Path Traversal · Open Redirect

> The GOOD examples in the SSRF and timing-attack sections are mirrored as executable code
> under `scripts/tests/examples/` and verified by `scripts/tests/test_examples_executable.py`.
> If you change one, change both — the test enforces it.

---

## Gate B: Go Resource Inventory — Extended Details

Perform a full resource lifecycle scan for at least:

| Resource | Type | Required Cleanup | Common Leak Pattern |
|----------|------|-----------------|-------------------|
| `rows` | `*sql.Rows` | `rows.Close()` + check `rows.Err()` | `defer` inside loop body (defers pile up) |
| `stmt` | `*sql.Stmt` | `stmt.Close()` | Created in function, not closed on error path |
| `tx` | `*sql.Tx` | `Commit()` or `Rollback()` | Rollback missing when commit fails |
| `conn` | `*sql.Conn`, `net.Conn`, `*grpc.ClientConn` | `conn.Close()` | Leaked on dial error retry |
| `file` | `*os.File` | `file.Close()` | Opened in helper, caller forgets close |
| `resp.Body` | `http.Response.Body` | `resp.Body.Close()` even on non-2xx | Skipped on error status check before close |
| `listener` | `net.Listener` | `listener.Close()` on shutdown | Missing graceful shutdown handler |
| `object` | driver objects (e.g. `godror.Object`) | Per-driver contract | Lifecycle not documented |
| `goroutine` | `go func()` | Cancellation signal or bounded lifetime | `go func()` without context or done channel |
| `cancel` | `context.CancelFunc` | `defer cancel()` | `WithTimeout` without cancel leaks timer |
| `pipe` | `io.PipeWriter` / `io.PipeReader` | Both ends must close | Writer closed but reader never drained |

### Key Invariant

Resource is closed/released on both success and error paths.

**Severity depends on reachability, not on the leak's existence.** A leak is a *security*
finding when an attacker can drive it; otherwise it is a reliability defect and belongs in a
code-quality review, not here.

| Situation | Severity |
|---|---|
| Leak on a path an unauthenticated caller can trigger repeatedly (request handler, retry loop) | `P2` — resource exhaustion → DoS |
| Leak reachable only via an authenticated, rate-limited, or admin-only path | `P3` |
| Leak on a startup/one-shot/CLI path that runs a bounded number of times, or in a process that exits immediately after | **Not a security finding** — report as reliability, or suppress with Rule 2 |
| Leak already bounded upstream (pool cap with a hard timeout, request-scoped context that forces release) | Suppressed (Rule 1), note residual risk |

State the attacker-reachability reason in the finding. "Missing `rows.Close()`" alone is not a
severity justification.

### Deferred Cleanup Anti-Patterns

```go
// BAD: defer inside loop — all closes deferred until function returns
for _, id := range ids {
    rows, _ := db.Query("SELECT ...", id)
    defer rows.Close() // defers pile up, connections exhausted
}

// GOOD: extract to helper function
for _, id := range ids {
    if err := processID(db, id); err != nil { ... }
}
func processID(db *sql.DB, id string) error {
    rows, err := db.Query("SELECT ...", id)
    if err != nil { return err }
    defer rows.Close()
    ...
}
```

---

## Gate D: 10-Domain Deep Reference

### Domain 1 — Randomness Safety

| Use Case | Required | Forbidden |
|----------|----------|-----------|
| Token / API key / session ID | `crypto/rand` | `math/rand` |
| Nonce / salt / IV | `crypto/rand` | `math/rand` |
| Shuffle display order | `math/rand` is OK | — |
| Test data | `math/rand` is OK | — |

Key check: `math/rand` in `import` block → trace all call sites; any security-relevant use is `P1`.

### Domain 2 — Injection & Data-Access Safety

Parameterized SQL checklist:

- `db.Query("SELECT ... WHERE id = ?", id)` — parameterized ✅
- `db.Query("SELECT ... ORDER BY " + col)` — injection ❌ → use allowlist
- `db.Query(fmt.Sprintf("SELECT ... WHERE name = '%s'", name))` — injection ❌
- `rows.Close()` called on all paths (success + error)
- `rows.Err()` checked after iteration loop
- `tx.Rollback()` in defer, `tx.Commit()` at end

### Domain 3 — Sensitive Data Handling

- `log.Printf("user: %+v", user)` → may print password field; use structured logging with field masking.
- `fmt.Errorf("query failed: %w", err)` returned to client → may contain SQL; wrap with opaque message.
- API response contains full user struct → use response DTO with only needed fields.

### Domain 4 — Secret / Config Management

Secret detection patterns:

```
password\s*=\s*"[^"]+"
secret\s*=\s*"[^"]+"
token\s*=\s*"[^"]+"
AKIA[0-9A-Z]{16}
-----BEGIN (RSA|EC|OPENSSH|PRIVATE) KEY-----
ghp_[A-Za-z0-9]{36}
xox[baprs]-
AIza[0-9A-Za-z\-_]{35}
```

Config best practices:

- `os.Getenv("DB_PASSWORD")` with fail-fast if empty
- No default values for secrets in code
- `//nolint:gosec` on secret-related code requires explicit rationale

### Domain 5 — Transport Security

```go
// BAD
tlsConfig := &tls.Config{InsecureSkipVerify: true}

// GOOD
tlsConfig := &tls.Config{MinVersion: tls.VersionTLS12}
```

- `InsecureSkipVerify: true` is `P1` in production code, `suppressed` in test code with note.
- `MinVersion` must be at least `tls.VersionTLS12`.
- mTLS: verify both client and server certificates when required by architecture.

### Domain 6 — Crypto Primitive Correctness

| Purpose | Correct | Incorrect |
|---------|---------|-----------|
| Password hashing | `bcrypt` / `argon2id` | MD5, SHA1, SHA256 (without salt+stretch) |
| Symmetric encryption | AES-GCM (AEAD) | AES-ECB, AES-CBC without HMAC |
| MAC | HMAC-SHA256 | Plain SHA256 of `secret+message` |
| Comparison | `subtle.ConstantTimeCompare` | `==` or `bytes.Equal` |

### Domain 7 — Concurrency & Shared-State Safety

Critical patterns:

- **TOCTOU**: `if hasPermission(userID) { doAction() }` — another goroutine may revoke permission between check and action. Hold lock or use DB transaction.
- **Double-spend**: `if balance >= amount { balance -= amount }` — two concurrent requests pass the check before either commits.
- **Concurrent map**: `map[K]V` read/written from multiple goroutines without `sync.Mutex` → Go runtime fatal crash (not just data corruption).
- **sync.Pool use-after-put**: object returned to pool, then caller continues to use pointer → data race.

Race detector:

```bash
go test -race -count=1 ./path/to/changed/...
```

A detected race is always a defect to fix, but its **security** severity depends on what races:

| What races | Severity |
|---|---|
| Auth / permission / balance / quota state | `P1` (CWE-367) |
| Request-scoped state an attacker can drive concurrently | `P2` |
| Test scaffolding, metrics counters, log buffers | `P3`, or reliability-only — say which |

State the attacker-reachability reason. "The race detector fired" is not a severity
justification. Governed by `severity-calibration.md` §Governing Rule.

### Domain 8 — Language-Specific Injection Sinks

| Sink | Risk | Mitigation |
|------|------|-----------|
| `text/template.Execute` with user content | XSS | Use `html/template` |
| `os/exec.Command("sh", "-c", userInput)` | Command injection | Use `exec.Command(binary, args...)` with separate args |
| `net/http.Redirect(w, r, userURL, 302)` | Open redirect | Validate URL against allowlist or force relative path |
| `filepath.Join(base, userInput)` | Path traversal | Use `os.Root`/`os.OpenRoot` (Go 1.24+) — symlink-aware. A `HasPrefix` check is lexical only and allows sibling-prefix and symlink escapes; see §Path Traversal |
| `encoding/json.Decoder` unbounded | DoS | Use `http.MaxBytesReader` or `io.LimitReader` |
| `xml.NewDecoder` on untrusted input | Memory exhaustion from large/deep input | Bound input with `http.MaxBytesReader`/`io.LimitReader`. **Do not** look for a decoder depth knob — see below |

#### Go XML: what actually applies (and what does not)

Do not port Java/Python XML advice to Go. Verified against the toolchain:

| Classic XML attack | Applies to Go `encoding/xml`? | Why |
|---|---|---|
| XXE (external entity → file read/SSRF) | **No** | Go never resolves external entities. `<!ENTITY x SYSTEM "file:///etc/passwd">` yields `XML syntax error: invalid character entity &x;` |
| Billion laughs (entity expansion) | **No** | Go does not expand DTD-declared entities at all — same `invalid character entity` error |
| Deeply-nested-element DoS | **Already mitigated** | `encoding/xml` enforces a **built-in, non-configurable** unmarshal depth cap; depth 10001 returns `exceeded max depth` |
| Large-payload memory exhaustion | **Yes** | This is the real Go XML risk, and the only one you must fix in code |

Consequences for review:

- **There is no `xml.Decoder.MaxDepth` field** in any Go version — `d.MaxDepth = N` fails to
  compile with `undefined (type *xml.Decoder has no field or method MaxDepth)`. Never
  recommend it, and flag it as an error if a diff adds it.
- Reporting "XXE" or "billion laughs" against stdlib `encoding/xml` is a **false positive**
  (Suppression Rule 3 — the parser structurally cannot reach the sink). Record it as
  suppressed with this reason.
- Do report missing input bounds: `xml.NewDecoder(r.Body)` without
  `http.MaxBytesReader` is the same finding class as the `encoding/json` row above.
- **These exemptions are stdlib-only.** If the repo uses a cgo binding to libxml2/expat, or
  another XML library that honours DTDs, the classic attacks are live again — check the
  library's entity-resolution settings and treat it as `Applicable`.

### Domain 9 — Static Scanner Posture

- `gosec ./...` triaged: each finding checked for exploitability on reachable paths.
- Suppressed `//nolint:gosec` must have inline rationale. Judge the **suppressed rule**, not the missing comment: if the underlying finding is exploitable, report it at its own severity. If it is a genuine false positive, an absent rationale is a hygiene note under `Hardening suggestions` — not a `P3` finding. Treat it as `P3` only when the suppression hides a defense gap you cannot assess.
- False positives documented under `Suppressed Items`.

### Domain 10 — Dependency Vulnerability Posture

- `govulncheck ./...` (source mode): call-trace reachable vulns are `confirmed/likely`.
- `govulncheck -mode=binary <path-to-binary>`: exposure signal only; do not mark `confirmed` without source reachability. Requires a built artifact — `-mode=binary ./...` errors with `"./..." is not a file`.
- Remediation path: upgrade available → `P2`; no fix available → note in `Uncovered Risk List`.

---

## Extended Security Patterns — BAD/GOOD Code Reference

The following sections provide concrete Go code examples for security domains frequently encountered in reviews but not fully covered by Gate D's 10 domains.

### Authentication & Authorization (AuthN/AuthZ)

#### JWT Validation

```go
// BAD: no algorithm restriction — attacker can use alg=none
func ParseToken(tokenString string) (*jwt.Token, error) {
    return jwt.Parse(tokenString, func(t *jwt.Token) (interface{}, error) {
        return mySecret, nil
    })
}

// GOOD: enforce algorithm and validate claims
func ParseToken(tokenString string) (*jwt.Token, error) {
    return jwt.Parse(tokenString, func(t *jwt.Token) (interface{}, error) {
        if _, ok := t.Method.(*jwt.SigningMethodHMAC); !ok {
            return nil, fmt.Errorf("unexpected signing method: %v", t.Header["alg"])
        }
        return mySecret, nil
    }, jwt.WithValidMethods([]string{"HS256"}),
       jwt.WithIssuer("myapp"),
       jwt.WithAudience("myapi"),
    )
}
```

Key checks:
- Algorithm explicitly constrained (reject `alg=none`)
- Issuer/audience validated
- Expiry enforced (library default or explicit)
- Token stored securely (not in localStorage for web apps)

#### IDOR (Insecure Direct Object Reference)

```go
// BAD: user can access any order by ID
func GetOrder(w http.ResponseWriter, r *http.Request) {
    orderID := chi.URLParam(r, "id")
    order, err := repo.GetOrder(r.Context(), orderID)
    if err != nil {
        http.Error(w, "not found", http.StatusNotFound)
        return
    }
    json.NewEncoder(w).Encode(order)
}

// GOOD: verify ownership before returning
func GetOrder(w http.ResponseWriter, r *http.Request) {
    orderID := chi.URLParam(r, "id")
    userID := auth.UserIDFrom(r.Context())
    order, err := repo.GetOrder(r.Context(), orderID)
    if err != nil {
        http.Error(w, "not found", http.StatusNotFound)
        return
    }
    if order.UserID != userID {
        http.Error(w, "not found", http.StatusNotFound) // 404, not 403
        return
    }
    json.NewEncoder(w).Encode(order)
}
```

Key checks:
- Every resource access verifies ownership or tenant scope
- Return 404 (not 403) to avoid confirming resource existence
- Multi-tenant queries include `WHERE tenant_id = ?`

#### Middleware Ordering

```go
// BAD: route registered before auth middleware
r := chi.NewRouter()
r.Get("/api/admin/users", adminHandler) // no auth!
r.Use(authMiddleware)

// GOOD: auth middleware applied before routes
r := chi.NewRouter()
r.Use(authMiddleware)
r.Get("/api/admin/users", adminHandler) // protected
```

Key checks:
- Auth middleware applied before route registration
- Group-level middleware for protected route groups
- No accidental public routes inside protected groups

#### Session Management

```go
// BAD: session ID not regenerated after login (session fixation)
func LoginHandler(w http.ResponseWriter, r *http.Request) {
    // authenticate user...
    session, _ := store.Get(r, "session")
    session.Values["user_id"] = user.ID
    session.Save(r, w)
}

// GOOD: regenerate session after privilege change
func LoginHandler(w http.ResponseWriter, r *http.Request) {
    // authenticate user...
    oldSession, _ := store.Get(r, "session")
    oldSession.Options.MaxAge = -1
    oldSession.Save(r, w) // invalidate old session

    newSession, _ := store.New(r, "session")
    newSession.Values["user_id"] = user.ID
    newSession.Options = &sessions.Options{
        HttpOnly: true,
        Secure:   true,
        SameSite: http.SameSiteStrictMode,
        MaxAge:   3600,
    }
    newSession.Save(r, w)
}
```

### SSRF (Server-Side Request Forgery)

```go
// BAD: user-controlled URL fetched without validation
func ProxyHandler(w http.ResponseWriter, r *http.Request) {
    targetURL := r.URL.Query().Get("url")
    resp, err := http.Get(targetURL) // SSRF: can reach internal services
    if err != nil {
        http.Error(w, "fetch failed", http.StatusBadGateway)
        return
    }
    defer resp.Body.Close()
    io.Copy(w, resp.Body)
}

// ALSO BAD (the common "fixed" version): resolve-then-dial-by-name.
// LookupIPAddr validates the IPs, then DialContext is handed the HOSTNAME again, so the
// resolver runs a SECOND time. An attacker whose DNS answer changes between the two
// lookups (DNS rebinding) passes the check and connects somewhere else entirely.
func unsafeDialContext(ctx context.Context, network, addr string) (net.Conn, error) {
    host, _, _ := net.SplitHostPort(addr)
    ips, err := net.DefaultResolver.LookupIPAddr(ctx, host) // check
    if err != nil {
        return nil, err
    }
    for _, ip := range ips {
        if ip.IP.IsLoopback() || ip.IP.IsPrivate() {
            return nil, fmt.Errorf("blocked %s", ip.IP)
        }
    }
    return (&net.Dialer{}).DialContext(ctx, network, addr) // use — resolves AGAIN
}

// GOOD: allowlist + scheme pin + redirects refused + IP validated at CONNECT time.
var allowedHosts = map[string]bool{
    "api.example.com": true,
    "cdn.example.com": true,
}

// blockNonPublic runs after DNS resolution on the concrete IP about to be dialed, so
// there is no check-then-resolve window. Dialer.Control is the hook that closes
// DNS rebinding; a pre-dial lookup cannot.
func blockNonPublic(network, address string, _ syscall.RawConn) error {
    host, _, err := net.SplitHostPort(address)
    if err != nil {
        return err
    }
    ip, err := netip.ParseAddr(host)
    if err != nil {
        return fmt.Errorf("ssrf guard: %q is not a resolved IP", host)
    }
    ip = ip.Unmap() // defeat ::ffff:127.0.0.1 smuggling
    if !ip.IsGlobalUnicast() || ip.IsPrivate() || ip.IsLoopback() ||
        ip.IsLinkLocalUnicast() || ip.IsLinkLocalMulticast() ||
        ip.IsInterfaceLocalMulticast() {
        return fmt.Errorf("ssrf guard: blocked non-public address %s", ip)
    }
    return nil
}

// Reuse one client; it carries the guard, the timeout, and the redirect policy.
var safeClient = &http.Client{
    Timeout: 10 * time.Second,
    // Refuse redirects outright. Following them re-opens SSRF: an allowlisted host
    // can 302 to 169.254.169.254 and the allowlist is never consulted again.
    CheckRedirect: func(*http.Request, []*http.Request) error {
        return http.ErrUseLastResponse
    },
    Transport: &http.Transport{
        DialContext: (&net.Dialer{Timeout: 5 * time.Second, Control: blockNonPublic}).DialContext,
    },
}

func ProxyHandler(w http.ResponseWriter, r *http.Request) {
    parsed, err := url.Parse(r.URL.Query().Get("url"))
    if err != nil || !allowedHosts[parsed.Hostname()] {
        http.Error(w, "forbidden target", http.StatusForbidden)
        return
    }
    if parsed.Scheme != "https" {
        http.Error(w, "https only", http.StatusForbidden)
        return
    }
    req, err := http.NewRequestWithContext(r.Context(), http.MethodGet, parsed.String(), nil)
    if err != nil {
        http.Error(w, "bad target", http.StatusBadRequest)
        return
    }
    resp, err := safeClient.Do(req)
    if err != nil {
        http.Error(w, "fetch failed", http.StatusBadGateway)
        return
    }
    defer resp.Body.Close()
    if resp.StatusCode >= 300 && resp.StatusCode < 400 {
        http.Error(w, "redirect refused", http.StatusBadGateway)
        return
    }
    io.Copy(w, io.LimitReader(resp.Body, 10<<20)) // 10MB limit
}
```

Verified: this guard rejects `localhost`, `127.0.0.1`, `[::ffff:127.0.0.1]`, `169.254.169.254`
(cloud IMDS), and `10.0.0.1` at connect time.

Key checks — an allowlist alone fails **all three** of the first items:
- IP validated at connect time via `Dialer.Control`, **not** by a pre-dial `LookupIP`
  (a separate lookup leaves a DNS-rebinding window)
- Redirects refused or re-validated per hop (`CheckRedirect`); an allowlisted host that
  returns 302 otherwise bypasses the allowlist entirely
- IPv4-mapped IPv6 unmapped before classification (`::ffff:127.0.0.1`)
- User-controlled URLs validated against a host allowlist
- Scheme restricted (https only or explicit allowlist)
- Response body size limited; client timeout set; one shared client reused

When reviewing, treat "validates the hostname against an allowlist" as **necessary but not
sufficient**. Ask specifically: what happens on a 302, and what IP is actually connected to?

### XSS (Cross-Site Scripting)

```go
// BAD: text/template does not auto-escape HTML
import "text/template"

func RenderPage(w http.ResponseWriter, r *http.Request) {
    tmpl := template.Must(template.New("page").Parse(`<h1>Hello {{.Name}}</h1>`))
    tmpl.Execute(w, map[string]string{"Name": r.URL.Query().Get("name")})
    // name=<script>alert(1)</script> renders unescaped
}

// GOOD: html/template auto-escapes contextually
import "html/template"

func RenderPage(w http.ResponseWriter, r *http.Request) {
    tmpl := template.Must(template.New("page").Parse(`<h1>Hello {{.Name}}</h1>`))
    w.Header().Set("Content-Type", "text/html; charset=utf-8")
    tmpl.Execute(w, map[string]string{"Name": r.URL.Query().Get("name")})
    // name=<script>alert(1)</script> is escaped to &lt;script&gt;...
}
```

```go
// BAD: template.HTML() defeats auto-escaping
func RenderComment(w http.ResponseWriter, data CommentData) {
    data.Body = template.HTML(data.Body) // user content rendered raw!
    tmpl.Execute(w, data)
}

// GOOD: only use template.HTML for trusted, pre-sanitized content
func RenderComment(w http.ResponseWriter, data CommentData) {
    data.Body = sanitizer.Sanitize(data.Body) // use bluemonday or similar
    tmpl.Execute(w, data) // auto-escaped by html/template
}
```

Key checks:
- `html/template` for all user-facing HTML (never `text/template`)
- `template.HTML()` / `template.JS()` / `template.CSS()` used only on trusted content
- `Content-Type: text/html; charset=utf-8` explicitly set
- JSON API responses set `Content-Type: application/json` (prevents browser HTML interpretation)

### CORS Misconfiguration

```go
// BAD: wildcard origin with credentials
func CORSMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        w.Header().Set("Access-Control-Allow-Origin", "*")
        w.Header().Set("Access-Control-Allow-Credentials", "true") // invalid with *
        next.ServeHTTP(w, r)
    })
}

// BAD: reflecting Origin header without validation
func CORSMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        origin := r.Header.Get("Origin")
        w.Header().Set("Access-Control-Allow-Origin", origin) // reflects anything
        w.Header().Set("Access-Control-Allow-Credentials", "true")
        next.ServeHTTP(w, r)
    })
}

// GOOD: explicit origin allowlist
var allowedOrigins = map[string]bool{
    "https://app.example.com":  true,
    "https://admin.example.com": true,
}

func CORSMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        origin := r.Header.Get("Origin")
        if allowedOrigins[origin] {
            w.Header().Set("Access-Control-Allow-Origin", origin)
            w.Header().Set("Access-Control-Allow-Credentials", "true")
            w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE")
            w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")
            w.Header().Set("Access-Control-Max-Age", "86400")
        }
        if r.Method == http.MethodOptions {
            w.WriteHeader(http.StatusNoContent)
            return
        }
        next.ServeHTTP(w, r)
    })
}
```

Key checks:
- No `Access-Control-Allow-Origin: *` with `Credentials: true`
- Origin validated against explicit allowlist (not regex that can be bypassed)
- `Access-Control-Allow-Methods` restricted to needed methods
- `Access-Control-Allow-Headers` restricted to needed headers
- Preflight responses cached with `Max-Age`

### Rate Limiting & Abuse Prevention

```go
// BAD: no rate limiting on login endpoint
func LoginHandler(w http.ResponseWriter, r *http.Request) {
    // ... authenticate
}

// GOOD: per-IP rate limiting
import "golang.org/x/time/rate"

type IPRateLimiter struct {
    mu       sync.Mutex
    limiters map[string]*rate.Limiter
    rate     rate.Limit
    burst    int
}

func NewIPRateLimiter(r rate.Limit, burst int) *IPRateLimiter {
    return &IPRateLimiter{
        limiters: make(map[string]*rate.Limiter),
        rate:     r,
        burst:    burst,
    }
}

func (rl *IPRateLimiter) GetLimiter(ip string) *rate.Limiter {
    rl.mu.Lock()
    defer rl.mu.Unlock()
    limiter, exists := rl.limiters[ip]
    if !exists {
        limiter = rate.NewLimiter(rl.rate, rl.burst)
        rl.limiters[ip] = limiter
    }
    return limiter
}

func RateLimitMiddleware(rl *IPRateLimiter) func(http.Handler) http.Handler {
    return func(next http.Handler) http.Handler {
        return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
            ip, _, _ := net.SplitHostPort(r.RemoteAddr)
            limiter := rl.GetLimiter(ip)
            if !limiter.Allow() {
                w.Header().Set("Retry-After", "60")
                http.Error(w, "Too Many Requests", http.StatusTooManyRequests)
                return
            }
            next.ServeHTTP(w, r)
        })
    }
}
```

Key checks:
- Authentication endpoints (login, register, password reset) rate-limited
- Per-IP and/or per-user limits
- Returns `429 Too Many Requests` with `Retry-After` header
- IP limiter map has cleanup mechanism (TTL or periodic sweep) to prevent memory leak
- Rate limits applied before expensive operations (DB lookup, hash computation)
- Consider `X-Forwarded-For` / `X-Real-IP` behind reverse proxy (but validate trust chain)

### HTTP Security Headers

```go
// BAD: no security headers
func handler(w http.ResponseWriter, r *http.Request) {
    json.NewEncoder(w).Encode(data)
}

// GOOD: security headers middleware
func SecurityHeaders(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        w.Header().Set("X-Content-Type-Options", "nosniff")
        w.Header().Set("X-Frame-Options", "DENY")
        w.Header().Set("Strict-Transport-Security", "max-age=63072000; includeSubDomains; preload")
        w.Header().Set("Content-Security-Policy", "default-src 'self'")
        w.Header().Set("Referrer-Policy", "strict-origin-when-cross-origin")
        w.Header().Set("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        next.ServeHTTP(w, r)
    })
}
```

| Header | Purpose | Minimum |
|--------|---------|---------|
| `X-Content-Type-Options` | Prevents MIME-sniffing | `nosniff` |
| `X-Frame-Options` | Prevents clickjacking | `DENY` or `SAMEORIGIN` |
| `Strict-Transport-Security` | Forces HTTPS | `max-age=63072000; includeSubDomains` |
| `Content-Security-Policy` | Controls resource loading | `default-src 'self'` (tune per app) |
| `Referrer-Policy` | Controls referer header leakage | `strict-origin-when-cross-origin` |
| `Permissions-Policy` | Restricts browser features | Deny unused features |

Key checks:
- HSTS set with `max-age ≥ 1 year` for production
- CSP configured (even basic `default-src 'self'` is better than none)
- API endpoints set `Content-Type: application/json` explicitly

### Timing Attacks & Constant-Time Comparison

```go
// BAD: early-return comparison leaks secret length via timing
func ValidateAPIKey(provided, stored string) bool {
    return provided == stored // timing side-channel
}

// BAD: bytes.Equal is not constant-time
func ValidateHMAC(provided, expected []byte) bool {
    return bytes.Equal(provided, expected) // timing side-channel
}

// GOOD: constant-time comparison
import "crypto/subtle"

func ValidateAPIKey(provided, stored string) bool {
    return subtle.ConstantTimeCompare([]byte(provided), []byte(stored)) == 1
}

func ValidateHMAC(provided, expected []byte) bool {
    return subtle.ConstantTimeCompare(provided, expected) == 1
}
```

Key checks:
- All secret/token/HMAC comparisons use `subtle.ConstantTimeCompare`
- `==` or `bytes.Equal` on secrets: `P2` **when the comparison is remotely observable and the attacker can retry** (API key check on a hot endpoint). Drop to `P3` where timing is not measurable through the surrounding noise — a single comparison behind an expensive DB round-trip, or a CLI tool — and say which case applies
- Applies to: API key validation, webhook signature verification, CSRF token comparison, password reset tokens

### Input Validation & Deserialization Safety

#### Request Body Size Limits

```go
// BAD: unbounded request body
func CreateHandler(w http.ResponseWriter, r *http.Request) {
    var req CreateRequest
    json.NewDecoder(r.Body).Decode(&req) // attacker can send GB payload
}

// GOOD: limit body size
func CreateHandler(w http.ResponseWriter, r *http.Request) {
    r.Body = http.MaxBytesReader(w, r.Body, 1<<20) // 1MB limit
    var req CreateRequest
    if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
        http.Error(w, "request too large or invalid", http.StatusBadRequest)
        return
    }
}
```

#### Recursive Structure Depth

```go
// BAD: deeply nested JSON causes stack overflow or excessive CPU
type Node struct {
    Children []Node `json:"children"`
}

func ParseTree(w http.ResponseWriter, r *http.Request) {
    r.Body = http.MaxBytesReader(w, r.Body, 1<<20)
    var root Node
    json.NewDecoder(r.Body).Decode(&root) // nested 10000 deep
    processTree(root) // stack overflow
}

// GOOD: validate depth after parsing or use streaming parser with depth limit
func ParseTree(w http.ResponseWriter, r *http.Request) {
    r.Body = http.MaxBytesReader(w, r.Body, 1<<20)
    var root Node
    if err := json.NewDecoder(r.Body).Decode(&root); err != nil {
        http.Error(w, "invalid JSON", http.StatusBadRequest)
        return
    }
    if depth := measureDepth(root); depth > 10 {
        http.Error(w, "nesting too deep", http.StatusBadRequest)
        return
    }
}
```

#### Integer Overflow in Quantity/Amount

```go
// BAD: integer overflow on multiplication
func CalculateTotal(price, quantity int32) int32 {
    return price * quantity // may overflow silently
}

// GOOD: check for overflow before arithmetic
func CalculateTotal(price, quantity int64) (int64, error) {
    if price > 0 && quantity > math.MaxInt64/price {
        return 0, fmt.Errorf("integer overflow: %d * %d", price, quantity)
    }
    return price * quantity, nil
}
```

Key checks:
- `http.MaxBytesReader` on all endpoints accepting body input
- JSON/XML depth limited for recursive structures
- Integer overflow checked in financial/quantity calculations
- `http.Server.ReadTimeout` and `WriteTimeout` set to prevent slowloris

### Path Traversal

```go
// BAD: filepath.Join does not prevent ../ traversal
func ServeFile(w http.ResponseWriter, r *http.Request) {
    filename := r.URL.Query().Get("file")
    path := filepath.Join("/data/uploads", filename)
    http.ServeFile(w, r, path) // ../../etc/passwd
}

// ALSO BAD: prefix check without a trailing separator — sibling-directory escape.
// base="/var/app", filename="../app-evil/secret" -> "/var/app-evil/secret",
// and strings.HasPrefix("/var/app-evil/secret", "/var/app") is TRUE. Verified.
func ServeFile(w http.ResponseWriter, r *http.Request) {
    path := filepath.Join("/var/app", r.URL.Query().Get("file"))
    if !strings.HasPrefix(filepath.Clean(path), "/var/app") { // missing trailing "/"
        http.Error(w, "forbidden", http.StatusForbidden)
        return
    }
    http.ServeFile(w, r, path)
}

// STILL BAD for file access: a lexical check cannot see symlinks.
// If /data/uploads/link -> /etc, then "link/passwd" stays lexically inside the base
// and the prefix check passes — verified reading a file planted outside the base.
func ServeFile(w http.ResponseWriter, r *http.Request) {
    path := filepath.Join("/data/uploads", r.URL.Query().Get("file"))
    if !strings.HasPrefix(filepath.Clean(path), "/data/uploads"+string(os.PathSeparator)) {
        http.Error(w, "forbidden", http.StatusForbidden)
        return
    }
    http.ServeFile(w, r, path) // symlink inside the base still escapes
}

// GOOD (Go 1.24+): os.Root gives kernel-enforced, symlink-aware containment.
// Every operation is resolved relative to the root and refuses to leave it.
var uploadRoot *os.Root // opened once at startup: os.OpenRoot("/data/uploads")

func ServeFile(w http.ResponseWriter, r *http.Request) {
    // Clean first: a trailing separator on a symlink component bypasses os.Root
    // containment (GO-2026-4970). See the note below this example.
    rel := filepath.Clean(r.URL.Query().Get("file"))
    if rel == "." || rel == ".." || filepath.IsAbs(rel) {
        http.Error(w, "forbidden", http.StatusForbidden)
        return
    }
    f, err := uploadRoot.Open(rel)
    if err != nil {
        // "path escapes from parent" on traversal or symlink escape; also covers
        // absolute paths and ".." without any manual string checking.
        http.Error(w, "forbidden", http.StatusForbidden)
        return
    }
    defer f.Close()
    st, err := f.Stat()
    if err != nil || st.IsDir() {
        http.Error(w, "forbidden", http.StatusForbidden)
        return
    }
    http.ServeContent(w, r, st.Name(), st.ModTime(), f)
}
```

Verified against the toolchain: with a symlink planted inside the base,
`os.Root.Open` returns `openat link/secret.txt: path escapes from parent`, while the lexical
guard allowed the read and returned the outside file's contents.

#### `os.Root` is necessary but not self-sufficient: the trailing-separator escape

`os.Root` has a containment bug in the **trailing-separator** form, advisory
[`GO-2026-4970`](https://pkg.go.dev/vuln/GO-2026-4970). Reproduced here on **go1.26.1**, which is
**within** the advisory's affected range — the reproduction confirms the advisory, it does not
contradict it.

**Fixed in Go 1.25.12+, 1.26.5+, and 1.27.0-rc.2+.** Upgrading the toolchain is the primary fix;
confirm the current ranges against the advisory rather than trusting this line, and let
`govulncheck` decide for your build. The observed behaviour on an affected toolchain:

```
BLOCKED         Open("link")            openat link: path escapes from parent
*** ALLOWED *** Open("link/")           isdir=true          <-- escapes
BLOCKED         Open("link/.")          path escapes from parent
BLOCKED         Open("link/secret.txt") path escapes from parent
BLOCKED         Open("link/sub/")       path escapes from parent
*** ALLOWED *** Stat("link/")
```

And the escaped handle is fully usable: `Readdirnames` on it listed the outside directory
(`[secret.txt]`) and reading through it returned `TOP SECRET`. Only the bare
`<symlink>/` shape escapes — every deeper path is blocked.

Two things are therefore required, in this order:

1. **Upgrade the toolchain** to a fixed release (1.25.12+ / 1.26.5+ / 1.27.0-rc.2+) and keep
   `govulncheck` in CI so a regression or a newly disclosed range is caught. This is the fix.
2. **`filepath.Clean` the relative input before handing it to `os.Root`** — defense in depth, not
   a substitute for upgrading. It matters because you rarely control every toolchain that builds
   the code, and a future containment bug may take a different shape. Verified as a complete
   mitigation for this shape — `Clean("link/")` → `"link"`, which `os.Root` correctly blocks,
   while legitimate paths are unaffected (`"realdir/"` → `"realdir"`, `"./ok.txt"` → `"ok.txt"`,
   both still allowed):

```go
func (s *Server) open(userInput string) (*os.File, error) {
    // Clean strips the trailing separator that bypasses os.Root containment,
    // and normalises "./" and duplicate separators. Do this BEFORE root.Open.
    rel := filepath.Clean(userInput)
    if rel == "." || rel == ".." || filepath.IsAbs(rel) {
        return nil, fs.ErrPermission
    }
    return s.root.Open(rel)
}
```

Defense in depth, since a lexical pre-pass is exactly the kind of thing that gets removed
later: when you expect a file, `Stat` the result and reject directories — the escape yields a
directory handle, so a `!IsDir()` check independently blocks it.

Key checks:
- **Prefer `os.Root` (`os.OpenRoot`) for any user-influenced file access on Go ≥ 1.24.** It is
  the only option here that is symlink-aware — but pair it with the two requirements above.
- If you must do it lexically (older Go), the prefix **must** include a trailing separator, or
  compare `filepath.Rel(base, target)` and reject results starting with `..`.
  `filepath.IsLocal` is also lexical-only — it rejects `..` and absolute paths but knows nothing
  about symlinks, so it is not sufficient on its own for filesystem access.
- A lexical check is adequate only when the path is never opened (e.g. building a key for an
  object store with no symlink semantics). Say which case applies.
- Reject null bytes; `http.Dir` / `http.FileServer` scoped to the intended directory
  (`http.Dir` already refuses `..`, but not symlinks out of the tree).

### Open Redirect

```go
// BAD: redirect to user-controlled URL without validation
func CallbackHandler(w http.ResponseWriter, r *http.Request) {
    redirectURL := r.URL.Query().Get("redirect")
    http.Redirect(w, r, redirectURL, http.StatusFound)
    // attacker: ?redirect=https://evil.com/phishing
}

// GOOD: restrict to relative paths or validate against allowlist
func CallbackHandler(w http.ResponseWriter, r *http.Request) {
    redirectURL := r.URL.Query().Get("redirect")
    parsed, err := url.Parse(redirectURL)
    if err != nil || parsed.IsAbs() {
        http.Redirect(w, r, "/", http.StatusFound)
        return
    }
    // ensure no host-relative URL (e.g., //evil.com)
    if strings.HasPrefix(redirectURL, "//") {
        http.Redirect(w, r, "/", http.StatusFound)
        return
    }
    http.Redirect(w, r, redirectURL, http.StatusFound)
}
```

Key checks:
- User-controlled redirect targets validated
- Restrict to relative paths or explicit domain allowlist
- Block `//evil.com` and `javascript:` scheme
- Return safe default on validation failure
