#!/usr/bin/env bash
# secret-scan.sh — scan the STAGED, ADDED lines for likely secrets.
#
# Output contract — exit 0 when the scan COMPLETED (clean, or findings printed
# for triage: "no secret found" is success, not a gate failure); exit 2 when the
# scan could NOT complete (fail-closed: never mistakable for clean):
#   SECRET_CANDIDATE: <file>:<line>: <redacted>  real source line number; the
#                                                value is cut at the match
#   CONTEXT: <file>:<line>: <text>               2 lines around each candidate,
#                                                masked the same way
#   ALLOWLISTED: <...>                           matched a glob in the COMMITTED
#                                                .commit-secret-allowlist
#   SENSITIVE_FILE: <path>                       staged filename that is key material
#   SCANNER_ERROR: <...>                         the scan itself failed — NOT clean
#
# Only ADDED lines are scanned, so removing a leaked secret is never blocked.
#
# FAIL-CLOSED AT EVERY STAGE. Not just the git reads: `set -o pipefail` plus a
# status check on each pipeline means a failure anywhere in the chain — git,
# tr, or the awk that classifies and redacts — raises SCANNER_ERROR and exit 2.
# Checking only git was not enough: with a broken `awk` the scan still exited 0
# having printed only the filename check, so a staged AWS key read as "clean".
# The rule is that no stage may fail while the scan claims to have completed.
#
# PATHS ARE READ RAW. `--name-only` is DISPLAY output: with the default
# core.quotePath a non-ASCII path arrives as "\346\272\220…", so `*.pem` no longer
# matches and the extension is unusable. Filenames come from `-z` (NUL-separated,
# unescaped) and the patch stream runs under `-c core.quotePath=false`.
#
# REDACTION CONTRACT. Two decisions, deliberately separated:
#
#   DETECT (is this line a finding?) — a known credential shape, or a
#   `<sensitive-key><separator>` pair (`password: x`, `API_KEY = x`,
#   `"client_secret":x` — case-insensitive, `:` and `=` both count).
#
#   CUT (where does the line stop printing?) — the EARLIEST of those two AND of
#   any run of 20+ token-ish characters. The blob rule cannot decide detection
#   (every long identifier would become a finding) but it must always constrain
#   the cut. It previously applied only when nothing else matched, so
#   `SESSION=<40 chars> password = x` cut at `password` and printed the session
#   token in full — on the finding line itself, not only in context.
#
# Residual risk, stated rather than papered over: a SHORT literal not attached
# to a sensitive key (a bare "hunter2" in a list) matches no rule and will
# print. CONTEXT is a triage aid, not a sanitiser — do not paste raw output
# into a public channel.
#
# Known limit: file paths containing ':' garble the <file>:<line> fields.
set -u
set -o pipefail

FAILED=0
fail() { printf 'SCANNER_ERROR: %s\n' "$1"; FAILED=1; }

# Every credential pattern below is length-anchored by a regex interval —
# AKIA[0-9A-Z]{16}, ghp_[A-Za-z0-9]{36}, the 20+ blob rule, twelve in total.
# An awk build without interval support (historical mawk, some busybox builds,
# gawk before --re-interval became default) treats `{16}` as LITERAL braces, so
# every one of those patterns matches nothing and the scan prints a confident
# clean result. That is the worst failure mode this script has, and it is
# invisible in its output — so probe the capability and refuse instead.
# Both forms are probed because the script uses both: a literal regex and one
# compiled at runtime from the environment.
if ! AWK_PROBE='[a-z]{20,}' awk 'BEGIN {
       exit !((match("aaaaaaaaaaaaaaaaaaaaaaaaa", /[a-z]{20,}/) == 1) &&
              (match("aaaaaaaaaaaaaaaaaaaaaaaaa", ENVIRON["AWK_PROBE"]) == 1))
     }' 2>/dev/null; then
  fail "this awk does not support regex intervals ({n,m}); every length-anchored credential pattern would silently never match"
  exit 2
fi

# A broken/absent repo must not read as "nothing staged, therefore clean".
if [ "$(git rev-parse --is-inside-work-tree 2>/dev/null)" != "true" ]; then
  fail "not inside a git work tree — cannot scan the index"
  exit 2
fi

# The repo's configured scanner, but only when the binary is actually installed
# (a present .gitleaks.toml must not make us invoke a missing command).
if command -v gitleaks >/dev/null 2>&1; then
  # `gitleaks git --pre-commit --staged` is the current form; `protect`/`detect`
  # are deprecated since v8.19. The DEFAULT findings exit code (1) is ambiguous —
  # gitleaks also exits 1 on execution errors — so pin findings to 10 and treat
  # everything except 0/10 as a scanner failure (no FTL/ERR text heuristics).
  # Capture stderr via fd swap (no temp file — mktemp fails in sandboxed and
  # restricted-TMPDIR environments) while findings pass through on stdout.
  { gl_err=$(gitleaks git --pre-commit --redact --staged --no-banner --exit-code 10 2>&1 1>&3); } 3>&1
  gl_rc=$?
  case "$gl_rc" in
    0)  ;;   # clean
    10) ;;   # findings — already printed (redacted) on stdout for triage
    *)
      # Verified against real binaries: v8.18.4 has no `git` subcommand at all
      # and exits 1 for any invocation; v8.24.3 has it and honours --exit-code.
      # Failing closed here is right, but the operator needs to know why.
      fail "gitleaks exited $gl_rc — note that \`gitleaks git --pre-commit --staged\` needs gitleaks >= 8.19; older builds have no \`git\` subcommand and exit 1 for everything"
      [ -n "$gl_err" ] && printf '%s\n' "$gl_err" | sed 's/^/SCANNER_ERROR: gitleaks: /'
      ;;
  esac
fi

sensitive='(^|/)(\.env(\..*)?|id_rsa|id_ed25519|id_dsa|.*\.pem|.*\.p12|.*\.key|.*\.keystore|credentials\.json|service[-_]?account.*\.json)$'

# Two regexes, because one cannot serve both jobs. HIGH_RE is case-SENSITIVE:
# `AKIA` and `-----BEGIN` are literal, and lowercasing them destroys the match.
# KEYED_RE is matched against tolower(line) so `PASSWORD=`, `Password:` and
# `password =` all hit — the old single case-sensitive pattern required a
# literal lowercase key AND an `=`, so every JSON/YAML secret was invisible.
# POSIX classes ([[:space:]]) so the same source works in grep -E and in awk.
HIGH_RE='(AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY( BLOCK)?-----|ghp_[A-Za-z0-9]{36}|gho_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{82}|xox[baprs]-[A-Za-z0-9-]+|hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/[A-Za-z0-9]+|AIza[0-9A-Za-z_-]{35}|sk_live_[0-9a-zA-Z]{24,}|rk_live_[0-9a-zA-Z]{24,}|sk-[A-Za-z0-9_-]{20,}|SG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}|mongodb(\+srv)?://[^[:space:]]+@|postgres(ql)?://[^[:space:]]*:[^[:space:]]*@|mysql://[^[:space:]]*:[^[:space:]]*@)'
KEYED_RE='(password|passwd|passphrase|pwd|secret|token|credential|authorization|api[_-]?key|apikey|access[_-]?key|secret[_-]?key|private[_-]?key|client[_-]?secret|auth[_-]?token)("|'"'"')?[[:space:]]*[:=]'

# COMMITTED allowlist only — a staged-but-uncommitted allowlist must not
# self-authorize the very commit that introduces it.
allow=$(git show HEAD:.commit-secret-allowlist 2>/dev/null || true)
allowlisted() {
  [ -n "$allow" ] || return 1
  while IFS= read -r pat; do
    case $pat in ''|'#'*) continue ;; esac
    # shellcheck disable=SC2254 — unquoted on purpose: the entry is a glob
    case $1 in $pat) return 0 ;; esac
  done <<EOF
$allow
EOF
  return 1
}

# Staged filenames that are key material by name. Deletions are excluded here
# (removing a .pem is the fix, not the leak) — unlike detect-ecosystems.sh,
# which must see deletions because they change what still compiles.
if ! staged=$(git diff --cached -z --name-only --diff-filter=d 2>/dev/null | tr '\0' '\n'); then
  fail "could not read staged filenames — sensitive files were NOT checked"
elif ! matches=$(printf '%s\n' "$staged" | SENSITIVE_RE="$sensitive" awk '
        BEGIN { re = ENVIRON["SENSITIVE_RE"] }
        $0 != "" && $0 ~ re { print }'); then
  # grep would exit 1 on "no match" — the normal case — which pipefail cannot
  # tell apart from a real failure. awk exits 0 unless it actually breaks.
  fail "sensitive-filename matching failed — staged filenames were NOT checked"
else
  # No subshell: a pipe would run this loop in one, and a FAILED set inside it
  # would be discarded on exit.
  if [ -n "$matches" ]; then
    while IFS= read -r f; do
      if allowlisted "$f"; then
        printf 'ALLOWLISTED: %s (sensitive filename)\n' "$f"
      else
        printf 'SENSITIVE_FILE: %s\n' "$f"
      fi
    done <<EOF
$matches
EOF
  fi
fi

# Added lines: parse the -U0 diff so findings carry REAL new-file line numbers
# (a filtered diff stream's own line numbers are meaningless to the caller).
# LC_ALL=C keeps tolower() bytewise: a locale-aware tolower can change byte
# length, which would slide the redaction cut and expose part of the value.
# core.quotePath=false keeps the `+++ b/<path>` header literal, so a finding in
# 源码/配置.py is labelled with the path `git show` can actually open.
if ! diff_out=$(git -c core.quotePath=false diff --cached --diff-filter=d -U0 2>/dev/null); then
  fail "could not read the staged diff — staged content was NOT scanned"
  diff_out=""
fi

if ! findings=$(printf '%s\n' "$diff_out" | LC_ALL=C HIGH_RE="$HIGH_RE" KEYED_RE="$KEYED_RE" awk '
  function redact(s, start) { return substr(s, 1, start + 3) "…[REDACTED]" }
  # BLOB never decides detection — only how early the line is cut.
  function blob_at(line) { return match(line, /[A-Za-z0-9+\/=_-]{20,}/) ? RSTART : 0 }
  function earlier(a, b) { if (!a) return b; if (!b) return a; return a < b ? a : b }
  function detect_at(line,   p, q) {
    p = match(line, HIGH)           ? RSTART : 0
    q = match(tolower(line), KEYED) ? RSTART : 0
    return earlier(p, q)
  }
  function cut_at(line) { return earlier(detect_at(line), blob_at(line)) }
  BEGIN { HIGH = ENVIRON["HIGH_RE"]; KEYED = ENVIRON["KEYED_RE"] }
  /^\+\+\+ / { file = substr($0, 5); sub(/^"?b\//, "", file); sub(/"$/, "", file); next }
  /^@@ /    { s = $0; sub(/^@@ -[0-9]+(,[0-9]+)? \+/, "", s); sub(/[ ,].*/, "", s); ln = s + 0; next }
  /^\+/ {
    line = substr($0, 2)
    if (detect_at(line)) printf "%s:%d:%s\n", file, ln, redact(line, cut_at(line))
    ln++
  }
'); then
  # Without this the scan printed nothing and exited 0 — the exact shape of a
  # clean result — whenever awk was missing, miscompiled its regex, or died.
  fail "content scan failed — staged lines were NOT scanned"
  findings=""
fi

if [ -n "$findings" ]; then
 while IFS= read -r hit; do
  path=${hit%%:*}; rest=${hit#*:}; ln=${rest%%:*}; red=${rest#*:}
  prefix=SECRET_CANDIDATE
  allowlisted "$path" && prefix=ALLOWLISTED
  printf '%s: %s:%s: %s\n' "$prefix" "$path" "$ln" "$red"
  # 2 lines of context from the staged blob, masked by the same contract.
  if ! blob=$(git show ":$path" 2>/dev/null); then
    printf 'CONTEXT: %s: (unavailable — could not read the staged blob)\n' "$path"
    continue
  fi
  # Fed by REDIRECT, not a pipe. The extractor stops at `NR > n + 2`, which on a
  # large blob leaves the writer mid-write: it takes SIGPIPE and exits 141, and
  # pipefail would then report a completed context render as a scan failure — a
  # false block that grows with file size (clean at 3 lines, exit 2 at 20k).
  # Process substitution keeps the early exit (a full scan per finding is O(K*N))
  # while excluding the writer from the status, so `if !` still measures exactly
  # what it is meant to: whether awk itself failed. A here-string would also
  # work but can spill to a temp file on bash < 5.1, and this script must run
  # where TMPDIR is not writable.
  if ! LC_ALL=C HIGH_RE="$HIGH_RE" KEYED_RE="$KEYED_RE" \
    awk -v n="$ln" -v pfile="$path" '
    function redact(s, start) { return substr(s, 1, start + 3) "…[REDACTED]" }
    # BLOB never decides detection — only how early the line is cut.
    function blob_at(line) { return match(line, /[A-Za-z0-9+\/=_-]{20,}/) ? RSTART : 0 }
    function earlier(a, b) { if (!a) return b; if (!b) return a; return a < b ? a : b }
    function detect_at(line,   p, q) {
      p = match(line, HIGH)           ? RSTART : 0
      q = match(tolower(line), KEYED) ? RSTART : 0
      return earlier(p, q)
    }
    function cut_at(line) { return earlier(detect_at(line), blob_at(line)) }
    BEGIN { HIGH = ENVIRON["HIGH_RE"]; KEYED = ENVIRON["KEYED_RE"] }
    NR >= n - 2 && NR <= n + 2 && NR != n {
      hit = cut_at($0)
      if (hit) $0 = redact($0, hit)
      printf "CONTEXT: %s:%d: %s\n", pfile, NR, $0
    }
    NR > n + 2 { exit }
  ' < <(printf '%s\n' "$blob"); then
    # Context is a triage aid, but a failure here means the redactor did not run
    # — so it must not be silently reported as "no context".
    fail "context rendering failed for $path"
  fi
 done <<EOF
$findings
EOF
fi

# Fail-closed: a broken scanner must surface in the exit code, not only in
# stdout text the caller might skim past. Any regex findings above still stand,
# but the scan is NOT equivalent coverage.
[ "$FAILED" = 1 ] && exit 2
exit 0
