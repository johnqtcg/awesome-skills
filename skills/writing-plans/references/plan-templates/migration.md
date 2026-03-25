# Migration Plan Template

**Trigger signals:** database schema change, data backfill, platform migration, dependency upgrade

**Default mode:** Deep (always — migrations are inherently high-risk)

## Required Sections

1. **Pre-migration validation** — current state checks, data integrity baseline
2. **Phased execution** — never one-shot; split into additive → backfill → constraint → cleanup
3. **Rollback SQL/commands per phase** — each phase must be independently reversible
4. **Validation checkpoints** — queries or commands to verify each phase succeeded
5. **Lock/downtime analysis** — which operations take locks, estimated duration, mitigation

## Skippable Sections

- None — all sections are required for migrations

## Skeleton (Deep)

```markdown
# [Migration Name] Implementation Plan

**Goal:** [One sentence]
**Mode:** Deep | **Risk:** High

### Task 1: Add nullable column / new table
  Migration: `ALTER TABLE X ADD COLUMN Y <type>;`
  Rollback: `ALTER TABLE X DROP COLUMN Y;`
  Validation: `SELECT column_name FROM information_schema.columns WHERE ...`

### Task 2: Deploy dual-write code
  Application changes to write to both old and new locations.
  Rollback: Revert application code (column is nullable, no data loss).

### Task 3: Backfill existing data
  Batch size: N rows per iteration.
  Validation: `SELECT count(*) FROM X WHERE Y IS NULL;` → must reach 0
  Rollback: `UPDATE X SET Y = NULL;` (reset backfill)

### Task 4: Add constraint / finalize
  Migration: `ALTER TABLE X ALTER COLUMN Y SET NOT NULL;` (use NOT VALID if large table)
  Rollback: `ALTER TABLE X ALTER COLUMN Y DROP NOT NULL;`
  Validation: Run full test suite + smoke test critical paths
```