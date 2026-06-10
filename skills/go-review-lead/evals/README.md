# Behavioral Smoke Eval — Golden Defect Review

The contract tests (`scripts/tests/`) verify document structure and the agent→skill mapping, but cannot detect systemic orchestration failures: triage skipping a required specialist, a planted defect class going unreported, consolidation losing severity ordering. This harness verifies those behaviors by running the skill once against a **golden defect package** — a small compiling Go module with three planted, known defects — and grading the report deterministically.

## The golden package

`golden/base/` is a clean baseline; `golden/defect/` overwrites it with three planted defects, each mapping to a specialist the triage MUST dispatch:

| Planted defect | File | Must dispatch | Must report |
|---|---|---|---|
| SQL built via `fmt.Sprintf` from raw input | `repo.go` `SearchUsers` | go-security-reviewer | SQL injection |
| Goroutines write map without holding the mutex | `store.go` `Warm` | go-concurrency-reviewer | data race |
| `resp.Body` never closed (and `rows` never closed) | `repo.go` `FetchProfile` | go-error-reviewer | resource leak |

Both versions compile (`go build ./...`) so the compile pre-check passes and the findings are genuinely semantic, not build errors. The harness commits base then defect into a throwaway git repo, so the skill's merge-base/HEAD~1 diff logic is exercised too.

**Machine-judged checks (no LLM grading):**

1. Report contains the mandatory sections (Review Mode, Findings, Execution Status, Summary).
2. Triage dispatched go-security-reviewer, go-concurrency-reviewer, go-error-reviewer (plus the two always-on agents).
3. All three planted defects appear in the findings with their file names.
4. Unified `REV-NNN` IDs present; no Medium/Low finding precedes the first High (severity ordering).

A probabilistic generator graded by deterministic checks: wording varies run to run, but "was the race in store.go reported" does not.

## Cost and cadence

One run dispatches 5+ sub-agents (~5-15 min, meaningful token spend). **Not** part of `run_regression.sh` — run manually after any change to triage rules, the dispatch prompt, the findings contract, or the agent definitions:

```bash
bash evals/run_smoke.sh
```

Prerequisites: `claude` CLI authenticated; the 8 worker agents installed in `~/.claude/agents/` and the 9 skills in `~/.claude/skills/` (see `outputexample/go-review-lead/README.md`); `go` toolchain on PATH.

## Extending

When a production incident reveals a defect class this system should have caught (see `.claude/rules/go-rules-CHANGELOG.md` for the incident-driven loop), add it to `golden/defect/` with a comment naming the planted defect, and add a corresponding grep check to `run_smoke.sh`. Incident → planted defect → eval scenario.