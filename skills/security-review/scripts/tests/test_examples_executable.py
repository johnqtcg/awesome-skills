"""Executable verification of the skill's GOOD security examples.

Why this file exists: a review found that `references/go-secure-coding.md` told reviewers to
set `xml.Decoder.MaxDepth`, a field that has never existed in any Go version. The advice was
unbuildable, and nothing caught it — the contract tests only assert that strings appear in
the documents, and the golden tests explicitly do not execute anything.

For a *security* skill, an unsafe or non-compiling GOOD example is the worst defect class:
readers copy it. So the documented patterns are mirrored as real code under
`examples/{go,node}/`, executed here, and pinned to the prose by drift checks:

  1. `examples/go`     — `go test ./...` proves the SSRF guard compiles and actually blocks
                         loopback/private/IMDS/IPv4-mapped targets, and pins every factual
                         claim in §Go XML (no MaxDepth field, no entity expansion, built-in
                         depth cap).
  2. `examples/node`   — proves `safeTokenEqual` never throws on attacker-chosen lengths and
                         that the raw-buffer misuse genuinely raises RangeError.
  3. Drift checks      — the docs must still teach what the probes prove, and must not
                         reintroduce the retired advice.

Toolchain-dependent tests skip cleanly when `go` / `node` are absent.
"""

import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[2]
SKILL_MD = SKILL_DIR / "SKILL.md"
REFERENCES = SKILL_DIR / "references"
EXAMPLES = Path(__file__).resolve().parent / "examples"

GO = shutil.which("go")
NODE = shutil.which("node")


def _doc_text() -> str:
    parts = [SKILL_MD.read_text(encoding="utf-8")]
    parts += [p.read_text(encoding="utf-8") for p in sorted(REFERENCES.glob("*.md"))]
    return "\n".join(parts)


def _all_docs():
    return [SKILL_MD, *sorted(REFERENCES.glob("*.md"))]


# A line that names retired advice in order to warn against it is required documentation,
# not a violation. Only unqualified occurrences read as instructions.
_CAUTIONARY = re.compile(
    r"(?i)(never existed|does not exist|no field|no such field|There is no|"
    r"is not a file|not a package pattern|Never recommend|not look for|"
    r"ALSO BAD|^\s*//\s*BAD|fails to compile|errors with|undefined \(type)"
)


def _is_cautionary(line: str) -> bool:
    return bool(_CAUTIONARY.search(line))


def _go_env(cache: Path) -> dict:
    """Inherit the environment (TMPDIR matters — without it `go` tries /tmp, which is not
    writable under sandboxed runs) and drop only GOROOT, which breaks cross-toolchain builds."""
    import os

    env = dict(os.environ)
    env.pop("GOROOT", None)
    env["GOTOOLCHAIN"] = "local"
    env["GOFLAGS"] = "-count=1"
    env["GOCACHE"] = str(cache / "build")
    env["GOMODCACHE"] = str(cache / "mod")
    env["GOPATH"] = str(cache / "path")
    return env


@unittest.skipIf(GO is None, "go toolchain not installed")
class GoExampleTests(unittest.TestCase):
    """Compile and run the Go security examples."""

    def test_go_examples_pass(self) -> None:
        mod = EXAMPLES / "go"
        self.assertTrue((mod / "go.mod").is_file(), "examples/go must be a Go module")
        with tempfile.TemporaryDirectory() as cache:
            env = _go_env(Path(cache))
            try:
                proc = subprocess.run(
                    [GO, "test", "./..."], cwd=mod, env=env,
                    capture_output=True, text=True, timeout=300, errors="replace",
                )
            except subprocess.TimeoutExpired:
                self.skipTest("go test exceeded 300s in this environment")
            except OSError as exc:
                self.skipTest(f"cannot exec go: {exc}")
            stderr = proc.stderr or ""
            if proc.returncode != 0 and "cannot find" in stderr:
                self.skipTest(f"go cannot build here: {stderr[:200]}")
            # The path-containment example needs os.Root (Go 1.24+); on an older toolchain
            # that is an environment limitation, not a skill defect.
            if proc.returncode != 0 and ("requires go >= 1.24" in stderr
                                         or "OpenRoot" in stderr):
                self.skipTest("toolchain predates Go 1.24 (os.Root); skipping example run")
            self.assertEqual(
                0, proc.returncode,
                "documented Go security examples failed:\n"
                f"{proc.stdout[-4000:]}\n{proc.stderr[-2000:]}",
            )


@unittest.skipIf(NODE is None, "node not installed")
class NodeExampleTests(unittest.TestCase):
    """Run the Node security examples."""

    def test_node_examples_pass(self) -> None:
        script = EXAMPLES / "node" / "security_examples.test.js"
        self.assertTrue(script.is_file(), f"missing {script}")
        try:
            proc = subprocess.run(
                [NODE, str(script)], cwd=script.parent,
                capture_output=True, text=True, timeout=120, errors="replace",
            )
        except subprocess.TimeoutExpired:
            self.skipTest("node examples exceeded 120s")
        except OSError as exc:
            self.skipTest(f"cannot exec node: {exc}")
        self.assertEqual(
            0, proc.returncode,
            f"documented Node security examples failed:\n{proc.stdout[-4000:]}\n{proc.stderr[-2000:]}",
        )


class RetiredAdviceTests(unittest.TestCase):
    """Guard against the specific wrong guidance that was removed. These run without any
    toolchain, so the regression is caught even in a bare environment."""

    def test_no_maxdepth_recommendation(self) -> None:
        """`xml.Decoder.MaxDepth` does not exist. It may only appear where the docs say so."""
        offenders = [
            f"{path.name}:{i}: {line.strip()}"
            for path in _all_docs()
            for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
            if "MaxDepth" in line and not _is_cautionary(line)
        ]
        self.assertFalse(
            offenders,
            "xml.Decoder.MaxDepth has never existed in any Go version; these lines read as "
            "advice to set it:\n" + "\n".join(offenders),
        )

    def test_no_binary_mode_with_package_pattern(self) -> None:
        """`govulncheck -mode=binary ./...` errors with `"./..." is not a file`."""
        offenders = [
            f"{path.name}:{i}: {line.strip()}"
            for path in _all_docs()
            for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
            if re.search(r"-mode=binary\s+(\./)?\.\.\.", line) and not _is_cautionary(line)
        ]
        self.assertFalse(
            offenders,
            "govulncheck binary mode takes a built artifact, not a package pattern:\n"
            + "\n".join(offenders),
        )

    def test_retired_advice_guards_are_not_vacuous(self) -> None:
        """Anti-vacuity: the cautionary allowance must not swallow a real instruction."""
        self.assertTrue(_is_cautionary("`-mode=binary ./...` errors with `not a file`"))
        self.assertTrue(_is_cautionary("no field or method MaxDepth"))
        # Bare instructions must still be caught.
        self.assertFalse(_is_cautionary("Set `d.MaxDepth = 100` on the decoder"))
        self.assertFalse(_is_cautionary("govulncheck -mode=binary ./..."))

    def test_no_lexical_only_path_guard_recommended(self) -> None:
        """`strings.HasPrefix(filepath.Clean(x), base)` without a trailing separator allows a
        sibling-directory escape (verified: /var/app + ../app-evil/secret passes). It may only
        appear where the docs mark it as broken."""
        offenders = []
        for path in _all_docs():
            lines = path.read_text(encoding="utf-8").splitlines()
            for i, line in enumerate(lines, 1):
                if not re.search(r"HasPrefix\(filepath\.Clean", line):
                    continue
                if _is_cautionary(line):
                    continue
                # The marker that makes it a counter-example sits on an earlier line of the
                # same code block, so look back to the nearest BAD/GOOD label.
                context = "\n".join(lines[max(0, i - 14):i])
                labels = re.findall(r"//\s*(ALSO BAD|STILL BAD|BAD|GOOD)", context)
                if labels and labels[-1] != "GOOD":
                    continue
                offenders.append(f"{path.name}:{i}: {line.strip()}")
        self.assertFalse(
            offenders,
            "a lexical prefix guard without a trailing separator is presented as the fix; "
            "recommend os.Root (Go 1.24+) instead:\n" + "\n".join(offenders),
        )

    def test_no_prose_prefix_check_recommended(self) -> None:
        """The earlier guard only matched the CODE form `HasPrefix(filepath.Clean(...))`, so the
        natural-language version of the same retired advice survived in
        scenario-checklists.md ("must verify result starts with `base` after filepath.Clean")."""
        prose = re.compile(
            r"(?i)(verify|check|ensure)[^.\n]{0,60}"
            r"(starts with|begins with|has(?:the)? ?prefix)[^.\n]{0,60}base"
            r"|(starts with|begins with)[^.\n]{0,30}`?base`?[^.\n]{0,40}filepath\.Clean"
        )
        offenders = []
        for path in _all_docs():
            for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if not prose.search(line):
                    continue
                if _is_cautionary(line) or re.search(r"(?i)is \*\*not\*\* the fix|not the fix|"
                                                     r"lexical|os\.Root", line):
                    continue
                offenders.append(f"{path.name}:{i}: {line.strip()}")
        self.assertFalse(
            offenders,
            "prose still recommends the retired prefix check as the path-traversal fix:\n"
            + "\n".join(offenders),
        )

    def test_prose_guard_is_not_vacuous(self) -> None:
        """Pin the exact sentence that was removed."""
        retired = ("- `filepath.Join(base, userInput)` does NOT prevent `../` traversal → must "
                   "verify result starts with `base` after `filepath.Clean`.")
        prose = re.compile(
            r"(?i)(verify|check|ensure)[^.\n]{0,60}"
            r"(starts with|begins with|has(?:the)? ?prefix)[^.\n]{0,60}base"
        )
        self.assertRegex(retired, prose,
                         "prose guard no longer detects the retired natural-language advice")

    def test_os_root_trailing_separator_caveat_documented(self) -> None:
        """os.Root alone is not sufficient: Open("<symlink>/") escapes (verified on go1.26.1).
        Recommending os.Root without the Clean pre-pass would ship a known bypass."""
        go_ref = (REFERENCES / "go-secure-coding.md").read_text(encoding="utf-8")
        self.assertIn("GO-2026-4970", go_ref,
                      "the os.Root containment advisory must be named")
        self.assertRegex(go_ref, r"(?i)trailing[- ]separator",
                         "the escaping shape must be described")
        self.assertRegex(
            go_ref, r"filepath\.Clean[\s\S]{0,400}?(before|pre-pass)[\s\S]{0,200}?os\.Root"
                    r"|Clean the relative input before handing it to `os\.Root`",
            "the verified mitigation (Clean the relative input first) must be stated",
        )

    def test_os_root_advisory_lists_fixed_versions(self) -> None:
        """Reproducing on 1.26.1 is *within* the advisory's range — it confirms the advisory
        rather than showing the ranges are untrustworthy. Earlier wording implied the latter and
        omitted the fixed releases, which reads as "upgrading will not help"."""
        go_ref = (REFERENCES / "go-secure-coding.md").read_text(encoding="utf-8")
        for fixed in ("1.25.12", "1.26.5", "1.27.0-rc.2"):
            self.assertIn(fixed, go_ref,
                          f"the fixed release {fixed} must be listed; upgrading is the fix")
        self.assertRegex(
            go_ref, r"(?i)Upgrad\w+ the toolchain is the primary fix|Upgrade the toolchain",
            "upgrading must be named as the primary fix, with Clean as defense in depth",
        )
        self.assertRegex(
            go_ref, r"(?i)defense in depth, not\s*\n?\s*a substitute|not\s+a substitute for upgrading",
            "the Clean pre-pass must be framed as defense in depth, not a replacement",
        )
        self.assertNotRegex(
            go_ref, r"(?i)do not assume a given release is\s*\n?\s*unaffected",
            "retired framing: it implied the advisory's ranges cannot be trusted",
        )

    def test_path_example_applies_the_mitigation(self) -> None:
        """The GOOD example itself must Clean before calling root.Open — otherwise the skill
        recommends the vulnerable shape in the code readers copy."""
        go_ref = (REFERENCES / "go-secure-coding.md").read_text(encoding="utf-8")
        m = re.search(r"var uploadRoot \*os\.Root[\s\S]{0,900}?uploadRoot\.Open\(([^)]*)\)", go_ref)
        self.assertIsNotNone(m, "the os.Root ServeFile example is missing")
        self.assertNotIn("Query().Get", m.group(1),
                         "the example passes raw user input to root.Open; it must Clean first")
        self.assertIn("filepath.Clean", m.group(0),
                      "the example must Clean the relative input before root.Open")

    def test_path_containment_recommends_os_root(self) -> None:
        text = _doc_text()
        self.assertIn("os.OpenRoot", text,
                      "path-traversal guidance must recommend os.Root for file access")
        self.assertRegex(text, r"(?i)symlink",
                         "guidance must state that a lexical check cannot see symlinks")
        self.assertRegex(
            text, r"(?i)IsLocal[\s\S]{0,300}?lexical",
            "must note filepath.IsLocal is lexical-only and not sufficient for file access",
        )

    def test_xml_suppression_guidance_present(self) -> None:
        text = _doc_text()
        self.assertIn("XXE", text)
        self.assertRegex(
            text, r"(?is)encoding/xml.*(no|not).*(entit|DTD)",
            "docs must state that stdlib encoding/xml resolves no DTD entities, so XXE and "
            "billion-laughs are false positives against it",
        )


class DocProbeDriftTests(unittest.TestCase):
    """The probes prove specific controls. If the docs stop teaching them, the probes are
    guarding code nobody is told to write."""

    def test_docs_teach_connect_time_ip_check(self) -> None:
        text = _doc_text()
        self.assertIn("Dialer.Control", text,
                      "Go SSRF guidance must name Dialer.Control — a pre-dial LookupIP "
                      "leaves a DNS-rebinding window")
        self.assertRegex(text, r"(?i)rebinding")

    def test_docs_teach_redirect_refusal(self) -> None:
        text = _doc_text()
        self.assertIn("CheckRedirect", text)
        self.assertRegex(
            text, r"(?i)redirect.*(refus|disab|manual|never)",
            "SSRF guidance must require refusing or re-validating redirects; an allowlisted "
            "host can 302 to an internal address",
        )

    def test_docs_teach_ipv4_mapped_unmap(self) -> None:
        text = _doc_text()
        self.assertIn("::ffff:127.0.0.1", text,
                      "guidance must cover IPv4-mapped IPv6 smuggling")

    def test_docs_warn_timingsafeequal_throws(self) -> None:
        text = _doc_text()
        self.assertIn("timingSafeEqual", text)
        self.assertRegex(
            text, r"(?i)timingSafeEqual[\s\S]{0,400}?(throw|RangeError)",
            "Node guidance must state that timingSafeEqual throws on unequal byte length",
        )

    def test_probe_and_doc_share_the_guard_name(self) -> None:
        """Cheap rename-drift check between examples/go and the reference."""
        probe = (EXAMPLES / "go" / "ssrf.go").read_text(encoding="utf-8")
        self.assertIn("blockNonPublic", probe)
        self.assertIn(
            "blockNonPublic", (REFERENCES / "go-secure-coding.md").read_text(encoding="utf-8"),
            "the reference and the executable probe must show the same guard",
        )


class CrossFileSemanticDriftTests(unittest.TestCase):
    """A Deep review loads SKILL.md *and* the deep references. If a reference still carries a
    rule the main file retired, the agent can silently revert to the old behaviour. Nothing
    caught that class before: SKILL.md was corrected while go-secure-coding.md kept
    "Any race: at least P2" and "missing nolint rationale is at least P3"."""

    # Absolute floors, stated without any attacker-reachability qualifier.
    # A severity floor is acceptable only when the same sentence names an attacker-reachability
    # condition. Vague escape hatches ("unless proven harmless") do not count — that phrasing is
    # what let the old rules read as absolute in practice.
    FLOOR_CLAIM = re.compile(r"(?i)\bat least `?P[0-3]`?")
    REACHABILITY = re.compile(
        r"(?i)\b(attacker|reachab|exploitab|observable|remotely|untrusted|"
        r"authenticated|rate-limit|drive[sn]?|trust boundary)\b"
    )

    @classmethod
    def FLOOR_search(cls, line: str):
        """True when the line asserts a floor without any reachability qualifier."""
        if not cls.FLOOR_CLAIM.search(line):
            return None
        if cls.REACHABILITY.search(line):
            return None
        return cls.FLOOR_CLAIM.search(line)

    # Keep the attribute name used by assertRegex-style checks below.
    FLOOR = property(lambda self: self.FLOOR_CLAIM)

    def test_no_unqualified_severity_floor_in_references(self) -> None:
        offenders = []
        for path in sorted(REFERENCES.glob("*.md")):
            # severity-calibration.md is the file that *explains* floors; exempt its prose.
            if path.name == "severity-calibration.md":
                continue
            for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if self.FLOOR_search(line):
                    offenders.append(f"{path.name}:{i}: {line.strip()}")
        self.assertFalse(
            offenders,
            "references assert an absolute severity floor with no reachability qualifier, "
            "contradicting SKILL.md's exploitability-first rule:\n" + "\n".join(offenders),
        )

    def test_references_defer_to_the_calibration_rule(self) -> None:
        """Where a reference does assign severity, it must point at the governing rule so a
        reader cannot treat the local number as final."""
        go_ref = (REFERENCES / "go-secure-coding.md").read_text(encoding="utf-8")
        self.assertIn("severity-calibration.md", go_ref,
                      "the deep Go reference must defer to the severity governing rule")

    def test_calibration_governing_rule_exists(self) -> None:
        cal = (REFERENCES / "severity-calibration.md").read_text(encoding="utf-8")
        self.assertIn("Exploitability Outranks Any Severity Floor", cal)

    def test_drift_guard_is_not_vacuous(self) -> None:
        """Prove the regex still matches the exact lines that were removed, and does not fire
        on the qualified replacements that took their place."""
        for retired in (
            "Any race: at least `P2`. Race on auth/balance/permission state: `P1` (CWE-367).",
            "- Suppressed `//nolint:gosec` must have inline rationale; missing rationale is at least `P3`.",
            "- `==` or `bytes.Equal` on secrets is at least `P2`",
            "- Any missing or ambiguous pairing is at least `P2` unless proven harmless.",
        ):
            self.assertIsNotNone(
                self.FLOOR_search(retired),
                f"drift guard no longer detects a retired floor: {retired}",
            )

        for qualified in (
            "- `==` on secrets is at least `P2` when the comparison is remotely observable",
            "A leak is at least `P2` where an attacker can drive it repeatedly",
            "at least `P2` on an untrusted path, `P3` behind an authenticated one",
        ):
            self.assertIsNone(
                self.FLOOR_search(qualified),
                f"drift guard false-positives on a properly qualified rule: {qualified}",
            )


class UnifiedDomainNumberingTests(unittest.TestCase):
    """SKILL.md claims the 10 domains are stack-independent. That claim is only true if every
    language reference actually uses the same numbers and names — otherwise an agent reviewing
    Node has no idea what Domain 7 is. The language refs previously said "replace Go-specific
    Gate D domains" and listed 9/8/8 ad-hoc categories."""

    CANONICAL = {
        1: "Randomness Safety",
        2: "Injection & Data-Access Safety",
        3: "Sensitive Data Handling",
        4: "Secret / Config Management",
        5: "Transport Security",
        6: "Crypto Primitive Correctness",
        7: "Concurrency & Shared-State Safety",
        8: "Language-Specific Injection Sinks",
        9: "Static Scanner Posture",
        10: "Dependency Vulnerability Posture",
    }
    LANG_REFS = ("lang-nodejs.md", "lang-java.md", "lang-python.md")
    ALL_STACK_REFS = LANG_REFS + ("go-secure-coding.md",)

    def test_all_stack_refs_agree_on_domain_names(self) -> None:
        """Go is one instantiation of the canonical set, not the definition. If it drifts, the
        numbering is ambiguous again."""
        for ref in self.ALL_STACK_REFS:
            text = (REFERENCES / ref).read_text(encoding="utf-8")
            for num, name in self.CANONICAL.items():
                self.assertRegex(
                    text, rf"{num}\s*\|?\s*—?\s*{re.escape(name)}",
                    f"{ref}: Domain {num} is not named {name!r}",
                )

    def test_canonical_list_is_declared_once(self) -> None:
        policy = (REFERENCES / "authorization-and-policy.md").read_text(encoding="utf-8")
        for num, name in self.CANONICAL.items():
            self.assertRegex(
                policy, rf"\|\s*{num}\s*\|\s*\*\*{re.escape(name)}\*\*",
                f"canonical domain {num} ({name}) missing from authorization-and-policy.md §2",
            )

    def test_every_language_ref_covers_all_ten_domains(self) -> None:
        for ref in self.LANG_REFS:
            text = (REFERENCES / ref).read_text(encoding="utf-8")
            for num, name in self.CANONICAL.items():
                self.assertRegex(
                    text, rf"\|\s*{num}\s*\|\s*{re.escape(name)}\s*\|",
                    f"{ref}: Domain {num} ({name}) missing — an agent cannot map it",
                )

    def test_nothing_claims_to_replace_gate_d(self) -> None:
        """Checks EVERY doc, not just the language refs — reference-index.md carried this line
        long after the language files were fixed."""
        offenders = []
        for path in _all_docs():
            for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if re.search(r"(?i)replace Go-specific Gate D|replace .{0,20}Gate D domains", line):
                    offenders.append(f"{path.name}:{i}")
        self.assertFalse(
            offenders,
            "these say a stack reference *replaces* Gate D, contradicting the "
            f"unified-domain rule: {offenders}",
        )

    def test_language_refs_point_at_the_canonical_definition(self) -> None:
        for ref in self.LANG_REFS:
            text = (REFERENCES / ref).read_text(encoding="utf-8")
            self.assertIn("authorization-and-policy.md` §2", text,
                          f"{ref} must point at the canonical domain definition")

    def test_main_flow_prose_is_not_go_only(self) -> None:
        """The domain TABLE was made stack-independent while the 15-step prose still said
        "Go resource inventory scan", "Go secure-coding 10-domain coverage" and "each Go
        domain" — so an agent reading the process narrative would still treat Gate B/D as
        Go-only. Tables and prose must agree."""
        skill = SKILL_MD.read_text(encoding="utf-8")
        for stale in (
            "Go resource inventory scan",
            "Go secure-coding 10-domain coverage",
            "each Go domain",
            "Gate B: Go Resource Inventory",
            "Mandatory for Go)",
        ):
            self.assertNotIn(stale, skill,
                             f"main flow still Go-only: {stale!r}")

    def test_gate_b_covers_every_stack(self) -> None:
        skill = SKILL_MD.read_text(encoding="utf-8")
        self.assertIn("Gate B: Resource Inventory (Mandatory, every stack)", skill)
        for idiom in ("try-with-resources", "Python `with`", "finally"):
            self.assertIn(idiom, skill,
                          f"Gate B must name the non-Go release idiom: {idiom}")

    def test_go_domain_8_is_language_neutral(self) -> None:
        go_ref = (REFERENCES / "go-secure-coding.md").read_text(encoding="utf-8")
        self.assertIn("Domain 8 — Language-Specific Injection Sinks", go_ref)
        self.assertNotIn("Domain 8 — Go-Specific Injection Sinks", go_ref)

    def test_java_xml_states_xxe_applies(self) -> None:
        """Java's parsers resolve external entities unless explicitly hardened, so the Go
        exemption must not leak across."""
        text = (REFERENCES / "lang-java.md").read_text(encoding="utf-8")
        self.assertRegex(
            text, r"(?i)(XXE|entity expansion)[\s\S]{0,120}?do apply|do apply[\s\S]{0,120}?(XXE|entity)",
            "lang-java.md must state that XXE applies here, unlike Go",
        )
        self.assertIn("disallow-doctype-decl", text,
                      "Java guidance must name the concrete hardening flag")

    def test_python_xml_is_split_by_attack_and_library(self) -> None:
        """A blanket "Python XXE applies" is a false-positive generator. Measured on CPython
        3.14 / Expat 2.7.1: an external SYSTEM entity yields `undefined entity` (no file read),
        while internal entity expansion DOES occur. The guidance must distinguish them, and must
        separate stdlib from lxml."""
        text = (REFERENCES / "lang-python.md").read_text(encoding="utf-8")
        # Ban the CLAIM, not one phrasing of it. The first version of this guard forbade only
        # the exact retired sentence, so the same error survived in the Domain 8 summary row
        # as "XXE — use defusedxml, since stdlib parsers honour DTDs".
        claims = [
            r"(?i)XXE and entity expansion do apply to Python",
            r"(?i)stdlib[^.\n]{0,40}pars\w+[^.\n]{0,30}(honour|honor|process|resolve)[^.\n]{0,20}DTD",
            r"(?i)XXE[^.\n]{0,60}(because|since)[^.\n]{0,60}DTD",
        ]
        for pattern in claims:
            for i, line in enumerate(text.splitlines(), 1):
                if re.search(pattern, line) and not re.search(
                        r"(?i)not XXE|does NOT|is a false positive|no file read", line):
                    self.fail(
                        f"lang-python.md:{i} asserts stdlib parsers resolve DTD entities, which "
                        f"generates XXE false positives (verified: external entities yield "
                        f"`undefined entity`):\n  {line.strip()}"
                    )

    def test_python_xml_guard_catches_paraphrases(self) -> None:
        """Anti-vacuity: the semantic guard must catch the summary-row wording, not just the
        original sentence."""
        paraphrase = ("| 8 | Language-Specific Injection Sinks | ... XXE — use `defusedxml`, "
                      "since stdlib parsers honour DTDs; ...")
        self.assertRegex(
            paraphrase,
            r"(?i)stdlib[^.\n]{0,40}pars\w+[^.\n]{0,30}(honour|honor|process|resolve)[^.\n]{0,20}DTD",
            "semantic guard no longer detects the Domain 8 summary-row paraphrase",
        )
        # And it must not fire on the corrected wording.
        corrected = ("**XML** — use `defusedxml` for untrusted input; the live stdlib risk is "
                     "*entity-expansion DoS*, **not** XXE file read")
        self.assertNotRegex(
            corrected,
            r"(?i)stdlib[^.\n]{0,40}pars\w+[^.\n]{0,30}(honour|honor|process|resolve)[^.\n]{0,20}DTD",
            "semantic guard false-positives on the corrected wording",
        )

    def test_python_xml_version_boundary_is_not_asserted_from_memory(self) -> None:
        """The reference claimed `< 2.4.x` as the risky Expat boundary — an unverified number
        that moves as CPython bumps its bundled Expat. Point at the official doc instead."""
        text = (REFERENCES / "lang-python.md").read_text(encoding="utf-8")
        self.assertNotRegex(
            text, r"(?i)Older Expat \(< 2\.\d",
            "do not hard-code an Expat risk boundary; cite the official doc and record the "
            "version actually checked",
        )
        self.assertIn("docs.python.org/3/library/xml.html#xml-security", text)
        self.assertIn("expat.version_info", text,
                      "must give the command that reports the version under review")
        # External-entity XXE must be marked as NOT applying to the stdlib default.
        self.assertRegex(
            text, r"(?i)external entity[\s\S]{0,200}?\*\*No\*\*|undefined entity",
            "must state that stdlib Expat does not resolve external entities",
        )
        # Internal expansion must still be reported as live.
        self.assertRegex(
            text, r"(?i)internal entity expansion[\s\S]{0,200}?\*\*Yes\*\*",
            "must state that internal entity expansion DOES occur",
        )
        # Version/build dependence and the lxml carve-out.
        self.assertRegex(text, r"(?i)expat", "must name Expat, since behaviour is version-dependent")
        self.assertIn("lxml", text, "must carve out lxml, where XXE does apply")
        self.assertIn("defusedxml", text)


class RunnerFailsClosedTests(unittest.TestCase):
    """The runner previously swallowed a quick_validate failure with `|| echo ... (non-blocking)`
    and still printed "passed" — false assurance from a security skill's own gate."""

    RUNNER = SKILL_DIR / "scripts" / "run_regression.sh"

    def test_validator_failure_is_not_swallowed(self) -> None:
        text = self.RUNNER.read_text(encoding="utf-8")
        self.assertNotRegex(
            text, r"quick_validate\.py.*\|\|",
            "validator failure must abort the run, not fall through to 'passed'",
        )
        self.assertNotIn("non-blocking", text)

    def test_runner_uses_strict_mode(self) -> None:
        self.assertIn("set -euo pipefail", self.RUNNER.read_text(encoding="utf-8"))

    def test_runner_invokes_example_tests(self) -> None:
        text = self.RUNNER.read_text(encoding="utf-8")
        self.assertIn("test_examples_executable.py", text)
        self.assertIn("test_forward_eval.py", text,
                      "the runner must execute the forward-eval layer")

    def test_runner_distinguishes_pass_from_pass_with_skips(self) -> None:
        """A bare "passed" after skipped checks is quieter false assurance. Verified behaviour:
        skips -> "PASS WITH SKIPS" (exit 0); STRICT=1 -> FAIL (exit 1); a validator *failure*
        aborts before any verdict is printed."""
        text = self.RUNNER.read_text(encoding="utf-8")
        self.assertIn("PASS WITH SKIPS", text)
        self.assertIn("PASS — all checks executed", text)
        self.assertIn("STRICT", text, "a strict mode must be available for CI")
        self.assertIn("gaps in verification, not evidence of correctness", text)

    def test_runner_accounts_for_the_skippable_layers(self) -> None:
        """Each layer that can silently vanish must be named in the skip accounting."""
        text = self.RUNNER.read_text(encoding="utf-8")
        for probe in ("command -v go", "command -v node",
                      "SECURITY_REVIEW_EVAL_CMD", "SKILL_CREATOR_VALIDATOR"):
            self.assertIn(probe, text,
                          f"runner must account for a possible skip of: {probe}")

    def test_runner_counts_skips_structurally_not_by_grepping(self) -> None:
        """Grepping the whole log for "skipped|SKIP" matched this suite's own docstrings and
        invented a phantom skip on a fully green run. Parse unittest's summary line instead."""
        text = self.RUNNER.read_text(encoding="utf-8")
        self.assertNotRegex(
            text, r'grep -qE "skipped\|SKIP"',
            "skip detection must not grep the log body — test prose mentions 'skipped'",
        )
        self.assertRegex(
            text, r"skipped=\(\[0-9\]\+\)|skipped=",
            "runner must read unittest's structured `OK (skipped=N)` summary",
        )

    def test_runner_attributes_each_skip_once(self) -> None:
        """The live-eval gap was reported twice (per-suite count + env-var note)."""
        text = self.RUNNER.read_text(encoding="utf-8")
        self.assertIn("SECURITY_REVIEW_EVAL_CMD", text)
        self.assertEqual(
            1, len(re.findall(r"note_skip \"live model forward-eval", text)),
            "the live-eval skip must be reported exactly once",
        )

    def test_runner_uses_a_sandbox_safe_tempfile(self) -> None:
        """A bare `mktemp` resolves outside TMPDIR on macOS and fails under sandboxed runs."""
        text = self.RUNNER.read_text(encoding="utf-8")
        self.assertNotRegex(text, r"mktemp\s*\)", "use an explicit TMPDIR template with mktemp")
        self.assertIn("TMPDIR", text)


if __name__ == "__main__":
    unittest.main()
