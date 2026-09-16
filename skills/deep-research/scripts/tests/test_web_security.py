"""Security boundaries for all deep-research Web egress."""

import importlib.util
import sys
import unittest
# Guards added after an audit found 14 of 18 raises in web.py never executing.
# Each test below fires exactly one of them; without a test that reaches the
# raise, deleting the guard is a silent no-op on a green suite.
from pathlib import Path
from unittest.mock import patch

LIB = (
    Path(__file__).resolve().parents[1]
    / "deep_research_lib"
    / "web.py"
)
spec = importlib.util.spec_from_file_location("deep_research_web_security", LIB)
web = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = web
spec.loader.exec_module(web)


class TestPublicTargetPolicy(unittest.TestCase):
    def test_rejects_non_http_schemes_and_credentials(self) -> None:
        for url in (
            "file:///etc/hosts",
            "ftp://example.com/archive",
            "gopher://example.com/1",
            "http://user:pass@example.com/",
        ):
            with self.subTest(url=url):
                with self.assertRaises(web.UnsafeWebTargetError):
                    web.resolve_public_target(url)

    def test_rejects_literal_non_public_addresses(self) -> None:
        for url in (
            "http://127.0.0.1/",
            "http://10.0.0.1/",
            "http://169.254.169.254/latest/meta-data/",
            "http://[::1]/",
            "http://[fe80::1]/",
            "http://0.0.0.0/",
            "http://224.0.0.1/",
        ):
            with self.subTest(url=url):
                with self.assertRaises(web.UnsafeWebTargetError):
                    web.resolve_public_target(url)

    def test_rejects_hostname_if_any_dns_answer_is_non_public(self) -> None:
        with patch.object(
            web,
            "_resolve_addresses",
            return_value=("93.184.216.34", "169.254.169.254"),
        ):
            with self.assertRaises(web.UnsafeWebTargetError):
                web.resolve_public_target("https://example.com/path")


class TestSafeRedirectAndPinning(unittest.TestCase):
    def test_redirect_is_revalidated_before_second_request(self) -> None:
        redirect = web.HopResponse(
            status=302,
            reason="Found",
            headers={"location": "http://169.254.169.254/latest/meta-data/"},
            body=b"",
        )
        with patch.object(
            web,
            "_resolve_addresses",
            return_value=("93.184.216.34",),
        ), patch.object(
            web,
            "_request_target",
            return_value=redirect,
        ) as request:
            with self.assertRaises(web.UnsafeWebTargetError):
                web.fetch_public_url("https://example.com/start")
        request.assert_called_once()

    def test_connection_uses_the_validated_ip(self) -> None:
        response = web.HopResponse(
            status=200,
            reason="OK",
            headers={"content-type": "text/html"},
            body=b"<html>safe</html>",
        )
        with patch.object(
            web,
            "_resolve_addresses",
            return_value=("93.184.216.34",),
        ), patch.object(
            web,
            "_request_target",
            return_value=response,
        ) as request:
            result = web.fetch_public_url("https://example.com/page")
        self.assertEqual(("93.184.216.34",), result.resolved_ips)
        self.assertEqual(
            "93.184.216.34",
            request.call_args.kwargs["connect_ip"],
        )





class TestPreviouslyUncoveredGuards(unittest.TestCase):
    """One test per guard that a coverage trace showed never executing.

    A guard with no test that reaches it can be deleted without turning the
    suite red, which is the same as not having it. Each case below was
    confirmed to fail when its guard is removed.
    """

    def test_localhost_and_dotted_localhost_are_rejected(self) -> None:
        for url in ("http://localhost/", "http://app.localhost/", "https://LOCALHOST/x"):
            with self.subTest(url=url):
                with self.assertRaises(web.UnsafeWebTargetError) as ctx:
                    web.resolve_public_target(url)
                self.assertIn("non-public", str(ctx.exception))

    def test_ipv4_mapped_ipv6_literals_are_rejected(self) -> None:
        """`::ffff:127.0.0.1` is loopback wearing an IPv6 costume.

        Honest scope note: on current CPython this passes with or without the
        `_canonical_ip` unwrap, because `IPv6Address.is_global` already
        delegates for mapped addresses. It is a version-independence check on
        the outcome, not proof that the unwrap is load-bearing. The assertion
        that does pin the unwrap is `test_mapped_literal_pins_the_ipv4_form`.
        """
        for url in (
            "http://[::ffff:127.0.0.1]/",
            "http://[::ffff:169.254.169.254]/latest/meta-data/",
            "http://[::ffff:10.0.0.1]/",
        ):
            with self.subTest(url=url):
                with self.assertRaises(web.UnsafeWebTargetError):
                    web.resolve_public_target(url)

    def test_mapped_literal_pins_the_ipv4_form(self) -> None:
        """The unwrap decides which address string the socket is pinned to.

        Deleting `_canonical_ip`'s ipv4_mapped branch makes this fail: the
        target would carry `::ffff:8.8.8.8`, so the connection would be opened
        over a different address family than the one that was validated.
        """
        target = web.resolve_public_target("http://[::ffff:8.8.8.8]/x")
        self.assertEqual(("8.8.8.8",), target.addresses)

    def test_malformed_target_is_rejected_before_any_lookup(self) -> None:
        with self.assertRaises(web.UnsafeWebTargetError):
            web.resolve_public_target("http://example.com:not-a-port/")

    def test_hostname_is_required(self) -> None:
        with self.assertRaises(web.UnsafeWebTargetError) as ctx:
            web.resolve_public_target("http:///just-a-path")
        self.assertIn("hostname", str(ctx.exception))

    def test_unresolvable_hostname_fails_closed(self) -> None:
        with patch.object(web.socket, "getaddrinfo", side_effect=web.socket.gaierror("nope")):
            with self.assertRaises(web.UnsafeWebTargetError) as ctx:
                web.resolve_public_target("https://example.com/")
        self.assertIn("unable to resolve", str(ctx.exception))

    def test_empty_resolution_fails_closed(self) -> None:
        """An empty answer must not read as "nothing disallowed, proceed"."""
        with patch.object(web.socket, "getaddrinfo", return_value=[]):
            with self.assertRaises(web.UnsafeWebTargetError) as ctx:
                web.resolve_public_target("https://example.com/")
        self.assertIn("did not resolve", str(ctx.exception))

    def test_public_hostname_still_resolves(self) -> None:
        """Positive control: the guards above must not reject everything.

        Without this, returning `raise` unconditionally would satisfy every
        negative test in this class and read as a hardened boundary.
        """
        answer = [(web.socket.AF_INET, web.socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]
        with patch.object(web.socket, "getaddrinfo", return_value=answer):
            target = web.resolve_public_target("https://example.com/path")
        self.assertIn("93.184.216.34", str(target))


if __name__ == "__main__":
    unittest.main()
