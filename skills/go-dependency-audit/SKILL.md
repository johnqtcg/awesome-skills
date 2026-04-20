---
name: go-dependency-audit
description: >
  Go dependency audit specialist for CVE scanning (govulncheck), license
  compliance, outdated dependency detection, upgrade impact analysis, and
  supply chain security. ALWAYS use when auditing go.mod dependencies,
  running govulncheck, checking license compatibility, planning dependency
  upgrades, or investigating supply chain risks in Go projects. Complements
  security-review (code-level) with module-level supply chain analysis.
allowed-tools: Read, Grep, Glob, Bash(govulncheck*), Bash(go mod*), Bash(go list*), Bash(go version*), Bash(go vet*), Bash(trivy*), Bash(nancy*), Bash(go-licenses*), Bash(cat go.mod*), Bash(cat go.sum*), Bash(git log*), Bash(git blame*)
---

## Quick Reference

| When you need...                          | Jump to                                    |
|-------------------------------------------|--------------------------------------------|
| Run a full dependency audit               | S2 Gates -> S5 Checklist -> S9 Output      |
| Scan for known CVEs                       | S2 Gates -> S5.1 CVE Scanning              |
| Check license compliance                  | S5.2 License Compliance                    |
| Plan a major version upgrade              | S5.3 Upgrade Planning                      |
| Investigate supply chain risk             | S5.4 Supply Chain Security                 |
| Review go.mod hygiene                     | S5.5 Module Hygiene                        |
| Triage a govulncheck finding              | S7 Anti-Examples -> analysis ref           |

---

## 1 Scope

**In scope**: go.mod/go.sum analysis, CVE scanning via govulncheck (primary),
license compliance checking, outdated dependency reporting, upgrade path
planning, breaking change assessment, supply chain posture (proxy, checksum,
private modules), circular dependency detection, +incompatible version triage.

**Out of scope**: application code security (use `security-review`), micro-
benchmark performance (use `go-benchmark`), infrastructure provisioning,
container image scanning (Dockerfile-level), runtime behavior analysis.

---

## 2 Mandatory Gates

Gates are serial hard blockers. Failure at any gate stops all subsequent work.

### Gate 1: Module Discovery

Locate and parse go.mod. STOP if no go.mod found in project root or specified path.

| Item              | How to check                            | Required |
|-------------------|-----------------------------------------|----------|
| go.mod exists     | `Glob("**/go.mod")`                     | Yes      |
| go.sum exists     | Adjacent to go.mod                      | Yes      |
| Go version        | `go version` / go directive in go.mod   | Yes      |
| Module path       | `module` directive in go.mod            | Yes      |
| Workspace         | Check for go.work (note but don't fail) | No       |

### Gate 2: Tool Availability

Check scanning tools. Degrade gracefully if optional tools are missing.

| Tool           | Check command                 | Required | Fallback                    |
|----------------|-------------------------------|----------|-----------------------------|
| govulncheck    | `govulncheck -version`        | Yes      | STOP — primary CVE scanner  |
| go-licenses    | `go-licenses version`         | No       | Manual license review       |
| trivy          | `trivy --version`             | No       | govulncheck-only mode       |
| nancy          | `nancy --version`             | No       | govulncheck-only mode       |

### Gate 3: Dependency Graph Completeness

Verify go.mod/go.sum are in sync. STOP if graph is broken.

| Check                        | Command                      | Failure action              |
|------------------------------|------------------------------|-----------------------------|
| Modules resolved             | `go mod verify`              | STOP — integrity failure    |
| Tidy state                   | `go mod tidy -diff` (1.21+)  | WARN — suggest tidy first   |
| No missing deps              | `go mod download`            | STOP — unresolvable deps    |

### Gate 4: Scope Classification

Classify the audit into one of three modes:

| Mode         | Trigger                                         | Deliverable                           |
|--------------|-------------------------------------------------|---------------------------------------|
| **Quick**    | "check for CVEs", single concern                | CVE scan + severity triage            |
| **Standard** | "audit dependencies", pre-release check         | Full 5-domain audit + upgrade plan    |
| **Deep**     | "supply chain review", compliance audit         | All domains + license + provenance    |

### Gate 5: Output Completeness

Before delivering, verify all S9 output sections are present. STOP and fill gaps.

---

## 3 Depth Selection

### Quick
Single-concern scan. Load no reference files.
- Triggers: "run govulncheck", "any CVEs?", "check this dependency"
- Coverage: govulncheck scan, severity triage, immediate remediation

### Standard (default)
Full audit across 5 domains. Load `references/govulncheck-patterns.md`.
- Triggers: pre-release audit, "audit our dependencies", quarterly review
- Coverage: CVE scan, license check, outdated report, upgrade assessment, module hygiene
- Force Standard if: multiple go.mod files, compliance requirements, CI integration

### Deep
Comprehensive supply chain review. Load all references.
- Triggers: compliance audit, incident response, "supply chain review"
- Coverage: all Standard domains + provenance, SBOM, transitive license, proxy config
- Force Deep if: regulatory compliance, post-incident, new vendor onboarding

---

## 4 Degradation Modes

When prerequisites are incomplete, produce explicitly-marked partial output.

| Available Data                 | Mode       | Can Deliver                              | Cannot Claim                  |
|--------------------------------|------------|------------------------------------------|-------------------------------|
| go.mod + govulncheck           | Full       | CVE scan + severity + remediation plan   | License or upgrade analysis   |
| go.mod only, no tools          | Manual     | Dependency list + version analysis       | CVE status, reachability      |
| go.sum missing                 | Degraded   | Module list + known issues               | Integrity verification        |
| No go.mod found                | Planning   | Go module setup guidance                 | Any audit findings            |
| govulncheck unavailable        | Partial    | License + outdated + hygiene checks      | CVE scan results              |

Mark degraded outputs: `# DEGRADED: [reason] - [what's missing]`

Never fabricate CVE findings. Never claim "no vulnerabilities" without scanning.

---

## 5 Dependency Audit Checklist

### 5.1 CVE Scanning

1. **govulncheck in source mode is primary** — `govulncheck ./...` checks reachability,
   not just version matching. Binary-only scanning misses call-graph context.
2. **Source mode confirms reachability** — a CVE in a dependency is only actionable
   if your code reaches the vulnerable function. govulncheck traces the call graph.
3. **Transitive CVEs need triage** — indirect dependencies with CVEs may not be
   reachable. Check `go mod why <pkg>` to confirm the dependency chain.
4. **CVSS score alone is insufficient** — a CVSS 9.8 in an unreachable function is
   less urgent than a CVSS 6.5 in a hot code path. Reachability determines priority.

### 5.2 License Compliance

5. **Categorize licenses by risk** — Permissive (MIT, Apache-2.0, BSD) are low risk.
   Copyleft (GPL, AGPL, LGPL) require legal review. Unknown licenses are blockers.
6. **Transitive licenses propagate** — a GPL transitive dependency makes the entire
   binary GPL-encumbered. Check the full dependency tree, not just direct imports.
7. **License files must exist** — missing LICENSE file is a red flag. The module may
   have implicit "all rights reserved" status.
8. **Commercial license compatibility** — proprietary projects cannot use AGPL
   dependencies. Document license compatibility matrix for the project.

### 5.3 Upgrade Planning

9. **Semantic versioning drives risk assessment** — patch upgrades (v1.2.3 -> v1.2.4)
   are safe. Minor upgrades (v1.2 -> v1.3) need changelog review. Major upgrades
   (v1 -> v2) require migration planning.
10. **Check CHANGELOG and release notes before upgrading** — not all maintainers
    follow semver correctly. A "minor" release may contain breaking changes.
11. **`+incompatible` versions signal migration debt** — these modules published v2+
    without proper go.mod support. Plan migration to properly-versioned forks.
12. **`go get -u` is dangerous** — it upgrades ALL transitive dependencies, not just
    the target. Use `go get pkg@version` for precise control.

### 5.4 Supply Chain Security

13. **go.sum is your integrity anchor** — it contains cryptographic hashes for every
    dependency. Commit both go.mod and go.sum. Verify with `go mod verify`.
14. **GOPROXY configuration matters** — use a trusted proxy (proxy.golang.org or
    corporate mirror). Direct fetches from source repos lose immutability guarantees.
15. **GOPRIVATE for internal modules** — prevents leaking internal module paths to
    public proxy/checksum servers. Set for all internal domain patterns.
16. **Deleted tags break reproducibility** — if a dependency tag is deleted upstream,
    builds fail. Monitor dependency availability. Use `replace` as emergency fix.

### 5.5 Module Hygiene

17. **Run `go mod tidy` before committing** — removes unused dependencies, adds
    missing ones, updates go.sum. Check the diff to understand what changed.
18. **Minimize `replace` directives** — each replace is technical debt. Document why
    each exists and when it can be removed. Temporary replaces for debugging must
    never be committed.
19. **Avoid circular dependencies between modules** — A imports B, B imports A
    creates cascading version conflicts. Design clear module boundaries.
20. **Do not commit go.work** — workspace files are local development aids. Add
    go.work and go.work.sum to .gitignore.

---

## 6 Severity Model

### P0 Critical
- Known RCE, auth bypass, or data exfiltration CVE in a **reachable** direct dependency
- CVSS >= 9.0 AND govulncheck confirms call-graph reachability
- Must patch immediately — merge-blocking

### P1 High
- CVE with CVSS >= 7.0 AND reachable, OR critical CVE in reachable transitive dependency
- AGPL/GPL license violation in proprietary project
- Integrity failure: go.sum mismatch or missing checksums

### P2 Medium
- CVE with CVSS >= 4.0 but limited exploitability or partial reachability
- Dependency 2+ major versions behind latest
- `+incompatible` version in active dependency
- License ambiguity (missing LICENSE file)

### P3 Low
- CVE in unreachable transitive dependency (govulncheck confirms no path)
- Minor version behind latest (within same major)
- Hygiene issues: unnecessary `replace` directives, untidy go.mod
- EOL library with no known active CVEs

---

## 7 Anti-Examples

### AE-1: Reporting every CVE without checking reachability

```
# WRONG: flag all CVE matches from version database
Found: CVE-2023-44487 in golang.org/x/net v0.15.0 (CVSS 7.5)
Action: UPGRADE IMMEDIATELY
// Version-only matching reports CVEs for functions you never call.
// govulncheck source mode may show: "No vulnerabilities found" — the
// vulnerable function is not reachable from your code.

# RIGHT: run govulncheck in source mode, triage by reachability
$ govulncheck ./...
Vulnerability GO-2023-2102 (CVE-2023-44487) — NOT CALLED
  Package: golang.org/x/net/http2
  Your code does not call the vulnerable function.
// Result: P3 Low — track for next upgrade cycle, not urgent
```

### AE-2: Ignoring transitive dependency licenses

```
# WRONG: "all our direct dependencies are MIT, we're fine"
go.mod: github.com/foo/bar v1.0.0  // MIT license
// But bar depends on github.com/baz/qux which is GPL-3.0.
// Your binary links GPL code. Legal team will not be happy.

# RIGHT: check full transitive license tree
$ go-licenses report ./... 2>/dev/null | grep -v "Apache\|MIT\|BSD"
github.com/baz/qux  GPL-3.0
// Flag for legal review before release
```

### AE-3: Using `go get -u` for a single dependency upgrade

```
# WRONG: upgrade everything to fix one CVE
$ go get -u ./...
// Upgrades 47 transitive dependencies. Three of them have breaking
// changes. CI breaks. Rollback takes hours.

# RIGHT: targeted upgrade of the specific vulnerable dependency
$ go get golang.org/x/net@v0.17.0
$ go mod tidy
// Only the target and its direct requirements change
```

### AE-4: Leaving `replace` directives after debugging

```
# WRONG: committed go.mod with local path replace
replace github.com/company/lib => ../lib
// Works on your machine. CI fails. Production deploy fails.
// Every developer must have identical directory structure.

# RIGHT: remove replace before committing, or use versioned fork
replace github.com/company/lib => github.com/yourfork/lib v1.2.3-fix
// Temporary: document in PR, set reminder to remove after upstream merges
```

### AE-5: Claiming "no vulnerabilities" without running govulncheck

```
# WRONG: "I checked go.mod, all versions look recent, we're safe"
// Manual version inspection cannot assess CVE status.
// A v1.20.0 released yesterday could already have a CVE.

# RIGHT: always run govulncheck for CVE claims
$ govulncheck ./...
No vulnerabilities found.
// Only govulncheck (or equivalent scanner) can make this claim
```

### AE-6: Treating +incompatible as harmless

```
# WRONG: "it compiles, so +incompatible is fine"
require github.com/uber/jaeger-client-go v2.29.1+incompatible
// +incompatible means this module lacks go.mod for v2+.
// MVS cannot resolve version conflicts properly.
// Upgrade path is unpredictable.

# RIGHT: plan migration to module-aware version
// Check if maintainer has published go.mod-aware v2
// If not, evaluate alternative libraries
// Document +incompatible as technical debt with timeline
```

---

## 8 Dependency Audit Scorecard

Three-tier scoring applied after every audit.

### Critical (must all pass — any failure = audit incomplete)

1. **govulncheck executed** — source mode scan completed without error
2. **No reachable P0 CVEs** — all CVSS >= 9.0 reachable vulns addressed
3. **go.mod/go.sum integrity verified** — `go mod verify` passes

### Standard (>= 4 of 5 must pass)

4. **No reachable P1 CVEs** — all CVSS >= 7.0 reachable vulns addressed or waived
5. **License compliance checked** — no copyleft violations in proprietary projects
6. **No +incompatible direct dependencies** — all direct deps have proper go.mod
7. **Dependencies within 1 major version of latest** — no severely outdated modules
8. **GOPROXY and GOPRIVATE configured** — supply chain basics in place

### Hygiene (>= 3 of 4 must pass)

9. **go.mod is tidy** — `go mod tidy` produces no diff
10. **No unnecessary replace directives** — each replace has documented justification
11. **Circular dependencies absent** — `go mod graph` shows no cycles
12. **go.work not committed** — workspace file in .gitignore

**Verdict**: Critical 3/3 AND Standard >= 4/5 AND Hygiene >= 3/4 = **PASS**

---

## 9 Output Contract

Every response MUST include these sections. Volume rules: P0/P1 findings fully
detailed; P2 up to 10; P3 summary only.

### 9.1 Audit Context
Module path, Go version, dependency count (direct/indirect), scan timestamp.

### 9.2 Mode & Depth
`Quick | Standard | Deep` with rationale for selection.

### 9.3 CVE Scan Results
govulncheck output summary: reachable vulns, unreachable vulns, total modules.
Per finding: CVE ID, CVSS, affected module, reachable (yes/no), fix version.

### 9.4 License Summary
License distribution table. Flag any copyleft, unknown, or missing licenses.

### 9.5 Outdated Dependencies
Direct dependencies behind latest, grouped by severity (major/minor/patch behind).

### 9.6 Supply Chain Posture
GOPROXY config, GOPRIVATE, go.sum status, replace directives inventory.

### 9.7 Upgrade Recommendations
Prioritized upgrade plan: immediate (P0/P1 CVE fixes), short-term (P2, license),
backlog (P3, hygiene). Each with: module, current -> target version, risk level.

### 9.8 Uncovered Risks
What this audit did NOT cover. Mandatory — never empty. Examples: "transitive
license check skipped — go-licenses not installed", "binary-only deps not scanned",
"private module registry not audited".

### 9.9 Machine-Readable Summary
```json
{"summary":{"pass":true,"score":"10/12"},"counts":{"p0":0,"p1":1,"p2":3,"p3":5},
"modules":{"direct":12,"indirect":47,"vulnerable":4,"eol":1}}
```

**Scorecard appended**: `X/12 — Critical Y/3, Standard Z/5, Hygiene W/4 — PASS/FAIL`

---

## 10 Reference Loading Guide

| Condition                                    | Load                                   |
|----------------------------------------------|----------------------------------------|
| CVE scanning (Standard+)                     | `references/govulncheck-patterns.md`   |
| License compliance (Standard+)               | `references/license-compliance.md`     |
| Upgrade planning, version migration          | `references/upgrade-planning.md`       |
| Supply chain review (Deep)                   | `references/supply-chain-security.md`  |

Each reference has a table of contents. Load relevant sections, not the
entire file, when only a specific pattern is needed.