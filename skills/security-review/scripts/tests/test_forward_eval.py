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

import importlib.util
import json
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
SKILL_DIR = TESTS_DIR.parents[1]
SKILL_MD = SKILL_DIR / "SKILL.md"
GOLDEN_DIR = TESTS_DIR / "golden"
EVAL_DIR = TESTS_DIR / "forward_eval"
LIVE_CMD = os.environ.get("SECURITY_REVIEW_EVAL_CMD")

# Same load-by-path convention as test_report_schema.py: `--import-mode=importlib` does not put
# this directory on sys.path, so a bare `import report_validator` would fail under pytest.
_REPORT_VALIDATOR_PATH = SKILL_DIR / "scripts" / "report_validator.py"
_spec = importlib.util.spec_from_file_location(
    "security_review_report_validator_eval", _REPORT_VALIDATOR_PATH)
report_validator = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
sys.modules[_spec.name] = report_validator
_spec.loader.exec_module(report_validator)

# Each scenario pairs a golden fixture (ground truth) with hand-authored exemplar reviews.
# Both polarities per stack: a detection-only set cannot measure over-reporting, and a
# suppression-only set cannot measure detection. The review that added the non-Go entries found
# Node and Java advertised in the frontmatter with no behavioural fixture at all.
SCENARIOS = {
    "idor_true_positive": "001_idor_missing_authz.json",
    "ssrf_false_positive": "019_ssrf_allowlisted_domain_fp.json",
    # Non-Go scenarios: exercise stack detection and the unified Domain 8 mapping.
    "python_pickle_true_positive": "021_python_pickle_rce.json",
    "python_stdlib_xxe_false_positive": "026_python_stdlib_xxe_fp.json",
    "nodejs_prototype_pollution_true_positive": "022_nodejs_prototype_pollution.json",
    "nodejs_execfile_false_positive": "023_nodejs_execfile_args_fp.json",
    "java_deserialization_true_positive": "024_java_deserialization_rce.json",
    "java_xxe_hardened_false_positive": "025_java_xxe_hardened_fp.json",
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


def _grade_false_positive(output: str, fixture: dict) -> list:
    """Grade an FP fixture on the CANDIDATE CLASS, not on the finding count.

    The first version asked "did the review report nothing at all?". Running the live eval showed
    why that is the wrong question: reviewers correctly suppressed the class under test — "the
    classic SSRF read on this code is a false positive", "shell injection really is closed" — and
    still failed, because they also reported real adjacent issues (a missing timeout, an
    unauthenticated endpoint, an unbounded body). That grader punished correct work and said
    nothing about the class it existed to measure.

    So the question is now three questions:
      1. is the fixture's `suppressed_cwe` absent from findings[]?
      2. is it present in suppressed[], citing a numbered rule?
      3. is every other reported finding in `allowed_adjacent_cwe`?

    CWE is the join key: it is machine-readable, mandatory in the contract, and immune to the
    phrasing drift that made the old prose matching fragile.
    """
    reasons = []
    data = _json_block(output)
    want_cwe = fixture.get("suppressed_cwe")
    want_class = fixture.get("suppressed_class") or fixture.get("category", "")

    if not want_cwe:
        # Fixture predates the class-scoped contract: fall back to the strict rule so an
        # unannotated FP fixture is never silently ungraded.
        if _claims_a_finding(output):
            reasons.append("FALSE POSITIVE: reported a finding on a safe fixture "
                           "(fixture declares no suppressed_cwe, so strict grading applies)")
        if not re.search(r"(?i)suppress", output):
            reasons.append("did not record the suppression explicitly")
        return reasons

    if data is None:
        # Without the JSON the class-scoped check cannot run; fall back to prose.
        if not re.search(rf"(?i){re.escape(want_class)}", output):
            reasons.append(f"no parseable JSON and the review never mentions {want_class!r}")
        if not re.search(r"(?i)suppress", output):
            reasons.append("did not record the suppression explicitly")
        return reasons

    reported = {str(f.get("cwe", "")).upper() for f in data.get("findings") or []}
    suppressed_entries = data.get("suppressed") or []

    # 1. The class under test must not be reported as a finding.
    if want_cwe.upper() in reported:
        reasons.append(
            f"FALSE POSITIVE: reported {want_cwe} ({want_class}) as a finding on a safe fixture")

    # 2. It must be recorded as an explicit, rule-cited suppression.
    suppressed_text = json.dumps(suppressed_entries) + "\n" + output
    cls = re.escape(want_class)
    # Either the machine-readable suppressed[] names the class, or prose ties the class to a
    # suppression *within one clause* — a document-wide co-occurrence would be satisfied by any
    # unrelated suppression elsewhere in the report.
    class_suppressed = (
        re.search(cls, json.dumps(suppressed_entries), re.I)
        or re.search(rf"{cls}[^.;\n]{{0,200}}?(suppress|false positive)", output, re.I)
        or re.search(rf"(suppress|false positive)[^.;\n]{{0,200}}?{cls}", output, re.I)
    )
    if not class_suppressed:
        reasons.append(f"did not record {want_class!r} as an explicit suppression")
    elif not re.search(r"(?i)suppression rule \d|\brule\s*[1-9]\b|\"rule\"\s*:\s*[1-9]",
                       suppressed_text):
        reasons.append("suppression does not cite a numbered suppression rule")

    # 3. Everything else reported must be declared allowed, or it is an unexplained over-report.
    allowed = {c.upper() for c in fixture.get("allowed_adjacent_cwe", [])}
    unexpected = sorted(c for c in reported if c and c != want_cwe.upper() and c not in allowed)
    if unexpected:
        reasons.append(
            f"OVER-REPORTED: {unexpected} are not the tested class and are not in the fixture's "
            f"allowed_adjacent_cwe {sorted(allowed)} — either the review over-reported or the "
            f"fixture needs to declare them")
    return reasons


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
    # Parsed once, up front: the TP branch below needs it to bind severity/confidence/ASVS to
    # the SPECIFIC finding object, not to "this string appears somewhere in the document".
    data = _json_block(output)
    found = _claims_a_finding(output)
    if fixture["expected_finding"]:
        if not found:
            reasons.append(f"MISSED the real vulnerability ({fixture.get('finding_pattern') or fixture['category']})")
        else:
            pattern = fixture.get("finding_pattern")
            if pattern and pattern.lower() not in low:
                reasons.append(f"finding does not name the class {pattern!r}")
            want_severity = fixture.get("severity")
            want_cwe = fixture.get("expected_cwe")
            target = None
            if data is not None and want_cwe:
                # Reported hole: a document-wide `severity\s*[:=]\s*P1` regex is satisfied by a
                # stray "Severity: P1" mentioned anywhere else in the report (an unrelated
                # finding, a prose aside), and a bare `CWE-\d+` search is satisfied by ANY CWE —
                # including a wrong one attached to the real bug (e.g. an IDOR mapped to
                # CWE-200). Locate the finding object that actually claims the expected CWE and
                # check every field on THAT object.
                target = next((f for f in data.get("findings") or []
                              if str(f.get("cwe", "")).upper() == want_cwe.upper()), None)
                if target is None:
                    reported = sorted({str(f.get("cwe", "")) for f in data.get("findings") or []})
                    reasons.append(f"no finding declares the expected CWE {want_cwe} "
                                   f"(findings[] reported: {reported or 'none'})")
            if target is not None:
                if want_severity and target.get("severity") != want_severity:
                    reasons.append(f"severity: the {want_cwe} finding is "
                                   f"{target.get('severity')!r}, expected {want_severity!r}")
                if target.get("confidence") not in ("confirmed", "likely", "suspected"):
                    reasons.append(f"the {want_cwe} finding has no valid confidence label "
                                   f"(got {target.get('confidence')!r})")
                asvs = str(target.get("asvs", ""))
                if not re.match(r"^(ASVS \d+\.\d+\.\d+ |Mapping: TBD)", asvs):
                    reasons.append(f"the {want_cwe} finding's ASVS mapping is not "
                                   f"version-pinned: {asvs!r}")
            else:
                # No parseable JSON, or the fixture predates `expected_cwe`: fall back to the
                # looser document-wide checks so an unmigrated fixture is never silently
                # ungraded. Weaker (not bound to one finding object) but better than nothing.
                if want_severity and not re.search(
                        rf'(?im)(severity\**\s*[:=]\s*\**{want_severity}\b|'
                        rf'"severity"\s*:\s*"{want_severity}")', output):
                    reasons.append(f"severity: expected {want_severity} declared on the finding")
                if not re.search(r"(?i)\b(confirmed|likely|suspected)\b", output):
                    reasons.append("no confidence label (confirmed|likely|suspected)")
                if not re.search(r"CWE-\d+", output):
                    reasons.append("no CWE mapping")
                if not re.search(r"ASVS \d+\.\d+\.\d+", output):
                    reasons.append(
                        "ASVS mapping is not version-pinned (e.g. 'ASVS 4.0.3 V4.1.2')")
    else:
        reasons.extend(_grade_false_positive(output, fixture))

    # --- Machine-readable block ---------------------------------------------------
    if data is None:
        reasons.append("no parseable machine-readable JSON summary")
    else:
        # Reported hole: this block used to check individual keys and never called the schema/
        # invariant validator at all, so a JSON with an open P1 and `summary.pass: true`, or a
        # security_domains tally of 30, validated cleanly through the grader even though
        # test_report_schema.py would have rejected the same defect. report_validator is the one
        # function both call now — see its module docstring.
        reasons.extend(f"schema/invariant violation: {e}"
                       for e in report_validator.validate_report(data))
        if "go_domains" in data:
            reasons.append("JSON uses retired `go_domains` key; must be `security_domains`")
        for key in ("stack", "asvs_version", "active_verification", "security_domains"):
            if key not in data:
                reasons.append(f"JSON missing `{key}`")
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

    # Each bad exemplar is written to fail for a SPECIFIC reason. Asserting only "it failed"
    # would pass on an incidental technicality — a missing heading, a typo'd JSON key — and prove
    # nothing about the grader's discrimination. Kept as data so a new scenario cannot be
    # registered without declaring what its bad exemplar is supposed to expose.
    INTENDED_FAILURES = {
        "idor_true_positive": ["MISSED the real vulnerability"],
        "ssrf_false_positive": ["FALSE POSITIVE"],
        # Downgrades an RCE to an input-validation nit and loads the wrong stack's sink table.
        "python_pickle_true_positive": ["does not name the class", "severity", "stack"],
        # Reports the two retired over-claims: stdlib XXE file read and stdlib expansion DoS.
        "python_stdlib_xxe_false_positive": ["FALSE POSITIVE", "suppression"],
        # Argues `Object.keys` excludes `__proto__` — plausible and wrong — and misdetects stack.
        "nodejs_prototype_pollution_true_positive": ["MISSED the real vulnerability", "stack"],
        # Treats an execFile+argv call as shell injection: the over-reporting half for Node.
        "nodejs_execfile_false_positive": ["FALSE POSITIVE", "suppression"],
        # Treats the post-hoc cast as a control, so calls RCE a P2 validation gap.
        "java_deserialization_true_positive": ["does not name the class", "severity"],
        # Reports XXE against an already-hardened factory: the over-reporting half for Java.
        "java_xxe_hardened_false_positive": ["FALSE POSITIVE", "suppression"],
    }

    def test_bad_exemplars_fail_for_the_intended_reason(self) -> None:
        """A bad exemplar that failed for an incidental reason would not prove anything."""
        for scenario, expected in self.INTENDED_FAILURES.items():
            with self.subTest(scenario=scenario):
                reasons = " | ".join(grade(_read(scenario, "bad.md"),
                                           load_fixture(SCENARIOS[scenario]))[1])
                for token in expected:
                    self.assertIn(token, reasons,
                                  f"{scenario}: bad exemplar must fail on {token!r}; "
                                  f"got: {reasons}")

    def test_every_scenario_declares_its_intended_failure(self) -> None:
        """Derived from SCENARIOS so a new scenario cannot skip the intended-reason check and
        quietly rely on 'it failed somehow'."""
        self.assertEqual(set(SCENARIOS), set(self.INTENDED_FAILURES),
                         "every registered scenario needs an INTENDED_FAILURES entry")

    # ------------------------------------------------------------------
    # Class-scoped false-positive grading. Each case below was decided WRONG by the previous
    # "must report zero findings" rule, which is why it was replaced.
    # ------------------------------------------------------------------

    def _fp_review(self, findings, suppressed_cwe="CWE-918", suppressed_class="SSRF",
                   cite_rule=True):
        """A minimal contract-compliant FP review with a chosen findings[] set."""
        rule = ', "rule": 2' if cite_rule else ""
        n = len(findings)
        return f"""Active verification: NOT permitted

## 1) Findings
{"No findings." if not n else "See below."}
The {suppressed_class} candidate is a **false positive** and is suppressed under
suppression rule 2 — the input is not attacker-controlled at the trust boundary.

## 2) Security Domain Coverage — stack: go
| # | Domain | Verdict |
|---|---|---|
| 1 | Randomness Safety | N/A |

## 3) Automation Evidence
None executed.

## 9) Uncovered Risk List
- Only the provided snippet was in scope.

```json
{{
  "summary": {{ "pass": true, "baseline": "absent" }},
  "counts": {{ "p0": 0, "p1": 0, "p2": {n}, "p3": 0, "overflow": 0 }},
  "stack": "go",
  "asvs_version": "4.0.3",
  "active_verification": "not_permitted",
  "security_domains": {{ "required": true, "total": 10, "pass": 3, "fail": 0, "na": 7 }},
  "findings": [{", ".join(
      f'{{"id": "SEC-00{i+1}", "severity": "P2", "confidence": "likely", "status": "new",'
      f' "origin": "introduced", "cwe": "{c}", "asvs": "ASVS 4.0.3 V5 (chapter-level)",'
      f' "file": "h.go:9"}}' for i, c in enumerate(findings))}],
  "suppressed": [
    {{ "candidate": "{suppressed_class} via http.Get"{rule},
      "residual_risk": "holds while the map stays a compile-time constant" }}
  ]
}}
```
"""

    def test_suppressing_the_class_while_reporting_an_allowed_adjacent_finding_passes(self) -> None:
        """The case the old rule got wrong. A live reviewer suppressed the SSRF correctly and
        reported a missing timeout; the old grader called that a false positive."""
        fixture = load_fixture(SCENARIOS["ssrf_false_positive"])
        self.assertIn("CWE-400", fixture["allowed_adjacent_cwe"])
        passed, reasons = grade(self._fp_review(["CWE-400"]), fixture)
        self.assertTrue(passed,
                        f"suppressing the tested class while reporting a declared-adjacent "
                        f"finding must pass; got {reasons}")

    def test_reporting_the_tested_class_still_fails(self) -> None:
        """The relaxation must not go too far: the class under test is still forbidden."""
        fixture = load_fixture(SCENARIOS["ssrf_false_positive"])
        _, reasons = grade(self._fp_review(["CWE-918"]), fixture)
        self.assertTrue(any("FALSE POSITIVE" in r and "CWE-918" in r for r in reasons),
                        f"reporting the suppressed class must still fail; got {reasons}")

    def test_reporting_an_undeclared_class_fails_as_over_reporting(self) -> None:
        """Not in allowed_adjacent_cwe: either the review over-reported or the fixture owes a
        declaration. Either way it must not pass silently."""
        fixture = load_fixture(SCENARIOS["ssrf_false_positive"])
        _, reasons = grade(self._fp_review(["CWE-89"]), fixture)
        self.assertTrue(any("OVER-REPORTED" in r for r in reasons),
                        f"an undeclared finding class must be flagged; got {reasons}")

    def test_silence_about_the_class_fails(self) -> None:
        """Reporting nothing is not the same as ruling the class out. A review that never
        mentions the candidate has not demonstrated suppression."""
        fixture = load_fixture(SCENARIOS["ssrf_false_positive"])
        silent = self._fp_review([]).replace(
            "The SSRF candidate is a **false positive** and is suppressed under\n"
            "suppression rule 2 — the input is not attacker-controlled at the trust boundary.",
            "Nothing of note.").replace('"candidate": "SSRF via http.Get", "rule": 2',
                                        '"candidate": "unrelated", "rule": 2')
        _, reasons = grade(silent, fixture)
        self.assertTrue(any("explicit suppression" in r for r in reasons),
                        f"silence must not pass as suppression; got {reasons}")

    def test_suppression_without_a_numbered_rule_fails(self) -> None:
        fixture = load_fixture(SCENARIOS["ssrf_false_positive"])
        out = self._fp_review([], cite_rule=False).replace("suppression rule 2 — the", "the")
        _, reasons = grade(out, fixture)
        self.assertTrue(any("numbered suppression rule" in r for r in reasons),
                        f"a bare suppression must fail; got {reasons}")

    def test_every_fp_scenario_declares_its_candidate_class(self) -> None:
        """Class-scoped grading only works if the fixture says which class is under test.
        Without it the grader silently falls back to the old strict rule."""
        missing = []
        for name, fixture_file in SCENARIOS.items():
            fixture = load_fixture(fixture_file)
            if fixture["expected_finding"]:
                continue
            if not fixture.get("suppressed_cwe") or not fixture.get("suppressed_class"):
                missing.append(name)
        self.assertEqual([], missing,
                         f"FP scenarios without suppressed_cwe/suppressed_class: {missing}")

    def test_allowed_adjacent_never_contains_the_tested_class(self) -> None:
        """A fixture that allows its own class as 'adjacent' would make the check vacuous."""
        for name, fixture_file in SCENARIOS.items():
            fixture = load_fixture(fixture_file)
            want = fixture.get("suppressed_cwe")
            if not want:
                continue
            with self.subTest(scenario=name):
                self.assertNotIn(want.upper(),
                                 {c.upper() for c in fixture.get("allowed_adjacent_cwe", [])},
                                 "the tested class must not also be allowed as adjacent")

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
        for always_on in ("scenario-checklists.md", "authorization-and-policy.md",
                          "output-contract.md"):
            self.assertIn(always_on, src,
                          f"the always-loaded reference {always_on} must be attached")

    def test_every_reference_the_contract_mandates_is_attached(self) -> None:
        """Derived, not listed: any reference SKILL.md tells the reviewer to load in order to
        *write the report* must be in the live prompt.

        This exists because splitting § Output Contract into output-contract.md removed the § 7
        field list from the prompt without breaking a single test. The live run then failed a
        correct 28k-char review on one missing JSON key — the eval was grading a contract the
        reviewer had never seen. A stack reference can legitimately be absent (only one stack
        loads at a time); a report-contract reference cannot."""
        contract_refs = {"output-contract.md", "authorization-and-policy.md"}
        attached = set(LiveForwardEval.ALWAYS_ATTACHED)
        missing = sorted(contract_refs - attached)
        self.assertEqual([], missing,
                         f"references needed to write the report but not attached: {missing}")
        refs_dir = SKILL_DIR / "references"
        for name in attached:
            self.assertTrue((refs_dir / name).is_file(), f"attached reference {name} is missing")

    def test_json_field_list_is_reachable_from_the_prompt(self) -> None:
        """The concrete failure, pinned: whichever file carries the § 7 JSON example, the live
        prompt must include it, or the grader checks keys the reviewer was never shown."""
        refs_dir = SKILL_DIR / "references"
        corpus = SKILL_MD.read_text(encoding="utf-8")
        for name in LiveForwardEval.ALWAYS_ATTACHED:
            corpus += (refs_dir / name).read_text(encoding="utf-8")
        for key in ("active_verification", "security_domains", "asvs_version", "\"stack\""):
            self.assertIn(key, corpus,
                          f"the grader requires JSON key {key} but no attached document "
                          f"mentions it")

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

    def test_every_advertised_stack_is_evaluated_in_both_polarities(self) -> None:
        """The frontmatter advertises Go, Node.js/TypeScript, Java and Python. Before this, the
        forward eval covered Go twice and Python once — so for Node and Java the skill's
        cross-language claim rested on document text alone, with no graded review behind it.

        Both polarities per stack, because a stack evaluated only on a true positive cannot show
        that its suppression rules work, and a stack evaluated only on a false positive cannot
        show that it detects anything."""
        by_stack: dict[str, set] = {}
        for fixture_file in SCENARIOS.values():
            fixture = load_fixture(fixture_file)
            by_stack.setdefault(fixture.get("stack", "go"), set()).add(
                fixture["expected_finding"])
        advertised = {"go", "nodejs", "java", "python"}
        missing = sorted(advertised - set(by_stack))
        self.assertEqual([], missing,
                         f"stacks advertised in the frontmatter with no graded scenario: {missing}")
        one_sided = sorted(s for s in advertised if by_stack[s] != {True, False})
        self.assertEqual([], one_sided,
                         f"stacks graded in only one polarity: {one_sided}")

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

    # ------------------------------------------------------------------
    # Field-binding regression tests. A review found three adversarial reports the OLD grader
    # (document-wide regex/substring checks) accepted as passing. All three must now fail, and
    # for the STATED reason — a wrong CWE, an unenforced pass/counts invariant, and a stray
    # severity mention elsewhere in the document that must not launder a wrong severity through.
    # ------------------------------------------------------------------

    def test_grader_catches_the_right_class_mapped_to_the_wrong_cwe(self) -> None:
        """The old grader's `CWE-\\d+` check was satisfied by ANY CWE in the document — so an
        IDOR correctly named and severed as P1 but tagged with the wrong CWE (e.g. CWE-200,
        information exposure, instead of CWE-639) passed anyway. Detection of the right CLASS at
        the right severity is not the same as mapping it to the right CWE, and the old grader
        could not tell the two apart."""
        good = _read("idor_true_positive", "good.md")
        wrong_cwe = good.replace('"cwe": "CWE-639"', '"cwe": "CWE-200"')
        self.assertIn('"cwe": "CWE-200"', wrong_cwe, "mutation did not apply")
        _, reasons = grade(wrong_cwe, load_fixture(SCENARIOS["idor_true_positive"]))
        self.assertTrue(
            any("expected CWE CWE-639" in r for r in reasons),
            f"grader must catch the real vulnerability being mapped to the wrong CWE; got {reasons}",
        )

    def test_grader_catches_open_p1_with_pass_true(self) -> None:
        """The old grader's JSON section checked individual keys but never called the schema/
        invariant validator, so `counts.p1: 1` alongside `summary.pass: true` — a report failing
        its own documented gate for no stated reason — validated cleanly."""
        good = _read("idor_true_positive", "good.md")
        broken = good.replace('"pass": false, "baseline": "absent"',
                              '"pass": true, "baseline": "absent"')
        self.assertIn('"pass": true, "baseline": "absent"', broken, "mutation did not apply")
        _, reasons = grade(broken, load_fixture(SCENARIOS["idor_true_positive"]))
        self.assertTrue(
            any("schema/invariant violation" in r for r in reasons),
            f"grader must reject counts.p1=1 alongside summary.pass=true; got {reasons}",
        )

    def test_grader_is_not_fooled_by_a_stray_severity_mention_elsewhere(self) -> None:
        """The old grader's severity check was `re.search(r'severity[:=]\\s*P1', output)` over
        the WHOLE document — satisfied by an unrelated "Severity: P1" appearing anywhere, such as
        a prose aside about a different, already-fixed issue. Downgrade the real finding to P3
        and plant exactly that decoy; the grader must report the real finding's actual severity,
        not be satisfied that the string 'P1' occurs somewhere."""
        good = _read("idor_true_positive", "good.md")
        downgraded = good.replace('"severity": "P1"', '"severity": "P3"') \
                         .replace("- **Severity**: P1", "- **Severity**: P3")
        self.assertIn('"severity": "P3"', downgraded, "mutation did not apply")
        decoyed = downgraded + (
            "\n\n> Note: an unrelated, already-remediated legacy finding was tracked internally "
            "as Severity: P1 last quarter and is out of scope here.\n"
        )
        _, reasons = grade(decoyed, load_fixture(SCENARIOS["idor_true_positive"]))
        self.assertTrue(
            any("CWE-639" in r and "P3" in r and "P1" in r for r in reasons),
            f"grader must report the real finding's actual severity (P3) despite the stray P1 "
            f"mention elsewhere in the document; got {reasons}",
        )


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

    def test_readme_matches_the_grader(self) -> None:
        """The README told readers the grader required `mode`, `data_basis` and a scorecard long
        after those were removed as foreign fields — so a contributor reading it would have
        written exemplars against a contract that does not exist. Pin the claim to the code."""
        readme = (EVAL_DIR / "README.md").read_text(encoding="utf-8")
        for i, line in enumerate(readme.splitlines(), 1):
            if self._is_historical(line):
                continue  # a line explaining that the fields were retired is documentation
            for foreign in ("`mode`", "`data_basis`", "scorecard present"):
                self.assertNotIn(
                    foreign, line,
                    f"forward_eval/README.md:{i} advertises the foreign contract field "
                    f"{foreign} as a requirement; the grader checks SKILL.md's own Output "
                    f"Contract sections:\n  {line.strip()}",
                )
        # And it must name what the grader actually requires.
        for mandated in ("Findings", "Security Domain Coverage", "Automation Evidence",
                         "Uncovered Risk List", "Active verification"):
            self.assertIn(mandated, readme,
                          f"README must name the mandated section {mandated!r}")

    # A line that names the retired fields in order to explain that they were removed is
    # required documentation, not a violation — the first version of the guard above forbade the
    # strings outright and therefore failed on the paragraph describing the fix.
    _HISTORY = re.compile(
        r"(?i)earlier version|retired|foreign|appear nowhere|was removed|were removed|"
        r"go-benchmark|keeps them out|drifting back")

    @classmethod
    def _is_historical(cls, line: str) -> bool:
        return bool(cls._HISTORY.search(line))

    def test_foreign_field_guard_is_not_vacuous(self) -> None:
        """Guard the guard: a line *requiring* the foreign fields must be caught, and the line
        explaining that they were retired must not be."""
        self.assertFalse(self._is_historical(
            "1. **Output contract** — `mode`, `data_basis`, `active_verification`, scorecard "
            "present."))
        self.assertTrue(self._is_historical(
            "   this list demanded `mode`, `data_basis` and a scorecard — those are the "
            "**go-benchmark** skill's fields"))

    def test_readme_lists_every_scenario(self) -> None:
        """SCENARIOS is the source of truth; the README's table must not fall behind it. It
        previously documented two scenarios while three were registered."""
        readme = (EVAL_DIR / "README.md").read_text(encoding="utf-8")
        missing = [s for s in SCENARIOS if s not in readme]
        self.assertEqual([], missing,
                         f"forward_eval/README.md does not document: {missing}")

    def test_registered_scenarios_match_disk(self) -> None:
        on_disk = {d.name for d in EVAL_DIR.iterdir()
                   if d.is_dir() and (d / "good.md").is_file()}
        self.assertEqual(on_disk, set(SCENARIOS),
                         f"unregistered forward-eval scenarios: {on_disk - set(SCENARIOS)}")


class LiveEvalHarnessTests(unittest.TestCase):
    """The reference reviewer command. Its whole value is the isolation flags: each one, if
    dropped, changes *what is measured* without producing an error — which is the failure mode
    that makes a live eval look like it validated something it did not."""

    SCRIPT = SKILL_DIR / "scripts" / "eval_live.sh"

    def test_script_exists_and_is_executable(self) -> None:
        self.assertTrue(self.SCRIPT.is_file(), f"missing {self.SCRIPT}")
        self.assertTrue(os.access(self.SCRIPT, os.X_OK),
                        "eval_live.sh must be executable; the harness runs it directly")

    def test_script_keeps_every_isolation_flag(self) -> None:
        text = self.SCRIPT.read_text(encoding="utf-8")
        for flag, why in (
            ("--strict-mcp-config", "inherited MCP servers change what the reviewer can reach"),
            ('--mcp-config \'{"mcpServers":{}}\'', "an empty server set must be supplied"),
            ("--disallowed-tools",
             "with tools the reviewer can read the fixture JSON and recall the expected verdict, "
             "and `claude -p` then prints only the final wrap-up message instead of the review"),
            ("-p", "must run non-interactively, reading the prompt from stdin"),
        ):
            self.assertIn(flag, text, f"eval_live.sh dropped {flag}: {why}")

    def test_script_does_not_use_the_ineffective_allowlist_flag(self) -> None:
        """`--allowed-tools ""` reads as "deny all" and is not: verified against the CLI, Bash
        still executed. The first version of this script used it, and two of eight live scenarios
        were consequently graded on a wrap-up message rather than a review. Deny explicitly."""
        text = self.SCRIPT.read_text(encoding="utf-8")
        for i, line in enumerate(text.splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue  # the header documents the trap on purpose
            self.assertNotRegex(
                line, r"--allowed-tools\s+\"\"",
                f"eval_live.sh:{i} uses --allowed-tools \"\", which does not disable tools",
            )
        for tool in ("Bash", "Read", "Task"):
            self.assertRegex(text, rf"--disallowed-tools[^\n]*\b{tool}\b",
                             f"the deny list must name {tool}")

    def test_script_runs_outside_any_repo(self) -> None:
        """CLAUDE.md is auto-discovered by walking up from the cwd. Run from inside this repo and
        the reviewer inherits its Go rules and constitution, so the eval measures
        'skill + host repo policy' rather than the skill."""
        text = self.SCRIPT.read_text(encoding="utf-8")
        self.assertRegex(text, r"(?m)^\s*cd \"\$\{ISOLATED\}\"",
                         "the script must cd into an isolated directory before invoking the CLI")
        self.assertIn("CLAUDE.md", text,
                      "the script must state and check the CLAUDE.md isolation requirement")
        self.assertRegex(text, r"name 'CLAUDE\.md'",
                         "isolation must be verified, not just asserted in a comment")

    def test_readme_points_at_the_script(self) -> None:
        readme = (EVAL_DIR / "README.md").read_text(encoding="utf-8")
        self.assertIn("scripts/eval_live.sh", readme,
                      "the live-eval section must point at the reference reviewer, not just say "
                      "'your-model-cli'")


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
    # Loaded for every review regardless of stack. `output-contract.md` is here because § Output
    # Contract's field detail was split out of SKILL.md: leaving it unattached silently removed
    # the § 7 JSON field list from the prompt, and a live run then produced a 28k-char correct
    # review that failed on a single missing `active_verification` key. The eval was measuring a
    # contract the reviewer had never been shown.
    ALWAYS_ATTACHED = ("scenario-checklists.md", "authorization-and-policy.md",
                       "output-contract.md")

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
                for name in (self.STACK_REFERENCE.get(stack), *self.ALWAYS_ATTACHED):
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
