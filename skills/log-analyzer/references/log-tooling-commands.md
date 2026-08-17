# Log-Analysis Tooling Commands

A focused reference for the unix toolset most useful in log analysis. The point is not exhaustiveness — it is *which command for which question*.

## Contents

- [Forbidden Forms](#forbidden-forms)
- [`jq` — JSON Logs](#jq--json-logs)
- [`rg` (ripgrep) — Fast Scanning](#rg-ripgrep--fast-scanning)
- [`awk` — Field-Aware Filtering](#awk--field-aware-filtering)
- [`journalctl` — systemd Journal](#journalctl--systemd-journal)
- [`kubectl logs` — Container Logs](#kubectl-logs--container-logs)
- [Streaming / Large Files](#streaming--large-files)
- [Bucket Counts (Histograms)](#bucket-counts-histograms)
- [Identifier Stripping (Pre-Counting)](#identifier-stripping-pre-counting)
- [Diff Two Windows](#diff-two-windows)
- [Common Pitfalls](#common-pitfalls)

## Forbidden Forms

Referenced from SKILL.md §Command Safety Contract. Every entry below writes,
deletes, or executes. **Never issue these**, regardless of whether a permission
prompt would approve them — the user cannot audit what they did not see proposed.

| Forbidden form | What it actually does | Use instead |
|---|---|---|
| `sed -i` / `sed … w FILE` / `s///w FILE` | edits the source log **in place** | `sed` to stdout; let the user redirect |
| `sort -o FILE` | writes FILE (works even when input == output) | `sort` to stdout |
| `sort --compress-program=CMD` | spawns CMD for spill files | `sort` to stdout |
| `uniq IN OUT` | second positional arg is an **output file**, silently overwritten | `uniq IN` |
| `awk 'BEGIN{system("…")}'` | arbitrary command execution | `awk` reading to stdout only |
| `awk '… > "f"'` / `printf > "f"` / `\| "cmd"` | file write / command pipe from inside awk | same |
| `gzip FILE` (no `-c`) | **replaces** FILE with FILE.gz — the log is gone | `gzip -c`, or `zcat` to read |
| `journalctl --vacuum-size=` / `--vacuum-time=` / `--vacuum-files=` | permanently deletes archived journals | `journalctl --since/--until` |
| `journalctl --rotate` / `--flush` / `--relinquish-var` | mutates journal storage | same |
| `rg --pre CMD` / `--pre-glob` | spawns a process for **every file searched** | plain `rg` / `grep` |
| `file -C` | compiles and writes a `.mgc` magic file | `file` without `-C` |
| `date -s` / `--set` | sets the system clock | read timestamps; never set them |
| any `kubectl` verb but `logs` | mutates cluster state | `kubectl logs` |
| `>`, `>>`, `tee`, `dd`, `truncate` | writes files | print to stdout, or use the tool's own `--output` |

When a step genuinely must produce a file, use the tool's own writer rather than
carving out an exception for `>`. A subcommand can enforce what a shell redirect
cannot: `redact_log.py write -o PATH` creates with `O_EXCL | O_NOFOLLOW`, so it
refuses an existing path or a symlink and cannot overwrite the log being read. It
is not auto-approved, so it prompts once — creating a file deserves a human.

Verified by execution, or against upstream documentation (systemd
`man/journalctl.xml` for the vacuum family; ripgrep `flags/defs.rs` for `--pre`:
*"ripgrep will unconditionally spawn a process for every file that is searched"*).
The attack corpus in `scripts/tests/test_allowed_tools.py` asserts none of these
can be auto-approved.

**Auto-approved (cannot write, delete, or execute):** `grep`, `jq`, `wc`, `cut`,
`head`, `tail`, `zcat`, `stat`, `kubectl logs`, and the two read-only subcommands
`redact_log.py scan` / `redact_log.py verify`.

**Allowed but prompts:** `awk`, `sed`, `sort`, `uniq`, `rg`, `journalctl`, `file`,
`date`, and `redact_log.py write` — for the first eight, safe and destructive forms
share a prefix so a glob cannot separate them; `write` creates a file. Propose them
normally and note the prompt in Execution Status.

The script grants are written as
`Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/redact_log.py scan *)` and `… verify *)`,
each anchored on the literal interpreter + path + subcommand so `python3 -c
'<anything>'` cannot match. `scan` and `verify` register no output option, so
argparse rejects `--output` on them — their read-only-ness is enforced by the
parser rather than by this paragraph.

### `${CLAUDE_SKILL_DIR}` version facts

Added in Claude Code **v2.1.69**. Verified by fetching `anthropics/claude-code`
`CHANGELOG.md` and locating the mention *relative to the version headings*: the
file contains exactly one `CLAUDE_SKILL_DIR` line — *"Added `${CLAUDE_SKILL_DIR}`
variable for skills to reference their own directory in SKILL.md content"* — and it
sits inside the `## 2.1.69` block. (Reviews have twice proposed `v2.1.73`; that
block does not contain the entry. Re-check by walking back to the nearest `^## `
heading, not by proximity search — the changelog is reverse-chronological, which is
how the wrong neighbour gets picked.)

The current skills documentation states it is substituted in **two places — the
skill's markdown content and Bash rules in `allowed-tools`** — and gives no
separate version for the second. An earlier revision of this file claimed a
distinct `v2.1.129` gate for `allowed-tools`; that number is supported by neither
source and has been removed. If a build ever did leave the rule unsubstituted it
would simply never match, so the command would prompt instead of auto-running — a
safe degradation, not a failure.

## `jq` — JSON Logs

Common patterns:

```bash
# Filter by level
jq -c 'select(.level=="ERROR")' app.log

# Multi-condition filter
jq -c 'select(.level=="ERROR" and .path=="/v1/checkout")' app.log

# Time-bound (ISO-8601 string compare works lexicographically)
jq -c 'select(.time>="2026-04-28T08:00:00Z" and .time<"2026-04-28T09:00:00Z")' app.log

# Project a subset of fields
jq -c '{time, level, msg, trace_id}' app.log

# Top-N error messages
jq -r 'select(.level=="ERROR") | .msg' app.log | sort | uniq -c | sort -rn | head -20

# Errors per minute (bucket on first 16 chars of ISO timestamp)
jq -r 'select(.level=="ERROR") | .time[0:16]' app.log | sort | uniq -c

# Walk one trace
jq -c --arg t "4bf92f3577…" 'select(.trace_id==$t)' *.log | jq -s 'sort_by(.time)'

# Convert epoch float to ISO (zap default)
jq -c '.ts |= todate' app.log

# Redaction: drop a field
jq -c 'del(.password)' app.log

# Redaction: rewrite a field
jq -c '.authorization = "***REDACTED***"' app.log
```

Notes:
- `-c` = compact; one log line per output line.
- `-r` = raw (no JSON quoting); use when feeding to `sort`/`uniq`.
- `--arg` injects a shell variable safely (no quoting issues).

## `rg` (ripgrep) — Fast Scanning

```bash
# Grep with context, all files
rg -A 2 -B 2 "context deadline exceeded" /var/log/

# Multi-line patterns (Go panics)
rg --multiline --multiline-dotall '^panic:.*?(?=^\S|\z)' app.log

# Count matches by file
rg -c "ERROR" /var/log/

# JSON-aware grep (respects field boundaries)
rg --json "ERROR" app.log | jq 'select(.type=="match")'
```

`rg` defaults: respects `.gitignore`, recursive, faster than grep on big trees.

## `awk` — Field-Aware Filtering

```bash
# Last 100 lines whose level field is ERROR (slog text format)
awk -F' ' '$2=="ERROR"' app.log | tail -100

# Aggregate counts of a field
awk -F' ' '$2=="ERROR" {print $4}' app.log | sort | uniq -c | sort -rn

# Print lines between two timestamps
awk '/2026-04-28T08:00/,/2026-04-28T09:00/' app.log

# Multi-line block (Go panic)
awk '/^panic:/{flag=1} flag{print} /^[[:space:]]*$/{flag=0}' app.log
```

## `journalctl` — systemd Journal

```bash
# Service errors in window
journalctl -u my-service.service \
  --since "2026-04-28 08:00:00" --until "2026-04-28 09:00:00" \
  -p err

# JSON output for jq pipelines
journalctl -u my-service.service --since "1 hour ago" -o json | jq -c .

# Boot-scoped (current boot only)
journalctl -b -p err

# Follow mode
journalctl -u my-service.service -f
```

Priority numbers: `0=emerg, 1=alert, 2=crit, 3=err, 4=warning, 5=notice, 6=info, 7=debug`. `-p err` includes 0–3.

## `kubectl logs` — Container Logs

```bash
# One pod, last 30 min, with kubelet timestamp prefix
kubectl logs <pod> -c <container> --since=30m --timestamps

# All replicas of a deployment
kubectl logs -l app=order-svc --all-containers=true --since=15m -f

# Previous instance (after a crash)
kubectl logs <pod> --previous

# Stream then filter through jq
kubectl logs <pod> --since=15m | jq -c 'select(.level=="ERROR")'

# Tail n lines
kubectl logs <pod> --tail=200
```

When pods are too many to specify, switch to a label selector or use `stern` (third-party tool for multi-pod streaming).

## Streaming / Large Files

For files > 1 GB, never `cat` to memory.

```bash
# Stream a gzip'd log
zcat app.log.gz | jq -c 'select(.level=="ERROR")'

# In-place sort by size with split
LC_ALL=C sort -k1,1 app.log | head -100

# Parallel jq on a directory (to stdout; pipe onward rather than redirecting)
ls *.log | xargs -P 4 -I{} jq -c 'select(.level=="ERROR")' {}

# Tail a live stream and feed jq incrementally
tail -F app.log | jq -c 'select(.level=="ERROR")'
```

## Bucket Counts (Histograms)

For a quick per-minute or per-second rate:

```bash
# Per-minute bucket on slog JSON
jq -r 'select(.level=="ERROR") | .time[0:16]' app.log | sort | uniq -c

# Per-second
jq -r '.time[0:19]' app.log | sort | uniq -c

# Per-15-minute bucket (trim more digits)
jq -r '.time[0:13]' app.log | sort | uniq -c
```

The shape of the output (step / ramp / spike) often reveals what kind of failure you are looking at — see `log-statistical-methods.md`.

## Identifier Stripping (Pre-Counting)

```bash
# Strip common ID shapes before grouping
jq -r 'select(.level=="ERROR") | .msg' app.log \
  | sed -E '
      s/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/<UUID>/g;
      s/\b[0-9]{8,}\b/<NUM>/g;
      s/(order|user|tenant)[-_]?[a-z0-9-]+/\1_<ID>/g;
    ' \
  | sort | uniq -c | sort -rn | head -20
```

This collapses cardinality before counting. The full identifier value is still available in the original lines for trace walking.

## Diff Two Windows

Process substitution keeps both sides as pipes, so no intermediate file is
written and no stale `/tmp` file from an earlier run can be compared by mistake.

```bash
# Reuse the same two pipes for each comparison direction.
now() { jq -r 'select(.level=="ERROR") | .err.code // .msg' last-hour.log | sort -u; }
was() { jq -r 'select(.level=="ERROR") | .err.code // .msg' baseline.log  | sort -u; }

comm -23 <(now) <(was)   # new error classes
comm -12 <(now) <(was)   # persistent error classes
comm -13 <(now) <(was)   # error classes that disappeared (also interesting)
```

## Common Pitfalls

- **`grep ERROR app.log`** without anchoring — matches `ERRORLESS`, etc. Use `\bERROR\b` or `level="ERROR"` for JSON.
- **Reading a JSON log with awk on whitespace** — JSON values with embedded spaces break field counting. Use `jq`.
- **Forgetting `LC_ALL=C` on sort** for very large files — locale-aware sort is dramatically slower.
- **Quoting in shell**: prefer `--arg` (jq) and double-quoting variables. Single quotes in a `--arg` value are common bugs.
