#!/usr/bin/env python3
"""Grade a documentation-update run against a scenario fixture.

Deterministic, no model in the loop. Takes the assistant's response text and the
repository as it stands after the run, and answers: was this update grounded in
the repository, and did it follow the skill's output contract?

The load-bearing check is `commands_exist`. A fabricated environment variable is
usually caught by a reader; an invented `make deploy` reads as authoritative and
is only caught by running it. Every wrapper invocation the document prints —
make, npm/pnpm/bun/yarn run, bare pnpm/yarn scripts, just, task — is therefore
checked against the repository's real targets. This list must track the
resolver's ladder in `discover_doc_scope.sh`; a wrapper the resolver can emit
but the grader cannot check is a hole a fabricated command walks through.

`commands_exist` answers "does this target exist". `commands_correct` answers
the separate question "is this the right command" — `npm run build` is wrong in
a pnpm repository even though `build` is a real script, and `go run ./cmd/nope`
is wrong even though nothing declares go targets.

`CHECKED` and `UNCHECKED` below state exactly which command families each check
covers. They are asserted against the implementation by
`test_forward_eval.py::test_declared_coverage_matches_the_implementation`,
because a docstring claiming more than the code does is how `cargo run --bin
does-not-exist` graded clean while the tests said native commands were covered.

Usage:
  grade_doc_update.py <scenario.json> <repo_dir> <response_file>
Exit:
  0 all checks passed
  1 one or more checks failed
  2 usage or setup error — never report this as a grading result
"""

import json
import re
import sys
from pathlib import Path


def make_targets(repo):
    for name in ("Makefile", "makefile", "GNUmakefile"):
        path = repo / name
        if path.exists():
            return {
                m.group(1)
                for m in re.finditer(
                    r"^([a-zA-Z0-9_][a-zA-Z0-9_.-]*)[ \t]*:",
                    path.read_text(encoding="utf-8", errors="replace"),
                    re.MULTILINE,
                )
            }
    return set()


def npm_scripts(repo):
    path = repo / "package.json"
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return set()
    scripts = data.get("scripts")
    return set(scripts) if isinstance(scripts, dict) else set()


def just_targets(repo):
    for name in ("justfile", "Justfile", ".justfile"):
        path = repo / name
        if path.exists():
            return {
                m.group(1)
                for m in re.finditer(
                    r"^([a-zA-Z0-9_][a-zA-Z0-9_.-]*)[ \t]*:",
                    path.read_text(encoding="utf-8", errors="replace"),
                    re.MULTILINE,
                )
            }
    return set()


def task_targets(repo):
    for name in ("Taskfile.yml", "Taskfile.yaml"):
        path = repo / name
        if not path.exists():
            continue
        out, inside = set(), False
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if re.match(r"^tasks:", line):
                inside = True
                continue
            if inside and re.match(r"^[a-zA-Z0-9_-]", line):
                inside = False
            m = re.match(r"^  ([a-zA-Z0-9_-]+):", line)
            if inside and m:
                out.add(m.group(1))
        return out
    return set()


# Every wrapper the discovery script can resolve to must also be checkable here,
# or a document can print `pnpm run deploy` / `task deploy` and still grade clean.
# Keeping this table next to the resolver's ladder is the point.
WRAPPER_PATTERNS = [
    (r"\bmake\s+([a-zA-Z0-9_.:-]+)", "make", "make"),
    (r"\bnpm\s+run\s+([a-zA-Z0-9_.:-]+)", "npm run", "scripts"),
    (r"\bpnpm\s+run\s+([a-zA-Z0-9_.:-]+)", "pnpm run", "scripts"),
    (r"\bbun\s+run\s+([a-zA-Z0-9_.:-]+)", "bun run", "scripts"),
    (r"\byarn\s+run\s+([a-zA-Z0-9_.:-]+)", "yarn run", "scripts"),
    (r"\bpnpm\s+(?!run\b|install\b|add\b|dlx\b)([a-zA-Z0-9_.:-]+)", "pnpm", "scripts"),
    (r"\byarn\s+(?!run\b|install\b|add\b|dlx\b)([a-zA-Z0-9_.:-]+)", "yarn", "scripts"),
    (r"\bjust\s+([a-zA-Z0-9_.:-]+)", "just", "just"),
    (r"\btask\s+([a-zA-Z0-9_.:-]+)", "task", "task"),
]


LOCKFILE_MANAGERS = [
    ("pnpm-lock.yaml", "pnpm"),
    ("yarn.lock", "yarn"),
    ("bun.lockb", "bun"),
    ("bun.lock", "bun"),
    ("package-lock.json", "npm"),
]


# What `commands_correct` actually verifies. Keep this honest: an entry here is
# a promise the test suite enforces.
CHECKED = {
    "package-manager-consistency": "npm/pnpm/yarn/bun invocation vs the lockfile",
    "go-package-path": "./… argument to go run|build|test must exist",
    "cargo-bin-target": "--bin NAME must be a declared [[bin]] or src/bin/NAME.rs",
    "script-path": "./x.sh, bash x.sh and sh x.sh must exist",
    "pytest-path": "a path argument to pytest must exist",
}

# Deliberately NOT verified. Listing them is the point: silence here is what
# turned an incomplete check into an overclaim.
UNCHECKED = {
    "maven-goal": "mvn goals come from plugins; not resolvable from the repo",
    "gradle-task": "tasks are defined dynamically in build scripts",
    "ci-provenance": "whether a documented command really appears in a workflow",
    "command-flags": "flag names and values beyond the paths named above",
}


def cargo_bin_targets(repo):
    names = set()
    manifest = repo / "Cargo.toml"
    if manifest.exists():
        text = manifest.read_text(encoding="utf-8", errors="replace")
        for block in re.findall(r"\[\[bin\]\](.*?)(?=\n\[|\Z)", text, re.DOTALL):
            m = re.search(r'name\s*=\s*"([^"]+)"', block)
            if m:
                names.add(m.group(1))
        m = re.search(r'^\s*\[package\](.*?)(?=\n\[|\Z)', text, re.DOTALL | re.MULTILINE)
        if m and (repo / "src" / "main.rs").exists():
            pkg = re.search(r'name\s*=\s*"([^"]+)"', m.group(1))
            if pkg:
                names.add(pkg.group(1))
    bin_dir = repo / "src" / "bin"
    if bin_dir.is_dir():
        names |= {f.stem for f in bin_dir.glob("*.rs")}
    return names


def detect_package_manager(repo):
    """The lockfile names the manager. Absent one, any manager is unprovable."""
    for lockfile, manager in LOCKFILE_MANAGERS:
        if (repo / lockfile).exists():
            return manager
    return None


def go_package_paths(doc_text):
    """`./...`-style package arguments to go run/build/test."""
    return re.findall(r"\bgo\s+(?:run|build|test)\s+(\./[^\s`)\]]*)", doc_text)


def read_docs(repo, doc_paths):
    out = {}
    for rel in doc_paths:
        path = repo / rel
        out[rel] = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
    return out


def grade(scenario, repo, response):
    """Return a list of (check_name, passed, detail)."""
    spec = scenario["grade"]
    docs = read_docs(repo, spec["doc_paths"])
    doc_text = "\n".join(docs.values())
    results = []

    def check(name, passed, detail=""):
        results.append((name, bool(passed), detail))

    missing = [b for b in spec["required_blocks"] if b.lower() not in response.lower()]
    check("required_blocks", not missing, f"missing: {missing}")

    mode = spec["expect_mode"]
    has_scorecard = bool(re.search(r"\bTotal:\s*\d+\s*/\s*12\b", response))
    if mode == "full":
        check("output_mode", has_scorecard, "full mode requires a 12-item scorecard total")
    else:
        check(
            "output_mode", not has_scorecard,
            "lightweight mode must not emit the 12-item scorecard",
        )

    uncited = [p for p in spec.get("must_cite", []) if p not in response]
    check("evidence_cited", not uncited, f"not cited: {uncited}")

    undocumented = [t for t in spec.get("must_document", []) if t not in doc_text]
    check("documented_facts", not undocumented, f"absent from docs: {undocumented}")

    fabricated = [t for t in spec.get("must_not_document", []) if t in doc_text]
    check("no_fabrication", not fabricated, f"present but absent from repo: {fabricated}")

    leaked = [t for t in spec.get("doc_must_not_contain", []) if t in doc_text]
    check("no_internal_labels", not leaked, f"internal markers leaked into docs: {leaked}")

    defined = {
        "make": make_targets(repo),
        "scripts": npm_scripts(repo),
        "just": just_targets(repo),
        "task": task_targets(repo),
    }
    bad_commands = []
    for pattern, label, source in WRAPPER_PATTERNS:
        for name in re.findall(pattern, doc_text):
            if name not in defined[source]:
                bad_commands.append(f"{label} {name}")
    check(
        "commands_exist", not bad_commands,
        f"documented but undefined in the repository: {sorted(set(bad_commands))}",
    )

    # A target that exists is not the same as a command that is correct.
    # `npm run build` is wrong in a pnpm repository even though `build` is a
    # real script, and `go run ./cmd/nope` is wrong even though `go run` needs
    # no target list at all.
    manager = detect_package_manager(repo)
    wrong_manager = []
    if manager:
        for other in ("npm", "pnpm", "yarn", "bun"):
            if other == manager:
                continue
            if re.search(rf"\b{other}\s+(run\s+)?[a-zA-Z0-9_.:-]+", doc_text):
                wrong_manager.append(other)
    missing_paths = [
        path for path in go_package_paths(doc_text)
        if "..." not in path and not (repo / path.lstrip("./")).exists()
    ]

    bins = cargo_bin_targets(repo)
    bad_bins = [
        name for name in re.findall(r"\bcargo\s+(?:run|build|test)[^\n]*?--bin\s+([\w.-]+)", doc_text)
        if name not in bins
    ]

    script_paths = re.findall(
        r"(?:^|\s)(?:bash\s+|sh\s+|)(\./[\w./-]+\.(?:sh|bash|py))\b", doc_text
    )
    script_paths += re.findall(r"\b(?:bash|sh)\s+([\w./-]+\.(?:sh|bash))\b", doc_text)
    missing_scripts = [
        s for s in script_paths if not (repo / s.lstrip("./")).exists()
    ]

    missing_pytest = [
        arg for arg in re.findall(r"\bpytest\s+([\w./-]+/[\w./-]*)", doc_text)
        if not (repo / arg.lstrip("./")).exists()
    ]

    detail = []
    if wrong_manager:
        detail.append(f"lockfile says {manager}, doc uses {sorted(set(wrong_manager))}")
    if missing_paths:
        detail.append(f"go package path does not exist: {sorted(set(missing_paths))}")
    if bad_bins:
        detail.append(f"cargo bin target not declared: {sorted(set(bad_bins))}")
    if missing_scripts:
        detail.append(f"script does not exist: {sorted(set(missing_scripts))}")
    if missing_pytest:
        detail.append(f"pytest path does not exist: {sorted(set(missing_pytest))}")
    check("commands_correct", not detail, "; ".join(detail))

    return results


def main(argv):
    if len(argv) != 4:
        print(__doc__.strip().splitlines()[-4], file=sys.stderr)
        print(
            "Usage: grade_doc_update.py <scenario.json> <repo_dir> <response_file>",
            file=sys.stderr,
        )
        return 2
    scenario_path, repo_dir, response_path = Path(argv[1]), Path(argv[2]), Path(argv[3])
    for path in (scenario_path, repo_dir, response_path):
        if not path.exists():
            print(f"error: missing {path}", file=sys.stderr)
            return 2

    scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
    response = response_path.read_text(encoding="utf-8", errors="replace")
    results = grade(scenario, repo_dir, response)

    failed = 0
    for name, passed, detail in results:
        mark = "PASS" if passed else "FAIL"
        print(f"{mark} {name}" + (f" — {detail}" if detail and not passed else ""))
        failed += not passed
    print(f"\n{len(results) - failed}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
