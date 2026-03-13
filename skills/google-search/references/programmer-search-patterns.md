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

Search real production code, not tutorials. Use GitHub's search syntax in the GitHub search box or via Google with `site:github.com`.

### GitHub Native Search Syntax

- `language:go "sync.Pool"` — Go projects using sync.Pool
- `language:go "errgroup" stars:>100` — popular projects using errgroup
- `filename:go.mod "go-redis"` — projects depending on go-redis
- `path:Makefile "golangci-lint"` — projects with golangci-lint in Makefile
- `path:.github/workflows "go test"` — CI configs running Go tests
- `org:kubernetes language:go "context.WithTimeout"` — Kubernetes codebase usage

### Google + GitHub

- `site:github.com <library> <pattern>` — find repos using a specific pattern
- `site:github.com/issues "<error message>"` — find issue discussions
- `site:github.com/pull "<fix description>"` — find relevant PRs

### Tactics

1. Use `stars:>N` to filter for well-maintained projects
2. Use `language:` to avoid cross-language noise
3. Use `path:` to target specific file types (Makefile, Dockerfile, .github/workflows/)
4. Production code reveals real patterns — better than tutorials for understanding idiomatic usage

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

| Syntax | Effect | Example |
|--------|--------|---------|
| `"phrase"` | Exact match | `"fatal error: concurrent map writes"` |
| `intitle:` | Title must contain keyword | `intitle:性能优化 Go` |
| `allintitle:` | Title must contain all keywords | `allintitle:Redis 持久化 RDB` |
| `intext:` | Body must contain keyword | `intext:"连接池调优"` |
| `inurl:` | URL must contain keyword | `inurl:github Go context` |
| `site:` | Restrict to domain | `site:go.dev context.WithTimeout` |
| `filetype:` | Restrict to file format | `Go最佳实践 filetype:pdf` |
| `imagesize:WxH` | Restrict image dimensions | `wallpaper imagesize:3840x2160` |
| `-keyword` | Exclude results with keyword | `苹果 -水果 -食谱` |
| `-site:` | Exclude a domain | `Go教程 -site:csdn.net` |
| `OR` | Logical OR (must be uppercase) | `(Redis OR Memcached) 缓存方案` |
| `*` | Wildcard for unknown words | `"best * for Go"` |
| `before:YYYY-MM-DD` | Results before date | `before:2026-01-01` |
| `after:YYYY-MM-DD` | Results after date | `Go 1.24 after:2025-01-01` |
| `related:` | Find similar websites | `related:github.com` |
| `define:` | Quick definition lookup | `define:idempotent` |

### Combination Examples

- Official docs on time-limited topic: `Go context 最佳实践 site:go.dev after:2024-01-01`
- Exclude noise, target community: `Redis集群 踩坑 site:zhihu.com -广告 -培训`
- Error in specific project: `"connection reset by peer" site:github.com/go-redis`
- Multiple frameworks comparison: `(Gin OR Echo OR Fiber) benchmark Go after:2025-01-01`
