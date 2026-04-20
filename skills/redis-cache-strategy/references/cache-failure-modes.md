# Redis Cache Failure Modes & Defenses

Four failure modes that cause production incidents when caching layers are
improperly designed. Each has distinct triggers, symptoms, and mitigations.

---

## 1. Cache Stampede (Thundering Herd)

### Trigger
A hot key expires (or is invalidated), and many concurrent requests simultaneously
miss the cache and query the database.

### Symptom
- Sudden DB CPU/connection spike when a popular cache key expires
- Response latency spikes correlated with cache TTL intervals
- Database connection pool exhaustion

### Defense: Singleflight / Mutex

Only one request fetches from DB; others wait for the result.

```go
import "golang.org/x/sync/singleflight"

var sfGroup singleflight.Group

func GetWithSingleflight(ctx context.Context, key string) ([]byte, error) {
    // Check cache first
    val, err := rdb.Get(ctx, key).Bytes()
    if err == nil {
        return val, nil
    }

    // Singleflight: only one goroutine queries DB for this key
    result, err, shared := sfGroup.Do(key, func() (interface{}, error) {
        data, err := db.Fetch(ctx, key)
        if err != nil {
            return nil, err
        }
        ttl := baseTTL + jitter()
        rdb.Set(ctx, key, data, ttl)
        return data, nil
    })
    // shared=true means this caller waited for another's result
    return result.([]byte), err
}
```

### Defense: Stale-While-Revalidate

Serve expired value while one background goroutine refreshes. Requires storing
both value and expiry metadata.

```go
type CachedEntry struct {
    Data      []byte
    ExpiresAt time.Time  // logical expiry (earlier than Redis TTL)
    StaleUntil time.Time // Redis TTL (actual hard expiry)
}

// Redis TTL = 2x logical TTL. When logical expires, serve stale + async refresh.
```

### Defense: Probabilistic Early Expiration

Each read has a small chance of triggering refresh before TTL. Distributes
refresh load over time instead of concentrating at expiry.

---

## 2. Cache Penetration

### Trigger
Requests for IDs/keys that do NOT exist in the database. Since there's nothing
to cache, every request always hits the database.

### Symptom
- High cache miss rate for specific key patterns (often sequential/random IDs)
- DB load from queries that always return zero results
- Common in: user-facing APIs with user-supplied IDs, enumeration attacks

### Defense: Null Value Caching

Cache the "not found" result with a short TTL.

```go
val, err := rdb.Get(ctx, key).Result()
if err == redis.Nil {
    dbVal, err := db.Fetch(ctx, id)
    if err == sql.ErrNoRows {
        // Cache "not found" with short TTL to prevent repeated DB queries
        rdb.Set(ctx, key, "__NULL__", 60*time.Second)
        return nil, ErrNotFound
    }
    // ... normal cache population
}
if val == "__NULL__" {
    return nil, ErrNotFound
}
```

**Tradeoff**: wastes some Redis memory on null entries. Use short TTL (30-60s)
and monitor null-entry count.

### Defense: Bloom Filter

Pre-load a bloom filter with all valid IDs. Check bloom filter before cache/DB.

```go
// On startup or periodically: load all valid IDs into bloom filter
bloom.AddAll(db.FetchAllIDs())

func Get(ctx context.Context, id string) (*Entity, error) {
    if !bloom.MayContain(id) {
        return nil, ErrNotFound  // guaranteed not in DB
    }
    // ... proceed to cache-aside pattern
}
```

**Tradeoff**: bloom filters have false positives (allow some invalid IDs through)
but zero false negatives. Memory-efficient: 1M entries ≈ 1.2MB at 1% FPR.

### Combined defense (recommended for APIs with user-supplied IDs)

```
Request → Bloom filter check → Cache check → DB query → Cache result (including nulls)
```

---

## 3. Cache Avalanche

### Trigger
Mass cache expiration at the same time. Causes sudden load transfer from Redis
to the database.

### Symptom
- Periodic DB load spikes at regular intervals (aligned with initial cache population time + fixed TTL)
- Redis `dbsize` drops sharply, then rebuilds over minutes
- Multiple unrelated cache keys expire simultaneously

### Defense: TTL Jitter

Add random variance to TTL so keys expire at different times.

```go
func jitteredTTL(base time.Duration) time.Duration {
    // ±20% jitter
    jitterRange := int(base.Seconds() * 0.2)
    jitter := time.Duration(rand.Intn(2*jitterRange)-jitterRange) * time.Second
    return base + jitter
}

// Usage: 30 min ± 6 min → keys expire between 24 and 36 minutes
rdb.Set(ctx, key, value, jitteredTTL(30*time.Minute))
```

### Defense: Multi-Level Cache (L1 + L2)

Use in-process cache (L1) in front of Redis (L2). When Redis goes down or
keys expire, L1 absorbs some load.

```
Request → L1 (in-process, ~1000 keys, 5s TTL) → L2 (Redis, ~1M keys, 30min TTL) → DB
```

L1 options: Go `sync.Map`, `groupcache`, `ristretto`, Java `Caffeine`.
L1 protects against both avalanche and Redis outage.

### Defense: Circuit Breaker on DB

If DB call rate exceeds threshold, open circuit breaker → serve stale or error
rather than overwhelming the database.

---

## 4. Hot Key

### Trigger
A single cache key receives disproportionate traffic. Even though it's cached,
the Redis instance serving that key becomes a bottleneck.

### Symptom
- Single Redis shard CPU at 100% while others are idle
- Latency spike on specific keys/operations
- In Redis Cluster: slot hotspot on one node
- Detect: `redis-cli --hotkeys` (requires LFU eviction policy), or application metrics

### Defense: Local In-Process Cache (L1)

Cache the hot key locally in each application instance. Short TTL (1-5s) is
fine for hot data.

```go
var localCache = ristretto.NewCache(&ristretto.Config{
    NumCounters: 1e4,
    MaxCost:     1 << 20,  // 1MB
    BufferItems: 64,
})

func Get(ctx context.Context, key string) ([]byte, error) {
    // L1: local cache
    if val, found := localCache.Get(key); found {
        return val.([]byte), nil
    }
    // L2: Redis
    val, err := rdb.Get(ctx, key).Bytes()
    if err == nil {
        localCache.SetWithTTL(key, val, 1, 5*time.Second)
        return val, nil
    }
    // L3: DB (with singleflight)
    // ...
}
```

### Defense: Key Sharding

Split one logical key into N physical keys. Distribute reads across shards.

```go
const shardCount = 8

func shardedKey(key string) string {
    shard := crc32.ChecksumIEEE([]byte(key)) % shardCount
    return fmt.Sprintf("%s:{%d}", key, shard)
}

// Write: update all shards
for i := 0; i < shardCount; i++ {
    rdb.Set(ctx, fmt.Sprintf("%s:{%d}", key, i), value, ttl)
}

// Read: pick random shard
rdb.Get(ctx, shardedKey(key))
```

### Defense: Read Replicas

In Redis Cluster or Sentinel, route reads to replicas for hot keys.
Configure `READONLY` on replica connections.

---

## 5. Combined Defense Matrix

| Failure Mode | Primary Defense | Secondary Defense | Monitor |
|-------------|----------------|-------------------|---------|
| **Stampede** | Singleflight/mutex | Stale-while-revalidate | DB connection spike on key expiry |
| **Penetration** | Null-value caching | Bloom filter | Cache miss rate by key pattern |
| **Avalanche** | TTL jitter | L1 local cache + circuit breaker | DB load correlation with Redis `dbsize` drops |
| **Hot Key** | L1 local cache | Key sharding | Per-key QPS, single-shard CPU |

### When to use multiple defenses

- **Public APIs with user-supplied IDs**: bloom filter + null caching + singleflight
- **E-commerce product pages**: L1 + TTL jitter + singleflight
- **Real-time leaderboards**: write-through + L1 + hot key sharding
- **Session stores**: write-through + circuit breaker + degraded anonymous mode