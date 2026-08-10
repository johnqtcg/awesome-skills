# Redis Version Matrix — What Changes for a Cache

- [1. Why this file exists](#1-why-this-file-exists)
- [2. Lines that are still shipping patches](#2-lines-that-are-still-shipping-patches)
- [3. What each release changed for caching](#3-what-each-release-changed-for-caching)
- [4. The seven version-gated conclusions](#4-the-seven-version-gated-conclusions)
- [5. When the version is genuinely unknown](#5-when-the-version-is-genuinely-unknown)
- [6. Verifying a claim in this file](#6-verifying-a-claim-in-this-file)

---

## 1. Why this file exists

A caching review that assumes one Redis version is wrong twice: it invents
constraints that the deployed server does not have, and it hides the primitive
that would have been the correct answer. Both failures look like a clean review.

The 8.x line in particular changed answers this skill used to give
unconditionally — compare-and-delete now exists as a command, hot-key detection
is server-side, and a deletable membership filter ships in the box. None of that
is reachable from a review that silently assumed 6.0.

**The version is not a global default. It is a per-conclusion gate.** Most of
what this skill says (source of truth, stampede, degradation, staleness SLA,
fencing) is version-independent and should never be blocked on it. §4 lists the
conclusions that are not.

## 2. Lines that are still shipping patches

As of 2026-08, the upstream project still cuts patch releases on all of these,
so all of them are live in production somewhere:

| Line | Most recent patch seen | Note |
|------|------------------------|------|
| 6.2 | 6.2.23 (2026-07) | Pre-listpack config names; no per-field hash TTL |
| 7.2 | 7.2.15 (2026-07) | Listpack names and encodings |
| 7.4 | 7.4.10 (2026-07) | Adds `HEXPIRE` |
| 8.0 | 8.0.x | First unified distribution |
| 8.2 | 8.2.8 (2026-07) | |
| 8.4 | 8.4.5 (2026-07) | |
| 8.6 | 8.6.5 (2026-07) | |
| 8.8 | 8.8.1 (2026-07) | |
| 8.10 | 8.10.0 (2026-07-29) | Newest GA at the time of writing |

Two consequences for a review:

1. **"Old" does not mean unsupported.** A 6.2 or 7.2 deployment is a normal,
   patched production system, not a migration finding. Do not open a review by
   telling the user to upgrade unless a conclusion actually needs it.
2. **"Latest" moves twice a year.** Any statement in this skill of the form
   "Redis cannot do X" is a claim with an expiry date. Check §6 before repeating
   one.

## 3. What each release changed for caching

Only entries that change a recommendation in this skill are listed.

### 7.0
- Hash/zset encoding thresholds renamed `hash-max-ziplist-*` → `hash-max-listpack-*`
  (the old names still work as aliases). `OBJECT ENCODING` reports `listpack`.
  On 6.x you must read and set the `ziplist` names — §5 H2's advice is otherwise
  unchanged.

### 7.4
- `HEXPIRE` and friends: **per-field TTL on a Hash**. This is the version gate
  under §5 H2's TTL bullet. Below 7.4 a Hash has exactly one expiry for the whole
  key, which is frequently the reason a Hash is the wrong shape for a cache
  entry.

### 8.0
- The distribution unified: the Query Engine, JSON, Time series, and five
  probabilistic structures — **Bloom filter, Cuckoo filter**, Count-min sketch,
  Top-k, t-digest — are part of Redis itself, no separate module install.
  - For §5 S3 (penetration) this is the difference between "you need a bloom
    filter and it cannot delete" and "use `CF.*` (8.0+), which can". A cuckoo
    filter supports `CF.DEL` (8.0+), so a row deleted from the DB stops being
    "maybe present" without a full rebuild.
  - New ACL categories `@bloom`, `@cuckoo` — relevant if the cache user is
    restricted.
- New hash commands `HGETDEL`, `HGETEX`, `HSETEX`.

### 8.2
- Keyspace notification event types `OVERWRITTEN` (a key's value was fully
  replaced) and `TYPE_CHANGED` — finer signals than inferring an overwrite from
  a generic `set` event.

  **Read the reliability tier before designing on this.** Keyspace notifications
  are Pub/Sub, and the Redis documentation is explicit that Pub/Sub is *fire and
  forget*: "if your Pub/Sub client disconnects, and reconnects later, all the
  events delivered during the time the client was disconnected are lost." The
  same page states that in a cluster, "every node of a Redis cluster generates
  events about its own subset of the keyspace" and those notifications "**are
  not** broadcasted to all nodes" — a listener must subscribe to every node, and
  a resharding changes which node owns which key.

  Three consequences that decide where this belongs (§5 C2):

  1. **It is not durable.** A dropped connection is silent, unbounded data loss
     of invalidations. It cannot sit in the same tier as CDC or a transactional
     outbox, both of which survive the consumer being down.
  2. **It reports a Redis key change, not a row change.** `OVERWRITTEN` (8.2+)
     fires when something overwrote the cache entry. If the database was updated
     and the cache write is the step that failed, there is no event at all —
     which is exactly the case §5 C3 exists to handle.
  3. **Cluster requires N subscriptions**, re-established on topology change.

  Legitimate use: best-effort **L2 (Redis) → L1 (in-process)** invalidation, so
  local caches drop a key sooner than their TTL would. Always with a TTL floor
  and a resync path, never as the only mechanism, and never for a design with a
  staleness SLA.
- Per-slot usage metrics and key-size distributions — cheaper hot-slot evidence
  than sampling from the client.

### 8.4
- **`SET … IFEQ` / `IFNE` / `IFDEQ` / `IFDNE`, and `DELEX … IFEQ`** — atomic
  compare-and-set and compare-and-delete on string keys.
  - §5 S7: the Lua CAS release script becomes `DELEX lock:X IFEQ <token>`. The
    Lua version stays correct and stays necessary below 8.4; on 8.4+ prefer the
    command, because it removes a script from the lock path and cannot be
    misapplied to the wrong `KEYS` arity.
  - §5 C3 / write-through: `SET key val IFEQ <previous>` gives a version-guarded
    cache write without Lua, which is the guard `cache-patterns.md` §2 requires
    to stop two concurrent writers inverting.
  - `DELEX` (8.4+) returns 1 when it deleted, 0 when the key was absent **or**
    the condition did not match. Those two are not distinguished — if you need
    to tell them apart, check existence separately and accept the race, or keep
    the Lua CAS.
- `MSETEX`, atomic slot migration (`CLUSTER MIGRATION`), `CLUSTER SLOT-STATS`.

### 8.6
- **`HOTKEYS`** — server-side hot-key tracking, a container command:
  `HOTKEYS START METRICS <n> [CPU] [NET] [COUNT k] [DURATION s] [SAMPLE ratio]`,
  then `HOTKEYS GET`, `HOTKEYS STOP`, `HOTKEYS RESET`.
  - It ranks by **CPU time and network bytes**, not by request count. A key with
    modest QPS and a 2MB value can outrank a genuinely hot small key — which is
    usually what you want for §5 S5, but it is not the same metric as "QPS on
    this key", so do not report it as one.
  - `redis-cli --hotkeys` (4.0+, requires an LFU policy) remains the fallback
    below 8.6, and it estimates from LFU counters rather than measuring.
- Eviction policies `volatile-lrm` / `allkeys-lrm` — least recently *modified*,
  a fourth option for §5 H3 alongside LRU, LFU, random and TTL.
- `XADD` idempotency arguments (`IDMPAUTO`, `IDMP`) — relevant if the write-behind
  queue (§5 C6) is a Redis Stream.

### 8.8
- `INCREX` — a window counter combining `INCR`/`INCRBY` with bounds and
  expiration in one command. The usual hand-rolled `INCR` + `EXPIRE` pair for a
  rate-limited DB bypass (§5 C5) is no longer two round trips with a gap where
  the key can be immortal.
- Field-level (subkey) notifications for hash fields.

### 8.10
- **Compact hashes**: a hash encoding that stores field names once across keys
  sharing a schema. This narrows the "a hashtable-encoded Hash is larger than the
  equivalent String" gap in §5 H2. It does not reverse the guidance — access
  granularity still decides the shape — but the memory arithmetic must be
  measured on 8.10+ rather than assumed from the older numbers.
- `HIMPORT` for bulk hash insertion (warmup, §5 H5).

## 4. The seven version-gated conclusions

These are the only conclusions in this skill that need the version. Everything
else is answerable without it.

| # | Conclusion | Gate | If below the gate |
|---|-----------|------|-------------------|
| 1 | Per-field TTL on a Hash | 7.4 | One TTL per key; often means "do not use a Hash" |
| 2 | `hash-max-listpack-*` config/encoding names | 7.0 | Use `hash-max-ziplist-*`; the thresholds are the same |
| 3 | Deletable membership filter (`CF.*`) | 8.0 | Bloom only: no deletes, rebuild-interval false negatives |
| 4 | `OVERWRITTEN` / `TYPE_CHANGED` keyspace events (best-effort L2→L1 only — Pub/Sub, lossy, node-local) | 8.2 | Infer from generic `set`/`del` events; the reliability tier is unchanged either way |
| 5 | `SET … IFEQ`, `DELEX … IFEQ` | 8.4 | Lua CAS — still correct, one more moving part |
| 6 | `HOTKEYS`; `*-lrm` eviction | 8.6 | `redis-cli --hotkeys` (needs LFU); LRU/LFU/TTL/random only |
| 7 | Compact-hash memory arithmetic | 8.10 | Hashtable-encoded Hash is larger than the String |

## 5. When the version is genuinely unknown

Do **not** pick a default. Two honest outputs, in order of preference:

1. **Branch the conclusion.** "On 8.4+ release the lock with
   `DELEX key IFEQ token`; below that use the Lua CAS in
   `distributed-locks.md` §6." Costs two sentences and is correct either way.
   Prefer this whenever both branches are short.
2. **Mark the item NOT SCOREABLE** (§5) when the branches diverge enough that
   guessing changes the design — for example, whether the penetration defense
   can rely on deletion. Record it in §9.9 with the question that would resolve
   it. A NOT SCOREABLE Critical item caps the whole review at INCOMPLETE, which
   is the correct outcome: you cannot certify what you could not evaluate.

What is never acceptable is stating a version-gated conclusion flatly. "Redis
cannot compare-and-delete without Lua" was true for fifteen years and has been
false since 8.4; a review that says it on an 8.6 cluster is wrong, and nothing
in the output would show it.

## 6. Verifying a claim in this file

Every "since" claim here was taken from the upstream repository, not from
recollection or a blog post:

- Command availability: `src/commands/<name>.json` in `redis/redis` carries a
  `since` field, and `SET`'s file carries a `history` array listing the version
  that added each option.
- Config and policy names: `src/config.c` — `maxmemory_policy_enum[]` for
  eviction policies, `createSizeTConfig(...)` for the listpack names and their
  ziplist aliases.
- What a minor release contains: the GitHub release body for that tag.

`redis.io` is frequently unreachable from sandboxed environments; the GitHub API
is the practical primary source. Re-check before repeating any "Redis cannot X"
claim in a review — this file has a shelf life of about six months.
