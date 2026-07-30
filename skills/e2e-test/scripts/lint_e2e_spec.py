#!/usr/bin/env python3
"""Grade a Playwright spec file against part of the e2e-test Quality Scorecard.

This is a *forward evaluator*: it reads generated test code and reports defects in
it. Contract tests check that the skill *says* the right things; this checks that
the output *is* the right thing.

Coverage is partial, and the exact subset matters — do not read a clean report as
"passes the scorecard":

    Implemented   C1 (waitForTimeout, networkidle)
                  C2 (shared mutable test identity)
                  C3 (hardcoded URL, credential literal)
                  C4 (per-variable env guard)
                  S1 (fragile CSS chain, XPath, no accessible locators)
                  S3 (UI-driving test with no assertion)
                  S5 (serial mode with no stated justification)
                  H2 (vague test name)
    Extra         W1 (network wait armed after its trigger) — not a scorecard
                  item; an additional check this linter performs
    NOT checked   S2 auth strategy, S4 artifact policy, S6 mock boundaries,
                  H1 reusable fixtures, H3 CI strategy, H4 repeat-run validation

Those six are judgement calls that need repository and CI context this script
does not have. Assess them yourself.

Usage:
    python3 lint_e2e_spec.py <file.spec.ts> [more.spec.ts ...]
    python3 lint_e2e_spec.py --json <file.spec.ts>

Exit codes:
    0  no CRITICAL findings
    1  at least one CRITICAL finding
    2  could not run (bad arguments, unreadable file)

Further limits, stated plainly because a linter that overclaims is worse than no
linter: this is a regex/heuristic pass over TypeScript source, not a parse. It
cannot see through helper indirection, cannot resolve imported constants, and does
not execute anything. Rules prefer a miss over a false alarm, so a dirty report is
much stronger evidence than a clean one.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

CRITICAL = "CRITICAL"
STANDARD = "STANDARD"
HYGIENE = "HYGIENE"


@dataclass
class Finding:
    rule: str
    severity: str
    line: int
    message: str
    evidence: str


def _strip_comments(text: str) -> str:
    """Blank out comments only, preserving string literals and line numbers.

    Comments must go: otherwise a rule forbidding `waitForTimeout` fires on the
    skill's own "// BAD: await page.waitForTimeout(3000)" teaching comment.

    String literals must stay: the evidence for most rules lives *inside* a
    literal — `waitForLoadState('networkidle')`, `locator('.a > .b')`,
    `mode: 'serial'`, `goto('https://…')`. Blanking literal contents made every
    one of those rules silently match nothing.

    Newlines are preserved so reported line numbers point at real source lines.
    """
    out = []
    i = 0
    n = len(text)
    while i < n:
        two = text[i : i + 2]
        if two == "//":
            while i < n and text[i] != "\n":
                out.append(" ")
                i += 1
        elif two == "/*":
            while i < n and text[i : i + 2] != "*/":
                out.append("\n" if text[i] == "\n" else " ")
                i += 1
            out.append("  ")
            i += 2
        elif text[i] in "\"'`":
            # Copy the literal through verbatim, tracking escapes so a quote
            # inside the string does not terminate it early.
            quote = text[i]
            out.append(quote)
            i += 1
            while i < n and text[i] != quote:
                if text[i] == "\\" and i + 1 < n:
                    out.append(text[i])
                    out.append(text[i + 1])
                    i += 2
                    continue
                out.append(text[i])
                i += 1
            if i < n:
                out.append(quote)
                i += 1
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def _lines_matching(pattern: str, text: str, flags: int = 0) -> list[tuple[int, str]]:
    hits = []
    for m in re.finditer(pattern, text, flags):
        line_no = text.count("\n", 0, m.start()) + 1
        hits.append((line_no, m.group(0).strip()))
    return hits


def _source_line(raw: str, line_no: int) -> str:
    lines = raw.split("\n")
    if 1 <= line_no <= len(lines):
        return lines[line_no - 1].strip()
    return ""


# --- C1: no unconditional waitForTimeout -----------------------------------
def check_c1(code: str, raw: str) -> list[Finding]:
    findings = []
    for line_no, hit in _lines_matching(r"waitForTimeout\s*\(", code):
        findings.append(
            Finding(
                "C1",
                CRITICAL,
                line_no,
                "Unconditional waitForTimeout. Assert the user-visible state "
                "instead; expect() auto-retries.",
                _source_line(raw, line_no),
            )
        )
    # networkidle is the same defect wearing a respectable hat: it is a proxy
    # signal, and Playwright marks it DISCOURAGED.
    for line_no, hit in _lines_matching(r"networkidle", code):
        findings.append(
            Finding(
                "C1",
                CRITICAL,
                line_no,
                "waitUntil/waitForLoadState 'networkidle' is DISCOURAGED by "
                "Playwright. Assert real content instead.",
                _source_line(raw, line_no),
            )
        )
    return findings


# --- C2: data isolation ----------------------------------------------------
def check_c2(code: str, raw: str) -> list[Finding]:
    findings = []
    # A module-scope const holding an email/username that a test then mutates is
    # the classic shared-fixture race. Only flag when it looks like an identity
    # AND the file runs more than one test.
    test_count = len(_lines_matching(r"\btest\s*\(", code))
    if test_count < 2:
        return findings
    ident_re = (
        r"^(?:const|let|var)\s+(\w*(?:[Ee]mail|[Uu]ser|[Aa]ccount|[Ll]ogin)\w*)"
        r"\s*=\s*['\"][^'\"]*@"
    )
    for line_no, hit in _lines_matching(ident_re, code, re.MULTILINE):
        if re.search(r"Date\.now|randomUUID|parallelIndex|\$\{", _source_line(raw, line_no)):
            continue
        findings.append(
            Finding(
                "C2",
                CRITICAL,
                line_no,
                "Module-scope test identity shared across multiple tests. Derive "
                "it per test (Date.now(), parallelIndex, or a fixture).",
                _source_line(raw, line_no),
            )
        )
    return findings


# --- C3: no guessed secrets or URLs ---------------------------------------
_LOCALHOST = re.compile(r"localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\]")

# A deliberately-invalid credential in a negative test is correct practice, not a
# leaked secret. "assert that a wrong password is rejected" has to pass a wrong
# password. Flagging these trains the reader to ignore the linter.
_NEGATIVE_SENTINEL = re.compile(
    r"^(?:wrong|bad|invalid|incorrect|expired|fake|nope|not-?a-?\w+|"
    r"short|empty|null|undefined|xxx+|[.]{3,})[\w.@-]*$",
    re.IGNORECASE,
)


def check_c3(code: str, raw: str) -> list[Finding]:
    findings = []
    # Absolute non-local URL literal => an invented or hardcoded environment.
    for line_no, hit in _lines_matching(r"['\"]https?://[^'\"]+['\"]", code):
        if _LOCALHOST.search(hit):
            continue
        findings.append(
            Finding(
                "C3",
                CRITICAL,
                line_no,
                "Hardcoded absolute URL. Read the environment from "
                "process.env / config baseURL and guard with test.skip.",
                _source_line(raw, line_no),
            )
        )
    # Credential-shaped literals passed to a fill/type call.
    cred_re = (
        r"\.(?:fill|type)\s*\(\s*(['\"])"
        r"([^'\"]*(?:password|passwd|secret|token|api[-_]?key)[^'\"]*|"
        r"[A-Za-z0-9!@#$%^&*]{6,})\1\s*\)"
    )
    for m in re.finditer(cred_re, code, re.IGNORECASE):
        line_no = code.count("\n", 0, m.start()) + 1
        literal = m.group(2)
        src = _source_line(raw, line_no)
        if "process.env" in src:
            continue
        # A visible-text search term or a display name is not a credential.
        if re.search(r"getBy(Placeholder|Label)\(['\"](Search|Query|Name|Display)", src, re.I):
            continue
        if not re.search(
            r"password|passwd|secret|token|api[-_]?key|credential",
            src,
            re.IGNORECASE,
        ):
            continue
        if _NEGATIVE_SENTINEL.match(literal):
            continue
        findings.append(
            Finding(
                "C3",
                CRITICAL,
                line_no,
                "Credential literal in source. Load from process.env and add a "
                "test.skip guard when it is absent.",
                src,
            )
        )
    return findings


# --- C4: skip guard present when env is required --------------------------
# Environment flags that steer configuration rather than supply a required value.
# `workers: process.env.CI ? 4 : undefined` needs no skip guard — undefined is a
# valid answer. Treating these as "missing required config" is a false alarm.
_CONFIG_FLAG_ENV = re.compile(
    r"^(?:CI|NODE_ENV|ENV|DEBUG|UPDATE_SNAPSHOTS|PWDEBUG|PLAYWRIGHT_\w+|"
    r"GITHUB_ACTIONS|TZ|HEADLESS)$"
)


def _is_guarded_read(src: str) -> bool:
    """True when this specific read supplies its own fallback.

    Covers `?? default`, `|| default`, and the ternary form
    `process.env.CI ? a : b` — all three make an unset value harmless.
    """
    return bool(re.search(r"process\.env\.\w+\s*(?:\?\?|\|\||\?[^?])", src))


def _guard_expressions(code: str) -> list[str]:
    """Extract the condition text of every test.skip / test.fixme call.

    Brace/paren-balanced enough for real specs: reads from the opening paren to
    the first comma at depth 1, which is where the condition ends.
    """
    guards = []
    for m in re.finditer(r"test\.(?:skip|fixme)\s*\(", code):
        guards.append(code[m.end() : _condition_end(code, m.end())])
    return guards


def _condition_end(code: str, start: int) -> int:
    """Index just past the guard's condition — the first depth-1 comma or the
    closing paren of the call."""
    i, depth = start, 1
    while i < len(code) and depth > 0:
        ch = code[i]
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
            if depth == 0:
                break
        elif ch == "," and depth == 1:
            break
        i += 1
    return i


def _call_end(code: str, open_paren_index: int) -> int:
    """Index just past the matching close paren of a call whose `(` is at
    open_paren_index - 1 (i.e. start scanning at depth 1)."""
    i, depth = open_paren_index, 1
    while i < len(code) and depth > 0:
        ch = code[i]
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return len(code)


# A `test(...)` or `test.describe(...)` call delimits a scope. `test.describe`
# followed by `.configure` is not a block — it is a settings call.
_SCOPE_RE = re.compile(
    r"\btest\s*\(|\btest\.describe(?!\.configure)(?:\.\w+)?\s*\(|"
    r"\btest\.(?:beforeEach|afterEach|beforeAll|afterAll)\s*\("
)
# Only a *before* hook runs early enough to stop a test that would read the
# variable. `test.skip` inside afterEach/afterAll executes after the body has
# already run, so it provides no protection and must not be promoted.
#
# This is a claim about Playwright's runtime, not about this file, so it is
# measured rather than assumed. `scripts/verify_hook_semantics.sh` runs a real
# Playwright suite and asserts the matrix below. Observed on 1.62.0:
#
#   guard in beforeAll, 2 tests            -> both skipped, no body ran
#   guard in beforeAll, --retries=2        -> skipped, no body ran
#   guard in beforeAll, --workers=2 (4)    -> all skipped, no body ran
#   guard in beforeEach                    -> skipped, no body ran
#   guard in describe-scoped beforeAll     -> only that group skipped; sibling ran
#   guard in beforeAll, false condition    -> test ran (negative control)
#   guard in afterAll / afterEach          -> BODY RAN, then reported "skipped"
#
# The last row is why after-hooks must not count: the read happens anyway, and
# the run is then relabelled skipped — so a suite that would have failed on an
# unset variable reports as skipped instead. Re-run the verifier when bumping the
# Playwright version this skill targets.
_BEFORE_HOOK_RE = re.compile(r"\btest\.(?:beforeEach|beforeAll)\b")


def _scopes(code: str) -> list[tuple[int, int, bool]]:
    """Every scope block as (start, end, is_before_hook), outermost first.

    `start` is the index of the call keyword so nesting comparisons work. The
    flag marks only before-hooks; an after-hook is an ordinary block whose guard
    covers nothing beyond itself.
    """
    out = []
    for m in _SCOPE_RE.finditer(code):
        end = _call_end(code, m.end())
        out.append((m.start(), end, bool(_BEFORE_HOOK_RE.search(m.group(0)))))
    return out


def _guard_coverage(code: str) -> list[tuple[str, int, int]]:
    """Each guard as (condition_text, coverage_start, coverage_end).

    A guard covers only the scope that encloses it — this is the fix for the
    cross-test false negative. `test.skip` inside test A says nothing about
    test B:

        test('a', ...) { test.skip(!PASS); use(PASS!) }   // guarded
        test('b', ...) { use(PASS!) }                     // NOT guarded

    A guard at file scope covers the whole file. A guard inside a `beforeEach` /
    `beforeAll` hook is promoted to the hook's own enclosing scope, because
    `test.skip` there runs before each test and does skip them.

    An `afterEach` / `afterAll` guard is **not** promoted: it executes after the
    body has already read the variable, so it protects nothing. Treating all four
    hooks alike made this a false negative.
    """
    scopes = _scopes(code)
    coverage = []
    for m in re.finditer(r"test\.(?:skip|fixme)\s*\(", code):
        pos = m.start()
        condition = code[m.end() : _condition_end(code, m.end())]

        enclosing = [s for s in scopes if s[0] < pos < s[1]]
        if not enclosing:
            coverage.append((condition, 0, len(code)))
            continue
        # Innermost enclosing scope = the one starting last.
        innermost = max(enclosing, key=lambda s: s[0])
        if innermost[2]:  # a hook — promote to the hook's enclosing scope
            outer = [s for s in enclosing if s is not innermost and s[0] < innermost[0]]
            if outer:
                promoted = max(outer, key=lambda s: s[0])
                coverage.append((condition, promoted[0], promoted[1]))
            else:
                coverage.append((condition, 0, len(code)))
            continue
        coverage.append((condition, innermost[0], innermost[1]))
    return coverage


def _env_aliases(code: str) -> dict[str, str]:
    """Map local identifier -> env var name for `const X = process.env.FOO`.

    Without this, a guard written against the alias (`test.skip(!U, …)`) reads as
    guarding nothing, and a guard against the env name reads as not covering the
    alias. Both directions matter.
    """
    aliases = {}
    for m in re.finditer(
        r"(?:const|let|var)\s+(\w+)\s*=\s*process\.env\.(\w+)([^\n;]*)", code
    ):
        # A declaration that supplies its own default — `?? ''`, `|| x`, or a
        # ternary — is intentionally optional. Tracking it would flag every later
        # use of a variable that can never be undefined.
        if re.match(r"\s*(?:\?\?|\|\||\?[^?])", m.group(3)):
            continue
        aliases[m.group(1)] = m.group(2)
    return aliases


def check_c4(code: str, raw: str) -> list[Finding]:
    """Guards are matched per variable AND per scope.

    Two ways a naive check gets defeated. First, per-file "does any test.skip
    exist":

        const U = process.env.E2E_USER;
        const P = process.env.E2E_PASS;
        test.skip(!U, 'user missing');   // guards U only
        await field.fill(P!);            // P unguarded — was reported clean

    Second, per-variable but file-wide, which leaks across test boundaries:

        test('a', async () => { test.skip(!PASS); use(PASS!); })  // guarded
        test('b', async () => { use(PASS!); })                    // NOT guarded,
                                                                  // was reported clean

    So coverage is positional: a guard protects the scope that encloses it and
    nothing outside it.
    """
    findings: list[Finding] = []
    aliases = _env_aliases(code)
    coverage = _guard_coverage(code)

    # Which env vars each guard names, resolved through the alias map so a guard
    # on `U` covers `E2E_USER` and vice versa.
    resolved: list[tuple[set[str], int, int]] = []
    for condition, start, end in coverage:
        names = set(re.findall(r"process\.env\.(\w+)", condition))
        for token in re.findall(r"\b\w+\b", condition):
            if token in aliases:
                names.add(aliases[token])
        resolved.append((names, start, end))

    def is_guarded_at(env_name: str, pos: int) -> bool:
        """Guard coverage is positional: a guard protects only its own scope."""
        return any(
            env_name in names and start <= pos <= end
            for names, start, end in resolved
        )

    # Reads inside a guard's own condition are not uses to be reported.
    condition_spans = [
        (m.end(), _condition_end(code, m.end()))
        for m in re.finditer(r"test\.(?:skip|fixme)\s*\(", code)
    ]

    def inside_condition(pos: int) -> bool:
        return any(start <= pos <= end for start, end in condition_spans)

    seen: set[tuple[str, int]] = set()

    def report(env_name: str, pos: int, message: str) -> None:
        line_no = code.count("\n", 0, pos) + 1
        key = (env_name, line_no)
        if key in seen:
            return
        seen.add(key)
        findings.append(
            Finding("C4", CRITICAL, line_no, message, _source_line(raw, line_no))
        )

    unguarded_msg = (
        "no guard covers it at this point. A test.skip on a different variable, "
        "or inside a different test, does not protect this use."
    )

    # Spans of alias declarations. Binding a name to process.env is harmless on
    # its own — an unset value is just `undefined` until something uses it. The
    # hazard is the *use*, which is checked below per alias. Reporting the
    # declaration would false-alarm on the common and correct shape of a
    # file-scope const plus a per-test guard in every test.
    decl_spans = [
        m.span()
        for m in re.finditer(
            r"(?:const|let|var)\s+\w+\s*=\s*process\.env\.\w+", code
        )
    ]

    def inside_declaration(pos: int) -> bool:
        return any(start <= pos < end for start, end in decl_spans)

    # Direct reads at the point of use: process.env.FOO
    for m in re.finditer(r"process\.env\.(\w+)", code):
        name = m.group(1)
        if _CONFIG_FLAG_ENV.match(name) or inside_condition(m.start()):
            continue
        if inside_declaration(m.start()) or is_guarded_at(name, m.start()):
            continue
        line_no = code.count("\n", 0, m.start()) + 1
        if _is_guarded_read(_source_line(code, line_no)):
            continue
        report(name, m.start(), f"Required env {name} is used but {unguarded_msg}")

    # Uses of an alias bound to process.env, with or without a `!` assertion.
    for alias, env_name in aliases.items():
        if _CONFIG_FLAG_ENV.match(env_name):
            continue
        for m in re.finditer(rf"\b{re.escape(alias)}\b", code):
            if inside_declaration(m.start()) or inside_condition(m.start()):
                continue
            if is_guarded_at(env_name, m.start()):
                continue
            report(
                env_name,
                m.start(),
                f"{alias} (= process.env.{env_name}) is used but {unguarded_msg}",
            )

    return findings


# --- W1: network waits must be armed before the triggering action ----------
# Not a Quality Scorecard item — an additional check this linter performs.
def check_w1(code: str, raw: str) -> list[Finding]:
    """`await page.waitForResponse(...)` on its own line is a latent hang.

    Playwright only delivers events that arrive *after* the waiter is installed.
    Awaiting the waiter inline means the triggering action already ran, so a
    response that already landed is never seen and the wait burns its full
    timeout. The correct shape stores the promise first:

        const p = page.waitForResponse(...);
        await action();
        await p;
    """
    findings = []
    waiters = r"waitForResponse|waitForRequest|waitForEvent"
    # `[^;=]*?` spans the receiver chain so `page.context().waitForEvent(...)` is
    # matched, not just `page.waitForEvent(...)`.
    pattern = rf"await\s+[^;=]*?\.(?:{waiters})\s*\("
    for m in re.finditer(pattern, code):
        line_no = code.count("\n", 0, m.start()) + 1
        matched = m.group(0)
        # `await Promise.all([page.waitForEvent('page'), page.click()])` is the
        # canonical *correct* form — both sides are armed before either runs.
        if re.search(r"Promise\.(?:all|race|allSettled)", matched):
            continue
        findings.append(
            Finding(
                "W1",
                STANDARD,
                line_no,
                "Network wait awaited inline: it can only catch events that "
                "arrive after this line. Store the promise before the action "
                "that triggers it, or assert the user-visible result instead.",
                _source_line(raw, line_no),
            )
        )
    return findings


# --- S1: accessible selectors --------------------------------------------
_ACCESSIBLE = r"getBy(?:Role|Label|Placeholder|TestId|Text|Title|AltText)\s*\("
_FRAGILE_CSS = re.compile(
    r"""(?:page|frame|window|\w+)\.locator\s*\(\s*['"]        # locator('
        (?=[^'"]*(?:>|\ )                                      # has a combinator
        )[^'"]*['"]""",
    re.VERBOSE,
)


def check_s1(code: str, raw: str) -> list[Finding]:
    findings = []
    accessible = len(_lines_matching(_ACCESSIBLE, code))
    for line_no, hit in _lines_matching(r"\.locator\s*\(\s*['\"][^'\"]+['\"]", code):
        sel = hit
        if re.search(r"nth-child|nth-of-type|>\s*\w|\w\s+\w+\.\w|^\s*\.locator\(['\"]\.", sel):
            findings.append(
                Finding(
                    "S1",
                    STANDARD,
                    line_no,
                    "Fragile CSS chain. Prefer getByRole/getByLabel/getByTestId.",
                    _source_line(raw, line_no),
                )
            )
    for line_no, hit in _lines_matching(r"\$x\(|xpath=", code):
        findings.append(
            Finding(
                "S1",
                STANDARD,
                line_no,
                "XPath selector. Prefer accessible locators.",
                _source_line(raw, line_no),
            )
        )
    total_interactions = len(
        _lines_matching(r"\.(?:click|fill|check|selectOption|press|type)\s*\(", code)
    )
    if total_interactions >= 3 and accessible == 0:
        findings.append(
            Finding(
                "S1",
                STANDARD,
                1,
                f"{total_interactions} interactions and zero accessible locators.",
                "",
            )
        )
    return findings


# --- S3: assertions after interactions -----------------------------------
_INTERACTION = re.compile(r"\.(?:click|fill|check|selectOption|press|type|goto)\s*\(")
_SCAFFOLD_MARKER = re.compile(r"TODO|FIXME|scaffold|\.\.\. scaffold", re.IGNORECASE)


def _test_bodies(code: str) -> list[str]:
    """Split into per-test chunks. Approximate but sufficient: each chunk runs
    from one `test(` to the next, so interactions and assertions are attributed
    to the test they appear in."""
    parts = re.split(r"\btest\s*\(\s*['\"]", code)
    return parts[1:] if len(parts) > 1 else []


def check_s3(code: str, raw: str) -> list[Finding]:
    findings = []
    bodies = _test_bodies(code)
    if not bodies:
        return findings

    # An honest scaffold has no assertions *by design* — the skill explicitly
    # endorses "placeholder-only scaffolding with explicit TODOs and skip guards".
    # Penalising that would push toward pseudo-runnable code, the exact failure
    # the Configuration Gate exists to prevent.
    is_scaffold = bool(_SCAFFOLD_MARKER.search(raw)) and bool(
        re.search(r"test\.(?:skip|fixme)\s*\(", code)
    )
    if is_scaffold:
        return findings

    # Only tests that actually drive the UI are expected to assert. A snippet
    # whose body is elided is illustrating structure, not claiming coverage.
    substantive = [b for b in bodies if _INTERACTION.search(b)]
    if not substantive:
        return findings

    asserting = [b for b in substantive if re.search(r"\bexpect\s*\(", b)]
    if not asserting:
        findings.append(
            Finding(
                "S3",
                STANDARD,
                1,
                f"{len(substantive)} test(s) drive the UI but none assert. A test "
                "that cannot fail is not coverage.",
                "",
            )
        )
    elif len(asserting) < len(substantive):
        findings.append(
            Finding(
                "S3",
                STANDARD,
                1,
                f"{len(substantive)} test(s) drive the UI but only "
                f"{len(asserting)} assert.",
                "",
            )
        )
    return findings


# --- S5: serial mode justified -------------------------------------------
def check_s5(code: str, raw: str) -> list[Finding]:
    findings = []
    for line_no, hit in _lines_matching(
        r"configure\s*\(\s*\{[^}]*mode\s*:\s*['\"]serial['\"]", code
    ):
        # A justification counts whether it is a comment or is stated in the
        # enclosing describe title ("checkout funnel — serial because steps
        # share cart state"). Requiring comment syntax specifically would reject
        # the clearer of the two forms.
        window = "\n".join(raw.split("\n")[max(0, line_no - 4) : line_no + 1])
        if re.search(r"//|/\*", window) or re.search(
            r"\bbecause\b|\bshares?\b|\bstateful\b|\bordering\b", window, re.IGNORECASE
        ):
            continue
        findings.append(
            Finding(
                "S5",
                STANDARD,
                line_no,
                "Serial mode with no stated justification. Say why parallel is "
                "unsafe here, in a comment or the describe title.",
                _source_line(raw, line_no),
            )
        )
    return findings


# --- H2: descriptive test names ------------------------------------------
_VAGUE = re.compile(
    r"^(?:test|tests?\s*\d*|works?|it works|should work|todo|foo|bar|temp|"
    r"test\s*\d+|check|basic|smoke)$",
    re.IGNORECASE,
)


def check_h2(code: str, raw: str) -> list[Finding]:
    findings = []
    for m in re.finditer(r"\btest\s*\(\s*(['\"])(.+?)\1", code):
        name = m.group(2).strip()
        line_no = raw.count("\n", 0, m.start()) + 1
        if _VAGUE.match(name) or len(name) < 8:
            findings.append(
                Finding(
                    "H2",
                    HYGIENE,
                    line_no,
                    f"Test name {name!r} does not describe a user journey.",
                    _source_line(raw, line_no),
                )
            )
    return findings


CHECKS = [
    check_c1,
    check_c2,
    check_c3,
    check_c4,
    check_w1,
    check_s1,
    check_s3,
    check_s5,
    check_h2,
]


def lint_source(raw: str) -> list[Finding]:
    code = _strip_comments(raw)
    findings: list[Finding] = []
    for check in CHECKS:
        findings.extend(check(code, raw))
    order = {CRITICAL: 0, STANDARD: 1, HYGIENE: 2}
    return sorted(findings, key=lambda f: (order[f.severity], f.line, f.rule))


def lint_file(path: Path) -> list[Finding]:
    return lint_source(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--json", action="store_true", help="emit JSON")
    args = parser.parse_args(argv)

    results: dict[str, list[dict]] = {}
    critical_total = 0

    for path in args.paths:
        if not path.is_file():
            print(f"lint_e2e_spec: not a file: {path}", file=sys.stderr)
            return 2
        findings = lint_file(path)
        results[str(path)] = [asdict(f) for f in findings]
        critical_total += sum(1 for f in findings if f.severity == CRITICAL)

    if args.json:
        print(json.dumps({"files": results, "critical_count": critical_total}, indent=2))
    else:
        for name, findings in results.items():
            if not findings:
                print(f"{name}: PASS — no findings")
                continue
            print(f"{name}:")
            for f in findings:
                print(f"  [{f['severity']}] {f['rule']} line {f['line']}: {f['message']}")
                if f["evidence"]:
                    print(f"      {f['evidence']}")
        print()
        print(f"CRITICAL findings: {critical_total}")

    return 1 if critical_total else 0


if __name__ == "__main__":
    sys.exit(main())
