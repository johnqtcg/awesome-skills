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

| If you need to…                        | Go to                                    |
|----------------------------------------|------------------------------------------|
| Understand what this skill covers      | §1 Scope                                 |
| Check mandatory prerequisites          | §2 Mandatory Gates                       |
| Choose review depth                    | §3 Depth Selection                       |
| Handle incomplete context              | §4 Degradation Modes                     |
| Evaluate cache design item by item     | §5 Cache Strategy Checklist              |
| Choose the right cache pattern         | §6 Pattern Selection                     |
| Avoid common caching mistakes          | §7 Anti-Examples                         |
| Score the review result                | §8 Scorecard                             |
| Format review output                   | §9 Output Contract                       |
| Deep-dive cache patterns               | `references/cache-patterns.md`           |
| Understand failure mode defenses       | `references/cache-failure-modes.md`      |
| Design or review a distributed lock    | `references/distributed-locks.md`        |

---

## §1 Scope

**In scope** — Redis caching strategy for production backend services:

- Cache pattern selection (cache-aside, write-through, write-behind, dual-write debounce)
- Key naming conventions and namespace design
- TTL strategy (expiration, jitter, eviction policy alignment)
- Cache failure modes (stampede/penetration/avalanche) and defenses
- Hot key detection and mitigation (singleflight, local cache, sharding)
- Cache-DB consistency design and staleness SLA
- Distributed locking patterns (SETNX, Redlock, lock timeout)
- Cache warmup and cold-start strategies
- Degradation design (cache-down fallback)

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
| **Redis version** (6.x / 7.x) | Feature availability (e.g., client-side caching in 6.0+) | Assume 6.0 |
| **Deployment mode** (standalone / sentinel / cluster) | Affects key distribution, Lua atomicity scope, lock patterns | Assume standalone |
| **maxmemory + eviction policy** | Determines what happens when cache is full | Ask; critical for correctness |
| **Cache role in architecture** | Primary cache? L1/L2? Read-through proxy? | **Blocking — cannot be assumed** |
| **Data source type** | SQL DB / NoSQL / external API — affects consistency patterns | **Blocking — cannot be assumed** |
| **Read:write ratio** | Drives pattern selection (read-heavy → cache-aside; write-heavy → write-behind) | Assume read-heavy |
| **Consistency requirement** | Eventual (seconds)? Strong? Best-effort? | **Blocking — cannot be assumed** |
| **Peak QPS on cached entities** | Determines stampede/hot-key risk | Assume high if unknown |

The three **blocking** items are blocking precisely because a wrong guess is
invisible: a strategy built on an assumed consistency requirement looks complete
and reviews clean, and the assumption only surfaces as a production incident.
The other five have defaults whose wrongness shows up as a tuning problem, not a
correctness one.

**STOP** — emit a question list and stop — when **any** of cache role, data
source, or consistency requirement is unknown. In this state you may output:
a numbered list of what you need and why; and, if code was supplied, a
Minimal-mode static review of that code as written (§4). You may **not** output
a strategy design, a pattern recommendation, or a scorecard.

**PROCEED**: all three blocking items are stated by the user or derivable from
supplied code/config. The remaining five may use their "If unknown" defaults —
and every default you used must appear in §9.1 with `Source = assumed`, and in
§9.9 with the impact if the assumption is wrong.

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

`distributed-locks.md` loads on the presence of a lock, independent of depth —
a lock in a Lite-scope review is still a lock.

**Force Standard or higher** when any signal appears:
write-behind or write-through pattern, distributed lock, multi-service shared cache, consistency SLA < 5s, cache as authoritative store for any data, hot key with >10K QPS.

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

Execute every item. Mark **PASS** / **WARN** / **FAIL** with evidence.

### 5.1 Pattern Selection

1. **Cache pattern identified and justified** — which pattern (cache-aside / write-through / write-behind / dual-write debounce) is used and why? The pattern must match the read:write ratio and consistency requirement. When uncertain → load `references/cache-patterns.md`.

2. **Source of truth explicitly defined** — is the database or the cache the authoritative source? Ambiguity here is the #1 cause of data inconsistency bugs. Rule: the database is almost always the source of truth; the cache is a derived, disposable copy.

3. **Invalidation strategy defined** — how and when is stale cache data removed? Options: TTL-based expiration, explicit invalidation on write, event-driven invalidation (CDC/pub-sub). At least one must be active.

### 5.2 Key Design & TTL

4. **Key naming follows namespace convention** — `{service}:{entity}:{id}` or `{tenant}:{domain}:{version}:{id}`. Keys must be deterministic, greppable, and avoid collisions. No bare numeric IDs.

5. **TTL is set with jitter** — every cached key must have a TTL. Add random jitter (±10-20%) to prevent synchronized expiration (cache avalanche). No immortal keys unless explicitly justified.

6. **Key and value size bounded** — keys < 1KB, values < 10KB as default guidance. Check with `redis-cli --bigkeys`. For values over the bound, pick the structure by **access granularity**, then measure — do not reach for a Hash reflexively:
   - **Readers fetch the whole object every time** → keep a single String and compress it. A Hash is strictly worse here: `HGETALL` costs more than `GET` and you lose the ability to compress across fields.
   - **Readers fetch individual fields** (`HGET`/`HMGET`) → a Hash avoids transferring the rest, which is the real win.
   - **Memory**: a Hash is only more compact while it stays under **both** `hash-max-listpack-entries` (default 512) and `hash-max-listpack-value` (default 64 bytes) — that is the listpack encoding. Cross either threshold and it converts to a hashtable, where per-field overhead makes it *larger* than the equivalent String. A "large blob" is by definition past the 64-byte value threshold, so the memory argument does not apply to it at all.
   - **TTL**: per-field expiry needs `HEXPIRE`, which is **Redis 7.4+**. Below that a Hash has one TTL for the whole key, so splitting an object into fields forces every field to share one expiry — often the reason a Hash is the wrong choice.
   - Verify with `MEMORY USAGE <key>` and `OBJECT ENCODING <key>` on real data before committing to a shape.

7. **Eviction policy matches access pattern** — `allkeys-lru` for general caching, `volatile-lru` for mixed TTL/permanent keys, `allkeys-lfu` for frequency-based (Redis 4.0+). Mismatched policy causes unpredictable evictions.

### 5.3 Failure Mode Defense

8. **Stampede (thundering herd) protection** — when a hot key expires, hundreds of concurrent requests hit the database simultaneously. Defense: singleflight/mutex pattern (only one goroutine/thread fetches, others wait), or stale-while-revalidate.

9. **Penetration protection** — requests for non-existent IDs bypass cache and always hit DB. Defense: cache null/empty results with short TTL (30-60s), or bloom filter at cache layer.

10. **Avalanche protection** — mass key expiration at same time overwhelms DB. Defense: TTL jitter (item 5), multi-level cache (L1 local + L2 Redis), circuit breaker on DB calls.

11. **Hot key mitigation** — single key receiving disproportionate traffic. Defense: local in-process cache (L1), replica fan-out, or read replicas. Detect with `redis-cli --hotkeys` (Redis 4.0+ LFU mode).

    Replica fan-out means N physical copies of one logical key, and **the replica index must be chosen by the caller** — round-robin or random, per request. Deriving it from the key (`key:{hash%N}`) is the classic non-fix: the hash is deterministic, so every reader of that key computes the same replica and 100% of the traffic still lands on one key on one node. Fan-out also obliges you to write and invalidate *all* N replicas and to state its consistency cost — see `references/cache-failure-modes.md`.

### 5.4 Consistency & Operations

12. **Staleness window quantified** — define in seconds/minutes how stale cached data can be. This is a business decision, not a technical default. Document it and monitor actual staleness.

13. **Distributed lock bounded** — baseline for any Redis lock: (a) lock has a TTL so a crashed holder cannot deadlock it, (b) the value is a unique per-acquisition token, (c) release is a Lua CAS so you cannot delete someone else's lock.

    Those three only make the lock *well-formed*. They do not make it **safe**, because a TTL-based lock has no way to stop a holder that is merely slow. Escalate to the four checks below — and load `references/distributed-locks.md` — whenever the lock guards work that is long-running or touches anything outside Redis:

    - **Expiry vs work duration.** The TTL is a bet that the work finishes first. Lose the bet and two holders run concurrently while both believe they hold the lock. Either bound the critical section well under the TTL, or renew.
    - **Renewal with a hard cap.** Renew only while the holder is alive and still owns the token (Lua CAS on `PEXPIRE`), and cap total hold time. Unbounded renewal converts a hung holder into a permanent lock — strictly worse than the deadlock the TTL was added to prevent.
    - **Failover.** Redis replication is asynchronous, so a lock acquired on a master can be absent on the replica promoted after that master fails, and the same lock is then granted twice. Redlock reduces this exposure but does not remove it; it also assumes bounded clock drift across nodes.
    - **Fencing token (required for external effects).** If the lock protects a database row, a file, a payment, or any third-party call, acquisition must return a monotonically increasing token that the protected resource stores and checks, rejecting anything older than the last token it accepted. Without fencing, a holder paused by GC or scheduling past its TTL will resume and write **after** the next holder has already written — no Redis-side lock design prevents this, Redlock included.

    **If correctness depends on mutual exclusion, do not rely on a Redis lock alone.** Enforce it where the data lives: a unique constraint, a conditional `UPDATE ... WHERE version = ?`, or `SELECT ... FOR UPDATE`. Treat the Redis lock as an efficiency optimization that suppresses duplicate work — not as a correctness guarantee. Mark any design that uses a Redis lock as its only mutual-exclusion mechanism **UNSAFE** in Gate 3.

14. **Cache-down degradation path** — what happens when Redis is unreachable? Options: serve stale from local cache, bypass to DB directly (with rate limiting), return degraded response. "Service crashes" is not an acceptable answer.

---

## §6 Pattern Selection (Standard + Deep)

Quick decision guide — for full patterns load `references/cache-patterns.md`.

| Scenario | Recommended Pattern | Why |
|----------|-------------------|-----|
| Read-heavy, moderate staleness OK | **Cache-Aside** | Simplest; app controls both read and invalidation |
| Read-heavy, immediate freshness needed | **Write-Through** | Cache updated synchronously on every write |
| Write-heavy, async durability acceptable | **Write-Behind** | Defers DB writes; highest throughput but data loss risk |
| Hot key with concurrent updates | **Dual-Write Debounce** | Absorbs race windows via delayed second invalidation |

### Cache warmup strategies (for cold start)

- **Lazy warmup**: first request populates cache (accept initial latency spike)
- **Eager warmup**: pre-populate on deploy via batch scan of hot entities
- **Gradual warmup**: route increasing traffic percentage through cache layer (canary)

---

## §7 Anti-Examples

### AE-1: Immortal cache key — no TTL set
```go
// WRONG: key lives forever; stale data never expires
rdb.Set(ctx, "user:123", userData, 0)  // 0 = no expiration
// RIGHT: always set TTL with jitter, and check that the write landed
ttl := 30*time.Minute + time.Duration(rand.Intn(300))*time.Second
if err := rdb.Set(ctx, "user:123", userData, ttl).Err(); err != nil {
    slog.WarnContext(ctx, "cache populate failed", "key", "user:123", "err", err)
}
```

### AE-2: Write-behind without durable queue
```go
// WRONG: write to Redis, async goroutine writes DB — if process crashes, data lost
rdb.Set(ctx, key, value, ttl)
go func() { db.Save(value) }()  // fire-and-forget = data loss risk
// RIGHT: use durable queue (Kafka, Redis Stream with ACK) between cache and DB
```

### AE-3: Cache-aside without stampede protection
```go
// WRONG: 1000 concurrent requests all miss cache, all query DB simultaneously
val, err := rdb.Get(ctx, key).Bytes()
if errors.Is(err, redis.Nil) {
    val = db.Query(id)           // 1000 goroutines hit the DB at once...
    rdb.Set(ctx, key, val, ttl)  // ...and 1000 of them write the same value back
}
// RIGHT: singleflight collapses them into one DB query per key
v, err, _ := sfGroup.Do(key, func() (any, error) {
    return db.Query(id), nil
})
val, _ = v.([]byte)
```

### AE-4: KEYS command for batch invalidation
```go
// WRONG: KEYS blocks Redis for the entire scan — O(N) on all keys
keys, _ := rdb.Keys(ctx, "user:*").Result()
rdb.Del(ctx, keys...)
// RIGHT: use SCAN with bounded cursor iteration, or structured invalidation
```

### AE-5: Distributed lock without TTL or safe release
```go
// WRONG: lock has no TTL — if holder crashes, lock is held forever (deadlock)
rdb.SetNX(ctx, "lock:order:123", "1", 0)
// Also WRONG: releasing without checking ownership
rdb.Del(ctx, "lock:order:123")  // may delete someone else's lock
// Also WRONG: discarding SetNX's bool — that value IS the lock. Ignoring it
// means you run the critical section whether or not you acquired anything.
// RIGHT: TTL + unique token + check acquisition + Lua CAS release
token := uuid.New().String()
ok, err := rdb.SetNX(ctx, "lock:order:123", token, 10*time.Second).Result()
if err != nil || !ok {
    return // not acquired: do NOT enter the critical section
}
// Release with Lua: if redis.call('get',KEYS[1])==ARGV[1] then return redis.call('del',KEYS[1]) end
```

TTL + token + CAS makes the lock *well-formed*, not *safe*. If the lock guards
anything outside Redis, see `references/distributed-locks.md` — you also need a
fencing token, bounded renewal, and a documented failover position.

### AE-6: Cache issue reported as business logic bug
```
-- WRONG: "Bug: user sees old profile after update"
-- This is a cache staleness issue, not a logic bug. Check invalidation strategy.
-- RIGHT: report as "Cache consistency: stale read after write — invalidation delay"
```

Extended anti-examples (AE-7 through AE-13) in `references/cache-anti-examples.md`.

---

## §8 Cache Strategy Scorecard

### Critical — any FAIL means overall FAIL

- [ ] Cache-DB consistency strategy explicitly defined (not "write both and hope")
- [ ] TTL set on all cached keys with jitter (no immortal keys without justification)
- [ ] Cache-down degradation path exists (Redis unavailable ≠ service down)
- [ ] **Cache-write failure semantics stated** — what the system guarantees when the `SET`/`DEL` itself fails: best-effort+TTL, bounded retry, transactional outbox, or CDC. "We DEL on failure" is not an answer, because the DEL is the operation that failed. If the staleness SLA is shorter than the TTL, best-effort is a FAIL.
- [ ] **Redis outage is distinguished from cache miss in code** — an operational error must not fall through to the data source as if it were a miss; that converts an outage into a full-rate stampede

### Standard — 4 of 5 must pass

- [ ] Cache pattern matches business scenario (not blindly cache-aside for everything)
- [ ] Stampede protection for hot keys (singleflight / mutex / stale-while-revalidate)
- [ ] Penetration protection (null-value caching or bloom filter)
- [ ] Key naming follows `{namespace}:{entity}:{id}` convention
- [ ] Distributed locks: TTL + unique token + Lua CAS release, plus a bounded-renewal policy; **fencing token enforced at the protected resource** whenever the lock guards an effect outside Redis (see `references/distributed-locks.md`)

### Hygiene — 3 of 4 must pass

- [ ] Cache hit rate monitoring configured
- [ ] Eviction policy matches data access pattern (LRU/LFU/volatile)
- [ ] Key and value sizes within bounds (<1KB key, <10KB value)
- [ ] Warmup strategy defined for cold start / deployment

**Verdict**: `X/14`; Critical: `Y/5`; Standard: `Z/5`; Hygiene: `W/4`.
PASS requires: Critical 5/5 AND Standard ≥4/5 AND Hygiene ≥3/4.

---

## §9 Output Contract

Every cache strategy review MUST produce these sections. Write "N/A — [reason]" if inapplicable.

```
### 9.1 Context Gate
| Item | Value | Source |

### 9.2 Depth & Mode
[Lite/Standard/Deep] × [review/design/troubleshoot] — [rationale]

### 9.3 Risk Assessment
| Component | Pattern | Risk | Notes |

### 9.4 Strategy Design (Standard/Deep; "N/A — Lite" for Lite)
- Pattern selection + justification
- Consistency model + staleness SLA
- Failure mode defenses

### 9.5 Implementation (key schema, TTL config, code patterns)

### 9.6 Validation Plan
- Cache hit rate target
- Staleness measurement
- Failure injection tests (Redis down, hot key, mass expiry)

### 9.7 Degradation Plan (what happens when cache fails)

### 9.8 Monitoring & Alerts
- Hit rate, latency, eviction rate, big key detection

### 9.9 Uncovered Risks (MANDATORY — never empty)
| Area | Reason | Impact | Follow-up |
```

**Volume rules**:
- FAIL findings: always fully detailed with fix
- WARN findings: up to 10; overflow to §9.9
- PASS: summary only
- §9.9 minimum: document all assumptions (especially consistency SLA if undefined)

**Scorecard summary** (append after §9.9):
```
Scorecard: X/14 — Critical Y/5, Standard Z/5, Hygiene W/4 — PASS/FAIL
Data basis: [full context | degraded | minimal | planning]
```

---

## §10 Reference Loading Guide

| Condition | Load |
|-----------|------|
| Standard or Deep depth | `references/cache-patterns.md` |
| Deep depth, or stampede/penetration/avalanche signals | `references/cache-failure-modes.md` |
| Any Redis lock in scope (always, not only at Deep) | `references/distributed-locks.md` |
| Extended anti-example matching | `references/cache-anti-examples.md` |