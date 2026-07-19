# Web Evidence Trust and Safe Egress

Use this reference whenever the research kind is `web` or `hybrid`.

## Trust Model

Web evidence has four states:

| State | Origin | What it proves | Maximum effect |
|---|---|---|---|
| Discovery result | Search/API/imported JSON | A candidate URL was discovered | No claim support |
| Serialized content | `content.json` or host/browser export | The supplied excerpt matches supplied text | Medium after validation |
| Live validator capture | Current `validate/report --live-web` process | The safe transport retrieved the effective URL and the excerpt matched that response | Eligible for High |
| Live primary capture | Live validator capture whose effective URL re-derives as T1 | Current primary content directly supports the narrow fact | High for `single_fact` |

Serialized data is caller-controlled. Loading it always sets
`live_verified=false`, even when the file says otherwise. The validator also
ignores caller-provided `source_tier`, `source_type`, `domain`, and
`classification_basis` when making authority decisions.

The current executable automatic T1 policy is intentionally conservative:
recognized government namespaces may derive as T1. Other domains remain below
High unless a future trusted authority registry or host execution handle is
added. This avoids replacing caller self-assertion with another unaudited JSON
field.

## Provenance Recorded for a Live Capture

The in-process validation record includes:

- requested URL and effective final URL,
- HTTP status,
- capture time and capture method,
- all validated public IPs used across redirect hops,
- raw-response and extracted-content SHA-256 values,
- source type, tier, and classification basis re-derived from the final URL,
- exact excerpt matched against extracted content.

Hashes make the result auditable; they are not a signature. A serialized copy
of the same fields is not reusable as proof that a later process executed the
fetch.

## Public-Network-Only Policy

Before any connection:

1. Parse the URL and require `http` or `https`.
2. Reject embedded credentials, missing hostnames, invalid ports, `localhost`,
   and `.localhost`.
3. Canonicalize literal IPv4, IPv6, zone, and IPv4-mapped IPv6 forms.
4. Resolve DNS with the intended TCP port.
5. Reject the whole target if any answer is not public unicast. This includes
   loopback, private, link-local, unspecified, reserved, multicast, and cloud
   metadata addresses.

During the request:

1. Connect directly to one of the already validated IPs.
2. Preserve the original hostname in the HTTP Host header and TLS SNI /
   certificate validation.
3. Do not let the HTTP library auto-follow redirects.
4. Resolve and validate each joined redirect URL before opening its connection.
5. Enforce timeout, redirect count, response-size, retry, WAF, and
   content-quality limits.

Validating and then connecting by hostname is insufficient because DNS can
change between those operations. Selecting one public answer while ignoring a
private answer is also insufficient.

## CLI Workflow

First collect content for finding authoring:

```bash
python3 scripts/deep_research.py fetch-content \
  --session /tmp/research_plan.json \
  --results /tmp/results.json \
  --output /tmp/content.json
```

For a final Web report, run live verification once:

```bash
python3 scripts/deep_research.py report \
  --question "<question>" \
  --research-kind web \
  --results /tmp/results.json \
  --content /tmp/content.json \
  --findings /tmp/findings.json \
  --session /tmp/research_plan.json \
  --live-web \
  --validation-output /tmp/validation.json \
  --output /tmp/report.md
```

Use `validate --live-web` instead when validation JSON is the final
deliverable. Running both live commands intentionally performs two independent
fresh checks; it is not required for the standard report workflow.

## Failure and Degradation

- Unsafe target: reject before budget reservation or connection.
- Fetch/extraction failure: preserve the error; the evidence is unusable.
- Serialized excerpt match without live capture: usable at most Medium.
- Live capture whose final URL is not T1: usable at most Medium for a narrow
  single fact.
- Redirect to a non-public target: reject the chain; do not keep the first hop
  as support.
- Missing or mismatched excerpt: unusable, regardless of source authority.

## Regression Requirements

Maintain negative tests for:

- `file:`, FTP, and other non-HTTP schemes,
- URL credentials,
- IPv4/IPv6 loopback, private, link-local, unspecified, reserved, multicast,
  and metadata targets,
- mixed public/private DNS answers,
- public first hop redirecting to a non-public target,
- connection IP matching the previously validated address,
- caller-authored T1 and serialized `live_verified=true`,
- final-URL authority reclassification.
