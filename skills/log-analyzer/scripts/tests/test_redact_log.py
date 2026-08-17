"""Behavioural tests for scripts/redact_log.py.

These tests EXECUTE the redactor. The previous test suite only asserted that the
string "REDACTED" appeared somewhere in the documentation, which is why two
non-working redaction recipes shipped undetected. Every assertion here is about
observed output, and every category promised by SKILL.md Gate 2 has both a
positive (it is redacted) and a negative (it is not over-redacted) case.
"""

from __future__ import annotations

import importlib.util
import io
import json
import pathlib
import re
import subprocess
import sys

import pytest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
SCRIPT_PATH = SCRIPTS / "redact_log.py"


def _load():
    # This repo runs pytest with --import-mode=importlib, so a bare sibling
    # import does not resolve. Load by path and register before executing.
    spec = importlib.util.spec_from_file_location("redact_log", SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["redact_log"] = mod
    spec.loader.exec_module(mod)
    return mod


R = _load()


def red(text: str, **kw) -> str:
    return R.Redactor(**kw).text(text)


def red_json(line: str, **kw) -> dict:
    return json.loads(R.Redactor(**kw).line(line, json_mode=True))


# ──────────────────────────────────────────────────────────────────────
class TestSecretsAreRedacted:
    """Positive cases: every Gate 2 class must actually disappear."""

    def test_bearer_token(self):
        out = red("auth failed Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJhIjoxfQ.sig")
        assert "eyJhbGciOiJIUzI1NiJ9" not in out
        assert "REDACTED" in out

    def test_basic_auth_scheme(self):
        out = red("Authorization: Basic YWxpY2U6aHVudGVyMg==")
        assert "YWxpY2U6aHVudGVyMg" not in out

    @pytest.mark.parametrize("secret", [
        "sk-abcdefghijklmnopqrstuvwxyz012345",
        "AKIAIOSFODNN7EXAMPLE",
        "xoxb-123456789012-abcdefghijkl",
        "ghp_abcdefghijklmnopqrstuvwxyz0123456789",
        "glpat-abcdefghijklmnopqrstu",
        "AIzaSyA1234567890abcdefghijklmnopqrstuv",
    ])
    def test_api_keys(self, secret):
        out = red(f"call failed key={secret} status=401")
        assert secret not in out, f"{secret!r} survived redaction"

    def test_url_password(self):
        out = red('dial error dsn="postgres://appuser:hunter2@db.internal:5432/orders"')
        assert "hunter2" not in out
        assert "appuser" in out, "username is not a secret and aids debugging"

    def test_cookie_header(self):
        out = red("req Cookie: session=abc123; theme=dark")
        assert "abc123" not in out

    def test_bare_session_id(self):
        out = red("resume sessionid=9f8e7d6c5b4a3210 ok")
        assert "9f8e7d6c5b4a3210" not in out

    def test_password_key_value(self):
        out = red("login attempt user=bob password=hunter2 result=fail")
        assert "hunter2" not in out
        assert "bob" in out

    def test_email(self):
        out = red("notify alice@example.com failed")
        assert "alice@example.com" not in out
        assert "a***@example.com" in out, "domain must survive for triage"

    def test_ssn(self):
        assert "123-45-6789" not in red("kyc record 123-45-6789 rejected")

    def test_credit_card_luhn_valid(self):
        # 4111111111111111 is the canonical Luhn-valid test PAN.
        out = red("charge failed card=4111111111111111 amount=20")
        assert "4111111111111111" not in out
        assert "REDACTED-PAN" in out

    def test_grouped_credit_card(self):
        out = red("card 4111 1111 1111 1111 declined")
        assert "4111 1111 1111 1111" not in out

    def test_international_phone(self):
        assert "+1-555-123-4567" not in red("sms to +1-555-123-4567 failed")

    def test_private_key_block(self):
        blob = ("-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA\n"
                "-----END RSA PRIVATE KEY-----")
        out = red(blob)
        assert "MIIEowIBAAKCAQEA" not in out
        assert "REDACTED-PRIVATE-KEY" in out


# ──────────────────────────────────────────────────────────────────────
class TestNoOverRedaction:
    """Negative cases. Over-redaction destroys the investigation."""

    def test_trace_id_survives(self):
        tid = "4bf92f3577b34da6a3ce929d0e0e4736"
        assert tid in red(f"timeout trace_id={tid} svc=checkout")

    def test_request_id_survives(self):
        assert "req-01HX8Z9K2M" in red("fail request_id=req-01HX8Z9K2M")

    def test_iso8601_timestamp_survives(self):
        line = "2026-04-28T08:14:31.047Z ERROR reserveStock deadline"
        assert "2026-04-28T08:14:31.047Z" in red(line), \
            "a greedy phone regex mangles ISO timestamps"

    def test_epoch_millis_not_treated_as_card(self):
        # 1714298071049 is a real epoch-ms value that ALSO passes Luhn, so only
        # the field-name guard can save it. Do not swap in a Luhn-failing value:
        # that silently turns this test into a duplicate of the Luhn test below.
        assert R._luhn_ok("1714298071049"), "fixture must be Luhn-valid to be meaningful"
        for key in ("time", "ts", "timestamp", "epoch_ms"):
            line = f"{key}=1714298071049 level=error"
            assert "1714298071049" in red(line), f"{key} value was eaten as a PAN"

    def test_luhn_invalid_long_digits_survive(self):
        # An internal 16-digit order number that fails Luhn is not a card.
        assert not R._luhn_ok("1234567890123456")
        assert "1234567890123456" in red("order=1234567890123456 failed")

    def test_cookie_rule_stops_at_the_cookie_list(self):
        """Consuming to end-of-line swallowed the correlation IDs that follow,
        contradicting the promise to preserve them."""
        out = red("GET /x Cookie: session=abc; theme=dark "
                  "trace_id=4bf92f35 request_id=req-77 status=500")
        assert "abc" not in out and "theme=dark" not in out
        for keep in ("trace_id=4bf92f35", "request_id=req-77", "status=500"):
            assert keep in out, f"cookie rule ate {keep}"

    def test_numeric_correlation_id_survives_in_json(self):
        # Some tracing SDKs emit decimal trace IDs. 1234567890123452 is
        # Luhn-valid, so PRESERVED_KEYS is the only thing protecting it.
        assert R._luhn_ok("1234567890123452"), "fixture must be Luhn-valid"
        out = red_json('{"trace_id":"1234567890123452","msg":"ok"}')
        assert out["trace_id"] == "1234567890123452", \
            "a numeric trace_id must not be redacted as a card number"

    def test_semver_and_ports_survive(self):
        line = "inventory-svc v1.23.4 listening on 0.0.0.0:8080 pid=41235"
        assert "v1.23.4" in red(line)
        assert "8080" in red(line)

    def test_ip_kept_by_default_masked_on_request(self):
        line = "peer 203.0.113.42 reset"
        assert "203.0.113.42" in red(line), "internal reports keep IPs"
        assert "203.0.113.42" not in red(line, mask_ip=True)

    def test_already_redacted_text_is_idempotent(self):
        once = red("Authorization: Bearer eyJabcdefghijklmnop")
        assert red(once) == once, "re-running the redactor must be a no-op"


# ──────────────────────────────────────────────────────────────────────
class TestJsonMode:

    def test_sensitive_key_redacted_regardless_of_value_shape(self):
        out = red_json('{"password":"a","level":"ERROR"}')
        assert out["password"] == R.REDACTED
        assert out["level"] == "ERROR"

    def test_correlation_keys_preserved(self):
        tid = "4bf92f3577b34da6a3ce929d0e0e4736"
        out = red_json(f'{{"trace_id":"{tid}","span_id":"00f067aa","msg":"x"}}')
        assert out["trace_id"] == tid
        assert out["span_id"] == "00f067aa"

    @pytest.mark.parametrize("secret,marker", [
        # For email the domain is deliberately retained everywhere (it aids
        # triage); the identifying local part is what must not survive.
        ("alice@example.com", "alice"),
        ("Bearer eyJhbGciOiJIUzI1NiJ9.abc", "eyJhbGciOiJIUzI1NiJ9"),
        ("sk-abcdefghijklmnopqrstuvwxyz012345", "sk-abcdefghij"),
        ("postgres://u:hunter2@db/orders", "hunter2"),
    ])
    def test_preserved_key_is_not_a_bypass(self, secret, marker):
        """Preserving the FIELD must not mean trusting its VALUE. Anything that
        lands in a correlation field -- misconfigured propagation, a caller
        stuffing user input -- is still a leak."""
        out = red_json(json.dumps({"trace_id": secret, "msg": "x"}))
        assert marker not in out["trace_id"], \
            f"secret survived because the key was named trace_id: {out['trace_id']!r}"

    def test_nested_values_redacted(self):
        out = red_json('{"http":{"headers":{"authorization":"Bearer eyJabc"}},"n":1}')
        assert "eyJabc" not in json.dumps(out)

    def test_secret_inside_free_text_message(self):
        out = red_json('{"msg":"failed for alice@example.com","level":"WARN"}')
        assert "alice@example.com" not in out["msg"]
        assert out["level"] == "WARN"

    def test_numeric_epoch_field_untouched(self):
        out = red_json('{"time":1714298071040,"msg":"ok"}')
        assert out["time"] == 1714298071040

    def test_non_json_line_falls_back_to_text_mode(self):
        r = R.Redactor()
        out = r.line("\tat com.example.Foo(Foo.java:42) user=bob@example.com", json_mode=True)
        assert "bob@example.com" not in out
        assert r.json_failed == 1, "stack-trace lines must be counted, not dropped"


# ──────────────────────────────────────────────────────────────────────
class TestVerifyMode:

    def test_detects_residual_secret(self):
        hits = R.verify(["Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.abc"])
        assert hits, "verify must flag an unredacted bearer token"

    def test_clean_after_redaction(self):
        raw = ("2026-04-28T08:14:31Z ERROR auth Bearer eyJhbGciOiJIUzI1NiJ9.sig "
               "user alice@example.com ssn 123-45-6789 "
               "dsn postgres://u:pw@h/db trace_id=4bf92f35")
        assert R.verify([red(raw)]) == {}, "redactor output must pass its own verifier"

    @pytest.mark.parametrize("line,category", [
        ("login user=bob password=hunter2", "secret_kv"),
        ("req Cookie: session=abc123; theme=dark", "cookie"),
        ("resume sessionid=9f8e7d6c5b4a3210", "session"),
        ("charge card=4111111111111111", "pan"),
        ("sms to +1-555-123-4567", "phone"),
        ("Authorization: Basic YWxpY2U6aHVudGVyMg==", "authorization"),
        ("kyc 123-45-6789", "govt_id"),
        ("notify alice@example.com", "email"),
        ("dsn postgres://u:pw@h/db", "url_password"),
        ("key=sk-abcdefghijklmnopqrstuvwxyz012345", "api_key"),
    ])
    def test_verify_covers_every_category(self, line, category):
        """A verifier narrower than the redactor converts an unchecked leak into
        a positive assurance. `password=` and `Cookie:` were both reported clean
        by an earlier six-entry residue table."""
        hits = R.verify([line])
        assert category in hits, f"--verify missed {category}: {line!r} reported clean"

    def test_verify_covers_all_declared_rules(self):
        """Structural guard: no rule may exist that verify cannot detect."""
        rule_names = {name for name, _, _ in R._RULES}
        probes = {
            "private_key": "-----BEGIN RSA PRIVATE KEY-----",
            "bearer": "Bearer eyJhbGciOiJIUzI1NiJ9.abc",
            "authorization": "Authorization: Basic YWxpY2U=",
            "cookie": "Cookie: a=b", "session": "sessionid=abc123",
            "url_password": "postgres://u:pw@h/db",
            "api_key": "sk-abcdefghijklmnopqrstuvwxyz012345",
            "secret_kv": "password=hunter2", "govt_id": "123-45-6789",
            "pan": "4111111111111111", "phone": "+1-555-123-4567",
            "email": "alice@example.com", "iban": "GB82WEST12345698765432",
        }
        # Rules only active under a policy flag are probed in their own tests.
        rule_names -= {"ip", "external_kv"}
        assert rule_names <= set(probes), \
            f"new rule with no verify probe: {rule_names - set(probes)}"
        for name, probe in probes.items():
            assert name in R.verify([probe]), f"verify cannot detect rule {name!r}"

    @pytest.mark.parametrize("mode", [
        {}, {"mask_ip": True}, {"redact_user_id": True},
        {"mask_ip": True, "redact_user_id": True},
    ])
    def test_json_key_redaction_is_counter_idempotent(self, mode):
        """Key-based redaction must not re-fire on its own sentinel, or the
        external round trip (scan -> verify with the same flags) never converges."""
        line = json.dumps({"password": "x", "user_id": "u-1", "tenant_id": "acme",
                           "src_ip": "203.0.113.42", "trace_id": "t1"})
        once = R.Redactor(**mode).line(line, json_mode=True)
        r2 = R.Redactor(**mode)
        assert r2.line(once, json_mode=True) == once
        assert not r2.counts, f"re-fired with {mode}: {dict(r2.counts)}"

    @pytest.mark.parametrize("line", [
        "Authorization: Bearer eyJabcdefghijkl", "Authorization: Basic YWxpY2U6cHc=",
        "req Cookie: session=abc123; theme=dark", "resume sessionid=9f8e7d6c5b4a3210",
        "dsn postgres://appuser:hunter2@db/orders", "user=bob password=hunter2",
        "key=sk-abcdefghijklmnopqrstuvwxyz012345", "kyc 123-45-6789",
        "card=4111111111111111", "sms +1-555-123-4567", "notify alice@example.com",
    ])
    def test_rules_are_counter_idempotent(self, line):
        """verify() defines residue as 'the redactor would still act here', so a
        rule that re-fires on its own output reports a permanent false leak."""
        once = red(line)
        assert R.verify([once]) == {}, \
            f"redacting {line!r} yields {once!r}, which verify still flags"


# ──────────────────────────────────────────────────────────────────────
class TestCliContract:
    """The reference docs tell the user to run these exact invocations."""

    def _run(self, args, stdin):
        return subprocess.run(
            [sys.executable, str(SCRIPT_PATH), *args],
            input=stdin, capture_output=True, text=True, timeout=60,
        )

    def test_text_mode_stdin(self):
        p = self._run(["scan"], "user alice@example.com Bearer eyJabcdefghij\n")
        assert p.returncode == 0, p.stderr
        assert "alice@example.com" not in p.stdout
        assert "categories:" in p.stderr

    def test_json_mode_stdin(self):
        p = self._run(["scan", "--json"], '{"msg":"hi","password":"x","trace_id":"t1"}\n')
        assert p.returncode == 0, p.stderr
        out = json.loads(p.stdout)
        assert out["password"] == R.REDACTED
        assert out["trace_id"] == "t1"

    def test_verify_exit_codes(self):
        dirty = self._run(["verify"], "Bearer eyJhbGciOiJIUzI1NiJ9.abcdef\n")
        assert dirty.returncode == 1, "verify must exit non-zero on residue"
        clean = self._run(["verify"], "level=info msg=ok trace_id=abc\n")
        assert clean.returncode == 0, clean.stderr

    def test_summary_json_is_parseable(self):
        p = self._run(["scan", "--summary-json"], "user alice@example.com\n")
        summary = json.loads(p.stderr.strip().splitlines()[-1])
        assert summary["lines"] == 1
        assert summary["categories"].get("email") == 1

    def test_multiline_private_key_via_cli(self):
        """The PEM rule is DOTALL, but the CLI reads one line at a time, so the
        rule could never fire through the real entry point. The library-level
        test passed the whole blob as one string and so never caught it -- always
        exercise the shipped path, not just the function."""
        pem = ("2026-04-28T08:00:00Z ERROR key load failed\n"
               "-----BEGIN RSA PRIVATE KEY-----\n"
               "MIIEowIBAAKCAQEAsecretmaterialhere\n"
               "AnotherLineOfSecretMaterial\n"
               "-----END RSA PRIVATE KEY-----\n"
               "2026-04-28T08:00:01Z INFO continuing\n")
        p = self._run(["scan"], pem)
        assert p.returncode == 0, p.stderr
        assert "secretmaterial" not in p.stdout.lower(), "private key body leaked"
        assert "REDACTED-PRIVATE-KEY" in p.stdout
        assert "continuing" in p.stdout, "lines after the block must survive"

    def test_multiline_private_key_fails_verify(self):
        pem = ("-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBsecret\n"
               "-----END RSA PRIVATE KEY-----\n")
        assert self._run(["verify"], pem).returncode == 1

    def test_line_count_preserved_across_a_key_block(self):
        """Blank placeholders keep line offsets aligned with the original file,
        so `path:line` citations in a report still point at the right place."""
        src = "a\n-----BEGIN RSA PRIVATE KEY-----\nbody\n-----END RSA PRIVATE KEY-----\nz\n"
        p = self._run(["scan"], src)
        assert len(p.stdout.splitlines()) == len(src.splitlines())


# ──────────────────────────────────────────────────────────────────────
class TestOutputFlag:
    """--output exists so the mandatory redaction step needs no shell `>`,
    which the Command Safety Contract forbids."""

    def _run(self, args, stdin=""):
        return subprocess.run([sys.executable, str(SCRIPT_PATH), *args],
                              input=stdin, capture_output=True, text=True, timeout=60)

    def test_writes_the_file(self, tmp_path):
        dst = tmp_path / "clean.log"
        p = self._run(["write", "--output", str(dst)], "user alice@example.com\n")
        assert p.returncode == 0, p.stderr
        assert "alice@example.com" not in dst.read_text()
        assert "a***@example.com" in dst.read_text()

    def test_refuses_to_overwrite_existing(self, tmp_path):
        dst = tmp_path / "exists.log"
        dst.write_text("ORIGINAL LOG DATA")
        p = self._run(["write", "--output", str(dst)], "x\n")
        assert p.returncode == 2, "must refuse rather than clobber"
        assert dst.read_text() == "ORIGINAL LOG DATA", "existing file was modified"

    def test_refuses_symlink_destination(self, tmp_path):
        target = tmp_path / "victim.log"
        target.write_text("VICTIM")
        link = tmp_path / "link.log"
        link.symlink_to(target)
        p = self._run(["write", "--output", str(link)], "x\n")
        assert p.returncode == 2, "must not follow a symlink to an existing file"
        assert target.read_text() == "VICTIM"

    def test_cannot_redact_a_log_onto_itself(self, tmp_path):
        src = tmp_path / "app.log"
        src.write_text("user alice@example.com\n")
        p = self._run(["write", str(src), "--output", str(src)])
        assert p.returncode == 2
        assert "alice@example.com" in src.read_text(), "source log was destroyed"

    def test_verify_rejects_output_flag(self, tmp_path):
        p = self._run(["verify", "--output", str(tmp_path / "x")], "x\n")
        assert p.returncode != 0, "--verify writes no output; combining is a mistake"

    @pytest.mark.parametrize("sub", ["scan", "verify"])
    def test_readonly_subcommands_cannot_write(self, sub, tmp_path):
        """These two are AUTO-APPROVED in SKILL.md, so their inability to create a
        file is a security property, not a convenience. Enforce it by execution:
        the previous single entry point was justified as 'stdout only' while
        accepting --output."""
        dest = tmp_path / "must_not_exist"
        p = self._run([sub, "--output", str(dest)], "x\n")
        assert p.returncode != 0
        assert not dest.exists(), f"{sub} created a file"
        p2 = self._run([sub, "-o", str(dest)], "x\n")
        assert p2.returncode != 0 and not dest.exists(), f"{sub} accepted -o"

    def test_write_requires_an_explicit_output(self):
        """`write` with no -o would silently behave like `scan`, blurring the
        very boundary the split exists to draw."""
        p = self._run(["write"], "x\n")
        assert p.returncode != 0, "write must demand --output"


# ──────────────────────────────────────────────────────────────────────
class TestVerifyMatchesRedactionPolicy:
    """`verify` checks the policy it is told about. Told the wrong policy, it
    reports `clean` on a file that is not clean for its intended audience."""

    EXTERNAL = ('{"user_id":"u-4471","tenant_id":"acme-corp","org_id":"org-991",'
                '"src_ip":"203.0.113.42","trace_id":"t-1","msg":"ok"}')

    def _run(self, args, stdin=""):
        return subprocess.run([sys.executable, str(SCRIPT_PATH), *args],
                              input=stdin, capture_output=True, text=True, timeout=60)

    def test_external_flags_are_honoured_by_verify(self):
        p = self._run(["verify", "--json", "--mask-ip", "--redact-user-id"],
                      self.EXTERNAL + "\n")
        assert p.returncode == 1, (
            "verify reported clean on a file carrying user_id, tenant_id and an IP "
            "while being asked to check the external policy"
        )
        for cat in ("user_id", "tenant_id", "ip"):
            assert cat in p.stderr, f"verify did not report residual {cat}"

    def test_internal_policy_still_passes_the_same_file(self):
        """Guards the over-correction: those fields are legitimately KEPT for an
        internal report, so the default policy must not flag them."""
        p = self._run(["verify", "--json"], self.EXTERNAL + "\n")
        assert p.returncode == 0, p.stderr

    @pytest.mark.parametrize("key", [
        "user_id", "tenant_id", "org_id", "account_id", "customer_id",
        "username", "user_email", "email",
    ])
    @pytest.mark.parametrize("fmt", ["json", "text", "text_in_json_stream"])
    def test_external_mode_covers_the_list_in_every_format(self, key, fmt):
        """EXTERNAL_ONLY_KEYS originally lived only in the JSON walker, so a plain
        text log -- and any non-JSON continuation line inside a JSON stream, such
        as a stack-trace frame -- leaked `user_id=` and `tenant_id=` verbatim."""
        r = R.Redactor(redact_user_id=True)
        if fmt == "json":
            out = r.line(json.dumps({key: "sensitive-value", "trace_id": "t1"}),
                         json_mode=True)
        elif fmt == "text":
            out = r.line(f"req {key}=sensitive-value trace_id=t1", json_mode=False)
        else:
            out = r.line(f"\tat Foo.java:42 {key}=sensitive-value trace_id=t1",
                         json_mode=True)  # unparseable -> text fallback
        assert "sensitive-value" not in out, \
            f"{key} survived an external-report redaction in {fmt} form: {out}"
        assert "t1" in out, "correlation ID must still survive"

    @pytest.mark.parametrize("key", ["user_id", "tenant_id", "org_id"])
    @pytest.mark.parametrize("fmt", ["json", "text"])
    def test_internal_mode_keeps_them_in_every_format(self, key, fmt):
        """These are deliberately KEPT internally -- user_id walks traces and
        tenant_id confirms blast radius. Over-redacting breaks the investigation."""
        r = R.Redactor()
        line = (json.dumps({key: "keep-me"}) if fmt == "json"
                else f"req {key}=keep-me")
        assert "keep-me" in r.line(line, json_mode=(fmt == "json"))

    def test_text_external_rule_is_counter_idempotent(self):
        r = R.Redactor(redact_user_id=True)
        once = r.line("req user_id=u-1 tenant_id=acme", json_mode=False)
        assert R.verify([once], redact_user_id=True) == {}
    def test_round_trip_external(self, tmp_path):
        """scan with external flags, then verify with the same flags, is clean."""
        red = self._run(["scan", "--json", "--mask-ip", "--redact-user-id"],
                        self.EXTERNAL + "\n")
        assert red.returncode == 0, red.stderr
        chk = self._run(["verify", "--json", "--mask-ip", "--redact-user-id"], red.stdout)
        assert chk.returncode == 0, f"external output failed its own verifier: {chk.stderr}"




# ──────────────────────────────────────────────────────────────────────
class TestQuotedValues:
    """The value pattern originally EXCLUDED quote characters, so it stopped at
    the opening `"` and every quoted secret survived `verify` as clean. Quoting is
    the normal way to write a value containing a space, so this was not an edge
    case -- it was a bypass for the whole key=value rule family."""

    SECRETS = [
        ("password", "hunter 2"), ("token", "abc def"), ("api_key", "k 1"),
        ("client_secret", "s 2"), ("sessionid", "9f8e 7d6c"),
    ]
    EXTERNAL = [("user_id", "u-17"), ("tenant_id", "acme corp"),
                ("org_id", "org-9"), ("customer_id", "cust 42")]

    @pytest.mark.parametrize("quote", ['"', "'", ""])
    @pytest.mark.parametrize("key,val", SECRETS)
    def test_quoted_secret_is_redacted(self, key, val, quote):
        v = val if quote else val.replace(" ", "")
        line = f'op {key}={quote}{v}{quote} status=fail'
        out = red(line)
        assert v not in out, f"quoted secret survived: {out}"
        assert "status=fail" in out, "rule consumed past the value"

    @pytest.mark.parametrize("quote", ['"', "'", ""])
    @pytest.mark.parametrize("key,val", EXTERNAL)
    def test_quoted_external_id_is_redacted(self, key, val, quote):
        v = val if quote else val.replace(" ", "")
        line = f'req {key}={quote}{v}{quote} trace_id=t1'
        out = red(line, redact_user_id=True)
        assert v not in out, f"quoted external id survived: {out}"
        assert "trace_id=t1" in out, "correlation id must survive"

    @pytest.mark.parametrize("key,val", SECRETS + EXTERNAL)
    def test_quoted_value_fails_verify(self, key, val):
        line = f'op {key}="{val}"'
        assert R.verify([line], redact_user_id=True), \
            f'verify reported clean on {line!r}'

    def test_json_colon_form_in_text_fallback(self):
        """A JSON line that fails to parse falls back to text handling, where the
        key carries quotes: `"password":"x"`."""
        r = R.Redactor(redact_user_id=True)
        out = r.line('\tat Foo.java:9 {"password":"hunter2","user_id":"u-1"}',
                     json_mode=True)
        assert "hunter2" not in out and "u-1" not in out, out

    @pytest.mark.parametrize("line", [
        '{"password":"hunter2"}',
        "{'token':'abc'}",
        '{"user_id":"u-1"}',
    ])
    def test_no_dangling_quote_left_behind(self, line):
        """_KEY_OPEN consumes the key's opening quote. Without it the output is
        `"password=***REDACTED***` -- unbalanced quotes that read as corruption in
        a report. The secret is gone either way; this is about legibility."""
        out = red(line, redact_user_id=True)
        assert out.count('"') % 2 == 0 and out.count("'") % 2 == 0, \
            f"unbalanced quotes in redacted output: {out!r}"

    def test_quoted_authorization_header(self):
        out = red('hdrs Authorization="Bearer abc.def" ua=curl')
        assert "abc.def" not in out
        assert "ua=curl" in out

    @pytest.mark.parametrize("key,val", SECRETS + EXTERNAL)
    def test_quoted_form_is_counter_idempotent(self, key, val):
        once = red(f'op {key}="{val}"', redact_user_id=True)
        assert R.verify([once], redact_user_id=True) == {}, \
            f"re-fired on its own output: {once!r}"

    def test_unrelated_quoted_values_survive(self):
        line = 'msg="request completed" path="/v1/checkout" level="INFO"'
        assert red(line, redact_user_id=True) == line, "over-redacted ordinary fields"

    def test_key_suffix_is_not_matched(self):
        """`mypassword=` and `not_user_id=` must not trip the word-boundary."""
        for line in ["mypassword=x", "xtoken=y"]:
            assert line in red(f"a {line} b"), f"matched a key suffix in {line}"


# ──────────────────────────────────────────────────────────────────────
class TestIban:
    """SKILL.md Gate 2 lists 'Credit card / IBAN'. A documented category with no
    implementation is a promise the tool does not keep."""

    VALID = [
        "GB82WEST12345698765432",              # UK, the ISO 13616 example
        "DE89370400440532013000",              # Germany
        "FR1420041010050500013M02606",         # France, contains a letter mid-body
        "GB82 WEST 1234 5698 7654 32",         # space-grouped
    ]

    @pytest.mark.parametrize("iban", VALID)
    def test_valid_iban_is_redacted(self, iban):
        out = red(f"payout iban={iban} amount=90")
        assert iban not in out, f"IBAN survived: {out}"
        assert "REDACTED-IBAN" in out

    @pytest.mark.parametrize("iban", VALID)
    def test_valid_iban_fails_verify(self, iban):
        assert "iban" in R.verify([f"payout iban={iban}"])

    @pytest.mark.parametrize("text", [
        "GB82WEST12345698765433",   # last digit changed -> checksum fails
        "DE89370400440532013001",
    ])
    def test_bad_checksum_is_left_alone(self, text):
        """Shape alone matches build IDs and resource names; MOD-97 is what makes
        the rule usable."""
        assert text in red(f"ref={text}")

    @pytest.mark.parametrize("text", [
        "BUILD2024ABCD1234", "AB12CDEF3456GH78", "US20240101ABCDEF01",
    ])
    def test_identifier_shapes_survive(self, text):
        assert text in red(f"artifact {text} pushed")

    def test_mod97_helper(self):
        assert R._iban_ok("GB82WEST12345698765432")
        assert R._iban_ok("gb82 west 1234 5698 7654 32"), "case/space insensitive"
        assert not R._iban_ok("GB82WEST12345698765433")
        assert not R._iban_ok("GB82"), "too short"

    @pytest.mark.parametrize("iban", [
        "gb82west12345698765432",          # fully lower case
        "Gb82WeSt12345698765432",          # mixed
        "de89370400440532013000",
    ])
    def test_case_insensitive(self, iban):
        """The helper upcases before checking, so an uppercase-only pattern made
        it accept a form it was never offered: a log normalised to lower case
        leaked. The checksum does the filtering, so widening the shape is free."""
        assert R._iban_ok(iban), "fixture must be a valid IBAN"
        out = red(f"payout iban={iban}")
        assert iban not in out, f"lower/mixed-case IBAN survived: {out}"
        assert "iban" in R.verify([f"payout iban={iban}"])

    @pytest.mark.parametrize("text", [
        "build2024abcd1234", "ab12cdef3456gh78", "a1b2c3d4e5f6a7b8",
    ])
    def test_lowercase_identifiers_still_survive(self, text):
        """Guard the widening: IGNORECASE must not start eating commit hashes and
        build tags."""
        assert text in red(f"artifact {text} pushed")

    def test_iban_is_idempotent(self):
        once = red("iban=GB82WEST12345698765432")
        assert R.verify([once]) == {}

    @pytest.mark.parametrize("key", ["trace_id", "request_id", "span_id",
                                     "correlation_id"])
    def test_iban_in_a_preserved_field_is_still_redacted(self, key):
        """Preserving a correlation FIELD must not preserve a bank account that
        was misfiled into it. IBAN carries MOD-97, so unlike Luhn it is safe to
        run over identifier values."""
        out = red_json(json.dumps({key: "GB82WEST12345698765432", "msg": "x"}))
        assert "GB82WEST" not in out[key], f"IBAN survived in {key}: {out[key]}"

    def test_numeric_id_in_preserved_field_still_survives(self):
        """Guard the over-correction: adding iban to the secrets-only set must not
        drag pan/phone in with it."""
        out = red_json('{"trace_id":"1234567890123452","msg":"x"}')
        assert out["trace_id"] == "1234567890123452"


# ──────────────────────────────────────────────────────────────────────
class TestPhoneMasking:
    """SKILL.md Gate 2 and log-pii-redaction.md both promise the middle digits are
    masked and the last four kept. The script masked everything, so the docs and
    the tool disagreed and nothing failed."""

    @pytest.mark.parametrize("raw,keep", [
        ("+1-555-123-4567", "4567"),
        ("+44 20 7946 0958", "0958"),
        ("555-123-9876", "9876"),
    ])
    def test_last_four_survive(self, raw, keep):
        out = red(f"sms to {raw} failed")
        assert raw not in out, "phone not masked"
        assert keep in out, f"documented last-four not preserved: {out}"

    def test_masking_is_idempotent(self):
        once = red("sms +1-555-123-4567")
        assert R.verify([once]) == {}, f"re-fired on {once!r}"


# ──────────────────────────────────────────────────────────────────────
class TestDocTableMatchesImplementation:
    """Gate 2's table is a promise about output. It said IBAN produced
    ***REDACTED-PAN***, and that phones kept the last four while the script masked
    them entirely. Pin the table to observed behaviour so prose cannot drift."""

    GATE2 = (SCRIPTS.parent / "SKILL.md").read_text(encoding="utf-8")

    # (sample input, replacement string the table promises)
    CASES = [
        ("hdr Bearer eyJhbGciOiJIUzI1NiJ9.x", "Bearer ***REDACTED***"),
        ("Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.x", "Authorization: ***REDACTED***"),
        ("key=sk-abcdefghijklmnopqrstuvwxyz012345", "***REDACTED-API-KEY***"),
        ("dsn postgres://user:hunter2@host/db", "postgres://user:***@host/db"),
        ("mail alice@example.com", "a***@example.com"),
        ("sms +1-555-123-4567", "+***-***-4567"),
        ("card=4111111111111111", "***REDACTED-PAN***"),
        ("iban=GB82WEST12345698765432", "***REDACTED-IBAN***"),
        ("kyc 123-45-6789", "***REDACTED-ID***"),
        ("req Cookie: session=abc123", "Cookie: ***REDACTED***"),
    ]

    @pytest.mark.parametrize("sample,promised", CASES)
    def test_script_emits_the_promised_replacement(self, sample, promised):
        assert promised in red(sample), \
            f"table promises {promised!r} but script produced {red(sample)!r}"

    @pytest.mark.parametrize("sample,promised", CASES)
    def test_gate2_table_lists_the_replacement(self, sample, promised):
        assert promised in self.GATE2, \
            f"script emits {promised!r} but SKILL.md Gate 2 does not list it"

    def test_iban_is_not_described_as_a_card(self):
        assert not re.search(r"Credit card / IBAN", self.GATE2), \
            "IBAN and PAN have different detectors and different replacements"


# ──────────────────────────────────────────────────────────────────────
class TestDecliningCallbacksDoNotReportResidue:
    """`re.subn` counts MATCHES; the pan and iban callbacks decline when the
    checksum fails. Counting matches made verify fail on any log containing a
    13-19 digit order number -- a false alarm that makes the gate unusable."""

    @pytest.mark.parametrize("line", [
        "order=1234567890123456 status=ok",     # 16 digits, Luhn-invalid
        "ts=1714298071049 level=error",         # epoch ms, Luhn-VALID, key-guarded
        "artifact BUILD2024ABCD1234 pushed",    # IBAN-shaped, checksum-invalid
        "ref=GB82WEST12345698765433",           # IBAN-shaped, checksum-invalid
    ])
    def test_declined_match_is_not_counted(self, line):
        r = R.Redactor()
        assert r.text(line) == line, "nothing should change"
        assert not r.counts, f"declined match was counted: {dict(r.counts)}"
        assert R.verify([line]) == {}, "verify reported residue on a clean line"
