# API Change Plan Template

**Trigger signals:** new endpoint, request/response format change, pagination, versioning, deprecation

**Default mode:** Standard (additive changes) or Deep (breaking changes, versioned API)

## Required Sections

1. **Backward compatibility analysis** — will existing clients break? How to handle old format?
2. **Request/response contract** — exact shape of new/changed fields with types
3. **Default behavior** — what happens when new parameters are omitted (existing clients)
4. **Test strategy** — test both old-format and new-format requests
5. **Client migration path** — if breaking, how do consumers update?

## Skippable Sections

- Rollback strategy (for purely additive changes)
- Dependency graph (unless multi-service)
- Phased rollout (unless breaking change)

## Skeleton (Standard)

```markdown
# [API Change] Implementation Plan

**Goal:** [One sentence]
**Mode:** Standard

**Backward Compatibility:**
  Existing clients send no new params → default to <sensible defaults>.
  No breaking change for current consumers.

### Task 1: Add new parameters/fields
**Files:**
- Modify: `path/to/handler` [Existing]
- Modify: `path/to/handler_test` [Existing]

- [ ] Step 1: [test-assertion] Test: no params → returns current behavior unchanged
- [ ] Step 2: [test-assertion] Test: new params → returns expected new behavior
- [ ] Step 3: Implement changes in handler
- [ ] Step 4: Run: `<test command>` — both old and new format tests PASS
- [ ] Step 5: Commit: `feat(api): add <description>`
```