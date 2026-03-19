#!/usr/bin/env bash
set -euo pipefail

# Deterministic repo fact scanner for readme-generator skill.
# Output: TSV lines (dimension<TAB>key<TAB>value) for gate decisions.

echo "=== readme-generator: discover_readme_needs ==="
echo ""

# ── 1. Project Type Detection ───────────────────────────────────
echo "--- project_type ---"

has_cmd=false
has_pkg=false
has_internal=false
has_apps=false
has_packages=false
has_go_mod=false
has_go_work=false
has_package_json=false
has_cargo=false
has_pyproject=false

[[ -d cmd ]] && has_cmd=true
[[ -d pkg ]] && has_pkg=true
[[ -d internal ]] && has_internal=true
[[ -d apps ]] && has_apps=true
[[ -d packages ]] && has_packages=true
[[ -f go.mod ]] && has_go_mod=true
[[ -f go.work ]] && has_go_work=true
[[ -f package.json ]] && has_package_json=true
[[ -f Cargo.toml ]] && has_cargo=true
[[ -f pyproject.toml ]] && has_pyproject=true

top_dirs=$(find . -maxdepth 1 -type d ! -name '.' ! -name '.git' ! -name '.github' ! -name '.codex' ! -name '.claude' ! -name 'node_modules' ! -name '.venv' ! -name '__pycache__' 2>/dev/null | wc -l | tr -d ' ')

if [[ "$has_apps" == "true" || "$has_go_work" == "true" ]]; then
  project_type="monorepo"
elif [[ "$has_cmd" == "true" ]]; then
  cmd_count=$(find cmd -maxdepth 1 -type d ! -name cmd 2>/dev/null | wc -l | tr -d ' ')
  if [[ "$cmd_count" -gt 1 ]]; then
    project_type="monorepo"
  else
    main_files=$(find cmd -name 'main.go' 2>/dev/null | head -5)
    if echo "$main_files" | grep -q 'main.go'; then
      if [[ "$has_internal" == "true" ]]; then
        project_type="service"
      else
        project_type="cli"
      fi
    else
      project_type="service"
    fi
  fi
elif [[ "$has_pkg" == "true" && "$has_cmd" == "false" ]]; then
  project_type="library"
elif [[ "$has_package_json" == "true" ]]; then
  if grep -q '"bin"' package.json 2>/dev/null; then
    project_type="cli"
  elif grep -q '"main"\|"exports"' package.json 2>/dev/null; then
    project_type="library"
  else
    project_type="service"
  fi
elif [[ "$has_go_mod" == "true" && "$has_cmd" == "false" && "$has_internal" == "false" ]]; then
  project_type="library"
else
  project_type="unknown"
fi

if [[ "$top_dirs" -lt 5 && "$project_type" != "monorepo" ]]; then
  lightweight_candidate="true"
else
  lightweight_candidate="false"
fi

printf "project_type\tdetected\t%s\n" "$project_type"
printf "project_type\ttop_level_dirs\t%s\n" "$top_dirs"
printf "project_type\tlightweight_candidate\t%s\n" "$lightweight_candidate"

# ── 2. Language Version Detection ───────────────────────────────
echo ""
echo "--- language_version ---"

if [[ "$has_go_mod" == "true" ]]; then
  go_ver=$(grep '^go ' go.mod 2>/dev/null | awk '{print $2}' || echo "unknown")
  printf "language\tgo\t%s\n" "$go_ver"
fi

if [[ "$has_package_json" == "true" ]]; then
  node_ver=$(python3 -c "import json; d=json.load(open('package.json')); print(d.get('engines',{}).get('node','not specified'))" 2>/dev/null || echo "not specified")
  printf "language\tnode\t%s\n" "$node_ver"
fi

if [[ "$has_cargo" == "true" ]]; then
  rust_ver=$(grep '^rust-version' Cargo.toml 2>/dev/null | head -1 | cut -d'"' -f2 || echo "not specified")
  printf "language\trust\t%s\n" "$rust_ver"
fi

if [[ "$has_pyproject" == "true" ]]; then
  py_ver=$(grep 'requires-python' pyproject.toml 2>/dev/null | head -1 | cut -d'"' -f2 || echo "not specified")
  printf "language\tpython\t%s\n" "$py_ver"
fi

# ── 3. Build System Detection ──────────────────────────────────
echo ""
echo "--- build_system ---"

if [[ -f Makefile ]]; then
  make_targets=$(grep -E '^[a-zA-Z_-]+:' Makefile 2>/dev/null | cut -d: -f1 | head -20 | tr '\n' ',' | sed 's/,$//')
  printf "build\tmakefile\ttrue\n"
  printf "build\tmake_targets\t%s\n" "$make_targets"
else
  printf "build\tmakefile\tfalse\n"
fi

if [[ "$has_package_json" == "true" ]]; then
  npm_scripts=$(python3 -c "import json; d=json.load(open('package.json')); print(','.join(d.get('scripts',{}).keys()))" 2>/dev/null || echo "")
  printf "build\tpackage_json_scripts\t%s\n" "$npm_scripts"
fi

[[ -f docker-compose.yml || -f docker-compose.yaml ]] && printf "build\tdocker_compose\ttrue\n" || printf "build\tdocker_compose\tfalse\n"
[[ -f Dockerfile ]] && printf "build\tdockerfile\ttrue\n" || printf "build\tdockerfile\tfalse\n"

# ── 4. CI Platform Detection ──────────────────────────────────
echo ""
echo "--- ci_platform ---"

if [[ -d .github/workflows ]]; then
  wf_files=$(ls .github/workflows/*.yml .github/workflows/*.yaml 2>/dev/null | head -5)
  printf "ci\tgithub_actions\ttrue\n"
  for f in $wf_files; do
    printf "ci\tworkflow_file\t%s\n" "$f"
  done
else
  printf "ci\tgithub_actions\tfalse\n"
fi

[[ -f .gitlab-ci.yml ]] && printf "ci\tgitlab_ci\ttrue\n" || printf "ci\tgitlab_ci\tfalse\n"
[[ -f Jenkinsfile ]] && printf "ci\tjenkins\ttrue\n" || printf "ci\tjenkins\tfalse\n"
[[ -f .circleci/config.yml ]] && printf "ci\tcircleci\ttrue\n" || printf "ci\tcircleci\tfalse\n"

# ── 5. Configuration Detection ─────────────────────────────────
echo ""
echo "--- configuration ---"

[[ -f .env.example ]] && printf "config\tenv_example\ttrue\n" || printf "config\tenv_example\tfalse\n"
[[ -f .env.sample ]] && printf "config\tenv_sample\ttrue\n"
[[ -d config ]] && printf "config\tconfig_dir\ttrue\n" || printf "config\tconfig_dir\tfalse\n"

if [[ -f .env.example ]]; then
  env_vars=$(grep -E '^[A-Z_]+=' .env.example 2>/dev/null | cut -d= -f1 | head -20 | tr '\n' ',' | sed 's/,$//')
  printf "config\tenv_vars\t%s\n" "$env_vars"
fi

# ── 6. Community Files Detection ───────────────────────────────
echo ""
echo "--- community_files ---"

for f in LICENSE LICENSE.md CONTRIBUTING.md CODE_OF_CONDUCT.md SECURITY.md CHANGELOG.md; do
  if [[ -f "$f" ]]; then
    printf "community\t%s\ttrue\n" "$f"
  else
    printf "community\t%s\tfalse\n" "$f"
  fi
done

if [[ -f LICENSE ]]; then
  license_type=$(head -1 LICENSE | grep -oiE 'MIT|Apache|BSD|GPL|ISC|MPL|Unlicense' | head -1 || echo "unknown")
  printf "community\tlicense_type\t%s\n" "${license_type:-unknown}"
fi

# ── 7. Coverage / Quality Tools ────────────────────────────────
echo ""
echo "--- quality_tools ---"

[[ -f .codecov.yml || -f codecov.yml ]] && printf "quality\tcodeov\ttrue\n" || printf "quality\tcodecov\tfalse\n"
[[ -f .coveralls.yml ]] && printf "quality\tcoveralls\ttrue\n" || printf "quality\tcoveralls\tfalse\n"
[[ -f .golangci.yml || -f .golangci.yaml ]] && printf "quality\tgolangci_lint\ttrue\n" || printf "quality\tgolangci_lint\tfalse\n"
[[ -f .eslintrc.js || -f .eslintrc.json || -f .eslintrc.yml ]] && printf "quality\teslint\ttrue\n"
[[ -f .prettierrc || -f .prettierrc.json ]] && printf "quality\tprettier\ttrue\n"

# ── 8. Existing README Analysis ────────────────────────────────
echo ""
echo "--- existing_readme ---"

if [[ -f README.md ]]; then
  readme_lines=$(wc -l < README.md | tr -d ' ')
  readme_sections=$(grep -cE '^#{1,3} ' README.md 2>/dev/null || echo 0)
  has_toc=$(grep -ciE '\[.*\]\(#' README.md 2>/dev/null || echo 0)
  has_badges=$(grep -cE '!\[.*\]\(https://' README.md 2>/dev/null || echo 0)
  printf "readme\texists\ttrue\n"
  printf "readme\tlines\t%s\n" "$readme_lines"
  printf "readme\tsections\t%s\n" "$readme_sections"
  printf "readme\thas_toc\t%s\n" "$([[ "$has_toc" -gt 2 ]] && echo true || echo false)"
  printf "readme\thas_badges\t%s\n" "$([[ "$has_badges" -gt 0 ]] && echo true || echo false)"
else
  printf "readme\texists\tfalse\n"
fi

# ── 9. Repo Visibility ────────────────────────────────────────
echo ""
echo "--- visibility ---"

remote_url=$(git remote get-url origin 2>/dev/null || echo "")
if [[ -n "$remote_url" ]]; then
  printf "repo\tremote_url\t%s\n" "$remote_url"
  if echo "$remote_url" | grep -q 'github.com'; then
    repo_path=$(echo "$remote_url" | sed -E 's|.*github\.com[:/](.+)(\.git)?$|\1|' | sed 's/\.git$//')
    is_private=$(gh api "repos/$repo_path" --jq '.private' 2>/dev/null || echo "unknown")
    printf "repo\tprivate\t%s\n" "$is_private"
  fi
else
  printf "repo\tremote_url\tnone\n"
fi

# ── 10. Summary Verdict ───────────────────────────────────────
echo ""
echo "--- verdict ---"

blockers=""
if [[ "$project_type" == "unknown" ]]; then
  blockers="${blockers}BLOCKER: cannot determine project type; "
fi
if [[ ! -f Makefile && "$has_package_json" == "false" && "$has_go_mod" == "false" && "$has_cargo" == "false" && "$has_pyproject" == "false" ]]; then
  blockers="${blockers}BLOCKER: no build system detected; "
fi

if [[ -n "$blockers" ]]; then
  printf "verdict\tstatus\tDEGRADED\n"
  printf "verdict\tblockers\t%s\n" "$blockers"
else
  printf "verdict\tstatus\tREADY\n"
  printf "verdict\tproject_type\t%s\n" "$project_type"
  printf "verdict\tlightweight\t%s\n" "$lightweight_candidate"
fi

echo ""
echo "=== discovery complete ==="
