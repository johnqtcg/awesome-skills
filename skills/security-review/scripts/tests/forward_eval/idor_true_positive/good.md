```
Active verification: NOT permitted
Target: none
Basis: no authorized target was provided; static source review only
```

Review depth: Standard (single handler, but an auth/authz path is touched).

## 1) Findings

> **SEC-001: IDOR — any authenticated caller can read any order**
>
> - **Severity**: P1 High
> - **Confidence**: confirmed — the vulnerable path is complete and visible in the handler
> - **Mapping**: CWE-639 (Authorization Bypass Through User-Controlled Key) / ASVS 4.0.3 V4.1.2
> - **File/line**: `GetOrder` handler, `orderID := chi.URLParam(r, "id")`
> - **Exploit path**: `orderID` comes straight from the URL and is passed to
>   `repo.GetOrder(ctx, orderID)` with no comparison against the caller's identity. Any
>   authenticated user can enumerate order IDs and read other users' records. Authentication is
>   present; **authorization is absent** — the classic object-level authorization failure.
> - **Impact**: horizontal privilege escalation across the whole order table (PII, amounts, addresses).
> - **Reproducer** (NOT executed — active verification not permitted; confirmed statically):
>   ```bash
>   # Local instance only. User A's token requesting User B's order.
>   curl -H "Authorization: Bearer <tokenA>" http://127.0.0.1:8080/api/orders/ORDER-9999
>   # Expected on the vulnerable build: 200 with User B's order
>   ```
>   Two IDs demonstrate the class; do not enumerate further.
> - **Recommended fix**: load the order, then compare ownership before serialising, and return
>   404 rather than 403 so existence is not confirmed:
>   ```go
>   order, err := repo.GetOrder(r.Context(), orderID)
>   if err != nil || order.UserID != auth.UserIDFrom(r.Context()) {
>       http.Error(w, "not found", http.StatusNotFound)
>       return
>   }
>   ```
> - **Regression test**: `TestGetOrder_CrossUser_Returns404` — create as User A, request as User B.
> - **Baseline status**: new
> - **Origin**: introduced

## 2) Security Domain Coverage — stack: go

Domains 1-10 evaluated. Relevant: Domain 3 (Sensitive Data Handling) — the handler serialises
the full order struct, so the IDOR leaks every field. Domains 1, 5, 6, 7, 8, 9, 10 `N/A` for this
handler (no randomness, TLS, crypto, concurrency, stack-specific sink, scanner, or dependency
change in scope). Domain 2 `Applicable`/PASS — the repo call is parameterised. Domain 4 `N/A`.

## 3) Automation Evidence

None executed — static review only, and no authorization for active verification.

## 4) Open questions / assumptions

- Assumes `auth` middleware populates an identity in the request context; if it does not, the
  severity rises because the endpoint is effectively unauthenticated.

## 5) Risk Acceptance Register

No accepted risks. SEC-001 is `introduced` and must be fixed before merge.

## 6) Remediation Plan

- **Immediate**: add the ownership check above; ship with the regression test.
- **Short-term**: audit sibling handlers for the same pattern.

## 9) Uncovered Risk List

- Other handlers in the same package were not in scope; the same missing-ownership pattern may
  repeat. Recommend grepping every `URLParam`/`Query().Get` that feeds a repo lookup.

```json
{
  "summary": { "pass": false, "baseline": "absent" },
  "counts": { "p0": 0, "p1": 1, "p2": 0, "p3": 0, "overflow": 0 },
  "stack": "go",
  "asvs_version": "4.0.3",
  "active_verification": "not_permitted",
  "security_domains": { "required": true, "total": 10, "pass": 1, "fail": 1, "na": 8 },
  "findings": [
    {
      "id": "SEC-001", "severity": "P1", "confidence": "confirmed", "status": "new",
      "origin": "introduced", "cwe": "CWE-639", "asvs": "ASVS 4.0.3 V4.1.2",
      "file": "handler/order.go:GetOrder"
    }
  ]
}
```
