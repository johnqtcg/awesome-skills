# Root Cause Analysis Techniques

## Table of Contents
1. 5-Why Analysis
2. Fishbone (Ishikawa) Diagram
3. Fault Tree Analysis
4. Contributing Factor Mapping
5. Common Root Cause Patterns
6. Anti-Patterns in RCA

---

## 1 5-Why Analysis

### When to Use
- Default technique for all post-mortems
- Best for incidents with a clear causal chain
- Quick to execute, easy to understand

### Process

1. Start with the observable symptom
2. Ask "Why did this happen?"
3. Repeat for each answer until you reach a systemic cause
4. Typically 3-7 levels deep (not always exactly 5)
5. Stop when you reach a process, design, or organizational decision

### Depth Guidelines

| Depth | Type of Cause | Example | Sufficient? |
|-------|--------------|---------|-------------|
| 1 | Symptom | "Payment API returned 503" | Never |
| 2 | Immediate cause | "Redis connection failed" | Never |
| 3 | Proximate cause | "Config had empty connection string" | Rarely |
| 4 | Process gap | "No config validation in pipeline" | Often |
| 5 | Systemic cause | "No process for pipeline gate reviews" | Yes |

### Branching 5-Why

When one "why" has multiple answers, branch:

```
Why did the outage last 47 minutes?
├─ Why was detection slow (23 min)?
│  └─ Why was the alert missing?
│     └─ Why wasn't it added during the last deploy?
│        └─ No checklist for alert coverage on new endpoints
└─ Why was recovery slow (24 min)?
   └─ Why was manual rollback needed?
      └─ No automated rollback on error rate spike
         └─ Rollback automation was descoped from Q3 roadmap
```

---

## 2 Fishbone (Ishikawa) Diagram

### When to Use
- Complex incidents with multiple contributing factors
- When 5-Why produces too many branches
- SEV-1 incidents requiring comprehensive analysis

### Standard Categories for Software Systems

| Category | Examples |
|----------|---------|
| **Process** | Missing review step, no runbook, unclear escalation |
| **Technology** | Software bug, infrastructure failure, dependency issue |
| **People** | Training gap, staffing, on-call fatigue |
| **Environment** | Load spike, third-party outage, network partition |
| **Monitoring** | Missing alert, alert fatigue, dashboard gap |
| **Communication** | Delayed notification, unclear status page, siloed information |

### Text Representation

```
                    ┌─ Process: No config validation gate
                    ├─ Process: Outdated runbook
INCIDENT ──────────├─ Technology: No automated rollback
(Payment 503)      ├─ Technology: Silent failure on empty config
                    ├─ Monitoring: Missing Redis connection alert
                    ├─ Environment: Peak traffic amplified impact
                    └─ Communication: Alert went to wrong channel
```

---

## 3 Fault Tree Analysis

### When to Use
- Safety-critical systems
- When you need to understand AND/OR relationships between causes
- Regulatory or compliance-driven post-mortems

### Notation

```
        [Outage]          (Top event — what happened)
           |
         [AND]            (All children must occur)
        /     \
  [Bad Config] [No Validation]
       |              |
     [OR]          [AND]
    /    \        /      \
[Typo] [Empty] [No CI] [No Review]
```

- **AND gate**: All sub-causes must be present for parent to occur
- **OR gate**: Any sub-cause is sufficient for parent to occur

### Key Insight

AND gates reveal **defense layers**: if any one defense had worked, the incident
would not have occurred. Each missing defense is a contributing factor.

---

## 4 Contributing Factor Mapping

### Root Cause vs Contributing Factors

| Aspect | Root Cause | Contributing Factor |
|--------|-----------|-------------------|
| Definition | The change/condition without which the incident would not have occurred | Conditions that worsened impact or delayed recovery |
| Count | Usually 1 (rarely 2) | Often 3-8 |
| Fix priority | Highest — prevents recurrence | High — reduces blast radius |
| Example | Empty config deployed | No automated rollback, outdated runbook |

### Contributing Factor Categories

**Detection factors** (why it wasn't caught earlier):
- Missing monitoring or alerts
- Alert fatigue (too many false positives)
- Dashboard not showing the right metrics

**Response factors** (why response was slow):
- Unclear escalation path
- Outdated or missing runbook
- Key responders unavailable

**Amplification factors** (why impact was larger than necessary):
- No circuit breaker or bulkhead
- Retry storms from upstream services
- No feature flag to disable affected functionality

**Recovery factors** (why recovery was slow):
- No automated rollback
- Complex manual recovery procedure
- Lack of tested recovery playbook

---

## 5 Common Root Cause Patterns

### Pattern 1: Missing Validation Gate
A change passed through the pipeline without the necessary safety check.
- **Symptom**: Bad config/code deployed to production
- **Root cause**: Pipeline lacks validation for the specific failure mode
- **Fix**: Add the validation gate + test it works

### Pattern 2: Silent Failure
A component failed without alerting or logging the failure.
- **Symptom**: Degradation detected late, often by customers
- **Root cause**: Error handling swallows failures without surfacing them
- **Fix**: Health checks, structured error logging, synthetic monitoring

### Pattern 3: Capacity Surprise
System exceeded a limit that wasn't monitored or load-tested.
- **Symptom**: Sudden degradation under traffic spike
- **Root cause**: No load testing, no capacity alerts, no auto-scaling
- **Fix**: Load testing + capacity alerts + scaling playbook

### Pattern 4: Dependency Cascade
One service's failure propagated to dependent services.
- **Symptom**: Multiple services failing in sequence
- **Root cause**: Missing circuit breakers, no bulkhead isolation
- **Fix**: Circuit breakers + retry budgets + graceful degradation

### Pattern 5: Runbook Drift
Runbook doesn't match current system architecture.
- **Symptom**: Responders following outdated steps, wasting time
- **Root cause**: No process to keep runbooks current with system changes
- **Fix**: Runbook review as part of deploy checklist + periodic audits

### Pattern 6: Alert Fatigue
Too many alerts dilute attention, causing real alerts to be ignored.
- **Symptom**: Critical alert acknowledged late or missed entirely
- **Root cause**: Low signal-to-noise ratio in alerting
- **Fix**: Alert consolidation + noise reduction + escalation policy

---

## 6 Anti-Patterns in RCA

### Stopping at the Human

```
# BAD: "John didn't test the config"
# GOOD: "The system allowed untested config to reach production"
```

### Single Cause Fallacy

Complex incidents rarely have a single cause. If your RCA identifies one cause
and stops, you're probably missing contributing factors.

### Hindsight Bias

"They should have known" is hindsight bias. Ask instead: "What information
was available at the time, and what would a reasonable person have concluded?"

### Solution-Driven RCA

Starting with a desired solution and working backward to justify it:
```
# BAD: "We need to rewrite the service" -> [RCA crafted to support rewrite]
# GOOD: [RCA identifies root cause] -> [Solution addresses root cause]
```

### Ignoring Near-Misses

A near-miss (caught before customer impact) has the same root cause as an
actual incident. Treat near-misses as learning opportunities, not non-events.