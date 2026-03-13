# Security Review — Go Secure-Coding Reference

This reference provides deep details for Gate B (resource inventory) and Gate D (10-domain coverage) when reviewing Go code.

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

Resource is closed/released on both success and error paths. Any violation is at least `P2`.

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

### Domain 2 — Injection + SQL Lifecycle Safety

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

### Domain 4 — Secret/Config Management

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

### Domain 5 — TLS Safety

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

### Domain 7 — Concurrency Safety

Critical patterns:

- **TOCTOU**: `if hasPermission(userID) { doAction() }` — another goroutine may revoke permission between check and action. Hold lock or use DB transaction.
- **Double-spend**: `if balance >= amount { balance -= amount }` — two concurrent requests pass the check before either commits.
- **Concurrent map**: `map[K]V` read/written from multiple goroutines without `sync.Mutex` → Go runtime fatal crash (not just data corruption).
- **sync.Pool use-after-put**: object returned to pool, then caller continues to use pointer → data race.

Race detector:

```bash
go test -race -count=1 ./path/to/changed/...
```

Any race: at least `P2`. Race on auth/balance/permission state: `P1` (CWE-367).

### Domain 8 — Go-Specific Injection Sinks

| Sink | Risk | Mitigation |
|------|------|-----------|
| `text/template.Execute` with user content | XSS | Use `html/template` |
| `os/exec.Command("sh", "-c", userInput)` | Command injection | Use `exec.Command(binary, args...)` with separate args |
| `net/http.Redirect(w, r, userURL, 302)` | Open redirect | Validate URL against allowlist or force relative path |
| `filepath.Join(base, userInput)` | Path traversal | Check `strings.HasPrefix(filepath.Clean(result), base)` |
| `encoding/json.Decoder` unbounded | DoS | Use `http.MaxBytesReader` or `io.LimitReader` |
| `xml.NewDecoder` on untrusted input | Billion-laughs DoS | Set `d.MaxDepth` (Go 1.24+) or limit input size |

### Domain 9 — Static Scanner Posture

- `gosec ./...` triaged: each finding checked for exploitability on reachable paths.
- Suppressed `//nolint:gosec` must have inline rationale; missing rationale is at least `P3`.
- False positives documented under `Suppressed Items`.

### Domain 10 — Dependency Vulnerability Posture

- `govulncheck ./...` (source mode): call-trace reachable vulns are `confirmed/likely`.
- `govulncheck -mode=binary`: exposure signal only; do not mark `confirmed` without source reachability.
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

// GOOD: allowlist + block private IPs
var allowedHosts = map[string]bool{
    "api.example.com":    true,
    "cdn.example.com":    true,
}

func ProxyHandler(w http.ResponseWriter, r *http.Request) {
    targetURL := r.URL.Query().Get("url")
    parsed, err := url.Parse(targetURL)
    if err != nil || !allowedHosts[parsed.Hostname()] {
        http.Error(w, "forbidden target", http.StatusForbidden)
        return
    }
    if parsed.Scheme != "https" {
        http.Error(w, "https only", http.StatusForbidden)
        return
    }

    client := &http.Client{
        Transport: &http.Transport{
            DialContext: safeDialContext, // blocks private IPs
        },
        Timeout: 10 * time.Second,
    }
    resp, err := client.Get(parsed.String())
    if err != nil {
        http.Error(w, "fetch failed", http.StatusBadGateway)
        return
    }
    defer resp.Body.Close()
    io.Copy(w, io.LimitReader(resp.Body, 10<<20)) // 10MB limit
}

// safeDialContext rejects connections to private/loopback addresses
func safeDialContext(ctx context.Context, network, addr string) (net.Conn, error) {
    host, _, err := net.SplitHostPort(addr)
    if err != nil {
        return nil, err
    }
    ips, err := net.DefaultResolver.LookupIPAddr(ctx, host)
    if err != nil {
        return nil, err
    }
    for _, ip := range ips {
        if ip.IP.IsLoopback() || ip.IP.IsPrivate() || ip.IP.IsLinkLocalUnicast() {
            return nil, fmt.Errorf("blocked: resolved to private IP %s", ip.IP)
        }
    }
    dialer := &net.Dialer{Timeout: 5 * time.Second}
    return dialer.DialContext(ctx, network, addr)
}
```

Key checks:
- User-controlled URLs validated against host allowlist
- Scheme restricted (https only or explicit allowlist)
- DNS resolution checked for private/loopback IPs (including IPv6)
- Response body size limited
- Client timeout set
- Redirect following disabled or limited (`CheckRedirect`)

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
- `==` or `bytes.Equal` on secrets is at least `P2`
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

// GOOD: validate cleaned path stays within base directory
func ServeFile(w http.ResponseWriter, r *http.Request) {
    filename := r.URL.Query().Get("file")
    path := filepath.Join("/data/uploads", filename)
    cleaned := filepath.Clean(path)
    if !strings.HasPrefix(cleaned, "/data/uploads/") {
        http.Error(w, "forbidden", http.StatusForbidden)
        return
    }
    http.ServeFile(w, r, cleaned)
}
```

Key checks:
- `filepath.Clean` + prefix check after `filepath.Join`
- Reject filenames containing `..`, null bytes, or absolute paths
- `http.Dir` / `http.FileServer` scoped to intended directory

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
