# Test Coverage — google-search Skill

## What changed on 2026-08-13, and why

Every check in this skill used to be a keyword-existence test against one concatenated blob
of `SKILL.md` plus all seven reference files:

```python
ALL_CONTENT = SKILL.md + all references
assert "stars:>" in ALL_CONTENT
assert "filename:" in ALL_CONTENT
```

That shape has two independent failure modes, and both were live:

1. **It cannot tell a recommendation from a warning.** `filename:` and `stars:` are not
   GitHub code-search qualifiers. The suite was green while the docs recommended them, and
   stayed green — all 111 tests — after they were moved into a do-not-use table. The
   assertion could not observe the correctness change in either direction, so it also could
   not have prevented the defect.
2. **The scope is wider than the claim.** "The GitHub section documents `path:`" was
   satisfied by `path:` appearing anywhere across seven files.

Two of those assertions were also *load-bearing in the wrong direction*: correcting the
syntax would have broken `test_stars_filter` and `test_filename_filter`, so the tests
actively defended the error.

The suite now checks values, structure, and scope. Where a keyword test was superseded by a
scoped one, the keyword version was **deleted** rather than kept alongside it — two checks
that must agree drift, and the weaker one silently wins.

## Suites

| Suite | Responsible for |
|-------|-----------------|
| `test_skill_contract.py` | Structure: frontmatter and tool pre-approval, the 8 numbered gates in serial order, mode definitions and budgets, output-contract fields, reference files exist and are linked, GitHub's two search engines are documented separately, SKILL.md line bounds |
| `test_golden_scenarios.py` | Scoped fixtures: each pattern is required *in the file and section that owns it*, and forbidden patterns are expressible. Includes negative controls proving the scope resolver rejects a bad scope instead of falling back to the corpus, and that the forbidden check fires when a pattern is in scope |
| `test_lint_mutations.py` | Proof the linter is not inert: every rule in `ALL_RULES` fires on a mutation that reintroduces the specific defect it exists to catch, plus the skill's own worked examples must pass the output contract they teach |
| `lint_search_report.py --self-test` | The linter grades itself on crafted violations before it is trusted to grade anything else |
| `test_forward_eval.py` + `eval_forward.py --self-test` | Grades the **behavioural** grader offline: every criterion must pass a model answer and fail a bad one, no criterion may be unused, and the harness must be able to report the skill *losing*. A grader that cannot lose turns a live eval into an expensive way of printing green |

Counts are derived, never written down here — a hand-maintained per-category table goes stale
the first time the rule set correctly changes:

```bash
python3 -m pytest skills/google-search/ -q            # totals
bash skills/google-search/scripts/run_regression.sh   # everything, in order
```

## Rule families

The authoritative rule list is `ALL_RULES` in `scripts/lint_search_report.py`, with one line
per rule in that file's module docstring. It is not restated here.

| Family | Subject | Applied to |
|--------|---------|-----------|
| `GQ001`–`GQ013` | Query syntax: balanced quotes/parens, operator spelling, Google support tier, date validity (constructed, so `2026-02-31` fails), GitHub qualifier belongs to the declared engine, no query mixes both GitHub engines | any query string, including the ones inside the docs and inside a graded report |
| `GS001`–`GS017` | Output contract: mode and degradation declared, a conclusion actually present, executed queries within budget, reusable-query minimum, closed label enums, no snippet-as-fact phrasing, `Full` cites a source in a source-bearing position, Standard/Deep cite two hosts and state evidence chain + key evidence, Deep states source assessment, unrun queries marked, one query does not declare two engines | a finished search report (`python3 scripts/lint_search_report.py report.md`) |
| `GD001`–`GD007` | Doc invariants: no invalid qualifier in a recommended example — checked per engine subsection against the engine that subsection promises — the warning that makes that rule non-vacuous still exists, label enums closed and enumerated in exactly one file, mode budgets agree across three files | the skill's own documentation |

Rules that exist only to keep other rules honest:

- **GD002** fails if the do-not-use table stops naming `filename:` / `stars:`. Without it,
  deleting that table would make GD001 pass vacuously.
- **GS003** returns `unknown`, not a pass, when a report contains no executed-query list.
- **GQ012** returns `unknown` when a GitHub query does not declare its engine. This one is not
  a limitation of the parser but of the input: `language:go errgroup stars:>100` is a valid
  repository search *and* exactly what someone writes when they wanted code from popular
  projects and did not know `stars:` is unavailable in code search. No property of the string
  separates the two readings, so the author declares the engine (`[github-code]` /
  `[github-repo]` before the query) or the linter reports that it guessed.

A check that cannot see its subject must say so rather than fail open. Three rules
can return `unknown`; the runner treats `unknown` as non-blocking but prints it.

## Fixtures

Golden fixtures are scoped JSON:

```json
{
  "scope": "programmer-search-patterns.md",
  "section": "Code search qualifiers",
  "required_keywords": ["path:", "symbol:", "content:"],
  "forbidden_keywords": ["filename:", "stars:", "extension:"]
}
```

`scope` omitted means the whole corpus, which is only appropriate for a claim that really is
corpus-wide. A `scope` that names a missing file or section is a hard error.

## Fifth review pass, 2026-09-24 — the executing tool, the long tail, and the first live run

The first four passes checked the docs against Google and GitHub. None checked them against the
tool that actually executes the queries, and none checked the long tail of `site:` targets.

**The executing engine.** Twelve `WebSearch` probes (recorded in SKILL.md § Execution
Environment): `site:` including path prefixes, `-site:` and `filetype:` are honoured;
`before:` / `after:` are ignored; `site:stackoverflow.com` returns other hosts with no error;
`allowed_domains: ["stackoverflow.com"]` is refused with a 400, and `WebFetch` on a Stack
Overflow URL answers "Claude Code is unable to fetch from stackoverflow.com". The skill sent
agents to Stack Overflow throughout and relied on date operators for recency, with no statement
that either fails here.

**Wrong targets nobody had flagged**, all found by checking every `site:` value in the docs:

| Was | Problem | Now |
|---|---|---|
| `site:gov OR site:government` "across countries" | `.gov` is a US TLD; it never matches `gov.uk` / `gov.cn` | `site:gov` labelled US-only, plus per-country suffixes |
| `site:gov.uk/dhsc` | `site:` is a URL prefix; `/dhsc` is a 301 to `/government/organisations/…` | `site:gov.uk "Department of Health and Social Care"` |
| `site:xinhua.net` | no results under `allowed_domains`; Xinhua is `xinhuanet.com` / `news.cn` | corrected |
| `site:tax.gov.cn` | no results; the State Taxation Administration is `chinatax.gov.cn` | corrected |
| `site:redcross.org` for war casualties | the American Red Cross; the ICRC is `icrc.org` | `icrc.org`, `reliefweb.int` |
| `site:telegram.me` | redirects to the Telegram home page; posts live on `t.me` | `t.me` only |
| `site:github.com/go-redis` | the repository moved to `github.com/redis/go-redis` | corrected |
| `[go] <topic> site:stackoverflow.com` "Go-tagged" | Google ignores the brackets | tag syntax confined to Stack Overflow's own box |
| `"as of YYYY-MM-DD"` as an exact phrase | reporting writes "as of September 1", so the phrase excludes it | month form, date read from the page |

Four hosts in the Chinese exclusion list could not be confirmed to exist and were removed.

**Rules added so the class, not the instances, is guarded:**

- **GD008** is an allow-list: every `site:` value must be in `VERIFIED_SITES` with its evidence.
  A deny-list would only have caught the domains someone had already noticed — the table above
  is the list of ones nobody had. Two known-bad values are allowed only inside a sentence that
  refutes them, so the docs can still warn against them.
- **GD009**: degradation levels are defined in SKILL.md only. `ai-search-and-termination.md`
  carried a second definition — Full = "a strong primary source directly answers the question",
  the single-strongest-source test SKILL.md's decision tree exists to reject — and
  `test_degradation_protocol` **required** that copy to exist. It was replaced by a test that it
  does not.
- **GD010**: every recommended Google example passes Google syntax rules (it caught
  `imagesize:` still listed as a web-search example on its first run).
- **GS018**: a Quick report has no table. The Quick worked example was itself a table while
  SKILL.md said "No tables"; `test_example_passes_report_lint` passed it because no rule looked.
- **GQ014**: `[tag]` in a Google query.

**The live eval had never been able to measure search.** Four harness defects, all fixed before
the first run and each pinned by a test in `test_forward_eval.py`:

1. `--permission-mode dontAsk` without `--allowedTools` denied every WebSearch and WebFetch call
   in **both** arms (measured with a nested `claude -p`). Had it been run, it would have compared
   two arms that could not search.
2. "Skill was read" matched the path in a tool *call*; a denied read satisfied it.
3. The with-skill arm was pointed at this package, whose `eval/*.json` hold the ground truth, and
   both arms ran under the repository, loading its CLAUDE.md and `.claude/rules/`.
4. A global `~/.claude/skills/google-search` could reach the without-skill arm undetected.

Two fixtures were added because GS-E5/GS-E6 test facts the skill states: GS-E8 asks for one the
skill does not contain, GS-E7 for a source the environment cannot open.

**First live run** — Sonnet, both arms, one sample, `--seed 7`, 16 calls. The first grading
exited INCOMPLETE/FAIL, and every cause was in the harness or the grader:

| Reported | Cause | Fix |
|---|---|---|
| INCOMPLETE: with-skill arm opened a foreign skill copy | the new contamination check compared against the staged copy's *absolute* path; a relative `Glob` of `google-search-skill/references/*.md` was its own copy | `is_foreign_skill_access`, re-applied at grade time |
| SKILL LOSS `no_filename_qualifier` | clause split at the "." inside `go.mod`, stranding "no longer supported" in another clause | a period ends a clause only before whitespace |
| SKILL LOSS `no_stars_in_code_search` | every `stars:` query was validated as code search; `language:go stars:>=500` is a valid repository search, as the answer said | fail only a query no engine accepts (GQ013) |
| both fail `marks_undocumented_as_such` | both answers put "NOT officially documented" in the heading over the list | window = clause, paragraph, nearest heading |
| (pre-emptive) `degradation_is_not_full`, `queries_are_valid`, `labels_key_numbers` | passable only with this skill's vocabulary — an honest plain-language refusal lost for not printing "Blocked" | removed or made vocabulary-free |

Graded after the fixes: **2 win / 0 loss / 1 both-fail / 25 uninformative of 28**. The base model
already gets almost every criterion right, including both refusals and the Stack Overflow trap.
The two wins are a cited source (GS-E1) and the `after:` semantics (GS-E5) — the latter stated in
the skill's own references. This is one sample per arm: directional, not a result.

What the run found that nothing offline could: on GS-E5 the with-skill arm wrote "no live search
needed, the skill's own reference answers it", ran no query, cited no URL, and declared
`Quick · Full`. SKILL.md Gate 8 now says the skill is not a source and that every mode runs at
least one query; `test_skill_is_not_a_source` pins it. The without-skill arm of GS-E6 also found
something the skill had wrong: Google Search Central documents `imagesize:` and `src:` (Images
only), so "Google documents only the Tier A group" was scoped too broadly.

Next step: `--repeat 3`, and criteria aimed at what this base model gets wrong — 25 of 28
criterion-arms measured the model, not the skill.

## Fourth review pass, 2026-08-13 — the eval design itself

The skill's text was by now well covered; the open question was whether the *evaluation* could
prove anything. Five findings, all in `eval_forward.py`:

| Reported | Root cause | Fix |
|---|---|---|
| the without-skill arm ran with `--tools ""` | copied from a sibling skill, where it is less harmful; for a **search** skill it means the control arm cannot search at all, so the delta measured "skill + tools vs priors" | one `ARM_TOOLS` constant passed to both arms; the only per-arm difference is the prompt, asserted by test |
| `grade_dir` returned 0 with zero wins | "no losses" was treated as success | exit 2 INCONCLUSIVE below `MIN_WINS` |
| single sample, fixed arm order | one sample of a stochastic model is an anecdote, and running all `with` arms first lets run-time drift land on one arm | `--repeat N` aggregated by majority, `--seed`-shuffled call order |
| only 4 scenarios | thin coverage of the verifiable-fact axis | added GS-E5 (`before:`/`after:` filter last-updated time) and GS-E6 (which operators Google documents) — both facts a base model usually gets wrong |
| `evaluate/` cited as if local | that directory is one level above the package and is absent from an installed copy | qualified as a repository reference; `TestLocalLinksResolve` now fails on any unresolvable skill-local path |

The first is the most instructive: an A/B that varies two things measures neither. It read as
rigorous because the arms were labelled "with skill" and "without skill" — the label described
the intent, not the manipulation.

## Third review pass, 2026-08-13

| Reported | Root cause | Fix |
|---|---|---|
| `Blocked` unreachable in the degradation tree | the chain question was asked first, and every Blocked case also has an unsatisfied chain, so it routed to Partial | ask about total failure (budget exhausted / paywalled) first |
| an engine tag was borrowed across positions | `{query: engine}` dict — keyed on text, so one declaration vouched for the query everywhere and a second occurrence overwrote the first | per-occurrence list bound to its own comma-item; `GS017` for conflicting declarations |
| `after:0000` passed while `after:0000-01-01` failed | the bare-year branch returned early without constructing the date | one construction path for both forms |

The first is the same shape as the `0 < len(hosts)` guard from the second pass: an ordering
choice made for one reason (put the most informative question first) silently removed a verdict
from the reachable set. Decision trees need a reachability check, not just a correctness read —
`test_every_degradation_level_is_reachable` asserts `Blocked` is decided before the chain question.

## Second review pass, 2026-08-13

A follow-up review found five more fail-opens in the linter itself, all confirmed by minimal
counter-example before being fixed. They are recorded because four of the five are the same
root cause as the defects the linter was written to catch — a check whose scope or input is
wider than the claim it asserts:

| Reported | Root cause | Fix |
|---|---|---|
| `language:go errgroup stars:>100` returned no findings | engine was **guessed** from the string; the guess is about author intent, which the string does not carry | declared engine (`[github-code]`/`[github-repo]`), guess reported as `GQ012` unknown |
| a Quick/Full report with no conclusion scored clean | no rule checked that the report answers anything | `GS013`, over the explicit Conclusion field or the free-prose residue |
| a Standard/Partial report citing nothing scored clean | `GS010` was guarded by `0 < len(hosts)`, so zero hosts skipped the check | `len(hosts) < 2` |
| `Full` was satisfied by any URL anywhere | scope was the whole document, not a citation position | `GS009` counts hosts only under Key evidence or a source-naming line |
| `after:2026-02-31` passed | month/day range check instead of date construction | `datetime.date(...)` |

The `0 < len(hosts)` guard is worth naming on its own: a boundary added to avoid double-reporting
with a neighbouring rule turned the empty case — the worst case — into a skip.

## What these tests still cannot prove

Stated plainly, because a green suite invites the opposite assumption. These are offline
checks over text. They establish that the skill's instructions are internally consistent,
that its query syntax is valid against the engines' current documented grammar, and that a
report *which is submitted for grading* satisfies the output contract. They do not establish
that the agent:

- selects the right execution mode for a given request,
- actually executes the queries it lists,
- actually opens the pages it cites, or
- reaches a correct answer.

Those are properties of a run, not of a document, and only a live eval can observe them. The
earlier A/B report measured format compliance, not answer correctness — see its Validity
Limitations section for what its headline number does and does not support. That report lives in
the awesome-skills repository at `evaluate/google-search-skill-eval-report.md`; it is not shipped
inside this skill package, so treat the path as a repository reference rather than a local file.

The behavioural gap above is what `scripts/eval_forward.py` addresses. Its grader is tested
offline here; the run itself needs an authenticated CLI:

```bash
python3 scripts/eval_forward.py --run --model sonnet --repeat 3 --out eval_out
```

Both arms receive the same `--model` and the same `--tools`, so the only variable is whether the
prompt points at the skill.
