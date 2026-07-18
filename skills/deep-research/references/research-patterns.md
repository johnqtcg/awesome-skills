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

Choose the research kind before collecting evidence.

- `codebase`: answer only from code, commits, and actual test runs; do not retrieve web sources.
- `hybrid`: inspect the repository first, then collect only the external evidence needed for comparison or recommendation.

**Repository evidence**:

The `search-codebase` helper uses ripgrep and emits structured matches.

```bash
python3 scripts/deep_research.py search-codebase \
  --pattern "error handling" \
  --root /path/to/repo \
  --glob "*.go" \
  --output /tmp/code_evidence.json
```

Use the emitted `code-*` and `commit-head` IDs in findings. Inspect each
record's `snapshot`: dirty or untracked bytes are deliberately labeled
`working-tree-unpinned`; never rewrite that label to the current HEAD.

Run a focused test once through the host's normal permission path, then import
the versioned receipt:

```bash
python3 scripts/deep_research.py snapshot-codebase \
  --root /path/to/repo \
  --output /tmp/repository_snapshot_before.json

go test -run TestAuth ./internal/auth

python3 scripts/deep_research.py snapshot-codebase \
  --root /path/to/repo \
  --output /tmp/repository_snapshot_after.json

python3 scripts/deep_research.py import-test-receipt \
  --receipt /tmp/host_test_receipt.json \
  --code-evidence /tmp/code_evidence.json \
  --output /tmp/code_and_test_evidence.json
```

The snapshots are read-only identity metadata, not test proof. For High they
must be clean and unchanged. One receipt must name the framework selector,
every cited code path, the stable finding and complete code-ID set in
`covers`, matching commit/tree and dirty state, plus an approved relevance
rationale. Separate receipts cannot collectively satisfy this rule.
`validate` and `report` consume the receipt statically and do not execute it
again. A commit alone proves history, and exit code 0 alone proves only process
success, not claim coverage.

## 9. Tool Selection Principles

Choose tools based on the artifact required, availability, and access constraints:

| Required artifact | Capability |
|---|---|
| Search candidates | Current web search |
| Static page text | Direct content fetch |
| JavaScript-rendered text | Browser-capable extraction |
| Code fact | Repository search/read |
| Runtime behavior | Local test execution |
| Commit fact | Version-control inspection |

Record which capability ran and whether it produced the artifact. Do not publish an unsourced ranking of named AI research products or treat a tool-generated citation as proof that its page was read.

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
