```
Active verification: NOT permitted
Target: none
Basis: no authorized target was provided; static source review only
```

Review depth: Standard (new endpoint, deserialization of untrusted input).
Stack detected: `python` (FastAPI) — Gate D evaluated against the same ten domains.

## 1) Findings

> **SEC-001: Remote code execution via `pickle.loads` on the request body**
>
> - **Severity**: P0 Critical
> - **Confidence**: confirmed — the untrusted-input-to-sink path is complete and unconditional
> - **Mapping**: CWE-502 (Deserialization of Untrusted Data) / ASVS 4.0.3 V5.5.1
> - **File/line**: `restore` handler, `state = pickle.loads(base64.b64decode(body))`
> - **Domain**: 8 — Language-Specific Injection Sinks
> - **Exploit path**: the raw POST body is base64-decoded and handed straight to
>   `pickle.loads`. Unpickling is not parsing — the pickle opcode stream can invoke arbitrary
>   callables via `__reduce__`, so a crafted payload executes code in the worker process as soon
>   as it is decoded. No authentication or content check stands between the socket and the sink.
> - **Impact**: full remote code execution as the service account: credential and environment
>   theft, lateral movement, persistence. This is a compromise of the host, not a data bug —
>   hence P0 rather than the P1 usually assigned to injection.
> - **Reproducer** (NOT executed — active verification not permitted; confirmed statically):
>   ```bash
>   # Local instance only. Payload constructed with a __reduce__ that runs a benign marker.
>   curl -X POST --data-binary @payload.b64 http://127.0.0.1:8000/session/restore
>   # Expected on the vulnerable build: the marker side effect occurs before any response
>   ```
>   Construct the payload only against a local instance you control; do not point this at
>   shared infrastructure.
> - **Recommended fix**: never unpickle untrusted data. Use a data-only format with an explicit
>   schema:
>   ```python
>   from pydantic import BaseModel
>
>   class SessionState(BaseModel):
>       user_id: str
>       cart: list[str] = []
>
>   @app.post("/session/restore")
>   async def restore(state: SessionState):   # JSON + schema validation, no code execution
>       return {"restored": list(state.model_dump().keys())}
>   ```
>   If a binary round-trip is genuinely required, sign the blob (HMAC verified with
>   `hmac.compare_digest`) and still parse it with a data-only codec — signing prevents forgery
>   but does not make `pickle` safe.
> - **Regression test**: post a `__reduce__` payload and assert 422 with no side effect.
> - **Baseline status**: new
> - **Origin**: introduced

## 2) Security Domain Coverage — stack: python

All ten evaluated against their canonical questions.

| # | Domain | Verdict | Evidence |
|---|--------|---------|----------|
| 1 | Randomness Safety | N/A | no token/ID generation in scope |
| 2 | Injection & Data-Access Safety | N/A | no query or command construction |
| 3 | Sensitive Data Handling | Applicable / PASS | response returns only key names |
| 4 | Secret / Config Management | N/A | no secrets or config read |
| 5 | Transport Security | N/A | no outbound client in scope |
| 6 | Crypto Primitive Correctness | N/A | no crypto in scope (see fix note on HMAC) |
| 7 | Concurrency & Shared-State Safety | Applicable / PASS | handler holds no shared state |
| 8 | Language-Specific Injection Sinks | Applicable / **FAIL** | `pickle.loads` on untrusted input — SEC-001 |
| 9 | Static Scanner Posture | Applicable / FAIL | `bandit` would flag B301/B403 here; no evidence it runs in CI |
| 10 | Dependency Vulnerability Posture | N/A | no dependency change in this diff |

## 3) Automation Evidence

None executed — static review only, and no authorization for active verification.
`bandit -r .` is the command that would confirm Domain 9; not run here.

## 4) Open questions / assumptions

- Assumes `/session/restore` is reachable without authentication. If an auth dependency exists
  upstream the severity stays P0 (an authenticated RCE is still RCE) but the exposure narrows.

## 5) Risk Acceptance Register

A P0 must not be accepted without VP-level sign-off. None recorded.

## 6) Remediation Plan

- **Immediate**: replace `pickle.loads` with the Pydantic model above; deploy as a hotfix.
- **Short-term**: grep for `pickle`, `yaml.load`, `eval`, `exec` across the service.
- **Backlog**: add `bandit` to CI so Domain 9 has standing evidence.

## 8) Hardening suggestions

- Cap request body size at the ASGI layer; the current handler reads an unbounded body.

## 9) Uncovered Risk List

- Did not inspect the rest of the router: other endpoints may deserialize similarly. Not covered
  because only this handler was provided.
- No dependency audit run, so a vulnerable transitive package could add further exposure.

```json
{
  "summary": { "pass": false, "baseline": "absent" },
  "counts": { "p0": 1, "p1": 0, "p2": 0, "p3": 0, "overflow": 0 },
  "stack": "python",
  "asvs_version": "4.0.3",
  "active_verification": "not_permitted",
  "security_domains": { "required": true, "total": 10, "pass": 2, "fail": 2, "na": 6 },
  "findings": [
    {
      "id": "SEC-001", "severity": "P0", "confidence": "confirmed", "status": "new",
      "origin": "introduced", "cwe": "CWE-502", "asvs": "ASVS 4.0.3 V5.5.1",
      "domain": 8, "file": "app/session.py:restore"
    }
  ]
}
```
