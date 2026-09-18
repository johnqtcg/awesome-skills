#!/usr/bin/env bash
# Discover CI requirements for a Go project.
# Prints tab-separated: category<tab>item<tab>source
# Categories: makefile-target, repo-task, tool, test-type, container, config,
#             shape, workflow, meta
#
# This is a PROBE script: most probes are EXPECTED to find nothing on any
# given repository (no scripts/ dir, no Makefile, no ci targets, ...).
# `set -e` / `pipefail` would turn every empty probe into a fatal mid-run
# abort with truncated output — which is worse than a crash, because the
# caller may treat the partial TSV as a complete discovery. So: `set -u`
# only, explicit error handling for the genuinely fatal case (bad root),
# and a terminal `meta<TAB>probe-complete` row so a truncated run is visible.
#
# COMPLETION CONTRACT: a run that finishes emits `meta<TAB>probe-complete<TAB>ok`
# as its LAST line. Output without that line is a partial run — do not read it
# as "nothing found". A run that could not scan everything additionally emits
# `meta<TAB>partial-scan<TAB>...`, and suppresses any shape verdict that the
# unreadable paths could have changed.
#
# LIMITS (the skill body must confirm these by manual inspection, never treat
# this output as an authoritative repo classification):
#   - app-vs-library is a heuristic (presence of `package main`), not a verdict.
#     `*_test.go` and `magefile.go` are excluded, but an example/codegen helper
#     declaring `package main` is still a valid witness and may be cited instead
#     of the real entrypoint;
#   - it does NOT parse Taskfile/mage task bodies, only detects their presence;
#   - CGO, codegen, cross-platform, and private-module needs are not inferred;
#   - filenames: spaces, apostrophes and quotes are handled (NUL-delimited
#     throughout). A literal TAB or NEWLINE in a path still corrupts or drops
#     that row, because the output format is TSV;
#   - Dockerfiles are searched to DOCKERFILE_MAX_DEPTH (4) below the root, which
#     covers `./Dockerfile`, `build/`, `cmd/<app>/`, and `deployments/docker/<app>/`
#     but NOT deeper burials — a repo that hides them lower will under-report;
#   - make targets are read from Makefile, makefile and GNUmakefile; `*.mk`
#     includes are NOT followed, so a target defined in an include is missed;
#   - only the PRUNE list below is excluded. A first-party tree with an unusual
#     name (e.g. `examples/`, `hack/`, generated site output) is still scanned
#     and can contribute targets the repo does not actually own.
set -u

# Directories that never indicate first-party repository structure. Vendored,
# generated, and dependency trees carry their own Makefiles, go.mod files,
# Dockerfiles, and test directories; counting any of them as first-party would
# make the skill promise CI parity with a target the repo does not own.
#
# ONE source of truth. Both the `find` predicate list and the regex form are
# DERIVED from PRUNE_DIRS below: an earlier version hand-wrote the regex in the
# package-main probe, it drifted (the copy omitted `.git`), and a stray
# `.git/x/leftover.go` was reported as the application entrypoint — while a
# comment right here claimed the list was applied to every probe.
PRUNE_DIRS=(vendor node_modules testdata third_party .git)
PRUNE=()
for _d in "${PRUNE_DIRS[@]}"; do PRUNE+=( -not -path "*/${_d}/*" ); done
_alt=""
for _d in "${PRUNE_DIRS[@]}"; do
  _alt="${_alt:+${_alt}|}$(printf '%s' "$_d" | sed 's/\./\\./g')"
done
PRUNE_RE="/(${_alt})/"
unset _d _alt

DOCKERFILE_MAX_DEPTH=4
MAKEFILE_NAMES=( -name Makefile -o -name makefile -o -name GNUmakefile )

# Every probe appends its stderr here instead of discarding it. Discarding made
# "permission denied" indistinguishable from "absent", so an unreadable `cmd/`
# silently flipped the shape verdict from application to library — a confidently
# WRONG answer, not an under-report.
ERRLOG="${TMPDIR:-/tmp}/gociw_probe_err.$$"
: > "$ERRLOG" 2>/dev/null || ERRLOG=/dev/null
trap 'rm -f "$ERRLOG"' EXIT

root="${1-.}"
if [ -z "$root" ]; then
  # `${1:-.}` treated an empty argument as unset, so `discover.sh "$REPO_ROOT"`
  # with an unset variable produced a full, plausible report of the CWD.
  printf 'error\tempty-root\t(empty argument)\n' >&2
  exit 2
fi
# Validate BEFORE cd. `--` is not sufficient for a literal `-`: bash's cd
# recognises `-` as $OLDPWD after option parsing, so `discover.sh -` silently
# scanned a different directory and exited 0. A `-d` test rejects that, a file
# passed as the root, and a nonexistent path — uniformly, before any probe runs.
if [ ! -d "$root" ]; then
  printf 'error\tnot-a-directory\t%s\n' "$root" >&2
  exit 2
fi
# `CDPATH` set in the user's profile makes `cd` echo the resolved path to
# STDOUT, injecting a non-TSV row into the report.
CDPATH= cd -- "$root" >/dev/null || {
  printf 'error\tcannot-cd\t%s\n' "$root" >&2
  exit 2
}

has_nested_go_mod=0

# 1. Root and nested make targets (a Makefile without ci targets is normal)
while IFS= read -r -d '' makefile; do
  rel="${makefile#./}"
  grep -E '^(ci|ci-[a-zA-Z0-9_-]+|docker-build):' "$makefile" 2>>"$ERRLOG" | while IFS=: read -r target _; do
    printf "makefile-target\t%s\t%s\n" "$target" "$rel"
  done
done < <(find . \( "${MAKEFILE_NAMES[@]}" \) -type f "${PRUNE[@]}" -print0 2>>"$ERRLOG" | sort -z)

# 2. Alternative repo task entrypoints
for taskfile in Taskfile.yml Taskfile.yaml; do
  [ -f "$taskfile" ] && printf "repo-task\ttaskfile\t%s\n" "$taskfile"
done
[ -f magefile.go ] && printf "repo-task\tmage\tmagefile.go\n"
if [ -d scripts ]; then
  find scripts -maxdepth 2 -type f \( -name '*.sh' -o -name '*.bash' \) "${PRUNE[@]}" -print0 2>>"$ERRLOG" \
    | sort -z | while IFS= read -r -d '' script; do
      printf "repo-task\tscript\t%s\n" "$script"
    done
fi

# 3. Dockerfile presence. Depth-limited (see DOCKERFILE_MAX_DEPTH in LIMITS):
# monorepos keep them at `services/<app>/Dockerfile` or `cmd/<app>/Dockerfile`,
# which an earlier -maxdepth 2 missed entirely — reporting zero containers for
# exactly the repository shape this skill emphasises.
find . -maxdepth "$DOCKERFILE_MAX_DEPTH" -type f \( -name 'Dockerfile' -o -name 'Dockerfile.*' \) \
  "${PRUNE[@]}" -print0 2>>"$ERRLOG" | sort -z | while IFS= read -r -d '' df; do
  rel="${df#./}"
  printf "container\t%s\t%s\n" "$rel" "$rel"
done

# 4. Test categories
find . -type d \( -path '*/tests/integration' -o -path '*/test/integration' \) \
  "${PRUNE[@]}" -print0 2>>"$ERRLOG" | sort -z | while IFS= read -r -d '' dir; do
  printf "test-type\tintegration\t%s\n" "${dir#./}"
done
find . -type d \( -path '*/tests/e2e' -o -path '*/test/e2e' \) \
  "${PRUNE[@]}" -print0 2>>"$ERRLOG" | sort -z | while IFS= read -r -d '' dir; do
  printf "test-type\te2e\t%s\n" "${dir#./}"
done

# 5. Tool config files
for cfg in .golangci.yaml .golangci.yml; do
  [ -f "$cfg" ] && printf "config\tgolangci-lint\t%s\n" "$cfg" && break
done
for cfg in .goreleaser.yaml .goreleaser.yml; do
  [ -f "$cfg" ] && printf "config\tgoreleaser\t%s\n" "$cfg" && break
done

# 6. Go module detection (vendored / generated trees pruned — see PRUNE)
while IFS= read -r -d '' gomod; do
  rel="${gomod#./}"
  go_ver=$(awk '/^go / {print $2}' "$gomod" 2>>"$ERRLOG")
  printf "config\tgo-version\t%s (%s)\n" "$rel" "${go_ver:-unknown}"
  # toolchain directive (Go 1.21+) pins the exact toolchain independently of
  # the language `go` line; setup-go honours it, so CI must not fight it.
  toolchain=$(awk '/^toolchain / {print $2}' "$gomod" 2>>"$ERRLOG")
  [ -n "$toolchain" ] && printf "config\ttoolchain\t%s (%s)\n" "$rel" "$toolchain"
  [ "$rel" != "go.mod" ] && has_nested_go_mod=1
done < <(find . -type f -name go.mod "${PRUNE[@]}" -print0 2>>"$ERRLOG" | sort -z)

if [ -f go.mod ]; then
  printf "shape\tsingle-root-module\tgo.mod\n"
fi
if [ "$has_nested_go_mod" -eq 1 ]; then
  printf "shape\tmulti-module\tfind go.mod\n"
fi
# go.work turns nested modules into one workspace; cache keys and build
# commands differ from independent multi-module repos.
if [ -f go.work ]; then
  printf "shape\tgo-workspace\tgo.work\n"
fi

# 6b. Application-vs-library signal (HEURISTIC — confirm manually).
# A `package main` outside vendored/generated trees suggests a buildable binary
# (application); its absence suggests a library. This does not classify the
# repo — it only tells the skill which questions to ask.
main_pkg=$(grep -rlE '^package main$' --include='*.go' . 2>>"$ERRLOG" \
  | grep -vE "$PRUNE_RE" \
  | grep -vE '(_test\.go|/magefile\.go)$' \
  | head -1)

# ANY unreadable path in the tree, from ANY probe, could be hiding a
# `package main`. An earlier version only tripped when the package-main scan
# was the FIRST probe to error, so a directory that also blocked the Makefile
# and Dockerfile probes still produced a confident library verdict.
if [ -n "$main_pkg" ]; then
  printf "shape\tlikely-application\t%s\n" "${main_pkg#./}"
elif [ -s "$ERRLOG" ]; then
  # Declare the undecidable case instead of guessing. Emitting
  # `likely-library-or-unknown` here would be a confidently wrong answer built
  # on a scan that could not read part of the tree.
  printf "shape\tundetermined\tpackage-main scan incomplete (unreadable paths)\n"
elif [ -f go.mod ]; then
  printf "shape\tlikely-library-or-unknown\tno package main found\n"
fi

# 7. Existing workflows
if [ -d .github/workflows ]; then
  find .github/workflows -maxdepth 1 -type f \( -name '*.yml' -o -name '*.yaml' \) -print0 2>>"$ERRLOG" \
    | sort -z | while IFS= read -r -d '' wf; do
      printf "workflow\t%s\t%s\n" "${wf##*/}" "${wf#./}"
    done
fi

# 8. Detect tools referenced in Makefiles and scripts.
# `-exec grep {} +` rather than `find | xargs`: BSD xargs treats an apostrophe
# as a quote character, so a single `John's dir/` ANYWHERE in the tree aborted
# the whole invocation with "unterminated quote" — zeroing the tool probe for
# the entire repository, with exit 0 and (because stderr was discarded) no
# diagnostic. `-exec ... +` also runs nothing when no file matches.
# Depth matches probe 2, so a tool is never attributed to a script the report
# does not also list.
find . \( "${MAKEFILE_NAMES[@]}" -o -path './scripts/*.sh' -o -path './scripts/*.bash' \) \
  -maxdepth 3 -type f "${PRUNE[@]}" \
  -exec grep -h -oE '(golangci-lint|swag|goimports-reviser|govulncheck|fieldalignment|protoc|mockgen|wire|gosec|nilaway)' {} + 2>>"$ERRLOG" \
  | sort -u | while read -r tool; do
    [ -n "$tool" ] && printf "tool\t%s\trepo-scan\n" "$tool"
  done

# Report a degraded scan explicitly. Silence here is what turned a
# permission-denied into a wrong verdict.
if [ -s "$ERRLOG" ]; then
  err_count=$(grep -c . "$ERRLOG" 2>/dev/null || printf '0')
  printf "meta\tpartial-scan\t%s path(s) could not be read; output is incomplete\n" "${err_count:-0}"
fi

# Terminal marker. Absence of this line means the run did not finish; a caller
# must not read a truncated TSV as "nothing found".
printf "meta\tprobe-complete\tok\n"
exit 0
