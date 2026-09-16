"""Persistent budget, source ceiling, and multilingual planning behavior."""

import importlib.util
import json
import multiprocessing
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "deep_research.py"
spec = importlib.util.spec_from_file_location("deep_research_session_tests", SCRIPT)
deep_research = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = deep_research
spec.loader.exec_module(deep_research)


def reserve_one_worker(session: str, queue: object) -> None:
    try:
        deep_research.reserve_session_budget(
            Path(session),
            "retrieval_calls",
            1,
            allow_partial=False,
        )
        queue.put("reserved")
    except deep_research.BudgetExceededError:
        queue.put("exhausted")
    except Exception as exc:  # pragma: no cover - diagnostic branch
        queue.put(f"error:{type(exc).__name__}:{exc}")


def run_cli(*argv: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *argv],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


class TestPersistentSessionBudget(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.session = Path(self._tmp.name) / "session.json"
        plan = deep_research.plan_research(
            "Perform a comprehensive architecture decision.",
            explicit_mode="deep",
        )
        deep_research.initialize_session(self.session, plan)

    def test_two_invocations_cannot_exceed_cumulative_retrieval_limit(self) -> None:
        first = deep_research.reserve_session_budget(
            self.session,
            "retrieval_calls",
            50,
            allow_partial=False,
        )
        self.assertEqual(50, first["reserved"])
        with self.assertRaises(deep_research.BudgetExceededError):
            deep_research.reserve_session_budget(
                self.session,
                "retrieval_calls",
                1,
                allow_partial=False,
            )

    def test_content_reservation_uses_only_remaining_allowance(self) -> None:
        quick_session = Path(self._tmp.name) / "quick.json"
        deep_research.initialize_session(
            quick_session,
            deep_research.plan_research("Quick check.", explicit_mode="quick"),
        )
        reservation = deep_research.reserve_session_budget(
            quick_session,
            "content_extractions",
            7,
            allow_partial=True,
        )
        self.assertEqual(5, reservation["reserved"])
        self.assertTrue(reservation["exhausted"])
        state = deep_research.load_session(quick_session)
        self.assertEqual(5, state["usage"]["content_extractions"])

    def test_parser_requires_session_for_budgeted_commands(self) -> None:
        parser = deep_research.build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(
                ["retrieve", "--query", "q", "--output", "/tmp/results.json"]
            )
        with self.assertRaises(SystemExit):
            parser.parse_args(
                [
                    "fetch-content",
                    "--url",
                    "https://example.com",
                    "--output",
                    "/tmp/content.json",
                ]
            )
        with self.assertRaises(SystemExit):
            parser.parse_args(
                [
                    "report",
                    "--question",
                    "q",
                    "--research-kind",
                    "web",
                    "--results",
                    "results.json",
                    "--content",
                    "content.json",
                    "--findings",
                    "findings.json",
                    "--output",
                    "/tmp/report.md",
                ]
            )

    def test_session_rejects_tampered_budget_and_negative_usage(self) -> None:
        original = json.loads(self.session.read_text(encoding="utf-8"))
        state = json.loads(json.dumps(original))
        state["budget"]["retrieval_max"] = 500
        self.session.write_text(json.dumps(state), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "not canonical"):
            deep_research.load_session(self.session)

        self.session.write_text(json.dumps(original), encoding="utf-8")
        state = json.loads(self.session.read_text(encoding="utf-8"))
        state["usage"]["retrieval_calls"] = -1
        self.session.write_text(json.dumps(state), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "invalid session usage"):
            deep_research.load_session(self.session)

    def test_plan_refuses_to_overwrite_existing_session(self) -> None:
        plan = deep_research.plan_research(
            "Perform a comprehensive architecture decision.",
            explicit_mode="deep",
        )
        with self.assertRaises(FileExistsError):
            deep_research.initialize_session(self.session, plan)

    @unittest.skipUnless(
        "fork" in multiprocessing.get_all_start_methods(),
        "the subprocess contention test requires fork",
    )
    def test_cross_process_lock_enforces_one_cumulative_ceiling(self) -> None:
        quick_session = Path(self._tmp.name) / "contended.json"
        deep_research.initialize_session(
            quick_session,
            deep_research.plan_research("Quick check.", explicit_mode="quick"),
        )
        context = multiprocessing.get_context("fork")
        queue = context.Queue()
        workers = [
            context.Process(
                target=reserve_one_worker,
                args=(str(quick_session), queue),
            )
            for _ in range(20)
        ]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(30)
            self.assertEqual(0, worker.exitcode)
        outcomes = [queue.get(timeout=5) for _ in workers]
        self.assertEqual(10, outcomes.count("reserved"), outcomes)
        self.assertEqual(10, outcomes.count("exhausted"), outcomes)
        self.assertFalse(
            [outcome for outcome in outcomes if outcome.startswith("error:")],
            outcomes,
        )
        state = deep_research.load_session(quick_session)
        self.assertEqual(10, state["usage"]["retrieval_calls"])

    def test_external_tool_budget_can_be_reserved_through_cli(self) -> None:
        receipt = Path(self._tmp.name) / "reservation.json"
        proc = run_cli(
            "reserve-budget",
            "--session",
            str(self.session),
            "--budget",
            "retrieval_calls",
            "--count",
            "3",
            "--output",
            str(receipt),
        )
        self.assertEqual(0, proc.returncode, proc.stderr)
        reservation = json.loads(receipt.read_text(encoding="utf-8"))
        self.assertEqual(3, reservation["reserved"])
        self.assertEqual(3, deep_research.load_session(self.session)["usage"]["retrieval_calls"])


def web_source(index: int) -> object:
    url = f"https://source{index}.example/fact"
    return deep_research.SearchResult(
        query="q",
        title=f"Source {index}",
        url=url,
        normalized_url=url,
        domain=f"source{index}.example",
        source_type="official",
        source_tier="T1",
        classification_basis="explicit",
        sponsorship="none",
        methodology="primary documentation",
    )


def web_content(index: int) -> object:
    text = f"Verified fact number {index}."
    return deep_research.ContentResult(
        url=f"https://source{index}.example/fact",
        title=f"Source {index}",
        content=text,
        word_count=len(text.split()),
    )


def finding(index: int) -> dict:
    return {
        "title": f"Fact {index}",
        "claim_type": "single_fact",
        "confidence": "high",
        "analysis": f"Verified fact number {index}.",
        "evidence": [
            {
                "kind": "web",
                "url": f"https://source{index}.example/fact",
                "excerpt": f"Verified fact number {index}.",
            }
        ],
    }


class TestReportSourceBudget(unittest.TestCase):
    def test_sources_only_lists_verified_cited_inputs(self) -> None:
        results = [web_source(i) for i in range(1, 10)]
        contents = [web_content(1)]
        findings = {"findings": [finding(1)]}
        validation = deep_research.validate_research_bundle(
            research_kind="web",
            results=results,
            contents=contents,
            code_evidence={},
            findings=findings,
        )
        report = deep_research.generate_report(
            question="What is fact one?",
            findings=findings,
            results=results,
            depth="quick",
            contents=contents,
            validation=validation,
            research_kind="web",
        )
        sources = report.split("## 8) Sources", 1)[1].split(
            "## 9) Gaps & Limitations", 1
        )[0]
        self.assertIn("Source 1", sources)
        self.assertNotIn("Source 2", sources)
        self.assertEqual(1, sum(1 for line in sources.splitlines() if line.startswith("[")))

    def test_quick_report_rejects_nine_verified_cited_sources(self) -> None:
        results = [web_source(i) for i in range(1, 10)]
        contents = [web_content(i) for i in range(1, 10)]
        findings = {"findings": [finding(i) for i in range(1, 10)]}
        validation = deep_research.validate_research_bundle(
            research_kind="web",
            results=results,
            contents=contents,
            code_evidence={},
            findings=findings,
        )
        with self.assertRaises(deep_research.ReportSourceBudgetError):
            deep_research.generate_report(
                question="What are the nine facts?",
                findings=findings,
                results=results,
                depth="quick",
                contents=contents,
                validation=validation,
                research_kind="web",
            )


class TestMultilingualPlanner(unittest.TestCase):
    def test_chinese_repository_request_selects_codebase(self) -> None:
        plan = deep_research.plan_research("这个仓库里的认证是怎么实现的？")
        self.assertEqual("codebase", plan["research_kind"])

    def test_chinese_cloud_security_comparison_selects_deep(self) -> None:
        plan = deep_research.plan_research("请深入比较 AWS、Azure 和 GCP 的安全性")
        self.assertEqual("web", plan["research_kind"])
        self.assertEqual("deep", plan["mode"])


class LedgerSchemaEvolution(unittest.TestCase):
    """A new budget line must not strand a session from an older version."""

    LEGACY = {
        "request": "x",
        "research_kind": "web",
        "mode": "quick",
        "budget": {
            "retrieval_min": 5,
            "retrieval_max": 10,
            "content_max": 5,
            "report_sources_max": 8,
        },
        "schema": "deep-research/session-v1",
        "session_id": "a" * 32,
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "usage": {
            "retrieval_calls": 0,
            "content_extractions": 0,
            "report_sources": 0,
        },
        "events": [],
    }

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "legacy.json"

    def _write(self, payload: dict) -> None:
        self.path.write_text(json.dumps(payload), encoding="utf-8")

    def test_missing_budget_line_is_backfilled_from_the_mode(self) -> None:
        self._write(self.LEGACY)
        state = deep_research.load_session(self.path)
        self.assertEqual(
            deep_research.MODE_BUDGETS["quick"]["live_verification_max"],
            state["budget"]["live_verification_max"],
        )
        self.assertEqual(0, state["usage"]["live_verifications"])

    def test_a_legacy_ledger_can_still_reserve_the_new_line(self) -> None:
        self._write(self.LEGACY)
        reservation = deep_research.reserve_session_budget(
            self.path, "live_verifications", 2, allow_partial=False
        )
        self.assertEqual(2, reservation["reserved"])
        self.assertEqual(
            2,
            json.loads(self.path.read_text(encoding="utf-8"))["usage"][
                "live_verifications"
            ],
        )

    def test_a_tampered_budget_value_is_still_rejected(self) -> None:
        """Backfilling an absent key must not soften the anti-tampering check."""
        tampered = json.loads(json.dumps(self.LEGACY))
        tampered["budget"]["live_verification_max"] = 500
        self._write(tampered)
        with self.assertRaisesRegex(ValueError, "not canonical"):
            deep_research.load_session(self.path)

        inflated = json.loads(json.dumps(self.LEGACY))
        inflated["budget"]["retrieval_max"] = 5000
        self._write(inflated)
        with self.assertRaisesRegex(ValueError, "not canonical"):
            deep_research.load_session(self.path)

    def test_a_usage_value_over_its_ceiling_is_still_rejected(self) -> None:
        overspent = json.loads(json.dumps(self.LEGACY))
        overspent["usage"]["live_verifications"] = 999
        self._write(overspent)
        with self.assertRaisesRegex(ValueError, "invalid session usage"):
            deep_research.load_session(self.path)


class ArtifactsAreBoundToTheirLedger(unittest.TestCase):
    """The report must not print one ledger's budget for another run's work.

    `retrieve` and `fetch-content` already stamp `session_id` into their
    output; nothing read it back. A report rendered from artifacts collected
    under a spent ledger, with `--session` pointing at a fresh one, printed
    "Budget consumed: retrieval 0/10" as an audit fact about a run that had
    consumed something else entirely.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.session = self.root / "session.json"
        deep_research.initialize_session(
            self.session,
            deep_research.plan_research("Quick check.", explicit_mode="quick"),
        )
        self.state = deep_research.load_session(self.session)

    def _artifact(self, name: str, session_id: str) -> Path:
        path = self.root / name
        path.write_text(json.dumps({"session_id": session_id, "results": []}))
        return path

    def test_foreign_session_id_is_rejected(self) -> None:
        foreign = self._artifact("results.json", "SOME-OTHER-SESSION")
        with self.assertRaises(ValueError) as ctx:
            deep_research.assert_artifacts_share_session(
                self.state, [("--results artifact", foreign)]
            )
        self.assertIn("SOME-OTHER-SESSION", str(ctx.exception))

    def test_matching_session_id_is_accepted(self) -> None:
        """Positive control: the check must not reject the normal workflow."""
        same = self._artifact("results.json", self.state["session_id"])
        deep_research.assert_artifacts_share_session(
            self.state, [("--results artifact", same)]
        )

    def test_unstamped_artifact_is_an_unknown_not_a_mismatch(self) -> None:
        """A fallback tool's artifact carries no stamp; that is not a conflict.

        Rejecting it would break the documented search/extraction fallback
        path, which the skill already treats as untrusted by other means.
        """
        path = self.root / "imported.json"
        path.write_text(json.dumps({"results": []}))
        deep_research.assert_artifacts_share_session(
            self.state, [("--results artifact", path)]
        )


class LiveReachabilityIsBudgeted(unittest.TestCase):
    """Both flags that open sockets are gated, not just one.

    `--check-live` issued one HEAD per cited URL, with GET fallback, three
    retries and five redirect hops, against no ledger at all — while the
    parser's own error text for `--live-web` explained that network fetches
    require `--session` "so they are counted against the mode budget".
    """

    def test_check_live_requires_a_session(self) -> None:
        parser = deep_research.build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args([
                "validate",
                "--research-kind", "web",
                "--results", "r.json",
                "--content", "c.json",
                "--findings", "f.json",
                "--check-live",
                "--output", "v.json",
            ])

    def test_validate_without_live_flags_does_not_require_a_session(self) -> None:
        """Control: offline validation must stay usable with no ledger.

        Without this, gating every `validate` invocation would satisfy the test
        above while breaking the documented offline shape-check step.
        """
        parser = deep_research.build_parser()
        args = parser.parse_args([
            "validate",
            "--research-kind", "web",
            "--results", "r.json",
            "--content", "c.json",
            "--findings", "f.json",
            "--output", "v.json",
        ])
        self.assertEqual("validate", args.cmd)



if __name__ == "__main__":
    unittest.main()
