"""Adversarial coverage for the claim-support axis.

The rest of the suite proves the tool obeys its own rules. These tests ask a
different question: does the second verdict actually catch a claim its own
excerpt does not support, and does it leave correct findings alone?

Every threshold and every case lives in `claim_support_corpus.json` as data, so
a weakened screen shows up as a failing count rather than as a docstring that
still claims coverage.
"""

import importlib.util
import json
import sys
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "deep_research.py"
CORPUS_PATH = Path(__file__).resolve().parent / "claim_support_corpus.json"

spec = importlib.util.spec_from_file_location("deep_research_claim_support", SCRIPT)
deep_research = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = deep_research
spec.loader.exec_module(deep_research)

sys.path.insert(0, str(SCRIPT.parent))
from deep_research_lib import claim_support  # noqa: E402

CORPUS = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
CASES = CORPUS["cases"]
THRESHOLDS = CORPUS["thresholds"]


def cases_labelled(label: str) -> list:
    return [c for c in CASES if c["label"] == label]


class PolarityScreenCorpus(unittest.TestCase):
    def test_corpus_covers_all_three_classes(self) -> None:
        """A corpus missing a class would let that obligation go unmeasured."""
        labels = {c["label"] for c in CASES}
        self.assertEqual({"conflict", "supported", "lexically-opposed"}, labels)
        for label in labels:
            self.assertGreaterEqual(len(cases_labelled(label)), 3, label)

    def test_every_case_id_is_unique(self) -> None:
        ids = [c["id"] for c in CASES]
        self.assertEqual(len(ids), len(set(ids)))

    def test_conflicting_claims_are_flagged(self) -> None:
        """A claim that opposes its own excerpt must never pass silently."""
        conflict_cases = cases_labelled("conflict")
        missed = [
            c["id"]
            for c in conflict_cases
            if not claim_support.polarity_conflict(c["claim"], c["excerpt"])
        ]
        recall = (len(conflict_cases) - len(missed)) / len(conflict_cases)
        self.assertGreaterEqual(
            recall,
            THRESHOLDS["min_conflict_recall"],
            f"recall {recall:.2f} below floor; missed {missed}",
        )

    def test_correct_findings_are_not_flagged(self) -> None:
        """A false conflict costs a real author an attestation and a level."""
        flagged = [
            (c["id"], claim_support.polarity_conflict(c["claim"], c["excerpt"]))
            for c in cases_labelled("supported")
            if claim_support.polarity_conflict(c["claim"], c["excerpt"])
        ]
        self.assertLessEqual(
            len(flagged),
            THRESHOLDS["max_false_conflicts"],
            f"false conflicts on correct findings: {flagged}",
        )

    def test_known_blind_spot_stays_documented(self) -> None:
        """The lexically-opposed class records where the method actually ends.

        If one of these stops being flagged the screen got better, which is
        good news that still has to be reclassified deliberately rather than
        silently absorbed.
        """
        for case in cases_labelled("lexically-opposed"):
            self.assertTrue(
                claim_support.polarity_conflict(case["claim"], case["excerpt"]),
                f"{case['id']} no longer trips the screen; reclassify it",
            )

    def test_numeric_drift_cases(self) -> None:
        for case in CORPUS["numeric_cases"]:
            self.assertEqual(
                case["expect_unquoted"],
                claim_support.numeric_drift(case["claim"], case["excerpts"]),
                case["id"],
            )


class ScreenMutations(unittest.TestCase):
    """Each mechanism must be individually load-bearing.

    A screen made of several parts can pass its corpus while one part does
    nothing. Removing each part in turn must break something.
    """

    def test_removing_negators_breaks_conflict_detection(self) -> None:
        original = claim_support.NEGATORS
        try:
            claim_support.NEGATORS = frozenset()
            still_flagged = [
                c["id"]
                for c in cases_labelled("conflict")
                if claim_support.polarity_conflict(c["claim"], c["excerpt"])
            ]
            self.assertEqual([], still_flagged, "negator set is not load-bearing")
        finally:
            claim_support.NEGATORS = original

    def test_clause_scoping_is_load_bearing(self) -> None:
        """Whole-text negation must produce a false conflict on real excerpts.

        Extracted page content runs to several sentences. Judging polarity over
        the whole excerpt lets an unrelated negative sentence contradict a
        claim the excerpt actually supports.
        """
        original = claim_support._clauses
        try:
            claim_support._clauses = lambda text: (
                [(
                    claim_support._tokens(text),
                    any(w in claim_support.NEGATORS
                        for w in claim_support._tokens(text)),
                )]
                if claim_support._tokens(text)
                else []
            )
            regressions = [
                c["id"]
                for c in cases_labelled("supported")
                if claim_support.polarity_conflict(c["claim"], c["excerpt"])
            ]
            self.assertTrue(
                regressions,
                "clause scoping is not load-bearing; simplify it away instead",
            )
        finally:
            claim_support._clauses = original

    def test_searching_every_anchor_length_is_load_bearing(self) -> None:
        """Stopping at the longest shared anchor must miss a real conflict.

        In `conflict-multi-sentence` the longest shared phrase sits in the
        sentence that agrees with the claim, so a longest-anchor-only search
        reports alignment and never reaches the sentence that contradicts it.
        """
        case = next(c for c in CASES if c["id"] == "conflict-multi-sentence")
        self.assertTrue(
            claim_support.polarity_conflict(case["claim"], case["excerpt"])
        )

        def longest_anchor_only(claim: str, excerpt: str):
            claim_clauses = claim_support._clauses(claim)
            excerpt_clauses = claim_support._clauses(excerpt)
            claim_tokens = claim_support._flatten(claim_clauses)
            excerpt_tokens = claim_support._flatten(excerpt_clauses)
            largest = min(len(claim_tokens), len(excerpt_tokens))
            for size in range(largest, claim_support.MIN_ANCHOR_TOKENS - 1, -1):
                ci = claim_support._content_ngrams(claim_tokens, size)
                ei = claim_support._content_ngrams(excerpt_tokens, size)
                shared = set(ci) & set(ei)
                if not shared:
                    continue
                for anchor in sorted(shared):
                    if all(
                        claim_support._negated_at(claim_clauses, i) for i in ci[anchor]
                    ) != all(
                        claim_support._negated_at(excerpt_clauses, i) for i in ei[anchor]
                    ):
                        return " ".join(anchor)
                return None
            return None

        self.assertIsNone(longest_anchor_only(case["claim"], case["excerpt"]))

    def test_before_window_scoping_would_regress(self) -> None:
        """The original before-the-anchor window produced a false conflict.

        Kept as an executable record of why negation scope is measured over the
        whole clause rather than a fixed span of preceding tokens.
        """
        case = next(c for c in CASES if c["id"] == "supported-crypto-rand")
        self.assertIsNone(
            claim_support.polarity_conflict(case["claim"], case["excerpt"])
        )

        original = claim_support._clauses
        try:
            def before_window(text: str):
                tokens = claim_support._tokens(text)
                return [
                    (
                        [token],
                        any(
                            w in claim_support.NEGATORS
                            for w in tokens[max(0, i - 3):i]
                        ),
                    )
                    for i, token in enumerate(tokens)
                ]

            claim_support._clauses = before_window
            self.assertTrue(
                claim_support.polarity_conflict(case["claim"], case["excerpt"]),
                "before-window scoping no longer regresses; drop this guard",
            )
        finally:
            claim_support._clauses = original

    def test_hyphen_joining_is_load_bearing(self) -> None:
        """Splitting `non-idempotent` re-creates a known false positive."""
        claim = "Retries apply only to idempotent methods."
        excerpt = "Do not retry non-idempotent methods such as POST."
        self.assertIsNone(claim_support.polarity_conflict(claim, excerpt))
        self.assertIn("nonidempotent", claim_support._tokens(excerpt))


class SupportVerdictStateMachine(unittest.TestCase):
    CLAIM = {
        "title": "Log retention",
        "analysis": "The service permanently retains all request logs.",
    }
    EVIDENCE = [
        {"kind": "web", "excerpt": "The service does not retain request logs."}
    ]

    def test_unattested_contradiction_is_not_publishable(self) -> None:
        review = claim_support.review_claim_support(self.CLAIM, self.EVIDENCE)
        self.assertEqual("contradicted", review["state"])
        self.assertFalse(review["publishable"])
        self.assertFalse(review["high_eligible"])

    def test_attested_contradiction_is_publishable_but_never_high(self) -> None:
        finding = dict(
            self.CLAIM,
            support_review={
                "stance": "supports",
                "rationale": "a later paragraph on the same page states the opposite",
            },
        )
        review = claim_support.review_claim_support(finding, self.EVIDENCE)
        self.assertEqual("disputed", review["state"])
        self.assertTrue(review["publishable"])
        self.assertFalse(review["high_eligible"])

    def test_a_bare_override_without_reasoning_does_not_count(self) -> None:
        finding = dict(self.CLAIM, support_review={"stance": "supports", "rationale": "ok"})
        review = claim_support.review_claim_support(finding, self.EVIDENCE)
        self.assertEqual("contradicted", review["state"])

    def test_missing_review_is_unreviewed_not_approved(self) -> None:
        finding = {"title": "x", "analysis": "The API returns 404 for missing users."}
        evidence = [{"kind": "web", "excerpt": "The API returns 404 for missing users."}]
        review = claim_support.review_claim_support(finding, evidence)
        self.assertEqual("unreviewed", review["state"])
        self.assertTrue(review["publishable"])
        self.assertFalse(review["high_eligible"])

    def test_malformed_review_block_cannot_approve(self) -> None:
        for bad in ("supports", ["supports"], {"stance": "yes"}, {}, None):
            finding = {
                "title": "x",
                "analysis": "The API returns 404 for missing users.",
                "support_review": bad,
            }
            evidence = [
                {"kind": "web", "excerpt": "The API returns 404 for missing users."}
            ]
            review = claim_support.review_claim_support(finding, evidence)
            self.assertFalse(review["high_eligible"], repr(bad))

    def test_author_declared_contradiction_blocks_the_finding(self) -> None:
        finding = dict(
            self.CLAIM,
            analysis="The API returns 404 for missing users.",
            support_review={"stance": "contradicts", "rationale": "it says 410"},
        )
        evidence = [{"kind": "web", "excerpt": "The API returns 410 for missing users."}]
        review = claim_support.review_claim_support(finding, evidence)
        self.assertEqual("contradicted", review["state"])
        self.assertFalse(review["publishable"])

    def test_unquoted_number_qualifies_but_does_not_block(self) -> None:
        finding = {
            "title": "Shutdown deadline",
            "analysis": "The default shutdown deadline is 30 seconds.",
            "support_review": {"stance": "supports", "rationale": "stated on the page"},
        }
        evidence = [
            {"kind": "web", "excerpt": "The server waits for connections to drain."}
        ]
        review = claim_support.review_claim_support(finding, evidence)
        self.assertEqual("qualified", review["state"])
        self.assertTrue(review["publishable"])
        self.assertFalse(review["high_eligible"])

    def test_derived_numbers_flag_clears_the_numeric_screen(self) -> None:
        finding = {
            "title": "Speedup",
            "analysis": "The new path is 3 times faster.",
            "support_review": {
                "stance": "supports",
                "rationale": "computed from the two latencies quoted below",
                "derived_numbers": True,
            },
        }
        evidence = [{"kind": "web", "excerpt": "Latency fell from 90ms to 30ms."}]
        review = claim_support.review_claim_support(finding, evidence)
        self.assertEqual("attested", review["state"])
        self.assertTrue(review["high_eligible"])


class EndToEndThroughTheValidator(unittest.TestCase):
    """The axis must reach the real bundle validator, not just the module."""

    URL = "https://www.nist.gov/policy"

    def _bundle(self, finding: dict) -> dict:
        source = deep_research.SearchResult(
            query="log retention",
            title="Policy",
            url=self.URL,
            normalized_url=self.URL,
            domain="nist.gov",
            source_type="government",
        )
        content = deep_research.ContentResult(
            url=self.URL,
            final_url=self.URL,
            title="Policy",
            content="The service does not retain request logs.",
            word_count=8,
            error="",
            http_status=200,
            fetched_at="2026-09-08T00:00:00+00:00",
            capture_method="validator-live-fetch",
            live_verified=True,
        )
        return deep_research.validate_research_bundle(
            research_kind="web",
            results=[source],
            contents=[content],
            code_evidence={},
            findings={"findings": [finding]},
        )

    def test_inverted_claim_cannot_reach_full_and_high(self) -> None:
        """The reference case from the external review.

        Excerpt containment passed, so the run reported Full, High and no
        issue for a claim that was the exact negation of its own quote.
        """
        summary = self._bundle({
            "title": "Log retention",
            "claim_type": "single_fact",
            "confidence": "high",
            "analysis": "The service permanently retains all request logs.",
            "evidence": [{
                "kind": "web",
                "url": self.URL,
                "excerpt": "The service does not retain request logs.",
            }],
        })
        self.assertNotEqual("Full", summary["degradation"])
        self.assertFalse(summary["findings"][0]["usable"])
        self.assertNotEqual("high", summary["findings"][0]["effective_confidence"])
        codes = {issue["code"] for issue in summary["issues"]}
        self.assertIn("claim_not_supported_by_excerpt", codes)
        self.assertEqual("conflicted", summary["claim_support"]["state"])

    def test_faithful_claim_without_review_is_capped_below_high(self) -> None:
        summary = self._bundle({
            "title": "Log retention",
            "claim_type": "single_fact",
            "confidence": "high",
            "analysis": "The service does not retain request logs.",
            "evidence": [{
                "kind": "web",
                "url": self.URL,
                "excerpt": "The service does not retain request logs.",
            }],
        })
        self.assertTrue(summary["findings"][0]["usable"])
        self.assertEqual("medium", summary["findings"][0]["effective_confidence"])
        self.assertEqual(
            "partially-reviewed", summary["claim_support"]["state"]
        )

    def test_faithful_and_reviewed_claim_reaches_high(self) -> None:
        summary = self._bundle({
            "title": "Log retention",
            "claim_type": "single_fact",
            "confidence": "high",
            "analysis": "The service does not retain request logs.",
            "support_review": {
                "stance": "supports",
                "rationale": "the excerpt is a direct restatement of the claim",
            },
            "evidence": [{
                "kind": "web",
                "url": self.URL,
                "excerpt": "The service does not retain request logs.",
            }],
        })
        self.assertEqual("Full", summary["degradation"])
        self.assertEqual("high", summary["findings"][0]["effective_confidence"])
        self.assertEqual("reviewed", summary["claim_support"]["state"])

    def test_report_states_both_verdicts_separately(self) -> None:
        """A reader must never read citation integrity as claim support."""
        summary = self._bundle({
            "title": "Log retention",
            "claim_type": "single_fact",
            "confidence": "high",
            "analysis": "The service does not retain request logs.",
            "evidence": [{
                "kind": "web",
                "url": self.URL,
                "excerpt": "The service does not retain request logs.",
            }],
        })
        report = deep_research.generate_report(
            "Does the service retain logs?",
            {"findings": []},
            [
                deep_research.SearchResult(
                    query="q", title="Policy", url=self.URL,
                    normalized_url=self.URL, domain="nist.gov",
                    source_type="government",
                )
            ],
            "quick",
            validation=summary,
            research_kind="web",
        )
        self.assertIn("Citation integrity", report)
        self.assertIn("Claim support", report)
        self.assertIn("not machine-verified", report)


class AuthorityRegistryContract(unittest.TestCase):
    """The registry must add reach without reopening the self-declared hole."""

    def test_registry_file_is_loadable_and_every_entry_is_dated(self) -> None:
        sys.path.insert(0, str(SCRIPT.parent))
        from deep_research_lib import authority

        entries = authority.load_registry()
        self.assertGreaterEqual(len(entries), 20)
        for entry in entries:
            self.assertTrue(entry["domains"], entry)
            self.assertTrue(entry["basis"], entry)
            self.assertRegex(entry["verified_on"], r"^\d{4}-\d{2}-\d{2}$")

    def test_unreadable_registry_fails_closed(self) -> None:
        from deep_research_lib import authority

        authority.load_registry.cache_clear()
        try:
            self.assertEqual([], authority.load_registry("/nonexistent/registry.json"))
        finally:
            authority.load_registry.cache_clear()

    def test_confidence_gate_fails_closed_without_a_support_verdict(self) -> None:
        """A finding carrying no claim-support verdict must not reach High.

        `assess_finding` always attaches one, so this guards the gate itself
        against a future caller that forgets to run the review.
        """
        unit = {
            "kind": "web",
            "primary": True,
            "vendor_self": False,
            "source_tier": "T1",
            "live_verified": True,
        }
        effective, _ = deep_research._effective_confidence(
            {"confidence": "high", "claim_type": "single_fact"},
            [unit],
            ["web:nist.gov"],
        )
        self.assertEqual("medium", effective)

    def test_project_domain_is_not_an_independent_primary_source(self) -> None:
        """Vendor-self docs are authoritative about the vendor, not neutral."""
        unit = {
            "kind": "web",
            "primary": True,
            "vendor_self": True,
            "source_tier": "T1",
            "live_verified": True,
        }
        effective, reasons = deep_research._effective_confidence(
            {"confidence": "high", "claim_type": "analysis", "claim_support":
                {"high_eligible": True}},
            [unit, dict(unit, url="https://go.dev/b")],
            ["web:go.dev", "web:other.example"],
        )
        self.assertEqual("medium", effective)
        self.assertTrue(any("own" in r for r in reasons))


class RelevanceFloorOnWebExcerpts(unittest.TestCase):
    """"No signal" from the screens must not be scored as "no objection".

    `polarity_conflict` returns None both when the texts agree and when it
    cannot align them. Treating those identically meant containment alone
    carried the verdict: the excerpt "the" is present on nearly every page, so
    it proved the fetch succeeded and nothing more.
    """

    @staticmethod
    def _finding(claim: str) -> dict:
        return {
            "title": claim,
            "analysis": "",
            "support_review": {
                "stance": "supports",
                "rationale": "the cited excerpt supports this claim as written",
            },
        }

    def test_thin_excerpt_cannot_reach_attested(self) -> None:
        review = claim_support.review_claim_support(
            self._finding("Go generics are production ready for all workloads."),
            [{"kind": "web", "excerpt": "the"}],
        )
        self.assertEqual("qualified", review["state"])
        self.assertFalse(review["high_eligible"])
        self.assertEqual(1, review["screens"]["thin_web_excerpts"])

    def test_excerpt_unrelated_to_the_claim_cannot_reach_attested(self) -> None:
        review = claim_support.review_claim_support(
            self._finding("Go generics are production ready for all workloads."),
            [{"kind": "web", "excerpt": "Shutdown waits for in-flight requests to drain."}],
        )
        self.assertEqual("qualified", review["state"])
        self.assertEqual("none", review["screens"]["corroboration"])

    def test_a_faithful_excerpt_is_still_attested(self) -> None:
        """Positive control: the floor must not reject correct citations."""
        review = claim_support.review_claim_support(
            self._finding("GOMAXPROCS defaults to the number of visible CPUs."),
            [{
                "kind": "web",
                "excerpt": "The default value of GOMAXPROCS is the number of CPUs visible to the program.",
            }],
        )
        self.assertEqual("attested", review["state"])
        self.assertEqual("lexical", review["screens"]["corroboration"])

    def test_repository_evidence_is_corroborated_structurally_not_lexically(self) -> None:
        """Code shares no prose phrase with the sentence built on it.

        Applying the Web floor to repository evidence would reject every
        legitimate code finding, so the state stays attested — but the
        corroboration label must say `structural`, so the report cannot imply
        a lexical screen examined it.
        """
        review = claim_support.review_claim_support(
            self._finding("The lookup entry point is a module-level function."),
            [{"kind": "code", "excerpt": "def lookup(hostname: str) -> Optional[Dict[str, Any]]:"}],
        )
        self.assertEqual("attested", review["state"])
        self.assertEqual("structural", review["screens"]["corroboration"])

    def test_anchor_threshold_does_not_false_downgrade_the_corpus(self) -> None:
        """The one-token threshold is a measured choice; keep it measured.

        A shared 2-gram false-downgraded 5 of the 18 `supported` cases (28%).
        This asserts the shipped threshold stays at zero on that same corpus,
        so a future tightening cannot be made quietly.
        """
        supported = [c for c in CORPUS["cases"] if c["label"] == "supported"]
        self.assertGreaterEqual(len(supported), 3)
        false_downgrades = [
            case
            for case in supported
            if not claim_support.content_anchor(case["claim"], case["excerpt"])
        ]
        self.assertEqual(
            [],
            [c["claim"] for c in false_downgrades],
            "relevance floor rejects correct findings; re-measure before tightening",
        )



if __name__ == "__main__":
    unittest.main()
