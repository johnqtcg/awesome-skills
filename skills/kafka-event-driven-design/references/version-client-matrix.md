# Kafka Version & Client Library Matrix

**Never give a single configuration template.** The same property name means
different things — or does not exist — depending on the broker version and the
client library. Establish both before recommending any config.

Every value below is cited to the source that defines it. Where this file and a
vendor blog post disagree, this file's source wins.

**Contents** — §2 and §3 are the ones that decide a producer verdict.

| § | Table | Answers |
|---|-------|---------|
| [1](#1-broker--protocol-feature-timeline) | Broker feature timeline | is this feature present on their broker at all |
| [2](#2-java-client-producer-defaults--the-30-break) | Java producer defaults | is a missing `acks` line safe here (3.0 flipped it) |
| [3](#3-client-library-defaults-differ-from-each-other) | Per-client defaults | Java / librdkafka / sarama / franz-go disagree |
| [4](#4-consumer-defaults-java-verified-on-43) | Consumer defaults | commit, session, poll interval baselines |
| [5](#5-kafka-4x-consumer-rebalance-protocol-kip-848) | KIP-848 protocol | which consumer configs stop existing under `group.protocol=consumer` |
| [6](#6-transactions--4x-changes) | Transactions | removed EOS APIs, fencing, `transaction.version` |
| [7](#7-what-to-record-in-gate-1) | Gate 1 record | the minimum you must establish before scoring |

---

## 1. Broker / Protocol Feature Timeline

| Feature | Available from | Notes |
|---------|---------------|-------|
| Idempotent producer | 0.11 | `enable.idempotence` |
| Transactions (EOS v1) | 0.11 | `transactional.id`, `initTransactions` |
| Static group membership | 2.3 | `group.instance.id` (KIP-345) |
| Cooperative (incremental) rebalance | 2.4 | `CooperativeStickyAssignor` (KIP-429) |
| KRaft GA (ZooKeeper-free) | 3.3 | ZooKeeper mode **removed** in 4.0 |
| Next-gen consumer rebalance protocol | 3.7 Early Access, **4.0 GA** | KIP-848 |
| Transactions Server Side Defense (txn v2) | **4.0** | KIP-890 |

Latest release at time of writing: **4.3.1**. Kafka 4.x has no ZooKeeper mode at
all — a "2.x cluster on ZooKeeper" and a "4.x KRaft cluster" are different
operational products, not different patch levels. **3.9 is the last bridge
release**: a ZooKeeper cluster must migrate to KRaft on 3.9 before it can go to
4.x, so "upgrade us to 4.x" from a 2.x/3.x ZK cluster is a two-step programme,
not a version bump. Say so if a review touches it.

**Gate rule**: if the user says "Kafka" without a version, ask. Do not assume.
If they cannot answer, state the assumption explicitly in §9.9 and give the
config for **both** the pre-3.0 and post-3.0 default regimes — they differ on
the single most safety-relevant property (`acks`).

---

## 2. Java Client Producer Defaults — The 3.0 Break

Source: `clients/src/main/java/org/apache/kafka/clients/producer/ProducerConfig.java`
on branches `2.8`, `3.0`, `4.3`.

| Property | ≤ 2.8 default | ≥ 3.0 default (unchanged through 4.3) |
|----------|--------------|--------------------------------------|
| `acks` | `1` | **`all`** |
| `enable.idempotence` | `false` | **`true`** |
| `retries` | `Integer.MAX_VALUE` | `Integer.MAX_VALUE` |
| `max.in.flight.requests.per.connection` | 5 | 5 |
| `delivery.timeout.ms` | 120000 | 120000 |

**Consequence for review:** on a Kafka ≥ 3.0 Java client, "no `acks` line in the
config" means `acks=all`, not `acks=1`. Flagging an *absent* `acks` setting as a
data-loss defect is a false positive on modern Java clients and a true positive
on 2.x. **Read the version before scoring this item.** An explicit
`acks=1`/`acks=0` is a finding on any version.

### 2.1 max.in.flight with idempotence — the "must be 1" myth

`ProducerConfig` states: enabling idempotence requires
`max.in.flight.requests.per.connection` **≤ 5**, "with message ordering
preserved for any allowable value". The broker retains at most 5 batches per
producer, which is where the 5 comes from.

So on the Java client, `max.in.flight=5` + `enable.idempotence=true` **preserves
ordering**. Forcing it to 1 costs throughput and buys nothing. The "set it to 1"
advice is either pre-0.11 folklore or a sarama-specific rule (see §3).

Without idempotence, `max.in.flight > 1` + retries **can** reorder — that part
is real, and is why `enable.idempotence=false` is the actual defect to flag.

### 2.2 Default partitioner — null key is not round-robin

With `partitioner.class` unset (the default), the built-in logic is:

1. key present → partition chosen by hash of the key;
2. no key → **a sticky partition that changes when at least `batch.size` bytes
   have been produced to it**.

Null-key records therefore arrive in *runs* on one partition, not one-per-partition
round-robin. `RoundRobinPartitioner` is an opt-in class you must name explicitly,
and it carries a known uneven-distribution issue (KAFKA-9965).

`partitioner.ignore.keys` (default `false`) makes the producer ignore keys even
when present — a silent ordering killer if set carelessly.

---

## 3. Client Library Defaults Differ From Each Other

The client library matters as much as the broker version. Verified from each
project's own source.

| | **Java** (kafka-clients 3.0+) | **librdkafka** (confluent-kafka-go/python/.NET) | **IBM/sarama** (Go) | **twmb/franz-go** (Go) |
|---|---|---|---|---|
| `acks` default | `all` | `-1` (= all) | **`WaitForLocal` (= acks=1)** | `AllISRAcks()` (= all) |
| idempotence default | **`true`** | `false` | `false` | **`true`** (opt out with `DisableIdempotentWrite()`) |
| in-flight limit when idempotent | ≤ 5, ordering preserved | auto-set to 5 | **must equal 1** | 5 (the `maxProduceInflight: 1` default applies only when idempotency is disabled) |
| null-key placement | sticky per `batch.size` | sticky per `sticky.partitioning.linger.ms` (default 10 ms; `0` = random) | **random** (hash partitioner falls back to random) | sticky |
| enabling idempotence also forces | — | `retries=INT32_MAX`, `acks=all`, `queuing.strategy=fifo` | requires `Retry.Max ≥ 1`, `RequiredAcks=WaitForAll`, `Net.MaxOpenRequests=1` — else `NewConfig` errors | rejects a config with idempotency and non-`all` acks |

Sources: `ProducerConfig.java` (apache/kafka 4.3); `CONFIGURATION.md`
(confluentinc/librdkafka); `config.go` + `partitioner.go` (IBM/sarama);
`pkg/kgo/config.go` (twmb/franz-go).

**Review implications:**

- **sarama**: `Producer.RequiredAcks` defaults to `WaitForLocal`. Silence *is* a
  real data-loss finding here. `Net.MaxOpenRequests = 1` alongside
  `Idempotent = true` is **correct and required** — sarama's `Validate()` returns
  a `ConfigurationError` otherwise. Do not "correct" it to 5.
- **librdkafka**: `acks` is already `all`, but idempotence is **off** by default —
  the opposite split from Java. Flag the idempotence, not the acks.
- **Java**: both are already safe by default; the finding is when someone has
  explicitly downgraded them.
- **franz-go**: safe on both counts by default — idempotency is opt-*out*, and
  the config is rejected outright if idempotency is combined with weaker acks.
  Here the finding is an explicit `DisableIdempotentWrite()`, and the fact that
  `maxProduceInflight` reads as `1` in the defaults is not a throughput bug: it
  is the non-idempotent path's limit and does not apply to the default config.
- **No client round-robins null keys by default.** "Null key → round-robin" is
  wrong on all four. The accurate statement is "null key → no per-key ordering,
  placement is batch-sticky or random depending on client".

---

## 4. Consumer Defaults (Java, verified on 4.3)

Source: `clients/src/main/java/org/apache/kafka/clients/consumer/ConsumerConfig.java`.

| Property | Default | Review note |
|----------|---------|-------------|
| `enable.auto.commit` | **`true`** | Still true in 4.3. At-least-once with correct semantics needs `false` + commit after processing. |
| `isolation.level` | **`read_uncommitted`** | A consumer reading a transactional topic sees **aborted** records unless you set `read_committed`. This is the most-missed half of "exactly-once". |
| `max.poll.interval.ms` | 300000 (5 min) | Exceeding it ejects the consumer → rebalance. |
| `partition.assignment.strategy` | `[RangeAssignor, CooperativeStickyAssignor]` | Range is first, so the effective default is **eager**, not cooperative. |
| `group.protocol` | `classic` | New protocol is opt-in on the client through 4.x. |

---

## 5. Kafka 4.x Consumer Rebalance Protocol (KIP-848)

Source: `docs/operations/consumer-rebalance-protocol.md` (apache/kafka 4.3).

- GA since 4.0; **enabled on the server automatically**, gated by the
  `group.version` feature flag.
- **Not enabled on the client by default.** Set `group.protocol=consumer`.
- Timeline per KIP-1274: 3.7 EA → 4.0 GA → **5.0 client default** → 6.0 classic
  removed from `KafkaConsumer`.

### 5.1 Configs that stop working when `group.protocol=consumer`

These are **no longer usable**:

- `heartbeat.interval.ms`
- `session.timeout.ms`
- `partition.assignment.strategy`
- `enforceRebalance(String)` / `enforceRebalance()`

Heartbeat and session timeout move to the **server**:
`group.consumer.heartbeat.interval.ms`, `group.consumer.session.timeout.ms`.

### 5.2 Assignors move server-side

`group.consumer.assignors` (broker config) lists available assignors; `uniform`
and `range` ship by default, `uniform` is the default choice. A client selects a
non-default one with `group.remote.assignor`.

| Classic client-side assignor | New server-side assignor |
|------------------------------|--------------------------|
| `RangeAssignor` | `range` |
| `CooperativeStickyAssignor` | `uniform` |
| `StickyAssignor` | `uniform` |
| `RoundRobinAssignor` | `uniform` |

**So**: recommending `partition.assignment.strategy=CooperativeStickyAssignor` is
correct advice for the classic protocol and **dead config** under
`group.protocol=consumer`. Say which protocol you mean.

### 5.3 Known limitations (4.3)

- Client-side (custom) assignors are **not supported** — a service with a custom
  `ConsumerPartitionAssignor` cannot move to the new protocol as-is (KAFKA-18327).
- Rack-aware assignment is not fully supported yet (KAFKA-19387).

Groups convert between `Classic` and `Consumer` automatically when empty; online
rolling upgrade works only if the classic group's assignor embeds no custom metadata.

---

## 6. Transactions — 4.x Changes

Source: `docs/operations/transaction-protocol.md` and `KafkaProducer.java` (4.3).

- **KIP-890 (txn v2)** is auto-enabled server-side from 4.0, gated by the
  `transaction.version` feature flag (`transaction.version=2`). The producer
  epoch is bumped on **every** transaction, so a zombie producer cannot bleed
  writes into the next transaction. Clients upgrade dynamically on reconnect;
  a producer never upgrades mid-transaction.
- Downgrade is safe and symmetric.
- Latency accounting shifts: the old 20 ms client-side `CONCURRENT_TRANSACTIONS`
  backoff is gone; the server retries internally, so **produce latency rises**
  while end-to-end transaction latency does not. Tune with
  `add.partitions.to.txn.retry.backoff.ms` / `.max.ms`. Do not open an incident
  over that produce-latency shift after a 4.0 upgrade.

### 6.1 Removed API — code that no longer compiles

`sendOffsetsToTransaction(Map<TopicPartition, OffsetAndMetadata>, String consumerGroupId)`
was deprecated by KIP-447 and **is gone in 4.x**. The only overload in 4.3 is:

```java
producer.sendOffsetsToTransaction(offsets, consumer.groupMetadata());
```

The `ConsumerGroupMetadata` form is what enables generation-based zombie fencing.
Any snippet still passing a bare group-id string is pre-3.0 code.

---

## 7. What to Record in Gate 1

Minimum to give a defensible config recommendation:

| Field | Why |
|-------|-----|
| Broker version (major.minor) | Decides defaults, KRaft, KIP-848/890 availability |
| Client library **and version** | Decides `acks`/idempotence defaults and in-flight rules |
| `group.protocol` (classic / consumer) | Decides whether assignor + timeout configs exist |
| `transaction.version` (if EOS) | Decides fencing semantics |

If any are unknown, say so in §9.9 and scope the recommendation: *"assuming
kafka-clients ≥ 3.0, where `acks` already defaults to `all`…"*.
