#!/usr/bin/env bash
# Behavioral smoke test for go-review-lead orchestration.
# Builds a throwaway git repo from the golden defect package, runs the skill
# once via `claude -p`, then grades the report deterministically.
# See evals/README.md for cost and prerequisites.
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)/golden-review"
mkdir -p "$WORK"

# Commit 1: clean baseline. Commit 2: planted defects.
cp "$SKILL_DIR/evals/golden/base/"* "$WORK/"
git -C "$WORK" init -q
git -C "$WORK" add -A
git -C "$WORK" -c user.email=smoke@eval -c user.name=smoke commit -qm "baseline"
cp "$SKILL_DIR/evals/golden/defect/"* "$WORK/"
git -C "$WORK" add -A
git -C "$WORK" -c user.email=smoke@eval -c user.name=smoke commit -qm "add search, warm-up, profile fetch"

REPORT="$WORK/report.txt"
echo "Golden repo: $WORK"
echo "Running claude -p (dispatches sub-agents; expect 5-15 min)..."
(cd "$WORK" && claude -p "Use the go-review-lead skill to review the changes in the latest commit of this repository at Standard depth.") > "$REPORT"
echo "Run complete. Grading report..."

fail=0

# Check 1 — mandatory report sections
for section in "Review Mode" "Findings" "Execution Status" "Summary"; do
  if ! grep -q "$section" "$REPORT"; then
    echo "FAIL: report missing section: $section"
    fail=1
  fi
done

# Check 2 — triage dispatched the right specialists for the planted defects
for agent in go-security-reviewer go-concurrency-reviewer go-error-reviewer; do
  if ! grep -q "$agent" "$REPORT"; then
    echo "FAIL: $agent not dispatched (planted defect requires it)"
    fail=1
  fi
done

# Check 3 — each planted defect was found
grep -qiE 'sql injection|parameteri[sz]' "$REPORT" && grep -q 'repo\.go' "$REPORT" \
  || { echo "FAIL: planted SQL injection (repo.go) not reported"; fail=1; }
grep -qiE 'race|without.*(lock|synchroni)|unsynchronized' "$REPORT" && grep -q 'store\.go' "$REPORT" \
  || { echo "FAIL: planted data race (store.go Warm) not reported"; fail=1; }
grep -qiE 'resp\.Body|Body[^a-z]*(not )?[Cc]lose' "$REPORT" \
  || { echo "FAIL: planted unclosed resp.Body not reported"; fail=1; }

# Check 4 — consolidation: unified IDs and High severity present and ordered first
grep -q 'REV-001' "$REPORT" || { echo "FAIL: no unified REV-NNN IDs"; fail=1; }
grep -q '\[High\]' "$REPORT" || { echo "FAIL: no High finding (3 were planted)"; fail=1; }
first_high=$(grep -n '\[High\]' "$REPORT" | head -1 | cut -d: -f1)
first_low=$(grep -n '\[Medium\]\|\[Low\]' "$REPORT" | head -1 | cut -d: -f1)
if [ -n "${first_low:-}" ] && [ -n "${first_high:-}" ] && [ "$first_low" -lt "$first_high" ]; then
  echo "FAIL: Medium/Low finding appears before first High — severity ordering broken"
  fail=1
fi

if [ "$fail" -ne 0 ]; then
  echo "SMOKE TEST FAILED — inspect $REPORT"
  exit 1
fi
echo "SMOKE TEST PASSED — report at $REPORT"