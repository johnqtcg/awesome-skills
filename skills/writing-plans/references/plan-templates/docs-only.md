# Docs-Only Plan Template

**Trigger signals:** README update, API reference, inline docs, CHANGELOG, configuration guide

**Default mode:** SKIP (no formal plan) or Lite (if touching multiple doc files)

## Decision

Most docs changes should SKIP the planning phase entirely:

| Situation | Action |
|---|---|
| Single file, straightforward content update | SKIP — proceed directly |
| Multiple files, cross-references need updating | Lite checklist |
| New documentation section with examples to verify | Lite checklist |
| Documentation restructure across 5+ files | Standard (rare) |

## Required Sections (Lite only)

1. **Files to update** — list with `[Existing]`/`[New]` labels
2. **Verification** — link check, build check, or visual review command

## Skippable Sections

- TDD workflow (no testable behavior)
- Risk & Rollback (docs are trivially reversible)
- Dependency graph
- Architecture overview

## Skeleton (Lite)

```markdown
**Mode:** Lite

- [ ] Update `docs/api/endpoints.md` [Existing] — add new endpoint docs
- [ ] Verify links: `<link check command or manual review>`
- [ ] Verify build: `<docs build command>` — no broken references
- [ ] Commit: `docs(<scope>): <description>`
```

## SKIP Example

```
Applicability Gate: docs-only change, no logic → SKIP formal plan.
Proceeding directly: update docs/api/endpoints.md, verify links, commit.
```