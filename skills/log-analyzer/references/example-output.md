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
- `Coverage: partial — both in-scope services fully covered (no rotation events), but the request path continues into the api-gateway and the change origin into the deploy event log, neither of which was scanned. Coverage is judged against the incident, not against the sources chosen.`
- `Format: slog JSON (both services)`

### Executive Summary
Checkout 502 ratio reached 4.2% from 08:14:30. Cause cluster: gRPC `reserveStock` deadlines on every call from `checkout-svc → inventory-svc` — Confirmed, both services were scanned. The attribution to deploy `inventory-svc:v823` is `Hypothesis — needs corroboration`, because the deploy timestamp comes from a deployer-bot line that was **not** in the scanned sources. Mechanism (suspect `gRPC.MaxConcurrentStreams=1` in the deploy diff) is also Hypothesis. Origin breakdown: 1 confirmed / 1 hypothesis / 1 needs-corroboration. 1 additional issue moved to Residual Risk.

### Findings

#### [High] Cause: inventory-svc gRPC deadlines on `reserveStock` from 08:14:30
- **ID:** `LOG-001`
- **Confidence:** `Confirmed`
- **Category:** `availability`
- **Location:** `inventory-svc` pods, slog field `caller="reserveStock.go:142"`, first occurrence `2026-04-28T08:14:31.047Z`
- **Evidence:** cause line, and the symptom line it produces 5ms later (both post-`redact_log.py write --json`; `trace_id` deliberately preserved so the reader can re-walk the trace):
  ```
  {"time":"2026-04-28T08:14:31.047Z","level":"ERROR","msg":"reserveStock deadline","grpc_method":"/Inventory/Reserve","duration_ms":2998,"trace_id":"4bf92f35…","peer":"checkout-svc"}
  {"time":"2026-04-28T08:14:31.052Z","level":"ERROR","msg":"upstream timeout","upstream":"inventory-svc","trace_id":"4bf92f35…","authorization":"Bearer ***REDACTED***","user_email":"a***@example.com"}
  ```
- **Inference:** All 412 distinct request_ids in the symptom cluster reach `inventory-svc.Reserve` and time out. A deployer-bot line reports `inventory-svc:v823` at `08:14:18` — 13 seconds before the first deadline — but the deploy event log was **not** among the scanned sources, so that link is corroboration-pending, not observed here.
- **Causation chain:** 502 at gateway *(out of scope — inferred from checkout-svc's own 503 responses)* ← upstream timeout from checkout-svc *(observed)* ← `Reserve` deadline at inventory-svc *(observed, cause cluster)* ← per-pod gRPC concurrency cap from v823 *(hypothesis — needs corroboration: deploy diff)*.
- **Cascade summary** (one cause finding, symptoms folded in per `log-cascade-analysis.md`):

  | Cluster | Service | Lines | Distinct request_id | Role |
  |---|---|---|---|---|
  | Cause | inventory-svc | 412 | 412 | `Reserve` deadline — specific error class, step-shaped onset |
  | Symptom | checkout-svc | 412 | 412 | `upstream timeout` → 503; rate proportional to RPS |

  The checkout-svc 502 storm is **not** reported as a separate finding: it is the
  symptom cluster of this cause. Counting it separately would double-count the
  same incident and inflate severity. It reappears in Suppressed Items.
- **Refuter:** if pod CPU / memory / GC pause metrics also stepped at 08:14:30, the cap hypothesis is weakened — could be a different resource exhaustion. If checkout-svc `upstream timeout` persists after an inventory-svc rollback, the symptom cluster is actually an independent cause and must be re-opened as its own finding.
- **Recommendation:** roll back `inventory-svc:v823`; capture pod metrics for the window; inspect deploy diff for gRPC server options.

#### [Medium] Observability: 14% of inventory-svc lines lack `trace_id`
- **ID:** `LOG-002`
- **Confidence:** `Confirmed` (the gap is counted directly in the scanned logs).
  The *explanation* — gRPC interceptor ordering — is
  `Hypothesis — needs corroboration: server.go interceptor registration`.
  Confidence attaches to each claim, not to the finding as a whole: a measured
  observation does not inherit the uncertainty of its proposed cause, and
  labelling the whole finding a hypothesis invites a reader to discount the
  measurement too.
- **Category:** `observability`
- **Location:** `kubectl logs -n prod -l app=inventory-svc --since=1h` @ `2026-04-28T08:00:00Z → 09:00:00Z`, 1011 of 7234 lines. *(The suspected code site — gRPC interceptor registration in `server.go` — is a lead for the fix, not a log source. Location must be where the evidence was read.)*
- **Evidence:** 1011 of 7234 inventory-svc lines (14%) carry an empty `trace_id`. Representative line:
  ```
  {"time":"2026-04-28T08:22:10.318Z","level":"INFO","msg":"stock reconciliation tick","trace_id":"","worker":"reconciler","batch":250}
  ```
  Spot-checked across the window: all 1011 come from internal background tasks, not the `Reserve` handler. Not load-bearing today, but the same gap will hurt the next outage.
- **Refuter:** if those 1011 lines come from request paths (not background), this is a higher-severity finding.
- **Recommendation:** confirm OTel interceptor wraps all handlers; if intentional for background tasks, add a `worker=true` tag for clarity.

### Timeline

Every row is marked `observed` (present in a scanned source) or `out of scope`
(known from elsewhere). Un-marked rows would read as evidence they are not.

| Time (UTC) | Service | Event | trace_id | Basis |
|---|---|---|---|---|
| 08:14:18.030 | deployer | `rollout inventory-svc v823 start` | n/a | **out of scope — deployer-bot message pasted by the user; deploy log not scanned** |
| 08:14:30.892 | inventory-svc | first `Reserve` deadline | 4bf92f35… | observed |
| 08:14:31.047 | inventory-svc | second `Reserve` deadline | a91c83… | observed |
| 08:14:31.052 | checkout-svc | first `upstream timeout` → 503 | 4bf92f35… | observed |
| 08:14:31.430 | gateway | `502` to client | 4bf92f35… | **out of scope — gateway logs not scanned; inferred from checkout-svc 503 + user-reported 502** |
| 08:30:14.221 | inventory-svc | error rate stable at ~4.2% of Reserve calls | various | observed |
| 09:00:00.000 | window end | (rollback not yet executed) | — | observed |

### Correlation Map

Walked trace `4bf92f35…` across the two scanned services. Gateway hops are
reconstructed, not walked — the gateway was not in scope.

| Time (UTC) | Service | Operation | Status | Latency | Basis |
|---|---|---|---|---|---|
| 08:14:31.020 | gateway | `POST /v1/checkout` | forwarded | 2ms | **out of scope — inferred from checkout-svc ingress span** |
| 08:14:31.022 | checkout-svc | `validate(order)` | OK | 4ms | observed |
| 08:14:31.026 | checkout-svc | `gRPC inventory.Reserve` | DeadlineExceeded | 2998ms | observed |
| 08:14:31.031 | inventory-svc | `Reserve` handler | deadline | 2998ms | observed |
| 08:14:31.052 | checkout-svc | response | 503 upstream timeout | — | observed |
| 08:14:31.430 | gateway | response to client | 502 | — | **out of scope — user-reported; gateway logs not scanned** |

### Root Cause Hypotheses

1. **Deploy v823 reduced gRPC server concurrency on inventory-svc** — Confidence: `Hypothesis — needs corroboration: deploy event log + deploy diff`. Evidence: error onset 13s after a deployer-bot message, cluster restricted to inventory's `Reserve`, step-shaped onset (a step is more common with a deploy or config change than with exhaustion, which usually ramps — this supports the hypothesis, it does not establish it). The deploy timestamp itself is out of scope, so the 13-second gap cannot be verified from the scanned logs. Refuter: pod CPU/mem also stepped at 08:14:30. Next data: `kubectl describe pod` for resource limits, deploy diff for gRPC server options.
2. **inventory-svc database connection pool sized below new traffic** — Confidence: Hypothesis. Evidence: latency hits exactly 3000ms (a deadline budget, not a pool wait). Weaker than #1. Refuter: db wait events absent in this window.

### Recommendations

1. **Roll back inventory-svc to v822.** Owner: inventory team. Effort: S. Expected effect: **this is the test of hypothesis 1, not a guaranteed fix.** If the deploy is the trigger, `Reserve` deadlines should stop within a deploy cycle (~2–5 min); if they continue, hypothesis 1 is refuted and the cause is elsewhere — which is useful either way. Watch `Reserve` deadline rate, not just the checkout 502 rate, so the outcome is attributable.
2. **Run smoke load against v823 in staging at production concurrency.** Owner: inventory team. Effort: M. Expected effect: confirm or refute concurrency-cap hypothesis before re-rolling.
3. **`→ monitoring-alerting`**: add SLO burn-rate alert on `inventory-svc.Reserve.deadline_ratio`. Pattern was visible in logs but no page fired during the window.

### Suppressed Items
- **checkout-svc 502 storm (412 requests, 4.2%)** → symptom cluster of LOG-001, not an independent finding. Suppressed by cascade analysis, not by base rate. Re-open as its own finding if it survives the inventory-svc rollback.
- 87 lines of `level=warn msg="retrying after transient error"` in checkout-svc → healthy retry path (each request_id eventually returned 200 or 503, no abandoned retries). Suppressed by base rate.
- 12 lines `level=info msg="leader elected"` in inventory-svc → not failure-related.
- *(Nothing suppressed here falls in the base-rate-exempt categories — no security, data-integrity, financial, or invariant-violation lines were present in the window.)*

### Execution Status
- `Format`: slog JSON (both services)
- `Window`: `2026-04-28T08:00:00Z → 2026-04-28T09:00:00Z`
- `Files / queries scanned`: 23 pods × 1 hour ≈ 17.0 GB stream-piped
- `References loaded`: log-format-cheatsheet.md, log-correlation.md, log-cascade-analysis.md, log-pii-redaction.md, log-anti-patterns.md, log-analysis-quick-checklist.md
- `PII redaction applied`: yes — `redact_log.py write --json` over both streams, then `redact_log.py verify --json` on the redacted copies: clean. Categories: `bearer=4`, `json_key:authorization=4`. Internal-only report, so `user_id` / `tenant_id` kept for trace walking and blast radius (an external report would add `--mask-ip --redact-user-id` to **both** commands).
- `Statistical baseline`: previous-hour `2026-04-28T07:00:00Z → 08:00:00Z` (error_ratio < 0.01%; deploy-event-free)
- `Correlation IDs present`: trace_id ✓, request_id ✓, span_id ✓, user_id ✓
- `Gate outcomes`:
  - Gate 6 (Causation) — DEGRADE — deploy→outage link downgraded to `needs corroboration`; deploy event log not in scanned sources.
  - Gate 7 (Volume) — CAP — 1 Low finding routed to Residual Risk.
- `External tools run`: `kubectl logs` PASS, `jq` PASS, `redact_log.py` PASS, aggregator query Not run — no Loki/ELK/Datadog access in this environment
- `Permission prompts`: none required; frequency counting done with `jq -rs 'group_by(...)'` rather than `sort | uniq -c`

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
top_findings: [LOG-001, LOG-002]
leading_hypothesis: inventory-svc deploy v823 introduced a gRPC server concurrency cap; Reserve calls hit the 3-second deadline; downstream cascaded into 502s at gateway. The deploy link is unverified — the deploy event log was not scanned.
blameless_framing: The inventory service began exceeding its Reserve deadline under normal production traffic, and the checkout path had no fallback for a slow dependency. A deploy is the leading suspected trigger but is NOT established from the scanned logs — do not write the mechanism as fact in the post-mortem until the deploy diff is read.
```

### Summary
Confirmed from the scanned logs: `inventory-svc` `Reserve` gRPC deadlines starting 08:14:30 are the cause cluster; the checkout 502 storm is their symptom cluster. **Not** confirmed: that deploy `v823` caused it — the deploy timestamp came from outside the scanned sources, so that link and the concurrency-cap mechanism are both hypotheses. Next data: deploy event log + deploy diff + pod resource metrics for 08:14:00–08:15:00. 1 additional issue moved to Residual Risk.
