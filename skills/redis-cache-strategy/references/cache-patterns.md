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
// ErrCacheUnavailable separates "Redis is down" from "key not cached".
// Collapsing the two is the single most common bug in this pattern.
var ErrCacheUnavailable = errors.New("cache unavailable")

func GetUser(ctx context.Context, id string) (*User, error) {
    key := "user:" + id

    // 1. Check cache — three outcomes, not two.
    cached, err := rdb.Get(ctx, key).Bytes()
    switch {
    case err == nil:
        var u User
        if err := json.Unmarshal(cached, &u); err != nil {
            // Corrupt entry. Returning here would hand the caller a
            // zero-value User that looks like a real record.
            slog.WarnContext(ctx, "cache decode failed, dropping", "key", key, "err", err)
            if delErr := rdb.Del(ctx, key).Err(); delErr != nil {
                slog.WarnContext(ctx, "drop corrupt entry failed", "key", key, "err", delErr)
            }
            break // fall through to the DB
        }
        return &u, nil

    case errors.Is(err, redis.Nil):
        // True miss — proceed to the DB.

    default:
        // Redis is unreachable. This is NOT a miss: treating it as one moves
        // the entire read load onto the DB at once. Take the degradation path
        // (circuit breaker / rate-limited bypass) instead.
        return nil, fmt.Errorf("%w: %v", ErrCacheUnavailable, err)
    }

    // 2. Singleflight: deduplicate concurrent DB queries for the same key.
    val, err, _ := sfGroup.Do(key, func() (any, error) {
        u, err := db.QueryUser(ctx, id)
        if err != nil {
            return nil, fmt.Errorf("query user %s: %w", id, err)
        }
        // 3. Populate cache with jittered TTL.
        data, err := json.Marshal(u)
        if err != nil {
            return nil, fmt.Errorf("encode user %s: %w", id, err)
        }
        if err := rdb.Set(ctx, key, data, jitteredTTL(30*time.Minute)).Err(); err != nil {
            // Serve the value, but alert: until this succeeds every read is
            // a miss and the DB carries full read traffic.
            slog.WarnContext(ctx, "cache populate failed", "key", key, "err", err)
        }
        return u, nil
    })
    if err != nil {
        return nil, err
    }
    u, ok := val.(*User)
    if !ok {
        return nil, fmt.Errorf("singleflight returned %T, want *User", val)
    }
    return u, nil
}

func UpdateUser(ctx context.Context, u *User) error {
    if err := db.UpdateUser(ctx, u); err != nil {
        return err
    }
    // The DB is already committed. A dropped DEL leaves the cache stale until
    // TTL with no record that it happened — it cannot be ignored. See
    // "Cache-write failure semantics" below for the durable-retry options.
    if err := rdb.Del(ctx, "user:"+u.ID).Err(); err != nil {
        return fmt.Errorf("db committed but cache invalidation failed for %s: %w", u.ID, err)
    }
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

### Write-through does **not** give you strong consistency

Two independent reasons, both of which survive a perfectly working `SET`:

1. **It is a dual write.** DB commit and cache write are two operations against
   two systems with no shared transaction. The DB can commit and the process
   can then crash, be OOM-killed, or lose Redis — leaving a stale entry with
   nothing left running to fix it. "Then DEL instead" does not close this: the
   DEL is the same unreliable second operation.
2. **Concurrent writers can invert.** W1 and W2 both commit to the DB (W2 last),
   then W2's cache `SET` lands before W1's. The cache now holds W1's older
   value, and it is not stale by TTL — it is *wrong* until the next write.
   A version/timestamp guard (`SET` only if the payload version is newer,
   via Lua CAS) is required to prevent this; TTL does not.

So the honest claim is **read-your-writes on the write path**, with a staleness
window bounded by whatever failure handling you actually implement — not zero.

### Cache-write failure semantics (mandatory to state)

Pick one and write it into §9.4. "We'll DEL on failure" is not one of these
unless you also say what happens when the DEL fails.

| Option | Guarantee | Cost |
|--------|-----------|------|
| **Best-effort + TTL** | Stale bounded by TTL; may serve wrong data for that long | Free. Only acceptable if TTL is inside the staleness SLA |
| **Bounded retry, then DEL, then alert** | Shrinks the window; still fails if the process dies mid-retry | Adds latency to the write path |
| **Transactional outbox** | Invalidation is committed in the same DB transaction as the data; a relay drains it | Needs an outbox table + relay; the only option that survives process death |
| **Event-driven (CDC)** | Cache follows the DB's replication log; no dual write at all | Needs CDC infrastructure (Debezium, logical decoding) |

Rule: if the staleness SLA is shorter than the TTL, best-effort is **not**
sufficient — you need the outbox or CDC. Say which one, in writing.

### Guardrails
- Set TTL even in write-through — it is the backstop for every drift case above
- Guard the cache write with a version check so out-of-order writers cannot invert
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

| Consistency need | Read:Write ratio | Recommended | Staleness on the happy path | Staleness when the cache write fails |
|-----------------|:----------------:|-------------|------------------|------------------|
| Eventual (seconds OK) | Read-heavy (>80%) | **Cache-Aside** | TTL-bounded | TTL-bounded (DEL failure = stale until TTL) |
| Read-your-writes | Moderate writes | **Write-Through** | Near-zero | **TTL-bounded, or unbounded if TTL is absent** — see "Cache-write failure semantics" |
| Best-effort (async) | Write-heavy | **Write-Behind** | Unbounded until flush | Data loss, not just staleness |
| Eventual + hot keys | Mixed with contention | **Cache-Aside + Debounce** | Debounce window | TTL-bounded |

No row in this table offers strong consistency. Redis in front of a database is
an eventually-consistent system in every pattern; the columns differ only in how
short and how *provable* the window is. If a caller genuinely requires strong
consistency, it must read the database, not the cache.

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