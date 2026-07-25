# CI Strategy

Use two-lane fuzz strategy to balance speed and depth.

## Where Go Actually Stores Corpus (read before writing any cache step)

Getting this wrong is the most common fuzz-CI bug: caching the wrong directory
produces a pipeline that looks like it accumulates corpus but never does.

| What | Location | In git? | Cache in CI? |
|------|----------|---------|--------------|
| **Seed corpus** you author by hand | `<pkg>/testdata/fuzz/FuzzXxx/` | **Yes** — you wrote it | n/a (already in repo) |
| **Failing input** found by the fuzzer | `<pkg>/testdata/fuzz/FuzzXxx/` — written automatically **on failure only** | **Yes** — commit it, it becomes a regression test | n/a (in repo once committed) |

`<pkg>` is the directory of the package under test, **not** the repo root. Fuzzing
`./pkg/parser/` writes to `pkg/parser/testdata/fuzz/`. Every path and glob below is written
accordingly — this is the detail that most often breaks crash artifact upload.
| **"Interesting" input** found by the fuzzer (grew coverage, did not fail) | `$GOCACHE/fuzz/<module>/<pkg>/FuzzXxx/` | **No** | **Yes — this is the directory to cache** |

Verify on any machine:

```bash
go env GOCACHE          # e.g. /home/runner/.cache/go-build
go test -run='^$' -fuzz='^FuzzXxx$' -fuzztime=10s .
find "$(go env GOCACHE)/fuzz" -type f    # interesting inputs land here
find . -path '*/testdata/fuzz/*' -type f  # exists only if a failure was found
```

Consequences:

- To carry an **enriched corpus** across runs, cache `$(go env GOCACHE)/fuzz`.
  Caching `testdata/fuzz` carries only what is already committed — it adds nothing.
- To preserve a **crash**, upload `**/testdata/fuzz/**` as an artifact. The CI workspace is
  destroyed after the run, so an uncommitted crasher is otherwise lost.

## One Target Per `-fuzz` Invocation

`-fuzz` must match **exactly one** target. A regex matching several fails immediately:

```
testing: will not fuzz, -fuzz matches more than one fuzz test: [FuzzA FuzzB]
```

So `-fuzz='^Fuzz'` is only valid when the package has a single fuzz target. Use an
anchored per-target regex (`-fuzz='^FuzzParseConfig$'`) and one step per target.
This does **not** apply to `-run='^Fuzz'`, which replays every target's corpus in one go.

## PR Lane (fast, stable)

**Goal**: catch regressions, never slow down PRs.

The PR lane replays the committed corpus. It deliberately does **not** restore the fuzz
cache — replay must be deterministic and depend only on what is in git.

```yaml
name: fuzz-pr

on:
  pull_request:

jobs:
  fuzz-regression:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-go@v5
        with:
          go-version: 'stable'

      # replay committed corpus in testdata/fuzz (no new fuzzing)
      - name: Corpus replay
        run: go test -run='^Fuzz' ./...

      # optional: short fuzz for low-cost targets only, one step per target
      - name: Quick fuzz (low-cost target)
        run: go test -run='^$' -fuzz='^FuzzParseConfig$' -fuzztime=10s ./pkg/parser/
        continue-on-error: true  # don't block PR on a time-limited search
```

Rules:
- Corpus replay is **mandatory** — fail the PR on deterministic replay failures.
- Short fuzz is **optional** — only `Low` cost targets, max 10-15s.
- Never run long fuzz in the PR lane (blocks the merge queue).

## Scheduled Lane (deep)

**Goal**: discover new bugs with extended budgets, and carry the corpus forward.

```yaml
name: fuzz-nightly

on:
  schedule:
    - cron: '0 3 * * *'   # 3 AM UTC daily.
                          # MUST be top-level `on:` — `schedule` is NOT a job key.
  workflow_dispatch:      # allow manual runs

jobs:
  fuzz-nightly:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-go@v5
        with:
          go-version: 'stable'

      # resolve the real fuzz-cache path for this runner
      - name: Resolve fuzz cache dir
        id: fuzzcache
        run: echo "dir=$(go env GOCACHE)/fuzz" >> "$GITHUB_OUTPUT"

      # restore corpus discovered by previous nightly runs.
      # run-scoped key + prefix restore-keys: each run starts from the newest
      # corpus and saves a strictly newer one.
      - uses: actions/cache@v4
        with:
          path: ${{ steps.fuzzcache.outputs.dir }}
          key: fuzz-corpus-${{ github.run_id }}
          restore-keys: |
            fuzz-corpus-

      - name: Deep fuzz
        run: |
          go test -run='^$' -fuzz='^FuzzParseConfig$'   -fuzztime=5m ./pkg/parser/
          go test -run='^$' -fuzz='^FuzzRoundTripEvent$' -fuzztime=5m ./pkg/codec/

      # a crash writes to the TARGET PACKAGE's testdata/fuzz, e.g.
      # pkg/parser/testdata/fuzz/FuzzParseConfig/ — not the repo root. The leading `**/`
      # is required; `testdata/fuzz/**` is anchored at the workspace root and silently
      # captures nothing for any target outside it.
      - uses: actions/upload-artifact@v4
        if: failure()
        with:
          name: fuzz-crashes-${{ github.run_id }}
          path: '**/testdata/fuzz/**'
          if-no-files-found: error   # a failed fuzz run with no crasher means the glob is wrong
```

Rules:
- Budget: 5-10 min per package, 30 min total max.
- **Do not** key the corpus cache on `hashFiles('**/*_test.go')` — every test edit would
  discard the accumulated corpus, which is exactly what the cache exists to preserve.
- Cache `$(go env GOCACHE)/fuzz`, never `testdata/fuzz`.
- Upload crash artifacts on failure with a **`**/`-prefixed glob**. Crashers land in the
  target package's own `testdata/fuzz/`, so a root-anchored `testdata/fuzz/**` uploads an
  empty artifact and the crash is lost when the workspace is destroyed. Set
  `if-no-files-found: error` so a mis-scoped glob fails loudly instead of silently.
- A crasher becomes a permanent regression test only once a human commits it to
  `<pkg>/testdata/fuzz/FuzzXxx/`.
- File issues automatically for new crashes (optional: `gh issue create`).

## Corpus Sharing Between Lanes

Two separate flows, with different storage and different lifetimes:

```
Coverage corpus (ephemeral, cached — NOT in git)
  nightly run → new interesting inputs → $GOCACHE/fuzz → actions/cache
       ↓
  next nightly → restores enriched corpus → explores deeper

Crash corpus (permanent, in git)
  nightly run → failing input → <pkg>/testdata/fuzz/FuzzXxx/ (workspace)
       ↓
  upload-artifact '**/testdata/fuzz/**' → a human commits it to the repo
       ↓
  every PR → corpus replay runs it → the regression cannot silently return
```

Key: deep exploration comes from caching `$GOCACHE/fuzz`; the regression guarantee comes
from committing crashers to `testdata/fuzz`. Different mechanisms — do not conflate them.

## Reporting

Always report in CI output:

| Field | PR Lane | Scheduled Lane |
|-------|---------|---------------|
| Targets run | list | list |
| Targets skipped | list + reason | list + reason |
| Duration budget | per-target | per-target |
| Committed corpus size | count from `testdata/fuzz` | count from `testdata/fuzz` |
| Failures | crash details | crash details + artifact link |
| New cached corpus entries | N/A | count from `$GOCACHE/fuzz` (before/after) |

## Makefile Integration

```make
fuzz-ci: ## Run corpus replay (PR lane)
	$(GO) test -run='^Fuzz' ./...

fuzz-nightly: ## Run deep fuzz (scheduled lane), one target per invocation
	$(GO) test -run='^$$' -fuzz='^FuzzParseConfig$$'   -fuzztime=5m ./pkg/parser/
	$(GO) test -run='^$$' -fuzz='^FuzzRoundTripEvent$$' -fuzztime=5m ./pkg/codec/

fuzz-cache-path: ## Print the directory CI should cache
	@echo "$$($(GO) env GOCACHE)/fuzz"
```
