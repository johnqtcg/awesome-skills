#!/usr/bin/env bash
set -euo pipefail

# Discover CI requirements for a Go project.
# Prints tab-separated: category<tab>item<tab>source
# Categories: makefile-target, repo-task, tool, test-type, container, config, shape, workflow

root="${1:-.}"
cd "$root"

has_nested_go_mod=0

# 1. Root and nested make targets
while IFS= read -r makefile; do
  rel="${makefile#./}"
  grep -E '^(ci|ci-[a-zA-Z0-9_-]+|docker-build):' "$makefile" 2>/dev/null | while IFS=: read -r target _; do
    printf "makefile-target\t%s\t%s\n" "$target" "$rel"
  done
done < <(find . -name Makefile -type f | sort)

# 2. Alternative repo task entrypoints
for taskfile in Taskfile.yml Taskfile.yaml; do
  [ -f "$taskfile" ] && printf "repo-task\ttaskfile\t%s\n" "$taskfile"
done
[ -f magefile.go ] && printf "repo-task\tmage\tmagefile.go\n"
find scripts -maxdepth 2 -type f \( -name '*.sh' -o -name '*.bash' \) 2>/dev/null | sort | while read -r script; do
  printf "repo-task\tscript\t%s\n" "$script"
done

# 3. Dockerfile presence
find . -maxdepth 2 -type f \( -name 'Dockerfile' -o -name 'Dockerfile.*' \) | sort | while read -r df; do
  rel="${df#./}"
  printf "container\t%s\t%s\n" "$rel" "$rel"
done

# 4. Test categories
find . -type d \( -path '*/tests/integration' -o -path '*/test/integration' \) | sort | while read -r dir; do
  printf "test-type\tintegration\t%s\n" "${dir#./}"
done
find . -type d \( -path '*/tests/e2e' -o -path '*/test/e2e' \) | sort | while read -r dir; do
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
  go_ver=$(awk '/^go / {print $2}' "$gomod")
  printf "config\tgo-version\t%s (%s)\n" "$rel" "${go_ver:-unknown}"
  [ "$rel" != "go.mod" ] && has_nested_go_mod=1
done < <(find . -name go.mod -type f | sort)

if [ -f go.mod ]; then
  printf "shape\tsingle-root-module\tgo.mod\n"
fi
if [ "$has_nested_go_mod" -eq 1 ]; then
  printf "shape\tmulti-module\tfind go.mod\n"
fi

# 7. Existing workflows
find .github/workflows -maxdepth 1 -type f \( -name '*.yml' -o -name '*.yaml' \) 2>/dev/null | sort | while read -r wf; do
  printf "workflow\t%s\t%s\n" "${wf##*/}" "${wf#./}"
done

# 8. Detect tools referenced in Makefiles and scripts
find . \( -name Makefile -o -path './scripts/*.sh' -o -path './scripts/*.bash' \) -type f 2>/dev/null \
  | xargs grep -h -oE '(golangci-lint|swag|goimports-reviser|govulncheck|fieldalignment|protoc|mockgen|wire|gosec|nilaway)' 2>/dev/null \
  | sort -u | while read -r tool; do
    printf "tool\t%s\trepo-scan\n" "$tool"
  done
