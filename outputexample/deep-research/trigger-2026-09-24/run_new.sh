#!/usr/bin/env bash
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO=/Users/john/awesome-skills
INSTALLED="$HOME/.claude/skills/deep-research/SKILL.md"
EVALSET="$REPO/outputexample/deep-research/ab-2026-09-08/three-dimension/trigger_eval_set.json"
BACKUP="$HERE/installed_SKILL.md.orig"
cmp -s "$BACKUP" "$INSTALLED" || { echo "ABORT: installed copy differs from backup before start"; exit 1; }
restore() { cp -p "$BACKUP" "$INSTALLED" && echo "RESTORED installed SKILL.md"; }
trap restore EXIT
python3 - "$INSTALLED" "$REPO/skills/deep-research/SKILL.md" <<'PY'
import re, sys
installed, repo = sys.argv[1], sys.argv[2]
pat = re.compile(r"^description: \|\n(?:  .*\n)+", re.M)
new = pat.search(open(repo).read()).group(0)
text = open(installed).read()
open(installed, "w").write(pat.sub(lambda _: new, text, count=1))
PY
check() { grep -q "Source-verified research: fact-check a claim" "$INSTALLED" && echo "CHECK $1: new description present" || { echo "CHECK $1: FAILED — installed description changed, cell invalid"; exit 2; }; }
check "before cell 2"
echo "== cell 2: NEW description, default budget, all 20 queries"
python3 "$HERE/trigger_cells.py" "$EVALSET" "$HERE/new_default_all.json" all
check "after cell 2"
echo "== cell 3: NEW description, listing budget raised, should-trigger only"
python3 "$HERE/trigger_cells.py" "$EVALSET" "$HERE/new_bigbudget_pos.json" pos 200000
check "after cell 3"
echo "ALL CELLS DONE"
