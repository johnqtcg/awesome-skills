# pg-migration Skill — Test Coverage Matrix

**Counts in this file are derived, not hand-maintained.** Regenerate with:

```bash
cd skills/pg-migration
for f in scripts/tests/test_*.py; do
  printf '%s\t%s\n' "$(basename "$f")" \
    "$(python3 -m pytest "$f" -q --collect-only 2>/dev/null | grep -c '::')"
done
python3 -m pytest scripts/tests/ -q --collect-only 2>/dev/null | grep -c '::'
```

Last regenerated 2026-08-07: **566 offline tests**, 57 mutations, 18 golden fixtures,
22 lint rules.

The live matrix is parametrised per major, so its collected count scales with how many
servers are reachable: 95 when none are (the non-parametrised tests, all skipped), 463
across 14/15/16/17/18.

**These numbers are asserted, not maintained by hand.**
`test_golden_scenarios.py::TestCoverageDocMatchesReality` fails when any of them, the rule
table, or the fixture table drifts from the code — a hand-maintained count had already
drifted twice: once stating more tests than pytest collected, and once leaving a mangled
kill-ratio behind after a bulk edit — which the weaker version of this check could not see,
because the correct figure also appeared elsewhere in the file.

---

## 1. What each suite can and cannot catch

This distinction is the point of the 2026-08 rework. Before it, all 91 tests were of
the first kind, which is why four factual errors about PostgreSQL survived in the
documents while the suite reported 100% coverage.

| Suite | Tests | Asserts against | Can catch a wrong PostgreSQL fact? |
|-------|:-----:|-----------------|:---:|
| `test_skill_contract.py` | 55 | Document structure: required sections, thresholds, line budget | **No** — structure only |
| `test_golden_scenarios.py` | 192 | Fixture shape **and** the linter's real output on each snippet | **Yes**, for anything a rule covers |
| `test_lint_migration.py` | 212 | The checker's behaviour on hand-written SQL, per rule, both directions | **Yes** |
| `test_pg_facts_drift.py` | 71 | Verified doc claims present + superseded phrasings absent | **Yes**, by pinning |
| `test_skill_exemplars.py` | 35 | The skill's own SQL examples, run through the skill's own checker | **Yes** |
| `test_run_regression.py` | 1 | Stage 6 shell orchestration and the linter exit-status contract | **Yes**, for runner/linter integration drift |
| `test_pg_server_matrix.py` | 463 | **A live PostgreSQL 14–18.** Locks read from `pg_locks`, rewrites from `relfilenode`, every shipped SQL block parsed | **Yes — and it is the only one that can catch a fact no rule covers** |

The load-bearing property of suites 2–5 is proven by `scripts/mutation_sweep.py`:
**57/57 mutations killed, 0 survivors.**

### Why the last row is a different kind of test

A mutation sweep proves an assertion is load-bearing. It cannot prove the assertion is
*true* — all it shows is that the suite and the document agree with each other. Two
claims survived a fully green offline suite and were wrong the first time a server was
asked:

| Claim as documented | What a live server showed |
|---------------------|---------------------------|
| `max()` works for a `uuid` backfill cursor | **No `max(uuid)` aggregate exists** on 14–18; the recommended loop would fail at runtime |
| FK on a partitioned table may never be `NOT VALID` | True on 14–17, **false on 18** — the rule needed a version gate |

The same run also found three shipped SQL snippets that could not parse at all
(`ON table (columns)` — both reserved words; `:batch_max`; `<ddl_pid>`).

**A skipped matrix is not a passed matrix, and a partial one is not a full one.** Both
runners encode that in their exit codes rather than in prose:

| Situation | `pg_server_harness.sh` | `run_regression.sh` |
|-----------|:---:|:---:|
| Ran on all five majors, passed | 0 | 0 |
| A test failed | 1 | 1 |
| No server reachable — nothing ran | 2 | 3 (`INCOMPLETE`) |
| Ran, but not on every requested major | 3 (`INCOMPLETE VERIFICATION`) | 3 (`PARTIAL`) |

So an environment without Docker cannot report this coverage as achieved, and neither can
one where four of five containers happened to start. Naming a subset explicitly
(`pg_server_harness.sh 16 18`) is the one case that exits 0 while covering less — it
prints `PARTIAL COVERAGE (n of 5 majors)` so the weaker claim is on the record.

## 2. Lint rules (`scripts/lint_migration.py`)

Every rule has a documentation source, a violating input, and a compliant input.
`test_lint_migration.py::TestRuleRegistry::test_every_rule_has_a_test_case` fails if
a rule is added without both.

| Code | Sev | Rule | Source (PG 17 doc) |
|------|-----|------|--------------------|
| PG001 | critical | `SET LOCAL` outside a transaction block is a no-op | `set.sgml` LOCAL |
| PG002 | critical | CONCURRENTLY inside a transaction block | `create_index.sgml` |
| PG003 | critical | index built without CONCURRENTLY | `create_index.sgml` |
| PG004 | critical | DDL with no `lock_timeout` guard | `config.sgml` |
| PG005 | critical | finite `statement_timeout` around a concurrent build | `config.sgml` |
| PG006 | standard | ALTER TABLE mixes lock classes (escalates to strictest) | `alter_table.sgml` Description |
| PG007 | standard | `ADD CONSTRAINT IF NOT EXISTS` is invalid syntax | `alter_table.sgml` |
| PG008 | standard | constraint guard not scoped by `conrelid` | `pg_constraint` catalog |
| PG009 | standard | constraint added without `NOT VALID` | `alter_table.sgml` NOT VALID |
| PG010 | standard | rewriting `ALTER COLUMN TYPE` without a tool | `alter_table.sgml` Notes |
| PG011 | standard | explicit insert into `GENERATED ALWAYS` identity | `insert.sgml` |
| PG012 | standard | `LIMIT/OFFSET` backfill | skill rule |
| PG013 | standard | `ADD COLUMN` with a volatile DEFAULT rewrites | `alter_table.sgml` Notes |
| PG014 | standard | `max()`-based resume point skips rows | skill rule |
| PG018 | standard | `SET NOT NULL` without a proving CHECK | `alter_table.sgml` SET NOT NULL |
| PG019 | critical | `lock_timeout` set to a value that disables the guard (`0`, `DEFAULT`) | `config.sgml`; measured `SHOW lock_timeout` = 0 |
| PG020 | standard | `ALTER COLUMN TYPE` whose **source** type is not statically known | `alter_table.sgml` Notes; coercibility is a property of the pair |
| PG021 | standard | `NOT VALID` FK on a partitioned table below PG 18 | measured on live 14–18 |
| PG015 | hygiene | REINDEX without CONCURRENTLY | `reindex.sgml` Notes |
| PG016 | hygiene | `VACUUM FULL` instead of pg_repack | `vacuum.sgml` |
| PG017 | hygiene | no ANALYZE after a bulk backfill | skill rule |
| PG022 | hygiene | idempotency guard decides on a NAME without comparing the definition | `pg_constraint` catalog / `create_index.sgml` IF NOT EXISTS |

## 3. Golden fixtures

Each fixture declares `expected_lint_codes` (the full set the checker must emit) and
`primary_lint_code` (the defect the fixture is *about*, whose severity the fixture's
`severity` field labels). Those are two different questions: a realistic snippet often
also lacks a `lock_timeout` (critical) while demonstrating a standard-severity defect.

| ID | Title | Type | Sev | Primary | All expected codes |
|----|-------|------|-----|---------|--------------------|
| PG-001 | Missing lock_timeout | defect | critical | PG004 | PG004 |
| PG-002 | Index without CONCURRENTLY | defect | critical | PG003 | PG001, PG003, PG004 |
| PG-003 | Constraint without NOT VALID | defect | standard | PG009 | PG001, PG004, PG009 |
| PG-004 | Missing rollback (DROP COLUMN) | defect | critical | PG004 | PG004 |
| PG-005 | ALTER COLUMN TYPE on large table | defect | standard | PG010 | PG001, PG004, PG010 |
| PG-006 | ADD CONSTRAINT IF NOT EXISTS | defect | standard | PG007 | PG004, PG007 |
| PG-007 | Well-formed phased migration | good_practice | none | — | *(none)* |
| PG-008 | Good CONCURRENTLY index build | good_practice | none | — | *(none)* |
| PG-009 | Degraded — no context | degradation_scenario | none | — | PG003, PG004 |
| PG-010 | Multi-step column rename | workflow | none | — | *(none)* |
| PG-011 | NOT NULL without CHECK shortcut | defect | standard | PG018 | PG001, PG004, PG018 |
| PG-012 | SET LOCAL before CONCURRENTLY | defect | critical | PG001 | PG001, PG004 |
| PG-013 | statement_timeout kills the build | defect | critical | PG005 | PG005 |
| PG-014 | Mixed lock classes in one ALTER | defect | standard | PG006 | PG006 |
| PG-015 | Unscoped constraint guard | defect | standard | PG008 | PG008, PG022 |
| PG-016 | int → bigint rewrites | defect | standard | PG010 | PG010 |
| PG-017 | Identity insert without OVERRIDING | defect | standard | PG011 | PG011, PG017 |
| PG-018 | max()-based resume point | defect | standard | PG014 | PG012, PG014, PG017 |

`good_practice` fixtures are asserted to emit **zero** findings. PG-007 previously
claimed "no violations" while containing a `SET LOCAL` no-op and an unscoped `conname`
guard — the old suite could not see it because it only read the fixture's own prose.

## 4. Fact-drift guards (`test_pg_facts_drift.py`)

33 facts pinned, each with the documentation source and the superseded wording it
replaced. 16 carry a `forbid` pattern; `test_forbid_patterns_are_specific_enough_to_fire`
proves each of those patterns actually matches the pre-2026-08 text it guards against,
so a typo'd regex cannot pass forever as an inert guard.

Facts corrected in the 2026-08 rework:

| Fact | Was | Now |
|------|-----|-----|
| `ADD FOREIGN KEY` lock | merged with CHECK as AccessExclusive | ShareRowExclusive on **both** tables |
| Multi-subcommand ALTER | not mentioned | escalates to the strictest subcommand's lock |
| REINDEX | AccessExclusive on the table, blocks reads | ShareLock on table + AccessExclusive on index; blocks nearly all queries via the planner |
| `VALIDATE CONSTRAINT` (FK) | ShareUpdateExclusive only | + RowShare on the referenced table |
| `int` → `bigint` | listed as no-rewrite | **rewrites** (not binary coercible) |
| `SET (fillfactor)` | AccessExclusive | ShareUpdateExclusive |
| `ATTACH PARTITION` | AccessExclusive on parent | ShareUpdateExclusive on parent |
| Partitioned-table FK | not mentioned | may **not** be declared NOT VALID |
| `SET LOCAL` guard | mandated unconditionally | context-dependent; a no-op outside a transaction |
| `statement_timeout` | mandated at 30s | must be 0 around a concurrent build |
| Identity copy | `GENERATED ALWAYS` + explicit id | needs `OVERRIDING SYSTEM VALUE` |
| DO-block `COMMIT` | "requires CREATE PROCEDURE" | legal on PG 11+, top-level invocation only |
| pg_repack | described a schema-change workflow | cannot change a schema at all |
| Extension version pin | `IF NOT EXISTS` accepted an installed wrong version | absent creates, matching is a no-op, mismatch fails for separate upgrade review |
| Supported versions | 12–17, default 12 | 14–18, default 14 |

## 5. Mutation sweep (`scripts/mutation_sweep.py`)

57 mutations, all killed. Anchors are verified to exist before the sweep runs — a
stale anchor is a hard error, never reported as a survivor, because a no-op
substitution would otherwise look like missing coverage.

Coverage by area: guard-form detection (M01–M05), lock classification (M06–M09),
type-change classifier (M10–M12, M31–M33), statement splitting (M13–M16), individual
rules (M17–M22, M29–M30), guard VALUE not presence (M34–M36), DDL and bulk-write scope
(M37–M38), version gating (M39), idempotency guards (M40–M42, M46,
M52–M53), narrowing to real guards (M45), severity wiring (M23), documentation drift
(M24–M28, M43–M44, M47–M51, M55–M57), and shell orchestration (M54).

M23 originally **survived**: `test_severity_matches_registry` compared the linter's
output against the registry it was checking, so downgrading a rule moved both sides
of the assertion together. Severities are now pinned independently in
`EXPECTED_SEVERITY`.

## 6. Known coverage gaps

Declared honestly — the frontmatter no longer claims coverage the checker lacks.

| Gap | Priority | Status |
|-----|----------|--------|
| RLS policy migration | Medium | §5.5 checklist items exist; no lint rule, no fixture |
| Extension upgrade (CREATE/ALTER EXTENSION) | Low | Gate 1 collects it; no rule |
| Logical replication DDL impact | Medium | §5.5 states DDL is not replicated; no rule |
| Partition conversion (non-partitioned → partitioned) | Medium | Covered in reference; no fixture |
| Live-server lock verification | Closed | `test_pg_server_matrix.py` reads every documented lock level out of `pg_locks` on live 14/15/16/17/18 (`scripts/pg_server_harness.sh`) |
| Concurrent-session lock *contention* | Open | Lock **modes** are verified; what a second session experiences while the DDL holds them is not. A two-session blocked/blocking test would close it |
| Lock-time estimation | Open | No production I/O sampling, so wall-clock estimates stay conditional on a stated throughput assumption (§4 Degradation Modes) |
| Cross-statement table-size awareness | Closed | `--rows` escalates rewrite findings to critical at >= 1,000,000 rows and never de-escalates (`TestRowCountEscalation`) |

**The live-server gap is closed.** Every lock level in `references/pg-ddl-lock-matrix.md`
is now read out of `pg_locks` on real servers, every rewrite claim from
`pg_relation_filenode()` before/after, and every shipped SQL block is fed through the real
parser on all five majors. Run it with `bash scripts/pg_server_harness.sh`.

What remains open is narrower and worth stating plainly: the matrix verifies lock **modes**
from inside the altering session. It does not open a second session to observe what a
concurrent reader or writer actually experiences while those locks are held, and it makes
no wall-clock measurements — so every duration in this skill is a conditional estimate,
not a measurement.
