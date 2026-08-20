# Golden runs

**Status: none exist yet.** This directory is empty apart from this file.

That is the honest state of the framework's evidence, and it is the largest
remaining gap. Everything else in v3 is verified by 4xx tests; this is not.

## What is missing, precisely

| Evidence | Status |
|---|---|
| The deterministic tool chain composes end to end | **Verified** — `scripts/tests/test_pipeline_e2e.py` walks the documented CLI sequence in order |
| Illegal dispatch histories are refused | **Verified** — `scripts/tests/test_dispatch.py` |
| An incomplete or self-contradicting bundle is blocked | **Verified** — `scripts/tests/test_runbundle.py` |
| Six real agents complete against real SEC filings and real market data | **Not verified** |
| A real worker emits a contract-valid `findings-json` block unprompted | **Not verified** |
| The timeout, invalid-output and retry paths behave as designed on live agents | **Not verified** |
| A second wave fires on a real cross-worker contradiction | **Not verified** |
| The synthesis faithfully carries real worker evidence into the report | **Not verified** |

The end-to-end test builds its worker replies from each worker skill's own
published template. That proves the *templates* satisfy the *validator*. It cannot
prove a live agent, given a real 10-K, produces one — the two failure modes the
contract exists to catch (a dropped field, a fabricated citation) are exactly the
ones a template fixture cannot exhibit.

## Why the two PDFs upstairs are not this

`../MSFT-投资分析报告.pdf` and `../META投资分析报告.pdf` were produced under earlier
skill versions and carry no bundle — no raw replies, no dispatch log, no model
inputs. A reader cannot check whether either synthesis followed its evidence,
which is the whole point of a baseline. See `../README.md` for the version table.

## Producing one

A golden run requires a real analysis: live SEC EDGAR access, current prices, and
six agents actually dispatched. When you have one:

```bash
# after the analysis completes, with the bundle still in $TMPDIR
skills/stock-analysis-lead/scripts/goldenrun.sh capture \
  "$TMPDIR/stock-analysis-msft/run" MSFT
```

`capture` runs `runbundle.py check --stage publication` **first** and aborts on
FAIL, so a bundle that cannot be published can never become a baseline. It writes
`<TICKER>-<verdict_date>/` here plus a `CAPTURE.md` carrying a review checklist —
raw replies can quote scraped third-party content and `verdict.json` records a
personal investment view, so both need a look before anything is committed.

Verify a captured run at any time:

```bash
skills/stock-analysis-lead/scripts/goldenrun.sh verify \
  outputexample/stock-analysis-lead/runs/MSFT-2026-08-20
```

## What a golden run does and does not prove

It is a **regression baseline**: if a later code change alters these artifacts, the
change needs an explanation. It is **not** evidence the verdict was correct —
correctness is what the verdict log and `calibration.py` measure, over years.

## This file cannot go stale

`scripts/tests/test_goldenrun.py` asserts that the claim above matches the
directory: if a run appears here, it must pass the publication gate and this file
must stop saying none exist. The status line is checked, not merely written.
