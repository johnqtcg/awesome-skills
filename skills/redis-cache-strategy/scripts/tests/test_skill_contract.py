"""Contract tests for redis-cache-strategy skill."""

import pathlib
import pytest

SKILL_DIR = pathlib.Path(__file__).resolve().parents[2]
SKILL_MD = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
REFS_DIR = SKILL_DIR / "references"


def _ref(name: str) -> str:
    return (REFS_DIR / name).read_text(encoding="utf-8")


class TestFrontmatter:
    def test_name(self):
        assert "name: redis-cache-strategy" in SKILL_MD

    def test_description_keywords(self):
        desc_area = SKILL_MD[:800].lower()
        for kw in ["cache-aside", "write-through", "ttl", "stampede", "penetration",
                    "avalanche", "hot key", "consistency"]:
            assert kw in desc_area, f"description missing keyword: {kw}"


class TestMandatoryGates:
    def test_gate_1_context(self):
        assert "Gate 1" in SKILL_MD
        lower = SKILL_MD.lower()
        assert "redis version" in lower
        assert "maxmemory" in lower
        assert "eviction" in lower

    def test_gate_1_stop_proceed(self):
        assert "**STOP**" in SKILL_MD
        assert "**PROCEED**" in SKILL_MD

    def test_gate_2_scope(self):
        assert "Gate 2" in SKILL_MD
        for mode in ["review", "design", "troubleshoot"]:
            assert mode in SKILL_MD.lower()

    def test_gate_3_risk(self):
        assert "Gate 3" in SKILL_MD
        for risk in ["SAFE", "WARN", "UNSAFE"]:
            assert risk in SKILL_MD

    def test_gate_4_completeness(self):
        assert "Gate 4" in SKILL_MD

    def test_all_gates_have_stop(self):
        stop_count = SKILL_MD.count("**STOP**")
        assert stop_count >= 3


class TestDepthSelection:
    def test_three_depths(self):
        for depth in ["Lite", "Standard", "Deep"]:
            assert depth in SKILL_MD

    def test_force_standard_signals(self):
        lower = SKILL_MD.lower()
        for signal in ["write-behind", "distributed lock", "hot key"]:
            assert signal in lower, f"missing signal: {signal}"

    def test_reference_loading_by_depth(self):
        assert "cache-patterns.md" in SKILL_MD
        assert "cache-failure-modes.md" in SKILL_MD


class TestDegradationModes:
    def test_four_modes_defined(self):
        for mode in ["Full", "Degraded", "Minimal", "Planning"]:
            assert mode in SKILL_MD

    def test_never_fabricate(self):
        lower = SKILL_MD.lower()
        assert "never" in lower and ("fabricate" in lower or "claim" in lower)

    def test_consistency_sla_warning(self):
        lower = SKILL_MD.lower()
        assert "staleness" in lower or "consistency" in lower


class TestCacheStrategyChecklist:
    def test_subsection_count(self):
        for sub in ["5.1", "5.2", "5.3", "5.4"]:
            assert sub in SKILL_MD

    def test_pattern_keywords(self):
        for kw in ["cache-aside", "write-through", "write-behind"]:
            assert kw in SKILL_MD.lower()

    def test_ttl_jitter(self):
        lower = SKILL_MD.lower()
        assert "ttl" in lower and "jitter" in lower

    def test_stampede(self):
        lower = SKILL_MD.lower()
        assert "stampede" in lower and "singleflight" in lower

    def test_penetration(self):
        lower = SKILL_MD.lower()
        assert "penetration" in lower and ("bloom" in lower or "null" in lower)

    def test_distributed_lock(self):
        lower = SKILL_MD.lower()
        assert "setnx" in lower or "distributed lock" in lower

    def test_degradation(self):
        lower = SKILL_MD.lower()
        assert "cache-down" in lower or "degradation" in lower


class TestPatternSelection:
    def test_selection_table(self):
        lower = SKILL_MD.lower()
        assert "cache-aside" in lower and "write-through" in lower and "write-behind" in lower

    def test_warmup(self):
        lower = SKILL_MD.lower()
        assert "warmup" in lower or "warm" in lower


class TestAntiExamples:
    def test_min_count(self):
        ae_count = sum(1 for line in SKILL_MD.split("\n") if line.strip().startswith("### AE-"))
        assert ae_count >= 6

    def test_wrong_right_pairs(self):
        assert SKILL_MD.count("// WRONG") >= 5
        assert SKILL_MD.count("// RIGHT") >= 5

    def test_ttl_anti_example(self):
        lower = SKILL_MD.lower()
        assert "immortal" in lower or "no ttl" in lower

    def test_extended_ref(self):
        assert "cache-anti-examples.md" in SKILL_MD


class TestScorecard:
    def test_critical_tier(self):
        lower = SKILL_MD.lower()
        assert "critical" in lower
        assert "any fail" in lower or "any failure" in lower

    def test_standard_tier(self):
        assert "4 of 5" in SKILL_MD or "4/5" in SKILL_MD

    def test_hygiene_tier(self):
        assert "3 of 4" in SKILL_MD or "3/4" in SKILL_MD

    def test_critical_items(self):
        lower = SKILL_MD.lower()
        assert "consistency" in lower
        assert "ttl" in lower
        assert "degradation" in lower

    def test_verdict_format(self):
        assert "X/12" in SKILL_MD or "PASS/FAIL" in SKILL_MD


class TestOutputContract:
    def test_nine_sections(self):
        for section in ["9.1", "9.2", "9.3", "9.4", "9.5", "9.6", "9.7", "9.8", "9.9"]:
            assert section in SKILL_MD

    def test_uncovered_risks_mandatory(self):
        lower = SKILL_MD.lower()
        assert "never empty" in lower or "mandatory" in lower

    def test_volume_rules(self):
        assert "volume" in SKILL_MD.lower()

    def test_scorecard_in_output(self):
        lower = SKILL_MD.lower()
        assert "scorecard" in lower and "data basis" in lower


class TestReferenceFiles:
    def test_cache_patterns_exists(self):
        content = _ref("cache-patterns.md")
        assert len(content.splitlines()) >= 80

    def test_cache_patterns_keywords(self):
        content = _ref("cache-patterns.md").lower()
        for kw in ["cache-aside", "write-through", "write-behind", "dual-write"]:
            assert kw in content

    def test_failure_modes_exists(self):
        content = _ref("cache-failure-modes.md")
        assert len(content.splitlines()) >= 80

    def test_failure_modes_keywords(self):
        content = _ref("cache-failure-modes.md").lower()
        for kw in ["stampede", "penetration", "avalanche", "hot key"]:
            assert kw in content

    def test_anti_examples_exists(self):
        content = _ref("cache-anti-examples.md")
        assert len(content.splitlines()) >= 80

    def test_anti_examples_numbering(self):
        content = _ref("cache-anti-examples.md")
        assert "AE-7" in content
        ae_count = sum(1 for line in content.split("\n") if "## AE-" in line)
        assert ae_count >= 5

    def test_all_refs_mentioned_in_skill(self):
        for f in REFS_DIR.glob("*.md"):
            assert f.name in SKILL_MD, f"{f.name} not in SKILL.md"


class TestLineCount:
    def test_max_lines(self):
        lines = len(SKILL_MD.splitlines())
        assert lines <= 420, f"SKILL.md is {lines} lines (budget: 420)"


class TestCrossFileConsistency:
    def test_cache_aside_in_patterns(self):
        assert "cache-aside" in _ref("cache-patterns.md").lower()

    def test_singleflight_in_failure_modes(self):
        assert "singleflight" in _ref("cache-failure-modes.md").lower()

    def test_bloom_in_failure_modes(self):
        assert "bloom" in _ref("cache-failure-modes.md").lower()

    def test_ttl_jitter_in_failure_modes(self):
        content = _ref("cache-failure-modes.md").lower()
        assert "jitter" in content

    def test_keys_command_in_anti_examples(self):
        content = _ref("cache-anti-examples.md").lower()
        assert "keys" in content or "scan" in content

    def test_degradation_in_skill(self):
        assert "degradation" in SKILL_MD.lower()