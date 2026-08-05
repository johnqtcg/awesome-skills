---
name: incident-postmortem
description: >
  Incident post-mortem specialist for writing blameless post-mortems, extracting
  timelines from logs/events, conducting root cause analysis (5-Why, fishbone),
  classifying severity, and generating tracked action items. ALWAYS use when
  writing a post-mortem, reviewing an incident, extracting a timeline, performing
  root cause analysis, or converting incident data into organizational knowledge.
  Complements systematic-debugging (finds the cause) with structured documentation
  that prevents recurrence.
allowed-tools: Read, Write, Grep, Glob, Bash(cat *), Bash(grep *), Bash(jq *), Bash(git log*), Bash(git blame*), Bash(*lint_postmortem.py*)
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
| Know which sections your output needs     | §9.0 Required Sections by Mode             |
| Redact before sharing / set distribution  | §2 Gate 5 Sensitive Data & Distribution    |
| Choose an RCA technique other than 5-Why  | §5.2 item 5 -> `rca-techniques.md` §0      |

---

## 1 Scope

**In scope**: blameless post-mortem writing, timeline extraction from logs/alerts/chat/
monitoring, root cause analysis (5-Why, fishbone, fault tree), severity classification,
action items with ownership and deadlines, contributing-factor identification,
detection/response gap analysis, post-mortem review and quality scoring.

**Out of scope**: live incident response / on-call procedures (use runbooks), debugging
code to find the root cause (use `systematic-debugging`), monitoring setup (use
`monitoring-alerting`), infrastructure provisioning, customer communication drafting
(PR/comms team scope).

**Language**: write the post-mortem in the language the user is using. The linter's
section, source, owner/deadline, category and N/A patterns are bilingual (English and
Chinese, including full-width `（）` and `：`), so a Chinese post-mortem passes the same
gates. Other languages are not yet aliased — a German or Japanese document will be
mis-reported as missing sections; lint it in English or add the aliases first.

---

## 2 Mandatory Gates

Gates are serial hard blockers. Failure at any gate stops all subsequent work.

### Gate 1: Incident Context Collection

Gather before proceeding. STOP if no incident is identified — the only permitted
continuation is **Planning** mode (§4), which delivers process guidance and a blank
template. Never synthesize a Draft from an unidentified incident.

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
| **Planning** | no incident identified, "how do we run these"    | Template + process guide only         |

The mode fixes which output sections are required (§9.0). It is not a depth setting —
depth (§3) is chosen independently.

### Gate 4: Output Completeness

Before delivering, verify every section **your mode** requires per §9.0 is present.
STOP and fill gaps. Sections outside your mode's contract are not gaps.

### Gate 5: Sensitive Data & Distribution

Incident evidence carries customer and credential data. Before delivering, scrub and
classify — a post-mortem is circulated far more widely than the logs it came from.

| Category                                   | Action                                        |
|--------------------------------------------|-----------------------------------------------|
| Credentials, tokens, keys, connection URIs | Remove. Never `***`-mask in place — rotate    |
| Customer identifiers, emails, IPs, payment data | Hash, aggregate, or drop                 |
| Employee names in causal position          | Replace with role ("the on-call engineer")     |
| Unpatched vulnerability detail             | Summarize; keep exploit specifics in the ticket |
| Log/dashboard links                        | Confirm the audience can access them           |

State the outcome in the document header: `**Distribution**: <audience>` and
`**Redaction**: <what was removed>`. Security-incident post-mortems follow the
organization's disclosure process before any distribution — that gate is not yours
to waive. STOP if a credential appears in the draft.

---

## 3 Depth Selection

### Quick
Single-section focus. No reference files needed.
- Triggers: "just the timeline", "quick severity assessment", single-concern
- Coverage: the one requested section, plus the §9.0 spine (9.2 + 9.9)
- Lint with `--depth quick`; sections you did not claim are not gaps

### Standard (default)
Full post-mortem document. Load `references/postmortem-template.md`.
- Triggers: "write a post-mortem", "document the incident", post-incident review
- Coverage: every section your mode requires per §9.0
- Force Standard if: severity >= SEV-2, customer impact, data loss

### Deep
Comprehensive analysis with systemic pattern review. Load all references.
- Triggers: "deep dive", recurring incident, SEV-1 or higher, regulatory requirement
- Coverage: §9.0 contract + systemic patterns + process recommendations
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

5. **Select the technique by causal shape, then reach depth >= 3** — 5-Why is the
   default for a linear chain; fishbone when factors are parallel rather than
   sequential; fault tree when several defenses had to fail together. Whichever you
   pick, name it, and keep asking "why?" until you reach a process or design
   decision, not a human action. Shallow analysis stops at "the config was wrong".
6. **Distinguish root cause from contributing factors** — root cause: the condition
   (or the smallest set of jointly-necessary conditions) without which the incident
   would not have occurred. Contributing factors: conditions that worsened impact or
   delayed recovery. Do not force a multi-cause incident into a single sentence — an
   AND-gated failure has one root cause per failed defense (`rca-techniques.md` §3).
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
    happens. Assess all three; when one genuinely does not apply, write
    `Mitigate: N/A — <reason>` rather than inventing a low-value item to fill the
    slot. An empty category is a finding; a justified N/A is an answer.
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

**The organization's own incident policy wins.** If the user's org defines severity
levels, SLO budgets, notification deadlines, or review requirements, use those and
say which policy you applied. The thresholds below are defaults for when no local
standard exists — the dollar figures and minute counts are calibrated to a
mid-size SaaS and are wrong for a hospital, a bank, or a two-person startup. Ask
for the local policy whenever severity drives a deadline or an escalation.

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
5. **RCA depth >= 3, technique named** — any technique from `rca-techniques.md` §0
   scores equally; a fault tree naming three failed defenses is a pass, not a miss
6. **Contributing factors distinguished from root cause** — separate sections
7. **Detection/response/recovery phases in timeline** — all three documented
8. **Blameless language throughout** — no individual blame, systems focus

### Hygiene (>= 3 of 4 must pass)

9. **"What went well" section present** — positive patterns documented
10. **Action items categorized (prevent/detect/mitigate)** — each category present
    or explicitly `N/A — <reason>`; Review mode is exempt (its items fix the
    document, not the system)
11. **Related incidents linked** — cross-reference to past similar incidents
12. **Follow-up tracking mechanism defined** — JIRA/Linear tickets, review date

**Verdict**: Critical 3/3 AND Standard >= 4/5 AND Hygiene >= 3/4 = **PASS**

**Mechanical layer** — before scoring by judgment, run the bundled linter on the produced document, passing the Gate 3 mode so only that mode's contract is enforced:

```bash
python3 scripts/lint_postmortem.py postmortem.md --mode draft --depth standard
```

Pass the Gate 3 mode and the §3 depth. `--depth quick` stops requiring sections a Quick
output never claimed, but **still lints everything present** and still requires §9.9.

It checks the regex-decidable subset in every entry format this skill's template emits — bare `14:23 [PHASE] … (source)` lines, `- 14:23 …` list items, and `| 14:23 | … |` table rows: valid clock times, a source on every entry, chronological order, an explicit UTC declaration, owner + concrete date on every action item (in list *and* table form, empty and `TBD` cells included), prevent/detect/mitigate coverage, a non-empty "Uncovered Risks" section, a blame-phrase scan, and a Gate 5 credential/PII scan. Critical lint findings block delivery, same as scorecard Critical items. The judgment items (root-cause depth, systemic framing) remain yours.

---

## 9 Output Contract

### 9.0 Required Sections by Mode

The mode (Gate 3) selects the contract. A section marked — is out of contract for
that mode: omitting it is correct, and padding it with speculation is a defect.

| Section              | Draft | Review | Extract | Planning |
|----------------------|:-----:|:------:|:-------:|:--------:|
| 9.1 Incident Summary | Yes   | Yes    | Yes     | —        |
| 9.2 Mode & Depth     | Yes   | Yes    | Yes     | Yes      |
| 9.3 Timeline         | Yes   | —      | Yes     | —        |
| 9.4 Root Cause       | Yes   | —      | —       | —        |
| 9.5 Impact           | Yes   | —      | —       | —        |
| 9.6 What Went Well   | Yes   | —      | —       | —        |
| 9.7 Action Items     | Yes   | Yes    | —       | —        |
| 9.8 Lessons Learned  | Yes   | Yes    | —       | —        |
| 9.9 Uncovered Risks  | Yes   | Yes    | Yes     | Yes      |

- **Review** adds a findings list + §8 scorecard + improvement plan in place of 9.3–9.6;
  its Action Items are fixes to the post-mortem, not to the system.
- **Extract** adds detection/response gap analysis, and states confidence per entry.
- **Planning** delivers `references/postmortem-template.md` + the process guide only;
  its 9.9 is what the process guide does not cover.
- **Review** items are commitments to fix the document, so they still need an owner and
  a deadline — only the prevent/detect/mitigate categories do not apply.
- The mandatory spine is 9.2 + 9.9, in every mode and at every depth (§3 Quick included).

**An explicit user format instruction outranks this contract.** If the user pins the
output shape — "output only the RCA section", "fill in our template", "no headings" —
deliver exactly that. Where the spine goes depends on what room the user left:

| The user's instruction leaves…            | Put 9.2 / 9.9…                          |
|-------------------------------------------|-----------------------------------------|
| room inside the document                  | inline: 9.2 one line, 9.9 a short list  |
| a separate file, chat message unrestricted | in the message, not in the file          |
| **no room at all** ("only X, no other text") | **nowhere — omit them**              |

The third row is not a loophole, it is obedience. When the reply *is* the artifact and
the user forbade anything else, padding it with a Mode line or a risks list disobeys a
direct instruction. Do not do it, and do not ask permission to. Say nothing extra.

Never drop 9.9 *silently* when you had somewhere to put it — rows 1 and 2 are the norm;
row 3 applies only to an explicit prohibition.

Lint with `--user-pinned-format` when the shape is pinned; it waives the §9.9 check
inside the file, and you remain accountable for stating it wherever room exists.

Volume rules: SEV-1/2 fully detailed; SEV-3 condensed; SEV-4 summary only.

### Section Definitions

- **9.1 Incident Summary** — one paragraph: what happened, when, impact, current
  status; metadata as a table.
- **9.2 Mode & Depth** — `Draft | Review | Extract | Planning` + `Quick | Standard |
  Deep`, with the rationale for each.
- **9.3 Timeline** — UTC-timestamped, sourced entries, chronologically ordered.
  Phases marked: DETECTION, RESPONSE, RECOVERY.
- **9.4 Root Cause Analysis** — technique named (§5.2 item 5), analysis at depth >= 3,
  root cause statement, contributing factors list.
- **9.5 Impact Assessment** — duration, affected users/services, error rates, SLO
  budget consumed, revenue impact.
- **9.6 What Went Well** — positive aspects of detection, response, communication,
  escalation.
- **9.7 Action Items** — table: ID, Category (prevent/detect/mitigate), Description,
  Owner, Deadline, Ticket.
- **9.8 Lessons Learned** — key takeaways, links to related incidents, systemic
  recommendations.
- **9.9 Uncovered Risks** — what this post-mortem did NOT analyze.
  Mandatory — never empty, in every mode. Examples: "revenue impact not quantified —
  no transaction-value tracking", "only the primary service analyzed — downstream
  cascade not traced".

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