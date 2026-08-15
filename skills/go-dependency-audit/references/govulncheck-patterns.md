# govulncheck Patterns

> **Verified against `govulncheck v1.1.4`** (`golang.org/x/vuln`). The output
> samples below are taken from govulncheck's own golden fixtures
> (`internal/scan/testdata/*.txt`), not paraphrased. Run `govulncheck -version`
> and re-check the flag set before relying on anything here; flags have been
> added and removed across releases.

## Table of Contents
1. Flag Surface (what actually exists)
2. Execution Modes
3. Scan Levels and Evidence Tiers
4. Reading Text Output
5. Reading JSON Output
6. Exit Codes
7. CI Integration
8. Triage Decision Tree
9. Limits of Reachability Analysis
10. Companion Tools

---

## 1 Flag Surface (what actually exists)

`govulncheck -h` on v1.1.4:

```
Usage:
	govulncheck [flags] [patterns]
	govulncheck -mode=binary [flags] [binary]

  -C dir      change to dir before running govulncheck
  -db url     vulnerability database url (default "https://vuln.go.dev")
  -format     'text', 'json', 'sarif', or 'openvex'   (default 'text')
  -json       output JSON (legacy alias for -format=json)
  -mode       'source', 'binary', or 'extract'        (default 'source')
  -scan       'module', 'package', or 'symbol'        (default 'symbol')
  -show       comma-separated: 'traces','color','version','verbose'
  -tags       comma-separated list of build tags
  -test       analyze test files (source mode only, default false)
  -version    print version information
```

**Flags that do not exist.** These appear in older blog posts and in
LLM-generated snippets; all three are usage errors (exit code 2):

| Not a flag              | What people mean                                              |
|-------------------------|---------------------------------------------------------------|
| `-go=1.21`              | There is no Go-version flag. Source mode uses the toolchain on `PATH`; select it with `GOTOOLCHAIN` or by invoking a specific `go`. |
| `-mode=query`           | `-mode` accepts only `source`, `binary`, `extract`. There is no offline version-lookup mode. |
| `-exclude` / `-ignore`  | No suppression flag. Filter downstream from `-format json`, or use `-format sarif` and suppress in the consuming tool. |

---

## 2 Execution Modes

### Source mode (primary)

```bash
# Scan every package in the module, tracing the call graph
govulncheck ./...

# Scan one package tree
govulncheck ./cmd/server/...

# Include test files (excluded by default)
govulncheck -test ./...

# Constrain to the build tags you actually ship
govulncheck -tags=prod,linux ./...
```

Source mode links the call graph from your entry points to the vulnerable
symbol. A dependency can contain a vulnerability that your code never reaches;
source mode is what tells the two cases apart.

**`-test` defaults to false.** Test-only dependencies are not analyzed unless you
ask. If you are auditing a library whose vulnerable surface is exercised only in
tests, `govulncheck ./...` will not see it.

### Binary mode

```bash
# The argument is a COMPILED BINARY, not a package pattern or source directory.
go build -o ./bin/server ./cmd/server
govulncheck -mode=binary ./bin/server
```

Passing a source directory (`govulncheck -mode=binary ./cmd/server`) is a usage
error. Binary mode reads the symbol table of a built artifact, which makes it the
right tool for:

- Third-party binaries with no source
- Verifying what is actually linked, versus what `go.mod` declares
- CI pipelines that build first and scan the artifact

Binary mode cannot produce call traces. Treat every binary-mode finding as
`no-reachability` mode: you learn *which* symbols are present, not whether a
request can reach them.

One further degradation to record: where symbol information cannot be extracted
from the binary at all — stripped builds, some cgo-heavy artifacts — govulncheck
falls back to reporting vulnerabilities for **every module the binary depends
on**. That output looks like a long list of findings but carries only E3
Required evidence.

### Extract mode

```bash
# Reduce a binary to the minimum govulncheck needs, then scan the blob later
govulncheck -mode=extract ./bin/server > server.blob
govulncheck -mode=binary server.blob
```

The blob is typically much smaller than the binary and is consumed by
`-mode=binary`. Its contents and representation are explicitly not a stable
interface — do not parse it. Useful when the machine holding the binary cannot
reach the vulnerability database, or when the binary itself cannot leave its
environment.

---

## 3 Scan Levels and Evidence Tiers

`-scan` sets how deep the analysis goes, and therefore what counts as a finding.

| `-scan`   | Reports                                        | Evidence tier |
|-----------|------------------------------------------------|---------------|
| `symbol`  | Vulnerable symbols reachable in the call graph  | E1 Called     |
| `package` | Affected packages you import                    | E2 Imported   |
| `module`  | Affected modules you require                    | E3 Required   |

`symbol` is the default and is a superset — a symbol-level scan still reports the
package- and module-level findings it did not manage to link to a call path,
under separate result sections.

**Lowering `-scan` forfeits reachability.** `-scan module` is fast and needs no
build, which makes it attractive for a broken or partially-vendored tree — but a
finding from it says only "you require an affected version". Never report such a
finding as reachable, and never report the absence of one as unreachable.

---

## 4 Reading Text Output

Findings are grouped into three sections; the section name is the evidence tier.

### E1 — symbol reachable

```
=== Symbol Results ===

Vulnerability #1: GO-0000-0001
    Third-party vulnerability
  More info: https://pkg.go.dev/vuln/GO-0000-0001
  Module: golang.org/vmod
    Found in: golang.org/vmod@v0.0.1
    Fixed in: golang.org/vmod@v0.1.3
    Platforms: amd
    Example traces found:
      #1: main.main calls vmod.Vuln

Your code is affected by 1 vulnerability from 1 module.
This scan found no other vulnerabilities in packages you import or modules you
require.
Use '-show verbose' for more details.
```

Add `-show traces` for full call stacks instead of the one-line example.

### E2 — package imported, no reachable symbol

```
=== Package Results ===

Vulnerability #1: GO-0000-0001
    ...
Your code may be affected by 1 vulnerability.
This scan also found 0 vulnerabilities in modules you require.
Use '-scan symbol' for more fine grained vulnerability detection and '-show
verbose' for more details.
```

### E3 — module required only

```
=== Module Results ===

Vulnerability #1: GO-0000-0001
    ...
Your code may be affected by 1 vulnerability.
Use '-scan symbol' for more fine grained vulnerability detection.
```

### Summary lines are the parse target

| Phrase                                                          | Meaning                                   |
|-----------------------------------------------------------------|-------------------------------------------|
| `Your code is affected by N vulnerabilit...`                     | N findings at symbol level (E1)           |
| `Your code may be affected by N vulnerabilit...`                 | Findings at package/module level only     |
| `...but your code doesn't appear to call these vulnerabilities.` | The E2/E3 remainder of a symbol-level scan|
| `No vulnerabilities found.`                                      | Zero findings at every tier               |
| `No other vulnerabilities found.`                                | Closes a section below one that had findings |

**Do not grep for `Your code is NOT affected`.** That string is not emitted by
v1.x. The negative signal is `doesn't appear to call these vulnerabilities`, or
the absence of a `=== Symbol Results ===` section.

### There is no severity in this output

Notice what is absent: no CVSS, no "HIGH"/"CRITICAL" label. The Go vulnerability
database does not publish severity scores, so govulncheck cannot print one. What
you get is the `GO-YYYY-NNNN` ID, aliases, affected range, fixed version, and
`database_specific.review_status` (`REVIEWED` or `UNREVIEWED`).

To obtain a CVSS score you must look up an alias (CVE/GHSA) in an external
database, and you must then cite that database. See SKILL.md S6.1.

---

## 5 Reading JSON Output

```bash
govulncheck -format json ./... > out.json
```

The output is a **stream of concatenated JSON objects**, not an array and not one
object per line — objects are pretty-printed across multiple lines. Every `jq`
invocation over it needs `-s`/`--slurp`.

Message kinds: `config` (always first), `progress`, `SBOM`, `osv` (full entry),
`finding`.

```json
{"config": {"protocol_version":"v0.1.0","scanner_name":"govulncheck","scan_level":"symbol"}}
{"osv": {"id":"GO-0000-0001","details":"Third-party vulnerability",
         "affected":[...],"database_specific":{"url":"https://pkg.go.dev/vuln/GO-0000-0001"}}}
{"finding": {"osv":"GO-0000-0001","fixed_version":"v0.1.3",
             "trace":[{"module":"golang.org/vmod","version":"v0.0.1"}]}}
{"finding": {"osv":"GO-0000-0001","fixed_version":"v0.1.3",
             "trace":[{"module":"golang.org/vmod","version":"v0.0.1",
                       "package":"golang.org/vmod","function":"VulnFoo"},
                      {"module":"golang.org/main","version":"v0.0.1",
                       "package":"golang.org/main","function":"main"}]}}
```

Two properties that break naive counting:

1. **`trace` runs innermost-first.** `trace[0]` is the vulnerable frame; the last
   element is your entry point.
2. **One OSV yields several findings, at different tiers.** The example above has
   `GO-0000-0001` twice: once module-only (E3) and once with a symbol trace (E1).
   Counting `findings` counts the same vulnerability more than once.

### Deriving evidence tiers

Classify by the shape of `trace[0]`, then subtract higher tiers so each OSV is
counted once at its strongest evidence:

```bash
govulncheck -format json ./... > out.json

jq -s '
  [.[].finding // empty] as $f
  | ([$f[] | select(.trace[0].function != null) | .osv] | unique) as $e1
  | ([$f[] | select(.trace[0].function == null and .trace[0].package != null) | .osv]
       | unique - $e1) as $e2
  | ([$f[] | select(.trace[0].package == null) | .osv] | unique - $e1 - $e2) as $e3
  | {e1_called: $e1, e2_imported: $e2, e3_required: $e3}
' out.json
```

The scan level that produced those tiers comes from the `config` message, which
is always first in the stream — record it, because an `e1_called` of `[]` means
something quite different under `-scan module` than under `-scan symbol`:

```bash
jq -rs '[.[].config // empty | .scan_level] | first' out.json
```

`$e1` is what a symbol-level scan proved reachable. `$e2` and `$e3` are the
remainder — real, tracked, but not demonstrated to be callable.

---

## 6 Exit Codes

| Code | Meaning                                                |
|------|--------------------------------------------------------|
| `0`  | Scan completed, no findings **at the scan level**       |
| `1`  | The scan itself failed (package load error, DB unreachable, bad path) |
| `2`  | Invalid usage — unknown flag or wrong argument shape    |
| `3`  | Scan completed and found vulnerabilities at the scan level |

Two rules that follow:

- **Exit 1 is not a clean scan.** It is *no* scan. Anything derived from it must
  be marked `no-cve` degraded — never reported as "no vulnerabilities found".
- **`-format json`, `-format sarif`, and `-format openvex` always exit 0**,
  whatever they found. This is documented behavior, not a bug: those formats are
  meant to be consumed by a downstream tool that makes the pass/fail decision. A
  CI job that scans with `-json` and gates on `$?` can never fail.

---

## 7 CI Integration

### GitHub Actions

```yaml
- name: govulncheck
  uses: golang/govulncheck-action@v1
  with:
    go-version-file: go.mod
    go-package: ./...
```

### Generic CI script — gate on the text-mode exit code

The simplest correct gate. Text mode already encodes the decision:

```bash
#!/usr/bin/env bash
set -uo pipefail          # NOT -e: exit 3 is a result, not a crash

govulncheck ./... | tee govulncheck.txt
rc=${PIPESTATUS[0]}

case "$rc" in
  0) echo "clean" ;;
  3) echo "FAIL: vulnerabilities reachable at scan level"; exit 1 ;;
  *) echo "FAIL: scan did not complete (rc=$rc) — status UNKNOWN"; exit 1 ;;
esac
```

`set -e` would abort on exit 3 before the `case` runs, losing the distinction
between "found vulnerabilities" and "scan broke" — the one distinction that
matters most.

### Report-plus-gate — JSON for the artifact, tiers for the decision

Use this when you want to fail only on reachable findings and still publish a
full report:

```bash
#!/usr/bin/env bash
set -uo pipefail

govulncheck -format json ./... > govulncheck.json
rc=$?
if [ "$rc" -ne 0 ]; then
  echo "FAIL: scan did not complete (rc=$rc)"; exit 1   # json mode: 0 unless broken
fi

CALLED=$(jq -s '[.[].finding // empty
                 | select(.trace[0].function != null) | .osv] | unique | length' \
             govulncheck.json)
OTHER=$(jq -s '[.[].finding // empty
                | select(.trace[0].function == null) | .osv] | unique | length' \
            govulncheck.json)

echo "reachable(E1)=$CALLED  other(E2+E3)=$OTHER"
[ "$CALLED" -gt 0 ] && { echo "FAIL: $CALLED reachable"; exit 1; }
exit 0
```

Note `jq -s`. Without it, `jq` evaluates the filter once per object in the stream
and prints one number per object — `$CALLED` becomes a multi-line string such as
`0 0 0 1`, and `[ "$CALLED" -gt 0 ]` fails with "integer expression expected".

---

## 8 Triage Decision Tree

```
govulncheck finding
  |
  +-- Which result section?
  |     |
  |     +-- Symbol Results (E1 Called)
  |     |     +-- fix version exists AND path reaches a network-facing entry -> P0
  |     |     +-- otherwise                                                  -> P1
  |     |
  |     +-- Package Results (E2 Imported)                                    -> P2
  |     +-- Module Results  (E3 Required)                                    -> P3
  |
  +-- Modifiers (apply, then state the reason)
        +-- no fix version           -> escalate one; remediation is a control, not a bump
        +-- review_status UNREVIEWED -> hold tier; absence of a symbol finding proves nothing
        +-- -scan was not 'symbol'   -> no-reachability mode; report the tier obtained
        +-- binary mode              -> no-reachability mode
        +-- test-only (confirm with `go mod why -m`) -> de-escalate one
        +-- reflection / unsafe / plugin in the path -> reachability unproven; hold tier
```

CVSS enters this tree at exactly one place: nowhere. If a score has been looked
up from a named external database it may be *reported* alongside, but it does not
move the priority — the evidence tier does.

---

## 9 Limits of Reachability Analysis

govulncheck documents its own limitations. Reachability is a **static**
approximation, and it errs in both directions:

- **Calls through `reflect` are invisible.** Vulnerable code reached only via
  reflection is not reported in source mode. Absence of an E1 finding is not
  proof of unreachability.
- **`unsafe` and linker directives** can defeat the analysis similarly.
- **Function pointers and interface dispatch are handled conservatively**, which
  can produce false positives and inaccurate call stacks.
- **Plugins and `os/exec`** are outside the graph entirely.

Practical consequence: an E1 finding is strong evidence *for* risk. The lack of
one is weak evidence *against* it. Never write "not affected" — write "no
reachable path found at symbol level".

### Filters that are legitimate

| Situation             | Evidence to gather                                              |
|-----------------------|-----------------------------------------------------------------|
| Test-only dependency  | `go mod why -m <module>` shows only test import paths; re-run with `-test` to confirm the finding appears only then |
| Platform-specific     | The finding's `Platforms:` line does not include your deploy target; confirm with `govulncheck -tags=...` matching the production build |
| Already migrated path | `go list -m all` no longer contains the old module path          |

Each of these de-escalates by one level and must be recorded with its evidence.
None of them permits deleting the finding.

---

## 10 Companion Tools

### trivy (container + filesystem scanner)

```bash
trivy fs --scanners vuln .
trivy fs --severity HIGH,CRITICAL .
```

Version-matching, not call-graph. Noisier than govulncheck, but it covers other
ecosystems (npm, pip) in polyglot repos, and it *does* carry severity data — so
it is a legitimate source for a CVSS number, cited as such.

### nancy (Sonatype OSS Index)

```bash
go list -mod=readonly -json -deps ./... | nancy sleuth
```

Different vulnerability database from vuln.go.dev. Useful as a second opinion;
it may report issues govulncheck does not, and vice versa. Also version-matching
only — no reachability.

### go-licenses

Not a vulnerability scanner. See `references/license-compliance.md`.
