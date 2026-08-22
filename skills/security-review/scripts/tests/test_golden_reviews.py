"""Behavioral regression tests using golden fixtures.

Each fixture defines a code scenario and whether the skill should produce
a finding or suppress it. Tests verify that SKILL.md and its reference files
contain the rules needed to handle each case correctly.

This is NOT runtime LLM testing — it validates that the *rule coverage* in
the skill documents is sufficient to produce the expected behavior.
"""

import json
import re
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[2]
SKILL_MD = SKILL_DIR / "SKILL.md"
REFERENCES_DIR = SKILL_DIR / "references"
GOLDEN_DIR = Path(__file__).resolve().parent / "golden"


class GoldenReviewTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.skill_text = SKILL_MD.read_text()
        cls.reference_texts: dict[str, str] = {}
        for ref_file in REFERENCES_DIR.glob("*.md"):
            cls.reference_texts[ref_file.name] = ref_file.read_text()
        cls.all_text = cls.skill_text + "\n".join(cls.reference_texts.values())

    def _load(self, filename: str) -> dict:
        with open(GOLDEN_DIR / filename) as f:
            return json.load(f)

    # Loaded for every review regardless of stack, so a rule living here is genuinely in scope.
    ALWAYS_LOADED = ("scenario-checklists.md", "authorization-and-policy.md",
                     "severity-calibration.md", "anti-examples.md", "security-review.md",
                     "reference-index.md")
    # The per-stack sink reference a review of that stack loads (reference-index.md § routing).
    STACK_REFERENCE = {
        "go": "go-secure-coding.md",
        "nodejs": "lang-nodejs.md",
        "java": "lang-java.md",
        "python": "lang-python.md",
    }

    def _in_scope_text(self, fixture: dict) -> str:
        """The documents a reviewer of THIS fixture's stack would actually have loaded.

        Previously this checked the concatenation of every reference, so a Node fixture's
        `prototype pollution` rule was satisfied by a mention in an unrelated file while
        lang-nodejs.md spelled it `Prototype pollution` — the fixture claimed coverage the
        reviewer of that stack would never have been shown. Scope the search instead."""
        names = list(self.ALWAYS_LOADED)
        names.append(self.STACK_REFERENCE[fixture.get("stack", "go")])
        ref = fixture.get("reference", "")
        if ref.startswith("references/"):
            names.append(ref.split("/", 1)[1])
        parts = [self.skill_text]
        parts += [self.reference_texts[n] for n in names if n in self.reference_texts]
        return "\n".join(parts)

    def _assert_coverage(self, fixture: dict) -> None:
        """Every coverage_rule must appear in the documents this fixture's stack loads."""
        scoped = self._in_scope_text(fixture)
        for rule in fixture.get("coverage_rules", []):
            if rule in scoped:
                continue
            elsewhere = sorted(n for n, t in self.reference_texts.items() if rule in t)
            self.fail(
                f"[{fixture['id']}] coverage rule {rule!r} is not in the documents a "
                f"{fixture.get('stack', 'go')} review loads"
                + (f" — it only appears in {elsewhere}, which this stack never reads. "
                   "Check the casing, or move the rule." if elsewhere
                   else " — it appears in no document at all.")
            )

    def _assert_anti_example(self, fixture: dict) -> None:
        """Every anti_example_pattern must appear in skill (suppression rules)."""
        for pattern in fixture.get("anti_example_patterns", []):
            self.assertIn(
                pattern,
                self.all_text,
                f"[{fixture['id']}] anti-example missing: {pattern!r}",
            )

    def _assert_reference(self, fixture: dict) -> None:
        """Referenced file must exist."""
        ref = fixture.get("reference", "")
        if ref.startswith("references/"):
            filename = ref.split("/", 1)[1]
            self.assertIn(
                filename,
                self.reference_texts,
                f"[{fixture['id']}] reference file missing: {ref}",
            )

    # ------------------------------------------------------------------
    # True-positive cases (should produce a finding)
    # ------------------------------------------------------------------

    def test_001_idor_missing_authz(self) -> None:
        f = self._load("001_idor_missing_authz.json")
        self.assertTrue(f["expected_finding"])
        self.assertEqual(f["severity"], "P1")
        self._assert_coverage(f)
        self._assert_reference(f)

    def test_003_hardcoded_secret(self) -> None:
        f = self._load("003_hardcoded_secret.json")
        self.assertTrue(f["expected_finding"])
        self.assertEqual(f["severity"], "P1")
        self._assert_coverage(f)

    def test_005_sql_injection_concat(self) -> None:
        f = self._load("005_sql_injection_concat.json")
        self.assertTrue(f["expected_finding"])
        self.assertEqual(f["severity"], "P1")
        self._assert_coverage(f)

    def test_007_toctou_balance_race(self) -> None:
        f = self._load("007_toctou_balance_race.json")
        self.assertTrue(f["expected_finding"])
        self.assertEqual(f["severity"], "P1")
        self._assert_coverage(f)

    def test_008_resp_body_not_closed(self) -> None:
        f = self._load("008_resp_body_not_closed.json")
        self.assertTrue(f["expected_finding"])
        self.assertEqual(f["severity"], "P2")
        self._assert_coverage(f)

    def test_009_jwt_alg_none(self) -> None:
        f = self._load("009_jwt_alg_none.json")
        self.assertTrue(f["expected_finding"])
        self.assertEqual(f["severity"], "P1")
        self._assert_coverage(f)
        self._assert_reference(f)

    def test_010_path_traversal(self) -> None:
        f = self._load("010_path_traversal.json")
        self.assertTrue(f["expected_finding"])
        self.assertEqual(f["severity"], "P1")
        self._assert_coverage(f)
        self._assert_reference(f)

    def test_011_dockerfile_root(self) -> None:
        f = self._load("011_dockerfile_root.json")
        self.assertTrue(f["expected_finding"])
        self.assertEqual(f["severity"], "P2")
        self._assert_coverage(f)
        self._assert_reference(f)

    def test_012_concurrent_map_write(self) -> None:
        f = self._load("012_concurrent_map_write.json")
        self.assertTrue(f["expected_finding"])
        self.assertEqual(f["severity"], "P1")
        self._assert_coverage(f)
        self._assert_reference(f)

    def test_013_maxbytesreader_missing(self) -> None:
        f = self._load("013_maxbytesreader_missing.json")
        self.assertTrue(f["expected_finding"])
        self.assertEqual(f["severity"], "P2")
        self._assert_coverage(f)
        self._assert_reference(f)

    def test_014_text_template_xss(self) -> None:
        f = self._load("014_text_template_xss.json")
        self.assertTrue(f["expected_finding"])
        self.assertEqual(f["severity"], "P1")
        self._assert_coverage(f)
        self._assert_reference(f)

    def test_015_open_redirect(self) -> None:
        f = self._load("015_open_redirect.json")
        self.assertTrue(f["expected_finding"])
        self.assertEqual(f["severity"], "P2")
        self._assert_coverage(f)
        self._assert_reference(f)

    # ------------------------------------------------------------------
    # False-positive cases (should NOT produce a finding)
    # ------------------------------------------------------------------

    def test_002_parameterized_sql_fp(self) -> None:
        f = self._load("002_parameterized_sql_fp.json")
        self.assertFalse(f["expected_finding"])
        self._assert_anti_example(f)

    def test_004_insecure_skip_verify_test_fp(self) -> None:
        f = self._load("004_insecure_skip_verify_test_fp.json")
        self.assertFalse(f["expected_finding"])
        self._assert_anti_example(f)

    def test_006_math_rand_non_security_fp(self) -> None:
        f = self._load("006_math_rand_non_security_fp.json")
        self.assertFalse(f["expected_finding"])
        self._assert_anti_example(f)
        self._assert_coverage(f)

    # ------------------------------------------------------------------
    # New true-positive cases: SSRF, Timing Attack, Integer Overflow
    # ------------------------------------------------------------------

    def test_016_ssrf_user_controlled_url(self) -> None:
        f = self._load("016_ssrf_user_controlled_url.json")
        self.assertTrue(f["expected_finding"])
        self.assertEqual(f["severity"], "P1")
        self._assert_coverage(f)
        self._assert_reference(f)

    def test_017_timing_attack_api_key(self) -> None:
        f = self._load("017_timing_attack_api_key.json")
        self.assertTrue(f["expected_finding"])
        self.assertEqual(f["severity"], "P2")
        self._assert_coverage(f)
        self._assert_reference(f)

    def test_018_integer_overflow_financial(self) -> None:
        f = self._load("018_integer_overflow_financial.json")
        self.assertTrue(f["expected_finding"])
        self.assertEqual(f["severity"], "P1")
        self._assert_coverage(f)
        self._assert_reference(f)

    def test_019_ssrf_allowlisted_domain_fp(self) -> None:
        f = self._load("019_ssrf_allowlisted_domain_fp.json")
        self.assertFalse(f["expected_finding"])
        self._assert_anti_example(f)
        self._assert_coverage(f)

    def test_020_constant_time_compare_correct_fp(self) -> None:
        f = self._load("020_constant_time_compare_correct_fp.json")
        self.assertFalse(f["expected_finding"])
        self._assert_anti_example(f)
        self._assert_coverage(f)

    def test_021_python_pickle_rce(self) -> None:
        """Non-Go fixture: the rule references must resolve in the Python reference, and the
        canonical Domain 8 name must be the one used — that is what makes the unified numbering
        real rather than table-deep."""
        f = self._load("021_python_pickle_rce.json")
        self.assertTrue(f["expected_finding"])
        self.assertEqual("P0", f["severity"], "pickle.loads on untrusted input is RCE, not P1")
        self.assertEqual("python", f["stack"])
        self.assertEqual(8, f["expected_domain"])
        self._assert_coverage(f)
        self._assert_reference(f)
        # The pinned domain must be named canonically in the stack reference the fixture cites.
        lang_ref = (REFERENCES_DIR / "lang-python.md").read_text()
        self.assertRegex(
            lang_ref, r"\|\s*8\s*\|\s*Language-Specific Injection Sinks\s*\|",
            "fixture pins Domain 8; lang-python.md must name it canonically",
        )

    # ------------------------------------------------------------------
    # Node.js and Java: the two stacks the skill claimed to cover with no behavioural fixture
    # ------------------------------------------------------------------

    def test_022_nodejs_prototype_pollution(self) -> None:
        f = self._load("022_nodejs_prototype_pollution.json")
        self.assertTrue(f["expected_finding"])
        self.assertEqual("P1", f["severity"],
                         "prototype pollution reaching an authorization read is P1, not a nit")
        self.assertEqual("nodejs", f["stack"])
        self.assertEqual(8, f["expected_domain"])
        self._assert_coverage(f)
        self._assert_reference(f)
        lang_ref = (REFERENCES_DIR / "lang-nodejs.md").read_text()
        self.assertRegex(lang_ref, r"\|\s*8\s*\|\s*Language-Specific Injection Sinks\s*\|",
                         "fixture pins Domain 8; lang-nodejs.md must name it canonically")

    def test_023_nodejs_execfile_args_fp(self) -> None:
        f = self._load("023_nodejs_execfile_args_fp.json")
        self.assertFalse(f["expected_finding"])
        self.assertEqual("nodejs", f["stack"])
        self._assert_anti_example(f)
        self._assert_coverage(f)
        self._assert_reference(f)

    def test_024_java_deserialization_rce(self) -> None:
        f = self._load("024_java_deserialization_rce.json")
        self.assertTrue(f["expected_finding"])
        self.assertEqual("P0", f["severity"],
                         "readObject on untrusted bytes is RCE via classpath gadgets")
        self.assertEqual("java", f["stack"])
        self.assertEqual(8, f["expected_domain"])
        self._assert_coverage(f)
        self._assert_reference(f)
        lang_ref = (REFERENCES_DIR / "lang-java.md").read_text()
        self.assertRegex(lang_ref, r"\|\s*8\s*\|\s*Language-Specific Injection Sinks\s*\|",
                         "fixture pins Domain 8; lang-java.md must name it canonically")

    def test_025_java_xxe_hardened_fp(self) -> None:
        """Java XXE applies by default, which is what makes an already-hardened factory the
        valuable false positive: the pattern match fires and the exploit does not."""
        f = self._load("025_java_xxe_hardened_fp.json")
        self.assertFalse(f["expected_finding"])
        self.assertEqual("java", f["stack"])
        self._assert_anti_example(f)
        self._assert_coverage(f)
        self._assert_reference(f)

    # ------------------------------------------------------------------
    # Python XML: the corrected version-gated guidance, in both polarities
    # ------------------------------------------------------------------

    def test_026_python_stdlib_xxe_fp(self) -> None:
        """Guards the correction of two over-claims at once: stdlib XXE file read and stdlib
        entity-amplification DoS. Both are false positives on a patched Expat."""
        f = self._load("026_python_stdlib_xxe_fp.json")
        self.assertFalse(f["expected_finding"])
        self.assertEqual("python", f["stack"])
        self._assert_anti_example(f)
        self._assert_coverage(f)
        self._assert_reference(f)
        lang_ref = (REFERENCES_DIR / "lang-python.md").read_text()
        self.assertRegex(lang_ref, r"(?i)Entity amplification[\s\S]{0,140}?\*\*No\*\*",
                         "the FP fixture depends on the doc stating that entity amplification "
                         "does not reach a build past the 2.4.0 gate")

    def test_026_declares_the_version_its_verdict_depends_on(self) -> None:
        """An FP fixture whose verdict is version-gated must show the version in the code, or it
        is undecidable and a correct reviewer can legitimately disagree with the ground truth.

        This is not hypothetical: without the pin, a live reviewer reported allocation
        amplification (CVE-2025-59375, live below Expat 2.7.2) against the then-unbounded body —
        a real finding, on a fixture asserting expected_finding=false."""
        f = self._load("026_python_stdlib_xxe_fp.json")
        code = f["code"]
        self.assertIn("2.7.2", code,
                      "the fixture must state the gate its 'no finding' verdict rests on")
        self.assertRegex(code, r"(?i)expat[_ ]?2\.7\.[2-9]",
                         "the pinned Expat must actually be at or past the CVE-2025-59375 fix")
        self.assertRegex(code, r"MAX_BODY|len\(body\)",
                         "the body must be bounded; an unbounded body leaves a genuine "
                         "resource-exhaustion finding reachable regardless of Expat")

    def test_python_fixture_code_parses(self) -> None:
        """Fixture code is read as code by anyone reviewing this skill. A NameError-level slip
        (the 026 body cap once raised HTTPException without importing it) undermines the fixture
        it lives in."""
        import ast

        for path in sorted(GOLDEN_DIR.glob("*.json")):
            fixture = json.loads(path.read_text(encoding="utf-8"))
            if fixture.get("stack") != "python":
                continue
            with self.subTest(fixture=fixture["id"]):
                try:
                    tree = ast.parse(fixture["code"])
                except SyntaxError as exc:
                    self.fail(f"{fixture['id']} code does not parse: {exc}")
                # Every bare name used as a call target should be imported or defined.
                imported = {
                    alias.asname or alias.name.split(".")[0]
                    for node in ast.walk(tree)
                    if isinstance(node, (ast.Import, ast.ImportFrom))
                    for alias in node.names
                }
                assigned = {
                    t.id for node in ast.walk(tree)
                    if isinstance(node, ast.Assign)
                    for t in node.targets if isinstance(t, ast.Name)
                }
                defined = {n.name for n in ast.walk(tree)
                           if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
                known = imported | assigned | defined | set(dir(__builtins__)) | {
                    "self", "app", "list", "len", "dict"}
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                        self.assertIn(
                            node.func.id, known,
                            f"{fixture['id']}: calls {node.func.id!r} which is never imported "
                            f"or defined — the fixture would NameError",
                        )

    def test_027_python_lxml_iterparse_xxe(self) -> None:
        """The other polarity: the one Python XML default that IS exploitable. A skill that
        suppresses both polarities is as wrong as one that reports both."""
        f = self._load("027_python_lxml_iterparse_xxe.json")
        self.assertTrue(f["expected_finding"])
        self.assertEqual("python", f["stack"])
        self.assertEqual(8, f["expected_domain"])
        self._assert_coverage(f)
        self._assert_reference(f)
        lang_ref = (REFERENCES_DIR / "lang-python.md").read_text()
        self.assertIn("CVE-2026-41066", lang_ref)
        self.assertIn("6.1.0", lang_ref, "the fix version is what makes the pin actionable")
        self.assertIn("lxml==6.0.2", f["code"],
                      "the fixture must show the pin, or the version gate is unresolvable "
                      "from the code and the finding could only be graded `likely`")

    def test_python_xml_fixtures_are_a_matched_pair(self) -> None:
        """A single-polarity pair would let the skill pass by always suppressing (or always
        reporting) Python XML. Both fixtures must exist and disagree."""
        fp = self._load("026_python_stdlib_xxe_fp.json")
        tp = self._load("027_python_lxml_iterparse_xxe.json")
        self.assertEqual("xxe", fp["category"])
        self.assertEqual("xxe", tp["category"])
        self.assertNotEqual(fp["expected_finding"], tp["expected_finding"],
                            "the XML pair must cover both polarities of the same category")

    def test_each_fixture_binds_to_its_own_stack_reference(self) -> None:
        """Scoping the coverage search to the loaded set is not enough on its own: a Node
        fixture's rule can still be satisfied by an always-loaded file (reference-index.md
        *mentions* prototype pollution) while the substantive rule in lang-nodejs.md is spelled
        differently and never actually matched. Require at least one rule to land in the stack's
        own sink table, which is where Domain 8 is decided.

        Applies only to fixtures that pin `expected_domain` — those are the ones claiming to
        exercise a Gate D domain. A fixture without one (IDOR, JWT, open redirect, container) is
        a *scenario checklist* case whose rules correctly live in scenario-checklists.md, which
        is why this is not a blanket rule."""
        unbound = []
        for path in sorted(GOLDEN_DIR.glob("*.json")):
            fixture = json.loads(path.read_text(encoding="utf-8"))
            rules = fixture.get("coverage_rules", [])
            if not rules or "expected_domain" not in fixture:
                continue
            stack_ref = self.STACK_REFERENCE[fixture.get("stack", "go")]
            text = self.reference_texts.get(stack_ref, "")
            if not any(rule in text for rule in rules):
                unbound.append(f"{fixture['id']} ({stack_ref}): {rules}")
        self.assertEqual([], unbound,
                         "no coverage rule lands in the stack's own sink reference, so these "
                         f"fixtures do not test that stack's Domain 8 table: {unbound}")

    def test_every_supported_stack_has_a_behavioural_fixture(self) -> None:
        """The review that prompted these fixtures found 20 Go fixtures, 1 Python, 0 Node,
        0 Java — while the frontmatter advertised all four stacks. Derived from disk so a newly
        advertised stack cannot ship without one."""
        advertised = {"go", "nodejs", "java", "python"}
        seen = {}
        for path in sorted(GOLDEN_DIR.glob("*.json")):
            fixture = json.loads(path.read_text(encoding="utf-8"))
            seen.setdefault(fixture.get("stack", "go"), set()).add(fixture["expected_finding"])
        self.assertEqual(set(), advertised - set(seen),
                         f"stacks advertised in the frontmatter with no golden fixture: "
                         f"{sorted(advertised - set(seen))}")
        both = {stack for stack, polarities in seen.items() if polarities == {True, False}}
        self.assertEqual(set(), advertised - both,
                         f"stacks with only one polarity — detection-only or suppression-only "
                         f"coverage cannot measure over-reporting: {sorted(advertised - both)}")

    # ------------------------------------------------------------------
    # Fixture integrity
    # ------------------------------------------------------------------

    def test_every_fixture_has_a_scenario_specific_test(self) -> None:
        """GOLDEN-021 was added, listed in COVERAGE.md and used by the forward eval, but had no
        test_021_* — so it only ever got the generic field checks. This makes that impossible:
        a new fixture must be named by its own test."""
        source = Path(__file__).read_text(encoding="utf-8")
        missing = []
        for path in sorted(GOLDEN_DIR.glob("*.json")):
            num = path.name.split("_", 1)[0]
            if not re.search(rf"def test_{num}_\w+", source):
                missing.append(path.name)
        self.assertFalse(
            missing,
            "fixtures with no scenario-specific golden test (generic field checks only): "
            f"{missing}",
        )

    def test_all_fixtures_have_required_fields(self) -> None:
        required = {"id", "title", "expected_finding", "category", "code"}
        for path in sorted(GOLDEN_DIR.glob("*.json")):
            with open(path) as fp:
                data = json.load(fp)
            missing = required - data.keys()
            self.assertFalse(
                missing,
                f"{path.name} missing required fields: {missing}",
            )

    def test_positive_fixtures_have_severity(self) -> None:
        for path in sorted(GOLDEN_DIR.glob("*.json")):
            with open(path) as fp:
                data = json.load(fp)
            if data["expected_finding"]:
                self.assertIn(
                    "severity",
                    data,
                    f"{path.name}: positive fixture must specify severity",
                )

    def test_fixture_ids_are_unique(self) -> None:
        ids = []
        for path in sorted(GOLDEN_DIR.glob("*.json")):
            with open(path) as fp:
                data = json.load(fp)
            ids.append(data["id"])
        self.assertEqual(len(ids), len(set(ids)), f"duplicate fixture IDs: {ids}")

    def test_fixture_severities_are_valid(self) -> None:
        valid = {"P0", "P1", "P2", "P3"}
        for path in sorted(GOLDEN_DIR.glob("*.json")):
            with open(path) as fp:
                data = json.load(fp)
            if "severity" in data:
                self.assertIn(
                    data["severity"],
                    valid,
                    f"{path.name}: invalid severity {data['severity']!r}",
                )


if __name__ == "__main__":
    unittest.main()
