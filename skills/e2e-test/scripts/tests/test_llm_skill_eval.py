#!/usr/bin/env python3
"""Skill-output evaluation for the e2e-test skill.

This closes the layer the other suites do not reach. `test_skill_contract.py` asserts
the skill *contains* its rules; `test_golden_scenarios.py` asserts the fixtures describe
the right answers; `lint_e2e_spec.py` grades spec source that someone hands it. None of
them grades **a response to a task** — which is the artifact the skill actually
produces.

The grader here is deterministic and offline. It takes a response in Markdown and:

  1. extracts every TypeScript/JavaScript block and runs the skill's own linter over it,
     treating any CRITICAL finding as a defect;
  2. checks the fixture's `requires` patterns — the decisions the answer must make;
  3. checks the fixture's `forbids` patterns — the plausible wrong answers.

A fixture passes only when all three are clean. Two exemplars ship per fixture and the
suite asserts they land on opposite verdicts, so a grader that has stopped
discriminating fails here rather than reporting everything green.

`E2E_LLM_EVAL=1` additionally runs the fixtures against a live model; without it the
offline exemplar grading is what runs, and that is the part CI depends on.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
SKILL_DIR = TESTS_DIR.parent.parent
EVAL_DIR = TESTS_DIR / "llm_eval"

CODE_LANGS = {"ts", "typescript", "tsx", "js", "javascript", "jsx"}
FENCE_RE = re.compile(r"^```([A-Za-z0-9_+-]*)\s*$")


def load_linter(alias: str):
    """Import scripts/lint_e2e_spec.py by path.

    Registered in sys.modules *before* exec_module: the module uses
    `from __future__ import annotations`, so @dataclass resolves its field types via
    sys.modules[cls.__module__] and raises AttributeError on None when it is absent.
    """
    import importlib.util
    import sys

    path = SKILL_DIR / "scripts" / "lint_e2e_spec.py"
    spec = importlib.util.spec_from_file_location(alias, path)
    assert spec and spec.loader, f"cannot load {path}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[alias] = module
    spec.loader.exec_module(module)
    return module


def code_blocks(markdown: str) -> list[tuple[int, str, str]]:
    """Yield (start_line, lang, body) for every fenced block.

    Line-oriented rather than regex-over-the-whole-document, and it follows the
    CommonMark closing rule: a fence line carrying an info string (```` ```ts ````) is
    *content* inside an open block, never a closer. Only a bare fence closes. A
    non-greedy regex gets this wrong on any response that shows a fence inside a
    fence — and a skill that teaches by example does that constantly.
    """
    out: list[tuple[int, str, str]] = []
    lines = markdown.split("\n")
    i = 0
    while i < len(lines):
        m = FENCE_RE.match(lines[i])
        if not m:
            i += 1
            continue
        lang = m.group(1).lower()
        start = i
        i += 1
        body: list[str] = []
        while i < len(lines):
            close = FENCE_RE.match(lines[i])
            if close and not close.group(1):
                break
            body.append(lines[i])
            i += 1
        i += 1  # consume the closing fence
        out.append((start + 1, lang, "\n".join(body)))
    return out


def grade(response: str, meta: dict, linter) -> list[str]:
    """Return a list of defect strings. Empty means PASS."""
    defects: list[str] = []

    for line, lang, body in code_blocks(response):
        if lang not in CODE_LANGS:
            continue
        for f in linter.lint_source(body):
            if f.severity == "CRITICAL":
                defects.append(f"linter {f.rule} at response line ~{line + f.line}: {f.message}")

    for req in meta.get("requires", []):
        if not re.search(req["pattern"], response):
            defects.append(f"missing [{req['id']}] — {req['why']}")

    for bad in meta.get("forbids", []):
        m = re.search(bad["pattern"], response)
        if m:
            defects.append(f"forbidden [{bad['id']}] matched {m.group(0)!r} — {bad['why']}")

    return defects


def fixture_dirs() -> list[Path]:
    return sorted(p for p in EVAL_DIR.iterdir() if p.is_dir() and (p / "meta.json").exists())


def load_fixture(d: Path) -> dict:
    meta = json.loads((d / "meta.json").read_text())
    meta["_dir"] = d
    meta["_name"] = d.name
    return meta


class FixtureShapeTests(unittest.TestCase):
    """A fixture that is missing a field fails silently as 'nothing to check'."""

    def test_fixtures_exist(self) -> None:
        self.assertGreaterEqual(len(fixture_dirs()), 3,
                                "the eval layer needs fixtures to be an eval layer")

    def test_every_fixture_is_complete(self) -> None:
        for d in fixture_dirs():
            with self.subTest(fixture=d.name):
                meta = load_fixture(d)
                for field in ("title", "prompt", "why_this_fixture", "requires", "forbids"):
                    self.assertIn(field, meta, f"{d.name}/meta.json has no {field}")
                self.assertTrue(meta["requires"], "a fixture with no requirements grades nothing")
                self.assertTrue(meta["forbids"], "a fixture with no forbidden shape grades nothing")
                for pattern_set in ("requires", "forbids"):
                    for entry in meta[pattern_set]:
                        self.assertEqual({"id", "pattern", "why"}, set(entry),
                                         f"{d.name} {pattern_set} entry must carry id/pattern/why")
                        re.compile(entry["pattern"])  # raises on a broken pattern
                for name in ("good.md", "bad.md"):
                    self.assertTrue((d / name).exists(), f"{d.name} has no {name}")


class ExemplarGradingTests(unittest.TestCase):
    """The offline half: known-good and known-bad responses must land apart."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.linter = load_linter("lint_e2e_spec_llmeval")

    def test_good_exemplars_pass(self) -> None:
        for d in fixture_dirs():
            with self.subTest(fixture=d.name):
                meta = load_fixture(d)
                defects = grade((d / "good.md").read_text(), meta, self.linter)
                self.assertEqual([], defects,
                                 f"{d.name}/good.md should be clean:\n  " + "\n  ".join(defects))

    def test_bad_exemplars_fail(self) -> None:
        for d in fixture_dirs():
            with self.subTest(fixture=d.name):
                meta = load_fixture(d)
                defects = grade((d / "bad.md").read_text(), meta, self.linter)
                self.assertNotEqual([], defects, f"{d.name}/bad.md graded clean")

    def test_every_fixture_discriminates_on_more_than_one_axis(self) -> None:
        """A fixture whose bad exemplar trips exactly one check is one edit away from
        grading nothing. Require at least two independent defects."""
        for d in fixture_dirs():
            with self.subTest(fixture=d.name):
                meta = load_fixture(d)
                defects = grade((d / "bad.md").read_text(), meta, self.linter)
                self.assertGreaterEqual(len(defects), 2,
                                        f"{d.name}/bad.md trips only: {defects}")

    def test_all_three_check_families_earn_their_place(self) -> None:
        """Asserted across the corpus rather than per fixture: a refusal fixture may
        legitimately have no code to lint. But if a whole family never fires on any bad
        exemplar, that family is decoration — it would keep passing if deleted."""
        fired = set()
        for d in fixture_dirs():
            meta = load_fixture(d)
            for defect in grade((d / "bad.md").read_text(), meta, self.linter):
                fired.add(defect.split(" ")[0])
        self.assertEqual({"linter", "missing", "forbidden"}, fired,
                         f"a check family never fires on any bad exemplar: {fired}")


class GraderSelfTests(unittest.TestCase):
    """The grader is the thing everything else here trusts. Probe it directly with
    synthetic input rather than assuming the exemplars exercise it."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.linter = load_linter("lint_e2e_spec_llmeval_self")

    META = {
        "requires": [{"id": "r", "pattern": "REQUIRED_TOKEN", "why": "test"}],
        "forbids": [{"id": "f", "pattern": "FORBIDDEN_TOKEN", "why": "test"}],
    }

    def test_missing_requirement_is_a_defect(self) -> None:
        self.assertEqual(1, len(grade("nothing here", self.META, self.linter)))

    def test_present_requirement_is_clean(self) -> None:
        self.assertEqual([], grade("REQUIRED_TOKEN", self.META, self.linter))

    def test_forbidden_token_is_a_defect(self) -> None:
        d = grade("REQUIRED_TOKEN and FORBIDDEN_TOKEN", self.META, self.linter)
        self.assertEqual(1, len(d))
        self.assertIn("forbidden [f]", d[0])

    def test_critical_linter_finding_in_a_ts_block_is_a_defect(self) -> None:
        response = "REQUIRED_TOKEN\n\n```ts\nawait page.waitForTimeout(3000);\n```\n"
        d = grade(response, self.META, self.linter)
        self.assertTrue(any("linter" in x for x in d), d)

    def test_prose_outside_a_code_block_is_not_linted(self) -> None:
        """The linter grades spec source. Quoting a forbidden call while explaining why
        it is wrong must not be scored as writing it."""
        response = "REQUIRED_TOKEN — never call page.waitForTimeout(3000) to fix a race.\n"
        self.assertEqual([], grade(response, self.META, self.linter))

    def test_a_non_code_fence_is_not_linted(self) -> None:
        response = "REQUIRED_TOKEN\n\n```text\nawait page.waitForTimeout(3000);\n```\n"
        self.assertEqual([], grade(response, self.META, self.linter))

    def test_nested_fence_does_not_split_a_block(self) -> None:
        """A ```` ```ts ```` line inside an open block is content. A non-greedy
        regex reads it as a new opener and mis-slices every later block."""
        md = "```text\nexample:\n```ts\nconst a = 1;\n```\n"
        blocks = code_blocks(md)
        self.assertEqual(1, len(blocks), blocks)
        self.assertEqual("text", blocks[0][1])
        self.assertIn("```ts", blocks[0][2], "the inner fence is content, not a boundary")

    def test_block_extraction_reports_language_and_line(self) -> None:
        md = "intro\n\n```ts\nconst a = 1;\n```\n"
        blocks = code_blocks(md)
        self.assertEqual([(3, "ts", "const a = 1;")], blocks)


class LiveSkillEval(unittest.TestCase):
    """Opt-in: run the real skill against each prompt and grade what comes back.

    Off by default — it needs a model, costs money, and is not deterministic. The
    offline exemplar grading above is what CI relies on.

        E2E_LLM_EVAL=1 python3 -m pytest scripts/tests/test_llm_skill_eval.py -k Live
    """

    @classmethod
    def setUpClass(cls) -> None:
        if os.environ.get("E2E_LLM_EVAL") != "1":
            raise unittest.SkipTest("set E2E_LLM_EVAL=1 to run the live evaluation")
        cls.linter = load_linter("lint_e2e_spec_llmeval_live")

    def test_live_responses_pass_the_grader(self) -> None:
        skill_md = (SKILL_DIR / "SKILL.md").read_text()
        for d in fixture_dirs():
            with self.subTest(fixture=d.name):
                meta = load_fixture(d)
                prompt = (
                    "You are following this skill. Obey it exactly.\n\n"
                    "<skill>\n" + skill_md + "\n</skill>\n\n"
                    "Task:\n" + meta["prompt"]
                )
                proc = subprocess.run(
                    ["claude", "-p", prompt],
                    capture_output=True, text=True, timeout=900,
                )
                self.assertEqual(0, proc.returncode,
                                 f"model invocation failed: {proc.stderr[:400]}")
                defects = grade(proc.stdout, meta, self.linter)
                self.assertEqual([], defects,
                                 f"{d.name} live response defects:\n  " + "\n  ".join(defects))


if __name__ == "__main__":
    unittest.main()
