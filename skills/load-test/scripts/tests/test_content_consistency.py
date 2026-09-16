"""Cross-checks that compare NUMBERS and MEANINGS, not keywords.

Why this file exists. A mutation audit injected 25 semantic defects into this
skill and 16 survived — including a threshold changed to 10x its own adjacent
comment, p95/p99 meanings swapped in the percentile table, an arithmetically
impossible worked average, a scorecard whose tiers no longer summed to its
stated total, a `>= 4 of 5` gate silently relaxed to `>= 2 of 5` while the
verdict line still said 4/5, minute-scale durations rewritten as seconds, and
nine occurrences of a vegeta flag that does not exist. Every one passed,
because `test_skill_contract.py` is 87% substring-presence assertions: it
checks that a word appears, never that a number is right or that two places
describing the same thing still agree.

`test_outputexample.py` already does this properly — it parses the published
script's threshold and compares it against the SLO stated in the prose, and it
checks the scorecard's arithmetic. That discipline was applied only to
`outputexample/`, the one directory that is not part of the skill. This file
applies it to `SKILL.md` and `references/`, which are what actually ship.

Rule of thumb for anything added here: if the assertion would still pass after
someone edits the number, it does not belong in this file.
"""

import re
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[2]
SKILL_MD = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
K6 = (SKILL_DIR / "references" / "k6-patterns.md").read_text(encoding="utf-8")
VEGETA = (SKILL_DIR / "references" / "vegeta-patterns.md").read_text(encoding="utf-8")
ANALYSIS = (SKILL_DIR / "references" / "analysis-guide.md").read_text(encoding="utf-8")


def section(text: str, heading: str, stop: str) -> str:
    """The body between two headings. Assertions scoped to a section cannot be
    satisfied by an unrelated paragraph elsewhere in the document."""
    start = text.index(heading)
    end = text.index(stop, start)
    return text[start:end]


# ----------------------------------------------------------------------
# Thresholds vs. the prose sitting next to them
# ----------------------------------------------------------------------

class ThresholdMatchesItsOwnComment(unittest.TestCase):
    """`http_req_failed: ['rate<0.001'],  // < 0.1% failure` — the number and
    the comment are two copies of one fact. Mutating one to 'rate<0.01' while
    the comment still read '< 0.1%' passed the whole suite."""

    RULE = re.compile(
        r"rate<(?P<rate>0\.\d+)'\]\s*,?\s*//\s*<?\s*(?P<pct>[\d.]+)\s*%")

    def test_error_rate_thresholds_match_their_percentage_comments(self) -> None:
        checked = 0
        for doc_name, doc in (("k6-patterns.md", K6), ("SKILL.md", SKILL_MD)):
            for m in self.RULE.finditer(doc):
                checked += 1
                rate = float(m.group("rate"))
                pct = float(m.group("pct"))
                self.assertAlmostEqual(
                    rate * 100, pct, places=6,
                    msg=(f"{doc_name}: threshold rate<{rate} means "
                         f"{rate * 100:g}%, but the comment says {pct:g}%"))
        self.assertGreaterEqual(
            checked, 1,
            "no commented error-rate threshold found — the regex drifted from "
            "the docs and this guard is now inert")


# ----------------------------------------------------------------------
# Percentile semantics
# ----------------------------------------------------------------------

class PercentileSemantics(unittest.TestCase):
    """Swapping the p95 and p99 rows, or defining p99 as 'the average of the
    slowest 1%', is the single most damaging error this skill could ship — the
    whole analysis methodology rests on it. Keyword tests cannot see it."""

    ROW = re.compile(r"^\|\s*p(?P<p>[\d.]+)\s*\|(?P<meaning>[^|]*)\|", re.MULTILINE)

    def test_percentile_rows_are_monotonic_and_self_describing(self) -> None:
        rows = [(float(m.group("p")), m.group("meaning"))
                for m in self.ROW.finditer(ANALYSIS)]
        self.assertGreaterEqual(len(rows), 4, "percentile table not found")
        self.assertEqual(sorted(r[0] for r in rows), [r[0] for r in rows],
                         "percentile table rows are out of order")
        for p, meaning in rows:
            nums = [float(n) for n in re.findall(r"(\d+(?:\.\d+)?)\s*%", meaning)]
            if nums:
                self.assertIn(
                    p, nums,
                    f"the p{p:g} row explains itself with {nums} — the row and "
                    "its description disagree (a p95/p99 swap looks exactly "
                    "like this)")

    def test_percentile_is_never_defined_as_an_average(self) -> None:
        """A percentile is an order statistic, not a mean of a tail slice."""
        bad = re.search(
            r"p\d[\d.]*\s*(?:=|is)\s*(?:the\s+)?(?:arithmetic\s+)?(?:average|mean)",
            ANALYSIS + SKILL_MD, re.IGNORECASE)
        self.assertIsNone(
            bad, f"a percentile is defined as an average: {bad.group(0) if bad else ''}")


class WorkedArithmeticHolds(unittest.TestCase):
    """The 'why percentiles' argument stands on one worked mean. If that
    number is wrong the argument is wrong, and no keyword test can tell."""

    CLAIM = re.compile(
        r"If (?P<pa>\d+)%\s+of\s+requests\s+take\s+(?P<va>\d+)\s*(?P<ua>ms|s)\b.*?"
        r"(?P<pb>\d+)%\s+take\s+(?P<vb>\d+)\s*(?P<ub>ms|seconds|s)\b.*?"
        r"average\s+is\s+(?P<avg>\d+)\s*(?P<uavg>ms|s)\b",
        re.DOTALL)

    @staticmethod
    def _ms(value: float, unit: str) -> float:
        return value * (1000.0 if unit.startswith("s") else 1.0)

    def test_stated_average_is_actually_the_weighted_mean(self) -> None:
        m = self.CLAIM.search(ANALYSIS)
        self.assertIsNotNone(
            m, "the worked average example was not found — if it was reworded, "
               "update this guard rather than deleting it")
        a = self._ms(float(m.group("va")), m.group("ua"))
        b = self._ms(float(m.group("vb")), m.group("ub"))
        expected = (float(m.group("pa")) * a + float(m.group("pb")) * b) / 100.0
        stated = self._ms(float(m.group("avg")), m.group("uavg"))
        self.assertAlmostEqual(
            expected, stated, delta=max(1.0, expected * 0.02),
            msg=(f"stated average {stated:g}ms but "
                 f"{m.group('pa')}%×{a:g}ms + {m.group('pb')}%×{b:g}ms "
                 f"= {expected:g}ms"))


# ----------------------------------------------------------------------
# Scorecard: tiers, totals, and the verdict line must agree
# ----------------------------------------------------------------------

class ScorecardInternalConsistency(unittest.TestCase):
    """§8 defines three tiers and §9 prints `X/13 — Critical Y/3, Standard Z/5,
    Hygiene W/5`. Four independent numbers describe one structure; the suite
    checked none of them against each other."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.body = section(SKILL_MD, "## 8 Load Test Scorecard", "## 9 Output Contract")
        cls.tiers = {}          # name -> (declared pass-threshold or None, item count)
        heads = list(re.finditer(
            r"^### (?P<name>Critical|Standard|Hygiene)\s*\((?P<rule>[^)]*)\)\s*$",
            cls.body, re.MULTILINE))
        for i, h in enumerate(heads):
            end = heads[i + 1].start() if i + 1 < len(heads) else len(cls.body)
            chunk = cls.body[h.end():end]
            n_items = len(re.findall(r"^\d+\.\s+\*\*", chunk, re.MULTILINE))
            need = re.search(r">=\s*(\d+)\s+of\s+(\d+)", h.group("rule"))
            cls.tiers[h.group("name")] = {
                "items": n_items,
                "need": int(need.group(1)) if need else None,
                "of": int(need.group(2)) if need else None,
            }

    def test_three_tiers_parsed(self) -> None:
        self.assertEqual({"Critical", "Standard", "Hygiene"}, set(self.tiers),
                         f"scorecard tiers did not parse: {self.tiers}")

    def test_tier_headings_match_their_own_item_counts(self) -> None:
        for name, t in self.tiers.items():
            if t["of"] is not None:
                self.assertEqual(
                    t["of"], t["items"],
                    f"{name} heading says 'of {t['of']}' but the tier lists "
                    f"{t['items']} items")

    def test_items_are_numbered_consecutively_across_tiers(self) -> None:
        nums = [int(n) for n in re.findall(r"^(\d+)\.\s+\*\*", self.body, re.MULTILINE)]
        self.assertEqual(list(range(1, len(nums) + 1)), nums,
                         "scorecard item numbering is not 1..N consecutive")

    def test_tier_sizes_sum_to_the_scorecard_total(self) -> None:
        total = sum(t["items"] for t in self.tiers.values())
        printed = re.search(r"`X/(\d+) — Critical Y/(\d+), Standard Z/(\d+), "
                            r"Hygiene W/(\d+)", SKILL_MD)
        self.assertIsNotNone(printed, "§9 scorecard line not found")
        stated_total, crit, std, hyg = (int(g) for g in printed.groups())
        self.assertEqual(total, stated_total,
                         f"tiers hold {total} items but §9 prints X/{stated_total}")
        self.assertEqual(crit + std + hyg, stated_total,
                         f"§9 tier denominators {crit}+{std}+{hyg} != {stated_total}")
        for name, denom in (("Critical", crit), ("Standard", std), ("Hygiene", hyg)):
            self.assertEqual(self.tiers[name]["items"], denom,
                             f"§9 prints {name} /{denom} but §8 lists "
                             f"{self.tiers[name]['items']} items")

    def test_verdict_line_matches_the_tier_headings(self) -> None:
        v = re.search(r"\*\*Verdict\*\*:\s*Critical (\d+)/(\d+) AND Standard "
                      r">=\s*(\d+)/(\d+) AND Hygiene >=\s*(\d+)/(\d+)", SKILL_MD)
        self.assertIsNotNone(v, "§8 verdict line not found")
        c_need, c_of, s_need, s_of, h_need, h_of = (int(g) for g in v.groups())
        self.assertEqual(self.tiers["Critical"]["items"], c_of)
        self.assertEqual(c_need, c_of, "Critical is 'must all pass'")
        self.assertEqual(
            (self.tiers["Standard"]["need"], self.tiers["Standard"]["of"]),
            (s_need, s_of),
            "the Standard heading and the Verdict line disagree on the "
            "pass threshold")
        self.assertEqual(
            (self.tiers["Hygiene"]["need"], self.tiers["Hygiene"]["of"]),
            (h_need, h_of),
            "the Hygiene heading and the Verdict line disagree on the "
            "pass threshold")


# ----------------------------------------------------------------------
# Durations: a load test measured in seconds is the thing this skill forbids
# ----------------------------------------------------------------------

class DurationsAreOnTheRightScale(unittest.TestCase):
    """AE-5 is an entire anti-example about 30 seconds being too short, yet
    rewriting the scorecard's floors to '>= 1 sec smoke, >= 3 sec load' passed
    every test."""

    def test_steady_state_floors_are_minutes_not_seconds(self) -> None:
        body = section(SKILL_MD, "## 8 Load Test Scorecard", "## 9 Output Contract")
        m = re.search(r"Steady state duration sufficient\*\*\s*—\s*(?P<rule>[^\n]*)", body)
        self.assertIsNotNone(m, "scorecard steady-state item not found")
        rule = m.group("rule")
        units = re.findall(r">=\s*\d+\s*(min|minute|minutes|sec|second|seconds|s)\b", rule)
        self.assertTrue(units, f"no duration units in: {rule!r}")
        for unit in units:
            self.assertTrue(
                unit.startswith("min"),
                f"steady-state floor given in {unit!r}: {rule!r} — this skill's "
                "own AE-5 says a 30-SECOND run is a smoke test at best")

    def test_soak_is_tens_of_minutes(self) -> None:
        m = re.search(r"\*\*Soak\*\*[^\n|]*\|[^|]*?(\d+)-(\d+)\+?\s*minutes", SKILL_MD)
        self.assertIsNotNone(m, "soak duration not found in §6.2")
        low, high = int(m.group(1)), int(m.group(2))
        self.assertGreaterEqual(low, 15, "soak floor below 15 min cannot detect leaks")
        self.assertGreater(high, low)


# ----------------------------------------------------------------------
# vegeta: no executable here, so validate against the real CLI surface
# ----------------------------------------------------------------------

class VegetaCliSurface(unittest.TestCase):
    """`vegeta-patterns.md` has 16 fenced blocks and zero validation of any
    kind — vegeta is not installed, and nothing would invoke it if it were.
    Replacing `-rate=` with the non-existent `-ratelimit=` in nine places
    passed the suite. An allowlist is not execution, but it does bind each
    flag to a real CLI surface instead of to nothing at all."""

    SUBCOMMANDS = {"attack", "report", "plot", "encode"}
    # flags accepted by the subcommands this reference actually uses
    FLAGS = {
        "attack": {"-rate", "-duration", "-targets", "-body", "-header", "-output",
                   "-timeout", "-workers", "-max-workers", "-connections", "-keepalive",
                   "-insecure", "-lazy", "-name", "-format", "-http2", "-max-body",
                   "-redirects", "-root-certs", "-cert", "-key", "-laddr", "-unix-socket",
                   "-chunked", "-dns-ttl", "-proxy-header", "-resolvers", "-session-tickets"},
        "report": {"-type", "-output", "-every", "-buckets"},
        "plot":   {"-title", "-threshold", "-output"},
        "encode": {"-to", "-output"},
    }
    INVOCATION = re.compile(r"vegeta\s+(?P<sub>[a-z]+)(?![-\w])(?P<rest>[^\n|]*)")

    def test_only_real_subcommands_are_invoked(self) -> None:
        bad = []
        for m in self.INVOCATION.finditer(VEGETA):
            sub = m.group("sub")
            # prose like "vegeta models traffic arrival" is not an invocation
            if not m.group("rest").lstrip().startswith("-") and sub not in self.SUBCOMMANDS:
                continue
            if sub not in self.SUBCOMMANDS:
                bad.append(f"vegeta {sub}")
        self.assertFalse(bad, f"unknown vegeta subcommands: {sorted(set(bad))}")

    def test_only_real_flags_are_used(self) -> None:
        bad = []
        checked = 0
        for m in self.INVOCATION.finditer(VEGETA):
            sub = m.group("sub")
            if sub not in self.SUBCOMMANDS:
                continue
            for flag in re.findall(r"(?<!\w)(-[a-z][a-z0-9-]*)", m.group("rest")):
                checked += 1
                if flag not in self.FLAGS[sub]:
                    bad.append(f"vegeta {sub} {flag}")
        self.assertFalse(bad, f"flags not accepted by vegeta: {sorted(set(bad))}")
        self.assertGreaterEqual(
            checked, 10,
            "fewer vegeta flags found than expected — the regex drifted and "
            "this guard is now inert")


if __name__ == "__main__":
    unittest.main()


# ----------------------------------------------------------------------
# §9 output contract: nine sections, each with an actual body
# ----------------------------------------------------------------------

class OutputContractSections(unittest.TestCase):
    """`assert "9.6" in SKILL_MD` plus `assert "Results Analysis" in SKILL_MD`
    both survive deleting §9.6's entire body, because the heading and the
    number remain. A contract section reduced to a heading promises nothing.
    """

    EXPECTED = {
        1: "Context Summary",
        2: "Mode & Depth",
        3: "SLO Definition",
        4: "Scenario Design",
        5: "Test Script or Script Review",
        6: "Results Analysis (Analyze mode)",
        7: "Bottleneck Assessment",
        8: "Recommendations",
        9: "Uncovered Risks",
    }

    @classmethod
    def setUpClass(cls) -> None:
        body = section(SKILL_MD, "## 9 Output Contract", "## 10 Reference Loading")
        heads = list(re.finditer(r"^###\s*9\.(?P<n>\d)\s+(?P<title>[^\n]+)$",
                                 body, re.MULTILINE))
        cls.sections = {}
        for i, h in enumerate(heads):
            end = heads[i + 1].start() if i + 1 < len(heads) else len(body)
            cls.sections[int(h.group("n"))] = (h.group("title").strip(),
                                               body[h.end():end].strip())

    def test_all_nine_sections_present_with_expected_titles(self) -> None:
        self.assertEqual(sorted(self.EXPECTED), sorted(self.sections),
                         f"output-contract sections found: {sorted(self.sections)}")
        for n, title in self.EXPECTED.items():
            self.assertEqual(title, self.sections[n][0],
                             f"§9.{n} is titled {self.sections[n][0]!r}")

    def test_every_section_has_a_substantive_body(self) -> None:
        for n, (title, body) in sorted(self.sections.items()):
            words = len(body.split())
            self.assertGreaterEqual(
                words, 8,
                f"§9.{n} {title} has a {words}-word body — a heading is not a "
                "contract section")

    def test_results_analysis_still_demands_percentiles(self) -> None:
        _, body = self.sections[6]
        for needle in ("Percentile table", "p99", "SLO pass/fail"):
            self.assertIn(needle, body,
                          f"§9.6 no longer requires {needle!r} in its own body")

    def test_uncovered_risks_is_still_mandatory(self) -> None:
        _, body = self.sections[9]
        self.assertIn("Mandatory", body)
        self.assertIn("never empty", body.lower())
