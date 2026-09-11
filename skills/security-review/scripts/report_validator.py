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


# --- Validation precondition layer -------------------------------------------------
# Round-1 of this fix hardened the ARITHMETIC sites and left the adjacent ones: a
# `findings[].severity` of `[]` was still used as a dict key (TypeError), a `findings`
# element of `null` still had `.get()` called on it (AttributeError), and the eval entry
# still ran `int()` on a count (ValueError). Patching site by site kept leaving the next
# one, because the precondition — "this value has the declared type" — was never
# established anywhere.
#
# So it is established ONCE here, from the schema, and every invariant below reads the
# resulting view. A value only appears in the view if its runtime type matches what the
# schema declares (via `type`, `enum` or `const`); anything else is reported and dropped.
# That makes the invariants total: there is no reachable dict lookup, attribute access or
# numeric conversion over an unvalidated value.

_JSON_PY_TYPES = {
    "object": (dict,),
    "array": (list,),
    "string": (str,),
    "boolean": (bool,),
    "integer": (int,),
    "number": (int, float),
    "null": (type(None),),
}


def _declared_types(subschema: dict):
    """Python types this subschema accepts, or None when it declares none.

    `type` when present; otherwise derived from `enum`/`const` members, which is how this
    schema spells most of its scalars (`severity` is an enum, `total` is a const)."""
    if not isinstance(subschema, dict):
        return None
    declared = subschema.get("type")
    if isinstance(declared, str):
        return _JSON_PY_TYPES.get(declared)
    if isinstance(declared, list):
        out = tuple({p for d in declared for p in _JSON_PY_TYPES.get(d, ())})
        return out or None
    for key in ("enum", "const"):
        if key in subschema:
            members = subschema[key] if key == "enum" else [subschema[key]]
            if isinstance(members, list) and members:
                return tuple({type(m) for m in members})
    return None


_TYPE_NAMES = {int: "an integer", float: "a number", str: "a string", bool: "a boolean",
               dict: "an object", list: "an array", type(None): "null"}


def _name_types(types) -> str:
    return " or ".join(sorted({_TYPE_NAMES.get(ty, ty.__name__) for ty in types}))


def _type_ok(value, types) -> bool:
    if types is None:
        return True
    # `bool` is an `int` subclass: a boolean must never satisfy an integer field.
    if bool not in types and isinstance(value, bool):
        return False
    return isinstance(value, types)


def typed_view(instance, subschema: dict, path: str = "$"):
    """Return (view, errors, degraded).

    `view` mirrors `instance` but contains only values whose runtime type matches the
    schema. `degraded` holds the paths of arrays or objects from which something was
    dropped — an invariant about the CARDINALITY of a degraded container is not
    computable and must be skipped rather than reported against a shortened list."""
    errors, degraded = [], set()
    types = _declared_types(subschema)
    if not _type_ok(instance, types):
        return None, [
            f"{path} must be {_name_types(types)}, got {type(instance).__name__} "
            f"({instance!r}) — every invariant that reads it is skipped, not evaluated "
            f"over a value of the wrong type"], {path}

    if isinstance(instance, dict):
        props = subschema.get("properties") or {}
        extra = subschema.get("additionalProperties")
        view = {}
        for key, value in instance.items():
            child = props.get(key)
            if child is None and isinstance(extra, dict):
                child = extra
            if child is None:
                view[key] = value        # undeclared: the schema layer decides its fate
                continue
            sub_view, sub_errors, sub_degraded = typed_view(value, child, f"{path}.{key}")
            errors.extend(sub_errors)
            degraded |= sub_degraded
            if sub_errors:
                degraded.add(path)
            # Keep a PARTIAL container: dropping the whole object because one child was
            # wrongly typed loses its healthy siblings, and every invariant that reads
            # them then goes silent. Only the offending child is withheld — which is
            # exactly what `sub_view is None and sub_errors` identifies.
            if not (sub_view is None and sub_errors):
                view[key] = sub_view
        return view, errors, degraded

    if isinstance(instance, list):
        item_schema = subschema.get("items")
        view = []
        for i, element in enumerate(instance):
            if not isinstance(item_schema, dict):
                view.append(element)
                continue
            sub_view, sub_errors, sub_degraded = typed_view(
                element, item_schema, f"{path}[{i}]")
            errors.extend(sub_errors)
            degraded |= sub_degraded
            if sub_errors:
                degraded.add(path)
            # Same rule: an element that is wholly the wrong type is dropped (and the array
            # marked degraded, so nothing counts its members); an element that is the right
            # type with one bad field is kept without that field.
            if not (sub_view is None and sub_errors):
                view.append(sub_view)
        return view, errors, degraded

    return instance, errors, degraded


def safe_int(value):
    """`int(value)` for a value that may be anything, or None when it is not an integer.

    The eval grader ran `int(counts.get(k, 0) or 0)` on model output and died with
    ValueError on `"one"` — before the validator it was about to call could report the
    defect. A converter that cannot raise is the only safe form at that boundary."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _ints(mapping: dict, keys, path: str, errors: list, invariant: str):
    """Return `[mapping[k] for k in keys]` as ints, or None when any is missing or not an int.

    Presence is not type. `all(k in dom for k in ("pass", "fail", "na", "total"))` passed for
    `{"pass": "7", ...}` and the next line evaluated `"7" + 3`, so a wrong type raised
    TypeError out of a function whose entire contract is to RETURN a list of errors — the
    forward-eval grader crashed on a malformed model report instead of reporting the defect.

    So: a type error is recorded here, naming the invariant it makes uncheckable, and the
    dependent arithmetic is skipped. Summing a string is not a weaker check, it is no check.
    `typed_view` is now the primary guarantee — a wrongly-typed value never reaches this
    function through `validate_report`. This stays as the belt for a direct caller of
    `_check_invariants`, and because a presence check is still needed either way.
    A missing key is left to the schema layer, which reports absence precisely. `bool` is
    rejected explicitly — it is an `int` subclass in Python, so `true` would otherwise pass
    as a count and arithmetic silently treat it as 1."""
    out = []
    for k in keys:
        if k not in mapping:
            return None
        v = mapping[k]
        if isinstance(v, bool) or not isinstance(v, int):
            errors.append(
                f"{path}.{k} must be an integer, got {type(v).__name__} ({v!r}) — "
                f"{invariant} cannot be evaluated over a non-integer")
            out = None
        elif out is not None:
            out.append(v)
    return out


def _int_or_none(value, path: str, errors: list, invariant: str):
    """Same discipline for a single optional integer (`counts.overflow`, `domains.total`)."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        errors.append(
            f"{path} must be an integer, got {type(value).__name__} ({value!r}) — "
            f"{invariant} cannot be evaluated over a non-integer")
        return None
    return value


def _check_invariants(instance, degraded=frozenset()) -> list:
    """The invariants JSON Schema cannot express, checked against ANY instance — not just a fixed
    canonical example. This is the fix for the gap where these were assertions against one
    hardcoded report rather than a rule enforced on every report.

    `instance` is expected to be a `typed_view`: every value present has its declared type.
    `degraded` names containers something was dropped from, whose cardinality is therefore
    unknown — an invariant that counts their members is skipped rather than computed over a
    shortened list."""
    errors = []
    if not isinstance(instance, dict):
        return errors
    countable = "$.findings" not in degraded

    dom = instance.get("security_domains")
    if isinstance(dom, dict):
        vals = _ints(dom, ("pass", "fail", "na", "total"), "$.security_domains", errors,
                     "the pass+fail+na == total tally")
        if vals:
            p, f_, na, total = vals
            if p + f_ + na != total:
                errors.append(
                    f"$.security_domains: pass({p}) + fail({f_}) + na({na}) = "
                    f"{p + f_ + na}, but total is {total}")

    counts = instance.get("counts")
    findings = instance.get("findings")
    changes = instance.get("changes")
    sev_counts = None
    if isinstance(counts, dict) and isinstance(findings, list) and countable:
        sev_counts = _ints(counts, ("p0", "p1", "p2", "p3"), "$.counts", errors,
                           "the p0+p1+p2+p3 == len(findings)+overflow reconciliation")
    if sev_counts:
        overflow = _int_or_none(counts.get("overflow", 0), "$.counts.overflow", errors,
                                "the findings reconciliation")
        declared = sum(sev_counts)
        if overflow is not None and declared != len(findings) + overflow:
            errors.append(
                f"$.counts: p0+p1+p2+p3 = {declared}, but len(findings) ({len(findings)}) + "
                f"overflow ({overflow}) = {len(findings) + overflow}")

        actual_sev = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
        for f in findings:
            if not isinstance(f, dict):
                continue
            sev = f.get("severity")
            # `in` on an unhashable value raises: `severity: []` died here with
            # "cannot use 'list' as a dict key". The view drops it, and this is the belt.
            if isinstance(sev, str) and sev in actual_sev:
                actual_sev[sev] += 1
        # P0/P1 drive summary.pass (schema allOf), so they may NEVER be hidden in overflow —
        # exact equality, not just a lower bound. P2/P3 may legitimately be capped and pushed
        # into overflow, so a declared count may exceed but never fall below what's itemised.
        by_key = dict(zip(("p0", "p1", "p2", "p3"), sev_counts))
        for sev in ("P0", "P1"):
            key = sev.lower()
            declared_sev = by_key[key]
            if declared_sev != actual_sev[sev]:
                errors.append(
                    f"$.counts.{key}: declared {declared_sev}, but findings[] contains "
                    f"{actual_sev[sev]} finding(s) with severity {sev!r} — {sev} may never be "
                    f"hidden in overflow, since summary.pass is computed from this count")
        for sev in ("P2", "P3"):
            key = sev.lower()
            declared_sev = by_key[key]
            if declared_sev < actual_sev[sev]:
                errors.append(
                    f"$.counts.{key}: declared {declared_sev}, but findings[] contains "
                    f"{actual_sev[sev]} finding(s) with severity {sev!r} — a declared count may "
                    f"not be less than what is actually itemised")

    summary = instance.get("summary")
    if isinstance(summary, dict) and summary.get("baseline") == "absent":
        if isinstance(changes, dict):
            # `if changes.get(k, 0)` alone is satisfied by the STRING "0", which is truthy.
            nonzero = [k for k in ("regressed", "unchanged", "resolved")
                       if isinstance(changes.get(k), int) and not isinstance(changes.get(k), bool)
                       and changes[k]]
            if nonzero:
                errors.append(
                    f"$.changes: baseline is 'absent' but {nonzero} is non-zero — with no "
                    f"baseline to diff against, every finding is 'new' by definition")
        if isinstance(findings, list):
            not_new = [f.get("id", "?") for f in findings
                       if isinstance(f, dict) and f.get("status") != "new"]
            if not_new:
                errors.append(
                    f"$.findings: baseline is 'absent' but {not_new} has a non-'new' status — "
                    f"there is no baseline for a finding to be regressed/unchanged against")

    change_counts = None
    if isinstance(changes, dict) and isinstance(findings, list) and countable:
        change_counts = _ints(changes, ("new", "regressed", "unchanged"), "$.changes", errors,
                              "the new+regressed+unchanged == open-findings reconciliation")
    if change_counts:
        open_now = sum(change_counts)
        overflow = _int_or_none(counts.get("overflow", 0) if isinstance(counts, dict) else 0,
                                "$.counts.overflow", errors,
                                "the open-findings reconciliation") or 0
        listed = len(findings) + overflow
        if open_now != listed:
            errors.append(
                f"$.changes: new({changes['new']}) + regressed({changes['regressed']}) + "
                f"unchanged({changes['unchanged']}) = {open_now}, but len(findings) "
                f"({len(findings)}) + overflow ({overflow}) = {listed} — `resolved` is not part "
                f"of this sum because a resolved finding is not reported")

        actual_status = {"new": 0, "regressed": 0, "unchanged": 0}
        for f in findings:
            if not isinstance(f, dict):
                continue
            status = f.get("status")
            if isinstance(status, str) and status in actual_status:
                actual_status[status] += 1
        # An overflow'd finding still has SOME status, so exact equality isn't safe here — but
        # a declared count below what's actually itemised is exactly the reviewer's bypass.
        for status, declared_status in zip(("new", "regressed", "unchanged"), change_counts):
            if declared_status < actual_status[status]:
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

            domain_total = _int_or_none(
                dom.get("total", 10) if isinstance(dom, dict) else 10,
                "$.security_domains.total", errors,
                "the per_stack pass+fail+na == total tally")
            if domain_total is None:
                domain_total = 10
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
    if isinstance(suppressed, list):  # elements guaranteed dicts by the view; guarded below
        valid_rules = _load_valid_suppression_rules()
        for i, s in enumerate(suppressed):
            if isinstance(s, dict) and isinstance(s.get("rule"), int) and \
                    valid_rules and s["rule"] not in valid_rules:
                errors.append(
                    f"$.suppressed[{i}].rule: {s['rule']} is not one of the numbered rules in "
                    f"SKILL.md's § False-Positive Suppression Rules ({sorted(valid_rules)})")

    return errors


def validated_view(instance, schema: dict = None):
    """Return (view, errors) for an arbitrary instance: the partial typed view, plus every
    schema and type error found reaching it.

    The public form of the precondition, for callers that need to TRAVERSE a report rather
    than only validate it. The eval grader walked raw `findings` before calling
    `validate_report`, so `findings: [null]`, `findings: "x"` and `findings: 7.5` crashed
    the grader on 48 of 2 552 matrix variants — the validator was safe and the call chain
    was not. A caller that reads this view instead cannot reach an unvalidated value, and
    what it cannot rate is already in `errors` as a contract defect."""
    schema = schema or load_schema()
    schema_errors = validate_schema(instance, schema)
    view, type_errors, degraded = typed_view(instance, schema)
    errors = list(dict.fromkeys(schema_errors + type_errors))
    if view is None:
        return {}, errors
    return view, list(dict.fromkeys(errors + _check_invariants(view, degraded)))


def validate_report(instance, schema: dict = None) -> list:
    """Errors from the stdlib schema checker plus the semantic invariants. This is the ONE
    function the schema test suite and the forward-eval grader both call — see the module
    docstring for why a second, drifting rule list is the failure this replaces."""
    # The precondition, established once: everything the invariants read has its declared
    # type. Type errors surface whether or not the schema layer names them, and the
    # invariants never see an unvalidated value. `validated_view` returns the same errors
    # plus the view, for callers that also need to traverse the report.
    return validated_view(instance, schema)[1]
