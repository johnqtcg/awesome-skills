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
