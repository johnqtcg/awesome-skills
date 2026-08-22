"""Executable proof for every factual claim in `references/lang-python.md § Python XML`.

Why this file exists: a review found that the section stated "expansion is performed, so
amplification DoS is real", justified by a 3-level entity that expanded to 1 000 characters.
That evidence sits *inside* Expat's tolerated amplification window (factor <= 100.0, enforced
after 8 MiB of expanded output), so it proved substitution and proved nothing about DoS. The same
section claimed lxml "resolves external entities and fetches network DTDs" by default, which has
been false for the ordinary parsers since lxml 5.0.0.

Both errors are the same class: a version-gated behaviour written down as a timeless fact. So
every row of that table is asserted here against the interpreter actually running, **branching on
the library version** rather than on what happened to be true when the doc was written. A future
Expat or lxml bump that changes an answer fails this file instead of silently rotting the
guidance.

Run directly:
    python3 -m unittest discover -s <this dir> -p 'xml_facts_test.py' -v

`test_examples_executable.py` invokes it as a subprocess so it participates in the regression
suite's skip accounting. lxml is optional: its tests skip cleanly when it is not installed, and
the skip is reported rather than swallowed.
"""

import os
import tempfile
import unittest
import xml.etree.ElementTree as ET
from xml.parsers import expat

EXPAT = expat.version_info

# Expat limits ENTITY amplification since 2.4.0 (CVE-2013-0340 / CWE-776): factor <= 100.0,
# enforced after 8 MiB of expanded output.
AMPLIFICATION_PROTECTED = EXPAT >= (2, 4, 0)
# ...and ALLOCATION amplification only since 2.7.2 (CVE-2025-59375): a ~250 KiB document could
# allocate ~800 MiB of heap, factor ~3,300. Separate mechanism, separate threshold (64 MiB), so
# the entity cap above does not bound it. The Python docs give 2.7.2 as the single conservative
# gate for "billion laughs, quadratic blowup, large tokens, or disproportional dynamic memory".
ALLOCATION_PROTECTED = EXPAT >= (2, 7, 2)

try:
    import lxml.etree as LET

    LXML = LET.LXML_VERSION
except ImportError:  # optional dependency — never a hard failure
    LET = None
    LXML = None

# lxml 5.0.0 changed the default for the ordinary parsers to resolve_entities='internal'.
LXML_DEFAULT_SAFE = LXML is not None and LXML >= (5, 0)
# lxml 6.1.0 extended that default to iterparse()/ETCompatXMLParser (CVE-2026-41066); before it,
# those two resolved external entities even with no options passed.
LXML_ITERPARSE_SAFE = LXML is not None and LXML >= (6, 1)


def _billion_laughs() -> str:
    """The classic 9-level x10 bomb: ~10^9 characters if fully expanded."""
    entities = ['<!ENTITY lol "lol">']
    for i in range(1, 10):
        prev = "lol" if i == 1 else f"lol{i - 1}"
        entities.append(f'<!ENTITY lol{i} "{("&" + prev + ";") * 10}">')
    return (
        '<?xml version="1.0"?>\n<!DOCTYPE lolz [\n'
        + "\n".join(entities)
        + "\n]>\n<lolz>&lol9;</lolz>"
    )


def _quadratic_blowup(size: int = 50_000) -> str:
    """One large entity referenced many times: size^2 bytes of output."""
    return (
        '<?xml version="1.0"?>\n'
        f'<!DOCTYPE bomb [ <!ENTITY a "{"A" * size}"> ]>\n'
        f"<bomb>{'&a;' * size}</bomb>"
    )


class StdlibExpatFacts(unittest.TestCase):
    """Rows 1-4 of the stdlib table."""

    def test_external_entity_is_not_resolved(self) -> None:
        """Row 1+2: no XXE file read, no SSRF — so both are false positives on the stdlib."""
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
            fh.write("TOP_SECRET_CONTENT")
            path = fh.name
        self.addCleanup(os.unlink, path)
        doc = (
            '<?xml version="1.0"?>'
            f'<!DOCTYPE d [ <!ENTITY x SYSTEM "file://{path}"> ]>'
            "<d>&x;</d>"
        )
        with self.assertRaises(ET.ParseError) as ctx:
            ET.fromstring(doc)
        self.assertIn("undefined entity", str(ctx.exception).lower())
        # And the point of the row: the secret never reaches the tree.
        self.assertNotIn("TOP_SECRET", str(ctx.exception))

    def test_bounded_internal_entity_substitution_does_occur(self) -> None:
        """Row 4: substitution happens. This is the fact the retired guidance had right."""
        doc = (
            '<?xml version="1.0"?>'
            '<!DOCTYPE d [ <!ENTITY a "HELLO"> ]>'
            "<d>&a;</d>"
        )
        self.assertEqual("HELLO", ET.fromstring(doc).text)

    def test_small_nested_expansion_is_inside_the_tolerated_window(self) -> None:
        """The retired evidence, reproduced: a 3-level nest expands to 1 000 chars and is
        allowed. Kept as a test so the doc's claim that this proves nothing about DoS stays
        anchored to a real measurement rather than an assertion."""
        doc = (
            '<?xml version="1.0"?>'
            '<!DOCTYPE d [ <!ENTITY a "AAAAAAAAAA">'
            ' <!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">'
            ' <!ENTITY c "&b;&b;&b;&b;&b;&b;&b;&b;&b;&b;"> ]>'
            "<d>&c;</d>"
        )
        self.assertEqual(1000, len(ET.fromstring(doc).text or ""))

    def test_real_billion_laughs_is_refused_when_expat_is_protected(self) -> None:
        """Row 3, the corrected claim. Branches on the version so the assertion stays true
        across builds instead of encoding one machine's answer."""
        doc = _billion_laughs()
        if AMPLIFICATION_PROTECTED:
            with self.assertRaises(ET.ParseError) as ctx:
                ET.fromstring(doc)
            self.assertIn("amplification", str(ctx.exception).lower(),
                          f"Expat {EXPAT} should refuse on the amplification limit; a different "
                          f"error means lang-python.md needs re-measuring")
        else:
            self.skipTest(f"Expat {EXPAT} predates amplification limiting (< 2.4.0); on such a "
                          "build the DoS finding is real and must be reported")

    def test_quadratic_blowup_is_refused_when_expat_is_protected(self) -> None:
        """Amplification limiting covers the quadratic flavour too, not just deep nesting."""
        if not AMPLIFICATION_PROTECTED:
            self.skipTest(f"Expat {EXPAT} predates amplification limiting (< 2.4.0)")
        with self.assertRaises(ET.ParseError) as ctx:
            ET.fromstring(_quadratic_blowup())
        self.assertIn("amplification", str(ctx.exception).lower())

    def test_documented_expat_gate_matches_this_build(self) -> None:
        """Fail loudly if the interpreter contradicts the gate the guidance is built on."""
        self.assertTrue(
            EXPAT >= (2, 0),
            f"unexpected Expat version tuple {EXPAT}; verify lang-python.md's gates by hand",
        )

    def test_refuting_the_classic_payloads_does_not_clear_the_version(self) -> None:
        """The guard against this file's own worst failure mode.

        The two tests above fire billion-laughs and quadratic-blowup payloads and watch them be
        refused. It is tempting to read that as "this build is safe from XML DoS". It is not:
        CVE-2025-59375 is an ALLOCATION amplification (a ~250 KiB document reaching ~800 MiB of
        heap, factor ~3,300) bounded by a limiter that only exists from Expat 2.7.2. The 2.4.0
        entity cap does not touch it, so both payloads can be refused on a build that is still
        vulnerable — which is exactly the case on this interpreter if EXPAT < (2, 7, 2).

        No payload is fired here on purpose: reproducing CVE-2025-59375 means deliberately
        exhausting ~800 MiB, which is a denial of service against the machine running the test
        suite. The claim is a version gate, so the version is what gets asserted."""
        if ALLOCATION_PROTECTED:
            self.assertGreaterEqual(EXPAT, (2, 7, 2))
            return
        # Below the gate: the entity payloads ARE refused (asserted above) and the build is
        # STILL vulnerable. Assert that both halves hold, so nobody can read a green run as
        # "no XML DoS applies".
        self.assertTrue(
            AMPLIFICATION_PROTECTED,
            "unexpected: entity amplification unprotected below 2.4.0 as well",
        )
        self.assertLess(
            EXPAT, (2, 7, 2),
            "version comparison disagrees with ALLOCATION_PROTECTED; re-derive the gate",
        )

    def test_guidance_states_the_2_7_2_gate(self) -> None:
        """The reference must carry the allocator gate, not just the entity one. An earlier
        version of § Python XML marked the whole DoS row 'No on Expat >= 2.4.0', measured on
        2.7.1 — a build that is behind CVE-2025-59375."""
        import pathlib

        # …/scripts/tests/examples/python/ -> skill root is four levels up.
        ref = pathlib.Path(__file__).resolve().parents[4] / "references" / "lang-python.md"
        text = ref.read_text(encoding="utf-8")
        self.assertIn("CVE-2025-59375", text,
                      "the allocation-amplification CVE must be named")
        self.assertIn("2.7.2", text, "the allocator gate must be stated")
        self.assertRegex(
            text, r"(?i)review rule is Expat\s*(>=|≥)\s*2\.7\.2",
            "the conservative rule a reviewer applies must be the 2.7.2 one, matching the "
            "Python docs, not the 2.4.0 entity-only gate",
        )


class StdlibMinidomSaxFacts(unittest.TestCase):
    """`minidom` and `sax` specifically. A review found that the table's blanket claim — "neither
    ElementTree, minidom, nor sax resolves external entities" — had only ever been executed
    against `ElementTree`; `minidom` and `sax` inherited the conclusion from the shared Expat
    backend without being run. That is true for the default configuration, but `xml.sax` alone
    exposes `feature_external_ges`, a documented, callable opt-in switch
    (https://docs.python.org/3/library/xml.sax.handler.html) that a call site can flip to `True`
    and get exactly the file read this table calls a false positive. Run both modules directly
    rather than inferring their behaviour from ElementTree's."""

    def setUp(self) -> None:
        fh = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False)
        fh.write("TOP_SECRET_CONTENT")
        fh.close()
        self.secret_path = fh.name
        self.addCleanup(os.unlink, self.secret_path)
        self.xxe = (
            '<?xml version="1.0"?>'
            f'<!DOCTYPE d [ <!ENTITY x SYSTEM "file://{self.secret_path}"> ]>'
            "<d>&x;</d>"
        )

    def test_minidom_default_does_not_resolve_the_external_entity(self) -> None:
        from xml.dom import minidom

        dom = minidom.parseString(self.xxe)
        text_nodes = [n.data for n in dom.getElementsByTagName("d")[0].childNodes
                     if n.nodeType == n.TEXT_NODE]
        self.assertNotIn("TOP_SECRET_CONTENT", "".join(text_nodes),
                         "minidom's default must not resolve the external entity")

    def test_sax_default_does_not_resolve_the_external_entity(self) -> None:
        from xml import sax

        class Collector(sax.ContentHandler):
            def __init__(self) -> None:
                self.chars: list[str] = []

            def characters(self, content: str) -> None:
                self.chars.append(content)

        handler = Collector()
        sax.parseString(self.xxe.encode(), handler)
        self.assertNotIn("TOP_SECRET_CONTENT", "".join(handler.chars),
                         "sax's default must not resolve the external entity")

    def test_sax_feature_external_ges_reopens_the_xxe(self) -> None:
        """The opt-in this table's blanket claim misses. Measured, not inferred: the same
        document that is refused by the default parser above is resolved once this feature is
        turned on, on the same interpreter."""
        import io
        from xml import sax

        class Collector(sax.ContentHandler):
            def __init__(self) -> None:
                self.chars: list[str] = []

            def characters(self, content: str) -> None:
                self.chars.append(content)

        parser = sax.make_parser()
        handler = Collector()
        parser.setContentHandler(handler)
        parser.setFeature(sax.handler.feature_external_ges, True)
        parser.parse(io.StringIO(self.xxe))
        self.assertIn("TOP_SECRET_CONTENT", "".join(handler.chars),
                      "feature_external_ges=True must reopen the external-entity file read; if "
                      "this no longer reproduces, § Python XML's trap 3 needs re-measuring")


@unittest.skipUnless(LET is not None, "lxml not installed (optional): pip install lxml")
class LxmlFacts(unittest.TestCase):
    """The lxml table. These are the rows the retired guidance got backwards."""

    def setUp(self) -> None:
        fh = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False)
        fh.write("TOP_SECRET_CONTENT")
        fh.close()
        self.secret_path = fh.name
        self.addCleanup(os.unlink, self.secret_path)
        self.xxe = (
            '<?xml version="1.0"?>'
            f'<!DOCTYPE d [ <!ENTITY x SYSTEM "file://{self.secret_path}"> ]>'
            "<d>&x;</d>"
        ).encode()

    def test_default_parser_does_not_resolve_external_entities(self) -> None:
        """Row 1: safe by default since 5.0.0 — so a plain `fromstring` XXE report is an FP."""
        if not LXML_DEFAULT_SAFE:
            self.skipTest(f"lxml {LXML} predates the 5.0.0 safe default; XXE applies broadly")
        for parser in (None, LET.XMLParser()):
            with self.subTest(parser="default" if parser is None else "XMLParser()"):
                with self.assertRaises(LET.XMLSyntaxError) as ctx:
                    LET.fromstring(self.xxe, parser) if parser else LET.fromstring(self.xxe)
                self.assertIn("not defined", str(ctx.exception))

    def test_explicit_resolve_entities_still_reads_the_file(self) -> None:
        """Row 4: the opt-in is a real finding on every version — proves the FP suppression
        above is scoped to the default, not a blanket 'lxml is safe'."""
        tree = LET.fromstring(self.xxe, LET.XMLParser(resolve_entities=True))
        self.assertEqual("TOP_SECRET_CONTENT", tree.text)

    def test_network_dtd_is_blocked_by_default(self) -> None:
        """Row 2: `no_network=True` is the default, so 'lxml fetches network DTDs' is false."""
        doc = b'<?xml version="1.0"?><!DOCTYPE d SYSTEM "http://127.0.0.1:9/x.dtd"><d>y</d>'
        with self.assertRaises(LET.XMLSyntaxError) as ctx:
            LET.fromstring(doc, LET.XMLParser(load_dtd=True))
        self.assertIn("network", str(ctx.exception).lower())

    def test_no_network_false_alone_makes_no_fetch_attempt(self) -> None:
        """A review found `no_network=False` graded as SSRF on its own. It is not: with
        `load_dtd` left at its default (False), libxml2 never loads the external subset at all,
        network or not — a report against a target that would hang or error on a real attempt
        parses clean here with no delay, which is the behavioural proof nothing was attempted."""
        doc = b'<?xml version="1.0"?><!DOCTYPE d SYSTEM "http://127.0.0.1:1/x.dtd"><d>y</d>'
        tree = LET.fromstring(doc, LET.XMLParser(no_network=False))
        self.assertEqual(b"<d>y</d>", LET.tostring(tree))

    def test_guidance_states_the_no_network_transport_caveat(self) -> None:
        """The reference must not let a reader read `no_network=False` as confirmed SSRF by
        itself — measured on this build, it fails identically to a bad `file://` path rather
        than reaching the network, because this libxml2 has no transport registered for the
        scheme. A prior version of § Python XML stated the opposite ('every version')."""
        import pathlib

        ref = pathlib.Path(__file__).resolve().parents[4] / "references" / "lang-python.md"
        text = ref.read_text(encoding="utf-8")
        self.assertIn("load_dtd", text)
        self.assertRegex(
            text, r"(?i)grade lxml SSRF from `no_network=False`\s+as `likely`",
            "the reference must not let no_network=False alone license a `confirmed` SSRF verdict",
        )

    def test_iterparse_xxe_matches_the_documented_version_gate(self) -> None:
        """Row 3 — CVE-2026-41066. The single exploitable default in the Python XML surface,
        and the row the retired guidance missed entirely while over-claiming elsewhere."""
        import io

        def parse():
            return [el.text for _, el in LET.iterparse(io.BytesIO(self.xxe), events=("end",))]

        if LXML_ITERPARSE_SAFE:
            with self.assertRaises(LET.XMLSyntaxError):
                parse()
        else:
            self.assertIn(
                "TOP_SECRET_CONTENT", parse(),
                f"lxml {LXML} is documented as vulnerable via iterparse (CVE-2026-41066, fixed "
                "in 6.1.0); it did not resolve the entity, so re-measure the gate",
            )

    def test_etcompat_parser_xxe_matches_the_documented_version_gate(self) -> None:
        """Same CVE, second affected surface."""
        if LXML_ITERPARSE_SAFE:
            with self.assertRaises(LET.XMLSyntaxError):
                LET.fromstring(self.xxe, LET.ETCompatXMLParser())
        else:
            self.assertEqual(
                "TOP_SECRET_CONTENT",
                LET.fromstring(self.xxe, LET.ETCompatXMLParser()).text,
                f"lxml {LXML} is documented as vulnerable via ETCompatXMLParser "
                "(CVE-2026-41066, fixed in 6.1.0); re-measure the gate",
            )


if __name__ == "__main__":
    print(f"expat={EXPAT} amplification_protected={AMPLIFICATION_PROTECTED} lxml={LXML}")
    unittest.main()
