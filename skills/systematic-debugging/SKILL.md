---
name: systematic-debugging
description: Use when debugging, diagnosing, or investigating any bug, test failure, flaky test, race condition, unexpected behavior, build failure, production incident, third-party breakage, root cause analysis, or performance regression before proposing fixes
---

# Systematic Debugging

## Overview

Random fixes waste time and create new bugs. Quick patches mask underlying issues and usually force a second debugging cycle.

**Core principle:** ALWAYS find root cause before attempting a permanent fix. Symptom fixes are failure.

**Debugging report quality is part of the job.** A report that lists guesses without evidence is not a passing debugging result.

## The Iron Law

```
NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST
```

If you haven't completed Phase 1, you cannot propose fixes.

### Diagnostic Instrumentation Exemption

Adding temporary code to collect evidence is **NOT a fix**. The following are explicitly permitted during Phase 1 investigation:

- Print/log statements to trace data flow (`fmt.Println`, `console.log`, `print()`, `logging.debug()`)
- Temporary breakpoints or debug flags
- Probe scripts that exercise a specific code path
- Temporary test harnesses to isolate behavior
- System commands (`df -h`, `lsof`, `strace`, `tcpdump`) to observe runtime state

**Rules:**
- Mark all diagnostic code clearly (e.g., `// DEBUG-INVESTIGATION` or `# DIAG`)
- Remove or revert all diagnostic instrumentation after root cause is identified
- Diagnostic code must not change program behavior — it only observes

## When to Use

Use for ANY technical issue:
- Test failures
- Bugs in production
- Unexpected behavior
- Performance problems
- Build failures
- Integration issues
- Flaky tests
- Race conditions
- Configuration drift
- Third-party breakage

**Use this ESPECIALLY when:**
- Under time pressure (emergencies make guessing tempting)
- "Just one quick fix" seems obvious
- You've already tried multiple fixes
- Previous fix didn't work
- You don't fully understand the issue

## Severity Triage (Do This FIRST)

Before entering the four phases, classify the issue. Different severity levels get different treatment:

```
+----------+---------------------+-----------------------------+------------------+
| Severity | Characteristics     | Strategy                    | Time Budget      |
+----------+---------------------+-----------------------------+------------------+
| P0       | Production down,    | 1. MITIGATE first (rollback | Mitigate: <15min |
| Critical | data loss, revenue  |    feature flag, fallback)   | Root cause: async|
|          | impact, security    | 2. Root cause AFTER stable  |                  |
+----------+---------------------+-----------------------------+------------------+
| P1       | Feature broken,     | Full 4-phase process        | 30-60min         |
| High     | blocking users,     | No shortcuts                |                  |
|          | test suite failing   |                             |                  |
+----------+---------------------+-----------------------------+------------------+
| P2       | Minor bug, cosmetic | Simplified: Phase 1 + 4    | 15-30min         |
| Medium   | edge case, non-     | (skip Pattern Analysis if   |                  |
|          | blocking            | cause is obvious)           |                  |
+----------+---------------------+-----------------------------+------------------+
```

### P0 Protocol: Mitigate First, Investigate Second

For production emergencies, the priority is **stopping the bleeding**:

1. **Mitigate immediately** (pick the fastest safe option):
   - Rollback to last known good deploy
   - Disable via feature flag
   - Apply targeted hotfix (e.g., retry, circuit breaker)
   - Redirect traffic / failover

2. **Verify mitigation works** - confirm service is restored

3. **THEN launch full root cause investigation** (Phases 1-4)
   - The mitigation is NOT the fix. It buys time.
   - Schedule root cause analysis within 24 hours
   - The permanent fix still requires the full process

**Why this isn't "skipping the process":** Mitigation and root cause fixing are separate concerns. Stopping revenue loss is an operational decision, not a debugging decision. The debugging process applies to the permanent fix.

### Bug Type Quick Reference

Different bug types need different investigation strategies:

| Bug Type | Primary Investigation | Key Tools/Techniques |
|----------|----------------------|---------------------|
| Logic error / wrong output | Trace data flow backward | Debugger, print statements, `references/root-cause-tracing.md` |
| Race condition / flaky test | Identify shared mutable state | `-race` flag (Go), thread sanitizer, `references/condition-based-waiting.md` |
| Memory leak / perf regression | Profile before hypothesizing | pprof (Go), Chrome DevTools, `time`/`perf` |
| Environment / "works on my machine" | Diff environments systematically; run environment health check (Phase 1 step 4) | `df -h`, `free -h`, `lsof`, `dmesg`, `env`, Docker, dependency versions |
| Third-party dependency change | Check changelogs and version diffs | `git log`, `go mod graph`, `npm ls` |
| Build / compilation error | Read error message literally | Usually Phase 1 step 1 is sufficient |
| Configuration error | Validate config propagation layer by layer | Phase 1 step 4 (multi-component evidence) |

See `references/bug-type-strategies.md` for detailed per-type guidance.

## Mandatory Gates

### 1. Root Cause Gate

Do not propose a permanent fix until you can state:
- what failed
- where it failed
- why it failed
- what evidence proves that cause

### 2. Evidence Gate

If the issue spans multiple components or boundaries, gather evidence at each boundary before selecting a fix.

Required evidence types:
- reproduction evidence
- recent change evidence
- boundary evidence
- data-flow or state evidence

### 3. Hypothesis Discipline Gate

One hypothesis at a time. One minimal test per hypothesis. No bundled changes.

### 4. Fix Attempt Gate

If 3 hypotheses or 3 fixes have failed, stop and question the architecture or mental model. Do not push to Fix #4 without escalation.

### 5. Reporting Integrity Gate

Never claim a command, profile, race run, trace, or verification was executed unless it actually ran.

If not run, say:
- `Not run in this environment`
- why
- exact command to run next

## The Four Phases

You MUST complete each phase before proceeding to the next.

### Phase 1: Root Cause Investigation

**BEFORE attempting ANY fix:**

1. **Read Error Messages Carefully**
   - Don't skip past errors or warnings
   - They often contain the exact solution
   - Read stack traces completely
   - Note line numbers, file paths, error codes

2. **Reproduce Consistently**
   - Can you trigger it reliably?
   - What are the exact steps?
   - Does it happen every time?
   - If not reproducible → gather more data, don't guess

3. **Check Recent Changes**
   - What changed that could cause this?
   - Git diff, recent commits
   - New dependencies, config changes
   - Environmental differences

4. **Check Environment Health**

   **WHEN symptoms include: intermittent failures, timeouts, "works on my machine", silent process death, or no obvious code cause:**

   Rule out infrastructure and OS-level issues BEFORE diving into code.
   Minimum checklist:
   - disk space: `df -h`
   - memory / OOM: `free -h && dmesg | grep -i oom` (Linux) or `top -l 1 | head -20` (macOS)
   - port conflicts: `lsof -i :<port>`
   - network / DNS: `nslookup <hostname>` and `curl -v <endpoint>`
   - file descriptors: `ulimit -a`
   - recent system events: `dmesg | tail -50` or `log show --last 10m`

   If environment is unhealthy, fix that first. A broken machine is not a code bug.

5. **Gather Evidence in Multi-Component Systems**

   **WHEN system has multiple components (CI → build → signing, API → service → database):**

   Before proposing fixes, instrument each boundary.
   For EACH component boundary:
   - log what enters the component
   - log what exits the component
   - verify config / environment propagation
   - confirm state at each layer

   Run once, identify the exact failing boundary, then narrow the investigation to that layer.

6. **Trace Data Flow**

   **WHEN error is deep in call stack:**

   See `references/root-cause-tracing.md` for the complete backward tracing technique.

   **Quick version:**
   - Where does bad value originate?
   - What called this with bad value?
   - Keep tracing up until you find the source
   - Fix at source, not at symptom

7. **Use Parallel Investigation for Complex Systems**

   **WHEN system has 3+ components or investigation is slow:**

   Launch independent tracks in parallel when possible:
   - logs / error messages
   - recent git changes / deploys
   - working vs broken environment diff
   - external dependency / third-party status

   Use the Agent tool for parallel tracks, then synthesize the results before choosing a fix.

### Phase 2: Pattern Analysis

**Find the pattern before fixing:**

1. **Find Working Examples**
   - Locate similar working code in same codebase
   - What works that's similar to what's broken?

2. **Compare Against References**
   - If implementing pattern, read reference implementation COMPLETELY
   - Don't skim - read every line
   - Understand the pattern fully before applying

3. **Identify Differences**
   - What's different between working and broken?
   - List every difference, however small
   - Don't assume "that can't matter"

4. **Understand Dependencies**
   - What other components does this need?
   - What settings, config, environment?
   - What assumptions does it make?

### Phase 3: Hypothesis and Testing

**Scientific method:**

1. **Form Single Hypothesis**
   - State clearly: "I think X is the root cause because Y"
   - Write it down
   - Be specific, not vague

2. **Test Minimally**
   - Make the SMALLEST possible change to test hypothesis
   - One variable at a time
   - Don't fix multiple things at once

3. **Verify Before Continuing**
   - Did it work? Yes → Phase 4
   - Didn't work? Form NEW hypothesis
   - DON'T add more fixes on top

4. **When You Don't Know**
   - Say "I don't understand X"
   - Don't pretend to know
   - Ask for help
   - Research more

5. **Maintain a Hypothesis Log**

   Track what you've tried to avoid circular investigation:

   ```
   | # | Hypothesis              | Evidence For    | Evidence Against       | Result   | Time |
   |---|-------------------------|-----------------|------------------------|----------|------|
   | 1 | Empty config path       | Error at line 42| Config file exists     | Rejected | 8min |
   | 2 | Race in goroutine pool  | Flaky under load| Passes with -race      | Rejected | 12min|
   | 3 | Stale cache after deploy | Cache TTL=1h    | Deploy was 2h ago      | CONFIRMED| 5min |
   ```

   **Time-box each hypothesis:** Max 15-20 minutes per hypothesis. If you can't confirm or reject within the time-box, note what's blocking and move to the next hypothesis. Return later with more information.

   **After 3 rejected hypotheses:** STOP. You likely have a wrong mental model of the system. Re-read Phase 1 evidence. Consider asking someone who knows the codebase.

### Phase 4: Implementation

1. **Create Failing Test Case**
   - Simplest possible reproduction
   - Automated test if possible
   - One-off test script if no framework
   - MUST have before fixing
   - Use the `tdd-workflow` skill for writing proper failing tests

2. **Implement Single Fix**
   - Address the root cause identified
   - ONE change at a time
   - No "while I'm here" improvements
   - No bundled refactoring

3. **Verify Fix**
   - Test passes now?
   - No other tests broken?
   - Issue actually resolved?

4. **If Fix Doesn't Work**
   - STOP
   - Count: How many fixes have you tried?
   - If < 3: Return to Phase 1, re-analyze with new information
   - **If ≥ 3: STOP and question the architecture (step 5 below)**
   - DON'T attempt Fix #4 without architectural discussion

5. **If 3+ Fixes Failed: Question Architecture**

   **Pattern indicating architectural problem:**
   - Each fix reveals new shared state/coupling/problem in different place
   - Fixes require "massive refactoring" to implement
   - Each fix creates new symptoms elsewhere

   **STOP and question fundamentals:**
   - Is this pattern fundamentally sound?
   - Are we "sticking with it through sheer inertia"?
   - Should we refactor architecture vs. continue fixing symptoms?

   **Discuss with your human partner before attempting more fixes**

   This is NOT a failed hypothesis - this is a wrong architecture.

## Quality Scorecard

Every debugging report MUST include a scorecard verdict. Use `references/debugging-report-scorecard.md` and include the result in the final report.

### Critical

Any FAIL in this tier means the whole debugging result is FAIL.

| ID | Requirement |
|----|-------------|
| C1 | No permanent fix proposed before Phases 1-3 evidence exists |
| C2 | Root cause is stated as a cause, not a symptom |
| C3 | Root cause is backed by concrete evidence from reproduction, trace, profile, or boundary instrumentation |
| C4 | Hypothesis log exists and matches the investigation path taken |

### Standard

Pass at least 4 of 6.

| ID | Requirement |
|----|-------------|
| S1 | Reproduction includes exact commands or steps |
| S2 | Evidence covers all relevant component boundaries |
| S3 | Fix scope is minimal and justified |
| S4 | Verification uses explicit commands and expected result |
| S5 | Residual risks and follow-ups are honest and specific |
| S6 | If 3+ fixes failed, the report explicitly questions architecture |

### Hygiene

Pass at least 3 of 4.

| ID | Requirement |
|----|-------------|
| H1 | Report follows the output contract order |
| H2 | Severity and bug type are classified |
| H3 | Owners / ETA are included when follow-ups exist |
| H4 | Wording is concise and avoids filler or hand-waving |

### Scorecard Output Rules

Always report:

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

Interpretation:
- any Critical fail => overall FAIL
- Standard below 4/6 => overall FAIL
- Hygiene below 3/4 => overall FAIL

## Red Flags - STOP and Follow Process

If you catch yourself thinking:
- "Quick fix for now, investigate later"
- "Just try changing X and see if it works"
- "Add multiple changes, run tests"
- "Skip the test, I'll manually verify"
- "It's probably X, let me fix that"
- "I don't fully understand but this might work"
- "Pattern says X but I'll adapt it differently"
- "Here are the main problems: [lists fixes without investigation]"
- Proposing solutions before tracing data flow
- **"One more fix attempt" (when already tried 2+)**
- **Each fix reveals new problem in different place**

**ALL of these mean: STOP. Return to Phase 1.**

**If 3+ fixes failed:** Question the architecture (see Phase 4.5)

## Your Human Partner's Signals You're Doing It Wrong

**Watch for these redirections:**
- "Is that not happening?" - You assumed without verifying
- "Will it show us...?" - You should have added evidence gathering
- "Stop guessing" - You're proposing fixes without understanding
- "Ultrathink this" - Question fundamentals, not just symptoms
- "We're stuck?" (frustrated) - Your approach isn't working

**When you see these:** STOP. Return to Phase 1.

## Anti-Examples - BAD / GOOD Debugging Reports

These are behavioral constraints, not cosmetic writing advice. The full BAD/GOOD library lives in `references/bad-good-debugging-reports.md`.

Required anti-example coverage:
- symptom presented as root cause
- guessed fix without reproduction
- sleep/retry used to hide a race
- performance fix without profiling
- missing boundary evidence in multi-component systems
- bundled fixes destroying attribution
- repeated failed fixes without questioning architecture

**P0 shortcut:** Triage -> Mitigate -> Verify mitigation -> THEN Phases 1-4 for permanent fix.

## Load References Selectively

When the bug appears deep in the stack, the bad value origin is unclear, or you need to trace caller-to-source:
→ Load `references/root-cause-tracing.md` for backward tracing technique — call chain mapping, value-origin tracking templates, and structured evidence collection from callers to root source.
When the root cause is invalid data, unsafe state transition, or a missing guard at one of several layers:
→ Load `references/defense-in-depth.md` for multi-layer guard patterns, layer responsibility matrix, and fix templates that address defense at the correct layer rather than patching symptoms.
When flaky tests, retries, sleeps, polling loops, or async timing issues appear:
→ Load `references/condition-based-waiting.md` for condition-based wait patterns, polling/retry templates, race condition detection strategies, and Go `-race` / thread sanitizer usage.
When the bug type is unclear, symptoms overlap multiple categories, or you need a per-class strategy:
→ Load `references/bug-type-strategies.md` for the 8-type bug classification matrix (logic error, race condition, data corruption, resource leak, config error, integration failure, performance regression, flaky test) with tailored investigation strategies.
When writing the final debugging report or verifying report completeness against the required sections:
→ Load `references/output-contract-template.md` for the 9-section output contract template (Triage, Reproduction, Evidence, Hypothesis log, Root cause, Fix plan, Verification, Residual risk, Scorecard).
When grading the quality of a debugging report or deciding PASS vs FAIL on report completeness:
→ Load `references/debugging-report-scorecard.md` for the scorecard rubric with per-section PASS/FAIL criteria and total score thresholds.
When the report quality is weak, overly hand-wavy, or you need concrete improvement patterns:
→ Load `references/bad-good-debugging-reports.md` for the BAD/GOOD library of report anti-patterns — vague diagnosis, missing reproduction steps, unverified fixes, and hand-wavy root cause claims with corrected alternatives.
When a test suite introduces filesystem or state pollution and you need to isolate the polluting test:
→ Run `scripts/find-polluter.sh` for automated binary-search isolation of the test that causes pollution, with before/after state diffs.

**Related skills:**
- **`tdd-workflow`** - For creating failing test case (Phase 4, Step 1)
- **`unit-test`** - Add/extend regression tests after root-cause fix
- **`go-code-reviewer`** - Validate risk and regression impact of fix

## Output Contract (Required)

Return debugging outputs using `references/output-contract-template.md`.

Minimum required order:
1. Triage
2. Reproduction
3. Evidence collected
4. Hypothesis log
5. Root cause
6. Fix plan/change
7. Verification
8. Residual risk/follow-ups
9. Scorecard

Minimum quality requirements:
- Do not propose implementation changes until sections 1-5 are complete
- Hypothesis log must contain at least one row for non-trivial debugging
- Evidence must cover every relevant component boundary
- Root cause must explain source, not just symptom
- Verification must include explicit commands or exact checks

## Regression Commands (Skill Maintenance)

Run all regression checks when editing this skill:

```bash
./scripts/run_regression.sh
```

That wrapper must execute:
- `python3 -m unittest discover -s scripts/tests -p 'test_*.py' -v`
- `./scripts/find-polluter.sh --help`
