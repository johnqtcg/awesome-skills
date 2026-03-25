#!/usr/bin/env bash
# Run regression tests for the git-commit skill.
# Usage: cd skills/git-commit && bash scripts/run_regression.sh

set -euo pipefail

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== git-commit skill regression ==="
echo "Skill directory: $SKILL_DIR"
echo ""

# Run contract tests
python3 -m pytest "$SKILL_DIR/scripts/tests/" -v --tb=short

echo ""
echo "=== All checks passed ==="