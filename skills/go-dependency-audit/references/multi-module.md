# Multi-Module Repositories

> Load this whenever gate 1 finds more than one `go.mod`. SKILL.md S2.3 states
> the rule; this file is the procedure.

The failure this exists to prevent: running the gate sequence once in the
repository root, auditing exactly one module, and presenting the result as a
repository-wide verdict. Every command below is scoped to a module on purpose.

## Table of Contents
1. Enumerate and Classify
2. Snapshot Before Any `go` Command
3. Run the Gates Per Module
4. `go.work`: Which Resolution Did You Audit?
5. Aggregating Findings Without Inventing Them
6. Reporting

---

## 1 Enumerate and Classify

Enumerate with the **Glob tool**, not a shell command — `Glob("**/go.mod")` is
already what gate 1 uses, it needs no allow-listing, and it cannot delete
anything the way a mis-typed `find -exec` can. Discard hits under `vendor/` and
`testdata/`.

For each remaining hit, record the directory and the declared module path:

```bash
go mod edit -json "$dir/go.mod" | jq -r .Module.Path
```

Then classify each one, because they are not equally in scope:

| Kind | How to tell | Audit it? |
|---|---|---|
| Sibling modules | Directories not nested inside another module | Yes — each independently |
| Nested module | A `go.mod` inside another module's directory tree | Yes, separately — but **it is excluded from the parent's build**, so never report it as a parent dependency |
| Vendored / testdata copy | Under `vendor/` or `testdata/` | No — not part of any build list |
| Tool module | Exists only to pin build tooling (often `tools/`) | Yes, but mark it: its dependencies are not in any shipped artifact |

A nested `go.mod` is the trap. The Go toolchain stops descending at a nested
module boundary, so the parent's `go list -m all` will not include it, and a
finding there is not a finding for the parent.

---

## 2 Snapshot Before Any `go` Command

The read-only proof (SKILL.md S1.3 rule 3) has to cover every manifest, not just
the root pair:

```bash
git status --porcelain -- '**/go.mod' '**/go.sum'
```

Record this once at the start and once at the end. If any line differs, a probe
mutated a manifest — say so in S9.8 rather than reporting the post-mutation
state.

---

## 3 Run the Gates Per Module

Use `-C <dir>` rather than changing directory: it keeps each invocation
self-describing in the report and stops a stale cwd leaking into a later command.

**`-C` must come before every other flag**, and the only placement correct for
every `go` subcommand is immediately after `go`:

```bash
go -C "$dir" mod edit -json                      # gate 3
go -C "$dir" list -mod=readonly -m all           # gate 4
go -C "$dir" mod verify                          # gate 6
go -C "$dir" mod tidy -diff                      # gate 10 (Go 1.23+)
govulncheck -C "$dir" ./...                      # gates 7-8

# gate 9 — go-licenses has no -C; it must be run FROM the module directory
( cd "$dir" && GOWORK=off go-licenses check ./... \
    --disallowed_types=forbidden,unknown )
```

**`go-licenses` is the exception: it takes no `-C`, and a path pattern will not
substitute for one.** Run from the repository root against a nested module, the
documented-looking form fails outright:

```
# WRONG — not a licence finding, a usage error (exit 1)
$ go-licenses check ./worker/... --disallowed_types=forbidden,unknown
pattern ./worker/...: directory prefix worker does not contain main module
or its selected dependencies
```

The package pattern is resolved against the **current** main module, and a nested
module is not part of it. Use a subshell so the parent's cwd is untouched, and
`GOWORK=off` so the workspace does not silently change resolution.

Both spellings can exit 1, so **do not gate on the exit code alone** — this is
the skill's own "exit 1 is not a result" rule applied to `go-licenses`. Read the
message: `directory prefix … does not contain main module` is a broken
invocation (fix the command), whereas `Did not find license for library …` is a
genuine finding (record it).

Getting this wrong is a hard error, not a silent misbehaviour — measured on
Go 1.26.1 from outside the module directory:

```
# WRONG — -C is not the first flag, so the go command refuses (exit 2)
$ go mod tidy -diff -C "$dir"
invalid value "…" for flag -C: -C flag must be first flag on command line
$ go list -mod=readonly -C "$dir" -m all
invalid value "…" for flag -C: -C flag must be first flag on command line

# RIGHT — -C first among flags; the second form works for every subcommand
$ go mod tidy -C "$dir" -diff
$ go -C "$dir" mod tidy -diff
```

Note the test that actually proves it: run from a *different* directory. Running
`-C "$dir"` while already inside `$dir` succeeds for the wrong reason and tells
you nothing. `govulncheck` has its own `-C` and is not bound by the go-command
rule, but `govulncheck -C "$dir" ./...` is the consistent spelling anyway.

**Each module carries its own gate outcomes and its own degradation modes.** One
module missing `go.sum` puts *that module* in `no-integrity`; it says nothing
about the others. A per-module table in the report is the only honest shape:

| Module | Gate 4 | Gate 5 | Gates 7-8 | Gate 9 | Modes |
|---|---|---|---|---|---|
| `./` | pass | pass | pass | pass | — |
| `./worker` | pass | N/A (all `replace`d) | pass | DEGRADE | `no-license` |

---

## 4 `go.work`: Which Resolution Did You Audit?

A workspace changes what the toolchain selects. With `go.work` active, the `use`
set is resolved together, so a module can build against a version that differs
from what it resolves to on its own — which is what a consumer of that module
would actually get.

Audit **per module with the workspace disabled**:

```bash
GOWORK=off govulncheck -C "$dir" ./...
GOWORK=off go -C "$dir" list -mod=readonly -m all
```

That gives the versions each module ships with. Then, if the workspace matters
to the question being asked, run once more with the workspace active and report
the delta — a dependency that is vulnerable in workspace mode but not standalone
(or vice versa) is a real finding about the developer environment.

**Always state which mode produced the numbers.** "We scanned the repo" is not an
answer when the two modes disagree.

Whether `go.work` should be committed is a separate question — see SKILL.md
S5.5 item 23.

---

## 5 Aggregating Findings Without Inventing Them

Modules resolve independently. That makes naive summing wrong in both
directions.

| Situation | Correct report |
|---|---|
| Same module, same version, vulnerable, used by 3 modules | **One** finding, affecting 3 modules. Fixing it is one upgrade per module, but it is one vulnerability |
| Same module at different versions across modules | **Separate version-scoped records**, but a finding **only** for versions inside the affected range. A module already on the fixed version is a record, not a finding |
| A vulnerability reachable (E1) in one module and only required (E3) in another | Two entries at two evidence tiers. Never report the higher tier repo-wide |
| Licence finding in a tool-only module | Report it, flagged as not shipped — a `restricted` licence in a build tool is a different conversation |

Deduplicate by `(module path, version, GO-ID)`, and keep the per-module
attribution. A repository total is only meaningful if you also say that modules
resolve independently — otherwise a reader will assume one upgrade fixes it
everywhere.

**Record ≠ finding.** Keeping one record per `(module, version)` is how you avoid
collapsing two different states into one row; it is *not* a licence to count both
as vulnerabilities. Only a version inside the advisory's affected range produces
a finding. Worked example, matching the e2e fixture:

| Module | Requires | In affected range? | Reported as |
|---|---|---|---|
| `./root` | `x/net v0.15.0` | yes (fixed in v0.17.0) | **1 finding**, GO-2023-2102, attributed to `./root` |
| `./sibling` | `x/net v0.17.0` | no | a version-scoped **record**, no finding |
| `./worker` | — | n/a | nothing |

Repository total: **one** vulnerability, not two — and not "one shared finding
across two modules" either, since only one module is affected. Reporting "2
vulnerabilities" double-counts a dependency that is already fixed in half the
repo; reporting "1 vulnerability, repo-wide" loses which module must upgrade.

---

## 6 Reporting

S9.1 must list every module discovered, with its directory and module path.
S9.8 must name every module that was **not** audited and why. The scorecard is
computed per module; a repository-level verdict is the worst outcome across
modules, stated as such — never an average, which would let a clean module mask
a failing one.

If only a subset was audited (because the user asked about one service, say),
that is fine — but the report must say so in its first section, not imply
repository coverage it does not have.
