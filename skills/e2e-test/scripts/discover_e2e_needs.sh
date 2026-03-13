#!/usr/bin/env bash
set -euo pipefail

# Scan the current repository and outputexample a structured E2E readiness report.
# Claude uses this deterministic outputexample to make informed decisions instead of guessing.
#
# Usage: bash discover_e2e_needs.sh [project-root]
# Output: TSV-formatted report to stdout

ROOT="${1:-.}"

echo "=== E2E Readiness Report ==="
echo "scan_root	${ROOT}"
echo "scan_time	$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo ""

# --- 1) Playwright detection ---
echo "--- playwright ---"
PW_VERSION="not_installed"
PW_CONFIG="none"

if [ -f "${ROOT}/package.json" ]; then
  PW_VERSION=$(grep -o '"@playwright/test"[[:space:]]*:[[:space:]]*"[^"]*"' "${ROOT}/package.json" 2>/dev/null \
    | head -1 | grep -o '[0-9][0-9.]*' || echo "not_installed")
fi

for cfg in playwright.config.ts playwright.config.js playwright.config.mjs; do
  if [ -f "${ROOT}/${cfg}" ]; then
    PW_CONFIG="${cfg}"
    break
  fi
done

echo "playwright_version	${PW_VERSION}"
echo "playwright_config	${PW_CONFIG}"

# --- 2) Node.js version ---
echo ""
echo "--- node ---"
NODE_VERSION="unknown"
if command -v node &>/dev/null; then
  NODE_VERSION=$(node --version 2>/dev/null | sed 's/^v//' || echo "unknown")
fi

NVMRC="none"
if [ -f "${ROOT}/.nvmrc" ]; then
  NVMRC=$(cat "${ROOT}/.nvmrc" | tr -d '[:space:]')
elif [ -f "${ROOT}/.node-version" ]; then
  NVMRC=$(cat "${ROOT}/.node-version" | tr -d '[:space:]')
fi

echo "node_version	${NODE_VERSION}"
echo "nvmrc	${NVMRC}"

# --- 3) Framework detection ---
echo ""
echo "--- framework ---"
FRAMEWORK="unknown"
if [ -f "${ROOT}/package.json" ]; then
  PKG=$(cat "${ROOT}/package.json")
  if echo "$PKG" | grep -q '"next"'; then
    FRAMEWORK="nextjs"
    if [ -d "${ROOT}/app" ]; then
      FRAMEWORK="nextjs-app-router"
    elif [ -d "${ROOT}/pages" ]; then
      FRAMEWORK="nextjs-pages-router"
    fi
  elif echo "$PKG" | grep -q '"nuxt"'; then
    FRAMEWORK="nuxt"
  elif echo "$PKG" | grep -q '"@remix-run"'; then
    FRAMEWORK="remix"
  elif echo "$PKG" | grep -q '"react-native-web"'; then
    FRAMEWORK="react-native-web"
  elif echo "$PKG" | grep -q '"vue"'; then
    FRAMEWORK="vue-spa"
  elif echo "$PKG" | grep -q '"react"'; then
    FRAMEWORK="react-spa"
  elif echo "$PKG" | grep -q '"svelte"'; then
    FRAMEWORK="svelte"
  elif echo "$PKG" | grep -q '"electron"'; then
    FRAMEWORK="electron"
  fi
fi

echo "framework	${FRAMEWORK}"

# --- 3b) Go web server detection ---
echo ""
echo "--- go ---"
GO_MOD="false"
GO_WEB_CMD="none"
GO_E2E_DIR="none"
GO_E2E_COUNT=0
GO_MAKEFILE_E2E="none"

if [ -f "${ROOT}/go.mod" ]; then
  GO_MOD="true"
  for cmd_dir in "${ROOT}"/cmd/*/; do
    if [ -f "${cmd_dir}main.go" ]; then
      if grep -ql 'net/http\|gin\|chi\|echo\|fiber\|mux' "${cmd_dir}main.go" 2>/dev/null; then
        GO_WEB_CMD="$(basename "${cmd_dir}")"
        break
      fi
    fi
  done
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
    if [ "${cnt}" -gt 0 ]; then
      GO_E2E_DIR="${dir}"
      GO_E2E_COUNT="${cnt}"
      break
    fi
  fi
done

if [ -f "${ROOT}/Makefile" ]; then
  e2e_targets=$(grep -oE '^[a-zA-Z_-]*e2e[a-zA-Z_-]*:' "${ROOT}/Makefile" 2>/dev/null | tr -d ':' | tr '\n' ' ')
  [ -n "${e2e_targets}" ] && GO_MAKEFILE_E2E="${e2e_targets}"
fi

echo "go_mod	${GO_MOD}"
echo "go_web_cmd	${GO_WEB_CMD}"
echo "go_e2e_directory	${GO_E2E_DIR}"
echo "go_e2e_test_files	${GO_E2E_COUNT}"
echo "go_makefile_e2e_targets	${GO_MAKEFILE_E2E}"

# --- 4) Existing E2E tests ---
echo ""
echo "--- existing_tests ---"
E2E_DIR="none"
E2E_COUNT=0

for dir in tests/e2e e2e tests test/e2e cypress/e2e; do
  if [ -d "${ROOT}/${dir}" ]; then
    JS_COUNT=$(find "${ROOT}/${dir}" -name '*.spec.ts' -o -name '*.spec.js' -o -name '*.test.ts' -o -name '*.test.js' 2>/dev/null | wc -l | tr -d ' ')
    GO_COUNT=$(find "${ROOT}/${dir}" -name '*_test.go' 2>/dev/null | wc -l | tr -d ' ')
    E2E_DIR="${dir}"
    E2E_COUNT=$(( JS_COUNT + GO_COUNT ))
    break
  fi
done

echo "e2e_directory	${E2E_DIR}"
echo "e2e_test_files	${E2E_COUNT}"

# --- 5) Auth / env detection ---
echo ""
echo "--- environment ---"

ENV_FILES=""
for ef in .env .env.local .env.test .env.e2e .env.example; do
  if [ -f "${ROOT}/${ef}" ]; then
    ENV_FILES="${ENV_FILES}${ef} "
  fi
done
echo "env_files	${ENV_FILES:-none}"

HAS_E2E_BASE_URL="missing"
HAS_E2E_USER="missing"
HAS_E2E_PASS="missing"

for ef in .env .env.local .env.test .env.e2e; do
  if [ -f "${ROOT}/${ef}" ]; then
    grep -q 'E2E_BASE_URL' "${ROOT}/${ef}" 2>/dev/null && HAS_E2E_BASE_URL="available"
    grep -q 'E2E_USER' "${ROOT}/${ef}" 2>/dev/null && HAS_E2E_USER="available"
    grep -q 'E2E_PASS' "${ROOT}/${ef}" 2>/dev/null && HAS_E2E_PASS="available"
  fi
done

echo "E2E_BASE_URL	${HAS_E2E_BASE_URL}"
echo "E2E_USER	${HAS_E2E_USER}"
echo "E2E_PASS	${HAS_E2E_PASS}"

# --- 6) Dev server detection ---
echo ""
echo "--- dev_server ---"
DEV_CMD="unknown"
DEV_PORT="unknown"

if [ -f "${ROOT}/package.json" ]; then
  DEV_CMD=$(grep -o '"dev"[[:space:]]*:[[:space:]]*"[^"]*"' "${ROOT}/package.json" 2>/dev/null \
    | head -1 | sed 's/"dev"[[:space:]]*:[[:space:]]*"//' | sed 's/"$//' || echo "unknown")
  START_CMD=$(grep -o '"start"[[:space:]]*:[[:space:]]*"[^"]*"' "${ROOT}/package.json" 2>/dev/null \
    | head -1 | sed 's/"start"[[:space:]]*:[[:space:]]*"//' | sed 's/"$//' || echo "unknown")
fi

if [ "${PW_CONFIG}" != "none" ] && [ -f "${ROOT}/${PW_CONFIG}" ]; then
  WEB_SERVER_PORT=$(grep -o 'port[[:space:]]*:[[:space:]]*[0-9]*' "${ROOT}/${PW_CONFIG}" 2>/dev/null \
    | head -1 | grep -o '[0-9]*' || echo "unknown")
  [ -n "${WEB_SERVER_PORT}" ] && DEV_PORT="${WEB_SERVER_PORT}"
fi

echo "dev_command	${DEV_CMD}"
echo "start_command	${START_CMD:-unknown}"
echo "detected_port	${DEV_PORT}"

# --- 7) CI detection ---
echo ""
echo "--- ci ---"
CI_PLATFORM="none"
CI_HAS_E2E="false"

if [ -d "${ROOT}/.github/workflows" ]; then
  CI_PLATFORM="github-actions"
  if grep -rl 'playwright' "${ROOT}/.github/workflows/" &>/dev/null; then
    CI_HAS_E2E="true"
  fi
elif [ -f "${ROOT}/.gitlab-ci.yml" ]; then
  CI_PLATFORM="gitlab-ci"
  grep -q 'playwright' "${ROOT}/.gitlab-ci.yml" 2>/dev/null && CI_HAS_E2E="true"
elif [ -f "${ROOT}/Jenkinsfile" ]; then
  CI_PLATFORM="jenkins"
fi

echo "ci_platform	${CI_PLATFORM}"
echo "ci_has_e2e	${CI_HAS_E2E}"

# --- 8) A11y and visual regression tools ---
echo ""
echo "--- tooling ---"
HAS_AXE="false"
HAS_VISUAL="false"

if [ -f "${ROOT}/package.json" ]; then
  grep -q '@axe-core/playwright' "${ROOT}/package.json" 2>/dev/null && HAS_AXE="true"
  grep -q 'percy' "${ROOT}/package.json" 2>/dev/null && HAS_VISUAL="percy"
  grep -q 'chromatic' "${ROOT}/package.json" 2>/dev/null && HAS_VISUAL="chromatic"
  grep -q 'argos' "${ROOT}/package.json" 2>/dev/null && HAS_VISUAL="argos"
fi

if [ "${HAS_VISUAL}" = "false" ] && [ "${PW_CONFIG}" != "none" ] && [ -f "${ROOT}/${PW_CONFIG}" ]; then
  grep -q 'toHaveScreenshot' "${ROOT}/${PW_CONFIG}" 2>/dev/null && HAS_VISUAL="playwright-built-in"
fi

echo "axe_core	${HAS_AXE}"
echo "visual_regression	${HAS_VISUAL}"

# --- 9) Summary verdict ---
echo ""
echo "--- verdict ---"
BLOCKERS=""
PROJECT_TYPE="unknown"

if [ "${GO_MOD}" = "true" ] && [ "${GO_WEB_CMD}" != "none" ]; then
  PROJECT_TYPE="go_web"
  [ "${GO_E2E_COUNT}" -eq 0 ] && BLOCKERS="${BLOCKERS}no_go_e2e_tests "
elif [ -f "${ROOT}/package.json" ]; then
  PROJECT_TYPE="js"
  [ "${PW_VERSION}" = "not_installed" ] && BLOCKERS="${BLOCKERS}playwright_not_installed "
  [ "${PW_CONFIG}" = "none" ] && BLOCKERS="${BLOCKERS}no_playwright_config "
  [ "${HAS_E2E_BASE_URL}" = "missing" ] && BLOCKERS="${BLOCKERS}no_base_url "
  [ "${HAS_E2E_USER}" = "missing" ] && BLOCKERS="${BLOCKERS}no_test_account "
else
  BLOCKERS="${BLOCKERS}unknown_project_type "
fi

echo "project_type	${PROJECT_TYPE}"
if [ -z "${BLOCKERS}" ]; then
  echo "readiness	ready"
  echo "blockers	none"
else
  echo "readiness	blocked"
  echo "blockers	${BLOCKERS}"
fi

echo ""
echo "=== End Report ==="
