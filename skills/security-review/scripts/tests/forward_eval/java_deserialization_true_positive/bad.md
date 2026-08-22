```
Active verification: NOT permitted
Target: none
Basis: static review
```

Stack detected: `java`.

## 1) Findings

> **SEC-001: Missing input validation on the session-restore endpoint**
>
> - **Severity**: P2 Medium
> - **Confidence**: likely
> - **Mapping**: CWE-20 (Improper Input Validation) / ASVS 4.0.3 V5.1.3
> - **File/line**: `SessionController.restore`
> - **Analysis**: the endpoint accepts a raw `byte[]` and deserializes it. The cast to
>   `SessionState` means only a `SessionState` can come back, so the type is constrained — a
>   wrong payload just throws `ClassCastException`. The resource is also correctly closed with
>   try-with-resources. The remaining gap is that malformed input produces a 500 rather than a
>   400, and there is no size limit on the body.
> - **Recommended fix**: wrap in a try/catch and return 400 on `ClassCastException`; add a
>   `@RequestBody` size limit.
> - **Baseline status**: new
> - **Origin**: introduced

## 2) Security Domain Coverage — stack: java

| # | Domain | Verdict | Evidence |
|---|--------|---------|----------|
| 1 | Randomness Safety | N/A | none |
| 2 | Injection & Data-Access Safety | Applicable / **FAIL** | unvalidated body — SEC-001 |
| 3 | Sensitive Data Handling | N/A | none |
| 4 | Secret / Config Management | N/A | none |
| 5 | Transport Security | N/A | none |
| 6 | Crypto Primitive Correctness | N/A | none |
| 7 | Concurrency & Shared-State Safety | Applicable / PASS | stateless controller |
| 8 | Language-Specific Injection Sinks | Applicable / PASS | the cast constrains the deserialized type |
| 9 | Static Scanner Posture | N/A | none |
| 10 | Dependency Vulnerability Posture | N/A | none |

## 3) Automation Evidence

None.

## 9) Uncovered Risk List

None.

```json
{
  "summary": { "pass": false, "baseline": "absent" },
  "counts": { "p0": 0, "p1": 0, "p2": 1, "p3": 0, "overflow": 0 },
  "stack": "java",
  "asvs_version": "4.0.3",
  "active_verification": "not_permitted",
  "security_domains": { "required": true, "total": 10, "pass": 2, "fail": 1, "na": 7 },
  "findings": [
    {
      "id": "SEC-001", "severity": "P2", "confidence": "likely", "status": "new",
      "origin": "introduced", "cwe": "CWE-20", "asvs": "ASVS 4.0.3 V5.1.3",
      "domain": 2, "file": "web/SessionController.java:restore"
    }
  ]
}
```
