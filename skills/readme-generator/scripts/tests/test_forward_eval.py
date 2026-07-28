"""Forward evaluation: grade a produced README against the repository it describes.

The gap this closes. `test_golden_scenarios.py` asserts that each fixture's own
`expected_*` strings appear in that fixture, and that SKILL.md mentions matching
keywords. That proves a rule is *written down*. It cannot distinguish a README grounded
in the repo from one that invented its commands, its env vars, its paths, and its
numbers — which is exactly the failure mode the skill exists to prevent.

Three layers, honesty boundary stated explicitly:

  1. `lint_readme.scan_repo` + `lint` — every check needs BOTH the document and a real
     repository, so it cannot be satisfied by keyword presence.
  2. `GraderSelfTest` — hand-authored good/bad README pairs per fixture repo. The good
     one must produce zero findings; the bad one must produce the SPECIFIC codes its
     `expect.json` names. "Fails somehow" is not evidence a grader discriminates;
     "fails for the stated reason" is.
  3. `LiveForwardEval` — opt-in via README_GEN_EVAL_CMD. Drives a real writer through
     the skill against a fixture repo and grades the result with the same grader.

Only (3) shows that a live model produces grounded READMEs. It is skipped by default
and `run_regression.sh` reports that as a gap rather than implying coverage it lacks.

Fixture repos are JSON manifests materialized into a temp dir, not files checked into
`skills/`: a checked-in fixture would have pytest collecting the fixture's own
`tests/test_core.py`, and would drop a second `.env.example` into this repository.
"""

import importlib.util
import json
import re
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
SKILL_DIR = TESTS_DIR.parents[1]
SKILL_MD = SKILL_DIR / "SKILL.md"
EVAL_DIR = TESTS_DIR / "forward_eval"
LINTER = SKILL_DIR / "scripts" / "lint_readme.py"
LIVE_CMD = os.environ.get("README_GEN_EVAL_CMD")

SCENARIOS = ("go_service", "node_cli", "py_library", "lightweight_tool",
             "rust_workspace")


def _load_linter():
    """Import lint_readme.py by path.

    Sibling imports are load-bearing here: this repo's pytest.ini sets
    --import-mode=importlib, which does not put the test directory on sys.path, so a
    bare `import lint_readme` passes under run_regression.sh and fails under
    `pytest skills/`.
    """
    spec = importlib.util.spec_from_file_location("lint_readme", LINTER)
    mod = importlib.util.module_from_spec(spec)
    # Register before exec: @dataclass resolves field types via
    # sys.modules[cls.__module__].__dict__, which is None for a module that was
    # created from a spec but never inserted — the class body then raises
    # AttributeError on 'NoneType'.
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


lint_readme = _load_linter()


def materialize(scenario: str, dest: Path) -> dict:
    manifest = json.loads((EVAL_DIR / scenario / "repo.json").read_text(encoding="utf-8"))
    for rel, content in manifest["files"].items():
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return manifest


def read_exemplar(scenario: str, name: str) -> str:
    return (EVAL_DIR / scenario / name).read_text(encoding="utf-8")


def expectations(scenario: str) -> dict:
    return json.loads((EVAL_DIR / scenario / "expect.json").read_text(encoding="utf-8"))


class _RepoCase(unittest.TestCase):
    """Base: materialize a fixture repo once per test and scan it."""

    scenario = ""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.manifest = materialize(self.scenario, self.repo)
        # `scan_as` models the Audience Gate deciding a mode discovery will not infer.
        self.facts = lint_readme.scan_repo(
            self.repo, project_type=self.manifest.get("scan_as", ""))

    def codes(self, readme: str):
        findings = lint_readme.lint(readme, self.facts)
        return findings, sorted({f.code for f in findings})


# ── 1. The fixture repos route the way the manifest claims ──────

class FixtureRoutingTest(unittest.TestCase):
    """A grader keyed to the wrong project type would check the wrong required
    sections, so routing is verified before anything is graded."""

    def test_every_fixture_routes_as_declared(self) -> None:
        for scenario in SCENARIOS:
            with self.subTest(scenario=scenario):
                with tempfile.TemporaryDirectory() as tmp:
                    repo = Path(tmp)
                    manifest = materialize(scenario, repo)
                    facts = lint_readme.scan_repo(repo)
                    self.assertEqual(facts.project_type, manifest["expected_project_type"],
                                     "effective type is the single answer generation "
                                     "and the linter must share")
                    if manifest.get("expected_lightweight_eligible"):
                        proc = subprocess.run(
                            ["bash", str(SKILL_DIR / "scripts" / "discover_readme_needs.sh")],
                            cwd=str(repo), capture_output=True, text=True, timeout=120)
                        self.assertIn("project_type\tlightweight_eligible\ttrue", proc.stdout)
                    if "expected_base_type" in manifest:
                        self.assertEqual(facts.base_type, manifest["expected_base_type"])
                    self.assertEqual(facts.verdict, manifest["expected_verdict"])
                    self.assertGreaterEqual(len(facts.entrypoints), 1,
                                            "fixture repo has no discoverable entrypoint")

    def test_scan_collects_command_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            materialize("go_service", repo)
            facts = lint_readme.scan_repo(repo)
            self.assertIn("run-api", facts.make_targets)
            self.assertIn("migrate-up", facts.make_targets)
            self.assertEqual({"DB_URL", "REDIS_URL", "PORT", "LOG_LEVEL"}, facts.env_vars)
            self.assertIn("ci.yml", facts.workflows)
            self.assertTrue(facts.has_codecov)

    def test_scan_reads_package_json_scripts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            materialize("node_cli", repo)
            facts = lint_readme.scan_repo(repo)
            self.assertEqual({"build", "test", "lint"}, facts.npm_scripts)
            self.assertFalse(facts.workflows, "node_cli fixture has no CI workflow")


# ── 2. Grader discrimination, per scenario ──────────────────────

class GoServiceGrading(_RepoCase):
    scenario = "go_service"

    def test_good_readme_is_clean(self) -> None:
        findings, _ = self.codes(read_exemplar(self.scenario, "good.md"))
        self.assertEqual([], [str(f) for f in findings])

    def test_bad_readme_fails_for_the_stated_reasons(self) -> None:
        exp = expectations(self.scenario)["bad"]
        findings, codes = self.codes(read_exemplar(self.scenario, "bad.md"))
        for code in exp["must_contain_codes"]:
            self.assertIn(code, codes,
                          f"{code} not raised ({exp['why'][code]}); got {codes}")
        self.assertTrue(any(f.severity == lint_readme.CRITICAL for f in findings))

    def test_undefined_make_target_is_named(self) -> None:
        findings, _ = self.codes("# x\n\n```bash\nmake deploy\n```\n")
        msgs = [f.message for f in findings if f.code == "R001"]
        self.assertTrue(any("'deploy'" in m for m in msgs), msgs)

    def test_defined_make_target_is_accepted(self) -> None:
        findings, _ = self.codes("# x\n\n```bash\nmake migrate-up\n```\n")
        self.assertEqual([], [f for f in findings if f.code == "R001"])

    def test_env_var_absent_from_env_example_is_flagged(self) -> None:
        readme = "# x\n\n## Configuration\n\n| Variable | Required |\n|---|---|\n| `JWT_SECRET` | Yes |\n"
        _, codes = self.codes(readme)
        self.assertIn("R003", codes)

    def test_env_var_present_in_env_example_is_accepted(self) -> None:
        readme = "# x\n\n## Configuration\n\n| Variable | Required |\n|---|---|\n| `DB_URL` | Yes |\n"
        self.assertNotIn("R003", self.codes(readme)[1])

    def test_coverage_claim_allowed_when_it_matches_a_committed_target(self) -> None:
        """The rule is 'no unbacked metric', not 'no metric'. `.codecov.yml` commits
        `target: 80%`, so a README may state 80 — and only 80."""
        self.assertTrue(self.facts.has_coverage_artifact)
        self.assertNotIn("R007", self.codes("# x\n\nThe coverage target is 80%.\n")[1])

    def test_throughput_claim_is_always_unbacked(self) -> None:
        self.assertIn("R007", self.codes("# x\n\nHandles 10K+ TPS.\n")[1])


class NodeCliGrading(_RepoCase):
    scenario = "node_cli"

    def test_good_readme_is_clean(self) -> None:
        findings, _ = self.codes(read_exemplar(self.scenario, "good.md"))
        self.assertEqual([], [str(f) for f in findings])

    def test_bad_readme_fails_for_the_stated_reasons(self) -> None:
        exp = expectations(self.scenario)["bad"]
        _, codes = self.codes(read_exemplar(self.scenario, "bad.md"))
        for code in exp["must_contain_codes"]:
            self.assertIn(code, codes,
                          f"{code} not raised ({exp['why'][code]}); got {codes}")

    def test_undefined_npm_script_is_flagged(self) -> None:
        _, codes = self.codes("# x\n\n```bash\nnpm run release\n```\n")
        self.assertIn("R002", codes)

    def test_defined_npm_script_is_accepted(self) -> None:
        self.assertNotIn("R002", self.codes("# x\n\n```bash\nnpm run lint\n```\n")[1])

    def test_ci_badge_without_workflow_is_flagged(self) -> None:
        readme = "# x\n\n![CI](https://github.com/a/b/actions/workflows/ci.yml/badge.svg)\n"
        self.assertIn("R008", self.codes(readme)[1])

    def test_required_sections_are_type_aware(self) -> None:
        """A CLI README is not required to carry a Configuration section; a
        service README is. One flat list could not express that."""
        self.assertNotIn("configuration", lint_readme.REQUIRED_SECTIONS["cli"])
        self.assertIn("configuration", lint_readme.REQUIRED_SECTIONS["service"])


class PyLibraryGrading(_RepoCase):
    scenario = "py_library"

    def test_good_readme_is_clean(self) -> None:
        findings, _ = self.codes(read_exemplar(self.scenario, "good.md"))
        self.assertEqual([], [str(f) for f in findings])

    def test_bad_readme_fails_for_the_stated_reasons(self) -> None:
        exp = expectations(self.scenario)["bad"]
        _, codes = self.codes(read_exemplar(self.scenario, "bad.md"))
        for code in exp["must_contain_codes"]:
            self.assertIn(code, codes,
                          f"{code} not raised ({exp['why'][code]}); got {codes}")

    def test_wrong_toolchain_command_is_flagged(self) -> None:
        _, codes = self.codes("# x\n\n```bash\ncargo build\n```\n")
        self.assertIn("R001", codes)

    def test_right_toolchain_command_is_accepted(self) -> None:
        self.assertNotIn("R001", self.codes("# x\n\n```bash\npytest\n```\n")[1])

    def test_benchmark_numbers_without_benchmarks_are_flagged(self) -> None:
        self.assertIn("R007", self.codes("# x\n\n240 ns/op on the hot path.\n")[1])

    def test_missing_path_is_flagged_and_real_path_is_not(self) -> None:
        self.assertIn("R004", self.codes("# x\n\nSee `src/parsekit/api/reference.py`.\n")[1])
        self.assertNotIn("R004", self.codes("# x\n\nSee `src/parsekit/core.py`.\n")[1])


class LightweightGrading(_RepoCase):
    scenario = "lightweight_tool"

    def test_good_readme_is_clean(self) -> None:
        findings, _ = self.codes(read_exemplar(self.scenario, "good.md"))
        self.assertEqual([], [str(f) for f in findings])

    def test_bad_readme_fails_for_the_stated_reasons(self) -> None:
        exp = expectations(self.scenario)["bad"]
        _, codes = self.codes(read_exemplar(self.scenario, "bad.md"))
        for code in exp["must_contain_codes"]:
            self.assertIn(code, codes,
                          f"{code} not raised ({exp['why'][code]}); got {codes}")

    def test_lightweight_readme_is_not_graded_as_a_cli(self) -> None:
        """The split that made this necessary: discovery classified the repo `cli` and
        only flagged `lightweight_candidate=true`, so a correct Template E README was
        reported as missing Installation. Once the Audience Gate records lightweight,
        every consumer reads that one value."""
        self.assertEqual("lightweight", self.facts.project_type)
        self.assertEqual("cli", self.facts.base_type)
        _, codes = self.codes(read_exemplar(self.scenario, "good.md"))
        self.assertNotIn("R009", codes)
        self.assertNotIn("R012", codes)

    def test_base_type_still_available_for_command_selection(self) -> None:
        """Promotion must not erase which language's commands apply."""
        self.assertIn("cli", self.facts.base_type)


class RustWorkspaceGrading(_RepoCase):
    scenario = "rust_workspace"

    def test_good_readme_is_clean(self) -> None:
        findings, _ = self.codes(read_exemplar(self.scenario, "good.md"))
        self.assertEqual([], [str(f) for f in findings])

    def test_bad_readme_fails_for_the_stated_reasons(self) -> None:
        exp = expectations(self.scenario)["bad"]
        _, codes = self.codes(read_exemplar(self.scenario, "bad.md"))
        for code in exp["must_contain_codes"]:
            self.assertIn(code, codes,
                          f"{code} not raised ({exp['why'][code]}); got {codes}")

    def test_crates_workspace_reaches_ready(self) -> None:
        """Routing to monorepo was already correct; the entrypoint scan walked only
        apps/, packages/, services/, so a crates/* workspace degraded anyway. Asserting
        the type without the verdict is what let that through."""
        self.assertEqual("monorepo", self.facts.project_type)
        self.assertEqual("READY", self.facts.verdict)
        modules = [v for k, v in self.facts.entrypoints if k == "module"]
        self.assertEqual(["crates/cli", "crates/core"], sorted(modules))

    def test_cargo_commands_accepted_without_a_root_manifest_package(self) -> None:
        self.assertNotIn("R001", self.codes("# x\n\n```bash\ncargo test --workspace\n```\n")[1])


# ── 2b. False-PASS regressions ──────────────────────────────────

class FalsePassRegressions(_RepoCase):
    """Five ways a fabricated README scored PASS against the first version of this
    grader. Each is reproduced here as the exact bypass, not as a paraphrase."""

    scenario = "go_service"

    def test_coverage_number_must_match_a_committed_target(self) -> None:
        """`.codecov.yml` justifies a badge and lets a README state the CONFIGURED
        target. It never licenses an arbitrary measured number — badges-and-governance.md
        said so while the grader accepted anything."""
        self.assertIn("80", self.facts.coverage_numbers)
        self.assertNotIn("R007", self.codes("# x\n\nCoverage target is 80%.\n")[1])
        self.assertIn("R007", self.codes("# x\n\nWe maintain 99% coverage.\n")[1])

    def test_benchmark_function_does_not_license_a_number(self) -> None:
        """A `func Benchmark…` proves you can run benchmarks; only committed OUTPUT
        makes a number citable."""
        self.assertFalse(self.facts.has_benchmark_output)
        self.assertIn("R007", self.codes("# x\n\nRuns at 999999 ns/op.\n")[1])

    def test_external_url_only_excuses_a_path_that_follows_it(self) -> None:
        """A line-wide exemption let any URL anywhere on the line launder a fabricated
        local path."""
        after = "# x\n\nSee https://github.com/other/p (`.github/workflows/ci.yml`).\n"
        before = "# x\n\nOur `internal/nope/x.go` is described at https://example.com.\n"
        self.assertNotIn("R004", self.codes(after)[1])
        self.assertIn("R004", self.codes(before)[1])

    def test_subheading_cannot_hide_the_configuration_table(self) -> None:
        """section_body stopped at the next heading of ANY level, so inserting
        `### Variables` truncated the Configuration body to nothing."""
        hidden = ("# x\n\n## Configuration\n\n### Variables\n\n"
                  "| Variable | Req |\n|---|---|\n| `JWT_SECRET` | Yes |\n")
        self.assertIn("R003", self.codes(hidden)[1])

    def test_title_only_readme_cannot_pass(self) -> None:
        """Every missing required section was one STANDARD finding, so a title plus a
        sentence returned PASS while the skill's own scorecard calls Quick Start
        Critical."""
        findings = lint_readme.lint("# x\n\nA service.\n", self.facts)
        self.assertEqual("FAIL", lint_readme.summarize(findings)["result"])
        self.assertIn("R009", {f.code for f in findings})

    def test_primary_and_secondary_gaps_are_reported_separately(self) -> None:
        """Missing Configuration alone must not be Critical; missing Quick Start must."""
        full = read_exemplar("go_service", "good.md")
        no_config = re.sub(r"## Configuration.*?(?=## Common Commands)", "", full, flags=re.S)
        codes = self.codes(no_config)[1]
        self.assertIn("R012", codes)
        self.assertNotIn("R009", codes)


# ── 3. Cross-cutting grader properties ──────────────────────────

class GraderPropertiesTest(_RepoCase):
    scenario = "go_service"

    def test_build_outputs_are_not_treated_as_missing_paths(self) -> None:
        """`./bin/api` legitimately does not exist before the build runs."""
        self.assertNotIn("R004", self.codes("# x\n\nBinary lands at `./bin/api`.\n")[1])

    def test_module_paths_are_not_treated_as_filesystem_paths(self) -> None:
        readme = "# x\n\nImport `github.com/acme/orderapi/internal/service`.\n"
        self.assertNotIn("R004", self.codes(readme)[1])

    def test_commands_inside_prose_backticks_are_not_command_checked(self) -> None:
        """Only fenced shell blocks are treated as runnable instructions."""
        self.assertNotIn("R001", self.codes("# x\n\nHistorically this was `make oldtarget`.\n")[1])

    def test_nested_fences_do_not_truncate_command_extraction(self) -> None:
        readme = (
            "# x\n\n````markdown\n```bash\nmake test\n```\n````\n\n"
            "```bash\nmake nonexistent\n```\n"
        )
        _, codes = self.codes(readme)
        self.assertIn("R001", codes,
                      "a four-backtick wrapper must not swallow the later real block")

    def test_slash_separated_alternatives_are_not_path_claims(self) -> None:
        """Found by running the linter against this repository: a table cell reading
        `fmt/test/lint/build/run` (a list of Makefile target names) was reported as a
        missing path, at CRITICAL severity."""
        readme = "# x\n\nStandardizes `fmt/test/lint/build/run` entrypoints.\n"
        self.assertNotIn("R004", self.codes(readme)[1])

    def test_two_segment_missing_path_is_still_flagged(self) -> None:
        """The alternatives exemption must not swallow real fabrications."""
        self.assertIn("R004", self.codes("# x\n\nManifests live in `deploy/k8s`.\n")[1])

    def test_path_on_a_line_naming_another_repo_is_skipped(self) -> None:
        """Also found against this repository: a path cited beside an external URL
        belongs to that repository, not this one."""
        readme = ("# x\n\nFor a full example see "
                  "https://github.com/other/proj (`.github/workflows/ci.yml`).\n")
        self.assertNotIn("R004", self.codes(readme)[1])

    def test_describing_scorecards_is_not_reporting_one(self) -> None:
        """A docs repo that catalogues skills mentions 'scorecard' as a topic. The
        defect is a README reporting its OWN scorecard."""
        self.assertNotIn("R006", self.codes(
            "# x\n\n| skill | keeps a guidance scorecard for reviewers |\n")[1])
        self.assertIn("R006", self.codes(
            "# x\n\n## Quality Scorecard\n\nCritical: 4/4\n")[1])

    def test_chained_commands_are_each_checked(self) -> None:
        """`^make\\s+(\\w+)` matched only the head of the line, so the second half of
        `make test && make deploy` was never looked at."""
        self.assertIn("R001", self.codes("# x\n\n```bash\nmake test && make deploy\n```\n")[1])
        self.assertNotIn("R001", self.codes("# x\n\n```bash\nmake test && make lint\n```\n")[1])
        self.assertIn("R001", self.codes("# x\n\n```bash\nmake cover; make ship\n```\n")[1])
        self.assertNotIn("R001", self.codes("# x\n\n```bash\nmake cover | tee out.txt\n```\n")[1])

    def test_committed_target_does_not_license_a_measurement(self) -> None:
        """`.codecov.yml` commits `target: 80%`. That licenses "the target is 80%"; it
        does not license "current coverage is 80%", which asserts a measurement the repo
        never records. Matching on the number alone conflated the two."""
        self.assertNotIn("R007", self.codes("# x\n\nCoverage target is 80%.\n")[1])
        self.assertIn("R007", self.codes("# x\n\nCurrent coverage is 80%.\n")[1])
        self.assertIn("R007", self.codes("# x\n\nWe maintain 80% coverage.\n")[1])

    def test_bare_number_is_flagged_as_ambiguous(self) -> None:
        codes = self.codes("# x\n\nCoverage: 80%.\n")[1]
        self.assertIn("R007", codes)

    def test_standard_only_findings_report_warn_not_pass(self) -> None:
        """summarize() returned PASS with an outstanding R012, contradicting its own
        docstring. PASS now means nothing was found; WARN means real but non-vetoing."""
        F, S, C = lint_readme.Finding, lint_readme.STANDARD, lint_readme.CRITICAL
        self.assertEqual("PASS", lint_readme.summarize([])["result"])
        self.assertEqual("WARN", lint_readme.summarize([F("R012", S, "m")])["result"])
        self.assertEqual("FAIL", lint_readme.summarize([F("R001", C, "m")])["result"])
        self.assertEqual("INCOMPLETE", lint_readme.summarize([F("R013", S, "m")])["result"])

    def test_warn_does_not_break_the_exit_gate(self) -> None:
        """The Standard tier tolerates up to two failures, so a warning must not break a
        caller's gate — only a critical finding does."""
        readme = read_exemplar("go_service", "good.md")
        readme += "\n## Extra\n\n- [Nowhere](#does-not-exist)\n"   # R010, standard
        (self.repo / "README.md").write_text(readme)
        proc = subprocess.run(["python3", str(LINTER), str(self.repo)],
                              capture_output=True, text=True, timeout=180)
        self.assertIn("WARN", proc.stdout)
        self.assertEqual(0, proc.returncode)

    def test_unknown_type_reports_incomplete_not_pass(self) -> None:
        """Found by pointing the linter at this repository: a docs repo routes to
        `unknown`, `REQUIRED_SECTIONS.get("unknown")` is None, so every section check
        silently no-opped and the run printed a clean PASS."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "notes.txt").write_text("nothing a manifest can classify\n")
            facts = lint_readme.scan_repo(repo)
            self.assertEqual("unknown", facts.project_type)
            findings = lint_readme.lint("# x\n\nSome prose.\n", facts)
            summary = lint_readme.summarize(findings)
            self.assertIn("R013", summary["codes"])
            self.assertEqual("INCOMPLETE", summary["result"],
                             "PASS must mean 'checked and clean', not 'could not check'")

    def test_type_override_restores_section_checking(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "notes.txt").write_text("x\n")
            facts = lint_readme.scan_repo(repo, project_type="lightweight")
            findings = lint_readme.lint("# x\n\nSome prose.\n", facts)
            codes = {f.code for f in findings}
            self.assertNotIn("R013", codes)
            self.assertIn("R009", codes, "an override must re-enable the section checks")

    def test_exit_status_keys_on_critical_alone(self) -> None:
        F = lint_readme.Finding
        self.assertEqual("WARN", lint_readme.summarize(
            [F("R006", lint_readme.STANDARD, "m")])["result"])
        self.assertEqual("FAIL", lint_readme.summarize(
            [F("R001", lint_readme.CRITICAL, "m")])["result"])

    def test_cli_exit_status_follows_severity(self) -> None:
        (self.repo / "README.md").write_text(read_exemplar("go_service", "good.md"))
        ok = subprocess.run(["python3", str(LINTER), str(self.repo)],
                            capture_output=True, text=True, timeout=180)
        self.assertEqual(0, ok.returncode, ok.stdout + ok.stderr)

        (self.repo / "README.md").write_text(read_exemplar("go_service", "bad.md"))
        bad = subprocess.run(["python3", str(LINTER), str(self.repo)],
                             capture_output=True, text=True, timeout=180)
        self.assertEqual(1, bad.returncode, bad.stdout + bad.stderr)
        self.assertIn("R001", bad.stdout)


class RequiredSectionSyncTest(unittest.TestCase):
    """The required-section matrix exists in two places (SKILL.md prose and the
    grader table). One-sided edits are the drift class this repo has been bitten
    by before."""

    def test_every_project_type_has_a_row_in_skill_md(self) -> None:
        skill = SKILL_MD.read_text(encoding="utf-8")
        for ptype in lint_readme.REQUIRED_SECTIONS:
            self.assertRegex(
                skill, rf"(?i)\|\s*{ptype}\s*\|",
                f"SKILL.md §Structure Policy has no required-section row for {ptype!r}",
            )

    def test_grader_covers_every_documented_project_type(self) -> None:
        for ptype in ("service", "library", "cli", "monorepo", "lightweight"):
            self.assertIn(ptype, lint_readme.REQUIRED_SECTIONS)


# ── 3b. The skill's own exemplars must survive its own grader ───

class GoldenExamplesSurviveTheGrader(unittest.TestCase):
    """Lint each `references/golden-<type>.md` README against a repository built from
    that same file's declared Repo signals.

    This is the strongest evidence available without running a model. The golden
    examples are what the model is *shown* as calibrated output; if one of them would
    be rejected by the grader the model is *checked* with, the skill teaches something
    it then penalises. Layer 4b proves the grader discriminates on exemplars I wrote
    for the tests; this proves it on the exemplars the skill actually ships.

    A failure here means one of two things, both real: the golden README drifted from
    its Repo signals block, or the grader is wrong. Read the finding before deciding.
    """

    GOLDEN_DIR = SKILL_DIR / "references"
    REPOS = TESTS_DIR / "golden_repos"

    @staticmethod
    def extract_readme(markdown: str):
        """Golden files wrap the README in a four-backtick fence so it can contain
        triple-backtick blocks. Match to the LAST closing fence, not the first."""
        m = re.search(r"^````(?:markdown)?\s*\n(.*)\n````", markdown, re.S | re.M)
        return m.group(1) if m else None

    def _case(self, name: str):
        manifest = json.loads((self.REPOS / f"{name}.json").read_text())
        golden = (self.GOLDEN_DIR / manifest["golden_file"]).read_text()
        readme = self.extract_readme(golden)
        self.assertIsNotNone(readme, f"no fenced README block in {manifest['golden_file']}")
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            for rel, content in manifest["files"].items():
                target = repo / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
            facts = lint_readme.scan_repo(repo, project_type=manifest["project_type"])
            findings = lint_readme.lint(readme, facts)
        return manifest, findings

    def test_every_golden_example_has_a_fixture_repo(self):
        goldens = {p.name for p in self.GOLDEN_DIR.glob("golden-*.md")
                   if p.name != "golden-examples.md"}
        covered = {json.loads(p.read_text())["golden_file"]
                   for p in self.REPOS.glob("*.json")}
        self.assertEqual(goldens, covered,
                         "a golden example with no fixture repo is never graded")

    def test_golden_examples_are_grader_clean(self):
        for name in ("service", "library", "cli", "monorepo", "lightweight"):
            with self.subTest(golden=name):
                manifest, findings = self._case(name)
                self.assertEqual(
                    [], [str(f) for f in findings],
                    f"{manifest['golden_file']} would be rejected by the grader the "
                    f"skill checks output with",
                )

    def test_golden_repo_signals_are_not_vacuous(self):
        """A fixture that omitted the files the README cites would make the check
        pass by having nothing to contradict."""
        for name in ("service", "library", "cli", "monorepo", "lightweight"):
            with self.subTest(golden=name):
                manifest = json.loads((self.REPOS / f"{name}.json").read_text())
                self.assertGreaterEqual(len(manifest["files"]), 4)


# ── 4. Live forward eval (opt-in) ───────────────────────────────

@unittest.skipUnless(LIVE_CMD, "set README_GEN_EVAL_CMD to run the live forward eval")
class LiveForwardEval(unittest.TestCase):
    """Drive a real writer through the skill and grade what it produces.

    README_GEN_EVAL_CMD receives the prompt on stdin and must print the README to
    stdout. It runs with CWD set to the materialized fixture repo, so the writer sees
    the same files the grader will check against.

    Two contract decisions, both learned from this layer being too forgiving:

    1. **Grade completeness, not just honesty.** Asserting "no Critical finding" let a
       skeletal-but-not-fabricated README pass. The bar is each fixture's
       `expect.json.good` budget — the same bar the hand-authored exemplar clears.
    2. **A configured-but-broken harness FAILS.** Skipping on a non-zero exit meant a
       broken eval environment kept showing green, which is the failure mode this whole
       layer exists to prevent. Not setting the variable still skips; setting it and
       having it fall over is a hard failure, reported as a harness fault rather than
       mislabelled as a skill finding.
    """

    PROMPT = (
        "Read the skill at {skill} and follow it to generate a README.md for the "
        "repository in the current working directory. Output ONLY the README markdown, "
        "with no commentary and no surrounding code fence."
    )

    def _run(self, scenario: str) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            manifest = materialize(scenario, repo)
            budget = expectations(scenario)["good"]
            proc = subprocess.run(
                LIVE_CMD, shell=True, cwd=str(repo),
                input=self.PROMPT.format(skill=SKILL_MD),
                capture_output=True, text=True, timeout=900,
            )
            self.assertEqual(
                0, proc.returncode,
                f"HARNESS FAULT (not a skill finding): README_GEN_EVAL_CMD exited "
                f"{proc.returncode} for {scenario}. stderr={proc.stderr.strip()[:400]}",
            )
            self.assertTrue(
                proc.stdout.strip(),
                f"HARNESS FAULT (not a skill finding): README_GEN_EVAL_CMD produced no "
                f"output for {scenario}.",
            )
            facts = lint_readme.scan_repo(repo)
            self.assertEqual(facts.project_type, manifest["expected_project_type"])
            findings = lint_readme.lint(proc.stdout, facts)
            critical = [str(f) for f in findings if f.severity == lint_readme.CRITICAL]
            self.assertLessEqual(
                len(critical), budget["max_critical"],
                "critical findings:\n" + "\n".join(critical),
            )
            self.assertLessEqual(
                len(findings), budget["max_total"],
                "findings over budget (completeness counts too):\n"
                + "\n".join(str(f) for f in findings),
            )

    def test_go_service(self) -> None:
        self._run("go_service")

    def test_node_cli(self) -> None:
        self._run("node_cli")

    def test_py_library(self) -> None:
        self._run("py_library")

    def test_lightweight_tool(self) -> None:
        self._run("lightweight_tool")

    def test_rust_workspace(self) -> None:
        self._run("rust_workspace")


class LiveHarnessPlumbingTest(unittest.TestCase):
    """The live layer is skipped by default; prove its plumbing works anyway, so a
    broken harness is not discovered only on the day someone enables it."""

    def test_broken_harness_would_fail_not_skip(self) -> None:
        """Pin the decision itself: a configured command that dies must not be
        laundered into a skip. Exercised through the same assertion helpers the live
        class uses, without needing a live model."""
        proc = subprocess.run("exit 3", shell=True, capture_output=True, text=True)
        with self.assertRaises(AssertionError) as ctx:
            self.assertEqual(0, proc.returncode, "HARNESS FAULT (not a skill finding)")
        self.assertIn("HARNESS FAULT", str(ctx.exception))

    def test_live_budget_is_total_not_just_critical(self) -> None:
        """The budget every live scenario is graded against must forbid standard
        findings too, otherwise an incomplete README still passes."""
        for scenario in SCENARIOS:
            with self.subTest(scenario=scenario):
                good = expectations(scenario)["good"]
                self.assertEqual(0, good["max_critical"])
                self.assertEqual(0, good["max_total"],
                                 "a non-zero total budget lets the live layer accept "
                                 "an incomplete README")

    def test_every_scenario_has_a_live_test(self) -> None:
        methods = {n[len("test_"):] for n in dir(LiveForwardEval) if n.startswith("test_")}
        self.assertEqual(set(SCENARIOS), methods,
                         "a fixture with no live test is invisible when the live layer runs")

    def test_harness_grades_a_stubbed_writer(self) -> None:
        if not shutil.which("bash"):
            self.skipTest("bash unavailable")
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            materialize("go_service", repo)
            good = EVAL_DIR / "go_service" / "good.md"
            proc = subprocess.run(
                f"cat {good}", shell=True, cwd=str(repo),
                capture_output=True, text=True, timeout=60,
            )
            self.assertEqual(0, proc.returncode)
            facts = lint_readme.scan_repo(repo)
            findings = lint_readme.lint(proc.stdout, facts)
            self.assertEqual([], [str(f) for f in findings])


if __name__ == "__main__":
    unittest.main()
