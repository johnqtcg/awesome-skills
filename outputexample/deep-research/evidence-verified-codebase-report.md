# Evidence-Verified Codebase Report Example

This illustrative output shows the repository evidence format. The code record is intentionally marked as a working-tree observation rather than pretending it is pinned to a committed revision.

## 1) Research Question

- Normalized question: How does the deep-research helper prevent report generation from bypassing evidence validation?
- Research kind: `codebase`
- Depth mode: `quick`
- Evidence chain requirements: direct code evidence plus an imported host test receipt with explicit claim/code coverage

## 2) Method

- Execution mode: `quick`
- Degradation level: `Partial`
- Retrieval plan / subtopics: inspect the report handler; run the evidence-integrity tests
- Dedup strategy: evidence ID uniqueness
- Retrieved sources: 0
- Content items processed: 0
- Successfully extracted: 0
- Repository evidence units: 2
- Cited evidence units: 2
- Live Web captures / validator-derived T1 references: 0 / 0 (pure codebase mode)
- Validation checks performed: bounded working-tree path/line/excerpt check, complete cited-code-set binding, host receipt schema/Git identity/relevance checks, confidence, and degradation checks

## 3) Executive Summary

The report handler invokes the shared evidence validator before rendering. A host-attested targeted integrity run was imported once and consumed statically, but the example code observation and test run use a dirty working tree, so the finding remains Medium and the report is Partial.

## 4) Key Findings

- **Report generation reuses evidence validation** (Medium confidence): `cmd_report` calls `validate_research_bundle` before `generate_report`, and the targeted evidence-integrity test suite passed. [1][2]

## 5) Detailed Analysis

### Validation flow

The code observation identifies the validator call in the report path. The
receipt covers this finding and `code-1`, names the targeted test selector and
paths, and records an approved relevance rationale. Its dirty snapshot prevents
High confidence. [1][2]

## 6) Consensus vs Debate

### Consensus

- The code path and passing test agree that report generation uses the shared validator. [1][2]

### Debate / Contradictory Evidence

- No contradictory repository evidence was collected.

## 7) Source Quality Notes

- Source tier T1–T5 distribution: no web sources
- Classification basis: direct repository artifacts; no serialized Web
  authority labels or live network claims were consumed
- Potential sponsorship / conflicts of interest: not applicable
- Methodology quality and unknowns: targeted offline host test imported once; the receipt is host attestation rather than cryptographic execution proof; working-tree code/test snapshot is not clean and commit-pinned for this claim
- Single-source findings: 0
- Unverified findings omitted: 0
- Evidence chain status: partially satisfied

## 8) Sources

[1] code evidence `code-1` — `skills/deep-research/scripts/deep_research.py` — `validation = validate_research_bundle(...)` — commit: `working-tree-unpinned`

[2] test evidence `test-1` — framework `unittest`, selector `test_evidence_integrity.py` — host-attested exit 0 — covers this finding and `code-1`; relevance approved; dirty snapshot; bounded stdout/stderr summaries and full-output hashes retained

## 9) Gaps & Limitations

- The code observation is not pinned to a commit, so it cannot support High confidence.
- Pin the final file to the resulting commit and rerun the regression to upgrade the evidence chain.
