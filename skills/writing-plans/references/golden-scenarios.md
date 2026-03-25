# Golden Scenarios — Good vs Bad Plan Examples

Each scenario shows a GOOD plan excerpt and a BAD plan excerpt for the same task.

## 1. Feature: Add User Email Verification

### GOOD (Standard mode)
```markdown
**Mode:** Standard
**Repo Discovery:** Go project, go.mod v1.22, tests use testify, CI runs `make test`

### Task 1: Add verification token model
**Files:**
- Create: `internal/auth/verification_token.go` [New]
- Create: `internal/auth/verification_token_test.go` [New]
- Modify: `internal/auth/service.go` [Existing] — add SendVerification method

- [ ] Step 1: Write failing test
  [test-assertion] assert token is created with 24h expiry, linked to user ID
- [ ] Step 2: Run: `go test ./internal/auth/... -run TestVerificationToken -v`
- [ ] Step 3: Implement token model and generation
- [ ] Step 4: Run test, verify pass
```

### BAD (over-decomposed, fabricated paths)
```markdown
### Task 1: Read the codebase
### Task 2: Understand the auth module
### Task 3: Design the token schema
### Task 4: Write the token model at src/models/token.go:1-45  ← wrong path, fabricated lines
    (50 lines of complete implementation code)               ← will be stale
### Task 5: Write one test
### Task 6: Run the test
### Task 7: Write another test
```

## 2. Bugfix: Fix nil pointer on empty config

### GOOD (Lite mode — correct sizing)
```markdown
**Mode:** Lite

- [ ] Write test: nil config input → expect ErrMissingConfig, not panic
  Run: `go test ./pkg/config/... -run TestLoadConfig_Nil -v`
- [ ] Fix: add nil guard in `LoadConfig` [Existing: `pkg/config/loader.go`]
- [ ] Run: `go test ./pkg/config/... -v` — all pass
- [ ] Commit: `fix(config): guard nil config to prevent panic`
```

### BAD (forced TDD ceremony on trivial fix)
```markdown
**Mode:** Standard
### Task 1: Set up test infrastructure for config module
### Task 2: Write comprehensive test suite for LoadConfig
  Step 1: Write 12 table-driven test cases...
### Task 3: Implement the nil guard
### Task 4: Write integration test
### Task 5: Update documentation
```

## 3. Refactor: Extract shared validation logic

### GOOD (Deep mode — has dependency graph and rollback)
```markdown
**Mode:** Deep

**Dependency Graph:**
Task 1 [blocks: 2, 3, 4]
Tasks 2, 3 [parallel]
Task 4 [depends: 2, 3]

### Task 1: Create shared validation package
**Risk:** Medium — 5 packages import current inline validators
**Rollback:** Revert extraction, keep inline validators

### Task 4: Remove old inline validators
**Depends:** Tasks 2, 3 complete and tested
**Rollback:** Re-add inline validators from git history
```

### BAD (Deep refactor without rollback or dependencies)
```markdown
### Task 1: Move all validators to new package
### Task 2: Update all imports
### Task 3: Delete old code
### Task 4: Run tests
(no dependency graph, no rollback, no risk classification)
```

## 4. Migration: Add tenant_id column

### GOOD (Deep mode — phased with validation)
```markdown
**Mode:** Deep | **Risk:** High

### Task 1: Add nullable column
  Migration SQL: `ALTER TABLE orders ADD COLUMN tenant_id bigint;`
  Rollback: `ALTER TABLE orders DROP COLUMN tenant_id;`
### Task 2: Deploy dual-write code
### Task 3: Backfill in batches of 5000
  Validation: `SELECT count(*) FROM orders WHERE tenant_id IS NULL;` → must reach 0
### Task 4: Add NOT NULL constraint with NOT VALID
  Rollback: `ALTER TABLE orders DROP CONSTRAINT ...;`
```

### BAD (one-shot, no rollback)
```markdown
### Task 1: Add column and set NOT NULL
  `ALTER TABLE orders ADD COLUMN tenant_id bigint NOT NULL DEFAULT 0;`
  (table rewrite on million-row table, blocking writes, no rollback)
```

## 5. Docs-only: Update API reference

### GOOD (SKIP decision)
```markdown
Applicability Gate: docs-only change, no logic → SKIP formal plan.
Proceeding directly: update docs/api/endpoints.md, verify links, commit.
```

### BAD (full plan for docs change)
```markdown
**Mode:** Standard
### Task 1: Read current documentation
### Task 2: Write failing test for documentation accuracy (???)
### Task 3: Update section 4.2
### Task 4: Update section 4.3
### Task 5: Run documentation linter
### Task 6: Commit
```

## 6. API Change: Add pagination to list endpoint

### GOOD (Standard mode — includes compatibility)
```markdown
**Mode:** Standard

**Backward Compatibility:** Existing clients send no pagination params →
  default to page=1, limit=20. No breaking change.

### Task 1: Add pagination parameters
**Files:**
- Modify: `internal/api/handlers/list.go` [Existing]
- Modify: `internal/api/handlers/list_test.go` [Existing]

- [ ] Step 1: [test-assertion] Test: no params → returns first 20 items + total count
- [ ] Step 2: [test-assertion] Test: page=2&limit=10 → returns items 11-20
- [ ] Step 3: Implement pagination in handler
- [ ] Step 4: Run: `go test ./internal/api/handlers/... -run TestListHandler -v`
```

### BAD (no compatibility analysis)
```markdown
### Task 1: Change response format to include pagination metadata
  (breaks all existing clients without mention)
### Task 2: Update handler to require page and limit parameters
  (existing clients that don't send these will get errors)
```