# Feature Plan Template

**Trigger signals:** new functionality, user story, feature request, spec implementation

**Default mode:** Standard (most features) or Deep (cross-module, new subsystem)

## Required Sections

1. **Goal** — one sentence describing what the feature enables
2. **File structure** — all files to create/modify with `[Existing]`/`[New]` labels
3. **Tasks** — each task: failing test → implementation → verification → commit
4. **Backward compatibility** — impact on existing behavior, API consumers, data formats
5. **Execution handoff** — recommended execution approach

## Skippable Sections

- Dependency graph (unless Deep mode)
- Rollback strategy (unless Medium/High risk)
- Migration steps (unless data model changes)

## Skeleton (Standard)

```markdown
# [Feature Name] Implementation Plan

**Goal:** [One sentence]
**Mode:** Standard
**Repo Discovery:** [Language, test framework, CI setup]

### Task 1: [Component Name]
**Files:**
- Create: `path/to/new_file` [New]
- Modify: `path/to/existing_file` [Existing] — add X method

- [ ] Step 1: [test-assertion] Write failing test for core behavior
- [ ] Step 2: Run: `<test command>` — expected: FAIL
- [ ] Step 3: Implement minimal code to pass test
- [ ] Step 4: Run: `<test command>` — expected: PASS
- [ ] Step 5: Commit: `feat(<scope>): <description>`
```