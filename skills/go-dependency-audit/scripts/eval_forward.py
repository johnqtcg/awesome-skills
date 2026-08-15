#!/usr/bin/env python3
"""Forward (behavioural) evaluation for the go-dependency-audit skill.

The rest of this skill's tests check that the *documents* are right. This one
checks whether reading them changes what a model actually answers.

    python3 scripts/eval_forward.py --self-test      # no CLI needed; always runs
    python3 scripts/eval_forward.py --run            # needs an authenticated `claude`
    python3 scripts/eval_forward.py --grade DIR      # grade recorded outputs

Design, and why each part is the way it is:

* **Two arms, one variable.** Both arms get the same model, the same tool
  allowlist, and the same question. The only difference is whether the prompt
  points at the skill. Anything else and the delta stops being about the skill.
* **The without-skill arm runs in a neutral cwd** outside this repository and is
  never told the skill's path, so its file tools cannot stumble into it.
* **A with-skill run that never opened the skill is not a with-skill run.**
  `--output-format stream-json` exposes the tool calls; a run whose trace shows
  no read under the skill directory is recorded as unverified and not graded as
  evidence about the skill.
* **Every fixture targets a fact, not a format.** Each one is a question where a
  model answering from priors tends to state something this skill's own docs got
  wrong until 2026-08-14 — an invented CVSS score, a flag that does not exist, a
  legal verdict. Measuring transfer of a correct fact is the point; measuring
  whether the output has nine headings is not.
* **A harness failure is never graded.** `--grade` exits 3 (INCONCLUSIVE) when an
  arm is missing, empty, or unverified — never 0.

**If `--run` reports `Not logged in`, that is the sandbox, not your login.** The
CLI's credential file is outside the default writable set; re-run with the
sandbox disabled for that command.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys
import tempfile
from collections import Counter

SKILL_DIR = pathlib.Path(__file__).resolve().parent.parent
EVAL_DIR = SKILL_DIR / "scripts" / "tests" / "eval"

MODEL = "sonnet"
REPEATS = 3           # odd, so majority voting cannot tie
ARM_TOOLS = "Read,Grep,Glob"

# Pass bar. Six fixtures, so "one win and five ties" must not read as success:
# a skill that moves one answer and leaves five untouched has not been shown to
# work. Every arm must also have exactly REPEATS valid results — a majority vote
# taken over 1-vs-2 samples is not a majority vote.
MIN_WINS = 4
MAX_LOSSES = 0
REQUIRE_EXACT_REPEATS = True

# The with-skill arm must be shown to have READ skill content. Two boundaries:
#   too weak  — any path under the skill dir: a Glob that merely lists the
#               directory would satisfy it while the model read nothing;
#   too strict — SKILL.md specifically: observed runs Grep+Read a reference
#               directly (references/govulncheck-patterns.md) without opening
#               SKILL.md first. That is unambiguously using the skill, and
#               discarding it throws away valid with-skill data.
# So: a content-reading tool aimed at SKILL.md or any references/*.md.
SKILL_CONTENT_FILES = ("SKILL.md", "references/")
READING_TOOLS = ("Read", "Grep")


# ─────────────────────────── text helpers ───────────────────────────────

# Sentence/clause splitter. Criteria bind to the clause containing the claim,
# not the whole answer: an answer that says "govulncheck does not report CVSS;
# NVD lists CVE-2023-44487 as 7.5" must not be scored as if it attributed 7.5
# to govulncheck.
_CLAUSE_SPLIT = re.compile(r"(?<=[.!?;:])\s+|\n")


def clauses(text: str) -> list[str]:
    return [c.strip() for c in _CLAUSE_SPLIT.split(text) if c.strip()]


def code_blocks(text: str) -> list[str]:
    return re.findall(r"```[a-zA-Z0-9_-]*\n(.*?)```", text, re.DOTALL)


def commands(text: str) -> list[str]:
    """Command lines the answer actually proposes, from fenced blocks only.

    Prose that *names* a wrong flag in order to warn about it is a correct
    answer, so scoping to emitted commands is what keeps the criterion from
    failing the response it should reward.
    """
    out = []
    for block in code_blocks(text):
        for line in block.splitlines():
            line = line.strip().lstrip("$ ").strip()
            if line and not line.startswith("#"):
                out.append(line)
    return out


# `\b` treats a hyphen as a word boundary, so `\bno\b` fires inside "ship/no-ship
# call" and inside "no-go", "no-op", "non-blocking". That phantom negation made
# a real answer — "…then this goes to your legal/compliance reviewer for the
# actual ship/no-ship call" — score as *not* escalating. Bar hyphens explicitly.
_NEG_WORDS = (
    "no", "not", "never", "isn't", "cannot", "can't", "won't", "doesn't",
    "deprecated", "removed", "invalid", "unsupported", "avoid", "wrong",
    "incorrect", "myth", "obsolete", "hallucinated", "bogus", "fictional",
)
_NEG_PHRASES = (
    "is not", "does not", "there is no", "instead of", "rather than",
    "made up", "non-existent", "nonexistent",
)
NEGATORS = re.compile(
    r"(?<![\w-])(?:" + "|".join(_NEG_WORDS) + r")(?![\w-])"
    r"|(?<![\w-])(?:" + "|".join(_NEG_PHRASES) + r")(?![\w-])",
    re.IGNORECASE,
)

# Negation scopes forward over a bounded span, it does not colour a whole
# sentence. Blanket-vetoing any clause containing a negator rejected this real
# answer — "the toolchain treats it as another version of the *same* module path
# … — not a separate module" — because a "not" attached to a *different* noun
# phrase appeared later in the same clause. Bind the negator to the needle.
NEG_WINDOW_BEFORE = 90
NEG_WINDOW_AFTER = 60


def _negated_before(clause: str, pos: int) -> bool:
    """A negator preceding the phrase negates it: 'there is no -go flag'."""
    return bool(NEGATORS.search(clause[max(0, pos - NEG_WINDOW_BEFORE):pos]))


def _negated_after(clause: str, end: int) -> bool:
    """A negator following it may negate it — '-go does not exist' — or may
    negate something else entirely."""
    return bool(NEGATORS.search(clause[end:end + NEG_WINDOW_AFTER]))


def _negated_at(clause: str, pos: int, end: int) -> bool:
    return _negated_before(clause, pos) or _negated_after(clause, end)


def _quoted_spans(clause: str) -> list[tuple[int, int]]:
    """Spans inside quotes or backticks — cited text, not asserted text."""
    return [m.span() for m in re.finditer(r'"[^"]*"|\u201c[^\u201d]*\u201d|`[^`]*`', clause)]


# A myth that is quoted and then contradicted is a correct answer. Observed:
#   This matters more than "MVS ignores it" — it's the opposite.
REFUTATION = re.compile(
    r"\b(the opposite|opposite of|is wrong|isn'?t (?:true|right)|not true|"
    r"a myth|mythical|misconception|common(?:ly)? (?:believed|assumed)|"
    r"in fact|actually|contrary to|despite what|people assume)\b",
    re.IGNORECASE,
)


def _occurrences(text: str, needle: str):
    low_needle = needle.lower()
    for c in clauses(text):
        low = c.lower()
        start = low.find(low_needle)
        while start != -1:
            yield c, start, start + len(low_needle)
            start = low.find(low_needle, start + 1)


def asserted(text: str, needle: str) -> tuple[bool, str]:
    """True when some occurrence of `needle` is stated, not negated.

    Only a **preceding** negator counts. A trailing one usually negates a
    different constituent, and treating it as a veto rejected real answers:

        …then this goes to your legal/compliance reviewer for the actual
        ship/no-ship call — not something to resolve here.

    That sentence escalates to legal; the "not" belongs to "something to resolve
    here". `denied()` still looks both ways, because "-go does not exist" puts
    the negator after the phrase it denies.
    """
    for clause, pos, end in _occurrences(text, needle):
        if not _negated_before(clause, pos):
            return True, clause[:220]
    return False, ""


def denied(text: str, needle: str) -> tuple[bool, str]:
    """True when some occurrence of `needle` is negated."""
    for clause, pos, end in _occurrences(text, needle):
        if _negated_at(clause, pos, end):
            return True, clause[:220]
    return False, ""


# ─────────────────────────────── criteria ───────────────────────────────
# Each returns (passed, evidence). Evidence is quoted so a human can audit
# a disagreement without re-running anything.


def c_no_cvss_from_govulncheck(text):
    """States govulncheck emits no severity, and does not invent one."""
    said, ev = False, ""
    for probe in ("cvss", "severity score", "severity rating"):
        ok, e = denied(text, probe)
        if ok:
            said, ev = True, e
            break
    if not said:
        return False, "never states that govulncheck reports no CVSS/severity"
    for c in clauses(text):
        if re.search(r"cvss", c, re.I) and re.search(r"\b\d\.\d\b", c) \
           and re.search(r"govulncheck", c, re.I) and not NEGATORS.search(c):
            return False, f"attributes a CVSS number to govulncheck: {c[:200]}"
    return True, ev


def c_names_alias_lookup(text):
    """Points at the CVE/GHSA alias as the route to a severity score."""
    for probe in ("alias", "nvd", "ghsa", "cve database", "osv.dev"):
        ok, ev = asserted(text, probe)
        if ok:
            return True, ev
    return False, "no external source named for obtaining a severity score"


def c_no_nonexistent_govulncheck_flag(text):
    bad = ("-go=", "-mode=query", "-exclude", "-ignore=")
    for cmd in commands(text):
        if "govulncheck" not in cmd:
            continue
        for flag in bad:
            if flag in cmd:
                return False, f"emits a non-existent flag: {cmd[:160]}"
    return True, "no invalid govulncheck flag in any emitted command"


def c_says_flag_absent(text):
    for probe in ("-go", "-goversion", "-mode=query", "query mode",
                  "version-selection flag", "version selection flag",
                  "go version flag", "offline"):
        ok, ev = denied(text, probe)
        if ok:
            return True, ev
    return False, "does not say the requested flag/mode does not exist"


def c_json_exit_code_is_zero(text):
    for probe in ("exit 0", "exits 0", "exit code 0", "always 0",
                  "regardless of", "zero regardless"):
        ok, ev = asserted(text, probe)
        if ok and re.search(r"json|sarif|openvex", ev, re.I):
            return True, ev
    ok, ev = denied(text, "$?")
    if ok:
        return True, ev
    return False, "never notes that -json exits 0 regardless of findings"


def c_ci_gate_can_fail(text):
    """The emitted gate must key on something that can actually be non-zero."""
    cmds = " ; ".join(commands(text))
    if not cmds:
        return False, "no command emitted"
    uses_text_rc = re.search(r"\brc\b|\$\?|PIPESTATUS", cmds) and \
        not re.search(r"-json|-format[ =]json", cmds)
    parses = "jq" in cmds
    if uses_text_rc or parses:
        return True, f"gate keys on {'text exit code' if uses_text_rc else 'parsed findings'}"
    return False, f"gate cannot fail: {cmds[:200]}"


def c_no_legal_verdict(text):
    verdicts = ("you cannot ship", "cannot ship this", "you must not ship",
                "you are not allowed", "this is a violation", "illegal to")
    for c in clauses(text):
        low = c.lower()
        for v in verdicts:
            if v in low and '"' not in c:
                return False, f"states a legal verdict: {c[:200]}"
    return True, "no legal verdict asserted"


# Ways a real answer routes the question to a human decision-maker. The first
# version listed only "legal review"/"legal counsel" and scored this as a
# failure: "…then this goes to your legal/compliance reviewer for the actual
# ship/no-ship call". Synonyms are pinned in REAL_ANSWER_CASES.
ESCALATION_PROBES = (
    "legal review", "legal counsel", "legal team", "legal department",
    "legal/compliance", "legal or compliance", "compliance reviewer",
    "compliance team", "consult a lawyer", "consult legal", "ask your lawyer",
    "qualified reviewer", "not legal advice", "your counsel",
    "escalate to legal", "legal sign-off", "legal signoff",
)


def c_escalates_to_legal(text):
    for probe in ESCALATION_PROBES:
        ok, ev = asserted(text, probe)
        if ok:
            return True, ev
    return False, "does not route the question to legal/compliance review"


def c_names_distribution_factor(text):
    for probe in ("distribut", "convey", "linked into", "static link",
                  "network service", "saas"):
        ok, ev = asserted(text, probe)
        if ok:
            return True, ev
    return False, "does not name distribution/linkage as what decides the answer"


def c_no_phantom_env_var(text):
    for cmd in commands(text) + clauses(text):
        if re.search(r"\bGONOSUMCHECK\b", cmd) and not NEGATORS.search(cmd):
            return False, f"recommends GONOSUMCHECK: {cmd[:160]}"
    return True, "GONOSUMCHECK not recommended"


def c_names_real_env_var(text):
    hits = [v for v in ("GOPRIVATE", "GONOSUMDB", "GONOPROXY", "GOSUMDB")
            if re.search(rf"\b{v}\b", text)]
    if hits:
        return True, f"names {', '.join(hits)}"
    return False, "names none of GOPRIVATE/GONOSUMDB/GONOPROXY/GOSUMDB"


def c_incompatible_same_module(text):
    for probe in ("same module", "one module", "treated as part of",
                  "same module path", "another version of the",
                  "one and the same module"):
        ok, ev = asserted(text, probe)
        if ok:
            return True, ev
    # "not a separate module" states the same fact by denying its opposite.
    for probe in ("separate module", "distinct module", "different module"):
        ok, ev = denied(text, probe)
        if ok:
            return True, ev
    return False, "does not say +incompatible is the same module path as v1"


MVS_BLINDNESS = re.compile(
    r"invisible|cannot see|can'?t see|ignores|ignore|unaware|blind|overlooks",
    re.IGNORECASE,
)


def c_no_mvs_blindness_claim(text):
    """The common wrong answer: 'MVS can't see the major version'.

    Quoting the myth in order to deny it is a *correct* answer, and an early
    version of this criterion failed exactly that:
        This matters more than "MVS ignores it" — it's the opposite.
    So a hit is excused when it sits inside quotes/backticks (cited, not
    asserted) or when the clause explicitly contradicts it. A bare assertion
    with neither is still a failure.
    """
    for c in clauses(text):
        if not re.search(r"\bmvs\b|minimal version selection", c, re.I):
            continue
        spans = _quoted_spans(c)
        for m in MVS_BLINDNESS.finditer(c):
            if any(s <= m.start() and m.end() <= e for s, e in spans):
                continue                      # cited, not asserted
            if REFUTATION.search(c):
                continue                      # asserted then contradicted
            return False, f"repeats the MVS-blindness myth: {c[:200]}"
    return True, "no MVS-blindness claim"


# "major version" alone is too loose — any answer that merely mentions the term
# passes, including one that says +incompatible is just a naming quirk. Probe
# for the *crossing* sense: an upgrade moving across major versions.
MAJOR_JUMP_PROBES = (
    "cross a major", "across a major", "crossing a major", "cross major",
    "jump major", "jump across", "jump you", "jump from v1", "v1 to v4",
    "automatically upgrade", "upgrade automatically", "silently upgrade",
    "upgrade you across", "break the build", "major-version jump",
    "major version jump", "major version silently", "majors silently",
)


def c_warns_major_jump(text):
    for probe in MAJOR_JUMP_PROBES:
        ok, ev = asserted(text, probe)
        if ok:
            return True, ev
    return False, "does not warn that -u can cross a major version"


CRITERIA = {
    "no_cvss_from_govulncheck": c_no_cvss_from_govulncheck,
    "names_alias_lookup": c_names_alias_lookup,
    "no_nonexistent_govulncheck_flag": c_no_nonexistent_govulncheck_flag,
    "says_flag_absent": c_says_flag_absent,
    "json_exit_code_is_zero": c_json_exit_code_is_zero,
    "ci_gate_can_fail": c_ci_gate_can_fail,
    "no_legal_verdict": c_no_legal_verdict,
    "escalates_to_legal": c_escalates_to_legal,
    "names_distribution_factor": c_names_distribution_factor,
    "no_phantom_env_var": c_no_phantom_env_var,
    "names_real_env_var": c_names_real_env_var,
    "incompatible_same_module": c_incompatible_same_module,
    "no_mvs_blindness_claim": c_no_mvs_blindness_claim,
    "warns_major_jump": c_warns_major_jump,
}

FIXTURE_CRITERIA = {
    "DA-E1": ["no_cvss_from_govulncheck", "names_alias_lookup"],
    "DA-E2": ["no_nonexistent_govulncheck_flag", "says_flag_absent"],
    "DA-E3": ["json_exit_code_is_zero", "ci_gate_can_fail"],
    "DA-E4": ["no_legal_verdict", "escalates_to_legal", "names_distribution_factor"],
    "DA-E5": ["no_phantom_env_var", "names_real_env_var"],
    "DA-E6": ["incompatible_same_module", "no_mvs_blindness_claim", "warns_major_jump"],
}


# ─────────────────────────────── running ────────────────────────────────

def fixtures():
    out = []
    for path in sorted(EVAL_DIR.glob("*.json")):
        fx = json.loads(path.read_text(encoding="utf-8"))
        if fx["id"] in FIXTURE_CRITERIA:
            out.append(fx)
    return out


def run_arm(fx, with_skill, model, cwd, timeout=600, max_turns=10):
    prompt = fx["question"] + "\n"
    if with_skill:
        prompt = (
            f"Use the go-dependency-audit skill at {SKILL_DIR} — read its SKILL.md "
            f"and any references it routes you to — then answer.\n\n" + prompt
        )
    cmd = ["claude", "-p", "--model", model, "--permission-mode", "dontAsk",
           "--strict-mcp-config", "--max-turns", str(max_turns),
           "--tools", ARM_TOOLS, "--output-format", "stream-json", "--verbose"]
    try:
        proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                              timeout=timeout, cwd=cwd)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"HARNESS ERROR: {exc}", {}
    blob = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0 or "Not logged in" in blob:
        return False, f"HARNESS ERROR: {blob[:300]}", {}
    try:
        text, meta = parse_stream(proc.stdout)
    except Exception as exc:                    # never let one arm kill the sweep
        return False, f"HARNESS ERROR: unparseable stream: {exc}", {}
    if not text.strip():
        return False, f"HARNESS ERROR: empty result; {proc.stdout[-300:]}", meta
    return True, text, meta


def parse_stream(raw: str) -> tuple[str, dict]:
    """Extract the final answer and tool trace from a stream-json transcript.

    Every field access is type-guarded. The stream carries event kinds this
    harness does not model — hook lifecycle events, rate-limit notices — and at
    least one of them can put a plain string in `message`, where a bare
    `(ev.get("message") or {}).get(...)` raises AttributeError and takes the
    whole evaluation down with it. Unknown events must be skipped, not trusted.
    """
    final, tools, skill_paths, skill_md_reads = "", [], [], []
    for line in raw.split("\n"):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if not isinstance(ev, dict):
            continue
        if ev.get("type") == "result" and isinstance(ev.get("result"), str):
            final = ev["result"]
        message = ev.get("message")
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for blk in content:
            if not isinstance(blk, dict) or blk.get("type") != "tool_use":
                continue
            name = blk.get("name")
            tools.append(name)
            payload = json.dumps(blk.get("input") or {})
            if str(SKILL_DIR) not in payload:
                continue
            skill_paths.append(payload[:200])
            # Reading is the claim; listing the directory is not.
            if name in READING_TOOLS and any(f in payload for f in SKILL_CONTENT_FILES):
                skill_md_reads.append(payload[:200])
    return final, {
        "tools_used": sorted({t for t in tools if t}),
        "skill_files_opened": skill_paths,
        "skill_dir_touched": bool(skill_paths),
        "skill_was_read": bool(skill_md_reads),
    }


def grade_answer(fx, text):
    return {
        name: dict(zip(("passed", "evidence"), CRITERIA[name](text)))
        for name in FIXTURE_CRITERIA[fx["id"]]
    }


def run(outdir: pathlib.Path, model: str) -> int:
    outdir.mkdir(parents=True, exist_ok=True)
    neutral = tempfile.mkdtemp(prefix="dep-audit-eval-")
    for fx in fixtures():
        for rep in range(REPEATS):
            # Alternate arm order per repeat so a systematic first-call effect
            # cannot land on the same arm every time.
            arms = [("with_skill", True), ("without_skill", False)]
            if rep % 2:
                arms.reverse()
            for arm, with_skill in arms:
                cwd = str(SKILL_DIR) if with_skill else neutral
                # One bad arm records a harness error and the sweep continues.
                # Aborting would discard every result already collected, and the
                # grader already refuses to score an arm marked not-ok.
                try:
                    ok, text, meta = run_arm(fx, with_skill, model, cwd)
                except Exception as exc:
                    ok, text, meta = False, f"HARNESS ERROR: {exc!r}", {}
                # Build the names by string, not Path.with_suffix: the stem ends
                # in ".0", which with_suffix would treat as the existing suffix
                # and replace — silently producing files the grader cannot find.
                stem = f"{fx['id']}.{arm}.{rep}"
                (outdir / f"{stem}.txt").write_text(text, encoding="utf-8")
                (outdir / f"{stem}.meta.json").write_text(
                    json.dumps({"ok": ok, "arm": arm, "fixture": fx["id"],
                                "repeat": rep, "model": model, **meta}, indent=2),
                    encoding="utf-8")
                print(f"{fx['id']} {arm} rep{rep}: "
                      f"{'ok' if ok else 'HARNESS ERROR'}"
                      f"{'' if not with_skill else ' skill_read=' + str(meta.get('skill_was_read'))}")
    print(f"\nrecorded to {outdir}\nnow: python3 {__file__} --grade {outdir}")
    return 0


def skill_was_read(meta: dict) -> bool:
    """Derive the read-verification from the recorded trace, not the stored flag.

    Recomputing keeps one definition of "read the skill" and lets a corrected
    definition apply to runs recorded under the old one.
    """
    opened = meta.get("skill_files_opened")
    if opened is None:
        return bool(meta.get("skill_was_read"))
    return any(any(f in entry for f in SKILL_CONTENT_FILES) for entry in opened)


def _valid_results(outdir: pathlib.Path, fid: str, arm: str) -> tuple[int, int]:
    """(valid, total) recorded results for one arm."""
    files = _arm_files(outdir, fid, arm)
    valid = 0
    for f in files:
        meta_path = f.with_name(f.name[:-len(".txt")] + ".meta.json")
        if not meta_path.exists():
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if not meta.get("ok"):
            continue
        if arm == "with_skill" and not skill_was_read(meta):
            continue
        valid += 1
    return valid, len(files)


def repair(outdir: pathlib.Path, model: str) -> int:
    """Top up every arm that has fewer than REPEATS valid results.

    Each repeat is an independent sample of the same condition, so topping up a
    short arm is legitimate — but only if it is done blind. This function never
    looks at a grade: it repairs *every* deficient arm, whatever it scored, so
    it cannot be used to re-roll until a fixture wins.
    """
    neutral = tempfile.mkdtemp(prefix="dep-audit-eval-")
    deficient = []
    for fx in fixtures():
        for arm, with_skill in (("with_skill", True), ("without_skill", False)):
            valid, total = _valid_results(outdir, fx["id"], arm)
            if valid < REPEATS:
                deficient.append((fx, arm, with_skill, valid, total))
    if not deficient:
        print("every arm already has", REPEATS, "valid results; nothing to repair")
        return 0
    for fx, arm, with_skill, valid, total in deficient:
        print(f"{fx['id']} {arm}: {valid}/{REPEATS} valid — adding {REPEATS - valid}")
        for i in range(REPEATS - valid):
            rep = total + i
            cwd = str(SKILL_DIR) if with_skill else neutral
            try:
                ok, text, meta = run_arm(fx, with_skill, model, cwd)
            except Exception as exc:
                ok, text, meta = False, f"HARNESS ERROR: {exc!r}", {}
            stem = f"{fx['id']}.{arm}.{rep}"
            (outdir / f"{stem}.txt").write_text(text, encoding="utf-8")
            (outdir / f"{stem}.meta.json").write_text(
                json.dumps({"ok": ok, "arm": arm, "fixture": fx["id"],
                            "repeat": rep, "model": model, "repaired": True,
                            **meta}, indent=2), encoding="utf-8")
            print(f"  rep{rep}: {'ok' if ok else 'HARNESS ERROR'}"
                  f" skill_read={meta.get('skill_was_read')}")
    return 0


def _arm_files(d: pathlib.Path, fid: str, arm: str) -> list[pathlib.Path]:
    return sorted(d.glob(f"{fid}.{arm}.*.txt"))


def _majority(gradings: list[dict]) -> dict:
    out = {}
    for name in gradings[0]:
        votes = Counter(g[name]["passed"] for g in gradings)
        winner = votes.most_common(1)[0][0]
        ev = next(g[name]["evidence"] for g in gradings if g[name]["passed"] == winner)
        out[name] = {"passed": winner, "evidence": ev,
                     "votes": f"{votes[winner]}/{len(gradings)}"}
    return out


def grade_dir(outdir: pathlib.Path) -> int:
    incomplete, skipped, wins, losses, ties = [], [], 0, 0, 0
    for fx in fixtures():
        fid = fx["id"]
        report = {}
        for arm in ("with_skill", "without_skill"):
            files = _arm_files(outdir, fid, arm)
            if not files:
                incomplete.append(f"{fid}/{arm}: no output recorded")
                continue
            gradings, bad = [], False
            for f in files:
                meta_path = f.with_name(f.name[:-len(".txt")] + ".meta.json")
                if not meta_path.exists():
                    incomplete.append(f"{fid}/{arm}: {f.name} has no .meta.json sidecar")
                    bad = True
                    break
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                if not meta.get("ok"):
                    skipped.append(f"{fid}/{arm}: {f.name} recorded a harness error")
                    continue
                if arm == "with_skill" and not skill_was_read(meta):
                    touched = meta.get("skill_dir_touched")
                    skipped.append(
                        f"{fid}/{arm}: {f.name} never read any skill content"
                        + (" (only touched the directory)" if touched else "")
                        + " — a without-skill run wearing the wrong label")
                    continue
                gradings.append(grade_answer(fx, f.read_text(encoding="utf-8")))
            if bad or not gradings:
                continue
            if REQUIRE_EXACT_REPEATS and len(gradings) < REPEATS:
                incomplete.append(
                    f"{fid}/{arm}: {len(gradings)} valid result(s), need "
                    f"{REPEATS} — a majority vote over an incomplete sample is "
                    f"not a majority vote. Run --repair {outdir} to top it up.")
                continue
            gradings = gradings[:REPEATS]
            report[arm] = _majority(gradings)
        if len(report) != 2:
            continue
        w = sum(1 for c in report["with_skill"].values() if c["passed"])
        o = sum(1 for c in report["without_skill"].values() if c["passed"])
        verdict = "WIN" if w > o else ("LOSS" if w < o else "TIE")
        wins += verdict == "WIN"
        losses += verdict == "LOSS"
        ties += verdict == "TIE"
        print(f"\n{fid}  with={w}  without={o}  -> {verdict}")
        for arm in ("with_skill", "without_skill"):
            for name, c in report[arm].items():
                mark = "PASS" if c["passed"] else "FAIL"
                print(f"  {arm:15} {name:32} {mark} ({c['votes']}) {c['evidence'][:90]}")

    if skipped:
        print("\nExcluded results (not counted, arm topped up by --repair):")
        for line in skipped:
            print("  " + line)
    if incomplete:
        print("\nINCOMPLETE — not graded:")
        for line in incomplete:
            print("  " + line)
        return 3
    graded = wins + losses + ties
    if graded != len(fixtures()):
        print(f"\nINCOMPLETE: graded {graded} of {len(fixtures())} fixtures")
        return 3
    print(f"\nwins={wins} losses={losses} ties={ties} "
          f"(bar: >= {MIN_WINS} wins, <= {MAX_LOSSES} losses, over {graded} fixtures)")
    if losses > MAX_LOSSES:
        print(f"FAIL: {losses} fixture(s) got worse with the skill")
        return 1
    if wins < MIN_WINS:
        print(f"INCONCLUSIVE: {wins} win(s), need {MIN_WINS}. Ties mean the "
              f"baseline already knew the answer — that is information about "
              f"the fixture, not a pass for the skill.")
        return 3
    print("PASS")
    return 0


# ────────────────────────────── self test ───────────────────────────────

# (criterion, text that must pass, text that must fail)
SELF_TEST_CASES = [
    ("no_cvss_from_govulncheck",
     "govulncheck does not report a CVSS score; the Go vulnerability database "
     "does not publish severity. Priority comes from the evidence tier.",
     "govulncheck reports GO-2023-2102 with CVSS 7.5, so treat it as High."),
    ("names_alias_lookup",
     "To get a score, look up the CVE alias in NVD and cite it.",
     "It is high severity."),
    ("no_nonexistent_govulncheck_flag",
     "```bash\ngovulncheck -scan symbol ./...\n```",
     "```bash\ngovulncheck -go=1.21 -mode=query ./...\n```"),
    ("says_flag_absent",
     "There is no -go flag, and query mode does not exist.",
     "Use -go=1.21 to pin the language version."),
    ("json_exit_code_is_zero",
     "With -json govulncheck exits 0 regardless of findings.",
     "Check $? after the scan and fail if non-zero."),
    ("ci_gate_can_fail",
     "```bash\ngovulncheck ./...; rc=$?\n[ \"$rc\" -eq 3 ] && exit 1\n```",
     "```bash\ngovulncheck -json ./... > out.json\nif [ $? -ne 0 ]; then exit 1; fi\n```"),
    ("no_legal_verdict",
     "This needs legal review before release.",
     "GPL-3.0 is present, so you cannot ship this product."),
    ("escalates_to_legal",
     "Route this to legal review with the dependency path attached.",
     "Just swap the dependency and move on."),
    ("names_distribution_factor",
     "Whether an obligation attaches depends on whether you distribute the binary.",
     "It is copyleft, so it is a problem."),
    ("no_phantom_env_var",
     "Set GOPRIVATE for internal prefixes.",
     "```bash\nexport GONOSUMCHECK=*\n```"),
    ("names_real_env_var",
     "Set GOPRIVATE, which defaults GONOPROXY and GONOSUMDB.",
     "Turn off the checksum check in your environment."),
    ("incompatible_same_module",
     "+incompatible is treated as part of the same module as v1.x.",
     "It is resolved as a distinct v2 module."),
    ("no_mvs_blindness_claim",
     "MVS compares +incompatible versions like any others.",
     "The major version is invisible to MVS, which cannot see it."),
    ("warns_major_jump",
     "A routine go get -u can automatically upgrade across a major version.",
     "It is only a naming quirk."),
]


# Excerpts from the 2026-08-14 recorded run, kept verbatim. These pin the
# criteria to language models actually produce, not to language the criteria's
# author imagined. Two criteria were widened after that run because they missed
# correct answers; these cases exist so the widening cannot silently narrow
# again. Both arms are represented on purpose — a criterion tuned only on
# with-skill text would be a thumb on the scale.
REAL_ANSWER_CASES = [
    ("says_flag_absent", "with_skill", True,
     "Neither request maps to a real govulncheck flag as literally phrased — I "
     "confirmed `-go=` and `-mode=query` are both documented as non-existent, "
     "LLM-hallucinated flags (exit code 2, usage error)."),
    ("says_flag_absent", "without_skill", True,
     "Scan using Go 1.21 language/toolchain semantics (govulncheck itself has "
     "no -go flag; you control this via GOTOOLCHAIN)."),
    ("incompatible_same_module", "with_skill", True,
     "the toolchain treats `v2.5.0+incompatible` as just another version of the "
     "*same* module path as any `v1.x` releases — not a separate module."),
    ("incompatible_same_module", "without_skill", True,
     "- It's just another version on the same module path."),
    ("no_cvss_from_govulncheck", "without_skill", True,
     "govulncheck doesn't report CVSS scores at all — that's a common "
     "misconception worth correcting."),
    ("no_mvs_blindness_claim", "with_skill", True,
     'This matters more than "MVS ignores it" \u2014 it\'s the opposite. MVS '
     "**actively considers** higher `+incompatible` versions as valid upgrade "
     "targets for the same module."),
    ("no_mvs_blindness_claim", "with_skill", False,
     "The major version is invisible to MVS, so it never considers it."),
    ("escalates_to_legal", "with_skill", True,
     "If you want, I can run the actual audit against your repo to produce the "
     "escalation packet with those facts filled in, and then this goes to your "
     "legal/compliance reviewer for the actual ship/no-ship call."),
    ("escalates_to_legal", "without_skill", True,
     "This is a licensing risk assessment, not legal advice \u2014 if there is "
     "any doubt, get your counsel to sign off before you ship."),
    ("escalates_to_legal", "with_skill", False,
     "GPL-3.0 is restricted, so replace the dependency and move on."),
    ("ci_gate_can_fail", "without_skill", False,
     "name: Vulnerability Scan\non:\n  push:\njobs:\n  scan:\n    steps:\n"
     "      - run: govulncheck -json ./... > out.json\n"
     "      - run: if [ $? -ne 0 ]; then exit 1; fi"),
]


def real_answer_check() -> list[str]:
    """Replay the pinned real excerpts. Returns a list of failure messages."""
    out = []
    for name, arm, expected, text in REAL_ANSWER_CASES:
        got, evidence = CRITERIA[name](text)
        if got is not expected:
            out.append(
                f"{name} on a real {arm} answer: expected "
                f"{'PASS' if expected else 'FAIL'}, got "
                f"{'PASS' if got else 'FAIL'} ({evidence[:90]})")
    return out


def self_test() -> int:
    """Every criterion must accept a correct answer and reject a wrong one.

    A criterion that passes everything measures nothing; one that fails
    everything is worse. Both directions are asserted, per criterion.
    """
    failures = []
    covered = {name for name, _g, _b in SELF_TEST_CASES}
    for name in CRITERIA:
        if name not in covered:
            failures.append(f"{name}: no self-test case")
    for name, good, bad in SELF_TEST_CASES:
        fn = CRITERIA.get(name)
        if fn is None:
            failures.append(f"{name}: not a known criterion")
            continue
        ok_good, ev_good = fn(good)
        ok_bad, ev_bad = fn(bad)
        if not ok_good:
            failures.append(f"{name}: rejected a CORRECT answer ({ev_good})")
        if ok_bad:
            failures.append(f"{name}: accepted a WRONG answer ({ev_bad})")

    used = {c for names in FIXTURE_CRITERIA.values() for c in names}
    for name in CRITERIA:
        if name not in used:
            failures.append(f"{name}: defined but no fixture uses it")
    for fid, names in FIXTURE_CRITERIA.items():
        if not (EVAL_DIR / f"{fid}.json").exists():
            failures.append(f"{fid}: no fixture file")
        for n in names:
            if n not in CRITERIA:
                failures.append(f"{fid}: unknown criterion {n!r}")

    failures.extend(real_answer_check())

    for line in failures:
        print("FAIL " + line)
    print(f"\nself-test: {len(SELF_TEST_CASES)} criteria, "
          f"{len(REAL_ANSWER_CASES)} pinned real answers, {len(failures)} failures")
    return 1 if failures else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--grade", metavar="DIR")
    ap.add_argument("--repair", metavar="DIR",
                    help="re-run only the arms with fewer than REPEATS valid "
                         "results; never looks at grades")
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--out", default=str(SKILL_DIR / "scripts" / "eval_runs" / "latest"))
    args = ap.parse_args()

    if args.self_test:
        return self_test()
    if args.run:
        return run(pathlib.Path(args.out), args.model)
    if args.repair:
        return repair(pathlib.Path(args.repair), args.model)
    if args.grade:
        return grade_dir(pathlib.Path(args.grade))
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
