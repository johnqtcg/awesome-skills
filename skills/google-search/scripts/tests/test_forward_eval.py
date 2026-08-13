"""Tests for the forward behavioural eval harness.

The harness itself needs an authenticated CLI to *run*, but its grader must be trustworthy
before any run is worth doing — a grader that always passes turns a live eval into an
expensive way of printing "green". These tests grade the grader offline.
"""

import importlib.util
import json
import pathlib
import sys

import pytest


def _write_arm(tmp_path, fid, arm, text, skill_read=True):
    """Write a recorded arm plus the trace sidecar `--grade` requires for a with-skill arm."""
    (tmp_path / f"{fid}.{arm}.md").write_text(text, encoding="utf-8")
    (tmp_path / f"{fid}.{arm}.meta.json").write_text(
        json.dumps({"arm": arm, "tools_used": ["Read", "WebSearch"],
                    "skill_files_opened": ["SKILL.md"] if skill_read else [],
                    "skill_was_read": skill_read}),
        encoding="utf-8",
    )


def _load(name):
    path = pathlib.Path(__file__).resolve().parents[1] / name
    spec = importlib.util.spec_from_file_location(name.replace(".py", ""), path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


E = _load("eval_forward.py")

EVAL_DIR = pathlib.Path(__file__).resolve().parents[1] / "tests" / "eval"


class TestGraderDiscriminates:
    def test_self_test_passes(self):
        """Every criterion passes its GOOD answer and fails its BAD answer."""
        assert E.self_test() == 0

    @pytest.mark.parametrize("fid", sorted(E.FIXTURE_CRITERIA))
    def test_each_fixture_has_a_bad_answer_that_fails_something(self, fid):
        results = [E.CRITERIA[c](E.BAD[fid])[0] for c in E.FIXTURE_CRITERIA[fid]]
        assert not all(results), f"{fid}: the BAD answer passes every criterion"

    @pytest.mark.parametrize("fid", sorted(E.FIXTURE_CRITERIA))
    def test_each_fixture_has_a_good_answer_that_passes_everything(self, fid):
        for c in E.FIXTURE_CRITERIA[fid]:
            passed, evidence = E.CRITERIA[c](E.GOOD[fid])
            assert passed, f"{fid}/{c} rejects the model answer: {evidence}"

    def test_no_criterion_is_unused(self):
        used = {c for names in E.FIXTURE_CRITERIA.values() for c in names}
        assert not set(E.CRITERIA) - used, f"unused criteria: {sorted(set(E.CRITERIA) - used)}"

    def test_no_format_only_degradation_criterion(self):
        """Presence of a Full/Partial/Blocked label is not evidence the label is correct.

        The March A/B was built almost entirely from criteria of that shape, which is why its
        +74.1 points measured formatting. Verdict *correctness* is checked instead, by
        degradation_is_not_full on the two unanswerable fixtures.
        """
        assert "declares_degradation" not in E.CRITERIA
        for fid in ("GS-E3", "GS-E4"):
            assert "degradation_is_not_full" in E.FIXTURE_CRITERIA[fid]


class TestFixtures:
    def test_every_fixture_with_criteria_has_a_file(self):
        ids = {f["id"] for f in E.fixtures()}
        assert set(E.FIXTURE_CRITERIA) <= ids, sorted(set(E.FIXTURE_CRITERIA) - ids)

    @pytest.mark.parametrize("path", sorted(EVAL_DIR.glob("*.json")))
    def test_fixture_records_its_ground_truth(self, path):
        fx = json.loads(path.read_text(encoding="utf-8"))
        for field in ("id", "title", "question", "ground_truth", "why_this_fixture"):
            assert fx.get(field), f"{path.name} missing {field}"
        assert len(fx["ground_truth"]) > 60, (
            f"{path.name}: ground truth must state the verifiable answer, not gesture at it"
        )

    def test_two_fixtures_have_no_findable_answer(self):
        """Honest degradation has to be measured on questions that cannot be answered."""
        unanswerable = [
            f for f in E.fixtures()
            if "degradation_is_not_full" in E.FIXTURE_CRITERIA[f["id"]]
        ]
        assert len(unanswerable) >= 2, "no scenario measures a correct refusal"


class TestArmsAreComparable:
    """The whole harness is worthless if the arms differ in anything but the skill."""

    SRC = (pathlib.Path(__file__).resolve().parents[1] / "eval_forward.py").read_text(
        encoding="utf-8"
    )

    def test_no_arm_is_denied_tools(self):
        """An earlier version passed `--tools ""` to the without-skill arm. That measured
        "skill plus a way to search" against "no skill and no way to search" — for a search
        skill the second arm cannot cite a URL or check a qualifier at all, so the delta was
        guaranteed and meaningless."""
        assert '"--tools", ""' not in self.SRC, "one arm is being denied tools"
        assert 'if not with_skill:' not in self.SRC, (
            "no branch may vary the command by arm except the prompt"
        )

    def test_tool_grant_is_a_single_shared_constant(self):
        assert "ARM_TOOLS" in self.SRC
        assert self.SRC.count('"--tools", ARM_TOOLS') == 1
        for tool in ("WebSearch", "WebFetch", "Read"):
            assert tool in E.ARM_TOOLS, f"{E.ARM_TOOLS} lacks {tool}"

    @staticmethod
    def _branch_body(src, header):
        """Lines indented deeper than `header`, i.e. the block it introduces."""
        lines = src.split("\n")
        i = next(n for n, l in enumerate(lines) if header in l)
        indent = len(lines[i]) - len(lines[i].lstrip())
        out = []
        for line in lines[i + 1:]:
            if line.strip() and (len(line) - len(line.lstrip())) <= indent:
                break
            out.append(line)
        return "\n".join(out)

    def test_the_only_arm_difference_is_the_prompt(self):
        """`run_arm` may branch on with_skill exactly once, and that branch may only touch the
        prompt — never the command, which is what would reintroduce an arm asymmetry."""
        body = self.SRC.split("def run_arm(")[1].split("\ndef ")[0]
        assert body.count("if with_skill") == 1, body.count("if with_skill")
        branch = self._branch_body(body, "if with_skill:")
        assert branch.strip(), "could not extract the with_skill branch"
        assert "prompt" in branch
        assert "cmd" not in branch, f"the with_skill branch modifies the command:\n{branch}"

    def test_without_skill_arm_is_never_told_the_path(self):
        body = self.SRC.split("def run_arm(")[1].split("\ndef ")[0]
        pointer_block = body.split("if with_skill:")[1].split("# --max-turns")[0]
        assert "SKILL_DIR" in pointer_block, "the skill path must only appear in the with arm"


class TestRepeatAndOrder:
    def test_majority_aggregation_rejects_a_minority_pass(self):
        gradings = [
            {"c": {"passed": True, "evidence": "a"}},
            {"c": {"passed": False, "evidence": "b"}},
            {"c": {"passed": False, "evidence": "c"}},
        ]
        assert E._majority(gradings)["c"]["passed"] is False
        assert "1/3 samples" in E._majority(gradings)["c"]["evidence"]

    def test_majority_accepts_a_majority_pass(self):
        gradings = [
            {"c": {"passed": True, "evidence": "a"}},
            {"c": {"passed": True, "evidence": "b"}},
            {"c": {"passed": False, "evidence": "c"}},
        ]
        assert E._majority(gradings)["c"]["passed"] is True

    def test_repeat_samples_are_collected(self, tmp_path):
        fx = E.fixtures()[0]
        for n in range(3):
            (tmp_path / f"{fx['id']}.with.{n}.md").write_text("x", encoding="utf-8")
        found = E._arm_files(tmp_path, fx["id"], "with")
        assert len(found) == 3, found

    def test_run_accepts_repeat_and_seed(self):
        src = TestArmsAreComparable.SRC
        assert '"--repeat"' in src and '"--seed"' in src
        assert "rng.shuffle(jobs)" in src, (
            "call order must be shuffled, or drift during the run lands on one arm"
        )


class TestExitCodes:
    def test_no_wins_is_inconclusive_not_success(self, tmp_path):
        """Zero losses is not evidence of benefit. A run where both arms answer identically
        demonstrated nothing and must not exit 0."""
        for fx in E.fixtures():
            for arm in ("with", "without"):
                _write_arm(tmp_path, fx["id"], arm, E.GOOD[fx["id"]])
        assert E.grade_dir(tmp_path) == 2

    def test_min_wins_is_positive(self):
        assert E.MIN_WINS >= 1


class TestHarnessSafety:
    def test_both_arms_receive_the_same_model(self):
        """The March run used the default model with the skill and the fast model without it,
        which confounds capability with skill presence. `run_arm` takes one model argument and
        main() passes args.model to both arms."""
        src = (pathlib.Path(__file__).resolve().parents[1] / "eval_forward.py").read_text(
            encoding="utf-8"
        )
        assert src.count("run_arm(fx, with_skill, args.model") == 1, (
            "both arms must be launched with the same --model value"
        )
        assert "--model" in src and 'default="sonnet"' in src

    def test_harness_error_is_not_graded(self):
        """A setup failure must not read as a pass or as a loss."""
        src = (pathlib.Path(__file__).resolve().parents[1] / "eval_forward.py").read_text(
            encoding="utf-8"
        )
        assert "HARNESS ERROR" in src
        assert "return 3" in src, "grade_dir must exit INCOMPLETE, not 0/1, on harness errors"

    def test_grade_dir_reports_incomplete_when_outputs_are_missing(self, tmp_path):
        assert E.grade_dir(tmp_path) == 3

    def test_grade_dir_reports_incomplete_on_a_harness_error(self, tmp_path):
        for fx in E.fixtures():
            _write_arm(tmp_path, fx["id"], "with", "HARNESS ERROR: not logged in")
            _write_arm(tmp_path, fx["id"], "without", "whatever")
        assert E.grade_dir(tmp_path) == 3

    def test_grade_dir_refuses_a_with_arm_that_never_opened_the_skill(self, tmp_path):
        """The manipulation must be verified. An arm labelled with-skill that answered from
        priors is a without-skill result, and grading it credits the base model to the skill."""
        for fx in E.fixtures():
            _write_arm(tmp_path, fx["id"], "with", E.GOOD[fx["id"]], skill_read=False)
            _write_arm(tmp_path, fx["id"], "without", E.BAD[fx["id"]])
        assert E.grade_dir(tmp_path) == 3

    def test_grade_dir_refuses_a_with_arm_with_no_trace_at_all(self, tmp_path):
        for fx in E.fixtures():
            (tmp_path / f"{fx['id']}.with.md").write_text(E.GOOD[fx["id"]], encoding="utf-8")
            _write_arm(tmp_path, fx["id"], "without", E.BAD[fx["id"]])
        assert E.grade_dir(tmp_path) == 3

    def test_grade_dir_scores_recorded_answers(self, tmp_path):
        """End-to-end on the built-in GOOD/BAD texts: a real grading run must produce wins."""
        for fx in E.fixtures():
            _write_arm(tmp_path, fx["id"], "with", E.GOOD[fx["id"]])
            _write_arm(tmp_path, fx["id"], "without", E.BAD[fx["id"]])
        assert E.grade_dir(tmp_path) == 0

    def test_grade_dir_flags_a_loss(self, tmp_path):
        """Arms swapped: the harness must be able to report the skill losing."""
        for fx in E.fixtures():
            _write_arm(tmp_path, fx["id"], "with", E.BAD[fx["id"]])
            _write_arm(tmp_path, fx["id"], "without", E.GOOD[fx["id"]])
        assert E.grade_dir(tmp_path) == 1, (
            "a harness that cannot report a loss is not measuring anything"
        )
