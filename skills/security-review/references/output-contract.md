# Security Review — Output Contract (§1-§9 detail)

> **Normative.** This is the section-by-section definition of the report SKILL.md § Output
> Contract requires. It was split out of SKILL.md so the contract can grow without competing
> with the review process for the same line budget — the depth matrix (which section is
> MUST/SHOULD/MAY at Lite/Standard/Deep) stays in SKILL.md because it drives execution, while
> the field-level detail lives here.
>
> Load this when writing the report. The machine-checkable shape of § 7 is
> `report-schema.json`; field semantics are in `authorization-and-policy.md` § 2.

### 1) Findings (P0 -> P3)

Each finding includes: Title · Severity · Confidence (`confirmed/likely/suspected`) ·
Mapping (`CWE` / version-pinned `ASVS`) · File/line · Exploit path · Impact ·
Minimal reproducer · Recommended fix · Suggested regression/negative test ·
Baseline status (`new/regressed/unchanged`) · Origin (`introduced | pre-existing | uncertain`).

The reproducer is required for confirmed P0/P1, but may be **unexecuted instructions** when
active verification is not authorized — label it as such; never fake execution.

→ Fully worked finding (IDOR, all fields populated, unexecuted reproducer, 404-not-403 fix):
`references/security-review.md` §One-Shot Finding Example.

#### Finding Volume Cap

P0/P1 findings are never dropped by volume cap — they are always fully reported. P2/P3 soft cap by depth:
Lite ≤ 3, Standard ≤ 5, Deep ≤ 8 *detailed* findings. **Overflow goes to a `Condensed Findings`
subsection of §1 — never to §9** — one line each (`ID — severity — title — file:line`), with
`counts.overflow` set in the JSON.

**§1 and §9 are disjoint.** §9 means *"scope I did not inspect"*; a confirmed P2 is the opposite.
Filing findings there corrupts the section readers use to judge coverage. The cap limits
**detail**, not disclosure. → `references/authorization-and-policy.md` §4.

### 2) Security Domain Coverage (Required for every stack)

Header must name the stack, e.g. `Security Domain Coverage — stack: nodejs`.

- Domains 1..10 with `PASS/FAIL/N/A`
- Applicability per domain (`Applicable` or `N/A` with reason)
- One-line evidence per domain (deep evidence required only for `Applicable` domains)
- Total `PASS` count and key failed domains

### 3) Automation Evidence

- Command list actually executed
- Key outputs (short)
- Tools skipped/unavailable and reason (including `N/A` applicability skips)

### 4) Open questions / assumptions

### 5) Risk Acceptance Register

P0 findings MUST NOT be accepted without VP-level or equivalent sign-off; record the approver explicitly. P1 findings require tech-lead-level sign-off.

For each accepted risk entry:

- Finding ID
- Reason for acceptance
- Compensating controls
- Approver (name and role)
- Owner
- Expiry/review date

### 6) Remediation Plan

- Immediate
- Short-term
- Backlog

### 7) Machine-Readable Summary (JSON)

Also output a compact JSON block for CI/inbox ingestion. The normative shape is
`references/report-schema.json` (JSON Schema 2020-12) — validate against it rather than
copying this example by eye:

```json
{
  "summary": { "pass": false, "baseline": "present" },
  "counts": { "p0": 0, "p1": 1, "p2": 0, "p3": 0, "overflow": 0 },
  "changes": { "new": 1, "regressed": 0, "unchanged": 0, "resolved": 0 },
  "stack": "go",
  "asvs_version": "4.0.3",
  "active_verification": "not_permitted",
  "security_domains": { "required": true, "total": 10, "pass": 7, "fail": 2, "na": 1 },
  "findings": [
    {
      "id": "SEC-001", "severity": "P1", "confidence": "confirmed", "status": "new",
      "origin": "introduced", "cwe": "CWE-639", "asvs": "ASVS 4.0.3 V4.1.2",
      "file": "internal/handler/account.go:88"
    }
  ],
  "suppressed": [
    {
      "candidate": "SSRF via the outbound webhook call",
      "rule": 2,
      "residual_risk": "holds while the destination stays a server-side allowlist constant"
    }
  ]
}
```

`security_domains` uses the same key for every stack — a consumer must never branch on language
to read the result (there is no `go_domains` key). `stack` may be a comma-joined list;
`active_verification` mirrors the authorization gate so CI can tell whether findings were
established statically or dynamically.

**`summary.pass` is computed, not judged**: `false` when `counts.p0 > 0` **or** `counts.p1 > 0`
**or** `security_domains.fail > 0`; `true` otherwise. A §5 Risk Acceptance Register entry does
**not** flip it back to `true`. Emit no key the schema does not define — an undefined field is
read differently by every consumer.
→ Semantics of `baseline`, `overflow`, `domain`, `suppressed[]`, and multi-stack `per_stack`:
`authorization-and-policy.md` §2.

### 8) Hardening suggestions

### 9) Uncovered Risk List (Mandatory)

