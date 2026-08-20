# Dispatch Protocol — Triage Tiers, State Machine, Budgets, Run Bundle

Load during Step 3 (triage) and Step 4 (dispatch). This file governs **who runs,
what happens when a worker fails, and what evidence the run leaves behind**.

**Why this exists**: v2 had a "Triage" step that dispatched all six workers at
every depth, and a failure model that covered only *missing data*. An agent that
timed out, crashed, refused, or returned unparseable JSON had no defined
handling — and "wait for all workers to return" made the slowest worker the
floor on latency for every run, including a hallway gut-check. Six agents also
compound: at 97% per-agent success the all-six success rate is 83%.

---

## Part 1 — Triage Tiers

Workers fall into three tiers. Only Tier 0 runs unconditionally.

### Tier 0 — Core (always dispatched, every depth)

These four cover the Good-Company items no other worker can supply, so skipping
any of them makes the score uninterpretable rather than merely thinner:

| Worker | Owns Good-Company items |
|---|---|
| `stock-business-reviewer` | 1 (revenue growth quality), 6 (share, narrative side) |
| `stock-earnings-quality-reviewer` | 2, 3, 4 (margin, leverage, cash) |
| `stock-balance-sheet-reviewer` | 7 (leverage), Bear-scenario floor |
| `stock-industry-reviewer` | 9 (moat), 10 (TAM) |

At Lite depth, Industry runs **Lite-Industry mode** (moat type + share-trend
one-liner, no Porter scan). The other three run full.

### Tier 1 — Conditional

Dispatched when a trigger fires. Each trigger is a property of the run, not a
judgment call:

| Worker | Dispatch when |
|---|---|
| `stock-management-reviewer` | depth ∈ {Standard, Strict} · **OR** DEF 14A + transcript both present · **OR** the question targets capital allocation / M&A / buybacks / insiders / guidance credibility · **OR** archetype ∈ {Mature Cash Cow, Capital-Intensive, Financials, REIT} (capital allocation *is* the thesis for these) |
| `stock-peer-comparison-reviewer` | depth ∈ {Standard, Strict} · **OR** a peer set of ≥2 names exists in the manifest **AND** the question is valuation- or moat-shaped ("expensive", "cheap", "fair price", "moat", "vs peers", "losing share") |

At **Lite** with none of the triggers firing, the fan-out is **4 workers**, not 6.
That is the point: Lite exists to be cheap. When a Tier-1 worker is skipped, the
Good-Company items it would have informed (8 — management quality) are scored
`UNSCORED` rather than guessed, and the report's Data Coverage section says which
worker was not run and why.

### Tier 2 — Conflict-triggered (second wave)

Dispatched **after** the first wave returns, only when consolidation surfaces a
specific contradiction. Each entry names the worker to re-run and the question it
must answer — a targeted re-dispatch, not a full re-run:

| Conflict detected in Step 5a | Second-wave dispatch |
|---|---|
| Industry claims share gains, but `P-01` revenue growth ≤ peer median | `stock-industry-reviewer`, scoped: "reconcile the share claim against peer revenue growth; cite the share series" |
| Industry claims a switching-cost/scale moat, but `P-02`/`P-04` margins below peer median | `stock-peer-comparison-reviewer`, scoped: "extend the panel through the last full cycle — is the margin gap cyclical or structural?" |
| ≥2 workers file the same `archetype_challenge` | re-classify, then re-dispatch **every** Tier-0 worker with the corrected archetype |
| Earnings-quality reports operating leverage, but `P-03` operating margin flat/declining vs peers | `stock-earnings-quality-reviewer`, scoped: "decompose the leverage claim by segment and by GAAP vs non-GAAP" |
| Balance-sheet reports adequate liquidity, but the Bear scenario implies a covenant breach | `stock-balance-sheet-reviewer`, scoped: "run the covenant math at Bear-case EBITDA" |

Second-wave dispatch is capped at **2 workers per run** (Strict: 3). Beyond that,
the conflict is not resolvable by more agents — surface it as an unresolved
tension in the synthesis and default the verdict to **Hold** per Step 5c.

---

## Part 2 — Dispatch State Machine

Every dispatched worker occupies exactly one state. The orchestrator maintains
this table in `run/dispatch-log.json` and **must** render it in the report's Data
Coverage section.

```
                    ┌──────────► TIMEOUT ──────────┐
                    │                              │
PENDING ──► RUNNING ┼──────────► CRASHED ──────────┼──► retry? ──► (RUNNING)
                    │                              │        │
                    └──► RETURNED ──► validate ────┤        └──► exhausted ──► FAILED
                                          │        │
                              PASS ───────┘        │
                                │                  │
                                ▼             INVALID_OUTPUT
                          VALIDATED
                                │
                    ┌───────────┴───────────┐
                    ▼                       ▼
              OK / DEGRADED          SKIPPED / REFUSED
```

| State | Meaning | Counts toward a publishable verdict? |
|---|---|---|
| `PENDING` | selected by triage, not yet launched | — |
| `RUNNING` | agent in flight | — |
| `RETURNED` | reply received, not yet validated | — |
| `VALIDATED` | reply passed `worker_contract.py validate` | yes (status `OK`/`DEGRADED`) |
| `INVALID_OUTPUT` | validation produced retryable error codes | no, until retry succeeds |
| `TIMEOUT` | no reply within the worker budget | no |
| `CRASHED` | agent returned an error / empty reply / tool failure | no |
| `SKIPPED` | worker itself reported `SKIPPED` (precondition failed) | no — dimension is uncovered |
| `REFUSED` | worker itself reported `REFUSED` | no — escalate to the user |
| `FAILED` | retries exhausted | no |
| `NOT_DISPATCHED` | triage did not select it | no — record the trigger that did not fire |

### Events — enforced, not narrated

The state table above is **owned by `scripts/finlib/dispatch.py`**, not by the
orchestrator's prose. The orchestrator plans the fan-out and records each event
through it; illegal events are refused with a non-zero exit and an explanation.

Before this module the transitions were documented here and then written into a
log the orchestrator authored freely — so `VALIDATED` with four attempts, a retry
after `WORKER_MISMATCH`, a Lite run dispatching six workers, and a five-deep
second wave were all recordable and nothing objected.

**Honest scope**: the *executor* is still the orchestrator — only it can spawn
agents. `dispatch.py` is the referee, not the runner. What it guarantees is that
`dispatch-log.json` cannot describe a history the protocol forbids.

```bash
python3 scripts/finlib/dispatch.py plan --log run/dispatch-log.json --ticker MSFT \
  --depth Standard --archetype "Hyperscaler" --manifest run/data-manifest.json \
  --question-shape valuation,moat
python3 scripts/finlib/dispatch.py record --log run/dispatch-log.json \
  --worker stock-business-reviewer --event launched
python3 scripts/finlib/dispatch.py quorum --log run/dispatch-log.json
```

`plan` computes Tier-1 triggers from depth + manifest + question shape, so triage
is a function rather than a judgment call. It refuses to plan at all when the
manifest has no 10-K.

| Event | Legal prior states | Result | Refused when |
|---|---|---|---|
| `dispatched` | — (opens a wave-2 entry) | `PENDING` | no `--reason`; the depth's second-wave cap is already reached |
| `launched` | `PENDING` | `RUNNING` | the worker was never dispatched; already launched; attempt cap reached |
| `returned` | `RUNNING` | `RETURNED` | nothing was in flight |
| `validated` | `RETURNED` | `VALIDATED` / `SKIPPED` / `REFUSED` (from the payload's `status`) | `--status` absent or outside the enum |
| `invalid` | `RETURNED` | `INVALID_OUTPUT` | `--error-code` absent — the retry decision must be recorded, not assumed |
| `timeout` | `RUNNING` | `TIMEOUT` | nothing was in flight |
| `crashed` | `RUNNING` | `CRASHED` | nothing was in flight |
| `retry` | `INVALID_OUTPUT` / `TIMEOUT` / `CRASHED` | `RUNNING` | the error code is non-retryable; attempt cap reached; leaving `INVALID_OUTPUT` without `--error-code` |
| `failed` | `INVALID_OUTPUT` / `TIMEOUT` / `CRASHED` | `FAILED` | attempts not yet exhausted — the granted retry may not be skipped |

`validated` splits on the payload's own status because a worker that correctly
declined is not a validation failure, yet it still leaves its dimension uncovered:
`SKIPPED` and `REFUSED` never count toward the quorum.

### Retry policy

- **One** retry per worker. Retrying a second time on the same input mostly
  reproduces the same failure and doubles the cost.
- Retry is allowed **only** for `INVALID_OUTPUT` with all-retryable error codes,
  `TIMEOUT`, and `CRASHED`. Never for `SKIPPED` / `REFUSED` (the worker made a
  correct judgment) and never for the non-retryable codes
  `WORKER_MISMATCH` / `DEPTH_MISMATCH` / `ARCHETYPE_MISMATCH` — those mean the
  **dispatch** was wrong, so fix the dispatch and re-launch as a new attempt.
- On an `INVALID_OUTPUT` retry, append the validator's JSON error list verbatim
  to the retry prompt plus: *"Your previous reply failed contract validation with
  the errors below. Return the same analysis with a compliant `findings-json`
  block. Do not re-run the research."* This makes the retry cheap.
- No model fallback. A different model is a different analyst; silently swapping
  one in makes the run unauditable. If a worker cannot complete, mark it `FAILED`
  and degrade the report honestly.

### Re-dispatch (archetype correction)

A retry re-asks the *same* question. A **re-dispatch** asks a *different* one,
because the dispatch parameters changed — so it re-plans rather than consuming
the retry.

Re-dispatch when:

- **≥2 workers file the same `archetype_challenge`** → the classification is
  presumed wrong. Re-classify, then re-dispatch **every** Tier-0 worker with the
  corrected archetype. Their thresholds all changed.
- **1 challenge that survives re-checking against `sector-archetypes.md`** →
  re-dispatch only the workers whose thresholds the correction actually moves.
- **A non-retryable validator code** (`WORKER_MISMATCH` / `DEPTH_MISMATCH` /
  `ARCHETYPE_MISMATCH`) → the dispatch itself was wrong. Fix it and re-plan; the
  state machine refuses to record these as retry causes.

Mechanically this is `dispatch.py plan` again with the corrected archetype,
preserving the prior log as `dispatch-log.archetype-1.json` in the bundle. The
superseded workers' replies stay on disk under their `.attempt<N>.md` names — that
the first classification was tried and abandoned is part of the run's evidence,
not something to overwrite.

A verdict must never be published while an archetype is contested.

### Timeout and head-of-line blocking

- Per-worker budget: **Lite 5 min · Standard 10 min · Strict 15 min**, measured
  from launch.
- **Do not block on the full set.** Consolidate on the *quorum* (below) as soon
  as it is met. A worker still `RUNNING` past the budget is marked `TIMEOUT` and
  the report proceeds without it. The alternative — one stalled agent holding the
  entire analysis — is the failure mode this rule exists to prevent.
- Timed-out workers are never partially consumed. A truncated reply has no
  validated `findings-json` block, so it contributes nothing.

### Quorum — when may a verdict be published?

| Condition | Rule |
|---|---|
| All four Tier-0 workers `VALIDATED` with status `OK`/`DEGRADED` | **Full verdict** permitted |
| Exactly one Tier-0 worker not validated | **Degraded verdict** permitted: conviction capped at **Low**, the missing worker's Good-Company items scored `UNSCORED`, and the gap named in the Verdict line itself — not only in Data Coverage |
| ≥2 Tier-0 workers not validated | **No verdict.** Report what was gathered and state which dimensions are uncovered. A target price built on half the evidence is worse than no target price |
| `stock-balance-sheet-reviewer` not validated | Bear scenario cannot be floored → **no Strong Buy / Buy**; cap at `Watch` |
| Any worker `REFUSED` | stop and surface to the user before synthesizing |

A degraded verdict must never be presented in the same voice as a full one. The
Verdict line carries the qualifier, e.g. `Buy (DEGRADED — industry dimension
uncovered, conviction capped Low)`.

### Concurrency and token budget

- Launch the first wave in **one** Agent batch. Sequential dispatch forfeits the
  parallelism the architecture exists for.
- Max concurrent workers: **6**. Second-wave dispatches wait for the first wave's
  quorum, so peak concurrency is the first wave's size.
- Indicative output-token budget per run (first wave + at most one retry +
  second wave): **Lite ≈ 120k · Standard ≈ 300k · Strict ≈ 500k**. These are
  directional planning figures, not metered limits — the orchestrator cannot read
  its own token meter. Their purpose is to make "Lite" mean something: if a Lite
  run is dispatching six workers plus a second wave, the depth selection was
  wrong.

---

## Part 3 — Run Bundle

Every run writes a bundle to `$TMPDIR/stock-analysis-<ticker>/run/`. Without it
the final report cannot be checked against the evidence it claims to rest on —
a reader has no way to tell a faithful synthesis from an invented one.

```
run/
├── data-manifest.json        # Step 2 output (what was fetched, what is missing)
├── financials.json           # EDGAR XBRL first-hand figures + source tags
├── dispatch-log.json         # owned by dispatch.py: tier, trigger, state, attempts, timings, errors
├── dispatch-log.archetype-1.json   # superseded plan, when an archetype re-dispatch happened
├── workers/
│   ├── stock-business-reviewer.md            # RAW final reply, verbatim, incl. the fence
│   ├── stock-business-reviewer.json          # payload extracted from that reply
│   ├── stock-business-reviewer.attempt1.md   # the FAILED reply, when attempts > 1
│   ├── stock-industry-reviewer.wave2.md      # second-wave reply, when one was dispatched
│   └── ...
├── consolidated.json         # worker_contract.py consolidate output (Step 5a working set)
├── model.json / model-out.json    # valuation driver model + engine output
├── sotp.json / sotp-out.json      # option-dominated names only
├── metrics.json / lint.json       # every stated ratio + the 口径 lint result
├── verdict.json              # the verdict-log entry, before append
└── report.md                 # the rendered report
```

### `dispatch-log.json`

```json
{
  "ticker": "MSFT",
  "depth_mode": "Standard",
  "archetype": "Hyperscaler / Mega-Cap Tech Platform",
  "wave_1_launched_at": "2026-08-19T09:00:00Z",
  "workers": [
    {"worker": "stock-business-reviewer", "tier": 0, "state": "VALIDATED", "status": "OK",
     "attempts": 1, "duration_s": 214, "errors": []},
    {"worker": "stock-management-reviewer", "tier": 1, "trigger": "depth=Standard",
     "state": "VALIDATED", "status": "DEGRADED", "attempts": 2, "duration_s": 402,
     "errors": [{"attempt": 1, "code": "MISSING_BLOCK"}]},
    {"worker": "stock-peer-comparison-reviewer", "tier": 1, "trigger": "depth=Standard",
     "state": "TIMEOUT", "attempts": 2, "duration_s": 600, "errors": []}
  ],
  "wave_2": [
    {"worker": "stock-industry-reviewer", "reason": "share claim vs P-01 conflict",
     "state": "VALIDATED", "status": "OK", "attempts": 1}
  ],
  "not_dispatched": [],
  "quorum": {"tier0_validated": 4, "tier0_required": 4, "verdict_permitted": "full"}
}
```

**Naming is load-bearing.** `<worker>.md` is always the reply the report was built
from; `<worker>.attempt<N>.md` are the superseded ones. The gate requires an
`attempt<N>.md` for every attempt the log claims beyond the first — otherwise
"we retried after a MISSING_BLOCK" is an unverifiable assertion.

### Bundle gate — two stages, fail-closed

The artifacts do not all exist at the same moment, so one gate cannot check them
all. The first version required `verdict.json` at Step 5d-ter, which runs *before*
Step 5f produces a verdict — following the documented order could only fail.

```bash
# Step 5d-ter, before the verdict exists
python3 scripts/finlib/runbundle.py check --run <run> --stage evidence

# after Step 5g, before showing anything to the user
python3 scripts/finlib/runbundle.py check --run <run> --stage publication
```

| Stage | Required files | Question |
|---|---|---|
| `evidence` | `data-manifest.json` · `financials.json` · `dispatch-log.json` · `consolidated.json` · every dispatched worker's reply + payload (both waves) | may I synthesize a verdict from this? |
| `publication` | the above **plus** `metrics.json` · `lint.json` · `verdict.json` (full v3 schema) · `report.md` · `model.json` with a matching digest | may I show this to the user? |

**Every requirement is fail-closed.** Nothing that changes whether the report is
trustworthy is a warning. An absent `lint.json` used to PASS with a note, which
made "the 口径 gate left no evidence it ran" indistinguishable from "it ran and
passed".

Beyond presence, the gate checks that the artifacts **agree with each other**:

| Check | Defect it catches |
|---|---|
| `<worker>.json` equals the payload extracted from `<worker>.md` | a hand-edited extraction lets the report cite findings the worker never returned |
| `consolidated.json` is reproducible by re-running consolidation, compared on **every field** of every finding | a rewritten evidence line, a softened implication, a swapped citation, a downgraded severity — all of which survived an id/severity-only comparison |
| `report.md` carries each finding faithfully: matching severity, the worker's citation `locator`, and the worker's `evidence` and `implication` **verbatim** (`report_audit.py`) | **distortion**. An ID-substring check could only see a *dropped* finding, and a report distorts far more easily than it loses |
| no report block claims a finding absent from `consolidated.json` | a fabricated finding — the mirror image of a dropped one |
| `verdict.json` passes `verdictlog.validate_entry()` **inside the gate** | a publication gate that depended on the caller having remembered to run a separate command |
| `verdict.json` model digest == `sha256(model.json)`, and the digest is **required** at publication | recorded targets that cannot be tied to the model that produced them |
| an `attempt<N>.md` exists for every claimed retry | an unverifiable retry claim |
| log states, attempt counts, tiers, triggers and wave-2 caps are legal | a self-certifying log |
| **the second wave is audited exactly like the first** — terminal state, attempts, duration, `<worker>.wave2.md` + `.json` on disk, contract validity, extraction match, and inclusion in consolidation | wave 2 previously got only a name/reason/cap check, so its findings could bypass the evidence chain entirely |
| one wave-2 entry per worker | two entries made a worker's history ambiguous and hid one of its replies |
| a `.wave2.md` on disk with no wave-2 entry | an unrecorded second-wave dispatch |
| the quorum is **recomputed** from states | a log asserting `full` while a Tier-0 worker timed out |
| a `NOT_DISPATCHED` Tier-1 worker records its non-firing trigger | silence about a skipped worker reads as "it ran" |
| no worker left in `PENDING` / `RUNNING` / `RETURNED` | a mid-flight bundle presented as a finished run |

**A FAIL blocks publication** — same discipline as the 口径 lint gate in Step 5d-bis.

Bundles are scratch artifacts and are not committed. To keep one as a regression
baseline, copy it out of `$TMPDIR` deliberately — see
`outputexample/stock-analysis-lead/README.md`.
