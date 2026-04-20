# Supply Chain Security

## Table of Contents
1. Go Module Security Model
2. go.sum and Integrity Verification
3. GOPROXY Configuration
4. Private Module Handling
5. Deleted Tag Recovery
6. SBOM Generation
7. Supply Chain Threat Model

---

## 1 Go Module Security Model

### Three Pillars

1. **Immutable module versions** — once published, a version cannot change content
2. **Cryptographic verification** — go.sum records hashes, verified against sumdb
3. **Transparency log** — sum.golang.org provides public accountability

### Trust Boundaries

```
Developer Machine
  -> GOPROXY (cache/mirror)
    -> Source Repository (GitHub, GitLab, etc.)
      -> sum.golang.org (checksum database)
```

Each boundary has different trust properties:
- **GOPROXY**: caches content, may be corporate or public
- **Source repo**: authoritative source, but mutable (tags can be moved/deleted)
- **sum.golang.org**: append-only transparency log, tamper-evident

---

## 2 go.sum and Integrity Verification

### go.sum Format

Each line contains:
```
module/path version h1:hash=
module/path version/go.mod h1:hash=
```

Two entries per module version:
- `h1:hash` — SHA-256 of the module zip archive
- `/go.mod h1:hash` — SHA-256 of the go.mod file alone

### Verification Commands

```bash
# Verify all cached modules match go.sum
go mod verify
# Output: "all modules verified" or lists mismatches

# Download and verify all dependencies
go mod download -x
# -x flag shows what's being fetched
```

### Common Integrity Failures

| Error                                    | Cause                         | Fix                        |
|------------------------------------------|-------------------------------|----------------------------|
| `SECURITY ERROR` in go mod verify        | Cache tampered                | Clear cache, re-download   |
| `verifying: checksum mismatch`           | go.sum out of date            | `go mod tidy`              |
| `no required module provides package`    | Module removed from registry  | `replace` with fork        |
| `GONOSUMCHECK` bypass detected           | sum checking disabled         | Remove bypass, investigate |

### go.sum Best Practices

1. **Always commit go.sum** — it's the integrity anchor for reproducible builds
2. **Review go.sum diffs** — new entries mean new dependencies added
3. **Never manually edit go.sum** — let `go mod tidy` manage it
4. **Alert on unexpected go.sum changes** — could indicate dependency injection

---

## 3 GOPROXY Configuration

### Default Configuration

```bash
# Default (Go 1.13+)
GOPROXY=https://proxy.golang.org,direct
```

### Corporate Proxy Setup

```bash
# Company proxy first, public fallback, then direct
GOPROXY=https://goproxy.company.com,https://proxy.golang.org,direct

# Company proxy only (no external access)
GOPROXY=https://goproxy.company.com

# Direct only (no proxy, not recommended)
GOPROXY=direct
```

### GONOSUMDB and GONOSUMCHECK

```bash
# Skip sum database check for private modules
GONOSUMDB=*.company.com,github.com/company/*

# Skip ALL sum verification (DANGEROUS — only for debugging)
GONOSUMCHECK=*  # Never use in CI/production
```

### Proxy Security Considerations

| Configuration           | Integrity | Privacy        | Availability      |
|-------------------------|-----------|----------------|-------------------|
| proxy.golang.org        | High      | Module names leak| Google-dependent |
| Corporate proxy         | High      | Internal        | Self-managed     |
| `direct` only           | Medium    | Source repos see| Source-dependent  |
| `GONOSUMCHECK=*`        | None      | N/A            | N/A               |

---

## 4 Private Module Handling

### GOPRIVATE Configuration

```bash
# Tell Go tools these modules are private
GOPRIVATE=*.company.com,github.com/company/*

# GOPRIVATE is shorthand for:
GONOSUMDB=*.company.com,github.com/company/*
GONOPROXY=*.company.com,github.com/company/*
```

### Why GOPRIVATE Matters

Without GOPRIVATE:
- Private module names are sent to proxy.golang.org (information leak)
- Private module checksums are sent to sum.golang.org (information leak)
- Download attempts from public proxy fail (revealing existence of private modules)

### Private Module Authentication

```bash
# .netrc for HTTPS authentication
machine github.com
  login oauth2
  password ${GITHUB_TOKEN}

# Or: git config for SSH
git config --global url."ssh://git@github.com/company/".insteadOf "https://github.com/company/"
```

### CI Configuration

```bash
# CI environment variables
export GOPRIVATE="github.com/company/*"
export GONOSUMDB="github.com/company/*"
# Ensure CI has credentials for private repos
```

---

## 5 Deleted Tag Recovery

### Problem

```
go: github.com/foo/bar@v1.2.3: reading github.com/foo/bar/go.mod at revision v1.2.3:
  unknown revision v1.2.3
```

A dependency tag was deleted upstream. Your build breaks.

### Recovery Steps

**Step 1: Check if proxy has cached version**
```bash
# proxy.golang.org caches immutably — tag deletion doesn't affect cached versions
GOPROXY=https://proxy.golang.org go mod download github.com/foo/bar@v1.2.3
```

**Step 2: If proxy doesn't have it, find the commit**
```bash
# Check git history for the deleted tag
git ls-remote https://github.com/foo/bar | grep v1.2
# Use commit hash as pseudo-version
go get github.com/foo/bar@commithash
```

**Step 3: Use replace as emergency fix**
```go
// go.mod
replace github.com/foo/bar v1.2.3 => github.com/foo/bar v1.2.4
// Or point to your fork
replace github.com/foo/bar v1.2.3 => github.com/yourfork/bar v1.2.3-restored
```

**Step 4: Permanent fix**
```bash
# Upgrade to a version that exists
go get github.com/foo/bar@v1.3.0  # Next available version
go mod tidy
```

### Prevention

1. **Use proxy.golang.org** — it caches versions immutably
2. **Vendor dependencies** — `go mod vendor` creates local copies
3. **Monitor dependency availability** — alert on `go mod download` failures in CI
4. **Pin with go.sum** — the hash in go.sum ensures version immutability even with proxy

---

## 6 SBOM Generation

### Software Bill of Materials

An SBOM lists all components in your software, required for:
- Regulatory compliance (Executive Order 14028, EU CRA)
- Incident response (quickly check if you're affected by a new CVE)
- License auditing (complete transitive dependency inventory)

### Go Module SBOM

```bash
# CycloneDX format (industry standard)
# Install: go install github.com/CycloneDX/cyclonedx-gomod/cmd/cyclonedx-gomod@latest
cyclonedx-gomod mod -json -output sbom.json

# SPDX format
# Install: go install github.com/spdx/tools-golang/cmd/builder@latest
# (requires manual configuration)

# Simple module list (not a standard SBOM but useful)
go list -m -json all > modules.json
```

### SBOM Contents Should Include

- Module path and version for every dependency
- License identifier (SPDX format)
- Checksum (from go.sum)
- Direct vs. transitive classification
- Build timestamp and Go version

---

## 7 Supply Chain Threat Model

### Attack Vectors

| Vector                      | Example                                  | Mitigation                         |
|-----------------------------|------------------------------------------|------------------------------------|
| Typosquatting               | `github.com/g0lang/net` (zero for O)     | Review new deps carefully          |
| Account takeover            | Maintainer account compromised           | go.sum detects changed content     |
| Dependency confusion        | Internal name matches public module       | GOPRIVATE configuration            |
| Tag manipulation            | Tag moved to different commit             | go.sum hash verification           |
| Malicious update            | Backdoor in minor version update         | Review diffs, pin versions         |
| Abandoned library           | No maintainer, CVEs unfixed              | Monitor dependency health          |

### Defense Checklist

1. **go.sum committed and verified** — never bypass checksum verification
2. **GOPRIVATE set for all internal domains** — prevent information leakage
3. **GOPROXY points to trusted proxy** — immutable caching layer
4. **Minimal direct dependencies** — reduce attack surface
5. **Regular govulncheck scans** — detect known vulnerabilities
6. **Dependency review in PRs** — review go.mod/go.sum changes
7. **SBOM generated and maintained** — inventory for incident response
8. **Replace directives documented** — each with justification and removal timeline