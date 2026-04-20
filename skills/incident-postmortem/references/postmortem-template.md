# Post-mortem Template

## Table of Contents
1. Document Structure
2. Incident Summary Template
3. Timeline Format
4. Root Cause Section
5. Action Items Table
6. Review Process

---

## 1 Document Structure

### Required Sections (in order)

```markdown
# Post-mortem: [Incident Title]

## Metadata
| Field          | Value                          |
|----------------|--------------------------------|
| Incident ID    | INC-YYYY-NNNN                  |
| Date           | YYYY-MM-DD                     |
| Severity       | SEV-1 / SEV-2 / SEV-3 / SEV-4 |
| Duration       | HH:MM (start to resolution)    |
| Author         | @author                        |
| Reviewers      | @reviewer1, @reviewer2         |
| Status         | Draft / In Review / Final      |

## Summary
[One paragraph: what happened, when, impact, current status]

## Timeline
[UTC-timestamped entries with sources]

## Root Cause Analysis
[5-Why minimum, systemic root cause statement]

## Contributing Factors
[Conditions that worsened impact or delayed recovery]

## Impact Assessment
[Quantified: duration, users, requests, revenue, SLO budget]

## What Went Well
[Positive aspects of detection, response, communication]

## What Needs Improvement
[Process/system gaps identified]

## Action Items
[Table: ID, Category, Description, Owner, Deadline, Ticket]

## Lessons Learned
[Key takeaways, related incidents, systemic recommendations]

## Appendix
[Raw data, links to dashboards, log excerpts]
```

---

## 2 Incident Summary Template

### Formula

> On [DATE], [SERVICE] experienced [IMPACT] for [DURATION] affecting
> [SCOPE]. The root cause was [ROOT CAUSE]. The incident was detected
> by [DETECTION METHOD] and resolved by [RESOLUTION]. [CURRENT STATUS].

### Good Examples

> On 2024-03-15, the payment-api experienced elevated error rates (15% 5xx)
> for 47 minutes, affecting approximately 12,000 transactions. The root cause
> was an empty Redis connection string deployed via a config update that
> bypassed schema validation. The incident was detected by a p99 latency
> alert and resolved by rolling back the configuration. All action items
> have been filed and are tracked in JIRA sprint 47.

### Bad Example (too vague)

> The payment system had issues on Friday afternoon. We fixed it.

---

## 3 Timeline Format

### Entry Format

```
HH:MM [PHASE] Event description (source)
```

### Phase Labels

| Phase       | Meaning                                     | Color Code |
|-------------|---------------------------------------------|------------|
| TRIGGER     | The change/event that caused the incident   | Red        |
| DETECTION   | System or human first noticed the problem   | Orange     |
| RESPONSE    | Humans began investigating/mitigating       | Yellow     |
| ESCALATION  | Additional teams/experts brought in          | Blue       |
| MITIGATION  | Temporary fixes applied                      | Green      |
| RECOVERY    | Service fully restored                       | Green      |
| FOLLOW-UP   | Post-incident activities                     | Gray       |

### Example Timeline

```
14:18 [TRIGGER]    Config deploy merged via CI (GitHub PR #4521)
14:23 [DETECTION]  payment-api error rate spike to 15% (Grafana: payment-slo)
14:26 [DETECTION]  PagerDuty alert: "payment-api p99 > 500ms" (PD #4821)
14:28 [RESPONSE]   On-call @alice acknowledged alert (PagerDuty)
14:31 [RESPONSE]   @alice: "Checking payment-api logs" (#incident-0142, Slack)
14:35 [RESPONSE]   @alice: "Redis connection errors in logs" (Slack)
14:38 [ESCALATION] @alice paged @bob (database team) (PagerDuty)
14:42 [RESPONSE]   @bob: "Redis config shows empty connection string" (Slack)
14:45 [MITIGATION] Rolled back config to previous version (ArgoCD)
14:48 [RECOVERY]   Error rate returned to baseline (Grafana)
15:10 [RECOVERY]   Confirmed all queued transactions processed (Kibana)
15:15 [FOLLOW-UP]  Incident channel archived, post-mortem started (Slack)
```

### Gap Analysis

After constructing timeline, check for:
- **Detection gap**: Time between TRIGGER and DETECTION (target: < 5 min)
- **Response gap**: Time between DETECTION and RESPONSE (target: < 5 min)
- **Escalation delay**: Was the right team engaged early enough?
- **Unexplained gaps**: Periods > 5 minutes with no entries during active incident

---

## 4 Root Cause Section

### 5-Why Template

```markdown
### 5-Why Analysis

1. **Why did [symptom]?**
   Because [immediate cause].

2. **Why did [immediate cause]?**
   Because [intermediate cause].

3. **Why did [intermediate cause]?**
   Because [deeper cause].

4. **Why did [deeper cause]?**
   Because [process/design gap].

5. **Why does [process/design gap] exist?**
   Because [systemic root cause].

**Root Cause Statement**: [One sentence systemic root cause]
```

### Quality Checks for Root Cause

- Does it explain ALL observed symptoms?
- Is it systemic (process/design) not individual (person)?
- Could reasonable people have made the same mistake given the same system?
- Does fixing it prevent recurrence (not just this specific incident)?
- Is it verifiable with evidence from the timeline?

### Contributing Factors Template

```markdown
### Contributing Factors

| Factor | Impact | Evidence |
|--------|--------|----------|
| Outdated runbook | Delayed recovery by ~10 min | Runbook last updated 2023-09 |
| No automated rollback | Required manual intervention | Deploy pipeline has no rollback trigger |
| Alert fatigue | On-call delayed response by 3 min | 47 alerts in past 24h, 42 false positives |
```

---

## 5 Action Items Table

### Standard Format

```markdown
### Action Items

| ID | Category | Description | Owner | Deadline | Ticket | Status |
|----|----------|-------------|-------|----------|--------|--------|
| AI-1 | Prevent | Add config schema validation to CI | @platform | Apr 1 | JIRA-4521 | Open |
| AI-2 | Detect | Add Redis connection health check | @sre | Mar 22 | JIRA-4522 | Open |
| AI-3 | Mitigate | Add auto-rollback on error rate spike | @platform | Apr 15 | JIRA-4523 | Open |
| AI-4 | Detect | Reduce alert noise (consolidate) | @sre | Mar 29 | JIRA-4524 | Open |
```

### Category Definitions

| Category   | Purpose                              | Example                                |
|------------|--------------------------------------|----------------------------------------|
| **Prevent** | Stop the root cause from recurring  | Add validation gate, fix the bug       |
| **Detect**  | Catch it faster next time            | Add alert, improve monitoring          |
| **Mitigate**| Reduce impact when it happens        | Add circuit breaker, auto-rollback     |

### Action Item Quality Checklist

- [ ] Has a single owner (person or team, not "engineering")
- [ ] Has a deadline (date, not "soon" or "next quarter")
- [ ] Has a tracking ticket (JIRA, Linear, GitHub issue)
- [ ] Is verifiable (how do you know it's done?)
- [ ] Addresses root cause or contributing factor (not unrelated)

---

## 6 Review Process

### Review Checklist

Before marking a post-mortem as "Final":

1. **Timeline reviewed by at least 2 participants** — people who were in the incident
2. **Root cause agreed upon by responding team** — not just the author's opinion
3. **Action items reviewed by owners** — each owner confirmed commitment
4. **Blameless language verified** — no individual blame in the document
5. **Scorecard passes** — Critical 3/3, Standard >= 4/5, Hygiene >= 3/4

### Review Meeting Agenda (30 min)

1. [5 min] Author presents summary and timeline
2. [5 min] Team validates timeline accuracy
3. [10 min] Discuss root cause and contributing factors
4. [5 min] Review action items, confirm owners and deadlines
5. [5 min] Identify any additional lessons or related incidents