# License Risk Triage

> **This document is not legal advice, and this skill does not determine whether
> a licence is compatible with a project.** Licence obligations turn on facts a
> dependency scanner cannot see — whether you distribute the artifact at all, how
> the code is combined, which licence version applies, whether an exception
> attaches, whether the code was modified, and how the software is deployed.
>
> What this skill produces is an **inventory plus an escalation packet**: what is
> in the build, under which licence, reached through which path, and whether it
> is linked into something you ship. A qualified reviewer decides the rest.
>
> Verified against `go-licenses v2.0.1`.

## Table of Contents
1. What This Skill Decides, and What It Does Not
2. The Scanner's Classification Vocabulary
3. Scanning with go-licenses
4. Facts That Determine the Answer
5. Linked vs. Merely Required
6. Escalation Packet Format
7. Findings That Are Objective
8. When go-licenses Is Unavailable

---

## 1 What This Skill Decides, and What It Does Not

| The skill reports (objective)                          | A reviewer decides (not objective)          |
|--------------------------------------------------------|---------------------------------------------|
| Which modules are in the build graph                    | Whether an obligation has been triggered    |
| The licence identifier each scanner assigned            | Whether the licence permits your use        |
| The scanner's risk classification, named as such        | Whether two licences may be combined        |
| Whether a LICENSE file was found at all                 | What "derivative work" covers here          |
| Which direct dependency pulls each module in            | Whether an exception clause applies         |
| Whether the module is linked into a shipped binary      | What must be disclosed, and to whom         |

Two failure modes to avoid, in both directions:

- **Over-claiming.** "This dependency is GPL, so you cannot ship this product" is
  a legal conclusion drawn without examining distribution, linkage, licence
  version, exceptions, or modification. It is also frequently wrong: copyleft
  licences place conditions on distribution, they do not prohibit commercial use.
- **Under-claiming.** "The scanner flagged it, so nothing to do here" wastes the
  finding. Every restricted / reciprocal / forbidden / unknown classification
  produces an escalation packet (S6), even when the auditor believes it is fine.

---

## 2 The Scanner's Classification Vocabulary

`go-licenses` assigns every dependency one of seven types. Reporting in the
tool's own vocabulary keeps the output auditable and stable across releases —
and keeps the skill from inventing a taxonomy of its own.

| Type            | Examples (as mapped by go-licenses v2.0.1)          |
|-----------------|------------------------------------------------------|
| `unencumbered`  | Unlicense, CC0-1.0, BSD-0-Clause                     |
| `permissive`    | assorted very lenient licences                       |
| `notice`        | MIT, Apache-2.0, BSD-2-Clause, BSD-3-Clause, ISC     |
| `reciprocal`    | MPL-1.0/1.1/2.0, EPL-1.0/2.0                         |
| `restricted`    | GPL-1.0/2.0/3.0, LGPL-2.0/2.1/3.0                    |
| `forbidden`     | AGPL-1.0, AGPL-3.0, CC-BY-NC*, CC-BY-ND*             |
| `unknown`       | no licence file found, or text the classifier could not match |

Three things to understand about this table before quoting it:

1. **`forbidden` is a tool default, not a legal fact.** It encodes the policy
   defaults of the tool's authors. AGPL is a valid licence with terms that can be
   satisfied; the classification means "this organisation's default policy says
   escalate", not "this is illegal". Report it as
   `go-licenses type: forbidden`, never as `forbidden`.
2. **The classifier does not model exceptions.** `GPL-2.0-with-classpath-exception`
   maps to `restricted` exactly like plain `GPL-2.0`, even though the exception is
   the entire point of that licence. If a finding involves an exception clause,
   the classification is too coarse to act on — say so.
3. **`unknown` is not "probably fine".** It means the tool could not identify the
   terms. See S7.

`go-licenses check` with no flags disallows `forbidden` and `unknown`. That
default is a reasonable *starting* policy — record it as the policy you applied,
so a reader can tell an unset default from a deliberate choice.

---

## 3 Scanning with go-licenses

### Availability check

```bash
go-licenses help
```

Two traps in this one probe:

- **There is no `version` subcommand.** `go-licenses version` fails whether or
  not the tool is installed, turning a working tool into a spurious `no-license`
  degradation.
- **`go-licenses --help` prints only the logging flag set** (`-alsologtostderr`,
  `-v`, `-vmodule` …) and never lists the commands. Use `go-licenses help`, or a
  bare `go-licenses`, both of which print `Available Commands`.

The real surface at v2.0.1 is `check`, `completion`, `csv`, `help`, `report`,
`save`.

### Inventory

```bash
# CSV inventory: module,license_url,license_type
go-licenses report ./...

# Same data via a custom Go template
go-licenses report ./... --template=./licenses.tmpl
```

**Use `report`, not `csv`.** `csv` still exists and still works, but its own help
text reads *"(Deprecated: use report instead)"* and the project README documents
only `check`, `report`, and `save`. `csv` is implemented as `report` with no
template — identical output, deprecated spelling.

Available template fields: `Name`, `Version`, `LicensePath`, `LicenseURL`,
`LicenseName`, and `LicenseText`.

**`report` makes network calls** (a ~20s-timeout HTTP client) to resolve each
`LicenseURL`. In an air-gapped CI runner it is slow and yields `Unknown` URLs. If
URLs come back empty at scale, that is a network symptom, not a licence finding —
do not report it as one. Prefer `check` when you only need the gate.

### Policy gate

```bash
# Allow-list by licence name
go-licenses check ./... \
  --allowed_licenses=MIT,Apache-2.0,BSD-2-Clause,BSD-3-Clause,ISC

# Or deny-list by classification type
go-licenses check ./... --disallowed_types=forbidden,restricted,unknown
```

The two flags are mutually exclusive — passing both is an error. Exit code 0
means every dependency passed the policy you specified; non-zero means at least
one did not, or had no discoverable licence file.

### Attribution bundle

```bash
# EMIT — remediation, not an audit probe: this writes files.
go-licenses save ./... --save_path=./third_party/licenses
```

Notice-type licences (MIT, Apache-2.0, BSD) generally require the licence text
and copyright notice to travel with a distributed artifact. `save` produces that
bundle. Not shipping it is a common, cheap-to-fix finding.

### Scope flags

```bash
--include_tests           # count packages imported only by test code
--ignore <prefix>         # exclude a path prefix; repeatable
```

By default test-only dependencies are excluded, which usually matches what you
ship. State which setting you used — the inventory differs materially.

---

## 4 Facts That Determine the Answer

When a finding escalates, these are the inputs the reviewer will ask for. The
skill's job is to arrive with them already collected.

| Question                          | How to answer it from the repo                                   |
|-----------------------------------|------------------------------------------------------------------|
| Do we distribute the artifact?    | Ship a binary/container/SDK to a third party, or run a service only? Most copyleft obligations attach to distribution. |
| Is it linked into what we ship?   | `go list -deps ./cmd/...` — see S5                                |
| Which licence *version*?          | Read the LICENSE file; "GPL" alone is not an answer               |
| Is there an exception clause?     | Read the file; the classifier does not model these                |
| Did we modify the dependency?     | Any `replace` pointing at a fork, or a vendored copy with local edits |
| Is it a build/test tool only?     | Present in `go.mod` but absent from `go list -deps ./cmd/...`     |
| Is the service network-facing?    | Relevant to AGPL-style network-use clauses                        |
| Which direct dependency pulls it? | `go mod why -m <module>` — this is the module you would replace   |

Notice that most of these are properties of *your deployment*, not of the
dependency. That is exactly why a scanner cannot answer the question.

---

## 5 Linked vs. Merely Required

Go statically links what it compiles, so anything reachable from a `main` package
ends up in the binary. But `go.mod` lists more than that: build tools, code
generators, test-only libraries, and modules required only by other modules'
tests all appear in the graph without entering the artifact.

There are three grades of evidence here, and they are not interchangeable. Use
the strongest one available and **label which one you used**.

**1. Required (weakest).** The module is in the graph. Says nothing about the
artifact.

```bash
go list -mod=readonly -m all
go mod why -m github.com/example/dep     # which direct dep pulls it in
```

**2. Build-dependency evidence.** The package is reachable from a `main` package,
so a build of that command would compile it. Do **not** hard-code `./cmd/...` —
plenty of projects put `main` elsewhere. Discover the entry points first:

```bash
# Every main package in this module, wherever it lives
go list -mod=readonly -f '{{if eq .Name "main"}}{{.ImportPath}}{{end}}' ./...

# Then the build closure of the ones you actually ship
go list -mod=readonly -deps <main-import-path> | sort -u
```

Ask the user which of those commands are shipped. A repo with six `main`
packages of which one is released has one relevant closure, not six.

**3. Binary evidence (strongest).** What a built artifact actually records:

```bash
go version -m ./bin/server
# server: go1.26.1
#   path  example.com/app/cmd/server
#   mod   example.com/app  (devel)
#   dep   github.com/example/dep  v1.4.2  h1:...
```

This is read from the binary's own build info, listing every module version
linked into it — not an inference from the graph.

**Do not write "linked into the shipped binary" when you only ran `go list
-deps`.** That command establishes a build dependency; it does not account for
dead-code elimination, build tags, `-ldflags` trimming, or the possibility that
the artifact you ship was built from a different entry point or configuration.
Report it as *build-dependency evidence*, and say plainly when binary evidence
was not available. A `restricted` dependency present in the build closure is a
materially more urgent finding than one appearing only in `go list -m all`, and
one confirmed by `go version -m` is more urgent still.

---

## 6 Escalation Packet Format

Every `restricted`, `reciprocal`, `forbidden`, or `unknown` classification emits
this block. No verdict, no recommendation to remove — facts and an open question.

```
ESCALATE — legal review
  Module:            github.com/example/dep v1.4.2
  Licence (as read): GPL-3.0        [file: LICENSE, verbatim identifier]
  Scanner type:      restricted     [go-licenses v2.0.1, --disallowed_types default]
  Exception clause:  none observed
  Reached via:       github.com/foo/bar v1.0.0   (go mod why -m)
  Shipping evidence: BUILD-DEPENDENCY — appears in
                     `go list -mod=readonly -deps example.com/app/cmd/server`.
                     Binary evidence (`go version -m`) not collected.
  Modified locally:  no `replace` directive, not vendored
  Distribution:      UNKNOWN to this audit — the reviewer must supply this
  Open question:     Does our distribution model trigger this licence's
                     source-availability condition, and if so what satisfies it?
```

`UNKNOWN to this audit` is a correct and expected value. Guessing it is not.

---

## 7 Findings That Are Objective

Not everything here is a judgment call. These are observations the skill can and
should state plainly.

### No LICENSE file found

`go-licenses` reports `Did not find license for library '<name>'` and fails the
`check` gate. The observation is objective: no grant of rights was located in the
distributed module. Under copyright, rights are not granted by default — so this
is the highest-signal licence finding an audit can produce, and it is worth
raising even when the module is popular and widely used. Escalate; do not
conclude.

### Attribution artifacts missing

Notice-type licences generally require the licence text and copyright notice to
accompany a distributed artifact. If the build ships no `third_party/licenses`
bundle (or equivalent) while `go-licenses report` lists notice-type dependencies,
that is a concrete, mechanically-checkable gap with an obvious remedy.

### Licence changed between versions

A dependency's licence can change on upgrade — this has happened to widely-used
Go modules. Diff it:

```bash
diff <(cat "$(go env GOMODCACHE)/github.com/example/dep@v1.4.2/LICENSE") \
     <(cat "$(go env GOMODCACHE)/github.com/example/dep@v1.5.0/LICENSE")
```

A changed licence on a version bump is a fact, and it is exactly the kind of
change a routine upgrade PR hides.

### Dual-licensed dependency

`MIT OR GPL-3.0` means the recipient chooses. Record which option the project is
relying on; an unrecorded choice is a gap in the compliance record, not a
violation.

---

## 8 When go-licenses Is Unavailable

Enter `no-license` degraded mode and say so. A manual sweep can still produce the
inventory's skeleton — it identifies *presence*, never classification:

```bash
go list -mod=readonly -m -f '{{.Path}} {{.Version}} {{.Dir}}' all | while read -r mod ver dir; do
  [ -d "$dir" ] || continue
  lic=$(find "$dir" -maxdepth 1 \( -iname 'LICENSE*' -o -iname 'COPYING*' \) | head -1)
  if [ -n "$lic" ]; then
    printf '%s\t%s\t%s\n' "$mod" "$ver" "$lic"
  else
    printf '%s\t%s\tNO_LICENSE_FILE_FOUND\n' "$mod" "$ver"
  fi
done
```

`go list -m -f '{{.Dir}}'` gives the real module-cache path directly, rather than
reconstructing it by string-concatenation — module paths with uppercase letters
are `!`-escaped in the cache, so a hand-built path silently misses them and
reports a licence as absent when it is present.

What this fallback can support: "these N modules have no licence file at the
module root". What it cannot support: any classification, any compatibility
statement, or any claim of completeness. Record both in S9.8.
