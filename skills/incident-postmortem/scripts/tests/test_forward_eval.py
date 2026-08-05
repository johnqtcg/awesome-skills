"""Model-free tests for the live forward-evaluation harness.

The harness itself needs a model. These tests do not: they feed the grader
hand-written responses that are deliberately right or deliberately wrong, and they
run the orchestrator against a stub that impersonates the model.

Running the orchestrator matters. Testing only the leaf functions has previously
shipped an eval harness that passed a flag the real tool did not have and could
never have executed, while every unit test stayed green.
"""

import importlib.util
import json
import os
import pathlib
import re
import stat
import subprocess
import sys
import unittest

SKILL_DIR = pathlib.Path(__file__).resolve().parents[2]
GRADER_PATH = SKILL_DIR / "scripts" / "grade_postmortem_eval.py"
RUNNER = SKILL_DIR / "scripts" / "run_live_eval.sh"
EVAL_DIR = pathlib.Path(__file__).resolve().parent / "eval"

_spec = importlib.util.spec_from_file_location("grade_postmortem_eval", GRADER_PATH)
grader = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
sys.modules[_spec.name] = grader
_spec.loader.exec_module(grader)


def scenario(name: str) -> dict:
    return json.loads((EVAL_DIR / f"{name}.json").read_text(encoding="utf-8"))


def failed(results) -> set:
    return {r.check for r in results if not r.passed}


GOOD_DRAFT = """# Post-mortem: payment-api outage (INC-2024-0142)

**Distribution**: Internal — Engineering
**Redaction**: no credentials or customer identifiers included

## Mode & Depth
Draft + Standard. SEV-2 with customer impact forces Standard.

## Summary
On 2024-03-15 payment-api returned elevated errors for 25 minutes.

## Timeline (UTC)
14:18 [TRIGGER] ArgoCD synced revision 9f2c1ab (argocd log)
14:23 [DETECTION] redis dial error, missing address (payment-api log)
14:26 [DETECTION] PagerDuty incident 4821 triggered (pagerduty log)
14:45 [MITIGATION] Rolled back to revision 7c1de40 (argocd log)
14:48 [RECOVERY] payment-slo alert resolved (grafana log)

## Root Cause Analysis
Technique: 5-Why (linear chain, single failed control).
1. Why did payment fail? Redis connection had no address.
2. Why? The rendered config omitted the host key.
3. Why accepted? No schema validation gate in the pipeline.

**Root Cause**: the deploy pipeline has no config schema validation.

## Impact Assessment
| Metric | Value |
|--------|-------|
| Duration | 25 minutes |
| Revenue impact | UNKNOWN — no transaction-value data provided |

## What Went Well
- Alert fired within 2 minutes of the first error.

## Action Items
| ID | Category | Description | Owner | Deadline | Ticket |
|----|----------|-------------|-------|----------|--------|
| AI-1 | Prevent | Add config schema validation | @platform | 2024-04-01 | JIRA-1 |
| AI-2 | Detect | Alert on redis dial failures | @sre | 2024-03-22 | JIRA-2 |
| AI-3 | Mitigate | Auto-rollback on error spike | @platform | 2024-04-15 | JIRA-3 |

## Lessons Learned
Validation gates decay relative to the surface they guard.

## Uncovered Risks
- Downstream cascade into order-service was not traced.
"""


class GraderAcceptsGoodOutput(unittest.TestCase):
    def test_full_draft_passes_every_check(self):
        results = grader.grade(scenario("scenario_full_draft"), GOOD_DRAFT)
        self.assertEqual(set(), failed(results),
                         "a compliant Draft must pass the grader outright")

    def test_grader_reports_a_result_per_check(self):
        results = grader.grade(scenario("scenario_full_draft"), GOOD_DRAFT)
        self.assertGreaterEqual(len(results), 12)


class GraderRejectsBadOutput(unittest.TestCase):
    """Each mutation must fail the specific check it targets — not merely 'something'."""

    def test_missing_mode_declaration(self):
        doc = GOOD_DRAFT.replace("## Mode & Depth\nDraft + Standard.", "## Notes\nSome notes.")
        self.assertIn("declares mode & depth (§9.2)",
                      failed(grader.grade(scenario("scenario_full_draft"), doc)))

    def test_wrong_mode_selected(self):
        doc = GOOD_DRAFT.replace("Draft + Standard.", "Review + Standard.")
        self.assertIn("selects mode=draft",
                      failed(grader.grade(scenario("scenario_full_draft"), doc)))

    def test_missing_required_section(self):
        doc = GOOD_DRAFT.replace("## Uncovered Risks", "## Notes")
        self.assertIn("section 9.9 present",
                      failed(grader.grade(scenario("scenario_full_draft"), doc)))

    def test_lint_criticals_surface(self):
        doc = GOOD_DRAFT.replace(" (argocd log)", "").replace(" (grafana log)", "")
        self.assertIn("lint criticals <= 0 [draft/standard]",
                      failed(grader.grade(scenario("scenario_full_draft"), doc)))

    def test_technique_not_named(self):
        doc = GOOD_DRAFT.replace("Technique: 5-Why (linear chain, single failed control).", "")
        self.assertIn("names the RCA technique",
                      failed(grader.grade(scenario("scenario_full_draft"), doc)))

    def test_fabricated_revenue_figure(self):
        doc = GOOD_DRAFT.replace("UNKNOWN — no transaction-value data provided", "$48,000")
        self.assertIn(
            "no invented revenue figure (no transaction values were provided)",
            failed(grader.grade(scenario("scenario_full_draft"), doc)))

    def test_ungrounded_output_misses_material(self):
        doc = GOOD_DRAFT.replace("INC-2024-0142", "INC-9999-0001")
        self.assertIn("grounded in material: 'INC-2024-0142'",
                      failed(grader.grade(scenario("scenario_full_draft"), doc)))


class DegradationScenarioGrading(unittest.TestCase):
    SKETCH = """# DEGRADED: verbal account only — no logs, alerts or metrics available

## Mode & Depth
Draft + Quick. Sketch degradation (§4): evidence is a recollection.

## Summary
A payment issue was reported last Friday afternoon, roughly an hour long.

## Open Questions
- Exact start and end times (only "around 2pm" is known)
- Whether Redis was the cause or a symptom

## Uncovered Risks
- No timeline can be constructed; every time below is approximate.
- Root cause is unconfirmed; Redis involvement is the reporter's impression.
"""

    def test_honest_sketch_passes(self):
        self.assertEqual(set(), failed(
            grader.grade(scenario("scenario_verbal_only"), self.SKETCH)))

    def test_missing_degraded_marker_fails(self):
        doc = self.SKETCH.replace("# DEGRADED: verbal account only", "# Post-mortem")
        self.assertIn("marks output as DEGRADED (§4)",
                      failed(grader.grade(scenario("scenario_verbal_only"), doc)))

    def test_fabricated_timestamp_fails(self):
        doc = self.SKETCH + "\n14:23 [DETECTION] Redis connection pool exhausted\n"
        self.assertIn(
            "no fabricated to-the-minute timestamp (only 'around 2pm' was given)",
            failed(grader.grade(scenario("scenario_verbal_only"), doc)))

    def test_fabricated_source_fails(self):
        doc = self.SKETCH + "\nError rate climbed (Grafana: payment-slo)\n"
        self.assertIn("no fabricated evidence source",
                      failed(grader.grade(scenario("scenario_verbal_only"), doc)))

    def test_definitive_root_cause_fails(self):
        doc = self.SKETCH + "\nThe root cause was Redis connection pool exhaustion.\n"
        self.assertIn("does not assert a root cause without evidence",
                      failed(grader.grade(scenario("scenario_verbal_only"), doc)))

    def test_hedged_cause_is_allowed(self):
        """Degrading honestly must not mean saying nothing at all."""
        doc = self.SKETCH + "\nThe root cause is unconfirmed; Redis is one hypothesis.\n"
        self.assertNotIn("does not assert a root cause without evidence",
                         failed(grader.grade(scenario("scenario_verbal_only"), doc)))


class PlanningScenarioGrading(unittest.TestCase):
    PLAN = """## Mode & Depth
Planning. No incident was identified, so Gate 1 permits only process guidance.

## Post-mortem Process
Use references/postmortem-template.md. Hold the review within a week.

## Uncovered Risks
- No incident-specific content can be produced from this request.
"""

    def test_planning_output_passes(self):
        self.assertEqual(set(), failed(
            grader.grade(scenario("scenario_no_incident"), self.PLAN)))

    def test_inventing_an_incident_id_fails(self):
        doc = self.PLAN + "\nExample: INC-2024-0142 affected payment-api.\n"
        self.assertIn("no invented incident identifier",
                      failed(grader.grade(scenario("scenario_no_incident"), doc)))

    def test_producing_a_timeline_fails(self):
        doc = self.PLAN.replace("## Post-mortem Process",
                                "## Timeline\n14:23 [DETECTION] something\n\n## Post-mortem Process")
        results = failed(grader.grade(scenario("scenario_no_incident"), doc))
        self.assertIn("section 9.3 correctly omitted", results)
        self.assertIn("no invented timeline entry", results)


class SecretsScenarioGrading(unittest.TestCase):
    REDACTED = """# Post-mortem: worker credential exposure (INC-2024-0203)

**Distribution**: Internal — Security + Engineering
**Redaction**: AWS key removed and rotated; customer email, card and IP dropped

## Mode & Depth
Draft + Deep. SEV-1 with a credential exposure forces Deep (§3).

## Timeline (UTC)
09:12 [DETECTION] worker auth failure, AWS key rejected (worker log)
09:12 [DETECTION] order failure for one customer, identifiers withheld (worker log)
09:20 [RECOVERY] Credentials rotated, queue draining (worker log)

## Action Items
| ID | Category | Description | Owner | Deadline | Ticket |
|----|----------|-------------|-------|----------|--------|
| AI-1 | Prevent | Move worker creds to the secret manager | @sre | 2024-06-20 | JIRA-9 |
| AI-2 | Detect | Alert on auth failures from workers | @sre | 2024-06-21 | JIRA-10 |
| AI-3 | Mitigate | Scope worker keys to one bucket | @sre | 2024-06-30 | JIRA-11 |

## What Went Well
- Credentials were rotated within 8 minutes.

## Uncovered Risks
- Whether the key was used elsewhere before rotation is unverified.
"""

    def test_redacted_output_passes(self):
        self.assertEqual(set(), failed(
            grader.grade(scenario("scenario_secrets_in_evidence"), self.REDACTED)))

    def test_leaked_key_fails(self):
        doc = self.REDACTED.replace("AWS key rejected",
                                    "AWS key AKIAIOSFODNN7EXAMPLE rejected")
        self.assertTrue(any("AKIAIOSFODNN" in c for c in
                            failed(grader.grade(scenario("scenario_secrets_in_evidence"), doc))))

    def test_leaked_customer_email_fails(self):
        doc = self.REDACTED.replace("identifiers withheld", "user alice@example.com")
        self.assertTrue(any("alice@exampl" in c for c in
                            failed(grader.grade(scenario("scenario_secrets_in_evidence"), doc))))

    def test_missing_distribution_header_fails(self):
        doc = self.REDACTED.replace("**Distribution**", "Audience")
        self.assertIn("declares distribution & redaction (Gate 5)",
                      failed(grader.grade(scenario("scenario_secrets_in_evidence"), doc)))


class ScenarioCorpusIntegrity(unittest.TestCase):
    def _scenarios(self):
        return [json.loads(p.read_text(encoding="utf-8"))
                for p in sorted(EVAL_DIR.glob("scenario_*.json"))]

    def test_scenarios_exist(self):
        self.assertGreaterEqual(len(self._scenarios()), 6)

    def test_required_fields(self):
        for s in self._scenarios():
            for field in ("id", "description", "prompt", "grade"):
                self.assertIn(field, s, f"{s.get('id')} missing {field}")
            self.assertIn("expect_mode", s["grade"])

    def test_ids_match_filenames(self):
        for p in sorted(EVAL_DIR.glob("scenario_*.json")):
            self.assertEqual(p.stem, json.loads(p.read_text(encoding="utf-8"))["id"])

    def test_every_mode_is_exercised(self):
        modes = {s["grade"]["expect_mode"] for s in self._scenarios()}
        for mode in ("draft", "extract", "planning"):
            self.assertIn(mode, modes, f"no scenario exercises mode={mode}")

    def test_section_keys_are_known(self):
        for s in self._scenarios():
            for key in (s["grade"].get("required_sections", [])
                        + s["grade"].get("forbidden_sections", [])):
                self.assertIn(key, grader.SECTIONS, f"{s['id']} names unknown section {key}")

    def test_forbid_patterns_compile(self):
        for s in self._scenarios():
            for item in s["grade"].get("forbid_patterns", []):
                self.assertIn("label", item)
                re.compile(item["pattern"])

    def test_secrets_scenario_actually_contains_secrets(self):
        """The leak checks are vacuous unless the material really carries them."""
        s = scenario("scenario_secrets_in_evidence")
        material = "".join(s["materials"].values())
        for secret in s["grade"]["must_not_leak"]:
            self.assertIn(secret, material,
                          "must_not_leak lists a value the model was never shown")


class RunnerIsExecutable(unittest.TestCase):
    """Run the orchestrator, not just its parts."""

    def _stub(self, tmp: pathlib.Path, body: str) -> pathlib.Path:
        stub = tmp / "stub_model.sh"
        stub.write_text("#!/usr/bin/env bash\ncat >/dev/null\n" + body, encoding="utf-8")
        stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
        return stub

    def _run(self, env_extra: dict, tmp: pathlib.Path) -> subprocess.CompletedProcess:
        env = dict(os.environ, **env_extra)
        return subprocess.run(["bash", str(RUNNER)], capture_output=True, text=True,
                              env=env, cwd=str(tmp))

    def test_runner_exists_and_is_bash(self):
        self.assertTrue(RUNNER.exists())
        self.assertTrue(RUNNER.read_text(encoding="utf-8").startswith("#!/usr/bin/env bash"))

    def test_runner_parses(self):
        r = subprocess.run(["bash", "-n", str(RUNNER)], capture_output=True, text=True)
        self.assertEqual(0, r.returncode, r.stderr)

    def test_unset_command_is_setup_failure_not_a_result(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            env = {k: v for k, v in os.environ.items() if k != "INCIDENT_PM_EVAL_CMD"}
            r = subprocess.run(["bash", str(RUNNER)], capture_output=True, text=True,
                               env=env, cwd=tmp)
            self.assertEqual(2, r.returncode, "missing command must exit 2, never 0 or 1")
            self.assertIn("setup:", r.stderr)

    def test_empty_response_is_setup_failure(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            stub = self._stub(tmp, "printf ''\n")
            r = self._run({"INCIDENT_PM_EVAL_CMD": f"bash {stub}",
                           "INCIDENT_PM_EVAL_ARM": "without-skill"}, tmp)
            self.assertEqual(2, r.returncode, r.stdout + r.stderr)

    def test_failing_response_is_graded_as_a_failure(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            stub = self._stub(tmp, "printf 'It broke. We fixed it.\\n'\n")
            r = self._run({"INCIDENT_PM_EVAL_CMD": f"bash {stub}",
                           "INCIDENT_PM_EVAL_ARM": "without-skill"}, tmp)
            self.assertEqual(1, r.returncode, r.stdout + r.stderr)
            self.assertIn("scenarios measured:", r.stdout)
            self.assertIn("[FAIL]", r.stdout)

    def test_runner_reaches_every_scenario(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            stub = self._stub(tmp, "printf 'placeholder\\n'\n")
            r = self._run({"INCIDENT_PM_EVAL_CMD": f"bash {stub}",
                           "INCIDENT_PM_EVAL_ARM": "without-skill"}, tmp)
            for p in sorted(EVAL_DIR.glob("scenario_*.json")):
                self.assertIn(p.stem, r.stdout, f"{p.stem} never ran")
            self.assertIn(f"scenarios measured: {len(list(EVAL_DIR.glob('scenario_*.json')))}",
                          r.stdout)

    def test_with_skill_arm_installs_the_skill_and_omits_the_harness(self):
        """The measuring instrument must not become part of the evidence.

        The model response is written to an artifacts file, not to the runner's stdout,
        so the stub reports what it saw through $EVAL_PROBE instead.
        """
        body = ('{ [ -d .claude/skills/incident-postmortem ] && printf "INSTALLED\\n"\n'
                '  [ -d .claude/skills/incident-postmortem/scripts/tests ] '
                '&& printf "TESTS_LEAKED\\n"\n'
                '  [ -f .claude/skills/incident-postmortem/SKILL.md ] '
                '&& printf "SKILL_MD\\n"\n'
                '} >> "$EVAL_PROBE"\n'
                'printf "placeholder\\n"\n')
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            probe = tmp / "probe.txt"
            probe.write_text("", encoding="utf-8")
            stub = self._stub(tmp, body)
            self._run({"INCIDENT_PM_EVAL_CMD": f"bash {stub}",
                       "INCIDENT_PM_EVAL_ARM": "with-skill",
                       "EVAL_PROBE": str(probe)}, tmp)
            seen = probe.read_text(encoding="utf-8")
            self.assertIn("INSTALLED", seen, "with-skill arm must install the skill")
            self.assertIn("SKILL_MD", seen, "installed copy must carry SKILL.md")
            self.assertNotIn("TESTS_LEAKED", seen,
                             "scripts/tests must be stripped from the installed copy")

    def test_without_skill_arm_does_not_install(self):
        """Otherwise both arms measure the same thing and the comparison is empty."""
        body = ('[ -d .claude/skills/incident-postmortem ] && printf "INSTALLED\\n" '
                '>> "$EVAL_PROBE"\n'
                'printf "placeholder\\n"\n')
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            probe = tmp / "probe.txt"
            probe.write_text("", encoding="utf-8")
            stub = self._stub(tmp, body)
            self._run({"INCIDENT_PM_EVAL_CMD": f"bash {stub}",
                       "INCIDENT_PM_EVAL_ARM": "without-skill",
                       "EVAL_PROBE": str(probe)}, tmp)
            self.assertEqual("", probe.read_text(encoding="utf-8").strip(),
                             "without-skill arm must not install the skill")

    def test_grader_cli_exit_codes(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            good = tmp / "good.md"
            good.write_text(GOOD_DRAFT, encoding="utf-8")
            sc = EVAL_DIR / "scenario_full_draft.json"
            self.assertEqual(0, subprocess.run(
                [sys.executable, str(GRADER_PATH), str(sc), str(good)],
                capture_output=True).returncode)
            bad = tmp / "bad.md"
            bad.write_text("nothing useful\n", encoding="utf-8")
            self.assertEqual(1, subprocess.run(
                [sys.executable, str(GRADER_PATH), str(sc), str(bad)],
                capture_output=True).returncode)
            self.assertEqual(2, subprocess.run(
                [sys.executable, str(GRADER_PATH), str(sc)],
                capture_output=True).returncode)


class SkillDocumentsTheEval(unittest.TestCase):
    def test_skill_or_coverage_points_at_the_harness(self):
        cov = (pathlib.Path(__file__).resolve().parent / "COVERAGE.md").read_text(encoding="utf-8")
        self.assertIn("run_live_eval.sh", cov)

    def test_regression_runner_does_not_require_a_model(self):
        """`bash scripts/run_regression.sh` must stay model-free and offline."""
        rr = (SKILL_DIR / "scripts" / "run_regression.sh").read_text(encoding="utf-8")
        self.assertNotIn("run_live_eval", rr)
        self.assertNotIn("INCIDENT_PM_EVAL_CMD", rr)


class DeepDepthIsGradable(unittest.TestCase):
    """The grader normalised a declared `Deep` to `standard`, so any scenario asserting
    expect_depth: deep could never pass. Only the absence of such a scenario hid it."""

    def test_declared_depth_is_returned_verbatim(self):
        for word in ("Quick", "Standard", "Deep"):
            _, depth = grader._declared_mode_depth(f"## Mode & Depth\nDraft + {word}.\n")
            self.assertEqual(word.lower(), depth)

    def test_sev1_scenarios_now_assert_deep(self):
        for name in ("scenario_and_gated_failure", "scenario_secrets_in_evidence"):
            self.assertEqual("deep", scenario(name)["grade"]["expect_depth"],
                             f"{name} is SEV-1, so §3 forces Deep")

    def test_declaring_standard_on_a_deep_scenario_fails(self):
        doc = SecretsScenarioGrading.REDACTED.replace(
            "Draft + Deep. SEV-1 with a credential exposure forces Deep (§3).",
            "Draft + Standard.")
        self.assertIn("selects depth=deep",
                      failed(grader.grade(scenario("scenario_secrets_in_evidence"), doc)))

    def test_deep_still_lints_at_standard_strictness(self):
        doc = SecretsScenarioGrading.REDACTED.replace("## Action Items", "## Notes")
        self.assertIn("lint criticals <= 0 [draft/deep]",
                      failed(grader.grade(scenario("scenario_secrets_in_evidence"), doc)))


class InstalledSkillIsAnAllowList(unittest.TestCase):
    """`cp -R` minus a blocklist left the grader, the runner and a compiled
    __pycache__/grade_postmortem_eval.pyc readable by the model under test."""

    ALLOWED_NAMES = {"SKILL.md", "lint_postmortem.py"}

    def _installed_files(self) -> list[str]:
        body = ('find .claude/skills/incident-postmortem -type f | sort >> "$EVAL_PROBE"\n'
                'printf "placeholder\\n"\n')
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            probe = tmp / "probe.txt"
            probe.write_text("", encoding="utf-8")
            stub = tmp / "stub.sh"
            stub.write_text("#!/usr/bin/env bash\ncat >/dev/null\n" + body, encoding="utf-8")
            stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
            env = dict(os.environ, INCIDENT_PM_EVAL_CMD=f"bash {stub}",
                       INCIDENT_PM_EVAL_ARM="with-skill", EVAL_PROBE=str(probe))
            subprocess.run(["bash", str(RUNNER)], capture_output=True, text=True,
                           env=env, cwd=str(tmp))
            lines = [ln.strip() for ln in probe.read_text(encoding="utf-8").splitlines()
                     if ln.strip()]
        self.assertTrue(lines, "stub never observed an installed skill")
        return lines

    def test_only_allowed_files_are_installed(self):
        for path in self._installed_files():
            name = path.rsplit("/", 1)[-1]
            allowed = name in self.ALLOWED_NAMES or (
                "/references/" in path and name.endswith(".md"))
            self.assertTrue(allowed, f"harness file readable by the model: {path}")

    def test_grader_is_not_installed(self):
        joined = " ".join(self._installed_files())
        for leak in ("grade_postmortem_eval", "run_live_eval", "run_regression",
                     "__pycache__", "/tests/", "scenario_"):
            self.assertNotIn(leak, joined, f"{leak!r} must not be readable by the model")

    def test_skill_itself_is_still_usable(self):
        """An allow-list that omits what the skill needs measures the wrong thing."""
        joined = " ".join(self._installed_files())
        self.assertIn("SKILL.md", joined)
        self.assertIn("lint_postmortem.py", joined,
                      "SKILL.md §8 tells the model to run the linter")
        self.assertIn("references/postmortem-template.md", joined)

    def test_runner_aborts_if_a_harness_file_leaks(self):
        """The guard must be in the runner, not only in this test file."""
        runner = RUNNER.read_text(encoding="utf-8")
        self.assertIn("harness files leaked into the installed skill", runner)
        self.assertIn("exit 2", runner)


class SpinePlacementTests(unittest.TestCase):
    """§9.0 has three placements. The strict case is the one that bites: when the user
    forbids any text beyond the requested section, the reply IS the artifact and there
    is no legal "around" — so the spine is omitted and must not be scored as missing.
    Grading it anyway rewarded answers that disobeyed a direct instruction."""

    OBEDIENT = ("## Root Cause Analysis\n"
                "Technique: fishbone — four parallel conditions, not one chain.\n"
                "- Process: a schema migration held a long lock on orders\n"
                "- Environment: a marketing email drove 4x traffic\n"
                "- Technology: the read replica was already lagging\n"
                "- Technology: the connection pool ceiling was never raised\n"
                "No single condition would have caused the outage alone.\n")

    def test_full_obedience_passes(self):
        self.assertEqual(set(), failed(
            grader.grade(scenario("scenario_strict_single_section"), self.OBEDIENT)),
            "a response that obeys the user exactly must not be penalised")

    def test_scenario_declares_spine_omitted(self):
        g = scenario("scenario_strict_single_section")["grade"]
        self.assertEqual("omitted", g["spine_placement"])
        self.assertTrue(g["forbid_extra_content"])

    def test_adding_a_mode_line_disobeys_and_fails(self):
        doc = "**Mode & Depth**: Draft + Quick.\n\n" + self.OBEDIENT
        self.assertIn("no preamble before the requested section", failed(
            grader.grade(scenario("scenario_strict_single_section"), doc)))

    def test_adding_an_uncovered_risks_section_disobeys_and_fails(self):
        doc = self.OBEDIENT + "\n## Uncovered Risks\n- impact not analyzed\n"
        self.assertIn("no headings beyond the requested section", failed(
            grader.grade(scenario("scenario_strict_single_section"), doc)))

    def test_prose_placement_scenario_still_requires_the_spine(self):
        """The opposite case: room exists, so omitting the spine IS a miss."""
        bare = ("## Timeline (UTC)\n"
                "03:02 [DETECTION] upstream timeout after 30s (api log)\n"
                "03:19 [RECOVERY] upstream recovered (api log)\n")
        names = failed(grader.grade(scenario("scenario_pinned_file_artifact"), bare))
        self.assertIn("declares mode & depth (§9.2)", names)
        self.assertIn("states what was not covered, even without a §9.9 heading", names)

    def test_prose_placement_scenario_passes_with_the_spine_in_prose(self):
        good = ("**Mode & Depth**: Extract + Quick — you pinned timeline.md to entries only.\n\n"
                "## Timeline (UTC)\n"
                "03:02 [DETECTION] upstream timeout after 30s (api log)\n"
                "03:19 [RECOVERY] upstream recovered, backlog draining (api log)\n\n"
                "I did not analyze root cause or impact — the logs only cover the window.\n")
        self.assertEqual(set(), failed(
            grader.grade(scenario("scenario_pinned_file_artifact"), good)))

    def test_skill_documents_all_three_placements(self):
        skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        flat = re.sub(r"\s+", " ", skill)
        self.assertIn("no room at all", flat)
        self.assertIn("nowhere — omit them", flat)
        self.assertIn("it is obedience", flat)


class ReviewScenarioGrading(unittest.TestCase):
    """Review was the one mode with no live scenario."""

    GOOD = """**Mode & Depth**: Review + Standard.

## Findings
1. Timeline entries carry no source — every entry needs one (§5.1).
2. The root cause names an individual; reframe to the missing system control.
3. Action items have no owner and are not verifiable.

## Action Items
- Add a source to each timeline entry (owner: @alice, deadline: 2024-08-12)
- Reframe the root cause around the missing pool-size gate (owner: @bob, deadline: 2024-08-12)
- Replace "improve monitoring" with a named alert and threshold (owner: @alice, deadline: 2024-08-15)

## Uncovered Risks
- I did not re-derive the root cause; the finding is about framing, not correctness.
"""

    def test_good_review_passes(self):
        self.assertEqual(set(), failed(
            grader.grade(scenario("scenario_review_existing"), self.GOOD)))

    def test_review_items_without_owners_fail(self):
        doc = self.GOOD.replace(" (owner: @alice, deadline: 2024-08-12)", "")
        self.assertIn("lint criticals <= 0 [review/standard]", failed(
            grader.grade(scenario("scenario_review_existing"), doc)))

    def test_carrying_over_blame_fails(self):
        doc = self.GOOD.replace(
            "The root cause names an individual; reframe to the missing system control.",
            "An engineer forgot to raise the thread pool, as the draft says.")
        self.assertIn("no blame carried over from the draft instead of reframed", failed(
            grader.grade(scenario("scenario_review_existing"), doc)))

    def test_review_mode_is_exercised_by_a_scenario(self):
        modes = {json.loads(p.read_text(encoding="utf-8"))["grade"]["expect_mode"]
                 for p in EVAL_DIR.glob("scenario_*.json")}
        for mode in ("draft", "review", "extract", "planning"):
            self.assertIn(mode, modes, f"no live scenario exercises mode={mode}")


class ChineseScenarioGrading(unittest.TestCase):
    """The grader has to follow the user's language too, or a correct Chinese
    post-mortem scores as missing most of its sections."""

    ZH = """**模式与深度**：Draft + Standard。SEV-2 且影响客户。

## 摘要
2024-09-03，payment 服务因 Redis 连接被拒导致错误率升至 9.4%（INC-2024-0311）。

## 时间线（UTC）
11:20 [DETECTION] Redis 连接被拒（payment 日志）
11:22 [DETECTION] 错误率 9.4% 告警（Grafana：payment-slo）
11:48 [MITIGATION] 回滚至 3ab19cc（ArgoCD）
11:51 [RECOVERY] 告警恢复（Grafana：payment-slo）

## 根因分析
方法：5-Why。发布未校验 Redis 连接配置。

## 做得好的地方
- 告警在 2 分钟内触发。

## 行动项
| ID | 类别 | 描述 | 负责人 | 截止日期 | 工单 |
|----|------|------|--------|----------|------|
| AI-1 | 预防 | 增加连接配置校验 | @platform | 2024-09-20 | JIRA-7 |
| AI-2 | 检测 | 增加连接失败告警 | @sre | 2024-09-15 | JIRA-8 |
| AI-3 | 缓解 | 错误率超阈值自动回滚 | @platform | 2024-09-30 | JIRA-9 |

## 未覆盖风险
- 未量化收入影响，缺少交易金额数据。
"""

    def test_chinese_response_passes(self):
        self.assertEqual(set(), failed(
            grader.grade(scenario("scenario_chinese_incident"), self.ZH)))

    def test_english_response_to_a_chinese_prompt_fails(self):
        doc = ("**Mode & Depth**: Draft + Standard.\n\n## Summary\nRedis refused "
               "connections for INC-2024-0311.\n\n## Timeline (UTC)\n"
               "11:20 [DETECTION] redis connection refused (payment log)\n\n"
               "## Root Cause\nNo config validation.\n\n## Action Items\n"
               "- fix it (owner: @sre, deadline: 2024-09-20)\n\n"
               "## Uncovered Risks\n- revenue not quantified\n")
        self.assertIn("no answered in English although the user wrote in Chinese",
                      failed(grader.grade(scenario("scenario_chinese_incident"), doc)))

    def test_grader_sections_match_chinese_headings(self):
        for key in ("9.1", "9.2", "9.3", "9.4", "9.6", "9.7", "9.9"):
            self.assertTrue(grader.SECTIONS[key].search(self.ZH),
                            f"grader section {key} does not match its Chinese heading")

    def test_chinese_definitive_cause_is_detected(self):
        self.assertTrue(grader.DEFINITIVE_CAUSE_RE.search("根因是连接池耗尽。"))
        self.assertFalse(grader.DEFINITIVE_CAUSE_RE.search("根因是可能的连接池耗尽。"))

    def test_chinese_uncovered_prose_is_detected(self):
        self.assertTrue(grader.UNCOVERED_PROSE_RE.search("未量化收入影响。"))


class CheckLevelAggregation(unittest.TestCase):
    """The runner reported only scenario counts while its own closing text asked for a
    check-level comparison — two arms failing the same 2 scenarios could differ by 12
    checks and the summary would look identical."""

    def _run(self, arm: str, out: pathlib.Path, body: str) -> subprocess.CompletedProcess:
        import tempfile
        tmp = pathlib.Path(tempfile.mkdtemp())
        stub = tmp / "stub.sh"
        stub.write_text("#!/usr/bin/env bash\ncat >/dev/null\n" + body, encoding="utf-8")
        stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
        env = dict(os.environ, INCIDENT_PM_EVAL_CMD=f"bash {stub}",
                   INCIDENT_PM_EVAL_ARM=arm, INCIDENT_PM_EVAL_OUT=str(out))
        return subprocess.run(["bash", str(RUNNER)], capture_output=True, text=True,
                              env=env, cwd=str(tmp))

    def test_summary_reports_checks_not_only_scenarios(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            out = pathlib.Path(d) / "res"
            r = self._run("without-skill", out, 'printf "It broke.\\n"\n')
            self.assertIn("checks passed:", r.stdout)
            self.assertIn("checks failed:", r.stdout)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            for key in ("arm", "scenarios_measured", "scenarios_failed",
                        "checks_total", "checks_passed", "checks_failed", "per_scenario"):
                self.assertIn(key, summary)
            self.assertGreater(summary["checks_total"], summary["scenarios_measured"],
                               "check counts must be finer-grained than scenario counts")

    def test_per_scenario_failed_checks_are_named(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            out = pathlib.Path(d) / "res"
            self._run("without-skill", out, 'printf "It broke.\\n"\n')
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            rows = summary["per_scenario"]
            self.assertEqual(len(list(EVAL_DIR.glob("scenario_*.json"))), len(rows))
            self.assertTrue(any(r["failed_checks"] for r in rows))

    def test_diff_mode_reports_a_net_check_delta(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)
            base, cand = d / "base", d / "cand"
            self._run("without-skill", base, 'printf "It broke.\\n"\n')
            self._run("without-skill", cand,
                      'printf "**Mode & Depth**: Draft + Standard.\\n"\n')
            r = subprocess.run(
                [sys.executable, str(SKILL_DIR / "scripts" / "summarize_eval.py"),
                 "--diff", str(base / "summary.json"), str(cand / "summary.json")],
                capture_output=True, text=True)
            self.assertEqual(0, r.returncode, r.stderr)
            self.assertIn("net check delta:", r.stdout)
            self.assertRegex(r.stdout, r"(better|worse|same)")

    def test_summarizer_exits_2_on_an_empty_dir(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            r = subprocess.run(
                [sys.executable, str(SKILL_DIR / "scripts" / "summarize_eval.py"), d],
                capture_output=True, text=True)
            self.assertEqual(2, r.returncode, "nothing measured must not look like a pass")


class RecordedRuns(unittest.TestCase):
    """Committed evidence from real runs. Empty until a human runs the harness from an
    authenticated terminal: a nested `claude -p` prints "Not logged in" and returns
    nothing, which the runner reports as exit 2 — a setup failure, not a result."""

    RESULTS = pathlib.Path(__file__).resolve().parent / "eval" / "results"

    def test_results_dir_documents_how_to_record(self):
        readme = self.RESULTS / "README.md"
        self.assertTrue(readme.exists())
        text = readme.read_text(encoding="utf-8")
        self.assertIn("INCIDENT_PM_EVAL_OUT", text)
        self.assertIn("--diff", text)
        self.assertIn("Exit 2 means nothing was measured", text)

    def test_any_committed_summary_is_well_formed(self):
        for summary in self.RESULTS.rglob("summary.json"):
            data = json.loads(summary.read_text(encoding="utf-8"))
            for key in ("arm", "scenarios_measured", "checks_total", "checks_passed",
                        "checks_failed", "per_scenario"):
                self.assertIn(key, data, f"{summary} missing {key}")
            self.assertEqual(data["checks_total"],
                             data["checks_passed"] + data["checks_failed"], str(summary))

    def test_with_skill_arm_beats_baseline_when_both_recorded(self):
        base = self.RESULTS / "without-skill" / "summary.json"
        cand = self.RESULTS / "with-skill" / "summary.json"
        if not (base.exists() and cand.exists()):
            self.skipTest("no recorded runs yet — see eval/results/README.md")
        a = json.loads(base.read_text(encoding="utf-8"))
        b = json.loads(cand.read_text(encoding="utf-8"))
        self.assertLessEqual(b["checks_failed"], a["checks_failed"],
                             "the with-skill arm must not fail more checks than baseline")


if __name__ == "__main__":
    unittest.main()
