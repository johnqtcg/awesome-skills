"""End-to-end skill-output eval: a GRADER for what a model produces when driven by
the unit-test skill, plus fixtures and a self-test that the grader actually
discriminates good from bad.

The gap this addresses (see COVERAGE.md): every other test validates the skill
*document* or the *methodology on fixed fixtures*. None grades an actual
skill-driven response. A true live eval needs a model in the loop, which cannot
run deterministically in this zero-LLM suite — so this file ships:

  1. A `grade(output, fixture)` function that scores a response on the dimensions
     the reviewer named: correct mode, real defect hypotheses, a test that
     COMPILES and KILLS the mutation, and a compliant scorecard + JSON.
  2. Two hand-authored exemplars (good, bad) and a self-test proving the grader
     PASSES the good one and FAILS the bad one — so the grader is not a rubber
     stamp. This runs in CI (needs `go` for the compile/kill check; skips without).
  3. An opt-in live hook (`UNIT_TEST_SKILL_EVAL_CMD`) that runs a real model and
     grades its output. Skipped unless configured — that is the remaining step to
     a full behavioral eval, now a drop-in rather than a rewrite.

Honesty: (1)+(2) prove the *grader* works; they do not prove a live model passes.
Only the opt-in (3), once wired to a backend, does that.
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest

GO = shutil.which("go")
FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "llm_eval", "slice_transform")
SKILL_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
SCORECARD_REF = os.path.join(SKILL_DIR, "references", "boundary-scorecard.md")
LIVE_CMD = os.environ.get("UNIT_TEST_SKILL_EVAL_CMD")

# --- Outcomes of running an emitted test (three states, not two) ---
PASSED = "passed"    # the test binary ran and every test passed
FAILED = "failed"    # the test binary ran and a test failed
NO_RUN = "no-run"    # nothing executed: the code did not compile / vet / contain a test

_BUILD_FAILED = re.compile(r"\[(?:build|setup) failed\]")
_GO_DIAGNOSTIC = re.compile(r"^(?:\./)?[\w./\\-]+\.go:\d+:\d+: ", re.M)
_TEST_FAILED = re.compile(r"^\s*--- FAIL:|^FAIL\s+\S+\s+[\d.]+s", re.M)
# Two different "nothing executed" messages, both of which exit 0:
#   `[no tests to run]`  — a _test.go file exists but declares no test function. This is
#                          the reachable one here, and it is printed on an `ok` line.
#   `[no test files]`    — the package has no _test.go at all (defensive: this helper
#                          always writes one, so it cannot occur today).
_NOTHING_RAN = re.compile(r"\[no tests? (?:to run|files)\]")
# Dependency resolution needs the module proxy. In an offline sandbox this is an
# environment limit, not a defect in the response — so it stays a skip.
_UNRESOLVED_DEP = re.compile(
    r"no required module provides package|missing go\.sum entry|module lookup disabled"
    r"|proxy\.golang\.org|dial tcp|i/o timeout",
)


def _load_fixture() -> dict:
    with open(os.path.join(FIXTURE_DIR, "meta.json"), encoding="utf-8") as fh:
        meta = json.load(fh)
    with open(os.path.join(FIXTURE_DIR, "sut.go"), encoding="utf-8") as fh:
        meta["source"] = fh.read()
    return meta


def scorecard_rule() -> dict:
    """Parse the PASS thresholds AND the tier sizes out of `references/boundary-scorecard.md`.

    The grader needs the per-tier minimums, the per-tier totals and the grand total to
    check that a response's `summary.pass` and `summary.score` agree with its own tier
    counts. Hard-coding them here would create a second copy of a documented number,
    which drifts silently the first time the reference is edited — so they are read from
    the reference itself. A reference that no longer states them is a repository defect:
    raise loudly rather than grade against a guess."""
    with open(SCORECARD_REF, encoding="utf-8") as fh:
        text = fh.read()
    patterns = {
        "critical_total": r"All (\d+) Critical items",
        "standard_min": r"Standard tier:\s*>=\s*(\d+)/\d+",
        "standard_total": r"Standard tier:\s*>=\s*\d+/(\d+)",
        "hygiene_min": r"Hygiene tier:\s*>=\s*(\d+)/\d+",
        "hygiene_total": r"Hygiene tier:\s*>=\s*\d+/(\d+)",
        "total_min": r"total\s*>=\s*(\d+)/\d+",
        "grand_total": r"total\s*>=\s*\d+/(\d+)",
    }
    rule = {}
    for key, pat in patterns.items():
        m = re.search(pat, text)
        if m is None:
            raise AssertionError(
                f"cannot read {key!r} from {SCORECARD_REF} (pattern {pat!r}); the scorecard "
                f"PASS criteria must stay machine-readable — the grader has no fallback copy"
            )
        rule[key] = int(m.group(1))
    tier_sum = rule["critical_total"] + rule["standard_total"] + rule["hygiene_total"]
    if tier_sum != rule["grand_total"]:
        raise AssertionError(
            f"{SCORECARD_REF} is internally inconsistent: tiers sum to {tier_sum} but the "
            f"grand total is {rule['grand_total']}")
    return rule


def _go_env(root: str) -> dict:
    env = dict(os.environ)
    env.pop("GOROOT", None)  # see test_behavioral_killer._go_env for why
    env["GOTOOLCHAIN"] = "local"
    env["GOFLAGS"] = "-count=1"
    env["GOCACHE"] = os.path.join(root, ".gocache")
    env["GOMODCACHE"] = os.path.join(root, ".gomod")
    env["GOPATH"] = os.path.join(root, ".gopath")
    return env


def _extract_go_test(output: str):
    """Return the first ```go fenced block that contains a test function, or None."""
    for block in re.findall(r"```go\s*\n(.*?)```", output, re.S):
        if "func Test" in block:
            return block
    return None


def _json_blocks(output: str):
    return re.findall(r"```json\s*\n(.*?)```", output, re.S)


def test_case_results(go_test_output: str):
    """Map leaf case name -> "PASS" | "FAIL" | "SKIP", as `go test -v` reported it.

    Status, not just the name. Collapsing the three into "executed" conflates
    **discovered** with **verified**: a `t.Skip()` still prints `--- SKIP: TestX/empty`,
    so a name-only list let two skipped subtests stand as evidence that their hypothesis
    was covered. A skipped case asserted nothing.

    Only leaf names count — a parent `TestX` that contains `TestX/empty` is a group, not
    a case."""
    found = re.findall(r"^\s*--- (PASS|FAIL|SKIP): (\S+)", go_test_output, re.M)
    names = [n for _, n in found]
    return {n: s for s, n in found
            if not any(o != n and o.startswith(n + "/") for o in names)}


def verified_cases(results: dict):
    """Cases that reached a verdict. A SKIP means the assertions never ran."""
    return {n for n, s in results.items() if s != "SKIP"}


class _GoRunner:
    """Minimal compile-and-run helper; raises unittest.SkipTest on env failure."""

    def __init__(self, test_case: unittest.TestCase):
        self.tc = test_case

    def _mod(self, files: dict) -> str:
        try:
            root = tempfile.mkdtemp(prefix="llm-eval-")
        except OSError as exc:
            self.tc.skipTest(f"cannot create temp dir: {exc}")
        self.tc.addCleanup(shutil.rmtree, root, ignore_errors=True)
        for name, content in files.items():
            path = os.path.join(root, name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(content)
        return root

    def _run(self, root: str, *args: str) -> subprocess.CompletedProcess:
        try:
            return subprocess.run(
                [GO, *args], cwd=root, env=_go_env(root),
                capture_output=True, text=True, timeout=180,
            )
        except OSError as exc:
            self.tc.skipTest(f"cannot exec go: {exc}")

    def preflight(self):
        root = self._mod({"go.mod": "module pf\n\ngo 1.22\n", "m.go": "package main\n\nfunc main() {}\n"})
        if self._run(root, "build", "./...").returncode != 0:
            self.tc.skipTest("go cannot compile in this environment")

    def run(self, source: str, go_test: str):
        """Return (outcome, detail, output) with outcome in {PASSED, FAILED, NO_RUN}.

        `output` is the full `go test -v` transcript, which is what makes the *number of
        test cases actually executed* observable — see `executed_case_names`.

        Three states, not two. `returncode == 0` alone conflates "the test failed" with
        "nothing compiled", and the grader reads this result in both directions, so a build
        failure corrupted the grade twice over:

          * on the correct source — it was reported as "the emitted test does not pass",
            blaming the model for a broken toolchain;
          * on the mutated source — a non-zero exit read as *the mutation was killed*,
            silently crediting a test that never ran.

        Collapsing both into a skip (the previous fix) then over-corrected: a response whose
        Go code does not compile is a **failure of the response**, not of the environment —
        for a test-generation skill it is the single most important failure to catch. So a
        compiler/vet diagnostic now yields NO_RUN, which the grader attributes to the side
        it came from, and only a genuine environment fault (`preflight` already proved the
        toolchain builds a trivial program here; unresolved module downloads) still skips."""
        root = self._mod({"go.mod": "module eval\n\ngo 1.22\n",
                          "sut.go": source, "sut_test.go": go_test})
        proc = self._run(root, "test", "-v", "./...")
        combined = f"{proc.stdout}\n{proc.stderr}".strip()
        tail = combined[-400:]

        if proc.returncode == 0:
            # A run that executed no test function exits 0 — and says so on an `ok` line,
            # so exit status and the `ok` prefix both read as success. Not a pass.
            if _NOTHING_RAN.search(combined):
                return NO_RUN, f"go test executed no test function: {tail}", combined
            return PASSED, "", combined
        if _UNRESOLVED_DEP.search(combined):
            self.tc.skipTest(
                f"go could not resolve a module dependency — an offline/proxy limit of this "
                f"environment, not a result: {tail}")
        # A build/vet failure says so explicitly, or points at a file:line:col.
        if _BUILD_FAILED.search(combined) or (
                _GO_DIAGNOSTIC.search(combined) and not _TEST_FAILED.search(combined)):
            return NO_RUN, f"go could not build the code: {tail}", combined
        if _TEST_FAILED.search(combined):
            return FAILED, tail, combined
        self.tc.skipTest(
            f"go test exited {proc.returncode} with neither a compiler diagnostic nor a test "
            f"result — an environment failure, not a grade: {tail}")


def parse_json_summary(output: str):
    """Return (doc, reasons). `doc` is None when there is nothing to check further."""
    blocks = _json_blocks(output)
    if not blocks:
        return None, ["no JSON summary block"]
    try:
        doc = json.loads(blocks[-1])
    except ValueError as exc:
        return None, [f"JSON summary block does not parse as JSON: {exc}"]
    if not isinstance(doc, dict):
        return None, [f"JSON summary block is a {type(doc).__name__}, not a JSON object"]
    return doc, []


def _typed(value, kind: str) -> bool:
    """JSON-type check. `bool` is a subclass of `int` in Python, so an `int` field must
    reject `true` explicitly — otherwise `"critical_pass": true` would type-check."""
    if kind == "bool":
        return isinstance(value, bool)
    if kind == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if kind == "string":
        return isinstance(value, str)
    if kind == "array":
        return isinstance(value, list)
    raise AssertionError(f"unknown declared type {kind!r} in the fixture's json_field_types")


def _check_json_types(doc: dict, field_types: dict):
    """Validate every declared field's presence AND type. Returns (reasons, values).

    `values` holds only the fields that passed, keyed by their dotted path — so the
    consistency rules below operate on validated data and never have to re-guess a
    type. The previous version guarded each consistency block with an `isinstance`
    test, which meant a **wrong type silently disabled the check**: setting
    `critical_pass` to the string `"three"` skipped the score/verdict comparison
    entirely and the response graded clean."""
    reasons, values = [], {}
    for path, kind in sorted(field_types.items()):
        section, _, field = path.partition(".")
        repeated = section.endswith("[]")
        sec = doc.get(section[:-2] if repeated else section)
        if repeated:
            if not isinstance(sec, list):
                reasons.append(f"JSON: section {section[:-2]!r} missing or not an array")
                continue
            if not sec:
                reasons.append(f"JSON: section {section[:-2]!r} is empty")
            for i, item in enumerate(sec):
                if not isinstance(item, dict):
                    reasons.append(f"JSON: {section[:-2]}[{i}] is not an object")
                elif field not in item:
                    reasons.append(f"JSON: {section[:-2]}[{i}].{field} missing")
                elif not _typed(item[field], kind):
                    reasons.append(
                        f"JSON: {section[:-2]}[{i}].{field} must be {kind}, got "
                        f"{type(item[field]).__name__} ({item[field]!r})")
                else:
                    values.setdefault(path, []).append(item[field])
            continue
        if not isinstance(sec, dict):
            reasons.append(f"JSON: section {section!r} missing or not an object")
        elif field not in sec:
            reasons.append(f"JSON: {path} missing")
        elif not _typed(sec[field], kind):
            reasons.append(
                f"JSON: {path} must be {kind}, got {type(sec[field]).__name__} "
                f"({sec[field]!r})")
        else:
            values[path] = sec[field]
    return reasons, values


def _check_json_ranges(v: dict, rule: dict):
    """Bounds and tier sizes. A count outside its range makes every downstream
    consistency comparison meaningless, so it is reported as its own defect."""
    reasons = []
    for tier in ("critical", "standard", "hygiene"):
        p, t = v.get(f"scorecard.{tier}_pass"), v.get(f"scorecard.{tier}_total")
        if p is None or t is None:
            continue
        if t != rule[f"{tier}_total"]:
            reasons.append(
                f"JSON: scorecard.{tier}_total={t} but the scorecard defines "
                f"{rule[f'{tier}_total']} {tier} items")
        if not 0 <= p <= t:
            reasons.append(f"JSON: scorecard.{tier}_pass={p} is not within 0..{t}")
    for path in ("coverage.line_pct", "coverage.gate"):
        if path in v and not 0 <= v[path] <= 100:
            reasons.append(f"JSON: {path}={v[path]} is not a percentage in 0..100")
    for cases in v.get("targets[].cases", []):
        if cases < 1:
            reasons.append(f"JSON: targets[].cases={cases} — a tested target has >= 1 case")
    for killers in v.get("targets[].killer_cases", []):
        if killers < 0:
            reasons.append(f"JSON: targets[].killer_cases={killers} is negative")
    return reasons


def _check_json_consistency(output: str, v: dict, rule: dict):
    """The verdict, the score, the tier counts and the coverage result must all agree.

    Every rule here is unconditional: `_check_json_types` has already validated the
    inputs, so a missing rule can no longer be caused by a wrong type."""
    reasons = []
    tiers = ("critical", "standard", "hygiene")
    have_counts = all(f"scorecard.{t}_{s}" in v for t in tiers for s in ("pass", "total"))
    got = total = None
    if have_counts:
        got = sum(v[f"scorecard.{t}_pass"] for t in tiers)
        total = sum(v[f"scorecard.{t}_total"] for t in tiers)
        if total != rule["grand_total"]:
            reasons.append(
                f"JSON: scorecard tiers total {total}, but the scorecard has "
                f"{rule['grand_total']} items")

    score = v.get("summary.score")
    parsed_score = None
    if score is not None:
        m = re.fullmatch(r"\s*(\d+)\s*/\s*(\d+)\s*", score)
        if m is None:
            reasons.append(f"JSON: summary.score {score!r} is not in 'N/M' form")
        else:
            parsed_score = (int(m.group(1)), int(m.group(2)))
            if have_counts and parsed_score != (got, total):
                reasons.append(
                    f"JSON: summary.score {score!r} contradicts its own scorecard tiers "
                    f"({got}/{total})")
        prose = re.sub(r"```json\s*\n.*?```", "", output, flags=re.S)
        if score not in prose:
            reasons.append(
                f"JSON: summary.score {score!r} never appears in the report prose — the "
                f"human-readable verdict and the machine-readable one disagree")

    declared_pass = v.get("summary.pass")
    if have_counts and declared_pass is not None:
        verdict = (v["scorecard.critical_pass"] == v["scorecard.critical_total"]
                   and v["scorecard.standard_pass"] >= rule["standard_min"]
                   and v["scorecard.hygiene_pass"] >= rule["hygiene_min"]
                   and got >= rule["total_min"])
        if declared_pass is not verdict:
            reasons.append(
                f"JSON: summary.pass={declared_pass} contradicts the tier rule "
                f"(Critical all-PASS, Standard >= {rule['standard_min']}, Hygiene >= "
                f"{rule['hygiene_min']}, total >= {rule['total_min']} => {verdict})")

    met, pct, gate = (v.get("coverage.met"), v.get("coverage.line_pct"), v.get("coverage.gate"))
    if None not in (met, pct, gate):
        if met is not (pct >= gate):
            reasons.append(
                f"JSON: coverage.met={met} contradicts line_pct={pct} vs gate={gate}")
        # The coverage gate is Critical scorecard item 13. A *measured* miss is not the
        # restricted N/A case (which applies when coverage was not or could not be
        # measured), so it must show up as a failed Critical item and an overall FAIL.
        # Without this link a report could state 20% coverage, met=false, and 13/13 PASS
        # — each field locally consistent, the verdict impossible.
        if met is False and pct < gate:
            if v.get("scorecard.critical_pass") == v.get("scorecard.critical_total") \
                    and "scorecard.critical_pass" in v:
                reasons.append(
                    f"JSON: coverage.met=false (line_pct={pct} < gate={gate}) means the "
                    f"Critical coverage item FAILED, so critical_pass cannot equal "
                    f"critical_total ({v['scorecard.critical_pass']})")
            if declared_pass is True:
                reasons.append(
                    f"JSON: summary.pass=true with a measured coverage miss "
                    f"(line_pct={pct} < gate={gate}) — a Critical FAIL is an overall FAIL")

    if v.get("race.clean") is True and v.get("race.executed") is not True:
        reasons.append(
            "JSON: race.clean=true with race.executed!=true — a clean race result cannot be "
            "claimed without running -race (Reporting Integrity)")
    return reasons


def grade_json_summary(output: str, fixture: dict):
    """Return a list of reasons the machine-readable JSON summary is non-conformant.

    Checking that a ```json fence exists proves nothing about the block inside it: a
    fence containing the literal text `NOT JSON` passed an earlier version of this
    grader. Parsing alone is not enough either — a summary meant to be ingested by CI
    must carry the declared fields **with the declared types**, hold values inside their
    ranges, and be internally consistent: the score, the per-tier counts, the coverage
    result and the final verdict all describe the same run and cannot disagree."""
    doc, reasons = parse_json_summary(output)
    if doc is None:
        return reasons
    rule = scorecard_rule()
    type_reasons, values = _check_json_types(doc, fixture["json_field_types"])
    all_reasons = (reasons + type_reasons
                   + _check_json_ranges(values, rule)
                   + _check_json_consistency(output, values, rule))
    # A missing repeated section (e.g. `targets`) is reported once per declared field.
    # Identical strings carry identical information, so collapse them, order preserved.
    return list(dict.fromkeys(all_reasons))


def validate_fixture(fixture: dict):
    """Return reasons the FIXTURE itself is unsound, before grading any response.

    Two things a hypothesis must be anchored to, or it grades nothing:

    * its **mutation** must exist in the source — otherwise the kill check silently
      compares the source against itself;
    * its **contract evidence** must appear in the source. A hypothesis asserts a
      behaviour; if the code under test does not promise that behaviour, the assertion
      is a requirement invented by the test. This is the direction the round-6 review
      named: assert non-nil only if non-nil is the contract, otherwise narrow the
      hypothesis. A mutation run found nothing checked it — deleting the contract from
      the SUT's doc comment left the exemplar passing.
    """
    reasons = []
    for hyp in fixture["hypotheses"]:
        if hyp["mutation"]["find"] not in fixture["source"]:
            reasons.append(
                f"fixture drift: {hyp['id']} mutation target "
                f"{hyp['mutation']['find']!r} not found in the source")
        evidence = hyp.get("contract_evidence")
        if evidence is None:
            reasons.append(
                f"fixture defect: {hyp['id']} declares no contract_evidence, so nothing "
                f"binds its asserted behaviour to a promise the source actually makes")
        elif not re.search(evidence, fixture["source"]):
            reasons.append(
                f"fixture defect: {hyp['id']} ({hyp['description']}) asserts a behaviour "
                f"the source does not document — no match for {evidence!r}. Either the "
                f"contract says it (document it) or it does not (narrow the hypothesis)")
    return reasons


def _grade_report_matches_code(output: str, fixture: dict, transcript: str):
    """Check the report's claims against the test run the toolchain performed.

    A report can say "5 cases, hypotheses H1 and H2 covered" while the code holds one
    case that exercises neither — every format check still passes, because none of them
    looks at the code. This is not full semantic analysis; it compares things that must
    already agree: the claimed case count, and the cases `go test -v` ran with a verdict.

    Discovered vs verified is the distinction that matters here. A `t.Skip()` prints
    `--- SKIP: TestX/empty`, so a case can be present, named exactly as its hypothesis
    requires, and assert nothing at all."""
    reasons = []
    results = test_case_results(transcript)
    verified = verified_cases(results)
    skipped = sorted(n for n in results if n not in verified)

    if skipped and not fixture.get("allow_skipped_cases", False):
        reasons.append(
            f"skipped case(s) {skipped} — this target has no legitimate reason to skip, "
            f"and a skipped case verifies nothing")

    doc, _ = parse_json_summary(output)
    targets = (doc or {}).get("targets")
    if isinstance(targets, list) and targets:
        claimed = [t.get("cases") for t in targets if isinstance(t, dict)]
        if all(isinstance(c, int) and not isinstance(c, bool) for c in claimed):
            if sum(claimed) != len(results):
                reasons.append(
                    f"report claims {sum(claimed)} case(s) but go test -v ran "
                    f"{len(results)}: {sorted(results)}")

    for hyp in fixture["hypotheses"]:
        matches = {n: s for n, s in results.items() if re.search(hyp["case_pattern"], n)}
        if not matches:
            reasons.append(
                f"{hyp['id']} ({hyp['description']}): no test case matches "
                f"{hyp['case_pattern']!r}; ran: {sorted(results)}")
        elif not any(n in verified for n in matches):
            reasons.append(
                f"{hyp['id']} ({hyp['description']}): its only matching case(s) "
                f"{sorted(matches)} were SKIPPED — discovered, not verified")
    return reasons


def _grade_mutations(fixture: dict, go_test: str, runner: "_GoRunner"):
    """Every declared hypothesis owns a mutation, and the emitted test must kill each.

    One mutation per fixture was not enough: H2 promised "empty but NON-NIL" and had no
    mutation, so changing the implementation to `var out []string` — which returns nil
    for an empty input — left all four of the exemplar's cases passing. The hypothesis
    was stated, given an input scenario, and never verified. Binding a mutation to each
    hypothesis makes "covered" mean "its stated behaviour is asserted"."""
    reasons = []
    for hyp in fixture["hypotheses"]:
        mut = hyp["mutation"]
        if mut["find"] not in fixture["source"]:
            continue  # already reported by validate_fixture
        mutated = fixture["source"].replace(mut["find"], mut["replace"])
        outcome, detail, _ = runner.run(mutated, go_test)
        if outcome is PASSED:
            reasons.append(
                f"emitted test does NOT kill the {hyp['id']} mutation "
                f"({hyp['description']}) — the hypothesis is stated but not verified")
        elif outcome is NO_RUN:
            # The test built on the correct source, so this is the MUTATION's doing. A
            # mutation that does not compile is not evidence of anything — crediting it
            # as a kill is how a broken fixture certifies a test that catches nothing.
            reasons.append(
                f"invalid {hyp['id']} mutation: the mutated source does not build, so a "
                f"kill cannot be credited (fixture defect, not a result): {detail}")
    return reasons


def grade(output: str, fixture: dict, runner: "_GoRunner"):
    """Return (passed: bool, reasons: list[str]). Runs ALL checks (no short-circuit)
    so a caller can see every way a response falls short."""
    reasons = list(validate_fixture(fixture))

    # 1. Correct execution mode declared.
    m = re.search(r"Mode[:*\s]+(Light|Standard|Strict)", output)
    declared = m.group(1) if m else None
    if declared != fixture["expected_mode"]:
        reasons.append(f"mode: declared {declared!r}, expected {fixture['expected_mode']!r}")

    # 2. Each declared hypothesis is actually described in the report.
    low = output.lower()
    for hyp in fixture["hypotheses"]:
        hits = [k for k in hyp["keywords"] if k.lower() in low]
        if len(hits) < hyp["min_keywords"]:
            reasons.append(
                f"{hyp['id']} ({hyp['description']}): found {hits}, need >= "
                f"{hyp['min_keywords']} of {hyp['keywords']}")

    # 3. Report contract: scorecard, required report markers, and a JSON summary that
    #    parses and agrees with itself. Light mode skips the JSON block by design.
    if "scorecard" not in low:
        reasons.append("no scorecard section")
    for marker in fixture.get("report_patterns", []):
        if not re.search(marker["regex"], output):
            reasons.append(f"report is missing {marker['name']}")
    if fixture["expected_mode"] != "Light":
        reasons.extend(grade_json_summary(output, fixture))

    # 4. Behavioral: the emitted test must COMPILE + PASS on the correct source.
    go_test = _extract_go_test(output)
    if go_test is None:
        reasons.append("no Go test block found")
        return (len(reasons) == 0, reasons)

    outcome, detail, transcript = runner.run(fixture["source"], go_test)
    if outcome is NO_RUN:
        # The response's own Go code never ran. For a test-generation skill this is the
        # headline failure — never a skip, and never an excuse to skip the kill check.
        reasons.append(f"emitted test does not build on the correct implementation: {detail}")
        return (len(reasons) == 0, reasons)
    if outcome is FAILED:
        reasons.append("emitted test does not pass on the correct implementation")
        return (len(reasons) == 0, reasons)

    # 5. Report vs. code: the claimed case count and the cases that actually reached a
    #    verdict. Prose and JSON can claim any number; `go test -v` reports the truth.
    #    (A response that shows only part of its test file will fail this — the eval
    #    prompt asks for the complete test.)
    reasons.extend(_grade_report_matches_code(output, fixture, transcript))

    # 6. Each hypothesis's mutation must be killed.
    reasons.extend(_grade_mutations(fixture, go_test, runner))
    return (len(reasons) == 0, reasons)


@unittest.skipIf(GO is None, "go toolchain not installed")
class GraderSelfTest(unittest.TestCase):
    """Prove the grader discriminates: PASS the good exemplar, FAIL the bad one."""

    def setUp(self):
        self.fixture = _load_fixture()
        self.runner = _GoRunner(self)
        self.runner.preflight()

    def _read(self, name: str) -> str:
        with open(os.path.join(FIXTURE_DIR, name), encoding="utf-8") as fh:
            return fh.read()

    def _no_skip(self, fn, *args):
        """Call `fn` and convert a SkipTest into a failure.

        unittest reports a skip as green, so a guard that lets SkipTest propagate cannot
        detect the very regression it exists to catch. A mutation run confirmed this:
        collapsing the build-failure branch back into `skipTest` left every one of these
        tests passing (as `OK (skipped=1)`). Any test here whose subject is "this must
        NOT be a skip" must therefore assert that explicitly."""
        try:
            return fn(*args)
        except unittest.SkipTest as exc:
            self.fail(f"skipped instead of producing a graded outcome: {exc}")

    # --- run(): three states ---

    def test_run_distinguishes_pass_from_fail(self):
        """Anti-vacuity: a real pass and a real failure must still be told apart."""
        src = "package eval\n\nfunc Add(a, b int) int { return a + b }\n"
        tpl = ('package eval\n\nimport "testing"\n\n'
               "func TestAdd(t *testing.T) {{ if Add(1, 2) != {0} {{ t.Fatal(\"mismatch\") }} }}\n")
        self.assertEqual(PASSED, self.runner.run(src, tpl.format(3))[0])
        self.assertEqual(FAILED, self.runner.run(src, tpl.format(99))[0])

    def test_uncompilable_test_is_no_run_not_a_skip_or_a_fail(self):
        outcome, detail, _ = self._no_skip(
            self.runner.run, self.fixture["source"],
            'package sut\n\nimport "testing"\n\nfunc TestBroken(t *testing.T) { this is not go }\n')
        self.assertEqual(NO_RUN, outcome, detail)

    def test_a_run_with_no_test_function_is_not_a_pass(self):
        """A `_test.go` with no test function exits 0 and prints `ok <pkg> [no tests to run]`
        — success by exit status AND by the `ok` prefix. Reading that as a pass credits a
        response that produced nothing runnable.

        Two traps this test had to survive: the extra file must declare the fixture's own
        package (`sut`), or the mismatch is a build error that satisfies the assertion via
        the wrong branch; and the observable is `[no tests to run]`, not `[no test files]`
        — the latter cannot occur here because `run()` always writes a test file."""
        outcome, detail, _ = self._no_skip(
            self.runner.run, self.fixture["source"], "package sut\n\nvar unused = 1\n")
        self.assertEqual(NO_RUN, outcome, detail)
        self.assertIn("no tests to run", detail)

    def test_environment_failure_still_skips(self):
        """The narrow skip path must stay alive: a go invocation that fails with neither a
        compiler diagnostic nor a test result is an environment fault, not a grade."""
        self.runner._run = lambda *a, **k: subprocess.CompletedProcess(
            args=["go"], returncode=2, stdout="", stderr="go: GOFLAGS parse error\n")
        with self.assertRaises(unittest.SkipTest):
            self.runner.run("package eval\n", "package eval\n")

    def test_unresolved_dependency_skips(self):
        self.runner._run = lambda *a, **k: subprocess.CompletedProcess(
            args=["go"], returncode=1, stdout="",
            stderr="sut_test.go:4:2: no required module provides package "
                   "github.com/stretchr/testify/require\n")
        with self.assertRaises(unittest.SkipTest):
            self.runner.run("package eval\n", "package eval\n")

    # --- grade(): the two holes the round-4 review demonstrated ---

    def test_undefined_symbol_is_a_grading_failure_not_a_skip(self):
        """Reviewer experiment 1: keep the whole good response, break only the call. The
        emitted test then references an undefined symbol — the response is wrong and must
        be graded as such. It previously raised SkipTest, so the run reported neither pass
        nor fail for a response whose code could not compile."""
        broken = self._read("good.md").replace(
            "ExtractIDs(tt.items)", "UndefinedFunction(tt.items)")
        passed, reasons = self._no_skip(grade, broken, self.fixture, self.runner)
        self.assertFalse(passed)
        self.assertTrue(
            any("does not build on the correct implementation" in r for r in reasons),
            f"expected a build failure to be graded, got: {reasons}")

    def test_uncompilable_mutation_is_not_credited_as_a_kill(self):
        """The mirror hole: if the mutation itself breaks the build, the emitted test cannot
        have demonstrated anything. It must not read as 'the mutation was killed'."""
        fixture = dict(self.fixture)
        fixture["hypotheses"] = [dict(self.fixture["hypotheses"][0])]
        fixture["hypotheses"][0]["mutation"] = {
            "find": "out := make([]string, 0, len(items))",
            "replace": "out := make([]string, 0, len(items)) +"}
        passed, reasons = self._no_skip(grade, self._read("good.md"), fixture, self.runner)
        self.assertFalse(passed)
        self.assertTrue(any("invalid H1 mutation" in r for r in reasons), reasons)

    def test_grader_rejects_non_json_summary_block(self):
        """Reviewer experiment 2: replace the JSON block's contents with `NOT JSON`. The
        earlier grader returned (True, []) — it only looked for the fence."""
        broken = re.sub(r"```json\s*\n.*?```", "```json\nNOT JSON\n```",
                        self._read("good.md"), flags=re.S)
        passed, reasons = grade(broken, self.fixture, self.runner)
        self.assertFalse(passed)
        self.assertTrue(any("does not parse as JSON" in r for r in reasons), reasons)

    def test_grader_rejects_missing_kill_verification(self):
        """SKILL.md requires every killer case to report `Kill: Verified` (mutation run,
        failure observed) or `Kill: Unverified` (+ reason). Without it, "this case catches
        the defect" is an unfalsifiable claim."""
        broken = re.sub(r"Kill:\s*(Verified|Unverified)", "Checked", self._read("good.md"))
        passed, reasons = grade(broken, self.fixture, self.runner)
        self.assertFalse(passed)
        self.assertTrue(any("kill verification" in r for r in reasons), reasons)

    # --- report vs. code: the claims must match the run ---

    def test_rejects_a_case_count_the_run_contradicts(self):
        """The exemplar itself once claimed 5 cases while shipping a single 3-element
        input. Every format check passed, because none of them looked at the code. The
        claimed count is now compared against the cases `go test -v` actually executed."""
        broken = self._read("good.md").replace('"cases": 4', '"cases": 9')
        passed, reasons = self._no_skip(grade, broken, self.fixture, self.runner)
        self.assertFalse(passed)
        self.assertTrue(any("claims 9 case(s) but go test -v ran" in r for r in reasons),
                        reasons)

    def test_rejects_a_declared_hypothesis_with_no_case_that_exercises_it(self):
        """H2 is "nil/empty input must not panic". Deleting both such rows leaves the
        report still claiming H2 covered — with no case that touches it."""
        broken = (self._read("good.md")
                  .replace('\t\t{name: "nil input", items: nil, want: []string{}},\n', "")
                  .replace('\t\t{name: "empty slice", items: []Item{}, want: []string{}},\n', "")
                  .replace('"cases": 4', '"cases": 2'))
        # Assert on the exact text the grader will run — the phrase also appears in the
        # report prose, so a looser slice of the document would not prove the removal.
        self.assertNotIn("nil input", _extract_go_test(broken))
        passed, reasons = self._no_skip(grade, broken, self.fixture, self.runner)
        self.assertFalse(passed)
        self.assertTrue(any(r.startswith("H2 (") and "no test case matches" in r
                            for r in reasons), reasons)

    def test_case_results_keeps_leaves_and_their_status(self):
        """A parent test containing subtests is a group, not a case — and the status has
        to survive, because SKIP is what separates discovered from verified."""
        transcript = (
            "--- PASS: TestX (0.00s)\n"
            "    --- PASS: TestX/empty (0.00s)\n"
            "    --- FAIL: TestX/three (0.00s)\n"
            "    --- SKIP: TestX/nil (0.00s)\n"
            "--- PASS: TestY (0.00s)\n")
        results = test_case_results(transcript)
        self.assertEqual(
            {"TestX/empty": "PASS", "TestX/three": "FAIL", "TestX/nil": "SKIP",
             "TestY": "PASS"}, results)
        self.assertEqual({"TestX/empty", "TestX/three", "TestY"},
                         verified_cases(results))

    def test_a_skipped_case_does_not_cover_its_hypothesis(self):
        """Round-6 review: make the two H2 subtests call `t.Skip()` and keep everything
        else. The names still match H2's `case_pattern`, the count still matches, and the
        grader returned `(True, [])` — a skipped case stood as evidence for a hypothesis
        whose assertions never ran."""
        broken = self._read("good.md").replace(
            "\t\t\tt.Parallel()\n\t\t\tassertIDs(t, ExtractIDs(tt.items), tt.want)",
            "\t\t\tt.Parallel()\n\t\t\tif len(tt.items) == 0 {\n"
            '\t\t\t\tt.Skip("skipped")\n\t\t\t}\n'
            "\t\t\tassertIDs(t, ExtractIDs(tt.items), tt.want)")
        self.assertIn("t.Skip", _extract_go_test(broken))
        passed, reasons = self._no_skip(grade, broken, self.fixture, self.runner)
        self.assertFalse(passed)
        self.assertTrue(
            any("were SKIPPED — discovered, not verified" in r for r in reasons), reasons)
        # And the general skip rule fires too: this fixture allows no skips.
        self.assertTrue(any("verifies nothing" in r for r in reasons), reasons)

    def test_a_hypothesis_promising_non_nil_is_not_covered_by_length_alone(self):
        """Round-6 review: H2 promises an empty but NON-NIL result. Dropping the nil
        check leaves all four cases passing on the correct source — and the H2 mutation
        (`var out []string`) then survives, because `len(nil) == 0`. An input scenario is
        not a verification of the behaviour the hypothesis states."""
        broken = self._read("good.md").replace(
            '\tif got == nil {\n'
            '\t\tt.Fatalf("got = nil, want a non-nil slice (contract: JSON [] not null)")\n'
            '\t}\n', "")
        self.assertNotIn("got == nil", _extract_go_test(broken))
        passed, reasons = self._no_skip(grade, broken, self.fixture, self.runner)
        self.assertFalse(passed)
        self.assertTrue(
            any("does NOT kill the H2 mutation" in r for r in reasons), reasons)

    def test_fixture_hypotheses_are_grounded_in_the_sut_contract(self):
        """Anti-vacuity for the check below: the shipped fixture must be sound."""
        self.assertEqual([], validate_fixture(self.fixture))

    def test_a_hypothesis_asserting_an_undocumented_contract_is_a_fixture_defect(self):
        """Round-6 mutation run: deleting the non-nil contract from `sut.go`'s doc comment
        left the exemplar passing. Nothing bound H2's assertion to a promise the code
        actually makes, so the exemplar could have been inventing a requirement — the
        exact failure mode the review warned about, in the opposite direction."""
        fixture = dict(self.fixture)
        fixture["source"] = self.fixture["source"].replace(
            "// The result is always non-nil, including for a nil or empty input: callers",
            "// Note:")
        self.assertNotIn("always non-nil", fixture["source"])
        reasons = validate_fixture(fixture)
        self.assertTrue(
            any("asserts a behaviour the source does not document" in r for r in reasons),
            reasons)
        # And it must fail the response grade too, not just this helper.
        passed, reasons = self._no_skip(grade, self._read("good.md"), fixture, self.runner)
        self.assertFalse(passed)

    def test_a_hypothesis_with_no_contract_evidence_is_a_fixture_defect(self):
        fixture = dict(self.fixture)
        fixture["hypotheses"] = [{k: v for k, v in h.items() if k != "contract_evidence"}
                                 for h in self.fixture["hypotheses"]]
        reasons = validate_fixture(fixture)
        self.assertTrue(any("declares no contract_evidence" in r for r in reasons), reasons)

    # --- the two exemplars ---

    def test_grader_passes_good_exemplar(self):
        passed, reasons = grade(self._read("good.md"), self.fixture, self.runner)
        self.assertTrue(passed, f"good exemplar should pass; reasons: {reasons}")

    def test_grader_fails_bad_exemplar(self):
        passed, reasons = grade(self._read("bad.md"), self.fixture, self.runner)
        self.assertFalse(passed, "bad exemplar must not pass the grader")
        # And for the RIGHT reasons: wrong mode AND a weak test that misses the bug.
        joined = " | ".join(reasons)
        self.assertIn("mode", joined)
        self.assertIn("does NOT kill the H1 mutation", joined)


class JsonSummaryContractTests(unittest.TestCase):
    """Mutation tests for `grade_json_summary`: break exactly one thing in the good
    exemplar's JSON and require the matching rejection.

    Deliberately go-free — the JSON contract is checkable without a toolchain, so these
    run in every environment. `GraderSelfTest.test_grader_rejects_non_json_summary_block`
    is the end-to-end wiring proof that `grade()` actually calls this."""

    @classmethod
    def setUpClass(cls):
        cls.fixture = _load_fixture()
        with open(os.path.join(FIXTURE_DIR, "good.md"), encoding="utf-8") as fh:
            cls.good = fh.read()

    def _reasons(self, output: str):
        return grade_json_summary(output, self.fixture)

    def _assert_rejected(self, output: str, needle: str):
        reasons = self._reasons(output)
        self.assertTrue(any(needle in r for r in reasons),
                        f"expected a reason containing {needle!r}, got: {reasons}")

    def test_good_exemplar_json_is_conformant(self):
        """Anti-vacuity: the checks below must be rejecting the mutation, not the exemplar."""
        self.assertEqual([], self._reasons(self.good))

    def test_rejects_unparseable_block(self):
        self._assert_rejected(
            re.sub(r"```json\s*\n.*?```", "```json\nNOT JSON\n```", self.good, flags=re.S),
            "does not parse as JSON")

    def test_rejects_non_object_block(self):
        self._assert_rejected(
            re.sub(r"```json\s*\n.*?```", "```json\n[1, 2, 3]\n```", self.good, flags=re.S),
            "not a JSON object")

    def test_rejects_missing_block(self):
        self._assert_rejected(re.sub(r"```json\s*\n.*?```", "", self.good, flags=re.S),
                              "no JSON summary block")

    def test_rejects_missing_required_fields(self):
        stripped = re.sub(r"```json\s*\n.*?```", '```json\n{"summary": {"pass": true}}\n```',
                          self.good, flags=re.S)
        reasons = self._reasons(stripped)
        for expected in ("summary.score missing", "summary.go_version missing",
                         "section 'targets' missing", "section 'coverage' missing",
                         "section 'race' missing", "section 'scorecard' missing"):
            self.assertTrue(any(expected in r for r in reasons),
                            f"{expected!r} not reported; got: {reasons}")

    def test_rejects_target_entry_missing_a_field(self):
        self._assert_rejected(self.good.replace('"killer_cases": 2,', ""),
                              "targets[0].killer_cases missing")

    def test_rejects_score_inconsistent_with_its_tiers(self):
        self._assert_rejected(self.good.replace('"critical_pass": 3', '"critical_pass": 1'),
                              "contradicts its own scorecard tiers")

    def test_rejects_pass_true_when_a_critical_item_failed(self):
        """A Critical FAIL is an overall FAIL regardless of total (SKILL.md tier rule), so
        pass=true with critical_pass < critical_total is an incoherent verdict."""
        broken = (self.good.replace('"critical_pass": 3', '"critical_pass": 2')
                           .replace('"score": "13/13"', '"score": "12/13"')
                           .replace("13/13 PASS", "12/13 PASS"))
        self._assert_rejected(broken, "contradicts the tier rule")

    def test_rejects_pass_true_below_the_standard_tier_minimum(self):
        rule = scorecard_rule()
        below = rule["standard_min"] - 1
        broken = (self.good.replace('"standard_pass": 5', f'"standard_pass": {below}')
                           .replace('"score": "13/13"', f'"score": "{8 + below}/13"')
                           .replace("13/13 PASS", f"{8 + below}/13 PASS"))
        self._assert_rejected(broken, "contradicts the tier rule")

    def test_rejects_wrong_type_for_a_count(self):
        """Reviewer experiment: `critical_pass: "three"`. Every consistency rule used to be
        guarded by an isinstance test, so a wrong type silently disabled the whole block and
        the response graded clean. A type error is now its own reason."""
        self._assert_rejected(self.good.replace('"critical_pass": 3', '"critical_pass": "three"'),
                              "scorecard.critical_pass must be int")

    def test_rejects_true_where_an_int_is_declared(self):
        """`bool` is a subclass of `int` in Python, so a naive isinstance check accepts
        `true` for a count."""
        self._assert_rejected(self.good.replace('"critical_pass": 3', '"critical_pass": true'),
                              "scorecard.critical_pass must be int")

    def test_rejects_measured_coverage_miss_with_a_pass_verdict(self):
        """Reviewer experiment: coverage 20% against an 80% gate, `met: false`, yet 13/13
        PASS. Each field was locally consistent — the verdict is impossible. The coverage
        gate is Critical item 13, so a *measured* miss must show as a Critical FAIL and an
        overall FAIL (the restricted N/A applies only when coverage was not measured)."""
        broken = (self.good.replace('"line_pct": 100.0', '"line_pct": 20.0')
                           .replace('"met": true', '"met": false'))
        reasons = self._reasons(broken)
        for expected in ("critical_pass cannot equal critical_total",
                         "a Critical FAIL is an overall FAIL"):
            self.assertTrue(any(expected in r for r in reasons),
                            f"{expected!r} not reported; got: {reasons}")

    def test_rejects_tier_total_that_contradicts_the_scorecard(self):
        self._assert_rejected(self.good.replace('"standard_total": 5', '"standard_total": 4'),
                              "the scorecard defines 5 standard items")

    def test_rejects_pass_count_above_its_tier_total(self):
        self._assert_rejected(self.good.replace('"critical_pass": 3', '"critical_pass": 9'),
                              "is not within 0..3")

    def test_rejects_line_pct_outside_a_percentage(self):
        self._assert_rejected(self.good.replace('"line_pct": 100.0', '"line_pct": 140.0'),
                              "is not a percentage in 0..100")

    def test_rejects_a_target_with_zero_cases(self):
        self._assert_rejected(self.good.replace('"cases": 4', '"cases": 0'),
                              "a tested target has >= 1 case")

    def test_rejects_score_not_in_n_over_m_form(self):
        self._assert_rejected(self.good.replace('"score": "13/13"', '"score": "excellent"'),
                              "is not in 'N/M' form")

    def test_rejects_coverage_met_contradicting_line_pct(self):
        self._assert_rejected(self.good.replace('"line_pct": 100.0', '"line_pct": 41.0'),
                              "coverage.met")

    def test_rejects_clean_race_that_was_never_executed(self):
        self._assert_rejected(self.good.replace('"executed": true', '"executed": false'),
                              "race.clean=true")

    def test_rejects_prose_verdict_disagreeing_with_json(self):
        self._assert_rejected(self.good.replace("13/13 PASS", "11/13 PASS"),
                              "never appears in the report prose")

    def test_scorecard_rule_is_parsed_from_the_reference(self):
        """The thresholds come from references/boundary-scorecard.md, so there is no second
        copy to drift. A reference that stops stating them must fail loudly."""
        rule = scorecard_rule()
        self.assertEqual(
            {"critical_total", "standard_min", "standard_total", "hygiene_min",
             "hygiene_total", "total_min", "grand_total"}, set(rule))
        self.assertTrue(all(isinstance(v, int) and v > 0 for v in rule.values()), rule)
        # The reference must be self-consistent, or every derived comparison is nonsense.
        self.assertEqual(
            rule["grand_total"],
            rule["critical_total"] + rule["standard_total"] + rule["hygiene_total"])
        for tier in ("standard", "hygiene"):
            self.assertLessEqual(rule[f"{tier}_min"], rule[f"{tier}_total"], tier)
        self.assertLessEqual(rule["total_min"], rule["grand_total"])

    def test_scorecard_rule_raises_when_the_reference_is_internally_inconsistent(self):
        """The tier sizes and the grand total are read from separate sentences, so they
        can drift apart. If they do, every comparison derived from them is nonsense —
        raise instead of grading against one of the two numbers.

        A mutation run found this guard untested: the existing test asserts that the
        shipped reference *is* consistent, which stays true whether or not the guard
        fires. Deleting the guard therefore survived. (An `assert` in shipped code with
        no test that makes it fire is not a check.)"""
        root = tempfile.mkdtemp(prefix="scref-")
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        path = os.path.join(root, "boundary-scorecard.md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("All 3 Critical items (5, 11, 13) are PASS, and\n"
                     "- Standard tier: >= 4/5 PASS, and\n"
                     "- Hygiene tier: >= 4/5 PASS, and\n"
                     "- total >= 11/99.\n")  # 3 + 5 + 5 != 99
        original = SCORECARD_REF
        try:
            globals()["SCORECARD_REF"] = path
            with self.assertRaises(AssertionError) as ctx:
                scorecard_rule()
            self.assertIn("internally inconsistent", str(ctx.exception))
        finally:
            globals()["SCORECARD_REF"] = original

    def test_scorecard_rule_raises_when_the_reference_stops_stating_it(self):
        original = SCORECARD_REF
        try:
            globals()["SCORECARD_REF"] = os.path.join(FIXTURE_DIR, "sut.go")  # no thresholds
            with self.assertRaises(AssertionError):
                scorecard_rule()
        finally:
            globals()["SCORECARD_REF"] = original


@unittest.skipUnless(
    LIVE_CMD and GO,
    "set UNIT_TEST_SKILL_EVAL_CMD to a shell command that reads a prompt on stdin "
    "and writes the model's skill-driven response to stdout (and have go installed)",
)
class LiveSkillEval(unittest.TestCase):
    """Opt-in: drive a real model through the skill and grade its output."""

    def test_live_model_output_passes_grader(self):
        fixture = _load_fixture()
        runner = _GoRunner(self)
        runner.preflight()
        skill_md = os.path.join(SKILL_DIR, "SKILL.md")
        with open(skill_md, encoding="utf-8") as fh:
            skill = fh.read()
        prompt = (
            "Follow this unit-test skill exactly and produce its full output "
            "(mode, failure hypotheses, killer case with a Go test, scorecard, JSON):\n\n"
            f"{skill}\n\n---\nTarget source (package sut):\n```go\n{fixture['source']}```\n"
        )
        proc = subprocess.run(LIVE_CMD, shell=True, input=prompt,
                              capture_output=True, text=True, timeout=900)
        passed, reasons = grade(proc.stdout, fixture, runner)
        self.assertTrue(passed, f"live model output failed grading: {reasons}\n\n{proc.stdout[:2000]}")


if __name__ == "__main__":
    unittest.main()
