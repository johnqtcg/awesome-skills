# Log-Analysis Tooling Commands

A focused reference for the unix toolset most useful in log analysis. The point is not exhaustiveness — it is *which command for which question*.

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

# Parallel jq on a directory
ls *.log | xargs -P 4 -I{} jq -c 'select(.level=="ERROR")' {} > /tmp/errs.jsonl

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

```bash
# Error classes seen now but not in baseline
jq -r 'select(.level=="ERROR") | .err.code // .msg' last-hour.log | sort -u > /tmp/now.txt
jq -r 'select(.level=="ERROR") | .err.code // .msg' baseline.log  | sort -u > /tmp/then.txt
comm -23 /tmp/now.txt /tmp/then.txt   # new error classes
comm -12 /tmp/now.txt /tmp/then.txt   # persistent error classes
comm -13 /tmp/now.txt /tmp/then.txt   # error classes that disappeared (also interesting)
```

## Common Pitfalls

- **`grep ERROR app.log`** without anchoring — matches `ERRORLESS`, etc. Use `\bERROR\b` or `level="ERROR"` for JSON.
- **Reading a JSON log with awk on whitespace** — JSON values with embedded spaces break field counting. Use `jq`.
- **Forgetting `LC_ALL=C` on sort** for very large files — locale-aware sort is dramatically slower.
- **Quoting in shell**: prefer `--arg` (jq) and double-quoting variables. Single quotes in a `--arg` value are common bugs.
