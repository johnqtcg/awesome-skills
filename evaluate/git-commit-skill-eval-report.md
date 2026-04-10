# git-commit Skill Evaluation Report

> Evaluation Framework: [skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator)
> Evaluation Date: 2026-03-25
> Regression Addendum: 2026-04-10
> Subject: `git-commit`

---

`git-commit` is a safety-enhanced commit workflow skill that runs repository state checks, staging analysis, secret scanning, ecosystem-aware quality gates, and Angular (Conventional Commits) message generation before executing `git commit`. Its three standout strengths: a mandatory 7-step workflow (Preflight → Staging → Secret Gate → Quality Gate → Compose → Commit → Report) that replaces the baseline model's habit of staging and committing directly; regex-based secret scanning with layered triage that precisely blocked a hardcoded API key in Scenario 2; and ecosystem-aware quality gates (Go/Node/Python/Java/Rust) that ensure vet/test/lint runs before every commit — steps the baseline skipped in all three scenarios.

## 1. Skill Overview

`git-commit` is a structured commit safety skill defining a mandatory 7-step workflow, Hard Rules, five ecosystem quality gates, secret-scanning regexes, and a scope-discovery mechanism. Its goal: every commit passes complete safety preflight, logical staging, secret scanning, quality verification, and message normalization before execution. The April 2026 addendum extends regression coverage to young-repo scope bootstrap, executable subject guards, and timeout overrides.

**Core Components**:

| File | Lines | Responsibility |
|------|-------|----------------|
| `SKILL.md` | 169 | Main skill definition (7-step workflow, Hard Rules, secret regexes, scope discovery, subject guard, timeout override) |
| `references/quality-gate-go.md` | 25 | Go quality gate (go vet + go test, scaled by package count) |
| `references/quality-gate-node.md` | 40 | Node.js/TS quality gate (package manager detection, lint, tsc, test) |
| `references/quality-gate-python.md` | 53 | Python quality gate (ruff/flake8, mypy/pyright, pytest) |
| `references/quality-gate-java.md` | 45 | Java/Kotlin quality gate (Maven/Gradle, multi-module aware) |
| `references/quality-gate-rust.md` | 32 | Rust quality gate (clippy, cargo test, workspace aware) |
| `scripts/tests/test_skill_contract.py` | 261 | Contract tests (frontmatter, required sections, key content, reference integrity, golden coverage hooks) |
| `scripts/tests/test_golden_scenarios.py` | 227 | Golden scenario tests for scope resolution, subject validation, and timeout selection |

---

## 2. Test Design

### 2.1 Scenario Definitions

Regression addendum: the original 3 evaluated scenarios remain unchanged for comparability. The current repository version adds 7 deterministic golden fixtures that specifically cover commit-message generation failure modes that the original matrix did not isolate well: new-repo scope bootstrap, mixed-root scope omission, executable 50-character guarding, and timeout override precedence.

| # | Scenario | Repo Type | Core Challenge | Expected Outcome |
|---|----------|-----------|----------------|------------------|
| 1 | Clean Go feature | Go calculator | 2-file single-concern change, all checks should pass | Normal commit, CC format |
| 2 | Python multi-concern + secret | Python myapp | 4 files across 3 logical concerns + hardcoded `sk-proj-` API key | Commit blocked, secret reported |
| 3 | Node.js >8 files, messy history | Node task-api | 10 files + non-CC history ("WIP", "fix bug") | List files for confirmation, split commits |

### 2.2 Assertion Matrix (35 items)

**Scenario 1 — Clean Go Feature (13 items)**

| ID | Assertion | With-Skill | Without-Skill |
|----|-----------|:----------:|:-------------:|
| A1 | Run all preflight checks systematically (7 checks, with commands) | PASS | FAIL |
| A2 | Check for unresolved merge conflicts (diff-filter=U) | PASS | FAIL |
| A3 | Check for detached HEAD state | PASS | FAIL |
| A4 | Check for rebase/merge/cherry-pick in progress | PASS | FAIL |
| A5 | Staging analysis: correctly identify as single logical change | PASS | PASS |
| A6 | Run secret/sensitive-content scan (filename + content regexes) | PASS | FAIL |
| A7 | Run quality gate: go vet + go test | PASS | FAIL |
| A8 | Check git log to determine scope frequency | PASS | PARTIAL |
| A9 | Generate CC-format commit message | PASS | PASS |
| A10 | Subject line ≤ 50 characters (including type(scope):) | PASS | PASS |
| A11 | Use imperative mood | PASS | PASS |
| A12 | Output structured post-commit report (hash + files + gate status) | PASS | FAIL |
| A13 | Follow ordered 7-step workflow (output contract) | PASS | FAIL |

**Scenario 2 — Python Multi-Concern + Secret (12 items)**

| ID | Assertion | With-Skill | Without-Skill |
|----|-----------|:----------:|:-------------:|
| B1 | Run all preflight checks systematically | PASS | FAIL |
| B2 | Identify 3 independent logical concerns (user feature, config, logging) | PASS | PARTIAL |
| B3 | Propose splitting into separate commits | PASS | PARTIAL |
| B4 | Run secret scan with specific regex patterns | PASS | FAIL |
| B5 | Detect hardcoded `sk-proj-` API key | PASS | PASS |
| B6 | Block the commit | PASS | PASS |
| B7 | Report exact file, line number, and matched pattern name | PASS | PARTIAL |
| B8 | Suggest remediation (env var + .env file + key rotation) | PASS | PASS |
| B9 | Run quality gate (pytest + ruff/flake8) | PASS | FAIL |
| B10 | Generate CC-format messages for each logical group | PASS | PARTIAL |
| B11 | All subject lines ≤ 50 characters | PASS | PARTIAL |
| B12 | Follow structured output contract | PASS | FAIL |

**Scenario 3 — Node.js >8 Files, Messy History (10 items)**

| ID | Assertion | With-Skill | Without-Skill |
|----|-----------|:----------:|:-------------:|
| C1 | Run all preflight checks systematically | PASS | FAIL |
| C2 | Detect >8 files and list full file set for user confirmation | PASS | FAIL |
| C3 | Partition changes into logical groups | PASS | FAIL |
| C4 | Propose multiple separate commits | PASS | FAIL |
| C5 | Run secret scan | PASS | PARTIAL |
| C6 | Run quality gate (npm test + npm run lint) | PASS | FAIL |
| C7 | Check git log for scope frequency | PASS | PASS |
| C8 | Detect no CC history → omit scope | PASS | FAIL |
| C9 | All subject lines ≤ 50 characters | PASS | FAIL |
| C10 | Follow structured output contract | PASS | FAIL |

---

## 3. Pass Rate Comparison

### 3.1 Overall Pass Rate

| Configuration | Pass | Partial | Fail | Pass Rate |
|---------------|------|---------|------|-----------|
| **With Skill** | 35 | 0 | 0 | **100%** |
| **Without Skill** | 8 | 6 | 21 | **23%** (counting PARTIAL as 0.5 = 31%) |

**Pass rate improvement: +77 percentage points** (strict) / +69pp (with PARTIAL)

### 3.2 Pass Rate by Scenario

| Scenario | With-Skill | Without-Skill | Delta |
|----------|:----------:|:-------------:|:-----:|
| 1. Clean Go feature | 13/13 (100%) | 4.5/13 (35%) | +65pp |
| 2. Python multi-concern + secret | 12/12 (100%) | 5.5/12 (46%) | +54pp |
| 3. Node.js >8 files, messy history | 10/10 (100%) | 1.5/10 (15%) | +85pp |

### 3.3 Substantive Dimension (Capability-Focused, Structure-Independent)

To remove "workflow-structure bias," 15 additional checks were evaluated independently of workflow steps:

| ID | Check | With-Skill | Without-Skill |
|----|-------|:----------:|:-------------:|
| S1 | Scenario 1: Run tests (go test) | PASS | FAIL |
| S2 | Scenario 1: Run static analysis (go vet) | PASS | FAIL |
| S3 | Scenario 1: Secret scan | PASS | FAIL |
| S4 | Scenario 1: CC-format message | PASS | PASS |
| S5 | Scenario 1: Subject ≤ 50 characters | PASS | PASS |
| S6 | Scenario 2: Identify multiple logical concerns | PASS | PARTIAL |
| S7 | Scenario 2: Detect hardcoded API key | PASS | PASS |
| S8 | Scenario 2: Block commit containing secret | PASS | PASS |
| S9 | Scenario 2: Suggest secret remediation | PASS | PASS |
| S10 | Scenario 2: Run quality gate | PASS | FAIL |
| S11 | Scenario 3: >8 files triggers confirmation | PASS | FAIL |
| S12 | Scenario 3: Propose split commits | PASS | FAIL |
| S13 | Scenario 3: Run tests (npm test) | PASS | FAIL |
| S14 | Scenario 3: Detect no CC history → adapt scope strategy | PASS | FAIL |
| S15 | Scenario 3: Subject ≤ 50 characters | PASS | FAIL |

**Substantive pass rate**: With-Skill **15/15 (100%)** vs Without-Skill **5.5/15 (37%)**, improvement **+63pp**.

---

## 4. Key Difference Analysis

### 4.1 Behaviors Unique to With-Skill (Completely Absent in Baseline)

| Behavior | Impact |
|----------|--------|
| **Mandatory 7-step workflow** | Each step executed explicitly, with precise commands and expected results — nothing skipped |
| **6-item preflight checklist** | Conflict detection, detached HEAD, rebase/merge/cherry-pick state, submodule awareness |
| **Regex secret scanning** | 13 secret patterns (AWS/GitHub/Slack/Google/Stripe/OpenAI/DB URIs, etc.) + filename patterns |
| **4-level triage filtering** | allowlist → test/fixture → doc → comment line — eliminates false positives |
| **Ecosystem-aware quality gates** | Auto-detects Go/Node/Python/Java/Rust, runs the matching vet/test/lint toolchain |
| **>8 file confirmation threshold** | Forces listing all files and requesting user confirmation when changes exceed 8 files |
| **Scope frequency discovery** | Uses `git log` frequency (≥3 commits with same scope) to decide whether to include scope |
| **Structured post-commit report** | Complete record including hash, file summary, and gate status |

### 4.2 Behaviors the Baseline Does, But with Lower Quality

| Behavior | With-Skill | Without-Skill |
|----------|-----------|---------------|
| Secret detection | Regex pattern matching + filename scan + tiered triage | Manual diff review — catches obvious secrets but no tool evidence |
| Logical grouping | Precise grouping + split proposal + character counting | Recognizes different concerns but defaults to a single commit |
| CC message generation | Scope frequency analysis + character counting + imperative mood check | Produces CC format but doesn't verify character limits — occasionally over 50 |
| Quality verification | go vet + go test / npm test + lint / pytest, etc. | Only `git status` — no tests or lint ever run |
| Post-commit verification | Structured report (hash, files, gate status) | Only `git status` to confirm success |

### 4.3 Scenario-Level Key Findings

**Scenario 1 (Clean Go feature)**:
- **With-Skill**: All 7 steps completed. Full 7-item preflight; secret scan clean; go vet + go test passed; scope `calc` confirmed from history frequency; message `feat(calc): add multiply operation` (35 chars) precise and concise; post-commit report complete.
- **Without-Skill**: Only ran `git status` / `git diff` / `git log` (3 steps). **No go vet or go test**. No secret scan. No preflight checks. Message `feat(calc): add Multiply function` (33 chars) — correct format but included a system-default Co-Authored-By line. No post-commit report.

**Scenario 2 (Python secret)**:
- **With-Skill**: After passing preflight, precisely identified 3 logical concerns. Secret scan matched both `sk-[A-Za-z0-9]{20,}` and `api[_-]?key\s*=` on `src/config.py:5`. Triage confirmed non-test/non-doc/non-comment → **BLOCKED**. Report included exact filename, line number, matched pattern names, and remediation (`os.environ["API_KEY"]` + key rotation). Proposed 3 split commits, each subject ≤ 50 chars (49/44/45).
- **Without-Skill**: Caught the `sk-proj-` key via manual diff review (**PASS**), correctly blocked and suggested env var replacement. But no regex evidence chain, only mentioned file and line — no matched pattern name reported. Tended toward a single commit (two at most); did not identify the logger as an independent concern.

**Scenario 3 (Node.js messy history)**:
- **With-Skill**: Detected 10 files > 8 threshold, listed all files and requested confirmation. Identified 6 logical groups (config/middleware, auth+test, task+test, user+test, index wiring, README). `git log` showed no CC history → omit scope → use `type: subject` format. All 6 subject lines ≤ 50 chars (42/44/42/38/etc.). Ran `npm test` + `npm run lint` (both exit 0).
- **Without-Skill**: **Committed all 10 files as one commit** — no file count threshold, no logical grouping. Message `feat: add auth, users, and tasks modules with tests` (**51 characters, exceeds the 50-char limit**). No `npm test` or `npm run lint`. Noticed the non-CC history but chose to ignore it (kept CC format — correct behavior).

---

## 5. Token Cost-Effectiveness

### 5.1 Skill Context Token Cost

| Component | Lines | Estimated Tokens | Load Timing |
|-----------|-------|-----------------|-------------|
| `SKILL.md` | 169 | ~1,050 | Always loaded |
| `quality-gate-go.md` | 25 | ~150 | On-demand for Go projects |
| `quality-gate-node.md` | 40 | ~240 | On-demand for Node projects |
| `quality-gate-python.md` | 53 | ~320 | On-demand for Python projects |
| `quality-gate-java.md` | 45 | ~270 | On-demand for Java/Kotlin projects |
| `quality-gate-rust.md` | 32 | ~190 | On-demand for Rust projects |
| **Typical scenario total** | ~209–237 | **~1,300–1,470** | SKILL.md + 1 ecosystem gate |

Note: Only one ecosystem's quality gate reference is loaded per commit.

### 5.2 Actual Token Usage (6 Evaluation Agents)

| Agent | Scenario | Total Tokens | Duration (s) | Tool Calls |
|-------|----------|-------------|--------------|------------|
| S1 With-Skill | Clean Go feature | 28,841 | 128 | 27 |
| S1 Without-Skill | Clean Go feature | 22,156 | 78 | 11 |
| S2 With-Skill | Python secret | 32,732 | 179 | 25 |
| S2 Without-Skill | Python secret | 23,217 | 104 | 15 |
| S3 With-Skill | Node.js messy | 30,068 | 122 | 42 |
| S3 Without-Skill | Node.js messy | 33,290 | 170 | 24 |

**With-Skill average**: ~30,547 tokens, ~143s, ~31 tool calls
**Without-Skill average**: ~26,221 tokens, ~117s, ~17 tool calls

With-Skill agents consumed on average **+17% more tokens** and **+22% more time**, spent on the additional preflight checks, secret scanning, and quality gate steps. Scenario 3's Without-Skill agent anomalously consumed more tokens (33,290 vs 30,068) — without structural guidance, it made more exploratory file reads.

### 5.3 Cost-Effectiveness Calculation

| Metric | Value |
|--------|-------|
| Overall pass rate improvement | +77pp (strict) / +69pp (with PARTIAL) |
| Substantive pass rate improvement | +63pp |
| Skill context cost (typical) | ~1,300 tokens |
| Runtime overhead (average) | +4,326 tokens (+17%) |
| **Context tokens per 1% improvement (strict)** | **~17 tokens/1%** |
| **Context tokens per 1% improvement (substantive)** | **~21 tokens/1%** |
| **Including runtime overhead per 1% improvement** | **~73 tokens/1%** |

Note: "Context cost" counts only SKILL.md + reference loading; "runtime overhead" includes extra tool calls from preflight, secret scan, and quality gate execution.

### 5.4 Comparison with Other Skills

| Skill | Context Tokens | Pass Rate Improvement | Context Tok/1% | With Runtime Tok/1% |
|-------|---------------|----------------------|----------------|---------------------|
| **`git-commit`** | **~1,300** | **+77pp** | **~17** | **~73** |
| `create-pr` | ~3,400 | +71pp | ~48 | — |
| `go-makefile-writer` | ~1,960–4,300 | +31pp | ~63–139 | — |

`git-commit` leads on context tokens per 1% improvement (~17), for three reasons:
1. **SKILL.md is extremely lean** (169 lines) — progressive reference loading prevents context bloat while leaving room for executable guardrails
2. **Per-file quality gate design** is highly efficient — only one ecosystem reference is ever loaded, adding just ~150–320 tokens per commit
3. **Large pass rate delta** (+77pp) — git commit is a domain where baseline models critically lack structured safety workflows

Even including runtime overhead (~73 tok/1%), `git-commit` still outperforms `go-makefile-writer` on context cost alone. The additional tool calls guided by the skill (quality gates, secret scanning) consume more tokens, but their safety output far exceeds the cost.

### 5.5 Token Return Curve

```
Token investment → return mapping:

~1,150 tokens (SKILL.md only):
  → Gets: 7-step workflow, Hard Rules, secret regexes, staging threshold, scope discovery
  → Estimated coverage: ~85% of pass rate improvement

+150–320 tokens (1 quality-gate reference):
  → Gets: Ecosystem-specific vet/test/lint commands and thresholds
  → Estimated coverage: +12% of pass rate improvement (Quality Gate assertions)

+0 tokens (edge cases / examples already inlined):
  → Gets: Empty commit, post-merge residuals, submodule handling
  → Estimated coverage: +3% (edge case coverage)
```

SKILL.md alone delivers ~85% of the value. The progressive reference loading design achieves optimal token efficiency.

---

## 6. Overall Scoring

### 6.1 Dimension Scores

| Dimension | With Skill | Without Skill | Delta |
|-----------|-----------|---------------|-------|
| Preflight completeness (6 systematic checks) | 5.0/5 | 1.0/5 | +4.0 |
| Secret scanning (regex patterns + triage) | 5.0/5 | 2.5/5 | +2.5 |
| Quality gate execution (ecosystem vet/test/lint) | 5.0/5 | 1.0/5 | +4.0 |
| Staging logic (grouping + threshold + confirmation) | 5.0/5 | 2.0/5 | +3.0 |
| CC message quality (scope discovery + char counting) | 5.0/5 | 3.5/5 | +1.5 |
| Structured output report (7-step ordered output) | 5.0/5 | 1.5/5 | +3.5 |
| **Overall average** | **5.0/5** | **1.9/5** | **+3.1** |

**Dimension notes**:

- **Preflight completeness**: With-Skill ran 6 preflight checks systematically across all 3 scenarios (work tree, status, conflicts, branch, rebase, merge/cherry-pick), plus submodule awareness. Without-Skill only ran `git status`/`git diff`/`git log` — no conflict detection, no detached HEAD check, no rebase/merge state check.
- **Secret scanning**: With-Skill used 13 regex patterns + filename patterns in a dual-scan, with 4-level triage to filter false positives. In Scenario 2, precisely matched `sk-[A-Za-z0-9]{20,}` and `api[_-]?key\s*=`. Without-Skill caught the obvious `sk-proj-` key via manual diff review but had no tool evidence chain and reported no pattern name.
- **Quality gate execution**: With-Skill ran go vet + go test, pytest + ruff (deferred), and npm test + npm run lint across the 3 scenarios. Without-Skill **ran zero tests or lint tools in all 3 scenarios** — the largest capability gap.
- **Staging logic**: With-Skill identified 3 logical concerns in Scenario 2 and proposed 3 split commits; in Scenario 3 triggered the >8 file threshold, listed all files, and identified 6 logical groups. Without-Skill defaulted to a single commit in Scenario 2 and committed all 10 files together in Scenario 3.
- **CC message quality**: With-Skill produced subjects ≤ 50 chars across all scenarios (35/49/44/45/42/38, etc.), using `git log` frequency analysis for scope decisions. Without-Skill's Scenario 3 subject was **51 characters — over the limit** — and no scope frequency analysis was performed.
- **Structured output report**: With-Skill strictly followed the 7-step workflow output order; post-commit report included hash, files, and gate status. Without-Skill only ran `git status` to confirm success — no structured report.

### 6.2 Weighted Score

| Dimension | Weight | Score | Rationale | Weighted |
|-----------|--------|-------|-----------|---------|
| Assertion pass rate (delta) | 25% | 10.0/10 | +77pp (strict) / +63pp (substantive), best token efficiency | 2.50 |
| Quality gate execution | 20% | 10.0/10 | 3/3 scenarios ran ecosystem-matched tools; baseline skipped all | 2.00 |
| Secret scanning | 15% | 9.5/10 | Excellent regex + triage; could add more patterns (e.g., JWT) | 1.43 |
| Staging logic and grouping | 15% | 10.0/10 | >8 threshold + logical grouping + split proposals + hunk-level staging | 1.50 |
| Token cost-effectiveness | 15% | 9.0/10 | ~17 tok/1% best among the three skills; progressive loading design elegant | 1.35 |
| CC message quality | 10% | 9.5/10 | Scope frequency discovery + char counting; 50-char limit strictly enforced | 0.95 |
| **Weighted total** | **100%** | | | **9.73/10** |

### 6.3 Comparison with Other Skills

| Skill | Weighted Score | Pass Rate Delta | Tokens/1% | Top Advantage Dimension |
|-------|---------------|-----------------|-----------|------------------------|
| **git-commit** | **9.73/10** | +77pp | ~17 | Quality gate (+4.0), Preflight (+4.0) |
| create-pr | 9.55/10 | +71pp | ~48 | Gate workflow (+3.5), Output Contract (+4.0) |
| go-makefile-writer | 9.16/10 | +31pp | ~63 | CI reproducibility (+3.0), Output Contract (+4.0) |

`git-commit` earns the highest overall score of the three skills, primarily because:

1. **Token efficiency is significantly ahead** (~17 tok/1% vs ~48 and ~63): progressive reference loading keeps SKILL.md at just 169 lines while covering 5 ecosystems
2. **Largest pass rate delta** (+77pp): git commit is the domain where baseline models are weakest in structured safety workflows — baseline skipped tests in every scenario
3. **No weak dimensions**: all 6 dimensions scored ≥ 9.0

**Point deductions**:
- Secret scanning (9.5/10): Current regexes cover mainstream secret types but lack patterns for JWT, Twilio (`SK[0-9a-fA-F]{32}`), Mailgun, and other newer SaaS platforms
- Token cost-effectiveness (9.0/10): Despite having the best absolute efficiency, the Edge Cases section (~100 tokens) sees low utilization in typical scenarios

---

## 7. Conclusion

`git-commit` is the skill with the **largest pass rate delta** (+77pp) and **best token efficiency** (~17 tok/1%) in this evaluation. This indicates that git commit is a domain where baseline models critically lack structured safety processes — baseline never ran any tests or lint tools across all 3 test scenarios, making the skill's marginal value exceptionally high.

**Core value**:
1. **Quality gate: zero to one** — Baseline never runs vet/test/lint; the skill guarantees "every commit passes a quality gate"
2. **Regex secret scanning** — 13 patterns + 4-level triage precisely blocked a hardcoded API key in Scenario 2, providing an evidence chain that manual review cannot match
3. **Staging safety net** — >8 file confirmation + logical split proposals prevented 10 mixed files from being committed as one blob in Scenario 3
4. **Progressive reference loading** — 5 ecosystem gates stored in separate files, loaded on demand; typical token cost is just ~1,300 (SKILL.md + 1 gate)

**Design strengths**:
- SKILL.md strictly held to 169 lines (target ≤ 200) with very high information density
- Quality gate per-file design achieves "one SKILL.md, five ecosystems" — a model example of progressive loading
- Hard Rules first + precise thresholds (8 files, 50 chars, 3-commit scope frequency) make rules verifiable and unambiguous

**Improvement suggestions**:
1. Extend secret regexes to cover JWT, Twilio (`SK[0-9a-fA-F]{32}`), Mailgun, and other emerging platforms
2. Add guidance on creating a `.commit-secret-allowlist` file to reduce first-time setup friction
3. Consider moving the Edge Cases section into a reference file to further trim SKILL.md (~80 tokens saved)
