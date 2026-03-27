#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEST_DIR="${SCRIPT_DIR}/tests"

echo "=== local-transcript regression tests ==="
python3 -m pytest "${TEST_DIR}/test_local_transcript.py" -v --tb=short "$@"
