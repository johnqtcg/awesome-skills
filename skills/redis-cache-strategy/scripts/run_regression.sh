#!/usr/bin/env bash
# Run all regression checks for the redis-cache-strategy skill.
#
# Deliberately NOT `set -e`: a gate that reports "unavailable" (exit 3) must be
# reported as SKIPPED and must not be able to masquerade as a pass, and a single
# failing gate must not hide the results of the ones after it. The verdict is
# computed at the bottom from explicit counters.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
TEST_DIR="${SCRIPT_DIR}/tests"

failed=0
skipped=0
declare -a SKIPPED_GATES=()

# run_gate <name> <cmd...>
#   exit 0 -> pass · exit 3 -> gate unusable, SKIP (not a pass) · else FAIL
run_gate() {
    local name="$1"; shift
    echo ""
    echo "=== ${name} ==="
    "$@"
    local rc=$?
    case "${rc}" in
        0) echo "--- ${name}: PASS" ;;
        3) echo "--- ${name}: SKIPPED (gate unusable, rc=3)"
           skipped=$((skipped + 1)); SKIPPED_GATES+=("${name}") ;;
        *) echo "--- ${name}: FAIL (rc=${rc})"
           failed=$((failed + 1)) ;;
    esac
    return 0
}

cd "${SKILL_DIR}" || exit 1

# The linter's own selftest runs FIRST: a dead rule reports "clean", so a green
# lint run means nothing until every rule is proven to still fire.
run_gate "1/7 Linter selftest (every rule fires on its own violating input)" \
    python3 scripts/lint_cache_docs.py --selftest

run_gate "2/7 Semantic doc lint (SKILL.md + references)" \
    python3 scripts/lint_cache_docs.py

run_gate "3/7 Go snippet compile gate" \
    python3 scripts/check_go_snippets.py

run_gate "4/7 Contract tests (SKILL.md structure + reference files)" \
    python3 -m pytest "${TEST_DIR}/test_skill_contract.py" -q

run_gate "5/7 Golden scenarios (fixtures drive the real checker)" \
    python3 -m pytest "${TEST_DIR}/test_golden_scenarios.py" -q

# Last: slowest gate, and it is the one that proves the gates above are not
# decorative. Each mutation reintroduces a defect that actually shipped.
run_gate "6/7 Mutation sweep (prove each gate catches its defect)" \
    python3 scripts/mutation_sweep.py

run_gate "7/7 Coverage doc is generated, not hand-maintained" \
    python3 scripts/gen_coverage.py --check

echo ""
echo "========================================"
if [ "${skipped}" -gt 0 ]; then
    echo "SKIPPED gates (${skipped}): ${SKIPPED_GATES[*]}"
fi
if [ "${failed}" -gt 0 ]; then
    echo "redis-cache-strategy regression: FAILED (${failed} gate(s))"
    exit 1
fi
if [ "${skipped}" -gt 0 ]; then
    echo "redis-cache-strategy regression: INCOMPLETE — ${skipped} gate(s) could not run"
    exit 3
fi
echo "redis-cache-strategy regression: passed (7/7 gates)"
