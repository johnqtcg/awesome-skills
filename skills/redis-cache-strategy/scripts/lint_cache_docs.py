#!/usr/bin/env python3
"""Semantic invariant linter for the redis-cache-strategy docs.

Why a second gate
-----------------
check_go_snippets.py proves the examples compile. It cannot prove they are
right: a deterministic hash used where the text promises a random shard is
type-correct, and an unchecked type assertion compiles cleanly and panics in
production. Every rule below encodes one defect class that the compiler is
blind to and that a fixture assertion would never reach.

Coverage is declared as data, not prose: RULES lists what is checked, and every
rule carries a `violation` string that MUST make it fire. `--selftest` asserts
exactly that, so a rule that has silently stopped matching anything fails the
build instead of reporting a clean run.

Exempt spans
------------
Anti-examples deliberately contain the defects these rules hunt. The WRONG half
of a `// WRONG:` / `// RIGHT:` pair is blanked to NUL of the same width before
matching -- NUL rather than deletion so line numbers stay exact and adjacent
lines never fuse into a false match.

Exit codes: 0 clean · 1 violations found · 3 selftest failure
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
SKILL_MD = SKILL_DIR / "SKILL.md"
REFS = SKILL_DIR / "references"


# --------------------------------------------------------------------------
# span handling
# --------------------------------------------------------------------------

def blank_wrong_spans(text: str) -> str:
    """Replace the WRONG half of each anti-example with NUL, preserving width.

    A WRONG span runs from a `// WRONG` (or `# WRONG`) marker to the next
    `// RIGHT` marker or the end of the fenced block, whichever comes first.
    """
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    in_fence = False
    in_wrong = False
    for ln in lines:
        stripped = ln.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            in_wrong = False
            out.append(ln)
            continue
        if in_fence:
            if re.search(r"(//|#|--)\s*(WRONG|Wrong|BAD)", ln):
                in_wrong = True
            elif re.search(r"(//|#|--)\s*(RIGHT|Right|CORRECT|GOOD)", ln):
                in_wrong = False
            if in_wrong:
                out.append("\x00" * (len(ln) - 1) + "\n" if ln.endswith("\n") else "\x00" * len(ln))
                continue
        out.append(ln)
    return "".join(out)


def strip_comments(body: str) -> str:
    """Blank out // comment tails, preserving width and line count.

    Without this, a rule fires on the prose that explains why the defect is a
    defect -- "a bare val.([]byte) panics" would be reported as an unchecked
    type assertion. The guard must not flag its own correction notice.
    """
    out = []
    for ln in body.split("\n"):
        i = ln.find("//")
        out.append(ln if i < 0 else ln[:i] + " " * (len(ln) - i))
    return "\n".join(out)


def code_blocks(text: str) -> list[tuple[int, str]]:
    """Return (start_line, body) for each ```go block."""
    lines = text.splitlines()
    blocks: list[tuple[int, str]] = []
    i = 0
    while i < len(lines):
        if lines[i].strip() == "```go":
            j = i + 1
            body: list[str] = []
            while j < len(lines) and lines[j].strip() != "```":
                body.append(lines[j])
                j += 1
            blocks.append((i + 1, "\n".join(body)))
            i = j
        i += 1
    return blocks


# --------------------------------------------------------------------------
# rules
# --------------------------------------------------------------------------

@dataclass
class Rule:
    id: str
    summary: str
    scope: str  # "code" | "prose" | "skill" | "global"
    violation: str  # input that MUST make this rule fire (selftest)
    files: tuple[str, ...] = ()
    _fn: object = field(default=None, repr=False)


RULES: list[Rule] = []


def rule(id_, summary, scope, violation, files=()):
    def deco(fn):
        RULES.append(Rule(id_, summary, scope, violation, files, fn))
        return fn
    return deco


HASH_FN = r"(?:crc32\.\w+|fnv\.\w+|md5\.\w+|sha1\.\w+|sha256\.\w+|hash/\w+)"


@rule(
    "RC001",
    "Shard/replica index must not be derived from a hash of the key "
    "(deterministic selection spreads nothing).",
    "code",
    violation="shard := crc32.ChecksumIEEE([]byte(key)) % shardCount",
)
def rc001(body: str):
    for m in re.finditer(
        rf"(\w+)\s*:?=\s*{HASH_FN}\([^%\n]*\)\s*%\s*(\w*[Ss]hard\w*|\w*[Rr]eplica\w*)", body
    ):
        yield m.start(), f"replica index `{m.group(1)}` derived from a hash of the key"


@rule(
    "RC002",
    "Single-value type assertion on an interface returned by cache/singleflight "
    "(panics on an unexpected type; use the two-value form).",
    "code",
    violation="return result.([]byte), err",
)
def rc002(body: str):
    for m in re.finditer(r"(?<![,\w])(\w+)\.\((\[\]byte|\*\w+|string|int64)\)", body):
        line_start = body.rfind("\n", 0, m.start()) + 1
        line = body[line_start:body.find("\n", m.start()) if body.find("\n", m.start()) != -1 else len(body)]
        if re.search(r",\s*ok\s*:?=", line) or re.search(r",\s*_\s*:?=", line):
            continue
        yield m.start(), f"unchecked type assertion `{m.group(0)}`"


@rule(
    "RC003",
    "Sentinel error compared with == instead of errors.Is (a wrapped error "
    "silently makes it false).",
    "code",
    violation="if err == redis.Nil {",
)
def rc003(body: str):
    for m in re.finditer(r"(?:err|\w+Err)\s*==\s*(redis\.Nil|sql\.ErrNoRows|Err\w+)", body):
        yield m.start(), f"`== {m.group(1)}` must be errors.Is"


@rule(
    "RC004",
    "Redis write whose error is discarded in a non-anti-example "
    "(a silent populate/invalidate failure is invisible and unbounded).",
    "code",
    violation="rdb.Set(ctx, key, val, ttl)",
)
def rc004(body: str):
    for m in re.finditer(r"^\s*(rdb|pipe)\.(Set|Del|SetNX|Expire)\([^\n]*\)\s*$", body, re.M):
        if ".Err()" in m.group(0):
            continue
        if m.group(1) == "pipe":  # individual stages are checked at Exec, below
            continue
        yield m.start(), f"discarded error from `{m.group(0).strip()}`"
    # A bare pipe.Exec discards the ONLY error the pipeline ever reports, so a
    # partial fan-out failure becomes invisible. This is the counterpart to the
    # `pipe` exemption above -- without it that exemption is a hole.
    for m in re.finditer(r"^\s*(?:pipe|p)\.Exec\([^\n]*\)\s*$", body, re.M):
        yield m.start(), "discarded error from a bare `pipe.Exec(...)`"


@rule(
    "RC005",
    "rand.Intn/Int31n/Int63n whose argument can be zero (panics).",
    "code",
    violation="jitter := rand.Intn(2*jitterRange) - jitterRange",
)
def rc005(body: str):
    for m in re.finditer(r"rand\.(Intn|Int31n|Int63n)\(\s*(?:\d+\s*\*\s*)?([\w.]+)", body):
        var = m.group(2)
        if var.isdigit():  # a literal argument cannot be zero unless written as 0
            if var != "0":
                continue
        guard = re.search(rf"if\s+{re.escape(var)}\s*<=?\s*0", body)
        if not guard:
            yield m.start(), f"`rand.{m.group(1)}` argument `{var}` has no zero guard"


@rule(
    "RC006",
    "Write-through must not be sold as strong/zero-staleness without the "
    "cache-write failure semantics that bound it.",
    "prose",
    violation="| Strong (immediate) | Moderate writes | **Write-Through** | Near-zero |",
    files=("cache-patterns.md",),
)
def rc006(text: str):
    for m in re.finditer(r"\|[^|\n]*[Ss]trong \(immediate\)[^|\n]*\|", text):
        yield m.start(), "pattern matrix claims strong/immediate consistency"
    # Anchor on the HEADING, not the bare phrase: the phrase also appears in a
    # cross-reference, which would keep this check green after the section is
    # renamed or deleted.
    if re.search(r"[Ww]rite-[Tt]hrough", text) and not re.search(
        r"^#{2,4}\s+Cache-write failure semantics", text, re.M
    ):
        yield 0, "write-through documented without a cache-write failure semantics section"


ABSOLUTE_FRESHNESS = re.compile(
    r"(?:always|guaranteed(?:ly)?|never stale|immediately|zero[- ]staleness)"
    r"[^.\n]{0,60}?(?:fresh|up[- ]to[- ]date)"
    r"|(?:fresh|up[- ]to[- ]date)[^.\n]{0,30}?(?:always|guaranteed)",
    re.I,
)


@rule(
    "RC017",
    "No absolute freshness claim about a cache without a qualification on the "
    "same line -- a cache in front of a database is eventually consistent in "
    "every pattern.",
    "global",
    violation="  2. Cache HIT → return, always fresh since writes update the cache",
)
def rc017(text: str):
    # The original defect: the words "always fresh" sat in a flow diagram three
    # paragraphs above the section explaining why that is false, and RC006 --
    # keyed on the phrase "strong (immediate)" -- never saw the rewording.
    #
    # The repudiation must be on the SAME LINE as the claim. A window-scoped
    # check was tried first and let this through: "read-your-writes" appears in
    # a "Best for" bullet ~200 characters later, so an unqualified "always
    # fresh" in the diagram was cleared by a sentence that was not about it.
    # A refutation that is not bound to the claim is a bypass, not a guard.
    for m in ABSOLUTE_FRESHNESS.finditer(text):
        lo = text.rfind("\n", 0, m.start()) + 1
        hi = text.find("\n", m.end())
        line = text[lo:hi if hi != -1 else len(text)]
        if re.search(r"\bNOT\b|\bnot\b|\bnever\b|\bno\b", line):
            continue
        yield m.start(), f"unqualified freshness claim {m.group(0)!r}"


@rule(
    "RC007",
    "Value-shape guidance must name the listpack thresholds and gate per-field "
    "TTL on HEXPIRE/7.4 -- and each claim must live in its OWN bullet.",
    "skill",
    violation="- **TTL**: per-field expiry is available.\n   - **Memory**: a Hash is smaller.",
)
def rc007(text: str):
    # Anchor on the bullet list itself, not on a prose phrase. The earlier
    # version guarded on the words "large value"; the section was later reworded
    # to "values over the bound" and the whole rule silently stopped running
    # while still passing its selftest. Find the bullets, or say so.
    bullets = dict(re.findall(r"^\s*-\s+\*\*(Memory|TTL)\*\*:([^\n]*)", text, re.M))
    if not bullets:
        if re.search(r"\bHash\b", text):
            yield 0, "value-shape guidance has no **Memory**/**TTL** bullets to check"
        return
    # Per-subject: the version gate must be in the TTL bullet. Checking whether
    # "HEXPIRE" appears anywhere in the file is defeated by any other mention.
    for bullet, tokens in (
        ("TTL", ("HEXPIRE", "7.4")),
        ("Memory", ("hash-max-listpack-entries", "hash-max-listpack-value")),
    ):
        if bullet not in bullets:
            yield 0, f"value-shape guidance is missing its **{bullet}** bullet"
            continue
        for token in tokens:
            if token not in bullets[bullet]:
                yield text.find(f"**{bullet}**"), f"**{bullet}** bullet does not name `{token}`"


@rule(
    "RC008",
    "Distributed-lock guidance must cover fencing, bounded renewal and failover "
    "-- TTL + token + CAS alone is not a safe lock.",
    "global",
    violation="(distributed lock guidance without fencing/renewal/failover)",
)
def rc008(text: str):
    if not re.search(r"[Dd]istributed lock", text):
        return
    for token in ("fencing", "renew", "failover"):
        if not re.search(token, text, re.I):
            yield 0, f"distributed-lock guidance never mentions `{token}`"


@rule(
    "RC009",
    "Gate 1 blocking items must appear in a STOP condition and must not be "
    "described as assumable.",
    "skill",
    violation="**PROCEED**: At least data source, cache role, and consistency requirement are known or assumed.",
)
def rc009(text: str):
    m = re.search(r"### Gate 1.*?(?=### Gate 2)", text, re.S)
    if not m:
        yield 0, "Gate 1 section not found"
        return
    g = m.group(0)
    if re.search(r"(cache role|data source|consistency requirement)[^.\n]*\bor assumed\b", g, re.I):
        yield m.start(), "a blocking Gate 1 item is described as assumable"
    # Per-row check on the table's "If unknown" cell. The STOP condition below
    # and this column are two independent statements about the same item; when
    # they disagree the table is what a reader follows, and the contradiction is
    # exactly the Gate 1 defect this rule exists to prevent.
    for label, item in (("Cache role", "cache role"),
                        ("Data source", "data source"),
                        ("Consistency requirement", "consistency requirement")):
        row = re.search(rf"^\|\s*\*\*{label}[^|\n]*\|([^|\n]*)\|([^|\n]*)\|", g, re.M | re.I)
        if not row:
            yield m.start(), f"blocking item `{item}` has no row in the Gate 1 table"
            continue
        if not re.search(r"blocking|cannot be assumed", row.group(2), re.I):
            yield m.start(), (
                f"Gate 1 table lets `{item}` default to "
                f"{row.group(2).strip()!r} — it is declared blocking")
    stop = re.search(r"\*\*STOP\*\*.*?(?=\*\*PROCEED\*\*)", g, re.S)
    if not stop:
        yield m.start(), "Gate 1 has no STOP condition"
        return
    # Normalise wrapped lines: "data\nsource" must still match "data source".
    stop_text = re.sub(r"\s+", " ", stop.group(0)).lower()
    for item in ("cache role", "data source", "consistency requirement"):
        if item not in stop_text:
            yield m.start(), f"blocking item `{item}` absent from the Gate 1 STOP condition"


TIER_PREFIX = {"Critical": "C", "Standard": "S", "Hygiene": "H"}


def skill_items(text: str) -> dict[str, list[int]]:
    """{'C': [1,2,...]} — the item IDs §5 actually defines, in order."""
    sec = re.search(r"^## §5\b.*?(?=^## §6\b)", text, re.S | re.M)
    if not sec:
        return {}
    out: dict[str, list[int]] = {}
    for pref, num in re.findall(r"^\*\*([CSH])(\d+) — ", sec.group(0), re.M):
        out.setdefault(pref, []).append(int(num))
    return out


@rule(
    "RC010",
    "§5 must be the only item list: every ID it defines is contiguous per tier "
    "and covered by exactly one §8 tier range, and §8 defines no items of its own.",
    "skill",
    violation=(
        "## §5 x\n\n**C1 — a.**\n\n**C3 — b.**\n\n**S1 — c.**\n\n**H1 — d.**\n\n"
        "## §6 x\n\n## §8 x\n\n| **Critical** | `C1–C2` |\n| **Standard** | `S1–S1` |\n"
        "| **Hygiene** | `H1–H1` |\nPASS FAIL INCOMPLETE\n\n## §9 x\n"
    ),
)
def rc010(text: str):
    # The failure this replaces: §5 listed 14 items and §8 scored a DIFFERENT 14,
    # so a Critical golden defect could be found by §5 and land in a Standard
    # bucket that tolerates one failure. Two lists cannot be kept in sync by
    # review; the fix is that there is one list, and this rule proves it.
    defined = skill_items(text)
    if not defined:
        yield 0, "§5 defines no `**<C|S|H><n> — ` items (section missing or reformatted)"
        return

    for pref, nums in sorted(defined.items()):
        dupes = {n for n in nums if nums.count(n) > 1}
        if dupes:
            yield 0, f"§5 defines {pref}{sorted(dupes)} more than once"
        expected = list(range(1, max(nums) + 1))
        if sorted(set(nums)) != expected:
            missing = sorted(set(expected) - set(nums))
            yield 0, f"§5 {pref} items are not contiguous from 1 — missing {missing}"

    sec8 = re.search(r"^## §8\b.*?(?=^## §9\b)", text, re.S | re.M)
    if not sec8:
        yield 0, "§8 section not found"
        return
    body8 = sec8.group(0)

    # §8 must not re-introduce a list of its own.
    if re.search(r"^- \[ \]", body8, re.M):
        yield sec8.start(), "§8 declares its own checkbox items — §5 is the only item list"

    for tier, pref in TIER_PREFIX.items():
        row = re.search(
            rf"\|\s*\*\*{tier}\*\*\s*\|[^|\n]*?([CSH])(\d+)\s*[–—-]\s*([CSH])?(\d+)",
            body8,
        )
        if not row:
            yield sec8.start(), f"§8 has no item range for the {tier} tier"
            continue
        lo_pref, lo, hi_pref, hi = row.group(1), int(row.group(2)), row.group(3), int(row.group(4))
        if lo_pref != pref or (hi_pref and hi_pref != pref):
            yield sec8.start(), f"§8 {tier} range uses prefix {lo_pref}, expected {pref}"
            continue
        nums = defined.get(pref, [])
        if not nums:
            yield sec8.start(), f"§8 scores {pref}{lo}–{pref}{hi} but §5 defines no {pref} items"
            continue
        if (lo, hi) != (1, max(nums)):
            yield sec8.start(), (
                f"§8 {tier} range is {pref}{lo}–{pref}{hi} but §5 defines "
                f"{pref}1–{pref}{max(nums)}")

    for pref in defined:
        if pref not in TIER_PREFIX.values():
            yield 0, f"§5 defines {pref}* items that no §8 tier scores"

    for verdict in ("PASS", "FAIL", "INCOMPLETE"):
        if not re.search(rf"\b{verdict}\b", body8):
            yield sec8.start(), f"§8 never names the `{verdict}` verdict"


VERDICTS = ("PASS", "WARN", "FAIL", "N/A", "NOT SCOREABLE")


@rule(
    "RC014",
    "The scoring vocabulary must be DEFINED where the items are: a verdict table "
    "with rows for PASS/WARN/FAIL/N-A/NOT SCOREABLE, or an unjudgeable item "
    "silently becomes a pass.",
    "skill",
    violation=(
        "## §5 x\n\n| Verdict | Meaning |\n|---|---|\n| **PASS** | ok |\n"
        "| **FAIL** | no |\n\n**C1 — a.** Silence is FAIL.\n\n## §6 x\n"
    ),
)
def rc014(text: str):
    sec = re.search(r"^## §5\b.*?(?=^## §6\b)", text, re.S | re.M)
    if not sec:
        yield 0, "§5 section not found"
        return
    head = sec.group(0)
    # Parse the table's first column rather than searching §5 for the words.
    # A bare substring check was tried first and an adversarial probe defeated
    # it: renaming the WARN row left the rule green, because C6's prose says
    # "is a FAIL, not a WARN" and that unrelated sentence satisfied the search.
    # A verdict has to be *defined*, and only a table row defines one.
    rows = {re.sub(r"[*`]", "", c).strip().upper()
            for c in re.findall(r"^\|\s*([^|\n]+?)\s*\|", head, re.M)}
    for token in VERDICTS:
        if token not in rows:
            yield sec.start(), f"§5 has no verdict-table row defining `{token}`"
    # The loophole that makes a dynamic denominator dishonest: marking an item
    # N/A because nobody wrote about it, rather than because it cannot apply.
    if not re.search(r"[Ss]ilence is FAIL", head):
        yield sec.start(), "§5 does not state that an unaddressed item is FAIL, not N/A"


VERSION_GATED: tuple[tuple[str, str, str], ...] = (
    # (token regex, version regex that must be nearby, human name)
    (r"\bHEXPIRE\b", r"7\.4", "HEXPIRE (7.4+)"),
    (r"\bDELEX\b", r"8\.4", "DELEX (8.4+)"),
    (r"\bIFEQ\b", r"8\.4", "SET/DELEX IFEQ (8.4+)"),
    (r"\bHOTKEYS\b", r"8\.6", "HOTKEYS (8.6+)"),
    (r"`CF\.", r"8\.0", "cuckoo filter CF.* (8.0+)"),
    (r"\bOVERWRITTEN\b", r"8\.2", "OVERWRITTEN keyspace event (8.2+)"),
    (r"\b(?:allkeys|volatile)-lrm\b", r"8\.6", "*-lrm eviction (8.6+)"),
    (r"\bcompact hash", r"8\.10", "compact hashes (8.10+)"),
    (r"hash-max-listpack", r"7\.0|8\.10|ziplist", "listpack config names (7.0+)"),
)


@rule(
    "RC015",
    "A version-gated Redis feature must carry its version where it is named -- "
    "an unqualified feature claim is wrong on every older server.",
    "global",
    violation="Release the lock with `DELEX key IFEQ token`, which is atomic.",
)
def rc015(text: str):
    # The defect this prevents is the one the 2026-08 review found: the skill
    # assumed one Redis version globally, so every claim silently applied to a
    # server that might not have the feature. Naming the version at each use is
    # the only form that survives a copy-paste into a review.
    for token_re, ver_re, name in VERSION_GATED:
        for m in re.finditer(token_re, text):
            lo, hi = max(0, m.start() - 320), min(len(text), m.end() + 320)
            if not re.search(ver_re, text[lo:hi]):
                yield m.start(), f"`{name}` named with no version qualifier nearby"


@rule(
    "RC018",
    "Keyspace notifications must never be listed as an authoritative invalidation "
    "mechanism -- Pub/Sub is fire-and-forget and node-local, so it cannot sit in "
    "the same tier as CDC or a transactional outbox.",
    "global",
    violation=(
        "Invalidation options: TTL expiry, explicit invalidation on write, or "
        "event-driven (CDC, or keyspace `OVERWRITTEN` on 8.2+)."
    ),
)
def rc018(text: str):
    # The exact error this rule was written for, in the sentence that shipped it:
    # `OVERWRITTEN` was listed beside CDC as an equivalent invalidation strategy.
    # It is not equivalent. Redis documents Pub/Sub as "fire and forget" -- a
    # disconnected subscriber loses every event delivered while it was away --
    # and in a cluster events are NOT broadcast, so each node must be subscribed
    # separately. It also reports that a *Redis key* changed, not that a
    # *database row* did.
    durable = re.compile(r"\bCDC\b|transactional outbox|\boutbox\b", re.I)
    keyspace = re.compile(r"keyspace (?:notification|event)|\bOVERWRITTEN\b|\bTYPE_CHANGED\b")
    # The qualifier must be near the mention: naming the caveat once, chapters
    # away, does not stop a reader acting on the sentence in front of them.
    qualified = re.compile(
        r"fire[- ]and[- ]forget|fire and forget|best[- ]effort|lossy|not durable"
        r"|node[- ]local|not an authoritative|must not be counted|are \*\*not\*\*",
        re.I,
    )
    for m in keyspace.finditer(text):
        lo, hi = max(0, m.start() - 400), min(len(text), m.end() + 400)
        window = text[lo:hi]
        if durable.search(window) and not qualified.search(window):
            yield m.start(), (
                f"`{m.group(0)}` presented alongside a durable mechanism with no "
                f"fire-and-forget / best-effort qualifier")


@rule(
    "RC016",
    "A delayed second delete must not be prescribed as an in-process sleep or "
    "goroutine -- it dies with the process, exactly like AE-2's write-behind.",
    "global",
    violation=(
        "Schedule the second DEL after 500ms via a sleep in goroutine.\n"
        "This absorbs the read-populate race."
    ),
)
def rc016(text: str):
    inproc = re.compile(
        r"sleep in (?:a )?goroutine|time\.Sleep|time\.AfterFunc|sleeping goroutine", re.I)
    delayed = re.compile(r"double[- ]delete|second DEL\b|delayed DEL\b|second delete", re.I)
    # Allow-list the safe shape: naming the mechanism is fine when the same
    # paragraph rejects it. Without this the rule fires on the table row and the
    # paragraph written to warn against it.
    repudiation = re.compile(
        r"do not|don't|\bnot a\b|fails the same way|acceptable only|\*\*no\*\*"
        r"|is a hope|loses|silently|never\b|prefer\b",
        re.I,
    )
    offset = 0
    for para in text.split("\n\n"):
        if inproc.search(para) and delayed.search(para) and not repudiation.search(para):
            yield offset, "delayed double-delete prescribed as an in-process sleep/goroutine"
        offset += len(para) + 2


@rule(
    "RC013",
    "Blocking O(N) or destructive command on a live keyspace (KEYS/FLUSHALL/"
    "FLUSHDB) -- single-threaded Redis stalls every other client meanwhile.",
    "code",
    violation='keys, _ := rdb.Keys(ctx, "user:"+userID+":*").Result()',
)
def rc013(body: str):
    for m in re.finditer(r"\b(?:rdb|client)\.(Keys|FlushAll|FlushDB)\(", body):
        yield m.start(), f"`{m.group(1)}` blocks the server; use SCAN or a tracked key set"


@rule(
    "RC012",
    "Cache write with an explicit zero expiration (no TTL) -- the entry never "
    "expires, so a missed invalidation is stale forever, not stale until TTL.",
    "code",
    violation='rdb.Set(ctx, "product:"+p.ID, data, 0)',
)
def rc012(body: str):
    for m in re.finditer(
        r"\b(?:rdb|pipe|client)\.(Set|SetNX|SetEX)\((?:[^()\n]|\([^()\n]*\))*,\s*0\s*\)", body
    ):
        yield m.start(), f"`{m.group(1)}` with expiration 0 — the key never expires"


@rule(
    "RC011",
    "Prose must not recommend hash-of-key shard/replica notation without "
    "repudiating it (RC001 only sees code blocks).",
    "global",
    violation="Defense: local cache, key sharding (`key:{hash%N}`), or read replicas.",
)
def rc011(text: str):
    # RC001 is scoped to ```go blocks. The same defect shipped for months in a
    # one-line prose summary -- the surface most readers actually act on --
    # because no rule looked outside code. Scope: paragraphs, code fences removed.
    prose = re.sub(r"```.*?```", "", text, flags=re.S)
    notation = re.compile(r"\{?\s*hash\s*%\s*\w+\s*\}?|crc32\.\w+\([^)]*\)\s*%", re.I)
    # Allow-list the safe shape: naming the notation is fine *when the same
    # paragraph says it is wrong*. Without this the rule would fire on the
    # sentence written to correct it.
    repudiation = re.compile(
        r"non-fix|deterministic|spreads nothing|must come from|chosen by the caller"
        r"|is the classic|the bug|wrong|never|do not|don't",
        re.I,
    )
    offset = 0
    for para in prose.split("\n\n"):
        if notation.search(para) and not repudiation.search(para):
            yield offset, "prose recommends a hash-derived shard/replica index without repudiating it"
        offset += len(para) + 2


# --------------------------------------------------------------------------
# driver
# --------------------------------------------------------------------------

def line_of(text: str, off: int) -> int:
    return text.count("\n", 0, off) + 1


def locate(paths: list[Path], texts: list[str], off: int) -> str:
    """Map an offset in the joined document back to `file:line`.

    A global-scope finding used to print `<all docs>`, which is a defect report
    nobody can act on -- the reader has to grep for the pattern themselves and
    may fix a different occurrence than the one that fired.
    """
    cursor = 0
    for p, t in zip(paths, texts):
        end = cursor + len(t)
        if off <= end:
            return f"{p.relative_to(SKILL_DIR)}:{t.count(chr(10), 0, off - cursor) + 1}"
        cursor = end + 1  # the "\n" join adds one character between files
    return "<all docs>"


def run(paths: list[Path]) -> list[str]:
    findings: list[str] = []
    texts = [p.read_text(encoding="utf-8") for p in paths]
    joined = "\n".join(texts)
    joined_masked = blank_wrong_spans(joined)

    for p in paths:
        raw = p.read_text(encoding="utf-8")
        masked = blank_wrong_spans(raw)
        rel = p.relative_to(SKILL_DIR)

        for r in RULES:
            if r.files and p.name not in r.files:
                continue
            if r.scope == "code":
                for start, body in code_blocks(masked):
                    for off, msg in r._fn(strip_comments(body)):
                        findings.append(f"{rel}:{start + body.count(chr(10), 0, off) + 1}: {r.id} {msg}")
            elif r.scope == "prose":
                for off, msg in r._fn(masked):
                    findings.append(f"{rel}:{line_of(masked, off)}: {r.id} {msg}")
            elif r.scope == "skill" and p.name == "SKILL.md":
                for off, msg in r._fn(masked):
                    findings.append(f"{rel}:{line_of(masked, off)}: {r.id} {msg}")

    masked_texts = [blank_wrong_spans(t) for t in texts]
    for r in RULES:
        if r.scope == "global":
            for off, msg in r._fn(joined_masked):
                findings.append(f"{locate(paths, masked_texts, off)}: {r.id} {msg}")
    return findings


def selftest() -> int:
    """Every rule must fire on its declared violating input."""
    bad = []
    for r in RULES:
        if r.scope == "code":
            fired = list(r._fn(r.violation))
        elif r.id == "RC006":
            fired = list(r._fn(r.violation + "\nwrite-through\n"))
        elif r.id == "RC007":
            fired = list(r._fn("6. Key and value size bounded. " + r.violation))
        elif r.id == "RC008":
            fired = list(r._fn("Distributed lock bounded: TTL, token, Lua CAS release."))
        elif r.id == "RC009":
            fired = list(r._fn(
                "### Gate 1: Context Collection\n\n**STOP**: unclear.\n\n"
                + r.violation + "\n\n### Gate 2:"))
        elif r.id == "RC010":
            fired = list(r._fn(
                "### Critical\n\n- [ ] a\n\n### Standard\n\n- [ ] b\n\n"
                "### Hygiene\n\n- [ ] c\n\n" + r.violation))
        else:
            fired = list(r._fn(r.violation))
        if not fired:
            bad.append(f"{r.id}: did NOT fire on its own violating input -- rule is dead")
    print(f"selftest: {len(RULES) - len(bad)}/{len(RULES)} rules effective")
    for b in bad:
        print(f"  {b}")
    return 3 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--list", action="store_true", help="print declared coverage")
    args = ap.parse_args()

    if args.list:
        for r in RULES:
            print(f"{r.id}  [{r.scope}]  {r.summary}")
        return 0
    if args.selftest:
        return selftest()

    paths = [SKILL_MD] + sorted(REFS.glob("*.md"))
    findings = run(paths)
    if findings:
        print(f"lint_cache_docs: {len(findings)} violation(s)")
        for f in findings:
            print(f"  {f}")
        return 1
    print(f"lint_cache_docs: clean ({len(RULES)} rules over {len(paths)} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
