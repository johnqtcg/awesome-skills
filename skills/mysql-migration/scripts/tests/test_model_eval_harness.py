"""Tests for scripts/run_model_eval.py — the grader, not the model.

The harness is only worth shipping if its rubric can be trusted, which means it
must be able to say FAIL. These tests drive it in three directions with recorded
transcripts, so the grader is falsifiable without invoking a model at all.

Nothing here measures the skill. The fixtures under eval_grader_fixtures/ are
synthetic inputs written to exercise the rubric; see that directory's README.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import sys

import pytest

SKILL_DIR = pathlib.Path(__file__).resolve().parents[2]
EVAL_PATH = SKILL_DIR / "scripts" / "run_model_eval.py"
FIXTURES = pathlib.Path(__file__).resolve().parent / "eval_grader_fixtures"


def _load():
    spec = importlib.util.spec_from_file_location("mysql_migration_model_eval", EVAL_PATH)
    assert spec and spec.loader, f"cannot load {EVAL_PATH}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ev = _load()


class TestRubricIsWellFormed:
    def test_every_criterion_has_a_distinct_key(self):
        keys = [c.key for c in ev.STRUCTURE + ev.TECHNICAL]
        assert len(keys) == len(set(keys)), f"duplicate criterion keys: {keys}"

    def test_every_criterion_has_a_human_description(self):
        for c in ev.STRUCTURE + ev.TECHNICAL:
            assert len(c.description) > 10, f"{c.key} has no usable description"

    def test_at_least_one_required_criterion_exists(self):
        assert any(c.required for c in ev.STRUCTURE + ev.TECHNICAL), (
            "with no required criterion the harness can never fail on regression"
        )

    @pytest.mark.parametrize("crit", ev.STRUCTURE + ev.TECHNICAL,
                             ids=[c.key for c in ev.STRUCTURE + ev.TECHNICAL])
    def test_each_criterion_discriminates(self, crit):
        """A criterion that matches everything, or nothing, measures nothing."""
        empty = "The migration looks fine to me."
        assert not crit.met(empty), (
            f"{crit.key} fires on a response containing none of its subject matter"
        )


class TestGraderOutcomes:
    """Drive the whole harness through main(), not just the helpers."""

    def _run(self, subdir: str) -> tuple[int, str]:
        import io
        import contextlib
        target = FIXTURES / subdir if subdir else FIXTURES
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = ev.main(["--replay", str(target)])
        return rc, buf.getvalue()

    def test_discriminating_pair_passes(self):
        rc, out = self._run("")
        assert rc == 0, out
        assert "**PASS**" in out

    def test_regressed_pair_fails_and_names_the_criteria(self):
        rc, out = self._run("regress")
        assert rc == 1, out
        # The per-scenario gate is more specific than the aggregate one and fires
        # first; either wording must name the criterion that was lost.
        assert "lost a required criterion" in out or "required criteria regressed" in out
        assert "session_guard" in out

    def test_lint_regression_is_reported_as_such(self):
        """Both arms tie on the rubric; only the lint verdict separates them.

        The reason matters: reporting this as "improved nothing" would hide that
        the with-skill arm emitted SQL the target server rejects.
        """
        rc, out = self._run("lintfail")
        assert rc == 1, out
        assert "critical lint findings" in out

    def test_no_arguments_skips_loudly_without_claiming_success(self):
        import io
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = ev.main([])
        out = buf.getvalue()
        assert rc == 0
        assert "SKIP" in out
        assert "UNANSWERED" in out, (
            "a skipped evaluation must not read like a passed one"
        )

    def test_empty_replay_dir_is_an_error_not_a_pass(self, tmp_path, capsys):
        rc = ev.main(["--replay", str(tmp_path)])
        capsys.readouterr()
        assert rc == 2, "grading zero transcripts must not report success"

    def test_one_armed_run_cannot_pass(self, tmp_path, capsys):
        """A directory with only with-skill transcripts proves nothing."""
        (tmp_path / "MIG-002.with_skill.txt").write_text(
            (FIXTURES / "MIG-002.with_skill.txt").read_text(encoding="utf-8"), encoding="utf-8")
        rc = ev.main(["--replay", str(tmp_path)])
        capsys.readouterr()
        assert rc == 1

    def test_json_output_is_parseable(self, capsys):
        rc = ev.main(["--replay", str(FIXTURES), "--format", "json"])
        payload = json.loads(capsys.readouterr().out)
        assert rc == 0
        assert payload["pass"] is True
        assert payload["grades"], "grades must be reported per scenario and arm"
        arms = {g["arm"] for g in payload["grades"]}
        assert arms == {"with_skill", "without_skill"}


class TestGraderIsDeterministic:
    def test_same_input_scores_identically(self, capsys):
        first = ev.main(["--replay", str(FIXTURES), "--format", "json"])
        a = capsys.readouterr().out
        second = ev.main(["--replay", str(FIXTURES), "--format", "json"])
        b = capsys.readouterr().out
        assert first == second
        assert a == b, "a re-run over the same transcripts must produce the same score"

    def test_no_model_is_invoked_during_replay(self, monkeypatch, capsys):
        def explode(*_args, **_kwargs):
            raise AssertionError("replay mode must not call a model")
        monkeypatch.setattr(ev, "run_model", explode)
        rc = ev.main(["--replay", str(FIXTURES)])
        capsys.readouterr()
        assert rc == 0


class TestSqlExtraction:
    def test_extracts_fenced_sql(self):
        got = ev.extract_sql("text\n```sql\nALTER TABLE t ADD COLUMN c INT;\n```\nmore")
        assert "ALTER TABLE t" in got

    def test_ignores_non_sql_fences(self):
        got = ev.extract_sql("```python\nprint('ALTER TABLE t')\n```")
        assert got.strip() == ""

    def test_missing_fence_yields_nothing_rather_than_garbage(self):
        assert ev.extract_sql("no code here").strip() == ""


class TestFixturesAreLabelledAsNonEvidence:
    """The fixtures must never be mistaken for a measurement of the skill."""

    def test_readme_exists_and_disclaims(self):
        readme = FIXTURES / "README.md"
        assert readme.exists()
        text = readme.read_text(encoding="utf-8")
        assert "NOT evaluation results" in text
        assert "synthetic" in text.lower()

    def test_coverage_still_reports_the_evaluation_as_unanswered(self):
        cov = (SKILL_DIR / "scripts" / "tests" / "COVERAGE.md").read_text(encoding="utf-8")
        gap_rows = [ln for ln in cov.split("\n")
                    if ln.startswith("|") and "odel evaluation" in ln]
        assert gap_rows, "COVERAGE.md must list model evaluation as an outstanding gap"
        assert any("UNANSWERED" in ln or "never run" in ln for ln in gap_rows), (
            "until a real model run happens, the gap row must say the question is open: "
            f"{gap_rows}"
        )
        assert "model arm has NOT been run" in cov


class TestModelInvocationFailure:
    """A model that was requested but could not run is exit 3, never 0 or 1.

    Conflating "the model was unreachable" with "the skill did not help" would
    let an auth failure be read as an evaluation result.
    """

    def test_failing_model_command_exits_3(self, tmp_path, capsys):
        rc = ev.main(["--model-cmd", "exit 7", "--out", str(tmp_path)])
        err = capsys.readouterr().err
        assert rc == 3, "a broken model command must not look like a graded run"
        assert "model invocation failed" in err

    def test_nonexistent_model_command_exits_3(self, tmp_path, capsys):
        rc = ev.main(["--model-cmd", "definitely-not-a-real-binary-9f3a", "--out", str(tmp_path)])
        capsys.readouterr()
        assert rc == 3

    def test_no_report_is_written_when_the_model_fails(self, tmp_path, capsys):
        ev.main(["--model-cmd", "exit 7", "--out", str(tmp_path)])
        capsys.readouterr()
        assert not (tmp_path / "report.md").exists(), (
            "a failed run must not leave a report that could be quoted as a result"
        )


class TestScenarioPairing:
    """Aggregates over different scenario sets are not a comparison.

    An unpaired scenario is missing data: if one arm answers an easy scenario the
    other never saw, the difference in totals says nothing about the skill.
    """

    def _write(self, d: pathlib.Path, scenario: str, arm: str, body: str):
        (d / f"{scenario}.{arm}.txt").write_text(body, encoding="utf-8")

    def test_unpaired_scenario_is_excluded_and_named(self, tmp_path, capsys):
        strong = (FIXTURES / "MIG-002.with_skill.txt").read_text(encoding="utf-8")
        weak = (FIXTURES / "MIG-002.without_skill.txt").read_text(encoding="utf-8")
        self._write(tmp_path, "MIG-002", "with_skill", strong)
        self._write(tmp_path, "MIG-002", "without_skill", weak)
        # MIG-006 answered only by the with-skill arm.
        self._write(tmp_path, "MIG-006", "with_skill", strong)
        ev.main(["--replay", str(tmp_path)])
        out = capsys.readouterr().out
        assert "Unpaired scenarios excluded" in out
        assert "MIG-006" in out
        assert "Paired scenarios scored: 1" in out

    def test_totals_use_only_paired_scenarios(self, tmp_path, capsys):
        """The unpaired arm must not inflate its own counts."""
        strong = (FIXTURES / "MIG-002.with_skill.txt").read_text(encoding="utf-8")
        weak = (FIXTURES / "MIG-002.without_skill.txt").read_text(encoding="utf-8")
        self._write(tmp_path, "MIG-002", "with_skill", strong)
        self._write(tmp_path, "MIG-002", "without_skill", weak)
        self._write(tmp_path, "MIG-006", "with_skill", strong)
        ev.main(["--replay", str(tmp_path)])
        out = capsys.readouterr().out
        rows = [ln for ln in out.split("\n") if ln.startswith("| states the MySQL version")]
        assert rows, out
        assert "1/1" in rows[0], (
            f"denominator must be the paired count, not the per-arm count: {rows[0]}"
        )

    def test_no_paired_scenario_is_a_failure(self, tmp_path, capsys):
        strong = (FIXTURES / "MIG-002.with_skill.txt").read_text(encoding="utf-8")
        weak = (FIXTURES / "MIG-002.without_skill.txt").read_text(encoding="utf-8")
        self._write(tmp_path, "MIG-002", "with_skill", strong)
        self._write(tmp_path, "MIG-006", "without_skill", weak)
        rc = ev.main(["--replay", str(tmp_path)])
        out = capsys.readouterr().out
        assert rc == 1
        assert "nothing is comparable" in out


class TestOnlyRequiredGainsCount:
    """Moving an optional nice-to-have while the contract items stay flat is not
    evidence the skill works."""

    def test_optional_only_improvement_fails(self, tmp_path, capsys):
        # Both arms satisfy every required criterion identically; the with-skill
        # arm adds only the optional pk_range_backfill signal.
        base = (
            "MySQL 8.0.32. Risk: WARN.\n"
            "Scorecard: 9/12 PASS\n"
            "Assumption: peak QPS unknown.\n"
            "Rollback: compensating DDL.\n"
            "```sql\nSET SESSION lock_wait_timeout = 3;\n"
            "ALTER TABLE t ADD INDEX i (c), ALGORITHM=INPLACE, LOCK=NONE;\n```\n"
        )
        extra = base + "\nBackfill batches by primary-key range.\n"
        (tmp_path / "MIG-002.without_skill.txt").write_text(base, encoding="utf-8")
        (tmp_path / "MIG-002.with_skill.txt").write_text(extra, encoding="utf-8")
        rc = ev.main(["--replay", str(tmp_path)])
        out = capsys.readouterr().out
        assert rc == 1, out
        assert "no *required* criterion" in out
        assert "pk_range_backfill" in out, "say which optional criterion did move"

    def test_required_gain_still_passes(self, tmp_path, capsys):
        (tmp_path / "MIG-002.without_skill.txt").write_text(
            (FIXTURES / "MIG-002.without_skill.txt").read_text(encoding="utf-8"), encoding="utf-8")
        (tmp_path / "MIG-002.with_skill.txt").write_text(
            (FIXTURES / "MIG-002.with_skill.txt").read_text(encoding="utf-8"), encoding="utf-8")
        rc = ev.main(["--replay", str(tmp_path)])
        capsys.readouterr()
        assert rc == 0


class TestUnfencedSqlStillReachesTheLinter:
    """Omitting a code fence must not be a way to dodge the lint arm."""

    def test_bare_alter_is_extracted(self):
        got = ev.extract_sql(
            "Here is the change:\n"
            "ALTER TABLE t ADD COLUMN c INT, ALGORITHM=INSTANT, LOCK=NONE;\n"
            "That should do it.")
        assert "ALTER TABLE t" in got, "unfenced DDL must still be linted"

    def test_bare_set_session_at_line_start_is_extracted(self):
        assert "lock_wait_timeout" in ev.extract_sql(
            "Run this first:\nSET SESSION lock_wait_timeout = 3;\nthen the alter.")

    def test_sql_embedded_mid_sentence_is_not_extracted(self):
        """Deliberate: the fallback anchors at line start.

        Grabbing statement-shaped fragments from the middle of prose would feed
        the linter half-sentences and produce findings about text nobody would
        execute. A model that buries DDL mid-paragraph is not emitting runnable
        SQL either way.
        """
        assert ev.extract_sql("You would then run ALTER TABLE t ADD COLUMN c INT; here.").strip() \
            == ""

    def test_fenced_blocks_still_take_precedence(self):
        got = ev.extract_sql(
            "ALTER TABLE outside ADD COLUMN a INT;\n"
            "```sql\nALTER TABLE inside ADD COLUMN b INT;\n```")
        assert "inside" in got and "outside" not in got

    def test_prose_without_sql_extracts_nothing(self):
        assert ev.extract_sql("I would alter the table carefully.").strip() == ""

    def test_unfenced_bad_sql_is_graded_as_critical(self, tmp_path, capsys):
        """End to end: a response that hides its DDL still gets caught."""
        clean = (
            "MySQL 5.7.40. Risk: WARN. Scorecard: PASS. Assumption: none.\n"
            "Rollback: compensating DDL.\n"
            "```sql\nSET SESSION lock_wait_timeout = 3;\n"
            "ALTER TABLE t ADD COLUMN c INT, ALGORITHM=INPLACE, LOCK=NONE;\n```\n"
        )
        unfenced_bad = (
            "MySQL 5.7.40. Risk: WARN. Scorecard: PASS. Assumption: none.\n"
            "Rollback: compensating DDL.\n"
            "SET SESSION lock_wait_timeout = 3;\n"
            "ALTER TABLE t ADD COLUMN c INT, ALGORITHM=INSTANT, LOCK=NONE;\n"
        )
        (tmp_path / "MIG-005.without_skill.txt").write_text(clean, encoding="utf-8")
        (tmp_path / "MIG-005.with_skill.txt").write_text(unfenced_bad, encoding="utf-8")
        rc = ev.main(["--replay", str(tmp_path)])
        out = capsys.readouterr().out
        assert rc == 1, out
        assert "critical lint findings" in out


class TestWithSkillArmLoadsReferences:
    """SKILL.md is a router; injecting it alone measures a crippled skill."""

    # SKILL.md itself names every reference file and mentions gh-ost, so asserting
    # on a filename or a tool name proves nothing about injection. These probes are
    # strings that exist ONLY in the reference bodies.
    MATRIX_ONLY = "Provenance"
    LARGE_TABLE_ONLY = "Connect to replica, migrate on master"

    def _fixture(self, ref: str) -> dict:
        return {"migration_snippet": "ALTER TABLE t ADD COLUMN c INT;",
                "context": {"mysql_version": "8.0.32"}, "reference": ref}

    def test_probe_strings_are_absent_from_skill_md_alone(self):
        """Guard the guard: if these leak into SKILL.md the tests below go vacuous."""
        skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        assert self.MATRIX_ONLY not in skill
        assert self.LARGE_TABLE_ONLY not in skill

    def test_matrix_body_is_injected(self):
        prompt = ev.build_prompt(self._fixture("references/migration-anti-examples.md"), True)
        assert self.MATRIX_ONLY in prompt, (
            "the algorithm matrix body must be present, not merely referenced by name"
        )
        assert "--- references/ddl-algorithm-matrix.md ---" in prompt

    def test_declared_reference_body_is_injected(self):
        prompt = ev.build_prompt(self._fixture("references/large-table-migration.md"), True)
        assert self.LARGE_TABLE_ONLY in prompt
        assert "--- references/large-table-migration.md ---" in prompt

    def test_without_skill_arm_gets_neither(self):
        prompt = ev.build_prompt(self._fixture("references/large-table-migration.md"), False)
        assert self.MATRIX_ONLY not in prompt
        assert self.LARGE_TABLE_ONLY not in prompt
        assert "ALTER TABLE t" in prompt

    def test_with_skill_prompt_carries_more_than_skill_md(self):
        fx = self._fixture("references/large-table-migration.md")
        skill_len = len((SKILL_DIR / "SKILL.md").read_text(encoding="utf-8"))
        w = ev.build_prompt(fx, True)
        assert len(w) > skill_len * 1.5, (
            "the with-skill arm must carry the references too; comparing against the "
            "without-skill stub would pass on SKILL.md alone"
        )

    def test_referenced_files_always_includes_the_matrix(self):
        assert "references/ddl-algorithm-matrix.md" in ev.referenced_files({})

    def test_referenced_files_does_not_duplicate(self):
        refs = ev.referenced_files({"reference": "references/ddl-algorithm-matrix.md"})
        assert refs.count("references/ddl-algorithm-matrix.md") == 1


class TestNoDuplicateInjection:
    """A fixture naming SKILL.md as its reference must not get it twice."""

    def test_skill_md_is_filtered_out_of_referenced_files(self):
        assert "SKILL.md" not in ev.referenced_files({"reference": "SKILL.md"})
        assert "SKILL.md" not in ev.referenced_files({"reference": "./SKILL.md"})

    def test_prompt_contains_skill_md_exactly_once(self):
        fx = {"migration_snippet": "ALTER TABLE t ADD COLUMN c INT;",
              "context": {"mysql_version": "8.0.32"}, "reference": "SKILL.md"}
        prompt = ev.build_prompt(fx, with_skill=True)
        assert prompt.count("# MySQL Migration Safety Review") == 1, (
            "a duplicated skill body pads the with-skill arm and can inflate any "
            "length- or repetition-sensitive effect"
        )

    def test_a_real_reference_is_still_injected_once(self):
        fx = {"migration_snippet": "ALTER TABLE t ADD COLUMN c INT;",
              "context": {"mysql_version": "8.0.32"},
              "reference": "references/large-table-migration.md"}
        prompt = ev.build_prompt(fx, with_skill=True)
        assert prompt.count("--- references/large-table-migration.md ---") == 1


class TestPerScenarioGates:
    """Totals can hide a scenario the skill made worse."""

    STRONG_CLEAN = (
        "MySQL 8.0.32. Risk: WARN. Scorecard: PASS.\n"
        "Assumption: peak QPS unknown.\nRollback: compensating DDL.\n"
        "```sql\nSET SESSION lock_wait_timeout = 3;\n"
        "ALTER TABLE t ADD INDEX i (c), ALGORITHM=INPLACE, LOCK=NONE;\n```\n"
    )
    STRONG_BAD_SQL = (
        "MySQL 8.0.32. Risk: WARN. Scorecard: PASS.\n"
        "Assumption: peak QPS unknown.\nRollback: compensating DDL.\n"
        "```sql\nSET SESSION lock_wait_timeout = 3;\n"
        "ALTER TABLE t ADD COLUMN c INT, ALGORITHM=INSTANT, LOCK=NONE;\n```\n"
    )
    WEAK = "It should be fine to run this.\n"

    def _pair(self, d, sid, without, with_):
        (d / f"{sid}.without_skill.txt").write_text(without, encoding="utf-8")
        (d / f"{sid}.with_skill.txt").write_text(with_, encoding="utf-8")

    def test_one_scenario_gaining_critical_lint_fails_despite_a_net_gain(
            self, tmp_path, capsys):
        """MIG-002 improves a lot; MIG-004 gains a critical finding. Net totals
        could be read as success — the per-scenario gate must not allow it."""
        self._pair(tmp_path, "MIG-002", self.WEAK, self.STRONG_CLEAN)
        self._pair(tmp_path, "MIG-004", self.STRONG_CLEAN, self.STRONG_BAD_SQL)
        rc = ev.main(["--replay", str(tmp_path)])
        out = capsys.readouterr().out
        assert rc == 1, out
        assert "Per-scenario regressions" in out
        assert "MIG-004" in out

    def test_one_scenario_losing_a_required_criterion_fails(self, tmp_path, capsys):
        no_guard = self.STRONG_CLEAN.replace("SET SESSION lock_wait_timeout = 3;\n", "")
        self._pair(tmp_path, "MIG-002", self.WEAK, self.STRONG_CLEAN)
        self._pair(tmp_path, "MIG-004", self.STRONG_CLEAN, no_guard)
        rc = ev.main(["--replay", str(tmp_path)])
        out = capsys.readouterr().out
        assert rc == 1, out
        assert "lost a required criterion" in out
        assert "MIG-004" in out
        assert "session_guard" in out

    def test_uniform_improvement_still_passes(self, tmp_path, capsys):
        self._pair(tmp_path, "MIG-002", self.WEAK, self.STRONG_CLEAN)
        self._pair(tmp_path, "MIG-004", self.WEAK, self.STRONG_CLEAN)
        rc = ev.main(["--replay", str(tmp_path)])
        out = capsys.readouterr().out
        assert rc == 0, out
        assert "Per-scenario regressions" not in out


class TestAbsoluteSafetyGate:
    """Matching a bad baseline is not success.

    Before this gate the harness compared only the DELTA in critical findings, so
    both arms could emit the same server-rejected statement and the with-skill arm
    still "won" on formatting. For a migration skill that is the exact failure mode
    the whole audit was about: output that reads well and does not run.
    """

    BAD = (
        "MySQL 8.0.28. Risk: WARN. Scorecard: PASS. Assumption: none.\n"
        "Rollback: compensating DDL.\n"
        "```sql\nSET SESSION lock_wait_timeout = 3;\n"
        "ALTER TABLE t ADD COLUMN c INT, ALGORITHM=INSTANT, LOCK=NONE;\n```\n"
    )
    BAD_UNFORMATTED = (
        "Risk: WARN. Scorecard: PASS. Assumption: none. Rollback: compensating DDL.\n"
        "```sql\nSET SESSION lock_wait_timeout = 3;\n"
        "ALTER TABLE t ADD COLUMN c INT, ALGORITHM=INSTANT, LOCK=NONE;\n```\n"
    )
    GOOD = (
        "MySQL 8.0.28. Risk: WARN. Scorecard: PASS. Assumption: none.\n"
        "Rollback: compensating DDL.\n"
        "```sql\nSET SESSION lock_wait_timeout = 3;\n"
        "ALTER TABLE t ADD COLUMN c INT DEFAULT NULL, ALGORITHM=INSTANT;\n```\n"
    )

    def _pair(self, d, without, with_, sid="MIG-002"):
        (d / f"{sid}.without_skill.txt").write_text(without, encoding="utf-8")
        (d / f"{sid}.with_skill.txt").write_text(with_, encoding="utf-8")

    def test_equally_bad_arms_do_not_pass_on_formatting(self, tmp_path, capsys):
        self._pair(tmp_path, self.BAD_UNFORMATTED, self.BAD)
        rc = ev.main(["--replay", str(tmp_path)])
        out = capsys.readouterr().out
        assert rc == 1, out
        assert "critical findings" in out
        assert "beside the point" in out, (
            "the message must say why matching the baseline is not enough"
        )

    def test_clean_with_skill_arm_passes(self, tmp_path, capsys):
        self._pair(tmp_path, self.BAD_UNFORMATTED, self.GOOD)
        rc = ev.main(["--replay", str(tmp_path)])
        capsys.readouterr()
        assert rc == 0

    def test_gate_is_absolute_not_a_delta(self, tmp_path, capsys):
        """Even a strict improvement fails while any critical remains."""
        two_critical = self.BAD.replace(
            "ALTER TABLE t ADD COLUMN c INT, ALGORITHM=INSTANT, LOCK=NONE;",
            "ALTER TABLE t ADD COLUMN c INT, ALGORITHM=INSTANT, LOCK=NONE;\n"
            "ALTER TABLE t ADD INDEX i (c), ALGORITHM=INSTANT;")
        self._pair(tmp_path, two_critical, self.BAD)  # 2 -> 1 is an improvement
        rc = ev.main(["--replay", str(tmp_path)])
        out = capsys.readouterr().out
        assert rc == 1, out
        assert "limit: 0" in out

    def test_threshold_is_configurable_but_defaults_to_zero(self, tmp_path, capsys):
        self._pair(tmp_path, self.BAD_UNFORMATTED, self.BAD)
        assert ev.main(["--replay", str(tmp_path)]) == 1
        capsys.readouterr()
        assert ev.main(["--replay", str(tmp_path), "--max-critical", "1"]) == 0
        capsys.readouterr()

    def test_max_warnings_gate_is_opt_in(self, tmp_path, capsys):
        """Isolate warnings: both arms drop the guard, so nothing REGRESSES.

        Both therefore carry an MM015 warning and neither loses a required
        criterion; only the with-skill arm adds the version, so the run improves.
        The default must pass on that, and --max-warnings 0 must not.
        """
        no_guard_weak = self.GOOD.replace(
            "SET SESSION lock_wait_timeout = 3;\n", "").replace("MySQL 8.0.28. ", "")
        no_guard_strong = self.GOOD.replace("SET SESSION lock_wait_timeout = 3;\n", "")
        self._pair(tmp_path, no_guard_weak, no_guard_strong)

        rc_default = ev.main(["--replay", str(tmp_path)])
        out_default = capsys.readouterr().out
        rc_strict = ev.main(["--replay", str(tmp_path), "--max-warnings", "0"])
        out_strict = capsys.readouterr().out
        assert rc_default == 0, out_default
        assert rc_strict == 1, out_strict
        assert "max-warnings" in out_strict


class TestLintErrorIsNotACleanLint:
    """A crashed linter must never compare as better than a clean one."""

    def _grade(self, arm, **kw):
        met = {c.key: True for c in ev.STRUCTURE + ev.TECHNICAL}
        base = dict(lint_critical=0, lint_warning=0, lint_error=False, score=10, max_score=10)
        base.update(kw)
        return ev.Grade("S", arm, met, **base)

    def test_lint_error_fails_the_run(self):
        _, ok = ev.report([self._grade("without_skill"),
                           self._grade("with_skill", lint_error=True)])
        assert not ok

    def test_lint_error_in_either_arm_fails(self):
        """An unparsed baseline makes the comparison meaningless too."""
        _, ok = ev.report([self._grade("without_skill", lint_error=True),
                           self._grade("with_skill")])
        assert not ok

    def test_message_says_nothing_is_known(self):
        text, _ = ev.report([self._grade("without_skill"),
                             self._grade("with_skill", lint_error=True)])
        assert "not a clean lint" in text

    def test_no_negative_sentinel_is_used(self):
        """-1 sorted as cleaner than 0 under `> 0` and `max(..., 0)` comparisons."""
        src = (SKILL_DIR / "scripts" / "run_model_eval.py").read_text(encoding="utf-8")
        assert "critical = -1" not in src, (
            "encoding an error as a score made a failed lint compare as cleaner than a clean one"
        )

    def test_grade_carries_an_explicit_error_flag(self):
        g = self._grade("with_skill", lint_error=True)
        assert g.as_dict()["lint_error"] is True
        assert g.lint_critical == 0, "the error must not be smuggled into the count"


class TestSkillDocMatchesFileDiscovery:
    """SKILL.md section 11 described the pre-fix behaviour."""

    SKILL_MD = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")

    def test_does_not_claim_explicit_naming_always_wins(self):
        assert "read whatever its extension" not in self.SKILL_MD, (
            "a known-unparseable carrier is reported as MM030 even when named explicitly"
        )

    def test_states_the_unknown_extension_carve_out(self):
        assert "unknown" in self.SKILL_MD and "MM030 finding whether named explicitly" in \
            self.SKILL_MD

    def test_says_why_scanning_a_changelog_as_sql_is_wrong(self):
        assert "masked inside string values" in self.SKILL_MD, (
            "the reason matters: it reported clean, not an error"
        )
