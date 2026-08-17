# Log PII / Secret Redaction

Reports leak data when analysts paste log lines verbatim. The redaction step is **before** quoting, not after. Once a secret is in the chat / PR / postmortem, you cannot recall it.

## Contents

- [Always Redact (Hard List)](#always-redact-hard-list)
- [Always Redact (PII)](#always-redact-pii)
- [Conditionally Redact (Context Matters)](#conditionally-redact-context-matters)
- [Redaction Procedure](#redaction-procedure)
- [What Not to Do](#what-not-to-do)
- [Reporting a Leaked Secret](#reporting-a-leaked-secret)
- [Quoting Examples (Before / After)](#quoting-examples-before--after)

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
2. Pipe the source through the redactor **once**. Do not redact ad-hoc per quote.
3. Verify the output. Then quote only from the verified file.

### Use the shipped redactor

`scripts/redact_log.py` is the executable form of Gate 2, regression-tested in
`scripts/tests/test_redact_log.py` against both directions — each category is
redacted, and the over-redaction cases that break an investigation are not.

**It does not automate the whole hard list.** Three entries above are
manual-judgement and the script deliberately does not guess at them:

| Not automated | Why | What you must do |
|---|---|---|
| Generic high-entropy keys (40+ chars) | No pattern separates a secret from a 32-hex `trace_id` or a content hash. Guessing would eat correlation IDs. | Eyeball long opaque values; redact by hand and note it |
| AWS account IDs (12 digits) | Only sensitive *in AWS context*; a bare 12-digit run is usually an ordinary ID | Redact by hand when the surrounding text is AWS |
| Free-form postal addresses | No reliable shape across locales | Redact by hand |

So `verify: clean` means "none of the **automated** categories survived", not "this
file is safe to publish". The 20-line spot-check below is not optional, and it is
specifically looking for these three.

Three subcommands, split by **capability** rather than by task:

| Subcommand | Writes? | Auto-approved? |
|---|---|---|
| `scan` | no — stdout only | yes |
| `verify` | no — reports and exits 1 on residue | yes |
| `write -o PATH` | **yes** | no — prompts once |

`scan` and `verify` register no output option at all, so argparse rejects
`--output` on them: their read-only-ness is enforced by the parser, not by
convention, which is what makes it safe to pre-approve them. `write` is excluded
because `O_EXCL` prevents *clobbering*, not *creation* — it can still create a new
file anywhere the process can write, and that deserves a human.

Never use a shell `>`; it is forbidden by the Command Safety Contract, and `write`
is strictly safer than the redirect it replaces (`O_EXCL | O_NOFOLLOW` refuses an
existing path or a planted symlink, so `write app.log -o app.log` exits 2 with the
source intact where `>` truncates before the first read).

```bash
# Redact to stdout — no prompt
python3 scripts/redact_log.py scan app.log
python3 scripts/redact_log.py scan --json app.jsonl   # by field NAME and by value

# Persist a redacted copy — prompts once
python3 scripts/redact_log.py write --json app.jsonl -o app.redacted.jsonl

# MANDATORY final step — automated residue check. Exits 1 if anything survived.
python3 scripts/redact_log.py verify app.redacted.jsonl --json
```

### Verify against the policy you redacted with

`verify` checks the policy it is *told* about. An external-facing file verified
without the external flags reports `clean` while still carrying user and tenant
identifiers — the flags must match on both sides:

```bash
python3 scripts/redact_log.py scan   --json --mask-ip --redact-user-id app.jsonl
python3 scripts/redact_log.py verify --json --mask-ip --redact-user-id ext.jsonl
```

`--redact-user-id` covers the whole conditional-redaction list below —
`user_id`, `email`, `tenant_id`, `org_id`, `account_id`, `customer_id`, `username`
— not just `user_id`.

`--verify` does not maintain its own pattern list: residue is defined as "the
redactor would still act on this", so it can never check fewer categories than the
redactor implements. An earlier version kept a separate six-entry table and
reported `password=hunter2` and `Cookie: session=abc` as clean.

Multi-line PEM blocks are handled by a streaming state machine, not the regex —
the CLI reads one line at a time, so a `DOTALL` rule alone never fires on a real
file. The body lines are replaced with blanks so `path:line` citations stay aligned
with the original.

It preserves `trace_id` / `request_id` / `span_id` / `traceparent`, prints a
per-category count to stderr for `Execution Status`, is idempotent (safe to
re-run), and falls back to text redaction on lines that are not valid JSON — so a
Go panic embedded in a JSON stream is still cleaned.

### Why not a hand-rolled sed / jq pipeline

Because they are written once, never executed, and fail silently. Two recipes that
look correct and are not:

```bash
# BROKEN — jq: error: Cannot index object with number
# sub()'s replacement is evaluated with `.` bound to the named-capture object.
# Unnamed captures produce {}, so .[0:1] indexes an object with a number.
jq -c '.user_email = (.user_email | sub("^(.).*@(.*)$"; "\(.[0:1])***@\(.[2])"))'

# CORRECT — name the captures, then reference them by name
jq -c 'if .user_email? then .user_email |= sub("^(?<a>.).*@(?<d>.*)$"; "\(.a)***@\(.d)") else . end'
```

```bash
# BROKEN — emits `alice[0:1]***@example.com`. This is jq slice syntax pasted
# into sed, where [0:1] is a literal character class match, not a slice.
sed -E 's/([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\.[A-Za-z]{2,})/\1[0:1]***@\2/g'

# CORRECT — capture only the first character in the pattern itself
sed -E 's/([A-Za-z0-9._%+-])[A-Za-z0-9._%+-]*@([A-Za-z0-9.-]+\.[A-Za-z]{2,})/\1***@\2/g'
```

Both bugs are invisible until executed: the first errors out mid-pipeline, the
second produces plausible-looking output that still leaks the local part.

If you must hand-roll (no Python available), test the pipeline on a crafted line
containing one instance of every category **before** running it on real logs, then
diff input against output to confirm each one changed. Note that `sed -i` is
forbidden by the Command Safety Contract — write to a new file.

4. After redaction, run `--verify`, then **spot-check 20 random lines** by eye.
   Regex-based redaction misses unconventional formats; `--verify` only re-checks
   the categories it knows about.

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
