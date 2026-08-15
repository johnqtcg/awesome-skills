# Upgrade Planning

> **This reference emits commands for a human to run.** The audit itself is
> read-only (SKILL.md S1.3). Nothing here should be executed by the skill, and
> nothing here may discard uncommitted work.

## Table of Contents
1. Versions in Go Modules
2. Upgrade Risk Assessment
3. Retracted and Deprecated Versions
4. `+incompatible` Migration
5. Major Version Upgrade Patterns
6. Dependency Graph Analysis
7. Upgrade Execution
8. Emergency Patch (Vulnerability Response)

---

## 1 Versions in Go Modules

### Format

`vMAJOR.MINOR.PATCH[-prerelease][+build]`

| Component | Signals                     | Guarantee                                        |
|-----------|-----------------------------|--------------------------------------------------|
| Major     | Breaking API changes        | None — expect breakage                           |
| Minor     | New features                | *Intended* backward compatible                    |
| Patch     | Bug fixes                   | *Intended* backward compatible                    |
| Prerelease| alpha/beta/rc               | None; sorts *before* the release of the same number |

"Intended" is doing real work in that table. Semver is a convention the author
opts into, and Go does not verify it. A minor bump can and does break callers.
Read the changelog; do not infer safety from the shape of the number.

### v0 has no compatibility promise at all

Go's module reference is explicit that major version zero carries no backward
compatibility guarantee. `v0.4.0 -> v0.5.0` is, by the spec, as free to break you
as `v1 -> v2` — the difference is only that the author is not obliged to bump the
module path. This matters because a large share of the Go ecosystem lives
permanently at v0.

**An audit must not label a `v0` bump "low risk" on the strength of it being a
minor or patch increment.** Report `v0` dependencies as a category, and treat
every `v0` upgrade as changelog-gated.

### Pseudo-versions

A pseudo-version encodes a specific commit. Three forms, depending on what the
nearest tagged version is:

| Situation                          | Form                                        | Real example                          |
|------------------------------------|---------------------------------------------|---------------------------------------|
| No known base version              | `vX.0.0-yyyymmddhhmmss-abcdefabcdef`        | `v0.0.0-20200825200019-8632dd797987`  |
| Base is a release `vX.Y.Z`         | `vX.Y.(Z+1)-0.yyyymmddhhmmss-abcdefabcdef`  | `v0.21.1-0.20240508182429-e35e4ccd0d2d` |
| Base is a prerelease `vX.Y.Z-pre`  | `vX.Y.Z-pre.0.yyyymmddhhmmss-abcdefabcdef`  | —                                     |

The timestamp is UTC `yyyymmddhhmmss`, and the suffix is exactly **12 lowercase
hexadecimal** characters of the commit hash. A "pseudo-version" containing
non-hex characters, or missing the `-0.` element in the second form, is malformed
and will not resolve — worth checking when a `go.mod` was hand-edited.

Pseudo-versions appear when a dependency has no semver tags, when you pin to a
commit, or when a module predates Go modules.

### Minimal Version Selection

Go selects the **minimum version satisfying all requirements**:

```
A requires C >= v1.3
B requires C >= v1.4
Selected: C v1.4     (not v1.5, not latest)
```

Two consequences the audit must state correctly:

1. Builds do not silently drift upward. A version enters your build only because
   some `require` asked for at least that.
2. **Any `go get` re-solves the whole graph.** Raising one module raises its
   requirements too, which can raise modules you did not name. "Targeted upgrade"
   means *targeted intent*, not a guarantee that only one line of `go.mod` moves.
   Always diff `go.mod` afterwards.

---

## 2 Upgrade Risk Assessment

| Upgrade                 | Example              | Risk      | Gate before merging          |
|-------------------------|----------------------|-----------|------------------------------|
| Patch, v1+              | v1.2.3 -> v1.2.4     | Low       | Unit tests                   |
| Minor, v1+              | v1.2.x -> v1.3.0     | Low-Medium| Unit + integration; skim changelog |
| **Any bump at v0**      | v0.4.1 -> v0.5.0     | **Medium-High** | Changelog mandatory; API diff |
| Major                   | v1.x -> v2.0.0       | High      | Full regression; migration plan |
| Multiple modules at once| batch upgrade        | Very High | Full regression + staging    |
| Go toolchain            | 1.22 -> 1.23         | Medium    | Full test suite; re-run govulncheck (stdlib findings move with it) |

### Pre-upgrade checklist

1. **Read the changelog / release notes.** If there are none, that is itself a
   risk signal worth recording.
2. **Check for a retraction or deprecation** on the target version — see S3.
3. **Diff the exported API** when the module documents nothing:
   `go doc -all <pkg>` before and after, or `gorelease` for a structured report.
4. **Establish a green baseline first.** "Tests fail after the upgrade" is only
   information if they passed before it.
5. **One module per commit.** A batch upgrade that breaks gives you no bisect.
6. **Re-run `govulncheck` after**, not only before — an upgrade can introduce a
   vulnerable transitive version as easily as it removes one.

### `go get -u` and what it actually does

```bash
# Raises the named module AND its dependencies to their latest minor/patch
go get -u github.com/foo/bar

# Raises everything in the build list. Routinely moves dozens of modules.
go get -u ./...

# Named version — the narrowest intent available
go get github.com/foo/bar@v1.3.0
```

`-u` is not "upgrade one thing"; it is "upgrade this thing and everything beneath
it". For a vulnerability fix you want the third form, then a `go.mod` diff to see
what minimal version selection did in response.

---

## 3 Retracted and Deprecated Versions

Signals the author publishes in-band, invisible to vulnerability scanners:

```bash
go list -mod=readonly -m -u -retracted all

go list -mod=readonly -m -u -json all \
  | jq 'select(.Retracted != null or .Deprecated != "")
        | {Path, Version, Retracted, Deprecated}'
```

- **Retracted** — the author marked this exact version broken via a `retract`
  directive. Check the retraction message; upgrading off a retracted version is
  usually urgent and usually trivial.
- **Deprecated** — the whole module is no longer maintained. Nothing breaks
  today; plan a migration.

Check both **before** proposing any target version. Upgrading onto a retracted
version is an avoidable, embarrassing outcome.

---

## 4 `+incompatible` Migration

```
require github.com/uber/jaeger-client-go v2.29.1+incompatible
```

The suffix means the module published `v2`+ tags without a module-aware `go.mod`
declaring the `/v2` path.

**What it actually does — and it is worse than "the toolchain ignores it".** The
Go modules reference is explicit: `+incompatible` "indicates that a version is
part of the same module as versions with lower major version numbers;
consequently, the `go` command may automatically upgrade to higher
`+incompatible` versions even though it may break the build."

So MVS does *not* overlook these versions. It compares and selects them like any
others — because as far as the toolchain is concerned they belong to one module
path. Consequences:

1. **A routine `-u` can cross a major version.** A module at `v1.5.2` can be
   upgraded straight to `v4.1.2+incompatible` with no `/vN` import-path change to
   signal that anything happened. This is the concrete risk; "MVS can't see it"
   is both wrong and less alarming than the truth.
2. **Resolution shifts if the maintainer modularises later** — once a real
   `go.mod` with a `/vN` path exists, the `+incompatible` line stops being an
   upgrade target and becomes a separate module.
3. **Vulnerability records may not map cleanly** onto the `+incompatible`
   version string.
4. **The suffix is never a tag.** `v4.1.2+incompatible` refers to the repository
   tag `v4.1.2`; the suffix exists only in versions the `go` command computes.

The module must also sit at the repository root, with no `go.mod` present.

### Migration path

```bash
# 1. Is there a module-aware major version?
go list -mod=readonly -m -versions github.com/uber/jaeger-client-go
go list -mod=readonly -m -versions github.com/uber/jaeger-client-go/v2

# 2. If yes, adopt it
go get github.com/uber/jaeger-client-go/v2@latest

# 3. Update import paths
#    OLD: import "github.com/uber/jaeger-client-go"
#    NEW: import "github.com/uber/jaeger-client-go/v2"

# 4. If no module-aware version exists, evaluate: fork and add go.mod,
#    switch libraries, or accept it as recorded technical debt
```

---

## 5 Major Version Upgrade Patterns

### The `/vN` convention

Modules at v2 and above must carry the major version in the module path:

```go
// go.mod of the dependency
module github.com/author/lib/v2

// import in the consumer
import "github.com/author/lib/v2/pkg"
```

Because the path differs, v1 and v2 are *different modules* to the toolchain.
That is what makes incremental migration possible.

### Strategy

```bash
# 1. Add the new major version
go get github.com/author/lib/v2@latest

# 2. Find every import of the old path (word-boundary quote avoids matching /v2)
grep -rn '"github.com/author/lib"' --include='*.go' .
grep -rn '"github.com/author/lib/' --include='*.go' .

# 3. Update imports, then adapt to API changes:
#    renamed and removed functions, changed struct fields, new error types

# 4. Drop the old version once nothing imports it
go mod tidy
```

### Coexistence during migration

```go
import (
    libv1 "github.com/author/lib"     // being retired
    libv2 "github.com/author/lib/v2"  // being adopted
)
```

Both versions are compiled in — binary size and, if the library holds global
state, behavior may both be affected. Legitimate as a transitional step, not as
a resting state. If a package's types cross between the two, they are unrelated
types to the compiler and will not interoperate.

---

## 6 Dependency Graph Analysis

```bash
# Full module graph
go mod graph

# Why is this module here?
go mod why -m github.com/some/dep

# What versions exist?
go list -mod=readonly -m -versions github.com/some/dep

# What has updates available?
go list -mod=readonly -m -u all            # shows: current [latest]

# Direct dependencies with updates, machine-readable
go list -mod=readonly -m -u -json all \
  | jq 'select(.Indirect != true and .Update != null and .Main != true)
        | {Path, Version, Update: .Update.Version}'
```

### Blast radius

```bash
# How many edges point at this module? High counts mean a wide upgrade impact.
go mod graph | awk -v m=github.com/some/dep '$2 ~ "^"m"@" {print $1}' | sort -u
```

A module required by many others is one whose upgrade needs staging, because MVS
will raise it for every dependent at once.

### Module-graph cycles are legal

`go mod graph` can legitimately contain cycles: module A may require B while B
requires A. The Go toolchain permits this and resolves it normally. Only
**package-level import cycles** are rejected, and those are a compile error you
will already know about.

An audit must therefore **not** report a module-graph cycle as a failed check. It
is worth a WARN-level note — a cycle couples two modules' release cadences and
widens upgrade blast radius — but it is a design observation, not a defect.

---

## 7 Upgrade Execution

> These are commands the **user** runs. The audit emits them; it does not run
> them, and it never emits a rollback that discards uncommitted work.

### Precondition

```bash
git status --porcelain go.mod go.sum
# Must be empty. If it is not, commit or stash FIRST — every recovery
# path below assumes the committed state is the fallback.
```

### Single dependency

```bash
go list -mod=readonly -m github.com/foo/bar              # current
go list -mod=readonly -m -versions github.com/foo/bar    # available
go list -mod=readonly -m -u -retracted github.com/foo/bar  # retracted or deprecated?

go get github.com/foo/bar@v1.3.0
go mod tidy

git diff go.mod go.sum                     # what did MVS actually move?
go build ./... && go test ./...
govulncheck ./...                          # confirm nothing new arrived
```

### Sequential batch

One module at a time, stopping at the first failure. Note what this loop does
**not** do: it never reverts. Stopping leaves the failure on disk to inspect,
and the clean precondition above means `git restore` remains available to the
human as a deliberate choice.

```bash
#!/usr/bin/env bash
set -uo pipefail

if [ -n "$(git status --porcelain go.mod go.sum)" ]; then
  echo "go.mod/go.sum are dirty — commit or stash before upgrading"; exit 1
fi

mapfile -t deps < <(
  go list -mod=readonly -m -u -json all \
    | jq -r 'select(.Indirect != true and .Update != null and .Main != true) | .Path'
)

for dep in "${deps[@]}"; do
  echo "=== $dep ==="
  go get "$dep@latest" && go mod tidy || { echo "STOP: $dep failed to resolve"; exit 1; }
  if ! go test ./...; then
    echo "STOP: $dep broke tests. go.mod/go.sum left as-is for inspection:"
    git --no-pager diff --stat go.mod go.sum
    exit 1
  fi
  git commit -am "chore: upgrade $dep" || true
done
```

Committing after each success is what makes the sequence recoverable: every green
step is a restore point, so recovery is `git revert`, not an overwrite of the
working tree.

### `replace` for a fix not yet released upstream

```go
// go.mod
replace github.com/vulnerable/lib v1.2.3 => github.com/yourfork/lib v1.2.3-patched
```

Record, next to the directive, why it exists and what removes it — an upstream
issue or PR link, and an owner. A bare marker comment is not tracking; the
removal condition belongs somewhere that gets reviewed.

---

## 8 Emergency Patch (Vulnerability Response)

```bash
# 0. Confirm the current state and the finding's evidence tier
git status --porcelain go.mod go.sum     # must be empty
govulncheck ./... ; echo "rc=$?"         # rc=3 means findings at scan level

# 1. Identify which direct dependency pulls the affected module in —
#    that is the one you can actually move
go mod why -m golang.org/x/net

# 2. Move to the fixed version named in the govulncheck output
go get golang.org/x/net@v0.17.0
go mod tidy

# 3. Verify — in this order
git diff go.mod go.sum                   # what else did MVS move?
go mod verify                            # integrity intact
go build ./... && go test ./...          # no regressions
govulncheck ./... ; echo "rc=$?"         # rc=0 confirms resolution
```

Step 3's `rc=0` is the only evidence that the vulnerability is resolved. A
successful build is not evidence — it never was.

If no fixed version exists, the remediation is not an upgrade. Record the finding
as unresolved with a compensating control (disable the affected code path, add a
WAF rule, restrict input at the boundary) and a date to re-check. Do not close a
finding because there was nothing convenient to upgrade to.
