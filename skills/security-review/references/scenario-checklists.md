# Security Review — Scenario Checklists

This reference contains the full 11-scenario checklist used in step 3 of the security review process.

For each applicable scenario, verify every item. Mark items as `Pass / Fail / N/A` with one-line evidence.

---

## 1) Authentication / Authorization

- Auth enforced on protected routes.
- Authz checks before sensitive operations.
- No IDOR across tenant/user boundaries.
- Token/session expiry-revocation-rotation handled.
- Privileged operations require explicit permission checks.

## 2) Input Validation / Injection / Uploads

- Explicit schema/rules for external input.
- Whitelist for enum/type/range/length.
- No unsafe SQL/shell/template/path sink usage.
- SQL must be parameterized; `ORDER BY`/identifier inputs must use allowlists.
- Path traversal protections (`..`, absolute path, symlink escape).
- Upload controls (size, MIME/type, extension, storage path).
- Unsafe deserialization patterns absent.

### Go-Specific Injection Sinks

- `text/template` used for user-facing content → must be `html/template` (auto-escapes HTML/JS/CSS).
- `os/exec.Command(name, args...)` — never concatenate user input into `name`; pass user values as separate `args`.
- `os/exec.CommandContext` with unsanitized shell string via `sh -c` → command injection.
- `net/http.Redirect` with user-controlled URL → open redirect; validate against allowlist or restrict to relative paths.
- `filepath.Join(base, userInput)` does NOT prevent `../` traversal → must verify result starts with `base` after `filepath.Clean`.
- `encoding/json.Decoder` without `DisallowUnknownFields` or size limit → resource exhaustion via large payload.
- `json.Unmarshal` / `xml.Decoder` on untrusted input without `xml.Decoder.MaxDepth` (Go 1.24+) → billion-laughs DoS.

## 3) Session / JWT / Cookie / CSRF

- JWT validation checks issuer/audience/expiry/alg constraints.
- Reject `alg=none` and weak parsing paths.
- Cookie flags (`HttpOnly`, `Secure`, `SameSite`) as required.
- CSRF defenses on cookie-auth mutation endpoints.

## 4) New Endpoints and Error Surface

- Endpoint has authn/authz and abuse-control strategy.
- Errors do not leak internals/secrets.
- CORS/method/content-type constraints explicit.
- Redirect/callback endpoints resist open-redirect abuse.
- State-changing endpoints consider idempotency and replay safety.

### Go-Specific Endpoint Checks

- `http.Error` / `fmt.Errorf("%v", err)` with internal error wrapping → may leak stack traces or SQL to client; use opaque error IDs.
- `http.Request.Body` not limited → `http.MaxBytesReader` required to prevent request body DoS.
- `http.TimeoutHandler` or server-level `ReadTimeout`/`WriteTimeout` set → prevents slowloris.
- `context.Background()` in request handler (ignoring request context) → goroutine leak on client disconnect.

## 5) Secrets / Crypto / Key Management

- No hardcoded secrets in source/config samples.
- Secrets loaded from env/secret manager only.
- No secret exposure in logs/errors/metrics/traces.
- Rotation/revocation path exists.
- No deprecated/insecure crypto primitives.
- Password storage uses bcrypt/argon2id, not direct hash.
- MAC/signature comparison uses constant-time operations.

## 6) Payment / Financial Transitions

- Server-side ownership and amount/currency validation.
- Replay protection and idempotency keys.
- Transaction boundaries prevent partial commit.
- Concurrency controls preserve balance consistency.
- Audit logs keep traceability without sensitive payload.

## 7) Sensitive Data Storage / Transmission

- TLS/HTTPS for external transmission.
- Sensitive fields masked/redacted.
- Encryption-at-rest or compensating controls documented.
- API responses avoid over-exposure of PII/financial data.

## 8) Third-Party Integrations

- Timeout/retry/backoff/circuit bounds.
- Signature/response verification when supported.
- SSRF-safe URL handling.
- Fail-safe behavior for security-critical call failures.

## 9) Supply Chain / Dependency / Build Path

- Dependency vulnerability assessment (`govulncheck` or equivalent).
- Security scanning (`gosec` or equivalent).
- Dependency pinning/update hygiene.
- CI security checks for changed risk paths.

## 10) Container / Deployment Security

When Dockerfiles, K8s manifests, Helm charts, or CI pipeline configs are in scope:

### Dockerfile

- Final stage runs as non-root user (`USER nonroot` or numeric UID ≥ 1000).
- Base image pinned to digest or specific version, not `latest`.
- No secrets (env vars, COPY of credential files) baked into image layers.
- Multi-stage build: build tools and source not present in final image.
- `HEALTHCHECK` defined for orchestrator liveness detection.

### Kubernetes / Helm

- `securityContext.runAsNonRoot: true` and `readOnlyRootFilesystem: true` on pods.
- `resources.limits` (CPU + memory) set → prevents noisy-neighbor DoS.
- Secrets mounted as volumes (not env vars when possible) and referenced from `Secret` objects, not hardcoded in manifests.
- `NetworkPolicy` restricts pod-to-pod traffic to necessary paths.
- Service accounts use least-privilege RBAC; default service account not used for workloads.
- No `privileged: true`, `hostNetwork: true`, or `hostPID: true` without explicit justification.

### CI Pipeline

- Secret injection via CI secret store, not plaintext in pipeline config.
- Pipeline does not echo/print secrets in logs.
- Artifact signing or checksum verification for deployed images.

## 11) Concurrency Safety as Security Risk

Race conditions are security vulnerabilities when they affect auth, access control, financial state, or resource limits (CWE-367 TOCTOU, CWE-362 Race Condition).

- TOCTOU in auth/authz: check-then-act on permission/ownership without holding lock or using atomic operation.
- Double-spend / balance race: concurrent requests bypass balance check before deduction commits.
- Concurrent map read/write without sync (Go fatal, not just data corruption — can crash the process = DoS).
- Goroutine writing shared config/state read by request handlers without synchronization.
- Race in session/token refresh: concurrent requests may use stale or revoked tokens.

### Go-Specific Concurrency Checks

- `go test -race` on changed packages (mandatory for Standard/Deep reviews if test suite exists).
- `sync.Mutex` / `sync.RWMutex` scope: lock held across the full check-act span, not just one of them.
- `atomic.Value.Store` / `.Load` type consistency (storing different concrete types = panic).
- `sync.Pool` ownership: using object after `Put` is a use-after-free race.
