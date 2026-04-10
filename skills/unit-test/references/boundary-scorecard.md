# Boundary Checklist & Scorecard — Full Reference

## Fixed Boundary Checklist (Standard + Strict — Per Test Target)

Mark each item as `Covered` or `N/A (reason)`:

1. `nil` input (only if parameter is pointer/interface/map/slice/channel/function)
2. empty value/collection
3. single element (`len == 1`)
4. size/index boundary (`n=2`, `n=3`, last element)
5. min/max value boundary (`x-1`, `x`, `x+1`) if numeric
6. invalid format/type
7. zero-value struct/default trap
8. error from each critical dependency
9. context cancellation/deadline propagation (if method accepts/uses `context.Context`)
10. concurrent/race behavior (if stateful or goroutine-based)
11. mapping completeness (`no dropped first/middle/last item`)
12. killer case present and mapped to a concrete defect hypothesis

## Auto Scorecard — 13 Items

| # | Tier | Check |
|---|------|-------|
| 1 | [Hygiene] | File naming and location are correct. |
| 2 | [Hygiene] | Top-level test naming follows the Target Type Adaptation table. |
| 3 | [Hygiene] | `t.Run` groups map 1-to-1 to test targets. |
| 4 | [Hygiene] | Table-driven style is used for test cases. |
| 5 | [Critical] | Assertions are mutation-resistant (business fields, not existence-only). |
| 6 | [Hygiene] | Happy path is covered. |
| 7 | [Standard] | Critical dependency error paths are covered. |
| 8 | [Standard] | Boundary checklist items are explicitly marked Covered/N/A. |
| 9 | [Standard] | Collection mapping completeness is asserted (length + identities + first/middle/last). |
| 10 | [Standard] | Terminal/last-element branch behavior is asserted. |
| 11 | [Critical] | Killer case exists for every target and is linked to a defect hypothesis. |
| 12 | [Standard] | `-race` execution result is reported (or marked N/A with rationale if not runnable here). |
| 13 | [Critical] | Coverage meets gate for the package category (logic >= 80%; infra per rationale) OR marked N/A with explicit justification. |

### Final PASS Criteria

Final PASS only when:

- All 3 Critical items (5, 11, 13) are PASS (or N/A with explicit rationale **and** hypothesis coverage is complete), and
- Standard tier: >= 4/5 PASS, and
- Hygiene tier: >= 4/5 PASS, and
- total >= 11/13.

Otherwise: FAIL — list missing items and next targeted test additions.

**N/A handling**: Items marked N/A with explicit rationale count as PASS for tier and total calculations.