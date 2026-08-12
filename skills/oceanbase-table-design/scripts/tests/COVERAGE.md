# Test Coverage Matrix

This file records, honestly, what `scripts/tests/` **does** and **does not** test.
Coverage claims are written as data (the tables below) rather than scattered in comments, so the "claim" and the "implementation" can be checked against each other: every CHECKED line has a corresponding case, and every UNCHECKED line is an explicitly written-down gap, not an oversight.

Run:

```bash
python3 -m pytest scripts/tests -q          # or bash scripts/run_regression.sh
```

Zero LLM dependency, all text and filesystem assertions, completes in seconds.

---

## 1. Division of Labor Between the Two Test Types

| | Contract tests `test_skill_contract.py` | Golden scenarios `test_golden_scenarios.py` | Mutation sweep `test_mutation_sweep.py` |
|---|---|---|---|
| Granularity | Whether a single rule / structural constraint exists | Whether the full set of rules needed for one complete scenario is present | Whether the assertions above actually bite |
| Analogy | Unit test -- every brick is there | Integration test -- the bricks assembled cover the scenario | Pulling a brick out to check the wall falls |
| Protects against | A rule being deleted, renamed, or losing its mode gate | Coverage gaps in a combined scenario | **Vacuous assertions** -- a test that passes whether or not the rule is present |
| Data source | Direct assertions | `golden/*.json` fixtures | The `MUTATIONS` table, run against a temp copy |

Why the third column exists: the first two only ever assert that text is **present**, and a
suite of presence assertions is green both when the corpus is right and when the assertions
are empty. Reading them cannot tell you which. The mutation sweep breaks each rule in turn
and requires the **named** test that owns it to fail -- so a survivor is a real coverage hole,
not a matter of opinion. It found two on its first run: `tablet-capacity.md` had no pin at
all, and one assertion in this suite offered an `|` alternative that matched a neighbouring
sentence, so inverting the claim it guarded left it green.

Boundary with `tests/cases.json`: `cases.json` is the grading standard for **Agent output** -- it requires an Agent run first, then a verdict from `run_cases.py --grade`. `scripts/tests/` judges **the skill text itself** and can be run at any time. The two are linked through shared rule IDs; `test_rules_registered_in_cases_json` guarantees they do not drift apart.

---

## 2. CHECKED -- Covered Items

### 2.1 Structure and Metadata

| Check | Case |
|---|---|
| Frontmatter exists, `name` matches the directory name, kebab-case | `FrontmatterTests` |
| `description` <= 1024 characters, no XML angle brackets | `FrontmatterTests` |
| SKILL.md within both the line and the word budget | `SkillSizeTests`, `RegressionRunnerTests` |
| Every required reference file exists, and every md under `references/` is indexed | `ReferenceIntegrityTests` |
| Every md under `references/` is registered in the Section 10 index | `ReferenceIntegrityTests` |
| **Every local link in SKILL.md resolves** | `ReferenceIntegrityTests` |
| The stale `agents/openai.yaml` no longer appears | `ReferenceIntegrityTests` |
| No TODO / FIXME / XXX / TBD scaffolding left behind | `ReferenceIntegrityTests` |
| `run_regression.sh` exists, is executable, and every script carrying a `--self-test` is wired into it | `RegressionRunnerTests` |

### 2.2 Rule Pins (each one anchors a past or possible failure)

| Rule | Why it is pinned | Case |
|---|---|---|
| Every L0 subject is named individually, and the item count equals that subject list | A bare "at least N items" is satisfied by any N items, so one could be swapped for an unrelated one; and the prose number drifts (this row said ">= 12" after the list became 11) | `L0Tests` |
| Auto-increment columns **branch by compatibility mode** | Without this gate, illegal DDL would be generated in Oracle mode | `AutoIncrementModeGateTests` |
| The Oracle BNF mirror really has no `AUTO_INCREMENT` | This is the factual basis for the rule; must be re-checked whenever the BNF is refreshed | `AutoIncrementModeGateTests` |
| The skip magnitude comes from `AUTO_INCREMENT_CACHE_SIZE` = 1000000 | Without this, "use BIGINT" becomes an unsupported slogan | `AutoIncrementModeGateTests` |
| The three states of `default_table_store_format` and the explicit-clause recommendation | "No clause means row storage" would produce the opposite of the actual conclusion | `TenantDefaultGateTests` |
| NDV > partition count; HASH needs high cardinality vs. LIST needs low cardinality -- **opposite directions** | Confusing the two produces a design that is inevitably skewed | `PartitionKeySelectionTests` |
| `unverified`, not `pass`, when a statistic is missing | "Not tested" does not mean "no problem" | `PartitionKeySelectionTests` |
| The four-tier HTAP architecture, with the columnstore-index tier as C3 | With only two tiers, a light-AP workload gets pushed toward approximately 2x redundancy | `StorageArchitectureTests` |
| A columnstore replica is eventually consistent | A strongly-consistent AP query cannot use the replica | `StorageArchitectureTests` |
| The `TABLE_MODE` axis is major-compaction aggressiveness | "Queuing intensity" is the wrong criterion | `TableModeSemanticsTests` |
| "Queuing intensity" appears only in a corrective context | Prevents the corrected wording from being reverted | `TableModeSemanticsTests` |
| Hotspots split by read/write direction first; the `read_hot_row` type exists | Treating a read hotspot as a write hotspot is pure wasted effort | `HotspotDirectionTests` |
| Read hotspots use a duplicated table, not bucketing | Bucketing amplifies reads by N times | `HotspotDirectionTests` |
| The specialized-index predicate allowlist, the existing-table sys switch, the Chinese-text tokenizer | Missing any one of the three means the capability is unusable | `SpecialIndexTests` |
| The multi-value-index `EXPLAIN` criterion cannot rely on the operator name alone | Even on a hit, the operator name can still read `TABLE FULL SCAN` | `SpecialIndexTests` |
| Every hard-required input field has a collection path | Setting up a gate with no way through it just leaves the user making up numbers | `InputCollectionTests` |
| Review mode also points to the collection file | Review's own entry point would otherwise get stuck the same way | `InputCollectionTests` |
| Registered official-source conflicts (primary key, auto-increment column type, Oracle subset rule) | Picking one side arbitrarily can veto an officially recommended, legal design | `OfficialConflictTests` |
| Every `checks` item present, evidence rules, table-group risk branching by version | The output contract is the interface downstream consumers rely on | `OutputContractTests` |
| The anti-pattern count matches the number cited in SKILL.md | Prevents the two counts from drifting apart | `AntiPatternTests` |
| **NDV vs. partition count is L1-B, not L0** -- absent from the L0 block, present in the blocker block | Classifying a legal statement as L0 blocks DDL generation for designs the server accepts | `L0Tests` |
| The blocker tier has an override (`accepted_with_reason` / `accepted_reason`) | Without one, "verdict defaults to fail" silently becomes "always fails" | `L0Tests` |
| Only criterion 3 of the four partition-key criteria is parser-enforced | Presenting all four as one hard gate is the original defect | `L0Tests` |
| **`NOCACHE` is Oracle sequence syntax**, and the MySQL option is an integer | Recommending it for MySQL emits a syntax error, not a slower-but-gapless table | `AutoIncrementModeGateTests` |
| The MySQL BNF mirror genuinely has no `NOCACHE` keyword | The factual basis; a refreshed BNF that adds it voids the rule | `AutoIncrementModeGateTests` |
| The cache-disabling value stays `unverified` | Promising gapless numbering on an unconfirmed value is the over-claim this skill exists to prevent | `AutoIncrementModeGateTests` |
| The Tablet ceiling parameters and the min(A,B) dual formula | `check_consistency.py`'s paired rule is conditional on the parameter name, so renaming it disarms the guard rather than failing it | `TabletCapacityTests` |
| Every script carrying a `--self-test` is wired into `run_regression.sh` | An unwired self-test is dead code that reads as coverage | `RegressionRunnerTests` |
| The size budget checks words, not only lines | A line budget lets sections grow verbose without growing the file | `RegressionRunnerTests` |
| The word budget keeps real headroom, not two words | A budget with no slack is a tripwire; the next commit trips it and the ceiling gets raised, retiring the constraint | `CountClaimTests` |
| **No prose restates a count of something countable** -- runner stages, reference files, L0 items | Two of these had silently drifted ("six checks" vs ten stages; ">= 12" L0 items vs 11). A count in prose is a second copy of a fact and nobody updates it | `CountClaimTests` |
| Every rule in `cases.json` is either mutated or explicitly exempted, and exemptions stay under a quarter | Closure in one direction only ("every mutation maps to a real rule") said nothing about the 28 rules that were in neither list | `MutationCoverageTests` |
| The output grader is calibrated against known-verdict fixtures | An uncalibrated grader silently rewrites every result it produces | `run_cases.py --self-test` |

### 2.3 The Validator's Own Validator

| Check | Case |
|---|---|
| `strip_inline_code` **keeps the link label** (once caused 22 links to be missed entirely) | `LinterSelfRegressionTests` |
| `strip_inline_code` still masks BNF fragments (the original intent must not be lost) | `LinterSelfRegressionTests` |
| `strip_inline_code` substitutes with an equal-length sentinel (a width change would break adjacency rules) | `LinterSelfRegressionTests` |
| A broken link really is caught by the link checker | `LinterSelfRegressionTests` |
| Every rule's `source` file exists | `CasesRegistryTests` |
| All 9 new rules are registered in `cases.json` and each has a case | `CasesRegistryTests` |
| The corpus really is loaded (a negative control, preventing an empty assertion from passing vacuously) | `GoldenNegativeControlTests` |

### 2.4 Golden Scenarios (10)

| Fixture | Scenario |
|---|---|
| `001_autoinc_mode_gate` | Oracle-mode auto-increment primary key -> IDENTITY / sequence |
| `002_tenant_default_format` | Omitting Column Group when the tenant default is columnstore |
| `003_ndv_gt_partitions` | HASH-partitioning a low-cardinality column |
| `004_htap_foutiers` | The cheapest tier for mostly-TP plus light AP |
| `005_tablemode_compaction` | The criterion for escalating a queuing table's tier |
| `006_hotspot_read_direction` | A read hotspot on a config table |
| `007_special_index` | A JSON array containment query (existing table) |
| `008_input_collection` | The user cannot obtain the quantified inputs |
| `009_doc_conflict_split` | A columnstore ETL table with no primary key |
| `010_special_index` | A full-text index over Chinese-language text |

---

## 3. UNCHECKED -- Explicitly Written-Down Gaps

These are **not** within the capability of this test suite. They are written down so that "all green" is never read as "verified."

| Gap | Why it cannot be tested here | Who closes it |
|---|---|---|
| Whether the generated DDL executes on the target version | Requires a real OceanBase instance | `tests/integration/` (delivered, **not yet run**) |
| Whether the execution plan really prunes partitions / localizes joins | Requires `EXPLAIN` | V3, `verification.md` |
| The gap between the actual Tablet count and the estimate | Requires `DBA_OB_TABLETS` | V4 |
| Whether the L2 empirical thresholds (per-partition size, hit rate, Tablet headroom) are reasonable | Requires benchmarking | V5 |
| **Whether the Agent actually follows these rules** | This suite only proves the rule text exists, not that the model complies | `run_cases.py --grade` (requires recording Agent output first) |
| Whether a *correct* Agent answer would be graded correctly | The grader is now calibrated on 11 synthetic answers, which is not the same as 45 real ones | `run_cases.py --grade` on real output |
| Prose prohibitions where an incidental negation appears in the same clause | Refutation awareness on free prose cannot be airtight; the limit is recorded as a fixture | prefer `expected_checks` for new expectations |
| Trigger accuracy (how good the `description` is) | Requires a with/without-skill A/B test | skill-creator evaluation |
| Whether the rules still hold after the official documentation is updated | A text-only test cannot sense an upstream change | Manual review + the BNF-grounding check raises an alarm when the mirror is refreshed |
| The 8 open items such as the Oracle-mode HASH partition-key type allowlist | Not given by the official documentation | `capability-matrix.md` §5, needs empirical testing |

**In one sentence**: `scripts/tests` all green == "the rules are written correctly, are mutually
consistent, have not been reverted, and are guarded by assertions that actually bite"; it does
**not** mean "the design will run," nor "the Agent will comply."

The mutation sweep moves the first clause forward but not the last two. It cannot make a
text-only suite say anything about a real instance or a real model run — those remain open,
and remain listed in the gap table above.
