#!/usr/bin/env bash
# Deterministic repo fact scanner for readme-generator skill.
# Output: TSV lines (dimension<TAB>key<TAB>value) for gate decisions.
#
# Robustness contract: this is a PROBE script — most probes finding nothing is
# a normal outcome, not an error. Therefore:
#   - `set -u` only. No `-e` / `pipefail`: grep/ls/find pipelines legitimately
#     exit non-zero on empty matches, and errexit would kill the script mid-TSV
#     (silent truncation — the caller then mistakes partial output for complete
#     discovery). Regression-guarded by scripts/tests/test_discovery_script.py.
#   - Always ends with an explicit `exit 0`; the verdict section is the
#     completeness marker consumers should look for.
#
# Project-type detection below must stay in sync with SKILL.md §Project Type
# Routing (guarded by test_discovery_script.py::TestRoutingSync).
set -u

echo "=== readme-generator: discover_readme_needs ==="
echo ""

PRUNE=( -name node_modules -o -name vendor -o -name .git -o -name testdata -o -name target -o -name dist -o -name .venv )

# count_subdirs <dir> — immediate subdirectories, 0 when the dir is absent.
count_subdirs() {
  local d="$1" n
  [[ -d "$d" ]] || { echo 0; return; }
  n=$(find "$d" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l | tr -d ' ')
  echo "${n:-0}"
}

# pkg_json <key> — read one fact out of package.json via a real JSON parse.
# grep on raw text was the old approach and matched `"bin"` inside unrelated
# blocks (e.g. `"directories": {"bin": …}`) or inside a dependency name.
pkg_json() {
  python3 - "$1" <<'PY' 2>/dev/null || echo ""
import json, sys
key = sys.argv[1]
try:
    d = json.load(open("package.json"))
except Exception:
    sys.exit(1)
if not isinstance(d, dict):
    sys.exit(1)
if key == "workspaces":
    print("true" if d.get("workspaces") else "false")
elif key == "bin":
    b = d.get("bin")
    if isinstance(b, str):
        print(d.get("name", "bin"))
    elif isinstance(b, dict):
        print(",".join(b.keys()))
elif key == "module_entry":
    for k in ("exports", "main", "module", "types"):
        if d.get(k):
            print(k)
            break
elif key == "start_script":
    print("true" if isinstance(d.get("scripts"), dict) and d["scripts"].get("start") else "false")
elif key == "scripts":
    s = d.get("scripts")
    print(",".join(s.keys()) if isinstance(s, dict) else "")
elif key == "engines_node":
    e = d.get("engines")
    print(e.get("node", "not specified") if isinstance(e, dict) else "not specified")
PY
}

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
has_setup_py=false

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
[[ -f setup.py ]] && has_setup_py=true

apps_count=$(count_subdirs apps)
packages_count=$(count_subdirs packages)
cmd_count=$(count_subdirs cmd)

# Go main packages anywhere shallow, not just under cmd/. A root-level main.go
# is the single most common small-Go-binary layout and used to route to
# "library" because only cmd/ was probed.
go_mains=$(find . -maxdepth 3 -type d \( "${PRUNE[@]}" \) -prune -o -type f -name 'main.go' -print 2>/dev/null | sed 's|^\./||' | sort)
go_main_count=$(printf '%s' "$go_mains" | grep -c . 2>/dev/null)
go_main_count=${go_main_count:-0}

rust_workspace=false
rust_bin=false
rust_lib=false
if [[ "$has_cargo" == "true" ]]; then
  grep -q '^\[workspace\]' Cargo.toml 2>/dev/null && rust_workspace=true
  { [[ -f src/main.rs ]] || grep -q '^\[\[bin\]\]' Cargo.toml 2>/dev/null; } && rust_bin=true
  { [[ -f src/lib.rs ]] || grep -q '^\[lib\]' Cargo.toml 2>/dev/null; } && rust_lib=true
fi

py_scripts=false
py_service=false
if [[ "$has_pyproject" == "true" ]]; then
  grep -qE '^\[(project\.scripts|tool\.poetry\.scripts)\]' pyproject.toml 2>/dev/null && py_scripts=true
fi
if [[ -f manage.py ]] || find . -maxdepth 3 -type d \( "${PRUNE[@]}" \) -prune -o -type f \( -name 'wsgi.py' -o -name 'asgi.py' \) -print 2>/dev/null | grep -q .; then
  py_service=true
fi

node_workspaces=$(pkg_json workspaces)
node_bin=$(pkg_json bin)
node_module_entry=$(pkg_json module_entry)
node_start=$(pkg_json start_script)

# Monorepo signals are checked first: they are structural and outrank the
# single-module language heuristics below.
if [[ "$has_go_work" == "true" \
   || "$apps_count" -gt 0 \
   || "$packages_count" -gt 1 \
   || "$node_workspaces" == "true" \
   || -f pnpm-workspace.yaml || -f lerna.json || -f nx.json \
   || "$rust_workspace" == "true" \
   || "$cmd_count" -gt 1 ]]; then
  project_type="monorepo"
elif [[ "$has_go_mod" == "true" || "$go_main_count" -gt 0 ]]; then
  if [[ "$go_main_count" -gt 0 ]]; then
    # internal/ is the service marker; a bare binary is a CLI.
    if [[ "$has_internal" == "true" ]]; then
      project_type="service"
    else
      project_type="cli"
    fi
  elif [[ "$has_pkg" == "true" ]]; then
    project_type="library"
  elif find . -maxdepth 3 -type d \( "${PRUNE[@]}" \) -prune -o -type f -name '*.go' -print 2>/dev/null | grep -q .; then
    project_type="library"
  else
    # go.mod with no Go source: nothing to describe yet.
    project_type="unknown"
  fi
elif [[ "$has_package_json" == "true" ]]; then
  if [[ -n "$node_bin" ]]; then
    project_type="cli"
  elif [[ -n "$node_module_entry" ]]; then
    project_type="library"
  elif [[ "$node_start" == "true" ]]; then
    project_type="service"
  else
    project_type="unknown"
  fi
elif [[ "$has_cargo" == "true" ]]; then
  if [[ "$rust_bin" == "true" ]]; then
    project_type="cli"
  elif [[ "$rust_lib" == "true" ]]; then
    project_type="library"
  else
    project_type="unknown"
  fi
elif [[ "$has_pyproject" == "true" || "$has_setup_py" == "true" ]]; then
  if [[ "$py_service" == "true" ]]; then
    project_type="service"
  elif [[ "$py_scripts" == "true" ]]; then
    project_type="cli"
  else
    project_type="library"
  fi
else
  project_type="unknown"
fi

top_dirs=$(find . -maxdepth 1 -type d ! -name '.' ! -name '.git' ! -name '.github' ! -name '.codex' ! -name '.claude' ! -name 'node_modules' ! -name '.venv' ! -name '__pycache__' 2>/dev/null | wc -l | tr -d ' ')
top_dirs=${top_dirs:-0}

if [[ "$top_dirs" -lt 5 && "$project_type" != "monorepo" ]]; then
  lightweight_candidate="true"
else
  lightweight_candidate="false"
fi

# Lightweight must resolve to ONE answer, not a flag the caller may or may not honour.
# Previously the script emitted project_type=cli alongside lightweight_candidate=true;
# the skill could then pick Template E while the linter checked Template C's required
# sections. `effective` is that single answer — generation, the output contract, and
# lint_readme.py all read it.
#
# But the script does NOT promote on its own. Of SKILL.md's four lightweight triggers,
# three are mechanical and one — "audience is internal contributors only" — is a human
# judgement no probe can make. Inferring it was actively harmful: a minimal public Go
# SDK (go.mod + pkg/, no CI, few directories) was silently downgraded to lightweight and
# lost its Installation and API sections. Absence of CI is not evidence of absence of
# users.
#
# So: this section reports ELIGIBILITY and the reasons. The Audience Gate decides, and
# records the decision with `lint_readme.py --type=lightweight`, which is what makes it
# the single answer everything downstream reads.
has_ci=false
if [[ -d .github/workflows ]] && find .github/workflows -maxdepth 1 -type f \( -name '*.yml' -o -name '*.yaml' \) 2>/dev/null | grep -q .; then
  has_ci=true
fi
[[ -f .gitlab-ci.yml || -f Jenkinsfile || -f .circleci/config.yml ]] && has_ci=true

has_deploy=false
[[ -f Dockerfile || -f docker-compose.yml || -f docker-compose.yaml ]] && has_deploy=true
[[ -d deploy || -d deployments || -d k8s || -d charts || -d terraform ]] && has_deploy=true

# A library exists to be imported by someone else — that IS a public surface, whatever
# the manifest says. npm `bin`/`main`/`exports` and Python console scripts are the
# explicit declarations; `project_type=library` is the structural one.
has_public_surface=false
[[ -n "$node_bin" || -n "$node_module_entry" ]] && has_public_surface=true
[[ "$py_scripts" == "true" ]] && has_public_surface=true
[[ "$project_type" == "library" ]] && has_public_surface=true

lightweight_blockers=""
[[ "$project_type" == "unknown" ]] && lightweight_blockers="${lightweight_blockers}unclassified; "
[[ "$lightweight_candidate" == "false" ]] && lightweight_blockers="${lightweight_blockers}5+ top-level dirs; "
[[ "$has_ci" == "true" ]] && lightweight_blockers="${lightweight_blockers}CI present; "
[[ "$has_deploy" == "true" ]] && lightweight_blockers="${lightweight_blockers}deployment surface; "
[[ "$has_public_surface" == "true" ]] && lightweight_blockers="${lightweight_blockers}public distribution surface; "

if [[ -z "$lightweight_blockers" ]]; then
  lightweight_eligible="true"
else
  lightweight_eligible="false"
fi

# effective == detected. Promotion is a decision, never an inference.
effective_type="$project_type"

printf "project_type\tdetected\t%s\n" "$project_type"
printf "project_type\teffective\t%s\n" "$effective_type"
printf "project_type\ttop_level_dirs\t%s\n" "$top_dirs"
printf "project_type\tlightweight_candidate\t%s\n" "$lightweight_candidate"
printf "project_type\thas_ci\t%s\n" "$has_ci"
printf "project_type\thas_deploy_surface\t%s\n" "$has_deploy"
printf "project_type\thas_public_surface\t%s\n" "$has_public_surface"
printf "project_type\tlightweight_eligible\t%s\n" "$lightweight_eligible"
if [[ -n "$lightweight_blockers" ]]; then
  printf "project_type\tlightweight_blocked_by\t%s\n" "$lightweight_blockers"
fi
printf "project_type\tapps_dirs\t%s\n" "$apps_count"
printf "project_type\tpackages_dirs\t%s\n" "$packages_count"
printf "project_type\tcmd_dirs\t%s\n" "$cmd_count"

# ── 2. Entrypoints ─────────────────────────────────────────────
# SKILL.md §Evidence Completeness Gate requires "at least one entry point
# identified". Emitting the inventory here is what makes that gate checkable
# instead of a prose aspiration.
echo ""
echo "--- entrypoints ---"

entrypoint_count=0
emit_entry() {
  printf "entrypoint\t%s\t%s\n" "$1" "$2"
  entrypoint_count=$((entrypoint_count + 1))
}

# In a monorepo the entrypoints live inside the modules, not at the root — a
# root-only probe would report zero and trip the no-entrypoint blocker.
#
# Find modules by their MANIFEST, not by a fixed parent-directory list. The earlier
# version walked only apps/, packages/, services/, so a Cargo workspace laid out as
# crates/*/Cargo.toml (the conventional Rust shape) routed to monorepo with
# entrypoint_count=0 and then degraded on its own success.
if [[ "$project_type" == "monorepo" ]]; then
  module_manifests=$(find . -mindepth 2 -maxdepth 3 \
    -type d \( "${PRUNE[@]}" \) -prune -o \
    -type f \( -name 'go.mod' -o -name 'Cargo.toml' -o -name 'package.json' -o -name 'pyproject.toml' \) -print \
    2>/dev/null | sed 's|^\./||' | sort)
  seen_modules=""
  while IFS= read -r manifest; do
    [[ -n "$manifest" ]] || continue
    mod=$(dirname "$manifest")
    case " ${seen_modules} " in
      *" ${mod} "*) continue ;;
    esac
    seen_modules="${seen_modules} ${mod}"
    emit_entry module "$mod"
  done <<< "$module_manifests"
fi

if [[ "$go_main_count" -gt 0 ]]; then
  while IFS= read -r m; do
    [[ -n "$m" ]] && emit_entry go_main "$m"
  done <<< "$go_mains"
elif [[ "$has_go_mod" == "true" ]]; then
  go_pkg=$(find . -maxdepth 3 -type d \( "${PRUNE[@]}" \) -prune -o -type f -name '*.go' -print 2>/dev/null | sed 's|^\./||' | head -1)
  [[ -n "$go_pkg" ]] && emit_entry go_package "$(grep '^module ' go.mod 2>/dev/null | awk '{print $2}')"
fi

if [[ "$has_package_json" == "true" ]]; then
  [[ -n "$node_bin" ]] && emit_entry node_bin "$node_bin"
  [[ -n "$node_module_entry" ]] && emit_entry node_module "$node_module_entry"
  [[ "$node_start" == "true" ]] && emit_entry node_start "scripts.start"
fi

[[ "$rust_bin" == "true" ]] && emit_entry rust_bin "src/main.rs"
[[ "$rust_lib" == "true" ]] && emit_entry rust_lib "src/lib.rs"
[[ "$py_service" == "true" ]] && emit_entry py_service "manage.py/wsgi.py/asgi.py"
[[ "$py_scripts" == "true" ]] && emit_entry py_script "pyproject.toml [project.scripts]"
if [[ "$entrypoint_count" -eq 0 && ( "$has_pyproject" == "true" || "$has_setup_py" == "true" ) ]]; then
  emit_entry py_package "pyproject.toml/setup.py"
fi

exec_scripts=$(find . -maxdepth 2 -type d \( "${PRUNE[@]}" \) -prune -o -type f -perm -u+x \( -name '*.sh' -o -name '*.py' \) -print 2>/dev/null | sed 's|^\./||' | head -3)
if [[ -n "$exec_scripts" ]]; then
  while IFS= read -r s; do
    [[ -n "$s" ]] && emit_entry exec_script "$s"
  done <<< "$exec_scripts"
fi

printf "entrypoint\tcount\t%s\n" "$entrypoint_count"

# ── 3. Language Version Detection ───────────────────────────────
echo ""
echo "--- language_version ---"

if [[ "$has_go_mod" == "true" ]]; then
  go_ver=$(grep '^go ' go.mod 2>/dev/null | awk '{print $2}')
  printf "language\tgo\t%s\n" "${go_ver:-unknown}"
fi

if [[ "$has_package_json" == "true" ]]; then
  node_ver=$(pkg_json engines_node)
  printf "language\tnode\t%s\n" "${node_ver:-not specified}"
fi

if [[ "$has_cargo" == "true" ]]; then
  rust_ver=$(grep '^rust-version' Cargo.toml 2>/dev/null | head -1 | cut -d'"' -f2)
  printf "language\trust\t%s\n" "${rust_ver:-not specified}"
fi

if [[ "$has_pyproject" == "true" ]]; then
  py_ver=$(grep 'requires-python' pyproject.toml 2>/dev/null | head -1 | cut -d'"' -f2)
  printf "language\tpython\t%s\n" "${py_ver:-not specified}"
fi

# ── 4. Build System Detection ──────────────────────────────────
echo ""
echo "--- build_system ---"

if [[ -f Makefile ]]; then
  make_targets=$(grep -E '^[a-zA-Z_-]+:' Makefile 2>/dev/null | cut -d: -f1 | head -20 | tr '\n' ',' | sed 's/,$//')
  printf "build\tmakefile\ttrue\n"
  printf "build\tmake_targets\t%s\n" "${make_targets:-none}"
else
  printf "build\tmakefile\tfalse\n"
fi

if [[ "$has_package_json" == "true" ]]; then
  npm_scripts=$(pkg_json scripts)
  printf "build\tpackage_json_scripts\t%s\n" "${npm_scripts:-none}"
fi

[[ -f docker-compose.yml || -f docker-compose.yaml ]] && printf "build\tdocker_compose\ttrue\n" || printf "build\tdocker_compose\tfalse\n"
[[ -f Dockerfile ]] && printf "build\tdockerfile\ttrue\n" || printf "build\tdockerfile\tfalse\n"

# ── 5. CI Platform Detection ──────────────────────────────────
echo ""
echo "--- ci_platform ---"

# find (not ls globs): unmatched globs make ls exit non-zero and pollute output.
# The directory existing is NOT the signal — an empty .github/workflows/ used to
# report github_actions=true and invited a CI badge with no workflow behind it.
wf_files=""
if [[ -d .github/workflows ]]; then
  wf_files=$(find .github/workflows -maxdepth 1 -type f \( -name '*.yml' -o -name '*.yaml' \) 2>/dev/null | sort | head -5)
fi
if [[ -n "$wf_files" ]]; then
  printf "ci\tgithub_actions\ttrue\n"
  for f in $wf_files; do
    printf "ci\tworkflow_file\t%s\n" "$f"
  done
else
  printf "ci\tgithub_actions\tfalse\n"
  [[ -d .github/workflows ]] && printf "ci\tgithub_actions_note\tworkflows dir exists but contains no workflow file\n"
fi

[[ -f .gitlab-ci.yml ]] && printf "ci\tgitlab_ci\ttrue\n" || printf "ci\tgitlab_ci\tfalse\n"
[[ -f Jenkinsfile ]] && printf "ci\tjenkins\ttrue\n" || printf "ci\tjenkins\tfalse\n"
[[ -f .circleci/config.yml ]] && printf "ci\tcircleci\ttrue\n" || printf "ci\tcircleci\tfalse\n"

# ── 6. Configuration Detection ─────────────────────────────────
echo ""
echo "--- configuration ---"

[[ -f .env.example ]] && printf "config\tenv_example\ttrue\n" || printf "config\tenv_example\tfalse\n"
[[ -f .env.sample ]] && printf "config\tenv_sample\ttrue\n"
[[ -d config ]] && printf "config\tconfig_dir\ttrue\n" || printf "config\tconfig_dir\tfalse\n"

if [[ -f .env.example ]]; then
  env_vars=$(grep -E '^[A-Z_]+=' .env.example 2>/dev/null | cut -d= -f1 | head -20 | tr '\n' ',' | sed 's/,$//')
  printf "config\tenv_vars\t%s\n" "${env_vars:-none}"
fi

# ── 7. Community Files Detection ───────────────────────────────
echo ""
echo "--- community_files ---"

for f in LICENSE LICENSE.md LICENSE.txt COPYING CONTRIBUTING.md CODE_OF_CONDUCT.md SECURITY.md CHANGELOG.md; do
  if [[ -f "$f" ]]; then
    printf "community\t%s\ttrue\n" "$f"
  else
    printf "community\t%s\tfalse\n" "$f"
  fi
done

# License type came only from a file literally named LICENSE; LICENSE.md was
# reported as present but never classified, so the badge lost its type.
license_file=""
for f in LICENSE LICENSE.md LICENSE.txt COPYING; do
  [[ -f "$f" ]] && { license_file="$f"; break; }
done
if [[ -n "$license_file" ]]; then
  # Scan first 5 lines: GPL's first line is "GNU GENERAL PUBLIC LICENSE",
  # which contains no contiguous "GPL" — match the spelled-out form too.
  license_type=$(head -5 "$license_file" | grep -oiE 'MIT|Apache|BSD|GNU (AFFERO |LESSER )?GENERAL PUBLIC|GPL|ISC|MPL|Unlicense' | head -1)
  case "$(echo "${license_type:-}" | tr '[:lower:]' '[:upper:]')" in
    "GNU AFFERO GENERAL PUBLIC") license_type="AGPL" ;;
    "GNU LESSER GENERAL PUBLIC") license_type="LGPL" ;;
    "GNU GENERAL PUBLIC")        license_type="GPL" ;;
  esac
  printf "community\tlicense_file\t%s\n" "$license_file"
  printf "community\tlicense_type\t%s\n" "${license_type:-unknown}"
fi

# ── 8. Coverage / Quality Tools ────────────────────────────────
echo ""
echo "--- quality_tools ---"

[[ -f .codecov.yml || -f codecov.yml ]] && printf "quality\tcodecov\ttrue\n" || printf "quality\tcodecov\tfalse\n"
[[ -f .coveralls.yml ]] && printf "quality\tcoveralls\ttrue\n" || printf "quality\tcoveralls\tfalse\n"
[[ -f .golangci.yml || -f .golangci.yaml ]] && printf "quality\tgolangci_lint\ttrue\n" || printf "quality\tgolangci_lint\tfalse\n"
[[ -f .eslintrc.js || -f .eslintrc.json || -f .eslintrc.yml || -f eslint.config.js ]] && printf "quality\teslint\ttrue\n"
[[ -f .prettierrc || -f .prettierrc.json ]] && printf "quality\tprettier\ttrue\n"

test_files=$(find . -maxdepth 4 -type d \( "${PRUNE[@]}" \) -prune -o -type f \( -name '*_test.go' -o -name 'test_*.py' -o -name '*_test.py' -o -name '*.test.ts' -o -name '*.test.js' -o -name '*.spec.ts' -o -name '*.spec.js' \) -print 2>/dev/null | head -50 | wc -l | tr -d ' ')
printf "quality\ttest_files\t%s\n" "${test_files:-0}"

# ── 9. Existing README Analysis ────────────────────────────────
echo ""
echo "--- existing_readme ---"

if [[ -f README.md ]]; then
  readme_lines=$(wc -l < README.md | tr -d ' ')
  # grep -c prints the count itself; an `|| echo 0` fallback here would emit a
  # SECOND zero on no-match (grep -c prints 0 AND exits 1) — use ${var:-0}.
  readme_sections=$(grep -cE '^#{1,3} ' README.md 2>/dev/null)
  has_toc=$(grep -ciE '\[.*\]\(#' README.md 2>/dev/null)
  has_badges=$(grep -cE '!\[.*\]\(https://' README.md 2>/dev/null)
  readme_sections=${readme_sections:-0}
  has_toc=${has_toc:-0}
  has_badges=${has_badges:-0}
  printf "readme\texists\ttrue\n"
  printf "readme\tlines\t%s\n" "${readme_lines:-0}"
  printf "readme\tsections\t%s\n" "$readme_sections"
  printf "readme\thas_toc\t%s\n" "$([[ "$has_toc" -gt 2 ]] && echo true || echo false)"
  printf "readme\thas_badges\t%s\n" "$([[ "$has_badges" -gt 0 ]] && echo true || echo false)"
else
  printf "readme\texists\tfalse\n"
fi

# ── 10. Repo Visibility ────────────────────────────────────────
echo ""
echo "--- visibility ---"

remote_url=$(git remote get-url origin 2>/dev/null || echo "")
if [[ -n "$remote_url" ]]; then
  printf "repo\tremote_url\t%s\n" "$remote_url"
  if echo "$remote_url" | grep -q 'github.com'; then
    repo_path=$(echo "$remote_url" | sed -E 's|.*github\.com[:/](.+)(\.git)?$|\1|' | sed 's/\.git$//')
    is_private=$(gh api "repos/$repo_path" --jq '.private' 2>/dev/null || echo "unknown")
    printf "repo\tprivate\t%s\n" "${is_private:-unknown}"
  fi
else
  printf "repo\tremote_url\tnone\n"
fi

# ── 11. Summary Verdict ───────────────────────────────────────
echo ""
echo "--- verdict ---"

blockers=""
if [[ "$project_type" == "unknown" ]]; then
  blockers="${blockers}BLOCKER: cannot determine project type; "
fi
# go.work counts: a Go workspace root legitimately has no go.mod of its own.
if [[ ! -f Makefile && "$has_package_json" == "false" && "$has_go_mod" == "false" && "$has_go_work" == "false" && "$has_cargo" == "false" && "$has_pyproject" == "false" && "$has_setup_py" == "false" ]]; then
  blockers="${blockers}BLOCKER: no build system detected; "
fi
if [[ "$entrypoint_count" -eq 0 ]]; then
  blockers="${blockers}BLOCKER: no entrypoint identified; "
fi

if [[ -n "$blockers" ]]; then
  printf "verdict\tstatus\tDEGRADED\n"
  printf "verdict\tblockers\t%s\n" "$blockers"
else
  printf "verdict\tstatus\tREADY\n"
  # The effective type, not the base classification: this is the line generation and
  # lint_readme.py both act on, and they must not be able to disagree.
  printf "verdict\tproject_type\t%s\n" "$effective_type"
  printf "verdict\tbase_type\t%s\n" "$project_type"
fi

echo ""
echo "=== discovery complete ==="
exit 0
