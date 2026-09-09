# MySQL 8.0 `ALGORITHM=INSTANT` and Metadata Locks: Reconciling the Manual's "Contradiction"

## Verdict (for the runbook)

**Both statements are true; they are not actually in conflict once you separate lock *mode* (shared vs. exclusive) from lock *duration*.**

- A metadata lock (MDL) of some mode is held for the **entire** `ALTER TABLE ... ALGORITHM=INSTANT` statement (from the moment it starts to the moment it commits).
- For almost that whole duration the lock is a **shared-upgradable** MDL, which does **not** block concurrent reads or writes.
- The lock is only **EXCLUSIVE** (the mode that blocks everything) for a **brief** moment at the very end, when the new table definition is committed and old caches are evicted.

So: "takes a metadata lock for the whole operation" (true, if you mean *any* MDL) and "only briefly" (true, if you mean the *exclusive* MDL) are describing two different things, not contradicting each other. The dangerous part for a maintenance window is not the brief exclusive phase itself — it's that this brief exclusive phase **must wait for every other session's pre-existing metadata lock on the table to be released first**, and while it waits, it **queues in front of and blocks every subsequent statement** against that table, including plain `SELECT`s. A "fast, non-blocking" INSTANT DDL can therefore stall for as long as the longest-running open transaction that has touched the table, and everything behind it stalls too.

---

## The two pages, and why they look like they disagree

**Page A — "Online DDL Performance and Concurrency"**
`https://dev.mysql.com/doc/refman/8.0/en/innodb-online-ddl-performance.html` (MySQL 8.0 Reference Manual §17.12.2)

Near the top of the page, in a bullet list of "how online DDL improves things," it currently reads:

> "Instant operations only modify metadata in the data dictionary. **An exclusive metadata lock on the table may be taken briefly during the execution phase of the operation.** Table data is unaffected, making operations instantaneous. Concurrent DML is permitted."

Further down the *same page*, under the heading **"Online DDL and Metadata Locks,"** it describes a **three-phase model that applies to all online DDL, INSTANT included**:

> "Online DDL operations can be viewed as having three phases:
> **Phase 1: Initialization** — ... a shared upgradeable metadata lock is taken to protect the current table definition.
> **Phase 2: Execution** — ... Whether the metadata lock is upgraded to exclusive depends on the factors assessed in the initialization phase. If an exclusive metadata lock is required, it is only taken briefly during statement preparation.
> **Phase 3: Commit Table Definition** — ... the metadata lock is upgraded to exclusive to evict the old table definition and commit the new one. Once granted, the duration of the exclusive metadata lock is brief.
> Due to the exclusive metadata lock requirements outlined above, an online DDL operation may have to wait for concurrent transactions that hold metadata locks on the table to commit or rollback. ... a pending exclusive metadata lock requested by an online DDL operation blocks subsequent transactions on the table."

**Page B — `ALTER TABLE` statement reference**
`https://dev.mysql.com/doc/refman/8.0/en/alter-table.html` ("Performance and Space Requirements" section)

> "`INSTANT`: Operations only modify metadata in the data dictionary. **An exclusive metadata lock on the table may be taken briefly during the execution phase of the operation.** Table data is unaffected, making operations instantaneous. Concurrent DML is permitted. (Introduced in MySQL 8.0.12)"

Read today, Pages A and B actually agree with each other and with the three-phase model. If what you found reads differently — e.g., a copy that flatly states **"No metadata locks are taken on the table"** for INSTANT — you are looking at **superseded wording**. That exact sentence really did exist on both pages until mid-2022, and it really did contradict the three-phase section on the same page. Here is the paper trail:

---

## Evidence the "No metadata locks are taken" wording was a documented error, since corrected

1. **Historical text (Wayback Machine, captured 2019–2022‑05‑09), Page A:**
   `https://web.archive.org/web/20191108072444/https://dev.mysql.com/doc/refman/8.0/en/innodb-online-ddl-performance.html`

   > "Instant operations only modify metadata in the data dictionary. **No metadata locks are taken on the table**, and table data is unaffected, making operations instantaneous. Concurrent DML is unaffected."

2. **MySQL Bug #106480 — "ALGORITHM=INSTANT takes exclusive metadata lock on table"**
   `https://bugs.mysql.com/bug.php?id=106480` (filed 17 Feb 2022, closed 13 May 2022, category "MySQL Server: Documentation")

   The reporter demonstrated with a 3-session repro (open transaction holding a shared read lock on the table → `ALTER TABLE ... ALGORITHM=INSTANT` blocks waiting for exclusive MDL → a plain `SELECT` from a third session then queues behind the blocked `ALTER TABLE`) that INSTANT DDL **does** take an exclusive MDL, and quoted the exact same "No metadata locks are taken on the table" line from both Page A and Page B as incorrect.

   MySQL's own Verification Team responded:

   > "documentation is correct regarding the exclusive lock. This variant of DDL takes the share lock, except at the very end, where it takes exclusive lock for a very short time." (17 Feb 2022)

   and, after further discussion:

   > "It turns out that this particular feature is not documented sufficiently. ... ALTER TABLE needs to invalidate all these caches at some point and update them while ensuring that there is no concurrent statement are using them, for which we acquire exclusive lock. ... Regarding the exclusive lock, it will be taken only once for the table ... before calling storage engine's inplace or instant ALTER TABLE commit hook/invalidating caches and updating data dictionary. This should be also added to our documentation. **Verified as a documentation request.**" (18 Feb 2022)

   Oracle's documentation team then confirmed the fix:

   > "The referenced documentation has been revised. The changes should appear online soon." — Daniel Price, MySQL documentation, 13 May 2022.

3. **Confirmed transition point in the Wayback Machine capture history for Page A** (`innodb-online-ddl-performance.html`): the "No metadata locks are taken on the table" wording is present through the **2022‑05‑09** capture and is replaced by "An exclusive metadata lock on the table may be taken briefly during the execution phase of the operation" by the **2022‑07‑26** capture — consistent with the bug's May 2022 resolution date and shipping with the MySQL 8.0.30 documentation refresh (2022‑07‑26 GA).

4. **Current live wording (verified via the most recent archived crawls, 2026)** on both Page A and Page B now matches the corrected text quoted above, and is internally consistent with the "Online DDL and Metadata Locks" three-phase section that was never changed (it was correct all along — it's a general statement about *all* online DDL operations, INSTANT included).

**Access note on sourcing:** `dev.mysql.com` and `bugs.mysql.com` returned an Oracle edge/WAF "Technical Difficulties" block page to this session's direct fetches; all quotations above were retrieved from the Internet Archive's Wayback Machine cache of the same canonical `dev.mysql.com` / `bugs.mysql.com` URLs (snapshot timestamps cited inline), which serves the identical Oracle-published content. If you want to eyeball the live pages yourself before the maintenance window, just open the two URLs in a normal browser — the block only affected this session's automated fetch, not the pages themselves.

---

## What this means mechanically (for the runbook)

Apply the three-phase model uniformly, INSTANT included:

| Phase | What happens | Lock held | Blocks concurrent reads/writes? |
|---|---|---|---|
| 1. Initialization | Server decides concurrency level for this ALTER | Shared-upgradable MDL | No |
| 2. Execution | Statement prepared/executed; for INSTANT this is just a dictionary metadata change (no rebuild, no data copy) | May briefly upgrade to exclusive during preparation | Only for the brief upgraded instant, if it happens |
| 3. Commit table definition | Old table definition evicted, new one committed | Upgraded to exclusive | Yes, but normally for milliseconds |

The risk is not the duration of the exclusive lock itself — it's **queue position**. Getting to Phase 3 requires every session that currently holds *any* MDL on the table (including a `SELECT`-only, seemingly idle transaction that merely touched the table earlier and hasn't committed/rolled back) to release it first. Until that happens:

- The `ALTER TABLE ... ALGORITHM=INSTANT` sits in `SHOW FULL PROCESSLIST` as `Waiting for table metadata lock`.
- Because MDL grants are effectively FIFO/priority-ordered, **every new query that arrives after the ALTER and touches that table — including plain `SELECT`s — queues behind the ALTER** rather than passing it, even though those queries would not otherwise have conflicted with a shared lock. This is what makes "instant" DDL look like it "took a full-table lock the whole time" in practice, when what actually happened is: the ALTER's brief exclusive-lock request got stuck in a queue behind a long-lived transaction, and it then blocked everything filed in behind it.
- If the wait exceeds `lock_wait_timeout` (default 31536000s / effectively unbounded unless set — check your session's actual setting, it's commonly tuned down to 5–50s in production), the ALTER fails with `ERROR 1205 (HY000): Lock wait timeout exceeded`, having done no damage but having potentially blocked other sessions for the whole wait window.

## Runbook recommendations

1. **Before running any `ALGORITHM=INSTANT` DDL in the maintenance window, check for long-running or idle-in-transaction sessions touching the target table:**
   ```sql
   SELECT * FROM performance_schema.metadata_locks
   WHERE OBJECT_SCHEMA = '<schema>' AND OBJECT_NAME = '<table>';

   SELECT * FROM information_schema.innodb_trx
   WHERE trx_mysql_thread_id IN (
     SELECT id FROM information_schema.processlist WHERE db = '<schema>'
   )\G
   ```
   (`performance_schema.metadata_locks` requires the `wait/lock/metadata/sql/mdl` instrument enabled, which is on by default in 8.0.)

2. **Set an explicit, short `lock_wait_timeout` for the DDL session** (e.g., `SET SESSION lock_wait_timeout = 10;`) so a stuck long transaction produces a fast, retryable failure instead of an open-ended stall that also blocks everything queued behind it.

3. **Kill or wait out blocking transactions deliberately** rather than firing the ALTER blind — a transaction that ran a single `SELECT` five minutes ago and never committed is enough to stall an INSTANT DDL indefinitely.

4. **Do not assume "INSTANT ⇒ zero risk of blocking."** Treat it the same as any other online DDL for scheduling purposes: safe and fast *if* the table has no long-lived open transactions at the moment you run it; potentially blocking (of itself and of everything after it) otherwise. The "instant" part refers to the amount of *work* done (metadata-only, no table rebuild/copy), not to a guarantee about *wait time* to acquire the lock.

5. **Retry-with-backoff pattern** is the standard mitigation used in most zero-downtime-migration tooling (e.g., gh-ost, pt-online-schema-change wrappers, or a simple shell loop) precisely because of this behavior: attempt the ALTER with a short `lock_wait_timeout`, and retry on `ERROR 1205` rather than holding a long-timeout ALTER that queue-blocks production traffic.

## Confidence and scope

- **High confidence** on the core mechanical claim (shared-upgradable → brief exclusive at commit, applies to INSTANT) — it is stated identically today on both manual pages, corroborated by MySQL's own Verification Team's bug-tracker response, and matches the publicly documented three-phase model that was never disputed or changed.
- **High confidence** that the literal phrase "No metadata locks are taken on the table" is stale/pre-May-2022 wording if you're seeing it today — confirmed via Wayback Machine snapshot diffing (last seen 2022‑05‑09, gone by 2022‑07‑26) and the bug's 13-May-2022 "documentation has been revised" closure note.
- **Scope check:** this analysis is specific to `ALGORITHM=INSTANT` on `InnoDB` tables in MySQL 8.0 (8.0.12+, where INSTANT was introduced; the ADD/DROP COLUMN variant landed in 8.0.29). The same phrasing and phase model also appear in the MySQL 8.4 manual, so the guidance carries forward if/when the runbook is used post-upgrade.
- **Not independently verified in a live server** in this session (no MySQL instance was available to reproduce Bug #106480's repro script) — the conclusion rests on the manual's own (now-consistent) text plus the bug tracker's authoritative back-and-forth with MySQL's Verification Team, not on a fresh reproduction. If the runbook is for a high-stakes maintenance window, it is worth a 10-minute dry run of the bug's repro script (open a transaction with a `SELECT` on the target table in one session, fire the `ALGORITHM=INSTANT` ALTER in a second, confirm it shows `Waiting for table metadata lock` in `SHOW FULL PROCESSLIST`) against a staging instance of the same MySQL 8.0 minor version to see the exact `lock_wait_timeout` and blocking behavior firsthand.

## Sources

- [17.12.2 Online DDL Performance and Concurrency — MySQL 8.0 Reference Manual](https://dev.mysql.com/doc/refman/8.0/en/innodb-online-ddl-performance.html) (current text verified via Wayback Machine snapshot `20260421043046`)
- [13.1.9 ALTER TABLE Statement — MySQL 8.0 Reference Manual](https://dev.mysql.com/doc/refman/8.0/en/alter-table.html) (current text verified via Wayback Machine snapshot `20260822073247`)
- [17.12.1 Online DDL Operations — MySQL 8.0 Reference Manual](https://dev.mysql.com/doc/refman/8.0/en/innodb-online-ddl-operations.html)
- [10.11.4 Metadata Locking — MySQL 8.0 Reference Manual](https://dev.mysql.com/doc/refman/8.0/en/metadata-locking.html)
- [MySQL Bug #106480: ALGORITHM=INSTANT takes exclusive metadata lock on table](https://bugs.mysql.com/bug.php?id=106480) (verified via Wayback Machine snapshot `20260412225138`; filed 17 Feb 2022, resolved as documentation fix 13 May 2022)
- [MySQL 8.0 Release Notes — Changes in MySQL 8.0.30 (2022-07-26)](https://dev.mysql.com/doc/relnotes/mysql/8.0/en/news-8-0-30.html) (documentation refresh timeframe)
- Historical (superseded) wording for cross-reference: [Wayback Machine capture of innodb-online-ddl-performance.html, 2019-11-08](https://web.archive.org/web/20191108072444/https://dev.mysql.com/doc/refman/8.0/en/innodb-online-ddl-performance.html)
