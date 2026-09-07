#!/usr/bin/env bash
# Run regression tests for the git-commit skill.
# Usage: cd skills/git-commit && bash scripts/run_regression.sh

set -euo pipefail

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== git-commit skill regression ==="
echo "Skill directory: $SKILL_DIR"
echo ""

# `-rs` prints the reason for every SKIPPED test. Skips here mark tools this
# host does not have (a real gitleaks, a second awk implementation) — they are
# gaps in the evidence, and an invisible skip is how a gap gets mistaken for
# coverage. Read them.
python3 -m pytest "$SKILL_DIR/scripts/tests/" -v --tb=short -rs

echo ""
echo "=== All checks passed ==="
echo "Skips above (if any) are UNVERIFIED environments, not passes."
echo "For cross-implementation coverage: bash scripts/run_portability_matrix.sh"