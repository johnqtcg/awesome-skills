# Forward evaluation — grading reviews, not documents

Graded by `../test_forward_eval.py`.

## Why this layer exists

The other three test layers all validate **artefacts**:

| Layer | Validates | Blind to |
|---|---|---|
| `test_skill_contract.py` | the documents contain the required rules | whether following them finds anything |
| `test_golden_reviews.py` | fixture metadata is complete; its rule strings exist in the docs | the review itself |
| `test_examples_executable.py` | the GOOD example code compiles and is genuinely safe | the review itself |

A skill can pass all three while a reviewer driven by it still misses the bug, or — more often —
reports the safe code as vulnerable. This layer grades the **output of a review**.

## The two polarities, and why both are required

| Scenario | Fixture | Ground truth | Failure it detects |
|---|---|---|---|
| `idor_true_positive` | `golden/001_idor_missing_authz.json` | a real P1 IDOR | **missed detection** |
| `ssrf_false_positive` | `golden/019_ssrf_allowlisted_domain_fp.json` | safe — URL comes from a server-side map | **over-reporting** |

Detection-only grading is easy to game: a reviewer that flags everything scores perfectly. The
false-positive scenario is the harder half and the one that decides whether the suppression rules
actually work. `ScenarioIntegrityTests.test_both_polarities_are_covered` enforces that both stay
present.

## What the grader scores

Given a review and the fixture's ground truth:

1. **Output contract** — `mode`, `data_basis`, `active_verification`, scorecard present.
2. **True positives** — a finding is reported, names the vulnerability class, carries the expected
   severity, a confidence label, a CWE, and a **version-pinned** ASVS ID.
3. **False positives** — *no* finding is reported, the suppression is explicit, and it cites a
   numbered suppression rule (a bare "looks fine" does not pass).
4. **Machine-readable JSON** — parses, uses `security_domains` (never the retired `go_domains`),
   `total` is 10, and carries `stack` / `asvs_version` / `active_verification`.
5. **No fabricated execution** — if `active_verification` is `not_permitted`, the review must not
   claim it ran anything; reproducers must be labelled `NOT executed`.

## The exemplars

Each scenario ships `good.md` (must pass) and `bad.md` (must fail). `bad.md` is written to fail
for the **intended** reason, and a test asserts that specifically — a bad exemplar failing on an
incidental technicality would prove nothing:

- `idor_true_positive/bad.md` — declares "No security issues found", and uses the retired
  `go_domains` key. Must fail on `MISSED the real vulnerability`.
- `ssrf_false_positive/bad.md` — reports the allowlisted-map SSRF as a confirmed P1. Must fail on
  `FALSE POSITIVE`.

Three further self-tests mutate the good exemplar to confirm the grader is not a rubber stamp:
swapping in `go_domains`, stripping the ASVS version, and forging execution claims must each be
caught.

## Running it

```bash
python3 -m unittest discover -s skills/security-review/scripts/tests -p 'test_forward_eval.py' -v
```

Pure Python — no toolchain, no network, deterministic.

## Live evaluation (opt-in)

```bash
export SECURITY_REVIEW_EVAL_CMD='your-model-cli --stdin'
python3 -m unittest discover -s skills/security-review/scripts/tests -p 'test_forward_eval.py' -v
```

The command reads a prompt on stdin and writes the review to stdout. The reviewer receives the
skill and the code **only** — never the fixture's expected verdict — so detection and suppression
are measured rather than recalled.

## Honesty boundary

The self-tests prove the **grader** discriminates good reviews from bad ones. They do **not**
prove that a live model passes. Only the opt-in live hook does that, and it is skipped by default
— which is why `run_regression.sh` reports **PASS WITH SKIPS** rather than a bare pass when it is
unconfigured. That distinction is the point: an unconfigured forward eval is a gap in
verification, not evidence of correctness.
