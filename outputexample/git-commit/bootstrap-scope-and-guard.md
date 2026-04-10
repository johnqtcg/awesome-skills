# git-commit Output Example: Bootstrap Scope + Guard

## Scenario

- Repository history has only 3 conventional commits.
- Staged files:
  - `services/billing/invoice_sync.go`
  - `services/billing/invoice_sync_test.go`
- Environment: `QUALITY_GATE_TIMEOUT_SECONDS=600`

## Expected behavior

1. Infer bootstrap scope `billing` from the stable staged directory.
2. Compose `feat(billing): add invoice sync job`.
3. Validate the subject before commit.
4. Run the quality gate with a reported timeout of `600` seconds.

## Guard output on failure

```text
subject too long (58/50)
```
