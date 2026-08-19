# REST API Error Model Patterns

A consistent error model is the difference between "clients can handle failures
gracefully" and "every team guesses what went wrong from a string message."

Nature tags follow §2.1 of the SKILL.md: **[P]** invariant, **[D]** convention,
**[C]** policy. Severity depends on the live risk triggers and is decided in §8.1.

---

## 1. Error Envelope

Two separate things live here. Keep them apart when reporting.

**The invariants [P]** — these four hold for any format:

1. failures carry a **non-2xx status**;
2. the body carries a **stable machine-identifiable discriminator**;
3. **one shape is used by every endpoint**;
4. nothing sensitive leaks (§6).

**The default shape [D]** — absent an existing house standard, use this:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Request validation failed",
    "details": [
      {"field": "email", "code": "invalid_format", "message": "Must be a valid email address"},
      {"field": "age", "code": "out_of_range", "message": "Must be between 1 and 150"}
    ],
    "trace_id": "req-abc-123"
  }
}
```

### Field semantics

| Field | Type | Required | Purpose |
|-------|------|:--------:|---------|
| `code` | string | Yes | Stable, machine-parseable error classification (snake_case) |
| `message` | string | Yes | Human-readable description, safe for display |
| `details` | array | No | Field-level validation errors or sub-errors |
| `trace_id` | string | Yes | Request correlation ID for debugging |

### Rules

- `code` MUST be stable across releases — clients depend on it for programmatic handling
- `message` MAY change wording — it's for humans, not machines
- Never expose: stack traces, SQL queries, driver messages, internal service names, file paths
- `details[].field` uses dot-notation for nested fields: `address.zip_code`
- These four keys are the whole client-facing contract. Everything else stays server-side — see §6

### RFC 9457 is an equally valid answer

`application/problem+json` (**RFC 9457**) satisfies all four invariants, with `type` as
the discriminator:

```json
{
  "type": "https://example.com/probs/validation",
  "title": "Request validation failed",
  "status": 422,
  "detail": "email must be a valid email address",
  "instance": "/orders/1e4f",
  "errors": [{"field": "email", "code": "invalid_format"}]
}
```

An API that uses RFC 9457 consistently is a **PASS on `C2`** — do not report it as an
envelope violation, and do not ask it to migrate to the shape above. The same holds for a
gRPC service returning `google.rpc.Status`. The only failure mode this rule detects is a
*different shape per endpoint*.

---

## 2. Standard Error Codes [D]

| Code | HTTP Status | When to use |
|------|:-----------:|-------------|
| `invalid_json` | 400 | Request body is not valid JSON |
| `validation_error` | 422 | One or more fields fail validation (use details[]) |
| `missing_field` | 422 | Required field is absent |
| `invalid_format` | 422 | Field present but wrong format (email, UUID, etc.) |
| `unauthorized` | 401 | No valid authentication credentials |
| `forbidden` | 403 | Authenticated, not authorized, and the resource's existence is not confidential |
| `not_found` | 404 | Resource does not exist — or the caller may not know whether it exists (see below) |
| `conflict` | 409 | Resource state conflict (duplicate key, already exists) |
| `precondition_failed` | 412 | ETag / If-Match condition not met |
| `idempotency_conflict` | 409 | Idempotency-Key reused with a different request body |
| `rate_limit_exceeded` | 429 | Too many requests — include Retry-After header |
| `internal_error` | 500 | Unexpected server error — log details, don't expose |
| `service_unavailable` | 503 | Temporary overload or maintenance — include Retry-After |

### Authorization denial: 403 or 404 — [C] policy choice

Both are sanctioned. The OWASP Authorization Regression Testing Cheat Sheet requires a
denied request to return "a 403 Forbidden **or** 404 Not Found (to avoid information
leakage about resource existence), never a 200 OK".

- Use **404** when the resource's existence is itself confidential: enumerable IDs,
  cross-tenant objects, per-user records sharing an ID space.
- Use **403** when existence is not confidential and an honest denial helps the caller:
  a teammate missing a role on a shared resource, admin tooling, internal APIs.
- Be **consistent within a resource class**. A mix of 403 and 404 for the same class is
  itself an existence oracle.
- Whichever you return, log both cases identically server-side, with the same detail.

A reviewer must not report a well-reasoned, consistently applied 403 as a defect.

---

## 3. Validation Error Detail Pattern [P]

```json
{
  "error": {
    "code": "validation_error",
    "message": "Request validation failed",
    "details": [
      {"field": "email", "code": "invalid_format", "message": "Must be a valid email"},
      {"field": "name", "code": "too_long", "message": "Maximum 100 characters"},
      {"field": "items[0].quantity", "code": "out_of_range", "message": "Must be > 0"}
    ]
  }
}
```

### Detail codes (for `details[].code`)

- `required` — field is missing
- `invalid_format` — wrong format (email, date, UUID)
- `too_long` / `too_short` — string length violation
- `out_of_range` — numeric value outside bounds
- `invalid_value` — value not in allowed set (enum violation)
- `duplicate` — value must be unique but already exists
- `immutable` — field cannot be changed after creation

---

## 4. Idempotency Error Patterns [C]

Binding under risk triggers **T1** (money), **T2** (quota/inventory), **T3**
(irreversible side effect). An append-only endpoint with no external effect does not
need an idempotency key, and reporting its absence there is a false positive.

### Idempotency-Key header

```
POST /api/v1/orders
Idempotency-Key: req-abc-123
Content-Type: application/json

{"items": [...], "total": 99.50}
```

### Responses

| Scenario | Response | Body |
|----------|----------|------|
| First request | 201 Created | Created order |
| Retry with same key + same body | 201 Created | Same response as the first (cached) |
| Retry with same key + different body | 409 Conflict | `{"error": {"code": "idempotency_conflict"}}` |
| Key expired (TTL passed) | 201 Created | New order (treated as a new request) |

### Key design rules

- Key scope: per-tenant per-subject — user A's key must not collide with user B's
- Key TTL: **24 hours is a default, not a requirement.** Derive it from
  *max client retry window + clock skew margin*. A mobile client that retries a queued
  payment after 3 days of offline needs a longer TTL; a synchronous internal RPC with a
  30s deadline needs far less.
- Storage: Redis or a database with TTL
- On conflict: return 409 with a clear error code, never silently reprocess

---

## 5. Concurrency Control Patterns [C]

<!-- api-lint: lww-acceptable -->

### Optimistic locking with ETag

```
GET /api/v1/users/123
→ 200 OK
   ETag: "v7"
   {"data": {"id": "123", "name": "Alice", "email": "alice@example.com"}}

PUT /api/v1/users/123
If-Match: "v7"
→ 200 OK (if version matches)
→ 412 Precondition Failed (if another update happened)
   {"error": {"code": "precondition_failed", "message": "Resource was modified"}}
```

### Last-write-wins is a legitimate choice

Not every resource needs optimistic locking. Last-write-wins is correct and simpler when:

- only one writer exists per resource (a user editing their own profile, a single job owner)
- writes are naturally idempotent (setting a state flag to the same terminal value)
- contention is negligible and the cost of a lost update is trivial

**The reviewable requirement is that the policy is stated**, not that ETag exists.
An API that documents "concurrent updates resolve last-write-wins; contention is
single-writer by construction" is a PASS. Escalate to a FAIL only under trigger **T4**
— genuine multi-writer contention — or where a lost update is financially or
operationally material (balances, inventory counts, permission grants).

---

## 6. Observability Without Leaking It Into the Contract

Error responses need exactly one observability field: a correlation ID.

```json
{
  "error": {
    "code": "forbidden",
    "message": "Access denied to this resource",
    "trace_id": "req-abc-123"
  }
}
```

Everything else an operator needs is recorded server-side and joined on `trace_id`:

| Data | Where it belongs | Why not in the response |
|------|------------------|------------------------|
| Correlation / trace ID | **Response + logs + span** | This is the join key; the client needs it to report a problem |
| Metric name (`http_request_errors_total`) | Metrics registry + dashboards | An internal naming detail; clients cannot act on it, and it couples your public contract to your monitoring stack's names |
| Audit subject / tenant / role | Audit sink + structured log | Echoing the caller's resolved role or tenant back discloses authorization state and helps an attacker map the permission model |
| Permission evaluation trace, policy IDs | Debug log at the authorization boundary | Reveals the internal authorization structure |
| Stack trace, SQL, driver text | Error log only | Reveals schema and implementation (see AE-9) |

```
// Server side — full context, one log line, keyed by the same trace_id
slog.Error("authorization denied",
    "trace_id",   traceID,
    "subject",    subjectID,
    "tenant",     tenantID,
    "role",       role,
    "resource",   resourceID,
    "metric",     "http_request_errors_total")
```

Do **not** put `metric` or `audit` keys inside the client-facing `error` object, and do
not move them to response headers such as `X-Audit-Subject` — a header is just as
public as a body field.

---

## 7. Scoped Idempotency-Key Implementation [C]

Production-grade idempotency goes beyond simple key deduplication.

### Key composition (prevent cross-user collision)

```
scope = tenant_id + subject_id + method + path
storage_key = SHA256(scope + idempotency_key_header)
```

### Request fingerprinting (detect body mismatch)

```
fingerprint = SHA256(method + path + request_body)
```

On replay: if `storage_key` matches but `fingerprint` differs → 409 Conflict
(same idempotency key reused with a different request body).

### Replay response

```
HTTP 201 Created
X-Idempotent-Replayed: true
{...original response body...}
```

### Key lifecycle

- TTL: default 24 hours; size it as max client retry window + clock skew (see §4)
- Scope: per-tenant per-subject, not global
- Storage: Redis with TTL, or a database with a cleanup job
