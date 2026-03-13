#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${SCRIPT_DIR}"

python3 -m unittest discover -s tests -p 'test_*.py' -v
"${SKILL_DIR}/scripts/find-polluter.sh" --help >/dev/null

echo "systematic-debugging regression: PASS"
