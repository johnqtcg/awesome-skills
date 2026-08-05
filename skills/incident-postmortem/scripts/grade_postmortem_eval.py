#!/usr/bin/env python3
"""Deterministic grader for the live forward evaluation.

Everything else in this skill's suite is model-free: it proves the rules exist, the
linter behaves, and the fixtures are self-consistent. It does NOT prove the thing the
skill is for — that a model given this skill selects the right mode, degrades honestly,
picks an RCA technique that fits the incident, redacts secrets, and does not invent
evidence. This grader measures that, from a real model response, without a second model
in the loop: every check below is a regex, a section lookup, or a call into
`lint_postmortem`.

Usage:
  grade_postmortem_eval.py <scenario.json> <response.md> [--json out.json]

Exit codes: 0 = every check passed, 1 = at least one check failed,
            2 = scenario or response unreadable.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

_LINT = Path(__file__).resolve().parent / "lint_postmortem.py"
_spec = importlib.util.spec_from_file_location("lint_postmortem_eval", _LINT)
lint_postmortem = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
sys.modules[_spec.name] = lint_postmortem
_spec.loader.exec_module(lint_postmortem)

# §9 section name -> heading matcher. Kept here rather than imported so a grader check
# cannot be silently weakened by an edit to the linter's own heading rules.
# Flags go in the compile() call, never inline: a second `(?mi)` inside an alternation
# is a hard PatternError on Python 3.11+, and it fails at import, not at match time.
_S = lambda p: re.compile(p, re.MULTILINE | re.IGNORECASE)  # noqa: E731
# The skill follows the user's language, so every matcher accepts both. A Chinese
# post-mortem previously scored as missing most of its sections.
SECTIONS = {
    "9.1": _S(r"^#{1,4}\s+.*(\bsummary\b|摘要|概述|总结)"),
    "9.2": _S(r"^#{1,4}\s+.*(\bmode\b.*\bdepth\b|模式.{0,2}深度)"
              r"|^\*\*(mode\s*&?\s*depth|模式.{0,2}深度)"),
    "9.3": _S(r"^#{1,4}\s+(timeline\b|.*(时间线|时间轴|时序))"),
    "9.4": _S(r"^#{1,4}\s+.*(root cause|根因|根本原因)"),
    "9.5": _S(r"^#{1,4}\s+.*(impact|影响)"),
    "9.6": _S(r"^#{1,4}\s+.*(what went well|做得好|值得肯定|亮点)"),
    "9.7": _S(r"^#{1,4}\s+(action items?\b|.*(行动项|待办项|改进项|整改项))"),
    "9.8": _S(r"^#{1,4}\s+.*(lessons|经验教训|教训)"),
    "9.9": _S(r"^#{1,4}\s+.*(uncovered risks|未覆盖风险|未覆盖的风险|遗留风险)"),
}

# A prose equivalent of §9.9, for responses whose artifact shape is pinned by the user.
UNCOVERED_PROSE_RE = re.compile(
    r"(?i)\b(not (analy|cover|trace|verif|examin|quantif)|did not (analy|cover|trace|look)"
    r"|out of scope|left unanalyzed|remains? unverified|no(t)? attempt(ed)? to)\w*"
    r"|未(分析|覆盖|追踪|验证|量化|展开)|没有(分析|覆盖|追踪|验证)|不在.{0,4}范围")

# Phrases that assert a cause as established fact. A degraded output may hypothesise,
# but §4 forbids claiming a definitive root cause without evidence.
DEFINITIVE_CAUSE_RE = re.compile(
    r"(?i)(\b(the )?root cause (was|is)\b|根因(是|为)|根本原因(是|为))"
    r"(?!.{0,40}(\b(likely|probably|suspected|hypothesis|unknown|cannot|unconfirmed|"
    r"to be confirmed|unverified)\b|可能|疑似|推测|未确认|待确认|无法确认))")


class Result:
    def __init__(self, check: str, passed: bool, detail: str = ""):
        self.check, self.passed, self.detail = check, passed, detail

    def __str__(self) -> str:
        return f"  [{'PASS' if self.passed else 'FAIL'}] {self.check}" + \
               (f" — {self.detail}" if self.detail and not self.passed else "")


def grade(scenario: dict, response: str) -> list[Result]:
    spec = scenario["grade"]
    out: list[Result] = []
    mode = spec["expect_mode"]
    depth = spec.get("expect_depth", "standard")

    # 1. Mode & depth must be declared, and must be the ones the scenario calls for.
    #
    # SKILL.md §9.0 has three placements. When the user forbids ANY text beyond the
    # requested section, the reply *is* the artifact and there is no legal "around" —
    # so the spine is omitted and its absence must not be scored as a failure. Grading
    # it anyway rewarded answers that disobeyed the user, which is the opposite of the
    # precedence rule.
    spine = spec.get("spine_placement", "in_artifact")
    declared = _declared_mode_depth(response)
    if spine != "omitted":
        out.append(Result("declares mode & depth (§9.2)", declared is not None,
                          "no Mode & Depth line found"))
    if declared and spine != "omitted":
        got_mode, got_depth = declared
        out.append(Result(f"selects mode={mode}", got_mode == mode,
                          f"declared {got_mode!r}"))
        if "expect_depth" in spec:
            out.append(Result(f"selects depth={depth}", got_depth == depth,
                              f"declared {got_depth!r}"))

    # 2. Output contract for that mode (§9.0).
    for sec in spec.get("required_sections", []):
        out.append(Result(f"section {sec} present",
                          bool(SECTIONS[sec].search(response)), "missing"))
    for sec in spec.get("forbidden_sections", []):
        out.append(Result(f"section {sec} correctly omitted",
                          not SECTIONS[sec].search(response),
                          "present though out of contract"))

    # 3. Mechanical layer, at the mode and depth the scenario expects.
    tolerated = set(spec.get("tolerated_lint_checks", []))
    findings = [f for f in lint_postmortem.lint(
        response, mode, depth, spec.get("user_pinned_format", False))
        if f.check not in tolerated]
    criticals = [f for f in findings if f.severity == lint_postmortem.CRITICAL]
    limit = spec.get("max_critical_findings", 0)
    pinned = " pinned" if spec.get("user_pinned_format") else ""
    out.append(Result(f"lint criticals <= {limit} [{mode}/{depth}{pinned}]",
                      len(criticals) <= limit,
                      "; ".join(str(f) for f in criticals[:4])))

    # 4. Honest degradation.
    if spec.get("require_degraded_marker"):
        out.append(Result("marks output as DEGRADED (§4)",
                          "# DEGRADED:" in response, "no '# DEGRADED:' marker"))
    if spec.get("forbid_definitive_root_cause"):
        hit = DEFINITIVE_CAUSE_RE.search(response)
        out.append(Result("does not assert a root cause without evidence",
                          hit is None, f"asserted: {hit.group(0)!r}" if hit else ""))

    # 5. RCA technique is named rather than assumed.
    if spec.get("require_technique_named"):
        named = re.search(r"(?i)\b(5[- ]why|five why|fishbone|ishikawa|fault tree|"
                          r"causal (map|diagram))\b", response)
        out.append(Result("names the RCA technique",
                          named is not None, "no technique named"))
    for technique in spec.get("forbid_techniques", []):
        out.append(Result(f"does not force {technique}",
                          not re.search(rf"(?i)\b{technique}\b", response),
                          "used a technique that does not fit this incident's shape"))

    # 6. Grounding: cite what was given, invent nothing.
    for needle in spec.get("must_mention", []):
        out.append(Result(f"grounded in material: {needle!r}",
                          needle.lower() in response.lower(), "not referenced"))
    for item in spec.get("forbid_patterns", []):
        hit = re.search(item["pattern"], response)
        out.append(Result(f"no {item['label']}", hit is None,
                          f"matched {hit.group(0)!r}" if hit else ""))

    # 7. Gate 5: material handed in may contain secrets; the write-up must not echo them.
    for secret in spec.get("must_not_leak", []):
        out.append(Result(f"redacts {secret[:12]!r}...", secret not in response,
                          "verbatim secret from the input material appears in the output"))
    if spec.get("forbid_extra_content"):
        # The user asked for exactly one section and nothing else. Verify obedience:
        # no preamble before the first heading, and no headings beyond the allowed set.
        allowed = spec.get("required_sections", [])
        headings = re.findall(r"(?m)^#{1,4}\s+.*$", response)
        extra = [h for h in headings
                 if not any(SECTIONS[s].match(h) for s in allowed)]
        out.append(Result("no headings beyond the requested section", not extra,
                          f"extra headings: {extra[:3]}"))
        preamble = response.split(headings[0])[0].strip() if headings else response.strip()
        out.append(Result("no preamble before the requested section", not preamble,
                          f"preamble: {preamble[:60]!r}"))

    if spec.get("require_uncovered_statement"):
        # With a pinned format §9.9 cannot be a heading inside the artifact, so the
        # linter's check is waived — but SKILL.md §9.0 still says "never drop 9.9
        # silently". It has to be stated somewhere in the response.
        out.append(Result("states what was not covered, even without a §9.9 heading",
                          bool(UNCOVERED_PROSE_RE.search(response)),
                          "no statement of what was left unanalyzed"))
    if spec.get("require_distribution_header"):
        out.append(Result("declares distribution & redaction (Gate 5)",
                          bool(re.search(r"(?i)\*\*distribution\*\*", response))
                          and bool(re.search(r"(?i)\*\*redaction\*\*", response)),
                          "no Distribution/Redaction header"))
    return out


def _declared_mode_depth(response: str) -> tuple[str, str] | None:
    """Read the mode and depth out of §9.2, wherever the model put it."""
    m = re.search(
        r"(?is)(?:^|\n)[#*\s]*(?:mode\s*&?\s*(?:and\s*)?depth|模式\s*[与和&]?\s*深度)"
        r"[^\n]*\n?(.{0,240})", response)
    scope = m.group(0) if m else ""
    mode = re.search(r"(?i)\b(draft|review|extract|planning)\b", scope)
    depth = re.search(r"(?i)\b(quick|standard|deep)\b", scope)
    if not mode:
        return None
    # Return the depth VERBATIM. Normalising "deep" to "standard" here made
    # expect_depth: "deep" unsatisfiable — the declaration could never match the
    # expectation, and only the absence of any deep scenario hid it.
    return mode.group(1).lower(), (depth.group(1).lower() if depth else "standard")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario")
    parser.add_argument("response")
    parser.add_argument("--json", dest="json_out", metavar="PATH",
                        help="write a machine-readable per-check result to PATH so the "
                             "runner can aggregate CHECK counts, not just scenario "
                             "counts — two arms can fail the same scenarios while one "
                             "fails 3 checks and the other 15")
    args = parser.parse_args(argv)
    try:
        scenario = json.loads(Path(args.scenario).read_text(encoding="utf-8"))
        response = Path(args.response).read_text(encoding="utf-8")
    except (OSError, json.JSONDecodeError) as exc:
        print(f"cannot read inputs: {exc}", file=sys.stderr)
        return 2
    results = grade(scenario, response)
    for r in results:
        print(r)
    failed = [r for r in results if not r.passed]
    print(f"  {len(results) - len(failed)}/{len(results)} checks passed"
          f" — {scenario['id']}")
    if args.json_out:
        Path(args.json_out).write_text(json.dumps({
            "scenario": scenario["id"],
            "checks_total": len(results),
            "checks_passed": len(results) - len(failed),
            "checks_failed": len(failed),
            "passed": not failed,
            "failed_checks": [{"check": r.check, "detail": r.detail} for r in failed],
        }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
