#!/usr/bin/env bash
# Controlled runner for third-party integration tests.
#
#   bash <skill-dir>/scripts/run_vendor_integration.sh <env-file> <go-package> [extra go test args...]
#
# WHERE TO RUN IT: from the TARGET REPOSITORY ROOT (so a relative package like
# `./internal/pkg/thirdparty/vendor` resolves against that repo), invoking this script by an
# ABSOLUTE path to wherever the skill is installed. The skill's tool allowlist ships
# `Bash(bash scripts/run_vendor_integration.sh*)`, which matches only that relative prefix; if
# you invoke it by absolute path, add a matching entry, e.g.
# `Bash(bash /path/to/skill/scripts/run_vendor_integration.sh*)`.
#
# WHY A WRAPPER: separate shell invocations do NOT carry env vars forward, so an
# "export …; then go test" recipe is unreliable under a strict tool runtime. This runs in a
# SINGLE invocation. It PARSES <env-file> as KEY=VALUE data (it never `source`s it — sourcing
# would execute arbitrary shell hidden in the file), validates the safety-critical vars, refuses
# a production target by default, fixes the safety flags (`-tags=integration -count=1
# -timeout=<bounded> -v`), restricts extra args to a strict ALLOWLIST (so neither `-count`/
# `-timeout`/`-tags` nor their `-test.count`/`-test.timeout` binary-flag forms, nor `-args`, can
# slip through), and — as a final anti-false-green check — refuses to report success unless at
# least one test actually executed.
set -euo pipefail

envfile="${1:-}"
pkg="${2:-}"
if [[ -z "$envfile" || -z "$pkg" ]]; then
  echo "usage: run_vendor_integration.sh <env-file> <go-package> [go test args...]" >&2
  exit 2
fi
shift 2

if [[ ! -f "$envfile" ]]; then
  echo "env file not found: $envfile" >&2
  exit 2
fi

# The package argument must not smuggle a flag (e.g. `-count=0` as the "package" would land
# after our -count=1 and win). Require a plain package spec, never one starting with '-'.
if [[ "$pkg" == -* || ! "$pkg" =~ ^[A-Za-z0-9._/@~-]+(\.\.\.)?$ ]]; then
  echo "invalid go-package argument (must be a package path like ./... or ./internal/x, not a flag)" >&2
  exit 2
fi

# Extra args are restricted to a STRICT ALLOWLIST. A denylist is not enough: Go accepts both the
# `-count`/`-timeout` test flags AND their `-test.count`/`-test.timeout` binary-flag forms, plus
# `-args`, `-list`, `-c`, `-exec`, `-o`, etc. Only these run-selection flags may pass through;
# anything else (including any `-test.*`) is refused. Concurrency (`-p`/`-parallel`) is NOT on the
# list — it is fixed below, because an unbounded value could fan out concurrent calls to a paid
# API past the per-test cost budget. Flags taking a separate value consume the next token, which
# must not itself look like a flag.
i=1
while [[ $i -le $# ]]; do
  a="${!i}"
  case "$a" in
    -v | --v | -race | --race | -short | --short | -failfast | --failfast)
      ;;
    -run=* | --run=* | -skip=* | --skip=* | -shuffle=* | --shuffle=*)
      ;;
    -run | --run | -skip | --skip | -shuffle | --shuffle)
      i=$((i + 1))
      if [[ $i -gt $# || "${!i}" == -* ]]; then
        echo "flag $a requires a value" >&2
        exit 2
      fi
      ;;
    *)
      echo "refuse disallowed go test arg: $a" >&2
      echo "allowed extra args: -run/-skip/-shuffle <value>, -v/-race/-short/-failfast" >&2
      echo "(-tags/-count/-timeout/-p/-parallel and their -test.* forms, -args, -list are fixed or forbidden)" >&2
      exit 2
      ;;
  esac
  i=$((i + 1))
done

# Parse KEY=VALUE lines WITHOUT executing the file. `source` would run any shell code in the
# env file (e.g. `X=$(rm -rf …)`); the file may also hold tokens, so on a malformed line we
# report only the LINE NUMBER — never echo the content (it could contain a secret).
lineno=0
while IFS= read -r line || [[ -n "$line" ]]; do
  lineno=$((lineno + 1))
  line="${line%$'\r'}"                       # tolerate CRLF
  [[ -z "$line" || "$line" == '#'* ]] && continue
  if [[ "$line" != *=* ]]; then
    echo "malformed line $lineno in $envfile (expected KEY=VALUE)" >&2
    exit 2
  fi
  key="${line%%=*}"
  val="${line#*=}"
  if [[ ! "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
    echo "invalid env key on line $lineno in $envfile" >&2
    exit 2
  fi
  # strip one layer of matching surrounding quotes, if present
  if [[ ${#val} -ge 2 && "$val" == \"*\" ]]; then val="${val:1:${#val}-2}"; fi
  if [[ ${#val} -ge 2 && "$val" == \'*\' ]]; then val="${val:1:${#val}-2}"; fi
  export "$key=$val"
done < "$envfile"

# Required safety vars (the gate + sandbox host allowlist + test account allowlist). Host and
# account values are validated inside the test (fail-closed Go path); this is a fast pre-check.
for v in THIRDPARTY_INTEGRATION VENDOR_SANDBOX_HOSTS VENDOR_TEST_ACCOUNTS; do
  if [[ -z "${!v:-}" ]]; then
    echo "missing required var: $v (set it in $envfile)" >&2
    exit 3
  fi
done
if [[ "${THIRDPARTY_INTEGRATION}" != "1" ]]; then
  echo "THIRDPARTY_INTEGRATION must be 1 to run integration tests" >&2
  exit 3
fi

# Refuse a production target by default (host/account are validated in-test; this is a
# fast fail before compiling).
env_lc="$(printf '%s' "${ENV:-}" | tr '[:upper:]' '[:lower:]')"
if [[ "$env_lc" == "prod" || "$env_lc" == "production" ]] && [[ "${INTEGRATION_ALLOW_PROD:-}" != "1" ]]; then
  echo "refuse ENV=${ENV} without INTEGRATION_ALLOW_PROD=1" >&2
  exit 3
fi

# The test timeout must always be bounded on BOTH ends. It defaults to 300s and may be set via
# VENDOR_TEST_TIMEOUT (a Go duration in s/m/h), but is clamped to [1s, 3600s]: a 0 disables the
# timeout, and something like 999999h is effectively no protection at all.
timeout_val="${VENDOR_TEST_TIMEOUT:-300s}"
if [[ ! "$timeout_val" =~ ^([0-9]+)(s|m|h)$ ]]; then
  echo "VENDOR_TEST_TIMEOUT must be a Go duration in s/m/h, e.g. 300s or 5m (got: rejected)" >&2
  exit 2
fi
to_n="${BASH_REMATCH[1]}"
case "${BASH_REMATCH[2]}" in
  s) to_secs=$to_n ;;
  m) to_secs=$((to_n * 60)) ;;
  h) to_secs=$((to_n * 3600)) ;;
esac
if [[ $to_secs -lt 1 || $to_secs -gt 3600 ]]; then
  echo "VENDOR_TEST_TIMEOUT must be between 1s and 3600s (1h policy cap); got ${to_secs}s" >&2
  exit 2
fi

# Bound suite concurrency. VENDOR_MAX_CALLS is a PER-test/client budget; a large -parallel/-p
# could still fan out many paid-API tests at once. Default fully serial (1); allow raising to a
# small cap ([1,4]) via VENDOR_TEST_PARALLELISM. -p and -parallel are set here, never by callers.
par="${VENDOR_TEST_PARALLELISM:-1}"
if [[ ! "$par" =~ ^[1-9][0-9]*$ ]] || [[ "$par" -gt 4 ]]; then
  echo "VENDOR_TEST_PARALLELISM must be an integer in [1, 4] (cost guard); got: ${par}" >&2
  exit 2
fi

# The integration tests must be identifiable so a plain unit test cannot satisfy the
# executed-a-test check below. A PASSED test's name must contain this marker (the skill's
# Required Pattern mandates `…Integration` in test names); override only to another non-empty
# substring for a repo with a different convention.
name_match="${VENDOR_TEST_NAME_MATCH:-Integration}"
if [[ -z "$name_match" ]]; then
  echo "VENDOR_TEST_NAME_MATCH must be non-empty (the integration test-name marker)" >&2
  exit 2
fi

# Run with -v so we can confirm from the output that a real integration test actually PASSED.
# Capture while still streaming. -tags/-count/-timeout/-p/-parallel/-v are fixed; extra args were
# allowlisted above. Give mktemp an explicit template under $TMPDIR: bare `mktemp` on macOS/BSD
# ignores $TMPDIR (it resolves the darwin per-user temp via confstr), which a caller cannot redirect.
runlog="$(mktemp "${TMPDIR:-/tmp}/run_vendor_integration.XXXXXX")"
trap 'rm -f "$runlog"' EXIT
set +e
go test -tags=integration -count=1 -timeout="$timeout_val" -p="$par" -parallel="$par" -v "$pkg" "$@" 2>&1 | tee "$runlog"
status=${PIPESTATUS[0]}
set -e

# Anti-false-green (output-contract §"never report PASS when tests were skipped"): a green exit
# is NOT success unless a real integration test PASSED. `go test` exits 0 when every test SKIPs
# (e.g. a destructive tier without INTEGRATION_ALLOW_DESTRUCTIVE) or a -run/-skip pattern matched
# nothing — neither verified the vendor.
if [[ $status -eq 0 ]]; then
  if ! grep -qE '^(    )*--- PASS: ' "$runlog"; then
    echo "runner: exit was 0 but no test PASSED (all skipped or none ran) — refusing to report success" >&2
    exit 4
  fi
  if ! grep -E '^(    )*--- PASS: ' "$runlog" | grep -qF "$name_match"; then
    echo "runner: a test passed, but none matching '${name_match}' — the third-party integration tests did not run (check -run)" >&2
    exit 4
  fi
fi
exit "$status"
