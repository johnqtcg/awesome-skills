#!/usr/bin/env bash
#
# discover_doc_scope.sh — deterministic scope discovery for the `update-doc` skill.
#
# Answers the four questions the skill must resolve before editing any document:
#   1. which files actually changed (worktree, staged, untracked, and base..HEAD)
#   2. what language dominates the repository
#   3. which command source is authoritative (Makefile > task runner > package
#      scripts > native toolchain > CI)
#   4. what documentation and doc-CI already exist
#
# Deliberately does NOT use `set -e`. Every probe here is expected to come back
# empty on some legitimate repository shape — an absent Makefile is a finding to
# report, not a reason to abort. A `set -e` runner would die on the first empty
# probe and report nothing at all.
#
# Usage: discover_doc_scope.sh [--base <ref>] [--repo <path>]
#
# Exit codes:
#   0  report emitted (always terminated by the `=== END ===` sentinel)
#   3  usage error — no report emitted
#
# A caller must treat the run as successful only when exit status is 0 AND the
# final line is `=== END ===`. A truncated report means the script died midway.

set -uo pipefail

BASE_REF=""
REPO_PATH="."

while [ $# -gt 0 ]; do
  case "$1" in
    --base)
      [ $# -ge 2 ] || { echo "error: --base needs a value" >&2; exit 3; }
      BASE_REF="$2"; shift 2 ;;
    --repo)
      [ $# -ge 2 ] || { echo "error: --repo needs a value" >&2; exit 3; }
      REPO_PATH="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: discover_doc_scope.sh [--base <ref>] [--repo <path>]"; exit 0 ;;
    *)
      echo "error: unknown argument: $1" >&2; exit 3 ;;
  esac
done

cd "$REPO_PATH" 2>/dev/null || { echo "error: cannot enter $REPO_PATH" >&2; exit 3; }

# Count lines without depending on `wc`'s platform-specific leading whitespace.
count_lines() { awk 'END { print NR }'; }

exists() { [ -e "$1" ]; }

# Extensions that count as source. Shared by language detection and by the
# NEW_SOURCE calculation so the two can never disagree about what "a source
# file" means.
SOURCE_EXT_RE='^(go|py|js|jsx|ts|tsx|java|kt|rb|rs|cs|php|swift|scala)$'

only_source_files() {
  # Filter a newline-separated path list down to source files.
  grep -v '^$' | while IFS= read -r path; do
    ext="${path##*.}"
    case "$path" in
      *.*) printf '%s\n' "$ext" | grep -qE "$SOURCE_EXT_RE" && printf '%s\n' "$path" ;;
    esac
  done
}

# ----------------------------------------------------------------------------
# repo
# ----------------------------------------------------------------------------
echo "=== SECTION: repo ==="

IS_GIT=no
if git rev-parse --git-dir >/dev/null 2>&1; then
  IS_GIT=yes
fi

if [ "$IS_GIT" = yes ]; then
  echo "STATUS: OK"
  echo "ROOT: $(git rev-parse --show-toplevel 2>/dev/null)"
  head_sha="$(git rev-parse --short HEAD 2>/dev/null)"
  echo "HEAD: ${head_sha:-NONE}"
else
  # Not a failure. The skill has a documented degraded path: fall back to
  # explicit file evidence when no git range is available.
  echo "STATUS: DEGRADED_NO_GIT"
  echo "ROOT: $(pwd)"
  echo "HEAD: NONE"
fi
echo

# ----------------------------------------------------------------------------
# diff_scope — four independent sources
# ----------------------------------------------------------------------------
echo "=== SECTION: diff_scope ==="

emit_source() {
  # emit_source <label> <payload>
  local label="$1" payload="$2" n=0
  if [ -n "$payload" ]; then
    n="$(printf '%s\n' "$payload" | count_lines)"
  fi
  echo "SOURCE $label: $n"
  if [ -n "$payload" ]; then
    printf '%s\n' "$payload" | sed 's/^/  /'
  fi
}

if [ "$IS_GIT" = yes ]; then
  if [ -z "$BASE_REF" ]; then
    for candidate in origin/HEAD origin/main origin/master main master; do
      if git rev-parse --verify --quiet "$candidate" >/dev/null 2>&1; then
        BASE_REF="$candidate"
        break
      fi
    done
  fi

  if [ -n "$BASE_REF" ] && git rev-parse --verify --quiet "$BASE_REF" >/dev/null 2>&1; then
    echo "BASE_REF: $BASE_REF"
  else
    # Shallow clone, detached CI checkout, or a repo with no upstream. The
    # base..HEAD source is unavailable; the other three still are.
    echo "BASE_REF: NOT_RESOLVED"
    BASE_REF=""
  fi

  worktree="$(git diff --name-only 2>/dev/null)"
  staged="$(git diff --cached --name-only 2>/dev/null)"
  untracked="$(git ls-files --others --exclude-standard 2>/dev/null)"
  base_range=""
  staged_added=""
  base_added=""
  if [ -n "$BASE_REF" ]; then
    base_range="$(git diff --name-only "${BASE_REF}...HEAD" 2>/dev/null)"
    base_added="$(git diff --name-only --diff-filter=A "${BASE_REF}...HEAD" 2>/dev/null)"
  fi
  staged_added="$(git diff --cached --name-only --diff-filter=A 2>/dev/null)"

  emit_source worktree    "$worktree"
  emit_source staged      "$staged"
  emit_source untracked   "$untracked"
  emit_source base_range  "$base_range"

  all="$(printf '%s\n%s\n%s\n%s\n' "$worktree" "$staged" "$untracked" "$base_range" \
        | grep -v '^$' | sort -u)"
  total=0
  [ -n "$all" ] && total="$(printf '%s\n' "$all" | count_lines)"
  echo "TOTAL_UNIQUE: $total"
  if [ -n "$all" ]; then
    printf '%s\n' "$all" | sed 's/^/  /'
  fi

  # `git diff --name-only` reports adds and modifications identically, so the
  # union above cannot answer "did this change introduce a new source file?" —
  # the question the lightweight/full output-mode rule turns on. Recompute it
  # from adds only: untracked files, staged adds, and base-range adds.
  new_source="$(printf '%s\n%s\n%s\n' "$untracked" "$staged_added" "$base_added" \
        | only_source_files | sort -u)"
  new_count=0
  [ -n "$new_source" ] && new_count="$(printf '%s\n' "$new_source" | count_lines)"
  echo "NEW_SOURCE: $new_count"
  if [ -n "$new_source" ]; then
    printf '%s\n' "$new_source" | sed 's/^/  /'
  fi
else
  echo "BASE_REF: NOT_RESOLVED"
  emit_source worktree ""
  emit_source staged ""
  emit_source untracked ""
  emit_source base_range ""
  echo "TOTAL_UNIQUE: 0"
  echo "NEW_SOURCE: 0"
  untracked=""
fi
echo

# ----------------------------------------------------------------------------
# language
# ----------------------------------------------------------------------------
echo "=== SECTION: language ==="

if [ "$IS_GIT" = yes ]; then
  # `git ls-files` alone lists only TRACKED files. A brand-new module that has
  # not been added yet would then be discovered by the diff scope but invisible
  # to language detection — so DOMINANT would keep pointing at the old language
  # and the wrong evidence-command block would be loaded for the very change
  # being documented. Union in the untracked set.
  file_list="$(printf '%s\n%s\n' "$(git ls-files 2>/dev/null)" "$untracked" \
    | grep -v '^$' | sort -u)"
else
  file_list="$(find . -type f -not -path '*/.git/*' 2>/dev/null | sed 's|^\./||')"
fi

ext_counts="$(printf '%s\n' "$file_list" \
  | sed -n 's/.*\.\([A-Za-z0-9_]*\)$/\1/p' \
  | grep -E "$SOURCE_EXT_RE" \
  | sed -e 's/^jsx$/js/' -e 's/^tsx$/ts/' \
  | sort | uniq -c | sort -rn)"

DOMINANT=GENERIC
if [ -n "$ext_counts" ]; then
  top_ext="$(printf '%s\n' "$ext_counts" | head -1 | awk '{print $2}')"
  case "$top_ext" in
    go)      DOMINANT=go ;;
    py)      DOMINANT=python ;;
    js|ts)   DOMINANT=node ;;
    java|kt) DOMINANT=java ;;
    rs)      DOMINANT=rust ;;
    rb)      DOMINANT=ruby ;;
    cs)      DOMINANT=csharp ;;
    *)       DOMINANT=GENERIC ;;
  esac
fi
echo "DOMINANT: $DOMINANT"
echo "COUNTS:"
if [ -n "$ext_counts" ]; then
  printf '%s\n' "$ext_counts" | awk '{print "  " $2 " " $1}'
else
  echo "  (none)"
fi

# A repo is polyglot when a second language holds a meaningful share. Doc
# structure for a polyglot monorepo differs from a single-language service, so
# this is a routing input, not trivia.
POLYGLOT=no
if [ -n "$ext_counts" ]; then
  langs_over_10pct="$(printf '%s\n' "$ext_counts" | awk '
    { c[NR] = $1; e[NR] = $2; total += $1 }
    END { n = 0; for (i = 1; i <= NR; i++) if (total > 0 && c[i] * 10 >= total) n++; print n }')"
  [ "${langs_over_10pct:-0}" -ge 2 ] && POLYGLOT=yes
fi
echo "POLYGLOT: $POLYGLOT"
echo

# ----------------------------------------------------------------------------
# command_sources — priority order, highest first
# ----------------------------------------------------------------------------
echo "=== SECTION: command_sources ==="

PRIMARY=NONE
note_source() {
  # note_source <kind> <path>
  echo "  $1: $2"
  [ "$PRIMARY" = NONE ] && PRIMARY="$1"
}

found_any=no
for f in Makefile makefile GNUmakefile; do
  if exists "$f"; then note_source makefile "$f"; found_any=yes; break; fi
done
for f in Taskfile.yml Taskfile.yaml; do
  if exists "$f"; then note_source taskfile "$f"; found_any=yes; break; fi
done
for f in justfile Justfile .justfile; do
  if exists "$f"; then note_source justfile "$f"; found_any=yes; break; fi
done
if exists package.json; then
  if grep -q '"scripts"' package.json 2>/dev/null; then
    note_source package-scripts package.json; found_any=yes
  fi
fi
for f in go.mod Cargo.toml pyproject.toml pom.xml build.gradle build.gradle.kts Gemfile; do
  if exists "$f"; then note_source native "$f"; found_any=yes; fi
done
ci_files="$(ls .github/workflows/*.yml .github/workflows/*.yaml 2>/dev/null; \
            ls .gitlab-ci.yml Jenkinsfile 2>/dev/null)"
if [ -n "$ci_files" ]; then
  printf '%s\n' "$ci_files" | while IFS= read -r f; do
    [ -n "$f" ] && echo "  ci: $f"
  done
  [ "$PRIMARY" = NONE ] && PRIMARY=ci
  found_any=yes
fi
[ "$found_any" = no ] && echo "  (none)"
echo "PRIMARY: $PRIMARY"

# ---------------------------------------------------------------------------
# Command-level resolution.
#
# PRIMARY answers "which wrapper does this repo mostly use". It cannot answer
# "where is the install command defined", which is what a document actually
# needs: a Makefile holding only a `lint` target still makes PRIMARY=makefile
# while `npm run build` remains the only real build command. Resolve each
# documentation-relevant command kind independently, walking the same priority
# ladder and reporting the first source that genuinely defines it.
# ---------------------------------------------------------------------------

list_make_targets() {
  [ -f "$1" ] || return 0
  grep -E '^[a-zA-Z0-9_][a-zA-Z0-9_.-]*[[:space:]]*:' "$1" 2>/dev/null \
    | sed -E 's/[[:space:]]*:.*//' | sort -u
}

list_pkg_scripts() {
  # Scans forward from the `scripts` key to its closing brace, taking every key
  # on the way. Reading one string per line could not parse a minified manifest,
  # where the whole object sits on one line.
  [ -f "$1" ] || return 0
  awk '
    {
      line = $0
      if (!inb) {
        p = index(line, "\"scripts\"")
        if (p == 0) next
        line = substr(line, p + 9)
        b = index(line, "{")
        if (b == 0) { inb = 1; next }
        line = substr(line, b + 1)
        inb = 1
      }
      e = index(line, "}")
      seg = (e > 0) ? substr(line, 1, e - 1) : line
      # Keys and values alternate; take every other quoted token.
      n = 0
      while (match(seg, /"[^"]*"/)) {
        v = substr(seg, RSTART + 1, RLENGTH - 2)
        n++
        if (n % 2 == 1 && v != "") print v
        seg = substr(seg, RSTART + RLENGTH)
      }
      if (e > 0) { inb = 0; exit }
    }' "$1" 2>/dev/null | sort -u
}

list_taskfile_tasks() {
  [ -f "$1" ] || return 0
  awk '/^tasks:/ { t = 1; next }
       t && /^[a-zA-Z0-9_-]/ { t = 0 }
       t && match($0, /^  [a-zA-Z0-9_-]+:/) {
         s = substr($0, 3, RLENGTH - 3); print s
       }' "$1" 2>/dev/null | sort -u
}

# Per-directory target inventories. Resolution runs against a directory so the
# root and each workspace module go through the identical ladder — a module with
# its own Makefile must not be labelled "makefile" wholesale, which would
# reintroduce the repo-level PRIMARY problem one level down.
collect_targets_for() {
  d="$1"
  DIR_MK="$(for f in Makefile makefile GNUmakefile; do list_make_targets "$d/$f"; done)"
  DIR_TASK="$(for f in Taskfile.yml Taskfile.yaml; do list_taskfile_tasks "$d/$f"; done)"
  DIR_JUST="$(for f in justfile Justfile .justfile; do list_make_targets "$d/$f"; done)"
  DIR_PKG="$(list_pkg_scripts "$d/package.json")"
}

# The lockfile names the package manager. Reporting `npm run build` for a repo
# with a pnpm-lock.yaml is a fabricated command, not a stylistic choice.
node_runner_for() {
  d="$1"
  if [ -f "$d/pnpm-lock.yaml" ]; then echo "pnpm run"
  elif [ -f "$d/yarn.lock" ]; then echo "yarn"
  elif [ -f "$d/bun.lockb" ] || [ -f "$d/bun.lock" ]; then echo "bun run"
  elif [ -f "$d/package-lock.json" ]; then echo "npm run"
  else echo "npm run"   # no lockfile: npm is the default that ships with Node
  fi
}

node_install_for() {
  d="$1"
  if [ -f "$d/pnpm-lock.yaml" ]; then echo "pnpm install"
  elif [ -f "$d/yarn.lock" ]; then echo "yarn install"
  elif [ -f "$d/bun.lockb" ] || [ -f "$d/bun.lock" ]; then echo "bun install"
  elif [ -f "$d/package-lock.json" ]; then echo "npm install"
  fi
  # No lockfile: the manager is genuinely unknown. Emit nothing so the kind
  # falls through to NOT_FOUND rather than guessing npm.
}

has_go_main() {
  # `go run .` needs a main package in the target directory. A library module
  # has none, and the command would fail.
  ls "$1"/*.go >/dev/null 2>&1 || return 1
  grep -lE '^package main([[:space:]]|$)' "$1"/*.go >/dev/null 2>&1
}

has_pytest_evidence() {
  d="$1"
  [ -f "$d/pytest.ini" ] && return 0
  [ -f "$d/conftest.py" ] && return 0
  grep -qiE '(^|[^a-z])pytest' "$d/requirements.txt" 2>/dev/null && return 0
  grep -qE '\[tool\.pytest|(^|[^a-z])pytest' "$d/pyproject.toml" 2>/dev/null && return 0
  return 1
}

# Only commands the toolchain guarantees from the manifest alone are emitted
# unconditionally. Anything that depends on project shape (a main package, a
# chosen test runner, a package manager) needs its own evidence, or the kind is
# reported NOT_FOUND. Filling it from convention is what the skill forbids.
native_command_for() {
  kind="$1"; d="$2"
  case "$kind" in
    build)
      [ -f "$d/go.mod" ]     && { echo "go build ./..."; return; }
      [ -f "$d/Cargo.toml" ] && { echo "cargo build"; return; }
      [ -f "$d/pom.xml" ]    && { echo "mvn package"; return; } ;;
    test)
      [ -f "$d/go.mod" ]     && { echo "go test ./..."; return; }
      [ -f "$d/Cargo.toml" ] && { echo "cargo test"; return; }
      [ -f "$d/pom.xml" ]    && { echo "mvn test"; return; }
      has_pytest_evidence "$d" && { echo "pytest"; return; } ;;
    lint)
      [ -f "$d/go.mod" ]     && { echo "go vet ./..."; return; } ;;
    run)
      { [ -f "$d/go.mod" ] && has_go_main "$d"; }        && { echo "go run ."; return; }
      { [ -f "$d/Cargo.toml" ] && [ -f "$d/src/main.rs" ]; } && { echo "cargo run"; return; } ;;
    install)
      [ -f "$d/go.mod" ]         && { echo "go mod download"; return; }
      [ -f "$d/Cargo.toml" ]     && { echo "cargo fetch"; return; }
      [ -f "$d/requirements.txt" ] && { echo "pip install -r requirements.txt"; return; }
      [ -f "$d/package.json" ]   && { node_install_for "$d"; return; } ;;
  esac
  return 0
}

# CI is the last resort, so an over-eager match here is the most likely source
# of a fabricated command. Two guards:
#   1. Match the command TEXT, not the raw line. Every GitHub Actions step
#      literally contains `run:`, so matching the line made the `run` kind
#      resolve to whatever the first step happened to be.
#   2. Skip environment-setup steps. `apt-get install` is not the project's
#      install command.
# Reduce a CI command to the token that carries its semantics.
#
# A package manager's `run` subcommand is not project-run semantics: the whole
# point of `npm run build` is that it BUILDS. Matching the raw text made every
# scripted CI step match the `run` kind, so `npm run build` was reported as both
# the build command and the start command. Strip the wrapper and match the
# script/target name. `go run` and `cargo run` are left intact — there the verb
# really is the semantics.
# Extract the command lines a CI file runs.
#
# GitHub Actions: `run: cmd` and the block form `run: |` / `run: >` whose body
# is indented under the key — reading only the same line missed every
# multi-line step, which is the common shape for anything beyond one command.
# GitLab CI: `script:` / `before_script:` / `after_script:` list items.
# Jenkins: `sh 'cmd'` / `sh "cmd"`.
ci_step_commands() {
  wf="$1"
  [ -f "$wf" ] || return 0
  awk '
    {
      ind = 0
      while (substr($0, ind + 1, 1) == " ") ind++

      if (inblock) {
        if ($0 ~ /^[[:space:]]*$/) next
        if (ind > key_indent) {
          line = $0; sub(/^[[:space:]]+/, "", line)
          if (line != "") print line
          next
        }
        inblock = 0
      }
      if (inlist) {
        if ($0 ~ /^[[:space:]]*-[[:space:]]*/ && ind > key_indent) {
          line = $0
          sub(/^[[:space:]]*-[[:space:]]*/, "", line)
          gsub(/^["\x27]|["\x27]$/, "", line)
          if (line != "") print line
          next
        }
        if ($0 !~ /^[[:space:]]*$/ && ind <= key_indent) inlist = 0
      }

      if ($0 ~ /^[[:space:]]*-?[[:space:]]*run:[[:space:]]*[|>][-+]?[[:space:]]*$/) {
        key_indent = ind; inblock = 1; next
      }
      if ($0 ~ /^[[:space:]]*-?[[:space:]]*run:[[:space:]]*[^[:space:]]/) {
        line = $0
        sub(/^[[:space:]]*-?[[:space:]]*run:[[:space:]]*/, "", line)
        print line; next
      }
      if ($0 ~ /^[[:space:]]*(before_script|after_script|script):[[:space:]]*$/) {
        key_indent = ind; inlist = 1; next
      }
      if ($0 ~ /^[[:space:]]*sh[[:space:]]+["\x27]/) {
        line = $0
        sub(/^[[:space:]]*sh[[:space:]]+["\x27]/, "", line)
        sub(/["\x27][[:space:]]*$/, "", line)
        if (line != "") print line
      }
    }' "$wf" 2>/dev/null
}

#
# A CI step is routinely a chain: `cd frontend && npm run build`, or
# `CI=true npm run test`. Stripping only at the start of the string left the
# package manager's `run` in the middle, so the whole command matched the `run`
# kind again. Split the chain, drop navigation-only and env-assignment
# segments, and reduce each remaining segment on its own.
ci_match_key() {
  printf '%s\n' "$1" \
    | sed -e 's/&&/;/g' -e 's/||/;/g' \
    | tr ';|' '\n\n' \
    | while IFS= read -r seg; do
        seg="$(printf '%s' "$seg" | sed -E 's/^[[:space:]]+//; s/[[:space:]]+$//')"
        [ -n "$seg" ] || continue
        seg="$(printf '%s' "$seg" \
          | sed -E 's/^([A-Za-z_][A-Za-z0-9_]*=[^[:space:]]*[[:space:]]+)+//')"
        case "$seg" in
          cd\ *|pushd\ *|popd*|export\ *|source\ *|.\ *|"") continue ;;
        esac
        printf '%s\n' "$seg" | sed -E \
          -e 's/^[[:space:]]*(npm|pnpm|bun|yarn)[[:space:]]+run[[:space:]]+//' \
          -e 's/^[[:space:]]*yarn[[:space:]]+//' \
          -e 's/^[[:space:]]*(make|task|just)[[:space:]]+//'
      done
}

ci_command_for() {
  [ -n "$ci_files" ] || return 0
  printf '%s\n' "$ci_files" | while IFS= read -r wf; do
    [ -n "$wf" ] || continue
    ci_step_commands "$wf" \
      | grep -vE '(^|[^a-z])(apt|apt-get|yum|dnf|apk|brew|choco|pacman|sudo)([^a-z]|$)' \
      | while IFS= read -r cmd; do
          [ -n "$cmd" ] || continue
          if printf '%s\n' "$(ci_match_key "$cmd")" \
             | grep -iqE "(^|[^a-zA-Z])($1)([^a-zA-Z]|$)"; then
            printf '%s\n' "$cmd"
          fi
        done
  done | grep -v '^$' | head -1
}

# resolve_command_kind <kind> <synonyms> <dir> <indent> [allow_ci]
resolve_command_kind() {
  kind="$1"; syn="$2"; d="${3:-.}"; indent="${4:-  }"; allow_ci="${5:-yes}"
  collect_targets_for "$d"
  node_run="$(node_runner_for "$d")"
  for pair in "makefile|make|$DIR_MK" \
              "taskfile|task|$DIR_TASK" \
              "justfile|just|$DIR_JUST" \
              "package-scripts|$node_run|$DIR_PKG"; do
    src="${pair%%|*}"; rest="${pair#*|}"; runner="${rest%%|*}"; names="${rest#*|}"
    [ -n "$names" ] || continue
    hit="$(printf '%s\n' "$names" | grep -iE "^($syn)$" | head -1)"
    if [ -n "$hit" ]; then
      echo "${indent}$kind: $src ($runner $hit)"
      return
    fi
  done
  hit="$(native_command_for "$kind" "$d")"
  if [ -n "$hit" ]; then echo "${indent}$kind: native ($hit)"; return; fi
  if [ "$allow_ci" = yes ]; then
    hit="$(ci_command_for "$syn")"
    if [ -n "$hit" ]; then echo "${indent}$kind: ci ($hit)"; return; fi
  fi
  echo "${indent}$kind: NOT_FOUND"
}

resolve_all_kinds() {
  d="$1"; indent="$2"; allow_ci="$3"
  resolve_command_kind build   'build|compile|dist|bundle'          "$d" "$indent" "$allow_ci"
  resolve_command_kind test    'test|tests|check|unit|spec'         "$d" "$indent" "$allow_ci"
  resolve_command_kind lint    'lint|vet|fmt|format|style'          "$d" "$indent" "$allow_ci"
  resolve_command_kind run     'run|start|dev|serve|server'         "$d" "$indent" "$allow_ci"
  resolve_command_kind install 'install|deps|setup|bootstrap|tidy'  "$d" "$indent" "$allow_ci"
}

echo "RESOLVED:"
resolve_all_kinds "." "  " yes

# Per-module resolution. A root wrapper frequently covers only some modules, and
# each module gets the same per-command treatment as the root — reporting a
# module as simply "makefile" would repeat the PRIMARY mistake at module level.
# CI is not consulted per module: a workflow step cannot be attributed to one
# module without more evidence than a name match.
# Workspace members come from the workspace manifests first, then from the
# conventional container directories. A go.work `use ./api` or a Cargo
# `members = ["crates/foo"]` puts modules outside packages/apps/services, and
# those were previously invisible.
# Read one array key out of Cargo.toml's [workspace] table. Handles both the
# inline form (`members = ["a", "b"]`) and the multi-line form.
cargo_array_values() {
  key="$1"
  [ -f Cargo.toml ] || return 0
  awk -v key="$key" '
    /^\[/ { inws = ($0 ~ /^\[workspace\]/); next }
    !inws { next }
    {
      if ($0 ~ "^[[:space:]]*" key "[[:space:]]*=") { collecting = 1 }
      else if (collecting && $0 ~ /^[[:space:]]*[A-Za-z_-]+[[:space:]]*=/) { collecting = 0 }
      if (!collecting) next
      line = $0
      while (match(line, /"[^"]*"/)) {
        v = substr(line, RSTART + 1, RLENGTH - 2)
        if (v != "") print v
        line = substr(line, RSTART + RLENGTH)
      }
      if ($0 ~ /\]/) collecting = 0
    }' Cargo.toml 2>/dev/null
}

# Directories a workspace manifest explicitly excludes. An excluded crate still
# has a Cargo.toml, so nothing downstream would otherwise filter it out.
list_workspace_exclusions() {
  if [ -f Cargo.toml ]; then
    cargo_array_values exclude
  fi
  if [ -f pnpm-workspace.yaml ]; then
    sed -nE 's/^[[:space:]]*-[[:space:]]*"?!([^"[:space:]]+)"?[[:space:]]*$/\1/p' \
      pnpm-workspace.yaml 2>/dev/null
  fi
}

list_workspace_members() {
  if [ -f go.work ]; then
    sed -nE 's|^[[:space:]]*use[[:space:]]+\.?/?([^[:space:]]+).*$|\1|p' go.work 2>/dev/null
    sed -nE 's|^[[:space:]]*\.?/?([a-zA-Z0-9_./-]+)[[:space:]]*$|\1|p' \
      <(sed -n '/^use[[:space:]]*($/,/^)/p' go.work 2>/dev/null | grep -v '^use\|^)') 2>/dev/null
  fi
  if [ -f Cargo.toml ]; then
    # `members` and `exclude` are separate keys. Harvesting every quoted string
    # in the [workspace] table treated an excluded crate as a member.
    cargo_array_values members
  fi
  if [ -f pnpm-workspace.yaml ]; then
    # A `!`-prefixed entry is a negation, not a package path.
    sed -nE 's/^[[:space:]]*-[[:space:]]*"?([^"[:space:]]+)"?[[:space:]]*$/\1/p' \
      pnpm-workspace.yaml 2>/dev/null | grep -v '^!'
  fi
  if [ -f package.json ]; then
    # Scan forward from the `workspaces` key rather than taking one string per
    # line: a single-line manifest (`{"workspaces":["libs/a"]}`) puts the key
    # and every member on the same line, so a per-line first-match reader saw
    # only the key and dropped the members.
    awk '
      {
        line = $0
        if (!inb) {
          p = index(line, "\"workspaces\"")
          if (p == 0) next
          line = substr(line, p + 12)
          b = index(line, "[")
          if (b == 0) { inb = 1; next }
          line = substr(line, b + 1)
          inb = 1
        }
        e = index(line, "]")
        seg = (e > 0) ? substr(line, 1, e - 1) : line
        while (match(seg, /"[^"]*"/)) {
          v = substr(seg, RSTART + 1, RLENGTH - 2)
          if (v != "" && v != "packages") print v
          seg = substr(seg, RSTART + RLENGTH)
        }
        if (e > 0) { inb = 0; exit }
      }' package.json 2>/dev/null
  fi
  for parent in packages apps services modules; do
    [ -d "$parent" ] || continue
    for dir in "$parent"/*/; do
      [ -d "$dir" ] && printf '%s\n' "${dir%/}"
    done
  done
}

# Expand a possible glob to existing directories, without the manifest filter —
# an exclusion list must resolve the same paths the member list does.
expand_globs() {
  while IFS= read -r entry; do
    [ -n "$entry" ] || continue
    entry="${entry#./}"
    for candidate in $entry; do
      [ -d "$candidate" ] && printf '%s\n' "${candidate%/}"
    done
  done
}

drop_excluded() {
  if [ -z "${EXCLUDED:-}" ]; then cat; return; fi
  grep -vxF -f <(printf '%s\n' "$EXCLUDED")
}

# Expand a possible glob ("crates/*") and keep only real directories that carry
# a manifest or a command source — a bare directory is not a module.
expand_members() {
  while IFS= read -r entry; do
    [ -n "$entry" ] || continue
    entry="${entry#./}"
    for candidate in $entry; do
      [ -d "$candidate" ] || continue
      if [ -f "$candidate/go.mod" ] || [ -f "$candidate/Cargo.toml" ] \
         || [ -f "$candidate/package.json" ] || [ -f "$candidate/pyproject.toml" ] \
         || [ -f "$candidate/Makefile" ] || [ -f "$candidate/justfile" ] \
         || [ -f "$candidate/Taskfile.yml" ]; then
        printf '%s\n' "${candidate%/}"
      fi
    done
  done
}

echo "MODULES:"
module_count=0
EXCLUDED="$(list_workspace_exclusions | expand_globs | sort -u)"
MEMBERS="$(list_workspace_members | expand_members | sort -u | drop_excluded)"
if [ -n "$MEMBERS" ]; then
  while IFS= read -r mod; do
    [ -n "$mod" ] || continue
    echo "  $mod:"
    resolve_all_kinds "$mod" "    " no
    module_count=$((module_count + 1))
    if [ "$module_count" -ge 10 ]; then
      echo "  (truncated at 10 modules)"
      break
    fi
  done <<MEMBERS_EOF
$MEMBERS
MEMBERS_EOF
fi
[ "$module_count" -eq 0 ] && echo "  (none)"
echo

# ----------------------------------------------------------------------------
# project_type
# ----------------------------------------------------------------------------
echo "=== SECTION: project_type ==="
echo "SIGNALS:"

sig_service=0; sig_library=0; sig_cli=0; sig_monorepo=0

if exists Dockerfile || exists docker-compose.yml || exists compose.yaml; then
  echo "  container-manifest"; sig_service=$((sig_service + 1))
fi
if [ -d deployments ] || [ -d k8s ] || [ -d charts ] || [ -d helm ]; then
  echo "  deploy-manifests"; sig_service=$((sig_service + 1))
fi
if [ -d cmd ]; then
  echo "  cmd-dir"; sig_cli=$((sig_cli + 1)); sig_service=$((sig_service + 1))
fi
if exists src/main.rs; then
  echo "  rust-bin-entry"; sig_cli=$((sig_cli + 1))
fi
if [ -d packages ] || [ -d apps ] || [ -d services ]; then
  echo "  workspace-dirs"; sig_monorepo=$((sig_monorepo + 2))
fi
if exists pnpm-workspace.yaml || exists lerna.json || exists nx.json || exists turbo.json; then
  echo "  js-workspace-config"; sig_monorepo=$((sig_monorepo + 2))
fi
if exists go.work; then
  echo "  go-workspace"; sig_monorepo=$((sig_monorepo + 2))
fi
if grep -qE '^[[:space:]]*\[workspace\]' Cargo.toml 2>/dev/null; then
  echo "  cargo-workspace"; sig_monorepo=$((sig_monorepo + 2))
fi
# A `bin` entry means readers install and run it; `main`/`exports` without `bin`
# means readers import it. The distinction is what separates CLI docs from
# library docs, so it must not collapse into one "has an entrypoint" signal.
if grep -qE '"bin"[[:space:]]*:' package.json 2>/dev/null; then
  echo "  package-bin-entry"; sig_cli=$((sig_cli + 2))
elif grep -qE '"(main|exports)"[[:space:]]*:' package.json 2>/dev/null; then
  echo "  package-lib-entry"; sig_library=$((sig_library + 1))
fi
if exists setup.py || grep -qE '^[[:space:]]*\[project\]' pyproject.toml 2>/dev/null; then
  echo "  python-package-manifest"; sig_library=$((sig_library + 1))
fi
# A Go module with no command entrypoint and no container manifest is consumed by
# `import`, not by running it.
if exists go.mod && [ ! -d cmd ] && ! exists main.go && ! exists Dockerfile; then
  echo "  go-library-shape"; sig_library=$((sig_library + 2))
fi
if grep -qE '^[[:space:]]*\[lib\]' Cargo.toml 2>/dev/null || exists src/lib.rs; then
  echo "  rust-library-shape"; sig_library=$((sig_library + 2))
fi
# POLYGLOT is reported on its own because it changes how a module index is
# written, but it deliberately does NOT score toward monorepo. A service that
# happens to embed a second language would otherwise be routed as a monorepo on
# that signal alone whenever nothing else scored. The monorepo verdict comes
# from workspace structure.
if [ "$POLYGLOT" = yes ]; then
  echo "  polyglot (reported, not scored)"
fi

LIKELY=UNKNOWN
best=0
for pair in "monorepo:$sig_monorepo" "service:$sig_service" "cli:$sig_cli" "library:$sig_library"; do
  name="${pair%%:*}"; score="${pair##*:}"
  if [ "$score" -gt "$best" ]; then best="$score"; LIKELY="$name"; fi
done
[ "$best" -eq 0 ] && echo "  (none)"
echo "LIKELY: $LIKELY"
echo "SCORES: monorepo=$sig_monorepo service=$sig_service cli=$sig_cli library=$sig_library"
echo

# ----------------------------------------------------------------------------
# docs
# ----------------------------------------------------------------------------
echo "=== SECTION: docs ==="
doc_list="$(ls README.md README.rst CHANGELOG.md CONTRIBUTING.md 2>/dev/null; \
            find docs -maxdepth 2 -name '*.md' 2>/dev/null | sort)"
if [ -n "$doc_list" ]; then
  printf '%s\n' "$doc_list" | sed 's/^/  /'
else
  echo "  (none)"
fi
if [ -d docs/CODEMAPS ]; then echo "CODEMAPS: present"; else echo "CODEMAPS: absent"; fi
echo

# ----------------------------------------------------------------------------
# ci
# ----------------------------------------------------------------------------
echo "=== SECTION: ci ==="
if [ -n "$ci_files" ]; then
  printf '%s\n' "$ci_files" | sed 's/^/  /'
else
  echo "  (none)"
fi
doc_ci=absent
if [ -n "$ci_files" ]; then
  if printf '%s\n' "$ci_files" | while IFS= read -r f; do
       [ -n "$f" ] && grep -lE 'markdownlint|lychee|linkcheck|docs?-drift|mkdocs' "$f" 2>/dev/null
     done | grep -q .; then
    doc_ci=present
  fi
fi
echo "DOC_CI: $doc_ci"
echo

echo "=== END ==="
