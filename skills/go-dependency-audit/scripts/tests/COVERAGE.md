# go-dependency-audit — test coverage, stated honestly

What each layer proves, and — more usefully — what it does not. A suite that
claims to check everything is claiming something false.

Run everything offline: `bash scripts/run_regression.sh`

| Layer | File | Proves | Does **not** prove |
|---|---|---|---|
| Fact linter | `scripts/lint_dep_audit_docs.py` | 17 rules over commands, flags, env vars, version gates, pseudo-versions, destructive/write commands, readonly enforcement, legal framing, gate/mode consistency, allowed-tools | That prose reasoning is sound |
| Mutation tests | `test_doc_lint.py` | Every rule kills its own injected defect; every rule permits its own correction | That the rule set is complete |
| Recipe execution | `test_govulncheck_recipes.py` | The jq extracted **from the docs** classifies evidence tiers correctly, and breaks without `-s` | That govulncheck behaves as documented on your repo |
| **Real scan** | `test_govulncheck_recipes.py` + `fixtures/govulncheck/real_scan_x_net_v0.15.0.json` | The recipe's tier counts match govulncheck's own text summary on actual output; no CVSS exists in it | That other repos produce the same shapes |
| **Live end-to-end** (opt-in) | `TestLiveEndToEnd`, `GO_DEP_AUDIT_E2E=1` | Every documented gate command runs against a real vulnerable module; text exits 3 / json exits 0; probes do not mutate the manifest | Anything, when skipped — and it is skipped by default |
| **Live multi-module e2e** (opt-in) | `TestLiveMultiModuleEndToEnd` | A real **three**-module repo (root + nested + sibling) with a real `go.work`, driven by the literal documented commands: `-C` placement, `go-licenses` subshell form, per-module govulncheck and licence isolation, `GOWORK=off` vs workspace resolution measurably differing, same dependency at two versions = two findings | Aggregation/dedup logic itself, and the full S9 report |
| Structure | `test_skill_contract.py` | Sections, gate classes, degradation modes, scorecard maths, output contract are present and internally consistent | That following them yields a good audit |
| Golden scenarios | `test_golden_scenarios.py` | Every fixture's `violated_rule` and `coverage_rules` are anchored in the docs; vocabularies stay separate | Model behaviour — these are anchoring checks |
| Eval harness | `test_forward_eval.py` | Each criterion accepts a right answer and rejects a wrong one; arms differ only by prompt+cwd; the grader returns INCONCLUSIVE rather than PASS on missing evidence, short samples, or an unread SKILL.md | Anything about the model until `--run` is executed |
| Behavioural eval | `scripts/eval_forward.py --run` | Whether reading the skill changes what a model answers on six fact-carrying questions | Generalisation beyond those six questions |

## Verified against real tools, not memory

Pinned facts are cross-checked against installed binaries when present. A skipped
live check never counts as a pass — the static pins run unconditionally.

| Pin | Source of truth | Live cross-check |
|---|---|---|
| govulncheck flag set, modes, scan levels | `govulncheck -h` (v1.1.4) | `test_live_govulncheck_flags_match_the_pin` |
| govulncheck output strings, JSON schema | `x/vuln@v1.1.4/internal/scan/testdata/*` + a real scan | real-scan fixture assertions |
| go-licenses subcommands **and deprecations** | `go-licenses help` (v2.0.1) | `test_live_go_licenses_*_match_the_pin` |
| Go module env vars, `-mod` modes, `go env -w` | `go env`, `go help environment`, `go help build` (1.26.1) | pinned allow-list + allowed-tools tests |
| `+incompatible`, go.sum, sumdb privacy | go.dev/ref/mod | pinned prose + DA-E6 fixture |

## Behavioural evaluation: current status

Bar: **>= 4 wins, 0 losses, over all 6 fixtures**, each arm with exactly 3 valid
repeats, with-skill arms verified to have read skill content.

| Fixture | run2 | run3 | run4 | **run5** |
|---|---|---|---|---|
| DA-E1 no CVSS from govulncheck | TIE | TIE | TIE | TIE |
| DA-E2 non-existent flags | WIN | TIE | WIN | **WIN** |
| DA-E3 `-json` always exits 0 | WIN | WIN | WIN | **WIN** |
| DA-E4 licence → legal, not a verdict | WIN | WIN | TIE | **WIN** |
| DA-E5 `GOPRIVATE`, not `GONOSUMCHECK` | TIE | TIE | TIE | TIE |
| DA-E6 `+incompatible` is the same module | WIN | WIN | TIE | **WIN** |
| **totals** | 4W 0L 2T | 3W 0L 3T | 2W 0L 4T | **4W 0L 2T** |
| grading instrument | revised after run2 | negation scope | myth refutation | **frozen before the run** |
| verdict | PASS (unusable) | INCONCLUSIVE | INCONCLUSIVE | **PASS** |

**run5 meets the bar**, and it is the only run whose criteria were frozen before
it started. Earlier runs are kept to show the trajectory and the effect of each
measurement fix, not as evidence.

### Sensitivity check on the one-sided correction

Of the four criterion corrections, three either tightened a probe or moved both
arms. One — broadening `escalates_to_legal` to recognise "legal/compliance
reviewer" — helped only the with-skill arm on replay, so run5 was re-graded with
the **pre-broadening** probes to see whether the verdict depended on it:

```
current (broadened)                  DA-E4 with=3 without=2 -> WIN;  total 4 -> PASS
counterfactual (old narrow probes)   DA-E4 with=3 without=2 -> WIN;  total 4 -> PASS
```

It does not. In run5 the with-skill answers used the literal phrase "legal
review", which the old probes already matched. The broadening was still the right
fix — refusing to count "legal/compliance reviewer" was a false negative — but the
PASS does not rest on it.

### What the result does and does not say

- **0 losses in 24 fixture-runs.** The skill has never made an answer worse.
- **DA-E3 wins in all four runs.** The `-json`-always-exits-0 fact transfers
  reliably; the baseline reaches for a CI gate that can never fail.
- **DA-E1 and DA-E5 have never discriminated.** Baseline Sonnet 5 already knows
  govulncheck emits no CVSS and already reaches for `GOPRIVATE`. The effective
  fixture set is four, not six, and the bar of 4 wins is therefore "win every
  discriminating fixture".
- **DA-E4 and DA-E6 flip between runs.** One passing run is not a stable claim.
  The honest reading is: *meets the bar on the single run graded by the current
  instrument, with known run-to-run variance on two of the four.*

Replacing DA-E1 and DA-E5 remains next round's work, and the selection criterion
must stay independent of the skill: probe the **baseline alone** for facts it
gets wrong, build fixtures from those, then run once against frozen criteria.

### Measurement corrections, stated for audit

1. **Negation scope** (before run3). `asserted()` vetoed any clause containing a
   negator, so "…the *same* module path … — not a separate module" failed on a
   "not" attached to a different noun. Moved both arms.
2. **Read verification** (during run3 repair). Requiring `SKILL.md` specifically
   discarded runs where the model went straight to a `references/` file. Now
   accepts a content read of either; still rejects a Glob that only lists the
   directory. Recomputed from the recorded trace.
3. **Myth refutation** (before run4). `no_mvs_blindness_claim` failed
   `This matters more than "MVS ignores it" — it's the opposite.` A hit is now
   excused when quoted or contradicted in the same clause. **Cost the skill a
   win** (DA-E6 run4).
4. **Hyphen boundary + assertion direction + loose probe** (before run5).
   `\bno\b` matched inside `ship/no-ship`, inventing a negation; `asserted()`
   was also vetoed by *trailing* negators that negate a different constituent
   (now backward-only, while `denied()` stays bidirectional); and
   `warns_major_jump` probed the bare phrase "major version", which any mention
   satisfied — **tightened**, and it immediately rejected a synthetic bad answer
   that had been passing.

All the real excerpts behind these are pinned in `REAL_ANSWER_CASES` (11 cases)
so a widened criterion cannot silently narrow again. `--repair DIR` tops up arms
with fewer than `REPEATS` valid results; it never inspects a grade and repairs
every deficient arm, so it cannot be used to re-roll until a fixture wins.

## What `allowed-tools` does and does not guarantee

`allowed-tools` is a **least-privilege auto-approval surface**, not an
enforcement mechanism. It pre-approves the listed patterns so they run without a
confirmation prompt; a command that is *not* listed is not thereby forbidden — it
simply goes through the normal permission flow and can still be approved and run.
It is not a denylist.

So DA008 proves exactly this, and nothing more:

- **Proven**: no command that mutates the **dependency graph or the worktree**
  is silently auto-approved — `go get`, `go mod tidy`, `go env -w`,
  `go list -mod=mod`, `go work`, `git checkout/restore/reset` — and neither are
  **wrapper or chained forms** (`go get evil/x && go-licenses check ./...`,
  `bash -c '…; go-licenses check ./...'`), which a leading-wildcard pattern
  silently approves. DA017 bans leading wildcards; the attack strings are in the
  forbidden set. Every command the skill's own procedure needs *is* auto-approved,
  so the contract cannot block its own flow.
- **Not proven, and not claimed**: that nothing auto-approved can write a file
  anywhere. A pattern anchored at the command name cannot exclude a write flag
  that appears later on the line, so `git diff --output=FILE`,
  `git log --output=FILE`, `trivy fs --output FILE` and
  `govulncheck -format json` are all auto-approved and all write files (verified,
  not assumed). Shell redirects are the same story. These are pinned in
  `WRITES_OUTSIDE_THE_MODULE` and asserted to *be* approved, so a change in the
  surface is noticed rather than silently assumed. They write **outside** the
  module manifests; the read-only contract that matters here is about go.mod and
  go.sum, and gate 2/11's snapshot is what detects a breach of it.
- **Not proven**: that the skill is incapable of running a write command.

Real read-only enforcement needs a deny rule, a `PreToolUse` hook, or a sandbox —
none of which live in this file. What carries the actual obligation is SKILL.md
S1.3, plus the gate-2/gate-11 worktree snapshot, which *detects* a mutation after
the fact rather than preventing it. The e2e's
`test_readonly_probes_do_not_mutate_the_manifest` is the empirical half.

`allowed-tools` is also a Claude Code frontmatter field, not part of a minimal
`name`+`description` schema — a deliberate portability trade-off. A runtime that
ignores unknown keys loses the auto-approval convenience and the DA008 check; the
prose boundary in S1.3 is unaffected. There is no `agents/` directory here: no
skill in this repository has one, and a sibling skill carries a regression test
forbidding a reference to `agents/openai.yaml` after an earlier revision indexed
a file that never existed.

## Known gaps

- **Record vs finding.** Two modules on different versions of the same
  dependency produce two *version-scoped records* but only one finding — the one
  inside the advisory's affected range. The rule is stated in `multi-module.md`
  S5 with a worked table, fixture-anchored (DEP-022), and measured by
  `test_only_the_affected_version_produces_a_finding`.
- **e2e fixtures fail fast.** `go mod tidy` during fixture setup is checked, and
  a non-zero exit calls `pytest.fail` with the stderr and an explicit "this is an
  environment problem, not a skill defect" note. Verified by running under
  `GOPROXY=off` with an empty module cache: 18 clean setup errors naming the
  cause, instead of nine cascading assertion failures.
- **The subshell `go-licenses` form is deliberately not auto-approved.**
  Approving `( cd "$dir" && GOWORK=off go-licenses check ./... )` requires a
  leading wildcard, which would approve any command containing that fragment. A
  confirmation prompt on one command is the cheaper trade; `Bash(awk*)`,
  `Bash(trivy*)`, `Bash(nancy*)` and `Bash(jq*)` were narrowed for the same
  reason.
- **Six eval fixtures.** They cover the six facts most often got wrong; they are
  not a sample of real audits. Two of them (DA-E1 CVSS, DA-E5 GOPRIVATE) tie
  because the baseline model already knows the answer — that is information
  about the fixture, not about the skill.
- **The e2e covers gates and scanning, not the full report.** It proves the
  commands run and the exit codes are as documented; it does not produce an S9
  report and grade it.
- **Multi-module e2e proves the commands, not the synthesis.** Three modules,
  a real `go.work`, and per-module isolation are exercised; the *aggregation*
  rules (dedup by `(module, version, GO-ID)`, worst-module verdict) are stated
  and fixture-anchored but no test builds the merged report and checks it.
- **No test produces a full S9 report and grades it.** Gates, scanning and
  scoring are covered piecewise; the end-to-end deliverable is not.
- **Legal framing is guarded by ten pinned strings** (DA005). They catch
  reintroduction of the specific over-claims found in review, not novel overreach.
- **Reference prose is unverified** beyond the linted claims.
- **CVE/GO identifiers**: `GO-2023-2102` and its `v0.17.0` fix are verified
  against a real scan and against golang/vulndb; the `GO-2024-000N` fixtures are
  synthetic by design.
