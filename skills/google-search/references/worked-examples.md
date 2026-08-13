# Worked Examples

## Example 1: Single-round factual search (Quick mode)

User request: *"Go 语言里 sync.Pool 的对象会不会被 GC 回收？"*

**Gates**: Scope = Knowledge (language internals), Goal = Know. No ambiguity. Evidence chain = Single factual claim → 1 official source → target High. Language = English-first (Go docs). Source path = official docs. Mode = Quick. Budget = 2 queries.

**Queries**:
- Precision: `sync.Pool GC behavior site:go.dev`
- Primary: `Go sync.Pool garbage collection`

**Result**: `poolCleanup` runs during GC. Since Go 1.13 a victim cache holds the previous cycle's
objects, so an entry survives one GC and is collected on the next one if nobody retrieved it.
Page opened: https://go.dev/src/sync/pool.go

**Output Contract**:

| # | Field | Value |
|---|-------|-------|
| 1 | Execution mode | Quick |
| 2 | Degradation level | Full |
| 3 | Conclusion | Yes, `sync.Pool` objects are collected by GC. Since Go 1.13, Pool uses a victim cache — objects survive one GC cycle, then are fully collected if not retrieved. |
| 7 | Key numbers | Victim cache survives 1 GC cycle (`High`, `Official`) |
| 8 | Reusable queries | `sync.Pool GC behavior site:go.dev`, `Go sync.Pool garbage collection` |

A `Full` verdict has to name the page it rests on. "go.dev says so" is not traceable — the URL is
what lets the user check the claim, and it is the difference between an opened source and a search
snippet.

## Example 2: Multi-round search where the official chain cannot be completed (Standard mode)

User request: *"Go 微服务项目里，MySQL 连接池配置多大合适？"*

**Gates**: Scope = Knowledge (production config), Goal = Complete a task. No critical ambiguity. Evidence chain = Best practice → 1 official basis + 1 practitioner report → target Medium. Language = Both (English for vendor docs, Chinese for production experience). Source path = Go stdlib reference and MySQL server docs first, community second. Mode = Standard. Budget = 5 executed queries.

**Round 1** (3 queries):
- `SetMaxOpenConns SetMaxIdleConns site:pkg.go.dev`
- `max_connections wait_timeout site:dev.mysql.com`
- `Go MySQL 连接池 MaxOpenConns 生产环境 配置 site:zhihu.com`

**Round 2** (1 query — reformulate to look for measured, not asserted, numbers):
- `Go sql.DB SetMaxOpenConns 压测 OR 基准 连接池 上限 site:juejin.cn`

**Result — separated by what each source actually establishes**:

*Established by official sources.* `database/sql` documents the knob semantics: `MaxOpenConns`
defaults to 0, meaning unlimited; `MaxIdleConns` defaults to 2 and is silently reduced to match
`MaxOpenConns` whenever that is lower; `ConnMaxLifetime` of 0 means connections are never retired
by age. MySQL's `max_connections` is a **server-wide** ceiling shared by every client, so the sum
of all pools across all instances has to fit under it, and the server drops idle connections after
`wait_timeout` without the client noticing.

*Not established by any source found.* An official sizing number or formula. The vendors document
what the knobs do, not what to set them to. Community posts circulate
`MaxOpenConns = QPS × avg_query_seconds × 1.5` — Little's Law with a 1.5 headroom factor. The one
post found states it without hardware, workload, version, or measurement, and MySQL's
`max_connections` page says nothing about client-side pool sizing, so it does not corroborate the
formula. Treat it as the first candidate value for a load test, not as an answer.

**Output Contract**:

| # | Field | Value |
|---|-------|-------|
| 1 | Execution mode | Standard |
| 2 | Degradation level | **Partial** — official basis covers knob semantics only; no official sizing guidance exists |
| 3 | Conclusion | Raise `MaxIdleConns` to match `MaxOpenConns` for a steady-QPS service, because the default of 2 closes every further returned connection and forces reconnect churn. Keep `ConnMaxLifetime` below MySQL `wait_timeout`. Size `MaxOpenConns` by load test; Little's Law (`QPS × avg_query_seconds`, plus headroom) supplies the first value to test, not the value to ship. |
| 4 | Evidence chain status | official basis (knob semantics) ✅ · practitioner report (sizing) — single source, no methodology · official sizing guidance — does not exist, chain cannot be completed |
| 5 | Key evidence | `pkg.go.dev/database/sql` (documented defaults and clamping behaviour) · `dev.mysql.com` (`max_connections` is server-wide, `wait_timeout` closes idle connections) · one Juejin post (the formula, methodology not disclosed) |
| 6 | Source assessment | Knob semantics: official, no conflict, directly answers. Sizing: one practitioner post, not independently cross-checked, no disclosed methodology — reported as an attributed claim rather than a fact. The official pages found are about a different question than the one asked. |
| 7 | Key numbers | `MaxIdleConns` default = 2 (`High`, `Official`) · `MaxOpenConns` default = 0 / unlimited (`High`, `Official`) · headroom factor 1.5 (`Low`, `Practitioner report`) |
| 8 | Reusable queries | `SetMaxOpenConns SetMaxIdleConns site:pkg.go.dev` · `max_connections wait_timeout site:dev.mysql.com` · `Go MySQL 连接池 MaxOpenConns 生产环境 配置 site:zhihu.com` · `Go sql.DB SetMaxOpenConns 压测 OR 基准 连接池 上限 site:juejin.cn` · `"database/sql" pool sizing benchmark methodology after:2025-01-01` (not run) |

| Gate | Result |
|------|--------|
| 1. Scope | Knowledge (production config), Complete a task |
| 2. Ambiguity | No critical ambiguity |
| 3. Evidence | Best practice → 1 official + 1 practitioner, target Medium |
| 4. Language | Both (EN vendor docs, CN production experience) |
| 5. Source Path | Go stdlib + MySQL server docs, then community |
| 6. Mode | Standard |
| 7. Budget | 4/5 executed queries |
| 8. Integrity | All 4 queries executed; pkg.go.dev, dev.mysql.com and the Juejin page opened; the Zhihu result was a repost of the same formula and is not counted as independent |

**Why this example degrades to Partial.** The tempting move is to pair a real official page with a
blog number and call the chain complete. It is not complete: the official page answers "what does
this knob do", while the question asked "what value should it hold". An official source about an
adjacent question is not an official basis for this claim. Naming the missing link, labeling the
formula `Practitioner report` / `Low`, and pointing at a load test is the honest output — and it is
more useful than a false `Full`.
