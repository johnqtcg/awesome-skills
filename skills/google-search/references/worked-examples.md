# Worked Examples

## Example 1: Single-round factual search (Quick mode)

User request: *"Go 语言里 sync.Pool 的对象会不会被 GC 回收？"*

**Gates**: Scope = Knowledge (language internals), Goal = Know. No ambiguity. Evidence chain = Single factual claim → 1 official source → target High. Language = English-first (Go docs). Source path = official docs. Mode = Quick. Budget = 2 queries.

**Queries**:
- Precision: `sync.Pool GC behavior site:go.dev`
- Primary: `Go sync.Pool garbage collection`

**Result**: go.dev source code shows `poolCleanup` called during GC. Since Go 1.13, victim cache mechanism: objects survive 1 GC in victim slot, collected on 2nd GC if unused.

**Output Contract**:

| # | Field | Value |
|---|-------|-------|
| 1 | Execution mode | Quick |
| 2 | Degradation level | Full |
| 3 | Conclusion | Yes, `sync.Pool` objects are collected by GC. Since Go 1.13, Pool uses a victim cache — objects survive one GC cycle, then are fully collected if not retrieved. |
| 7 | Key numbers | Victim cache survives 1 GC cycle (`High`, `Official`) |
| 8 | Reusable queries | `sync.Pool GC behavior site:go.dev`, `Go sync.Pool garbage collection` |

## Example 2: Multi-round search with Chinese sources (Standard mode)

User request: *"Go 微服务项目里，MySQL 连接池配置多大合适？"*

**Gates**: Scope = Knowledge (production config), Goal = Know + Do. No critical ambiguity. Evidence chain = Best practice → 1 official basis + 1 practitioner report → target Medium-High. Language = Both (English for vendor docs, Chinese for production experience). Source path = MySQL docs + community. Mode = Standard. Budget = 5 queries.

**Round 1** (3 queries):
- `MySQL connection pool size recommendation site:dev.mysql.com`
- `Go MySQL connection pool MaxOpenConns production tuning`
- `Go MySQL 连接池 MaxOpenConns 生产环境 配置 site:zhihu.com`

**Round 2** (1 query — reformulate for Chinese pitfalls):
- `Go sql.DB SetMaxOpenConns "生产" OR "线上" 配置建议 site:juejin.cn`

**Result**: Formula from Juejin: `MaxOpenConns = QPS × avg_query_seconds × 1.5`. Cross-checked with Zhihu production case (500 QPS → MaxOpenConns=50). MySQL docs confirm server-side `max_connections`. 4 queries used (within budget).

**Output Contract**:

| # | Field | Value |
|---|-------|-------|
| 1 | Execution mode | Standard |
| 2 | Degradation level | Full |
| 3 | Conclusion | Starting config: `MaxOpenConns = QPS × avg_query_seconds × 1.5`, `MaxIdleConns = MaxOpenConns / 2`, `ConnMaxLifetime < MySQL wait_timeout`. |
| 4 | Evidence chain status | 1 official (MySQL docs) ✅ + 1 practitioner (Juejin + Zhihu) ✅ |
| 5 | Key evidence | MySQL docs (max_connections), Juejin formula, Zhihu production case |
| 6 | Source assessment | Official + practitioner, consistent, Medium-High confidence |
| 7 | Key numbers | MaxOpenConns formula (`Medium-High`, `Mixed official + practitioner`) |
| 8 | Reusable queries | 4 queries listed above |

| Gate | Result |
|------|--------|
| 1. Scope | Knowledge (production config), Know + Do |
| 2. Ambiguity | No critical ambiguity |
| 3. Evidence | Best practice → 1 official + 1 practitioner |
| 4. Language | Both (EN vendor docs, CN production experience) |
| 5. Source Path | MySQL docs + community |
| 6. Mode | Standard |
| 7. Budget | 4/5 queries used |
| 8. Integrity | All queries executed, Juejin and Zhihu pages opened |
