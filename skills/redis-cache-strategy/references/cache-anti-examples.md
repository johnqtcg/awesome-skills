# Extended Cache Anti-Examples

Supplementary to the inline anti-examples in §7 of the SKILL.md.
Load when reviewing caching code that exhibits suspicious patterns.

---

## AE-7: Caching database query results with mutable WHERE clauses

```go
// WRONG: cache key doesn't encode the full query parameters
key := "orders:recent"
rdb.Set(ctx, key, db.Query("SELECT * FROM orders WHERE status='active' LIMIT 100"), ttl)
// Different users may filter differently, but all get same cached result
```

**Why this is dangerous:**
The cache key doesn't capture the query parameters. Requests with different
filters/pagination return the same cached result. Worse: if the underlying
query changes (e.g., adding a date filter), the cache key doesn't change.

**Right approach:**
```go
// Include all query parameters in the cache key
key := fmt.Sprintf("orders:status=%s:limit=%d:offset=%d", status, limit, offset)
```

---

## AE-8: Using Redis as primary data store without persistence or replication

```go
// WRONG: data only exists in Redis — if Redis restarts, data is gone
rdb.Set(ctx, "user:session:abc123", sessionData, 0)  // no DB backing
```

**Why this is catastrophic:**
Redis with default config may not persist data (RDB snapshots can lose minutes of data).
If used as sole store without replication, a restart or failover loses all sessions.

**Right approach:**
Either back session data with a database, or ensure Redis has AOF persistence + replicas.
For truly ephemeral data (rate limit counters), document the acceptable data loss window.

---

## AE-9: SET then GET race in cache population

```go
// WRONG: race condition between SET and GET across goroutines
go func() { rdb.Set(ctx, key, newValue, ttl) }()
val := rdb.Get(ctx, key)  // may get old value or new value — non-deterministic
```

**Right approach:**
Use atomic operations or singleflight. If you need read-after-write consistency,
return the written value directly from the write path, not via a subsequent GET.

---

## AE-10: Unbounded cache growth without eviction policy

```
# Redis config
maxmemory 0           # No memory limit — Redis grows until OOM
maxmemory-policy noeviction  # When maxmemory hit, reject writes with OOM error
```

**Why this fails:**
Without `maxmemory`, Redis grows until the OS kills it (OOM). With `noeviction`,
once memory limit is reached, all SET commands fail — cache becomes read-only.

**Right approach:**
```
maxmemory 2gb                    # Set appropriate limit
maxmemory-policy allkeys-lru     # LRU eviction for general caching
# Or: allkeys-lfu for frequency-based (Redis 4.0+)
```

---

## AE-11: Caching sensitive data without considering expiry and access control

```go
// WRONG: PII cached in shared Redis with long TTL and no access segmentation
rdb.Set(ctx, "user:profile:123", fullProfileWithSSN, 24*time.Hour)
```

**Why this is a security issue:**
Sensitive data in cache outlives its usefulness. If Redis is shared across services,
other services can read PII they shouldn't access. Long TTL means stale PII persists.

**Right approach:**
- Short TTL for sensitive data (minutes, not hours)
- Separate Redis instance or keyspace for PII
- Consider encrypting cached PII at rest
- ACL to restrict which services can access PII keys

---

## AE-12: Cache invalidation via wildcard pattern in production

```go
// WRONG: SCAN + DEL pattern in hot path — unpredictable latency
iter := rdb.Scan(ctx, 0, "user:123:*", 100).Iterator()
for iter.Next(ctx) {
    rdb.Del(ctx, iter.Val())
}
```

**Why this is problematic:**
SCAN is O(N) over the keyspace — even with `COUNT` hint, Redis must iterate internally.
In hot path, this adds unpredictable latency. With millions of keys, each SCAN call
may take 10-100ms.

**Right approach:**
Use structured key design so invalidation targets exact keys:
```go
// Instead of scanning for user:123:*, maintain an explicit list
rdb.Del(ctx, "user:123:profile", "user:123:settings", "user:123:prefs")
// Or: use Redis Hash — one HDEL covers all fields
rdb.Del(ctx, "user:123")  // if user data is a single Hash
```

---

## AE-13: Ignoring cache during load testing

```
// WRONG: load test always warms cache on first request, then subsequent
// requests hit cache — test shows great latency but doesn't reflect
// cache-miss scenarios, stampede risk, or cold-start behavior
```

**Why this hides real problems:**
Load tests with warm cache show optimistic results. Production experiences:
cold starts after deploy, cache invalidation storms, and hot key rotation.

**Right approach:**
- Test with cache disabled (pure DB load)
- Test cold start: flush cache before test, measure warmup time
- Test stampede: expire hot keys mid-test
- Test degradation: kill Redis mid-test, verify fallback behavior