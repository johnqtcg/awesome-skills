# Hallucination Awareness and Verification Protocol

## AI Hallucination Types

Understand these failure modes to detect them during research:

| Type | Description | Example | Detection Method |
|------|-------------|---------|-----------------|
| **Fabricated Citation** | AI invents a URL, paper title, or author | "According to Smith et al. (2024)..." with no such paper | Verify URL is reachable; search for the actual paper |
| **Stale Information** | AI uses outdated facts as if current | "Go 1.18 is the latest version" (when 1.24 is current) | Check official release pages; add `after:YYYY` to searches |
| **Confidence Inflation** | AI presents uncertain claims as definitive | "Redis is always faster than PostgreSQL for caching" | Look for qualifiers; check if benchmarks support the absolute claim |
| **Phantom Feature** | AI describes an API/function that doesn't exist | "Use `sync.OrderedMap` in Go" (no such type) | Verify against official API docs |
| **Cherry-Picked Evidence** | AI selects supporting evidence while ignoring contradictions | "Kubernetes adoption is declining" (citing one negative article, ignoring growth data) | Search for counter-arguments explicitly |
| **Conflation** | AI merges distinct concepts or products | Confusing Apache Kafka with Confluent Platform | Verify the exact product/version being discussed |

## Cross-Validation Protocol

### Mandatory for High-Confidence Findings

Every finding marked `High` confidence must pass:

1. **Primary Source Check** — Can the claim be traced to an official document, specification, or primary dataset?
2. **Independent Domain Check** — Is the claim supported by sources from ≥2 independent domains?
3. **Recency Check** — Is the information current? Add `after:YYYY-MM` to verification searches for time-sensitive claims
4. **Content Extraction Check** — Was the claim verified from extracted page content, not just search snippets?

### Recommended for Medium-Confidence Findings

1. Cross-reference with at least 1 independent source
2. Check if the claim is contested in forums or issue trackers
3. Note any version/time dependency

### What To Verify — Priority Matrix

| Risk Level | Information Type | Verification Action |
|-----------|-----------------|-------------------|
| Critical | API signatures, function parameters, config syntax | Read official documentation directly |
| Critical | Performance numbers, benchmark results | Find the original benchmark report with methodology |
| Critical | Security configurations, encryption standards | Check official security advisories |
| High | Version compatibility, migration paths | Check release notes and changelogs |
| High | License terms, pricing, quotas | Go to the vendor's official page |
| Medium | Best practice recommendations | Verify with 2+ independent practitioner sources |
| Medium | Architecture comparisons | Check for recency and disclosed methodology |
| Low | General conceptual explanations | Trust if consistent across sources; flag if contradicted |

## Verification Query Patterns

When a finding needs verification, construct targeted queries:

```
# Verify an API claim
"<exact function name>" site:official-docs-domain.com

# Verify a performance claim
"<product>" benchmark "methodology" after:2024

# Verify a version-specific claim
"<product> <version>" changelog OR "release notes"

# Check for contradicting evidence
"<claim subject>" "however" OR "but" OR "actually" OR "myth"
```

## Numeric Claim Labels

When reporting numeric claims (statistics, benchmarks, adoption rates):

| Confidence | Format | Example |
|-----------|--------|---------|
| Verified primary source | **Value [source]** | 1.2M req/s [TechEmpower Round 23] |
| Cross-checked secondary | Value ± range [sources] | ~850K–1.1M req/s [source1, source2] |
| Single unverified source | "~Value (unverified, single source)" | ~70% adoption (unverified, single survey) |
| AI estimation, no source | Mark as inference, not finding | Not used — omit or flag as gap |

## Tool-Specific Verification Guidance

### When To Recommend Alternative Tools

During the research process, certain findings may benefit from verification with specialized tools:

| Situation | Recommended Tool | Why |
|-----------|-----------------|-----|
| Claim requires real-time data | Perplexity Pro Search | Live web search with citations |
| Need to verify Chinese-language claims | Baidu/WeChat/Zhihu search | Google may not index walled-garden content |
| Need to verify code behavior | Local execution (`go test`, `python -c`) | Running code is the ultimate verification |
| Academic paper claims | Google Scholar, arxiv.org | Dedicated academic indexes |
| GitHub-specific data (stars, issues, releases) | GitHub API / `gh` CLI | Authoritative source for repo metadata |

### Insufficient Evidence Protocol

When the evidence chain cannot be satisfied:
1. Do not fabricate or stretch existing sources
2. State explicitly what evidence is missing and why
3. Lower confidence to `Low` or remove the finding entirely
4. Suggest alternative research approaches in the Gaps section

## Source Tier Ranking

Default credibility order for research sources:

| Tier | Source Types | Notes |
|------|-------------|-------|
| T1 (Authoritative) | Official docs, RFCs, specifications, `.gov`, `.edu`, peer-reviewed papers | Highest weight |
| T2 (Authoritative-adjacent) | Release notes, changelogs, official blogs, conference talks by maintainers | High weight with recency check |
| T3 (Expert) | Independent benchmarks with methodology, reputable tech publications | Medium-high weight |
| T4 (Community) | Stack Overflow (high-vote), HN discussions, experienced practitioners' blogs | Medium weight, verify claims |
| T5 (Supplementary) | Medium posts, dev.to, tutorial sites, vendor marketing | Low weight, never sole source for findings |
