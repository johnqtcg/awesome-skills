# Deep Research Complete Runtime Code-Set Implementation Plan

**Goal:** Make runtime High depend on one clean host receipt bound to every
cited code item from one pinned Git snapshot, and add a safe snapshot metadata
helper for receipt authors.
**Mode:** Standard
**Architecture:** Confidence validation treats the finding's cited code as one
atomic evidence set. A read-only CLI exposes repository identity; host tools
continue to own test execution and receipt attestation.
**Tech Stack:** Python standard library, unittest/pytest, Git CLI, Markdown.
**Repo Discovery:** Existing verifier, CLI/parser, repository fixture tests,
frontmatter permissions, five-layer documentation policy, and dirty worktree
were inspected.

---

## Scope And Risk

- **Risk:** Medium-high — tightens runtime confidence semantics and adds a
  public read-only CLI command.
- **In scope:** Complete code-set binding, one-receipt coverage, same-snapshot
  enforcement, snapshot CLI, permission/document updates, negative regressions.
- **Out of scope:** Cryptographic receipts, semantic coverage inference, test
  execution, and preapproval of additional build tools.

## Dependency Graph

Task 1 [blocks: 2, 3]
Task 2 [depends: 1] [blocks: 4]
Task 3 [depends: 1] [blocks: 4]
Task 4 [depends: 2, 3] [blocks: 5]
Task 5 [depends: 4]

## Task 1: Add failing behavioral tests

**Files:**

- `skills/deep-research/scripts/tests/test_repository_integrity.py` [Existing]
- `skills/deep-research/scripts/tests/test_subcommand_smoke.py` [Existing]
- `skills/deep-research/scripts/tests/test_skill_contract.py` [Existing]

**Steps:**

- [x] Reproduce pinned plus unpinned code incorrectly reaching High.
- [x] Prove separate receipts cannot collectively cover one finding.
- [x] Prove pinned code from multiple commits cannot reach High.
- [x] Specify clean/dirty/non-repository snapshot CLI behavior.
- [x] Extend parser and permission drift guards.

**Verification:**

```text
[command] rtk python3 -m unittest discover -s skills/deep-research/scripts/tests -p 'test_repository_integrity.py' -v
Expected: new runtime and snapshot assertions fail before implementation.
```

## Task 2: Enforce complete runtime evidence binding

**Files:**

- `skills/deep-research/scripts/deep_research.py` [Existing]

**Steps:**

- [x] Collect all cited verified code items before checking pinned state.
- [x] Reject unresolved, unpinned, or mixed-commit code sets.
- [x] Require one receipt to cover the finding and every code ID.
- [x] Require that receipt to name every code path and match the shared
  snapshot.
- [x] Preserve explicit, deduplicated downgrade reasons.

**Verification:** Focused repository-integrity tests pass.

## Task 3: Add read-only repository snapshot command

**Files:**

- `skills/deep-research/scripts/deep_research_lib/repository.py` [Existing]
- `skills/deep-research/scripts/deep_research.py` [Existing]

**Steps:**

- [x] Add versioned HEAD/tree/dirty snapshot collection.
- [x] Add `snapshot-codebase --root --output`.
- [x] Fail closed for non-repositories and unborn HEAD.
- [x] Reject output paths inside the measured repository.
- [x] Confirm the command never runs test argv or mutates Git.

**Verification:** Clean and dirty fixture snapshots match direct Git results.

## Task 4: Synchronize contracts and permissions

**Files:**

- `skills/deep-research/SKILL.md` [Existing]
- `skills/deep-research/references/test-receipt-schema.md` [Existing]
- `skills/deep-research/references/hallucination-and-verification.md` [Existing]
- `skills/deep-research/references/output-contract-template.md` [Existing]
- `skills/deep-research/references/research-patterns.md` [Existing]
- `skills/deep-research/scripts/tests/COVERAGE.md` [Existing]
- `rationale/deep-research/design.md` [Existing]
- `rationale/deep-research/design.zh-CN.md` [Existing]
- `evaluate/deep-research-skill-eval-report.md` [Existing]
- `evaluate/deep-research-skill-eval-report.zh-CN.md` [Existing]
- `bestpractice/Advanced.md` [Existing]
- `bestpractice/进阶篇.md` [Existing]

**Steps:**

- [x] Add `Write` and the narrow snapshot helper to `allowed-tools`.
- [x] Document complete code-set and one-receipt semantics.
- [x] State that the helper supplies identity only, not execution proof.
- [x] State that non-preapproved frameworks require normal host authorization.
- [x] Keep English/Chinese layers aligned.

**Verification:** Contract tests and skill quick validation pass.

## Task 5: Full validation

**Files:**

- `skills/deep-research/scripts/run_regression.sh` [Existing]

**Steps:**

- [x] Run the complete regression and pytest suite: 286 passed.
- [x] Compile with an external pycache.
- [x] Run diff/conflict checks and MkDocs.
- [x] Update coverage/evaluation counts to observed results.

**Verification:**

```text
[command] rtk bash skills/deep-research/scripts/run_regression.sh
[command] rtk python3 -m pytest skills/deep-research/scripts/tests -q
[command] rtk git diff --check
[command] rtk mkdocs build
Expected: all functional gates pass; only documented baseline warnings remain.
```

## Plan Review

**Status:** Approved by the user's explicit runtime-binding and snapshot-helper
requirements.

**Blocking Issues:** None.

**Residual Boundary:** Host receipts remain programmatic attestations until an
unforgeable execution handle is available.

**Execution Handoff:** Execute inline; sub-agent delegation was not authorized.

## Completion Record

- Regression wrapper: 286/286 passed.
- Pytest: 286/286 passed.
- Skill quick validation: passed.
- Compileall and `git diff --check`: passed.
- MkDocs: built successfully with repository-baseline navigation/link warnings.
