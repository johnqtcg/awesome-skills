# Dependency Audit Scorecard

> Load at the end of an audit, to score it. SKILL.md S8 states the tier
> thresholds and the N/A rule; this file is the item list and how to judge each.

Twelve checks in three tiers. A check that could not run because of a DEGRADE
gate scores **N/A** and is removed from both numerator and denominator — it never
counts as a pass. In a multi-module audit, score **per module**; the repository
verdict is the worst module's, never an average.

## Table of Contents
1. Critical
2. Standard
3. Hygiene
4. Scoring Worked Example

---

## 1 Critical (ratio must be 1.00)

**C1. govulncheck completed** — exit code 0 or 3, output parsed.
Exit 1 is a failed scan: score N/A and enter `no-cve`, never pass. A common
cause is a govulncheck built against a different Go than the one on `PATH`;
the fix is to rebuild it, not to record a clean result.

**C2. No unaddressed P0 findings** — every finding meeting the *full* S6.3 P0
test (E1 Called **and** a fix version exists **and** the path is reachable from a
network-facing entry point) is remediated or carries a written, dated waiver.
An E1 finding failing any of those three is **P1**, scored by S1 below. The two
items must not double-count the same finding.

**C3. Checksum state reported** — the `go mod verify` result is recorded, pass
*or* fail. A mismatch is a reported P1 finding, not a failed check: this item
asks whether you looked, not whether it passed.

---

## 2 Standard (ratio >= 0.80)

**S1. No unaddressed P1 findings** — E1 Called findings outside the P0 test,
checksum mismatches, and unlicensed dependencies linked into a shipped artifact.

**S2. License inventory produced** — every dependency has a licence identifier,
or is explicitly listed as unresolved. "Unresolved" is an acceptable value;
silence is not.

**S3. Every copyleft/unknown licence has an escalation record** — routed to
legal with the S5.2 item 11 facts attached. Scored on whether the packet exists,
never on what the answer was — this skill does not adjudicate it.

**S4. No `+incompatible` direct dependencies** — or each one has a recorded
migration plan. Remember these are the *same* module to MVS, so `-u` can cross a
major version silently.

**S5. `GOPROXY`/`GOPRIVATE`/`GOSUMDB` recorded** — actual values read with
`go env GO…`, not assumed defaults. `GOPRIVATE` must cover every internal module
prefix actually present in `go.mod`; a partial pattern leaks the ones it misses.

---

## 3 Hygiene (ratio >= 0.75)

**H1. go.mod is tidy** — `go mod tidy -diff` empty. **N/A below Go 1.23**, where
the flag does not exist; do not substitute the mutating `go mod tidy`.

**H2. Every `replace` directive has a documented justification** — a rationale
and a removal condition, next to the directive or in an issue it links to.

**H3. No local-path `replace` committed** — a filesystem path in a committed
`go.mod` breaks every machine but the author's.

**H4. `go.work` status assessed** — absent, gitignored, or a repo-relative
workspace with a stated reason for committing it. Check the `use` paths before
flagging: a single-repository workspace is a legitimate thing to commit.

---

## 4 Scoring Worked Example

A Standard audit where `go-licenses` was unavailable (gate 9 DEGRADE ->
`no-license`) and the module is on Go 1.22:

| Item | Result | Note |
|---|---|---|
| C1 govulncheck completed | pass | exit 3, parsed |
| C2 no unaddressed P0 | pass | one E1 finding, not network-reachable -> P1 |
| C3 checksum state reported | pass | "all modules verified" |
| S1 no unaddressed P1 | fail | the E1 finding above is unremediated |
| S2 licence inventory | **N/A** | `no-license` mode |
| S3 escalation records | **N/A** | `no-license` mode |
| S4 no `+incompatible` | pass | |
| S5 env recorded | pass | |
| H1 tidy | **N/A** | Go 1.22, `-diff` unavailable |
| H2 replace justified | pass | |
| H3 no local-path replace | pass | |
| H4 go.work assessed | pass | absent |

```
critical = 3/3 = 1.00              >= 1.00  ok
standard = 2/3 = 0.67              >= 0.80  FAIL
hygiene  = 3/3 = 1.00 (1 N/A)      >= 0.75  ok
Verdict: FAIL — Critical 3/3 (1.00) · Standard 2/3 (0.67, 2 N/A) · Hygiene 3/3 (1.00, 1 N/A)
```

Note what the N/A rule prevents: scoring the two `no-license` items as passes
would give `standard = 4/5 = 0.80` and flip the verdict to PASS on the strength
of two checks that never ran.
