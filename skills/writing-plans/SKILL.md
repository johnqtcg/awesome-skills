---
name: writing-plans
description: >
  Create implementation plans for multi-step tasks. Use when you have a spec,
  requirements, or feature request that needs decomposition into concrete steps
  before implementation. Covers feature, bugfix, refactor, migration, API change,
  and docs-only plans. NOT for single-file edits, trivial fixes, or tasks
  completable in under 5 minutes.
---

# Writing Plans

Write implementation plans that a developer with zero codebase context can follow. Plans must be evidence-backed (paths verified), mode-appropriate (not over-engineered), and executable (every step has a verification command).

**Announce at start:** "I'm using the writing-plans skill to create the implementation plan."

## Gate 1: Applicability Gate

Before writing any plan, classify the task:

| Complexity Signal | Decision |
|---|---|
| Single file, <30 lines changed, no cross-module deps | **SKIP** — execute directly, no plan needed |
| Docs/config/README only, no logic changes | **SKIP** or Lite checklist |
| Single module feature, clear scope, <200 lines | **Lite** mode |
| Multi-file feature, tests + impl, 200-800 lines | **Standard** mode |
| Cross-module, migration, architecture change, >800 lines | **Deep** mode |

If SKIP: tell the user "This task doesn't need a formal plan. Proceeding directly."
If unclear: default to Lite, upgrade during execution if complexity emerges.

Load `references/applicability-gate.md` for edge cases and language-specific signals.

## Execution Modes

### Lite (single-module, low risk)
- 5-15 line checklist (not a full plan document)
- No code blocks — only steps and verification commands
- No reviewer loop
- Execute immediately in current session

### Standard (typical feature or bugfix)
- Full plan document saved to file
- Interface-level code only (signatures, key assertions — not full implementations)
- **Mandatory Reviewer Loop (1 round)** — always runs after self-check, not conditional on self-check result
- Supports subagent-driven or inline execution

### Deep (cross-module, migration, architecture)
- Full plan document + dependency graph
- Phased validation checkpoints + rollback strategy per phase
- **Mandatory Reviewer Loop (up to 3 rounds)** — always runs after self-check, not conditional on self-check result
- Subagent-driven execution recommended

## Gate 2: Repo Discovery Gate

Before writing ANY file path into the plan:

1. **Read project structure**: top-level dirs, package manager, test framework, CI config
2. **Label every path** (all four levels defined in `references/repo-discovery-protocol.md`):
   - `[Existing]` — verified via Glob/Read
   - `[New]` — will be created, parent dir verified
   - `[Inferred]` — based on project convention, not directly verified
   - `[Speculative]` — degraded mode only, no verification possible
3. **NEVER write line numbers** for files you haven't read
4. **NEVER write complete implementation code** for functions whose interface you haven't verified

Load `references/repo-discovery-protocol.md` for the full discovery checklist.

If repo is not accessible: see Degraded Mode below.

## Gate 3: Scope & Risk Gate

| Change Size | Risk | Action |
|---|---|---|
| ≤200 lines | Low | Standard flow |
| 201-800 lines | Medium | Include rollback notes per phase |
| >800 lines | High | Dependency graph required, phased rollout, validation checkpoints |

High-risk areas requiring explicit rollback strategy:
- Auth/authz, payment, database schema, public API, concurrency, infrastructure

## Plan Content Rules

### Code Level by Mode

| Mode | What to Include | What NOT to Include |
|---|---|---|
| Lite | Step descriptions + verification commands | Any code blocks |
| Standard | `[interface]` signatures, `[test-assertion]` key assertions, `[command]` CLI commands | Complete function implementations |
| Deep | Same as Standard + data flow sketches, migration SQL, sequence outlines | Complete implementations, hardcoded config values |

### Code Block Labels (mandatory for Standard/Deep)
- `[interface]` — function signature, struct definition, type contract
- `[test-assertion]` — expected behavior check, not implementation
- `[command]` — exact CLI command to run
- `[speculative]` — best guess, needs verification during execution

## Plan Document Structure (Output Contract)

### Header (all modes except Lite)
```markdown
# [Feature Name] Implementation Plan

**Goal:** [One sentence]
**Mode:** Lite | Standard | Deep
**Architecture:** [2-3 sentences]
**Tech Stack:** [Key technologies]
**Repo Discovery:** [Verified project conventions, test framework, CI setup]

---
```

### Dependency Graph (Deep mode only)
```
Task 2 [depends: 1] [blocks: 4, 5]
Task 3 [depends: 1] [blocks: 5]
Tasks 2, 3 are parallelizable.
```

### Tasks (mandatory)
Each task has:
- **Files:** with `[Existing]` / `[New]` / `[Inferred]` / `[Speculative]` labels
- **Steps:** using `- [ ]` checkbox syntax
- **Verification:** at least 1 runnable command per task

### Risk & Rollback (Standard + Deep)
- Per-phase rollback strategy for Medium/High risk changes
- Validation checkpoints between phases

### Execution Handoff (mandatory)
```
Plan saved to `<path>`. Execution options:

1. **Subagent-Driven (this session)** — fresh subagent per task, review between tasks
2. **Parallel Session** — open new session, batch execution with checkpoints

Which approach?
```

If companion skills (`subagent-driven-development`, `executing-plans`) are unavailable:
provide inline execution guidance without external skill dependency.

## Plan Save Location

1. Check CLAUDE.md for `plan_dir` setting → use it
2. Check if `docs/plans/` exists in project → use it
3. Fallback: save to project root as `plan-YYYY-MM-DD-<name>.md`

Filename: `YYYY-MM-DD-<feature-name>.md`

## Anti-Examples

Load `references/anti-examples.md` for the full list. Key suppressions:

1. **Path fabrication**: writing `src/auth/handler.go:45-67` without reading the file
2. **Implementation code in plans**: 50-line function body that hasn't been compiled
3. **Over-decomposition**: 20-line bugfix split into 8 tasks with 40 steps
4. **Rigid TDD for everything**: docs-only changes forced through test-first workflow
5. **Ignoring parallelism**: 5 independent tasks forced into sequential order
6. **No verification commands**: steps ending with "check that it works"
7. **Framework assumption**: "use Jest" when project actually uses Vitest
8. **Missing rollback**: database migration without undo steps
9. **Hardcoded paths**: fixed save location ignoring project conventions

## Plan Update Protocol

During execution, when reality diverges from plan:

1. Record: `[Deviation] Task N Step M: planned X → actual Y (reason: Z)`
2. Assess: Trivial (continue) / Significant (adjust downstream) / Breaking (pause, replan)
3. Update plan file if impact is non-trivial
4. If >30% of tasks deviate significantly: pause execution, reassess plan

Load `references/plan-update-protocol.md` for the full protocol.

## Degraded Mode

If repo is not accessible or discovery cannot run:

1. Announce: "Degraded mode — repo structure not verified"
2. Mark ALL file paths as `[Speculative]`
3. Do not write line-number references
4. Include "Discovery commands to run first" section in the plan
5. Reduce code blocks to `[speculative]` interface sketches only
6. Skip Gate 3 (cannot classify risk without evidence)

## Post-Writing Workflow

After finishing the plan document, run these two gates in sequence. **Both are required for Standard and Deep mode.** They are complementary, not substitutable: the Self-Check catches format violations; the Reviewer Loop catches logic problems that only emerge when you read the plan as a skeptic who never saw the codebase.

```
Step 1 → Self-Check (Format Gate)       — always run, fixes structural errors
Step 2 → Reviewer Loop (Substance Gate) — mandatory for Standard/Deep, skip for Lite
Step 3 → Execution Handoff
```

### Step 1 — Plan Quality Scorecard (Format Gate)

Self-evaluate for structural correctness. Fix any Critical failures before moving to Step 2.

**Critical (ALL must pass)**

| # | Check |
|---|---|
| C1 | Applicability Gate ran and mode declared |
| C2 | Every file path labeled `[Existing]`/`[New]`/`[Inferred]`/`[Speculative]` |
| C3 | No complete implementation code in Standard/Deep mode |
| C4 | Every task has ≥1 runnable verification command |

**Standard (≥4/6 must pass)**

| # | Check |
|---|---|
| S1 | Repo discovery ran (or Degraded mode declared) |
| S2 | Risk classification assigned; rollback included for Medium/High |
| S3 | Tasks are single-responsibility (one concern per task) |
| S4 | Independent tasks identified and not forced sequential |
| S5 | Test/verification steps precede commit steps |
| S6 | Plan follows Output Contract structure |

**Hygiene (≥3/4 must pass)**

| # | Check |
|---|---|
| H1 | Plan saved to correct location (project convention or fallback) |
| H2 | Execution handoff offered |
| H3 | No hardcoded environment assumptions without fallback |
| H4 | Mode-appropriate depth (Lite not over-engineered, Deep not too thin) |

**Format Gate PASS**: All Critical pass AND ≥4/6 Standard AND ≥3/4 Hygiene

### Step 2 — Reviewer Loop (Substance Gate)

**Lite mode**: Skip — go directly to Execution Handoff.

**Standard and Deep mode**: The Reviewer Loop is **MANDATORY regardless of Step 1 result**. A plan that passes the Scorecard is well-formatted; it is not necessarily logically sound. The Reviewer catches what the Scorecard cannot: task dependencies that contradict the stated order, parallel tasks that write to the same file, verification commands that run but don't test the claimed behavior, and scope that silently exceeds the stated goal.

Load `references/reviewer-checklist.md` and apply every item. Two execution paths:

- **Subagent available**: Dispatch an independent reviewer subagent with the plan text and checklist. The subagent reviews without author context and returns a structured report.
- **Single session (no subagent)**: Deliberately adopt a reviewer mindset — step back from authorship and read the plan as a skeptic seeing it for the first time. Work through every checklist item, with extra attention to the Substance section (SB1–SB6 in the checklist), which requires adversarial reasoning the self-check cannot perform.

**Rounds:**
- Standard: 1 round. Fix any blocking issues, then proceed.
- Deep: up to 3 rounds. Iterate until no blocking issues remain.

If blocking issues are found: fix them, re-run Step 1 on the changed sections, then proceed to Step 3.

### Step 3 — Execution Handoff

Proceed only after both gates pass. Offer the user execution options per the Execution Handoff template in the Output Contract section above.

## Reference Loading Guide

| Scenario | Load |
|---|---|
| Unsure whether to write a plan | `references/applicability-gate.md` |
| Starting a plan (always) | `references/repo-discovery-protocol.md` |
| Choosing plan shape | `references/plan-templates/<scenario>.md` |
| Self-checking quality | scorecard in Step 1 above |
| Reviewer evaluating plan | `references/reviewer-checklist.md` |
| Execution diverges from plan | `references/plan-update-protocol.md` |
| Need examples of good/bad plans | `references/golden-scenarios.md` |
| Checking common mistakes | `references/anti-examples.md` |

## Context Note

This skill does not depend on specific companion skills or worktree setup.
It recommends `subagent-driven-development` and `executing-plans` when available,
but provides self-contained guidance when they are not.
Worktree isolation is recommended but not required.
