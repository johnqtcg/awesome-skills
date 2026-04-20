# govulncheck Patterns

## Table of Contents
1. Execution Modes
2. Source Mode Deep Dive
3. Reading Output
4. Triage Decision Tree
5. CI Integration
6. Common False Positives
7. Companion Tools

---

## 1 Execution Modes

### Source Mode (Primary)

```bash
# Scan all packages in module — traces call graph for reachability
govulncheck ./...

# Scan specific package
govulncheck ./cmd/server/...

# Scan with JSON output for automation
govulncheck -json ./...

# Scan with specific Go version context
govulncheck -go=1.21 ./...
```

Source mode uses the Go call graph to determine whether your code actually
reaches the vulnerable function. A dependency may contain a CVE, but if your
code never calls the affected function (directly or transitively), source mode
reports it as **not called** — drastically reducing noise.

### Binary Mode

```bash
# Scan compiled binary — no source required
govulncheck -mode=binary ./cmd/server
```

Binary mode scans the symbol table of compiled binaries. Less precise than
source mode (cannot trace call paths), but useful for:
- Third-party binaries without source
- Verifying what's actually linked vs what go.mod declares
- CI pipelines that build first, scan second

### Version Query Mode

```bash
# Check specific module version without source
govulncheck -mode=query -db=https://vuln.go.dev golang.org/x/net@v0.15.0
```

Quick lookup without full source analysis. Useful for pre-upgrade assessment.

---

## 2 Source Mode Deep Dive

### Call Graph Reachability

govulncheck traces the call graph from your module's entry points
(`main` functions, test functions, init functions) through all transitive calls.

**Reachable vulnerability**: Your code -> pkg A -> pkg B -> vulnerable function
```
Vulnerability #1: GO-2023-2102
  Found in: golang.org/x/net@v0.15.0
  Fixed in: golang.org/x/net@v0.17.0
  Your code is affected.
    main.go:45: main calls server.ListenAndServe
    server.go:12: server.ListenAndServe calls http2.ConfigureServer
    http2.go:89: http2.ConfigureServer calls http2.countReset  <-- vulnerable
```

**Unreachable vulnerability**: CVE exists in dependency, but no call path
```
Vulnerability #2: GO-2023-2153
  Found in: golang.org/x/crypto@v0.13.0
  Fixed in: golang.org/x/crypto@v0.14.0
  Your code is NOT affected.
    The vulnerable symbol ssh.ServerConfig.SetDefaults is not called.
```

### Entry Point Analysis

govulncheck considers these entry points:
- `func main()` in `package main`
- `func init()` in any imported package
- `func Test*`, `func Benchmark*`, `func Fuzz*` in `_test.go` files
- Functions exported from library packages (when scanning a library)

### stdlib Vulnerabilities

govulncheck also checks the Go standard library itself:
```
Vulnerability #3: GO-2023-2186
  Found in: stdlib@go1.21.0
  Fixed in: stdlib@go1.21.4
  Your code is affected.
```

Fix: upgrade Go toolchain version.

---

## 3 Reading Output

### JSON Output Format

```bash
govulncheck -json ./... 2>&1
```

Key fields in JSON output:
```json
{
  "finding": {
    "osv": "GO-2023-2102",
    "trace": [
      {"module": "golang.org/x/net", "version": "v0.15.0",
       "package": "golang.org/x/net/http2", "function": "countReset",
       "position": {"filename": "http2.go", "line": 89}},
      {"module": "your/module", "package": "your/pkg",
       "function": "ListenAndServe",
       "position": {"filename": "server.go", "line": 12}}
    ],
    "fixed_version": "v0.17.0"
  }
}
```

### Interpreting Results

| Output phrase                    | Meaning                    | Action              |
|----------------------------------|----------------------------|---------------------|
| "Your code is affected"          | Reachable vulnerability    | Fix immediately     |
| "Your code is NOT affected"      | Not reachable via callgraph| Track, plan upgrade |
| "No vulnerabilities found"       | Clean scan                 | Document and verify |
| "Found N vulnerabilities"        | Mixed results              | Triage by severity  |

---

## 4 Triage Decision Tree

```
CVE found in dependency
  |
  +-- govulncheck source mode: reachable?
  |     |
  |     +-- YES: Check CVSS score
  |     |     |
  |     |     +-- >= 9.0: P0 Critical — patch now
  |     |     +-- >= 7.0: P1 High — patch this sprint
  |     |     +-- >= 4.0: P2 Medium — plan upgrade
  |     |     +-- < 4.0:  P3 Low — backlog
  |     |
  |     +-- NO (not called): Check if direct dependency
  |           |
  |           +-- Direct dep: P3 Low — upgrade at convenience
  |           +-- Transitive: P3 Low — track only
  |
  +-- govulncheck not available: Fall back to version matching
        |
        +-- Version match only: report as "unconfirmed"
        +-- Cannot claim "not affected" without source scan
```

### Reachability Override Rules

Even if govulncheck says "not called", escalate to P2+ when:
- The vulnerable function is in a package you DO import (import proximity)
- The CVE is actively exploited in the wild (threat intelligence)
- The CVSS is >= 9.0 and the fix is a simple version bump

---

## 5 CI Integration

### GitHub Actions

```yaml
- name: govulncheck
  uses: golang/govulncheck-action@v1
  with:
    go-version-file: go.mod
    go-package: ./...
```

### Generic CI Script

```bash
#!/bin/bash
set -euo pipefail

echo "=== govulncheck scan ==="
RESULT=$(govulncheck -json ./... 2>&1)

# Count findings by reachability
REACHABLE=$(echo "$RESULT" | jq '[.finding // empty | select(.trace[0].function != null)] | length')
TOTAL=$(echo "$RESULT" | jq '[.finding // empty] | length')

echo "Total CVEs: $TOTAL, Reachable: $REACHABLE"

# Fail CI only on reachable vulnerabilities
if [ "$REACHABLE" -gt 0 ]; then
  echo "FAIL: $REACHABLE reachable vulnerabilities found"
  exit 1
fi
```

---

## 6 Common False Positives

### Test-only Dependencies

CVE in a module only imported in `_test.go` files. Not a production risk.
- **Action**: P3 Low — fix at convenience, not urgent
- **Detection**: `go mod why -m <module>` shows only test import paths

### Build-constrained Code

CVE in platform-specific code (`// +build linux`) when deploying to different OS.
- **Action**: Verify build tags match deployment target
- **Detection**: Check `go list -tags=...` with production build tags

### Deprecated Module Path

Old module path has CVE, but project already migrated to new path.
- **Action**: Verify go.mod no longer references old path
- **Detection**: `grep old/module/path go.mod` should return nothing

---

## 7 Companion Tools

### trivy (Container + FS scanner)

```bash
# Filesystem scan (checks go.mod/go.sum)
trivy fs --scanners vuln .

# With severity filter
trivy fs --severity HIGH,CRITICAL .
```

Trivy uses version matching (not call-graph). Noisier than govulncheck but
covers more ecosystems (npm, pip, etc.) in polyglot projects.

### nancy (Sonatype OSS Index)

```bash
# Pipe go list output to nancy
go list -json -deps ./... | nancy sleuth
```

Uses Sonatype OSS Index for vulnerability data. Different database from
Go vulnerability DB — may find issues govulncheck misses (and vice versa).

### go-licenses

```bash
# Report all licenses
go-licenses report ./... 2>/dev/null

# Check compliance against allowed list
go-licenses check ./... --allowed_licenses=MIT,Apache-2.0,BSD-3-Clause
```

Not a vulnerability scanner — focused on license compliance. Essential
for commercial/proprietary projects.