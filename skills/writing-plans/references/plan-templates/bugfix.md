# Bugfix Plan Template

**Trigger signals:** reproducing a bug, fixing a reported issue, crash/panic investigation, regression

**Default mode:** Lite (single-file, single-cause) or Standard (multi-file, unclear root cause)

## Required Sections

1. **Bug reproduction** — exact commands, inputs, or conditions that trigger the bug
2. **Root cause hypothesis** — where and why the bug occurs (cite evidence: stack trace, log line, test output)
3. **Fix approach** — test-first: write failing test reproducing the bug → fix → verify
4. **Regression check scope** — which existing tests to run, what else might be affected

## Skippable Sections

- Architecture overview (bug context is sufficient)
- Dependency graph (unless fix spans 3+ modules)
- Phased rollout (unless production hotfix with rollback risk)

## Skeleton (Lite)

```markdown
**Mode:** Lite

- [ ] Reproduce: `<exact command>` → observe `<error>`
- [ ] Write test: `<test name>` — input X → expect Y, currently gets Z
  Run: `<test command>` — expected: FAIL
- [ ] Fix: `<file>` [Existing] — `<one-line description of change>`
- [ ] Run: `<test command>` — expected: PASS
- [ ] Run: `<broader test suite>` — expected: all PASS (no regressions)
- [ ] Commit: `fix(<scope>): <description>`
```