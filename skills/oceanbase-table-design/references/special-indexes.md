# Dedicated Indexes: JSON Multi-Value Index and Full-Text Index

Local and global indexes solve "equality or range filtering by column." There are two kinds of filtering that **ordinary indexes cannot help with at all** —
a full table scan is the only fallback. The official "Table Design and Index Optimization Best Practices" guide devotes two separate sections to this:

| Requirement | Why an ordinary index doesn't work | Correct approach |
|---|---|---|
| JSON array "contains a given value" | The index is built on the whole JSON column and cannot locate individual array elements | **JSON multi-value index** |
| Fuzzy search / relevance ranking over large text | `LIKE '%x%'` cannot use an index; relevance ranking cannot be expressed by rewriting SQL | **Full-text index** |

The decision entry point is `access_patterns.filter` from Step 1: if any of the shapes in the table above appears, this file must be evaluated —
**you cannot just pick between local and global index and call it done.**

<!-- toc -->

**Table of Contents**

- [1. JSON Multi-Value Index](#1-json-multi-value-index)
  - [1.1 Trigger Criteria (Predicate Allowlist)](#11-trigger-criteria-predicate-allowlist)
  - [1.2 Syntax](#12-syntax)
  - [1.3 Warning: Adding an Index to an Existing Table Requires a sys-Tenant Switch](#13-warning-adding-an-index-to-an-existing-table-requires-a-sys-tenant-switch)
  - [1.4 Execution Plan Verification Point (V3)](#14-execution-plan-verification-point-v3)
- [2. Full-Text Index](#2-full-text-index)
  - [2.1 Syntax](#21-syntax)
  - [2.2 Execution Plan Verification Point (V3)](#22-execution-plan-verification-point-v3)
  - [2.3 Adding an Index to an Existing Table](#23-adding-an-index-to-an-existing-table)
- [3. Interaction with Other Decisions in This Skill (Must Check)](#3-interaction-with-other-decisions-in-this-skill-must-check)
- [4. Output Contract](#4-output-contract)

<!-- /toc -->

## 1. JSON Multi-Value Index

### 1.1 Trigger Criteria (Predicate Allowlist)

The multi-value index is only used when one of the following predicates appears in `WHERE`:

- `MEMBER OF()`
- `JSON_CONTAINS()`
- `JSON_OVERLAPS()`

Typical scenarios: many-to-many relationships (a movie with multiple actors), tags/categories (a product with multiple tags).

### 1.2 Syntax

```sql
CREATE TABLE user_info (
    user_id BIGINT,
    name    VARCHAR(1024),
    age     BIGINT,
    hobbies JSON,
    INDEX idx1 ((CAST(hobbies->"$[*]" AS UNSIGNED ARRAY)))
);
```

Key points:

- The index expression must be written as `CAST(<json_path> AS <type> ARRAY)`; the `ARRAY` keyword is what marks it as a multi-value index.
- The `CAST` target type must match the actual type of the array elements. In the example above, `UNSIGNED ARRAY` is used for a numeric array;
  a string array requires the corresponding `CHAR(n) ARRAY` form per the target version's documentation.

### 1.3 Warning: Adding an Index to an Existing Table Requires a sys-Tenant Switch

**Adding a JSON multi-value index to an existing table is disabled by default** and must be enabled in the sys tenant:

```sql
ALTER SYSTEM SET _enable_add_fulltext_index_to_existing_table = true;
```

This is one of the rare cases in this Skill where "the DDL is valid but fails because the environment hasn't enabled it" — equivalent to the relationship between `enable_auto_split`
and `SIZE` (see `partitioning.md` §3.2). Therefore:

- **At table-creation time**, creating the index together with the table definition → no switch needed.
- **`CREATE INDEX` on an existing table** → the switch must be listed as a precondition and recorded in warnings and the verification checklist;
  the Agent has no authority to assume it is already enabled.
- Parameter names starting with `_` are hidden configuration items — **confirm with the DBA before changing**, and verify it still exists in the target version
  (mark as `unverified`).

### 1.4 Execution Plan Verification Point (V3)

```sql
EXPLAIN SELECT user_id, name FROM user_info
 WHERE JSON_CONTAINS(hobbies->'$[*]', CAST('["hiking"]' AS JSON));
```

- Miss: the operator is `TABLE FULL SCAN`, and `NAME` is the base table name.
- Hit: `NAME` becomes `user_info(idx1)`, `range_key` shows the multi-value index's internal column
  (of the form `SYS_NC_mvi_*`), accompanied by `is_index_back=true`.

**Note**: even after hitting the multi-value index, the operator name may still display `TABLE FULL SCAN` — the criterion is the index name inside `NAME` and
`range_key`, not the literal operator name. Looking only at the operator name will lead to the mistaken conclusion that "the index didn't take effect."

## 2. Full-Text Index

### 2.1 Syntax

```sql
CREATE TABLE articles (
  id      INT AUTO_INCREMENT,
  title   VARCHAR(255),
  content TEXT,
  PRIMARY KEY (id),
  FULLTEXT ft1 (content) WITH PARSER SPACE
);
```

Query and relevance scoring:

```sql
SELECT id, title, MATCH(content) AGAINST('OceanBase database') AS score
  FROM articles
 WHERE MATCH(content) AGAINST('OceanBase database');
```

- `WITH PARSER <parser>` specifies the tokenizer. `SPACE` tokenizes on whitespace, which suits English; **Chinese text must not use `SPACE`** —
  otherwise the entire passage is treated as a single token and search effectively fails. Choose a Chinese tokenizer per the target version's documentation (`unverified`, requires testing).
- Sorting by descending `MATCH(...) AGAINST(...)` score is what produces relevance ranking.

### 2.2 Execution Plan Verification Point (V3)

When the full-text index is hit, the operator is **`TEXT RETRIEVAL SCAN`**, `NAME` is `articles(ft1)`,
and `calc_relevance=true` and `pushdown_match_filter` appear. Seeing `TABLE FULL SCAN` means it was not hit.

### 2.3 Adding an Index to an Existing Table

Same switch as in §1.3 (the parameter name itself is `_enable_add_fulltext_index_to_existing_table`).

## 3. Interaction with Other Decisions in This Skill (Must Check)

This section is the main reason this file exists — these two index types are not standalone options; they can **override decisions already made elsewhere**:

| Interaction | Conclusion |
|---|---|
| **Automatic partition splitting** | `partitioning.md` §3.1: automatic splitting **is not supported** when the table has a **full-text index / spatial index / vector index**. Whether a JSON multi-value index is subject to the same restriction is not listed in the official limitations → `unverified`, requires testing |
| **Write amplification** | Both index types are maintained synchronously with insert/update/delete on the JSON/text column, increasing write cost; the official documentation explicitly requires "weighing write frequency against query needs." Do not add these by default on high-write tables |
| **Storage overhead** | Both consume extra storage (the official documentation gives no specific multiplier → do not fabricate a number, mark `unverified`, require testing) |
| **Archival tables** | Same logic as global indexes: adding a dedicated index on top of a table that rolls off data by dropping partitions requires evaluating the index-maintenance cost of dropping partitions (`partitioning.md` §4.1) |
| **Local vs. global** | Dedicated indexes also have local/global variants; the cost decision still goes through the `index_decision` contract in `indexes.md` §2.1 — this file only addresses "should this category of index be used at all" |
| **Columnstore tables** | Whether these two index types can be built on a columnstore table is not addressed by the official best practices → `unverified` |

## 4. Output Contract

```yaml
special_index:
  - kind: json_multivalue | fulltext
    column:
    trigger_predicate:            # The predicate or search shape that was hit (from access_patterns.filter)
    ddl_fragment:
    created_with_table: true | false      # Required if false: see the next field
    existing_table_switch_required:       # _enable_add_fulltext_index_to_existing_table
      required: true | false
      confirmed: true | false | unverified
    parser:                       # Full-text index only; must not be SPACE for Chinese-language corpora
    write_amplification_note:     # Required
    storage_overhead: unverified  # No multiplier given officially; fabrication is forbidden
    autosplit_conflict: true | false | unverified
    explain_expectation:          # Expected operator / NAME / range_key, for V3 verification
    result: pass | fail | unverified
```

When there is no triggering predicate at all, output `special_index: not_applicable` — do not force an index onto the design just for "feature completeness."
