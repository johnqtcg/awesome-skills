# benchstat — Statistical Comparison Guide

## Installation and Basic Usage

Install once:

```bash
go install golang.org/x/perf/cmd/benchstat@latest
```

**Summarise one variant.** Runs top-to-bottom on its own; makes no A/B claim:

```bash
go test -bench=. -benchmem -count=10 ./pkg/... | tee old.txt
benchstat old.txt
```

**Compare two variants.** Do *not* get `new.txt` by repeating the block above with the other
checkout — that is the sequential pattern §Interleave A and B exists to replace. Produce both
files there, then:

```bash
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

A change comparable to or smaller than the `±` of either side is unlikely to be resolvable on
that machine — treat it as below the noise floor and reduce noise or add samples before
believing it. This is a practical reading of the interval, not a theorem: benchstat's
significance verdict comes from the p-value against `-alpha`, and an effect narrower than the
displayed range can still test significant if the two distributions separate cleanly.
Where the two disagree, distrust both and stabilise the machine.

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
- `count=10`: the usual starting point for a comparison; on a quiet machine showing `±` ≤3% it
  will typically surface changes in the low tens of percent
- `count=20`: for subtle changes (< 10%) or noisy environments
- Never use `count=5` for comparative claims; use `count=5` only for exploratory runs

**What extra samples actually buy — a rule of thumb, not a guarantee.** For an average over
independent, identically distributed samples, the standard error shrinks with the *square root*
of the sample count, so the smallest resolvable effect scales roughly as `1/√n`:

| `-count` | Relative detectable effect (approx.) |
|---|---|
| 5 | baseline (1.00×) |
| 10 | 0.71× — about **29%** finer |
| 20 | 0.50× — half the baseline |

Read that as direction and rough magnitude. Two things stop it from being exact:

- **benchstat does not test a mean.** It reports **medians** and compares distributions with a
  non-parametric test, judging significance by p-value against `-alpha` (default 0.05) and
  showing a confidence range at `-confidence` (default 0.95) — all visible in `benchstat -h`.
  A rank test's power depends on the shape of the two distributions, not on `√n` alone.
- **Benchmark samples are frequently not independent.** Thermal throttling, frequency scaling
  and background load drift *during* a run, so consecutive samples correlate. When that
  happens, extra samples buy less than `1/√n` predicts — sometimes much less, because you are
  sampling the same drift repeatedly rather than sampling noise afresh.

The practical consequence is unchanged, and is the part to remember: `5 → 10` is a modest gain,
**quadrupling to `-count=20` is what halves the resolvable effect**, and reducing machine noise
usually beats adding samples — a run at `±1%` resolves more detail than a run at `±3%` at any
count.

## Interleave A and B — do not run all of A, then all of B

The second correlation problem above has a cheap fix that costs no extra samples. If the
machine warms up, or a background job starts halfway through, running every `old` sample before
every `new` sample bakes that drift straight into the difference you are about to attribute to
your change. Alternating the two spreads any drift across both sides.

**Compile both variants first, then alternate the binaries.** Switching branches inside the
measurement loop is the version of this that goes wrong: it fails outright on a dirty worktree,
assumes particular branch names, leaves you parked on the wrong branch if the loop is
interrupted, and folds compilation into the window you are timing.

```bash
# BAD: all of old, then all of new — drift is confounded with the change
go test -bench=. -benchmem -count=10 ./... > old.txt
git switch feature && go test -bench=. -benchmem -count=10 ./... > new.txt

# ALSO BAD: alternating, but by switching the worktree 20 times mid-measurement.
# Fails on a dirty tree, hardcodes branch names, leaves you on `feature` if interrupted,
# and folds compilation into the timing window.
for i in $(seq 10); do
    git switch main -q    && go test -bench=. -count=1 ./... >> old.txt
    git switch feature -q && go test -bench=. -count=1 ./... >> new.txt
done

# GOOD: build once per variant, restore your branch, then alternate two fixed binaries.
# `go test -c` compiles a SINGLE package — `-o file` with ./pkg/... fails with
# "with multiple packages, -o must refer to a directory or /dev/null".
git switch main    -q && go test -c -o /tmp/old.bench ./pkg/mypkg
git switch feature -q && go test -c -o /tmp/new.bench ./pkg/mypkg
git switch -       -q

bash scripts/run_interleaved_bench.sh /tmp/old.bench /tmp/new.bench /tmp/bench-out 10
```

The script refuses to overwrite an existing `old.txt`/`new.txt` rather than appending to it,
writes results outside the repository, validates its arguments, and runs benchstat at the end.

A compiled test binary takes its flags with a `-test.` prefix (`-test.bench`, `-test.count`,
`-test.benchmem`, `-test.run`) — the bare forms only work through `go test`.

benchstat consumes the appended files exactly the same way — it groups by benchmark name, not
by position — so interleaving changes nothing except which run the drift lands on. When a
comparison is close to the noise floor, this is usually worth more than doubling `-count`.

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