# SLI/SLO Patterns for Production Services

Service Level Indicators (SLIs) and Objectives (SLOs) are the foundation of
reliable monitoring. Without SLOs, alerts are arbitrary thresholds disconnected
from business impact.

---

## 1. SLI Selection by Service Type

### API Service (HTTP/gRPC)

| SLI | Measurement | PromQL Example |
|-----|-------------|----------------|
| **Availability** | Ratio of successful requests (non-5xx) | `sum(rate(http_requests_total{status!~"5.."}[5m])) / sum(rate(http_requests_total[5m]))` |
| **Latency** | p99 response time | `histogram_quantile(0.99, sum(rate(http_duration_seconds_bucket[5m])) by (le))` |
| **Error rate** | Ratio of 5xx responses | `sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))` |

### Worker / Consumer (Kafka, message queue)

| SLI | Measurement | PromQL Example |
|-----|-------------|----------------|
| **Processing rate** | Events processed per second | `rate(events_processed_total[5m])` |
| **Consumer lag** | Offset delta per partition | `kafka_consumer_group_lag` |
| **Processing latency** | Time from produce to consume | `histogram_quantile(0.99, rate(event_processing_duration_seconds_bucket[5m]))` |
| **Error rate** | Failed processing ratio | `rate(events_failed_total[5m]) / rate(events_processed_total[5m])` |

### Batch Job (cron, scheduled)

| SLI | Measurement | PromQL Example |
|-----|-------------|----------------|
| **Completion** | Did the job finish successfully? | `job_last_success_timestamp > (time() - 86400)` |
| **Duration** | How long did it take? | `job_duration_seconds` |
| **Data quality** | Rows processed vs expected | `job_rows_processed / job_rows_expected` |

---

## 2. SLO Target Setting

### Guidelines

| Service tier | Availability SLO | Error budget (30 days) |
|-------------|:---:|:---:|
| **Tier 1** (revenue-critical) | 99.99% | 4.3 minutes |
| **Tier 2** (user-facing) | 99.9% | 43.2 minutes |
| **Tier 3** (internal tooling) | 99.5% | 3.6 hours |
| **Tier 4** (batch/analytics) | 99% | 7.2 hours |

### Setting SLOs

1. **Start lower than you think** — 99.9% is harder than it sounds. Start at 99.5%, prove you can meet it, then tighten.
2. **Align with business impact** — if 15 minutes of downtime has no business impact, 99.99% is waste.
3. **Get stakeholder sign-off** — SLOs are contracts between engineering and business. Engineers don't set them alone.
4. **Review quarterly** — tighten if consistently met by large margin; loosen if error budget is always exhausted.

---

## 3. Burn-Rate Alerting

Traditional threshold alerts (e.g., "error rate > 1%") are noisy and disconnected
from business impact. Burn-rate alerts fire when the error budget is being consumed
faster than sustainable.

### Concept

```
burn_rate = actual_error_rate / allowed_error_rate
```

If SLO = 99.9% availability (error budget = 0.1%):
- burn_rate = 1.0 → consuming budget at exactly the allowed pace
- burn_rate = 14.4 → will exhaust 30-day budget in 2 hours (page immediately)
- burn_rate = 6.0 → will exhaust budget in 5 hours (page soon)
- burn_rate = 1.0 → on track (no alert)

### Multi-window, multi-burn-rate (Google SRE pattern)

```yaml
# Page-worthy: high burn rate sustained over short AND long window
- alert: SLOBurnRateHigh
  expr: |
    (
      sum(rate(http_requests_total{status=~"5.."}[1h])) / sum(rate(http_requests_total[1h])) > (14.4 * 0.001)
      and
      sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m])) > (14.4 * 0.001)
    )
  for: 2m
  labels:
    severity: critical
  annotations:
    summary: "Error budget burn rate is 14.4x — will exhaust 30-day budget in 2 hours"
    runbook_url: "https://wiki.example.com/runbooks/slo-burn-rate"

# Warning: moderate burn rate over longer window
- alert: SLOBurnRateElevated
  expr: |
    (
      sum(rate(http_requests_total{status=~"5.."}[6h])) / sum(rate(http_requests_total[6h])) > (6.0 * 0.001)
      and
      sum(rate(http_requests_total{status=~"5.."}[30m])) / sum(rate(http_requests_total[30m])) > (6.0 * 0.001)
    )
  for: 15m
  labels:
    severity: warning
```

### Why multi-window

- **Short window only** (5m): fires on transient spikes → noisy
- **Long window only** (6h): too slow to detect acute incidents
- **Both windows**: short window catches acute problems, long window confirms they're sustained

---

## 4. Dashboard Layout Pattern (RED Method)

```
┌─────────────────────────────────────────────────────┐
│ Row 1: Golden Signals Overview (single stat panels)  │
│ [Request Rate] [Error Rate] [p99 Latency] [Uptime]  │
├─────────────────────────────────────────────────────┤
│ Row 2: Request Rate (time series, by endpoint)       │
├─────────────────────────────────────────────────────┤
│ Row 3: Error Rate (time series, by status code)      │
├─────────────────────────────────────────────────────┤
│ Row 4: Latency Distribution (heatmap or histogram)   │
├─────────────────────────────────────────────────────┤
│ Row 5: Infrastructure (CPU, Memory, Goroutines)      │
├─────────────────────────────────────────────────────┤
│ Row 6: Dependencies (DB latency, Redis, Kafka lag)   │
└─────────────────────────────────────────────────────┘
Variables: $namespace, $service, $instance, $interval
```

### Panel type selection

| Metric type | Panel | Why |
|-------------|-------|-----|
| Rate (req/sec) | Time series | Show trends over time |
| Ratio (error %) | Gauge + Time series | Current value + trend |
| Latency | Heatmap | Shows distribution, not just percentile |
| Count (total errors) | Stat | Single number for at-a-glance |
| Saturation (CPU/mem) | Time series with thresholds | Show proximity to capacity |