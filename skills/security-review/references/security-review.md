# Security Review — Supplementary Review Aids

> **Single source of truth**: all normative rules — severity model, remediation SLA,
> evidence-confidence labels, false-positive suppression rules, baseline diff labels,
> risk-acceptance fields, automation commands, and tool-interpretation rules — are
> defined **only in `SKILL.md`**. Do not restate them here. If a normative rule ever
> appears in this file again, treat `SKILL.md` as authoritative and delete the copy.
>
> This file holds only supplementary aids that are useful during a review but too
> bulky for the main flow: threat prompts, a negative-test matrix, and the CWE/ASVS
> mapping lookup table.

## Quick Threat Prompts

Use these to seed trust-boundary analysis (process step 2) before running scenario checks:

- Can an unauthenticated caller reach this path?
- Can a low-privilege user access another tenant/user resource?
- Can untrusted input reach SQL/shell/template/file/network sinks unsafely?
- Can user-controlled URL/host/protocol trigger SSRF?
- Can secrets/PII appear in logs/traces/metrics/errors?
- Can payment/state transitions be replayed, raced, or partially committed?
- Can JWT/session/cookie logic be bypassed or weakened?
- Can redirect/callback endpoints be abused?

## Minimal Negative Test Matrix

Use when writing the suggested regression/negative test for a finding (Output Contract §1):

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

## CWE / OWASP ASVS Mapping Table

Lookup table for the mandatory Standards Mapping (`SKILL.md § Standards Mapping`).
Section-level ASVS references are sufficient; use `Mapping: TBD` with a reason if unclear.

| Finding Category | CWE | OWASP ASVS |
|------------------|-----|-----------|
| Authz bypass / IDOR | CWE-639 | V4 |
| SQL / command / code injection | CWE-89 / CWE-78 / CWE-94 | V5 |
| XSS | CWE-79 | V5 |
| CSRF | CWE-352 | V4 |
| Path traversal | CWE-22 | V12 |
| SSRF | CWE-918 | V5 |
| Sensitive data exposure | CWE-200 | V8 / V9 |
| Hardcoded secrets | CWE-798 | V6 |
| Weak randomness | CWE-330 | V7 |
| Weak TLS config | CWE-295 / CWE-327 | V9 |
| Weak crypto / hash usage | CWE-327 / CWE-328 | V6 |
| Race condition / TOCTOU | CWE-362 / CWE-367 | V11 |
