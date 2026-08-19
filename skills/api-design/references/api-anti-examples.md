# Extended API Design Anti-Examples

Supplementary to the inline anti-examples in §7 of the SKILL.md.
Each entry carries the nature tag from §2.1 of the SKILL.md. Nature bounds *what* is reportable; severity comes from §8.1 and depends on the live risk triggers.

---

## AE-7 [D]: Inconsistent field naming across endpoints

```json
// GET /users/123
{"userId": "123", "firstName": "Alice"}

// GET /orders/456
{"order_id": "456", "first_name": "Alice"}
```

**Problem**: mixing camelCase and snake_case across endpoints. Clients must
handle both conventions, increasing integration complexity and bug surface.

**Right**: choose ONE convention for the entire API family and enforce it.
Either convention is acceptable — the defect is the mixture, not the choice.

---

## AE-8 [D]: Offset pagination on a high-churn dataset

```
GET /api/v1/notifications?page=500&limit=20
```

**Problem**: at page 500 the database skips 10,000 rows (O(n)). If new
notifications are inserted between page requests, items are duplicated or
skipped. On a dataset with 10M+ rows and frequent inserts, this is
both slow and inconsistent.

**Right**: cursor-based pagination for high-churn data:
```
GET /api/v1/notifications?cursor=eyJpZCI6MTIzfQ&limit=20
```

Offset pagination remains correct for small, stable, or page-numbered admin views.

---

## AE-9 [P]: Leaking internal implementation in errors

```json
HTTP 500
{
  "error": "pq: duplicate key value violates unique constraint \"users_email_key\""
}
```

**Problem**: exposes database type (PostgreSQL), table name, constraint name.
Attackers learn the schema; clients can't programmatically handle the error.

**Right**:
```json
HTTP 409
{"error": {"code": "conflict", "message": "A user with this email already exists"}}
```

---

## AE-10 [P]: Undocumented and inconsistent DELETE success shape

<!-- api-lint: delete-200-legal -->

```
DELETE /api/v1/users/123      → 204 No Content
DELETE /api/v1/orders/456     → 200 OK {"message": "Order deleted successfully"}
DELETE /api/v1/sessions/789   → 200 OK {}
// Three shapes across one API; the spec documents none of them.
```

**The defect is the inconsistency and the missing spec — not the 200 itself.**
RFC 9110 §9.3.5 states that a successfully applied DELETE SHOULD send **202
Accepted** (will likely succeed, not yet enacted), **204 No Content** (enacted,
no further information to supply), or **200 OK** (enacted, and the response
includes a representation describing the status). All three are conformant.
A reviewer who reports `200 OK` on a DELETE as a protocol violation is raising a
false positive.

`{"message": "Order deleted successfully"}` is a genuine but *separate* problem:
a prose-only body gives the client nothing machine-readable, so it should either
carry the deleted representation (for undo UI) or be dropped in favour of 204.

**Right**: pick one shape per resource class and document it.

```
204 No Content            → nothing useful to return (the common default)
200 OK + representation   → client needs the deleted object, e.g. for undo
202 Accepted + status URL  → deletion is asynchronous
```

Two further facts from RFC 9110 §9.3.5 worth putting in the contract: responses
to DELETE are **not cacheable**, and a successful DELETE **invalidates** any
stored responses a cache holds for that URI. Clients should not send a request
body on DELETE — it has no defined semantics and some servers reject it.

---

## AE-11 [P]: PUT used for partial updates

```
PUT /api/v1/users/123
{"name": "Bob"}
// Only name sent — but PUT semantics mean "replace entire resource"
// Server interprets as: email=null, address=null, phone=null
```

**Problem**: PUT means full replacement. Sending partial fields with PUT
either silently nulls missing fields or requires the server to merge
(violating PUT semantics).

**Right**: use PATCH for partial updates, PUT only for full replacement.

---

## AE-12 [D]: No Content-Type negotiation

```
POST /api/v1/users
// No Content-Type header
// Server guesses: is this JSON? Form data? XML?
```

**Problem**: without Content-Type, the server guesses the format. Different
frameworks guess differently. Form-encoded data parsed as JSON → cryptic errors.

**Right**: require `Content-Type: application/json` for all JSON endpoints.
Return 415 Unsupported Media Type for unrecognized content types.

---

## AE-13 [C]: Choosing the denial status code without a threat model

<!-- api-lint: denial-403-permitted -->

```
GET /api/v1/users/456  (caller is user 123)
→ 403 Forbidden        ← leaks that user 456 exists
→ 404 Not Found        ← leaks nothing
```

**This is a policy choice, not a defect.** The OWASP Authorization Regression
Testing Cheat Sheet requires that an unauthorized request return "a 403
Forbidden **or** 404 Not Found (to avoid information leakage about resource
existence), never a 200 OK". Both codes are sanctioned; only 200 is forbidden.

Decide by whether *existence* is confidential:

| Situation | Code | Why |
|-----------|:----:|-----|
| Enumerable IDs, cross-tenant objects, per-user records in a shared ID space | **404** | Existence is itself the secret |
| Known shared resource, caller simply lacks a role (admin console, internal API) | **403** | Existence is not secret; a clear denial saves the caller a debugging session |
| Any unauthorized request | never **200** | Breaks every client's error handling |

**The real defect is inconsistency.** If one endpoint answers 403 and another
answers 404 for the same resource class, the difference between them *is* the
enumeration oracle you were trying to close. Whichever you pick, apply it per
resource class, and log both cases identically server-side.

---

## AE-14 [P]: Classifying a JSON field reorder as a breaking change

<!-- api-lint: field-reorder-not-breaking -->

```go
// Before                          // After (fieldalignment / manual tidy)
type UserResp struct {             type UserResp struct {
    Name  string `json:"name"`         ID    string `json:"id"`
    ID    string `json:"id"`           Name  string `json:"name"`
}                                  }
```

**Problem with the *report*, not the code**: a reviewer flags this as a breaking
API change on the grounds that the JSON output changed. RFC 8259 §1 defines a
JSON object as "an unordered collection of zero or more name/value pairs" — key
order carries no meaning, so every spec-conformant consumer is unaffected.
Reporting this as breaking by default produces noise on routine refactors.

What *is* true: `encoding/json` (and `sonic`) serialize struct fields in
declaration order, so the byte sequence changes. That matters in exactly two
situations, and each must be evidenced before you report it:

| Situation | Evidence required | Then it is |
|-----------|-------------------|-----------|
| A specific consumer parses by field position or string-prefix match | Name the consumer and the parsing code | Breaking **for that consumer** — record as its non-conformance |
| The raw body feeds a byte-exact artifact — HMAC/signature, content-addressed cache key, `ETag` computed over the body, golden-file test | Point at the signing/hashing code | Breaking — the digest changes |

Absent both, the correct classification is **non-breaking**. Do not generalize a
single non-conformant consumer into a property of JSON.

**Right** report: "`UserResp` field order changed. Non-breaking under RFC 8259.
Verify consumer `legacy-billing-gateway`, which prefix-matches the response
body, before deploying — that consumer is non-conformant and needs a fix."
