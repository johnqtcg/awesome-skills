---
name: api-design
description: >
  REST API contract designer and reviewer. ALWAYS use when designing new endpoints,
  reviewing existing API contracts, planning API versioning, or standardizing error models.
  Covers resource modeling (URL/naming), HTTP method semantics, status code selection,
  error model consistency, pagination/filtering/sorting, idempotency keys, concurrency
  control (ETag/If-Match), object-level authorization (IDOR prevention), rate limiting,
  backward compatibility assessment, and OpenAPI-ready output. Use even for "just add
  an endpoint" — inconsistent APIs compound into integration nightmares that are
  extremely expensive to fix after clients depend on them.
---

# REST API Design Review

## Quick Reference

| If you need to…                        | Go to                                    |
|----------------------------------------|------------------------------------------|
| Understand what this skill covers      | §1 Scope                                 |
| Check mandatory prerequisites          | §2 Mandatory Gates                       |
| Choose review depth                    | §3 Depth Selection                       |
| Handle incomplete context              | §4 Degradation Modes                     |
| Evaluate API design item by item       | §5 Design Checklist                      |
| Avoid common API design mistakes       | §6 Anti-Examples                         |
| Score the review result                | §7 Scorecard                             |
| Format review output                   | §8 Output Contract                       |
| Deep-dive error model patterns         | `references/error-model-patterns.md`     |
| Check compatibility rules              | `references/compatibility-rules.md`      |

---

## §1 Scope

**In scope** — REST API contract design and review:

- Resource modeling (URL structure, naming, hierarchy)
- HTTP method semantics (GET/POST/PUT/PATCH/DELETE)
- Status code selection (2xx/4xx/5xx semantic correctness)
- Error model design (machine-parseable codes, field-level details)
- Pagination, filtering, sorting, search patterns
- Idempotency (Idempotency-Key header, retry safety)
- Concurrency control (ETag, If-Match, optimistic locking)
- Auth/AuthZ per endpoint, IDOR prevention
- Rate limiting (per-actor, 429 + Retry-After)
- Versioning, backward compatibility, deprecation planning
- OpenAPI/Swagger contract generation

**Out of scope** — delegate to dedicated skills:

- API integration testing → `api-integration-test`
- gRPC/Protobuf design → separate skill
- Application code implementation → `go-code-reviewer`

---

## §2 Mandatory Gates

Execute gates sequentially. Each gate has a **STOP** condition.

### Gate 1: Consumer & Use-Case

| Item | Why it matters | If unknown |
|------|----------------|------------|
| **Who consumes this API?** | Frontend / mobile / partner / service-to-service — drives auth, versioning, error detail | Must clarify |
| **Latency / consistency SLA** | Determines sync vs async patterns | Assume sync, best-effort |
| **Public vs internal** | Public APIs need stricter versioning, deprecation windows | Assume internal |

**STOP**: Cannot determine who the consumers are. API design without consumer context produces unusable contracts.

**PROCEED**: At least consumer type and public/internal classification known.

### Gate 2: Scope Classification

| Mode | Trigger | Output |
|------|---------|--------|
| **review** | User provides existing API spec/code | Findings + improvement recommendations |
| **design** | User describes new endpoint requirements | Complete API contract |
| **governance** | User wants API standards audit across endpoints | Consistency report + standardization plan |

**STOP**: Request is not API design (e.g., database query optimization). Redirect to appropriate skill.

**PROCEED**: API design intent confirmed.

### Gate 3: Risk Classification

| Risk | Definition | Required action |
|------|-----------|-----------------|
| **SAFE** | New endpoint, additive fields, internal API | Standard review |
| **WARN** | Changing existing response shape, new auth requirement | Compatibility assessment mandatory |
| **UNSAFE** | Removing/renaming fields, changing status codes, public API version bump | Migration plan + deprecation timeline mandatory |

**STOP**: Any UNSAFE change without migration plan.

**PROCEED**: Every change has risk level and mitigation.

### Gate 4: Output Completeness

Before delivering output, verify all §8 Output Contract sections present. §8.9 Uncovered Risks must never be empty.

---

## §3 Depth Selection

| Depth | When to use | Gates | References to load |
|-------|-------------|-------|-------------------|
| **Lite** | Single endpoint review, ≤3 endpoints | 1–4 | None |
| **Standard** | Full API surface (4–15 endpoints), error model, pagination | 1–4 | `error-model-patterns.md` |
| **Deep** | Public/partner API, versioning strategy, deprecation, governance | 1–4 | Both reference files |

**Force Standard or higher** when any signal appears:
pagination/filtering design, idempotency requirement, versioning discussion, breaking change assessment, public API, multi-consumer API.

---

## §4 Degradation Modes

When context is incomplete, degrade gracefully — never guess consumer requirements.

| Available context | Mode | What you can do | What you cannot do |
|-------------------|------|-----------------|-------------------|
| Full (consumers, SLA, public/internal, existing contracts) | **Full** | Complete contract with compatibility assessment | — |
| Consumer type known, SLA unknown | **Degraded** | Contract design with assumptions documented | Precise rate-limit/timeout recommendations |
| Only endpoint description, no context | **Minimal** | Resource naming + method + status code review | Full contract, auth model, pagination |
| No spec (greenfield requirements) | **Planning** | Propose API structure from requirements | Review existing contract |

**Hard rule**: Never claim an API is "backward compatible" without reviewing the actual existing contract. In Degraded/Minimal mode, list all assumptions in §8.9.

---

## §5 Design Checklist

Execute every item. Mark **PASS** / **WARN** / **FAIL** with evidence.

### 5.1 Resource Model

1. **Resource naming** — plural nouns, lowercase, kebab-case. `/users`, `/order-items`, not `/getUsers`, `/OrderItem`. No verbs in URLs except explicit action sub-resources (`/orders/{id}/cancel`).

2. **URL hierarchy reflects ownership** — nested resources show containment: `/users/{id}/orders`. Avoid deeply nested URLs (max 2 levels). Cross-references use query params or top-level resources.

3. **HTTP method semantics correct** — GET is safe (no side effects), PUT is idempotent (full replace), DELETE is idempotent, POST is not idempotent (use Idempotency-Key). PATCH is partial update.

4. **Status codes semantically correct** — 200 OK (with body), 201 Created (with Location header), 204 No Content (successful delete/update), 400 (client error), 401 (not authenticated), 403 (not authorized), 404 (not found), 409 (conflict), 422 (validation), 429 (rate limited). Never return 200 for errors.

### 5.2 Safety & Reliability

5. **Error model consistent and machine-parseable** — every error response uses the same envelope: `{error: {code, message, details[], trace_id}}`. `code` is stable, snake_case, machine-readable. `message` is human-readable. Never expose stack traces or internal details. For production observability, also include: `metric` (standardized metric name for monitoring, e.g., `http_request_errors_total`) and `audit` fields (subject/tenant/role for security auditing). Load `references/error-model-patterns.md` for standard codes.

6. **Idempotency for mutations** — POST (create) and action endpoints must support `Idempotency-Key` header for retry safety. Production-grade idempotency requires: (a) **scoped keys** — scope by tenant + subject + method + path to prevent cross-user collision, (b) **request fingerprinting** — hash the request body; if same key reused with different body → 409 Conflict, (c) **TTL** — keys expire after 24h (configurable), (d) **replay indicator** — return `X-Idempotent-Replayed: true` header on cache hit.

7. **Concurrency control** — update endpoints should support `ETag` / `If-Match` for optimistic locking. Return 412 Precondition Failed on version mismatch. Without this, last-writer-wins silently overwrites concurrent changes.

8. **Object-level authorization (IDOR prevention)** — every endpoint that accesses a resource by ID must verify the caller owns or has permission to access that specific resource. `GET /users/{id}` must not return other users' data regardless of authentication. This is OWASP API Security Top 1.

### 5.3 Query & Pagination

9. **Pagination type fits use case** — cursor-based for large/high-churn datasets (efficient, consistent), offset-based for small/search/admin UX (page numbers). Enforce server-side max limit (e.g., 100). Return `next_cursor` / `total_count` as appropriate. Always use **stable sorting**: append a unique field (e.g., `id`) as tie-breaker to prevent non-deterministic page boundaries when primary sort has duplicates.

10. **Filtering and sorting allowlisted** — only explicitly allowed fields can be filtered/sorted. Reject unknown fields with 400 + error code. Never pass filter values directly to database queries (SQL injection risk).

11. **Search separate from filtering** — full-text search uses a `q` parameter or dedicated `/search` endpoint. Don't overload filter params for search.

### 5.4 Compatibility & Operations

12. **Rate limiting defined** — per-actor (user/IP/API key) limits defined. Return 429 with `Retry-After` header. Different limits for different actor types (internal service vs public user).

13. **Backward compatibility assessed** — every change classified as breaking or non-breaking. Non-breaking: add optional fields, add endpoints. Breaking: remove/rename fields, change types, tighten validation, **reorder fields in JSON/gRPC response structs**. On the last point: Go's `encoding/json` (and alternatives like `sonic`) serialize struct fields in their declaration order; reordering fields — even via "harmless" internal tools like `fieldalignment` — changes the JSON output shape and breaks consumers that parse by field position or string-prefix match, without adding, removing, or renaming any field. Treat any struct field reorder in an API response type as a breaking change unless all known consumers are verified to use key-based JSON parsing. Load `references/compatibility-rules.md` for full matrix.

14. **OpenAPI spec complete** — final output includes or references an OpenAPI-ready specification: paths, methods, parameters, request/response schemas per status code, error codes, auth requirements. Include an **API contract test strategy**: maintain a baseline OpenAPI spec and automatically detect breaking changes (removed paths, removed fields, changed types) in CI.

15. **Health check endpoint** — provide `GET /healthz` (no auth required) returning `{status: "ok"}` for load balancer probes. Separate from readiness checks if the service has warm-up dependencies.

16. **Middleware ordering documented** — if the API has middleware (auth, rate-limit, logging, CORS), document the execution order and rationale. Standard order: Recovery → CORS → Logging → RateLimit → Auth → Handler. CORS before auth (OPTIONS preflight needs no token); RateLimit before auth (prevent brute-force at perimeter).

---

## §6 Anti-Examples

### AE-1: Verb in URL
```
WRONG: POST /api/v1/createUser
RIGHT: POST /api/v1/users
```
Resources are nouns. The HTTP method IS the verb.

### AE-2: 200 for everything
```
WRONG: HTTP 200 {"success": false, "error": "not found"}
RIGHT: HTTP 404 {"error": {"code": "not_found", "message": "User not found"}}
```
Status codes exist for machines. Wrapping errors in 200 breaks HTTP semantics, caching, and client error handling.

### AE-3: Unstructured error messages
```
WRONG: HTTP 400 {"message": "Something went wrong"}
RIGHT: HTTP 422 {"error": {"code": "validation_error", "message": "Validation failed", "details": [{"field": "email", "code": "invalid_format"}]}}
```
Without a stable `code`, clients can only match on `message` strings — which break on wording changes.

### AE-4: POST create without idempotency
```
WRONG: POST /orders — no Idempotency-Key → network retry creates duplicate order
RIGHT: POST /orders with Idempotency-Key: "req-abc-123" → retry returns same response
```

### AE-5: No object-level authorization (IDOR)
```
WRONG: GET /users/456 — returns data if user is authenticated (any user can read any user)
RIGHT: GET /users/456 — returns 404 unless caller is user 456 or has admin role
```
OWASP API Security #1 vulnerability. Authentication != Authorization.

### AE-6: Design issue reported as implementation bug
```
WRONG: "Bug: API returns 500 when email is missing"
RIGHT: "API design gap: POST /users lacks input validation spec — no defined behavior for missing required fields"
```

Extended anti-examples (AE-7 through AE-13) in `references/api-anti-examples.md`.

---

## §7 API Design Scorecard

### Critical — any FAIL means overall FAIL

- [ ] Resource naming follows REST conventions (plural nouns, kebab-case, no verbs)
- [ ] Error model is consistent and machine-parseable across all endpoints
- [ ] Object-level authorization (IDOR) addressed for every resource-by-ID endpoint

### Standard — 4 of 5 must pass

- [ ] HTTP method semantics correct (GET safe, PUT/DELETE idempotent)
- [ ] Idempotency strategy exists for create/action mutations
- [ ] Input validation rules explicit per endpoint
- [ ] Pagination type matches data scale and use case
- [ ] Backward compatibility impact assessed for changes

### Hygiene — 3 of 4 must pass

- [ ] Rate limiting defined per actor type with 429 + Retry-After
- [ ] OpenAPI-ready spec elements complete
- [ ] Filtering/sorting fields explicitly allowlisted
- [ ] Concurrency control (ETag/If-Match) for update endpoints

**Verdict**: `X/12`; Critical: `Y/3`; Standard: `Z/5`; Hygiene: `W/4`.
PASS requires: Critical 3/3 AND Standard ≥4/5 AND Hygiene ≥3/4.

---

## §8 Output Contract

Every API design review MUST produce these sections. Write "N/A — [reason]" if inapplicable.

```
### 8.1 Context Gate
| Item | Value | Source |

### 8.2 Depth & Mode
[Lite/Standard/Deep] × [review/design/governance] — [rationale]

### 8.3 Endpoint Contract Table
| Method | Path | Purpose | Auth | Idempotent |

### 8.4 Request/Response Design
- Per-endpoint: request schema, response schema, status codes, validation rules

### 8.5 Error Model
- Standard error codes + examples per endpoint

### 8.6 Pagination/Filtering Policy (Standard/Deep)

### 8.7 Compatibility Assessment (Standard/Deep)
- Breaking vs non-breaking classification per change
- Migration/deprecation plan if breaking

### 8.8 OpenAPI Spec Elements

### 8.9 Uncovered Risks (MANDATORY — never empty)
| Area | Reason | Impact | Follow-up |
```

**Volume rules**:
- FAIL: always fully detailed
- WARN: up to 10; overflow to §8.9
- PASS: summary only
- §8.9 minimum: document all assumptions (especially consumer type if unknown)

**Scorecard summary** (append after §8.9):
```
Scorecard: X/12 — Critical Y/3, Standard Z/5, Hygiene W/4 — PASS/FAIL
Data basis: [full context | degraded | minimal | planning]
```

---

## §9 Reference Loading Guide

| Condition | Load |
|-----------|------|
| Standard or Deep depth | `references/error-model-patterns.md` |
| Deep depth, or breaking change signals | `references/compatibility-rules.md` |
| Extended anti-example matching | `references/api-anti-examples.md` |