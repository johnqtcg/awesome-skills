"""Behavioral coverage for the deep-research executable evidence contract."""

import importlib.util
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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
    live_verified: bool = False,
) -> object:
    content = (
        "WithTimeout returns a copy of the parent context with the timeout "
        "adjusted to be no later than d."
    )
    result = deep_research.ContentResult(
        url=url,
        title="context package",
        content=content,
        word_count=len(content.split()),
        error=error,
    )
    result.live_verified = live_verified
    result.final_url = url
    return result


def web_finding(
    *,
    confidence: str = "high",
    excerpt: str = "",
    url: str = "https://go.dev/pkg/context",
) -> dict:
    return {
        "title": "WithTimeout return value",
        "claim_type": "single_fact",
        "confidence": confidence,
        "analysis": "WithTimeout returns a derived context.",
        "support_review": {
            "stance": "supports",
            "rationale": "the excerpt states the return value the claim asserts",
        },
        "evidence": [
            {
                "kind": "web",
                "url": url,
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
    def test_caller_authored_t1_cannot_be_high(self) -> None:
        summary = deep_research.validate_research_bundle(
            research_kind="web",
            results=[web_source()],
            contents=[web_content()],
            code_evidence={},
            findings={"findings": [web_finding()]},
        )
        assessed = summary["findings"][0]
        self.assertEqual("medium", assessed["effective_confidence"])
        self.assertEqual("Partial", summary["degradation"])
        self.assertIn(
            "live Web verification",
            " ".join(assessed["downgrade_reasons"]),
        )

    def test_serialized_live_flag_and_t1_label_are_not_trusted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            results_path = root / "results.json"
            content_path = root / "content.json"
            results_path.write_text(
                json.dumps(
                    {
                        "results": [
                            {
                                "query": "claim",
                                "title": "Caller-authored source",
                                "url": "https://example.com/claim",
                                "source_type": "official",
                                "source_tier": "T1",
                                "classification_basis": "explicit",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            content_path.write_text(
                json.dumps(
                    {
                        "items": [
                            {
                                "url": "https://example.com/claim",
                                "title": "Caller-authored content",
                                "content": "The caller-authored claim is true.",
                                "word_count": 6,
                                "error": "",
                                "live_verified": True,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            results = deep_research.load_results(results_path)
            contents, _ = deep_research.load_content_artifact(content_path)
        finding = {
            "title": "Caller-authored claim",
            "claim_type": "single_fact",
            "confidence": "high",
            "analysis": "The caller-authored claim is true.",
            "evidence": [
                {
                    "kind": "web",
                    "url": "https://example.com/claim",
                    "excerpt": "caller-authored claim is true",
                }
            ],
        }
        summary = deep_research.validate_research_bundle(
            research_kind="web",
            results=results,
            contents=contents,
            code_evidence={},
            findings={"findings": [finding]},
        )
        assessed = summary["findings"][0]
        self.assertEqual("medium", assessed["effective_confidence"])
        self.assertFalse(assessed["verified_evidence"][0]["live_verified"])
        self.assertEqual("T4", assessed["verified_evidence"][0]["source_tier"])

    def test_live_verified_validator_derived_t1_can_be_high(self) -> None:
        url = "https://www.nist.gov/example"
        summary = deep_research.validate_research_bundle(
            research_kind="web",
            results=[web_source(url=url)],
            contents=[web_content(url=url, live_verified=True)],
            code_evidence={},
            findings={"findings": [web_finding(url=url)]},
        )
        assessed = summary["findings"][0]
        self.assertEqual("high", assessed["effective_confidence"])
        self.assertEqual("Full", summary["degradation"])

    def _quick_session(self, root: Path) -> Path:
        session_path = root / "session.json"
        deep_research.initialize_session(
            session_path,
            deep_research.plan_research("live verification", explicit_mode="quick"),
        )
        return session_path

    def test_live_verifier_replaces_serialized_content_before_assessment(self) -> None:
        url = "https://www.nist.gov/example"
        loaded = web_content(url)
        loaded.content = "Caller supplied unrelated text."
        fresh = web_content(url, live_verified=True)
        fresh.capture_method = "validator-live-fetch"
        fresh.http_status = 200
        with tempfile.TemporaryDirectory() as tmp:
            session_path = self._quick_session(Path(tmp))
            with patch.object(
                deep_research,
                "fetch_contents_parallel",
                return_value=[fresh],
            ) as fetch:
                contents, reservation = deep_research._live_verify_web_contents(
                    {"findings": [web_finding(url=url)]},
                    [loaded],
                    session_path=session_path,
                    timeout=3,
                )
            fetch.assert_called_once_with(
                [url],
                timeout=3,
                max_workers=deep_research.CONTENT_FETCH_WORKERS,
                capture_method="validator-live-fetch",
                max_bytes=deep_research.VALIDATION_MAX_BYTES,
                max_chars=deep_research.VALIDATION_MAX_CHARS,
            )
            self.assertEqual(1, reservation["reserved"])
            ledger = json.loads(session_path.read_text(encoding="utf-8"))
            self.assertEqual(1, ledger["usage"]["live_verifications"])
        summary = deep_research.validate_research_bundle(
            research_kind="web",
            results=[web_source(url=url)],
            contents=contents,
            code_evidence={},
            findings={"findings": [web_finding(url=url)]},
        )
        self.assertEqual(
            "high",
            summary["findings"][0]["effective_confidence"],
        )

    def test_live_verification_stops_at_the_session_ceiling(self) -> None:
        """The final verification path is inside the cumulative budget.

        Before this, `report --live-web` fetched every cited URL through a
        direct call that touched no ledger, so a Quick session that had already
        spent its whole allowance could still issue unlimited network requests
        and still print `Full`.
        """
        urls = [f"https://www.nist.gov/p{i}" for i in range(7)]
        with tempfile.TemporaryDirectory() as tmp:
            session_path = self._quick_session(Path(tmp))
            limit = deep_research.MODE_BUDGETS["quick"]["live_verification_max"]
            findings = {
                "findings": [
                    {
                        "title": "Retention",
                        "claim_type": "single_fact",
                        "confidence": "high",
                        "analysis": "Requests are discarded after processing.",
                        "evidence": [
                            {"kind": "web", "url": u, "excerpt": "discarded"}
                            for u in urls
                        ],
                    }
                ]
            }
            with patch.object(
                deep_research,
                "fetch_contents_parallel",
                side_effect=lambda u, **kw: [],
            ) as fetch:
                _, reservation = deep_research._live_verify_web_contents(
                    findings,
                    [],
                    session_path=session_path,
                    timeout=3,
                )
            self.assertEqual(limit, reservation["reserved"])
            self.assertTrue(reservation["exhausted"])
            self.assertEqual(limit, len(fetch.call_args[0][0]))
            ledger = json.loads(session_path.read_text(encoding="utf-8"))
            self.assertEqual(limit, ledger["usage"]["live_verifications"])

            # A second pass on the same ledger must fetch nothing at all.
            with patch.object(
                deep_research,
                "fetch_contents_parallel",
                side_effect=lambda u, **kw: [],
            ) as fetch_again:
                _, second = deep_research._live_verify_web_contents(
                    findings,
                    [],
                    session_path=session_path,
                    timeout=3,
                )
            fetch_again.assert_not_called()
            self.assertEqual(0, second["reserved"])
            self.assertTrue(second["exhausted"])

    def test_verification_lifts_both_authoring_truncation_caps(self) -> None:
        """A correct excerpt from the tail of a long page must still validate.

        Two caps used to silence it independently: a 512 KB download cap and a
        15,000-character extraction cap. A live A/B measured 19 of 67 correct
        citations rejected for this reason alone, so verification must read the
        whole page while authoring keeps the smaller budget.
        """
        self.assertGreater(
            deep_research.VALIDATION_MAX_CHARS, deep_research.CONTENT_MAX_CHARS
        )
        self.assertGreater(
            deep_research.VALIDATION_MAX_BYTES, deep_research.CONTENT_MAX_BYTES
        )
        seen = {}

        def fake_fetch(urls, **kwargs):
            seen.update(kwargs)
            return []

        url = "https://www.nist.gov/long"
        with tempfile.TemporaryDirectory() as tmp:
            session_path = self._quick_session(Path(tmp))
            with patch.object(deep_research, "fetch_contents_parallel", fake_fetch):
                deep_research._live_verify_web_contents(
                    {"findings": [{"evidence": [{"kind": "web", "url": url}]}]},
                    [],
                    session_path=session_path,
                    timeout=3,
                )
        self.assertEqual(deep_research.VALIDATION_MAX_CHARS, seen.get("max_chars"))
        self.assertEqual(deep_research.VALIDATION_MAX_BYTES, seen.get("max_bytes"))

    def test_extraction_cap_is_a_parameter_not_a_hardcoded_default(self) -> None:
        """`fetch_page_content` must honour a caller-supplied cap."""
        long_html = "<p>" + ("word " * 20_000) + "needle-at-the-tail</p>"
        short = deep_research.extract_text_from_html(long_html, max_chars=5_000)
        full = deep_research.extract_text_from_html(long_html, max_chars=500_000)
        self.assertNotIn("needle-at-the-tail", short)
        self.assertIn("needle-at-the-tail", full)

    def test_typographic_variants_do_not_reject_a_correct_quote(self) -> None:
        """A page's rendering must not decide whether a quote is real.

        Each pair below is one real failure from the 2026-09-08 live A/B: the
        page rendered curly quotes or wrapped identifiers in backticks and the
        matcher rejected an excerpt that was copied correctly.
        """
        pairs = [
            ('severity labels such as "LOW," "MEDIUM", and "CRITICAL"',
             'severity labels such as \u201cLOW,\u201d \u201cMEDIUM\u201d, and \u201cCRITICAL\u201d'),
            ("An error is thrown if `a` and `b` have different byte lengths.",
             "An error is thrown if a and b have different byte lengths."),
            ("a range of 1-10 values",
             "a range of 1\u201310\u00a0values"),
        ]
        for excerpt, page in pairs:
            self.assertIn(
                deep_research._normalized_excerpt(excerpt),
                deep_research._normalized_excerpt(page),
                excerpt,
            )

    def test_folding_does_not_loosen_the_match(self) -> None:
        """The fold must not make an opposite sentence match."""
        self.assertNotIn(
            deep_research._normalized_excerpt("the service does retain logs"),
            deep_research._normalized_excerpt("the service does not retain logs"),
        )
        self.assertNotIn(
            deep_research._normalized_excerpt("acks defaults to 1"),
            deep_research._normalized_excerpt("acks defaults to all"),
        )

    def test_validate_live_web_without_session_is_rejected(self) -> None:
        """--live-web opens sockets, so it may not run outside a ledger."""
        parser = deep_research.build_parser()
        with tempfile.TemporaryDirectory() as tmp:
            findings_path = Path(tmp) / "findings.json"
            findings_path.write_text(json.dumps({"findings": [web_finding()]}))
            with self.assertRaises(SystemExit):
                parser.parse_args(
                    [
                        "validate",
                        "--research-kind",
                        "web",
                        "--findings",
                        str(findings_path),
                        "--live-web",
                    ]
                )

    def test_effective_final_url_controls_live_authority(self) -> None:
        requested_url = "https://www.nist.gov/example"
        content = web_content(requested_url, live_verified=True)
        content.final_url = "https://example.com/redirected"
        content.capture_method = "validator-live-fetch"
        summary = deep_research.validate_research_bundle(
            research_kind="web",
            results=[web_source(url=requested_url)],
            contents=[content],
            code_evidence={},
            findings={"findings": [web_finding(url=requested_url)]},
        )
        assessed = summary["findings"][0]
        self.assertEqual("medium", assessed["effective_confidence"])
        verified = assessed["verified_evidence"][0]
        self.assertEqual(
            "https://example.com/redirected",
            verified["final_url"],
        )
        self.assertEqual("T4", verified["source_tier"])

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
            "support_review": {
                "stance": "supports",
                "rationale": "the pinned code and passing receipt cover this path",
            },
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
            "support_review": {
                "stance": "supports",
                "rationale": "the cited repository evidence states this directly",
                "reviewed_by": "author",
            },
            "support_review": {
                "stance": "supports",
                "rationale": "the pinned excerpt is the call site the claim names",
            },
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
            "support_review": {
                "stance": "supports",
                "rationale": "the cited repository evidence states this directly",
                "reviewed_by": "author",
            },
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

    def test_unpinned_code_is_never_an_independent_primary_unit(self) -> None:
        """Two working-tree files must not satisfy the two-unit High rule.

        `_verify_code` used to stamp `primary: True` on every code record, and
        the `pinned` flag next to it was only consulted for `code_fact` and
        `runtime_behavior` claims. On the default branch — analysis, comparison,
        recommendation — two unpinned records keyed on distinct ids counted as
        "two independent verified units, including a primary unit". Verified
        against a directory that was not a Git repository at all: `Full` +
        `high` + no downgrade reason, for a purely subjective comparative claim.
        """
        for record in self.evidence["evidence"]:
            if record.get("kind") == "code":
                record["commit"] = "working-tree-unpinned"
                record["snapshot"] = "worktree"
        second = dict(self.evidence["evidence"][0])
        second["id"] = "code-2"
        self.evidence["evidence"].append(second)
        finding = {
            "title": "Framework X is a better fit than framework Y",
            "claim_type": "analysis",
            "confidence": "high",
            "analysis": "Both call sites point the same way.",
            "support_review": {
                "stance": "supports",
                "rationale": "both cited working-tree call sites were read in full",
                "reviewed_by": "author",
            },
            "evidence": [
                {"kind": "code", "id": "code-1"},
                {"kind": "code", "id": "code-2"},
            ],
        }
        summary = deep_research.validate_research_bundle(
            research_kind="codebase",
            results=[],
            contents=[],
            code_evidence=self.evidence,
            findings={"findings": [finding]},
        )
        self.assertNotEqual("Full", summary["degradation"])
        self.assertEqual("medium", summary["findings"][0]["effective_confidence"])
        self.assertTrue(
            summary["findings"][0]["downgrade_reasons"],
            "an unpinned-only High must name the rule it failed",
        )

    def test_pinned_code_remains_an_independent_primary_unit(self) -> None:
        """Positive control: the fix must not demote pinned evidence.

        Without this, gating `primary` on `pinned` could be satisfied by
        returning False everywhere, which would silently cap every codebase
        finding at Medium and read as "the guard works".
        """
        second = dict(self.evidence["evidence"][0])
        second["id"] = "code-2"
        self.evidence["evidence"].append(second)
        finding = {
            "title": "Both call sites verify the token",
            "claim_type": "analysis",
            "confidence": "high",
            "analysis": "Both call sites point the same way.",
            "support_review": {
                "stance": "supports",
                "rationale": "both cited pinned call sites were read in full",
                "reviewed_by": "author",
            },
            "evidence": [
                {"kind": "code", "id": "code-1"},
                {"kind": "code", "id": "code-2"},
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

    def test_unpinned_code_fact_cannot_be_high(self) -> None:
        self.evidence["evidence"][0]["commit"] = "unknown"
        finding = {
            "title": "Authentication call site",
            "claim_type": "code_fact",
            "confidence": "high",
            "analysis": "The middleware calls verifyToken.",
            "support_review": {
                "stance": "supports",
                "rationale": "the cited repository evidence states this directly",
                "reviewed_by": "author",
            },
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
            "support_review": {
                "stance": "supports",
                "rationale": "the cited repository evidence states this directly",
                "reviewed_by": "author",
            },
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
            "support_review": {
                "stance": "supports",
                "rationale": "the cited repository evidence states this directly",
                "reviewed_by": "author",
            },
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
            "support_review": {
                "stance": "supports",
                "rationale": "the cited repository evidence states this directly",
                "reviewed_by": "author",
            },
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


class FindingsMustStateAClaim(unittest.TestCase):
    """Every other gate grades a claim against evidence; none checked one exists.

    A finding with an empty title and empty analysis validated as usable and
    `attested`, and rendered into Key Findings as
    "**Untitled finding** (High confidence)" — a report whose headline section
    carried no assertion at all, with zero issues raised.
    """

    def test_empty_claim_is_not_usable(self) -> None:
        summary = deep_research.validate_research_bundle(
            research_kind="web",
            results=[web_source()],
            contents=[web_content()],
            code_evidence={},
            findings={"findings": [{
                "title": "",
                "analysis": "",
                "confidence": "high",
                "evidence": [{
                    "kind": "web",
                    "url": "https://go.dev/pkg/context",
                    "excerpt": "WithTimeout returns a copy of the parent context",
                }],
                "support_review": {
                    "stance": "supports",
                    "rationale": "the excerpt states the return value directly",
                },
            }]},
        )
        finding = summary["findings"][0]
        self.assertFalse(finding["usable"])
        self.assertIn(
            "finding_has_no_claim",
            [issue["code"] for issue in summary["issues"]],
        )

    def test_a_stated_claim_is_still_accepted(self) -> None:
        """Positive control: the check must key on emptiness, not on presence."""
        summary = deep_research.validate_research_bundle(
            research_kind="web",
            results=[web_source()],
            contents=[web_content()],
            code_evidence={},
            findings={"findings": [web_finding(confidence="medium")]},
        )
        self.assertNotIn(
            "finding_has_no_claim",
            [issue["code"] for issue in summary["issues"]],
        )
        self.assertTrue(summary["findings"][0]["usable"])


class ReportCarriesItsOwnEvidence(unittest.TestCase):
    """The verified excerpt is the only part a reader can check without a rerun.

    The renderer emitted a bare citation index and left the matched excerpt in
    `findings.json` — a temporary file nobody keeps. A report whose thesis is
    traceability has to carry the quotation it traced.
    """

    def test_sources_section_prints_the_verified_excerpt(self) -> None:
        excerpt = "WithTimeout returns a copy of the parent context"
        validation = deep_research.validate_research_bundle(
            research_kind="web",
            results=[web_source()],
            contents=[web_content()],
            code_evidence={},
            findings={"findings": [web_finding(confidence="medium", excerpt=excerpt)]},
        )
        report = deep_research.generate_report(
            question="What does WithTimeout return?",
            findings={"findings": [web_finding(confidence="medium", excerpt=excerpt)]},
            results=[web_source()],
            depth="quick",
            contents=[web_content()],
            research_kind="web",
            validation=validation,
        )
        self.assertIn(excerpt, report)
        self.assertIn("verified excerpt:", report)

    def test_excerpts_do_not_shift_the_citation_numbering(self) -> None:
        """Excerpt lines are continuation text, not new citations.

        `next_index` used to be derived from the rendered line count, so
        adding a line under a source would have renumbered every repository
        citation after it and silently misaligned every `[n]` in the body.
        """
        excerpt = "WithTimeout returns a copy of the parent context"
        validation = deep_research.validate_research_bundle(
            research_kind="web",
            results=[web_source()],
            contents=[web_content()],
            code_evidence={},
            findings={"findings": [web_finding(confidence="medium", excerpt=excerpt)]},
        )
        sources = deep_research.build_sources_index(
            [web_source()],
            None,
            deep_research.verified_web_excerpts(validation),
        )
        self.assertIn("[1] ", sources)
        self.assertNotIn("[2] ", sources)



if __name__ == "__main__":
    unittest.main()
