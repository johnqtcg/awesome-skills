---
name: monitoring-alerting
description: >
  Monitoring and alerting design reviewer for production backend services. ALWAYS use
  when writing Prometheus alerting rules, designing Grafana dashboards, defining SLI/SLO,
  configuring alert routing (PagerDuty/OpsGenie/Slack), or reviewing existing monitoring
  setups. Covers SLI/SLO definition, alert rule quality (sensitivity/specificity tradeoff),
  burn-rate alerting, alert fatigue prevention, dashboard design principles, label
  cardinality management, and on-call routing configuration. Use even for "just add an
  alert" — a poorly designed alert either pages at 3AM for non-issues (alert fatigue)
  or stays silent during real outages (false confidence).
---

# Monitoring & Alerting Design Review

## Quick Reference

| If you need to…                        | Go to                                    |
|----------------------------------------|------------------------------------------|
| Understand what this skill covers      | §1 Scope                                 |
| Check mandatory prerequisites          | §2 Mandatory Gates                       |
| Choose review depth                    | §3 Depth Selection                       |
| Handle incomplete context              | §4 Degradation Modes                     |
| Evaluate monitoring design item by item| §5 Design Checklist                      |
| Avoid common alerting mistakes         | §6 Anti-Examples                         |
| Score the review result                | §7 Scorecard                             |
| Format review output                   | §8 Output Contract                       |
| Deep-dive SLI/SLO patterns            | `references/sli-slo-patterns.md`         |
| Understand alert anti-patterns         | `references/alert-anti-patterns.md`      |

---

## §1 Scope

**In scope** — monitoring and alerting for production backend services:

- SLI (Service Level Indicator) definition and measurement
- SLO (Service Level Objective) target setting and error budget
- Prometheus alerting rules (PromQL, `for` duration, severity labels)
- Burn-rate alerting (multi-window, multi-burn-rate SLO alerts)
- Grafana dashboard design (layout, variable templating, panel types)
- Alert routing configuration (PagerDuty/OpsGenie/Slack, severity-based routing)
- Alert fatigue audit (noise ratio, actionability, deduplication)
- Label cardinality management (high-cardinality label detection)
- On-call runbook integration (alert → runbook → action mapping)

**Out of scope** — delegate to dedicated skills:

- Metrics/tracing instrumentation in code → `go-observability-review`
- Application performance profiling → `go-benchmark`
- Infrastructure provisioning (Prometheus/Grafana setup) → ops tooling
- Log aggregation pipeline design → separate skill

---

## §2 Mandatory Gates

Execute gates sequentially. Each gate has a **STOP** condition.

### Gate 1: Context Collection

| Item | Why it matters | If unknown |
|------|----------------|------------|
| **Service type** (API / worker / batch / data pipeline) | Determines which SLIs are relevant | Must clarify |
| **Current SLIs/SLOs** (if any) | Building on existing or greenfield? | Assume greenfield |
| **Monitoring stack** (Prometheus/Datadog/CloudWatch) | Query language and alert config format differ | Assume Prometheus + Grafana |
| **On-call routing** (PagerDuty/OpsGenie/Slack/custom) | Determines alert destination config | Ask |
| **Traffic pattern** (steady / bursty / batch / cron) | Affects alert window sizing and threshold | Must clarify |
| **Current alert count** | Audit scope for alert fatigue | Ask; critical for review mode |

**STOP**: Cannot determine what the service does (no SLI candidates identifiable). Clarify before proceeding.

**PROCEED**: At least service type and traffic pattern known.

### Gate 2: Scope Classification

| Mode | Trigger | Output |
|------|---------|--------|
| **review** | User provides existing alerts/dashboards | Findings + improvement recommendations |
| **design** | User describes service needing monitoring | Complete SLI/SLO + alerts + dashboard spec |
| **audit** | User wants alert fatigue / noise analysis | Actionability report + reduction plan |

**STOP**: Request is about code instrumentation (not alert/dashboard design). Redirect to `go-observability-review`.

**PROCEED**: Monitoring/alerting design intent confirmed.

### Gate 3: Risk Classification

| Risk | Definition | Required action |
|------|-----------|-----------------|
| **SAFE** | New alert for non-critical service, dashboard addition | Standard review |
| **WARN** | Modifying existing production alerts, changing routing | Validate no coverage gap introduced |
| **UNSAFE** | Removing alerts, changing SLO targets, PagerDuty routing change | Impact assessment + rollback plan |

**STOP**: Any UNSAFE change without impact assessment.

**PROCEED**: Every change has risk level and mitigation.

### Gate 4: Output Completeness

Before delivering output, verify all §8 Output Contract sections present. §8.9 Uncovered Risks must never be empty.

---

## §3 Depth Selection

| Depth | When to use | Gates | References to load |
|-------|-------------|-------|-------------------|
| **Lite** | Single alert rule review, dashboard panel addition | 1–4 | None |
| **Standard** | Full SLI/SLO definition, alert suite for a service | 1–4 | `sli-slo-patterns.md` |
| **Deep** | Alert fatigue audit, multi-service monitoring architecture, burn-rate alerting | 1–4 | Both reference files |

**Force Standard or higher** when any signal appears:
SLO definition, burn-rate alerting, PagerDuty/OpsGenie routing, multi-service dashboard, alert fatigue investigation, label cardinality concern.

---

## §4 Degradation Modes

When context is incomplete, degrade gracefully — never guess traffic patterns.

| Available context | Mode | What you can do | What you cannot do |
|-------------------|------|-----------------|-------------------|
| Full (service type, SLIs, traffic, stack, routing) | **Full** | Complete SLI/SLO + alerts + dashboard | — |
| Service type known, traffic unknown | **Degraded** | SLI selection + alert rules; flag threshold unknowns | Set precise thresholds, window sizes |
| Only alert rules, no service context | **Minimal** | Static rule review (syntax, anti-patterns) | SLO alignment, routing review |
| No existing monitoring (greenfield) | **Planning** | Propose monitoring strategy from requirements | Review existing setup |

**Hard rule**: Never set alert thresholds without knowing the traffic pattern. A 1% error rate alert on a 10-QPS service fires on a single error; on a 10K-QPS service it means 100 errors/sec. In Degraded mode, flag all thresholds as "requires traffic data to validate" in §8.9.

---

## §5 Design Checklist

Execute every item. Mark **PASS** / **WARN** / **FAIL** with evidence.

### 5.1 SLI/SLO Foundation

1. **SLIs defined for the service** — every production service needs measurable SLIs. Standard SLIs by service type:
   - **API service**: availability (success ratio), latency (p50/p95/p99), error rate
   - **Worker/consumer**: processing rate, lag, error rate, processing latency
   - **Batch job**: completion rate, duration, data quality
   - **Data pipeline**: throughput, freshness, correctness

2. **SLOs set with error budget** — each SLI has a target (e.g., "99.9% availability over 30 days"). Error budget = 1 - SLO target (e.g., 0.1% = ~43 minutes/month of allowed downtime). SLOs must be agreed with stakeholders, not invented by engineers.

3. **Burn-rate alerting for SLOs** — instead of raw threshold alerts, use multi-window burn-rate alerts that fire when error budget is being consumed too fast. This dramatically reduces false positives. Load `references/sli-slo-patterns.md` for patterns.

### 5.2 Alert Rule Quality

4. **Every alert is actionable** — when this alert fires, is there a concrete action the on-call can take? If the answer is "look at it and hope it resolves," the alert should be a dashboard graph, not a page. Non-actionable alerts cause alert fatigue.

5. **`for` duration prevents flapping** — Prometheus `for` clause should be set to absorb transient spikes. Too short (e.g., `for: 1m` on a noisy metric) → flapping alerts. Too long (e.g., `for: 30m`) → delayed notification. Typical: `for: 5m` for warning, `for: 2m` for critical.

6. **Severity labels match routing** — alerts must have `severity: critical|warning|info` labels that map to routing rules. Critical → PagerDuty page. Warning → Slack channel. Info → dashboard only. Mislabeled severity causes either missed pages or unnecessary wake-ups.

7. **Alert includes runbook link** — every alerting rule should include an `annotations.runbook_url` pointing to a runbook with: what the alert means, how to diagnose, how to mitigate. Without runbooks, on-call responders waste time Googling their own alerts.

### 5.3 Dashboard Design

8. **Dashboard follows USE/RED method** — organize dashboards by signal type:
   - **USE** (infrastructure): Utilization, Saturation, Errors (CPU, memory, disk, network)
   - **RED** (services): Rate, Errors, Duration (request rate, error rate, latency)
   - Top row: golden signals overview. Detail rows: drill-down by endpoint/consumer/partition.

9. **Dashboard uses variables for templating** — Grafana variables (`$service`, `$namespace`, `$instance`) allow one dashboard to serve multiple instances. Avoid hardcoded label values in queries.

10. **No high-cardinality labels in dashboard queries** — labels like `user_id`, `request_id`, `trace_id` in PromQL queries explode time series count and crash Prometheus. Use bounded labels: `method`, `status_code`, `endpoint` (allowlisted).

### 5.4 Operations & Routing

11. **Alert routing matches severity** — critical alerts page on-call (PagerDuty/OpsGenie with escalation). Warning alerts go to team Slack channel. Info alerts are dashboard-only. No unrouted alerts.

12. **Deduplication and grouping configured** — Alertmanager `group_by` prevents firing 100 instances of the same alert. `group_wait` and `group_interval` control batch notification timing. Without grouping, a single incident generates N alerts for N instances.

13. **Inhibition rules prevent alert cascade** — if the database is down, suppress all "elevated error rate" alerts from services that depend on it. Without inhibition, one root cause generates dozens of symptomatic alerts.

14. **Alert fatigue metrics tracked** — measure: total alerts/week, alerts-per-on-call-shift, % of alerts that required action, MTTA (mean time to acknowledge). Target: <5 pages/week per on-call, >80% actionability rate.

---

## §6 Anti-Examples

### AE-1: Alert on absolute count instead of rate
```yaml
# WRONG: fires when 10 errors exist (even over 24 hours = normal)
- alert: HighErrorCount
  expr: http_errors_total > 10
# RIGHT: alert on error rate relative to traffic
- alert: HighErrorRate
  expr: rate(http_errors_total[5m]) / rate(http_requests_total[5m]) > 0.01
  for: 5m
```

### AE-2: No `for` duration — flapping on transient spike
```yaml
# WRONG: fires immediately on any spike, resolves in seconds, pages at 3AM
- alert: HighLatency
  expr: histogram_quantile(0.99, rate(http_duration_seconds_bucket[5m])) > 1
# RIGHT: require sustained condition
- alert: HighLatency
  expr: histogram_quantile(0.99, rate(http_duration_seconds_bucket[5m])) > 1
  for: 5m
```

### AE-3: Alert without runbook — on-call doesn't know what to do
```yaml
# WRONG: no annotations, no runbook
- alert: DatabaseConnectionPoolExhausted
  expr: db_pool_active >= db_pool_max
# RIGHT: include runbook and summary
- alert: DatabaseConnectionPoolExhausted
  expr: db_pool_active >= db_pool_max
  for: 2m
  annotations:
    summary: "DB connection pool exhausted on {{ $labels.instance }}"
    runbook_url: "https://wiki.example.com/runbooks/db-pool-exhausted"
```

### AE-4: user_id in PromQL label — cardinality explosion
```yaml
# WRONG: unique label per user → millions of time series
- record: user_request_duration
  expr: histogram_quantile(0.99, rate(http_duration_seconds_bucket{user_id!=""}[5m]))
# RIGHT: use bounded labels only (method, status_code, endpoint)
```

### AE-5: Critical alert routed to Slack only — no page
```yaml
# WRONG: critical alert goes to Slack where it drowns in messages
route:
  receiver: slack-team
  routes:
    - match: {severity: critical}
      receiver: slack-team  # should be pagerduty!
# RIGHT: critical → PagerDuty, warning → Slack
```

### AE-6: Monitoring gap reported as "system is stable"
```
WRONG: "No alerts fired this month, so the system is healthy"
RIGHT: "No alerts fired — verify alert coverage: are SLIs measured? Are thresholds correct? Absence of alerts ≠ absence of problems"
```

Extended anti-examples (AE-7 through AE-13) in `references/alert-anti-patterns.md`.

---

## §7 Monitoring Scorecard

### Critical — any FAIL means overall FAIL

- [ ] SLIs defined and measured for the service (availability, latency, error rate minimum)
- [ ] Every alert is actionable (clear action when it fires, not just "investigate")
- [ ] Alert severity labels match routing (critical → page, warning → Slack, info → dashboard)

### Standard — 4 of 5 must pass

- [ ] SLOs set with error budget and stakeholder agreement
- [ ] `for` duration set on all alerts to prevent flapping
- [ ] Runbook link included in alert annotations
- [ ] Dashboard follows USE/RED method with variable templating
- [ ] No high-cardinality labels in alert rules or dashboard queries

### Hygiene — 3 of 4 must pass

- [ ] Alert grouping and deduplication configured (Alertmanager `group_by`)
- [ ] Inhibition rules prevent alert cascade from single root cause
- [ ] Alert fatigue metrics tracked (alerts/week, actionability rate)
- [ ] Burn-rate alerting for SLO-critical services

**Verdict**: `X/12`; Critical: `Y/3`; Standard: `Z/5`; Hygiene: `W/4`.
PASS requires: Critical 3/3 AND Standard ≥4/5 AND Hygiene ≥3/4.

---

## §8 Output Contract

Every monitoring review MUST produce these sections. Write "N/A — [reason]" if inapplicable.

```
### 8.1 Context Gate
| Item | Value | Source |

### 8.2 Depth & Mode
[Lite/Standard/Deep] × [review/design/audit] — [rationale]

### 8.3 SLI/SLO Definition (Standard/Deep)
| SLI | Measurement | SLO Target | Error Budget |

### 8.4 Alert Rules
- Per alert: name, expr, for, severity, summary, runbook_url

### 8.5 Dashboard Spec (Standard/Deep)
- Panel layout, queries, variables, drill-down structure

### 8.6 Routing Configuration
- Severity → destination mapping
- Grouping, deduplication, inhibition rules

### 8.7 Alert Fatigue Assessment (audit mode)
- Total alerts/week, actionability %, recommendations

### 8.8 Runbook Mapping
| Alert | Runbook URL | Last Updated |

### 8.9 Uncovered Risks (MANDATORY — never empty)
| Area | Reason | Impact | Follow-up |
```

**Volume rules**:
- FAIL: always fully detailed
- WARN: up to 10; overflow to §8.9
- PASS: summary only
- §8.9 minimum: document all assumptions (especially traffic pattern if unknown)

**Scorecard summary** (append after §8.9):
```
Scorecard: X/12 — Critical Y/3, Standard Z/5, Hygiene W/4 — PASS/FAIL
Data basis: [full context | degraded | minimal | planning]
```

---

## §9 Reference Loading Guide

| Condition | Load |
|-----------|------|
| Standard or Deep depth | `references/sli-slo-patterns.md` |
| Deep depth, or alert fatigue / burn-rate signals | `references/alert-anti-patterns.md` |
| Deep depth, or routing / inhibition / grouping signals | `references/alertmanager-config-patterns.md` |