#!/usr/bin/env bash
# detect-ecosystems.sh — list EVERY ecosystem present in the staged change set,
# one per line (go / node / python / java / rust), ordered by staged-file count,
# largest first. Empty output = nothing detected.
#
# Detection covers source extensions AND dependency-manifest markers, so a
# stage touching only go.mod / package.json / Cargo.toml / pyproject.toml /
# pom.xml still selects its gate. The count only orders the gates — it never
# drops a minority ecosystem (5 Go files + 1 TS file → both "go" and "node").
#
# DELETIONS COUNT. Removing a file is exactly the change most likely to break
# the build for its ecosystem (a deleted helper.py breaks every importer), so
# unlike secret-scan.sh — which reads blob content and must skip deletions —
# this detector must see them. `--no-renames` makes a rename report both the
# old and the new path, so `foo.py -> foo.txt` still selects the python gate.
#
# Fail-closed, because EMPTY output is this script's signal for "no ecosystem
# detected", which §4 turns into "quality gate: not detected". Any stage that
# fails — the git read or the awk that classifies — must therefore exit 2:
# "could not tell" is not "none". `pipefail` makes a failing awk visible; without
# it the shell reports only the last command's status.
set -u
set -o pipefail

# `-z` gives raw, NUL-separated paths. Plain --name-only is DISPLAY output: with
# the default core.quotePath, a non-ASCII path arrives as "\346\272\220…" and the
# extension parses as `py"` — so a stage of 配置.py detected nothing at all and
# skipped the gate. Never classify a path that git escaped for a terminal.
# Residual: `tr` turns a path containing a literal newline into two entries.
# That over-reports (an extra bogus path), which is the safe direction here.
if ! staged=$(git diff --cached -z --name-only --no-renames 2>/dev/null | tr '\0' '\n'); then
  echo "detect-ecosystems: could not read staged paths — ecosystems are UNKNOWN, not none" >&2
  exit 2
fi

if ! printf '%s\n' "$staged" | awk '
  {
    base = $0; sub(/.*\//, "", base)
    if (base == "go.mod" || base == "go.sum" ||
        base == "go.work" || base == "go.work.sum")          { count["go"]++; next }
    if (base == "package.json" || base == "package-lock.json" ||
        base == "yarn.lock" || base == "pnpm-lock.yaml" ||
        base == "bun.lock" || base == "bun.lockb" ||
        base == "deno.json" || base == "deno.jsonc" ||
        base == "tsconfig.json")                             { count["node"]++; next }
    if (base == "Cargo.toml" || base == "Cargo.lock")        { count["rust"]++; next }
    if (base == "pyproject.toml" || base == "setup.py" ||
        base == "setup.cfg" || base == "Pipfile" ||
        base == "Pipfile.lock" || base == "uv.lock" ||
        base == "poetry.lock" || base == "tox.ini" ||
        base ~ /^requirements.*\.txt$/)                      { count["python"]++; next }
    if (base == "pom.xml" || base ~ /^build\.gradle/ ||
        base ~ /^settings\.gradle/ ||
        base == "gradle.properties" ||
        base == "gradle.lockfile")                           { count["java"]++; next }
    n = split(base, parts, "."); if (n < 2) next
    ext = parts[n]
    if (ext == "go")                                           count["go"]++
    else if (ext == "js" || ext == "ts" || ext == "jsx" ||
             ext == "tsx" || ext == "mjs" || ext == "cjs" ||
             ext == "mts" || ext == "cts" ||
             ext == "vue" || ext == "svelte")                  count["node"]++
    else if (ext == "py")                                      count["python"]++
    else if (ext == "java" || ext == "kt" || ext == "kts")     count["java"]++
    else if (ext == "rs")                                      count["rust"]++
  }
  END { for (e in count) printf "%d %s\n", count[e], e }
' | sort -rn | awk '{ print $2 }'; then
  echo "detect-ecosystems: classification failed — ecosystems are UNKNOWN, not none" >&2
  exit 2
fi