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

### 4. Triage Verdict (round-trip / differential failures — mandatory)

A round-trip or differential failure can come from either side, and SKILL.md §Crash
Handling requires the verdict to be decided **from the contract**, not from confidence in
the code. Record which, and on what basis:

```
Verdict:         harness_wrong | implementation_wrong | contract_ambiguous
Contract clause: <the documented sentence that decided it, quoted or cited>
Basis:           <why that clause settles this input>
```

- `harness_wrong` — the contract says this input is outside what the target must preserve.
  Fix: add the domain guard or the canonical comparison. **Cite the clause.**
- `implementation_wrong` — the contract says the value must survive. Keep the input as a
  regression corpus entry.
- `contract_ambiguous` — neither is settled. Report it as an open question with the
  reproducer attached; do **not** change the assertion to hide it.

A harness fix filed with `Contract clause: (none)` is indistinguishable from suppressing a
bug, and must be reviewed as one. For a plain panic/OOM finding this section is `N/A —
no-panic oracle`.

### 5. Root Cause

One paragraph: why the code failed on this input. Reference specific line numbers and conditions.

### 6. Fix Summary

```
Files changed:  <list>
Approach:       <minimal description>
Diff size:      <lines changed>
```

### 7. Verification

```
Corpus replay:  PASS (go test -run=^FuzzParseXxx$ ./pkg/)
Short fuzz:     PASS (go test -run=^$ -fuzz=^FuzzParseXxx$ -fuzztime=30s ./pkg/)
Unit test:      <added regression test name, if applicable>
```

### 8. Prevention Guard

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

- [ ] Crashing input saved to `<pkg>/testdata/fuzz/FuzzXxx/`
- [ ] Triage verdict recorded with its contract clause (round-trip / differential only)
- [ ] Corpus replay passes
- [ ] Short fuzz run (30s) passes
- [ ] Deterministic regression test added (if applicable)
- [ ] Production code fix is minimal and targeted
- [ ] Similar patterns checked elsewhere in codebase