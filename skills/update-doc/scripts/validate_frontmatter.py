#!/usr/bin/env python3
"""Validate a skill's SKILL.md frontmatter against the real Claude Code schema.

Why this exists rather than reusing `skill-creator/scripts/quick_validate.py`:
that validator's allowlist is `{name, description, license, allowed-tools,
metadata}` — five fields. The documented Claude Code frontmatter reference table
has seventeen. Any skill using a legitimate field outside those five fails it.

The tempting workaround is to strip the offending field and validate a copy. That
validates a file nobody ships. This validator reads the real file instead.

Field allowlist provenance: the "Frontmatter reference" table at
https://docs.anthropic.com/en/docs/claude-code/skills.md (read 2026-07-31), plus
`license` and `metadata` from the Agent Skills packaging spec, which
quick_validate accepts and this repository uses.

Every constraint quick_validate enforces is reproduced here; see
`test_skill_contract.py::TestValidatorIsNotWeaker`, which proves that against
synthetic bad input rather than asserting it in prose.

Usage: validate_frontmatter.py <skill_directory>
Exit:  0 valid, 1 invalid, 2 usage error
"""

import re
import sys
from pathlib import Path

MAX_NAME_LENGTH = 64
MAX_DESCRIPTION_LENGTH = 1024

# Documented Claude Code frontmatter fields.
CLAUDE_CODE_FIELDS = {
    "name",
    "description",
    "when_to_use",
    "argument-hint",
    "arguments",
    "disable-model-invocation",
    "user-invocable",
    "allowed-tools",
    "disallowed-tools",
    "model",
    "effort",
    "context",
    "agent",
    "background",
    "hooks",
    "paths",
    "shell",
}
# Agent Skills packaging fields.
PACKAGING_FIELDS = {"license", "metadata"}

ALLOWED_FIELDS = CLAUDE_CODE_FIELDS | PACKAGING_FIELDS

BOOLEAN_FIELDS = {"disable-model-invocation", "user-invocable", "background"}

# Claude Code v2.1.218 accepts `yes`/`no`/`on`/`off`/`1`/`0` (case-insensitive)
# for frontmatter booleans alongside `true`/`false`. PyYAML resolves all of those
# to `bool` already EXCEPT `1` and `0`, which arrive as `int` — so an
# `isinstance(value, bool)` check alone would reject frontmatter Claude Code
# accepts. Only 0 and 1 qualify; `2` is not a boolean in any spelling.
BOOLEAN_INT_VALUES = {0, 1}


STRING_OR_LIST_FIELDS = {"allowed-tools", "disallowed-tools"}


def is_frontmatter_boolean(value):
    if isinstance(value, bool):
        return True
    return isinstance(value, int) and value in BOOLEAN_INT_VALUES


def validate(skill_path):
    """Return (ok, [messages]). Validates the file as shipped — no rewriting."""
    try:
        import yaml
    except ImportError:
        return False, ["pyyaml is required (declared in requirements.txt)"]

    skill_md = Path(skill_path) / "SKILL.md"
    if not skill_md.exists():
        return False, [f"SKILL.md not found under {skill_path}"]

    content = skill_md.read_text(encoding="utf-8")
    if not content.startswith("---"):
        return False, ["no YAML frontmatter found"]

    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return False, ["invalid frontmatter format"]

    try:
        data = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        return False, [f"invalid YAML in frontmatter: {exc}"]

    if not isinstance(data, dict):
        return False, ["frontmatter must be a YAML mapping"]

    errors = []

    unexpected = sorted(set(data) - ALLOWED_FIELDS)
    if unexpected:
        errors.append(
            f"unexpected key(s): {', '.join(unexpected)}. "
            f"Allowed: {', '.join(sorted(ALLOWED_FIELDS))}"
        )

    if "name" not in data:
        errors.append("missing required key: name")
    if "description" not in data:
        errors.append("missing required key: description")

    name = data.get("name")
    if name is not None:
        if not isinstance(name, str):
            errors.append(f"name must be a string, got {type(name).__name__}")
        else:
            stripped = name.strip()
            if stripped:
                if not re.match(r"^[a-z0-9-]+$", stripped):
                    errors.append(
                        f"name '{stripped}' must be hyphen-case "
                        "(lowercase letters, digits, hyphens)"
                    )
                if (
                    stripped.startswith("-")
                    or stripped.endswith("-")
                    or "--" in stripped
                ):
                    errors.append(
                        f"name '{stripped}' cannot start/end with a hyphen "
                        "or contain consecutive hyphens"
                    )
                if len(stripped) > MAX_NAME_LENGTH:
                    errors.append(
                        f"name is too long ({len(stripped)}); "
                        f"maximum is {MAX_NAME_LENGTH}"
                    )

    description = data.get("description")
    if description is not None:
        if not isinstance(description, str):
            errors.append(
                f"description must be a string, got {type(description).__name__}"
            )
        else:
            stripped = description.strip()
            if "<" in stripped or ">" in stripped:
                errors.append("description cannot contain angle brackets (< or >)")
            if len(stripped) > MAX_DESCRIPTION_LENGTH:
                errors.append(
                    f"description is too long ({len(stripped)}); "
                    f"maximum is {MAX_DESCRIPTION_LENGTH}"
                )

    for key in BOOLEAN_FIELDS & set(data):
        if not is_frontmatter_boolean(data[key]):
            errors.append(
                f"{key} must be a boolean "
                "(true/false/yes/no/on/off/1/0), got "
                f"{type(data[key]).__name__} {data[key]!r}"
            )

    for key in STRING_OR_LIST_FIELDS & set(data):
        value = data[key]
        if not isinstance(value, (str, list)):
            errors.append(
                f"{key} must be a string or list, got {type(value).__name__}"
            )
        elif isinstance(value, list) and not all(isinstance(v, str) for v in value):
            errors.append(f"{key} list entries must all be strings")

    return (not errors), errors


def main(argv):
    if len(argv) != 2:
        print("Usage: validate_frontmatter.py <skill_directory>", file=sys.stderr)
        return 2
    ok, messages = validate(argv[1])
    if ok:
        print(f"Frontmatter is valid: {argv[1]}/SKILL.md")
        return 0
    for message in messages:
        print(f"error: {message}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
