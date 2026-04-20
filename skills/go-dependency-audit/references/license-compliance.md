# License Compliance

## Table of Contents
1. License Categories
2. Compatibility Matrix
3. Scanning with go-licenses
4. Transitive License Propagation
5. Common Violations
6. Remediation Strategies

---

## 1 License Categories

### Permissive (Low Risk)

| License       | Key Terms                                    | Commercial Use |
|---------------|----------------------------------------------|----------------|
| MIT           | Do anything, keep copyright notice           | Yes            |
| Apache-2.0    | Like MIT + patent grant + NOTICE file        | Yes            |
| BSD-2-Clause  | Do anything, keep copyright, no endorsement  | Yes            |
| BSD-3-Clause  | Like BSD-2 + no-endorsement clause           | Yes            |
| ISC           | Simplified BSD equivalent                    | Yes            |
| Unlicense     | Public domain dedication                     | Yes            |

### Copyleft (High Risk for Proprietary)

| License       | Key Terms                                         | Commercial Use    |
|---------------|---------------------------------------------------|-------------------|
| GPL-2.0       | Derivative works must be GPL; source disclosure    | Requires GPL      |
| GPL-3.0       | GPL-2.0 + patent protection + anti-tivoization    | Requires GPL      |
| AGPL-3.0      | GPL-3.0 + network use triggers source disclosure  | Effectively no    |
| LGPL-2.1      | Weaker copyleft; dynamic linking may be exempt     | With restrictions  |
| MPL-2.0       | File-level copyleft; new files can be proprietary  | With restrictions  |

### Problematic / Unknown

| Category         | Examples                          | Action Required           |
|------------------|-----------------------------------|---------------------------|
| No license file  | Repository without LICENSE        | STOP — assume all rights  |
| Custom license   | Non-standard terms                | Legal review required     |
| WTFPL / Beerware | Joke licenses                     | Legal review — unclear    |
| Dual license     | MIT OR GPL-3.0                    | Choose permissive option  |

---

## 2 Compatibility Matrix

### Can proprietary projects use this license?

| Your Project | MIT | Apache | BSD | MPL-2.0 | LGPL | GPL | AGPL |
|--------------|-----|--------|-----|---------|------|-----|------|
| Proprietary  | Yes | Yes    | Yes | Partial | Partial | No | No  |
| MIT          | Yes | Yes    | Yes | Yes     | Yes  | No  | No   |
| Apache-2.0   | Yes | Yes    | Yes | Yes     | Yes  | No  | No   |
| GPL-3.0      | Yes | Yes    | Yes | Yes     | Yes  | Yes | No   |

**Partial**: Allowed with conditions (e.g., LGPL allows dynamic linking;
MPL-2.0 allows new files to be proprietary but modified MPL files stay MPL).

### Key Rule

**Most restrictive license wins.** If ANY dependency in the transitive tree
is GPL, and you statically link it (which Go does by default), your binary
is encumbered by GPL terms.

---

## 3 Scanning with go-licenses

### Basic Report

```bash
# List all dependencies with their licenses
go-licenses report ./... 2>/dev/null

# Output format: module_path  license_url  license_type
# Example:
# github.com/gin-gonic/gin  https://github.com/.../LICENSE  MIT
# github.com/lib/pq         https://github.com/.../LICENSE  MIT
```

### Compliance Check

```bash
# Fail if any dependency uses a non-allowed license
go-licenses check ./... \
  --allowed_licenses=MIT,Apache-2.0,BSD-2-Clause,BSD-3-Clause,ISC

# Exit code 0 = all compliant, non-zero = violations found
```

### Save Licenses Locally

```bash
# Copy all license files to a directory (for distribution compliance)
go-licenses save ./... --save_path=./third_party/licenses
```

### When go-licenses Is Unavailable

Manual fallback:
```bash
# List all modules
go list -m all | tail -n +2 | while read mod ver; do
  MODDIR=$(go env GOMODCACHE)/${mod}@${ver}
  if [ -d "$MODDIR" ]; then
    LICENSE=$(find "$MODDIR" -maxdepth 1 -iname 'LICENSE*' -o -iname 'COPYING*' | head -1)
    if [ -n "$LICENSE" ]; then
      echo "$mod  $ver  $(head -1 "$LICENSE")"
    else
      echo "$mod  $ver  NO_LICENSE_FOUND"
    fi
  fi
done
```

---

## 4 Transitive License Propagation

### Go's Static Linking Model

Go compiles to statically linked binaries by default. This means:
- ALL imported package code is embedded in the binary
- Dynamic linking exceptions (CGO, plugin) are rare
- From a license perspective, ALL dependencies are "distributed"

### Propagation Example

```
Your Project (MIT)
  -> github.com/foo/bar (MIT)
    -> github.com/baz/qux (GPL-3.0)     <-- Problem!
```

Even though `baz/qux` is a transitive dependency you didn't choose, its GPL
license propagates through the static binary. Your project is encumbered.

### Detection

```bash
# Full transitive dependency list
go list -m all

# Check why a specific module is included
go mod why -m github.com/baz/qux
# Output shows the import chain from your code to the dependency
```

---

## 5 Common Violations

### Violation 1: GPL Transitive in Proprietary Project

**Scenario**: Direct dependency is MIT, but it pulls in a GPL library.
**Detection**: `go-licenses check` fails on the transitive dependency.
**Fix**: Replace the direct dependency with an alternative that doesn't
transitively import GPL code, or get legal approval.

### Violation 2: Missing LICENSE File

**Scenario**: Module has no LICENSE or COPYING file in repository.
**Detection**: `go-licenses report` shows "Unknown" or errors.
**Impact**: Legally, this means "all rights reserved" — you have no license
to use, modify, or distribute the code.
**Fix**: Contact maintainer to add a license, or replace the dependency.

### Violation 3: AGPL in SaaS Context

**Scenario**: AGPL dependency in a network service (SaaS).
**Detection**: Manual or `go-licenses report` shows AGPL-3.0.
**Impact**: AGPL requires source disclosure for network-accessible services.
**Fix**: Replace dependency. AGPL is effectively incompatible with SaaS.

### Violation 4: Dual License Not Chosen

**Scenario**: Dependency offers "MIT OR GPL-3.0" but no explicit choice made.
**Detection**: License scanner shows both options.
**Fix**: Document the chosen license in your compliance records.

---

## 6 Remediation Strategies

| Problem                     | Strategy                                        | Effort |
|-----------------------------|-------------------------------------------------|--------|
| GPL transitive dependency   | Replace direct dep that pulls it in             | Medium |
| Missing license             | Contact maintainer or find alternative           | Low    |
| AGPL in SaaS                | Replace immediately                              | High   |
| Unknown license             | Legal review, then replace or accept             | Medium |
| Dual license                | Document chosen option                           | Low    |
| License changed in upgrade  | Pin version, evaluate new license                | Medium |