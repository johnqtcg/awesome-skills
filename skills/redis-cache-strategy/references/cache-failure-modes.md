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
    val, err := rdb.Get(ctx, key).Bytes()
    switch {
    case err == nil:
        return val, nil
    case errors.Is(err, redis.Nil):
        // True miss — the only case that may fall through to the DB.
    default:
        // Redis is erroring, not empty. Falling through here sends 100% of
        // traffic to the DB in one step: the outage becomes a stampede.
        return nil, fmt.Errorf("%w: %v", ErrCacheUnavailable, err)
    }

    result, err, _ := sfGroup.Do(key, func() (any, error) {
        data, err := db.Fetch(ctx, key)
        if err != nil {
            return nil, fmt.Errorf("fetch %s: %w", key, err)
        }
        if err := rdb.Set(ctx, key, data, baseTTL+jitter()).Err(); err != nil {
            // Population failed: serve the value, but this must alert —
            // every later read misses until Redis recovers.
            slog.WarnContext(ctx, "cache populate failed", "key", key, "err", err)
        }
        return data, nil
    })
    if err != nil {
        return nil, err
    }
    b, ok := result.([]byte)
    if !ok {
        return nil, fmt.Errorf("singleflight returned %T, want []byte", result)
    }
    return b, nil
}
```

Three things the naive version of this gets wrong, all of which have shipped:

- **`return result.([]byte), err`** — when `err != nil`, `result` is a nil
  interface and the assertion **panics**. Check `err` first, then assert with
  the two-value form.
- **Treating every Redis error as a miss.** `redis.Nil` means "not cached";
  anything else means "Redis is unwell". Only the first may fall through.
- **Discarding the `SET` error.** A silent population failure looks identical
  to a cold cache and produces permanent full-rate DB load.

`sfGroup.Do` also returns `shared bool` as its third value. Bind it with `_`
unless you use it — Go rejects an unused named variable, so `result, err, shared :=`
does not compile on its own.

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
// nullMarker must be a value the real encoder can never emit. A bare
// "__NULL__" collides with any string value that happens to equal it —
// use a sentinel that is invalid in your value encoding (here: not valid JSON).
const nullMarker = "\x00null"

func fetchWithNullCache(ctx context.Context, key, id string) ([]byte, error) {
    val, err := rdb.Get(ctx, key).Result()
    switch {
    case err == nil:
        if val == nullMarker {
            return nil, ErrNotFound
        }
        return []byte(val), nil
    case errors.Is(err, redis.Nil):
        // fall through to the DB
    default:
        return nil, fmt.Errorf("%w: %v", ErrCacheUnavailable, err)
    }

    row, err := db.Fetch(ctx, id)
    if errors.Is(err, sql.ErrNoRows) {
        // Cache "not found" with a short TTL to stop repeated DB queries.
        if err := rdb.Set(ctx, key, nullMarker, 60*time.Second).Err(); err != nil {
            slog.WarnContext(ctx, "null-cache write failed", "key", key, "err", err)
        }
        return nil, ErrNotFound
    }
    if err != nil {
        return nil, fmt.Errorf("fetch %s: %w", id, err)
    }
    return row, nil
}
```

Use `errors.Is`, not `==`, for both `redis.Nil` and `sql.ErrNoRows`: a wrapped
error from any middleware layer makes `==` silently false, which turns a
not-found into a 500 and defeats the null cache entirely.

**Tradeoff**: wastes some Redis memory on null entries. Use short TTL (30-60s)
and monitor null-entry count.

### Defense: Bloom Filter

Pre-load a bloom filter with all valid IDs. Check bloom filter before cache/DB.

```go
// On startup and on a refresh interval: load all valid IDs into the filter.
func warmBloom() {
    bloom.AddAll(db.FetchAllIDs())
}

func Get(ctx context.Context, id string) (*Entity, error) {
    if !bloom.MayContain(id) {
        // Absent from the filter ⇒ absent from the DB *as of the last rebuild*.
        return nil, ErrNotFound
    }
    // ... proceed to cache-aside pattern
    return nil, nil
}
```

**Tradeoff**: bloom filters have false positives (allow some invalid IDs through)
but zero false negatives. Memory-efficient: 1M entries ≈ 1.2MB at 1% FPR.

**Two operational constraints that decide whether this is usable at all:**

- **A standard bloom filter cannot delete.** A row deleted from the DB stays
  "maybe present" until the filter is rebuilt, so the filter never rejects it
  and the null cache has to carry that load. If deletes are frequent, use a
  counting/cuckoo filter or drop the bloom layer.
- **Newly inserted IDs are false negatives until the next rebuild** — the filter
  will answer "definitely not in DB" for a row that *is* in the DB, and the
  request 404s. Either add every new ID to the filter on the write path, or
  accept a wrong 404 for up to one rebuild interval and say so in §9.4. This is
  the failure mode that makes bloom filters unsafe to bolt on without thought:
  it turns a cache layer into a source of incorrect answers.

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
// jitteredTTL returns base ±20%.
//
// The arithmetic is in nanoseconds, not seconds, for a reason: computing the
// span as int(base.Seconds()*0.2) truncates to 0 for any base under 5s, and
// rand.Intn(0) PANICS. This skill recommends 1-5s L1 TTLs and 30-60s null-cache
// TTLs, so the short-TTL path is the common case, not an edge case.
func jitteredTTL(base time.Duration) time.Duration {
    span := int64(base) / 5
    if span <= 0 {
        return base
    }
    return base + time.Duration(rand.Int63n(2*span)-span)
}

// Usage: 30 min ± 6 min → keys expire between 24 and 36 minutes.
func setJittered(ctx context.Context, key string, value []byte) error {
    return rdb.Set(ctx, key, value, jitteredTTL(30*time.Minute)).Err()
}
```

**Jitter must be applied at write time, per key.** A single TTL constant
randomised once at startup gives every key on that process the same expiry —
the avalanche is unchanged, just shifted. And note that jitter only spreads
*expiry*; if all keys were populated by one warmup batch, they still share a
population time, so widen the jitter to at least the width of that batch.

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
// ristretto.NewCache returns (*Cache, error) — it validates Config and fails
// on a zero NumCounters/MaxCost. Verified against ristretto v0.2.0.
func newL1() (*ristretto.Cache, error) {
    c, err := ristretto.NewCache(&ristretto.Config{
        NumCounters: 1e4,
        MaxCost:     1 << 20, // 1MB
        BufferItems: 64,
    })
    if err != nil {
        return nil, fmt.Errorf("init L1 cache: %w", err)
    }
    return c, nil
}

func getL1(ctx context.Context, l1 *ristretto.Cache, key string) ([]byte, error) {
    // L1: local cache. Get returns (interface{}, bool) — assert with the
    // two-value form; a bare val.([]byte) panics on a type you did not store.
    if v, found := l1.Get(key); found {
        if b, ok := v.([]byte); ok {
            return b, nil
        }
    }
    // L2: Redis
    val, err := rdb.Get(ctx, key).Bytes()
    if err != nil {
        return nil, err // caller distinguishes redis.Nil from an outage
    }
    // cost must reflect real size, otherwise MaxCost cannot bound memory
    l1.SetWithTTL(key, val, int64(len(val)), 5*time.Second)
    return val, nil
}
```

**Ristretto semantics that change how you must use L1** (v0.2.0):

- `Set`/`SetWithTTL` are **asynchronous**. They return `true` meaning "accepted
  into the buffer", not "readable now". The very next `Get` may miss. Call
  `Wait()` in tests; never assert read-your-write on L1 in production code.
- The admission policy (TinyLFU) **may reject an item outright**. A key you
  just wrote can be absent forever. L1 is an optimization, never a store.
- Because each process has its own L1, an L1 TTL of *T* means the cluster-wide
  staleness window is *T* **on top of** the Redis TTL. Keep L1 TTL at 1–5s and
  add it to the staleness SLA you publish in §9.4.

### Defense: Key Sharding (replica fan-out)

Split one logical key into N physical **replicas** that all hold the same value.
Reads pick a replica per request; writes must update every replica.

> **The bug this section exists to prevent**: deriving the replica from a hash
> of the key — `crc32.ChecksumIEEE([]byte(key)) % shardCount` — is
> deterministic. Every reader of the same logical key computes the same
> replica, so all traffic still lands on one key on one node. It spreads
> nothing. The replica index must come from the *caller*, not from the key.

```go
const shardCount = 8

var rrCounter atomic.Uint64

// physicalKey names replica `replica` of a logical hot key.
//
// No Redis Cluster hash tag: hashing the whole key spreads the N replicas over
// different slots, which is the point. A "{replica}" tag would hash only the
// index, pinning replica 3 of *every* hot key to one slot — re-concentrating
// exactly the load this is meant to spread.
func physicalKey(logical string, replica uint64) string {
    return fmt.Sprintf("%s|r%d", logical, replica)
}

// Read: round-robin. An atomic counter spreads evenly with no RNG contention;
// rand.IntN(shardCount) is equally acceptable. Either way the choice is made
// per call, independent of the key.
func readHot(ctx context.Context, logical string) ([]byte, error) {
    replica := rrCounter.Add(1) % shardCount
    return rdb.Get(ctx, physicalKey(logical, replica)).Bytes()
}

// Write: fan out to every replica, one shared value and one shared TTL.
func writeHot(ctx context.Context, logical string, val []byte, ttl time.Duration) error {
    pipe := rdb.Pipeline()
    for i := uint64(0); i < shardCount; i++ {
        pipe.Set(ctx, physicalKey(logical, i), val, ttl)
    }
    if _, err := pipe.Exec(ctx); err != nil {
        // Partial failure is a real failure: some replicas now serve old data.
        return fmt.Errorf("fan-out write %s: %w", logical, err)
    }
    return nil
}

// Invalidate: DEL on the logical key deletes nothing. All N must go.
func invalidateHot(ctx context.Context, logical string) error {
    pipe := rdb.Pipeline()
    for i := uint64(0); i < shardCount; i++ {
        pipe.Del(ctx, physicalKey(logical, i))
    }
    if _, err := pipe.Exec(ctx); err != nil {
        return fmt.Errorf("fan-out invalidate %s: %w", logical, err)
    }
    return nil
}
```

#### Consistency rules for a replicated hot key

Fan-out buys throughput and pays for it in consistency. State these four rules
in §9.4 whenever you propose sharding, or the design is incomplete:

1. **The fan-out is not atomic.** Between the first and last `SET`, concurrent
   readers see a mix of old and new depending on which replica they drew. The
   staleness window is the pipeline duration, not zero. Acceptable for
   whole-value overwrites (a rendered product page, a counter snapshot); **not**
   acceptable for read-modify-write, where two writers interleaving across
   replicas leave the set permanently inconsistent.
2. **Identical TTL across replicas — put the jitter on the logical key, not
   between its replicas.** Compute the TTL once and apply the same value to all
   N. Independent per-replica jitter makes them expire at different times, so a
   reader round-robining across replicas can observe a *newer* value, then an
   *older* one, then newer again — non-monotonic reads that are far harder to
   debug than plain staleness.
3. **Repopulate under one singleflight key: the logical key.** Replicas expire
   together (rule 2), so a miss storm without this produces N concurrent DB
   queries — the stampede sharding was supposed to survive.
4. **Prefer a generation counter over N-key deletion.** Partial `DEL` failure
   leaves live stale replicas with no record of which. Putting a generation in
   the key makes invalidation a single `INCR`; old replicas become unreachable
   and expire on their own.

```go
func genKey(logical string, gen, replica uint64) string {
    return fmt.Sprintf("%s|g%d|r%d", logical, gen, replica)
}
```

**Cost check before sharding**: N replicas multiply memory for that key by N and
multiply every write by N. If reads dominate and the value is small, that is a
good trade. If not, an L1 cache (above) usually beats sharding — it removes the
Redis round trip entirely instead of spreading it.

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