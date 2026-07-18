# Deep Research Trusted Repository Evidence Implementation Plan

**Goal:** Replace declarative repository trust with live Git/filesystem/process verification, add cumulative session budgets and cited-source ceilings, improve multilingual classification, and split the CLI into maintainable modules without regressing Web research or the nine-section report.
**Mode:** Deep
**Architecture:** Preserve `scripts/deep_research.py` as the compatibility CLI and incrementally extract high-risk trust boundaries into `deep_research_lib`, with boundary verification performed only for referenced evidence.
**Tech Stack:** Python 3.14 standard library, `unittest`/`pytest`, Git CLI, ripgrep, MkDocs.
**Repo Discovery:** The repository uses per-skill `unittest` regression wrappers plus repo-level pytest; `CLAUDE.md` requires synchronized skill, rationale, evaluation, and output-example layers.

---

## Scope & Risk

- **Risk:** High — evidence semantics, CLI contracts, and module boundaries change together.
- **In scope:** Repository evidence collection/validation, trusted test replay, session budget ledger, report source filtering/ceiling, multilingual planner, module extraction, all paired documentation/tests.
- **Out of scope:** Cryptographic attestation against a malicious filesystem owner, public-network DDG/WAF reliability, or new third-party dependencies.

## Dependency Graph

Task 1 [blocks: 2, 3, 4, 5]
Task 2 [depends: 1] [blocks: 6]
Task 3 [depends: 1] [blocks: 6]
Task 4 [depends: 1] [blocks: 6]
Task 5 [depends: 1] [blocks: 6]
Task 6 [depends: 2, 3, 4, 5] [blocks: 7]
Task 7 [depends: 6]

Tasks 2–5 are logically independent but execute inline to preserve fix attribution and avoid shared-file conflicts.

## Task 1: Lock every reproduced gap into failing tests

**Files:**

- `skills/deep-research/scripts/tests/test_repository_integrity.py` [New]
- `skills/deep-research/scripts/tests/test_session_budget.py` [New]
- `skills/deep-research/scripts/tests/test_evidence_integrity.py` [Existing]
- `skills/deep-research/scripts/tests/test_subcommand_smoke.py` [Existing]

**Steps:**

- [x] Add temporary-Git-repository fixtures.
- [x] Assert dirty matches are unpinned and clean matches resolve to the real blob.
- [x] Assert nonexistent commit/path, mismatched line/excerpt/subject, and hand-written passing status are rejected.
- [x] Assert `run-test` plus explicit replay is the only runtime-High path.
- [x] Assert cumulative budget reservations, cited-only Sources, source ceilings, and Chinese classifier decisions.
- [x] Run only the new tests and capture the expected failures.

**Verification:**

```text
[command] rtk python3 -m unittest skills/deep-research/scripts/tests/test_repository_integrity.py skills/deep-research/scripts/tests/test_session_budget.py
Expected: failures proving the current trust and budget gaps.
```

**Rollback:** Remove only the new tests if their assumptions contradict the approved design; do not change production code.

## Task 2: Implement repository and test execution verification

**Files:**

- `skills/deep-research/scripts/deep_research.py` [Existing]
- `skills/deep-research/scripts/deep_research_lib/repository.py` [New]
- `skills/deep-research/scripts/tests/test_repository_integrity.py` [New]

**Steps:**

- [x] Add Git-root, clean-path, commit existence, blob read, subject read, and line/excerpt comparison helpers.
- [x] Change `search-codebase` to pin only clean tracked paths and mark dirty/untracked matches `working-tree-unpinned`.
- [x] Add `run-test` with argv execution, bounded timeout, output hashes, and structured receipt.
- [x] Require explicit test replay during validation for test evidence to become verified.
- [x] Keep subprocess execution on argv arrays with `shell=False`.

**Verification:**

```text
[command] rtk python3 -m unittest skills/deep-research/scripts/tests/test_repository_integrity.py
Expected: all repository and replay tests pass.
```

**Rollback:** Revert repository helpers and handler changes together; the pre-change tests remain as evidence that rollback reopens the defect.

## Task 3: Implement the persistent session budget ledger

**Files:**

- `skills/deep-research/scripts/deep_research.py` [Existing]
- `skills/deep-research/scripts/deep_research_lib/session.py` [New]
- `skills/deep-research/scripts/tests/test_session_budget.py` [New]
- `skills/deep-research/scripts/tests/test_subcommand_smoke.py` [Existing]

**Steps:**

- [x] Initialize a versioned ledger from `plan --output`.
- [x] Add locked, atomic reservation and report-source recording operations.
- [x] Require `--session` for retrieval, content extraction, and reporting.
- [x] Derive mode from the session and reject conflicting explicit modes.
- [x] Ensure attempts count before network execution and over-budget work does not start.

**Verification:**

```text
[command] rtk python3 -m unittest skills/deep-research/scripts/tests/test_session_budget.py skills/deep-research/scripts/tests/test_subcommand_smoke.py
Expected: cumulative limits and all output-writing CLI paths pass.
```

**Rollback:** Remove session flags and ledger calls as one phase; do not leave documentation claiming session-wide enforcement.

## Task 4: Enforce cited-only report sources and source ceilings

**Files:**

- `skills/deep-research/scripts/deep_research.py` [Existing]
- `skills/deep-research/scripts/deep_research_lib/reporting.py` [New]
- `skills/deep-research/scripts/tests/test_evidence_integrity.py` [Existing]
- `skills/deep-research/scripts/tests/test_session_budget.py` [New]

**Steps:**

- [x] Derive the unique evidence-key set from validated substantive sections.
- [x] Filter Web and repository artifacts before numbering and rendering.
- [x] Reject reports whose verified cited evidence exceeds `report_sources_max`.
- [x] Record the accepted count in the session ledger.

**Verification:**

```text
[command] rtk python3 -m unittest skills/deep-research/scripts/tests/test_evidence_integrity.py skills/deep-research/scripts/tests/test_session_budget.py
Expected: unused inputs are absent and Quick rejects 9 cited sources.
```

**Rollback:** Revert filtering and ceiling changes together to keep citation maps internally consistent.

## Task 5: Expand multilingual planner behavior

**Files:**

- `skills/deep-research/scripts/deep_research.py` [Existing]
- `skills/deep-research/scripts/deep_research_lib/planning.py` [New]
- `skills/deep-research/scripts/tests/test_evidence_integrity.py` [Existing]
- `skills/deep-research/scripts/tests/test_golden_scenarios.py` [Existing]

**Steps:**

- [x] Add Chinese and expanded English signal groups for repository, external, deep, comparison, security, and multi-provider intent.
- [x] Preserve explicit user overrides.
- [x] Add the two reported Chinese requests as executable decisions.

**Verification:**

```text
[command] rtk python3 -m unittest skills/deep-research/scripts/tests/test_evidence_integrity.py skills/deep-research/scripts/tests/test_golden_scenarios.py
Expected: Chinese repository → codebase and Chinese cloud-security comparison → deep.
```

**Rollback:** Revert signal tables without changing explicit override behavior.

## Task 6: Extract the high-risk responsibility boundaries

**Files:**

- `skills/deep-research/scripts/deep_research.py` [Existing]
- `skills/deep-research/scripts/deep_research_lib/__init__.py` [New]
- `skills/deep-research/scripts/deep_research_lib/planning.py` [New]
- `skills/deep-research/scripts/deep_research_lib/session.py` [New]
- `skills/deep-research/scripts/deep_research_lib/repository.py` [New]
- `skills/deep-research/scripts/deep_research_lib/reporting.py` [New]
- `skills/deep-research/scripts/tests/test_skill_contract.py` [Existing]

**Steps:**

- [x] Extract planning/classification, repository/process verification, session state, and cited-source selection by responsibility.
- [x] Preserve the compatibility API used by existing dynamic-import tests.
- [x] Keep Web retrieval, validation orchestration, report rendering, and CLI handlers in the existing entry point to limit this trust-boundary change set.
- [x] Run the focused and full regressions after the extraction boundaries.

Further extraction of legacy Web/validation/rendering code remains a
maintainability follow-up, not a prerequisite for the evidence and budget
closures in this plan.

**Verification:**

```text
[command] rtk bash skills/deep-research/scripts/run_regression.sh
Expected: every pre-existing and new test passes through the compatibility entry point.
```

**Rollback:** Revert one module extraction at a time; exported interfaces keep the previous implementation callable during rollback.

## Task 7: Synchronize all skill layers and perform final validation

**Files:**

- `skills/deep-research/SKILL.md` [Existing]
- `skills/deep-research/references/output-contract-template.md` [Existing]
- `skills/deep-research/references/hallucination-and-verification.md` [Existing]
- `skills/deep-research/references/research-patterns.md` [Existing]
- `skills/deep-research/scripts/tests/COVERAGE.md` [Existing]
- `rationale/deep-research/design.md` [Existing]
- `rationale/deep-research/design.zh-CN.md` [Existing]
- `evaluate/deep-research-skill-eval-report.md` [Existing]
- `evaluate/deep-research-skill-eval-report.zh-CN.md` [Existing]
- `outputexample/deep-research/evidence-verified-codebase-report.md` [Existing]

**Steps:**

- [x] Document the Git/filesystem/process trust boundaries, replay safety, and session semantics.
- [x] Replace “per session” ambiguity with the ledger-backed definition.
- [x] Update the codebase report example to include real provenance fields.
- [x] Update behavioral coverage counts after the final regression.
- [x] Run regression, pytest, skill validation, compile, diff checks, conflict scans, and MkDocs.

**Verification:**

```text
[command] rtk bash skills/deep-research/scripts/run_regression.sh
[command] rtk python3 -m pytest skills/deep-research/scripts/tests -q
[command] rtk python3 /Users/john/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/deep-research
[command] rtk python3 -m compileall -q skills/deep-research/scripts
[command] rtk git diff --check
[command] rtk mkdocs build
Expected: all commands pass except any explicitly identified repository-baseline strict-link warnings.
```

**Rollback:** Documentation and examples revert with the behavior phase they describe; never leave claims stronger than executable enforcement.

## Plan Review

**Status:** Approved

**Blocking Issues:** None.

**Non-Blocking Notes:**

- Test replay proves execution but not semantic adequacy; the report exposes argv and result for human review.
- Tasks 2–5 share the current monolith, so inline sequential execution is safer than nominal parallel execution.

**Scorecard:** B: 6/6 | N: 7/7 | SB: 6/6
**Overall:** PASS

## Execution Handoff

Plan saved to `docs/plans/2026-07-18-deep-research-trusted-repository-evidence.md`.

The user requested immediate continuation. Execution proceeds inline in this session with validation checkpoints; sub-agent execution is not used because delegation was not authorized.
