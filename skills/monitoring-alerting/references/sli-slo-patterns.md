# SLI/SLO Patterns for Production Services

<!-- toc -->

**Table of Contents**

- [1. SLI Selection by Service Type](#1-sli-selection-by-service-type)
  - [1.0 An SLI is not complete until valid and good events are both defined](#10-an-sli-is-not-complete-until-valid-and-good-events-are-both-defined)
  - [1.1 Define the event set ONCE, in recording rules](#11-define-the-event-set-once-in-recording-rules)
  - [Worker / Consumer (Kafka, message queue)](#worker--consumer-kafka-message-queue)
  - [Batch Job (cron, scheduled)](#batch-job-cron-scheduled)
- [2. SLO Target Setting](#2-slo-target-setting)
  - [Guidelines](#guidelines)
  - [Setting SLOs](#setting-slos)
- [3. Burn-Rate Alerting](#3-burn-rate-alerting)
  - [Concept](#concept)
  - [Multi-window, multi-burn-rate (Google SRE pattern)](#multi-window-multi-burn-rate-google-sre-pattern)
  - [Why multi-window](#why-multi-window)
- [4. Dashboard Layout Pattern (RED Method)](#4-dashboard-layout-pattern-red-method)
  - [Panel type selection](#panel-type-selection)

<!-- /toc -->

Service Level Indicators (SLIs) and Objectives (SLOs) are the foundation of
reliable monitoring. Without SLOs, alerts are arbitrary thresholds disconnected
from business impact.

---

## 1. SLI Selection by Service Type

### 1.0 An SLI is not complete until valid and good events are both defined

Every ratio SLI is `good_events / valid_events`, and **both halves are decisions**, not
defaults. Writing `non-5xx / total` skips two questions that change the number materially:

- **valid events** — what enters the denominator? Health checks, synthetic probes, requests
  the client cancelled, and traffic to an endpoint you do not own are usually *excluded*.
  Include them and your SLI measures your load balancer's opinion, not your users'.
- **good events** — what counts as success? 5xx is the obvious failure. Then decide, and
  write down: `429` (you shed load deliberately — often *not* a user-visible failure, but it
  is if the client had no way to retry), `499`/client-cancel (usually excluded from valid
  rather than counted bad), `401`/`403` (the user's fault, normally good), `400` (may signal
  *your* contract broke).

State both in the SLO document. An SLI whose exclusions are undocumented cannot be audited,
and two engineers will compute it differently.

### 1.1 Define the event set ONCE, in recording rules

Write the valid/good decision down as **recording rules**, then derive every SLI, error rate
and burn-rate alert from those. Repeating the selector inline in each expression is how
definitions drift: the moment you add `path!~"/health.*"` to availability and forget it in the
error-rate query, the two stop being complements of each other and nobody notices, because
both still look plausible.

```yaml
groups:
  - name: sli_events
    interval: 30s
    rules:
      # THE denominator. Every ratio below uses exactly this event set.
      # Exclusions are decisions -- change them here and everything follows.
      - record: sli:http_requests_valid:rate5m
        expr: |
          sum by (job) (rate(http_requests_total{path!~"/health.*|/metrics",code!="499"}[5m]))

      # bad = server fault. 4xx is the caller's fault and stays "good";
      # 499 (client cancelled) is excluded from valid entirely, above.
      - record: sli:http_requests_bad:rate5m
        expr: |
          sum by (job) (rate(http_requests_total{path!~"/health.*|/metrics",code!="499",code=~"5.."}[5m]))

      # fast = completed under the latency objective (400ms).
      # NOTE the selector is identical to the two rules above, `code!="499"` included --
      # and note the *separate denominator* below. See the caveat after this block.
      - record: sli:http_requests_fast:rate5m
        expr: |
          sum by (job) (rate(http_request_duration_seconds_bucket{path!~"/health.*|/metrics",code!="499",le="0.4"}[5m]))
      # The latency denominator must come from the SAME histogram, not from the request
      # counter: `le="+Inf"` is that histogram's own total.
      - record: sli:http_requests_latency_valid:rate5m
        expr: |
          sum by (job) (rate(http_request_duration_seconds_bucket{path!~"/health.*|/metrics",code!="499",le="+Inf"}[5m]))
```

**Latency numerator and denominator must come from the same histogram.** Dividing a
histogram bucket by the *request counter* is a category error even when both selectors match:
they are different instruments, sampled and exposed separately, so the ratio can drift and can
exceed 1. Worse, the first version of this section filtered `code!="499"` on the counter but
**not** on the bucket — so the "fast" numerator counted cancelled requests the denominator had
excluded, and `fast/valid > 1` was reachable. Use `le="0.4" / le="+Inf"` from one histogram.

**Instrumentation prerequisite, stated rather than assumed.** This only works if the histogram
actually carries the labels you need to exclude on (`code`, `path`). Many services expose
`http_request_duration_seconds_bucket` with *no* status label at all. If yours does not, you
cannot compute a valid-request latency SLI from it — say so explicitly and either
(a) add the label at the instrumentation layer, or (b) define the SLI on the events you *can*
isolate and record the exclusion you were unable to apply. What you must not do is present a
bucket ratio as a valid-request latency SLI when the bucket cannot distinguish valid requests.

**Burn-rate alerts need one pair per window, not one pair total.** A multi-window alert
compares a long and a short window, so `rate5m` alone cannot express it — and reusing the
5m pair on both sides silently degrades the alert to "the same window, twice", which looks
like a multi-window rule and behaves like a single-window one. Emit the pair for every window
your alert tiers use:

```yaml
groups:
  - name: sli_events_windows
    interval: 30s
    rules:
      # One valid/bad pair per burn-rate window. Same selector everywhere -- that is the
      # entire point; only the range differs.
      - record: sli:http_requests_valid:rate5m
        expr: sum by (job) (rate(http_requests_total{path!~"/health.*|/metrics",code!="499"}[5m]))
      - record: sli:http_requests_bad:rate5m
        expr: sum by (job) (rate(http_requests_total{path!~"/health.*|/metrics",code!="499",code=~"5.."}[5m]))
      - record: sli:http_requests_valid:rate1h
        expr: sum by (job) (rate(http_requests_total{path!~"/health.*|/metrics",code!="499"}[1h]))
      - record: sli:http_requests_bad:rate1h
        expr: sum by (job) (rate(http_requests_total{path!~"/health.*|/metrics",code!="499",code=~"5.."}[1h]))
      - record: sli:http_requests_valid:rate30m
        expr: sum by (job) (rate(http_requests_total{path!~"/health.*|/metrics",code!="499"}[30m]))
      - record: sli:http_requests_bad:rate30m
        expr: sum by (job) (rate(http_requests_total{path!~"/health.*|/metrics",code!="499",code=~"5.."}[30m]))
      - record: sli:http_requests_valid:rate6h
        expr: sum by (job) (rate(http_requests_total{path!~"/health.*|/metrics",code!="499"}[6h]))
      - record: sli:http_requests_bad:rate6h
        expr: sum by (job) (rate(http_requests_total{path!~"/health.*|/metrics",code!="499",code=~"5.."}[6h]))
```

The repetition is deliberate and mechanical — generate it from a template if you have many
tiers. What you must not do is hand-write the selector again per window, which is how the
exclusions drift back apart.

| SLI | Definition | PromQL (derived, never re-selected) |
|-----|------------|----------------|
| **Availability** | good / valid | `1 - (sli:http_requests_bad:rate5m / sli:http_requests_valid:rate5m)` |
| **Latency** | proportion of valid requests faster than the objective — not a percentile value | `sli:http_requests_fast:rate5m / sli:http_requests_latency_valid:rate5m` (both from one histogram) |
| **Error rate** | bad / valid — the exact complement of availability, because it is the same two series | `sli:http_requests_bad:rate5m / sli:http_requests_valid:rate5m` |

Availability and error rate now sum to 1 **by construction**. Burn-rate alerts (§3) use the
same pair, so a change to the exclusion list propagates to the alerts without a second edit.

One caveat on the latency recording rules: they fix `le="0.4"` to the objective, so changing
the objective means editing the rule and waiting for the new series to fill (and the bucket
boundary must exist in the histogram — `le="0.4"` is only available if the service was
configured with a 0.4 bucket). That is the
intended trade — the alternative is re-deriving the bucket selector in every alert, which is
the drift this section exists to prevent.

**Why latency is a proportion, not a percentile.** The SLO you can burn a budget against is
"99% of requests complete in under 400ms" — a *ratio of events*, so a bad event is countable
and a burn rate is computable. `histogram_quantile(0.99, ...)` returns a **duration**, which
gives you a dashboard number and a threshold alert but no error budget: there is no
"bad event" to count, and `quantile-of-a-rate` is additionally unsafe to average across
instances or re-aggregate over time. Keep `histogram_quantile` for dashboards; define the
*SLI* as the fast-request ratio.

**On the latency denominator, `le="+Inf"` vs `_count`.** They are numerically equal in a
well-formed histogram — `+Inf` is mandatory and holds every observation — so either is correct.
This file uses `le="+Inf"` **in the recording rules** for one reason: the numerator and
denominator then differ by a single label, so a reader can diff the two selectors at a glance
and `MA017` can demand they match exactly. `_count` is a different metric name, so a dropped
exclusion there is invisible to that comparison — which is precisely the defect this section
was written to close. Inline, outside a recording-rule pair, `_count` reads more clearly and is
fine; the worker and batch examples below use it. What matters is that a numerator and its
denominator come from the **same instrument with the same exclusions**, never that one spelling
is banned.

Google SRE, "Implementing SLOs", defines request latency the same way: the proportion of
requests faster than a threshold — https://sre.google/workbook/implementing-slos/

### Worker / Consumer (Kafka, message queue)

**First settle what `events_processed_total` counts.** `failed / processed` is ambiguous and
the two readings give different numbers:

- if `processed` counts **attempts** (successes *and* failures), then `failed / processed` is
  the success-rate complement and is correct as written;
- if `processed` counts **successes only** — which is how the name reads to most people, and
  how plenty of exporters implement it — then the denominator must be `success + failed`, and
  `failed / processed` overstates the failure ratio (it is `failed / success`).

Do not guess from the metric name. Read the instrumentation, then encode the answer in a
recording rule so nobody has to guess again:

```yaml
- record: sli:events_valid:rate5m          # attempts = the denominator
  expr: sum by (consumer_group) (rate(events_succeeded_total[5m]))
      + sum by (consumer_group) (rate(events_failed_total[5m]))
- record: sli:events_bad:rate5m
  expr: sum by (consumer_group) (rate(events_failed_total[5m]))
```

| SLI | Definition | PromQL Example |
|-----|------------|----------------|
| **Processing success ratio** | good / valid, on the attempts denominator above | `1 - (sli:events_bad:rate5m / sli:events_valid:rate5m)` |
| **Consumer lag** | Offset delta per partition — a **saturation** signal, not a ratio SLI | `max by (consumer_group, topic) (kafka_consumer_group_lag)` |
| **Freshness** | Age of the newest processed event; the SLI users actually feel | `time() - max by (consumer_group) (event_last_processed_timestamp_seconds)` |
| **Processing latency** | proportion of events processed within the objective | `sum(rate(event_processing_duration_seconds_bucket{le="30"}[5m])) / sum(rate(event_processing_duration_seconds_count[5m]))` |

Lag is deliberately *not* expressed as a ratio: there is no denominator, so it cannot carry an
error budget. Alert on it as saturation (with a `for`), and burn budget against the success
ratio and freshness.

### Batch Job (cron, scheduled)

A batch SLI has to answer "what fraction of **scheduled** runs met the objective", so the
denominator is *scheduled runs* — which a timestamp comparison cannot express.
`job_last_success_timestamp > (time() - 86400)` returns a boolean vector: it is a useful
**staleness / deadman** check, but it is not an SLI, because a run that never started produces
no series at all and therefore silently disappears from the measurement.

```yaml
# valid = runs the scheduler was supposed to start (emitted by the scheduler, NOT the job --
# a job that never ran cannot increment its own counter, which is exactly the failure mode)
- record: sli:batch_runs_scheduled:increase1d
  expr: sum by (job) (increase(batch_runs_scheduled_total[1d]))
- record: sli:batch_runs_ontime:increase1d
  expr: sum by (job) (increase(batch_runs_succeeded_within_sla_total[1d]))
```

| SLI | Definition | PromQL Example |
|-----|------------|----------------|
| **On-time completion** | on-time runs / scheduled runs | `sli:batch_runs_ontime:increase1d / sli:batch_runs_scheduled:increase1d` |
| **Staleness (deadman)** | how long since the last success — the check that catches "never started" | `time() - max by (job) (batch_last_success_timestamp_seconds)` |
| **Duration** | proportion of runs finishing inside the window | `sum(rate(batch_duration_seconds_bucket{le="3600"}[1d])) / sum(rate(batch_duration_seconds_count[1d]))` |
| **Correctness** | rows processed vs expected, per run | `batch_rows_processed / batch_rows_expected` |

You need **both** the ratio and the deadman. The ratio measures quality across runs that
happened; the deadman is the only thing that fires when the scheduler itself stopped.

---

## 2. SLO Target Setting

### Guidelines

**The minutes column is a *time-based* budget.** It is `(1 - SLO) x 30 days`, and it is the
right unit only when the SLI is time-based (a probe sampling "is the service up?" at a fixed
interval). A **request-based** SLI — the kind every PromQL example in this file uses — has a
budget denominated in *requests*: `(1 - SLO) x total_requests`. The two coincide only when
traffic is uniform, and diverge exactly when it matters: an outage during peak hour burns far
more request budget than the same wall-clock minutes at 4AM.

| Service tier | Availability SLO | Time-based budget (30 d) | Request-based budget at 1000 req/s |
|-------------|:---:|:---:|:---:|
| **Tier 1** (revenue-critical) | 99.99% | 4.3 minutes | ~259k failed requests |
| **Tier 2** (user-facing) | 99.9% | 43.2 minutes | ~2.59M failed requests |
| **Tier 3** (internal tooling) | 99.5% | 3.6 hours | ~13.0M failed requests |
| **Tier 4** (batch/analytics) | 99% | 7.2 hours | ~25.9M failed requests |

Always say which basis you are on. When you quote minutes for a request-based SLO, mark it
`request-based approximation under uniform traffic` — otherwise the number reads as a
downtime guarantee it does not provide.

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

Two different quantities get confused here, and mixing them up is the most common
burn-rate mistake. Both are simple arithmetic — derive them, never quote them from memory:

```
budget_consumed_over_window = burn_rate x (window / slo_window)
time_to_exhaust_at_this_rate = slo_window / burn_rate
```

For SLO = 99.9% over 30 days, the error budget is **0.1% of valid requests**. (The familiar
"~43.2 min/month" is the *time-based* budget for the same target; treating it as the
request-based budget is only valid as a `request-based approximation under uniform traffic`.)
Burn rate is a ratio of rates, so it is basis-independent — which is why it is the safer thing
to alert on:

| burn rate | budget consumed in 1 h | time to exhaust if sustained |
|---|---|---|
| 1.0 | 0.14% | 30 days — exactly the sustainable pace, no alert |
| 3.0 | 0.42% | 10 days |
| 6.0 | 0.83% | **5 days** |
| 14.4 | **2%** | **50 hours** (~2.1 days) |

So `14.4` is not "exhausts the budget in 2 hours". It is the rate at which **1 hour of
sustained burn spends 2% of the monthly budget** — and if it never stopped, the budget
would last 50 hours. The pair (14.4, 1 h) is chosen precisely so that 2% is gone before
a human needs to be woken; the urgency comes from the *fast consumption*, not from
imminent exhaustion.

**Sanity check any burn-rate claim before writing it down**: `30 days / 14.4 = 50 hours`,
`30 days / 6 = 5 days`. If a summary says a double-digit burn rate exhausts a 30-day
budget in a couple of hours, the arithmetic is wrong by more than an order of magnitude.

### Multi-window, multi-burn-rate (Google SRE pattern)

The four canonical tiers, with the budget each window spends. The long window decides
*whether* to alert; the short window is a "still happening now" gate that stops an alert
from lingering after the burn has stopped.

| Severity | Burn rate | Long window | Short window | Budget spent over long window |
|---|---|---|---|---|
| Page | 14.4 | 1 h | 5 m | 2% |
| Page | 6 | 6 h | 30 m | 5% |
| Ticket | 3 | 1 d | 2 h | 10% |
| Ticket | 1 | 3 d | 6 h | 10% |

Each short window is 1/12 of its long window. Reference: Google SRE Workbook,
"Alerting on SLOs" — https://sre.google/workbook/alerting-on-slos/

```yaml
# Page-worthy: high burn rate sustained over the LONG window AND still burning NOW.
# Both ratios derive from §1.1's recording rules, so the health/metrics/499 exclusions
# apply here identically -- and the two windows are genuinely different (1h and 5m).
- alert: SLOBurnRateHigh
  expr: |
    (
      sli:http_requests_bad:rate1h / sli:http_requests_valid:rate1h > (14.4 * 0.001)
      and
      sli:http_requests_bad:rate5m / sli:http_requests_valid:rate5m > (14.4 * 0.001)
    )
  for: 2m
  labels:
    severity: critical
  annotations:
    summary: "Error budget burn rate 14.4x — 2% of the 30-day budget spent in 1h (exhausts in ~50h if sustained)"
    runbook_url: "https://wiki.example.com/runbooks/slo-burn-rate"

# Warning: moderate burn rate over longer window
- alert: SLOBurnRateElevated
  expr: |
    (
      sli:http_requests_bad:rate6h / sli:http_requests_valid:rate6h > (6.0 * 0.001)
      and
      sli:http_requests_bad:rate30m / sli:http_requests_valid:rate30m > (6.0 * 0.001)
    )
  for: 15m
  labels:
    severity: warning
  annotations:
    summary: "Error budget burn rate 6x — 5% of the 30-day budget spent in 6h (exhausts in ~5 days if sustained)"
    runbook_url: "https://wiki.example.com/runbooks/slo-burn-rate"
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