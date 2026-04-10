#!/usr/bin/env python3
"""Golden review tests — verify skill docs cover all expected rules."""
import json
import os
import glob
import re
import unittest

SKILL_DIR = os.path.join(os.path.dirname(__file__), '..', '..')
GOLDEN_DIR = os.path.join(os.path.dirname(__file__), 'golden')

REQUIRED_FIELDS = {'id', 'title', 'type', 'severity', 'makefile_snippet',
                   'expected_feedback', 'coverage_rules', 'reference'}


def _load_all_docs():
    """Load all skill text into a single string for searching."""
    parts = []
    for pattern in ['SKILL.md', 'references/*.md', 'references/golden/*.mk']:
        for path in glob.glob(os.path.join(SKILL_DIR, pattern)):
            with open(path, 'r', encoding='utf-8') as f:
                parts.append(f.read())
    return '\n'.join(parts)


def _load_fixtures():
    fixtures = []
    for path in sorted(glob.glob(os.path.join(GOLDEN_DIR, '*.json'))):
        with open(path, 'r', encoding='utf-8') as f:
            fixtures.append(json.load(f))
    return fixtures


def _normalize(text):
    """Normalize docs/rules for robust concept matching.

    Strips lightweight Markdown formatting and collapses whitespace so
    contract checks do not fail on case-only or backtick-only drift.
    """
    text = text.lower()
    text = re.sub(r"[`*_#]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


class TestFixtureIntegrity(unittest.TestCase):
    """Ensure golden fixtures are well-formed."""

    @classmethod
    def setUpClass(cls):
        cls.fixtures = _load_fixtures()

    def test_at_least_5_fixtures(self):
        self.assertGreaterEqual(len(self.fixtures), 5,
                                'Need at least 5 golden fixtures')

    def test_unique_ids(self):
        ids = [f['id'] for f in self.fixtures]
        self.assertEqual(len(ids), len(set(ids)), 'Duplicate fixture IDs')

    def test_required_fields(self):
        for fix in self.fixtures:
            missing = REQUIRED_FIELDS - set(fix.keys())
            self.assertFalse(missing,
                             f'{fix["id"]}: missing fields {missing}')

    def test_valid_types(self):
        for fix in self.fixtures:
            self.assertIn(fix['type'], ('defect', 'false_positive'),
                          f'{fix["id"]}: invalid type')

    def test_valid_severities(self):
        for fix in self.fixtures:
            self.assertIn(fix['severity'],
                          ('high', 'medium', 'low', 'none'),
                          f'{fix["id"]}: invalid severity')

    def test_has_at_least_one_false_positive(self):
        fps = [f for f in self.fixtures if f['type'] == 'false_positive']
        self.assertGreaterEqual(len(fps), 1,
                                'Need at least one false-positive fixture')


class TestRuleCoverage(unittest.TestCase):
    """Verify every fixture's coverage_rules appear in skill docs."""

    @classmethod
    def setUpClass(cls):
        cls.all_docs = _normalize(_load_all_docs())
        cls.fixtures = _load_fixtures()

    def test_all_rules_covered(self):
        for fix in self.fixtures:
            for rule in fix['coverage_rules']:
                self.assertIn(
                    _normalize(rule), self.all_docs,
                    f'{fix["id"]} ({fix["title"]}): '
                    f'coverage rule "{rule}" not found in skill docs'
                )

    def test_reference_files_exist(self):
        for fix in self.fixtures:
            ref = fix['reference']
            path = os.path.join(SKILL_DIR, ref)
            self.assertTrue(os.path.isfile(path),
                            f'{fix["id"]}: reference {ref} does not exist')


class TestMakefileDefectBehavior(unittest.TestCase):
    """Per-scenario behavioral verification — upgrade from bulk keyword loop.

    Each test method maps to one fixture and explicitly asserts:
    - Correct type (defect vs false_positive)
    - Correct severity for defects
    - Coverage rules present in docs
    - Anti-example patterns present for false-positives

    This mirrors security-review's TP/FP code-scenario approach.
    """

    @classmethod
    def setUpClass(cls):
        cls.all_docs = _normalize(_load_all_docs())

    def _load(self, filename):
        path = os.path.join(GOLDEN_DIR, filename)
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _assert_coverage(self, fix):
        for rule in fix.get('coverage_rules', []):
            self.assertIn(_normalize(rule), self.all_docs,
                          f'[{fix["id"]}] coverage rule not found: {rule!r}')

    def _assert_anti_patterns(self, fix):
        for pattern in fix.get('anti_example_patterns', []):
            self.assertIn(_normalize(pattern), self.all_docs,
                          f'[{fix["id"]}] anti-example pattern not found: {pattern!r}')

    # ------------------------------------------------------------------
    # True-positive (defect) cases
    # ------------------------------------------------------------------

    def test_001_missing_help_target(self):
        f = self._load('001_missing_help.json')
        self.assertEqual(f['type'], 'defect')
        self.assertEqual(f['severity'], 'high')
        self._assert_coverage(f)

    def test_002_test_missing_race(self):
        f = self._load('002_missing_race.json')
        self.assertEqual(f['type'], 'defect')
        self.assertEqual(f['severity'], 'high')
        self._assert_coverage(f)

    def test_003_build_without_ldflags(self):
        f = self._load('003_missing_ldflags.json')
        self.assertEqual(f['type'], 'defect')
        self.assertEqual(f['severity'], 'medium')
        self._assert_coverage(f)

    def test_004_missing_phony(self):
        f = self._load('004_no_phony.json')
        self.assertEqual(f['type'], 'defect')
        self.assertEqual(f['severity'], 'medium')
        self._assert_coverage(f)

    def test_005_cross_compile_no_cgo(self):
        f = self._load('005_cross_compile_with_cgo.json')
        self.assertEqual(f['type'], 'defect')
        self.assertEqual(f['severity'], 'high')
        self._assert_coverage(f)

    def test_006_target_name_mismatch(self):
        f = self._load('006_target_name_mismatch.json')
        self.assertEqual(f['type'], 'defect')
        self.assertEqual(f['severity'], 'low')
        self._assert_coverage(f)

    def test_007_unpinned_tool_versions(self):
        f = self._load('007_unpinned_tools.json')
        self.assertEqual(f['type'], 'defect')
        self.assertEqual(f['severity'], 'medium')
        self._assert_coverage(f)

    def test_012_ci_target_diverges(self):
        f = self._load('012_ci_target_diverges.json')
        self.assertEqual(f['type'], 'defect')
        self.assertEqual(f['severity'], 'high')
        self._assert_coverage(f)

    def test_013_refactor_rename_no_alias(self):
        f = self._load('013_refactor_rename_no_alias.json')
        self.assertEqual(f['type'], 'defect')
        self.assertEqual(f['severity'], 'medium')
        self.assertEqual(f.get('mode'), 'refactor')
        self._assert_coverage(f)

    def test_014_monorepo_missing_aggregates(self):
        f = self._load('014_monorepo_missing_aggregates.json')
        self.assertEqual(f['type'], 'defect')
        self.assertEqual(f['severity'], 'medium')
        self._assert_coverage(f)

    def test_015_tab_vs_space_recipes(self):
        f = self._load('015_tab_vs_space_recipes.json')
        self.assertEqual(f['type'], 'defect')
        self.assertEqual(f['severity'], 'high')
        self._assert_coverage(f)

    def test_016_missing_tidy_target(self):
        f = self._load('016_missing_tidy_target.json')
        self.assertEqual(f['type'], 'defect')
        self.assertEqual(f['severity'], 'low')
        self._assert_coverage(f)

    # ------------------------------------------------------------------
    # False-positive cases (acceptable patterns, no defect expected)
    # ------------------------------------------------------------------

    def test_008_well_formed_makefile_fp(self):
        """Well-formed Makefile: skill must NOT report defects."""
        f = self._load('008_good_makefile.json')
        self.assertEqual(f['type'], 'false_positive')
        self.assertEqual(f['severity'], 'none')
        self._assert_coverage(f)  # coverage_rules confirm why each pattern is correct

    def test_009_custom_help_format_fp(self):
        """Custom echo-based help is acceptable — must not flag as missing help."""
        f = self._load('009_custom_help_format_fp.json')
        self.assertEqual(f['type'], 'false_positive')
        self.assertEqual(f['severity'], 'none')
        self._assert_coverage(f)

    def test_010_gofmt_variant_fp(self):
        """gofmt -w is an acceptable fmt variant — must not flag as wrong."""
        f = self._load('010_gofmt_variant_fp.json')
        self.assertEqual(f['type'], 'false_positive')
        self.assertEqual(f['severity'], 'none')
        self._assert_coverage(f)

    def test_011_no_docker_targets_fp(self):
        """Absence of Docker targets without a Dockerfile is correct — must not flag."""
        f = self._load('011_no_docker_targets_fp.json')
        self.assertEqual(f['type'], 'false_positive')
        self.assertEqual(f['severity'], 'none')
        self._assert_coverage(f)


if __name__ == '__main__':
    unittest.main()
