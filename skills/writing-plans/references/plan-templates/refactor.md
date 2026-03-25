# Refactor Plan Template

**Trigger signals:** extracting shared logic, splitting large modules, renaming/reorganizing, reducing duplication

**Default mode:** Standard (single-module) or Deep (cross-module, shared interfaces)

## Required Sections

1. **Motivation** — why refactor now (tech debt, readability, testability, upcoming feature)
2. **Scope boundary** — exactly what changes, what does NOT change
3. **Dependency graph** — which modules import what, change order matters
4. **Rollback strategy** — how to revert each phase if tests break
5. **Behavioral equivalence proof** — existing tests must pass unchanged

## Skippable Sections

- New feature tests (refactor should not change behavior)
- API compatibility analysis (unless public API changes)

## Skeleton (Deep)

```markdown
# [Refactor Name] Implementation Plan

**Goal:** [One sentence]
**Mode:** Deep

**Dependency Graph:**
Task 1 [blocks: 2, 3]
Tasks 2, 3 [parallel]
Task 4 [depends: 2, 3]

### Task 1: Create shared package/module
**Risk:** Medium — N packages currently import inline logic
**Rollback:** Revert extraction, keep inline versions

- [ ] Step 1: Run existing tests: `<command>` — baseline: all PASS
- [ ] Step 2: Create shared interface [New]
- [ ] Step 3: Run tests again — still all PASS (no behavior change)
- [ ] Step 4: Commit: `refactor(<scope>): extract shared <X>`

### Task 4: Remove old inline code
**Depends:** Tasks 2, 3 complete and tested
**Rollback:** Re-add inline code from git history

- [ ] Step 1: Remove old code
- [ ] Step 2: Run full test suite — all PASS
- [ ] Step 3: Commit: `refactor(<scope>): remove deprecated inline <X>`
```