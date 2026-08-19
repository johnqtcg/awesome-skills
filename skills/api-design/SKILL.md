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
| Know how binding each rule is          | §2 Rule Nature and Finding Severity      |
| Check mandatory prerequisites          | §3 Mandatory Gates                       |
| Choose review depth                    | §4 Depth Selection                       |
| Handle incomplete context              | §5 Degradation Modes                     |
| Evaluate API design item by item       | §6 Design Checklist                      |
| Avoid common API design mistakes       | §7 Anti-Examples                         |
| Score the review result                | §8 Scorecard                             |
| Format review output                   | §9 Output Contract                       |
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

## §2 Rule Nature and Finding Severity

Most API "best practices" are house conventions, not protocol requirements. Reporting a
convention deviation with the same force as a security hole destroys the signal. But
"how binding is this rule" and "how bad is this instance" are **two different questions**,
and collapsing them into one tag is what makes two reviewers reach two verdicts.

### 2.1 Rule nature — a static property of the rule

Every rule in §6 carries exactly one nature tag. Nature answers *why the rule exists*.
It does **not** by itself determine severity.

| Tag | Nature | The rule says | A conforming API may |
|-----|--------|---------------|----------------------|
| **[P]** | Invariant | A spec requires it, or violating it is a security defect. Wrong regardless of business context. | — nothing to choose |
| **[D]** | Convention | This is the house default shape. | adopt any **consistent, stated** alternative |
| **[C]** | Policy | A decision the API owner must make and record. | choose **any** of the valid options |

For a **[C]** rule the review asks *"was a policy chosen and written down?"* — never
*"was my preferred option chosen?"* Disagreeing with a stated, consistently applied policy
is never a finding.

### 2.2 Risk triggers — conditions that change what is at stake

| ID | Trigger |
|----|---------|
| **T1** | Money movement — payment, refund, transfer, credit/debit, billing |
| **T2** | Quota or inventory decrement — seat allocation, stock reservation, rate quota |
| **T3** | Irreversible external side effect — send email/SMS, ship goods, provision infra, publish |
| **T4** | Concurrent multi-writer on the same resource — two humans or two jobs edit one record |
| **T5** | Untrusted callers — public or partner exposure |
| **T6** | Regulated or personal data in the response — PII, PHI, payment credentials |

A trigger does exactly one of two things, and **never lowers an obligation**:

- **Raises severity** of a [D] or [C] finding — an unstated write-conflict policy is a WARN
  in general and a FAIL under T4, because a lost update now costs something real.
- **Adds an obligation** to a rule of any nature — T6 adds data minimization to the [P] rule
  in item 5. A trigger attached to a [P] rule is normal: [P] rules can grow requirements
  under risk, they just never shrink.

If you cannot tell whether a trigger applies, record that in §9.9 and score the item `N/A`.
Do not assume the strict reading.

### 2.3 Where severity is decided

Severity is **not** a property of the nature tag. It is a function of
(nature × what is actually wrong × which triggers are live), and it is defined in
**exactly one place**: the table in §8. Do not restate a severity ceiling here — two
severity tables drift, and the reader then cannot tell which one binds.

---

## §3 Mandatory Gates

Execute gates in order. Each gate has a **STOP** condition.

### Gate 1: Scope Classification

| Mode | Trigger | Output |
|------|---------|--------|
| **review** | User provides an existing API spec, code, or endpoint list | Findings + improvement recommendations |
| **design** | User describes new endpoint requirements | Complete API contract |
| **governance** | User wants an API standards audit across endpoints | Consistency report + standardization plan |

**STOP**: Request is not API design (e.g., database query optimization). Redirect to the appropriate skill.

**PROCEED**: Mode selected. The mode determines whether Gate 2 can stop you.

### Gate 2: Consumer & Use-Case

| Item | Why it matters | If unknown |
|------|----------------|------------|
| **Who consumes this API?** | Frontend / mobile / partner / service-to-service — drives auth, versioning, error detail | See mode rule below |
| **Latency / consistency SLA** | Determines sync vs async patterns | Assume sync, best-effort; record in §9.9 |
| **Public vs internal** | Public APIs need stricter versioning and deprecation windows | See mode rule below |
| **Risk triggers present?** | Raises the severity of [D]/[C] findings and can add obligations (§2.2) | Assume none; record the assumption |

**Mode rule — this is the only correct reading of an unknown consumer:**

| Mode | Consumers unknown → |
|------|--------------------|
| **design** / **governance** | **STOP.** Inventing a contract for an unknown consumer produces an unusable contract. Ask. |
| **review** | **PROCEED in Minimal mode** (§5). Review only the rules that do not depend on consumer identity — [P] invariants, plus [D] naming/shape conventions. Do **not** score any item whose severity depends on an unknown trigger; list those as unassessed in §9.9. |

**PROCEED**: mode known, and either consumer context is known or review-mode degradation is declared.

### Gate 3: Risk Classification (change risk)

| Risk | Definition | Required action |
|------|-----------|-----------------|
| **SAFE** | New endpoint, additive optional fields, internal API | Standard review |
| **WARN** | Changing an existing response shape, new auth requirement | Compatibility assessment mandatory |
| **UNSAFE** | Removing/renaming fields, changing types, changing status code semantics, public API version bump | Migration plan + deprecation timeline mandatory |

**STOP**: Any UNSAFE change without a migration plan.

**PROCEED**: Every change has a risk level and a mitigation.

### Gate 4: Output Completeness

Before delivering, verify all §9 Output Contract sections are present. §9.9 Uncovered Risks must never be empty.

---

## §4 Depth Selection

| Depth | When to use | Gates | References to load |
|-------|-------------|-------|-------------------|
| **Lite** | Single endpoint review, ≤3 endpoints | 1–4 | None |
| **Standard** | Full API surface (4–15 endpoints), error model, pagination | 1–4 | `error-model-patterns.md` |
| **Deep** | Public/partner API, versioning strategy, deprecation, governance | 1–4 | Both reference files |

**Force Standard or higher** when any signal appears:
pagination/filtering design, idempotency requirement, versioning discussion, breaking change assessment, public API, multi-consumer API, any risk trigger T1–T6.

---

## §5 Degradation Modes

When context is incomplete, degrade explicitly — never guess consumer requirements,
and never silently upgrade an assumption into a finding.

| Available context | Mode | What you can do | What you cannot do |
|-------------------|------|-----------------|-------------------|
| Full (consumers, SLA, public/internal, existing contracts) | **Full** | Complete contract with compatibility assessment | — |
| Consumer type known, SLA unknown | **Degraded** | Contract design with assumptions documented | Precise rate-limit/timeout recommendations |
| Only endpoint description, no context | **Minimal** | [P] invariants + naming/shape conventions; report trigger-dependent items as unassessed | Score any item whose severity needs a trigger you cannot see, judge auth model, judge pagination fitness |
| No spec (greenfield requirements) | **Planning** | Propose API structure from requirements | Review an existing contract |

**Hard rules**:
- Never claim an API is "backward compatible" without reviewing the actual existing contract.
- In Degraded/Minimal mode, list every assumption in §9.9, and mark unassessed scorecard items `N/A` — never `FAIL`.

---

## §6 Design Checklist

Execute every item. Mark **PASS** / **WARN** / **FAIL** / **N/A** with evidence.
Each item shows its nature tag (§2.1) and the scorecard item it feeds (§8), or `—` if unscored. Severity comes from §8.1, never from the tag alone.

### 6.1 Resource Model

1. **[D] Resource naming & hierarchy** → `H1`. Plural nouns, lowercase, kebab-case: `/users`, `/order-items`. No verbs in URLs except explicit action sub-resources (`/orders/{id}/cancel`). Nesting reflects ownership (`/users/{id}/orders`); prefer ≤2 levels, more only when every level is part of the authorization boundary. A codebase-wide alternative convention that is applied consistently is a PASS with a note — consistency beats this default.

2. **[P] Method & success-status semantics** → `S1`. GET is safe (no side effects). PUT is a full replace and idempotent; PATCH is partial. DELETE is idempotent. POST is not idempotent. For a successful DELETE, RFC 9110 §9.3.5 permits **202** (accepted, not yet enacted), **204** (enacted, nothing to return), or **200** (enacted, body describes the status) — all three are legal; the requirement is that the contract states which one and is consistent per resource class.

   The **Code** column is [P]: sending 200 where the semantics call for 4xx is a defect. The
   **Also send** column is mostly [D] — read the force marker on each row before reporting it.
   Only rows marked [P] are protocol requirements.

   | Situation | Code | Also send | Force |
   |-----------|:----:|-----------|:-----:|
   | GET / PUT / PATCH success with a body | 200 | — | — |
   | POST created a resource | 201 | `Location`. RFC 9110 §15.3.2: **if Location is absent the target URI identifies the new resource**, so its absence is a usability miss, not a violation | [D] |
   | Accepted, not yet enacted | 202 | a status monitor to poll. RFC 9110 §15.3.3 says the response "ought to" point to one — strong advice, not a MUST | [D] |
   | Success with nothing to return | 204 | no body at all | [P] |
   | Malformed JSON in the body | 400 | a parse-error code | [D] |
   | Not authenticated | 401 | re-login *can* fix this | [P] |
   | Authenticated, not permitted | 403 | re-login *cannot* fix this — see item 7 | [P] |
   | Absent, or existence withheld | 404 | see item 7 | [P] |
   | State conflict, duplicate key | 409 | — | — |
   | Precondition failed (`If-Match`) | 412 | — | [P] |
   | Deliberately removed after sunset | 410 | 410 says "was here, deliberately gone"; 404 is still legal | [D] |
   | Semantically invalid field values | 422 | field-level `details[]`. RFC 9110 §15.5.21 defines 422 as "syntax correct, instructions unprocessable" — it does **not** mandate 422 for validation, and a consistent 400 is a valid house convention | [D] |
   | Rate limited | 429 | `Retry-After`. RFC 6585 §4 says the response **MAY** include it — recommend it, never fail on it | [D] |
   | Unexpected server error | 500 | log it, never expose it | [P] |

   Never swap 401 and 403 — the distinction is the whole signal a client needs to decide whether retrying with fresh credentials is worth it. That one **is** [P].

### 6.2 Safety & Authorization

3. **[P] Error transport integrity** → `C2`. Four properties, and only these four are invariants:
   - the failure carries a **non-2xx status** — never `200 {"success": false}`, because proxies, caches, browsers and client HTTP libraries branch on the status line, not on your body;
   - the body carries a **stable machine-identifiable discriminator** that clients can switch on without string-matching prose;
   - the **same shape is used by every endpoint** in the API;
   - nothing sensitive leaks (item 5).

   <!-- api-lint: error-shape-agnostic -->
   These are satisfied by more than one concrete format. An API that returns
   `application/problem+json` per **RFC 9457** — `type`/`title`/`status`/`detail`/`instance`
   plus extensions — satisfies all four, with `type` as the discriminator. So does a gRPC
   `google.rpc.Status`. **Do not FAIL a consistent RFC 9457 API for not using the envelope
   in item 4.** The invariant is the four properties; the field names are item 4's default.

4. **[D] Default error envelope** → `—` (report only). Absent an existing house standard, use
   `{error: {code, message, details[], trace_id}}`: `code` stable and snake_case, `message`
   human-readable and re-wordable, `trace_id` correlating to server logs. Any consistent
   alternative — RFC 9457 being the obvious one — is a PASS with a note. What fails is a
   *different shape per endpoint*, which is item 3's third invariant, not this rule.
   Load `references/error-model-patterns.md` for the standard code list.

5. **[P] No internal or sensitive data in responses** → `C3` · *Triggers: T6*. Never return stack traces, SQL text, driver messages, internal hostnames, file paths, or credentials. Also keep **server-side observability out of the client contract**: metric names, audit subject/tenant/role, and permission-evaluation traces belong in your logs and audit sink, keyed by `trace_id`. Echoing them back leaks authorization state to the caller and couples the client contract to internal monitoring names. Under **T6** two further requirements bind: return only the regulated fields the caller actually needs (data minimization — a full record because "the client might want it" is a disclosure), and never echo a submitted regulated value back inside `details[]` of a validation error.

6. **[P] Object-level authorization is performed** → `C1`. Every endpoint that reaches a resource by ID MUST verify that *this caller* may reach *that specific resource* — ownership, tenant scope, or role. `GET /users/{id}` must not serve another user's record merely because the request is authenticated. This is OWASP API Security #1 (Broken Object Level Authorization). The **check** is the non-negotiable part; the status code returned on denial is item 7.

7. **[C] Denial status policy** → `—` (report only). Both 403 and 404 are legitimate; OWASP accepts either, and forbids only 200. Choose by whether the resource's *existence* is confidential:
   - **404** when existence itself is secret — enumerable IDs, cross-tenant resources, per-user objects in a shared ID space.
   - **403** when existence is not secret and a clear denial aids the caller — a teammate lacking a role on a known shared resource, admin tooling, internal APIs.
   - **Consistency is the security property.** Mixing 403 and 404 across one resource class *is* the enumeration oracle you were trying to close. Log both identically server-side.

8. **[C] Retry-safety policy for mutations** → `S2` · *Triggers: T1, T2, T3*. A POST or action endpoint whose replay would double-charge, double-allocate, or re-send needs a stated answer to "what happens on retry". Valid options include an `Idempotency-Key` header, a client-supplied natural key the server dedupes on, an exactly-once consumer, or a documented "replays are harmless here". **Under T1/T2/T3 having no stated answer is a FAIL**; elsewhere it is a WARN, and an append-only endpoint with no external effect is a PASS. If you choose `Idempotency-Key`, production-grade keys need: (a) **scope** — tenant + subject + method + path, so two callers cannot collide; (b) **request fingerprint** — same key with a different body → 409; (c) **TTL** — default 24h, chosen as *max client retry window + clock skew*; (d) **replay indicator** — `X-Idempotent-Replayed: true` on a cache hit.

9. **[C] Write-conflict policy** → `S2` · *Triggers: T4*. Concurrent updates resolve either by optimistic locking (`ETag` + `If-Match`, 412 on mismatch) or by last-write-wins. LWW is a legitimate choice, and the reportable failure is an **unstated** policy — never the absence of ETag. Under **T4** apply §8.1 by asking which of three things is true, in this order:
   - **No policy stated** → FAIL. Nobody knows what a concurrent write does.
   - **A policy is stated and its premise holds** → PASS. Including "multi-writer, LWW, lost updates accepted because the field is advisory and the user sees current state on reload." You may record the risk; you may not fail it.
   - **A policy is stated but the design contradicts its premise** → FAIL. "LWW is safe because only the owner writes this record", on a record a batch job also writes, is a false premise, not a preference. Name the second writer as the evidence.

   Without T4 the same three cases are FAIL / PASS / WARN respectively.

10. **[P] Input validation is specified** → `S3`. Every request field has a declared type, required/optional status, and bounds. Undefined behaviour for a missing required field is a contract gap, not an implementation bug (see AE-6). Which rejection code carries a validation failure is [D], not part of this rule — see the status table in item 2: 422 with `details[]` is this skill's default and a consistent 400 is an equally valid house convention. What this rule requires is that the contract *defines* the rejection behaviour at all, and that caller error never surfaces as 5xx.

### 6.3 Query & Pagination

11. **[D] Pagination bounded and stable** → `S4` · *Triggers: T5*. Cursor-based for large or high-churn datasets; offset-based for small, searchable, or page-numbered admin UX. Enforce a server-side max `limit`. Always sort on a **stable** key — append a unique tie-breaker (e.g. `id`) so page boundaries are deterministic when the primary sort key has duplicates.

12. **[D] Filtering, sorting, and search constrained** → `H3`. Only allowlisted fields may be filtered or sorted; reject unknown fields with 400 + error code. Never interpolate filter values into a query. Keep full-text search on its own `q` parameter or `/search` endpoint rather than overloading filter params.

### 6.4 Compatibility & Operations

13. **[P] Every change classified breaking or non-breaking** → `S5`. Non-breaking: add optional response fields, add endpoints, add optional query params, relax validation. Breaking: remove/rename fields, change types, tighten validation, change status-code semantics, add a required request field.

    **Field order is not on either list by default.** RFC 8259 §1 defines a JSON object as an *unordered* collection of name/value pairs, so reordering fields is **not** a breaking change for any spec-conformant consumer. It does change the serialized byte sequence — Go's `encoding/json` (and `sonic`) emit struct fields in declaration order — which matters in exactly two cases:
    - a **named** consumer parses the body by position or string-prefix rather than by key (record it as that consumer's non-conformance, with its identity, not as a property of JSON);
    - the raw body feeds a **byte-exact artifact** — response signature/digest, HMAC, content-addressed cache key, or golden-file test.

    Absent one of those two, classify a reorder as non-breaking. Load `references/compatibility-rules.md` for the full matrix.

14. **[D] OpenAPI elements complete** → `H2`. Paths, methods, parameters, request/response schemas per status code, error codes, auth requirements. Keep a baseline spec in CI and diff each PR against it to catch removed paths, removed fields, and type changes automatically.

15. **[C] Rate-limit policy** → `H4` · *Triggers: T5*. Valid options run from a per-actor quota returning 429 (with `Retry-After` recommended — RFC 6585 §4 makes it a MAY, so never fail on its absence) through to an explicit "no limit; capacity bounded by the upstream gateway". **Under T5 no stated policy is a FAIL**; for trusted internal callers it is a WARN. What is reportable is silence — nobody knowing whether a limit exists — never the option chosen.

16. **[C] Operational contract documented** → `—` (report only). If the service exposes health/readiness endpoints or middleware, state the shape: a liveness probe (`GET /healthz` — is the process alive) split from a readiness probe (`GET /readyz` — are dependencies reachable), whether those probes are authenticated (unauthenticated probes are simpler but disclose service state — a threat-model call), and middleware order. A common ordering is Recovery → CORS → Logging → RateLimit → Auth → Handler, because CORS preflight carries no token and rate limiting should absorb credential brute-force before auth. Deviations are fine when argued against those reasons.

---

## §7 Anti-Examples

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

### AE-4: Replayable money-moving POST
```
WRONG: POST /payments — no Idempotency-Key → network retry double-charges the customer
RIGHT: POST /payments with Idempotency-Key: "req-abc-123" → retry returns the original response
```
Binding under T1–T3 (§2). A `POST /audit-log-entries` with no external side effect does not need this.

### AE-5: No object-level authorization (IDOR)
```
WRONG: GET /users/456 — returns data whenever the caller is authenticated (any user reads any user)
RIGHT: GET /users/456 — server verifies caller is user 456 or holds an admin role, then serves or denies
```
OWASP API Security #1. Authentication != authorization. The denial status (403 or 404) is a separate policy choice — see §6 item 7 and AE-13.

### AE-6: Design issue reported as implementation bug
```
WRONG: "Bug: API returns 500 when email is missing"
RIGHT: "API design gap: POST /users lacks input validation spec — no defined behavior for missing required fields"
```

Extended anti-examples (AE-7 through AE-14) in `references/api-anti-examples.md`.

---

## §8 API Design Scorecard

Score 12 items. Unassessed items in Degraded/Minimal mode are `N/A`, never `FAIL`.

### 8.1 Severity — the single decision table

This is the **only** place severity is defined (§2.3). Read the row for what is actually
wrong; the nature tag alone never decides the outcome.

Only a trigger **that the rule itself declares** moves it between the last two columns.
Each §6 rule states its own triggers (`Triggers: T4`); a rule that declares none is always
read in the "no applicable trigger" column. T1 being live somewhere in the API does not
escalate an unrelated naming deviation.

| Nature | What is wrong | No applicable trigger live | Applicable trigger live |
|--------|---------------|----------------------------|-------------------------|
| **[P]** | the invariant is violated | **FAIL** | **FAIL** (the trigger may add obligations, never remove them) |
| **[D]** | deviates, but consistently and with a stated reason | **PASS** + note | **PASS** + note |
| **[D]** | deviates inconsistently, or with no stated reason | **WARN** | **FAIL** |
| **[C]** | a policy is stated, and its stated premise holds | **PASS** | **PASS** |
| **[C]** | you would have chosen differently | **PASS** — record the trade-off | **PASS** |
| **[C]** | a policy is stated, but the design **contradicts the premise the policy rests on** | **WARN** | **FAIL** |
| **[C]** | no policy is stated | **WARN** | **FAIL** |
| any | could not be assessed (Degraded/Minimal) | **N/A** | **N/A** |

WARN never fails its scorecard item; it is reported and carried to §9.9. FAIL fails it.

**The falsified-premise row is not a back door for overruling the owner's choice.** It fires
only when the API's *own justification* is untrue — "last-write-wins is safe here because
only the owner writes this record", on a resource the design shows two writers reaching.
That is a factual contradiction you can point at, not a preference. An owner who writes
"multi-writer, last-write-wins, we accept lost updates because the field is advisory" has
stated a policy whose premise holds: **PASS**, with the trade-off recorded.

**What a [C] rule can and cannot cause.** A [C] rule can fail its item only through
*silence under a live trigger* — never through the choice made. Because `S2` is fed by
[C] rules, an unstated write-conflict policy under T4 can consume one of the five Standard
slots, and combined with another Standard failure that can produce an overall FAIL. That
is intended: an unanswered concurrency question on a genuinely contended resource is a
real defect. What cannot happen is an overall FAIL caused by disagreeing with a stated
policy, and no [C] rule feeds a Critical item, so contextual judgement can never trip the
any-FAIL tier.

### Critical — any FAIL means overall FAIL

Security and protocol integrity only. Nothing cosmetic belongs in this tier.

- [ ] `C1` Object-level authorization performed on every resource-by-ID endpoint (item 6)
- [ ] `C2` Failures carry a non-2xx status and a stable machine-identifiable discriminator, in one shape across the API — any consistent format, RFC 9457 included (item 3)
- [ ] `C3` No internal implementation detail, authorization state, or sensitive data in responses (item 5)

### Standard — 4 of 5 must pass

- [ ] `S1` HTTP method and success-status semantics correct (item 2)
- [ ] `S2` Retry safety and write-conflict policy specified where risk triggers apply (item 8, item 9)
- [ ] `S3` Input validation specified per endpoint (item 10)
- [ ] `S4` Pagination bounded with a stable sort key (item 11)
- [ ] `S5` Every change classified breaking or non-breaking (item 13)

### Hygiene — 3 of 4 must pass

- [ ] `H1` Resource naming and hierarchy consistent (item 1)
- [ ] `H2` OpenAPI elements complete with a CI contract baseline (item 14)
- [ ] `H3` Filtering, sorting, and search constrained to allowlists (item 12)
- [ ] `H4` Rate-limit policy stated — including an explicit "none needed" (item 15)

**Verdict**: `X/12`; Critical: `Y/3`; Standard: `Z/5`; Hygiene: `W/4`.
PASS requires: Critical 3/3 AND Standard ≥4/5 AND Hygiene ≥3/4.
`N/A` items are excluded from both numerator and denominator; report the reduced denominator explicitly.

**Report-only rules** (never scored, always surfaced in §9.9 when undocumented):
default error envelope (item 4), denial status policy (item 7), operational contract (item 16).
Item 4 is deliberately unscored: deviating from the house envelope is a [D] matter, and a
consistent RFC 9457 API must not lose a Critical point for it.

---

## §9 Output Contract

Every API design review MUST produce these sections. Write "N/A — [reason]" if inapplicable.

```
### 9.1 Context Gate
| Item | Value | Source |   ← include mode, consumer type, risk triggers found

### 9.2 Depth & Mode
[Lite/Standard/Deep] × [review/design/governance] × [Full/Degraded/Minimal/Planning] — [rationale]

### 9.3 Endpoint Contract Table
| Method | Path | Purpose | Auth | Idempotent |

### 9.4 Request/Response Design
- Per-endpoint: request schema, response schema, status codes, validation rules

### 9.5 Error Model
- Standard error codes + examples per endpoint

### 9.6 Pagination/Filtering Policy (Standard/Deep)

### 9.7 Compatibility Assessment (Standard/Deep)
- Breaking vs non-breaking classification per change
- Migration/deprecation plan if breaking

### 9.8 OpenAPI Spec Elements

### 9.9 Uncovered Risks (MANDATORY — never empty)
| Area | Reason | Impact | Follow-up |
```

**Finding format** — every finding carries its nature tag, the triggers that were live, and the severity §8.1 assigns, so a reader can re-derive the verdict:
`[P|D|C] <scorecard id or —> <triggers or none> <PASS|WARN|FAIL|N/A> — <evidence>`

**Volume rules**:
- FAIL: always fully detailed
- WARN: up to 10; overflow to §9.9
- PASS: summary only
- §9.9 minimum: every assumption, every item left N/A for an unknown trigger, every undocumented [C] policy

**Scorecard summary** (append after §9.9):
```
Scorecard: X/12 — Critical Y/3, Standard Z/5, Hygiene W/4 — PASS/FAIL
Risk triggers: [T1..T6 present, or none identified]
Data basis: [full context | degraded | minimal | planning]
```

---

## §10 Reference Loading Guide

| Condition | Load |
|-----------|------|
| Standard or Deep depth | `references/error-model-patterns.md` |
| Deep depth, or breaking change signals | `references/compatibility-rules.md` |
| Extended anti-example matching | `references/api-anti-examples.md` |
