"""Prove the forward-eval grader discriminates before trusting any live run.

A grader that passes everything makes a live evaluation meaningless — the result
would say more about the grader than about the skill. Each scenario ships one
grounded exemplar that must PASS and several defective ones that must FAIL, each
naming the specific check it is supposed to trip.

This layer contains no model. It answers "can the grader tell the difference?",
not "does the skill work" — `run_live_eval.sh` answers the second question and is
gated behind UPDATE_DOC_EVAL_CMD.
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[2]
GRADER = SKILL_DIR / "scripts" / "grade_doc_update.py"
EVAL_DIR = Path(__file__).resolve().parent / "eval"


def scenarios():
    return sorted(EVAL_DIR.glob("scenario_*.json"))


def materialize(root, scenario, docs):
    files = dict(scenario["repo"])
    files.update(scenario.get("untracked", {}))
    files.update(docs)
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def run_grader(scenario_path, repo, response_text):
    response_file = repo.parent / "response.md"
    response_file.write_text(response_text, encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(GRADER), str(scenario_path), str(repo), str(response_file)],
        capture_output=True,
        text=True,
    )


def failing_checks(stdout):
    return {
        line.split()[1]
        for line in stdout.splitlines()
        if line.startswith("FAIL ")
    }


class ForwardEvalGraderTests(unittest.TestCase):
    maxDiff = None

    def test_scenarios_exist(self):
        self.assertGreaterEqual(len(scenarios()), 1, "no eval scenarios shipped")

    def test_grader_separates_grounded_from_defective(self):
        for path in scenarios():
            scenario = json.loads(path.read_text(encoding="utf-8"))
            exemplars = scenario["exemplars"]

            # A corpus of only-passing or only-failing exemplars cannot show
            # discrimination, whatever the individual results say.
            expectations = {e["expect"] for e in exemplars}
            self.assertEqual(
                expectations, {"pass", "fail"},
                f"{path.name}: corpus must contain both grounded and defective exemplars",
            )

            for exemplar in exemplars:
                with self.subTest(scenario=path.stem, exemplar=exemplar["label"]):
                    with tempfile.TemporaryDirectory(
                        dir=os.environ.get("TMPDIR") or None
                    ) as tmp:
                        repo = Path(tmp) / "repo"
                        repo.mkdir()
                        materialize(repo, scenario, exemplar["docs"])
                        proc = run_grader(path, repo, exemplar["response"])

                    self.assertNotEqual(
                        proc.returncode, 2,
                        f"grader setup error, not a result:\n{proc.stderr}",
                    )
                    want = 0 if exemplar["expect"] == "pass" else 1
                    self.assertEqual(
                        proc.returncode, want,
                        f"{exemplar['label']} expected {exemplar['expect']}:\n{proc.stdout}",
                    )

                    expected_failures = set(exemplar.get("expect_failing_checks", []))
                    if expected_failures:
                        actual = failing_checks(proc.stdout)
                        self.assertTrue(
                            expected_failures <= actual,
                            f"{exemplar['label']}: expected {expected_failures} to fail, "
                            f"got {actual}\n{proc.stdout}",
                        )

    def test_every_check_is_exercised_by_some_exemplar(self):
        """A check no exemplar can trip is untested surface.

        Without this, a grader check could be silently broken — always passing —
        and the suite would stay green.
        """
        for path in scenarios():
            scenario = json.loads(path.read_text(encoding="utf-8"))
            declared = set()
            for exemplar in scenario["exemplars"]:
                declared |= set(exemplar.get("expect_failing_checks", []))
            self.assertGreaterEqual(
                len(declared), 5,
                f"{path.name}: only {sorted(declared)} are exercised; "
                "each grader check needs a defective exemplar",
            )

    def test_command_existence_check_is_the_load_bearing_one(self):
        """The invented-`make`-target exemplar must fail on `commands_exist`
        alone — if it also trips other checks, it is not isolating that check."""
        path = EVAL_DIR / "scenario_worker.json"
        scenario = json.loads(path.read_text(encoding="utf-8"))
        exemplar = next(
            e for e in scenario["exemplars"] if e["label"] == "invents_a_make_target"
        )
        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR") or None) as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            materialize(repo, scenario, exemplar["docs"])
            proc = run_grader(path, repo, exemplar["response"])
        self.assertEqual(failing_checks(proc.stdout), {"commands_exist"})

    def test_wrapper_targets_are_checked_for_every_resolver_wrapper(self):
        """Drift guard for `commands_exist` only.

        Scoped to what it actually asserts: every wrapper the resolver can emit
        must be checkable against the repository's real targets. Command
        *correctness* is a separate question, covered below.
        """
        grader = (SKILL_DIR / "scripts" / "grade_doc_update.py").read_text(encoding="utf-8")
        resolver = (SKILL_DIR / "scripts" / "discover_doc_scope.sh").read_text(encoding="utf-8")
        for wrapper in ("make", "npm", "pnpm", "yarn", "bun", "just", "task"):
            with self.subTest(wrapper=wrapper):
                self.assertIn(
                    wrapper, resolver, f"{wrapper} is expected in the resolver ladder"
                )
                self.assertIn(
                    wrapper, grader,
                    f"resolver can emit {wrapper} but the grader cannot check it",
                )

    def test_declared_coverage_matches_the_implementation(self):
        """The grader's CHECKED table is a promise; hold it to it.

        Twice now a docstring claimed broader coverage than the code had, and
        both times the gap only surfaced through an external failure injection.
        Every declared family must actually fail a crafted bad command, and
        nothing may be declared unchecked while silently being checked.
        """
        spec = importlib.util.spec_from_file_location("uv_grader", GRADER)
        grader = importlib.util.module_from_spec(spec)
        sys.modules["uv_grader"] = grader
        spec.loader.exec_module(grader)

        self.assertFalse(
            set(grader.CHECKED) & set(grader.UNCHECKED),
            "a family cannot be both checked and unchecked",
        )

        # One crafted violation per declared family; each must trip
        # `commands_correct`, proving the declaration is not aspirational.
        violations = {
            "package-manager-consistency": "npm run build",
            "go-package-path": "go run ./cmd/nope",
            "cargo-bin-target": "cargo run --bin nope",
            "script-path": "./scripts/nope.sh",
            "pytest-path": "pytest tests/nope",
        }
        self.assertEqual(
            set(violations), set(grader.CHECKED),
            "every declared family needs a violation case here",
        )

        scenario = {
            "grade": {
                "doc_paths": ["README.md"],
                "expect_mode": "full",
                "required_blocks": [],
            }
        }
        for family, bad in violations.items():
            with self.subTest(family=family):
                with tempfile.TemporaryDirectory(
                    dir=os.environ.get("TMPDIR") or None
                ) as tmp:
                    repo = Path(tmp) / "repo"
                    repo.mkdir()
                    (repo / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n")
                    (repo / "Cargo.toml").write_text('[package]\nname = "x"\n')
                    (repo / "README.md").write_text(f"```bash\n{bad}\n```\n")
                    results = dict(
                        (name, ok) for name, ok, _ in grader.grade(scenario, repo, "")
                    )
                self.assertFalse(
                    results["commands_correct"],
                    f"{family} is declared checked but `{bad}` graded clean",
                )

    def test_target_existence_and_command_correctness_are_separate_checks(self):
        """The two questions fail independently and must be attributable.

        `npm run build` in a pnpm repo has a real target and a wrong command;
        `make deploy` has a wrong target. Collapsing them into one check makes
        a failure impossible to act on.
        """
        path = EVAL_DIR / "scenario_node_workspace.json"
        scenario = json.loads(path.read_text(encoding="utf-8"))
        exemplar = next(
            e for e in scenario["exemplars"] if e["label"] == "uses_the_wrong_package_manager"
        )
        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR") or None) as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            materialize(repo, scenario, exemplar["docs"])
            proc = run_grader(path, repo, exemplar["response"])
        self.assertEqual(failing_checks(proc.stdout), {"commands_correct"})
        self.assertIn("lockfile says pnpm", proc.stdout)

    def test_scenarios_cover_more_than_one_wrapper_family(self):
        """One Go/Makefile scenario cannot exercise the Node wrappers."""
        families = set()
        for path in scenarios():
            body = path.read_text(encoding="utf-8")
            for wrapper in ("make ", "pnpm ", "npm run", "just ", "task ", "yarn "):
                if wrapper in body:
                    families.add(wrapper.strip())
        self.assertGreaterEqual(
            len(families), 3, f"eval corpus only exercises {sorted(families)}"
        )

    def test_live_harness_excludes_its_own_installation(self):
        """The installed skill must not enter the scenario's own discovery.

        The harness copies the skill into `<repo>/.claude/skills/` after the base
        commit. Without an exclude, its files land in the untracked set and the
        language counts, so scope, NEW_SOURCE, DOMINANT and POLYGLOT would all
        describe the measuring instrument.
        """
        harness = (SKILL_DIR / "scripts" / "run_live_eval.sh").read_text(encoding="utf-8")
        self.assertIn(".git/info/exclude", harness)
        self.assertRegex(harness, r"echo '\.claude/' >>")
        exclude_at = harness.index(".git/info/exclude")
        install_at = harness.index('cp -R "${SKILL_DIR}"')
        self.assertLess(
            exclude_at, install_at,
            "the exclude must be written before the skill is installed",
        )
        self.assertIn("Contamination probe", harness)

    def test_grader_usage_error_is_distinct_from_a_failing_grade(self):
        proc = subprocess.run(
            [sys.executable, str(GRADER)], capture_output=True, text=True
        )
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
