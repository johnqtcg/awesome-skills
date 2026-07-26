**Mode**: Review
**Doc type**: troubleshooting
**Resolution**: R1 — the document under review states its own system and reader, so no retrieval
or assumption was needed → Level 1.
**Reference loaded**: writing-quality-guide.md §Review Patterns (severity grouping, evidence
over opinion).

Findings are grouped by severity tier. Each carries the offending text and a concrete
replacement — evidence over opinion, no "this could be clearer".

## Critical findings

**C1 — Root cause is asserted without evidence**

- Before: `Root cause: the database was slow.`
- After: `Root cause: connection pool exhaustion. Evidence: pool_active hit the 20 cap at
  14:02 (Grafana db-pool panel), while pool_wait_seconds p99 rose to 8.4s. Slow queries were a
  symptom, not the cause — query p99 was flat until the pool saturated.`
- Why Critical: a troubleshooting doc whose root cause is unevidenced cannot be trusted to
  prevent recurrence, which is the document's whole purpose.

**C2 — No verification after the fix**

- Before: `Fix: restarted the service.`
- After: `Fix: raised max_open_conns 20 → 60 and restarted. Verify: pool_active plateaus below
  50 under peak load, and pool_wait_seconds p99 stays under 100ms for 30 minutes.`
- Why Critical: without a verification step the reader cannot tell whether the fix worked.

## Standard findings

**S1 — Conclusion is buried**

- Before: the root cause appears in the sixth paragraph, after a chronological narrative.
- After: move the root-cause sentence directly under the H1; keep the timeline as a later
  section. Troubleshooting docs are read under pressure — the answer goes first.

**S2 — Prevention has no thresholds**

- Before: `Prevention: monitor the connection pool.`
- After: `Prevention: alert when pool_active > 80% of max_open_conns for 5 minutes; page when
  pool_wait_seconds p99 > 1s.` An unquantified "monitor X" is not actionable.

## Hygiene findings

**H1 — Terminology mixes "connection pool" and "DB pool"** — pick one and use it throughout.

## Quality Scorecard

Type is `troubleshooting`.

- **Critical**: 2/4 applicable pass (1 N/A — parameter tables). C1 and C2 above are the failures,
  so the document is **not deliverable** until they are fixed.
- **Standard**: 2/4 applicable pass (2 N/A — rollback and error codes are task/reference items)
  → FAIL (need 3/4).
- **Hygiene**: 3/4 applicable pass, 2 conditional not applicable (no diagrams) → PASS (need 3/4).

Recommended order: fix C1 and C2 first — S1 is a restructure that is cheaper once the root cause
sentence exists.
