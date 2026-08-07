# Replication, RLS and Extension Migrations

Supplementary to SKILL.md §5.5. These three areas are **in scope for review but not
covered by `scripts/lint_migration.py`** — there is no automated rule for them. Work
through the checklists here by hand and record the result in §9.9 Uncovered Risks.

---

## 1. Logical Replication

### DDL is not replicated

Logical replication ships row changes, not schema changes. Nothing in the WAL stream
tells a subscriber that a column appeared. If the publisher starts sending rows whose
shape the subscriber's table cannot accept, **apply on the subscriber stops with an
error** and the subscription falls behind until someone intervenes. The replication
slot keeps retaining WAL in the meantime, so the publisher's disk fills.

So "replication: logical" is not a context field to record and move on from — it
changes the order of operations for the whole migration.

### Ordering rules

| Change | Order |
|--------|-------|
| ADD COLUMN (nullable, or with default) | **Subscribers first**, then publisher |
| DROP COLUMN | **Publisher first**, then subscribers |
| ADD COLUMN NOT NULL without default | Subscribers first, and the subscriber needs a default or the inserts fail |
| RENAME COLUMN | Avoid. Use add-new + dual-write + drop-old; a rename breaks the column mapping |
| ALTER COLUMN TYPE | Widen on subscribers first; the subscriber's type must accept every value the publisher can send |

The asymmetry is the thing to remember: on **additions** the subscriber must be ready
before data arrives; on **removals** the publisher must stop sending before the
subscriber loses the column.

### Publication settings that change what must match

- **Column lists** (`ALTER PUBLICATION p SET TABLE t (a, b)`, PG 15+) — only the listed
  columns are replicated. Adding a column does *not* add it to an existing column list;
  the publication must be altered explicitly or the new column silently never
  replicates.
- **Row filters** (`WHERE` on a published table, PG 15+) — the filter expression may
  only reference replicated columns. Dropping a column used in the filter breaks the
  publication.
- **`publish_via_partition_root`** — determines whether partition DDL is visible as
  parent-table changes or per-partition changes. Re-verify after any partition
  attach/detach.
- **`REPLICA IDENTITY`** — `UPDATE`/`DELETE` need one. A table with `REPLICA IDENTITY
  DEFAULT` and no primary key cannot replicate updates. Dropping or replacing a primary
  key silently breaks update replication; set `REPLICA IDENTITY USING INDEX` or `FULL`
  before the swap.

### Verification (run before declaring the phase done)

```sql
-- On the subscriber: is apply actually progressing?
SELECT subname, pid, received_lsn, latest_end_lsn, latest_end_time
FROM pg_stat_subscription;

-- Any subscription in error? (PG 15+)
SELECT * FROM pg_stat_subscription_stats;

-- On the publisher: is any slot retaining WAL?
SELECT slot_name, active, restart_lsn,
       pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn)) AS retained
FROM pg_replication_slots;
```

A growing `retained` figure with `active = false` is the signature of a halted
subscription. Treat it as an incident, not a lag metric.

### Streaming (physical) replication

Physical replicas replay WAL, so DDL arrives automatically and none of the ordering
above applies. Two effects still matter:

- **A table rewrite ships the entire new heap as WAL.** Rewriting a 200 GB table
  generates on the order of 200 GB of WAL. Check replica bandwidth, WAL archive
  capacity, and `max_slot_wal_keep_size` before starting.
- **`max_standby_streaming_delay` vs AccessExclusiveLock.** Replaying an
  AccessExclusiveLock on a replica cancels conflicting read queries there. A migration
  that looks fine on the primary can cancel analytics queries on the replica.

---

## 2. Row-Level Security

### Lock level

`CREATE POLICY`, `ALTER POLICY`, `DROP POLICY`, and `ALTER TABLE ... ENABLE/DISABLE ROW
LEVEL SECURITY` all take **AccessExclusiveLock** on the table — reads block. They are
fast (catalog-only), so the standard `lock_timeout` + retry approach applies.

### Failure mode 1: enabling RLS before writing policies

```sql
-- WRONG: between these two statements, and after the first if the second is
-- forgotten, every non-owner role sees ZERO rows. Silent, total data denial.
ALTER TABLE accounts ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON accounts USING (tenant_id = current_tenant());
```

```sql
-- RIGHT: policy first, then enable. Both in one transaction so there is no window.
BEGIN;
SET LOCAL lock_timeout = '3s';
CREATE POLICY tenant_isolation ON accounts USING (tenant_id = current_tenant());
ALTER TABLE accounts ENABLE ROW LEVEL SECURITY;
COMMIT;
```

The default with RLS enabled and no matching policy is deny, not allow. There is no
error and no log line — queries simply return nothing.

### Failure mode 2: testing as the wrong role

Table **owners bypass RLS** unless `FORCE ROW LEVEL SECURITY` is set, and roles with
the `BYPASSRLS` attribute bypass it always. Verifying the migration as the owner or as
a superuser proves nothing about what the application will see.

```sql
-- Verify as the actual application role
SET ROLE app_user;
SELECT count(*) FROM accounts;          -- must match expectations for this tenant
RESET ROLE;

-- Check whether the owner is being fooled
SELECT relname, relrowsecurity, relforcerowsecurity
FROM pg_class WHERE relname = 'accounts';

-- Enumerate effective policies
SELECT polname, polcmd, pg_get_expr(polqual, polrelid) AS using_expr,
       pg_get_expr(polwithcheck, polrelid) AS check_expr
FROM pg_policy WHERE polrelid = 'public.accounts'::regclass;
```

### Failure mode 3: unindexed policy predicates

A policy's `USING` expression is evaluated per row on every query against the table.
If `tenant_id` is unindexed, a policy on `tenant_id` turns every lookup into a scan and
the regression appears as a general slowdown with no changed query. Build the index
**CONCURRENTLY before** creating the policy.

### `WITH CHECK` vs `USING`

- `USING` filters which existing rows are visible (SELECT/UPDATE/DELETE).
- `WITH CHECK` constrains which rows may be written (INSERT/UPDATE).
- Omitting `WITH CHECK` on an `ALL` or `INSERT` policy makes `USING` apply to writes
  too — usually intended, but state it explicitly rather than relying on the default.

A policy that permits reading a row but not writing the same value back produces
"new row violates row-level security policy" on an otherwise valid UPDATE. Test both
directions.

---

## 3. Extensions

### `CREATE EXTENSION` / `ALTER EXTENSION ... UPDATE` run arbitrary SQL

An extension's install and upgrade scripts are ordinary SQL files shipped by the
extension author. They may create tables, take any lock, rewrite data, or run for a
long time. The lock behaviour is **not** knowable from the DDL you wrote — it is a
property of the script. Treat extension work as unbounded-risk DDL:

```sql
-- What is installed, and what could it move to?
SELECT extname, extversion FROM pg_extension;
SELECT * FROM pg_available_extension_versions WHERE name = 'pg_stat_statements';

-- Pin the version explicitly, and FAIL LOUDLY when the pin is not available here
-- rather than discovering it mid-migration. 1.9 ships on every major from 14 to 18;
-- substitute the version you actually verified for your target.
DO $$
DECLARE
  want text := '1.9';
  have text;
BEGIN
  SELECT extversion INTO have FROM pg_extension
   WHERE extname = 'pg_stat_statements';

  IF have IS NULL THEN
    IF NOT EXISTS (SELECT 1 FROM pg_available_extension_versions
                   WHERE name = 'pg_stat_statements' AND version = want) THEN
      RAISE EXCEPTION 'pg_stat_statements % is not available on this server; it has: %',
        want, (SELECT string_agg(version, ', ' ORDER BY version)
                 FROM pg_available_extension_versions WHERE name = 'pg_stat_statements');
    END IF;
    EXECUTE format('CREATE EXTENSION pg_stat_statements VERSION %L', want);
  ELSIF have <> want THEN
    RAISE EXCEPTION
      'pg_stat_statements is installed at %, expected %; review ALTER EXTENSION UPDATE separately',
      have, want;
  END IF;
END $$;
```

This deliberately has three outcomes: create the target version when absent, do
nothing when the installed version matches, and fail when it differs. Do not turn the
third case into an automatic `ALTER EXTENSION UPDATE`; its upgrade SQL needs a separate
lock, rewrite, compatibility, and rollback review.

**Never hard-code an extension version into a migration that runs on more than one
server major.** The set of shipped versions differs per major, and asking for one that
is not there is a hard failure, not a downgrade. Measured across the supported range:

| Major | `pg_stat_statements` default | Is `1.10` installable? |
|:-----:|:---:|---|
| 14 | 1.9 | **No** — `ERROR: extension "pg_stat_statements" has no installation script nor update path for version "1.10"` |
| 15 | 1.10 | Yes |
| 16 | 1.10 | Yes |
| 17 | 1.11 | Yes |
| 18 | 1.12 | Yes |

Note what this costs a reviewer: a syntax check passes it. The failure is SQLSTATE
`22023` (invalid_parameter_value), raised at execution, so any validation that only
rejects parse errors will report the statement as fine. Resolve the version from
`pg_available_extension_versions` on the target server, or omit `VERSION` and let the
server pick its default — but then record which default you got.

Before running an upgrade in production, read the upgrade script for the exact version
transition — the packaged `<ext>--<from>--<to>.sql`. A one-line `ALTER EXTENSION` can
contain a table rewrite.

**There is no `extension_destdir` setting on PostgreSQL 14–18** (verified absent from
`pg_settings` on live 14.23 and 18.4). Locate the scripts through `pg_config` instead:

```sql
SELECT setting FROM pg_config WHERE name = 'SHAREDIR';   -- scripts live in <SHAREDIR>/extension
```

```bash
ls "$(pg_config --sharedir)/extension/" | grep '^pg_stat_statements'
```

An extension's `.control` file may set `directory = ...` to relocate its scripts, so
read the control file when the expected path is empty.

### Checklist

- [ ] Version pinned explicitly, not left to the packaged default
- [ ] Target version confirmed present in `pg_available_extension_versions`
- [ ] Managed-provider availability verified (RDS, Cloud SQL and Azure each ship a
      restricted, differently-versioned set)
- [ ] Upgrade script read; any DDL it performs assessed against §5 like ordinary DDL
- [ ] Rollback assessed — most extensions have no downgrade path, so treat the upgrade
      as **irreversible** and classify it that way in §9.7
- [ ] Dependent objects checked: `DROP EXTENSION` fails or cascades into application
      objects that reference its types and functions
- [ ] If the extension provides types used in columns (`postgis`, `hstore`, `citext`),
      the extension upgrade and any column type change are the same migration, not two

### Extensions relevant to migration work itself

| Extension | Role | Caveat |
|-----------|------|--------|
| `pg_repack` | Online table reorganisation | Cannot change a schema — see `large-table-migration.md` §1 |
| `pg_stat_statements` | Find the queries a migration slowed | Adds shared-memory overhead; needs a restart to install |
| `pgstattuple` | Measure real bloat before deciding to repack | Reads the whole table |
| `pg_cron` | Schedule batched backfills server-side | Jobs run as the scheduling role; RLS applies |
