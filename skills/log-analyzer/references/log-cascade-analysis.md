# Cascade Analysis: Cause Cluster vs Symptom Cluster

In a real outage the log is dominated by **symptom clusters** — many downstream errors caused by a single upstream failure. Counting symptoms inflates severity and points at the wrong service. Cascade analysis separates the cause cluster from its symptom clusters.

## Two Cluster Types

**Cause cluster** — errors at the failing component itself. Usually small, often 1–5 lines. Examples:

- 1 line: `level=error msg="db connection pool exhausted" pool=primary inflight=200/200`
- 3 lines: deploy event + first failure + readiness probe failed.

**Symptom cluster** — errors in components that depended on the failing one. Usually large. Examples:

- 200 lines: every consumer that called the DB getting `context deadline exceeded`.
- 500 lines: every retry attempt at the gateway.

## Recognising Cascades

Signs you are looking at a symptom cluster, not a cause cluster:

1. **Tight time clustering**: errors begin within milliseconds of each other across many services. The trigger is usually a single upstream event.
2. **Convergent error class**: many services emit the same error class (`context deadline exceeded`, `i/o timeout`, `connection refused`). Convergence on a generic timeout/refused error is a near-certain signal of upstream failure.
3. **Asymmetric attribution by request**: if you walk one trace, the error appears at hop N. Walk a second trace — same hop N. The cause is at or above hop N.
4. **Rate proportional to traffic**: error count tracks RPS. The trigger is "we tried to do work" — the work itself failed.

Signs you are looking at a cause cluster:

1. **Originating service is small / lower-level** (DB, cache, auth, message broker).
2. **Error class is specific**: `pool exhausted`, `deadlock detected`, `disk full`, `out of memory`, `unauthorized`, `quota exceeded`.
3. **Precedes** the symptom cluster by milliseconds to seconds in time order.
4. **Independent of caller volume**: error rate is roughly constant or step-function-shaped, not proportional to RPS.

## Practical Procedure

1. Order all errors in the window by `time` ascending.
2. Look at the **first 30 seconds** of error activity. The cause almost always lives there.
3. Group by `service` and `msg` (after identifier stripping — see `log-statistical-methods.md`).
4. Build a precedence graph: which service's first error preceded which others?
5. The earliest service with a **specific** error class is your cause-cluster candidate. Validate by walking one symptom-cluster trace back through it.

## Common Cascade Shapes

### DB Pool Exhaustion → Service-wide 5xx Storm

```
T+0:    db-proxy: "max connections reached: 200/200" (cause)
T+0.05: order-svc: "context deadline exceeded" while calling db    (symptom)
T+0.05: payment-svc: "context deadline exceeded" while calling db  (symptom)
T+0.10: gateway: "upstream timeout" 502                             (symptom)
T+0.50: order-svc: retry → "context deadline exceeded"             (symptom)
…
```

Reporting: ONE finding (the cause), with the cascade summarised in Causation Chain.

### Cache Outage → DB Hot-Spot → Latency Cascade

```
T+0:    redis: "MASTERDOWN failover starting"                      (cause)
T+1:    feature-svc: "redis: connection refused" → fallback to DB   (symptom A)
T+1.5:  db: "wait_event=lock_manager" 95%                           (symptom B, bigger downstream of A)
T+2:    every read path: 2-second median latency                    (symptom C, biggest)
```

The largest cluster is **C**, the smallest is **the cause**. Reporting only the largest produces a useless "every service is slow" finding.

### Deploy → Bad Config → Authn Failures Across Services

```
T+0:    deployer: "rolled out config v823"                          (trigger event — not a log error)
T+0.5:  auth-svc: "JWT verification failed: kid not found"          (cause)
T+1:    order-svc: "401 from auth-svc"                              (symptom)
T+1:    every service: 401s for new sessions                        (symptom)
```

The cause is `auth-svc` first JWT failure, but the **trigger** is the deploy. State both. Recommend: roll back; add CI check for new-key staging.

### Retry Storm Amplification

A single upstream timeout becomes 3 timeouts per request because of client-side retries. This **inflates count by 3×** and shortens time-to-pool-exhaustion in downstream services.

Distinguish by counting unique `request_id` / `trace_id`:

```bash
# Apparent count
jq 'select(.level=="ERROR") | .msg' app.log | wc -l       # → 12000

# Distinct requests affected
jq -r 'select(.level=="ERROR") | .request_id' app.log | sort -u | wc -l   # → 4000
# 3× difference = retry amplification, probably
```

Reporting: state both numbers. Recommend a circuit breaker if absent.

## When the Cause Is Outside the Logs

Sometimes the cause cluster is empty in the logs you have because:

- The failing component does not log to the same destination (different aggregator, different cluster, dropped at ingest).
- The cause was a **non-log event**: a deploy, a config push, a network partition, a noisy neighbour exhausting CPU.
- The cause was in an upstream **vendor / SaaS** outside your aggregator entirely.

Procedure when the cause is missing:

1. State explicitly: `Cause cluster not visible in scoped logs`.
2. Identify candidate non-log sources: deploy timeline, config audit trail, infra event log, vendor status page.
3. Convert "find the cause cluster" into an **Open Question** with concrete data the user should pull.

This is honest and far more useful than promoting a symptom cluster to "root cause".

## Quoting Cascades in Reports

A 200-line cascade is unreadable. Quote at most:

- 1 line from the cause cluster (with redaction),
- 2 lines from the leading symptom cluster,
- A summary table of the cascade by minute (Time / Service / Error class / Count).

Offer the full data as an artefact reference if needed.
