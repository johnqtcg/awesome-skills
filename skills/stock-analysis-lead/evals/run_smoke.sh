#!/usr/bin/env bash
# Behavioral smoke test for stock-analysis-lead orchestration.
# Runs the skill once against mock data via `claude -p`, then grades the
# artifacts deterministically. See evals/README.md for cost and prerequisites.
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRATCH="$(mktemp -d)/stock-analysis-MOCK"
mkdir -p "$SCRATCH"
cp "$SKILL_DIR/evals/mock/"* "$SCRATCH/"

# Substitute the scratch path into manifest and prompt (portable in-place edit)
python3 - "$SCRATCH" <<'EOF'
import pathlib, sys
scratch = sys.argv[1]
for name in ("data-manifest.json",):
    p = pathlib.Path(scratch) / name
    p.write_text(p.read_text().replace("__SCRATCH__", scratch))
EOF
PROMPT="$(sed "s|__SCRATCH__|$SCRATCH|g" "$SKILL_DIR/evals/smoke-prompt.txt")"

REPORT="$SCRATCH/report.md"
echo "Scratch dir: $SCRATCH"
echo "Running claude -p (this dispatches up to 6 sub-agents; expect 10-20 min)..."
claude -p "$PROMPT" > "$REPORT"
echo "Run complete. Grading artifacts..."

fail=0

# Check 1 — mandatory report sections
for section in "Verdict" "Good-Company Score" "Bull / Base / Bear" \
               "Risks I Accept" "Invalidation Conditions" "Data Coverage" \
               "Cognitive-Bias"; do
  if ! grep -q "$section" "$REPORT"; then
    echo "FAIL: report missing section: $section"
    fail=1
  fi
done

# Check 2 — findings from >= 3 distinct workers (proves dispatch + consolidation)
prefix_count=$(grep -oE '\b(BUS|EQ|BS|MGT|IND|P)-[0-9]+' "$REPORT" | cut -d- -f1 | sort -u | wc -l | tr -d ' ')
if [ "$prefix_count" -lt 3 ]; then
  echo "FAIL: only $prefix_count distinct worker prefixes in report (need >= 3)"
  fail=1
else
  echo "OK: $prefix_count distinct worker prefixes found"
fi

# Check 3 — exactly one schema-valid verdict log entry
if [ ! -f "$SCRATCH/verdicts.jsonl" ]; then
  echo "FAIL: verdict log not written to $SCRATCH/verdicts.jsonl"
  fail=1
else
  entries=$(grep -c . "$SCRATCH/verdicts.jsonl" || true)
  if [ "$entries" -ne 1 ]; then
    echo "FAIL: expected exactly 1 verdict log entry, found $entries"
    fail=1
  fi
  python3 "$SKILL_DIR/scripts/validate_verdict_log.py" "$SCRATCH/verdicts.jsonl" || fail=1
fi

if [ "$fail" -ne 0 ]; then
  echo "SMOKE TEST FAILED — inspect $SCRATCH"
  exit 1
fi
echo "SMOKE TEST PASSED — artifacts in $SCRATCH"