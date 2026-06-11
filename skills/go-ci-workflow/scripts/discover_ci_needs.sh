#!/usr/bin/env bash
# Discover CI requirements for a Go project.
# Prints tab-separated: category<tab>item<tab>source
# Categories: makefile-target, repo-task, tool, test-type, container, config, shape, workflow
#
# This is a PROBE script: most probes are EXPECTED to find nothing on any
# given repository (no scripts/ dir, no Makefile, no ci targets, ...).
# `set -e` / `pipefail` would turn every empty probe into a fatal mid-run
# abort with truncated output — which is worse than a crash, because the
# caller may treat the partial TSV as a complete discovery. So: `set -u`
# only, explicit error handling for the genuinely fatal case (bad root),
# and an explicit `exit 0` at the end.
set -u

root="${1:-.}"
cd "$root" || { printf 'error\tcannot-cd\t%s\n' "$root" >&2; exit 2; }

has_nested_go_mod=0

# 1. Root and nested make targets (a Makefile without ci targets is normal)
while IFS= read -r makefile; do
  rel="${makefile#./}"
  grep -E '^(ci|ci-[a-zA-Z0-9_-]+|docker-build):' "$makefile" 2>/dev/null | while IFS=: read -r target _; do
    printf "makefile-target\t%s\t%s\n" "$target" "$rel"
  done
done < <(find . -name Makefile -type f 2>/dev/null | sort)

# 2. Alternative repo task entrypoints
for taskfile in Taskfile.yml Taskfile.yaml; do
  [ -f "$taskfile" ] && printf "repo-task\ttaskfile\t%s\n" "$taskfile"
done
[ -f magefile.go ] && printf "repo-task\tmage\tmagefile.go\n"
if [ -d scripts ]; then
  find scripts -maxdepth 2 -type f \( -name '*.sh' -o -name '*.bash' \) 2>/dev/null | sort | while read -r script; do
    printf "repo-task\tscript\t%s\n" "$script"
  done
fi

# 3. Dockerfile presence
find . -maxdepth 2 -type f \( -name 'Dockerfile' -o -name 'Dockerfile.*' \) 2>/dev/null | sort | while read -r df; do
  rel="${df#./}"
  printf "container\t%s\t%s\n" "$rel" "$rel"
done

# 4. Test categories
find . -type d \( -path '*/tests/integration' -o -path '*/test/integration' \) 2>/dev/null | sort | while read -r dir; do
  printf "test-type\tintegration\t%s\n" "${dir#./}"
done
find . -type d \( -path '*/tests/e2e' -o -path '*/test/e2e' \) 2>/dev/null | sort | while read -r dir; do
  printf "test-type\te2e\t%s\n" "${dir#./}"
done

# 5. Tool config files
for cfg in .golangci.yaml .golangci.yml; do
  [ -f "$cfg" ] && printf "config\tgolangci-lint\t%s\n" "$cfg" && break
done
for cfg in .goreleaser.yaml .goreleaser.yml; do
  [ -f "$cfg" ] && printf "config\tgoreleaser\t%s\n" "$cfg" && break
done

# 6. Go module detection
while IFS= read -r gomod; do
  rel="${gomod#./}"
  go_ver=$(awk '/^go / {print $2}' "$gomod" 2>/dev/null)
  printf "config\tgo-version\t%s (%s)\n" "$rel" "${go_ver:-unknown}"
  [ "$rel" != "go.mod" ] && has_nested_go_mod=1
done < <(find . -name go.mod -type f 2>/dev/null | sort)

if [ -f go.mod ]; then
  printf "shape\tsingle-root-module\tgo.mod\n"
fi
if [ "$has_nested_go_mod" -eq 1 ]; then
  printf "shape\tmulti-module\tfind go.mod\n"
fi

# 7. Existing workflows
if [ -d .github/workflows ]; then
  find .github/workflows -maxdepth 1 -type f \( -name '*.yml' -o -name '*.yaml' \) 2>/dev/null | sort | while read -r wf; do
    printf "workflow\t%s\t%s\n" "${wf##*/}" "${wf#./}"
  done
fi

# 8. Detect tools referenced in Makefiles and scripts
tool_sources=$(find . \( -name Makefile -o -path './scripts/*.sh' -o -path './scripts/*.bash' \) -type f 2>/dev/null)
if [ -n "$tool_sources" ]; then
  printf '%s\n' "$tool_sources" \
    | xargs grep -h -oE '(golangci-lint|swag|goimports-reviser|govulncheck|fieldalignment|protoc|mockgen|wire|gosec|nilaway)' 2>/dev/null \
    | sort -u | while read -r tool; do
      printf "tool\t%s\trepo-scan\n" "$tool"
    done
fi

exit 0
