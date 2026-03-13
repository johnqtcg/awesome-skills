# Crash Handling Reference

## Crash Report Template

When fuzz finds a failure, document using this structure:

### 1. Reproducer

```
Package:  github.com/example/pkg
Target:   FuzzParseXxx
Command:  go test -run=FuzzParseXxx/corpus_entry_name ./pkg/
Input:    testdata/fuzz/FuzzParseXxx/<hash>
```

### 2. Failure Snapshot

```
Type:     panic | invariant_violation | timeout | oom
Message:  <exact error/panic message>
Stack:    <key frames, not full trace>
```

### 3. Corpus Retention

```
Path:     testdata/fuzz/FuzzParseXxx/<hash>
Content:  <hex dump or description of crashing input>
Committed: yes/no (always yes for regression)
```

### 4. Root Cause

One paragraph: why the code failed on this input. Reference specific line numbers and conditions.

### 5. Fix Summary

```
Files changed:  <list>
Approach:       <minimal description>
Diff size:      <lines changed>
```

### 6. Verification

```
Corpus replay:  PASS (go test -run=^FuzzParseXxx$ ./pkg/)
Short fuzz:     PASS (go test -run=^$ -fuzz=^FuzzParseXxx$ -fuzztime=30s ./pkg/)
Unit test:      <added regression test name, if applicable>
```

### 7. Prevention Guard

What was added to prevent this class of bug:
- Input validation / bounds check
- Nil/empty guard
- Overflow protection
- New assertion in fuzz harness

## Crash Classification

| Type | Severity | Action |
|------|----------|--------|
| Panic (nil deref, index OOB, etc.) | High | Fix immediately, add bounds check |
| Invariant violation (round-trip mismatch) | Medium-High | Fix logic bug, keep corpus |
| Timeout / hang | Medium | Add context timeout or input size bound |
| OOM / excessive allocation | Medium | Add allocation limit or input size cap |
| Data race (with `-race`) | High | Fix concurrency, add mutex/atomic |

## Post-Fix Checklist

- [ ] Crashing input saved to `testdata/fuzz/FuzzXxx/`
- [ ] Corpus replay passes
- [ ] Short fuzz run (30s) passes
- [ ] Deterministic regression test added (if applicable)
- [ ] Production code fix is minimal and targeted
- [ ] Similar patterns checked elsewhere in codebase