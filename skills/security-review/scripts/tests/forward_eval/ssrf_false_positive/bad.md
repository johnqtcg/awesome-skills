**mode**: `review`
**data_basis**: source code
**active_verification**: not_permitted

## 1) Findings

> **SEC-001: SSRF — user-controlled input reaches an outbound HTTP request**
>
> - **Severity**: P1 High
> - **Confidence**: confirmed
> - **Mapping**: CWE-918 / ASVS 4.0.3 V5.2.6
> - **File/line**: `FetchPartnerData`, `resp, err := http.Get(endpoint)`
> - **Exploit path**: `partnerID` is taken from `r.URL.Query().Get("partner")` — attacker-controlled
>   input — and flows into `http.Get`. There is no IP validation, no `CheckRedirect`, and no
>   `Dialer.Control` guard, so an attacker can reach internal services such as
>   `http://169.254.169.254/`.
> - **Impact**: full SSRF; cloud credential theft via the instance metadata service.
> - **Recommended fix**: validate the resolved IP at connect time and refuse redirects.
> - **Baseline status**: new
> - **Origin**: pre-existing

Also note `io.Copy(w, resp.Body)` has no size limit — P2.

## Scorecard

- Findings reported: 2

```json
{
  "summary": { "pass": false },
  "counts": { "p0": 0, "p1": 1, "p2": 1, "p3": 0 },
  "stack": "go",
  "asvs_version": "4.0.3",
  "active_verification": "not_permitted",
  "security_domains": { "required": true, "total": 10, "pass": 8, "fail": 2, "na": 0 },
  "findings": [
    {
      "id": "SEC-001", "severity": "P1", "confidence": "confirmed", "status": "new",
      "cwe": "CWE-918", "asvs": "ASVS 4.0.3 V5.2.6", "file": "handler.go:FetchPartnerData"
    }
  ]
}
```
