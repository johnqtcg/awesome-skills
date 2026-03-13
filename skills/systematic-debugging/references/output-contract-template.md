# Systematic Debugging Output Contract

Use this structure for every debugging report so reviewers can verify root-cause quality, investigation completeness, and whether the result should PASS or FAIL.

## Table of Contents

1. [Triage](#1-triage)
2. [Reproduction](#2-reproduction)
3. [Evidence Collected](#3-evidence-collected)
4. [Hypothesis Log](#4-hypothesis-log)
5. [Root Cause](#5-root-cause)
6. [Fix Plan and Change](#6-fix-plan-and-change)
7. [Verification](#7-verification)
8. [Residual Risk and Follow-ups](#8-residual-risk-and-follow-ups)
9. [Scorecard](#9-scorecard)
10. [PASS/FAIL Rules](#passfail-rules)

## 1. Triage

- Severity: `P0|P1|P2`
- Bug type: `logic|race|perf|environment|dependency|build|config|other`
- User impact: `<one line>`
- Mitigation status (P0 only): `<what was mitigated and when>`
- Investigation status: `investigating|root-cause-confirmed|fix-verified|blocked`

## 2. Reproduction

- Repro status: `consistent|intermittent|not-yet`
- Exact command(s) or exact manual steps:

```bash
<command>
```

- Observed error/output:

```text
<key error lines>
```

- Expected behavior:
- Notes on frequency or timing:

## 3. Evidence Collected

Minimum evidence for any non-trivial issue:
- recent changes inspected
- at least one concrete artifact from runtime behavior
- boundary evidence for each relevant component hop

Template:
- Recent changes inspected: `<commit/pr/deploy range>`
- Boundary evidence:
  - `<component A -> B>`
  - `<component B -> C>`
- Data-flow trace summary: `<where bad value or bad state originates>`
- Profiling / tracing evidence (if perf or concurrency): `<pprof / trace / race output>`
- Working vs broken comparison: `<optional but preferred>`

## 4. Hypothesis Log

At least one row for non-trivial debugging. Add a new row whenever a hypothesis is rejected or confirmed.

| # | Hypothesis | Evidence For | Evidence Against | Result | Time |
|---|------------|--------------|------------------|--------|------|
| 1 |            |              |                  |        |      |

Rules:
- use `CONFIRMED|REJECTED|OPEN`
- do not skip this section if you evaluated multiple possibilities
- if first hypothesis was rejected, there should usually be at least 2 rows

## 5. Root Cause

- Root cause statement (single sentence):
- Why this is the source (not symptom):
- Evidence linking source to symptom:
- Files/lines:
  - `<absolute-path>:<line>`

Good root cause statement:
- identifies the source condition
- names the failing boundary or assumption
- explains why the symptom appears downstream

Bad root cause statement:
- repeats the symptom
- names the fix instead of the cause
- blames a component without evidence

## 6. Fix Plan and Change

- Failing test or probe added first: `yes|no` (if no, explain why)
- Minimal fix applied:
- Diff scope justification:
- Alternatives considered but rejected:

If no permanent fix is proposed yet, say so explicitly and explain what evidence is still missing.

## 7. Verification

- Validation commands:

```bash
<test/lint/build/profile commands>
```

- Results: `pass|fail|partial`
- Regression checks run:
- Not run in this environment:
- Why anything was skipped:

Verification should prove:
- the original symptom is gone
- the intended failing scenario is now covered
- adjacent regressions were considered

## 8. Residual Risk and Follow-ups

- Uncovered risks:
- Monitoring / alerts added:
- Follow-up owner and ETA:
- Escalation needed: `yes|no`

Be explicit when:
- mitigation exists but permanent fix is pending
- intermittent behavior remains
- architecture review is needed after repeated failed fixes

## 9. Scorecard

Use the tier definitions from `references/debugging-report-scorecard.md`.

```json
{
  "scorecard": {
    "critical": "PASS|FAIL",
    "standard": "x/6",
    "hygiene": "y/4",
    "overall": "PASS|FAIL"
  }
}
```

Also include:
- Failed items: `[C2, S4]`
- Short rationale: `<why any items failed>`

## PASS/FAIL Rules

The report is PASS only when all of these hold:
- Critical tier has no FAIL
- Standard score is at least `4/6`
- Hygiene score is at least `3/4`
- sections 1-9 are present in order

The report is FAIL when any of these occur:
- fix proposed before root cause evidence
- no hypothesis log despite non-trivial investigation
- root cause is a symptom, not a source
- verification is asserted without commands or exact checks
- multi-component issue lacks boundary evidence
