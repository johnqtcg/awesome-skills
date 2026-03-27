# Plan Document Review Checklist

Use this checklist when reviewing a plan document. Each item is PASS / FAIL / N/A.

The checklist has three sections:
- **Blocking Items** — format violations; any FAIL → plan not approved
- **Non-Blocking Items** — structural observations; flag but don't reject
- **Substance Items** — logic and soundness checks; SB1/SB3/SB4 are blocking for Standard/Deep

---

## Blocking Items (any FAIL → plan not approved)

| # | Check | How to Verify |
|---|---|---|
| B1 | Applicability Gate ran and mode declared | Plan header states "Mode: Lite/Standard/Deep" |
| B2 | Every file path has `[Existing]`/`[New]`/`[Inferred]`/`[Speculative]` label | Search for unlabeled file paths |
| B3 | No TODO/TBD/placeholder unfilled | Search for "TODO", "TBD", "FIXME", "..." |
| B4 | Every task has ≥1 runnable verification command | Look for `Run:` or code block with `[command]` per task |
| B5 | No complete implementation code in Standard/Deep plans | Code blocks should be labeled `[interface]` or `[test-assertion]`, not full functions |
| B6 | Requirements clarity gate ran — plan goal is specific and scope is bounded, or assumptions are explicitly marked `[Assumption]` | Read the Goal sentence. Is it concrete and actionable? Check for `[Assumption]` markers if scope was ambiguous. |

---

## Non-Blocking Items (flag but don't reject)

| # | Check | How to Verify |
|---|---|---|
| N1 | Independent tasks identified and marked parallelizable | Look for `[parallel]` or `[depends:]` annotations |
| N2 | Risk classification assigned | Plan has Scope & Risk section or risk labels |
| N3 | Medium/High risk tasks have rollback steps | Rollback section exists for risky phases |
| N4 | Code blocks labeled with type | `[interface]`/`[test-assertion]`/`[command]`/`[speculative]` |
| N5 | Plan saved to correct project-conventional location | Path matches project convention or documented fallback |
| N6 | Execution handoff section present | Plan ends with execution options |
| N7 | Discovery summary included (or Degraded mode declared) | Header has "Repo Discovery" or "Degraded mode" note |

---

## Substance Items (logic and soundness — requires adversarial reasoning)

These checks require reading the plan as a skeptic who has NOT seen the codebase. The Scorecard self-check cannot catch these — they demand an outside perspective.

**SB1, SB3, SB4 are blocking for Standard/Deep mode.**

| # | Check | How to Verify | Blocking? |
|---|---|---|---|
| SB1 | **Task ordering is causally valid** — each task only assumes outputs that prior tasks actually produce | For every task with `[depends: N]`, verify Task N produces what this task requires as input. Look for tasks that read a file before any task has created it, or call a function before any task has defined it. | **Yes** |
| SB2 | **Parallel tasks have no shared write targets** — tasks marked parallelizable don't both modify the same file | List all files modified in each parallel task group. Flag any file appearing in two parallel tasks. | No (flag as risk) |
| SB3 | **Verification commands test the stated claim** — each `[command]` block actually exercises the behavior described in the step, not just that the command exits 0 | Read each verification command in isolation. Would it pass even if the step's implementation was wrong? If `go build ./...` is the only verification for a behavioral change, flag it — build success ≠ correct behavior. | **Yes** |
| SB4 | **Scope is bounded by the stated Goal** — no step implements something not required by the Goal | Re-read the Goal sentence, then scan every task and step. Flag any step that adds functionality, changes unrelated files, or refactors code not mentioned in the Goal. | **Yes** |
| SB5 | **`[Speculative]` paths are mutually consistent** — inferred paths follow the same naming/structure convention | For plans with multiple `[Speculative]` paths, check they use consistent naming patterns (e.g., all controllers in `src/controllers/`, not some in `src/handlers/`). Inconsistent speculation signals that discovery was incomplete. | No (flag) |
| SB6 | **High-risk tasks have a failure detection step** — for tasks flagged Medium/High risk, there is a step or command that would surface a failure, not just undo it | A rollback command is not enough. Look for a verification step (e.g., `alembic current`, health check, smoke test) that runs BEFORE the rollback opportunity is lost. | No (flag) |

---

## Review Output Format

```
## Plan Review

**Status:** Approved | Issues Found

**Blocking Issues (if any):**
- [B# or SB#]: [specific issue] — [why it matters for execution]

**Non-Blocking Notes:**
- [N# or SB#]: [observation] — [suggestion]

**Scorecard:** B: _/6 | N: _/7 | SB: _/6
**Overall:** PASS | FAIL
```
