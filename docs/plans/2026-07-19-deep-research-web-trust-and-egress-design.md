# Design: Deep Research Web Trust And Safe Egress

## 1. Context

- **Problem / Purpose**: The Web path accepts caller-authored content and
  source tiers as if they were independently verified, while the fetch path
  can open `file://`, loopback, private, link-local, and redirected internal
  targets.
- **Who is affected**: Agents and reviewers relying on Web High confidence,
  plus hosts that grant the `fetch-content` helper permission.
- **Success criteria**:
  - caller-authored `source_tier: T1` never establishes primary authority;
  - serialized content alone cannot establish Web High;
  - Web High requires a fresh validator-controlled public-network fetch;
  - every outbound hop is HTTP(S), resolves only to globally routable
    addresses, and connects to a validated pinned address;
  - redirects are revalidated before the next request;
  - offline artifacts remain useful at Medium with an explicit downgrade.

## 2. Constraints And Compatibility

- Python 3.12 CI and standard library only.
- Preserve the current CLI and nine-section report contract.
- Keep `fetch-content` useful for discovery and excerpt authoring, but do not
  treat reloaded JSON as execution proof.
- Do not add a caller-writable authority policy or unsigned Web receipt and
  describe it as trusted.
- Do not make network access implicit: final live verification is opt-in via
  an explicit CLI flag and otherwise fails closed for High.

## 3. Approaches Considered

The design uses inversion: instead of asking how to make caller JSON appear
more trustworthy, require the verifier to own the authoritative operation.

### Option A: Add hashes and provenance fields to `content.json`

- Improves auditability.
- Does not create a trust root; a caller that can write JSON can forge hashes,
  timestamps, and labels together.
- Rejected as sufficient proof, retained only as audit metadata.

### Option B: Import a host Web receipt

- Could integrate with a future unforgeable host execution handle.
- A plain `origin=host-tool` JSON receipt has the same forgery boundary as the
  test receipt and does not independently prove a fetch.
- Deferred until the host provides a non-forgeable handle.

### Option C: Validator-owned live refetch plus derived authority

- `validate/report --live-web` securely refetches each cited page and validates
  the excerpt against that fresh response.
- Source tier/type/basis are recomputed from the effective final URL; caller
  labels are contextual only.
- Without live verification, evidence may remain usable but cannot be primary
  or High.

Choose Option C. It is the only option available in the current process model
that materially improves the trust boundary without pretending local JSON is
attestation.

## 4. Chosen Approach

Use Brainstorming `Standard` mode. Split the implementation into:

1. a standard-library safe HTTP(S) module;
2. live-capture metadata on in-memory content records;
3. conservative authority derivation inside evidence validation;
4. explicit `--live-web` verification for `validate` and `report`.

The user's instruction to continue targeted hardening approves closing both
reported boundaries. No clarification is required because the exploit,
desired fail-closed behavior, and non-goals are concrete.

## 5. Architecture / Components / Flow

### Safe egress

`URL -> parse -> reject credentials/non-HTTP(S) -> resolve all addresses ->
reject any non-global address -> pin one validated address -> request ->
validate redirect target -> repeat`

The HTTP client connects to the resolved IP rather than resolving the hostname
again at connection time. HTTPS still verifies the certificate and sends SNI
for the original hostname. Environment proxies are not used.

### Web evidence

1. `fetch-content` securely fetches and records audit metadata.
2. Reloading `content.json` deliberately marks every row as not live-verified.
3. `validate/report --live-web` fetches cited URLs again through the safe
   egress client and uses those in-memory results.
4. The validator derives tier/type/basis from the final URL, ignoring caller
   authority labels.
5. Only live-verified, validator-derived T1 content can satisfy the narrow
   single-fact High rule.
6. Offline content can still support Medium if its excerpt matches.

## 6. Failure Handling And Operational Notes

- Unsafe direct URL: reject before reserving extraction budget or opening a
  socket.
- Mixed public/private DNS answers: reject the hostname entirely.
- Redirect to unsafe target: stop before following it.
- Excess redirects, invalid port, credentials, DNS failure, TLS failure, HTTP
  error, or low-yield content: record or return an explicit error.
- `--live-web` failure downgrades or blocks according to remaining verified
  evidence; it never falls back to trusting the serialized content as High.
- Authority classification remains conservative. Most arbitrary documentation
  sites will not be T1 without a validator-owned rule.

## 7. Validation And Testing

- Reproduce and reject `file:///etc/hosts`.
- Reject IPv4/IPv6 loopback, RFC1918, link-local metadata, multicast,
  unspecified, reserved, and mixed DNS answers.
- Prove redirect targets are validated before the next request.
- Prove the connection receives the already validated IP.
- Prove caller-authored T1 is ignored.
- Prove serialized content cannot reach High.
- Prove a fresh live-verified validator-derived T1 page can reach High.
- Run focused tests, all regressions, pytest, compileall, quick validation,
  diff checks, and MkDocs.

## 8. Open Questions / Risks

- Automatic authority derivation cannot identify every first-party vendor,
  standards body, or original research publisher. This intentionally favors
  Medium over false High.
- A future host WebFetch execution handle could avoid the second network call
  while preserving the trust boundary.
- Live pages can change between authoring and final reporting; a mismatch is a
  real downgrade, not a validator error.

## 9. Approval And Handoff

- **Approval status**: Approved by the user's explicit request to close the
  demonstrated Web trust and egress gaps.
- **Design doc status**: Saved at
  `docs/plans/2026-07-19-deep-research-web-trust-and-egress-design.md`.
- **Next step**: `writing-plans`, then inline execution because delegation was
  not authorized.

