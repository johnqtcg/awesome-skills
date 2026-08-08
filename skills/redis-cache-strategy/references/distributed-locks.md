# Redis Distributed Locks — What They Do and Do Not Guarantee

Load when a design uses a Redis lock for anything beyond suppressing duplicate
cache fills. All Go below is compiled by `scripts/check_go_snippets.py` against
`github.com/redis/go-redis/v9`.

---

## 1. The one-sentence version

A Redis lock is a **lease**, not a lock. It guarantees that at most one holder
has an *unexpired* token — it cannot guarantee that at most one holder is
*running*, because it has no way to stop a process that is slow, paused, or
partitioned. Every rule below follows from that distinction.

---

## 2. Classification: which kind of lock do you have?

| Class | What the lock protects | Minimum design |
|-------|------------------------|----------------|
| **Efficiency** | Duplicate work that is harmless if it happens twice (cache fill, idempotent recompute, a cron job that is safe to run twice) | TTL + unique token + Lua CAS release |
| **Correctness** | An external effect that must not happen twice (DB write, payment, file move, third-party API call) | Everything above **plus fencing tokens enforced by the protected resource** |

Getting this classification wrong is the root cause of most Redis-lock
incidents. A lock introduced for efficiency quietly acquires a correctness role
the first time someone adds a write inside the critical section.

**If it is a correctness lock, the honest answer is usually: do not use Redis.**
Enforce mutual exclusion where the data lives — a unique constraint, a
conditional `UPDATE ... WHERE version = ?`, `SELECT ... FOR UPDATE`, or a system
built for consensus (ZooKeeper, etcd). Redis then becomes an optimization that
keeps contention off that mechanism, not the mechanism itself.

---

## 3. Acquire — with a fencing token

Acquisition and token issuance must be one atomic step, or two holders can be
issued the same token.

```go
// KEYS[1] = lock key, KEYS[2] = fence counter key
// ARGV[1] = unique token,  ARGV[2] = ttl in milliseconds
var acquireScript = redis.NewScript(`
if redis.call('SET', KEYS[1], ARGV[1], 'NX', 'PX', ARGV[2]) then
  return redis.call('INCR', KEYS[2])
end
return nil
`)

// acquire returns a strictly increasing fence number, or an error if the lock
// is held. The fence number — not the token — is what downstream systems check.
func acquire(ctx context.Context, lockKey, fenceKey, token string, ttl time.Duration) (int64, error) {
    fence, err := acquireScript.Run(ctx, rdb,
        []string{lockKey, fenceKey}, token, ttl.Milliseconds()).Int64()
    if errors.Is(err, redis.Nil) {
        return 0, ErrLockHeld
    }
    if err != nil {
        return 0, fmt.Errorf("acquire %s: %w", lockKey, err)
    }
    return fence, nil
}
```

The token must come from `crypto/rand` or a UUID — never a counter, a hostname,
or a timestamp. Two holders with the same token can each pass the other's CAS
release check.

---

## 4. Fencing — the part that is usually skipped

The fence number is worthless unless the **protected resource** enforces it.
The check belongs at the write, not at the lock.

```sql
-- The resource rejects any writer whose fence is not strictly newer.
UPDATE orders
   SET state = $1, last_fence = $2
 WHERE id = $3
   AND last_fence < $2;
-- 0 rows affected  ⇒  a newer holder already wrote. Abort; do not retry.
```

Why this is required, in the only sequence that matters:

```
Holder A: acquire (fence=41) ─┬─ GC pause / CPU starvation / network partition ──┐
                              │   (lock TTL expires during the pause)            │
Holder B:                     └─ acquire (fence=42) → writes → releases          │
Holder A:  resumes, still believes it holds the lock ─────────────────────────────┘
           → writes with fence=41 → OVERWRITES B's newer write
```

No Redis-side design prevents this. Not a longer TTL (the pause can always be
longer), not renewal (a paused process cannot renew), not Redlock (its own
documentation is explicit that it does not address a paused client). Only the
resource refusing the stale fence prevents it — which is why fencing is listed
as **required** for correctness locks and merely nice-to-have for efficiency
locks.

---

## 5. Renewal — bounded, always

```go
var renewScript = redis.NewScript(`
if redis.call('GET', KEYS[1]) == ARGV[1] then
  return redis.call('PEXPIRE', KEYS[1], ARGV[2])
end
return 0
`)

// renewOnce reports whether this holder still owns the lock. false means it was
// lost — the caller MUST abort the critical section, not keep working.
func renewOnce(ctx context.Context, lockKey, token string, ttl time.Duration) (bool, error) {
    ok, err := renewScript.Run(ctx, rdb, []string{lockKey}, token, ttl.Milliseconds()).Int64()
    if err != nil {
        return false, fmt.Errorf("renew %s: %w", lockKey, err)
    }
    return ok == 1, nil
}
```

Rules:

- **Renew on ownership, never blindly.** A bare `PEXPIRE` extends whoever holds
  the lock now — possibly a different holder. The CAS above is mandatory.
- **Cap total hold time.** `maxHold = renewInterval × maxRenewals`, chosen from
  the work's p99 duration plus headroom. Unbounded renewal turns a hung holder
  into a permanent lock, which is worse than the deadlock the TTL prevented.
- **Renew at TTL/3 or faster.** One lost renewal must not expire the lock.
- **A failed renewal is a lost lock.** Cancel the context and abandon the work.
  Continuing after `renewOnce` returns false is the same bug as having no lock.

---

## 6. Release

```go
var releaseScript = redis.NewScript(`
if redis.call('GET', KEYS[1]) == ARGV[1] then
  return redis.call('DEL', KEYS[1])
end
return 0
`)

func release(ctx context.Context, lockKey, token string) error {
    if _, err := releaseScript.Run(ctx, rdb, []string{lockKey}, token).Int64(); err != nil {
        return fmt.Errorf("release %s: %w", lockKey, err)
    }
    return nil
}
```

A plain `DEL` deletes whatever is there — including the lock a *different*
holder acquired after yours expired. Release always goes through the CAS.

---

## 7. Failover

Redis replication is asynchronous. A lock `SET` on the master is acknowledged
before it reaches any replica, so:

```
master accepts SET lock:X (holder A)  →  master dies before replicating
replica promoted (no lock:X)          →  holder B acquires lock:X
                                      →  A and B both hold it
```

This is inherent to any asynchronously-replicated store; `WAIT` narrows the
window but does not close it and costs latency on every acquisition. Redlock
(quorum across N independent masters) addresses this specific failure but adds
its own assumptions — bounded clock drift and bounded process pauses — and does
**not** address §4 at all.

Practical guidance:

- Sentinel/Cluster + a single-instance lock: acceptable for **efficiency** locks.
  Document that a failover may double-run the work.
- **Correctness** locks: fence at the resource (§4). Once fencing is in place,
  failover degrades to duplicated work rather than corrupted data — and the
  quorum machinery of Redlock stops being load-bearing.

---

## 8. Review checklist

Mark PASS/WARN/FAIL per item; any FAIL in the Correctness column blocks.

| # | Check | Efficiency | Correctness |
|---|-------|:----------:|:-----------:|
| 1 | TTL set on acquisition | required | required |
| 2 | Token from `crypto/rand`/UUID, unique per acquisition | required | required |
| 3 | Release via Lua CAS on the token | required | required |
| 4 | TTL ≥ p99 work duration, or renewal implemented | required | required |
| 5 | Renewal is CAS-on-ownership, not bare `PEXPIRE` | required | required |
| 6 | Renewal capped by a maximum total hold time | required | required |
| 7 | Lost renewal aborts the critical section | required | required |
| 8 | Fencing token issued atomically with acquisition | recommended | **required** |
| 9 | Protected resource rejects stale fence numbers | — | **required** |
| 10 | Failover double-grant documented and accepted | required | required |
| 11 | Acquisition failure path defined (fail fast / bounded retry / queue) | required | required |
| 12 | Lock hold time and contention exported as metrics | recommended | required |

Item 9 is the one that is almost always missing. A design that issues fence
numbers but has no resource-side check has not implemented fencing — it has
implemented a counter.
