"""Offline checks for scripts/run_live_eval.sh.

The live A/B arms need credentials and cannot run here. Everything *around* the
model can, and this file covers it, because the failure modes that make an A/B
worthless are all in the harness rather than in the model:

* a setup failure reported as a score of 0 (indistinguishable from a model that
  answered badly);
* a "with-skill" arm that silently never loaded the skill, which is a second
  control arm wearing a treatment label;
* a grader that cannot fail, so every response looks compliant;
* a prompt built from a fixture that states the expected answer;
* a truncated run that reads as a finished one.

Every assertion below runs the SHIPPED script or the python it actually embeds
— never a re-implementation of its logic in this file.
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[2]
SCRIPT = SKILL_DIR / "scripts" / "run_live_eval.sh"
SKILL_MD = SKILL_DIR / "SKILL.md"
GOLDEN_DIR = SKILL_DIR / "scripts" / "tests" / "golden"
SETUP_RC = 3
MARKER = "LIVE-EVAL-COMPLETE"

GRADER = SKILL_DIR / "scripts" / "live_eval_grader.py"
COPY_LINE = re.compile(r'^cp "\$\{SCRIPT_DIR\}/live_eval_grader\.py" "\$\{HARNESS\}"$',
                       re.MULTILINE)


def run(argv, env=None, cwd=None, stdin=None):
    return subprocess.run(argv, capture_output=True, text=True, env=env,
                          cwd=cwd, input=stdin, timeout=600)


def clean_env():
    """A caller may already have the eval command exported; the setup-failure
    tests must not silently turn into live runs."""
    env = dict(os.environ)
    for key in ("GO_CI_WORKFLOW_EVAL_CMD", "GO_CI_WORKFLOW_EVAL_ARM",
                "GO_CI_WORKFLOW_EVAL_OUT"):
        env.pop(key, None)
    return env


def bash_code(text: str) -> str:
    """The script with every comment line removed — i.e. the bash that actually
    executes. The grader is a sibling .py file, so nothing has to be carved out
    of a heredoc first."""
    assert COPY_LINE.search(text), "the grader is no longer installed from its own file"
    return "\n".join(l for l in text.splitlines()
                     if not l.lstrip().startswith("#"))


def embedded_harness() -> str:
    """The grader the script installs at run time.

    Read from the shipped file rather than copied into this test: a second copy
    would be a second thing to keep in sync, and the copy would pass while the
    shipped one rotted. It used to be a 960-line heredoc inside the bash script,
    which the tests had to carve out before they could run it — not lintable,
    not importable, and a second parser to keep correct."""
    assert GRADER.exists(), f"grader missing: {GRADER}"
    return GRADER.read_text(encoding="utf-8")


class ShippedScriptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SCRIPT.read_text(encoding="utf-8")

    def test_script_exists_and_is_executable(self):
        self.assertTrue(SCRIPT.is_file(), f"{SCRIPT} is missing")
        self.assertTrue(os.access(SCRIPT, os.X_OK), f"{SCRIPT} is not executable")

    def test_bash_syntax_is_valid(self):
        proc = run(["bash", "-n", str(SCRIPT)])
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_no_gnu_only_tooling(self):
        """macOS ships BSD userland. A harness that only runs on a GNU box is a
        harness nobody on this team runs.

        Scanned over EXECUTABLE bash only. Scanning the whole file flagged the
        script's own comment promising not to use `xargs -d` — a guard that
        fires on its own documentation is a guard nobody keeps."""
        banned = {
            r"(?<![\w/-])timeout\s+\d": "GNU coreutils `timeout` is absent on stock macOS",
            r"xargs\s+-d": "`xargs -d` is GNU-only",
            r"sed\s+-i\s+-e": "`sed -i` without a backup suffix fails on BSD sed",
            r"sed\s+-i\s+['\"]?s": "`sed -i` without a backup suffix fails on BSD sed",
            r"grep\s+-P": "`grep -P` is unavailable in BSD grep",
            r"readlink\s+-f": "`readlink -f` is GNU-only",
            r"date\s+-d\s": "`date -d` is GNU-only",
        }
        code = bash_code(self.text)
        self.assertIn("mktemp -d", code, "the executable-bash view lost the script")
        for pattern, why in banned.items():
            with self.subTest(pattern=pattern):
                hit = re.search(pattern, code)
                self.assertIsNone(hit, f"{why}: found {hit.group(0) if hit else ''!r}")

    def test_never_uses_bare_and_says_why(self):
        """`--bare` skips the skill directory walk, so it disables the very
        thing under test, and it skips the credential path as well."""
        self.assertIsNone(
            re.search(r"^[^#]*--bare", self.text, re.MULTILINE),
            "--bare must never appear in an executable line")
        self.assertIn("--bare", self.text,
                      "the prohibition on --bare must be documented")
        window = self.text[self.text.index("NEVER use `--bare`"):][:900]
        for token in ("skill directory walk", "credential", "control arm"):
            self.assertIn(token, window,
                          f"the --bare note must explain {token!r}")

    def test_documents_the_distinct_setup_exit_code(self):
        self.assertIn("SETUP_RC=3", self.text)
        self.assertRegex(self.text, r"#\s+3\s+SETUP failure")
        self.assertIn("not a score of 0", self.text)

    def test_documents_measured_isolation_facts(self):
        for token in ("does NOT inherit the parent session's credentials",
                      "Not logged in",
                      "user-level plugin hooks",
                      "SessionEnd",
                      "working directory",
                      "CLAUDE.md"):
            with self.subTest(token=token):
                self.assertIn(token, self.text)

    def test_scenarios_come_from_the_golden_fixtures(self):
        """Requirement, not decoration: a second hand-written scenario list is
        a second thing to keep in sync, and it drifts."""
        self.assertIn("scripts/tests/golden", self.text)
        self.assertIn('h derive --golden "${GOLDEN_DIR}"', self.text)


class RecordingCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.recordings = sorted(GOLDEN_DIR.glob("live_eval_*.md"))
        cls.fixture_ids = {p.stem for p in GOLDEN_DIR.glob("*.json")}

    def test_corpus_is_not_empty(self):
        self.assertGreaterEqual(len(self.recordings), 3, self.recordings)

    def test_every_recording_declares_fixture_arm_and_expectation(self):
        harness = embedded_harness()
        with tempfile.TemporaryDirectory() as tmp:
            hp = Path(tmp) / "harness.py"
            hp.write_text(harness, encoding="utf-8")
            for rec in self.recordings:
                with self.subTest(recording=rec.name):
                    proc = run(["python3", str(hp), "--skill-md", str(SKILL_MD),
                                "meta", "--response", str(rec)])
                    self.assertEqual(proc.returncode, 0, proc.stderr)
                    meta = json.loads(proc.stdout)
                    self.assertIn(meta["fixture"], self.fixture_ids)
                    self.assertIn(meta["arm"],
                                  {"replay-good", "replay-bad", "replay-untreated"})
                    self.assertIn(meta["expect"], {"pass", "fail", "setup-abort"})

    def test_corpus_covers_pass_fail_and_untreated(self):
        """A grader that cannot fail is worthless, and a treatment assertion
        that is never exercised is not a guard."""
        harness = embedded_harness()
        arms = set()
        with tempfile.TemporaryDirectory() as tmp:
            hp = Path(tmp) / "harness.py"
            hp.write_text(harness, encoding="utf-8")
            for rec in self.recordings:
                proc = run(["python3", str(hp), "--skill-md", str(SKILL_MD),
                            "meta", "--response", str(rec), "--key", "arm"])
                arms.add(proc.stdout.strip())
        self.assertEqual(arms, {"replay-good", "replay-bad", "replay-untreated"})


class DryRunTests(unittest.TestCase):
    """One dry run, shared. It is the only layer that can prove — here, with no
    credentials — that the grader discriminates."""

    @classmethod
    def setUpClass(cls):
        cls.proc = run(["bash", str(SCRIPT), "--dry-run"],
                       env=clean_env(), cwd=str(SKILL_DIR))
        cls.out = cls.proc.stdout + cls.proc.stderr

    def test_dry_run_succeeds(self):
        self.assertEqual(self.proc.returncode, 0,
                         f"--dry-run failed:\n{self.out}")

    def test_prints_a_terminal_completion_marker(self):
        """A truncated run must never read as a finished one."""
        lines = [l for l in self.out.strip().splitlines() if l.strip()]
        self.assertTrue(lines[-1].startswith(MARKER),
                        f"last line was {lines[-1]!r}")
        self.assertRegex(lines[-1], r"arms=\d+")
        self.assertRegex(lines[-1], r"scenarios=\d+")
        self.assertIn("mode=dry-run", lines[-1])
        self.assertIn("result=ok", lines[-1])

    def test_derives_every_golden_fixture(self):
        count = len(list(GOLDEN_DIR.glob("*.json")))
        self.assertIn(f"derived {count} scenarios", self.out)
        self.assertIn(f"scenarios={count}", self.out)
        for fixture in sorted(GOLDEN_DIR.glob("*.json")):
            with self.subTest(fixture=fixture.stem):
                self.assertIn(fixture.stem, self.out)

    def test_materializes_repositories_the_discovery_probe_can_read(self):
        self.assertIn("probe-complete", self.out)

    def test_reports_every_axis_separately(self):
        """One blended number hides which axis failed."""
        for axis in ("shape", "parity", "contract", "integrity"):
            with self.subTest(axis=axis):
                self.assertRegex(
                    self.out,
                    re.compile(r"^\s+%s\s+\d\.\d\d\s" % axis, re.MULTILINE),
                    f"no per-axis score line for {axis}")

    def test_grader_discriminates_on_the_planted_axes_only(self):
        """The two recordings differ only in the planted defect. If a control
        axis moves, the grader is responding to length or tone."""
        table = {}
        for m in re.finditer(
                r"^\s+(shape|parity|contract|integrity)\s+"
                r"(-?\d\.\d\d)\s+(-?\d\.\d\d)\s+(-?\d\.\d\d)\s+(.+)$",
                self.out, re.MULTILINE):
            table[m.group(1)] = (float(m.group(2)), float(m.group(3)),
                                 m.group(5).strip())
        self.assertEqual(set(table), {"shape", "parity", "contract", "integrity"},
                         f"discrimination table not found in:\n{self.out}")

        for axis in ("parity", "integrity"):
            good, bad, verdict = table[axis]
            self.assertGreaterEqual(
                good - bad, 0.5,
                f"{axis}: good {good} vs bad {bad} — the grader does not "
                f"discriminate on the axis the defect was planted in")
            self.assertEqual(verdict, "discriminates")
        for axis in ("shape", "contract"):
            good, bad, verdict = table[axis]
            self.assertEqual(good, bad,
                             f"{axis} is a control axis but moved "
                             f"({good} vs {bad})")
            self.assertEqual(verdict, "control (equal)")

    def test_reference_response_passes_and_defective_twin_fails(self):
        self.assertIn("verdict    PASS", self.out)
        self.assertIn("verdict    FAIL", self.out)

    def test_treatment_assertion_actually_fires(self):
        """A guard needs a test that fires it. The untreated recording must
        abort the with-skill arm as a SETUP failure, not score low."""
        self.assertRegex(
            self.out,
            r"treatment\s+correctly refused this arm \(exit %d" % SETUP_RC,
            self.out)


class SetupFailureTests(unittest.TestCase):
    def test_missing_eval_command_exits_with_the_setup_code(self):
        proc = run(["bash", str(SCRIPT)], env=clean_env(), cwd=str(SKILL_DIR))
        self.assertEqual(proc.returncode, SETUP_RC,
                         f"expected {SETUP_RC}, got {proc.returncode}")

    def test_missing_eval_command_grades_nothing(self):
        """A setup failure must never be reported as a score. No marker, no
        axis lines, no verdict."""
        proc = run(["bash", str(SCRIPT)], env=clean_env(), cwd=str(SKILL_DIR))
        out = proc.stdout + proc.stderr
        self.assertNotIn(MARKER, out)
        self.assertNotIn("verdict", out)
        self.assertNotRegex(
            out, re.compile(r"^\s+shape\s+\d\.\d\d", re.MULTILINE),
            "a setup abort must not print an axis score")
        self.assertIn("nothing was graded", out.lower())
        self.assertIn("not a score of 0", out.lower())

    def test_unknown_argument_is_a_setup_failure(self):
        proc = run(["bash", str(SCRIPT), "--nope"], env=clean_env(),
                   cwd=str(SKILL_DIR))
        self.assertEqual(proc.returncode, SETUP_RC)
        self.assertNotIn(MARKER, proc.stdout + proc.stderr)

    def test_invalid_arm_is_a_setup_failure(self):
        env = clean_env()
        env["GO_CI_WORKFLOW_EVAL_CMD"] = "true"
        env["GO_CI_WORKFLOW_EVAL_ARM"] = "with-skil"  # typo, not a third arm
        proc = run(["bash", str(SCRIPT)], env=env, cwd=str(SKILL_DIR))
        self.assertEqual(proc.returncode, SETUP_RC)
        self.assertNotIn(MARKER, proc.stdout + proc.stderr)


class EmbeddedTripwireTests(unittest.TestCase):
    """The harness refuses to run rather than measure something meaningless.
    Each tripwire is exercised by breaking the input it guards."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="gociw-live-eval-")
        cls.harness = Path(cls.tmp) / "harness.py"
        cls.harness.write_text(embedded_harness(), encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def derive(self, skill_md, golden_dir):
        out = Path(self.tmp) / "out"
        shutil.rmtree(out, ignore_errors=True)
        return run(["python3", str(self.harness), "--skill-md", str(skill_md),
                    "derive", "--golden", str(golden_dir), "--out", str(out)])

    def test_derivation_succeeds_on_the_shipped_inputs(self):
        proc = self.derive(SKILL_MD, GOLDEN_DIR)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_a_fixture_that_leaks_the_answer_is_refused(self):
        """Fixture descriptions read '<situation> — skill must <answer>'. Only
        the situation half becomes the prompt. If a future edit moves a Gate
        name into the situation half, the prompt would hand the model the
        closed vocabulary the treatment assertion looks for, and the A/B would
        measure the prompt instead of the skill."""
        golden = Path(self.tmp) / "golden-leak"
        shutil.rmtree(golden, ignore_errors=True)
        golden.mkdir(parents=True)
        for src in GOLDEN_DIR.glob("*.json"):
            shutil.copy(src, golden / src.name)
        victim = golden / "001_single_module_service.json"
        data = json.loads(victim.read_text(encoding="utf-8"))
        data["description"] = (
            "Standard service that needs the Local Parity Gate applied "
            "— skill should produce a full-parity workflow")
        victim.write_text(json.dumps(data), encoding="utf-8")

        proc = self.derive(SKILL_MD, golden)
        self.assertEqual(proc.returncode, SETUP_RC, proc.stdout + proc.stderr)
        self.assertIn("leaks behavioural vocabulary", proc.stderr)

    def test_an_unmappable_expected_output_field_is_refused(self):
        """An `expected_output_fields` entry with no canonical mapping would be
        silently dropped — a required check that quietly stops being required."""
        golden = Path(self.tmp) / "golden-field"
        shutil.rmtree(golden, ignore_errors=True)
        golden.mkdir(parents=True)
        for src in GOLDEN_DIR.glob("*.json"):
            shutil.copy(src, golden / src.name)
        victim = golden / "001_single_module_service.json"
        data = json.loads(victim.read_text(encoding="utf-8"))
        data["expected_output_fields"].append("cost estimate")
        victim.write_text(json.dumps(data), encoding="utf-8")

        proc = self.derive(SKILL_MD, golden)
        self.assertEqual(proc.returncode, SETUP_RC, proc.stdout + proc.stderr)
        self.assertIn("no canonical", proc.stderr)

    def test_a_changed_skill_vocabulary_is_refused(self):
        """Every closed set is parsed out of SKILL.md at run time. If the
        Repository Shape Gate stops listing six shapes, grading against the old
        six would be grading a contract the skill no longer has."""
        mutated = Path(self.tmp) / "SKILL.md"
        text = SKILL_MD.read_text(encoding="utf-8")
        self.assertIn("- Docker-heavy repository\n", text)
        mutated.write_text(text.replace("- Docker-heavy repository\n", "", 1),
                           encoding="utf-8")

        proc = self.derive(mutated, GOLDEN_DIR)
        self.assertEqual(proc.returncode, SETUP_RC, proc.stdout + proc.stderr)
        self.assertIn("Repository Shape Gate", proc.stderr)
        self.assertIn("expected 6 shape bullets", proc.stderr)

    def test_a_changed_output_contract_is_refused(self):
        mutated = Path(self.tmp) / "SKILL-contract.md"
        text = SKILL_MD.read_text(encoding="utf-8")
        self.assertIn("- tool versions used\n", text)
        mutated.write_text(text.replace("- tool versions used\n", "", 1),
                           encoding="utf-8")

        proc = self.derive(mutated, GOLDEN_DIR)
        self.assertEqual(proc.returncode, SETUP_RC, proc.stdout + proc.stderr)
        self.assertIn("Output Contract", proc.stderr)


if __name__ == "__main__":
    unittest.main()
