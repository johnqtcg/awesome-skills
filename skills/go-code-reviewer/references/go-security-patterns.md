# Go Security Patterns

Deep-dive reference for the **Security (High)** category in SKILL.md step 6.

## Table of Contents

- [SQL Injection](#sql-injection)
- [Command Injection](#command-injection)
- [Path Traversal](#path-traversal)
- [Insecure TLS](#insecure-tls)
- [Weak Crypto](#weak-crypto)
- [Hardcoded Secrets](#hardcoded-secrets)
- [Unsafe Package](#unsafe-package)
- [Sensitive Data in Logs / Errors](#sensitive-data-in-logs--errors)
- [Authentication & Authorization (AuthN/AuthZ)](#authentication--authorization-authnauthz)
- [SSRF (Server-Side Request Forgery)](#ssrf-server-side-request-forgery)
- [XSS (Cross-Site Scripting)](#xss-cross-site-scripting)
- [Rate Limiting & Abuse Prevention](#rate-limiting--abuse-prevention)
- [CORS Misconfiguration](#cors-misconfiguration)
- [HTTP Security Headers](#http-security-headers)
- [Timing Attacks & Constant-Time Comparison](#timing-attacks--constant-time-comparison)
- [Input Validation & Deserialization Safety](#input-validation--deserialization-safety)

## SQL Injection

```go
// BAD: string interpolation
query := fmt.Sprintf("SELECT * FROM users WHERE id = '%s'", userID)
rows, err := db.Query(query)

// GOOD: parameterized query
rows, err := db.QueryContext(ctx, "SELECT * FROM users WHERE id = $1", userID)
```

Also watch for:
- `database/sql` `Exec` with string concatenation
- Raw SQL in ORM bypass methods (e.g., `gorm.Raw()`)

## Command Injection

```go
// BAD: user input in shell command
cmd := exec.Command("sh", "-c", "echo "+userInput)

// GOOD: pass arguments directly (no shell expansion)
cmd := exec.CommandContext(ctx, "echo", userInput)
```

Key checks:
- Never pass user input through `sh -c`
- Validate/allowlist command arguments
- Prefer library calls over shelling out

## Path Traversal

```go
// BAD: unchecked path join
filePath := filepath.Join(baseDir, userInput)
data, _ := os.ReadFile(filePath)

// GOOD: validate resolved path is within base
filePath := filepath.Join(baseDir, filepath.Clean(userInput))
if !strings.HasPrefix(filePath, filepath.Clean(baseDir)+string(os.PathSeparator)) {
    return fmt.Errorf("path traversal attempt: %s", userInput)
}
```

## Insecure TLS

```go
// BAD: disables certificate verification
client := &http.Client{
    Transport: &http.Transport{
        TLSClientConfig: &tls.Config{
            InsecureSkipVerify: true, // FINDING: never in production
        },
    },
}

// GOOD: use default TLS verification
client := &http.Client{}

// ACCEPTABLE: custom CA pool for internal services
pool := x509.NewCertPool()
pool.AppendCertsFromPEM(caCert)
client := &http.Client{
    Transport: &http.Transport{
        TLSClientConfig: &tls.Config{
            RootCAs: pool,
        },
    },
}
```

## Weak Crypto

```go
// BAD: weak hash for security purposes
h := md5.Sum(password)  // or sha1.Sum
h := sha1.Sum(password)

// GOOD: use bcrypt for passwords
hash, err := bcrypt.GenerateFromPassword([]byte(password), bcrypt.DefaultCost)

// GOOD: use SHA-256+ for integrity checks
h := sha256.Sum256(data)
```

Flags:
- `crypto/md5` or `crypto/sha1` used for authentication/integrity
- `crypto/des` or `crypto/rc4` usage
- Hard-coded IV or nonce in encryption

## Hardcoded Secrets

```go
// BAD: secrets in source
const apiKey = "sk-proj-abc123..."
var dbPassword = "super_secret"

// GOOD: environment variables with validation
apiKey := os.Getenv("API_KEY")
if apiKey == "" {
    log.Fatal("API_KEY environment variable required")
}
```

Search patterns:
- String literals matching `sk-`, `ghp_`, `AKIA`, `-----BEGIN`, `password=`
- Constants or `var` declarations with credential-like names

## Unsafe Package

```go
// REQUIRES JUSTIFICATION: unsafe pointer conversion
ptr := unsafe.Pointer(&data[0])
```

Acceptable uses (must document why):
- Performance-critical syscall interop
- CGo bridge code
- Serialization of known-layout structs

Not acceptable:
- Bypassing type safety for convenience
- Working around interface constraints

## Sensitive Data in Logs / Errors

```go
// BAD: leaks credentials
log.Printf("auth failed for user=%s password=%s", user, password)
return fmt.Errorf("connection to %s failed", connStringWithPassword)

// GOOD: redact sensitive fields
log.Printf("auth failed for user=%s", user)
return fmt.Errorf("connection to database failed: %w", err)
```

Check for:
- Tokens, passwords, PII in `log.*`, `fmt.Errorf`, `slog.*`
- Full request/response bodies logged (may contain auth headers)
- Stack traces exposing internal paths in user-facing errors

## Authentication & Authorization (AuthN/AuthZ)

### JWT Validation

```go
// BAD: no signature verification
token, _ := jwt.Parse(tokenString, nil)
claims := token.Claims.(jwt.MapClaims)
userID := claims["sub"]

// BAD: accepting "none" algorithm
token, err := jwt.Parse(tokenString, func(t *jwt.Token) (interface{}, error) {
    return secretKey, nil // does not validate signing method
})

// GOOD: validate algorithm + signature + claims
token, err := jwt.Parse(tokenString, func(t *jwt.Token) (interface{}, error) {
    if _, ok := t.Method.(*jwt.SigningMethodHMAC); !ok {
        return nil, fmt.Errorf("unexpected signing method: %v", t.Header["alg"])
    }
    return secretKey, nil
})
if err != nil || !token.Valid {
    return ErrUnauthorized
}
claims, ok := token.Claims.(jwt.MapClaims)
if !ok || !claims.VerifyExpiresAt(time.Now().Unix(), true) {
    return ErrTokenExpired
}
```

Key checks:
- Always validate the signing algorithm explicitly (prevent "alg: none" attacks)
- Check `exp`, `iat`, `nbf` claims
- Use `jwt.WithValidMethods()` when available
- Store signing keys in environment/secrets manager, never in code

### IDOR (Insecure Direct Object Reference)

```go
// BAD: user can access any resource by ID without ownership check
func GetOrder(w http.ResponseWriter, r *http.Request) {
    orderID := chi.URLParam(r, "id")
    order, err := db.GetOrder(ctx, orderID)
    // returns any user's order
    json.NewEncoder(w).Encode(order)
}

// GOOD: verify ownership before returning resource
func GetOrder(w http.ResponseWriter, r *http.Request) {
    orderID := chi.URLParam(r, "id")
    currentUserID := auth.UserIDFromContext(r.Context())
    order, err := db.GetOrder(ctx, orderID)
    if err != nil {
        http.Error(w, "not found", http.StatusNotFound)
        return
    }
    if order.UserID != currentUserID {
        http.Error(w, "forbidden", http.StatusForbidden)
        return
    }
    json.NewEncoder(w).Encode(order)
}
```

Key checks:
- Every resource endpoint must verify the requesting user owns or has permission to access the resource
- Use **404 (not 403)** when you don't want to reveal that the resource exists to unauthorized users
- Apply ownership checks at the data layer when possible (e.g. `WHERE user_id = $1 AND id = $2`)

### Middleware Ordering

```go
// BAD: handler executes before auth middleware
r := chi.NewRouter()
r.Get("/admin/users", listUsers)         // unprotected!
r.Use(authMiddleware)
r.Get("/admin/settings", getSettings)

// GOOD: auth middleware wraps all protected routes
r := chi.NewRouter()
r.Use(authMiddleware)
r.Get("/admin/users", listUsers)
r.Get("/admin/settings", getSettings)

// GOOD: route-group scoping for mixed public/private
r := chi.NewRouter()
r.Group(func(r chi.Router) {
    r.Get("/health", healthCheck) // public
})
r.Group(func(r chi.Router) {
    r.Use(authMiddleware)
    r.Get("/admin/users", listUsers) // protected
})
```

Key checks:
- Auth/authz middleware must be registered **before** any handler it protects
- Check that route groups correctly scope middleware to the intended routes
- Verify RBAC/permission middleware runs after authentication (identity must be established first)

### Session Management

Key checks:
- Session tokens must be cryptographically random (`crypto/rand`, not `math/rand`)
- Set `HttpOnly`, `Secure`, `SameSite` attributes on session cookies
- Implement session expiry and rotation after privilege escalation (login)
- Invalidate sessions server-side on logout (don't just delete the cookie)

## SSRF (Server-Side Request Forgery)

```go
// BAD: user-controlled URL fetched without validation
func ProxyHandler(w http.ResponseWriter, r *http.Request) {
    targetURL := r.URL.Query().Get("url")
    resp, err := http.Get(targetURL) // can reach internal services, metadata endpoints
    if err != nil {
        http.Error(w, err.Error(), http.StatusBadGateway)
        return
    }
    defer resp.Body.Close()
    io.Copy(w, resp.Body)
}

// GOOD: allowlist + block private IP ranges
func ProxyHandler(w http.ResponseWriter, r *http.Request) {
    targetURL := r.URL.Query().Get("url")
    parsed, err := url.Parse(targetURL)
    if err != nil || !isAllowedHost(parsed) {
        http.Error(w, "forbidden target", http.StatusForbidden)
        return
    }
    client := &http.Client{
        Transport: &http.Transport{
            DialContext: safeDialContext, // blocks 127.0.0.0/8, 10.0.0.0/8, 169.254.169.254, etc.
        },
        Timeout: 10 * time.Second,
    }
    resp, err := client.Get(targetURL)
    if err != nil {
        http.Error(w, "upstream error", http.StatusBadGateway)
        return
    }
    defer resp.Body.Close()
    io.Copy(w, io.LimitReader(resp.Body, 1<<20)) // 1 MB cap
}

func isAllowedHost(u *url.URL) bool {
    allowed := map[string]bool{"api.example.com": true, "cdn.example.com": true}
    return u.Scheme == "https" && allowed[u.Hostname()]
}

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
            return nil, fmt.Errorf("blocked private IP: %s", ip.IP)
        }
    }
    return (&net.Dialer{Timeout: 5 * time.Second}).DialContext(ctx, network, addr)
}
```

Key checks:
- Any endpoint that fetches user-supplied URLs is an SSRF vector
- Block private/loopback/link-local IPs at the dialer level (DNS rebinding defense)
- Block cloud metadata endpoints (`169.254.169.254`)
- Use an allowlist of permitted hosts when possible
- Set response body size limits (`io.LimitReader`)
- Set timeouts on the outbound HTTP client

## XSS (Cross-Site Scripting)

```go
// BAD: raw user input in HTML response
func handler(w http.ResponseWriter, r *http.Request) {
    name := r.URL.Query().Get("name")
    fmt.Fprintf(w, "<h1>Hello, %s</h1>", name) // reflected XSS
}

// GOOD: use html/template (auto-escapes by default)
var tmpl = template.Must(template.New("").Parse(`<h1>Hello, {{.Name}}</h1>`))
func handler(w http.ResponseWriter, r *http.Request) {
    name := r.URL.Query().Get("name")
    w.Header().Set("Content-Type", "text/html; charset=utf-8")
    tmpl.Execute(w, map[string]string{"Name": name})
}

// BAD: text/template used for HTML (no auto-escaping)
import "text/template"
var tmpl = template.Must(template.New("").Parse(`<h1>Hello, {{.Name}}</h1>`))

// BAD: template.HTML() bypasses escaping on user input
data := template.HTML(userInput) // defeats the purpose of auto-escaping
```

Key checks:
- Always use `html/template` for HTML output, never `text/template` or `fmt.Fprintf`
- Never cast user input to `template.HTML`, `template.JS`, or `template.CSS`
- Set `Content-Type: text/html; charset=utf-8` explicitly (prevents MIME-sniffing attacks)
- For JSON API responses, set `Content-Type: application/json` — prevents browsers from interpreting response as HTML
- Sanitize user-generated HTML/Markdown with a dedicated library (e.g. `bluemonday`) before storage

## Rate Limiting & Abuse Prevention

```go
// BAD: no rate limiting on authentication endpoint
r.Post("/api/login", loginHandler) // brute-force friendly

// GOOD: rate limit middleware on sensitive endpoints
import "golang.org/x/time/rate"

func RateLimitMiddleware(rps float64, burst int) func(http.Handler) http.Handler {
    limiter := rate.NewLimiter(rate.Limit(rps), burst)
    return func(next http.Handler) http.Handler {
        return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
            if !limiter.Allow() {
                http.Error(w, "too many requests", http.StatusTooManyRequests)
                return
            }
            next.ServeHTTP(w, r)
        })
    }
}

// per-IP rate limiting for production use
type IPRateLimiter struct {
    mu       sync.Mutex
    limiters map[string]*rate.Limiter
    rps      rate.Limit
    burst    int
}

func (rl *IPRateLimiter) GetLimiter(ip string) *rate.Limiter {
    rl.mu.Lock()
    defer rl.mu.Unlock()
    if l, exists := rl.limiters[ip]; exists {
        return l
    }
    l := rate.NewLimiter(rl.rps, rl.burst)
    rl.limiters[ip] = l
    return l
}
```

Key checks:
- Authentication endpoints (login, password reset, OTP verify) **must** have rate limiting
- Use per-IP or per-user limiting, not just global
- Return `429 Too Many Requests` with `Retry-After` header
- Consider using `golang.org/x/time/rate` (standard extended library) or middleware-level solutions
- Watch for limiter map memory leaks — implement periodic cleanup or use an LRU eviction policy
- For distributed systems, consider Redis-based rate limiting (token bucket or sliding window)

## CORS Misconfiguration

```go
// BAD: wildcard origin with credentials
w.Header().Set("Access-Control-Allow-Origin", "*")
w.Header().Set("Access-Control-Allow-Credentials", "true") // browsers ignore this combo, but intent is dangerous

// BAD: reflect any origin as allowed
origin := r.Header.Get("Origin")
w.Header().Set("Access-Control-Allow-Origin", origin) // allows any site to make credentialed requests

// GOOD: explicit allowlist
var allowedOrigins = map[string]bool{
    "https://app.example.com":    true,
    "https://admin.example.com":  true,
}

func CORSMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        origin := r.Header.Get("Origin")
        if allowedOrigins[origin] {
            w.Header().Set("Access-Control-Allow-Origin", origin)
            w.Header().Set("Access-Control-Allow-Credentials", "true")
            w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
            w.Header().Set("Access-Control-Allow-Headers", "Authorization, Content-Type")
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
- Never reflect arbitrary `Origin` header back as `Access-Control-Allow-Origin`
- `Access-Control-Allow-Origin: *` with `Access-Control-Allow-Credentials: true` is always wrong
- Use a strict allowlist of origins; validate against the list on each request
- Set `Access-Control-Max-Age` to reduce preflight frequency
- Review `Access-Control-Allow-Methods` — expose only the methods actually needed
- For APIs with no browser access needed, omit CORS headers entirely

## HTTP Security Headers

```go
func SecurityHeadersMiddleware(next http.Handler) http.Handler {
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

| Header | Purpose | Finding if missing |
|--------|---------|-------------------|
| `X-Content-Type-Options: nosniff` | Prevents MIME-type sniffing | Medium |
| `X-Frame-Options: DENY` | Prevents clickjacking | Medium |
| `Strict-Transport-Security` | Forces HTTPS | High (if serving over HTTPS) |
| `Content-Security-Policy` | Mitigates XSS, data injection | Medium |
| `Referrer-Policy` | Controls referrer leakage | Low |
| `Permissions-Policy` | Restricts browser features | Low |

Key checks:
- Security headers should be set in a shared middleware, not per-handler
- `Strict-Transport-Security` must only be set when the service is behind TLS (not for localhost/dev)
- `Content-Security-Policy` should be as strict as feasible — avoid `unsafe-inline` and `unsafe-eval`

## Timing Attacks & Constant-Time Comparison

```go
// BAD: early-exit string comparison leaks token length/content via timing
func validateToken(provided, expected string) bool {
    return provided == expected // timing side-channel
}

// GOOD: constant-time comparison
import "crypto/subtle"

func validateToken(provided, expected string) bool {
    return subtle.ConstantTimeCompare([]byte(provided), []byte(expected)) == 1
}
```

Key checks:
- Use `crypto/subtle.ConstantTimeCompare` for secrets, tokens, API keys, HMAC digests
- `==` comparison on secrets is a finding when the value is user-supplied and security-sensitive
- Also applies to password reset tokens, webhook signatures, CSRF tokens
- `bcrypt.CompareHashAndPassword` is already constant-time — no extra action needed for bcrypt

## Input Validation & Deserialization Safety

### Request Body Size Limits

```go
// BAD: unbounded request body
var payload MyStruct
json.NewDecoder(r.Body).Decode(&payload)

// GOOD: enforce size limit
r.Body = http.MaxBytesReader(w, r.Body, 1<<20) // 1 MB
var payload MyStruct
if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
    http.Error(w, "request too large or invalid", http.StatusBadRequest)
    return
}
```

### Recursive/Nested Structures

```go
// BAD: deeply nested JSON can cause stack overflow or excessive memory
type Node struct {
    Value    string  `json:"value"`
    Children []*Node `json:"children"` // no depth limit
}

// GOOD: validate depth after unmarshaling, or use streaming decoder with depth counter
func validateDepth(n *Node, maxDepth int) error {
    if maxDepth <= 0 {
        return fmt.Errorf("max nesting depth exceeded")
    }
    for _, child := range n.Children {
        if err := validateDepth(child, maxDepth-1); err != nil {
            return err
        }
    }
    return nil
}
```

### Integer Overflow in Untrusted Input

```go
// BAD: user-supplied count directly used for allocation
count, _ := strconv.Atoi(r.URL.Query().Get("count"))
items := make([]Item, count) // negative or huge value → panic or OOM

// GOOD: validate range
count, err := strconv.Atoi(r.URL.Query().Get("count"))
if err != nil || count < 0 || count > 10000 {
    http.Error(w, "invalid count", http.StatusBadRequest)
    return
}
items := make([]Item, 0, count)
```

Key checks:
- Always use `http.MaxBytesReader` before decoding request bodies
- Validate integer inputs from query params, headers, and JSON fields before using them for allocation or indexing
- Set depth/recursion limits on tree-like structures from untrusted input
- For XML, disable external entity expansion (XXE) — Go's `encoding/xml` is safe by default, but third-party XML parsers may not be

---

## CSRF Protection

### Missing CSRF Validation on State-Changing Endpoint

```go
// BAD: POST handler that mutates state with no CSRF token check.
// An attacker page can submit a form to this endpoint using the victim's cookies.
func transferHandler(w http.ResponseWriter, r *http.Request) {
    if r.Method != http.MethodPost {
        http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
        return
    }
    to := r.FormValue("to")
    amount := r.FormValue("amount")
    // ... executes transfer with no origin or token verification
    _ = executeTransfer(r.Context(), to, amount)
    fmt.Fprintln(w, "transfer complete")
}
```

### Double-Submit Cookie CSRF Middleware

```go
// GOOD: double-submit cookie pattern.
// On GET: generate a random token, set it as a cookie AND embed it in the
// response (HTML form hidden field or response header for SPA).
// On POST/PUT/DELETE: compare cookie value with the token submitted in the
// request header or form field.

import (
    "crypto/rand"
    "encoding/hex"
    "net/http"
)

const csrfCookieName = "_csrf"
const csrfHeaderName = "X-CSRF-Token"

func generateToken() (string, error) {
    b := make([]byte, 32)
    if _, err := rand.Read(b); err != nil {
        return "", err
    }
    return hex.EncodeToString(b), nil
}

func CSRFMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        switch r.Method {
        case http.MethodGet, http.MethodHead, http.MethodOptions:
            // Safe methods: issue a fresh token cookie if absent.
            if _, err := r.Cookie(csrfCookieName); err != nil {
                tok, err := generateToken()
                if err != nil {
                    http.Error(w, "internal error", http.StatusInternalServerError)
                    return
                }
                http.SetCookie(w, &http.Cookie{
                    Name:     csrfCookieName,
                    Value:    tok,
                    Path:     "/",
                    HttpOnly: false, // JS must read it to send in header
                    Secure:   true,
                    SameSite: http.SameSiteStrictMode,
                })
            }
            next.ServeHTTP(w, r)

        default:
            // State-changing methods: validate token.
            cookie, err := r.Cookie(csrfCookieName)
            if err != nil {
                http.Error(w, "missing CSRF cookie", http.StatusForbidden)
                return
            }
            headerTok := r.Header.Get(csrfHeaderName)
            if headerTok == "" {
                headerTok = r.FormValue("csrf_token")
            }
            if headerTok == "" || subtle.ConstantTimeCompare([]byte(headerTok), []byte(cookie.Value)) != 1 {
                http.Error(w, "CSRF token mismatch", http.StatusForbidden)
                return
            }
            next.ServeHTTP(w, r)
        }
    })
}
```

Key checks:
- Any state-changing endpoint (POST/PUT/DELETE) serving browser clients must validate a CSRF token
- Use `crypto/rand` for token generation — never `math/rand`
- Set `SameSite=Strict` (or at minimum `Lax`) on the CSRF cookie
- For SPAs, expose the token via a cookie readable by JS (`HttpOnly: false`) and require it back in a custom header (`X-CSRF-Token`) — browsers enforce that custom headers cannot be sent cross-origin without CORS preflight
- The synchronizer token pattern (server-side session store) is equally valid but requires session infrastructure

---

## File Upload Security

### Unvalidated File Upload

```go
// BAD: no size limit, trusts Content-Type header, uses client filename as-is.
func uploadHandler(w http.ResponseWriter, r *http.Request) {
    file, header, _ := r.FormFile("document")
    defer file.Close()

    // Trusts client-supplied Content-Type — trivially spoofed.
    contentType := header.Header.Get("Content-Type")
    _ = contentType

    // Uses client filename directly — may contain path traversal (../../etc/passwd).
    dst, _ := os.Create(filepath.Join("/uploads", header.Filename))
    defer dst.Close()
    io.Copy(dst, file) // no size limit — OOM or disk exhaustion
}
```

### Hardened File Upload

```go
// GOOD: enforce size limit, detect real content type, sanitize filename.
import (
    "fmt"
    "io"
    "net/http"
    "os"
    "path/filepath"
    "strings"
)

const maxUploadSize = 10 << 20 // 10 MB

var allowedMIME = map[string]bool{
    "image/jpeg":      true,
    "image/png":       true,
    "application/pdf": true,
}

func secureUploadHandler(w http.ResponseWriter, r *http.Request) {
    // 1. Enforce request body size at the reader level.
    r.Body = http.MaxBytesReader(w, r.Body, maxUploadSize)

    if err := r.ParseMultipartForm(maxUploadSize); err != nil {
        http.Error(w, "file too large", http.StatusRequestEntityTooLarge)
        return
    }

    file, header, err := r.FormFile("document")
    if err != nil {
        http.Error(w, "invalid file", http.StatusBadRequest)
        return
    }
    defer file.Close()

    // 2. Detect real content type by reading magic bytes — do NOT trust the
    //    Content-Type header supplied by the client.
    buf := make([]byte, 512)
    n, err := file.Read(buf)
    if err != nil && err != io.EOF {
        http.Error(w, "read error", http.StatusInternalServerError)
        return
    }
    detectedType := http.DetectContentType(buf[:n])
    if !allowedMIME[detectedType] {
        http.Error(w, fmt.Sprintf("file type %s not allowed", detectedType), http.StatusUnsupportedMediaType)
        return
    }
    // Seek back so the full file is written to disk.
    if seeker, ok := file.(io.Seeker); ok {
        seeker.Seek(0, io.SeekStart)
    }

    // 3. Sanitize filename: strip directory components and reject suspicious names.
    safeName := filepath.Base(header.Filename)
    safeName = strings.ReplaceAll(safeName, "..", "")
    if safeName == "" || safeName == "." || safeName == "/" {
        http.Error(w, "invalid filename", http.StatusBadRequest)
        return
    }

    dstPath := filepath.Join("/uploads", safeName)
    // Verify the resolved path is still under the upload root.
    if !strings.HasPrefix(filepath.Clean(dstPath), "/uploads/") {
        http.Error(w, "invalid path", http.StatusBadRequest)
        return
    }

    dst, err := os.Create(dstPath)
    if err != nil {
        http.Error(w, "storage error", http.StatusInternalServerError)
        return
    }
    defer dst.Close()

    if _, err := io.Copy(dst, file); err != nil {
        http.Error(w, "write error", http.StatusInternalServerError)
        return
    }
    w.WriteHeader(http.StatusCreated)
}
```

Key checks:
- Always use `http.MaxBytesReader` to cap upload size — never rely on `Content-Length` alone
- Detect content type with `http.DetectContentType` (magic bytes) — the client-supplied `Content-Type` header is trivially spoofed
- Maintain an allowlist of permitted MIME types; reject everything else
- Sanitize filenames with `filepath.Base` and reject names containing `..`
- After path construction, verify the resolved absolute path is still under the intended upload directory to prevent path traversal

---

## Open Redirect Prevention

### User-Controlled Redirect URL

```go
// BAD: redirects to whatever the client supplies — attacker can craft
// a link like /login?next=https://evil.com/phish and victims land on
// the attacker's site after authenticating.
func loginCallbackHandler(w http.ResponseWriter, r *http.Request) {
    // ... authentication logic ...
    next := r.URL.Query().Get("next")
    http.Redirect(w, r, next, http.StatusFound)
}
```

### Validated Redirect

```go
// GOOD: only allow relative paths or an explicit set of trusted hosts.
import (
    "net/http"
    "net/url"
    "strings"
)

var trustedHosts = map[string]bool{
    "example.com":     true,
    "app.example.com": true,
}

func safeRedirect(w http.ResponseWriter, r *http.Request, fallback string) {
    target := r.URL.Query().Get("next")
    if target == "" {
        http.Redirect(w, r, fallback, http.StatusFound)
        return
    }

    parsed, err := url.Parse(target)
    if err != nil {
        http.Redirect(w, r, fallback, http.StatusFound)
        return
    }

    // Allow relative paths (no scheme, no host).
    if parsed.Host == "" && parsed.Scheme == "" && strings.HasPrefix(parsed.Path, "/") {
        http.Redirect(w, r, parsed.Path, http.StatusFound)
        return
    }

    // Absolute URL: must be in the trusted host list.
    if trustedHosts[parsed.Hostname()] && (parsed.Scheme == "https" || parsed.Scheme == "http") {
        http.Redirect(w, r, target, http.StatusFound)
        return
    }

    // Reject everything else.
    http.Redirect(w, r, fallback, http.StatusFound)
}

func loginCallbackHandler(w http.ResponseWriter, r *http.Request) {
    // ... authentication logic ...
    safeRedirect(w, r, "/dashboard")
}
```

Key checks:
- Never pass a user-controlled value directly to `http.Redirect`
- Parse with `url.Parse` and inspect `Scheme` and `Host` — a bare path like `/dashboard` is safe; anything with a host must be on an allowlist
- Reject protocol-relative URLs (`//evil.com`) — they have an empty scheme but a non-empty host after parsing
- Beware of backslash tricks (`/\evil.com`) on some platforms — normalize the URL before validation
- Default to a safe fallback (`/` or `/dashboard`) when the redirect target fails validation

---

## See Also

- `go-api-http-checklist.md` — middleware ordering, request validation
- `go-concurrency-patterns.md` — rate limiter concurrency
- `go-database-patterns.md` — SQL injection context