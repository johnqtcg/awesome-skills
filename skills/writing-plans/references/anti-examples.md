# Anti-Examples — Plans You Must NOT Produce

Each entry shows a BAD pattern and its GOOD replacement. If your plan matches a BAD pattern, fix it before proceeding.

## 1. Path Fabrication

```
BAD:  Modify: `src/auth/handler.go:45-67`  ← line numbers without reading the file
GOOD: Modify: `src/auth/handler.go` [Existing] — update validateToken function
```

Why: Line numbers change constantly. Fabricated paths cause implementers to waste time searching.

## 2. Complete Implementation Code

```
BAD:  (50 lines of full function implementation in plan)
GOOD: [interface] func ValidateToken(ctx context.Context, token string) (*Claims, error)
      [test-assertion] require.NoError(t, err); assert.Equal(t, expectedUserID, claims.UserID)
```

Why: Plan-time code hasn't been compiled or tested. It creates false confidence and usually needs rewriting.

## 3. Over-Decomposition

```
BAD:  20-line bugfix split into 8 tasks:
      Task 1: Read the file  Task 2: Understand the bug  Task 3: Write test
      Task 4: Run test  Task 5: Fix bug  Task 6: Run test  Task 7: Lint  Task 8: Commit

GOOD: 1 task, 5 steps: Write failing test → verify it fails → fix → verify pass → commit
```

Why: Overhead of task management exceeds the work itself. Use Lite mode for simple fixes.

## 4. Rigid TDD for Non-Code Changes

```
BAD:  docs-only change forced through "write failing test → implement → verify" cycle
GOOD: Lite mode checklist: Update README section X → verify links → commit
```

Why: Not all changes have testable behavior. Docs, config, and CI changes need verification, not TDD.

## 5. Forced Sequential on Independent Tasks

```
BAD:  Task 1 → Task 2 → Task 3 → Task 4 → Task 5  (all sequential)
      where Tasks 1,2,3 touch different files with no shared state

GOOD: Tasks 1,2,3 [parallel] → Task 4 [depends: 1,2] → Task 5 [depends: 3,4]
```

Why: Sequential ordering wastes execution time and obscures actual dependencies.

## 6. Vague Verification

```
BAD:  "Check that it works"  /  "Verify the implementation"
GOOD: Run: `go test ./pkg/auth/... -v -run TestValidateToken`
      Expected: PASS, 3 test cases
```

Why: Without a concrete command, the implementer can't objectively verify success.

## 7. Framework Assumption

```
BAD:  "Write tests using Jest" ← without checking what the project actually uses
GOOD: [After discovery] "Project uses Vitest (detected from package.json). Write tests using Vitest."
```

Why: Framework mismatch causes failed imports and wasted debugging time.

## 8. Missing Rollback on Risky Changes

```
BAD:  Migration plan for adding NOT NULL column with no rollback steps
GOOD: Phase 1: Add nullable column → Phase 2: Backfill → Phase 3: Add constraint NOT VALID
      Rollback: ALTER TABLE DROP COLUMN (if Phase 1), remove backfill job (if Phase 2)
```

Why: Medium/High risk changes without rollback leave production exposed if something goes wrong.

## 9. Hardcoded Save Path

```
BAD:  "Save plan to docs/superpowers/plans/..."  ← ignoring project conventions
GOOD: Check CLAUDE.md for plan_dir → check if docs/plans/ exists → fallback to project root
```

Why: Projects have different conventions. Hardcoded paths create files in unexpected locations.

## 10. Planning Against Vague Requirements

```
BAD:  User says "optimize the auth module" → plan immediately written with 8 tasks
      covering token caching, connection pooling, query optimization, and session cleanup

GOOD: "Before planning, I'd like to clarify: are you targeting latency reduction,
      memory usage, or code maintainability? And which part of auth — token validation,
      session management, or the OAuth flow?"
```

Why: Plans built on assumptions get rewritten. A 2-minute clarification prevents a 20-minute replan.