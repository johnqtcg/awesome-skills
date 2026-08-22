```
Active verification: NOT permitted
Target: none
Basis: no authorized target was provided; static source review only
```

Review depth: Standard (new endpoint, native deserialization of untrusted bytes).
Stack detected: `java` (Spring Boot) — Gate D evaluated against the same ten domains.

## 1) Findings

> **SEC-001: Remote code execution via Java native deserialization of the request body**
>
> - **Severity**: P0 Critical
> - **Confidence**: confirmed — the untrusted-input-to-sink path is complete and unconditional
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
> - **Impact**: remote code execution as the service account — full host compromise, credential
>   and environment theft, lateral movement. P0.
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
>   classes and bounds depth/refs — and treat it as a mitigation, not a fix:
>   ```java
>   in.setObjectInputFilter(ObjectInputFilter.Config.createFilter(
>       "com.example.SessionState;java.lang.String;java.util.List;!*"));
>   ```
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
- Whether a known gadget library is on the classpath is unresolved. This does **not** lower the
  severity: absence of a known chain today is not a control, and the classpath changes with every
  dependency bump.

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
      "domain": 8, "file": "web/SessionController.java:restore"
    }
  ]
}
```
