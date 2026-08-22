"""Single source of truth for validating the security-review § 7 machine-readable report.

Why this module exists: `references/report-schema.json` documents semantic invariants under
`x-invariants` that plain JSON Schema cannot express — cross-field sums, a conditional across
`summary.baseline` and `findings[].status`, and a rule for multi-stack reports that was not even
documented. Before this module they were enforced ONLY against the single canonical example in
`test_report_schema.py`'s `DocumentedExampleTests` (`assertEqual` calls reading one fixed dict),
so a live model's report — or any hand-authored exemplar — with an open P1 and
`summary.pass: true`, or a `security_domains` tally of 30 instead of 10, validated cleanly:
nothing ever ran the invariant against it. `validate_report()` is the one function the schema
test suite AND the forward-eval grader both call, so a report is judged by the same rule
everywhere instead of by two rule sets that can silently drift apart.

No third-party dependency: this is the stdlib-subset schema checker plus the invariants, moved
out of `test_report_schema.py` rather than left duplicated inline. `jsonschema`, where installed,
remains an independent cross-check kept in the test file itself (it proves this stdlib subset
isn't quietly wrong) — that comparison is a property of the *test suite*, not something the live
grader needs, so it is not duplicated here.
"""

import json
import re
from pathlib import Path

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "references" / "report-schema.json"
SKILL_MD_PATH = Path(__file__).resolve().parent.parent / "SKILL.md"

TYPES = {
    "object": dict, "array": list, "string": str, "boolean": bool,
    "integer": int, "number": (int, float),
}
# Keywords `validate_schema` implements. A schema keyword outside this set would be silently
# ignored, i.e. the gate would fail OPEN — `test_schema_uses_only_supported_keywords` in
# test_report_schema.py asserts the schema never uses one.
SUPPORTED_KEYWORDS = {
    "type", "const", "enum", "pattern", "minimum", "maximum", "exclusiveMinimum",
    "required", "properties", "additionalProperties", "items", "allOf", "anyOf", "if", "then",
}
ANNOTATION_KEYWORDS = {"$schema", "$id", "title", "description", "x-invariants"}


def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_schema(instance, schema: dict, path: str = "$") -> list:
    """Minimal JSON Schema subset interpreter — the keyword-level checks only. Does not know
    about the cross-field invariants; see `_check_invariants` for those."""
    errors = []

    if "const" in schema and instance != schema["const"]:
        errors.append(f"{path}: expected const {schema['const']!r}, got {instance!r}")
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: {instance!r} not in {schema['enum']}")

    expected = schema.get("type")
    if expected:
        py = TYPES[expected]
        # bool is a subclass of int in Python; JSON Schema treats them as distinct.
        ok = isinstance(instance, py) and not (expected in ("integer", "number")
                                               and isinstance(instance, bool))
        if not ok:
            errors.append(f"{path}: expected type {expected}, got {type(instance).__name__}")
            return errors

    if isinstance(instance, str):
        if "pattern" in schema and not re.search(schema["pattern"], instance):
            errors.append(f"{path}: {instance!r} does not match /{schema['pattern']}/")
    if isinstance(instance, int) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(f"{path}: {instance} < minimum {schema['minimum']}")
        if "maximum" in schema and instance > schema["maximum"]:
            errors.append(f"{path}: {instance} > maximum {schema['maximum']}")
        if "exclusiveMinimum" in schema and instance <= schema["exclusiveMinimum"]:
            errors.append(f"{path}: {instance} <= exclusiveMinimum {schema['exclusiveMinimum']}")

    if isinstance(instance, dict):
        for key in schema.get("required", []):
            if key not in instance:
                errors.append(f"{path}: missing required property {key!r}")
        props = schema.get("properties", {})
        extra = schema.get("additionalProperties")
        for key, value in instance.items():
            if key in props:
                errors.extend(validate_schema(value, props[key], f"{path}.{key}"))
            elif extra is False:
                errors.append(f"{path}: additional property {key!r} is not defined in the schema")
            elif isinstance(extra, dict):
                errors.extend(validate_schema(value, extra, f"{path}.{key}"))

    if isinstance(instance, list) and "items" in schema:
        for i, item in enumerate(instance):
            errors.extend(validate_schema(item, schema["items"], f"{path}[{i}]"))

    for i, sub in enumerate(schema.get("allOf", [])):
        if "if" in sub:
            if not validate_schema(instance, sub["if"], path):  # condition held
                if "then" in sub:
                    errors.extend(validate_schema(instance, sub["then"],
                                                  f"{path} ({sub.get('title', f'allOf[{i}]')})"))
        else:
            errors.extend(validate_schema(instance, sub, path))

    for sub in schema.get("anyOf", []):
        if not validate_schema(instance, sub, path):
            break
    else:
        if "anyOf" in schema:
            errors.append(f"{path}: matched none of anyOf")

    return errors


def _load_valid_suppression_rules() -> set:
    """The numbered rules under SKILL.md's `## False-Positive Suppression Rules`, derived from
    the doc rather than hardcoded — so a rule added to one side without the other fails a test
    (`test_suppression_rule_count_matches_skill_document`) instead of letting `suppressed[].rule`
    silently reference a number that no longer exists, or no longer reference a number that does."""
    text = SKILL_MD_PATH.read_text(encoding="utf-8")
    m = re.search(r"## False-Positive Suppression Rules\n(.*?)\n##", text, re.DOTALL)
    section = m.group(1) if m else ""
    return {int(n) for n in re.findall(r"^(\d+)\.", section, re.MULTILINE)}


def _check_invariants(instance) -> list:
    """The invariants JSON Schema cannot express, checked against ANY instance — not just a fixed
    canonical example. This is the fix for the gap where these were assertions against one
    hardcoded report rather than a rule enforced on every report."""
    errors = []
    if not isinstance(instance, dict):
        return errors

    dom = instance.get("security_domains")
    if isinstance(dom, dict) and all(k in dom for k in ("pass", "fail", "na", "total")):
        tally = dom["pass"] + dom["fail"] + dom["na"]
        if tally != dom["total"]:
            errors.append(
                f"$.security_domains: pass({dom['pass']}) + fail({dom['fail']}) + "
                f"na({dom['na']}) = {tally}, but total is {dom['total']}")

    counts = instance.get("counts")
    findings = instance.get("findings")
    changes = instance.get("changes")
    if isinstance(counts, dict) and isinstance(findings, list) and \
            all(k in counts for k in ("p0", "p1", "p2", "p3")):
        declared = counts["p0"] + counts["p1"] + counts["p2"] + counts["p3"]
        overflow = counts.get("overflow", 0)
        if declared != len(findings) + overflow:
            errors.append(
                f"$.counts: p0+p1+p2+p3 = {declared}, but len(findings) ({len(findings)}) + "
                f"overflow ({overflow}) = {len(findings) + overflow}")

        actual_sev = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
        for f in findings:
            if isinstance(f, dict) and f.get("severity") in actual_sev:
                actual_sev[f["severity"]] += 1
        # P0/P1 drive summary.pass (schema allOf), so they may NEVER be hidden in overflow —
        # exact equality, not just a lower bound. P2/P3 may legitimately be capped and pushed
        # into overflow, so a declared count may exceed but never fall below what's itemised.
        for sev in ("P0", "P1"):
            key = sev.lower()
            declared_sev = counts[key]
            if isinstance(declared_sev, int) and declared_sev != actual_sev[sev]:
                errors.append(
                    f"$.counts.{key}: declared {declared_sev}, but findings[] contains "
                    f"{actual_sev[sev]} finding(s) with severity {sev!r} — {sev} may never be "
                    f"hidden in overflow, since summary.pass is computed from this count")
        for sev in ("P2", "P3"):
            key = sev.lower()
            declared_sev = counts[key]
            if isinstance(declared_sev, int) and declared_sev < actual_sev[sev]:
                errors.append(
                    f"$.counts.{key}: declared {declared_sev}, but findings[] contains "
                    f"{actual_sev[sev]} finding(s) with severity {sev!r} — a declared count may "
                    f"not be less than what is actually itemised")

    summary = instance.get("summary")
    if isinstance(summary, dict) and summary.get("baseline") == "absent":
        if isinstance(changes, dict):
            nonzero = [k for k in ("regressed", "unchanged", "resolved") if changes.get(k, 0)]
            if nonzero:
                errors.append(
                    f"$.changes: baseline is 'absent' but {nonzero} is non-zero — with no "
                    f"baseline to diff against, every finding is 'new' by definition")
        if isinstance(findings, list):
            not_new = [f.get("id", "?") for f in findings if f.get("status") != "new"]
            if not_new:
                errors.append(
                    f"$.findings: baseline is 'absent' but {not_new} has a non-'new' status — "
                    f"there is no baseline for a finding to be regressed/unchanged against")

    if isinstance(changes, dict) and isinstance(findings, list) and \
            all(k in changes for k in ("new", "regressed", "unchanged")):
        open_now = changes["new"] + changes["regressed"] + changes["unchanged"]
        overflow = counts.get("overflow", 0) if isinstance(counts, dict) else 0
        listed = len(findings) + overflow
        if open_now != listed:
            errors.append(
                f"$.changes: new({changes['new']}) + regressed({changes['regressed']}) + "
                f"unchanged({changes['unchanged']}) = {open_now}, but len(findings) "
                f"({len(findings)}) + overflow ({overflow}) = {listed} — `resolved` is not part "
                f"of this sum because a resolved finding is not reported")

        actual_status = {"new": 0, "regressed": 0, "unchanged": 0}
        for f in findings:
            if isinstance(f, dict) and f.get("status") in actual_status:
                actual_status[f["status"]] += 1
        # An overflow'd finding still has SOME status, so exact equality isn't safe here — but
        # a declared count below what's actually itemised is exactly the reviewer's bypass.
        for status in ("new", "regressed", "unchanged"):
            declared_status = changes[status]
            if isinstance(declared_status, int) and declared_status < actual_status[status]:
                errors.append(
                    f"$.changes.{status}: declared {declared_status}, but findings[] contains "
                    f"{actual_status[status]} finding(s) with status {status!r} — a declared "
                    f"count may not be less than what is actually itemised")

    stack = instance.get("stack")
    per_stack = instance.get("per_stack")
    if isinstance(stack, str):
        declared_stacks = [s.strip() for s in stack.split(",") if s.strip()]
        multi_stack = "," in stack
        if multi_stack and not isinstance(per_stack, dict):
            errors.append(
                f"$.stack declares multiple stacks ({stack!r}) but per_stack is missing — a "
                f"consumer cannot tell which stack a domain failure came from")
        elif isinstance(per_stack, dict):
            missing = [s for s in declared_stacks if s not in per_stack]
            if missing:
                errors.append(f"$.per_stack is missing an entry for {missing}")
            extra = [s for s in per_stack if s not in declared_stacks]
            if extra:
                errors.append(
                    f"$.per_stack has an entry for {extra}, which is not in the declared stack "
                    f"{stack!r} — a consumer cannot tell where an undeclared stack's result "
                    f"came from")

            if multi_stack:
                # A count-only per_stack (pass/fail/na) cannot distinguish two stacks failing
                # the SAME domain from two stacks failing DIFFERENT domains — the fail-count-only
                # check below is a lower bound, not the true union. Making failing_domains
                # mandatory here (not merely used-if-present) is what actually closes that gap,
                # rather than leaving it an opt-in a report can silently omit.
                no_failing_domains = [
                    s for s in declared_stacks
                    if isinstance(per_stack.get(s), dict)
                    and not isinstance(per_stack[s].get("failing_domains"), list)
                ]
                if no_failing_domains:
                    errors.append(
                        f"$.per_stack is missing failing_domains for {no_failing_domains} — "
                        f"required on every stack in a multi-stack report, so the validator can "
                        f"compute the exact union of failing domains across stacks instead of "
                        f"only a lower bound (two stacks each failing a DIFFERENT domain is 2 "
                        f"failing domains overall, not 1, and a fail-count-only per_stack cannot "
                        f"tell that apart from both stacks failing the SAME domain)")

            domain_total = dom.get("total", 10) if isinstance(dom, dict) else 10
            max_stack_fail = None
            # True only if every per_stack entry names WHICH domains failed — only then can the
            # exact union be computed. Two stacks each failing one DIFFERENT domain is 2 failing
            # domains overall, not 1; a count-only fail=1/fail=1 cannot distinguish that from both
            # stacks failing the SAME domain, so the fallback below is a lower bound, not exact.
            all_have_failing_domains = bool(per_stack)
            failing_domain_union = set()
            for s, entry in per_stack.items():
                if not isinstance(entry, dict) or \
                        not all(k in entry for k in ("pass", "fail", "na")) or \
                        not all(isinstance(entry[k], int) for k in ("pass", "fail", "na")):
                    all_have_failing_domains = False
                    continue
                stack_tally = entry["pass"] + entry["fail"] + entry["na"]
                if stack_tally != domain_total:
                    errors.append(
                        f"$.per_stack.{s}: pass({entry['pass']}) + fail({entry['fail']}) + "
                        f"na({entry['na']}) = {stack_tally}, but total is {domain_total} — "
                        f"every stack evaluates the same fixed domain set")
                if max_stack_fail is None or entry["fail"] > max_stack_fail:
                    max_stack_fail = entry["fail"]

                fd = entry.get("failing_domains")
                if isinstance(fd, list) and all(isinstance(d, int) for d in fd):
                    if len(fd) != entry["fail"]:
                        errors.append(
                            f"$.per_stack.{s}.failing_domains lists {len(fd)} domain(s), but "
                            f"fail={entry['fail']} — it must list exactly the failing domains")
                    if len(set(fd)) != len(fd):
                        errors.append(
                            f"$.per_stack.{s}.failing_domains contains a duplicate domain number")
                    failing_domain_union |= set(fd)
                else:
                    all_have_failing_domains = False

            if max_stack_fail is not None and isinstance(dom, dict) and \
                    isinstance(dom.get("fail"), int):
                if all_have_failing_domains:
                    if dom["fail"] != len(failing_domain_union):
                        errors.append(
                            f"$.security_domains.fail ({dom['fail']}) does not equal the union "
                            f"of every per_stack failing_domains ({sorted(failing_domain_union)}"
                            f" = {len(failing_domain_union)} distinct domain(s)) — e.g. one "
                            f"stack failing domain 1 and another failing domain 2 is 2 failing "
                            f"domains overall, not 1")
                elif dom["fail"] < max_stack_fail:
                    errors.append(
                        f"$.security_domains.fail ({dom['fail']}) is less than the largest "
                        f"per_stack fail count ({max_stack_fail}) — a domain that fails in any "
                        f"stack must be counted as failing at the top level too "
                        f"(report-schema.json's per_stack rule), or summary.pass can go true "
                        f"while a stack has an open failure. (This is only a lower-bound check: "
                        f"add failing_domains to every per_stack entry for an exact union check.)")

    suppressed = instance.get("suppressed")
    if isinstance(suppressed, list):
        valid_rules = _load_valid_suppression_rules()
        for i, s in enumerate(suppressed):
            if isinstance(s, dict) and isinstance(s.get("rule"), int) and \
                    valid_rules and s["rule"] not in valid_rules:
                errors.append(
                    f"$.suppressed[{i}].rule: {s['rule']} is not one of the numbered rules in "
                    f"SKILL.md's § False-Positive Suppression Rules ({sorted(valid_rules)})")

    return errors


def validate_report(instance, schema: dict = None) -> list:
    """Errors from the stdlib schema checker plus the semantic invariants. This is the ONE
    function the schema test suite and the forward-eval grader both call — see the module
    docstring for why a second, drifting rule list is the failure this replaces."""
    schema = schema or load_schema()
    return validate_schema(instance, schema) + _check_invariants(instance)
