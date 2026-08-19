# API Compatibility Rules

Backward compatibility determines whether existing clients break when the API changes.
Every API change must be classified before deployment.

Nature tags follow §2.1 of the SKILL.md: **[P]** invariant, **[D]** convention,
**[C]** policy. Severity depends on the live risk triggers and is decided in §8.1.

---

## 1. Non-Breaking Changes (Safe to deploy)

| Change | Why safe | Caveat |
|--------|----------|--------|
| Add new optional field to response | Objects are open; conformant clients ignore unknown keys | A client doing exhaustive/strict schema validation will reject it — check known strict consumers |
| Add new optional query parameter | Existing requests don't include it | — |
| Add new endpoint | No existing client calls it | — |
| Add new enum value | Only safe if the contract documented unknown-value handling | Otherwise treat as breaking |
| Add new HTTP header | Clients ignore unknown headers | — |
| Relax validation (accept wider input) | Existing valid input stays valid | — |
| Increase rate limit | Clients can only benefit | — |
| **Reorder response fields** | RFC 8259 §1: a JSON object is an *unordered* collection — key order is not part of the contract | Breaking only if a named consumer parses positionally/by prefix, or the raw body feeds a signature/digest/golden file. See §2.1 |

## 2. Breaking Changes (Require migration plan)

| Change | Why breaking | Mitigation |
|--------|-------------|------------|
| Remove response field | Clients reading it get null/error | Deprecate first, remove after sunset |
| Rename response field | Same as removal for the old name | Add new field, deprecate old |
| Change field type | Client parsing breaks | New field with new type |
| Add required request field | Existing requests missing it → 422 | Make optional first, require later |
| Tighten validation | Previously valid input rejected | Announce, grace period |
| Change status code semantics | Client error handling breaks | Version bump |
| Change URL structure | Existing client URLs break | Redirect + version bump |
| Change auth requirements | Existing tokens/keys rejected | Grace period + migration guide |
| Remove endpoint | Clients get 404 | Deprecate → sunset → remove |
| Change error `code` values | Client error handling breaks | Version bump |

### 2.1 Field order: what is actually at stake

Reordering struct fields changes the serialized byte sequence — Go's `encoding/json`
(and `sonic`) emit fields in declaration order — but **not** the JSON data model.
Classify a reorder as breaking only with evidence of one of these:

1. **A named non-conformant consumer** parses the body by field position or by
   string-prefix match. Record the consumer's identity and treat the fix as that
   consumer's bug; the reorder is breaking *for it*, not in general.
2. **A byte-exact artifact** derives from the raw body: HMAC or response signature,
   content-addressed cache key, an `ETag` computed by hashing the body, or a
   golden-file test asserting exact bytes. Changing byte order invalidates the digest.

With neither present, a reorder is non-breaking and needs no migration plan. Do not
promote a single legacy consumer's parsing bug into a general rule about JSON.

## 3. Versioning Strategy

### Path versioning ([D] default for public APIs)

```
/api/v1/users    ← current stable
/api/v2/users    ← new version with breaking changes
```

- Simple, visible, cacheable
- At most 2 active major versions
- Old version gets security fixes only during the sunset period

### Header versioning (for internal APIs)

```
Accept: application/vnd.myapi.v2+json
```

- Cleaner URLs but harder to test in a browser
- Suitable for service-to-service where clients control headers

### Query parameter versioning (not recommended)

```
/api/users?version=2
```

- Pollutes query space, confuses caching
- Avoid unless a legacy constraint requires it

### Versioning strategy selection matrix

| Criterion | Path (`/v1/`) | Header (`Accept: vnd.v2`) | Query (`?v=2`) |
|-----------|:---:|:---:|:---:|
| Visibility in URL | Yes | No | Partial |
| Browser/curl testability | Easy | Requires custom headers | Easy |
| CDN/proxy caching | Clean cache key | Varies by CDN config | Pollutes cache key |
| API Gateway routing | Native support | Requires header inspection | Fragile |
| Client complexity | Lowest | Medium | Low |
| **Recommendation** | **Public APIs** | **Internal microservices** | **Avoid** |

### Consumer version negotiation

For APIs with diverse consumers migrating at different speeds:

1. Server supports both v1 and v2 simultaneously
2. Default behavior: v1 (backward compatible)
3. Client opts into v2 via path or Accept header
4. Server tracks per-consumer version usage via API key metadata
5. When v1 usage drops to zero: begin the sunset countdown

## 4. Deprecation Signalling — exact header syntax

Two different RFCs, two different date formats. Getting this wrong means clients'
Structured-Field parsers reject your header.

| Header | Defined by | Value type | Example |
|--------|-----------|-----------|---------|
| `Deprecation` | **RFC 9745** §2.1 | Item Structured Field, **Date** (`@` + Unix seconds, per RFC 9651 §3.3.7) | `Deprecation: @1688169599` |
| `Sunset` | **RFC 8594** | **HTTP-date** (the `IMF-fixdate` form defined in RFC 9110 §5.6.7) | `Sunset: Sun, 30 Jun 2024 23:59:59 GMT` |
| `Link; rel="deprecation"` | RFC 9745 §3 | URI reference to the deprecation/migration docs | `Link: <https://developer.example.com/deprecation>; rel="deprecation"; type="text/html"` |

```
Deprecation: @1688169599
Sunset: Sun, 30 Jun 2024 23:59:59 GMT
Link: <https://developer.example.com/deprecation>; rel="deprecation"; type="text/html"
Link: </api/v2/users>; rel="successor-version"
```

Constraints that are actually normative:

- `Deprecation` is **not a boolean**. `Deprecation: true` is invalid syntax under RFC 9745
  and predates the standard; a compliant Structured Fields parser fails on it.
- The `Deprecation` date **may be in the future** (will be deprecated then) or in the past
  (was deprecated then).
- `Sunset` **MUST NOT be earlier than** `Deprecation` (RFC 9745 §4).
- Deprecation alone **does not change resource behaviour** (RFC 9745 §5) — the endpoint
  keeps working identically until the sunset date. Do not start degrading responses.
- `Sunset` may be absent: deprecating without committing to a removal date is valid.
- The zone literal in `Sunset` **must be `GMT`, not `UTC`**. RFC 9110 §5.6.7 defines
  `IMF-fixdate = day-name "," SP date1 SP time-of-day SP GMT` with `GMT = %s"GMT"`, and
  requires senders to generate that form. Note that **RFC 9745 §4's own example prints
  `... 23:59:59 UTC`** — that example is non-conformant with the ABNF it inherits, and
  RFC 8594's examples correctly use `GMT`. Follow the ABNF, not the illustration.

## 5. Deprecation Protocol

```
Phase 1: Announce
  - Deprecation header (RFC 9745 Date), optional Sunset header (RFC 8594 HTTP-date)
  - Link; rel="deprecation" to the migration guide
  - Update docs and changelog

Phase 2: Monitor
  - Track calls to deprecated endpoints/fields per consumer
  - Notify active consumers directly — headers alone are not a notification

Phase 3: Sunset
  - Prefer 410 Gone for removed endpoints — it says "was here, deliberately gone" where
    404 says only "not here". 404 stays conformant; this is a [D] convention, not a rule
  - Log attempts for forensics
  - Keep the 410 response in place well past the sunset date
```

### Deprecation window length — [C] contextual

There is no standard window. **6 months public / 3 months internal is a starting default,
not a rule.** The binding requirement is that the window is *agreed with identified
consumers and published*. Size it from evidence:

| Input | Effect on window |
|-------|-----------------|
| Consumer release cadence (mobile app store review, quarterly enterprise releases) | The window must exceed at least one full consumer release cycle |
| Number of consumers and whether they are reachable | Unreachable/anonymous public consumers → longer |
| Contractual or regulatory notice periods | Hard floor, overrides any default |
| Migration effort (mechanical rename vs re-architecture) | Larger effort → longer |

A 2-week window for a single internal caller you can page is fine. A 6-month window for
an unreachable public API may be too short.

## 6. Multi-Version Coexistence Pattern

When a breaking change is necessary, run both versions simultaneously:

```
/api/v1/users  ← deprecated, with Deprecation + Sunset + Link headers
/api/v2/users  ← current, new contract
```

Every v1 endpoint returns the deprecation headers via middleware. Lifecycle: launch v2 →
add deprecation headers to v1 → monitor v1 usage → notify consumers → after the sunset
date, v1 returns 410 Gone.

---

## 7. API Contract Testing Strategy

Automate breaking change detection in CI:

1. Maintain a baseline OpenAPI spec (`openapi.baseline.json`)
2. On every PR: generate the new spec, diff against the baseline
3. Detect: removed paths, removed fields, changed types, new required fields
4. Block merge if a breaking change is detected without a version bump

Checks worth automating, with the force each one deserves:

| Check | Force | Note |
|-------|:-----:|------|
| No paths removed | [P] | Hard gate |
| No response fields removed or renamed | [P] | Hard gate |
| No field type changes | [P] | Hard gate |
| No new required request fields | [P] | Hard gate |
| Error responses use non-2xx status + stable `code` | [P] | Hard gate |
| `Idempotency-Key` accepted on replay-unsafe POSTs | [C] | Gate only endpoints matching T1–T3 (money, quota, irreversible side effect). Gating *all* POSTs generates noise on append-only endpoints |
| `If-Match` supported on PUT/PATCH | [C] | Gate only resources with real multi-writer contention (T4). A single-writer config API may document last-write-wins instead |
| Field order unchanged | — | **Do not gate this.** Key order is not part of the JSON contract (§2.1). Gate the digest instead, if a signature covers the body |

---

## 8. Compatibility Checklist

Before deploying any API change:

- [ ] Change classified as breaking or non-breaking, with evidence for edge cases (§2.1)
- [ ] If breaking: migration plan documented
- [ ] If breaking: deprecation window set with identified consumers, and signalled with
      correctly-typed `Deprecation` / `Sunset` headers (§4)
- [ ] If breaking: affected consumers identified and notified directly
- [ ] OpenAPI spec updated to reflect the change
- [ ] Contract test baseline updated
- [ ] Changelog entry written
