# update-doc Reference

## Purpose

Use this reference when synchronizing `README.md` and docs after code changes.

## Core Drift-Safe Rules

- Prefer code evidence over historical prose.
- Update docs in diff-scoped manner first.
- Keep path notation consistent (project-relative).
- Mark unknowns as `Not found in repo`.
- Never claim command readiness without verification status.

## Required Output Blocks

### Lightweight output

1. Changed files
2. Evidence map (changed sections only)
3. Command verification status

### Full output

1. Changed files
2. Evidence map (section -> source files)
3. Command verification status
4. Scorecard
5. Open gaps

Use lightweight output for narrow README/docs fixes. Use full output for codemaps, restructures, or explicit doc audits.

## Recommended Consistency Checks

- Paths exist
- Links/anchors resolve
- Commands are syntactically runnable
- Terminology is consistent
- No contradictory run modes or env docs
