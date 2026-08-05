# Post-mortem Template

## Table of Contents
1. Document Structure
2. Incident Summary Template
3. Timeline Format
4. Root Cause Section
5. Action Items Table
6. Review Process
7. Complete Worked Example (lint-clean)

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

## Mode & Depth
[Draft | Review | Extract | Planning] + [Quick | Standard | Deep] + rationale

## Summary
[One paragraph: what happened, when, impact, current status]

## Timeline (UTC)
[UTC-timestamped entries with sources. Declare UTC in the heading — the linter
flags a timeline that never states its timezone, because bare HH:MM is ambiguous.]

## Root Cause Analysis
[Name the technique (rca-techniques.md §0), reach depth >= 3, state the systemic
root cause — one condition, or the set of jointly-necessary conditions]

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

## Uncovered Risks
[What this post-mortem did NOT analyze. Mandatory — never empty. SKILL.md §9.9]

## Appendix
[Raw data, links to dashboards, log excerpts — redacted per Gate 5]
```

### Distribution header

Every document carries the Gate 5 classification directly under the title:

```markdown
**Distribution**: Internal — Engineering + Management
**Redaction**: customer IDs hashed, IPs removed, no credentials included
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

Use this shape only when §0 of `rca-techniques.md` routes you to 5-Why. For a
fishbone or fault tree, use that section's own layout — the scorecard scores every
technique equally, so do not reshape a branching analysis into five linear steps.

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

---

## 7 Complete Worked Example (lint-clean)

The block below is a full Draft-mode document in this template's own formats. The
regression suite extracts it verbatim and runs `scripts/lint_postmortem.py` over
it, asserting zero findings. If you change any format rule in this template, that
test fails until the example and the linter agree — the template can never again
document a shape its own linter rejects.

<!-- WORKED-EXAMPLE-BEGIN -->
```markdown
# Post-mortem: payment-api elevated error rate (INC-2024-0142)

**Distribution**: Internal — Engineering + Management
**Redaction**: customer IDs hashed, no credentials or IPs included

## Mode & Depth
Draft + Standard. SEV-2 with customer impact, so Standard is forced (SKILL.md §3).

## Summary
On 2024-03-15, payment-api returned elevated 5xx (peak 15.2%) for 47 minutes,
affecting ~12,000 transactions. A config update with an empty Redis connection
string reached production because the deploy pipeline had no schema-validation
gate. Detected by a p99 latency alert, resolved by config rollback. All action
items are filed in JIRA sprint 47.

## Timeline (UTC)
14:18 [TRIGGER]    Config deploy merged and rolled out (GitHub PR #4521)
14:23 [DETECTION]  Error rate crossed 15% (Grafana dashboard: payment-slo)
14:26 [DETECTION]  Alert fired: payment-api p99 > 500ms (PagerDuty #4821)
14:28 [RESPONSE]   On-call acknowledged the page (PagerDuty #4821)
14:35 [RESPONSE]   Scaled to 10 replicas, no improvement (ArgoCD audit log)
14:38 [ESCALATION] Database team paged (PagerDuty #4821)
14:42 [RESPONSE]   Redis connection string found empty (#incident-0142, Slack)
14:45 [MITIGATION] Config rolled back to previous revision (ArgoCD audit log)
14:48 [RECOVERY]   Error rate returned to baseline (Grafana: payment-slo)
15:10 [RECOVERY]   Queued transactions fully drained (Kibana query saved-search)

## Root Cause Analysis
Technique: 5-Why (linear causal chain, single failed control).

1. Why did payment calls fail? The Redis client could not connect.
2. Why could it not connect? The connection string was empty at runtime.
3. Why was it empty? The new config format nested the key one level deeper.
4. Why did the pipeline accept it? There is no config schema validation gate.
5. Why is there no gate? Pipeline capabilities are never re-reviewed as the
   config surface grows.

**Root Cause Statement**: The deploy pipeline has no process for re-reviewing its
validation gates as configuration complexity grows, so an unvalidated format
change reached production.

## Contributing Factors
| Factor | Impact | Evidence |
|--------|--------|----------|
| No automated rollback | Added ~7 min to recovery | ArgoCD has no error-rate trigger |
| Outdated Redis runbook | Added ~4 min to diagnosis | Runbook last updated 2023-09 |
| Silent failure on empty config | Delayed detection | Client logs at debug, not warn |

## Impact Assessment
| Metric | Value |
|--------|-------|
| Duration | 47 minutes (14:23 - 15:10 UTC) |
| Affected users | ~12,000 of ~80,000 active |
| Failed requests | 34,521 (15.2% error rate) |
| Revenue impact | UNKNOWN — no transaction-value tracking |
| SLO budget consumed | 108% of March budget (99.9% target) |
| Regions affected | US-East, EU-West (AP-Southeast unaffected) |

## What Went Well
- Detection: alert fired 3 minutes after the first error, inside the 5-min SLO.
- Escalation: database team engaged 12 minutes after detection.
- Communication: incident channel opened immediately, updates every 15 minutes.

## What Needs Improvement
- Rollback required manual intervention.
- The Redis runbook did not match the current architecture.

## Action Items
| ID | Category | Description | Owner | Deadline | Ticket | Status |
|----|----------|-------------|-------|----------|--------|--------|
| AI-1 | Prevent | Add config JSON-schema validation to the deploy pipeline | @platform | 2024-04-01 | JIRA-4521 | Open |
| AI-2 | Detect | Alert on Redis connection failures at warn level | @sre | 2024-03-22 | JIRA-4522 | Open |
| AI-3 | Mitigate | Auto-rollback when error rate exceeds 5% for 2 min | @platform | 2024-04-15 | JIRA-4523 | Open |
| AI-4 | Prevent | Quarterly review of deploy-pipeline validation gates | @platform | 2024-04-30 | JIRA-4524 | Open |

## Lessons Learned
Validation gates decay relative to the surface they guard. Related: INC-2024-0098
and INC-2024-0112 were both config-shaped failures reaching production through the
same pipeline; this is the third, which makes AI-4 the highest-leverage item.

## Uncovered Risks
- Revenue impact not quantified — no transaction-value tracking exists.
- Downstream cascade into order-service not traced; only payment-api was analyzed.
- Whether other services share the same unvalidated config path is unverified.
```
<!-- WORKED-EXAMPLE-END -->