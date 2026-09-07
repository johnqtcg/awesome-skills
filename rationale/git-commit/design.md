---
title: git-commit skill design rationale
owner: awesome-skills maintainers
status: active
last_updated: 2026-04-10
applicable_versions: current repository version
---

# git-commit Skill Design Rationale

`git-commit` is a safety workflow that turns the act of committing into an engineering process. Its core idea is: **a commit is a quality gate that should pass preflight checks, staging review, secret scanning, quality verification, and result reporting before it goes through.** That is why it uses a seven-step serial workflow instead of a bare `git add` + `git commit`.

## 1. Definition

`git-commit` is a safety-enhanced commit skill. Before executing a commit, it validates repository state, identifies the staging scope, scans for secrets, runs an ecosystem-matched quality gate, generates an Angular / Conventional Commits message in English, and outputs a structured post-commit report.

## 2. Background and Problems

The skill is not solving "developers don't know how to write a commit message." It is solving "teams treat committing as a throwaway action."

Without guardrails, failures tend to cluster into five categories:

| Problem | Typical consequence |
|---------|---------------------|
| Committing while the repository is in a bad state | Conflicts, a rebase mid-state, or a detached HEAD end up in the commit |
| Staging scope out of control | Unrelated changes, temp files, and submodule pointer updates sneak into the commit |
| Secrets not caught | API keys, private keys, and database URIs land in version history |
| No quality checks before committing | Broken changes reach the main branch without tests, lint, or vet ever running |
| Message looks correct but the semantics are wrong | Invented scopes, overly long subjects, multiple intents packed into one commit |

The design philosophy is to move these common failure points forward as mandatory gates, each with clearly defined inputs, pass/fail conditions, and a clean failure exit.

## 3. Comparison with Common Alternatives

Before diving into the design, a quick high-level comparison helps establish what gap the skill fills:

| Dimension | `git-commit` skill | Plain `git add && git commit` | commitlint / hook only |
|-----------|--------------------|-------------------------------|------------------------|
| Preflight checks | Strong | Weak | Weak |
| Staging scope control | Strong | Weak | Weak |
| Secret scanning | Strong | Manual | Medium |
| Multi-ecosystem quality gates | Strong | Often skipped | Medium |
| Message convention | Strong | Inconsistent | Strong |
| Handling mixed-intent commits | Strong | Weak | Weak |
| Post-commit receipt | Strong | Weak | Weak |

The skill is not a replacement for hooks. It fills the layer that comes *before* hooks — the structured, interactive commit decision process that hooks alone cannot provide.

## 4. Core Design Rationale

### 4.1 Seven Steps in Series

The main workflow is:

```mermaid
flowchart LR
  A[Preflight] --> B[Staging]
  B --> C[Secret Gate]
  C --> D[Quality Gate]
  D --> E[Compose Message]
  E --> F[Commit]
  F --> G[Post-commit Report]
```

The order is not arbitrary. It follows a strict principle: the cheaper, the more foundational, the earlier it runs.

1. `Preflight` checks whether the repository is in a committable state.
2. `Staging` clarifies what is actually going into this commit.
3. `Secret Gate` intercepts high-risk content before any quality checks run.
4. `Quality Gate` validates only the content that is already confirmed for commit.
5. `Compose Message` runs last, because the message must be grounded in known scope, known intent, and known check results.
6. `Post-commit Report` ensures the workflow has a complete ending, not just a silent success.

This ordering solves two practical problems:

- Prevents wasted effort on the wrong object. If the repository is mid-rebase, there is no point discussing the message.
- Prevents after-the-fact fixes. Discovering a leaked secret after committing is far more costly than catching it before.

### 4.2 Preflight Is a Hard Gate

`git-commit` checks for conflicts, detached HEAD, and mid-operation states (rebase, merge, cherry-pick, revert) right at the start. The underlying insight is: **most commit accidents are not caused by bad code content — they are caused by bad repository context.**

The value of these checks is threefold:

- They are cheap — a handful of deterministic Git commands.
- A single failure makes every subsequent step meaningless.
- They significantly reduce the chance of mistaking a mid-operation Git state for a clean working tree.

Preflight is not a nice-to-have. It is a commit eligibility check.

### 4.3 Staging Is Its Own Layer

Most commit tools assume the user has already staged the right things. `git-commit` rejects this assumption and treats staging analysis as a distinct, non-trivial problem.

Four important design decisions here:

| Decision | Reasoning |
|----------|-----------|
| More than 8 changed files → always list all files and ask for confirmation | The more files there are, the easier it is to miss details and accidentally include the wrong ones |
| Group changes by logical intent, not by file list | A good commit unit is "one logical intent," not "a set of files" |
| Use `git add -p` when a single file contains multiple intents | Prevents staging granularity from being too coarse |
| Stash unstaged changes with `--keep-index` before running the quality gate | Ensures the gate validates what will actually be committed, without discarding local work |

**On the eight-file threshold:** the number is not arbitrary. Cognitive science research on working memory (Miller's Law) shows that error rates rise significantly when a person tracks more than 7±2 objects simultaneously. Past eight changed files, reliably reviewing each file's intent by hand becomes difficult. Fixing the threshold at 8 gives the confirmation prompt a clear, predictable trigger — it becomes a reliable safety net rather than something the model decides on a case-by-case basis.

The standout detail here is `stash --keep-index`. It reflects mature engineering judgment: **pre-commit tests should validate what is about to be committed, not a working tree that still contains unstaged changes mixed in.**

### 4.4 Secret Scanning Uses Regex Plus Layered Triage

Manual diff review misses tokens, private keys, and connection strings. Broad regexes catch everything but generate too many false positives. `git-commit` does not choose between these two approaches — it combines them:

1. Cast a wide net using filename and content regexes to capture as many suspicious matches as possible.
2. Filter through four ordered rule layers: allowlist, test data files, documentation, comments.
3. Only matches that survive all four filters actually block the commit.

This design balances security against usability:

- Scanning without triage buries users in false positives and they stop trusting the tool.
- Triage without scanning lets genuinely dangerous content slip through unnoticed.

The filter order is fixed as "first hit decides." Results are deterministic — they do not vary based on how the model interprets each specific situation.

### 4.5 Quality Gates Are Split into Reference Files

`git-commit` does not stuff Go, Node, Python, Java, and Rust quality checks into the main skill file. They live in separate `references/quality-gate-*.md` files instead.

This is a deliberate tradeoff with three benefits:

| Goal | Benefit |
|------|---------|
| Keep the main skill small | The main file stays focused on the universal commit workflow |
| Load on demand | Only the gate for the current ecosystem gets loaded |
| Independent maintenance | Each language gate can evolve without touching the main workflow |

More importantly, the decision of *which gate to run* is not left to the model's judgment. The skill provides deterministic rules: check the extension distribution of staged files, count staged files per ecosystem — deletions included, since a removed file still changes what compiles — and run every detected gate, largest first. The goal is not cleverness — it is reproducibility.

### 4.6 Message Generation Is Strictly Constrained

The skill enforces two hard constraints on the commit message:

- Total subject length must fit the repository's own limit, defaulting to ≤ 50 characters when the repository declares none.
- A scope may only appear if it has already been established in the commit history — otherwise, omit it entirely.

Each constraint addresses a distinct common failure:

| Constraint | Problem it solves |
|------------|-------------------|
| ≤ 50 characters by default | Prevents the subject from becoming a compressed summary paragraph, while still deferring to a commitlint/`CONTRIBUTING` limit when the repository sets one |
| No invented scopes | Prevents messages that look structured but actually introduce incorrect taxonomy |

The no-invented-scope rule deserves emphasis. Many tools encourage the model to always fill in a scope. `git-commit` requires the model to mine scope frequency from recent history before deciding whether to use one at all. This is a deliberate rejection of fake-structured output.

The April 2026 revision tightens this further in two places:

- **Bootstrap scope only for young repositories**: if the repository has fewer than 10 conventional commits total, the skill may infer a scope from the deepest stable staged directory after stripping generic path segments such as `src`, `pkg`, `internal`, `service`, `services`, `module`, `package`, `component`, and `testdata`. This fixes the "new repo can never establish a scope" failure mode without allowing free-form scope invention in mature repositories.
- **Executable subject guard**: the skill now requires a shell-level length and trailing-period check before `git commit` runs. The 50-character limit is therefore enforced by a concrete command path, not by model self-discipline alone.

The September 2026 revision came out of an external review that reproduced four
defects in the shipped scripts. Each fix is pinned by a test that fails against
the previous version:

- **Deletions reach the ecosystem detector.** `--diff-filter=d` excluded them, so
  removing an imported `helper.py` alongside a JavaScript edit selected only the
  Node gate — while the Python package no longer imported. A deletion is the
  change most likely to break a build, so it must select its gate.
- **Reads fail closed.** `git diff | awk` reports awk's exit status, so a failed
  git read produced empty output and exit 0 from both the secret scanner and the
  ecosystem detector — indistinguishable from "no secrets" and "no ecosystem".
  Both now check each read and exit 2, because *unknown* is not *none*.
- **Keyed secrets are recognised in every serialisation.** The old pattern
  required a literal lowercase key followed by `=`, so `"password": "x"` in JSON
  and `PASSWORD =` in a properties file were invisible — and, being undetected,
  were also printed verbatim in the context lines around a neighbouring finding.
  Matching is now case-insensitive over `:` and `=`, and context lines are masked
  by the same rule. The residual risk (a short unkeyed literal) is documented in
  SKILL.md rather than covered by a promise the code cannot keep.
- **Timeout escalates past TERM.** GNU `timeout` without `--kill-after` returns
  124 while a TERM-ignoring command keeps running — the coreutils manual
  demonstrates exactly this. The enforcer now probes for `-k` and passes it, so
  a timeout means the process group is genuinely dead. GNU reports 137 in that
  case, which SKILL.md now documents alongside 124.

The same revision moved scope resolution out of prose and into
`scripts/resolve-scope.sh`. The rules were purely mechanical — count, threshold,
strip, match — yet leaving them as prose forced the golden tests to re-derive
them in Python, so those tests only ever proved that one implementation agreed
with another. Driving the shipped script against real repositories replaced that
tautology. The move also allowed a rule the prose could not express cleanly: a
canonical scope is adopted only when **no second canonical scope** appears in the
staged set, so a commit spanning `auth/` and `billing/` is left unscoped instead
of being labelled with whichever scope is more frequent.

A second review round in September 2026 found that the first round had fixed the
reported instances rather than the underlying classes. Four more defects, all
reproduced before being accepted:

- **Paths were read in git's display form.** `--name-only` honours
  `core.quotePath`, so `源码/配置.py` arrived as `"\346\272\220…"`. The extension
  parsed as `py"`, `*.pem` stopped matching, and a stage of CJK-named sources
  detected no ecosystem at all — silently skipping the gate. All three scripts now
  read `-z` (raw, NUL-separated) and the patch stream runs under
  `-c core.quotePath=false`, so a finding is labelled with a path `git show` can
  actually open. Never hand a matcher the string git escaped for a terminal.
- **Only the git stage was checked.** The first round checked git's exit status
  but left the classifier unchecked, so a broken `awk` still exited 0 having
  printed nothing — the exact shape of a clean scan. `set -o pipefail` plus a
  status check on every pipeline means each failing stage now reports itself.
  *Could not tell* is not *nothing found*.
- **Detection and redaction were conflated.** One function decided both whether a
  line was a finding and where to cut it, so the 20+ character blob rule could
  only run as a fallback: `SESSION=<40 chars> password = x` cut at `password` and
  printed the session token in full, on the finding line itself. These are now
  two decisions — the blob rule never creates a finding, but always constrains
  the cut.
- **The timeout silently degraded.** A `timeout` without `--kill-after` was used
  anyway, behind a warning, and the perl watcher below it was unreachable.
  Reporting a timeout that the tool cannot deliver tells the caller the process
  group is dead while the gate may still hold locks and ports. An ineligible tool
  is now skipped, the search continues, and if nothing on the host can force-kill
  the enforcer exits 2 rather than run with a guarantee weaker than it reports.
  A test that previously *required* the degraded run had its expectation changed.

The pattern across both rounds is the same: a fail-open is rarely one line. It is
a stage that cannot distinguish "nothing" from "could not tell", and the fix has
to cover every stage that can produce that ambiguity, not the one that was
demonstrated.

A third round in September 2026 found a defect the second round had *introduced*.
`set -o pipefail` was added to make stage failures visible; the context extractor
stops at `NR > n + 2`; the writer was a pipe. Each choice is correct alone. Together
they produce a false block that only appears past the pipe buffer: the writer is
still writing when the reader leaves, takes SIGPIPE, exits 141, and a COMPLETED
context render is reported as a scanner failure. Clean at three lines, exit 2 at
twenty thousand — so every small fixture in the suite missed it, including the ones
written specifically for the pipefail fix.

The fix is not to relax the check. The context stage is now fed by process
substitution, which keeps the early exit (context is rendered once per finding, so
a full scan each time would be O(findings x lines)) while structurally excluding the
writer from the status, so `if !` again measures exactly the thing it names: whether
awk failed. A here-string would also work, but can spill to a temp file on bash
before 5.1, and this script must run where TMPDIR is not writable.

Two things generalise from it:

- **Single-point coverage does not find interaction defects.** Every individual
  choice here had a test. The failure lived in their combination, and was gated on
  a property no fixture varied — size. The suite now asserts small and large blobs
  agree *in one test*, so a regression cannot hide behind a passing small case.
- **A stage-failure check must be attributable.** A mutation deleting the context
  error check survived, because the shim used to test it broke every awk, so an
  earlier stage supplied the exit 2 on its own. The shim now fails exactly one
  invocation, and the test asserts the failing stage names *itself*.

The same round closed two verification gaps rather than adding rules.
`scripts/run_portability_matrix.sh` re-runs the suite once per available awk and
reports absent implementations as UNVERIFIED, exiting non-zero if nothing could be
exercised — an empty matrix is not a green one. That mattered immediately: twelve
credential patterns are length-anchored by regex intervals (`AKIA[0-9A-Z]{16}`,
the 20+ blob rule), and an awk without interval support treats `{16}` as literal
braces, matches nothing, and prints a confident clean result. `secret-scan.sh` now
probes that capability — both the literal and the runtime-compiled form it uses —
and refuses to run rather than degrade silently. A real-`gitleaks` contract test
runs where the binary exists and is reported as a visible skip where it does not,
because the alternative is a shim-only proof quietly counted as coverage.

Finally, a whole-workflow test executes §1 through §7 in order against one repo and
asserts a real commit lands. It does not prove the agent *decides* correctly — no
agent is in the loop — but it caught something no unit test could: SKILL.md's own
§7 report command printed a deleted CJK path as `"\346\272\220…"`, unreadable to
the user and not a path `git add --` accepts. The path-escaping class had been fixed
in all three scripts and missed in the documented commands beside them.

The fourth round in September 2026 answered the standing evidence objection
rather than adding rules, and the evidence immediately changed the design.

Five environments were exercised with the shipped scripts, using ephemeral
containers so nothing was installed on the host:

| Environment | awk | intervals | force-kill | Full suite |
|-------------|-----|-----------|------------|------------|
| macOS 15.6 | BSD awk 20200816 | yes | perl watcher | pass |
| Debian 12 | mawk 1.3.4 20200120 | **no** | GNU `timeout -k` | pass, 36 skipped |
| Debian 12 + gawk | GNU Awk 5.2.1 | yes | GNU `timeout -k` | pass |
| Ubuntu 24.04 | mawk 1.3.4 20240123 | yes | GNU `timeout -k` | pass |
| Alpine 3.24 | BusyBox awk | yes | BusyBox `timeout -k`, **no perl** | pass |

Three findings came out of it that no amount of single-host testing would have
produced:

- **Debian 12's default awk cannot match the patterns.** `mawk 1.3.4 20200120`
  has no regex interval support, so `AKIA[0-9A-Z]{16}` and eleven siblings match
  nothing. The capability probe added this round refuses to run there instead of
  printing a confident clean result. Ubuntu 24.04's `mawk 1.3.4 20240123` — the
  same nominal version — does support intervals, which is why a version
  comparison would have been the wrong test and a behavioural probe is the right
  one.
- **BusyBox `timeout` does not implement the 124 convention at all.** It reports
  the child's signal death: 143 for a plain expiry, 137 with `-k`. The previous
  round had documented "124 or 137", which was simply wrong on Alpine. The
  enforcer now runs the tool as a child rather than `exec`ing it and normalises a
  signal death at or past the deadline to 124, keying on elapsed time — the one
  piece of evidence no implementation can disagree about. Callers went from two
  codes to one, so the contract got *shorter* by being made correct.
- **A suite can be wrong about its own applicability.** On interval-less Debian
  the first run produced 31 failures. The script was behaving correctly; the
  tests assumed a capable awk. They now gate on the capability and skip with a
  reason that names the awk and the fix, so an operator on Debian reads
  "unsupported awk" instead of "broken skill". Installing gawk lifts the gate and
  all 172 run — proving it is a capability gate, not a blanket disable.

A real `gitleaks` was also exercised for the first time, and corrected two
things. The exit-code design was confirmed from the binary's own `--help`
("default 1") and behaviour (`--exit-code 10` yields 10) — but v8.18.4 has no
`git` subcommand at all and exits 1 for every invocation, which the script
already failed closed on and now explains in its error message. It also
invalidated one of this repository's own test fixtures: gitleaks **allowlists**
`AKIAIOSFODNN7EXAMPLE`, AWS's documentation key, and reports "no leaks found" for
it. A test built on that fixture proves nothing about the real scanner.

Two verification gaps remain, and are now addressed by tooling rather than by
assertion. `scripts/run_cross_env_probe.sh` needs only bash, git and awk, so it
runs where python does not — which is most minimal images, and was why every
non-macOS row had been missing. `scripts/eval/` probes the one thing no
deterministic suite can reach: whether an agent following the instruction picks
the right *branch* when authorisation is ambiguous, a change mixes intents, or a
tool reports an abnormal result. Its README states plainly that it grades a
stated decision in plan mode, is non-deterministic, reports per-repetition rather
than averaging, and treats a missing answer as INCOMPLETE rather than as a score.

Finally, the instruction was shortened. `SKILL.md` had accumulated the reasoning
behind each contract inline, which an agent re-reads on every invocation and
which duplicated the design documents. The measured evidence moved to
`references/design-evidence.md`, loaded only when maintaining the skill, and the
guard against regrowth is a **character** budget rather than a line count —
because the bloat had arrived as long sentences inside existing bullets, moving
the line count not at all.

The fifth round, September 2026, fixed two regressions the fourth round had
introduced, and then found a third defect in the evaluation harness that
invalidated part of the fourth round's own recorded evidence.

**A failing container was summarised as a pass.** The matrix ran
`if docker run … | sed 's/^/    /'`, so the `if` tested *sed*. A container
exiting 42 produced "all 2 exercised implementation(s) pass" and exit 0. In full
mode a second pipeline, `pytest … | tail -3`, hid a failing suite the same way.
Both now capture the status before formatting. Deliberately not `set -o pipefail`
for the whole file: other pipelines there end in `head -1`, whose early exit
would then be reported as a failure — the same trap round three fell into.

**Cancellation stopped reaching the gate.** Normalising the timeout code replaced
`exec tool` with a supervisor that launched the tool in the background and
`wait`ed. While it was `exec`, a signal to the executor hit the tool directly;
the supervisor forwarded nothing. Measured: SIGTERM to the executor returned 143
at once while the gate ran on and wrote its side effect two seconds later. The
supervisor now runs the tool in its own process group (`set -m`), forwards
INT/TERM/HUP to that **group**, waits for the group to empty, escalates to KILL,
and only then exits.

Two attempts at asserting that were wrong before one was right, and the wrong
ones are the more instructive:

- Asserting "no side effect at all after cancellation" passed by luck. Graceful
  termination sends TERM first *so that* a gate may clean up, and a shell gate
  finishes the statement it was on. The assertion was really a race on how far
  the gate got. It now asserts the guarantee the design actually makes: the gate
  is dead before the executor exits, and nothing new appears afterwards.
- Asserting the group kill makes cancellation *prompt* failed on correct code.
  With a tool that ignores TERM and a shell gate that survives it, the group form
  is no faster than the pid form; both wait out the grace window. What the group
  form buys is that the **escalation reaches the whole tree at all** — a pid-only
  escalation leaves such a gate running forever. Mutation testing is what forced
  that distinction: reverting only the forward survived, and only reverting the
  escalation as well was caught.

**The eval's skill arm had been running with no skill.** `SKILL_DIR` came from
`$0`, so copying the runner elsewhere to point it at a subset of scenarios moved
that path; `SKILL.md` did not exist, and the arm labelled `skill` was a second
control arm. Four recorded cells were void and had been reported as wins. It is
worth being precise about why it was caught at all: one nested run *said* the
file was missing and refused to substitute another `SKILL.md` it could have
found. Had it silently guessed, the numbers would have looked fine.

The runner now refuses to start without `SKILL.md` (exit 2), stamps the skill
path, line count and hash into every transcript so validity is auditable per
cell rather than inferred from prose, and takes `EVAL_SKILL_DIR` /
`EVAL_SCEN_DIR` so nobody needs to copy it. The void results were deleted rather
than annotated, and the standing summary of the eval is now "no measured
decision benefit" — six paired cells that *both* arms pass cannot demonstrate
one. Scenario 10 is the single case known to separate the arms, and only after
its grader was tightened from length alone to format **and** length: a base
answer of `Add reconciliation matcher stub` fits in fifty characters and is not
Conventional Commits at all.

### 4.6.1 Timeout Overrides Are Explicit

The original 120-second timeout rule was intentionally conservative, but it was too rigid for large Java and multi-module builds. The skill now treats timeout as a deterministic setting with a default and an override chain:

- Default: 120 seconds with no output.
- Override sources: repository wrapper configuration (`COMMIT_TEST_TIMEOUT`) or environment (`QUALITY_GATE_TIMEOUT_SECONDS`, `SKILL_QUALITY_GATE_TIMEOUT_SECONDS`).
- Operational rule: report the chosen timeout before starting the long-running quality gate.

This keeps the safety property ("do not hang forever") while removing the false-negative failure mode where a healthy but slow build looks like a gate failure.

### 4.7 There Is a Post-Commit Report

Many workflows treat a successful `git commit` as the finish line. `git-commit` does not. It requires a post-commit output that includes the short hash, final subject, a summary of changed files, and gate status.

This adds three concrete values:

- The user can immediately confirm what was just committed.
- Quality gate outcomes are recorded, not just shown in passing during the run.
- The report provides consistent input for subsequent PR creation, review, and audit.

The skill cares not just about executing the commit, but about whether the whole workflow reached a proper conclusion.

### 4.8 `--no-verify` Is Disallowed After a Hook Rejection

Step 6 has an explicit rule: if a Git hook (commitlint, pre-commit, husky, lefthook, etc.) rejects the commit, the message must be read and adapted to satisfy the hook. Using `--no-verify` to bypass it is not an option unless the user explicitly requests it.

The reasoning: **hooks are the team's compliance layer, not noise in an individual workflow.**

- Hooks in a project typically encode deliberate team or organization rules — an allowed scope list, a required ticket ID format, a ban on WIP commit types. Bypassing them with `--no-verify` is a unilateral declaration that one's own commit is exempt from the team's standards.
- A hook rejection is information: it tells you the message does not meet the agreed convention. The correct response is to fix the message, not to silence the feedback.
- Allowing AI tools to default to `--no-verify` creates a destructive cycle: the team spends effort configuring compliance hooks, and the AI tool quietly bypasses them.

The skill's response to a rejection is to report the hook name and error, adapt the message accordingly, and log what was changed. This resolves the immediate problem while keeping the hook's enforcement intact. The only exception is an explicit user instruction to skip — at that point, the skip is logged and the decision is returned to the user rather than made by the tool.

## 5. Problems This Design Addresses

Cross-referencing `SKILL.md` and the evaluation report, the skill targets these concrete engineering problems:

| Problem | Corresponding design | Practical effect |
|---------|----------------------|------------------|
| Bad repository state | Preflight hard gates | Stops on conflict, rebase, or detached HEAD before anything else runs |
| Staging scope drift | Intent-based grouping, 8-file threshold, `git add -p` | Reduces mixed-intent and accidental commits |
| Secret exposure | Filename scan + content scan + triage | Higher detection rate with fewer false positives |
| Skipped quality checks | Ecosystem-aware quality gate | Tests, lint, and vet run before every commit |
| Distorted commit messages | History-based scope discovery, length limit, imperative mood | More consistent and readable commit history |
| Bypassing team standards | Refusing default `--no-verify`, requiring error-based adjustment | Keeps hook compliance layer fully effective |
| No audit trail | Post-commit report | Every commit leaves a structured receipt |

The evaluation data backs this up: `git-commit` passed all 35 assertions across 3 test scenarios (100%), while the same scenarios without the skill had a strict pass rate of only 23%. The April 2026 regression expansion adds 7 golden fixtures for message composition, scope bootstrap, and timeout override behavior. The value is not prettier formatting — it is a significant reduction in steps that get skipped in real workflows.

## 6. Key Highlights

### 6.1 Elevating a Commit from a Command to a Quality Gate

This is the skill's most important contribution. It reframes a commit not as a mechanical command but as the last local checkpoint before code enters version history.

### 6.2 Determinism Over Model Improvisation

The skill's critical decisions are not "let the model guess." They follow a pattern of run a command first, then apply a rule:

- Repository state is determined by Git commands, not inference.
- Commit content is read from the staged diff, not guessed from the working tree.
- The quality gate is selected by extension count and marker file, not by judgment.
- Scope eligibility is decided by commit frequency in history, not by what sounds right.

The design goal is not to make the model look smart. It is to make the workflow reliably consistent.

### 6.3 Strict on Safety, Light on Friction

A skill that is only strict will eventually be worked around. `git-commit` keeps a practical balance:

- Secret scanning has an allowlist and triage — it is not all-or-nothing.
- Quality gates load per ecosystem — no project is forced to run a full suite it does not need.
- When the user explicitly asks to skip a gate, that is allowed — but the status is recorded.

The result is a skill that holds its safety line without becoming a workflow burden that nobody wants to use.

### 6.4 Explicit Rules for Edge Cases, Not Reliance on Default Behavior

`git-commit` spells out what to do in a set of situations that commonly cause problems:

- Empty commits are only allowed when the user explicitly requests one.
- Submodule pointer changes must be confirmed again after staging.
- Hook rejections require an adapted message, not `--no-verify`.
- Quality gate commands that produce no output for more than 120 seconds are interrupted and reported.

The value of these rules is that they cover not the happy path, but the edge cases that tend to be overlooked in real engineering work.

## 7. When to Use It — and When Not To

| Scenario | Suitable | Reason |
|----------|----------|--------|
| Everyday development commits | Yes | Gets the most value from preflight, staging grouping, and quality gates |
| Team wants consistent commit quality | Yes | Turns implicit standards into an executable workflow |
| Multi-language repository | Yes | Ecosystem-aware gates — no manual switching required |
| In a rush and want to bundle unrelated changes | No | The skill will actively prevent this |
| Need to skip all checks and just leave a quick marker | No | This is the opposite of what the skill is designed for |

## 8. Conclusion

The skill's real strength is not that it writes a Conventional Commit. It is that it systematizes the judgment that should happen *before* a commit is made. Through a seven-step serial workflow, it connects repository state checking, staging scope control, secret protection, ecosystem quality gates, message normalization, and post-commit reporting into one complete loop.

From a design standpoint, this skill is a clear example of production-grade skill principles in practice: **enforce gates before generating output; gather evidence before composing language; manage risk before optimizing for flow.** These principles are why it solves the core problem — commits being too casual to carry the risk they represent.

## 9. Document Maintenance

This document should be updated when:

- The workflow, hard rules, or failure handling in `skills/git-commit/SKILL.md` changes.
- The gate policies in `skills/git-commit/references/quality-gate-*.md` change.
- Key data in `evaluate/git-commit-skill-eval-report.md` that supports conclusions in this document changes.
- The project's team conventions around Conventional Commits, scope usage, or the commit workflow change.

Review quarterly; review immediately if the `git-commit` skill undergoes significant refactoring.

## 10. Further Reading

- `skills/git-commit/SKILL.md`
- `skills/git-commit/references/quality-gate-go.md`
- `skills/git-commit/references/quality-gate-node.md`
- `skills/git-commit/references/quality-gate-python.md`
- `skills/git-commit/references/quality-gate-java.md`
- `skills/git-commit/references/quality-gate-rust.md`
- `skills/git-commit/scripts/resolve-scope.sh`
- `evaluate/git-commit-skill-eval-report.md`
