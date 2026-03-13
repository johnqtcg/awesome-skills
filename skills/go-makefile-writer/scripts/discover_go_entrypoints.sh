#!/usr/bin/env bash
set -euo pipefail

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

json_mode=false
root="."

for arg in "$@"; do
  case "$arg" in
    --json) json_mode=true ;;
    *)      root="$arg" ;;
  esac
done

cd "$root"

# Find main.go files: prefer rg, fall back to find
if command -v rg >/dev/null 2>&1; then
  files=$(rg --files cmd 2>/dev/null | grep '/main\.go$' | sort)
else
  files=$(find cmd -name 'main.go' 2>/dev/null | sort)
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
