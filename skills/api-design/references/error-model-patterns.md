# REST API Error Model Patterns

A consistent error model is the difference between "clients can handle failures
gracefully" and "every team guesses what went wrong from a string message."

---

## 1. Standard Error Envelope

Every error response MUST use this structure:

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
- Never expose: stack traces, SQL queries, internal service names, file paths
- `details[].field` uses dot-notation for nested fields: `address.zip_code`

---

## 2. Standard Error Codes

| Code | HTTP Status | When to use |
|------|:-----------:|-------------|
| `invalid_json` | 400 | Request body is not valid JSON |
| `validation_error` | 422 | One or more fields fail validation (use details[]) |
| `missing_field` | 422 | Required field is absent |
| `invalid_format` | 422 | Field present but wrong format (email, UUID, etc.) |
| `unauthorized` | 401 | No valid authentication credentials |
| `forbidden` | 403 | Authenticated but not authorized for this resource |
| `not_found` | 404 | Resource does not exist (or caller has no access — use 404 not 403 for IDOR) |
| `conflict` | 409 | Resource state conflict (duplicate key, already exists) |
| `precondition_failed` | 412 | ETag / If-Match condition not met |
| `idempotency_conflict` | 409 | Idempotency-Key reused with different request body |
| `rate_limit_exceeded` | 429 | Too many requests — include Retry-After header |
| `internal_error` | 500 | Unexpected server error — log details, don't expose |
| `service_unavailable` | 503 | Temporary overload or maintenance — include Retry-After |

### IDOR-safe 404 pattern

When a user requests a resource they don't own, return 404 (not 403):
- 403 reveals the resource exists → information leak
- 404 reveals nothing → safe default

---

## 3. Validation Error Detail Pattern

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

## 4. Idempotency Error Patterns

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
| Retry with same key + same body | 201 Created | Same response as first (cached) |
| Retry with same key + different body | 409 Conflict | `{"error": {"code": "idempotency_conflict"}}` |
| Key expired (TTL passed) | 201 Created | New order (treated as new request) |

### Key design rules

- Key scope: per-user (user A's key doesn't conflict with user B's)
- Key TTL: 24 hours (configurable; long enough for retry windows)
- Storage: Redis or database with TTL
- On conflict: return 409 with clear error code, never silently reprocess

---

## 5. Concurrency Control Patterns

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

### Without ETag: last-writer-wins

If you choose not to implement ETag, document that concurrent updates are
resolved by last-writer-wins. This is acceptable for some use cases but
dangerous for financial or inventory data.

---

## 6. Observability Fields in Error Responses

Production APIs benefit from embedding observability context in error responses:

```json
{
  "error": {
    "code": "forbidden",
    "message": "Access denied to this resource",
    "trace_id": "req-abc-123",
    "metric": "http_request_errors_total",
    "audit": {
      "subject": "user-456",
      "tenant": "acme-corp",
      "role": "viewer"
    }
  }
}
```

| Field | Purpose | When to include |
|-------|---------|----------------|
| `trace_id` | Cross-service request correlation | Always |
| `metric` | Standardized metric name for dashboards | 4xx/5xx errors |
| `audit.subject` | Who made the request | Auth/authz errors |
| `audit.tenant` | Which tenant context | Multi-tenant APIs |
| `audit.role` | Caller's role at time of request | Permission errors |

**Security note**: omit `audit` fields on unauthenticated 401 errors.
Consider exposing as response headers (`X-Audit-Subject`, `X-Audit-Tenant`)
for middleware/proxy consumption.

---

## 7. Scoped Idempotency-Key Implementation

Production-grade idempotency goes beyond simple key deduplication:

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
(same idempotency key reused with different request body).

### Replay response

```
HTTP 201 Created
X-Idempotent-Replayed: true
{...original response body...}
```

### Key lifecycle

- TTL: 24 hours (configurable per endpoint)
- Scope: per-tenant per-subject (not global)
- Storage: Redis with TTL or database with cleanup job