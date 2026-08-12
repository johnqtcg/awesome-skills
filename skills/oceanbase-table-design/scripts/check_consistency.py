#!/usr/bin/env python3
"""Cross-file rule-consistency checker (static lint, no database needed).

Why this exists: this skill's knowledge is spread across SKILL.md and a dozen-plus
files under references/. A good share of the defects found across past reviews were
not "the rule is wrong" but **rule drift** -- one place was fixed, another still
carries the old wording. Manual grep cannot catch this reliably, so it is codified
as a checker.

Six categories of check:
  A BNF grounding          every syntax capability claimed by capability-matrix must
                            match the bundled BNF mirror
  B Controlled wording     phrasing that is prone to drifting back to a wrong form
                            may only appear in a negating/corrective context
  C Paired assertions      mentioning X requires also mentioning Y (prevents a
                            half-finished edit)
  D Constant consistency   the default value of a given config item must agree
                            across every file
  E Link integrity         every local link in the body must resolve (code blocks
                            are skipped)
  F Index completeness     every file under references/ scripts/ tests/ must be
                            listed in SKILL.md's index

Usage:
    python3 check_consistency.py [--verbose]
Exit code: 0 = all passed, 1 = there is an error
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MYSQL_BNF = "references/mysql_mode_create_table_syntax.md"
ORACLE_BNF = "references/oracle_mode_create_table_syntax.md"
SKILL = "SKILL.md"

errors, warnings = [], []


def err(msg):
    errors.append(msg)


def warn(msg):
    warnings.append(msg)


def read(rel):
    p = os.path.join(ROOT, rel)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return f.read()


def md_files():
    out = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for fn in sorted(filenames):
            if fn.endswith(".md"):
                out.append(os.path.relpath(os.path.join(dirpath, fn), ROOT))
    return sorted(out)


def strip_fences(text):
    """Replace fenced code blocks with an equal number of blank lines, so line numbers do not shift."""
    lines, out, infence = text.split("\n"), [], False
    for ln in lines:
        if ln.lstrip().startswith("```"):
            infence = not infence
            out.append("")
            continue
        out.append("" if infence else ln)
    return "\n".join(out)


INLINE_SENTINEL = "\x00"


def strip_inline_code(text):
    """Replace inline `code` spans with an equal-length sentinel string.

    A BNF fragment such as `RANGE [COLUMNS](cols)` looks like a markdown link; without
    masking it, the link check would misfire on it. But it **must not be replaced with
    an empty string**: a link in the reference index table is written as
    [`references/x.md`](references/x.md), and blanking the code span turns the label
    into `[]`, which the link regex `\\[[^\\]]+\\]` cannot match -- making the entire
    link invisible to check E. This is exactly what once caused all 22 local links in
    SKILL.md to go undetected, and let a broken reference to agents/openai.yaml go
    unnoticed. An equal-length sentinel masks the content while keeping the label
    non-empty and the original column width.
    """
    return re.sub(r"`[^`\n]*`",
                  lambda m: INLINE_SENTINEL * len(m.group(0)), text)


def fenced_only(text):
    """Keep only the content inside fenced code blocks. Factual assertions about the
    BNF mirror must be checked against the grammar itself, not against the file's
    introductory prose (which may casually mention words like KEY / ORGANIZATION)."""
    keep, infence = [], False
    for ln in text.split("\n"):
        if ln.lstrip().startswith("```"):
            infence = not infence
            continue
        if infence:
            keep.append(ln)
    return "\n".join(keep)


# ------------------------------------------------------------ A. BNF grounding
# Every syntax-capability claim capability-matrix makes must be verifiable against
# the BNF mirror. If the BNF is refreshed for a new version and the capability
# matrix is not updated to match, this fails immediately.
BNF_FACTS = [
    (ORACLE_BNF, "absent", r"COLUMNS",
     "Oracle mode has no COLUMNS keyword (capability-matrix §1.1/§1.2 depends on this fact)"),
    (ORACLE_BNF, "absent", r"PARTITION BY KEY",
     "Oracle mode has no PARTITION BY KEY"),
    (ORACLE_BNF, "absent", r"ORGANIZATION",
     "Oracle mode's table_option has no ORGANIZATION"),
    (ORACLE_BNF, "present", r"PARTITION BY RANGE \(column_name\) INTERVAL",
     "Oracle mode supports INTERVAL"),
    (ORACLE_BNF, "present", r"PARTITION BY HASH\(column_name_list\)",
     "Oracle mode's HASH accepts a column list"),
    (ORACLE_BNF, "present", r"SIZE\('size_value'\)",
     "Oracle mode supports the automatic-partitioning SIZE clause"),
    (ORACLE_BNF, "present", r"DUPLICATE_SCOPE", "Oracle mode supports duplicated tables"),
    (ORACLE_BNF, "present", r"QUEUING", "Oracle mode supports queuing-table mode"),
    (MYSQL_BNF, "absent", r"INTERVAL", "MySQL mode has no INTERVAL partitioning"),
    (MYSQL_BNF, "present", r"PARTITION BY KEY", "MySQL mode has KEY partitioning"),
    (MYSQL_BNF, "present", r"ORGANIZATION \[=\] \{INDEX \| HEAP\}",
     "MySQL mode supports heap tables"),
    (MYSQL_BNF, "present", r"SIZE\('size_value'\)",
     "MySQL mode supports the automatic-partitioning SIZE clause"),
    (MYSQL_BNF, "present", r"DUPLICATE_SCOPE", "MySQL mode supports duplicated tables"),
    (MYSQL_BNF, "present", r"QUEUING", "MySQL mode supports queuing-table mode"),
    (MYSQL_BNF, "present", r"SKIP_INDEX", "MySQL mode supports Skip Index"),
    (MYSQL_BNF, "present", r"DYNAMIC_PARTITION_POLICY",
     "MySQL mode supports the dynamic partitioning policy"),
    (MYSQL_BNF, "present", r"WITH COLUMN GROUP\(each column\)",
     "the pure-columnstore clause form exists"),
    (MYSQL_BNF, "present", r"SEMISTRUCT_ENCODING_TYPE",
     "the option line the deprecation note is attached to (doc-gaps §3 depends on it being present)"),
    (MYSQL_BNF, "absent", r"AUTO_INCREMENT_MODE",
     "the official BNF does not list AUTO_INCREMENT_MODE (the premise for doc-gaps §2)"),
    (MYSQL_BNF, "absent", r"NOCACHE",
     "MySQL mode has no NOCACHE keyword -- the premise for doc-gaps §2.3.1; "
     "if a refreshed BNF introduces it, that section must be rewritten"),
    (MYSQL_BNF, "present", r"auto_increment_cache_size \[=\] INT_VALUE",
     "the MySQL-mode auto-increment cache option takes an integer, which is why NOCACHE cannot substitute for it"),
]

# The token that must never be recommended in a MySQL-mode context. NOCACHE is an
# Oracle CREATE SEQUENCE clause; three files once offered it as the MySQL way to
# suppress auto-increment gaps, which is a syntax error rather than a tuning knob.
#
# Why this is a bespoke check rather than another GUARDED row: the generic rule looks
# for guard words in a +/-3 line window, and a neighbouring line here legitimately
# says "sequences support ORDER + CACHE" -- which would have satisfied a windowed
# guard and let the original defect through. So the binding is deliberately tight:
# only allow-listed shapes pass, and the token itself is masked first so that the "no"
# inside NOCACHE cannot pose as a negation.
#
# The safe shapes are enumerated rather than the unsafe ones. Listing what is wrong is
# unbounded -- some new phrasing always walks through the gap -- whereas the ways a
# line may legitimately mention this token are few and can be written down in full.
NOCACHE_HOME = ("oracle", "sequence")

#: Closed list of non-recommending mentions. Each is a claim ABOUT the token
#: (absent / cross-referenced / the name of this very lint rule) rather than an
#: instruction to write it. `test_nocache_selftest` proves these do not become a
#: bypass by re-feeding the three original defect sentences.
NOCACHE_META = (
    r"no\s+`?NOCACHE`?\s+(?:token|keyword)",   # an absence claim
    r"`NOCACHE`\s+(?:by mode|scoping)",        # a pointer / this rule's own name
    r"§[\d.]+\s+`NOCACHE`",                    # a section cross-reference
)


def nocache_violation(line):
    """True when `line` mentions NOCACHE in a way that reads as a MySQL-mode option.

    Split out from the file walk so the self-test can exercise the decision directly
    instead of round-tripping through the filesystem.
    """
    if "NOCACHE" not in line:
        return False
    if any(re.search(p, line, re.I) for p in NOCACHE_META):
        return False
    # mask the token so its own letters cannot satisfy the requirement
    masked = line.replace("NOCACHE", INLINE_SENTINEL * len("NOCACHE")).lower()
    return not any(h in masked for h in NOCACHE_HOME)


def check_nocache_scoping():
    for rel in md_files():
        if rel in (MYSQL_BNF, ORACLE_BNF):
            continue                     # verbatim mirrors, exempt
        raw = read(rel)
        for i, ln in enumerate(strip_fences(raw).split("\n")):
            if nocache_violation(ln):
                err(f"[G] {rel}:{i+1} NOCACHE must name its real home (Oracle / sequence) "
                    f"on the same line, otherwise it reads as a MySQL-mode option\n      > "
                    f"{ln.strip()[:150]}")


#: The exact sentences that shipped in three files before 2026-08-12. Every one must
#: still be caught, or the exemptions above have quietly become a bypass.
NOCACHE_REGRESSION_CASES = [
    (True, "if the business cannot tolerate skipped numbers, reduce the cache (e.g., 10000), "
           "or use `NOCACHE` (accepting reduced performance)."),
    (True, "or use `NOCACHE` (the official docs state this significantly reduces performance "
           "and is not recommended in production). This option supports table-level configuration."),
    (True, "reduce it or use `NOCACHE` if this cannot be tolerated (at a performance cost)."),
    # near-misses that must also fail: a MySQL context with no mode qualifier at all
    (True, "set `NOCACHE` to stop the gaps entirely."),
    (True, "MySQL mode: add `NOCACHE` to the table options."),
    # legitimate shapes
    (False, "`NOCACHE` is an Oracle `CREATE SEQUENCE` clause and does not exist in MySQL mode."),
    (False, "`NOCACHE` is valid here -- it is a sequence clause, trading throughput for gapless numbering."),
    (False, "`auto_increment_cache_size [=] INT_VALUE`; no `NOCACHE` token"),
    (False, "Cross-file lint: BNF grounding, `NOCACHE` scoping, wording, pairs"),
    (False, "gap corrections (LIST enumeration, `AUTO_INCREMENT_MODE`, §2.3.1 `NOCACHE`)"),
    (False, "corrections (LIST enumeration, `AUTO_INCREMENT_MODE`, `NOCACHE` by mode)"),
]


def nocache_self_test():
    """Grade this rule against the defect it was written for, plus its own exemptions."""
    bad = 0
    for expect_flagged, line in NOCACHE_REGRESSION_CASES:
        got = nocache_violation(line)
        if got != expect_flagged:
            bad += 1
            want = "flagged" if expect_flagged else "allowed"
            print(f"[error] nocache self-test: expected {want}: {line[:90]!r}")
    n = len(NOCACHE_REGRESSION_CASES)
    if bad:
        print(f"nocache self-test: FAILED ({bad}/{n})")
        return 1
    print(f"nocache self-test: {n}/{n} passed "
          f"({sum(1 for f, _ in NOCACHE_REGRESSION_CASES if f)} pre-fix defects still caught)")
    return 0


def check_bnf_grounding():
    for rel, kind, pat, why in BNF_FACTS:
        text = read(rel)
        if text is None:
            err(f"[A] BNF mirror not found: {rel}")
            continue
        found = re.search(pat, fenced_only(text)) is not None
        if kind == "absent" and found:
            err(f"[A] {rel} contains /{pat}/, which conflicts with this fact: {why}")
        if kind == "present" and not found:
            err(f"[A] {rel} is missing /{pat}/, this fact no longer holds: {why}")


# --------------------------------------------------- B. Controlled wording (anti-drift)
# Negation/correction markers. Deliberately broad: English phrases negation in far more
# ways than a single fixed vocabulary, and missing one produces a noisy false [B] error
# rather than a missed drift.
GUARDS = ("✗", "not", "does not exist", "no such", "unsupported", "does not support",
          "forbidden", "Forbidden", "must not", "Must not", "do not", "Do not",
          "cannot", "can't", "wrong", "wrongly", "incorrect", "syntax error",
          "has been removed", "removed", "no longer", "is not", "instead",
          "correct", "corrected", "correction", "conversely", "the other way around",
          "not_applicable", "fail", "no basis", "no hard rule",
          "has no", "does not have", "neither", "rejects", "avoid", "never",
          "should fail", "expect an error", "negative example", "rather than",
          "old semantics", "MySQL-style", "hard rule")
VERSION_TOKENS = ("4.4.2", "BP1", "version fork", "version_branch", "pre_4_4_2", "post_4_4_2")
BRANCH_TOKENS = ("three-branch", "no_pk", "unique key", "conditional rule",
                 "table_key_shape", "not_applicable")
MODE_TOKENS = ("MySQL", "mysql", "Oracle", "oracle", "65536", "compat_mode",
               "depends on the mode", "mode-specific")
TIER_TOKENS = ("C1", "C2", "C3", "candidate_ddl", "confirmation tier", "primary DDL",
               "alternative", "candidate", "must not", "Must not")

GUARDED = [
    # (regex, guard words required nearby to allow the match, explanation)
    (r"(?:Oracle|oracle)[^\n]{0,80}COLUMNS|COLUMNS[^\n]{0,80}(?:Oracle|oracle)",
     GUARDS, "Oracle mode and COLUMNS co-occurring must be a negating context"),
    (r"SHARDING\s*=\s*'?NONE'?[^\n]{0,120}(?:single[- ]node|concentrated on a single node|pushed onto a single node)"
     r"|(?:single[- ]node|concentrated on a single node|pushed onto a single node)[^\n]{0,120}SHARDING\s*=\s*'?NONE'?",
     VERSION_TOKENS, "the single-node risk of SHARDING=NONE must carry a version condition (the V4.4.2 BP1 fork)"),
    (r"partition key[^\n]{0,40}(?:subset of|prefix of|must be)[^\n]{0,20}primary key"
     r"|all partition key[^\n]{0,30}primary key",
     BRANCH_TOKENS,
     "the relationship between the partition key and the primary key must reflect the three-branch conditional rule, not be stated unconditionally"),
    (r"READ_CONSISTENCY", GUARDS, "READ_CONSISTENCY may only appear in a corrective context"),
    (r"page splitting", GUARDS, "page splitting is a B-Tree term and may only appear in a corrective context"),
    (r"TPS\s*>\s*100", GUARDS, "a TPS>100 threshold has no basis and may only appear in a corrective context"),
    (r"30\s*GB", GUARDS, "a 30GB threshold has no official basis and may only appear in a corrective context"),
    (r"partitions\s*[x×]\s*subpartitions\s*[x×]\s*(?:number of tables|table count)",
     GUARDS, "the old Tablet formula may only appear in a corrective context"),
    # 8192 is a MySQL-mode-only ceiling; whenever it appears the mode must be
    # qualified (otherwise a legal Oracle-mode design gets wrongly rejected)
    (r"8192", MODE_TOKENS,
     "the 8192 partition-count ceiling applies to MySQL mode only; when it appears the mode must be qualified or 65536 mentioned"),
    # DYNAMIC_PARTITION_POLICY and INTERVAL co-occurring must explain that the two
    # cannot both go into the primary DDL
    (r"DYNAMIC_PARTITION_POLICY[^\n]{0,80}INTERVAL"
     r"|INTERVAL[^\n]{0,80}DYNAMIC_PARTITION_POLICY",
     TIER_TOKENS,
     "INTERVAL and DYNAMIC_PARTITION_POLICY co-occurring must state the confirmation tier / primary-vs-candidate relationship"),
]


def check_guarded_phrases():
    for rel in md_files():
        raw = read(rel)
        lines = strip_fences(raw).split("\n")
        for pat, guards, why in GUARDED:
            rx = re.compile(pat, re.I)
            for i, ln in enumerate(lines):
                if not rx.search(ln):
                    continue
                # Guard words may appear on this line or the neighboring lines
                # (tables/lists often wrap across lines). English sentences also
                # wrap differently than the Chinese original did, so the window is
                # slightly wider than the source (+/-3 lines instead of +/-2).
                window = "\n".join(lines[max(0, i - 3): i + 4]).lower()
                if not any(g.lower() in window for g in guards):
                    err(f"[B] {rel}:{i+1} {why}\n      > {ln.strip()[:150]}")


# --------------------------------------------------------- C. Paired assertions
PAIRED = [
    (r"auto_split_tablet_size", r"enable_auto_split",
     "mentioning the automatic-partitioning threshold requires also mentioning the tenant switch"),
    (r"(?:columnstore replica|columnstore_replica)[^\n]{0,40}(?:routing|read)"
     r"|routing[^\n]{0,40}(?:columnstore replica|columnstore_replica)",
     r"ODP|OBProxy",
     "discussing **routing** for a columnstore replica requires also mentioning the ODP/OBProxy deployment prerequisite (otherwise it reverts to the Hint myth)"),
    (r"_max_tablet_cnt_per_gb", r"min\(|_storage_meta_memory_limit_percentage",
     "mentioning the Tablet ceiling parameter requires also showing the min(A,B) dual formula"),
    (r"SCOPE\s*=\s*SERVER|SCOPE attribute", r"4\.4\.2",
     "mentioning table-group SCOPE requires also noting >= V4.4.2 BP1"),
    (r"all columns, each column", r"redundan|2×|2x|approximately 2|≈ ?2",
     "mentioning the row-column redundancy clause requires also stating its storage amplification"),
    (r"VALUES IN", r"MySQL|mysql",
     "VALUES IN is MySQL-mode syntax and the mode must be stated"),
    (r"candidate_ddl", r"C1|C2|C3|confirmation tier",
     "mentioning candidate_ddl requires also stating the capability confirmation tier"),
    (r"max_partition_num", r"65536",
     "mentioning max_partition_num requires also giving Oracle's 65536, to avoid it being read as a universal ceiling"),
]


def check_paired_claims():
    for rel in md_files():
        if rel in (MYSQL_BNF, ORACLE_BNF):
            continue                     # the BNF files are a verbatim mirror, exempt from paired assertions
        raw = read(rel)
        body = strip_fences(raw)
        for pat, need, why in PAIRED:
            if re.search(pat, body) and not re.search(need, raw, re.I):
                err(f"[C] {rel}: has /{pat}/ but is missing /{need}/ -- {why}")


# --------------------------------------------------------- D. Constant consistency
CONSTANTS = [
    ("max_partition_num", "8192"),
    ("_max_tablet_cnt_per_gb", "20000"),
    ("_storage_meta_memory_limit_percentage", "20"),
]


def check_constants():
    for rel in md_files():
        raw = read(rel)
        for i, ln in enumerate(raw.split("\n")):
            for name, value in CONSTANTS:
                # Only treat this as a default-value statement when "default" sits
                # within 20 characters of the constant's name.
                near = re.search(
                    re.escape(name) + r"[^\n]{0,20}default|default[^\n]{0,20}" + re.escape(name),
                    ln, re.I)
                if near and value not in ln:
                    err(f"[D] {rel}:{i+1} the default value of {name} should be {value}\n      > "
                        f"{ln.strip()[:150]}")


# --------------------------------------------------------------- E. Link integrity
def check_links():
    for rel in md_files():
        raw = read(rel)
        body = strip_inline_code(strip_fences(raw))   # skip code blocks and inline code,
        # otherwise a BNF fragment like `RANGE [COLUMNS](cols)` would be read as a markdown link
        base = os.path.dirname(os.path.join(ROOT, rel))
        for m in re.finditer(r"\[[^\]]+\]\((?!https?://|#)([^)#]+)", body):
            target = m.group(1).strip()
            if not os.path.exists(os.path.normpath(os.path.join(base, target))):
                err(f"[E] {rel}: link target does not exist -> {target}")


# ----------------------------------------------------------- F. Index completeness
def check_index_completeness():
    skill = read(SKILL)
    if skill is None:
        err(f"[F] {SKILL} not found")
        return
    for sub in ("references", "scripts", "tests"):
        d = os.path.join(ROOT, sub)
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if fn.startswith(".") or fn.endswith(".pyc") or fn == "__pycache__":
                continue
            rel = f"{sub}/{fn}"
            if os.path.isdir(os.path.join(d, fn)):
                if fn == "__pycache__":
                    continue
                if rel not in skill:
                    warn(f"[F] directory {rel} does not appear in {SKILL}'s reference index")
                continue
            if rel not in skill:
                err(f"[F] {rel} is not registered in {SKILL}'s Section 10 reference index")


def main():
    if "--self-test" in sys.argv:
        return nocache_self_test()
    verbose = "--verbose" in sys.argv
    check_bnf_grounding()
    check_nocache_scoping()
    check_guarded_phrases()
    check_paired_claims()
    check_constants()
    check_links()
    check_index_completeness()

    for w in warnings:
        print(f"[warn] {w}")
    for e in errors:
        print(f"[error] {e}")
    if verbose:
        print(f"\nScanned {len(md_files())} md files, "
              f"{len(BNF_FACTS)} BNF facts, {len(GUARDED)} controlled-wording rules, "
              f"{len(PAIRED)} paired assertions, {len(CONSTANTS)} constants")
    if errors:
        print(f"\ncheck_consistency: FAILED ({len(errors)} error, "
              f"{len(warnings)} warn)")
        return 1
    print(f"check_consistency: OK ({len(warnings)} warn)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
