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
| **Cache role in architecture** | Primary cache? L1/L2? Read-through proxy? | Must clarify before design |
| **Data source type** | SQL DB / NoSQL / external API — affects consistency patterns | Must clarify |
| **Read:write ratio** | Drives pattern selection (read-heavy → cache-aside; write-heavy → write-behind) | Assume read-heavy |
| **Consistency requirement** | Eventual (seconds)? Strong? Best-effort? | Must clarify |
| **Peak QPS on cached entities** | Determines stampede/hot-key risk | Assume high if unknown |

**STOP**: Cannot determine what the cache is caching (no data source, no access pattern). Clarify before proceeding.

**PROCEED**: At least data source, cache role, and consistency requirement are known or assumed.

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
| **Deep** | Multi-service cache architecture, hot key analysis, consistency SLA | 1–4 | Both reference files |

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

6. **Key and value size bounded** — keys < 1KB, values < 10KB as default guidance. Large values should use Hash fields or compression. Check with `redis-cli --bigkeys`.

7. **Eviction policy matches access pattern** — `allkeys-lru` for general caching, `volatile-lru` for mixed TTL/permanent keys, `allkeys-lfu` for frequency-based (Redis 4.0+). Mismatched policy causes unpredictable evictions.

### 5.3 Failure Mode Defense

8. **Stampede (thundering herd) protection** — when a hot key expires, hundreds of concurrent requests hit the database simultaneously. Defense: singleflight/mutex pattern (only one goroutine/thread fetches, others wait), or stale-while-revalidate.

9. **Penetration protection** — requests for non-existent IDs bypass cache and always hit DB. Defense: cache null/empty results with short TTL (30-60s), or bloom filter at cache layer.

10. **Avalanche protection** — mass key expiration at same time overwhelms DB. Defense: TTL jitter (item 5), multi-level cache (L1 local + L2 Redis), circuit breaker on DB calls.

11. **Hot key mitigation** — single key receiving disproportionate traffic. Defense: local in-process cache (L1), key sharding (`key:{hash%N}`), or read replicas. Detect with `redis-cli --hotkeys` (Redis 4.0+ LFU mode).

### 5.4 Consistency & Operations

12. **Staleness window quantified** — define in seconds/minutes how stale cached data can be. This is a business decision, not a technical default. Document it and monitor actual staleness.

13. **Distributed lock bounded** — if using Redis locks (SETNX + EX), ensure: (a) lock has TTL to prevent deadlock, (b) lock value is unique token for safe release, (c) release uses Lua CAS to prevent releasing someone else's lock. Consider whether the lock actually needs to be distributed.

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
// RIGHT: always set TTL with jitter
ttl := 30*time.Minute + time.Duration(rand.Intn(300))*time.Second
rdb.Set(ctx, "user:123", userData, ttl)
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
val, err := rdb.Get(ctx, key).Result()
if err == redis.Nil {
    val = db.Query(id)        // 1000 goroutines hit DB at once
    rdb.Set(ctx, key, val, ttl)
}
// RIGHT: use singleflight to deduplicate concurrent cache fills
val, err, _ = sfGroup.Do(key, func() (interface{}, error) {
    return db.Query(id)
})
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
// RIGHT: TTL + unique token + Lua CAS release
token := uuid.New().String()
rdb.SetNX(ctx, "lock:order:123", token, 10*time.Second)
// Release with Lua: if redis.call('get',KEYS[1])==ARGV[1] then return redis.call('del',KEYS[1]) end
```

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

### Standard — 4 of 5 must pass

- [ ] Cache pattern matches business scenario (not blindly cache-aside for everything)
- [ ] Stampede protection for hot keys (singleflight / mutex / stale-while-revalidate)
- [ ] Penetration protection (null-value caching or bloom filter)
- [ ] Key naming follows `{namespace}:{entity}:{id}` convention
- [ ] Distributed locks have TTL and safe CAS release

### Hygiene — 3 of 4 must pass

- [ ] Cache hit rate monitoring configured
- [ ] Eviction policy matches data access pattern (LRU/LFU/volatile)
- [ ] Key and value sizes within bounds (<1KB key, <10KB value)
- [ ] Warmup strategy defined for cold start / deployment

**Verdict**: `X/12`; Critical: `Y/3`; Standard: `Z/5`; Hygiene: `W/4`.
PASS requires: Critical 3/3 AND Standard ≥4/5 AND Hygiene ≥3/4.

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
Scorecard: X/12 — Critical Y/3, Standard Z/5, Hygiene W/4 — PASS/FAIL
Data basis: [full context | degraded | minimal | planning]
```

---

## §10 Reference Loading Guide

| Condition | Load |
|-----------|------|
| Standard or Deep depth | `references/cache-patterns.md` |
| Deep depth, or stampede/penetration/avalanche signals | `references/cache-failure-modes.md` |
| Extended anti-example matching | `references/cache-anti-examples.md` |