#!/usr/bin/env python3
"""Regression case validator and grader.

Three usages:

  --self-test           grade the grader against fixtures whose verdict is known by construction
  --validate            validate tests/cases.json's own integrity + rule coverage + id sync with cases.md
  --grade DIR           grade already-recorded Agent output (DIR/<case_id>.md), print a pass/fail report
                        exit code: fail>0 or missing>0 or pass==0 always means 1
                        ("not a single scenario was run" must be red, not green)
  --list [--tier T]     list cases

Expectation fields on a case (all optional, at least one required):

  must_include        regex, whole document. Positive, so a stray match is harmless.
  forbidden_in_ddl    regex, checked ONLY inside the emitted primary DDL. Use this for
                      every syntax token: a correct answer often has to *name* the thing
                      it refuses ("Oracle mode has no AUTO_INCREMENT_MODE"), and a
                      whole-document prohibition fails that answer.
  must_not_include    regex, whole document, but clause-scoped and refutation-aware --
                      a clause that refutes the claim does not count as asserting it.
                      For prose claims only ("design failed"), never for syntax.
  expected_checks     {check_name: verdict}, graded against the `checks:` block.

On the boundary of automation (understand this honestly):
  This script **cannot** automatically drive the Agent to produce answers --
  that needs an LLM evaluator.
  What it automates is the two steps of "spec completeness" and "grading":
    1. --validate can run after every rule change, preventing the rule list
       from drifting apart from the cases and the docs;
    2. --grade mechanically judges pass/fail after a human (or an LLM in CI)
       has run the cases and dropped the output into DIR.
  So what can currently be proven is "the rules are written correctly and the
  cases are complete", not "the Agent never regresses in any scenario".
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CASES_JSON = os.path.join(ROOT, "tests", "cases.json")
CASES_MD = os.path.join(ROOT, "tests", "cases.md")
TIERS = ("golden", "invalid", "boundary")


def load():
    with open(CASES_JSON, encoding="utf-8") as f:
        return json.load(f)


def validate(spec):
    errors, warnings = [], []
    rules = spec.get("rules", {})
    cases = spec.get("cases", [])

    if not rules:
        errors.append("rules is empty")
    if not cases:
        errors.append("cases is empty")

    # the rule entries themselves
    for rid, r in rules.items():
        if not re.fullmatch(r"R-[A-Z0-9-]+", rid):
            errors.append(f"rule id does not follow naming convention: {rid}")
        for k in ("desc", "source"):
            if not r.get(k):
                errors.append(f"rule {rid} is missing {k}")
        src = r.get("source")
        if src and not os.path.exists(os.path.join(ROOT, src)):
            errors.append(f"rule {rid}'s source does not exist: {src}")

    # the case entries
    seen_ids = set()
    for c in cases:
        cid = c.get("id")
        if not cid:
            errors.append(f"case missing id: {c}")
            continue
        if cid in seen_ids:
            errors.append(f"duplicate case id: {cid}")
        seen_ids.add(cid)
        if c.get("tier") not in TIERS:
            errors.append(f"{cid}: tier must be one of {TIERS}, got {c.get('tier')!r}")
        if not c.get("title"):
            errors.append(f"{cid}: missing title")
        if not c.get("input"):
            errors.append(f"{cid}: missing input")
        crules = c.get("rules") or []
        if not crules:
            errors.append(f"{cid}: not linked to any rule")
        for rid in crules:
            if rid not in rules:
                errors.append(f"{cid}: references undefined rule {rid}")
        inc = c.get("must_include") or []
        exc = c.get("must_not_include") or []
        ddl = c.get("forbidden_in_ddl") or []
        chk = c.get("expected_checks") or {}
        if not inc and not exc and not ddl and not chk:
            errors.append(f"{cid}: has no gradable expectation (must_include / "
                          f"must_not_include / forbidden_in_ddl / expected_checks)")
        for pat in list(inc) + list(exc) + list(ddl):
            try:
                re.compile(pat)
            except re.error as e:
                errors.append(f"{cid}: invalid regex {pat!r}: {e}")
        # The greedy fence idiom reads as "inside a SQL block" but scopes nothing --
        # `[\s\S]*` runs past the closing fence into the prose. Anything meant to be
        # DDL-scoped belongs in forbidden_in_ddl, which parses the fences properly.
        for pat in list(exc):
            if "```" in pat:
                errors.append(f"{cid}: must_not_include pattern {pat!r} tries to scope "
                              f"itself to a code fence; use forbidden_in_ddl instead")
        if not isinstance(chk, dict):
            errors.append(f"{cid}: expected_checks must be an object of name -> verdict")

    # rule coverage: every rule needs at least one case
    covered = {rid for c in cases for rid in (c.get("rules") or [])}
    uncovered = sorted(set(rules) - covered)
    for rid in uncovered:
        errors.append(f"rule {rid} is not covered by any regression case")

    # sync ids with cases.md (prevents the two case sets from drifting apart)
    if os.path.exists(CASES_MD):
        with open(CASES_MD, encoding="utf-8") as f:
            md = f.read()
        md_ids = set(re.findall(r"^##\s+([GIB]\d+)\s", md, re.M))
        only_md = sorted(md_ids - seen_ids)
        only_json = sorted(seen_ids - md_ids)
        for cid in only_md:
            errors.append(f"cases.md has {cid} but cases.json does not")
        for cid in only_json:
            errors.append(f"cases.json has {cid} but cases.md does not")
    else:
        warnings.append("cases.md not found, skipping id sync check")

    return errors, warnings, {"rules": len(rules), "cases": len(cases),
                              "coverage": len(covered)}


# ─────────────────────── Output parsing (structure, not raw regex) ───────────────────────
#
# Why this exists. Grading used to run every pattern over the whole document with
# `re.search`, which produced two classes of wrong verdict:
#
#   1. FALSE FAILURE on a correct answer. I12 forbade `AUTO_INCREMENT_MODE`, but the
#      *right* answer says "Oracle mode has no AUTO_INCREMENT_MODE -- use IDENTITY".
#      Explaining the prohibition tripped the prohibition. Same for G2's `PARTITION BY
#      KEY` / `COLUMNS` / `VALUES IN`, I14's salt/bucket advice, and every case whose
#      correct answer has to name the thing it is refusing.
#   2. FALSE PASS *and* false failure from the `` ```sql[\s\S]*X `` idiom, which reads
#      as "X inside a SQL block" but does not scope anything: `[\s\S]*` is greedy and
#      runs past the closing fence, so it matches X anywhere later in the document,
#      including in prose. Meanwhile a genuine violation in a *second* SQL block was
#      still caught only by accident.
#
# The fix is to grade against structure. Syntax prohibitions are checked inside the
# emitted DDL, where a mention cannot be an explanation; prose prohibitions are checked
# clause by clause with refutation awareness.

FENCE_RE = re.compile(r"^[ \t]*```([A-Za-z0-9_+-]*)[ \t]*$")
HEADING_RE = re.compile(r"^[ \t]*(#{1,6})[ \t]+(.*\S)[ \t]*$")

#: A heading is the primary-DDL section when it names the DDL and is not the candidate
#: one. "2 / 2b. Primary DDL and Candidate DDL" style headings are handled by requiring
#: "primary" and rejecting a heading that is *only* about candidates.
_PRIMARY_HINT = re.compile(r"primary\s+ddl|primary\s+statement|\bddl\b", re.I)
_CANDIDATE_HINT = re.compile(r"candidate|alternative|rejected|anti-?example|wrong|"
                             r"counter-?example|do\s+not\s+use", re.I)


def fenced_blocks(text):
    """Yield (lang, body, heading) for every fenced block, tagged with its heading.

    Tracking the enclosing heading is what makes "in the PRIMARY DDL" answerable. A
    block under "Candidate DDL" is deliberately allowed to contain unconfirmed syntax --
    that is the whole point of the candidate section -- so it must not be graded as if
    it were the primary statement.
    """
    out = []
    heading = ""
    lang = None
    buf = []
    for ln in text.split("\n"):
        if lang is None:
            m = FENCE_RE.match(ln)
            if m:
                lang = m.group(1).lower()
                buf = []
                continue
            h = HEADING_RE.match(ln)
            if h:
                heading = h.group(2)
            continue
        if FENCE_RE.match(ln):
            out.append((lang, "\n".join(buf), heading))
            lang = None
            continue
        buf.append(ln)
    if lang is not None:                      # unterminated fence: keep what we have
        out.append((lang, "\n".join(buf), heading))
    return out


def _looks_like_ddl(body):
    return re.search(r"\b(CREATE|ALTER|DROP)\s+(TABLE|INDEX|TABLEGROUP|SEQUENCE)\b",
                     body, re.I) is not None


def primary_ddl(text):
    """The SQL the user would actually run, as one string.

    Selection order, most specific first:
      1. blocks under a heading that names the primary DDL;
      2. if the output has no such heading, every DDL-looking block that is NOT under a
         candidate / anti-example heading.
    Returns "" when the output contains no DDL at all -- the caller reports that as a
    contract violation rather than passing the case by default.
    """
    blocks = fenced_blocks(text)
    primary = [b for lang, b, h in blocks
               if _PRIMARY_HINT.search(h) and not _CANDIDATE_HINT.search(h)]
    if primary:
        return "\n".join(primary)
    return "\n".join(b for lang, b, h in blocks
                     if _looks_like_ddl(b) and not _CANDIDATE_HINT.search(h))


#: Clause-level refutation markers. Deliberately clause-scoped, not sentence- or
#: window-scoped: a window guard is a bypass, because an adjacent sentence that happens
#: to contain "not" would excuse a genuine violation next to it.
REFUTATION = (
    "has no", "have no", "there is no", "no such", "does not", "do not", "don't",
    "did not", "cannot", "can't", "must not", "never", "avoid", "forbidden",
    "prohibited", "unsupported", "not supported", "is not", "are not", "was not",
    "instead of", "rather than", "not ", "wrong", "incorrect", "myth", "misconception",
    "unlike", "reject", "refus", "illegal", "syntax error", "would fail", "not a",
)

_CLAUSE_SPLIT = re.compile(r"(?:\n|(?<=[.;:!?])\s|\s—\s|\s--\s|\s\|\s)")


def clauses(text):
    """Split prose into clauses for refutation-aware matching.

    Splitting on `;` matters: "X is wrong; use X" would otherwise let the refutation in
    the first clause excuse the recommendation in the second.
    """
    return [c for c in _CLAUSE_SPLIT.split(text) if c.strip()]


def prose_violation(text, pattern):
    """Return the first clause that asserts `pattern` without refuting it, else None.

    The matched span is masked before the refutation scan so that a marker appearing
    *inside* the pattern's own text cannot excuse it -- e.g. forbidding the phrase
    "cannot be designed" must not be self-excused by the "cannot" it contains.

    **Known limit, stated rather than papered over.** Refutation awareness on free prose
    cannot be made airtight: a clause that asserts the forbidden claim *and* happens to
    negate something else ("the table must be a partitioned table, not a standalone one")
    is excused. `GRADER_FIXTURES` carries that case explicitly so the behaviour is a
    documented decision, not a surprise. The residual error is a false PASS, which for a
    regression grader is the safer direction than a false FAIL -- but it is why every
    *syntax* prohibition belongs in `forbidden_in_ddl`, which is structural and exact,
    and why a new expectation about a verdict should use `expected_checks` rather than
    hunting for a phrase.
    """
    rx = re.compile(pattern, re.I)
    for cl in clauses(text):
        m = rx.search(cl)
        if not m:
            continue
        masked = (cl[:m.start()] + " " * (m.end() - m.start()) + cl[m.end():]).lower()
        if not any(marker in masked for marker in REFUTATION):
            return cl.strip()
    return None


def grade_one(case, text):
    """Grade one recorded output. Returns a list of failure strings (empty == pass)."""
    fails = []

    for pat in case.get("must_include") or []:
        if not re.search(pat, text, re.I):
            fails.append(f"missing: /{pat}/")

    forbidden_ddl = case.get("forbidden_in_ddl") or []
    if forbidden_ddl:
        ddl = primary_ddl(text)
        if not ddl.strip():
            fails.append("no primary DDL block found -- the output does not follow the "
                         "Section 5 format, so DDL-scoped rules cannot be graded")
        else:
            for pat in forbidden_ddl:
                m = re.search(pat, ddl, re.I)
                if m:
                    line = next((l for l in ddl.split("\n")
                                 if re.search(pat, l, re.I)), m.group(0))
                    fails.append(f"forbidden in primary DDL: /{pat}/ -> {line.strip()[:100]}")

    for pat in case.get("must_not_include") or []:
        hit = prose_violation(text, pat)
        if hit is not None:
            fails.append(f"asserted without refuting: /{pat}/ -> {hit[:100]}")

    for name, want in (case.get("expected_checks") or {}).items():
        m = re.search(rf"^\s*{re.escape(name)}:\s*$", text, re.M)
        block = text[m.end():] if m else ""
        got = re.search(r"^\s*result:\s*(\S+)", block, re.M) if m else None
        if got is None:
            fails.append(f"checks.{name}.result not found (expected {want})")
        elif got.group(1).strip().rstrip(",") != want:
            fails.append(f"checks.{name}.result = {got.group(1)}, expected {want}")

    return fails


def grade(spec, outdir):
    results = []
    for c in spec["cases"]:
        path = os.path.join(outdir, f"{c['id']}.md")
        if not os.path.exists(path):
            results.append((c["id"], "missing", []))
            continue
        with open(path, encoding="utf-8") as f:
            text = f.read()
        fails = grade_one(c, text)
        results.append((c["id"], "fail" if fails else "pass", fails))
    return results


# ─────────────────────────── Grading the grader ───────────────────────────
#
# A grader is a measuring instrument, and an uncalibrated one silently rewrites every
# result it produces. These fixtures are the calibration: each is a synthetic answer
# whose correct verdict is known by construction, so a change to the parsing above that
# starts passing violations (or failing correct answers) fails here instead of quietly
# corrupting a future --grade run.

_CORRECT_ORACLE_AUTOINC = """\
## 2. Primary DDL

```sql
CREATE TABLE T_ORDER (
  ID NUMBER GENERATED BY DEFAULT AS IDENTITY,
  AMT NUMBER(18,2),
  PRIMARY KEY (ID)
);
```

## 3. Design rationale

Oracle mode has no AUTO_INCREMENT_MODE and no auto_increment_cache_size -- the entire
AUTO_INCREMENT family is MySQL-only, so writing it here would be a syntax error.
Use the IDENTITY column property instead, or CREATE SEQUENCE for cross-table numbering.
"""

_VIOLATING_ORACLE_AUTOINC = """\
## 2. Primary DDL

```sql
CREATE TABLE T_ORDER (
  ID NUMBER,
  PRIMARY KEY (ID)
) AUTO_INCREMENT_MODE = 'NOORDER';
```

## 3. Design rationale

Numbering is handled by the auto-increment mode above.
"""

_CANDIDATE_ONLY = """\
## 2. Primary DDL

```sql
CREATE TABLE t (id BIGINT PRIMARY KEY, stat_day DATE)
PARTITION BY RANGE COLUMNS(stat_day) (PARTITION pmax VALUES LESS THAN (MAXVALUE));
```

## 2b. Candidate DDL

```sql
CREATE TABLE t (id BIGINT PRIMARY KEY, stat_day DATE)
DYNAMIC_PARTITION_POLICY = (ENABLE = true, TIME_UNIT = 'day');
```
"""

_PROSE_REFUTED = """\
Conflicting dimensions are normal, not a design failure; we resolve it with a global index.
This design is not infeasible -- both options are quantified below.
"""

_PROSE_ASSERTED = """\
The two dimensions conflict, so the design failed and cannot be designed as requested.
"""

#: (label, case fragment, output, expect_pass)
GRADER_FIXTURES = [
    ("correct Oracle answer that EXPLAINS the prohibition",
     {"forbidden_in_ddl": ["AUTO_INCREMENT_MODE", "auto_increment_cache_size"]},
     _CORRECT_ORACLE_AUTOINC, True),
    ("Oracle answer that actually EMITS the forbidden option",
     {"forbidden_in_ddl": ["AUTO_INCREMENT_MODE", "auto_increment_cache_size"]},
     _VIOLATING_ORACLE_AUTOINC, False),
    ("whole-document regex would have failed the correct answer",
     {"must_not_include": ["AUTO_INCREMENT_MODE"]},
     _CORRECT_ORACLE_AUTOINC, True),
    ("C2 syntax confined to the candidate section is allowed",
     {"forbidden_in_ddl": ["DYNAMIC_PARTITION_POLICY"]},
     _CANDIDATE_ONLY, True),
    ("refuted prose claim is allowed",
     {"must_not_include": ["design failed", "cannot be designed", "infeasible"]},
     _PROSE_REFUTED, True),
    ("asserted prose claim is caught",
     {"must_not_include": ["design failed", "cannot be designed"]},
     _PROSE_ASSERTED, False),
    ("missing must_include is caught",
     {"must_include": ["GENERATED BY DEFAULT AS IDENTITY", "ThisWillNeverAppear"]},
     _CORRECT_ORACLE_AUTOINC, False),
    ("DDL-scoped rule on an output with no DDL is a failure, not a pass",
     {"forbidden_in_ddl": ["AUTO_INCREMENT_MODE"]},
     _PROSE_REFUTED, False),
    ("expected check verdict matches",
     {"expected_checks": {"partition_key_selection": "fail"}},
     "checks:\n  partition_key_selection:\n    result: fail\n", True),
    ("expected check verdict mismatch is caught",
     {"expected_checks": {"partition_key_selection": "fail"}},
     "checks:\n  partition_key_selection:\n    result: pass\n", False),
    # Documented limit, not an aspiration: an incidental negation elsewhere in the same
    # clause excuses the claim. Recorded as expect_pass=True because that IS the current
    # behaviour -- if a future change makes prose matching stricter, this fixture fails
    # and the docstring above gets updated with it.
    ("KNOWN LIMIT: incidental negation in the same clause excuses the claim",
     {"must_not_include": ["must be a partitioned table"]},
     "NOORDER requires that the table must be a partitioned table, not a standalone one.\n",
     True),
]


def grader_self_test():
    bad = 0
    for label, frag, out, expect_pass in GRADER_FIXTURES:
        fails = grade_one(frag, out)
        got_pass = not fails
        if got_pass != expect_pass:
            bad += 1
            want = "pass" if expect_pass else "fail"
            print(f"[error] grader self-test: expected {want}: {label}")
            for f in fails:
                print(f"          {f}")
    # the greedy idiom the old spec used must be gone from the case file, or the fix is
    # only half applied -- the patterns would still be graded by the old path
    spec = load()
    greedy = [(c["id"], p) for c in spec["cases"]
              for p in (c.get("must_not_include") or []) if "```" in p]
    for cid, p in greedy:
        bad += 1
        print(f"[error] {cid}: must_not_include still uses the greedy fence idiom "
              f"{p!r} -- move it to forbidden_in_ddl")
    n = len(GRADER_FIXTURES)
    if bad:
        print(f"grader self-test: FAILED ({bad} issue(s), {n} fixtures)")
        return 1
    print(f"grader self-test: {n}/{n} fixtures graded correctly "
          f"(structure-scoped DDL rules, refutation-aware prose rules)")
    return 0


def main():
    args = sys.argv[1:]
    if args and args[0] == "--self-test":
        return grader_self_test()
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    spec = load()

    if args[0] == "--validate":
        errors, warnings, stats = validate(spec)
        for w in warnings:
            print(f"[warn] {w}")
        for e in errors:
            print(f"[error] {e}")
        print(f"\n{stats['rules']} rule(s), {stats['cases']} case(s), "
              f"{stats['coverage']} rule(s) covered")
        if errors:
            print(f"validate: FAILED ({len(errors)} issue(s))")
            return 1
        print("validate: OK (rule list, cases, and cases.md are all consistent)")
        return 0

    if args[0] == "--list":
        tier = None
        if "--tier" in args:
            tier = args[args.index("--tier") + 1]
        for c in spec["cases"]:
            if tier and c["tier"] != tier:
                continue
            print(f"{c['id']:<5} [{c['tier']:<9}] {c['title']}  "
                  f"rules={','.join(c.get('rules') or [])}")
        return 0

    if args[0] == "--grade":
        if len(args) < 2:
            print("usage: run_cases.py --grade <dir>", file=sys.stderr)
            return 2
        outdir = args[1]
        if not os.path.isdir(outdir):
            print(f"directory does not exist: {outdir}", file=sys.stderr)
            return 2
        results = grade(spec, outdir)
        npass = sum(1 for _, s, _ in results if s == "pass")
        nfail = sum(1 for _, s, _ in results if s == "fail")
        nmiss = sum(1 for _, s, _ in results if s == "missing")
        for cid, status, fails in results:
            print(f"{cid:<5} {status.upper()}")
            for f in fails:
                print(f"        {f}")
        print(f"\npass={npass} fail={nfail} missing={nmiss} / {len(results)}")
        if nmiss:
            print(f"[error] {nmiss} case(s) have no recorded output -- "
                  f"**not run does not mean passed**, CI must judge this as a failure")
        if not results:
            print("[error] the case set is empty, nothing to grade")
        if npass == 0 and results:
            print("[error] zero cases passed, this almost certainly means the eval environment is broken")
        # not-run / failed / zero-passed all count as failure: avoids CI turning
        # "not a single scenario ran" green
        return 1 if (nfail or nmiss or not results or npass == 0) else 0

    print(f"unknown argument: {args[0]}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
