# Example Output

A complete `Standard`-mode report from a real-shaped investigation. Use this as a formatting reference. Identifiers and timestamps are fabricated.

---

# Log Analysis — Checkout 502 Spike

### Analysis Mode
- `Standard`
- 2 services in scope, 1-hour window, no security signal — Lite would underweight the correlation work; Strict's baseline-vs-baseline is overkill given clear deploy correlation.

### Window & Source
- `Window: 2026-04-28T08:00:00Z → 2026-04-28T09:00:00Z`
- `Source:` `kubectl logs -n prod -l app=checkout-svc --since=1h --timestamps` (15 pods) + `kubectl logs -n prod -l app=inventory-svc --since=1h --timestamps` (8 pods)
- `Coverage: full — no rotation events in window`
- `Format: slog JSON (both services)`

### Executive Summary
Checkout 502 ratio reached 4.2% from 08:14:30 (deploy v823 of `inventory-svc`). Cause cluster: gRPC `reserveStock` deadlines on every call from `checkout-svc → inventory-svc`. Confidence Confirmed for cause; Hypothesis for the underlying mechanism (suspect new `gRPC.MaxConcurrentStreams=1` in the deploy diff). Origin breakdown: 1 confirmed / 2 hypothesis / 0 needs-corroboration. 1 additional issue moved to Residual Risk.

### Findings

#### [High] Cause: inventory-svc gRPC deadlines on `reserveStock` from 08:14:30
- **ID:** `LOG-001`
- **Confidence:** `Confirmed`
- **Category:** `availability`
- **Location:** `inventory-svc` pods, slog field `caller="reserveStock.go:142"`, first occurrence `2026-04-28T08:14:31.047Z`
- **Evidence:**
  ```
  {"time":"2026-04-28T08:14:31.047Z","level":"ERROR","msg":"reserveStock deadline","grpc_method":"/Inventory/Reserve","duration_ms":2998,"trace_id":"4bf92f35…","peer":"checkout-svc"}
  ```
- **Inference:** All 412 distinct request_ids in the symptom cluster reach `inventory-svc.Reserve` and time out. Deploy event `inventory-svc:v823` posted at `08:14:18` — 13 seconds before first deadline.
- **Causation chain:** 502 at gateway ← upstream timeout from checkout-svc ← `Reserve` deadline at inventory-svc ← (hypothesis) per-pod gRPC concurrency cap from v823.
- **Refuter:** if pod CPU / memory / GC pause metrics also stepped at 08:14:30, the cap hypothesis is weakened — could be a different resource exhaustion.
- **Recommendation:** roll back `inventory-svc:v823`; capture pod metrics for the window; inspect deploy diff for gRPC server options.

#### [High] Symptom cluster: checkout-svc 502 storm (suppressed from cause attribution)
- **ID:** `LOG-002`
- **Confidence:** `Confirmed`
- **Category:** `availability`
- **Location:** `checkout-svc` pods, 412 distinct request_ids in window
- **Evidence (one of 4 lines redacted before quoting):**
  ```
  {"time":"2026-04-28T08:14:31.052Z","level":"ERROR","msg":"upstream timeout","upstream":"inventory-svc","trace_id":"4bf92f35…","authorization":"Bearer ***REDACTED***"}
  ```
- **Inference:** 412 / 9870 (4.2%) of checkout requests in window. Rate is proportional to RPS — characteristic of symptom cluster, not independent cause.
- **Refuter:** if the same error class persists after inventory-svc rollback, this becomes its own cause cluster.
- **Recommendation:** track post-rollback; if persistent, escalate.

#### [Medium] Observability: 14% of inventory-svc lines lack `trace_id`
- **ID:** `LOG-003`
- **Confidence:** `Hypothesis — needs corroboration: deploy diff`
- **Category:** `observability`
- **Location:** `inventory-svc.go:server.go` (suspected interceptor ordering)
- **Evidence:** of 7234 inventory-svc lines in window, 1011 (14%) have empty `trace_id`. Spot-checked: all 1011 are from internal background tasks, not Reserve handler. Fine for now, but the same gap will hurt the next outage.
- **Refuter:** if those 1011 lines come from request paths (not background), this is a higher-severity finding.
- **Recommendation:** confirm OTel interceptor wraps all handlers; if intentional for background tasks, add a `worker=true` tag for clarity.

### Timeline

| Time (UTC) | Service | Event | trace_id |
|---|---|---|---|
| 08:14:18.030 | deployer | `rollout inventory-svc v823 start` | n/a |
| 08:14:30.892 | inventory-svc | first `Reserve` deadline | 4bf92f35… |
| 08:14:31.047 | inventory-svc | second `Reserve` deadline | a91c83… |
| 08:14:31.052 | checkout-svc | first `upstream timeout 502` | 4bf92f35… |
| 08:14:31.430 | gateway | first `502` to client | 4bf92f35… |
| 08:30:14.221 | inventory-svc | error rate stable at ~4.2% of Reserve calls | various |
| 09:00:00.000 | window end | (rollback not yet executed) | — |

### Correlation Map

Walked trace `4bf92f35…`:

| Time (UTC) | Service | Operation | Status | Latency |
|---|---|---|---|---|
| 08:14:31.020 | gateway | `POST /v1/checkout` | forwarded | 2ms |
| 08:14:31.022 | checkout-svc | `validate(order)` | OK | 4ms |
| 08:14:31.026 | checkout-svc | `gRPC inventory.Reserve` | DeadlineExceeded | 2998ms |
| 08:14:31.052 | checkout-svc | response | 503 upstream timeout | — |
| 08:14:31.430 | gateway | response to client | 502 | — |

### Root Cause Hypotheses

1. **Deploy v823 reduced gRPC server concurrency on inventory-svc** — Confidence: Hypothesis. Evidence: error onset 13s after deploy + cluster restricted to inventory's `Reserve`. Refuter: pod CPU/mem also stepped at 08:14:30. Next data: kubectl describe pod for resource limits, deploy diff.
2. **inventory-svc database connection pool sized below new traffic** — Confidence: Hypothesis. Evidence: latency hits exactly 3000ms (a deadline budget, not a pool wait). Weaker than #1. Refuter: db wait events absent in this window.

### Recommendations

1. **Roll back inventory-svc to v822.** Owner: inventory team. Effort: S. Expected effect: error rate to 0 within 2–5 min (deploy time).
2. **Run smoke load against v823 in staging at production concurrency.** Owner: inventory team. Effort: M. Expected effect: confirm or refute concurrency-cap hypothesis before re-rolling.
3. **`→ monitoring-alerting`**: add SLO burn-rate alert on `inventory-svc.Reserve.deadline_ratio`. Pattern was visible in logs but no page fired during the window.

### Suppressed Items
- 87 lines of `level=warn msg="retrying after transient error"` in checkout-svc → healthy retry path (each request_id eventually returned 200 or 502, no abandoned retries). Suppressed by base rate.
- 12 lines `level=info msg="leader elected"` in inventory-svc → not failure-related.

### Execution Status
- `Format`: slog JSON (both services)
- `Window`: `2026-04-28T08:00:00Z → 2026-04-28T09:00:00Z`
- `Files / queries scanned`: 23 pods × 1 hour ≈ 17.0 GB stream-piped
- `References loaded`: log-format-cheatsheet.md, log-correlation.md, log-cascade-analysis.md, log-pii-redaction.md, log-anti-patterns.md, log-analysis-quick-checklist.md
- `PII redaction applied`: yes (Bearer tokens redacted in 4 lines; user_id kept for trace walking — internal-only report)
- `Statistical baseline`: previous-hour `2026-04-28T07:00:00Z → 08:00:00Z` (error_ratio < 0.01%; deploy-event-free)
- `Correlation IDs present`: trace_id ✓, request_id ✓, span_id ✓, user_id ✓
- `External tools run`: `kubectl logs` PASS, `jq` PASS, `rg` PASS, aggregator query Not run — no Loki/ELK/Datadog access in this environment

### Open Questions
- Is there a deploy diff for `inventory-svc:v823`? Specifically gRPC server options.
- Are pod CPU/memory metrics available for 08:14:00–08:15:00? Either they will show a step (different cause) or they will not (consistent with the concurrency hypothesis).

### Residual Risk / Investigation Gaps
- Volume-cap overflow: `Low | hygiene | inventory-svc | 41 lines of duplicate "starting graceful shutdown" — log noise, not a defect`.
- Time-window gap: deploy *event log* not consulted (only effect visible in service logs); deploy timestamp inferred from deployer-bot log line.
- Coverage gap: gateway logs not scoped — gateway is shared with 7 other services; including it would 10× the volume but might surface upstream throttle behaviour.

### Hand-off Protocol
```
incident_id: TBD
impact_summary: Checkout 4.2% error rate for ≥45 min beginning 2026-04-28T08:14:30Z
window_utc: 2026-04-28T08:00:00Z → 2026-04-28T09:00:00Z
affected_services: checkout-svc, inventory-svc, api-gateway (downstream)
data_sources: kubectl logs prod -l app=checkout-svc; kubectl logs prod -l app=inventory-svc
top_findings: [LOG-001, LOG-002, LOG-003]
leading_hypothesis: inventory-svc deploy v823 introduced a gRPC server concurrency cap; Reserve calls hit the 3-second deadline; downstream cascaded into 502s at gateway.
blameless_framing: A configuration change in the inventory service deploy reduced server-side concurrency below production traffic levels; the change-review process did not surface the concurrency-affecting setting.
```

### Summary
Confirmed cause: `inventory-svc:v823` deploy at 08:14:18 → `Reserve` gRPC deadlines → checkout 502 cascade. Hypothesis on mechanism: per-pod gRPC concurrency cap. Confidence: High on attribution, Medium on mechanism. Next data: deploy diff + pod resource metrics. 1 additional issue moved to Residual Risk.
