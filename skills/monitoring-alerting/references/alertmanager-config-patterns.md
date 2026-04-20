# Alertmanager Configuration Patterns

## 1. Route Tree Design

Alertmanager routes form a tree. The root route matches all alerts; child routes refine by label matchers. Evaluation is top-down, first-match-wins (unless `continue: true`).

```yaml
route:
  receiver: default-slack
  group_by: ['alertname', 'severity']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  routes:
    # Critical → PagerDuty with escalation
    - match:
        severity: critical
      receiver: pagerduty-oncall
      repeat_interval: 5m
      routes:
        - match_re:
            service: ^(payments|auth)$
          receiver: pagerduty-platform-critical

    # Warning → team Slack channel
    - match:
        severity: warning
      receiver: team-slack
      repeat_interval: 1h

    # Info → no notification, dashboard only
    - match:
        severity: info
      receiver: blackhole
```

**Key rules:**
- Every alert must match a route — orphan alerts indicate a routing gap
- `match` is exact string equality; `match_re` supports regex
- Child routes inherit parent's `group_by` / intervals unless overridden

## 2. group_by / group_wait / group_interval Tuning

These three parameters control how Alertmanager batches notifications.

| Parameter | Purpose | Bad Value | Good Value |
|-----------|---------|-----------|------------|
| `group_by` | Which labels define a group | `['...']` (wildcard — every combo is its own group) | `['alertname', 'severity']` or `['alertname', 'cluster']` |
| `group_wait` | Delay before sending first notification for a new group | `0s` (instant — no batching) | `30s` (collect related alerts) |
| `group_interval` | Minimum wait before sending updates to an existing group | `0s` | `5m` |
| `repeat_interval` | How often to re-send if alert is still firing | `1m` (spammy) | `4h` for warning, `5m` for critical |

**Anti-pattern — wildcard grouping:**
```yaml
# BAD: every label combination creates a separate notification
group_by: ['...']
group_wait: 0s
# DB outage → 50 instances fire HighErrorRate → 50 separate pages
```

**Correct grouping:**
```yaml
# GOOD: same alert + severity batched into one notification
group_by: ['alertname', 'severity']
group_wait: 30s
group_interval: 5m
# DB outage → 50 instances fire HighErrorRate → 1 notification listing all 50
```

## 3. Inhibition Rules

Inhibition suppresses target alerts when a source alert is firing. This prevents alert cascading from a single root cause.

```yaml
inhibit_rules:
  # If DatabaseDown fires, suppress HighErrorRate on dependent services
  - source_matchers:
      - alertname = DatabaseDown
    target_matchers:
      - alertname = HighErrorRate
    equal: ['cluster', 'namespace']
    # Only inhibit when source and target share the same cluster + namespace

  # If NodeDown fires, suppress all pod-level alerts on that node
  - source_matchers:
      - alertname = NodeDown
    target_matchers:
      - severity =~ "warning|critical"
    equal: ['node']
```

**How inhibition matching works:**
1. Source alert must be **actively firing** (not pending)
2. Target alert labels listed in `equal` must have identical values in both source and target
3. If both conditions met → target alert is suppressed (no notification sent)

**Multi-level cascade example:**
```
InfraDown (L0)
  └─ inhibits → DatabaseDown (L1)
       └─ inhibits → HighErrorRate (L2)
            └─ inhibits → SLOBurnRateHigh (L3)
```

Each level only inhibits the next. Alertmanager does not chain inhibitions transitively — each rule must be declared explicitly.

**Common mistake:** omitting the `equal` field. Without it, a DatabaseDown in cluster-A would suppress HighErrorRate in cluster-B. Always scope inhibition with `equal`.

## 4. Multi-Receiver Routing

For alerts that need to reach multiple channels simultaneously, use `continue: true`:

```yaml
routes:
  - match:
      severity: critical
    receiver: pagerduty-oncall
    continue: true          # don't stop — keep matching
  - match:
      severity: critical
    receiver: critical-slack  # also post to Slack for visibility
```

Without `continue`, the first matching route terminates evaluation. With `continue`, Alertmanager continues to the next sibling route.

**Fan-out pattern for incident alerts:**
- PagerDuty → pages on-call (primary action channel)
- Slack #incidents → team visibility and async coordination
- Email → audit trail for compliance

## 5. Silence vs Inhibition

| Aspect | Silence | Inhibition |
|--------|---------|------------|
| Trigger | Manual creation via UI/API | Automatic rule evaluation |
| Duration | Fixed time window (start → end) | As long as source alert fires |
| Use case | Planned maintenance, known noisy alert | Root-cause suppression (DB down → suppress downstream) |
| Scope | Exact matcher on labels | Source/target matcher pairs with `equal` |
| Persistence | Expires automatically | Permanent rule in config |
| Risk | Forgetting to remove → missed real alerts | Overly broad `equal` → over-suppression |

**When to use silence:**
- Scheduled maintenance window (e.g., DB migration Saturday 2–4 AM)
- Known flaky alert awaiting fix (set expiry, add comment)
- One-time infrastructure change generating expected alerts

**When to use inhibition:**
- Cascading failure patterns (root cause → N symptoms)
- Infrastructure hierarchy (node down → pod alerts redundant)
- Dependency chains (DB → cache → API error rates)

**Never silence as a substitute for inhibition.** If a pattern recurs, encode it as an inhibition rule rather than repeatedly creating manual silences.