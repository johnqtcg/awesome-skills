"""Forward evaluation: grade a produced DOCUMENT, not the presence of keywords in the skill.

The gap this closes. `test_golden_scenarios.py` asserts that each fixture's
`skill_must_contain` strings appear somewhere in the concatenation of SKILL.md and every
reference. That proves a rule is *written down*; it cannot distinguish a skill that works from
one that merely documents the right words. None of the existing layers check whether a run:

  - picked the right doc type,
  - landed in the expected degradation level and said which resolution step got it there,
  - loaded the right reference,
  - produced a document that survives the mechanical scorecard (`lint_doc.py`),
  - and, in Improve mode, changed only what was flagged instead of rewriting.

This file grades exactly those, by running `lint_doc.py` over the emitted document and diffing
Improve-mode output against the original.

  1. `grade(output, fixture)` → (passed, reasons).
  2. Hand-authored good/bad exemplars per scenario, plus a self-test proving the grader passes
     the good one and fails the bad one *for the intended reason*. Pure stdlib, deterministic.
  3. `LiveForwardEval` — opt-in via TECH_DOC_EVAL_CMD; drives a real writer through the skill
     and grades the result with the same grader.

Honesty boundary: (1)+(2) prove the GRADER discriminates. Only (3), once configured, shows that
a live model does. It is skipped by default, and run_regression.sh reports that as a gap.
"""

import difflib
import json
import math
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
LINTER = SKILL_DIR / "scripts" / "lint_doc.py"
LIVE_CMD = os.environ.get("TECH_DOC_EVAL_CMD")

SCENARIOS = {
    "runbook_write": "001_write_api_runbook.json",
    "audience_unknown": "004_audience_unknown_degradation.json",
    "improve_minimal_diff": "006_improve_existing_doc.json",
    # Review and Level-3 exercise machinery the other three never touch: severity-grouped
    # findings with before/after, and scaffold integrity (TODO placeholders, no fabrication).
    "review_troubleshooting": "002_review_troubleshooting_doc.json",
    "scaffold_level3": "005_insufficient_info_scaffold.json",
}

DOC_TYPES = ("concept", "task", "reference", "troubleshooting", "design")


def load_fixture(name: str) -> dict:
    return json.loads((GOLDEN_DIR / name).read_text(encoding="utf-8"))


def read(scenario: str, name: str) -> str:
    return (EVAL_DIR / scenario / name).read_text(encoding="utf-8")


DOC_BEGIN = "<!-- BEGIN DOCUMENT -->"
DOC_END = "<!-- END DOCUMENT -->"


def extract_document(output: str):
    """Return the emitted markdown document.

    Delimiter choice matters. The first version used a non-greedy ```` ```markdown … ``` ````
    match, which stops at the document's **first inner fence** — a runbook full of ```bash
    blocks was truncated at the first one (measured: 94 lines in, 25 lines out), so Rollback,
    Verification, and most commands never reached the linter. The layer claimed to run the
    mechanical gate over the whole document while checking only its opening.

    Accepted forms, most explicit first:
      1. `<!-- BEGIN DOCUMENT -->` … `<!-- END DOCUMENT -->`  — cannot collide with fences
      2. a four-backtick fence, which legally contains triple-backtick blocks
      3. a ```markdown fence matched to its LAST closing fence, not its first
      4. bare frontmatter onward
    """
    if DOC_BEGIN in output and DOC_END in output:
        return output.split(DOC_BEGIN, 1)[1].split(DOC_END, 1)[0].strip("\n")

    m = re.search(r"````(?:markdown|md)?\s*\n(.*?)\n````", output, re.S)
    if m:
        return m.group(1)

    # Greedy to the last fence: an inner ```bash must not terminate the outer block.
    m = re.search(r"```(?:markdown|md)\s*\n(.*)\n```", output, re.S)
    if m:
        return m.group(1)

    m = re.search(r"(?ms)^---\s*$.*", output)
    return m.group(0) if m else None


def _load_lint_doc():
    """Import lint_doc.py so the grader checks claimed denominators against the SAME table the
    skill's tooling uses. Without this the arithmetic was decorative: `99/99 applicable` passed."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("lint_doc", LINTER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def document_conditions(doc: str) -> dict:
    """Decide each scorecard `when …` condition FROM THE DOCUMENT.

    Accepting any denominator inside min..max was too weak: for a concept doc both `2/2` and
    `2/3` passed, so the check could not tell whether a conditional item genuinely applied.
    These predicates make the denominator exact."""
    lint_doc = _load_lint_doc()
    text = doc or ""
    fm, body, _off = lint_doc.split_frontmatter(text)
    return {
        # A diagram is a mermaid block, an embedded image, or an explicit figure reference.
        # Flags go in the `flags=` argument: an inline `(?im)` mid-pattern is a PatternError
        # on modern Python.
        "diagrams present": bool(
            re.search(r"```mermaid|!\[[^\]]*\]\(|^\s*(figure|diagram)\s*\d*\s*[:.]",
                      text, re.I | re.M)),
        # Version-sensitive iff the body pins a concrete version (same rule the linter uses).
        "version-sensitive": bool(lint_doc.VERSION_MENTION_RE.search(body)),
        # Error codes apply to an API reference: HTTP statuses or a machine-readable code column.
        "api doc": bool(
            re.search(r"(?i)\b(HTTP\s*status|status\s*code|error\s*code)s?\b|\b[45]\d{2}\b", text)),
    }


def applicable_bounds(tier: str, doc_type, doc: str | None = None):
    """Return (min_denominator, max_denominator) for a tier at this doc type.

    With `doc` supplied, each conditional item is resolved against the document, so min == max
    and the denominator is checked as a fact rather than a range. Without it (no document to
    inspect, e.g. Review mode) the permissive range is returned."""
    lint_doc = _load_lint_doc()
    conditions = document_conditions(doc) if doc is not None else None
    base = cond = 0
    for _name, types, condition in lint_doc.SCORECARD[tier]:
        in_scope = types == "all" or (doc_type in types if doc_type else True)
        if not in_scope:
            continue
        if condition:
            if conditions is None:
                cond += 1
            elif conditions.get(condition):
                base += 1          # the condition holds, so the item is applicable
        else:
            base += 1
    return base, base + cond


# Field-value gap tolerance.
#
# The Output Contract in SKILL.md column-aligns its values (`mode:` followed by eleven spaces),
# and the grader's original `\W{0,6}` could not span that padding — so the grader was unable to
# match the format the skill itself prescribes. It had been written against the bullet-list
# shape the static exemplars happen to use, and because the live eval had never run against a
# model, nothing compared the two. A model that followed the contract exactly was reported as
# having declared no mode, no doc type and no resolution path.
#
# `[^\w\n]` rather than `\W` keeps the match on one line: `\W` matches newlines, so a generous
# bound would let a key on one line pair with an unrelated value further down.
GAP = r"[^\w\n]{0,24}"

# Defined once and shared with the guard test below. A test that re-types the pattern it is
# meant to pin proves only that the copy is self-consistent — which is precisely how the grader
# drifted away from the Output Contract unnoticed.
MODE_RE = re.compile(rf"(?im)^{GAP}mode{GAP}(write|review|improve)")
# `doc(?:ument)? ` required a SPACE, and `\btype` cannot match inside `doc_type` because `_` is a
# word character — so the grader never matched the Output Contract's real field name, only the
# prose forms `type:` and `doc type:`. `[ _]?` covers all three.
DOC_TYPE_RE = re.compile(
    rf"(?i)\b(?:doc(?:ument)?[ _]?)?type{GAP}(?P<dt>{'|'.join(DOC_TYPES)})\b")
RESOLUTION_RE = re.compile(rf"(?i)resolution{GAP}R[123]")


# `(?:^|\|)` rather than `^`: SKILL.md's contract puts two tiers on one line separated by `|`
# (`Critical: 4/4 applicable (1 N/A) | Standard: 5/5 applicable |`), and a line-anchored pattern
# saw only the first of them — so a model following the contract was reported as having omitted
# the Standard tier. The optional `scorecard` prefix covers the first tier sharing its line with
# the field label. Both shapes matter: the aligned contract form and the exemplars' bullet form.
SCORE_CLAIM_RE = re.compile(
    r"(?im)(?:^|\|)[\s\-*>]*(?:scorecard[^\w\n]{0,24})?\**(Critical|Standard|Hygiene)\**\s*[:：]?\s*"
    r"(?:.*?\b(\d+)\s*/\s*(\d+)\s*applicable|.*?\bn/a\s*\(0 applicable\))"
)


def check_scorecard_arithmetic(output: str, doc_type, doc: str | None = None):
    """Verify the reported numbers, not merely that numbers were reported."""
    reasons = []
    claims = SCORE_CLAIM_RE.findall(output)
    if not claims:
        return ["scorecard lacks the applicable-item arithmetic (`N/M applicable`)"]
    seen = set()
    for tier, num, den in claims:
        seen.add(tier)
        if not den:  # the `n/a (0 applicable)` form
            lo, _hi = applicable_bounds(tier, doc_type, doc)
            if lo != 0:
                reasons.append(f"{tier}: claimed 0 applicable but {lo} are applicable")
            continue
        n, m = int(num), int(den)
        if n > m:
            reasons.append(f"{tier}: claimed {n}/{m} — numerator exceeds denominator")
        # Only range-check when the doc type is known: with no type every item counts as
        # applicable, which reported correct concept-doc arithmetic as wrong.
        if doc_type:
            lo, hi = applicable_bounds(tier, doc_type, doc)
            if lo == hi:
                # Exact: every conditional item was resolved against the document.
                if m != lo:
                    reasons.append(
                        f"{tier}: claimed denominator {m} but this {doc_type} document has "
                        f"exactly {lo} applicable items "
                        f"(conditions resolved from the document: "
                        f"{', '.join(k for k, v in document_conditions(doc).items() if v) or 'none hold'})")
            elif not (lo <= m <= hi):
                reasons.append(
                    f"{tier}: claimed denominator {m} but {doc_type} docs have "
                    f"{lo}..{hi} applicable items — the arithmetic does not match the scorecard")
        if tier != "Critical":
            need = math.ceil(m * 2 / 3) if m else 0
            # The verdict must be the explicit uppercase PASS/FAIL, not the lowercase "pass"
            # inside "N/M applicable pass" — matching that read a declared FAIL as a PASS.
            verdict = re.search(
                rf"{tier}[^\n]*?\b{n}\s*/\s*{m}\b[^\n]*?(?:→|->|:)\s*\**(PASS|FAIL)\b",
                output)
            if verdict and verdict.group(1) == "PASS" and n < need:
                reasons.append(
                    f"{tier}: claims PASS at {n}/{m} but ⅔ of {m} requires {need}")
    for tier in ("Critical", "Standard", "Hygiene"):
        if tier not in seen:
            reasons.append(f"scorecard does not report the {tier} tier")
    return reasons


def run_linter(doc: str, doc_type, tmp: Path):
    """Return (returncode, stdout) from lint_doc.py over the emitted document.

    Deliberately *not* passing `--today`: the document was written moments ago and should carry
    today's date, so the system clock is the right reference. Pinning a date here would report a
    correctly-dated fresh document as post-dated. This stays safe only because staleness is a
    warning and the grader gates on criticals — promoting staleness to critical would make this
    date-dependent, so pin `--today` at that point.

    `tmp` is a system temp directory, outside any repository, so no `.techdocrc.json` is
    discovered and the emitted document is always graded against the default conventions.
    """
    path = tmp / "emitted.md"
    path.write_text(doc, encoding="utf-8")
    argv = [sys.executable, str(LINTER), str(path)]
    if doc_type in DOC_TYPES:
        argv += ["--type", doc_type]
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=60, errors="replace")
    return proc.returncode, proc.stdout


def grade(output: str, fixture: dict, tmp: Path, requested=None):
    """Return (passed, reasons); runs every check so all shortfalls are visible.

    `requested` is the set of reference filenames the writer actually asked for over the `LOAD:`
    protocol, and is supplied only by the live harness. Pass it whenever the observation exists:
    citing a path proves the writer typed the path, not that it ever read the file. Measured with
    `STUB_MODE=no_load` — a stub that skipped `LOAD:` entirely and emitted the known-good
    exemplar still passed, because the exemplar's own prose names the reference. `None` means the
    observation is unavailable (static exemplars have no protocol turn), and the check falls back
    to citation only."""
    reasons = []
    low = output.lower()

    # 1. Mode declared and correct.
    want_mode = fixture["expected_mode"]
    m = MODE_RE.search(output)
    if not m:
        reasons.append("no mode declared (Write|Review|Improve)")
    elif m.group(1).lower() != want_mode.lower():
        reasons.append(f"mode: declared {m.group(1)!r}, expected {want_mode!r}")

    # 2. Doc type: must be stated, and match when the fixture pins one.
    want_type = fixture.get("expected_doc_type")
    stated = DOC_TYPE_RE.search(output)
    if want_type:
        if not stated:
            reasons.append(f"doc type not stated (expected {want_type!r})")
        elif stated.group("dt").lower() != want_type.lower():
            reasons.append(f"doc type: stated {stated.group("dt")!r}, expected {want_type!r}")
    elif not stated and not re.search(
            r"(?i)stop|clarif|not yet determined|undetermined|which .{0,20}\?|"
            r"tell me|what I need from you|type-neutral", output):
        # Ambiguous fixture: either state a type, or visibly hold it open and ask.
        reasons.append("ambiguous request: neither a doc type nor a request for clarification")

    # 3. Resolution path + degradation level (the state machine being deterministic is the
    #    whole point of §Resolution Order — an ungrounded level claim is what it replaced).
    if not RESOLUTION_RE.search(output):
        reasons.append("no `Resolution: R1|R2|R3` path recorded")
    want_level = fixture.get("expected_level")
    if want_level:
        if not re.search(rf"(?i)level\s*{want_level}\b", output):
            reasons.append(f"expected degradation Level {want_level} to be declared")
        if want_level == 2 and "audience:" not in low and "assumed" not in low:
            reasons.append("Level 2 requires the audience assumption to be labelled")

    # Extract once, up front: the scorecard check needs the document to resolve each
    # conditional scorecard item (diagrams present? version-sensitive? API doc?).
    doc = extract_document(output)

    # 4. Reference actually loaded, when the fixture names one.
    ref = fixture.get("reference_to_load")
    if ref:
        if ref not in output:
            reasons.append(f"did not cite the reference it should have loaded ({ref})")
        if requested is not None and Path(ref).name not in {Path(w).name for w in requested}:
            reasons.append(
                f"cited {ref} but never requested it over the LOAD protocol — the file was "
                f"never supplied, so the citation is unverified "
                f"(requested: {sorted(requested) or 'nothing'})")

    # 5. Scorecard reported WITH arithmetic, and the arithmetic must be RIGHT.
    if "scorecard" not in low:
        reasons.append("no scorecard reported")
    else:
        # When the fixture does not pin a type, score against the type the response DECLARED —
        # the scorecard must be internally consistent with its own classification. Passing
        # None here made every item count as applicable, so a correct concept-doc scorecard
        # was reported as wrong.
        effective_type = want_type or (stated.group("dt").lower() if stated else None)
        reasons += check_scorecard_arithmetic(output, effective_type, doc)

    # 6. Behavioral: the emitted document must survive the mechanical linter.
    if doc is None:
        if fixture["expected_mode"].lower() != "review":
            reasons.append("no emitted document found (```markdown block or frontmatter)")
    else:
        code, lint_out = run_linter(doc, want_type, tmp)
        if code != 0:
            first = next((l for l in lint_out.splitlines() if l.startswith("[critical]")), "")
            reasons.append(f"emitted document fails lint_doc.py critical checks: {first}")

    # 6b. Review mode emits findings, not a document: require severity grouping and before/after.
    if fixture["expected_mode"].lower() == "review":
        grouped = re.search(
            r"\b(critical|standard|hygiene)\b.{0,40}\b(finding|issue)s?\b"
            r"|^#{1,4}\s*(critical|standard|hygiene)\b",
            output, re.I | re.M)
        if not grouped:
            reasons.append("Review output is not grouped by severity tier")
        evidence = re.search(
            r"before\s*(/|→|->|and)\s*after|^\s*[-*]\s*before\s*:", output, re.I | re.M)
        if not evidence:
            reasons.append("Review findings lack before/after evidence")

    # 6c. Scaffold (Level 3) integrity: placeholders present, nothing invented.
    for needle in fixture.get("must_contain_in_document", []):
        if doc is not None and needle not in doc:
            reasons.append(f"scaffold must contain {needle!r} rather than invented content")
    if fixture.get("expected_level") == 3 and doc is not None:
        for token in fixture.get("must_not_fabricate", []):
            # A concrete value next to one of these words means content was invented.
            m = re.search(rf"(?i)\b{token}\b\D{{0,12}}(\d{{2,}}|v\d+\.\d+)", doc)
            if m:
                reasons.append(
                    f"scaffold fabricated a concrete {token} ({m.group(0)!r}); Level 3 must use "
                    "TODO placeholders")

    # 7. Improve mode: minimal diff. Rewriting passing sections is the failure mode.
    if fixture["expected_mode"].lower() == "improve" and doc is not None:
        original = fixture.get("original_document")
        if original:
            before, after = original.splitlines(), doc.splitlines()
            changed = sum(1 for d in difflib.unified_diff(before, after, n=0)
                          if d[:1] in "+-" and not d.startswith(("+++", "---")))
            budget = fixture.get("max_changed_lines", max(8, len(before) // 3))
            if changed > budget:
                reasons.append(
                    f"Improve mode changed {changed} lines (budget {budget}) — minimal-diff "
                    "means fixing what the scorecard flagged, not rewriting")
            if changed == 0:
                reasons.append("Improve mode changed nothing; the fixture has real defects")
            # Stronger than the line count: content the fixture marks as already-correct must
            # survive byte-for-byte. A rewrite reformats it even when the line count fits.
            for keep in fixture.get("must_survive_verbatim", []):
                if keep not in doc:
                    reasons.append(
                        f"Improve mode altered content that was already correct: {keep!r} — "
                        "preserve passing sections verbatim")

    return (len(reasons) == 0, reasons)


class GraderSelfTest(unittest.TestCase):
    """Prove the grader discriminates on each scenario."""

    def setUp(self):
        import tempfile
        self.tmp = Path(tempfile.mkdtemp(prefix="tdw-eval-"))
        self.addCleanup(__import__("shutil").rmtree, self.tmp, ignore_errors=True)

    def test_grader_accepts_the_contract_format_skill_md_prescribes(self):
        """The exemplars are hand-written, so they can drift from the contract they illustrate.

        They use a compact `mode: Write` bullet shape. SKILL.md's Output Contract column-aligns
        its values, and the grader's `\\W{0,6}` gap could not span eleven spaces of padding — so a
        model that followed the contract *exactly* was reported as declaring no mode, no doc type
        and no resolution path, and the first scorecard tier (which shares its line with the
        `scorecard:` label) went undetected. Nothing caught it because the exemplars never used
        the aligned form and the live eval had never been run.

        This test builds the block from SKILL.md's own template shape, so the grader and the
        contract cannot drift apart again.
        """
        block = (
            "── tech-doc-writer output ──\n"
            "mode:           Write\n"
            "resolution:     R1 (retrieved) — CONTRIBUTING.md names the on-call rota\n"
            "degradation:    Level 1 (Full)\n"
            "doc_type:       task\n"
            "audience:       backend dev / deploy service / knows Docker\n"
            "scorecard:      Critical: 4/4 applicable (1 N/A) | Standard: 5/5 applicable |\n"
            "                Hygiene: 3/3 applicable (2 conditional)\n"
            "files:          [docs/deploy.md]\n"
            "maintenance:    cadence: monthly; triggers: deploy script change\n"
            "assumptions:    [none]\n")

        self.assertRegex(block, MODE_RE,
                         "grader must match the aligned `mode:` field SKILL.md prescribes")
        self.assertRegex(block, DOC_TYPE_RE,
                         "grader must match the `doc_type:` field name, not only `type:`")
        self.assertEqual("task", DOC_TYPE_RE.search(block).group("dt"))
        self.assertRegex(block, RESOLUTION_RE,
                         "grader must match the aligned `resolution:` field")
        tiers = {tier for tier, _n, _d in SCORE_CLAIM_RE.findall(block)}
        self.assertEqual(
            {"Critical", "Standard", "Hygiene"}, tiers,
            "all three tiers must be detected, including the one sharing a line with "
            f"the `scorecard:` label — got {sorted(tiers)}")

    def test_good_exemplars_pass(self):
        for scenario, fx in SCENARIOS.items():
            with self.subTest(scenario=scenario):
                passed, reasons = grade(read(scenario, "good.md"), load_fixture(fx), self.tmp)
                self.assertTrue(passed, f"{scenario}: good exemplar should pass; got {reasons}")

    def test_bad_exemplars_fail(self):
        for scenario, fx in SCENARIOS.items():
            with self.subTest(scenario=scenario):
                passed, _ = grade(read(scenario, "bad.md"), load_fixture(fx), self.tmp)
                self.assertFalse(passed, f"{scenario}: bad exemplar must not pass")

    def test_bad_exemplars_fail_for_the_intended_reason(self):
        r = " | ".join(grade(read("runbook_write", "bad.md"),
                             load_fixture(SCENARIOS["runbook_write"]), self.tmp)[1])
        self.assertIn("lint_doc.py critical", r,
                      f"runbook bad exemplar must fail the mechanical gate; got: {r}")

        a = " | ".join(grade(read("audience_unknown", "bad.md"),
                             load_fixture(SCENARIOS["audience_unknown"]), self.tmp)[1])
        self.assertIn("Resolution", a,
                      f"audience bad exemplar must fail on the missing resolution path; got: {a}")

        i = " | ".join(grade(read("improve_minimal_diff", "bad.md"),
                             load_fixture(SCENARIOS["improve_minimal_diff"]), self.tmp)[1])
        self.assertIn("minimal-diff", i.lower(),
                      f"improve bad exemplar must fail on diff size; got: {i}")

        r = " | ".join(grade(read("review_troubleshooting", "bad.md"),
                             load_fixture(SCENARIOS["review_troubleshooting"]), self.tmp)[1])
        self.assertIn("severity tier", r,
                      f"review bad exemplar must fail on ungrouped findings; got: {r}")
        self.assertIn("before/after", r,
                      f"review bad exemplar must fail on missing evidence; got: {r}")

        s = " | ".join(grade(read("scaffold_level3", "bad.md"),
                             load_fixture(SCENARIOS["scaffold_level3"]), self.tmp)[1])
        self.assertTrue(
            any("fabricated" in x or "TODO" in x for x in s.split(" | ")),
            f"scaffold bad exemplar must fail on invented content; got: {s}")

    def test_review_and_scaffold_exercise_distinct_machinery(self):
        """The first three scenarios never touch severity grouping or scaffold integrity."""
        modes = {load_fixture(f)["expected_mode"].lower() for f in SCENARIOS.values()}
        self.assertIn("review", modes, "Review mode must be graded")
        levels = {load_fixture(f).get("expected_level") for f in SCENARIOS.values()}
        self.assertIn(3, levels, "Level 3 scaffold must be graded")

    def test_grader_catches_a_bare_scorecard_verdict(self):
        """The N/A denominator fix is only real if the arithmetic is required in output."""
        good = read("runbook_write", "good.md")
        stripped = re.sub(r"\d+\s*/\s*\d+\s*applicable", "PASS", good)
        _, reasons = grade(stripped, load_fixture(SCENARIOS["runbook_write"]), self.tmp)
        self.assertTrue(any("arithmetic" in r for r in reasons),
                        "grader must reject a scorecard without applicable-item arithmetic")

    def test_extraction_survives_inner_code_fences(self):
        """Regression for the worst defect in this layer: a non-greedy ```markdown match stopped
        at the document's FIRST inner fence, so a runbook full of ```bash blocks was truncated
        (measured 94 lines in, 25 out) and Rollback/Verification never reached the linter."""
        good = read("runbook_write", "good.md")
        doc = extract_document(good)
        self.assertIsNotNone(doc)
        self.assertIn("## Rollback", doc,
                      "extraction truncated before Rollback — inner fences are ending the block")
        self.assertIn("## Verification", doc)
        self.assertGreater(len(doc.splitlines()), 60,
                           f"extracted only {len(doc.splitlines())} lines; the document is longer")
        # The delimiter must not be a plain triple-backtick fence for exactly this reason.
        self.assertIn(DOC_BEGIN, good,
                      "exemplars must use the explicit document delimiter")

    def test_extraction_handles_a_bare_triple_fence_greedily(self):
        """Fallback path: if a response does wrap in ```markdown, match to the LAST fence."""
        wrapped = ("intro\n\n```markdown\n---\ntitle: T\n---\n\n# T\n\n"
                   "```bash\necho hi\n```\n\n## Tail\n\ndone\n```\n\ntrailing\n")
        doc = extract_document(wrapped)
        self.assertIn("## Tail", doc, "greedy match must reach past the inner bash fence")

    def test_grader_rejects_fabricated_scorecard_arithmetic(self):
        """`99/99 applicable` used to pass: only the presence of digits was checked."""
        good = read("runbook_write", "good.md")
        for forged in ("99/99 applicable", "88/88 applicable"):
            mutated = re.sub(r"\d+/\d+ applicable", forged, good)
            passed, reasons = grade(mutated, load_fixture(SCENARIOS["runbook_write"]), self.tmp)
            # Assert the rejection, not its wording: the exact-denominator branch reports
            # "exactly N applicable items" while the range branch reports a permitted span.
            self.assertFalse(
                passed, f"grader accepted fabricated arithmetic {forged!r}")
            self.assertTrue(
                any(t in r for t in ("Critical", "Standard", "Hygiene") for r in reasons),
                f"rejection of {forged!r} did not name the offending tier: {reasons}")

    def test_denominator_is_exact_not_a_range(self):
        """Checking only min..max accepted both `2/2` and `2/3` for the same concept document, so
        it could not tell whether a conditional item genuinely applied. Conditions are now
        resolved from the document, making the denominator a fact."""
        good = read("audience_unknown", "good.md")
        fx = load_fixture(SCENARIOS["audience_unknown"])
        doc = extract_document(good)
        lo, hi = applicable_bounds("Hygiene", "concept", doc)
        self.assertEqual(lo, hi, "with a document supplied the denominator must be exact")

        passed, _ = grade(good, fx, self.tmp)
        self.assertTrue(passed, "the correct denominator must still pass")
        for wrong in ("2/3 applicable", "3/3 applicable", "2/4 applicable"):
            mutated = good.replace("- **Hygiene**: 2/2 applicable", f"- **Hygiene**: {wrong}")
            _, reasons = grade(mutated, fx, self.tmp)
            self.assertTrue(
                any("exactly" in r for r in reasons),
                f"grader accepted an inflated denominator {wrong!r}: {reasons}")

    def test_conditions_are_derived_from_the_document(self):
        """The three `when …` conditions must be decided by inspecting the document."""
        self.assertTrue(document_conditions("```mermaid\ngraph TD\n```")["diagrams present"])
        self.assertTrue(document_conditions("![arch](a.png)")["diagrams present"])
        self.assertFalse(document_conditions("no visuals here")["diagrams present"])

        self.assertTrue(document_conditions("Requires Redis 7.2.1")["version-sensitive"])
        self.assertFalse(document_conditions("Requires Redis")["version-sensitive"])

        self.assertTrue(document_conditions("Returns 404 on miss")["api doc"])
        self.assertFalse(document_conditions("a prose paragraph")["api doc"])

    def test_diagram_condition_changes_the_denominator(self):
        """Adding a diagram must move the Hygiene denominator, or the condition is decorative."""
        without = applicable_bounds("Hygiene", "concept", "plain prose")[0]
        with_diagram = applicable_bounds("Hygiene", "concept", "```mermaid\ngraph TD\n```")[0]
        self.assertEqual(without + 1, with_diagram,
                         "a document containing a diagram must gain the diagram Hygiene item")

    def test_grader_rejects_a_pass_below_the_two_thirds_threshold(self):
        good = read("runbook_write", "good.md")
        mutated = good.replace("**Standard**: 5/5 applicable pass", "**Standard**: 1/5 applicable pass")
        _, reasons = grade(mutated, load_fixture(SCENARIOS["runbook_write"]), self.tmp)
        self.assertTrue(any("requires" in r for r in reasons),
                        f"grader accepted PASS below the ⅔ threshold: {reasons}")

    def test_grader_requires_all_three_tiers(self):
        good = read("runbook_write", "good.md")
        mutated = re.sub(r"(?m)^- \*\*Hygiene\*\*.*$", "", good)
        _, reasons = grade(mutated, load_fixture(SCENARIOS["runbook_write"]), self.tmp)
        self.assertTrue(any("Hygiene tier" in r for r in reasons),
                        f"a missing tier must be reported: {reasons}")

    def test_grader_catches_a_rewrite_that_fits_the_line_budget(self):
        """Line count alone is gameable; content marked already-correct must survive verbatim."""
        good = read("improve_minimal_diff", "good.md")
        mutated = good.replace(
            "kubectl scale deploy/payment-worker --replicas=0 -n payments",
            "kubectl -n payments scale deployment payment-worker --replicas=0")
        _, reasons = grade(mutated, load_fixture(SCENARIOS["improve_minimal_diff"]), self.tmp)
        self.assertTrue(any("already correct" in r for r in reasons),
                        f"reformatting a correct command must be flagged: {reasons}")

    def test_grader_catches_wrong_doc_type(self):
        good = read("runbook_write", "good.md")
        wrong = re.sub(r"(?i)(type\W{0,6})task", r"\1concept", good, count=1)
        _, reasons = grade(wrong, load_fixture(SCENARIOS["runbook_write"]), self.tmp)
        self.assertTrue(any("doc type" in r for r in reasons),
                        "grader must reject a misclassified doc type")


class ScenarioIntegrityTests(unittest.TestCase):
    def test_every_scenario_has_both_exemplars(self):
        for scenario in SCENARIOS:
            for name in ("good.md", "bad.md"):
                self.assertTrue((EVAL_DIR / scenario / name).is_file(),
                                f"missing forward_eval/{scenario}/{name}")

    def test_scenarios_reference_existing_fixtures(self):
        for scenario, fx in SCENARIOS.items():
            self.assertTrue((GOLDEN_DIR / fx).is_file(), f"{scenario} -> missing {fx}")

    def test_registered_scenarios_match_disk(self):
        on_disk = {d.name for d in EVAL_DIR.iterdir()
                   if d.is_dir() and (d / "good.md").is_file()}
        self.assertEqual(on_disk, set(SCENARIOS),
                         f"unregistered scenarios: {on_disk - set(SCENARIOS)}")

    def test_scenarios_cover_the_three_modes_that_differ(self):
        """Write, degradation, and Improve exercise different machinery; grading only one of
        them would leave the others' rules unverified."""
        modes = {load_fixture(fx)["expected_mode"].lower() for fx in SCENARIOS.values()}
        self.assertIn("write", modes)
        self.assertIn("improve", modes)

    def test_improve_scenario_carries_its_original(self):
        """Minimal-diff cannot be measured without the pre-edit document."""
        fx = load_fixture(SCENARIOS["improve_minimal_diff"])
        self.assertIn("original_document", fx,
                      "the Improve fixture must embed the original for diff measurement")
        self.assertIn("max_changed_lines", fx)


# The run context the fixtures were written against, stated explicitly.
#
# Found by finally pointing the harness at a live model: fixture 004 expects Level 2 and says so
# in as many words — "R1 retrieval finds nothing and R2 asking is unavailable, so R3 assumes" —
# but the prompt never told the writer either of those things. A live model therefore did the
# *correct* thing under §Resolution Order (one consolidated question, R2) and was graded as
# failing all six checks. The stub could never surface this: it replays a stored document and
# never consults the resolution rules at all.
RUN_CONTEXT = """\
--- run context (this is a non-interactive batch evaluation) ---
- There is NO repository, codebase, or doc corpus available. R1 retrieval is a no-op; say so.
- You CANNOT ask the user anything: this is a batch run and there is no second party to answer.
  Per §Resolution Order this satisfies "cannot ask", so R2 is unavailable and you proceed to R3.
- Do not use tools or explore the filesystem. Answer from the request and the skill alone.
- Emit the complete document plus the output-contract block in your reply.
"""


@unittest.skipUnless(
    LIVE_CMD,
    "set TECH_DOC_EVAL_CMD to a shell command that reads a prompt on stdin and writes the "
    "skill-driven response to stdout",
)
class LiveForwardEval(unittest.TestCase):
    """Opt-in: drive a real writer through the skill and grade the document it produces.

    The prompt carries the skill, the references a real run would load, and the user request —
    never the fixture's expected mode/type/level, so classification is measured not recalled."""

    def test_live_output_passes_grader(self):
        """References are offered, not pre-loaded.

        Attaching every reference up front made the progressive-disclosure rule untestable — the
        model could not fail to "load only what it needs" because everything was already in the
        prompt. Instead the prompt lists the available reference files and a fetch protocol, so
        the response has to name what it wants. Any reference the fixture pins as required is
        supplied on the second turn if requested; the set of files actually requested is passed
        into `grade`, so a fixture that pins a reference fails when the writer cites it without
        ever asking for it. That distinction is the point: until the request set was threaded
        through, `STUB_MODE=no_load` passed all five scenarios."""
        import tempfile
        skill = SKILL_MD.read_text(encoding="utf-8")
        refs = SKILL_DIR / "references"
        available = "\n".join(f"  - references/{p.name}" for p in sorted(refs.glob("*.md")))
        attached = (
            "\n\n--- available references (NOT pre-loaded) ---\n"
            f"{available}\n"
            "To read one, emit a line `LOAD: references/<name>` before your answer; the contents "
            "will be supplied and you may then answer. Load only what the task needs.\n")
        for scenario, fx in SCENARIOS.items():
            with self.subTest(scenario=scenario):
                fixture = load_fixture(fx)
                request = fixture["user_request"]
                if fixture.get("original_document"):
                    request += ("\n\nExisting document:\n```markdown\n"
                                + fixture["original_document"] + "\n```")
                prompt = (f"{skill}{attached}\n{RUN_CONTEXT}\n---\nUser request: {request}\n")
                proc = subprocess.run(LIVE_CMD, shell=True, input=prompt,
                                      capture_output=True, text=True, timeout=900,
                                      errors="replace")
                # Honour LOAD: requests once, so selective loading is exercised rather than
                # pre-empted. Only files the model actually asked for are supplied.
                wanted = re.findall(r"(?m)^\s*LOAD:\s*references/([\w.-]+)", proc.stdout)
                if wanted:
                    supplied = "".join(
                        f"\n\n--- references/{n} ---\n{(refs / n).read_text(encoding='utf-8')}"
                        for n in dict.fromkeys(wanted) if (refs / n).is_file())
                    proc = subprocess.run(
                        LIVE_CMD, shell=True,
                        input=f"{prompt}{supplied}\n\n(References you requested are above. "
                              f"Now produce the full answer.)\n",
                        capture_output=True, text=True, timeout=900, errors="replace")
                tmp = Path(tempfile.mkdtemp(prefix="tdw-live-"))
                self.addCleanup(__import__("shutil").rmtree, tmp, ignore_errors=True)
                passed, reasons = grade(proc.stdout, fixture, tmp, requested=set(wanted))
                self.assertTrue(passed,
                                f"{scenario}: live output failed grading: {reasons}\n\n"
                                f"{proc.stdout[:2000]}")


class LiveHarnessPlumbingTest(unittest.TestCase):
    """Run `LiveForwardEval` against a scripted stub, so the live path executes on every run.

    Without this, the live class was dead code: skipped by default, never once exercised, and its
    docstring made a claim about `reference_to_load` that turned out to be false. This proves the
    plumbing — prompt assembly, the `LOAD:` second turn, the hand-off into `grade` — and proves
    the harness can still FAIL, which a stub that only ever replayed known-good output would not.

    It deliberately proves nothing about model behaviour. The stub replays a stored document
    rather than writing one; only `TECH_DOC_EVAL_CMD` pointed at a real model measures that.
    """

    STUB = TESTS_DIR / "stub_writer.py"

    def _run(self, stub_mode=None):
        env = dict(os.environ)
        env["TECH_DOC_EVAL_CMD"] = f"{sys.executable} {self.STUB}"
        if stub_mode:
            env["STUB_MODE"] = stub_mode
        else:
            env.pop("STUB_MODE", None)
        return subprocess.run(
            [sys.executable, "-m", "unittest", "test_forward_eval.LiveForwardEval"],
            cwd=TESTS_DIR, env=env, capture_output=True, text=True, timeout=300,
            errors="replace")

    def test_stub_exists_and_is_runnable(self):
        self.assertTrue(self.STUB.is_file(), f"missing {self.STUB}")

    def test_harness_passes_on_replayed_good_exemplars(self):
        proc = self._run()
        self.assertEqual(0, proc.returncode,
                         f"live harness failed on known-good replay:\n{proc.stderr[-3000:]}")

    def test_harness_fails_on_replayed_bad_exemplars(self):
        """Anti-vacuity: a harness that cannot fail is not measuring anything."""
        proc = self._run("bad")
        self.assertNotEqual(0, proc.returncode,
                            "live harness passed the BAD exemplars — it is not grading")
        self.assertIn("failures=5", proc.stderr,
                      f"expected all 5 scenarios to be rejected:\n{proc.stderr[-3000:]}")

    def test_harness_requires_the_reference_to_be_actually_requested(self):
        """A cited path is not a loaded file. Two of the five fixtures pin a reference; a writer
        that never sends `LOAD:` must fail exactly those two."""
        proc = self._run("no_load")
        self.assertIn("never requested it over the LOAD protocol", proc.stderr,
                      f"citation-only responses were accepted:\n{proc.stderr[-3000:]}")
        self.assertIn("failures=2", proc.stderr,
                      f"expected the 2 reference-pinning scenarios to fail:\n"
                      f"{proc.stderr[-3000:]}")


if __name__ == "__main__":
    unittest.main()
