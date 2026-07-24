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

**Logical checks above: ~70. Actual `def test_*` methods: 38.** (The category
counts are assertions grouped by topic, several of which live inside one test
method or a loop — they are NOT the runnable test count.)

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

**Logical checks above: ~38. Actual `def test_*` methods: 31.** As above, the
per-scenario counts are grouped assertions, not the runnable test count. The
golden JSON tests (G1-G8) only search for keywords across the skill corpus —
presence, not correctness.

## Behavioral Tests (`test_behavioral_integration.py`)

Unlike the two suites above (which check that rule *text* exists), this compiles a
real Go integration fixture and runs it under many env configs, asserting ACTUAL
behavior:

| Test | Proves |
|------|--------|
| `test_gate_unset_skips` | run gate off → `t.Skip` (opt-in) |
| `test_gate_on_missing_config_fails` / `test_gate_on_missing_userid_fails` | gate on + required var missing → `t.Fatalf`, not a silent skip (#2) |
| `test_prod_host_under_dev_env_fails` / `test_bare_prod_host_no_scheme_fails` | a prod **host** (even a scheme-less bare host) under `ENV=dev` is refused — ENV is not trusted alone, and `url.Parse` fails closed (#3/#1) |
| `test_host_not_on_allowlist_fails` | with `NONPROD_HOST_ALLOWLIST`, a host not on it is refused |
| `test_prod_allowed_with_override_passes` / `test_valid_nonprod_passes` | `INTEGRATION_ALLOW_PROD=1` permits a READ prod test; a fully-configured non-prod target runs |
| `test_no_tenant_allowlist_fails` / `test_tenant_off_allowlist_fails` / `test_missing_tenant_fails` | tenant is **fail-closed**: `TEST_TENANT_ALLOWLIST` required; off-list or missing tenant refused (#1) |
| `test_destructive_without_flag_skips` / `test_destructive_with_flag_passes` | destructive is an opt-in tier; passes only with the flag + host allowlist + test tenant (#2/#4) |
| `test_destructive_without_host_allowlist_fails` | destructive requires `NONPROD_HOST_ALLOWLIST` — fail closed on host, not a substring denylist (#2) |
| `test_destructive_without_tenant_fails` | destructive validates a designated test tenant too (#1) |
| `test_destructive_on_prod_forbidden_even_with_both_flags` | a destructive write against prod FAILS even with `ALLOW_PROD=1` + `ALLOW_DESTRUCTIVE=1` (#2) |
| `test_contract_asserts_status_and_body` | real HTTP status + body field via `httptest` |
| `test_bounded_retry_hits_endpoint_three_times` | bounded retry contacts the endpoint exactly 3× (#3) |
| `test_context_timeout_surfaces_deadline` | `context.DeadlineExceeded` on a slow endpoint (#3) |
| `test_count1_defeats_test_cache` | a plain re-run prints `(cached)`; `-count=1` forces execution (#1) |

The fixture's three safety helpers are kept token-identical to the SKILL.md
baseline; `test_skill_contract.py::...safety_helpers_logic_identical_doc_vs_fixture`
compares their **full normalized function bodies** (brace-depth extraction, not
"up to the first `}`"), so the doc and the tested code cannot silently drift —
stronger than a token-presence check.

Skips (never fails) on environment limits: no `go`, no writable temp dir, or a
sandbox that denies binding a local socket (the `httptest`-based tests). Drops
inherited `GOROOT` so a stale one can't poison the build.

**Actual behavioral test methods: 20** (15 run without socket binding; 5 need a
bindable local socket and skip under a sandbox that denies it).

## Combined Total

**102 runnable test methods** = 51 contract + 31 golden + 20 behavioral. A
call-site arity guard also checks that every doc call of a safety helper matches
its definition, so a signature change can't leave a stale (non-compiling) example.
(Counts are `def test_*` methods. An earlier revision's "108"/"81" were wrong —
either logical checks, not methods, or stale; this line is regenerated from the
actual suite each time it changes.)

## Known Gaps

1. No live LLM-in-the-loop skill-output eval (the doc-contract + golden suites are
   structural; the behavioral suite proves the *prescribed code* works, not that a
   model emits it). A grader + fixtures like the unit-test skill's would close this.
2. Golden scenarios cover common cases; edge cases (e.g., mixed HTTP+gRPC in one
   file) not yet covered.
3. gRPC behavioral coverage: the behavioral fixture is HTTP (`httptest`); gRPC
   gate/retry/timeout behavior is still only asserted as doc text.
