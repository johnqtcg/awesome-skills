# Log Format Cheatsheet

Detect the format **before** parsing. Picking the wrong tool (e.g., `grep` against JSON) hides fields you need and creates false confidence in negative results.

## Detection Rules of Thumb

| Visual cue (first non-blank line) | Likely format | Notes |
|---|---|---|
| `{"time":"2026-…","level":"INFO",…}` | Go `slog` JSON | Stdlib `slog.NewJSONHandler` |
| `{"@timestamp":"2026-…","level":"info",…}` | Bunyan / pino / Logstash | Common in Node services |
| `{"ts":"2026-…","level":"info","caller":…,"msg":…}` | Go `zap` (production preset) | `caller` and `msg` are zap defaults |
| `<14>2026-04-28T08:14:00Z host kube-apiserver[1234]: …` | RFC 5424 syslog | Priority `<NN>` is the giveaway |
| `Apr 28 08:14:00 host kube-apiserver[1234]: …` | RFC 3164 syslog | No priority byte; older format |
| `2026-04-28T08:14:00.123Z INFO  com.acme.OrderSvc - …` | JVM (Logback / Log4j) | Level keyword + dash separator |
| `[2026-04-28 08:14:00,123] {dag.py:142} INFO - …` | Python (Airflow / stdlib) | `[level=...]` square brackets common |
| `time="2026-04-28T08:14:00Z" level=info msg=…` | Go `logrus` / Docker daemon | key=value pairs (`logfmt`) |
| Multi-line block starting `panic:` or `goroutine 1 [running]:` | Go panic / runtime stack | Aggregate as one record |
| Multi-line block starting `Traceback (most recent call last):` | Python traceback | Aggregate to closing exception line |
| Multi-line block starting `Exception in thread` | Java / JVM stack trace | Aggregate to last `at …` line |

When piped through `kubectl logs` you may get **mixed** formats (one container per pod with its own format). Detect per source, not globally.

## Parsing Recipes

### slog JSON (Go ≥1.21 stdlib)

Schema (default):
```json
{"time":"2026-04-28T08:14:00.123Z","level":"ERROR","msg":"db query failed","err":"context deadline exceeded","trace_id":"4b…"}
```

Recipes:
```bash
# Errors only
jq -c 'select(.level=="ERROR")' app.log

# Group error counts by msg
jq -r 'select(.level=="ERROR") | .msg' app.log | sort | uniq -c | sort -rn

# All log lines for one trace
jq -c --arg t "4bf92f3577b34da6a3ce929d0e0e4736" 'select(.trace_id==$t)' app.log

# Time-bound by ISO timestamp
jq -c 'select(.time>="2026-04-28T08:00:00Z" and .time<"2026-04-28T09:00:00Z")' app.log
```

### zap JSON

Default production schema includes `ts` (epoch float), `level`, `caller`, `msg`, plus arbitrary fields.

```bash
# Errors only
jq -c 'select(.level=="error" or .level=="fatal")' app.log

# Convert epoch timestamp to ISO for human reading
jq -c '.ts |= todate' app.log
```

### logrus / logfmt (key=value pairs)

```bash
# All ERROR rows
grep -F 'level=error' app.log

# Pull out msg= values
grep -oP 'msg="[^"]+"' app.log | sort | uniq -c | sort -rn

# Logfmt → JSON (then use jq) via `lfmt`-style awk one-liner
awk '{ printf "{"; for (i=1;i<=NF;i++){ split($i,a,"="); printf "%s\"%s\":%s", (i>1?",":""), a[1], a[2] }; print "}" }' app.log
```

### syslog (RFC 5424)

Use `journalctl` whenever possible — it parses the structured fields for you:
```bash
journalctl -u my-service.service --since "2026-04-28 08:00:00" --until "2026-04-28 09:00:00" -o json
```

Plain syslog files:
```bash
# Filter by program / unit
awk '/kube-apiserver\[/' /var/log/syslog
# Filter by severity using priority byte (<8>=ERR, <11>=WARN, <14>=INFO)
awk '/^<(0|1|2|3)>/' /var/log/syslog   # emerg..err
```

### Container / Kubernetes

```bash
# Single pod, last 30 min, only the app container
kubectl logs <pod> -c app --since=30m --timestamps

# All replicas of a deployment, follow
kubectl logs -l app=order-svc --all-containers=true --since=15m -f

# Previous-instance logs (after a crash)
kubectl logs <pod> --previous

# Stream-then-pipe (handles JSON + multi-line panics)
kubectl logs <pod> --since=15m | jq -c 'select(.level=="ERROR")'
```

`--timestamps` prepends a kubelet-side ISO timestamp regardless of the inner format — useful when the application log lacks one.

### Multi-line stack traces

Treat a stack trace as **one logical record**. Dumb line-counting will overstate severity by counting every `at com.acme…` frame.

Go panic block detection:
```bash
awk '/^panic:/{flag=1} flag{print} /^[[:space:]]*$/{flag=0}' app.log
```

Python traceback block detection:
```bash
awk '/^Traceback/{flag=1} flag{print} /^[A-Z][A-Za-z]*Error:/{flag=0; print ""}' app.log
```

When using `rg` (ripgrep), prefer `--multiline --multiline-dotall` with anchored start patterns; this is dramatically faster than `grep -A` chains on large files.

## Mixed-Format Sources

If a single source emits multiple formats (e.g., a Go service whose stdlib `log.Print` lines coexist with `slog` JSON), split the analysis:

1. Filter by anchor (`grep '^{' app.log` for JSON, `grep -v '^{' app.log` for text).
2. Analyse each subset with its own tooling.
3. Merge the resulting timelines back together by timestamp.

Record both formats in `Execution Status: Format`.

## Performance Notes

- For files > 1 GB, use streaming pipelines (`zcat … | jq -c 'select(…)'`) rather than `cat`-then-process. Memory will not survive a `jq` over a 10 GB file held in RAM.
- `rg` is faster than `grep` on large directories and respects `.gitignore` by default.
- For repeated queries, build a single intermediate filtered file (`jq -c 'select(.level=="ERROR")' app.log > /tmp/errs.json`) and re-query that, rather than re-scanning the original.
- Avoid `cat | grep | grep | grep` chains; combine with `awk '/A/ && /B/ && !/C/'` or one anchored regex.

## When Format Detection Fails

If the first 1000 lines do not match any pattern above:

- Print the first 5 non-blank lines and ask the user what generated them.
- State `Format: unknown — analysis paused pending source identification` and stop. Drawing conclusions from a guessed format is a Causation Discipline Gate violation.
