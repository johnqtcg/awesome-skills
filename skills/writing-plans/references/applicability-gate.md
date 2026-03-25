# Applicability Gate — When to Write a Plan

Load this file when unsure whether a task needs a formal plan.

## Decision Tree

```
Task received
│
├─ Can be done in a single file, <30 lines? ──→ SKIP (execute directly)
├─ Docs/config/README only, no logic? ──→ SKIP or Lite checklist
├─ "Looks small" but touches ≥3 packages? ──→ Reassess: likely Standard
├─ Involves database schema change? ──→ At least Standard (migration risk)
├─ Involves public API contract change? ──→ At least Standard (compatibility risk)
├─ Crosses module boundaries, >800 lines? ──→ Deep mode
└─ Unsure? ──→ Start with Lite, upgrade if complexity emerges
```

## Complexity Signals by Language

| Signal | Go | TypeScript/Node | Python |
|---|---|---|---|
| Multi-package change | ≥3 `internal/` packages | ≥3 workspace packages | ≥3 modules with distinct `__init__.py` |
| Test framework diversity | `_test.go` + integration tags | Jest + Playwright + Storybook | pytest + fixtures + conftest layers |
| Build complexity | Makefile with ≥5 targets | nx/turbo monorepo | tox/nox matrix |

## "Looks Small But Isn't" Signals

These tasks LOOK like they should be Lite but require Standard or Deep:

1. **Import chain depth**: changing a shared utility used by ≥5 consumers
2. **Schema + code**: any database migration paired with application code
3. **API + client**: server endpoint change that requires client SDK update
4. **Auth boundary**: any change touching authentication or authorization paths
5. **CI pipeline**: changes that alter what gates run or how artifacts are built

## Team Size Adjustment

| Context | Default Bias |
|---|---|
| Solo developer, own repo | Lite unless complexity signals fire |
| Team feature, shared repo | Standard minimum for shared understanding |
| Cross-team dependency | Deep with explicit interface contracts |

## Upgrade Protocol

If you started with Lite and discover during execution that:
- The change touches ≥3 files across different modules → upgrade to Standard
- The change has migration, rollback, or phased deployment needs → upgrade to Deep
- The plan keeps growing beyond 15 lines → upgrade to Standard

Announce: "Upgrading from Lite to Standard — complexity exceeded initial estimate."