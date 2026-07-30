#!/usr/bin/env python3
"""Mechanical layer of the tech-doc-writer Quality Scorecard (Gate 3).

Deterministically checks the regex-decidable subset of the scorecard so the
judgment-based items are the only thing left to the model. Stdlib only.

Checks (severity in brackets):
  metadata        [critical]  metadata block carries every required field
  status-value    [critical]  status is one of the configured vocabulary
  date-format     [critical]  the date field is a real YYYY-MM-DD calendar date
  fence-balance   [critical]  every opening code fence is closed
  table-cells     [critical for --type reference, warning otherwise]
                              no TBD/TODO/empty cells inside markdown tables
  table-columns   [critical for --type reference]
                              a parameter/field table declares Type, Required, Default
                              and Description columns (synonyms and CJK accepted)
  single-h1       [warning]   exactly one H1 title
  title-weight    [warning]   H1 title within the language-aware budget, and free of
                              filler words (see TITLE_BUDGET / FILLER_RE)
  title-h1-match  [warning]   metadata `title` and the H1 name the same document
  code-fence-lang [warning]   fenced code blocks carry a language tag
  pangu-spacing   [warning]   exactly one space between CJK and Latin/digit runs
                              (inline code, fenced blocks, URLs, table rows exempt)
  applicable-versions [warning]  present when the doc names version-sensitive content
  staleness       [warning]   the date field is neither in the future nor older than the
                              review cadence allows — the check that makes the
                              anti-staleness rules load-bearing rather than decorative
  maintenance     [warning]   task/troubleshooting docs state when they must be updated

Repository conventions win over this skill's defaults (SKILL.md Gate 1), so every
hard-coded expectation above is overridable from a `.techdocrc.json` discovered by
walking up from the linted file, or passed with `--config`. `--print-config` dumps the
schema and the effective merge.

Usage:
  lint_doc.py <file.md> [--type concept|task|reference|troubleshooting|design]
              [--strict] [--scorecard] [--config PATH] [--today YYYY-MM-DD]
              [--print-config]

`--scorecard` prints the applicable/N-A item counts and the ⅔ thresholds for the given
--type, so the scorecard denominator is computed rather than guessed.

`--today` pins the reference date for the staleness check. Without it the system date is
used, which would make any test asserting "no findings" rot into a failure on its own.

Exit codes: 0 = no critical findings (warnings allowed unless --strict),
            1 = critical findings (or any finding with --strict),
            2 = file unreadable, 3 = bad config or bad --today.
"""

from __future__ import annotations

import argparse
import copy
import datetime
import json
import math
import re
import sys
from pathlib import Path

CRITICAL = "critical"
WARNING = "warning"

CONFIG_FILENAME = ".techdocrc.json"

# Defaults reproduce the behaviour documented in SKILL.md. A repository that documents a
# different convention overrides the relevant subtree in `.techdocrc.json` instead of being
# told its own standard is a lint error — Gate 1 says the repo's convention wins, and before
# this existed the linter could not honour that.
DEFAULT_CONFIG: dict = {
    "metadata": {
        # frontmatter -> leading `---` block; footer -> trailing `---` block (page metadata at
        # the end); none -> the repo forbids an in-document block, so the field checks and the
        # staleness check are both skipped, and the skip is printed rather than implied.
        "location": "frontmatter",
        "required": ["title", "owner", "status", "last_updated"],
        "status_field": "status",
        "status_values": ["draft", "active", "needs-update", "deprecated"],
        "date_field": "last_updated",
        # Repo uses `maintainer:` instead of `owner:`? Map it here rather than renaming docs.
        "aliases": {},
    },
    "staleness": {
        "enabled": True,
        "max_age_days": 365,
        "cadence_field": "review_cadence",
        "cadence_days": {"monthly": 30, "quarterly": 90, "biannually": 180},
        "grace_days": 30,
    },
    "title": {"budget": 20.0, "require_h1_match": True},
    "pangu": {"enabled": True, "flag_multiple_spaces": True},
    "tables": {
        "reference_required_columns": ["type", "required", "default", "description"],
    },
    "maintenance": {"require_triggers_for": ["task", "troubleshooting"]},
}

CONFIG_DOC = """\
.techdocrc.json — every key is optional; only the keys you set override the default.
Discovered by walking up from the linted file, so docs/ may differ from the repo root.

{
  "metadata": {
    "location": "frontmatter" | "footer" | "none",
    "required": ["title", "owner", "status", "last_updated"],
    "status_field": "status",
    "status_values": ["draft", "active", "needs-update", "deprecated"],
    "date_field": "last_updated",
    "aliases": {"owner": ["maintainer", "author"]}
  },
  "staleness": {
    "enabled": true, "max_age_days": 365,
    "cadence_field": "review_cadence",
    "cadence_days": {"monthly": 30, "quarterly": 90, "biannually": 180},
    "grace_days": 30
  },
  "title":  {"budget": 20.0, "require_h1_match": true},
  "pangu":  {"enabled": true, "flag_multiple_spaces": true},
  "tables": {"reference_required_columns": ["type", "required", "default", "description"]},
  "maintenance": {"require_triggers_for": ["task", "troubleshooting"]}
}
"""

# Default status vocabulary, exposed as a module constant so callers (and the template tests)
# can name it without reaching into the config tree.
VALID_STATUS = set(DEFAULT_CONFIG["metadata"]["status_values"])

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Title budget is language-aware: a CJK character carries far more information than a Latin
# one, so a single character threshold is not comparable across scripts. Budget is measured in
# "weight units" — 1 per CJK char, 0.5 per Latin char/digit — and a leading identifier
# (`RFC-042:`, `ADR-7:`, `[JIRA-12]`) is exempt because it aids search rather than padding.
TITLE_BUDGET = 20.0
IDENT_PREFIX_RE = re.compile(r"^\s*(?:\[[^\]]{1,20}\]|[A-Z]{2,10}[- ]?\d{1,5})\s*[:：-]\s*")
FILLER_RE = re.compile(
    r"(?i)\b(a|an|the|some|various|detailed|comprehensive|complete|simple|basic|"
    r"introduction to|overview of|notes on|thoughts on|things about)\b"
    r"|关于|简介|详解|浅谈|随笔"
)
# Version-sensitive content: if the body names a versioned dependency, the doc should declare
# which versions it applies to, or it silently rots.
VERSION_MENTION_RE = re.compile(
    r"(?i)\b(?:go|python|node(?:\.js)?|java|mysql|postgres(?:ql)?|redis|kafka|kubernetes|k8s|"
    r"docker|terraform)\s*v?\d+(?:\.\d+)+"
)
CJK = r"一-鿿㐀-䶿"
PANGU_RE = re.compile(rf"([{CJK}])([A-Za-z0-9])|([A-Za-z0-9])([{CJK}])")
# Two or three spaces between scripts violates "exactly one space" just as zero does. Four or
# more is deliberately left alone: in Markdown that is indentation or column alignment, not
# prose spacing, and flagging it produced false positives on aligned text.
PANGU_MULTI_RE = re.compile(rf"([{CJK}])( {{2,3}})([A-Za-z0-9])|([A-Za-z0-9])( {{2,3}})([{CJK}])")
# Path charset must be explicit ASCII: Python's \w matches CJK, so a \w-based
# pattern would treat prose like 读/写 as a "path" and swallow the surrounding
# CJK text — masking real pangu violations on any line containing a slash.
URL_RE = re.compile(r"https?://\S+|[A-Za-z0-9._~-]*(?:/[A-Za-z0-9._~-]+)+")
# Stands in for an exempt span (inline code, URL, path). See prose_lines().
SENTINEL = "\x00"
TBD_RE = re.compile(r"^\s*(TBD|TODO|待定|待补充)?\s*$", re.IGNORECASE)

# A parameter table is recognised by its first column, so the error-code, changelog and
# compatibility tables that legitimately live in the same reference doc are not dragged in.
PARAM_FIRST_COL_RE = re.compile(
    r"(?i)^\W*(field|fields|parameter|parameters|param|params|name|argument|arg|"
    r"attribute|attr|option|options|flag|flags|key|property|prop|"
    r"字段|参数|属性|选项|键|配置项)\W*$"
)
# Accepted spellings for each required column. `optional` counts as `required` because it
# carries the same fact with inverted polarity — rejecting it would be pedantry.
COLUMN_SYNONYMS: dict[str, str] = {
    "type": r"(?i)\btype\b|数据类型|类型",
    "required": r"(?i)\brequired\b|\boptional\b|\bmandatory\b|\bnullable\b|必填|必需|是否必填|可选",
    "default": r"(?i)\bdefaults?\b|默认值|默认",
    "description": r"(?i)\bdescription\b|\bdesc\b|\bmeaning\b|\bnotes?\b|\bconstraints?\b|"
                   r"说明|描述|含义|备注|约束",
}
# A heading that declares "what follows is the parameter/field reference". Required as
# corroboration before table-columns fires: a first column merely *named* `Field` is far too
# weak on its own. Forcing every file in this repository through `--type reference` produced 39
# findings against tables like `Field | Value` and `Flag | Purpose` — explanatory tables, not
# API dictionaries. Because table-columns is CRITICAL and therefore blocks delivery, a false
# positive costs more than a miss, so the trigger is deliberately conservative.
PARAM_SECTION_RE = re.compile(
    r"(?i)parameters?\b|\bparams?\b|\bfields?\b|data dictionary|\battributes?\b|"
    r"\barguments?\b|request body|query string|schema\b|"
    r"参数|字段|数据字典|属性|请求体"
)
# Anything that reads as "this doc says when it must be revised".
MAINTENANCE_RE = re.compile(
    r"(?i)^#{1,6}\s+.*(maintenance|upkeep|update trigger|review cadence|when to update|"
    r"维护|更新触发|复审|回顾周期)"
)


class Finding:
    def __init__(self, check: str, severity: str, line: int, message: str):
        self.check = check
        self.severity = severity
        self.line = line
        self.message = message

    def __str__(self) -> str:
        return f"[{self.severity}] {self.check} (line {self.line}): {self.message}"


# ─────────────────────────── configuration ───────────────────────────


def deep_merge(base: dict, override: dict) -> dict:
    """Recursive dict merge; scalars and lists in `override` replace wholesale."""
    out = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def discover_config(start: Path) -> Path | None:
    """Walk up from the linted file looking for `.techdocrc.json`.

    The nearest file wins: a `docs/` subtree may legitimately follow a different convention
    from the repository root.
    """
    here = start.resolve()
    here = here if here.is_dir() else here.parent
    for directory in [here, *here.parents]:
        candidate = directory / CONFIG_FILENAME
        if candidate.is_file():
            return candidate
    return None


def validate_config(cfg: dict, where: str) -> None:
    """Reject a config whose shape is wrong, rather than misbehaving quietly.

    The motivating case: `"aliases": {"owner": "maintainer"}` — a string where a list belongs.
    `resolve_field` then unpacked the string into its characters, looked up `m`, `a`, `i`, …,
    found nothing, and reported `metadata missing owner`. The author sees a confusing complaint
    about the very field they just aliased, with no hint that the config is at fault.
    """
    meta = cfg["metadata"]
    location = meta.get("location")
    if location not in {"frontmatter", "footer", "none"}:
        raise ValueError(f"{where}: metadata.location must be "
                         f"frontmatter|footer|none, got {location!r}")
    for key in ("required", "status_values"):
        if not isinstance(meta.get(key), list):
            raise ValueError(f"{where}: metadata.{key} must be a list")
    aliases = meta.get("aliases", {})
    if not isinstance(aliases, dict):
        raise ValueError(f"{where}: metadata.aliases must be an object")
    for field, names in aliases.items():
        if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
            raise ValueError(
                f"{where}: metadata.aliases[{field!r}] must be a list of strings, got "
                f"{names!r} — a bare string would be read one character at a time")
    for key in ("max_age_days", "grace_days"):
        if not isinstance(cfg["staleness"].get(key), int):
            raise ValueError(f"{where}: staleness.{key} must be an integer")
    if not isinstance(cfg["staleness"].get("cadence_days"), dict):
        raise ValueError(f"{where}: staleness.cadence_days must be an object")
    if not isinstance(cfg["title"].get("budget"), (int, float)):
        raise ValueError(f"{where}: title.budget must be a number")
    if not isinstance(cfg["tables"].get("reference_required_columns"), list):
        raise ValueError(f"{where}: tables.reference_required_columns must be a list")
    unknown_cols = set(cfg["tables"]["reference_required_columns"]) - set(COLUMN_SYNONYMS)
    if unknown_cols:
        raise ValueError(
            f"{where}: tables.reference_required_columns names column(s) with no known "
            f"spellings: {sorted(unknown_cols)}; expected a subset of "
            f"{sorted(COLUMN_SYNONYMS)}")


def load_config(explicit: str | None, doc_path: Path) -> tuple[dict, Path | None]:
    path = Path(explicit) if explicit else discover_config(doc_path)
    if path is None:
        return copy.deepcopy(DEFAULT_CONFIG), None
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: top level must be a JSON object")
    unknown = set(raw) - set(DEFAULT_CONFIG)
    if unknown:
        raise ValueError(
            f"{path}: unknown top-level key(s) {sorted(unknown)}; "
            f"expected a subset of {sorted(DEFAULT_CONFIG)}")
    merged = deep_merge(DEFAULT_CONFIG, raw)
    validate_config(merged, str(path))
    return merged, path


# ─────────────────────────── document scanning ───────────────────────────

# CommonMark: a fence is 3+ backticks OR 3+ tildes, indented at most 3 spaces. It closes only
# on the same character, at least as long, and with no info string. Five checks used to
# re-derive this from `line.startswith("```")`, which missed `~~~` entirely — the contents of
# a `~~~yaml` block were linted as if they were prose, producing pangu findings inside code.
FENCE_OPEN_RE = re.compile(r"^ {0,3}(?P<fence>`{3,}|~{3,})\s*(?P<info>[^`]*)$")


def fence_closes(line: str, char: str, length: int) -> bool:
    match = re.match(r"^ {0,3}(?P<fence>`{3,}|~{3,})\s*$", line)
    if not match:
        return False
    fence = match.group("fence")
    return fence[0] == char and len(fence) >= length


def scan(body: str):
    """Yield (line_no, line, in_code) for every line, resolving code fences correctly.

    `in_code` is True for the fence delimiters themselves as well as their contents, so a
    caller can blank a whole block with a single test. This is the one place fence state is
    tracked; every check consumes it rather than re-implementing it.
    """
    fence_char: str | None = None
    fence_len = 0
    for i, line in enumerate(body.splitlines(), 1):
        if fence_char is None:
            match = FENCE_OPEN_RE.match(line)
            if match:
                fence_char = match.group("fence")[0]
                fence_len = len(match.group("fence"))
                yield i, line, True
                continue
            yield i, line, False
            continue
        if fence_closes(line, fence_char, fence_len):
            fence_char, fence_len = None, 0
        yield i, line, True


def prose_lines(body: str) -> list[tuple[int, str]]:
    """Return (line_no, line) pairs with fenced blocks, inline code and URLs blanked.

    Exempt spans collapse to SENTINEL rather than to the empty string. Deleting them
    outright merged the spaces on either side, so `中 `git-commit` skill` became `中  skill`
    and the "exactly one space" rule reported a double space that the author never wrote —
    78 false positives out of 78 across this repository. SENTINEL is neither CJK nor
    alphanumeric, so it still breaks adjacency for the missing-space rule.
    """
    out: list[tuple[int, str]] = []
    for i, line, in_code in scan(body):
        if in_code:
            out.append((i, ""))
            continue
        line = re.sub(r"`[^`]*`", SENTINEL, line)
        line = URL_RE.sub(SENTINEL, line)
        out.append((i, line))
    return out


def parse_yaml_block(block: str) -> dict:
    fm: dict[str, str] = {}
    for line in block.splitlines():
        if line.lstrip().startswith("#"):
            continue  # whole-line YAML comment
        if ":" in line and not line.startswith(" "):
            key, _, value = line.partition(":")
            value = value.strip()
            # YAML allows a trailing comment. Without stripping it, `status: draft  # notes`
            # was read as the literal value `draft  # notes` and rejected as invalid — which
            # made every annotated template fail its own metadata check. Only strip when the
            # value is unquoted, so a legitimate `#` inside a quoted string survives.
            if value[:1] not in {'"', "'"}:
                value = re.split(r"\s+#", value, maxsplit=1)[0].strip()
            fm[key.strip()] = value.strip("\"'")
    return fm


def split_frontmatter(text: str) -> tuple[dict, str, int]:
    """Return (frontmatter dict, body, body line offset)."""
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not match:
        return {}, text, 0
    return parse_yaml_block(match.group(1)), text[match.end():], match.group(0).count("\n")


def split_footer(text: str) -> tuple[dict, str, int]:
    """Return (metadata dict, body, offset) for a trailing `---` delimited block.

    Some doc systems keep page metadata at the foot of the file. Gate 1 says the repository's
    convention wins, so the linter has to be able to find it there instead of reporting every
    field as missing.
    """
    match = re.search(r"\n---[ \t]*\n(?P<block>(?:[^\n]*\n)*?)---[ \t]*\n?\s*\Z", text)
    if not match:
        return {}, text, 0
    return parse_yaml_block(match.group("block")), text[: match.start() + 1], 0


def resolve_field(fm: dict, field: str, aliases: dict) -> str:
    """Return the value of `field`, honouring the repo's alias spellings."""
    if not field:
        return ""
    for name in (field, *aliases.get(field, ())):
        if fm.get(name):
            return fm[name]
    return ""


# ─────────────────────────── checks ───────────────────────────


def check_metadata(fm: dict, cfg: dict) -> list[Finding]:
    meta = cfg["metadata"]
    aliases = meta.get("aliases", {})
    findings = []
    for field in meta["required"]:
        if not resolve_field(fm, field, aliases):
            findings.append(Finding("metadata", CRITICAL, 1, f"metadata missing `{field}`"))

    status_field = meta.get("status_field", "")
    valid = set(meta.get("status_values") or [])
    status = resolve_field(fm, status_field, aliases)
    if status and valid and status not in valid:
        findings.append(Finding(
            "status-value", CRITICAL, 1,
            f"{status_field} {status!r} not in {sorted(valid)}"))

    date_field = meta.get("date_field", "")
    raw = resolve_field(fm, date_field, aliases)
    if raw:
        if not DATE_RE.match(raw):
            findings.append(Finding(
                "date-format", CRITICAL, 1, f"{date_field} {raw!r} is not YYYY-MM-DD"))
        else:
            # Shape alone is not enough: `2026-99-99` matched the old regex and passed,
            # so a stale-date audit could never rely on this field.
            try:
                datetime.date.fromisoformat(raw)
            except ValueError:
                findings.append(Finding(
                    "date-format", CRITICAL, 1,
                    f"{date_field} {raw!r} is not a real calendar date"))
    return findings


def check_staleness(fm: dict, cfg: dict, today: datetime.date) -> list[Finding]:
    """Is the document actually current?

    Checking that the date merely *parses* let `last_updated: 2000-01-01` through with zero
    findings, which made "anti-staleness" a claim about metadata presence rather than about
    freshness. Age is compared against the doc's declared review cadence when it has one, and
    against `max_age_days` otherwise.
    """
    stale = cfg["staleness"]
    meta = cfg["metadata"]
    if not stale.get("enabled", True) or meta.get("location") == "none":
        return []
    aliases = meta.get("aliases", {})
    raw = resolve_field(fm, meta.get("date_field", ""), aliases)
    if not raw or not DATE_RE.match(raw):
        return []  # already reported by metadata / date-format
    try:
        updated = datetime.date.fromisoformat(raw)
    except ValueError:
        return []  # already reported by date-format

    if updated > today:
        return [Finding(
            "staleness", WARNING, 1,
            f"{meta['date_field']} {raw} is in the future (today {today.isoformat()}) — "
            "a post-dated document cannot be audited for freshness")]

    cadence = resolve_field(fm, stale.get("cadence_field", ""), aliases).strip().lower()
    cadence_days = stale.get("cadence_days", {})
    if cadence in cadence_days:
        limit = cadence_days[cadence] + stale.get("grace_days", 0)
        basis = f"declared {stale['cadence_field']}={cadence}"
    else:
        limit = stale.get("max_age_days", 365)
        basis = f"default max_age_days={limit}"

    age = (today - updated).days
    if age <= limit:
        return []

    status = resolve_field(fm, meta.get("status_field", ""), aliases)
    hint = ""
    if status == "active":
        hint = (" — status is `active`, which asserts the content is correct; set "
                "`needs-update` or revise the document")
    return [Finding(
        "staleness", WARNING, 1,
        f"{meta['date_field']} {raw} is {age} days old, past the {limit}-day review window "
        f"({basis}){hint}")]


def check_maintenance(fm: dict, body: str, cfg: dict, doc_type: str | None,
                      offset: int) -> list[Finding]:
    """Scorecard Hygiene, mechanised: does the doc say when it must be updated?

    Satisfied by either a declared review cadence in the metadata or a maintenance section in
    the body — the two ways this skill tells authors to record it.
    """
    required_for = cfg["maintenance"].get("require_triggers_for", [])
    if not doc_type or doc_type not in required_for:
        return []
    aliases = cfg["metadata"].get("aliases", {})
    if resolve_field(fm, cfg["staleness"].get("cadence_field", ""), aliases):
        return []
    for _, line, in_code in scan(body):
        if not in_code and MAINTENANCE_RE.match(line.strip()):
            return []
    return [Finding(
        "maintenance", WARNING, offset + 1,
        f"{doc_type} doc states no update trigger: add a maintenance section, or a "
        f"`{cfg['staleness'].get('cadence_field')}` field, so staleness is detectable")]


def check_fence_balance(body: str, offset: int) -> list[Finding]:
    """An unclosed fence silently swallows the rest of the document — every later check that
    skips fenced content stops seeing anything, so this must be critical."""
    open_line: int | None = None
    fence_char: str | None = None
    fence_len = 0
    for i, line in enumerate(body.splitlines(), 1):
        if fence_char is None:
            match = FENCE_OPEN_RE.match(line)
            if match:
                fence_char = match.group("fence")[0]
                fence_len = len(match.group("fence"))
                open_line = i
        elif fence_closes(line, fence_char, fence_len):
            fence_char, fence_len, open_line = None, 0, None
    if open_line is not None:
        return [Finding(
            "fence-balance", CRITICAL, offset + open_line,
            "code fence opened here is never closed — the rest of the document is "
            "treated as code by every downstream check")]
    return []


def check_applicable_versions(fm: dict, body: str, offset: int, cfg: dict) -> list[Finding]:
    # Resolved through the alias map like every other field: a repo that calls this
    # `applies_to:` would otherwise be told the field is missing while it is sitting right there.
    if resolve_field(fm, "applicable_versions", cfg["metadata"].get("aliases", {})):
        return []
    for line_no, line in prose_lines(body):
        m = VERSION_MENTION_RE.search(line)
        if m:
            return [Finding(
                "applicable-versions", WARNING, offset + line_no,
                f"body pins a version ({m.group(0)!r}) but metadata has no "
                "`applicable_versions` — the doc cannot be audited for staleness")]
    return []


def title_weight(title: str) -> float:
    """Language-aware length: CJK 1.0, Latin/digit 0.5, leading identifier exempt."""
    core = IDENT_PREFIX_RE.sub("", title)
    weight = 0.0
    for ch in core:
        if re.match(rf"[{CJK}]", ch):
            weight += 1.0
        elif ch.isalnum():
            weight += 0.5
    return weight


def normalise_title(title: str) -> str:
    """Compare titles by meaning, not by byte.

    The identifier prefix is stripped so `RFC-042: Migrate to X` and `Migrate to X` count as
    the same document; case and trailing punctuation are ignored for the same reason.
    """
    core = IDENT_PREFIX_RE.sub("", title).strip()
    core = re.sub(r"\s+", " ", core)
    return core.strip(" .。:：!！?？").casefold()


SEPARATOR_CELL_RE = re.compile(r"^:?-{3,}:?$")


def is_separator_row(line: str) -> bool:
    """True only for a genuine markdown alignment row.

    The previous test was `^\\s*\\|[\\s:|-]+\\|\\s*$`. Because that character class admits
    spaces and pipes, an entirely **blank data row** — `|   |   |   |` — matched it and was
    skipped, so a parameter table with no values filled in produced no findings at all and
    sailed through the Critical completeness gate for reference docs. Every cell must now
    actually look like `---`, `:---`, `---:` or `:---:`.
    """
    stripped = line.strip()
    if not stripped.startswith("|"):
        return False
    cells = [c.strip() for c in stripped.strip("|").split("|")]
    return bool(cells) and all(SEPARATOR_CELL_RE.match(c) for c in cells)


def row_cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def check_tables(body: str, offset: int, severity: str) -> list[Finding]:
    findings = []
    for i, line, in_code in scan(body):
        if in_code or not line.lstrip().startswith("|") or is_separator_row(line):
            continue
        cells = row_cells(line)
        for cell in cells:
            if TBD_RE.match(cell) and cell != "":
                findings.append(Finding(
                    "table-cells", severity, offset + i,
                    f"table cell is a placeholder: {cell!r}"))
            elif cell == "" and len(cells) > 1:
                findings.append(Finding(
                    "table-cells", severity, offset + i, "empty table cell"))
    return findings


def iter_table_headers(body: str):
    """Yield (line_no, header_cells, enclosing_heading) for every markdown table.

    A header is the row immediately preceding an alignment row — in GFM that is the only
    structural way to tell a header from a data row. The nearest preceding heading travels
    with it because a table's meaning lives in the section that introduces it.
    """
    rows: list[tuple[int, str]] = []
    heading_at: dict[int, str] = {}
    heading = ""
    for i, line, in_code in scan(body):
        if in_code:
            continue
        if re.match(r"^#{1,6}\s+\S", line):
            heading = line.lstrip("# ").strip()
        elif line.lstrip().startswith("|"):
            rows.append((i, line))
            heading_at[i] = heading
    for idx, (line_no, line) in enumerate(rows):
        if idx + 1 >= len(rows):
            continue
        next_no, next_line = rows[idx + 1]
        if next_no == line_no + 1 and is_separator_row(next_line) and not is_separator_row(line):
            yield line_no, row_cells(line), heading_at[line_no]


def check_table_columns(body: str, offset: int, cfg: dict,
                        doc_type: str | None) -> list[Finding]:
    """Reference docs: a parameter table must carry the columns the Critical item names.

    Checking only for empty and `TBD` cells meant a table reduced to `Field | Description`
    scored a perfect pass — every value present, three quarters of the contract missing.

    Identifying the table takes two signals, not one. A field-ish first column alone matched
    explanatory tables (`Field | Value`, `Flag | Purpose`) all over this repository; it must be
    corroborated by either a section heading that declares a parameter reference, or by the
    table already carrying at least two of the required columns. Tables whose first column is
    `Code`, `Version` or `Date` — the error-code, compatibility and changelog tables that
    legitimately share a reference doc — never qualify.
    """
    if doc_type != "reference":
        return []
    required = [c for c in cfg["tables"].get("reference_required_columns", [])
                if c in COLUMN_SYNONYMS]
    if not required:
        return []
    findings = []
    for line_no, header, heading in iter_table_headers(body):
        if not header or not PARAM_FIRST_COL_RE.match(header[0]):
            continue
        joined = " | ".join(header)
        present = [col for col in required if re.search(COLUMN_SYNONYMS[col], joined)]
        missing = [col for col in required if col not in present]
        if not missing:
            continue
        if not (PARAM_SECTION_RE.search(heading) or len(present) >= 2):
            continue
        findings.append(Finding(
            "table-columns", CRITICAL, offset + line_no,
            f"parameter table is missing column(s) {missing} — a reader cannot use a "
            f"field reference without them (header was {header}, "
            f"section {heading or '<none>'!r})"))
    return findings


def check_headings(body: str, offset: int, cfg: dict, fm: dict) -> list[Finding]:
    findings = []
    h1_lines = []
    for i, line, in_code in scan(body):
        if not in_code and re.match(r"^#\s+\S", line):
            h1_lines.append((i, line.lstrip("# ").strip()))
    if len(h1_lines) != 1:
        findings.append(Finding(
            "single-h1", WARNING, offset + (h1_lines[1][0] if len(h1_lines) > 1 else 1),
            f"expected exactly 1 H1, found {len(h1_lines)}"))
    if not h1_lines:
        return findings

    line_no, title = h1_lines[0]
    budget = float(cfg["title"].get("budget", TITLE_BUDGET))
    weight = title_weight(title)
    if weight > budget:
        findings.append(Finding(
            "title-weight", WARNING, offset + line_no,
            f"title weight {weight:.1f} > {budget:.0f} "
            f"(CJK 1.0/char, Latin 0.5/char, ID prefix exempt): {title!r}"))
    filler = FILLER_RE.search(IDENT_PREFIX_RE.sub("", title))
    if filler:
        findings.append(Finding(
            "title-weight", WARNING, offset + line_no,
            f"title contains filler {filler.group(0)!r} — SPA wants searchable keywords, "
            f"not padding: {title!r}"))

    if cfg["title"].get("require_h1_match", True):
        declared = resolve_field(fm, "title", cfg["metadata"].get("aliases", {}))
        if declared and normalise_title(declared) != normalise_title(title):
            findings.append(Finding(
                "title-h1-match", WARNING, offset + line_no,
                f"metadata title {declared!r} and H1 {title!r} name different documents — "
                "sidebars and search indexes show the metadata one, the reader sees the H1"))
    return findings


def check_code_fences(body: str, offset: int) -> list[Finding]:
    findings = []
    fence_char: str | None = None
    fence_len = 0
    for i, line in enumerate(body.splitlines(), 1):
        if fence_char is None:
            match = FENCE_OPEN_RE.match(line)
            if match:
                fence_char = match.group("fence")[0]
                fence_len = len(match.group("fence"))
                if not match.group("info").strip():
                    findings.append(Finding(
                        "code-fence-lang", WARNING, offset + i,
                        "fenced code block without language tag"))
        elif fence_closes(line, fence_char, fence_len):
            fence_char, fence_len = None, 0
    return findings


def check_pangu(body: str, offset: int, cfg: dict) -> list[Finding]:
    if not cfg["pangu"].get("enabled", True):
        return []
    findings = []
    flag_multi = cfg["pangu"].get("flag_multiple_spaces", True)
    for line_no, line in prose_lines(body):
        match = PANGU_RE.search(line)
        if match:
            findings.append(Finding(
                "pangu-spacing", WARNING, offset + line_no,
                f"missing space between CJK and Latin: ...{match.group(0)}..."))
            continue
        # Table rows pad cells to align pipes; that is layout, not prose spacing.
        if flag_multi and not line.lstrip().startswith("|"):
            multi = PANGU_MULTI_RE.search(line)
            if multi:
                gap = multi.group(2) or multi.group(5)
                findings.append(Finding(
                    "pangu-spacing", WARNING, offset + line_no,
                    f"{len(gap)} spaces between CJK and Latin — the rule is exactly one: "
                    f"...{multi.group(0)}..."))
    return findings


def lint(text: str, doc_type: str | None = None, config: dict | None = None,
         today: datetime.date | None = None) -> list[Finding]:
    cfg = config or copy.deepcopy(DEFAULT_CONFIG)
    today = today or datetime.date.today()
    location = cfg["metadata"].get("location", "frontmatter")
    if location == "footer":
        fm, body, offset = split_footer(text)
    elif location == "none":
        fm, body, offset = {}, text, 0
    else:
        fm, body, offset = split_frontmatter(text)

    # Scorecard marks complete tables as Critical for reference docs only.
    table_severity = CRITICAL if doc_type == "reference" else WARNING
    findings: list[Finding] = []
    if location != "none":
        findings += check_metadata(fm, cfg)
    findings += check_fence_balance(body, offset)
    findings += check_tables(body, offset, table_severity)
    findings += check_table_columns(body, offset, cfg, doc_type)
    findings += check_headings(body, offset, cfg, fm)
    findings += check_code_fences(body, offset)
    findings += check_pangu(body, offset, cfg)
    findings += check_applicable_versions(fm, body, offset, cfg)
    findings += check_staleness(fm, cfg, today)
    findings += check_maintenance(fm, body, cfg, doc_type, offset)
    return findings


# Scorecard applicability, mirroring the tags in SKILL.md § Gate 3. Kept here so the
# denominator is computed rather than eyeballed: a fixed "4/6" was unreachable for concept,
# reference and design docs. Third element is the `when` condition, or None when the item
# applies unconditionally to every type in the second element.
SCORECARD = {
    "Critical": [
        ("commands runnable in form + verification level declared",
         {"task", "troubleshooting", "concept"}, None),
        ("每步有预期输出与验证 / expected output + verification", {"task", "troubleshooting"}, None),
        ("metadata owner+last_updated+status", "all", None),
        ("terminology consistent after first definition", "all", None),
        ("param tables complete", {"reference"}, None),
    ],
    "Standard": [
        ("conclusion first", "all", None),
        ("prerequisites complete", {"task", "troubleshooting"}, None),
        ("rollback documented", {"task"}, None),
        ("title follows SPA", "all", None),
        ("code examples self-contained", {"task", "troubleshooting", "reference"}, None),
        ("error codes documented", {"reference"}, "api doc"),
    ],
    "Hygiene": [
        ("diagrams titled + legend", "all", "diagrams present"),
        # Stays unconditional. "A related doc exists" is not decidable from the document, and
        # the forward-eval grader resolves every condition from the document — an unresolvable
        # condition silently zeroed the item and moved every denominator. The absolutism the
        # review objected to is removed in the wording instead: declaring the document
        # standalone satisfies the item, so a greenfield doc can pass it.
        ("cross-references or standalone declared", "all", None),
        # Split by type: an 80 % lists-and-tables ratio suits a reference or a runbook and
        # actively harms a design doc, whose argument has to be carried in prose.
        ("structured info in lists/tables", {"reference", "task", "troubleshooting"}, None),
        ("paragraphs stay scannable", {"concept", "design"}, None),
        ("applicable_versions present", "all", "version-sensitive"),
        ("maintenance triggers noted", {"task", "troubleshooting"}, None),
        ("prevention thresholds", {"troubleshooting"}, None),
    ],
}


def scorecard_report(doc_type: str | None) -> str:
    """Print applicable / N-A counts and the ⅔ threshold for each tier."""
    t = doc_type or "unspecified"
    lines = [f"scorecard applicability for --type {t}:"]
    for tier, items in SCORECARD.items():
        applicable, conditional, na = [], [], []
        for name, types, condition in items:
            in_scope = types == "all" or (doc_type in types if doc_type else True)
            if not in_scope:
                na.append(name)
            elif condition:
                conditional.append(f"{name} (only if {condition})")
            else:
                applicable.append(name)
        if tier == "Critical":
            verdict = (f"all {len(applicable)} applicable must pass"
                       f"{f'; {len(conditional)} conditional' if conditional else ''}")
        else:
            base = len(applicable)
            need = math.ceil(base * 2 / 3) if base else 0
            verdict = (f"need {need}/{base} applicable (⅔ rounded up)" if base
                       else "n/a (0 applicable) — passes trivially")
            if conditional:
                verdict += f"; +{len(conditional)} conditional count only when the condition holds"
        lines.append(f"  {tier:9s} applicable={len(applicable)} conditional={len(conditional)} "
                     f"n/a={len(na)} -> {verdict}")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("file")
    parser.add_argument("--type", default=None, dest="doc_type",
                        choices=["concept", "task", "reference", "troubleshooting", "design"],
                        help="doc type; table-cells is critical for reference, warning otherwise")
    parser.add_argument("--strict", action="store_true", help="exit 1 on warnings too")
    parser.add_argument("--scorecard", action="store_true",
                        help="print applicable/N-A scorecard counts and thresholds")
    parser.add_argument("--config", default=None,
                        help=f"config file path (default: nearest {CONFIG_FILENAME})")
    parser.add_argument("--today", default=None,
                        help="YYYY-MM-DD reference date for the staleness check")
    parser.add_argument("--print-config", action="store_true",
                        help="print the config schema and the effective merge, then exit")
    args = parser.parse_args(argv)

    path = Path(args.file)
    try:
        cfg, cfg_path = load_config(args.config, path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 3

    if args.print_config:
        print(CONFIG_DOC)
        print(f"effective config (from {cfg_path or 'built-in defaults'}):")
        print(json.dumps(cfg, indent=2, ensure_ascii=False))
        return 0

    try:
        today = (datetime.date.fromisoformat(args.today) if args.today
                 else datetime.date.today())
    except ValueError:
        print(f"--today {args.today!r} is not a YYYY-MM-DD date", file=sys.stderr)
        return 3

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"cannot read {path}: {exc}", file=sys.stderr)
        return 2

    findings = lint(text, args.doc_type, cfg, today)
    for f in findings:
        print(f)

    criticals = [f for f in findings if f.severity == CRITICAL]
    warnings = [f for f in findings if f.severity == WARNING]
    print(f"lint_doc: {len(criticals)} critical, {len(warnings)} warning(s)")
    if cfg_path:
        print(f"lint_doc: config {cfg_path}")
    if cfg["metadata"].get("location") == "none":
        print("lint_doc: metadata + staleness checks SKIPPED (metadata.location=none)")
    if args.scorecard:
        print(scorecard_report(args.doc_type))
    if criticals or (args.strict and warnings):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
