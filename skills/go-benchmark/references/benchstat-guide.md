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

```
goos: linux
goarch: amd64
pkg: example.com/pkg
cpu: Intel Core i7-11800H

name           old time/op    new time/op    delta
Encode/64B      125ns ± 2%     98ns ± 1%   -21.6%  (p=0.002 n=10+10)
Encode/1KB      840ns ± 3%    680ns ± 2%   -19.0%  (p=0.000 n=10+10)
Encode/64KB    52.1µs ± 1%   41.0µs ± 2%   -21.3%  (p=0.000 n=10+10)

name           old allocs/op  new allocs/op  delta
Encode/64B        3.00 ± 0%      1.00 ± 0%   -66.7%  (p=0.000 n=10+10)
Encode/1KB        3.00 ± 0%      1.00 ± 0%   -66.7%  (p=0.000 n=10+10)
Encode/64KB       3.00 ± 0%      1.00 ± 0%   -66.7%  (p=0.000 n=10+10)
```

| Column | Meaning |
|--------|---------|
| `± 2%` | Coefficient of variation (CV) — lower is more stable |
| `delta` | Relative change: negative = improvement |
| `p=0.002` | p-value from Welch t-test — `p < 0.05` = statistically significant |
| `n=10+10` | Samples from old.txt + new.txt |

## p-value Guide

| p-value | Conclusion |
|---------|-----------|
| `p < 0.001` | Very strong evidence of real change |
| `0.001 ≤ p < 0.01` | Strong evidence |
| `0.01 ≤ p < 0.05` | Moderate evidence — consider rerunning |
| `p ≥ 0.05` | Not statistically significant — increase `-count` or reduce noise |

**Rule:** never claim "X is faster than Y" when `p ≥ 0.05`.

## CV (± %) Guide

| CV | Interpretation | Action |
|----|---------------|--------|
| `< 2%` | Excellent stability | Trust results |
| `2–5%` | Acceptable | Fine for most comparisons |
| `5–10%` | Noisy | Use `-benchtime=2s` or `-count=20` |
| `> 10%` | Unreliable | Check for background processes, thermal throttling |

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
- `count=10`: standard comparison; detects ≥15% changes reliably at CV ≤3%
- `count=20`: for subtle changes (< 10%) or noisy environments
- Never use `count=5` for comparative claims; use `count=5` only for exploratory runs

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