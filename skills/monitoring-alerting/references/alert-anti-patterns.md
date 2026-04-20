# Alert Anti-Patterns

Extended anti-patterns beyond the inline AE-1 through AE-6 in SKILL.md.

---

## AE-7: Alerting on symptoms instead of SLIs

```yaml
# WRONG: alert on CPU usage — symptom, not customer impact
- alert: HighCPU
  expr: instance:cpu_utilization:ratio > 0.90
  for: 5m
  labels:
    severity: critical
```

**Problem**: High CPU doesn't necessarily mean degraded service. The service
may be performing normally at high CPU. Conversely, the service can be broken
with low CPU (deadlock, network issue).

**Right**: Alert on SLIs (error rate, latency) that reflect customer impact.
Use CPU as a diagnostic dashboard panel, not an alert trigger.

---

## AE-8: Same threshold for all environments

```yaml
# WRONG: production threshold applied to staging
- alert: HighErrorRate
  expr: rate(http_errors_total[5m]) / rate(http_requests_total[5m]) > 0.01
  # This fires constantly in staging where traffic is 10 req/min
```

**Problem**: Low-traffic environments have noisy ratios — 1 error in 10 requests = 10% error rate.

**Right**: Separate alert definitions per environment, or use `min_samples` predicate:
```yaml
expr: |
  (rate(http_errors_total[5m]) / rate(http_requests_total[5m]) > 0.01)
  and
  (rate(http_requests_total[5m]) > 1)  # minimum traffic threshold
```

---

## AE-9: Alert that can never auto-resolve

```yaml
# WRONG: based on counter total, which only increases
- alert: TooManyErrors
  expr: http_errors_total > 1000
  # Once 1000 errors accumulated (even over weeks), this fires forever
```

**Right**: Use `rate()` or `increase()` for counters:
```yaml
- alert: HighErrorRate
  expr: increase(http_errors_total[1h]) > 100
```

---

## AE-10: Duplicate alerts at different thresholds

```yaml
# WRONG: three alerts for the same condition
- alert: LatencyWarning
  expr: histogram_quantile(0.99, ...) > 0.5
- alert: LatencyHigh
  expr: histogram_quantile(0.99, ...) > 1.0
- alert: LatencyCritical
  expr: histogram_quantile(0.99, ...) > 2.0
# When latency = 3s, ALL THREE fire simultaneously
```

**Right**: Use severity labels on a single alert, or use Alertmanager inhibition
so that Critical suppresses Warning and High.

---

## AE-11: Dashboard with 50+ panels — information overload

```
WRONG: single dashboard with CPU, memory, disk, network, goroutines, GC,
       DB connections, Redis, Kafka, HTTP methods × status codes × endpoints
       = 50+ panels that nobody reads
```

**Right**: Layer dashboards by audience:
- **L1 Overview** (on-call): 4-6 golden signal panels → "is it broken?"
- **L2 Service** (team): 10-15 panels → "what part is broken?"
- **L3 Debug** (deep dive): detailed breakdown → "why is it broken?"

---

## AE-12: Alert on p50 latency — misses tail latency problems

```yaml
# WRONG: p50 (median) hides tail latency issues
- alert: HighLatency
  expr: histogram_quantile(0.50, ...) > 0.5
  # 50% of requests are fast, but 5% take 10 seconds → p50 is fine
```

**Right**: Alert on p99 or p95 — tail latency affects the worst user experience:
```yaml
- alert: HighP99Latency
  expr: histogram_quantile(0.99, ...) > 2.0
  for: 5m
```

---

## AE-13: No correlation between alerts and dashboards

```
WRONG: alert fires "HighErrorRate on payment-service"
       On-call opens Grafana, searches for "payment" → no dashboard found
       On-call spends 15 minutes finding the right graph
```

**Right**: Every alert annotation includes:
```yaml
annotations:
  dashboard_url: "https://grafana.example.com/d/abc123?var-service=payment-service"
  runbook_url: "https://wiki.example.com/runbooks/payment-high-error-rate"
```

Link directly to the relevant dashboard WITH pre-filled variables.