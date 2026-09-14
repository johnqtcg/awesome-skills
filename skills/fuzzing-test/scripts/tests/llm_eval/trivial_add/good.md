## Applicability Verdict

`Applicability Verdict: Not suitable for fuzzing`

## Why

- Check 1 **Fail** — `Add` and `Double` have no meaningful input space: one fixed
  arithmetic path, no parsing, no branching on input structure. Every `int` pair exercises
  the same instruction sequence, so a coverage-guided fuzzer has nothing to explore.
- Check 3 **Fail** — no oracle beyond restating the implementation. The only invariant
  available is `Add(a,b) == a+b`, which re-implements the function under test and would
  pass for any implementation that is wrong in the same way.
- Item 1 and item 3 are each independently blocking, so the workflow stops here.

## Action

**No fuzz tests written.** Use table-driven unit tests instead, covering the cases that
actually matter for integer arithmetic:

- zero and identity (`Add(0, x)`)
- overflow boundaries (`math.MaxInt`, `math.MinInt`)
- sign combinations

If overflow behaviour is a real concern, a property test with `rapid` over bounded ranges
is a better fit than a fuzzer: the property is arithmetic, not structural.

No harness is emitted, and no `go test -fuzz` command is suggested, because the gate failed.
