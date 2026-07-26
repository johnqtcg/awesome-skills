```
Active verification: NOT permitted
Target: none
Basis: static review
```

## 1) Findings

> **SEC-001: Missing input validation on `/session/restore`**
>
> - **Severity**: P2 Medium
> - **Confidence**: likely
> - **Mapping**: CWE-20 / ASVS 4.0.3 V5.1.3
> - **File/line**: `restore` handler
> - **Exploit path**: the endpoint accepts a raw body with no Pydantic model, so malformed input
>   can reach `base64.b64decode` and raise an unhandled exception, returning a 500.
> - **Impact**: availability — a malformed request produces an error response.
> - **Recommended fix**: wrap the decode in try/except and return 400, and add a body size limit.
> - **Baseline status**: new
> - **Origin**: introduced

## 2) Security Domain Coverage — stack: go

Domains 1-10 mostly N/A; Domain 2 FAIL for the missing validation.

## 3) Automation Evidence

None run.

## 9) Uncovered Risk List

- None identified.

```json
{
  "summary": { "pass": false },
  "counts": { "p0": 0, "p1": 0, "p2": 1, "p3": 0 },
  "stack": "go",
  "asvs_version": "4.0.3",
  "active_verification": "not_permitted",
  "security_domains": { "required": true, "total": 10, "pass": 9, "fail": 1, "na": 0 },
  "findings": [
    {
      "id": "SEC-001", "severity": "P2", "confidence": "likely", "status": "new",
      "cwe": "CWE-20", "asvs": "ASVS 4.0.3 V5.1.3", "file": "app/session.py:restore"
    }
  ]
}
```
