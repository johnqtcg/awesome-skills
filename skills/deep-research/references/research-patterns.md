# Programmer-Specific Research Patterns

Reference patterns for technical research scenarios commonly encountered by software engineers.

## 1. Error Debugging Research

When researching error messages or unexpected behavior:

**Query Strategy**:
```
# Exact error message search
"<exact error text>" <language/framework>

# Stack trace keyword extraction
"<key function name>" "<error type>" site:github.com OR site:stackoverflow.com

# Known-issue search
"<product>" "<error keyword>" issue OR bug after:2024
```

**Evidence Chain**: Error message → Root cause → Fix (verified in official docs or issue tracker)

**Pitfall**: AI may suggest fixes for similar-but-different errors. Always verify the error message matches exactly.

## 2. Official Documentation Research

When researching API behavior, configuration, or specifications:

**Query Strategy**:
```
# Direct official docs
"<function/API name>" site:<official-docs-domain>

# Release notes for version-specific behavior
"<product> <version>" "release notes" OR changelog

# Migration guide
"<product>" "migration" OR "upgrade" "<old-version>" "<new-version>"
```

**Evidence Chain**: Official documentation → Version-specific behavior → Working code example

**Pitfall**: Documentation may lag behind actual implementation. Check both docs AND release notes for the specific version.

## 3. GitHub Code Search Patterns

When researching how others implement a pattern:

**Query Strategy**:
```
# GitHub code search (use site:github.com)
"<function signature>" language:go site:github.com

# Find real-world usage examples
"<import path>" "<function name>" filetype:go

# Find configuration examples
filename:<config-file> "<setting name>" site:github.com
```

**Evidence Chain**: Multiple repos using the pattern → Official documentation confirming it → Understanding of edge cases

## 4. Technology Comparison Research

When comparing frameworks, libraries, or architectural approaches:

**Subtopic Split** (required):
1. Architecture and design philosophy
2. Performance characteristics (with benchmarks)
3. Ecosystem maturity (community, tooling, documentation)
4. Operational complexity (deployment, monitoring, debugging)
5. Trade-offs and known limitations

**Query Strategy**:
```
# Independent benchmarks
"<tech-A>" vs "<tech-B>" benchmark "methodology" after:2024

# Migration experiences
"migrated from <tech-A> to <tech-B>" OR "switched from <tech-A>"

# Production experience reports
"<tech>" "in production" "lessons learned" OR "post-mortem"
```

**Evidence Chain**: Independent benchmarks → Production experience reports → Official documentation on limitations

**Pitfall**: Vendor-sponsored benchmarks are biased. Always check methodology disclosure.

## 5. Performance Benchmark Research

When researching performance claims or conducting performance analysis:

**Query Strategy**:
```
# Find benchmarks with methodology
"<product>" benchmark results "test environment" OR "hardware" after:2024

# TechEmpower, Database benchmarks, etc.
"<product>" "techempower" OR "sysbench" OR "pgbench" OR "wrk" OR "k6"

# Regression or scalability data
"<product>" "scalability" OR "throughput" "concurrent" OR "connections"
```

**Evidence Chain**: Benchmark with disclosed methodology → Independent reproduction → Version and hardware specification

**Verification Mandatory**: Never report a performance number without the benchmark methodology and environment.

## 6. RFC and Technical Standards Research

When researching protocols, standards, or specifications:

**Query Strategy**:
```
# Direct RFC
"RFC <number>" OR rfc<number> site:rfc-editor.org OR site:datatracker.ietf.org

# Find the relevant RFC for a concept
"<protocol concept>" RFC site:rfc-editor.org

# Implementation conformance
"<product>" "RFC <number>" "compliance" OR "conformance"
```

**Evidence Chain**: RFC/specification text → Reference implementation → Known deviations

## 7. Security Research

When researching security practices, vulnerabilities, or compliance:

**Query Strategy**:
```
# CVE search
"CVE-<year>-<number>" site:nvd.nist.gov OR site:cve.mitre.org

# Security advisory
"<product>" "security advisory" OR "vulnerability" after:2024

# Best practices
"<technology>" "security" "best practices" site:owasp.org OR site:<vendor>.com
```

**Evidence Chain**: Official CVE/advisory → Vendor patch/fix → Independent security analysis

**Critical**: Never rely on blog posts alone for security recommendations. Always trace to official advisories.

## 8. Codebase Research Patterns

When combining internal codebase analysis with external research:

**Workflow**:
1. Use `search-codebase` to identify internal patterns
2. Formulate external queries based on patterns found
3. Cross-reference internal implementation with external best practices
4. Report deviations with evidence

**Query Strategy**:
```bash
# Internal patterns
python3 scripts/deep_research.py search-codebase \
  --pattern "error handling" --root /path/to/repo --glob "*.go"

# Then external validation
python3 scripts/deep_research.py retrieve \
  --query "Go error handling best practices 2024" \
  --query "Go error wrapping vs sentinel errors"
```

## 9. AI Tool Selection for Deep Research

Different AI tools have distinct strengths for research:

| Research Need | Primary Tool | Fallback | Why |
|--------------|-------------|----------|-----|
| Source-backed facts with citations | Perplexity | ChatGPT (web) | Perplexity attaches source links to every claim |
| Deep technical analysis | Claude / ChatGPT Deep Research | Each other | Strong reasoning + comprehensive source coverage |
| Broadest source coverage | Gemini Deep Research | ChatGPT | Google search index is the widest |
| Real-time social/community signals | Grok | Perplexity | X platform data access |
| Chinese-language research | Gemini / Baidu | Perplexity | Better Chinese content coverage |
| Private document analysis | NotebookLM / Claude | ChatGPT | Upload-based Q&A without hallucination risk |

**Best Practice**: For important research, run Deep Research on 2 different tools and compare conclusions. Differences highlight the key decision points.

## Quick Reference: Query Syntax

| Operator | Function | Example |
|----------|----------|---------|
| `""` | Exact phrase match | `"concurrent map writes"` |
| `site:` | Restrict to domain | `site:go.dev context.WithCancel` |
| `filetype:` | Specific file type | `filetype:pdf "system design"` |
| `intitle:` | Word must be in title | `intitle:benchmark Go HTTP` |
| `-keyword` | Exclude results | `Go context -tutorial -beginner` |
| `OR` | Either term matches | `gRPC OR "connect-go"` |
| `*` | Wildcard placeholder | `"Go * pattern" concurrency` |
| `after:YYYY` | Published after date | `Kafka performance after:2024` |
| `before:YYYY` | Published before date | `before:2020` for historical context |
| `related:` | Find similar sites | `related:kubernetes.io` |
| `inurl:` | URL must contain | `inurl:benchmark "Go HTTP"` |
