#!/usr/bin/env bash
# detect-ecosystems.sh — list EVERY ecosystem present in the staged change set,
# one per line (go / node / python / java / rust), ordered by staged-file count,
# largest first. Empty output = nothing detected.
#
# Detection covers source extensions AND dependency-manifest markers, so a
# stage touching only go.mod / package.json / Cargo.toml / pyproject.toml /
# pom.xml still selects its gate. The count only orders the gates — it never
# drops a minority ecosystem (5 Go files + 1 TS file → both "go" and "node").
set -u

git diff --cached --name-only --diff-filter=d | awk '
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
' | sort -rn | awk '{ print $2 }'