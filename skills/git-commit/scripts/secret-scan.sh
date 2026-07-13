#!/usr/bin/env bash
# secret-scan.sh — scan the STAGED, ADDED lines for likely secrets.
#
# Output contract — exit 0 when the scan COMPLETED (clean, or findings printed
# for triage: "no secret found" is success, not a gate failure); exit 2 when the
# configured scanner itself failed (fail-closed: never mistakable for clean):
#   SECRET_CANDIDATE: <file>:<line>: <redacted>  real source line number; only the
#                                                first 4 matched chars are kept
#   CONTEXT: <file>:<line>: <text>               2 lines around each candidate,
#                                                redacted the same way
#   ALLOWLISTED: <...>                           matched a glob in the COMMITTED
#                                                .commit-secret-allowlist
#   SENSITIVE_FILE: <path>                       staged filename that is key material
#   SCANNER_ERROR: <...>                         gitleaks itself failed — NOT clean
#
# Only ADDED lines are scanned, so removing a leaked secret is never blocked.
# The secret value is never printed — long token-ish runs in context lines are
# masked too, so a multi-line key body (PEM base64) cannot leak via CONTEXT.
# Known limit: file paths containing ':' garble the <file>:<line> fields.
set -u

# The repo's configured scanner, but only when the binary is actually installed
# (a present .gitleaks.toml must not make us invoke a missing command).
gl_failed=0
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
      gl_failed=1
      printf 'SCANNER_ERROR: gitleaks exited %s\n' "$gl_rc"
      [ -n "$gl_err" ] && printf '%s\n' "$gl_err" | sed 's/^/SCANNER_ERROR: gitleaks: /'
      ;;
  esac
fi

sensitive='(^|/)(\.env(\..*)?|id_rsa|id_ed25519|id_dsa|.*\.pem|.*\.p12|.*\.key|.*\.keystore|credentials\.json|service[-_]?account.*\.json)$'
# POSIX classes ([[:space:]]) so the same pattern works in grep -E and in awk's
# dynamic regex (neither understands \s).
secrets='(AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY( BLOCK)?-----|ghp_[A-Za-z0-9]{36}|gho_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{82}|xox[baprs]-[A-Za-z0-9-]+|hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/[A-Za-z0-9]+|AIza[0-9A-Za-z_-]{35}|sk_live_[0-9a-zA-Z]{24,}|rk_live_[0-9a-zA-Z]{24,}|sk-[A-Za-z0-9_-]{20,}|SG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}|mongodb(\+srv)?://[^[:space:]]+@|postgres(ql)?://[^[:space:]]*:[^[:space:]]*@|mysql://[^[:space:]]*:[^[:space:]]*@|password[[:space:]]*=|secret[[:space:]]*=|token[[:space:]]*=|api[_-]?key[[:space:]]*=)'

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

# Staged filenames that are key material by name.
git diff --cached --name-only --diff-filter=d | grep -E "$sensitive" | while IFS= read -r f; do
  if allowlisted "$f"; then
    printf 'ALLOWLISTED: %s (sensitive filename)\n' "$f"
  else
    printf 'SENSITIVE_FILE: %s\n' "$f"
  fi
done

# Added lines: parse the -U0 diff so findings carry REAL new-file line numbers
# (a filtered diff stream's own line numbers are meaningless to the caller),
# and redact from the match start so the value itself is never printed.
findings=$(git diff --cached --diff-filter=d -U0 | SECRETS_RE="$secrets" awk '
  function redact(s, start) { return substr(s, 1, start + 3) "…[REDACTED]" }
  BEGIN { re = ENVIRON["SECRETS_RE"] }
  /^\+\+\+ / { file = substr($0, 5); sub(/^"?b\//, "", file); sub(/"$/, "", file); next }
  /^@@ /    { s = $0; sub(/^@@ -[0-9]+(,[0-9]+)? \+/, "", s); sub(/[ ,].*/, "", s); ln = s + 0; next }
  /^\+/ {
    line = substr($0, 2)
    if (match(line, re)) printf "%s:%d:%s\n", file, ln, redact(line, RSTART)
    ln++
  }
')

[ -n "$findings" ] && printf '%s\n' "$findings" | while IFS= read -r hit; do
  path=${hit%%:*}; rest=${hit#*:}; ln=${rest%%:*}; red=${rest#*:}
  prefix=SECRET_CANDIDATE
  allowlisted "$path" && prefix=ALLOWLISTED
  printf '%s: %s:%s: %s\n' "$prefix" "$path" "$ln" "$red"
  # 2 lines of context from the staged blob. Token-ish runs (20+ chars of
  # [A-Za-z0-9+/=_-]) are masked so key bodies cannot leak via context.
  git show ":$path" 2>/dev/null | SECRETS_RE="$secrets" awk -v n="$ln" -v p="$path" '
    function redact(s, start) { return substr(s, 1, start + 3) "…[REDACTED]" }
    BEGIN { re = ENVIRON["SECRETS_RE"] }
    NR >= n - 2 && NR <= n + 2 && NR != n {
      if (match($0, re))                            $0 = redact($0, RSTART)
      else if (match($0, /[A-Za-z0-9+\/=_-]{20,}/)) $0 = redact($0, RSTART)
      printf "CONTEXT: %s:%d: %s\n", p, NR, $0
    }
    NR > n + 2 { exit }
  '
done

# Fail-closed: a broken scanner must surface in the exit code, not only in
# stdout text the caller might skim past. The regex fallback above still ran,
# but it is NOT equivalent coverage.
[ "$gl_failed" = 1 ] && exit 2
exit 0