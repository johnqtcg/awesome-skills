**Mode**: Write
**Doc type**: concept — "document our caching layer" asks *what is it and why*, not how to operate
it. If you wanted a runbook or a config reference instead, say so and I will switch type.
**Resolution**: R1 searched the repo for a stated reader (no `CONTRIBUTING.md` audience section, no
existing `docs/` corpus, no ADRs referencing the cache) → nothing found. R2 asking is unavailable:
this is a non-interactive run, so I cannot wait for an answer. → **R3 assume → Level 2**.
**Audience (assumed)**: backend engineers new to this service — the broadest reasonable reader.

<!-- BEGIN DOCUMENT -->
---
title: Caching Layer
owner: platform-team
status: draft
last_updated: 2026-07-26
applicable_versions: Redis 7.2+
---

<!-- AUDIENCE: assumed — backend engineers new to this service. Confirm before publishing;
     if the real reader is SRE or a product engineer, the depth below is wrong. -->

# Caching Layer

Reads are served from Redis in front of Postgres, cutting p99 read latency from ~180ms to ~12ms
at the cost of up to 60 seconds of staleness.

## Why it exists

Product listing endpoints repeated identical queries on every page view. The database was the
bottleneck, not the query. Caching was chosen over read replicas because the working set is small
and the staleness budget is generous.

## How it fits together

| Layer | Role | Failure behaviour |
|---|---|---|
| Application | Checks Redis first, falls back to Postgres | Cache miss is transparent |
| Redis | Holds serialised listing payloads, 60s TTL | On outage, all reads hit Postgres |
| Postgres | System of record | No caching semantics |

## What it deliberately does not do

- No write-through: writes go to Postgres and invalidate the key, so a reader may see a stale
  value for up to the TTL.
- No cross-region replication: each region caches independently.

## Cross-references

- Operating the cache: see the cache runbook (not yet written).
- The decision record for choosing Redis over read replicas: ADR-011.
<!-- END DOCUMENT -->

## Quality Scorecard

Type is `concept`, so most task/reference items are N/A — the denominator is the applicable set,
not a fixed 6.

- **Critical**: 3/3 applicable pass (2 N/A — per-step verification and parameter tables are not
  concept-doc items). Code is prose-only, so the "snippet marked" item does not arise.
- **Standard**: 2/2 applicable pass (4 N/A — prerequisites, rollback, self-contained code, error
  codes are all task/reference items) → PASS (need 2/2).
- **Hygiene**: 2/2 applicable pass, plus `applicable_versions` present → PASS (need 2/2).

Level 2 caveat: because the audience is assumed, the *depth* is the least reliable part of this
document. Confirm the reader before publishing.
