# mysql-migration Skill — Test Coverage Matrix

> **What these tests prove, and what they do not.** Layers 1–2 check that the documentation is
> structurally intact and internally consistent. Only layers 3–5 can catch a claim that is
> *coherent and wrong* — which is how the 2026-08-06 audit found four incorrect rows in the DDL
> matrix and a reversed gh-ost invocation enshrined as a golden "good practice" while all 89 tests
> were green. Read §6 before quoting a pass rate as evidence of correctness.

## 1. Contract Tests (`test_skill_contract.py`)

Structural properties of SKILL.md and the reference files: required sections, gate structure,
keyword presence, line budget, cross-file consistency. **51 tests.**

These prove the skill is well-formed. They cannot detect a wrong technical claim.

## 2. Golden Fixtures (`test_golden_scenarios.py`)

### 2.1 Fixture inventory

| ID | Title | Type | Severity | Lint expectation |
|----|-------|------|----------|------------------|
| MIG-001 | Missing session guards | defect | critical | reports MM015 |
| MIG-002 | Implicit algorithm on large table | defect | critical | reports MM014 |
| MIG-003 | NOT NULL without phased approach | defect | critical | reports MM014, never MM001 |
| MIG-004 | Missing rollback plan (DROP COLUMN) | defect | critical | reports MM025 |
| MIG-005 | INSTANT on MySQL 5.7 | defect | standard | reports MM001 |
| MIG-006 | LIMIT/OFFSET backfill | defect | standard | reports MM011, MM012, MM016 |
| MIG-007 | Well-formed phased migration | good_practice | none | clean: no MM001/MM014/MM015 |
| MIG-008 | Good gh-ost invocation | good_practice | none | clean: never MM017/MM018 |
| MIG-009 | Degraded mode — no context | degradation_scenario | none | reports MM014, MM015 |
| MIG-010 | Multi-step column rename workflow | workflow | none | exempt (no executable statements) |
| MIG-011 | VARCHAR boundary cross (utf8mb4) | defect | standard | reports MM006 |
| **MIG-012** | gh-ost `--allow-on-master` with a replica host | defect | critical | reports MM017, MM018 |
| **MIG-013** | `ALGORITHM=INPLACE` on a 5.7 partition clause | defect | critical | reports MM007 |
| **MIG-014** | DROP COLUMN wrongly escalated to gh-ost | defect | standard | clean — the SQL is correct, the review note is not |
| **MIG-015** | ADD FOREIGN KEY + INPLACE with checks on | defect | critical | reports MM009 |

Bold rows were added by the 2026-08-06 audit. MIG-008 was rewritten: it previously taught
`--host=replica-host --allow-on-master`, which is backwards.

### 2.2 Two layers of assertion

| Layer | Mechanism | Falsifiable by |
|-------|-----------|----------------|
| Integrity + rule coverage | JSON schema checks; every `coverage_rules` phrase must appear in the docs | A malformed fixture, or a rule phrase deleted from the docs |
| **Checker verdicts** | Each `migration_snippet` is run through `lint_migration.py` at the fixture's version; reported check IDs are compared against `must_report` / `must_not_report` | The checker's judgement on real statements changing |

`test_good_practice_fixtures_are_clean` is the assertion that would have caught MIG-008 on the day
it was written: a fixture labelled `good_practice` must produce zero critical findings.

## 3. Migration Checker (`lint_migration.py` + `test_lint_migration.py`)

A deterministic checker over actual SQL and gh-ost/pt-osc commands. `CHECK_REGISTRY` declares 29
checks; `test_every_registered_check_has_a_violating_input` makes that declaration falsifiable, and
each check has both a violating input and a corrected input that must come back clean.

MM002 was **withdrawn** on 2026-08-06: once MM001's threshold was corrected from 8.0.0 to 8.0.12 it
became a strict subset, and a check that cannot fire independently inflates the count without adding
coverage. `test_mm002_is_not_resurrected` keeps it withdrawn. IDs are not reused.

| Group | Checks | Verified against |
|-------|--------|------------------|
| INSTANT clause availability | MM001 | Nutshell: the clause arrives **whole** in 8.0.12 — 5.7 and 8.0.0–8.0.11 reject it for *every* operation, `SET DEFAULT` included |
| INSTANT per-operation gates | MM003–MM005 | 8.0.29 positional ADD / 8.0.29 DROP / 8.0.28 RENAME |
| Never-INSTANT operations | MM006 | 8.0/8.4 matrix `Instant = No` rows |
| Partition clause support | MM007, MM008 | 5.7 vs 8.0 partitioning tables |
| Concurrent-DML violations | MM008 | manual `Permits Concurrent DML = No` rows |
| Foreign keys | MM009 | "INPLACE … when `foreign_key_checks` is disabled. Otherwise, only COPY" |
| VARCHAR byte boundary | MM010 | length-prefix rule (0–255 = 1 byte, ≥256 = 2 bytes) |
| Runnability | MM011, MM012 | `WHILE`/`REPEAT` are stored-program-only; `UPDATE` takes `LIMIT n` only |
| Operational safety | MM013–MM016, MM025 | binlog/PITR semantics; MDL guards; O(n²) paging |
| Tooling | MM017–MM020 | gh-ost cheatsheet + flags doc; Percona Toolkit docs |
| Version-correct monitoring | MM021–MM024 | `SHOW REPLICA STATUS` 8.0.22+; `SHOW SLAVE STATUS` removed 8.4; `data_locks` 8.0+ |
| Invalid ALTER syntax | MM026 | `IF [NOT] EXISTS` appears **zero** times on the 8.0 ALTER TABLE page; it is MariaDB syntax |
| pt-osc flag incompatibility | MM027 | `--preserve-triggers` cannot combine with `--no-drop-triggers` / `--no-drop-old-table` / `--no-swap-tables` |
| **INSTANT lock clause** | MM029 | *"Only `LOCK = DEFAULT` is permitted for operations that use `ALGORITHM=INSTANT`."* `ALGORITHM=INSTANT, LOCK=NONE` reads like a stronger guarantee and is a rejected statement |
| **Unread migration carrier** | MM030 | run-level: Liquibase XML/YAML/JSON and Go/Java/Python migrations are counted as findings, not printed as a footnote — printing while returning 0 let a directory of changelogs pass CI as a clean run |
| **Unverified or assumed target version** | MM028 | run-level, not per-statement: fires for anything outside the three transcribed versions (5.7 / 8.0 / 8.4) — that includes the `assumed` bands 8.1–8.3 and 9.x, not only unknown ones. `dev.mysql.com` redirects an unknown version such as 10.0 to the current release, so "the manual loaded" is not evidence the rules apply |

**Declared non-coverage** (`UNCHECKED_BY_DESIGN` in the module, asserted by a test):

| Not checked | Why |
|-------------|-----|
| Type change vs nullability change | `MODIFY c DECIMAL(12,2) NOT NULL` is COPY when the type changes and INPLACE when only nullability does. Distinguishing requires the current schema. An earlier heuristic flagged the standard backfill-then-enforce phase as critical — a false positive on the very pattern this skill recommends |
| VARCHAR band crossing without a declared charset | Needs the column's character set; only checked when `CHARACTER SET` is on the statement |
| Table size / QPS risk axes | Require production metrics, not statement text |
| Whether a VARCHAR change crosses the length-prefix band | The band depends on **both** widths and the statement carries only the new one: `VARCHAR(260)→VARCHAR(300)` latin1 is legal in place, `VARCHAR(200)→VARCHAR(300)` is not. MM010 is therefore a **warning** naming `SHOW CREATE TABLE` as the evidence, never a critical |
| The wider safety model of an `assumed` version | 9.x shares 8.4's online-DDL matrix byte for byte, yet 9.1.0 moved the INSTANT row-version ceiling from 64 to 255. Matrix identity is not rule identity, so 9.x and the EOL 8.1-8.3 releases are `assumed`, and MM028 says so on every run |
| Whether the target table has triggers | Decides gh-ost `--include-triggers` vs pt-osc `--preserve-triggers`; needs `SHOW TRIGGERS` |
| DDL inside Liquibase XML/YAML/JSON changelogs, or Go/Java/Python programmatic migrations | Not SQL. These become MM030 findings **whether discovered in a directory or named explicitly** — naming one on the command line does not make it parseable, and scanning it as SQL reported "clean" about DDL masked inside JSON string values. Lint `liquibase updateSQL` output instead |

## 4. Fact Drift Guards

| File | Guards |
|------|--------|
| `test_ddl_matrix_drift.py` | Every audited matrix row, pinned against the manual with the source URLs and the 2026-08-06 verification date. Includes a guard that the unsourced "only one INSTANT ALTER per rebuild" claim does not return |
| `test_tool_facts_drift.py` | gh-ost operation modes, destructive-flag absence from templates, feature version gates (1.1.6/1.1.8/1.1.9), trigger handling, backfill runnability, `sql_log_bin` containment, version-correct monitoring, pt-osc upstream defaults, and the corrected AE-9/AE-13 |

Both are scoped to **code blocks and table cells**, not whole-document string presence: the
documents necessarily discuss each wrong pattern in order to correct it, so a naive "this string
must not appear" test would fire on the prose that fixes the bug.

## 4a. Self-Lint Gate and the Warning Baseline

The self-lint runs at `--fail-on warning`, not `--fail-on critical`. A warning nobody must act on
accumulates until the gate is decorative — the first review pass left an unnoticed MM014 behind
exactly that way.

Genuinely-correct-at-another-version findings live in `tests/lint_baseline.txt` as
`CHECK_ID | path-suffix | evidence-substring`, each with a written justification. Two properties
make it a gate rather than a mute button:

- Matching is **by content, not line number** — an entry follows the statement it was written for
  and stops matching when that statement changes, instead of silently drifting onto its neighbour.
- A baseline entry that matches **nothing** fails the run, so an exemption cannot outlive its reason.

`run_regression.sh` also carries a **test-file coverage guard**: every `test_*.py` on disk must be
wired into a named phase. Without it a new test file is collected by `pytest skills/` in CI but
skipped by the skill's own runner — which is what happened to a 52-test file on 2026-08-06.

## 5. Evidence Beyond the Documentation

Three opt-in harnesses answer questions the pytest suite structurally cannot. All three **skip
loudly** rather than passing quietly, because "not run" and "verified" must never look alike.

### 5.1 `verify_against_server.sh` + `verify_matrix.sh` — can falsify the matrix

Executes representative ALTERs against a real server and compares acceptance/rejection with what the
matrix claims, in **both** directions: a claimed rejection that actually succeeds is also a failure,
since that is how an over-conservative row sends safe migrations through gh-ost for nothing.

`verify-matrix.docker-compose.yml` brings up 5.7, **8.0.11**, 8.0, 8.4 and 9.x on loopback with no
volumes; `verify_matrix.sh` probes each. 8.0.11 is pinned deliberately — the INSTANT-clause boundary
at 8.0.12 is the fact this skill got wrong twice, and one 8.0.x tag cannot test both sides of it.

Safety properties (all exercised by the guard paths below):

| Property | Why |
|---|---|
| `MYSQL_MIGRATION_VERIFY_DISPOSABLE=yes` required | the script CREATEs and DROPs a schema; working credentials must not be sufficient to reach production |
| Schema name must match `^[A-Za-z][A-Za-z0-9_]{0,62}$` | the name is interpolated into DDL |
| Credentials via a 0600 option file | `--password=` is world-readable in `ps` for the life of every invocation |
| Option file removed on **every** exit path | the trap is installed before the file is populated, not after the first successful query |
| Refuses to reuse an existing schema | it would drop someone else's data on cleanup |

| Exit | Meaning |
|:----:|---------|
| 0 | skipped (not requested / nothing reachable), or every probe matched |
| 1 | the server contradicted a documented claim |
| 3 | prerequisites missing, or `--require-all` with an unreachable instance |

**Status: the guard paths — not requested, not declared disposable, unsafe schema name, missing
client, unreachable server, pre-existing schema, credential-never-in-argv, temp-file-cleanup — have
all been exercised. The 19 on-server probes have NOT been run**: no MySQL instance and no usable
Docker daemon existed in the environment where this was written.

### 5.2 `run_model_eval.py` — the with-skill / without-skill question

Runs each golden fixture through a model twice and grades both arms on a **deterministic** rubric:
every criterion is a regex or a `lint_migration.py` verdict over the response text, so a re-run over
the same transcripts yields the same score and the rubric itself is unit-testable. A model grader
would make the headline number unfalsifiable, which is the failure mode this audit has been about.

The harness fails when the with-skill arm regresses on a required criterion, emits SQL with more
critical lint findings, or improves nothing measurable. `test_model_eval_harness.py` drives all
three outcomes plus the skip, empty-input, and one-armed cases against recorded transcripts.

**Status: the grader is tested in three directions. The model arm has NOT been run** — a nested
`claude -p` in this environment reports `Not logged in`. The fixtures under
`tests/eval_grader_fixtures/` are synthetic grader inputs and are labelled as such; **no number
derived from them is evidence about this skill.**

## 6. Coverage Summary and Honest Limits

Test counts are **not** reproduced here. They drifted at every one of the four review passes —
545-vs-546 and 254-vs-255 were both caught by a reviewer rather than by a test — and a number nobody
checks is worse than no number. `bash scripts/run_regression.sh` prints the authoritative per-phase
totals in a couple of seconds.

The two counts that ARE stated below are stated because
`test_lint_round2_audit.py::TestDocumentedCountsMatchTheCode` fails when they drift:
**29 registered checks** and the mutation total. A guard test enforces that no unasserted grand
total creeps back into this file.

Mutation coverage: `scripts/mutation_sweep.py` ships with the skill and holds **89** mutations, each
reintroducing one defect a review actually found or disabling one check. Latest run: **89/89 killed,
0 survived, 0 errors.** Reproduce with `python3 scripts/mutation_sweep.py` (`--list` / `-k` to
inspect and subset). A surviving mutation marks an assertion that is not testing what it claims; a
mutation whose string no longer matches is an ERROR, not a quiet skip.

### What is still not covered

| Gap | Priority | Why it matters |
|-----|----------|----------------|
| **On-server matrix verification actually executed** | High | §5.1's harness, guard paths, and 5-version Docker matrix all exist and are tested; **no probe has touched a live server.** Until one does, every matrix row rests on the manual plus transcription guards. This is the single highest-value thing anyone with a Docker daemon can do for this skill: `docker compose -f scripts/verify-matrix.docker-compose.yml up -d --wait && bash scripts/verify_matrix.sh` |
| **Model evaluation actually executed** | High | §5.2's grader is tested in three directions; **the model arm has never run.** Whether the skill changes what an assistant produces remains UNANSWERED |
| Liquibase / programmatic migration parsing | Medium | XML/YAML/JSON changelogs and Go/Java/Python migrations are counted and named as unread, not parsed. Lint `liquibase updateSQL` output instead |
| INSTANT row-version exhaustion in the checker | Medium | AE-17 documents the budget (64 before 9.1.0, 255 from 9.1.0); the checker cannot count versions from statement text — it needs `INNODB_TABLES.TOTAL_ROW_VERSIONS` |
| Character-set conversion fixture (full-table `CONVERT TO`) | Medium | AE-7 covers it in prose; no golden fixture exercises the 5.7-COPY vs 8.0-SHARED split |
| Golden fixtures for MM026–MM030 | Low | All five have failing inputs in the checker tests; none has a narrative golden fixture |
| Multi-database migration coordination | Low | Real pattern, rare; would add significant complexity |

### Review history

| Date | Trigger | Outcome |
|------|---------|---------|
| 2026-08-06 (pass 1) | External review of the DDL matrix and large-table doc | 4 matrix rows wrong + 6 more found while verifying; gh-ost mode reversed; `WHILE` backfill unrunnable; golden tests were string-presence only. Added `lint_migration.py`, drift guards, 4 fixtures |
| 2026-08-06 (pass 2) | External review of the pass-1 result | INSTANT threshold off by 12 patch releases; `IF [NOT] EXISTS` advice invalid on MySQL; 3 checker defects; pt-osc trigger path incomplete; warnings could accumulate silently; mutation runner not shipped. Runner also gained a test-file coverage guard after a 52-test file was found unwired |
| 2026-08-06 (pass 6) | External review of the pass-5 result | The model eval could **PASS a with-skill arm that emitted server-rejected SQL**, because it compared only the *delta* in critical findings — both arms could be equally unsafe while the skill "won" on formatting. Replaced with an absolute gate: any with-skill scenario above `--max-critical` (default 0) fails, whatever the baseline did. A crashed linter had been encoded as `critical = -1`, which compared as *cleaner* than 0 under every `> 0` / `max(…, 0)` test — now a separate `lint_error` flag that fails the run in either arm. `--max-warnings` added as an opt-in threshold. Rubric bug found while testing: `lock_explicit` required a literal `LOCK=`, scoring the **correct** INSTANT form (which must omit it) as a regression. SKILL.md section 11 still described pre-pass-5 file discovery |
| 2026-08-06 (pass 5) | External review of the pass-4 result | An explicitly-named `.json`/`.xml` changelog was still scanned as SQL and reported clean — the DDL sat inside a JSON string, masked by the quoting. Known-unparseable extensions now yield MM030 whether named or discovered; only *unknown* extensions keep the "caller says it is a migration" escape hatch. AE-17's prose still said "number 65" after its table was versioned. SKILL.md said INSTANT "accepts no LOCK clause" beside a quote saying `LOCK=DEFAULT` is permitted — now states the accepted forms. Eval harness stopped double-injecting SKILL.md and gained per-scenario gates, since aggregate scoring let one scenario's regression cancel against another's gain. Hand-maintained test totals were removed from this file: they drifted at every pass and a guard test now blocks their return |
| 2026-08-06 (pass 4) | External review of the pass-3 result | **Pass 3 introduced a production-safety error**: it rewrote SKILL.md to say INSTANT takes no metadata lock, following the *What Is New* page over the ALTER TABLE reference, which states an exclusive MDL may be taken briefly — and that INSTANT accepts **only** `LOCK=DEFAULT` (MM029). 9.x downgraded verified→assumed after 9.1.0 was found to have moved the row-version ceiling 64→255 without touching the DDL matrix. Unread migration carriers became MM030 findings instead of a footnote over a green exit. Eval harness gained strict scenario pairing, required-only improvement, unfenced-SQL extraction, and reference injection |
| 2026-08-06 (pass 3) | External review of the pass-2 result | Version range overclaimed (9.x silently analysed with 8.x rules → MM028 + verified-range data); `.ddl` files skipped in directory mode and Liquibase coverage overstated; server script accepted an unvalidated schema name and leaked the password via argv; one baseline exemption was hiding a real doc gap rather than a version constraint; model-eval and server-matrix harnesses added |
