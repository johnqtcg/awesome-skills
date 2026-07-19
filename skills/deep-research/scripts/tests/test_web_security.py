"""Security boundaries for all deep-research Web egress."""

import importlib.util
import sys
import unittest
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


if __name__ == "__main__":
    unittest.main()

