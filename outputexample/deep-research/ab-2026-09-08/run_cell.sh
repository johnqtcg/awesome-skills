#!/usr/bin/env bash
# Run one A/B cell: one fixture x one arm x one repetition.
#
# Both arms receive an identical task prompt, identical tools, identical model,
# identical working directory and identical turn budget. The ONLY difference is
# whether SKILL.md is appended to the system prompt. Every cell stamps what it
# actually received so a treatment cell that silently lost its treatment cannot
# be scored as a control win.
set -uo pipefail

FIXTURE_ID="$1"
ARM="$2"          # skill | control
REP="$3"
QUESTION="$4"

WORK="${WORK:-/tmp/claude-503/dr_ab}"
SKILL_DIR="${SKILL_DIR:-/Users/john/awesome-skills/skills/deep-research}"
MODEL="${MODEL:-sonnet}"
MAX_TURNS="${MAX_TURNS:-30}"

CELLS_DIR="${CELLS_DIR:-$WORK/cells}"
CELL="$CELLS_DIR/${FIXTURE_ID}__${ARM}__r${REP}"
mkdir -p "$CELL"

# Neutral cwd: keeps the repository's own CLAUDE.md out of both arms.
RUNDIR="$CELL/cwd"
mkdir -p "$RUNDIR"

read -r -d '' TASK <<EOF || true
${QUESTION}

Research this question using the web, then answer it.

End your response with exactly these two blocks, in this order, and write
nothing after them:

VERDICT: YES
or
VERDICT: NO

SOURCES:
- <url> ||| <one sentence copied verbatim from that page that supports your verdict>

Use one SOURCES line per source, at least one line. The text after ||| must be
copied character-for-character from the page at that url, not paraphrased.
EOF

SYS_FILE="$CELL/system_prompt.txt"
if [ "$ARM" = "skill" ]; then
  {
    printf 'You have the following skill available. Follow it for this task.\n'
    printf 'Its bundled scripts and references are at: %s\n' "$SKILL_DIR"
    printf 'Paths inside the skill are relative to that directory.\n\n'
    cat "$SKILL_DIR/SKILL.md"
  } > "$SYS_FILE"
else
  : > "$SYS_FILE"
fi
SKILL_BYTES=$(wc -c < "$SYS_FILE" | tr -d ' ')

START=$(date +%s)
CLAUDE_ARGS=(
  -p "$TASK"
  --model "$MODEL"
  --max-turns "$MAX_TURNS"
  --output-format stream-json
  --verbose
  --permission-mode bypassPermissions
  --strict-mcp-config
  --setting-sources ""
  --add-dir "$SKILL_DIR"
)
if [ "$ARM" = "skill" ]; then
  CLAUDE_ARGS+=(--append-system-prompt "$(cat "$SYS_FILE")")
fi

( cd "$RUNDIR" && claude "${CLAUDE_ARGS[@]}" ) > "$CELL/stream.jsonl" 2> "$CELL/stderr.txt"
RC=$?
END=$(date +%s)

python3 - "$CELL" "$FIXTURE_ID" "$ARM" "$REP" "$RC" "$((END-START))" "$SKILL_BYTES" <<'PY'
import json, sys, pathlib
cell, fid, arm, rep, rc, dur, skill_bytes = sys.argv[1:8]
cell = pathlib.Path(cell)
text, usage, err = "", {}, ""
tools = []
turns = 0
for line in (cell / "stream.jsonl").read_text(encoding="utf-8", errors="replace").splitlines():
    line = line.strip()
    if not line:
        continue
    try:
        event = json.loads(line)
    except Exception:
        continue
    kind = event.get("type")
    if kind == "assistant":
        turns += 1
        for block in event.get("message", {}).get("content", []):
            if block.get("type") == "tool_use":
                tools.append({
                    "name": block.get("name"),
                    "input": json.dumps(block.get("input", {}))[:400],
                })
    elif kind == "result":
        text = event.get("result") or ""
        usage = event.get("usage") or {}
        if event.get("is_error"):
            err = str(event.get("result", ""))[:400]
if not text:
    err = err or "no result event in stream"
(cell / "answer.txt").write_text(text, encoding="utf-8")
(cell / "meta.json").write_text(json.dumps({
    "fixture": fid, "arm": arm, "rep": int(rep),
    "returncode": int(rc), "duration_s": int(dur),
    "system_prompt_bytes": int(skill_bytes),
    "answer_chars": len(text),
    "assistant_turns": turns,
    "tool_calls": tools,
    "usage": usage,
    "error": err or (cell / "stderr.txt").read_text(encoding="utf-8", errors="replace")[:400],
}, indent=2), encoding="utf-8")
print(f"{fid} {arm} r{rep} rc={rc} {dur}s chars={len(text)} tools={len(tools)} sys_bytes={skill_bytes}")
PY
