#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
TESTS_DIR="${SKILL_DIR}/scripts/tests"

echo "============================================"
echo "  update-doc skill regression suite"
echo "============================================"

echo ""
echo "[1/5] Validate skill frontmatter"
# Validates SKILL.md exactly as shipped. An earlier version of this step ran
# skill-creator's quick_validate.py, whose allowlist is five fields while the
# documented Claude Code frontmatter reference has seventeen; it rejects
# `disable-model-invocation`. Working around that by stripping the field and
# validating a temp copy would have validated a file nobody ships. The bundled
# validator knows the real schema, so the real file is the one checked.
python3 "${SKILL_DIR}/scripts/validate_frontmatter.py" "${SKILL_DIR}"

echo ""
echo "[2/5] Smoke-test the discovery script"
DISCOVER="${SKILL_DIR}/scripts/discover_doc_scope.sh"
SMOKE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/update-doc-smoke.XXXXXX")"
# An empty directory is the shape that kills a `set -e` probe script. Assert a
# clean exit AND the terminating sentinel: exit status alone cannot tell a full
# report from one truncated halfway.
if out="$(bash "${DISCOVER}" --repo "${SMOKE_DIR}")" \
   && [[ "$(printf '%s\n' "${out}" | tail -1)" == "=== END ===" ]]; then
  echo "  empty-directory probe OK (exit 0 + END sentinel)"
else
  echo "  discovery script failed on an empty directory" >&2
  rm -rf "${SMOKE_DIR}"
  exit 1
fi
rm -rf "${SMOKE_DIR}"

echo ""
echo "[3/5] Enumerate discovered test files"
# Discovered, never hardcoded: a test file added without touching this runner
# must still run. `mapfile` is bash 4+, and macOS ships bash 3.2, so read the
# list with a portable while-loop instead.
TEST_FILES=()
while IFS= read -r f; do
  [[ -n "$f" ]] && TEST_FILES+=("$f")
done < <(find "${TESTS_DIR}" -maxdepth 1 -name 'test_*.py' | sort)

# Safe under `set -u` on bash 3.2 because TEST_FILES is explicitly declared
# above; only an *undeclared* array trips the unbound-variable check.
TEST_COUNT=${#TEST_FILES[@]}
if [[ "${TEST_COUNT}" -eq 0 ]]; then
  echo "  no test files found under ${TESTS_DIR}" >&2
  exit 1
fi
for f in ${TEST_FILES[@]+"${TEST_FILES[@]}"}; do echo "  $(basename "$f")"; done

echo ""
echo "[4/5] Run regression tests"
if python3 -c "import pytest" >/dev/null 2>&1; then
  python3 -m pytest "${TESTS_DIR}" -v
else
  echo "  pytest not installed; falling back to unittest discovery"
  python3 -m unittest discover -s "${TESTS_DIR}" -p 'test_*.py' -v
fi

echo ""
echo "[5/5] Forward-eval grader discrimination"
echo "  (covered by test_forward_eval.py above: the grader must PASS a grounded"
echo "   exemplar and FAIL each defective one on the specific check it targets)"

echo ""
echo "============================================"
echo "  All regression checks passed"
echo "============================================"
echo ""
echo "  Verified: the skill's tool grants match the commands it instructs, its"
echo "  evidence commands are not silently-empty regexes, output-mode routing is"
echo "  unambiguous, and discovery reports the correct scope, command source and"
echo "  project type across ${TEST_COUNT} test files and the golden corpus."
echo ""
echo "  NOT verified here: that a live model, given this skill, produces a grounded"
echo "  document. The grader that would decide that is proven to discriminate, but"
echo "  no model ran in this suite."
if [[ -z "${UPDATE_DOC_EVAL_CMD:-}" ]]; then
  echo ""
  echo "  Run it with:  bash scripts/run_live_eval.sh"
  echo "  It needs an AUTHENTICATED CLI in UPDATE_DOC_EVAL_CMD. Without one it exits 2"
  echo "  and grades nothing, so a setup failure can never be read as a skill result."
fi
