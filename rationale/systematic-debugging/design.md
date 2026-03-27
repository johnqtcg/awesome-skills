---
title: systematic-debugging skill design rationale
owner: awesome-skills maintainers
status: active
last_updated: 2026-03-27
applicable_versions: current repository version
---

# systematic-debugging Skill Design Rationale

`systematic-debugging` is a debugging framework that turns debugging work from intuition-driven patching into a strict "root cause first, fix second" investigation process. Its core idea is: **the goal of debugging is to first classify severity, collect evidence, form a single hypothesis, validate it minimally, and only then move into implementation and verification, while delivering the whole process as a report that can be reviewed and judged PASS/FAIL.** That is why the skill turns Severity Triage, the Iron Law, the four phases, Hypothesis Discipline, the Fix Attempt Gate, the Scorecard, and the Output Contract into one tightly constrained workflow.

## 1. Definition

`systematic-debugging` is used for:

- debugging test failures, production incidents, intermittent issues, performance regressions, build failures, and third-party breakages,
- requiring root-cause investigation before any permanent fix,
- using explicit hypotheses, boundary evidence, and data-flow tracing to locate the true source,
- handling P0 incidents by mitigating first and then returning to full root-cause analysis,
- and enforcing debugging quality through report structure and scoring rules.

Its output is not just a fix suggestion. It also includes:

- triage,
- reproduction,
- evidence collected,
- hypothesis log,
- root cause,
- fix plan/change,
- verification,
- residual risk/follow-ups,
- scorecard.

From a design perspective, it is closer to a debugging-governance framework than to a prompt that simply reads an error and jumps to a repair.

## 2. Background and Problems

The main problem this skill addresses is not that models cannot fix bugs. It is that debugging naturally drifts toward a few high-risk impulses:

- seeing a symptom and editing immediately,
- changing multiple things at once and destroying attribution,
- declaring success after a change without real verification.

Without process constraints, the most common failures cluster into eight categories:

| Problem | Typical consequence |
|---------|---------------------|
| No root-cause investigation first | symptom gets patched and the issue returns quickly |
| No reproduction check first | the issue seems fixed only because it did not reappear yet |
| No recent-change review | the most likely trigger gets missed |
| No environment-health check | full disk, port conflicts, or OOM get treated like code bugs |
| No boundary evidence collection | in multi-component systems, nobody knows which layer actually failed |
| No explicit hypothesis | confirmed cause and guesswork get mixed together |
| Multiple fixes bundled together | nobody knows which change actually mattered |
| Repeated failures without questioning architecture | investigation degrades into Fix #4, Fix #5, and endless trial-and-error |

The design logic of `systematic-debugging` is to make "what severity is this, how should it be investigated, is the evidence strong enough to support root cause, and was the fix actually verified?" explicit before implementation is allowed.

## 3. Comparison with Common Alternatives

It helps to compare it with a few common alternatives:

| Dimension | `systematic-debugging` skill | Asking a model to "fix this bug" | Manual intuition-driven debugging |
|-----------|------------------------------|----------------------------------|-----------------------------------|
| Root-cause-first discipline | Strong | Weak | Medium |
| Explicit phase structure | Strong | Weak | Weak |
| Separation of hypothesis and verification | Strong | Weak | Medium |
| Multi-boundary evidence collection | Strong | Weak | Medium |
| Resistance to impulsive patching | Strong | Weak | Weak |
| P0 mitigation vs permanent-fix separation | Strong | Weak | Medium |
| Debug-report auditability | Strong | Weak | Weak |
| PASS/FAIL quality judgment | Strong | Weak | Weak |

Its value is not only that the debugging write-up looks more formal. Its value is that it turns debugging from one-off trial-and-error into an engineering process with evidence, gates, and reviewable outputs.

## 4. Core Design Rationale

### 4.1 Severity Triage Comes Before Code Analysis

Before entering the four phases, `systematic-debugging` requires classifying the issue as:

- `P0`,
- `P1`,
- or `P2`.

This matters because different severity levels have different debugging goals. A P0 is first an operational problem and must be stabilized quickly; a P1 goes through the full four-phase process; a P2 can take the simplified path, usually centered on Phase 1 + Phase 4, with Pattern Analysis skipped when the cause is already obvious. The skill therefore bakes "mitigate first, investigate second" into the P0 protocol instead of pretending every incident should be handled identically.

The value of this design is that it cleanly separates service restoration from permanent correction. That prevents emergency incidents from being slowed down by over-idealized investigation, while also preventing a temporary mitigation from being mistaken for the real fix.

### 4.2 The Iron Law Is Written So Absolutely

The skill's Iron Law is:

```text
NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST
```

This is not stylistic preference. It is the central constraint of the skill. It explicitly forbids:

- fixing before investigating,
- stacking multiple changes first and then checking the result,
- proposing a permanent fix first and only later backfilling the investigation.

That is also why the skill separately carves out a diagnostic instrumentation exemption. Temporary logs, breakpoints, and probe scripts are not fixes; they are observation tools. This preserves the "investigate first" rule without blocking necessary evidence collection.

### 4.3 The Four Phases Form the Skeleton of the Skill

`systematic-debugging` fixes the debugging flow into:

1. Root Cause Investigation
2. Pattern Analysis
3. Hypothesis and Testing
4. Implementation

These phases are not cosmetic sectioning. They prevent several common jumps:

- going straight from symptom to fix,
- seeing an apparent cause and skipping working-example comparison,
- touching code before forming a single hypothesis,
- finishing a change without explicit verification.

The evaluation makes this especially clear: without-skill responses naturally collapsed toward `Root Cause -> Fix -> Test`, while with-skill responses consistently preserved the full Phase 1→2→3→4 structure. That shows one of the skill's main increments is not stronger repair ability, but stronger process integrity.

### 4.4 Explicit Hypothesis Is a Core Design Rule, Not Just a Writing Convention

The skill forces statements like:

> I think X is the root cause because Y

and it requires one hypothesis at a time plus one minimal test for that hypothesis.

This matters because the most common debugging distortion is not having zero ideas. It is treating "the explanation that currently feels most likely" as though it were "the cause already proven." Explicit hypotheses force the debugger to answer:

- what exactly I currently believe the cause is,
- what evidence supports that belief,
- what evidence could still disprove it.

That turns Phase 3 into a real scientific-method step instead of a more polished version of intuition.

### 4.5 It Enforces "One Hypothesis, One Minimal Change"

The skill explicitly forbids bundled changes and requires:

- one hypothesis at a time,
- one minimal test per hypothesis,
- one fix at a time.

This is a very strong design choice because one of the most common reasons debugging goes wrong is that several plausible causes get changed together. Even if the issue disappears, nobody knows which change actually mattered. The skill therefore preserves attribution so that a debugging result is not only "passing" but also "understood."

### 4.6 Environment Health Check Lives in Phase 1

When symptoms include:

- intermittent failures,
- timeouts,
- "works on my machine",
- silent process death,
- or no obvious code cause,

the skill explicitly says to check environment health first and even suggests commands like `df -h`, `lsof`, `dmesg`, and `nslookup`.

This is mature design because many issues that look like code bugs are actually:

- full disk,
- OOM kills,
- port conflicts,
- DNS/network failures,
- file-descriptor exhaustion.

By front-loading environment checks, the skill explicitly acknowledges that not every failure should begin inside the source code. This greatly reduces time wasted debugging at the wrong layer.

### 4.7 Multi-Component Systems Require Boundary Evidence

For systems like CI -> build -> signing or API -> service -> database, the skill explicitly requires:

- recording what enters each boundary,
- recording what exits each boundary,
- verifying environment/config propagation,
- using one round of observation to determine which boundary breaks.

This is critical because the most common misread in multi-component debugging is to treat the layer where the error appears as the layer that caused it. Boundary evidence forces the debugger to build an evidence chain instead of reasoning by proximity. The evaluation's multi-layer error-mapping scenario is a direct example of why this rule matters.

### 4.8 Phase 2 Preserves Pattern Analysis

A natural question is: if Phase 1 already identifies the root cause, why keep Pattern Analysis as a separate phase?

Because root-cause investigation answers "where did this fail," while Pattern Analysis answers:

- what similar code is already working,
- what the full reference pattern actually looks like,
- what all the differences are between working and broken behavior,
- and what hidden assumptions the current component depends on.

This phase is the skill's guardrail against jumping from a plausible cause to code changes too early. In the evaluation, working-example comparison was missing in some without-skill scenarios, which is enough to show that this step does not reliably appear unless the structure requires it.

### 4.9 The Fix Attempt Gate Forces Escalation After Three Failed Tries

The skill explicitly says:

- after 3 failed hypotheses or 3 failed fixes,
- stop,
- question the mental model or architecture,
- and do not drift into Fix #4 without escalation.

This design is valuable because repeated debugging failure often means the problem is not "this one line is wrong," but "the whole problem is being interpreted inside the wrong architecture or abstraction." Hard-coding that escalation point prevents endless local patching when the real issue is structural.

### 4.10 The P0 Protocol Says "Mitigate First, Investigate After"

For P0 incidents, the skill requires:

1. rollback / feature flag / failover / targeted hotfix first,
2. verify mitigation worked,
3. then begin full root-cause investigation within 24 hours.

This solves a common confusion: does mitigating first mean skipping the debugging process? The skill's answer is no. Mitigation is an operational action; permanent correction is the debugging action. By separating them, the skill avoids delaying recovery for the sake of purity while also refusing to let emergency response replace actual root-cause work.

### 4.11 Debugging Report Quality Is Also a Hard Constraint

`systematic-debugging` does not only govern actions. It also requires the final report to include an explicit scorecard verdict:

- Critical,
- Standard,
- Hygiene.

This is a strong design choice because many debugging results appear to include:

- a root cause,
- a fix,
- and a test,

while still failing in substance because:

- the root cause is actually a symptom,
- the evidence is incomplete,
- the hypothesis log is missing,
- the verification is vague.

The scorecard separates "the report looks complete" from "the report is trustworthy." It explicitly allows a report to be judged `FAIL` when the investigation or verification quality is weak. That makes the skill's output not only a technical conclusion, but a debugging artifact whose quality can be judged.

### 4.12 Fixed-Order Output Contract

The skill requires debugging reports to follow this order:

1. Triage
2. Reproduction
3. Evidence Collected
4. Hypothesis Log
5. Root Cause
6. Fix Plan and Change
7. Verification
8. Residual Risk and Follow-ups
9. Scorecard

This solves a very practical problem: when report structure is fluid, reviewers cannot quickly tell:

- whether investigation really happened before fixing,
- whether an explicit hypothesis existed,
- whether root cause is truly source-level,
- whether verification actually ran.

A fixed output order turns those into checkable structure instead of subjective reading impressions.

### 4.13 References Are Loaded by Symptom

The skill's references are not meant to be loaded all at once. They are routed by situation:

- deep-stack issues load `root-cause-tracing.md`,
- missing guards or layered validation load `defense-in-depth.md`,
- flaky / async / sleep issues load `condition-based-waiting.md`,
- unclear bug category loads `bug-type-strategies.md`,
- final report writing loads `output-contract-template.md`,
- report grading loads `debugging-report-scorecard.md`.

This structure is sensible because debugging problems vary widely, but not every run needs every debugging technique in context. The skill keeps core discipline in `SKILL.md` and loads specialized tactics only when symptoms warrant them, balancing coverage against token cost.

## 5. Problems This Design Solves

Combining the current `SKILL.md`, key references, and the evaluation report, the skill solves the following problems:

| Problem type | Corresponding design | Practical effect |
|--------------|----------------------|------------------|
| Seeing a bug and fixing immediately | Iron Law + four-phase process | Forces investigation before implementation |
| Confusing root cause with guesswork | Hypothesis Discipline | Makes root-cause claims more testable |
| Unclear breakpoints in multi-component systems | Boundary Evidence | Locates the failing hop faster |
| Mistaking environment failures for code bugs | Environment Health Check | Reduces debugging at the wrong layer |
| Losing attribution across repeated edits | Single hypothesis, single minimal change | Preserves causal understanding |
| Endless Fix #4 / #5 trial-and-error | Fix Attempt Gate | Escalates to architecture discussion sooner |
| Reports that look complete but are not trustworthy | Output Contract + Scorecard | Makes review and replay easier |
| Emergency mitigation replacing real debugging | P0 protocol | Preserves both restoration and root-cause analysis |

## 6. Key Highlights

### 6.1 It Turns Debugging from "Fixing Bugs" into "Investigating Bugs"

This is the skill's biggest upgrade. Evidence comes first; repair is allowed later.

### 6.2 The Four-Phase Structure Is Its Most Visible Process Strength

Phase 1→2→3→4 separates investigation, analysis, hypothesis, and implementation so debugging does not collapse into "look once, patch once."

### 6.3 The Explicit Hypothesis Mechanism Is Crucial

It forces the debugger to turn "I think this is the cause" into a testable statement instead of leaving it as hidden intuition.

### 6.4 Environment Health and Boundary Evidence Make It Useful for Real Systems

Many debugging playbooks focus only on code. `systematic-debugging` deliberately includes OS state, config propagation, and cross-component boundaries in root-cause work.

### 6.5 It Has Direct Countermeasures Against Debugging Impulses

Red flags, escalation after three failed attempts, and the P0 mitigate-then-investigate split all directly target the most common human debugging failures.

### 6.6 Its Real Increment Is Process Discipline More Than Repair Ability

The evaluation already shows this: the base model was already strong at reading errors, tracing data flow, identifying root cause, and writing repair code. The real delta came from phase structure, explicit hypothesis, investigation completeness, verification discipline, and report auditability. That means the skill's core value is debugging governance, not simply "smarter fixes."

## 7. When to Use It — and When Not To

| Scenario | Suitable | Reason |
|----------|----------|--------|
| Test failures, build failures, and production incidents | Very suitable | These are its core use cases |
| Multi-layer call chains or multi-component systems | Very suitable | Boundary evidence is especially valuable |
| Intermittent, flaky, or race-related issues | Very suitable | Hypothesis discipline and evidence collection matter most here |
| Situations with strong pressure for a quick fix | Very suitable | That is exactly the failure mode it is designed to constrain |
| Obvious one-line typo or compile error | Suitable but can be lighter | This often fits the simplified P2 path |

## 8. Conclusion

The real strength of `systematic-debugging` is not that it invents smarter fixes. It is that it systematizes the judgments most likely to go wrong in debugging: classify severity first, investigate before changing code, form a single hypothesis, validate minimally, implement only after the source is understood, and make the whole process reviewable, scoreable, and reproducible by another engineer.

From a design perspective, the skill embodies a clear principle: **the key to high-quality debugging is not writing a fix faster, but knowing earlier what you actually understand, where the evidence comes from, whether the hypothesis was tested, and whether the final change rests on a real root cause instead of a convenient symptom.** That is why it is especially well suited to bug investigation, incident debugging, and root-cause analysis workflows.

## 9. Document Maintenance

This document should be updated when:

- the Severity Triage, Iron Law, four-phase flow, Mandatory Gates, Scorecard, Output Contract, or P0 protocol in `skills/systematic-debugging/SKILL.md` change,
- key rules in `skills/systematic-debugging/references/root-cause-tracing.md`, `bug-type-strategies.md`, `defense-in-depth.md`, `condition-based-waiting.md`, `output-contract-template.md`, `debugging-report-scorecard.md`, or `bad-good-debugging-reports.md` change,
- key supporting conclusions in `evaluate/systematic-debugging-skill-eval-report.md` or `evaluate/systematic-debugging-skill-eval-report.zh-CN.md` change.

Review quarterly; review immediately if the phase structure, hypothesis discipline, P0 protocol, or scorecard / output contract of `systematic-debugging` changes substantially.

## 10. Further Reading

- `skills/systematic-debugging/SKILL.md`
- `skills/systematic-debugging/references/root-cause-tracing.md`
- `skills/systematic-debugging/references/bug-type-strategies.md`
- `skills/systematic-debugging/references/output-contract-template.md`
- `skills/systematic-debugging/references/debugging-report-scorecard.md`
- `evaluate/systematic-debugging-skill-eval-report.md`
- `evaluate/systematic-debugging-skill-eval-report.zh-CN.md`
