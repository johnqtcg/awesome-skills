# PR Title

`<type(scope): concise summary>`

## 1) Problem / Context

- What issue is being solved?
- Why now?
- Linked issue/ticket: `<ID or URL>`

## 2) What Changed

- Change 1
- Change 2
- Change 3

## 3) Why This Approach

- Key design choice and rationale
- Tradeoffs considered

## 4) Risk and Rollback Plan

- Main risks:
- Rollback strategy:
- Monitoring/alerts after merge:

## 5) Test Evidence

| Command | Result | Notes |
| --- | --- | --- |
| `go test ./...` | PASS/FAIL | short note |
| `golangci-lint run` | PASS/FAIL | short note |
| `<project command>` | PASS/FAIL | short note |

## 6) Security Notes

- Secret scan result:
- `gosec` result:
- `govulncheck` result:
- Residual risk:

## 7) Breaking Changes / Migration Notes

- Breaking change: yes/no
- Migration steps:
- Compatibility statement:

## 8) Reviewer Checklist

- [ ] Code paths and edge cases make sense
- [ ] Tests and lint evidence are sufficient
- [ ] Security notes are acceptable
- [ ] Rollback strategy is practical
- [ ] Docs/changelog update is sufficient
