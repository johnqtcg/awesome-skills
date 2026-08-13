# Programmer Search Patterns

Use these patterns when the search category is "Programmer search" — error debugging, API docs, code examples, benchmarks, RFCs, or technical troubleshooting.

## Error Debugging

Copy the error message, strip personal paths and variable names, keep the generic error description and error codes.

### Patterns

- `"<exact error message>"` — full error, exact match
- `"<exact error message>" <language>` — add language to narrow scope
- `"<exact error message>" site:stackoverflow.com` — high-quality Q&A
- `"<exact error message>" site:github.com` — issue discussions and fix PRs
- `"<error code>" <library> <symptom>` — error code with context
- `"<error message>" "解决方案" OR "解决办法"` — Chinese troubleshooting articles

### Examples

- `"fatal error: concurrent map writes"` — Go concurrent map write
- `"connection refused" MySQL Go` — Go MySQL connection refused
- `"context deadline exceeded" gRPC` — gRPC timeout
- `"slice bounds out of range" Go` — Go slice bounds error

### Tactics

1. Search the full error first, then the shortest distinctive substring
2. Add runtime, framework, or OS when the error is too broad
3. Exclude low-quality domains: `-site:csdn.net` if results are flooded with reposts
4. For Go errors, also try: `"<error message>" site:go.dev` to find official guidance

## Official Documentation

Use `site:` to search within official docs directly — more accurate than third-party tutorials.

### Patterns

- `site:go.dev <package> <function>` — Go standard library
- `site:pkg.go.dev <package>` — Go third-party packages
- `site:redis.io <command>` — Redis commands and docs
- `site:dev.mysql.com <topic>` — MySQL official docs
- `site:kafka.apache.org <topic>` — Kafka official docs
- `site:kubernetes.io <resource> <operation>` — Kubernetes docs
- `site:docs.docker.com <topic>` — Docker docs
- `site:docs.github.com <feature>` — GitHub docs

### Tactics

1. Start with the official site — only go to community sources if official docs are insufficient
2. Add version numbers when behavior changed across releases
3. For Go: `site:go.dev/doc` for guides, `site:go.dev/ref` for specs, `site:go.dev/blog` for release announcements

## GitHub Code Search

Search real production code, not tutorials.

GitHub runs **two search engines with different qualifier sets**. Code search matches file
content and paths; repository search matches repo metadata. A qualifier from the wrong engine
does not error — it is reinterpreted as plain search text, so the query silently returns junk.

**Tag every GitHub query with the engine it targets**: `[github-code]` or `[github-repo]`
before the query, in the report and in your own notes. This is not decoration. Given
`language:go errgroup stars:>100` nobody can tell whether you meant a repository search (valid
— matches repo metadata mentioning errgroup) or a code search that will silently drop `stars:`
and return unrelated files. The tag is the only thing that makes the query checkable, by a
reviewer or by `scripts/lint_search_report.py`. Untagged Google queries need no tag.

### Code search qualifiers

The complete qualifier set for code search: `repo:`, `org:`, `user:`, `enterprise:`,
`language:`, `license:`, `path:`, `symbol:`, `content:`, `is:` (`archived` / `fork` /
`vendored` / `generated`), plus regex in `/slashes/` and the boolean operators `AND`, `OR`,
`NOT`. There is nothing else.

- `language:go "sync.Pool"` — Go files containing the string
- `language:go symbol:WithContext` — symbol **definitions** only, not call sites
- `path:go.mod "go-redis"` — projects depending on go-redis
- `path:/(^|\/)go\.mod$/ "go-redis"` — same, anchored so `vendor/foo/go.mod.bak` cannot match
- `path:.github/workflows "go test"` — CI configs running Go tests
- `org:kubernetes language:go "context.WithTimeout"` — one org's codebase
- `"fatal error" NOT path:__testing__` — exclude a directory
- `errgroup NOT is:fork` — skip forks of the same code

`path:` also accepts globs: `path:*.go`, `path:src/*.js`, `path:/src/**/*.js`. A leading `/`
anchors to the repo root; `*` does not cross `/`, `**` does.

### Qualifiers that do NOT work in code search

| Do not use | Why | Use instead |
|---|---|---|
| `filename:go.mod` | legacy qualifier, not in current code search | `path:go.mod`, or a regex to anchor the exact name |
| `stars:>100` | repository-search qualifier — not available in code search | shortlist repos first (below), then scope with `repo:` / `org:` |
| `extension:go` | legacy qualifier | `path:*.go` or `language:go` |

### Repository search qualifiers

A separate engine over repo metadata (name, description, README, topics) — this is where
`stars:` is valid.

- `language:go stars:>=500 errgroup` — popular Go repos whose metadata mentions errgroup
- `topic:kubernetes stars:100..1000` — by topic within a star band
- `language:go pushed:>2025-06-01` — still maintained

**"Popular projects using X" needs two steps**, because no single query filters by stars and
by file content at once:

1. Repository search: `language:go stars:>=1000 <domain keyword>` → shortlist
2. Code search scoped to that shortlist: `org:<org> language:go "<pattern>"`

### Google + GitHub

- `site:github.com <library> <pattern>` — repos referencing a pattern
- `site:github.com/<org>/<repo> "<error message>"` — discussions inside one repo
- `site:github.com/<org>/<repo> inurl:issues "<error message>"` — narrow to that repo's issues

`site:` matches a URL prefix, so `site:github.com/issues` matches only the signed-in issue
dashboard — never a repository's issues, which live at `github.com/<org>/<repo>/issues/<n>`.

### Tactics

1. Shortlist by `stars:` in repository search, then read code with `repo:` / `org:` scoping
2. Use `language:` to avoid cross-language noise
3. Use `path:` to target file types (`path:Makefile`, `path:Dockerfile`, `path:*.yaml`)
4. Use `symbol:` when you want the definition and `content:` when you want the mention
5. Production code reveals real patterns — better than tutorials for idiomatic usage

## Stack Overflow

High-quality Q&A, but noisy at volume. Use Google + `site:` for better filtering than SO's native search.

### Patterns

- `[go] <topic> site:stackoverflow.com` — Go-tagged questions
- `[mysql] <topic> site:stackoverflow.com` — MySQL-tagged questions
- `"<exact error>" site:stackoverflow.com` — error-specific Q&A
- `<topic> "accepted answer" site:stackoverflow.com` — prioritize accepted answers

### In Stack Overflow's Search Box

- `[go] is:answer score:10 <topic>` — high-score answers only
- `[go] is:question votes:5 <topic>` — well-upvoted questions

### Tactics

1. Prefer answers with code examples and explicit version numbers
2. Check answer dates — a 2018 Go answer may be obsolete
3. For Go-specific questions, also try `site:forum.golangbridge.org`

## RFC and Technical Standards

For protocol specifications, use authoritative standards bodies.

### Patterns

- `site:ietf.org RFC <number>` — IETF RFC lookup
- `"RFC <number>" <topic>` — RFC by number with topic context
- `site:ietf.org <protocol> specification` — find the relevant RFC
- `filetype:pdf RFC <number>` — download RFC as PDF
- `site:w3.org <web standard>` — W3C web standards
- `site:unicode.org <encoding topic>` — Unicode standards

### Examples

- `site:ietf.org RFC 9110 HTTP semantics` — HTTP/1.1 semantics
- `"RFC 6455" WebSocket` — WebSocket protocol
- `site:ietf.org TLS 1.3 specification` — TLS 1.3 standard

## Performance Benchmarks

For technical selection, performance data must be recent and sourced.

### Patterns

- `benchmark <technology A> vs <technology B> after:YYYY-MM-DD` — recent comparison
- `"TechEmpower" <framework> benchmark` — authoritative web framework benchmarks
- `<technology> benchmark filetype:pdf` — benchmark reports
- `<technology> 性能对比 实测 after:YYYY-MM-DD` — Chinese real-world benchmarks

### Examples

- `benchmark Go HTTP framework 2025 after:2025-01-01`
- `Redis vs Memcached benchmark after:2024-01-01`
- `"TechEmpower" Go framework benchmark`
- `Kafka RocketMQ 性能对比 实测 after:2024-01-01`

### Tactics

1. Always add `after:` — benchmark results from 2020 are irrelevant for 2026 decisions
2. Prefer benchmarks that disclose hardware specs, methodology, and version numbers
3. Cross-check with at least one independent benchmark source
4. For Go frameworks, TechEmpower is the gold standard for HTTP throughput comparisons

## Common Mistakes in Programmer Search

1. **Searching error messages without exact quotes** — `context deadline exceeded gRPC` returns noise; `"context deadline exceeded" gRPC` returns targeted discussions.
2. **Not constraining to official docs** when the answer is in stdlib — always try `site:go.dev` or `site:pkg.go.dev` before community sources.
3. **Using the full error text** when only the distinctive substring matters — strip variable names, paths, and timestamps before searching.
4. **Forgetting `after:`** for fast-moving libraries — a 2020 gRPC answer may be obsolete; add `after:2024-01-01` for current behavior.
5. **Searching GitHub issues without `site:github.com/<org>/<repo>`** — broad `site:github.com` returns too many unrelated repos.

## Quick-Reference: Google Search Syntax

Operators are graded by support level. Google documents only the first group; the rest are
community knowledge that Google may change or drop without notice — the `+` operator was
removed outright. Build the evidence chain on Tier A operators; treat Tier B as convenience and
Tier C as expendable.

### Tier A — documented in Google's own help page

| Syntax | Effect | Example |
|--------|--------|---------|
| `"phrase"` | Exact match | `"fatal error: concurrent map writes"` |
| `site:` | Restrict to domain | `site:go.dev context.WithTimeout` |
| `-keyword` | Exclude results with keyword | `苹果 -水果 -食谱` |
| `-site:` | Exclude a domain | `Go教程 -site:csdn.net` |
| `filetype:` | Restrict to file format | `Go最佳实践 filetype:pdf` |
| `before:YYYY-MM-DD` | Document last updated before date | `before:2026-01-01` |
| `after:YYYY-MM-DD` | Document last updated after date | `Go 1.24 after:2025-01-01` |

**`before:` / `after:` filter on when the document was last updated, not when the event
happened.** A 2019 tutorial re-published today passes `after:2026-01-01`; a correct 2024 spec
page that has not been touched since fails it. Use them to cut stale pages out of a noisy
result set — never as proof that a claim is current. To date the *claim*, read the date printed
on the page itself. Both `2026-01-01` and `2026/01/01` are accepted, as is a bare year.

### Tier B — undocumented but generally working

| Syntax | Effect | Example |
|--------|--------|---------|
| `OR` | Logical OR (must be uppercase) | `(Redis OR Memcached) 缓存方案` |
| `intitle:` | Title must contain keyword | `intitle:性能优化 Go` |
| `allintitle:` | Title must contain all keywords | `allintitle:Redis 持久化 RDB` |
| `intext:` | Body must contain keyword | `intext:"连接池调优"` |
| `inurl:` | URL must contain keyword | `inurl:issues site:github.com` |
| `*` | Wildcard for unknown words | `"best * for Go"` |

If a Tier B operator returns obviously unfiltered results, it is being ignored — fall back to a
quoted phrase plus `site:` rather than assuming the filter applied.

### Tier C — unreliable, verify before relying on it

| Syntax | Status |
|--------|--------|
| `related:` | Frequently returns nothing; do not build a source list on it |
| `define:` | Redirects into the dictionary panel, not a document search |
| `imagesize:WxH` | Image-search-only, and often overridden by the Tools size filter |
| `link:` | Removed by Google — always empty |
| `+keyword` | Removed by Google — use `"keyword"` |

### Combination Examples

- Official docs on time-limited topic: `Go context 最佳实践 site:go.dev after:2024-01-01`
- Exclude noise, target community: `Redis集群 踩坑 site:zhihu.com -广告 -培训`
- Error in specific project: `"connection reset by peer" site:github.com/go-redis`
- Multiple frameworks comparison: `(Gin OR Echo OR Fiber) benchmark Go after:2025-01-01`
