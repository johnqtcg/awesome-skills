```
Active verification: NOT permitted
Target: none
Basis: no authorized target was provided; static source review only
```

Review depth: Standard (untrusted XML reaches a parser).
Stack detected: `python` (FastAPI) — Gate D evaluated against the same ten domains.

## 1) Findings

No findings. Two candidates were examined and **suppressed**; both are recorded below rather
than omitted, so the reader can tell "examined and ruled out" from "never looked at".

**Suppressed candidate 1 — XXE (external entity → local file read / SSRF)**

- **Candidate class**: XML External Entity injection (CWE-611) — `ET.fromstring` on a raw
  request body.
- **Why it looks like a finding**: untrusted XML reaching a parser is the canonical XXE shape,
  and it *is* a real finding in Java, where `DocumentBuilderFactory` resolves external entities
  by default.
- **Why it is not exploitable — Suppression Rule 3** (the sink is structurally safe by parser
  guarantees): `xml.etree.ElementTree` is backed by Expat, which resolves **no** external entity
  unless the application installs an `ExternalEntityRefHandler`. `ElementTree` installs none, so
  `<!ENTITY x SYSTEM "file:///etc/passwd">` followed by `&x;` fails with
  `ParseError: undefined entity` — the file is never opened, and the external DTD/entity URL is
  never fetched, so the SSRF variant is closed by the same mechanism.
- **Recorded as**: suppressed, not a finding.

**Suppressed candidate 2 — entity-expansion DoS (billion laughs / quadratic blowup)**

- **Candidate class**: uncontrolled resource consumption via entity amplification (CWE-776).
- **Why it looks like a finding**: Expat *does* substitute internal entities — unlike Go's
  `encoding/xml`, which expands none — so "expansion happens" is true and invites the conclusion
  that amplification is reachable. It is not.
- **Why it is not exploitable — Suppression Rule 3**: Expat has limited input amplification since
  **2.4.0** (CVE-2013-0340 / CWE-776): a factor above **100.0** is refused once **8 MiB** of
  expanded output has been produced, raising
  `ParseError: limit on input amplification factor (from DTD and entities) breached`. A real
  billion-laughs and a quadratic blowup are both refused in under 0.1 s. The bounded substitution
  that does succeed (a small nested entity reaching ~1 000 characters) sits *inside* the tolerated
  window — it demonstrates substitution, not a DoS. "Expansion occurred" must not be graded as
  "amplification DoS confirmed".
- **Version basis**: this build reports `expat (2, 7, 1)` via
  `python3 -c "from xml.parsers import expat; print(expat.version_info)"`, which is past the gate.
- **Residual risk** (stated, not waved away): both suppressions are **version-gated, not
  absolute**. They hold for the interpreter checked and stop holding on Expat **< 2.4.0**, or
  **< 2.6.0** built without `XML_DTD` (CVE-2023-52426), or **< 2.6.2** if the application parses
  isolated external entities (CVE-2024-28757). A distro build or a differently configured
  `pyexpat` can also change the answer. If the deployment image's Expat version cannot be
  established, this drops to `likely` rather than a clean suppression — so pin the base image and
  record the version in CI. Separately, the handler reads an unbounded body, so a very large
  well-formed document is still a capacity risk that entity limits do not address.
- **Recorded as**: suppressed, not a finding.

**Hardening, not a finding**: `defusedxml.ElementTree` remains the right recommendation for
untrusted XML — it blocks entity expansion outright and covers every shape above uniformly,
independent of the Expat version. It is listed under §8 rather than as a finding precisely
because the current code is not exploitable.

## 2) Security Domain Coverage — stack: python

| # | Domain | Verdict | Evidence |
|---|--------|---------|----------|
| 1 | Randomness Safety | N/A | no token/ID generation in scope |
| 2 | Injection & Data-Access Safety | N/A | no query or command construction |
| 3 | Sensitive Data Handling | Applicable / PASS | returns a count only; no payload echo, no logging of the body |
| 4 | Secret / Config Management | N/A | no secrets or config read |
| 5 | Transport Security | N/A | no outbound client; external entity fetch is not performed |
| 6 | Crypto Primitive Correctness | N/A | no crypto in scope |
| 7 | Concurrency & Shared-State Safety | Applicable / PASS | handler holds no shared state; parsing is CPU-bound but bounded by the amplification limit |
| 8 | Language-Specific Injection Sinks | Applicable / PASS | XXE not reachable (no external entity resolution); amplification DoS refused by Expat >= 2.4.0; no `eval`/`exec`/`pickle`/`yaml.load` in scope |
| 9 | Static Scanner Posture | Applicable / FAIL | `bandit` flags B314 on `ElementTree.fromstring` by pattern; no evidence it runs in CI, so the triage that would mark it a false positive is not recorded anywhere |
| 10 | Dependency Vulnerability Posture | Applicable / FAIL | the suppressions above depend on the Expat version shipped in the runtime image, and no pin or inventory was provided |

## 3) Automation Evidence

None executed against a live target — static review only, and no authorization for active
verification. Version facts were read from the local interpreter:

- `python3 -c "from xml.parsers import expat; print(expat.version_info)"` → `(2, 7, 1)`

`bandit -r . -ll` and `pip-audit` would give Domains 9 and 10 standing evidence; not run here.

## 4) Open questions / assumptions

- Assumes the deployed runtime ships the same Expat as the reviewed environment. This is the load-
  bearing assumption behind both suppressions, hence the Domain 10 FAIL.
- Assumes no `ExternalEntityRefHandler` is installed elsewhere in the process; none was in scope.

## 5) Risk Acceptance Register

No findings, so no accepted risks.

## 6) Remediation Plan

- **Immediate**: none required for exploitability.
- **Short-term**: pin the runtime base image and assert the Expat version in CI so the
  suppression stays valid; switch to `defusedxml` to make it version-independent.
- **Backlog**: add `bandit` to CI with a documented triage note for B314 at this call site.

## 8) Hardening suggestions

- Use `defusedxml.ElementTree.fromstring` — removes the version dependency entirely.
- Cap the request body (`Content-Length` check or an ASGI limit); the amplification limit does
  not bound a plain large document.

## 9) Uncovered Risk List

- Only this handler was provided; other XML entry points, and any use of `lxml`, are unassessed.
  `lxml` matters specifically because its exposure is gated differently — `iterparse` and
  `ETCompatXMLParser` resolved external entities by default until lxml 6.1.0
  (CVE-2026-41066) — so a suppression valid here does not transfer to an lxml call site.
- The runtime image's Expat version is unverified, which is the one fact both suppressions rest
  on.

```json
{
  "summary": { "pass": false, "baseline": "absent" },
  "counts": { "p0": 0, "p1": 0, "p2": 0, "p3": 0, "overflow": 0 },
  "stack": "python",
  "asvs_version": "4.0.3",
  "active_verification": "not_permitted",
  "security_domains": { "required": true, "total": 10, "pass": 4, "fail": 2, "na": 4 },
  "findings": [],
  "suppressed": [
    {
      "candidate": "XXE external entity file read / SSRF via ET.fromstring",
      "rule": 3,
      "residual_risk": "Expat resolves no external entity without a handler; holds unless the app installs an ExternalEntityRefHandler"
    },
    {
      "candidate": "Entity-expansion DoS (billion laughs) via ET.fromstring",
      "rule": 3,
      "residual_risk": "version-gated on Expat >= 2.4.0 (checked: 2.7.1); real below 2.4.0, or below 2.6.0 built without XML_DTD, or below 2.6.2 with isolated external entities"
    }
  ]
}
```
