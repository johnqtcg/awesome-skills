"""Executable proof for every factual claim in `references/lang-python.md § SSTI`.

Why this file exists: a review found the section's "GOOD" example labelled
`# GOOD: sandboxed environment with autoescape` while constructing a plain
`Environment(autoescape=...)` — and with no `loader`, so `get_template()` could not have
worked either. Two separate errors in one four-line snippet:

  1. **`autoescape` is not a sandbox.** It escapes an expression's *output*; it does not
     restrict which attributes a template may reach. A template body under attacker
     control still walks `''.__class__.__mro__` with autoescape fully on.
  2. **`Environment()` with no loader cannot load a template**, so the snippet was not a
     working control at all.

Jinja's sandbox is `jinja2.sandbox.SandboxedEnvironment`, and it bounds attribute access,
not CPU or memory. Every one of those statements is asserted below against the installed
Jinja rather than against the version that happened to be current when the doc was
written — the same discipline `xml_facts_test.py` applies to Expat and lxml.

Skipped, loudly, when Jinja is absent: the environment this was written in has no jinja2
and no package index reachable, so these rows were documentation-verified there and are
execution-verified anywhere Jinja is installed. A skip is not a pass — see
`test_examples_executable.py::PythonJinjaSSTIFacts`.
"""

import unittest

try:
    import jinja2
    from jinja2.sandbox import SandboxedEnvironment
    HAVE_JINJA = True
except ImportError:  # pragma: no cover - environment-dependent
    HAVE_JINJA = False

# The canonical SSTI probe: reach a type object, from which `__mro__` walks to `object`
# and its subclasses (subprocess.Popen among them on any real interpreter).
PROBE = "{{ ''.__class__.__name__ }}"


@unittest.skipUnless(HAVE_JINJA, "jinja2 not installed: the § SSTI rows did not execute")
class JinjaSSTIFacts(unittest.TestCase):
    def test_environment_without_a_loader_cannot_get_a_template(self):
        """The doc's original snippet called `get_template()` on a loader-less Environment."""
        env = jinja2.Environment(autoescape=True)
        with self.assertRaises(TypeError) as ctx:
            env.get_template("anything.html")
        self.assertIn("loader", str(ctx.exception).lower(),
                      f"expected the failure to name the missing loader: {ctx.exception}")

    def test_autoescape_does_not_block_attribute_traversal(self):
        """The headline claim: autoescape is an XSS control, not an SSTI control."""
        env = jinja2.Environment(autoescape=True)
        rendered = env.from_string(PROBE).render()
        self.assertEqual("str", rendered,
                         "autoescape must NOT have blocked `''.__class__` — if this ever "
                         "starts blocking, lang-python.md's rule table needs re-measuring")

    def test_autoescape_still_escapes_output(self):
        """Anti-vacuity for the test above: autoescape is on and doing its own job."""
        env = jinja2.Environment(autoescape=True)
        self.assertEqual(
            "&lt;script&gt;", env.from_string("{{ x }}").render(x="<script>"))

    def test_sandboxed_environment_blocks_attribute_traversal(self):
        env = SandboxedEnvironment(autoescape=True)
        with self.assertRaises(jinja2.exceptions.SecurityError):
            env.from_string(PROBE).render()

    def test_sandboxed_environment_still_renders_ordinary_templates(self):
        """Anti-vacuity: the sandbox rejects the probe, not everything."""
        env = SandboxedEnvironment(autoescape=True)
        self.assertEqual("hi alice",
                         env.from_string("hi {{ name }}").render(name="alice"))

    # --- Which resources the sandbox actually bounds ------------------------------
    # The doc first claimed `{% for _ in range(10**9) %}` "still runs". It does not: the
    # sandbox replaces `range` with `safe_range`, capped at MAX_RANGE. The conclusion
    # ("the sandbox is not a general resource limit") was right and the example was wrong,
    # and the test used range(50000) — inside the cap, so it could not have caught it.
    # Each row of the doc's table is asserted here, including the bound that DOES exist.

    def test_range_above_max_range_is_refused_by_the_sandbox(self):
        env = SandboxedEnvironment()
        with self.assertRaises(OverflowError):
            env.from_string("{% for _ in range(10**9) %}x{% endfor %}").render()

    def test_max_range_is_the_documented_hundred_thousand(self):
        """Pinned against the installed Jinja, so a future change to the cap fails here
        instead of rotting the doc's table."""
        from jinja2 import sandbox
        self.assertEqual(100_000, sandbox.MAX_RANGE)
        env = SandboxedEnvironment()
        self.assertEqual(
            sandbox.MAX_RANGE,
            len(env.from_string("{{ range(m) | length }}").render(m=sandbox.MAX_RANGE)
                and range(sandbox.MAX_RANGE)))
        with self.assertRaises(OverflowError):
            env.from_string("{{ range(m) | length }}").render(m=sandbox.MAX_RANGE + 1)

    def test_a_range_within_the_cap_still_renders(self):
        """Anti-vacuity for the two above: the sandbox refuses the oversized range, not
        every range."""
        env = SandboxedEnvironment()
        rendered = env.from_string("{% for _ in range(50000) %}x{% endfor %}").render()
        self.assertEqual(50000, len(rendered))

    def test_nested_loops_within_the_cap_are_not_bounded(self):
        """The doc's real example of an unbounded cost: each range is legal, the product is
        not. Asserted at a size that runs fast — the point is that it is PERMITTED, and the
        same template with 100000 x 100000 is 10^10 iterations by the same rule."""
        env = SandboxedEnvironment()
        template = env.from_string(
            "{% for a in range(o) %}{% for b in range(i) %}x{% endfor %}{% endfor %}")
        self.assertEqual(4000, len(template.render(o=2000, i=2)))

    def test_binary_operators_are_not_intercepted_by_default(self):
        """So `*` runs natively and string growth is unbounded — the doc's memory row."""
        env = SandboxedEnvironment()
        self.assertEqual(frozenset(), env.intercepted_binops)
        self.assertEqual(200_000, len(env.from_string("{{ 'x' * n }}").render(n=200_000)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
