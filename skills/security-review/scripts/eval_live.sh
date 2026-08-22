#!/usr/bin/env bash
# Reference reviewer command for the opt-in live forward eval.
#
#   SECURITY_REVIEW_EVAL_CMD="$PWD/scripts/eval_live.sh" \
#     python3 -m unittest discover -s scripts/tests -p 'test_forward_eval.py' -v
#
# Reads a prompt on stdin, writes a review to stdout — the contract test_forward_eval.py
# expects. Exists because the isolation below is easy to get wrong, and getting it wrong
# silently measures something other than the skill:
#
#   1. Empty working directory.  Claude Code auto-discovers CLAUDE.md by walking up from the
#      cwd. Run from inside this repo and the nested reviewer inherits this repo's Go rules,
#      constitution, and coding meta-rules — so the eval would measure "skill + repo policy"
#      and score differently from a user invoking the skill in their own project.
#   2. Empty MCP config + --strict-mcp-config.  Otherwise the reviewer inherits every MCP
#      server configured for the parent session, which changes what it can reach.
#   3. No tools, via --disallowed-tools.  Two reasons, and the flag choice matters:
#      (a) the fixture code arrives inline, so a reviewer that can read the filesystem may find
#          the fixture's own JSON (which states the expected verdict) and recall the answer
#          instead of deriving it — measuring retrieval, not detection;
#      (b) with tools the reviewer runs an agentic loop, and `claude -p` prints only the FINAL
#          assistant message. That final message is then a wrap-up ("Saved to memory…",
#          "Evidence collection complete") rather than the report, so the grader scores the
#          wrong artifact and every mandatory section reads as missing.
#      `--allowed-tools ""` does NOT do this. Verified: with it, `echo TOOLS_WORK` still
#      executed — the flag takes a variadic list and an empty string is not "deny all". The
#      first version of this script used it and two of eight scenarios were graded on a
#      wrap-up message. Use the explicit deny list below.
#   4. Single response.  Denying tools is what actually bounds it to one turn.
#
# Auth: `claude` needs its credentials file. Under a sandboxed parent this surfaces as
# "Not logged in · Please run /login" — that is the sandbox denying ~/.claude/.credentials.json,
# not an expired session. In CI, set ANTHROPIC_API_KEY and add --bare instead.
set -euo pipefail

MODEL="${SECURITY_REVIEW_EVAL_MODEL:-claude-opus-5}"

# A fixed path rather than `mktemp -d`: the eval runs once per scenario and a stable cwd keeps
# the runs comparable. It must be OUTSIDE any repo so no CLAUDE.md is discoverable above it.
ISOLATED="${SECURITY_REVIEW_EVAL_CWD:-${TMPDIR:-/tmp}/security-review-eval-cwd}"
mkdir -p "${ISOLATED}"

# Fail loudly rather than silently measuring the wrong thing.
if find "${ISOLATED}" -maxdepth 1 -name 'CLAUDE.md' | grep -q .; then
  echo "eval_live.sh: ${ISOLATED} contains CLAUDE.md; the run would not be isolated" >&2
  exit 1
fi

cd "${ISOLATED}"
exec claude -p \
  --model "${MODEL}" \
  --strict-mcp-config \
  --mcp-config '{"mcpServers":{}}' \
  --disallowed-tools Bash,Read,Write,Edit,Grep,Glob,WebFetch,WebSearch,Task,NotebookEdit,AskUserQuestion,TodoWrite,Skill \
  --disable-slash-commands
