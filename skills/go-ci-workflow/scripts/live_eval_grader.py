#!/usr/bin/env python3
"""go-ci-workflow live-eval harness core: scenario derivation, repository
materialisation, structural grading, treatment assertion and aggregation.

This file is EMBEDDED in scripts/run_live_eval.sh and written to a temp file at
run time. It is kept in one place on purpose: the grader and the runner must
never drift apart, and the skill ships one new executable, not three.

Nothing here judges prose. Every axis is extracted as DATA:

  shape      the closed set of 6 repository shapes, parsed out of SKILL.md
             "### 1) Repository Shape Gate" at run time
  parity     per job, exactly one of the 3 execution-path labels parsed out of
             "### 2) Local Parity Gate"
  contract   the 9 named items parsed out of "## Output Contract", each looked
             for in a LABEL POSITION (heading / bold span / text before a colon
             / table cell), never anywhere in the prose
  integrity  the literal string parsed out of "### 4) Execution Integrity Gate"

No vocabulary is retyped here. Every closed set is derived from SKILL.md and
cross-checked against a small probe table; if SKILL.md's contract changes shape
the harness aborts as a SETUP failure instead of grading a stale contract.
"""

import argparse
import json
import os
import pathlib
import re
import sys

SETUP = 3  # keep in sync with run_live_eval.sh


class SetupError(Exception):
    """Nothing can be measured. Never surfaces as a score."""


# --------------------------------------------------------------------------
# SKILL.md parsing — the single source of every closed vocabulary
# --------------------------------------------------------------------------

def section(text, heading_re):
    """Body of the first heading matching `heading_re`, up to the next heading
    of the same or higher level. Scoping matters: an assertion that may match
    anywhere in a 240-line SKILL.md is not an assertion about that section."""
    m = re.search(heading_re, text, re.MULTILINE)
    if not m:
        return ""
    level = len(re.match(r"#+", m.group(0)).group(0))
    rest = text[m.end():]
    nxt = re.search(r"^#{1," + str(level) + r"}\s", rest, re.MULTILINE)
    return rest[:nxt.start()] if nxt else rest


def bullets(block):
    """The FIRST contiguous run of bullets in `block`.

    Not every bullet in a section: "### 1) Repository Shape Gate" holds two
    lists — the six shapes, then an "Inspect:" checklist — and taking all of
    them yielded an 11-item "closed set" of shapes. A closed vocabulary that
    silently absorbs the next list under the same heading is not closed."""
    run, out = False, []
    for line in block.splitlines():
        m = re.match(r"^[-*]\s+(.+)$", line)
        if m:
            run = True
            out.append(m.group(1).strip())
        elif run and line.strip():
            break
    return out


def backticked(block):
    out, seen = [], set()
    for m in re.finditer(r"`([^`\n]+)`", block):
        v = m.group(1).strip()
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


# Shape label -> regex that recognises that shape as a model would write it.
# The bijection tripwire below proves each pattern matches its own canonical
# label and NO other, so this table cannot silently rot into a second, wrong
# copy of the shape list.
SHAPE_PROBES = {
    "single-module application": r"single[-\s]module\s+(?:application|service|app|binary)",
    "single-module library": r"single[-\s]module\s+library",
    "multi-module repository": r"multi[-\s]module\s+(?:repo|repository)",
    "monorepo with multiple apps/packages": r"monorepo",
    "Docker-heavy repository": r"docker[-\s]heavy",
    "reusable-workflow candidate": r"reusable[-\s]workflow\s+candidate",
}

# Output-Contract item -> (anchor that must appear in the derived bullet,
#                          regex matched against LABEL positions only)
CONTRACT_PROBES = {
    "changed_files": (
        "changed files",
        r"\bchanged files?\b|\bfiles? (?:changed|created|written|added|modified)\b"
        r"|\bnew files?\b|\bdeliverables?\b",
    ),
    "shape": (
        "repository shape",
        r"\b(?:repository|repo)\s+shape\b|\bshape\s+classification\b"
        r"|^\s*shape\s*$|\brepository\s+classification\b",
    ),
    "jobs_and_paths": (
        "job list",
        r"\bjobs?\b",
    ),
    "triggers": (
        "trigger configuration",
        r"\btriggers?\b|\btrigger configuration\b|\bevents?\b",
    ),
    "permissions": (
        "permissions and secret",
        r"\bpermissions?\b|\bsecrets?\b",
    ),
    "tool_versions": (
        "tool versions",
        r"\btool(?:ing)? versions?\b|\bpinned versions?\b|\bversions? (?:used|pinned)\b"
        r"|\bpinned (?:tools?|actions?)\b|\btool pinning\b",
    ),
    "missing_targets": (
        "missing targets",
        r"\bmissing\b|\bgaps?\b|\babsent\b",
    ),
    "validation": (
        "validation performed",
        r"\bvalidation\b|\bvalidated\b|\bverification\b",
    ),
    "followup": (
        "recommended follow-up",
        r"\bfollow[-\s]?ups?\b|\brecommend(?:ed|ations?)\b|\bnext steps?\b",
    ),
}

# Fixture `expected_output_fields` wording -> canonical contract key. A fixture
# field with no mapping is a SETUP failure, not a silently-ignored requirement.
FIELD_ALIASES = {
    "changed files": "changed_files",
    "repository shape classification": "shape",
    "job list": "jobs_and_paths",
    "execution path for each job": "jobs_and_paths",
    "trigger configuration": "triggers",
    "permissions": "permissions",
    "permissions and secret assumptions": "permissions",
    "tool versions": "tool_versions",
    "tool versions used": "tool_versions",
    "missing targets": "missing_targets",
    "missing targets or missing local entrypoints": "missing_targets",
    "validation performed": "validation",
    "recommended follow-up work": "followup",
}


class Vocab:
    def __init__(self, skill_md):
        text = pathlib.Path(skill_md).read_text(encoding="utf-8")
        self.text = text

        self.shapes = bullets(section(text, r"^### 1\) Repository Shape Gate"))
        parity = section(text, r"^### 2\) Local Parity Gate")
        self.paths = backticked("\n".join(bullets(parity)))
        integrity = section(text, r"^### 4\) Execution Integrity Gate")
        lits = backticked("\n".join(bullets(integrity)))
        self.integrity_literal = lits[0] if lits else ""
        self.contract = bullets(section(text, r"^## Output Contract"))
        self.gate_names = re.findall(
            r"^###\s+\d+\)\s+(.+?)\s*$",
            section(text, r"^## Mandatory Gates"), re.MULTILINE)

        self._check()

    def _check(self):
        """Fail loudly when SKILL.md's structure moved. Grading against a
        vocabulary the skill no longer defines is worse than not grading."""
        problems = []
        if len(self.shapes) != 6:
            problems.append(
                "Repository Shape Gate: expected 6 shape bullets, parsed "
                "%d %r" % (len(self.shapes), self.shapes))
        if len(self.paths) != 3:
            problems.append(
                "Local Parity Gate: expected 3 backticked execution paths, "
                "parsed %d %r" % (len(self.paths), self.paths))
        if not self.integrity_literal:
            problems.append(
                "Execution Integrity Gate: no backticked literal parsed")
        if len(self.contract) != 9:
            problems.append(
                "Output Contract: expected 9 bullets, parsed %d"
                % len(self.contract))
        if len(self.gate_names) != 5:
            problems.append(
                "Mandatory Gates: expected 5 '### N) ... Gate' headings, "
                "parsed %d %r" % (len(self.gate_names), self.gate_names))

        # Shape probe bijection: one probe per parsed shape, and each probe
        # matches its own label and no sibling label.
        if len(self.shapes) == 6:
            if set(self.shapes) != set(SHAPE_PROBES):
                problems.append(
                    "SHAPE_PROBES keys %r do not equal SKILL.md's shapes %r"
                    % (sorted(SHAPE_PROBES), sorted(self.shapes)))
            else:
                for label, pat in SHAPE_PROBES.items():
                    hits = [s for s in self.shapes
                            if re.search(pat, s, re.IGNORECASE)]
                    if hits != [label]:
                        problems.append(
                            "shape probe %r matches %r, must match only %r"
                            % (pat, hits, label))

        # Contract probe bijection: every anchor hits exactly one bullet and
        # every bullet is claimed by exactly one anchor.
        if len(self.contract) == 9:
            claimed = {}
            for key, (anchor, _) in CONTRACT_PROBES.items():
                hits = [b for b in self.contract if anchor in b.lower()]
                if len(hits) != 1:
                    problems.append(
                        "contract anchor %r matches %d bullets, need exactly 1"
                        % (anchor, len(hits)))
                else:
                    claimed.setdefault(hits[0], []).append(key)
            for bullet in self.contract:
                owners = claimed.get(bullet, [])
                if len(owners) != 1:
                    problems.append(
                        "Output Contract bullet %r is claimed by %d probes"
                        % (bullet[:60], len(owners)))

        if problems:
            raise SetupError(
                "SKILL.md no longer matches what this harness parses:\n  - "
                + "\n  - ".join(problems))


# --------------------------------------------------------------------------
# Scenario derivation — one source of truth: scripts/tests/golden/*.json
# --------------------------------------------------------------------------

# The fixture `description` is "<situation> — <what the skill should do>".
# Only the SITUATION half becomes the prompt. Feeding the model the second half
# would hand it the answer: fixture 006's tail literally names "Degraded Output
# Gate", which is one of the closed-vocabulary tokens the treatment assertion
# and the grader look for.
SPLIT_RE = re.compile(r"\s+[\u2014\u2013]\s+|\s+--\s+|(?<=\.)\s+(?=[Ss]kill\s)")

# Behavioural vocabulary that must never reach the prompt.
def leak_patterns(vocab):
    pats = [re.escape(g) for g in vocab.gate_names]
    pats += [re.escape(p) for p in vocab.paths]
    pats.append(re.escape(vocab.integrity_literal))
    pats.append(r"\bskill (?:should|must)\b")
    return pats


def situation_of(description):
    return SPLIT_RE.split(description, maxsplit=1)[0].strip().rstrip(".")


def render_context(ctx):
    lines = []
    for key in sorted(ctx):
        val = ctx[key]
        if isinstance(val, list):
            rendered = ", ".join(str(v) for v in val) if val else "(none)"
        elif isinstance(val, bool):
            rendered = "yes" if val else "no"
        else:
            rendered = str(val)
        lines.append("  %s: %s" % (key, rendered))
    return "\n".join(lines)


PROMPT_TEMPLATE = """{situation}.

Repository facts, as observed on the repository you are working in:
{facts}

The repository is the current working directory. Create the GitHub Actions CI
workflow for it, then report what you did."""


def derive(golden_dir, vocab):
    paths = sorted(pathlib.Path(golden_dir).glob("*.json"))
    if not paths:
        raise SetupError("no golden fixtures under %s" % golden_dir)

    leaks = leak_patterns(vocab)
    scenarios, problems = [], []
    for p in paths:
        fx = json.loads(p.read_text(encoding="utf-8"))
        situation = situation_of(fx["description"])
        if not situation:
            problems.append("%s: empty situation half" % fx["id"])
            continue
        for pat in leaks:
            if pat and re.search(pat, situation, re.IGNORECASE):
                problems.append(
                    "%s: situation half leaks behavioural vocabulary %r — the "
                    "prompt would hand the model the answer" % (fx["id"], pat))

        for field in fx.get("expected_output_fields", []):
            if field.lower() not in FIELD_ALIASES:
                problems.append(
                    "%s: expected_output_fields entry %r has no canonical "
                    "mapping; it would be silently dropped" % (fx["id"], field))

        exp_shape = fx.get("expected_shape")
        hinted = bool(
            exp_shape
            and re.search(SHAPE_PROBES[exp_shape], situation, re.IGNORECASE))

        scenarios.append({
            "id": fx["id"],
            "scenario_type": fx["scenario_type"],
            "situation": situation,
            "prompt": PROMPT_TEMPLATE.format(
                situation=situation, facts=render_context(fx["context"])),
            "context": fx["context"],
            "expected_shape": exp_shape,
            "expected_execution_paths": fx.get("expected_execution_paths", {}),
            "expected_jobs": fx.get("expected_jobs", []),
            "expected_output_fields": fx.get("expected_output_fields", []),
            "shape_hinted": hinted,
        })

    if problems:
        raise SetupError("fixture derivation refused:\n  - "
                         + "\n  - ".join(problems))
    return scenarios


# --------------------------------------------------------------------------
# Repository materialisation — so the skill's own discovery script has
# something real to probe. Everything written here comes from the fixture's
# `context`; nothing is invented per scenario.
# --------------------------------------------------------------------------

def write(root, rel, content):
    p = pathlib.Path(root) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def materialize(scenario, root):
    ctx = scenario["context"]
    mods = list(ctx.get("go_mod_paths") or [])
    if not mods:
        n = int(ctx.get("go_mod_count", 1) or 0)
        mods = ["go.mod"] + ["module%d/go.mod" % i for i in range(1, n)]
    for rel in mods:
        name = pathlib.PurePosixPath(rel).parent.as_posix().strip(".") or "app"
        write(root, rel, "module example.com/%s\n\ngo 1.23\n" % name.replace("/", "-"))

    write(root, "main.go",
          "package main\n\nfunc main() {\n\tprintln(\"ok\")\n}\n")
    if "unit" in (ctx.get("test_types") or []):
        write(root, "main_test.go",
              "package main\n\nimport \"testing\"\n\n"
              "func TestMain_(t *testing.T) {}\n")

    for d in ctx.get("app_dirs") or []:
        write(root, "%s/main.go" % d,
              "package main\n\nfunc main() {}\n")

    if ctx.get("has_makefile"):
        targets = ctx.get("makefile_targets") or []
        body = ".PHONY: %s\n\n" % " ".join(targets)
        for t in targets:
            body += "%s:\n\t@echo %s\n\n" % (t, t)
        write(root, "Makefile", body)
    if ctx.get("has_taskfile"):
        write(root, "Taskfile.yml", "version: '3'\ntasks:\n  ci:\n    cmds:\n      - go test ./...\n")
    if ctx.get("has_mage"):
        write(root, "magefile.go", "//go:build mage\n\npackage main\n\nfunc CI() error { return nil }\n")
    if ctx.get("has_scripts"):
        write(root, "scripts/ci.sh", "#!/usr/bin/env bash\nset -euo pipefail\ngo test ./...\n")

    dockerfiles = list(ctx.get("dockerfile_paths") or [])
    if not dockerfiles and ctx.get("has_dockerfile"):
        n = int(ctx.get("dockerfile_count", 1) or 1)
        apps = ctx.get("app_dirs") or []
        if len(apps) == n:
            dockerfiles = ["%s/Dockerfile" % a for a in apps]
        else:
            dockerfiles = ["Dockerfile"] + ["build/app%d/Dockerfile" % i
                                            for i in range(1, n)]
    for rel in dockerfiles:
        args = "".join("ARG %s\n" % a for a in (ctx.get("build_args") or []))
        write(root, rel, "FROM golang:1.23-alpine\n%sWORKDIR /src\nCOPY . .\n"
                         "RUN go build ./...\n" % args)

    if ctx.get("has_golangci_lint_config"):
        write(root, ".golangci.yml",
              "version: \"2\"\nlinters:\n  enable:\n    - govet\n")

    for d in ctx.get("test_dirs") or []:
        write(root, "%s/main_test.go" % d,
              "//go:build integration\n\npackage integration\n\n"
              "import \"testing\"\n\nfunc TestIntegration_(t *testing.T) {}\n")
    types = ctx.get("test_types") or []
    if "integration" in types and not (ctx.get("test_dirs") or []):
        write(root, "test/integration/main_test.go",
              "//go:build integration\n\npackage integration\n\n"
              "import \"testing\"\n\nfunc TestIntegration_(t *testing.T) {}\n")
    if "e2e" in types:
        write(root, "test/e2e/main_test.go",
              "//go:build e2e\n\npackage e2e\n\n"
              "import \"testing\"\n\nfunc TestE2E_(t *testing.T) {}\n")

    for wf in ctx.get("existing_workflows") or []:
        write(root, ".github/workflows/%s" % wf,
              "name: ci\non:\n  push:\n    branches: [main]\njobs:\n"
              "  build:\n    runs-on: ubuntu-latest\n    steps:\n"
              "      - uses: actions/checkout@v5\n")


# --------------------------------------------------------------------------
# Response parsing
# --------------------------------------------------------------------------

HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


def load_response(path):
    """Strip HTML comments before grading. The replay recordings carry their
    metadata in an HTML comment; without this a recording could satisfy its own
    grader through its own header."""
    return HTML_COMMENT.sub(" ", pathlib.Path(path).read_text(encoding="utf-8"))


def strip_fences(text):
    """Drop fenced code blocks.

    The Output Contract is about the REPORT, not the artifact. Leaving the
    fences in meant a bare YAML dump scored the `permissions` and `jobs`
    contract items for free, off its own `permissions:` and `jobs:` keys —
    the workflow satisfying the contract that asks you to describe the
    workflow."""
    out, fenced = [], False
    for line in text.splitlines():
        if re.match(r"^\s*(```|~~~)", line):
            fenced = not fenced
            continue
        if not fenced:
            out.append(line)
    return "\n".join(out)


def label_strings(text):
    """Every position in the document that acts as a LABEL rather than prose:
    headings, bold spans, the text before the first colon on a line, and table
    cells. An Output-Contract item counts as reported only if it appears in one
    of these — a passing mention inside a sentence does not satisfy a contract
    that says "always return"."""
    text = strip_fences(text)
    labels = []
    for line in text.splitlines():
        s = line.strip()
        m = re.match(r"^#{1,6}\s+(.+)$", s)
        if m:
            labels.append(m.group(1))
        if s.startswith("|") and s.count("|") >= 2:
            labels.extend(c.strip() for c in s.strip("|").split("|"))
        m = re.match(r"^(?:[-*+]\s+|\d+[.)]\s+)?([^:\n]{1,90}?):(?:\s|$)", s)
        if m:
            labels.append(m.group(1))
    labels.extend(m.group(1) for m in re.finditer(r"\*\*(.+?)\*\*", text))
    return [l.strip() for l in labels if l.strip()]


def yaml_job_ids(text):
    """Job ids from the fenced YAML the model wrote. Deliberately regex-based:
    the harness must not need PyYAML, and a partially-written workflow should
    still yield its job ids."""
    ids, in_jobs, indent = [], False, None
    for raw in text.splitlines():
        if re.match(r"^\s*```", raw):
            continue
        if re.match(r"^jobs:\s*$", raw):
            in_jobs, indent = True, None
            continue
        if not in_jobs:
            continue
        if raw.strip() and not raw.startswith((" ", "\t")):
            in_jobs = False
            continue
        m = re.match(r"^(\s+)([A-Za-z0-9_][A-Za-z0-9_-]*):\s*$", raw)
        if m:
            width = len(m.group(1))
            if indent is None:
                indent = width
            if width == indent and m.group(2) not in ids:
                ids.append(m.group(2))
    return ids


# --------------------------------------------------------------------------
# Axes
# --------------------------------------------------------------------------

SHAPE_CUE = re.compile(r"\bshapes?\b|\bclassification\b|\bclassified\b"
                       r"|\brepository type\b", re.IGNORECASE)


def grade_shape(text, scenario, vocab):
    lines = text.splitlines()
    block = []
    for i, line in enumerate(lines):
        if SHAPE_CUE.search(line):
            block.extend(lines[i:i + 5])
    scope, source = "\n".join(block), "shape-block"
    found = {s for s, pat in SHAPE_PROBES.items()
             if re.search(pat, scope, re.IGNORECASE)}
    if not found:
        scope, source = text, "whole-response"
        found = {s for s, pat in SHAPE_PROBES.items()
                 if re.search(pat, scope, re.IGNORECASE)}

    expected = scenario.get("expected_shape")
    declared = sorted(found)
    if not found:
        score, note = 0.0, "no repository shape declared"
    elif len(found) > 1:
        score, note = 0.25, "ambiguous: %d shapes declared" % len(found)
    elif expected is None:
        score, note = 1.0, "one shape declared; fixture pins none"
    elif declared[0] == expected:
        score, note = 1.0, "matches expected"
    else:
        score, note = 0.5, "classified, but expected %r" % expected
    return {"score": score, "declared": declared, "expected": expected,
            "source": source, "hinted": scenario.get("shape_hinted", False),
            "note": note}


def grade_parity(text, scenario, vocab):
    expected_paths = scenario.get("expected_execution_paths") or {}
    jobs = list(expected_paths)
    for j in scenario.get("expected_jobs") or []:
        if j not in jobs:
            jobs.append(j)
    for j in yaml_job_ids(text):
        if j not in jobs:
            jobs.append(j)

    if not jobs:
        return {"score": 0.0, "jobs": {},
                "note": "no job names to classify (no YAML jobs: block, no "
                        "fixture job list)"}

    lines = text.splitlines()
    detail, total = {}, 0.0
    for job in jobs:
        jre = re.compile(r"(?<![A-Za-z0-9_-])%s(?![A-Za-z0-9_-])"
                         % re.escape(job), re.IGNORECASE)
        labels = []
        for line in lines:
            if not jre.search(line):
                continue
            for p in vocab.paths:
                if re.search(r"(?<![A-Za-z0-9_-])%s(?![A-Za-z0-9_-])"
                             % re.escape(p), line, re.IGNORECASE):
                    labels.append(p)
        labels = sorted(set(labels))
        want = expected_paths.get(job)
        if len(labels) == 1 and (want is None or labels[0] == want):
            s, note = 1.0, "classified"
        elif len(labels) == 1:
            s, note = 0.4, "classified %r, expected %r" % (labels[0], want)
        elif len(labels) > 1:
            s, note = 0.2, "ambiguous: %d path labels on the same line" % len(labels)
        else:
            s, note = 0.0, "no execution path label"
        detail[job] = {"labels": labels, "expected": want,
                       "score": s, "note": note}
        total += s
    return {"score": total / len(jobs), "jobs": detail,
            "note": "%d job(s) checked" % len(jobs)}


def grade_contract(text, scenario, vocab):
    labels = label_strings(text)
    has_path_label = any(
        re.search(r"(?<![A-Za-z0-9_-])%s(?![A-Za-z0-9_-])" % re.escape(p),
                  text, re.IGNORECASE)
        for p in vocab.paths)

    present, missing = [], []
    for key, (_anchor, pat) in CONTRACT_PROBES.items():
        hit = any(re.search(pat, l, re.IGNORECASE) for l in labels)
        if key == "jobs_and_paths":
            hit = hit and has_path_label
        (present if hit else missing).append(key)

    required = []
    for field in scenario.get("expected_output_fields", []):
        key = FIELD_ALIASES[field.lower()]
        if key not in required:
            required.append(key)
    required_missing = [k for k in required if k in missing]

    return {"score": len(present) / len(CONTRACT_PROBES),
            "present": sorted(present), "missing": sorted(missing),
            "required": sorted(required),
            "required_missing": sorted(required_missing),
            "note": "%d/%d contract items in a label position"
                    % (len(present), len(CONTRACT_PROBES))}


VALIDATION_CMD = re.compile(
    r"\bactionlint\b|\byq\s+eval\b|\bdiscover_ci_needs\.sh\b|\bgo\s+test\b"
    r"|\bgo\s+build\b|\bgo\s+vet\b|\bmake\s+\S+|\bgolangci-lint\b"
    r"|\bpython3?\s+-c\b|\bgh\s+workflow\b", re.IGNORECASE)
VALIDATION_VERDICT = re.compile(
    r"\bpass(?:ed|ing)?\b|\bfail(?:ed|ing|ure)?\b|\bno (?:errors|issues|findings)\b"
    r"|\b0 (?:errors|issues|findings)\b|\bclean\b|\bexit (?:code )?[0-9]+\b",
    re.IGNORECASE)


def grade_integrity(text, scenario, vocab):
    lit = vocab.integrity_literal
    lit_re = re.compile(re.escape(lit), re.IGNORECASE)
    m = lit_re.search(text)
    if m:
        lines = text.splitlines()
        idx = text[:m.start()].count("\n")
        # Generous window: the gate asks for the literal, the reason AND the
        # exact commands to run next, which routinely spans a paragraph and a
        # fenced block. A tight window graded the formatting, not the answer.
        near = "\n".join(lines[max(0, idx - 3):idx + 13])
        reason = bool(re.search(r"\breasons?\b|\bbecause\b|\bnot (?:available|"
                                r"installed|present)\b|\bunavailable\b|\bno "
                                r"\S+ (?:binary|installed)\b|\bcannot\b",
                                near, re.IGNORECASE))
        cmds = bool(VALIDATION_CMD.search(near)) or "```" in near
        return {"score": 0.5 + 0.25 * reason + 0.25 * cmds,
                "mode": "declared-not-run", "literal": True,
                "reason": reason, "next_commands": cmds,
                "note": "literal %r present (reason=%s, next-commands=%s)"
                        % (lit, reason, cmds)}

    claim_lines = [l for l in text.splitlines()
                   if re.search(r"\bvalidat", l, re.IGNORECASE)]
    scope = "\n".join(claim_lines)
    cmd = bool(VALIDATION_CMD.search(scope))
    verdict = bool(VALIDATION_VERDICT.search(scope))
    if claim_lines and cmd and verdict:
        return {"score": 1.0, "mode": "declared-ran", "literal": False,
                "reason": True, "next_commands": cmd,
                "note": "validation claimed with a named command and a verdict"}
    return {"score": 0.0, "mode": "unsubstantiated", "literal": False,
            "reason": False, "next_commands": cmd,
            "note": "no %r literal and no command+verdict evidence — the gate "
                    "forbids claiming validation that did not run" % lit}


def grade_treatment(text, vocab):
    # Whitespace-tolerant: a gate name that wrapped across a line break is
    # still the gate name. A plain substring test scored a correct, treated
    # response as untreated purely because prose reflow split
    # "Repository Shape / Gate" over two lines.
    gates = sorted({
        g for g in vocab.gate_names
        if re.search(r"\s+".join(re.escape(w) for w in g.split()),
                     text, re.IGNORECASE)})
    paths = sorted({p for p in vocab.paths
                    if re.search(r"(?<![A-Za-z0-9_-])%s(?![A-Za-z0-9_-])"
                                 % re.escape(p), text, re.IGNORECASE)})
    ok = len(gates) >= 2 and len(paths) >= 1
    return {"ok": ok, "gate_names": gates, "path_labels": paths,
            "note": "%d/5 gate names, %d/3 execution-path labels"
                    % (len(gates), len(paths))}


AXES = ("shape", "parity", "contract", "integrity")


def grade(scenario, response_path, vocab):
    text = load_response(response_path)
    axes = {
        "shape": grade_shape(text, scenario, vocab),
        "parity": grade_parity(text, scenario, vocab),
        "contract": grade_contract(text, scenario, vocab),
        "integrity": grade_integrity(text, scenario, vocab),
    }
    treatment = grade_treatment(text, vocab)
    passed = (
        axes["shape"]["score"] >= 1.0
        and axes["parity"]["score"] >= 1.0
        and not axes["contract"]["required_missing"]
        and axes["integrity"]["score"] >= 1.0
    )
    return {"scenario": scenario["id"], "axes": axes,
            "treatment": treatment, "pass": passed}


def print_result(result, prefix="  "):
    for name in AXES:
        a = result["axes"][name]
        extra = ""
        if name == "shape":
            extra = " declared=%s" % (a["declared"] or "-")
            if a["hinted"]:
                extra += " [shape-hinted by the fixture situation]"
        elif name == "parity":
            extra = " " + ", ".join(
                "%s=%s" % (j, d["labels"] or "-")
                for j, d in sorted(result["axes"]["parity"]["jobs"].items()))
        elif name == "contract":
            extra = " missing=%s" % (a["missing"] or "-")
            if a["required_missing"]:
                extra += " REQUIRED-MISSING=%s" % a["required_missing"]
        print("%s%-10s %.2f  %s%s" % (prefix, name, a["score"], a["note"], extra))
    t = result["treatment"]
    print("%s%-10s %s  %s" % (prefix, "treatment",
                              "OK " if t["ok"] else "ABSENT", t["note"]))
    print("%s%-10s %s" % (prefix, "verdict", "PASS" if result["pass"] else "FAIL"))


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def cmd_derive(args, vocab):
    scenarios = derive(args.golden, vocab)
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for s in scenarios:
        (out / ("%s.json" % s["id"])).write_text(
            json.dumps(s, indent=2, ensure_ascii=False), encoding="utf-8")
    print("derived %d scenarios from %s" % (len(scenarios), args.golden))
    for s in scenarios:
        print("  %-34s %-22s %s%s" % (
            s["id"], s["scenario_type"],
            s["expected_shape"] or "(shape not pinned)",
            "  [shape-hinted]" if s["shape_hinted"] else ""))
    return 0


def cmd_materialize(args, vocab):
    scenario = json.loads(pathlib.Path(args.scenario).read_text(encoding="utf-8"))
    materialize(scenario, args.repo)
    return 0


def cmd_prompt(args, vocab):
    scenario = json.loads(pathlib.Path(args.scenario).read_text(encoding="utf-8"))
    sys.stdout.write(scenario["prompt"])
    return 0


def cmd_grade(args, vocab):
    scenario = json.loads(pathlib.Path(args.scenario).read_text(encoding="utf-8"))
    result = grade(scenario, args.response, vocab)
    result["arm"] = args.arm
    if args.json:
        pathlib.Path(args.json).write_text(
            json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print_result(result)
    return 0 if result["pass"] else 1


def cmd_treatment(args, vocab):
    text = load_response(args.response)
    t = grade_treatment(text, vocab)
    if t["ok"]:
        print("  treatment  OK  %s" % t["note"])
        return 0
    print("setup: the with-skill arm shows NO evidence the skill was loaded.",
          file=sys.stderr)
    print("       %s" % t["note"], file=sys.stderr)
    print("       Gate names seen: %s; execution-path labels seen: %s"
          % (t["gate_names"] or "none", t["path_labels"] or "none"),
          file=sys.stderr)
    print("       An untreated with-skill arm is a second control arm: any A/B",
          file=sys.stderr)
    print("       number from it would be a bogus null result. Aborting as a",
          file=sys.stderr)
    print("       SETUP failure, NOT as a low score.", file=sys.stderr)
    return SETUP


RECORDING_META = re.compile(
    r"<!--\s*live-eval-recording\s*(.*?)-->", re.DOTALL)


def recording_meta(path):
    raw = pathlib.Path(path).read_text(encoding="utf-8")
    m = RECORDING_META.search(raw)
    if not m:
        raise SetupError(
            "%s has no <!-- live-eval-recording ... --> header; the replay "
            "corpus must declare which fixture and arm each response answers, "
            "or --dry-run would grade it against a scenario nobody chose"
            % path)
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    for key in ("fixture", "arm", "expect"):
        if key not in meta:
            raise SetupError("%s: recording header is missing %r" % (path, key))
    return meta


def cmd_meta(args, vocab):
    meta = recording_meta(args.response)
    if args.key:
        if args.key not in meta:
            raise SetupError("%s: no %r in recording header"
                             % (args.response, args.key))
        print(meta[args.key])
    else:
        print(json.dumps(meta, ensure_ascii=False))
    return 0


def cmd_compare(args, vocab):
    good = json.loads(pathlib.Path(args.good).read_text(encoding="utf-8"))
    bad = json.loads(pathlib.Path(args.bad).read_text(encoding="utf-8"))
    axes = [a.strip() for a in args.axes.split(",") if a.strip()]
    unknown = [a for a in axes if a not in AXES]
    if unknown:
        raise SetupError("unknown axis/axes %r" % unknown)

    print("  grader discrimination — recorded good vs recorded bad")
    print("  %-12s %8s %8s %8s  %s" % ("axis", "good", "bad", "delta", "verdict"))
    failures = []
    for name in AXES:
        g = good["axes"][name]["score"]
        b = bad["axes"][name]["score"]
        if name in axes:
            ok = (g - b) >= args.margin
            verdict = "discriminates" if ok else "NO DISCRIMINATION"
            if not ok:
                failures.append(
                    "%s: good %.2f - bad %.2f = %.2f < required margin %.2f"
                    % (name, g, b, g - b, args.margin))
        else:
            # A control axis: the two recordings differ ONLY in the axes under
            # test, so an unexpected move here means the grader is reacting to
            # length or tone rather than to the planted defect.
            ok = abs(g - b) < 1e-9
            verdict = "control (equal)" if ok else "CONTROL AXIS MOVED"
            if not ok:
                failures.append(
                    "%s is a control axis but moved: good %.2f vs bad %.2f — "
                    "the grader is responding to something other than the "
                    "planted defect" % (name, g, b))
        print("  %-12s %8.2f %8.2f %8.2f  %s" % (name, g, b, g - b, verdict))

    if failures:
        print("\n  grader discrimination check FAILED:")
        for f in failures:
            print("    - %s" % f)
        return 1
    print("\n  grader discriminates on %s and holds every other axis steady."
          % ", ".join(axes))
    return 0


def cmd_summarize(args, vocab):
    files = sorted(pathlib.Path(args.results).glob("*.json"))
    results = [json.loads(p.read_text(encoding="utf-8")) for p in files]
    print("=" * 66)
    print("  go-ci-workflow live eval — arm: %s" % args.arm)
    print("=" * 66)
    if not results:
        print("  no graded scenarios")
        return 0
    print("  %-12s %6s  %s" % ("axis", "mean", "per-scenario"))
    for name in AXES:
        scores = [r["axes"][name]["score"] for r in results]
        mean = sum(scores) / len(scores)
        print("  %-12s %6.2f  %s" % (
            name, mean, " ".join("%.2f" % s for s in scores)))
    treated = sum(1 for r in results if r["treatment"]["ok"])
    passed = sum(1 for r in results if r["pass"])
    print("  %-12s %6s  %d/%d scenarios show closed-vocabulary evidence"
          % ("treatment", "-", treated, len(results)))
    print("-" * 66)
    print("  scenarios graded: %d   passing: %d   failing: %d"
          % (len(results), passed, len(results) - passed))
    print("  A single blended number would hide which axis moved. Compare arms")
    print("  axis by axis: GO_CI_WORKFLOW_EVAL_ARM=without-skill re-runs the")
    print("  identical prompts with no skill installed.")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--skill-md", required=True)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("derive")
    p.add_argument("--golden", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(fn=cmd_derive)

    p = sub.add_parser("materialize")
    p.add_argument("--scenario", required=True)
    p.add_argument("--repo", required=True)
    p.set_defaults(fn=cmd_materialize)

    p = sub.add_parser("prompt")
    p.add_argument("--scenario", required=True)
    p.set_defaults(fn=cmd_prompt)

    p = sub.add_parser("grade")
    p.add_argument("--scenario", required=True)
    p.add_argument("--response", required=True)
    p.add_argument("--arm", default="with-skill")
    p.add_argument("--json")
    p.set_defaults(fn=cmd_grade)

    p = sub.add_parser("treatment")
    p.add_argument("--response", required=True)
    p.set_defaults(fn=cmd_treatment)

    p = sub.add_parser("meta")
    p.add_argument("--response", required=True)
    p.add_argument("--key")
    p.set_defaults(fn=cmd_meta)

    p = sub.add_parser("compare")
    p.add_argument("--good", required=True)
    p.add_argument("--bad", required=True)
    p.add_argument("--axes", required=True)
    p.add_argument("--margin", type=float, default=0.5)
    p.set_defaults(fn=cmd_compare)

    p = sub.add_parser("summarize")
    p.add_argument("--results", required=True)
    p.add_argument("--arm", default="with-skill")
    p.set_defaults(fn=cmd_summarize)

    args = ap.parse_args(argv)
    try:
        vocab = Vocab(args.skill_md)
    except SetupError as e:
        print("setup: %s" % e, file=sys.stderr)
        return SETUP
    try:
        return args.fn(args, vocab)
    except SetupError as e:
        print("setup: %s" % e, file=sys.stderr)
        return SETUP


if __name__ == "__main__":
    sys.exit(main())
