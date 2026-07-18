# Design: Deep Research Evidence Integrity

## 1. Context

- **Problem / Purpose**: The skill documents mandatory extraction, confidence, budget, and reporting rules, but its CLI does not enforce them end to end. The report template, reference contract, implementation, fixtures, and tests also disagree.
- **Who is affected**: Agents using `deep-research`, maintainers reviewing research quality, and readers relying on confidence labels and source notes.
- **Success criteria**: One nine-section contract is shared by documentation and code; web findings trace to successfully extracted supporting text; pure codebase findings use first-class repository evidence; confidence, budget, mode, and degradation decisions are executable and behavior-tested.

## 2. Constraints And Compatibility

- Keep the existing dependency-free Python CLI and `unittest` regression shape.
- Preserve existing retrieval/result fields when they remain meaningful, but do not treat legacy URL-only citations as verified evidence.
- Require extracted content only for `web` and `hybrid` research. Require repository evidence for `codebase` and `hybrid` research.
- Keep every report at exactly nine top-level sections. Quick mode may shorten a section, not omit it.
- Use conservative source preclassification. Domain heuristics are hints; explicit T1–T5 assessment records sponsorship, methodology, and classification basis.
- Do not add network-dependent regression tests.
- Updating the example PDF is out of scope; add a text example that exercises the new codebase evidence contract instead.

## 3. Approaches Considered

### Option A: Documentation-only reconciliation

Unify wording and leave the CLI unchanged. This has low migration cost but cannot prove extraction or enforce budgets, so it does not address the main integrity defects.

### Option B: Compatibility shim around the current CLI

Add `--content` flags and more report headings while retaining citation-only findings. This is less disruptive, but a URL can still be cited without claim-support evidence and behavioral fixtures remain detached from executable decisions.

### Option C: Unified plan and evidence state machine

Add deterministic request planning, bounded execution, a typed evidence bundle, automatic report validation, effective-confidence assessment, and one report renderer. This changes more code but directly closes every reviewed gap and provides stable seams for behavior tests.

**Chosen**: Option C. Decomposing mode selection, evidence validation, confidence assessment, degradation, and rendering prevents a single documentation rule from drifting independently.

## 4. Chosen Approach

Use a `Standard` design with one executable model:

1. `plan` classifies research kind and mode and returns fixed budgets.
2. Retrieval and extraction enforce those budgets.
3. Findings cite typed evidence, not bare URLs.
4. `validate` checks web excerpts against extracted content and repository references against a code-evidence artifact.
5. `report` always invokes the same validation path, computes effective confidence and degradation, then renders the canonical nine sections.

## 5. Architecture / Components / Flow

### Research plan

Input request plus optional explicit mode becomes:

- `research_kind`: `web | codebase | hybrid`
- `mode`: `quick | standard | deep`
- retrieval and extraction ceilings
- whether web content and/or repository evidence are required

### Evidence contracts

Web evidence is a finding-level object with `kind=web`, URL, and an exact supporting excerpt. Validation requires the URL in retrieval results, a successful content item, and the excerpt in extracted page text.

Repository evidence is collected in a structured artifact with stable IDs:

- `code`: path, line, and excerpt
- `commit`: commit identifier and subject
- `test`: command, status, and output summary

Findings reference those IDs. This keeps code lines, commits, and test runs first-class without inventing web URLs.

### Confidence

A requested label is never trusted directly. Validation emits an effective label:

- A narrow single fact may be `High` with one T1 primary web source whose content and excerpt are verified.
- A direct codebase fact may be `High` with pinned code evidence; a runtime-behavior claim additionally needs passing test evidence.
- Other `High` claims require at least two independent verified evidence units and one primary unit.
- Missing support downgrades the finding or excludes it when no usable evidence remains.

### Degradation

- `Full`: every included finding satisfies its requested confidence and all required inputs were processed.
- `Partial`: usable findings remain, but at least one finding is downgraded, a non-critical extraction failed, or an evidence target is incomplete.
- `Blocked`: required evidence input is absent, no finding has usable support, or budget exhaustion prevents the core evidence chain.

## 6. Failure Handling And Operational Notes

- Reject query counts above the selected mode ceiling during argument parsing, including the global 50-call ceiling.
- Cap default extraction to the selected mode budget and reject a larger explicit limit.
- Produce machine-readable validation issues with severity, finding index, and effective confidence.
- Do not write a normal report when required evidence artifacts are absent. When artifacts exist but evidence is incomplete, write an honestly degraded nine-section report.
- Keep source dates as `unknown` when retrieval does not provide them.

## 7. Validation And Testing

- Replace fixture self-assertions with calls to the real planner and degradation/confidence functions.
- Assert the exact ordered nine headings, not a partial heading subset.
- Add negative tests for missing content, failed extraction, excerpt mismatch, URL-only legacy citations, 51 queries, per-mode limits, and report auto-validation.
- Add pure codebase and hybrid tests using code, commit, and test evidence without forced URLs.
- Add conservative source-quality tests for `docs.*`, `.edu`, tier distribution, sponsorship, and methodology notes.
- Run the per-skill regression, repository pytest target, skill quick validation, syntax compilation, and `git diff --check`.

## 8. Open Questions / Risks

- Exact excerpt matching is intentionally strict. Normalized whitespace and case folding reduce formatting noise, but paraphrases still require the agent to include a source excerpt.
- Existing user-authored findings files using only `citations` will validate as unverified. The report explains the migration rather than silently accepting them.
- Source tier inference remains provisional until an agent supplies explicit metadata; the report must expose the basis and unknown fields.

## 9. Approval And Handoff

- **Approval status**: Approved by the user’s explicit request to implement the seven prioritized review recommendations.
- **Design doc status**: Saved at this path.
- **Next step**: Use `writing-plans`, then execute the verified plan in the current session.
