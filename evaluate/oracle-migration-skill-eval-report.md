# oracle-migration Skill Evaluation Report

> **Method**: skill-creator A/B testing
> **Date**: 2026-04-18
> **Subject**: `skills/oracle-migration/` — Oracle Database schema migration safety reviewer and DDL generator

---

The `oracle-migration` skill covers DDL auto-commit semantics, `DDL_LOCK_TIMEOUT` configuration, large-table online redefinition via `DBMS_REDEFINITION`, the `ENABLE NOVALIDATE` constraint pattern, global index invalidation prevention, and the mandatory §9 output contract. The evaluation ran three A/B scenarios (six real model calls) scoring 23 assertions against both with-skill and without-skill responses, with actual token usage recorded for each run.

The most important finding cuts against the expected narrative: the baseline model already handles common Oracle safety patterns — FK constraint risks, ORA-02298 orphan rows, and ENABLE NOVALIDATE two-step — with solid accuracy. The skill's differentiated value is concentrated in three areas: enforcing `DDL_LOCK_TIMEOUT` (missed in 3/3 baseline runs), correctly classifying `NUMBER` precision widening as a metadata operation rather than a table rewrite, and guaranteeing a structured scorecard, rollback plan, and uncovered-risk section regardless of time pressure or incomplete context.

---

## 1. Skill Overview

**Core files:**

| File | Lines | Purpose |
|------|-------|---------|
| `SKILL.md` | ~352 | Main framework: depth levels, 4-stage gate, 12-item scorecard, §9 output contract |
| `references/oracle-ddl-lock-matrix.md` | ~154 | DDL × lock behavior matrix; covers metadata ops, full rewrites, `DBMS_REDEFINITION` trigger conditions |
| `references/large-table-migration.md` | ~303 | Deep-mode guide: `DBMS_REDEFINITION` 7-step workflow, CAN/START/SYNC/FINISH/ABORT, UNDO/TEMP sizing |
| `references/migration-anti-examples.md` | ~174 | Extended anti-examples AE-1 through AE-N; AE-1 covers the DDL_LOCK_TIMEOUT omission pattern |

**Key safety rules the skill enforces:**

- Set `ALTER SESSION SET DDL_LOCK_TIMEOUT = N` before every DDL statement (Critical; baseline omits this in all three scenarios)
- Classify column modifications against the DDL lock matrix before recommending a migration path — widening `NUMBER` precision is a metadata operation, not a table rewrite
- Use `ENABLE NOVALIDATE` + `VALIDATE` two-step for adding NOT NULL or FK constraints on populated tables
- Recommend `CREATE INDEX ... ONLINE` with an explicit Enterprise Edition prerequisite note
- Produce a §9 output contract on every run: context collection table (§9.1), per-DDL risk scorecard (§9.8), uncovered-risk section (§9.9), and rollback SQL
- Formally declare a degraded mode level (MINIMAL / Degraded) when required context is absent, and list blocking unknowns in §9.9 rather than issuing conditional advice

---

## 2. Test Design

### 2.1 Scenarios

| # | Name | Environment | Core challenge | Expected outcome |
|---|------|-------------|----------------|-----------------|
| 0 | Standard DDL review | Oracle 19c EE, `orders` ~5M rows, Flyway-managed, no maintenance window | Three DDL statements in one session; no `DDL_LOCK_TIMEOUT` preset; NOT NULL modify on a live table | Flags missing `DDL_LOCK_TIMEOUT`, recommends `ENABLE NOVALIDATE` + `ONLINE` index, generates full §9 scorecard |
| 1 | Large-table column type change | Oracle 19c EE, `events` ~80M rows, no maintenance window | User requests `NUMBER(10) → NUMBER(18)` on a deep table | Correctly classifies as metadata operation (not `DBMS_REDEFINITION`), sets `DDL_LOCK_TIMEOUT`, full index-status and rollback plan |
| 2 | Degraded mode — no context | Version unknown, row count unknown; question asked in Chinese | FK constraint addition with bare SQL and no environment context | Declares MINIMAL/Degraded mode, refuses unconditional "safe" claim, puts version and size unknowns as blocking gaps in §9.9 |

### 2.2 Assertion Matrix (23 total)

**Scenario 0 — Standard DDL review (9 assertions)**

| ID | Assertion | Without Skill | With Skill |
|----|-----------|:-------------:|:----------:|
| A1 | Complete context collection table (§9.1, including Edition and RAC fields) | PARTIAL | PASS |
| A2 | Explicitly flags missing `DDL_LOCK_TIMEOUT` as an ORA-00054 risk | FAIL | PASS |
| A3 | `MODIFY NOT NULL` identified as ORA-02296 risk if existing NULLs present | PASS | PASS |
| A4 | Recommends `ENABLE NOVALIDATE` + `VALIDATE` two-step pattern | PARTIAL | PASS |
| A5 | `CREATE INDEX` recommends `ONLINE` option with EE prerequisite note | PARTIAL | PASS |
| A6 | DDL auto-commit risk explained (uncommitted DML will be implicitly committed) | PARTIAL | PASS |
| A7 | Manual rollback SQL provided for each DDL statement | PARTIAL | PASS |
| A8 | Three-tier scorecard present (Critical / Standard / Hygiene) | FAIL | PASS |
| A9 | §9.9 Uncovered Risks section present | FAIL | PASS |

**Scenario 0 result**: Without Skill 3.5/9 weighted (1 PASS + 5 PARTIAL + 3 FAIL) | With Skill **9/9**

*Token usage*: Without Skill 14,195 tokens (0 tool calls) | With Skill 41,080 tokens (9 tool calls, including SKILL.md + two reference files)

**Scenario 1 — Large-table column type change (8 assertions)**

| ID | Assertion | Without Skill | With Skill |
|----|-----------|:-------------:|:----------:|
| B1 | Table formally classified at Deep depth | FAIL | PASS |
| B2 | `NUMBER(10→18)` correctly identified as a metadata operation (Oracle variable-length internal storage; no table rewrite needed) | FAIL | PASS |
| B3 | Complete, executable migration SQL provided | PARTIAL | PASS |
| B4 | Index status verification included (confirm `STATUS = VALID` after DDL) | PARTIAL | PASS |
| B5 | UNDO/TEMP tablespace assessment included | PASS | PASS |
| B6 | Per-phase manual rollback plan provided (including `ABORT_REDEF_TABLE`) | PASS | PASS |
| B7 | `DDL_LOCK_TIMEOUT` set before each DDL statement | FAIL | PASS |
| B8 | `DBMS_STATS` collection plan included | PASS | PASS |

**Scenario 1 result**: Without Skill 4/8 weighted (3 PASS + 2 PARTIAL + 3 FAIL) | With Skill **8/8**

*Token usage*: Without Skill 16,288 tokens (0 tool calls) | With Skill 41,362 tokens (9 tool calls, all three reference files loaded)

**Scenario 2 — Degraded mode, no context (6 assertions)**

| ID | Assertion | Without Skill | With Skill |
|----|-----------|:-------------:|:----------:|
| C1 | Degraded mode formally declared (not just implicit hedging) | FAIL | PASS |
| C2 | Refuses to unconditionally call the migration "safe"; uses conditional language | PASS | PASS |
| C3 | FK index absence flagged as a parent-table DML contention and deadlock risk | PASS | PASS |
| C4 | `ENABLE` keyword identified as triggering immediate full-table validation → ORA-02298 orphan risk | PASS | PASS |
| C5 | `ENABLE NOVALIDATE` + `VALIDATE` two-step recommended | PASS | PASS |
| C6 | §9.9 lists unknown version and unknown row count as blocking gaps | FAIL | PASS |

**Scenario 2 result**: Without Skill 4/6 weighted (4 PASS + 0 PARTIAL + 2 FAIL) | With Skill **6/6**

*Token usage*: Without Skill 13,266 tokens (0 tool calls) | With Skill 33,754 tokens (7 tool calls, SKILL.md + oracle-ddl-lock-matrix.md)

---

## 3. Results

### 3.1 Overall

| Configuration | PASS | PARTIAL | FAIL | Weighted pass rate* |
|---------------|:----:|:-------:|:----:|:-------------------:|
| **With Skill** | **23** | 0 | 0 | **100%** |
| Without Skill | 8 | 7 | 8 | 50% |

**Delta: +50 percentage points (weighted)**

*Weighted formula: PASS = 1.0, PARTIAL = 0.5, FAIL = 0. Weighted score = (PASS + PARTIAL × 0.5) / 23.*

### 3.2 By scenario

| Scenario | Without Skill (weighted) | With Skill | Points lost |
|----------|:------------------------:|:----------:|-------------|
| S0 Standard DDL review (9 assertions) | 3.5/9 (39%) | **9/9** | A2 DDL_LOCK_TIMEOUT, A8 scorecard, A9 §9.9, A1/A4/A5/A6/A7 partial |
| S1 Large-table type change (8 assertions) | 4/8 (50%) | **8/8** | B1 depth classification, B2 metadata-op misclassification, B7 DDL_LOCK_TIMEOUT, B3/B4 partial |
| S2 Degraded mode (6 assertions) | 4/6 (67%) | **6/6** | C1 degraded mode declaration, C6 §9.9 blocking gaps |

### 3.3 Where the skill makes a difference

| Skill contribution | Evidence |
|-------------------|----------|
| **`DDL_LOCK_TIMEOUT` enforcement** | Baseline omitted this parameter in all three scenarios across all DDL-containing sessions. The skill flags it as a Critical item via §5.1 item 2 and AE-1. Without it, any DDL that encounters a long-running transaction holding a row lock fails immediately with ORA-00054 — no retry. |
| **Precise DDL behavior classification** | S1: baseline recommended a full `DBMS_REDEFINITION` workflow for a `NUMBER(10→18)` widening — technically safe, but unnecessary. Oracle 19c handles this as a metadata-only operation. The skill's DDL lock matrix identified it as a WARN-level `MODIFY column (widen)`, producing a simpler and correct path. |
| **§9 output contract completeness** | Baseline never produced a scorecard, §9.9 uncovered-risk section, or structured context collection table. The skill generates all three on every run, converting a narrative review into a blockable engineering judgment (e.g., `5/12 — Critical 1/3 — FAIL`). |
| **Formal degraded mode protocol** | S2: baseline gave useful conditional advice but without a named degraded level. The skill names the level (MINIMAL), and converts unknown version and row count into structured §9.9 blocking gaps — not "please provide more information," but a formal "cannot issue a safe judgment under these conditions." |
| **ORA error code precision** | The skill references ORA-00054, ORA-02296, ORA-02298, and ORA-30036 precisely. The baseline cited ORA-02296 and ORA-02298 correctly in S0/S2, but never mentioned ORA-00054 — the most operationally common DDL failure on a live production database. |
| **Scorecard as an engineering gate** | Each skill run produces a `X/12 — Critical Y/3 — PASS/FAIL` judgment. This format can block a deployment pipeline. The baseline's narrative output cannot. |

### 3.4 Where the baseline is already strong

The baseline model handles these Oracle patterns correctly without the skill:

- ORA-02296 (NOT NULL enforcement when existing NULLs are present) — correctly identified in S0
- ORA-02298 (FK VALIDATE encountering orphan rows) — correctly identified in S2
- `ENABLE NOVALIDATE` + `VALIDATE` two-step pattern — full SQL provided in S2
- FK index absence → parent-table DML lock contention and deadlock risk — correctly identified in S2 including DELETE scenarios
- `DBMS_REDEFINITION` overall workflow (CAN_REDEF → START → SYNC → FINISH → ABORT) — complete steps in S1
- UNDO/TEMP tablespace assessment — correctly raised in S1

The skill's core value is not filling an Oracle knowledge gap — the baseline is technically solid on common patterns. It is enforcing `DDL_LOCK_TIMEOUT` (a consistently missed Oracle-specific safety parameter), providing accurate DDL behavior classification for edge cases, and guaranteeing structural output completeness under time pressure or incomplete context.

---

## 4. Token Cost Analysis

| Scenario | Without Skill tokens | With Skill tokens | Overhead | Tool calls (with skill) |
|----------|:--------------------:|:-----------------:|:--------:|:-----------------------:|
| S0 Standard (SKILL.md + DDL matrix + anti-examples) | 14,195 | 41,080 | +189% | 9 |
| S1 Deep (all 3 reference files) | 16,288 | 41,362 | +154% | 9 |
| S2 Degraded (SKILL.md + DDL matrix) | 13,266 | 33,754 | +154% | 7 |
| **Average** | **14,583** | **38,732** | **+166%** | **8.3** |

Token counts are full session totals (input + tool calls + tool results + output) measured from the Agent tool's `usage` field.

The +166% average overhead is higher than the mysql-migration evaluation (+51%) for two reasons. First, this evaluation used the Agent tool for file reads, which carries per-call overhead. Second, oracle-migration's reference files are denser — the large-table migration guide is 303 lines of PL/SQL workflow. In production use, where SKILL.md content is injected as a system prompt rather than loaded via tool calls, actual overhead would drop to roughly SKILL.md (~8,000 tokens) plus on-demand reference files, bringing it closer to the mysql-migration range.

---

## 5. Coverage Gaps

| Gap | Severity | Notes |
|-----|----------|-------|
| `DBMS_REDEFINITION` vs direct DDL boundary accuracy | Medium | The evaluation exposed one edge case: `NUMBER` precision widening is a metadata operation. The inverse case — a type change requiring a full table rewrite (e.g., `VARCHAR2 → NUMBER`) — produces a different classification; this boundary has no dedicated golden fixture |
| Partition key column changes | High | Mentioned in §9.9 output but no dedicated evaluation scenario. Partition key type changes are severely restricted in Oracle and typically require `DBMS_REDEFINITION` or partition rebuilds; misclassification would have serious consequences |
| RAC-specific migration coordination | Medium | The input gate asks about RAC status but no scenario validates lock behavior differences in a RAC environment |
| Edition-Based Redefinition (EBR) | Low | In scope per §1 but no evaluation coverage; a niche advanced deployment pattern |
| FK reference chains (child-of-child) | Medium | S2 covers a direct parent-child FK; multi-level FK chains (adding a constraint that cascades through intermediate tables) are not evaluated |
| Flashback Table recovery flow | Low | Reference documentation is complete; no assertion verifies that the model correctly cites it in output |

---

## 6. Conclusion

`oracle-migration` achieved **100% assertion coverage** across six real model runs and 23 scored assertions (weighted pass rate up from 50% to 100%, +50 pp).

The most significant finding is the baseline's strength: the base model scores 67% weighted on the hardest scenario (degraded mode with no context), and correctly handles ORA-02298, ENABLE NOVALIDATE, and FK deadlock risks without any skill guidance. This shifts the interpretation of the skill's value — it is not a knowledge delivery vehicle, but a structural and safety enforcement layer.

**Four contributions where the skill delivers measurable value:**

1. **`DDL_LOCK_TIMEOUT` enforcement** — The baseline omitted this parameter in all three scenarios. On a live production database, a DDL statement without a timeout will fail immediately with ORA-00054 if any long-running transaction holds a conflicting lock. The skill marks this as a Critical check via §5.1 and AE-1, making it impossible to miss.

2. **Accurate DDL behavior classification** — S1 showed the baseline recommending a full `DBMS_REDEFINITION` workflow for a `NUMBER(10→18)` widening. The skill's DDL lock matrix correctly identifies this as a metadata-only `MODIFY column (widen)` operation, producing a simpler, faster, and equally safe migration path.

3. **Structural output contract** — The §9 output contract guarantees a scorecard, rollback SQL, and §9.9 uncovered-risk section on every run. Without the skill, none of these appeared in any baseline response. The scorecard format (`X/12 — Critical Y/3 — PASS/FAIL`) is directly usable as a deployment gate.

4. **Formal degraded mode** — When context is incomplete, the skill assigns a named degraded level (MINIMAL) and converts unknowns into structured blocking gaps in §9.9. The baseline gives useful conditional advice but without a formal framework that prevents an overconfident judgment from slipping through.

**Recommendation: production-ready.** Recommended for all Oracle DDL review workflows, with the highest single-item value in no-maintenance-window production environments where `DDL_LOCK_TIMEOUT` enforcement is the difference between a clean migration and an ORA-00054 failure.
