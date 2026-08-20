# Worker Findings Contract — v1

The wire format between `stock-analysis-lead` (orchestrator) and the six worker
agents. Load during Step 4 (dispatch) and Step 5a (consolidation).

**Why this exists**: before v1 the orchestrator told workers "return structured
Findings per your skill's Output Format" while the worker agent definitions told
themselves to emit "the machine-readable Findings JSON block exactly as specified
in the orchestrator's dispatch prompt". Neither side defined it. The orchestrator
therefore parsed free-form Markdown, and a worker that dropped a field, emitted
malformed JSON, or wrapped extra prose around the block failed **silently** — the
finding just did not appear in the report. This file closes that loop with a
schema, an enum set, and a deterministic validator that fails loudly.

`CONTRACT_VERSION = "1"`. The version is a **required** field on every payload.
The orchestrator MUST reject a payload whose `contract_version` it does not know
rather than best-effort parsing it.

---

## Transport

The worker's reply is human-readable Markdown (per its skill's Output Format)
**followed by exactly one fenced JSON block** tagged `findings-json`:

````
...worker's Markdown report...

```findings-json
{ ...payload... }
```
````

Rules:

- Exactly **one** `findings-json` block per reply. Zero → `MISSING_BLOCK`.
  Two or more → `MULTIPLE_BLOCKS` (the orchestrator must not guess which is
  authoritative).
- The block contains **only** JSON — no comments, no trailing prose inside the
  fence. Prose belongs above the fence.
- The Markdown above the fence is for the human reader. The orchestrator
  synthesizes **from the JSON only**. Anything a worker states in prose but omits
  from the JSON does not exist as far as the verdict is concerned — this is
  deliberate, and workers are told so in the dispatch prompt.

---

## Payload schema

| Field | Type | Req | Notes |
|---|---|:--:|---|
| `contract_version` | string | ✔ | must equal `"1"` |
| `worker` | string | ✔ | the agent name, e.g. `stock-business-reviewer` |
| `prefix` | string | ✔ | the worker's Finding-ID prefix; one of the fixed set below |
| `status` | string | ✔ | enum below |
| `status_reason` | string | cond | **required** when status ≠ `OK`; free text |
| `depth_mode` | string | ✔ | `Lite` \| `Standard` \| `Strict` — echoed back from dispatch |
| `archetype_applied` | string | ✔ | echoed back from dispatch; proves the worker used the lead's classification |
| `archetype_challenge` | object\|null | ✔ | `null` if the worker accepts the lead's archetype; otherwise `{proposed, reason, evidence}` — see §Archetype challenge |
| `findings` | array | ✔ | may be empty (`[]` = structurally clean, a real result) |
| `positives` | array | ✔ | may be empty; objects `{id, statement, citation}` |
| `data_gaps` | array | ✔ | may be empty; objects `{item, reason}` |
| `checklist_coverage` | object | ✔ | `{items_total, items_checked, items_not_found, ids_not_checked[]}` |
| `mandatory_checks_run` | array | ✔ | the archetype `specialist_checks` IDs the dispatch marked REQUIRED; `[]` when none were passed in |

### `status` enum

| Value | Meaning | Orchestrator action |
|---|---|---|
| `OK` | ran fully, coverage complete | consume normally |
| `DEGRADED` | ran, but some required input was missing | consume; record degradation in Data Coverage |
| `SKIPPED` | precondition failed (no 10-K, non-US issuer, no peer set) | do not consume findings; treat dimension as uncovered |
| `REFUSED` | worker judged the task out of its scope | do not consume; escalate to the user |

Any other value → `BAD_STATUS`.

### `findings[]` element

| Field | Type | Req | Notes |
|---|---|:--:|---|
| `id` | string | ✔ | `<PREFIX>-NN`, optional `-a`/`-b` suffix for multiple instances |
| `severity` | string | ✔ | `High` \| `Medium` \| `Low` |
| `title` | string | ✔ | ≤ 80 chars |
| `citation` | object | ✔ | see below — a bare string is rejected |
| `evidence` | string | ✔ | direct quote ≤ 60 words, or a computed figure with its inputs |
| `implication` | string | ✔ | one sentence: what this means for the thesis |
| `confidence` | string | ✔ | `first-hand` (filing / `financials.json`) \| `second-hand` (aggregator / search snippet) |

### `citation` object

| Field | Type | Req | Notes |
|---|---|:--:|---|
| `source` | string | ✔ | `10-K` \| `10-Q` \| `DEF14A` \| `8-K` \| `transcript` \| `Form4` \| `financials.json` \| `peer-filing` \| `aggregator` |
| `locator` | string | ✔ | e.g. `Item 1A, page 23`, `Note 12`, `Q1 FY26 call, prepared remarks` — must be non-empty |
| `fiscal_period` | string | ✔ | e.g. `FY2024`, `Q1 FY26`, `TTM 2026-06-30` |
| `quote` | string | — | optional verbatim snippet |

`source: aggregator` forces `confidence: second-hand`; the validator enforces
this pair. This is the mechanism that makes the first-hand data rule checkable
instead of aspirational.

---

## Fixed worker → prefix map

The orchestrator, the six worker skills, and the six agent definitions must all
agree on this table. `test_orchestration_matrix.py` asserts it.

| Agent | Skill | Prefix |
|---|---|:--:|
| `stock-business-reviewer` | `stock-business-review` | `BUS` |
| `stock-earnings-quality-reviewer` | `stock-earnings-quality-review` | `EQ` |
| `stock-balance-sheet-reviewer` | `stock-balance-sheet-review` | `BS` |
| `stock-management-reviewer` | `stock-management-review` | `MGT` |
| `stock-industry-reviewer` | `stock-industry-review` | `IND` |
| `stock-peer-comparison-reviewer` | `stock-peer-comparison-review` | `P` |

Prefixes are matched on the **whole ID segment before the first hyphen**, so
`P` can never absorb an ID belonging to another worker.

---

## Archetype challenge

The lead picks the archetype **before** the workers run (Step 1.5c). If that
classification is wrong, every dispatched worker analyzes in the same wrong direction —
a correlated error the parallel architecture otherwise protects against.

Every worker therefore carries a challenge channel:

```json
"archetype_challenge": {
  "proposed": "Capital-Intensive Industrial",
  "reason": "Capex/revenue 31% TTM and 28% 3-yr avg; gross margin 21% — SaaS thresholds do not apply",
  "evidence": {"source": "financials.json", "locator": "capex, revenue TTM", "fiscal_period": "TTM 2026-06-30"}
}
```

Orchestrator handling (Step 5a):

- **0 challenges** → proceed.
- **1 challenge** → record it in Execution Status; re-check the classification
  against `sector-archetypes.md`. If the challenge holds, the Good-Company
  thresholds and valuation norms change, so the affected workers MUST be
  re-dispatched with the corrected archetype (see `dispatch-protocol.md`
  § Re-dispatch). Do not silently keep the original thresholds.
- **≥2 independent challenges proposing the same archetype** → the lead's
  classification is presumed wrong. Re-classify and re-dispatch. A verdict must
  not be published on a contested archetype.

A challenge is **not** a finding and never counts toward the volume caps.

---

## Validation

```bash
python3 scripts/finlib/worker_contract.py validate --reply worker-business.md
python3 scripts/finlib/worker_contract.py validate --reply worker-business.md --expect-worker stock-business-reviewer --expect-depth Standard --expect-archetype "Hyperscaler / Mega-Cap Tech Platform"
python3 scripts/finlib/worker_contract.py consolidate --replies run/workers/*.md --cap 15
```

`validate` exits non-zero on any error code and prints them as JSON. Error codes
are stable identifiers, not prose, so the dispatch state machine can branch on
them:

| Code | Cause | Retryable |
|---|---|:--:|
| `MISSING_BLOCK` | no `findings-json` fence | yes |
| `MULTIPLE_BLOCKS` | more than one fence | yes |
| `BAD_JSON` | fence content is not parseable JSON | yes |
| `BAD_VERSION` | `contract_version` absent or unknown | yes |
| `MISSING_FIELD` | a required field is absent | yes |
| `BAD_TYPE` | field present with the wrong type | yes |
| `BAD_STATUS` | `status` outside the enum | yes |
| `BAD_SEVERITY` | severity outside `High/Medium/Low` | yes |
| `BAD_PREFIX` | `prefix` not in the fixed map, or a finding ID whose prefix ≠ the payload prefix | yes |
| `BAD_CITATION` | citation missing / not an object / empty `locator` / unknown `source` | yes |
| `CONFIDENCE_MISMATCH` | `source: aggregator` with `confidence: first-hand` | yes |
| `WORKER_MISMATCH` | payload `worker` ≠ the agent the lead dispatched | **no** — wrong agent answered |
| `DEPTH_MISMATCH` | payload `depth_mode` ≠ dispatched depth | **no** |
| `ARCHETYPE_MISMATCH` | payload `archetype_applied` ≠ dispatched archetype **and** no challenge filed | **no** |
| `COVERAGE_INCOMPLETE` | `items_checked + items_not_found < items_total` | yes |
| `MANDATORY_CHECK_MISSING` | a REQUIRED archetype check is absent from `mandatory_checks_run` | yes |

Retryable errors are formatting failures — re-dispatch with the validator output
appended to the prompt (one retry, per `dispatch-protocol.md`). Non-retryable
errors mean the dispatch itself was wrong; fix the dispatch, do not re-ask.

---

## Reference payload

```json
{
  "contract_version": "1",
  "worker": "stock-business-reviewer",
  "prefix": "BUS",
  "status": "DEGRADED",
  "status_reason": "10-Q for the current quarter not in manifest; composition is FY-only",
  "depth_mode": "Standard",
  "archetype_applied": "Payment Network / Card Scheme / Transaction Processor",
  "archetype_challenge": null,
  "findings": [
    {
      "id": "BUS-11",
      "severity": "High",
      "title": "Client incentives at 38% of gross revenue, rising 4pp in 3 years",
      "citation": {
        "source": "10-K",
        "locator": "Note 1 Revenue recognition; Item 7 MD&A gross-to-net table",
        "fiscal_period": "FY2025",
        "quote": "Client incentives are recorded as a reduction of revenue"
      },
      "evidence": "Gross revenue $38.2B less client incentives $14.5B = net revenue $23.7B; incentives/gross 38.0% vs 34.1% FY2022",
      "implication": "Reported net-revenue growth understates volume growth and overstates pricing power; the incentive ratchet is a structural margin headwind.",
      "confidence": "first-hand"
    }
  ],
  "positives": [
    {"id": "BUS-02", "statement": "No single customer above 10% of net revenue", "citation": {"source": "10-K", "locator": "Item 1A", "fiscal_period": "FY2025"}}
  ],
  "data_gaps": [
    {"item": "10-Q Q3", "reason": "not present in manifest"}
  ],
  "checklist_coverage": {
    "items_total": 11,
    "items_checked": 9,
    "items_not_found": 2,
    "ids_not_checked": []
  },
  "mandatory_checks_run": ["BUS-11"]
}
```
