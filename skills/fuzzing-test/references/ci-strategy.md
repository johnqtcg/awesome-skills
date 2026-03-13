# CI Strategy

Use two-lane fuzz strategy to balance speed and depth.

## PR Lane (fast, stable)

**Goal**: catch regressions, never slow down PRs.

```yaml
# GitHub Actions example
fuzz-regression:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4

    # restore corpus from previous nightly runs
    - uses: actions/cache/restore@v4
      with:
        path: testdata/fuzz
        key: fuzz-corpus-${{ hashFiles('**/*_test.go') }}
        restore-keys: fuzz-corpus-

    # replay corpus only (no new fuzzing)
    - name: Corpus replay
      run: go test -run=^Fuzz ./...

    # optional: short fuzz for low-cost targets only
    - name: Quick fuzz (low-cost targets)
      run: |
        go test -run=^$ -fuzz=^FuzzParse -fuzztime=10s ./pkg/parser/
      continue-on-error: true  # don't block PR on time-limited fuzz
```

Rules:
- Corpus replay is **mandatory** — fail PR on deterministic replay failures.
- Short fuzz is **optional** — only for `Low` cost targets, max 10-15s.
- Never run long fuzz in PR lane (blocks merge queue).

## Scheduled Lane (deep)

**Goal**: discover new bugs with extended fuzz budgets.

```yaml
# GitHub Actions example — runs nightly
fuzz-nightly:
  runs-on: ubuntu-latest
  schedule:
    - cron: '0 3 * * *'  # 3 AM UTC daily
  steps:
    - uses: actions/checkout@v4

    - uses: actions/cache@v4
      with:
        path: testdata/fuzz
        key: fuzz-corpus-${{ hashFiles('**/*_test.go') }}
        restore-keys: fuzz-corpus-

    - name: Deep fuzz
      run: |
        go test -run=^$ -fuzz=^Fuzz -fuzztime=5m ./pkg/parser/
        go test -run=^$ -fuzz=^Fuzz -fuzztime=5m ./pkg/codec/
      timeout-minutes: 30

    # save any new corpus entries (including crash inputs)
    - uses: actions/cache/save@v4
      if: always()
      with:
        path: testdata/fuzz
        key: fuzz-corpus-${{ hashFiles('**/*_test.go') }}-${{ github.run_id }}

    # upload crash artifacts
    - uses: actions/upload-artifact@v4
      if: failure()
      with:
        name: fuzz-crashes-${{ github.run_id }}
        path: testdata/fuzz/**/
```

Rules:
- Budget: 5-10 min per package, 30 min total max.
- Cache corpus between runs for incremental improvement.
- Upload crash artifacts on failure for investigation.
- File issues automatically for new crashes (optional: use `gh issue create`).

## Corpus Sharing Between Lanes

```
nightly run → discovers new corpus entries → saves to cache
     ↓
next PR → restores cached corpus → replays (catches regressions from code changes)
     ↓
next nightly → starts from enriched corpus → explores deeper
```

Key: use `actions/cache` with a key that combines test file hash + run ID to avoid cache collisions.

## Reporting

Always report in CI output:

| Field | PR Lane | Scheduled Lane |
|-------|---------|---------------|
| Targets run | list | list |
| Targets skipped | list + reason | list + reason |
| Duration budget | per-target | per-target |
| Corpus size | count | count (before/after) |
| Failures | crash details | crash details + artifact link |
| New corpus entries | N/A | count added |

## Makefile Integration

```make
fuzz-ci: ## Run corpus replay (PR lane)
	$(GO) test -run=^Fuzz ./...

fuzz-nightly: ## Run deep fuzz (scheduled lane)
	$(GO) test -run=^$$ -fuzz=^Fuzz -fuzztime=5m ./pkg/parser/
	$(GO) test -run=^$$ -fuzz=^Fuzz -fuzztime=5m ./pkg/codec/
```