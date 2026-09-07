# Official Sources

The target version's own documentation is the final authority on syntax and capability.
When this skill and the official docs disagree, the docs win — and the disagreement
belongs in `doc-gaps.md` so the next reader inherits the correction rather than
rediscovering it.

Two links per claim is the standard here: a syntax page and, where the claim is a design
recommendation rather than a parser rule, the best-practices page it came from. That
distinction is what keeps a *suggestion* from being written up as a hard constraint —
the mistake that put partition-key cardinality in the L0 checklist for as long as it was
there.

## Syntax reference

- [MySQL-mode CREATE TABLE](https://www.oceanbase.com/docs/common-oceanbase-database-cn-1000000004479546)
- [Oracle-mode CREATE TABLE](https://www.oceanbase.com/docs/common-oceanbase-database-cn-1000000004480962)
- [Automatic partition splitting](https://www.oceanbase.com/docs/common-oceanbase-database-cn-1000000004479331)
- [Table group overview](https://www.oceanbase.com/docs/common-oceanbase-database-cn-1000000005283503)
- [Partitioned indexes](https://en.oceanbase.com/docs/common-oceanbase-database-10000000003454860)
- [Columnstore replicas](https://en.oceanbase.com/docs/common-oceanbase-database-10000000001719945)
- [Auto-increment columns](https://en.oceanbase.com/docs/common-oceanbase-database-10000000000829618)

## Partition lifecycle (Oracle mode, standalone V4.4.2 LTS)

These pages carry the rules in `partitioning.md` §4.1 / §5 — the global-index interaction, the
per-combination support matrix, the one-way doors, and the INTERVAL restrictions. They are cited
individually because several of the statements exist on **only one** of them, and because two of
them contradict each other in a way recorded in `doc-gaps.md` §7.

- [Create a partitioned table](https://www.oceanbase.com/docs/common-oceanbase-database-standalone-1000000006077662)
  — INTERVAL restrictions (first-level only, key type allowlist, mutual exclusion with
  `DYNAMIC_PARTITION_POLICY`); `DEFAULT` / `MAXVALUE` blocking `ADD PARTITION`
- [Drop a partition](https://www.oceanbase.com/docs/common-oceanbase-database-standalone-1000000006077656)
  — `UPDATE GLOBAL INDEXES` rule, lazy-maintenance exclusions, drop support matrix
- [Truncate a partition](https://www.oceanbase.com/docs/common-oceanbase-database-standalone-1000000006077663)
  — same rule restated for TRUNCATE, truncate support matrix
- [Add a partition](https://en.oceanbase.com/docs/common-oceanbase-database-10000000001717062)
  (V4.3.3) — `ADD SUBPARTITION` requires a non-templated table; add support matrix; adding a
  RANGE/LIST partition does not affect indexes
- [Modify partition rules](https://www.oceanbase.com/docs/common-oceanbase-database-standalone-1000000006077657)
  — repartitioning and RANGE↔INTERVAL only; **no `MODIFY PARTITION … ADD VALUES`**
- [Column constraints](https://www.oceanbase.com/docs/common-oceanbase-database-standalone-1000000006077652)
  — primary key = NOT NULL + unique; unique permits multiple NULLs (`indexes.md` §1.1.1)
- [Modify a table](https://www.oceanbase.com/docs/common-oceanbase-database-cn-1000000000641844)
  (V4.3.0) — row/columnstore conversion via `ALTER TABLE ADD/DROP COLUMN GROUP`
- [ALTER TABLE](https://en.oceanbase.com/docs/common-oceanbase-database-10000000001106227)
  (V4.2.1) — `DESC` not supported on index columns; the `ALTER TABLE` production list

> Version caveat: these are V4.4.2 / V4.3.5 / V4.3.3 / V4.3.0 / V4.2.1 pages while this skill's
> syntax baseline is V4.5.0. Directionally reliable, but a design that hinges on one of them
> should confirm on the actual target version.

## Best practices

These are the source of this skill's tenant-default gating (§2.1), the four-tier HTAP
architecture, the quantitative partition-key criteria, read/write hotspot classification,
`TABLE_MODE` semantics, auto-increment skip magnitude, and the specialized indexes.

- [Table design and index optimization](https://en.oceanbase.com/docs/common-best-practices-10000000002431625)
- [Hotspot tables](https://en.oceanbase.com/docs/common-best-practices-10000000002727359)
- [Auto-increment columns and sequences](https://en.oceanbase.com/docs/common-best-practices-10000000002807692)
- [Database development](https://en.oceanbase.com/docs/common-best-practices-10000000001824695)
- [Hot-row updates](https://en.oceanbase.com/docs/common-best-practices-10000000001953531)
- [Indexing large tables](https://en.oceanbase.com/docs/common-best-practices-10000000001824694)

## What these pages state as a *recommendation*, not a restriction

Recorded explicitly, because reading a best-practices page as a parser rule is how a
legal design gets rejected:

| Claim | Framing in the official docs | Tier here |
|---|---|---|
| HASH partition key should have high cardinality | "Suggestions on using partitioned tables" — a selection suggestion | **L1-B** (B1) |
| Partition count should be a power of two | Even distribution is *best* at a power of two | **L1** |
| Partition key should appear in query filters | Pruning guidance | **L1-B** (B2) |
| MySQL HASH/RANGE/LIST key must be integer or YEAR | `CREATE TABLE` production — the parser rejects otherwise | **L0** (item 5) |
| Oracle mode has no `AUTO_INCREMENT` | Absent from the `table_option` production | **L0** (item 11) |
| MySQL `auto_increment_cache_size` takes an integer | `auto_increment_cache_size [=] INT_VALUE`; no `NOCACHE` token | **L0** (`doc-gaps.md` §2.3.1) |
