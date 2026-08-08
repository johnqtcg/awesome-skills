# mongo-migration Skill — Test Coverage Matrix

**Counts here are asserted, not maintained by hand.**
`test_golden_scenarios.py::TestCoverageDocMatchesReality` fails when any of them drifts
from the code. Regenerate with:

```bash
cd skills/mongo-migration
python3 scripts/tests/update_coverage_counts.py
```

Last regenerated 2026-08-07: **347 offline tests**, 32 mutations, 13 golden fixtures,
16 checker rules, 19 pinned facts.

The live matrix is parametrised per major, so its collected count depends on how many
servers are reachable: 108 across MongoDB 7.0 + 8.0.

---

## 1. What each suite can and cannot catch

Before 2026-08 this skill had 97 passing tests split across two suites, and they proved
only that the document, the fixture and the test shared a wording. What they preserved,
green:

- a backfill loop that threw `TypeError` on its first line and could not run at all;
- a rolling-index procedure the server rejects with `NotWritablePrimary`, recorded by a
  fixture as *"No violations"*;
- a `$gt` keyset cursor that silently strands every `_id` of a different BSON type.

| Suite | Tests | Asserts against | Can catch a wrong MongoDB fact? |
|-------|:-----:|-----------------|:---:|
| `test_skill_contract.py` | 57 | Document structure: required sections, frontmatter, thresholds | **No** — structure only |
| `test_golden_scenarios.py` | 54 | Fixture shape and metadata consistency | **No** — shape only |
| `test_lint_migration.py` | 115 | The real checker's output on real JavaScript, per rule, both directions — **and every fixture's snippet run through it** | **Yes**, for anything a rule covers |
| `test_mongo_facts_drift.py` | 110 | Verified claims present, superseded phrasings absent, **and cross-file consistency** | **Yes**, by pinning |
| `test_go_examples_compile.py` | 11 | **The Go blocks, gofmt-parsed and built** against a stubbed driver module | **Yes** — it is what would have caught the `wcColl` handle that could not compile |
| `test_mongo_server_matrix.py` | 108 | **A live MongoDB 7.0 and 8.0, as real 3-member replica sets** | **Yes — the only suite that can catch a fact no rule covers** |

`scripts/mutation_sweep.py`: **32/32 mutations killed, 0 survivors**, run against a
private copy of the skill directory so the real worktree is never written to.

### Why the last row is a different kind of test

A mutation sweep proves an assertion is load-bearing. It cannot prove the assertion is
*true* — it only shows the suite and the document agree with each other. Everything in
the table below was found the first time a server was actually asked:

| Claim as documented | What a live server showed |
|---------------------|---------------------------|
| `lastId.valueOf().substring(0,24)` | `valueOf()` returns an **object**; the loop threw `TypeError` on iteration 1 |
| that range would batch by `_id` | `ObjectId(hex).equals(id)` is true, so `{$gt: id, $lte: id}` is **always empty** |
| "`$gt`/sort agree, so any `_id` type works" | `$gt` **type-brackets**: 30 ints + 30 ObjectIds, batch 25 → **30 documents stranded** |
| index the backfill with a partial `_id` index | rejected 3 ways: `partialFilterExpression` invalid on `_id`, `$exists: false` unsupported in it *at all*, and `_id_` cannot be dropped |
| "connect to the secondary and createIndex" | `NotWritablePrimary` — the procedure cannot execute |
| TTL change requires dropIndex + createIndex | `collMod` changes `expireAfterSeconds` in place (5.1+, i.e. every supported major) |
| `moderate` "only validates new writes" | insert **rejected**; update of a *compliant* doc **rejected**; only an already-invalid doc is exempt |
| "MongoDB has no transactional DDL" | `createCollection` and `createIndex` both commit inside a transaction |
| WiredTiger tickets default to 128 each | `totalTickets` was **10**; and the metric moved from `wiredTiger.concurrentTransactions` (7.0) to `queues.execution` (8.0) |
| `rs.printReplicationInfo()` for lag | prints the connected member's **oplog window**, not anyone's lag |

**Three members, not one.** A single-node replica set answers `rs.*` and satisfies
`w: "majority"`, which is enough for the ObjectId / TTL / validator / transaction facts.
It has no secondary, so "a secondary rejects `createIndex`" *skipped* and "the default
build replicates" only re-read the primary's own index list. The harness now starts three
members per major and connects to a secondary with `directConnection=true`; those tests
**fail** rather than skip when no secondary is reachable.

**A skipped matrix is not a passed matrix, and a partial one is not a full one.**

| Situation | `mongo_server_harness.sh` | `run_regression.sh` |
|-----------|:---:|:---:|
| Ran on both majors, passed | 0 | 0 |
| A test failed | 1 | 1 |
| No server reachable — nothing ran | 2 | 3 (`INCOMPLETE`) |
| Ran, but not on every requested major | 3 (`INCOMPLETE VERIFICATION`) | 3 (`PARTIAL`) |

## 2. Checker rules (`scripts/lint_migration.py`)

Every rule has a source, a violating input and a compliant input;
`test_lint_migration.py::TestRuleRegistry` fails if one is added without them.

| Code | Sev | Rule | Grounding |
|------|-----|------|-----------|
| MG001 | critical | unbounded `updateMany`/`deleteMany` with no batching loop | one write holds a ticket for its whole duration |
| MG002 | critical | ObjectId range rebuilt from its own hex — an empty range | measured: `ObjectId(hex).equals(id)` |
| MG003 | critical | `ObjectId.valueOf()` treated as a string | measured: returns an object |
| MG004 | critical | `createIndex` aimed at a replica-set secondary | measured: `NotWritablePrimary` |
| MG016 | critical | `$gt` keyset over `_id` with no single-type guarantee | measured: type bracketing strands a whole type |
| MG005 | standard | write concern not stated on a migration write | not the default for every deployment |
| MG006 | standard | resume point taken from `max(_id)` of migrated docs | pre-migrated high keys hide unfinished work |
| MG007 | standard | `validationLevel: strict` before a backfill | strict validates every write against legacy docs |
| MG008 | standard | unique index with no duplicate pre-check | `createIndex` fails on existing duplicates |
| MG009 | standard | TTL change by dropIndex + createIndex | `collMod` does it in place from 5.1 |
| MG010 | standard | `$unset` described as reversible | the previous value is gone unless captured |
| MG011 | standard | `validate()` as a routine migration step | takes an exclusive collection lock |
| MG015 | standard | index build on a large collection with no lag monitoring | the build runs on every member |
| MG012 | hygiene | `rs.printReplicationInfo()` used to read lag | measured: it reports the oplog window |
| MG013 | hygiene | ticket metric read from the version-wrong path | measured: path differs on 7.0 vs 8.0 |
| MG014 | hygiene | no throttle between backfill batches | an unthrottled loop is an unbounded write |

MG010 has no automatable violating input — it is about prose, and the fact-drift guards
cover it. `TestRuleRegistry::test_every_rule_has_a_test_case` asserts that exemption
explicitly rather than letting it pass unnoticed.

## 3. Golden fixtures

Each fixture declares `expected_lint_codes`, and
`TestGoldenFixturesDriveTheChecker::test_declared_codes_match_the_checker` runs the
snippet through the real checker and compares. The previous suite asserted that a
fixture's own `expected_feedback` contained the word *"no violation"* — a string the
fixture author wrote, with nothing executed. That is how MONGO-008 shipped an
unexecutable procedure labelled *good practice*.

Two properties now hold by assertion, not by labelling:

- every `good_practice` fixture emits **zero** findings;
- every `defect` fixture trips at least one rule, so a defect no rule covers is a stated
  coverage gap rather than a silent one.

## 4. What none of this establishes

- **Sharded clusters.** No `mongos`/config-server harness. Every sharding claim
  (`reshardCollection`, `refineCollectionShardKey`, chunk migration) rests on the manual.
- **Scale.** Probes run on hundreds of documents. Nothing here measures how a build or a
  backfill behaves at 50M.
- **Lag under load.** The matrix confirms replication *happens*; it does not measure lag
  during a build, so every duration in this skill is a conditional estimate.
- **The checker's semantics.** It reads JavaScript syntactically. `--limitations` lists
  what it cannot decide, and a clean run prints `NOT a proof of safety` rather than `OK`.
