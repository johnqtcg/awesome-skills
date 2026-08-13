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
allowed-tools: Read, Write, Grep, Glob, Bash(promtool*), Bash(amtool*)
---

# Monitoring & Alerting Design Review

## Quick Reference

| If you need to…                        | Go to                                    |
|----------------------------------------|------------------------------------------|
| Scope / prerequisites / depth          | §1, §2 Gates, §3 Depth                   |
| Handle incomplete context              | §4 Degradation Modes                     |
| Evaluate the design item by item       | §5 Design Checklist                      |
| Validate rules before shipping         | §5.5 Rule Validation                     |
| Avoid common alerting mistakes         | §6 Anti-Examples                         |
| Score, then format the output          | §7 Scorecard, §8 Output Contract         |
| SLI/SLO, burn-rate, error budget       | `references/sli-slo-patterns.md`         |
| Alert anti-patterns and fatigue        | `references/alert-anti-patterns.md`      |
| Routing / grouping / inhibition config | `references/alertmanager-config-patterns.md` |

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

**STOP**: The request needs service context that is unavailable *and* unobtainable — no SLI candidates identifiable and the user cannot describe the service. Clarify before proceeding.

**PROCEED**, at the depth the context supports (this gate selects a §4 mode, it does not require full context):

| Context available | Proceed as | Ceiling |
|---|---|---|
| Service type **and** traffic pattern | **Full** | no restriction |
| Service type only | **Degraded** | no precise thresholds or window sizes |
| Neither — only alert rules pasted in | **Minimal** | static rule review only: syntax, anti-patterns, missing annotations. **No** SLO alignment, threshold, or routing verdicts |
| Greenfield, requirements only | **Planning** | strategy proposal, no review of existing setup |

Minimal mode is a legitimate entry point, not a gate failure — a pasted alert rule can be
checked for a missing runbook or an absolute-count expression without knowing the service.
What Minimal must not do is emit a threshold or an SLO verdict; those go to §8.9 as
"requires service context". See §4 for the full matrix.

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
| **Deep** | Alert fatigue audit, multi-service monitoring architecture, burn-rate alerting | 1–4 | All three reference files |

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

**Hard rule**: Never set alert thresholds without knowing the traffic pattern **and the evaluation window** — a ratio threshold is meaningless without both. At 10 QPS a `[1m]` window sees ~600 requests, so 1% needs 6 errors; a `[10s]` window sees ~100, so a **single** error crosses 1%. At 10K QPS the same 1% means ~100 errors/sec. The rule of thumb: `min_errors_to_trip = threshold x QPS x window_seconds`; when that number is below ~5, the alert is measuring noise. In Degraded mode, flag all thresholds as "requires traffic data to validate" in §8.9.

---

## §5 Design Checklist

Execute every item. Mark **PASS** / **WARN** / **FAIL** with evidence.

### 5.1 SLI/SLO Foundation

1. **SLIs defined for the service** — every production service needs measurable SLIs, and each ratio SLI needs **both** halves defined: which events are *valid* (denominator — exclude health checks, synthetic probes, client cancellations) and which are *good* (numerator — decide explicitly how `429`/`499`/`4xx` are treated). Undocumented exclusions make an SLI unauditable. Standard SLIs by service type:
   - **API service**: availability (good/valid ratio), latency as the **proportion of requests under a threshold** (e.g. 99% < 400ms — not a raw p99 value, which has no countable bad event to burn a budget against), error rate
   - **Worker/consumer**: processing rate, lag, error rate, processing latency
   - **Batch job**: completion rate, duration, data quality
   - **Data pipeline**: throughput, freshness, correctness

2. **SLOs set with error budget, on a stated basis** — each SLI has a target (e.g. "99.9% availability over 30 days") and `error budget = 1 - SLO`. **Say which basis the budget is in**: a *time-based* SLO converts directly to minutes (0.1% of 30 days = 43.2 min); a *request-based* SLO's budget is 0.1% of **valid requests**, which equals those minutes only under uniform traffic. Quoting minutes for a request-based SLO without that caveat promises a downtime guarantee the SLO does not make. SLOs must be agreed with stakeholders, not invented by engineers.

3. **Burn-rate alerting for SLOs** — instead of raw threshold alerts, use multi-window burn-rate alerts that fire when error budget is being consumed too fast. This dramatically reduces false positives. Load `references/sli-slo-patterns.md` for patterns.

### 5.2 Alert Rule Quality

4. **Every alert is actionable** — when this alert fires, is there a concrete action the on-call can take? If the answer is "look at it and hope it resolves," the alert should be a dashboard graph, not a page. Non-actionable alerts cause alert fatigue.

5. **`for` duration prevents flapping** — `for` is **optional** in Prometheus (omitted means fire on the first evaluation where the expression is true). Default to setting it, because absorbing transient spikes is what stops 3AM flapping: typical `for: 5m` for warning, `for: 2m` for critical. Too short on a noisy metric → flapping; too long (e.g. `for: 30m`) → delayed notification.

   **Whether `for` is needed depends on whether the expression already expresses duration** — "it looks like a liveness check" is not the same thing. `up == 0` is true after a **single** failed scrape, so it needs `for` (Prometheus's own canonical example is `up == 0` + `for: 5m`); a `vector(1)` watchdog needs none, because it is always firing and is alerted on by its *absence*. Full decision table, including `absent()` vs `absent_over_time()`: `alert-anti-patterns.md` §0.

   Flag a missing `for` as WARN, not FAIL, and name which row above you applied.

5b. **Page-worthiness comes from user impact and redundancy, not from the signal** — the gap the forward eval exposed: an agent explained that `up` is telemetry rather than customer impact, then set a single-replica `up == 0` to `severity: critical` on the platform on-call in the same answer. Two questions decide it: **how many replicas remain**, and **how much deadline headroom** is left before the SLO is threatened. One of six replicas down is a ticket; all replicas down, a single-instance service, or a failing external probe is a page. State which you used — "paged because 3/3 replicas down" is reviewable, "paged because up == 0" is not. Full table: `alert-anti-patterns.md` §0.1.

6. **Severity labels match routing** — every alert carries a severity label from a **closed, documented set**, and every value in that set maps to exactly one **routing policy**. A policy is not a single destination: it has one primary action receiver (the thing that gets a human to act) plus zero or more secondary receivers for visibility, which is exactly what `continue: true` fan-out expresses (`alertmanager-config-patterns.md` §4). What must be unambiguous is *who acts*, not *how many places see it*. The common mapping is `critical` → page, `warning` → chat, `info` → dashboard, and the common tooling is PagerDuty/OpsGenie + Slack — but that is this skill's **default example, not a requirement**. Some orgs page from Slack with a bot, split `critical` into business hours vs out of hours, or have no `info` tier at all. What is actually reviewable: (a) the mapping is written down, (b) no severity value is unrouted, (c) nothing that pages a human is only sent somewhere nobody watches at 3AM. When the user states their own mapping, review against **theirs**.

7. **Alert includes runbook link** — every alerting rule should include an `annotations.runbook_url` pointing to a runbook with: what the alert means, how to diagnose, how to mitigate. Without runbooks, on-call responders waste time Googling their own alerts.

### 5.3 Dashboard Design

8. **Dashboard follows USE/RED method** — organize dashboards by signal type:
   - **USE** (infrastructure): Utilization, Saturation, Errors (CPU, memory, disk, network)
   - **RED** (services): Rate, Errors, Duration (request rate, error rate, latency)
   - Top row: golden signals overview. Detail rows: drill-down by endpoint/consumer/partition.

9. **Dashboard uses variables for templating** — Grafana variables (`$service`, `$namespace`, `$instance`) allow one dashboard to serve multiple instances. Avoid hardcoded label values in queries.

10. **No unbounded labels in dashboard queries** — get the causality right, because it decides where the fix goes. **Series count is created at instrumentation time**: an unbounded label (`user_id`, `trace_id`, full URL path) attached in application code multiplies series whether or not anything queries it. A query cannot create series — it can only load a huge number at once (slow panels, query-path memory, plausible OOM). So a query over an unbounded label is a **symptom to flag**, the real fix belongs in instrumentation (`go-observability-review`), and the dashboard-side fix is to aggregate away (`sum by (status_code)`) or filter to a bounded set. Use `method`, `status_code`, route **template** (`/users/:id`, not `/users/12345`).

### 5.4 Operations & Routing

11. **Alert routing matches severity** — no orphan alerts: every severity value in use resolves to a receiver, and the root route has a catch-all. Verify against the org's own mapping (§5.2 item 6) rather than assuming PagerDuty/Slack. The one non-negotiable: anything defined as page-worthy must reach a channel with an escalation path, not only a chat room.

12. **Deduplication and grouping configured** — `group_by` does **not** stop alert instances from firing; Prometheus still evaluates and fires one alert per label set, and they all appear in the Alertmanager UI and API. What grouping changes is **notification volume**: instances sharing the `group_by` labels are batched into one notification instead of N. `group_wait` sets how long to wait for more members of a new group, `group_interval` how long before sending an update for a group that already notified. Without grouping, one incident across N instances becomes N pages.

13. **Inhibition rules prevent alert cascade** — if the database is down, suppress all "elevated error rate" alerts from services that depend on it. Without inhibition, one root cause generates dozens of symptomatic alerts.

14. **Alert fatigue metrics tracked** — measure: total alerts/week, alerts-per-on-call-shift, % of alerts that required action, MTTA (mean time to acknowledge). Target: <5 pages/week per on-call, >80% actionability rate.

### 5.5 Rule Validation (Eat Your Own Dog Food)

A skill that preaches "no false positives, no silent gaps" must validate its rules mechanically, not by eyeball:

15. **Rules pass `promtool check rules alerts.yml`** — syntax + PromQL validation before any rule ships.

16. **SLO-critical alerts have `promtool test rules` unit tests** — Prometheus natively asserts "given this input series, this alert fires (or stays silent)". That is the executable form of the sensitivity/specificity tradeoff, and it is the only thing that catches a wrong window pairing or a wrong `for`, both of which parse perfectly. Write at least two cases per SLO-critical alert: one where it MUST fire, one where it MUST stay silent.

    A **third** case matters more than either: the alert must **stop** firing once the burn stops. A brief spike is silent whether the rule is single- or multi-window, so only "burn ended, must stop paging" proves the short-window gate is doing anything. Working example with all five cases (fire / silent / spike absorbed / health-checks excluded / clears after recovery), runnable as-is: [`tests/promtool/rules_test.yml`](tests/promtool/rules_test.yml).

17. **Routing config passes `amtool check-config alertmanager.yml`** — validate routing/inhibition changes before deploy.

If promtool/amtool are unavailable in the environment, state `Not run — <tool> unavailable` in §8.4 and list the exact commands for the user; never claim rules are validated without running them.

**A skip is not a pass** — for this skill's own suite too: `run_regression.sh` prints how many external validators ran and says `PASS (text layer only)` when that is zero. Report the same way.

18. **Burn-rate arithmetic is derived, never quoted.** `budget_consumed = burn_rate x window / slo_window`; `time_to_exhaust = slo_window / burn_rate`. These get confused constantly: for a 30-day SLO a 14.4x burn spends 2% of budget per hour and takes ~50 hours to exhaust it — **not** 2 hours. Compute both before writing either into a summary (`scripts/lint_monitoring_docs.py` checks every such claim here against the formulas).

---

## §6 Anti-Examples

### AE-1: Alert on absolute count instead of rate
```yaml
# WRONG: fires when 10 errors exist (even over 24 hours = normal)
- alert: HighErrorCount
  expr: http_errors_total > 10
# RIGHT: rate relative to traffic — and complete, because a RIGHT example is copied
- alert: HighErrorRate
  expr: rate(http_errors_total[5m]) / rate(http_requests_total[5m]) > 0.01
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "Error ratio above 1% on {{ $labels.job }}"
    runbook_url: "https://wiki.example.com/runbooks/high-error-rate"
```
Check the threshold against traffic before shipping: at 10 QPS a `[5m]` window sees ~3000
requests, so 1% is ~30 errors — meaningful. At 1 QPS it is 3, which is noise (§4).

### AE-2: No `for` duration — flapping on transient spike
```yaml
# WRONG: fires immediately on any spike, resolves in seconds, pages at 3AM
- alert: HighLatency
  expr: histogram_quantile(0.99, rate(http_duration_seconds_bucket[5m])) > 1
# RIGHT: require a sustained condition, and route it
- alert: HighLatency
  expr: histogram_quantile(0.99, rate(http_duration_seconds_bucket[5m])) > 1
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "p99 latency above 1s on {{ $labels.job }}"
    runbook_url: "https://wiki.example.com/runbooks/high-latency"
```
This is a threshold alert on a percentile — fine as a symptom page. It is **not** an SLI: to
burn an error budget you need the *proportion of requests under the threshold* instead
(`sli-slo-patterns.md` §1.1).

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

### AE-5: Page-worthy alert routed to chat only — no escalation
```yaml
# WRONG: two problems. (a) page-worthy severity lands in a chat channel with no
# escalation, where it drowns in messages; (b) `match` is the deprecated form.
route:
  receiver: slack-team
  routes:
    - match: {severity: critical}
      receiver: slack-team
# RIGHT: modern `matchers`, and page-worthy severity reaches an escalation path
route:
  receiver: slack-team
  routes:
    - matchers: ['severity = "critical"']
      receiver: pagerduty-oncall
```
The receiver *names* are this skill's default example — review against the org's own
severity → receiver mapping. What is never acceptable is a page-worthy alert whose only
destination has no escalation.

### AE-6: Monitoring gap reported as "system is stable"
WRONG: "no alerts fired this month, so the system is healthy". RIGHT: "no alerts fired — verify coverage first: are the SLIs measured, are the thresholds right? Absence of alerts ≠ absence of problems."

Extended anti-examples (AE-7 through AE-13) in `references/alert-anti-patterns.md`.

---

## §7 Monitoring Scorecard

### Critical — any FAIL means overall FAIL

- [ ] SLIs defined and measured, **matching the service type** (§5.1) — API: availability + latency + error rate; worker/consumer: lag + processing success rate; batch: on-time completion + correctness; pipeline: freshness + coverage + correctness. Judging a batch job against `availability, latency, error rate` fails a well-designed batch job for lacking SLIs it should not have
- [ ] Every alert is actionable (clear action when it fires, not just "investigate")
- [ ] Alert severity labels match routing — every severity value maps to a receiver under the org's own documented mapping, and page-worthy alerts reach a channel with escalation

### Standard — 4 of 5 must pass

- [ ] SLOs set with error budget and stakeholder agreement
- [ ] `for` duration set on every alert that needs damping, or a stated reason it is omitted (deadman, discrete safety event, expression already integrates over time — §5.2 item 5)
- [ ] Runbook link included in alert annotations
- [ ] Dashboard follows USE/RED method with variable templating
- [ ] No unbounded labels in alert rules or dashboard queries (and the fix is routed to instrumentation, not just to the query)

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
- Validation evidence: `promtool check rules` / `promtool test rules` output,
  or `Not run — <tool> unavailable` + exact commands for the user

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

**Volume rules**: FAIL always fully detailed; WARN up to 10 with overflow to §8.9; PASS summary only; §8.9 must document every assumption (especially an unknown traffic pattern).

**Scorecard summary** (append after §8.9):
```
Scorecard: X/12 — Critical Y/3, Standard Z/5, Hygiene W/4 — PASS/FAIL
Data basis: [full context | degraded | minimal | planning]
```

---

## §9 Reference Loading Guide

§3's depth table sets the baseline. Load one reference early, regardless of depth, when its
signal appears: `sli-slo-patterns.md` for SLO or burn-rate work, `alert-anti-patterns.md`
for alert-fatigue investigation, `alertmanager-config-patterns.md` for routing, grouping or
inhibition.