#!/usr/bin/env python3
"""Contract tests for go-makefile-writer skill structure."""
import os
import unittest

SKILL_DIR = os.path.join(os.path.dirname(__file__), '..', '..')
SKILL_MD = os.path.join(SKILL_DIR, 'SKILL.md')
QUALITY_GUIDE = os.path.join(SKILL_DIR, 'references', 'makefile-quality-guide.md')
PR_CHECKLIST = os.path.join(SKILL_DIR, 'references', 'pr-checklist.md')
GOLDEN_SIMPLE = os.path.join(SKILL_DIR, 'references', 'golden', 'simple-project.mk')
GOLDEN_COMPLEX = os.path.join(SKILL_DIR, 'references', 'golden', 'complex-project.mk')
DISCOVERY_SCRIPT = os.path.join(SKILL_DIR, 'scripts', 'discover_go_entrypoints.sh')


def _read(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


class TestSkillMdStructure(unittest.TestCase):
    """Verify SKILL.md contains all required sections and references."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_MD)

    def test_has_workflow_section(self):
        self.assertIn('## Workflow', self.text)

    def test_workflow_has_four_steps(self):
        for step in ['1. **Inspect**', '2. **Plan**', '3. **Compose**', '4. **Validate**']:
            self.assertIn(step, self.text, f'Missing workflow step: {step}')

    def test_has_rules_section(self):
        self.assertIn('## Rules', self.text)

    def test_has_output_contract(self):
        self.assertIn('## Output Contract', self.text)

    def test_output_contract_items(self):
        output_contract = self.text.lower()
        for item in ['changed files', 'new/updated targets', 'deprecated/aliased targets',
                      'assumptions or missing tools', 'validation commands executed']:
            self.assertIn(item, output_contract, f'Output contract missing: {item}')

    def test_references_quality_guide(self):
        self.assertIn('makefile-quality-guide.md', self.text)

    def test_references_pr_checklist(self):
        self.assertIn('pr-checklist.md', self.text)

    def test_references_discovery_script(self):
        self.assertIn('discover_go_entrypoints.sh', self.text)

    def test_references_golden_examples(self):
        self.assertIn('golden/', self.text)

    def test_core_targets_listed(self):
        for target in ['help', 'fmt', 'tidy', 'test', 'cover', 'lint', 'clean']:
            self.assertIn(target, self.text, f'Core target missing from SKILL.md: {target}')

    def test_version_injection_mentioned(self):
        self.assertIn('-ldflags', self.text)

    def test_ci_target_mentioned(self):
        self.assertIn('ci', self.text)


class TestQualityGuideStructure(unittest.TestCase):
    """Verify quality guide completeness."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(QUALITY_GUIDE)

    def test_has_all_sections(self):
        for i in range(1, 16):
            self.assertRegex(self.text, rf'## {i}\.',
                             f'Missing section {i} in quality guide')

    def test_has_help_pattern(self):
        self.assertIn('awk', self.text)
        self.assertIn('MAKEFILE_LIST', self.text)

    def test_has_version_template(self):
        self.assertIn('VERSION', self.text)
        self.assertIn('COMMIT', self.text)
        self.assertIn('BUILD_TIME', self.text)
        self.assertIn('LDFLAGS', self.text)

    def test_has_antipatterns(self):
        self.assertIn('Anti-Patterns', self.text)

    def test_has_validation_matrix(self):
        self.assertIn('Validation Matrix', self.text)

    def test_has_backward_compatibility(self):
        self.assertIn('Backward Compatibility', self.text)

    def test_cover_check_not_fragile(self):
        self.assertNotIn("gsub(\"%\",\"\",$$3)", self.text,
                          'cover-check still uses fragile gsub pattern')

    def test_fmt_not_git_only(self):
        self.assertIn('go fmt ./...', self.text,
                       'fmt target should use go fmt ./... as primary')

    def test_cross_compile_not_hardcoded(self):
        self.assertIn('Multi-binary project', self.text,
                       'Cross-compile section should cover multi-binary')

    def test_compatibility_notes_present(self):
        self.assertIn('Compatibility note', self.text,
                       'Should have compatibility notes for portability')


class TestGoldenExamplesExist(unittest.TestCase):
    """Verify golden Makefile examples exist and are well-formed."""

    def _check_golden(self, path, label):
        self.assertTrue(os.path.isfile(path), f'{label} golden example missing')
        text = _read(path)
        self.assertIn('.DEFAULT_GOAL := help', text,
                       f'{label}: missing .DEFAULT_GOAL')
        self.assertIn('LDFLAGS', text, f'{label}: missing LDFLAGS')
        self.assertIn('.PHONY', text, f'{label}: missing .PHONY')
        self.assertIn('help:', text, f'{label}: missing help target')
        self.assertIn('build-', text, f'{label}: missing build targets')
        self.assertIn('test:', text, f'{label}: missing test target')
        self.assertIn('clean:', text, f'{label}: missing clean target')
        self.assertIn('-race', text, f'{label}: test missing -race')
        self.assertIn('version:', text, f'{label}: missing version target')
        self.assertIn('VERSION', text, f'{label}: missing VERSION variable')

    def test_simple_golden(self):
        self._check_golden(GOLDEN_SIMPLE, 'simple')

    def test_complex_golden(self):
        self._check_golden(GOLDEN_COMPLEX, 'complex')

    def test_complex_has_multi_binary(self):
        text = _read(GOLDEN_COMPLEX)
        self.assertIn('build-all:', text)
        self.assertIn('build-consumer-', text)
        self.assertIn('build-cron-', text)

    def test_complex_has_docker(self):
        text = _read(GOLDEN_COMPLEX)
        self.assertIn('docker-build:', text)

    def test_complex_has_generate(self):
        text = _read(GOLDEN_COMPLEX)
        self.assertIn('generate:', text)
        self.assertIn('generate-check:', text)

    def test_complex_has_cross_compile(self):
        text = _read(GOLDEN_COMPLEX)
        self.assertIn('CGO_ENABLED=0', text)
        self.assertIn('GOOS=linux', text)


class TestDiscoveryScriptExists(unittest.TestCase):
    """Verify discovery script exists and has required features."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(DISCOVERY_SCRIPT)

    def test_file_exists(self):
        self.assertTrue(os.path.isfile(DISCOVERY_SCRIPT))

    def test_is_executable(self):
        self.assertTrue(os.access(DISCOVERY_SCRIPT, os.X_OK))

    def test_outputs_target_name(self):
        self.assertIn('target_name', self.text)

    def test_supports_json_mode(self):
        self.assertIn('--json', self.text)

    def test_handles_known_kinds(self):
        for kind in ['api', 'consumer', 'cron', 'worker', 'migrate']:
            self.assertIn(kind, self.text, f'Discovery script missing kind: {kind}')


class TestPrChecklistExists(unittest.TestCase):

    def test_file_exists(self):
        self.assertTrue(os.path.isfile(PR_CHECKLIST),
                        'references/pr-checklist.md should exist')


if __name__ == '__main__':
    unittest.main()
