# Example Output (End-to-End)

The example below shows the minimum shape for a go-code-reviewer report. Keep findings short, evidence-backed, and origin-aware.

```
### Review Mode
- Standard
- 4 files changed, includes concurrency and persistence paths

### Findings

#### [High] Race Condition on Shared Map
- **ID:** REV-001
- **Origin:** introduced
- **Baseline:** new
- **Principle:** N/A (no constitution.md)
- **Location:** internal/cache/store.go:42
- **Impact:** Concurrent HTTP handlers write to shared map; will panic under load
- **Evidence:** `go vet -race` confirms; map write at L42, concurrent access from handler at L78
- **Recommendation:** Replace with `sync.Map` or protect with `sync.RWMutex`
- **Action:** must-fix

#### [High] SQL Injection in Existing Query Builder
- **ID:** REV-002
- **Origin:** pre-existing
- **Baseline:** new
- **Principle:** N/A
- **Location:** internal/repo/user.go:67
- **Impact:** User-controlled input directly concatenated into SQL query
- **Evidence:** `fmt.Sprintf("SELECT * FROM users WHERE name = '%s'", name)`
- **Recommendation:** Use parameterized query: `db.QueryContext(ctx, "SELECT * FROM users WHERE name = ?", name)`
- **Action:** follow-up issue

### Summary
1 introduced / 1 pre-existing / 0 uncertain.
The pre-existing SQL injection is reported for visibility and follow-up, not as merge debt for the author.
```
