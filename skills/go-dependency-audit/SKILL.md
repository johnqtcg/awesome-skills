---
name: go-dependency-audit
description: >
  Go dependency audit specialist for CVE scanning (govulncheck), license risk
  triage, outdated dependency detection, upgrade impact analysis, and supply
  chain security. ALWAYS use when auditing go.mod dependencies, running
  govulncheck, checking license compatibility, planning dependency upgrades, or
  investigating supply chain risks in Go projects. Read-only by default — emits
  a remediation plan instead of mutating go.mod/go.sum. Complements
  security-review (code-level) with module-level supply chain analysis.
allowed-tools: Read, Grep, Glob, Bash(govulncheck*), Bash(GOWORK=off govulncheck*), Bash(go version*), Bash(go env GO*), Bash(go list -mod=readonly*), Bash(go mod graph*), Bash(go mod verify*), Bash(go mod why*), Bash(go mod edit -json*), Bash(go mod tidy -diff*), Bash(go -C * list -mod=readonly*), Bash(go -C * mod graph*), Bash(go -C * mod verify*), Bash(go -C * mod why*), Bash(go -C * mod edit -json*), Bash(go -C * mod tidy -diff*), Bash(GOWORK=off go -C * list -mod=readonly*), Bash(GOWORK=off go list -mod=readonly*), Bash(go-licenses check*), Bash(go-licenses report*), Bash(go-licenses help*), Bash(GOWORK=off go-licenses check*), Bash(GOWORK=off go-licenses report*), Bash(trivy fs*), Bash(nancy sleuth*), Bash(jq -s*), Bash(jq -rs*), Bash(git status*), Bash(git diff*), Bash(git log*), Bash(git blame*)
---

## Quick Reference

| When you need...                          | Jump to                                    |
|-------------------------------------------|--------------------------------------------|
| Run a full dependency audit               | S2 Gates -> S5 Checklist -> S9 Output      |
| Scan for known CVEs                       | S2 Gates -> S5.1 CVE Scanning              |
| Triage a finding / decide urgency         | S6 — evidence tier, NOT a CVSS guess       |
| Check license risk                        | S5.2 + `references/license-compliance.md`  |
| Plan a version upgrade                    | S5.3 + `references/upgrade-planning.md`    |
| Investigate supply chain risk             | S5.4 + `references/supply-chain-security.md` |
| Review go.mod hygiene                     | S5.5 Module Hygiene                        |
| Actually apply a fix                      | S1.3 Remediation Boundary                  |

---

## 1 Scope & Operating Mode

### 1.1 In scope

go.mod/go.sum analysis, CVE scanning via govulncheck (primary), license risk
triage, outdated dependency reporting, upgrade path planning, breaking change
assessment, supply chain posture (proxy, checksum DB, private modules),
`+incompatible` triage, module graph analysis.

### 1.2 Out of scope

Application code security (use `security-review`), micro-benchmark performance
(use `go-benchmark`), infrastructure provisioning, container image scanning,
runtime behavior analysis, and **legal determinations about license
obligations** — see S5.2: this skill produces evidence and escalation triggers,
never verdicts.

### 1.3 Remediation Boundary (NON-NEGOTIABLE)

**An audit is read-only. It observes; it does not repair.**

| Class            | Commands                                                                 | Allowed during audit |
|------------------|--------------------------------------------------------------------------|----------------------|
| Read-only probe  | `govulncheck`, `go list -mod=readonly`, `go mod graph/verify/why`, `go mod edit -json`, `go mod tidy -diff`, `go version -m`, `go env <VAR>…`, `go-licenses check/report/help`, `git status/diff/log` | Yes |
| Mutating         | `go get`, `go mod tidy` (without `-diff`), `go mod edit -require`, `go work`, **`go env -w`**, **`go list -mod=mod`**, `go-licenses save`, `go install`, `cyclonedx-gomod -output` | No — emit as plan |
| Destructive      | `git checkout`, `git restore`, `git reset`, `rm`                           | Never — not even to roll back |

`allowed-tools` pre-approves; it does not forbid. It keeps writes off the
auto-approved surface, while gate 2/11's snapshot *detects* a mutation that
happened anyway. Two writes wear the name of a read, and a coarse list lets
both through:
**`go env -w`** rewrites Go's persistent env file rather than printing it, and
**`go list -mod=mod`** lets package loading update `go.mod`/`go.sum`. Readonly is
the default since Go 1.16, but `GOFLAGS` can override it — so every
package-loading command here states `-mod=readonly`. Writes that produce a
deliverable (`go-licenses save`, SBOM, tool installs) are remediation: emitted
under S9.7, marked `# EMIT` in the references, never run. Guarded by
regression checks DA008/DA014/DA015 — static checks that keep writes off the
auto-approved surface; they cannot stop a write at runtime.

1. **Emit, do not execute.** Every fix is delivered as a copy-pasteable command
   block under S9.7, for a human to run. The skill never runs it.
2. **Never generate a rollback that discards uncommitted work.** `git checkout
   go.mod go.sum` overwrites unstaged edits with no recovery path. Require a
   clean worktree instead — `git status --porcelain go.mod go.sum` empty before
   any upgrade loop — and stop on failure rather than revert.
3. **Prove read-only-ness.** Record `git status --porcelain go.mod go.sum` at the
   start and end. If it differs, a probe mutated the module files (e.g.
   `go mod download` on Go < 1.18) — say so in S9.8 rather than silently
   reporting post-mutation state.
4. Switching to remediation requires the user to ask for it in this turn.
   "Audit our dependencies" is not authorization to upgrade them.

---

## 2 Gates

Gates are checked in order. Each gate declares a **class** that determines what
failure does — this is the only thing that decides stop-vs-continue.

### 2.1 Gate classes

| Class       | Meaning                                          | On failure                                                        |
|-------------|--------------------------------------------------|-------------------------------------------------------------------|
| **BLOCK**   | The audit's subject does not exist or is untrustworthy | Stop. Emit no findings. Emit the reason + what would unblock, headed `NOT AN AUDIT`. |
| **DEGRADE** | A capability is unavailable; the subject is fine | Continue. Enter the matching S4 mode, list the lost coverage in S9.8. |
| **WARN**    | An observation worth reporting                   | Continue at full scope. Record as a finding.                       |

A gate has exactly one class. There is no gate that both stops and degrades.

### 2.2 Gate table

Order matters. Gates 1–2 touch no Go tooling, so the read-only baseline is
captured before anything could disturb it.

| #  | Gate                    | Check                                              | Class   | Failure action                                        |
|----|-------------------------|----------------------------------------------------|---------|-------------------------------------------------------|
| 1  | Module exists           | `Glob("**/go.mod")` — filesystem only               | BLOCK   | No Go module here — nothing to audit                  |
| 2  | Baseline snapshot       | `git status --porcelain go.mod go.sum` — **before any `go` command** | WARN | Note uncommitted module edits; the audit reflects the worktree, not HEAD |
| 3  | go.mod is well-formed   | `go mod edit -json` parses; `module` directive present | BLOCK | Malformed manifest — findings would be fiction         |
| 4  | Module graph resolvable | `go list -mod=readonly -m all` succeeds             | DEGRADE | -> `no-graph` mode (see below)                        |
| 5  | Checksums available     | go.sum covers every non-replaced external requirement | DEGRADE | -> `no-integrity` mode (see below — absence alone is not a failure) |
| 6  | Checksums verify        | `go mod verify`                                     | WARN    | **Report as a P1 finding, do not stop** — a tampered cache is exactly what an audit exists to surface |
| 7  | govulncheck available   | `govulncheck -version`                              | DEGRADE | -> `no-cve` mode                                      |
| 8  | Vuln DB reachable       | `govulncheck` exits 0 or 3, not 1                   | DEGRADE | -> `no-cve` mode (offline)                            |
| 9  | License tool available  | `go-licenses help` lists subcommands                | DEGRADE | -> `no-license` mode                                  |
| 10 | Tidy state              | `go mod tidy -diff` (**Go 1.23+**; skip below that) | WARN    | Report untidy go.mod as a hygiene finding             |
| 11 | Closing snapshot        | `git status --porcelain go.mod go.sum` matches gate 2 | WARN  | A probe mutated the module files — say so in S9.8     |

Four rationales, each replacing a worse rule:

- **Gate 2 precedes every `go` command.** A baseline taken after `go list` cannot
  prove the audit was read-only — `go list` is one of the things it would have to
  exonerate.
- **Gate 4 is DEGRADE, not BLOCK.** Gate 3 already caught a broken manifest; a
  failure here is environmental (offline, proxy down, missing credentials, cold
  cache) — a lost capability, not an untrustworthy subject.
- **Gate 5 is conditional, not "file exists".** A missing `go.sum` is legal when
  the module has no dependencies or every requirement is redirected by a local
  `replace`. Decide by what is required, not by `ls`: external non-`replace`d
  requirements with checksums missing -> DEGRADE; none, or all locally replaced
  -> **N/A**, legitimately absent, not a finding; cannot tell (gate 4 already
  degraded) -> DEGRADE, naming the unresolved graph as the cause.

- **Gate 6 is WARN.** An integrity failure is the highest-value output this skill
  can produce; stopping would suppress the finding the user most needs.
- **Gate 9 uses `help`, not `--help`.** `go-licenses --help` prints only the
  logging flags and never lists commands — a useless liveness probe.

### 2.3 Multi-module repositories

Gate 1 globs for **every** `go.mod`. If it finds more than one, **the unit of
audit is the module, not the repository** — running the gates once in the root
audits one module and reports it as though it covered all of them. When >1 is
found, before gate 3:

1. **Load `references/multi-module.md`** and follow it. Do not improvise.
2. **Snapshot all manifests at once**, still before any `go` command:
   `git status --porcelain -- '**/go.mod' '**/go.sum'`
3. **List every module in S9.1**; name any you skipped in S9.8.

Single-module repositories skip this — the gate table runs once.

### 2.4 Scope classification

| Mode         | Trigger                                    | Output contract |
|--------------|--------------------------------------------|-----------------|
| **Quick**    | "check for CVEs", one named concern        | S9 subset (9.1, 9.2, 9.3, 9.8, 9.9) |
| **Standard** | "audit dependencies", pre-release check    | Full S9          |
| **Deep**     | "supply chain review", compliance audit    | Full S9 + provenance/SBOM |

---

## 3 Depth Selection

### Quick
Single-concern scan. Load no reference files.
- Triggers: "run govulncheck", "any CVEs?", "check this dependency"
- Coverage: govulncheck scan + S6 triage + immediate remediation plan
- **Output**: the S9 subset above. Do not emit empty License/Supply-Chain
  sections — omit them and say why in S9.8.

### Standard (default)
Full audit across 5 domains. Load `govulncheck-patterns.md`,
`license-compliance.md`, `upgrade-planning.md` — one per domain this depth
covers. (`supply-chain-security.md` is Deep-only; `multi-module.md` loads on the
gate-1 trigger regardless of depth.)
- Triggers: pre-release audit, "audit our dependencies", quarterly review
- Coverage: CVE scan, license risk, outdated report, upgrade assessment, hygiene
- Force Standard if: multiple go.mod files, compliance requirements, CI integration

### Deep
Comprehensive supply chain review. Load all references.
- Triggers: compliance audit, incident response, "supply chain review"
- Coverage: all Standard domains + provenance, SBOM, transitive license, proxy config
- Force Deep if: regulatory compliance, post-incident, new vendor onboarding

---

## 4 Degradation Modes

Each mode is entered by exactly one DEGRADE gate. Modes compose — record all
that apply.

| Mode            | Entered by | Can still deliver                                | MUST NOT claim                                |
|-----------------|------------|--------------------------------------------------|-----------------------------------------------|
| `no-graph`      | Gate 4     | Direct requirements read from `go.mod`           | Anything about indirect dependencies, or that the list is complete |
| `no-integrity`  | Gate 5     | Module list, versions, licenses, hygiene         | Reproducible-build or tamper-detection status |
| `no-cve`        | Gate 7, 8  | License, outdated, hygiene, supply chain posture | Any CVE status — present, absent, or reachable |
| `no-license`    | Gate 9     | CVE, outdated, hygiene, supply chain posture     | License distribution or compliance posture    |
| `no-reachability` | `-scan` was not `symbol`, or binary mode | Which modules are affected           | That any finding is or is not reachable       |

Mark every degraded output inline: `# DEGRADED [<mode>]: <what is missing>`

Two absolute rules:

- **Never fabricate CVE findings.**
- **Never claim "no vulnerabilities" without a scan that completed.** A
  govulncheck exit code of 1 is a *failed scan*, not a clean one.

---

## 5 Dependency Audit Checklist

### 5.1 CVE Scanning

1. **`govulncheck ./...` in source mode is primary** — it traces the call graph,
   so it reports whether your code can actually reach the vulnerable symbol.
2. **The `-scan` level decides what "found" means** — `symbol` (default) reports
   reachable symbols, `package` imported packages, `module` required versions.
   Lowering it raises noise and forfeits reachability.
3. **Exit code is the CI contract, and `-format json` breaks it** — text mode:
   `3` found at scan level, `2` invalid usage, `1` error, `0` clean. `-json` /
   `-format sarif` / `-format openvex` exit **0 regardless of findings**, so a
   CI job gating on `$?` after them never fails.
4. **govulncheck reports no CVSS score** — see S6.1. Priority comes from the
   evidence tier, not from a severity number the tool never emitted.
5. **Test files are excluded by default** — `-test` defaults to false, so
   test-only dependencies are not analyzed unless you pass `-test`.
6. **Transitive findings still need `go mod why -m <module>`** to establish which
   direct dependency pulls them in — that is the module you actually upgrade.

### 5.2 License Risk Triage

> **This skill does not give legal advice and does not decide whether a license
> is compatible with a project.** It gathers the facts a lawyer needs and states
> which facts trigger escalation. Every copyleft finding routes to legal review.

7. **Report the license, the path, and the trigger conditions — never a verdict.**
   Whether a copyleft obligation attaches turns on facts this skill cannot see:
   distribution, linkage vs build-tool-only, licence version and exceptions,
   modification, deployment model. Record the observable; escalate the rest.
8. **Use the scanner's own vocabulary** — `go-licenses` types are `forbidden`,
   `restricted`, `reciprocal`, `notice`, `permissive`, `unencumbered`, `unknown`;
   `--disallowed_types` defaults to `forbidden,unknown`. Reporting in the tool's
   terms keeps the output auditable and version-stable.
9. **Distinguish shipped from not-shipped, and label the evidence grade.**
   Required (`go list -m all`) < build-dependency (`go list -mod=readonly -deps
   <main pkg>`, after discovering `main` packages — never assume `./cmd/...`) <
   binary (`go version -m <artifact>`, which reads the module list the build
   actually recorded). Say which grade you have; only the last supports the
   phrase "linked into the shipped binary".
10. **A missing LICENSE file is the highest-signal license finding** — no grant
    of rights was located. An escalation trigger, not a legal conclusion.
11. **Escalate with the facts attached**: module path, licence identifier and
    version, `go mod why -m` path, evidence grade for shipping (item 9), and
    whether the project distributes binaries or runs a network service.

### 5.3 Upgrade Planning

12. **Semver signals intent, not a guarantee.** Patch/minor are *lower risk*,
    not safe, and **`v0.x.y` carries no compatibility promise at all**. Read the
    changelog; diff the API surface when there is none.
13. **`+incompatible` is a silent major-version upgrade hazard** — the module
    published v2+ tags without a module-aware `go.mod`, so the toolchain treats
    those versions as part of the *same* module as v1.x. MVS can therefore
    upgrade v1.5.2 straight to v4.1.2+incompatible during a routine `-u`. Plan
    migration to a `/vN` path.
14. **`go get -u` upgrades far more than the target** — it raises the target and
    its dependencies. Use `go get <module>@<version>` for precise control, and
    remember that even a precise `go get` can move *other* modules, because
    minimal version selection re-solves the whole graph.

### 5.4 Supply Chain Security

15. **go.sum is an integrity anchor, not a lockfile.** It records expected hashes;
    it does not pin which version is selected — that is `go.mod` + MVS. Commit
    both; verify with `go mod verify`.
16. **GOPROXY affects availability and privacy, not checksum verification.**
    Validation is controlled by `GOSUMDB` and disabled per pattern by
    `GOPRIVATE`/`GONOSUMDB` — `GOPROXY=direct` still verifies.
17. **`GOPRIVATE` for internal modules** — stops internal module paths leaking to
    the public proxy and checksum database. Shorthand for `GONOPROXY` +
    `GONOSUMDB`.
18. **Deleted upstream tags break builds** — `proxy.golang.org` caches immutably,
    so a cached version survives tag deletion. Prefer the proxy over `direct`.

### 5.5 Module Hygiene

19. **Check tidiness without mutating** — `go mod tidy -diff` (Go 1.23+) prints
    the change and exits non-zero if non-empty. Below 1.23 report the check as
    unavailable rather than running the mutating `go mod tidy`.
20. **Minimize `replace` directives** — each is technical debt, and a local-path
    `replace` in a committed go.mod breaks every machine but the author's.
21. **Module-graph cycles are legal in Go and are not, by themselves, a defect.**
    Modules may require each other; only *package* import cycles are rejected by
    the compiler. Report a cycle as a WARN-level design smell that widens upgrade
    blast radius — never as a failed check.
22. **`go.work` is normally not committed** — it encodes one developer's local
    layout. Exception: a single-repository workspace whose `use` directives are
    all repo-relative. Check the paths before flagging it.

---

## 6 Triage & Priority Model

### 6.1 The tool gives you evidence, not a score

The Go vulnerability database does **not** publish CVSS scores, so govulncheck
never prints one. Its report carries the `GO-YYYY-NNNN` ID, aliases (CVE/GHSA),
summary, affected ranges, fixed version, and `database_specific.review_status`
(`REVIEWED` / `UNREVIEWED`). Both rules are mandatory:

- **Never state a CVSS score sourced from govulncheck.** It did not produce one.
- Any CVSS must be enriched from a *named external source* keyed on the alias —
  "CVSS 9.8 (NVD, CVE-2023-44487)" — and recorded in S9.3. With no such lookup
  the column reads `not retrieved`, never a guess.

### 6.2 Evidence tiers

govulncheck groups findings into result sections. The section *is* the evidence.

| Section                   | Meaning                                                | Tier |
|---------------------------|--------------------------------------------------------|------|
| `=== Symbol Results ===`  | A vulnerable symbol is reachable from your call graph  | **E1 Called** |
| `=== Package Results ===` | You import the affected package; no reachable symbol proven | **E2 Imported** |
| `=== Module Results ===`  | The module is required at an affected version only     | **E3 Required** |

`No vulnerabilities found.` = zero findings at any tier.

### 6.3 Priority

| Priority | Condition |
|----------|-----------|
| **P0** | E1 Called, a fix version exists, and the call path is reachable from a network-facing entry point |
| **P1** | E1 Called (any other case); **or** `go mod verify` reported a checksum mismatch; **or** an unlicensed dependency is linked into a shipped binary |
| **P2** | E2 Imported; **or** a copyleft dependency linked into a shipped artifact and pending legal review; **or** a `+incompatible` direct dependency |
| **P3** | E3 Required only; minor-version drift; hygiene findings; EOL library with no current findings |

Escalation modifiers — apply, then state the reason:

- **No fix version available** — escalate one; remediation is a compensating
  control, not an upgrade.
- **`UNREVIEWED` report** — absence of a symbol-level finding is not proof of
  unreachability. Hold at the tier reported and note the status.
- **Reachability not established** (`-scan module|package`, binary mode, or
  reflection/`unsafe`/plugin in the path) — `no-reachability` mode. Report the
  tier obtained; never downgrade on absent evidence.
- **Test-only dependency** — de-escalate one, only after `go mod why -m` confirms
  no non-test path exists.

---

## 7 Anti-Examples

Each rule below is binding on its own. Worked WRONG/RIGHT pairs for all six are
in `references/anti-examples.md` — load it when an audit is about to do one of
these things, or when explaining why not.

| ID   | Anti-pattern                                    | Rule                                                                 |
|------|-------------------------------------------------|----------------------------------------------------------------------|
| AE-1 | Assigning a CVSS score govulncheck never emitted | Report `CVSS: not retrieved`, or cite the external database and alias it came from. Priority comes from the evidence tier. |
| AE-2 | Turning a licence observation into a legal verdict | Emit the escalation packet — module, licence, path, linkage, distribution — and route to legal. Never conclude. |
| AE-3 | Gating CI on an exit code `-json` always sets to 0 | Gate on the text-mode exit code (3 = found, 1 = broke), or parse findings from JSON with `jq -s`. |
| AE-4 | Rolling back with a command that destroys work   | Never emit `git checkout`/`restore`/`reset`. Require a clean worktree up front and stop on failure. |
| AE-5 | Claiming "no vulnerabilities" from a failed scan | Only exit 0 with `No vulnerabilities found.` supports that claim. Exit 1 means `no-cve`, status UNKNOWN. |
| AE-6 | Treating `+incompatible` as harmless             | It is the *same* module as v1.x to MVS, so `-u` can cross a major version silently. Track as P2 with a `/vN` migration plan. |

---

## 8 Dependency Audit Scorecard

Twelve checks in three tiers, applied after every audit —
**load `references/scorecard.md`** for the item list and score them there.

A check that could not run because of a DEGRADE gate scores **N/A** and leaves
both numerator and denominator; it never counts as a pass. Score each tier as a
ratio over its applicable items, because a fixed threshold breaks the moment an
item goes N/A:

```
critical = passed / applicable   must be 1.00      (0 applicable -> tier N/A)
standard = passed / applicable   must be >= 0.80
hygiene  = passed / applicable   must be >= 0.75
PASS iff every non-N/A tier meets its threshold.
```

Report ratio and raw counts: `Standard 3/3 (1.00) — 2 items N/A`. In a
multi-module audit the repository verdict is the **worst** module's, never an
average — an average lets a clean module mask a failing one.

---

## 9 Output Contract

Quick mode emits 9.1, 9.2, 9.3, 9.8, 9.9; Standard and Deep emit all nine. An
omitted section must be named in 9.8 with the reason — never silently dropped,
never emitted empty. Volume: P0/P1 fully detailed, P2 up to 10, P3 summary.

### 9.1 Audit Context
Every module audited (path + directory), Go version, direct/indirect counts,
worktree state, tool versions, scan timestamp.

### 9.2 Mode & Depth
`Quick | Standard | Deep`, plus every active degradation mode from S4 and the
gate that triggered it.

### 9.3 CVE Scan Results
Command (with `-scan`/`-mode`), exit code, and per finding: GO-ID, aliases,
module, evidence tier (E1/E2/E3), fixed version, review status, priority, and
CVSS **with its source** or `not retrieved`.

### 9.4 License Inventory
Per dependency: licence identifier, scanner classification, shipping evidence
grade (S5.2 item 9). Separate escalation table for copyleft/unknown/missing with
the item-11 facts attached. No verdicts.

### 9.5 Outdated Dependencies
Direct dependencies behind latest, grouped by major/minor/patch drift, with the
`v0.x` ones called out as unbounded-risk regardless of the size of the bump.

### 9.6 Supply Chain Posture
Actual `go env` values (`GOPROXY`, `GOPRIVATE`, `GONOPROXY`, `GONOSUMDB`,
`GOSUMDB`); go.sum status and `go mod verify` result; `replace` inventory.

### 9.7 Remediation Plan
Prioritized, **as commands for the user to run** — this skill does not run them.
Immediate (P0/P1), short-term (P2), backlog (P3). Each entry: module, current ->
target, evidence tier resolved, and precondition (clean worktree, green baseline).

### 9.8 Uncovered Risks
What this audit did NOT cover. Mandatory — never empty. Must include every
degradation mode, N/A scorecard item, omitted output section, module not audited,
and escalation handed to another party.

### 9.9 Machine-Readable Summary
```json
{"summary":{"pass":true,"modes":["no-license"],
 "tiers":{"critical":{"passed":3,"applicable":3,"ratio":1.0},
          "standard":{"passed":4,"applicable":4,"ratio":1.0,"na":1},
          "hygiene":{"passed":3,"applicable":4,"ratio":0.75}}},
"counts":{"p0":0,"p1":1,"p2":3,"p3":5},
"evidence":{"e1_called":1,"e2_imported":3,"e3_required":5},
"modules":{"direct":12,"indirect":47,"affected":4},
"scan":{"tool":"govulncheck","mode":"source","scan_level":"symbol","exit_code":3}}
```

**Scorecard appended**, ratios with raw counts and N/A totals:
`Critical 3/3 (1.00) · Standard 4/4 (1.00, 1 N/A) · Hygiene 3/4 (0.75) — PASS`

---

## 10 Reference Loading Guide

| Condition                                    | Load                                   |
|----------------------------------------------|----------------------------------------|
| CVE scanning (Standard+)                     | `references/govulncheck-patterns.md`   |
| License risk triage (Standard+)              | `references/license-compliance.md`     |
| Upgrade planning, version migration (Standard+) | `references/upgrade-planning.md`    |
| Supply chain review (Deep)                   | `references/supply-chain-security.md`  |
| About to do — or explain — an S7 anti-pattern | `references/anti-examples.md`          |
| More than one `go.mod` found (gate 1)         | `references/multi-module.md`           |
| Scoring the audit (S8)                        | `references/scorecard.md`             |

Each reference has a table of contents — load the relevant sections, not the
whole file.

**Tool-version note (G1)**: commands here are verified against `govulncheck
v1.1.4`, `go-licenses v2.0.1`, and Go 1.26.1.
`go mod tidy -diff` additionally requires Go 1.23+.
Check `govulncheck -version` and the local `go` version before relying on a
flag. A govulncheck built against a *different* Go than the one on `PATH` fails
package loading with exit 1 — that is `no-cve`, and the fix is to rebuild
govulncheck, not to report a clean scan.
