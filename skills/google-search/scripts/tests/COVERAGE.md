# Test Coverage — google-search Skill

## Summary

| Suite | Tests | Focus |
|-------|-------|-------|
| Contract (`test_skill_contract.py`) | 77 | Structure, gates, modes, evidence chain, sections, references |
| Golden Scenarios (`test_golden_scenarios.py`) | 34 | Keyword coverage across search scenarios |
| **Total** | **111** | |

## Contract Test Categories

| Category | Tests | What it validates |
|----------|-------|-------------------|
| Frontmatter | 4 | YAML frontmatter, name, description, allowed-tools |
| Mandatory Sections | 9 | All required H2 sections present |
| Mandatory Gates | 13 | 8 numbered gates, serial order, ASCII flow, STOP+ASK, blocking, evidence chain table + 6 conclusion types |
| Execution Modes | 5 | 3 modes defined, auto-selection table, budgets, user override, evidence chain in examples |
| Anti-Examples | 2 | Minimum count, BAD/GOOD pairs |
| Degradation | 1 | 3 degradation levels (Full/Partial/Blocked) |
| Output Contract | 8 | 8 mandatory output fields (including execution mode, degradation level, evidence chain status) |
| Worked Examples | 2 | Minimum count, gate structure reference |
| Reference Files | 18 | 6 references exist, non-empty, linked from SKILL.md |
| Programmer Patterns | 8 | 7 required sections, syntax table |
| Source Scorecard | 2 | 3-tier scorecard, checkbox items |
| AI Search/Termination | 2 | Degradation protocol, search budget |
| Line Limits | 2 | SKILL.md between 100–500 lines |

## Golden Scenario Categories

| Category | Tests | What it validates |
|----------|-------|-------------------|
| JSON Fixtures | 8 | Keywords for 8 golden scenarios |
| Error Debugging | 3 | Error message patterns, SO + GitHub patterns |
| Official Docs | 2 | go.dev, pkg.go.dev patterns |
| Chinese Production | 3 | zhihu, juejin, pitfall keywords |
| Performance Benchmarks | 3 | TechEmpower, date filtering, benchmark keyword |
| High Conflict | 3 | Scope lock, claim tiers, as-of-date |
| Tool Discovery | 2 | Online tool, alternatives patterns |
| PDF Reports | 2 | filetype:pdf, report keyword |
| Walled Garden | 3 | WeChat, Xiaohongshu, platform search |
| GitHub Code Search | 3 | language:, stars:>, filename: filters |
| Query Refinement | 2 | Refinement loop, noise reduction |

## Running Tests

```bash
bash scripts/run_regression.sh
```
