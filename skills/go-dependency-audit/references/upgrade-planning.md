# Upgrade Planning

## Table of Contents
1. Semantic Versioning in Go Modules
2. Upgrade Risk Assessment
3. +incompatible Migration
4. Major Version Upgrade Patterns
5. Dependency Graph Analysis
6. Upgrade Execution

---

## 1 Semantic Versioning in Go Modules

### Version Format

`v{Major}.{Minor}.{Patch}[-pre][+meta]`

| Component | Meaning                          | Compatibility          |
|-----------|----------------------------------|------------------------|
| Major     | Breaking API changes             | NOT backward compatible|
| Minor     | New features                     | Backward compatible    |
| Patch     | Bug fixes                        | Backward compatible    |
| Pre       | Pre-release label (alpha, beta)  | NOT for production     |

### Pseudo-versions

Format: `v0.0.0-{timestamp}-{commit_hash_prefix}`

Example: `v1.0.1-20231109134442-10cbfed86s6y`

Pseudo-versions appear when:
- A dependency has no semver tags
- You pin to a specific commit
- The module pre-dates Go module support

### MVS (Minimal Version Selection)

Go selects the **minimum version** that satisfies all constraints:

```
A requires C >= v1.3
B requires C >= v1.4
Result: C v1.4 (not v1.5, not latest)
```

Key implication: `go get` does NOT automatically use the latest version.
You must explicitly request upgrades.

---

## 2 Upgrade Risk Assessment

### Risk Tiers

| Upgrade Type     | Example               | Risk     | Testing Required         |
|------------------|-----------------------|----------|--------------------------|
| Patch            | v1.2.3 -> v1.2.4     | Minimal  | Unit tests               |
| Minor            | v1.2.x -> v1.3.0     | Low      | Unit + integration tests |
| Major            | v1.x.x -> v2.0.0     | High     | Full regression suite    |
| Cross-module     | Multiple deps at once | Very High| Full regression + staging|
| stdlib           | Go 1.21 -> 1.22      | Medium   | Full test suite          |

### Pre-upgrade Checklist

1. **Read CHANGELOG/release notes** — not all maintainers follow semver
2. **Check for deprecated APIs** — `go vet` may catch some
3. **Review breaking changes list** — if the module documents them
4. **Check downstream impact** — does this module have known issues in new version?
5. **Run tests before AND after** — establish baseline, then compare
6. **One module at a time** — never upgrade multiple unrelated deps simultaneously

### Dangerous Patterns

**`go get -u` upgrades EVERYTHING:**
```bash
# DANGEROUS: upgrades target AND all transitive deps
go get -u github.com/foo/bar

# SAFE: upgrade only the target to specific version
go get github.com/foo/bar@v1.3.0
```

**`go get -u ./...` is even more dangerous:**
```bash
# VERY DANGEROUS: upgrades ALL direct and indirect deps to latest minor/patch
go get -u ./...
# This can change 50+ modules in one operation
```

---

## 3 +incompatible Migration

### What +incompatible Means

```
require github.com/uber/jaeger-client-go v2.29.1+incompatible
```

This module:
- Published v2+ tags BEFORE Go modules existed
- Does NOT have a go.mod file (or go.mod doesn't declare v2 module path)
- Import path doesn't include `/v2` suffix
- MVS cannot properly resolve version conflicts for this module

### Why It Matters

1. **Version resolution is fragile** — MVS doesn't understand the major version
2. **Future upgrades may break** — maintainer may add go.mod later, changing resolution
3. **Security scanning gaps** — vulnerability databases may not map correctly

### Migration Path

```bash
# 1. Check if maintainer has added go.mod support
go list -m -versions github.com/uber/jaeger-client-go

# 2. If v2 module path exists:
go get github.com/uber/jaeger-client-go/v2@latest

# 3. Update all import paths
# OLD: import "github.com/uber/jaeger-client-go"
# NEW: import "github.com/uber/jaeger-client-go/v2"

# 4. If no module-aware version exists, evaluate alternatives
# - Fork and add go.mod
# - Switch to alternative library
# - Accept +incompatible as documented tech debt
```

---

## 4 Major Version Upgrade Patterns

### The `/vN` Convention

Go modules v2+ MUST include the major version in the module path:

```go
// go.mod for v2
module github.com/author/lib/v2

// import in consumer
import "github.com/author/lib/v2/pkg"
```

### Upgrade Strategy

1. **Update go.mod:**
   ```bash
   go get github.com/author/lib/v2@latest
   ```

2. **Update all import paths:**
   ```bash
   # Find all imports of the old version
   grep -r '"github.com/author/lib/' --include='*.go' .
   
   # Replace with v2 import path
   # Use goimports or manual find-and-replace
   ```

3. **Handle API changes:**
   - Review migration guide (if available)
   - Check for renamed/removed functions
   - Update struct field usage
   - Adapt to new error types

4. **Remove old version:**
   ```bash
   go mod tidy  # Removes unused old version
   ```

### Coexistence Pattern (Temporary)

During migration, both v1 and v2 can coexist:

```go
import (
    libv1 "github.com/author/lib"     // old, being phased out
    libv2 "github.com/author/lib/v2"  // new, being adopted
)
```

This is a migration aid, not a long-term pattern. Remove v1 after full migration.

---

## 5 Dependency Graph Analysis

### Visualizing the Graph

```bash
# Full dependency graph (text format)
go mod graph

# Why is a specific module included?
go mod why -m github.com/some/dep

# List all versions of a specific module
go list -m -versions github.com/some/dep

# Check which modules are outdated
go list -m -u all
# Modules with updates show: current [latest]
```

### Identifying Problematic Patterns

**Deep transitive chains:**
```bash
go mod graph | grep 'target/module' | wc -l
# If a module appears in many dependency chains, upgrading it has wide impact
```

**Circular dependencies:**
```bash
# Check for cycles (rudimentary)
go mod graph | awk '{print $1, $2}' | sort | uniq > /tmp/deps.txt
# Visual inspection or cycle detection script needed
```

**Pinned versions vs. latest:**
```bash
# Show all direct deps with their latest available version
go list -m -u -json all | jq 'select(.Indirect != true) | 
  select(.Update != null) | {Path, Version, Update: .Update.Version}'
```

---

## 6 Upgrade Execution

### Single Dependency Upgrade

```bash
# 1. Check current version
go list -m github.com/foo/bar

# 2. Check available versions
go list -m -versions github.com/foo/bar

# 3. Upgrade to specific version
go get github.com/foo/bar@v1.3.0

# 4. Clean up
go mod tidy

# 5. Verify
go build ./...
go test ./...

# 6. Check what changed
git diff go.mod go.sum
```

### Batch Upgrade (Careful)

```bash
# 1. List outdated direct dependencies
go list -m -u all | grep '\[' | grep -v 'indirect'

# 2. Upgrade one at a time, test between each
for dep in $(go list -m -u all | grep '\[' | grep -v indirect | awk '{print $1}'); do
  echo "Upgrading $dep..."
  go get "$dep@latest"
  go mod tidy
  if ! go test ./...; then
    echo "FAIL: $dep upgrade broke tests"
    git checkout go.mod go.sum  # Rollback
    break
  fi
done
```

### Emergency Patch (CVE Response)

```bash
# When a CVE fix is in a specific version:
go get golang.org/x/net@v0.17.0  # Exact version with fix
go mod tidy
go mod verify                     # Confirm integrity
govulncheck ./...                 # Confirm CVE resolved
go test ./...                     # Confirm no regressions
```

### Using replace for Emergency Fixes

```bash
# When upstream hasn't released a fix yet:
# 1. Fork the vulnerable dependency
# 2. Apply the fix in your fork
# 3. Use replace directive
replace github.com/vulnerable/lib v1.2.3 => github.com/yourfork/lib v1.2.3-patched

# IMPORTANT: Document the replace with a TODO and issue link
// TODO(security): Remove after upstream merges fix (github.com/vulnerable/lib/issues/123)
```