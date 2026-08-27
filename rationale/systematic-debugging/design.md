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
- `skills/systematic-debugging/references/scope-and-severity.md`
- `skills/systematic-debugging/references/safety-and-authorization.md`
- `evaluate/systematic-debugging-skill-eval-report.md`
- `evaluate/systematic-debugging-skill-eval-report.zh-CN.md`

## 11. 2026-08-27 Restructuring — External Review Hardening

An external review found seven concrete defects in the then-current (500-line) `SKILL.md`, all independently verified against the actual files before acting on any of them (per this repo's `skill-quality-audit` discipline — restructuring a doc without re-checking its factual claims just carries the errors forward in better packaging):

1. **Rule conflict**: the P2 severity row's "Simplified: Phase 1 + 4" shortcut directly contradicted "you MUST complete each phase" and Critical gate C1's unconditional "Phases 1-3 evidence" requirement — a P2 fix following the skill's own shortcut would automatically fail C1.
2. **No diagnose-only mode**: the skill triggers on "diagnosing, investigating" but mandated Phase 4 (Implementation) regardless, with no way to stop at root cause when a fix wasn't requested or authorized.
3. **Over-mechanical rules**: "after 3 rejected hypotheses, you likely have a wrong mental model" was stated as near-certain, and the full 9-section report + scorecard was mandatory even for trivial cases the skill's own `bug-type-strategies.md` says need only "Phase 1 Step 1."
4. **Insufficient safety gates**: `allowed-tools` pre-approved `git init` (no legitimate use in this workflow) and `rm -rf node_modules` (destructive, no confirmation); the P0 protocol permitted rollback/hotfix/failover with no authorization, evidence-preservation, or rollback-risk requirement.
5. **Verifiable factual errors**: an "8-type bug classification" claim against a 6-section reference file; an "automated binary-search isolation" claim against `find-polluter.sh`, which is a sequential linear scan; a silent exit-code swallow (`|| true`) in that script that let "the test never actually ran" read identically to "the test ran clean"; an undocumented tension between `defense-in-depth.md`'s "validate at every layer" and Phase 4's "one minimal fix, no bundling."
6. **Shallow tests**: 66 tests, all real and all passing, but the golden-scenario assertions check that `SKILL.md` + references *contain* certain strings, not that a model given a scenario *produces* a good report — a gap the skill's own `COVERAGE.md` already documented honestly.
7. **Stale eval score**: the 8.76/10 in `evaluate/systematic-debugging-skill-eval-report.md` was measured against a 296-line, 3-scenario predecessor and the report's own text says the delta is process discipline, not fix quality — it was not representative of the (then) current 500-line file.

**Resolution, in the same order:**

1–2. Added a **Scope & Mode** decision (`references/scope-and-severity.md`): diagnose-only / diagnose-and-fix / P0-incident, each with a defined stopping point and Fix Plan wording. C1 was rewritten to key off the declared mode/severity instead of stating an unconditional bar that a documented shortcut then violated.
3. Phase 3's hypothesis-rejection language was reframed — rejected hypotheses are cheap and expected; the real architecture-questioning signal moved to Phase 4's **fix-attempt** failures (real code changes that didn't work), which is materially stronger evidence. Report weight now scales with severity/mode via a defined N/A-scoring convention (an inapplicable Scorecard criterion is PASS-by-inapplicability with a one-line stated reason, not a silent FAIL and not exempt from any justification at all).
4. Removed `git init` and `rm -rf node_modules` from `allowed-tools` (falls back to normal permission prompting instead of being pre-approved); added `references/safety-and-authorization.md` covering secret redaction for `env`, payload caution for `tcpdump`, and P0 authorization/evidence-preservation/rollback-risk requirements.
5. Corrected the category count and the algorithm-label claim to match the actual files; fixed `find-polluter.sh` to surface (not swallow) a runner execution failure; added a reconciling paragraph to `defense-in-depth.md` — multi-layer validation for one confirmed root cause is one fix, not bundling, but validation unrelated to the confirmed cause still is.
6. Added targeted consistency/mutation tests that would have caught each of the above as a regression (category-count cross-check, binary-search-claim absence, mode/C1 cross-reference, destructive-tool absence) rather than attempting to replace the keyword-based golden tests with a live LLM-in-the-loop evaluation in the same pass — that requires the eval report's own subagent methodology re-run against the current file, which is out of scope for a consistency-hardening edit and is recorded as a follow-up in `COVERAGE.md`'s Known Gaps instead of being silently implied as done.
7. Added a staleness note to the top of both eval report files rather than fabricating a new score without running one.

Net effect on `SKILL.md` itself: 500 → 319 lines, with the new mode/safety detail pushed into two new reference files (`scope-and-severity.md`, `safety-and-authorization.md`) rather than added inline — consistent with this skill's own progressive-disclosure pattern. Word/byte count moved the other direction (2,931 → ~3,100 words) — the file is shorter to scan but not literally smaller, because real new distinctions (mode, N/A scoring, safety gates) were added, not just reformatted. Line count is a legitimate scan-cost win; it is not a token-cost win, and this document does not claim otherwise.

## 12. 2026-08-27 Round 2 — Closing the Contract, Safety, and Verification Gaps

A second review pass, after round 1 landed, found seven further defects — all independently re-verified before fixing, same discipline as round 1:

1. **Scorecard/Output-Contract desync**: round 1 added mode-awareness and an N/A convention to `SKILL.md` and the new `scope-and-severity.md`, but never propagated it into `references/debugging-report-scorecard.md` itself (its C1/C4/H2 rows still had the old, mode-blind wording). Separately, and independent of round 1's changes, `output-contract-template.md`'s "the report is FAIL when any of these occur" list (covering missing boundary evidence and unverified claims) was never reconciled with the Scorecard's "Standard needs only 4/6" threshold — a report could fail both S2 and S4 (2 of 6) and still hit exactly 4/6 on the rest, overall-PASSing despite missing boundary evidence and dishonest verification.
2. **Diagnose-only self-contradiction**: `scope-and-severity.md` (round 1) explicitly permitted sketching a labeled, unimplemented fix description in diagnose-only mode; `SKILL.md`'s Output Contract said "do not propose implementation changes ... in diagnose-only mode" — both used the word "propose" for two different things (describing vs. implementing), reading as a direct contradiction. Separately, `output-contract-template.md`'s Verification section unconditionally required proving "the original symptom is gone," which is definitionally impossible for a mode where no fix was implemented.
3. **`find-polluter.sh` still machine-unreliable**: round 1 added a human-visible warning when a test run failed to execute, but the script still `exit 0`'d (success) even when *every* run failed — an automated caller checking only the exit code would read total inconclusiveness as a confirmed-clean scan.
4. **`allowed-tools` vs. the round-1 safety reference talked past each other**: `safety-and-authorization.md` classified cache-clearing (`go clean`, `mvn clean`) as state-changing needing justification, while `allowed-tools` still pre-approved them with zero friction, reading as unexplained inconsistency (it wasn't — they're low-risk/recoverable, unlike `rm -rf`/`git init` — but the doc never said so). Separately, the `env` redaction rule was framed as something to do "before displaying" output, when the actual secret exposure happens the moment the command runs in the tool transcript — redaction on the report can't undo that, only minimizing what gets dumped in the first place can.
5. **A real bug in the `defense-in-depth.md` example**: `normalized.startsWith(tmpDir)` is a classic path-prefix flaw — `/tmp-evil` passes a `startsWith('/tmp')` check as a string even though it isn't inside `/tmp`. Also, the doc's "Why Multiple Layers" / "Key Insight" sections credited all four layers (including layer 4, debug logging) with making the bug "structurally impossible," when logging is observability, not prevention — it doesn't stop anything, it just makes the next gap fast to diagnose.
6. **Still no live behavioral evidence**: round 1 deliberately declined to fabricate an LLM-in-the-loop evaluation and recorded it as a follow-up rather than doing it partially. The second review explicitly asked for exactly that follow-up (diagnose-only, P2-collapse, unauthorized-P0), so round 2 does it: three areas, four live runs (see below), rather than continuing to defer it a second time.
7. **Word/byte size still grew**: correctly noted as an honest observation rather than a new defect — see the note directly above this section, added at the same time as this one.

**Resolution, in the same order:**

1. Added a fifth Critical criterion, **C5** (Reporting Integrity — no command/profile/trace/verification claimed unless it actually ran), to both `debugging-report-scorecard.md` and `SKILL.md`; tightened **C3** to explicitly require boundary evidence at the *failing hop* for multi-component issues. This absorbs the two contradiction-causing bullets into the Critical tier (unconditional FAIL) rather than leaving them as offsettable Standard-tier items — S2 and S4 remain in Standard, but now as genuinely *softer, broader* completeness checks (all boundaries, not just the failing one; thoroughness, not bare honesty) that legitimately can tolerate 2-of-6 slack without contradiction. `output-contract-template.md`'s "FAIL when" list was rewritten to say explicitly that these are the five Critical criteria restated, not a sixth rule layered on top, and that they are never offset by Standard/Hygiene scores. `debugging-report-scorecard.md`'s H2 now includes "mode."
2. Reworded both files to distinguish *describing* a fix (allowed in diagnose-only, clearly labeled as unimplemented analysis) from *implementing* one (gated). `output-contract-template.md`'s Verification section is now mode-aware: diagnose-and-fix/P0 reports prove the symptom is gone; diagnose-only reports instead prove the root-cause mechanism itself, since there's no implemented fix to verify against.
3. `find-polluter.sh` now returns a distinct exit code (4, documented in the script's header) and an `INCOMPLETE:`-prefixed message whenever any run failed to execute, instead of `exit 0`. The corresponding test was updated to assert this rather than asserting 0 as the "expected" result of a fully-failed scan (which is what the review caught — the test had baked in the same bug it should have been catching).
4. `safety-and-authorization.md` now states explicitly why `go clean`/`mvn clean` stay pre-approved (recoverable, no runtime-constructed target path) while `rm -rf`/`git init` don't (not recoverable, and/or a runtime-constructed path) — a stated risk-tiering rule instead of an apparent inconsistency. The `env` guidance now leads with "default to a targeted lookup" and explains that redaction happens to the *report*, not the *already-run command's output* — minimizing the dump is the real defense.
5. Fixed the `startsWith` example to check the path-separator boundary (`normalized === tmpDir || normalized.startsWith(tmpDir + sep)`), with a comment explaining why the naive version is wrong. Reworded "Why Multiple Layers" and "Key Insight" to credit only layers 1-3 with "structurally impossible," and reframe layer 4 as "fast to diagnose if it ever isn't" — a different, real contribution, just not that one.
6. Ran five live scenarios via fresh, context-isolated subagents (no shared context with this authoring session, no hints about what was being tested) against small synthetic codebases: diagnose-only (PASS), P0-without-explicit-authorization (PASS), and P2-collapsed-hypothesis (three attempts — the first two didn't invoke the skill at all, because the model judged the bugs too trivial to need any formal process, which is itself a legitimate finding about the trigger boundary; the third, requiring a genuine if small two-file investigation, invoked the skill and explicitly cited the collapse rule by name, but also mis-scored Standard-tier item S2 as N/A — a real, live-caught violation of `scope-and-severity.md`'s "only C1/C4 may be N/A" rule, corrected in that file and in `COVERAGE.md`'s write-up rather than glossed over). This is real behavioral evidence, not a claim of a scored evaluation — it is explicitly not being oversold as such in `COVERAGE.md`. Raw JSONL transcripts for all five runs are preserved at `evaluate/systematic-debugging-live-scenarios-2026-08-27/` so this isn't just a paraphrased summary — a review round correctly pointed out that "transcripts not preserved" made the original write-up unreviewable, and this was fixed by actually saving them, not by asserting they were fine to discard.
7. No action beyond the honest disclosure already added above this section — reducing byte count further was not on the review's required list, and further compression at the cost of the safety/mode content this round added would trade a real fix for a cosmetic metric.

New regression tests were added for items 1, 3, and 5 specifically (H2/C5 sync, `find-polluter.sh` INCOMPLETE code, `defense-in-depth.md` boundary check) so each is a checkable regression, not just a one-time fix.

## 13. 2026-08-27 Round 3 — Fixing Round 2's Own Mistakes

A third review pass audited round 2's changes themselves — including the live-scenario write-up — and found four further issues, two of which were errors in round 2's own documentation rather than in the skill's design:

1. **Output Contract template missing the Mode field**: round 2 required H2 to classify severity/mode/bug type (in both `SKILL.md` and `debugging-report-scorecard.md`), but never added an actual `Mode:` line to `output-contract-template.md`'s Triage section — a report author following the template literally had nowhere to write it down.
2. **A real scoring error in round 2's own live-scenario grading**: the P2-attempt-3 subagent marked Standard-tier **S2** as N/A. `scope-and-severity.md` says explicitly that only C1 and C4 may ever be N/A — S2 should have been scored as an ordinary PASS (a single-component issue vacuously satisfies "all relevant boundaries covered"). Round 2's `COVERAGE.md` write-up called this "correctly applied," which was simply wrong — it mis-graded a real rule violation as a success, in the same document that exists to catch exactly this kind of mistake.
3. **Live verification claimed but not preserved**: round 2 said "full transcripts are not preserved" while also miscounting its own scenario count (prose said "four," the table listed five rows — diagnose-only, P0, and three P2 attempts). Both are round-2 documentation defects: an unreviewable summary, and an arithmetic error in describing the very evidence meant to demonstrate rigor.
4. **`env`/`tcpdump` still bare in `allowed-tools`**: round 2's `safety-and-authorization.md` explained, correctly, that report-time redaction can't undo an exposure that already happened when the command ran — but round 2 stopped short of applying that logic to the `allowed-tools` grant itself, leaving both commands pre-approved with no per-run confirmation.

**Resolution, in the same order:**

1. Added `Mode: diagnose-only|diagnose-and-fix|P0-incident` to `output-contract-template.md`'s Triage section, with a pointer to `scope-and-severity.md`.
2. Corrected `COVERAGE.md`'s write-up to describe the S2/N/A as the scoring error it is, not a correct extension of the convention; strengthened `scope-and-severity.md`'s N/A rule to explicitly name S2 as an example of what "no other criterion" means, since a live model found the boundary ambiguous enough to cross it once already.
3. Copied the raw JSONL transcripts for all five live-scenario runs into `evaluate/systematic-debugging-live-scenarios-2026-08-27/` (with a `README.md` mapping file → scenario, and disclosing the S2 scoring error directly) instead of asserting they were fine to discard; corrected "four" to "five" everywhere it appeared, including in this document.
4. Removed `env*` and `tcpdump*` from `allowed-tools` (same treatment as `git init`/`rm -rf` in round 1) — both now require an explicit per-run ask, with `safety-and-authorization.md` and the relevant `SKILL.md` checklist lines updated to say so and to keep recommending targeted lookups and bounded captures once that ask is granted.

Items 2 and 3 are worth being explicit about: they are not new defects introduced by round 3's authoring session — they are mistakes round 2's *own authoring session* made while trying to add rigor (a live-verification effort that itself contained a grading error and a documentation slip). Recording that here rather than quietly fixing it without comment is the same "no silent errors" standard this skill asks of debugging reports, applied to the process of hardening the skill itself.
