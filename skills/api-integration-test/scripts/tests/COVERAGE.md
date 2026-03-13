# Test Coverage Matrix

## Contract Tests (`test_skill_contract.py`)

| Category | Tests | What it validates |
|----------|-------|-------------------|
| Frontmatter | 6 | YAML structure, name, description keywords, allowed-tools |
| Mandatory Sections | 12 | All required H2 headings present |
| Mandatory Gates | 11 | 7 named gates with `### N)` format, sequential 1-7 numbering, serial dependency stated, failure-blocks stated |
| Execution Modes | 7 | Smoke/Standard/Comprehensive defined, default mode, auto-selection table, trigger signals, user override |
| Gate Content | 8 | Production gate, build tag, run gate env, context timeout, execution integrity, scope redirect, version gate go.mod + versions |
| Degradation | 4 | Full/Scaffold/Blocked levels defined, Blocked stops execution |
| Anti-Examples | 2 | Section exists, minimum count ≥ 5 |
| Output Contract | 1 | References common-output-contract.md |
| Reference Files | 12 | All 4 files exist, non-empty, mentioned in SKILL.md |
| Reference Loading | 2 | Gate always loads, trigger patterns present |
| Safety Rules | 2 | No hardcode secrets, timeout bounded |
| Size | 1 | SKILL.md ≤ 500 lines |

**Total contract tests: 70**

## Golden Scenario Tests (`test_golden_scenarios.py`)

| # | Scenario | Tests | Key assertions |
|---|----------|-------|----------------|
| 1 | Simple HTTP GET | 4 | HTTP pattern, success+failure, timeout, build tag |
| 2 | gRPC Service | 2 | gRPC pattern, error code assertion |
| 3 | Retryable Endpoint | 5 | Bounded retry, backoff, ctx.Done, transient classification |
| 4 | Production Safety | 4 | Prod gate, env check, t.Skip, destructive gate |
| 5 | Missing Config | 4 | Scaffold/Blocked degradation, TODO markers, actionable skip |
| 6 | CI Integration | 4 | GitHub Actions, service containers, Docker Compose, Makefile |
| 7 | Concurrent Requests | 2 | Concurrency pattern, goroutine usage |
| 8 | Data Lifecycle | 2 | t.Cleanup, idempotency |
| 9 | Anti-Patterns | 3 | No mock transport, no unstable fields, no unbounded retry |
| G1-G8 | Golden JSON files | 8 | Keyword coverage across all skill+reference text |

**Total golden scenario tests: 38**

## Combined Total: 108 tests

## Known Gaps

1. No LLM-in-the-loop tests (by design — these are structural tests only).
2. No output format validation (would require actual test execution).
3. Golden scenarios cover common cases; edge cases (e.g., mixed HTTP+gRPC in one file) not yet covered.
