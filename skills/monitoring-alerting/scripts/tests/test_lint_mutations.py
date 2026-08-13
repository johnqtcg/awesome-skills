"""Mutation sweep for `lint_monitoring_docs.py`.

Every other test in this directory asserts that some text is *present*. That is
one-directional evidence: the suite is green when the docs are right and equally green
when the assertions are empty, and reading it cannot tell you which. This file settles it
by breaking each rule's subject in a temp copy and requiring the **named** rule to fire.

It earns its place immediately. The first version of MA006 tested
`expr:.*_total\\s*[<>]` on a single line and `not re.search(r"rate\\(", rule)` over the
whole rule -- so a mutation that put a bare counter in the *numerator* while the
denominator stayed wrapped in `rate()` sailed through. The rule looked reasonable and did
nothing. Only the mutation showed that; no amount of re-reading would have.

Coverage is derived, not declared: `RULE_IDS` is read out of the linter's own docstring,
so adding a rule without a mutation fails `test_every_rule_has_a_mutation` rather than
silently reading as covered.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[2]
LINTER = SKILL_DIR / "scripts" / "lint_monitoring_docs.py"

# (rule, file, find, replace, why this mutation matters)
#
# `find`/`replace` may each be a string, or matching tuples for a mutation that needs several
# edits. Fixture-scoped rules need that: MA013 asks whether a fixture declares its budget
# basis *anywhere*, and this fixture declares it three times, so removing one phrase leaves
# the rule correctly satisfied. Weakening the rule to make a one-line mutation work would be
# the wrong trade.
MUTATIONS = [
    ("MA001", "references/sli-slo-patterns.md",
     "2% of the 30-day budget spent in 1h", "9% of the 30-day budget spent in 1h",
     "the percentage is the number an on-call reads off the page; a wrong one "
     "misrepresents how urgent the burn is"),
    ("MA002", "references/sli-slo-patterns.md",
     "exhausts in ~50h if sustained", "exhausts in ~2h if sustained",
     "this is the exact error that shipped: 14.4x takes 50 hours, not 2"),
    ("MA003", "references/sli-slo-patterns.md",
     "| Page | 14.4 | 1 h | 5 m | 2% |", "| Page | 14.4 | 1 h | 30 m | 2% |",
     "the short window gates 'is it still happening'; at 1/2 the long window it stops "
     "being a gate and the alert lingers after recovery"),
    ("MA004", "references/alertmanager-config-patterns.md",
     '- matchers:\n        - severity = "critical"', "- match:\n        severity: critical",
     "match/match_re are deprecated; emitting them teaches config that upstream is retiring"),
    ("MA005", "references/sli-slo-patterns.md",
     '    runbook_url: "https://wiki.example.com/runbooks/slo-burn-rate"',
     "    # runbook intentionally removed",
     "the skill requires a runbook on every alert; shipping one without is the "
     "do-as-I-say-not-as-I-do failure a reviewer will notice first"),
    ("MA006", "SKILL.md",
     "expr: rate(http_errors_total[5m]) / rate(http_requests_total[5m]) > 0.01",
     "expr: http_errors_total / rate(http_requests_total[5m]) > 0.01",
     "a bare counter compared to a threshold crosses it eventually no matter what the "
     "service does. Targets the AE-1 RIGHT half deliberately: it is the example readers "
     "copy, and it was exempt from every rule until the per-half fix"),
    ("MA008", "SKILL.md",
     "`for` is **optional** in Prometheus", "`for` is mandatory",
     "re-absolutising this is how the reviewed defect comes back"),
    ("MA007", "SKILL.md",
     "that is this skill's **default example, not a requirement**",
     "critical alerts must page via PagerDuty",
     "a vendor mapping stated as a requirement fails orgs with a different stack"),
    # ---- added after the 2026-08-12 second review ----
    ("MA009", "references/alert-anti-patterns.md",
     "| `up == 0` | **Yes** — default `for: 5m` |",
     "| `up == 0` | No — deadman / watchdog, already a sustained absence |",
     "this is the exact error the previous round introduced: up == 0 is true after ONE "
     "failed scrape, so exempting it from `for` turns a dropped packet into a 3AM page"),
    ("MA010", "references/sli-slo-patterns.md",
     "| Service tier | Availability SLO | Time-based budget (30 d) |",
     "| Service tier | Availability SLO | Error budget (30 days) |",
     "the basis has to be where the number is: a reader scanning a table row does not read "
     "the next paragraph, which is exactly how the first version of this rule failed open"),
    ("MA011", "references/sli-slo-patterns.md",
     "| **Latency** | proportion of valid requests faster than the objective",
     "| **Latency** | p99 response time",
     "a percentile is a duration, not a countable bad event -- there is no error budget to "
     "burn against it"),
    # Injects an unlabelled minutes budget into a fixture that declares NO basis. Deleting
    # labels from MON-007 does not work: it declares its basis four independent ways
    # ("request-based", "uniform traffic", "valid requests", "time-based"), which is the rule
    # being satisfied, not a gap. Adding the offending shape to a clean fixture tests the rule
    # directly and in one edit.
    ("MA013", "scripts/tests/golden/001_no_sli.json",
     "Critical:",
     "Critical: the SLO allows an error budget of 43.2 minutes per month.",
     "a good_practice fixture IS the model answer; an unlabelled minutes budget there "
     "teaches that a request-based SLO guarantees downtime minutes"),
    ("MA014", "scripts/tests/golden/007_well_formed_slo.json",
     "(3) valid and good are both stated",
     "(3) the SLI is non-5xx / total",
     "a bare non-5xx/total in the model answer contradicts the recording rules in the same "
     "fixture, and is unauditable on its own"),
    ("MA015", "references/sli-slo-patterns.md",
     "sli:http_requests_bad:rate5m / sli:http_requests_valid:rate5m` |",
     'sum(rate(http_requests_total{code=~"5.."}[5m])) / sum(rate(http_requests_total{job!=""}[5m]))` |',
     "two inline selectors that differ by one matcher look fine and silently stop being "
     "complements -- the drift the recording rules exist to prevent"),
    # These three are graded by test_yaml_artifacts (parser / promtool / window checks),
    # not by the linter, so they carry a GOLDEN- prefix and are asserted below by
    # test_golden_defects_are_covered rather than by rule id.
    ("MA016", "scripts/tests/golden/013_error_budget_exhaustion.json",
     "fired at 60x for 8 hours", "fired at 6x for 8 hours",
     "the exact defect that shipped: 6x for 8h is 6.67%, not 66%. A 10x error in a workflow "
     "fixture's premise makes every downstream conclusion wrong while looking plausible"),
    ("MA017", "references/sli-slo-patterns.md",
     'http_request_duration_seconds_bucket{path!~"/health.*|/metrics",code!="499",le="0.4"}',
     'http_request_duration_seconds_bucket{path!~"/health.*|/metrics",le="0.4"}',
     "the latency bucket shipped without the code!=\"499\" the counter had, so the fast "
     "numerator counted requests the denominator excluded and fast/valid > 1 was reachable"),
    ("MA018", "references/sli-slo-patterns.md",
     '**On the latency denominator, `le="+Inf"` vs `_count`.**',
     'Note the denominator uses `_count`, not `le="+Inf"` --',
     "the prose told the reader not to use the spelling every recording rule above it used; "
     "following the prose produces what the file's own examples contradict"),
    ("MA019", "scripts/tests/golden/013_error_budget_exhaustion.json",
     "20% remaining and 5% remaining are both tickets, not pages",
     "warn at 20% remaining and page at 5% remaining",
     "a low budget with no active burn is a policy state, not an incident -- waking someone "
     "cannot restore budget, and paging on it is how a pager stops being believed"),
    ("MA020", "tests/promtool/rules.yml",
     'sum(up{job="order-api"}) == 0 or absent(up{job="order-api"})',
     'count(up{job="order-api"} == 1) == 0',
     "an aggregation over an EMPTY vector is empty, not 0, so this form is silent exactly when "
     "every replica is down -- verified with promtool, and the broken form passes "
     "`check rules` happily"),
    ("MA012", "scripts/tests/COVERAGE.md",
     "| Fixture | Test Class | Validates |\n|---------|-----------|-----------|",
     "| Fixture | Test Class | Tests | Validates |\n|---------|-----------|:-----:|-----------|",
     "a 4-column header over 3-column data rows renders as a broken table"),
]


def rule_ids_from_docstring() -> set[str]:
    text = LINTER.read_text(encoding="utf-8")
    doc = text.split('"""')[1]
    return set(re.findall(r"^\s{2}(MA\d{3})\s", doc, re.M))


def run_linter(root: Path):
    proc = subprocess.run([sys.executable, "scripts/lint_monitoring_docs.py"],
                          cwd=root, capture_output=True, text=True, timeout=120)
    return proc.returncode, proc.stdout + proc.stderr


class LinterMutationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="mon-lint-baseline-")
        root = Path(cls.tmp) / SKILL_DIR.name
        shutil.copytree(SKILL_DIR, root,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"))
        cls.rc, cls.out = run_linter(root)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_baseline_copy_is_clean(self):
        """Without this, every 'mutation caught' below could be an unrelated pre-existing
        finding, and the sweep would report success while proving nothing."""
        self.assertEqual(self.rc, 0,
                         f"the unmutated copy already has findings:\n{self.out[-2000:]}")

    def test_self_test_passes_on_baseline(self):
        root = Path(self.tmp) / SKILL_DIR.name
        proc = subprocess.run([sys.executable, "scripts/lint_monitoring_docs.py", "--self-test"],
                              cwd=root, capture_output=True, text=True, timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("pre-fix defects still caught", proc.stdout,
                      "the linter's self-test no longer reports how many of the original "
                      "defects it still catches -- that number is the whole point")

    def test_each_mutation_fires_its_rule(self):
        if self.rc != 0:
            self.skipTest("baseline not clean; see test_baseline_copy_is_clean")
        for rule, rel, find, replace, why in MUTATIONS:
            with self.subTest(rule=rule, file=rel):
                tmp = tempfile.mkdtemp(prefix="mon-lint-")
                try:
                    root = Path(tmp) / SKILL_DIR.name
                    shutil.copytree(SKILL_DIR, root,
                                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc",
                                                                  ".pytest_cache"))
                    target = root / rel
                    body = target.read_text(encoding="utf-8")
                    finds = find if isinstance(find, tuple) else (find,)
                    repls = replace if isinstance(replace, tuple) else (replace,)
                    self.assertEqual(len(finds), len(repls),
                                     f"{rule}: find/replace tuples differ in length")
                    mutated = body
                    for f_, r_ in zip(finds, repls):
                        self.assertIn(
                            f_, mutated,
                            f"the {rule} mutation no longer matches {rel} -- the text was "
                            f"reworded, so this mutation tests nothing. Update MUTATIONS.")
                        # replace EVERY occurrence: a partial mutation leaves another copy
                        # satisfying the rule and the survivor gets misread as a dead rule
                        mutated = mutated.replace(f_, r_)
                        if f_ not in r_:
                            # The "find is gone" check guards against a partial replacement.
                            # It does not apply to an INJECTION, where the replacement
                            # deliberately keeps the anchor and appends to it -- that is how
                            # you test a rule whose subject is the presence of a bad shape
                            # rather than the absence of a good one.
                            self.assertNotIn(f_, mutated)
                    target.write_text(mutated, encoding="utf-8")

                    rc, out = run_linter(root)
                    self.assertNotEqual(
                        rc, 0,
                        f"MUTATION SURVIVED for {rule}: replacing {find[:60]!r} in {rel} "
                        f"produced no finding.\nWhy it matters: {why}")
                    self.assertIn(
                        f"[{rule}]", out,
                        f"the linter went red for the {rule} mutation, but {rule} was not "
                        f"the rule that fired -- it is being caught by accident, so "
                        f"{rule} is not actually guarding this.\n{out[-1500:]}")
                finally:
                    shutil.rmtree(tmp, ignore_errors=True)

    def test_golden_defects_are_covered(self):
        """The two defects MON-007 actually shipped must have a guard, named explicitly.

        A mutation list keyed on linter rule ids cannot express these -- they are caught by
        the YAML parser and by `promtool`, which have no rule id. Naming the guarding tests
        here means deleting one of them fails this file rather than silently reducing
        coverage of the worst failure this skill has had.
        """
        yaml_tests = (SKILL_DIR / "scripts" / "tests" /
                      "test_yaml_artifacts.py").read_text(encoding="utf-8")
        for guard, why in (
            ("test_every_good_practice_snippet_parses",
             "MON-007 shipped a code_snippet that did not parse as YAML at all"),
            ("test_multi_window_claims_use_two_windows",
             "MON-007 claimed 1h+5m while using 5m on both sides"),
            ("test_feedback_window_claims_match_the_expression",
             "prose naming a window the expression never uses"),
            ("test_good_practice_snippets_pass_promtool",
             "golden snippets were never fed to the real parser"),
            ("test_temporal_unit_tests_pass",
             "syntax-only validation cannot see a wrong window pairing or a wrong `for`"),
        ):
            self.assertIn(guard, yaml_tests,
                          f"guard {guard} is gone; it covers: {why}")

    def test_every_rule_has_a_mutation(self):
        """Derived closure: the denominator is the linter's rule list, not this file's.

        A sweep that counts kills against its own mutation list cannot notice a rule with
        no mutation at all -- that rule reads as covered while being exercised by nothing.
        """
        declared = rule_ids_from_docstring()
        self.assertGreaterEqual(len(declared), 20,
                                "could not parse rule IDs out of the linter docstring")
        mutated = {m[0] for m in MUTATIONS}
        missing = sorted(declared - mutated)
        self.assertEqual(
            missing, [],
            f"{len(missing)} linter rule(s) have no mutation, so nothing proves they fire: "
            f"{missing}")
        stale = sorted(mutated - declared)
        self.assertEqual(
            stale, [],
            f"mutations name rules the linter no longer declares: {stale}")


if __name__ == "__main__":
    unittest.main()
