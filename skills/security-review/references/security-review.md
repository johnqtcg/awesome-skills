# Security Review Reference

## Quick Threat Prompts

- Can an unauthenticated caller reach this path?
- Can a low-privilege user access another tenant/user resource?
- Can untrusted input reach SQL/shell/template/file/network sinks unsafely?
- Can user-controlled URL/host/protocol trigger SSRF?
- Can secrets/PII appear in logs/traces/metrics/errors?
- Can payment/state transitions be replayed, raced, or partially committed?
- Can JWT/session/cookie logic be bypassed or weakened?
- Can redirect/callback endpoints be abused?

## Go 10-Domain Quick Matrix

Use this matrix for Go repos and mark each `PASS/FAIL/N/A` with one-line evidence.

Execution order:

1. Triage applicability for each domain (`Applicable` or `N/A` with reason).
2. Deep-check only `Applicable` domains.
3. Keep `N/A` evidence explicit to avoid false completeness.

1. Randomness safety: `crypto/rand` used for tokens/keys/nonces; no `math/rand` in secret paths.
2. SQL injection + lifecycle: parameterized SQL, identifier allowlists, `rows.Close`, `rows.Err`, `stmt.Close`, `Commit/Rollback` pairing.
3. Sensitive data handling: redacted logs, no internal-error leakage, minimal response exposure.
4. Secret/config management: no hardcoded secrets, env fail-fast, secret masking, justified `nolint:gosec`.
5. TLS safety: `MinVersion >= TLS1.2`, no unsafe `InsecureSkipVerify`, mTLS where required.
6. Crypto primitive correctness: bcrypt/argon2id for password storage, no MD5/SHA1, constant-time comparison for MAC/signature.
7. Concurrency safety: `go test -race` clean, no TOCTOU in auth/balance, no unsynchronized shared state.
8. Go injection sinks: `html/template` not `text/template`, `exec.Command` arg separation, `filepath.Join` traversal check.
9. Static scanner posture: `gosec` findings triaged with exploitability evidence.
10. Dependency vulnerability posture: `govulncheck` source-mode reachability and remediation path.

## Minimal Negative Test Matrix

- Auth missing -> `401`
- Insufficient role -> `403`
- Cross-tenant resource ID -> forbidden/not found
- Invalid payload type/range/size -> `400`
- Injection-like payload -> rejected
- Path traversal payload -> rejected
- JWT invalid issuer/audience/expiry -> rejected
- CSRF missing/invalid token -> rejected
- Third-party timeout/failure -> safe fallback/error path
- Duplicate idempotency key -> no duplicate side effect

## Evidence Levels

- `confirmed`: proven exploitable path
- `likely`: strong evidence, one assumption remaining
- `suspected`: needs more data

## Suppression Guidance

Suppress only when one of these is proven:

1. Upstream guard/middleware blocks the path.
2. Input is not attacker-controlled at boundary.
3. Sink is safely parameterized/encoded by framework guarantees.

Suppressed items go to assumptions, not findings.

## Baseline Diff Labels

- `new`
- `regressed`
- `unchanged`
- `resolved`

## Risk Acceptance Entry Template

- Finding ID:
- Reason:
- Compensating controls:
- Owner:
- Expiry/review date:

## SLA Defaults

- P0: immediate mitigation, full fix <= 24h
- P1: <= 3 business days
- P2: <= 14 calendar days
- P3: backlog milestone

## Standard Mapping Hints

- Authz/IDOR -> CWE-639, OWASP ASVS V4
- Injection -> CWE-89/CWE-78/CWE-94, OWASP ASVS V5
- Sensitive data exposure -> CWE-200, OWASP ASVS V8/V9
- SSRF -> CWE-918, OWASP ASVS V5
- Hardcoded secrets -> CWE-798, OWASP ASVS V6
- Weak randomness -> CWE-330, OWASP ASVS V7
- Weak TLS config -> CWE-295/CWE-327, OWASP ASVS V9
- Weak crypto/hash usage -> CWE-327/CWE-328, OWASP ASVS V6

## Tooling Quick Commands

```bash
rg -n "(AKIA[0-9A-Z]{16}|-----BEGIN (RSA|EC|OPENSSH|PRIVATE) KEY-----|ghp_[A-Za-z0-9]{36}|xox[baprs]-|password\s*=|secret\s*=|token\s*=)" .
gosec ./...
govulncheck ./...
govulncheck -mode=binary ./...
```

## Tool Interpretation Notes

- `gosec` is coding-pattern-oriented and may require reachability/exploitability triage.
- `govulncheck` source mode is reachability-aware and should drive confidence.
- `govulncheck -mode=binary` is exposure-oriented and can over-report; do not mark `confirmed` from this alone.

If tools are unavailable, report explicitly and continue with manual evidence.
