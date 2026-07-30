# Docs-as-Code Engineering Practices

Load this reference when the user asks about doc CI, PR templates, auto-generation, or when setting up documentation infrastructure for a new project.

---

## Document CI Checks

Treat documentation with the same rigor as code. Add these checks to the CI pipeline:

| Check | Tool | Purpose |
|-------|------|---------|
| Scorecard floor + staleness | `scripts/lint_doc.py` | Metadata, table completeness, fences, Pangu spacing, and document age vs. review cadence |
| Markdown format | markdownlint | Heading levels, list indentation, blank lines |
| Spelling | cspell / aspell | Catch typos in mixed Chinese/English text |
| Link validity | markdown-link-check | Detect dead links and 404s |
| Code block compilation | `go vet` / `go build` | Ensure Go code examples actually compile |
| Terminology consistency | Vale (custom rules) | Detect synonym mixing (e.g. "集群" vs "cluster") |

### Implementation Priority

1. **`lint_doc.py`** — no install step, and it is the only check here that notices a document
   has gone stale. Run it over changed docs on every PR, and over the whole tree on a schedule
   (staleness is a function of the clock, so it surfaces with no commit to trigger it).
2. **markdownlint** — catches 80% of formatting issues with near-zero setup.
3. **markdown-link-check** — dead links are the fastest path to reader distrust.
4. **cspell** — add a `.cspell.json` with custom dictionary for domain terms.
5. **Vale** — higher setup cost but catches terminology drift.
6. **Code block compilation** — extract blocks into `_example_test.go` files.

### Adapting the Linter to Your Conventions (`.techdocrc.json`)

The linter's defaults encode *this skill's* conventions. Your repository's conventions outrank
them (SKILL.md Gate 1), so declare them once instead of arguing with the tool on every file.
Drop a `.techdocrc.json` beside your docs — the nearest one to the linted file wins, so a
`docs/` subtree may differ from the repository root.

```json
{
  "metadata": {
    "location": "footer",
    "required": ["title", "maintainer", "state", "updated"],
    "aliases": { "owner": ["maintainer"], "last_updated": ["updated"] },
    "status_field": "state",
    "status_values": ["wip", "published", "archived"],
    "date_field": "updated"
  },
  "staleness": { "max_age_days": 180, "grace_days": 14 },
  "title": { "require_h1_match": false },
  "tables": { "reference_required_columns": ["type", "description"] }
}
```

| Key | Use when |
|---|---|
| `metadata.location` | `footer` for page metadata at the end; `none` when in-document blocks are forbidden (both metadata and staleness checks then report as skipped rather than failing) |
| `metadata.aliases` | The repo already uses `maintainer:`/`author:`/`updated:` and renaming every doc is not worth it |
| `metadata.status_values` | A different lifecycle vocabulary |
| `staleness.*` | A different review rhythm, or `"enabled": false` for an archive |
| `title.require_h1_match` | A deliberate convention of long sidebar titles and short headings |
| `pangu.*` | English-only repos (`"enabled": false`), or a house style that tolerates loose spacing |
| `tables.reference_required_columns` | Your parameter tables genuinely need a different column set |

Verify the merge before trusting it — a typo in a section name is rejected rather than silently
ignored, but a typo in a *field* name is not:

```bash
python3 scripts/lint_doc.py docs/some-page.md --print-config
```

### Example GitHub Actions Workflow

> **Action versions in this example are illustrative, not current.** A skill that preaches
> anti-staleness must not ship pins that rot silently — this file previously carried
> `checkout@v4`, `markdownlint-cli2-action@v18`, and
> `gaurav-nelson/github-action-markdown-link-check@v1`, the last of which has since been
> **archived by its author**. Before adopting, resolve each `uses:` against its current
> release page and replace the `vN` below, then let Dependabot keep it current (config after
> the workflow). Treat any unverified pin as a finding in your own doc review.

```yaml
name: docs-ci
on:
  pull_request:
    paths: ['docs/**', '**/*.md']

# Least privilege: this job only needs to read the tree. Without an explicit block the job
# inherits the repository default, which is often write.
permissions:
  contents: read

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      # Pin to the current major of each action — verify before use, see note above.
      - uses: actions/checkout@vN

      - uses: DavidAnson/markdownlint-cli2-action@vN
        with:
          globs: '**/*.md'

      # Link checking: prefer a maintained checker. lychee is the common choice now that the
      # gaurav-nelson action is archived; confirm the current major on its releases page.
      - name: Check links
        uses: lycheeverse/lychee-action@vN
        with:
          args: --no-progress --verbose 'docs/**/*.md'
          fail: true
```

**Keep the pins fresh automatically** — `.github/dependabot.yml`:

```yaml
version: 2
updates:
  - package-ecosystem: github-actions
    directory: /
    schedule:
      interval: weekly
```

Without this, action pins are exactly the kind of silent staleness the §Anti-Staleness rules
exist to prevent — and the docs-CI workflow is the last place you want it, because a dead
action reports success by not running.

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
