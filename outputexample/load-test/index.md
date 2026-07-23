# load-test Output Example

Write-mode and Analyze-mode output produced with the load-test skill against
a sample target, `checkout-service`. Results in the analysis are illustrative
data constructed for this example, not a real production run.

Files:

- [checkout-load-test.js](checkout-load-test.js) — Write mode: complete k6
  script (warmup separation, percentile-based thresholds, parameterized
  cart data, correctly-fed Rate metric, no-remote-dependency
  `handleSummary()`). Validated with `k6 inspect`.
- [testdata/carts.json](testdata/carts.json) — fixture the script's
  `SharedArray` loads.
- [checkout-load-test-analysis.md](checkout-load-test-analysis.md) —
  Analyze mode: full §9 Output Contract (percentile table, bottleneck
  assessment, recommendations, uncovered risks, scorecard) against the
  script's own SLOs.