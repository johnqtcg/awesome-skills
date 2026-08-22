```
Active verification: NOT permitted
Target: none
Basis: static review
```

Stack detected: `python`.

## 1) Findings

> **SEC-001: XXE — arbitrary file read via `ET.fromstring` on the request body**
>
> - **Severity**: P1 High
> - **Confidence**: confirmed
> - **Mapping**: CWE-611 (Improper Restriction of XML External Entity Reference) /
>   ASVS 4.0.3 V5.5.2
> - **File/line**: `import_invoice` — `root = ET.fromstring(body)`
> - **Exploit path**: stdlib XML parsers honour DTDs, so an attacker posts
>   `<!DOCTYPE d [<!ENTITY x SYSTEM "file:///etc/passwd">]><invoice>&x;</invoice>` and the entity
>   is expanded into the tree. The response then leaks the file contents.
> - **Impact**: arbitrary local file read, and SSRF via an external DTD URL.
> - **Recommended fix**: replace `xml.etree.ElementTree` with `defusedxml`.
> - **Baseline status**: new
> - **Origin**: introduced

> **SEC-002: Billion-laughs denial of service via entity expansion**
>
> - **Severity**: P2 Medium
> - **Confidence**: confirmed
> - **Mapping**: CWE-776 / ASVS 4.0.3 V5 (chapter-level)
> - **File/line**: same call site
> - **Exploit path**: internal entity expansion is performed by Expat, so amplification DoS is
>   real — a nested-entity payload expands without bound and exhausts memory.
> - **Recommended fix**: use `defusedxml`, which forbids entity expansion.
> - **Baseline status**: new
> - **Origin**: introduced

## 2) Security Domain Coverage — stack: python

| # | Domain | Verdict | Evidence |
|---|--------|---------|----------|
| 1 | Randomness Safety | N/A | none |
| 2 | Injection & Data-Access Safety | N/A | none |
| 3 | Sensitive Data Handling | Applicable / **FAIL** | file disclosure via SEC-001 |
| 4 | Secret / Config Management | N/A | none |
| 5 | Transport Security | N/A | none |
| 6 | Crypto Primitive Correctness | N/A | none |
| 7 | Concurrency & Shared-State Safety | N/A | none |
| 8 | Language-Specific Injection Sinks | Applicable / **FAIL** | SEC-001, SEC-002 |
| 9 | Static Scanner Posture | N/A | none |
| 10 | Dependency Vulnerability Posture | N/A | none |

## 3) Automation Evidence

None.

## 9) Uncovered Risk List

None.

```json
{
  "summary": { "pass": false, "baseline": "absent" },
  "counts": { "p0": 0, "p1": 1, "p2": 1, "p3": 0, "overflow": 0 },
  "stack": "python",
  "asvs_version": "4.0.3",
  "active_verification": "not_permitted",
  "security_domains": { "required": true, "total": 10, "pass": 0, "fail": 2, "na": 8 },
  "findings": [
    {
      "id": "SEC-001", "severity": "P1", "confidence": "confirmed", "status": "new",
      "origin": "introduced", "cwe": "CWE-611", "asvs": "ASVS 4.0.3 V5.5.2",
      "domain": 8, "file": "app/invoices.py:import_invoice"
    },
    {
      "id": "SEC-002", "severity": "P2", "confidence": "confirmed", "status": "new",
      "origin": "introduced", "cwe": "CWE-776", "asvs": "ASVS 4.0.3 V5 (chapter-level)",
      "domain": 8, "file": "app/invoices.py:import_invoice"
    }
  ]
}
```
