#!/usr/bin/env bash
# Discover Go entrypoints under cmd/**/main.go.
#
# Output (tab-separated):
#   kind    name    target_name    dir
#
# kind: api | consumer | cron | worker | migrate | seed | cli | tool | other
# target_name: the recommended Makefile target suffix (e.g. "consumer-sync")
#
# Usage:
#   ./discover_go_entrypoints.sh [project-root]
#   ./discover_go_entrypoints.sh --json [project-root]
#
# This is a PROBE script: finding no entrypoints is a normal outcome, not an
# error. `set -e` / `pipefail` would kill the script inside the discovery
# pipeline on any repo without cmd/**/main.go — making the "no entrypoints"
# branch below unreachable dead code (this happened; see
# scripts/tests/test_executable_assets.py). So: `set -u` only, explicit
# handling for the genuinely fatal case (bad root), explicit exit codes.
set -u

json_mode=false
modules_mode=false
root="."

for arg in "$@"; do
  case "$arg" in
    --json)    json_mode=true ;;
    --modules) modules_mode=true ;;
    *)         root="$arg" ;;
  esac
done

cd "$root" || { echo "# cannot cd to $root" >&2; exit 2; }

# --modules: list Go workspace module directories from go.work `use` directives.
# Prefer the toolchain; fall back to parsing go.work so it works without `go`
# installed. Modules NOT listed under `use` (examples/, tools/, vendored) are
# excluded — this is what a bare `rg --files go.mod` gets wrong.
if $modules_mode; then
  if command -v go >/dev/null 2>&1 && [ -n "$(go env GOWORK 2>/dev/null)" ]; then
    go list -m -f '{{.Dir}}' 2>/dev/null || true
  elif [ -f go.work ]; then
    awk '
      /^[[:space:]]*use[[:space:]]*\(/  { inblk=1; next }
      inblk && /^[[:space:]]*\)/        { inblk=0; next }
      inblk                             { gsub(/[[:space:]]/,""); if ($0 != "") print; next }
      /^[[:space:]]*use[[:space:]]/     { sub(/^[[:space:]]*use[[:space:]]+/,""); gsub(/[[:space:]]/,""); print }
    ' go.work
  fi
  exit 0
fi

# Find main.go files: prefer rg, fall back to find. Empty result is normal.
if command -v rg >/dev/null 2>&1; then
  files=$(rg --files cmd 2>/dev/null | grep '/main\.go$' | sort) || true
else
  files=$(find cmd -name 'main.go' -type f 2>/dev/null | sort) || true
fi

if [ -z "$files" ]; then
  echo "# No cmd/**/main.go entrypoints found" >&2
  exit 0
fi

classify() {
  local dir="$1"

  # Single-level: cmd/<kind>/main.go
  # Multi-level:  cmd/<kind>/<name>/main.go  or  cmd/<kind>/<sub>/<name>/main.go

  # Known kind prefixes (extend this list for new conventions)
  local known_kinds="api consumer cron worker migrate seed cli tool"

  local rel="${dir#cmd/}"  # strip "cmd/" prefix
  local first="${rel%%/*}" # first path segment

  local kind="other"
  local name=""
  local target_name=""

  for k in $known_kinds; do
    if [ "$first" = "$k" ]; then
      kind="$k"
      break
    fi
  done

  if [ "$kind" != "other" ]; then
    local rest="${rel#"$first"}"
    rest="${rest#/}"  # strip leading slash
    if [ -z "$rest" ]; then
      # cmd/<kind>/main.go  (e.g. cmd/api/main.go)
      name="$kind"
      target_name="$kind"
    else
      # cmd/<kind>/<path>/main.go  (e.g. cmd/consumer/sync/main.go)
      name="$rest"
      target_name="${kind}-$(echo "$rest" | tr '/' '-')"
    fi
  else
    # cmd/<name>/main.go or cmd/<path>/main.go
    name="$rel"
    target_name="$(echo "$rel" | tr '/' '-')"
  fi

  if $json_mode; then
    printf '{"kind":"%s","name":"%s","target":"%s","dir":"%s"}\n' \
      "$kind" "$name" "$target_name" "$dir"
  else
    printf '%s\t%s\t%s\t%s\n' "$kind" "$name" "$target_name" "$dir"
  fi
}

echo "$files" | while IFS= read -r file; do
  [ -z "$file" ] && continue
  dir="${file%/main.go}"
  classify "$dir"
done

exit 0
