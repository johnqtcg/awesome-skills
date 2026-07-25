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

> **These are ASVS 4.0.3 chapter numbers.** ASVS 5.0.0 reorganised and renumbered its
> chapters, so these values are **not** valid 5.0.0 identifiers. Pick one version per report
> and say which:
>
> - Targeting **4.0.3** → use this table, and write IDs as `ASVS 4.0.3 V4.1.2`.
> - Targeting **5.0.0** → resolve the requirement in the 5.0.0 document itself and write
>   `ASVS 5.0.0 V<n>.<n>.<n>`. Do **not** translate the numbers below by guessing; a plausible
>   but wrong requirement ID is worse than `Mapping: TBD`.
>
> Chapter-level precision is acceptable (`ASVS 4.0.3 V5 (chapter-level)`) when the exact
> requirement is unclear — state the imprecision rather than implying precision you lack.

| Finding Category | CWE | ASVS 4.0.3 chapter |
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

---

## One-Shot Finding Example

The finding format from `SKILL.md §1) Findings`, fully populated. Note the reproducer is
labelled as **not executed** and targets loopback only — see
`authorization-and-policy.md` §1.

> **SEC-001: IDOR — Any authenticated user can access other users' orders**
>
> - **Severity**: P1 High
> - **Confidence**: confirmed
> - **Mapping**: CWE-639 (Authorization Bypass Through User-Controlled Key) / ASVS 4.0.3 V4.1.2
> - **File/line**: `internal/handler/order.go:47`
> - **Exploit path**: `GET /api/orders/:id` extracts `id` from the URL path and passes it
>   directly to `repo.GetOrder(id)` without verifying `order.UserID == ctx.UserID()`. Any
>   authenticated user can read any order by iterating IDs.
> - **Impact**: Full horizontal privilege escalation on order data (PII, payment amounts, addresses).
> - **Reproducer** (NOT executed — no authorization to test a live target; confirmed from the
>   code path alone):
>   ```bash
>   # Run against a local instance only. User A's token, requesting User B's order.
>   curl -H "Authorization: Bearer <tokenA>" http://127.0.0.1:8080/api/orders/ORDER-9999
>   # Expected on the vulnerable build: 200 with User B's order details
>   ```
>   Two IDs are enough to demonstrate the class — do not enumerate further.
> - **Recommended fix**:
>   ```go
>   order, err := h.repo.GetOrder(ctx, orderID)
>   if err != nil { ... }
>   if order.UserID != auth.UserIDFrom(ctx) {
>       return echo.NewHTTPError(http.StatusNotFound, "order not found")
>   }
>   ```
>   Return 404 (not 403) to avoid confirming the order exists.
> - **Regression test**: Add `TestGetOrder_CrossUser_Returns404` — create order as User A,
>   request as User B, assert 404.
> - **Baseline status**: new
> - **Origin**: introduced
