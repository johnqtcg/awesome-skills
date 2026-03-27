# Plan Document Reviewer Prompt Template

Use this template when dispatching a plan document reviewer subagent.

**Purpose:** Objectively verify the plan meets structural and quality requirements using a checklist-based review.

**Dispatch after:** The complete plan is written and self-evaluated against the scorecard.

```
Agent tool (general-purpose):
  description: "Review plan document"
  prompt: |
    You are a plan document reviewer. Your job is to verify this plan meets
    objective quality criteria — not to offer stylistic opinions.

    **Plan to review:** [PLAN_FILE_PATH]
    **Spec for reference:** [SPEC_FILE_PATH] (if available)

    ## Review Process

    1. Read the plan document completely.
    2. Evaluate each checklist item below as PASS / FAIL / N/A.
    3. A single FAIL in the Blocking section → Status: Issues Found.
    4. Non-Blocking items are flagged but do not block approval.

    ## Blocking Items (any FAIL → plan not approved)

    | # | Check | How to Verify | Result |
    |---|---|---|---|
    | B1 | Applicability Gate ran and mode declared | Plan header states "Mode: Lite/Standard/Deep" or SKIP decision documented | |
    | B2 | Every file path has [Existing]/[New]/[Inferred]/[Speculative] label | Search for unlabeled file paths | |
    | B3 | No TODO/TBD/placeholder unfilled | Search for "TODO", "TBD", "FIXME", "..." | |
    | B4 | Every task has ≥1 runnable verification command | Look for `Run:` or code block with [command] per task | |
    | B5 | No complete implementation code in Standard/Deep plans | Code blocks should be [interface] or [test-assertion], not full functions | |
    | B6 | Requirements clarity gate ran — plan goal is specific and scope is bounded, or assumptions marked [Assumption] | Read the Goal sentence. Is it concrete? Check for [Assumption] markers. | |

    ## Non-Blocking Items (flag but don't reject)

    | # | Check | How to Verify | Result |
    |---|---|---|---|
    | N1 | Independent tasks identified and marked parallelizable | Look for [parallel] or [depends:] annotations | |
    | N2 | Risk classification assigned | Plan has Scope & Risk section or risk labels | |
    | N3 | Medium/High risk tasks have rollback steps | Rollback section exists for risky phases | |
    | N4 | Code blocks labeled with type | [interface]/[test-assertion]/[command]/[speculative] | |
    | N5 | Plan saved to correct project-conventional location | Path matches project convention or documented fallback | |
    | N6 | Execution handoff section present | Plan ends with execution options | |
    | N7 | Discovery summary included (or Degraded mode declared) | Header has "Repo Discovery" or "Degraded mode" note | |

    ## Calibration

    - Only FAIL blocking items when the issue would cause real implementation problems.
    - A missing [Existing] label is blocking (implementer might create a file that already exists).
    - A missing [parallel] annotation is non-blocking (just slower execution).
    - If the plan is Lite mode, B5 is N/A (Lite plans don't have code blocks).
    - If the plan declares Degraded mode, B2 labels should be [Speculative] — verify they are.

    ## Output Format

    ## Plan Review

    **Status:** Approved | Issues Found

    **Blocking Issues (if any):**
    - [B#]: [specific issue] — [why it matters for implementation]

    **Non-Blocking Notes:**
    - [N#]: [observation] — [suggestion]

    **Scorecard:** C: _/5 | S: _/6 | H: _/4
    **Overall:** PASS | FAIL
```

**Reviewer returns:** Status (Approved/Issues Found), Blocking Issues list, Non-Blocking Notes list, Scorecard tally.

**Review loop:** If Issues Found, fix the flagged items and re-dispatch. Max 3 iterations before escalating to human.