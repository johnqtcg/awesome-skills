#!/usr/bin/env python3
"""Generate and verify the table of contents in every long reference file.

Hand-written TOCs are a second list that has to agree with the headings, and the second list
is the one that goes stale (see COVERAGE.md §3 on prose counts). Generating them removes the
drift class instead of adding a rule asking people to remember.

  python3 scripts/gen_toc.py            # check; non-zero exit if any TOC is missing or stale
  python3 scripts/gen_toc.py --write    # rewrite every TOC block in place
  python3 scripts/gen_toc.py --self-test
"""
import os
import re
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
REFS = SKILL_DIR / "references"
MIN_LINES = 100
OPEN_MARK, CLOSE_MARK = "<!-- toc -->", "<!-- /toc -->"
LABEL = "**Table of Contents**"
TOC_LEVELS = (2, 3)


def slugify(text, seen):
    """GitHub-flavoured heading anchor."""
    s = re.sub(r"`([^`]*)`", r"\1", text)
    s = re.sub(r"\*\*([^*]*)\*\*", r"\1", s)
    s = re.sub(r"\*([^*]*)\*", r"\1", s)
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"[^\w\s-]", "", s.lower(), flags=re.UNICODE).strip().replace(" ", "-")
    n = seen.get(s, 0)
    seen[s] = n + 1
    return s if n == 0 else f"{s}-{n}"


def headings(text):
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
    seen, lines = {}, []
    for level, title in headings(text):
        slug = slugify(title, seen)          # every heading consumes a slug so duplicate
        if level not in TOC_LEVELS:          # numbering matches what GitHub assigns
            continue
        indent = "  " * (level - min(TOC_LEVELS))
        lines.append(f"{indent}- [{title.replace('[', '').replace(']', '')}](#{slug})")
    if not lines:
        return None
    return "\n".join([OPEN_MARK, "", LABEL, ""] + lines + ["", CLOSE_MARK])


def splice(text, block):
    if OPEN_MARK in text and CLOSE_MARK in text:
        return text[:text.index(OPEN_MARK)] + block + \
            text[text.index(CLOSE_MARK) + len(CLOSE_MARK):]
    m = re.search(r"^#\s+.*$", text, re.M)
    return None if not m else text[:m.end()] + "\n\n" + block + text[m.end():]


def process(write):
    problems = []
    for path in sorted(REFS.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        n = text.count("\n") + 1
        has = OPEN_MARK in text
        if n <= MIN_LINES and not has:
            continue
        block = build_toc(text)
        if block is None:
            if has:
                problems.append(f"references/{path.name}: TOC block but no level-2 headings")
            continue
        want = splice(text, block)
        if want is None:
            problems.append(f"references/{path.name}: no H1 to insert a TOC after")
        elif want != text:
            if write:
                path.write_text(want, encoding="utf-8")
                print(f"  rewrote TOC: references/{path.name}")
            else:
                problems.append(
                    f"references/{path.name}: TOC is {'missing' if not has else 'stale'} "
                    f"({n} lines) -- run python3 scripts/gen_toc.py --write")
    return problems


def self_test():
    cases = 0

    def eq(got, want, label):
        nonlocal cases
        cases += 1
        assert got == want, f"{label}: {got!r} != {want!r}"

    eq(slugify("1. Route Tree Design", {}), "1-route-tree-design", "basic")
    eq(slugify("0.1 Is this page-worthy?", {}), "01-is-this-page-worthy", "punctuation")
    eq(slugify("Does this alert need a `for` duration?", {}),
       "does-this-alert-need-a-for-duration", "inline code")
    eq(slugify("§4 **bold** and — dash", {}), "4-bold-and--dash", "em dash keeps two hyphens")
    dup = {}
    eq(slugify("Notes", dup), "notes", "dup 1")
    eq(slugify("Notes", dup), "notes-1", "dup 2")
    md = "# T\n\n## Real\n\n```\n## Fake\n```\n\n## Also\n"
    eq([t for _, t in headings(md)], ["Real", "Also"], "fence exclusion")
    # a skipped level-4 heading still consumes its slug
    toc = build_toc("# T\n\n## Dup\n\n#### Dup\n\n## Dup\n")
    eq("#dup" in toc and "#dup-2" in toc, True, "slug numbering")
    doc = "# T\n\n" + build_toc("# T\n\n## A\n") + "\n\n## A\n"
    eq(splice(doc, build_toc(doc)).count(OPEN_MARK), 1, "no duplicate block")
    print(f"gen_toc self-test: {cases}/{cases} passed")
    return 0


def main():
    if "--self-test" in sys.argv:
        return self_test()
    problems = process("--write" in sys.argv)
    for p in problems:
        print(f"[error] {p}")
    if problems:
        print(f"\ngen_toc: FAILED ({len(problems)} file(s))")
        return 1
    print(f"gen_toc: OK (every reference over {MIN_LINES} lines has an up-to-date TOC)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
