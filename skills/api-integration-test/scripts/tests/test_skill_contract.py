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


# ══════════════════════════════════════════════════════════════════════════════════════
# Structural guards — added after a mutation sweep found the normative prose unpinned
# ══════════════════════════════════════════════════════════════════════════════════════

def md_section(text: str, heading: str) -> str:
    """Body under `heading`, to the next heading of the same or higher level.

    Scoping is the point. `assertIn(x, whole_document)` stays green while the occurrence
    that *decides* something is edited, as long as `x` survives anywhere else — measured:
    flipping both Skip-vs-Fail rows from `t.Fatalf` to `t.Skip`, i.e. reverting this
    skill's central CI-integrity rule to the broken form, passed all 102 tests."""
    lines = text.splitlines()
    for start, ln in enumerate(lines):
        if ln.startswith("#") and ln.lstrip("#").strip() == heading:
            level = len(ln) - len(ln.lstrip("#"))
            break
    else:
        raise AssertionError(f"heading not found: {heading!r}")
    for end in range(start + 1, len(lines)):
        nxt = lines[end]
        if nxt.startswith("#") and (len(nxt) - len(nxt.lstrip("#"))) <= level:
            return "\n".join(lines[start + 1:end])
    return "\n".join(lines[start + 1:])


def md_rows(section: str) -> list:
    """Every markdown table row in `section` as a cell list (header/separator dropped,
    `**bold**` stripped so emphasis cannot change a value)."""
    rows, seen_header = [], False
    for ln in section.splitlines():
        s = ln.strip()
        if not s.startswith("|"):
            seen_header = False
            continue
        cells = [c.strip().replace("**", "") for c in s.strip("|").split("|")]
        if set("".join(cells)) <= set("-: "):
            continue
        if not seen_header:
            seen_header = True
            continue
        rows.append(cells)
    return rows


class NormativeRuleGuardTests(unittest.TestCase):
    """Seventeen mutations were applied to this skill's documents; **twelve survived the
    full 102-test suite**. The Go safety helpers were caught every time (three layers guard
    them), but the *prose* rules that decide behaviour were not guarded at all:

    * both Skip-vs-Fail rows (`t.Fatalf` -> `t.Skip`) — the skill's signature rule,
    * `-count=1` demoted from mandatory to optional,
    * the per-mode timeouts and the retry cap,
    * the Comprehensive auto-select threshold,
    * the `//go:build integration` tag,
    * the Go version gate rows,
    * the checklists' tier bars, including the Critical one-veto rule,
    * the gate reference's fail-closed sentence.

    Each test below was confirmed to FAIL against the mutation it names before it was
    committed.
    """

    # --- Skip vs Fail: the table IS the rule ---

    SKIP_VS_FAIL = {
        "Run gate unset (`INTERNAL_API_INTEGRATION != 1`)": "`t.Skip`",
        "Gate set, a required runtime var missing/empty": "`t.Fatalf`",
        "Gate set, target is production (by ENV or host) without `INTEGRATION_ALLOW_PROD=1`": "`t.Fatalf`",
        "Gate set, destructive op without `INTEGRATION_ALLOW_DESTRUCTIVE=1`": "`t.Skip`",
        "Scaffold test (a value could not be determined at authoring time)": "`t.Skip` + `// TODO`",
    }

    def test_skip_vs_fail_table_cells_are_pinned(self) -> None:
        rows = {r[0]: r[1] for r in md_rows(md_section(SKILL_TEXT, "Skip vs Fail (CI Integrity)"))}
        self.assertEqual(set(self.SKIP_VS_FAIL), set(rows),
                         "a Skip-vs-Fail row was added or removed without being pinned")
        for situation, behavior in self.SKIP_VS_FAIL.items():
            with self.subTest(situation=situation):
                self.assertEqual(behavior, rows[situation])

    def test_skip_vs_fail_rule_is_restated_in_the_same_direction(self) -> None:
        """The prose under the table must not contradict it — an agent may read either."""
        section = md_section(SKILL_TEXT, "Skip vs Fail (CI Integrity)")
        self.assertIn('Skip = "not opted in / incomplete"', section)
        self.assertIn('Fatal = "opted in but broken or dangerous"', section)
        # Two cells say Fatal; the prose must name both of those causes.
        self.assertIn("config missing", section)
        self.assertIn("prod target unauthorized", section)

    # --- Execution integrity ---

    def test_count1_is_stated_as_mandatory_in_both_places(self) -> None:
        gate = md_section(SKILL_TEXT, "6) Execution Integrity Gate")
        self.assertIn("MUST pass `-count=1`", gate)
        self.assertIn("(cached)", gate)
        cmds = md_section(SKILL_TEXT, "Execution Commands")
        self.assertIn("**`-count=1` is mandatory on EVERY real integration run", cmds)
        self.assertNotIn("optional", cmds.split("-count=1` is mandatory")[1][:200])

    def test_every_documented_go_test_command_carries_count1(self) -> None:
        """A documented command without `-count=1` is the cached-run trap, shipped."""
        for line in SKILL_TEXT.splitlines():
            if "go test -tags=integration" in line and not line.lstrip().startswith(("-", "*", "|")):
                with self.subTest(line=line.strip()[:70]):
                    self.assertIn("-count=1", line,
                                  "documented integration command omits -count=1")

    # --- Modes: the numbers that decide scope ---

    MODE_BUDGETS = {
        "Smoke (connectivity check)": ("Timeout: 5s. No retry.", None),
        "Standard (default)": ("Timeout: 15s. Max 1 retry for transient failures only.", None),
        "Comprehensive (full coverage)": ("Timeout: 30s. Max 2 retries with bounded backoff.", None),
    }

    def test_mode_timeouts_and_retry_caps_are_pinned(self) -> None:
        for heading, (budget, _) in self.MODE_BUDGETS.items():
            with self.subTest(mode=heading):
                self.assertIn(budget, md_section(SKILL_TEXT, heading))

    def test_retry_policy_stays_bounded(self) -> None:
        pattern = md_section(SKILL_TEXT, "Required Test Pattern")
        self.assertIn("max 1-2 retries, bounded backoff, no infinite loop", pattern)
        self.assertIn("default: no retry", pattern)

    def test_comprehensive_auto_select_threshold_is_pinned(self) -> None:
        rows = md_rows(md_section(SKILL_TEXT, "4) Execution Mode Gate"))
        signals = {r[0]: r[1] for r in rows}
        self.assertIn("≥ 5 endpoints or security-sensitive API (auth/payment/PII)", signals)
        self.assertEqual("Comprehensive",
                         signals["≥ 5 endpoints or security-sensitive API (auth/payment/PII)"])
        self.assertEqual("Standard (default)", signals["Everything else"])

    # --- Build tag and version gate ---

    def test_build_tag_is_the_integration_tag_everywhere(self) -> None:
        """The tag is the isolation mechanism: rename it in one place and the CI target
        runs nothing while reporting success."""
        for text, name in ((SKILL_TEXT, "SKILL.md"),
                           (read(os.path.join(REFS_DIR, "common-integration-gate.md")),
                            "common-integration-gate.md")):
            with self.subTest(file=name):
                self.assertIn("//go:build integration", text)
                self.assertNotIn("//go:build inttest", text)
                self.assertIn("-tags=integration", text)

    GO_VERSION_GATE = {
        "`t.Setenv`": "1.17",
        "`context.WithTimeout` (no leak)": "all",
        "Range var capture fix": "1.22",
        "`t.Chdir`": "1.24",
    }

    def test_go_version_gate_rows_are_pinned(self) -> None:
        rows = {r[0]: r[1] for r in md_rows(md_section(SKILL_TEXT, "2) Go Version Gate"))}
        self.assertEqual(set(self.GO_VERSION_GATE), set(rows))
        for feature, version in self.GO_VERSION_GATE.items():
            with self.subTest(feature=feature):
                self.assertEqual(version, rows[feature])
        # t.Setenv/t.Chdir + t.Parallel panic on EVERY version — not a version gate.
        joined = " ".join(" ".join(r) for r in md_rows(md_section(SKILL_TEXT, "2) Go Version Gate")))
        self.assertIn("Panics under `t.Parallel()` on every Go version", joined)

    # --- The quality scorecard, and the fact that it is now reachable ---

    CHECKLIST_TIERS = {
        "Critical": "Any single FAIL → overall FAIL (one-veto rule)",
        "Standard": "≥ 4/5 must pass",
        "Hygiene": "≥ 3/4 must pass",
    }

    def test_checklist_tier_bars_are_pinned(self) -> None:
        text = read(os.path.join(REFS_DIR, "checklists.md"))
        for tier, rule in self.CHECKLIST_TIERS.items():
            with self.subTest(tier=tier):
                self.assertIn(f"- **{tier}**: {rule}", text)

    def test_checklist_tier_sizes_match_the_bars(self) -> None:
        """`≥ 4/5` and `≥ 3/4` must match the number of rows in those tiers, or the bar
        describes a table that does not exist."""
        text = read(os.path.join(REFS_DIR, "checklists.md"))
        quality = text.split("## Test Quality Checklist", 1)[1]
        for tier, prefix, want in (("Critical", "C", 4), ("Standard", "S", 5), ("Hygiene", "H", 4)):
            body = quality.split(f"### {tier}", 1)[1]
            ids = re.findall(rf"(?m)^\|\s*({prefix}\d+)\s*\|", body)
            with self.subTest(tier=tier):
                self.assertEqual(want, len(set(ids)), f"{tier} has {sorted(set(ids))}")

    def test_the_scorecard_is_actually_reachable(self) -> None:
        """Before this guard the word "scorecard" appeared exactly ONCE in the whole
        skill — as the H1 of `checklists.md`. The three-tier rubric was defined and then
        never applied: SKILL.md never asked for a score and the output contract never
        asked for the verdict. A rubric nothing invokes is dead weight."""
        contract = read(os.path.join(REFS_DIR, "common-output-contract.md"))
        self.assertIn("Quality scorecard verdict", contract,
                      "the output contract must require the scorecard verdict")
        self.assertIn("Critical FAIL", contract,
                      "the contract must restate the one-veto rule it is reporting")
        loading = md_section(SKILL_TEXT, "7) Load References Selectively")
        self.assertIn("checklists.md", loading)
        self.assertIn("MUST then score it", loading,
                      "SKILL.md must instruct that authored code is scored, not merely "
                      "that the checklist file may be read")

    # --- The gate reference's fail-closed rule ---

    def test_gate_reference_keeps_the_fail_closed_url_rule(self) -> None:
        gate = read(os.path.join(REFS_DIR, "common-integration-gate.md"))
        self.assertIn("absolute `http(s)` URL with a non-empty host", gate)
        self.assertIn("Checking only the parse error is a bypass", gate)
        self.assertIn("refuse non-test tenants", gate)


class ShippedSurfaceIntegrityTests(unittest.TestCase):
    """Structure and reachability of the shipped documents."""

    @classmethod
    def setUpClass(cls):
        cls.docs = {"SKILL.md": SKILL_TEXT}
        cls.docs.update({f: read(os.path.join(REFS_DIR, f))
                         for f in sorted(os.listdir(REFS_DIR)) if f.endswith(".md")})

    @staticmethod
    def unclosed_fence(text: str):
        """Return the line number of an unclosed fence, or None.

        CommonMark: a closing fence must have NO info string. So a ```bash line inside a
        ``` block is literal content, not a closer — which is how `common-integration-gate.md`
        ended up with a stray fence that swallowed its last 30 lines (23% of an always-load
        reference, including the whole Output and Message-Quality sections) as code."""
        open_at = opener_len = None
        opener_ch = ""
        for i, ln in enumerate(text.splitlines(), 1):
            m = re.match(r"^\s{0,3}(`{3,}|~{3,})(.*)$", ln)
            if not m:
                continue
            fence, info = m.groups()
            if open_at is None:
                open_at, opener_len, opener_ch = i, len(fence), fence[0]
            elif fence[0] == opener_ch and len(fence) >= opener_len and not info.strip():
                open_at = None
        return open_at

    def test_every_code_fence_is_balanced(self) -> None:
        for name, text in self.docs.items():
            with self.subTest(doc=name):
                self.assertIsNone(
                    self.unclosed_fence(text),
                    f"{name}: a fence is never closed — everything after it renders as "
                    f"code. A nested ```lang block does not close its parent; use a "
                    f"four-backtick outer fence.")

    def test_the_fence_detector_still_detects(self) -> None:
        """Synthetic input: the guard above is pinned to documents that are correct today,
        so a detector edited into one that matches nothing would pass vacuously."""
        self.assertEqual(1, self.unclosed_fence("```\nx\n"))
        self.assertIsNone(self.unclosed_fence("```\nx\n```\n"))
        # The real defect shape: an inner info-string fence is NOT a closer.
        self.assertEqual(7, self.unclosed_fence("a\n\n```\n```bash\nx\n```\n```\n"))
        self.assertIsNone(self.unclosed_fence("````text\n```bash\nx\n```\n````\n"))

    def test_every_reference_pointer_resolves(self) -> None:
        pointers = {(name, t) for name, text in self.docs.items()
                    for t in re.findall(r"references/([A-Za-z0-9._-]+\.md)", text)}
        self.assertGreaterEqual(len(pointers), 5, "the pointer regex stopped matching")
        for source, target in sorted(pointers):
            with self.subTest(source=source, target=target):
                self.assertTrue(os.path.isfile(os.path.join(REFS_DIR, target)),
                                f"{source} cites references/{target}, which does not exist")

    def test_every_intra_document_anchor_resolves(self) -> None:
        for name, text in self.docs.items():
            slugs = {re.sub(r"[^a-z0-9\s-]", "", h.lower()).strip().replace(" ", "-")
                     for h in re.findall(r"(?m)^#{1,6}\s+(.+?)\s*$", text)}
            for anchor in re.findall(r"\]\(#([A-Za-z0-9_-]+)\)", text):
                with self.subTest(doc=name, anchor=anchor):
                    self.assertIn(anchor, slugs, f"{name} links to a #{anchor} that no "
                                                 f"heading in it produces")


class ToolPermissionGuardTests(unittest.TestCase):
    """`allowed-tools` is a least-privilege AUTO-APPROVAL surface: a listed pattern runs
    with no prompt, and an unlisted command is not forbidden — it just prompts. Two things
    must hold, and both were broken:

    * every command the skill tells you to run must be matchable, or the documented
      workflow stalls on a prompt at exactly the step that matters;
    * nothing broader than the workflow needs may be pre-approved.
    """

    @staticmethod
    def bash_patterns() -> list:
        line = [ln for ln in SKILL_TEXT.splitlines() if ln.startswith("allowed-tools:")]
        assert len(line) == 1, "expected exactly one allowed-tools line"
        return re.findall(r"Bash\(([^)]*)\)", line[0])

    @staticmethod
    def matches(pattern: str, command: str) -> bool:
        """Prefix match with `*` as the only wildcard, anchored at the START of the
        command — which is the rule that broke this skill: `Bash(go test*)` does not match
        `INTERNAL_API_INTEGRATION=1 … go test …`, because the first token is an assignment."""
        return re.fullmatch(re.escape(pattern).replace(r"\*", ".*"), command, re.S) is not None

    def documented_commands(self) -> list:
        """Every runnable command line in a ```bash fence in SKILL.md."""
        out = []
        for block in re.findall(r"```bash\s*\n(.*?)```", SKILL_TEXT, re.S):
            joined = re.sub(r"\\\n\s*", " ", block)          # unfold line continuations
            for ln in joined.splitlines():
                ln = ln.strip()
                if ln and not ln.startswith(("#", "export ", "cat >", "EOF", "INTERNAL_")):
                    out.append(ln)
        return out

    def test_the_primary_run_recipe_is_auto_approved(self) -> None:
        """At least one documented way to actually run the tests must need no prompt."""
        patterns = self.bash_patterns()
        runnable = [c for c in self.documented_commands() if "run_integration.sh" in c]
        self.assertTrue(runnable, "SKILL.md documents no wrapper invocation")
        for cmd in runnable:
            with self.subTest(cmd=cmd[:70]):
                self.assertTrue(any(self.matches(p, cmd) for p in patterns),
                                f"no allowed-tools pattern matches {cmd!r}")

    def test_the_wrapper_exists_and_is_a_single_invocation(self) -> None:
        path = os.path.join(SKILL_ROOT, "scripts", "run_integration.sh")
        self.assertTrue(os.path.isfile(path), "scripts/run_integration.sh must exist")
        body = read(path)
        # Scoped to the line that actually runs go, not the file. `assertIn("-count=1",
        # body)` passed while the exec line had lost the flag, because the `echo` that
        # previews the command still carried it — the same unscoped-substring failure this
        # whole class exists to fix, committed into one of its own guards.
        execs = [ln for ln in body.splitlines() if ln.startswith("exec ") and "go test" in ln]
        self.assertEqual(1, len(execs), "expected exactly one exec'd go test line")
        self.assertIn("-count=1", execs[0],
                      "the wrapper's exec line must carry -count=1: without it Go serves a "
                      "cached result and the external service is never contacted")
        self.assertIn("-tags=integration", execs[0])
        # The preview echo must not drift from what is actually run.
        echoes = [ln for ln in body.splitlines() if ln.startswith("echo \"+ go test")]
        self.assertEqual(1, len(echoes))
        for flag in ("-tags=integration", "-run Integration", "-count=1"):
            self.assertIn(flag, echoes[0],
                          f"the previewed command omits {flag} that the real one passes")
        self.assertIn("INTERNAL_API_INTEGRATION", body,
                      "the wrapper must refuse an env file with no run gate")
        self.assertNotIn("source ", body)
        self.assertNotIn(". \"$ENV_FILE\"", body)
        self.assertIn("never `source`", body,
                      "the wrapper must say why it parses rather than sources")

    def test_skill_explains_why_the_inline_form_is_not_auto_approved(self) -> None:
        cmds = md_section(SKILL_TEXT, "Execution Commands")
        self.assertIn("first token", cmds.lower())
        self.assertIn("do not carry env vars forward", cmds)

    def test_no_overbroad_bash_pattern(self) -> None:
        """`Bash(make*)` pre-approved every target in the project's Makefile — including
        `make deploy` — for the sake of one integration target."""
        for pattern in self.bash_patterns():
            with self.subTest(pattern=pattern):
                self.assertNotIn(pattern, ("make*", "go*", "bash*", "sh*", "*"),
                                 f"`{pattern}` pre-approves far more than this skill needs")


class CoverageDocConsistencyTests(unittest.TestCase):
    """COVERAGE.md declares per-file test counts. They drifted: one line said the contract
    file had 38 `def test_*` methods while another line in the SAME file said 51 (the
    loader collects 51) — and nothing compared either number to the suite. The irony is
    that the stale line is the one asserting the counts are "regenerated from the actual
    suite each time"."""

    COVERAGE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "COVERAGE.md")

    def test_declared_counts_match_the_collected_suite(self) -> None:
        here = os.path.dirname(os.path.abspath(__file__))
        text = read(self.COVERAGE)
        declared = {
            "test_skill_contract.py": r"Actual `def test_\*` methods: (\d+)\.",
            "test_golden_scenarios.py": r"Actual `def test_\*` methods: (\d+)\.",
            "test_behavioral_integration.py": r"Actual behavioral test methods: (\d+)",
            "test_llm_skill_eval.py": r"Actual skill-output eval methods: (\d+)",
        }
        # The two identical patterns appear in file order; consume them in that order.
        generic = re.findall(r"Actual `def test_\*` methods: (\d+)\.", text)
        order = ["test_skill_contract.py", "test_golden_scenarios.py"]
        total = 0
        for i, filename in enumerate(order):
            spec = importlib.util.spec_from_file_location(
                f"_count_{i}_" + filename[:-3], os.path.join(here, filename))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            actual = unittest.defaultTestLoader.loadTestsFromModule(mod).countTestCases()
            total += actual
            self.assertEqual(actual, int(generic[i]),
                             f"COVERAGE.md says {generic[i]} tests in {filename}, loader "
                             f"collects {actual}")
        for filename in ("test_behavioral_integration.py", "test_llm_skill_eval.py"):
            m = re.search(declared[filename], text)
            self.assertIsNotNone(m, f"COVERAGE.md must declare a count for {filename}")
            spec = importlib.util.spec_from_file_location(
                "_count_" + filename[:-3], os.path.join(here, filename))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            actual = unittest.defaultTestLoader.loadTestsFromModule(mod).countTestCases()
            total += actual
            self.assertEqual(actual, int(m.group(1)),
                             f"COVERAGE.md says {m.group(1)} tests in {filename}, loader "
                             f"collects {actual}")
        m = re.search(r"\*\*(\d+) runnable test methods\*\*", text)
        self.assertIsNotNone(m, "COVERAGE.md must declare a combined total")
        self.assertEqual(total, int(m.group(1)),
                         f"COVERAGE.md total is {m.group(1)}, loader collects {total}")

    def test_no_closed_gap_is_still_listed(self) -> None:
        gaps = read(self.COVERAGE).split("## Known Gaps")[-1]
        self.assertNotIn("No live LLM-in-the-loop skill-output eval", gaps,
                         "the skill-output eval now exists; this gap is closed")


if __name__ == "__main__":
    unittest.main()
