"""Offline tests for scripts/verify_examples_load.py.

The loader itself needs npm and the network, so it is opt-in. Everything that decides
WHAT it loads and HOW it reads the result is pure, and is pinned here on every run:
which blocks count as GOOD, how a fragment is made loadable, and what counts as a
load error. A wrong answer in any of these makes the opt-in run report green while
checking the wrong thing.
"""

import importlib.util
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent.parent


def _load():
    alias = "verify_examples_load_tests"
    spec = importlib.util.spec_from_file_location(alias, SKILL_DIR / "scripts" / "verify_examples_load.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[alias] = module  # dataclass + `from __future__ import annotations`
    spec.loader.exec_module(module)
    return module


V = _load()


class GoodExampleSelectionTests(unittest.TestCase):
    def skill(self, skill_md: str) -> Path:
        root = Path(tempfile.mkdtemp(prefix="e2e-skill-"))
        self.addCleanup(shutil.rmtree, root, True)
        (root / "SKILL.md").write_text(skill_md)
        (root / "references").mkdir()
        return root

    def bodies(self, skill_md: str) -> list[str]:
        return [e.body.strip() for e in V.good_examples(self.skill(skill_md))]

    def test_good_block_right_after_a_bad_block_is_selected(self) -> None:
        """The defect that hid the crashing example: the old selector looked for a BAD
        marker in the 200 characters before a fence, which always includes the BAD
        block a GOOD block is paired with."""
        md = "BAD:\n```ts\nbadCall();\n```\nGOOD:\n```ts\ngoodCall();\n```\n"
        self.assertEqual(["goodCall();"], self.bodies(md))

    def test_explanatory_prose_inside_a_good_block_does_not_exempt_it(self) -> None:
        md = "GOOD:\n```ts\n// falling back is wrong for CI, so throw\ngoodCall();\n```\n"
        self.assertEqual(1, len(self.bodies(md)))

    def test_unlabelled_block_is_a_recommendation(self) -> None:
        self.assertEqual(["call();"], self.bodies("### Pattern\n\n```ts\ncall();\n```\n"))

    def test_label_must_be_the_line_directly_before_the_fence(self) -> None:
        """A BAD block earlier in the section does not taint a later unlabelled one."""
        md = ("BAD:\n```ts\nbad();\n```\n\nThe fix keeps the flow intact.\n\n"
              "```ts\ngood();\n```\n")
        self.assertEqual(["good();"], self.bodies(md))

    def test_segments_inside_one_fence_are_classified_separately(self) -> None:
        md = ("```ts\n// WRONG — proxy signal\nbad();\n\n"
              "// CORRECT — assert the state\ngood();\n```\n")
        self.assertEqual(["// CORRECT — assert the state\ngood();"], self.bodies(md))

    def test_before_after_pair(self) -> None:
        md = "```ts\n// BEFORE (flaky)\nbad();\n\n// AFTER (stable)\ngood();\n```\n"
        self.assertEqual(["// AFTER (stable)\ngood();"], self.bodies(md))

    def test_non_typescript_blocks_are_ignored(self) -> None:
        self.assertEqual([], self.bodies("```bash\nnpx playwright test\n```\n"))

    def test_lines_point_at_the_example(self) -> None:
        md = "intro\n\n```ts\n// WRONG\nbad();\n// CORRECT\ngood();\n```\n"
        [ex] = V.good_examples(self.skill(md))
        self.assertEqual(6, ex.line)  # the `// CORRECT` line, 1-based

    def test_every_good_labelled_block_in_skill_md_is_selected(self) -> None:
        """Real corpus: each `GOOD:` block in SKILL.md is one selected example. Derived
        from the text, so adding an anti-example cannot silently fall outside."""
        text = (SKILL_DIR / "SKILL.md").read_text()
        labelled = len(re.findall(r"(?m)^GOOD:\n```ts$", text))
        selected = [e for e in V.good_examples() if e.source == "SKILL.md"]
        self.assertGreaterEqual(labelled, 7)
        self.assertEqual(labelled, len(selected))


class ClassifyTests(unittest.TestCase):
    def test_kinds(self) -> None:
        cases = {
            "await page.goto('/');": "fragment",
            "test.skip(!process.env.E2E_BASE_URL, 'x');\nawait page.goto('/');": "fragment",
            "test('t', async ({ page }) => {});": "module",
            "test.describe('g', () => {});": "module",
            "test.use({ storageState: 'a.json' });": "module",
            "import { test } from '@playwright/test';": "module",
            "export default defineConfig({});": "module",
            "export const test = base.extend({});": "module",
            "// playwright.config.ts\nuse: {\n  trace: 'on',\n}": "config",
            "projects: [\n  { name: 'chromium' },\n],": "config",
        }
        for body, want in cases.items():
            with self.subTest(body=body):
                self.assertEqual(want, V.classify(body))

    def test_sibling_file_dependencies_are_skipped(self) -> None:
        for body in ("import { test } from './fixtures';",
                     "export default defineConfig({ globalSetup: require.resolve('./global-setup') });",
                     "const h = require('../helpers');"):
            with self.subTest(body=body):
                self.assertTrue(V.classify(body).startswith("skip:"))


class BuildSpecTests(unittest.TestCase):
    def test_fragment_is_wrapped_in_a_test_body_with_imports(self) -> None:
        spec = V.build_spec("await expect(page.getByText('x')).toBeVisible();", "fragment")
        self.assertTrue(spec.startswith('import { test, expect } from "@playwright/test";'))
        self.assertIn('test("example", async ({ page, request, context, browser, baseURL }) => {', spec)

    def test_config_fragment_is_wrapped_in_define_config(self) -> None:
        spec = V.build_spec("use: { trace: 'on' },", "config")
        self.assertIn("export default defineConfig({", spec)
        self.assertIn('import { defineConfig } from "@playwright/test";', spec)

    def test_a_module_with_its_own_import_is_left_alone(self) -> None:
        body = "import { test, expect } from '@playwright/test';\ntest('t', async () => {});"
        self.assertEqual(body + "\n", V.build_spec(body, "module"))

    def test_declared_test_is_not_imported_again_but_base_is(self) -> None:
        spec = V.build_spec("export const test = base.extend({});", "module")
        self.assertEqual('import { test as base } from "@playwright/test";', spec.split("\n")[0])

    def test_only_used_names_are_imported(self) -> None:
        spec = V.build_spec("test('t', async () => {});", "module")
        self.assertEqual('import { test } from "@playwright/test";', spec.split("\n")[0])


class LoadErrorTests(unittest.TestCase):
    def test_no_tests_found_alone_is_not_an_error(self) -> None:
        self.assertIsNone(V.load_error("Error: No tests found.\nMake sure that arguments are regular expressions"))

    def test_real_error_wins_over_the_no_tests_line_that_follows_it(self) -> None:
        out = ("Error: test.info() can only be called while test is running\n\n"
               "   at a.spec.ts:2\nError: No tests found.\n")
        self.assertEqual("Error: test.info() can only be called while test is running", V.load_error(out))

    def test_typed_errors_are_errors(self) -> None:
        for line in ("SyntaxError: await is only valid in async functions",
                     "ReferenceError: defineConfig is not defined",
                     "TypeError: Duplicate declaration \"test\""):
            with self.subTest(line=line):
                self.assertEqual(line, V.load_error(f"noise\n  {line}\nmore"))

    def test_clean_listing(self) -> None:
        self.assertIsNone(V.load_error("Listing tests:\n  a.spec.ts:2:5 › t\nTotal: 1 test in 1 file"))


class PackageTests(unittest.TestCase):
    def test_third_party_packages(self) -> None:
        examples = [V.Example("x", 1, "import AxeBuilder from '@axe-core/playwright';\n"
                                      "import { test } from '@playwright/test';\n"
                                      "import fs from 'node:fs';\nimport { z } from 'zod/v4';")]
        self.assertEqual(["@axe-core/playwright", "zod"], V.third_party_packages(examples))


if __name__ == "__main__":
    unittest.main()
