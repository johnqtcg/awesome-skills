#!/usr/bin/env python3
"""Load every GOOD TypeScript example this skill ships in real Playwright.

Why this exists: until 2026-10-09 no shipped example had ever been executed, and
SKILL.md's anti-example 3 taught as GOOD a file-scope `test.info()` call that throws
during collection — the file runs zero tests. The linter passed it. Reading code
cannot settle what a runtime does at load time; loading it can.

What it checks: each GOOD example is written out as a spec file and collected with
`playwright test --list`, which executes module-level code and every
`test.describe` callback but no test body. A pass means "this example loads", not
"this example type-checks" (Playwright transpiles without a type check) and not
"this example passes" (no browser, no target app).

How fragments are made loadable, stated so a pass is not over-read:
  - a statement fragment (no import, no top-level test/describe/hook/fixture) is
    wrapped in a `test(...)` body, because that is where the prose places it;
  - a config-property fragment (`use: {...}`, `projects: [...]`) is wrapped in
    `export default defineConfig({...})`;
  - `test`, `expect`, `defineConfig`, `devices` and `base` are imported from
    `@playwright/test` when the block uses them without declaring them. Docs elide
    that import; restoring it is the only edit made to a block's own text;
  - a block importing or resolving a relative module (`from './fixtures'`,
    `require.resolve('./global-setup')`) is SKIPPED and listed — it depends on a
    sibling example file this script does not reconstruct.

Opt-in: needs node, npm, and network access to the npm registry. It is not part of
the default regression run.

Usage:
    python3 scripts/verify_examples_load.py            # PW_VERSION=1.62.0 by default
    PW_VERSION=1.63.0 python3 scripts/verify_examples_load.py

Exit codes:
    0  every non-skipped example loads (skips are listed, not hidden)
    1  at least one example fails to load
    2  could not run (no npm, install failed) — NOT a verdict
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_PW_VERSION = "1.62.0"

FENCE_RE = re.compile(r"^```([A-Za-z0-9_+-]*)\s*$")
TS_LANGS = {"ts", "typescript"}
# GOOD/BAD is read from LABELS, never from prose. The docs label a block with a line
# of its own just above the fence (`BAD:`, `GOOD:`, `BEST — …`) and a segment inside a
# block with a leading comment (`// WRONG — …`, `// CORRECT — …`, `// BEFORE (flaky)`
# then `// AFTER (stable)`). Labels are
# uppercase; matching case-sensitively keeps "what goes wrong" in an explanation from
# reading as a label. An unlabelled block is a recommendation.
_LABEL_WORDS = r"(BAD|WRONG|AVOID|BEFORE|GOOD|BEST|CORRECT|ACCEPTABLE|AFTER)\b"
_PROSE_LABEL_RE = re.compile(r"^(?:\*\*)?" + _LABEL_WORDS)
_COMMENT_LABEL_RE = re.compile(r"^\s*//\s*" + _LABEL_WORDS)
_BAD_LABELS = {"BAD", "WRONG", "AVOID", "BEFORE"}

# Top-level shapes that make a block a module rather than a test-body fragment.
# `test.skip` / `test.fixme` are deliberately absent: both are legal at file scope
# AND inside a test body, so they say nothing about which one the block is.
_MODULE_RE = re.compile(
    r"^(?:import\s|export\s|test\s*\(|test\.(?:describe|use|beforeEach|beforeAll|"
    r"afterEach|afterAll|extend)\b|(?:const|let)\s+\w+\s*=\s*(?:base|test)\.extend\b)",
    re.M,
)
_CONFIG_PROPERTY_RE = re.compile(r"^[A-Za-z_]\w*\s*:\s*[\[{]")
_RELATIVE_IMPORT_RE = re.compile(r"""(?:from\s+|require(?:\.resolve)?\(\s*)['"]\.{1,2}/""")
_BARE_IMPORT_RE = re.compile(r"""from\s+['"]([^'".][^'"]*)['"]""")
PRELUDE_NAMES = ("test", "expect", "defineConfig", "devices")


@dataclass
class Example:
    source: str  # file name relative to the skill directory
    line: int  # 1-based line where the example starts in its source file
    body: str


def code_blocks(markdown: str) -> list[tuple[int, str, str]]:
    """Yield (start_line, lang, body) for every fenced block.

    Line-oriented, following the CommonMark closing rule: a fence line carrying an
    info string (```` ```ts ````) is *content* inside an open block, never a closer.
    Only a bare fence closes. A non-greedy regex gets this wrong whenever a document
    shows a fence inside a fence.
    """
    out: list[tuple[int, str, str]] = []
    lines = markdown.split("\n")
    i = 0
    while i < len(lines):
        m = FENCE_RE.match(lines[i])
        if not m:
            i += 1
            continue
        lang = m.group(1).lower()
        start = i
        i += 1
        body: list[str] = []
        while i < len(lines):
            close = FENCE_RE.match(lines[i])
            if close and not close.group(1):
                break
            body.append(lines[i])
            i += 1
        i += 1  # consume the closing fence
        out.append((start + 1, lang, "\n".join(body)))
    return out


def _segments(body: str, block_is_bad: bool, first_line: int) -> list[tuple[int, str, bool]]:
    """Split a block at its label comments into (line, text, is_bad) segments.

    One fence holding `// WRONG` then `// CORRECT` is two examples. Classifying the
    fence as a unit either exempts the CORRECT half (if any marker counts) or grades
    the WRONG half (if none does) — both are wrong.
    """
    segments, current, start, bad = [], [], first_line, block_is_bad
    for offset, ln in enumerate(body.split("\n")):
        m = _COMMENT_LABEL_RE.match(ln)
        if m:
            if any(c.strip() for c in current):
                segments.append((start, "\n".join(current), bad))
            current, start, bad = [], first_line + offset, m.group(1) in _BAD_LABELS
        current.append(ln)
    if any(c.strip() for c in current):
        segments.append((start, "\n".join(current), bad))
    return segments


def good_examples(skill_dir: Path = SKILL_DIR) -> list[Example]:
    """Every GOOD TypeScript example in SKILL.md and references/.

    The single source of the GOOD/BAD split: the contract test that runs the linter
    over the examples uses this function too, so both layers grade the same set.
    Selection used to search the 200 characters before a fence for a BAD marker, which
    also caught the GOOD block that follows every BAD block — so SKILL.md's seven
    GOOD anti-example fixes were never linted, and the one that crashed at load
    went unnoticed.
    """
    out: list[Example] = []
    paths = [skill_dir / "SKILL.md"] + sorted((skill_dir / "references").glob("*.md"))
    for path in paths:
        lines = path.read_text(encoding="utf-8").split("\n")
        prev_end = 0
        for line, lang, body in code_blocks("\n".join(lines)):
            gap = [ln.strip() for ln in lines[prev_end : line - 1] if ln.strip()]
            prev_end = line + body.count("\n") + 2
            if lang not in TS_LANGS:
                continue
            label = _PROSE_LABEL_RE.match(gap[-1]) if gap else None
            block_is_bad = bool(label) and label.group(1) in _BAD_LABELS
            for seg_line, text, is_bad in _segments(body, block_is_bad, line + 1):
                if not is_bad:
                    out.append(Example(str(path.relative_to(skill_dir)), seg_line, text))
    return out


def classify(body: str) -> str:
    """'module', 'fragment', 'config', or 'skip: <reason>'."""
    if _RELATIVE_IMPORT_RE.search(body):
        return "skip: depends on a sibling example file (relative import or require)"
    first = next(
        (ln.strip() for ln in body.split("\n") if ln.strip() and not ln.strip().startswith("//")),
        "",
    )
    if _CONFIG_PROPERTY_RE.match(first):
        return "config"
    if _MODULE_RE.search(body):
        return "module"
    return "fragment"


def _declared_names(src: str) -> set[str]:
    names = set(re.findall(r"\b(?:const|let|var|function|class)\s+([A-Za-z_$][\w$]*)", src))
    for group in re.findall(r"import\s*\{([^}]*)\}", src):
        for spec in group.split(","):
            spec = spec.strip()
            if spec:
                names.add(spec.split(" as ")[-1].strip())
    names.update(re.findall(r"import\s+([A-Za-z_$][\w$]*)\s+from", src))
    return names


def build_spec(body: str, kind: str) -> str:
    """The loadable spec text for a block of the given kind (see module docstring)."""
    if kind == "fragment":
        src = (
            'test("example", async ({ page, request, context, browser, baseURL }) => {\n'
            f"{body}\n}});\n"
        )
    elif kind == "config":
        src = f"export default defineConfig({{\n{body}\n}});\n"
    else:
        src = body + "\n"
    declared = _declared_names(src)
    needed = [n for n in PRELUDE_NAMES if n not in declared and re.search(rf"\b{n}\b", src)]
    if "base" not in declared and re.search(r"\bbase\.extend\b", src):
        needed.append("test as base")
    if needed:
        src = f'import {{ {", ".join(needed)} }} from "@playwright/test";\n' + src
    return src


def third_party_packages(examples: list[Example]) -> list[str]:
    """npm packages imported by the examples, other than Playwright itself."""
    pkgs = set()
    for ex in examples:
        for spec in _BARE_IMPORT_RE.findall(ex.body):
            if spec.startswith("node:") or spec.startswith("@playwright/test"):
                continue
            parts = spec.split("/")
            pkgs.add("/".join(parts[:2]) if spec.startswith("@") else parts[0])
    return sorted(pkgs)


def load_error(output: str) -> str | None:
    """First collection error in `playwright test --list` output, or None.

    "No tests found" alone is not a load error: a fixtures module or a file holding
    only `test.use(...)` legitimately declares no tests. It also follows every real
    load error, which is why a real error is searched for first.
    """
    for ln in output.split("\n"):
        s = ln.strip()
        if re.match(r"^(?:\w*Error|Error):", s) and "No tests found" not in s:
            return s
    return None


def main() -> int:
    version = os.environ.get("PW_VERSION", DEFAULT_PW_VERSION)
    if not shutil.which("npm"):
        print("verify_examples_load: npm not available — cannot verify", file=sys.stderr)
        return 2

    examples = good_examples()
    work = Path(tempfile.mkdtemp(prefix="e2e-examples-"))
    try:
        packages = [f"@playwright/test@{version}"] + third_party_packages(examples)
        print(f"=== installing {' '.join(packages)} (browsers not needed) ===")
        (work / "package.json").write_text('{"name":"e2e-examples","private":true}\n')
        install = subprocess.run(
            ["npm", "install", "--no-audit", "--no-fund", "--loglevel=error",
             "--cache", str(work / ".npmcache"), *packages],
            cwd=work, capture_output=True, text=True,
        )
        if install.returncode != 0:
            print("verify_examples_load: npm install failed — cannot verify", file=sys.stderr)
            print(install.stderr[-2000:], file=sys.stderr)
            return 2
        (work / "playwright.config.ts").write_text(
            'import { defineConfig } from "@playwright/test";\n'
            'export default defineConfig({ testDir: "examples" });\n'
        )
        cli = work / "node_modules" / ".bin" / "playwright"
        spec_dir = work / "examples"
        spec_dir.mkdir()

        loaded, failed, skipped = [], [], []
        for n, ex in enumerate(examples, 1):
            where = f"{ex.source}:{ex.line}"
            kind = classify(ex.body)
            if kind.startswith("skip"):
                skipped.append(f"{where} — {kind[len('skip: '):]}")
                continue
            name = f"{n:03d}-{Path(ex.source).stem}-L{ex.line}.spec.ts"
            (spec_dir / name).write_text(build_spec(ex.body, kind))
            run = subprocess.run(
                [str(cli), "test", "--list", f"examples/{name}"],
                cwd=work, capture_output=True, text=True,
            )
            err = load_error(run.stdout + run.stderr)
            if err:
                failed.append(f"{where} ({kind}) — {err}")
            else:
                loaded.append(where)

        print(f"\nPlaywright {version}: {len(examples)} GOOD examples — "
              f"{len(loaded)} load, {len(failed)} FAIL, {len(skipped)} skipped")
        for line in failed:
            print(f"  FAIL  {line}")
        for line in skipped:
            print(f"  SKIP  {line}")
        return 1 if failed else 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
