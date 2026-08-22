```
Active verification: NOT permitted
Target: none
Basis: no authorized target was provided; static source review only
```

Review depth: Standard (untrusted XML reaches a parser).
Stack detected: `java` (Spring) — Gate D evaluated against the same ten domains.

## 1) Findings

No findings. One candidate was examined and **suppressed**; it is recorded below rather than
omitted, so the reader can tell "examined and ruled out" from "never looked at".

**Suppressed candidate — XXE in `InvoiceParser.parse`**

- **Candidate class**: XML External Entity injection (CWE-611) —
  `DocumentBuilderFactory` parsing an untrusted `InputStream`.
- **Why it looks like a finding**: in Java this is a real default. `DocumentBuilderFactory`,
  `SAXParserFactory` and `TransformerFactory` resolve external entities out of the box, so
  "DocumentBuilderFactory + untrusted input" is normally a confirmed XXE — unlike Go's
  `encoding/xml`, which resolves no DTD entities at all, and unlike Python's stdlib, where Expat
  resolves no external entity without a handler. The Java exemption does **not** come for free,
  which is exactly why this call site must be read rather than pattern-matched.
- **Why it is not exploitable — Suppression Rule 3** (sink is parameterized / safely encoded by
  framework guarantees): every parser is built by `hardenedFactory()`, which sets
  `disallow-doctype-decl = true`. That is the decisive control: the parser rejects the `DOCTYPE`
  declaration itself with a `SAXParseException`, so there is no place to declare an entity —
  external **or** internal. It therefore closes external-entity file read, external-DTD SSRF, and
  billion-laughs expansion in one flag, and it subsumes the other three settings, which remain
  correct defence in depth:
  - `FEATURE_SECURE_PROCESSING = true` — bounds entity expansion and disables risky extensions.
  - `setXIncludeAware(false)` — blocks `xi:include`, a separate file-read path that DTD flags
    do not cover.
  - `setExpandEntityReferences(false)` — redundant once DOCTYPE is refused.
- **Reachability check**: `parse()` cannot bypass the hardening, because the factory is
  constructed inside `hardenedFactory()` on every call and no setter is exposed. There is no
  path that produces an unhardened `DocumentBuilder` from this class — the class is `final` and
  the factory method is `private`.
- **Residual risk** (stated, not waved away): the suppression rests on `hardenedFactory()` being
  the only source of parsers in this class, which holds today because it is `private` in a
  `final` class. It does not extend to other classes: any other `DocumentBuilderFactory`,
  `SAXParserFactory`, `XMLInputFactory`, `SchemaFactory` or `TransformerFactory` in the codebase
  is unhardened until shown otherwise, and this review covered only the class provided.
  `setFeature` also throws `ParserConfigurationException` on a parser that does not know the
  Apache feature name; the declared `throws` propagates it, so a parser swap fails closed rather
  than silently unhardened — worth keeping.
- **Recorded as**: suppressed, not a finding.

## 2) Security Domain Coverage — stack: java

| # | Domain | Verdict | Evidence |
|---|--------|---------|----------|
| 1 | Randomness Safety | N/A | no token/ID generation in scope |
| 2 | Injection & Data-Access Safety | Applicable / PASS | no SQL/command construction; the `InputStream` is owned by the caller |
| 3 | Sensitive Data Handling | Applicable / PASS | returns a `Document`; no logging of payload contents |
| 4 | Secret / Config Management | N/A | no secrets or config read |
| 5 | Transport Security | N/A | no outbound client; network entity fetch is refused by the DOCTYPE ban |
| 6 | Crypto Primitive Correctness | N/A | no crypto in scope |
| 7 | Concurrency & Shared-State Safety | Applicable / PASS | a new factory and builder per call; `DocumentBuilder` is not shared, which is the correct pattern since it is not thread-safe |
| 8 | Language-Specific Injection Sinks | Applicable / PASS | XXE closed at the parser via `disallow-doctype-decl`; no deserialization, SpEL, or expression evaluation in scope |
| 9 | Static Scanner Posture | Applicable / FAIL | find-sec-bugs would need to run to confirm no other unhardened factory exists — see residual risk |
| 10 | Dependency Vulnerability Posture | N/A | no dependency change in this diff |

## 3) Automation Evidence

None executed — static review only, and no authorization for active verification.
The command that would settle Domain 9 and the residual risk above, not run here:
`mvn spotbugs:check -Dspotbugs.plugins=com.h3xstream.findsecbugs:findsecbugs-plugin`, plus
`rg -n "DocumentBuilderFactory|SAXParserFactory|TransformerFactory|XMLInputFactory"` to find
sibling parsers.

## 4) Open questions / assumptions

- Assumes the caller closes the `InputStream`; ownership stays with the caller, which is
  consistent with the signature.
- Assumes the runtime uses a Xerces-derived parser that recognises the Apache feature URI. If
  not, `setFeature` throws and the call fails closed rather than parsing unhardened.

## 5) Risk Acceptance Register

No findings, so no accepted risks.

## 6) Remediation Plan

- **Immediate**: none required.
- **Short-term**: sweep for other XML factories and route them through `hardenedFactory()` or an
  equivalent shared helper.
- **Backlog**: add find-sec-bugs to CI so an unhardened factory cannot be introduced silently.

## 8) Hardening suggestions

- Promote `hardenedFactory()` into a shared utility so new parsers inherit the configuration
  instead of re-deriving it.
- Cap the input size before parsing; DOCTYPE refusal stops entity expansion but not a very large
  well-formed document.

## 9) Uncovered Risk List

- Only `InvoiceParser` was provided. Other XML entry points in the service are unassessed and
  are the most likely place for a real XXE to live. Not covered because that code was out of
  scope.
- Schema validation of the parsed document was not reviewed; a structurally valid but
  semantically hostile invoice is a separate concern.

```json
{
  "summary": { "pass": false, "baseline": "absent" },
  "counts": { "p0": 0, "p1": 0, "p2": 0, "p3": 0, "overflow": 0 },
  "stack": "java",
  "asvs_version": "4.0.3",
  "active_verification": "not_permitted",
  "security_domains": { "required": true, "total": 10, "pass": 5, "fail": 1, "na": 4 },
  "findings": [],
  "suppressed": [
    {
      "candidate": "XXE via DocumentBuilderFactory on untrusted InputStream",
      "rule": 3,
      "residual_risk": "scoped to this final class whose only factory is private and hardened; every other XML factory in the codebase is unhardened until shown otherwise"
    }
  ]
}
```
