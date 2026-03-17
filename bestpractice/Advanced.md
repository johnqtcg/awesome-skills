
## Table of Contents

6. [Design Patterns for High-Quality Skills](#6-design-patterns-for-high-quality-skills)
   - [6.1 Mandatory Gate Architecture](#61-mandatory-gate-architecture)
   - [6.2 Teaching Through Anti-Examples](#62-teaching-through-anti-examples)
   - [6.3 Three-Tier Quality Scorecard](#63-three-tier-quality-scorecard)
   - [6.4 Golden Fixtures and Contract Tests](#64-golden-fixtures-and-contract-tests)
   - [6.5 Structured Output Contract](#65-structured-output-contract)
   - [6.6 Version and Platform Awareness](#66-version-and-platform-awareness)
   - [6.7 Honest Degradation](#67-honest-degradation)
   - [6.8 Degrees of Freedom](#68-degrees-of-freedom)
   - [6.9 Five Execution-Orchestration Patterns (from Anthropic's Official Guide)](#69-five-execution-orchestration-patterns-from-anthropics-official-guide)
7. [Common Pitfalls and Anti-Patterns](#7-common-pitfalls-and-anti-patterns)
   - [7.1 Description Determines Whether a Skill Lives or Dies](#71-description-determines-whether-a-skill-lives-or-dies)
   - [7.2 `SKILL.md` Exceeds 500 Lines](#72-skillmd-exceeds-500-lines)
   - [7.3 Reference Files Without Loading Conditions](#73-reference-files-without-loading-conditions)
   - [7.4 Positive Examples Only, No Anti-Examples](#74-positive-examples-only-no-anti-examples)
   - [7.5 Ignoring `allowed-tools` Security Constraints](#75-ignoring-allowed-tools-security-constraints)
   - [7.6 Good and Bad Uses of Dynamic Context Injection](#76-good-and-bad-uses-of-dynamic-context-injection)
   - [7.7 Creating Extra Files You Do Not Need](#77-creating-extra-files-you-do-not-need)
   - [7.8 Naming and Security Hard Limits](#78-naming-and-security-hard-limits)
   - [7.9 Performance and Loading Limits](#79-performance-and-loading-limits)
   - [7.10 Common Misunderstandings](#710-common-misunderstandings)
8. [Real-World Examples: From Simple to Complex](#8-real-world-examples-from-simple-to-complex)
   - [8.1 Simple Case: `git-commit`](#81-simple-case-git-commit)
   - [8.2 Complex Case: `go-code-reviewer`](#82-complex-case-go-code-reviewer)
9. [Design Philosophy: From Teachable to Executable](#9-design-philosophy-from-teachable-to-executable)
   - [9.1 Three Forms of Knowledge](#91-three-forms-of-knowledge)
   - [9.2 Case Study: How `git-commit` Aligns with the Git Standard](#92-case-study-how-git-commit-aligns-with-the-git-standard)
   - [9.3 The Same Philosophy Across Different Skills](#93-the-same-philosophy-across-different-skills)
   - [9.4 Three Core Capabilities](#94-three-core-capabilities)
   - [9.5 Three Design Principles](#95-three-design-principles)

## 6. Design Patterns for High-Quality Skills

From a systematic review of 10 production-grade, high-quality skills, we can extract **8 quality-assurance patterns** (6.1-6.8). In addition, Anthropic's official guide summarizes **5 execution-orchestration patterns** (6.9). The two are complementary: the first set governs **how well** the skill works, while the second governs **how execution is organized**.

| # | Pattern | One-Line Summary | Frequency |
|---|---------|------------------|-----------|
| 6.1 | Mandatory gates | If a prerequisite is not met, execution cannot continue | 9/10 |
| 6.2 | Anti-examples | Teaching AI what *not* to do is often more effective than teaching it what to do | 8/10 |
| 6.3 | Three-tier scorecard | Critical items can veto the whole result, so minor issues do not dilute major defects | 7/10 |
| 6.4 | Golden fixtures + contract tests | Zero-LLM structural checks protect a skill from accidental breakage | 9/10 |
| 6.5 | Structured output contract | Fixed output fields let CI consume AI results reliably | 10/10 |
| 6.6 | Version/platform awareness | Recommendations are filtered based on the project's actual runtime version | 6/10 |
| 6.7 | Honest degradation | When conditions are incomplete, return a clearly marked partial result instead of pretending it is complete | 5/10 |
| 6.8 | Degrees of freedom | Use exact scripts for fragile actions and natural language for flexible ones | Official guidance |

### 6.1 Mandatory Gate Architecture

Gates are the core quality mechanism in a skill: **if a prerequisite is not satisfied, execution must stop**. The number and shape of gates vary by workflow complexity, from lighter skills such as `git-commit` to heavier ones such as `create-pr`.

Common gate types:

| Gate Type | Purpose | Typical Example |
|-----------|---------|-----------------|
| Execution-integrity gate | Prevent the model from claiming it ran a tool when it did not | `go-code-reviewer`: "Never claim verification ran unless it actually did" |
| Context/evidence gate | Collect the necessary information before acting | `security-review`: scan the resource inventory before evaluating |
| Version-awareness gate | Adjust behavior based on the actual runtime version | `unit-test`: read the Go version from `go.mod`; do not recommend `t.Setenv` for Go < 1.17 |
| Degradation-output gate | Mark the result as partial when conditions are incomplete | `go-ci-workflow`: mark `# INLINE FALLBACK` when no Makefile exists |
| Applicability gate | Decide whether the task should be executed at all | `fuzzing-test`: stop immediately if the target is not suitable for fuzzing |

**Design point**: gates form a **serial dependency chain**. If any one fails, all later steps are blocked. This is different from a checklist, where you may skip an item.

### 6.2 Teaching Through Anti-Examples

This is the most counterintuitive pattern: **teaching AI what not to do is often more effective than teaching it what to do**. LLMs naturally tend to over-report because they prefer false positives over missed issues. Clear anti-examples suppress that tendency.

Take `go-code-reviewer` as an example. It defines 8 major false-positive classes:

```markdown
## Anti-Examples — DO NOT Report

1. Speculative nil dereference with no evidence of actual nil source
2. Over-cautious error handling complaints where stdlib guarantees non-nil
3. False concurrency alarm on a map used only in a single goroutine
4. Premature optimization suggestion without profiling evidence
5. Version-inappropriate recommendation (e.g., slog for Go < 1.21)
6. Context over-propagation complaint when function already has ctx
7. Unnecessary abstraction suggestion for teaching/example code
8. Structural false alarm on intentional test fixtures
```

The `unit-test` skill has the same idea, with 10 anti-examples such as "do not test standard-library behavior" and "do not write test cases that only assert `err == nil` just to raise coverage."

**Design point**: anti-examples must be specific. Do not write vague advice like "avoid false positives." Say **in what scenario, and what kind of output would be wrong**. A BAD/GOOD comparison works best.

### 6.3 Three-Tier Quality Scorecard

Split quality dimensions into three layers so critical issues are not averaged away and every dimension does not compete on equal weight:

| Tier | Pass Standard | Typical Example |
|------|---------------|-----------------|
| **Critical** | Any FAIL means the overall result FAILS | Gate existence, security scan, killer case |
| **Standard** | At least 4/5 pass | Test coverage, lint, formatting |
| **Hygiene** | At least 3/4 pass | Comment completeness, naming style |

This avoids two common problems: critical defects getting "averaged out" by minor wins, and decision paralysis caused by treating every dimension as equally important.

### 6.4 Golden Fixtures and Contract Tests

Golden fixtures are the "anchor tests" of a skill. They define expected rule coverage and behavior assertions for typical input scenarios. Contract tests validate the structural completeness of the skill text itself.

A typical test system includes:

- **Contract tests**: verify that `SKILL.md` includes its required gates, reference files, and output fields (pure text matching, no LLM dependency)
- **Golden-scenario tests**: given input scenario X, verify that the skill text contains all required rule keywords
- **Regression runner**: `scripts/run_regression.sh` to run all tests in one command
- **Coverage docs**: `COVERAGE.md` to record what is covered and what gaps remain

Test counts across 10 skills:

| Skill | Contract Tests | Golden-Scenario Tests | Total |
|-------|----------------|-----------------------|-------|
| `tdd-workflow` | 49 | 38 | 87 |
| `fuzzing-test` | 35 | 25 | 60 |
| `go-ci-workflow` | 44 | 17 | 61 |
| `security-review` | 30 | 25 | 55 |
| `go-makefile-writer` | 25 | 20 | 45 |
| `unit-test` | 24 | 17 | 41 |
| `go-code-reviewer` | 33 | 8 | 41 |

**Key property**: all of these tests have zero LLM dependency and run in under one second. This is not "using AI to test AI." It is plain structural and rule validation.

#### Concrete Example: 33 Contract Tests and 8 Golden Cases in `go-code-reviewer`

The table above shows that `go-code-reviewer` has 33 contract tests and 8 golden cases. What do they actually verify? Three examples show the pattern.

**Example 1: Contract test — protect two rules that point in opposite directions**

Go has a classic subtle distinction around closing HTTP bodies: in a server handler, `r.Body` is closed automatically by `net/http`, so manual `r.Body.Close()` is unnecessary; but on the client side, `resp.Body` must be closed manually or the connection leaks. That means `SKILL.md` must contain **two opposite rules**. Missing either one causes false positives or missed findings.

The contract test verifies this:

```python
def test_http_body_rule_is_server_client_aware(self):
    # Rule 1: no manual close needed on the server side
    self.assertIn("avoid requiring explicit `r.Body.Close()`", self.skill_text)
    # Rule 2: client code must close resp.Body
    self.assertIn("require `resp.Body.Close()`", self.skill_text)
    # Rule 3: detailed explanation in the reference file
    self.assertIn(
        "Do not treat missing `r.Body.Close()` in server handlers as an automatic defect.",
        self.api_ref_text,
    )
```

If someone accidentally deletes the server-side rule while editing `SKILL.md`, this test fails immediately. **The point of contract tests is to catch accidental rule loss or drift, not to test the model's runtime behavior.**

**Example 2: Golden case (true positive) — verify that the skill covers a real defect**

`001_race_shared_map.json` defines a real concurrency bug:

```json
{
  "id": "GOLDEN-001",
  "title": "Race condition on shared package-level map",
  "expected_finding": true,
  "severity": "High",
  "category": "concurrency",
  "code": "package cache\n\nvar store = map[string]string{}\n\nfunc Set(k, v string) { store[k] = v }\nfunc Get(k string) string { return store[k] }\n// Both called from HTTP handlers (concurrent goroutines)",
  "coverage_rules": [
    "Race conditions on shared state (maps, slices, vars)",
    "concurrent map write"
  ]
}
```

The test logic is: `expected_finding: true` means the skill **should** produce a finding for this scenario. The test walks through the `coverage_rules` array and checks whether `SKILL.md` plus the reference files contain those keywords:

```python
def test_001_race_shared_map(self):
    f = self._load("001_race_shared_map.json")
    self.assertTrue(f["expected_finding"])
    # Verify that the skill text covers
    # "Race conditions on shared state"
    # and "concurrent map write"
    self._assert_coverage(f)
```

If someone removes the section about concurrent map writes from a reference file, this test fails and tells you the skill can no longer reliably catch a shared-map race.

**Example 3: Golden case (false-positive suppression) — verify that the skill does not over-report**

`004_server_handler_body_fp.json` pairs with Example 1, but checks the other side of the problem: **given a correct code example, are the rules sufficient to stop the AI from raising a false positive?**

```json
{
  "id": "GOLDEN-004",
  "title": "Server handler without r.Body.Close — false positive",
  "expected_finding": false,
  "code": "func handler(w http.ResponseWriter, r *http.Request) {\n    data, err := io.ReadAll(r.Body)\n    // ... no r.Body.Close() call\n}",
  "anti_example_patterns": [
    "avoid requiring explicit `r.Body.Close()`"
  ]
}
```

`expected_finding: false` means this scenario **should not** produce a finding. The test checks whether the suppression rule listed in `anti_example_patterns` still exists in `SKILL.md`. If it was deleted, the test fails and warns you that the model will start flagging resource leaks on every server handler that omits `r.Body.Close()`.

Its counterpart is `003_missing_resp_body_close.json` (`expected_finding: true`) for client code, where the AI **should** report the missing close. Together they form a yin-yang pair that protects this subtle distinction.

#### Contract Tests vs Golden Cases

| | Contract Tests | Golden Cases |
|---|---|---|
| **Granularity** | Whether a single rule exists | Whether a full scenario is covered by the combined rules |
| **What is validated** | "Does `SKILL.md` mention `r.Body.Close()`?" | "Given a server handler without `r.Body.Close()`, are the rules enough to avoid a false positive?" |
| **Protection target** | Prevent accidental deletion or renaming of rules | Prevent coverage gaps in combined scenarios |
| **Analogy** | Unit test: every brick is present | Integration test: the bricks together cover a real case |

In short: **contract tests make sure every brick is still there; golden cases make sure those bricks still cover the real-world structure.** Together they keep a skill from quietly degrading over time.

### 6.5 Structured Output Contract

Each skill defines 7-10 required output fields so results are auditable, parseable, and easy to integrate downstream:

```markdown
## Output Contract (Mandatory Fields)

1. review_mode: Lite | Standard | Strict
2. files_reviewed: list of paths
3. findings: [{id, severity, category, location, description, evidence, recommendation}]
4. suppressed: [{reason, original_finding}]
5. baseline_comparison: {new, regressed, unchanged, resolved}
6. risk_summary: {overall_risk, sla_recommendations}
7. execution_status: {tools_run, tools_skipped, reason}
```

The output contract solves a common LLM problem: **without a contract, the output shape changes every time, so CI cannot consume it reliably.**

### 6.6 Version and Platform Awareness

Read the project's real version information and adjust recommendations dynamically:

```markdown
## Go Version Gate

Read go.mod → extract Go version → apply rules:
- < 1.17: do NOT recommend t.Setenv
- < 1.21: do NOT recommend slog
- < 1.22: WARN about range variable capture in goroutines
- < 1.24: do NOT recommend t.Parallel() + t.Setenv combination
```

This looks simple, but it solves one of the most common LLM mistakes: **recommending features the current project version does not support**. Traditional tools such as `golangci-lint` and SonarQube do not offer this kind of version-aware filtering.

### 6.7 Honest Degradation

When prerequisites are incomplete, the skill should not skip checks or guess. It should **produce an explicitly marked degraded result**:

```yaml
# Degradation strategy from go-ci-workflow:
# Level 1: Makefile target exists        → full parity
# Level 2: Makefile exists but target missing → partial parity + recommendations
# Level 3: no Makefile                   → inline scaffold + mark every line with "# INLINE FALLBACK"
```

The `create-pr` skill has a similar pattern: sufficient evidence → ready PR; insufficient evidence → draft PR with suspected items clearly marked.

**Design point**: degradation does not mean "do nothing if you cannot do it perfectly." It means **do what you can, while clearly telling the user which parts are incomplete**. That is far more valuable than pretending everything is fine.

### 6.8 Degrees of Freedom

**Source**: official `skill-creator` guidance

Choose different levels of instruction precision based on how fragile the operation is:

| Degree of Freedom | Expression Style | Best Use |
|-------------------|------------------|----------|
| **High** | Natural language ("use appropriate error handling") | Tasks with multiple valid implementations |
| **Medium** | Pseudocode or parameterized templates | A preferred pattern exists, but variation is acceptable |
| **Low** | Concrete scripts or full code | Fragile, error-prone actions that must be executed precisely |

The anti-pattern is clear: if everything is described with high freedom, output quality becomes unstable; if everything is defined as low freedom, the skill becomes too rigid to fit different projects.

### 6.9 Five Execution-Orchestration Patterns (from Anthropic's Official Guide)

The 8 patterns above focus on **quality assurance**: gates, anti-examples, scorecards, and so on. Anthropic's official guide also defines 5 patterns for **how a skill organizes execution**. The two sets complement each other:

| Pattern | Best Use | Core Technique |
|---------|----------|----------------|
| **Sequential workflow orchestration** | Multi-step flows that must happen in a fixed order | Explicit step order, inter-step dependency, phase-by-phase validation, rollback instructions |
| **Multi-MCP coordination** | Workflows that span multiple services, such as Figma → Drive → Linear → Slack | Clear phase boundaries, data handoff across MCPs, pre-validation, centralized error handling |
| **Iterative refinement** | Tasks where output quality improves over multiple passes, such as report generation | Draft → quality check → refinement loop → finalization, with explicit quality bar and stop criteria |
| **Context-aware tool selection** | One goal, but different tools are better depending on context | Decision trees, fallback options, transparent explanations for tool choice |
| **Domain-expertise injection** | The skill provides professional knowledge beyond raw tool access | Embedded domain rules, pre-action gates, audit trails, governance records |

**Real-world mapping**: `go-code-reviewer` combines sequential workflow orchestration (10 serial gates), context-aware tool selection (loading different references based on code traits), and domain-expertise injection (2,100+ lines of expert knowledge across 8 domains). When designing a skill, first pick the orchestration pattern, then layer on the quality-assurance patterns.

---

## 7. Common Pitfalls and Anti-Patterns

### 7.1 Description Determines Whether a Skill Lives or Dies

`description` is the **only basis** Claude uses to decide whether to auto-load a skill. It is not part of the body of `SKILL.md`; it lives in frontmatter and is always present in context.

Common mistakes:

```yaml
# BAD — too vague, Claude cannot tell when to load it
description: A helpful tool for Go developers.

# BAD — explains what it is, but not when to use it
description: Go code review skill with multiple modes.

# GOOD — includes trigger conditions and core capability
description: >
  Review Go code changes for real defects (security, concurrency, error handling,
  resource leaks). Triggers on PR review, code review, diff analysis.
  Supports Lite/Standard/Strict modes. Evidence-based, false-positive-aware.
```

**Rule**: everything about "when to use this skill" belongs in `description`, not the body. The body answers **how**. The description answers **when**.

### 7.2 `SKILL.md` Exceeds 500 Lines

The body of `SKILL.md` is **fully loaded into context** whenever the skill triggers. Once it grows past 500 lines, it not only wastes tokens but also weakens Claude's focus on the most important instructions.

**Split like this:**

- Decision framework, gates, output contract → keep in `SKILL.md`
- Detailed domain knowledge, templates, checklists → move to `references/`
- Deterministic logic (scan, validate, discover) → wrap in `scripts/`

### 7.3 Reference Files Without Loading Conditions

If you only list file names without explaining **when to load them**, Claude may load all of them (wasting tokens) or none of them (missing key knowledge):

```markdown
# BAD — no loading conditions
## References
- references/security-patterns.md
- references/concurrency-patterns.md
- references/performance-patterns.md

# GOOD — explicit triggers
## References (Load Selectively)
- references/security-patterns.md
  Load when diff contains: database/sql, tls.Config, crypto/, jwt, bcrypt
- references/concurrency-patterns.md
  Load when diff contains: go func, chan, sync.Mutex, errgroup, context.WithCancel
- references/performance-patterns.md
  Load when diff contains: append(, sync.Pool, atomic., reflect.
```

### 7.4 Positive Examples Only, No Anti-Examples

If you only teach the AI what to look for, but not what *not* to report, false positives will explode. **In review skills especially, the anti-example library may be more valuable than the positive-example guide.**

### 7.5 Ignoring `allowed-tools` Security Constraints

If a production skill runs without tool restrictions, the AI may perform unexpected operations:

```yaml
# BAD — unrestricted tools; the AI might push or delete files
- uses: anthropics/claude-code-action@v1
  with:
    prompt: "Review this PR"

# GOOD — allowlist plus denylist
- uses: anthropics/claude-code-action@v1
  with:
    prompt: "Review this PR following .claude/skills/go-code-reviewer/SKILL.md"
    allowed_tools: "Read,Grep,Glob,Bash(go test:*),Bash(golangci-lint:*)"
    disallowed_tools: "Bash(git add:*),Bash(git commit:*),Bash(git push:*)"
```

### 7.6 Good and Bad Uses of Dynamic Context Injection

Skills support the `` !`command` `` syntax, which runs a shell command *before the skill is loaded* and replaces the placeholder with its output:

```markdown
# Dynamic context injection inside SKILL.md
Current Go version: !`grep '^go ' go.mod | awk '{print $2}'`
Current branch: !`git branch --show-current`
```

This is **preprocessing**, not an instruction telling Claude to execute a command. It is useful for deterministic metadata such as project version or branch name.

**Bad use**: putting complex logic inside `` !`...` ``. Complex logic belongs in standalone scripts under `scripts/`.

### 7.7 Creating Extra Files You Do Not Need

A skill directory should contain only the files it actually needs. The following files should not exist:

- `README.md` (`SKILL.md` is already the documentation)
- `CHANGELOG.md` (use `git log`)
- `INSTALLATION_GUIDE.md` (skills do not need installation guides)
- `LICENSE` (the skill follows the parent project's license)

### 7.8 Naming and Security Hard Limits

Anthropic enforces the following hard constraints. Violations may cause uploads to fail or the skill to be silently ignored:

| Constraint | Requirement | Bad Example |
|------------|-------------|-------------|
| Folder naming | **Must use kebab-case** | `My_Cool_Skill` ❌, `mySkill` ❌, `my-skill` ✅ |
| `SKILL.md` naming | Case-sensitive and exact | `skill.md` ❌, `SKILL.MD` ❌, `SKILL.md` ✅ |
| Reserved words in skill names | Must not contain `claude` or `anthropic` | `claude-helper` ❌ |
| `description` content | XML angle brackets `< >` are forbidden | Frontmatter is injected into the system prompt, so angle brackets may be interpreted as instructions |
| `description` length | ≤ 1024 characters | — |

### 7.9 Performance and Loading Limits

| Metric | Recommended Value | Notes |
|--------|-------------------|-------|
| `SKILL.md` size | **< 5,000 words** (about 500 lines) | Beyond this threshold, both latency and output quality tend to degrade |
| Number of skills enabled at once | **20-50** | Beyond that, frontmatter alone consumes a large chunk of the context window |
| Reference files | Load on demand; do not inline everything | Put detailed content under `references/` and define loading conditions in `SKILL.md` |

**Advanced tip** (from the official guide): for critical validation logic, prefer executable scripts under `scripts/` over natural-language instructions. Code is deterministic; prose is not. Anthropic's Office-related skills (`docx`, `pptx`, `xlsx`) are good examples of this pattern.

### 7.10 Common Misunderstandings

| Misunderstanding | Reality |
|------------------|---------|
| "A skill is just a more advanced prompt" | A skill is a **testable, version-controlled, on-demand knowledge module**. A normal prompt cannot be regression-tested, loaded conditionally, or shared reliably across a team. The relationship is similar to "temporary script" vs "real tool." |
| "The more detailed the instructions, the better the skill" | Over-detail causes two problems: (1) once you exceed 500 lines, context cost becomes too high; (2) low-freedom instructions cannot adapt across projects. The right approach is to match instruction precision to the degree of freedom (see §6.8). |
| "Every common operation should become a skill" | A skill is worth creating only if it is reused, longer than 50 lines, and not needed in every session (see §3.1). Deterministic steps such as formatting are better as hooks, and short global rules belong in `CLAUDE.md`. |
| "Once a skill is written, it does not need maintenance" | Skills decay just like code. Tool upgrades, changing team standards, and model behavior changes can all make a skill stale. You need contract tests and real-world iteration to keep it healthy (see Chapter 9). |
| "Only developers can write skills" | `SKILL.md` is just Markdown. PMs can write process skills, QA can write testing-standard skills, and technical writers can write documentation-style skills. The key is understanding the structure: trigger conditions + operating steps + output requirements. |

---

## 8. Real-World Examples: From Simple to Complex

### 8.1 Simple Case: `git-commit`

The `git-commit` skill has only about 130 lines in `SKILL.md` and no `references/` directory, yet it still implements a complete safe-commit workflow:

**Workflow:**

```
Pre-check → Staging strategy → Secret scan → Quality gates → Generate commit message → Commit → Report
```

**Core design points:**

1. **Security gates**: scan for AWS keys, PEM files, GitHub tokens, and other secrets using regex; if any are found, block the commit
2. **Quality gates**: for Go projects, run `go vet` and `go test`; for non-Go projects, run the project's standard checks
3. **Hook awareness**: if a git hook rejects the commit, the skill adjusts the message to satisfy the hook instead of bypassing it
4. **Atomicity rule**: "one commit = one logical change"

**In practice: running `$git-commit` in a real project**

The following three screenshots come from an actual commit in the `issue2md` project and show how the gates work at each stage:

![Secret scan: both the filename regex and content regex checks return `(no output)`](images/commit-three.png)

**Security gate**: after staging and before commit, the skill scans the staged changes with two regex passes: file-name patterns such as `.env`, `.pem`, and `.key`, plus content patterns such as AWS keys, SSH private keys, and GitHub tokens. In the screenshot, both return `(no output)`, so the gate passes.

![Generate a Conventional Commit message and commit](images/commit-four.png)

**Commit step**: after the security gate passes, the skill looks at the style of the previous commit and generates `fix(github): classify raw 401 auth errors`. Notice that it confirms there are unrelated changes in `retry.go` and `coverage.out`, but **only stages the 3 files related to the target fix**. That is the atomicity rule in action.

![Final report: commit hash, committed files, quality-gate result, and unrelated changes left out of the commit](images/commit-five.png)

**Report**: the output includes a structured commit hash, file list, quality-gate result (`make ci-api-integration passed`), and a clear note about unrelated changes that were not committed. This same commit later triggers the all-green CI pipeline shown in §12.2.

Even a simple skill like this still relies on gates. That is a shared trait across all high-quality skills. Its deeper value, though, is that it turns the team's Git standard into executable enforcement, and Chapter 9 explains that idea in more detail.

### 8.2 Complex Case: `go-code-reviewer`

`go-code-reviewer` is a complex skill rated 9.5/10. It spans about 3,100 lines across `SKILL.md`, 8 reference files, 33 contract tests, and 8 golden cases. It shows the full architecture of a mature skill.

**Three execution modes:**

| Mode | Best Use | Finding Limit |
|------|----------|---------------|
| Lite | ≤ 3 files, low risk | 5 |
| Standard | Default | 10 |
| Strict | Security, concurrency, or API contract changes | 15 |

**7 mandatory gates:**

```
Execution Integrity → Baseline Comparison → False-Positive Suppression
→ Risk Acceptance/SLA → Go Version → Generated Code Exclusion → Reference Loading
```

Three of these are especially distinctive:

- **Go Version Gate**: reads the Go version from `go.mod` and blocks recommendations the project cannot use (for example, no `slog` recommendation for a Go 1.20 project). Neither `golangci-lint` nor SonarQube can do this.
- **Reference Loading Gate**: when code matches a trigger pattern, the corresponding domain reference file is **mandatory**. It is not "nice to have"; without loading it, review is not allowed to continue.
- **Anti-example library**: 8 major false-positive classes. It teaches Claude **what not to report**, which is harder, and often more valuable, than teaching what to look for.

**What anti-examples achieve in practice:**

![Suppressed Items in a real `go-code-reviewer` run: two false positives are automatically suppressed with domain-specific reasoning](images/review-two.png)

This screenshot comes from a real review of the same `fix(github)` commit. The skill suppresses two false positives automatically: (1) string matching on `"bad credentials"` inside `isAuthError`, because it is limited to the GitHub API domain and is not a real security issue; and (2) field reordering inside `statusError`, because the 4 fields are already 8-byte aligned, so memory layout does not change. Every suppressed item includes **specific domain reasoning and a residual-risk note**, rather than simply being ignored. That is the real-world effect of the anti-example pattern in §6.2.

**Progressive disclosure in practice:**

```
SKILL.md (457-line operating framework)
   └── Load references on demand based on trigger keywords in the code:
       ├── go-security-patterns.md (581 lines; triggers: database/sql, tls.Config, jwt...)
       ├── go-concurrency-patterns.md (224 lines; triggers: go func, chan, sync.Mutex...)
       ├── go-error-and-quality.md (249 lines; triggers: _ =, panic(, errors.Is...)
       ├── go-test-quality.md (174 lines; triggers: *_test.go files in diff)
       ├── go-api-http-checklist.md (222 lines; triggers: net/http, gin., grpc...)
       ├── go-performance-patterns.md (287 lines; triggers: append(, sync.Pool, atomic....)
       ├── go-modern-practices.md (296 lines; triggers: [T, slog., atomic.Int...)
       └── pr-review-quick-checklist.md (65 lines; triggers: any PR/diff review)
```

If a PR only touches HTTP handlers, the review loads only `go-api-http-checklist.md` and `pr-review-quick-checklist.md`, not all 2,100 lines of domain knowledge. That is progressive disclosure working as intended.

---

## 9. Design Philosophy: From Teachable to Executable

The earlier chapters focus on how to write a skill, what patterns matter, and how to iterate on it. But after writing and refining many skills in real projects, a deeper idea becomes clear: **a skill is not just a way to customize an AI coding assistant. It represents an engineering shift, from knowledge that can be taught to knowledge that can be executed.**

### 9.1 Three Forms of Knowledge

In any technical team, engineering practice exists in three forms:

```
Tacit knowledge         Explicit knowledge        Executable knowledge
(in people's heads)     (in documents)           (in a skill)
┌──────────┐          ┌──────────┐          ┌──────────┐
│ "Check   │ ───────→ │ Git      │ ───────→ │ git-     │
│ secrets  │ Document │ standard │ Skillify │ commit   │
│ before   │          │ Chapter 6│          │ SKILL.md │
│ commit"  │          │ details  │          │ 7-step   │
└──────────┘          └──────────┘          │ workflow │
  ✗ depends on memory   ✗ depends on reading └──────────┘
  ✗ cannot be verified  ✗ cannot be enforced   ✓ enforced by gates
  ✗ lost with people    ✓ preserved            ✓ preserved + reusable
```

Traditional practice usually stops at the second stage: write documents, do training, and pass knowledge through code review. The core problem is that **execution still depends entirely on human discipline and memory**. Even a great document is useless if nobody remembers to read it.

Skills close the gap from stage two to stage three by **automating explicit knowledge**.

### 9.2 Case Study: How `git-commit` Aligns with the Git Standard

The `git-commit` skill (§8.1) is the most direct proof of this philosophy. For example, our team's Git operations guide had already distilled a complete Git commit standard in Chapter 2, "Daily Operation Commands Explained in Detail," and Chapter 6, "Workflow and Commit Standards." The skill turns those commit-related rules into mandatory gates inside a 7-step workflow:

Reference: [`xrdy511623/go-notes`](https://github.com/xrdy511623/go-notes) / `productivetools/git`

| Git Standard Topic | Current Documentation Topic | Skill Alignment |
|--------------------|-----------------------------|-----------------|
| Atomic commit: one commit should do one thing | Commit granularity and patch staging | ✅ Hard rule + `git add -p` as the default strategy |
| Describe **why**, not just **what** | Commit message body guidance | ✅ Body must answer "why it changed" |
| Follow the team's commit standard | Commit message conventions | ✅ Full Conventional Commits rule set |
| Conventional Commits format | Subject-line format rules | ✅ `type(scope): subject` exactly aligned |
| Full type coverage | Type conventions and exceptions | ✅ Superset, with extra `build` and `revert` |
| Subject ≤ 50 characters | Subject length guidance | ✅ Aligned with GitHub truncation behavior |
| Body explains **why** | Responsibility split for the body | ✅ Clear split between what and why |
| Footer rules | Footer and issue-linking conventions | ✅ Supports `BREAKING CHANGE`, `Closes #`, and `Refs:` |
| `--amend` safety warning | History-rewrite and force-push risk | ✅ Includes force-push warnings when the commit was already pushed |

All 9 documented rules are covered, from atomicity to footer formatting, from subject length to `--amend` risk warnings. The important change is not that the skill repeats the document. It changes **how the knowledge is executed**: from "please consult the Git standard" to "if the rule is not satisfied, the commit is blocked."

### 9.3 The Same Philosophy Across Different Skills

The same pattern appears across all strong skills:

| Skill | Tacit Knowledge (originally in people's heads) | Explicit Knowledge (documented) | Executable Knowledge (skillified) |
|-------|-----------------------------------------------|---------------------------------|-----------------------------------|
| `go-code-reviewer` | Senior engineers' review instincts: security patterns, concurrency traps, performance anti-patterns | 8 domain references totaling 2,100+ lines | Trigger keywords auto-load the right references, then mandatory gates run in sequence |
| `unit-test` | "Tests should find bugs, not chase coverage" | Defect-First Workflow methodology docs | Before writing tests, the skill must produce a failure-hypothesis list, and every target needs a killer case |
| `go-makefile-writer` | Team build standards: standard targets and flags for lint/test/fmt | Project Makefile conventions | Generates a Makefile that matches team standards and can be used directly by CI |
| `security-review` | Security lessons learned from real production incidents (for example, DB connection leaks) | Security review checklist | Forces review of resource lifecycle management, including constructor-release pairing |

### 9.4 Three Core Capabilities

Turning experience from "teachable" into "executable" requires three capabilities:

1. **Identify tacit knowledge**: realize which team rules "everyone knows" are actually stored only in a few people's heads. For example, "check for accidentally committed secrets before commit" often feels obvious only after an incident.
2. **Express it structurally**: turn vague experience into precise rules, gates, and workflows. "Be careful in code review" is not executable. "When `database/sql` appears, load the security review reference and check connection-pool config plus transaction boundaries" is executable.
3. **Choose the right level of automation**: not all knowledge should be automated. High-determinism rules such as formatting, secret scanning, and resource-lifecycle checks fit skills well. Flexible judgment such as architecture choices or business-logic reasoning should stay with humans. Too much automation is as harmful as too little.

### 9.5 Three Design Principles

Anthropic's official guide highlights the following three principles as the foundation of skills. Together they support the philosophy above:

| Principle | Meaning | Practical Guidance |
|-----------|---------|--------------------|
| **Progressive disclosure** | Three loading layers: frontmatter always visible, `SKILL.md` loaded on use, `references/` discovered on demand | Do not put everything into `SKILL.md`; move detailed docs into `references/` (see §5) |
| **Composability** | Claude may load multiple skills at once, so your skill should coexist cleanly with others | Do not assume exclusive tool access; avoid output-field collisions with common skills; keep boundaries clear |
| **Portability** | The same skill should run on Claude.ai, Claude Code, and the API without changes | Do not rely on platform-specific paths or env vars; declare required runtime dependencies in `compatibility` |

"Progressive disclosure" was covered in detail in §5. "Composability" and "portability" are especially important here because they determine whether a skill can actually scale across team environments and multiple platforms. If a skill assumes it is the only active skill, or only works on one platform, its reuse value drops sharply.

This is not just about using a tool better. It is an **upgrade in engineering thinking**. In the AI era, the people and teams that can make this shift will keep a long-term advantage.

---
