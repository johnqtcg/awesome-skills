---
name: systematic-debugging
description: Use when debugging, diagnosing, or investigating any bug, test failure, flaky test, race condition, unexpected behavior, build failure, production incident, third-party breakage, root cause analysis, or performance regression before proposing fixes
allowed-tools: Read, Grep, Glob, Bash(go test*), Bash(go build*), Bash(go run*), Bash(go vet*), Bash(go mod graph*), Bash(go generate*), Bash(go clean*), Bash(git log*), Bash(git diff*), Bash(npm ls*), Bash(python3 -m unittest*), Bash(./scripts/find-polluter.sh*), Bash(df*), Bash(free*), Bash(lsof*), Bash(strace*), Bash(dmesg*), Bash(top*), Bash(log show*), Bash(nslookup*), Bash(curl*), Bash(ulimit*), Bash(mvn clean*)
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

Phase 1 always applies. How much of Phases 2-4 apply, and what the final report requires, is set by Severity Triage and Scope & Mode below — read both before investigating.

### Diagnostic Instrumentation Exemption

Adding temporary code to collect evidence is **NOT a fix**. Permitted during Phase 1: print/log statements, temporary breakpoints or debug flags, probe scripts, temporary test harnesses, system commands (`df -h`, `lsof`, `strace`, `tcpdump`) to observe runtime state. "Permitted" here is about scope (it's investigation, not a fix), not about pre-approval — `tcpdump` and `env` specifically are not pre-approved in `allowed-tools` and require asking first; see `references/safety-and-authorization.md`.

**Rules:** mark diagnostic code clearly (`// DEBUG-INVESTIGATION` or `# DIAG`), remove it after root cause is identified, and it must not change program behavior — only observe.

## When to Use

Use for any technical issue: test failures, bugs in production, unexpected behavior, performance problems, build failures, integration issues, flaky tests, race conditions, Configuration drift, third-party breakage.

**Use this ESPECIALLY when:** under time pressure, "just one quick fix" seems obvious, you've already tried multiple fixes, a previous fix didn't work, or you don't fully understand the issue.

## Severity Triage (Do This First)

```
+----------+---------------------+------------------------------+------------------+
| Severity | Characteristics     | Investigation                | Time Budget      |
+----------+---------------------+------------------------------+------------------+
| P0       | Production down,    | Mitigate first (P0 Protocol),| Mitigate: <15min |
| Critical | data loss, revenue  | root cause after stable      | Root cause: async|
|          | impact, security    |                               |                  |
+----------+---------------------+------------------------------+------------------+
| P1       | Feature broken,     | Full 4-phase process,        | 30-60min         |
| High     | blocking users,     | no shortcuts                 |                  |
|          | test suite failing  |                               |                  |
+----------+---------------------+------------------------------+------------------+
| P2       | Minor bug, cosmetic | Phase 1 required; Phase 2    | 15-30min         |
| Medium   | edge case, non-     | skippable if cause is        |                  |
|          | blocking            | obvious; Phase 3 collapses   |                  |
|          |                     | to one hypothesis line       |                  |
+----------+---------------------+------------------------------+------------------+
```

Severity sets the time budget and how much of Phases 2-3 compress. It does not change what Critical gate C1 requires — C1's evidence bar moves *with* severity instead (see Mandatory Gates).

### P0 Protocol: Mitigate First, Investigate Second

1. **Confirm authorization to act.** Production mitigation is an operational decision — if it isn't already clear you're authorized to roll back, disable, or fail over, say so and ask before acting.
2. **Preserve evidence** before or during mitigation when it doesn't cost meaningful time: snapshot logs, error state, metrics. Rollback and failover can destroy the evidence Phase 1 needs.
3. **Mitigate** (fastest safe option): rollback to last known good deploy, disable via feature flag, targeted hotfix (retry, circuit breaker), or redirect traffic/failover. State the mitigation's own rollback risk (e.g., does rolling back reintroduce a bug that was fixed since?).
4. **Verify mitigation works** — confirm service is restored.
5. **THEN launch full root cause investigation** (Phases 1-4). The mitigation is NOT the fix — schedule root cause analysis within 24 hours; the permanent fix still requires the full process.

**Why this isn't "skipping the process":** mitigation and root-cause fixing are separate concerns. Stopping revenue loss is an operational decision; the debugging process governs the permanent fix. Full authorization/evidence/rollback-risk detail: `references/safety-and-authorization.md`.

### Bug Type Quick Reference

| Bug Type | Primary Investigation | Key Tools/Techniques |
|----------|----------------------|---------------------|
| Logic error / wrong output | Trace data flow backward | Debugger, print statements, `references/root-cause-tracing.md` |
| Race condition / flaky test | Identify shared mutable state | `-race` flag (Go), thread sanitizer, `references/condition-based-waiting.md` |
| Memory leak / perf regression | Profile before hypothesizing | pprof (Go), Chrome DevTools, `time`/`perf` |
| Environment / "works on my machine" | Diff environments systematically; run environment health check (Phase 1 step 4) | `df -h`, `free -h`, `lsof`, `dmesg`, `env` (not pre-approved, ask first, redact secrets), Docker, dependency versions |
| Third-party dependency change | Check changelogs and version diffs | `git log`, `go mod graph`, `npm ls` |
| Build / compilation error | Read error message literally | Usually Phase 1 step 1 is sufficient |
| Configuration error | Validate config propagation layer by layer | Phase 1 step 4 (multi-component evidence) |

## Scope & Mode (Do This Second)

Decide which mode applies before investigating — it determines how far through the Four Phases you go and what the Fix Plan section says. Full decision detail, edge cases, and how N/A criteria score in the Scorecard: `references/scope-and-severity.md`.

| Mode | When | How far | Fix Plan section says |
|------|------|---------|------------------------|
| **Diagnose-only** | Request is scoped to "why"/"investigate"/root cause, or you lack authorization to change the target system | Stop after Phase 3 / Output Contract §5 (Root Cause) | "Not implemented — root cause identified, awaiting authorization to fix." A valid PASS, not a skipped step. |
| **Diagnose-and-fix** (default) | Request expects a fix | Full Phases 1-4, scaled by severity above | The actual fix |
| **P0 incident** | Production down, data loss, security | P0 Protocol first, then full Phases 1-4 for the permanent fix | Mitigation now; permanent fix tracked separately |

## Mandatory Gates

### 1. Root Cause Gate
Do not propose a permanent fix until you can state what failed, where, why, and what evidence proves that cause.

### 2. Evidence Gate
If the issue spans multiple components or boundaries, gather evidence at each boundary before selecting a fix. Required: reproduction evidence, recent-change evidence, boundary evidence, data-flow/state evidence.

### 3. Hypothesis Discipline Gate
One hypothesis at a time. One minimal test per hypothesis. No bundled changes.

### 4. Fix Attempt Gate
If 3 fix attempts have failed (real code changes that didn't resolve it — not rejected hypotheses, which cost nothing and are a normal part of complex debugging), stop and question the architecture. Do not push to Fix #4 without escalation.

### 5. Reporting Integrity Gate
Never claim a command, profile, race run, trace, or verification was executed unless it actually ran. If not run, say `Not run in this environment`, why, and the exact command to run next.

## The Four Phases

Phase 1 is always required. How much of Phases 2-4 apply is set by Scope & Mode and Severity above — within that scope, complete phases in order.

### Phase 1: Root Cause Investigation

**BEFORE attempting ANY fix:**

1. **Read Error Messages Carefully** — don't skip past errors/warnings, they often contain the exact solution. Read stack traces completely; note line numbers, file paths, error codes.

2. **Reproduce Consistently** — can you trigger it reliably, what are the exact steps, does it happen every time? If not reproducible, gather more data, don't guess.

3. **Check Recent Changes** — what changed that could cause this? Git diff, recent commits, new dependencies, config changes, environmental differences.

4. **Check Environment Health**

   **WHEN symptoms include:** intermittent failures, timeouts, "works on my machine", silent process death, or no obvious code cause.

   Rule out infrastructure/OS-level issues before diving into code. Minimum checklist:
   - disk space: `df -h`
   - memory / OOM: `free -h && dmesg | grep -i oom` (Linux) or `top -l 1 | head -20` (macOS)
   - port conflicts: `lsof -i :<port>`
   - network / DNS: `nslookup <hostname>` and `curl -v <endpoint>`
   - file descriptors: `ulimit -a`
   - recent system events: `dmesg | tail -50` or `log show --last 10m`
   - environment variables (only if suspected): `env` is not pre-approved (see `references/safety-and-authorization.md`) — ask before running it, prefer a targeted lookup (`env | grep '^VAR_NAME='`) over a full dump, and redact any value whose key contains `SECRET`/`KEY`/`TOKEN`/`PASSWORD` before it goes into the report (this limits the report, not the raw command output, which already ran by the time you're writing)

   If environment is unhealthy, fix that first. A broken machine is not a code bug.

5. **Gather Evidence in Multi-Component Systems**

   **WHEN system has multiple components** (CI → build → signing, API → service → database):

   Before proposing fixes, instrument each boundary. For EACH component boundary: log what enters, log what exits, verify config/environment propagation, confirm state at each layer. Run once, identify the exact failing boundary, then narrow to that layer.

6. **Trace Data Flow**

   **WHEN error is deep in call stack:** see `references/root-cause-tracing.md` for the full backward-tracing technique. Quick version: where does the bad value originate, what called this with a bad value, keep tracing up until you find the source. Fix at source, not at symptom.

7. **Use Parallel Investigation for Complex Systems**

   **WHEN system has 3+ components or investigation is slow:** launch independent tracks (logs/errors, recent changes/deploys, working-vs-broken diff, external dependency status) via the Agent tool, then synthesize before choosing a fix.

### Phase 2: Pattern Analysis

Skippable for P2 when the cause is already obvious (see Scope & Mode).

1. **Find Working Examples** — locate similar working code in the same codebase.
2. **Compare Against References** — if implementing a pattern, read the reference implementation completely, don't skim.
3. **Identify Differences** — list every difference between working and broken, however small; don't assume "that can't matter."
4. **Understand Dependencies** — what other components, settings, config, or assumptions does this need?

### Phase 3: Hypothesis and Testing

For P2, this collapses to step 1 alone (state the hypothesis, then go to Phase 4) unless it's rejected — see Scope & Mode.

1. **Form Single Hypothesis** — state clearly: "I think X is the root cause because Y." Write it down. Be specific.
2. **Test Minimally** — the smallest change that tests the hypothesis, one variable at a time, don't fix multiple things at once.
3. **Verify Before Continuing** — worked? go to Phase 4. Didn't work? form a new hypothesis, don't add more fixes on top.
4. **When You Don't Know** — say "I don't understand X," don't pretend to know, ask for help or research more.
5. **Maintain a Hypothesis Log** for anything non-trivial, to avoid circular investigation:

   ```
   | # | Hypothesis              | Evidence For    | Evidence Against       | Result   | Time |
   |---|-------------------------|-----------------|------------------------|----------|------|
   | 1 | Empty config path       | Error at line 42| Config file exists     | Rejected | 8min |
   | 2 | Race in goroutine pool  | Flaky under load| Passes with -race      | Rejected | 12min|
   | 3 | Stale cache after deploy | Cache TTL=1h    | Deploy was 2h ago      | CONFIRMED| 5min |
   ```

   **Time-box each hypothesis:** max 15-20 minutes. If you can't confirm or reject in time, note what's blocking and move to the next one.

   **Rejected hypotheses are cheap and normal** — even 3+ in a row usually means update your mental model with what you've now ruled out and keep investigating, not that the architecture is wrong. The architecture-questioning signal lives in Phase 4 (repeated **fix attempt** failures, which cost real changes — not hypothesis rejections, which cost nothing). See the Fix Attempt Gate.

### Phase 4: Implementation

1. **Create Failing Test Case** — simplest reproduction, automated if possible, one-off script if no framework. Must exist before fixing. Use the `tdd-workflow` skill for proper failing tests.

2. **Implement Single Fix** — address the root cause identified, one change at a time, no "while I'm here" improvements or bundled refactoring. **Exception:** when the confirmed root cause is "invalid data enters through multiple layers," a defense-in-depth fix across those specific layers is still ONE fix for ONE root cause (see `references/defense-in-depth.md`) — it's bundling *unrelated* changes that's forbidden, not addressing every layer the actual root cause touches.

3. **Verify Fix** — test passes now? No other tests broken? Issue actually resolved?

4. **If Fix Doesn't Work** — STOP. Count fix attempts. `< 3`: return to Phase 1 with new information. `>= 3`: stop and question the architecture (below) — don't attempt Fix #4 without that discussion.

5. **If 3+ Fix Attempts Failed: Question the Architecture**

   Pattern indicating an architectural problem: each fix reveals new shared state/coupling elsewhere, fixes require "massive refactoring," each fix creates new symptoms elsewhere.

   Stop and ask: is this pattern fundamentally sound, are we sticking with it through inertia, should we refactor vs. keep patching symptoms? **Discuss with your human partner before attempting more fixes.** This is not a failed hypothesis — it's a wrong architecture.

## Quality Scorecard

Every debugging report MUST include a scorecard verdict, scaled to the declared Scope & Mode. Use `references/debugging-report-scorecard.md`; N/A-scoring rules for diagnose-only and collapsed-P2 reports live in `references/scope-and-severity.md` — an inapplicable criterion counts as PASS-by-inapplicability with a one-line stated reason, never a silent FAIL.

### Critical
Any FAIL here means the whole report FAILS.

| ID | Requirement |
|----|-------------|
| C1 | No permanent fix proposed before the evidence the declared mode/severity requires exists (P1: Phases 1-3; P2: Phase 1 + explicit hypothesis; diagnose-only: N/A, no fix was requested) |
| C2 | Root cause is stated as a cause, not a symptom |
| C3 | Root cause is backed by concrete evidence from reproduction, trace, profile, or boundary instrumentation — for a multi-component issue, this means boundary evidence at the specific failing hop |
| C4 | Hypothesis log exists and matches the investigation path taken, or is marked N/A with a one-line reason (e.g., P2 collapsed hypothesis) |
| C5 | No command, profile, trace, or verification is claimed to have run unless it actually did (Reporting Integrity Gate) — anything not run is marked `Not run in this environment` with why and the next command |

### Standard
Pass at least 4 of 6.

| ID | Requirement |
|----|-------------|
| S1 | Reproduction includes exact commands or steps |
| S2 | Evidence covers *every* relevant component boundary, not just the failing one C3 already requires |
| S3 | Fix scope is minimal and justified (defense-in-depth across layers for one root cause counts as minimal; unrelated bundled changes do not) |
| S4 | Verification is thorough — regression checks and adjacent risk considered, beyond the bare honesty C5 already requires |
| S5 | Residual risks and follow-ups are honest and specific |
| S6 | If 3+ fix attempts failed, the report explicitly questions architecture |

### Hygiene
Pass at least 3 of 4.

| ID | Requirement |
|----|-------------|
| H1 | Report follows the output contract order |
| H2 | Severity, mode, and bug type are classified |
| H3 | Owners / ETA are included when follow-ups exist |
| H4 | Wording is concise and avoids filler or hand-waving |

### Scorecard Output Rules

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

Interpretation: any Critical fail => overall FAIL; Standard below 4/6 => overall FAIL; Hygiene below 3/4 => overall FAIL.

## Red Flags — STOP and Return to Phase 1

Catch yourself thinking any of these, or hear your human partner say any of these — both mean the same thing.

**Your own reasoning:**
- "Quick fix for now, investigate later" / "Just try changing X and see"
- "Add multiple changes, run tests" / "Skip the test, I'll manually verify"
- "It's probably X, let me fix that" / "I don't fully understand but this might work"
- "Pattern says X but I'll adapt it differently"
- "Here are the main problems: [lists fixes without investigation]"
- Proposing solutions before tracing data flow
- **"One more fix attempt" (when already tried 2+)** / **each fix reveals a new problem elsewhere**

**Your human partner's signals:**
- "Is that not happening?" — you assumed without verifying
- "Will it show us...?" — you should have added evidence gathering
- "Stop guessing" — you're proposing fixes without understanding
- "Ultrathink this" — question fundamentals, not just symptoms
- "We're stuck?" (frustrated) — your approach isn't working

**If 3+ fix attempts failed:** question the architecture (Phase 4, step 5) — a stronger signal than a rejected hypothesis, and one that should not be brushed past.

## Anti-Examples - BAD / GOOD Debugging Reports

These are behavioral constraints, not cosmetic writing advice. Full BAD/GOOD library: `references/bad-good-debugging-reports.md`.

Required anti-example coverage: symptom presented as root cause; guessed fix without reproduction; sleep/retry used to hide a race; performance fix without profiling; missing boundary evidence in multi-component systems; bundled fixes destroying attribution; repeated failed fixes without questioning architecture.

## Load References Selectively

- Bug appears deep in the stack, bad-value origin unclear, need caller-to-source tracing → `references/root-cause-tracing.md`.
- Root cause is invalid data, unsafe state transition, or a missing guard at one of several layers → `references/defense-in-depth.md` (multi-layer guard patterns; also resolves how this relates to the single-fix rule in Phase 4).
- Flaky tests, retries, sleeps, polling loops, async timing → `references/condition-based-waiting.md`.
- Bug type unclear or you need a per-class strategy → `references/bug-type-strategies.md` for the 6-category matrix (logic errors, race conditions, memory leaks/performance regression, environment/configuration bugs, third-party dependency changes, build/compilation errors) with worked examples.
- Deciding diagnose-only vs. diagnose-and-fix vs. P0, or how N/A criteria score in the Scorecard → `references/scope-and-severity.md`.
- Running P0 mitigation, or any command that touches production, secrets, or destructive state changes → `references/safety-and-authorization.md`.
- Writing the final report or checking completeness against the required sections → `references/output-contract-template.md`.
- Grading a debugging report's quality → `references/debugging-report-scorecard.md`.
- Report is weak or hand-wavy and needs concrete improvement patterns → `references/bad-good-debugging-reports.md`.
- Test suite pollutes filesystem/state and you need to isolate the polluting test → run `scripts/find-polluter.sh`, which sequentially tests each matching file in sorted order (a linear scan) and reports the first one whose run leaves the artifact behind.

**Related skills:**
- **`tdd-workflow`** — for creating the failing test case (Phase 4, step 1)
- **`unit-test`** — add/extend regression tests after the root-cause fix
- **`go-code-reviewer`** — validate risk and regression impact of the fix

## Output Contract (Required)

Return debugging outputs using `references/output-contract-template.md`.

Minimum required order: 1. Triage (incl. mode) 2. Reproduction 3. Evidence collected 4. Hypothesis log (or N/A + reason) 5. Root cause 6. Fix plan/change (or "not implemented, awaiting authorization" for diagnose-only) 7. Verification 8. Residual risk/follow-ups 9. Scorecard.

Minimum quality requirements:
- Do not *implement* a fix (write or apply a code change) until sections 1-5 are complete, and never in diagnose-only mode without new authorization. Describing/sketching what a fix would look like in section 6, clearly labeled as unimplemented, is fine in diagnose-only mode (see `references/scope-and-severity.md`) — it's the act of changing code that's gated, not the act of describing one.
- Hypothesis log must contain at least one row for non-trivial debugging, or be marked N/A with a one-line reason.
- Evidence must cover every relevant component boundary.
- Root cause must explain source, not just symptom.
- Verification must include explicit commands or exact checks.

## Regression Commands (Skill Maintenance)

Run all regression checks when editing this skill:

```bash
./scripts/run_regression.sh
```

That wrapper must execute:
- `python3 -m unittest discover -s scripts/tests -p 'test_*.py' -v`
- `./scripts/find-polluter.sh --help`
