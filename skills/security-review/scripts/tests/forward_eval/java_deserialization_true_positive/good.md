```
Active verification: NOT permitted
Target: none
Basis: no authorized target was provided; static source review only
```

Review depth: Standard (new endpoint, native deserialization of untrusted bytes).
Stack detected: `java` (Spring Boot) — Gate D evaluated against the same ten domains.

## 1) Findings

> **SEC-001: Unfiltered Java native deserialization of the request body (CWE-502)**
>
> - **Severity**: P0 Critical — unfiltered Java-native deserialization of network input, by
>   class and reachability. The unresolved classpath question below does not move this in
>   either direction.
> - **Confidence**: confirmed — this labels the **path**: `@RequestBody byte[]` reaches
>   `readObject()` unconditionally, proven from the code below. No per-stream filter is set
>   *in the code under review*; a process-wide `jdk.serialFilter` or a Java 17+ filter
>   factory was not in scope, so "unfiltered" is asserted of this class, not of the JVM
>   (see § 4).
> - **Impact basis**: assessed — the maximum consequence (RCE) depends on a gadget chain
>   reachable on the classpath, which was not verified. Severity is unaffected: an
>   unverified *aggravating* condition moves neither the severity nor the confidence,
>   only this axis (SKILL.md § Evidence Confidence).
> - **Mapping**: CWE-502 (Deserialization of Untrusted Data) / ASVS 4.0.3 V5.5.1
> - **File/line**: `SessionController.restore` — `new ObjectInputStream(...).readObject()`
> - **Domain**: 8 — Language-Specific Injection Sinks
> - **Exploit path**: `@RequestBody byte[] body` is attacker-controlled, and
>   `ObjectInputStream.readObject()` reconstructs an arbitrary object graph from it. During
>   reconstruction the JVM invokes `readObject`/`readResolve`/`finalize` on the deserialized
>   types, so a gadget chain present anywhere on the classpath (Commons-Collections,
>   Commons-BeanUtils, Groovy, Spring's own AOP types, and many others) executes before control
>   returns.
> - **Why the cast is not a control**: `(SessionState) in.readObject()` is the mistake that makes
>   this look guarded. The cast is evaluated **after** `readObject` has already built and
>   side-effected the graph — a `ClassCastException` is thrown too late to prevent execution. The
>   `try`-with-resources block is likewise correct resource handling and irrelevant to the
>   vulnerability.
> - **Impact — established here**: `readObject()` reconstructs an arbitrary object graph from
>   attacker bytes. Independent of any known gadget, that already permits instantiation of
>   arbitrary `Serializable` types on the classpath, invocation of their
>   `readObject`/`readResolve`/`validateObject` during reconstruction, and unbounded graph
>   expansion (a self-referential or hash-colliding graph is a DoS with no code execution
>   needed).
> - **Impact — assessed, not demonstrated by this review**: remote code execution as the
>   service account, with full host compromise and lateral movement, **if** a gadget chain is
>   reachable on the classpath. That condition was **not verified here** — see § 4. Stated as
>   assessed per § Evidence Confidence: the label `confirmed` covers the path, not the
>   maximum impact.
> - **What would move the RCE impact from assessed to demonstrated**: (1) `mvn dependency:tree`
>   showing a known-gadget library; (2) the absence of a JEP 290 filter — check
>   `ObjectInputFilter.Config.getSerialFilter()`, the `jdk.serialFilter` system property, and
>   any per-stream filter; (3) with authorization, the reproducer below against a build you
>   control.
> - **Reproducer** (NOT executed — active verification not permitted; confirmed statically):
>   ```bash
>   # Local instance only, against a classpath you control.
>   # Generate a chain matching a gadget library actually present, then:
>   curl -X POST --data-binary @payload.ser \
>     -H 'Content-Type: application/octet-stream' \
>     http://127.0.0.1:8080/session/restore
>   # Expected on the vulnerable build: the gadget's side effect fires before any response
>   ```
>   Build and fire the payload only against an instance you stood up yourself.
> - **Recommended fix**: stop deserializing Java-native bytes from the network. Accept JSON bound
>   to a DTO:
>   ```java
>   public record SessionStateDto(@NotBlank String userId, List<String> cart) {}
>
>   @PostMapping(value = "/session/restore", consumes = MediaType.APPLICATION_JSON_VALUE)
>   public ResponseEntity<String> restore(@Valid @RequestBody SessionStateDto dto) {
>       return ResponseEntity.ok(dto.userId());
>   }
>   ```
>   If a binary format is unavoidable, set a JEP 290 filter that allowlists exactly the expected
>   classes and bounds depth/refs — and treat it as a mitigation, not a fix. **Check the target's
>   Java version before recommending the API**, because the two are not interchangeable:
>   ```java
>   // Java 9+ — java.io.ObjectInputFilter
>   in.setObjectInputFilter(ObjectInputFilter.Config.createFilter(
>       "com.example.SessionState;java.lang.String;java.util.List;!*"));
>   ```
>   On **Java 8** `java.io.ObjectInputFilter` does not exist (verified: `javac` on 1.8.0_461
>   rejects it). There, the equivalents are the `-Djdk.serialFilter=...` system property
>   (8u121+, accepted by that JVM) or the internal
>   `sun.misc.ObjectInputFilter.Config.setObjectInputFilter(stream, filter)` — note the static
>   two-argument form, not a method on the stream, and an internal API that compiles with a
>   proprietary-API warning. Recommending the Java 9 call to an 8 service is advice that will
>   not build.
>   Note Jackson `DefaultTyping` reintroduces the same class if enabled — check it is off.
> - **Regression test**: POST a serialized `java.util.HashMap` and assert the request is rejected
>   before any object is constructed.
> - **Baseline status**: new
> - **Origin**: introduced

## 2) Security Domain Coverage — stack: java

All ten evaluated against their canonical questions.

| # | Domain | Verdict | Evidence |
|---|--------|---------|----------|
| 1 | Randomness Safety | N/A | no token/ID generation in scope |
| 2 | Injection & Data-Access Safety | Applicable / PASS | no SQL/command construction; resources released via try-with-resources |
| 3 | Sensitive Data Handling | Applicable / PASS | response returns only a user id |
| 4 | Secret / Config Management | N/A | no secrets or config read |
| 5 | Transport Security | N/A | no outbound client in scope |
| 6 | Crypto Primitive Correctness | N/A | no crypto in scope |
| 7 | Concurrency & Shared-State Safety | Applicable / PASS | controller holds no mutable state |
| 8 | Language-Specific Injection Sinks | Applicable / **FAIL** | `ObjectInputStream.readObject` on untrusted input — SEC-001 |
| 9 | Static Scanner Posture | Applicable / FAIL | find-sec-bugs would flag this (`OBJECT_DESERIALIZATION`); no evidence it runs in CI |
| 10 | Dependency Vulnerability Posture | Applicable / FAIL | exploitability depends on classpath gadgets and no dependency inventory was provided — unresolved, so recorded as FAIL rather than N/A |

## 3) Automation Evidence

None executed — static review only, and no authorization for active verification.
The commands that would settle Domains 9 and 10, not run here:
`mvn spotbugs:check -Dspotbugs.plugins=com.h3xstream.findsecbugs:findsecbugs-plugin` and
`mvn org.owasp:dependency-check-maven:check`.

## 4) Open questions / assumptions

- Assumes the endpoint is reachable without authentication; no `@PreAuthorize` or filter chain
  was in scope. An authenticated RCE is still P0.
- **Unverified condition, and what it does and does not change.** Whether a known gadget library
  is on the classpath is unresolved: no dependency inventory was provided. This does **not** lower
  the severity — absence of a known chain today is not a control, and the classpath changes with
  every dependency bump — and it does **not** raise it either. What it does change is the
  *impact wording*: the RCE consequence is recorded as assessed rather than demonstrated (see
  SEC-001's two Impact lines). Settle it with `mvn dependency:tree` plus a check of
  `jdk.serialFilter` / `ObjectInputFilter.Config.getSerialFilter()` / any per-stream filter.
- No JEP 290 filter configuration was in scope — neither a per-stream
  `setObjectInputFilter` call, a `jdk.serialFilter` property, nor (Java 17+) a filter factory.
  Absence of evidence is recorded as unresolved, not as absence of a filter.
- Target Java version unknown. It does not affect the finding, but it decides which filter API
  the remediation can name (see the fix above).

## 5) Risk Acceptance Register

A P0 must not be accepted without VP-level or equivalent sign-off. None recorded.

## 6) Remediation Plan

- **Immediate**: replace native deserialization with the JSON DTO above; hotfix.
- **Short-term**: grep for `ObjectInputStream`, `readObject`, `XMLDecoder`, and Jackson
  `enableDefaultTyping`/`activateDefaultTyping` across the service.
- **Backlog**: add find-sec-bugs and dependency-check to CI so Domains 9 and 10 have standing
  evidence.

## 8) Hardening suggestions

- Constrain the endpoint's request size at the container level; `byte[]` binding reads an
  unbounded body.
- Set a process-wide `jdk.serialFilter` as defence in depth.

## 9) Uncovered Risk List

- The rest of the controller package was not provided; other endpoints may deserialize
  similarly. Not covered because only this class was in scope.
- No dependency inventory, so gadget-chain reachability is unassessed — see Domain 10.

```json
{
  "summary": { "pass": false, "baseline": "absent" },
  "counts": { "p0": 1, "p1": 0, "p2": 0, "p3": 0, "overflow": 0 },
  "stack": "java",
  "asvs_version": "4.0.3",
  "active_verification": "not_permitted",
  "security_domains": { "required": true, "total": 10, "pass": 3, "fail": 3, "na": 4 },
  "findings": [
    {
      "id": "SEC-001", "severity": "P0", "confidence": "confirmed", "status": "new",
      "origin": "introduced", "cwe": "CWE-502", "asvs": "ASVS 4.0.3 V5.5.1",
      "domain": 8, "file": "web/SessionController.java:restore",
      "impact_basis": "assessed",
      "impact_condition": "RCE requires a gadget chain reachable on the classpath; not verified — no dependency inventory was provided. Settle with `mvn dependency:tree` plus a check of jdk.serialFilter / ObjectInputFilter.Config.getSerialFilter()."
    }
  ]
}
```
