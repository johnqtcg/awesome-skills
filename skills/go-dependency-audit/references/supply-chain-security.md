# Supply Chain Security

> Environment-variable names and semantics below are verified against
> `go help environment` and `go env` on Go 1.26.1. Go's module environment has
> accumulated obsolete names from the pre-release `vgo` prototype that still
> circulate in blog posts; S3.4 lists the ones that do nothing.

## Table of Contents
1. Go Module Security Model
2. go.sum: What It Guarantees and What It Does Not
3. Checksum Database and Proxy Configuration
4. Private Module Handling
5. Retracted and Deprecated Modules
6. Deleted Tag Recovery
7. SBOM Generation
8. Supply Chain Threat Model

---

## 1 Go Module Security Model

### Three pillars

1. **Immutable module versions** — once published and cached, a version's content
   is fixed
2. **Cryptographic verification** — `go.sum` records hashes, checked on every use
3. **Transparency log** — `sum.golang.org` is an append-only, tamper-evident
   record of module hashes

### Trust boundaries

```
Developer / CI machine
  -> GOPROXY (cache / mirror)          availability + privacy
    -> Source repository (GitHub, ...)  authoritative but MUTABLE (tags move)
  -> GOSUMDB (sum.golang.org)          integrity, independent of GOPROXY
```

The critical property: **the checksum database is consulted independently of the
proxy**. A malicious or compromised proxy cannot serve altered content without
the hash mismatching. This is why the proxy and the sumdb are separate knobs.

---

## 2 go.sum: What It Guarantees and What It Does Not

### Format

Each line has three space-separated fields: module path, version, and hash.

```
module/path version         h1:hash=     # hash of the files in the module .zip
module/path version/go.mod  h1:hash=     # hash of the go.mod file alone
```

A version may therefore appear under **at most two kinds of entry** — the `/go.mod`
one, and the module-zip one. It is not a guarantee that both are present: a module
pulled in only for graph resolution, whose source is never downloaded, carries the
`/go.mod` entry alone. `h1` is SHA-256 and is currently the only algorithm.

`go.sum` may also be **empty or absent entirely** — legitimately so, when the
module has no dependencies, or when every dependency is replaced with a local
directory via `replace`. A missing `go.sum` is a question to ask, not an
automatic finding.

### go.sum is an integrity anchor, not a lockfile

This distinction causes real confusion, and the audit must get it right:

| | `go.sum` | A lockfile (`package-lock.json`, `Cargo.lock`) |
|---|---|---|
| Decides which versions are used | **No** | Yes |
| Records expected hashes | Yes | Yes |
| Contains only selected versions | **No** — may include versions considered but not selected | Yes |
| Removing a line changes the build | No — it removes a *check* | Yes |

Version selection comes from the `require` directives in `go.mod` plus minimal
version selection. `go.sum` says "if you use this version, its hash must be this"
— nothing about which version you use. An audit that calls `go.sum` a lockfile
will mis-explain every reproducibility question that follows.

### Verification

```bash
# Verify downloaded modules in the cache still match their go.sum hashes
go mod verify
# -> "all modules verified", or a list of mismatches

# Show what a build would fetch, without mutating go.mod/go.sum
go list -mod=readonly -m -json all
```

`go mod verify` checks the **local module cache** against `go.sum`. It detects a
tampered or corrupted cache. It does not re-fetch from upstream, and it does not
prove that `go.sum` itself is correct — that is what the checksum database did
when the entries were first written.

### Failure modes

| Symptom                                       | Cause                              | Response                                    |
|-----------------------------------------------|------------------------------------|---------------------------------------------|
| `go mod verify` reports a mismatch            | Module cache modified or corrupted | **P1 finding.** Report it; do not "fix" it by clearing the cache mid-audit — that destroys the evidence |
| `checksum mismatch` / `SECURITY ERROR` on fetch | Upstream content differs from the recorded hash | Stop. This is either a moved tag or a substituted artifact. Investigate before proceeding |
| `missing go.sum entry`                        | `go.mod` requires a module `go.sum` doesn't cover | The tree is untidy; report it. Remediation is `go mod tidy`, which the audit emits rather than runs |

### Practices

1. **Commit `go.sum`.** Without it every build re-derives trust from scratch.
2. **Review `go.sum` diffs in PRs.** New entries mean new code entering the build.
3. **Never hand-edit `go.sum`.** A hand-edited entry is indistinguishable from an
   attacker-edited one.

---

## 3 Checksum Database and Proxy Configuration

### The variables that exist

| Variable     | Controls                                                        |
|--------------|-----------------------------------------------------------------|
| `GOPROXY`    | Where modules are fetched from. Comma-separated; `direct` means straight from the source repo |
| `GOSUMDB`    | Which checksum database to consult. `off` disables checksum-database verification entirely |
| `GONOSUMDB`  | Glob patterns exempt from checksum-database lookup              |
| `GONOPROXY`  | Glob patterns fetched directly, bypassing the proxy             |
| `GOPRIVATE`  | Shorthand that sets the default for both `GONOPROXY` and `GONOSUMDB` |
| `GOINSECURE` | Glob patterns allowed over plain HTTP. Does **not** disable checksum-database validation |
| `GOVCS`      | Which version-control tools may be used for which module prefixes |
| `GOFLAGS`    | Default flags for every `go` command                            |

```bash
# Default
GOPROXY=https://proxy.golang.org,direct
GOSUMDB=sum.golang.org

# Corporate proxy first, public fallback, then direct
GOPROXY=https://goproxy.company.com,https://proxy.golang.org,direct

# Corporate proxy only, no egress
GOPROXY=https://goproxy.company.com
```

### GOPROXY does not control integrity

A frequent and consequential error is to treat `GOPROXY=direct` as "unverified".
It is not: `GOSUMDB` still applies, and `go.sum` is still enforced. What changes
is availability and privacy.

| Configuration              | Integrity                              | Privacy                          | Availability            |
|----------------------------|----------------------------------------|----------------------------------|-------------------------|
| `proxy.golang.org`         | Full — sumdb + go.sum                  | Module paths visible to the proxy| Immutable cache; third-party dependency |
| Corporate proxy            | Full — sumdb + go.sum                  | Internal                         | Self-managed            |
| `GOPROXY=direct`           | Full — sumdb + go.sum                  | Source repos see your fetches    | Breaks if a tag is deleted |
| `GOSUMDB=off`              | **go.sum only** — no first-use verification | n/a                         | n/a                     |
| `GONOSUMDB`/`GOPRIVATE` match | **go.sum only**, for matching paths | n/a                              | n/a                     |

The row that actually weakens integrity is `GOSUMDB=off`, not `GOPROXY=direct`.
With the sumdb off, `go.sum` entries added from then on are trusted on first use
with nothing to check them against.

### 3.4 Obsolete names that do nothing

These appear widely in older documentation. They are **not** Go environment
variables; setting them has no effect, and an audit that reports them as a
misconfiguration is reporting noise:

| Name            | Reality                                                     |
|-----------------|-------------------------------------------------------------|
| `GONOSUMCHECK`  | From the `vgo` prototype. Never shipped. Ignored entirely    |
| `GONOSUMDB=*` as "disable everything" | Real variable, but scoped to path globs; the switch to disable verification is `GOSUMDB=off` |
| `GOPROXY=off`   | Real, but means "no network at all" — fails unless every module is already cached, not "no verification" |

Verify against the running toolchain rather than from memory:

```bash
go env GOPROXY GOSUMDB GOPRIVATE GONOPROXY GONOSUMDB GOFLAGS GOVCS
```

Report the values this returns. An empty `GOPRIVATE` in a repo that imports
internal modules is a genuine finding; a missing `GONOSUMCHECK` is not.

---

## 4 Private Module Handling

```bash
# One setting covers both proxy bypass and sumdb bypass
GOPRIVATE=*.company.com,github.com/company/*

# Or set them separately when the two lists differ — e.g. route private
# modules through an internal proxy while still skipping the public sumdb
GONOPROXY=none
GONOSUMDB=*.company.com,github.com/company/*
```

### Why it matters

Without `GOPRIVATE`, for every internal module the toolchain will:

- request it from the public proxy. The `go` command transmits no personally
  identifying information, but it does transmit **the full module path** in the
  request URL — leaking internal service and project names.
- query the checksum database at `$GOSUMDB/lookup/$module@$version` — for example
  `https://sum.golang.org/lookup/golang.org/x/text@v0.3.2`. What leaks here is
  again **the module path and version in the URL**, not a locally-computed hash.
- then fail the fetch, because neither service can reach a private repository.

Two corrections to the folklore around this:

1. **The client does not upload your code's hash.** It asks the database for a
   `go.sum` line by name. The disclosure is the name and version, which is
   usually the sensitive part anyway.
2. **A genuinely unreachable private module does not end up in the transparency
   log.** sum.golang.org can only record a checksum for a module it can fetch;
   for a private repository the lookup simply fails. The lasting exposure is the
   request itself reaching a third party, not a permanent public record of your
   module. Do not overstate this — the fix is the same either way.

The disclosure happens *before* the failure, so the error message is not your
first warning. A `GOPRIVATE` pattern that covers only some internal prefixes
leaks exactly the ones it misses — and a **typo** leaks too: with a private proxy
first and a public fallback, `go mod download corp.example.com/secret-product/typo@latest`
falls through to the public proxy on a 404, carrying `secret-product` in the URL.

### Authentication

`.netrc` for HTTPS. **`.netrc` performs no variable expansion** — a literal
`${GITHUB_TOKEN}` in the file is sent as those characters, and the auth failure
that follows is opaque. Generate the file with the value already substituted, and
restrict its mode:

```bash
umask 077
cat > "$HOME/.netrc" <<EOF
machine github.com
  login x-access-token
  password ${GITHUB_TOKEN}
EOF
# The heredoc is unquoted, so the shell expands the token before writing.
```

Or route over SSH instead of embedding a token at all:

```bash
git config --global \
  url."ssh://git@github.com/company/".insteadOf "https://github.com/company/"
```

### CI checklist

```bash
export GOPRIVATE="github.com/company/*"
# and ensure the runner holds credentials for those repos
```

An audit should report whether `GOPRIVATE` covers every internal module prefix
actually present in `go.mod` — a partial pattern leaks the modules it misses.

---

## 5 Retracted and Deprecated Modules

Two module-level signals that most audits miss entirely, because neither is a
CVE and neither shows up in `govulncheck`:

```bash
# Retractions and deprecations for the modules you use
go list -mod=readonly -m -u -retracted all

# Machine-readable
go list -mod=readonly -m -u -json all | jq 'select(.Retracted != null or .Deprecated != "")
  | {Path, Version, Retracted, Deprecated}'
```

- **Retracted** — the author published a `retract` directive marking this exact
  version as broken or unsafe. Using a retracted version is nearly always a
  defect, and the author has told you so in-band. Treat as P2, or higher when the
  retraction rationale describes a security issue.
- **Deprecated** — the module's `go.mod` carries a `// Deprecated:` comment on the
  module directive. The module still works; the author has stopped supporting it.
  Treat as P3 with a migration note.

Both fields are documented members of `go list -m`'s `Module` struct, alongside
`Dir`, `Sum`, and `GoModSum`.

---

## 6 Deleted Tag Recovery

### Symptom

```
go: github.com/foo/bar@v1.2.3: reading github.com/foo/bar/go.mod at revision v1.2.3:
  unknown revision v1.2.3
```

An upstream tag was deleted or moved. Builds that worked yesterday now fail.

### Recovery

**1. Try the proxy — it caches immutably.**

```bash
GOPROXY=https://proxy.golang.org GOFLAGS=-mod=mod go mod download github.com/foo/bar
```

Tag deletion upstream does not remove an already-cached version from the proxy.
This alone resolves most occurrences.

**2. If the proxy does not have it, locate the commit.**

```bash
git ls-remote https://github.com/foo/bar | grep -i 'v1\.2'
go get github.com/foo/bar@<commit-sha>
```

The result is a pseudo-version pinned to that commit.

**3. Bridge with `replace` while you plan the real fix.**

```go
// go.mod — both sides carry a version when redirecting a specific one
replace github.com/foo/bar v1.2.3 => github.com/yourfork/bar v1.2.3-restored
```

A `replace` used this way is a temporary bridge. Record the reason and the
removal condition next to it (an issue link, not a bare marker comment), and give
it an owner — undocumented `replace` directives outlive everyone who understood
them.

**4. Move to a version that exists.**

```bash
go get github.com/foo/bar@v1.3.0
```

### Prevention

1. **Keep `proxy.golang.org` (or a mirror) in `GOPROXY`** — immutable caching is
   the single most effective mitigation
2. **`go mod vendor`** for builds that must survive total upstream loss
3. **Alert on `go mod download` failures in CI** — the first failure is the
   warning
4. **Commit `go.sum`** — it pins content even when a tag is repointed

---

## 7 SBOM Generation

An SBOM inventories every component in the artifact. Required for regulatory
regimes (US EO 14028, EU CRA), and — more usefully day to day — it answers "are
we affected?" in minutes when a new CVE lands.

```bash
# EMIT — remediation, not an audit probe: this installs a tool and
# writes a file. The audit hands these to a human; it never runs them.
go install github.com/CycloneDX/cyclonedx-gomod/cmd/cyclonedx-gomod@latest
cyclonedx-gomod mod -json -output sbom.json

# Ad-hoc module inventory (not a standard SBOM, but scriptable)
go list -mod=readonly -m -json all > modules.json
```

Note that `govulncheck -format json` also emits an `SBOM` message describing what
it scanned — useful for proving that the scan covered what you think it did.

An SBOM should carry, per component: module path and version, licence identifier
(SPDX), checksum from `go.sum`, direct-vs-transitive classification, and the Go
toolchain version used for the build.

---

## 8 Supply Chain Threat Model

| Vector                 | Example                                       | Mitigation                                    |
|------------------------|-----------------------------------------------|-----------------------------------------------|
| Typosquatting          | `github.com/g0lang/net` (zero for "o")        | Review every new direct dependency by hand    |
| Account takeover       | Maintainer credentials compromised, new version published | `go.sum` protects existing versions; nothing protects you from a *new* version you choose to adopt |
| Dependency confusion   | Internal module name also exists publicly     | `GOPRIVATE` / `GONOPROXY`                     |
| Tag manipulation       | Tag repointed to a different commit           | `go.sum` hash mismatch on fetch               |
| Malicious minor update | Backdoor introduced in a patch release        | Review `go.mod`/`go.sum` diffs; pin versions; delay adoption |
| Abandoned library      | No maintainer, vulnerabilities unfixed        | Track deprecation (S5) and last-commit dates  |
| Build-tool dependency  | Code generator or linter with repo write access | Audit the tools too; they are rarely in the shipped binary but they run in CI |

Note where `go.sum` does and does not help. It defends the integrity of a version
you have already accepted. It does not evaluate a version you are about to accept
— that is what dependency review is for.

### Defense checklist

1. `go.sum` committed; `go mod verify` in CI
2. `GOSUMDB` on (not `off`); `GOPRIVATE` covering every internal prefix
3. `GOPROXY` pointing at an immutable cache
4. Minimal direct dependencies — every one is an ongoing commitment
5. `govulncheck` on a schedule, not only on change (the database moves; your code does not)
6. `go.mod`/`go.sum` diffs reviewed in every PR, by a human
7. SBOM produced per release and retained
8. Every `replace` directive documented with a rationale and a removal condition
9. Retracted and deprecated modules tracked (S5)
