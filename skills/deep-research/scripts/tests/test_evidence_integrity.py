"""Behavioral coverage for the deep-research executable evidence contract."""

import importlib.util
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "deep_research.py"
spec = importlib.util.spec_from_file_location("deep_research_integrity", SCRIPT)
deep_research = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = deep_research
spec.loader.exec_module(deep_research)


def repository_evidence_fixture(root: Path) -> dict:
    def git(*args: str) -> str:
        proc = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if proc.returncode != 0:
            raise AssertionError(proc.stderr)
        return proc.stdout.strip()

    git("init", "-q")
    git("config", "user.email", "tests@example.com")
    git("config", "user.name", "Deep Research Tests")
    source = root / "middleware.go"
    source.write_text(
        "package auth\n\nfunc middleware(raw string) bool {\n"
        "    return verifyToken(raw)\n}\n\n"
        'func verifyToken(raw string) bool { return raw == "ok" }\n',
        encoding="utf-8",
    )
    test_source = root / "middleware_test.go"
    test_source.write_text(
        "package auth\n\nimport \"testing\"\n\n"
        "func TestMiddlewareAcceptsValidToken(t *testing.T) {\n"
        '    if !middleware("ok") { t.Fatal("expected valid token") }\n'
        "}\n",
        encoding="utf-8",
    )
    (root / "go.mod").write_text(
        "module example.com/auth\n\ngo 1.22\n",
        encoding="utf-8",
    )
    git("add", "middleware.go", "middleware_test.go", "go.mod")
    git("commit", "-q", "-m", "fix: verify bearer token")
    commit = git("rev-parse", "HEAD")
    tree = git("rev-parse", "HEAD^{tree}")
    stdout = "ok   example.com/auth"
    empty_hash = hashlib.sha256(b"").hexdigest()
    stdout_hash = hashlib.sha256(stdout.encode("utf-8")).hexdigest()
    return {
        "root": str(root.resolve()),
        "evidence": [
            {
                "id": "code-1",
                "kind": "code",
                "path": "middleware.go",
                "line": 4,
                "excerpt": "    return verifyToken(raw)",
                "commit": commit,
                "snapshot": "commit",
            },
            {
                "id": "commit-1",
                "kind": "commit",
                "commit": commit,
                "subject": "fix: verify bearer token",
            },
            {
                "schema": "deep-research/host-test-receipt-v2",
                "id": "test-1",
                "kind": "test",
                "origin": "host-tool",
                "execution_id": "a" * 64,
                "command": "go test -run TestMiddlewareAcceptsValidToken .",
                "argv": [
                    "go",
                    "test",
                    "-run",
                    "TestMiddlewareAcceptsValidToken",
                    ".",
                ],
                "framework": "go-test",
                "test_target": "TestMiddlewareAcceptsValidToken",
                "selectors": ["TestMiddlewareAcceptsValidToken"],
                "tested_paths": ["middleware.go", "middleware_test.go"],
                "covers": ["finding-auth-path", "code-1"],
                "repository": {
                    "root": str(root.resolve()),
                    "head_commit": commit,
                    "tree_hash": tree,
                    "dirty": False,
                },
                "status": "passed",
                "exit_code": 0,
                "summary": stdout,
                "stdout_summary": stdout,
                "stderr_summary": "",
                "stdout_sha256": stdout_hash,
                "stderr_sha256": empty_hash,
                "started_at": "2026-07-18T00:00:00+00:00",
                "finished_at": "2026-07-18T00:00:01+00:00",
                "duration_seconds": 1.0,
                "relevance_review": {
                    "status": "approved",
                    "reviewer": "evidence-integrity-test",
                    "rationale": (
                        "The named Go test calls middleware with a valid token."
                    ),
                    "reviewed_at": "2026-07-18T00:00:02+00:00",
                },
            },
        ],
    }


def web_source(
    url: str = "https://go.dev/pkg/context",
    *,
    tier: str = "T1",
) -> object:
    return deep_research.SearchResult(
        query="context WithTimeout return value",
        title="context package",
        url=url,
        normalized_url=url,
        domain=deep_research.registrable_domain(
            deep_research.urllib.parse.urlparse(url).hostname or ""
        ),
        source_type="official",
        source_tier=tier,
        classification_basis="explicit",
        sponsorship="none",
        methodology="primary documentation",
    )


def web_content(
    url: str = "https://go.dev/pkg/context",
    *,
    error: str = "",
) -> object:
    content = (
        "WithTimeout returns a copy of the parent context with the timeout "
        "adjusted to be no later than d."
    )
    return deep_research.ContentResult(
        url=url,
        title="context package",
        content=content,
        word_count=len(content.split()),
        error=error,
    )


def web_finding(*, confidence: str = "high", excerpt: str = "") -> dict:
    return {
        "title": "WithTimeout return value",
        "claim_type": "single_fact",
        "confidence": confidence,
        "analysis": "WithTimeout returns a derived context.",
        "evidence": [
            {
                "kind": "web",
                "url": "https://go.dev/pkg/context",
                "excerpt": excerpt
                or "WithTimeout returns a copy of the parent context",
            }
        ],
    }


class TestExecutableModeStateMachine(unittest.TestCase):
    def test_quick_single_fact(self) -> None:
        plan = deep_research.plan_research(
            "What HTTP status code does http.StatusOK represent in Go?"
        )
        self.assertEqual("quick", plan["mode"])
        self.assertEqual(10, plan["budget"]["retrieval_max"])

    def test_deep_security_decision(self) -> None:
        plan = deep_research.plan_research(
            "Select a TLS library for our payment processor and compare security trade-offs."
        )
        self.assertEqual("deep", plan["mode"])
        self.assertEqual(50, plan["budget"]["retrieval_max"])

    def test_user_mode_override_wins(self) -> None:
        plan = deep_research.plan_research(
            "Compare Redis and Valkey for our caching layer.",
            explicit_mode="standard",
        )
        self.assertEqual("standard", plan["mode"])
        self.assertEqual("user", plan["mode_basis"])

    def test_pure_codebase_suppresses_web(self) -> None:
        plan = deep_research.plan_research(
            "How is authentication implemented in our internal repository?"
        )
        self.assertEqual("codebase", plan["research_kind"])
        self.assertFalse(plan["requires_web_content"])

    def test_parser_rejects_global_51_query_overflow(self) -> None:
        parser = deep_research.build_parser()
        argv = [
            "retrieve",
            "--mode",
            "deep",
            "--session",
            "/tmp/session.json",
            "--output",
            "/tmp/out.json",
        ]
        for i in range(51):
            argv.extend(["--query", f"q{i}"])
        with self.assertRaises(SystemExit):
            parser.parse_args(argv)

    def test_parser_rejects_quick_mode_11_query_overflow(self) -> None:
        parser = deep_research.build_parser()
        argv = [
            "retrieve",
            "--mode",
            "quick",
            "--session",
            "/tmp/session.json",
            "--output",
            "/tmp/out.json",
        ]
        for i in range(11):
            argv.extend(["--query", f"q{i}"])
        with self.assertRaises(SystemExit):
            parser.parse_args(argv)


class TestWebEvidenceClosure(unittest.TestCase):
    def test_single_t1_primary_source_can_be_high(self) -> None:
        summary = deep_research.validate_research_bundle(
            research_kind="web",
            results=[web_source()],
            contents=[web_content()],
            code_evidence={},
            findings={"findings": [web_finding()]},
        )
        assessed = summary["findings"][0]
        self.assertEqual("high", assessed["effective_confidence"])
        self.assertEqual("Full", summary["degradation"])

    def test_missing_content_blocks_web_research(self) -> None:
        summary = deep_research.validate_research_bundle(
            research_kind="web",
            results=[web_source()],
            contents=[],
            code_evidence={},
            findings={"findings": [web_finding()]},
        )
        self.assertEqual("Blocked", summary["degradation"])
        self.assertTrue(
            any(issue["code"] == "required_content_missing" for issue in summary["issues"])
        )

    def test_failed_extraction_cannot_support_high(self) -> None:
        summary = deep_research.validate_research_bundle(
            research_kind="web",
            results=[web_source()],
            contents=[web_content(error="blocked by WAF")],
            code_evidence={},
            findings={"findings": [web_finding()]},
        )
        self.assertNotEqual("high", summary["findings"][0]["effective_confidence"])
        self.assertEqual("Blocked", summary["degradation"])

    def test_excerpt_must_exist_in_extracted_text(self) -> None:
        finding = web_finding(excerpt="This sentence does not occur on the page.")
        summary = deep_research.validate_research_bundle(
            research_kind="web",
            results=[web_source()],
            contents=[web_content()],
            code_evidence={},
            findings={"findings": [finding]},
        )
        self.assertFalse(summary["findings"][0]["usable"])
        self.assertTrue(
            any(issue["code"] == "excerpt_not_in_content" for issue in summary["issues"])
        )

    def test_legacy_url_only_citation_is_not_verified_evidence(self) -> None:
        legacy = web_finding()
        legacy.pop("evidence")
        legacy["citations"] = ["https://go.dev/pkg/context"]
        summary = deep_research.validate_research_bundle(
            research_kind="web",
            results=[web_source()],
            contents=[web_content()],
            code_evidence={},
            findings={"findings": [legacy]},
        )
        self.assertFalse(summary["findings"][0]["usable"])
        self.assertTrue(
            any(issue["code"] == "legacy_citations_unverified" for issue in summary["issues"])
        )

    def test_no_findings_cannot_be_full(self) -> None:
        summary = deep_research.validate_research_bundle(
            research_kind="web",
            results=[web_source()],
            contents=[web_content()],
            code_evidence={},
            findings={"findings": []},
        )
        self.assertEqual("Blocked", summary["degradation"])

    def test_unsupported_analysis_section_forces_partial(self) -> None:
        summary = deep_research.validate_research_bundle(
            research_kind="web",
            results=[web_source()],
            contents=[web_content()],
            code_evidence={},
            findings={
                "findings": [web_finding()],
                "analysis_sections": [{
                    "title": "Unsupported detail",
                    "content": "No evidence is attached.",
                    "evidence": [],
                }],
            },
        )
        self.assertEqual("Partial", summary["degradation"])

    def test_one_valid_and_one_invalid_reference_cannot_be_full(self) -> None:
        finding = web_finding()
        finding["evidence"].append(
            {
                "kind": "web",
                "url": "https://example.invalid/not-retrieved",
                "excerpt": "This source was never collected.",
            }
        )
        summary = deep_research.validate_research_bundle(
            research_kind="web",
            results=[web_source()],
            contents=[web_content()],
            code_evidence={},
            findings={"findings": [finding]},
        )
        self.assertTrue(summary["findings"][0]["usable"])
        self.assertEqual("Partial", summary["degradation"])
        self.assertTrue(
            any(
                issue["code"] == "web_source_not_retrieved"
                for issue in summary["issues"]
            )
        )


class TestCodebaseEvidence(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.evidence = repository_evidence_fixture(Path(self._tmp.name))

    def test_code_commit_and_test_are_first_class_sources(self) -> None:
        finding = {
            "id": "finding-auth-path",
            "title": "Authentication path",
            "claim_type": "runtime_behavior",
            "confidence": "high",
            "analysis": "Bearer tokens are verified by middleware.",
            "evidence": [
                {"kind": "code", "id": "code-1"},
                {"kind": "commit", "id": "commit-1"},
                {"kind": "test", "id": "test-1"},
            ],
        }
        summary = deep_research.validate_research_bundle(
            research_kind="codebase",
            results=[],
            contents=[],
            code_evidence=self.evidence,
            findings={"findings": [finding]},
        )
        self.assertEqual("high", summary["findings"][0]["effective_confidence"])
        self.assertEqual("Full", summary["degradation"])
        self.assertEqual(3, summary["counts"]["repository_evidence"])

    def test_codebase_does_not_require_url_or_content(self) -> None:
        finding = {
            "title": "Authentication call site",
            "claim_type": "code_fact",
            "confidence": "high",
            "analysis": "The middleware calls verifyToken.",
            "evidence": [{"kind": "code", "id": "code-1"}],
        }
        summary = deep_research.validate_research_bundle(
            research_kind="codebase",
            results=[],
            contents=[],
            code_evidence=self.evidence,
            findings={"findings": [finding]},
        )
        self.assertEqual("Full", summary["degradation"])
        self.assertEqual("high", summary["findings"][0]["effective_confidence"])

    def test_failed_test_does_not_verify_runtime_behavior(self) -> None:
        self.evidence["evidence"][2]["status"] = "failed"
        self.evidence["evidence"][2]["exit_code"] = 1
        finding = {
            "id": "finding-auth-path",
            "title": "Authentication behavior",
            "claim_type": "runtime_behavior",
            "confidence": "high",
            "analysis": "The path is tested.",
            "evidence": [
                {"kind": "code", "id": "code-1"},
                {"kind": "test", "id": "test-1"},
            ],
        }
        summary = deep_research.validate_research_bundle(
            research_kind="codebase",
            results=[],
            contents=[],
            code_evidence=self.evidence,
            findings={"findings": [finding]},
        )
        self.assertNotEqual("high", summary["findings"][0]["effective_confidence"])

    def test_unpinned_code_fact_cannot_be_high(self) -> None:
        self.evidence["evidence"][0]["commit"] = "unknown"
        finding = {
            "title": "Authentication call site",
            "claim_type": "code_fact",
            "confidence": "high",
            "analysis": "The middleware calls verifyToken.",
            "evidence": [{"kind": "code", "id": "code-1"}],
        }
        summary = deep_research.validate_research_bundle(
            research_kind="codebase",
            results=[],
            contents=[],
            code_evidence=self.evidence,
            findings={"findings": [finding]},
        )
        self.assertEqual("medium", summary["findings"][0]["effective_confidence"])
        self.assertEqual("Partial", summary["degradation"])

    def test_working_tree_label_is_not_a_pinned_commit(self) -> None:
        self.evidence["evidence"][0]["commit"] = "working-tree-unpinned"
        finding = {
            "title": "Authentication call site",
            "claim_type": "code_fact",
            "confidence": "high",
            "analysis": "The middleware calls verifyToken.",
            "evidence": [{"kind": "code", "id": "code-1"}],
        }
        summary = deep_research.validate_research_bundle(
            research_kind="codebase",
            results=[],
            contents=[],
            code_evidence=self.evidence,
            findings={"findings": [finding]},
        )
        self.assertEqual("medium", summary["findings"][0]["effective_confidence"])

    def test_single_fact_exception_does_not_accept_repository_evidence(self) -> None:
        finding = {
            "title": "Authentication call site",
            "claim_type": "single_fact",
            "confidence": "high",
            "analysis": "The middleware calls verifyToken.",
            "evidence": [{"kind": "code", "id": "code-1"}],
        }
        summary = deep_research.validate_research_bundle(
            research_kind="codebase",
            results=[],
            contents=[],
            code_evidence=self.evidence,
            findings={"findings": [finding]},
        )
        self.assertEqual("medium", summary["findings"][0]["effective_confidence"])

    def test_hybrid_requires_both_web_and_repository_support(self) -> None:
        finding = {
            "title": "Authentication call site",
            "claim_type": "code_fact",
            "confidence": "high",
            "analysis": "The middleware calls verifyToken.",
            "evidence": [{"kind": "code", "id": "code-1"}],
        }
        summary = deep_research.validate_research_bundle(
            research_kind="hybrid",
            results=[web_source()],
            contents=[web_content()],
            code_evidence=self.evidence,
            findings={"findings": [finding]},
        )
        self.assertEqual("Partial", summary["degradation"])
        self.assertTrue(
            any(
                issue["code"] == "hybrid_evidence_incomplete"
                for issue in summary["issues"]
            )
        )


class TestCanonicalReport(unittest.TestCase):
    def test_exact_nine_sections_and_actual_counts(self) -> None:
        findings = {
            "executive_summary": "WithTimeout returns a derived context.",
            "findings": [web_finding()],
            "analysis_sections": [
                {
                    "title": "API behavior",
                    "content": "The returned context inherits from its parent.",
                    "evidence": [
                        {
                            "kind": "web",
                            "url": "https://go.dev/pkg/context",
                            "excerpt": "WithTimeout returns a copy of the parent context",
                        }
                    ],
                }
            ],
            "consensus": [],
            "debate": [],
            "gaps": [],
        }
        validation = deep_research.validate_research_bundle(
            research_kind="web",
            results=[web_source()],
            contents=[web_content()],
            code_evidence={},
            findings=findings,
        )
        report = deep_research.generate_report(
            question="What does WithTimeout return?",
            findings=findings,
            results=[web_source()],
            depth="quick",
            contents=[web_content()],
            code_evidence={},
            validation=validation,
            research_kind="web",
        )
        headings = [line for line in report.splitlines() if line.startswith("## ")]
        self.assertEqual(
            [
                "## 1) Research Question",
                "## 2) Method",
                "## 3) Executive Summary",
                "## 4) Key Findings",
                "## 5) Detailed Analysis",
                "## 6) Consensus vs Debate",
                "## 7) Source Quality Notes",
                "## 8) Sources",
                "## 9) Gaps & Limitations",
            ],
            headings,
        )
        self.assertIn("Successfully extracted: 1", report)
        self.assertIn("Cited evidence units: 1", report)
        self.assertIn("T1: 1", report)

    def test_blocked_report_does_not_echo_unverified_summary(self) -> None:
        findings = {
            "executive_summary": "UNVERIFIED CLAIM MUST NOT LEAK",
            "findings": [web_finding()],
        }
        validation = deep_research.validate_research_bundle(
            research_kind="web",
            results=[web_source()],
            contents=[],
            code_evidence={},
            findings=findings,
        )
        report = deep_research.generate_report(
            question="What does WithTimeout return?",
            findings=findings,
            results=[web_source()],
            depth="quick",
            contents=[],
            validation=validation,
            research_kind="web",
        )
        self.assertNotIn("UNVERIFIED CLAIM MUST NOT LEAK", report)
        self.assertIn("Research is blocked:", report)

    def test_codebase_source_quality_notes_cover_pinning_and_tests(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            evidence = repository_evidence_fixture(Path(tmp))
            evidence["evidence"] = [
                row
                for row in evidence["evidence"]
                if row["kind"] in {"code", "test"}
            ]
            findings = {
                "findings": [
                    {
                        "id": "finding-auth-path",
                        "title": "Authentication path",
                        "claim_type": "runtime_behavior",
                        "confidence": "high",
                        "analysis": "Bearer tokens are verified by middleware.",
                        "evidence": [
                            {"kind": "code", "id": "code-1"},
                            {"kind": "test", "id": "test-1"},
                        ],
                    }
                ]
            }
            validation = deep_research.validate_research_bundle(
                research_kind="codebase",
                results=[],
                contents=[],
                code_evidence=evidence,
                findings=findings,
            )
            report = deep_research.generate_report(
                question="How are bearer tokens verified?",
                findings=findings,
                results=[],
                depth="quick",
                code_evidence=evidence,
                validation=validation,
                research_kind="codebase",
            )
            self.assertIn(
                "Repository evidence quality: code observations: 1; "
                "commit-pinned: 1; tests passed: 1; tests failed/other: 0",
                report,
            )
            self.assertIn("covers: finding-auth-path, code-1", report)
            self.assertIn("relevance: approved", report)


class TestCliEvidenceRequirements(unittest.TestCase):
    def test_web_report_parser_requires_content(self) -> None:
        parser = deep_research.build_parser()
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
                    "--findings",
                    "findings.json",
                    "--session",
                    "/tmp/session.json",
                    "--output",
                    "report.md",
                ]
            )

    def test_codebase_report_parser_requires_code_evidence_not_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            session = Path(tmp) / "session.json"
            deep_research.initialize_session(
                session,
                deep_research.plan_research("q", explicit_mode="standard"),
            )
            parser = deep_research.build_parser()
            args = parser.parse_args(
                [
                    "report",
                    "--question",
                    "q",
                    "--research-kind",
                    "codebase",
                    "--code-evidence",
                    "code.json",
                    "--findings",
                    "findings.json",
                    "--session",
                    str(session),
                    "--output",
                    "report.md",
                ]
            )
            self.assertEqual("codebase", args.research_kind)
            self.assertEqual("", args.content)

    def test_content_budget_exhaustion_automatically_degrades_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            results_path = root / "results.json"
            content_path = root / "content.json"
            findings_path = root / "findings.json"
            report_path = root / "report.md"
            session_path = root / "session.json"
            deep_research.initialize_session(
                session_path,
                deep_research.plan_research(
                    "What does WithTimeout return?",
                    explicit_mode="quick",
                ),
            )
            results_path.write_text(
                json.dumps({"results": [deep_research.asdict(web_source())]})
            )
            content_path.write_text(
                json.dumps(
                    {
                        "mode": "quick",
                        "budget_exhausted": True,
                        "items": [deep_research.asdict(web_content())],
                    }
                )
            )
            findings_path.write_text(json.dumps({"findings": [web_finding()]}))

            parser = deep_research.build_parser()
            args = parser.parse_args(
                [
                    "report",
                    "--question",
                    "What does WithTimeout return?",
                    "--research-kind",
                    "web",
                    "--results",
                    str(results_path),
                    "--content",
                    str(content_path),
                    "--findings",
                    str(findings_path),
                    "--mode",
                    "quick",
                    "--session",
                    str(session_path),
                    "--output",
                    str(report_path),
                ]
            )
            self.assertEqual(0, args.func(args))
            report = report_path.read_text()
            self.assertIn("Degradation level: `Partial`", report)
            self.assertIn("research budget was exhausted", report)


if __name__ == "__main__":
    unittest.main()
