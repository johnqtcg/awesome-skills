# Behavioral Smoke Eval — Orchestration Mechanics

The contract tests (`scripts/tests/`) verify document structure and the agent→skill mapping, but cannot detect systemic orchestration failures: a worker silently never dispatched, Findings format drift breaking consolidation, the verdict log entry violating its schema. This harness verifies those behaviors by actually running the skill once against a mock data package, then grading the artifacts deterministically.

**What it checks (all machine-judged, no LLM grading):**

1. The final report contains every mandatory section (Verdict, Good-Company Score, Bull/Base/Bear, Risks I Accept, Invalidation Conditions, Data Coverage, Cognitive-Bias Self-Check).
2. Findings from ≥3 distinct workers appear, identified by their ID prefixes (`BUS-`/`EQ-`/`BS-`/`MGT-`/`IND-`/`P-`) — proves multiple workers were actually dispatched and consolidated.
3. Exactly one verdict-log entry was appended and it passes `scripts/validate_verdict_log.py` (schema, enums, target-price ordering).

**What it does NOT check:** analytical quality of the verdict. That requires LLM-as-judge with a rubric and is out of scope for a smoke test.

## Cost and cadence

One run dispatches up to 6 sub-agents (~10–20 min wall clock, meaningful token spend). This is **not** part of `run_regression.sh` — run it manually after any change to SKILL.md's workflow steps, the dispatch prompt, the Findings contract, or the agent definitions:

```bash
bash evals/run_smoke.sh
```

Prerequisites: `claude` CLI authenticated; the 6 worker agents installed in `~/.claude/agents/` and the 7 stock skills in `~/.claude/skills/` (see `outputexample/stock-analysis-lead/README.md`).

## How it stays offline and side-effect-free

- The prompt declares SMOKE TEST MODE: the fictional ticker `MOCK` skips EDGAR validation, Step 2 uses the pre-built mock manifest instead of network fetching, and workers are told not to use WebSearch/WebFetch.
- The verdict log is redirected into the scratch directory — the real `~/.claude/stock-analysis/verdicts.jsonl` is never touched.

A probabilistic generator graded by deterministic checks: the model's wording varies run to run, but "did 3+ workers report", "is the log entry schema-valid", and "are all report sections present" do not.