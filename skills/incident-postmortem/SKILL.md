---
name: incident-postmortem-postmortem
description: >
  Incident post-mortem specialist for writing blameless post-mortems, extracting
  timelines from logs/events, conducting root cause analysis (5-Why, fishbone),
  classifying severity, and generating tracked action items. ALWAYS use when
  writing a post-mortem, reviewing an incident, extracting a timeline, performing
  root cause analysis, or converting incident data into organizational knowledge.
  Complements systematic-debugging (finds the cause) with structured documentation
  that prevents recurrence.
allowed-tools: Read, Write, Grep, Glob, Bash(cat *), Bash(grep *), Bash(jq *), Bash(git log*), Bash(git blame*)
---

## Quick Reference

| When you need...                          | Jump to                                    |
|-------------------------------------------|--------------------------------------------|
| Write a post-mortem from scratch          | §2 Gates -> §5 Checklist -> §9 Output      |
| Extract timeline from logs/events         | §5.1 Timeline Construction                 |
| Perform root cause analysis               | §5.2 Root Cause Analysis                   |
| Classify incident severity                | §6 Severity Classification                 |
| Generate action items                     | §5.4 Action Items                          |
| Review an existing post-mortem            | §2 Gates -> §5 Checklist -> §8 Scorecard   |

---

## 1 Scope

**In scope**: blameless post-mortem writing, timeline extraction from logs/alerts/
chat transcripts/monitoring data, root cause analysis (5-Why, fishbone, fault tree),
severity classification, action item generation with ownership and deadlines,
contributing factor identification, detection/response gap analysis, post-mortem
review and quality scoring.

**Out of scope**: live incident response / on-call procedures (use runbooks),
debugging code to find the root cause (use `systematic-debugging`), monitoring
setup (use `monitoring-alerting`), infrastructure provisioning, customer
communication drafting (PR/comms team scope).

---

## 2 Mandatory Gates

Gates are serial hard blockers. Failure at any gate stops all subsequent work.

### Gate 1: Incident Context Collection

Gather before proceeding. STOP if no incident is identified.

| Item                | Example                                    | Required |
|---------------------|--------------------------------------------|----------|
| Incident identifier | INC-2024-0142, JIRA ticket, PagerDuty ID   | Yes      |
| Impact summary      | "Payment API 503 for 47 minutes"           | Yes      |
| Time window         | 2024-03-15 14:23 - 15:10 UTC               | Yes      |
| Affected services   | payment-api, order-service, Redis cluster   | Yes      |
| Data sources        | Logs, alerts, Slack threads, dashboards     | If any   |

### Gate 2: Blameless Framing

STOP and reframe if any input contains blame language. Post-mortems examine
systems and processes, not individuals.

Reframe rules:
- "John caused the outage" -> "A configuration change triggered the failure"
- "The team should have caught this" -> "The review process did not surface this risk"
- "Operator error" -> "The system permitted an unsafe operation"

### Gate 3: Scope Classification

| Mode         | Trigger                                         | Deliverable                           |
|--------------|-------------------------------------------------|---------------------------------------|
| **Draft**    | "write a post-mortem", raw incident data         | Complete post-mortem document          |
| **Review**   | "review this post-mortem", existing document     | Quality findings + improvement plan   |
| **Extract**  | "extract timeline", logs/events provided         | Structured timeline + gap analysis    |

### Gate 4: Output Completeness

Before delivering, verify all §9 output sections are present. STOP and fill gaps.

---

## 3 Depth Selection

### Quick
Single-section focus. No reference files needed.
- Triggers: "just the timeline", "quick severity assessment", single-concern
- Coverage: one section only (timeline OR root cause OR action items)

### Standard (default)
Full post-mortem document. Load `references/postmortem-template.md`.
- Triggers: "write a post-mortem", "document the incident", post-incident review
- Coverage: complete post-mortem with all §9 sections
- Force Standard if: severity >= SEV-2, customer impact, data loss

### Deep
Comprehensive analysis with systemic pattern review. Load all references.
- Triggers: "deep dive", recurring incident, SEV-1 or higher, regulatory requirement
- Coverage: full post-mortem + systemic patterns + process recommendations
- Force Deep if: SEV-1, repeat incident, multi-team involvement, regulatory

---

## 4 Degradation Modes

When prerequisites are incomplete, produce explicitly-marked partial output.

| Available Data                  | Mode       | Can Deliver                              | Cannot Claim                  |
|---------------------------------|------------|------------------------------------------|-------------------------------|
| Logs + alerts + timeline        | Full       | Complete post-mortem with root cause     | Systemic pattern analysis     |
| Timeline only, no logs          | Partial    | Timeline review + gap analysis           | Root cause depth              |
| Verbal description only         | Sketch     | Draft post-mortem skeleton + questions   | Definitive root cause         |
| Existing post-mortem document   | Review     | Quality score + missing sections         | New root cause analysis       |
| No incident data                | Planning   | Post-mortem template + process guide     | Any incident-specific content |

Mark degraded outputs: `# DEGRADED: [reason] — [what's missing]`

Never fabricate timeline entries. Never invent root causes without evidence.

---

## 5 Post-mortem Checklist

### 5.1 Timeline Construction

1. **Timestamps are UTC and sequential** — mixed timezones cause confusion.
   Convert all sources to UTC. Flag any gaps > 5 minutes during active incident.
2. **Every entry has a source** — "14:23 Alert fired (PagerDuty)" not just "14:23
   something happened". Sources: monitoring, alerts, logs, chat, git commits.
3. **Include detection, response, and recovery phases** — detection: when the
   system first showed symptoms. Response: when humans engaged. Recovery: when
   service was restored. All three matter independently.
4. **Capture what was tried AND what failed** — failed mitigation attempts are
   valuable data. "14:35 Scaled to 10 replicas (no improvement)" prevents
   future responders from repeating the same step.

### 5.2 Root Cause Analysis

5. **Use 5-Why analysis as minimum** — ask "why?" at each level until you reach
   a systemic cause. Stop when you reach a process or design decision, not a
   human action. Shallow analysis stops at "the config was wrong".
6. **Distinguish root cause from contributing factors** — root cause: the single
   change/condition without which the incident would not have occurred.
   Contributing factors: conditions that worsened impact or delayed recovery.
7. **Root cause must be systemic, not individual** — "Engineer deployed bad config"
   is not a root cause. "Deploy pipeline has no config validation gate" is.
8. **Verify root cause explains all symptoms** — if your proposed root cause
   doesn't explain every observed symptom, you haven't found it yet.

### 5.3 Impact Assessment

9. **Quantify impact with metrics** — "47 minutes of degraded service" not "a
   while". Include: duration, affected users/requests, error rate, revenue impact
   if measurable, SLO budget consumed.
10. **Classify customer impact explicitly** — total outage vs degraded vs
    internal-only. Different impact levels drive different response requirements.
11. **Document blast radius** — which services, regions, user segments were affected
    and which were not. Helps assess containment effectiveness.

### 5.4 Action Items

12. **Every action item has an owner and deadline** — "Fix the deploy pipeline"
    is not an action item. "Add config validation to deploy pipeline (owner: @platform,
    deadline: 2024-04-01)" is.
13. **Categorize actions: prevent, detect, mitigate** — prevent: stop it from
    happening again. Detect: catch it faster. Mitigate: reduce impact when it
    happens. All three categories needed.
14. **Action items must be concrete and verifiable** — "Improve monitoring" fails.
    "Add p99 latency alert at 500ms threshold on payment-api (owner: @sre)"
    passes. How do you know it's done?
15. **Include quick wins AND systemic fixes** — not everything is a 3-month
    project. "Add the missing alert" is a 1-hour quick win that prevents the
    next page from being missed.

### 5.5 Organizational Learning

16. **Document what went well** — blameless means celebrating good response too.
    Fast detection, effective communication, correct escalation — call them out.
17. **Identify process gaps, not people gaps** — if the runbook was missing a step,
    the gap is in the runbook process, not in the person who didn't know the step.
18. **Link to previous related incidents** — pattern recognition across incidents
    is where organizational learning happens. "This is the third Redis connection
    pool incident in 6 months — see INC-2024-0098, INC-2024-0112."

---

## 6 Severity Classification

### SEV-1 Critical
- Complete service outage, data loss, or security breach
- Customer-facing impact > 30 minutes with no workaround
- Revenue impact > $10K or regulatory notification required
- Requires: Deep post-mortem, exec review, action items within 48 hours

### SEV-2 Major
- Significant degradation or partial outage
- Customer-facing impact > 15 minutes, workaround available
- SLO budget consumed > 50% of monthly allowance
- Requires: Standard post-mortem, team review, action items within 1 week

### SEV-3 Minor
- Limited impact, quickly resolved
- Internal-only or < 5 minutes customer-facing
- SLO budget consumed < 10%
- Requires: Quick post-mortem, team retrospective

### SEV-4 Informational
- Near-miss or caught before customer impact
- Requires: Brief write-up, no formal post-mortem required

---

## 7 Anti-Examples

### AE-1: Blame-focused post-mortem

```
# WRONG: names individuals as root cause
Root Cause: John deployed a bad configuration file at 14:23 without testing it.
Action Item: Ensure John reviews configs more carefully.
// This is blame, not analysis. It stops at the human and misses the system.

# RIGHT: systemic root cause
Root Cause: The deployment pipeline accepted an invalid configuration because
config validation was not enforced at the CI/CD gate. The config schema
allows empty connection strings, which cause silent failures at runtime.
Action Item: Add JSON schema validation to the deploy pipeline (owner: @platform).
```

### AE-2: Timeline without sources

```
# WRONG: no evidence chain
14:23 Something went wrong
14:30 Someone noticed
14:45 Fixed

# RIGHT: every entry sourced
14:23 payment-api error rate spiked to 15% (Grafana dashboard: payment-slo)
14:26 PagerDuty alert fired: "payment-api p99 > 500ms" (PD incident #4821)
14:28 On-call @alice acknowledged (PagerDuty)
14:31 @alice in #incident-2024-0142: "Checking payment-api logs" (Slack)
```

### AE-3: "Improve monitoring" as an action item

```
# WRONG: vague, unverifiable, no owner
Action Items:
- Improve monitoring
- Be more careful with deploys
- Add more tests

# RIGHT: specific, owned, deadlined
Action Items:
- [Detect] Add p99 latency alert at 500ms for payment-api (owner: @sre, deadline: Mar 22)
- [Prevent] Add config schema validation to CI pipeline (owner: @platform, deadline: Apr 1)
- [Mitigate] Add circuit breaker between order-svc and payment-api (owner: @backend, deadline: Apr 15)
```

### AE-4: Shallow 5-Why analysis (stops at human)

```
# WRONG: stops at human action (depth 2)
Why did payment fail? -> Bad config was deployed
Why was bad config deployed? -> Engineer didn't test it
// Stops here. Blames individual. Misses systemic cause.

# RIGHT: reaches systemic cause (depth 5)
Why did payment fail? -> Connection string was empty in config
Why was connection string empty? -> Config file had wrong format
Why was wrong format accepted? -> No schema validation in deploy pipeline
Why is there no schema validation? -> Pipeline was built before config complexity grew
Why wasn't validation added when config grew? -> No process to review pipeline gates
// Root cause: missing process for pipeline capability reviews as services evolve
```

### AE-5: Missing "what went well"

```
# WRONG: all negative, no learning from successes
Summary: Everything went wrong. Detection was slow. Response was slow.
// Demoralizing and incomplete. Misses positive patterns to reinforce.

# RIGHT: balanced assessment
What Went Well:
- Detection: Alert fired within 3 minutes of first error (SLO: < 5 min)
- Communication: Incident channel created immediately, stakeholders updated every 15 min
- Escalation: Correctly escalated to database team within 10 minutes
What Needs Improvement:
- Runbook for Redis failover was outdated (last updated 8 months ago)
- No automated rollback — manual intervention required
```

### AE-6: No follow-up tracking

```
# WRONG: action items with no tracking
Action Items: [listed in the document, never tracked]
// Six months later: same incident occurs. Action items were forgotten.

# RIGHT: action items linked to tracking system
Action Items:
- [Prevent] JIRA-4521: Add config validation (owner: @platform, deadline: Apr 1)
- [Detect] JIRA-4522: Add missing alert (owner: @sre, deadline: Mar 22)
Status: Reviewed in weekly incident review meeting. Next check: Apr 5.
```

---

## 8 Post-mortem Scorecard

Three-tier scoring applied after every post-mortem.

### Critical (must all pass — any failure = post-mortem incomplete)

1. **Timeline present with UTC timestamps** — sequential, sourced entries
2. **Root cause identified (systemic, not individual)** — blameless, depth >= 3
3. **Action items have owners and deadlines** — every item concrete and tracked

### Standard (>= 4 of 5 must pass)

4. **Impact quantified with metrics** — duration, users affected, error rates
5. **5-Why analysis depth >= 3** — not stopping at superficial cause
6. **Contributing factors distinguished from root cause** — separate sections
7. **Detection/response/recovery phases in timeline** — all three documented
8. **Blameless language throughout** — no individual blame, systems focus

### Hygiene (>= 3 of 4 must pass)

9. **"What went well" section present** — positive patterns documented
10. **Action items categorized (prevent/detect/mitigate)** — all three categories
11. **Related incidents linked** — cross-reference to past similar incidents
12. **Follow-up tracking mechanism defined** — JIRA/Linear tickets, review date

**Verdict**: Critical 3/3 AND Standard >= 4/5 AND Hygiene >= 3/4 = **PASS**

---

## 9 Output Contract

Every response MUST include these sections. Volume rules: SEV-1/2 fully detailed;
SEV-3 condensed; SEV-4 summary only.

### 9.1 Incident Summary
One paragraph: what happened, when, impact, current status. Table format for metadata.

### 9.2 Mode & Depth
`Draft | Review | Extract` + `Quick | Standard | Deep` with rationale.

### 9.3 Timeline
UTC-timestamped entries with sources. Phases marked: DETECTION, RESPONSE, RECOVERY.

### 9.4 Root Cause Analysis
5-Why analysis (minimum). Root cause statement. Contributing factors list.

### 9.5 Impact Assessment
Duration, affected users/services, error rates, SLO budget consumed, revenue impact.

### 9.6 What Went Well
Positive aspects of detection, response, communication, escalation.

### 9.7 Action Items
Table: ID, Category (prevent/detect/mitigate), Description, Owner, Deadline, Ticket.

### 9.8 Lessons Learned
Key takeaways. Link to related incidents. Systemic recommendations.

### 9.9 Uncovered Risks
What this post-mortem did NOT analyze. Mandatory — never empty. Examples: "customer
impact not fully quantified — no revenue data available", "only primary service
analyzed — downstream cascade effects not traced".

**Scorecard appended**: `X/12 — Critical Y/3, Standard Z/5, Hygiene W/4 — PASS/FAIL`

---

## 10 Reference Loading Guide

| Condition                                    | Load                                    |
|----------------------------------------------|-----------------------------------------|
| Writing any post-mortem (Standard+)          | `references/postmortem-template.md`     |
| Root cause analysis (Standard+)              | `references/rca-techniques.md`          |
| Severity classification, impact assessment   | `references/severity-framework.md`      |
| Deep analysis, systemic patterns             | All three references                    |

Each reference has a table of contents. Load relevant sections, not the
entire file, when only a specific pattern is needed.