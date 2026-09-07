#!/usr/bin/env bash
# run_portability_matrix.sh — re-run the regression suite once per available
# implementation of the external tools these scripts depend on.
#
#   Usage: cd skills/git-commit && bash scripts/run_portability_matrix.sh
#
# WHY THIS EXISTS. The suite proves behaviour against whichever `awk` happens to
# be first on PATH. That is ONE ROW of a matrix, and the dependencies are not
# interchangeable in practice:
#   * regex intervals ({16}, {20,}) — twelve credential patterns rely on them,
#     and an awk without support matches NOTHING while printing a clean result.
#     secret-scan.sh probes for this and refuses, but the probe deserves to be
#     exercised against a real such awk, not only against a shim.
#   * tolower() byte semantics under LC_ALL=C, which the redaction cut relies on.
#   * `sort -rn` tie ordering, which decides gate order on equal counts.
#
# CONTAINER ROWS. `MATRIX_DOCKER=1` additionally runs the cross-env probe inside
# ephemeral Linux images (nothing is installed on the host), which is the only way
# this matrix reports more than one OS. `MATRIX_FULL=1` runs the whole pytest
# suite in-image instead. Verified rows are recorded in
# evaluate/git-commit-skill-eval-report.md.
#
# WHAT IT DOES NOT DO. It cannot conjure an implementation the host lacks.
# Absent rows are printed as UNVERIFIED — a gap in the evidence, never a pass —
# and the runner exits non-zero if NOTHING could be exercised, so an empty
# matrix can never be mistaken for a green one.
set -u

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$SKILL_DIR" || exit 2

SHIM="$SKILL_DIR/.portability-shim"
# Trap-guaranteed: a lingering shim dir is an `awk` override waiting to confuse
# the next run, and untracked clutter in the repo.
cleanup() { rm -rf "$SHIM"; }
trap cleanup EXIT INT TERM

# MATRIX_LOCAL=0 runs only the container rows. Needed because the local rows run
# the pytest suite, and that suite contains the fault-injection tests for THIS
# script — without the switch, calling the matrix from a test recurses forever
# (observed: the first version of those tests hung and had to be killed).
CANDIDATES="awk gawk mawk nawk busybox-awk original-awk"
[ "${MATRIX_LOCAL:-1}" = 1 ] || CANDIDATES=""
ran=0
skipped=""
failed=""

probe_intervals() {   # "$@" = the awk command; 0 = intervals supported
  AWK_PROBE='[a-z]{20,}' "$@" 'BEGIN {
    exit !((match("aaaaaaaaaaaaaaaaaaaaaaaaa", /[a-z]{20,}/) == 1) &&
           (match("aaaaaaaaaaaaaaaaaaaaaaaaa", ENVIRON["AWK_PROBE"]) == 1))
  }' 2>/dev/null
}

echo "=== git-commit portability matrix ==="
printf 'host: %s %s / bash %s / git %s\n\n' \
  "$(uname -s)" "$(uname -r)" "${BASH_VERSION:-?}" "$(git --version | awk '{print $3}')"

[ "${MATRIX_LOCAL:-1}" = 1 ] || echo "--- local rows: SKIPPED (MATRIX_LOCAL=0)"
for name in $CANDIDATES; do
  case $name in
    busybox-awk)  command -v busybox      >/dev/null 2>&1 && set -- busybox awk  || { skipped="$skipped $name"; continue; } ;;
    original-awk) command -v original-awk >/dev/null 2>&1 && set -- original-awk || { skipped="$skipped $name"; continue; } ;;
    *)            command -v "$name"      >/dev/null 2>&1 && set -- "$name"      || { skipped="$skipped $name"; continue; } ;;
  esac

  ver=$("$@" --version 2>/dev/null | head -1 || true)
  [ -n "$ver" ] || ver=$("$@" -W version 2>&1 | head -1 || true)
  [ -n "$ver" ] || ver="(version unknown)"

  if probe_intervals "$@"; then intervals="intervals=YES"
  else intervals="intervals=NO — secret-scan.sh must REFUSE to run"; fi
  printf -- '--- %-13s %s | %s\n' "$name:" "$ver" "$intervals"

  # The shim must exec an ABSOLUTE path. It is itself named `awk` and sits first
  # on PATH, so `exec awk "$@"` re-invokes the shim and hangs forever — which is
  # exactly what the first version of this runner did: no output, killed by hand.
  # Hence both the absolute path AND the self-test below.
  abs=$(command -v "$1") || { skipped="$skipped $name(unresolved)"; continue; }
  rest=""
  [ "$#" -gt 1 ] && { shift; rest="$*"; }

  rm -rf "$SHIM"
  mkdir -p "$SHIM" || { skipped="$skipped $name(shim-mkdir)"; continue; }
  printf '#!/usr/bin/env bash\nexec %s %s "$@"\n' "$abs" "$rest" > "$SHIM/awk"
  chmod +x "$SHIM/awk"

  # Self-test the shim before handing it a full suite: a recursing or broken
  # shim would otherwise show up as a hang or a wall of unrelated failures.
  probe=$(echo ok | PATH="$SHIM:$PATH" awk '{ print $1 }' 2>&1)
  if [ "$probe" != "ok" ]; then
    echo "    shim: UNUSABLE (got '${probe:-<empty>}') — skipping"
    skipped="$skipped $name(shim-broken)"
    continue
  fi

  if PATH="$SHIM:$PATH" python3 -m pytest scripts/tests/ -q -p no:cacheprovider >/dev/null 2>&1; then
    echo "    suite: PASS"
  else
    echo "    suite: FAIL"
    failed="$failed $name"
  fi
  ran=$((ran + 1))
done

# --- optional: real other-OS rows, via ephemeral containers ------------------
# Without this the matrix can only ever report one OS. Images are used as-is and
# discarded; nothing is installed on the host. Set MATRIX_IMAGES to override, or
# MATRIX_FULL=1 to run the whole pytest suite in-image instead of the probe.
if [ "${MATRIX_DOCKER:-0}" = 1 ]; then
  echo
  if ! docker info >/dev/null 2>&1; then
    echo "--- docker rows: UNAVAILABLE (no reachable daemon)"
    skipped="$skipped docker"
  else
    for img in ${MATRIX_IMAGES:-debian:12-slim ubuntu:24.04 alpine:latest}; do
      printf -- '--- container %s\n' "$img"
      if [ "${MATRIX_FULL:-0}" = 1 ]; then
        # Capture pytest's status, THEN show the tail. `pytest | tail` reports
        # tail's success, so a failing suite inside the container looked clean.
        # No temp file: a host or image where the redirect target is unwritable
        # would lose the output AND report a false failure. Parameter expansion
        # is not recursive, so the `$(...)`/`$?` below survive being embedded in
        # the outer double-quoted `sh -c` payload and are evaluated in-container.
        inner='pyout=$(python3 -m pytest scripts/tests/ -q -p no:cacheprovider -rs 2>&1); prc=$?; printf "%s\\n" "$pyout" | tail -3; exit $prc'
        pkgs_apk="git bash python3 py3-pytest"; pkgs_apt="git python3 python3-pytest"
      else
        inner='PROBE_WORK=/tmp bash scripts/run_cross_env_probe.sh'
        pkgs_apk="git bash"; pkgs_apt="git"
      fi
      # NOT `if docker run ... | sed`. In a pipeline the shell reports the LAST
      # command's status, so the `if` tested sed and a container exiting 42 was
      # summarised as "all exercised implementations pass" with exit 0. Capture
      # the status first, indent afterwards. (Deliberately not `set -o pipefail`
      # for the whole file: other pipelines here end in `head -1`, whose early
      # exit would then be reported as a failure.)
      cout=$(docker run --rm -v "$SKILL_DIR:/skill:ro" "$img" sh -c "
            if command -v apk >/dev/null 2>&1; then apk add --no-cache $pkgs_apk >/dev/null 2>&1
            else apt-get update -qq >/dev/null 2>&1; apt-get install -y -qq $pkgs_apt >/dev/null 2>&1; fi
            cp -r /skill /work && cd /work && $inner
          " 2>&1)
      drc=$?
      printf '%s\n' "$cout" | sed 's/^/    /'
      ran=$((ran + 1))
      if [ "$drc" -ne 0 ]; then
        echo "    FAILED (container exited $drc)"
        failed="$failed $img"
      fi
    done
  fi
fi

echo
echo "exercised : $ran implementation(s)"
printf 'UNVERIFIED:%s\n' "${skipped:- none}"
echo "            (absent on this host — a gap in the evidence, not a pass)"
if [ -n "$failed" ]; then
  echo "FAILED    :$failed"
  exit 1
fi
if [ "$ran" -eq 0 ]; then
  echo "nothing could be exercised — an empty matrix is not a passing matrix"
  exit 2
fi
echo "result    : all $ran exercised implementation(s) pass"
