# git-commit — why the contracts are what they are

**Load this only when maintaining the skill.** `SKILL.md` states the rules an
invocation needs; this file holds the measured evidence behind them, so the
operational instruction stays short and the reasoning is not lost. Every claim
below was reproduced, not assumed. Verified environments are listed at the end.

## Reads fail closed, at every stage

In a pipeline the shell reports the **last** command's status, so `git … | awk`
returned awk's `0` even when git died — and an empty result is indistinguishable
from "nothing found". Injecting a failing `git diff` made `secret-scan.sh` exit 0
with empty stdout while a staged AWS key and a `.pem` went unreported.

Checking git alone was not enough either: with a broken `awk` the scan still
exited 0, having printed only the filename check. Every script now sets
`set -o pipefail` and checks each pipeline, and each failing stage reports itself
by name — two failed stages print two `SCANNER_ERROR` lines.

*Unknown is not none.* `detect-ecosystems.sh` uses empty output to mean "no
ecosystem", which §4 turns into "quality gate: not detected"; a failed read there
would have skipped the gate silently, so it exits 2 instead.

## Paths are read raw, never in git's display form

`--name-only` honours `core.quotePath`, so `源码/模块/配置.py` arrives as
`"\346\272\220…"`. The extension then parses as `py"`: a stage of CJK-named
sources selected **no gate at all**, `*.pem` stopped matching, and a reported
path could not be reopened with `git show`. Path lists now use `-z`; the patch
stream runs under `-c core.quotePath=false`; and §1, §2 and §7 do the same,
because the agent shows those paths to the user and feeds them back to `git add`.

`tr '\0' '\n'` splits a path containing a literal newline. That over-reports
(an extra candidate), which is the safe direction for a scanner and for scope
(extra candidates omit the scope rather than invent one).

## Deletions select their gate

`--diff-filter=d` once excluded them, so `git rm helper.py` alongside a
JavaScript edit selected only the Node gate — while the Python package no longer
imported. Removing a file is the change most likely to break its ecosystem's
build. `--no-renames` additionally makes `foo.py -> foo.txt` show both sides.

## Detection and the redaction cut are separate decisions

One function once did both, so the 20+ character blob rule could only run as a
fallback: `SESSION=<40 chars> password = x` cut at `password` and printed the
session token in full — on the finding line itself, not merely in context.
`detect_at()` decides whether a line is a finding; `cut_at()` takes the earliest
of credential shape, sensitive key, and blob. The blob rule never creates a
finding (every long identifier would become one) but always constrains the cut.

The keyed pattern was also case-sensitive and required `=`, so `"password": "x"`
in JSON and `PASSWORD =` in a properties file were invisible — and, being
undetected, printed verbatim in context. Matching is now case-insensitive over
`:` and `=`, via `tolower()` under `LC_ALL=C` (a locale-aware `tolower` can
change byte length and slide the cut).

Residual risk, stated rather than papered over: a short literal not attached to a
sensitive key is not maskable by shape and will print.

## The awk interval probe

Twelve credential patterns are length-anchored — `AKIA[0-9A-Z]{16}`,
`ghp_…{36}`, `github_pat_…{82}`, the `{20,}` blob rule. An awk without regex
interval support treats `{16}` as literal braces, matches **nothing**, and the
scan prints a confident clean result. This is not hypothetical: **Debian 12's
default `mawk 1.3.4 20200120` is such an awk** (Ubuntu 24.04's `mawk 1.3.4
20240123` is not — same nominal version, different snapshot). Rewriting twelve
patterns without intervals is not viable, so the script probes the capability —
both the literal and the runtime-compiled form it uses — and refuses to run.

## Context rendering is fed by redirect, not a pipe

The extractor stops at `NR > n + 2`. Fed by a pipe, that leaves the writer
mid-write on a large blob: SIGPIPE, exit 141, and `pipefail` turns a **completed**
render into a scan failure. Clean at 3 lines, exit 2 at 20 001 lines
(`PIPESTATUS = 141 0`) — and it fired even for an allowlisted path. Process
substitution keeps the early exit (context renders once per finding, so a full
scan each time is O(findings × lines)) and structurally excludes the writer. A
here-string also works but can spill to a temp file on bash < 5.1, and this
script must run where `TMPDIR` is unwritable.

## One timeout code, and no silent degradation

Expiry sends `TERM`, and a gate that ignores it survives. The coreutils manual
demonstrates this exactly: `timeout -s INT 5s env --ignore-signal=INT sleep 20`
→ *"'sleep' terminates regularly after the full 20 seconds, still 'timeout'
returns with exit status 124"*. So `TERM` alone cannot back the "process tree is
dead" promise; `--kill-after` is required, and a tool that lacks it is **skipped
in favour of one that can**, because reporting a timeout you cannot deliver tells
the caller the gate is dead while it may still hold locks and ports. If nothing
on the host qualifies, the enforcer exits 2.

Three implementations then disagree on the code: GNU returns 124, or 137 when
the KILL was needed; **BusyBox does not implement the 124 convention at all** and
reports the child's signal death (143 plain, 137 with `-k`; verified on BusyBox
v1.37.0). 137 and 143 also occur when something else kills the gate. So the tool
runs as a child (not `exec`) and a signal death **at or past the deadline** is
normalised to 124 — elapsed time is the implementation-independent evidence that
the deadline is what fired. Callers have one rule: **124 means timed out**.

## gitleaks: exit codes and versions

Verified against real binaries:

| gitleaks | `git` subcommand | `--exit-code 10` | default |
|----------|------------------|------------------|---------|
| v8.24.3  | present          | 10               | 1       |
| v8.18.4  | **absent**       | 1                | 1       |

The default findings code is 1, which is also what gitleaks returns on execution
errors — hence pinning to 10 and treating everything outside `{0,10}` as a
scanner failure. On v8.18.4 the documented invocation does not exist and exits 1,
so the script fails closed; its `SCANNER_ERROR` names the ≥ 8.19 requirement.

Note for fixture authors: gitleaks **allowlists `AKIAIOSFODNN7EXAMPLE`** (AWS's
documentation key) and reports "no leaks found" for it. Tests that need the real
scanner to fire must use a non-allowlisted value.

## Scope rules live in a script

The §5 rules are purely mechanical — count, threshold, strip, match — so leaving
them as prose forced the golden tests to re-derive them in Python, and a test
asserting "my Python agrees with my Python" proves nothing. `resolve-scope.sh` is
the single source and the fixtures drive it against real repositories. That also
allowed a rule prose could not express cleanly: a canonical scope is adopted only
when **no second canonical scope** appears in the staged set, so a commit
spanning `auth/` and `billing/` is left unscoped instead of labelled with
whichever is more frequent.

## Verified environments

`scripts/run_cross_env_probe.sh` needs only bash, git and awk (no python), and
`scripts/run_portability_matrix.sh` with `MATRIX_DOCKER=1` reproduces the
container rows. Results as of 2026-09-07:

| Environment | awk | intervals | force-kill | Full suite |
|-------------|-----|-----------|------------|------------|
| macOS 15.6 / bash 5.3 | BSD awk 20200816 | yes | perl watcher | pass |
| Debian 12 / git 2.39.5 | mawk 1.3.4 20200120 | **no** | GNU timeout `-k` | pass, 36 skipped (script refuses — correct) |
| Debian 12 + gawk | GNU Awk 5.2.1 | yes | GNU timeout `-k` | pass |
| Ubuntu 24.04 / git 2.43.0 | mawk 1.3.4 20240123 | yes | GNU timeout `-k` | pass |
| Alpine 3.24 / git 2.54.0 | BusyBox awk | yes | BusyBox timeout `-k`, **no perl** | pass |

Alpine has no perl, so it is the row that exercises "nothing else qualifies →
refuse" for real rather than through a shim. Real gitleaks v8.24.3 was exercised
on Linux; v8.18.4 confirmed the fail-closed path.

**Still unverified:** Windows/WSL, `original-awk`, gitleaks on macOS, and any
agent-in-the-loop decision testing beyond `scripts/eval/` (see its README).
