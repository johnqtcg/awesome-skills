#!/usr/bin/env python3
"""Golden review tests — verify skill docs cover all expected rules."""
import json
import os
import glob
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
        cls.all_docs = _load_all_docs()
        cls.fixtures = _load_fixtures()

    def test_all_rules_covered(self):
        for fix in self.fixtures:
            for rule in fix['coverage_rules']:
                self.assertIn(
                    rule, self.all_docs,
                    f'{fix["id"]} ({fix["title"]}): '
                    f'coverage rule "{rule}" not found in skill docs'
                )

    def test_reference_files_exist(self):
        for fix in self.fixtures:
            ref = fix['reference']
            path = os.path.join(SKILL_DIR, ref)
            self.assertTrue(os.path.isfile(path),
                            f'{fix["id"]}: reference {ref} does not exist')


if __name__ == '__main__':
    unittest.main()
