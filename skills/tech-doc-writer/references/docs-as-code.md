# Docs-as-Code Engineering Practices

Load this reference when the user asks about doc CI, PR templates, auto-generation, or when setting up documentation infrastructure for a new project.

---

## Document CI Checks

Treat documentation with the same rigor as code. Add these checks to the CI pipeline:

| Check | Tool | Purpose |
|-------|------|---------|
| Markdown format | markdownlint | Heading levels, list indentation, blank lines |
| Spelling | cspell / aspell | Catch typos in mixed Chinese/English text |
| Link validity | markdown-link-check | Detect dead links and 404s |
| Code block compilation | `go vet` / `go build` | Ensure Go code examples actually compile |
| Terminology consistency | Vale (custom rules) | Detect synonym mixing (e.g. "集群" vs "cluster") |

### Implementation Priority

1. **markdownlint** — catches 80% of formatting issues with near-zero setup.
2. **markdown-link-check** — dead links are the fastest path to reader distrust.
3. **cspell** — add a `.cspell.json` with custom dictionary for domain terms.
4. **Vale** — higher setup cost but catches terminology drift.
5. **Code block compilation** — extract blocks into `_example_test.go` files.

### Example GitHub Actions Workflow

```yaml
name: docs-ci
on:
  pull_request:
    paths: ['docs/**', '**/*.md']

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: DavidAnson/markdownlint-cli2-action@v18
        with:
          globs: '**/*.md'
      - name: Check links
        uses: gaurav-nelson/github-action-markdown-link-check@v1
        with:
          folder-path: 'docs'
```

---

## PR Template — Doc Impact Section

Add to the team's PR template to prevent documentation drift:

```markdown
### Doc Impact
- [ ] This change does NOT affect any existing documentation
- [ ] Updated related docs (link: ___)
- [ ] Code examples in docs verified runnable
- [ ] New API/config items added to reference docs
```

**Why this matters**: Code and docs are merged in the same PR, so documentation stays in sync by default. Retrofitting docs after a release almost never happens.

---

## Auto-Generate Where Possible

| Source | Tool | Output |
|--------|------|--------|
| Go package comments | `godoc` / `pkgsite` | API documentation |
| OpenAPI annotations | swag / oapi-codegen | REST API documentation |
| Proto files | protoc-gen-doc | gRPC interface docs |
| Database DDL | tbls / schemaspy | Data dictionary |

**Principle**: what can be generated from code should never be hand-written. Hand-written docs inevitably drift from code; auto-generated docs stay in sync with each build.

### When to Auto-Generate vs. Hand-Write

| Content | Auto-Generate | Hand-Write |
|---------|--------------|------------|
| API parameter tables | ✓ | |
| Error code reference | ✓ | |
| Data dictionary / schema | ✓ | |
| Architecture rationale | | ✓ |
| Runbook procedures | | ✓ |
| Concept explanations | | ✓ |
| Getting-started guides | | ✓ |

Auto-generation handles "what exists"; hand-writing handles "why" and "how to use it well."

---

## Document Review vs. Code Review

| Dimension | Code Review | Document Review |
|-----------|-------------|-----------------|
| Primary focus | Correctness, performance, security | Understandability, executability, completeness |
| Reviewer perspective | "Is the implementation correct?" | "Can the reader complete the task independently?" |
| Common blind spots | Edge cases | Missing prerequisites, undefined terms |
| Validation method | Run tests | Have someone unfamiliar follow the doc |

**Practical tip**: the best document reviewer is someone who does NOT know the system. If they can follow the doc successfully, the doc is good. If they get stuck, the doc needs work.

---

## Version Compatibility Matrix

For critical documents, include a compatibility table to prevent version misuse:

| Component | Version | Status | Notes |
|-----------|---------|--------|-------|
| Go | 1.24.x | Supported | Current verified version |
| MySQL | 8.0.x | Supported | Parameter semantics verified |
| Redis | 7.x | Supported | Command examples based on this |
| MySQL | 5.7.x | Limited | See legacy doc |

Place at the top of the document (after metadata) or in an Appendix. Update when any component version changes.
