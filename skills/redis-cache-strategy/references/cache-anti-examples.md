# Cache Anti-Examples

Every anti-example this skill ships. AE-1 to AE-6 are the six a review must
recognise on sight; AE-7 to AE-13 are the longer tail. §10 of SKILL.md loads
this file for any review or troubleshoot request.

- [AE-1: Immortal cache key — no TTL set](#ae-1-immortal-cache-key--no-ttl-set)
- [AE-2: Write-behind without durable queue](#ae-2-write-behind-without-durable-queue)
- [AE-3: Cache-aside without stampede protection](#ae-3-cache-aside-without-stampede-protection)
- [AE-4: KEYS command for batch invalidation](#ae-4-keys-command-for-batch-invalidation)
- [AE-5: Distributed lock without TTL or safe release](#ae-5-distributed-lock-without-ttl-or-safe-release)
- [AE-6: Cache issue reported as business logic bug](#ae-6-cache-issue-reported-as-business-logic-bug)
- [AE-7: Caching database query results with mutable WHERE clauses](#ae-7-caching-database-query-results-with-mutable-where-clauses)
- [AE-8: Using Redis as primary data store without persistence or replication](#ae-8-using-redis-as-primary-data-store-without-persistence-or-replication)
- [AE-9: SET then GET race in cache population](#ae-9-set-then-get-race-in-cache-population)
- [AE-10: Unbounded cache growth without eviction policy](#ae-10-unbounded-cache-growth-without-eviction-policy)
- [AE-11: Caching sensitive data without considering expiry and access control](#ae-11-caching-sensitive-data-without-considering-expiry-and-access-control)
- [AE-12: Cache invalidation via wildcard pattern in production](#ae-12-cache-invalidation-via-wildcard-pattern-in-production)
- [AE-13: Ignoring cache during load testing](#ae-13-ignoring-cache-during-load-testing)

---

## AE-1: Immortal cache key — no TTL set
```go
// WRONG: key lives forever; stale data never expires
rdb.Set(ctx, "user:123", userData, 0)  // 0 = no expiration
// RIGHT: always set TTL with jitter, and check that the write landed
ttl := 30*time.Minute + time.Duration(rand.Intn(300))*time.Second
if err := rdb.Set(ctx, "user:123", userData, ttl).Err(); err != nil {
    slog.WarnContext(ctx, "cache populate failed", "key", "user:123", "err", err)
}
```

## AE-2: Write-behind without durable queue
```go
// WRONG: write to Redis, async goroutine writes DB — if process crashes, data lost
rdb.Set(ctx, key, value, ttl)
go func() { db.Save(value) }()  // fire-and-forget = data loss risk
// RIGHT: use durable queue (Kafka, Redis Stream with ACK) between cache and DB
```

## AE-3: Cache-aside without stampede protection
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

## AE-4: KEYS command for batch invalidation
```go
// WRONG: KEYS blocks Redis for the entire scan — O(N) on all keys
keys, _ := rdb.Keys(ctx, "user:*").Result()
rdb.Del(ctx, keys...)
// RIGHT: use SCAN with bounded cursor iteration, or structured invalidation
```

## AE-5: Distributed lock without TTL or safe release
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

## AE-6: Cache issue reported as business logic bug
```
-- WRONG: "Bug: user sees old profile after update"
-- This is a cache staleness issue, not a logic bug. Check invalidation strategy.
-- RIGHT: report as "Cache consistency: stale read after write — invalidation delay"
```

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
// Instead of scanning for user:123:*, delete the exact known keys.
// A failed invalidation leaves stale data with no record — it must be returned,
// not discarded, so the caller can retry or fall back to the durable path.
func invalidateUser(ctx context.Context, id string) error {
    keys := []string{
        "user:" + id + ":profile",
        "user:" + id + ":settings",
        "user:" + id + ":prefs",
    }
    if err := rdb.Del(ctx, keys...).Err(); err != nil {
        return fmt.Errorf("invalidate user %s: %w", id, err)
    }
    return nil
}
```

If the entity is stored as a single Hash, one `DEL` of that key covers every
field — but see §5 item H2 in `SKILL.md` before reshaping data into a Hash for
this reason alone: it is the right move only when readers actually fetch fields
individually.

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