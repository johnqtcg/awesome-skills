"""Contract tests for kafka-event-driven-design skill."""

import pathlib
import pytest

SKILL_DIR = pathlib.Path(__file__).resolve().parents[2]
SKILL_MD = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
REFS_DIR = SKILL_DIR / "references"


def _ref(name: str) -> str:
    return (REFS_DIR / name).read_text(encoding="utf-8")


class TestFrontmatter:
    def test_name(self):
        assert "name: kafka-event-driven-design" in SKILL_MD

    def test_description_keywords(self):
        desc = SKILL_MD[:800].lower()
        for kw in ["kafka", "partition", "consumer group", "schema", "idempotent",
                    "dead letter", "exactly-once"]:
            assert kw in desc, f"description missing keyword: {kw}"


class TestMandatoryGates:
    def test_gate_1_context(self):
        assert "Gate 1" in SKILL_MD
        lower = SKILL_MD.lower()
        assert "kafka version" in lower
        assert "ordering" in lower
        assert "delivery" in lower

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
        assert SKILL_MD.count("**STOP**") >= 3


class TestDepthSelection:
    def test_three_depths(self):
        for depth in ["Lite", "Standard", "Deep"]:
            assert depth in SKILL_MD

    def test_force_standard_signals(self):
        lower = SKILL_MD.lower()
        for signal in ["schema evolution", "exactly-once", "compacted"]:
            assert signal in lower, f"missing signal: {signal}"

    def test_reference_loading_by_depth(self):
        assert "event-schema-patterns.md" in SKILL_MD
        assert "consumer-failure-modes.md" in SKILL_MD


class TestDegradationModes:
    def test_four_modes_defined(self):
        for mode in ["Full", "Degraded", "Minimal", "Planning"]:
            assert mode in SKILL_MD

    def test_never_fabricate(self):
        lower = SKILL_MD.lower()
        assert "never" in lower and ("claim" in lower or "fabricate" in lower)

    def test_delivery_guarantee_warning(self):
        lower = SKILL_MD.lower()
        assert "exactly-once" in lower and "verify" in lower


class TestDesignChecklist:
    def test_subsection_count(self):
        for sub in ["5.1", "5.2", "5.3", "5.4"]:
            assert sub in SKILL_MD

    def test_acks_all(self):
        assert "acks=all" in SKILL_MD or "acks = all" in SKILL_MD

    def test_idempotent(self):
        assert "idempotent" in SKILL_MD.lower() or "idempotence" in SKILL_MD.lower()

    def test_dlq(self):
        lower = SKILL_MD.lower()
        assert "dead letter" in lower or "dlq" in lower

    def test_partition_key(self):
        assert "partition key" in SKILL_MD.lower()

    def test_schema_registry(self):
        assert "Schema Registry" in SKILL_MD

    def test_consumer_lag(self):
        assert "consumer lag" in SKILL_MD.lower() or "consumer_lag" in SKILL_MD


class TestPartitionDesign:
    def test_ordering_table(self):
        lower = SKILL_MD.lower()
        assert "per-entity" in lower or "per-order" in lower

    def test_hot_partition(self):
        lower = SKILL_MD.lower()
        assert "hot partition" in lower or "skewed" in lower


class TestAntiExamples:
    def test_min_count(self):
        ae_count = sum(1 for l in SKILL_MD.split("\n") if l.strip().startswith("### AE-"))
        assert ae_count >= 6

    def test_wrong_right_pairs(self):
        assert SKILL_MD.count("// WRONG") >= 5
        assert SKILL_MD.count("// RIGHT") >= 5

    def test_acks_anti_example(self):
        assert "acks=1" in SKILL_MD or "WaitForLocal" in SKILL_MD

    def test_extended_ref(self):
        assert "consumer-anti-examples.md" in SKILL_MD


class TestScorecard:
    def test_critical_tier(self):
        lower = SKILL_MD.lower()
        assert "critical" in lower
        assert "any fail" in lower

    def test_standard_tier(self):
        assert "4 of 5" in SKILL_MD or "4/5" in SKILL_MD

    def test_hygiene_tier(self):
        assert "3 of 4" in SKILL_MD or "3/4" in SKILL_MD

    def test_critical_items(self):
        lower = SKILL_MD.lower()
        assert "acks" in lower
        assert "idempoten" in lower
        assert "dead letter" in lower or "dlq" in lower

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
    def test_schema_patterns_exists(self):
        content = _ref("event-schema-patterns.md")
        assert len(content.splitlines()) >= 80

    def test_schema_patterns_keywords(self):
        content = _ref("event-schema-patterns.md").lower()
        for kw in ["avro", "protobuf", "backward", "event_id", "outbox"]:
            assert kw in content

    def test_failure_modes_exists(self):
        content = _ref("consumer-failure-modes.md")
        assert len(content.splitlines()) >= 80

    def test_failure_modes_keywords(self):
        content = _ref("consumer-failure-modes.md").lower()
        for kw in ["rebalance", "poison", "lag", "duplicate", "ordering"]:
            assert kw in content

    def test_anti_examples_exists(self):
        content = _ref("consumer-anti-examples.md")
        assert len(content.splitlines()) >= 80

    def test_anti_examples_numbering(self):
        content = _ref("consumer-anti-examples.md")
        assert "AE-7" in content
        ae_count = sum(1 for l in content.split("\n") if "## AE-" in l)
        assert ae_count >= 5

    def test_all_refs_mentioned_in_skill(self):
        for f in REFS_DIR.glob("*.md"):
            assert f.name in SKILL_MD, f"{f.name} not in SKILL.md"


class TestLineCount:
    def test_max_lines(self):
        lines = len(SKILL_MD.splitlines())
        assert lines <= 420, f"SKILL.md is {lines} lines (budget: 420)"


class TestCrossFileConsistency:
    def test_avro_in_schema_patterns(self):
        assert "Avro" in _ref("event-schema-patterns.md")

    def test_dlq_in_failure_modes(self):
        content = _ref("consumer-failure-modes.md").lower()
        assert "dead letter" in content or "dlq" in content

    def test_rebalance_in_failure_modes(self):
        assert "rebalance" in _ref("consumer-failure-modes.md").lower()

    def test_partition_key_in_skill(self):
        assert "partition key" in SKILL_MD.lower()

    def test_outbox_in_schema_patterns(self):
        assert "outbox" in _ref("event-schema-patterns.md").lower()

    def test_auto_commit_in_anti_examples(self):
        content = _ref("consumer-anti-examples.md").lower()
        assert "auto" in content and "commit" in content