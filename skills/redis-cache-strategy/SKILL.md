---
name: redis-cache-strategy
description: >
  Redis caching strategy designer and reviewer. ALWAYS use when designing, reviewing,
  or troubleshooting Redis caching layers — cache pattern selection (cache-aside,
  write-through, write-behind), TTL strategy, cache stampede/penetration/avalanche
  prevention, hot key handling, cache-DB consistency, distributed locking, key naming,
  and degradation design. Use even for "just add a cache" requests — cache invalidation
  is one of the two hard problems in computer science, and a naive implementation creates
  subtle consistency bugs that surface only under load.
---

# Redis Cache Strategy Review

## Quick Reference

**§1** scope · **§2** gates (context, mode, risk, completeness) · **§3** depth ·
**§4** degradation modes · **§5** the checklist — the only item list · **§6**
pattern selection · **§7** anti-example index · **§8** how §5's items are scored ·
**§9** output contract · **§10** which reference to load when.

References: `cache-patterns.md` (patterns in depth) ·
`cache-failure-modes.md` (stampede / penetration / avalanche / hot key) ·
`distributed-locks.md` (fencing, renewal, failover) ·
`cache-anti-examples.md` (AE-1 … AE-13 with code) ·
`redis-version-matrix.md` (what each Redis version changes).

---

## §1 Scope

**In scope** — Redis caching strategy for production backend services. The §5
checklist *is* the scope; it is not restated here, because a second copy of a
list is the defect this skill spent a release removing.

**Out of scope** — delegate to dedicated skills:

- Redis cluster topology, persistence (RDB/AOF), replication config → `redis-best-practise`
- Application code changes → `go-code-reviewer` or language-specific reviewer
- Security hardening, ACL, TLS → `redis-best-practise`

---

## §2 Mandatory Gates

Execute gates sequentially. Each gate has a **STOP** condition.

### Gate 1: Context Collection

| Item | Why it matters | If unknown |
|------|----------------|------------|
| **Redis version** (major.minor) | Gates several concrete answers this skill gives — see below | **Never assume a version.** Answer in branches, or mark the version-gated item NOT SCOREABLE |
| **Deployment mode** (standalone / sentinel / cluster) | Affects key distribution, Lua atomicity scope, lock patterns | Assume standalone — **but not for a lock or a multi-key script**, where Cluster changes correctness (§5 S7) |
| **maxmemory + eviction policy** | Determines what happens when cache is full | Ask; critical for correctness |
| **Cache role in architecture** | Primary cache? L1/L2? Read-through proxy? | **Blocking — cannot be assumed** |
| **Data source type** | SQL DB / NoSQL / external API — affects consistency patterns | **Blocking — cannot be assumed** |
| **Read:write ratio** | Drives pattern selection (read-heavy → cache-aside; write-heavy → write-behind) | Assume read-heavy |
| **Consistency requirement** | Eventual (seconds)? Strong? Best-effort? | **Blocking — cannot be assumed** |
| **Peak QPS on cached entities** | Determines stampede/hot-key risk | Assume high if unknown |

The three **blocking** items block because a wrong guess is invisible: a strategy
built on an assumed consistency requirement reviews clean and surfaces only as an
incident.

The remaining five are **not** uniformly safe to default — the "If unknown"
column is the authority. Only read:write ratio and peak QPS degrade to a tuning
problem when wrong. Version has no default (below). `maxmemory` must be asked:
`noeviction` on a full instance turns every cache write into an error, which is
C3's problem. Deployment mode defaults to standalone only while nothing in scope
is a lock or a multi-key script — under Cluster those need a shared hash slot
(S7), so a wrong default there is a correctness defect too.

**Version is gated per conclusion, not globally.** A global default (the old
"assume 6.0") is wrong in both directions — it invents constraints that no longer
apply and hides features that are now the better answer. Ask, or state both
branches, when a conclusion touches: per-field Hash TTL (`HEXPIRE`, 7.4+);
`hash-max-listpack-*` naming and encoding (7.0+, before that
`hash-max-ziplist-*`); a deletable membership filter (`CF.*` cuckoo, bundled
8.0+); keyspace events `OVERWRITTEN` / `TYPE_CHANGED` (8.2+, best-effort only —
C2); Lua-free compare-and-set / compare-and-delete (`SET … IFEQ`, `DELEX … IFEQ`,
8.4+); `HOTKEYS` and `*-lrm` eviction (8.6+); the Hash-vs-String memory trade
(compact hashes, 8.10+). Matrix and unknown-version procedure:
`references/redis-version-matrix.md`.

**STOP** — emit a question list and stop — when **any** of cache role, data
source, or consistency requirement is unknown. You may then output a numbered
list of what you need and why, plus (if code was supplied) a Minimal-mode static
review of that code as written (§4). You may **not** output a strategy design, a
pattern recommendation, or a scorecard.

**PROCEED**: all three blocking items are stated by the user or derivable from
supplied code/config. The remaining five may use their "If unknown" defaults;
each default used appears in §9.1 with `Source = assumed` and in §9.9 with the
impact if it is wrong.

### Gate 2: Scope Classification

| Mode | Trigger | Output |
|------|---------|--------|
| **review** | User provides existing caching code/config | Safety analysis with findings |
| **design** | User describes what they want to cache | Complete cache strategy proposal |
| **troubleshoot** | User reports cache-related issues (stale data, stampede, latency) | Root cause + fix plan |

**STOP**: Request is not cache-related (e.g., Redis Streams pipeline, pub/sub messaging). Redirect to `redis-best-practise`.

**PROCEED**: Caching intent confirmed.

### Gate 3: Risk Classification

| Risk | Definition | Required action |
|------|-----------|-----------------|
| **SAFE** | Standard cache-aside with TTL, read-heavy workload | Standard review |
| **WARN** | Distributed lock usage, write-behind pattern, multi-service cache sharing | Off-peak rollout + monitoring |
| **UNSAFE** | Cache as sole data source (no DB backing), or cache-DB consistency SLA < 1s | Architecture review + fallback design mandatory |

**STOP**: Any UNSAFE item without fallback design.

**PROCEED**: Every cache component has risk level and mitigation.

### Gate 4: Output Completeness

Before delivering output, verify all §9 Output Contract sections present. §9.9 Uncovered Risks must never be empty.

---

## §3 Depth Selection

| Depth | When to use | Gates | References to load |
|-------|-------------|-------|-------------------|
| **Lite** | Single key TTL/pattern review, ≤3 cached entities | 1–4 | None |
| **Standard** | Full cache layer design (pattern + consistency + failure modes) | 1–4 | `cache-patterns.md` |
| **Deep** | Multi-service cache architecture, hot key analysis, consistency SLA | 1–4 | `cache-patterns.md` + `cache-failure-modes.md` |

`distributed-locks.md` loads on the presence of a lock, at any depth.

**Force Standard or higher** on any of: write-behind or write-through pattern, distributed lock, multi-service shared cache, consistency SLA < 5s, cache as authoritative store for any data, hot key with >10K QPS.

---

## §4 Degradation Modes

When context is incomplete, degrade gracefully — never fabricate assumptions about consistency requirements.

| Available context | Mode | What you can do | What you cannot do |
|-------------------|------|-----------------|-------------------|
| Full (version, mode, eviction, source, consistency SLA) | **Full** | Complete strategy with quantified staleness | — |
| Source + consistency known, infra unknown | **Degraded** | Pattern selection + consistency design; flag infra unknowns | Eviction/memory recommendations |
| Only code snippets, no architecture context | **Minimal** | Static review of caching patterns in code | Full strategy design |
| No code (greenfield design request) | **Planning** | Propose cache strategy from requirements | Review existing implementation |

**Hard rule**: Never claim a caching strategy is "consistent" without defining the staleness window. In Degraded/Minimal mode, flag "consistency SLA undefined" in §9.9.

---

## §5 Cache Strategy Checklist

The **only** list of items in this skill. §8 scores these same IDs and defines
nothing of its own, so an item cannot be graded in one place and ignored in the
other. Mark every item with exactly one verdict:

| Verdict | Meaning | Effect on the score |
|---------|---------|---------------------|
| **PASS** | Evidence in the design or code satisfies the item | numerator + denominator |
| **WARN** | Present but partial, unverified, or weaker than the item requires | denominator only — a WARN is not a pass |
| **FAIL** | Absent, or contradicted by the code | denominator only |
| **N/A** | Structurally inapplicable (no lock exists at all; single-tenant system) — **requires a one-line reason naming the structural fact** | removed from both |
| **NOT SCOREABLE** | The context needed to judge is missing (§4 Degraded / Minimal / Planning) | removed from both, and caps the verdict — §8 |

**Silence is FAIL, not N/A.** A design that never mentions degradation has no
degradation path. N/A is for items the system cannot have, never for items the
author did not discuss — otherwise the denominator shrinks until all pass.

### 5.1 Consistency Foundations

**C1 — Source of truth explicitly defined.** DB or cache authoritative?
Ambiguity here is the #1 cause of inconsistency bugs. The database is almost
always the source of truth; the cache is a derived, disposable copy.

**C2 — Invalidation strategy defined and non-blocking.** At least one
*authoritative* mechanism must be active: TTL expiry, explicit invalidation on
write, or a durable event stream (CDC / transactional outbox). "Write both and
hope" is not one. It must not depend on a blocking keyspace scan: `KEYS` stalls
every other client (AE-4). Pattern choice (cache-aside / write-through /
write-behind / dual-write debounce) must match the read:write ratio and the
consistency requirement; load `references/cache-patterns.md` when uncertain.

Redis **keyspace notifications do not count** as that mechanism. They are
Pub/Sub, which Redis documents as *fire and forget* (a subscriber that
disconnects loses every event from that window, permanently); in Cluster they
are node-local and not broadcast; and they report that a *Redis key* changed,
not that a *database row* did. Best-effort L2→L1 invalidation only, always
behind a TTL floor — see `references/redis-version-matrix.md` § 8.2.

**C3 — Cache-write failure semantics stated.** What the system guarantees when
the `SET`/`DEL` itself fails: best-effort + TTL, bounded retry, transactional
outbox, or CDC. "We DEL on failure" is not an answer — the DEL is the operation
that failed. If the staleness SLA is shorter than the TTL, best-effort is a FAIL.

**C4 — Redis outage distinguished from cache miss in code.** `redis.Nil` is a
miss; every other error is an outage. An operational error that falls through to
the data source as if it were a miss converts the outage into a full-rate
stampede.

**C5 — Cache-down degradation path exists.** What the service does with Redis
unavailable: serve stale from L1, bypass to the DB with rate limiting, or return
a degraded response. "Service crashes" is not an acceptable answer.

**C6 — Durability profile matches the data.** Write-behind — and every other
deferred-durability path — puts an RPO > 0 on the data. Financial, ledger, or
audit-critical data therefore needs a durable queue with acknowledgement *and* a
written, accepted RPO. A fire-and-forget goroutine between cache and DB is a
FAIL, not a WARN: the process dying is not an edge case, it is a deploy.

**C7 — Tenant and principal isolation in the key.** Any key holding data scoped
to a tenant, user, or permission set must carry that scope *in the key*. A key
built from the entity ID alone is reachable by every caller that reaches the
cache path, making the cache an authorization bypass that correct DB-side
authorization cannot undo. The cached *value* must likewise not carry fields the
requester is not entitled to see.

### 5.2 Key Design & TTL

**C8 — Every cached key has a bounded lifetime.** A TTL, or a documented and
enforced invalidation guarantee that makes immortality safe. Without one a single
missed invalidation is stale *forever* rather than until expiry — unbounded
staleness is a correctness defect, not a tuning problem.

**S1 — TTL jitter applied per write.** Random ±10–20% computed at write time,
per key, so keys populated together do not expire together. A constant
randomised once at startup shifts the avalanche instead of spreading it.

**H1 — Key naming follows a namespace convention.** `{service}:{entity}:{id}` or
`{tenant}:{domain}:{version}:{id}` — deterministic, greppable, collision-free, no
bare numeric IDs. (Naming *style* is hygiene; the isolation guarantee is C7.)

**H2 — Key and value size bounded.** Keys < 1KB, values < 10KB as default
guidance; check with `redis-cli --bigkeys`. Over the bound, pick the structure by
**access granularity** and then measure — do not reach for a Hash reflexively:
   - **Readers fetch the whole object every time** → keep a single String and compress it. A Hash is strictly worse here: `HGETALL` costs more than `GET` and you lose the ability to compress across fields.
   - **Readers fetch individual fields** (`HGET`/`HMGET`) → a Hash avoids transferring the rest, which is the real win.
   - **Memory**: a Hash is only more compact while it stays under **both** `hash-max-listpack-entries` (default 512) and `hash-max-listpack-value` (default 64 bytes) — that is the listpack encoding (named `hash-max-ziplist-*` before 7.0). Cross either threshold and it converts to a hashtable, where per-field overhead makes it *larger* than the equivalent String. A "large blob" is by definition past the 64-byte value threshold, so the memory argument does not apply to it at all. On 8.10+ compact hashes store shared field names once, which narrows but does not erase the gap — measure on your version.
   - **TTL**: per-field expiry needs `HEXPIRE`, which is **Redis 7.4+**. Below that a Hash has one TTL for the whole key, so splitting an object into fields forces every field to share one expiry — often the reason a Hash is the wrong choice.
   - Verify with `MEMORY USAGE <key>` and `OBJECT ENCODING <key>` on real data before committing to a shape.

**H3 — Eviction policy matches access pattern.** `allkeys-lru` general,
`volatile-lru` for mixed TTL/permanent keys, `allkeys-lfu` frequency-based
(4.0+), `allkeys-lrm`/`volatile-lrm` least-recently-*modified* (8.6+). A full
instance under `noeviction` turns every cache write into an error — that is C3's
problem, not a tuning one.

### 5.3 Failure Mode Defense

**S2 — Stampede (thundering herd) protection.** A hot key expires and every
concurrent request queries the DB at once. Defense: singleflight / mutex (one
caller fetches, the rest wait), stale-while-revalidate, or probabilistic early
expiration.

**S3 — Penetration protection.** Requests for IDs that do not exist bypass the
cache and always reach the DB. Defense: cache the null result with a short TTL
(30–60s), or a membership filter — whose rebuild semantics must be stated,
because a plain bloom filter cannot delete and answers "definitely absent" for
rows inserted since the last rebuild, turning the cache into a source of wrong
404s. Cuckoo filters (`CF.*`, bundled from 8.0) support deletion.

**S4 — Avalanche protection.** Mass expiry at one instant moves the whole read
load to the DB in a single step. Defense: TTL jitter (S1), L1 local cache,
circuit breaker on DB calls. Keys populated by one warmup batch share a
population time, so the jitter must be at least as wide as that batch.

**S5 — Hot key mitigation.** One key taking disproportionate traffic. Defense:
L1 in-process cache, replica fan-out, or read replicas. Detect with
`redis-cli --hotkeys` (4.0+, LFU mode) or the server-side `HOTKEYS` command
(8.6+, top-K by CPU time and network bytes).

Replica fan-out means N physical copies of one logical key, and **the replica
index must be chosen by the caller** — round-robin or random, per request.
Deriving it from the key (`key:{hash%N}`) is the classic non-fix: the hash is
deterministic, so every reader computes the same replica and 100% of the traffic
still lands on one key on one node. Fan-out also obliges you to write and
invalidate *all* N replicas and to state its consistency cost — see
`references/cache-failure-modes.md`.

### 5.4 Consistency & Operations

**S6 — Staleness window quantified.** How stale may cached data be, in
seconds/minutes? A business decision, not a technical default. Layers add up: an
L1 TTL of *T* stacks on top of the Redis TTL because every process holds its own
copy. Publish the total and monitor the actual value.

**S7 — Distributed lock is well-formed and bounded.** Baseline: a TTL so a
crashed holder cannot deadlock it, a unique per-acquisition token, and a
compare-and-set release (Lua CAS, or `DELEX <key> IFEQ <token>` on 8.4+) so you
cannot delete someone else's lock. Beyond it: keep the critical section well
under the TTL or renew with a hard cap — unbounded renewal turns a hung holder
into a permanent lock, worse than the deadlock the TTL prevented; treat a failed
renewal as a lost lock and abort; state a failover position, since asynchronous
replication can grant one lock twice. In Cluster every key a lock script touches
must share a hash slot, or it fails with CROSSSLOT.

**C9 — Correctness locks are enforced where the data lives.** When the lock
guards an effect outside Redis (a DB row, a payment, a file, a third-party call),
a fencing token must be issued atomically with acquisition **and checked by the
protected resource**, which rejects anything not strictly newer than the last
token it accepted. Without that check a holder paused past its TTL resumes and
writes *after* the next holder already wrote — no Redis-side design prevents it,
Redlock included. Equivalently and usually better: enforce mutual exclusion where
the data lives (unique constraint, `UPDATE … WHERE version = ?`,
`SELECT … FOR UPDATE`) and treat Redis as an efficiency optimization. A design
whose only mutual-exclusion mechanism is a Redis lock is **UNSAFE** in Gate 3.
N/A only when no lock exists *and* nothing outside Redis needs mutual exclusion;
a lock nobody classified is FAIL, not N/A.

**H4 — Cache observability configured.** Hit rate, miss rate, eviction rate,
latency, big-key and hot-key detection. Without a hit-rate metric the cache
cannot be shown to work, and a silent populate failure is indistinguishable from
a cold cache.

**H5 — Warmup strategy for cold start and deploy.** Lazy (the first request
pays), eager (batch pre-populate on deploy), or gradual (canary a rising traffic
share); state the first-minute DB load it implies and confirm it is survivable.

---

## §6 Pattern Selection (Standard + Deep)

Quick decision guide — for full patterns load `references/cache-patterns.md`.

| Scenario | Recommended Pattern | Why |
|----------|-------------------|-----|
| Read-heavy, moderate staleness OK | **Cache-Aside** | Simplest; app controls both read and invalidation |
| Read-your-writes on the write path | **Write-Through** | Cache updated synchronously on the same request — **not** strong consistency, and not fresh at all when the cache write fails (C3) |
| Write-heavy, async durability acceptable | **Write-Behind** | Defers DB writes; highest throughput but data loss risk |
| Hot key with concurrent updates | **Dual-Write Debounce** | Absorbs race windows via delayed second invalidation — the second delete must be durable, not an in-process sleep |

---

## §7 Anti-Examples

The thirteen anti-examples, with the wrong/right code for each, live in
`references/cache-anti-examples.md` — load it for any review or troubleshoot
request. This index exists so you can recognise a case without loading the file;
it is not a substitute for reading the pair before writing a finding.

| # | Pattern on sight | The defect | Item |
|---|------------------|-----------|------|
| AE-1 | `rdb.Set(..., 0)` | Immortal key: a missed invalidation is stale forever | C8 |
| AE-2 | `go func() { db.Save(v) }()` | Write-behind with no durable queue — the goroutine dies with the process | C6 |
| AE-3 | `redis.Nil` → DB query, no dedup | Stampede: every concurrent miss queries the DB | S2 |
| AE-4 | `rdb.Keys(ctx, "user:*")` | `KEYS` blocks the server for the whole scan | C2 |
| AE-5 | `SetNX` with no TTL, bare `Del`, or a discarded `ok` | Lock that deadlocks, releases someone else's, or never acquired | S7 |
| AE-6 | "user sees old profile" filed as a logic bug | Staleness misdiagnosed, so invalidation is never examined | C2 |
| AE-7 | Cache key omitting query parameters | One key serves several different queries | H1 |
| AE-8 | Redis as the only store | No DB backing: a restart is data loss | C1 |
| AE-9 | Async `Set` then immediate `Get` | Read-after-write race in cache population | C3 |
| AE-10 | `maxmemory 0` / `noeviction` | Unbounded growth, or every write fails once full | H3 |
| AE-11 | PII with a 24h TTL in a shared instance | Sensitive data outliving its purpose, readable cross-service | C7 |
| AE-12 | `SCAN` + `DEL` loop in the hot path | Unpredictable invalidation latency | C2 |
| AE-13 | Load test with a cold or bypassed cache | Capacity numbers that do not describe production | H4 |

A lock that is TTL + token + CAS is *well-formed*, not *safe* (AE-5 stops at
well-formed). If it guards anything outside Redis, see C9 and
`references/distributed-locks.md`.

---

## §8 Cache Strategy Scorecard

The items scored are §5's, by ID. §8 introduces none of its own — that
duplication is how a Critical finding ends up graded as optional.

| Tier | Items | To pass the tier |
|------|-------|------------------|
| **Critical** | `C1–C9` | **every scoreable item PASS.** WARN fails the tier too |
| **Standard** | `S1–S7` | ≥ 80% of scoreable items PASS (round up) |
| **Hygiene** | `H1–H5` | ≥ 75% of scoreable items PASS (round up) |

**Dynamic denominator.** N/A and NOT SCOREABLE items leave *both* sides of the
fraction; a fixed `/21` would force either a false FAIL for a system that needs
no lock, or a fake pass. A tier whose denominator reaches 0 is reported `—` and
cannot count as passed.

**Verdict:**

- **FAIL** — any Critical item is WARN or FAIL, or any tier misses its threshold.
- **INCOMPLETE** — nothing failed, but at least one Critical item is NOT
  SCOREABLE. An unanswerable Critical question is never a pass; name the missing
  context in §9.9.
- **PASS** — every tier meets its threshold and no Critical item is NOT SCOREABLE.

**Every item gets a row**, `| ID | Verdict | Evidence or reason |`, before the
summary — an item with no row is a FAIL you did not write down. Then emit the
arithmetic, never the bare verdict:

```
Critical p/n · Standard p/n · Hygiene p/n
N/A            <ids + the structural reason>
NOT SCOREABLE  <ids + the missing context>
Verdict: PASS | FAIL | INCOMPLETE
```

---

## §9 Output Contract

Every cache strategy review MUST produce these sections. Write "N/A — [reason]" if inapplicable.

```
### 9.1 Context Gate                | Item | Value | Source |
### 9.2 Depth & Mode                [Lite/Standard/Deep] × [review/design/troubleshoot] — rationale
### 9.3 Risk Assessment             | Component | Pattern | Risk | Notes |
### 9.4 Strategy Design             pattern + justification; consistency model + staleness SLA; failure-mode defenses ("N/A — Lite" at Lite depth)
### 9.5 Implementation              key schema, TTL config, code patterns
### 9.6 Validation Plan             hit-rate target; staleness measurement; failure injection (Redis down, hot key, mass expiry)
### 9.7 Degradation Plan            what the service does while the cache is gone
### 9.8 Monitoring & Alerts         hit rate, latency, eviction rate, big-key and hot-key detection
### 9.9 Uncovered Risks (MANDATORY — never empty)   | Area | Reason | Impact | Follow-up |
```

**Volume rules**: FAIL findings fully detailed with a fix; WARN up to 10, then overflow to §9.9; PASS summarised. §9.9 records every assumption you used.

**Scorecard summary** (append after §9.9, in the §8 format):
```
Critical p/n · Standard p/n · Hygiene p/n
N/A            <ids + reason>
NOT SCOREABLE  <ids + missing context>
Verdict: PASS | FAIL | INCOMPLETE
Data basis: [full context | degraded | minimal | planning]
```

---

## §10 Reference Loading Guide

| Condition | Load |
|-----------|------|
| Standard or Deep depth | `references/cache-patterns.md` |
| Deep depth, or stampede/penetration/avalanche signals | `references/cache-failure-modes.md` |
| Any Redis lock in scope (always, not only at Deep) | `references/distributed-locks.md` |
| Gate 2 mode is review or troubleshoot (any depth) | `references/cache-anti-examples.md` |
| A conclusion on the Gate 1 version-gated list, at any depth | `references/redis-version-matrix.md` |