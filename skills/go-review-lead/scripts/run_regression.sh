#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m pytest scripts/tests/ -v
echo "go-review-lead skill regression checks passed"