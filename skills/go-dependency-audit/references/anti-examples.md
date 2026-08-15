# Anti-Examples

Worked WRONG/RIGHT pairs for the six failure modes named in SKILL.md S7. The
one-line rule for each lives in SKILL.md and is binding on its own; this file
carries the demonstration.

## Table of Contents
1. AE-1 Assigning a CVSS score govulncheck never emitted
2. AE-2 Turning a licence observation into a legal verdict
3. AE-3 Gating CI on an exit code `-json` always sets to 0
4. AE-4 Rolling back with a command that destroys uncommitted work
5. AE-5 Claiming "no vulnerabilities" from a scan that did not complete
6. AE-6 Treating `+incompatible` as harmless

---

## 1 AE-1: Assigning a CVSS score that govulncheck never emitted

```
# WRONG
Finding: GO-2023-2102 in golang.org/x/net v0.15.0 — CVSS 7.5, P1 High
// govulncheck prints no CVSS. This number was invented, or copied from an
// unstated source, and the priority was derived from the invention.

# RIGHT
Finding: GO-2023-2102 (alias CVE-2023-44487) in golang.org/x/net v0.15.0
  Evidence tier: E1 Called (=== Symbol Results ===)
  Fixed in: v0.17.0 | Review status: REVIEWED | CVSS: not retrieved
  Priority: P1 — reachable symbol with an available fix
```

---

## 2 AE-2: Turning a licence observation into a legal verdict

```
# WRONG
github.com/baz/qux is GPL-3.0. Your binary is GPL-encumbered and you
cannot ship this product. Replace the dependency.
// The obligation depends on distribution, linkage, licence version and
// exceptions, and modification — none of which were checked. This is a
// legal conclusion stated by a tool that examined none of the inputs.

# RIGHT
github.com/baz/qux v1.0.0 — GPL-3.0 (go-licenses type: restricted)
  Reached via: github.com/foo/bar (go mod why -m)
  Linked into a shipped binary: yes (in go list -deps ./cmd/server)
  ESCALATE: legal review required before release.
  Facts legal will need: do we distribute binaries, or operate a network
  service only? Is the dependency modified? Does its licence carry a
  linking exception?
```

---

## 3 AE-3: Gating CI on an exit code that `-json` always sets to 0

```
# WRONG
govulncheck -json ./... > out.json
if [ $? -ne 0 ]; then exit 1; fi
// -json (and -format sarif/openvex) exit 0 even when vulnerabilities are
// found. This gate can never fail.

# RIGHT
# Gate on the text-mode exit code (3 = found at scan level):
govulncheck ./...; rc=$?
[ "$rc" -eq 3 ] && { echo "vulnerabilities found"; exit 1; }
[ "$rc" -ne 0 ] && { echo "scan failed (rc=$rc)"; exit 1; }
# Or keep -json for the report and parse the findings — see
# govulncheck-patterns.md S7.
```

---

## 4 AE-4: Rolling back with a command that destroys uncommitted work

```
# WRONG
go get "$dep@latest" && go mod tidy
go test ./... || git checkout go.mod go.sum   # "rollback"
// git checkout overwrites the worktree copy. Any unstaged go.mod edit the
// developer had in progress is gone, with no reflog entry to recover it.

# RIGHT
# An audit emits the plan; a human runs it from a clean worktree.
git status --porcelain go.mod go.sum   # must be empty before starting
go get "$dep@v1.3.0"
go test ./...                          # on failure: stop and inspect the diff
```

---

## 5 AE-5: Claiming "no vulnerabilities" from a scan that did not complete

```
# WRONG
$ govulncheck ./...
govulncheck: loading packages: ... (exit 1)
"No vulnerabilities found — dependencies are clean."
// Exit 1 is a failed scan. Only exit 0 with "No vulnerabilities found."
// supports that claim.

# RIGHT
# DEGRADED [no-cve]: govulncheck exited 1 (package load failure).
# CVE status is UNKNOWN. This audit cannot assert presence or absence.
```

---

## 6 AE-6: Treating `+incompatible` as harmless

```
# WRONG
require github.com/uber/jaeger-client-go v2.29.1+incompatible
// "It compiles, so it's fine."

# RIGHT
// +incompatible means the module published v2+ tags without a module-aware
// go.mod. The go command therefore treats v2.29.1+incompatible as part of the
// SAME module as v1.x — not as a separate /v2 module. MVS sees it and compares
// it, so `go get -u` may upgrade you across a major version automatically,
// "even though it may break the build" (Go modules reference). Track as P2 with
// a migration plan to a /vN path or an alternative library.
```
