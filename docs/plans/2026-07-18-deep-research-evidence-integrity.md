# Deep Research Evidence Integrity Implementation Plan

**Goal:** Make the `deep-research` documentation, CLI, evidence validation, confidence rules, budgets, and regressions enforce one auditable end-to-end contract.
**Mode:** Standard
**Architecture:** Add a deterministic research planner and typed evidence validation layer, route both `validate` and `report` through it, and render one exact nine-section report. Keep the dependency-free Python and `unittest` architecture.
**Tech Stack:** Python standard library, `unittest`, Bash regression runner, Markdown skill/reference documents.
**Repo Discovery:** The repository is a documentation-and-assets collection; regression-enabled skills use `scripts/run_regression.sh`, `scripts/tests/test_*.py`, and golden JSON fixtures. The target script and all listed skill files were read, and recent commits use Conventional Commits.

---

## Scope & Risk

- **Risk:** Medium. The CLI input contract becomes stricter and existing URL-only findings no longer count as verified.
- **In scope:** The target skill, references, Python helper, regression tests/fixtures, coverage matrix, paired rationale/evaluation notes, and a text output example.
- **Out of scope:** New dependencies, live-web reliability measurement, and rewriting the existing PDF example.
- **Rollback:** Revert the target-file patch as one unit; no persisted user data or external system is changed.

## Task 1: Lock the reviewed failures into executable tests

**Files:**

- `[Existing] skills/deep-research/scripts/tests/test_deep_research.py`
- `[Existing] skills/deep-research/scripts/tests/test_golden_scenarios.py`
- `[Existing] skills/deep-research/scripts/tests/test_skill_contract.py`
- `[Existing] skills/deep-research/scripts/tests/test_subcommand_smoke.py`
- `[Existing] skills/deep-research/scripts/tests/golden/*.json`

**Steps:**

- [ ] Replace fixture-value assertions with calls to the real planner, confidence assessor, and degradation state machine.
- [ ] Add exact ordered nine-heading assertions.
- [ ] Add negative cases for missing/failed content, unsupported excerpts, legacy citations, and mode budget overflow.
- [ ] Add codebase/hybrid evidence cases for code lines, commits, and test runs.

**Verification:**

```text
[command] python3 -m unittest discover -s skills/deep-research/scripts/tests -p 'test_*.py' -v
```

Expected at this checkpoint: the new tests fail for the reviewed gaps.

## Task 2: Implement planning, budgets, evidence validation, and reporting

**Files:**

- `[Existing] skills/deep-research/scripts/deep_research.py`

**Steps:**

- [ ] Add mode budgets and a deterministic `plan` command.
- [ ] Enforce retrieval and extraction limits during parsing/execution.
- [ ] Add conservative T1–T5 source-quality metadata.
- [ ] Add web-content and repository-evidence loaders and validators.
- [ ] Unify confidence and degradation assessment.
- [ ] Route `report` through validation and render the exact nine-section contract.

**Verification:**

```text
[command] python3 -m py_compile skills/deep-research/scripts/deep_research.py
[command] python3 -m unittest skills.deep-research.scripts.tests.test_deep_research
```

## Task 3: Reconcile the normative documentation

**Files:**

- `[Existing] skills/deep-research/SKILL.md`
- `[Existing] skills/deep-research/references/output-contract-template.md`
- `[Existing] skills/deep-research/references/hallucination-and-verification.md`
- `[Existing] skills/deep-research/references/research-patterns.md`

**Steps:**

- [ ] Define one nine-section report contract and one confidence rule.
- [ ] Document conditional web/codebase/hybrid evidence requirements.
- [ ] Document executable mode, budget, validation, and degradation flow.
- [ ] Remove unstable AI-tool rankings and absolute recommendations.

**Verification:**

```text
[command] python3 -m unittest skills.deep-research.scripts.tests.test_skill_contract -v
```

## Task 4: Update coverage artifacts and repository layers

**Files:**

- `[Existing] skills/deep-research/scripts/tests/COVERAGE.md`
- `[Existing] rationale/deep-research/design.md`
- `[Existing] rationale/deep-research/design.zh-CN.md`
- `[Existing] evaluate/deep-research-skill-eval-report.md`
- `[Existing] evaluate/deep-research-skill-eval-report.zh-CN.md`
- `[New] outputexample/deep-research/evidence-verified-codebase-report.md`

**Steps:**

- [ ] Describe the new executable behavior coverage instead of keyword-only coverage.
- [ ] Synchronize the English and Chinese rationale with the evidence model.
- [ ] Add a dated post-evaluation note without rewriting the historical evaluation snapshot.
- [ ] Add a small codebase report example demonstrating non-URL evidence.

**Verification:**

```text
[command] git diff --check
[command] rg -n "evidence|证据|2026-07-18" rationale/deep-research evaluate/deep-research-skill-eval-report* outputexample/deep-research
```

## Task 5: Run full validation and adversarial probes

**Files:**

- `[Existing] skills/deep-research/scripts/run_regression.sh`
- `[Existing] /Users/john/.codex/skills/.system/skill-creator/scripts/quick_validate.py`

**Steps:**

- [ ] Run the complete skill regression suite.
- [ ] Run skill structure validation and repository diff checks.
- [ ] Probe 51-query parsing, report-without-content, and pure-codebase report behavior.
- [ ] Review the final diff for scope, compatibility, and unintentional changes.

**Verification:**

```text
[command] bash skills/deep-research/scripts/run_regression.sh
[command] python3 /Users/john/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/deep-research
[command] git diff --check
```

## Plan Review

**Status:** Approved

**Blocking Issues:** None.

**Non-Blocking Notes:**

- The implementation and documentation tasks both touch contract concepts, but their write targets do not overlap.
- The CLI compatibility break is explicit and covered by migration-facing validation messages.

**Scorecard:** B: 6/6 | N: 7/7 | SB: 6/6
**Overall:** PASS

## Execution Handoff

Plan saved to `docs/plans/2026-07-18-deep-research-evidence-integrity.md`. The required skills are available in this session, so execution proceeds inline with checkpoints and no subagent dependency.
