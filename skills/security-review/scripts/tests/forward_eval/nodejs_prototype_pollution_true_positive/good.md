```
Active verification: NOT permitted
Target: none
Basis: no authorized target was provided; static source review only
```

Review depth: Standard (new endpoint, untrusted object merged into application state).
Stack detected: `nodejs` (Express) — Gate D evaluated against the same ten domains.

## 1) Findings

> **SEC-001: Prototype pollution via recursive merge of the request body**
>
> - **Severity**: P1 High
> - **Confidence**: confirmed — the path from request body to `Object.prototype` is complete and
>   unconditional
> - **Mapping**: CWE-1321 (Improperly Controlled Modification of Object Prototype Attributes) /
>   ASVS 4.0.3 V5 (chapter-level — Validation, Sanitization and Encoding; no 4.0.3 requirement
>   names prototype pollution specifically, so precision is not claimed)
> - **File/line**: `merge(target, source)` called as `merge({}, req.body)` in the
>   `POST /settings` handler
> - **Domain**: 8 — Language-Specific Injection Sinks
> - **Exploit path**: `express.json()` produces a plain object, and `__proto__` **is** an own
>   enumerable property on it, so `Object.keys(source)` yields it. The recursion then evaluates
>   `target["__proto__"]`, which resolves to `Object.prototype`, and assigns attacker-chosen keys
>   onto it. A body of `{"__proto__": {"isAdmin": true}}` makes `({}).isAdmin === true` for the
>   remainder of the process lifetime.
> - **Impact**: any later `if (user.isAdmin)`-shaped check on an object that does not define the
>   key itself now reads the polluted value — an authorization bypass reachable by one unauth
>   POST, and it persists process-wide rather than per-request. Also a DoS vector by polluting
>   `toString`. Graded P1 rather than P2 because the effect crosses a trust boundary; P0 is
>   withheld only because the impact depends on the shape of downstream reads, which were not
>   in the provided scope.
> - **Reproducer** (NOT executed — active verification not permitted; confirmed statically):
>   ```bash
>   # Local instance only.
>   curl -X POST http://127.0.0.1:3000/settings \
>     -H 'Content-Type: application/json' \
>     -d '{"__proto__":{"polluted":"yes"}}'
>   # Then any subsequent response derived from a fresh object exposes `polluted`
>   ```
> - **Recommended fix**: reject the three dangerous keys and stop recursing into inherited
>   slots. `Object.create(null)` for the accumulator is not sufficient on its own, because the
>   recursion still walks into `target[key]` for nested objects:
>   ```js
>   const BLOCKED = new Set(['__proto__', 'constructor', 'prototype']);
>
>   function merge(target, source) {
>     for (const key of Object.keys(source)) {
>       if (BLOCKED.has(key)) continue;
>       const value = source[key];
>       if (value && typeof value === 'object' && !Array.isArray(value)) {
>         target[key] = merge(Object.create(null), value);
>       } else {
>         target[key] = value;
>       }
>     }
>     return target;
>   }
>   ```
>   Preferably validate the body against a schema (zod/ajv) and merge only known keys.
> - **Regression test**: POST `{"__proto__":{"x":1}}` and assert `({}).x === undefined`
>   afterwards.
> - **Baseline status**: new
> - **Origin**: introduced

## 2) Security Domain Coverage — stack: nodejs

All ten evaluated against their canonical questions.

| # | Domain | Verdict | Evidence |
|---|--------|---------|----------|
| 1 | Randomness Safety | N/A | no token/ID generation in scope |
| 2 | Injection & Data-Access Safety | N/A | no query or command construction |
| 3 | Sensitive Data Handling | Applicable / PASS | handler echoes only what was submitted |
| 4 | Secret / Config Management | N/A | no secrets or config read |
| 5 | Transport Security | N/A | no outbound client in scope |
| 6 | Crypto Primitive Correctness | N/A | no crypto in scope |
| 7 | Concurrency & Shared-State Safety | Applicable / **FAIL** | prototype pollution mutates process-wide shared state — same root cause as SEC-001 |
| 8 | Language-Specific Injection Sinks | Applicable / **FAIL** | recursive merge of untrusted input — SEC-001 |
| 9 | Static Scanner Posture | Applicable / FAIL | no evidence `eslint-plugin-security` runs in CI |
| 10 | Dependency Vulnerability Posture | N/A | no dependency change in this diff |

## 3) Automation Evidence

None executed — static review only, and no authorization for active verification.
`npm audit --omit=dev` and `eslint --plugin security` are the commands that would give Domains 9
and 10 standing evidence; not run here.

## 4) Open questions / assumptions

- Assumes `POST /settings` is reachable unauthenticated; no auth middleware was in scope. An
  auth gate narrows exposure but does not change the class, since the pollution is persistent.
- Downstream reads of the polluted keys were not provided, which is why impact is stated as
  conditional on their shape.

## 5) Risk Acceptance Register

None recorded. A P1 requires tech-lead-level sign-off.

## 6) Remediation Plan

- **Immediate**: block `__proto__`/`constructor`/`prototype` in `merge`, or replace it with
  schema-validated field copying.
- **Short-term**: grep for other recursive merges and for `lodash.merge`/`Object.assign` on
  request-derived objects.
- **Backlog**: add `eslint-plugin-security` to CI.

## 8) Hardening suggestions

- Add `express.json({ limit: '100kb' })`; the handler currently accepts an unbounded body.

## 9) Uncovered Risk List

- Did not inspect the rest of the router, so other merge call sites may share the defect. Not
  covered because only this handler was provided.
- No dependency audit run; a vulnerable transitive package could add further exposure.

```json
{
  "summary": { "pass": false, "baseline": "absent" },
  "counts": { "p0": 0, "p1": 1, "p2": 0, "p3": 0, "overflow": 0 },
  "stack": "nodejs",
  "asvs_version": "4.0.3",
  "active_verification": "not_permitted",
  "security_domains": { "required": true, "total": 10, "pass": 1, "fail": 3, "na": 6 },
  "findings": [
    {
      "id": "SEC-001", "severity": "P1", "confidence": "confirmed", "status": "new",
      "origin": "introduced", "cwe": "CWE-1321", "asvs": "ASVS 4.0.3 V5 (chapter-level)",
      "domain": 8, "file": "routes/settings.js:merge"
    }
  ]
}
```
