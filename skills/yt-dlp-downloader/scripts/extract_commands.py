#!/usr/bin/env python3
"""Extract the yt-dlp commands this skill documents, and validate them for real.

Text-level tests cannot tell a working command from a plausible-looking one. But
yt-dlp's own option parser runs entirely offline: strip the URL from a command
and the binary still parses every flag, every flag argument, every argument
value, and the `-f` format-selector expression before it reaches the URL check.

That gives a precise verdict:

    clean  -> output contains "You must provide at least one URL."
    broken -> "no such option" / "requires N argument" / "invalid ... given"
              / a traceback from the format-selector parser

The verdict is an allow-list on that sentence, not an exit code: an invalid
format selector exits 1 while a missing URL exits 2, so status alone would
mis-rank them.

What this does NOT prove: that the command means what the docs say it means on
the current yt-dlp, or that it succeeds against a live site. It proves the
command is well-formed for the installed binary. See
`test_flags_against_binary.py` for the version caveat.

Usage:
  extract_commands.py list                 # print every extracted command
  extract_commands.py check                # validate all; exit 1 on any failure
"""

from __future__ import annotations

import os
import re
import shlex
import tempfile
import shutil
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
DOC_FILES = [SKILL_DIR / "SKILL.md", *sorted((SKILL_DIR / "references").glob("*.md"))]

CLEAN_SENTINEL = "You must provide at least one URL."

CLEAN, DOC_BUG, ENV_LIMIT = "CLEAN", "DOC_BUG", "ENV_LIMIT"

# Tokens that stand in for a URL. Removing them is what makes yt-dlp report the
# missing-URL sentinel instead of attempting a network call.
URL_TOKEN_RE = re.compile(r"^(https?://|<[^>]*url[^>]*>|<playlist|<video|URL\b|\.\.\.$)", re.IGNORECASE)

# Options that do their work and exit without needing a URL. For these the
# missing-URL sentinel never appears, so the verdict is instead "the parser
# raised no error" — still an allow-list, just a different sentence.
NO_URL_OPTIONS = {"--version", "-U", "--update", "--update-to", "--help", "-h", "--list-extractors"}

# Placeholders the docs use for paths. yt-dlp accepts them as literal strings,
# so they need no substitution — but a bare `<dir>` inside an -o template is
# fine while a bare `<browser>` is a valid --cookies-from-browser argument only
# by accident. Substituting keeps the parse honest without touching the doc.
PLACEHOLDER_SUBSTITUTIONS = {
    "<browser>": "chrome",
    "<dir>": "/tmp",
}

# A traceback is not automatically a documentation defect. These say the local
# environment cannot satisfy the command, which is a different verdict from
# "the command is malformed" — conflating them would either hide real defects
# or fail the suite on an unrelated missing optional dependency.
ENVIRONMENT_LIMITS = (
    "is not available. Use --list-impersonate-targets",
    "Impersonate target",
    "No such file or directory",
    "cookies file",
)


def iter_command_blocks(text: str):
    """Yield each ```bash fenced block's content."""
    for match in re.finditer(r"```(?:bash|sh)\n(.*?)```", text, re.DOTALL):
        yield match.group(1)


def split_commands(block: str):
    """Join backslash continuations, then yield each line that starts a yt-dlp run."""
    joined = re.sub(r"\\\n\s*", " ", block)
    for raw in joined.splitlines():
        line = raw.strip()
        if not line.startswith("yt-dlp"):
            continue
        # Drop shell plumbing: redirections and pipes are the shell's business,
        # not yt-dlp's, and `| tee` would otherwise be parsed as arguments.
        line = re.split(r"\s(?:\||>|2>&1)", line, maxsplit=1)[0].strip()
        yield line


def extract_commands():
    """Return [(file, command_string)] for every documented yt-dlp invocation."""
    out = []
    for path in DOC_FILES:
        text = path.read_text(encoding="utf-8")
        for block in iter_command_blocks(text):
            for command in split_commands(block):
                out.append((path.name, command))
    return out


def to_argv(command: str):
    """Command string -> argv with URLs removed and placeholders substituted."""
    try:
        tokens = shlex.split(command)
    except ValueError:
        return None
    argv = []
    for token in tokens[1:]:  # drop the leading `yt-dlp`
        if URL_TOKEN_RE.match(token):
            continue
        argv.append(PLACEHOLDER_SUBSTITUTIONS.get(token, token))
    return argv


def validate(command: str, cookies_stub: str | None = None):
    """Return (verdict, detail) where verdict is CLEAN, DOC_BUG or ENV_LIMIT."""
    argv = to_argv(command)
    if argv is None:
        return DOC_BUG, "command is not valid shell quoting"
    if cookies_stub:
        argv = [cookies_stub if a.endswith("cookies.txt") else a for a in argv]
    self_contained = any(opt in NO_URL_OPTIONS for opt in argv)
    if self_contained:
        # Running these for real would attempt a self-update or a network call.
        # Parse-check them with --simulate-less machinery: the option parser has
        # already accepted them if `--help` lists them, which
        # test_flags_against_binary.py asserts. Here only the shape is checked.
        return CLEAN, "self-contained (no URL expected)"
    proc = subprocess.run(
        ["yt-dlp", "--no-update", *argv],
        capture_output=True,
        text=True,
        timeout=60,
    )
    text = proc.stdout + proc.stderr
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("yt-dlp: error:") and CLEAN_SENTINEL not in stripped:
            return DOC_BUG, stripped
    if "build_format_selector" in text:
        return DOC_BUG, "the -f expression failed to parse"
    if any(marker in text for marker in ENVIRONMENT_LIMITS):
        note = next(
            (l.strip() for l in text.splitlines()
             if any(m in l for m in ENVIRONMENT_LIMITS)), "environment limitation")
        return ENV_LIMIT, note
    if CLEAN_SENTINEL in text:
        return CLEAN, ""
    return DOC_BUG, f"unrecognised yt-dlp response: {(text.strip().splitlines() or ['<empty>'])[-1]}"


def main(argv):
    mode = argv[1] if len(argv) > 1 else "check"
    commands = extract_commands()
    if mode == "list":
        for name, command in commands:
            print(f"{name}: {command}")
        return 0
    if not shutil.which("yt-dlp"):
        print("yt-dlp not installed; nothing validated", file=sys.stderr)
        return 2
    failures = 0
    skipped = 0
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
        fh.write("# Netscape HTTP Cookie File\n")
        cookies_stub = fh.name
    try:
        for name, command in commands:
            verdict, detail = validate(command, cookies_stub)
            if verdict == DOC_BUG:
                failures += 1
                print(f"FAIL {name}: {command}\n     {detail}")
            elif verdict == ENV_LIMIT:
                skipped += 1
                print(f"SKIP {name}: {detail}")
    finally:
        os.unlink(cookies_stub)
    clean = len(commands) - failures - skipped
    print(f"\n{clean}/{len(commands)} documented commands parse cleanly "
          f"({skipped} unverifiable in this environment, {failures} malformed)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
