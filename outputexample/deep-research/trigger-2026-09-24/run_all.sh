#!/usr/bin/env bash
# Runs the three trigger cells against the installed personal copy of deep-research.
# The installed SKILL.md is backed up first and restored on any exit, so the user's
# environment ends exactly as it started; only the description block is swapped.
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO=/Users/john/awesome-skills
INSTALLED="$HOME/.claude/skills/deep-research/SKILL.md"
EVALSET="$REPO/outputexample/deep-research/ab-2026-09-08/three-dimension/trigger_eval_set.json"
BACKUP="$HERE/installed_SKILL.md.orig"

cp -p "$INSTALLED" "$BACKUP" || exit 1
restore() { cp -p "$BACKUP" "$INSTALLED" && echo "RESTORED installed SKILL.md"; }
trap restore EXIT

swap_in_new_description() {
  python3 - "$INSTALLED" "$REPO/skills/deep-research/SKILL.md" <<'PY'
import re, sys
installed, repo = sys.argv[1], sys.argv[2]
pat = re.compile(r"^description: \|\n(?:  .*\n)+", re.M)
new = pat.search(open(repo).read()).group(0)
text = open(installed).read()
assert pat.search(text), "installed copy has no description block"
open(installed, "w").write(pat.sub(lambda _: new, text, count=1))
PY
}

echo "== cell 1: OLD description, default budget, should-trigger only"
python3 "$HERE/trigger_cells.py" "$EVALSET" "$HERE/old_default_pos.json" pos

swap_in_new_description || exit 1
grep -c "fact-check a claim" "$INSTALLED" | sed 's/^/new description lines present: /'

echo "== cell 2: NEW description, default budget, all 20 queries"
python3 "$HERE/trigger_cells.py" "$EVALSET" "$HERE/new_default_all.json" all

echo "== cell 3: NEW description, listing budget raised, should-trigger only"
python3 "$HERE/trigger_cells.py" "$EVALSET" "$HERE/new_bigbudget_pos.json" pos 200000

echo "ALL CELLS DONE"
