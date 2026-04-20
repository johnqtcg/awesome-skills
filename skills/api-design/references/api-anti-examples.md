# Extended API Design Anti-Examples

Supplementary to the inline anti-examples in §6 of the SKILL.md.

---

## AE-7: Inconsistent field naming across endpoints

```json
// GET /users/123
{"userId": "123", "firstName": "Alice"}

// GET /orders/456
{"order_id": "456", "first_name": "Alice"}
```

**Problem**: mixing camelCase and snake_case across endpoints. Clients must
handle both conventions, increasing integration complexity and bug surface.

**Right**: choose ONE convention for the entire API family and enforce it.

---

## AE-8: Offset pagination on high-churn dataset

```
GET /api/v1/notifications?page=500&limit=20
```

**Problem**: at page 500, the database skips 10,000 rows (O(n)). If new
notifications are inserted between page requests, items are duplicated or
skipped. On a dataset with 10M+ rows and frequent inserts, this is
both slow and inconsistent.

**Right**: cursor-based pagination for high-churn data:
```
GET /api/v1/notifications?cursor=eyJpZCI6MTIzfQ&limit=20
```

---

## AE-9: Leaking internal implementation in errors

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

## AE-10: DELETE returns 200 with body instead of 204

```
DELETE /api/v1/users/123
→ 200 OK {"message": "User deleted successfully"}
```

**Problem**: 200 with body is semantically incorrect for DELETE. Clients
expect 204 No Content for successful deletion. 200 with a body implies
there's meaningful data to parse.

**Right**: `204 No Content` (no response body). Or `200 OK` with the
deleted resource representation if the client needs it for undo UI.

---

## AE-11: PUT used for partial updates

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

## AE-12: No Content-Type negotiation

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

## AE-13: Returning 403 instead of 404 for resources the user doesn't own

```
GET /api/v1/users/456  (caller is user 123)
→ 403 Forbidden
```

**Problem**: 403 reveals that user 456 EXISTS. An attacker can enumerate
valid user IDs by distinguishing 403 (exists, no access) from 404 (doesn't exist).

**Right**: return 404 for resources the caller cannot access. From the
caller's perspective, if they can't see it, it doesn't exist.