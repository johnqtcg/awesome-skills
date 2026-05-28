# Log PII / Secret Redaction

Reports leak data when analysts paste log lines verbatim. The redaction step is **before** quoting, not after. Once a secret is in the chat / PR / postmortem, you cannot recall it.

## Always Redact (Hard List)

These categories are **always** redacted in any quoted log line, regardless of context:

| Class | Pattern (illustrative) | Replacement |
|---|---|---|
| Bearer tokens / JWTs | `Bearer\s+[A-Za-z0-9._-]+={0,2}` | `Bearer ***REDACTED***` |
| OAuth / API keys | `sk-[A-Za-z0-9]{20,}`, `AKIA[0-9A-Z]{16}`, `xox[bpasr]-[A-Za-z0-9-]+`, `ghp_[A-Za-z0-9]{30,}`, `glpat-[A-Za-z0-9_-]{20,}` | `***REDACTED-API-KEY***` |
| Generic high-entropy keys (40+ chars, alphanum) | (manual judgement) | `***REDACTED-KEY***` |
| Passwords in URLs | `://[^:]+:[^@/]+@` | `://user:***@` |
| Cookies / session IDs | `Cookie:\s*[^;\n]+` | `Cookie: ***REDACTED***` |
| Authorization headers (any scheme) | `Authorization:\s*\S+` | `Authorization: ***REDACTED***` |
| Private keys | `-----BEGIN [A-Z ]+ KEY-----.*-----END [A-Z ]+ KEY-----` | `***REDACTED-PRIVATE-KEY***` |
| AWS account IDs | `\b[0-9]{12}\b` (when in AWS context) | `***REDACTED-AWS-ACCT***` |

## Always Redact (PII)

| Class | Pattern (illustrative) | Replacement |
|---|---|---|
| Email | `[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}` | first char + `***@<domain>` |
| Phone | `\+?\d[\d\s().-]{7,}\d` (country-aware preferred) | mask middle digits |
| Credit card / PAN | 13–19 digits, optionally grouped, passing Luhn | `***REDACTED-PAN***` |
| Government IDs (SSN-shape) | `\b\d{3}-\d{2}-\d{4}\b` | `***REDACTED-ID***` |
| Postal addresses (free-form) | (manual judgement) | `***REDACTED-ADDR***` |
| IP addresses (only when reporting to an external party) | `\b(\d{1,3}\.){3}\d{1,3}\b` | `<masked-ip>` |

## Conditionally Redact (Context Matters)

These can be safe or sensitive depending on audience:

| Class | When to redact | When to keep |
|---|---|---|
| `user_id` | Reports leaving the company (vendor postmortem, public blog). | Internal investigation: keep — needed to walk traces. |
| `tenant_id` / `org_id` | External-facing report. | Internal: keep — confirms blast radius. |
| Internal hostnames / pod names | Public-facing report (security through obscurity is real for attackers mapping infrastructure). | Internal: keep. |
| Trace IDs | Almost never sensitive on their own. | Always keep — they enable re-walking the trace. |

When in doubt, redact and add `(redacted by analyst — uncertainty)` to the side.

## Redaction Procedure

1. Decide the redaction set **before** opening the log file.
2. Build a single sed/awk pipeline that applies all redactions and pipe the source through it once. Do **not** redact ad-hoc per quote.
3. Redact at the **field level** for JSON logs (preserves structure):
   ```bash
   jq -c '.authorization = (.authorization // empty | "***REDACTED***")
          | .user_email = (.user_email // empty | sub("^(.).*@(.*)$"; "\(.[0:1])***@\(.[2])"))
          | del(.password)' app.log > app.redacted.jsonl
   ```
4. For text logs, layer regex substitutions:
   ```bash
   sed -E '
     s/Bearer [A-Za-z0-9._-]+={0,2}/Bearer ***REDACTED***/g;
     s/(sk-[A-Za-z0-9]{20,})/***REDACTED-API-KEY***/g;
     s/([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\.[A-Za-z]{2,})/\1[0:1]***@\2/g;
   ' app.log > app.redacted.log
   ```
5. After redaction, **spot-check 20 random lines** for residual leaks. Regex-based redaction misses unconventional formats.

## What Not to Do

- **Do not** retro-redact after the report is written. The unredacted draft is itself a leak (chat history, autosaves, screen shares).
- **Do not** rely on the user redacting before sending. They paste the log because they want help; they will not pre-process.
- **Do not** skip redaction "just for myself" — chat transcripts persist; tooling logs persist; secrets must be considered compromised after any plaintext exposure.
- **Do not** redact correlation IDs (`trace_id`, `request_id`). They are not a secret and are essential to the analysis. Plain rule: do not redact `trace_id`.

## Reporting a Leaked Secret

If during analysis you find a secret has already been leaked (committed in a log line, copy-pasted in a Slack thread, persisted in an aggregator):

- Treat the secret as compromised. **Rotation is mandatory**, regardless of whether the leak was external.
- Add a High-severity finding tagged `Category: security`.
- Recommendation must include: rotate, scan history (Git, log retention, message archives), audit usage, and add a redaction rule preventing recurrence.
- **Do not** quote the leaked secret in the finding. State its location and class only.

## Quoting Examples (Before / After)

Before:
```
2026-04-28T08:14:00Z ERROR auth.service Failed to validate token Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJ1c2VyIjoiYWxpY2VAZXhhbXBsZS5jb20iLCJleHAiOjE3MTQzMDB9.signature_here for user alice@example.com from 203.0.113.42 trace_id=4bf92f3577b34da6a3ce929d0e0e4736
```

After:
```
2026-04-28T08:14:00Z ERROR auth.service Failed to validate token Authorization: Bearer ***REDACTED*** for user a***@example.com from <masked-ip> trace_id=4bf92f3577b34da6a3ce929d0e0e4736
```

The `trace_id` survives intact — the report still enables walking the trace. Everything else is masked.
