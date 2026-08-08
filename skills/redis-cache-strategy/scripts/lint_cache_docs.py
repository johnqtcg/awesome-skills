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


@rule(
    "RC010",
    "Scorecard tier counts in the verdict line must equal the number of "
    "checkboxes actually listed in each tier.",
    "skill",
    violation="**Verdict**: `X/99`; Critical: `Y/9`; Standard: `Z/9`; Hygiene: `W/9`.",
)
def rc010(text: str):
    tiers = {}
    for name in ("Critical", "Standard", "Hygiene"):
        m = re.search(rf"### {name}[^\n]*\n(.*?)(?=\n### |\n\*\*Verdict|\Z)", text, re.S)
        tiers[name] = len(re.findall(r"^- \[ \]", m.group(1), re.M)) if m else 0
    v = re.search(
        r"\*\*Verdict\*\*: `X/(\d+)`; Critical: `Y/(\d+)`; Standard: `Z/(\d+)`; Hygiene: `W/(\d+)`",
        text,
    )
    if not v:
        yield 0, "verdict line not found or malformed"
        return
    total, crit, std, hyg = (int(x) for x in v.groups())
    for name, declared, actual in (
        ("Critical", crit, tiers["Critical"]),
        ("Standard", std, tiers["Standard"]),
        ("Hygiene", hyg, tiers["Hygiene"]),
    ):
        if declared != actual:
            yield v.start(), f"{name} declared {declared}, {actual} checkboxes present"
    if total != sum(tiers.values()):
        yield v.start(), f"total declared {total}, {sum(tiers.values())} checkboxes present"


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


def run(paths: list[Path]) -> list[str]:
    findings: list[str] = []
    joined = "\n".join(p.read_text(encoding="utf-8") for p in paths)
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

    for r in RULES:
        if r.scope == "global":
            for _, msg in r._fn(joined_masked):
                findings.append(f"<all docs>: {r.id} {msg}")
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
