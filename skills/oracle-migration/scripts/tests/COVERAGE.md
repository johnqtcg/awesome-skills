# oracle-migration Skill — Test Coverage Matrix

> **Counts in this file are generated, not hand-maintained.** Regenerate with
> `python3 scripts/tests/report_coverage.py`. A hand-edited total drifts from reality
> within two changes and then quietly misrepresents the suite.

## 1. What changed and why

An earlier revision reported "92 tests / 100% coverage" while the golden tests asserted
only that certain words appeared inside each fixture's own `expected_feedback` string.
A fixture could satisfy every assertion by confidently restating its own conclusion —
including a wrong one — so the suite protected several incorrect technical claims rather
than catching them. Four of those claims were factual errors about Oracle.

The suite is now built on three layers that can each fail independently:

| Layer | File | What it can catch |
|-------|------|-------------------|
| Structure | `test_skill_contract.py` | missing sections, reference files, line budget |
| **Fact drift** | `test_skill_contract.py::TestFactDrift` | a corrected Oracle fact being reverted |
| **Behaviour** | `test_golden_scenarios.py` | the real checker's output vs per-fixture expectations |
| **Assertion strength** | `scripts/mutation_sweep.py` | assertions that are not load-bearing |
| **Server truth** | `scripts/verify_against_server.sh` | a documented claim the real server contradicts |
| **Harness truth** | `scripts/tests/test_server_harness.py` | the server harness reaching the wrong verdict |

## 2. Deterministic checker (`scripts/lint_migration.py`)

32 checks, declared as data in `CHECKS`. Two registry tests enforce that each one has a
golden fixture that **triggers** it and at least one that does **not** — a check that
never fires is dead, and one that always fires carries no information.

| Code | Severity | Check |
|------|----------|-------|
| ORA001 | critical | DDL without `DDL_LOCK_TIMEOUT` in session |
| ORA002 | critical | `ADD CONSTRAINT` without `ENABLE NOVALIDATE` |
| ORA003 | critical | Partition DDL without `UPDATE INDEXES` |
| ORA004 | warning | Unbounded DML on a large table |
| ORA005 | critical | `ALTER TABLE MOVE` without `ONLINE` |
| ORA006 | warning | `CREATE INDEX` without `ONLINE` |
| ORA007 | critical | `DROP COLUMN` without a pre-DDL data snapshot |
| ORA008 | critical | `DBA_EXTENTS.data_object_id` does not exist |
| ORA009 | critical | Two-statement `RENAME` cutover is not atomic |
| ORA010 | critical | `FLASHBACK TABLE` cannot cross structural DDL |
| ORA011 | critical | `COPY_TABLE_DEPENDENTS` `num_errors` not checked |
| ORA012 | warning | `FINISH_REDEF_TABLE` without `dml_lock_timeout` |
| ORA013 | warning | `NOLOGGING` written as a hint has no effect |
| ORA014 | info | `DBMS_LOCK.SLEEP` requires an explicit grant |
| ORA015 | warning | `MODIFY` column needs empty/rewrite classification |
| ORA016 | critical | Uncommitted DML before DDL is silently committed |
| ORA017 | critical | `TRUNCATE` is irreversible and auto-commits |
| ORA018 | warning | `RENAME COLUMN` breaks deployed application SQL |
| ORA019 | warning | `ALTER INDEX REBUILD` without `ONLINE` |
| ORA020 | warning | `VALIDATE` without a preceding `NOVALIDATE` |
| ORA021 | info | Bulk DML without `DBMS_STATS` refresh |
| ORA022 | critical | Comment claims atomicity across multiple DDL |
| ORA023 | warning | `NOLOGGING` load without a recoverability plan |
| ORA024 | warning | `DROP TABLE PURGE` bypasses the recycle bin |
| ORA025 | info | `SET UNUSED` is cheaper, not reversible |
| ORA026 | critical | `DDL_LOCK_TIMEOUT = 0` is NOWAIT, not protection |
| ORA027 | warning | `DDL_LOCK_TIMEOUT` larger than any sane window |
| ORA028 | critical | `DDL_LOCK_TIMEOUT` value is invalid |
| ORA029 | warning | `DDL_LOCK_TIMEOUT` value cannot be verified statically |
| ORA030 | warning | Normal restore point is not a recovery guarantee |
| ORA031 | warning | Snapshot completeness cannot be confirmed |
| ORA032 | critical | Guaranteed restore point needs Flashback Database (EE) |

### Calibration (false-positive guards)

These are checks the linter deliberately does **not** make. Each is pinned by a
`forbid_findings` entry and by a mutation that re-introduces the false positive:

- `CREATE TABLE` of a new object is excluded from ORA001 — no other session can hold a
  lock on a table that does not exist yet, so ORA-00054 is unreachable.
- `DDL_LOCK_TIMEOUT` is parsed into **four** states, because two were not enough:
  valid / zero (NOWAIT) / invalid / dynamic. `= 0` does not satisfy ORA001, and neither
  does `= -1` — Oracle rejects that statement outright, so the session silently keeps
  the NOWAIT default and the script reads as protected while being *less* protected
  than if the line were absent. A substitution variable is reported as unverified
  rather than rounded up to compliant.
- A CTAS is classified by an **allow-list**, not a deny-list. Only a provably simple
  `SELECT * FROM <one table>` (nothing after the table name) counts as a full copy,
  and only a bare column list counts as a targeted one; everything else — JOIN,
  UNION, DISTINCT, GROUP BY, a function in the select list — is `unverifiable`. The
  previous revision enumerated *restricting* constructs instead and a JOIN walked
  straight through: that list can never be complete, the safe-shape list can.
- The destructive-statement trigger and the coverage logic read the **same** parsed
  column list. A second, narrower regex on the trigger side is how
  `ALTER TABLE t DROP (a, b)` — ordinary documented Oracle syntax — produced *no finding
  at all*: the parser understood the form, the trigger did not.
- A targeted copy must carry every dropped column **and retain a column that survives
  the drop** to key a MERGE on, judged against the whole drop set at once. Per-column
  checking lets the doomed columns vouch for each other: for `DROP (legacy_a, legacy_b)`
  a copy of exactly those two passes when testing either one, and is useless after the
  drop. (Whether the surviving column is genuinely unique is not decidable from the
  text; the finding says so.)
- The two artefact kinds stay distinguishable to the end. A table copy means "MERGE the
  rows back"; a guaranteed restore point means "FLASHBACK DATABASE and lose everything
  since". Collapsing both into one `covered` boolean made the finding tell reviewers to
  MERGE from a copy that did not exist.
- A plain table alias (`FROM orders o`) is not a restricting construct. Requiring an
  empty tail rejected ordinary SQL; the alias is accepted unless it is a SQL keyword,
  which would let `FROM orders WHERE …` pass as "a table aliased WHERE".
- Coverage is judged **against what is being destroyed**. TRUNCATE needs a full
  copy; `DROP COLUMN c` needs only a copy containing `c` — which is exactly the
  targeted pattern `references/large-table-migration.md` recommends, and which an
  earlier revision rejected, so the checker refused its own documented advice.
- `WHERE 1=0` is the interim-table skeleton, the same statement the checker exempts
  from ORA002/ORA006 as "not live" — reading it as a full backup had the checker
  contradict itself. Anything that does not qualify earns ORA031 explaining *why*, so
  the reviewer is not left assuming the checker missed their backup.
- A guaranteed restore point downgrades **only** on confirmed Enterprise Edition.
  Flashback Database is EE-only — which this skill's own licensing matrix already said
  while the checker downgraded on SE2 anyway. An *unknown* edition does not downgrade
  either: SKILL.md Gate 1 says assume SE2, and accepting it produced a safety false
  negative where a destructive statement silently dropped to warning on the strength
  of an unverified edition.
- Only a **guaranteed** restore point counts as a recovery artefact. A normal
  `CREATE RESTORE POINT` is an SCN bookmark bounded by `DB_FLASHBACK_RETENTION_TARGET`
  (Oracle: "a target, not a guarantee") that ages out of the control file on its own, so
  it downgrades nothing and earns ORA030 instead.
- A pre-DDL snapshot only mitigates the table it actually copied. Snapshots are keyed
  by their `FROM` table; a guaranteed restore point is database-wide and covers any
  target. An earlier revision kept one boolean, so a CTAS of `customers` downgraded a
  destructive statement against `orders`. ORA007 also now always *reports* — only its
  severity changes — because suppressing it entirely made a column drop invisible.
- ORA002 softens to a note below the 100,000-row threshold SKILL.md §8 actually states,
  so the checker cannot contradict the scorecard it feeds. Both read the same constant.
- ORA003 is suppressed by `--global-indexes no`. Whether global indexes exist is not
  derivable from SQL, so the default stays conservative: `UPDATE INDEXES` is a no-op
  when unnecessary and prevents ORA-01502 when it is not.
- An irreversible statement preceded by a snapshot or restore point is downgraded, the
  same positive exemption ORA007 honours.
- Constraints and indexes on a table the **same script created** are exempt from ORA002
  and ORA006. An interim table has no concurrent traffic to protect, and without this
  the standard CTAS and DBMS_REDEFINITION patterns — both of which must build a second
  table — light up with findings that are correct about the SQL and wrong about the risk.
- A single-key `UPDATE ... WHERE id = 12345` is not "unbounded DML", and does not
  invalidate table statistics, so neither ORA004 nor ORA021 fires.
- PL/SQL blocks are parsed as one unit. Splitting on the internal `;` separates a call
  from the code that checks its result and makes every intra-block guard invisible.
- A comment that *denies* atomicity ("this is NOT atomic") does not trigger ORA022,
  and a cutover that stages its reverse rename is downgraded from critical to
  warning — reporting the documented safe procedure as a critical defect is how a
  checker teaches people to ignore it.
- Comments and string literals are width-preservingly blanked before SQL matching, so a
  keyword inside a comment cannot trigger a finding — and blanking never fuses adjacent
  tokens.

## 3. Golden fixtures

49 fixtures — 40 defect, 7 good_practice, 1 degradation_scenario, 1 workflow.

Each declares `expect_findings`, `forbid_findings` and `lint_context`; the suite runs the
real checker over `migration_snippet` and compares. `test_no_undeclared_findings` means
an unexpected finding fails too, so a new false positive cannot slip in silently.

| ID | Scenario | Expected findings |
|----|----------|-------------------|
| ORA-001 | Missing `DDL_LOCK_TIMEOUT` | ORA001 |
| ORA-002 | Constraint without `NOVALIDATE` | ORA002 |
| ORA-003 | Column drop with no recovery path | ORA007 |
| ORA-004 | `ALTER TABLE MOVE` without `ONLINE` | ORA005 |
| ORA-005 | Partition DDL without `UPDATE INDEXES` | ORA003 |
| ORA-006 | Monolithic `UPDATE` | ORA004 |
| ORA-007 | Well-formed phased migration | *(none)* |
| ORA-008 | Correct `DBMS_REDEFINITION` workflow | *(none)* |
| ORA-009 | Degraded mode, no context | ORA001, ORA006 |
| ORA-010 | Zero-downtime datatype change (planning) | *(none)* |
| ORA-011 | Widening misreported as a rewrite | ORA015 |
| ORA-012 | `DBA_EXTENTS.data_object_id` — unexecutable | ORA008, ORA014 |
| ORA-013 | Two-`RENAME` cutover called atomic | ORA009, ORA022 |
| ORA-014 | Flashback offered as undo for `DROP COLUMN` | ORA010, ORA007 |
| ORA-015 | `num_errors` printed then ignored | ORA011, ORA012 |
| ORA-016 | `NOLOGGING` inside a hint | ORA013, ORA004 |
| ORA-017 | Widening `VARCHAR2` (false-positive guard) | *(none)* |
| ORA-018 | Uncommitted DML before DDL | ORA016 |
| ORA-019 | `ONLINE` index build proposed on SE2 | ORA006 |
| ORA-020 | `MOVE ONLINE` proposed on 12.1 | ORA005 |
| ORA-021 | `TRUNCATE` with no backup | ORA017 |
| ORA-022 | `RENAME COLUMN` on a live table | ORA018 |
| ORA-023 | Offline rebuild + orphan `VALIDATE` | ORA019, ORA020 |
| ORA-024 | `NOLOGGING` CTAS + `DROP ... PURGE` | ORA023, ORA024 |
| ORA-025 | Session setting across two releases | ORA001 |
| ORA-026 | Correctly planned two-step cutover | *(none critical)* |
| ORA-027 | `DDL_LOCK_TIMEOUT = 0` (NOWAIT) | ORA026, ORA001 |
| ORA-028 | `DDL_LOCK_TIMEOUT = 1000000` | ORA027 |
| ORA-029 | Constraint on a 180-row table | *(note only)* |
| ORA-030 | Irreversible statement with a prior snapshot | ORA017 (warning) |
| ORA-031 | Partition drop, no global indexes | *(none)* |
| ORA-032 | Index + PK on a script-created interim table | *(none)* |
| ORA-033 | `DDL_LOCK_TIMEOUT = -1` (rejected by Oracle) | ORA028, ORA001 |
| ORA-034 | `DDL_LOCK_TIMEOUT = &var` (unverifiable) | ORA029 |
| ORA-035 | Backup of a *different* table + TRUNCATE/DROP COLUMN | ORA017, ORA007 |
| ORA-036 | **Guaranteed** restore point covers any target | ORA007 (warning) |
| ORA-037 | **Normal** restore point is not a guarantee | ORA030, ORA007 |
| ORA-038 | Row-restricted CTAS + TRUNCATE | ORA017, ORA031 |
| ORA-039 | `WHERE 1=0` interim skeleton read as a backup | ORA007, ORA031 |
| ORA-040 | Guaranteed restore point on SE2 | ORA032, ORA007 |
| ORA-041 | Guaranteed restore point, edition unknown | ORA032, ORA007 |
| ORA-042 | Keyed copy of the dropped column (documented pattern) | ORA007 (warning) |
| ORA-043 | JOIN-filtered CTAS read as a full copy | ORA017, ORA031 |
| ORA-044 | Copy of the dropped column with no key | ORA007, ORA031 |
| ORA-045 | Restore-point coverage described as a MERGE | ORA007 (warning) |
| ORA-046 | Plain table alias `FROM orders o` | ORA007 (warning) |
| ORA-047 | `DROP (a, b)` column-list form | ORA007 |
| ORA-048 | Copy of only the doomed columns | ORA007, ORA031 |
| ORA-049 | Multi-column drop with a keyed copy | ORA007 (warning) |

19 fixtures also assert **context-sensitive wording** via `lint_detail_must_contain`,
so the edition/version inputs must change the advice text rather than only the header:
ORA-019 (SE2 → "the online path is not available"), ORA-020 (12.1 → "MOVE ONLINE is
12.2+"), ORA-009 (unknown edition → "confirm the edition first"), ORA-023 (EE →
"available on Enterprise Edition"), ORA-027 (NOWAIT), ORA-029 (below the threshold),
ORA-030 (downgraded from critical), ORA-033 (rejected value), ORA-035
("some *other* table does not count"), ORA-036 (restore point downgrades), ORA-037 ("not a retention promise"), ORA-038 ("copies a subset"), ORA-039
("interim-table skeleton"), ORA-040 (SE2 edition gate), ORA-041 ("assume SE2 when unknown"), ORA-043
("not a plain single-table copy"), ORA-044 ("no key to match the values back"),
ORA-045 ("no per-table copy here to MERGE back from"), ORA-048 ("doomed columns
cannot vouch for each other").

## 4. Fact drift guards

25 parametrised guards pin technical claims that were **wrong in an earlier revision**
and have since been corrected against Oracle documentation. Each asserts the corrected
form is present and, where a specific wrong form existed, that it has not returned.

| Corrected fact | Was |
|----------------|-----|
| `RENAME COLUMN` supported since **9i Release 2** | "not supported before 23ai" (SKILL.md) / "12c+" (matrix) — two wrong answers that contradicted each other |
| `DROP INDEX ... ONLINE` is **12.1+** | "21c+" |
| Narrowing `NUMBER` → **ORA-01440**, datatype class change → **ORA-01439**, both *rejections* not slow rewrites | "MODIFY column type … Rewrites Table: Yes" |
| `DISABLE NOVALIDATE` still takes a brief exclusive lock | lock recorded as "None" |
| `DBA_EXTENTS` has **no** `DATA_OBJECT_ID` column | example selected it; `ORA-00904` at parse time |
| CTAS cutover is **two statements**, each auto-committing | "Atomic swap" |
| `COPY_TABLE_DEPENDENTS` must **halt** on `num_errors` | printed, then proceeded to SYNC and FINISH |
| `FINISH_REDEF_TABLE` must pass `dml_lock_timeout` | omitted |
| `FLASHBACK TABLE ... TO SCN/TIMESTAMP` **cannot cross structural DDL** | offered as the safety net for a column drop |
| `NOLOGGING` is **not a hint** | `/*+ APPEND NOLOGGING */` presented as working |
| Gate 1 requires an exact release (12.1 ≠ 12.2) | "Assume 12c" |
| Rollback is **classified** into six strategies | "rollback SQL provided for every phase" |
| `dml_lock_timeout` defaults to **`NULL`** — no cap, the swap *waits* | "`0` (default), do not wait" — taken from secondary blogs. The two defaults fail in **opposite** directions |
| **Flashback Table** (`TO SCN/TIMESTAMP`) is **EE only**; Flashback Query and Flashback Drop are not | one row reading "Flashback Table / Flashback Query — all editions", which tells an SE2 site it has a recovery path it does not have |

Two whole-corpus sweeps back these up: no asset may tie `RENAME COLUMN` to 23ai, and no
asset may describe a widening as a rewrite. Both exclude *refuting* sentences — a line
may name a wrong claim in order to correct it — and `test_guards_still_catch_a_real_violation`
proves that exclusion has not been widened until the sweeps stopped detecting anything.

## 5. Mutation sweep

`python3 scripts/mutation_sweep.py` — 104 mutations.

| Group | Count | Attacks |
|-------|------:|---------|
| `L01`–`L32` | 32 | one per check: disable it and require a failure |
| `L50`–`L85` | 36 | gating and calibration (session boundary, `CREATE TABLE` exclusion, single-key DML, PL/SQL block parsing, comment blanking, edition/version wording, atomicity-denial exclusion, reverse-rename downgrade, per-statement structural-DDL scope, `DDL_LOCK_TIMEOUT` value parsing, row-count threshold, global-index context, snapshot exemption, script-created-object exemption, four-state timeout classification, per-target snapshot coverage, GUARANTEE-keyword requirement, full-copy snapshot test, restore-point edition gate, allow-list snapshot classification, targeted-column coverage, recovery-key requirement, table-alias tolerance, artefact-specific advice) |
| `F01`–`F16` | 16 | fixture facts and expectation wiring |
| `D01`–`D20` | 20 | corrected facts in `SKILL.md` and the reference documents |

Every mutation reports how many occurrences it replaced. A `SURVIVED` line means the
suite passed with a defect present — treat it as a missing assertion, not a flake.

## 6. Running

```bash
bash scripts/run_regression.sh              # all six stages
SKIP_MUTATION_SWEEP=1 bash scripts/run_regression.sh   # fast path, no sweep
python3 -m pytest scripts/tests -q          # tests only
python3 scripts/mutation_sweep.py --list    # inspect mutations without running
bash scripts/verify_against_server.sh --list          # 14 server probes
ORACLE_TEST_DSN=... ORACLE_ALLOW_DDL=1 \\
  bash scripts/verify_against_server.sh               # run them for real
```

## 7. Known coverage gaps

| Gap | Priority | Rationale |
|-----|----------|-----------|
| No live Oracle instance in CI | High | **Harness exists and its verdict logic is tested** — `scripts/verify_against_server.sh` runs 14 probes that execute the disputed DDL and assert both the successes and the documented *rejections* (ORA-01439/01440/02296/00904). Each probe runs against a freshly rebuilt scratch table (probe order is not load-bearing) and every expected rejection asserts its specific ORA code, so a statement that fails for an unrelated reason cannot score as a confirmed fact. `test_server_harness.py` drives the whole loop against a stubbed `sqlplus` to prove those verdicts. It skips cleanly with no DSN, so the claims remain documentation-derived until someone points it at a 12.1/12.2/19c/21c/23ai matrix. The gap is "unrun", not "unrunnable". |
| No model-in-the-loop A/B | High | The checker verifies the *mechanical* half. Whether the skill improves an LLM's review has not been measured with/without the skill. |

| Edition-Based Redefinition (EBR) | Medium | Advanced continuous-deployment feature; no fixture. |
| RAC cross-instance coordination | Medium | Covered in the licensing matrix as guidance; no fixture, since the checker cannot see the cluster. |
| Invisible columns/indexes (12c+) | Low | Useful, not on the critical path. |
| Data Guard standby lag mid-migration | Low | Covered as guidance; needs a live standby to test. |
