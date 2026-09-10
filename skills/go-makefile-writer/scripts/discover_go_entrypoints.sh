#!/usr/bin/env bash
# Discover Go entrypoints (packages named "main") via the Go toolchain.
#
# Output (tab-separated):
#   kind    name    target_name    dir    confidence
#
# kind: api | consumer | cron | worker | migrate | seed | cli | tool | other
# target_name: the recommended Makefile target suffix (e.g. "consumer-sync")
# confidence:
#   confirmed — `go list` reported this package's name as "main". Safe to turn
#               straight into a build target.
#   candidate — a filename guess made because the toolchain could not be asked
#               about that subtree. NOT package-level truth: report it to the
#               user for confirmation instead of emitting a build target for it.
# A caller that treats the two alike re-introduces the bug this column exists
# for, so the column is always present — there is no 4-field output mode.
#
# Usage:
#   ./discover_go_entrypoints.sh [project-root]
#   ./discover_go_entrypoints.sh --json [project-root]
#   ./discover_go_entrypoints.sh --modules [project-root]
#
# Exit status — this is the completeness signal, read it before the output:
#   0  query complete; the output is the whole answer. No rows means the repo
#      genuinely has no programs (library-only), and that conclusion is safe.
#   2  bad project root.
#   3  --modules only: zero modules, which is never a legitimate answer.
#   4  query INCOMPLETE; the toolchain could not be asked about some or all of
#      the tree. No rows here means "unknown", NOT "library-only". Any rows are
#      marked `candidate`.
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

# Module directories present on disk, relative to the root ("." for the root
# module). One implementation, used by BOTH --modules tier 3 and entrypoint
# discovery — they answer the same question ("which directories are modules?")
# and had drifted apart, which is how entrypoint discovery came to look only at
# the root module.
list_module_dirs() {
  if command -v rg >/dev/null 2>&1; then
    rg --files -g 'go.mod' 2>/dev/null
  else
    find . -name go.mod -type f 2>/dev/null
  fi \
    | grep -Ev '(^|/)(vendor|testdata|examples?)(/|$)' \
    | while IFS= read -r f; do dirname "$f"; done \
    | sed 's|^\./||' \
    | LC_ALL=C sort -u
}

# --modules: list the repo's module directories. Three tiers, in order:
#   1. go.work workspace via the toolchain (authoritative — exact `use` set);
#   2. go.work parsed by hand when `go` is absent (block + single-line forms,
#      strips `//` comments, unquotes quoted paths);
#   3. NO go.work — a traditional multi-module repo: scoped `go.mod` search
#      excluding vendor/testdata/examples/tool-only modules.
# A bare `rg --files go.mod` gets tier 1/2 wrong by including modules the
# workspace deliberately omits; tier 3 is the only place a file search belongs.
if $modules_mode; then
  # `go env GOWORK` prints the literal string "off" when workspace mode has been
  # switched off explicitly (GOWORK=off / -workfile=off). "off" is non-empty, so
  # a bare `-n` test treats it as a workspace path and asks the toolchain for
  # `go list -m`, which then answers for whichever single module the cwd is in —
  # or for nothing at all in a monorepo with no root go.mod. Either way the
  # workspace's real member modules disappear and an aggregate target loops over
  # the wrong set while reporting success. Treat "off" as "no workspace" and fall
  # through to the file-based search, which finds every module regardless.
  gowork="$(go env GOWORK 2>/dev/null || true)"
  mod_list=$(if command -v go >/dev/null 2>&1 && [ -n "$gowork" ] && [ "$gowork" != "off" ]; then
    go list -m -f '{{.Dir}}' 2>/dev/null || true
  elif [ -f go.work ] && [ "$gowork" != "off" ]; then
    awk '
      { sub(/\/\/.*/, "") }                                    # strip line comments
      /^[[:space:]]*use[[:space:]]*\(/ { inblk=1; next }        # block: use (
      inblk && /^[[:space:]]*\)[[:space:]]*$/ { inblk=0; next } # block: )
      inblk {
        sub(/^[[:space:]]+/, ""); sub(/[[:space:]]+$/, "")      # trim (keeps inner spaces)
        sub(/^"/, ""); sub(/"$/, "")                            # unquote
        if ($0 != "") print
        next
      }
      /^[[:space:]]*use[[:space:]]/ {                           # single-line: use ./x
        sub(/^[[:space:]]*use[[:space:]]+/, "")
        sub(/^[[:space:]]+/, ""); sub(/[[:space:]]+$/, "")
        sub(/^"/, ""); sub(/"$/, "")
        if ($0 != "") print
      }
    ' go.work
  else
    # Tier 3: traditional multi-module repo (no go.work).
    list_module_dirs
  fi)

  # Finding zero modules is never a legitimate outcome of --modules: every Go
  # repo has at least one go.mod. Exiting 0 with empty output lets an aggregate
  # target ("for m in $(MODULES) ...") iterate over nothing and report success,
  # which is the exact failure this flag exists to prevent. No temp file here on
  # purpose — a probe script has to run where /tmp is not writable.
  if [ -z "$mod_list" ]; then
    echo "# no Go modules found under $(pwd)" >&2
    if [ "$gowork" = "off" ]; then
      echo "# note: GOWORK=off, so the go.work member list was deliberately ignored" >&2
    fi
    exit 3
  fi
  printf '%s\n' "$mod_list"
  exit 0
fi

# Find entrypoint DIRECTORIES — packages whose name is "main".
#
# Ask the toolchain, not the filesystem. A `cmd/**/main.go` glob is wrong in
# both directions, and a real repo hits both:
#   - it MISSES a program whose file is not called main.go (cmd/app/entry.go)
#     and any program outside cmd/ (a root-level main.go, tools/gen/gen.go);
#   - it FALSELY REPORTS a non-main package that merely happens to contain a
#     file named main.go (internal/helper/main.go).
# `go list` answers at package level, which is the only level where "is this an
# entrypoint" is actually defined.
# `go list ./...` is run with GOWORK=off on purpose. Inside a workspace the
# toolchain refuses any directory that is not a `use` member —
# "directory prefix . does not contain modules listed in go.work" — so a
# workspace root reports zero entrypoints even when programs sit right there.
# Entrypoint discovery is a question about the files on disk, not about which
# modules the current workspace happens to select, so the workspace is stepped
# around rather than obeyed.
topdir="$PWD"

# Ask ONE module. Prints the absolute dirs of its main packages; the return
# status is `go list`'s own, unmangled — the previous version ran it through a
# `| grep | sort` pipeline, whose status is the last stage's, so a failed query
# was indistinguishable from a successful empty one.
#
# Measured: `go list -f '{{.Name}}'` exits 0 for a module with no packages at
# all, for a library-only module, for a module whose source does not parse, and
# for a module with an unresolvable import — it only needs the package clause.
# It exits non-zero for exactly one thing: no module here to ask about. So a
# zero status means the answer is authoritative even when it is EMPTY, and
# "library-only" and "cannot ask" are different states, not one.
query_module() {
  ( cd "$1" 2>/dev/null || exit 70
    GOWORK=off go list -f '{{if eq .Name "main"}}{{.Dir}}{{end}}' ./... 2>/dev/null )
}

# Fallback for a subtree the toolchain could not be asked about. Still reads
# each file's package clause: a filename is not a package declaration, and
# `internal/helper/main.go` saying `package helper` is not an entrypoint.
glob_candidates() {
  local base="$1" files
  if command -v rg >/dev/null 2>&1; then
    files=$(rg --files "$base/cmd" 2>/dev/null | grep '/main\.go$') || true
  else
    files=$(find "$base/cmd" -name 'main.go' -type f 2>/dev/null) || true
  fi
  printf '%s\n' "$files" | grep -v '^$' | while IFS= read -r f; do
    if grep -Eq '^package[[:space:]]+main([[:space:]]|$)' "$f" 2>/dev/null; then
      dirname "$f"
    fi
  done | sed 's|^\./||' | LC_ALL=C sort -u
}

# Every module is queried and the results are UNIONED. Stopping at the first
# module that answered — the old `if [ -z "$dirs" ]` guard — hid every program
# in a nested module whenever the root module also had one.
confirmed=""
unqueried=""
query_errors=""
if command -v go >/dev/null 2>&1; then
  module_dirs="$(list_module_dirs)"
  if [ -z "$module_dirs" ]; then
    unqueried="."
    query_errors="  .: no go.mod found in this tree
"
  else
    while IFS= read -r moddir; do
      [ -z "$moddir" ] && continue
      out=$(query_module "$moddir")
      if [ $? -eq 0 ]; then
        confirmed="$confirmed$out
"
      else
        unqueried="$unqueried$moddir
"
        # Say WHY. The failure is usually "no module here", but it can equally
        # be an unreadable build cache or a GOFLAGS mistake, and a notice that
        # only ever says "no module" sends the reader looking in the wrong
        # place. Cheap: one extra call, and only on the failing path.
        reason=$( cd "$moddir" 2>/dev/null && \
                  GOWORK=off go list -f '' ./... 2>&1 >/dev/null | head -n 1 )
        query_errors="$query_errors  $moddir: ${reason:-unknown error}
"
      fi
    done <<EOF
$module_dirs
EOF
  fi
else
  unqueried="."
  query_errors="  .: no 'go' on PATH
"
fi

confirmed=$(printf '%s\n' "$confirmed" \
  | sed "s|^$topdir/||; s|^$topdir\$|.|" | grep -v '^$' | LC_ALL=C sort -u) || confirmed=""

candidates=""
if [ -n "$(printf '%s' "$unqueried" | tr -d '[:space:]')" ]; then
  echo "# note: could not ask the Go toolchain about:" >&2
  printf '%s' "$query_errors" | sed 's/^/# /' >&2
  echo "#       falling back to a cmd/**/main.go glob there. Those rows are marked" >&2
  echo "#       'candidate' — confirm them before generating build targets." >&2
  candidates=$(while IFS= read -r u; do
                 [ -z "$u" ] && continue
                 glob_candidates "$u"
               done <<EOF
$unqueried
EOF
              ) || candidates=""
  # Never downgrade something the toolchain already confirmed.
  if [ -n "$confirmed" ] && [ -n "$candidates" ]; then
    candidates=$(printf '%s\n' "$candidates" | grep -vxF -f <(printf '%s\n' "$confirmed")) || candidates=""
  fi
fi

# A STABLE TOKEN, always printed — including when nothing was found, which is
# exactly when a caller most needs to know whether the answer came from the
# toolchain or from a filename guess. It is a fixed word rather than a sentence
# because callers and tests match on it; the prose that follows may be reworded.
#   go-list      every module answered; the result is package-level truth
#   go-list+glob some subtree could not be queried, so it also holds guesses
#   glob         nothing could be queried; every row is a guess
if [ -n "$(printf '%s' "$unqueried" | tr -d '[:space:]')" ]; then
  if [ -n "$confirmed" ]; then
    discovery_method="go-list+glob"
  else
    discovery_method="glob"
  fi
else
  discovery_method="go-list"
fi
echo "# discovery: $discovery_method" >&2

# EXIT STATUS IS THE COMPLETENESS SIGNAL, and it is the only safe place for it.
#
#   0  the query was complete. Whatever was printed is the whole answer, and an
#      EMPTY answer means this repo genuinely has no programs — a library.
#   4  the query was incomplete. Anything printed is a filename guess, and
#      NOTHING printed means "unknown", not "no programs".
#
# Before this split, both cases exited 0 with no output and the same "no
# entrypoints" line, so a repo whose toolchain simply could not run (a bad
# GOFLAGS, an unreadable build cache, a missing go.mod) was indistinguishable
# from a library-only repo — and the project-shape table in SKILL.md reads
# "reports no package main" as "library: emit no build targets". A normal
# program with a root entry.go silently lost every build target it should have
# had. The stderr diagnostic was there, but a diagnostic nobody is required to
# read is not a signal.
if [ "$discovery_method" = "go-list" ]; then
  if [ -z "$confirmed" ]; then
    echo "# No Go entrypoints (package main) found — this repo has no programs" >&2
    echo "# (the query was COMPLETE: every module answered. Safe to treat as library-only.)" >&2
  fi
else
  echo "# WARNING: entrypoint discovery is INCOMPLETE — do not conclude 'library-only'." >&2
  if [ -z "$confirmed" ] && [ -z "$candidates" ]; then
    echo "# Nothing was found, but nothing could be checked either. This is 'unknown'." >&2
  fi
  echo "# Fix the toolchain error above, or confirm the 'candidate' rows by hand." >&2
  incomplete=4
fi
incomplete="${incomplete:-0}"

if [ -z "$confirmed" ] && [ -z "$candidates" ]; then
  exit "$incomplete"
fi

classify() {
  local dir="$1"
  local confidence="$2"

  # Single-level: cmd/<kind>/main.go
  # Multi-level:  cmd/<kind>/<name>/main.go  or  cmd/<kind>/<sub>/<name>/main.go

  # Known kind prefixes (extend this list for new conventions)
  local known_kinds="api consumer cron worker migrate seed cli tool"

  # Entrypoints outside cmd/ are legitimate (a root-level main.go, tools/gen).
  # Name them from the directory rather than pretending they follow the cmd/
  # convention, and for the module root fall back to the module's own name.
  if [ "$dir" = "." ]; then
    local root_name
    root_name=$(basename "$(pwd)")
    # Read ./go.mod directly. `go list -m` answers for the *selected* module,
    # which inside a workspace is a member, not the directory we are naming.
    if [ -f go.mod ]; then
      local mod
      mod=$(awk '$1 == "module" { print $2; exit }' go.mod) || mod=""
      [ -n "$mod" ] && root_name=$(basename "$mod")
    fi
    if $json_mode; then
      printf '{"kind":"other","name":"%s","target":"%s","dir":".","confidence":"%s"}\n' \
        "$root_name" "$root_name" "$confidence"
    else
      printf 'other\t%s\t%s\t.\t%s\n' "$root_name" "$root_name" "$confidence"
    fi
    return
  fi
  case "$dir" in
    cmd/*) : ;;
    *)
      local outside="${dir//\//-}"
      if $json_mode; then
        printf '{"kind":"other","name":"%s","target":"%s","dir":"%s","confidence":"%s"}\n' \
          "$dir" "$outside" "$dir" "$confidence"
      else
        printf 'other\t%s\t%s\t%s\t%s\n' "$dir" "$outside" "$dir" "$confidence"
      fi
      return ;;
  esac

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
    printf '{"kind":"%s","name":"%s","target":"%s","dir":"%s","confidence":"%s"}\n' \
      "$kind" "$name" "$target_name" "$dir" "$confidence"
  else
    printf '%s\t%s\t%s\t%s\t%s\n' "$kind" "$name" "$target_name" "$dir" "$confidence"
  fi
}

for tier in confirmed candidate; do
  case "$tier" in
    confirmed) list="$confirmed" ;;
    candidate) list="$candidates" ;;
  esac
  [ -z "$list" ] && continue
  while IFS= read -r dir; do
    [ -z "$dir" ] && continue
    classify "$dir" "$tier"
  done <<EOF
$list
EOF
done

exit "$incomplete"
