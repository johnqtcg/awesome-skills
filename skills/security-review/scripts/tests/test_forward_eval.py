"""Forward evaluation: grade a skill-driven REVIEW of a fixture, not the skill document.

The gap this closes. Every other layer here validates artefacts:
  - test_skill_contract.py     — the documents contain the required rules
  - test_golden_reviews.py     — fixture metadata is complete and its rules exist in the docs
  - test_examples_executable.py — the GOOD example code compiles and is actually safe

None of them answers the question that matters: *given this vulnerable code, does a reviewer
driven by this skill find the bug, suppress the false positive, and emit a compliant report?*
This file adds that layer:

  1. `grade(output, fixture)` scores a review against the fixture's ground truth — detection on
     true positives, **suppression on false positives** (the harder half), severity, confidence,
     CWE, version-pinned ASVS, the authorization-gate fields, and a machine-readable JSON block
     that is stack-neutral.
  2. Hand-authored good/bad exemplars per fixture, plus a self-test proving the grader PASSES
     the good one and FAILS the bad one *for the right reasons*. This runs everywhere — pure
     Python, no toolchain, no network.
  3. `LiveForwardEval` — opt-in via SECURITY_REVIEW_EVAL_CMD. It hands the skill plus the
     fixture code to a real reviewer with no prior knowledge of the answer and grades the
     result with the same grader.

Honesty boundary, stated plainly: (1)+(2) prove the GRADER discriminates. They do not prove a
live model passes. Only (3), once configured, does that — and it is skipped by default, which
`run_regression.sh` reports as PASS WITH SKIPS rather than a bare pass.
"""

import json
import os
import re
import subprocess
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
SKILL_DIR = TESTS_DIR.parents[1]
SKILL_MD = SKILL_DIR / "SKILL.md"
GOLDEN_DIR = TESTS_DIR / "golden"
EVAL_DIR = TESTS_DIR / "forward_eval"
LIVE_CMD = os.environ.get("SECURITY_REVIEW_EVAL_CMD")

# Each scenario pairs a golden fixture (ground truth) with hand-authored exemplar reviews.
SCENARIOS = {
    "idor_true_positive": "001_idor_missing_authz.json",
    "ssrf_false_positive": "019_ssrf_allowlisted_domain_fp.json",
    # Non-Go scenario: exercises stack detection and the unified Domain 8 mapping.
    "python_pickle_true_positive": "021_python_pickle_rce.json",
}


def load_fixture(name: str) -> dict:
    return json.loads((GOLDEN_DIR / name).read_text(encoding="utf-8"))


def _json_block(output: str):
    """Return the parsed machine-readable summary, or None."""
    for m in re.finditer(r"```json\s*\n(.*?)```", output, re.S):
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and ("summary" in data or "findings" in data):
            return data
    return None


def _claims_a_finding(output: str) -> bool:
    """True when the review reports at least one real finding (not a suppression)."""
    data = _json_block(output)
    if data is not None:
        counts = data.get("counts") or {}
        if any(int(counts.get(k, 0) or 0) for k in ("p0", "p1", "p2", "p3")):
            return True
        if data.get("findings"):
            return True
        return False
    # No JSON: fall back to a SEC-nnn finding heading.
    return bool(re.search(r"(?m)^\s*(>\s*)?\**SEC-\d+", output))


def grade(output: str, fixture: dict):
    """Return (passed, reasons). Runs every check so a caller sees all shortfalls."""
    reasons = []
    low = output.lower()

    # --- Output Contract: only what SKILL.md actually mandates ---------------------
    # Grade the skill's DOCUMENTED contract. An earlier version of this grader demanded
    # `mode`, `data_basis` and a scorecard — those are the go-benchmark skill's fields and
    # appear nowhere in security-review's Output Contract, so the grader was scoring the
    # prompt that fed them in rather than the skill. MUST-at-every-depth sections are
    # 1 Findings, 2 Security Domain Coverage, 3 Automation Evidence, 7 JSON, 9 Uncovered Risk.
    for label, pattern in (
        ("§1 Findings", r"(?im)^#{0,4}\s*(1\)|1\.)?\s*\**Findings\**"),
        ("§2 Security Domain Coverage", r"(?i)Security Domain Coverage"),
        ("§3 Automation Evidence", r"(?i)Automation Evidence"),
        ("§9 Uncovered Risk List", r"(?i)Uncovered Risk List"),
    ):
        if not re.search(pattern, output):
            reasons.append(f"missing mandatory section {label}")

    # The Active Verification Authorization Gate block is mandatory before any request, and
    # its documented shape is a literal `Active verification:` line.
    if not re.search(r"(?i)active[ _]verification", output):
        reasons.append("authorization gate not addressed (no `Active verification:` state)")

    # --- Detection vs suppression (the ground truth) ------------------------------
    found = _claims_a_finding(output)
    if fixture["expected_finding"]:
        if not found:
            reasons.append(f"MISSED the real vulnerability ({fixture.get('finding_pattern') or fixture['category']})")
        else:
            pattern = fixture.get("finding_pattern")
            if pattern and pattern.lower() not in low:
                reasons.append(f"finding does not name the class {pattern!r}")
            want = fixture.get("severity")
            # Must appear as a DECLARED severity, not merely anywhere in the text: a
            # case-insensitive bare `\bP0\b` is satisfied by the JSON counts key `"p0": 0`,
            # which every report contains regardless of the verdict.
            if want and not re.search(
                    rf'(?im)(severity\**\s*[:=]\s*\**{want}\b|"severity"\s*:\s*"{want}")', output):
                reasons.append(f"severity: expected {want} declared on the finding")
            if not re.search(r"(?i)\b(confirmed|likely|suspected)\b", output):
                reasons.append("no confidence label (confirmed|likely|suspected)")
            if not re.search(r"CWE-\d+", output):
                reasons.append("no CWE mapping")
            if not re.search(r"ASVS \d+\.\d+\.\d+", output):
                reasons.append("ASVS mapping is not version-pinned (e.g. 'ASVS 4.0.3 V4.1.2')")
    else:
        if found:
            reasons.append("FALSE POSITIVE: reported a finding on a safe fixture")
        if not re.search(r"(?i)suppress", output):
            reasons.append("did not record the suppression explicitly")
        else:
            # A suppression must cite which rule justified it.
            if not re.search(r"(?i)suppression rule \d|rule [1-4]\b", output):
                reasons.append("suppression does not cite a numbered suppression rule")

    # --- Machine-readable block ---------------------------------------------------
    data = _json_block(output)
    if data is None:
        reasons.append("no parseable machine-readable JSON summary")
    else:
        if "go_domains" in data:
            reasons.append("JSON uses retired `go_domains` key; must be `security_domains`")
        for key in ("stack", "asvs_version", "active_verification", "security_domains"):
            if key not in data:
                reasons.append(f"JSON missing `{key}`")
        dom = data.get("security_domains")
        if isinstance(dom, dict) and dom.get("total") not in (10, "10"):
            reasons.append("JSON security_domains.total must be 10 (unified domain set)")
        # Stack detection: reporting the wrong stack means the wrong sink table was loaded.
        want_stack = fixture.get("stack", "go")
        got_stack = str(data.get("stack", ""))
        if want_stack not in got_stack:
            reasons.append(f"stack: reported {got_stack!r}, code is {want_stack!r}")
        # Where the fixture pins a domain, the finding must attribute it correctly.
        want_domain = fixture.get("expected_domain")
        if want_domain and fixture["expected_finding"]:
            if not re.search(rf"(?i)domain\D{{0,4}}{want_domain}\b", output):
                reasons.append(f"finding does not attribute Domain {want_domain}")

    # --- Never fabricate execution ------------------------------------------------
    av = (data or {}).get("active_verification")
    if av == "not_permitted" or re.search(r"(?i)active[_ ]verification\W{0,4}not[_ ]permitted", output):
        if re.search(r"(?i)\bI (ran|executed|sent)\b|returned 200 with|response was", output) \
                and not re.search(r"(?i)NOT executed", output):
            reasons.append("claims execution while active verification is not permitted")

    return (len(reasons) == 0, reasons)


def _read(scenario: str, name: str) -> str:
    return (EVAL_DIR / scenario / name).read_text(encoding="utf-8")


class GraderSelfTest(unittest.TestCase):
    """Prove the grader discriminates on both halves: catching the real bug, and NOT flagging
    the safe code. Over-reporting is the failure mode a keyword check can never detect."""

    def test_good_exemplars_pass(self) -> None:
        for scenario, fixture_file in SCENARIOS.items():
            with self.subTest(scenario=scenario):
                passed, reasons = grade(_read(scenario, "good.md"), load_fixture(fixture_file))
                self.assertTrue(passed, f"{scenario}: good exemplar should pass; got {reasons}")

    def test_bad_exemplars_fail(self) -> None:
        for scenario, fixture_file in SCENARIOS.items():
            with self.subTest(scenario=scenario):
                passed, reasons = grade(_read(scenario, "bad.md"), load_fixture(fixture_file))
                self.assertFalse(passed, f"{scenario}: bad exemplar must not pass")

    def test_bad_exemplars_fail_for_the_intended_reason(self) -> None:
        """A bad exemplar that failed for an incidental reason would not prove anything."""
        tp = " | ".join(grade(_read("idor_true_positive", "bad.md"),
                              load_fixture(SCENARIOS["idor_true_positive"]))[1])
        self.assertIn("MISSED the real vulnerability", tp,
                      f"true-positive bad exemplar must fail on detection; got: {tp}")

        fp = " | ".join(grade(_read("ssrf_false_positive", "bad.md"),
                              load_fixture(SCENARIOS["ssrf_false_positive"]))[1])
        self.assertIn("FALSE POSITIVE", fp,
                      f"false-positive bad exemplar must fail on over-reporting; got: {fp}")

        # Cross-language: the bad Python review downgrades an RCE to an input-validation nit,
        # and loads the wrong stack's sink table.
        py = " | ".join(grade(_read("python_pickle_true_positive", "bad.md"),
                              load_fixture(SCENARIOS["python_pickle_true_positive"]))[1])
        self.assertIn("does not name the class", py,
                      f"python bad exemplar must fail on missing the pickle class; got: {py}")
        self.assertIn("severity", py, f"must fail on the P0->P2 downgrade; got: {py}")
        self.assertIn("stack", py, f"must fail on reporting stack=go for Python; got: {py}")

    def test_live_prompt_fences_code_in_the_fixture_language(self) -> None:
        """A Python fixture inside a ```go fence biases the stack detection being graded.
        Checked statically so it holds without configuring the live hook."""
        src = Path(__file__).read_text(encoding="utf-8")
        self.assertNotRegex(
            src, r'Code under review:\\n```go\\n',
            "the live prompt hard-codes a go fence; derive it from the fixture's stack",
        )
        self.assertRegex(src, r"FENCE\s*=\s*\{", "a per-stack fence map must exist")
        for stack in ("go", "python", "nodejs", "java"):
            self.assertIn(f'"{stack}"', src, f"fence map must cover {stack}")

    def test_live_prompt_attaches_the_stack_reference(self) -> None:
        """SKILL.md alone is not the skill: Gate D's per-stack evidence lives in the lang-*
        reference, so an eval without it measures less than a real run loads."""
        src = Path(__file__).read_text(encoding="utf-8")
        self.assertRegex(src, r"STACK_REFERENCE\s*=\s*\{")
        for name in ("go-secure-coding.md", "lang-python.md", "lang-nodejs.md", "lang-java.md"):
            self.assertIn(name, src, f"stack reference map must cover {name}")
        for always_on in ("scenario-checklists.md", "authorization-and-policy.md"):
            self.assertIn(always_on, src,
                          f"the always-loaded reference {always_on} must be attached")

    def test_stack_reference_map_points_at_real_files(self) -> None:
        refs = SKILL_DIR / "references"
        for name in ("go-secure-coding.md", "lang-python.md", "lang-nodejs.md",
                     "lang-java.md", "scenario-checklists.md", "authorization-and-policy.md"):
            self.assertTrue((refs / name).is_file(), f"missing reference {name}")

    def test_scenarios_cover_more_than_one_stack(self) -> None:
        """Two Go scenarios cannot show that the unified-domain mapping works for other stacks."""
        stacks = {load_fixture(f).get("stack", "go") for f in SCENARIOS.values()}
        self.assertGreater(len(stacks), 1,
                           f"forward eval must span multiple stacks, got {stacks}")

    def test_grader_catches_retired_json_key(self) -> None:
        out = _read("idor_true_positive", "good.md").replace("security_domains", "go_domains")
        _, reasons = grade(out, load_fixture(SCENARIOS["idor_true_positive"]))
        self.assertTrue(any("go_domains" in r for r in reasons),
                        "grader must reject the retired go_domains key")

    def test_grader_catches_unpinned_asvs(self) -> None:
        out = re.sub(r"ASVS \d+\.\d+\.\d+ ", "ASVS ", _read("idor_true_positive", "good.md"))
        _, reasons = grade(out, load_fixture(SCENARIOS["idor_true_positive"]))
        self.assertTrue(any("version-pinned" in r for r in reasons),
                        "grader must reject an unpinned ASVS mapping")

    def test_grader_catches_a_missing_mandatory_section(self) -> None:
        """Anti-vacuity for the contract checks: drop §9 and grading must fail."""
        good = _read("idor_true_positive", "good.md")
        stripped = re.sub(r"(?is)##\s*9\)\s*Uncovered Risk List.*?(?=```json)", "", good)
        self.assertNotIn("Uncovered Risk List", stripped, "failed to strip §9 for the test")
        _, reasons = grade(stripped, load_fixture(SCENARIOS["idor_true_positive"]))
        self.assertTrue(any("Uncovered Risk List" in r for r in reasons),
                        "grader must require the mandatory §9 section")

    def test_grader_does_not_demand_foreign_contract_fields(self) -> None:
        """Regression guard for a real defect in this grader: it once required `mode`,
        `data_basis` and a scorecard — go-benchmark's contract fields, absent from
        security-review's Output Contract. Demanding them measured the prompt, not the skill."""
        good = _read("ssrf_false_positive", "good.md")
        for foreign in ("mode", "data.basis", "scorecard", "profiling.method"):
            # Field-style declaration only: bare-substring matching false-positives
            # ("mode" is inside "threat model").
            self.assertNotRegex(
                good, rf"(?im)^[\s>*`]*{foreign}[`*]*\s*:",
                f"exemplar declares the foreign field {foreign!r}; the grader must not need it",
            )
        passed, reasons = grade(good, load_fixture(SCENARIOS["ssrf_false_positive"]))
        self.assertTrue(passed, f"exemplar without foreign fields must pass; got {reasons}")

    def test_live_prompt_does_not_enumerate_the_contract(self) -> None:
        """The live prompt must not list the required output fields — that would hand the model
        the contract the skill is supposed to supply."""
        src = Path(__file__).read_text(encoding="utf-8")
        m = re.search(r'prompt = \((.*?)\)\n', src, re.S)
        self.assertIsNotNone(m, "live prompt not found")
        prompt_src = m.group(1)
        for leak in ("Findings", "Uncovered Risk", "security_domains", "scorecard",
                     "data_basis", "JSON block"):
            self.assertNotIn(leak, prompt_src,
                             f"live prompt leaks contract detail {leak!r} to the model")

    def test_grader_catches_fabricated_execution(self) -> None:
        good = _read("idor_true_positive", "good.md")
        forged = good.replace("Reproducer (NOT executed", "Reproducer (executed") \
                     .replace("NOT executed", "executed")
        forged += "\n\nI ran the request and it returned 200 with User B's order.\n"
        _, reasons = grade(forged, load_fixture(SCENARIOS["idor_true_positive"]))
        self.assertTrue(any("claims execution" in r for r in reasons),
                        "grader must catch fabricated execution under a closed authorization gate")


class ScenarioIntegrityTests(unittest.TestCase):
    """The scenarios must stay wired to real fixtures and keep both polarities covered."""

    def test_every_scenario_has_both_exemplars(self) -> None:
        for scenario in SCENARIOS:
            for name in ("good.md", "bad.md"):
                self.assertTrue((EVAL_DIR / scenario / name).is_file(),
                                f"missing forward_eval/{scenario}/{name}")

    def test_scenarios_reference_existing_fixtures(self) -> None:
        for scenario, fixture_file in SCENARIOS.items():
            self.assertTrue((GOLDEN_DIR / fixture_file).is_file(),
                            f"{scenario} points at a missing fixture {fixture_file}")

    def test_both_polarities_are_covered(self) -> None:
        polarities = {load_fixture(f)["expected_finding"] for f in SCENARIOS.values()}
        self.assertEqual({True, False}, polarities,
                         "forward eval must cover a true positive AND a false positive; "
                         "detection-only grading cannot measure over-reporting")

    def test_registered_scenarios_match_disk(self) -> None:
        on_disk = {d.name for d in EVAL_DIR.iterdir()
                   if d.is_dir() and (d / "good.md").is_file()}
        self.assertEqual(on_disk, set(SCENARIOS),
                         f"unregistered forward-eval scenarios: {on_disk - set(SCENARIOS)}")


@unittest.skipUnless(
    LIVE_CMD,
    "set SECURITY_REVIEW_EVAL_CMD to a shell command that reads a prompt on stdin and writes "
    "a skill-driven security review to stdout",
)
class LiveForwardEval(unittest.TestCase):
    """Opt-in: drive a real reviewer through the skill on each fixture and grade the output.

    The reviewer is given the skill and the code only — never the fixture's expected verdict —
    so detection and suppression are measured, not recalled."""

    # Fence language per stack: wrapping a Python fixture in a ```go fence biases stack
    # detection, which is one of the things being graded.
    FENCE = {"go": "go", "python": "python", "nodejs": "javascript", "java": "java"}
    # The stack reference is part of the skill package; without it the eval measures SKILL.md
    # alone, not what a real run would have loaded.
    STACK_REFERENCE = {
        "go": "go-secure-coding.md",
        "python": "lang-python.md",
        "nodejs": "lang-nodejs.md",
        "java": "lang-java.md",
    }

    def test_live_review_passes_grader(self) -> None:
        skill = SKILL_MD.read_text(encoding="utf-8")
        refs_dir = SKILL_DIR / "references"
        for scenario, fixture_file in SCENARIOS.items():
            with self.subTest(scenario=scenario):
                fixture = load_fixture(fixture_file)
                stack = fixture.get("stack", "go")
                fence = self.FENCE.get(stack, "")
                # Attach exactly the references a real run would load for this stack: the
                # stack reference, the always-on scenario checklists, and the policy file the
                # unified domains and authorization gate live in.
                attached = []
                for name in (self.STACK_REFERENCE.get(stack), "scenario-checklists.md",
                             "authorization-and-policy.md"):
                    path = refs_dir / name if name else None
                    if path and path.is_file():
                        attached.append(f"\n\n--- references/{name} ---\n"
                                        + path.read_text(encoding="utf-8"))
                # Deliberately does NOT enumerate the required fields. Naming them would
                # supply the contract the skill is supposed to carry, turning this into an
                # eval of "skill + prompt". The only added context is the authorization
                # fact, which is environmental input a real caller would also provide.
                prompt = (
                    "Perform a security review of the code below, following this skill.\n"
                    "You have NO authorization to test any live system.\n\n"
                    f"{skill}{''.join(attached)}\n\n---\n"
                    f"Code under review:\n```{fence}\n{fixture['code']}\n```\n"
                )
                proc = subprocess.run(LIVE_CMD, shell=True, input=prompt,
                                      capture_output=True, text=True, timeout=900,
                                      errors="replace")
                passed, reasons = grade(proc.stdout, fixture)
                self.assertTrue(
                    passed,
                    f"{scenario}: live review failed grading: {reasons}\n\n{proc.stdout[:2000]}",
                )


if __name__ == "__main__":
    unittest.main()
