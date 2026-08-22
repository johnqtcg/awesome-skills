"""Validate the § 7 machine-readable block against a formal schema.

Why this file exists: a review found `"score": "10/14"` in the documented example with no
definition anywhere — not in SKILL.md, not in `authorization-and-policy.md`, not in any test. The
numerator/denominator were undefined, `14` contradicted the sibling `security_domains.total: 10`,
and `summary.pass` was equally undefined. A CI consumer could not read the block reliably and two
models would emit two different meanings.

The fix is a schema plus enforcement, not prose. `references/report-schema.json` is the single
normative shape; this file proves that:

  1. the schema is well-formed and its own `pass` rule is enforceable,
  2. the example in SKILL.md § 7 validates against it,
  3. every hand-authored forward-eval exemplar validates against it,
  4. the invariants JSON Schema cannot express hold — generically, not just for the
     canonical example, and
  5. the validator is not a rubber stamp — mutations of the example must be rejected.

Validation runs on the stdlib subset checker unconditionally, so the gate cannot vanish in a bare
environment; when `jsonschema` is installed, the authoritative implementation runs as well. Both
read the same schema file, so there is no second rule list to drift.

The schema-and-invariant checker itself lives in `../report_validator.py`, not here: a review
found that `test_forward_eval.py`'s live grader never called it, so a report with an open P1 and
`summary.pass: true`, or a domain tally of 30 instead of 10, validated cleanly through the eval
path even though this file's `DocumentedExampleTests` would have caught the same defect in the
one canonical example. Moving the checker out to a shared module — imported by both this file
and the grader — is the fix; see `report_validator.py`'s module docstring.
"""

import importlib.util
import json
import re
import sys
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
SKILL_DIR = TESTS_DIR.parents[1]
SKILL_MD = SKILL_DIR / "SKILL.md"
SCHEMA_PATH = SKILL_DIR / "references" / "report-schema.json"
# § Output Contract's field detail (including the § 7 JSON example and the allowed baseline
# statuses) lives in this reference since the contract was split out of SKILL.md to free line
# budget. Both files are normative and both are loaded when writing a report.
OUTPUT_CONTRACT = SKILL_DIR / "references" / "output-contract.md"
EVAL_DIR = TESTS_DIR / "forward_eval"

try:
    import jsonschema

    JSONSCHEMA_AVAILABLE = True
except ImportError:
    jsonschema = None
    JSONSCHEMA_AVAILABLE = False

# `--import-mode=importlib` (see pytest.ini) does not put sibling test files' directory on
# sys.path, so a bare `import report_validator` fails under pytest even though it succeeds under
# `unittest discover`. Load by path instead, matching the convention other skills already use
# for importing a scripts/ module from its test file (e.g. incident-postmortem's lint import).
_REPORT_VALIDATOR_PATH = SKILL_DIR / "scripts" / "report_validator.py"
_spec = importlib.util.spec_from_file_location(
    "security_review_report_validator_schema", _REPORT_VALIDATOR_PATH)
report_validator = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
sys.modules[_spec.name] = report_validator
_spec.loader.exec_module(report_validator)

load_schema = report_validator.load_schema
_validate = report_validator.validate_schema  # schema-keywords only, no invariants — see below
_SUPPORTED = report_validator.SUPPORTED_KEYWORDS
_ANNOTATIONS = report_validator.ANNOTATION_KEYWORDS


def validate(instance, schema=None) -> list:
    """Errors from the stdlib checker + the semantic invariants (via report_validator), plus
    jsonschema's own errors when it is installed. `jsonschema` only ever checks schema keywords
    — it has no notion of the Python-side invariants — so the cross-check below deliberately
    calls `_validate` (schema-only), not this function, when comparing the two."""
    schema = schema or load_schema()
    errors = report_validator.validate_report(instance, schema)
    if JSONSCHEMA_AVAILABLE:
        validator = jsonschema.Draft202012Validator(schema)
        errors += [f"jsonschema: {e.json_path}: {e.message}"
                   for e in validator.iter_errors(instance)]
    return errors


def json_blocks(text: str):
    for m in re.finditer(r"```json\s*\n(.*?)```", text, re.S):
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and ("summary" in data or "findings" in data):
            yield data


def _declared_total(data: dict) -> int:
    c = data["counts"]
    return c["p0"] + c["p1"] + c["p2"] + c["p3"]


def contract_text() -> str:
    """SKILL.md plus the extracted § Output Contract detail."""
    return SKILL_MD.read_text(encoding="utf-8") + "\n" + OUTPUT_CONTRACT.read_text(
        encoding="utf-8")


def documented_example() -> dict:
    blocks = list(json_blocks(contract_text()))
    assert blocks, "the Output Contract has no parseable § 7 JSON example"
    return blocks[0]


class SchemaIntegrityTests(unittest.TestCase):
    def test_schema_is_well_formed(self) -> None:
        schema = load_schema()
        self.assertEqual("object", schema["type"])
        self.assertFalse(schema["additionalProperties"],
                         "an open object lets an undefined field like the retired `score` back in")
        if JSONSCHEMA_AVAILABLE:
            jsonschema.Draft202012Validator.check_schema(schema)

    def test_every_field_carries_a_definition(self) -> None:
        """The defect was an undefined field, so every leaf must say what it means: a
        description, an enum, or a const. `score` would fail this."""
        undocumented = []

        def walk(node, path):
            if not isinstance(node, dict):
                return
            props = node.get("properties")
            if isinstance(props, dict):
                for key, sub in props.items():
                    here = f"{path}.{key}"
                    if not any(k in sub for k in ("description", "enum", "const", "properties",
                                                  "items", "additionalProperties")):
                        undocumented.append(here)
                    walk(sub, here)
            for key in ("items", "additionalProperties"):
                if isinstance(node.get(key), dict):
                    walk(node[key], f"{path}[]")

        walk(load_schema(), "$")
        self.assertEqual([], undocumented,
                         f"fields with no stated meaning: {undocumented}")

    def test_schema_uses_only_supported_keywords(self) -> None:
        """The stdlib checker ignores keywords it does not implement, so an unsupported keyword
        in the schema would weaken the gate without any test turning red. Fail closed instead."""
        unsupported = set()

        def walk(node) -> None:
            """Recurse through keyword positions only — names under `properties` are field
            names, not schema keywords, so they must not be checked against _SUPPORTED."""
            if not isinstance(node, dict):
                return
            for key, value in node.items():
                if key == "properties" and isinstance(value, dict):
                    for sub in value.values():
                        walk(sub)
                elif key in ("items", "additionalProperties", "if", "then"):
                    walk(value)
                elif key in ("allOf", "anyOf") and isinstance(value, list):
                    for sub in value:
                        walk(sub)
                elif key not in _SUPPORTED and key not in _ANNOTATIONS:
                    unsupported.add(key)

        walk(load_schema())
        self.assertEqual(set(), unsupported,
                         f"schema uses keywords the stdlib checker ignores, so the gate would "
                         f"fail open: {sorted(unsupported)}")

    def test_keyword_guard_is_not_vacuous(self) -> None:
        """A schema with an unimplemented keyword must be caught, and a field literally named
        after a keyword must not be."""
        self.assertNotIn("multipleOf", _SUPPORTED)
        self.assertIn("pattern", _SUPPORTED)
        # A field named "pattern" under `properties` is a name, not a keyword.
        benign = {"properties": {"pattern": {"type": "string"}}}
        self.assertEqual([], _validate({"pattern": "x"}, benign))

    def test_suppression_rule_numbers_stay_within_the_documented_rules(self) -> None:
        """The schema deliberately sets no maximum on `suppressed[].rule` — a hard-coded 4 would
        be a second copy of the rule list. Derive the bound from SKILL.md instead."""
        skill = SKILL_MD.read_text(encoding="utf-8")
        start = skill.index("## False-Positive Suppression Rules")
        section = skill[start:skill.index("\n## ", start + 1)]
        rule_count = len(re.findall(r"(?m)^\d+\.", section))
        self.assertGreaterEqual(rule_count, 4)
        cited = [entry["rule"]
                 for path in sorted(EVAL_DIR.glob("*/good.md"))
                 for block in json_blocks(path.read_text(encoding="utf-8"))
                 for entry in block.get("suppressed", [])]
        for rule in cited:
            self.assertLessEqual(rule, rule_count,
                                 f"an exemplar cites suppression rule {rule} but SKILL.md "
                                 f"defines {rule_count}")

    def test_pass_rule_is_stated_in_the_schema_not_only_in_prose(self) -> None:
        schema = load_schema()
        titles = " ".join(s.get("title", "") for s in schema.get("allOf", []))
        for token in ("P0", "P1", "domain"):
            self.assertIn(token, titles,
                          f"the computed-pass rule must be enforced for {token} in allOf")
        self.assertIn("computed", schema["properties"]["summary"]["properties"]["pass"]
                      ["description"])


class DocumentedExampleTests(unittest.TestCase):
    def test_skill_md_example_validates(self) -> None:
        errors = validate(documented_example())
        self.assertEqual([], errors, f"SKILL.md § 7 example violates its own schema: {errors}")

    def test_retired_score_field_is_gone(self) -> None:
        """Scoped to the emitted JSON, not the whole document.

        The first version of this guard searched all of SKILL.md for `"score"` and therefore
        failed on the sentence that *explains why the field was removed* — a guard that forbids
        its own correction. Only occurrences inside a ```json block are instructions."""
        example = documented_example()
        self.assertNotIn("score", example.get("summary", {}),
                         "`summary.score` was undefined and contradicted security_domains.total")
        for block in json_blocks(contract_text()):
            self.assertNotIn("score", json.dumps(block),
                             "the undefined score field reappeared in an emitted JSON example")

    def test_score_guard_is_scoped_but_not_toothless(self) -> None:
        """Guard the guard: prose mentioning the retired field must pass, a JSON block
        containing it must fail. Without this the scoping above could be vacuous."""
        prose_only = 'the earlier `"score": "10/14"` contradicted `total: 10` and was removed'
        self.assertEqual([], list(json_blocks(prose_only)),
                         "a prose mention must not be read as an emitted block")
        with_block = '```json\n{"summary": {"pass": false, "score": "10/14"}}\n```'
        blocks = list(json_blocks(with_block))
        self.assertTrue(blocks, "a real JSON block must still be detected")
        self.assertIn("score", json.dumps(blocks[0]))
        self.assertTrue(validate(blocks[0]), "the schema must reject the retired field")

    def test_example_exercises_every_required_key(self) -> None:
        """An example that omits a required key cannot be copied as a template."""
        schema = load_schema()
        example = documented_example()
        for key in schema["required"]:
            self.assertIn(key, example, f"the documented example omits required key {key!r}")

    def test_domain_tally_sums_to_total(self) -> None:
        """x-invariant 1 — not expressible in JSON Schema."""
        dom = documented_example()["security_domains"]
        self.assertEqual(dom["total"], dom["pass"] + dom["fail"] + dom["na"],
                         "pass + fail + na must account for all 10 domains")

    def test_counts_reconcile_with_the_findings_list(self) -> None:
        """x-invariant 3. The documented example previously declared 4 findings with overflow 0
        while listing 1, so the template a reader copies violated the rule it defines: a consumer
        could not tell whether 3 findings were dropped or never existed."""
        data = documented_example()
        self.assertEqual(_declared_total(data), len(data["findings"]) + data["counts"]["overflow"],
                         "counts must equal len(findings[]) + overflow")

    def test_changes_reconcile_with_the_findings_list(self) -> None:
        """A baseline diff that does not add up is the same defect one field over."""
        data = documented_example()
        changes = data.get("changes")
        if changes is None:
            self.skipTest("example declares no baseline")
        listed = len(data["findings"]) + data["counts"]["overflow"]
        open_now = changes["new"] + changes["regressed"] + changes["unchanged"]
        self.assertEqual(listed, open_now,
                         "new + regressed + unchanged must equal the reported findings; "
                         "`resolved` is not among them because a resolved finding is not reported")

    def test_pass_matches_the_computation(self) -> None:
        data = documented_example()
        counts, dom = data["counts"], data["security_domains"]
        expected = not (counts["p0"] > 0 or counts["p1"] > 0 or dom["fail"] > 0)
        self.assertEqual(expected, data["summary"]["pass"],
                         "summary.pass in the example contradicts the documented computation")


class ExemplarConformanceTests(unittest.TestCase):
    """The hand-authored good exemplars are what a reviewer is shown as correct output. If they
    do not satisfy the contract, the contract is decorative."""

    def _good_exemplars(self):
        return sorted(EVAL_DIR.glob("*/good.md"))

    def test_there_are_exemplars_to_check(self) -> None:
        self.assertGreater(len(self._good_exemplars()), 0)

    def test_good_exemplars_validate(self) -> None:
        for path in self._good_exemplars():
            with self.subTest(exemplar=path.parent.name):
                blocks = list(json_blocks(path.read_text(encoding="utf-8")))
                self.assertTrue(blocks, f"{path} has no parseable JSON summary")
                for i, block in enumerate(blocks):
                    errors = validate(block)
                    self.assertEqual([], errors, f"{path} block {i}: {errors}")

    def test_good_exemplar_tallies_are_consistent(self) -> None:
        for path in self._good_exemplars():
            with self.subTest(exemplar=path.parent.name):
                for block in json_blocks(path.read_text(encoding="utf-8")):
                    dom = block["security_domains"]
                    self.assertEqual(dom["total"], dom["pass"] + dom["fail"] + dom["na"],
                                     f"{path}: domain tally does not sum to total")
                    counts = block["counts"]
                    expected = not (counts["p0"] > 0 or counts["p1"] > 0 or dom["fail"] > 0)
                    self.assertEqual(expected, block["summary"]["pass"],
                                     f"{path}: summary.pass contradicts the computation")


class ValidatorIsNotARubberStampTests(unittest.TestCase):
    """Mutations of the valid example must be rejected. Without this, a validator that returned
    [] unconditionally would look identical to a working one."""

    def _mutate(self, **changes) -> dict:
        data = documented_example()
        for dotted, value in changes.items():
            node = data
            *parents, leaf = dotted.split("__")
            for part in parents:
                node = node[part]
            if value is None:
                node.pop(leaf, None)
            else:
                node[leaf] = value
        return data

    def test_undefined_field_is_rejected(self) -> None:
        self.assertTrue(validate(self._mutate(summary__score="10/14")),
                        "an undefined field must be rejected — this is the original defect")

    def test_open_p0_with_pass_true_is_rejected(self) -> None:
        data = self._mutate(counts__p0=1)
        data["summary"]["pass"] = True
        errors = validate(data)
        self.assertTrue(errors, "pass=true alongside an open P0 must be rejected")

    def test_open_p1_with_pass_true_is_rejected(self) -> None:
        data = self._mutate(counts__p1=3)
        data["summary"]["pass"] = True
        self.assertTrue(validate(data), "pass=true alongside an open P1 must be rejected")

    def test_failing_domain_with_pass_true_is_rejected(self) -> None:
        data = documented_example()
        data["counts"].update(p0=0, p1=0)
        data["security_domains"]["fail"] = 2
        data["summary"]["pass"] = True
        self.assertTrue(validate(data), "pass=true with a FAILing domain must be rejected")

    def test_wrong_domain_total_is_rejected(self) -> None:
        self.assertTrue(validate(self._mutate(security_domains__total=14)),
                        "the domain set is fixed at 10; 14 must be rejected")

    def test_retired_go_domains_key_is_rejected(self) -> None:
        data = documented_example()
        data["go_domains"] = data.pop("security_domains")
        self.assertTrue(validate(data), "the retired go_domains key must be rejected")

    def test_unpinned_asvs_is_rejected(self) -> None:
        data = documented_example()
        data["findings"][0]["asvs"] = "V4.1.2"
        self.assertTrue(validate(data), "an ASVS id without its version must be rejected")

    def test_bad_severity_is_rejected(self) -> None:
        data = documented_example()
        data["findings"][0]["severity"] = "high"
        self.assertTrue(validate(data), "severity must be one of P0..P3")

    def test_missing_required_block_is_rejected(self) -> None:
        self.assertTrue(validate(self._mutate(active_verification=None)))

    def test_baseline_present_without_changes_is_rejected(self) -> None:
        data = documented_example()
        data.pop("changes", None)
        self.assertTrue(validate(data),
                        "baseline=present promises a diff; `changes` must then be required")

    def test_clean_report_claiming_pass_false_is_rejected(self) -> None:
        """Reported hole: the pass rule was one-directional. With no P0/P1 and no failing domain,
        `pass: false` was accepted — a report failing its own gate for no stated reason."""
        data = documented_example()
        data["counts"].update(p0=0, p1=0, p2=0, p3=0, overflow=0)
        data["security_domains"].update(fail=0, na=2, **{"pass": 8})
        data["findings"] = []
        data["changes"] = {"new": 0, "regressed": 0, "unchanged": 0, "resolved": 0}
        data["summary"]["pass"] = False
        self.assertTrue(validate(data),
                        "a clean report must not be allowed to claim pass=false")
        # ...and the same report with pass=true must be accepted, or the rule is unsatisfiable.
        data["summary"]["pass"] = True
        self.assertEqual([], validate(data),
                        "the corrected form must validate; otherwise the rule cannot be obeyed")

    def test_mixed_asvs_versions_are_rejected(self) -> None:
        """Reported hole: a top-level 5.0.0 with 4.0.3 requirement IDs was accepted, which is
        precisely the ambiguity the version pinning exists to prevent."""
        data = documented_example()
        data["asvs_version"] = "5.0.0"  # findings still say "ASVS 4.0.3 V4.1.2"
        self.assertTrue(validate(data), "mixed ASVS versions must be rejected")
        # And the reverse direction.
        data = documented_example()
        data["findings"][0]["asvs"] = "ASVS 5.0.0 V8.1.1"  # top level still 4.0.3
        self.assertTrue(validate(data), "mixed ASVS versions must be rejected either way")

    def test_mapping_tbd_survives_the_version_check(self) -> None:
        """The version check must not forbid the documented escape hatch."""
        data = documented_example()
        data["findings"][0]["asvs"] = "Mapping: TBD — requirement not identified"
        self.assertEqual([], validate(data),
                         "`Mapping: TBD <reason>` is explicitly permitted by SKILL.md")

    def test_resolved_status_on_a_reported_finding_is_rejected(self) -> None:
        """Reported hole: SKILL.md § Output Contract allows `new/regressed/unchanged` on a
        finding. `resolved` means it is no longer a finding, so it belongs in changes.resolved."""
        data = documented_example()
        data["findings"][0]["status"] = "resolved"
        self.assertTrue(validate(data),
                        "`resolved` must not be a valid status for a listed finding")

    def test_finding_status_enum_matches_the_skill_document(self) -> None:
        """Derived from SKILL.md rather than duplicated, so the two cannot drift."""
        m = re.search(r"Baseline status \(`([^`]+)`\)", contract_text())
        self.assertIsNotNone(m, "the Output Contract must state the allowed baseline statuses")
        documented = set(m.group(1).split("/"))
        schema_enum = set(load_schema()["properties"]["findings"]["items"]
                          ["properties"]["status"]["enum"])
        self.assertEqual(documented, schema_enum,
                         f"schema status enum {sorted(schema_enum)} disagrees with SKILL.md "
                         f"{sorted(documented)}")

    def test_stdlib_checker_agrees_with_jsonschema_on_every_mutation(self) -> None:
        """If the two disagree, the bare-environment gate is weaker than it appears."""
        if not JSONSCHEMA_AVAILABLE:
            self.skipTest("jsonschema not installed; cross-check unavailable")
        schema = load_schema()
        mutations = []
        base = documented_example()
        m1 = json.loads(json.dumps(base)); m1["summary"]["score"] = "10/14"; mutations.append(m1)
        m2 = json.loads(json.dumps(base)); m2["counts"]["p0"] = 1; m2["summary"]["pass"] = True
        mutations.append(m2)
        m3 = json.loads(json.dumps(base)); m3["security_domains"]["total"] = 14
        mutations.append(m3)
        m4 = json.loads(json.dumps(base)); m4["findings"][0]["severity"] = "high"
        mutations.append(m4)
        for i, mutated in enumerate(mutations):
            with self.subTest(mutation=i):
                stdlib_errs = _validate(mutated, schema)
                js_errs = list(jsonschema.Draft202012Validator(schema).iter_errors(mutated))
                self.assertEqual(
                    bool(stdlib_errs), bool(js_errs),
                    f"mutation {i}: stdlib checker and jsonschema disagree "
                    f"(stdlib={stdlib_errs}, jsonschema={[e.message for e in js_errs]})",
                )


class GenericInvariantEnforcementTests(unittest.TestCase):
    """The x-invariants, checked against constructed reports — deliberately NOT
    `documented_example()`. Reported hole: `DocumentedExampleTests` above proves the invariant
    holds for one fixed canonical report; it says nothing about whether `validate()` would catch
    the same defect in an arbitrary report, and it did not — the forward-eval grader called a
    schema-only check that never ran these invariants at all. These tests are the generic form:
    build the smallest instance that isolates one invariant, mutate it, and prove `validate()`
    — the function the grader now also calls — rejects it."""

    def _minimal_valid_report(self) -> dict:
        """A hand-built minimal instance, independent of the documented example, so these tests
        do not silently depend on that fixture's shape."""
        return {
            "summary": {"pass": True, "baseline": "absent"},
            "counts": {"p0": 0, "p1": 0, "p2": 0, "p3": 0, "overflow": 0},
            "stack": "go",
            "asvs_version": "4.0.3",
            "active_verification": "not_permitted",
            "security_domains": {"required": True, "total": 10, "pass": 10, "fail": 0, "na": 0},
            "findings": [],
        }

    def test_baseline_valid_form_passes(self) -> None:
        self.assertEqual([], validate(self._minimal_valid_report()))

    def test_domain_tally_of_30_instead_of_10_is_rejected(self) -> None:
        """Reported hole: pass=10, fail=10, na=10 each individually satisfy the schema's
        per-field 0-10 bounds, so nothing but a cross-field sum check catches a tally of 30."""
        data = self._minimal_valid_report()
        data["security_domains"]["pass"] = 10
        data["security_domains"]["fail"] = 10
        data["security_domains"]["na"] = 10
        errors = validate(data)
        self.assertTrue(errors, "pass(10)+fail(10)+na(10)=30 != total(10) must be rejected")
        self.assertTrue(any("security_domains" in e and "30" in e for e in errors), errors)

    def test_counts_and_findings_length_mismatch_is_rejected(self) -> None:
        """Reported hole: a report claiming counts p1=1 while findings[] is empty (or vice
        versa) validated cleanly because the reconciliation was only ever tested against the
        one canonical example."""
        data = self._minimal_valid_report()
        data["counts"]["p1"] = 1
        data["summary"]["pass"] = False
        # findings[] stays empty and overflow stays 0 — the mismatch the reviewer found.
        errors = validate(data)
        self.assertTrue(errors, "counts declaring 1 P1 with an empty findings[] and overflow=0 "
                                "must be rejected")
        self.assertTrue(any("counts" in e for e in errors), errors)

    def test_baseline_absent_with_a_non_new_finding_status_is_rejected(self) -> None:
        """Reported hole: with no baseline to diff against, a finding cannot legitimately be
        'unchanged' (or 'regressed') — there is nothing for it to be unchanged FROM."""
        data = self._minimal_valid_report()
        data["counts"]["p2"] = 1
        data["findings"] = [{
            "id": "SEC-001", "severity": "P2", "confidence": "confirmed", "status": "unchanged",
            "origin": "introduced", "cwe": "CWE-89", "asvs": "ASVS 4.0.3 V5.3.4",
            "file": "app.py:10",
        }]
        errors = validate(data)
        self.assertTrue(errors, "baseline='absent' with a finding status of 'unchanged' must be "
                                "rejected")
        self.assertTrue(any("baseline is 'absent'" in e for e in errors), errors)

    def test_baseline_absent_with_nonzero_changes_is_rejected(self) -> None:
        data = self._minimal_valid_report()
        data["changes"] = {"new": 0, "regressed": 1, "unchanged": 0, "resolved": 0}
        errors = validate(data)
        self.assertTrue(errors, "baseline='absent' with changes.regressed=1 must be rejected")

    def test_multi_stack_without_per_stack_is_rejected(self) -> None:
        """Reported hole: `stack: 'go,nodejs'` is legal per the schema's own pattern, and
        `per_stack` is optional in the schema, so nothing required it to actually be present for
        a multi-stack report — leaving a consumer unable to tell which stack a domain failure
        belongs to."""
        data = self._minimal_valid_report()
        data["stack"] = "go,nodejs"
        errors = validate(data)
        self.assertTrue(errors, "stack='go,nodejs' with no per_stack must be rejected")
        self.assertTrue(any("per_stack" in e for e in errors), errors)

    def test_multi_stack_with_complete_per_stack_passes(self) -> None:
        data = self._minimal_valid_report()
        data["stack"] = "go,nodejs"
        data["per_stack"] = {
            "go": {"pass": 10, "fail": 0, "na": 0, "failing_domains": []},
            "nodejs": {"pass": 10, "fail": 0, "na": 0, "failing_domains": []},
        }
        self.assertEqual([], validate(data))

    def test_multi_stack_without_failing_domains_is_rejected(self) -> None:
        """Reported hole: failing_domains being merely optional meant a report using the old
        count-only per_stack shape fell back to the weaker fail>=max(...) bound and validated
        cleanly even when the counts were internally consistent — the union gap was real but
        silently opt-out-able. Requiring the field on every stack of a multi-stack report is what
        actually closes it, rather than leaving it a bound a reporter can choose not to meet."""
        data = self._minimal_valid_report()
        data["stack"] = "go,nodejs"
        # Internally consistent under the OLD (count-only) rule: fail propagates correctly.
        data["security_domains"] = {"required": True, "total": 10, "pass": 9, "fail": 1, "na": 0}
        data["summary"]["pass"] = False
        data["counts"]["p2"] = 1
        data["per_stack"] = {
            "go": {"pass": 10, "fail": 0, "na": 0},
            "nodejs": {"pass": 9, "fail": 1, "na": 0},
        }
        data["findings"] = [{
            "id": "SEC-001", "severity": "P2", "confidence": "confirmed", "status": "new",
            "origin": "introduced", "cwe": "CWE-89", "asvs": "ASVS 4.0.3 V5.3.4",
            "file": "app.js:1",
        }]
        errors = validate(data)
        self.assertTrue(errors, "a multi-stack report omitting failing_domains must be rejected "
                                "even when its counts are otherwise self-consistent")
        self.assertTrue(any("missing failing_domains" in e for e in errors), errors)

    def test_multi_stack_with_incomplete_per_stack_is_rejected(self) -> None:
        data = self._minimal_valid_report()
        data["stack"] = "go,nodejs,python"
        data["per_stack"] = {"go": {"pass": 10, "fail": 0, "na": 0}}  # missing nodejs, python
        errors = validate(data)
        self.assertTrue(errors)
        self.assertTrue(any("nodejs" in e and "python" in e for e in errors), errors)

    def test_changes_and_findings_length_mismatch_is_rejected(self) -> None:
        """The fifth invariant — the same shape as the counts/findings reconciliation, one
        field over. `test_changes_reconcile_with_the_findings_list` above only ever asserted it
        against the one canonical example; this proves `validate()` catches it generically."""
        data = self._minimal_valid_report()
        data["summary"]["baseline"] = "present"
        data["counts"]["p2"] = 1
        data["findings"] = [{
            "id": "SEC-001", "severity": "P2", "confidence": "confirmed", "status": "unchanged",
            "origin": "pre-existing", "cwe": "CWE-89", "asvs": "ASVS 4.0.3 V5.3.4",
            "file": "app.py:10",
        }]
        # Claims 2 unchanged findings are open, but only 1 is actually listed.
        data["changes"] = {"new": 0, "regressed": 0, "unchanged": 2, "resolved": 0}
        errors = validate(data)
        self.assertTrue(errors, "changes.unchanged=2 with only 1 finding listed must be rejected")
        self.assertTrue(any("$.changes" in e for e in errors), errors)

    def test_changes_reconciling_with_findings_passes(self) -> None:
        data = self._minimal_valid_report()
        data["summary"]["baseline"] = "present"
        data["counts"]["p2"] = 1
        data["findings"] = [{
            "id": "SEC-001", "severity": "P2", "confidence": "confirmed", "status": "unchanged",
            "origin": "pre-existing", "cwe": "CWE-89", "asvs": "ASVS 4.0.3 V5.3.4",
            "file": "app.py:10",
        }]
        data["changes"] = {"new": 0, "regressed": 0, "unchanged": 1, "resolved": 0}
        self.assertEqual([], validate(data))

    def test_p1_finding_hidden_via_overflow_is_rejected(self) -> None:
        """The reviewer's exact PoC: a real P1 finding, `counts.p1` left at 0, `counts.p2`
        bumped to keep the total reconciling, `summary.pass: true`. The pre-fix validator
        checked only that p0+p1+p2+p3 == len(findings)+overflow and returned []."""
        data = self._minimal_valid_report()
        data["counts"]["p2"] = 1
        data["findings"] = [{
            "id": "SEC-001", "severity": "P1", "confidence": "confirmed", "status": "new",
            "origin": "introduced", "cwe": "CWE-89", "asvs": "ASVS 4.0.3 V5.3.4",
            "file": "app.py:1",
        }]
        errors = validate(data)
        self.assertTrue(errors, "a P1 finding with counts.p1=0 must be rejected")
        self.assertTrue(any("counts.p1" in e and "hidden in overflow" in e for e in errors),
                        errors)

    def test_p2_declared_below_itemised_is_rejected(self) -> None:
        data = self._minimal_valid_report()
        data["counts"]["p3"] = 1  # compensates the total so only the per-severity check fires
        data["findings"] = [{
            "id": "SEC-001", "severity": "P2", "confidence": "confirmed", "status": "new",
            "origin": "introduced", "cwe": "CWE-89", "asvs": "ASVS 4.0.3 V5.3.4",
            "file": "app.py:1",
        }]
        errors = validate(data)
        self.assertTrue(errors, "counts.p2=0 with one itemised P2 finding must be rejected")
        self.assertTrue(any("counts.p2" in e for e in errors), errors)

    def test_p2_declared_above_itemised_via_overflow_passes(self) -> None:
        """P2/P3 may legitimately be capped: more identified than itemised is fine as long as
        `overflow` accounts for the gap — this must not regress."""
        data = self._minimal_valid_report()
        data["counts"]["p2"] = 2
        data["counts"]["overflow"] = 1
        data["findings"] = [{
            "id": "SEC-001", "severity": "P2", "confidence": "confirmed", "status": "new",
            "origin": "introduced", "cwe": "CWE-89", "asvs": "ASVS 4.0.3 V5.3.4",
            "file": "app.py:1",
        }]
        self.assertEqual([], validate(data))

    def test_changes_status_declared_below_itemised_is_rejected(self) -> None:
        """Same-class bypass on the `changes` side: a finding with status='regressed' while
        `changes.regressed` stays 0 and `changes.new` absorbs the count instead."""
        data = self._minimal_valid_report()
        data["summary"]["baseline"] = "present"
        data["counts"]["p2"] = 1
        data["findings"] = [{
            "id": "SEC-001", "severity": "P2", "confidence": "confirmed", "status": "regressed",
            "origin": "pre-existing", "cwe": "CWE-89", "asvs": "ASVS 4.0.3 V5.3.4",
            "file": "app.py:1",
        }]
        data["changes"] = {"new": 1, "regressed": 0, "unchanged": 0, "resolved": 0}
        errors = validate(data)
        self.assertTrue(errors, "changes.regressed=0 with one itemised regressed finding must "
                                "be rejected")
        self.assertTrue(any("changes.regressed" in e for e in errors), errors)

    def test_per_stack_extra_undeclared_stack_is_rejected(self) -> None:
        """Reported hole: `stack: 'go,nodejs'` with a `per_stack.python` entry validated
        cleanly — only missing entries were checked, never extra ones."""
        data = self._minimal_valid_report()
        data["stack"] = "go,nodejs"
        data["per_stack"] = {
            "go": {"pass": 10, "fail": 0, "na": 0},
            "nodejs": {"pass": 10, "fail": 0, "na": 0},
            "python": {"pass": 10, "fail": 0, "na": 0},
        }
        errors = validate(data)
        self.assertTrue(errors, "an undeclared per_stack.python entry must be rejected")
        self.assertTrue(any("per_stack" in e and "python" in e for e in errors), errors)

    def test_per_stack_domain_sum_not_ten_is_rejected(self) -> None:
        """Reported hole: `per_stack.nodejs` summing to 30 (10/10/10) individually satisfies
        each field's own 0-10 bound, exactly like the top-level security_domains bug this
        mirrors."""
        data = self._minimal_valid_report()
        data["stack"] = "go,nodejs"
        data["per_stack"] = {
            "go": {"pass": 10, "fail": 0, "na": 0},
            "nodejs": {"pass": 10, "fail": 10, "na": 10},
        }
        errors = validate(data)
        self.assertTrue(errors, "per_stack.nodejs summing to 30 instead of 10 must be rejected")
        self.assertTrue(any("per_stack.nodejs" in e and "30" in e for e in errors), errors)

    def test_per_stack_fail_not_propagated_to_top_level_is_rejected(self) -> None:
        """Reported hole: a sub-stack FAIL can be masked by a clean top-level tally — the
        multi-stack report's own summary.pass would then wrongly read as true."""
        data = self._minimal_valid_report()
        data["stack"] = "go,nodejs"
        data["per_stack"] = {
            "go": {"pass": 10, "fail": 0, "na": 0},
            "nodejs": {"pass": 9, "fail": 1, "na": 0},
        }
        # top-level security_domains.fail stays 0 — the exact masking the reviewer described.
        errors = validate(data)
        self.assertTrue(errors, "security_domains.fail=0 despite a per_stack fail=1 must be "
                                "rejected")
        self.assertTrue(any("security_domains.fail" in e for e in errors), errors)

    def test_per_stack_fail_propagated_passes(self) -> None:
        data = self._minimal_valid_report()
        data["stack"] = "go,nodejs"
        data["counts"]["p2"] = 1
        data["security_domains"] = {"required": True, "total": 10, "pass": 9, "fail": 1, "na": 0}
        data["summary"]["pass"] = False
        data["per_stack"] = {
            "go": {"pass": 10, "fail": 0, "na": 0, "failing_domains": []},
            "nodejs": {"pass": 9, "fail": 1, "na": 0, "failing_domains": [2]},
        }
        data["findings"] = [{
            "id": "SEC-001", "severity": "P2", "confidence": "confirmed", "status": "new",
            "origin": "introduced", "cwe": "CWE-89", "asvs": "ASVS 4.0.3 V5.3.4",
            "file": "app.js:1",
        }]
        self.assertEqual([], validate(data))

    def test_per_stack_failing_domains_union_undercounted_is_rejected(self) -> None:
        """Reported hole: the fail-propagation check above is only a lower bound
        (fail >= max(per_stack.fail)). Two stacks each failing a DIFFERENT domain is 2 failing
        domains overall, not 1 — a count-only per_stack (fail=1 in each) cannot distinguish that
        from both stacks failing the SAME domain, so a top-level fail=1 wrongly passed."""
        data = self._minimal_valid_report()
        data["stack"] = "go,nodejs"
        data["counts"]["p2"] = 2
        data["security_domains"] = {"required": True, "total": 10, "pass": 8, "fail": 1, "na": 1}
        data["summary"]["pass"] = False
        data["per_stack"] = {
            "go": {"pass": 9, "fail": 1, "na": 0, "failing_domains": [1]},
            "nodejs": {"pass": 9, "fail": 1, "na": 0, "failing_domains": [2]},
        }
        data["findings"] = [
            {"id": "SEC-001", "severity": "P2", "confidence": "confirmed", "status": "new",
             "origin": "introduced", "cwe": "CWE-89", "asvs": "ASVS 4.0.3 V5.3.4", "file": "a.go:1"},
            {"id": "SEC-002", "severity": "P2", "confidence": "confirmed", "status": "new",
             "origin": "introduced", "cwe": "CWE-79", "asvs": "ASVS 4.0.3 V5.3.4", "file": "a.js:1"},
        ]
        errors = validate(data)
        self.assertTrue(errors, "fail=1 with per_stack failing_domains=[1] and [2] (2 distinct "
                                "domains) must be rejected")
        self.assertTrue(any("union" in e and "security_domains.fail" in e for e in errors),
                        errors)

    def test_per_stack_failing_domains_exact_union_passes(self) -> None:
        data = self._minimal_valid_report()
        data["stack"] = "go,nodejs"
        data["counts"]["p2"] = 2
        data["security_domains"] = {"required": True, "total": 10, "pass": 8, "fail": 2, "na": 0}
        data["summary"]["pass"] = False
        data["per_stack"] = {
            "go": {"pass": 9, "fail": 1, "na": 0, "failing_domains": [1]},
            "nodejs": {"pass": 9, "fail": 1, "na": 0, "failing_domains": [2]},
        }
        data["findings"] = [
            {"id": "SEC-001", "severity": "P2", "confidence": "confirmed", "status": "new",
             "origin": "introduced", "cwe": "CWE-89", "asvs": "ASVS 4.0.3 V5.3.4", "file": "a.go:1"},
            {"id": "SEC-002", "severity": "P2", "confidence": "confirmed", "status": "new",
             "origin": "introduced", "cwe": "CWE-79", "asvs": "ASVS 4.0.3 V5.3.4", "file": "a.js:1"},
        ]
        self.assertEqual([], validate(data))

    def test_per_stack_failing_domains_same_domain_in_both_stacks_passes(self) -> None:
        """The union of {1} and {1} is 1 distinct domain, not 2 — must not over-reject."""
        data = self._minimal_valid_report()
        data["stack"] = "go,nodejs"
        data["counts"]["p2"] = 2
        data["security_domains"] = {"required": True, "total": 10, "pass": 9, "fail": 1, "na": 0}
        data["summary"]["pass"] = False
        data["per_stack"] = {
            "go": {"pass": 9, "fail": 1, "na": 0, "failing_domains": [1]},
            "nodejs": {"pass": 9, "fail": 1, "na": 0, "failing_domains": [1]},
        }
        data["findings"] = [
            {"id": "SEC-001", "severity": "P2", "confidence": "confirmed", "status": "new",
             "origin": "introduced", "cwe": "CWE-89", "asvs": "ASVS 4.0.3 V5.3.4", "file": "a.go:1"},
            {"id": "SEC-002", "severity": "P2", "confidence": "confirmed", "status": "new",
             "origin": "introduced", "cwe": "CWE-79", "asvs": "ASVS 4.0.3 V5.3.4", "file": "a.js:1"},
        ]
        self.assertEqual([], validate(data))

    def test_per_stack_failing_domains_length_mismatch_is_rejected(self) -> None:
        data = self._minimal_valid_report()
        data["stack"] = "go,nodejs"
        data["security_domains"] = {"required": True, "total": 10, "pass": 8, "fail": 2, "na": 0}
        data["summary"]["pass"] = False
        data["per_stack"] = {
            "go": {"pass": 9, "fail": 1, "na": 0, "failing_domains": [1, 2]},  # fail=1 but 2 listed
            "nodejs": {"pass": 8, "fail": 2, "na": 0, "failing_domains": [3, 4]},
        }
        errors = validate(data)
        self.assertTrue(errors, "failing_domains listing 2 entries with fail=1 must be rejected")
        self.assertTrue(any("per_stack.go.failing_domains" in e for e in errors), errors)

    def test_per_stack_failing_domains_duplicate_is_rejected(self) -> None:
        data = self._minimal_valid_report()
        data["stack"] = "go,nodejs"
        data["security_domains"] = {"required": True, "total": 10, "pass": 8, "fail": 1, "na": 1}
        data["summary"]["pass"] = False
        data["per_stack"] = {
            "go": {"pass": 8, "fail": 2, "na": 0, "failing_domains": [1, 1]},
            "nodejs": {"pass": 10, "fail": 0, "na": 0, "failing_domains": []},
        }
        errors = validate(data)
        self.assertTrue(errors, "failing_domains=[1, 1] (a duplicate) must be rejected")
        self.assertTrue(any("duplicate" in e for e in errors), errors)

    def test_suppressed_rule_out_of_range_is_rejected(self) -> None:
        """Reported hole: `suppressed[].rule: 999` passed schema validation (any integer >= 1
        satisfies the field's own bound) even though SKILL.md documents only 4 numbered rules."""
        data = self._minimal_valid_report()
        data["suppressed"] = [
            {"candidate": "SSRF via http.Get", "rule": 999, "residual_risk": "n/a"},
        ]
        errors = validate(data)
        self.assertTrue(errors, "suppressed[].rule=999 must be rejected")
        self.assertTrue(any("suppressed[0].rule" in e for e in errors), errors)

    def test_suppressed_rule_in_documented_range_passes(self) -> None:
        data = self._minimal_valid_report()
        data["suppressed"] = [
            {"candidate": "SSRF via http.Get", "rule": 2, "residual_risk": "n/a"},
        ]
        self.assertEqual([], validate(data))

    def test_suppression_rule_count_matches_skill_document(self) -> None:
        """Derived from SKILL.md rather than hardcoded — mirrors
        `test_finding_status_enum_matches_the_skill_document`'s anti-drift pattern. If a rule is
        added to SKILL.md without the validator being able to see it (or vice versa), this fails
        instead of the two silently disagreeing."""
        text = SKILL_MD.read_text(encoding="utf-8")
        m = re.search(r"## False-Positive Suppression Rules\n(.*?)\n##", text, re.DOTALL)
        self.assertIsNotNone(m, "SKILL.md must have a § False-Positive Suppression Rules "
                                "section for suppressed[].rule to be checkable at all")
        documented = {int(n) for n in re.findall(r"^(\d+)\.", m.group(1), re.MULTILINE)}
        self.assertTrue(documented, "the section must contain at least one numbered rule")
        derived = report_validator._load_valid_suppression_rules()
        self.assertEqual(documented, derived,
                         f"validator's derived rule set {sorted(derived)} disagrees with "
                         f"SKILL.md's documented set {sorted(documented)}")


if __name__ == "__main__":
    unittest.main()
