#!/usr/bin/env bash
# run_eval.sh — decision-branch probe. Does an agent following SKILL.md pick the
# right BRANCH when the situation is ambiguous, mixed, or the tooling misbehaves?
#
#   Usage: bash scripts/eval/run_eval.sh [reps]        (default 2)
#          EVAL_ARMS="skill base" bash scripts/eval/run_eval.sh
#
# WHAT THIS PROVES, AND WHAT IT DOES NOT. It grades the agent's stated decision
# token, in plan mode, so nothing is executed and no commit is made. It therefore
# tests branch SELECTION — the thing the regression suite cannot reach — and not
# execution fidelity, which WholeWorkflowTests covers. It is non-deterministic:
# results are reported per repetition, never averaged into a single score, and a
# run with any incomplete cell is reported INCOMPLETE rather than scored.
#
# The `base` arm runs the same scenario WITHOUT the skill. A scenario both arms
# pass is not evidence about the skill; the report separates them.
set -u

# Both overridable by env, because the alternative is what actually happened:
# copying this script elsewhere to point it at a different scenario directory
# moved $0, so SKILL_DIR resolved to the copy's parent, `$SKILL_DIR/SKILL.md`
# did not exist, and the SKILL ARM SILENTLY RAN WITH NO SKILL — a base arm
# wearing the skill arm's label. Four cells of recorded evidence were void.
SKILL_DIR="${EVAL_SKILL_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
SCEN_DIR="${EVAL_SCEN_DIR:-$SKILL_DIR/scripts/eval/scenarios}"

# Fail loudly rather than degrade. An eval that cannot find the artefact it is
# evaluating has no result to report, in either direction.
if [ ! -f "$SKILL_DIR/SKILL.md" ]; then
  echo "eval: no SKILL.md at $SKILL_DIR/SKILL.md" >&2
  echo "eval: refusing to run — the skill arm would be indistinguishable from the base arm." >&2
  echo "eval: set EVAL_SKILL_DIR to the skill directory (and EVAL_SCEN_DIR for scenarios)." >&2
  exit 2
fi
if [ ! -d "$SCEN_DIR" ] || [ -z "$(ls "$SCEN_DIR"/*.sh 2>/dev/null)" ]; then
  echo "eval: no scenarios in $SCEN_DIR" >&2
  exit 2
fi
REPS="${1:-2}"
ARMS="${EVAL_ARMS:-skill}"
WORK="${EVAL_WORK:-${TMPDIR:-/tmp}}/gc-eval-$$"
mkdir -p "$WORK" || exit 2
WORK=$(cd "$WORK" && pwd -P)
LOG="$WORK/transcripts"; mkdir -p "$LOG"

command -v claude >/dev/null 2>&1 || { echo "eval: the claude CLI is required"; exit 2; }

DECISIONS='ASK|SPLIT|STOP|COMMIT'
cells=0; done_cells=0; correct=0
declare_row() { printf '%-34s %-6s %-4s %-8s %-8s %s\n' "$1" "$2" "$3" "$4" "$5" "$6"; }

echo "=== git-commit decision-branch eval ==="
printf 'claude   : %s\n' "$(claude --version 2>&1 | head -1)"
printf 'arms     : %s | reps: %s\n' "$ARMS" "$REPS"
printf 'skill    : %s (%s lines)\n' "$SKILL_DIR/SKILL.md" "$(wc -l < "$SKILL_DIR/SKILL.md" | tr -d ' ')"
printf 'scenarios: %s\n' "$SCEN_DIR"
printf 'workdir  : %s\n\n' "$WORK"
declare_row SCENARIO ARM REP EXPECT GOT VERDICT

for scen in "$SCEN_DIR"/*.sh; do
  name=$(basename "$scen" .sh)
  for arm in $ARMS; do
    r=1
    while [ "$r" -le "$REPS" ]; do
      cells=$((cells+1))
      repo="$WORK/$name-$arm-$r"
      mkdir -p "$repo"; cd "$repo" || exit 2
      git init -q .; git config user.email eval@example.invalid; git config user.name eval
      git config commit.gpgsign false
      printf 'seed\n' > README.md; git add README.md; git commit -qm "initial import" >/dev/null 2>&1
      PROMPT=""; EXPECT=""; EXTRA_PATH=""; ANSWER_PROMPT=""; EXPECT_ANSWER=""
      # shellcheck disable=SC1090
      . "$scen"
      [ -n "$PROMPT" ] && [ -n "$EXPECT" ] || { echo "eval: $name is missing PROMPT/EXPECT"; exit 2; }
      [ -z "$ANSWER_PROMPT" ] || [ -n "$EXPECT_ANSWER" ] || {
        echo "eval: $name asks an ANSWER_PROMPT but sets no EXPECT_ANSWER"; exit 2; }
      # EXPECT=ANY without a graded answer would grade nothing at all.
      [ "$EXPECT" != "ANY" ] || [ -n "$EXPECT_ANSWER" ] || {
        echo "eval: $name sets EXPECT=ANY but grades no answer"; exit 2; }

      if [ "$arm" = skill ]; then
        instr="Follow the instructions in $SKILL_DIR/SKILL.md exactly. Read it first."
      else
        instr="You are committing changes in a git repository. Use your own judgement."
      fi
      # A scenario may add a second graded question. Branch choice alone cannot
      # test rule APPLICATION — which scope, which subject, bypass or adapt —
      # and those are where a rule a model would not invent shows up.
      extra=""
      if [ -n "$ANSWER_PROMPT" ]; then
        extra="
Then, on the very last line and nothing after it:
ANSWER: $ANSWER_PROMPT"
      fi
      ask="$instr

The user says: \"$PROMPT\"

You are in PLAN MODE: do not modify anything and do not create a commit.
Investigate with read-only commands, then decide what you would do next and
finish your reply with EXACTLY this line:
DECISION: <ASK|SPLIT|STOP|COMMIT>
where ASK = you need the user to confirm or clarify before staging,
SPLIT = the change must become more than one commit,
STOP = a gate or safety check blocks committing right now,
COMMIT = you would create a single commit as-is.$extra"

      out="$LOG/$name-$arm-$r.txt"
      # Stamp provenance INTO the transcript. After the void-skill-arm bug I had
      # to infer, from prose, whether a recorded cell had the skill loaded —
      # which is exactly the kind of judgement a result file should not require.
      {
        printf '#EVAL_CELL %s arm=%s rep=%s\n' "$name" "$arm" "$r"
        if [ "$arm" = skill ]; then
          printf '#EVAL_SKILL %s (%s lines, sha %s)\n' "$SKILL_DIR/SKILL.md" \
            "$(wc -l < "$SKILL_DIR/SKILL.md" | tr -d ' ')" \
            "$( (shasum "$SKILL_DIR/SKILL.md" 2>/dev/null || cksum "$SKILL_DIR/SKILL.md") | awk '{print $1}' | cut -c1-12)"
        else
          printf '#EVAL_SKILL none (control arm)\n'
        fi
      } > "$out"
      PATH="${EXTRA_PATH:+$EXTRA_PATH:}$PATH" \
        claude -p "$ask" --permission-mode plan --strict-mcp-config --mcp-config '{"mcpServers":{}}' \
        >> "$out" 2>&1
      got=$(grep -oE "DECISION: ($DECISIONS)" "$out" | tail -1 | sed 's/DECISION: //')
      ans=$(grep -E "^ANSWER: " "$out" | tail -1 | sed 's/^ANSWER: //')
      if [ -z "$got" ] || { [ -n "$ANSWER_PROMPT" ] && [ -z "$ans" ]; }; then
        # A missing answer is not a wrong answer. Scoring it either way would be
        # a fabricated result, so the whole run is INCOMPLETE.
        declare_row "$name" "$arm" "$r" "$EXPECT" "${got:--}" "INCOMPLETE (missing token)"
      else
        done_cells=$((done_cells+1))
        ok_dec=1; ok_ans=1
        # EXPECT=ANY means the decision is NOT the graded property for this
        # scenario — the ANSWER is. Saying so beats a three-way alternation that
        # accepts everything while looking like a constraint.
        if [ "$EXPECT" != "ANY" ]; then
          printf '%s' "$got" | grep -qE "^($EXPECT)$" || ok_dec=0
        fi
        # EXPECT_ANSWER may hold SEVERAL patterns, one per line, ALL required.
        # A rule with two properties (Conventional Commits format AND a length
        # cap) cannot be expressed as one ERE — grep has no lookahead — and
        # grading only the easy half is how scenario 10 passed a base answer
        # that was not Conventional Commits at all.
        if [ -n "$EXPECT_ANSWER" ]; then
          while IFS= read -r pat; do
            [ -n "$pat" ] || continue
            printf '%s' "$ans" | grep -qE "$pat" || ok_ans=0
          done <<PATTERNS
$EXPECT_ANSWER
PATTERNS
        fi
        shown="$got"
        [ -n "$ANSWER_PROMPT" ] && shown="$got/$(printf '%s' "$ans" | cut -c1-24)"
        if [ "$ok_dec" = 1 ] && [ "$ok_ans" = 1 ]; then
          correct=$((correct+1)); declare_row "$name" "$arm" "$r" "$EXPECT" "$shown" PASS
        else
          why="decision"; [ "$ok_dec" = 1 ] && why="answer"
          declare_row "$name" "$arm" "$r" "$EXPECT" "$shown" "FAIL ($why)"
        fi
      fi
      cd "$WORK" || exit 2
      r=$((r+1))
    done
  done
done

echo
printf 'cells %s | completed %s | correct %s\n' "$cells" "$done_cells" "$correct"
printf 'transcripts: %s\n' "$LOG"
if [ "$done_cells" -ne "$cells" ]; then
  echo "RESULT: INCOMPLETE — a cell produced no decision token; do not read this as a score"
  exit 1
fi
[ "$correct" -eq "$cells" ] && { echo "RESULT: all cells correct"; exit 0; }
echo "RESULT: $((cells - correct)) cell(s) chose the wrong branch"
exit 1
