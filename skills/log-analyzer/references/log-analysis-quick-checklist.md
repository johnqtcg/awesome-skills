# Log-Analysis Quick Checklist

A short pre-flight and post-flight checklist. **Always loaded.** Use it as the last thing before publishing the report.

## Pre-Flight (Before Drawing Any Conclusion)

- [ ] **Mode chosen**: `Lite | Standard | Strict`, with one-line rationale.
- [ ] **Format detected** per source. Mixed formats split.
- [ ] **Time window locked** in absolute UTC; coverage flagged `full | partial — reason`.
- [ ] **Source listed** with paths / queries / kubectl args.
- [ ] **Volume estimated** (`wc -l`, `du -sh`, or query result count).
- [ ] **Redaction set decided** before quoting any line.
- [ ] **Reference files loaded** matching scope (correlation, aggregator, statistics, cascade, format).

## During Analysis

- [ ] **Quick scan** done: counts by level, top-N error classes, first/last occurrence.
- [ ] **Identifier stripping** applied before grouping by `msg`.
- [ ] **First-occurrence pivot** for each High class — captured 30 lines *before* the first ERROR.
- [ ] **Trace walked** for ≥ 1 representative failure (when correlation IDs are present).
- [ ] **Cascade vs cause** check done — first 30 seconds inspected for the cause cluster.
- [ ] **Statistical context** computed: rate, baseline comparison, new-class diff.
- [ ] **Causation chain** (symptom → proximate → underlying → contributing) for each leading hypothesis.
- [ ] **Volume cap applied**; overflow routed to Residual Risk.

## Pre-Publish (Output Quality)

- [ ] All quoted log lines **redacted**. Spot-checked.
- [ ] Each finding has **ID, Confidence, Category, Location, Evidence, Inference, Refuter, Recommendation**.
- [ ] Each finding labelled `Confirmed | Hypothesis | Hypothesis — needs corroboration`.
- [ ] Severity (`High | Medium | Low`) assigned and matches the rubric.
- [ ] **Execution Status** present even when there are no findings.
- [ ] **Open Questions** lists only blockers that materially change the conclusion.
- [ ] **Residual Risk** captures volume-cap overflow, time-window gaps, and coverage gaps.
- [ ] **Hand-off Protocol** filled when `Strict` mode or post-mortem deliverable is requested.
- [ ] Summary is 1–3 lines and includes confidence + next data needed.
- [ ] **No individuals named** in findings or recommendations.
- [ ] **No raw secrets / tokens / PII** anywhere in the report.

## Sanity Checks (Catch Common Errors)

- [ ] If you wrote "spike", you have a baseline number to compare against.
- [ ] If you wrote "frequent", you have a denominator.
- [ ] If you wrote "caused by", you have either confirmed evidence OR a `Hypothesis` label.
- [ ] If counts are surprising, you checked sampling / quota / rotation before publishing.
- [ ] If correlation IDs are missing, that is itself a High Observability finding.
- [ ] If the cause cluster is not visible, you stated so explicitly under Open Questions.

## When in Doubt

Default to:
- More redaction, not less.
- Wider time window stated, not narrower.
- Lower confidence label, not higher.
- More Open Questions, fewer asserted conclusions.

The cost of an unsourced confident report is a wrong rollback or a wrong post-mortem. The cost of a humble accurate report is a follow-up question.
