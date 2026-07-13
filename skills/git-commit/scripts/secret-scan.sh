#!/usr/bin/env bash
# secret-scan.sh — scan the STAGED, ADDED lines for likely secrets.
#
# Prints `SENSITIVE_FILE:` / `SECRET_CANDIDATE:` lines for the caller to triage,
# and ALWAYS exits 0 — "no secret found" is success, not a gate failure (a bare
# `grep`/`rg` returns 1 on no match, which callers misread as "scan failed").
# Only ADDED lines are scanned, so removing a leaked secret is never blocked.
set -u

# The repo's configured scanner, but only when the binary is actually installed
# (a present .gitleaks.toml must not make us invoke a missing command).
if command -v gitleaks >/dev/null 2>&1; then
  # `gitleaks git --pre-commit --staged` is the current form; `protect`/`detect`
  # are deprecated since v8.19. Non-zero just means "findings" — surface, do not abort.
  gitleaks git --pre-commit --redact --staged --no-banner 2>/dev/null || true
fi

sensitive='(^|/)(\.env(\..*)?|id_rsa|id_ed25519|id_dsa|.*\.pem|.*\.p12|.*\.key|.*\.keystore|credentials\.json|service[-_]?account.*\.json)$'
# POSIX classes ([[:space:]]) so the same pattern works under both `rg` and `grep -E`
# (grep -E does not understand \s).
secrets='(AKIA[0-9A-Z]{16}|-----BEGIN (RSA|EC|OPENSSH|DSA|PGP|PRIVATE) KEY-----|ghp_[A-Za-z0-9]{36}|gho_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{82}|xox[baprs]-[A-Za-z0-9-]+|hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/[A-Za-z0-9]+|AIza[0-9A-Za-z_-]{35}|sk_live_[0-9a-zA-Z]{24,}|rk_live_[0-9a-zA-Z]{24,}|sk-[A-Za-z0-9_-]{20,}|SG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}|mongodb(\+srv)?://[^[:space:]]+@|postgres(ql)?://[^[:space:]]*:[^[:space:]]*@|mysql://[^[:space:]]*:[^[:space:]]*@|password[[:space:]]*=|secret[[:space:]]*=|token[[:space:]]*=|api[_-]?key[[:space:]]*=)'

# rg when available, else grep -E — two explicit branches, no string-splitting
# of a "rg -n" variable (which breaks under zsh and other non-Bash shells).
search() {
  if command -v rg >/dev/null 2>&1; then rg -n "$1"; else grep -En "$1"; fi
}

files=$(git diff --cached --name-only --diff-filter=d | { search "$sensitive" || true; })
added=$(git diff --cached --diff-filter=d -U0 | grep -E '^\+[^+]' | { search "$secrets" || true; })

[ -n "$files" ] && printf 'SENSITIVE_FILE: %s\n' "$files"
[ -n "$added" ] && printf 'SECRET_CANDIDATE: %s\n' "$added"
exit 0