# Severity Framework

## Table of Contents
1. Severity Levels
2. Impact Quantification
3. SLO Budget Mapping
4. Escalation Matrix
5. Post-mortem Requirements by Severity

---

## 1 Severity Levels

### Decision Tree

```
Is there data loss or security breach?
├─ YES → SEV-1
└─ NO
   Is there complete customer-facing outage?
   ├─ YES, > 30 min → SEV-1
   ├─ YES, < 30 min → SEV-2
   └─ NO (degraded, not down)
      Is customer impact significant?
      ├─ YES, > 15 min → SEV-2
      ├─ YES, < 15 min → SEV-3
      └─ NO (internal only)
         Was there actual impact?
         ├─ YES → SEV-3
         └─ NO (near-miss) → SEV-4
```

### Severity Definitions

| Level | Name | Customer Impact | Duration | SLO Budget | Examples |
|-------|------|-----------------|----------|------------|---------|
| SEV-1 | Critical | Total outage or data loss | > 30 min | > monthly budget | Payment API down, data breach, DB corruption |
| SEV-2 | Major | Significant degradation | > 15 min | > 50% monthly | Elevated errors, partial outage, feature broken |
| SEV-3 | Minor | Limited impact | < 15 min | < 10% monthly | Brief spike, single endpoint, quick self-heal |
| SEV-4 | Info | None (near-miss) | N/A | None | Caught by monitoring, prevented by automation |

---

## 2 Impact Quantification

### Metrics to Capture

| Metric | How to Measure | Example |
|--------|---------------|---------|
| Duration | TRIGGER to RECOVERY timestamps | 47 minutes |
| Affected users | Unique user IDs in error logs | ~12,000 users |
| Failed requests | 5xx count during incident window | 34,521 requests |
| Error rate | Failed / total during window | 15.2% |
| Revenue impact | Failed transactions × avg value | ~$48,000 |
| SLO budget consumed | Error minutes / monthly budget | 62% of monthly |

### Impact Statement Template

```markdown
## Impact Assessment

| Metric | Value |
|--------|-------|
| Duration | 47 minutes (14:23 - 15:10 UTC) |
| Affected users | ~12,000 (out of ~80,000 active) |
| Failed requests | 34,521 (15.2% error rate) |
| Revenue impact | ~$48,000 estimated |
| SLO budget consumed | 62% of March budget |
| Data loss | None confirmed |
| Regions affected | US-East, EU-West |
| Regions unaffected | AP-Southeast |
```

### When Data Is Unavailable

Mark gaps explicitly:
```
| Revenue impact | UNKNOWN — no transaction value tracking |
| Affected users | ESTIMATED ~12,000 — based on error log sampling |
```

Never fabricate impact numbers. "Unknown" is better than a guess.

---

## 3 SLO Budget Mapping

### Monthly Error Budget Calculation

```
Monthly minutes = 30 days × 24 hours × 60 min = 43,200 minutes

SLO 99.9%  → Error budget: 43.2 min/month
SLO 99.95% → Error budget: 21.6 min/month
SLO 99.99% → Error budget: 4.3 min/month
```

### Budget Impact Table

| SLO Target | Monthly Budget | 47-min Incident Consumes |
|------------|---------------|--------------------------|
| 99.9% | 43.2 min | 108% (budget exceeded) |
| 99.95% | 21.6 min | 217% (budget blown) |
| 99.99% | 4.3 min | 1093% (catastrophic) |

### Severity Escalation by Budget

- Budget consumed < 10% → SEV-3
- Budget consumed 10-50% → SEV-2
- Budget consumed > 50% → SEV-2 minimum, consider SEV-1
- Budget exceeded (> 100%) → SEV-1

---

## 4 Escalation Matrix

### Who Needs to Know

| Severity | Engineering | Management | Executive | Customer | Legal |
|----------|------------|------------|-----------|----------|-------|
| SEV-1 | Immediate | Immediate | Within 1h | Within 2h | If data | 
| SEV-2 | Immediate | Within 1h | Daily | If asked | No |
| SEV-3 | Within 1h | Weekly | No | No | No |
| SEV-4 | Async | No | No | No | No |

### Communication Cadence During Incident

| Severity | Internal Updates | Customer Updates |
|----------|-----------------|-----------------|
| SEV-1 | Every 15 min | Every 30 min on status page |
| SEV-2 | Every 30 min | Hourly if customer-facing |
| SEV-3 | At resolution | Not required |

---

## 5 Post-mortem Requirements by Severity

### SEV-1 Requirements

| Requirement | Deadline | Mandatory |
|-------------|----------|-----------|
| Incident channel created | During incident | Yes |
| Initial post-mortem draft | Within 24 hours | Yes |
| Full post-mortem with RCA | Within 72 hours | Yes |
| Action items filed in tracker | Within 48 hours | Yes |
| Review meeting held | Within 1 week | Yes |
| Executive summary distributed | Within 48 hours | Yes |
| Action items completed | Track weekly | Yes |
| Post-mortem depth | Deep | Yes |

### SEV-2 Requirements

| Requirement | Deadline | Mandatory |
|-------------|----------|-----------|
| Post-mortem draft | Within 48 hours | Yes |
| Full post-mortem with RCA | Within 1 week | Yes |
| Action items filed | Within 1 week | Yes |
| Review meeting | Within 2 weeks | Yes |
| Post-mortem depth | Standard | Yes |

### SEV-3 Requirements

| Requirement | Deadline | Mandatory |
|-------------|----------|-----------|
| Brief post-mortem | Within 1 week | Yes |
| Action items filed | Within 1 week | Recommended |
| Team retrospective | Next sprint | Recommended |
| Post-mortem depth | Quick | Minimum |

### SEV-4 Requirements

| Requirement | Deadline | Mandatory |
|-------------|----------|-----------|
| Brief write-up | Within 1 week | Recommended |
| No formal post-mortem | N/A | N/A |