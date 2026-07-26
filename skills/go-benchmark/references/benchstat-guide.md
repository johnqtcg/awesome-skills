# benchstat — Statistical Comparison Guide

## Installation and Basic Usage

```bash
go install golang.org/x/perf/cmd/benchstat@latest

# Capture baseline
go test -bench=. -benchmem -count=10 ./pkg/... | tee old.txt

# Make your change, then capture new run
go test -bench=. -benchmem -count=10 ./pkg/... | tee new.txt

# Compare
benchstat old.txt new.txt
```

## Reading the Output

Current `golang.org/x/perf` output. One **table per metric**, one **column per input file**,
plus a `geomean` aggregate row:

```
goos: darwin
goarch: arm64
pkg: bs
cpu: Apple M4
                │   old.txt   │              new.txt              │
                │   sec/op    │   sec/op     vs base              │
Encode/64B-10     125.4n ± 1%   98.10n ± 1%  -21.77% (p=0.000 n=8)
Encode/1024B-10   1.892µ ± 0%   1.894µ ± 0%       ~ (p=0.738 n=8)
geomean           487.1n        431.0n       -11.52%

                │   old.txt    │               new.txt                │
                │  allocs/op   │ allocs/op     vs base                │
Encode/64B-10       3.000 ± 0%    1.000 ± 0%  -66.67% (p=0.000 n=8)
Encode/1024B-10     3.000 ± 0%    3.000 ± 0%       ~ (p=1.000 n=8) ¹
```

| Element | Meaning |
|--------|---------|
| `sec/op` | Time metric column name. **Not** `time/op` |
| `vs base` | Relative change vs the first file: negative = improvement. **Not** `delta` |
| `± 1%` | **Confidence-interval range** around the median (`-confidence`, default 0.95). Not a coefficient of variation |
| `~` | No statistically significant difference — report as "no measurable change" |
| `p=0.000` | p-value; significant when `p < α` (`-alpha`, default 0.05) |
| `n=8` | Sample count (one number, not `n=8+8`) |
| `geomean` | Geometric mean across all rows — the single-number summary |
| `¹` | Footnote marker; benchstat explains it below the table (e.g. all samples identical) |

**benchstat reports medians, not means.** Its own help states it "shows benchmark medians in a
table". Do not describe its centre value as an average.

> **Retired format.** Material written before ~2023 shows
> `name | old time/op | new time/op | delta` with `n=10+10`. The current tool does not emit
> that layout. If you are looking for a `delta` column, you are reading stale documentation.

### Statistical significance is not practical significance

Comparing a package against **an unmodified copy of itself**, benchstat reported:

```
Encode/64B-10     125.4n ± 1%   128.5n ± 1%  +2.43% (p=0.000 n=8)
```

`p=0.000` on identical code. The +2.43% is real *measurement* drift (thermal state, frequency
scaling, code/data layout), not a code change. Two consequences:

- A significant p-value proves the two **sample sets** differ, not that your **change** caused
  it. Always ask whether the effect exceeds the machine's own run-to-run drift.
- Establish that floor before trusting small wins: run the same binary twice and compare.
  Anything below that noise floor is not a result. Treat sub-5% "wins" with suspicion unless
  the noise floor is demonstrably lower.

## p-value Guide

| p-value | Conclusion |
|---------|-----------|
| `p < 0.001` | Very strong evidence of real change |
| `0.001 ≤ p < 0.01` | Strong evidence |
| `0.01 ≤ p < 0.05` | Moderate evidence — consider rerunning |
| `p ≥ 0.05` | Not statistically significant — increase `-count` or reduce noise |

**Rule:** never claim "X is faster than Y" when `p ≥ 0.05`.

## Spread (`± %`) Guide

The `± N%` figure is the confidence-interval range around the median, not a coefficient of
variation. Either way it is your stability signal — the wider it is, the larger a change has to
be before you can see it.

| `±` range | Interpretation | Action |
|----|---------------|--------|
| `< 2%` | Excellent stability | Trust results |
| `2–5%` | Acceptable | Fine for most comparisons |
| `5–10%` | Noisy | Use `-benchtime=2s` or `-count=20` |
| `> 10%` | Unreliable | Check for background processes, thermal throttling |

A change smaller than the `±` of either side is not measurable on that machine, whatever the
p-value says.

## Common Options

```bash
# Filter by benchmark name regex
benchstat -filter ".*/64B" old.txt new.txt

# Show only significant changes (p < 0.05)
benchstat old.txt new.txt | grep -v "~"

# Compare multiple files (A/B/C test)
benchstat baseline.txt opt1.txt opt2.txt

# Output as CSV for spreadsheet analysis
benchstat -format csv old.txt new.txt
```

## Increasing Statistical Power

```bash
# More samples (preferred)
go test -bench=. -benchmem -count=20 ./... | tee new.txt

# Longer measurement window per sample
go test -bench=. -benchmem -count=10 -benchtime=2s ./... | tee new.txt

# Both: maximum confidence, slow
go test -bench=. -benchmem -count=10 -benchtime=5s ./... | tee new.txt
```

**When to use count=10 vs count=20:**
- `count=10`: standard comparison; detects ≥15% changes reliably when `±` ≤3%
- `count=20`: for subtle changes (< 10%) or noisy environments
- Never use `count=5` for comparative claims; use `count=5` only for exploratory runs

**What extra samples actually buy.** The smallest effect you can resolve shrinks with the
*square root* of the sample count, not linearly:

| `-count` | Relative detectable effect |
|---|---|
| 5 | baseline (1.00×) |
| 10 | 0.71× — about **29%** finer |
| 20 | 0.50× — half the baseline |

So `5 → 10` is a meaningful but modest gain; **quadrupling to `-count=20` is what halves it**.
Reducing machine noise usually beats adding samples: a run at `±1%` resolves more than twice
the detail of a run at `±3%`, at any count.

## Noise Reduction Checklist

Before running comparison benchmarks:
- [ ] Close browser, IDEs, and background downloads
- [ ] On Linux: `sudo cpupower frequency-set -g performance` (pin clock)
- [ ] Wait ≥30s after any large compilation for CPU to stabilize
- [ ] Use `-cpu=1` for single-threaded code to eliminate scheduler noise
- [ ] Run in the same shell session (warm module cache)

## Interpreting No Change

If `benchstat` shows `~ (no change)`:
- The change had no measurable performance impact (could be good or bad)
- Or the change is too small to detect with current sample size
- Or the benchmark is measuring the wrong thing (check for anti-patterns)

If `p=1.000`: identical distributions — likely ran the same binary twice.