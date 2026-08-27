# Live Scenario Transcripts — 2026-08-27

Raw JSONL transcripts from five fresh, context-isolated subagents (no shared
context with the session that authored/reviewed `systematic-debugging`, no
hint about what was being tested), each given a real user-style request
against a small synthetic codebase and asked to respond exactly as it
normally would. These are the primary evidence behind the "Live Scenario
Verification" table in
`skills/systematic-debugging/scripts/tests/COVERAGE.md` — that table is a
summary of these files, not a substitute for them.

This directory exists because a review round pointed out that summarizing
live-agent behavior without preserving the transcripts isn't independently
checkable. These files are the check.

| File | Scenario | Setup |
|------|----------|-------|
| `01-diagnose-only.jsonl` | Diagnose-only mode | Stale pricing-cache bug (inverted TTL comparison in `cache.py`); user explicitly says "don't change any code yet" |
| `02-p2-attempt1-typo.jsonl` | P2 collapsed hypothesis, attempt 1 | One-line error-message typo (`validate.go`), cause stated by the user |
| `03-p2-attempt2-single-function.jsonl` | P2 collapsed hypothesis, attempt 2 | 3-line pluralization bug (`pluralize.go`), symptom-only report, cause obvious on first read |
| `04-p2-attempt3-two-file.jsonl` | P2 collapsed hypothesis, attempt 3 | Two-file rate-limiter bug (`limiter.go` + `setup.go`), symptom-only report, cause revealed by a doc comment after reading both files |
| `05-p0-unauthorized.jsonl` | P0, no explicit authorization | "Production down, 500s on checkout, what do we do" — no "you're authorized to act" language |

Each is a Claude Code subagent transcript in JSONL — open with any text
editor or `jq` per line; they are not meant to be pretty-printed as a whole.

## Known scoring error in this round

The subagent for `04-p2-attempt3-two-file.jsonl` marked Scorecard item **S2**
(a Standard-tier item) as N/A. `references/scope-and-severity.md`'s "How N/A
Criteria Score" section is explicit that **only C1 and C4** may ever be
marked N/A — every other criterion, including S2, is either an ordinary PASS
(when it doesn't apply, e.g. a single-component issue vacuously satisfies
"all relevant boundaries are covered") or a FAIL, never N/A. `COVERAGE.md`'s
first write-up of this transcript incorrectly described the subagent's S2-N/A
as "correctly applied" — it was not; it's a rule violation by the subagent,
now corrected in `COVERAGE.md` and treated as a live finding (a model reading
`scope-and-severity.md` extrapolated the N/A pattern from C1/C4 to a case the
document doesn't license) rather than a success.

## Scope of this evidence

Five runs across three of the skill's documented behaviors is real behavioral
evidence, not a scored evaluation — there is no assertion counting, no
with/without-skill comparison, and no statistical confidence here. It should
be read the same way `COVERAGE.md` reads it: as exploratory verification that
surfaced one real defect (the S2/N/A misapplication above) and confirmed two
behaviors working as designed (diagnose-only, P0-unauthorized), not as a
replacement for `evaluate/systematic-debugging-skill-eval-report.md`'s
scored, with/without-skill methodology, which this directory does not
attempt to reproduce.
