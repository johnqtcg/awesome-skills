#!/usr/bin/env python3
"""Generate and verify the table of contents in every long reference file.

Why this is a script and not a convention: the TOCs here were hand-written, and a
hand-written TOC is a second list that has to agree with the headings. It did not --
renaming one `##` heading in partitioning.md left its TOC pointing at an anchor that
no longer existed, and nothing noticed. Generating the TOC deletes that whole class of
drift instead of adding a rule asking people to remember.

Usage:
  python3 scripts/gen_toc.py            # check only; non-zero exit if any TOC is stale
  python3 scripts/gen_toc.py --write    # rewrite every TOC block in place
  python3 scripts/gen_toc.py --self-test

A reference file longer than MIN_LINES must have a TOC; shorter files may have one but
are not required to. The two BNF mirrors are included -- they are the longest lookup
files here, which is exactly where navigation matters.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REFS = os.path.join(ROOT, "references")

MIN_LINES = 100
OPEN_MARK = "<!-- toc -->"
CLOSE_MARK = "<!-- /toc -->"
HEADING_LABEL = "**Table of Contents**"
#: only these heading levels go in the TOC; deeper levels make the block longer than
#: the section it indexes
TOC_LEVELS = (2, 3)


def slugify(text, seen):
    """GitHub-flavoured heading anchor.

    Renders inline markdown away, lowercases, drops everything that is not a letter,
    digit, space, hyphen or underscore, then turns spaces into hyphens. Duplicates get
    a numeric suffix, matching GitHub's slugger.
    """
    s = text
    s = re.sub(r"`([^`]*)`", r"\1", s)          # inline code
    s = re.sub(r"\*\*([^*]*)\*\*", r"\1", s)    # bold
    s = re.sub(r"\*([^*]*)\*", r"\1", s)        # italic
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)   # links -> label
    s = s.lower()
    s = re.sub(r"[^\w\s-]", "", s, flags=re.UNICODE)
    s = s.strip().replace(" ", "-")
    base = s
    n = seen.get(base, 0)
    seen[base] = n + 1
    return base if n == 0 else f"{base}-{n}"


def headings(text):
    """(level, title) for every ATX heading outside a fenced code block."""
    out, infence = [], False
    for ln in text.split("\n"):
        if ln.lstrip().startswith("```"):
            infence = not infence
            continue
        if infence:
            continue
        m = re.match(r"^(#{2,6})\s+(.*\S)\s*$", ln)
        if m:
            out.append((len(m.group(1)), m.group(2)))
    return out


def build_toc(text):
    seen = {}
    lines = []
    for level, title in headings(text):
        slug = slugify(title, seen)          # every heading consumes a slug, so that
        if level not in TOC_LEVELS:          # duplicate-suffix numbering stays aligned
            continue                         # with what GitHub actually assigns
        indent = "  " * (level - min(TOC_LEVELS))
        label = title.replace("[", "").replace("]", "")
        lines.append(f"{indent}- [{label}](#{slug})")
    if not lines:
        return None
    return "\n".join([OPEN_MARK, "", HEADING_LABEL, ""] + lines + ["", CLOSE_MARK])


def splice(text, block):
    """Replace an existing TOC block, or insert one after the H1."""
    if OPEN_MARK in text and CLOSE_MARK in text:
        start = text.index(OPEN_MARK)
        end = text.index(CLOSE_MARK) + len(CLOSE_MARK)
        return text[:start] + block + text[end:]
    m = re.search(r"^#\s+.*$", text, re.M)
    if not m:
        return None
    at = m.end()
    return text[:at] + "\n\n" + block + text[at:]


def process(write):
    problems = []
    for fn in sorted(os.listdir(REFS)):
        if not fn.endswith(".md"):
            continue
        path = os.path.join(REFS, fn)
        with open(path, encoding="utf-8") as f:
            text = f.read()
        n_lines = text.count("\n") + 1
        has_toc = OPEN_MARK in text
        if n_lines <= MIN_LINES and not has_toc:
            continue                      # short file, TOC optional
        block = build_toc(text)
        if block is None:
            # The two BNF mirrors are one H1 over a single fenced production block --
            # there is no section structure to index, so a TOC there would be noise.
            # Only complain if such a file somehow already has one.
            if has_toc:
                problems.append(
                    f"references/{fn}: has a TOC block but no level-2 headings to index")
            continue
        want = splice(text, block)
        if want is None:
            problems.append(f"{fn}: no H1 to insert a TOC after")
            continue
        if want == text:
            continue
        if write:
            with open(path, "w", encoding="utf-8") as f:
                f.write(want)
            print(f"  rewrote TOC: references/{fn}")
        else:
            reason = "missing" if not has_toc else "stale"
            problems.append(
                f"references/{fn}: TOC is {reason} "
                f"({n_lines} lines) -- run python3 scripts/gen_toc.py --write")
    return problems


def self_test():
    cases = 0

    def eq(got, want, label):
        nonlocal cases
        cases += 1
        assert got == want, f"{label}: {got!r} != {want!r}"

    seen = {}
    eq(slugify("1. Local Index vs. Global Index", seen),
       "1-local-index-vs-global-index", "basic")
    eq(slugify("2. Partition Key vs. Primary Key/Unique Key", {}),
       "2-partition-key-vs-primary-keyunique-key", "slash dropped")
    eq(slugify("2.1 Criteria (official, **tiered**)", {}),
       "21-criteria-official-tiered", "dot, parens, comma, bold dropped")
    eq(slugify("§4 `AUTO_INCREMENT` family", {}),
       "4-auto_increment-family", "section sign dropped, underscore kept")
    eq(slugify("3. Automatic split — not a type", {}),
       "3-automatic-split--not-a-type", "em dash leaves the two spaces as hyphens")

    dup = {}
    eq(slugify("Notes", dup), "notes", "first duplicate")
    eq(slugify("Notes", dup), "notes-1", "second duplicate")

    # headings must ignore fenced content
    md = "# T\n\n## Real\n\n```\n## Fake\n```\n\n## Also Real\n"
    eq([t for _, t in headings(md)], ["Real", "Also Real"], "fence exclusion")

    # a level-4 heading is skipped but still consumes its slug, so a later duplicate
    # of it gets the suffix GitHub would give it
    md2 = "# T\n\n## Dup\n\n#### Dup\n\n## Dup\n"
    toc = build_toc(md2)
    eq("#dup" in toc and "#dup-2" in toc, True, "skipped heading still consumes a slug")

    # round trip: splicing an existing block replaces rather than duplicates it
    doc = "# T\n\n" + build_toc("# T\n\n## A\n") + "\n\n## A\n"
    once = splice(doc, build_toc(doc))
    eq(once.count(OPEN_MARK), 1, "no duplicate TOC block")

    print(f"gen_toc self-test: {cases}/{cases} passed")
    return 0


def main():
    if "--self-test" in sys.argv:
        return self_test()
    write = "--write" in sys.argv
    problems = process(write)
    if problems:
        for p in problems:
            print(f"[error] {p}")
        print(f"\ngen_toc: FAILED ({len(problems)} file(s))")
        return 1
    print("gen_toc: OK (every reference over "
          f"{MIN_LINES} lines has an up-to-date TOC)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
