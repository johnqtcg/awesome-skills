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

- Key design choice and change-specific rationale (do not describe the create-pr workflow)
- Alternatives/tradeoffs considered

## 4) Risk and Rollback Plan

- Main risks:
- Rollback strategy (must fit this change; do not assume revert/redeploy is sufficient):
- Monitoring/alerts after merge:

## 5) Test Evidence

| Command | Result | Notes |
| --- | --- | --- |
| `go test ./...` | PASS/FAIL | short note |
| `golangci-lint run` | PASS/FAIL | short note |
| `go build ./...` | PASS/FAIL | short note |
| `<project command>` | PASS/FAIL | short note |

Quality coverage (a dimension without executed evidence is an uncovered risk, not a pass):

| Dimension | Evidence |
| --- | --- |
| test | executed: `<cmd>` / N/A (declared) / uncovered: `<reason>` |
| lint | executed: `<cmd>` / N/A (declared) / uncovered: `<reason>` |
| build | executed: `<cmd>` / N/A (declared) / uncovered: `<reason>` |

## 6) Security Notes

- Secret scan result (net diff + every commit in the pushed range):
- `gosec` result:
- `govulncheck` result:
- Residual risk:

## 7) Breaking Changes / Migration Notes

- Breaking change: yes / no / unknown — not assessed
- Migration steps (required and executable when breaking):
- Compatibility statement (`unknown (not assessed)` is a valid, honest value; it keeps the PR in draft):

## 8) Reviewer Checklist

- [ ] Code paths and edge cases make sense
- [ ] Tests and lint evidence are sufficient
- [ ] Security notes are acceptable
- [ ] Rollback strategy is practical
- [ ] Docs/changelog update is sufficient
