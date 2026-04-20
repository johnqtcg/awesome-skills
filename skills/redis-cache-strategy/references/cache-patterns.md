# Redis Cache Patterns — Detailed Guide

Four primary caching patterns for production backend services. Each pattern has
a distinct consistency model, failure profile, and operational complexity.

---

## 1. Cache-Aside (Lazy Loading)

The most common pattern. Application manages both cache reads and invalidation.

### Flow

```
Read path:
  1. App checks Redis for key
  2. Cache HIT → return cached value
  3. Cache MISS → query database → write result to Redis with TTL → return

Write path:
  1. App writes to database
  2. App invalidates (DEL) the cache key
  3. Next read will repopulate cache from DB
```

### Best for
- Read-heavy workloads (>80% reads)
- Simple ownership (one service owns the cache key)
- Moderate staleness tolerance (seconds to minutes)

### Risks
- **Stale reads**: between DB write and cache invalidation, other readers see old data
- **Stampede**: when a hot key expires, concurrent requests all miss and hit DB simultaneously
- **Race condition**: concurrent write + read can cache stale data (write invalidates, then read re-caches old value from slow DB query that started before the write)

### Guardrails
- Always set TTL with jitter (±10-20%) to prevent synchronized mass expiration
- Use singleflight/mutex for hot key misses — only one caller fetches, others wait
- Invalidate deterministically by exact key — never use pattern-based `KEYS` or `SCAN` for real-time invalidation
- Consider delayed double-delete for write-read race: delete on write, then delete again after 500ms

### Code pattern (Go)

```go
func GetUser(ctx context.Context, id string) (*User, error) {
    // 1. Check cache
    cached, err := rdb.Get(ctx, "user:"+id).Bytes()
    if err == nil {
        var u User
        json.Unmarshal(cached, &u)
        return &u, nil
    }

    // 2. Singleflight: deduplicate concurrent DB queries for same key
    val, err, _ := sfGroup.Do("user:"+id, func() (interface{}, error) {
        u, err := db.QueryUser(ctx, id)
        if err != nil {
            return nil, err
        }
        // 3. Populate cache with jittered TTL
        data, _ := json.Marshal(u)
        ttl := 30*time.Minute + time.Duration(rand.Intn(300))*time.Second
        rdb.Set(ctx, "user:"+id, data, ttl)
        return u, nil
    })
    if err != nil {
        return nil, err
    }
    return val.(*User), nil
}

func UpdateUser(ctx context.Context, u *User) error {
    if err := db.UpdateUser(ctx, u); err != nil {
        return err
    }
    rdb.Del(ctx, "user:"+u.ID)  // Invalidate cache
    return nil
}
```

---

## 2. Write-Through

Cache is updated synchronously on every write. Reads always hit cache first.

### Flow

```
Write path:
  1. App writes to database
  2. App writes updated value to Redis (synchronously, same request)

Read path:
  1. App reads from Redis
  2. Cache HIT → return (always fresh since writes update cache)
  3. Cache MISS → query database → populate cache → return
```

### Best for
- Latency-sensitive reads where freshness is critical
- Moderate write volume (each write has added Redis SET latency)
- Systems where cache miss penalty is very high

### Risks
- **Write latency increase**: every write adds a Redis SET to the critical path
- **Partial failure**: DB write succeeds but cache write fails → stale cache
- **Unnecessary caching**: data written but never read wastes memory

### Guardrails
- If cache write fails, invalidate (DEL) the key rather than leaving stale data
- Set TTL even in write-through — defense against cache-DB drift from edge cases
- Keep writes idempotent — retry-safe
- Consider write-through only for data that is read within seconds of writing

---

## 3. Write-Behind (Write-Back)

Cache is updated first; database write is deferred asynchronously.

### Flow

```
Write path:
  1. App writes to Redis (and optionally to a durable queue)
  2. Background worker reads queue, writes to database

Read path:
  1. App reads from Redis (always has latest value)
```

### Best for
- Extreme write throughput requirements
- Tolerable delayed durability (RPO > 0)
- Batch-friendly DB writes (aggregate before flush)

### Risks
- **Data loss on crash**: if Redis/queue fails before DB write, data is lost
- **Reordering**: async writes may arrive out of order at DB
- **Reconciliation complexity**: cache and DB can diverge; need reconciliation process

### Guardrails
- Use durable queue (Kafka, Redis Streams with ACK, not fire-and-forget goroutines)
- Enforce strict idempotency and version checks on DB writes
- Define explicit RPO/RTO acceptance with stakeholders
- Build reconciliation runbook for cache-DB divergence
- Never use write-behind for financial or audit-critical data

---

## 4. Dual-Write Debounce

Adjunct pattern for cache-aside under high write contention on hot keys.

### Problem
In cache-aside, a race exists between write-invalidation and concurrent reads:
1. Writer A updates DB
2. Reader B (started before A's write) queries DB, gets old value
3. Writer A invalidates cache
4. Reader B writes old value to cache ← stale data persists until TTL

### Solution: Delayed Double-Delete

```
Write path:
  1. App writes to database
  2. App DELs cache key immediately
  3. App schedules a second DEL after delay (100ms–1s)
     (via delayed job, or sleep in goroutine)
```

The second DEL catches the race: if a concurrent reader re-cached stale data
between step 2 and 3, the delayed DEL cleans it up.

### Best for
- Hot keys with frequent concurrent reads AND writes
- Cache-aside base pattern with known race conditions
- When staleness window of 100ms–1s is acceptable

### Guardrails
- Bound the delay queue/retry count to prevent pileup
- Monitor stale-read rate to tune debounce window
- Consider per-entity debounce policy (not all keys need it)

---

## 5. Pattern Selection Matrix

| Consistency need | Read:Write ratio | Recommended | Staleness |
|-----------------|:----------------:|-------------|-----------|
| Eventual (seconds OK) | Read-heavy (>80%) | **Cache-Aside** | TTL-bounded |
| Strong (immediate) | Moderate writes | **Write-Through** | Near-zero |
| Best-effort (async) | Write-heavy | **Write-Behind** | Unbounded until flush |
| Eventual + hot keys | Mixed with contention | **Cache-Aside + Debounce** | Debounce window |

### Decision questions

1. **Can you tolerate stale data for N seconds?** → determines pattern
2. **Is the data source the only source of truth?** → if no, you need write-through or write-behind
3. **What happens if the cache is lost entirely?** → if "service fails," redesign
4. **Is there a single hot key?** → add singleflight + consider local L1 cache

---

## 6. Operational Checklist for Any Pattern

1. Source of truth is explicitly documented (DB or cache?)
2. Cache failure mode is defined (stale serve / bypass / error)
3. Retry and idempotency strategy exists for cache-write failures
4. Staleness window is quantified and monitored
5. Rollback path exists (can you safely turn off caching?)