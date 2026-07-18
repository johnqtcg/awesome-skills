# Deep Research Host-Attested Test Evidence Implementation Plan

**Goal:** Remove all test-command execution from the research helper and make
runtime High depend on a relevant host receipt bound to the same clean Git
snapshot as the cited code.
**Mode:** Deep
**Architecture:** The host owns test execution and permissions. The helper
imports a versioned receipt, performs only Git/filesystem/schema verification,
and renders normalized evidence; session accounting gains cross-platform
locking semantics and an external-tool reservation path.
**Tech Stack:** Python 3.14 standard library, `unittest`/pytest, Git CLI,
ripgrep, MkDocs.
**Repo Discovery:** Existing CLI/parser, repository verifier, session ledger,
278-test regression wrapper, five-layer bilingual documentation policy, and
dirty worktree were inspected.

---

## Scope & Risk

- **Risk:** High — removes public CLI flags/subcommand and changes runtime-High
  evidence semantics.
- **In scope:** Test receipt schema/import/static verification, claim
  relevance, snapshot binding, single-execution workflow, ledger locking and
  external reservations, paired docs/tests.
- **Out of scope:** Cryptographic attestation, automatic semantic coverage
  proof, real Windows CI, and public-network reliability.

## Dependency Graph

Task 1 [blocks: 2, 3, 4]
Task 2 [depends: 1] [blocks: 5]
Task 3 [depends: 1] [blocks: 5]
Task 4 [depends: 1] [blocks: 5]
Task 5 [depends: 2, 3, 4] [blocks: 6]
Task 6 [depends: 5]

Tasks 2–4 touch overlapping contracts and execute inline in causal order even
where their conceptual responsibilities are independent.

## Task 1: Lock the unsafe behavior into failing tests

**Files:**

- `skills/deep-research/scripts/tests/test_repository_integrity.py` [Existing]
- `skills/deep-research/scripts/tests/test_session_budget.py` [Existing]
- `skills/deep-research/scripts/tests/test_subcommand_smoke.py` [Existing]
- `skills/deep-research/scripts/tests/test_skill_contract.py` [Existing]

**Steps:**

- [x] Assert `run-test` and replay flags are absent.
- [x] Add real host-executed receipt fixtures with stable finding/code IDs.
- [x] Reject generic output, missing relevance, snapshot mismatch, dirty state,
  tree mismatch, and tested-path mismatch.
- [x] Add a multiprocess budget race and external reservation smoke test.
- [x] Run focused tests and capture expected failures.

**Verification:**

```text
[command] rtk python3 -m unittest discover -s skills/deep-research/scripts/tests -p 'test_repository_integrity.py' -v
[command] rtk python3 -m unittest discover -s skills/deep-research/scripts/tests -p 'test_session_budget.py' -v
Expected: new assertions fail against the command-proxy/replay implementation.
```

**Rollback:** Remove only the new failing assertions if the approved receipt
contract proves internally inconsistent.

## Task 2: Replace execution with host receipt import

**Files:**

- `skills/deep-research/scripts/deep_research.py` [Existing]
- `skills/deep-research/scripts/deep_research_lib/repository.py` [Existing]
- `skills/deep-research/references/test-receipt-schema.md` [New]

**Steps:**

- [x] Delete `run_test_command`, `cmd_run_test`, replay state, replay flags, and
  the `run-test` parser.
- [x] Add the v2 receipt schema and static Git/tree/path verifier.
- [x] Add `import-test-receipt`, which reads and appends but never executes.
- [x] Preserve normalized verified receipt data for report rendering.

**Verification:**

```text
[command] rtk python3 -m unittest discover -s skills/deep-research/scripts/tests -p 'test_repository_integrity.py' -v
Expected: command-proxy rejection and static receipt-import tests pass.
```

**Rollback:** Restore the previous files together only if the unsafe behavior
is also explicitly restored in documentation; partial rollback is forbidden.

## Task 3: Enforce relevance and snapshot binding

**Files:**

- `skills/deep-research/scripts/deep_research.py` [Existing]
- `skills/deep-research/scripts/deep_research_lib/repository.py` [Existing]
- `skills/deep-research/scripts/tests/test_evidence_integrity.py` [Existing]
- `skills/deep-research/scripts/tests/test_repository_integrity.py` [Existing]

**Steps:**

- [x] Require stable finding IDs for runtime High.
- [x] Require `covers` to include the finding and every cited pinned-code ID.
- [x] Verify receipt commit/tree and tested paths against each covered code
  record.
- [x] Require clean snapshot and approved relevance review for runtime High.
- [x] Downgrade rather than discard otherwise valid audit context.

**Verification:**

```text
[command] rtk python3 -m unittest discover -s skills/deep-research/scripts/tests -p 'test_evidence_integrity.py' -v
[command] rtk python3 -m unittest discover -s skills/deep-research/scripts/tests -p 'test_repository_integrity.py' -v
Expected: only relevant same-snapshot receipts establish runtime High.
```

**Rollback:** Revert confidence and receipt verification together so no schema
is documented without executable enforcement.

## Task 4: Harden ledger boundaries

**Files:**

- `skills/deep-research/scripts/deep_research.py` [Existing]
- `skills/deep-research/scripts/deep_research_lib/session.py` [Existing]
- `skills/deep-research/scripts/tests/test_session_budget.py` [Existing]
- `skills/deep-research/scripts/tests/test_subcommand_smoke.py` [Existing]

**Steps:**

- [x] Add POSIX/Windows lock backends and fail closed without either.
- [x] Refuse accidental session overwrite.
- [x] Add `reserve-budget` for host WebSearch/WebFetch accounting.
- [x] Run a real multiprocess contention test.
- [x] Document non-tamper-proof and non-interception boundaries.

**Verification:**

```text
[command] rtk python3 -m unittest discover -s skills/deep-research/scripts/tests -p 'test_session_budget.py' -v
[command] rtk python3 -m unittest discover -s skills/deep-research/scripts/tests -p 'test_subcommand_smoke.py' -v
Expected: contention preserves the ceiling and external reservations persist.
```

**Rollback:** Revert lock/reservation/parser changes as one phase; never retain
claims stronger than the active backend.

## Task 5: Synchronize contracts and examples

**Files:**

- `skills/deep-research/SKILL.md` [Existing]
- `skills/deep-research/references/output-contract-template.md` [Existing]
- `skills/deep-research/references/hallucination-and-verification.md` [Existing]
- `skills/deep-research/references/research-patterns.md` [Existing]
- `skills/deep-research/references/test-receipt-schema.md` [New]
- `skills/deep-research/scripts/tests/COVERAGE.md` [Existing]
- `rationale/deep-research/design.md` [Existing]
- `rationale/deep-research/design.zh-CN.md` [Existing]
- `evaluate/deep-research-skill-eval-report.md` [Existing]
- `evaluate/deep-research-skill-eval-report.zh-CN.md` [Existing]
- `outputexample/deep-research/evidence-verified-codebase-report.md` [Existing]
- `bestpractice/Advanced.md` [Existing]
- `bestpractice/进阶篇.md` [Existing]

**Steps:**

- [x] Remove command-proxy/replay instructions and narrow `allowed-tools`.
- [x] Document host execution, receipt coverage, snapshot identity, relevance,
  single execution, and ledger limits.
- [x] Update the example and coverage count from final observed results.
- [x] Keep English/Chinese layers aligned.

**Verification:**

```text
[command] rtk python3 -m unittest discover -s skills/deep-research/scripts/tests -p 'test_skill_contract.py' -v
[command] rtk python3 /Users/john/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/deep-research
Expected: contract tests and skill validation pass.
```

**Rollback:** Documentation reverts with its behavior phase; never preserve
unsafe examples after removing the execution interface.

## Task 6: Full validation

**Files:**

- `skills/deep-research/scripts/run_regression.sh` [Existing]

**Steps:**

- [x] Run unittest regression and pytest.
- [x] Compile into an external pycache.
- [x] Run diff/conflict checks and MkDocs.
- [x] Re-run direct probes proving no command proxy and correct snapshot
  downgrade.

**Verification:**

```text
[command] rtk bash skills/deep-research/scripts/run_regression.sh
[command] rtk python3 -m pytest skills/deep-research/scripts/tests -q
[command] rtk env PYTHONPYCACHEPREFIX=/tmp/deep-research-pycache python3 -m compileall -q skills/deep-research/scripts
[command] rtk git diff --check
[command] rtk mkdocs build
Expected: all functional gates pass; only documented repository-baseline MkDocs warnings may remain.
```

**Rollback:** Revert the second-round phase as a unit if a blocking regression
cannot be resolved without weakening the approved security boundary.

## Plan Review

**Status:** Approved

**Blocking Issues:** None.

**Non-Blocking Notes:**

- Host receipts are attestations, not cryptographic proof; the plan states this
  boundary consistently.
- Genuine Windows contention remains an external CI gap; the implementation
  can only unit-test backend selection on this POSIX host.

**Scorecard:** B: 6/6 | N: 7/7 | SB: 6/6
**Overall:** PASS

## Execution Handoff

Plan saved to
`docs/plans/2026-07-18-deep-research-host-attested-test-evidence.md`.

Execution proceeds inline with test-first checkpoints. Sub-agent execution is
not used because delegation was not authorized.
