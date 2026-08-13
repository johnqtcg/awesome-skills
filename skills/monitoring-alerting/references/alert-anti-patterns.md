# Alert Anti-Patterns

<!-- toc -->

**Table of Contents**

- [0.0 `count()` over an empty vector is silent, not zero](#00-count-over-an-empty-vector-is-silent-not-zero)
- [0.1 Is this page-worthy? Redundancy and headroom, not the signal name](#01-is-this-page-worthy-redundancy-and-headroom-not-the-signal-name)
- [0. Does this alert need a `for` duration?](#0-does-this-alert-need-a-for-duration)
- [AE-7: Alerting on symptoms instead of SLIs](#ae-7-alerting-on-symptoms-instead-of-slis)
- [AE-8: Same threshold for all environments](#ae-8-same-threshold-for-all-environments)
- [AE-9: Alert that can never auto-resolve](#ae-9-alert-that-can-never-auto-resolve)
- [AE-10: Duplicate alerts at different thresholds](#ae-10-duplicate-alerts-at-different-thresholds)
- [AE-11: Dashboard with 50+ panels — information overload](#ae-11-dashboard-with-50-panels--information-overload)
- [AE-12: Alert on p50 latency — misses tail latency problems](#ae-12-alert-on-p50-latency--misses-tail-latency-problems)
- [AE-13: No correlation between alerts and dashboards](#ae-13-no-correlation-between-alerts-and-dashboards)

<!-- /toc -->

## 0.0 `count()` over an empty vector is silent, not zero

The trap that makes an all-instances-down alert fire in every case except the one that matters.
**Verified with `promtool test rules`, not reasoned about** — the cases live in
`tests/promtool/rules_test.yml`:

| Expression | All targets `up=0` | Series gone from discovery |
|---|---|---|
| `count(up{job="x"} == 1) == 0` | **silent** — `up == 1` is empty, `count()` of empty returns *no result*, and `empty == 0` is empty | **silent** |
| `sum(up{job="x"}) == 0` | fires (sum is 0) | **silent** — sum of nothing is empty |
| `absent(up{job="x"})` | silent (the series exist) | fires |
| `sum(up{job="x"}) == 0 or absent(up{job="x"})` | fires | fires |

So "are all replicas down" needs **both** halves:

```promql
sum(up{job="order-api"}) == 0 or absent(up{job="order-api"})
```

The general rule: **an aggregation over an empty vector produces an empty vector, not 0.** Any
alert shaped like "count/sum of a filtered series compared to zero" is therefore silent when the
filter matches nothing — usually the very failure you wanted to catch. `absent()` exists for the
missing-series case; reach for it whenever the alert's premise is *the absence of something*.

## 0.1 Is this page-worthy? Redundancy and headroom, not the signal name

The forward eval showed an agent state this principle correctly and violate it in the same answer: it explained that `up` is telemetry rather than customer impact, then set a single-replica `up == 0` to `severity: critical` on the platform on-call. Knowing a principle and applying it are different things.

- **One replica of N down (N>1), others healthy** → `warning` / ticket. Redundancy absorbed it; capacity is affected, users are not. Page only if losing a second would breach the SLO.
- **All replicas down, or a single-instance service down** → `critical` / page. No redundancy left, so this *is* user impact.
- **External synthetic probe failing** → `critical` / page. It measures what the user experiences, not what a scrape target reports.
- **Burn-rate alert** → per the tier table (`sli-slo-patterns.md` §3); impact is already quantified as budget spend.

Two questions settle almost every case: **how many replicas remain**, and **how much deadline headroom** is left before the SLO is threatened. Comfortable on both → ticket. State which you used: "paged because 3/3 replicas down" is reviewable, "paged because up == 0" is not.

## 0. Does this alert need a `for` duration?

**Whether `for` is needed depends on whether the expression already expresses duration** — and "it looks like a liveness check" is not the same thing:

| Expression | `for` needed? | Why |
|---|---|---|
| `vector(1)` watchdog | **No** | Always firing by construction; an external system alerts on its *disappearance*, so there is nothing to debounce |
| `up == 0` | **Yes** — default `for: 5m` | True after a **single** failed scrape. One dropped packet pages someone. Prometheus's own canonical example is `expr: up == 0` + `for: 5m` |
| `absent_over_time(m[5m])` | **No** | The `[5m]` range *is* the duration; adding `for` doubles the delay |
| `absent(m)` | **Judge it** | Fires as soon as the series is missing at one evaluation. Whether that is enough depends on scrape interval and staleness (a series is stale ~5m after its last sample), so reason from those two numbers rather than from the function name |
| Discrete safety event (cert expired, disk read-only) | **Usually no** | One observation is the incident — but ask whether the *check* can be flaky. "Replication broken" is often a scraped gauge that blips during a failover, so a short `for: 2m` there suppresses a self-healing switchover without delaying a real break |
| `increase(...[15m]) > N`, or a burn-rate long window | **Optional** — a short `for` is still reasonable | The range window supplies the damping, so `for` is not doing the debouncing. A short `for` (1–2 evaluation intervals) still helps: it absorbs evaluation-time jitter as a series crosses the threshold, and avoids firing off one unlucky evaluation. This is why §3's burn-rate examples carry `for: 2m` / `for: 15m` — **not** a contradiction of this row. What you must not do is set a `for` comparable to the long window itself, which doubles time-to-detect |

Prometheus reference for the `up == 0` + `for: 5m` pairing:
https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/

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
**Fix**: do not **page** on CPU. It is legitimate at lower urgency, and the distinction is
the urgency tier, not the metric:

| Tier | CPU-based alert | Why |
|---|---|---|
| **Page** | No | High CPU with healthy latency and error rate is not a customer problem; and the service can be broken at low CPU (deadlock, upstream stall) |
| **Ticket** | Yes — sustained saturation, e.g. `> 0.85` for `for: 30m` | Predicts a problem days out; someone should resize during business hours |
| **Capacity warning** | Yes — trend, e.g. `predict_linear(...[6h], 4*24*3600) > 0.9` | Feeds capacity planning, not the on-call rotation |

Page on the symptom the user feels (latency, errors, burn rate); use CPU to explain *why*,
and to open a ticket before saturation becomes an outage.

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
  expr: histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le)) > 0.5
- alert: LatencyHigh
  expr: histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le)) > 1.0
- alert: LatencyCritical
  expr: histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le)) > 2.0
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
  expr: histogram_quantile(0.50, sum(rate(http_request_duration_seconds_bucket[5m])) by (le)) > 0.5
  # 50% of requests are fast, but 5% take 10 seconds → p50 is fine
```

**Right**: Alert on p99 or p95 — tail latency affects the worst user experience:
```yaml
- alert: HighP99Latency
  expr: histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le)) > 2.0
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