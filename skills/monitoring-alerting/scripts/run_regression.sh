#!/usr/bin/env bash
# Static regression checks for the monitoring-alerting skill.
#
# Scope, stated up front so "passed" is never read as more than it is: everything here
# except the promtool/amtool stages is a check on the skill's own *text and fixtures*.
# It proves the rules are written correctly, the arithmetic in them is right, and the
# assertions guarding them actually bite. It does not prove a real Prometheus accepts
# the rules, and it says nothing about what an agent does with them at runtime.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
TEST_DIR="${SCRIPT_DIR}/tests"
cd "${SKILL_DIR}"

FAIL=0

run() {
    local label="$1"; shift
    echo "--- ${label} ---"
    if "$@"; then
        echo "  OK"
    else
        echo "  FAIL: ${label}"
        FAIL=1
    fi
    echo ""
}

run "Semantic doc lint (burn-rate arithmetic, matcher syntax, runbook coverage)" \
    python3 scripts/lint_monitoring_docs.py

run "Doc lint graded against the defects it was written for" \
    python3 scripts/lint_monitoring_docs.py --self-test

run "TOC generator self-test" \
    python3 scripts/gen_toc.py --self-test

run "Reference TOCs up to date (headings vs. anchors)" \
    python3 scripts/gen_toc.py

run "Forward-eval grader calibrated against known-verdict answers" \
    python3 scripts/eval_forward.py --self-test

# pytest discovers every test_*.py, so newly added test files can never be silently
# skipped (explicit per-file lists repeatedly caused exactly that across this repo's
# skills).
echo "--- Test suite (contract + golden + yaml artifacts + lint mutations) ---"
if python3 -m pytest "${TEST_DIR}" -q; then
    echo "  OK"
else
    echo "  FAIL: pytest"
    FAIL=1
fi
echo ""

# ── External validators ────────────────────────────────────────────────────────
# These are the only stages that execute the artifacts rather than reading them.
# When they are absent the suite still passes -- so the count is printed explicitly.
# A silent skip here is how "106 passed, 1 skipped" got read as "the rules are
# validated", when the skipped test was the *only* mechanical validation in the run.
echo "--- External validators (promtool / amtool) ---"
EXTERNAL_TOTAL=2
EXTERNAL_RAN=0
for tool in promtool amtool; do
    if command -v "${tool}" >/dev/null 2>&1; then
        echo "  ${tool}: present ($(command -v "${tool}"))"
        EXTERNAL_RAN=$((EXTERNAL_RAN + 1))
        if [ "${tool}" = "promtool" ]; then
            # Temporal behaviour, not just syntax: does the alert fire when it should and
            # stay silent when it should not. Run explicitly so the output is visible even
            # though the pytest suite also covers it.
            if (cd tests/promtool && promtool test rules rules_test.yml >/dev/null); then
                # Count derived from the file, not written here: this line said "5 temporal
                # cases" after the file had grown to 8 -- the same prose-count drift COVERAGE.md
                # documents, in the script that reports on it.
                N_CASES=$(grep -c '^  - interval:' tests/promtool/rules_test.yml)
                echo "    promtool test rules: SUCCESS (${N_CASES} temporal cases)"
            else
                echo "    promtool test rules: FAILED"
                FAIL=1
            fi
        fi
    else
        echo "  ${tool}: NOT INSTALLED — its checks were skipped, not passed"
    fi
done
echo "  ${EXTERNAL_RAN}/${EXTERNAL_TOTAL} external validators ran"
if [ "${EXTERNAL_RAN}" -eq 0 ]; then
    echo "  NOTE: zero artifacts were executed. Everything green above is a text-level"
    echo "        result. To close this gap:"
    echo "          go install github.com/prometheus/prometheus/cmd/promtool@latest"
    echo "          go install github.com/prometheus/alertmanager/cmd/amtool@latest"
fi
echo ""

echo "=== Conclusion ==="
if [ "${FAIL}" -ne 0 ]; then
    echo "FAIL — some checks did not pass"
    exit 1
fi
if [ "${EXTERNAL_RAN}" -eq 0 ]; then
    echo "PASS (text layer only) — rules are internally correct and guarded;"
    echo "     promtool/amtool did not run, so no artifact was executed."
else
    echo "PASS — text layer plus ${EXTERNAL_RAN}/${EXTERNAL_TOTAL} external validators."
fi
exit 0
