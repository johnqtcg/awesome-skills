"""Contract tests for the api-design skill.

Guards here are **section-scoped**. A whole-document `assert "x" in SKILL_MD`
fails open: it passes when the string exists anywhere, including in a section
where its presence proves nothing. Where a test asserts that something belongs
to a particular tier or gate, it parses that block and checks the block.
"""

import importlib.util
import pathlib
import re
import sys

SKILL_DIR = pathlib.Path(__file__).resolve().parents[2]
SKILL_MD = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
REFS_DIR = SKILL_DIR / "references"

# SKILL.md line budget. Kept above the current size with real headroom so a
# genuine addition does not have to fight the gate, while runaway growth still
# trips it.
# Raised from 440 deliberately: the nature/severity split added the §8.1 decision
# table, a force column on the status-code table, and the error-invariants vs
# default-shape split. Each removes a class of false positive, so the size buys
# precision rather than prose.
LINE_BUDGET = 500


def _load_linter():
    spec = importlib.util.spec_from_file_location(
        "lint_api_doc", SKILL_DIR / "scripts" / "lint_api_doc.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["lint_api_doc"] = module
    spec.loader.exec_module(module)
    return module


LINT = _load_linter()


def _ref(name: str) -> str:
    return (REFS_DIR / name).read_text(encoding="utf-8")


def _section(needle: str) -> str:
    body = LINT.find_section(SKILL_MD, needle)
    assert body, f"section matching {needle!r} not found in SKILL.md"
    return body


def _gate(number: int) -> str:
    body = LINT.find_section(_section("Mandatory Gates"), f"Gate {number}", "### ")
    assert body, f"Gate {number} not found"
    return body


class TestFrontmatter:
    def test_name(self):
        assert "name: api-design" in SKILL_MD

    def test_description_keywords(self):
        desc = SKILL_MD[:800].lower()
        for kw in ["rest", "endpoint", "status code", "error model", "idempotency",
                   "pagination", "idor", "openapi"]:
            assert kw in desc, f"description missing keyword: {kw}"


class TestRuleForceClasses:
    """The tiering that stops a convention being reported like a vulnerability."""

    def test_section_exists(self):
        assert _section("Rule Nature")

    def test_three_natures_defined(self):
        body = _section("Rule Nature")
        for tag in ("[P]", "[D]", "[C]"):
            assert tag in body, f"nature {tag} not defined"
        for word in ("Invariant", "Convention", "Policy"):
            assert word in body
        assert "[S]" not in body, \
            "[S] conflated nature with severity and was removed; triggers are §2.2"

    def test_nature_tags_match_the_linter(self):
        body = _section("Rule Nature")
        declared = {m for m in re.findall(r"\*\*\[([A-Z])\]\*\*", body)}
        assert declared == set(LINT.FORCE_TAGS), \
            f"SKILL.md declares {sorted(declared)}, linter allows {sorted(LINT.FORCE_TAGS)}"

    def test_severity_is_not_defined_in_section_2(self):
        assert not [f for f in LINT.lint(SKILL_DIR) if f.rule == "AD014"]

    def test_triggers_apply_to_any_nature(self):
        body = _section("Rule Nature")
        assert re.search(r"[Aa]dds an obligation", body), \
            "a trigger must be allowed to add an obligation to a [P] rule"
        assert re.search(r"never lowers an obligation", body)

    def test_contextual_choice_is_never_a_finding(self):
        body = _section("Rule Nature").lower()
        assert "is never a finding" in body or "never" in body
        assert "was my preferred option chosen" in body, \
            "the [C] rule must state that it judges whether a policy exists, not which"

    def test_risk_triggers_enumerated(self):
        body = _section("Rule Nature")
        triggers = re.findall(r"^\|\s*\*\*(T\d)\*\*\s*\|", body, re.MULTILINE)
        assert len(triggers) >= 5, f"only {len(triggers)} risk triggers defined"
        assert triggers == sorted(triggers), "trigger ids must be ordered"

    def test_every_trigger_is_declared_and_bound(self):
        """AD017 owns this: a trigger defined but declared by no rule reads as
        coverage while binding nothing, and a rule that reasons about a trigger it
        never declares leaves the §8.1 trigger column unscoped."""
        assert not [f for f in LINT.lint(SKILL_DIR) if f.rule == "AD017"]

    def test_severity_table_scopes_triggers_to_the_rule(self):
        body = _section("Scorecard")
        assert "Applicable trigger live" in body, \
            "an unscoped 'Live trigger' column lets any live trigger escalate any rule"
        assert re.search(r"declares", _section("Scorecard")), \
            "the table must say the trigger has to be declared by the rule itself"


class TestMandatoryGates:
    def test_four_gates_present(self):
        for n in (1, 2, 3, 4):
            assert _gate(n)

    def test_gate_1_classifies_scope(self):
        body = _gate(1)
        for mode in ("review", "design", "governance"):
            assert mode in body.lower(), f"Gate 1 must define the {mode} mode"

    def test_gate_2_covers_consumer_context(self):
        body = _gate(2).lower()
        assert "consume" in body
        assert "public" in body and "internal" in body

    def test_gate_2_stop_is_mode_conditional(self):
        """The original skill stopped on an unknown consumer while §5 told the
        model to degrade and continue. Only one of those can be right."""
        body = _gate(2)
        assert "STOP" in body and "PROCEED" in body
        assert re.search(r"design.*governance", body, re.IGNORECASE), \
            "Gate 2 must name the modes in which an unknown consumer stops the review"
        assert re.search(r"review.*(minimal|degrad)", body, re.IGNORECASE | re.DOTALL), \
            "Gate 2 must say review mode degrades instead of stopping"

    def test_gate_3_risk_levels(self):
        body = _gate(3)
        for risk in ("SAFE", "WARN", "UNSAFE"):
            assert risk in body

    def test_gate_4_checks_output(self):
        assert "9.9" in _gate(4)

    def test_every_gate_has_a_stop(self):
        for n in (1, 2, 3):
            assert "STOP" in _gate(n), f"Gate {n} has no STOP condition"


class TestDepthSelection:
    def test_three_depths(self):
        body = _section("Depth Selection")
        for depth in ("Lite", "Standard", "Deep"):
            assert depth in body

    def test_force_standard_signals(self):
        body = _section("Depth Selection").lower()
        for signal in ("pagination", "idempotency", "breaking change"):
            assert signal in body, f"missing force-Standard signal: {signal}"

    def test_risk_trigger_forces_standard(self):
        assert re.search(r"T1\D{0,4}T6", _section("Depth Selection")), \
            "any risk trigger must force Standard depth or higher"

    def test_reference_loading_by_depth(self):
        assert "error-model-patterns.md" in SKILL_MD
        assert "compatibility-rules.md" in SKILL_MD


class TestDegradationModes:
    def test_four_modes_defined(self):
        body = _section("Degradation Modes")
        for mode in ("Full", "Degraded", "Minimal", "Planning"):
            assert mode in body

    def test_never_fabricate(self):
        body = _section("Degradation Modes").lower()
        assert "never" in body and ("claim" in body or "guess" in body)

    def test_unassessed_items_are_na_not_fail(self):
        body = _section("Degradation Modes")
        assert re.search(r"N/A.{0,40}never.{0,10}`?FAIL", body, re.IGNORECASE | re.DOTALL), \
            "a rule that could not be assessed must score N/A, never FAIL"

    def test_assumptions_documented(self):
        assert "9.9" in _section("Degradation Modes")


class TestDesignChecklist:
    def test_four_subsections(self):
        body = _section("Design Checklist")
        for sub in ("6.1", "6.2", "6.3", "6.4"):
            assert sub in body

    def test_every_item_is_tagged_and_mapped(self):
        items, _ = LINT._checklist_items(SKILL_MD)
        assert len(items) >= 12, f"only {len(items)} checklist items parsed"
        for num, tag, title, target in items:
            assert tag in ("P", "S", "D", "C"), f"item {num}: bad tag {tag}"
            assert target, f"item {num} ({title}) has no scorecard mapping"

    def test_resource_naming_is_a_default_not_a_protocol_rule(self):
        items, _ = LINT._checklist_items(SKILL_MD)
        naming = [i for i in items if "naming" in i[2].lower()]
        assert naming, "no resource-naming rule found"
        for num, tag, title, _ in naming:
            assert tag in ("D", "C"), \
                f"item {num} ({title}) is tagged [{tag}]; naming is a convention"

    def test_object_level_authorization_is_protocol_grade(self):
        items, _ = LINT._checklist_items(SKILL_MD)
        authz = [i for i in items if "authorization" in i[2].lower()]
        assert authz, "no object-level authorization rule found"
        assert all(tag == "P" for _, tag, _, _ in authz)

    def test_status_codes(self):
        body = _section("Design Checklist")
        for code in ("201", "202", "204", "400", "401", "403", "404",
                     "409", "410", "412", "422", "429", "500"):
            assert code in body, f"status code {code} not covered in the checklist"

    def test_401_403_distinction_is_stated(self):
        body = _section("Design Checklist")
        assert re.search(r"401.{0,200}403", body, re.DOTALL)
        assert "re-login" in body.lower()

    def test_error_model(self):
        body = _section("Design Checklist").lower()
        assert "machine-parseable" in body or "machine-identifiable" in body

    def test_error_shape_is_not_an_invariant(self):
        """A consistent RFC 9457 API must not fail the Critical error item."""
        body = _section("Design Checklist")
        assert "RFC 9457" in body
        items, _ = LINT._checklist_items(SKILL_MD)
        envelope = [i for i in items if "envelope" in i[2].lower()]
        assert envelope, "no error-envelope rule found"
        for num, tag, title, target in envelope:
            assert tag == "D", f"item {num} ({title}) is [{tag}]; field names are a convention"
            assert target == "—", f"item {num} must not feed a scorecard item"

    def test_optional_spec_companions_not_mandatory(self):
        assert not [f for f in LINT.lint(SKILL_DIR) if f.rule == "AD016"]

    def test_idempotency_is_a_policy_with_a_trigger(self):
        items, _ = LINT._checklist_items(SKILL_MD)
        retry = [i for i in items if "retry-safety" in i[2].lower()]
        assert retry, "no retry-safety rule found"
        assert all(tag == "C" for _, tag, _, _ in retry), \
            "retry safety is a policy choice; the trigger sets its severity"
        body = _section("Design Checklist")
        assert re.search(r"T1/T2/T3.{0,80}FAIL", body, re.DOTALL), \
            "the rule must state which triggers make an unstated policy a FAIL"

    def test_idempotency_key_details_present(self):
        body = _section("Design Checklist")
        assert "Idempotency-Key" in body
        assert "fingerprint" in body.lower() and "scope" in body.lower()

    def test_concurrency_control_is_contextual(self):
        items, _ = LINT._checklist_items(SKILL_MD)
        conflict = [i for i in items if "write-conflict" in i[2].lower()]
        assert conflict, "no write-conflict rule found"
        assert all(tag in ("C", "S") for _, tag, _, _ in conflict), \
            "ETag vs last-write-wins is a policy choice, not a mandate"

    def test_pagination(self):
        body = _section("Design Checklist").lower()
        assert "cursor" in body and "offset" in body

    def test_stable_sort(self):
        body = _section("Design Checklist").lower()
        assert "stable" in body and "tie-breaker" in body

    def test_observability_is_kept_out_of_the_client_contract(self):
        """Inverted from the original test, which merely required the words
        'metric' and 'audit' to appear — satisfied by recommending them."""
        body = _section("Design Checklist")
        assert re.search(r"metric names.{0,120}(logs|audit sink)", body, re.DOTALL), \
            "metric/audit data must be routed to logs, not the error body"
        assert not [f for f in LINT.lint(SKILL_DIR) if f.rule == "AD004"]

    def test_health_check(self):
        body = _section("Design Checklist").lower()
        assert "healthz" in body or "health check" in body

    def test_middleware_ordering(self):
        body = _section("Design Checklist").lower()
        assert "middleware" in body and "order" in body


class TestAntiExamples:
    def test_min_count(self):
        body = _section("Anti-Examples")
        ae_count = sum(1 for l in body.split("\n") if l.strip().startswith("### AE-"))
        assert ae_count >= 6

    def test_wrong_right_pairs(self):
        body = _section("Anti-Examples")
        assert body.count("WRONG") >= 5
        assert body.count("RIGHT") >= 5

    def test_verb_anti_example(self):
        assert "createUser" in _section("Anti-Examples")

    def test_idempotency_anti_example_names_its_trigger(self):
        body = LINT.find_section(_section("Anti-Examples"), "AE-4", "### ")
        assert re.search(r"T1", body), \
            "AE-4 must state the risk trigger that makes idempotency binding"

    def test_idor_anti_example_separates_check_from_status(self):
        body = LINT.find_section(_section("Anti-Examples"), "AE-5", "### ")
        assert "403" in body and "404" in body
        assert "policy choice" in body.lower() or "separate" in body.lower()

    def test_extended_ref(self):
        assert "api-anti-examples.md" in SKILL_MD


class TestScorecard:
    def _tier(self, name: str) -> str:
        body = LINT.find_section(_section("Scorecard"), name, "### ")
        assert body, f"{name} tier not found"
        return body

    def test_three_tiers_parsed(self):
        tiers = LINT._scorecard_tiers(SKILL_MD)
        assert set(tiers) == {"Critical", "Standard", "Hygiene"}
        assert [len(tiers[k]) for k in ("Critical", "Standard", "Hygiene")] == [3, 5, 4]

    def test_critical_tier_is_any_fail(self):
        heading = next(l for l in _section("Scorecard").splitlines()
                       if l.startswith("### Critical"))
        assert "any FAIL" in heading

    def test_standard_threshold(self):
        assert "4 of 5" in _section("Scorecard") or "4/5" in _section("Scorecard")

    def test_hygiene_threshold(self):
        assert "3 of 4" in _section("Scorecard") or "3/4" in _section("Scorecard")

    def test_critical_tier_holds_security_items(self):
        body = self._tier("Critical").lower()
        assert "object-level authorization" in body
        assert "non-2xx" in body and "discriminator" in body, \
            "C2 must be stated as format-agnostic invariants, not one envelope shape"

    def test_naming_is_not_critical(self):
        """The original scorecard put /createUser at the same tier as IDOR."""
        critical = self._tier("Critical").lower()
        for cosmetic in ("naming", "kebab-case", "plural"):
            assert cosmetic not in critical, \
                f"{cosmetic!r} must not gate the review alongside authorization defects"

    def test_naming_is_scored_as_hygiene(self):
        tiers = LINT._scorecard_tiers(SKILL_MD)
        hygiene = self._tier("Hygiene").lower()
        assert "naming" in hygiene
        assert "H1" in tiers["Hygiene"]

    def test_verdict_counts_match_the_tiers(self):
        """Duplicate of linter AD009: hand-written totals drift from the lists."""
        assert not [f for f in LINT.lint(SKILL_DIR) if f.rule == "AD009"]

    def _severity_rows(self):
        """Parse §8.1 as data. A regex over prose breaks on rewording while still
        passing on an inverted meaning; the table is the contract."""
        rows = []
        for line in _section("Scorecard").splitlines():
            m = re.match(r"^\|\s*\*\*\[([A-Z])\]\*\*\s*\|([^|]+)\|([^|]+)\|([^|]+)\|",
                         line)
            if m:
                rows.append((m.group(1), m.group(2).strip(),
                             m.group(3).strip().strip("*"), m.group(4).strip().strip("*")))
        assert rows, "§8.1 severity table not parsed"
        return rows

    def test_severity_table_covers_every_nature(self):
        natures = {r[0] for r in self._severity_rows()}
        assert natures == set(LINT.FORCE_TAGS), \
            f"severity table covers {sorted(natures)}, natures are {sorted(LINT.FORCE_TAGS)}"

    def test_invariant_violation_always_fails(self):
        for nature, cond, no_trig, trig in self._severity_rows():
            if nature == "P":
                assert no_trig.startswith("FAIL") and trig.startswith("FAIL"), \
                    f"[P] row {cond!r} does not fail in both columns"

    def test_disagreeing_with_a_stated_policy_is_never_a_finding(self):
        rows = [r for r in self._severity_rows() if r[0] == "C"]
        passing = [r for r in rows if r[2].startswith("PASS") and r[3].startswith("PASS")]
        assert passing, "no [C] row where a stated policy passes under a live trigger"
        assert any("chosen differently" in r[1] or "stated" in r[1] for r in passing)

    def test_contextual_silence_escalates_only_with_a_trigger(self):
        rows = [r for r in self._severity_rows()
                if r[0] == "C" and "no policy" in r[1].lower()]
        assert rows, "no [C] row for an unstated policy"
        for _, cond, no_trig, trig in rows:
            assert no_trig.startswith("WARN"), f"{cond!r} should WARN without a trigger"
            assert trig.startswith("FAIL"), f"{cond!r} should FAIL under a trigger"

    def test_consistent_documented_convention_passes(self):
        rows = [r for r in self._severity_rows() if r[0] == "D"]
        assert any(r[2].startswith("PASS") for r in rows), \
            "a consistent, stated alternative convention must be able to PASS"
        assert any(r[2].startswith("WARN") for r in rows), \
            "an unexplained convention deviation must still be reportable"

    def test_no_contextual_rule_gates_a_critical_item(self):
        assert not [f for f in LINT.lint(SKILL_DIR) if f.rule == "AD010"]

    def test_report_only_rules_are_declared(self):
        body = _section("Scorecard").lower()
        assert "report-only" in body or "never scored" in body

    def test_na_items_leave_the_denominator(self):
        assert "N/A" in _section("Scorecard")


class TestOutputContract:
    def test_nine_sections(self):
        body = _section("Output Contract")
        for n in range(1, 10):
            assert f"9.{n}" in body, f"output section 9.{n} missing"

    def test_uncovered_risks_mandatory(self):
        body = _section("Output Contract").lower()
        assert "never empty" in body or "mandatory" in body

    def test_findings_carry_their_force_tag(self):
        body = _section("Output Contract")
        assert re.search(r"\[P\|D\|C\]", body), \
            "a finding must show its nature tag so the reader can triage it"
        assert "trigger" in body.lower(), \
            "a finding must name the live triggers, since they set severity"

    def test_volume_rules(self):
        assert "Volume" in _section("Output Contract")

    def test_scorecard_summary_reports_triggers_and_basis(self):
        body = _section("Output Contract").lower()
        assert "scorecard" in body
        assert "data basis" in body
        assert "risk trigger" in body


class TestReferenceFiles:
    def test_error_model_exists(self):
        assert len(_ref("error-model-patterns.md").splitlines()) >= 80

    def test_error_model_keywords(self):
        content = _ref("error-model-patterns.md").lower()
        for kw in ("validation_error", "not_found", "trace_id", "idempotency"):
            assert kw in content

    def test_compatibility_exists(self):
        assert len(_ref("compatibility-rules.md").splitlines()) >= 80

    def test_compatibility_keywords(self):
        content = _ref("compatibility-rules.md").lower()
        for kw in ("breaking", "non-breaking", "deprecation", "sunset"):
            assert kw in content

    def test_anti_examples_exists(self):
        assert len(_ref("api-anti-examples.md").splitlines()) >= 80

    def test_anti_examples_numbering(self):
        content = _ref("api-anti-examples.md")
        assert "AE-7" in content and "AE-14" in content
        ae_count = sum(1 for l in content.split("\n") if l.startswith("## AE-"))
        assert ae_count >= 5

    def test_all_refs_mentioned_in_skill(self):
        for f in REFS_DIR.glob("*.md"):
            assert f.name in SKILL_MD, f"{f.name} not in SKILL.md"


class TestLineCount:
    def test_max_lines(self):
        lines = len(SKILL_MD.splitlines())
        assert lines <= LINE_BUDGET, f"SKILL.md is {lines} lines (budget: {LINE_BUDGET})"

    def test_budget_has_headroom(self):
        """A budget the file already hugs is not a budget."""
        lines = len(SKILL_MD.splitlines())
        assert LINE_BUDGET - lines >= 25, \
            f"only {LINE_BUDGET - lines} lines of headroom; raise the budget deliberately"


class TestCrossFileConsistency:
    def test_validation_error_in_error_model(self):
        assert "validation_error" in _ref("error-model-patterns.md")

    def test_sunset_attributed_to_rfc_8594(self):
        content = _ref("compatibility-rules.md")
        assert "RFC 8594" in content
        assert "RFC 7231" not in content, "RFC 7231 is obsoleted by RFC 9110"

    def test_deprecation_uses_structured_field_date(self):
        content = _ref("compatibility-rules.md")
        assert "RFC 9745" in content
        assert re.search(r"Deprecation:\s*@\d+", content), \
            "the documented example must use the Structured Field Date form"

    def test_denial_status_presented_as_a_choice_in_both_files(self):
        for name in ("error-model-patterns.md", "api-anti-examples.md"):
            content = _ref(name)
            assert "403" in content and "404" in content, name
            assert re.search(r"or\s+404|either|both", content, re.IGNORECASE), name

    def test_field_order_cites_rfc_8259_everywhere_it_is_discussed(self):
        for name in ("compatibility-rules.md", "api-anti-examples.md"):
            assert "RFC 8259" in _ref(name), name
        assert "RFC 8259" in SKILL_MD

    def test_etag_in_error_model(self):
        assert "ETag" in _ref("error-model-patterns.md")

    def test_last_write_wins_is_licensed(self):
        content = _ref("error-model-patterns.md").lower()
        assert "last-write-wins" in content
        assert "legitimate" in content or "policy is stated" in content

    def test_observability_not_in_error_envelope(self):
        """The reference file used to recommend metric/audit keys in the body."""
        assert not [f for f in LINT.lint(SKILL_DIR) if f.rule == "AD004"]
        content = _ref("error-model-patterns.md")
        assert re.search(r"[Dd]o \*\*not\*\* put `metric` or `audit`", content), \
            "the file must state the prohibition explicitly, not merely omit it"

    def test_contract_testing_in_compatibility(self):
        content = _ref("compatibility-rules.md").lower()
        assert "contract" in content and "baseline" in content

    def test_contract_testing_gates_are_scoped_not_blanket(self):
        content = LINT.find_section(_ref("compatibility-rules.md"), "Contract Testing")
        assert "[C]" in content, "policy gates must be marked as policy"
        for probe in ("Idempotency-Key", "If-Match"):
            row = next(l for l in content.splitlines() if probe in l)
            assert "[P]" not in row, \
                f"gating every endpoint on {probe} is the false-positive generator"
        assert re.search(r"T1.{0,6}T3", content), \
            "the idempotency gate must name the triggers that scope it"

    def test_multi_version_in_compatibility(self):
        content = _ref("compatibility-rules.md")
        assert "v1" in content and "v2" in content and "410" in content
