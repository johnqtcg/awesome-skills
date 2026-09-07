#!/usr/bin/env bash
# resolve-scope.sh — decide the Conventional Commits scope for the staged
# change, by the rules in SKILL.md §5, as an EXECUTABLE artifact.
#
#   Usage: bash resolve-scope.sh
#   Output (always both lines):
#     SCOPE: <name>            or  SCOPE: (none)
#     SCOPE_SOURCE: canonical | bootstrap | omitted
#   Exit 0 = decided. Exit 2 = a stage failed (unreadable repo, broken awk).
#   Never guess a scope from a failed read: an empty path list looks exactly
#   like "nothing staged", which would answer `omitted` — a confident wrong
#   answer rather than a failure.
#
# Why a script and not prose: the rules are purely mechanical (count, compare,
# strip, match), so leaving them as prose forced the golden tests to re-derive
# them in Python — and a test that asserts "my Python agrees with my Python"
# proves nothing about the skill. One executable source, tested directly.
#
# Rules:
#   1. Scan at most the last 50 commits (an older convention is not current).
#   2. A scope used >= 3 times there is CANONICAL.
#   3. A canonical scope is adopted only when it appears as a path segment of a
#      staged file AND no OTHER canonical scope also appears in the staged set.
#      That second half is the anti-mislabel rule: staging auth/ + billing/ in a
#      repo where both are canonical is a mixed commit, so scope is omitted
#      rather than silently labelled with whichever is more frequent. A staged
#      path that matches no canonical scope (CHANGELOG.md) does not block.
#   4. Fewer than 10 conventional commits total => the convention is not
#      established yet: BOOTSTRAP the scope from staged directories, dropping
#      generic containers. One stable directory => use it; otherwise omit.
#   5. Anything else omits. A scope is never invented from filenames or text.
set -u
set -o pipefail

if [ "$(git rev-parse --is-inside-work-tree 2>/dev/null)" != "true" ]; then
  echo "resolve-scope: not inside a git work tree" >&2
  exit 2
fi

# An unborn HEAD (no commits yet) is a legitimate empty history, NOT a failure.
# Distinguishing it here keeps a genuine `git log` failure fail-closed.
if git rev-parse --verify -q HEAD >/dev/null 2>&1; then
  if ! HIST=$(git log --oneline --no-decorate -n 50 2>/dev/null); then
    echo "resolve-scope: git log failed" >&2
    exit 2
  fi
else
  HIST=""
fi

# `-z` gives raw paths. Plain --name-only is display output: a non-ASCII path
# arrives escaped as "\346\272\220…", which would strip the real directory names
# a bootstrap scope is derived from. (`tr` splits a path containing a literal
# newline; that can only add a candidate directory, and extra candidates omit
# the scope rather than inventing one — the safe direction.)
if ! STAGED=$(git diff --cached -z --name-only --no-renames 2>/dev/null | tr '\0' '\n'); then
  echo "resolve-scope: could not read staged paths" >&2
  exit 2
fi

if ! HIST="$HIST" STAGED="$STAGED" LC_ALL=C awk '
BEGIN {
  split("src lib pkg cmd internal app apps service services module modules " \
        "package packages component components test tests testdata", g, " ")
  for (i in g) generic[g[i]] = 1

  # --- history: count conventional-commit scopes -------------------------
  cc = 0
  n = split(ENVIRON["HIST"], lines, "\n")
  for (i = 1; i <= n; i++) {
    L = lines[i]
    if (L !~ /^[0-9a-f]+ [a-z]+(\([a-z0-9_-]+\))?!?: [^ ]/) continue
    cc++
    if (match(L, /\([a-z0-9_-]+\)/))
      count[substr(L, RSTART + 1, RLENGTH - 2)]++
  }

  # --- staged paths -------------------------------------------------------
  np = 0
  m = split(ENVIRON["STAGED"], praw, "\n")
  for (i = 1; i <= m; i++) if (praw[i] != "") paths[++np] = praw[i]
  if (np == 0) { emit("", "omitted"); exit }

  # --- rule 2+3: canonical --------------------------------------------------
  matched = 0; chosen = ""
  for (s in count) {
    if (count[s] < 3) continue
    for (i = 1; i <= np; i++) {
      if (index("/" paths[i] "/", "/" s "/") > 0) {
        matched++; chosen = s
        break
      }
    }
  }
  if (matched == 1) { emit(chosen, "canonical"); exit }
  if (matched > 1)  { emit("", "omitted");       exit }   # mixed known scopes

  # --- rule 4: bootstrap ----------------------------------------------------
  if (cc < 10) {
    nd = 0
    for (i = 1; i <= np; i++) {
      k = split(paths[i], seg, "/")
      d = ""
      for (j = 1; j < k; j++) if (!(seg[j] in generic)) d = d (d == "" ? "" : "/") seg[j]
      if (d != "") dirs[++nd] = d
    }
    if (nd > 0) {
      # Longest common directory prefix; its last element is the scope.
      pc = split(dirs[1], pref, "/")
      for (i = 2; i <= nd; i++) {
        c = split(dirs[i], cur, "/")
        keep = 0
        for (j = 1; j <= (pc < c ? pc : c); j++) {
          if (pref[j] != cur[j]) break
          keep = j
        }
        pc = keep
      }
      if (pc > 0) { emit(pref[pc], "bootstrap"); exit }
      # No shared prefix: accept only if every path ends in the same directory.
      last = ""; same = 1
      for (i = 1; i <= nd; i++) {
        c = split(dirs[i], cur, "/")
        if (last == "") last = cur[c]
        else if (last != cur[c]) { same = 0; break }
      }
      if (same && last != "") { emit(last, "bootstrap"); exit }
    }
  }
  emit("", "omitted")
}
function emit(scope, source) {
  printf "SCOPE: %s\n", (scope == "" ? "(none)" : scope)
  printf "SCOPE_SOURCE: %s\n", source
}
'; then
  # A silent awk failure would print nothing, and a caller reading no SCOPE line
  # has no answer at all — say so rather than let it look like an omitted scope.
  echo "resolve-scope: scope resolution failed" >&2
  exit 2
fi
