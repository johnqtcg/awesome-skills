#!/usr/bin/env bash
set -uo pipefail

# Scan a repository and print a structured E2E readiness report.
# Claude uses this deterministic report to make informed decisions instead of guessing.
#
# `set -e` is deliberately NOT enabled: this script is a probe, and almost every
# check is a grep/find that legitimately returns non-zero when a thing is absent.
# Under `set -e` the first absent thing would abort the scan and silently truncate
# the report, which reads as "nothing else found" rather than "scan died".
#
# Usage: bash discover_e2e_needs.sh [project-root]
# Output: TSV to stdout. Exit 0 = scan completed (regardless of verdict).
#         Exit 2 = scan could not run (bad root).

ROOT="${1:-.}"

if [ ! -d "${ROOT}" ]; then
  echo "discover_e2e_needs.sh: not a directory: ${ROOT}" >&2
  exit 2
fi

# has_dep <package.json path> <dependency name>
# Matches a dependency key, not an arbitrary substring, so that a package named
# "next-auth" does not register as "next" and "react-native-web" does not
# register as "react".
has_dep() {
  grep -Eq "\"$2\"[[:space:]]*:" "$1" 2>/dev/null
}

echo "=== E2E Readiness Report ==="
echo "scan_root	${ROOT}"
echo "scan_time	$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo ""

PKG="${ROOT}/package.json"
HAS_PKG="false"
[ -f "${PKG}" ] && HAS_PKG="true"

# --- 1) Runner detection (Playwright and alternatives) ---
echo "--- runner ---"
PW_VERSION="not_installed"
PW_CONFIG="none"
OTHER_RUNNER="none"

if [ "${HAS_PKG}" = "true" ]; then
  PW_VERSION=$(grep -o '"@playwright/test"[[:space:]]*:[[:space:]]*"[^"]*"' "${PKG}" 2>/dev/null \
    | head -1 | grep -o '[0-9][0-9.]*' | head -1)
  [ -z "${PW_VERSION}" ] && PW_VERSION="not_installed"

  # An existing E2E runner is a routing fact, not a blocker. Adding a second
  # framework alongside one already in use is usually the wrong recommendation.
  for dep in cypress webdriverio @wdio/cli nightwatch puppeteer testcafe codeceptjs; do
    if has_dep "${PKG}" "${dep}"; then
      OTHER_RUNNER="${dep}"
      break
    fi
  done
fi

for cfg in playwright.config.ts playwright.config.js playwright.config.mjs \
           playwright.config.cjs playwright.config.mts; do
  if [ -f "${ROOT}/${cfg}" ]; then
    PW_CONFIG="${cfg}"
    break
  fi
done

echo "playwright_version	${PW_VERSION}"
echo "playwright_config	${PW_CONFIG}"
echo "other_e2e_runner	${OTHER_RUNNER}"

# --- 2) Node.js version ---
echo ""
echo "--- node ---"
NODE_VERSION="unknown"
if command -v node >/dev/null 2>&1; then
  NODE_VERSION=$(node --version 2>/dev/null | sed 's/^v//')
  [ -z "${NODE_VERSION}" ] && NODE_VERSION="unknown"
fi

NVMRC="none"
if [ -f "${ROOT}/.nvmrc" ]; then
  NVMRC=$(tr -d '[:space:]' < "${ROOT}/.nvmrc")
elif [ -f "${ROOT}/.node-version" ]; then
  NVMRC=$(tr -d '[:space:]' < "${ROOT}/.node-version")
fi

echo "node_version	${NODE_VERSION}"
echo "nvmrc	${NVMRC:-none}"

# --- 3) Framework detection ---
echo ""
echo "--- framework ---"
FRAMEWORK="unknown"
if [ "${HAS_PKG}" = "true" ]; then
  if has_dep "${PKG}" "@tauri-apps/api" || has_dep "${PKG}" "@tauri-apps/cli"; then
    # Checked before the web frameworks: a Tauri app also depends on React/Vue,
    # and the desktop shell is what determines the runner.
    FRAMEWORK="tauri"
  elif has_dep "${PKG}" "electron"; then
    FRAMEWORK="electron"
  elif has_dep "${PKG}" "next"; then
    FRAMEWORK="nextjs"
    if [ -d "${ROOT}/app" ]; then
      FRAMEWORK="nextjs-app-router"
    elif [ -d "${ROOT}/pages" ]; then
      FRAMEWORK="nextjs-pages-router"
    fi
  elif has_dep "${PKG}" "nuxt"; then
    FRAMEWORK="nuxt"
  elif has_dep "${PKG}" "@remix-run/react"; then
    FRAMEWORK="remix"
  elif has_dep "${PKG}" "react-native-web" || has_dep "${PKG}" "expo"; then
    FRAMEWORK="react-native-web"
  elif has_dep "${PKG}" "react-native"; then
    FRAMEWORK="react-native-native"
  elif has_dep "${PKG}" "svelte"; then
    FRAMEWORK="svelte"
  elif has_dep "${PKG}" "vue"; then
    FRAMEWORK="vue-spa"
  elif has_dep "${PKG}" "react"; then
    FRAMEWORK="react-spa"
  fi
fi

echo "framework	${FRAMEWORK}"

# --- 3b) Workspace / monorepo detection ---
echo ""
echo "--- workspace ---"
WORKSPACE="none"
if [ "${HAS_PKG}" = "true" ] && grep -q '"workspaces"' "${PKG}" 2>/dev/null; then
  WORKSPACE="npm-workspaces"
fi
[ -f "${ROOT}/pnpm-workspace.yaml" ] && WORKSPACE="pnpm-workspace"
[ -f "${ROOT}/turbo.json" ] && WORKSPACE="turborepo"
[ -f "${ROOT}/nx.json" ] && WORKSPACE="nx"
[ -f "${ROOT}/lerna.json" ] && WORKSPACE="lerna"
echo "workspace	${WORKSPACE}"
if [ "${WORKSPACE}" != "none" ]; then
  echo "workspace_note	resolve the owning package before generating commands; root config may not apply"
fi

# --- 3c) Non-JS web backends ---
echo ""
echo "--- other_languages ---"
GO_MOD="false"
GO_WEB_CMD="none"
GO_E2E_DIR="none"
GO_E2E_COUNT=0
GO_MAKEFILE_E2E="none"

if [ -f "${ROOT}/go.mod" ]; then
  GO_MOD="true"
  for cmd_dir in "${ROOT}"/cmd/*/; do
    [ -f "${cmd_dir}main.go" ] || continue
    if grep -Eq 'net/http|gin-gonic|go-chi|labstack/echo|gofiber|gorilla/mux' "${cmd_dir}main.go" 2>/dev/null; then
      GO_WEB_CMD="$(basename "${cmd_dir}")"
      break
    fi
  done
  if [ "${GO_WEB_CMD}" = "none" ] && [ -f "${ROOT}/main.go" ]; then
    if grep -Eq 'net/http|gin-gonic|go-chi|labstack/echo|gofiber|gorilla/mux' "${ROOT}/main.go" 2>/dev/null; then
      GO_WEB_CMD="root_main.go"
    fi
  fi
  if [ "${GO_WEB_CMD}" = "none" ]; then
    for handler in "${ROOT}"/internal/*/handler.go "${ROOT}"/internal/*/server.go "${ROOT}"/internal/*/router.go; do
      if [ -f "${handler}" ]; then
        GO_WEB_CMD="detected_via_$(basename "$(dirname "${handler}")")"
        break
      fi
    done
  fi
fi

for dir in tests/e2e test/e2e e2e; do
  if [ -d "${ROOT}/${dir}" ]; then
    cnt=$(find "${ROOT}/${dir}" -name '*_test.go' 2>/dev/null | wc -l | tr -d ' ')
    if [ "${cnt:-0}" -gt 0 ]; then
      GO_E2E_DIR="${dir}"
      GO_E2E_COUNT="${cnt}"
      break
    fi
  fi
done

if [ -f "${ROOT}/Makefile" ]; then
  # `|| true` is required: grep exits 1 when a Makefile has no e2e target, which
  # is the common case and must not abort the scan.
  e2e_targets=$(grep -oE '^[a-zA-Z0-9_.-]*e2e[a-zA-Z0-9_.-]*:' "${ROOT}/Makefile" 2>/dev/null \
    | tr -d ':' | tr '\n' ' ' || true)
  [ -n "${e2e_targets}" ] && GO_MAKEFILE_E2E="${e2e_targets}"
fi

PY_WEB="false"
if [ -f "${ROOT}/requirements.txt" ] || [ -f "${ROOT}/pyproject.toml" ] || [ -f "${ROOT}/Pipfile" ]; then
  if grep -rEiql 'fastapi|flask|django|starlette|aiohttp|tornado' \
      "${ROOT}/requirements.txt" "${ROOT}/pyproject.toml" "${ROOT}/Pipfile" 2>/dev/null; then
    PY_WEB="true"
  fi
fi

RUST_WEB="false"
if [ -f "${ROOT}/Cargo.toml" ]; then
  grep -Eq 'axum|actix-web|rocket|warp|tide' "${ROOT}/Cargo.toml" 2>/dev/null && RUST_WEB="true"
fi

echo "go_mod	${GO_MOD}"
echo "go_web_cmd	${GO_WEB_CMD}"
echo "go_e2e_directory	${GO_E2E_DIR}"
echo "go_e2e_test_files	${GO_E2E_COUNT}"
echo "go_makefile_e2e_targets	${GO_MAKEFILE_E2E}"
echo "python_web	${PY_WEB}"
echo "rust_web	${RUST_WEB}"

# --- 4) Existing E2E tests ---
echo ""
echo "--- existing_tests ---"
E2E_DIR="none"
E2E_COUNT=0

for dir in tests/e2e e2e test/e2e cypress/e2e tests; do
  if [ -d "${ROOT}/${dir}" ]; then
    JS_COUNT=$(find "${ROOT}/${dir}" \
      \( -name '*.spec.ts' -o -name '*.spec.js' -o -name '*.spec.mjs' \
         -o -name '*.test.ts' -o -name '*.test.js' -o -name '*.cy.ts' -o -name '*.cy.js' \) \
      2>/dev/null | wc -l | tr -d ' ')
    GO_COUNT=$(find "${ROOT}/${dir}" -name '*_test.go' 2>/dev/null | wc -l | tr -d ' ')
    PY_COUNT=$(find "${ROOT}/${dir}" -name 'test_*.py' 2>/dev/null | wc -l | tr -d ' ')
    E2E_DIR="${dir}"
    E2E_COUNT=$(( ${JS_COUNT:-0} + ${GO_COUNT:-0} + ${PY_COUNT:-0} ))
    break
  fi
done

echo "e2e_directory	${E2E_DIR}"
echo "e2e_test_files	${E2E_COUNT}"

# --- 5) Base URL and credential sources ---
echo ""
echo "--- environment ---"

ENV_FILES=""
for ef in .env .env.local .env.test .env.e2e .env.example; do
  [ -f "${ROOT}/${ef}" ] && ENV_FILES="${ENV_FILES}${ef} "
done
echo "env_files	${ENV_FILES:-none}"

# Four states, because "the name appears somewhere" and "a value exists" are
# different facts and conflating them produces a false `ready`:
#
#   available  a non-empty value exists (live process env, or a real .env file)
#   declared   the name is known but has no value here — a .env.example entry, or
#              `E2E_PASS=` with nothing after the `=`. Proves the variable is
#              expected; proves nothing about runtime.
#   missing    no evidence the project uses this variable at all
#
# Never print a value. Secrets leak through CI logs and transcripts, and a
# "check" that echoes the value is itself the leak. Below, only emptiness is
# tested; the value never reaches stdout.
HAS_E2E_BASE_URL="missing"
HAS_E2E_USER="missing"
HAS_E2E_PASS="missing"

# env_state_in_file <file> <var> -> available | declared | missing
env_state_in_file() {
  local file="$1" var="$2" line value
  line=$(grep -E "^[[:space:]]*(export[[:space:]]+)?${var}=" "${file}" 2>/dev/null | tail -1)
  if [ -z "${line}" ]; then
    # The name may still be mentioned in a comment or as documentation.
    grep -q "${var}" "${file}" 2>/dev/null && echo "declared" || echo "missing"
    return
  fi
  value="${line#*=}"

  # Order matters. Quoted values first: anything after the closing quote is a
  # comment, and the quoted body is the value even if it contains a '#'.
  case "${value}" in
    [[:space:]]*) value="${value#"${value%%[![:space:]]*}"}" ;;
  esac
  case "${value}" in
    '"'*)
      value="${value#\"}"
      value="${value%%\"*}"
      ;;
    "'"*)
      value="${value#\'}"
      value="${value%%\'*}"
      ;;
    *)
      # Unquoted: an inline comment starts at a '#' that begins the value or
      # follows whitespace. `E2E_PASS= # TODO: inject from vault` declares the
      # variable and supplies nothing — stripping only whitespace and quotes
      # left "#TODO:injectfromvault" and reported it as an available value.
      case "${value}" in
        '#'*) value="" ;;
        *) value="${value%%[[:space:]]#*}" ;;
      esac
      value="$(printf '%s' "${value}" | tr -d '[:space:]')"
      ;;
  esac

  [ -n "${value}" ] && echo "available" || echo "declared"
}

# promote <current> <candidate> -> the stronger of the two
promote() {
  case "$1:$2" in
    *:available) echo "available" ;;
    available:*) echo "available" ;;
    *:declared) echo "declared" ;;
    declared:*) echo "declared" ;;
    *) echo "missing" ;;
  esac
}

for ef in .env .env.local .env.test .env.e2e; do
  [ -f "${ROOT}/${ef}" ] || continue
  HAS_E2E_BASE_URL=$(promote "${HAS_E2E_BASE_URL}" "$(env_state_in_file "${ROOT}/${ef}" E2E_BASE_URL)")
  HAS_E2E_USER=$(promote "${HAS_E2E_USER}" "$(env_state_in_file "${ROOT}/${ef}" E2E_USER)")
  HAS_E2E_PASS=$(promote "${HAS_E2E_PASS}" "$(env_state_in_file "${ROOT}/${ef}" E2E_PASS)")
done

# .env.example is a template. Even a filled-in value there is documentation, not
# configuration, so it can never raise a variable above `declared`.
if [ -f "${ROOT}/.env.example" ]; then
  for var in E2E_BASE_URL E2E_USER E2E_PASS; do
    if grep -q "${var}" "${ROOT}/.env.example" 2>/dev/null; then
      case "${var}" in
        E2E_BASE_URL) HAS_E2E_BASE_URL=$(promote "${HAS_E2E_BASE_URL}" declared) ;;
        E2E_USER) HAS_E2E_USER=$(promote "${HAS_E2E_USER}" declared) ;;
        E2E_PASS) HAS_E2E_PASS=$(promote "${HAS_E2E_PASS}" declared) ;;
      esac
    fi
  done
fi

# The live process environment is the strongest evidence: a value is present now.
[ -n "${E2E_BASE_URL:-}" ] && HAS_E2E_BASE_URL="available"
[ -n "${E2E_USER:-}" ] && HAS_E2E_USER="available"
[ -n "${E2E_PASS:-}" ] && HAS_E2E_PASS="available"

BASE_URL_IN_CONFIG="false"
if [ "${PW_CONFIG}" != "none" ] && [ -f "${ROOT}/${PW_CONFIG}" ]; then
  grep -q 'baseURL' "${ROOT}/${PW_CONFIG}" 2>/dev/null && BASE_URL_IN_CONFIG="true"
fi

# Projects commonly use their own names. Report what was found rather than
# insisting on the E2E_* convention.
CUSTOM_URL_VARS="none"
if [ -n "${ENV_FILES}" ]; then
  found=$(grep -hoE '^[A-Z0-9_]*(BASE_URL|BASEURL|APP_URL|SITE_URL|HOST|ENDPOINT)[A-Z0-9_]*' \
    "${ROOT}"/.env* 2>/dev/null | sort -u | tr '\n' ' ' || true)
  [ -n "${found}" ] && CUSTOM_URL_VARS="${found}"
fi

echo "E2E_BASE_URL	${HAS_E2E_BASE_URL}"
echo "E2E_USER	${HAS_E2E_USER}"
echo "E2E_PASS	${HAS_E2E_PASS}"
echo "base_url_in_playwright_config	${BASE_URL_IN_CONFIG}"
echo "candidate_url_env_vars	${CUSTOM_URL_VARS}"
echo "env_state_legend	available=value present | declared=name known, no value | missing=no evidence"

# --- 6) Dev server detection ---
echo ""
echo "--- dev_server ---"
DEV_CMD="unknown"
START_CMD="unknown"
DEV_PORT="unknown"
WEB_SERVER_IN_CONFIG="false"

if [ "${HAS_PKG}" = "true" ]; then
  DEV_CMD=$(grep -o '"dev"[[:space:]]*:[[:space:]]*"[^"]*"' "${PKG}" 2>/dev/null \
    | head -1 | sed 's/.*:[[:space:]]*"//; s/"$//')
  [ -z "${DEV_CMD}" ] && DEV_CMD="unknown"
  START_CMD=$(grep -o '"start"[[:space:]]*:[[:space:]]*"[^"]*"' "${PKG}" 2>/dev/null \
    | head -1 | sed 's/.*:[[:space:]]*"//; s/"$//')
  [ -z "${START_CMD}" ] && START_CMD="unknown"
fi

if [ "${PW_CONFIG}" != "none" ] && [ -f "${ROOT}/${PW_CONFIG}" ]; then
  grep -q 'webServer' "${ROOT}/${PW_CONFIG}" 2>/dev/null && WEB_SERVER_IN_CONFIG="true"
  port=$(grep -oE 'localhost:[0-9]+|127\.0\.0\.1:[0-9]+' "${ROOT}/${PW_CONFIG}" 2>/dev/null \
    | head -1 | grep -oE '[0-9]+$')
  [ -n "${port}" ] && DEV_PORT="${port}"
fi

echo "dev_command	${DEV_CMD}"
echo "start_command	${START_CMD}"
echo "detected_port	${DEV_PORT}"
echo "web_server_in_config	${WEB_SERVER_IN_CONFIG}"

# --- 7) CI detection ---
echo ""
echo "--- ci ---"
CI_PLATFORM="none"
CI_HAS_E2E="false"

if [ -d "${ROOT}/.github/workflows" ]; then
  CI_PLATFORM="github-actions"
  if grep -rEql 'playwright|cypress|wdio' "${ROOT}/.github/workflows/" 2>/dev/null; then
    CI_HAS_E2E="true"
  fi
elif [ -f "${ROOT}/.gitlab-ci.yml" ]; then
  CI_PLATFORM="gitlab-ci"
  grep -Eq 'playwright|cypress|wdio' "${ROOT}/.gitlab-ci.yml" 2>/dev/null && CI_HAS_E2E="true"
elif [ -f "${ROOT}/Jenkinsfile" ]; then
  CI_PLATFORM="jenkins"
  grep -Eq 'playwright|cypress|wdio' "${ROOT}/Jenkinsfile" 2>/dev/null && CI_HAS_E2E="true"
elif [ -d "${ROOT}/.circleci" ]; then
  CI_PLATFORM="circleci"
fi

echo "ci_platform	${CI_PLATFORM}"
echo "ci_has_e2e	${CI_HAS_E2E}"

# --- 8) A11y and visual regression tooling ---
echo ""
echo "--- tooling ---"
HAS_AXE="false"
HAS_VISUAL="false"

if [ "${HAS_PKG}" = "true" ]; then
  has_dep "${PKG}" "@axe-core/playwright" && HAS_AXE="true"
  for vis in percy @percy/cli chromatic @argos-ci/playwright; do
    if has_dep "${PKG}" "${vis}"; then
      HAS_VISUAL="${vis}"
      break
    fi
  done
fi

if [ "${HAS_VISUAL}" = "false" ] && [ "${E2E_DIR}" != "none" ]; then
  if grep -rq 'toHaveScreenshot' "${ROOT}/${E2E_DIR}" 2>/dev/null; then
    HAS_VISUAL="playwright-built-in"
  fi
fi

echo "axe_core	${HAS_AXE}"
echo "visual_regression	${HAS_VISUAL}"

# --- 9) Summary verdict ---
#
# Two distinct output channels, deliberately kept apart:
#   blockers  — cannot produce a runnable test without this. Genuinely fatal.
#   unknowns  — must be confirmed with the user or by reading the repo. NOT fatal;
#               a public site needs no login, and a baseURL may live in config.
# Collapsing "unknown" into "blocked" is what produces false stop-the-world
# verdicts on public-page suites, Cypress repos, and non-JS projects.
echo ""
echo "--- verdict ---"
BLOCKERS=""
UNKNOWNS=""
PROJECT_TYPE="unknown"
SUGGESTED_RUNNER="unknown"

if [ "${FRAMEWORK}" = "tauri" ]; then
  PROJECT_TYPE="tauri_desktop"
  SUGGESTED_RUNNER="webdriverio+@wdio/tauri-service"
  UNKNOWNS="${UNKNOWNS}playwright_cannot_drive_tauri_webview "
elif [ "${FRAMEWORK}" = "react-native-native" ]; then
  PROJECT_TYPE="native_mobile"
  SUGGESTED_RUNNER="detox_or_maestro"
  UNKNOWNS="${UNKNOWNS}native_mobile_out_of_playwright_scope "
elif [ "${HAS_PKG}" = "true" ]; then
  PROJECT_TYPE="js"
  if [ "${PW_VERSION}" != "not_installed" ]; then
    SUGGESTED_RUNNER="playwright"
  elif [ "${OTHER_RUNNER}" != "none" ]; then
    # Do not recommend adding Playwright next to an in-use runner.
    SUGGESTED_RUNNER="${OTHER_RUNNER}"
    UNKNOWNS="${UNKNOWNS}existing_runner_${OTHER_RUNNER}_confirm_before_adding_playwright "
  else
    SUGGESTED_RUNNER="playwright"
    UNKNOWNS="${UNKNOWNS}no_e2e_runner_installed "
  fi
  if [ "${PW_VERSION}" != "not_installed" ] && [ "${PW_CONFIG}" = "none" ]; then
    UNKNOWNS="${UNKNOWNS}playwright_installed_but_no_config "
  fi
  # Base URL resolution, strongest evidence first:
  #   available            -> a real value exists
  #   config/webServer     -> resolved_from_config, no env var needed
  #   declared             -> the project expects the var but nothing supplies a
  #                           value here. Not fatal: CI may inject it at run time
  #                           and the generated test carries a skip guard. Must be
  #                           confirmed, so it is an unknown.
  #   missing              -> nothing indicates where the URL comes from. Fatal.
  if [ "${HAS_E2E_BASE_URL}" = "available" ]; then
    :
  elif [ "${BASE_URL_IN_CONFIG}" = "true" ] || [ "${WEB_SERVER_IN_CONFIG}" = "true" ]; then
    UNKNOWNS="${UNKNOWNS}base_url_resolved_from_config_verify_it_targets_the_intended_env "
  elif [ "${HAS_E2E_BASE_URL}" = "declared" ]; then
    UNKNOWNS="${UNKNOWNS}base_url_declared_but_unset_confirm_runtime_source "
  else
    BLOCKERS="${BLOCKERS}no_base_url "
  fi

  # Credentials are never a blocker — the journey may be entirely public — but
  # `declared` and `missing` are different conversations.
  case "${HAS_E2E_USER}" in
    available) ;;
    declared)
      UNKNOWNS="${UNKNOWNS}test_account_declared_but_unset_provide_value_or_confirm_public_journey "
      ;;
    *)
      UNKNOWNS="${UNKNOWNS}no_test_account_confirm_whether_journey_needs_auth "
      ;;
  esac
  if [ "${HAS_E2E_USER}" = "available" ] && [ "${HAS_E2E_PASS}" != "available" ]; then
    # A username with no password is a partial config, which fails at login with
    # a misleading error rather than a clear "not configured".
    UNKNOWNS="${UNKNOWNS}test_account_password_not_available "
  fi
elif [ "${GO_MOD}" = "true" ]; then
  PROJECT_TYPE="go"
  [ "${GO_WEB_CMD}" != "none" ] && PROJECT_TYPE="go_web"
  SUGGESTED_RUNNER="go_net_http"
  [ "${GO_E2E_COUNT}" -eq 0 ] && UNKNOWNS="${UNKNOWNS}no_existing_go_e2e_tests "
  [ "${GO_WEB_CMD}" = "none" ] && UNKNOWNS="${UNKNOWNS}no_go_web_entrypoint_found "
elif [ "${PY_WEB}" = "true" ]; then
  PROJECT_TYPE="python_web"
  SUGGESTED_RUNNER="pytest+httpx"
  [ "${E2E_COUNT}" -eq 0 ] && UNKNOWNS="${UNKNOWNS}no_existing_e2e_tests "
  UNKNOWNS="${UNKNOWNS}confirm_base_url_and_startup_command "
elif [ "${RUST_WEB}" = "true" ]; then
  PROJECT_TYPE="rust_web"
  SUGGESTED_RUNNER="cargo_test+reqwest"
  [ "${E2E_COUNT}" -eq 0 ] && UNKNOWNS="${UNKNOWNS}no_existing_e2e_tests "
  UNKNOWNS="${UNKNOWNS}confirm_base_url_and_startup_command "
else
  UNKNOWNS="${UNKNOWNS}project_type_not_recognised_inspect_repo_manually "
fi

echo "project_type	${PROJECT_TYPE}"
echo "suggested_runner	${SUGGESTED_RUNNER}"

if [ -z "${BLOCKERS}" ]; then
  echo "blockers	none"
else
  echo "blockers	${BLOCKERS}"
fi

if [ -z "${UNKNOWNS}" ]; then
  echo "unknowns	none"
else
  echo "unknowns	${UNKNOWNS}"
fi

if [ -n "${BLOCKERS}" ]; then
  echo "readiness	blocked"
elif [ -n "${UNKNOWNS}" ]; then
  echo "readiness	needs_confirmation"
else
  echo "readiness	ready"
fi

echo ""
echo "=== End Report ==="
