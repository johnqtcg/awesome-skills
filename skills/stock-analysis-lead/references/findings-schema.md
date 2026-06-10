# Findings JSON Contract — Worker ↔ Orchestrator Interface

Load this during Step 4 (dispatch — the compact schema is embedded in every dispatch prompt) and Step 5a (consolidation — parse each worker's block).

**Why this exists**: the worker → orchestrator Findings hand-off is the load-bearing interface of this architecture, but it was previously free text — consolidation (dedup, severity sort, volume caps) relied entirely on the orchestrator interpreting prose. A machine-readable block makes consolidation deterministic and makes format drift detectable: a worker that stops emitting the block is flagged, not silently mis-parsed.

The block supplements the worker's human-readable Findings; it does not replace them. Workers emit their normal prose Findings first, then end the reply with exactly one fenced `json` block.

---

## Schema

```json
{
  "worker": "stock-business-reviewer",
  "prefix": "BUS",
  "status": "OK",
  "findings": [
    {
      "id": "BUS-01",
      "severity": "High",
      "title": "Top customer is 22% of revenue",
      "citation": "10-K Item 1A, p. 14",
      "evidence": "Customer A accounted for 22% of FY2025 revenue, up from 17% in FY2023",
      "implication": "Single-customer loss would erase ~2 years of revenue growth"
    }
  ],
  "positives": ["Geographic mix well diversified (no region > 35%)"],
  "data_gaps": ["Segment-level margin not disclosed"]
}
```

## Field Rules

| Field | Type | Rule |
|---|---|---|
| `worker` | string | The agent's own name (`stock-*-reviewer`) |
| `prefix` | string | One of `BUS` / `EQ` / `BS` / `MGT` / `IND` / `P`; must match the worker |
| `status` | string | `OK`, `DEGRADED(<reason>)`, or `SKIPPED(<reason>)` — mirror the degradation state the manifest imposed |
| `findings` | array | May be empty (clean company). Every element needs all 6 keys |
| `findings[].id` | string | `<PREFIX>-NN`, numbered within the worker |
| `findings[].severity` | string | `High` / `Medium` / `Low` |
| `findings[].citation` | string | Filing section or data source — never empty |
| `positives` | array of string | Notable strengths; mandatory when `findings` is empty |
| `data_gaps` | array of string | What the worker wanted but could not get |

## Orchestrator Parsing Rules (Step 5a)

1. Extract the **last** fenced `json` block from each worker's reply.
2. Validate: `prefix` matches the dispatched worker; every finding `id` carries that prefix; severities are from the allowed set.
3. On a missing or malformed block: fall back to the worker's prose Findings, and record `"<worker>: findings JSON block missing/malformed"` in the final report's Data Coverage section. Do not fail the run.
4. Consolidation (dedup by meaning, severity promotion, volume caps) operates on the parsed objects, preserving `citation` and `evidence` verbatim.