"""Execute EVERY Makefile recipe this skill ships, from wherever it lives.

The skill ships the same capability more than once: `fmt-check` appears in both
golden templates and in the quality guide, `generate-check` in a golden template
and the guide, `install-tools` in three places. An agent reads whichever
reference the task steers it to, so a fix applied to one copy leaves the others
generating defective Makefiles. That is not a documentation-tidiness problem —
it is the same shipped defect, still shipped.

Earlier rounds tested one hand-written copy of a recipe and grepped the other
documents for a marker string. Both halves fail open: the hand-written copy can
be correct while the shipped one is not (this happened — the untracked-file hole
in `generate-check` survived a green test that held a hand-copied recipe), and a
marker string proves nothing about behaviour.

So this module does not read recipes. It extracts every one of them out of every
shipped asset, builds a Makefile around it, and runs it against fixtures where
the right answer is known — a positive case that must pass and a negative case
that must fail. A new copy of a recipe pasted into any document is picked up
automatically; a new recipe with no contract is caught by the coverage test at
the bottom, which derives what is uncovered rather than counting what is.

Every negative case is additionally run under a plain POSIX `/bin/sh` with the
template's own `SHELL`/`.SHELLFLAGS` overridden. The templates exist to be
copied, and a recipe that only propagates failure because `pipefail` happens to
be set stops doing so the moment someone lifts it into a Makefile without the
header.

Requires `make`, `bash` and `git`; `go` for the cases that compile.
"""

import os
import pathlib
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[2]
GO = shutil.which("go")
GIT = shutil.which("git")

# Every asset a reader could copy a Makefile recipe out of.
SHIPPED_SOURCES = [
    "references/golden/simple-project.mk",
    "references/golden/complex-project.mk",
    "SKILL.md",
    "references/makefile-quality-guide.md",
    "references/pr-checklist.md",
]

# `name:` or `name: deps ## comment`, but never `name := value`.
_TARGET_RE = re.compile(r"^([A-Za-z0-9_.%-]+)[ \t]*:(?!=)[^=\n]*$")

# Defaults for variables a recipe references but whose definition lives outside
# the extracted block. Written with `?=` and placed after the source's own
# header so a real definition always wins.
FALLBACK_PRELUDE = """
GO ?= go
BIN_DIR ?= bin
VERSION ?= v0.0.0-test
COMMIT ?= deadbeef
DATE ?= 1970-01-01T00:00:00Z
LDFLAGS ?= -X main.version=$(VERSION) -X main.commit=$(COMMIT)
BUILD_FLAGS ?= -ldflags "$(LDFLAGS)"
COVERAGE_THRESHOLD ?= 70
COVER_MIN ?= 70
GOLANGCI_LINT_VERSION ?= v2.1.0
SWAG_VERSION ?= v1.16.4
IMAGE_NAME ?= fixture
IMAGE_TAG ?= test
"""

# Forces the recipe out of bash and into a plain POSIX shell.
POSIX_SHELL_OVERRIDE = "\nSHELL := /bin/sh\n.SHELLFLAGS := -c\n"


class Recipe:
    """One target's recipe, and where in the shipped assets it came from."""

    def __init__(self, source: str, block: int, name: str, header: str, text: str):
        self.source = source
        self.block = block
        self.name = name
        self.header = header
        self.text = text

    @property
    def origin(self) -> str:
        where = self.source if self.source.endswith(".mk") else f"{self.source} block {self.block}"
        return f"{self.name} @ {where}"

    @property
    def prereqs(self) -> list[str]:
        head = self.text.split("\n", 1)[0].split("##", 1)[0]
        return head.split(":", 1)[1].split()

    def makefile(self, prelude: str = "", posix_shell: bool = False) -> str:
        parts = [self.header, FALLBACK_PRELUDE, prelude]
        if posix_shell:
            parts.append(POSIX_SHELL_OVERRIDE)
        # Pull in prerequisites from the SAME document. `cover-check: cover` is
        # only half a contract without the target that produces the profile it
        # reads, and hand-writing a stand-in for it would be the hand-copied
        # recipe problem all over again.
        for dep in self._resolved_prereqs(prelude):
            parts.append("\n" + dep + "\n")
        parts.append("\n" + self.text + "\n")
        return "\n".join(parts)

    def _resolved_prereqs(self, prelude: str) -> list[str]:
        out, seen, queue = [], {self.name}, list(self.prereqs)
        while queue:
            name = queue.pop(0)
            if name in seen or f"\n{name}:" in f"\n{prelude}":
                continue
            seen.add(name)
            # Same block first, then anywhere in the same document: the quality
            # guide splits `cover` and `cover-check` across two fenced blocks,
            # and a reader assembling a Makefile takes both.
            pool = ([r for r in ALL_RECIPES
                     if r.name == name and r.source == self.source and r.block == self.block]
                    or [r for r in ALL_RECIPES if r.name == name and r.source == self.source])
            if pool:
                out.append(pool[0].text)
                queue.extend(pool[0].prereqs)
        return out


def _blocks(source: str) -> list[str]:
    text = (SKILL_DIR / source).read_text()
    if source.endswith(".mk"):
        return [text]
    return re.findall(r"```make\n(.*?)```", text, re.S)


def _split_block(block: str) -> tuple[str, list[tuple[str, str]]]:
    """Return (header, [(target_name, recipe_text), ...]) for one make block."""
    lines = block.split("\n")
    header_end = len(lines)
    recipes: list[tuple[str, str]] = []
    i = 0
    while i < len(lines):
        m = _TARGET_RE.match(lines[i])
        # A target line ending in a backslash is a CONTINUED DECLARATION, not a
        # rule — `.PHONY: a b \` wraps onto tab-indented lines that look exactly
        # like a recipe body, and used to be extracted as one.
        if (m and not lines[i].rstrip().endswith("\\")
                and i + 1 < len(lines) and lines[i + 1].startswith("\t")):
            if header_end == len(lines):
                header_end = i
            name = m.group(1)
            body = [lines[i]]
            i += 1
            while i < len(lines):
                if lines[i].startswith("\t"):
                    body.append(lines[i])
                    i += 1
                elif lines[i].strip() == "" and i + 1 < len(lines) and lines[i + 1].startswith("\t"):
                    body.append(lines[i])
                    i += 1
                else:
                    break
            recipes.append((name, "\n".join(body)))
        else:
            i += 1
    return "\n".join(lines[:header_end]), recipes


def shipped_recipes() -> list[Recipe]:
    out: list[Recipe] = []
    for source in SHIPPED_SOURCES:
        for bi, block in enumerate(_blocks(source)):
            header, recipes = _split_block(block)
            for name, text in recipes:
                out.append(Recipe(source, bi, name, header, text))
    return out


ALL_RECIPES = shipped_recipes()


def recipes_named(*names: str) -> list[Recipe]:
    return [r for r in ALL_RECIPES if r.name in names]


def run_make(project: Path, target: str, env_extra: dict | None = None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.setdefault("GOCACHE", str(project / ".gocache"))
    env.setdefault("GOMODCACHE", str(project / ".gomodcache"))
    env["GOFLAGS"] = "-mod=mod"
    # `install-tools` calls mktemp; point it somewhere writable so the positive
    # case measures the recipe rather than the sandbox. A SUBDIRECTORY, not the
    # project itself: Go ignores a go.mod that sits in the system temp root
    # ("warning: ignoring go.mod in system temp root"), which silently broke
    # every build in the fixture.
    tmp = project / ".tmp"
    tmp.mkdir(exist_ok=True)
    env["TMPDIR"] = str(tmp)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(["make", target], cwd=project, env=env,
                          capture_output=True, text=True, timeout=120)


class RecipeExtractionTests(unittest.TestCase):
    """The extractor is the load-bearing part: if it finds nothing, every
    contract below passes vacuously."""

    def test_every_shipped_source_yields_recipes(self):
        for source in SHIPPED_SOURCES:
            with self.subTest(source=source):
                found = [r for r in ALL_RECIPES if r.source == source]
                if source == "references/pr-checklist.md":
                    continue  # prose-only today; kept in the list so a future block is picked up
                self.assertTrue(found, f"no recipes extracted from {source}")

    def test_recipe_bodies_are_tab_indented_and_non_empty(self):
        for r in ALL_RECIPES:
            with self.subTest(origin=r.origin):
                body = r.text.split("\n")[1:]
                self.assertTrue(body, f"{r.origin} has a target line but no recipe")
                for line in body:
                    if line.strip():
                        self.assertTrue(line.startswith("\t"),
                                        f"{r.origin}: recipe line not tab-indented: {line!r}")


class _ContractCase(unittest.TestCase):
    """Shared fixture plumbing for the behavioural contracts."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.proj = Path(self._tmp.name)

    def _write(self, recipe: Recipe, prelude: str = "", posix_shell: bool = False) -> None:
        (self.proj / "Makefile").write_text(recipe.makefile(prelude, posix_shell))

    def assert_fails(self, recipe: Recipe, target: str, prelude: str = "",
                     env: dict | None = None, why: str = "", reset=None) -> None:
        """The negative case, run twice: as shipped, and under a plain POSIX sh.

        `reset` re-arms a fixture that its own first run consumes — a
        generate-check trigger, for instance, is a file the generator rewrites,
        so after one run the tree is already regenerated and the second run has
        nothing to detect. Without this the POSIX pass silently measured a
        different, already-clean fixture.
        """
        for posix in (False, True):
            if reset is not None:
                reset()
            self._write(recipe, prelude, posix_shell=posix)
            shell = "/bin/sh" if posix else "as shipped"
            out = run_make(self.proj, target, env)
            self.assertNotEqual(
                0, out.returncode,
                f"{recipe.origin} [{shell}] exited 0 although {why}\n"
                f"stdout: {out.stdout}\nstderr: {out.stderr}")

    def assert_passes(self, recipe: Recipe, target: str, prelude: str = "",
                      env: dict | None = None, why: str = "") -> None:
        self._write(recipe, prelude)
        out = run_make(self.proj, target, env)
        self.assertEqual(
            0, out.returncode,
            f"{recipe.origin} failed although {why}\nstdout: {out.stdout}\nstderr: {out.stderr}")


@unittest.skipUnless(GO, "requires the go toolchain")
class FmtCheckContractTests(_ContractCase):
    """`gofmt -l` reports unformatted files on stdout with status 0, and a parse
    error on stderr with status 2 and an EMPTY stdout. A recipe that reads only
    the output passes a tree that does not compile."""

    def setUp(self) -> None:
        super().setUp()
        (self.proj / "go.mod").write_text("module fixture\n\ngo 1.22\n")

    def test_clean_tree_passes(self):
        (self.proj / "ok.go").write_text("package fixture\n\nfunc G() {}\n")
        for r in recipes_named("fmt-check"):
            with self.subTest(origin=r.origin):
                self.assert_passes(r, "fmt-check", why="the tree is gofmt-clean")

    def test_unformatted_source_fails(self):
        (self.proj / "ok.go").write_text("package fixture\n\nfunc G() {}\n")
        (self.proj / "ugly.go").write_text("package fixture\nfunc   H( ) {  }\n")
        for r in recipes_named("fmt-check"):
            with self.subTest(origin=r.origin):
                self.assert_fails(r, "fmt-check", why="a file is unformatted")

    def test_unparsable_source_fails(self):
        (self.proj / "broken.go").write_text("package fixture\nfunc broken( { }\n")
        for r in recipes_named("fmt-check"):
            with self.subTest(origin=r.origin):
                self.assert_fails(
                    r, "fmt-check",
                    why="a file does not parse (gofmt exits 2 with empty stdout)")

    def test_unparsable_source_reports_which_file(self):
        """Exit code alone is not the whole contract.

        A live task run flagged this recipe as losing its diagnostic under
        `set -e` (the theory being that `out=$(gofmt …)` aborts before
        `status=$?` runs). Measured, it does not — the message survives. But the
        only assertion here was on the exit code, so the claim was unfalsifiable
        either way. Now it is checked.
        """
        (self.proj / "broken.go").write_text("package fixture\nfunc broken( { }\n")
        for r in recipes_named("fmt-check"):
            with self.subTest(origin=r.origin):
                self._write(r)
                out = run_make(self.proj, "fmt-check")
                combined = out.stdout + out.stderr
                self.assertIn("broken.go", combined,
                              f"{r.origin} failed without naming the file: {combined!r}")


class InstallToolsContractTests(_ContractCase):
    """`curl ... | sh` reports only sh's status, and sh given no input exits 0."""

    def _fake_curl(self, body: str) -> dict:
        bindir = self.proj / "fakebin"
        bindir.mkdir(exist_ok=True)
        (bindir / "curl").write_text(body)
        (bindir / "curl").chmod(0o755)
        # `install-tools` also runs `go install`; stub it so the contract under
        # test is the download, not network access to a module proxy.
        (bindir / "go").write_text('#!/bin/sh\ncase "$1" in env) echo "'
                                   + str(self.proj) + '";; *) exit 0;; esac\n')
        (bindir / "go").chmod(0o755)
        # BSD/macOS `mktemp` with no template ignores TMPDIR and uses the
        # Darwin per-user temp dir, which this sandbox denies — so the positive
        # case failed on the environment rather than on the recipe. The shim
        # delegates to the real mktemp with an explicit template, which BOTH
        # implementations honour, and is otherwise faithful: it creates a fresh
        # file with 0600 and prints its path.
        (bindir / "mktemp").write_text(
            '#!/bin/sh\n[ $# -gt 0 ] && exec /usr/bin/mktemp "$@"\n'
            'exec /usr/bin/mktemp "${TMPDIR:-/tmp}/tmp.XXXXXXXX"\n')
        (bindir / "mktemp").chmod(0o755)
        return {"PATH": f"{bindir}:{os.environ.get('PATH', '')}"}

    def _targets(self) -> list[Recipe]:
        return [r for r in recipes_named("install-tools") if "curl" in r.text]

    def test_download_failure_fails(self):
        env = self._fake_curl('#!/bin/sh\necho "curl: (22) 404" >&2\nexit 22\n')
        for r in self._targets():
            with self.subTest(origin=r.origin):
                self.assert_fails(r, "install-tools", env=env,
                                  why="the installer download failed (curl exit 22)")

    def test_empty_download_fails(self):
        """curl can exit 0 having written nothing — a proxy returning 204, a
        truncated transfer. Piping that into `sh` is a silent no-op."""
        env = self._fake_curl(
            '#!/bin/sh\nout=""\nwhile [ $# -gt 0 ]; do '
            'if [ "$1" = "-o" ]; then out="$2"; fi; shift; done\n'
            '[ -n "$out" ] && : > "$out"\nexit 0\n')
        for r in self._targets():
            with self.subTest(origin=r.origin):
                self.assert_fails(r, "install-tools", env=env,
                                  why="the download produced an empty installer")

    def test_successful_download_passes(self):
        env = self._fake_curl(
            '#!/bin/sh\nout=""\nwhile [ $# -gt 0 ]; do '
            'if [ "$1" = "-o" ]; then out="$2"; fi; shift; done\n'
            '[ -n "$out" ] && printf \'#!/bin/sh\\nexit 0\\n\' > "$out"\nexit 0\n')
        for r in self._targets():
            with self.subTest(origin=r.origin):
                self.assert_passes(r, "install-tools", env=env,
                                   why="the installer downloaded and ran cleanly")


@unittest.skipUnless(GIT, "requires git")
class GenerateCheckContractTests(_ContractCase):
    """`git status --porcelain` prints the same `?? path` line whatever an
    untracked file contains, and `git diff` skips untracked files, so comparing
    those two strings before and after cannot see a rewritten untracked file."""

    GENERATE = "generate:\n\t@%s\n"

    def setUp(self) -> None:
        super().setUp()
        subprocess.run(["git", "init", "-q", "."], cwd=self.proj, check=True)
        subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=self.proj, check=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=self.proj, check=True)
        (self.proj / "tracked.txt").write_text("base\n")
        subprocess.run(["git", "add", "tracked.txt"], cwd=self.proj, check=True)
        subprocess.run(["git", "commit", "-qm", "init"], cwd=self.proj, check=True)

    def _prelude(self, generate_cmd: str) -> str:
        return self.GENERATE % generate_cmd

    def test_noop_generator_passes(self):
        for r in recipes_named("generate-check"):
            with self.subTest(origin=r.origin):
                self.assert_passes(r, "generate-check", self._prelude("true"),
                                   why="the generator changed nothing")

    def test_rewritten_tracked_file_fails(self):
        def reset():
            (self.proj / "tracked.txt").write_text("base\n")
        for r in recipes_named("generate-check"):
            with self.subTest(origin=r.origin):
                self.assert_fails(
                    r, "generate-check",
                    self._prelude("printf 'regenerated\\\\n' > tracked.txt"),
                    why="the generator rewrote a tracked file", reset=reset)

    def test_rewritten_untracked_file_fails(self):
        def reset():
            (self.proj / "gen_out.txt").write_text("generated v1\n")
        for r in recipes_named("generate-check"):
            with self.subTest(origin=r.origin):
                self.assert_fails(
                    r, "generate-check",
                    self._prelude("printf 'generated v2\\\\n' > gen_out.txt"),
                    why="the generator rewrote an already-untracked file", reset=reset)

    def test_failing_generator_fails(self):
        for r in recipes_named("generate-check"):
            with self.subTest(origin=r.origin):
                self.assert_fails(r, "generate-check",
                                  self._prelude("exit 1"),
                                  why="the generator itself failed")

    def test_preexisting_unrelated_dirt_is_not_flagged(self):
        """The other half of the contract, and the reason the check compares
        before/after instead of just asking whether the tree is clean: a
        developer's unrelated local edit must not be reported as stale codegen,
        or the target cries wolf and gets bypassed."""
        (self.proj / "tracked.txt").write_text("locally edited, nothing to do with codegen\n")
        (self.proj / "scratch.txt").write_text("untracked scratch file\n")
        for r in recipes_named("generate-check"):
            with self.subTest(origin=r.origin):
                self.assert_passes(r, "generate-check", self._prelude("true"),
                                   why="the dirt predates the generator and it changed nothing")

    def test_preexisting_deletion_with_a_noop_generator_passes(self):
        """`git ls-files --modified` lists DELETED files too.

        With `[ -f "$f" ] && echo …` as the loop body's last command, a deleted
        file makes the body exit non-zero, which becomes the `while`'s status,
        the pipeline's status and the snapshot function's status — and `set -e`
        then fails the check. One unrelated pre-existing deletion made every
        repo report stale codegen. The fix is an explicit `if`; the deletion is
        still visible because `git status --porcelain` reports it in both
        snapshots, and a deletion the generator CAUSES still differs.
        """
        (self.proj / "zzz_last.txt").write_text("committed\n")
        subprocess.run(["git", "add", "zzz_last.txt"], cwd=self.proj, check=True)
        subprocess.run(["git", "commit", "-qm", "add"], cwd=self.proj, check=True)
        (self.proj / "zzz_last.txt").unlink()
        for r in recipes_named("generate-check"):
            with self.subTest(origin=r.origin):
                self.assert_passes(r, "generate-check", self._prelude("true"),
                                   why="the deletion predates the generator, which changed nothing")

    def test_a_deletion_caused_by_the_generator_fails(self):
        """The other side of the same case — ignoring pre-existing deletions
        must not mean ignoring deletions."""
        def reset():
            (self.proj / "victim.txt").write_text("v1\n")
            subprocess.run(["git", "add", "victim.txt"], cwd=self.proj, check=True)
            subprocess.run(["git", "commit", "-qm", "victim", "--allow-empty"],
                           cwd=self.proj, check=True)
        for r in recipes_named("generate-check"):
            with self.subTest(origin=r.origin):
                self.assert_fails(r, "generate-check", self._prelude("rm -f victim.txt"),
                                  why="the generator deleted a tracked file", reset=reset)

    def test_change_to_an_already_dirty_tracked_file_is_detected(self):
        """`git status --porcelain` prints ` M tracked.txt` both before and
        after, so status alone cannot see this one either — the diff half of
        the snapshot is what catches it."""
        def reset():
            (self.proj / "tracked.txt").write_text("locally edited\n")
        for r in recipes_named("generate-check"):
            with self.subTest(origin=r.origin):
                self.assert_fails(
                    r, "generate-check",
                    self._prelude("printf 'more\\\\n' >> tracked.txt"),
                    why="an already-modified file was modified again", reset=reset)


# Every `for x in $(VAR)` loop the shipped assets contain, with a fixture whose
# FIRST item fails and whose LAST item succeeds. That ordering is the whole
# point: a loop's exit status is its last iteration's, so a fixture that fails
# on the last item passes whether or not the recipe propagates anything.
LOOP_FIXTURES = {
    "PLATFORMS": "PLATFORMS := linux/nosucharch linux/amd64\n",
    "BINARIES": "BINARIES := broken:cmd/broken fine:cmd/fine\n",
    "MODULES": "MODULES := broken-mod fine-mod\n",
}
_LOOP_VAR_RE = re.compile(r"for\s+\w+\s+in\s+\$\((\w+)\)")


def loop_recipes() -> list[tuple[Recipe, str]]:
    out = []
    for r in ALL_RECIPES:
        for var in _LOOP_VAR_RE.findall(r.text):
            out.append((r, var))
    return out


@unittest.skipUnless(GO, "requires the go toolchain")
class LoopFailurePropagationTests(_ContractCase):
    """A shell `for` loop's status is its LAST iteration's, so a broken first
    item is masked by a working second one."""

    def setUp(self) -> None:
        super().setUp()
        (self.proj / "go.mod").write_text("module fixture\n\ngo 1.22\n")
        for d, src in (("cmd/api", "package main\n\nfunc main() {}\n"),
                       ("cmd/broken", "package main\nfunc main( { }\n"),
                       ("cmd/fine", "package main\n\nfunc main() {}\n")):
            (self.proj / d).mkdir(parents=True)
            (self.proj / d / "main.go").write_text(src)
        for mod, src in (("broken-mod", "package m\nfunc F( { }\n"),
                         ("fine-mod", "package m\n\nfunc F() {}\n")):
            (self.proj / mod).mkdir()
            (self.proj / mod / "go.mod").write_text(f"module example.com/{mod}\n\ngo 1.22\n")
            (self.proj / mod / "m.go").write_text(src)
        # A linter that fails only in the first module, so the loop's own
        # propagation — not a missing binary — decides the outcome.
        bindir = self.proj / "fakebin"
        bindir.mkdir()
        (bindir / "golangci-lint").write_text(
            '#!/bin/sh\ncase "$PWD" in *broken-mod*) echo "lint failure" >&2; exit 1;; esac\nexit 0\n')
        (bindir / "golangci-lint").chmod(0o755)
        self.env = {"PATH": f"{bindir}:{os.environ.get('PATH', '')}"}

    def test_every_loop_variable_has_a_fixture(self):
        """A new loop over a variable nobody fixtured would otherwise iterate
        zero times and pass."""
        seen = {var for _, var in loop_recipes()}
        self.assertTrue(seen, "no loops found — the loop detector matched nothing")
        missing = seen - set(LOOP_FIXTURES)
        self.assertFalse(missing, f"loop variables with no first-fails fixture: {sorted(missing)}")

    def test_first_item_failure_fails_the_target(self):
        cases = loop_recipes()
        self.assertTrue(cases, "no loop recipes extracted")
        for recipe, var in cases:
            with self.subTest(origin=recipe.origin, var=var):
                self.assert_fails(recipe, recipe.name, LOOP_FIXTURES[var], env=self.env,
                                  why=f"the first {var} item fails and a later one succeeds")

    def test_all_items_succeeding_passes(self):
        """The positive half — without it, a recipe that always fails would
        satisfy the negative case above."""
        good = {"PLATFORMS": "PLATFORMS := linux/amd64 linux/arm64\n",
                "BINARIES": "BINARIES := fine:cmd/fine\n",
                "MODULES": "MODULES := fine-mod\n"}
        for recipe, var in loop_recipes():
            with self.subTest(origin=recipe.origin, var=var):
                self.assert_passes(recipe, recipe.name, good[var], env=self.env,
                                   why=f"every {var} item succeeds")


@unittest.skipUnless(GO, "requires the go toolchain")
class AggregateEmptyListTests(_ContractCase):
    """An aggregate target whose input list comes back empty must fail. Zero
    iterations exiting 0 reads as 'every module passed' when what actually
    happened is that discovery broke."""

    def test_empty_module_list_fails(self):
        for recipe, var in loop_recipes():
            if var != "MODULES":
                continue
            with self.subTest(origin=recipe.origin):
                self.assert_fails(recipe, recipe.name, "MODULES :=\n",
                                  why="the module list is empty")


class RecipeContractCoverageTests(unittest.TestCase):
    """Every shipped recipe, COPY BY COPY, must fall into one accounted-for
    category — and each category's claim is itself checked.

    The previous version of this table asserted in prose that `cover-check` and
    `check-tools` were "covered by GoldenMakefileExecutionTests". Neither was:
    that class has no threshold test and no tool-presence test. A claim of
    coverage that nothing verifies is worse than no claim, because it stops the
    next reader from looking. So the categories below are checked, not asserted:
    a "single command" claim is rejected if the recipe composes commands, and a
    "covered by X" claim is rejected if class X does not exist or never
    mentions the recipe.
    """

    # Run against a positive and a negative fixture, every copy, in this module.
    CONTRACTED = {"fmt-check", "install-tools", "generate-check", "cover-check",
                  "check-tools", "lint", "swagger", "build-all-platforms",
                  "build-linux", "test-all", "lint-all"}

    # Claimed to be exercised by a class elsewhere in the suite.
    COVERED_BY = {
        "help": ("test_executable_assets", "GoldenMakefileExecutionTests"),
        "build-api": ("test_executable_assets", "RealBuildTests"),
        "clean": ("test_executable_assets", "CleanSafetyTests"),
        "version": ("test_executable_assets", "RealBuildTests"),
    }

    # No shell composition on any line, so make propagates each command's status
    # directly and there is no status to swallow. Verified structurally below.
    SINGLE_COMMAND_OK = {
        "fmt", "tidy", "test", "test-norace", "test-short", "test-integration",
        "bench", "generate", "build-consumer-sync", "build-consumer-notify",
        "build-cron-cleanup", "build-migrate", "run-api", "run-consumer-sync",
        "run-consumer-notify", "run-cron-cleanup", "run-migrate",
    }

    # Genuinely not exercised here, each with the reason. No test-class claims.
    DECLARED = {
        "cover": "the only pipeline is the summary print on its own recipe line; "
                 "the test run that can fail is a separate line whose status make "
                 "propagates. Asserted below.",
        "docker-build": "needs a docker daemon",
        "docker-push": "needs a registry",
    }

    COMPOSITION = ("$$(", "|", "&&", "||", ";", "for ")

    def _category(self, r: Recipe) -> str | None:
        if _LOOP_VAR_RE.search(r.text):
            return "loop-contract"
        if r.name in self.CONTRACTED:
            return "contract"
        if not any(tok in line for line in r.text.split("\n")[1:] for tok in self.COMPOSITION):
            return "single-command"
        if r.name in self.COVERED_BY:
            return "covered-by"
        if r.name in self.DECLARED:
            return "declared"
        return None

    def test_no_shipped_recipe_is_unaccounted_for(self):
        orphans = [r.origin for r in ALL_RECIPES if self._category(r) is None]
        self.assertFalse(
            orphans,
            "shipped recipes with no contract, no structural justification and no "
            f"declared reason: {orphans}")

    def test_single_command_claims_hold(self):
        """Reject the claim if the recipe actually composes commands."""
        for r in ALL_RECIPES:
            if r.name not in self.SINGLE_COMMAND_OK:
                continue
            with self.subTest(origin=r.origin):
                for line in r.text.split("\n")[1:]:
                    for tok in self.COMPOSITION:
                        self.assertNotIn(
                            tok, line,
                            f"{r.origin} is listed as a single command but composes with {tok!r}: "
                            f"{line.strip()!r} — give it a contract instead")

    @staticmethod
    def _class_source(module_name: str, class_name: str) -> str | None:
        """Read the sibling test file rather than importing it.

        `importlib.import_module("test_executable_assets")` works under
        `python -m unittest` and fails under this repo's pytest, which runs
        with `--import-mode=importlib` and does not put the test directory on
        sys.path. Reading the file has no such dependency, and does not
        re-execute a module whose import side effects include spawning `go`.
        """
        path = pathlib.Path(__file__).with_name(f"{module_name}.py")
        if not path.exists():
            return None
        lines = path.read_text().splitlines()
        for i, line in enumerate(lines):
            if line.startswith(f"class {class_name}(") or line.startswith(f"class {class_name}:"):
                body = [line]
                for nxt in lines[i + 1:]:
                    if nxt and not nxt[0].isspace():
                        break
                    body.append(nxt)
                return "\n".join(body)
        return None

    def test_covered_by_claims_resolve_to_a_real_test(self):
        for name, (module_name, class_name) in self.COVERED_BY.items():
            with self.subTest(recipe=name):
                self.assertTrue(recipes_named(name), f"{name} is no longer shipped")
                source = self._class_source(module_name, class_name)
                self.assertIsNotNone(
                    source, f"{module_name}.{class_name} does not exist")
                self.assertIn(name, source,
                              f"{class_name} never mentions {name!r} — the coverage claim is empty")

    def test_covers_only_recipe_line_pipeline_claim(self):
        """`cover`'s exemption rests on the failing command being on its own
        line; check that rather than trusting the sentence."""
        for r in recipes_named("cover"):
            with self.subTest(origin=r.origin):
                lines = [l for l in r.text.split("\n")[1:] if l.strip()]
                self.assertNotIn("|", lines[0],
                                 f"{r.origin}: the test run must not be inside a pipeline")

    def test_no_stale_entries(self):
        shipped = {r.name for r in ALL_RECIPES}
        listed = (self.CONTRACTED | set(self.COVERED_BY) | self.SINGLE_COMMAND_OK
                  | set(self.DECLARED))
        stale = listed - shipped
        self.assertFalse(stale, f"listed but no longer shipped: {sorted(stale)}")

    def test_contracted_recipes_are_actually_reached(self):
        for name in self.CONTRACTED:
            with self.subTest(recipe=name):
                self.assertTrue(recipes_named(name), f"no shipped recipe named {name}")


class DuplicatedCapabilityTests(unittest.TestCase):
    """Where the same target is shipped in more than one document, the copies
    must not diverge on the parts that decide pass/fail."""

    #  target -> substrings every copy must contain, and why.
    INVARIANTS = {
        "fmt-check": [("2>&1", "gofmt's parse error goes to stderr"),
                      ("exit", "must exit non-zero, not just print")],
        "generate-check": [("hash-object", "porcelain cannot see untracked content"),
                           ("--others", "untracked files must be in the snapshot")],
        "install-tools": [("-o", "download to a file rather than piping into sh")],
    }

    def test_all_copies_share_the_deciding_construct(self):
        for name, invariants in self.INVARIANTS.items():
            copies = recipes_named(name)
            self.assertGreaterEqual(len(copies), 2, f"{name}: expected at least two copies")
            for r in copies:
                for needle, why in invariants:
                    with self.subTest(origin=r.origin, needle=needle):
                        self.assertIn(needle, r.text, f"{r.origin} is missing {needle!r} — {why}")


@unittest.skipUnless(GO, "requires the go toolchain")
class CoverCheckContractTests(_ContractCase):
    """The coverage gate must fail below its threshold and pass above it.

    This class exists because the exemption table below used to claim
    `cover-check` was "covered by GoldenMakefileExecutionTests" — which has no
    threshold test at all. A written claim of coverage is not coverage.

    The fixture is a real module at a known coverage level rather than a stubbed
    `go tool cover`, so the awk/bc parsing of the `total:` line is under test too
    — that parsing is where the fragile-gsub defect lived historically.
    """

    def setUp(self) -> None:
        super().setUp()
        (self.proj / "go.mod").write_text("module fixture\n\ngo 1.22\n")
        # Two statements, one covered: 50%.
        (self.proj / "lib.go").write_text(
            "package fixture\n\nfunc Covered() int {\n\treturn 1\n}\n\n"
            "func Uncovered() int {\n\treturn 2\n}\n")
        (self.proj / "lib_test.go").write_text(
            "package fixture\n\nimport \"testing\"\n\n"
            "func TestCovered(t *testing.T) {\n\tif Covered() != 1 {\n\t\tt.Fatal()\n\t}\n}\n")

    def test_coverage_below_the_threshold_fails(self):
        for r in recipes_named("cover-check"):
            with self.subTest(origin=r.origin):
                self.assert_fails(r, "cover-check", "COVER_MIN := 90\nCOVERAGE_THRESHOLD := 90\n",
                                  why="coverage is 50%, below the 90% threshold")

    def test_coverage_above_the_threshold_passes(self):
        for r in recipes_named("cover-check"):
            with self.subTest(origin=r.origin):
                self.assert_passes(r, "cover-check", "COVER_MIN := 10\nCOVERAGE_THRESHOLD := 10\n",
                                   why="coverage is 50%, above the 10% threshold")


class ToolPresenceGuardContractTests(_ContractCase):
    """A missing tool must stop the target, not be reported and skipped.

    Covers every recipe that guards on a tool being installed — `check-tools`,
    `lint`, `swagger` — because they share one shape and one failure mode. The
    guarded tool is READ OUT OF EACH RECIPE rather than assumed: a fixture that
    hides `golangci-lint` proves nothing about `swagger`, which guards `swag`,
    and a first version of this class passed it a PATH that still contained the
    very tool it was supposed to be missing.

    For a recipe guarding several tools, the fixture hides the FIRST and
    supplies the rest — a loop that reports each missing tool but never sets a
    failure flag exits with the last iteration's status, which is success.
    """

    GUARDED = ("check-tools", "lint", "swagger")

    @staticmethod
    def _tools(recipe: Recipe) -> list[str]:
        found: list[str] = []
        for m in re.finditer(r"for\s+\w+\s+in\s+([a-zA-Z0-9_.\- ]+?);\s*do", recipe.text):
            found.extend(m.group(1).split())
        for m in re.finditer(r"command -v \$*\{?(\w[\w.-]*)\}?", recipe.text):
            name = m.group(1)
            if name not in ("tool",) and name not in found:
                found.append(name)
        return found

    def _path_with(self, present: list[str]) -> dict:
        bindir = self.proj / "fakebin"
        if bindir.exists():
            shutil.rmtree(bindir)
        bindir.mkdir()
        for tool in present:
            (bindir / tool).write_text("#!/bin/sh\nexit 0\n")
            (bindir / tool).chmod(0o755)
        # `SHELL := bash` in the golden headers is resolved through PATH, so the
        # real bash is linked in here rather than left to a directory that also
        # holds the tools being deliberately hidden (/opt/homebrew/bin has both).
        real_bash = shutil.which("bash")
        if real_bash:
            (bindir / "bash").symlink_to(real_bash)
        return {"PATH": f"{bindir}:/usr/bin:/bin"}

    def test_every_guard_recipe_names_a_tool(self):
        """Guards the fixture: an empty tool list would make both cases vacuous."""
        recipes = recipes_named(*self.GUARDED)
        self.assertTrue(recipes, "no tool-presence guards found")
        for r in recipes:
            with self.subTest(origin=r.origin):
                self.assertTrue(self._tools(r), f"{r.origin}: no guarded tool detected")

    def test_missing_first_tool_fails(self):
        for r in recipes_named(*self.GUARDED):
            with self.subTest(origin=r.origin, tools=self._tools(r)):
                self.assert_fails(r, r.name, env=self._path_with(self._tools(r)[1:]),
                                  why=f"{self._tools(r)[0]} is missing")

    def test_all_tools_present_passes(self):
        for r in recipes_named(*self.GUARDED):
            with self.subTest(origin=r.origin):
                self.assert_passes(r, r.name, env=self._path_with(self._tools(r)),
                                   why="every guarded tool is on PATH")


@unittest.skipUnless(GO, "requires the go toolchain")
class ModuleListAgreementTests(unittest.TestCase):
    """The monorepo Makefile in SKILL.md and `discover_go_entrypoints.sh
    --modules` compute the same thing two ways, and cannot be merged into one:
    the script is a generation-time tool living in the skill directory, while
    the Makefile ships into the user's repo and has to stand alone there. So
    the two are held together by behaviour instead — same repo shapes, same
    answer.

    They had drifted. The script learned that `go env GOWORK` can print the
    literal string `off` and the Makefile did not, so on one monorepo the
    script listed both member modules and the Makefile listed none, silently.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = Path(self._tmp.name)
        self.script = SKILL_DIR / "scripts" / "discover_go_entrypoints.sh"
        header = [r for r in ALL_RECIPES if r.source == "SKILL.md" and r.name == "test-all"]
        self.assertTrue(header, "SKILL.md no longer ships a monorepo example")
        self.header = header[0].header

    def _module(self, rel: str, pkg: str) -> None:
        d = self.repo / rel if rel != "." else self.repo
        d.mkdir(parents=True, exist_ok=True)
        (d / "go.mod").write_text(f"module example.com/{pkg}\n\ngo 1.22\n")
        (d / f"{pkg}.go").write_text(f"package {pkg}\n\nfunc F() {{}}\n")

    def _env(self, extra: dict | None = None) -> dict:
        env = {**os.environ,
               "GOCACHE": str(self.repo / ".gocache"),
               "GOMODCACHE": str(self.repo / ".gomodcache")}
        if extra:
            env.update(extra)
        return env

    def _from_makefile(self, env_extra: dict | None = None) -> set:
        (self.repo / "Makefile").write_text(
            self.header + "\n\nprint-modules:\n\t@echo $(MODULES)\n")
        out = subprocess.run(["make", "print-modules"], cwd=self.repo, env=self._env(env_extra),
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(0, out.returncode, out.stderr)
        return {str(Path(self.repo / p).resolve()) for p in out.stdout.split()}

    def _from_script(self, env_extra: dict | None = None) -> set:
        out = subprocess.run(["bash", str(self.script), "--modules"], cwd=self.repo,
                             env=self._env(env_extra), capture_output=True, text=True, timeout=60)
        self.assertEqual(0, out.returncode, f"{out.stdout}{out.stderr}")
        return {str(Path(self.repo / p).resolve()) for p in out.stdout.split()}

    def _assert_agree(self, label: str, env_extra: dict | None = None) -> None:
        script, makefile = self._from_script(env_extra), self._from_makefile(env_extra)
        self.assertTrue(script, f"{label}: the script found no modules")
        self.assertEqual(script, makefile,
                         f"{label}: script and SKILL.md Makefile disagree\n"
                         f"script:   {sorted(script)}\nmakefile: {sorted(makefile)}")

    def test_single_module(self):
        self._module(".", "one")
        self._assert_agree("single module")

    def test_multi_module_without_a_workspace(self):
        self._module("svc-a", "a")
        self._module("svc-b", "b")
        self._assert_agree("multi-module, no go.work")

    def test_workspace(self):
        self._module("svc-a", "a")
        self._module("svc-b", "b")
        (self.repo / "go.work").write_text("go 1.22\n\nuse (\n\t./svc-a\n\t./svc-b\n)\n")
        self._assert_agree("go.work active")

    def test_workspace_with_gowork_off(self):
        """The case that was silently wrong on the Makefile side."""
        self._module("svc-a", "a")
        self._module("svc-b", "b")
        (self.repo / "go.work").write_text("go 1.22\n\nuse (\n\t./svc-a\n\t./svc-b\n)\n")
        self._assert_agree("GOWORK=off", {"GOWORK": "off"})

    def test_vendor_and_testdata_modules_are_excluded_by_both(self):
        self._module("svc-a", "a")
        self._module("vendor/thing", "vendored")
        self._module("testdata/fixture", "fixturemod")
        self._assert_agree("vendor/testdata excluded")


if __name__ == "__main__":
    unittest.main()
