#!/usr/bin/env python3
"""Contract tests for api-integration-test skill."""

import importlib.util
import json
import os
import re
import unittest

SKILL_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
SKILL_MD = os.path.join(SKILL_ROOT, "SKILL.md")
REFS_DIR = os.path.join(SKILL_ROOT, "references")


def load_fixture_source():
    """Return `_FIXTURE` from the sibling behavioral test, imported BY PATH.

    A bare `from test_behavioral_integration import _FIXTURE` only resolves when the tests dir is
    on sys.path — true under `unittest discover -s tests` (run_regression.sh) but NOT under
    `pytest skills/` from the repo root, where it raises ModuleNotFoundError. Loading by explicit
    path with a per-file unique module name works under both runners and avoids colliding with the
    identically-named module in the sibling thirdparty-api-integration-test skill."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_behavioral_integration.py")
    spec = importlib.util.spec_from_file_location("_sibling_" + re.sub(r"\W+", "_", path), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod._FIXTURE


def read(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()
SKILL_TEXT = read(SKILL_MD)
SKILL_LINES = SKILL_TEXT.splitlines()


def norm_func(src: str, name: str) -> str:
    """Extract a top-level Go func by name and normalize it (strip line comments +
    ALL whitespace). Uses brace DEPTH to find the true end of the function, so the
    FULL body is compared — not just up to the first inner '}'. Assumes the target
    funcs have no braces inside string literals (true for these safety helpers) and
    balanced slice/struct literals (e.g. []string{...})."""
    started, depth, out = False, 0, []
    for ln in src.splitlines():
        code = ln.split("//")[0]
        if not started:
            if ("func " + name + "(") not in ln:
                continue
            started = True
        out.append(code)
        depth += code.count("{") - code.count("}")
        if depth == 0:  # closing brace of the function body reached
            break
    return "".join("".join(out).split())


def _paren_group(s: str, open_idx: int):
    """Return the text between s[open_idx]=='(' and its matching ')', or None."""
    depth = 0
    for i in range(open_idx, len(s)):
        if s[i] == "(":
            depth += 1
        elif s[i] == ")":
            depth -= 1
            if depth == 0:
                return s[open_idx + 1:i]
    return None


def _arg_count(argstr: str) -> int:
    """Count top-level comma-separated args/params, respecting nested (){}[] and strings."""
    if argstr.strip() == "":
        return 0
    depth, count, in_str, i = 0, 1, None, 0
    while i < len(argstr):
        c = argstr[i]
        if in_str:
            if c == "\\":
                i += 2
                continue
            if c == in_str:
                in_str = None
        elif c in "\"`'":
            in_str = c
        elif c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif c == "," and depth == 0:
            count += 1
        i += 1
    return count


def go_call_arities(text: str, name: str):
    """Return (definition_arity or None, [call_arity, ...]) for a Go func `name`."""
    import re

    def_arity, calls = None, []
    for m in re.finditer(re.escape(name) + r"\(", text):
        content = _paren_group(text, m.end() - 1)
        if content is None:
            continue
        arity = _arg_count(content)
        if text[:m.start()].rstrip().endswith("func"):
            def_arity = arity
        else:
            calls.append(arity)
    return def_arity, calls


def assert_re(testcase: unittest.TestCase, pattern: str, text: str, msg: str | None = None) -> None:
    testcase.assertIsNotNone(re.search(pattern, text, re.MULTILINE), msg or f"regex not found: {pattern}")


# ── Frontmatter ──────────────────────────────────────────────


class TestFrontmatter(unittest.TestCase):
    def test_has_yaml_frontmatter(self):
        self.assertTrue(SKILL_TEXT.startswith("---"), "SKILL.md must start with YAML frontmatter")
        second = SKILL_TEXT.index("---", 3)
        self.assertGreater(second, 3, "Frontmatter must have closing ---")

    def test_has_name(self):
        assert_re(self, r"^name:\s*api-integration-test", SKILL_TEXT)

    def test_has_description(self):
        assert_re(self, r"^description:", SKILL_TEXT)

    def test_description_has_trigger_keywords(self):
        fm = SKILL_TEXT.split("---")[1]
        keywords = ["integration", "API", "Go"]
        for kw in keywords:
            self.assertIn(kw.lower(), fm.lower(), f"description missing keyword: {kw}")

    def test_has_allowed_tools(self):
        assert_re(self, r"^allowed-tools:", SKILL_TEXT)

    def test_allowed_tools_whitelist(self):
        fm = SKILL_TEXT.split("---")[1]
        match = re.search(r"allowed-tools:\s*(.+)", fm)
        self.assertIsNotNone(match, "allowed-tools line not found")
        tools = match.group(1)
        for tool in ["Read", "Grep", "Glob", "Bash"]:
            self.assertIn(tool, tools, f"allowed-tools missing {tool}")


# ── Mandatory Sections (H2 level) ───────────────────────────


class TestMandatorySections(unittest.TestCase):
    REQUIRED_HEADINGS = [
        "Goal",
        "When To Use",
        "Scope",
        "Mandatory Gates",
        "Execution Modes",
        "Required Test Pattern",
        "Anti-Examples",
        "Go Implementation Baseline",
        "Safety Rules",
        "Execution Commands",
        "Output Contract",
        "CI Integration",
    ]

    def test_has_required_heading(self):
        for heading in self.REQUIRED_HEADINGS:
            with self.subTest(heading=heading):
                assert_re(self, rf"^##\s+.*{re.escape(heading)}", SKILL_TEXT, f"Missing required heading: {heading}")


# ── Mandatory Gates ──────────────────────────────────────────


class TestMandatoryGates(unittest.TestCase):
    GATES = [
        "Scope Validation Gate",
        "Go Version Gate",
        "Configuration Completeness Gate",
        "Execution Mode Gate",
        "Production Safety Gate",
        "Execution Integrity Gate",
        "Load References Selectively",
    ]

    def test_gate_defined(self):
        for gate in self.GATES:
            with self.subTest(gate=gate):
                assert_re(self, rf"^###\s+\d+\)\s+{re.escape(gate)}", SKILL_TEXT, f"Mandatory gate not defined: {gate}")

    def test_gates_numbered_1_through_7(self):
        numbers = re.findall(r"^###\s+(\d+)\)", SKILL_TEXT, re.MULTILINE)
        expected = [str(i) for i in range(1, 8)]
        self.assertEqual(numbers, expected, f"Gates must be numbered 1-7 sequentially, got: {numbers}")

    def test_serial_dependency_stated(self):
        section = SKILL_TEXT.split("## Mandatory Gates")[1].split("\n## ")[0]
        self.assertTrue("serial" in section.lower() or "order" in section.lower())

    def test_gate_failure_blocks(self):
        section = SKILL_TEXT.split("## Mandatory Gates")[1].split("\n## ")[0]
        self.assertTrue("block" in section.lower() or "stop" in section.lower())


# ── Execution Mode Auto-Selection ────────────────────────────


class TestExecutionModes(unittest.TestCase):
    MODES = ["Smoke", "Standard", "Comprehensive"]

    def test_mode_defined(self):
        for mode in self.MODES:
            with self.subTest(mode=mode):
                assert_re(self, rf"^###\s+{mode}", SKILL_TEXT, f"Execution mode not defined: {mode}")

    def test_standard_is_default(self):
        self.assertIn("default", SKILL_TEXT.lower().split("### standard")[1].split("###")[0])

    def test_auto_selection_table_exists(self):
        gate_section = SKILL_TEXT.split("Execution Mode Gate")[1].split("###")[0]
        self.assertIn("Signal", gate_section)
        self.assertIn("Mode", gate_section)

    def test_smoke_triggers(self):
        gate_section = SKILL_TEXT.split("Execution Mode Gate")[1].split("###")[0]
        self.assertTrue("smoke" in gate_section.lower() or "connectivity" in gate_section.lower())

    def test_comprehensive_triggers(self):
        gate_section = SKILL_TEXT.split("Execution Mode Gate")[1].split("###")[0]
        self.assertTrue("comprehensive" in gate_section.lower() or "release" in gate_section.lower())

    def test_user_override(self):
        gate_section = SKILL_TEXT.split("Execution Mode Gate")[1].split("###")[0]
        self.assertTrue("user explicitly" in gate_section.lower() or "regardless" in gate_section.lower())


# ── Gates Content ────────────────────────────────────────────


class TestGateContent(unittest.TestCase):
    def test_production_gate_env(self):
        self.assertIn("INTEGRATION_ALLOW_PROD", SKILL_TEXT)

    def test_build_tag(self):
        self.assertIn("//go:build integration", SKILL_TEXT)

    def test_run_gate_env(self):
        self.assertIn("INTERNAL_API_INTEGRATION", SKILL_TEXT)

    def test_context_timeout_required(self):
        self.assertIn("context.WithTimeout", SKILL_TEXT)

    def test_execution_integrity_no_false_pass(self):
        section = SKILL_TEXT.split("Execution Integrity Gate")[1].split("###")[0]
        self.assertTrue("never" in section.lower() and ("claim" in section.lower() or "report" in section.lower()))

    def test_scope_redirect_to_unit_test(self):
        section = SKILL_TEXT.split("Scope Validation Gate")[1].split("###")[0]
        self.assertIn("$unit-test", section)

    def test_version_gate_go_mod(self):
        section = SKILL_TEXT.split("Go Version Gate")[1].split("###")[0]
        self.assertIn("go.mod", section)

    def test_version_gate_versions(self):
        section = SKILL_TEXT.split("Go Version Gate")[1].split("###")[0]
        self.assertIn("1.17", section)
        self.assertIn("1.22", section)


# ── Degradation (now in Gate 3) ──────────────────────────────


class TestDegradation(unittest.TestCase):
    LEVELS = ["Full", "Scaffold", "Blocked"]

    def test_level_defined(self):
        for level in self.LEVELS:
            with self.subTest(level=level):
                self.assertIn(level, SKILL_TEXT)

    def test_blocked_stops_execution(self):
        section = SKILL_TEXT.split("Configuration Completeness Gate")[1].split("###")[0]
        self.assertTrue("stop" in section.lower() or "STOP" in section)


# ── Anti-Examples ────────────────────────────────────────────


class TestAntiExamples(unittest.TestCase):
    def test_has_anti_examples_section(self):
        self.assertIn("Anti-Examples", SKILL_TEXT)

    def test_minimum_anti_examples(self):
        section = SKILL_TEXT.split("Anti-Examples")[1].split("## ")[0]
        numbered = re.findall(r"^\d+\.\s+\*\*", section, re.MULTILINE)
        self.assertGreaterEqual(len(numbered), 5, f"Expected ≥5 anti-examples, found {len(numbered)}")


# ── Output Contract ──────────────────────────────────────────


class TestOutputContract(unittest.TestCase):
    def test_references_output_contract(self):
        self.assertIn("common-output-contract.md", SKILL_TEXT)


# ── Reference Files ──────────────────────────────────────────


class TestReferenceFiles(unittest.TestCase):
    EXPECTED_FILES = [
        "common-integration-gate.md",
        "common-output-contract.md",
        "checklists.md",
        "internal-api-patterns.md",
    ]

    def test_reference_exists(self):
        for filename in self.EXPECTED_FILES:
            with self.subTest(filename=filename):
                path = os.path.join(REFS_DIR, filename)
                self.assertTrue(os.path.isfile(path), f"Reference file missing: {filename}")

    def test_reference_not_empty(self):
        for filename in self.EXPECTED_FILES:
            with self.subTest(filename=filename):
                path = os.path.join(REFS_DIR, filename)
                content = read(path)
                self.assertGreater(len(content.strip()), 50, f"Reference file too short: {filename}")

    def test_reference_mentioned_in_skill(self):
        for filename in self.EXPECTED_FILES:
            with self.subTest(filename=filename):
                self.assertIn(filename, SKILL_TEXT, f"Reference {filename} not mentioned in SKILL.md")


# ── Reference Loading (now in Gate 7) ───────────────────────


class TestReferenceLoading(unittest.TestCase):
    def test_gate_file_always_loads(self):
        section = SKILL_TEXT.split("Load References Selectively")[1].split("## ")[0]
        self.assertTrue("always" in section.lower() and "common-integration-gate.md" in section)

    def test_patterns_has_trigger(self):
        section = SKILL_TEXT.split("Load References Selectively")[1].split("## ")[0]
        self.assertTrue(
            "trigger" in section.lower()
            or "only when" in section.lower()
            or "http/gRPC" in section
        )


# ── Safety Rules ─────────────────────────────────────────────


class TestSafetyRules(unittest.TestCase):
    def test_no_hardcode_secrets(self):
        # Anchor on the heading, not a bare "Safety Rules" substring (which also
        # appears in code comments), so the slice is the real section.
        section = SKILL_TEXT.split("## Safety Rules")[1].split("## ")[0]
        self.assertTrue("hardcode" in section.lower() or "secret" in section.lower())

    def test_timeout_bounded(self):
        section = SKILL_TEXT.split("## Safety Rules")[1].split("## ")[0]
        self.assertTrue("timeout" in section.lower() and "bounded" in section.lower())


# ── SKILL.md Size ────────────────────────────────────────────


class TestSize(unittest.TestCase):
    def test_under_500_lines(self):
        self.assertLessEqual(
            len(SKILL_LINES),
            500,
            f"SKILL.md is {len(SKILL_LINES)} lines (max 500). Move content to references/.",
        )


class CrossFileConsistencyGuardTests(unittest.TestCase):
    """Guards for the round-4 fixes, and consistency between the SKILL.md baseline,
    the reference docs, and the behavioral fixture the tests actually run — so the
    doc and the fixture can't silently diverge."""

    @classmethod
    def setUpClass(cls):
        cls.skill = SKILL_TEXT
        cls.advanced = read(os.path.join(REFS_DIR, "advanced-patterns.md"))
        cls.gate = read(os.path.join(REFS_DIR, "common-integration-gate.md"))
        cls.fixture = read(os.path.join(os.path.dirname(__file__), "test_behavioral_integration.py"))

    # #1 — prod URL check fails CLOSED (not just on url.Parse error).
    def test_skill_prod_check_is_fail_closed(self):
        for token in ("IsAbs()", "Hostname() ==", '!= "http"', '!= "https"'):
            self.assertIn(token, self.skill, f"SKILL.md isProdTarget missing fail-closed guard: {token}")

    def test_behavioral_fixture_prod_check_matches_skill(self):
        # The fixture the behavioral tests run must carry the same hardening,
        # or a green behavioral run would not reflect the documented logic.
        for token in ("IsAbs()", "Hostname() =="):
            self.assertIn(token, self.fixture, f"behavioral fixture missing: {token}")

    # #2 — dedicated test tenant enforced in the baseline CODE, not only prose.
    def test_skill_baseline_validates_tenant(self):
        self.assertIn("TEST_TENANT_ID", self.skill)
        self.assertIn("assertTestTenant", self.skill)
        self.assertIn("assertTestTenant", self.fixture)

    # #1-cache — -count=1 mandate + (cached) rejection documented.
    def test_count1_mandate_documented(self):
        self.assertIn("-count=1", self.skill)
        self.assertIn("(cached)", self.skill)

    # #1-cache — every real integration RUN command carries -count=1.
    def test_every_integration_command_has_count1(self):
        for label, text in (("SKILL.md", self.skill), ("advanced", self.advanced), ("gate", self.gate)):
            for line in text.splitlines():
                if "go test -tags=integration" not in line:
                    continue
                # a real run command (not a prose fragment) has -run/-timeout/-v
                if any(f in line for f in ("-run ", "-timeout", "-v ")):
                    self.assertIn("-count=1", line, f"{label}: integration command missing -count=1:\n{line}")

    # #4a — the gate flowchart refuses prod with t.Fatalf, not the old t.Skip.
    def test_flowchart_prod_is_fatal_not_skip(self):
        self.assertIn("prod? env+host", self.skill)
        self.assertNotIn("ENV=prod?", self.skill)

    # #4c — the Blocked example run command carries -count=1.
    def test_blocked_command_has_count1(self):
        self.assertIn("-count=1", self.gate)

    # #3 — prove the DOC helper and the behavioral FIXTURE share identical logic,
    # not merely that some tokens are present. Compares normalized function bodies.
    def test_safety_helpers_logic_identical_doc_vs_fixture(self):
        _FIXTURE = load_fixture_source()
        for name in ("isProdTarget", "assertTestTenant", "assertDestructiveSafe"):
            doc = norm_func(self.skill, name)
            fix = norm_func(_FIXTURE, name)
            self.assertTrue(doc, f"{name} not found in SKILL.md")
            self.assertTrue(fix, f"{name} not found in the behavioral fixture")
            self.assertEqual(
                doc, fix,
                f"{name}: normalized body differs between SKILL.md and the behavioral "
                f"fixture — the doc and the tested code have drifted.\nSKILL: {doc}\nFIX:   {fix}",
            )

    # #2 — the destructive-on-prod invariant is documented (never allowed).
    def test_destructive_never_on_prod_documented(self):
        self.assertIn("forbidden against a production target", self.skill)
        self.assertIn("assertDestructiveSafe", self.skill)

    # #1 — tenant validation is fail-closed (allowlist required), not a denylist.
    def test_tenant_validation_is_fail_closed(self):
        self.assertIn("TEST_TENANT_ALLOWLIST is required", self.skill)
        # the old fail-OPEN denylist fallback must be gone
        self.assertNotIn('strings.Contains(low, "prod")', self.skill)
        # ...including the stale doc comment that described the denylist behavior.
        self.assertNotIn("fail closed on prod-looking IDs", self.skill)

    # #3 — command examples that set TEST_TENANT_ID must also provide the now-mandatory
    # TEST_TENANT_ALLOWLIST, or a copied command fails immediately.
    def test_command_examples_include_tenant_allowlist(self):
        for label, text in (("SKILL.md", self.skill), ("advanced", self.advanced), ("gate", self.gate)):
            if "TEST_TENANT_ID" in text:
                self.assertIn("TEST_TENANT_ALLOWLIST", text,
                              f"{label}: sets TEST_TENANT_ID but not the required TEST_TENANT_ALLOWLIST")

    # #2 — destructive is fail-closed on host (requires NONPROD_HOST_ALLOWLIST) and
    # folds tenant validation in.
    def test_destructive_requires_host_allowlist_and_tenant(self):
        self.assertIn("require NONPROD_HOST_ALLOWLIST", self.skill)
        # assertDestructiveSafe takes the tenant and validates it.
        self.assertIn("assertDestructiveSafe(t *testing.T, env, baseURL, tenant string)", self.skill)
        self.assertIn("assertTestTenant(t, tenant)", self.skill)

    # A helper signature change must not leave a stale call anywhere in the docs
    # (which would fail to compile). Compare every doc call site's arity to the
    # definition's — this catches the exact drift where advanced-patterns kept a
    # 3-arg assertDestructiveSafe call after the helper grew a 4th param.
    def test_helper_call_sites_match_definition_arity(self):
        corpus = "\n".join([
            self.skill, self.advanced, self.gate,
            read(os.path.join(REFS_DIR, "internal-api-patterns.md")),
            read(os.path.join(REFS_DIR, "checklists.md")),
        ])
        for name in ("assertDestructiveSafe", "assertTestTenant", "isProdTarget"):
            defn, calls = go_call_arities(corpus, name)
            self.assertIsNotNone(defn, f"{name}: no definition found in the doc corpus")
            for c in calls:
                self.assertEqual(
                    c, defn,
                    f"{name}: a doc call site passes {c} args but the definition takes "
                    f"{defn} — stale signature, would not compile",
                )


if __name__ == "__main__":
    unittest.main()
