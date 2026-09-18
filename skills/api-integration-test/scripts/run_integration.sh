#!/usr/bin/env bash
# Single-invocation runner for gated internal-API integration tests.
#
# WHY THIS EXISTS — two tool-runtime facts, not a style preference:
#
#   1. A strict `Bash(go test*)` allowlist matches only a command whose FIRST token is
#      `go test`. The documented form `INTERNAL_API_INTEGRATION=1 ENV=dev … go test …`
#      starts with a variable assignment, so it does NOT match and needs a prompt.
#   2. Separate Bash invocations do not carry env vars forward, so "export … then
#      `go test`" is unreliable: the second call runs with none of the first call's env.
#
# So the env and the run must happen in ONE invocation, behind one allowlist entry:
#   Bash(bash scripts/run_integration.sh*)
#
# Usage:
#   bash scripts/run_integration.sh <env-file> <package> [extra go test args...]
#
#   <env-file>  gitignored file of KEY=VALUE lines.
#               It is parsed as data and is never `source`d: sourcing would execute
#               any shell hidden in a file that holds tenant IDs and tokens.
#   <package>   e.g. ./internal/pkg/client/user
#
# `-count=1` is appended unconditionally: Go caches a passing package result keyed on the
# test binary + consulted env vars + files, none of which include the external service, so
# a cached run never contacts it. See SKILL.md §Execution Integrity Gate.

set -euo pipefail

if [[ $# -lt 2 ]]; then
    echo "usage: bash scripts/run_integration.sh <env-file> <package> [go test args...]" >&2
    exit 2
fi

ENV_FILE="$1"; shift
PKG="$1"; shift

if [[ ! -f "$ENV_FILE" ]]; then
    echo "env file not found: $ENV_FILE" >&2
    echo "create it with the variables listed by the Configuration Completeness Gate," >&2
    echo "and add it to .gitignore — it holds tenant IDs and may hold tokens." >&2
    exit 2
fi

# Parse KEY=VALUE as data. No `source`, no command substitution, no globbing.
declare -a ENVS=()
while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%%$'\r'}"
    [[ -z "${line// }" ]] && continue
    [[ "${line#"${line%%[![:space:]]*}"}" == \#* ]] && continue
    if [[ "$line" != *=* ]]; then
        echo "malformed line in $ENV_FILE (expected KEY=VALUE): $line" >&2
        exit 2
    fi
    key="${line%%=*}"
    if [[ ! "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
        echo "malformed key in $ENV_FILE: $key" >&2
        exit 2
    fi
    ENVS+=("$line")
done < "$ENV_FILE"

# The run gate must be present, or the whole suite skips and CI goes green blind.
if ! printf '%s\n' "${ENVS[@]}" | grep -q '^INTERNAL_API_INTEGRATION='; then
    echo "$ENV_FILE does not set INTERNAL_API_INTEGRATION — the suite would skip entirely" >&2
    exit 2
fi

echo "+ go test -tags=integration $PKG -run Integration -v -count=1 $*"
exec env "${ENVS[@]}" go test -tags=integration "$PKG" -run Integration -v -count=1 "$@"
