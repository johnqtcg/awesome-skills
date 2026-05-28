# Log Correlation Patterns

The single most valuable move in a multi-service investigation is **walking one failed request end-to-end**, not summarising a thousand.

## The Correlation Field Hierarchy

| Field | Scope | Source | Purpose |
|---|---|---|---|
| `trace_id` | Cross-service, full request lifecycle | OpenTelemetry / W3C Trace Context (`traceparent`) | Reconstruct the entire distributed call tree |
| `span_id` | One operation within a trace | OTel span | Identify the specific hop (one DB call, one HTTP fan-out) |
| `request_id` | One service-side request | Service middleware (often UUIDv4) | Service-local pivot when no trace propagated |
| `correlation_id` / `x-correlation-id` | Cross-service, ad-hoc | Header set at edge | Older alternative to `trace_id` |
| `tenant_id` / `org_id` | Multi-tenant | Auth middleware | Slice by customer to confirm blast radius |
| `user_id` | Per-user | Auth middleware | Confirm "who was affected" |
| `session_id` | Per-session | Auth middleware | Useful for "this user keeps getting 500s" |

Field names vary. In `slog` you may see `trace_id`; in `zap` projects sometimes `traceID`; OTel-instrumented services often emit `trace_id` and `span_id` together in lower-snake-case. Try both casings.

## The Walking-the-Trace Procedure

1. **Pick a representative failure**, not the first ERROR. Choose one that:
   - falls inside the locked time window,
   - belongs to the leading symptom class (e.g., 502 to /checkout, not a background warn),
   - has a populated `trace_id` (skip lines where it is empty — those cannot be walked).

2. **Extract every correlation field on that line**:
   ```bash
   jq -c 'select(.level=="ERROR" and .path=="/v1/checkout") | {trace_id, request_id, user_id, tenant_id, time}' \
     app.log | head -1
   ```

3. **Search every source for that `trace_id`**, not just the service that emitted the error:
   ```bash
   trace=4bf92f3577b34da6a3ce929d0e0e4736
   for f in checkout-svc.log payment-svc.log inventory-svc.log gateway.log kafka-consumer.log; do
     jq -c --arg t "$trace" 'select(.trace_id==$t)' "$f"
   done | jq -s 'sort_by(.time)' > /tmp/trace.json
   ```

4. **Order by timestamp** and reconstruct the hop sequence (service → operation → status → latency).

5. **Annotate each hop**: which boundary it crossed (HTTP / gRPC / Kafka / DB), latency, and outcome.

## Reading the Walked Trace

Patterns that show up in the ordered timeline:

- **Tail-latency cascade**: Each downstream hop adds normal latency, but together they exceed the gateway timeout. The "error" is at the gateway; the *cause* is anywhere in the chain.
- **Retry storm**: One upstream timeout → 3 retries × N services. The error count balloons; the underlying failure is one. Count by `trace_id`, not by line.
- **Lost trace**: Trace ID present at gateway and service A, missing from service B. Either propagation broke (gateway bug, missing OTel middleware) or B emits to a different sink. Note which.
- **Cross-tenant blast radius**: Same error class for many `tenant_id`s in the window → infrastructure-level cause. Same `tenant_id` only → tenant-specific config / quota.

## When Correlation IDs Are Missing

If logs do not carry a `trace_id`, `request_id`, or any cross-service correlation field, **this is itself a High-severity Observability finding**. Reasons:

- You cannot reconstruct user journeys.
- Mean time to repair degrades by an order of magnitude.
- Every future incident pays the same tax.

Recommend, in order of effort:

1. **Edge-injected request_id** (cheapest): the gateway / ingress sets `X-Request-ID` if absent, propagates via header, and every service logs it. Most frameworks have a one-line middleware for this.
2. **OTel auto-instrumentation**: enables `trace_id` / `span_id` on all logs without per-service code changes when the language SDK supports it (Go: `otelhttp`, `otelgrpc`; Java: `opentelemetry-java-instrumentation`).
3. **Structured logger with context-bound fields**: `slog` supports a context-derived handler; `zap` supports `With(...)`; standardise the field name (`trace_id`) repo-wide.

## Fallback: Pivot by `request_id` Within One Service

When trace propagation is broken (B has no `trace_id`), salvage what you can with single-service `request_id`:

```bash
req=$(jq -r 'select(.level=="ERROR" and .path=="/checkout") | .request_id' app.log | head -1)
jq -c --arg r "$req" 'select(.request_id==$r)' app.log | sort -u
```

This gives you the **service-local** request lifecycle. It is strictly weaker than `trace_id` (no cross-service hops) but typically enough to distinguish "request actually broke here" from "request received and forwarded normally; failure is downstream".

## Fallback: Time Plus User

If neither `trace_id` nor `request_id` is present, the last resort is `(user_id, ±5s window)`:

```bash
ts=2026-04-28T08:14:00Z
uid=user_42
jq -c --arg u "$uid" --arg t "$ts" \
  'select(.user_id==$u and .time>=($t|ltrimstr("")|.[0:19]+"Z"))' app.log
```

Be honest in the report: this is *temporal correlation*, not causal correlation. State the window and acknowledge the false-positive risk.

## Quoting Trace Walks in Reports

When the report quotes a walked trace, use a compact table — not the raw JSON. Example:

| Time (UTC) | Service | Operation | Status | Latency |
|---|---|---|---|---|
| 08:14:00.012 | gateway | `POST /v1/checkout` | 200 forwarded | 1ms |
| 08:14:00.018 | checkout-svc | `validate(order)` | OK | 4ms |
| 08:14:00.022 | inventory-svc | `gRPC reserve` | DeadlineExceeded | **2998ms** |
| 08:14:03.020 | checkout-svc | response | 503 upstream timeout | — |
| 08:14:03.024 | gateway | response | 502 | — |

This format makes the *where* obvious and is far more usable than dumped JSON.

## Anti-Patterns Specific to Correlation

- **Listing all 12 services as "affected"** when really one upstream caused 11 cascading errors. Report the cause + the cascade, not the cascade alone.
- **Pivoting on `user_id` first**: tempting but lossy. Always try `trace_id` first; fall back stepwise.
- **Quoting every line of a trace verbatim**: a 200-line trace is unreadable. Aggregate to ≤ 10 hops in the report; offer the full trace as an artefact reference if needed.
