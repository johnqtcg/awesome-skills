#!/usr/bin/env bash
# Drive the full fixture x arm x rep matrix with bounded parallelism.
# Cells that already have a meta.json are skipped, so the run is resumable.
set -uo pipefail

WORK="${WORK:-/tmp/claude-503/dr_ab}"
REPS="${REPS:-2}"
PAR="${PAR:-4}"
export WORK
export CELLS_DIR="${CELLS_DIR:-$WORK/cells}"

cd "$WORK"

mapfile -t JOBS < <(python3 - "$WORK/fixtures.json" "$REPS" <<'PY'
import json, sys
fixtures = json.load(open(sys.argv[1]))["fixtures"]
reps = int(sys.argv[2])
for f in fixtures:
    for arm in ("control", "skill"):
        for rep in range(reps):
            print(f"{f['id']}\t{arm}\t{rep}\t{f['question']}")
PY
)

echo "planned cells: ${#JOBS[@]}"

run_one() {
  local line="$1"
  IFS=$'\t' read -r fid arm rep question <<< "$line"
  local cell="${CELLS_DIR:-$WORK/cells}/${fid}__${arm}__r${rep}"
  if [ -f "$cell/meta.json" ]; then
    echo "skip ${fid} ${arm} r${rep} (already run)"
    return 0
  fi
  bash "$WORK/run_cell.sh" "$fid" "$arm" "$rep" "$question"
}
export -f run_one

pids=()
for line in "${JOBS[@]}"; do
  run_one "$line" &
  pids+=($!)
  while [ "$(jobs -rp | wc -l)" -ge "$PAR" ]; do
    sleep 2
  done
done
for p in "${pids[@]}"; do
  wait "$p"
done

echo "=== matrix complete ==="
ls -d "$CELLS_DIR"/*/ | wc -l
