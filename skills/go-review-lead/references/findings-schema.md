# Findings JSON Contract — Worker ↔ Lead Interface

Load this during Step 3 (dispatch — the compact schema is embedded in every dispatch prompt) and Step 4 (consolidation — parse each worker's block).

**Why this exists**: the worker → lead findings hand-off is the load-bearing interface of this architecture, but it was previously free text — deduplication, severity promotion, and the volume cap relied on the Lead interpreting prose. A machine-readable block makes consolidation deterministic and makes format drift detectable: a worker that stops emitting the block is flagged in Execution Status, not silently mis-parsed.

The block supplements the worker's human-readable report; it does not replace it. Workers emit their normal report first, then end the reply with exactly one fenced `json` block.

---

## Schema

```json
{
  "worker": "go-security-reviewer",
  "prefix": "SEC",
  "grep_audit": {"hit": 5, "total": 14, "confirmed": 2},
  "findings": [
    {
      "id": "SEC-001",
      "severity": "High",
      "title": "SQL injection in user search",
      "location": "internal/repo/user.go:67",
      "evidence": "fmt.Sprintf builds SELECT with raw `name` parameter, passed to db.Query",
      "recommendation": "Use parameterized query: db.Query(\"SELECT ... WHERE name = ?\", name)"
    }
  ],
  "suppressed": [
    {"title": "math/rand in test helper", "reason": "anti-example: non-secret randomness in _test.go"}
  ]
}
```

## Field Rules

| Field | Type | Rule |
|---|---|---|
| `worker` | string | The agent's own name (`go-*-reviewer`) |
| `prefix` | string | One of `SEC` / `CONC` / `ERR` / `LOGIC` / `PERF` / `QUAL` / `TEST` / `OBS`; must match the worker |
| `grep_audit` | object | `hit`/`total`/`confirmed` mirroring the prose audit line. Semantic-only skills (go-logic-reviewer) report `{"hit": 0, "total": 0, "confirmed": N}` |
| `findings` | array | FOUND items only (may be empty). Every element needs all 6 keys |
| `findings[].id` | string | `<PREFIX>-NN`, numbered within the worker |
| `findings[].severity` | string | `High` / `Medium` / `Low` |
| `findings[].location` | string | `path:line`; for raw snippets use `review_snippet.go:line` |
| `suppressed` | array | Items filtered by anti-example gates, each with the gate that matched |

## Lead Parsing Rules (Step 4)

1. Extract the **last** fenced `json` block from each worker's reply.
2. Validate: `prefix` matches the dispatched worker; every finding `id` carries that prefix; severities are from the allowed set.
3. On a missing or malformed block: fall back to the worker's prose report, and record `"<worker>: findings JSON block missing/malformed"` in Execution Status. Do not fail the review.
4. Deduplication, severity promotion, volume caps, and `REV-NNN` renumbering operate on the parsed objects, preserving `evidence` verbatim.