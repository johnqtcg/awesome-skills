#!/usr/bin/env python3
"""Golden scenario tests for api-integration-test skill."""

import json
import os
import re
import unittest

SKILL_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
SKILL_MD = os.path.join(SKILL_ROOT, "SKILL.md")
REFS_DIR = os.path.join(SKILL_ROOT, "references")
GOLDEN_DIR = os.path.join(os.path.dirname(__file__), "golden")


def read(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def load_golden(name: str) -> dict:
    with open(os.path.join(GOLDEN_DIR, name), encoding="utf-8") as f:
        return json.load(f)
def all_text() -> str:
    """Concatenation of SKILL.md + all reference files for deep keyword checks."""
    parts = [read(SKILL_MD)]
    for fname in os.listdir(REFS_DIR):
        if fname.endswith(".md"):
            parts.append(read(os.path.join(REFS_DIR, fname)))
    return "\n".join(parts)


# ── Golden Scenario Tests ────────────────────────────────────


def golden_files():
    if not os.path.isdir(GOLDEN_DIR):
        return []
    return sorted(f for f in os.listdir(GOLDEN_DIR) if f.endswith(".json"))


class TestGoldenScenarios(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.all_text = all_text()

    def test_golden_scenario(self):
        for golden_file in golden_files():
            with self.subTest(golden_file=golden_file):
                scenario = load_golden(golden_file)
                name = scenario["name"]
                required_keywords = scenario["required_keywords"]
                missing = []
                for kw in required_keywords:
                    if kw.startswith("re:"):
                        pattern = kw[3:]
                        if not re.search(pattern, self.all_text, re.IGNORECASE | re.MULTILINE):
                            missing.append(kw)
                    else:
                        if kw.lower() not in self.all_text.lower():
                            missing.append(kw)
                self.assertFalse(missing, f"Scenario '{name}' missing keywords in skill corpus: {missing}")


# ── Inline Scenario Tests (no JSON dependency) ──────────────


class TestScenario_SimpleHTTPGet(unittest.TestCase):
    """Scenario: User asks for integration test of a GET /users/:id endpoint."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.all_text = all_text()

    def test_http_pattern_available(self):
        self.assertIn("http.StatusOK", self.all_text)
        self.assertIn("require.Equal", self.all_text)

    def test_success_plus_failure_paths(self):
        self.assertTrue("NotFound" in self.all_text or "StatusNotFound" in self.all_text)

    def test_context_timeout(self):
        self.assertIn("context.WithTimeout", self.all_text)

    def test_build_tag(self):
        self.assertIn("//go:build integration", self.all_text)


class TestScenario_GRPCEndpoint(unittest.TestCase):
    """Scenario: User asks for integration test of a gRPC service."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.all_text = all_text()

    def test_grpc_pattern(self):
        self.assertIn("grpc", self.all_text.lower())
        self.assertTrue("status.Code" in self.all_text or "codes.NotFound" in self.all_text)

    def test_grpc_error_assertion(self):
        self.assertIn("status.FromError", self.all_text)


class TestScenario_RetryableEndpoint(unittest.TestCase):
    """Scenario: Endpoint sometimes returns 503, needs retry logic."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.all_text = all_text()

    def test_retry_pattern(self):
        self.assertTrue("maxRetries" in self.all_text or "maxretries" in self.all_text.lower())

    def test_bounded_backoff(self):
        self.assertIn("backoff", self.all_text.lower())

    def test_context_done_check(self):
        self.assertIn("ctx.Done()", self.all_text)

    def test_transient_classification(self):
        self.assertTrue("isTransient" in self.all_text or "transient" in self.all_text.lower())

    def test_non_retryable_listed(self):
        self.assertTrue("400" in self.all_text or "Bad Request" in self.all_text)


class TestScenario_ProductionSafety(unittest.TestCase):
    """Scenario: Someone accidentally runs integration tests against production."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.all_text = all_text()
        cls.skill_text = read(SKILL_MD)

    def test_prod_gate(self):
        self.assertIn("INTEGRATION_ALLOW_PROD", self.all_text)

    def test_env_check(self):
        self.assertTrue('env == "prod"' in self.all_text or "prod" in self.all_text.lower())

    def test_skip_not_panic(self):
        self.assertIn("t.Skip", self.all_text)

    def test_destructive_gate(self):
        self.assertIn("destructive", self.skill_text.lower())


class TestScenario_MissingConfig(unittest.TestCase):
    """Scenario: Developer runs tests without setting env vars."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.all_text = all_text()

    def test_scaffold_degradation(self):
        self.assertIn("Scaffold", self.all_text)

    def test_blocked_degradation(self):
        self.assertIn("Blocked", self.all_text)

    def test_todo_markers(self):
        self.assertIn("TODO", self.all_text)

    def test_actionable_skip(self):
        self.assertIn("set INTERNAL_API_INTEGRATION=1 to run", self.all_text)


class TestScenario_CIIntegration(unittest.TestCase):
    """Scenario: Team wants to run integration tests in GitHub Actions."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.all_text = all_text()

    def test_github_actions_example(self):
        self.assertTrue("actions/checkout" in self.all_text or "github actions" in self.all_text.lower())

    def test_service_containers(self):
        self.assertIn("services:", self.all_text)

    def test_docker_compose(self):
        self.assertTrue("docker compose" in self.all_text.lower() or "docker-compose" in self.all_text.lower())

    def test_makefile_target(self):
        self.assertIn("integration-test", self.all_text)


class TestScenario_ConcurrentRequests(unittest.TestCase):
    """Scenario: Comprehensive mode tests concurrent API safety."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.all_text = all_text()

    def test_concurrent_pattern(self):
        self.assertIn("concurrent", self.all_text.lower())

    def test_goroutine_pattern(self):
        self.assertTrue("go func" in self.all_text or "goroutine" in self.all_text.lower())


class TestScenario_DataLifecycle(unittest.TestCase):
    """Scenario: Test creates data and needs cleanup."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.all_text = all_text()

    def test_cleanup_pattern(self):
        self.assertTrue("t.Cleanup" in self.all_text or "cleanup" in self.all_text.lower())

    def test_idempotent_mention(self):
        self.assertIn("idempoten", self.all_text.lower())


class TestScenario_AntiPatterns(unittest.TestCase):
    """Scenario: Verify skill teaches what NOT to do."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.all_text = all_text()

    def test_no_mock_transport(self):
        self.assertTrue("mock" in self.all_text.lower() and "not an integration test" in self.all_text.lower())

    def test_no_unstable_fields(self):
        self.assertTrue("unstable" in self.all_text.lower() or "volatile" in self.all_text.lower())

    def test_no_unbounded_retry(self):
        self.assertIn("unbounded", self.all_text.lower())


if __name__ == "__main__":
    unittest.main()
