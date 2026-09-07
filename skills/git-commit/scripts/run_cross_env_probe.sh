#!/usr/bin/env bash
# run_cross_env_probe.sh — exercise the SHIPPED scripts against whatever tools
# this host actually has. Needs only bash, git and awk: no python, no pytest.
#
#   Usage: bash scripts/run_cross_env_probe.sh
#
# The pytest suite is the detailed authority, but it can only run where python
# and pytest exist — which excludes almost every minimal Linux image, and so
# excluded every non-macOS awk from the evidence. This probe covers the checks
# whose outcome genuinely varies with the environment, and states which branch
# it took, so a run in a container is a real result rather than a claim.
#
# Reports one line per check and exits non-zero on any failure. A capability the
# host lacks is reported as SKIP with a reason, never silently passed.
set -u

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
WORK="${PROBE_WORK:-${TMPDIR:-/tmp}}/gc-probe-$$"
pass=0; fail=0; skip=0

ok()   { printf '  PASS  %s\n' "$1"; pass=$((pass+1)); }
bad()  { printf '  FAIL  %s\n     -> %s\n' "$1" "${2:-}"; fail=$((fail+1)); }
miss() { printf '  SKIP  %s (%s)\n' "$1" "$2"; skip=$((skip+1)); }

command -v git >/dev/null 2>&1 || { echo "probe: git is required"; exit 2; }
command -v awk >/dev/null 2>&1 || { echo "probe: awk is required"; exit 2; }

# --- environment report ------------------------------------------------------
awkver=$( (awk --version 2>/dev/null || awk -W version 2>&1) | head -1 )
if AWK_PROBE='[a-z]{20,}' awk 'BEGIN {
     exit !((match("aaaaaaaaaaaaaaaaaaaaaaaaa", /[a-z]{20,}/) == 1) &&
            (match("aaaaaaaaaaaaaaaaaaaaaaaaa", ENVIRON["AWK_PROBE"]) == 1))
   }' 2>/dev/null; then INTERVALS=yes; else INTERVALS=no; fi

if command -v timeout >/dev/null 2>&1 && timeout -k 1 5 true >/dev/null 2>&1; then
  KILLER="timeout -k"
elif command -v gtimeout >/dev/null 2>&1 && gtimeout -k 1 5 true >/dev/null 2>&1; then
  KILLER="gtimeout -k"
elif command -v perl >/dev/null 2>&1; then
  KILLER="perl watcher"
else
  KILLER="none"
fi

echo "=== git-commit cross-environment probe ==="
printf 'os        : %s\n' "$(uname -s) $(uname -r) $(uname -m)"
printf 'bash      : %s\n' "${BASH_VERSION:-?}"
printf 'git       : %s\n' "$(git --version)"
printf 'awk       : %s\n' "$awkver"
printf 'intervals : %s\n' "$INTERVALS"
printf 'force-kill: %s\n' "$KILLER"
echo

# Resolve WORK to a PHYSICAL path before comparing: on macOS /tmp is a symlink
# to /private/tmp, so `git rev-parse --show-toplevel` returns a path that never
# matches the logical one and the safety guard below rejects its own workdir.
mkdir -p "$WORK" || { echo "probe: cannot create $WORK"; exit 2; }
WORK=$(cd "$WORK" && pwd -P)

newrepo() {   # newrepo <name>; cds into a fresh repo, guarded
  rm -rf "$WORK/$1"; mkdir -p "$WORK/$1" || return 1
  cd "$WORK/$1" || return 1
  git init -q . >/dev/null 2>&1 || return 1
  git config user.email probe@example.invalid
  git config user.name probe
  git config commit.gpgsign false
  case "$(git rev-parse --show-toplevel)" in
    "$WORK"/*) : ;;
    *) echo "probe: refusing to run outside $WORK"; exit 2 ;;
  esac
  printf 'seed\n' > seed.txt; git add seed.txt
  git commit -qm "chore: seed" >/dev/null 2>&1
}
cleanup() { cd /; rm -rf "$WORK"; }
trap cleanup EXIT INT TERM

# --- 1. the interval guard, on this host's real awk --------------------------
# The single most important cross-environment check: twelve credential patterns
# are length-anchored, and an awk that treats {16} as literal braces matches
# NOTHING while printing a clean result. Debian 12's default mawk is such an awk.
newrepo intervals || { echo "probe: cannot create a repo"; exit 2; }
printf 'AWS = "AKIAIOSFODNN7EXAMPLE"\nname = "plain"\n' > leak.py
git add leak.py
out=$(bash "$SKILL_DIR/scripts/secret-scan.sh" 2>&1); rc=$?
if [ "$INTERVALS" = no ]; then
  case "$rc:$out" in
    2:*"regex intervals"*)
      case "$out" in
        *SECRET_CANDIDATE*) bad "interval-less awk refuses" "claimed findings it cannot produce" ;;
        *) ok "interval-less awk: refuses with exit 2 instead of a false clean" ;;
      esac ;;
    0:*) bad "interval-less awk refuses" "exited 0 — a CONFIDENT CLEAN on an awk that matches nothing" ;;
    *)   bad "interval-less awk refuses" "rc=$rc out=$out" ;;
  esac
else
  case "$rc:$out" in
    0:*SECRET_CANDIDATE*)
      case "$out" in
        *AKIAIOSFODNN7EXAMPLE*) bad "AKIA key detected + redacted" "the value was printed in full" ;;
        *) ok "AKIA key detected and redacted (exit 0 = scan completed)" ;;
      esac ;;
    *) bad "AKIA key detected" "rc=$rc out=$out" ;;
  esac
fi

# --- 2. non-ASCII paths ------------------------------------------------------
newrepo cjk || exit 2
mkdir -p 源码/模块
printf 'x = 1\n' > 源码/模块/配置.py
printf 'package m\n' > 源码/主程序.go
git add -A
eco=$(bash "$SKILL_DIR/scripts/detect-ecosystems.sh" 2>&1); rc=$?
if [ "$rc" -eq 0 ] && echo "$eco" | grep -q python && echo "$eco" | grep -q go; then
  ok "CJK-named sources select both gates (raw -z paths)"
else
  bad "CJK-named sources select their gates" "rc=$rc out=[$eco]"
fi
sc=$(bash "$SKILL_DIR/scripts/resolve-scope.sh" 2>&1)
case "$sc" in
  *"SCOPE: 源码"*) ok "CJK directory bootstraps a readable scope" ;;
  *) bad "CJK directory bootstraps a scope" "out=[$sc]" ;;
esac

# --- 3. deletions select their gate -----------------------------------------
newrepo deletion || exit 2
printf 'def add(a, b):\n    return a + b\n' > helper.py
printf 'console.log(1);\n' > web.js
git add -A; git commit -qm "chore: sources" >/dev/null 2>&1
git rm -q helper.py
printf 'console.log(2);\n' >> web.js
git add -A
eco=$(bash "$SKILL_DIR/scripts/detect-ecosystems.sh" 2>&1)
if echo "$eco" | grep -q python && echo "$eco" | grep -q node; then
  ok "a deleted .py still selects the python gate"
else
  bad "deleted .py selects its gate" "out=[$eco]"
fi

# --- 4. large blob: a completed context render is not a failure -------------
if [ "$INTERVALS" = no ]; then
  miss "large blob does not false-block" "this awk cannot match; the scan refuses first"
else
  newrepo bigblob || exit 2
  { printf 'KEY = "AKIAIOSFODNN7EXAMPLE"\n'
    i=0; while [ "$i" -lt 20000 ]; do printf 'padding line %d aaaaaaaaaaaaaaaaa\n' "$i"; i=$((i+1)); done
  } > big.py
  git add big.py
  out=$(bash "$SKILL_DIR/scripts/secret-scan.sh" 2>&1); rc=$?
  bytes=$(wc -c < big.py | tr -d ' ')
  if [ "$rc" -eq 0 ] && echo "$out" | grep -q "CONTEXT: big.py:2"; then
    ok "large blob (${bytes}B): context rendered, exit 0 (no SIGPIPE false block)"
  else
    bad "large blob does not false-block" "rc=$rc bytes=$bytes out=$(echo "$out" | tail -2)"
  fi
fi

# --- 5. timeout escalates past TERM -----------------------------------------
if [ "$KILLER" = none ]; then
  miss "TERM-ignoring gate is killed" "no tool on this host can force-kill"
else
  newrepo gate || exit 2
  cat > stubborn.sh <<'EOF'
#!/usr/bin/env bash
trap '' TERM
echo $$ > child.pid
sleep 60
EOF
  chmod +x stubborn.sh
  bash "$SKILL_DIR/scripts/run-gate.sh" -t 1 ./stubborn.sh >/dev/null 2>&1
  rc=$?
  pid=$(cat child.pid 2>/dev/null || echo "")
  alive=no
  if [ -n "$pid" ]; then
    n=0
    while [ "$n" -lt 30 ]; do
      kill -0 "$pid" 2>/dev/null || { alive=no; break; }
      alive=yes; n=$((n+1)); sleep 1
    done
  fi
  if { [ "$rc" -eq 124 ] || [ "$rc" -eq 137 ]; } && [ "$alive" = no ]; then
    ok "TERM-ignoring gate killed via '$KILLER' (exit $rc)"
  else
    bad "TERM-ignoring gate killed" "rc=$rc still_alive=$alive killer=$KILLER"
    [ -n "$pid" ] && kill -9 "$pid" 2>/dev/null
  fi
fi

# --- 6. a tool that cannot force-kill must be skipped, not used -------------
newrepo weak || exit 2
mkdir -p shim
printf '#!/usr/bin/env bash\nif [ "$1" = "-k" ]; then exit 125; fi\necho USED >> "%s/used"\nshift\nexec "$@"\n' "$PWD/shim" > shim/timeout
chmod +x shim/timeout
cp shim/timeout shim/gtimeout
out=$(PATH="$PWD/shim:$PATH" bash "$SKILL_DIR/scripts/run-gate.sh" -t 5 true 2>&1); rc=$?
if [ -f shim/used ]; then
  bad "weak timeout is skipped" "the tool that cannot force-kill was used anyway"
elif command -v perl >/dev/null 2>&1; then
  [ "$rc" -eq 0 ] && ok "weak timeout skipped; fell through to the perl watcher" \
                  || bad "weak timeout skipped then gate runs" "rc=$rc out=$out"
else
  { [ "$rc" -eq 2 ] && echo "$out" | grep -q "refusing to run"; } \
    && ok "weak timeout skipped and, with no alternative, refuses (exit 2)" \
    || bad "weak timeout refusal" "rc=$rc out=$out"
fi

# --- 7. isolation restores the working tree ---------------------------------
newrepo isolation || exit 2
printf 'staged\n' > tracked.txt; git add tracked.txt
printf 'dirt\n' > untracked.txt
out=$(bash "$SKILL_DIR/scripts/stash-guard.sh" sh -c 'test ! -f untracked.txt && echo STAGED_ONLY' 2>&1); rc=$?
if [ "$rc" -eq 0 ] && echo "$out" | grep -q STAGED_ONLY && [ -f untracked.txt ] \
   && [ -z "$(git stash list)" ]; then
  ok "gate saw the staged snapshot; untracked dirt restored; no stash left"
else
  bad "isolation restores the tree" "rc=$rc out=$out dirt=$([ -f untracked.txt ] && echo kept || echo LOST)"
fi

# --- tally -------------------------------------------------------------------
echo
printf 'passed %s | failed %s | skipped %s\n' "$pass" "$fail" "$skip"
[ "$skip" -gt 0 ] && echo "(skips are capabilities this host lacks — gaps in the evidence, not passes)"
if [ "$fail" -gt 0 ]; then echo "RESULT: FAIL"; exit 1; fi
if [ "$pass" -eq 0 ]; then echo "RESULT: nothing was exercised"; exit 2; fi
echo "RESULT: PASS"
