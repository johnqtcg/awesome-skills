# API Compatibility Rules

Backward compatibility determines whether existing clients break when the API changes.
Every API change must be classified before deployment.

---

## 1. Non-Breaking Changes (Safe to deploy)

| Change | Why safe |
|--------|----------|
| Add new optional field to response | Clients should ignore unknown fields |
| Add new optional query parameter | Existing requests don't include it |
| Add new endpoint | No existing client calls it |
| Add new enum value (if clients ignore unknown) | Only safe if documented |
| Add new HTTP header | Clients ignore unknown headers |
| Relax validation (accept wider input) | Existing valid input still valid |
| Increase rate limit | Clients can only benefit |

## 2. Breaking Changes (Require migration plan)

| Change | Why breaking | Mitigation |
|--------|-------------|------------|
| Remove response field | Clients reading it get null/error | Deprecate first, remove after sunset |
| Rename response field | Same as removal for old name | Add new field, deprecate old |
| Change field type | JSON parsing breaks | New field with new type |
| Add required request field | Existing requests missing it → 422 | Make optional first, require later |
| Tighten validation | Previously valid input rejected | Announce, grace period |
| Change status code semantics | Client error handling breaks | Version bump |
| Change URL structure | Existing client URLs break | Redirect + version bump |
| Change auth requirements | Existing tokens/keys rejected | Grace period + migration guide |
| Remove endpoint | Clients get 404 | Deprecate → sunset → remove |
| Change error code values | Client error handling breaks | Version bump |

## 3. Versioning Strategy

### Path versioning (recommended for public APIs)

```
/api/v1/users    ← current stable
/api/v2/users    ← new version with breaking changes
```

- Simple, visible, cacheable
- At most 2 active major versions
- Old version gets security fixes only during sunset period

### Header versioning (for internal APIs)

```
Accept: application/vnd.myapi.v2+json
```

- Cleaner URLs but harder to test in browser
- Suitable for service-to-service where clients control headers

### Query parameter versioning (not recommended)

```
/api/users?version=2
```

- Pollutes query space, confuses caching
- Avoid unless legacy constraint requires it

### Versioning strategy selection matrix

| Criterion | Path (`/v1/`) | Header (`Accept: vnd.v2`) | Query (`?v=2`) |
|-----------|:---:|:---:|:---:|
| Visibility in URL | Yes | No | Partial |
| Browser/curl testability | Easy | Requires custom headers | Easy |
| CDN/proxy caching | Clean cache key | Varies by CDN config | Pollutes cache key |
| API Gateway routing | Native support | Requires header inspection | Fragile |
| Client complexity | Lowest | Medium | Low |
| **Recommendation** | **Public APIs** | **Internal microservices** | **Avoid** |

### Sunset header HTTP format

```
Sunset: Sat, 01 Mar 2025 00:00:00 GMT
```

- Format: RFC 7231 HTTP-date (not ISO-8601)
- Must be a future date when first set
- Clients should parse and alert when `Sunset` < 30 days from now

### Consumer version negotiation

For APIs with diverse consumers migrating at different speeds:

1. Server supports both v1 and v2 simultaneously
2. Default behavior: v1 (backward compatible)
3. Client opts into v2 via path or Accept header
4. Server tracks per-consumer version usage via API key metadata
5. When v1 usage drops to zero: begin sunset countdown

## 4. Deprecation Protocol

```
Phase 1: Announce deprecation
  - Add Deprecation header: Deprecation: true
  - Add Sunset header: Sunset: Sat, 01 Mar 2025 00:00:00 GMT
  - Update docs with migration guide
  - Minimum window: 6 months for public, 3 months for internal

Phase 2: Monitor usage
  - Track calls to deprecated endpoints/fields
  - Notify active consumers directly

Phase 3: Sunset
  - Return 410 Gone (not 404) for removed endpoints
  - Log attempts for forensics
  - Keep 410 response for 3+ months after sunset
```

## 5. Multi-Version Coexistence Pattern

When a breaking change is necessary, run both versions simultaneously:

```
/api/v1/users  ← deprecated, with Deprecation + Sunset + Link headers
/api/v2/users  ← current, new contract
```

Every v1 endpoint returns deprecation headers via middleware:
```
Deprecation: true
Sunset: Sat, 01 Mar 2025 00:00:00 GMT
Link: </api/v2/users>; rel="successor-version"
```

Lifecycle: launch v2 → add deprecation headers to v1 → monitor v1 usage → notify consumers → after sunset date: v1 returns 410 Gone.

---

## 6. API Contract Testing Strategy

Automate breaking change detection in CI:

1. Maintain baseline OpenAPI spec (`openapi.baseline.json`)
2. On every PR: generate new spec, diff against baseline
3. Detect: removed paths, removed fields, changed types, new required fields
4. Block merge if breaking change detected without version bump

Checks to automate:
- No paths removed
- No response fields removed or renamed
- No field type changes
- Idempotency-Key required on all POST mutations
- If-Match required on all PUT/PATCH

---

## 7. Compatibility Checklist

Before deploying any API change:

- [ ] Change classified as breaking or non-breaking
- [ ] If breaking: migration plan documented
- [ ] If breaking: deprecation timeline set (with Sunset header)
- [ ] If breaking: affected consumers identified and notified
- [ ] OpenAPI spec updated to reflect change
- [ ] Contract test baseline updated
- [ ] Changelog entry written