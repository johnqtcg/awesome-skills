```
Active verification: NOT permitted
Target: none
Basis: static review
```

Stack detected: `java`.

## 1) Findings

> **SEC-001: XXE — external entity injection in `InvoiceParser.parse`**
>
> - **Severity**: P1 High
> - **Confidence**: confirmed
> - **Mapping**: CWE-611 (Improper Restriction of XML External Entity Reference) /
>   ASVS 4.0.3 V5.5.2
> - **File/line**: `InvoiceParser.parse` — `newDocumentBuilder().parse(untrusted)`
> - **Exploit path**: `DocumentBuilderFactory` resolves external entities by default in Java. An
>   attacker submits `<!DOCTYPE d [<!ENTITY x SYSTEM "file:///etc/passwd">]><invoice>&x;</invoice>`
>   and the parser inlines the file contents into the document, which the caller then reads.
> - **Impact**: arbitrary local file read and SSRF via external DTD fetch.
> - **Recommended fix**: use `defusedxml`-equivalent hardening — set
>   `disallow-doctype-decl` to `true` and disable external entity resolution on the factory.
> - **Baseline status**: new
> - **Origin**: pre-existing

## 2) Security Domain Coverage — stack: java

| # | Domain | Verdict | Evidence |
|---|--------|---------|----------|
| 1 | Randomness Safety | N/A | none |
| 2 | Injection & Data-Access Safety | N/A | none |
| 3 | Sensitive Data Handling | Applicable / **FAIL** | file disclosure via SEC-001 |
| 4 | Secret / Config Management | N/A | none |
| 5 | Transport Security | N/A | none |
| 6 | Crypto Primitive Correctness | N/A | none |
| 7 | Concurrency & Shared-State Safety | N/A | none |
| 8 | Language-Specific Injection Sinks | Applicable / **FAIL** | SEC-001 |
| 9 | Static Scanner Posture | N/A | none |
| 10 | Dependency Vulnerability Posture | N/A | none |

## 3) Automation Evidence

None.

## 9) Uncovered Risk List

None.

```json
{
  "summary": { "pass": false, "baseline": "absent" },
  "counts": { "p0": 0, "p1": 1, "p2": 0, "p3": 0, "overflow": 0 },
  "stack": "java",
  "asvs_version": "4.0.3",
  "active_verification": "not_permitted",
  "security_domains": { "required": true, "total": 10, "pass": 0, "fail": 2, "na": 8 },
  "findings": [
    {
      "id": "SEC-001", "severity": "P1", "confidence": "confirmed", "status": "new",
      "origin": "pre-existing", "cwe": "CWE-611", "asvs": "ASVS 4.0.3 V5.5.2",
      "domain": 8, "file": "parse/InvoiceParser.java:parse"
    }
  ]
}
```
