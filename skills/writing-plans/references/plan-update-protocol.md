# Plan Update Protocol

Use this protocol when execution diverges from the written plan.

## Deviation Classification

| Level | Definition | Action |
|---|---|---|
| **Trivial** | Minor path or naming difference, no downstream impact | Log and continue |
| **Significant** | Approach changed, affects 1-2 downstream tasks | Log, adjust affected tasks, update plan file |
| **Breaking** | Fundamental assumption wrong, affects >30% of remaining tasks | Pause execution, reassess, consider replanning |

## Recording Format

When a deviation occurs, record it in the plan file:

```markdown
> [Deviation] Task N Step M: planned X → actual Y
> Reason: Z
> Impact: Trivial/Significant/Breaking
> Downstream adjustment: (describe changes to later tasks, or "none")
```

## Escalation Thresholds

| Condition | Action |
|---|---|
| 1 Significant deviation | Log, adjust, continue |
| 3 Significant deviations | Pause and review remaining plan for similar assumptions |
| 1 Breaking deviation | Pause execution immediately |
| >30% tasks with Significant+ deviations | Full replan recommended |

## Who Updates the Plan

- **Implementer** (subagent): records the deviation in their report
- **Coordinator** (controller): decides whether to update plan file, adjusts downstream tasks
- **Neither should silently skip planned steps** — either do it, update it, or mark it N/A with reason

## Mode Upgrade During Execution

If execution reveals more complexity than planned:
- Lite → Standard: task count growing beyond 3, cross-file changes emerging
- Standard → Deep: dependency graph needed, rollback strategy needed, phased deployment needed

Announce: "Upgrading plan from [old mode] to [new mode] — [specific reason]"